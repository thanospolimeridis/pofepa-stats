#!/usr/bin/env python3
"""Build lazy GitHub Pages data shards and a self-contained offline archive."""
import base64
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from dataset import load, encode, save
from validate import validate

ROOT = Path(__file__).resolve().parents[1]


def player_stats(rows, pid):
    result = dict(played=len(rows), wins=0, gamesWon=0, gamesLost=0, deciding=0, decidingWins=0)
    for m in rows:
        a, b = m['score'] if m['p1'] == pid else reversed(m['score'])
        result['wins'] += a > b
        result['gamesWon'] += a
        result['gamesLost'] += b
        result['deciding'] += a + b == 5
        result['decidingWins'] += a + b == 5 and a > b
    result['losses'] = len(rows) - result['wins']
    result['winRate'] = result['wins'] / len(rows) if rows else None
    return result


BOOTSTRAP_SCHEMA = 2
ROUTE_ARCHIVES = {
    'fixtures': 'data/fixtures.json.gz',
    'about': 'data/about.json.gz',
}


def bootstrap_data(data):
    """Keep route-independent indexes while deferring fixture and audit records.

    The full catalog and offline archive retain their original data contract.
    This shallow projection never removes fields from their source objects.
    """
    result = {key: value for key, value in data.items() if key not in ('fixtures', 'issues')}
    result['bootstrap_schema'] = BOOTSTRAP_SCHEMA
    result['archives'] = dict(ROUTE_ARCHIVES)
    result['sources'] = [{key: source[key] for key in ('id', 'url')} for source in data['sources']]
    coverage = data['coverage']
    result['coverage'] = {key: value for key, value in coverage.items()
                          if not isinstance(value, (dict, list)) or key == 'ranking_periods'}
    if 'match_sheets' in coverage:
        result['coverage']['match_sheets'] = {
            key: value for key, value in coverage['match_sheets'].items()
            if not isinstance(value, (dict, list)) or key == 'seasons'
        }
    return result


def build():
    data = load()
    validate(data)
    data['player_redirects'] = json.loads((ROOT / 'data/player-redirects.json').read_text())
    data['version'] = (ROOT / 'VERSION').read_text().strip()
    data['dataset_sha256'] = hashlib.sha256(encode(data)).hexdigest()
    data['ranking_index'] = 'https://www.pofepa.gr/piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html'
    html = (ROOT / 'src/template.html').read_text()
    for marker, filename in [('STYLE', 'style.css'), ('CORE', 'core.js'), ('EVIDENCE', 'evidence.js'), ('APP', 'app.js')]:
        html = html.replace(f'/*{marker}*/', (ROOT / 'src' / filename).read_text())
    dist = ROOT / 'dist'
    if dist.exists():
        shutil.rmtree(dist)
    (dist / 'data').mkdir(parents=True)
    offline = html.replace('/*DATA*/', encode({'compressed': base64.b64encode(gzip.compress(encode(data), mtime=0)).decode()}).decode())
    (ROOT / 'index.html').write_text(offline)
    (dist / 'offline.html').write_text(offline)
    save(data, dist / 'data/catalog.json.gz')
    save(data['matches'], dist / 'data/matches.json.gz')
    history, matches = defaultdict(list), defaultdict(list)
    event_matches = defaultdict(list)
    for match in data['matches']:
        for pid in (match['p1'], match['p2']):
            matches[pid].append(match)
        event_matches[match['event']].append(match)
    for snapshot in data['snapshots']:
        for row in snapshot['rows']:
            history[row[0]].append([snapshot['id'], row])
    shards = defaultdict(dict)
    for player in data['players']:
        pid = player['id']
        bucket = int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16) % 128
        player['archive'] = f'data/players-{bucket:03}.json.gz'
        player['stats'] = player_stats(matches[pid], pid)
        shards[bucket][pid] = dict(matches=matches[pid], history=history[pid])
    for bucket, records in shards.items():
        save(records, dist / f'data/players-{bucket:03}.json.gz')
    for event in data['events']:
        event['match_count'] = len(event_matches[event['id']]) if event['kind'] == 'singles' else sum(f['event'] == event['id'] for f in data['fixtures'])
        if event['kind'] == 'singles':
            event['archive'] = f'data/{event["id"]}.json.gz'
            save(event_matches[event['id']], dist / event['archive'])
    latest = data['coverage']['ranking_periods'][-1]
    for snapshot in data['snapshots']:
        path = 'data/r-' + hashlib.sha256(snapshot['id'].encode()).hexdigest()[:16] + '.json.gz'
        snapshot['archive'] = path
        save(snapshot['rows'], dist / path)
        if not (snapshot['region'] == 'national' and snapshot['period'] == latest and snapshot['list'] in ('ΓΕΝΙΚΟΣ', 'BET 40-49')):
            del snapshot['rows']
    data['recent_matches'] = data['matches'][:6]
    data['matches'] = data['recent_matches']
    data['lazy'] = True
    save(data['fixtures'], dist / ROUTE_ARCHIVES['fixtures'])
    save({'sources': data['sources'], 'coverage': data['coverage']}, dist / ROUTE_ARCHIVES['about'])
    bootstrap = bootstrap_data(data)
    save(bootstrap, dist / 'data/bootstrap.json.gz')
    # Include the lazy-data schema and projection in cache identity, not only the catalog.
    revision = hashlib.sha256(encode(bootstrap)).hexdigest()[:16]
    (dist / 'index.html').write_text(html.replace('/*DATA*/', encode({'bootstrap': 'data/bootstrap.json.gz', 'revision': revision}).decode()))
    (dist / '.nojekyll').touch()
    (dist / 'coverage.json').write_bytes(encode(data['coverage']))
    (dist / 'provenance.json').write_bytes(encode({'dataset_sha256': data['dataset_sha256'], 'sources': data['sources']}))
    print(f'Built lazy archive: {data["coverage"]["matches"]:,} matches, {data["coverage"]["ranking_rows"]:,} ranking rows; bootstrap {(dist / "data/bootstrap.json.gz").stat().st_size:,} bytes.')


if __name__ == '__main__':
    build()
