"""Preserve the regional headings around links in POFΕPA season pages."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
REGIONS = [
    ('attica-south', 'Αττική & Νότια Ελλάδα', 'Attica & South Greece'),
    ('central-macedonia', 'Κεντρική Μακεδονία', 'Central Macedonia'),
    ('western-greece', 'Δυτική Ελλάδα', 'Western Greece'),
    ('crete', 'Κρήτη', 'Crete'),
    ('western-macedonia-epirus-ionian', 'Δυτική Μακεδονία - Ήπειρος - Ιόνια Νησιά', 'Western Macedonia - Epirus - Ionian Islands'),
    ('eastern-macedonia-thrace', 'Ανατολική Μακεδονία & Θράκη', 'Eastern Macedonia & Thrace'),
    ('peloponnese', 'Πελοπόννησος', 'Peloponnese'),
    ('thessaly', 'Θεσσαλία', 'Thessaly'),
    ('north-aegean', 'Νησιά Βόρειου Αιγαίου', 'North Aegean Islands'),
    ('nationwide', 'Πανελλήνιες διοργανώσεις', 'National competitions'),
]


def normalized(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', text.upper())
                           if not unicodedata.combining(c)).replace('\u200b', '').replace('\ufeff', '').split())


def named_region(text):
    text = normalized(text)
    for pattern, region in [
        (r'ΠΑΝΕΛΛΗΝ|ΠΑΝ\.? ΠΡΩΤ|ΠΑΝ\.? ΚΥΠ', 'nationwide'),
        (r'ΑΤΤΙΚ|ΝΟΤΙΑ ΕΛΛΑΔ', 'attica-south'),
        (r'ΚΕΝΤΡΙΚ.{0,4} ΜΑΚΕΔΟΝ|Κ-ΜΑΚ', 'central-macedonia'),
        (r'ΔΥΤΙΚ.{0,4} ΕΛΛΑΔ', 'western-greece'),
        (r'ΚΡΗΤ', 'crete'),
        (r'ΔΥΤΙΚ.{0,4} ΜΑΚΕΔΟΝ|ΗΠΕΙΡ', 'western-macedonia-epirus-ionian'),
        (r'ΑΝΑΤΟΛΙΚ.{0,4} ΜΑΚΕΔΟΝ|ΘΡΑΚ', 'eastern-macedonia-thrace'),
        (r'ΠΕΛΟΠΟΝΝ', 'peloponnese'),
        (r'ΘΕΣΣΑΛ', 'thessaly'),
        (r'ΑΙΓΑΙ', 'north-aegean'),
    ]:
        if re.search(pattern, text):
            return region


def regional_links(html, base):
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#wsite-content') or soup
    found = {}
    # Context belongs to one content column, never the navigation or next column.
    for block in main.select('.paragraph'):
        region, heading = None, ''
        for node in block.descendants:
            if isinstance(node, NavigableString):
                if node.find_parent('a'):
                    continue
                text = ' '.join(str(node).split())
                identified = named_region(text)
                if identified:
                    region, heading = identified, text
            elif node.name == 'a' and node.get('href'):
                label = ' '.join(node.get_text(' ', strip=True).replace('\u200b', '').split())
                if not label:
                    continue
                explicit = named_region(label)
                selected = explicit or region
                if selected:
                    found.setdefault(urljoin(base, node['href']), {
                        'region': selected, 'heading': label if explicit else heading, 'label': label})
                if explicit:
                    region, heading = explicit, label
    return found


def attach_regions(data):
    manifest = json.loads((ROOT / 'data/competition-regions.json').read_text())
    source_urls = {s['id']: s['url'] for s in data['sources']}
    data['competition_regions'] = [{'id': key, 'el': el, 'en': en} for key, el, en in REGIONS]
    for event in data['events']:
        refs = [manifest['links'][source_urls[s]] for s in event['sources']
                if source_urls[s] in manifest['links']] if event['kind'] == 'fixtures' else []
        regions = {r['region'] for r in refs}
        if len(regions) == 1:
            event['competition_region'] = refs[0]['region']
        else:
            # Workbook coverage is not the competition's geographical region.
            event['competition_region'] = event.get('competition_region') or named_region(event['name']) or 'unspecified'


def generate():
    from dataset import load
    data = load()
    urls = {s['url'] for s in data['sources'] if any(s['id'] in e['sources'] for e in data['events'] if e['kind'] == 'fixtures')}
    links, pages = {}, []
    for season in data['coverage']['season_inventory']:
        url = season['url']
        filename = 'season.html' if season['season'] == '2026-2027' else hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
        body = (ROOT / 'capture' / filename).read_bytes()
        pages.append({'url': url, 'sha256': hashlib.sha256(body).hexdigest()})
        for target, context in regional_links(body.decode(), url).items():
            if target in urls:
                links.setdefault(target, {**context, 'page': url})
    output = {'pages': pages, 'links': links}
    (ROOT / 'data/competition-regions.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(f'Regional source context retained for {len(links)} / {len(urls)} competition sources.')
    for url in sorted(urls - links.keys()):
        print('Unclassified:', url)


if __name__ == '__main__':
    generate()
