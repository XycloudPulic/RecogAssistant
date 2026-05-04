# SPDX-License-Identifier: MIT

"""Unified configuration manager."""

import os
from pathlib import Path
from typing import Any


class Settings:
    """Unified configuration manager (singleton pattern)."""

    _config: dict[str, Any] = {}
    _initialized: bool = False

    @classmethod
    def load(cls, config_path: str | None = None) -> None:
        """Load YAML configuration file.

        Args:
            config_path: Path to configuration file. Defaults to settings.yaml.
        """
        import yaml

        if cls._initialized:
            return

        if config_path is None:
            # Look for config in project root's config/ directory
            # __file__ is in src/recognizer/common/config/settings.py
            # Go up 4 levels: config -> common -> recognizer -> src -> project_root
            project_root = Path(__file__).parent.parent.parent.parent.parent
            base_config = project_root / "config" / "settings.yaml"
            local_config = project_root / "config" / "settings-local.yaml"

            # 1. 先加载基础配置（settings.yaml）
            if base_config.exists():
                with open(base_config, "r", encoding="utf-8") as f:
                    cls._config = yaml.safe_load(f) or {}
            else:
                raise FileNotFoundError(
                    f"Base configuration file not found: {base_config}"
                )

            # 2. 加载本地配置（覆盖基础配置；不应提交到git）
            if local_config.exists():
                with open(local_config, "r", encoding="utf-8") as f:
                    local_cfg = yaml.safe_load(f) or {}
                cls._deep_merge(cls._config, local_cfg)
                print(f"[Config] Loaded local config: {local_config.name}")
        else:
            config_path = Path(config_path)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = yaml.safe_load(f) or {}

        cls._initialized = True

    @classmethod
    def _deep_merge(cls, base: dict, override: dict) -> None:
        """Deep merge override dict into base dict (in-place).

        Args:
            base: Base configuration dict (will be modified)
            override: Override configuration dict
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                cls._deep_merge(base[key], value)
            else:
                base[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key: Configuration key with dot notation (e.g., 'server.port').
            default: Default value if key not found.

        Returns:
            Configuration value or default.

        Example:
            >>> Settings.get('server.port')
            8000
            >>> Settings.get('logging.level', 'INFO')
            'INFO'
        """
        if not cls._initialized:
            cls.load()

        # Check environment variable override first
        env_key = f"INVOICE_OCR_{key.upper().replace('.', '_')}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return cls._convert_env_value(env_val)

        # Read from configuration file
        keys = key.split(".")
        val = cls._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    @classmethod
    def _convert_env_value(cls, value: str) -> Any:
        """Convert environment variable string to appropriate type.

        Args:
            value: Environment variable value as string.

        Returns:
            Converted value (bool, int, float, None, or str).
        """
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        # Numeric
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        # Null
        if value.lower() in ("null", "none"):
            return None
        return value

    @classmethod
    def project_root(cls) -> Path:
        """Directory that contains config/, src/, data/ (repository root)."""
        return Path(__file__).resolve().parent.parent.parent.parent.parent

    @classmethod
    def resolve_optional_project_path(cls, raw: Any) -> Path | None:
        """Turn YAML path into absolute Path; None/empty stays None.

        Relative paths resolve against ``project_root`` (same rule as ``db.recognition_path``).
        """
        cls.load()
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        p = Path(s)
        if p.is_absolute():
            return p.resolve()
        return (cls.project_root() / p).resolve()

    @classmethod
    def db_recognition_path(cls) -> Path:
        """Absolute SQLite path for db.recognition_path.

        Relative paths in YAML are resolved against project_root so startup cwd
        (e.g. running from src/) does not break sqlite3.connect.
        """
        cls.load()
        raw = cls.get("db.recognition_path")
        root = cls.project_root()
        if not raw:
            return (root / "data" / "db" / "recognition.db").resolve()
        p = Path(str(raw))
        if p.is_absolute():
            return p.resolve()
        return (root / p).resolve()
