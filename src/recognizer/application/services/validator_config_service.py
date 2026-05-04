# SPDX-License-Identifier: MIT

"""Application service for validator config CRUD and testing."""

from __future__ import annotations

import json

from recognizer.application.errors import ConflictError, NotFoundError, ValidationError
from recognizer.infrastructure.persistence.admin_configuration.repositories.validator_repository import (
    ValidatorRepository,
)
from recognizer.interfaces.api.schemas.config_models import (
    ValidatorIn,
    ValidatorOut,
    ValidatorTestIn,
    ValidatorTestOut,
)


class ValidatorConfigService:
    def __init__(self, repository: ValidatorRepository | None = None) -> None:
        self._repository = repository or ValidatorRepository()

    def list_validators(self, *, active_only: bool) -> list[ValidatorOut]:
        out: list[ValidatorOut] = []
        for row in self._repository.list_validators(active_only=active_only):
            row["config_json"] = json.loads(row.get("config_json") or "{}")
            out.append(ValidatorOut(**row))
        return out

    def get_validator(self, validator_id: int) -> ValidatorOut:
        row = self._repository.get_validator_by_id(int(validator_id))
        if not row:
            raise NotFoundError("Validator not found")
        row["config_json"] = json.loads(row.get("config_json") or "{}")
        return ValidatorOut(**row)

    def create_validator(self, payload: ValidatorIn) -> ValidatorOut:
        try:
            vid = self._repository.create_validator(
                name=payload.name,
                validator_type=payload.validator_type,
                config_json=json.dumps(payload.config_json, ensure_ascii=False),
                is_active=payload.is_active,
            )
        except Exception as exc:
            if not self._repository.is_unique_conflict(exc):
                raise
            existing = self._repository.get_validator_id_by_name(payload.name)
            if existing is None:
                raise
            raise ConflictError("Validator name already exists")
        return self.get_validator(vid)

    def update_validator(self, validator_id: int, payload: ValidatorIn) -> ValidatorOut:
        updated = self._repository.update_validator(
            int(validator_id),
            name=payload.name,
            validator_type=payload.validator_type,
            config_json=json.dumps(payload.config_json, ensure_ascii=False),
            is_active=payload.is_active,
        )
        if updated <= 0:
            raise NotFoundError("Validator not found")
        return self.get_validator(int(validator_id))

    def delete_validator(self, validator_id: int) -> dict:
        deleted = self._repository.delete_validator(int(validator_id))
        if deleted <= 0:
            raise NotFoundError("Validator not found")
        return {"ok": True}

    def test_validator(self, payload: ValidatorTestIn) -> ValidatorTestOut:
        # Deferred import to avoid circular deps; implementation lands in v-engine.
        from recognizer.domain.validation.engine import ValidationEngine

        if payload.validator_id is None and payload.validator is None:
            raise ValidationError("validator_id or validator must be provided")
        if payload.validator_id is not None and payload.validator is not None:
            raise ValidationError("Provide only one of validator_id / validator")

        if payload.validator_id is not None:
            v = self.get_validator(int(payload.validator_id))
            validator = {
                "id": v.id,
                "validator_type": v.validator_type,
                "config": v.config_json,
                "name": v.name,
            }
        else:
            assert payload.validator is not None
            validator = {
                "id": None,
                "validator_type": payload.validator.validator_type,
                "config": payload.validator.config_json,
                "name": payload.validator.name,
            }

        engine = ValidationEngine()
        ok, message = engine.test_value(
            validator_type=validator["validator_type"],
            config=validator["config"],
            value=payload.value,
        )
        return ValidatorTestOut(ok=ok, message=message)
