# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from core.plugin_loader import discover_plugins, get_plugins
from core.plugin_base import ExtractorPlugin
from core import extractors as builtins

_plugins_loaded = False

def _ensure_plugins():
    global _plugins_loaded
    if not _plugins_loaded:
        discover_plugins()
        _plugins_loaded = True

def extract_text_for_keywords(path: str, max_chars: int = 4000) -> str:
    _ensure_plugins()
    p = Path(path)
    for plugin in get_plugins():
        try:
            if plugin.can_handle(str(p)):
                res = plugin.extract(str(p), max_chars=max_chars)
                txt = res.get('text','')
                if txt:
                    return txt[:max_chars]
        except Exception:
            continue
    # fallback
    try:
        return builtins.extract_text_for_keywords(str(p), max_chars=max_chars)
    except Exception:
        return ""
