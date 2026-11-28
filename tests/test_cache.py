"""The source cache never loses bytes, and the collector fails closed."""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collect  # noqa: E402
from collect import Cache, SourceUnavailable  # noqa: E402

URL = 'https://www.pofepa.gr/2026-2027-a1.html'


class Response:
    def __init__(self, body, final=URL):
        self.body, self.final = body, final

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.final

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.sleep = mock.patch.object(collect.time, 'sleep')
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()

    def seed(self, body=b'reviewed bytes'):
        path = self.dir / 'page.html'
        path.write_bytes(body)
        (self.dir / 'page.html.meta.json').write_text(json.dumps({'url': URL, 'retrieved_at': '2026-11-26T08:00:00+00:00'}))
        return path

    def test_refresh_replaces_atomically_and_keeps_the_previous_bytes(self):
        path = self.seed()
        with mock.patch.object(collect, 'urlopen', return_value=Response(b'new bytes')):
            sid, got = Cache(self.dir, refresh=True).get(URL, 'page.html')
        self.assertEqual(got.read_bytes(), b'new bytes')
        kept = list((self.dir / 'replaced').glob('page.html.*'))
        self.assertIn(b'reviewed bytes', [p.read_bytes() for p in kept])
        self.assertTrue(any(p.name.endswith('.meta.json') for p in kept), 'previous retrieval metadata is kept')
        self.assertFalse(list(self.dir.glob('*.part')), 'no partial files remain')

    def test_unchanged_refresh_keeps_nothing_extra(self):
        self.seed(b'same')
        with mock.patch.object(collect, 'urlopen', return_value=Response(b'same')):
            Cache(self.dir, refresh=True).get(URL, 'page.html')
        self.assertFalse((self.dir / 'replaced').exists())

    def test_failed_refresh_falls_back_to_the_cached_copy(self):
        path = self.seed()
        with mock.patch.object(collect, 'urlopen', side_effect=URLError('offline')), mock.patch('sys.stderr'):
            sid, got = Cache(self.dir, refresh=True).get(URL, 'page.html')
        self.assertEqual(got.read_bytes(), b'reviewed bytes')

    def test_uncached_source_that_cannot_be_fetched_is_unavailable(self):
        error = HTTPError(URL, 404, 'Not Found', None, None)
        with mock.patch.object(collect, 'urlopen', side_effect=error):
            with self.assertRaises(SourceUnavailable):
                Cache(self.dir).get(URL, 'page.html')

    def test_redirect_to_an_unapproved_host_is_refused(self):
        with mock.patch.object(collect, 'urlopen', return_value=Response(b'x', 'https://example.com/page.html')):
            with self.assertRaisesRegex(ValueError, 'unapproved'):
                Cache(self.dir).get(URL, 'page.html')
        self.assertFalse((self.dir / 'page.html').exists())

    def test_oversized_source_is_refused(self):
        with mock.patch.object(collect, 'MAX_SOURCE_BYTES', 4), mock.patch.object(collect, 'urlopen', return_value=Response(b'12345')):
            with self.assertRaisesRegex(ValueError, 'larger'):
                Cache(self.dir).get(URL, 'page.html')

    def test_offline_gap_is_an_error_not_an_unavailable_source(self):
        with self.assertRaises(FileNotFoundError) as caught:
            Cache(self.dir, offline=True).get(URL, 'page.html')
        self.assertNotIsInstance(caught.exception, SourceUnavailable)


class FakeCache:
    """Serves a ranking index with no workbooks and one season linking one PDF."""
    def __init__(self, unavailable=False):
        self.unavailable, self.sources = unavailable, {}
        self.dir = Path(tempfile.mkdtemp())

    def get(self, url, filename=None):
        if url.endswith('.pdf') and self.unavailable:
            raise SourceUnavailable(f'{url}: HTTP 404')
        path = self.dir / (filename or 'source' + Path(url).suffix)
        if url == collect.RANKINGS:
            path.write_text('<html></html>')
        elif url == collect.SEASON:
            path.write_text('<html><body><a href="https://www.pofepa.gr/2026-2027.html">Αποτελεσματα</a>'
                            '<a href="https://www.pofepa.gr/cup.pdf">Κύπελλο</a></body></html>')
        else:
            path.write_bytes(b'%PDF-1.4')
        sid = collect.uid('s-', url)
        self.sources[sid] = {'id': sid, 'url': url, 'retrieved_at': '', 'sha256': '0' * 64, 'bytes': 0}
        return sid, path


class CollectorFailsClosedTests(unittest.TestCase):
    def run_collect(self, cache):
        with mock.patch.object(collect, 'seasons', return_value=[('2026-2027', collect.SEASON)]), \
             mock.patch.object(collect, 'content_links', return_value=[('Κύπελλο', 'https://www.pofepa.gr/cup.pdf')]), \
             mock.patch.object(collect, 'regional_links', return_value={}), \
             mock.patch('import_match_sheets.import_reviews'):  # match-sheet replay needs the real catalog
            return collect.collect(cache, date(2026, 11, 26))

    def test_changed_reviewed_document_stops_the_collection(self):
        error = ValueError('Document changed since visual review; transcription must be checked again')
        with mock.patch.object(collect, 'extract_document', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'changed since visual review'):
                self.run_collect(FakeCache())

    def test_missing_pdf_tool_stops_the_collection(self):
        with mock.patch.object(collect, 'extract_document', side_effect=FileNotFoundError('pdftotext')):
            with self.assertRaises(FileNotFoundError):
                self.run_collect(FakeCache())

    def test_only_an_unavailable_source_is_deferred(self):
        data = self.run_collect(FakeCache(unavailable=True))
        self.assertEqual([(d['url'], d['reason']) for d in data['coverage']['deferred']],
                         [('https://www.pofepa.gr/cup.pdf', 'source_unavailable')])


if __name__ == '__main__':
    unittest.main()
