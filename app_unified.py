# -*- coding: utf-8 -*-
"""
Surprised Groundhog — 统一入口（LAN / Full 合并）
- "/"        : LAN 安全版（仅扫描 + AI，无服务器端敏感文件操作）
- "/full/*"  : 完整版，仅允许本机访问（127.0.0.1 / ::1）
- 兼容性     : 旧版把接口打到根路径或 /api/* 时，自动 307 重写到 /full/*
- 目录浏览   : /ls 供前端目录选择弹窗使用（跨平台：Windows 盘符 / POSIX /）

使用：
  python app_unified.py
"""
import os
from urllib.parse import urlencode
from flask import Flask, request, abort, redirect, jsonify

# 你的项目里已有的蓝图/配置（路径按你现有工程保持不变）
from api.ai import bp as ai_bp           # /api/ai/*
from api.routes import bp as full_bp     # /full/*
from core.config import PORT             # 例如 5005

# 旧接口（根路径）清单：用于自动重写到 /full/*
ROOT_API_PATHS = {
    "/scan", "/page",
    "/export_csv", "/import_mysql",
    "/apply_ops", "/kw", "/keywords"
}

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # --------------------------- 蓝图注册 ---------------------------
    app.register_blueprint(ai_bp)                 # /api/ai/*
    app.register_blueprint(full_bp, url_prefix="/full")  # 完整功能

    # --------------------------- 访问控制 ---------------------------
    @app.before_request
    def _only_local_for_full():
        """仅允许本机访问 /full/*，防止同网段他人操作你的服务器文件。"""
        p = (request.path or "/")
        if p.startswith("/full"):
            ra = (request.remote_addr or "")
            if ra not in ("127.0.0.1", "::1"):
                abort(403)
        return None

    # --------------------------- 兜底重写 ---------------------------
    @app.before_request
    def _rewrite_legacy_root_paths():
        """
        若旧前端仍向根路径发请求（如 fetch('/scan')），
        则 307 到 /full/*；/ls 保留在根路径，不做重写。
        """
        p = (request.path or "/")
        if p.startswith("/full") or p.startswith("/static") or p.startswith("/api/ai"):
            return None
        if p == "/ls":
            return None  # /ls 给目录选择用，不能重写
        if p in ROOT_API_PATHS:
            target = "/full" + request.path
            if request.query_string:
                target += "?" + request.query_string.decode("utf-8", errors="ignore")
            return redirect(target, code=307)
        return None

    # --------------------------- 目录浏览（给前端弹窗用） ---------------------------
    @app.get("/ls")
    def ls_root():
        """
        返回统一结构：
        { "ok": true, "dir": "<当前目录或空>", "subs": ["D:/", "E:/", ...] }
        - 不传 ?dir= ：列“根级”可选项（Windows=盘符；Linux/macOS="/" 的一级目录）
        - 传 ?dir=<目录>：列该目录下【子目录】完整路径
        """
        def list_windows_drives():
            subs = []
            for code in range(ord('C'), ord('Z') + 1):
                root = f"{chr(code)}:/"
                if os.path.exists(root):
                    subs.append(root)
            return subs

        def list_posix_root():
            try:
                with os.scandir("/") as it:
                    return [os.path.join("/", e.name) for e in it if e.is_dir()]
            except Exception:
                return []

        dir_arg = request.args.get("dir")

        # 根级：给出可选起点
        if not dir_arg:
            subs = list_windows_drives() if os.name == "nt" else list_posix_root()
            return jsonify({"ok": True, "dir": "", "subs": subs})

        # 子目录列表
        base = os.path.abspath(dir_arg)
        subs = []
        try:
            if os.path.exists(base):
                with os.scandir(base) as it:
                    for e in it:
                        if e.is_dir():
                            subs.append(os.path.join(base, e.name))
            subs.sort(key=lambda s: s.lower())
        except Exception:
            subs = []

        return jsonify({"ok": True, "dir": base, "subs": subs})

    # --------------------------- 参数归一化工具 ---------------------------
    def _norm_recursive_arg(args: dict) -> dict:
        """把 recur/deep/r/subdirs/include_subdirs/walk 等别名统一为 recursive=0/1"""
        a = dict(args or {})
        any_rec = (
            a.get("recursive") or a.get("recur") or a.get("deep") or
            a.get("r") or a.get("subdirs") or a.get("include_subdirs") or a.get("walk")
        )
        if any_rec is not None:
            val = str(any_rec).strip().lower()
            a["recursive"] = "0" if val in ("0", "false", "no", "off") else "1"
        return a

    def _redirect_with_args(path: str, args: dict, code: int = 307):
        qs = urlencode(args, doseq=True)
        target = path + ("?" + qs if qs else "")
        if target.rstrip("?") != request.full_path.rstrip("?"):
            return redirect(target, code=code)
        return None

    # 对 /full/scan 做“参数规范化重定向”
    @app.before_request
    def normalize_recursive_for_full_scan():
        if request.path == "/full/scan":
            args = _norm_recursive_arg(request.args.to_dict(flat=True))
            resp = _redirect_with_args("/full/scan", args, code=307)
            if resp is not None:
                return resp
        return None

    # --------------------------- /api/* 兼容为 /full/* ---------------------------
    @app.get("/api/scan")
    def api_scan_alias():
        args = _norm_recursive_arg(request.args.to_dict(flat=True))
        return _redirect_with_args("/full/scan", args) or redirect("/full/scan", code=307)

    @app.get("/api/export_csv")
    def api_export_alias():
        return _redirect_with_args("/full/export_csv", request.args.to_dict(flat=True)) or redirect("/full/export_csv", code=307)

    @app.get("/api/import_mysql")
    def api_import_alias():
        return _redirect_with_args("/full/import_mysql", request.args.to_dict(flat=True)) or redirect("/full/import_mysql", code=307)

    @app.post("/api/apply_ops")
    def api_apply_ops_alias():
        target = "/full/apply_ops"
        if request.query_string:
            target += "?" + request.query_string.decode("utf-8", errors="ignore")
        return redirect(target, code=307)

    @app.get("/api/kw")
    @app.get("/api/keywords")
    def api_kw_alias():
        return _redirect_with_args("/full/kw", request.args.to_dict(flat=True)) or redirect("/full/kw", code=307)

    return app


if __name__ == "__main__":
    # host=0.0.0.0 以便局域网可访问；debug 可按需切换
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
