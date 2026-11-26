"""Extract explicit team fixture rows from text PDFs; retain page/line evidence."""
import re
import subprocess
import unicodedata
import io
import pymupdf
from fontTools.ttLib import TTFont, TTLibError


def clean_text(text):
    return ' '.join((text or '').split())


def team_name(text):
    text = clean_text(text)
    text = re.sub(r'\s+&?\s*\(?α[./]?α\.?\)?\s*$', '', text, flags=re.I)
    text = re.sub(r'^\([Α-ΩA-Z]\d[^)]*\)\s*','',text)
    text = re.sub(r'\s*\(για \d+η θέση\)$','',text)
    return text.strip().strip('*').strip()


def reported_score(text):
    match = re.fullmatch(r'(\d)\s*[-–:]\s*(\d)(?:\s*\(?[αaΑ][./]?[αaΑ]\.?\)?)?', clean_text(text))
    return list(map(int, match.groups())) if match else None


def vacant(name):
    return clean_text(name).upper() in {'BYE', 'ΒΥΕ', 'ΒYΕ', 'XXX', 'ΧΧΧ', 'ΑΝΕΥ ΑΓΩΝΟΣ', 'ΑΝΕΥ ΑΓΩΝΟΣ *'}


def font_repairs(document, page):
    """Recover Greek text from rendered glyphs when a PDF's ToUnicode is wrong."""
    if '\u03a2' not in page.get_text():
        return lambda text: text
    maps, replacements = {}, {}
    for xref, extension, _, name, *_ in page.get_fonts():
        if extension != 'ttf':
            continue
        try:
            font = TTFont(io.BytesIO(document.extract_font(xref)[3]))
            cmap = font.getBestCmap() or {}
            reverse = {font.getGlyphID(g): chr(cp) for cp, g in reversed(list(cmap.items()))}
            if reverse:
                maps[name.split('+')[-1]] = reverse
        except (KeyError, TTLibError):
            continue
    for span in page.get_texttrace():
        mapping = maps.get(span['font'], {})
        old = ''.join(chr(c[0]) for c in span['chars'])
        new = ''.join(mapping.get(c[1], chr(c[0])) for c in span['chars'])
        if old != new:
            for a, b in zip(old.split(), new.split()):
                if a != b and re.search('[Α-ω]', a):
                    replacements[a] = b
    if not replacements:
        return lambda text: text
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
    return lambda text: pattern.sub(lambda m: replacements[m[0]], text)


def table_rows(path, source_id, event_id, uid):
    """Read ruled fixtures and round-robin cells, retaining only one occurrence.

    A score matrix is corroboration when the same group has a fixture list;
    its mirrored cells must agree and are never counted as two matches.
    """
    records, warnings = [], []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, 1):
            matrix, section_rows, matrix_rows = {}, [], []
            def flush():
                represented = {tuple(sorted((r['home'], r['away']))) for r in section_rows}
                records.extend(section_rows)
                records.extend(r for r in matrix_rows if tuple(sorted((r['home'], r['away']))) not in represented)
            for ti, table in enumerate(page.find_tables().tables):
                cells = [[clean_text(c) for c in row] for row in table.extract()]
                if not cells:
                    continue
                header = cells[0]
                numbered_columns = {c: i for i, c in enumerate(header[2:], 2) if c.isdigit()}
                is_matrix = len(numbered_columns) >= 2 and '1' in numbered_columns and '2' in numbered_columns
                named_matrix = header[0] == '' and len(cells) > 2 and cells[1][0] in header[1:] and cells[2][0] in header[1:]
                def record(home, away, score, ri, method, raw):
                    if home and away and home != away and not vacant(home) and not vacant(away) and score is not None:
                        return dict(id=uid('f-', f'{event_id}:table:{page_number}:{ti}:{ri}:{method}:{home}:{away}'), event=event_id,
                            home=home, away=away, score=score, status='reported', round=f'PDF · {page_number} · {ti + 1}',
                            schedule_note='', deadline='', source=source_id, sheet_url='', page=page_number, table=ti + 1,
                            row=ri + 1, document_method=method, score_text=raw,
                            bbox=[round(x, 2) for x in table.rows[ri].bbox])
                if is_matrix or named_matrix:
                    flush()
                    section_rows, matrix_rows = [], []
                    identifiers=[r[0] for r in cells[1:] if r and r[0].isdigit()]
                    if len(set(identifiers)) != len(identifiers):
                        # An outer border can enclose several independent grids.
                        # Do not mix their draw numbers; read their inner lists.
                        matrix={}
                        continue
                    matrix = {r[0]: r[0] if named_matrix else r[1] for r in cells[1:] if len(r) > 2 and (named_matrix or r[0].isdigit())}
                    numbered = {r[0]: (ri, r) for ri, r in enumerate(cells[1:], 1) if len(r) > 2 and (named_matrix or r[0].isdigit())}
                    for number, (ri, row) in numbered.items():
                        for ci, opponent in enumerate(header):
                            if opponent not in matrix or ci <= header.index(number):
                                continue
                            score = reported_score(row[ci])
                            opposite = numbered.get(opponent)
                            mirror = reported_score(opposite[1][header.index(number)]) if opposite else None
                            if score is not None and mirror is not None and score != mirror[::-1]:
                                warnings.append(dict(page=page_number, table=ti+1, reason='conflicting_matrix_scores', pair=[number,opponent]))
                                continue
                            if score is None and mirror is not None:
                                score = mirror[::-1]
                            item = record(matrix[number], matrix[opponent], score, ri, 'matrix', row[ci])
                            if item:
                                matrix_rows.append(item)
                    continue
                for ri, row in enumerate(cells):
                    # Some knockout stages have no header or draw-pair numbers.
                    if len(row) == 4 and reported_score(row[-1]) is not None and all(re.search(r'[A-Za-zΑ-ω]', c) for c in row[1:3]) and ' - ' not in row[2] and not re.search(r'\d:\d|^\(',row[1]):
                        item = record(row[1], row[2], reported_score(row[-1]), ri, 'fixture_table', row[-1])
                        if item:
                            section_rows.append(item)
                        continue
                    # Fixture rows have a draw-pair cell before a team-pair cell.
                    pair_index = next((i for i, c in enumerate(row[:-1]) if re.fullmatch(r'\d{1,2}\s*[-–]\s*\d{1,2}', c)
                        and i + 1 < len(row) and re.search(r'[A-Za-zΑ-ω]', row[i+1])), None)
                    combined = [i for i,c in enumerate(row[:-1]) if ' - ' in c and len(c)>15]
                    name_index = combined[-1] if combined else pair_index + 1 if pair_index is not None else None
                    if name_index is None:
                        continue
                    names = row[name_index]
                    separate_names = ' - ' not in names and len(row) > name_index + 2 and re.search(r'[A-Za-zΑ-ω]', row[name_index+1])
                    rest = row[name_index + (2 if separate_names else 1):]
                    if len(rest) >= 2 and all(re.fullmatch(r'\d', c) for c in rest[-2:]):
                        raw = '-'.join(rest[-2:])
                    else:
                        raw = ' '.join(rest)
                    score = reported_score(raw)
                    if score is None:
                        continue
                    draw_pair = re.split(r'\s*[-–]\s*',row[pair_index]) if pair_index is not None else []
                    if separate_names:
                        home, away = names, row[name_index+1]
                    elif ' - ' in names:
                        names = re.sub(r'^\([^)]*\)\s*','',names)
                        home, away = names.split(' - ', 1)
                    else:
                        a, b = re.split(r'\s*[-–]\s*', row[pair_index])
                        if a not in matrix or b not in matrix:
                            continue
                        home, away = matrix[a], matrix[b]
                    item = record(home, away, score, ri, 'fixture_table', raw)
                    if item:
                        section_rows.append(item)
            flush()
    return records, warnings


def merged_segments(segments, horizontal):
    """Excel PDF borders often consist of several touching cell edges."""
    groups = []
    for rect in sorted(segments, key=lambda r: (r.y0, r.x0) if horizontal else (r.x0, r.y0)):
        axis = rect.y0 if horizontal else rect.x0
        group = next((g for g in groups if abs(g[0] - axis) < 1), None)
        if group is None:
            group = [axis, []]
            groups.append(group)
        group[1].append(rect)
    result = []
    for _, rectangles in groups:
        ordered = sorted(rectangles, key=lambda r: r.x0 if horizontal else r.y0)
        current = pymupdf.Rect(ordered[0])
        for rect in ordered[1:]:
            if (rect.x0 <= current.x1 + 1.1 if horizontal else rect.y0 <= current.y1 + 1.1):
                current |= rect
            else:
                result.append(current)
                current = pymupdf.Rect(rect)
        result.append(current)
    return result


def bracket_rows(path, source_id, event_id, uid, diagnostics=None):
    """Follow drawn bracket connectors; require a named winner in the pair."""
    def normalized(s):
        s = re.sub(r'(?:\s+|\()[ΝNΠ]\d+\)?$', '', s)
        s = re.sub(r'^[Α-ΩA-Z]{1,2}\d+\s+', '', s)
        s = ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if not unicodedata.combining(c))
        # Letter lookalikes occur in the same bracket (e.g. AEK / ΑΕΚ).
        return re.sub(r'[\s.]', '', s).translate(str.maketrans('ABEHIKMNOTXY', 'ΑΒΕΗΙΚΜΝΟΤΧΥ'))
    records, candidates = [], 0
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, 1):
            repair = font_repairs(document, page)
            horizontal, vertical = [], []
            for drawing in page.get_drawings():
                for item in drawing['items']:
                    if item[0] == 're':
                        rect = item[1]
                    elif item[0] == 'l':
                        a, b = item[1:3]
                        rect = pymupdf.Rect(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))
                    else:
                        continue
                    if rect.width > 20 and rect.height < 2:
                        horizontal.append(rect)
                    if rect.height > 2 and rect.width < 2:
                        vertical.append(rect)
            horizontal = merged_segments(horizontal, True)
            vertical = merged_segments(vertical, False)
            # A third-place winner can share a baseline with the final. Keep
            # the two branches separate at the main bracket's vertical join.
            split = []
            for h in horizontal:
                cuts = sorted({v.x1 for v in vertical if h.x0 + 3 < v.x1 < h.x1 - 3 and v.y0 < h.y0-2 and v.y1 > h.y1+2})
                edges = [h.x0, *cuts, h.x1]
                split.extend(pymupdf.Rect(a,h.y0,b,h.y1) for a,b in zip(edges,edges[1:]))
            horizontal = split
            lines = [(pymupdf.Rect(line['bbox']), repair(''.join(span['text'] for span in line['spans']).strip()))
                for block in page.get_text('dict')['blocks'] for line in block.get('lines', [])]
            def label(bar, participant=True):
                found = [(box, text) for box, text in lines if bar.x0 - 3 <= (box.x0 + box.x1) / 2 <= bar.x1 + 3
                    and -9 <= bar.y0 - box.y1 < 10 and re.search('[A-Za-zΑ-ω]', text) and reported_score(text) is None
                    and (not participant or not re.fullmatch(r'[A-ZΑ-Ω]{1,2}\d+',text))]
                name = min(found, key=lambda item: (round(abs(bar.y0-item[0].y1),1), -len(item[1])))[1] if found else ''
                if not name:
                    # A few third-place brackets put the lower team below its bar.
                    found = [(box, text) for box, text in lines if bar.x0 - 3 <= (box.x0 + box.x1) / 2 <= bar.x1 + 3
                        and -3 <= box.y0 - bar.y1 < 3 and re.search('[A-Za-zΑ-ω]', text) and reported_score(text) is None]
                    name = min(found, key=lambda item: item[0].y0)[1] if found else ''
                return re.sub(r'^\d+\s+', '', name).strip()
            for score_index, (box, text) in enumerate(lines):
                score = re.fullmatch(r'(\d)\s*[-–:]\s*(\d)(?:\s*\(?α[./]α\.?\)?)?', text, re.I)
                if not score:
                    continue
                center = (box.x0 + box.x1) / 2
                bars = [h for h in horizontal if h.x0 <= center <= h.x1 and -3 <= box.y0 - h.y1 < 18]
                if not bars:
                    continue
                bar = max(bars, key=lambda h: h.y1)
                pair = None
                for mirrored in (False, True):
                    x = bar.x1 if mirrored else bar.x0
                    children = [h for h in horizontal if h is not bar and abs((h.x0 if mirrored else h.x1) - x) < 2]
                    above = [h for h in children if h.y0 < bar.y0 - 2]
                    below = [h for h in children if h.y0 > bar.y0 + 2]
                    if not above or not below:
                        continue
                    joins = [v for v in vertical if abs(v.x0 - x) < 2 and v.y0 <= bar.y1 + 1 and v.y1 >= bar.y0 - 1]
                    connected = [(a,b) for v in joins for a in above for b in below
                        if abs(a.y1-v.y0)<2 and abs(b.y1-v.y1)<2]
                    possible = [(a,b) for a in above for b in below if abs((a.y0+b.y0)/2-bar.y0)<2]
                    if joins and (connected or possible):
                        pair = min(connected or possible, key=lambda ab:ab[1].y0-ab[0].y0)
                        break
                if pair is None:
                    continue
                candidates += 1
                home, away, winner = label(pair[0]), label(pair[1]), label(bar, False)
                numbered_winner = bool(re.fullmatch(r'[ΝNΠ]\d+', winner))
                if not home or not away or (not numbered_winner and normalized(winner) not in (normalized(home), normalized(away))):
                    if diagnostics is not None:
                        diagnostics.append(dict(page=page_number, bbox=list(box), score=text, home=home, away=away, winner=winner))
                    continue
                if vacant(home) or vacant(away):
                    continue
                a, b = sorted(map(int, score.groups()), reverse=True)
                if a == b or a == 0 or normalized(home) == normalized(away):
                    continue
                oriented = list(map(int, score.groups())) if numbered_winner else [a,b] if normalized(winner) == normalized(home) else [b,a]
                records.append(dict(id=uid('f-', f'{event_id}:bracket:{page_number}:{score_index}'), event=event_id,
                    home=home, away=away, score=oriented,
                    status='reported', round=f'PDF · {page_number}', schedule_note='', deadline='', source=source_id,
                    sheet_url='', page=page_number, bracket=True, winner=home if oriented[0]>oriented[1] else away, document_method='bracket', score_text=text,
                    bbox=[round(x, 2) for x in box]))
    return records, candidates


def extract_pdf(path, source_id, event_id, uid):
    text = subprocess.check_output(['pdftotext', '-layout', str(path), '-'], text=True)
    fixtures, warnings = table_rows(path, source_id, event_id, uid)
    def fingerprint(f):
        return f['page'], tuple(sorted(((f['home'], f['score'][0]), (f['away'], f['score'][1]))))
    existing = {fingerprint(f) for f in fixtures}
    for page, contents in enumerate(text.split('\f'), 1):
        for line_number, line in enumerate(contents.splitlines(), 1):
            # Published group-match rows start with two draw numbers. Final
            # scores may be hyphenated or printed in two adjacent score cells.
            match = re.match(r'^\s*(.+?)\s{2,}((?:\d\s*[-–]\s*\d|\d\s+\d)(?:\s*\(?α[./]?α\.?\)?)?)\s*$', line, re.I)
            if not match:
                continue
            names, score_text = match.groups()
            placement = bool(re.search(r'τελικ[οό]ς|κατάταξη|ΚΑΤΑΤΑΞΗ',names,re.I))
            names = re.sub(r'^(?:\d{1,2}:\d{2}\s+)?\d{1,2}\s*-\s*\d{1,2}\s+', '', names)
            names = re.sub(r'^.*?[ΑAΒBΓΔ]\d\s*-\s*[ΑAΒBΓΔ]\d\s*:\s*', '', names)
            names = re.sub(r'^(?:(?:1ος|2ος)\s+)?(?:Μικρός\s+τελικός|Ημιτελικός|Τελικός)\s*:?\s*', '', names, flags=re.I)
            names = re.sub(r'^Προκριματικός\s+αγώνας\s*:\s*', '', names, flags=re.I)
            if ':' in names and any(word in names.split(':',1)[0].upper() for word in ('ΤΕΛΙΚΟΣ','ΤΕΛΙΚΌΣ')):
                names=names.split(':',1)[1].strip()
            names = re.sub(r'^(?:(?:ΜΙΚΡΟΣ\s+)?ΤΕΛΙΚΟΣ|ΚΑΤΑΤΑΞΗ)\s+[Α-ΩA-Z]\d\s*-\s*[Α-ΩA-Z]\d\s*','',names)
            names = re.sub(r'^\d{1,2}:\d{2}\s*', '', names)
            names = re.sub(r'^\([^)]*\)\s*', '', names)
            names = re.sub(r'^(?:[Α-ΩA-Z]{1,2}\d+\s+)?[Α-ΩA-Z]{1,2}\d+\s*-\s*[Α-ΩA-Z]{1,2}\d+\s+', '', names)
            if re.match(r'^\d+\s+', names):
                continue  # A bracket seed followed by a hyphenated team name.
            if ' - ' not in names:
                continue
            names = re.sub(r'^\d{1,2}/\d{1,2},?\s*(?:ώρα)?\s*\d{1,2}:\d{2}\s*', '', names).strip()
            home, away = [n.strip() for n in names.split(' - ', 1)]
            away = re.sub(r'\s+\d{1,2}/\d{1,2},?\s+.*$','',away)
            away = re.sub(r'\s+\d\s*[-–]\s*\d\s*$','',away)
            scores = re.findall(r'(?<!\d)(\d)\s*[-–]\s*(\d)(?!\d)', score_text)
            tail = re.search(r'(\d)\s+(\d)\s*$', score_text)
            score = list(map(int, tail.groups() if tail else scores[-1])) if (tail or scores) else None
            if not all(re.search('[A-Za-zΑ-ω]', n) and not re.fullmatch(r'[Α-ΩA-Z]{1,2}\d+',n) for n in (home,away)) or not score or vacant(home) or vacant(away):
                continue
            fixture = dict(id=uid('f-', f'{event_id}:pdf:{page}:{line_number}'), event=event_id,
                home=home, away=away, score=score, status='reported', round=f'PDF · {page}',
                schedule_note='', deadline='', source=source_id, sheet_url='', page=page, line=line_number, document_method='text_row')
            if placement:
                fixture['placement']=True
                fixture['round']='Μικρός τελικός' if re.search('μικρ[οό]ς',line,re.I) else 'Τελική φάση'
            if placement or fingerprint(fixture) not in existing:
                fixtures.append(fixture)
                existing.add(fingerprint(fixture))
    diagnostics = []
    bracket, candidates = bracket_rows(path, source_id, event_id, uid, diagnostics)
    fixtures.extend(bracket)
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            repair = font_repairs(document, page)
            for fixture in fixtures:
                if fixture['page'] != number or fixture.get('bracket'):
                    continue
                for field in ('home', 'away', 'winner'):
                    if field in fixture:
                        original = fixture[field]
                        fixture[field] = repair(original)
                        if fixture[field] != original:
                            fixture.setdefault('source_text', {})[field] = original
    for fixture in fixtures:
        for field in ('home','away','winner'):
            if field in fixture:
                original = fixture[field]
                fixture[field] = team_name(original)
                if original != fixture[field]:
                    fixture.setdefault('source_text', {})[field] = original
    # Prefer explicit rows to their matrix/laid-out text duplicates. Distinct
    # fixture rows in different rounds are retained even with identical scores.
    preferred = {'fixture_table': 0, 'bracket': 1, 'matrix': 2, 'text_row': 3}
    kept, seen = [], {}
    for fixture in sorted(fixtures, key=lambda f: preferred[f['document_method']]):
        fp = fingerprint(fixture)
        if fp in seen and fixture['document_method'] in ('matrix', 'text_row') and not fixture.get('placement'):
            continue
        kept.append(fixture)
        seen[fp] = fixture
    fixtures = kept
    return fixtures, dict(pages=len(text.rstrip('\f\n').split('\f')), has_bracket=bool(re.search('ΤΕΛΙΚΟΣ|ΤΕΛΙΚΟΙ', text)),
        bracket_candidates=candidates, bracket_parsed=len(bracket), text_characters=len(text.strip()), warnings=warnings, unmatched_brackets=diagnostics)
