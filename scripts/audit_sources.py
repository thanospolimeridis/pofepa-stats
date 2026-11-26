#!/usr/bin/env python3
"""Compare every ranking and singles result with its original cached cells."""
from collections import defaultdict
from datetime import datetime
import hashlib
from pathlib import Path
import re

from dataset import load
from workbooks import open_book, number
from collect import clean, key

ROOT = Path(__file__).resolve().parents[1]


def audit():
    data = load()
    paths = {hashlib.sha256(p.read_bytes()).hexdigest(): p for p in (ROOT / 'capture').iterdir()
             if p.is_file() and p.suffix in ('.xls', '.xlsx', '.pdf', '.html', '.jpg', '.jpeg', '.png')}
    players = {p['id']: p for p in data['players']}
    clubs = {c['id']: c['name'] for c in data['clubs']}
    snapshots, evidence = defaultdict(list), defaultdict(list)
    for snap in data['snapshots']:
        snapshots[snap['source']].append(snap)
    for match in data['matches']:
        for row in match['evidence']:
            evidence[row['source']].append((match, row))
    ranking_count = result_count = 0
    for source in data['sources']:
        assert source['sha256'] in paths, source['url']
        if source['id'] not in snapshots:
            continue
        book = open_book(paths[source['sha256']])
        sheets = {s.title: list(s.iter_rows(values_only=True)) for s in book}
        book.close()
        for snap in snapshots[source['id']]:
            raw = sheets[snap['sheet']]
            header = [clean(v) for v in raw[0]]
            expected_ranks, previous = {}, None
            for n, row in enumerate(raw[1:], 2):
                value = clean(row[0])
                rank = previous if value in ('"', '〃') else int(value) if value.isdigit() else None
                expected_ranks[n] = rank
                if rank is not None:
                    previous = rank
            for pid, rank, points, club, category, row_number in snap['rows']:
                row = raw[row_number - 1]
                cell = lambda label: row[header.index(label)]
                assert rank == expected_ranks[row_number], (snap['id'], row_number)
                raw_points = cell('Βαθμοί')
                assert points == (None if clean(raw_points) == '-' else float(raw_points))
                assert key(cell('Ονοματεπώνυμο')) in {key(players[pid]['name']), *map(key, players[pid]['aliases'])}
                if 'ΔΑΙ' in header and cell('ΔΑΙ'):
                    assert str(int(cell('ΔΑΙ'))) == players[pid]['registration']
                assert clean(cell('Κατηγορία')) == category
                expected_club = clean(cell('Ομάδα'))
                assert clubs.get(club, '') == (expected_club if expected_club not in ('-', '—') else '')
                ranking_count += 1
        for match, proof in evidence[source['id']]:
            rows = sheets[proof['sheet']]
            row = rows[proof['row'] - 1]
            layout = proof['layout'].split('-')[0]
            scores = list(map(int, re.split(r'[-:]', str(row[3])))) if layout == 'combined' else list(map(number, row[int(layout):int(layout) + 2]))
            assert sorted([(key(row[1]), scores[0]), (key(row[2]), scores[1])]) == sorted(zip(map(key, match['names']), match['score']))
            raw_date = rows[proof['date_row'] - 1][0]
            played = raw_date if isinstance(raw_date, datetime) else datetime.strptime(clean(raw_date), '%d/%m/%Y')
            assert played.date().isoformat() == match['date']
            result_count += 1
    assert ranking_count == data['coverage']['ranking_rows']
    assert result_count == sum(e.get('kind')!='match_sheet' for m in data['matches'] for e in m['evidence'])
    print(f'Verified {len(data["sources"])} source hashes, {ranking_count:,} ranking rows and {result_count:,} original result rows for {len(data["matches"]):,} distinct singles matches.')


if __name__ == '__main__':
    audit()
