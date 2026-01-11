from flask import Blueprint, jsonify, request, send_file, render_template, session, current_app
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
import csv
import os

from core.config import ALLOWED_ROOTS, DEFAULT_SCAN_DIR, PAGE_SIZE_DEFAULT, ENABLE_HASH_DEFAULT
from core.utils.iterfiles import is_under_allowed_roots, iter_files
from core.mysql_log import get_mysql_conn

bp = Blueprint("scan", __name__)

def _parse_recursive(params):
    val = next(
        (params.get(k) for k in ("recursive", "recur", "deep", "r", "subdirs", "include_subdirs", "walk") 
         if params.get(k) is not None), "1"
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")

def _parse_types(params):
    s = next((params.get(k) for k in ("types", "exts", "ext") if params.get(k)), "")
    return s.split(",") if s else None

@bp.get("/")
def index_page():
    return render_template(
        "full.html",
        allowed_roots=ALLOWED_ROOTS,
        default_dir="",
        enable_hash_default=ENABLE_HASH_DEFAULT,
        page_size_default=PAGE_SIZE_DEFAULT,
        current_user=session.get("user")
    )

@bp.get("/ls")
def list_dirs():
    base = request.args.get("dir")
    if base:
        if not is_under_allowed_roots(base):
            return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400
        try:
            subs = [str(p) for p in Path(base).iterdir() if p.is_dir()]
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
    else:
        subs = ALLOWED_ROOTS
    return jsonify({"ok": True, "subs": subs})

@bp.get("/scan")
def scan():
    scan_dir = request.values.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.values.get("hash", "0") == "1"
    recursive = _parse_recursive(request.values)
    page = max(int(request.values.get("page", "1")), 1)
    page_size = max(int(request.values.get("page_size", str(PAGE_SIZE_DEFAULT))), 1)
    category = request.values.get("category")
    types = _parse_types(request.values)

    if not is_under_allowed_roots(scan_dir):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

    rows = [asdict(r) for r in iter_files(scan_dir, with_hash, category, types, recursive)]
    total = len(rows)
    start, end = (page - 1) * page_size, (page * page_size)
    return jsonify({"ok": True, "data": rows[start:end], "total": total})

@bp.get("/export_csv")
def export_csv():
    scan_dir = request.values.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.values.get("hash", "0") == "1"
    recursive = _parse_recursive(request.values)
    category = request.values.get("category")
    types = _parse_types(request.values)

    if not is_under_allowed_roots(scan_dir):
        return "目录不在允许的根目录内", 400

    project_root = Path(current_app.root_path).resolve()
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    base = os.path.basename(scan_dir.rstrip("\\/")) or "root"
    filename = f"groundhog_{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = output_dir / filename

    fieldnames = ["category","full_path","dir_path","name","ext","size_bytes","mtime_iso","sha256","keywords"]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in iter_files(scan_dir, with_hash, category, types, recursive):
            d = asdict(row)
            d.pop("previewable", None)
            d["keywords"] = "，".join(row.keywords or [])
            writer.writerow({k: d.get(k) for k in fieldnames})

    return send_file(str(filepath), as_attachment=True, download_name=filename, mimetype="text/csv")
