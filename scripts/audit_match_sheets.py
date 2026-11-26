#!/usr/bin/env python3
"""Verify source hashes and replay every reviewed match sheet without changes."""
from pathlib import Path
from collect import Cache
from dataset import load, encode
from import_match_sheets import import_reviews

ROOT = Path(__file__).resolve().parents[1]
data = load()
before = encode(data)
import_reviews(data, Cache(ROOT / 'capture', offline=True))
assert encode(data) == before, 'Match-sheet replay changed the committed dataset'
coverage = data['coverage']['match_sheets']
print(f"Verified {coverage['reviewed']} reviewed sheets and {coverage['imported']} imported singles; replay is unchanged.")
