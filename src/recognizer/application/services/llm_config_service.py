# SPDX-License-Identifier: MIT

"""Application service for llm config use-cases."""

from __future__ import annotations

import json

from recognizer.application.errors import NotFoundError
from recognizer.infrastructure.persistence.admin_configuration.repositories.llm_config_repository import (
    LLMConfigRepository,
)
from recognizer.interfaces.api.schemas.config_models import LLMConfigIn, LLMConfigOut


class LLMConfigService:
    def __init__(self, repository: LLMConfigRepository | None = None) -> None:
        self._repository = repository or LLMConfigRepository()

    @staticmethod
    def _to_out(row: dict) -> LLMConfigOut:
        row["response_schema"] = json.loads(row.get("response_schema") or "{}")
        return LLMConfigOut(**row)

    def list_configs(self, *, active_only: bool) -> list[LLMConfigOut]:
        return [
            self._to_out(r)
            for r in self._repository.list_configs(active_only=active_only)
        ]

    def create_config(self, payload: LLMConfigIn) -> LLMConfigOut:
        payload_dict = payload.model_dump()
        response_schema_json = json.dumps(payload.response_schema, ensure_ascii=False)
        try:
            llm_id = self._repository.create_config(payload_dict, response_schema_json)
        except Exception as exc:
            if not self._repository.is_unique_conflict(exc):
                raise
            llm_id = self._repository.get_id_by_name(payload.name)
            if llm_id is None:
                raise
            self._repository.update_config(llm_id, payload_dict, response_schema_json)
        row = self._repository.get_by_id(llm_id)
        if not row:
            raise NotFoundError("LLM config not found")
        return self._to_out(row)

    def update_config(self, llm_id: int, payload: LLMConfigIn) -> LLMConfigOut:
        updated = self._repository.update_config(
            llm_id,
            payload.model_dump(),
            json.dumps(payload.response_schema, ensure_ascii=False),
        )
        if updated <= 0:
            raise NotFoundError("LLM config not found")
        row = self._repository.get_by_id(llm_id)
        if not row:
            raise NotFoundError("LLM config not found")
        return self._to_out(row)

    def delete_config(self, llm_id: int) -> dict:
        deleted = self._repository.hard_delete(llm_id)
        if deleted <= 0:
            raise NotFoundError("LLM config not found")
        return {"ok": True}
