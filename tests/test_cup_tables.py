"""Regression for the source's widely spaced team name in a BR-delimited draw."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect import parse_fixture_tables


class CupTableTests(unittest.TestCase):
    def test_br_delimited_cup_preserves_space_inside_team_name(self):
        # Reduced from 2012-13-kyp-k-mak.html, first round, fourth away team.
        html = '''<h2>Α' Προκριματική Φάση</h2><table><tr>
          <td>PARTIZAN ΧΑΡΙΛΑΟΥ<br/><span></span>ΚΙΛΚΙΣΦΑΙΡΙΣΗ<br/></td>
          <td>-<br/><span></span>-<br/></td>
          <td>ΘΕΡΜΗ<br/><span></span>Δ. Π. ΜΕΛΑ             2010<br/></td>
          <td>4-3<br/><span><a href="/sheets/final.jpg">7-0</a></span><br/></td>
        </tr></table>'''
        rows = parse_fixture_tables(html, 'source', 'https://www.pofepa.gr/cup.html', 'event')
        self.assertEqual([(r['home'], r['away'], r['score']) for r in rows], [
            ('PARTIZAN ΧΑΡΙΛΑΟΥ', 'ΘΕΡΜΗ', [4, 3]),
            ('ΚΙΛΚΙΣΦΑΙΡΙΣΗ', 'Δ. Π. ΜΕΛΑ 2010', [7, 0]),
        ])
        self.assertEqual(rows[1]['round'], "Α' Προκριματική Φάση")
        self.assertEqual((rows[1]['table'], rows[1]['row']), (0, 2))
        self.assertEqual(rows[1]['sheet_url'], 'https://www.pofepa.gr/sheets/final.jpg')
        # A missing score or separator cannot move a later result to a team.
        for bad in [html.replace('4-3<br/>', ''), html.replace('-<br/><span></span>-<br/>', '-<br/>')]:
            self.assertEqual(parse_fixture_tables(bad, 'source', 'https://www.pofepa.gr/cup.html', 'event'), [])


if __name__ == '__main__':
    unittest.main()
