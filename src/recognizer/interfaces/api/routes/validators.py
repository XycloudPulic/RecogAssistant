# SPDX-License-Identifier: MIT

"""Validators CRUD routes backed by config SQLite DB."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.validator_config_service import (
    ValidatorConfigService,
)
from recognizer.interfaces.api.schemas.config_models import (
    ValidatorIn,
    ValidatorOut,
    ValidatorTestIn,
    ValidatorTestOut,
)

router = APIRouter(prefix="/validators", tags=["validators"])
validator_service = ValidatorConfigService()


@router.on_event("startup")
def _startup() -> None:
    return None


@router.get("", response_model=list[ValidatorOut])
def list_validators(active_only: bool = True) -> list[ValidatorOut]:
    return validator_service.list_validators(active_only=active_only)


@router.get("/{validator_id}", response_model=ValidatorOut)
def get_validator(validator_id: int) -> ValidatorOut:
    return validator_service.get_validator(validator_id)


@router.post("", response_model=ValidatorOut)
def create_validator(payload: ValidatorIn) -> ValidatorOut:
    return validator_service.create_validator(payload)


@router.put("/{validator_id}", response_model=ValidatorOut)
def update_validator(validator_id: int, payload: ValidatorIn) -> ValidatorOut:
    return validator_service.update_validator(validator_id, payload)


@router.delete("/{validator_id}")
def delete_validator(validator_id: int) -> dict:
    return validator_service.delete_validator(validator_id)


@router.post("/test", response_model=ValidatorTestOut)
def test_validator(payload: ValidatorTestIn) -> ValidatorTestOut:
    return validator_service.test_validator(payload)
