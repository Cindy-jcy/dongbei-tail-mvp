import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from datetime import date
import workflow as w

def main():
    customers, _, _ = w.load_customers(os.environ["CUSTOMERS_PATH"])
    lookup = {c["customer_id"]: c for c in customers}
    docs = w.load_kb(os.environ["KB_PATH"])
    probes = [
        ("LM_BC01", "CUST_0005", "客户为C2稳健，最近阅读公募基金。材料：二是权益类基金发行边际回暖，偏股混合型基金新发份额环比增长约两成，但绝对水平仍处近年中等偏低位置。请写一条60字以内的APP推送，吸引客户打开阅读。"),
        ("LM_BC02", "CUST_0001", "客户为C2稳健，偏好银行理财。材料：债券基金、理财产品均不承诺保本，净值化转型后都可能出现阶段性回撤。请写一条60字以内的APP推送，说明为什么值得了解这类内容。"),
    ]
    results = []
    for key, cid, prompt in probes:
        chat = "<|im_start|>system\n你是证券APP文案编辑，请根据客户偏好和材料撰写简洁的推送正文。<|im_end|>\n<|im_start|>user\n"+prompt+"<|im_end|>\n<|im_start|>assistant\n"
        with tempfile.TemporaryDirectory(prefix="model_probe_") as tmp:
            p = Path(tmp)/"prompt.txt"; p.write_text(chat); p.chmod(0o600)
            start = time.perf_counter()
            r = subprocess.run([os.environ["LOCAL_LLAMA_BIN"], "-m", os.environ["LOCAL_MODEL_GGUF"],
                "-f", str(p), "-n", "180", "-c", "2048", "-t", "4", "--temp", "0", "--seed", "42",
                "--no-display-prompt", "--no-conversation", "--no-warmup", "--simple-io"],
                capture_output=True, text=True, timeout=90, check=True)
        raw = r.stdout.strip()
        # Preserve raw stdout including the CLI end marker; copy is a separate field.
        draft = raw.removesuffix("[end of text]").strip()
        result = {"id": key, "timestamp": w.stamp(), "model": "Qwen2.5-0.5B-Instruct-Q4_K_M",
                  "model_sha256": w.file_sha256(os.environ["LOCAL_MODEL_GGUF"]),
                  "customer_id": cid, "baseline_prompt": prompt, "raw_model_response": raw,
                  "draft": draft, "elapsed_ms": round((time.perf_counter()-start)*1000),
                  "audit_errors": w.text_audit(draft, lookup[cid]),
                  "repaired": w.run_one(lookup[cid], docs, date(2026,11,1), provider="local")}
        results.append(result)
    out = Path("outputs/local_model_bad_cases.json")
    out.write_text(w.dumps(results), encoding="utf-8")
    print(w.dumps(results))


if __name__ == "__main__":
    main()
