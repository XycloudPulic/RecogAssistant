# SPDX-License-Identifier: MIT

"""Repository for node config CRUD."""

from __future__ import annotations

import json

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class NodeConfigRepository:
    """Persistence adapter for node configuration."""

    def __init__(self) -> None:
        init_config_db()

    def get_node_id_by_name(self, node_name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM nodes WHERE node_name=?", (node_name,)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def create_node(self, payload: dict) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                """
                INSERT INTO nodes(
                  node_name, display_name, description, node_type, enabled, order_index,
                  template_id, ruleset_id, llm_config_id, config_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payload["node_name"],
                    payload.get("display_name"),
                    payload.get("description"),
                    payload["node_type"],
                    1 if bool(payload.get("enabled", True)) else 0,
                    int(payload.get("order_index", 100)),
                    payload.get("template_id"),
                    payload.get("ruleset_id"),
                    payload.get("llm_config_id"),
                    json.dumps(payload.get("config_json", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_nodes(self) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM nodes ORDER BY order_index ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_node_by_id(self, node_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM nodes WHERE id=?", (int(node_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_node(self, node_id: int, payload: dict) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                """
                UPDATE nodes SET
                  node_name=?, display_name=?, description=?, node_type=?, enabled=?, order_index=?,
                  template_id=?, ruleset_id=?, llm_config_id=?, config_json=?, updated_at=datetime('now')
                WHERE id=?
                """,
                (
                    payload["node_name"],
                    payload.get("display_name"),
                    payload.get("description"),
                    payload["node_type"],
                    1 if bool(payload.get("enabled", True)) else 0,
                    int(payload.get("order_index", 100)),
                    payload.get("template_id"),
                    payload.get("ruleset_id"),
                    payload.get("llm_config_id"),
                    json.dumps(payload.get("config_json", {}), ensure_ascii=False),
                    int(node_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def delete_node(self, node_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM nodes WHERE id=?", (int(node_id),))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()
