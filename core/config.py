# -*- coding: utf-8 -*-
from pathlib import Path
try:
    import tomllib  # py3.11+
except Exception:
    import tomli as tomllib

def load_config():
    cfg_path = Path(__file__).resolve().parents[1] / "config.toml"
    if not cfg_path.exists():
        cfg_path = Path(__file__).resolve().parents[1] / "config_example.toml"
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)

CFG = load_config()
ALLOWED_ROOTS = [str(Path(r).resolve()) for r in CFG.get("allowed_roots", [])]
DEFAULT_SCAN_DIR = ALLOWED_ROOTS[0] if ALLOWED_ROOTS else str(Path.cwd())
ENABLE_HASH_DEFAULT = bool(CFG.get("enable_hash", False))
PAGE_SIZE_DEFAULT = int(CFG.get("page_size_default", 200))
PORT = int(CFG.get("port", 5005))
OLLAMA = CFG.get("ollama", {"enable": False, "model":"qwen2.5:latest", "timeout_sec":30})
MYSQL_CFG = CFG.get("mysql", {"enable": False})
MYSQL_ENABLED = bool(MYSQL_CFG.get("enable"))
TRASH_DIR = CFG.get("trash_dir", "")
