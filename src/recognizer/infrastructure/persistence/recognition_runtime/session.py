# SPDX-License-Identifier: MIT

"""SQLAlchemy 引擎与会话（持久化基础设施中的 ORM 入口）。

与 ``admin_configuration.connection``（后台配置域的 sqlite 入口）指向同一数据库文件；技术实现不同、数据子域不同。
应用与领域代码通过 ``get_db`` / ``get_db_session`` / ``init_database`` 使用本模块。
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# ==================== 数据库配置 ====================

from recognizer.common.config.settings import Settings  # noqa: E402

# Unified DB path: absolute (relative YAML paths use project root, not cwd)
DATABASE_PATH = Settings.db_recognition_path()
DATABASE_DIR = DATABASE_PATH.parent
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# SQLAlchemy配置
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite需要
    echo=False,  # 生产环境设为False，开发时可设为True查看SQL
    pool_pre_ping=True,  # 连接池健康检查
)

# 创建Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


# ==================== 数据库操作接口 ====================


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（依赖注入）

    用于FastAPI的依赖注入：
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理器）

    用于普通Python代码：
        with get_db_session() as db:
            users = db.query(User).all()

    Yields:
        Session: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # 自动提交
    except Exception:
        db.rollback()  # 异常时回滚
        raise
    finally:
        db.close()


_TABLE_EXISTS_SQL = text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n")


def _table_exists(conn, name: str) -> bool:
    """Return True if a table with the given name exists."""
    row = conn.execute(_TABLE_EXISTS_SQL, {"n": name}).fetchone()
    return row is not None


def _row_count(conn, name: str) -> int:
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0)


def _rename_legacy_invoice_tables() -> None:
    """Rename invoice-named tables to generic recognition names (idempotent).

    - 若仅旧表存在：直接 ALTER TABLE RENAME。
    - 若新旧都存在：当新表为空时，删除空新表后再 RENAME，以保留旧表数据。
    - 其他情况（新表非空）：什么都不做，避免覆盖正在使用的新数据。
    """
    renames = (("runtime_invoice_templates", "runtime_templates"),)
    with engine.begin() as conn:
        for old, new in renames:
            old_exists = _table_exists(conn, old)
            new_exists = _table_exists(conn, new)
            if not old_exists:
                continue
            if new_exists:
                if _row_count(conn, new) > 0:
                    logger.warning(
                        "Both %s and %s exist; %s already has rows. Skip rename.",
                        old,
                        new,
                        new,
                    )
                    continue
                logger.info("Dropping empty %s before renaming %s -> %s", new, old, new)
                conn.exec_driver_sql(f"DROP TABLE {new}")
            logger.info("Renaming table %s -> %s", old, new)
            conn.exec_driver_sql(f"ALTER TABLE {old} RENAME TO {new}")


def _fix_runtime_template_fk_targets() -> None:
    """Fix legacy FK targets pointing to `invoice_templates`.

    Some older DBs have `runtime_template_fields` / `runtime_template_rules` created with
    `REFERENCES invoice_templates(id)`. After invoice->recognition renames, the referenced
    table no longer exists which breaks DELETE/UPDATE operations.

    SQLite can't ALTER FK constraints; we rebuild the affected tables (best-effort).
    """

    def _needs_fix(conn, table_name: str) -> bool:
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
        if not row or not row[0]:
            return False
        return "REFERENCES invoice_templates" in str(row[0])

    with engine.begin() as conn:
        if not _table_exists(conn, "runtime_templates"):
            return

        for table_name in ("runtime_template_fields", "runtime_template_rules"):
            if not _table_exists(conn, table_name):
                continue
            if not _needs_fix(conn, table_name):
                continue

            logger.info(
                "Rebuilding %s to fix FK target -> runtime_templates", table_name
            )
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            old = f"{table_name}__old"
            conn.exec_driver_sql(f"ALTER TABLE {table_name} RENAME TO {old}")

            if table_name == "runtime_template_fields":
                conn.exec_driver_sql(
                    """
                    CREATE TABLE runtime_template_fields (
                      id INTEGER NOT NULL PRIMARY KEY,
                      template_id INTEGER NOT NULL,
                      field_name VARCHAR(50) NOT NULL,
                      field_label VARCHAR(100),
                      field_type VARCHAR(20),
                      extractor_type VARCHAR(20) NOT NULL,
                      extractor_config JSON NOT NULL,
                      required BOOLEAN,
                      validation_rule VARCHAR(200),
                      order_index INTEGER,
                      FOREIGN KEY(template_id) REFERENCES runtime_templates (id)
                    );
                    """
                )
                conn.exec_driver_sql(
                    """
                    INSERT INTO runtime_template_fields(
                      id, template_id, field_name, field_label, field_type,
                      extractor_type, extractor_config, required, validation_rule, order_index
                    )
                    SELECT
                      id, template_id, field_name, field_label, field_type,
                      extractor_type, extractor_config, required, validation_rule, order_index
                    FROM runtime_template_fields__old;
                    """
                )
            else:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE runtime_template_rules (
                      id INTEGER NOT NULL PRIMARY KEY,
                      template_id INTEGER NOT NULL,
                      rule_type VARCHAR(20) NOT NULL,
                      rule_value TEXT NOT NULL,
                      weight INTEGER,
                      FOREIGN KEY(template_id) REFERENCES runtime_templates (id)
                    );
                    """
                )
                conn.exec_driver_sql(
                    """
                    INSERT INTO runtime_template_rules(
                      id, template_id, rule_type, rule_value, weight
                    )
                    SELECT
                      id, template_id, rule_type, rule_value, weight
                    FROM runtime_template_rules__old;
                    """
                )

            conn.exec_driver_sql(f"DROP TABLE {old}")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def init_database() -> None:
    """初始化数据库（执行兼容迁移并创建缺失表）。"""
    # 1. 注册模型（确保它们进入 Base.metadata）
    from .models.recognition import (  # noqa: F401
        NodeRunResult,
        RecognitionJob,
        RecognitionRun,
        Template,
        TemplateField,
        TemplateRule,
    )

    logger.info("Initializing database at: %s", DATABASE_PATH)

    try:
        from recognizer.infrastructure.local_runtime.initial_bootstrap import (
            is_database_bundled,
        )

        if is_database_bundled():
            logger.info("Database bundle already applied; skipping legacy ORM init.")
            return
    except Exception:
        logger.exception("Bundle check failed; continuing with legacy ORM init")

    # 2. 兼容迁移：把旧的发票特化表名改成通用名（in-place rename）。
    try:
        _rename_legacy_invoice_tables()
    except Exception:
        logger.exception("Failed to rename legacy invoice tables (best-effort)")

    # 2.1 Fix legacy foreign key targets if needed.
    try:
        _fix_runtime_template_fk_targets()
    except Exception:
        logger.exception(
            "Failed to fix legacy runtime template FK targets (best-effort)"
        )

    # 3. 创建尚未存在的表。
    Base.metadata.create_all(bind=engine)

    logger.info("Database initialized successfully")


def get_database_path() -> Path:
    """获取数据库文件路径"""
    return DATABASE_PATH


# ==================== 事件监听 ====================


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """设置SQLite优化选项"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
    cursor.execute("PRAGMA journal_mode=WAL")  # WAL模式提高并发性能
    cursor.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全性
    cursor.close()
