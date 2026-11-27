#!/usr/bin/env python3
"""Collect public POFΕPA sources. Cached, replayable, no inferred game scores."""
from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from workbooks import inventory as workbook_inventory, open_book, canonical_list, result_rows
from season_sources import seasons, content_links
from competition_regions import regional_links
from reviewed_documents import extract_document

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.pofepa.gr/"
RANKINGS = BASE + "piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html"
SEASON = BASE + "2026-2027.html"


def clean(value):
    return " ".join(str(value if value is not None else "").replace("\u200b", "").replace("\ufeff", "").split())


def key(value):
    # Case, accents and spaces only. Never fuzzy-match different spellings.
    return "".join(c for c in unicodedata.normalize("NFD", clean(value).upper()) if not unicodedata.combining(c))


def uid(prefix, value):
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:16]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_url(value):
    p = urlparse(value)
    return p.scheme in ("http", "https") and p.hostname in ("www.pofepa.gr", "pofepa.gr", "files.ping-pong.gr") and not p.username


def score_status(a, b, opponent=""):
    if "BONUS" in key(opponent):
        return "bonus"
    if type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and a == int(a) and b == int(b):
        if (a == 3 and 0 <= b < 3) or (b == 3 and 0 <= a < 3):
            return "completed"
    return "nonstandard_score"


class Cache:
    def __init__(self, directory, offline=False, refresh=False):
        self.path = directory
        self.path.mkdir(parents=True, exist_ok=True)
        self.offline, self.refresh = offline, refresh
        self.sources = {}

    def get(self, url, filename=None):
        if not safe_url(url):
            raise ValueError(f"Unapproved source URL: {url}")
        filename = filename or uid("", url) + Path(urlparse(url).path).suffix
        path = self.path / filename
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if (self.refresh or not path.exists()) and not self.offline:
            request = Request(url, headers={"User-Agent": "pofepa-stats/0.1 (public sports archive)"})
            with urlopen(request, timeout=45) as response:
                body = response.read()
            path.write_bytes(body)
            meta_path.write_text(json.dumps({"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
            time.sleep(.15)
        if not path.exists():
            raise FileNotFoundError(f"Missing cached source: {url}")
        body = path.read_bytes()
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            if metadata["url"] != url:
                raise ValueError(f"Cache URL mismatch: {path}")
        else:
            metadata = {"url": url, "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
        sid = uid("s-", url)
        self.sources[sid] = {"id": sid, **metadata, "sha256": sha(body), "bytes": len(body)}
        return sid, path


def ranking_rows(sheet):
    iterator = sheet.iter_rows(values_only=True)
    header = [clean(v) for v in next(iterator)]
    if header[0] in ("Θέση", ""):
        header[0] = "Νέα θέση"
    required = ["Νέα θέση", "Ονοματεπώνυμο", "Βαθμοί", "Κατηγορία", "Ομάδα"]
    if not all(h in header for h in required):
        raise ValueError(f"Unrecognized ranking header: {sheet.title}: {header}")
    columns = [header.index(h) for h in required]
    previous_rank = None
    for row_number, row in enumerate(iterator, 2):
        if not any(v is not None and clean(v) for v in row):
            continue
        values = [row[i] if i < len(row) else None for i in columns]
        rank, name, points, category, club = values
        registration = row[header.index("ΔΑΙ")] if "ΔΑΙ" in header else None
        if clean(rank) in ('"', '〃'):
            rank = previous_rank  # The source uses ditto marks for tied positions.
        if clean(rank) in ('-', '') and (clean(points) == '-' or isinstance(points, (int, float))):
            yield row_number, None, clean(name), None if clean(points) == '-' else float(points), clean(category), clean(club), str(int(registration)) if registration else ""
            continue
        if not name or (registration is not None and not str(registration).strip().isdigit()):
            raise ValueError(f"Missing identity in {sheet.title} row {row_number}")
        if not isinstance(points, (int, float)) or not str(rank).isdigit():
            raise ValueError(f"Invalid ranking in {sheet.title} row {row_number}: {values}")
        previous_rank = int(rank)
        yield row_number, int(rank), clean(name), float(points), clean(category), clean(club), str(int(registration)) if registration else ""


def resolve_player(name, club, candidates):
    found = candidates.get(key(name), [])
    if club and key(club) not in ("-", "—"):
        same_club = [p for p in found if key(p["club"]) == key(club)]
        if len({p["id"] for p in same_club}) == 1:
            return same_club[0]["id"], "exact_name_and_team"
        # A conflicting recorded club is not silently ignored.
        return None, "team_mismatch" if found else "name_not_found"
    if len({p["id"] for p in found}) == 1:
        # This is an explicit provisional association, not a source-supplied ID.
        return found[0]["id"], "unique_name_in_month"
    return None, "ambiguous_name" if found else "name_not_found"


def registry_id(dai, name, registry):
    """Quarantine changed names under one DAI until reviewed, even typos."""
    return "p-" + dai + ("-" + uid("", key(name))[:8] if len(registry[dai]) > 1 else "")


def direct_rows(table):
    """A table's own rows. Rows of a nested layout table belong to that table."""
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def flat_cells(row):
    """A row's own cells, with a nested Weebly column table expanded in place.

    Some rounds put the home column beside a nested table that holds the
    separator, away and score columns. A cell is expanded only when that
    single-row nested table is its whole content, so text is never split.
    Returns the cells and the nested tables they came from.
    """
    cells, expanded = [], []
    for cell in row.find_all("td", recursive=False):
        nested = [t for t in cell.find_all("table") if t.find_parent(["td", "th"]) is cell]
        inner = direct_rows(nested[0]) if len(nested) == 1 else []
        if len(inner) == 1 and clean(cell.get_text(" ")) == clean(nested[0].get_text(" ")):
            inner_cells, inner_tables = flat_cells(inner[0])
            cells.extend(inner_cells)
            expanded.extend([nested[0], *inner_tables])
        else:
            cells.append(cell)
    return cells, expanded


def parse_fixture_tables(html, source_id, source_url, event_id):
    soup = BeautifulSoup(html, "html.parser")
    fixtures = []
    consumed = set()  # nested tables already read as part of their parent round
    for table_index, table in enumerate(soup.select("table")):
        if id(table) in consumed:
            continue
        rows = direct_rows(table)
        if not rows:
            continue
        header = rows[0].get_text(" ", strip=True)
        if "Γηπεδούχος" not in header or "Φιλοξενούμενος" not in header:
            heading = table.find_previous(['h2', 'h3'])
            round_name = clean(heading.get_text(' ')) if heading else ''
            if len(rows) > 1 and 'ΑΓΩΝΙΣΤΙΚ' in key(round_name):
                for row_index, tr in enumerate(rows, 1):
                    cells = tr.find_all(['td', 'th'], recursive=False)
                    if len(cells) < 3:
                        continue
                    home, away, result = [clean(c.get_text(' ')) for c in cells[:3]]
                    if not home or not away:
                        continue
                    score = re.match(r'^(\d+)\s*[-–:]\s*(\d+)(?:\s|$)', result)
                    links = [urljoin(source_url, a['href']) for a in cells[2].find_all('a', href=True)]
                    fixtures.append({'id': uid('f-', f'{event_id}:{table_index}:{row_index}'), 'event': event_id,
                        'home': home, 'away': away, 'score': [int(score[1]), int(score[2])] if score else None,
                        'status': 'reported' if score else 'scheduled', 'round': round_name,
                        'schedule_note': result if not score else '', 'deadline': '', 'source': source_id,
                        'sheet_url': next((u for u in links if safe_url(u)), ''), 'table': table_index, 'row': row_index})
                continue
            # Historical Weebly pages put an entire round in four parallel
            # columns, with <br> separating games. Require exact alignment.
            cells, nested_tables = flat_cells(rows[0])
            if len(rows) != 1 or len(cells) < 4:
                continue
            def lines(cell, preserve_blank=False, retain_links=False, split_spacing=True):
                copy = BeautifulSoup(str(cell), 'html.parser')
                if retain_links:
                    for anchor in copy.find_all('a', href=True):
                        target = urljoin(source_url, anchor['href'])
                        if safe_url(target) and re.match(r'^\s*\d+\s*[-–:]\s*\d+', anchor.get_text()):
                            for node in anchor.find_all(string=True):
                                if re.search(r'\d+\s*[-–:]\s*\d+', str(node)):
                                    node.replace_with(re.sub(r'(\d+\s*[-–:]\s*\d+)', lambda m:m[0]+'[[SHEET:'+target+']]', str(node), count=1))
                                    break
                for br in copy.find_all('br'):
                    br.insert_before('\x1e')
                output = []
                for segment in copy.get_text().split('\x1e'):
                    pieces = [clean(line) for line in (re.split(r'\n| {5,}|\xa0{3,}', segment) if split_spacing else [segment]) if clean(line)]
                    output.extend(pieces or ([''] if preserve_blank else []))
                return output
            offset = 0
            first_column = lines(cells[0])
            if len(cells) >= 5 and first_column and all(re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', value) for value in first_column):
                offset = 1  # A separate date column precedes the team columns.
            home_lines, away_lines = lines(cells[offset], True), lines(cells[offset + 2], True)
            for values in (home_lines, away_lines):
                while values and not values[-1]:
                    values.pop()
            score_lines = lines(cells[offset + 3], True, retain_links=True)
            compact_home, compact_away = list(filter(None, home_lines)), list(filter(None, away_lines))
            candidates = [(compact_home, compact_away, score_lines), (home_lines, away_lines, score_lines),
                          (compact_home, compact_away, list(filter(None, score_lines)))]
            columns = None
            if any(x not in ('-', '–', '—') for x in lines(cells[offset + 1])):
                continue
            for homes, aways, results in candidates:
                results = list(results)
                while len(results) > len(homes) and not results[-1]:
                    results.pop()
                if homes and len(homes) == len(aways) == len(results):
                    columns = [homes, [], aways, results]
                    break
            if columns is None and all(cells[offset+i].find('br') for i in range(4)):
                # A real team name can contain wide spacing (e.g. the 2012–13
                # cup's "Δ. Π. ΜΕΛΑ             2010"). Only after the legacy
                # layouts fail, trust explicit BR boundaries if all four
                # columns, including the separator dashes, agree exactly.
                explicit = [lines(cells[offset+i], retain_links=i==3, split_spacing=False) for i in range(4)]
                if explicit[0] and len({len(col) for col in explicit}) == 1 and all(value in ('-', '–', '—') for value in explicit[1]):
                    columns = explicit
            if columns is None:
                continue
            consumed.update(id(t) for t in nested_tables)
            heading = table.find_previous(['h2', 'h3'])
            round_name = clean(heading.get_text(' ')) if heading else ''
            for row_index, (home, away, result) in enumerate(zip(columns[0], columns[2], columns[3]), 1):
                if not home or not away:
                    continue
                sheet = re.search(r'\[\[SHEET:(.*?)\]\]', result)
                result = re.sub(r'\[\[SHEET:.*?\]\]', '', result)
                score = re.match(r'^(\d+)\s*[-–:]\s*(\d+)(?:\s|$)', result)
                fixtures.append({'id': uid('f-', f'{event_id}:{table_index}:{row_index}'), 'event': event_id,
                    'home': home, 'away': away, 'score': [int(score[1]), int(score[2])] if score else None,
                    'status': 'reported' if score else 'scheduled', 'round': round_name,
                    'schedule_note': result if not score else '', 'deadline': '', 'source': source_id, 'sheet_url': sheet[1] if sheet else '',
                    'table': table_index, 'row': row_index})
            continue
        heading = table.find_previous(["h2", "h3"])
        round_name = clean(heading.get_text(" ")) if heading else ""
        for row_index, tr in enumerate(rows[1:], 2):
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) < 3:
                continue
            home, away, result = [clean(c.get_text(" ")) for c in cells[:3]]
            if not home or not away:
                continue
            score = re.match(r"^(\d+)\s*[-–:]\s*(\d+)(?:\s|$)", result)
            parsed_score = [int(score[1]), int(score[2])] if score else None
            # Team formats differ by region. Preserve reported totals without
            # pretending these are played singles or deducing a match date.
            links = [urljoin(source_url, a["href"]) for a in cells[2].find_all("a", href=True)]
            fixtures.append({"id": uid("f-", f"{event_id}:{table_index}:{row_index}"), "event": event_id,
                "home": home, "away": away, "score": parsed_score, "status": "reported" if score else "scheduled",
                "round": round_name, "schedule_note": result if not score else "",
                "deadline": clean(cells[3].get_text(" ")) if len(cells) > 3 else "",
                "source": source_id, "sheet_url": next((u for u in links if safe_url(u)), "")})
    return fixtures


def collect(cache, as_of):
    sources, players, clubs, events, snapshots, matches, fixtures, issues = {}, {}, {}, {}, [], [], [], []
    def club_id(name):
        if not name or name in ("-", "—"):
            return ""
        cid = uid("c-", name)  # no undocumented club alias merges
        clubs[cid] = {"id": cid, "name": name}
        return cid

    _, ranking_index = cache.get(RANKINGS, "rankings.html")
    inventory = workbook_inventory(ranking_index.read_text(), BASE)
    candidates_by_period = defaultdict(lambda: defaultdict(list))
    workbook_objects = []
    registry = defaultdict(set)
    for item in sorted(inventory, key=lambda item: (item["period"], item["region"] == "national", item["region"])):
        period, region = item["period"], item["region"]
        sid, path = cache.get(item["url"], item["filename"])
        book = open_book(path)
        ranking_sheets, results = [], []
        for sheet in book:
            if sheet.title in ("ΑΠΟΤΕΛΕΣΜΑΤΑ", "Sheet1"):
                results.extend(result_rows(sheet) or [])
            else:
                ranking_sheets.append((sheet.title, list(ranking_rows(sheet))))
        book.close()
        general = next(rows for title, rows in ranking_sheets if title == "ΓΕΝΙΚΟΣ")
        workbook_objects.append((period, region, sid, ranking_sheets, results))
        for rownum, rank, name, points, category, club, dai in general:
            if dai:
                registry[dai].add(key(name))
        item.update(imported=True, source=sid)
        if len(workbook_objects) % 30 == 0:
            print(f"Parsed {len(workbook_objects)}/{len(inventory)} workbooks", flush=True)
    # Modern registrations are the evidence for linking pre-registration lists.
    modern_names = defaultdict(list)
    legacy_homonyms = set()
    for period, region, sid, sheets, results in workbook_objects:
        for title, rows in sheets:
            if title != "ΓΕΝΙΚΟΣ":
                continue
            duplicates = Counter(key(row[2]) for row in rows)
            legacy_homonyms.update(name for name, count in duplicates.items() if count > 1)
            for rownum, rank, name, points, category, club, dai in rows:
                if dai:
                    modern_names[key(name)].append({"id": registry_id(dai, name, registry), "club": club, "registration": dai})
    def historical_id(dai, name, club, region):
        if dai:
            return registry_id(dai, name, registry), "registration", dai
        if key(name) in legacy_homonyms:
            return uid("h-", f"{region}:{key(name)}:{key(club)}"), "historical_ambiguous_name", ""
        found = modern_names.get(key(name), [])
        same = [p for p in found if key(p["club"]) == key(club)] if club else []
        pool = same if len({p["id"] for p in same}) == 1 else found
        if len({p["id"] for p in pool}) == 1:
            return pool[0]["id"], "historical_exact_name_and_team" if pool is same else "historical_unique_name", pool[0]["registration"]
        return uid("h-", f"{region}:{key(name)}:{key(club)}"), "historical_unregistered", ""
    identity_conflicts = [{"registration": dai, "names": sorted(names)} for dai, names in sorted(registry.items()) if len(names) > 1]
    for period, region, sid, sheets, results in workbook_objects:
        # Include category-only entries if a source's general table omits them.
        for title, source_rows in sheets:
            rows = []
            for rownum, rank, name, points, category, club, dai in source_rows:
                pid, method, registration = historical_id(dai, name, club, region)
                old = players.get(pid)
                aliases = sorted(set((old or {}).get("aliases", []) + ([old["name"]] if old and old["name"] != name else [])))
                players[pid] = {"id": pid, "registration": registration, "name": name, "aliases": aliases,
                    "club": club_id(club), "category": category, "period": period, "provisional": False,
                    "identity_conflict": bool(registration and len(registry[registration]) > 1),
                    "historical_identity": method if not dai else (old or {}).get("historical_identity", "")}
                if title == "ΓΕΝΙΚΟΣ":
                    candidates_by_period[period][key(name)].append({"id": pid, "club": club, "source": sid})
                rows.append([pid, rank, points, club_id(club), category, rownum])
            repeated = Counter(r[0] for r in rows)
            for pid, count in repeated.items():
                if count > 1:
                    issues.append({"source": sid, "sheet": title, "player": pid, "reason": "repeated_source_ranking", "count": count})
            snapshots.append({"id": f"{region}:{period}:{canonical_list(title)}:{sid}", "region": region, "period": period,
                "list": canonical_list(title), "sheet": title, "source": sid, "rows": rows})

    records_by_fingerprint = defaultdict(list)
    for period, region, sid, sheets, results in workbook_objects:
        this_source = Counter()
        for rownum, row, context in results:
            raw_date, first, second, a, b, first_club, second_club, event_name = row[:8]
            first, second, first_club, second_club, event_name = map(clean, (first, second, first_club, second_club, event_name))
            if context.pop("walkover", False):
                # Marked "α/α" (άνευ αγώνα): not a played match, so it never enters statistics.
                issues.append({"source": sid, "sheet": context["sheet"], "row": rownum, "reason": "walkover_mark", "score": [a, b]})
                continue
            status = score_status(a, b, second)
            if status != "completed":
                issues.append({"source": sid, "sheet": context["sheet"], "row": rownum, "reason": status, "score": [a, b]})
                continue
            try:
                played = raw_date.date() if isinstance(raw_date, datetime) else datetime.strptime(clean(raw_date), "%d/%m/%Y").date()
            except (ValueError, TypeError):
                issues.append({"source": sid, "row": rownum, "reason": "invalid_date"})
                continue
            if played > as_of:
                issues.append({"source": sid, "row": rownum, "reason": "future_result"})
                continue
            if abs(played.year - int(period[:4])) > 1:
                issues.append({"source": sid, "row": rownum, "reason": "date_outside_workbook_year", "date": played.isoformat()})
                continue
            if not first or not second or not event_name or key(first) == key(second):
                issues.append({"source": sid, "row": rownum, "reason": "invalid_participants"})
                continue
            season_match = re.search(r"(20\d{2})-(20\d{2}|\d{2})", event_name)
            if season_match:
                season = season_match[1] + "-" + (season_match[2] if len(season_match[2]) == 4 else "20" + season_match[2])
            else:
                season = f"{played.year if played.month >= 8 else played.year - 1}-{played.year + 1 if played.month >= 8 else played.year}"
            eid = uid("e-", event_name + season)
            events.setdefault(eid, {"id": eid, "name": event_name, "season": season, "region": region, "regions": [], "kind": "singles", "sources": []})
            if region not in events[eid]["regions"]:
                events[eid]["regions"].append(region)
            events[eid]["region"] = region if len(events[eid]["regions"]) == 1 else "multi"
            if sid not in events[eid]["sources"]:
                events[eid]["sources"].append(sid)
            ids, methods, identity_sources = [], [], []
            for name, club in [(first, first_club), (second, second_club)]:
                candidates = candidates_by_period[period]
                pid, method = resolve_player(name, club, candidates)
                if not pid and method == "team_mismatch" and key(name) not in legacy_homonyms:
                    found = candidates.get(key(name), [])
                    if len({p["id"] for p in found}) == 1:
                        pid, method = found[0]["id"], "unique_name_team_differs"
                evidence = sorted({p["source"] for p in candidates.get(key(name), []) if p["id"] == pid and (method != "exact_name_and_team" or key(p["club"]) == key(club))})
                if not pid:
                    # Unresolved identities stay scoped to this source and event.
                    pid = uid("u-", f"{sid}:{eid}:{key(name)}:{key(club)}")
                    players[pid] = {"id": pid, "registration": "", "name": name, "aliases": [], "club": club_id(club), "category": "", "period": period, "provisional": True}
                ids.append(pid)
                methods.append(method)
                identity_sources.append(evidence)
            if ids[0] == ids[1]:
                issues.append({"source": sid, "row": rownum, "reason": "self_match"})
                continue
            # Deduplicate a physical result without resolving an ambiguous player:
            # date, competition, both names/IDs, source team and oriented score
            # must agree. Keep unresolved profiles separate outside that result.
            identity_keys = [pid if not pid.startswith("u-") else f"unresolved:{key(name)}:{key(club)}"
                             for pid, name, club in zip(ids, [first, second], [first_club, second_club])]
            fingerprint = json.dumps([played.isoformat(), eid, sorted([(identity_keys[0], int(a)), (identity_keys[1], int(b))])])
            this_source[fingerprint] += 1
            if this_source[fingerprint] <= len(records_by_fingerprint[fingerprint]):
                original = records_by_fingerprint[fingerprint][this_source[fingerprint] - 1]
                original["evidence"].append({"source": sid, "row": rownum, "region": region, **context})
                if region not in original["regions"]:
                    original["regions"].append(region)
                issues.append({"source": sid, "row": rownum, "reason": "overlapping_source_result"})
                continue
            match = {"id": uid("m-", f"{sid}:{rownum}"), "date": played.isoformat(), "event": eid, "region": region, "regions": [region],
                "p1": ids[0], "p2": ids[1], "names": [first, second], "score": [int(a), int(b)],
                "clubs": [club_id(first_club), club_id(second_club)], "identity": methods, "identity_sources": identity_sources,
                "source": sid, "row": rownum, "evidence": [{"source": sid, "row": rownum, "region": region, **context}]}
            matches.append(match)
            records_by_fingerprint[fingerprint].append(match)

    _, season_path = cache.get(SEASON, "season.html")
    visited = set()
    deferred = []
    document_reviews = []
    season_inventory = []
    for season_name, season_url in seasons(season_path.read_text(), BASE):
        season_sid, path = cache.get(season_url, "season.html" if season_url == SEASON else None)
        links = content_links(path.read_text(), season_url)
        regions = regional_links(path.read_text(), season_url)
        season_inventory.append({"season": season_name, "url": season_url, "linked_sources": len(links)})
        if not links:
            deferred.append({"label": season_name, "url": season_url, "reason": "no_linked_results"})
        for label, url in links:
            if not safe_url(url) or url in visited:
                continue
            visited.add(url)
            if not url.lower().endswith((".html", ".pdf", ".jpg", ".jpeg", ".png")):
                deferred.append({"label": label, "url": url, "season": season_name, "reason": "invalid_result_link"})
                continue
            try:
                sid, path = cache.get(url, "a1.html" if url == BASE + "2026-2027-a1.html" else None)
                eid = uid("e-", url)
                if not url.endswith(".html"):
                    title = label
                    parsed, pdf_info = extract_document(path, sid, eid, uid)
                    document_reviews.append({"source":sid,"url":url,"season":season_name,**pdf_info})
                    if pdf_info['review_status'] in ('pending','source_conflict'):
                        deferred.append({"label":title,"url":url,"reason":"document_"+pdf_info['review_status'],"detail":pdf_info.get('review_issues',[])})
                else:
                    html = path.read_text()
                    page = BeautifulSoup(html, "html.parser")
                    title = clean(page.title.get_text()).split(" - ΠΑΝΕΛ")[0] if page.title else label
                    parsed = parse_fixture_tables(html, sid, url, eid)
                events[eid] = {"id": eid, "name": title, "season": season_name, "kind": "fixtures", "sources": [sid]}
                if url in regions:
                    events[eid]['competition_region'] = regions[url]['region']
                    events[eid]['competition_type'] = regions[url]['competition_type']
                for f in parsed:
                    f["clubs"] = [club_id(f["home"]), club_id(f["away"])]
                fixtures.extend(parsed)
                if not parsed and url.endswith('.html'):
                    deferred.append({"label": title, "url": url, "reason": "no_supported_fixture_table"})
            except (OSError, ValueError) as exc:
                deferred.append({"label": label, "url": url, "reason": "source_unavailable", "detail": str(exc)})

    referenced_players = {m[p] for m in matches for p in ("p1", "p2")}
    players = {pid: p for pid, p in players.items() if not p["provisional"] or pid in referenced_players}
    matches.sort(key=lambda m: (m["date"], m["id"]), reverse=True)
    coverage = {"as_of": as_of.isoformat(), "ranking_periods": sorted(set(s["period"] for s in snapshots)),
        "matches": len(matches), "players": len(players), "ranked_players": sum(not p["provisional"] for p in players.values()),
        "provisional_players": sum(p["provisional"] for p in players.values()), "fixtures": len(fixtures),
        "reported_fixtures": sum(f["status"] == "reported" for f in fixtures),
        "ranking_rows": sum(len(s["rows"]) for s in snapshots), "events": len(events),
        "match_date_min": min((m["date"] for m in matches), default=None), "match_date_max": max((m["date"] for m in matches), default=None),
        "excluded_rows": dict(Counter(i["reason"] for i in issues)),
        "identity_methods": dict(Counter(v for m in matches for v in m["identity"])),
        "identity_conflicts": identity_conflicts, "season_inventory": season_inventory, "deferred": deferred, "workbook_inventory": inventory,
        "document_reviews":document_reviews}
    result = {"schema": 1, "coverage": coverage, "sources": list(cache.sources.values()), "players": list(players.values()),
        "clubs": list(clubs.values()), "events": list(events.values()), "snapshots": snapshots, "matches": matches, "fixtures": fixtures, "issues": issues}
    from refresh_documents import corroborate_singles
    corroborate_singles(result)
    from import_match_sheets import import_reviews, MANIFEST
    if MANIFEST.exists():
        import_reviews(result, cache)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch configured source scope")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--cache", type=Path, default=ROOT / "capture")
    parser.add_argument("--output", type=Path, default=ROOT / "data/catalog.json.gz")
    args = parser.parse_args()
    if args.offline and args.refresh:
        parser.error("--offline and --refresh are mutually exclusive")
    data = collect(Cache(args.cache, args.offline, args.refresh), date.fromisoformat(args.as_of))
    from validate import validate
    validate(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    from dataset import save
    save(data, args.output)
    print(json.dumps({k: v for k, v in data["coverage"].items() if k not in ("workbook_inventory", "deferred")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
