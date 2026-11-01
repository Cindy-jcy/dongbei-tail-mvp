# 本机网页演示操作说明

演示页是 `demo.py` 对 `workflow.py` 的包装，核心工作流仍为 v2.0。网页不调用外部模型服务，只在 `127.0.0.1` 提供页面；真实模式调用本机 llama-cli。历史证据、本次真实响应和离线回放分别标识。

## Mac 准备步骤

1. 解压本地演示包，得到 `dongbei_mvp` 文件夹。原题资料另放本机。
2. 打开“终端”，输入 `cd `（cd 后留一个空格），把 Finder 里的 `dongbei_mvp` 文件夹拖入终端，回车。
3. 输入 `python3 --version`。需要 3.11 或更新版本；没有 Python 时从 https://www.python.org/downloads/macos/ 安装。完成后重新打开终端并进入该文件夹。
4. 输入 `python3 setup_demo.py`。它自动识别 Apple Silicon 或 Intel，下载固定 b6500 版本的 llama.cpp 与官方 Qwen 0.5B GGUF，核对模型 SHA256，写入本机 `local_config.json`。只下载公开制品，不读取客户资料。不在面试时下载。
5. 在 `dongbei_mvp` 里创建 `input` 文件夹。把原始 `mock_customers(1).txt` 复制进去，重命名为 `mock_customers.txt`；把原始 `knowledge_base(1).zip` 复制进去，重命名为 `knowledge_base.zip`，知识库保持 ZIP 不解压。Mac Finder 菜单“显示”中开启“显示所有文件扩展名”，防止重复后缀。
6. 输入 `python3 demo.py`，保持终端打开。在浏览器地址栏输入 `http://127.0.0.1:8765`。
7. 页面选“② 客户与流程”，客户选择 `CUST_0005 基金`，材料模式选择“历史模拟演示”。再点“③ 运行与结果”→“现场运行真实本地模型”。必须看到“本次收到真实模型响应”和 `REVIEW_REQUIRED`，才能认定本机复现成功。

浏览器里的 localhost 指你自己的电脑。直接双击 demo.html 无法启动模型。关闭终端会关闭服务，结束时按 Ctrl+C。

## 面试时只做这些动作

在已配置的项目目录运行 `python3 demo.py`，打开上面的本机地址。共享浏览器窗口。先看①数据与分层，再用②解释基金客户，③实际运行一次，再到④比较三例，⑤展示两个失败记录，⑥按追问看代码，⑦收尾。不要在现场安装模型。

当日时效演示：②将材料模式改为“当日时效检查”，③点击真实运行按钮。旧材料会先被过滤，结果 `HOLD_NO_FRESH_SOURCE`，没有调用模型。演示完切回“历史模拟演示”。

③的三个按钮含义不同：真实按钮尝试本机模型；离线按钮只做固定决策回放；已有记录按钮读取原来的真实测试文件，不触发新推理。④与⑤也都是历史记录展示。

## 常见问题

- `python3: command not found`：未安装或未重新打开终端。
- `can't open file demo.py`：终端不在正确文件夹，重新执行 cd 拖文件夹步骤。
- `启动失败`：检查 input 两个文件名和路径。端口占用时先在旧终端按 Ctrl+C，或 `python3 demo.py --port 8766` 后打开对应地址。
- `HOLD_PROVIDER_ERROR`：模型未配好、系统拦截、程序不兼容或超过等待时间。先运行 `python3 setup_demo.py`；不把该状态说成生成成功。Mac 如弹系统阻止提示，按系统官方设置核实开发者和来源后处理，不关闭整机安全保护。
- `HOLD_NO_FRESH_SOURCE`：当日模式对旧材料的预期停止，不是环境故障。用于讲成功输出时切回历史模拟模式。
- `REVIEW_REQUIRED`：本地检查通过、等待人工复核，不等于已获正式批准或已发送。
- 网页显示未附历史证据：代码仓库版默认不放运行记录，需使用含证据的本地演示包。
- SSL/下载中断：检查正常网络和 Python 证书安装，保留错误信息；不要关闭 TLS 校验。脚本需要访问 GitHub 和 Hugging Face 的官方制品地址。

## Windows 与其他系统

脚本支持识别 Windows x64/arm64 的 CPU 制品，但本次未在 Windows 或 Mac 实机测试。Windows 可用 Python 3.11+：`py setup_demo.py`、`py demo.py`。若提示找不到 Asia/Shanghai 时区，运行 `py -m pip install tzdata` 后重试。Mac 主讲操作已在自用手册详细拆解。

## 代码与数据的交付分开

私有 GitHub 仅上传代码、前端、测试、配置模板与运行说明。不要上传 input、outputs、live_local_outputs、demo_runs、local_config.json、runtime、原题与签名。代码内包含从题目整理的候选句，仓库必须保持私有，也应按招聘方确认的渠道授权访问。含客户示例和运行证据的本地演示包按招聘方指定渠道提交。

## 官方来源

- GitHub创建仓库：https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- GitHub上传文件：https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository

- Python Mac 下载：https://www.python.org/downloads/macos/
- llama.cpp 固定发行：https://github.com/ggml-org/llama.cpp/releases/tag/b6500
- Qwen 官方模型：https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF

本次新增演示层在辅助执行环境 Linux x86_64 实测，Mac/Windows 路径通过平台分支提供，仍须在候选人设备完成安装和真实运行。下载和版本探测成功也不等于三个画像已经推理成功。
