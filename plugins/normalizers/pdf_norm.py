from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from PyPDF2 import PdfReader

from core.normalize_base import NormalizeResult, register
from core.settings import SETTINGS

TIMEOUT = SETTINGS.get("normalize", {}).get("timeouts", {}).get("pdf", 7200)


def process_pdf(in_path: str, out_dir: Path) -> None:
    reader = PdfReader(in_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_lines = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text:
            md_lines.append(f"## 第 {i} 页\n\n{text}\n")
    (out_dir / "document.md").write_text("\n".join(md_lines), encoding="utf-8")


def cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    process_pdf(args.input, Path(args.out))
    return 0


class PdfNormalizer:
    name = "pdf"
    priority = 80
    exts = ["pdf"]

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(".pdf")

    def normalize(self, path: str, out_root: str) -> NormalizeResult:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--input", path, "--out", out_root]
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, env=env)
        except Exception as e:
            return NormalizeResult(False, message=str(e))
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "")[-800:]
            return NormalizeResult(False, message=msg)
        md_paths = [str(p) for p in Path(out_root).glob("*.md")]
        csv_paths = [str(p) for p in Path(out_root).glob("*.csv")]
        sidecar = str(Path(out_root) / "sidecar.json") if (Path(out_root) / "sidecar.json").exists() else None
        return NormalizeResult(True, md_paths=md_paths, csv_paths=csv_paths, sidecar=sidecar)


register(PdfNormalizer())

if __name__ == "__main__":
    raise SystemExit(cli())
