# -*- coding: utf-8 -*-
from __future__ import annotations
"""Utilities and data structures for chunk based indexing."""

from dataclasses import dataclass, field
from typing import Dict, Any, Iterable, Tuple, List
import json


@dataclass
class Chunk:
    """Lightweight chunk representation.

    Parameters
    ----------
    id: str
        Unique identifier for the chunk.
    doc_id: str
        Identifier of the source document.
    text: str
        Raw text content of this chunk.
    page: int | None, optional
        Page number if applicable (1-indexed).
    section_path: Tuple[str, ...], optional
        Hierarchical section path within the document.
    span: Tuple[int, int] | None, optional
        Character span within the original document.
    metadata: Dict[str, Any]
        Additional plugin specific metadata.
    """

    id: str
    doc_id: str
    text: str
    page: int | None = None
    section_path: Tuple[str, ...] = ()
    span: Tuple[int, int] | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise chunk to a plain dictionary."""
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "text": self.text,
            "page": self.page,
            "section_path": list(self.section_path),
            "span": list(self.span) if self.span else None,
            "metadata": self.metadata,
        }

    def to_retriever_dict(self) -> Dict[str, Any]:
        """Return structure compatible with Retriever.upsert."""
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
            "chunk": self.to_dict(),
        }


def persist_chunks(
    chunks: Iterable[Chunk],
    chunks_path: str = "chunks.parquet",
    vec_index_path: str = "vec.index",
) -> None:
    """Persist chunks and vector data to disk.

    ``chunks_path`` stores a table of chunk metadata while ``vec_index_path``
    keeps a minimal vector index mapping chunk id to the stored embedding.
    Both operations are best-effort; if optional dependencies such as
    ``pandas`` are missing the function silently falls back to JSON lines.
    """

    chunk_list = list(chunks)

    # -------- chunks.parquet --------
    rows = [ch.to_dict() for ch in chunk_list]
    try:  # Try Parquet via pandas
        import pandas as pd  # type: ignore

        df = pd.DataFrame(rows)
        df.to_parquet(chunks_path, index=False)
    except Exception:
        # Fallback to JSON lines
        with open(chunks_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # -------- vec.index --------
    vectors = {
        ch.id: ch.metadata.get("clip_vector")
        for ch in chunk_list
        if ch.metadata.get("clip_vector") is not None
    }
    if vectors:
        with open(vec_index_path, "w", encoding="utf-8") as f:
            json.dump(vectors, f)


def index_chunks(
    chunks: Iterable[Chunk],
    retriever=None,
    chunks_path: str = "chunks.parquet",
    vec_index_path: str = "vec.index",
) -> int:
    """Upsert chunks into the retriever and persist to disk.

    Parameters
    ----------
    chunks:
        Iterable of :class:`Chunk` objects.
    retriever:
        Optional retrieval backend implementing ``upsert``.
    chunks_path, vec_index_path:
        Destination files for persisted data.

    Returns
    -------
    int
        Number of processed chunks.
    """

    chunk_list = list(chunks)
    if retriever is not None:
        retriever.upsert([ch.to_retriever_dict() for ch in chunk_list])
    persist_chunks(chunk_list, chunks_path, vec_index_path)
    return len(chunk_list)


__all__ = ["Chunk", "persist_chunks", "index_chunks"]
