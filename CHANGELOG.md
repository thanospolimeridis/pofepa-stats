# Changelog

## Prototype updates — 2026-11-27

- Refresh the visual design within the existing ink, teal and mint palette: pill navigation, the archive totals beside the search in the hero, a latest-ranking banner, flat rounded cards with their headings inside, a category-free home ranking with position chips, one linked row per home competition, each player's games as a chip beside the name in match rows, a segmented athlete section switch, and proportional bars in the athlete score breakdown.
- Remove the imported-matches statistics notice from the overview, competition, comparison, and athlete pages.
- Keep the language switch visible on phones, bring the current section into view in the scrolling menu, and fade its clipped edges.
- Open Coverage & sources with its explanations, then paginate the match-sheet, document and source lists.
- Label match rows, home-page competitions and the competition filter with the region where the competition is played, falling back to the ranking-source region when the results site gives none.
- Load the Matches page from a compact match list instead of the full records, and search names without re-normalising every row on each keystroke. The full records remain the CSV export source.
- Add a season filter to Matches, group competitions by season, and show the season in each competition name.
- Download the dataset as the published gzip catalog in both editions, without parsing and re-serialising the whole archive in the page.
- Return to the previous scroll position on Back/Forward, move focus to the new page's heading after navigation, make the ranking chart a single tab stop with arrow-key navigation, and title missing pages "Page not found".
- Replace the Head to head datalist of every profile with a player picker: accent-insensitive Greek or Latin search over name, registration and team, keyboard and touch selection, and ranked suggestions.
- Read league rounds whose columns continue in a nested table. Seven merged fixtures, including one published 5–1 result between a separator column and eight teams, are replaced by their real games, recovering 26 fixtures on seven pages from 2023–24 to 2025–26.
- Bring the catalog in line with the current HTML parser: 35 more fixtures from rounds missing on four 2013–14 and 2022–23 pages. In all, 61 fixtures and 51 match-sheet links are added; no fixture with match-sheet results changes.
- Record byes as a dash with no club instead of a team named "-", and reject fixture team names without a letter.
- Re-point two held 2025–26 match sheets to the fixtures that now link them and note on four held sheets that their fixture is now read correctly. Seven newly linked 2025–26 sheets await review.
- Stop reading individual-event headings in older workbooks as teams: 6,033 singles results no longer carry a category, stage, row header or tournament name as a club, and wrapped team names keep their real team. 121 placeholder clubs drop out.
- Merge 388 provisional profiles that were split only by those placeholders into 113 (links to the old profiles redirect). 53 match sides now link to a registered profile under the existing rule for results without a team; two sides become provisional because a restored team's spelling differs from the ranking list. Match dates, scores, events and counts are unchanged.

## Prototype updates — 2026-11-26

- Bring the athlete directory and profiles close to Greek TT Archive: dark profile headers, a full-width combined chart with date ranges, win/loss cards, score and opponent breakdowns, source-linked best wins, and season/competition summaries. Keep ranking comparison data in lazy athlete archives and preserve match correction evidence.

- Separate cups from leagues within each region. Show source-faithful cup draws with zoom, match-sheet links, byes and progression to the winner; load each draw only on demand and preserve the full offline archive.
- Connect confirmed winners in historical HTML cup rounds, keeping group and placement stages separate. Restore eight omitted 2012–13 Central Macedonia first-round team results by preserving spaces within BR-delimited team names.

- Group league fixtures under their published round headings, retaining complete rounds across pagination and showing unnamed PDF rounds explicitly.

- Remove the separate Teams directory and navigation entry; retain contextual team details and redirect old directory links to Competitions.

- Group competitions under POFΕPA's original regional headings, retain historical source context, and add region/season filters with the latest team competitions shown first.
- Move the athlete ranking chart and match breakdown above match history, with section shortcuts following the page order.

- Combine athlete ranking points into one chronological chart without regional or national labels; preserve distinct published values and collapse identical points for the same month. Remove the redundant full ranking table from athlete pages.

- Defer team fixtures and detailed source reports until their pages are opened, reducing the compressed initial data package by 68.6% while retaining the complete offline archive.
- Expose reviewed match corrections and their evidence in match history and CSV exports; show readable match cards on narrow screens.
- Add accessible athlete section shortcuts and paginate matches in compact ten-row pages while retaining all history.

- Complete review of every available 2025–26 match sheet, publish per-season coverage, and track unavailable source files separately.
- Correct source-verified dates, scores and participants while preserving original workbook records; reconcile explicit no-play awards without removing played retirements.

- Reject a reviewed walkover when the same athletes and date are already counted as played, requiring source reconciliation before acceptance.
- Record whole-team no-shows without inventing individual results, and retain both original and recovered URLs when a match sheet is linked from the wrong fixture.

- Offer a page reload when an older open tab cannot render newly published archive data.
- Retain historical match-sheet links and add 939 reviewed singles to athlete pages, with substitutions, walkover exclusions and visible import progress. Corroborate 10,083 existing workbook results and record 303 sheets excluded from the singles import separately.

- Review 124 PDFs and seven images; add 1,601 team results, preserve document evidence and disclose contradictory source labels.
- Confirm three existing singles from the handwritten final, retain its doubles result, and show document coverage on the sources page.

- Import every linked historical XLS/XLSX ranking workbook, preserving region and age-bracket positions from 2011–2026.
- Import historical singles and team results, including supported PDF tables and brackets, with source anomalies and unresolved sections disclosed.
- Show all linked rankings and matches on athlete pages; remove athlete region and age selectors.
- Load hosted data by ranking, athlete and competition; retain a complete compressed offline edition.
- Audit historical formats, source cells, ranking ties, duplicate exports and dates.


## 0.1.0

- Initial local POFΕPA archive with 2026 regional and national data.
- Rankings by source region, veteran/independent division, age bracket and month.
- Player profiles, ranking charts, match statistics, team fixtures and head-to-head comparisons.
- Greek/English navigation, CSV/JSON exports and offline HTML build.
- Cached importer, source hashes, unresolved identity handling and validation workflows.
