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
from reconcile_match_sheets import reconcile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/match-sheet-reviews.json'
ISSUES = ROOT / 'data/match-sheet-issues.json'
UNAVAILABLE = ROOT / 'data/match-sheet-unavailable.json'


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
        _, path = cache.get(url)
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


def same_day_identity(review, fixture, roster, person, player, proof, by_pair):
    """Permit evidence attachment to an existing provisional's first-day results.

    Every played row must already exist exactly once, with the same date,
    opponents, score and oriented clubs. This path cannot introduce singles.
    """
    if not proof or proof['date'] != review['date'] or not player.get('provisional') or player.get('club') not in fixture['clubs']:
        return False
    matched_ids = set()
    for row in review['rows']:
        if row.get('status', 'played') != 'played':
            continue
        ids = [roster[k].get('id') for k in row['players']]
        if None in ids:
            return False
        candidates = by_pair.get((review['date'], tuple(sorted(ids))), [])
        if len(candidates) != 1:
            return False
        match = candidates[0]
        forward = match['p1'] == ids[0]
        if match['score'] != (row['score'] if forward else row['score'][::-1]) or match['clubs'] != (fixture['clubs'] if forward else fixture['clubs'][::-1]):
            return False
        if player['id'] in ids:
            matched_ids.add(match['id'])
    return proof['id'] in matched_ids


def import_reviews(data, cache, reviews=None, issues=None, unavailable=None):
    if unavailable is None:
        unavailable = json.loads(UNAVAILABLE.read_text()) if reviews is None and UNAVAILABLE.exists() else {}
    if issues is None:
        issues = json.loads(ISSUES.read_text()) if reviews is None and ISSUES.exists() else {}
    reviews = reviews if reviews is not None else json.loads(MANIFEST.read_text())
    if set(reviews) & set(issues):
        raise ValueError('A match sheet cannot be both imported and held for review')
    reconcile(data, cache, reviews)
    fixtures = {f['id']: f for f in data['fixtures']}
    players = {p['id']: p for p in data['players']}
    sources = {s['id']: s for s in data['sources']}
    events = {e['id']: e for e in data['events']}
    by_pair = defaultdict(list)
    matches_by_id = {m['id']:m for m in data['matches']}
    for m in data['matches']:
        by_pair[(m['date'], tuple(sorted((m['p1'], m['p2']))))].append(m)
    ranking_proofs = defaultdict(list)
    for snapshot in data['snapshots']:
        if snapshot['list'] == 'ΓΕΝΙΚΟΣ':
            for row in snapshot['rows']:
                ranking_proofs[row[0]].append((snapshot['period'], snapshot['source']))
    report = []
    for url, review in reviews.items():
        document_url = review.get('document_url', url)
        if document_url != url and not review.get('notes'):
            raise ValueError(f'Missing recovered-source explanation: {url}')
        sid, path = cache.get(document_url)
        source_location = {'url': document_url, **({'linked_url': url} if document_url != url else {})}
        if hashlib.sha256(path.read_bytes()).hexdigest() != review['sha256']:
            raise ValueError(f'Reviewed match sheet changed: {url}')
        sources[sid] = cache.sources[sid]
        f = fixtures[review['fixture']]
        if f['sheet_url'] != url or f['score'] != review['team_score']:
            raise ValueError(f'Review does not match the team fixture: {url}')
        played = date.fromisoformat(review['date'])
        if played > date.fromisoformat(data['coverage']['as_of']):
            raise ValueError(f'Future match-sheet date: {url}')
        sheet_status = review.get('status', 'played')
        if sheet_status not in ('played', 'team_walkover'):
            raise ValueError(f'Unsupported match-sheet status: {url}')
        if sheet_status == 'team_walkover':
            if review['rows'] or review['players'] or sorted(review['team_score']) != [0, 5] or not review.get('notes'):
                raise ValueError(f'Invalid whole-team walkover: {url}')
            f.update(date=review['date'], rubbers=[], match_sheet_source=sid,
                     match_sheet_status='team_walkover')
            report.append({'source': sid, **source_location, 'fixture': f['id'], 'date': review['date'],
                           'season': events[f['event']]['season'], 'team_walkover': 1,
                           'notes': review['notes']})
            continue
        roster = review['players']
        identity_sources = {}
        for roster_key, person in roster.items():
            if not person.get('id'):
                if not person.get('label') or any(roster_key in r['players'] and r.get('status', 'played') != 'walkover' for r in review['rows']):
                    raise ValueError(f'Absent participant in a played match: {url}')
                continue
            p = players[person['id']]
            if person.get('registration') and person['registration'] != p['registration']:
                raise ValueError(f'Match-sheet registration mismatch: {url}')
            if not person['label']:
                raise ValueError(f'Missing identity evidence: {url}')
            available = [(period, source) for period, source in ranking_proofs[p['id']] if period <= review['date'][:7]]
            if not available:
                prior = matches_by_id.get(person.get('identity_match'))
                earlier = prior and p['id'] in (prior['p1'], prior['p2']) and prior['date'] < review['date'] and p.get('club') in f['clubs']
                corroboration_only = person.get('identity_basis') == 'same_day_workbook' and same_day_identity(review, f, roster, person, p, prior, by_pair)
                if not earlier and not corroboration_only:
                    raise ValueError(f'No contemporary ranking or prior-result identity: {url}')
                identity_sources[p['id']] = sorted({e['source'] for e in prior['evidence']})
            else:
                latest = max(period for period, _ in available)
                identity_sources[p['id']] = sorted({source for period, source in available if period == latest})
        scores = [0, 0]
        row_numbers = set()
        rubbers, counts = [], Counter()
        for row in review['rows']:
            number = row['row']
            if not isinstance(number, int) or not 1 <= number <= 9 or number in row_numbers:
                raise ValueError(f'Invalid or repeated match-sheet row: {url}')
            row_numbers.add(number)
            if row.get('status', 'played') not in ('played', 'walkover') or row.get('kind', 'singles') != 'singles':
                raise ValueError(f'Unsupported match-sheet row type: {url}')
            if len(row['players']) != 2 or any(k not in roster for k in row['players']):
                raise ValueError(f'Invalid match-sheet participants: {url}')
            if row.get('status', 'played') == 'played' and len({roster[k]['id'] for k in row['players']}) != 2:
                raise ValueError(f'Identical match-sheet participants: {url}')
            score = list(row['score'])
            if sorted(score) not in ([0, 3], [1, 3], [2, 3]):
                raise ValueError(f'Invalid match-sheet score: {url} row {number}')
            scores[0 if score[0] > score[1] else 1] += 1
            if row.get('status', 'played') != 'played' or row.get('kind', 'singles') != 'singles':
                ids = [roster[k].get('id') for k in row['players']]
                if all(ids) and by_pair.get((review['date'], tuple(sorted(ids)))):
                    raise ValueError(f'Existing played result conflicts with walkover: {url} row {number}')
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
        report.append({'source': sid, **source_location, 'fixture': f['id'], 'date': review['date'],
                       'season': events[f['event']]['season'], **counts, 'notes': review.get('notes', '')})
    held = []
    for url, issue in issues.items():
        sid, path = cache.get(url)
        if hashlib.sha256(path.read_bytes()).hexdigest() != issue['sha256']:
            raise ValueError(f'Held match sheet changed: {url}')
        if fixtures[issue['fixture']]['sheet_url'] != url or not issue['reason']:
            raise ValueError(f'Invalid held match sheet: {url}')
        sources[sid] = cache.sources[sid]
        held.append({'source': sid, 'url': url, **issue})
    data['sources'] = list(sources.values())
    data['events'] = list(events.values())
    data['matches'].sort(key=lambda m: (m['date'], m['id']), reverse=True)
    c = data['coverage']
    c.update(matches=len(data['matches']), events=len(data['events']),
             match_date_min=min(m['date'] for m in data['matches']), match_date_max=max(m['date'] for m in data['matches']),
             identity_methods=dict(Counter(v for m in data['matches'] for v in m['identity'])))
    linked = {f['sheet_url'] for f in data['fixtures'] if f.get('sheet_url')}
    unavailable_records = []
    for url, item in unavailable.items():
        if url not in linked or fixtures[item['fixture']]['sheet_url'] != url or url in reviews or url in issues or item.get('http_status') not in (404, 410) or not item.get('reason'):
            raise ValueError(f'Invalid unavailable sheet record: {url}')
        if date.fromisoformat(item['checked_at']) > date.fromisoformat(c['as_of']):
            raise ValueError(f'Future unavailable sheet check: {url}')
        unavailable_records.append({'url': url, **item})
    season_links = defaultdict(set)
    for fixture in data['fixtures']:
        if fixture.get('sheet_url'):
            season_links[events[fixture['event']]['season']].add(fixture['sheet_url'])
    season_coverage = {}
    for season, urls in sorted(season_links.items(), reverse=True):
        accepted = len(urls & set(reviews))
        held_count = len(urls & set(issues))
        season_coverage[season] = {'linked': len(urls), 'reviewed': accepted + held_count,
            'accepted': accepted, 'held': held_count, 'unavailable': len(urls & set(unavailable)),
            'pending': len(urls - set(reviews) - set(issues) - set(unavailable))}
    c['match_sheets'] = {'linked': len(linked), 'reviewed': len(report) + len(held),
                         'imported_sheets': len(report), 'held': len(held),
                         'pending': len(linked - set(reviews) - set(issues) - set(unavailable)), 'issues': held,
                         'unavailable': len(unavailable_records), 'unavailable_sources': unavailable_records,
                         'seasons': season_coverage,
                         'imported': sum(r.get('imported', 0) for r in report),
                         'corroborated': sum(r.get('corroborated', 0) for r in report),
                         'excluded_team_walkovers': sum(r.get('team_walkover', 0) for r in report),
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
    print(json.dumps({k:v for k,v in data['coverage']['match_sheets'].items() if k not in ('reviews', 'issues')}))


if __name__ == '__main__':
    main()
