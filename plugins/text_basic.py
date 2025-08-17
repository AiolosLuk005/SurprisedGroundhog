# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from core.plugin_base import ExtractResult, register

class TextBasic:
    name = "text-basic"
    version = "0.1.0"
    priority = 50

    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower().lstrip('.') in {'txt','md','rtf','log','json','yaml','yml'}

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                txt = f.read(max_chars)
        except Exception:
            txt = ''
        return ExtractResult(text=txt, meta={'handler': self.name})

register(TextBasic())
