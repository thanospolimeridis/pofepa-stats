"""Validate committed data before it can be built or published (stdlib only)."""
from datetime import date
import math
import re
from urllib.parse import urlparse

# A published schedule line with a dash opposite a team is a bye: it keeps the
# dash as printed and has no club. Any other team name must contain a letter,
# which rejects separator columns merged into a fixture.
BYE = ("-", "—")
LETTER = re.compile(r"[^\W\d_]")


def fixture_side_ok(name, club, clubs):
    return (name in BYE and club == "") or (bool(LETTER.search(name or "")) and club in clubs)


def validate(data):
    def require(test, message):
        if not test:
            raise ValueError(message)
    require(data.get("schema") == 1, "Unsupported schema")
    indices = {}
    for table in ("sources", "players", "clubs", "events", "matches", "fixtures", "snapshots"):
        records = data[table]
        ids = {row["id"] for row in records}
        require(len(ids) == len(records), f"Duplicate IDs: {table}")
        indices[table] = ids
    for source in data["sources"]:
        url = urlparse(source["url"])
        require(url.scheme in ("http", "https") and url.hostname in ("www.pofepa.gr", "pofepa.gr", "files.ping-pong.gr") and not url.username, "Unsafe source URL")
        require(len(source["sha256"]) == 64, "Missing source hash")
    for snapshot in data["snapshots"]:
        require(snapshot["source"] in indices["sources"], "Missing ranking source")
        seen = set()
        for pid, rank, points, club, category, row in snapshot["rows"]:
            require(pid in indices["players"] and (pid, row) not in seen, "Missing/duplicate ranking record")
            require((rank is None or isinstance(rank, int) and rank > 0) and (points is None or math.isfinite(points)), "Invalid rank/points")
            require(not club or club in indices["clubs"], "Missing ranking club")
            seen.add((pid, row))
    for match in data["matches"]:
        require(match["p1"] in indices["players"] and match["p2"] in indices["players"] and match["p1"] != match["p2"], "Invalid match players")
        require(match["source"] in indices["sources"] and match["event"] in indices["events"], "Invalid match reference")
        a, b = match["score"]
        require(type(a) is int and type(b) is int and ((a == 3 and 0 <= b < 3) or (b == 3 and 0 <= a < 3)), "Invalid completed score")
        require(date.fromisoformat(match["date"]) <= date.fromisoformat(data["coverage"]["as_of"]), "Future match")
        require(all(not c or c in indices["clubs"] for c in match["clubs"]), "Invalid match clubs")
        require(bool(match["evidence"]), "Missing match evidence")
        require(all(e["source"] in indices["sources"] and isinstance(e["row"], int) and e["row"] > 0 for e in match["evidence"]), "Invalid corroborating source")
        require(all(s in indices["sources"] for group in match["identity_sources"] for s in group), "Invalid identity source")
    for fixture in data["fixtures"]:
        require(fixture["event"] in indices["events"] and fixture["source"] in indices["sources"], "Invalid fixture reference")
        require((fixture["status"] == "reported") == (fixture["score"] is not None), "Fixture status mismatch")
        require(fixture['home'] and fixture['away'], 'Missing fixture team')
        require(len(fixture['clubs']) == 2 and all(fixture_side_ok(name, club, indices['clubs']) for name, club in zip((fixture['home'], fixture['away']), fixture['clubs'])), 'Invalid fixture team or club')
        if fixture['score'] is not None:
            require(len(fixture['score'])==2 and all(type(s) is int and 0<=s<=99 for s in fixture['score']), 'Invalid team score')
        for rubber in fixture.get('rubbers',[]):
            require(rubber['kind'] in ('singles','doubles'), 'Invalid rubber type')
            if rubber['kind']=='singles' and rubber.get('status','played')=='played':require(rubber['match'] in indices['matches'],'Missing corroborated singles match')
    for match in data['matches']:
        for proof in match.get('document_evidence',[]):
            require(proof['source'] in indices['sources'] and proof['fixture'] in indices['fixtures'],'Invalid document evidence')
    for review in data['coverage'].get('document_reviews',[]):
        require(review['source'] in indices['sources'],'Missing reviewed source')
    for k in ("matches", "players", "fixtures", "events"):
        require(data["coverage"][k] == len(data[k]), f"Coverage mismatch: {k}")
