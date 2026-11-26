# POFEPA Stats · Αγώνες & αθλητές

An independent POFΕPA table tennis archive, built in the same spirit as [Greek TT Archive](https://github.com/thanospolimeridis/greek-tt-stats): **Python ingestion, a static website, no database or frontend dependencies, and an offline HTML edition**.

## Browse locally

The generated `index.html` can be opened directly, including all searches and charts. To serve the site:

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

Open `http://localhost:8000`. Builds need Python 3.10+ and the committed dataset only; they make no network requests. The generated files are ignored by Git.

## Rankings: region first, then division and age

Rankings use the **official age-category worksheet**, not a general list filtered and renumbered by age. The main controls select:

- Region: **North Greece**, **Attica & South Greece**, or **Nationwide**.
- Division: veterans (`BET`) or independent players (`ANE`).
- Published age bracket: independent 18–39; veteran 30–39; then 40–49, 50–59, 60–64, 65–69 and 70+.
- Source month.

The source publishes a combined women's list without separate age worksheets. That table is available with an explicit note, as is the overall ranking.

**North and South lists were unified from September 2026.** Their separate histories here end in June 2026. September and October are nationwide lists; the site does not invent regional ranks from them. Source categories are preserved even when a label appears unusual. No birth years are published or used to recalculate categories.

## Current coverage — 26 November 2026

| Data | Imported scope |
| --- | --- |
| Regional rankings | North and South: January–June 2026, 12 workbooks |
| National rankings | May, June, September and October 2026, 4 workbooks |
| Ranking records | 88,170 rows in 256 dated, regional/category lists |
| Ranked identities | 3,113 profiles representing 3,109 source registration numbers; 4 changed-name numbers are kept split pending review |
| Singles results | 12,814 completed matches, dated 1 January–31 October 2026 in the source |
| Team schedules | 1,262 fixtures, 294 with a reported score, from supported current-season HTML tables |
| Unresolved match identities | 68 source/event-scoped profiles, not merged into ranking identities |
| Excluded result rows | 476 bonus rows, 36 nonstandard scores, 12 rows missing participants, and 357 repeated exports already represented by another source |

This is **partial 2026 coverage**, not a complete historical archive. There are no July/August result workbooks in this import scope. PDF/image-only regional results, cup brackets and pre-2026 archives remain untranscribed. The source catalog and deferred pages are retained in the dataset and exposed on About. Team results can be newer than the latest imported singles workbook.

Implemented: Greek/English interface; Greek accent-insensitive and transliterated player search; player profiles with season filters, W/L, win rate, games won/lost and deciding-game records; region-specific age-bracket ranking histories; matches and fixture filters; competition and team pages; shareable head-to-head comparisons; CSV/JSON downloads; source links and spreadsheet row numbers; responsive layouts.

## Refresh and reproduce

Install importer/test dependencies in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Fetch any missing files, use existing cached sources otherwise:
python3 scripts/collect.py --as-of 2026-11-26

# Replay exactly the downloaded sources, with the same cutoff:
python3 scripts/collect.py --offline --as-of 2026-11-26

# Fetch the configured scope again (review the data diff before publishing):
python3 scripts/collect.py --refresh --as-of YYYY-MM-DD

python3 scripts/build.py
python3 -m unittest discover -s tests -v
node tests/smoke.js
python3 scripts/check_reproducible_build.py
python3 scripts/audit_sources.py  # requires the ignored raw cache
```

`--output PATH` stages a collection separately; `--cache PATH` selects a different cache. The collector replaces its selected output only after validation. Ranking download/schema failures abort. Unavailable fixture pages are reported explicitly in coverage. Raw downloads, their timestamps and metadata live in ignored `capture/`; normalized data, source URLs and SHA-256 hashes are committed in `data/catalog.json`.

The importer refreshes the **explicit `WORKBOOKS` scope** in `scripts/collect.py`. New months are not silently included: inspect the new workbook and add its `(YYYY-MM, region, filename)` entry before recollecting. Discovery records the other published workbook URLs for later backfill. No periodic automation is enabled.

## Identity and score policy

- Source DAI is the ranking identity key. If its normalized name changes, **all variants are separated** until reviewed. This prevents merging a reused or mistyped number into someone else's profile. Four such numbers are recorded in `coverage.identity_conflicts`.
- Result sheets omit DAI. Exact name plus exact team across the **same month’s ranking lists** resolves a player. With a blank team, a unique exact name across those lists is a *provisional association*, retained as `unique_name_in_month`. Conflicting teams and ambiguous names are kept as distinct unresolved profiles. No fuzzy matching or manual spelling corrections are applied.
- Only numeric completed best-of-five scores (`3–0`, `3–1`, `3–2`, either orientation), nonempty distinct participants and valid dates through the cutoff enter statistics. Bonus rows, nonstandard outcomes and missing participants are recorded as exclusions. There are no invented set points or walkover wins.
- Same-day repeated matches within one source are retained. Overlapping identical results across workbooks use occurrence counts to avoid double counting repeated exports without discarding legitimate within-source repeats. Every corroborating workbook/row is retained. An unresolved participant may be matched as part of an identical result by its exact name/team, without linking it to a ranked identity.
- Fixture deadlines remain `deadline`, never `date`. Reported team totals are displayed as published. No individual match results or standings are reconstructed from them.
- Team names are exact source strings with whitespace cleanup. Different spellings remain separate. Profile team labels are dated observations, not inferred current membership.

Read [the source contract](docs/SOURCES.md) for schema, evidence and remaining coverage.

## Repository and deployment

```text
Public POFΕPA pages and XLSX workbooks
  → capture/ (ignored raw sources)
  → scripts/collect.py → data/catalog.json (normalized, attributed records)
  → scripts/build.py → index.html + dist/ (offline/static website)
```

The repository is local and has no configured GitHub remote or deployed URL. It includes GitHub Actions validation and a manually triggered Pages workflow. To publish after creating/pushing a GitHub repository, select **GitHub Actions** as the Pages source in repository settings, then run **Publish GitHub Pages**. Ordinary pushes run validation only.

No API keys, cookies or secrets are required. Production builds run offline against the committed dataset; only the collector contacts POFΕPA.

## License and attribution

Code is MIT licensed. Design and architecture follow Greek TT Archive; its attribution is retained in `LICENSE`. Third-party sports data and source documents are not covered by this code license. The site links every result to [POFΕPA](https://www.pofepa.gr/) and the [ranking archive](https://www.pofepa.gr/piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html).
