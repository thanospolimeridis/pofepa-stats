# POFEPA Stats · Αγώνες & αθλητές

[Website](https://thanospolimeridis.github.io/pofepa-stats/) · [Offline edition](https://thanospolimeridis.github.io/pofepa-stats/offline.html) · [Source archive](https://www.pofepa.gr/piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html)

An independent Greek/English POFΕPA table tennis archive, following [Greek TT Archive](https://github.com/thanospolimeridis/greek-tt-stats): Python ingestion, a static website, no backend, and an offline HTML edition.

## Match-sheet imports

Linked team-result sheets are being reviewed newest first. The reviewed batches cover **1689 sheets from the 2025–26 and 2026–27 seasons**, adding **939 played singles** directly to athlete histories and corroborating 10,083 existing workbook results. 329 individual walkovers and 11 whole-team no-shows are excluded from player statistics. Another 303 inspected sheets remain outside the singles import because they need clarification or record an unplayed team fixture. The archive now retains **13,511 match-sheet links**, of which **11,518 have not yet been reviewed**; the website reports the reviewed and pending counts explicitly. Unavailable source links (1) are tracked separately.

`data/match-sheet-issues.json` records held sheets and the reason each remains unimported. `data/match-sheet-reviews.json` records the source hash, actual date, row scores, substitutions and checked athlete identities. Replaying a sheet corroborates an existing result instead of creating a duplicate. Explicit sheet-backed corrections retain the complete original workbook record for audit. Unavailable links are tracked separately in `data/match-sheet-unavailable.json`.

The 2025–26 review is complete: every available linked sheet has been inspected. Unresolved source conflicts remain listed for clarification, and the unavailable sheet is tracked separately. Older seasons still have a review backlog.

## Historical coverage

All **270 distinct Excel workbooks** linked in the official ranking archive are imported, covering **October 2011–October 2026** and **742,275 ranking records**. Every published regional and age-category position is retained. The archive contains over **137,000 completed singles matches**, together with historical team results from HTML pages, 124 reviewed PDFs and a handwritten match sheet. The document review adds 1,601 team results, bringing reported team results to 17,118. Six older images contain standings only. Exact current counts, exclusions, source hashes and unparsed documents are available on the website's **Coverage & sources** page and in `dist/coverage.json`.

The results menu is inventoried for every listed season, from 2007–2008 through 2026–2027. The two earliest season pages currently link no results; the imported team pages start in 2009–2010. Some source documents contain ambiguous layouts or incomplete score fields. Those sections remain explicitly listed for review; this does not claim that every match ever played is recoverable.

Rankings remain separated into **North Greece**, **Attica & South Greece**, and **Nationwide**, then into the source's age brackets. September 2026 onward uses the unified national rankings. Historical age-sheet titles are normalized (`ΑΝΕΞΑΡΤΗΤΟΙ` → `ANE`, `ΒΕΤΕΡΑΝΟΙ` → `BET`), with original worksheet names retained for evidence. Positions are never recalculated from a filtered overall ranking. Tied positions and unranked source entries are preserved. Birth years are not published.

Athlete pages show **all linked matches** and one chronological ranking-points chart, combining published general-ranking points without regional or national labels. Identical month/value pairs appear once; distinct published values are preserved. There are no region or age selectors or detailed ranking tables on athlete pages. The ranking chart and match breakdown appear above match history, with section shortcuts in the same order. Match statistics default to all seasons, and match history shows the newest results first with ten matches per page. The dedicated rankings page retains every region and age category. Team details remain accessible through athlete and result links; there is no separate Teams directory.

## Build and preview

Competitions follow the original results site's regional groups. The latest season's team competitions open first, with region, season and record-type filters. `data/competition-regions.json` preserves the source-page heading, link label and page hash for historical competition links; regenerate it from the cached season pages with `.venv/bin/python scripts/competition_regions.py`. New collections retain the same regional context. Workbook coverage regions are not treated as competition geography; records without a specified competition region remain separately accessible.

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

Open `http://localhost:8000`. The generated root `index.html` and `dist/offline.html` contain the complete compressed archive and can be saved for offline use. The hosted site loads ranking, athlete and competition data on demand; team fixtures and detailed source reports load only on their respective pages. The compressed initial data package is approximately 631 KB, down from 2.01 MB. A modern browser with `DecompressionStream` support is required.

The committed dataset is `data/catalog.json.gz`. Builds require Python 3.10+ and make no network requests. Generated files and raw downloads are ignored by Git.

## Collect, validate and reproduce

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Also install Poppler (pdftotext) for PDF collection, e.g. brew install poppler.

python3 scripts/collect.py --as-of 2026-11-26
python3 scripts/collect.py --offline --as-of 2026-11-26
python3 scripts/build.py
python3 -m unittest discover -s tests -v
node tests/smoke.js
node tests/evidence.js
node tests/export.js
node tests/bootstrap.js
node tests/hydration.js
python3 scripts/check_reproducible_build.py
python3 scripts/audit_sources.py
python3 scripts/audit_documents.py
python3 scripts/audit_match_sheets.py
python3 scripts/import_match_sheets.py --offline --discover
# Refresh the reviewed documents without rebuilding unchanged workbook data:
python3 scripts/refresh_documents.py --offline
```

The collector discovers all linked workbooks and result seasons rather than maintaining a fixed month list. `--refresh` refetches sources; `--cache PATH` selects the raw cache; `--output PATH` stages a separate collection. Validation must pass before the output is atomically replaced. The source-cell audit requires the original ignored `capture/` downloads.

## Identity and evidence

- Reviewed corrections expand beside the match to show the original record, corrected result, supporting match sheet, review note and document hash. Match CSV exports include structured source references and correction provenance.
- Ranking DAI registration numbers identify athletes. Conflicting names under a number remain separate, with the conflict disclosed.
- Earlier lists omit DAI. An exact name and team, or a unique exact name among registered profiles, can associate the historical entry. Names appearing more than once in historical general lists remain separate.
- Match records link against the same month's ranking lists. Exact name plus team is preferred; unique exact names with blank or differing teams are provisional associations. Ambiguous or unmatched names remain separate profiles. No fuzzy spelling matching is used.
- Older spreadsheets use grouped dates and team headings, numeric text scores, combined score cells and different column layouts. The importer retains the worksheet, result row and context row numbers used to interpret each result.
- Only completed 3–0, 3–1 and 3–2 singles scores enter statistics. Invalid dates, implausible years, bonus entries and nonstandard outcomes are excluded with reasons. Scores and dates are never invented.
- Repeated result exports are deduplicated while preserving every source row. Repeated games within one source remain separate. Repeated ranking entries remain as published and are flagged.
- Team fixtures retain reported totals and source-page references. Schedule deadlines are not treated as dates played. PDF brackets use drawn connectors, named winners and source-bound visual transcriptions. Repeated grids and bracket pages count once; real repeats in later rounds remain separate.

See [SOURCES.md](docs/SOURCES.md) for the source contract and known anomalies.

## Deployment

Pushes to `main` validate, build, verify reproducibility and publish `dist/` through GitHub Actions. During prototyping, each validated change is also pushed to `main` for immediate preview. No new version numbers or release tags are created until the prototype is ready. The full normalized dataset and offline edition are downloadable; the hosted HTML is small and loads compressed data shards on demand.

Code is MIT licensed, with Greek TT Archive attribution retained in `LICENSE`. Third-party sports data and source documents remain attributed to POFΕPA and are not covered by the code license.
