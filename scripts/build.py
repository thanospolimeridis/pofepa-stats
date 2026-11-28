#!/usr/bin/env python3
"""Build lazy GitHub Pages data shards and a self-contained offline archive."""
import base64
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil

from dataset import load, encode, save
from validate import validate
from competition_regions import attach_regions
from cup_draws import attach_draws
from athlete_rankings import match_ranking_context

ROOT = Path(__file__).resolve().parents[1]
VERSION_FORMAT = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')


def read_version(root=ROOT):
    """The site's release version, from the committed VERSION file.

    The file is the only source: reading Git or the clock here would make the same
    commit build differently in CI. scripts/release.py is what changes it. A copy
    of the project without the file builds an unversioned site.
    """
    path = root / 'VERSION'
    if not path.exists():
        return None
    version = path.read_text(encoding='utf-8').strip()
    if not VERSION_FORMAT.fullmatch(version):
        raise SystemExit(f'VERSION must hold MAJOR.MINOR.PATCH, found {version!r}')
    return version


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
MATCH_LIST = 'data/match-list.json.gz'


def match_list(matches):
    """Compact index for the Matches page, decoded by core.js expandMatchList.

    Each singles result becomes one row with shared event, name, source and
    region tables: what the list filters, searches and renders, plus correction
    evidence. data/matches.json.gz keeps the full records for CSV exports.
    """
    tables = {name: ([], {}) for name in ('events', 'names', 'sources', 'regions')}

    def index(name, value):
        values, positions = tables[name]
        key = json.dumps(value, ensure_ascii=False)
        if key not in positions:
            positions[key] = len(values)
            values.append(value)
        return positions[key]

    def refs(items):
        return [value for ref in items for value in (index('sources', ref['source']), ref.get('row'))]

    rows, corrections = [], {}
    for position, match in enumerate(matches):
        evidence = match.get('evidence') or [{'source': match['source'], 'row': match.get('row')}]
        if (evidence[0]['source'], evidence[0].get('row')) != (match['source'], match.get('row')):
            raise ValueError(f'Primary source must lead the evidence list: {match["id"]}')
        row = [match['date'], index('events', match['event']), match['p1'], match['p2'], *match['score'],
               *(index('names', name) for name in match['names']),
               index('regions', [match['region'], match.get('regions')]), refs(evidence)]
        if match.get('document_evidence'):
            row.append(refs(match['document_evidence']))
        if match.get('sheet_corrections'):
            corrections[str(position)] = match['sheet_corrections']
        rows.append(row)
    return {'schema': 1, **{name: values for name, (values, _) in tables.items()},
            'rows': rows, 'corrections': corrections}


def bootstrap_data(data):
    """Keep route-independent indexes while deferring fixture and audit records.

    The full catalog and offline archive retain their original data contract.
    This shallow projection never removes fields from their source objects.
    """
    result = {key: value for key, value in data.items() if key not in ('fixtures', 'issues', 'cup_draws', 'match_rankings')}
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


def stamp(data, version):
    """Give the catalog its data hash, then the number of the release that carries it.

    The hash comes first and so leaves the number out: a release that changes no
    data leaves dataset_sha256 as it was.
    """
    data['dataset_sha256'] = hashlib.sha256(encode(data)).hexdigest()
    if version:
        data['version'] = version
    return data


def build():
    data = load()
    validate(data)
    attach_regions(data)
    attach_draws(data)
    data['match_rankings'] = match_ranking_context(data)
    data['player_redirects'] = json.loads((ROOT / 'data/player-redirects.json').read_text())
    stamp(data, read_version())
    data['ranking_index'] = 'https://www.pofepa.gr/piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html'
    html = (ROOT / 'src/template.html').read_text()
    for marker, filename in [('STYLE', 'style.css'), ('CORE', 'core.js'), ('EVIDENCE', 'evidence.js'), ('ATHLETES', 'athlete-stats.js'), ('APP', 'app.js')]:
        html = html.replace(f'/*{marker}*/', (ROOT / 'src' / filename).read_text())
    dist = ROOT / 'dist'
    if dist.exists():
        shutil.rmtree(dist)
    (dist / 'data').mkdir(parents=True)
    shutil.copytree(ROOT / 'data/cup-draws', dist / 'data/cup-draws')
    offline = html.replace('/*DATA*/', encode({'compressed': base64.b64encode(gzip.compress(encode(data), mtime=0)).decode()}).decode())
    (ROOT / 'index.html').write_text(offline)
    (dist / 'offline.html').write_text(offline)
    save(data, dist / 'data/catalog.json.gz')
    save(data['matches'], dist / 'data/matches.json.gz')
    save(match_list(data['matches']), dist / MATCH_LIST)
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
        shards[bucket][pid] = dict(matches=matches[pid], history=history[pid],
            rank_comparisons={m['id']: data['match_rankings'][m['id']] for m in matches[pid] if m['id'] in data['match_rankings']})
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
