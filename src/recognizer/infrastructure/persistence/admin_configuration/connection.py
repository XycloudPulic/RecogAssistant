# SPDX-License-Identifier: MIT

"""持久化基础设施中的 sqlite3 入口：连接、轻量迁移、与 bootstrap 衔接。

与 ``recognition_runtime.session`` 的 SQLAlchemy 指向同一 ``Settings.db_recognition_path()``；
此处面向配置类表的仓储与 CRUD，ORM Session 与 ``sqlite3.Connection`` 各司其职。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def _config_db_path() -> Path:
    from recognizer.common.config.settings import Settings

    return Settings.db_recognition_path()


def get_connection() -> sqlite3.Connection:
    db_path = _config_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_config_db() -> None:
    """Ensure DB exists: apply bundled DDL/DML from data/db/scripts when needed."""
    from recognizer.infrastructure.local_runtime.initial_bootstrap import (
        ensure_initial_database,
    )

    ensure_initial_database()


def _ensure_expected_tables(conn: sqlite3.Connection) -> None:
    """Best-effort repair for missing tables.

    If a DB was migrated by copying only some tables but also copied the
    `schema_migrations` rows, the migration runner may skip creating newer
    tables. This helper ensures critical tables exist without re-running
    non-idempotent ALTER migrations.
    """

    def has_table(name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    if not has_table("export_configs"):
        conn.executescript(_migration_v2())

    if not has_table("data_fields"):
        # Create latest `data_fields` schema including `rule_item_id`.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS data_fields (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ruleset_id INTEGER NOT NULL,
              field_key TEXT NOT NULL,
              field_label TEXT NOT NULL,
              field_type TEXT NOT NULL DEFAULT 'string',
              order_index INTEGER NOT NULL DEFAULT 0,
              rule_item_id INTEGER,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE CASCADE
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_data_fields_ruleset_key ON data_fields(ruleset_id, field_key);
            CREATE INDEX IF NOT EXISTS idx_data_fields_ruleset ON data_fields(ruleset_id, order_index);
            CREATE INDEX IF NOT EXISTS idx_data_fields_rule_item ON data_fields(rule_item_id);
            """
        )

    if not has_table("validators"):
        # Ensure latest validators schema exists even if migrations were partially copied.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS validators (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              validator_type TEXT NOT NULL,
              config_json TEXT NOT NULL DEFAULT '{}',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_validators_type ON validators(validator_type);
            CREATE INDEX IF NOT EXISTS idx_validators_active ON validators(is_active);
            """
        )

    # Best-effort: add missing `template_fields.validator_ids` without re-running full migrations.
    if has_table("template_fields"):
        cols = conn.execute("PRAGMA table_info(template_fields)").fetchall()
        col_names = {str(c["name"]) for c in cols}
        if "validator_ids" not in col_names:
            conn.executescript(
                "ALTER TABLE template_fields ADD COLUMN validator_ids TEXT NOT NULL DEFAULT '[]';"
            )


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r["version"]) for r in rows}


def _apply_migrations(conn: sqlite3.Connection) -> None:
    applied = _applied_versions(conn)

    migrations: list[tuple[int, str]] = [
        (1, _migration_v1()),
        (2, _migration_v2()),
        (3, _migration_v3()),
        (4, _migration_v4()),
        (5, _migration_v5()),
        (6, _migration_v6()),
        (7, _migration_v7()),
        (8, _migration_v8()),
        (9, _migration_v9()),
        (10, _migration_v10()),
    ]

    for version, sql in migrations:
        if version in applied:
            continue
        logger.info("Applying config DB migration v%s", version)
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))


def _migration_v1() -> str:
    # Note: keep this idempotent (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS)
    return """
    -- =========================
    -- Templates
    -- =========================
    CREATE TABLE IF NOT EXISTS templates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      engine TEXT NOT NULL,
      parser TEXT NOT NULL,
      field_count INTEGER NOT NULL DEFAULT 0,
      sample_image TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS template_fields (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      template_id INTEGER NOT NULL,
      field_name TEXT NOT NULL,
      field_label TEXT NOT NULL,
      field_type TEXT NOT NULL DEFAULT 'string',
      extractor_type TEXT NOT NULL DEFAULT 'keyword',
      extractor_config TEXT NOT NULL DEFAULT '{}',
      validation_rule TEXT,
      order_index INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS template_rules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      template_id INTEGER NOT NULL,
      rule_type TEXT NOT NULL,
      rule_value TEXT NOT NULL,
      priority INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_templates_engine_parser ON templates(engine, parser);
    CREATE INDEX IF NOT EXISTS idx_template_fields_template ON template_fields(template_id);
    CREATE INDEX IF NOT EXISTS idx_template_rules_template ON template_rules(template_id);

    -- =========================
    -- Rule sets (general-purpose)
    -- =========================
    CREATE TABLE IF NOT EXISTS rulesets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS rule_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ruleset_id INTEGER NOT NULL,
      item_type TEXT NOT NULL,          -- regex/keyword/key_value/region/...
      pattern TEXT,                     -- for regex, etc.
      config_json TEXT NOT NULL DEFAULT '{}',
      priority INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_rule_items_ruleset ON rule_items(ruleset_id);

    -- =========================
    -- LLM configs
    -- =========================
    CREATE TABLE IF NOT EXISTS llm_configs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      provider TEXT NOT NULL,           -- openai/ollama/...
      base_url TEXT,
      model TEXT NOT NULL,
      api_key_ref TEXT,                 -- reference/env var name; avoid storing raw secret
      system_prompt TEXT,
      response_schema TEXT NOT NULL DEFAULT '{}',  -- JSON schema / template
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- =========================
    -- Node configs
    -- =========================
    CREATE TABLE IF NOT EXISTS nodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      node_name TEXT NOT NULL UNIQUE,
      display_name TEXT,
      description TEXT,
      node_type TEXT NOT NULL,          -- ocr/llm
      enabled INTEGER NOT NULL DEFAULT 1,
      order_index INTEGER NOT NULL DEFAULT 100,
      template_id INTEGER,              -- optional for OCR
      ruleset_id INTEGER,               -- optional for OCR
      llm_config_id INTEGER,            -- required for LLM nodes (enforced at API level)
      config_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL,
      FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE SET NULL,
      FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_nodes_order ON nodes(order_index);
    """


def _migration_v2() -> str:
    return """
    -- =========================
    -- Export configs
    -- =========================
    CREATE TABLE IF NOT EXISTS export_configs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      format TEXT NOT NULL,              -- csv/xlsx/txt/...
      filename_template TEXT NOT NULL DEFAULT 'export_{date}',
      options_json TEXT NOT NULL DEFAULT '{}',
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def _migration_v3() -> str:
    return """
    -- =========================
    -- Workflows (node composition / scheduling)
    -- =========================
    CREATE TABLE IF NOT EXISTS workflows (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS workflow_nodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      workflow_id INTEGER NOT NULL,
      node_id INTEGER NOT NULL,
      enabled INTEGER NOT NULL DEFAULT 1,
      order_index INTEGER NOT NULL DEFAULT 100,
      config_override_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
      FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow ON workflow_nodes(workflow_id);
    CREATE INDEX IF NOT EXISTS idx_workflow_nodes_order ON workflow_nodes(workflow_id, order_index);
    """


def _migration_v4() -> str:
    return """
    -- =========================
    -- Templates -> Ruleset linkage
    -- =========================
    -- Note: SQLite cannot add/alter FK constraints easily after table creation.
    -- We add a nullable column and keep logic at application layer.
    ALTER TABLE templates ADD COLUMN ruleset_id INTEGER;
    CREATE INDEX IF NOT EXISTS idx_templates_ruleset ON templates(ruleset_id);
    """


def _migration_v5() -> str:
    return """
    -- =========================
    -- Template fields -> Rule item reference (optional)
    -- =========================
    ALTER TABLE template_fields ADD COLUMN rule_item_id INTEGER;
    CREATE INDEX IF NOT EXISTS idx_template_fields_rule_item ON template_fields(rule_item_id);
    """


def _migration_v6() -> str:
    return """
    -- =========================
    -- Data fields (business field definitions) under a ruleset ("data rule")
    -- =========================
    CREATE TABLE IF NOT EXISTS data_fields (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ruleset_id INTEGER NOT NULL,
      field_key TEXT NOT NULL,            -- stable key, e.g. invoice_number
      field_label TEXT NOT NULL,          -- display label, e.g. 发票号码
      field_type TEXT NOT NULL DEFAULT 'string',
      order_index INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (ruleset_id) REFERENCES rulesets(id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_data_fields_ruleset_key ON data_fields(ruleset_id, field_key);
    CREATE INDEX IF NOT EXISTS idx_data_fields_ruleset ON data_fields(ruleset_id, order_index);
    """


def _migration_v7() -> str:
    return """
    -- =========================
    -- Data fields -> rule item (extractor) reference
    -- =========================
    ALTER TABLE data_fields ADD COLUMN rule_item_id INTEGER;
    CREATE INDEX IF NOT EXISTS idx_data_fields_rule_item ON data_fields(rule_item_id);
    """


def _migration_v8() -> str:
    return """
    -- =========================
    -- Workflows: default workflow flag
    -- =========================
    ALTER TABLE workflows ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX IF NOT EXISTS idx_workflows_default ON workflows(is_default);
    """


def _migration_v9() -> str:
    return """
    -- =========================
    -- Export configs: sort order for default selection
    -- =========================
    ALTER TABLE export_configs ADD COLUMN sort INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX IF NOT EXISTS idx_export_configs_sort ON export_configs(sort);
    """


def _migration_v10() -> str:
    return """
    -- =========================
    -- Validators: reusable field legitimacy checks
    -- =========================
    CREATE TABLE IF NOT EXISTS validators (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      validator_type TEXT NOT NULL,         -- required/regex/amount/number/date/...
      config_json TEXT NOT NULL DEFAULT '{}',
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_validators_type ON validators(validator_type);
    CREATE INDEX IF NOT EXISTS idx_validators_active ON validators(is_active);

    -- template_fields: attach validators (stored as JSON array string)
    ALTER TABLE template_fields ADD COLUMN validator_ids TEXT NOT NULL DEFAULT '[]';
    """
