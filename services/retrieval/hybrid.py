"""Hybrid retrieval combining simple vector and keyword search."""
from __future__ import annotations

from pathlib import Path
import tarfile
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


def snapshot(collection_name: str, base_dir: str = "collections", out_dir: str = "snapshots") -> Path:
    """Compress collection files into a snapshot archive.

    The function looks for ``*.parquet`` files, any ``*.index`` files and a
    ``meta.json`` under ``base_dir/collection_name``.  Found files are packed
    into ``out_dir/collection_name.tar.gz`` and the resulting path is returned.
    """

    src = Path(base_dir) / collection_name
    if not src.is_dir():
        raise FileNotFoundError(f"collection directory not found: {src}")

    files = list(src.glob("*.parquet"))
    files += list(src.glob("*.index"))
    meta = src / "meta.json"
    if meta.exists():
        files.append(meta)
    if not files:
        raise FileNotFoundError(f"no snapshotable files in {src}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"{collection_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for f in files:
            tar.add(f, arcname=f.name)
    return archive


def _cli() -> None:  # pragma: no cover - convenience CLI
    import argparse

    p = argparse.ArgumentParser(description="Utility helpers for retrieval")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("snapshot", help="Create snapshot for a collection")
    sp.add_argument("collection_name")
    sp.add_argument("--base-dir", default="collections")
    sp.add_argument("--out-dir", default="snapshots")
    args = p.parse_args()

    if args.cmd == "snapshot":
        path = snapshot(args.collection_name, args.base_dir, args.out_dir)
        print(path)
    else:
        p.print_help()


if __name__ == "__main__":
    _cli()
