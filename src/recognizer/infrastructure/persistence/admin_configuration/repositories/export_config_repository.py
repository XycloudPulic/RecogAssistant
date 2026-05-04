# SPDX-License-Identifier: MIT

"""Repository for export_configs CRUD + defaults."""

from __future__ import annotations

import sqlite3

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class ExportConfigRepository:
    def __init__(self) -> None:
        init_config_db()

    def has_any_config(self) -> bool:
        conn = get_connection()
        try:
            row = conn.execute("SELECT id FROM export_configs LIMIT 1").fetchone()
            return row is not None
        finally:
            conn.close()

    def create_config(self, payload: dict, options_json: str) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO export_configs(name, format, filename_template, sort, options_json, is_active) VALUES(?,?,?,?,?,?)",
                (
                    payload["name"],
                    payload["format"],
                    payload.get("filename_template", "export_{date}"),
                    int(payload.get("sort") or 0),
                    options_json,
                    1 if bool(payload.get("is_active", True)) else 0,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def create_ignore_config(
        self, name: str, fmt: str, filename_template: str, options_json: str
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO export_configs(name, format, filename_template, sort, options_json, is_active) VALUES(?,?,?,?,?,1)",
                (name, fmt, filename_template, 0, options_json),
            )
            conn.commit()
        finally:
            conn.close()

    def list_configs(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM export_configs WHERE is_active=1 ORDER BY sort ASC, id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM export_configs ORDER BY sort ASC, id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_id_by_name(self, name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM export_configs WHERE name=?", (name,)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def get_by_id(self, export_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM export_configs WHERE id=?", (int(export_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_active_by_id(self, export_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM export_configs WHERE id=? AND is_active=1",
                (int(export_id),),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_config(self, export_id: int, payload: dict, options_json: str) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE export_configs SET name=?, format=?, filename_template=?, sort=?, options_json=?, is_active=?, updated_at=datetime('now') WHERE id=?",
                (
                    payload["name"],
                    payload["format"],
                    payload.get("filename_template", "export_{date}"),
                    int(payload.get("sort") or 0),
                    options_json,
                    1 if bool(payload.get("is_active", True)) else 0,
                    int(export_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def soft_delete(self, export_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE export_configs SET is_active=0, updated_at=datetime('now') WHERE id=?",
                (int(export_id),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def hard_delete(self, export_id: int) -> int:
        """Physically delete export config."""
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM export_configs WHERE id=?", (int(export_id),)
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    @staticmethod
    def is_unique_conflict(error: Exception) -> bool:
        return isinstance(error, sqlite3.IntegrityError)
