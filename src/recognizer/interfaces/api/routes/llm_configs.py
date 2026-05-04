# SPDX-License-Identifier: MIT

"""LLM config CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.llm_config_service import LLMConfigService
from recognizer.interfaces.api.schemas.config_models import LLMConfigIn, LLMConfigOut

router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])
llm_service = LLMConfigService()


@router.on_event("startup")
def _startup() -> None:
    # Repository init is handled by service/repository constructor.
    return None


@router.get("", response_model=list[LLMConfigOut])
def list_llm_configs(active_only: bool = True) -> list[LLMConfigOut]:
    return llm_service.list_configs(active_only=active_only)


@router.post("", response_model=LLMConfigOut)
def create_llm_config(payload: LLMConfigIn) -> LLMConfigOut:
    return llm_service.create_config(payload)


@router.put("/{llm_id}", response_model=LLMConfigOut)
def update_llm_config(llm_id: int, payload: LLMConfigIn) -> LLMConfigOut:
    return llm_service.update_config(llm_id, payload)


@router.delete("/{llm_id}")
def delete_llm_config(llm_id: int) -> dict:
    return llm_service.delete_config(llm_id)
