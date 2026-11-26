#!/usr/bin/env python3
"""Refresh reviewed PDFs/images without reprocessing unchanged workbooks."""
import argparse
from pathlib import Path

from dataset import load, save
from reviewed_documents import extract_document
from season_sources import seasons, content_links
from validate import validate

ROOT = Path(__file__).resolve().parents[1]


def corroborate_singles(data):
    matches = {m['id']:m for m in data['matches']}
    for f in data['fixtures']:
        for rubber in f.get('rubbers',[]):
            if rubber['kind']!='singles':
                continue
            if rubber.get('status','played')!='played' or f.get('match_sheet_source'):
                continue
            match = matches[rubber['match']]
            if match['date']!=f['date'] or match['score']!=rubber['score'] or match['clubs']!=f['clubs']:
                raise ValueError('Image transcription does not match its workbook corroboration')
            proof = {'source':f['source'],'row':rubber['row'],'fixture':f['id']}
            if proof not in match.setdefault('document_evidence',[]):
                match['document_evidence'].append(proof)
            rubber['players']=[match['p1'],match['p2']]


def refresh(data, cache):
    from collect import BASE, SEASON, uid, clean
    reviews, new_fixtures, visited, inventory = [], [], set(), []
    events = {e['id']:e for e in data['events']}
    clubs = {c['id']:c for c in data['clubs']}
    _,path = cache.get(SEASON,'season.html')
    for season,url in seasons(path.read_text(),BASE):
        _,landing = cache.get(url,'season.html' if url==SEASON else None)
        links = content_links(landing.read_text(),url)
        inventory.append({'season':season,'url':url,'linked_sources':len(links)})
        for label,source_url in links:
            if not source_url.lower().endswith(('.pdf','.jpg','.jpeg','.png')) or source_url in visited:
                continue
            visited.add(source_url)
            sid,path = cache.get(source_url)
            eid=uid('e-',source_url)
            fixtures,info=extract_document(path,sid,eid,uid)
            events.setdefault(eid,{'id':eid,'name':label,'season':season,'kind':'fixtures','sources':[sid]})
            reviews.append({'source':sid,'url':source_url,'season':season,**info})
            for f in fixtures:
                f['clubs']=[]
                for name in (f['home'],f['away']):
                    cid=uid('c-',clean(name));clubs.setdefault(cid,{'id':cid,'name':clean(name)});f['clubs'].append(cid)
            new_fixtures.extend(fixtures)
    sources={s['id']:s for s in data['sources']}
    sources.update(cache.sources)
    replaced={r['source'] for r in reviews}
    data['fixtures']=[f for f in data['fixtures'] if f['source'] not in replaced]+new_fixtures
    referenced={p.get('club') for p in data['players']}
    referenced.update(c for m in data['matches'] for c in m['clubs'])
    referenced.update(c for f in data['fixtures'] for c in f['clubs'])
    referenced.update(row[3] for snapshot in data['snapshots'] for row in snapshot['rows'])
    clubs={cid:c for cid,c in clubs.items() if cid in referenced}
    data['sources']=list(sources.values());data['clubs']=list(clubs.values());data['events']=list(events.values())
    coverage=data['coverage']
    coverage.update(fixtures=len(data['fixtures']),reported_fixtures=sum(f['status']=='reported' for f in data['fixtures']),events=len(data['events']),document_reviews=reviews,season_inventory=inventory)
    coverage['deferred']=[d for d in coverage['deferred'] if d['url'] not in visited and d['reason']!='no_linked_results']
    for d in coverage['deferred']:
        if d['url']==BASE:d['reason']='invalid_result_link'
        if '2012-13-k-makp.html' in d['url']:d['reason']='empty_source'
    for r in reviews:
        if r['review_status']=='source_conflict':coverage['deferred'].append({'label':events[uid('e-',r['url'])]['name'],'url':r['url'],'reason':'document_source_conflict','detail':r['review_issues']})
    corroborate_singles(data)
    validate(data)
    return data


def main():
    from collect import Cache
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--cache',type=Path,default=ROOT/'capture')
    args=parser.parse_args()
    data=refresh(load(),Cache(args.cache,offline=args.offline))
    save(data,ROOT/'data/catalog.json.gz')
    print(f"Reviewed {len(data['coverage']['document_reviews'])} documents; {data['coverage']['reported_fixtures']:,} reported team results.")


if __name__=='__main__':main()
