"""Utility helpers for where / where_document filters.

The implementation is intentionally tiny and supports only the operators
required by the project: ``$and``, ``$or``, ``$in``, ``$gte``, ``$lte``,
``$gt``, ``$lt``, ``$regex`` and ``$contains``.
"""
from __future__ import annotations

import re
from typing import Any, Dict


def _match_expr(value: Any, expr: Any) -> bool:
    """Match a single field against an expression."""

    if isinstance(expr, dict):
        for op, cond in expr.items():
            if op == "$in":
                if value not in cond:
                    return False
            elif op == "$gt":
                if not (value > cond):
                    return False
            elif op == "$gte":
                if not (value >= cond):
                    return False
            elif op == "$lt":
                if not (value < cond):
                    return False
            elif op == "$lte":
                if not (value <= cond):
                    return False
            elif op == "$regex":
                if not re.search(str(cond), str(value)):
                    return False
            elif op == "$contains":
                if str(cond) not in str(value):
                    return False
            else:  # unknown operator
                return False
        return True
    else:
        return value == expr


def match_where(obj: Dict[str, Any], where: Dict[str, Any] | None) -> bool:
    """Return True if ``obj`` satisfies ``where`` expression."""

    if not where:
        return True
    if "$and" in where:
        return all(match_where(obj, w) for w in where["$and"])
    if "$or" in where:
        return any(match_where(obj, w) for w in where["$or"])

    for field, expr in where.items():
        if field.startswith("$"):
            continue
        if not _match_expr(obj.get(field), expr):
            return False
    return True


def match_where_document(text: str, where_doc: Dict[str, Any] | None) -> bool:
    """Evaluate ``where_document`` against text content."""

    if not where_doc:
        return True
    # Reuse ``match_where`` by pretending the text is a field named 'document'.
    return match_where({"document": text}, {"document": where_doc})
