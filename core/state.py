import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[1] / "state.json"
try:
    if STATE_PATH.exists():
        STATE = json.loads(STATE_PATH.read_text("utf-8"))
    else:
        STATE = {}
except Exception:
    STATE = {}

def save_state():
    try:
        STATE_PATH.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
