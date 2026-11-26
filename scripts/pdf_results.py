"""Extract explicit team fixture rows from text PDFs; retain page/line evidence."""
import re
import subprocess
import unicodedata
import pymupdf


def bracket_rows(path, source_id, event_id, uid):
    """Follow drawn bracket connectors; require a named winner in the pair."""
    normalized = lambda s: ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if not unicodedata.combining(c)).strip()
    records, candidates = [], 0
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, 1):
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
                    if rect.height > 15 and rect.width < 2:
                        vertical.append(rect)
            lines = [(pymupdf.Rect(line['bbox']), ''.join(span['text'] for span in line['spans']).strip())
                for block in page.get_text('dict')['blocks'] for line in block.get('lines', [])]
            def label(bar):
                found = [(box, text) for box, text in lines if bar.x0 - 3 <= (box.x0 + box.x1) / 2 <= bar.x1 + 3
                    and -1 <= bar.y0 - box.y1 < 10 and not re.fullmatch(r'[\d\s\-:]+', text)]
                return max(found, key=lambda item: item[0].y1)[1] if found else ''
            for score_index, (box, text) in enumerate(lines):
                score = re.fullmatch(r'(\d)\s*[-–:]\s*(\d)', text)
                if not score:
                    continue
                center = (box.x0 + box.x1) / 2
                bars = [h for h in horizontal if h.x0 <= center <= h.x1 and 0 <= box.y0 - h.y1 < 18]
                if not bars:
                    continue
                bar = max(bars, key=lambda h: h.y1)
                joins = [v for v in vertical if abs(v.x1 - bar.x0) < 2 and v.y0 < bar.y0 < v.y1]
                if len(joins) != 1:
                    continue
                candidates += 1
                join = joins[0]
                first = [h for h in horizontal if abs(h.x1 - join.x1) < 2 and abs(h.y1 - join.y0) < 2]
                second = [h for h in horizontal if abs(h.x1 - join.x1) < 2 and abs(h.y1 - join.y1) < 2]
                if len(first) != 1 or len(second) != 1:
                    continue
                home, away, winner = label(first[0]), label(second[0]), label(bar)
                if not home or not away or normalized(winner) not in (normalized(home), normalized(away)):
                    continue
                a, b = sorted(map(int, score.groups()), reverse=True)
                if a == b or a not in (3, 4, 5, 6, 7, 8, 9) or normalized(home) == normalized(away):
                    continue
                records.append(dict(id=uid('f-', f'{event_id}:bracket:{page_number}:{score_index}'), event=event_id,
                    home=home, away=away, score=[a, b] if normalized(winner) == normalized(home) else [b, a],
                    status='reported', round=f'PDF · {page_number}', schedule_note='', deadline='', source=source_id,
                    sheet_url='', page=page_number, bracket=True, winner=winner))
    return records, candidates


def extract_pdf(path, source_id, event_id, uid):
    text = subprocess.check_output(['pdftotext', '-layout', str(path), '-'], text=True)
    fixtures = []
    for page, contents in enumerate(text.split('\f'), 1):
        for line_number, line in enumerate(contents.splitlines(), 1):
            # Published group-match rows start with two draw numbers. Final
            # scores may be hyphenated or printed in two adjacent score cells.
            match = re.match(r'^\s*\d{1,2}\s*-\s*\d{1,2}\s+(.+?)\s{2,}(.*?)\s*$', line)
            if not match:
                continue
            names, score_text = match.groups()
            if ' - ' not in names:
                continue
            names = re.sub(r'^\d{1,2}/\d{1,2},?\s*(?:ώρα)?\s*\d{1,2}:\d{2}\s*', '', names).strip()
            home, away = [n.strip() for n in names.split(' - ', 1)]
            scores = re.findall(r'(?<!\d)(\d)\s*[-–]\s*(\d)(?!\d)', score_text)
            tail = re.search(r'(\d)\s+(\d)\s*$', score_text)
            score = list(map(int, tail.groups() if tail else scores[-1])) if (tail or scores) else None
            if not home or not away or not score:
                continue
            fixtures.append(dict(id=uid('f-', f'{event_id}:pdf:{page}:{line_number}'), event=event_id,
                home=home, away=away, score=score, status='reported', round=f'PDF · {page}',
                schedule_note='', deadline='', source=source_id, sheet_url='', page=page, line=line_number))
    bracket, candidates = bracket_rows(path, source_id, event_id, uid)
    fixtures.extend(bracket)
    return fixtures, dict(pages=len(text.rstrip('\f\n').split('\f')), has_bracket=bool(re.search('ΤΕΛΙΚΟΣ|ΤΕΛΙΚΟΙ', text)),
        bracket_candidates=candidates, bracket_parsed=len(bracket), text_characters=len(text.strip()))
