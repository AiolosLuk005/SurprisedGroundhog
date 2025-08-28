import os, hashlib, re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from dateutil.tz import tzlocal
from core.config import ALLOWED_ROOTS
from core.models import CATEGORIES, FileRow

def is_under_allowed_roots(path: str) -> bool:
    try:
        p = str(Path(path).resolve())
        for root in ALLOWED_ROOTS:
            if Path(p).is_relative_to(root):
                return True
    except Exception:
        p = os.path.abspath(path)
        for root in ALLOWED_ROOTS:
            if os.path.commonpath([p, os.path.abspath(root)]) == os.path.abspath(root):
                return True
    return False

def detect_category(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    for cat, exts in CATEGORIES.items():
        if e in exts:
            return cat
    return "TEXT"

def iter_files(scan_dir: str, with_hash: bool, cat: Optional[str], types: Optional[list[str]], recursive: bool=True) -> Iterable[FileRow]:
    tz = tzlocal()
    allowed_types = set([t.lower() for t in types]) if types else None

    if recursive:
        walker = os.walk(scan_dir)
        for root, _, files in walker:
            for fn in files:
                yield from _yield_row(root, fn, with_hash, cat, allowed_types, tz)
    else:
        try:
            for fn in os.listdir(scan_dir):
                full = os.path.join(scan_dir, fn)
                if os.path.isfile(full):
                    yield from _yield_row(scan_dir, fn, with_hash, cat, allowed_types, tz)
        except Exception:
            return

def _yield_row(root, fn, with_hash, cat, allowed_types, tz):
    full = os.path.join(root, fn)
    try:
        st = os.stat(full)
        name, ext = os.path.splitext(fn)
        ext = (ext or "").lower().lstrip(".")
        detected = detect_category(ext)
        if cat and detected != cat:
            return
        if allowed_types and ext not in allowed_types:
            return
        mtime = datetime.fromtimestamp(st.st_mtime, tz).isoformat(timespec="seconds")
        sha256 = None
        if with_hash:
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            sha256 = h.hexdigest()
        from core.state import STATE
        kw = STATE.get("keywords", {}).get(full)
        if isinstance(kw, str):
            kw = [w.strip() for w in re.split(r"[，,;；]", kw) if w.strip()]
        previewable = detected in ("IMAGE","VIDEO","AUDIO")
        yield FileRow(
            full_path=full, dir_path=root, name=name, ext=ext, category=detected,
            size_bytes=st.st_size, mtime_iso=mtime, sha256=sha256, keywords=kw, previewable=previewable
        )
    except (PermissionError, FileNotFoundError, OSError):
        return
