"""Tests for auth-user provisioning performed by the ingest path.

These use a fake GoTrue admin endpoint: the behaviours being guarded are what
payload gets sent, what happens on a repeat run, and which lifecycle status a
seeded profile is given. None of that needs the live database, and a test that
provisioned real accounts would be both slow and destructive.

Run: python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import user_mgmt_sync as U  # noqa: E402
from scripts import ingest_figures, ingest_routines  # noqa: E402

SUPABASE_CONFIG = {"url": "https://example.supabase.co", "key": "service-role-key"}


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or ""

    def json(self):
        return self._payload


class FakeAdminAPI:
    """Stands in for requests against /auth/v1/admin/users.

    Mirrors GoTrue's one behaviour that the caller must survive: creating a user
    whose email already exists is a 422 with error_code 'email_exists', not a
    200 returning the existing row.
    """

    def __init__(self, existing_emails=None):
        self.existing = {e.lower() for e in (existing_emails or [])}
        self.created = []          # (email, password, email_confirm)
        self.list_calls = 0

    def post(self, url, headers=None, json=None, timeout=None):
        email = (json or {}).get("email", "")
        self.created.append((email, (json or {}).get("password"),
                             (json or {}).get("email_confirm")))
        if email.lower() in self.existing:
            return FakeResponse(422, {"error_code": "email_exists",
                                      "msg": "User already registered"})
        self.existing.add(email.lower())
        return FakeResponse(200, {"id": f"uuid-for-{email.lower()}"})

    def get(self, url, headers=None, params=None, timeout=None):
        self.list_calls += 1
        users = [{"id": f"uuid-for-{e}", "email": e} for e in sorted(self.existing)]
        return FakeResponse(200, {"users": users, "last_page": 1})


class PasswordDefaultTests(unittest.TestCase):
    """The seeded password must be overridable and must have a documented fallback."""

    def test_env_var_overrides_the_default(self):
        with patch.dict(os.environ, {"INGEST_DEFAULT_PASSWORD": "Chosen-By-Operator"}):
            with patch.object(U.os, "getenv", U.os.getenv):
                import importlib
                reloaded = importlib.reload(U)
                try:
                    self.assertEqual(reloaded.DEFAULT_PASSWORD, "Chosen-By-Operator")
                finally:
                    importlib.reload(U)

    def test_default_is_used_when_env_var_absent(self):
        import importlib
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INGEST_DEFAULT_PASSWORD", None)
            reloaded = importlib.reload(U)
            try:
                self.assertEqual(reloaded.DEFAULT_PASSWORD, "pa$$word$d3Faul%")
            finally:
                importlib.reload(U)

    def test_default_password_is_not_empty(self):
        self.assertTrue(U.DEFAULT_PASSWORD, "a blank seed password would be unusable")


class ProvisionAuthUserTests(unittest.TestCase):
    """get_or_create_auth_user is what both ingest scripts rely on."""

    def _run(self, api, email):
        with patch.object(U, "requests", api):
            return U.get_or_create_auth_user(SUPABASE_CONFIG, email)

    def test_creates_with_default_password_and_confirms_email(self):
        api = FakeAdminAPI()
        self._run(api, "alice.zhang@tuk.swim")
        self.assertEqual(len(api.created), 1)
        email, password, confirmed = api.created[0]
        self.assertEqual(email, "alice.zhang@tuk.swim")
        self.assertEqual(password, U.DEFAULT_PASSWORD)
        self.assertTrue(confirmed,
                        "an unconfirmed email would block sign-in for seeded accounts")

    def test_repeat_run_is_idempotent_and_returns_existing_id(self):
        api = FakeAdminAPI()
        first = self._run(api, "alice.zhang@tuk.swim")
        second = self._run(api, "alice.zhang@tuk.swim")
        self.assertEqual(first, second)
        # One real create, one refused create resolved by lookup.
        self.assertEqual(len(api.created), 2)
        self.assertEqual(api.list_calls, 1)

    def test_lookup_is_case_insensitive(self):
        api = FakeAdminAPI()
        self._run(api, "alice.zhang@tuk.swim")
        got = self._run(api, "Alice.Zhang@TUK.swim")
        self.assertEqual(got, "uuid-for-alice.zhang@tuk.swim")

    def test_unrecoverable_error_raises(self):
        class Broken(FakeAdminAPI):
            def post(self, *a, **kw):
                return FakeResponse(500, {"error_code": "unexpected_failure",
                                          "msg": "boom"}, text="500 boom")

        with patch.object(U, "requests", Broken()):
            with self.assertRaises(RuntimeError):
                U.get_or_create_auth_user(SUPABASE_CONFIG, "alice.zhang@tuk.swim")

    def test_password_is_never_logged_or_returned(self):
        api = FakeAdminAPI()
        out = self._run(api, "alice.zhang@tuk.swim")
        self.assertNotIn(U.DEFAULT_PASSWORD, str(out))
        self.assertEqual(out, "uuid-for-alice.zhang@tuk.swim")


class SeededEmailTests(unittest.TestCase):
    """The address a seeded athlete receives decides whether it can ever register."""

    def test_same_name_different_club_gets_different_addresses(self):
        self.assertNotEqual(U._make_email("Alice Zhang", "TUK"),
                            U._make_email("Alice Zhang", "PDX"))

    def test_same_name_same_club_collides(self):
        # Recorded deliberately: this is the known limitation that makes a
        # seeded address unsuitable as a real login (see the plan doc). If this
        # assertion ever starts failing, _make_email gained a disambiguator and
        # this note should be removed with it.
        self.assertEqual(U._make_email("Alice Zhang", "TUK"),
                         U._make_email("Alice Zhang", "TUK"))


class IngestFlagTests(unittest.TestCase):
    """Both ingest scripts expose --no-provision and reject nothing else."""

    def _usage_mentions(self, module):
        buf = []
        with patch.object(module, "print", lambda *a, **k: buf.append(" ".join(str(x) for x in a))):
            rc = module.main(["ingest", "--definitely-not-a-flag"])
        return rc, "\n".join(buf)

    def test_figures_rejects_unknown_flag_and_documents_no_provision(self):
        rc, out = self._usage_mentions(ingest_figures)
        self.assertEqual(rc, 2)
        self.assertIn("--no-provision", out)

    def test_routines_rejects_unknown_flag_and_documents_no_provision(self):
        rc, out = self._usage_mentions(ingest_routines)
        self.assertEqual(rc, 2)
        self.assertIn("--no-provision", out)

    def test_figures_with_no_arguments_returns_usage_error(self):
        with patch.object(ingest_figures, "print", lambda *a, **k: None):
            self.assertEqual(ingest_figures.main(["ingest"]), 1)

    def test_no_provision_suppresses_person_sync(self):
        """With --no-provision, synchronized_meet must never be called."""
        calls = []
        parsed = {"athletes": []}

        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "fake.pdf"
            pdf.write_bytes(b"%PDF-1.4 not really a pdf")
            with patch.object(ingest_figures, "extract_text_from_pdf", return_value=""), \
                 patch.object(ingest_figures, "parse_figure_pdf_text", return_value=parsed), \
                 patch.object(ingest_figures, "insert_rows_to_supabase",
                              return_value="wrote 0"), \
                 patch.object(ingest_figures, "describe", return_value=""), \
                 patch.object(ingest_figures, "synchronized_meet",
                              side_effect=lambda *a, **k: calls.append(a)), \
                 patch.object(ingest_figures, "print", lambda *a, **k: None):
                rc = ingest_figures.main(["ingest", str(pdf), "--no-provision"])

        self.assertEqual(rc, 0)
        self.assertEqual(calls, [], "--no-provision did not suppress provisioning")

    def test_provisioning_runs_by_default(self):
        calls = []
        parsed = {"athletes": []}

        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "fake.pdf"
            pdf.write_bytes(b"%PDF-1.4 not really a pdf")
            with patch.object(ingest_routines, "extract_text_from_pdf", return_value=""), \
                 patch.object(ingest_routines, "parse_routine_pdf_text", return_value=parsed), \
                 patch.object(ingest_routines, "insert_rows_to_supabase",
                              return_value="wrote 0"), \
                 patch.object(ingest_routines, "describe", return_value=""), \
                 patch.object(ingest_routines, "synchronized_meet",
                              side_effect=lambda *a, **k: calls.append(a)), \
                 patch.object(ingest_routines, "print", lambda *a, **k: None):
                rc = ingest_routines.main(["ingest", str(pdf)])

        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1, "provisioning is on by default")


class SeededStatusTests(unittest.TestCase):
    """A seeded profile must land in a state that cannot log in.

    Asserted against the SQL text rather than a database, because the point is
    that the literal in the INSERT is 'INVITED'. A regression to 'ACTIVE' would
    make every seeded account immediately loggable-in with a password that is
    published in this repository.
    """

    def test_profile_insert_uses_invited_not_active(self):
        src = (ROOT / "scripts" / "user_mgmt_sync.py").read_text(encoding="utf-8")
        marker = "INSERT INTO public.user_profile"
        idx = src.index(marker)
        window = src[idx:idx + 900]
        self.assertIn("'INVITED'", window)
        self.assertNotIn("'ACTIVE'", window,
                         "seeding an ACTIVE profile bypasses the approval gate")


if __name__ == "__main__":
    unittest.main()