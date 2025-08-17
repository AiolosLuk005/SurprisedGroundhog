# -*- coding: utf-8 -*-
"""Fallback extractor for legacy support.
All actual implementations are migrated to plugins.
This file remains only to keep import paths valid."""

def extract_text_for_keywords(path: str, max_chars: int = 4000) -> str:
    return ""  # always return empty; real work is in plugins
