# 长尾客户个性化触达 MVP

私有测验源码仓库。核心工作流 v2.0，演示包装层 v1.0。使用 ChatGPT 辅助形成方案、代码、文档和测试；辅助环境执行证据通过招聘方指定渠道另交。本仓库不包含客户原始资料、运行输出、模型或本机配置。代码内有根据题目整理的候选片段，仓库必须保持私有。

## 做什么

按资产金额圈选长尾客户，按阅读需求分三类。先按风险权限与日期筛选知识片段，再调用本机 Qwen 编排句子 ID，程序核对来源和规则后组装文案。输出停在 REVIEW_REQUIRED 等待人工复核；没有发送功能。current 模式对过期资料停止，simulation 模式标注历史模拟。

当前三例各只有一个合法事实候选，主要验证链路与约束，未证明模型优于规则模板；尚未完成公司 API 联调或线上效果实验。

## 怎么运行

Python 3.11+。把本人收到的原始资料放本机 input/mock_customers.txt 和 input/knowledge_base.zip，保持知识库 ZIP 不解压。

```bash
python3 setup_demo.py
python3 demo.py
```

浏览器打开 http://127.0.0.1:8765。真实运行需要本机 llama-cli 与 GGUF 权重；setup_demo.py 只下载官方公开制品并核对模型哈希。网页先看②客户，再到③运行，真实、离线和已有记录明确分开。详细步骤及排错见 DEMO_QUICKSTART.md。

仓库不包含历史记录，所以④历史样例、⑤失败记录及③已有记录会提示文件缺失。使用另交本地演示包可查看证据；本人放好原题输入并成功安装模型后，本仓库可以重新执行③真实模式。

## 直接命令行运行

```bash
python3 workflow.py --customers input/mock_customers.txt --kb input/knowledge_base.zip --provider local --out live_local_outputs
```

真实命令行需设置 LOCAL_LLAMA_BIN 与 LOCAL_MODEL_GGUF 环境变量；demo.py 会读取 setup_demo.py 生成的 local_config.json，workflow.py 不自动读取该配置。细节见 LOCAL_MODEL_SETUP.md。

## 测试

Mac/Linux：

```bash
CUSTOMERS_PATH="$PWD/input/mock_customers.txt" KB_PATH="$PWD/input/knowledge_base.zip" python3 -m unittest -v test_workflow test_demo
```

36 项核心测试与 10 项演示层测试；未附历史证据时，演示层中 1 项历史记录测试明确跳过。不要把跳过算作通过。测试使用原题虚构资料，不联调真实公司接口。

## 文件职责

| 文件 | 用途 |
| --- | --- |
| workflow.py | 数据、分层、检索、Prompt、本地模型、校验和停止规则 |
| demo.py 与 demo.html | 本机演示服务和七个页签 |
| setup_demo.py | 下载固定版本官方公开模型与运行程序 |
| test_workflow.py 与 test_demo.py | 核心规则与演示层检查 |
| probe_local_model.py | 较弱 Prompt 的真实失败与受控修复复现 |
| workflow_spec.json | 自定义工作流说明，不是 Dify/Coze 导出 |
| company_api.env.example | 公司接口配置名称模板，不含凭证 |

## 数据与访问

不上传 input、outputs、live_local_outputs、demo_runs、runtime、local_config.json、模型、题目附件、签名或密钥。.gitignore 已排除这些目录，但网页手动上传也要自己核对。请按招聘方认可方式授权访问私有仓库；仅有链接不代表他人已有权限。

完整 AI 使用范围、资料流向、个人复现状态与待核验平台设置在另交技术说明披露；代码仓库不能替代该声明和本人承诺书。
