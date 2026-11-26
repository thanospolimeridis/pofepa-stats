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

All 124 linked PDFs (166 pages) and seven result-section images have been reviewed. The documents supply 2,351 team results: 2,350 from PDFs and one from the handwritten North Aegean sheet. This replaces the earlier 750-row PDF import, adding 1,601 team results overall. Six images from 2007–2009 contain team standings only; their aggregate totals cannot establish specific matches. Two PDFs contain schedules/draws without reported scores.

The parser follows bracket connectors in both directions, joins fragmented borders, reads group matrices and explicit fixture lists, and preserves page, row or bounding-box evidence. Explicit fixture names determine score orientation; draw numbers sometimes disagree with the printed name order. Matrix mirrors and repeated bracket/list representations count once. Group matches repeated in placement rounds remain separate. Byes are excluded. Administrative scores are retained as reported team results.

Broken Greek ToUnicode mappings are repaired from the embedded font's rendered glyph mapping where available. Clipped labels, abbreviations, finals split across pages, and a PDF without a usable font map have checked transcriptions in `data/document-reviews.json`. Each review is tied to a source SHA-256 and pinned result count and digest. A changed source or changed extraction must be reviewed before refreshing it. The 2022–2023 Peloponnese bracket repeats its second-page fixture list and is counted once.

Two placement scores on page 2 of `CUP-DELL-2024-25.pdf` are excluded: the winner labels name teams absent from their corresponding pairs. In the 2018–2019 Peloponnese cup, two matrix outcomes disagree with both the explicit fixture rows and the final standings; the explicit rows are used. The 2015–2016 Western Greece cup has inconsistent advancement between semifinal and final entrants; its directly named fixture rows are retained as printed. These decisions are documented in the review manifest.

The handwritten North Aegean final records ΓΑΤΕΛΟΥΖΟΙ 0–4 ΑΡΙΣΒΑΙΟΣ on 27 April 2023. Its three singles already exist in the April workbook and gain `document_evidence`, without duplicate matches or changed athlete totals. The doubles rubber is retained under the team fixture and excluded from singles statistics. Team totals do not imply individual athlete results. Schedule deadlines remain separate from actual dates played. Supplemental match-sheet links on imported HTML fixtures remain available as source links; this review covers the PDF/image sections linked from the season landing pages.

## Distribution and reproducibility

`data/catalog.json.gz` is deterministic gzip JSON with timestamps disabled in the compression header. The hosted build includes a small bootstrap archive, per-ranking shards, athlete buckets, event shards and full-dataset exports. Athlete buckets contain the complete associated match and ranking histories. The offline HTML embeds the complete compressed data.

Validation checks references, unique record IDs, legal singles scores, date bounds and reconciled counts. Source auditing independently compares every ranking row and every singles evidence row with the cached original cells. UI smoke tests exercise both languages and all routes against the hosted shards. Reproducibility checks hash every generated file recursively.

## Linked individual match sheets

The historical parallel-column importer retains score hyperlinks, including anchors that contain line breaks. Discovery checks that every existing fixture keeps the same teams, score and ID. There are 13,511 distinct linked sheets; match photographs and standings links are not treated as individual result sheets. The reviewed/pending counts are published in `coverage.match_sheets`.

The reviewed batches cover 282 September–November 2026 sheets, contributing 900 played singles and corroborating 951 existing workbook results. 64 more inspected sheets are held with source-bound reasons in `data/match-sheet-issues.json`; they add no singles. The remaining 13,165 linked sheets have not yet been reviewed. `data/match-sheet-reviews.json` binds every transcription to the source SHA-256, fixture, actual date and individual row. Explicit substitutions replace the normal A/B/C/X/Y/Z pairing for that row. 25 walkovers are retained under the team fixture but excluded from athlete statistics. An absent roster slot can be retained as a label for a walkover; it cannot become an athlete or a played match.

Athletes are checked using the printed registration where reliable, or a visually reviewed name and team association supported by the contemporary ranking roster. An existing provisional profile absent from the rankings may retain a cited prior result for the same team as identity evidence; this does not merge profiles or promote a handwritten registration to a verified ID. Printed registration errors are documented rather than used to silently attach results to a different player. Existing same-date player pairs and oriented scores are checked before insertion; conflicting or multiple candidates stop the import. Rankings are not recalculated. The match-sheet audit verifies hashes and requires an identical replay of the published data.
