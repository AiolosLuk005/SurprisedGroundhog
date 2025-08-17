# -*- coding: utf-8 -*-
from __future__ import annotations
from core.plugin_base import ExtractResult, register

class PdfBasic:
    name = "pdf-basic"
    version = "0.1.0"
    priority = 60

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith('.pdf')

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        text = ''
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            for page in reader.pages[:30]:
                try:
                    text += (page.extract_text() or '') + "\n"
                    if len(text) >= max_chars:
                        break
                except Exception:
                    continue
            text = text[:max_chars]
            pages_scanned = min(len(getattr(reader,'pages',[])), 30)
        except Exception:
            text = ''
            pages_scanned = 0
        return ExtractResult(text=text, meta={'pages_scanned': pages_scanned, 'handler': self.name})

register(PdfBasic())
