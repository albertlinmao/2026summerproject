import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ingest_figures  # noqa: E402
from scripts.ingest_figures import (  # noqa: E402
    build_supabase_payload,
    extract_text_from_pdf,
    parse_figure_pdf_text,
)


class IngestFiguresTests(unittest.TestCase):
    def test_get_supabase_config_uses_local_stack_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".env").write_text(
                "SUPABASE_URL=postgres://localhost:5432/postgres\n", encoding="utf-8"
            )
            (root / "supabase").mkdir(parents=True, exist_ok=True)
            (root / "supabase" / ".env").write_text(
                "SERVICE_ROLE_KEY=test-service-role-key\n", encoding="utf-8"
            )

            with patch.dict(os.environ, {}, clear=True):  # noqa: SIM117
                with patch.object(ingest_figures, "ROOT_DIR", root):
                    config = ingest_figures.get_supabase_config()

        self.assertEqual(config["url"], "http://localhost:8000")
        self.assertEqual(config["key"], "test-service-role-key")

    def test_build_supabase_payload_contains_separate_entities(self) -> None:
        pdf_path = (
            ROOT
            / "swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf"
        )
        text = extract_text_from_pdf(str(pdf_path))
        parsed = parse_figure_pdf_text(text)
        payload = build_supabase_payload(parsed, str(pdf_path))

        self.assertEqual(
            payload["meet"]["meet_name"], "2026 Youth Championship and 12u Invitational"
        )
        self.assertEqual(payload["meet"]["age_group"], "Age Group 12 and Under Figures")
        self.assertEqual(payload["meet"]["location"], "Buffalo, NY")
        self.assertEqual(payload["meet"]["meet_date"], "2026-04-23")
        self.assertTrue(payload["judges"])
        self.assertEqual(payload["routines"][0]["figure_number"], 1)
        self.assertEqual(payload["athletes"][0]["athlete_name"], "SHEN Jasper")
        self.assertEqual(payload["athletes"][0]["figure_scores"][0]["figure_number"], 1)


if __name__ == "__main__":
    unittest.main()
