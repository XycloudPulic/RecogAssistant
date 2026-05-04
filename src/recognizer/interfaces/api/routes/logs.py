# SPDX-License-Identifier: MIT

"""Log viewer management routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

router = APIRouter(prefix="/logs", tags=["logs"])


def _resolve_log_path() -> Path:
    """Resolve project-root logs/app.log robustly.

    We previously mis-pointed to src/logs/app.log on Windows. This resolver walks up
    from this file and prefers the *nearest* existing logs/app.log; otherwise it
    falls back to <repo_root>/logs/app.log.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "logs" / "app.log"
        if candidate.exists():
            return candidate
    # logs.py -> routes -> api -> interfaces -> recognizer -> src -> <project_root>
    return here.parents[5] / "logs" / "app.log"


LOG_PATH = _resolve_log_path()


@router.get("/tail", response_class=PlainTextResponse)
def tail(lines: int = 200) -> str:
    if lines <= 0:
        raise HTTPException(status_code=400, detail="lines must be > 0")
    log_path = _resolve_log_path()
    if not log_path.exists():
        return ""

    with open(log_path, "rb") as f:
        data = f.read().splitlines()[-lines:]
    return b"\n".join(data).decode("utf-8", errors="replace")


@router.post("/clear")
def clear_logs() -> dict:
    log_path = _resolve_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("")
    return {"ok": True}


@router.get("/download")
def download():
    log_path = _resolve_log_path()
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="app.log not found")
    return FileResponse(str(log_path), filename="app.log", media_type="text/plain")
