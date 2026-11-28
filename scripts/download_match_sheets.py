#!/usr/bin/env python3
"""Cache linked public match sheets; keep downloads resumable and rate limited."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from collect import Cache
from dataset import load

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', help='Season such as 2026-2027 (default: the latest season with linked sheets)')
    args = parser.parse_args()
    data = load()
    events = {e['id']: e for e in data['events']}
    args.season = args.season or max(events[f['event']]['season'] for f in data['fixtures'] if f.get('sheet_url'))
    urls = sorted({f['sheet_url'] for f in data['fixtures'] if f.get('sheet_url')
                   and events[f['event']]['season'] == args.season})
    def fetch(url):
        cache = Cache(ROOT / 'capture')
        try:
            sid, path = cache.get(url)
            return {'url': url, 'path': str(path), 'source': cache.sources[sid]}
        except Exception as error:
            return {'url': url, 'error': str(error)}
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, url) for url in urls]):
            results.append(future.result())
            if len(results) % 25 == 0:
                print(f'Cached {len(results)}/{len(urls)} sheets', flush=True)
    target = ROOT / 'capture' / f'match-sheet-downloads-{args.season}.json'
    target.write_text(json.dumps(sorted(results, key=lambda r:r['url']), ensure_ascii=False, indent=2))
    print(f'{len(results)} sheets; {sum("error" in r for r in results)} unavailable. {target}')


if __name__ == '__main__':
    main()
