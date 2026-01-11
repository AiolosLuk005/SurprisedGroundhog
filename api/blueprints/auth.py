from flask import Blueprint, request, jsonify, session
from core.settings import SETTINGS, save_settings

bp = Blueprint("auth", __name__)

@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = data.get("username")
    pwd = data.get("password")
    
    # Simple auth based on settings.json
    # In a real app, use a DB or hashing. keeping compatibility.
    admin_user = SETTINGS.get("auth", {}).get("admin_username", "admin")
    admin_pass = SETTINGS.get("auth", {}).get("admin_password", "admin")
    
    if user == admin_user and pwd == admin_pass:
        session["user"] = user
        session["level"] = SETTINGS.get("permissions", {}).get(user, 1)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "用户名或密码错误"}), 401

@bp.get("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@bp.get("/settings")
def get_settings():
    out = dict(SETTINGS)
    if "user" in session:
        out["user"] = session.get("user")
        out["level"] = session.get("level")
    return jsonify(out)

@bp.post("/settings")
def update_settings_route():
    data = request.get_json(silent=True) or {}
    for key in ("theme", "ai", "features", "prompts"):
        if key in data:
            SETTINGS[key] = data[key]
    save_settings(SETTINGS)
    return jsonify({"ok": True})
