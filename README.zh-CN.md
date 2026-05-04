# RecogAssistant

基于 **OCR / 可选 LLM 视觉** 的**模板驱动**文档识别：**模板匹配 → 字段抽取 → 多引擎一致性校验 → 字段校验（validators）** → 结构化结果。默认场景偏**发票**，schema 与流程可扩展至车票、收据、合同等。

[English](README.md) | [中文](README.zh-CN.md)

**技术栈**：FastAPI（API）+ Streamlit（UI）+ SQLite（配置与运行库）+ PaddleOCR + 可选 LLM。

## 目录

- [功能概览](#功能概览)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 概览](#api-概览)
- [目录结构](#目录结构)
- [脚本说明](#脚本说明)
- [常见问题](#常见问题)
- [开发与许可](#开发与许可)

## 功能概览

- **多引擎流水线**：如 PaddleOCR 与 LLM 组合；节点、工作流等在库中配置。
- **动态结果**：`common_result`、各引擎 `result`、`verify_result`、`validation_result`。
- **Streamlit 前端**：识别页（队列、历史、导出等）、配置类页面。
- **SQLite**：模板、校验规则、任务与运行数据等。

## 环境要求

- **Python** 3.10+（团队常用 3.11）。
- **Windows 使用 PaddleOCR**：若加载失败，请安装 [VC++ 2015–2022 x64 运行库](https://aka.ms/vs/17/release/vc_redist.x64.exe)。`service.bat init` 会探测 VC++，缺失时可能跳过 Paddle 预热并给出提示。
- **磁盘**：首次识别或 `init` 预热会拉取/缓存 OCR 模型，需预留空间。

## 快速开始

### Windows：推荐 `service.bat`

在仓库根目录执行（首次：`init`；日常使用：`start` / `stop`）：

```bat
service.bat init
service.bat start
service.bat stop
```

`init` 会创建/使用 `.venv`、安装 `requirements.txt`、初始化数据库、探测 VC++、并按 `config/settings.yaml` 决定是否做 Paddle 预热。`start` 通过 `scripts/service_spawn.ps1` 拉起后端与 Streamlit，PID 写入 `.service/`。

**仅清理本机运行态**（数据库、日志、`.service` 等，**不**卸载 pip 包）：

```bat
service.bat clear
```

之后需再执行 `service.bat init`，再 `start`。

访问地址：

- 前端：http://127.0.0.1:8501  
- API 文档：http://127.0.0.1:8000/docs  
- 服务日志：`logs/app.log`

可选环境变量：`PIP_INDEX`（`init` 时 pip 源，默认清华镜像，失败会回退 PyPI）。

### Linux / macOS：`service.sh`

```bash
chmod +x service.sh
./service.sh start
./service.sh stop
```

具体子命令以脚本内注释为准（与 Windows 脚本尽量对齐）。

### 手动：venv / Conda

```bash
pip install -r requirements.txt
export PYTHONPATH=src        # Linux/macOS
# Windows CMD: set PYTHONPATH=%cd%\src
python -m uvicorn recognizer.interfaces.api.app:app --host 127.0.0.1 --port 8000
python -m streamlit run src/recognizer/interfaces/web/app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

### 以可安装包方式使用

`pyproject.toml` 中可配置控制台入口（如 `invoicer`）。**完整运行环境与仓库一致时**，建议仍以 `pip install -r requirements.txt` 或 `service.bat init` 为准，以免缺少 Streamlit、OCR 等依赖。

## 配置说明

| 文件 | 说明 |
| --- | --- |
| `config/settings.yaml` | 默认配置，可提交版本库。 |
| `config/settings-local.yaml` | 本机覆盖，**勿提交**。 |

常用项：`server.*`、`db.recognition_path`、`api.base_url` / `api.timeout`、是否返回 debug（`api.recognition.return_debug`）、`ocr.*`、`llm.*`；`ocr.prefetch_on_init` 等控制初始化时是否预热 Paddle。

节点、工作流、模板、校验规则等**主要存放在 SQLite**，`settings.yaml` 中的 orchestrator 等多为兜底。

## API 概览

- **`POST /api/v1/recognition/parse`**：上传图片或 PDF，返回 JSON。
  - `data.common_result`：汇总结果（动态 dict）
  - `data.engine_results[]`：各引擎结果 + `validation_result`
  - `data.verify_result`：多引擎一致性对比
  - `data.validation_result`：总校验结果

## 目录结构

```text
RecogAssistant/
  src/recognizer/          # 分层代码：应用、领域、基础设施、API、Streamlit
  config/                  # settings.yaml、settings-local.yaml
  data/db/                 # SQLite、初始化与升级脚本
  scripts/                 # service_spawn.ps1、VC++ 检查等
  service.bat / service.sh
  requirements.txt
  pyproject.toml
```

## 脚本说明

| 脚本 | 作用 |
| --- | --- |
| `service.bat` / `service.sh` | `init`（环境+库+DB+可选预热）、`start`、`stop`、`clear`（清本机运行数据）。 |
| `scripts/service_spawn.ps1` | 由 `service.bat start` 调用，拉起 uvicorn / Streamlit，PID 写入 `.service/`。 |
| `scripts/check_vcredist.ps1` | 可选：检查 System32 下 VC++ 相关 DLL，辅助排查 Paddle 加载失败。 |

## 常见问题

- **Paddle / onnx 报错与 VC++**：先安装上述 VC++ 再执行 `service.bat init`，查看 `logs/app.log`。
- **识别队列卡住或切页后中断**：使用识别页的「继续识别」；必要时 `stop` 后 `start`。队列按文件内容哈希去重追加；支持「当前重识 / 全部重识」等操作（见页面按钮说明与 `help`）。
- **导出**：可按成功/失败/全部与队列范围导出；元数据中的任务 ID 为字符串（UUID）。

## 开发与许可

- 生产代码在 `src/`；测试在 `tests/`（如有）。
- 关键词：`OCR`、`LLM`、`文档识别`、`发票`、`FastAPI`、`Streamlit`、`PaddleOCR`、`SQLite`、`validators`。
- **License**：MIT，见 [LICENSE](LICENSE)。
