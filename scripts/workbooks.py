"""Discover the official archive and read both generations of Excel files."""
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import openpyxl
import xlrd


def inventory(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    region = None
    found = {}
    for el in (soup.select_one('#wsite-content') or soup).find_all(['h2', 'a']):
        label = ' '.join(el.get_text(' ', strip=True).replace('\u200b', '').split())
        if el.name == 'h2':
            if 'ΠΑΝΕΛΛΑΔΙΚΑ' in label:
                region = 'national'
            elif 'ΝΟΤΙΑ' in label:
                region = 'south'
            elif 'ΒΟΡΕΙΑ' in label:
                region = 'north'
            continue
        url = urljoin(base, el.get('href', ''))
        if not region or not re.search(r'\.xlsx?$', url, re.I):
            continue
        filename = urlparse(url).path.rsplit('/', 1)[-1]
        match = re.search(r'(\d{1,2})[_-](20\d{2})', filename)
        if not match:
            raise ValueError(f'Undated workbook: {url}')
        period = f'{match[2]}-{int(match[1]):02}'
        item = found.setdefault(url, dict(url=url, filename=filename, period=period, region=region, labels=[], imported=False))
        if item['region'] != region:
            raise ValueError(f'Workbook linked under multiple regions: {url}')
        if label and label not in item['labels']:
            item['labels'].append(label)
    return list(found.values())


class LegacySheet:
    def __init__(self, sheet, datemode):
        self.sheet, self.datemode, self.title = sheet, datemode, sheet.name

    def iter_rows(self, values_only=True):
        for row in self.sheet.get_rows():
            values = []
            for cell in row:
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    value = xlrd.xldate_as_datetime(value, self.datemode)
                elif cell.ctype == xlrd.XL_CELL_NUMBER and value.is_integer():
                    value = int(value)
                elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    value = None
                values.append(value)
            yield tuple(values)


class LegacyBook:
    def __init__(self, path):
        self.book = xlrd.open_workbook(path)
        self.sheetnames = self.book.sheet_names()

    def __getitem__(self, name):
        return LegacySheet(self.book.sheet_by_name(name), self.book.datemode)

    def __iter__(self):
        return (self[name] for name in self.sheetnames)

    def close(self):
        self.book.release_resources()


def open_book(path):
    return LegacyBook(path) if path.suffix.lower() == '.xls' else openpyxl.load_workbook(path, read_only=True, data_only=True)


def canonical_list(title):
    return title.replace('ΑΝΕΞΑΡΤΗΤΟΙ ', 'ANE ').replace('ΒΕΤΕΡΑΝΟΙ ', 'BET ')


def number(value):
    if isinstance(value, str) and re.fullmatch(r'\s*\d+\s*', value):
        return int(value)
    return value


# Older sheets head individual-event blocks with a category (ΑΝΕ 18-39,
# ΒΕΤΕΡΑΝΟΙ 40-49 ΟΜΙΛΟΙ), a stage (ΦΑΣΗ ΟΜΙΛΩΝ, 1-8, ΚΑΤΑΤΑΞΗ 5-14) or a
# row-number header (α/α) in the cells where team results print two teams.
# Team names such as "ΒΕΤ. ΑΟ ΤΑΤΑΥΛΑ" or "ΒΕΤΕΡΑΝΟΙ ΔΡΑΜΑΣ" do not match.
CATEGORY_WORD = r'(?:ΚΑΤΗΓΟΡΙΑ|ΑΝΕΞ(?:ΑΡΤΗΤ\w*)?|ANE|ΑΝΕ|ΒΕΤ(?:ΕΡΑΝ\w*)?|BET|ΓΥΝ(?:ΑΙΚ\w*)?)\.?'
EVENT_LABEL = re.compile(
    rf'^(?:{CATEGORY_WORD}\s*)+(?:\d+\s*(?:-\s*\d+|\+))?(?:\s*(?:{CATEGORY_WORD}|ΟΜΙΛΟΙ))*$'
    r'|^(?:α\.?/?α\.?|\d+\s*-\s*\d+|ΚΑΤΑΤΑΞΗ\b.*|ΦΑΣΗ\s.*|ΟΜΙΛΟΙ|ΗΜΙΤΕΛΙΚΟΙ|ΤΕΛΙΚΟΣ|ΝΟΚ\s*ΑΟΥΤ|`)$',
    re.I)


def team_pair(values):
    """The two printed team names, or None when the cells head an individual event.

    A team result always names both teams. A single filled cell (a tournament or
    region heading) or any category/stage label means the block has no teams.
    """
    names = [v.strip() if isinstance(v, str) else '' for v in values]
    return names if all(names) and not any(EVENT_LABEL.match(n) for n in names) else None


def result_rows(sheet):
    """Read published score columns and the older grouped-row notation.

    Pre-2019 sheets leave repeated date/team/competition cells blank. Context
    row numbers are retained so every filled value can be checked in Excel.
    A new date/team block resets teams; numeric cells are never team names.
    """
    rows = list(sheet.iter_rows(values_only=True))
    votes = Counter()
    def completed(a, b):
        return type(a) in (int, float) and type(b) in (int, float) and ((a == 3 and b in (0, 1, 2)) or (b == 3 and a in (0, 1, 2)))
    for row in rows:
        if len(row) < 6:
            continue
        if re.fullmatch(r'\s*[0-3]\s*[-:]\s*[0-3]\s*', str(row[3])):
            votes['combined'] += 1
        for offset in (3, 4):
            if completed(*map(number, row[offset:offset + 2])):
                votes[offset] += 1
    if not votes:
        return
    layout = votes.most_common(1)[0][0]
    width = len(rows[0])
    compact = (layout == 'combined' and width <= 8) or (layout == 3 and width == 8)
    club_at = None if compact else (4 if layout == 'combined' else layout + 2)
    event_at = (4 if layout == 'combined' else 5) if compact else club_at + 2
    legacy = isinstance(sheet, LegacySheet)
    last_date, date_row, teams, team_row, event, event_row = None, None, ['', ''], None, '', None
    team_line = None  # last row holding the current pair's names, including wrapped lines
    for rownum, raw in enumerate(rows, 1):
        row = list(raw) + [None] * 12
        if not any(v is not None and str(v).strip() for v in raw):
            continue
        raw_date = row[0]
        explicit_date = isinstance(raw_date, datetime) or (isinstance(raw_date, str) and re.fullmatch(r'\s*\d{1,2}/\d{1,2}/\d{2,4}\s*', raw_date))
        if explicit_date:
            last_date, date_row = raw_date, rownum
            teams, team_row = ['', ''], None
        if club_at is not None:
            new_teams = [v.strip() if isinstance(v, str) else '' for v in row[club_at:club_at + 2]]
            if any(new_teams):
                # Long team names wrap onto the next undated row ("ΚΡΟΚΟΔΕΙΛΟΙ"
                # above "ΦΛΩΡΙΝΑΣ"); such a line keeps the pair. Otherwise an
                # individual-event heading starts a block without teams.
                wrapped = (not explicit_date and team_line == rownum - 1 and all(teams)
                           and not any(EVENT_LABEL.match(n) for n in new_teams if n))
                if wrapped:
                    team_line = rownum
                else:
                    pair = team_pair(new_teams)
                    teams, team_row, team_line = pair or ['', ''], rownum, rownum if pair else None
        raw_event = row[event_at]
        if isinstance(raw_event, str) and raw_event.strip():
            event, event_row = raw_event.strip(), rownum
        if layout == 'combined':
            match = re.fullmatch(r'\s*(\d+)\s*[-:]\s*(\d+)\s*', str(row[3]))
            a, b = map(int, match.groups()) if match else (None, None)
        else:
            a, b = map(number, row[layout:layout + 2])
        date_value = last_date if legacy else raw_date
        clubs = teams if legacy else [row[5], row[6]]
        event_value = event if legacy else raw_event
        yield rownum, (date_value, row[1], row[2], a, b, *clubs, event_value), {
            'sheet': sheet.title, 'layout': str(layout) + ('-compact' if compact else ''),
            'date_row': date_row if legacy else rownum, 'team_row': team_row if legacy else rownum,
            'event_row': event_row if legacy else rownum,
        }
