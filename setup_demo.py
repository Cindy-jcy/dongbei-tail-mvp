"""Download only public official runtime artifacts; never read customer inputs."""
import hashlib
import json
from pathlib import Path
import platform
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
TAG = "b6500"
MODEL_SHA256 = "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024*1024), b""):
            h.update(part)
    return h.hexdigest()


def download(url, target):
    temporary = target.with_suffix(target.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "dongbei-local-demo/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, temporary.open("wb") as f:
        size, last = 0, 0
        while True:
            chunk = r.read(1024*1024)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)
            if size-last >= 20*1024*1024:
                print(f"  已下载 {size//1024//1024} MB", flush=True)
                last = size
    temporary.replace(target)


def platform_asset():
    system, machine = platform.system(), platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64" if machine in ("x86_64", "amd64") else None
    if system == "Darwin" and arch:
        return f"llama-{TAG}-bin-macos-{arch}.zip"
    if system == "Linux" and arch == "x64":
        return f"llama-{TAG}-bin-ubuntu-x64.zip"
    if system == "Windows" and arch:
        return f"llama-{TAG}-bin-win-cpu-{arch}.zip"
    raise ValueError("本脚本没有适配此系统，请按官方说明手动安装 llama.cpp。")


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("需要 Python 3.11 或更新版本。安装后再运行。")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    asset = platform_asset()
    print("本步骤只下载公开 llama.cpp 程序与 Qwen 模型，不读取或上传题目资料。", flush=True)
    print("检测平台：", platform.system(), platform.machine(), flush=True)
    archive = runtime / asset
    tools = runtime / (asset.removesuffix(".zip"))
    binary_name = "llama-cli.exe" if platform.system() == "Windows" else "llama-cli"
    bins = list(tools.rglob(binary_name)) if tools.exists() else []
    if not bins:
        if not archive.exists():
            print("下载官方 llama.cpp " + TAG, flush=True)
            download("https://github.com/ggml-org/llama.cpp/releases/download/" + TAG + "/" + asset, archive)
        tools.mkdir(exist_ok=True)
        with ZipFile(archive) as z:
            # Reject paths outside the managed runtime folder.
            for info in z.infolist():
                dest = (tools / info.filename).resolve()
                if not dest.is_relative_to(tools.resolve()) or stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError("压缩包路径不安全")
            z.extractall(tools)
        bins = list(tools.rglob(binary_name))
    if len(bins) != 1:
        raise ValueError("无法唯一定位 llama-cli，请检查 runtime 文件夹")
    binary = bins[0].resolve()
    if platform.system() != "Windows":
        binary.chmod(binary.stat().st_mode | 0o111)
    print("验证程序可启动…", flush=True)
    subprocess.run([str(binary), "--version"], check=True, timeout=20, capture_output=True)
    model = runtime / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    if not model.exists():
        print("下载官方 Qwen 0.5B Q4_K_M，约 0.5 GB；请等待。", flush=True)
        download(MODEL_URL, model)
    print("核对模型 SHA256…", flush=True)
    if file_hash(model) != MODEL_SHA256:
        raise ValueError("模型校验值不符，请将 runtime 中模型文件改名留存后重新下载。")
    cfg = {"LOCAL_LLAMA_BIN": str(binary), "LOCAL_MODEL_GGUF": str(model.resolve()),
           "llama_release": TAG, "model_sha256": MODEL_SHA256,
           "platform": platform.platform(), "runtime_archive_sha256": file_hash(archive) if archive.exists() else None}
    (ROOT / "local_config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "input").mkdir(exist_ok=True)
    print("准备完成。请把原始客户文件与知识库放到 input，再运行 python3 demo.py。", flush=True)
    print("模型真实推理是否成功，以网页中第一次真实运行结果为准。", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as exc:
        print("准备未完成：" + type(exc).__name__, file=sys.stderr)
        print("请保留错误画面。检查网络、系统兼容性和 Python 版本，勿关闭 TLS 校验或绕过系统安全提示。", file=sys.stderr)
        sys.exit(1)
