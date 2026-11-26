"""Contract checks for deferred fixture and source-audit data."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build import bootstrap_data
from dataset import encode


class BootstrapContractTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            'schema': 1, 'dataset_sha256': 'unchanged-catalog-hash',
            'players': [{'id': 'p-1', 'stats': {'played': 2}}],
            'events': [{'id': 'e-1', 'match_count': 2}],
            'snapshots': [{'id': 'r-1', 'list': 'ΓΕΝΙΚΟΣ', 'rows': [['p-1', 1]]}],
            'matches': [{'id': 'm-1'}], 'recent_matches': [{'id': 'm-1'}],
            'fixtures': [{'id': 'f-1', 'rubbers': [{'match': 'm-1'}],
                          'excluded_workbook_results': [{'match': {'id': 'm-2'}}]}],
            'sources': [{'id': 's-1', 'url': 'https://example.org/source.jpg',
                         'sha256': 'hash', 'retrieved_at': '2026-11-26'}],
            'issues': [{'reason': 'audit-only'}],
            'coverage': {'matches': 2, 'ranking_periods': ['2026-10'],
                         'document_reviews': [{'url': 'source'}],
                         'match_sheets': {'reviewed': 1, 'held': 0,
                                          'seasons': {'2025-2026': {'accepted': 1}},
                                          'reviews': [{'fixture': 'f-1'}],
                                          'issues': [], 'unavailable_sources': []}},
        }

    def test_projection_preserves_full_archive_and_required_indexes(self):
        original = deepcopy(self.data)
        result = bootstrap_data(self.data)
        self.assertEqual(self.data, original)
        self.assertNotIn('fixtures', result)
        self.assertNotIn('issues', result)
        self.assertEqual(result['sources'], [{'id': 's-1', 'url': 'https://example.org/source.jpg'}])
        self.assertEqual(result['archives'], {'fixtures': 'data/fixtures.json.gz', 'about': 'data/about.json.gz'})
        for key in ('players', 'events', 'snapshots', 'matches', 'recent_matches'):
            self.assertEqual(result[key], original[key])
        self.assertEqual(result['coverage']['ranking_periods'], ['2026-10'])
        self.assertEqual(result['coverage']['match_sheets'], {
            'reviewed': 1, 'held': 0, 'seasons': {'2025-2026': {'accepted': 1}}})
        self.assertNotIn('document_reviews', result['coverage'])

    def test_bootstrap_hash_changes_without_catalog_hash_change(self):
        result = bootstrap_data(self.data)
        before = hashlib.sha256(encode(result)).hexdigest()
        result['bootstrap_schema'] += 1
        self.assertNotEqual(before, hashlib.sha256(encode(result)).hexdigest())
        self.assertEqual(result['dataset_sha256'], self.data['dataset_sha256'])


if __name__ == '__main__':
    unittest.main()
