"""Apply explicit, hash-bound corrections to existing workbook records.

The original record is retained in the match audit trail, or in the fixture for
an excluded walkover. Replays require the same before/after states and source.
"""
from copy import deepcopy
import hashlib

FIELDS = {'date', 'p1', 'p2', 'score'}


def state(match):
    return {key: deepcopy(match[key]) for key in FIELDS}


def reconcile(data, cache, reviews):
    players = {p['id']: p for p in data['players']}
    fixtures = {f['id']: f for f in data['fixtures']}
    matches = {m['id']: m for m in data['matches']}
    seen = set()
    for url, review in reviews.items():
        if not review.get('corrections'):
            continue
        sid, path = cache.get(review.get('document_url', url))
        if hashlib.sha256(path.read_bytes()).hexdigest() != review['sha256']:
            raise ValueError(f'Correction source changed: {url}')
        fixture = fixtures[review['fixture']]
        if fixture['sheet_url'] != url or fixture['score'] != review['team_score']:
            raise ValueError(f'Correction fixture mismatch: {url}')
        rows = {r['row']: r for r in review['rows']}
        for correction in review['corrections']:
            mid = correction['match']
            if mid in seen:
                raise ValueError(f'Duplicate match correction: {mid}')
            seen.add(mid)
            before = correction['before']
            if set(before) != FIELDS or not correction.get('reason'):
                raise ValueError(f'Incomplete correction precondition: {mid}')
            row = rows[correction['row']]
            roster = [review['players'][k] for k in row['players']]
            ids = [p.get('id') for p in roster]
            action = correction.get('action', 'correct')
            proof = {'source': sid, 'sha256': review['sha256'], 'fixture': fixture['id'],
                     'row': row['row'], 'reason': correction['reason'], 'before': deepcopy(before),
                     'action': action}
            if action == 'exclude_walkover':
                if row.get('status') != 'walkover' or None in ids or set(ids) != {before['p1'], before['p2']} or before['date'] != review['date']:
                    raise ValueError(f'Walkover correction mismatch: {mid}')
                expected_score = row['score'] if before['p1'] == ids[0] else row['score'][::-1]
                if before['score'] != expected_score or sorted(expected_score) != [0, 3]:
                    raise ValueError(f'Walkover score precondition failed: {mid}')
                exclusions = fixture.get('excluded_workbook_results', [])
                previous = [x for x in exclusions if x['match']['id'] == mid]
                if previous:
                    if len(previous) != 1 or previous[0]['correction'] != proof or mid in matches:
                        raise ValueError(f'Walkover replay conflict: {mid}')
                    continue
                match = matches.get(mid)
                if not match or state(match) != before or match.get('document_evidence') or match.get('origin') == 'match_sheet':
                    raise ValueError(f'Walkover precondition failed: {mid}')
                if any(r.get('match') == mid for f in data['fixtures'] for r in f.get('rubbers', [])):
                    raise ValueError(f'Walkover already linked as played: {mid}')
                fixture.setdefault('excluded_workbook_results', []).append({'match': deepcopy(match), 'correction': proof})
                del matches[mid]
                continue
            if action != 'correct' or row.get('status', 'played') != 'played':
                raise ValueError(f'Unsupported correction action: {mid}')
            after = correction['after']
            if set(after) != FIELDS or after == before or after['date'] != review['date'] or None in ids:
                raise ValueError(f'Invalid correction result: {mid}')
            if [after['p1'], after['p2']] == ids:
                score, clubs = row['score'], fixture['clubs']
            elif [after['p2'], after['p1']] == ids:
                score, clubs = row['score'][::-1], fixture['clubs'][::-1]
            else:
                raise ValueError(f'Correction participants mismatch: {mid}')
            if after['score'] != score:
                raise ValueError(f'Correction score mismatch: {mid}')
            proof['after'] = deepcopy(after)
            match = matches.get(mid)
            if not match:
                raise ValueError(f'Missing corrected match: {mid}')
            prior = match.get('sheet_corrections', [])
            if prior:
                if len(prior) != 1 or prior[0]['correction'] != proof or state(match) != after:
                    raise ValueError(f'Correction replay conflict: {mid}')
                continue
            if state(match) != before or match.get('document_evidence') or match.get('origin') == 'match_sheet':
                raise ValueError(f'Correction precondition failed: {mid}')
            if any(r.get('match') == mid for f in data['fixtures'] for r in f.get('rubbers', [])):
                raise ValueError(f'Correction already linked as played: {mid}')
            if any(other['id'] != mid and other['date'] == after['date'] and {other['p1'], other['p2']} == {after['p1'], after['p2']} for other in matches.values()):
                raise ValueError(f'Correction would collide with another result: {mid}')
            original = deepcopy(match)
            match.update(deepcopy(after))
            match['names'] = [players[match[k]]['name'] for k in ('p1', 'p2')]
            match['clubs'] = list(clubs)
            for i, key in enumerate(('p1', 'p2')):
                if after[key] != before[key]:
                    match['identity'][i] = 'reviewed_sheet_name_and_team'
                    match['identity_sources'][i] = [sid]
            match['sheet_corrections'] = [{'match': original, 'correction': proof}]
    data['matches'] = list(matches.values())
    return data
