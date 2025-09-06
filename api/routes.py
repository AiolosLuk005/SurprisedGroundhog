from flask import Blueprint, render_template, request, jsonify, send_file, send_from_directory, abort, current_app, session
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import os, io, csv, shutil, json, re, textwrap, math, tempfile
import requests
from PIL import Image
from send2trash import send2trash
from services.retrieval import CollectionManager

from core.extractors import extract_chunks
from core.chunking import index_chunks

from core.config import (
    ALLOWED_ROOTS, DEFAULT_SCAN_DIR, ENABLE_HASH_DEFAULT, PAGE_SIZE_DEFAULT,
    MYSQL_ENABLED, TRASH_DIR, CFG
)
from core.utils.iterfiles import is_under_allowed_roots, iter_files, detect_category  # 复用扫描逻辑
from core.state import STATE, save_state
from core.mysql_log import get_mysql_conn, log_op
from core.normalize_runner import normalize_file
from core.settings import SETTINGS, save_settings

# 新增：关键词流水线服务
try:
    from services.keywords import (
        extract_text_for_keywords, kw_fast, kw_embed, kw_llm,
        compose_keywords
    )
except Exception:  # pragma: no cover - 如果依赖缺失
    extract_text_for_keywords = None
    kw_fast = kw_embed = kw_llm = compose_keywords = None

bp = Blueprint("full_api", __name__)
retriever = CollectionManager()

# -------------------- 本地分类（含 zip/rar/7z ） --------------------
CATEGORIES_LOCAL = {
    "TEXT":   {"docx","doc","txt","md","rtf"},
    "DATA":   {"xlsx","xlsm","xls","csv","tsv","xml","parquet"},
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
            d.pop("previewable", None)
            d["keywords"] = "，".join(row.keywords or [])
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
        kw = "，".join(r.keywords or [])
        batch.append((r.category, r.full_path, r.dir_path, r.name, r.ext, r.size_bytes, r.mtime_iso, r.sha256, kw))
        if len(batch) >= 1000:
            cur.executemany(sql, batch); conn.commit(); count += len(batch); batch.clear()
    if batch:
        cur.executemany(sql, batch); conn.commit(); count += len(batch)
    cur.close(); conn.close()
    return jsonify({"ok": True, "inserted": count})

# -------------------- Normalize Files --------------------
@bp.post("/normalize")
def normalize_endpoint():
    data = request.get_json(force=True, silent=True) or {}
    files = data.get("files") or []
    strategy = data.get("on_unsupported") or "fallback"
    collection = data.get("collection") or "default"
    base_dir = SETTINGS.get("normalize", {}).get("artifact_dir", "data/normalized")
    out_root = Path(base_dir) / collection
    results = []
    for f in files:
        try:
            res = normalize_file(f, out_root, on_unsupported=strategy)
            results.append({
                "path": f,
                "ok": res.ok,
                "doc_id": res.doc_id,
                "out_dir": res.out_dir,
                "md": list(res.md_paths or []),
                "csv": list(res.csv_paths or []),
                "sidecar": res.sidecar,
                "message": res.message,
            })
        except Exception as e:
            results.append({"path": f, "ok": False, "doc_id": "", "out_dir": "", "md": [], "csv": [], "sidecar": "", "message": str(e)})
    return jsonify({"ok": True, "results": results})

# -------------------- 关键词管理（本地 Ollama Map-Reduce 增强） --------------------

# —— 工具：调用 Ollama generate API（仅本地 provider=ollama）
def _ollama_generate(prompt: str) -> str:
    ai = SETTINGS.get("ai", {}) or {}
    if ai.get("provider") != "ollama":
        raise RuntimeError("当前仅实现 provider=ollama 的关键词提取")
    url = (ai.get("url") or "http://localhost:11434").rstrip("/")
    model = ai.get("model") or "qwen2:7b"
    options = {
        "num_ctx": int(ai.get("num_ctx", 8192)),
        "temperature": float(ai.get("temperature", 0.3)),
        "top_p": float(ai.get("top_p", 0.9)),
        "repeat_penalty": float(ai.get("repeat_penalty", 1.1))
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "options": options,
        "stream": False
    }
    resp = requests.post(f"{url}/api/generate", json=payload, timeout=int(ai.get("timeout_sec", 60)))
    resp.raise_for_status()
    data = resp.json()
    # Ollama 返回 {"response":"..."}；我们统一取 response
    return data.get("response", "")

def _json_from_text(text: str):
    # 严格尝试 json 解析；若失败，尽力用正则提取第一个 {...} 块
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

def _split_text(s: str, chunk_chars: int):
    s = s or ""
    chunk_chars = max(500, int(chunk_chars or 2000))
    # 尽量按换行断；否则硬切
    out, buf = [], []
    acc = 0
    for line in s.splitlines():
        L = len(line) + 1
        if acc + L > chunk_chars and acc > 0:
            out.append("\n".join(buf))
            buf, acc = [line], L
        else:
            buf.append(line); acc += L
    if buf:
        out.append("\n".join(buf))
    # 防止大段无换行：二次硬切
    final = []
    for seg in out:
        if len(seg) <= chunk_chars:
            final.append(seg); continue
        for i in range(0, len(seg), chunk_chars):
            final.append(seg[i:i+chunk_chars])
    return final

def _doc_type_hints(doc_type: str) -> str:
    dt = (doc_type or "TEXT").upper()
    if dt == "DATA":
        return "若出现表头/字段名/单位/指标（如MAU、ARPU、转化率），将其视作术语或实体；结合显著的数值变化提取关键词。"
    if dt == "SLIDES":
        return "标题与要点（bullet points）权重更高；忽略页脚模板、版权、页码。"
    if dt == "PDF":
        return "若文本带有分栏/页眉页脚/参考文献，请忽略这些噪声；优先正文与图表标题。"
    if dt in ("AUDIO","VIDEO"):
        return "去除口头语、寒暄；保留人名/组织名/关键决策/行动项（含动词短语）。"
    return "优先考虑标题/小标题/结论段/列表项中的名词短语；避免空词。"

def _map_reduce_keywords(title: str, body: str, doc_type: str, seeds: str = "", max_len: int = 50) -> dict:
    ai = SETTINGS.get("ai", {}) or {}
    prompts = SETTINGS.get("prompts", {}) or {}
    language = ai.get("language", "zh")
    chunk_chars = int(ai.get("map_chunk_chars", 2000))
    top_n = int(ai.get("reduce_top_n", 16))
    top_pn = int(ai.get("reduce_top_pn", 8))

    if not body:
        return {"title": title, "language": language, "keywords": [], "keyphrases": [], "summary": ""}

    chunks = _split_text(body, chunk_chars)
    map_prompt_tpl = prompts.get("map") or "Extract keywords as JSON from:\n\"\"\"\n{{chunk_text}}\n\"\"\""
    map_results = []

    for idx, ck in enumerate(chunks, 1):
        prompt = (map_prompt_tpl
            .replace("{{filename}}", title or "")
            .replace("{{path}}", "")
            .replace("{{doc_type}}", doc_type or "TEXT")
            .replace("{{language}}", language)
            .replace("{{chunk_text}}", ck)
        )
        # 附加类型提示
        hint = _doc_type_hints(doc_type)
        prompt = prompt.replace("{{doc_type_hints}}", hint)
        try:
            text = _ollama_generate(prompt)
            obj = _json_from_text(text) or {}
        except Exception as e:
            obj = {}
        # 兜底：结构化最少字段
        if "keywords" not in obj:
            obj = {
                "language": language,
                "keywords": [{"term": w.strip(), "weight": 0.5, "type": "主题"} for w in (seeds or title or "").split() if w.strip()],
                "keyphrases": [],
                "summary": ""
            }
        map_results.append(obj)

    reduce_tpl = prompts.get("reduce") or "Merge keyword JSON array:\n{{map_results_json}}"
    reduce_prompt = (reduce_tpl
        .replace("{{top_n}}", str(top_n))
        .replace("{{top_pn}}", str(top_pn))
        .replace("{{map_results_json}}", json.dumps(map_results, ensure_ascii=False))
    )
    try:
        red_text = _ollama_generate(reduce_prompt)
        red_obj = _json_from_text(red_text) or {}
    except Exception:
        red_obj = {}

    # 归一化输出
    kws = red_obj.get("keywords") or []
    # 截断、去重、只保留 term
    seen, flat = set(), []
    for item in kws:
        term = (isinstance(item, dict) and item.get("term")) or (isinstance(item, str) and item) or ""
        term = term.strip()
        if not term or term.lower() in seen:
            continue
        seen.add(term.lower()); flat.append(term)
        if len(flat) >= max_len:  # 这里用 max_len 当作显示预算（词数不是严格等于字符数，但符合你的“关键词列”长度控制诉求）
            break

    return {
        "title": red_obj.get("title") or title or "",
        "language": red_obj.get("language") or language,
        "keywords": kws,                # 完整结构化
        "keyphrases": red_obj.get("keyphrases") or [],
        "summary": red_obj.get("summary") or "",
        "flat_terms": flat              # 逗号拼接用
    }

@bp.post("/update_keywords")
def update_keywords():
    data = request.get_json(silent=True) or {}
    updates = data.get("updates", [])
    STATE.setdefault("keywords", {})
    saved = 0
    for u in updates:
        p = u.get("path")
        kw_raw = u.get("keywords", [])
        if isinstance(kw_raw, str):
            kw_list = [w.strip() for w in re.split(r"[，,;；]", kw_raw) if w.strip()]
        else:
            kw_list = [str(w).strip() for w in kw_raw if str(w).strip()]
        if p and is_under_allowed_roots(p):
            STATE["keywords"][p] = kw_list
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
    seeds_raw = (data.get("seeds") or "").strip()
    strategy = (data.get("strategy") or CFG.get("keywords", {}).get("mode", "hybrid")).lower()
    force_llm = bool(data.get("force_llm"))

    max_chars = int(CFG.get("keywords", {}).get("max_chars", 50))
    lang = (CFG.get("keywords", {}).get("lang", "zh") or "zh")

    ollama_cfg = CFG.get("ollama", {})
    ollama_enable = bool(ollama_cfg.get("enable"))
    ollama_model = ollama_cfg.get("model", "phi3:mini")
    ollama_timeout = int(ollama_cfg.get("timeout_sec", 30))

    out = {}
    STATE.setdefault("keywords", {})

    for p in paths:
        if not is_under_allowed_roots(p):
            continue
        title = Path(p).name
        stem = Path(p).stem.replace("_", " ").replace("-", " ")
        ext = Path(p).suffix.lower().lstrip(".")
        cat = detect_category(ext)

        body = ""
        if cat in ("TEXT", "DATA", "PDF") and extract_text_for_keywords:
            body = extract_text_for_keywords(p, max_chars=3000)

        seeds = seeds_raw.replace("；", ";").replace(",", ";")
        seeds = "，".join([s.strip() for s in seeds.split(";") if s.strip()])

        result_kw = ""

        try:
            if strategy == "fast":
                parts = kw_fast(body, lang=lang, topk=12) if kw_fast else []
                result_kw = compose_keywords(seeds, parts or [stem], max_chars=max_chars)
            elif strategy == "embed":
                base = kw_fast(body, lang=lang, topk=12) if kw_fast else []
                parts = kw_embed(body, base, topk=8) if kw_embed else base
                result_kw = compose_keywords(seeds, parts or [stem], max_chars=max_chars)
            elif strategy == "llm" and ollama_enable and kw_llm:
                result_kw = kw_llm(title, body, seeds, max_chars=max_chars,
                                   model=ollama_model, timeout=ollama_timeout)
                if not result_kw:
                    result_kw = compose_keywords(seeds, [stem], max_chars=max_chars)
            else:
                base = kw_fast(body, lang=lang, topk=12) if kw_fast else []
                parts = kw_embed(body, base, topk=8) if kw_embed else base
                result_kw = compose_keywords(seeds, parts or [stem], max_chars=max_chars)
                if force_llm and ollama_enable and kw_llm:
                    llm_out = kw_llm(title, body, seeds, max_chars=max_chars,
                                     model=ollama_model, timeout=ollama_timeout)
                    if llm_out:
                        result_kw = llm_out
        except Exception:
            result_kw = compose_keywords(seeds, [stem], max_chars=max_chars)

        kw_list = [w.strip() for w in result_kw.split("，") if w.strip()]
        out[p] = kw_list
        STATE["keywords"][p] = kw_list

    save_state()
    return jsonify({"ok": True, "keywords": out})

# -------------------- 图片关键词 --------------------
@bp.post("/keywords_image")
def keywords_image():
    """Generate image keywords using the WD14 plugin."""
    try:
        from plugins.image_keywords_wd14 import ImageKeywordsWD14
    except Exception as e:  # pragma: no cover - plugin import may fail
        return jsonify({"ok": False, "error": f"plugin load failed: {e}"}), 500
    extractor = ImageKeywordsWD14()

    upload = request.files.get("file")
    if upload:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                upload.save(tmp)
                tmp_path = tmp.name
            res = extractor.extract(tmp_path)
            err = res.meta.get("error")
            if err:
                return jsonify({"ok": False, "error": err})
            tags = res.meta.get("tags", [])
            return jsonify({"ok": True, "keywords": tags})
        except Exception as e:  # pragma: no cover - runtime failures
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    out = {}
    for p in paths:
        if not (p and is_under_allowed_roots(p) and os.path.isfile(p)):
            continue
        try:
            res = extractor.extract(p)
            err = res.meta.get("error")
            if err:
                out[p] = {"ok": False, "error": err}
            else:
                out[p] = {"ok": True, "keywords": res.meta.get("tags", [])}
        except Exception as e:
            out[p] = {"ok": False, "error": str(e)}
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

# -------------------- 检索接口 --------------------
@bp.post("/search")
def search():
    """Unified search endpoint.

    The request body follows a subset of the Chroma API with fields such as
    ``query``, ``k``, ``where`` and ``where_document``.
    """

    # Parse request parameters (compatible with Chroma-style JSON)
    p = request.get_json(silent=True) or {}
    collection = p.get("collection", "default")

    # Perform the query using the configured CollectionManager
    res = retriever.query(
        collection,
        [p.get("query", "")],
        k=p.get("k", 10),
        where=p.get("where"),
        where_document=p.get("where_document"),
        search_type=p.get("search_type", "hybrid"),
    )

    hits = {
        "ids": [h["id"] for h in res],
        "documents": [h["document"] for h in res],
        "metadatas": [h["metadata"] for h in res],
        "distances": [1 - float(h.get("score", 0.0)) for h in res],
        "chunks": [h.get("chunk", {}) for h in res],
    }

    return jsonify({"results": hits})


# -------------------- 索引接口 --------------------
@bp.post("/index")
def index_file():
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    if not (path and is_under_allowed_roots(path)):
        return jsonify({"ok": False, "error": "路径不合法"}), 400
    chunks = extract_chunks(path)
    count = index_chunks(chunks, retriever)
    return jsonify({"ok": True, "chunks": count})

# -------------------- 登录/登出 --------------------
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