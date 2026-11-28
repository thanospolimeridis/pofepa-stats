"""Canonical, deterministic dataset storage.

The committed catalog lives in data/catalog/ as plain text so git can store
each change as a small delta: an index, one JSON object file per mapping
(coverage) and JSON Lines shards for each table, one record per line, split
into files of at most about 8 MB. Loading it returns exactly the saved object:
same keys, order and values, so encode() and every hash are unchanged.
Build outputs and other single files use .json or deterministic .json.gz.
"""
import gzip
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data/catalog'
CATALOG_FORMAT = 1
SHARD_BYTES = 8 * 1024 * 1024


def encode(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def _write(path, text):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def save_catalog(data, directory=CATALOG):
    """Write the catalog as text shards, then swap the folder into place."""
    directory = Path(directory)
    staging = directory.with_name(directory.name + '.tmp')
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    index = {'format': CATALOG_FORMAT, 'keys': []}
    for key, value in data.items():
        if isinstance(value, list):
            files, lines, size = [], [], 0
            def flush():
                name = f'{key}-{len(files):03}.jsonl'
                (staging / name).write_text(''.join(lines), encoding='utf-8')
                files.append(name)
            for record in value:
                line = json.dumps(record, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
                if lines and size + len(line.encode()) > SHARD_BYTES:
                    flush()
                    lines, size = [], 0
                lines.append(line)
                size += len(line.encode())
            if lines:
                flush()
            index['keys'].append({'key': key, 'type': 'list', 'files': files})
        elif isinstance(value, dict):
            name = f'{key}.json'
            (staging / name).write_text(json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + '\n', encoding='utf-8')
            index['keys'].append({'key': key, 'type': 'object', 'file': name})
        else:
            index['keys'].append({'key': key, 'type': 'value', 'value': value})
    (staging / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    previous = directory.with_name(directory.name + '.old')
    if previous.exists():
        shutil.rmtree(previous)
    if directory.exists():
        directory.rename(previous)
    staging.rename(directory)
    if previous.exists():
        shutil.rmtree(previous)


def load_catalog(directory=CATALOG):
    directory = Path(directory)
    index = json.loads((directory / 'index.json').read_text(encoding='utf-8'))
    if index.get('format') != CATALOG_FORMAT:
        raise ValueError(f'Unsupported catalog format: {index.get("format")}')
    data = {}
    for entry in index['keys']:
        if entry['type'] == 'list':
            # Split on newlines only: JSON escapes them, but U+2028 and similar
            # characters can appear raw inside strings.
            data[entry['key']] = [json.loads(line) for name in entry['files']
                                  for line in (directory / name).read_text(encoding='utf-8').split('\n') if line]
        elif entry['type'] == 'object':
            data[entry['key']] = json.loads((directory / entry['file']).read_text(encoding='utf-8'))
        else:
            data[entry['key']] = entry['value']
    return data


def load(path=None):
    path = Path(path) if path else CATALOG
    if path.is_dir():
        return load_catalog(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(data, path):
    """Save to a .json/.json.gz file, or as a sharded catalog for a folder path."""
    path = Path(path)
    if path.suffix not in ('.gz', '.json'):
        return save_catalog(data, path)
    body = encode(data)
    if path.suffix == '.gz':
        body = gzip.compress(body, compresslevel=9, mtime=0)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(body)
    temporary.replace(path)
