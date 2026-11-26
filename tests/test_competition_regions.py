import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from competition_regions import attach_regions, named_region, regional_links
from dataset import load


class CompetitionRegionTests(unittest.TestCase):
    def test_headings_apply_to_generic_links_and_do_not_cross_columns(self):
        links = regional_links('''<div id="wsite-content">
          <div class="paragraph"><strong>Αττική &amp; Νότια Ελλάδα</strong><br>
          <a href="a.html">Α1 Κατηγορία</a><br><strong>Κεντρική Μακεδονία</strong>
          <a href="b.html">Play offs</a><br><a href="west.html">Δυτική Ελλάδα</a>
          <a href="cup.html">Κύπελλο</a></div>
          <div class="paragraph"><a href="unknown.html">Α1-Α2</a></div>
          <div class="paragraph">Αττική<br><a href="attica-cup.pdf">Α1-Α2</a></div>
        </div>''', 'https://www.pofepa.gr/')
        self.assertEqual(links['https://www.pofepa.gr/a.html']['region'], 'attica-south')
        self.assertEqual(links['https://www.pofepa.gr/b.html']['region'], 'central-macedonia')
        self.assertEqual(links['https://www.pofepa.gr/cup.html']['region'], 'western-greece')
        self.assertEqual(links['https://www.pofepa.gr/attica-cup.pdf']['region'], 'attica-south')
        self.assertNotIn('https://www.pofepa.gr/unknown.html', links)

    def test_archive_region_is_not_competition_geography(self):
        data = {'sources': [], 'events': [
            {'name': 'ΠΡΩΤΑΘΛΗΜΑ', 'region': 'national', 'kind': 'singles', 'sources': []},
            {'name': 'ΠΑΝΕΛΛΗΝΙΟ', 'region': 'multi', 'kind': 'singles', 'sources': []},
        ]}
        attach_regions(data)
        self.assertEqual(data['events'][0]['competition_region'], 'unspecified')
        self.assertEqual(data['events'][0]['region'], 'national')
        self.assertEqual(data['events'][1]['competition_region'], 'nationwide')
        self.assertIsNone(named_region('ΠΡΩΤΑΘΛΗΜΑ'))

    def test_committed_source_context_covers_regional_competitions(self):
        data = load()
        before = [(e['id'], e.get('region'), e.get('regions')) for e in data['events']]
        attach_regions(data)
        self.assertEqual(before, [(e['id'], e.get('region'), e.get('regions')) for e in data['events']])
        current = [e for e in data['events'] if e['kind'] == 'fixtures' and e['season'] == '2026-2027']
        self.assertEqual(len({e['competition_region'] for e in current}), 9)
        self.assertNotIn('unspecified', {e['competition_region'] for e in current})
        cup = next(e for e in current if e['name'] == 'Α1-Α2')
        self.assertEqual(cup['competition_region'], 'attica-south')
        self.assertEqual(cup['competition_type'], 'cup')
        self.assertEqual(sum(e.get('competition_type') == 'cup' for e in data['events']), 113)
        by_id = {e['id']: e for e in data['events']}
        self.assertEqual(by_id['e-5cf953c77581868f']['competition_type'], 'cup')
        for eid in ('e-abed920a9f792f0d', 'e-6506a8d5f78bffbf'):
            self.assertEqual(by_id[eid]['competition_type'], 'league')
        for eid in ('e-a6dcea0ba29a77cc', 'e-ec08bc9719630027'):
            self.assertEqual(by_id[eid]['competition_type'], 'cup')
            self.assertEqual(by_id[eid]['competition_region'], 'attica-south')
        for e in data['events']:
            if e['kind'] == 'fixtures' and e['season'] >= '2011-2012':
                self.assertNotEqual(e['competition_region'], 'unspecified', e['id'])
        manifest = json.loads((ROOT / 'data/competition-regions.json').read_text())
        pages = {p['url'] for p in manifest['pages']}
        sources = {s['url'] for s in data['sources']}
        for url, context in manifest['links'].items():
            self.assertIn(url, sources)
            self.assertIn(context['page'], pages)
            self.assertTrue(context['heading'])


if __name__ == '__main__':
    unittest.main()
