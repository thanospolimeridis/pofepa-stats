"""The sharded text catalog round-trips exactly and stays within file limits."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import dataset  # noqa: E402
from dataset import CATALOG, encode, load, load_catalog, save, save_catalog  # noqa: E402


class CatalogStorageTests(unittest.TestCase):
    def test_round_trip_keeps_keys_order_and_awkward_text(self):
        data = {'schema': 1, 'coverage': {'b': [1, 2.5], 'a': {'x': None}},
                'matches': [{'id': f'm{i}', 'names': ['ΑΒΓ ΔΕ', 'line\nbreak', 'tab\tquote"'], 'score': [3, i % 3]}
                            for i in range(50)],
                'empty': [], 'note': 'κείμενο'}
        directory = Path(tempfile.mkdtemp()) / 'catalog'
        with mock.patch.object(dataset, 'SHARD_BYTES', 400):
            save_catalog(data, directory)
        self.assertEqual(encode(load_catalog(directory)), encode(data))
        self.assertGreater(len(list(directory.glob('matches-*.jsonl'))), 1, 'large tables are split into shards')
        first = {p.name: p.read_bytes() for p in directory.iterdir()}
        with mock.patch.object(dataset, 'SHARD_BYTES', 400):
            save(data, directory)
        self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, first, 'saving is deterministic')
        self.assertFalse(directory.with_name('catalog.tmp').exists() or directory.with_name('catalog.old').exists())

    def test_single_files_still_use_json_or_gzip(self):
        target = Path(tempfile.mkdtemp()) / 'part.json.gz'
        save({'a': [1, 2]}, target)
        self.assertEqual(load(target), {'a': [1, 2]})

    def test_committed_catalog_is_text_shards_within_github_limits(self):
        index = load_catalog(CATALOG)
        self.assertEqual(index['schema'], 1)
        for path in CATALOG.iterdir():
            self.assertLess(path.stat().st_size, 20 * 1024 * 1024, path.name)
        self.assertFalse((ROOT / 'data/catalog.json.gz').exists(), 'the gzip catalog is no longer committed')


if __name__ == '__main__':
    unittest.main()
