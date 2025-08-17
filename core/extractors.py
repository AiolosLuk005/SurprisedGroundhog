# -*- coding: utf-8 -*-
"""Fallback-only extractor.

This module intentionally contains *minimal* logic.
All real extractors live in `plugins/` and are loaded via `core.extractors_patch`.
If no plugin handles a file, we fall back to a very safe, empty-string response
instead of raising, to keep API stable.
"""
from pathlib import Path

def extract_text_for_keywords(path: str, max_chars: int = 4000) -> str:
    # Conservative fallback: read plain text only, others -> empty.
    try:
        if Path(path).suffix.lower().lstrip('.') in {'txt','md','rtf','log','json','yaml','yml'}:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(max_chars)
    except Exception:
        pass
    return ""
