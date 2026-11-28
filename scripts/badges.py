#!/usr/bin/env python3
"""Draw the README badges that GitHub does not draw itself, for the release being published.

    python3 scripts/badges.py RECORDING FOLDER

writes into FOLDER (dist/badges in the publish workflow):

    release.svg            the version in VERSION
    python-coverage.svg    how much of scripts/ the checks ran
    js-coverage.svg        how much of src/*.js the checks ran

RECORDING is the folder COVERAGE named when scripts/check_all.sh ran (see
scripts/code_coverage.py). The badges are plain SVG in the usual flat style and
are served with the site, so the README depends on no badge service. Its other
two badges, "Checks" and "Publish GitHub Pages", are drawn by GitHub Actions.
"""
import argparse
from html import escape
from pathlib import Path

from build import read_version
from code_coverage import CoverageError, measure, percent, total

GREY, BLUE = '#555', '#007ec6'
# From this share of the code upwards, this colour: the steps shields.io applies to coverage.
COVERAGE_COLORS = ((100, '#4c1'), (90, '#97ca00'), (80, '#a4a61d'), (1, '#dfb317'), (0, '#e05d44'))
# Advance widths of Verdana at 11px, the face flat badges are set in. textLength pins each
# text to this estimate, so a reader without the face sees other letter spacing, not a spill.
WIDTHS = {' ': 3.87, '%': 11.84, '-': 5.0, '.': 4.0, **{digit: 6.99 for digit in '0123456789'},
          'a': 6.61, 'b': 6.85, 'c': 5.73, 'd': 6.85, 'e': 6.55, 'f': 3.87, 'g': 6.85, 'h': 6.96, 'i': 3.02,
          'j': 3.79, 'k': 6.51, 'l': 3.02, 'm': 10.7, 'n': 6.96, 'o': 6.68, 'p': 6.85, 'q': 6.85, 'r': 4.69,
          's': 5.73, 't': 4.33, 'u': 6.96, 'v': 6.51, 'w': 9.0, 'x': 6.51, 'y': 6.51, 'z': 5.78}
OTHER_WIDTH = 7.5  # capitals and anything else, on average


def text_width(text):
    """Whole pixels the text takes, made odd so it centres on a pixel, as badge makers do."""
    width = int(sum(WIDTHS.get(character, OTHER_WIDTH) for character in text))
    return width if width % 2 else width + 1


def svg(label, message, color):
    """A flat two-part badge: the label on grey, the message on the given colour."""
    label_text, message_text = text_width(label), text_width(message)
    left, right = label_text + 10, message_text + 10
    name = escape(f'{label}: {message}')

    def text(content, middle, length):
        place = f'x="{round(middle * 10)}" transform="scale(.1)" textLength="{length * 10}"'
        return (f'<text aria-hidden="true" {place} y="150" fill="#010101" fill-opacity=".3">{escape(content)}</text>'
                f'<text {place} y="140">{escape(content)}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{left + right}" height="20" role="img" aria-label="{name}">'
            f'<title>{name}</title>'
            '<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
            '<stop offset="1" stop-opacity=".1"/></linearGradient>'
            f'<clipPath id="r"><rect width="{left + right}" height="20" rx="3" fill="#fff"/></clipPath>'
            f'<g clip-path="url(#r)"><rect width="{left}" height="20" fill="{GREY}"/>'
            f'<rect x="{left}" width="{right}" height="20" fill="{color}"/>'
            f'<rect width="{left + right}" height="20" fill="url(#s)"/></g>'
            '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
            'text-rendering="geometricPrecision" font-size="110">'
            f'{text(label, left / 2 + 1, label_text)}{text(message, left + right / 2 - 1, message_text)}'
            '</g></svg>\n')


def coverage_color(value):
    return next(color for floor, color in COVERAGE_COLORS if value >= floor)


def badges(measured, version):
    """{file name: svg} for a release: its number, and its test coverage per language."""
    drawn = {'release.svg': svg('release', f'v{version}', BLUE)} if version else {}
    for key, _, _, _, files in measured:
        value = percent(*total(files))
        drawn[f'{key}-coverage.svg'] = svg(f'{key} coverage', f'{value}%', coverage_color(value))
    return drawn


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('recording', type=Path, help='the folder COVERAGE named when scripts/check_all.sh ran')
    parser.add_argument('folder', type=Path, help='where to write the badges, such as dist/badges')
    args = parser.parse_args()
    try:
        drawn = badges(measure(args.recording), read_version())
    except CoverageError as error:
        raise SystemExit(f'No badges: {error}.')
    args.folder.mkdir(parents=True, exist_ok=True)
    for name, image in drawn.items():
        (args.folder / name).write_text(image, encoding='utf-8')
    print(f'Drew {", ".join(sorted(drawn))} in {args.folder}.')


if __name__ == '__main__':
    main()
