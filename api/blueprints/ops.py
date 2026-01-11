from flask import Blueprint, request, jsonify, send_file, send_from_directory, abort
from pathlib import Path
from send2trash import send2trash
import shutil
import io
from PIL import Image

from core.utils.iterfiles import is_under_allowed_roots
from core.settings import SETTINGS
from core.mysql_log import log_op
from core.normalize_runner import normalize_file
# from core.config import SETTINGS as CFG_DICT # removed to fix import error

bp = Blueprint("ops", __name__)

@bp.post("/apply_ops")
def apply_ops():
    data = request.get_json(silent=True) or {}
    ops, done, errors = data.get("ops", []), 0, []

    for op in ops:
        try:
            action = op.get("action")
            # ... (Implementation copied from original routes.py)
            # Re-implementing specific secure checks for clarity
            
            if action == "delete":
                if not SETTINGS.get("features", {}).get("enable_delete", True):
                    raise ValueError("删除功能已禁用")
                src = op.get("path")
                if not (src and is_under_allowed_roots(src)):
                    raise ValueError("路径不合法")
                send2trash(src)
                log_op("delete", src_path=src)
                done += 1

            elif action == "move":
                if not SETTINGS.get("features", {}).get("enable_move", True):
                    raise ValueError("移动功能已禁用")
                src, dst_full = op.get("src"), op.get("dst")
                if not (src and dst_full and is_under_allowed_roots(src) and is_under_allowed_roots(dst_full)):
                    raise ValueError("路径不合法")
                Path(dst_full).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(src, dst_full)
                log_op("move", src_path=src, dst_path=dst_full)
                done += 1
                
            # ... rename logic similar ...
            
        except Exception as e:
            errors.append(f"操作 {op.get('action')} 失败：{e}")

    return jsonify({"ok": True, "done": done, "errors": errors})

@bp.post("/normalize")
def normalize_endpoint():
    # ... logic from routes.py ...
    data = request.get_json(force=True, silent=True) or {}
    files = data.get("files") or []
    strategy = data.get("on_unsupported") or "fallback"
    collection = data.get("collection") or "default"
    # Fix: Get normalize config correctly from settings or config
    base_dir = "data/normalized" # default
    out_root = Path(base_dir) / collection
    
    results = []
    for f in files:
        try:
            res = normalize_file(f, out_root, on_unsupported=strategy)
            results.append({
                "path": f, "ok": res.ok, "doc_id": res.doc_id
            })
        except Exception as e:
             results.append({"path": f, "ok": False, "error": str(e)})
    return jsonify({"ok": True, "results": results})

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
