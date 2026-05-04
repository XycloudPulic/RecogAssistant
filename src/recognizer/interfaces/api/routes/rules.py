# SPDX-License-Identifier: MIT

"""Ruleset CRUD + regex test routes."""

from __future__ import annotations

from fastapi import APIRouter

from recognizer.application.services.ruleset_config_service import RulesetConfigService
from recognizer.interfaces.api.schemas.config_models import (
    DataFieldIn,
    DataFieldOut,
    RegexTestIn,
    RegexTestOut,
    RuleItemIn,
    RuleItemOut,
    RulesetIn,
    RulesetOut,
)

router = APIRouter(prefix="/rulesets", tags=["rulesets"])
ruleset_service = RulesetConfigService()


@router.on_event("startup")
def _startup() -> None:
    return None


@router.get("", response_model=list[RulesetOut])
def list_rulesets(active_only: bool = True) -> list[RulesetOut]:
    return ruleset_service.list_rulesets(active_only=active_only)


@router.post("", response_model=RulesetOut)
def create_ruleset(payload: RulesetIn) -> RulesetOut:
    return ruleset_service.create_ruleset(payload)


@router.put("/{ruleset_id}", response_model=RulesetOut)
def update_ruleset(ruleset_id: int, payload: RulesetIn) -> RulesetOut:
    return ruleset_service.update_ruleset(ruleset_id, payload)


@router.delete("/{ruleset_id}")
def delete_ruleset(ruleset_id: int) -> dict:
    return ruleset_service.delete_ruleset(ruleset_id)


@router.get("/{ruleset_id}/items", response_model=list[RuleItemOut])
def list_rule_items(ruleset_id: int) -> list[RuleItemOut]:
    return ruleset_service.list_rule_items(ruleset_id)


@router.post("/{ruleset_id}/items", response_model=RuleItemOut)
def create_rule_item(ruleset_id: int, payload: RuleItemIn) -> RuleItemOut:
    return ruleset_service.create_rule_item(ruleset_id, payload)


@router.put("/{ruleset_id}/items/{item_id}", response_model=RuleItemOut)
def update_rule_item(ruleset_id: int, item_id: int, payload: RuleItemIn) -> RuleItemOut:
    return ruleset_service.update_rule_item(ruleset_id, item_id, payload)


@router.delete("/{ruleset_id}/items/{item_id}")
def delete_rule_item(ruleset_id: int, item_id: int) -> dict:
    return ruleset_service.delete_rule_item(ruleset_id, item_id)


@router.get("/{ruleset_id}/data-fields", response_model=list[DataFieldOut])
def list_data_fields(ruleset_id: int, active_only: bool = True) -> list[DataFieldOut]:
    return ruleset_service.list_data_fields(ruleset_id, active_only=active_only)


@router.post("/{ruleset_id}/data-fields", response_model=DataFieldOut)
def create_data_field(ruleset_id: int, payload: DataFieldIn) -> DataFieldOut:
    return ruleset_service.create_data_field(ruleset_id, payload)


@router.put("/{ruleset_id}/data-fields/{field_id}", response_model=DataFieldOut)
def update_data_field(
    ruleset_id: int, field_id: int, payload: DataFieldIn
) -> DataFieldOut:
    return ruleset_service.update_data_field(ruleset_id, field_id, payload)


@router.delete("/{ruleset_id}/data-fields/{field_id}")
def delete_data_field(ruleset_id: int, field_id: int) -> dict:
    return ruleset_service.delete_data_field(ruleset_id, field_id)


@router.post("/regex-test", response_model=RegexTestOut)
def regex_test(payload: RegexTestIn) -> RegexTestOut:
    return ruleset_service.regex_test(payload)
