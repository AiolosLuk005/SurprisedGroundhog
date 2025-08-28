"""Hybrid retrieval combining simple vector and keyword search."""
from __future__ import annotations

from typing import Dict, Any, Iterable, List

from .retriever import Hit, Retriever
from .faiss_local import FaissLocal
from .bm25_local import BM25Local


class HybridRetriever(Retriever):
    def __init__(self) -> None:
        self.vector = FaissLocal()
        self.keyword = BM25Local()

    def upsert(self, chunks: Iterable[Dict[str, Any]]) -> int:
        data = list(chunks)
        self.vector.upsert(data)
        self.keyword.upsert(data)
        return len(data)

    def delete(self, ids: List[str]) -> int:
        removed_vec = self.vector.delete(ids)
        removed_kw = self.keyword.delete(ids)
        return max(removed_vec, removed_kw)

    def query(
        self,
        query_texts: List[str],
        k: int = 10,
        where: Dict[str, Any] | None = None,
        where_document: Dict[str, Any] | None = None,
        search_type: str = "hybrid",
    ) -> List[Hit]:
        if search_type == "vector":
            return self.vector.query(query_texts, k, where, where_document)
        if search_type == "keyword":
            return self.keyword.query(query_texts, k, where, where_document)

        hits: Dict[str, Hit] = {}
        for h in self.vector.query(query_texts, k, where, where_document):
            hits[h["id"]] = h
        for h in self.keyword.query(query_texts, k, where, where_document):
            if h["id"] in hits:
                # favour higher score, keep combined metadata
                hits[h["id"]]["score"] = max(hits[h["id"]]["score"], h["score"])
            else:
                hits[h["id"]] = h
        return sorted(hits.values(), key=lambda x: x["score"], reverse=True)[:k]
