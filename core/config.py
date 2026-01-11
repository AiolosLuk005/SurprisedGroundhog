# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib  # py3.11+
except ImportError:
    import tomli as tomllib

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]

class AppConfig:
    """Unified configuration loader."""
    
    def __init__(self):
        self._toml_config = self._load_toml()
        self._json_settings = self._load_json_settings()
        self._env_config = os.environ

    def _load_toml(self) -> Dict[str, Any]:
        cfg_path = ROOT_DIR / "config.toml"
        if not cfg_path.exists():
            cfg_path = ROOT_DIR / "config_example.toml"
        try:
            with open(cfg_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.toml: {e}")
            return {}

    def _load_json_settings(self) -> Dict[str, Any]:
        """Load dynamic settings from config/settings.json."""
        msg_file = ROOT_DIR / "config" / "settings.json"
        if msg_file.exists():
            try:
                with open(msg_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load settings.json: {e}")
        return {}

    @property
    def PORT(self) -> int:
        return int(self._toml_config.get("port", 5005))

    @property
    def ALLOWED_ROOTS(self) -> list[str]:
        return [str(Path(r).resolve()) for r in self._toml_config.get("allowed_roots", [])]

    @property
    def LOG_CONFIG(self) -> dict:
        return self._toml_config.get("logging", {})

    @property
    def MYSQL_CONFIG(self) -> dict:
        # Merge TOML config with potential env overrides or secure settings
        base = self._toml_config.get("mysql", {})
        return {
            "enable": bool(base.get("enable", False)),
            "host": base.get("host", "127.0.0.1"),
            "port": int(base.get("port", 3306)),
            "user": base.get("user", "root"),
            "password": base.get("password", ""),
            "database": base.get("database", "groundhog"),
        }

    @property
    def AI_CONFIG(self) -> dict:
        # Priority: settings.json > config.toml
        toml_ai = self._toml_config.get("ollama", {}) # legacy name in toml might be just ollama
        json_ai = self._json_settings.get("ai", {})
        
        # Merge, preferring JSON settings (dynamic)
        merged = toml_ai.copy()
        merged.update(json_ai)
        
        # Ensure 'enable' key exists and normalize provider
        if "enable" not in merged:
            merged["enable"] = toml_ai.get("enable", False)
            
        return merged

    @property
    def FEATURE_FLAGS(self) -> dict:
        return self._json_settings.get("features", {})
    
    @property
    def TRASH_DIR(self) -> str:
        return self._toml_config.get("trash_dir", "")

    # Helpers for global access
    def get(self, key: str, default: Any = None) -> Any:
        return self._toml_config.get(key, default)

# Global Instance
CFG = AppConfig()

# Expose legacy constants for compatibility during refactoring
PORT = CFG.PORT
ALLOWED_ROOTS = CFG.ALLOWED_ROOTS
DEFAULT_SCAN_DIR = ALLOWED_ROOTS[0] if ALLOWED_ROOTS else str(Path.cwd())
ENABLE_HASH_DEFAULT = bool(CFG.get("enable_hash", False))
PAGE_SIZE_DEFAULT = int(CFG.get("page_size_default", 50))

# Legacy objects adapted
OLLAMA = CFG.AI_CONFIG
MYSQL_CFG = CFG.MYSQL_CONFIG
MYSQL_ENABLED = MYSQL_CFG["enable"]
TRASH_DIR = CFG.TRASH_DIR
LOG_LEVEL = CFG.LOG_CONFIG.get("level", "INFO")
LOG_FILE = CFG.LOG_CONFIG.get("file", "")
