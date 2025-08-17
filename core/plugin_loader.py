# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib, pkgutil, sys
from pathlib import Path
from typing import List
from .plugin_base import REGISTRY

def discover_plugins(plugins_dir: str | None = None) -> List[str]:
    mod_names = []
    base = Path(plugins_dir or Path(__file__).resolve().parents[1] / "plugins")
    if not base.exists():
        return mod_names
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    pkg_name = "plugins"
    for _, name, _ in pkgutil.iter_modules([str(base)]):
        full = f"{pkg_name}.{name}"
        try:
            importlib.import_module(full)
            mod_names.append(full)
        except Exception as e:
            print(f"[plugin_loader] Failed to load {full}: {e}")
    return mod_names

def get_plugins():
    return list(REGISTRY)
