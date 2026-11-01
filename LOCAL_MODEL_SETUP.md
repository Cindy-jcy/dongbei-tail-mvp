# 本地模型复现说明

验证组合：Qwen2.5-0.5B-Instruct Q4_K_M GGUF，llama.cpp b6500，Linux x86_64，4个推理线程，temperature=0，seed=42。

本地推理模型与代码辅助工具分别披露在技术说明末尾。下载模型不会向模型仓库上传客户资料。本项目不调用Hugging Face托管推理API。

## 下载官方制品

模型文件：

https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf

模型SHA256：

`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`

本次使用的Linux工具包：

https://github.com/ggml-org/llama.cpp/releases/download/b6500/llama-b6500-bin-ubuntu-x64.zip

解压后使用build/bin/llama-cli，并保留同目录动态库。工具二进制及压缩包校验值见outputs/inference_manifest.json。Windows或macOS请选择官方发布页中与本机平台对应的制品，并先验证CLI参数兼容性；本次性能记录仅对应上述Linux环境。

## 运行

将`LOCAL_LLAMA_BIN`设为llama-cli的绝对路径，将`LOCAL_MODEL_GGUF`设为GGUF文件的绝对路径。程序只读取已经存在的这两个文件，不会自动下载。

```bash
python3 workflow.py --customers '/本地路径/mock_customers(1).txt' --kb '/本地路径/knowledge_base(1).zip' --provider local --run-date 2026-11-01 --out live_local_outputs
```

需保留原始响应、elapsed_ms、model_sha256与最终文案，检查3个目标画像均为REVIEW_REQUIRED。该状态表示待人工复核，没有推送动作。

## 验证数据的解释

模型实际生成的是符合JSON Schema的句子编排决策，程序据此组装文案。事实句、引导语和风险提示受控；模型不拥有发送权限。`offline`是固定决策回放，不能当作真实模型推理。

公开权重和本地二进制未打包进提交附件，可按上述来源重新获取。模型使用条款以官方模型卡为准；本次未微调或训练该模型。
