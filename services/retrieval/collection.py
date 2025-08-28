from __future__ import annotations

"""Utilities for managing multiple retrieval collections.

This module reads the ``collections`` configuration from
``config/settings.json`` and exposes a :class:`CollectionManager` that
creates individual :class:`~services.retrieval.hybrid.HybridRetriever`
instances per collection.  It also provides snapshot export and rollback
helpers which operate on the on-disk structure::

    data/collections/<name>/
        chunks.parquet
        vec.index
        idmap.parquet
        snapshots/

The storage files are only placeholders in this lightweight
implementation but the functions mirror how a real backend would manage
on-disk indices.
"""

from pathlib import Path
from typing import Dict, Any, Iterable, List
import datetime as _dt
import zipfile

from .hybrid import HybridRetriever
from .retriever import Hit
from core.settings import SETTINGS


class CollectionManager:
    """Manage retrievers for configured collections."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        cfg = config or SETTINGS
        self.paths: Dict[str, Path] = {
            name: Path(path) for name, path in cfg.get("collections", {}).items()
        }
        self._retrievers: Dict[str, HybridRetriever] = {}

    # ------------------------------------------------------------------
    def _ensure_collection(self, name: str) -> HybridRetriever:
        if name not in self._retrievers:
            self.paths.setdefault(name, Path(f"data/collections/{name}"))
            self._retrievers[name] = HybridRetriever()
        return self._retrievers[name]

    # Public API -------------------------------------------------------
    def upsert(self, collection: str, chunks: Iterable[Dict[str, Any]]) -> int:
        """Insert chunks into the specified collection."""
        retriever = self._ensure_collection(collection)
        return retriever.upsert(chunks)

    def query(
        self,
        collection: str,
        query_texts: List[str],
        k: int = 10,
        where: Dict[str, Any] | None = None,
        where_document: Dict[str, Any] | None = None,
        search_type: str = "hybrid",
    ) -> List[Hit]:
        """Query the specified collection."""
        retriever = self._ensure_collection(collection)
        return retriever.query(query_texts, k, where, where_document, search_type)

    # Snapshot helpers -------------------------------------------------
    def export_snapshot(self, collection: str, name: str | None = None) -> Path:
        """Create a zip snapshot of the collection's index files."""
        base = self.paths.get(collection, Path(f"data/collections/{collection}"))
        base.mkdir(parents=True, exist_ok=True)
        snap_dir = base / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        if not name:
            name = _dt.datetime.now().strftime("%Y%m%d%H%M%S") + ".zip"
        out = snap_dir / name
        with zipfile.ZipFile(out, "w") as zf:
            for fname in ["chunks.parquet", "vec.index", "idmap.parquet"]:
                p = base / fname
                if p.exists():
                    zf.write(p, arcname=fname)
        return out

    def rollback_snapshot(self, collection: str, snapshot_file: str | Path) -> None:
        """Restore index files from a snapshot zip."""
        base = self.paths.get(collection, Path(f"data/collections/{collection}"))
        with zipfile.ZipFile(snapshot_file, "r") as zf:
            zf.extractall(base)
