"""Very small in-memory keyword matcher.

The implementation is *not* a full BM25 algorithm; it merely counts term
frequency for the supplied query terms.  The goal is to provide a zero
dependency baseline that mirrors the API of a more sophisticated backend.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Any, Iterable, List

from .retriever import Hit, Retriever
from .filters import match_where, match_where_document


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
        terms = query_texts[0].split()
        scores = []
        for ch in self._docs.values():
            if not match_where(ch.get("metadata", {}), where):
                continue
            if not match_where_document(ch.get("text", ""), where_document):
                continue
            cnt = Counter(ch.get("text", "").split())
            score = sum(cnt[t] for t in terms)
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
