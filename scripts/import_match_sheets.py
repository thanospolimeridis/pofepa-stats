#!/usr/bin/env python3
"""Replay source-bound, visually reviewed individual match-sheet results."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path

from collect import Cache, key, uid, parse_fixture_tables
from dataset import load, save
from validate import validate

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/match-sheet-reviews.json'


def discover(data, cache):
    """Attach old parallel-column score links without replacing existing fixtures."""
    sources = {s['id']: s for s in data['sources']}
    fixtures = {f['id']: f for f in data['fixtures']}
    for event in data['events']:
        if event['kind'] != 'fixtures':
            continue
        source = sources[event['sources'][0]]
        url = source['url']
        if not url.endswith('.html'):
            continue
        _, path = cache.get(url, 'a1.html' if url.endswith('/2026-2027-a1.html') else None)
        parsed = parse_fixture_tables(path.read_text(), source['id'], url, event['id'])
        previous = [f for f in data['fixtures'] if f['event'] == event['id']]
        if len(parsed) != len(previous):
            raise ValueError(f'Fixture discovery changed row alignment: {url}')
        for f in parsed:
            old = fixtures[f['id']]
            if any(old[k] != f[k] for k in ('home', 'away', 'score')):
                raise ValueError(f'Fixture discovery changed a result: {url}')
            old['sheet_url'] = f['sheet_url']
    return data


def import_reviews(data, cache, reviews=None):
    reviews = reviews if reviews is not None else json.loads(MANIFEST.read_text())
    fixtures = {f['id']: f for f in data['fixtures']}
    players = {p['id']: p for p in data['players']}
    sources = {s['id']: s for s in data['sources']}
    events = {e['id']: e for e in data['events']}
    by_pair = defaultdict(list)
    for m in data['matches']:
        by_pair[(m['date'], tuple(sorted((m['p1'], m['p2']))))].append(m)
    ranking_proofs = defaultdict(list)
    for snapshot in data['snapshots']:
        if snapshot['list'] == 'ΓΕΝΙΚΟΣ':
            for row in snapshot['rows']:
                ranking_proofs[row[0]].append((snapshot['period'], snapshot['source']))
    report = []
    for url, review in reviews.items():
        sid, path = cache.get(url)
        if hashlib.sha256(path.read_bytes()).hexdigest() != review['sha256']:
            raise ValueError(f'Reviewed match sheet changed: {url}')
        sources[sid] = cache.sources[sid]
        f = fixtures[review['fixture']]
        if f['sheet_url'] != url or f['score'] != review['team_score']:
            raise ValueError(f'Review does not match the team fixture: {url}')
        played = date.fromisoformat(review['date'])
        if played > date.fromisoformat(data['coverage']['as_of']):
            raise ValueError(f'Future match-sheet date: {url}')
        roster = review['players']
        identity_sources = {}
        for person in roster.values():
            p = players[person['id']]
            if person.get('registration') and person['registration'] != p['registration']:
                raise ValueError(f'Match-sheet registration mismatch: {url}')
            if not person['label'] or not ranking_proofs[p['id']]:
                raise ValueError(f'Missing identity evidence: {url}')
            available = [(period, source) for period, source in ranking_proofs[p['id']] if period <= review['date'][:7]]
            if not available:
                raise ValueError(f'No contemporary ranking identity: {url}')
            latest = max(period for period, _ in available)
            identity_sources[p['id']] = sorted({source for period, source in available if period == latest})
        scores = [0, 0]
        rubbers, counts = [], Counter()
        for row in review['rows']:
            number = row['row']
            score = list(row['score'])
            if sorted(score) not in ([0, 3], [1, 3], [2, 3]):
                raise ValueError(f'Invalid match-sheet score: {url} row {number}')
            scores[0 if score[0] > score[1] else 1] += 1
            if row.get('status', 'played') != 'played' or row.get('kind', 'singles') != 'singles':
                counts[row.get('status', 'doubles')] += 1
                rubbers.append({'kind': row.get('kind', 'singles'), 'status': row.get('status', 'played'),
                                'row': number, 'score': score, 'names': [roster[k]['label'] for k in row['players']]})
                continue
            people = [roster[k] for k in row['players']]
            ids = [p['id'] for p in people]
            candidates = by_pair[(review['date'], tuple(sorted(ids)))]
            matches = [m for m in candidates if m['score'] == (score if m['p1'] == ids[0] else score[::-1])]
            if len(matches) > 1 or candidates and not matches:
                raise ValueError(f'Ambiguous existing result: {url} row {number}')
            proof = {'source': sid, 'row': number, 'fixture': f['id'], 'kind': 'match_sheet'}
            if matches:
                m = matches[0]
                if not any(e['source']==sid and e['row']==number for e in m['evidence']) and proof not in m.setdefault('document_evidence', []):
                    m['document_evidence'].append(proof)
                counts['imported' if m.get('origin') == 'match_sheet' else 'corroborated'] += 1
            else:
                base = events[f['event']]
                eid = uid('e-', 'match-sheets:' + f['event'])
                event = events.setdefault(eid, {'id': eid, 'name': base['name'] + ' · Φύλλα αγώνων',
                    'season': base['season'], 'kind': 'singles', 'region': 'national', 'regions': ['national'], 'sources': []})
                if sid not in event['sources']:
                    event['sources'].append(sid)
                m = {'id': uid('m-', f'{sid}:rubber:{number}'), 'date': review['date'], 'event': eid,
                     'region': 'national', 'regions': ['national'], 'p1': ids[0], 'p2': ids[1],
                     'names': [players[p]['name'] for p in ids], 'score': score, 'clubs': f['clubs'],
                     'identity': ['sheet_registration' if p.get('registration') else 'reviewed_sheet_name_and_team' for p in people],
                     'identity_sources': [identity_sources[p] for p in ids], 'source': sid, 'row': number,
                     'evidence': [{**proof, 'region': 'national', 'sheet': 'Φύλλο αγώνα'}], 'origin': 'match_sheet'}
                data['matches'].append(m)
                by_pair[(review['date'], tuple(sorted(ids)))].append(m)
                counts['imported'] += 1
            rubbers.append({'kind': 'singles', 'row': number, 'match': m['id'], 'score': score, 'players': ids})
        if scores != review['team_score']:
            raise ValueError(f'Rubber totals disagree with team score: {url}: {scores}')
        f.update(date=review['date'], rubbers=rubbers, match_sheet_source=sid)
        report.append({'source': sid, 'url': url, 'fixture': f['id'], 'date': review['date'],
                       'season': events[f['event']]['season'], **counts, 'notes': review.get('notes', '')})
    data['sources'] = list(sources.values())
    data['events'] = list(events.values())
    data['matches'].sort(key=lambda m: (m['date'], m['id']), reverse=True)
    c = data['coverage']
    c.update(matches=len(data['matches']), events=len(data['events']),
             match_date_min=min(m['date'] for m in data['matches']), match_date_max=max(m['date'] for m in data['matches']),
             identity_methods=dict(Counter(v for m in data['matches'] for v in m['identity'])))
    linked = {f['sheet_url'] for f in data['fixtures'] if f.get('sheet_url')}
    c['match_sheets'] = {'linked': len(linked), 'reviewed': len(report), 'pending': len(linked - set(reviews)),
                         'imported': sum(r.get('imported', 0) for r in report),
                         'corroborated': sum(r.get('corroborated', 0) for r in report),
                         'excluded_walkovers': sum(r.get('walkover', 0) for r in report), 'reviews': report}
    validate(data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/catalog.json.gz')
    args = parser.parse_args()
    cache = Cache(ROOT / 'capture', offline=args.offline)
    data = load()
    if args.discover:
        discover(data, cache)
    import_reviews(data, cache)
    save(data, args.output)
    print(json.dumps({k:v for k,v in data['coverage']['match_sheets'].items() if k!='reviews'}))


if __name__ == '__main__':
    main()
