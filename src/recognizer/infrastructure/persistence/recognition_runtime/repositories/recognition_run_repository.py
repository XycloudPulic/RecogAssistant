# SPDX-License-Identifier: MIT

"""Repository for querying recognition runs from persistence DB."""

from __future__ import annotations

from sqlalchemy import func

from recognizer.infrastructure.persistence.recognition_runtime.models.recognition import (
    RecognitionRun,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    get_db_session,
)


class RecognitionRunRepository:
    def list_runs_by_ids(self, run_ids: list[int]) -> list[RecognitionRun]:
        with get_db_session() as db:
            return (
                db.query(RecognitionRun)
                .filter(RecognitionRun.id.in_([int(x) for x in run_ids]))
                .order_by(RecognitionRun.id.desc())
                .all()
            )

    def list_latest_runs_per_job(
        self, job_ids: list[int] | None = None
    ) -> list[RecognitionRun]:
        with get_db_session() as db:
            q = db.query(RecognitionRun)
            if job_ids:
                q = q.filter(RecognitionRun.job_id.in_([int(x) for x in job_ids]))
            sub = (
                db.query(
                    RecognitionRun.job_id, func.max(RecognitionRun.id).label("max_id")
                )
                .group_by(RecognitionRun.job_id)
                .subquery()
            )
            return (
                q.join(sub, RecognitionRun.id == sub.c.max_id)
                .order_by(RecognitionRun.id.desc())
                .all()
            )
