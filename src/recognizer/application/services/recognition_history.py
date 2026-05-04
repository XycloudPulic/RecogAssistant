# SPDX-License-Identifier: MIT

"""Service for persisting recognition history (jobs/runs) and supporting reruns."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from recognizer.application.errors import NotFoundError
from recognizer.application.workflows.recognition_orchestrator import (
    RecognitionOrchestrator,
)
from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection as get_config_conn,
)
from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    NodeRunResult,
    RecognitionJob,
    RecognitionRun,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    get_db_session,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RECORDS_DIR = PROJECT_ROOT / "data" / "recognition"
IMAGES_DIR = RECORDS_DIR / "images"


class RecognitionHistoryService:
    def __init__(self) -> None:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self._orchestrator: RecognitionOrchestrator | None = None

    def upsert_job(
        self, *, file_bytes: bytes, original_filename: str | None, temp_path: str
    ) -> int:
        """Insert or update recognition job; returns ``job_id`` (primitive).

        Returning an ORM instance is unsafe here: ``get_db_session`` commits on
        exit, so with default ``expire_on_commit`` the returned ``RecognitionJob``
        would be detached/expired and ``job.id`` would raise DetachedInstanceError.
        """
        sha = hashlib.sha256(file_bytes).hexdigest()

        # Persist image under data/recognition/images/<sha>.ext
        ext = Path(original_filename or temp_path).suffix or ".jpg"
        persisted_path = IMAGES_DIR / f"{sha}{ext}"
        if not persisted_path.exists():
            try:
                shutil.copyfile(temp_path, persisted_path)
            except Exception:
                # fallback to bytes write
                persisted_path.write_bytes(file_bytes)

        with get_db_session() as db:
            job = (
                db.query(RecognitionJob)
                .filter(RecognitionJob.image_sha256 == sha)
                .first()
            )
            if job:
                job.original_filename = original_filename or job.original_filename
                job.image_path = str(persisted_path)
                job.updated_at = datetime.utcnow()
                db.flush()
                return int(job.id)

            job = RecognitionJob(
                original_filename=original_filename,
                image_sha256=sha,
                image_path=str(persisted_path),
                is_active=True,
            )
            db.add(job)
            db.flush()
            return int(job.id)

    def _load_node_snapshot(self) -> list[dict[str, Any]]:
        """Snapshot enabled nodes config from config DB (best-effort).

        Any failure must not block ``save_run`` — missing ``nodes`` table or
        broken config DB would otherwise roll back the whole recognition run.
        """
        try:
            conn = get_config_conn()
        except Exception:
            logger.warning(
                "Could not open config DB for node snapshot; using empty snapshot",
                exc_info=True,
            )
            return []
        try:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE enabled=1 ORDER BY order_index ASC"
            ).fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["enabled"] = bool(d["enabled"])
                try:
                    d["config_json"] = json.loads(d.get("config_json") or "{}")
                except Exception:
                    d["config_json"] = {}
                out.append(d)
            return out
        except Exception:
            logger.warning(
                "Failed to load nodes snapshot; saving run with empty snapshot",
                exc_info=True,
            )
            return []
        finally:
            conn.close()

    def save_run(
        self,
        *,
        job_id: int,
        response: dict[str, Any] | None,
        orchestrator_config: Optional[dict[str, Any]] = None,
    ) -> int:
        """Persist a run from API response (InvoiceResponse dict). Returns run_id."""
        resp = response or {}
        data = (resp.get("data") or {}) if isinstance(resp, dict) else {}
        code = resp.get("code")
        status = "success" if code == 0 else "failed"

        common_result = data.get("common_result")
        verify_result = data.get("verify_result")
        engine_results = data.get("engine_results")
        debug = data.get("debug") if isinstance(data.get("debug"), dict) else None
        template_ctx = debug.get("template_ctx") if debug else None
        nodes = debug.get("nodes") if debug else None

        node_snapshot = self._load_node_snapshot()

        with get_db_session() as db:
            run = RecognitionRun(
                job_id=int(job_id),
                status=status,
                cost_time_ms=int(data.get("cost_time") or 0),
                orchestrator_config=orchestrator_config,
                node_config_snapshot=node_snapshot,
                common_result=common_result,
                verify_result=verify_result,
                engine_results=engine_results,
                raw_response=resp,
                template_ctx=template_ctx,
            )
            db.add(run)
            db.flush()

            run_id = int(run.id)
            if isinstance(nodes, list):
                for n in nodes:
                    db.add(
                        NodeRunResult(
                            run_id=run_id,
                            node_name=n.get("node_name") or n.get("engine") or "node",
                            node_type=n.get("node_type"),
                            engine=n.get("engine"),
                            status=n.get("status") or "success",
                            cost_time_ms=int(n.get("cost_time") or 0),
                            output_json=n.get("output_json"),
                            error=n.get("error"),
                        )
                    )
            return run_id

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_db_session() as db:
            rows = (
                db.query(RecognitionJob)
                .filter(RecognitionJob.is_active == True)  # noqa: E712
                .order_by(RecognitionJob.id.desc())
                .limit(int(limit))
                .all()
            )
            out: list[dict[str, Any]] = []
            for j in rows:
                out.append(
                    {
                        "id": j.id,
                        "original_filename": j.original_filename,
                        "image_sha256": j.image_sha256,
                        "image_path": j.image_path,
                        "created_at": j.created_at.isoformat(),
                        "updated_at": j.updated_at.isoformat(),
                        "run_count": len(j.runs or []),
                    }
                )
            return out

    def list_runs(self, job_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with get_db_session() as db:
            job = (
                db.query(RecognitionJob)
                .filter(RecognitionJob.id == int(job_id))
                .first()
            )
            if not job:
                raise NotFoundError("job not found")
            runs = (
                db.query(RecognitionRun)
                .filter(RecognitionRun.job_id == int(job_id))
                .order_by(RecognitionRun.id.desc())
                .limit(int(limit))
                .all()
            )
            out: list[dict[str, Any]] = []
            for r in runs:
                out.append(
                    {
                        "id": r.id,
                        "job_id": r.job_id,
                        "status": r.status,
                        "cost_time_ms": r.cost_time_ms,
                        "created_at": r.created_at.isoformat(),
                        "template_ctx": r.template_ctx,
                        "common_result": r.common_result,
                    }
                )
            return out

    def _get_orchestrator(self) -> RecognitionOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = RecognitionOrchestrator()
        return self._orchestrator

    def rerun_job(self, job_id: int) -> dict[str, Any]:
        with get_db_session() as db:
            job = (
                db.query(RecognitionJob)
                .filter(RecognitionJob.id == int(job_id))
                .first()
            )
            if not job or not job.image_path:
                raise NotFoundError("job/image not found")
            image_path = job.image_path
        response = self._get_orchestrator().execute(image_path, debug=True)
        run_id = self.save_run(
            job_id=int(job_id),
            response=response.model_dump()
            if hasattr(response, "model_dump")
            else response.dict(),
        )
        return {"ok": True, "job_id": int(job_id), "run_id": int(run_id)}
