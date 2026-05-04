# SPDX-License-Identifier: MIT

"""Logging system configuration."""

import logging
import logging.handlers
from pathlib import Path
from typing import Any

from recognizer.common.config.settings import Settings
from recognizer.common.logging.log_filter import RequestIDFilter


def _create_console_handler(
    level: int, formatter: logging.Formatter
) -> logging.Handler:
    """Create a console handler.

    Args:
        level: Log level.
        formatter: Log formatter.

    Returns:
        Configured StreamHandler.
    """
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def _create_file_handler(
    config: dict[str, Any], formatter: logging.Formatter, project_root: Path
) -> logging.Handler:
    """Create a rotating file handler (or plain FileHandler if rotation open fails).

    Ensures the parent directory exists and creates an empty log file when missing
    so downstream open() behaves consistently on Windows.

    Args:
        config: File handler configuration.
        formatter: Log formatter.
        project_root: Project root directory for resolving relative paths.

    Returns:
        Configured RotatingFileHandler or FileHandler.
    """
    log_file = config.get("file", "logs/app.log")
    max_bytes = config.get("max_bytes", 10 * 1024 * 1024)
    backup_count = config.get("backup_count", 5)
    encoding = config.get("encoding", "utf-8")
    level_name = config.get("level", "INFO")

    log_path = Path(log_file)
    if not log_path.is_absolute():
        log_path = project_root / log_path

    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not log_path.exists():
            log_path.touch()
    except OSError:
        pass

    level_num = getattr(logging, level_name.upper(), logging.INFO)

    try:
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )
    except OSError as e:
        # E.g. Permission denied when another process holds the file without share (shell redirect).
        if getattr(e, "errno", None) != 13 and not isinstance(e, PermissionError):
            raise
        handler = logging.FileHandler(log_path, mode="a", encoding=encoding, delay=True)
        logging.getLogger(__name__).warning(
            "Using plain FileHandler for %s (rotation disabled): %s", log_path, e
        )

    handler.setLevel(level_num)
    handler.setFormatter(formatter)
    return handler


def setup_logging() -> None:
    """Initialize logging system based on configuration.

    Supports multiple handlers similar to log4j2:
        - Console handler
        - File handler (rotating)
        - Multiple handlers can be enabled simultaneously
    """
    root_logger = logging.getLogger()

    # 检查是否已经配置过我们的handler（通过检查是否有RotatingFileHandler）
    has_our_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        for h in root_logger.handlers
    )
    if has_our_handler:
        # Already initialized with our handler, skip
        return

    # Read root configuration
    level_name = Settings.get("logging.level", "INFO")
    # 更新日志格式，包含请求ID
    log_format = Settings.get(
        "logging.format",
        "%(asctime)s [%(levelname)-8s] [%(request_id)s] %(name)s - %(message)s",
    )
    handlers_config = Settings.get("logging.handlers", {})

    # 获取项目根目录，确保日志路径是绝对的
    # 当前文件路径：src/recognizer/common/logging/setup.py
    # 需要向上5层才能到达项目根目录：src -> recognizer -> common -> logging -> setup.py
    project_root = Path(__file__).parent.parent.parent.parent.parent

    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(log_format)

    # 创建请求ID过滤器
    request_id_filter = RequestIDFilter()

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Create handlers based on configuration (dict format)
    for handler_name, handler_cfg in handlers_config.items():
        handler_type = handler_cfg.get("type")
        enabled = handler_cfg.get("enabled", True)
        handler_level_name = handler_cfg.get("level", level_name)
        handler_level = getattr(logging, handler_level_name.upper(), level)

        if not enabled:
            continue

        try:
            if handler_type == "console":
                handler = _create_console_handler(handler_level, formatter)
                handler.addFilter(request_id_filter)  # 添加请求ID过滤器
                root_logger.addHandler(handler)
            elif handler_type == "file":
                # 将相对路径转换为绝对路径
                handler = _create_file_handler(handler_cfg, formatter, project_root)
                handler.addFilter(request_id_filter)  # 添加请求ID过滤器
                root_logger.addHandler(handler)
            else:
                logging.warning(f"Unknown handler type: {handler_type}")
        except Exception as e:
            logging.error(f"Failed to create handler '{handler_type}': {e}")

    # Suppress excessive logging from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
