"""Shared plumbing for the ad-hoc scripts under ``scripts/tmp/``.

These scripts are throwaway diagnostics and one-off data loaders, so they are
not part of the backend package and have no shared test harness. This module
exists only to stop three things being copy-pasted into all 17 of them:

1. Repo-root / backend import path resolution. The old scripts used
   ``os.path.join(os.getcwd(), 'backend')``, which silently breaks the moment a
   script is run from anywhere other than the repo root. Resolution is now based
   on ``__file__``.
2. Postgres connection strings. Four of these scripts had the same production
   password hardcoded in the source. Credentials now come from the environment
   (see ``.env.example``); nothing here has a default that would silently
   connect somewhere.
3. The Supabase client, which previously embedded a ``service_role`` JWT in the
   source of ``load_athletes_clubs.py``.

Identity model: ``specs/001-analytics-dashboard/identity-contract.md``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# scripts/tmp/_ad_hoc_common.py -> scripts/tmp -> scripts -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

#: Printed once by the scripts that need it, so a missing variable is obvious.
_REQUIRED_HINT = (
    "Set it in your environment or in a .env file (see .env.example). "
    "Credentials are never hardcoded in these scripts."
)


class MissingConfig(RuntimeError):
    """Raised when a required environment variable is absent."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingConfig(
            f"Required environment variable {name} is not set. {_REQUIRED_HINT}"
        )
    return value


def add_backend_to_path() -> Path:
    """Put ``backend/`` on ``sys.path`` so ``import src.*`` resolves.

    Returns the backend directory. Idempotent.
    """
    path = str(BACKEND_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)
    return BACKEND_DIR


def load_dotenv_if_present() -> None:
    """Best-effort ``.env`` load.

    Uses python-dotenv when it is installed and silently does nothing when it
    is not, so these scripts still run on a bare interpreter.
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_file)


def dsn() -> str:
    """Build a Postgres DSN from ``PG*`` environment variables.

    ``DATABASE_URL`` wins if present, otherwise the standard libpq variables are
    assembled. Raises :class:`MissingConfig` if neither is usable, rather than
    defaulting to a host that might be somebody's production database.
    """
    load_dotenv_if_present()

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if url:
        return url

    host = os.environ.get("PGHOST")
    if not host:
        raise MissingConfig(
            "Neither DATABASE_URL nor PGHOST is set. " + _REQUIRED_HINT
        )

    parts = [f"host={host}"]
    for var, kw in (
        ("PGPORT", "port"),
        ("PGDATABASE", "dbname"),
        ("PGUSER", "user"),
        ("PGPASSWORD", "password"),
    ):
        value = os.environ.get(var)
        if value:
            parts.append(f"{kw}={value}")
    return " ".join(parts)


def connect():
    """Open a psycopg2 connection from the environment.

    ``psycopg2`` is imported lazily so the scripts that do not need it (the
    offline parsing/regex checks) still run without the driver installed.
    """
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise MissingConfig(
            "psycopg2 is not installed. Run: pip install psycopg2-binary"
        ) from exc
    return psycopg2.connect(dsn())


def supabase_client():
    """Create a Supabase client from the environment.

    Prefers the service-role key because these are admin/one-off loaders writing
    to tables that RLS protects, and a read-only anon key cannot insert
    ``as_person`` / ``as_club_membership`` rows. The key is never written to
    disk here.
    """
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise MissingConfig(
            "supabase is not installed. Run: pip install supabase"
        ) from exc

    load_dotenv_if_present()
    url = _require("SUPABASE_URL")
    # Same fallback order as src/core/database.py: service role first, then the
    # legacy/alternate names. SUPABASE_KEY is what the repo's own .env carries.
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not key:
        raise MissingConfig(
            "Required environment variable SUPABASE_SERVICE_ROLE_KEY is not set. "
            + _REQUIRED_HINT
        )
    return create_client(url, key)


def print_rows(rows, limit: int | None = None) -> None:
    """Print a sequence of rows, optionally truncated."""
    rows = list(rows or [])
    shown = rows if limit is None else rows[:limit]
    for row in shown:
        print(f"  {row}")
    if limit is not None and len(rows) > limit:
        print(f"  ... {len(rows) - limit} more")
