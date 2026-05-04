# RecogAssistant — OCR + LLM Document Recognition (FastAPI + Streamlit)

[English](README.md) | [中文](README.zh-CN.md)

A **template-driven** document recognition toolkit powered by **OCR / LLM Vision**.  
Pipeline: **template matching → field extraction → cross-engine verification → field validation (validators)** to produce structured outputs.

- **Default focus**: invoice recognition
- **Also supports**: tickets, receipts, reimbursements, contracts, and other document types (dynamic schema)
- **Tech stack**: FastAPI (API) + Streamlit (UI) + SQLite (config/runtime DB) + PaddleOCR (OCR) + optional LLM

## Keywords

`OCR` `LLM` `document-recognition` `invoice-recognition` `ticket-recognition` `receipt` `template-driven` `field-extraction` `validation` `validators` `FastAPI` `Streamlit` `PaddleOCR` `SQLite`

## Use cases

- **Invoice / ticket / receipt extraction** from images and PDFs (amount, date, title, etc.)
- **Multi-template parsing** via DB-managed templates and fields
- **Reusable validation rules**: required / regex / number / date / range / enum / length
- **Multi-engine comparison** with `verify_result` to surface conflicts and consistency

## Features

- **Multi-engine recognition**: run OCR/LLM engines in parallel or sequence (e.g., PaddleOCR + LLM Vision)
- **Template matching + dynamic extraction**: both `common_result` and `engine_results[].result` are dynamic dicts
- **Cross-engine verification**: compares extracted fields and produces `verify_result`
- **Field validation (reusable validators)**: per-engine validation + total validation result
- **Streamlit UI**: visualize workflow nodes, engine outputs, verification and validation results
- **DB-driven configuration**: nodes, workflows, templates, and validators are stored in SQLite

## Quick start

### Option A: Conda (recommended for development)

1) Activate your env (example: `novel-ai`)

```bash
conda activate novel-ai
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Start backend (FastAPI / 8000)

```bash
set PYTHONPATH=%cd%\src  # Windows CMD
python -m uvicorn recognizer.interfaces.api.app:app --host 127.0.0.1 --port 8000
```

4) Start frontend (Streamlit / 8501)

```bash
set PYTHONPATH=%cd%\src  # Windows CMD
python -m streamlit run src\recognizer\interfaces\web\app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Visit:
- UI: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

### Option B: Python-only (no conda)

Use `service.bat` / `service.sh` to create `.venv`, install `requirements.txt` with Tsinghua mirror, and start/stop.

- Windows:

```bat
service.bat start
service.bat stop
```

- Linux/macOS:

```bash
chmod +x service.sh
./service.sh start
./service.sh stop
```

## Configuration (YAML)

Only two config files are used:
- `config/settings.yaml`: base defaults (commit)
- `config/settings-local.yaml`: local overrides (do not commit)

Common keys:
- **Backend**: `server.host / server.port / server.debug / server.workers`
- **DB**: `db.recognition_path`
- **UI → API**: `api.base_url / api.timeout`
- **Return debug or not (server-controlled)**: `api.recognition.return_debug`
- **OCR defaults**: `ocr.lang / ocr.use_angle_cls`
- **LLM**: `llm.provider / llm.openai.*`

## API

- `POST /api/v1/recognition/parse`: upload image/PDF and get recognition result
  - `data.common_result`: final merged dict
  - `data.engine_results[]`: per-engine dict + `validation_result`
  - `data.verify_result`: cross-engine verification
  - `data.validation_result`: total validation result

## Project layout

```text
RecogAssistant/
  src/recognizer/
  config/
  data/db/
  service.bat / service.sh
  requirements.txt
```

## Development

- Python 3.10+
- Production code under `src/` (tests optional under `tests/`)

## License

MIT. See `LICENSE`.

