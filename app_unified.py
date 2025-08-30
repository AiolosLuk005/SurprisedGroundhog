# -*- coding: utf-8 -*-
import os
from urllib.parse import urlencode
from flask import Flask, request, abort, redirect, jsonify, session
from core.settings import SETTINGS

# 你的蓝图（保持现有路径）
from api.ai import bp as ai_bp            # /api/ai/*
from api.routes import bp as full_bp      # 我们将把它注册到 /full/*

# 端口配置
from core.config import PORT

# 旧版前端可能直接请求根路径接口，这里统一做 307 → /full/* 的兼容重写
ROOT_API_PATHS = {
    "/",
    "/scan", "/page",
    "/export_csv", "/import_mysql",
    "/apply_ops",
    "/kw", "/keywords",
    "/update_keywords", "/clear_keywords",
    "/file", "/thumb",
    "/ls",
}

def _redirect_with_args(target_path: str, params: dict | None):
    """拼接 querystring 并返回 307 重定向响应。"""
    if params:
        return redirect(target_path + "?" + urlencode(params), code=307)
    return redirect(target_path, code=307)

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = (
        SETTINGS.get("auth", {}).get("secret_key")
        or os.environ.get("SECRET_KEY")
        or "groundhog-secret"
    )

    # --------------------------- Blueprint Registration ---------------------------
    # /api/ai/* 直接保留
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    # 你的 routes.py 里 bp = Blueprint("api", __name__)
    # 我们统一挂到 /full 前缀下（你在 routes.py 中的所有接口都会暴露成 /full/xxx）
    app.register_blueprint(full_bp, url_prefix="/full")

    # --------------------------- Home ---------------------------
    # 访问根路径 → 进入完整页面（/full/ 渲染 full.html）
    @app.get("/")
    def home():
        return redirect("/full/", code=302)

    # --------------------------- Access Control ---------------------------
    @app.before_request
    def check_login_permission():
        if request.path.startswith("/full/") and not request.path.endswith("/login"):
            if "user" not in session:
                if request.is_json or request.method == "POST":
                    return jsonify({"ok": False, "error": "未登录"}), 401
    @app.before_request
    def _only_local_for_full():
        """
        只允许本机访问 /full/* ，防止同网段的人通过你的电脑操作文件。
        如果你以后需要局域网可用，可以放开这里或者在 routes 里拆分只读/只写接口。
        """
        if request.path.startswith("/full"):
            ra = (request.remote_addr or "")
            if ra not in ("127.0.0.1", "::1"):
                abort(403)
        return None

    # --------------------------- Legacy Fallback Rewrites ---------------------------
    @app.before_request
    def _rewrite_legacy_root_paths():
        """
        兼容旧前端：如果还请求根路径，如 fetch('/scan')，
        则把它 307 重定向到 /full/*（包含 /ls 在内）。
        """
        p = (request.path or "/")
        if p.startswith("/full") or p.startswith("/static") or p.startswith("/api"):
            return None

        if p in ROOT_API_PATHS:
            # 根路径 '/' 直接跳首页
            if p == "/":
                return redirect("/full/", code=302)

            # 其余接口按原路径映射到 /full/*
            target = "/full" + p
            if request.query_string:
                # 保留查询参数
                return redirect(target + "?" + request.query_string.decode("utf-8", errors="ignore"), code=307)
            return redirect(target, code=307)

        return None

    # --------------------------- (Optional) 简单健康检查 ---------------------------
    @app.get("/healthz")
    def health():
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    # host=0.0.0.0 允许局域网访问首页，但 /full/* 仍然只允许本机（见上面的 before_request）
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
