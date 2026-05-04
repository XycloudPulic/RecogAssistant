# SPDX-License-Identifier: MIT

"""Repository for rulesets and rule_items CRUD."""

from __future__ import annotations

import sqlite3

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class RulesetConfigRepository:
    def __init__(self) -> None:
        init_config_db()

    def list_rulesets(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM rulesets WHERE is_active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rulesets ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_ruleset(
        self, name: str, description: str | None, is_active: bool
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO rulesets(name, description, is_active) VALUES(?,?,?)",
                (name, description, 1 if is_active else 0),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_ruleset_id_by_name(self, name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM rulesets WHERE name=?", (name,)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def update_ruleset(
        self, ruleset_id: int, name: str, description: str | None, is_active: bool
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE rulesets SET name=?, description=?, is_active=?, updated_at=datetime('now') WHERE id=?",
                (name, description, 1 if is_active else 0, int(ruleset_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def get_ruleset_by_id(self, ruleset_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM rulesets WHERE id=?", (int(ruleset_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def soft_delete_ruleset(self, ruleset_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE rulesets SET is_active=0, updated_at=datetime('now') WHERE id=?",
                (int(ruleset_id),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def hard_delete_ruleset(self, ruleset_id: int) -> int:
        """Physically delete ruleset and rule_items (FK ON DELETE CASCADE)."""
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM rulesets WHERE id=?", (int(ruleset_id),))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def list_rule_items(self, ruleset_id: int) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM rule_items WHERE ruleset_id=? ORDER BY priority DESC, id DESC",
                (int(ruleset_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_rule_item(
        self,
        ruleset_id: int,
        item_type: str,
        pattern: str | None,
        config_json: str,
        priority: int,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO rule_items(ruleset_id, item_type, pattern, config_json, priority) VALUES(?,?,?,?,?)",
                (int(ruleset_id), item_type, pattern, config_json, int(priority)),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def update_rule_item(
        self,
        ruleset_id: int,
        item_id: int,
        item_type: str,
        pattern: str | None,
        config_json: str,
        priority: int,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE rule_items SET item_type=?, pattern=?, config_json=?, priority=? WHERE id=? AND ruleset_id=?",
                (
                    item_type,
                    pattern,
                    config_json,
                    int(priority),
                    int(item_id),
                    int(ruleset_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def get_rule_item_by_id(self, item_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM rule_items WHERE id=?", (int(item_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_rule_item(self, ruleset_id: int, item_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM rule_items WHERE id=? AND ruleset_id=?",
                (int(item_id), int(ruleset_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    # --------------------
    # Data fields (business field definitions)
    # --------------------
    def list_data_fields(self, ruleset_id: int, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM data_fields WHERE ruleset_id=? AND is_active=1 ORDER BY order_index, id",
                    (int(ruleset_id),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM data_fields WHERE ruleset_id=? ORDER BY order_index, id",
                    (int(ruleset_id),),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_data_field(
        self,
        ruleset_id: int,
        *,
        field_key: str,
        field_label: str,
        field_type: str,
        order_index: int,
        rule_item_id: int | None,
        is_active: bool,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO data_fields(ruleset_id, field_key, field_label, field_type, order_index, rule_item_id, is_active) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    int(ruleset_id),
                    field_key,
                    field_label,
                    field_type,
                    int(order_index),
                    rule_item_id,
                    1 if is_active else 0,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_data_field_by_id(self, field_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM data_fields WHERE id=?", (int(field_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_data_field_id_by_key(self, ruleset_id: int, field_key: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM data_fields WHERE ruleset_id=? AND field_key=?",
                (int(ruleset_id), str(field_key)),
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def update_data_field(
        self,
        ruleset_id: int,
        field_id: int,
        *,
        field_key: str,
        field_label: str,
        field_type: str,
        order_index: int,
        rule_item_id: int | None,
        is_active: bool,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE data_fields SET field_key=?, field_label=?, field_type=?, order_index=?, rule_item_id=?, is_active=?, "
                "updated_at=datetime('now') WHERE id=? AND ruleset_id=?",
                (
                    field_key,
                    field_label,
                    field_type,
                    int(order_index),
                    rule_item_id,
                    1 if is_active else 0,
                    int(field_id),
                    int(ruleset_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def delete_data_field(self, ruleset_id: int, field_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM data_fields WHERE id=? AND ruleset_id=?",
                (int(field_id), int(ruleset_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    @staticmethod
    def is_unique_conflict(error: Exception) -> bool:
        return isinstance(error, sqlite3.IntegrityError)
