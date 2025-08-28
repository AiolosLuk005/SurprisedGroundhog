"""Toy vector retriever based on token overlap.

This module mimics the interface of a FAISS-backed retriever but does not
require external dependencies.  It computes a simple Jaccard similarity over
word tokens which is sufficient for small demos and unit tests.
"""
from __future__ import annotations

from typing import Dict, Any, Iterable, List

from .retriever import Hit, Retriever
from .filters import build_where, build_where_document


class FaissLocal(Retriever):
    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, Any]] = {}

    def _tokenise(self, text: str) -> set[str]:
        return set(text.split())

    # Retriever interface -------------------------------------------------
    def upsert(self, chunks: Iterable[Dict[str, Any]]) -> int:
        count = 0
        for ch in chunks:
            ch = dict(ch)
            ch["_tokens"] = self._tokenise(ch.get("text", ""))
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
        search_type: str = "vector",
    ) -> List[Hit]:
        if not query_texts:
            return []
        q_tokens = self._tokenise(query_texts[0])
        meta_pred = build_where(where)
        doc_pred = build_where_document(where_document)
        scores = []
        for ch in self._docs.values():
            if not meta_pred(ch.get("metadata", {})):
                continue
            if not doc_pred(ch.get("text", "")):
                continue
            t = ch.get("_tokens", set())
            if not t:
                continue
            score = len(q_tokens & t) / len(q_tokens | t)
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
