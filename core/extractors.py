# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Extractor orchestrator with safe fallback.

对外只暴露一个函数：
    extract_text_for_keywords(path: str, max_chars: int = 4000) -> str

流程：
1) 发现并加载 plugins/ 下的 ExtractorPlugin；
2) 命中 plugin.can_handle(path) 则 plugin.extract()；
3) 否则回退到只读纯文本的兜底逻辑。

注意：不要在本文件最前面放任何其他 import/代码，
以保证 `from __future__ import annotations` 位于文件开头。
"""

from pathlib import Path
from typing import Iterable

from core.plugin_loader import discover_plugins, get_plugins
from core.plugin_base import ExtractorPlugin

# ---------------- internal state ----------------
_PLUGINS_READY = False

def _ensure_plugins() -> None:
    """首次调用时发现并加载插件；重复调用无副作用。"""
    global _PLUGINS_READY
    if not _PLUGINS_READY:
        try:
            discover_plugins()
        finally:
            _PLUGINS_READY = True

# ---------------- fallback (safe & minimal) ----------------
_TEXT_EXTS: set[str] = {"txt","md","rtf","log","json","yaml","yml"}

def _fallback_extract_text(path: str, max_chars: int = 4000) -> str:
    """只对纯文本扩展名做前 max_chars 字符读取，其它返回空串。"""
    try:
        ext = Path(path).suffix.lower().lstrip(".")
        if ext in _TEXT_EXTS:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
    except Exception:
        pass
    return ""

# ---------------- public API ----------------
def extract_text_for_keywords(path: str, max_chars: int = 4000) -> str:
    """优先插件，失败则兜底。始终返回字符串。"""
    p = Path(path)
    _ensure_plugins()

    # 1) 插件优先
    try:
        for plugin in get_plugins():  # type: Iterable[ExtractorPlugin]
            try:
                if plugin.can_handle(str(p)):
                    res = plugin.extract(str(p), max_chars=max_chars) or {}
                    txt = (res.get("text") or "")
                    if txt:
                        return txt[:max_chars]
            except Exception:
                # 单个插件失败不影响整体
                continue
    except Exception:
        pass

    # 2) 兜底
    try:
        return _fallback_extract_text(str(p), max_chars=max_chars)
    except Exception:
        return ""

__all__ = ["extract_text_for_keywords"]
