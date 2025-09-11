#!/usr/bin/env python3
"""Generate WD14 tag lists from wd-vit-tagger-v3.csv.

This script reads the CSV file distributed with the WD14 tagger and
splits tags into general and character categories, writing them to
``tags.txt`` and ``char_tags.txt`` respectively within the models
folder.
"""
from pathlib import Path
import csv

CSV_FILE = Path(__file__).resolve().parent.parent / 'plugins' / 'image_keywords_wd14' / 'models' / 'wd-vit-tagger-v3.csv'
OUT_DIR = CSV_FILE.parent

general: list[str] = []
characters: list[str] = []

with CSV_FILE.open('r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row['name']
        category = row['category']
        if category == '0':
            general.append(name)
        elif category == '4':
            characters.append(name)

(OUT_DIR / 'tags.txt').write_text('\n'.join(general), encoding='utf-8')
(OUT_DIR / 'char_tags.txt').write_text('\n'.join(characters), encoding='utf-8')

print(f"Wrote {len(general)} general tags and {len(characters)} character tags")
