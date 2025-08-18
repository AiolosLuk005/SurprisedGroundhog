from flask import Blueprint, render_template, request, jsonify, send_file, send_from_directory, abort, current_app
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import os, io, csv
from PIL import Image

from core.config import ALLOWED_ROOTS, DEFAULT_SCAN_DIR, ENABLE_HASH_DEFAULT, PAGE_SIZE_DEFAULT, MYSQL_ENABLED, TRASH_DIR
from core.utils.iterfiles import is_under_allowed_roots, iter_files
from core.extractors import extract_text_for_keywords
from core.ollama import call_ollama_keywords
from core.state import STATE, save_state
from core.mysql_log import get_mysql_conn, log_op

bp = Blueprint("api", __name__)

def _parse_recursive(params):
    val = next(
        (params.get(k) for k in (
            "recursive",
            "recur",
            "deep",
            "r",
            "subdirs",
            "include_subdirs",
            "walk",
        ) if params.get(k) is not None),
        "1",
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
        default_dir=DEFAULT_SCAN_DIR,
        enable_hash_default=ENABLE_HASH_DEFAULT,
        page_size_default=PAGE_SIZE_DEFAULT
    )

@bp.get("/scan")
def scan():
    scan_dir = request.args.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.args.get("hash", "0") == "1"
    recursive = request.args.get("recursive", "0") == "1"
    recursive = _parse_recursive(request.form)
    page = max(int(request.args.get("page", "1")), 1)
    page_size = max(int(request.args.get("page_size", str(PAGE_SIZE_DEFAULT))), 1)
    category = request.args.get("category")
    types = _parse_types(request.args)

    if not is_under_allowed_roots(scan_dir):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

    rows = [asdict(r) for r in iter_files(scan_dir, with_hash, category, types, recursive)]
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]
    return jsonify({"ok": True, "data": page_rows, "total": total})

@bp.get("/export_csv")
def export_csv():
    scan_dir = request.args.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.args.get("hash", "0") == "1"
    recursive = request.args.get("recursive", "0") == "1"
    recursive = _parse_recursive(request.args)
    category = request.args.get("category")
    types = _parse_types(request.args)

    if not is_under_allowed_roots(scan_dir):
        return "目录不在允许的根目录内", 400

    project_root = Path(current_app.root_path).resolve()
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    base = os.path.basename(scan_dir.rstrip("\/")) or "root"
    filename = f"groundhog_{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = output_dir / filename

    fieldnames = ["category","full_path","dir_path","name","ext","size_bytes","mtime_iso","sha256","keywords"]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in iter_files(scan_dir, with_hash, category, types, recursive):
            d = asdict(row); d.pop("previewable", None)
            writer.writerow({k: d.get(k) for k in fieldnames})

    return send_file(str(filepath), as_attachment=True, download_name=filename, mimetype="text/csv")

@bp.post("/import_mysql")
def import_mysql():
    if not MYSQL_ENABLED:
        return jsonify({"ok": False, "error": "MySQL 未启用"}), 400

    scan_dir = request.form.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.form.get("hash", "0") == "1"
    recursive = _parse_recursive(request.form)
    recursive = request.form.get("recursive", "0") == "1"
    category = request.form.get("category")
    types = _parse_types(request.form)

    if not is_under_allowed_roots(scan_dir):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

    import mysql.connector
    conn = get_mysql_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        category VARCHAR(16) NOT NULL,
        full_path TEXT NOT NULL,
        dir_path TEXT NOT NULL,
        name VARCHAR(512) NOT NULL,
        ext VARCHAR(64),
        size_bytes BIGINT NOT NULL,
        mtime_iso VARCHAR(32) NOT NULL,
        sha256 CHAR(64) NULL,
        keywords VARCHAR(255) NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    try: cur.execute("CREATE INDEX idx_ext ON files (ext)")
    except Exception: pass
    try: cur.execute("CREATE INDEX idx_mtime ON files (mtime_iso)")
    except Exception: pass

    sql = """
    INSERT INTO files (category, full_path, dir_path, name, ext, size_bytes, mtime_iso, sha256, keywords)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    batch, count = [], 0
    for r in iter_files(scan_dir, with_hash, category, types, recursive):
        batch.append((r.category, r.full_path, r.dir_path, r.name, r.ext, r.size_bytes, r.mtime_iso, r.sha256, r.keywords))
        if len(batch) >= 1000:
            cur.executemany(sql, batch); conn.commit(); count += len(batch); batch.clear()
    if batch:
        cur.executemany(sql, batch); conn.commit(); count += len(batch)
    cur.close(); conn.close()
    return jsonify({"ok": True, "inserted": count})

@bp.get("/ls")
def ls():
    base = request.args.get("dir", "")
    if not base:
        return jsonify({"ok": True, "dir": "", "subs": ALLOWED_ROOTS})
    if not is_under_allowed_roots(base):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

    try:
        subs = []
        for name in os.listdir(base):
            p = os.path.join(base, name)
            if os.path.isdir(p):
                subs.append(os.path.abspath(p))
        subs.sort()
        return jsonify({"ok": True, "dir": base, "subs": subs})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/update_keywords")
def update_keywords():
    data = request.get_json(silent=True) or {}
    updates = data.get("updates", [])
    if "keywords" not in STATE:
        STATE["keywords"] = {}
    saved = 0
    for u in updates:
        p = u.get("path")
        kw = (u.get("keywords") or "").strip()
        if p and is_under_allowed_roots(p):
            STATE["keywords"][p] = kw
            saved += 1
    save_state()
    return jsonify({"ok": True, "saved": saved})

@bp.post("/clear_keywords")
def clear_keywords():
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    if "keywords" not in STATE:
        STATE["keywords"] = {}
    cleared = 0
    for p in paths:
        if p and is_under_allowed_roots(p) and p in STATE["keywords"]:
            del STATE["keywords"][p]
            cleared += 1
    save_state()
    return jsonify({"ok": True, "cleared": cleared})

@bp.post("/keywords")
def gen_keywords():
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    seeds = (data.get("seeds") or "").strip()
    out = {}
    if "keywords" not in STATE: STATE["keywords"] = {}

    for p in paths:
        if not is_under_allowed_roots(p):
            continue
        title = Path(p).name
        ext = Path(p).suffix.lower().lstrip(".")
        from core.utils.iterfiles import detect_category
        cat = detect_category(ext)
        if cat in ("TEXT","DATA","PDF","SLIDES"):
            body = extract_text_for_keywords(p, max_chars=3000)
            kw = call_ollama_keywords(title, body, max_total_chars=50, seeds=seeds)
            if not kw:
                base = Path(p).stem.replace("_"," ").replace("-"," ")
                prefix = (seeds + ", ") if seeds else ""
                remain = max(0, 50 - len(prefix))
                kw = prefix + base[:remain]
        else:
            base = Path(p).stem
            prefix = (seeds + ", ") if seeds else ""
            remain = max(0, 50 - len(prefix))
            kw = prefix + base[:remain]
        kw = kw[:50]
        out[p] = kw
        STATE["keywords"][p] = kw
    save_state()
    return jsonify({"ok": True, "keywords": out})

@bp.post("/apply_ops")
def apply_ops():
    from send2trash import send2trash
    data = request.get_json(silent=True) or {}
    ops = data.get("ops", [])
    done, errors = 0, []

    for op in ops:
        try:
            action = op.get("action")
            if action == "delete":
                src = op.get("path")
                if not (src and is_under_allowed_roots(src)):
                    raise ValueError("路径不合法")
                try:
                    send2trash(src)
                except Exception:
                    if TRASH_DIR:
                        target = Path(TRASH_DIR).resolve() / Path(src).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(src, str(target))
                    else:
                        raise RuntimeError("回收站删除失败，未配置 trash_dir，已取消操作")
                log_op("delete", src_path=src)
                done += 1

            elif action == "move":
                src, dst_dir = op.get("src"), op.get("dst")
                if not (src and dst_dir and is_under_allowed_roots(src) and is_under_allowed_roots(dst_dir)):
                    raise ValueError("路径不合法")
                Path(dst_dir).mkdir(parents=True, exist_ok=True)
                dst_full = str(Path(dst_dir) / Path(src).name)
                os.replace(src, dst_full)
                log_op("move", src_path=src, dst_path=dst_full)
                done += 1

            elif action == "rename":
                src, new_name = op.get("src"), op.get("new_name")
                if not (src and new_name and is_under_allowed_roots(src)):
                    raise ValueError("路径不合法")
                dirpath = str(Path(src).parent)
                dst_full = str(Path(dirpath) / new_name)
                old_name = Path(src).name
                os.replace(src, dst_full)
                log_op("rename", src_path=src, dst_path=dst_full, old_name=old_name, new_name=new_name)
                done += 1

            else:
                raise ValueError("未知操作")

        except Exception as e:
            errors.append(str(e))

    return jsonify({"ok": True, "done": done, "errors": errors})

@bp.get("/file")
def serve_file():
    path = request.args.get("path")
    if not (path and is_under_allowed_roots(path)):
        abort(403)
    p = Path(path)
    return send_from_directory(p.parent, p.name, as_attachment=False)

@bp.get("/thumb")
def thumb():
    path = request.args.get("path")
    if not (path and is_under_allowed_roots(path)):
        abort(403)
    p = Path(path)
    try:
        with Image.open(p) as im:
            im.thumbnail((320, 240))
            buf = io.BytesIO()
            im.save(buf, format="JPEG")
            buf.seek(0)
            return send_file(buf, mimetype="image/jpeg")
    except Exception:
        abort(404)
