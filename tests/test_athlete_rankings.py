"""Comparable ranking context must be available before the match month."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from athlete_rankings import match_ranking_context


def snapshot(identifier, period, rows, region='national', ranking_list='ΓΕΝΙΚΟΣ'):
    return {'id': identifier, 'period': period, 'region': region, 'list': ranking_list, 'rows': rows}


def match(identifier='m1', played='2026-03-10', first='a', second='b', region='south', regions=None):
    return {'id': identifier, 'date': played, 'p1': first, 'p2': second,
            'region': region, 'regions': [region] if regions is None else regions}


class AthleteRankingTests(unittest.TestCase):
    def context(self, snapshots, matches=None):
        return match_ranking_context({'snapshots': snapshots, 'matches': matches or [match()]})

    def test_same_month_and_future_snapshots_are_excluded(self):
        snapshots = [snapshot('old', '2026-02', [['a', 3], ['b', 8]]),
                     snapshot('same', '2026-03', [['a', 9], ['b', 2]]),
                     snapshot('future', '2026-04', [['a', 1], ['b', 4]])]
        self.assertEqual(self.context(snapshots), {'m1': {'snapshot': 'old', 'ranks': [3, 8]}})
        self.assertEqual(self.context(snapshots[1:]), {})

    def test_latest_prior_period_is_global_not_latest_common_player_list(self):
        snapshots = [snapshot('stale', '2026-01', [['a', 3], ['b', 8]]),
                     snapshot('current', '2026-02', [['a', 4]])]
        self.assertEqual(self.context(snapshots), {})
        # A current list in a different region still prevents a stale fallback.
        snapshots[-1]['region'] = 'north'
        self.assertEqual(self.context(snapshots), {})

    def test_both_players_must_share_one_snapshot(self):
        snapshots = [snapshot('south', '2026-02', [['a', 1]], 'south'),
                     snapshot('north', '2026-02', [['b', 2]], 'north')]
        self.assertEqual(self.context(snapshots, [match(regions=['north', 'south'])]), {})
        # Two national source files are not a licence to combine their rows.
        for item in snapshots:
            item['region'] = 'national'
        self.assertEqual(self.context(snapshots), {})

    def test_national_preferred_then_primary_then_other_recorded_regions(self):
        snapshots = [snapshot('national', '2026-02', [['a', 20], ['b', 30]]),
                     snapshot('north', '2026-02', [['a', 2], ['b', 3]], 'north'),
                     snapshot('south', '2026-02', [['a', 5], ['b', 6]], 'south')]
        matches = [match(region='south', regions=['north', 'south'])]
        self.assertEqual(self.context(snapshots, matches)['m1']['snapshot'], 'national')
        self.assertEqual(self.context(snapshots[1:], matches)['m1']['snapshot'], 'south')
        self.assertEqual(self.context(snapshots[1:2], matches)['m1']['snapshot'], 'north')

    def test_unrelated_regional_list_is_not_selected(self):
        self.assertEqual(self.context([snapshot('north', '2026-02', [['a', 1], ['b', 2]], 'north')]), {})

    def test_region_and_source_ties_are_deterministic(self):
        snapshots = [snapshot('source-z', '2026-02', [['a', 5], ['b', 6]], 'south'),
                     snapshot('source-a', '2026-02', [['a', 3], ['b', 4]], 'south')]
        self.assertEqual(self.context(snapshots)['m1'], {'snapshot': 'source-a', 'ranks': [3, 4]})
        self.assertEqual(self.context(snapshots), self.context(list(reversed(snapshots))))
        regions = [snapshot('south', '2026-02', [['a', 4], ['b', 5]], 'south'),
                   snapshot('north', '2026-02', [['a', 2], ['b', 3]], 'north')]
        self.assertEqual(self.context(regions, [match(region='multi', regions=['south', 'north'])]),
                         self.context(regions[::-1], [match(region='multi', regions=['north', 'south'])]))

    def test_age_lists_do_not_supply_ranks_or_move_latest_general_period(self):
        snapshots = [snapshot('general', '2026-01', [['a', 30], ['b', 40]]),
                     snapshot('age', '2026-02', [['a', 1], ['b', 2]], ranking_list='BET 40-49')]
        self.assertEqual(self.context(snapshots)['m1'], {'snapshot': 'general', 'ranks': [30, 40]})
        self.assertEqual(self.context(snapshots[1:]), {})

    def test_conflicting_duplicate_position_is_excluded_without_stale_fallback(self):
        snapshots = [snapshot('stale', '2026-01', [['a', 4], ['b', 5]]),
                     snapshot('ambiguous', '2026-02', [['a', 1], ['a', 2], ['b', 3]])]
        self.assertEqual(self.context(snapshots), {})
        # An unambiguous regional list from that same current period may work.
        snapshots.append(snapshot('regional', '2026-02', [['a', 2], ['b', 4]], 'south'))
        self.assertEqual(self.context(snapshots)['m1'], {'snapshot': 'regional', 'ranks': [2, 4]})

    def test_tied_ranks_and_identical_duplicate_rows_are_preserved(self):
        snapshots = [snapshot('tied', '2026-02', [['a', 3], ['a', 3], ['b', 3]])]
        self.assertEqual(self.context(snapshots)['m1']['ranks'], [3, 3])

    def test_unranked_or_invalid_duplicate_rows_do_not_become_ranked(self):
        for rank in (None, 0, -1, True, '3', 3.5):
            with self.subTest(rank=rank):
                self.assertEqual(self.context([snapshot('bad', '2026-02', [['a', rank], ['b', 4]])]), {})
                self.assertEqual(self.context([snapshot('bad', '2026-02', [['a', 3], ['a', rank], ['b', 4]])]), {})

    def test_ambiguous_snapshot_reference_is_excluded(self):
        self.assertEqual(self.context([snapshot('same-id', '2026-02', [['a', 1], ['b', 2]]),
                                       snapshot('same-id', '2026-02', [['a', 3], ['b', 4]])]), {})

    def test_orientation_calendar_and_catalog_are_preserved(self):
        data = {'snapshots': [snapshot('before', '2025-12', [['a', 7], ['b', 11]])],
                'matches': [match('forward', '2026-01-01'), match('reverse', '2026-01-31', 'b', 'a'),
                            match('too-early', '2025-12-31'), match('invalid', '2026-02-30'),
                            match('missing-player', first='unknown'), match('same-player', second='a')]}
        before = deepcopy(data)
        self.assertEqual(match_ranking_context(data), {
            'forward': {'snapshot': 'before', 'ranks': [7, 11]},
            'reverse': {'snapshot': 'before', 'ranks': [11, 7]},
        })
        self.assertEqual(data, before)
        self.assertEqual(match_ranking_context({'snapshots': [], 'matches': data['matches']}), {})


if __name__ == '__main__':
    unittest.main()
