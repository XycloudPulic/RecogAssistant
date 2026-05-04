# SPDX-License-Identifier: MIT

"""Application service for export generation use-cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi.responses import Response

from recognizer.application.errors import NotFoundError, ValidationError
from recognizer.infrastructure.export.exporters import ExportSpec, default_registry
from recognizer.infrastructure.persistence.admin_configuration.repositories.export_config_repository import (
    ExportConfigRepository,
)
from recognizer.infrastructure.persistence.recognition_runtime.repositories.recognition_run_repository import (
    RecognitionRunRepository,
)


class ExportService:
    def __init__(
        self,
        export_config_repository: ExportConfigRepository | None = None,
        run_repository: RecognitionRunRepository | None = None,
    ) -> None:
        self._export_config_repository = (
            export_config_repository or ExportConfigRepository()
        )
        self._run_repository = run_repository or RecognitionRunRepository()

    @staticmethod
    def _export_key(field_name: str) -> str:
        """Identity mapping for backward compatibility.

        Historically this performed invoice-specific aliasing (e.g. purchaser_name
        -> buyer). The extraction engine now writes template field names directly
        into the result dict, so no mapping is needed.
        """
        return str(field_name or "")

    @staticmethod
    def _row_get(row: dict[str, Any], key: str) -> Any:
        """Get value from a flat common_result row.

        common_result is now a flat dict keyed by template field_name. We still
        tolerate legacy persisted rows that contain `extra_fields`, so values
        keep flowing through for older runs.
        """
        if not isinstance(row, dict):
            return None
        if key in row:
            return row.get(key)
        extra = row.get("extra_fields")
        if isinstance(extra, dict) and key in extra:
            return extra.get(key)
        return None

    @classmethod
    def resolve_headers(
        cls, template_ctx: Optional[dict[str, Any]], rows: list[dict[str, Any]]
    ) -> list[str]:
        if template_ctx and template_ctx.get("fields"):
            headers: list[str] = []
            for f in template_ctx["fields"]:
                name = f.get("field_name")
                if not name:
                    continue
                key = cls._export_key(str(name))
                if key and key not in headers:
                    headers.append(key)
            if headers:
                return headers
        keys: list[str] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            for k in r.keys():
                if k == "extra_fields":
                    continue
                if k not in keys:
                    keys.append(k)
            extra = r.get("extra_fields")
            if isinstance(extra, dict):
                for k in extra.keys():
                    if k not in keys:
                        keys.append(k)
        return keys

    @staticmethod
    def resolve_header_labels(
        template_ctx: Optional[dict[str, Any]], headers: list[str]
    ) -> list[str]:
        if not template_ctx or not template_ctx.get("fields"):
            return headers
        # Match by mapped export key first, fallback to raw field_name.
        by_export_key: dict[str, str] = {}
        for f in template_ctx["fields"]:
            raw = f.get("field_name")
            if not raw:
                continue
            label = f.get("field_label") or raw
            raw_s = str(raw)
            by_export_key[ExportService._export_key(raw_s)] = str(label)
            by_export_key[raw_s] = str(label)
        return [by_export_key.get(h, h) for h in headers]

    def _load_active_export_config(self, export_config_id: int) -> dict:
        cfg = self._export_config_repository.get_active_by_id(export_config_id)
        if not cfg:
            raise NotFoundError("export config not found")
        return cfg

    def build_export_response(
        self,
        *,
        export_config_id: int,
        rows: list[dict[str, Any]],
        template_ctx: Optional[dict[str, Any]],
        filename_overwrite: str | None,
    ) -> Response:
        cfg = self._load_active_export_config(export_config_id)
        import json

        options = json.loads(cfg.get("options_json") or "{}")
        fmt = str(cfg.get("format") or "").lower()
        today = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname_tpl = str(cfg.get("filename_template") or "export_{date}")
        filename = (filename_overwrite or fname_tpl).replace("{date}", today)

        exporter = default_registry().get(fmt)
        headers = self.resolve_headers(template_ctx, rows)
        header_labels = self.resolve_header_labels(template_ctx, headers)
        export_rows = [
            {
                label: self._row_get((r or {}), name)
                for name, label in zip(headers, header_labels)
            }
            for r in rows
        ]

        artifact = exporter.export(
            spec=ExportSpec(format=fmt, filename=filename, options=options),
            headers=header_labels,
            rows=export_rows,
        )
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"'
            },
        )

    def generate_export(self, payload: dict) -> Response:
        export_config_id = payload.get("export_config_id")
        rows = payload.get("rows") or []
        template_ctx = payload.get("template_ctx")
        filename_overwrite = payload.get("filename_overwrite")

        if not export_config_id:
            raise ValidationError("export_config_id is required")
        if not isinstance(rows, list) or not rows:
            raise ValidationError("rows must be a non-empty list")
        return self.build_export_response(
            export_config_id=int(export_config_id),
            rows=rows,
            template_ctx=template_ctx,
            filename_overwrite=filename_overwrite,
        )

    def export_from_runs(self, payload: dict) -> Response:
        export_config_id = payload.get("export_config_id")
        run_ids = payload.get("run_ids") or None
        job_ids = payload.get("job_ids") or None
        filename_overwrite = payload.get("filename_overwrite")
        if not export_config_id:
            raise ValidationError("export_config_id is required")

        if run_ids:
            runs = self._run_repository.list_runs_by_ids([int(x) for x in run_ids])
        else:
            runs = self._run_repository.list_latest_runs_per_job(
                [int(x) for x in job_ids] if job_ids else None
            )

        if not runs:
            raise ValidationError(
                "no recognition runs found (run invoice recognition at least once, or provide run_ids/job_ids)"
            )

        rows: list[dict[str, Any]] = []
        template_ctx = None
        for run in runs:
            if run.common_result:
                rows.append(run.common_result)
            if template_ctx is None and run.template_ctx:
                template_ctx = run.template_ctx

        if not rows:
            raise ValidationError(
                "no common_result to export for given selection (runs exist but common_result is empty)"
            )

        return self.build_export_response(
            export_config_id=int(export_config_id),
            rows=rows,
            template_ctx=template_ctx,
            filename_overwrite=filename_overwrite,
        )
