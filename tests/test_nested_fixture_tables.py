"""Rounds whose columns sit partly in a nested Weebly table, and fixture-team validation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect import order_deferred, parse_fixture_tables, unaligned_rounds
from validate import bye, fixture_side_ok

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

    def test_a_skipped_round_is_reported_once_with_its_printed_results(self):
        broken = HOME_BESIDE_NESTED.replace('SPIN DOCTORS</br>', '</br>')
        skipped = []
        self.assertEqual(parse_fixture_tables(broken, 'source', URL, 'event', skipped), [])
        self.assertEqual(skipped, [{'table': 0, 'round': '14η Αγωνιστική (7-13/4/2025)', 'printed_results': 3}])
        self.assertEqual(unaligned_rounds('Ε ΚΑΤΗΓΟΡΙΑ', URL, skipped), [{
            'label': 'Ε ΚΑΤΗΓΟΡΙΑ · 14η Αγωνιστική (7-13/4/2025)', 'url': URL, 'reason': 'unaligned_round',
            'table': 0, 'printed_results': 3}])

    def test_a_round_without_results_is_reported_with_none_printed(self):
        # Reduced from 2019-20-a1.html: rounds listed for spring 2020 with an empty score column.
        html = '<h2>9η Αγωνιστική (16-22/3/2020)</h2><table><tr><td>A<br>B</td><td>-<br>-</td><td>C<br>D</td><td></td></tr></table>'
        skipped = []
        self.assertEqual(parse_fixture_tables(html, 'source', URL, 'event', skipped), [])
        self.assertEqual(skipped, [{'table': 0, 'round': '9η Αγωνιστική (16-22/3/2020)', 'printed_results': 0}])

    def test_aligned_rounds_and_other_tables_are_not_reported(self):
        layout = '<table><tr><td>Κείμενο</td><td></td><td>Εικόνα</td><td>Σύνδεσμος</td></tr></table>'
        for html in (HOME_BESIDE_NESTED, HOME_AND_DASH_BESIDE_NESTED, layout):
            skipped = []
            parse_fixture_tables(html, 'source', URL, 'event', skipped)
            self.assertEqual(skipped, [])

    def test_deferred_order_lists_whole_sources_before_rounds(self):
        entries = [{'url': 'b', 'reason': 'unaligned_round', 'table': 2}, {'url': 'z', 'reason': 'source_unavailable'},
                   {'url': 'a', 'reason': 'unaligned_round', 'table': 9}, {'url': 'b', 'reason': 'unaligned_round', 'table': 1},
                   {'url': 'c', 'reason': 'document_source_conflict'}]
        self.assertEqual([(d['url'], d.get('table')) for d in order_deferred(entries)],
                         [('z', None), ('c', None), ('a', 9), ('b', 1), ('b', 2)])

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

    def test_a_row_of_x_is_a_bye_in_either_alphabet(self):
        clubs = {'c-x'}
        for name in ('XXX', 'ΧΧΧ', 'ΧΧΧΧ', 'xxx', ' ΧΧΧ ', '—', '–'):
            self.assertTrue(bye(name), name)
            self.assertTrue(fixture_side_ok(name, '', clubs), name)
            self.assertFalse(fixture_side_ok(name, 'c-x', clubs), 'A bye has no club')

    def test_real_team_names_are_not_byes(self):
        # "ΑΝΕΥ ΑΓΩΝΟΣ" plays in the 2025-26 East Macedonia & Thrace league.
        for name in ('ΑΝΕΥ ΑΓΩΝΟΣ', 'X', 'ΧΑΝΘΗ', 'XXL', 'ΑΕΚ', '25ο', 'A-B', ''):
            self.assertFalse(bye(name), name)
        self.assertTrue(fixture_side_ok('ΑΝΕΥ ΑΓΩΝΟΣ', 'c-1', {'c-1'}))
        self.assertFalse(fixture_side_ok('ΑΝΕΥ ΑΓΩΝΟΣ', '', {'c-1'}))


if __name__ == '__main__':
    unittest.main()
