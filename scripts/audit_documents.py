#!/usr/bin/env python3
"""Replay all reviewed document imports and compare exact published results."""
import json
from pathlib import Path

from collect import Cache, uid
from dataset import load
from reviewed_documents import extract_document, fixture_digest

ROOT=Path(__file__).resolve().parents[1]


def audit():
    data=load()
    cache=Cache(ROOT/'capture',offline=True)
    reviews=json.loads((ROOT/'data/document-reviews.json').read_text())
    count=0
    for review in reviews:
        sid,path=cache.get(review['url'])
        parsed,_=extract_document(path,sid,uid('e-',review['url']),uid,reviews)
        committed=[f for f in data['fixtures'] if f['source']==sid]
        assert fixture_digest(parsed)==fixture_digest(committed),review['url']
        assert cache.sources[sid]['sha256']==review['sha256']
        count+=len(parsed)
    print(f'Verified {len(reviews)} source hashes and replayed {count:,} reviewed document results.')


if __name__=='__main__':audit()
