# SPDX-License-Identifier: MIT

"""Repository for workflow CRUD and workflow-node composition."""

from __future__ import annotations

import sqlite3

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class WorkflowConfigRepository:
    """Persistence adapter for workflow configuration."""

    def __init__(self) -> None:
        init_config_db()

    def has_any_workflow(self) -> bool:
        conn = get_connection()
        try:
            row = conn.execute("SELECT id FROM workflows LIMIT 1").fetchone()
            return row is not None
        finally:
            conn.close()

    def list_enabled_nodes(self) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, order_index, enabled FROM nodes ORDER BY order_index ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_workflow(
        self, name: str, description: str | None, is_active: bool
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO workflows(name, description, is_active, is_default) VALUES(?,?,?,?)",
                (name, description, 1 if is_active else 0, 0),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def create_workflow_node(
        self,
        workflow_id: int,
        node_id: int,
        enabled: bool,
        order_index: int,
        config_override_json: str,
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO workflow_nodes(workflow_id, node_id, enabled, order_index, config_override_json) VALUES(?,?,?,?,?)",
                (
                    int(workflow_id),
                    int(node_id),
                    1 if enabled else 0,
                    int(order_index),
                    config_override_json,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_workflows(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM workflows WHERE is_active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workflows ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_workflow_by_id(self, workflow_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM workflows WHERE id=?", (int(workflow_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_workflow_id_by_name(self, name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM workflows WHERE name=?", (name,)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def update_workflow(
        self, workflow_id: int, *, name: str, description: str | None, is_active: bool
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE workflows SET name=?, description=?, is_active=?, updated_at=datetime('now') WHERE id=?",
                (name, description, 1 if is_active else 0, int(workflow_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def get_default_workflow_id(self, *, active_only: bool = True) -> int | None:
        conn = get_connection()
        try:
            if active_only:
                row = conn.execute(
                    "SELECT id FROM workflows WHERE is_default=1 AND is_active=1 ORDER BY id DESC LIMIT 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM workflows WHERE is_default=1 ORDER BY id DESC LIMIT 1"
                ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def set_default_workflow(self, workflow_id: int) -> None:
        """Mark given workflow as default and unset others (transactional)."""
        conn = get_connection()
        try:
            conn.execute("UPDATE workflows SET is_default=0")
            conn.execute(
                "UPDATE workflows SET is_default=1, updated_at=datetime('now') WHERE id=?",
                (int(workflow_id),),
            )
            conn.commit()
        finally:
            conn.close()

    def soft_delete_workflow(self, workflow_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE workflows SET is_active=0, updated_at=datetime('now') WHERE id=?",
                (int(workflow_id),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def hard_delete_workflow(self, workflow_id: int) -> int:
        """Physically delete workflow and composition nodes (FK ON DELETE CASCADE)."""
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM workflows WHERE id=?", (int(workflow_id),))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def list_workflow_nodes(self, workflow_id: int) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM workflow_nodes WHERE workflow_id=? ORDER BY order_index ASC",
                (int(workflow_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def replace_workflow_nodes(self, workflow_id: int, rows: list[dict]) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "DELETE FROM workflow_nodes WHERE workflow_id=?", (int(workflow_id),)
            )
            for item in rows:
                conn.execute(
                    "INSERT INTO workflow_nodes(workflow_id, node_id, enabled, order_index, config_override_json) VALUES(?,?,?,?,?)",
                    (
                        int(workflow_id),
                        int(item["node_id"]),
                        1 if bool(item["enabled"]) else 0,
                        int(item["order_index"]),
                        str(item["config_override_json"]),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def is_unique_conflict(error: Exception) -> bool:
        return isinstance(error, sqlite3.IntegrityError)
