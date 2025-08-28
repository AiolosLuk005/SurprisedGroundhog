from __future__ import annotations
"""Evaluate retrieval quality against internal QA pairs.

This script expects two JSONL files:

1. A collection of chunks to index, each line containing at least ``id`` and
   ``text`` fields.  Use ``--collection`` to point at this file.
2. A file of evaluation questions with a list of relevant ``answer_ids``.
   Use ``--pairs`` to point at this file.  Example line::

       {"question": "...", "answer_ids": ["doc-1", "doc-2"]}

The script builds an in-memory :class:`HybridRetriever` from the collection and
computes Recall@k and MRR for the questions.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Dict, Any, List

# allow running as a stand-alone script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.retrieval import HybridRetriever


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield dictionaries from a JSONL file."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval metrics")
    parser.add_argument(
        "--collection", required=True, type=Path, help="JSONL file of chunks to index"
    )
    parser.add_argument(
        "--pairs", required=True, type=Path, help="JSONL file of question/answer ids"
    )
    parser.add_argument("--k", type=int, default=5, help="Top k hits to consider")
    args = parser.parse_args()

    retriever = HybridRetriever()
    for ch in load_jsonl(args.collection):
        retriever.upsert([ch])

    total = 0
    recall = 0.0
    mrr = 0.0

    for qa in load_jsonl(args.pairs):
        q = qa.get("question", "")
        rel_ids: List[str] = qa.get("answer_ids") or []
        if not q or not rel_ids:
            continue
        hits = retriever.query([q], k=args.k)
        hit_ids = [h["id"] for h in hits]
        # recall@k
        retrieved = sum(1 for i in rel_ids if i in hit_ids)
        recall += retrieved / len(rel_ids)
        # mrr
        rr = 0.0
        for rank, hid in enumerate(hit_ids, 1):
            if hid in rel_ids:
                rr = 1.0 / rank
                break
        mrr += rr
        total += 1

    if total:
        print(f"Recall@{args.k}: {recall / total:.4f}")
        print(f"MRR@{args.k}: {mrr / total:.4f}")
    else:
        print("No valid QA pairs found.")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
