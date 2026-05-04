# SPDX-License-Identifier: MIT

"""首次部署：把仓库里的 SQL 打进本机 SQLite（幂等）。

包路径：``recognizer.infrastructure.local_runtime`` — 与 ORM 无关，只负责执行脚本。

- DDL: ``data/db/scripts/init_recognition_db.sql``
- 种子: ``data/db/scripts/insert_recognition_db.sql``
- 已打过初始包则跳过（表 ``_recog_db_bundle`` 为标记）。

增量迁移预留：``data/db/upgrades/``（尚未接线）。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DDL_NAME = "init_recognition_db.sql"
SEED_NAME = "insert_recognition_db.sql"


def _scripts_dir() -> Path:
    from recognizer.common.config.settings import Settings

    return Settings.project_root() / "data" / "db" / "scripts"


def _db_path() -> Path:
    from recognizer.common.config.settings import Settings

    return Settings.db_recognition_path()


def is_database_bundled() -> bool:
    """True when init bundle marker row exists."""
    db_path = _db_path()
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='_recog_db_bundle'"
        ).fetchone()
        if not row:
            return False
        row = conn.execute("SELECT 1 FROM _recog_db_bundle WHERE id=1").fetchone()
        return row is not None
    finally:
        conn.close()


def ensure_initial_database() -> bool:
    """Execute DDL (+ seed if present) once. Returns True if SQL was applied.

    Safe to call repeatedly; skips when bundle marker exists.
    """
    from recognizer.common.config.settings import Settings

    Settings.load()
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        if _bundled_conn(conn):
            return False

        scripts = _scripts_dir()
        ddl_path = scripts / DDL_NAME
        if not ddl_path.is_file():
            raise FileNotFoundError(f"Missing DDL script: {ddl_path}")

        logger.info("Applying initial DDL from %s", ddl_path)
        conn.executescript(ddl_path.read_text(encoding="utf-8"))

        seed_path = scripts / SEED_NAME
        if seed_path.is_file():
            logger.info("Applying seed from %s", seed_path)
            conn.executescript(seed_path.read_text(encoding="utf-8"))
        else:
            logger.warning("No seed file at %s; marking bundle DDL-only", seed_path)
            conn.execute(
                "INSERT OR REPLACE INTO _recog_db_bundle (id, bundle_version) VALUES (1, '1')"
            )

        conn.commit()
        logger.info("Initial database bundle applied at %s", db_path)
        return True
    finally:
        conn.close()


def _bundled_conn(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='_recog_db_bundle'"
    ).fetchone()
    if not row:
        return False
    row = conn.execute("SELECT 1 FROM _recog_db_bundle WHERE id=1").fetchone()
    return row is not None


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    applied = ensure_initial_database()
    print("applied=" + str(applied))


if __name__ == "__main__":
    main()
