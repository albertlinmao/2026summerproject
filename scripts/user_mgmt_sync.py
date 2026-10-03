#!/usr/bin/env python3
"""Provision user-management records while ingesting meet results.

Ingestion enhancement: when a score PDF introduces a club that the
user-management service does not know yet, it is provisioned as a tenant
with the default roles/permissions (tenant admin, platform-engineer, regular
tenant user). A tenant-scoped API key is minted at the same time so the
dashboard app can later identify the tenant from the key. Every athlete found
in the PDF is created as a tenant user (with a default password), gets a
membership, and --- for routine results --- is added to the team whose
assignment appears in the PDF.

All writes are idempotent so the ingest scripts can be re-run safely.

================================================================================
IDENTITY MODEL (see specs/001-analytics-dashboard/identity-contract.md)
================================================================================
A person is a human, a club is the tenant, and membership is the edge between
them. A person has no club_id. A login is optional. Roles are per-club.

Dashboard side, this script now writes:
  as_person             the human (given_name / family_name / birth_date)
  as_person_identity    optional 1:1 link to the auth subject (`sub`)
  as_club_membership    the tenant edge: role 'swimmer', status 'active'
  as_team_member        roster edge, keyed on person_id (was user_id)

`as_athlete` is now a VIEW over as_person + as_club_membership and is never
written to. The user-service `user_profile` row keeps the encrypted PII; its id
is the auth subject id, which becomes `as_person_identity.subject_id` -- a
distinct identifier from the dashboard's `person_id` and never conflated with it.

--------------------------------------------------------------------------------
BLOCKING DEPENDENCY in the identity service (api/user-management, separate repo)
--------------------------------------------------------------------------------
`public.membership` there is declared UNIQUE (tenant_id, user_id). That constraint
makes multi-club membership impossible: a person can hold at most ONE role in a
tenant, so being a swimmer in club A and a coach in club B cannot be expressed.

It must become UNIQUE (tenant_id, user_id, role_id), or the membership table must
be replaced by a membership-per-role structure, before the model in
identity-contract.md works. Recorded as a blocking dependency in
identity-contract.md section 4; out of scope for this repository.

Until that lands, the inserts below use a bare ON CONFLICT DO NOTHING (no
conflict target) so they remain correct under either constraint -- naming
`ON CONFLICT (tenant_id, user_id, role_id)` today would raise "no unique or
exclusion constraint matching" against the current (tenant_id, user_id) index.
================================================================================
"""
import os
import re
import json
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from dotenv import load_dotenv

try:
    import psycopg2
except Exception:
    print("Missing dependency psycopg2. Install via: pip install -r requirements.txt")
    raise

try:
    import bcrypt
except Exception:
    print("Missing dependency bcrypt. Install via: pip install -r requirements.txt")
    raise

ROOT_DIR = Path(__file__).resolve().parents[1]

# Password handed to an account this script seeds. Overridable from the
# environment because a credential committed to a repository is a published
# credential: INGEST_DEFAULT_PASSWORD wins, and the literal below is the
# documented development fallback only.
#
# The seeded password is deliberately paired with status 'INVITED' (see
# get_or_create_user). It is a placeholder that nobody should be able to log in
# with, not a working credential: an account stays unable to authenticate until
# an admin activates it and the real owner chooses their own password.
DEFAULT_PASSWORD = os.getenv("INGEST_DEFAULT_PASSWORD") or "pa$$word$d3Faul%"

# GoTrue clamps per_page server-side; the value only decides how few round trips
# a full scan of auth.users costs.
AUTH_LIST_PAGE_SIZE = 1000

# Issued to callers as "<key_prefix>.<secret>"; only a bcrypt hash is stored.
API_KEY_PREFIX = "ssk_live_"

# Permission names per api/user-management/supabase/init/seed_permissions.sql
DEFAULT_PERMISSIONS = [
    ("GLOBAL", "ADMIN"),
    ("PLATFORM", "ENGINEER"),
    ("ORG", "ADMIN"),
    ("ORG", "USER"),
    ("ORG", "GUEST"),
]

ORG_MODEL_DDL = """
-- Dashboard org-model mirror tables (idempotent).
-- The identity core (as_person / as_person_identity / as_club_membership) is NOT
-- created here: it is owned by
-- backend/src/supabase/migrations/20260826_person_identity_migration.sql and must
-- be applied before this script runs.
CREATE TABLE IF NOT EXISTS public.as_team (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id uuid NOT NULL REFERENCES public.tenant(id) ON DELETE CASCADE,
    name text NOT NULL,
    lead_coach_person_id uuid REFERENCES public.as_person(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (club_id, name)
);

CREATE TABLE IF NOT EXISTS public.as_team_member (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id uuid NOT NULL REFERENCES public.as_team(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES public.as_person(id) ON DELETE CASCADE,
    team_role text NOT NULL DEFAULT 'ATHLETE'
        CHECK (team_role IN ('COACH', 'CAPTAIN', 'ATHLETE')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (team_id, person_id)
);

-- Tenant API keys (machine access). Mirrors api/user-management/supabase/init/tenant_api_keys.sql
-- so provisioning works even before that migration has been run.
CREATE TABLE IF NOT EXISTS public.tenant_api_keys (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES public.tenant(id) ON DELETE CASCADE,
    key_prefix   varchar(16) NOT NULL UNIQUE,
    secret_hash  varchar(255) NOT NULL,
    name         varchar(100),
    status       varchar(20) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'revoked', 'expired')),
    expires_at   timestamptz,
    last_used_at timestamptz,
    created_at   timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tenant_api_keys_prefix
    ON public.tenant_api_keys (key_prefix)
    WHERE status = 'active';
"""


def get_db_config() -> Dict[str, str]:
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / "supabase" / ".env", override=False)

    host = (os.getenv("POSTGRES_HOST") or "localhost").strip()
    if host in ("db", "host.docker.internal", "localhost"):
        host = "localhost"

    return {
        "host": host,
        "port": int(os.getenv("POSTGRES_PORT") or "5432"),
        "user": os.getenv("POSTGRES_USER") or "postgres",
        "dbname": os.getenv("POSTGRES_DB") or "postgres",
        "password": (os.getenv("POSTGRES_PASSWORD") or "").strip(),
    }


def get_supabase_config() -> Dict[str, str]:
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / "supabase" / ".env", override=False)

    raw_url = (os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
    if raw_url.startswith("postgres://") or raw_url.startswith("postgresql://"):
        raw_url = "http://localhost:8000"
    if raw_url.startswith("http://host.docker.internal"):
        raw_url = raw_url.replace("http://host.docker.internal", "http://localhost")
    if not raw_url:
        raw_url = "http://localhost:8000"

    key = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SERVICE_ROLE_KEY")
        or os.getenv("ANON_KEY")
        or ""
    )
    return {"url": raw_url, "key": key}


def _connect(db_config: Dict[str, str]):
    return psycopg2.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        dbname=db_config["dbname"],
        password=db_config["password"],
    )


def ensure_org_schema(db_config: Dict[str, str]) -> None:
    """Create the org-model tables the ingestion needs (idempotent)."""
    if not db_config["password"]:
        raise RuntimeError("POSTGRES_PASSWORD not provided in environment")
    with _connect(db_config) as conn:
        with conn.cursor() as cur:
            cur.execute(ORG_MODEL_DDL)
        conn.commit()


def _ensure_permissions(cur) -> Dict[Tuple[str, str], str]:
    """Seed default (resource, action) permissions; return {(res,act): id}."""
    for resource, action in DEFAULT_PERMISSIONS:
        cur.execute(
            """
            INSERT INTO public.permission (resource, action)
            VALUES (%s, %s)
            ON CONFLICT (resource, action) DO NOTHING
            """,
            (resource, action),
        )
    cur.execute("SELECT id, resource, action FROM public.permission")
    return {(res, act): perm_id for perm_id, res, act in cur.fetchall()}


def _get_or_create_role(cur, tenant_id, role_name) -> str:
    """Lookup-first role creation (system roles have tenant_id NULL)."""
    cur.execute(
        "SELECT id FROM public.role WHERE tenant_id IS NOT DISTINCT FROM %s AND name=%s",
        (tenant_id, role_name),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO public.role (tenant_id, name) VALUES (%s, %s) RETURNING id",
        (tenant_id, role_name),
    )
    return cur.fetchone()[0]


def _ensure_default_roles(cur, tenant_id: str, permissions: Dict[Tuple[str, str], str]) -> Dict[str, str]:
    """Create the default roles and grant their default permission(s)."""
    role_ids: Dict[str, str] = {}

    # System-level platform-engineer role (no tenant) sharing with all tenants.
    role_ids["PLATFORM_ENGINEER"] = _get_or_create_role(cur, None, "PLATFORM_ENGINEER")

    # Tenant-scoped roles.
    role_ids["ORG_ADMIN"] = _get_or_create_role(cur, tenant_id, "ORG_ADMIN")
    role_ids["ORG_USER"] = _get_or_create_role(cur, tenant_id, "ORG_USER")

    _grant(cur, role_ids["PLATFORM_ENGINEER"], [permissions[("PLATFORM", "ENGINEER")], permissions[("GLOBAL", "ADMIN")]])
    _grant(cur, role_ids["ORG_ADMIN"], [permissions[p] for p in [("ORG", "ADMIN"), ("GLOBAL", "ADMIN")]])
    _grant(cur, role_ids["ORG_USER"], [permissions[p] for p in [("ORG", "USER"), ("ORG", "GUEST")]])

    return role_ids


def _grant(cur, role_id: str, permission_ids: List[str]) -> None:
    for permission_id in permission_ids:
        cur.execute(
            """
            INSERT INTO public.role_permission (role_id, permission_id)
            VALUES (%s, %s)
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """,
            (role_id, permission_id),
        )


def _slugify(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z]+", ".", value.strip().lower()).strip(".")
    return value or "unknown"


def _make_email(name: str, club_code: str) -> str:
    return f"{_slugify(name)}@{_slugify(club_code)}.swim"


def _split_name(name: str) -> Tuple[str, str]:
    """Split a printed result name into (given_name, family_name).

    The result sheets print "FAMILY Given" (e.g. "HE Sunny", "MOLCHANOVA Kate"),
    so the first token is the family name. Middle names are not distinguishable
    from the printed form and are kept in given_name.
    """
    parts = name.strip().split()
    if not parts:
        return "Unknown", "Unknown"
    if len(parts) == 1:
        return "Unknown", parts[0]
    return " ".join(parts[1:]), parts[0]


def _ensure_person(cur, subject_id: str, name: str) -> str:
    """Return the as_person.id for an auth subject, creating it if needed.

    The person and the auth subject are different identifiers: `subject_id` is
    the only link to the identity provider and is matched against the verified
    `sub` claim (identity-contract.md section 2). A person may exist with no
    identity at all, but a provisioned user always gets exactly one.
    """
    cur.execute(
        "SELECT person_id FROM public.as_person_identity WHERE subject_id = %s",
        (subject_id,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    given_name, family_name = _split_name(name)
    person_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO public.as_person (id, given_name, family_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (person_id, given_name, family_name),
    )
    cur.execute(
        """
        INSERT INTO public.as_person_identity (person_id, subject_id)
        VALUES (%s, %s)
        ON CONFLICT (subject_id) DO NOTHING
        """,
        (person_id, subject_id),
    )
    return person_id


def _ensure_swimmer_membership(cur, person_id: str, club_id: str) -> None:
    """Record the person <-> club edge. This is the authorization source of truth.

    Partial unique index uq_as_club_membership_active covers
    (person_id, club_id, role) where status in ('invited','active').
    """
    cur.execute(
        """
        INSERT INTO public.as_club_membership (person_id, club_id, role, status)
        VALUES (%s, %s, 'swimmer', 'active')
        ON CONFLICT DO NOTHING
        """,
        (person_id, club_id),
    )


def create_tenant_api_key(conn, tenant_id: str, name: str = "Ingestion provisioning key") -> str:
    """Mint a tenant-scoped API key; return the full "<prefix>.<secret>" value.

    Only a bcrypt hash of the full key is stored; the plaintext is returned
    exactly once so the caller can hand it to the club.
    """
    with conn.cursor() as cur:
        while True:  # retry on key_prefix collision (unique constraint)
            prefix = API_KEY_PREFIX + secrets.token_hex(3)  # 15 chars, fits varchar(16)
            full_key = f"{prefix}.{secrets.token_urlsafe(32)}"
            secret_hash = bcrypt.hashpw(full_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            try:
                cur.execute(
                    """
                    INSERT INTO public.tenant_api_keys (tenant_id, key_prefix, secret_hash, name, status)
                    VALUES (%s, %s, %s, %s, 'active')
                    """,
                    (tenant_id, prefix, secret_hash, name),
                )
                conn.commit()
                return full_key
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                continue


def resolve_tenant_api_key(conn, api_key: str):
    """Resolve a "<prefix>.<secret>" key to its tenant_id or None.

    Looks up the public prefix, verifies the bcrypt hash of the full key,
    and skips non-active / expired keys. This is what the dashboard app will
    use to identify the calling club/tenant before checking the logged-in user.
    """
    if not api_key or "." not in api_key:
        return None
    prefix, secret = api_key.split(".", 1)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tenant_id, secret_hash, status
            FROM public.tenant_api_keys
            WHERE key_prefix = %s AND status = 'active'
              AND (expires_at IS NULL OR expires_at > now())
            """,
            (prefix,),
        )
        row = cur.fetchone()
        if not row:
            return None
        tenant_id, secret_hash, _status = row
        if not bcrypt.checkpw(api_key.encode("utf-8"), secret_hash.encode("utf-8")):
            return None
        cur.execute(
            "UPDATE public.tenant_api_keys SET last_used_at = now() WHERE key_prefix = %s",
            (prefix,),
        )
        conn.commit()
        return tenant_id


def _ensure_club_mirror(cur, tenant_id: str, club_code: str, club_name: str) -> None:
    """Mirror the tenant into the dashboard's as_club (a club IS a tenant).

    `as_club.id` is the tenant id, so this row is what makes
    `as_club_membership.club_id` satisfiable. It is reconciled on every call and
    not only when the tenant is created: the tenant and its mirror are two
    separate rows, a tenant that predates the identity change carries no mirror,
    and the membership insert that follows fails its foreign key without one.

    `as_club.code` is NOT NULL and UNIQUE, and the application resolves a club by
    that column (backend/src/api/auth.py::_resolve_club_id and results_browser),
    so a code is always written -- the one the result sheet prints, and a slug of
    the name for a sheet that carries none. A code already held by a *different*
    tenant is disambiguated with a prefix of the tenant id rather than allowed to
    raise: the prefix is unique because the id is, which also makes the value
    deterministic, so a tenant keeps the same code for the life of the database.
    """
    code = (club_code or "").strip() or _slugify(club_name)
    cur.execute("SELECT id FROM public.as_club WHERE code = %s", (code,))
    row = cur.fetchone()
    if row is not None and str(row[0]) != tenant_id:
        code = f"{code}-{tenant_id[:8]}"
    cur.execute(
        "INSERT INTO public.as_club (id, name, code) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (tenant_id, club_name, code),
    )


def get_or_create_tenant(conn, club_code: str, club_name: str) -> Tuple[str, bool]:
    """Return (tenant_id, created). Reuses tenant/as_club by exact name."""
    if not club_name:
        raise ValueError(f"Missing club name for team code {club_code!r}")

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.tenant WHERE name=%s", (club_name,))
        row = cur.fetchone()
        if row:
            tenant_id = row[0]
            created = False
        else:
            cur.execute(
                """
                INSERT INTO public.tenant (name, status)
                VALUES (%s, 'ACTIVE')
                RETURNING id
                """,
                (club_name,),
            )
            tenant_id = cur.fetchone()[0]
            created = True

            permissions = _ensure_permissions(cur)
            _ensure_default_roles(cur, tenant_id, permissions)

        _ensure_club_mirror(cur, tenant_id, club_code, club_name)
    conn.commit()

    if created:
        api_key = create_tenant_api_key(conn, tenant_id, f"{club_name} dashboard key")
        print(
            f"[user-mgmt] API key for {club_name} (tenant {tenant_id}): "
            f"{api_key}\n"
            f"[user-mgmt]   store it now --- only the bcrypt hash is saved."
        )
    return tenant_id, created


def _auth_headers(supabase_config: Dict[str, str]) -> Dict[str, str]:
    return {
        "apikey": supabase_config["key"],
        "Authorization": f"Bearer {supabase_config['key']}",
        "Content-Type": "application/json",
    }


def _auth_error(response) -> Dict[str, str]:
    """Pull error_code/msg out of a GoTrue error body, tolerating non-JSON."""
    try:
        body = response.json()
    except ValueError:
        return {"error_code": "", "msg": response.text}
    if not isinstance(body, dict):
        return {"error_code": "", "msg": response.text}
    return {"error_code": str(body.get("error_code") or ""), "msg": str(body.get("msg") or "")}


def find_auth_user_by_email(supabase_config: Dict[str, str], email: str) -> str | None:
    """Return the id of the auth user already registered for `email`, or None.

    The admin list endpoint returns the address in plaintext, so it can be
    matched directly. GoTrue narrows the lookup server-side when it understands
    `filter`; a build that ignores the parameter is handled by paging the list
    instead. Addresses are compared case-insensitively because GoTrue folds them
    to lower case on create, while a name-derived address may not be folded.
    """
    base = f"{supabase_config['url'].rstrip('/')}/auth/v1/admin/users"
    headers = _auth_headers(supabase_config)
    target = email.strip().lower()

    def scan(params: Dict[str, str]) -> str | None:
        page = 1
        while True:
            query: Dict[str, Any] = {"page": page, "per_page": AUTH_LIST_PAGE_SIZE}
            query.update(params)
            response = requests.get(base, headers=headers, params=query, timeout=20)
            if response.status_code != 200:
                return None
            body = response.json()
            for user in body.get("users", []):
                if (user.get("email") or "").strip().lower() == target:
                    return user["id"]
            last_page = body.get("last_page")
            if not last_page or page >= last_page:
                return None
            page += 1

    return scan({"filter": f"email.eq.{email}"}) or scan({})


def get_or_create_auth_user(supabase_config: Dict[str, str], email: str) -> str:
    """Create a Supabase Auth user with the default password; return user id.

    Idempotent. A re-run meets the address a previous run already registered,
    and the admin API answers that with 422 email_exists instead of returning
    the existing row -- so the id is resolved from the address and returned, and
    the caller carries on instead of aborting the whole ingest. Only an address
    the admin API will not create at all still raises.
    """
    endpoint = f"{supabase_config['url'].rstrip('/')}/auth/v1/admin/users"
    payload: Dict[str, Any] = {
        "email": email,
        "password": DEFAULT_PASSWORD,
        "email_confirm": True,
    }
    response = requests.post(endpoint, headers=_auth_headers(supabase_config), json=payload, timeout=20)
    if response.status_code in (200, 201):
        return response.json()["id"]

    error = _auth_error(response)
    if error["error_code"] == "email_exists" or "already been registered" in error["msg"]:
        existing = find_auth_user_by_email(supabase_config, email)
        if existing:
            return existing

    raise RuntimeError(f"Auth admin create user failed for {email}: {response.status_code} {response.text}")


def get_or_create_user(conn, supabase_config: Dict[str, str], tenant_id: str, role_ids: Dict[str, str],
                       name: str, email: str) -> str:
    """Return a person_id for the swimmer, creating auth user + profile + membership.

    The auth subject id (`sub`) and the dashboard `person_id` are distinct
    identifiers; the person is reached from the subject through
    as_person_identity. The person is minted once and reused when the same
    subject shows up in another club, so one login can hold memberships in
    several clubs.
    """
    with conn.cursor() as cur:
        # Reuse existing profile identified by the (encrypted) email.
        cur.execute(
            """
            WITH secret AS (
                SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'pii_encryption_key' LIMIT 1
            )
            SELECT u.id FROM public.user_profile u, secret
            WHERE pgp_sym_decrypt(u.email::bytea, secret.decrypted_secret) = %s
            LIMIT 1
            """,
            (email,),
        )
        row = cur.fetchone()
        if row:
            subject_id = row[0]
        else:
            subject_id = get_or_create_auth_user(supabase_config, email)
            # The profile is keyed by the auth subject id, so an existing row is
            # recognized by id and not by the address the lookup above decrypts:
            # an address that no longer decrypts to this value (a scrubbed or
            # rewritten email) would otherwise re-insert and collide on the
            # primary key. Presence is the only question here -- the row is
            # deliberately not rewritten.
            cur.execute("SELECT 1 FROM public.user_profile WHERE id = %s", (subject_id,))
            if cur.fetchone() is None:
                first_name, last_name = _split_name(name)
                # 'INVITED', not 'ACTIVE'. This script seeds an account for every
                # name printed on a result sheet, using a shared default password,
                # so writing 'ACTIVE' here would make all of them immediately
                # loggable-in with a password that is published in this file.
                # 'INVITED' is the state the approval gate expects
                # (design.md 4.1 / 5.1: login refuses anything not yet enabled),
                # and it is the column default, so the value is written
                # explicitly only to stop it being "fixed" back to 'ACTIVE'.
                cur.execute(
                    """
                    WITH secret AS (
                        SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'pii_encryption_key' LIMIT 1
                    )
                    INSERT INTO public.user_profile (id, email, first_name, last_name, status, created_at, updated_at)
                    SELECT %s,
                           pgp_sym_encrypt(%s, secret.decrypted_secret),
                           pgp_sym_encrypt(%s, secret.decrypted_secret),
                           pgp_sym_encrypt(%s, secret.decrypted_secret),
                           'INVITED', NOW(), NOW()
                    FROM secret
                    """,
                    (subject_id, email, first_name, last_name),
                )

        person_id = _ensure_person(cur, subject_id, name)
        _ensure_swimmer_membership(cur, person_id, tenant_id)

        # Membership (org user role). See the header block: the conflict target is
        # deliberately omitted because the identity service still declares
        # UNIQUE (tenant_id, user_id) and must become (tenant_id, user_id, role_id).
        cur.execute(
            """
            INSERT INTO public.membership (tenant_id, user_id, role_id)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (tenant_id, subject_id, role_ids["ORG_USER"]),
        )
    conn.commit()
    return person_id


def add_athlete_to_team(conn, tenant_id: str, team_name: str, person_id: str, team_code: str = None) -> None:
    """Ensure the team row exists and link the swimmer (routine assignment)."""
    team_name = team_name or team_code or "Unnamed Team"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.as_team (club_id, name)
            VALUES (%s, %s)
            ON CONFLICT (club_id, name) DO NOTHING
            RETURNING id
            """,
            (tenant_id, team_name),
        )
        row = cur.fetchone()
        if row:
            team_id = row[0]
        else:
            cur.execute(
                "SELECT id FROM public.as_team WHERE club_id=%s AND name=%s",
                (tenant_id, team_name),
            )
            team_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO public.as_team_member (team_id, person_id, team_role)
            VALUES (%s, %s, 'ATHLETE')
            ON CONFLICT (team_id, person_id) DO NOTHING
            """,
            (team_id, person_id),
        )
    conn.commit()


def synchronized_meet(payload: Dict[str, Any], dry_run: bool = False, routine: bool = False) -> None:
    """Provision tenants/users/memberships (and team assignment for routines)."""
    db_config = get_db_config()
    supabase_config = get_supabase_config()

    if dry_run:
        clubs = {a.get("team_code") or a.get("team_name") for a in payload.get("athletes", [])}
        print(f"[user-mgmt dry-run] would provision clubs/tenants: {sorted(filter(None, clubs))}")
        return

    ensure_org_schema(db_config)

    conn = _connect(db_config)
    try:
        for team in payload.get("athletes", []):
            club_code = (team.get("team_code") or "").strip()
            club_name = (team.get("team_name") or "").strip()
            if not club_code and not club_name:
                continue

            tenant_id, created = get_or_create_tenant(conn, club_code, club_name)
            if created:
                print(f"[user-mgmt] provisioned tenant + default roles for club '{club_name}'")

            member_names = _team_member_names(team)
            if not member_names and team.get("athlete_name"):
                member_names = [team["athlete_name"]]

            with conn.cursor() as cur:
                permissions = _ensure_permissions(cur)
                role_ids = _ensure_default_roles(cur, tenant_id, permissions)

            for name in member_names:
                if not name:
                    continue
                email = _make_email(name, club_code)
                person_id = get_or_create_user(conn, supabase_config, tenant_id, role_ids, name, email)
                print(f"[user-mgmt] ensured person '{name}' ({email}, person {person_id}) in club '{club_name}'")
                if routine:
                    add_athlete_to_team(conn, tenant_id, team.get("team_name"), person_id, team.get("team_code"))
    finally:
        conn.close()


def _team_member_names(team: Dict[str, Any]) -> List[str]:
    """Extract athlete names from a routine team row (team_athletes is a JSON string)."""
    raw = team.get("team_athletes")
    if not raw:
        return []
    if isinstance(raw, list):
        members = raw
    elif isinstance(raw, str):
        try:
            members = json.loads(raw)
        except Exception:
            return []
    else:
        return []
    return [m.get("name") for m in members if m.get("name")]