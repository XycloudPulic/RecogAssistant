# SPDX-License-Identifier: MIT

"""Repository for templates + template_fields + template_rules."""

from __future__ import annotations

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class TemplateConfigRepository:
    def __init__(self) -> None:
        init_config_db()

    def list_templates(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM templates WHERE is_active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM templates ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_template_by_id(self, template_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM templates WHERE id=?", (int(template_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_template(
        self,
        *,
        name: str,
        engine: str,
        parser: str,
        field_count: int,
        sample_image: str | None,
        is_active: bool,
        ruleset_id: int | None = None,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO templates(name, engine, parser, field_count, sample_image, is_active, ruleset_id) VALUES(?,?,?,?,?,?,?)",
                (
                    name,
                    engine,
                    parser,
                    int(field_count),
                    sample_image,
                    1 if is_active else 0,
                    ruleset_id,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def update_template(
        self,
        template_id: int,
        *,
        name: str,
        engine: str,
        parser: str,
        field_count: int,
        sample_image: str | None,
        is_active: bool,
        ruleset_id: int | None = None,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE templates SET name=?, engine=?, parser=?, field_count=?, sample_image=?, is_active=?, ruleset_id=?, updated_at=datetime('now') WHERE id=?",
                (
                    name,
                    engine,
                    parser,
                    int(field_count),
                    sample_image,
                    1 if is_active else 0,
                    ruleset_id,
                    int(template_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def replace_fields(self, template_id: int, fields: list[dict]) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "DELETE FROM template_fields WHERE template_id=?", (int(template_id),)
            )
            for f in fields:
                conn.execute(
                    "INSERT INTO template_fields(template_id, field_name, field_label, field_type, extractor_type, extractor_config, "
                    "rule_item_id, validation_rule, validator_ids, order_index) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        int(template_id),
                        f["field_name"],
                        f["field_label"],
                        f.get("field_type", "string"),
                        f.get("extractor_type", "keyword"),
                        f["extractor_config"],
                        f.get("rule_item_id"),
                        f.get("validation_rule"),
                        f.get("validator_ids", "[]"),
                        int(f.get("order_index", 0)),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def replace_rules(self, template_id: int, rules: list[dict]) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "DELETE FROM template_rules WHERE template_id=?", (int(template_id),)
            )
            for r in rules:
                conn.execute(
                    "INSERT INTO template_rules(template_id, rule_type, rule_value, priority) VALUES(?,?,?,?)",
                    (
                        int(template_id),
                        r["rule_type"],
                        r["rule_value"],
                        int(r.get("priority", 0)),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_fields(self, template_id: int) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT field_name, field_label, field_type, extractor_type, extractor_config, rule_item_id, validation_rule, validator_ids, order_index "
                "FROM template_fields WHERE template_id=? ORDER BY order_index",
                (int(template_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_rules(self, template_id: int) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT rule_type, rule_value, priority FROM template_rules WHERE template_id=? ORDER BY priority DESC",
                (int(template_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def soft_delete_template(self, template_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE templates SET is_active=0, updated_at=datetime('now') WHERE id=?",
                (int(template_id),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def hard_delete_template(self, template_id: int) -> int:
        """Physically delete template and its child rows (FK ON DELETE CASCADE)."""
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM templates WHERE id=?", (int(template_id),))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()
