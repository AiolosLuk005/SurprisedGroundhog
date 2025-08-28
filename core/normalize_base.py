from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass
class NormalizeResult:
    ok: bool
    doc_id: str = ""
    out_dir: str = ""
    md_paths: Sequence[str] | None = None
    csv_paths: Sequence[str] | None = None
    sidecar: str | None = None
    message: str | None = None


class NormalizerPlugin(Protocol):
    name: str
    priority: int
    exts: Sequence[str]

    def can_handle(self, path: str) -> bool: ...

    def normalize(self, path: str, out_root: str) -> NormalizeResult: ...


REGISTRY: list[NormalizerPlugin] = []


def register(plugin: NormalizerPlugin) -> None:
    REGISTRY.append(plugin)
    REGISTRY.sort(key=lambda p: p.priority, reverse=True)
