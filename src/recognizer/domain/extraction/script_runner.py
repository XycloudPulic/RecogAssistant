# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScriptContext:
    """Context object passed into user extractor scripts."""

    field_name: str
    raw_data: Any
    full_text: str
    image_size: tuple[int, int] | None
    config: dict[str, Any]


def _safe_script_path(project_root: Path, script_ref: str) -> Path:
    base = (project_root / "scripts" / "extractors").resolve()
    candidate = (base / script_ref).resolve()
    if base not in candidate.parents and candidate != base:
        raise ValueError("script_ref must be under scripts/extractors/")
    if candidate.suffix.lower() != ".py":
        raise ValueError("script_ref must be a .py file")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    return candidate


def _run_in_child(
    script_path: str, entrypoint: str, ctx: ScriptContext, q: Queue
) -> None:
    try:
        spec = importlib.util.spec_from_file_location("user_extractor", script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("failed to load script module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        fn = getattr(module, entrypoint, None)
        if fn is None or not callable(fn):
            raise AttributeError(f"entrypoint '{entrypoint}' not found/callable")

        out = fn(ctx)
        q.put({"ok": True, "value": "" if out is None else str(out)})
    except Exception as e:
        q.put({"ok": False, "error": f"{type(e).__name__}: {e}"})


def run_extractor_script(
    *,
    script_ref: str,
    entrypoint: str = "extract",
    timeout_ms: int = 200,
    ctx: ScriptContext,
) -> str:
    """Run a user extractor script with a hard timeout (Windows friendly).

    Security note: This is not a full sandbox; it only restricts script path and enforces a timeout.
    """
    # script_runner.py lives at: <root>/src/recognizer/domain/extraction/script_runner.py
    # so project root is 4 levels up from this file.
    project_root = Path(__file__).resolve().parents[4]
    script_path = _safe_script_path(project_root, script_ref)

    q: Queue = Queue()
    p = Process(target=_run_in_child, args=(str(script_path), str(entrypoint), ctx, q))
    p.daemon = True
    p.start()
    p.join(max(0.01, float(timeout_ms) / 1000.0))

    if p.is_alive():
        try:
            p.terminate()
        finally:
            p.join(1)
        raise TimeoutError(f"script extractor timed out after {timeout_ms}ms")

    if q.empty():
        raise RuntimeError("script extractor returned no result")

    msg = q.get()
    if not msg.get("ok"):
        raise RuntimeError(msg.get("error") or "script extractor failed")
    return str(msg.get("value") or "")
