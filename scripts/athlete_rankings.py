"""Attach comparable, strictly prior monthly ranking context to singles matches.

The source identifies a ranking month, not its publication day. Consequently a
match can only use a general-ranking snapshot from an earlier month. Both ranks
must come from one snapshot in the latest available earlier general-ranking
period; missing players never trigger a fallback to an older period.
"""
from bisect import bisect_left
from collections import defaultdict
from datetime import date
import re


def _ranking_rows(rows):
    """Keep one unambiguous positive position per player in this source list."""
    ranks, excluded = {}, set()
    for row in rows:
        if len(row) < 2 or not row[0]:
            continue
        player, rank = row[:2]
        if player in excluded:
            continue
        if (not isinstance(rank, int) or isinstance(rank, bool) or rank < 1 or
                (player in ranks and ranks[player] != rank)):
            excluded.add(player)
            ranks.pop(player, None)
        else:
            ranks[player] = rank
    return ranks


def _period(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}', value):
        return None
    try:
        date.fromisoformat(value + '-01')
    except ValueError:
        return None
    return value


def match_ranking_context(data):
    """Return ``{match_id: {snapshot: snapshot_id, ranks: [p1_rank, p2_rank]}}``.

    Only ΓΕΝΙΚΟΣ lists qualify. For the latest period strictly before a match's
    month, prefer a shared national snapshot, then the match's primary region,
    then its other recorded regions (alphabetically). Snapshot ID breaks ties
    deterministically within a region. Neither player is looked up in a
    different snapshot, period, age bracket, or unrelated regional list.

    Conflicting duplicate player positions and unranked/invalid positions are
    unavailable. Duplicate snapshot IDs are also unavailable, since a returned
    reference would not identify one source list unambiguously. The result
    omits matches without sufficient context and never mutates the catalog.
    """
    by_period = defaultdict(list)
    snapshots = [s for s in data.get('snapshots', [])
                 if s.get('list') == 'ΓΕΝΙΚΟΣ' and s.get('id') and _period(s.get('period'))]
    id_counts = defaultdict(int)
    for snapshot in snapshots:
        id_counts[snapshot['id']] += 1
    for snapshot in snapshots:
        # Even a period whose list has unusable rows is still the latest
        # published period; it must not make us silently use stale rankings.
        by_period[snapshot['period']]
        if id_counts[snapshot['id']] == 1:
            by_period[snapshot['period']].append((snapshot, _ranking_rows(snapshot.get('rows', []))))
    periods = sorted(by_period)
    previous_months, candidates = {}, {}
    context = {}
    for match in data.get('matches', []):
        played = match.get('date')
        if not isinstance(played, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', played):
            continue
        try:
            date.fromisoformat(played)
        except ValueError:
            continue
        first, second = match.get('p1'), match.get('p2')
        if not match.get('id') or not first or not second or first == second:
            continue
        month = played[:7]
        if month not in previous_months:
            index = bisect_left(periods, month) - 1
            previous_months[month] = periods[index] if index >= 0 else None
        previous = previous_months[month]
        if previous is None:
            continue
        regions = ['national']
        primary = match.get('region')
        if primary and primary not in regions:
            regions.append(primary)
        regions.extend(sorted(set(match.get('regions') or []) - set(regions)))
        key = (previous, tuple(regions))
        if key not in candidates:
            candidates[key] = sorted(
                ((snapshot, ranks) for snapshot, ranks in by_period[previous]
                 if snapshot.get('region') in regions),
                key=lambda item: (regions.index(item[0]['region']), item[0]['id']))
        for snapshot, ranks in candidates[key]:
            if first in ranks and second in ranks:
                context[match['id']] = {'snapshot': snapshot['id'], 'ranks': [ranks[first], ranks[second]]}
                break
    return context
