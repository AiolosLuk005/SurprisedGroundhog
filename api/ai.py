from flask import Blueprint, request, jsonify
from core.ollama import call_ollama_keywords

bp = Blueprint("ai", __name__, url_prefix="/api/ai")

def _contains_pathlike(s: str) -> bool:
    if not s: return False
    s = s.lower()
    suspicious = [":\\", ":/", "/users/", "/home/", "\\", "/etc/", "c:\\", "d:\\"]
    return any(token in s for token in suspicious)

@bp.get("/health")
def health():
    return jsonify({"ok": True})

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
    return jsonify({"ok": True, "keywords": out})
