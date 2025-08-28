from flask import Blueprint, request, jsonify
from core.ollama import call_ollama_keywords, call_ollama_tags
from core.extractors import extract_text_for_keywords
import json, urllib.request, tempfile, os, re
from pathlib import Path
from core.settings import SETTINGS
from datetime import datetime
from core.state import STATE, save_state

bp = Blueprint("ai", __name__, url_prefix="/api/ai")

def _contains_pathlike(s: str) -> bool:
    if not s: return False
    s = s.lower()
    suspicious = [":\\", ":/", "/users/", "/home/", "\\", "/etc/", "c:\\", "d:\\"]
    return any(token in s for token in suspicious)

@bp.get("/health")
def health():
    return jsonify({"ok": True})

@bp.get("/ollama/models")
def list_ollama_models():
    base = SETTINGS.get("ai", {}).get("url", "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=5) as resp:
            data = json.load(resp)
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        models = []
    return jsonify({"ok": True, "models": models})

@bp.post("/keywords")
def keywords():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "")[:20000]
    seeds = (data.get("seeds") or "").strip()
    max_len = int(data.get("max_len", 50))
    if _contains_pathlike(text):
        return jsonify({"ok": False, "error": "path-like content forbidden"}), 400
    out = call_ollama_keywords(text[:80], text, max_total_chars=max_len, seeds=seeds)
    if not out:
        prefix = (seeds + ", ") if seeds else ""
        remain = max_len - len(prefix)
        out = (prefix + text.replace("\n"," ")[:max(0, remain)]).strip(", ")
    tags = call_ollama_tags(text[:80], text)
    kw_list = [w.strip() for w in re.split(r"[，,;；]", out or "") if w.strip()]
    STATE.setdefault("keywords_log", [])
    STATE["keywords_log"].append({
        "time": datetime.utcnow().isoformat(),
        "source": "text",
        "seeds": seeds,
        "input_preview": text[:100],
        "keywords": kw_list,
        "tags": tags,
    })
    STATE["keywords_log"] = STATE["keywords_log"][-100:]
    save_state()
    return jsonify({"ok": True, "keywords": kw_list, "tags": tags})

@bp.post("/keywords_file")
def keywords_file():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "file required"}), 400
    seeds = (request.form.get("seeds") or "").strip()
    max_len = int(request.form.get("max_len", 50))
    max_len = max(1, min(200, max_len))
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            f.save(tmp)
        body = extract_text_for_keywords(tmp_path, max_chars=3000)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    title = f.filename or ""
    kw = call_ollama_keywords(title, body, max_total_chars=max_len, seeds=seeds) or ""
    if not kw:
        base = Path(title).stem.replace("_", " ").replace("-", " ")
        prefix = (seeds + ", ") if seeds else ""
        kw = prefix + base[:max(0, max_len - len(prefix))]
    kw = kw[:max_len]
    tags = call_ollama_tags(title, body)
    kw_list = [w.strip() for w in re.split(r"[，,;；]", kw or "") if w.strip()]
    STATE.setdefault("keywords_log", [])
    STATE["keywords_log"].append({
        "time": datetime.utcnow().isoformat(),
        "source": "file",
        "filename": title,
        "seeds": seeds,
        "keywords": kw_list,
        "tags": tags,
    })
    STATE["keywords_log"] = STATE["keywords_log"][-100:]
    save_state()
    return jsonify({"ok": True, "keywords": kw_list, "tags": tags})
