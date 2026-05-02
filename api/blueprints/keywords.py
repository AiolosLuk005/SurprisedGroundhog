from flask import Blueprint, request, jsonify
from pathlib import Path
import re
import tempfile
import os
import logging

from core.utils.iterfiles import is_under_allowed_roots, detect_category
from core.state import STATE, save_state
from core.settings import SETTINGS
from core.config import CFG
from services.ai_keywords import AIKeywordService
from services.image_keywords_ollama import OllamaImageKeywordService

# Optional dependency (legacy WD14 plugin, kept for fallback)
try:
    from plugins.image_keywords_wd14 import ImageKeywordsWD14
except ImportError:
    ImageKeywordsWD14 = None

bp = Blueprint("keywords", __name__)
logger = logging.getLogger(__name__)

# Instantiate service once
ai_service = AIKeywordService()

def _compose_keywords(seeds: str, parts: list, max_chars: int = 50) -> str:
    # Helper to format output string
    s = ", ".join(parts)
    if seeds:
        seed_list = [w.strip() for w in re.split(r"[,;，；]", seeds) if w.strip()]
        # Remove dups from s
        existing = set(seed_list)
        rest = [p for p in parts if p not in existing]
        s = ", ".join(seed_list + rest)
    
    s = s.replace(",", "，").replace(";", "，") # unify
    return s[:max_chars]

@bp.post("/keywords")
def gen_keywords():
    if not SETTINGS.get("features", {}).get("enable_ai_keywords", True):
        return jsonify({"ok": False, "error": "关键词功能已禁用"}), 403

    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    seeds_raw = (data.get("seeds") or "").strip()
    strategy = (data.get("strategy") or "hybrid").lower()
    force_llm = bool(data.get("force_llm"))
    max_chars = int(data.get("max_chars") or CFG.get("keywords", {}).get("max_chars", 50))
    
    # We simplified the service to `map_reduce_keywords`.
    # For now, if strategy is 'llm' or 'hybrid'+force_llm, we use the service.
    # Legacy 'fast'/'embed' support is currently minimal in the service 
    # (can be added later or we rely on the service's own heuristics).
    
    from core.extractors import extract_text_for_keywords
    
    out = {}
    STATE.setdefault("keywords", {})
    
    for p in paths:
        if not is_under_allowed_roots(p):
            continue
            
        try:
            # 1. Extract text
            body = extract_text_for_keywords(p, max_chars=3000)
            
            # 2. Generate
            # If simplistic fast mode is requested, we might just skip AI service call 
            # to save tokens/time if we had a local jieba implementation.
            # For this refactor, we route complex requests to AI Service.
            
            title = Path(p).name
            cat = detect_category(Path(p).suffix.lower().lstrip("."))
            
            # Simple wrapper to use the service
            # In a full impl, we'd pass strategy to service or have different methods
            res_dict = ai_service.map_reduce_keywords(title, body, cat, seeds=seeds_raw, max_len=max_chars)
            
            kw_list = res_dict.get("keywords", [])
            # If the service returns objects, flatten them
            flat_kws = []
            for k in kw_list:
                if isinstance(k, dict): flat_kws.append(k.get("term", ""))
                elif isinstance(k, str): flat_kws.append(k)
            
            # Fallback to just seeds if empty
            if not flat_kws and seeds_raw:
                 flat_kws = [s.strip() for s in re.split(r"[,;，；]", seeds_raw) if s.strip()]

            out[p] = flat_kws
            STATE["keywords"][p] = flat_kws
            
        except Exception as e:
            logger.error(f"Keyword gen failed for {p}: {e}")
            out[p] = []

    save_state()
    return jsonify({"ok": True, "keywords": out})

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


@bp.post("/keywords_image")
def keywords_image():
    """Generate image keywords using Ollama vision model (qwen3-vl:8b)."""
    logger.info("/keywords_image called")
    
    # Use Ollama vision model as primary extractor
    use_ollama = SETTINGS.get("features", {}).get("use_ollama_vision", True)
    
    if use_ollama:
        extractor = OllamaImageKeywordService()
        logger.info(f"Using Ollama vision model: {extractor.model}")
    elif ImageKeywordsWD14:
        extractor = ImageKeywordsWD14()
        logger.info("Using WD14 plugin (fallback)")
    else:
        return jsonify({"ok": False, "error": "No image keyword extractor available"}), 500
    
    # Handle file upload
    upload = request.files.get("file")
    if upload:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                upload.save(tmp)
                tmp_path = tmp.name
            logger.debug("Uploaded file saved to %s", tmp_path)
            res = extractor.extract(tmp_path)
            meta = res.get("meta", {})
            err = meta.get("error")
            if err:
                logger.error("Extraction error for %s: %s", tmp_path, err)
                return jsonify({"ok": False, "error": err})
            tags = meta.get("tags", [])
            logger.info("Extracted %d tags for uploaded file", len(tags))
            return jsonify({"ok": True, "keywords": tags})
        except Exception as e:
            logger.error("Runtime failure for uploaded file: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    
    # Handle path-based extraction
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    logger.debug("Processing paths: %s", paths)
    out = {}
    for p in paths:
        if not (p and is_under_allowed_roots(p) and os.path.isfile(p)):
            continue
        try:
            res = extractor.extract(p)
            meta = res.get("meta", {})
            err = meta.get("error")
            if err:
                logger.error("Extraction error for %s: %s", p, err)
                out[p] = {"ok": False, "error": err}
            else:
                tags = meta.get("tags", [])
                logger.info("Extracted %d tags for %s", len(tags), p)
                out[p] = {"ok": True, "keywords": tags}
        except Exception as e:
            logger.error("Runtime failure for %s: %s", p, e)
            out[p] = {"ok": False, "error": str(e)}
    return jsonify({"ok": True, "keywords": out})

