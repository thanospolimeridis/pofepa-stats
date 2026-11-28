"""Which legacy workbook cells name teams: pairs, wrapped names and event headings."""
from datetime import datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from workbooks import LegacySheet, result_date, result_days, result_rows, team_pair


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


class DateBlockTests(unittest.TestCase):
    def rows(self, rows):
        return {num: (values, context) for num, values, context in result_rows(Sheet(rows))}

    def test_a_date_range_starts_a_block_dated_to_its_first_day(self):
        # Reduced from rl_be_05-2016.xls rows 10-19: a league match dated 5 May,
        # then a two-day tournament headed "7-8/05/16" with no team cells.
        out = self.rows([
            row(datetime(2016, 5, 5), 'Α1', 'Β1', (3, 0), 'ΠΟΛΥΝΙΚΟΣ', 'ΑΕΤΟΙ ΕΥΟΣΜΟΥ', 'ΠΡΩΤΑΘΛΗΜΑ'),
            row(None, 'Α2', 'Β2', (3, 1)),
            row('7-8/05/16', 'Γ1', 'Δ1', (2, 3), None, None, '1ο ΒΟΡΕΙΟΥ ΕΛΛΑΔΑΣ'),
            row(None, 'Γ2', 'Δ2', (3, 0)),
        ])
        self.assertEqual(out[2][0][0], datetime(2016, 5, 5))
        self.assertEqual((out[2][0][5], out[2][0][6]), ('ΠΟΛΥΝΙΚΟΣ', 'ΑΕΤΟΙ ΕΥΟΣΜΟΥ'))
        for num in (3, 4):
            values, context = out[num]
            self.assertEqual(values[0], '7-8/05/16', 'the printed range, never the earlier date')
            self.assertEqual(result_date(values[0]).isoformat(), '2016-05-07', 'the first day of the range')
            self.assertEqual(context['date_through'], '2016-05-08', 'the last day stays with the evidence')
            self.assertEqual((values[5], values[6], values[7]), ('', '', '1ο ΒΟΡΕΙΟΥ ΕΛΛΑΔΑΣ'))
            self.assertEqual((context['date_row'], context['team_row']), (3, None))
        for num in (1, 2):
            self.assertNotIn('date_through', out[num][1], 'a single day has no range')

    def test_a_dashed_date_is_the_date_of_its_block(self):
        # Reduced from rl_03_2018.xls rows 319 and 428: the second day is typed "11-03-2018".
        out = self.rows([
            row(datetime(2018, 3, 10), 'Α1', 'Β1', (3, 0), None, None, '1ο VENUS SPINTHAROS'),
            row('11-03-2018', 'Α2', 'Β2', (0, 3)),
            row(None, 'Α3', 'Β3', (3, 2)),
        ])
        self.assertEqual(result_date(out[1][0][0]).isoformat(), '2018-03-10')
        for num in (2, 3):
            self.assertEqual(result_date(out[num][0][0]).isoformat(), '2018-03-11')
            self.assertEqual(out[num][1]['date_row'], 2)
            self.assertEqual(out[num][0][7], '1ο VENUS SPINTHAROS')

    def test_a_note_in_the_date_column_ends_the_dated_block(self):
        out = self.rows([
            row(datetime(2016, 5, 5), 'Α1', 'Β1', (3, 0), 'ΠΟΛΥΝΙΚΟΣ', 'ΑΕΤΟΙ ΕΥΟΣΜΟΥ', 'ΠΡΩΤΑΘΛΗΜΑ'),
            row('Τα αποτελέσματα του τουρνουά εμφανίζονται παρακάτω', None, None, (None, None)),
            row(None, 'Γ1', 'Δ1', (3, 0)),
        ])
        self.assertIsNone(result_date(out[3][0][0]))
        self.assertEqual((out[3][0][5], out[3][0][6]), ('', ''))

    def test_a_day_or_a_range_of_days_in_one_month_is_a_date(self):
        for text, expected in (('26/10/2011', '2011-10-26'), ('6/1/2011', '2011-01-06'), ('11-03-2018', '2018-03-11'),
                               ('11.03.2018', '2018-03-11'), (' 26/10/2011 ', '2011-10-26'), ('26/10/11', '2011-10-26')):
            self.assertEqual([day.isoformat() for day in result_days(text)], [expected, expected], text)
        self.assertEqual(result_date(datetime(2019, 6, 1, 0, 0)).isoformat(), '2019-06-01')
        for text, first, last in (('7-8/05/16', '2016-05-07', '2016-05-08'), ('7 - 8/05/2016', '2016-05-07', '2016-05-08'),
                                  ('6-8.05.16', '2016-05-06', '2016-05-08')):
            self.assertEqual([day.isoformat() for day in result_days(text)], [first, last], text)
            self.assertEqual(result_date(text).isoformat(), first, text)
        # Not a date: a reversed or empty range, a day that does not exist, a range across
        # months, a three-digit year (rl_06_2018.xls prints "2/6/208") and other text.
        for text in ('8-7/05/16', '7-7/05/16', '30-31/02/16', '30/4-1/5/16', '31/02/2015', '29/2/2015', '2/6/208',
                     '11-03/2018', '2018-03-11', 'ΣΑΒΒΑΤΟ', '', None, 43160):
            self.assertIsNone(result_days(text), text)
            self.assertIsNone(result_date(text), text)


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
