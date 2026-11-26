#!/usr/bin/env python3
"""Independently compare normalized records with cached workbook cells."""
from collections import defaultdict
import hashlib
import json
import unicodedata
from pathlib import Path
from datetime import datetime
import openpyxl

ROOT=Path(__file__).resolve().parents[1]


def audit():
    data=json.loads((ROOT/'data/catalog.json').read_text())
    cache=ROOT/'capture'
    paths={}
    for path in cache.iterdir():
        if path.is_file() and not path.name.endswith('.meta.json'):
            paths[hashlib.sha256(path.read_bytes()).hexdigest()]=path
    sources={s['id']:s for s in data['sources']}
    players={p['id']:p for p in data['players']}
    clubs={c['id']:c['name'] for c in data['clubs']}
    books={}
    normalize=lambda v:' '.join(str(v if v is not None else '').replace('\u200b','').replace('\ufeff','').split())
    for sid,s in sources.items():
        if s['sha256'] not in paths:
            raise ValueError('Missing original source bytes: '+s['url'])
        if s['url'].endswith('.xlsx'):
            book=openpyxl.load_workbook(paths[s['sha256']],read_only=True,data_only=True)
            books[sid]={sheet.title:list(sheet.iter_rows(values_only=True)) for sheet in book}
            book.close()
    for snap in data['snapshots']:
        raw=books[snap['source']][snap['list']]
        header=[normalize(v) for v in raw[0]]
        def cell(row,label):return raw[row-1][header.index(label)]
        for pid,rank,points,club,category,row in snap['rows']:
            assert int(cell(row,'Νέα θέση'))==rank
            assert float(cell(row,'Βαθμοί'))==points
            assert str(int(cell(row,'ΔΑΙ')))==players[pid]['registration']
            assert normalize(cell(row,'Κατηγορία'))==category
            expected_club=normalize(cell(row,'Ομάδα'))
            assert (clubs.get(club,'') if club else '')==(expected_club if expected_club not in ('-','—') else '')
    fold=lambda v:''.join(c for c in unicodedata.normalize('NFD',normalize(v).upper()) if not unicodedata.combining(c))
    evidence_count=0
    for match in data['matches']:
        for evidence in match['evidence']:
            row=books[evidence['source']]['ΑΠΟΤΕΛΕΣΜΑΤΑ'][evidence['row']-1]
            assert sorted([(fold(row[1]),row[3]),(fold(row[2]),row[4])])==sorted(zip(map(fold,match['names']),match['score']))
            dt=row[0] if isinstance(row[0],datetime) else datetime.strptime(normalize(row[0]),'%d/%m/%Y')
            assert dt.date().isoformat()==match['date']
            evidence_count+=1
    # Regional namespace reconciliation uses the common June reference month.
    generals={s['region']:s for s in data['snapshots'] if s['period']=='2026-06' and s['list']=='ΓΕΝΙΚΟΣ'}
    national={r[0] for r in generals['national']['rows']}
    north={r[0] for r in generals['north']['rows']}
    south={r[0] for r in generals['south']['rows']}
    assert not north & south
    assert north | south == national
    print(f"Verified {len(sources)} source hashes, {data['coverage']['ranking_rows']:,} ranking rows and {evidence_count:,} source rows for {len(data['matches']):,} distinct matches; regional June identities reconcile.")


if __name__=='__main__':
    audit()
