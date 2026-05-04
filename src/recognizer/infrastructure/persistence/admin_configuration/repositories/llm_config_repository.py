# SPDX-License-Identifier: MIT

"""Repository for llm_configs CRUD."""

from __future__ import annotations

import sqlite3

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class LLMConfigRepository:
    def __init__(self) -> None:
        init_config_db()

    def list_configs(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM llm_configs WHERE is_active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM llm_configs ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_config(self, payload: dict, response_schema_json: str) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO llm_configs(name, provider, base_url, model, api_key_ref, system_prompt, response_schema, is_active) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    payload["name"],
                    payload["provider"],
                    payload.get("base_url"),
                    payload["model"],
                    payload.get("api_key_ref"),
                    payload.get("system_prompt"),
                    response_schema_json,
                    1 if bool(payload.get("is_active", True)) else 0,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_id_by_name(self, name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM llm_configs WHERE name=?", (name,)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def update_config(
        self, llm_id: int, payload: dict, response_schema_json: str
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE llm_configs SET name=?, provider=?, base_url=?, model=?, api_key_ref=?, system_prompt=?, response_schema=?, is_active=?, updated_at=datetime('now') "
                "WHERE id=?",
                (
                    payload["name"],
                    payload["provider"],
                    payload.get("base_url"),
                    payload["model"],
                    payload.get("api_key_ref"),
                    payload.get("system_prompt"),
                    response_schema_json,
                    1 if bool(payload.get("is_active", True)) else 0,
                    int(llm_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def get_by_id(self, llm_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM llm_configs WHERE id=?", (int(llm_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def soft_delete(self, llm_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE llm_configs SET is_active=0, updated_at=datetime('now') WHERE id=?",
                (int(llm_id),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def hard_delete(self, llm_id: int) -> int:
        """Physically delete llm config (nodes FK ON DELETE SET NULL)."""
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM llm_configs WHERE id=?", (int(llm_id),))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    @staticmethod
    def is_unique_conflict(error: Exception) -> bool:
        return isinstance(error, sqlite3.IntegrityError)
