# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Protocol, Any, List

from core.chunking import Chunk

class ExtractResult(dict):
    """Plugin extraction result following the ``Chunk`` spec.

    Plugins should populate ``text`` with the raw concatenated text, ``meta``
    with any plugin specific metadata and, most importantly, ``chunks`` which
    is a list of :class:`core.chunking.Chunk` objects.
    """

    text: str
    meta: dict
    chunks: List[Chunk]

class ExtractorPlugin(Protocol):
    name: str
    version: str
    priority: int
    def can_handle(self, path: str) -> bool: ...
    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult: ...

REGISTRY: list[ExtractorPlugin] = []

def register(plugin: ExtractorPlugin) -> None:
    REGISTRY.append(plugin)
    REGISTRY.sort(key=lambda p: p.priority, reverse=True)
