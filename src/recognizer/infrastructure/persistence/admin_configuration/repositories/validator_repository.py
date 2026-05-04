# SPDX-License-Identifier: MIT

"""Repository for validators CRUD."""

from __future__ import annotations

import sqlite3

from recognizer.infrastructure.persistence.admin_configuration.connection import (
    get_connection,
    init_config_db,
)


class ValidatorRepository:
    def __init__(self) -> None:
        init_config_db()

    def list_validators(self, *, active_only: bool) -> list[dict]:
        conn = get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM validators WHERE is_active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM validators ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_validator_by_id(self, validator_id: int) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM validators WHERE id=?", (int(validator_id),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_validator_id_by_name(self, name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM validators WHERE name=?", (str(name),)
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def create_validator(
        self, *, name: str, validator_type: str, config_json: str, is_active: bool
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO validators(name, validator_type, config_json, is_active) VALUES(?,?,?,?)",
                (name, validator_type, config_json, 1 if is_active else 0),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def update_validator(
        self,
        validator_id: int,
        *,
        name: str,
        validator_type: str,
        config_json: str,
        is_active: bool,
    ) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE validators SET name=?, validator_type=?, config_json=?, is_active=?, updated_at=datetime('now') WHERE id=?",
                (
                    name,
                    validator_type,
                    config_json,
                    1 if is_active else 0,
                    int(validator_id),
                ),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def delete_validator(self, validator_id: int) -> int:
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM validators WHERE id=?", (int(validator_id),)
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    @staticmethod
    def is_unique_conflict(error: Exception) -> bool:
        return isinstance(error, sqlite3.IntegrityError)
