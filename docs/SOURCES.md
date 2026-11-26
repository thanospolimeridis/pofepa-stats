# Source contract

## Discovery and provenance

The collector reads the POFΕPA ranking index headings to assign `north`, `south`, or `national`; it discovers every linked XLS/XLSX workbook. Source filenames provide the month. All 270 distinct linked workbooks are imported. Result seasons are discovered specifically from the **Αποτελεσματα** navigation menu, avoiding similarly named competition-announcement pages.

Each fetched source records its public URL, retrieval time, byte length and SHA-256. Raw files and cache metadata stay in ignored `capture/`. No credentials or private data are needed.

One index error is confirmed: the North link labeled **ΝΟΕ/2011** points to `rl_be_11-2014-v3.xls`. Its result dates and ranking contents confirm November 2014. The correctly labeled November 2014 link points to v2, whose ranking rows are identical. Both source versions are preserved as separately attributed snapshots; no November 2011 North snapshot is fabricated.

## Ranking records

A snapshot records region, month, canonical list title, original worksheet title, source ID and rows:

```text
[player_id, source_rank, source_points, club_id, source_category, Excel_row]
```

A missing source rank or points value remains null. Ditto marks copy the preceding tied rank. Negative points are valid source values. Historical Greek division names are normalized to ANE/BET for consistent navigation, but age brackets and source positions remain unchanged. Repeated athlete entries in a sheet remain separate rows and receive `repeated_source_ranking` issues.

Registration-free historical entries are matched only through exact names and supporting team or unique-name evidence. Names repeated in a historical general list remain separate. Registration conflicts are split by normalized name. Source birth years, addresses and contact fields are omitted.

## Singles results

Both XLS and XLSX formats are supported. Published score layouts include a combined score cell, separate columns D/E, shifted columns E/F, and compact individual-tournament sheets without teams. The dominant explicit score layout is detected per sheet; point-change columns are not interpreted as scores.

Legacy worksheets leave repeated dates, teams and event labels blank within a group. The importer carries the written context and retains its row numbers in every evidence object (`date_row`, `team_row`, `event_row`), alongside the original sheet, result row and detected layout. Explicit new dates reset carried teams. Numeric totals are never interpreted as team names.

Results require two distinct named participants, a valid date and a completed best-of-five score. Dates more than one calendar year away from their workbook are quarantined as `date_outside_workbook_year`; source mistakes such as 1949 in a 2019 workbook are not silently corrected. Future dates, missing context, nonstandard scores and bonus rows are also reported as exclusions.

Exact name/team associations and provisional unique-name associations are distinguished in `identity`. Each association retains its ranking-source evidence. Unresolved identities remain source/event-scoped rather than being merged by similar spelling. Cross-source duplicate results keep all corroborating source rows; occurrence counts preserve legitimate repeats within a single source.

## Team fixtures and PDFs

Supported HTML layouts include modern headed tables, round tables without column headings, and historical parallel columns separated by line breaks or explicit wide spacing. Parallel columns must align exactly; missing cells are not shifted to guess opponents or scores.

PDF group-result rows retain page and text-line evidence. Knockout brackets are read through their drawn horizontal and vertical connectors. A recorded bracket winner must exactly match one of the two connected teams. Ambiguous sections remain in the deferred list, including partially parsed documents. Blank draws are not wins. Source fonts sometimes contain imperfect text mappings; original spellings are retained rather than guessed.

Team totals do not imply individual athlete results. Match-sheet image links are retained as source evidence; individual scores come from the official workbooks. Reported schedule deadlines remain separate from dates played.

## Distribution and reproducibility

`data/catalog.json.gz` is deterministic gzip JSON with timestamps disabled in the compression header. The hosted build includes a small bootstrap archive, per-ranking shards, athlete buckets, event shards and full-dataset exports. Athlete buckets contain the complete associated match and ranking histories. The offline HTML embeds the complete compressed data.

Validation checks references, unique record IDs, legal singles scores, date bounds and reconciled counts. Source auditing independently compares every ranking row and every singles evidence row with the cached original cells. UI smoke tests exercise both languages and all routes against the hosted shards. Reproducibility checks hash every generated file recursively.
