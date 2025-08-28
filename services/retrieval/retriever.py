"""Abstract retrieval interface.

The real implementation is intentionally lightweight.  All data is kept in
memory and the public interface follows a subset of the Chroma VectorStore
API so that future backends can drop in with minimal changes.
"""
from __future__ import annotations

from typing import Protocol, TypedDict, Iterable, List, Dict, Any


class Hit(TypedDict):
    """Standardised return structure for search results."""

    id: str
    document: str
    metadata: Dict[str, Any]
    score: float
    chunk: Dict[str, Any]


class Retriever(Protocol):
    """Protocol implemented by all retriever backends."""

    def upsert(self, chunks: Iterable[Dict[str, Any]]) -> int:
        """Insert or update chunks.

        Parameters
        ----------
        chunks:
            Iterable of dictionaries containing at least ``id`` and ``text``
            keys.  Additional fields are stored as metadata.

        Returns
        -------
        int
            Number of processed chunks.
        """

        ...

    def delete(self, ids: List[str]) -> int:
        """Remove chunks by id.

        Parameters
        ----------
        ids:
            Identifiers to remove.

        Returns
        -------
        int
            Number of removed chunks.
        """

        ...

    def query(
        self,
        query_texts: List[str],
        k: int = 10,
        where: Dict[str, Any] | None = None,
        where_document: Dict[str, Any] | None = None,
        search_type: str = "hybrid",
    ) -> List[Hit]:
        """Query the index.

        Parameters mirror the Chroma API.  The default implementation
        returns an empty list so that callers can gracefully degrade when a
        more sophisticated backend is not available.
        """

        ...
