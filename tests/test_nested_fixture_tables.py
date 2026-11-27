"""Rounds whose columns sit partly in a nested Weebly table, and fixture-team validation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect import parse_fixture_tables
from validate import fixture_side_ok

URL = 'https://www.pofepa.gr/league.html'
# Reduced from 2024-2025-e2.html round 14: home column beside a nested table
# holding the separator, away and score columns.
HOME_BESIDE_NESTED = '''<h2>14η Αγωνιστική (7-13/4/2025)</h2>
<table class="wsite-multicol-table"><tbody><tr>
  <td><div class="paragraph">RED LIONS 2<br>BEER PONGERS<br/>SPIN DOCTORS</br></div></td>
  <td><div><div class="wsite-multicol"><table class="wsite-multicol-table"><tbody><tr>
    <td><div class="paragraph">-<br/>-<br/>​-</div></td>
    <td><div class="paragraph">SPINFINITY 1<br/>ΑΡΗΣ ΝΙΚΑΙΑΣ<br/>ΤΡ.ΕΛΛΑ BLOCK</div></td>
    <td><div class="paragraph"><a href="/FA24-25/RL2-SF1.jpg">5-1</a> [<a href="/FA24-25/RL2-SF1p.jpg">pic</a>]<br/><a href="/FA24-25/BPG-AML.jpg">5-1</a><br/>2-5<br/></div></td>
  </tr></tbody></table></div></div></td>
</tr></tbody></table>'''
# Reduced from 2025-26-kmaka.html round 2: home and separator columns beside a
# nested table holding the away and score columns.
HOME_AND_DASH_BESIDE_NESTED = '''<h2>2η Αγωνιστική (10-16/11/2025)</h2>
<table class="wsite-multicol-table"><tbody><tr>
  <td><div class="paragraph">RED BLADES<br/>POLYGYROS TT</div></td>
  <td><div class="paragraph">-<br/>-</div></td>
  <td><div><table class="wsite-multicol-table"><tbody><tr>
    <td><div class="paragraph">ΚΙΛΚΙΣΦΑΙΡΙΣΗ<br/>SPEEDPONG</div></td>
    <td><div class="paragraph"><a href="/FA25-26/RBL-KLS.jpg">5-1</a><br/><a href="/FA25-26/PLG-SPG.jpg">5-0</a></div></td>
  </tr></tbody></table></div></td>
</tr></tbody></table>'''


def results(html):
    return [(f['home'], f['away'], f['score']) for f in parse_fixture_tables(html, 'source', URL, 'event')]


class NestedFixtureTableTests(unittest.TestCase):
    def test_home_column_beside_nested_away_and_scores(self):
        rows = parse_fixture_tables(HOME_BESIDE_NESTED, 'source', URL, 'event')
        self.assertEqual([(f['home'], f['away'], f['score']) for f in rows], [
            ('RED LIONS 2', 'SPINFINITY 1', [5, 1]),
            ('BEER PONGERS', 'ΑΡΗΣ ΝΙΚΑΙΑΣ', [5, 1]),
            ('SPIN DOCTORS', 'ΤΡ.ΕΛΛΑ BLOCK', [2, 5]),
        ])
        self.assertEqual([f['sheet_url'] for f in rows], [
            'https://www.pofepa.gr/FA24-25/RL2-SF1.jpg', 'https://www.pofepa.gr/FA24-25/BPG-AML.jpg', ''])
        self.assertEqual({f['round'] for f in rows}, {'14η Αγωνιστική (7-13/4/2025)'})
        # IDs follow the outer table's position, as for any other round table.
        self.assertEqual([(f['table'], f['row']) for f in rows], [(0, 1), (0, 2), (0, 3)])

    def test_home_and_separator_beside_nested_away_and_scores(self):
        self.assertEqual(results(HOME_AND_DASH_BESIDE_NESTED), [
            ('RED BLADES', 'ΚΙΛΚΙΣΦΑΙΡΙΣΗ', [5, 1]),
            ('POLYGYROS TT', 'SPEEDPONG', [5, 0]),
        ])

    def test_nested_rows_never_become_a_merged_fixture(self):
        for html in (HOME_BESIDE_NESTED, HOME_AND_DASH_BESIDE_NESTED):
            for home, away, _ in results(html):
                self.assertNotIn('-', home.split())
                self.assertNotIn('-', away.split())

    def test_misaligned_nested_round_is_skipped_not_guessed(self):
        broken = HOME_BESIDE_NESTED.replace('SPIN DOCTORS</br>', '</br>')
        self.assertEqual(results(broken), [])

    def test_text_beside_a_nested_table_keeps_the_cell_whole(self):
        # A cell with its own text is not expanded, so its parts cannot shift columns.
        mixed = HOME_BESIDE_NESTED.replace('<div><div class="wsite-multicol">', '<div>Σημείωση<div class="wsite-multicol">')
        self.assertEqual(results(mixed), [])


class FixtureTeamValidationTests(unittest.TestCase):
    def test_teams_need_a_letter_and_a_club(self):
        clubs = {'c-1'}
        self.assertTrue(fixture_side_ok('ΑΡΗΣ ΝΙΚΑΙΑΣ', 'c-1', clubs))
        self.assertTrue(fixture_side_ok('25ο', 'c-1', clubs))
        self.assertFalse(fixture_side_ok('- - - -', 'c-1', clubs), 'Merged separator column is not a team')
        self.assertFalse(fixture_side_ok('ΑΡΗΣ ΝΙΚΑΙΑΣ', '', clubs))

    def test_bye_is_a_bare_dash_without_a_club(self):
        clubs = {'c-dash'}
        self.assertTrue(fixture_side_ok('-', '', clubs))
        self.assertFalse(fixture_side_ok('-', 'c-dash', clubs), 'A bye has no club')


if __name__ == '__main__':
    unittest.main()
