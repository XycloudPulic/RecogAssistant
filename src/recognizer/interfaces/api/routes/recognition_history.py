# SPDX-License-Identifier: MIT

"""Recognition history APIs (jobs / runs / rerun)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from recognizer.application.services.recognition_history import (
    RecognitionHistoryService,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    init_database,
)

router = APIRouter(prefix="/recognition", tags=["recognition-history"])

history_service = RecognitionHistoryService()


@router.get("/jobs")
def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    init_database()
    return history_service.list_jobs(limit=limit)


@router.get("/jobs/{job_id}/runs")
def list_runs(job_id: int, limit: int = 20) -> list[dict[str, Any]]:
    init_database()
    return history_service.list_runs(job_id=job_id, limit=limit)


@router.post("/jobs/{job_id}/rerun")
def rerun_job(job_id: int) -> dict[str, Any]:
    """Rerun a job with current orchestrator/node configuration and persist a new run."""
    init_database()
    return history_service.rerun_job(job_id=job_id)
