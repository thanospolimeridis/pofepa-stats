"""Which legacy workbook cells name teams: pairs, wrapped names and event headings."""
from datetime import datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from workbooks import LegacySheet, result_rows, team_pair


class Sheet(LegacySheet):
    """An in-memory .xls results sheet (layout: date, players, games, teams, event)."""
    def __init__(self, rows):
        self.title, self.rows = 'ΑΠΟΤΕΛΕΣΜΑΤΑ', rows

    def iter_rows(self, values_only=True):
        return iter(self.rows)


def row(date, a, b, games, home=None, away=None, event=None):
    return (date, a, b, *games, home, away, event, 0, None)


class TeamPairTests(unittest.TestCase):
    def test_team_names_that_resemble_categories_stay_teams(self):
        for pair in (['ΒΕΤ. ΑΟ ΤΑΤΑΥΛΑ', 'ΑΚΤΩΡ'], ['ΒΕΤΕΡΑΝΟΙ ΔΡΑΜΑΣ', 'ΑΕΤΟΙ ΚΟΜΟΤΗΝΗΣ'],
                     ['ΑΝΕΞ. ΑΟ ΤΑΤΑΥΛΑ', 'SPINMASTERS'], ['ΒΕΤ. Δ. 3Β', 'ΣΕΠ ΑΙΓΑΛΕΩ'], ['25ο', 'ΦΟΥΡΤΟΥΝΑ']):
            self.assertEqual(team_pair(pair), pair)

    def test_categories_stages_headers_and_single_cells_are_not_teams(self):
        for cells in (['ΟΜΙΛΟΙ', 'ΑΝΕΞ. 18-39'], ['ΑΝΕΞ. 40-49', 'ΦΑΣΗ ΟΜΙΛΩΝ'], ['ANE 18-39', 'ΠΑΝΕΛΛΗΝΙΟ ΠΡΩΤΑΘΛΗΜΑ'],
                      ['α/α', 'ΒΕΤ 40-49'], ['ΚΑΤΗΓΟΡΙΑ 50+ ΑΝΕΞ.', 'ΚΑΤΑΤΑΞΗ 5-14'], ['1-8', 'ΓΥΝ ΑΝΕ'],
                      ['ΑΤΟΜΙΚΑ ΔΥΤΙΚΗΣ ΕΛΛΑΔΑΣ', 'ΑΝΕΞΑΡΤΗΤΟΙ'], ['ΑΤΤΙΚΗΣ & ΝΟΤΙΑΣ ΕΛΛΑΔΑΣ', ''], ['', 'ΓΥΝΑΙΚΕΣ']):
            self.assertIsNone(team_pair(cells), cells)


class LegacyBlockTests(unittest.TestCase):
    def clubs(self, rows):
        return {num: (values[5], values[6], context['team_row']) for num, values, context in result_rows(Sheet(rows))}

    def test_wrapped_team_names_keep_the_pair(self):
        # Reduced from rl_be_10-2017.xls: "ΚΡΟΚΟΔΕΙΛΟΙ / ΦΛΩΡΙΝΑΣ" vs "ΑΠΡΟΠΟΝΗΤΟΙ / ΚΟΖΑΝΗΣ".
        clubs = self.clubs([
            row(datetime(2017, 10, 8), 'Α1', 'Β1', (3, 0), 'ΚΡΟΚΟΔΕΙΛΟΙ', 'ΑΠΡΟΠΟΝΗΤΟΙ', 'ΠΡΩΤΑΘΛΗΜΑ'),
            row(None, 'Α2', 'Β2', (3, 1), 'ΦΛΩΡΙΝΑΣ', ' ΚΟΖΑΝΗΣ', 'ΔΥΤ. ΜΑΚΕΔΟΝΙΑΣ-'),
            row(None, 'Α3', 'Β3', (3, 0), None, 'ΝΟΤΙΟΥ', None),
            row(None, 'Α4', 'Β4', (2, 3)),
        ])
        for num in (1, 2, 3, 4):
            self.assertEqual(clubs[num], ('ΚΡΟΚΟΔΕΙΛΟΙ', 'ΑΠΡΟΠΟΝΗΤΟΙ', 1))

    def test_individual_event_headings_carry_no_teams(self):
        # Reduced from rl_be_06-2019.xls rows 76-91 and rl_01_2019.xls row 260.
        clubs = self.clubs([
            row(datetime(2019, 6, 1), 'Α1', 'Β1', (1, 3), 'SPEEDPONG', '25ο', 'PLAY OFF Κ-ΜΑΚ'),
            row(None, 'Α2', 'Β2', (2, 3)),
            row(datetime(2019, 6, 1), 'Γ1', 'Δ1', (3, 0), 'ΑΝΕ 18-39', 'ΟΡΕΝ ΖΩΓΡΑΦΟΥ'),
            row(None, 'Γ2', 'Δ2', (2, 3)),
            row(None, 'Ε1', 'Ζ1', (0, 3), 'α/α'),  # a walkover inside the heading's block
            row(datetime(2019, 6, 2), 'Η1', 'Θ1', (3, 0), 'ΒΕΤ. ΑΟ ΤΑΤΑΥΛΑ', 'ΑΚΤΩΡ', 'ΠΡΩΤΑΘΛΗΜΑ'),
            row(None, 'Η2', 'Θ2', (3, 1), 'ΒΕΤ 40-49'),
            row(None, 'Η3', 'Θ3', (3, 2)),
        ])
        self.assertEqual(clubs[1][:2], ('SPEEDPONG', '25ο'))
        self.assertEqual(clubs[2][:2], ('SPEEDPONG', '25ο'))
        for num in (3, 4, 5, 7, 8):
            self.assertEqual(clubs[num][:2], ('', ''), num)
        self.assertEqual(clubs[6][:2], ('ΒΕΤ. ΑΟ ΤΑΤΑΥΛΑ', 'ΑΚΤΩΡ'))
        # A category directly under a pair starts a new block; it is not a wrapped name.
        self.assertEqual(clubs[7][2], 7)


class WalkoverMarkTests(unittest.TestCase):
    def rows(self, rows):
        return {num: (values, context) for num, values, context in result_rows(Sheet(rows))}

    def test_walkover_mark_flags_only_its_row_and_never_becomes_a_team_or_event(self):
        # Reduced from rl_02_2016v3.xls and rl_01_2015.xls: "α/α" (άνευ αγώνα) in a
        # team or event cell, in front of a team name, or as a participant.
        out = self.rows([
            row(datetime(2016, 2, 7), 'Α1', 'Β1', (3, 0), 'α/α ΓΛΥΦΑΔΑ', 'ΑΚΤΩΡ', "Δ2' ΑΤΤΙΚΗΣ"),
            row(None, 'Α2', 'Β2', (3, 1)),
            row(None, 'Α3', 'Β3', (0, 3), 'α/α', None, 'α/α'),
            row(None, 'α.α.', 'Β4', (0, 3)),
            row(None, 'Α5', 'Β5', (3, 2)),
        ])
        self.assertEqual([num for num, (_, context) in out.items() if context.get('walkover')], [1, 3, 4])
        for num in (1, 2, 3, 4, 5):
            values = out[num][0]
            self.assertEqual((values[5], values[6], values[7]), ('ΓΛΥΦΑΔΑ', 'ΑΚΤΩΡ', "Δ2' ΑΤΤΙΚΗΣ"), num)

    def test_names_that_only_start_with_alpha_are_not_marks(self):
        out = self.rows([row(datetime(2016, 2, 7), 'ΑΑΡΩΝ ΚΩΝ.', 'Α.ΑΝΤΩΝΙΟΥ', (3, 0), 'ΑΛΦΑ', 'ΑΚΤΩΡ', 'ΠΡΩΤΑΘΛΗΜΑ')])
        self.assertNotIn('walkover', out[1][1])


if __name__ == '__main__':
    unittest.main()
