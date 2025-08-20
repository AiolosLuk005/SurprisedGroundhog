import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "config/settings.json"

def load_settings():
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_settings(data):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ✅ 确保这一行存在
SETTINGS = load_settings()
