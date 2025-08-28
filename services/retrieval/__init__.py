"""Lightweight retrieval service layer.

This package provides a minimal local implementation of a hybrid search
pipeline inspired by the Chroma API.  It is intentionally small and keeps
all data in memory so that the surrounding application can evolve without a
heavy dependency footprint.
"""

from .hybrid import HybridRetriever

__all__ = ["HybridRetriever"]
