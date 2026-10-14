"""
test_register_profiles_unique.py — PR 5.0a (registration was down for personal accounts).

Root cause: create_user does INSERT INTO profiles … ON CONFLICT (user_id); a production
profiles table created before UNIQUE(user_id) had no matching constraint → PostgreSQL error
→ the old "unique" text match turned it into «البريد الإلكتروني مسجل مسبقاً» (409).

  1. profiles_user_unique migration adds the index to a table without it (dedupe keeps the
     oldest) and is idempotent when the constraint already exists.
  2. POST /auth/register for a personal account succeeds (profile row written).
  3. A real duplicate email → 409 with the email message.
  4. Any other DB error (the original bug: profiles without the constraint) → 500, never
     the email message.

Real PostgreSQL — needs TW_TEST_DB_URL (run_tests.sh sets it). Without it: skipped.
Run: python -m pytest tests/test_register_profiles_unique.py -q
"""
import os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_EMAIL_TAKEN = "البريد الإلكتروني مسجل مسبقاً"


@pytest.fixture(scope="module")
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    auth._db_params = dict(host=host, port=int(port), user=user, password=pw,
                           database=name.split("?")[0], ssl_context=None)
    srv._run_startup_migrations()
    yield


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "get_country_from_ip", lambda ip: "DEFAULT")  # no ip-api call
    srv._rate_store.clear()
    yield


def _drop_profiles_unique(conn):
    """Recreate the old production state: profiles with no UNIQUE on user_id."""
    conn.run("ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_user_id_key")
    conn.run("DROP INDEX IF EXISTS profiles_user_id_key")


def _has_profiles_unique(conn) -> bool:
    return bool(conn.run(
        "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "WHERE c.relname = 'profiles_user_id_key' AND i.indisunique"))


def _register(email):
    return client.post("/auth/register", json={
        "first_name": "سارة", "last_name": "خالد", "email": email,
        "password": "secret-pass-1", "user_type": "emp"})


def test_registry_marks_profiles_unique_critical():
    reg = [(n, c) for n, _, c in srv._startup_migrations()]
    assert ("profiles_user_unique", True) in reg
    assert [n for n, _ in reg].index("profiles_user_unique") > [n for n, _ in reg].index("init_db")


def test_migration_adds_missing_constraint_and_is_idempotent(db):
    with auth.db_conn() as conn:
        _drop_profiles_unique(conn)
        assert not _has_profiles_unique(conn)
        n = uuid.uuid4().hex[:10]
        uid = int(conn.run(
            "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
            "VALUES (:t, 'U', :e, 'x', 'emp') RETURNING id", t="U" + n, e=n + "@t.test")[0][0])
        first = int(conn.run("INSERT INTO profiles (user_id, headline) VALUES (:u, 'a') RETURNING id", u=uid)[0][0])
        conn.run("INSERT INTO profiles (user_id, headline) VALUES (:u, 'b')", u=uid)
    auth._migrate_profiles_user_unique()
    auth._migrate_profiles_user_unique()   # constraint now exists → no-op
    with auth.db_conn() as conn:
        assert _has_profiles_unique(conn)
        assert conn.run("SELECT id FROM profiles WHERE user_id=:u", u=uid) == [[first]]
        conn.run("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT (user_id) DO NOTHING", u=uid)


def test_register_personal_account_succeeds_then_duplicate_is_409(db):
    email = uuid.uuid4().hex[:10] + "@reg.test"
    r = _register(email)
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    with auth.db_conn() as conn:
        assert conn.run("SELECT first_name, last_name FROM profiles WHERE user_id=:u", u=uid) == [["سارة", "خالد"]]
    r2 = _register(email.upper())
    assert r2.status_code == 409
    assert r2.json()["error"] == _EMAIL_TAKEN


def test_other_db_error_is_500_not_email_taken(db):
    with auth.db_conn() as conn:
        _drop_profiles_unique(conn)
    try:
        email = uuid.uuid4().hex[:10] + "@reg.test"
        r = _register(email)
        assert r.status_code == 500
        assert _EMAIL_TAKEN not in r.text
        assert "constraint" not in r.text.lower()
        with auth.db_conn() as conn:   # the whole registration rolled back
            assert conn.run("SELECT 1 FROM users WHERE email=:e", e=email) == []
    finally:
        auth._migrate_profiles_user_unique()
