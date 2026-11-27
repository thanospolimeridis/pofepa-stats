#!/usr/bin/env python3
"""Re-read cached HTML fixture pages with the current parser.

Fixtures the parser still produces unchanged keep their catalog record, with any
match-sheet date, rubbers and links. New fixtures, and fixtures whose teams or
score changed, are taken from the parser. A fixture that carries match-sheet
results, or that a review or availability record cites, is never changed or
dropped. Bye lines (a dash opposite a team) keep no club. Held match sheets are
re-pointed to the one fixture that links them, and sheet coverage is recomputed.
Repeated runs change nothing.
"""
import argparse
import json
from pathlib import Path

from collect import Cache, parse_fixture_tables, uid
from dataset import load, save
from import_match_sheets import ISSUES, MANIFEST, UNAVAILABLE, import_reviews
from validate import BYE, validate

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ('rubbers', 'date', 'match_sheet_source')


def same_result(a, b):
    return (a['home'], a['away'], a['score']) == (b['home'], b['away'], b['score'])


def refresh(data, cache, issues):
    reviews = json.loads(MANIFEST.read_text())
    unavailable = json.loads(UNAVAILABLE.read_text())
    cited = {item['fixture'] for item in [*reviews.values(), *unavailable.values()]}
    sources = {s['id']: s for s in data['sources']}
    clubs = {c['id']: c for c in data['clubs']}

    def club(name):
        if name in BYE:
            return ''
        cid = uid('c-', name)
        clubs.setdefault(cid, {'id': cid, 'name': name})
        return cid

    def guard(fixture):
        if fixture['id'] in cited or any(fixture.get(k) for k in PROTECTED):
            raise ValueError(f'Refusing to change a fixture with match-sheet results: {fixture["id"]}')

    refreshed, summary = {}, {'events': 0, 'added': 0, 'changed': 0}
    for event in data['events']:
        url = sources[event['sources'][0]]['url']
        if event['kind'] != 'fixtures' or not url.endswith('.html'):
            continue
        _, path = cache.get(url, 'a1.html' if url.endswith('/2026-2027-a1.html') else None)
        parsed = parse_fixture_tables(path.read_text(), event['sources'][0], url, event['id'])
        old = {f['id']: f for f in data['fixtures'] if f['event'] == event['id']}
        rows, ids = [], {f['id'] for f in parsed}
        for gone in set(old) - ids:
            guard(old[gone])
        for fixture in parsed:
            previous = old.get(fixture['id'])
            if previous and same_result(previous, fixture):
                rows.append(previous)
                continue
            if previous:
                guard(previous)
                summary['changed'] += 1
            else:
                summary['added'] += 1
            fixture['clubs'] = [club(fixture['home']), club(fixture['away'])]
            rows.append(fixture)
        if len(rows) != len(old) or any(a is not b for a, b in zip(rows, old.values())):
            summary['events'] += 1
        refreshed[event['id']] = rows
    fixtures, placed = [], set()
    for fixture in data['fixtures']:
        event = fixture['event']
        if event not in refreshed:
            fixtures.append(fixture)
        elif event not in placed:
            fixtures.extend(refreshed[event])
            placed.add(event)
    for fixture in fixtures:  # byes as collect.py records them: the dash has no club
        fixture['clubs'] = ['' if name in BYE else cid for name, cid in zip((fixture['home'], fixture['away']), fixture['clubs'])]
    data['fixtures'] = fixtures
    linking = {}
    for fixture in fixtures:
        if fixture.get('sheet_url'):
            linking.setdefault(fixture['sheet_url'], []).append(fixture['id'])
    for url, issue in issues.items():
        if len(linking.get(url, [])) != 1:
            raise ValueError(f'Held match sheet is not linked by exactly one fixture: {url}')
        issue['fixture'] = linking[url][0]
    referenced = {p.get('club') for p in data['players']}
    referenced.update(c for m in data['matches'] for c in m['clubs'])
    referenced.update(c for f in fixtures for c in f['clubs'])
    referenced.update(row[3] for snapshot in data['snapshots'] for row in snapshot['rows'])
    data['clubs'] = [c for cid, c in clubs.items() if cid in referenced]
    data['coverage'].update(fixtures=len(fixtures), reported_fixtures=sum(f['status'] == 'reported' for f in fixtures))
    import_reviews(data, cache, reviews=reviews, issues=issues, unavailable=unavailable)
    validate(data)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--cache', type=Path, default=ROOT / 'capture')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/catalog.json.gz')
    parser.add_argument('--issues-output', type=Path, default=ISSUES)
    args = parser.parse_args()
    data, issues = load(), json.loads(ISSUES.read_text())
    summary = refresh(data, Cache(args.cache, offline=args.offline), issues)
    save(data, args.output)
    args.issues_output.write_text(json.dumps(issues, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({**summary, 'fixtures': data['coverage']['fixtures'], 'reported': data['coverage']['reported_fixtures'],
                      **{k: data['coverage']['match_sheets'][k] for k in ('linked', 'held', 'pending')}}))


if __name__ == '__main__':
    main()
