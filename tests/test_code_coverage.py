"""The test coverage report: how lines are counted, merged across processes and shown."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import coverage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from code_coverage import (CoverageError, javascript_coverage, line_spans, lines_run,  # noqa: E402
                           markdown_report, measure, percent, python_coverage, text_report)

# Five lines; `never` and the `else` block do not run.
SCRIPT = ('const ran = 1;\n'
          'function never() {\n'
          '  return 2;\n'
          '}\n'
          'if (ran) { one(); } else { two(); }\n')
NEVER = (SCRIPT.index('function'), SCRIPT.index('}') + 1)
ELSE = (SCRIPT.index('{ two'), SCRIPT.rindex('}') + 1)


def function(name, *blocks):
    return {'functionName': name, 'isBlockCoverage': True,
            'ranges': [{'startOffset': start, 'endOffset': end, 'count': count} for start, end, count in blocks]}


def recorded(text=SCRIPT, never=0):
    """V8's view of SCRIPT: the whole script once, `never` called `never` times, the else block not at all."""
    return [function('', (0, len(text), 1), (*ELSE, 0)), function('never', (*NEVER, never))]


def site(folder, **sources):
    """A project root holding src/ files, and the folder a recording of it goes into."""
    root = Path(folder) / 'project'
    (root / 'src').mkdir(parents=True)
    (root / 'scripts').mkdir()
    for name, text in sources.items():
        (root / 'src' / name).write_bytes(text.encode('utf-8'))
    recording = Path(folder) / 'recording'
    (recording / 'v8').mkdir(parents=True)
    return root, recording


def node_process(recording, number, *scripts):
    result = [{'scriptId': str(index), 'url': url, 'functions': functions} for index, (url, functions) in enumerate(scripts)]
    (recording / 'v8' / f'coverage-{number}-0-0.json').write_text(json.dumps({'result': result}))


class LineTests(unittest.TestCase):
    def test_positions_are_utf16_units_and_line_ends_leave_out_the_break(self):
        self.assertEqual(line_spans('ab\r\nγδ\n\n😀x'), ([0, 4, 7, 8], [2, 6, 7, 11], 11))
        self.assertEqual(line_spans(''), ([], [], 0))
        self.assertEqual(line_spans('one line, no break'), ([0], [18], 18))

    def test_a_line_is_missed_only_when_a_block_that_never_ran_holds_all_of_it(self):
        # The function's first line starts before the block; the last line only loses its else half.
        self.assertEqual(lines_run(SCRIPT, recorded()), [True, False, False, False, True])
        self.assertEqual(lines_run(SCRIPT, recorded(never=3)), [True] * 5)

    def test_the_smallest_enclosing_block_decides_whatever_order_v8_lists_them_in(self):
        text = 'function outer() {\n  if (x) {\n    inner();\n  }\n  after();\n}\n'
        whole, outer = (0, len(text), 1), (0, text.rindex('}') + 1)
        skipped = (text.index('{\n    inner'), text.index('  }\n') + 3)  # the if block, brace to brace
        functions = [function('', whole), function('outer', (*outer, 4), (*skipped, 0))]
        expected = [True, True, False, False, True, True]
        self.assertEqual(lines_run(text, functions), expected)
        self.assertEqual(lines_run(text, functions[::-1]), expected)
        self.assertEqual(lines_run(text, [function('', whole), function('outer', (*outer, 0))]), [False] * 6)

    def test_a_recording_of_other_text_is_refused(self):
        for functions in ([], [function('', (0, len(SCRIPT) - 1, 1))], [function('', (1, len(SCRIPT), 1))]):
            with self.assertRaisesRegex(CoverageError, 'not the text of the file'):
                lines_run(SCRIPT, functions)


class JavaScriptTests(unittest.TestCase):
    def test_processes_and_repeated_scripts_merge_into_lines_any_of_them_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, recording = site(tmp, **{'app.js': SCRIPT, 'core.js': 'a();\n'})
            app, core = ((root / 'src' / name).resolve().as_uri() for name in ('app.js', 'core.js'))
            node_process(recording, 1, (app, recorded()), (core, [function('', (0, 5, 1))]),
                         ('node:internal/vm', [function('', (0, 9, 1))]), ('evalmachine.<anonymous>', recorded()),
                         ((root / 'tests' / 'smoke.js').as_uri(), recorded()))
            self.assertEqual(javascript_coverage(recording, root), {'src/app.js': (2, 5), 'src/core.js': (1, 1)})
            # A second process, and a second copy of the script in it, called the function.
            node_process(recording, 2, (app, recorded()), (app, recorded(never=1)))
            self.assertEqual(javascript_coverage(recording, root), {'src/app.js': (5, 5), 'src/core.js': (1, 1)})

    def test_a_file_no_suite_loaded_by_name_fails_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, recording = site(tmp, **{'app.js': SCRIPT, 'core.js': 'a();\n'})
            with self.assertRaisesRegex(CoverageError, 'no Node recording'):
                javascript_coverage(recording, root)
            node_process(recording, 1, ((root / 'src' / 'app.js').resolve().as_uri(), recorded()))
            with self.assertRaisesRegex(CoverageError, 'src/core.js is missing'):
                javascript_coverage(recording, root)

    def test_a_file_edited_after_the_recording_fails_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, recording = site(tmp, **{'app.js': SCRIPT + '// edited\n'})
            node_process(recording, 1, ((root / 'src' / 'app.js').resolve().as_uri(), recorded()))
            with self.assertRaisesRegex(CoverageError, 'src/app.js: .*changed after the recording'):
                javascript_coverage(recording, root)

    def test_line_breaks_are_read_as_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = SCRIPT.replace('\n', '\r\n')
            root, recording = site(tmp, **{'app.js': text})
            start, end = text.index('function'), text.index('}') + 1
            functions = [function('', (0, len(text), 1)), function('never', (start, end, 0))]
            node_process(recording, 1, ((root / 'src' / 'app.js').resolve().as_uri(), functions))
            self.assertEqual(javascript_coverage(recording, root), {'src/app.js': (2, 5)})


class PythonTests(unittest.TestCase):
    def record(self, recording, lines):
        """Add to a recording as `coverage run --append` does: real paths, earlier data kept."""
        data = coverage.CoverageData(basename=str(recording / 'python'))
        data.read()
        data.add_lines({str(path.resolve()): numbers for path, numbers in lines.items() if numbers})
        for path, numbers in lines.items():
            if not numbers:
                data.touch_file(str(path.resolve()))
        data.write()

    def test_statements_run_are_counted_per_script_and_unrun_scripts_count_in_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, recording = site(tmp)
            used, unused = root / 'scripts' / 'used.py', root / 'scripts' / 'hooks' / 'unused.py'
            unused.parent.mkdir()
            used.write_text('a = 1\n\n# a comment\nif a:\n    b = 2\nelse:\n    b = 3\n')
            unused.write_text('c = 1\nd = 2\n')
            with self.assertRaisesRegex(CoverageError, 'no Python recording'):
                python_coverage(recording, root)
            self.record(recording, {used: [1, 4, 5]})
            with self.assertRaisesRegex(CoverageError, 'scripts/hooks/unused.py is missing'):
                python_coverage(recording, root)
            self.record(recording, {unused: []})
            self.assertEqual(python_coverage(recording, root), {'scripts/hooks/unused.py': (0, 2), 'scripts/used.py': (3, 4)})


class ReportTests(unittest.TestCase):
    MEASURED = [('python', 'Python', 'statements', 'Python statements', {'scripts/a.py': (3, 4), 'scripts/b.py': (0, 2)}),
                ('js', 'JavaScript', 'lines', 'JavaScript lines', {'src/app.js': (199, 200)})]

    def test_percentages_round_down_and_only_everything_is_a_hundred(self):
        self.assertEqual([percent(*pair) for pair in ((199, 200), (200, 200), (1, 300), (0, 5), (0, 0))], [99, 100, 0, 0, 100])

    def test_reports_list_every_file_and_a_total_per_language(self):
        text, markdown = text_report(self.MEASURED), markdown_report(self.MEASURED)
        for row in (r'scripts/a\.py +3 +4 +75%', r'scripts/b\.py +0 +2 +0%', r'Python +3 +6 +50%',
                    r'src/app\.js +199 +200 +99%', r'JavaScript +199 +200 +99%'):
            self.assertRegex(text, rf'(?m)^  {row}$')
        self.assertEqual(len({line.rindex('%') for line in text.splitlines() if line.endswith('%')}), 1, 'columns line up')
        for line in ('| Python statements | Run | Statements | |', '| **Python** | **3** | **6** | **50%** |',
                     '| `scripts/b.py` | 0 | 2 | 0% |',
                     '| JavaScript lines | Run | Lines | |', '| **JavaScript** | **199** | **200** | **99%** |'):
            self.assertIn(line + '\n', markdown)

    def test_a_recording_is_read_for_both_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, recording = site(tmp, **{'app.js': SCRIPT})
            node_process(recording, 1, ((root / 'src' / 'app.js').resolve().as_uri(), recorded()))
            script = root / 'scripts' / 'tool.py'
            script.write_text('a = 1\nb = 2\n')
            PythonTests.record(self, recording, {script: [1]})
            self.assertEqual([(key, files) for key, _, _, _, files in measure(recording, root)],
                             [('python', {'scripts/tool.py': (1, 2)}), ('js', {'src/app.js': (2, 5)})])


if __name__ == '__main__':
    unittest.main()
