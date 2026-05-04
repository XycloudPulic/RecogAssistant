# SPDX-License-Identifier: MIT

"""发票模板数据库管理模块"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 统一数据库路径（default: data/db/recognition.db，相对路径相对项目根而非 cwd）
from recognizer.common.config.settings import Settings  # noqa: E402

DB_PATH = Settings.db_recognition_path()
LEGACY_PREFIX = "legacy_"


def get_db_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(cursor, name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def _row_count(cursor, name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {name}")
    row = cursor.fetchone()
    return int((row[0] if row else 0) or 0)


def _migrate_legacy_invoice_table_name(cursor) -> None:
    """Idempotent rename: legacy_invoice_templates -> legacy_templates.

    若新表已存在但为空，则先删除空新表再 RENAME，以保留旧表数据；
    若新表非空则不动（避免覆盖现有数据）。
    """
    old = f"{LEGACY_PREFIX}invoice_templates"
    new = f"{LEGACY_PREFIX}templates"
    if not _table_exists(cursor, old):
        return
    if _table_exists(cursor, new):
        if _row_count(cursor, new) > 0:
            logger.warning(
                "Both %s and %s exist; %s already has rows. Skip rename.",
                old,
                new,
                new,
            )
            return
        logger.info("Dropping empty %s before renaming %s -> %s", new, old, new)
        cursor.execute(f"DROP TABLE {new}")
    logger.info("Renaming legacy table %s -> %s", old, new)
    cursor.execute(f"ALTER TABLE {old} RENAME TO {new}")


def init_database() -> None:
    """初始化 legacy template store（已通用化命名，仍保留 legacy_ 前缀）。"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 兼容迁移：旧名 legacy_invoice_templates -> legacy_templates
    try:
        _migrate_legacy_invoice_table_name(cursor)
    except Exception:
        logger.exception("Failed to rename legacy invoice templates table")

    # 模板主表（通用命名）
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LEGACY_PREFIX}templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            engine TEXT NOT NULL,
            parser TEXT NOT NULL,
            field_count INTEGER DEFAULT 0,
            sample_image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LEGACY_PREFIX}template_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT DEFAULT 'string',
            parser_config TEXT NOT NULL,
            validation_rule TEXT,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES {LEGACY_PREFIX}templates(id) ON DELETE CASCADE
        )
    """)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LEGACY_PREFIX}template_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            rule_type TEXT NOT NULL,
            rule_value TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES {LEGACY_PREFIX}templates(id) ON DELETE CASCADE
        )
    """)

    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS {LEGACY_PREFIX}idx_template_engine_parser ON {LEGACY_PREFIX}templates(engine, parser)"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS {LEGACY_PREFIX}idx_template_rule_type ON {LEGACY_PREFIX}template_rules(rule_type, rule_value)"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS {LEGACY_PREFIX}idx_field_template ON {LEGACY_PREFIX}template_fields(template_id)"
    )

    conn.commit()
    conn.close()
    logger.info("Database initialized at: %s", DB_PATH)


@dataclass
class TemplateField:
    """模板字段定义"""

    id: Optional[int] = None
    template_id: int = 0
    field_name: str = ""
    field_label: str = ""
    field_type: str = "string"
    parser_config: Dict[str, Any] = field(default_factory=dict)
    validation_rule: Optional[str] = None
    order_index: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TemplateField":
        """从数据库行创建实例"""
        parser_config = row["parser_config"]
        if isinstance(parser_config, str):
            try:
                parser_config = json.loads(parser_config)
            except json.JSONDecodeError:
                # 尝试修复可能的单引号问题
                parser_config = parser_config.replace("'", '"')
                parser_config = json.loads(parser_config)
        return cls(
            id=row["id"],
            template_id=row["template_id"],
            field_name=row["field_name"],
            field_label=row["field_label"],
            field_type=row["field_type"],
            parser_config=parser_config if parser_config else {},
            validation_rule=row["validation_rule"],
            order_index=row["order_index"],
        )


@dataclass
class TemplateRule:
    """模板识别规则"""

    id: Optional[int] = None
    template_id: int = 0
    rule_type: str = "keyword"  # keyword/regex/position
    rule_value: str = ""
    priority: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TemplateRule":
        """从数据库行创建实例"""
        return cls(
            id=row["id"],
            template_id=row["template_id"],
            rule_type=row["rule_type"],
            rule_value=row["rule_value"],
            priority=row["priority"],
        )


@dataclass
class InvoiceTemplate:
    """发票模板"""

    id: Optional[int] = None
    name: str = ""
    engine: str = "paddleocr"
    parser: str = "regex"
    field_count: int = 0
    sample_image: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_active: bool = True
    fields: List[TemplateField] = field(default_factory=list)
    rules: List[TemplateRule] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "InvoiceTemplate":
        """从数据库行创建实例"""
        return cls(
            id=row["id"],
            name=row["name"],
            engine=row["engine"],
            parser=row["parser"],
            field_count=row["field_count"],
            sample_image=row["sample_image"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=bool(row["is_active"]),
        )


if __name__ == "__main__":
    # 初始化数据库
    init_database()
    print(f"Database initialized at: {DB_PATH}")
