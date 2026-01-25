from flask import Blueprint, jsonify, request
from dataclasses import asdict
from core.config import ALLOWED_ROOTS, DEFAULT_SCAN_DIR
from core.utils.iterfiles import is_under_allowed_roots, iter_files
from core.pg_db import upsert_files, PG_ENABLED

bp = Blueprint("db_save", __name__)

def _parse_recursive(params):
    val = next(
        (params.get(k) for k in ("recursive", "recur", "deep", "r", "subdirs", "include_subdirs", "walk") 
         if params.get(k) is not None), "1"
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")

def _parse_types(params):
    s = next((params.get(k) for k in ("types", "exts", "ext") if params.get(k)), "")
    return s.split(",") if s else None

@bp.post("/save_to_db")
def save_to_db():
    """手动保存扫描结果到 PostgreSQL 数据库"""
    if not PG_ENABLED:
        return jsonify({"ok": False, "error": "PostgreSQL 未启用"}), 400
    
    scan_dir = request.values.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.values.get("hash", "0") == "1"
    recursive = _parse_recursive(request.values)
    category = request.values.get("category")
    types = _parse_types(request.values)

    if not is_under_allowed_roots(scan_dir):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

    rows = [asdict(r) for r in iter_files(scan_dir, with_hash, category, types, recursive)]
    
    try:
        upsert_files(rows)
        return jsonify({"ok": True, "saved": len(rows), "message": f"成功保存 {len(rows)} 条记录到数据库"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"保存失败: {str(e)}"}), 500
