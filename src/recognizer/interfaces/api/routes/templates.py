# SPDX-License-Identifier: MIT

"""Templates CRUD routes backed by config SQLite DB."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.template_config_service import (
    TemplateConfigService,
)
from recognizer.interfaces.api.schemas.config_models import (
    TemplateDetailOut,
    TemplateIn,
    TemplateOut,
)

router = APIRouter(prefix="/templates", tags=["templates"])
template_service = TemplateConfigService()


@router.on_event("startup")
def _startup() -> None:
    return None


@router.get("", response_model=list[TemplateOut])
def list_templates(active_only: bool = True) -> list[TemplateOut]:
    return template_service.list_templates(active_only=active_only)


@router.get("/{template_id}", response_model=TemplateDetailOut)
def get_template(template_id: int) -> TemplateDetailOut:
    return template_service.get_template(template_id)


@router.post("", response_model=TemplateDetailOut)
def create_template(payload: TemplateIn) -> TemplateDetailOut:
    return template_service.create_template(payload)


@router.put("/{template_id}", response_model=TemplateDetailOut)
def update_template(template_id: int, payload: TemplateIn) -> TemplateDetailOut:
    return template_service.update_template(template_id, payload)


@router.delete("/{template_id}")
def delete_template(template_id: int) -> dict:
    return template_service.delete_template(template_id)
