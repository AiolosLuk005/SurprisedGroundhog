# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from core.plugin_base import ExtractResult, register
from core.chunking import Chunk

class ArchiveKeywords:
    name = "archive-keywords"
    version = "0.1.0"
    priority = 80

    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower() in {'.zip','.rar','.7z'}

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        p = Path(path)
        ext = p.suffix.lower()
        words = set()

        def add_parts(name: str):
            base = name.rsplit('.',1)[0]
            for tok in base.replace('-', ' ').replace('_', ' ').split():
                if tok and tok.isascii():
                    words.add(tok.lower())

        try:
            if ext == '.zip':
                import zipfile
                with zipfile.ZipFile(p, 'r') as zf:
                    for info in zf.infolist()[:250]:
                        add_parts(info.filename)
            elif ext == '.rar':
                try:
                    import rarfile
                except Exception:
                    rarfile = None
                if rarfile:
                    with rarfile.RarFile(p, 'r') as rf:
                        for info in rf.infolist()[:250]:
                            add_parts(info.filename)
            elif ext == '.7z':
                try:
                    import py7zr
                except Exception:
                    py7zr = None
                if py7zr:
                    with py7zr.SevenZipFile(p, 'r') as z:
                        for name in z.getnames()[:250]:
                            add_parts(name)
        except Exception:
            pass

        txt = ' '.join(sorted(words))[:max_chars]
        chunk = Chunk(
            id=f"{path}#0",
            doc_id=path,
            text=txt,
            metadata={'handler': self.name, 'unique_tokens': len(words)},
        )
        return ExtractResult(text=txt, meta={'handler': self.name, 'unique_tokens': len(words)}, chunks=[chunk])
    
register(ArchiveKeywords())
