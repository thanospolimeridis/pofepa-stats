"""The README badges drawn for a release: what they say, their colour and their shape."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from badges import BLUE, GREY, badges, coverage_color, svg, text_width  # noqa: E402

SVG = '{http://www.w3.org/2000/svg}'
MEASURED = [('python', 'Python', 'statements', 'Python statements', {'scripts/a.py': (3, 4), 'scripts/b.py': (0, 2)}),
            ('js', 'JavaScript', 'lines', 'JavaScript lines', {'src/app.js': (199, 200)})]


def parts(image):
    """(width, label box, message box and colour, the two visible texts) of a drawn badge."""
    root = ET.fromstring(image)
    label, message, _ = root.find(f'{SVG}g').findall(f'{SVG}rect')
    texts = [node for node in root.iter(f'{SVG}text') if not node.get('aria-hidden')]
    return int(root.get('width')), label, message, texts


class DrawingTests(unittest.TestCase):
    def test_widths_match_what_badge_makers_measure(self):
        # The label and message widths of the familiar "build | passing" and "coverage" badges.
        self.assertEqual([text_width(text) for text in ('build', 'passing', 'coverage')], [27, 41, 51])
        self.assertEqual(text_width(''), 1)

    def test_a_badge_is_the_label_on_grey_beside_the_message_in_colour(self):
        image = svg('js coverage', '94%', '#97ca00')
        width, label, message, texts = parts(image)
        self.assertEqual((label.get('fill'), message.get('fill')), (GREY, '#97ca00'))
        self.assertEqual(int(label.get('width')) + int(message.get('width')), width)
        self.assertEqual(message.get('x'), label.get('width'))
        self.assertEqual([node.text for node in texts], ['js coverage', '94%'])
        for node, box, offset in zip(texts, (label, message), (0, int(label.get('width')))):
            length, middle = int(node.get('textLength')) / 10, int(node.get('x')) / 10
            self.assertEqual(length + 10, int(box.get('width')), 'five pixels either side of the text')
            self.assertAlmostEqual(middle, offset + int(box.get('width')) / 2, delta=1)
        self.assertEqual(ET.fromstring(image).find(f'{SVG}title').text, 'js coverage: 94%')

    def test_text_is_escaped_wherever_it_lands(self):
        image = svg('a<b', '"x" & y', BLUE)
        root = ET.fromstring(image)
        self.assertEqual(root.get('aria-label'), 'a<b: "x" & y')
        self.assertEqual([node.text for node in parts(image)[3]], ['a<b', '"x" & y'])


class BadgeSetTests(unittest.TestCase):
    def test_coverage_takes_the_usual_steps_from_red_to_bright_green(self):
        steps = {0: '#e05d44', 1: '#dfb317', 79: '#dfb317', 80: '#a4a61d', 89: '#a4a61d', 90: '#97ca00', 99: '#97ca00', 100: '#4c1'}
        self.assertEqual({value: coverage_color(value) for value in steps}, steps)

    def test_a_release_gets_its_number_and_one_coverage_badge_per_language(self):
        drawn = badges(MEASURED, '1.4.2')
        self.assertEqual(sorted(drawn), ['js-coverage.svg', 'python-coverage.svg', 'release.svg'])
        shown = {name: ([node.text for node in parts(image)[3]], parts(image)[2].get('fill')) for name, image in drawn.items()}
        self.assertEqual(shown, {'release.svg': (['release', 'v1.4.2'], BLUE),
                                 'python-coverage.svg': (['python coverage', '50%'], '#dfb317'),
                                 'js-coverage.svg': (['js coverage', '99%'], '#97ca00')})
        self.assertNotIn('release.svg', badges(MEASURED, None), 'a copy without VERSION has no release to name')


if __name__ == '__main__':
    unittest.main()
