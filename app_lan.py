
# -*- coding: utf-8 -*-
"""
Surprised Groundhog - LAN/Full 合并入口（修正版）
- "/"        : LAN 安全版（本地浏览器扫描，不暴露服务器文件系统）
- "/full/*"  : 完整版（导出CSV/导入MySQL/移动/重命名/删除/关键词等）仅允许本机访问
- 兼容修复   : 旧前端把接口打到根路径或 /api/* 时，自动 307 到 /full/*
"""
import os
from urllib.parse import urlencode
from flask import Flask, render_template, request, abort, redirect, jsonify

from api.ai import bp as ai_bp         # AI 关键词接口（不接收路径/内容）
from api.routes import bp as full_bp   # 完整版蓝图
from core.config import PORT

# 注意：不包含 /ls（/ls 保留给前端“选择目录”使用）
ROOT_API_PATHS = {
    "/scan", "/page",
    "/export_csv", "/import_mysql",
    "/apply_ops", "/kw", "/keywords"
}

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # --------------------------- 蓝图注册 ---------------------------
    app.register_blueprint(ai_bp)                 # /api/ai/*（按你的蓝图内部前缀设置）
    app.register_blueprint(full_bp, url_prefix="/full")

    # --------------------------- 访问控制 ---------------------------
    @app.before_request
    def _only_local_for_full():
        """仅允许本机访问 /full/*，防止内网他人操作你的服务器文件。"""
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
        兜底：如果旧前端仍向根路径发请求（如 fetch('/scan')），
        则 307 到 /full/*；/ls 保留在根路径，不做重写。
        """
        p = (request.path or "/")
        if p.startswith("/full") or p.startswith("/static") or p.startswith("/api/ai"):
            return None
        if p == "/ls":
            return None  # 关键：/ls 不重写，供前端目录选择使用
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
        - 不传 ?dir= ：列“根级”可选项（Windows = 盘符；Linux/macOS = "/" 下的一级目录）
        - 传入 ?dir=某目录：列该目录下【子目录】名称（完整路径字符串）
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
            # Windows：列盘符；其他：列 / 的一级目录
            if os.name == "nt":
                subs = list_windows_drives()
            else:
                subs = list_posix_root()
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

    # --------------------------- 参数归一化 & /api/* 兼容 ---------------------------
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
        # 避免无限重定向（只有在参数有变化时才跳转）
        if target.rstrip("?") != request.full_path.rstrip("?"):
            return redirect(target, code=code)
        return None

    # 关键：对 /full/scan 做“参数规范化重定向”
    @app.before_request
    def normalize_recursive_for_full_scan():
        if request.path == "/full/scan":
            args = _norm_recursive_arg(request.args.to_dict(flat=True))
            resp = _redirect_with_args("/full/scan", args, code=307)
            if resp is not None:
                return resp
        return None

    # /api/* 兼容为 /full/*（GET 场景同时归并递归别名）
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
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
