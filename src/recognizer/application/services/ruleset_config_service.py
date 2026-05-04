# SPDX-License-Identifier: MIT

"""Application service for ruleset/rule-item use-cases."""

from __future__ import annotations

import json
import re

from recognizer.application.errors import NotFoundError, ValidationError
from recognizer.infrastructure.persistence.admin_configuration.repositories.ruleset_config_repository import (
    RulesetConfigRepository,
)
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


class RulesetConfigService:
    def __init__(self, repository: RulesetConfigRepository | None = None) -> None:
        self._repository = repository or RulesetConfigRepository()
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        """Create a ready-to-use default data set and extractor rules."""
        try:
            default_name = "电子发票·通用数据集合"
            rid = self._repository.get_ruleset_id_by_name(default_name)
            if rid is None:
                rid = self._repository.create_ruleset(
                    default_name, "内置示例：常用字段 + 可直接选择的提取规则", True
                )

            existing_items = self._repository.list_rule_items(int(rid))

            def _ensure_rule_item(
                item_type: str, pattern: str | None, config: dict, priority: int
            ) -> int:
                cfg_s = json.dumps(config or {}, ensure_ascii=False, sort_keys=True)
                for it in existing_items:
                    if str(it.get("item_type")) != str(item_type):
                        continue
                    if (it.get("pattern") or None) != (pattern or None):
                        continue
                    try:
                        it_cfg = it.get("config_json") or "{}"
                        it_cfg_s = (
                            json.dumps(
                                json.loads(it_cfg), ensure_ascii=False, sort_keys=True
                            )
                            if isinstance(it_cfg, str)
                            else json.dumps(
                                dict(it_cfg), ensure_ascii=False, sort_keys=True
                            )
                        )
                    except Exception:
                        it_cfg_s = "{}"
                    if it_cfg_s == cfg_s:
                        return int(it["id"])
                new_id = self._repository.create_rule_item(
                    int(rid), item_type, pattern, cfg_s, int(priority)
                )
                # update local cache to avoid duplicate inserts within same bootstrap run
                existing_items.append(
                    {
                        "id": new_id,
                        "ruleset_id": rid,
                        "item_type": item_type,
                        "pattern": pattern,
                        "config_json": cfg_s,
                        "priority": priority,
                    }
                )
                return int(new_id)

            # Regex extractors (full_text) - commonly used for invoices
            rx_invoice_no = _ensure_rule_item(
                "regex",
                r"(发票号码|INVOICE[_\s-]*NO)[:：]?\s*([A-Z0-9]{8,})",
                {"source": "full_text", "group": 2},
                100,
            )
            rx_invoice_date = _ensure_rule_item(
                "regex",
                r"(开票日期|Invoice\s*Date)[:：]?\s*([0-9]{4}[年\-/\.][0-9]{1,2}[月\-/\.][0-9]{1,2}日?)",
                {
                    "source": "full_text",
                    "group": 2,
                    "strip_spaces": True,
                    "replace_map": {"年": "-", "月": "-", "日": ""},
                },
                90,
            )
            _ = _ensure_rule_item(
                "regex",
                r"名称[:：]?\s*([^\n]{2,}?\(个人\))",
                {"source": "full_text", "group": 1},
                80,
            )
            _ = _ensure_rule_item(
                "regex",
                r"名称[:：]?\s*([^\n]{2,}?有限公司)",
                {"source": "full_text", "group": 1},
                80,
            )
            _ = _ensure_rule_item(
                "regex",
                r"(统一社会信用代码/纳税人识别号|纳税人识别号|统一社会信用代码)[:：]?\s*([0-9A-Z]{15,20})",
                {"source": "full_text", "group": 2},
                80,
            )
            sc_amount = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_amounts.py",
                    "entrypoint": "extract_amount",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                70,
            )
            sc_tax = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_amounts.py",
                    "entrypoint": "extract_tax",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                70,
            )
            sc_total = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_amounts.py",
                    "entrypoint": "extract_total_amount",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                70,
            )

            # Script extractor example (scheme B)
            sc_invoice_no = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "example_invoice_number.py",
                    "entrypoint": "extract",
                    "timeout_ms": 800,
                    "input": "full_text",
                },
                60,
            )

            sc_buyer = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_parties.py",
                    "entrypoint": "extract_buyer",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                65,
            )
            sc_seller = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_parties.py",
                    "entrypoint": "extract_seller",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                65,
            )
            sc_buyer_tax = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_parties.py",
                    "entrypoint": "extract_buyer_tax_id",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                65,
            )
            sc_seller_tax = _ensure_rule_item(
                "script",
                None,
                {
                    "script_ref": "electronic_common_parties.py",
                    "entrypoint": "extract_seller_tax_id",
                    "timeout_ms": 1200,
                    "input": "full_text",
                },
                65,
            )

            # Ensure default data fields (business fields) exist and bind extractor rules
            def _upsert_field(
                field_key: str,
                field_label: str,
                field_type: str,
                order_index: int,
                rule_item_id: int | None,
                *,
                is_active: bool = True,
            ) -> None:
                existing_id = self._repository.get_data_field_id_by_key(
                    int(rid), field_key
                )
                payload = dict(
                    field_key=field_key,
                    field_label=field_label,
                    field_type=field_type,
                    order_index=int(order_index),
                    rule_item_id=rule_item_id,
                    is_active=bool(is_active),
                )
                if existing_id is None:
                    self._repository.create_data_field(int(rid), **payload)
                else:
                    self._repository.update_data_field(
                        int(rid), int(existing_id), **payload
                    )

            _upsert_field(
                "invoice_number",
                "发票号码",
                "string",
                10,
                sc_invoice_no or rx_invoice_no,
            )
            _upsert_field("invoice_date", "开票日期", "date", 20, rx_invoice_date)
            _upsert_field("purchaser_name", "购买方名称", "string", 30, sc_buyer)
            # Buyer tax id is often empty for personal invoices; disable by default to avoid mislabeling seller tax.
            _upsert_field(
                "purchaser_tax_no",
                "购买方税号",
                "string",
                40,
                sc_buyer_tax,
                is_active=True,
            )
            _upsert_field("seller_name", "销售方名称", "string", 50, sc_seller)
            _upsert_field("seller_tax_no", "销售方税号", "string", 60, sc_seller_tax)
            _upsert_field("amount", "金额", "number", 70, sc_amount)
            _upsert_field("tax", "税额", "number", 80, sc_tax)
            _upsert_field("total_amount", "价税合计", "number", 90, sc_total)
        except Exception:
            # Best-effort bootstrap; never block API.
            return

    def list_rulesets(self, *, active_only: bool) -> list[RulesetOut]:
        return [
            RulesetOut(**r)
            for r in self._repository.list_rulesets(active_only=active_only)
        ]

    def create_ruleset(self, payload: RulesetIn) -> RulesetOut:
        try:
            rid = self._repository.create_ruleset(
                payload.name, payload.description, payload.is_active
            )
        except Exception as exc:
            if not self._repository.is_unique_conflict(exc):
                raise
            rid = self._repository.get_ruleset_id_by_name(payload.name)
            if rid is None:
                raise
            self._repository.update_ruleset(
                rid, payload.name, payload.description, payload.is_active
            )
        row = self._repository.get_ruleset_by_id(rid)
        if not row:
            raise NotFoundError("Ruleset not found")
        return RulesetOut(**row)

    def update_ruleset(self, ruleset_id: int, payload: RulesetIn) -> RulesetOut:
        updated = self._repository.update_ruleset(
            ruleset_id, payload.name, payload.description, payload.is_active
        )
        if updated <= 0:
            raise NotFoundError("Ruleset not found")
        row = self._repository.get_ruleset_by_id(ruleset_id)
        if not row:
            raise NotFoundError("Ruleset not found")
        return RulesetOut(**row)

    def delete_ruleset(self, ruleset_id: int) -> dict:
        deleted = self._repository.hard_delete_ruleset(ruleset_id)
        if deleted <= 0:
            raise NotFoundError("Ruleset not found")
        return {"ok": True}

    def list_rule_items(self, ruleset_id: int) -> list[RuleItemOut]:
        out: list[RuleItemOut] = []
        for row in self._repository.list_rule_items(ruleset_id):
            row["config_json"] = json.loads(row.get("config_json") or "{}")
            out.append(RuleItemOut(**row))
        return out

    def create_rule_item(self, ruleset_id: int, payload: RuleItemIn) -> RuleItemOut:
        item_id = self._repository.create_rule_item(
            ruleset_id,
            payload.item_type,
            payload.pattern,
            json.dumps(payload.config_json, ensure_ascii=False),
            payload.priority,
        )
        row = self._repository.get_rule_item_by_id(item_id)
        if not row:
            raise NotFoundError("Rule item not found")
        row["config_json"] = json.loads(row.get("config_json") or "{}")
        return RuleItemOut(**row)

    def update_rule_item(
        self, ruleset_id: int, item_id: int, payload: RuleItemIn
    ) -> RuleItemOut:
        updated = self._repository.update_rule_item(
            ruleset_id,
            item_id,
            payload.item_type,
            payload.pattern,
            json.dumps(payload.config_json, ensure_ascii=False),
            payload.priority,
        )
        if updated <= 0:
            raise NotFoundError("Rule item not found")
        row = self._repository.get_rule_item_by_id(item_id)
        if not row:
            raise NotFoundError("Rule item not found")
        row["config_json"] = json.loads(row.get("config_json") or "{}")
        return RuleItemOut(**row)

    def delete_rule_item(self, ruleset_id: int, item_id: int) -> dict:
        deleted = self._repository.delete_rule_item(ruleset_id, item_id)
        if deleted <= 0:
            raise NotFoundError("Rule item not found")
        return {"ok": True}

    # --------------------
    # Data fields (business field definitions)
    # --------------------
    def list_data_fields(
        self, ruleset_id: int, *, active_only: bool
    ) -> list[DataFieldOut]:
        return [
            DataFieldOut(**r)
            for r in self._repository.list_data_fields(
                ruleset_id, active_only=active_only
            )
        ]

    def create_data_field(self, ruleset_id: int, payload: DataFieldIn) -> DataFieldOut:
        field_id = self._repository.create_data_field(
            ruleset_id,
            field_key=payload.field_key,
            field_label=payload.field_label,
            field_type=payload.field_type,
            order_index=payload.order_index,
            rule_item_id=payload.rule_item_id,
            is_active=payload.is_active,
        )
        row = self._repository.get_data_field_by_id(field_id)
        if not row:
            raise NotFoundError("Data field not found")
        return DataFieldOut(**row)

    def update_data_field(
        self, ruleset_id: int, field_id: int, payload: DataFieldIn
    ) -> DataFieldOut:
        updated = self._repository.update_data_field(
            ruleset_id,
            field_id,
            field_key=payload.field_key,
            field_label=payload.field_label,
            field_type=payload.field_type,
            order_index=payload.order_index,
            rule_item_id=payload.rule_item_id,
            is_active=payload.is_active,
        )
        if updated <= 0:
            raise NotFoundError("Data field not found")
        row = self._repository.get_data_field_by_id(field_id)
        if not row:
            raise NotFoundError("Data field not found")
        return DataFieldOut(**row)

    def delete_data_field(self, ruleset_id: int, field_id: int) -> dict:
        deleted = self._repository.delete_data_field(ruleset_id, field_id)
        if deleted <= 0:
            raise NotFoundError("Data field not found")
        return {"ok": True}

    @staticmethod
    def regex_test(payload: RegexTestIn) -> RegexTestOut:
        try:
            m = re.search(payload.pattern, payload.text)
        except re.error as exc:
            raise ValidationError(f"Invalid regex: {exc}") from exc
        if not m:
            return RegexTestOut(matched=False)
        groups = [g for g in m.groups() if g is not None]
        return RegexTestOut(matched=True, groups=groups, match=m.group(0))
