# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from core.plugin_base import ExtractResult, register
from core.chunking import Chunk

class DocxBasic:
    name = "docx-basic"
    version = "0.1.0"
    priority = 70

    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower() == '.docx'

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        text = ''
        chunks = []
        try:
            from docx import Document
            doc = Document(path)
            parts = []
            for p in doc.paragraphs[:200]:
                if p.text:
                    parts.append(p.text)
                if sum(len(x) for x in parts) >= max_chars:
                    break
            text = "\n".join(parts)[:max_chars]
        except Exception:
            text = ''
        if text:
            chunks.append(
                Chunk(
                    id=f"{path}#0",
                    doc_id=path,
                    text=text,
                    metadata={'handler': self.name},
                )
            )
        return ExtractResult(text=text, meta={'handler': self.name}, chunks=chunks)
    
register(DocxBasic())
