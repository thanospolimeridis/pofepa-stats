import copy
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from collect import key, no_opponent, parse_fixture_tables, registry_id, resolve_player, score_status
from validate import bye, validate
from dataset import load


class ParserTests(unittest.TestCase):
    def test_only_completed_best_of_five_counts(self):
        for a, b in [(3, 0), (0, 3), (3, 1), (1, 3), (3, 2), (2, 3)]:
            self.assertEqual(score_status(a, b), "completed")
        for a, b in [(0, 0), (1, 0), (3, 3), (4, 2), (-1, 3), (3, 1.5), (3, None), (True, 3), (float('nan'), 3)]:
            self.assertEqual(score_status(a, b), "nonstandard_score")
        self.assertEqual(score_status(0, 0, "Bonus 1ος BET"), "bonus")

    def test_same_names_require_team_disambiguation(self):
        candidates = {key("ΓΕΩΡΓΙΟΥ ΙΩΑΝΝΗΣ"): [{"id": "p-1", "club": "ONE"}, {"id": "p-2", "club": "TWO"}]}
        self.assertEqual(resolve_player("Γεωργίου Ιωάννης", "TWO", candidates), ("p-2", "exact_name_and_team"))
        self.assertEqual(resolve_player("Γεωργίου Ιωάννης", "", candidates), (None, "ambiguous_name"))
        self.assertEqual(resolve_player("Γεωργίου Ιωάννης", "THREE", candidates), (None, "team_mismatch"))
        self.assertEqual(resolve_player("Γεωργιου Ιωαννη", "ONE", candidates), (None, "name_not_found"))

    def test_name_only_is_explicitly_provisional_association(self):
        candidates = {key("Example Name"): [{"id": "p-1", "club": "ONE"}]}
        self.assertEqual(resolve_player("Example Name", "", candidates), ("p-1", "unique_name_in_month"))
        self.assertEqual(resolve_player("Example Name", "TWO", candidates), (None, "team_mismatch"))

    def test_same_month_national_and_regional_duplicates_do_not_create_ambiguity(self):
        candidates = {key("Example Name"): [{"id": "p-1", "club": "ONE"}, {"id": "p-1", "club": "ONE"}]}
        self.assertEqual(resolve_player("Example Name", "", candidates), ("p-1", "unique_name_in_month"))
        candidates[key("Example Name")].append({"id": "p-2", "club": "TWO"})
        self.assertEqual(resolve_player("Example Name", "", candidates), (None, "ambiguous_name"))

    def test_changed_name_under_same_registration_stays_separate(self):
        registry = {"1": {key("A"), key("B")}, "2": {key("C")}}
        self.assertNotEqual(registry_id("1", "A", registry), registry_id("1", "B", registry))
        self.assertEqual(registry_id("2", "C", registry), "p-2")

    def test_fixture_deadlines_are_not_play_dates(self):
        html = '''<h2>1η Αγωνιστική</h2><table><tr><td>Γηπεδούχος</td><td>Φιλοξενούμενος</td><td>Σκορ</td><td>Ορισμός</td></tr>
        <tr><td>A</td><td>B</td><td><a href="http://files.ping-pong.gr/a.jpg">5-0</a></td><td>31/12/2026</td></tr>
        <tr><td>C</td><td>D</td><td>12/12, 18:00</td><td>15/12/2026</td></tr></table>'''
        rows = parse_fixture_tables(html, "s-1", "https://www.pofepa.gr/a.html", "e-1")
        self.assertEqual(rows[0]["score"], [5, 0])
        self.assertNotIn("date", rows[0])
        self.assertEqual(rows[1]["status"], "scheduled")
        self.assertIsNone(rows[1]["score"])
        self.assertEqual(rows[0]["round"], "1η Αγωνιστική")


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_committed_dataset_validates(self):
        validate(self.data)

    def test_region_age_positions_are_distinct_source_records(self):
        matches = [s for s in self.data["snapshots"] if s["period"] == "2026-06" and s["list"] == "BET 40-49"]
        self.assertEqual({s["region"] for s in matches}, {"north", "south", "national"})
        positions = {s["region"]: next((r[1] for r in s["rows"] if r[0] == "p-859"), None) for s in matches}
        self.assertEqual(positions["north"], 1)
        self.assertIsNone(positions["south"])
        self.assertGreater(positions["national"], 1)

    def test_no_fabricated_post_merger_regional_lists(self):
        self.assertFalse(any(s["region"] != "national" and s["period"] > "2026-06" for s in self.data["snapshots"]))

    def test_category_row_is_not_general_position(self):
        june = {s["list"]: s for s in self.data["snapshots"] if s["region"] == "north" and s["period"] == "2026-06"}
        rank = lambda sheet, pid: next(r[1] for r in june[sheet]["rows"] if r[0] == pid)
        self.assertEqual(rank("ANE 50-59", "p-7"), 1)
        self.assertNotEqual(rank("ΓΕΝΙΚΟΣ", "p-7"), rank("ANE 50-59", "p-7"))

    def test_changed_registration_has_two_profiles(self):
        rows = [p for p in self.data["players"] if p["registration"] == "2851"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(p["identity_conflict"] for p in rows))

    def test_no_birth_or_contact_fields(self):
        for p in self.data["players"]:
            self.assertFalse(set(p) & {"birth_year", "birth_date", "phone", "email", "address"})

    def test_invalid_scores_fail_build_validation(self):
        data = {**self.data, "matches": [dict(m) for m in self.data["matches"]]}
        data["matches"][0]["score"] = [3, 3]
        with self.assertRaisesRegex(ValueError, "Invalid completed score"):
            validate(data)

    def test_counts_reconcile(self):
        c = self.data["coverage"]
        self.assertEqual(sum(len(s["rows"]) for s in self.data["snapshots"]), c["ranking_rows"])
        self.assertEqual(sum(f["status"] == "reported" for f in self.data["fixtures"]), c["reported_fixtures"])
        self.assertEqual(len(self.data["issues"]), sum(c["excluded_rows"].values()))

    def test_no_placeholder_is_a_player_a_match_side_or_a_club(self):
        # "ΧΧΧ", "-" or "ΑΝΕΥ 1" stands where a player or team had no opponent.
        self.assertEqual([p["id"] for p in self.data["players"] if no_opponent(p["name"])], [])
        self.assertEqual([m["id"] for m in self.data["matches"] if any(no_opponent(n) for n in m["names"])], [])
        self.assertEqual([c["name"] for c in self.data["clubs"] if bye(c["name"])], [])
        self.assertGreater(self.data["coverage"]["excluded_rows"]["no_opponent"], 1000)
        byes = [f for f in self.data["fixtures"] if bye(f["home"]) or bye(f["away"])]
        self.assertGreater(len(byes), 800)
        self.assertTrue(all(f["score"] is None and not f.get("rubbers") for f in byes), "a bye is never a played fixture")
        # "ΑΝΕΥ ΑΓΩΝΟΣ" is a real team in the 2025-26 East Macedonia & Thrace league.
        self.assertIn("ΑΝΕΥ ΑΓΩΝΟΣ", {c["name"] for c in self.data["clubs"]})

    def test_results_under_one_date_heading_keep_that_date(self):
        # rl_03_2018.xls row 428 heads the second day "11-03-2018"; rl_be_05-2016.xls
        # row 19 heads a tournament "7-8/05/16", which is not one known day.
        source = {s["url"].rsplit("/", 1)[-1]: s["id"] for s in self.data["sources"]}
        second_day = [m for m in self.data["matches"] if m["source"] == source["rl_03_2018.xls"] and m["evidence"][0].get("date_row") == 428]
        self.assertEqual({m["date"] for m in second_day}, {"2018-03-11"})
        self.assertEqual(len(second_day), 56)
        ranged = [m for m in self.data["matches"] if m["source"] == source["rl_be_05-2016.xls"] and m["row"] >= 19]
        self.assertFalse([m["id"] for m in ranged if m["date"] == "2016-05-05"], "results below the range never take the earlier date")

    def test_skipped_rounds_are_listed_and_new_ones_with_results_need_review(self):
        # A parallel-column round that does not align yields no fixtures and is
        # listed under coverage. These ten print results that are not in the
        # catalog; a new one must be looked at before this list is extended.
        rounds = [d for d in self.data["coverage"]["deferred"] if d["reason"] == "unaligned_round"]
        self.assertEqual(len({(d["url"], d["table"]) for d in rounds}), len(rounds))
        with_results = {(d["url"].rsplit("/", 1)[-1], d["table"]): d["printed_results"] for d in rounds if d["printed_results"]}
        self.assertEqual(with_results, {
            ("2010-11-b.html", 0): 5, ("2012-13-a.html", 6): 5, ("2012-13-a.html", 8): 5, ("2012-13-b.html", 5): 5,
            ("2012-13-b.html", 7): 5, ("2012-13-c2.html", 0): 6, ("2012-13-d-mak.html", 0): 2, ("2012-13-a-mak.html", 3): 2,
            ("2015-16-b.html", 1): 4, ("2024-2025-e3.html", 9): 7})
        listed = {(f["source"], f["table"]) for f in self.data["fixtures"] if "table" in f}
        sources = {s["url"]: s["id"] for s in self.data["sources"]}
        self.assertFalse([d["label"] for d in rounds if (sources[d["url"]], d["table"]) in listed], "a listed round has no fixtures")

    def test_cross_region_results_count_once_and_retain_both_sources(self):
        shared = [m for m in self.data["matches"] if len(m["evidence"]) > 1]
        self.assertTrue(shared)
        self.assertEqual(sum(len(m["evidence"])-1 for m in shared), self.data["coverage"]["excluded_rows"]["overlapping_source_result"])
        for m in shared:
            self.assertEqual(len({e["source"] for e in m["evidence"]}), len(m["evidence"]))
            self.assertEqual(set(m["regions"]), {e["region"] for e in m["evidence"]})


if __name__ == "__main__":
    unittest.main()

class HistoricalTests(unittest.TestCase):
    def test_legacy_scores_and_grouped_dates_keep_context(self):
        import xlrd
        from workbooks import LegacySheet, result_rows
        class Sheet:
            name = 'ΑΠΟΤΕΛΕΣΜΑΤΑ'
            def get_rows(self):
                values = [['26/10/2011', 'A', 'B', '3-1', 'HOME', 'AWAY', 'CUP', 2, -1],
                          ['', 'C', 'D', '2-3', '', '', '', -1, 2]]
                return [[xlrd.sheet.Cell(xlrd.XL_CELL_TEXT, x) if isinstance(x, str) else xlrd.sheet.Cell(xlrd.XL_CELL_NUMBER, float(x)) for x in row] for row in values]
        rows = list(result_rows(LegacySheet(Sheet(), 0)))
        self.assertEqual(rows[1][1], ('26/10/2011', 'C', 'D', 2, 3, 'HOME', 'AWAY', 'CUP'))
        self.assertEqual(rows[1][2]['date_row'], 1)
        self.assertEqual(rows[1][2]['layout'], 'combined')

    def test_source_ties_and_unranked_entries_are_preserved(self):
        from collect import ranking_rows
        class Sheet:
            title = 'ΓΕΝΙΚΟΣ'
            def iter_rows(self, values_only=True):
                yield ('Θέση', 'Ονοματεπώνυμο', 'Βαθμοί', 'Κατηγορία', 'Ομάδα')
                yield (1, 'A', 12.5, 'ANE 18-39', 'X')
                yield ('"', 'B', 12.5, 'ANE 18-39', 'Y')
                yield ('-', 'C', '-', 'ANE 18-39', 'Z')
        rows = list(ranking_rows(Sheet()))
        self.assertEqual([r[1] for r in rows], [1, 1, None])
        self.assertIsNone(rows[-1][3])

    def test_historical_parallel_columns_do_not_shift_scores(self):
        html = '<h2>1η Αγωνιστική</h2><table><tr><td>A<br>B</td><td>-<br>-</td><td>C<br>D</td><td>5-1<br>2-5</td></tr></table>'
        rows = parse_fixture_tables(html, 'source', 'https://www.pofepa.gr/test.html', 'event')
        self.assertEqual([(r['home'], r['away'], r['score']) for r in rows], [('A', 'C', [5, 1]), ('B', 'D', [2, 5])])
        # Missing a score is ambiguous; never shift the second score up a row.
        bad = html.replace('5-1<br>2-5', '2-5')
        self.assertEqual(parse_fixture_tables(bad, 'source', 'https://www.pofepa.gr/test.html', 'event'), [])

    def test_explicit_blank_bye_score_preserves_following_result(self):
        html = '<h2>1η Αγωνιστική</h2><table><tr><td>A<br>B</td><td>-</td><td>XXX<br>C</td><td><br>5-2<br></td></tr></table>'
        rows = parse_fixture_tables(html, 'source', 'https://www.pofepa.gr/test.html', 'event')
        self.assertEqual([(r['home'], r['away'], r['score']) for r in rows], [('A', 'XXX', None), ('B', 'C', [5, 2])])

    def test_full_linked_workbook_archive_is_accounted_for(self):
        d = DatasetTests.data
        inventory = d['coverage']['workbook_inventory']
        # New monthly workbooks add to the archive; none may be skipped or listed twice.
        self.assertGreaterEqual(len(inventory), 270)
        self.assertEqual(len({i['url'] for i in inventory}), len(inventory))
        self.assertTrue(all(i['imported'] for i in inventory))
        self.assertEqual(d['coverage']['ranking_periods'][0], '2011-10')
        self.assertGreater(d['coverage']['matches'], 130000)
        self.assertGreater(d['coverage']['ranking_rows'], 700000)
        self.assertGreaterEqual(d['coverage']['match_date_min'], '2011-01-01')
