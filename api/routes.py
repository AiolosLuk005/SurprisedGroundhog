from flask import Blueprint, render_template, request, jsonify, send_file, send_from_directory, abort, current_app
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import os, io, csv, shutil
from PIL import Image
from send2trash import send2trash
from core.config import ALLOWED_ROOTS, DEFAULT_SCAN_DIR, ENABLE_HASH_DEFAULT, PAGE_SIZE_DEFAULT, MYSQL_ENABLED, TRASH_DIR
from core.utils.iterfiles import is_under_allowed_roots, iter_files  # 依然复用你的核心扫描逻辑
from core.extractors import extract_text_for_keywords
from core.ollama import call_ollama_keywords
from core.state import STATE, save_state
from core.mysql_log import get_mysql_conn, log_op
from flask import session
from core.settings import SETTINGS, save_settings

bp = Blueprint("full_api", __name__)

# -------------------- 本地分类（含 zip/rar/7z ） --------------------
# 仅用于关键词分支判断，保证不依赖外部 detect_category 也能识别 ARCHIVE
CATEGORIES_LOCAL = {
    "TEXT":   {"docx","doc","txt","md"},
    "DATA":   {"xlsx","xlsm","xls","csv","xml"},
    "SLIDES": {"pptx","ppt"},
    "ARCHIVE":{"zip","rar","7z"},
    "PDF":    {"pdf"},
    "IMAGE":  {"jpg","jpeg","gif","png","tif","tiff","bmp","svg","webp"},
    "AUDIO":  {"mp3","wav","flac","m4a","aac","ogg"},
    "VIDEO":  {"mp4","mkv","avi","mov","wmv","webm"},
}
def _detect_category_local(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    for cat, exts in CATEGORIES_LOCAL.items():
        if e in exts:
            return cat
    return "TEXT"

# -------------------- 参数解析 --------------------
def _parse_recursive(params):
    val = next(
        (params.get(k) for k in (
            "recursive", "recur", "deep", "r",
            "subdirs", "include_subdirs", "walk"
        ) if params.get(k) is not None),
        "1",
    )
    return str(val).strip().lower() not in ("0", "false", "no", "off")

def _parse_types(params):
    s = next((params.get(k) for k in ("types", "exts", "ext") if params.get(k)), "")
    return s.split(",") if s else None

# -------------------- 页面 --------------------
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

# -------------------- 导出 CSV --------------------
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
            d.pop("previewable", None)  # 防止 DictWriter 报错
            writer.writerow({k: d.get(k) for k in fieldnames})

    return send_file(str(filepath), as_attachment=True, download_name=filename, mimetype="text/csv")

# -------------------- 导入 MySQL --------------------
@bp.post("/import_mysql")
def import_mysql():
    if not MYSQL_ENABLED:
        return jsonify({"ok": False, "error": "MySQL 未启用"}), 400

    scan_dir = request.values.get("dir", DEFAULT_SCAN_DIR)
    with_hash = request.values.get("hash", "0") == "1"
    recursive = _parse_recursive(request.values)
    category = request.values.get("category")
    types = _parse_types(request.values)

    if not is_under_allowed_roots(scan_dir):
        return jsonify({"ok": False, "error": "目录不在允许的根目录内"}), 400

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

# -------------------- 关键词管理 --------------------
@bp.post("/update_keywords")
def update_keywords():
    data = request.get_json(silent=True) or {}
    updates = data.get("updates", [])
    STATE.setdefault("keywords", {})
    saved = 0
    for u in updates:
        p, kw = u.get("path"), (u.get("keywords") or "").strip()
        if p and is_under_allowed_roots(p):
            STATE["keywords"][p] = kw
            saved += 1
    save_state()
    return jsonify({"ok": True, "saved": saved})

@bp.post("/clear_keywords")
def clear_keywords():
    if not SETTINGS.get("features", {}).get("enable_ai_keywords", True):
        return jsonify({"ok": False, "error": "关键词功能已禁用"}), 403
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    STATE.setdefault("keywords", {})
    cleared = 0
    for p in paths:
        if p and is_under_allowed_roots(p) and p in STATE["keywords"]:
            del STATE["keywords"][p]
            cleared += 1
    save_state()
    return jsonify({"ok": True, "cleared": cleared})

@bp.post("/keywords")
def gen_keywords():
    if not SETTINGS.get("features", {}).get("enable_ai_keywords", True):
        return jsonify({"ok": False, "error": "关键词功能已禁用"}), 403
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    seeds = (data.get("seeds") or "").strip()
    max_len = int(data.get("max_len", 50))
    max_len = max(1, min(200, max_len))
    out = {}
    STATE.setdefault("keywords", {})

    for p in paths:
        if not is_under_allowed_roots(p):
            continue
        title = Path(p).name
        ext = Path(p).suffix.lower().lstrip(".")
        cat = _detect_category_local(ext)

        if cat in ("TEXT", "DATA", "PDF", "SLIDES", "ARCHIVE"):
            body = extract_text_for_keywords(p, max_chars=3000)
            kw = call_ollama_keywords(title, body, max_total_chars=max_len, seeds=seeds) or ""
            if not kw:
                base = Path(p).stem.replace("_", " ").replace("-", " ")
                prefix = (seeds + ", ") if seeds else ""
                kw = prefix + base[:max(0, max_len - len(prefix))]
        elif cat == "IMAGE":
            kw = "图片关键词提取功能待实现"
        elif cat == "AUDIO":
            kw = "音频关键词提取功能待实现"
        else:
            base = Path(p).stem
            prefix = (seeds + ", ") if seeds else ""
            kw = prefix + base[:max(0, max_len - len(prefix))]

        kw = kw[:max_len]
        out[p] = kw
        STATE["keywords"][p] = kw

    save_state()
    return jsonify({"ok": True, "keywords": out})

# -------------------- 文件操作 --------------------
@bp.post("/apply_ops")
def apply_ops():
    data = request.get_json(silent=True) or {}
    ops, done, errors = data.get("ops", []), 0, []

    for op in ops:
        try:
            action = op.get("action")
            if action == "delete":
                if not SETTINGS.get("features", {}).get("enable_delete", True):
                    raise ValueError("删除功能已禁用")
                src = op.get("path")
                if not (src and is_under_allowed_roots(src)):
                    raise ValueError("路径不合法")
                send2trash(src)  # 始终回收站删除
                log_op("delete", src_path=src)
                done += 1

            elif action == "move":
                if not SETTINGS.get("features", {}).get("enable_move", True):
                    raise ValueError("移动功能已禁用")
                src, dst_dir = op.get("src"), op.get("dst")
                if not (src and dst_dir and is_under_allowed_roots(src) and is_under_allowed_roots(dst_dir)):
                    raise ValueError("路径不合法")
                Path(dst_dir).mkdir(parents=True, exist_ok=True)
                dst_full = str(Path(dst_dir) / Path(src).name)
                shutil.move(src, dst_full)
                log_op("move", src_path=src, dst_path=dst_full)
                done += 1

            elif action == "rename":
                if not SETTINGS.get("features", {}).get("enable_rename", True):
                    raise ValueError("重命名功能已禁用")
                src, new_name = op.get("src"), op.get("new_name")
                if not (src and new_name and is_under_allowed_roots(src)):
                    raise ValueError("路径不合法")
                dst_full = str(Path(src).parent / new_name)
                shutil.move(src, dst_full)
                log_op("rename", src_path=src, dst_path=dst_full, old_name=Path(src).name, new_name=new_name)
                done += 1

            else:
                raise ValueError("未知操作")

        except Exception as e:
            errors.append(f"操作 {op.get('action')} 失败：{e}")

    return jsonify({"ok": True, "done": done, "errors": errors})

# -------------------- 文件访问 --------------------
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

@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = data.get("username")
    pwd = data.get("password")
    if user == SETTINGS["auth"]["admin_username"] and pwd == SETTINGS["auth"]["admin_password"]:
        session["user"] = user
        session["level"] = SETTINGS["permissions"].get(user, 1)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "用户名或密码错误"}), 401

@bp.get("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

# -------------------- 设置 --------------------
@bp.get("/settings")
def get_settings():
    return jsonify(SETTINGS)

@bp.post("/settings")
def update_settings_route():
    data = request.get_json(silent=True) or {}
    for key in ("theme", "ai", "features"):
        if key in data:
            SETTINGS[key] = data[key]
    save_settings(SETTINGS)
    return jsonify({"ok": True})
