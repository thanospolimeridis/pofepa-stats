"""Package exact published cup drawings for local, lazy and offline viewing.

PDF pages are vector drawings, not reconstructed knockout trees. This preserves
byes, preliminary draws, regional finals and third-place branches, including
empty slots. Generating assets needs PyMuPDF and the verified capture cache;
ordinary builds use only the committed deterministic gzip archives.
"""
import gzip
import hashlib
import json
from pathlib import Path

from competition_regions import attach_regions
from dataset import load, save

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'data/cup-draws'


def attach_draws(data):
    sources = {s['id']: s for s in data['sources']}
    data['cup_draws'] = {}
    for event in data['events']:
        if event.get('competition_type') != 'cup':
            continue
        pdfs = [sources[s] for s in event['sources'] if sources[s]['url'].lower().endswith('.pdf')]
        if not pdfs:
            continue
        archive = f'data/cup-draws/{event["id"]}.json.gz'
        with gzip.open(ROOT / archive) as stream:
            draw = json.load(stream)
        expected = [{'id': s['id'], 'url': s['url'], 'sha256': s['sha256']} for s in pdfs]
        if draw['event'] != event['id'] or draw['sources'] != expected:
            raise ValueError(f'Cup source changed; regenerate drawings: {event["id"]}')
        event['draw_archive'] = archive
        data['cup_draws'][event['id']] = draw


def generate():
    import pymupdf
    data = load()
    attach_regions(data)
    sources = {s['id']: s for s in data['sources']}
    ASSETS.mkdir(parents=True, exist_ok=True)
    count = pages = 0
    for event in data['events']:
        if event.get('competition_type') != 'cup':
            continue
        pdfs = [sources[s] for s in event['sources'] if sources[s]['url'].lower().endswith('.pdf')]
        if not pdfs:
            continue
        draw = {'event': event['id'], 'sources': [], 'pages': []}
        for source in pdfs:
            path = ROOT / 'capture' / (hashlib.sha256(source['url'].encode()).hexdigest()[:16] + '.pdf')
            if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
                raise ValueError(f'Source bytes differ from imported results: {source["url"]}')
            draw['sources'].append({k: source[k] for k in ('id', 'url', 'sha256')})
            with pymupdf.open(path) as document:
                for number, page in enumerate(document, 1):
                    # Outlined glyphs preserve fonts and Greek PDFs with broken
                    # character maps. SVG is generated from graphics, never
                    # copied from remote markup; it is displayed as an image.
                    draw['pages'].append({'source': source['id'], 'page': number,
                        'width': round(page.rect.width, 2), 'height': round(page.rect.height, 2),
                        'links': [{'url': link['uri'], 'bbox': [round(v, 2) for v in link['from']]}
                                  for link in page.get_links() if link.get('uri', '').startswith(('https://', 'http://'))
                                  and link['from'].width > .02 and link['from'].height > .02],
                        'svg': page.get_svg_image(text_as_path=True)})
        save(draw, ASSETS / f'{event["id"]}.json.gz')
        count += 1
        pages += len(draw['pages'])
    print(f'Packaged {pages} source pages across {count} cup draws.')


if __name__ == '__main__':
    generate()
