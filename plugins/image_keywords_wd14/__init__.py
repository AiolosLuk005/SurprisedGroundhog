# -*- coding: utf-8 -*-
"""WD14 based image keyword extractor.

This plugin loads the WD14 tagger ONNX model and produces comma separated
keywords for images. Model paths and thresholds are configured via
``config/settings.toml``. A manifest file (``config/wd14_manifest.json``)
is checked before model loading to ensure files are present and intact.

Only a very small subset of the original wd14 tagger features are
implemented here but the structure mirrors the external workflow so the
project can be extended easily on a real installation.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - tomli fallback
    import tomli as tomllib  # type: ignore

from PIL import Image

from core.plugin_base import ExtractResult, register
from core.chunking import Chunk


class ImageKeywordsWD14:
    name = "image-keywords-wd14"
    version = "0.1.0"
    priority = 60

    _EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

    def __init__(self) -> None:
        self._cfg = self._load_cfg()
        self._blacklist = self._load_blacklist()
        self._dict = self._load_dict()
        self._session = None
        self._general_tags: List[str] = []
        self._char_tags: List[str] = []
        self._manifest_error: str | None = None

        man_cfg = self._cfg.get("manifest", {})
        if man_cfg.get("enforce_integrity"):
            try:
                self._verify_manifest(Path(man_cfg.get("file", "")))
            except Exception as e:  # store error but do not crash import
                self._manifest_error = str(e)

    # ------------------------------------------------------------------
    def _load_cfg(self) -> dict:
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "settings.toml"
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                return tomllib.load(f).get("wd14", {})
        return {}

    def _load_blacklist(self) -> set[str]:
        path = Path(__file__).with_name("blacklist.txt")
        if path.exists():
            return {
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        return set()

    def _load_dict(self) -> dict:
        path = Path(__file__).with_name("zh_dictionary.json")
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _verify_manifest(self, manifest_path: Path) -> None:
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {manifest_path}")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        for f in data.get("files", []):
            p = Path(f["path"])
            if not p.exists():
                raise FileNotFoundError(f"missing {p}")
            size = p.stat().st_size
            if int(f.get("size_bytes", -1)) != size:
                raise ValueError(f"size mismatch for {p}")
            with open(p, "rb") as fh:
                sha = hashlib.sha256(fh.read()).hexdigest()
            if f.get("sha256") != sha:
                raise ValueError(f"sha256 mismatch for {p}")

    # ------------------------------------------------------------------
    def _ensure_model(self) -> None:
        logger.debug("Ensuring WD14 model is loaded")
        if self._session is not None:
            logger.debug("Model session already initialized")
            return

        model_cfg = self._cfg.get("model", {})
        model_path = model_cfg.get("path", "")
        provider = model_cfg.get("provider", "auto").lower()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if provider == "cpu":
            providers = ["CPUExecutionProvider"]
        elif provider == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        logger.info("Loading WD14 model from %s with providers %s", model_path, providers)
        try:
            import onnxruntime as ort  # type: ignore
        except ModuleNotFoundError as e:  # pragma: no cover - runtime dependency
            logger.error("onnxruntime is required but missing: %s", e)
            raise ModuleNotFoundError(
                "onnxruntime is required for image keyword extraction. "
                "Install it with 'pip install onnxruntime'."
            ) from e

        self._session = ort.InferenceSession(model_path, providers=providers)
        logger.info("WD14 model loaded successfully")

        tag_path = model_cfg.get("taglist", "")
        char_path = model_cfg.get("charlist", "")
        self._general_tags = Path(tag_path).read_text(encoding="utf-8").splitlines()
        self._char_tags = Path(char_path).read_text(encoding="utf-8").splitlines()

    # ------------------------------------------------------------------
    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._EXTS

    # ------------------------------------------------------------------
    def _cache_get(self, key: str):
        cache_path = self._cfg.get("caching", {}).get("store")
        if not cache_path:
            return None
        conn = sqlite3.connect(cache_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
        )
        cur = conn.execute("SELECT value FROM cache WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return None
        return None

    def _cache_set(self, key: str, value) -> None:
        cache_path = self._cfg.get("caching", {}).get("store")
        if not cache_path:
            return
        conn = sqlite3.connect(cache_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            "REPLACE INTO cache(key,value) VALUES (?,?)", (key, json.dumps(value))
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    def _preprocess(self, img: Image.Image):
        import numpy as np

        img = img.convert("RGB").resize((448, 448), Image.BICUBIC)
        arr = np.array(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        arr = arr.transpose(2, 0, 1)[None]
        return arr

    def _infer_tags(self, img: Image.Image) -> List[str]:
        import numpy as np  # noqa: F401

        logger.debug("Running tag inference")
        self._ensure_model()
        arr = self._preprocess(img)
        logger.debug("Image preprocessed: %s", getattr(arr, "shape", "unknown"))
        outputs = self._session.run(None, {self._session.get_inputs()[0].name: arr})[0][0]

        g_thr = self._cfg.get("threshold", {}).get("general", 0.35)
        c_thr = self._cfg.get("threshold", {}).get("character", 0.85)

        general_scores = outputs[4 : 4 + len(self._general_tags)]
        char_scores = outputs[4 + len(self._general_tags) : 4 + len(self._general_tags) + len(self._char_tags)]

        results: List[tuple[str, float]] = []
        for tag, prob in zip(self._general_tags, general_scores):
            if prob >= g_thr and tag not in self._blacklist:
                results.append((tag, float(prob)))
        for tag, prob in zip(self._char_tags, char_scores):
            if prob >= c_thr and tag not in self._blacklist:
                results.append((tag, float(prob)))

        results.sort(key=lambda x: x[1], reverse=True)
        topk = self._cfg.get("output", {}).get("topk", 128)
        tags = [t for t, _ in results[:topk]]

        if self._cfg.get("output", {}).get("replace_underscore", True):
            tags = [t.replace("_", " ") for t in tags]

        if self._cfg.get("translation", {}).get("enable", False):
            tags = [self._dict.get(t, t) for t in tags]

        logger.debug("Inference produced %d tags", len(tags))
        return tags

    # ------------------------------------------------------------------
    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        logger.info("Extracting image keywords from %s", path)
        meta = {"handler": self.name}

        if self._manifest_error:
            logger.error("Manifest error: %s", self._manifest_error)
            meta["error"] = self._manifest_error
            chunk = Chunk(id=f"{path}#0", doc_id=path, text="", metadata=meta)
            return ExtractResult(text="", meta=meta, chunks=[chunk])

        try:
            with open(path, "rb") as f:
                img_bytes = f.read()

            img_sha = hashlib.sha256(img_bytes).hexdigest()
            key = (
                f"{img_sha}:{self._cfg.get('model', {}).get('variant', '')}:"
                f"{self._cfg.get('threshold', {}).get('general', 0)}:"
                f"{self._cfg.get('threshold', {}).get('character', 0)}"
            )
            cached = self._cache_get(key)
            if cached is not None:
                logger.debug("Using cached tags for %s", path)
                tags = cached
            else:
                img = Image.open(io.BytesIO(img_bytes))
                tags = self._infer_tags(img)
                self._cache_set(key, tags)

            text = ", ".join(tags)
            if tags and self._cfg.get("output", {}).get("trailing_comma", True):
                text += ","

            meta["tags"] = tags
            if not tags:
                logger.warning("No tags extracted for %s", path)
            else:
                logger.info("Extracted %d tags for %s", len(tags), path)
            chunk = Chunk(id=f"{path}#0", doc_id=path, text=text, metadata=meta)
            return ExtractResult(text=text, meta=meta, chunks=[chunk])
        except Exception as e:  # pragma: no cover - robustness
            meta["error"] = str(e)
            logger.error("Failed to extract tags for %s: %s", path, e)
            chunk = Chunk(id=f"{path}#0", doc_id=path, text="", metadata=meta)
            return ExtractResult(text="", meta=meta, chunks=[chunk])


register(ImageKeywordsWD14())

