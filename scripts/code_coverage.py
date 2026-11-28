#!/usr/bin/env python3
"""Report how much of the code the checks execute: the project's test coverage.

Elsewhere in this project "coverage" means how much of the source archive is
imported (coverage.json, the Coverage & sources page). This script is about the
code: which statements of scripts/*.py and which lines of src/*.js ran while
scripts/check_all.sh was recording.

    COVERAGE=.qa/coverage scripts/check_all.sh       record, then print the report
    python3 scripts/code_coverage.py .qa/coverage    print it again
        --markdown                                   as Markdown tables (the CI job summary)

Python is measured by coverage.py, in executable statements. JavaScript comes from
V8's block coverage (NODE_V8_COVERAGE), counted the way c8 counts lines: every
line of the file counts, and a line is missed when it lies wholly inside a block
that never ran. The two figures are reported side by side and never added up.
"""
import argparse
import bisect
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PYTHON_DATA = 'python'  # the coverage.py data file inside a recording
V8_DATA = 'v8'          # the folder Node fills through NODE_V8_COVERAGE


class CoverageError(Exception):
    pass


def python_coverage(recording, root=ROOT):
    """{path: (statements run, statements)} for every Python file under scripts/."""
    import coverage  # needed only to read a recording, so the report's helpers import without it

    data_file = Path(recording) / PYTHON_DATA
    if not data_file.is_file():
        raise CoverageError(f'there is no Python recording at {data_file}')
    reader = coverage.Coverage(data_file=str(data_file), config_file=False)
    reader.load()
    recorded = {Path(name).resolve(): name for name in reader.get_data().measured_files()}
    result = {}
    for path in sorted((root / 'scripts').rglob('*.py')):
        name = path.relative_to(root).as_posix()
        if path.resolve() not in recorded:
            raise CoverageError(f'{name} is missing from the Python recording')
        _, statements, _, missing, _ = reader.analysis2(recorded[path.resolve()])
        result[name] = (len(statements) - len(missing), len(statements))
    return result


def units(text):
    """Length in UTF-16 code units, which is how V8 counts positions."""
    return len(text.encode('utf-16-le')) // 2


def line_spans(text):
    """Where every line starts and ends, and the length of the whole text.

    A line's end leaves out its line break, as c8 does, so a block that closes
    where the line's text stops still contains the line.
    """
    starts, ends, position = [], [], 0
    for line in re.split(r'(?<=\n)', text):
        if line:
            starts.append(position)
            ends.append(position + units(re.sub(r'\r?\n\Z', '', line)))
            position += units(line)
    return starts, ends, position


def lines_run(text, functions):
    """Whether each line ran, for one script as V8 recorded it.

    Every line starts as run. Blocks are applied from the outermost in, so a line
    ends with the count of the smallest block that wholly contains it.
    """
    starts, ends, length = line_spans(text)
    blocks = sorted((block for function in functions for block in function['ranges']),
                    key=lambda block: (block['startOffset'], -block['endOffset']))
    # V8 records the whole script as its outermost block; anything else is another text.
    if not blocks or (blocks[0]['startOffset'], blocks[0]['endOffset']) != (0, length):
        raise CoverageError('the recorded script is not the text of the file')
    counts = [1] * len(starts)
    for block in blocks:
        first = bisect.bisect_left(starts, block['startOffset'])
        last = bisect.bisect_right(ends, block['endOffset'])
        for index in range(first, last):
            counts[index] = block['count']
    return [count > 0 for count in counts]


def javascript_coverage(recording, root=ROOT):
    """{path: (lines run, lines)} for every src/*.js, over every recorded Node process.

    A file loaded by several suites, or several times by one, appears once per
    script V8 compiled; a line counts as run when any of them ran it.
    """
    folder = Path(recording) / V8_DATA
    reports = sorted(folder.glob('*.json'))
    if not reports:
        raise CoverageError(f'there is no Node recording in {folder}')
    files = {path.resolve(): path.relative_to(root).as_posix() for path in sorted((root / 'src').glob('*.js'))}
    # Bytes, not read_text: universal newlines would shift every position after a CRLF.
    texts = {path: path.read_bytes().decode('utf-8') for path in files}
    run = {}
    for report in reports:
        for script in json.loads(report.read_bytes())['result']:
            url = urlsplit(script['url'])
            path = Path(unquote(url.path)).resolve() if url.scheme == 'file' else None
            if path not in files:
                continue
            try:
                seen = lines_run(texts[path], script['functions'])
            except CoverageError as error:
                raise CoverageError(f'{files[path]}: {error}; it changed after the recording, '
                                    'or a suite ran other text under its name') from None
            run[path] = [a or b for a, b in zip(run.get(path, seen), seen)]
    result = {}
    for path, name in files.items():
        if path not in run:
            raise CoverageError(f'{name} is missing from the Node recording: no suite loaded it under its file name')
        result[name] = (sum(run[path]), len(run[path]))
    return result


LANGUAGES = (
    # key, name, unit, heading, reader
    ('python', 'Python', 'statements', 'Python statements, by coverage.py', python_coverage),
    ('js', 'JavaScript', 'lines', 'JavaScript lines, by V8 as c8 counts', javascript_coverage),
)


def measure(recording, root=ROOT):
    """[(key, name, unit, heading, {path: (run, total)})] for a recording made by check_all.sh."""
    return [(key, name, unit, heading, reader(recording, root)) for key, name, unit, heading, reader in LANGUAGES]


def total(files):
    return tuple(sum(column) for column in zip(*files.values())) if files else (0, 0)


def percent(run, out_of):
    """Whole percent, rounded down so the figure never overstates; no code counts as all run."""
    return 100 * run // out_of if out_of else 100


def text_report(measured):
    width = max(len(text) for _, _, _, heading, files in measured for text in (heading, *files)) + 2
    lines = ['Test coverage: the code scripts/check_all.sh ran', '']
    for _, name, unit, heading, files in measured:
        lines.append(f'{heading:<{width + 2}}{"run":>7}{"of":>8}')
        for path, (run, out_of) in files.items():
            lines.append(f'  {path:<{width}}{run:>7}{out_of:>8}{percent(run, out_of):>6}%')
        run, out_of = total(files)
        lines += [f'  {name:<{width}}{run:>7}{out_of:>8}{percent(run, out_of):>6}%', '']
    return '\n'.join(lines)


def markdown_report(measured):
    lines = ['### Test coverage', '',
             'The code `scripts/check_all.sh` ran. Python is counted in statements, JavaScript in lines; '
             'the two are not added up.', '']
    for _, name, unit, heading, files in measured:
        run, out_of = total(files)
        lines += [f'| {heading} | Run | {unit.capitalize()} | |', '| --- | ---: | ---: | ---: |',
                  f'| **{name}** | **{run:,}** | **{out_of:,}** | **{percent(run, out_of)}%** |']
        lines += [f'| `{path}` | {run:,} | {out_of:,} | {percent(run, out_of)}% |' for path, (run, out_of) in files.items()]
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('recording', type=Path, help='the folder COVERAGE named when scripts/check_all.sh ran')
    parser.add_argument('--markdown', action='store_true', help='print Markdown tables instead of plain text')
    args = parser.parse_args()
    try:
        measured = measure(args.recording)
    except CoverageError as error:
        raise SystemExit(f'No test coverage report: {error}.')
    print(markdown_report(measured) if args.markdown else text_report(measured))


if __name__ == '__main__':
    main()
