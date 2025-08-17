# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Protocol, Any

class ExtractResult(dict):
    pass

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
