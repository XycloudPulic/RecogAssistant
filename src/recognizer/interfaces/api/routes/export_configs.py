# SPDX-License-Identifier: MIT

"""Export config CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.export_config_service import ExportConfigService
from recognizer.interfaces.api.schemas.config_models import (
    ExportConfigIn,
    ExportConfigOut,
)

router = APIRouter(prefix="/export-configs", tags=["export-configs"])
export_config_service = ExportConfigService()


@router.on_event("startup")
def _startup() -> None:
    export_config_service.seed_defaults_if_needed()


@router.get("", response_model=list[ExportConfigOut])
def list_export_configs(active_only: bool = True) -> list[ExportConfigOut]:
    return export_config_service.list_configs(active_only=active_only)


@router.post("", response_model=ExportConfigOut)
def create_export_config(payload: ExportConfigIn) -> ExportConfigOut:
    return export_config_service.create_config(payload)


@router.put("/{export_id}", response_model=ExportConfigOut)
def update_export_config(export_id: int, payload: ExportConfigIn) -> ExportConfigOut:
    return export_config_service.update_config(export_id, payload)


@router.delete("/{export_id}")
def delete_export_config(export_id: int) -> dict:
    return export_config_service.delete_config(export_id)
