# RecogAssistant

**Template-driven document recognition** with OCR and optional LLM vision: **template match → field extraction → cross-engine verification → validators** → structured JSON.

[English](README.md) | [中文](README.zh-CN.md)

- **Default focus**: invoices; schema supports tickets, receipts, contracts, etc.
- **Stack**: FastAPI, Streamlit, SQLite, PaddleOCR, optional OpenAI-compatible LLM

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API](#api)
- [Project layout](#project-layout)
- [Scripts](#scripts)
- [Development](#development)
- [License](#license)

## Features

- Multi-engine pipelines (e.g. PaddleOCR + LLM) with DB-driven nodes and workflows.
- Dynamic `common_result` / per-engine `result` plus `verify_result` and `validation_result`.
- Streamlit UI for recognition, queue, history, and admin-style configuration.
- SQLite for config and runtime (templates, validators, jobs).

## Requirements

- **Python** 3.10+ (3.11 tested).
- **Python 3.12 note**: some environments may not include build tooling by default. If you see errors about `setuptools` / build backend, run: `python -m pip install -U pip setuptools wheel`.
- **Windows 10/11 + PaddleOCR**: you must install **Microsoft Visual C++ 2015–2022 Redistributable (x64)** (otherwise Paddle/PaddleOCR may fail to load native DLLs).
  - Download: [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)
  - Winget: `winget install --id Microsoft.VCRedist.2015+.x64 -e`
  - `service.bat init` will probe these DLLs and may skip Paddle warm-up when missing.
- Disk space for OCR models (downloaded on first use or during init warm-up).

## Quick start

### Windows (recommended): `service.bat`

From the repo root (first time: `init`; daily: `start` / `stop`):

```bat
service.bat init
service.bat start
service.bat stop
```

`init` creates/uses `.venv`, runs `pip install -r requirements.txt`, bootstraps the DB, checks VC++ for Paddle, and may run Paddle warm-up per `config/settings.yaml`.

Reset local DB, logs, and project runtime state (does **not** uninstall packages):

```bat
service.bat clear
```

Then run `service.bat init` again before `start`.

- **UI**: http://127.0.0.1:8501  
- **OpenAPI**: http://127.0.0.1:8000/docs  
- **Service log**: `logs/app.log`

Optional: set `PIP_INDEX` before `init` to change the pip index URL (default uses Tsinghua mirror; falls back to PyPI on failure).

### Linux / macOS: `service.sh`

```bash
chmod +x service.sh
./service.sh start
./service.sh stop
```

Use `./service.sh` with the same semantics as `service.bat` where implemented (see script header).

### Manual (venv / conda)

```bash
pip install -r requirements.txt
export PYTHONPATH=src   # Linux/macOS
set PYTHONPATH=%cd%\src # Windows CMD
python -m uvicorn recognizer.interfaces.api.app:app --host 127.0.0.1 --port 8000
python -m streamlit run src/recognizer/interfaces/web/app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

### Install as a package

`pyproject.toml` defines a console script (e.g. `invoicer`). For a **full** environment matching the app, prefer `pip install -r requirements.txt` (or `service.bat init`) so Streamlit, OCR, and other runtime deps align with what the team tests.

## Configuration

| File | Purpose |
| --- | --- |
| `config/settings.yaml` | Defaults (safe to commit). |
| `config/settings-local.yaml` | Local overrides (do not commit). |

Useful keys: `server.*`, `db.recognition_path`, `api.base_url` / `api.timeout`, `api.recognition.return_debug`, `ocr.*`, `llm.*`, `ocr.prefetch_on_init` / startup-related flags in YAML.

Workflow and template data live primarily in the SQLite DB after bootstrap.

## API

- **`POST /api/v1/recognition/parse`** — multipart image/PDF → JSON with `data.common_result`, `data.engine_results[]`, `data.verify_result`, `data.validation_result`.

## Project layout

```text
RecogAssistant/
  src/recognizer/          # Application, domain, infrastructure, API, Streamlit UI
  config/                  # settings.yaml, settings-local.yaml
  data/db/                 # SQLite + SQL scripts / upgrades
  scripts/                 # (reserved)
  service.bat / service.sh
  requirements.txt
  pyproject.toml
```

## Scripts

| Script | Role |
| --- | --- |
| `service.bat` / `service.sh` | `init` / `start` / `stop` / `clear` launcher. |
| `scripts/` | Reserved (no longer required by `service.bat`). |

## Development

- Source under `src/`; tests under `tests/` if present.
- Keywords: `OCR`, `LLM`, `document-recognition`, `invoice`, `FastAPI`, `Streamlit`, `PaddleOCR`, `SQLite`, `validators`.

## License

MIT — see [LICENSE](LICENSE).
