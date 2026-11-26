"""Source fidelity and lazy/offline packaging for original cup drawings."""
import gzip
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from competition_regions import attach_regions
from cup_draws import attach_draws
from dataset import load
from build import bootstrap_data


class CupDrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        attach_regions(cls.data)
        attach_draws(cls.data)

    def test_every_pdf_cup_has_all_source_pages_and_matching_provenance(self):
        self.assertEqual(len(self.data['cup_draws']), 103)
        sources = {s['id']: s for s in self.data['sources']}
        total = 0
        for event in self.data['events']:
            if 'draw_archive' not in event:
                continue
            self.assertEqual(event['competition_type'], 'cup')
            draw = self.data['cup_draws'][event['id']]
            for source in draw['sources']:
                self.assertEqual(source['sha256'], sources[source['id']]['sha256'])
            self.assertTrue(draw['pages'])
            for page in draw['pages']:
                total += 1
                self.assertGreater(page['width'], 0)
                self.assertGreater(page['height'], 0)
                for link in page['links']:
                    self.assertTrue(link['url'].startswith(('https://', 'http://')))
                    self.assertEqual(len(link['bbox']), 4)
                    self.assertGreater(link['bbox'][2], link['bbox'][0])
                    self.assertGreater(link['bbox'][3], link['bbox'][1])
                svg = ET.fromstring(page['svg'])
                self.assertTrue(svg.tag.endswith('svg'))
                for node in svg.iter():
                    self.assertNotIn(node.tag.split('}')[-1], ('script', 'foreignObject', 'a'))
                    for attr, value in node.attrib.items():
                        self.assertFalse(attr.startswith('on'))
                        if attr.endswith('href'):
                            self.assertTrue(value.startswith(('#', 'data:image/')), value)
        self.assertEqual(total, 131)
        self.assertEqual(len(self.data['cup_draws']['e-872537db429e91ee']['pages'][0]['links']), 24)

    def test_draws_stay_out_of_initial_download(self):
        bootstrap = bootstrap_data(self.data)
        self.assertNotIn('cup_draws', bootstrap)
        self.assertTrue(any('draw_archive' in e for e in bootstrap['events']))

    def test_changed_source_requires_regeneration(self):
        data = load()
        attach_regions(data)
        source = next(s for s in data['sources'] if s['id'] == 's-872537db429e91ee')
        source['sha256'] = 'different-source-bytes'
        with self.assertRaisesRegex(ValueError, 'Cup source changed'):
            attach_draws(data)


if __name__ == '__main__':
    unittest.main()
