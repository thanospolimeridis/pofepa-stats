"""Canonical, deterministic compressed dataset storage."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def encode(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def load(path=None):
    path = Path(path) if path else ROOT / 'data/catalog.json.gz'
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(data, path):
    path = Path(path)
    body = encode(data)
    if path.suffix == '.gz':
        body = gzip.compress(body, compresslevel=9, mtime=0)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(body)
    temporary.replace(path)
