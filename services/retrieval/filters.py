"""Utility helpers for where / where_document filters.

The implementation is intentionally tiny and supports only the operators
required by the project: ``$and``, ``$or``, ``$in``, ``$gte``, ``$lte``,
``$gt``, ``$lt``, ``$regex`` and ``$contains``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Callable


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
    return value == expr


def _build(where: Dict[str, Any] | None) -> Callable[[Dict[str, Any]], bool]:
    """Compile a ``where`` expression into a predicate function."""

    if not where:
        return lambda obj: True

    if "$and" in where:
        preds = [_build(w) for w in where["$and"]]
        return lambda obj: all(p(obj) for p in preds)

    if "$or" in where:
        preds = [_build(w) for w in where["$or"]]
        return lambda obj: any(p(obj) for p in preds)

    tests = []
    for field, expr in where.items():
        if field.startswith("$"):
            continue

        def test(obj: Dict[str, Any], field=field, expr=expr) -> bool:
            return _match_expr(obj.get(field), expr)

        tests.append(test)

    return lambda obj: all(t(obj) for t in tests)


def build_where(where: Dict[str, Any] | None) -> Callable[[Dict[str, Any]], bool]:
    """Return predicate checking a metadata dictionary against ``where``."""

    return _build(where)


def match_where(obj: Dict[str, Any], where: Dict[str, Any] | None) -> bool:
    """Immediate evaluation helper for ``where`` expressions."""

    return build_where(where)(obj)


def build_where_document(where_doc: Dict[str, Any] | None) -> Callable[[str], bool]:
    """Return predicate evaluating ``where_document`` against text."""

    if not where_doc:
        return lambda text: True

    doc_pred = build_where({"document": where_doc})
    return lambda text: doc_pred({"document": text})


def match_where_document(text: str, where_doc: Dict[str, Any] | None) -> bool:
    """Immediate evaluation helper for ``where_document`` expressions."""

    return build_where_document(where_doc)(text)

