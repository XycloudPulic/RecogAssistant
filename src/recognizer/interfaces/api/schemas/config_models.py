# SPDX-License-Identifier: MIT

"""Pydantic models for config CRUD APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TemplateFieldIn(BaseModel):
    field_name: str
    field_label: str
    field_type: str = "string"
    extractor_type: str = "keyword"
    extractor_config: dict[str, Any] = Field(default_factory=dict)
    rule_item_id: Optional[int] = None
    validation_rule: Optional[str] = None
    validator_ids: list[int] = Field(default_factory=list)
    order_index: int = 0


class TemplateRuleIn(BaseModel):
    rule_type: str
    rule_value: str
    priority: int = 0


class TemplateIn(BaseModel):
    name: str
    engine: str
    parser: str
    sample_image: Optional[str] = None
    is_active: bool = True
    ruleset_id: Optional[int] = None
    fields: list[TemplateFieldIn] = Field(default_factory=list)
    rules: list[TemplateRuleIn] = Field(default_factory=list)


class TemplateOut(BaseModel):
    id: int
    name: str
    engine: str
    parser: str
    field_count: int
    sample_image: Optional[str] = None
    is_active: bool
    ruleset_id: Optional[int] = None
    created_at: str
    updated_at: str


class TemplateDetailOut(TemplateOut):
    fields: list[TemplateFieldIn] = Field(default_factory=list)
    rules: list[TemplateRuleIn] = Field(default_factory=list)


class RulesetIn(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class RulesetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class RuleItemIn(BaseModel):
    item_type: str
    pattern: Optional[str] = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class RuleItemOut(RuleItemIn):
    id: int
    ruleset_id: int
    created_at: str


class DataFieldIn(BaseModel):
    field_key: str
    field_label: str
    field_type: str = "string"
    order_index: int = 0
    rule_item_id: Optional[int] = None
    is_active: bool = True


class DataFieldOut(DataFieldIn):
    id: int
    ruleset_id: int
    created_at: str
    updated_at: str


class RegexTestIn(BaseModel):
    pattern: str
    text: str


class RegexTestOut(BaseModel):
    matched: bool
    groups: list[str] = Field(default_factory=list)
    match: Optional[str] = None


class LLMConfigIn(BaseModel):
    name: str
    provider: str
    base_url: Optional[str] = None
    model: str
    api_key_ref: Optional[str] = None
    system_prompt: Optional[str] = None
    response_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class LLMConfigOut(LLMConfigIn):
    id: int
    created_at: str
    updated_at: str


class NodeConfigIn(BaseModel):
    node_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    node_type: str  # ocr/llm
    enabled: bool = True
    order_index: int = 100
    template_id: Optional[int] = None
    ruleset_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class NodeConfigOut(NodeConfigIn):
    id: int
    created_at: str
    updated_at: str


class ExportConfigIn(BaseModel):
    name: str
    format: str  # csv/xlsx/txt/...
    filename_template: str = "export_{date}"
    sort: int = 0
    options_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ExportConfigOut(ExportConfigIn):
    id: int
    created_at: str
    updated_at: str


class WorkflowIn(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class WorkflowOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    is_default: bool = False
    created_at: str
    updated_at: str


class WorkflowNodeIn(BaseModel):
    node_id: int
    enabled: bool = True
    order_index: int = 100
    config_override_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowNodeOut(WorkflowNodeIn):
    id: int
    workflow_id: int


class ValidatorIn(BaseModel):
    name: str
    validator_type: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ValidatorOut(ValidatorIn):
    id: int
    created_at: str
    updated_at: str


class ValidatorTestIn(BaseModel):
    validator_id: Optional[int] = None
    validator: Optional[ValidatorIn] = None
    value: Any = None


class ValidatorTestOut(BaseModel):
    ok: bool
    message: Optional[str] = None
