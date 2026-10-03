"""Figure parse contract.

The previous version of this file could not run: it called `build_supabase_payload`,
which does not exist, and pointed at `YouthChampionshipand12uinvitational/`, a folder
name that no longer exists. It also asserted a payload shape (`meet_name`, `age_group`,
`location`, `routines`, `figure_scores`) that the parser stopped producing. These
assertions describe what the parser produces today.

Run: python -m unittest tests.test_ingest_figures -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.ingest_figures import (  # noqa: E402
    extract_text_from_pdf,
    parse_figure_pdf_text,
)

FIXTURE = ROOT / ("swim-meets/2025/20251207_Monte Johnson Figure Meet_Tukwila_WA"
                  "/Age-12-and-under_figure.pdf")


@unittest.skipUnless(FIXTURE.exists(), f"fixture PDF missing: {FIXTURE}")
class FigureParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = parse_figure_pdf_text(extract_text_from_pdf(str(FIXTURE)))

    def test_header_gives_event_meet_and_date(self):
        self.assertEqual(self.parsed["event"]["event_name"], "Monte Johnson Figure Meet")
        self.assertEqual(self.parsed["meet"]["name"], "Age Group 12 and Under Figures")
        self.assertEqual(self.parsed["event"]["event_date"], "7 DEC 2025")
        self.assertIn("Tukwila", self.parsed["event"]["host_city"])

    def test_figures_carry_code_name_and_difficulty(self):
        figures = self.parsed["figures"]
        self.assertEqual(len(figures), 4)
        first = figures[0]
        self.assertEqual(first["figure_code_short"], "F1")
        self.assertEqual(first["figure_code"], "Figure 1")
        self.assertTrue(first["name"])
        self.assertIsInstance(first["degree_difficulty"], float)

    def test_judge_panels_are_keyed_by_figure_and_one_referee(self):
        judges = self.parsed["judges"]
        per_figure = [j for j in judges if j.get("figure_code_short")]
        referees = [j for j in judges if j.get("panel_name") == "Referee"]
        self.assertEqual(len(per_figure), 4)
        self.assertEqual(len(referees), 1)
        for judge in per_figure:
            self.assertIn(judge["figure_code_short"], {"F1", "F2", "F3", "F4"})
            self.assertTrue(judge["panel"], "a panel row with no judges is not useful")

    def test_athletes_carry_rank_name_and_birth_year(self):
        athletes = self.parsed["athletes"]
        self.assertEqual(len(athletes), 11)
        first = athletes[0]
        self.assertEqual(first["rank"], "1")
        self.assertEqual(first["athlete_name"], "YANG Emily")
        self.assertEqual(first["athlete_birth_year"], 2014)
        self.assertEqual(first["team_code"], "SST")

    def test_figure_scores_are_per_figure_with_one_score_per_judge(self):
        athlete = self.parsed["athletes"][0]
        results = athlete["figure_results"]
        self.assertEqual(len(results), 4)
        judge_count = len(self.parsed["judges"][0]["panel"])
        for item in results:
            self.assertEqual(len(item["judge_scores"]), judge_count)
            self.assertIsInstance(item["total_score"], float)

    def test_athlete_total_is_the_sum_of_the_figure_totals(self):
        for athlete in self.parsed["athletes"]:
            parts = [f["total_score"] for f in athlete["figure_results"]
                     if f["total_score"] is not None]
            self.assertAlmostEqual(athlete["total_score"], sum(parts), places=6)

    def test_no_warning_on_a_known_good_layout(self):
        self.assertEqual(self.parsed["warnings"], [])

    def test_payload_carries_every_entity_the_writer_needs(self):
        # The keys insert_rows_to_supabase reads. A missing one is a KeyError at write
        # time, after the event and meet already exist.
        for key in ("event", "meet", "figures", "judges", "athletes", "warnings"):
            self.assertIn(key, self.parsed)


if __name__ == "__main__":
    unittest.main()