# -*- coding: utf-8 -*-
from __future__ import annotations
from core.plugin_base import ExtractResult, register
from core.chunking import Chunk

class PdfBasic:
    name = "pdf-basic"
    version = "0.1.0"
    priority = 60

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith('.pdf')

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        text = ''
        chunks = []
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            for idx, page in enumerate(reader.pages[:30], 1):
                try:
                    ptxt = (page.extract_text() or '')
                except Exception:
                    ptxt = ''
                if ptxt:
                    ptxt = ptxt[:max_chars]
                    chunks.append(
                        Chunk(
                            id=f"{path}#p{idx}",
                            doc_id=path,
                            text=ptxt,
                            page=idx,
                            metadata={'handler': self.name},
                        )
                    )
                    text += ptxt + "\n"
                    if len(text) >= max_chars:
                        break
            text = text[:max_chars]
            pages_scanned = min(len(getattr(reader,'pages',[])), 30)
        except Exception:
            text = ''
            pages_scanned = 0
        return ExtractResult(text=text, meta={'pages_scanned': pages_scanned, 'handler': self.name}, chunks=chunks)

register(PdfBasic())
