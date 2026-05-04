# SPDX-License-Identifier: MIT

"""Application service for export config use-cases."""

from __future__ import annotations

import json

from recognizer.application.errors import NotFoundError
from recognizer.infrastructure.persistence.admin_configuration.repositories.export_config_repository import (
    ExportConfigRepository,
)
from recognizer.interfaces.api.schemas.config_models import (
    ExportConfigIn,
    ExportConfigOut,
)


class ExportConfigService:
    def __init__(self, repository: ExportConfigRepository | None = None) -> None:
        self._repository = repository or ExportConfigRepository()

    def seed_defaults_if_needed(self) -> None:
        if self._repository.has_any_config():
            return
        defaults = [
            (
                "默认CSV",
                "csv",
                "common_result_{date}",
                {"delimiter": ",", "encoding": "utf-8-sig"},
            ),
            (
                "默认Excel",
                "xlsx",
                "common_result_{date}",
                {"sheet_name": "common_result"},
            ),
            (
                "默认TXT",
                "txt",
                "common_result_{date}",
                {"separator": "\t", "encoding": "utf-8"},
            ),
        ]
        for name, fmt, tpl, opts in defaults:
            self._repository.create_ignore_config(
                name, fmt, tpl, json.dumps(opts, ensure_ascii=False)
            )

    @staticmethod
    def _to_out(row: dict) -> ExportConfigOut:
        row["is_active"] = bool(row["is_active"])
        row["options_json"] = json.loads(row.get("options_json") or "{}")
        return ExportConfigOut(**row)

    def list_configs(self, *, active_only: bool) -> list[ExportConfigOut]:
        return [
            self._to_out(r)
            for r in self._repository.list_configs(active_only=active_only)
        ]

    def create_config(self, payload: ExportConfigIn) -> ExportConfigOut:
        payload_dict = payload.model_dump()
        options_json = json.dumps(payload.options_json, ensure_ascii=False)
        try:
            export_id = self._repository.create_config(payload_dict, options_json)
        except Exception as exc:
            if not self._repository.is_unique_conflict(exc):
                raise
            export_id = self._repository.get_id_by_name(payload.name)
            if export_id is None:
                raise
            self._repository.update_config(export_id, payload_dict, options_json)
        row = self._repository.get_by_id(export_id)
        if not row:
            raise NotFoundError("Export config not found")
        return self._to_out(row)

    def update_config(self, export_id: int, payload: ExportConfigIn) -> ExportConfigOut:
        updated = self._repository.update_config(
            export_id,
            payload.model_dump(),
            json.dumps(payload.options_json, ensure_ascii=False),
        )
        if updated <= 0:
            raise NotFoundError("Export config not found")
        row = self._repository.get_by_id(export_id)
        if not row:
            raise NotFoundError("Export config not found")
        return self._to_out(row)

    def delete_config(self, export_id: int) -> dict:
        deleted = self._repository.hard_delete(export_id)
        if deleted <= 0:
            raise NotFoundError("Export config not found")
        return {"ok": True}
