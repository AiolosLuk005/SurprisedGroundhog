from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from core.extractors import extract_text_for_keywords
from .normalize_base import NormalizerPlugin, NormalizeResult, REGISTRY

_PLUGINS_READY = False


def discover_normalizers() -> List[str]:
    mod_names: List[str] = []
    base = Path(__file__).resolve().parents[1] / "plugins" / "normalizers"
    if not base.exists():
        return mod_names
    pkg_name = "plugins.normalizers"
    if str(Path(__file__).resolve().parents[1]) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    for info in base.glob("*.py"):
        if info.name == "__init__.py":
            continue
        mod = f"{pkg_name}.{info.stem}"
        try:
            __import__(mod)
            mod_names.append(mod)
        except Exception:
            continue
    return mod_names


def _ensure_plugins() -> None:
    global _PLUGINS_READY
    if not _PLUGINS_READY:
        discover_normalizers()
        _PLUGINS_READY = True


def _calc_fingerprint(p: Path) -> tuple[str, float]:
    sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
    mtime = p.stat().st_mtime
    return sha256, mtime


def normalize_file(path: str, out_root: Path, on_unsupported: str = "fallback") -> NormalizeResult:
    _ensure_plugins()
    p = Path(path)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, str(p.resolve())).hex[:12]
    doc_dir = out_root / doc_id
    sidecar_path = doc_dir / "sidecar.json"

    sha256, mtime = _calc_fingerprint(p)
    if sidecar_path.exists():
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if data.get("sha256") == sha256 and data.get("mtime") == mtime:
                md_paths = [str(x) for x in doc_dir.glob("*.md")]
                csv_paths = [str(x) for x in doc_dir.glob("*.csv")]
                return NormalizeResult(True, doc_id, str(doc_dir), md_paths, csv_paths, str(sidecar_path), "cached")
        except Exception:
            pass

    for plugin in REGISTRY:  # type: NormalizerPlugin
        try:
            if plugin.can_handle(str(p)):
                res = plugin.normalize(str(p), str(doc_dir))
                res.doc_id = doc_id
                res.out_dir = str(doc_dir)
                if res.ok:
                    doc_dir.mkdir(parents=True, exist_ok=True)
                    if not res.sidecar:
                        meta = {
                            "doc_id": doc_id,
                            "source_path": str(p),
                            "ext": p.suffix.lstrip("."),
                            "mtime": mtime,
                            "sha256": sha256,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                        sidecar_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                        res.sidecar = str(sidecar_path)
                return res
        except Exception as e:
            return NormalizeResult(False, doc_id, str(doc_dir), [], [], None, str(e))

    # unsupported
    doc_dir.mkdir(parents=True, exist_ok=True)
    if on_unsupported == "skip":
        return NormalizeResult(False, doc_id, str(doc_dir), [], [], None, "unsupported")
    meta = {
        "doc_id": doc_id,
        "source_path": str(p),
        "ext": p.suffix.lstrip("."),
        "mtime": mtime,
        "sha256": sha256,
        "created_at": datetime.utcnow().isoformat(),
    }
    md_paths: List[str] = []
    csv_paths: List[str] = []
    if on_unsupported == "ledger":
        sidecar_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return NormalizeResult(True, doc_id, str(doc_dir), md_paths, csv_paths, str(sidecar_path), "ledger")
    # fallback
    text = extract_text_for_keywords(str(p))
    md_file = doc_dir / "document.md"
    md_file.write_text(text, encoding="utf-8")
    md_paths = [str(md_file)]
    sidecar_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return NormalizeResult(True, doc_id, str(doc_dir), md_paths, csv_paths, str(sidecar_path), "fallback")
