"""Replay visually checked document transcriptions against exact source bytes."""
import hashlib
import json
from pathlib import Path

from pdf_results import extract_pdf, team_name

ROOT = Path(__file__).resolve().parents[1]


def fixture_digest(fixtures):
    rows=sorted((f.get('page',1),f['home'],f['away'],f['score']) for f in fixtures)
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def extract_document(path, source_id, event_id, uid, reviews=None):
    reviews = reviews if reviews is not None else json.loads((ROOT / 'data/document-reviews.json').read_text())
    review = next((r for r in reviews if uid('s-',r['url']) == source_id), None)
    if review and hashlib.sha256(Path(path).read_bytes()).hexdigest() != review['sha256']:
        raise ValueError('Document changed since visual review; transcription must be checked again')
    fixtures, info = extract_pdf(path, source_id, event_id, uid) if Path(path).suffix.lower()=='.pdf' else ([], {'pages':1})
    if not review:
        return fixtures, {**info, 'review_status':'pending'}
    corrections = review.get('name_corrections',{})
    fixtures=[f for f in fixtures if f.get('page') not in review.get('duplicate_pages',[])]
    for f in fixtures:
        for field in ('home','away','winner'):
            if f.get(field) in corrections:
                f.setdefault('source_text',{})[field] = f[field]
                f[field] = corrections[f[field]]
    for index, row in enumerate(review.get('additional_fixtures',[])):
        duplicate = next((f for f in fixtures if f.get('page',1)==row.get('page',1) and
            sorted(zip((f['home'],f['away']),f['score'])) == sorted(zip((row['home'],row['away']),row['score']))),None)
        if duplicate:
            duplicate['visually_confirmed'] = True
            continue
        fixture = dict(id=uid('f-',f'{event_id}:review:{index}'),event=event_id,
            status='reported',round=f"PDF · {row.get('page',1)}" if Path(path).suffix=='.pdf' else 'Κύπελλο Βορείου Αιγαίου',
            schedule_note='',deadline='',source=source_id,sheet_url='',document_method='visual_transcription')
        fixture.update(row)
        fixtures.append(fixture)
    # Corrections can reconcile a clipped fixture name with its matrix entry.
    seen, result = {}, []
    for f in fixtures:
        fp = (f.get('page',1),tuple(sorted(((team_name(f['home']),f['score'][0]),(team_name(f['away']),f['score'][1])))))
        if fp in seen and f['document_method'] in ('matrix','text_row') and not f.get('placement'):
            continue
        result.append(f)
        seen[fp]=f
    if 'expected_fixtures' in review and len(result)!=review['expected_fixtures']:
        raise ValueError(f"Reviewed fixture count changed: {review['url']}: {len(result)} != {review['expected_fixtures']}")
    if review.get('fixture_digest') and fixture_digest(result)!=review['fixture_digest']:
        raise ValueError(f"Reviewed names/scores changed: {review['url']}")
    info.pop('unmatched_brackets',None)
    return result, {**info,'review_status':review['status'],'review_issues':review.get('issues',[]),
        'review_notes':review.get('notes',''),'reviewed_at':review['reviewed_at'],'fixtures':len(result)}
