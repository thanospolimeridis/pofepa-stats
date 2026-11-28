"""Figures stated in README.md and docs/SOURCES.md must match the committed catalog.

When the data changes, this fails with the sentence to update instead of
letting the documentation drift. (Page counts and build sizes need the raw
cache or a build, so they are not checked here.)
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dataset import load  # noqa: E402

NUMBER = r'(\d{1,3}(?:,\d{3})+|\d+)'


def value(text):
    return int(text.replace(',', ''))


class DocumentedFiguresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = load()
        c, sheets = data['coverage'], data['coverage']['match_sheets']
        pdfs = [r for r in c['document_reviews'] if r['url'].lower().endswith('.pdf')]
        images = [r for r in c['document_reviews'] if not r['url'].lower().endswith('.pdf')]
        cls.facts = {
            'imported_sheets': sheets['imported_sheets'], 'imported': sheets['imported'], 'corroborated': sheets['corroborated'],
            'walkovers': sheets['excluded_walkovers'], 'team_walkovers': sheets['excluded_team_walkovers'], 'held': sheets['held'],
            'linked': sheets['linked'], 'pending': sheets['pending'], 'unavailable': sheets['unavailable'],
            'workbooks': len(c['workbook_inventory']), 'ranking_rows': c['ranking_rows'], 'reported': c['reported_fixtures'],
            'pdfs': len(pdfs), 'images': len(images), 'document_results': sum(r.get('fixtures', 0) for r in c['document_reviews']),
            'pdf_results': sum(r.get('fixtures', 0) for r in pdfs),
        }
        cls.matches, cls.periods = c['matches'], c['ranking_periods']
        cls.docs = {name: (ROOT / name).read_text(encoding='utf-8') for name in ('README.md', 'docs/SOURCES.md')}

    def claim(self, name, pattern, fact):
        found = re.search(pattern.replace('{n}', NUMBER), self.docs[name])
        self.assertIsNotNone(found, f'{name}: sentence not found for {fact} ({pattern})')
        self.assertEqual(value(found.group(1)), self.facts[fact],
                         f'{name} says {found.group(1)} for {fact}, but the catalog has {self.facts[fact]:,}: "{found.group(0)}"')

    def test_readme_figures(self):
        for pattern, fact in [
            (r'\*\*{n} sheets from the', 'imported_sheets'), (r'adding \*\*{n} played singles', 'imported'),
            (r'corroborating {n} existing workbook results', 'corroborated'), (r'{n} individual walkovers', 'walkovers'),
            (r'and {n} whole-team no-shows', 'team_walkovers'), (r'Another {n} inspected sheets', 'held'),
            (r'\*\*{n} match-sheet links\*\*', 'linked'), (r'\*\*{n} have not yet been reviewed', 'pending'),
            (r'Unavailable source links \({n}\)', 'unavailable'), (r'All \*\*{n} distinct Excel workbooks', 'workbooks'),
            (r'\*\*{n} ranking records\*\*', 'ranking_rows'), (r'{n} reviewed PDFs', 'pdfs'),
            (r'bringing reported team results to {n}', 'reported'),
        ]:
            with self.subTest(fact=fact):
                self.claim('README.md', pattern, fact)

    def test_readme_ranges(self):
        floor = value(re.search(r'over \*\*' + NUMBER + r' completed singles', self.docs['README.md']).group(1))
        self.assertTrue(floor <= self.matches < floor + 1000, f'README says over {floor:,} singles; the catalog has {self.matches:,}')
        months = 'January February March April May June July August September October November December'.split()
        span = f'{months[int(self.periods[0][5:]) - 1]} {self.periods[0][:4]}–{months[int(self.periods[-1][5:]) - 1]} {self.periods[-1][:4]}'
        self.assertIn(f'**{span}**', self.docs['README.md'], 'README ranking-month span')

    def test_sources_figures(self):
        for pattern, fact in [
            (r'All {n} distinct linked workbooks', 'workbooks'), (r'All {n} linked PDFs', 'pdfs'),
            (r'The documents supply {n} team results', 'document_results'), (r'team results: {n} from PDFs', 'pdf_results'),
            (r'There are {n} distinct linked sheets', 'linked'), (r'The reviewed batches cover {n} sheets', 'imported_sheets'),
            (r'contributing {n} played singles', 'imported'), (r'corroborating {n} existing workbook results', 'corroborated'),
            (r'{n} more inspected sheets', 'held'), (r'The remaining {n} available linked sheets', 'pending'),
            (r'unavailable source links \({n}\)', 'unavailable'), (r'{n} walkovers are retained', 'walkovers'),
            (r'{n} whole-team no-shows', 'team_walkovers'),
        ]:
            with self.subTest(fact=fact):
                self.claim('docs/SOURCES.md', pattern, fact)


if __name__ == '__main__':
    unittest.main()
