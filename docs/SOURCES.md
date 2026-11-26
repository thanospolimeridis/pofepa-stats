# Source contract and audit

## Observed sources

The public ranking index groups workbooks into `ΠΑΝΕΛΛΑΔΙΚΑ`, `ΑΤΤΙΚΗ & ΝΟΤΙΑ ΕΛΛΑΔΑ` and `ΒΟΡΕΙΑ ΕΛΛΑΔΑ`. Its note says the regional rankings were unified in September 2026. The national May and June files are combined ranking lists and have no results sheet. Regional January–June and unified September/October files contain a results sheet.

All June 2026 regional DAI/name pairs were checked against the June nationwide list: every pair matched exactly, and North/South DAI sets did not overlap. This supports a common 2026 registration namespace. Four numbers change names across the full imported time range; they are quarantined into separate name-specific profiles rather than automatically merged.

The index labels are **months**, not verified publication dates. They are stored as `YYYY-MM`; the application does not fabricate a day of publication or use a month-end ranking as pre-match evidence.

## Workbook tables

`ΓΕΝΙΚΟΣ` has either 7 or 8 columns. Columns are selected by header, including `Νέα θέση`, `Ονοματεπώνυμο`, `Βαθμοί`, `Κατηγορία`, `Ομάδα`, `ΔΑΙ`. The optional `Από θέση` column is not needed. The birth-year column is ignored and never normalized.

Each category sheet has its own official `Νέα θέση`. Category ranks are not derived from the overall list. Each snapshot is keyed by **region + month + sheet name**. Category membership and ranking order are kept as published; equal points are not renumbered or given an invented tie-break.

`ΑΠΟΤΕΛΕΣΜΑΤΑ` has no header:

| Column | Meaning used by importer |
| --- | --- |
| A | Source match date, day/month/year |
| B, C | Player names |
| D, E | Final games won by each player |
| F, G | Source team names, sometimes blank |
| H | Competition name |
| I, J | Rating changes; deliberately not treated as scores |

Bonus rows include non-player text such as `Bonus 1ος…`. Source `1–0` or `0–1` outcomes have no established completed-match semantics, so they are excluded from played-match statistics. Twelve October result rows have a blank participant despite a numeric score. Their row locations remain in `issues`.

## HTML team fixtures

Only tables with explicit `Γηπεδούχος` and `Φιλοξενούμενος` headers are parsed. The preceding heading supplies the round. Score cells containing a leading numeric score are preserved as reported fixture totals; scheduling text remains a note.

`Ημ/νια ενδεχόμενου ορισμού` is a deadline, not a played date. Those values never enter chronological singles statistics. Score links usually point to scans on `files.ping-pong.gr`; the app keeps the link but does not claim to have transcribed it. Some of those external HTTPS endpoints have certificate issues; the collector does not disable TLS verification or fetch them. Their original HTTP links remain as published.

The 2026–2027 index also contains empty links to old seasons, PDF-only competitions and at least one named link into a previous season. They are not treated as current supported HTML fixtures. Pages without supported tables remain explicitly listed in coverage; their source page title is retained, including any stale year displayed by POFΕPA.

## Dataset schema 1

- `sources`: source ID, URL, UTC retrieval timestamp, byte count, response SHA-256.
- `players`: source DAI, display name, dated team/category observation, provisional/conflicting identity flags. Conflict variants have distinct profile IDs.
- `clubs`: source team name; hashed IDs do not establish official club identity.
- `snapshots`: ID, region, period, source, sheet/list name and compact rows `[player_id, source_rank, points, club_id, category, Excel_row]`.
- `matches`: source ID and Excel row, date, event, region, two player IDs, original names, final games, source teams, identity resolution method and supporting ranking sources for each side. Duplicate physical results keep all workbook/row references in `evidence`.
- `fixtures`: event, round, source, teams, reported total or null, deadline, schedule note, external match-sheet link.
- `events`: workbook competition aggregates use the exact competition label and season, retaining all contributing source regions; HTML fixture competitions have distinct records. Results are not guessed to belong to a league division when the workbook does not identify it.
- `issues`: excluded source rows and reasons. This is not evidence that all source errors have been detected.
- `coverage`: totals, cutoff, imported month range, deferred pages, other discovered workbooks and registration-name conflicts.

Player resolution uses the union of the same month’s national/regional general lists. A visiting player can therefore be resolved from their home-region list. Repeated DAI entries across national and regional sheets are treated as one candidate; equal names with different DAIs remain ambiguous.

The committed catalog contains the normalized source records. `build.py` checks it, embeds it safely in the HTML, and generates downloadable coverage/provenance reports. `audit_sources.py` independently checks every normalized ranking/match row against the corresponding raw workbook cells and verifies source hashes. Raw cache files are required only for replay/audit, never to build the site.

## Remaining work

- Review the four registration-name conflicts with additional evidence before merging any profiles.
- Resolve result names lacking an unambiguous corresponding ranking identity.
- Backfill pre-2026 ranking files after checking their formats and namespaces.
- Parse PDF/image-only fixtures and individual tournament documents with their own source-specific validation.
- Add new published months deliberately. A refresh does not expand the configured collection scope.

## Browser verification

The implementation is checked at desktop and narrow mobile widths, with ranking region/age changes, source-ranked positions, player search/profile histories, comparison routes and bilingual rendering. Domain tests validate disambiguation, invalid score exclusions, age-sheet ranks and post-merger regional boundaries. The complete route render smoke test runs in both languages against the committed data.
