# SPDX-License-Identifier: MIT

"""Application service for template config use-cases."""

from __future__ import annotations

import json

from recognizer.application.errors import NotFoundError
from recognizer.infrastructure.persistence.admin_configuration.repositories.ruleset_config_repository import (
    RulesetConfigRepository,
)
from recognizer.infrastructure.persistence.admin_configuration.repositories.template_config_repository import (
    TemplateConfigRepository,
)
from recognizer.infrastructure.persistence.recognition_runtime.repositories.runtime_template_repository import (
    TemplateRepository,
)
from recognizer.infrastructure.persistence.recognition_runtime.session import (
    init_database,
)
from recognizer.interfaces.api.schemas.config_models import (
    TemplateDetailOut,
    TemplateFieldIn,
    TemplateIn,
    TemplateOut,
    TemplateRuleIn,
)


class TemplateConfigService:
    def __init__(self, repository: TemplateConfigRepository | None = None) -> None:
        self._repository = repository or TemplateConfigRepository()
        self._runtime_repo = TemplateRepository()
        self._rules_repo = RulesetConfigRepository()

    def _runtime_code(self, template_id: int) -> str:
        """Derive runtime template code from config-db template id."""
        return f"cfg_{int(template_id)}"

    def _sync_to_runtime(self, template_id: int, payload: TemplateIn) -> None:
        """Sync config-db template to runtime template store (used by RecognitionOrchestrator)."""
        # Ensure runtime DB schema exists
        init_database()

        code = self._runtime_code(template_id)
        existing = self._runtime_repo.get_by_code(code)
        if existing:
            self._runtime_repo.delete(existing.id)

        def _expand_rule_item(
            *, ruleset_id: int, rule_item_id: int | None
        ) -> tuple[str, dict]:
            if not rule_item_id:
                return "keyword", {}
            rule = self._rules_repo.get_rule_item_by_id(int(rule_item_id))
            if not rule or int(rule.get("ruleset_id") or 0) != int(ruleset_id):
                return "keyword", {}
            item_type = str(rule.get("item_type") or "")
            pattern = rule.get("pattern")
            cfg_raw = rule.get("config_json") or "{}"
            try:
                cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else dict(cfg_raw)
            except Exception:
                cfg = {}

            if item_type == "regex":
                return "regex", {"pattern": pattern or "", **cfg}
            if item_type == "keyword":
                keywords: list[str] = []
                if pattern:
                    keywords = [str(pattern)]
                elif isinstance(cfg.get("keywords"), list):
                    keywords = [str(x) for x in cfg.get("keywords") if x is not None]
                return "keyword", {"keywords": keywords, **cfg}
            if item_type == "region":
                return "region", dict(cfg)
            if item_type == "script":
                return "script", dict(cfg)
            return "keyword", dict(cfg)

        fields: list[dict] = []
        if payload.ruleset_id:
            # Authoritative field definitions come from data_fields under this data rule.
            data_fields = self._rules_repo.list_data_fields(
                int(payload.ruleset_id), active_only=True
            )
            for df in data_fields:
                extractor_type, extractor_config = _expand_rule_item(
                    ruleset_id=int(payload.ruleset_id),
                    rule_item_id=df.get("rule_item_id"),
                )
                fields.append(
                    {
                        "field_name": df.get("field_key") or "",
                        "field_label": df.get("field_label") or "",
                        "field_type": df.get("field_type") or "string",
                        "extractor_type": extractor_type,
                        "extractor_config": extractor_config,
                        "required": False,
                        "validation_rule": None,
                        "order_index": int(df.get("order_index") or 0),
                    }
                )
        else:
            # Legacy behavior: use per-template fields.
            for f in payload.fields:
                extractor_type = f.extractor_type
                extractor_config = f.extractor_config
                fields.append(
                    {
                        "field_name": f.field_name,
                        "field_label": f.field_label,
                        "field_type": f.field_type,
                        "extractor_type": extractor_type,
                        "extractor_config": extractor_config,
                        "required": False,
                        "validation_rule": f.validation_rule,
                        "order_index": f.order_index,
                    }
                )

        rules = []
        for r in payload.rules:
            weight = int(r.priority) if r.priority and int(r.priority) > 0 else 1
            rules.append(
                {"rule_type": r.rule_type, "rule_value": r.rule_value, "weight": weight}
            )

        self._runtime_repo.create(
            {
                "name": payload.name,
                "code": code,
                "engine": payload.engine,
                "category": None,
                "priority": 100,
                "enabled": payload.is_active,
                "description": None,
                "fields": fields,
                "rules": rules,
            }
        )

    def _disable_runtime(self, template_id: int) -> None:
        """Disable runtime template by derived code."""
        init_database()
        code = self._runtime_code(template_id)
        existing = self._runtime_repo.get_by_code(code)
        if not existing:
            return
        self._runtime_repo.update(existing.id, {"enabled": False})

    def _delete_runtime(self, template_id: int) -> None:
        """Physically delete runtime template by derived code."""
        init_database()
        code = self._runtime_code(template_id)
        existing = self._runtime_repo.get_by_code(code)
        if not existing:
            return
        self._runtime_repo.delete(existing.id)

    def list_templates(self, *, active_only: bool) -> list[TemplateOut]:
        return [
            TemplateOut(**r)
            for r in self._repository.list_templates(active_only=active_only)
        ]

    def _load_fields(self, template_id: int) -> list[TemplateFieldIn]:
        out: list[TemplateFieldIn] = []
        for row in self._repository.list_fields(template_id):
            row["extractor_config"] = json.loads(row.get("extractor_config") or "{}")
            try:
                row["validator_ids"] = json.loads(row.get("validator_ids") or "[]")
            except Exception:
                row["validator_ids"] = []
            out.append(TemplateFieldIn(**row))
        return out

    def _load_rules(self, template_id: int) -> list[TemplateRuleIn]:
        return [TemplateRuleIn(**r) for r in self._repository.list_rules(template_id)]

    def get_template(self, template_id: int) -> TemplateDetailOut:
        row = self._repository.get_template_by_id(template_id)
        if not row:
            raise NotFoundError("Template not found")
        return TemplateDetailOut(
            **row,
            fields=self._load_fields(template_id),
            rules=self._load_rules(template_id),
        )

    def create_template(self, payload: TemplateIn) -> TemplateDetailOut:
        template_id = self._repository.create_template(
            name=payload.name,
            engine=payload.engine,
            parser=payload.parser,
            field_count=len(payload.fields),
            sample_image=payload.sample_image,
            is_active=payload.is_active,
            ruleset_id=payload.ruleset_id,
        )
        self._repository.replace_fields(
            template_id,
            [
                {
                    "field_name": f.field_name,
                    "field_label": f.field_label,
                    "field_type": f.field_type,
                    "extractor_type": f.extractor_type,
                    "extractor_config": json.dumps(
                        f.extractor_config, ensure_ascii=False
                    ),
                    "rule_item_id": f.rule_item_id,
                    "validation_rule": f.validation_rule,
                    "validator_ids": json.dumps(f.validator_ids, ensure_ascii=False),
                    "order_index": f.order_index,
                }
                for f in payload.fields
            ],
        )
        self._repository.replace_rules(
            template_id,
            [
                {
                    "rule_type": r.rule_type,
                    "rule_value": r.rule_value,
                    "priority": r.priority,
                }
                for r in payload.rules
            ],
        )
        self._sync_to_runtime(template_id, payload)
        return self.get_template(template_id)

    def update_template(
        self, template_id: int, payload: TemplateIn
    ) -> TemplateDetailOut:
        updated = self._repository.update_template(
            template_id,
            name=payload.name,
            engine=payload.engine,
            parser=payload.parser,
            field_count=len(payload.fields),
            sample_image=payload.sample_image,
            is_active=payload.is_active,
            ruleset_id=payload.ruleset_id,
        )
        if updated <= 0:
            raise NotFoundError("Template not found")
        self._repository.replace_fields(
            template_id,
            [
                {
                    "field_name": f.field_name,
                    "field_label": f.field_label,
                    "field_type": f.field_type,
                    "extractor_type": f.extractor_type,
                    "extractor_config": json.dumps(
                        f.extractor_config, ensure_ascii=False
                    ),
                    "rule_item_id": f.rule_item_id,
                    "validation_rule": f.validation_rule,
                    "validator_ids": json.dumps(f.validator_ids, ensure_ascii=False),
                    "order_index": f.order_index,
                }
                for f in payload.fields
            ],
        )
        self._repository.replace_rules(
            template_id,
            [
                {
                    "rule_type": r.rule_type,
                    "rule_value": r.rule_value,
                    "priority": r.priority,
                }
                for r in payload.rules
            ],
        )
        self._sync_to_runtime(template_id, payload)
        return self.get_template(template_id)

    def delete_template(self, template_id: int) -> dict:
        deleted = self._repository.hard_delete_template(template_id)
        if deleted <= 0:
            raise NotFoundError("Template not found")
        self._delete_runtime(template_id)
        return {"ok": True}
