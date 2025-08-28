# -*- coding: utf-8 -*-
from __future__ import annotations
"""Basic image extractor with perceptual hashes and CLIP embeddings."""

from pathlib import Path
from typing import List

from PIL import Image

from core.plugin_base import ExtractResult, register
from core.chunking import Chunk


class ImageBasic:
    name = "image-basic"
    version = "0.1.0"
    priority = 55

    _EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._EXTS

    # -------- Hash helpers -------------------------------------------------
    def _dhash(self, img: Image.Image, hash_size: int = 8) -> str:
        img = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        diff: List[bool] = []
        for row in range(hash_size):
            row_start = row * (hash_size + 1)
            for col in range(hash_size):
                diff.append(pixels[row_start + col] > pixels[row_start + col + 1])
        bits = ''.join('1' if v else '0' for v in diff)
        return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"

    def _phash(self, img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
        import math

        size = hash_size * highfreq_factor
        img = img.convert("L").resize((size, size), Image.LANCZOS)
        pixels = list(img.getdata())
        matrix = [pixels[i * size:(i + 1) * size] for i in range(size)]

        # 2D DCT
        dct = [[0.0] * size for _ in range(size)]
        for u in range(size):
            for v in range(size):
                s = 0.0
                for x in range(size):
                    for y in range(size):
                        s += (
                            matrix[x][y]
                            * math.cos((2 * x + 1) * u * math.pi / (2 * size))
                            * math.cos((2 * y + 1) * v * math.pi / (2 * size))
                        )
                dct[u][v] = s

        vals = [dct[u][v] for u in range(hash_size) for v in range(hash_size)]
        med = sorted(vals)[len(vals) // 2]
        bits = ''.join('1' if v > med else '0' for v in vals)
        return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"

    def _clip_vector(self, path: str) -> List[float]:
        try:
            import torch
            import open_clip  # type: ignore

            model, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="laion2b_s34b_b79k"
            )
            model.eval()
            with torch.no_grad():
                img = preprocess(Image.open(path)).unsqueeze(0)
                vec = model.encode_image(img)[0].float().tolist()
            return vec
        except Exception:
            return []

    # ------------------------------------------------------------------
    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        meta = {"handler": self.name}
        try:
            with Image.open(path) as img:
                meta["dhash"] = self._dhash(img)
                meta["phash"] = self._phash(img)
        except Exception:
            pass
        vec = self._clip_vector(path)
        if vec:
            meta["clip_vector"] = vec
        chunk = Chunk(id=f"{path}#0", doc_id=path, text="", metadata=meta)
        return ExtractResult(text="", meta=meta, chunks=[chunk])


register(ImageBasic())
