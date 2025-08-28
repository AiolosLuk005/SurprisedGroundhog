"""Very small in-memory keyword matcher.

The implementation is *not* a full BM25 algorithm; it merely counts term
frequency for the supplied query terms.  The goal is to provide a zero
dependency baseline that mirrors the API of a more sophisticated backend.
"""
from __future__ import annotations

import re
from typing import Dict, Any, Iterable, List

from .retriever import Hit, Retriever
from .filters import build_where, build_where_document


class BM25Local(Retriever):
    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, Any]] = {}

    # Retriever interface -------------------------------------------------
    def upsert(self, chunks: Iterable[Dict[str, Any]]) -> int:
        count = 0
        for ch in chunks:
            self._docs[ch["id"]] = ch
            count += 1
        return count

    def delete(self, ids: List[str]) -> int:
        removed = 0
        for i in ids:
            if i in self._docs:
                del self._docs[i]
                removed += 1
        return removed

    def query(
        self,
        query_texts: List[str],
        k: int = 10,
        where: Dict[str, Any] | None = None,
        where_document: Dict[str, Any] | None = None,
        search_type: str = "keyword",
    ) -> List[Hit]:
        if not query_texts:
            return []
        patterns = [re.compile(t, re.IGNORECASE) for t in query_texts[0].split()]
        meta_pred = build_where(where)
        doc_pred = build_where_document(where_document)
        scores = []
        for ch in self._docs.values():
            if not meta_pred(ch.get("metadata", {})):
                continue
            text = ch.get("text", "")
            if not doc_pred(text):
                continue
            score = sum(len(p.findall(text)) for p in patterns)
            if score:
                scores.append((score, ch))
        scores.sort(key=lambda x: x[0], reverse=True)
        hits: List[Hit] = []
        for score, ch in scores[:k]:
            hits.append(
                Hit(
                    id=ch["id"],
                    document=ch.get("text", ""),
                    metadata=ch.get("metadata", {}),
                    score=float(score),
                    chunk=ch.get("chunk", {}),
                )
            )
        return hits
