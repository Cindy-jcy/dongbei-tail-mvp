"""Loopback-only teaching UI around the unchanged workflow v2.0.

No hosted service, third-party frontend or automatic outbound model call.
Historical evidence and newly executed inference are labeled separately.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import workflow as w

ROOT = Path(__file__).resolve().parent
SAMPLE_IDS = ("CUST_0005", "CUST_0003", "CUST_0001")
FUNCTIONS = ("load_customers", "segment", "allowed", "retrieve", "minimal_profile",
             "build_prompt", "local_model", "validate_decision", "compose", "text_audit", "run_one")


def load_config(path):
    if path.is_file():
        cfg = json.loads(path.read_text(encoding="utf-8"))
        for key in ("LOCAL_LLAMA_BIN", "LOCAL_MODEL_GGUF"):
            if cfg.get(key) and not os.environ.get(key):
                os.environ[key] = cfg[key]


class Demo:
    def __init__(self, customers, kb, run_date):
        self.customers, self.quarantine, self.audit = w.load_customers(customers)
        self.lookup = {c["customer_id"]: c for c in self.customers}
        self.docs = w.load_kb(kb)
        self.run_date = run_date
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()

    def profile(self, customer_id, mode):
        if customer_id not in SAMPLE_IDS or mode not in ("simulation", "current"):
            raise ValueError("请选择页面提供的客户和日期模式")
        c = self.lookup[customer_id]
        candidates = w.retrieve(c, self.docs, self.run_date, mode)
        all_reviewed = [{**s, "date": self.docs[s["doc"]]["date"],
                         "risk_allowed": w.allowed(s, c),
                         "selected": s in candidates} for s in w.CATALOG]
        return {"customer_id": customer_id, "assets": c["total_assets"],
                "risk": c["risk_level"], "holding": c["holding_preference"],
                "logins": c["login_days_30d"], "clicks": c["content_click_count_30d"],
                "risk_uncertain": c["risk_uncertain"], "activity_uncertain": c["activity_uncertain"],
                "segment": w.segment(c), "model_profile": w.minimal_profile(c),
                "candidates": candidates, "catalog": all_reviewed,
                "messages": w.build_prompt(c, candidates, self.docs, mode) if candidates else [],
                "mode": mode, "run_date": self.run_date.isoformat()}

    def summary(self):
        groups = Counter(w.segment(c) for c in self.customers)
        return {"audit": self.audit, "quarantine": self.quarantine, "segments": dict(groups),
                "long_tail": sum(v for k, v in groups.items() if k != "非长尾"),
                "model_paths_exist": all(Path(os.environ.get(k, "")).is_file()
                                         for k in ("LOCAL_LLAMA_BIN", "LOCAL_MODEL_GGUF")),
                "run_date": self.run_date.isoformat(), "token": self.token,
                "note": "文件存在不等于可运行，首次点击真实模型运行后才确认兼容性。"}

    def run(self, customer_id, mode, provider):
        self.profile(customer_id, mode)  # Validate identifiers before execution.
        if provider not in ("local", "offline"):
            raise ValueError("本演示只支持本地模型或明确标识的离线回放")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("已有运行任务，请等待完成")
        try:
            result = w.run_one(self.lookup[customer_id], self.docs, self.run_date, provider, mode)
            live_called = any("raw_model_response" in a for a in result.get("attempts", []))
            envelope = {"view_kind": "new_run", "requested_provider": provider,
                        "live_model_response_received": live_called,
                        "result": result}
            out = ROOT / "demo_runs"
            out.mkdir(exist_ok=True)
            name = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(3) + ".json"
            (out / name).write_text(w.dumps(envelope), encoding="utf-8")
            envelope["saved_file"] = "demo_runs/" + name
            return envelope
        finally:
            self.lock.release()


def source_function(name):
    if name not in FUNCTIONS:
        raise ValueError("未知函数")
    source = (ROOT / "workflow.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = source.splitlines()
    return {"file": "workflow.py", "function": name, "start_line": node.lineno,
            "end_line": node.end_lineno,
            "code": "\n".join(f"{i+1:>3}  {lines[i]}" for i in range(node.lineno-1, node.end_lineno))}


def handler_for(demo):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def safe_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def reply(self, status, value, content_type="application/json; charset=utf-8"):
            body = value if isinstance(value, bytes) else w.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.safe_host():
                return self.reply(403, {"error": "仅允许本机地址"})
            parsed = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if parsed.path == "/":
                    return self.reply(200, (ROOT / "demo.html").read_bytes(), "text/html; charset=utf-8")
                if parsed.path == "/api/summary":
                    return self.reply(200, demo.summary())
                if parsed.path == "/api/profile":
                    return self.reply(200, demo.profile(q.get("id", "CUST_0005"), q.get("mode", "simulation")))
                if parsed.path == "/api/source":
                    return self.reply(200, source_function(q.get("fn", "segment")))
                if parsed.path == "/api/record":
                    cid = q.get("id", "CUST_0005")
                    if cid not in SAMPLE_IDS:
                        raise ValueError("未知客户")
                    records = json.loads((ROOT / "live_local_outputs/examples.json").read_text(encoding="utf-8"))
                    return self.reply(200, {"view_kind": "historical_record", "live_model_response_received": False,
                                            "result": next(x for x in records if x["customer_id"] == cid)})
                if parsed.path == "/api/badcases":
                    return self.reply(200, json.loads((ROOT / "outputs/local_model_bad_cases.json").read_text(encoding="utf-8")))
                return self.reply(404, {"error": "未找到页面"})
            except FileNotFoundError:
                return self.reply(404, {"error": "本机未附历史证据文件。代码仓库不包含这些资料；请使用本地演示包。"})
            except (ValueError, StopIteration):
                return self.reply(400, {"error": "请求参数不正确"})

        def do_POST(self):
            if not self.safe_host() or self.headers.get("X-Demo-Token") != demo.token:
                return self.reply(403, {"error": "请求未通过本机页面校验"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self.reply(403, {"error": "来源不匹配"})
            if urlparse(self.path).path != "/api/run":
                return self.reply(404, {"error": "未找到操作"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("请求大小不正确")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("请求格式不正确")
                return self.reply(200, demo.run(data.get("id"), data.get("mode"), data.get("provider")))
            except (ValueError, TypeError):
                return self.reply(400, {"error": "客户、日期模式或模型模式不正确"})
            except RuntimeError as exc:
                return self.reply(409, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="本机演示页面，不提供外网服务")
    parser.add_argument("--customers", default=str(ROOT / "input/mock_customers.txt"))
    parser.add_argument("--kb", default=str(ROOT / "input/knowledge_base.zip"))
    parser.add_argument("--config", type=Path, default=ROOT / "local_config.json")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run-date", default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    args = parser.parse_args()
    load_config(args.config)
    try:
        demo = Demo(args.customers, args.kb, date.fromisoformat(args.run_date))
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(demo))
    except (OSError, ValueError) as exc:
        raise SystemExit("启动失败：请核对原始资料路径、端口和日期。错误类型：" + type(exc).__name__)
    print(f"请在浏览器打开 http://127.0.0.1:{args.port}", flush=True)
    print("终端保持打开。结束时按 Ctrl+C。本页面只在本机提供服务。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
