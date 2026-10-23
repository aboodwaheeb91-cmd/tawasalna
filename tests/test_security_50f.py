"""Task 5.0f — security fixes from the external audit (SYSTEMS_INDEX §2a / §23 / §54k / §54l).

1. AUD-P1-12  _migrate_rls_lockdown: RLS on every public table + nothing for anon / authenticated
              (tables, sequences, default privileges) — and the owning app role still reads / writes.
2. AUD-P1-08  a JWT of a deleted account → 401; a DB outage does not log anyone out.
3. AUD-P1-07  a company turned personal account → 403 on every company action
              (current users.user_type, not the JWT claim) — one helper _require_org_account.
4. AUD-P1-06  a token without sv → 401 from server._NO_SV_REJECT_FROM.
5. AUD-P2-08  _migrate_verified_source runs once — a withdrawn badge stays withdrawn after a restart.

Real PostgreSQL (superuser — creates the anon / authenticated roles + one non-superuser owner role):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_security_50f.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-security-50f-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-50f-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pg8000.native
import pytest
from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)
OWNER_ROLE, OWNER_PW = "tw50f_app_owner", "tw50f-owner-pass"


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def env():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    for t in ("blocks", "app_migrations", "kyc_submissions", "profiles", "users"):
        c.run(f"DROP TABLE IF EXISTS {t} CASCADE")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', password_hash TEXT, is_verified BOOLEAN DEFAULT FALSE, "
          "created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("CREATE TABLE profiles (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, "
          "is_verified BOOLEAN DEFAULT FALSE)")
    c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER, step TEXT, status TEXT)")
    auth.release_conn(c)
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    auth.bs.migrate_blocks_suspension()     # task 5.4 — users.suspended_* + blocks (read by the session check)
    server._pwd_changed_cache.clear()
    yield


def _user(email, utype):
    return int(_sql("INSERT INTO users (tw_id, email, full_name, user_type) VALUES ('X', :e, 'ن', :t) "
                    "RETURNING id", e=email, t=utype)[0][0])


def _token(uid, utype, **extra):
    claims = {"user_id": uid, "user_type": utype, "tw_id": "X", "sv": 0}
    claims.update(extra)
    return server._jwt_encode(claims)


def _h(tok):
    return {"Authorization": "Bearer " + tok}


# ── 1. RLS lockdown ──────────────────────────────────────────────────────────

def _ensure_role(name, login=False):
    if not _sql("SELECT 1 FROM pg_roles WHERE rolname = :n", n=name):
        _sql(f"CREATE ROLE {name} " + (f"LOGIN PASSWORD '{OWNER_PW}'" if login else "NOLOGIN"))


def test_rls_lockdown_every_table_closed_to_api_roles_app_still_works():
    _ensure_role("anon")
    _ensure_role("authenticated")
    _ensure_role(OWNER_ROLE, login=True)
    _sql(f"GRANT CREATE, USAGE ON SCHEMA public TO {OWNER_ROLE}")
    # a table owned by a NON-superuser role (like the app's role on Supabase) + an old grant to anon
    _sql("DROP TABLE IF EXISTS rls_probe")
    _sql("CREATE TABLE rls_probe (id SERIAL PRIMARY KEY, v TEXT)")
    _sql(f"ALTER TABLE rls_probe OWNER TO {OWNER_ROLE}")
    _sql("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated")
    _sql("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated")

    auth._migrate_rls_lockdown()
    auth._migrate_rls_lockdown()   # idempotent

    tables = _sql("SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n "
                  "ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p')")
    assert tables and all(rls for _, rls in tables), [t for t, rls in tables if not rls]
    for role in ("anon", "authenticated"):
        granted = _sql("SELECT table_name FROM information_schema.role_table_grants "
                       "WHERE table_schema = 'public' AND grantee = :r", r=role)
        assert granted == [], (role, granted)
        seqs = _sql("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'S' AND EXISTS (SELECT 1 FROM "
                    "aclexplode(c.relacl) a JOIN pg_roles g ON g.oid = a.grantee WHERE g.rolname = :r)",
                    r=role)
        assert seqs == [], (role, seqs)

    # default privileges: a table the app creates later is closed too
    _sql("CREATE TABLE rls_later (id SERIAL PRIMARY KEY)")
    assert not _sql("SELECT has_table_privilege('anon', 'public.rls_later', 'SELECT')")[0][0]

    # the owning (non-superuser) app role still reads and writes a table with RLS and no policy
    auth._parse_db_url()
    owner = pg8000.native.Connection(**dict(auth._db_params, user=OWNER_ROLE, password=OWNER_PW))
    try:
        assert not owner.run("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user")[0][0]
        owner.run("INSERT INTO rls_probe (v) VALUES ('a'), ('b')")
        owner.run("UPDATE rls_probe SET v = 'c' WHERE v = 'b'")
        assert sorted(r[0] for r in owner.run("SELECT v FROM rls_probe")) == ["a", "c"]
    finally:
        owner.close()
    # anon (the Supabase API role) is refused
    with pytest.raises(Exception):
        with auth.db_conn() as c:
            try:
                c.run("SET ROLE anon")
                c.run("SELECT * FROM rls_probe")
            finally:
                c.run("RESET ROLE")
    _sql("DROP TABLE rls_probe")
    _sql("DROP TABLE rls_later")


def test_rls_lockdown_is_critical_and_last():
    migrations = server._startup_migrations()
    name, fn, critical = migrations[-1]
    assert fn is auth._migrate_rls_lockdown and critical is True


# ── 2. deleted account ───────────────────────────────────────────────────────

def test_token_of_deleted_account_is_rejected_db_outage_is_not(monkeypatch):
    uid = _user("gone50f@example.com", "emp")
    tok = _token(uid, "emp")
    assert client.post("/auth/verify-token", headers=_h(tok)).status_code == 200
    _sql("DELETE FROM users WHERE id = :u", u=uid)
    server._pwd_changed_cache.clear()          # any worker after the cache TTL
    assert client.post("/auth/verify-token", headers=_h(tok)).status_code == 401

    uid2 = _user("live50f@example.com", "emp")
    tok2 = _token(uid2, "emp")
    server._pwd_changed_cache.clear()

    def down(_uid):
        raise RuntimeError("db down")
    monkeypatch.setattr(auth, "get_session_state", down)
    assert client.post("/auth/verify-token", headers=_h(tok2)).status_code == 200


# ── 3. company actions read the CURRENT account type ─────────────────────────

COMPANY_ACTIONS = [
    ("get",    "/jobs/1/applicants", None),
    ("put",    "/jobs/applications/1/status", {"status": "viewed"}),
    ("post",   "/jobs/applications/1/promote", None),
    ("post",   "/api/appointments", {"application_id": 1}),
    ("get",    "/api/schedule/jobs", None),
    ("get",    "/api/schedule/people?q=a", None),
    ("post",   "/api/appointments/1/send", {"scheduled_at": "2030-01-01T10:00:00Z"}),
    ("post",   "/api/appointments/1/reschedule", {"new_scheduled_at": "2030-01-01T10:00:00Z"}),
    ("post",   "/api/appointments/1/complete", None),
    ("post",   "/api/appointments/1/close", None),
    ("get",    "/company/saved-candidates", None),
    ("post",   "/company/saved-candidates/2", None),
    ("get",    "/company/candidate-suggestions", None),
    ("post",   "/company/posts", {"body": "x"}),
    ("patch",  "/company/posts/1", {"body": "x"}),
    ("delete", "/company/posts/1", None),
]


def test_company_turned_personal_account_gets_403_everywhere():
    uid = _user("co50f@example.com", "co")
    tok = _token(uid, "co")                   # JWT still says co, sv still matches
    assert server._require_org_account({"user_id": uid}) == uid
    _sql("UPDATE users SET user_type = 'emp' WHERE id = :u", u=uid)
    for method, path, body in COMPANY_ACTIONS:
        kw = {"headers": _h(tok)}
        if body is not None:
            kw["json"] = body
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 403, (method, path, r.status_code)


# ── 4. tokens without sv ─────────────────────────────────────────────────────

def test_token_without_sv_rejected_from_cutoff(monkeypatch):
    uid = _user("legacy50f@example.com", "emp")
    now = int(time.time())
    legacy = server._jwt_sign({"user_id": uid, "user_type": "emp", "iat": now, "exp": now + 3600},
                              server.JWT_SECRET)
    monkeypatch.setattr(server, "_NO_SV_REJECT_FROM", now + 3600)
    assert client.post("/auth/verify-token", headers=_h(legacy)).status_code == 200
    monkeypatch.setattr(server, "_NO_SV_REJECT_FROM", now - 1)
    assert client.post("/auth/verify-token", headers=_h(legacy)).status_code == 401
    assert client.post("/auth/verify-token", headers=_h(_token(uid, "emp"))).status_code == 200


# ── 5. badge carry-over runs once ────────────────────────────────────────────

def test_verified_source_runs_once_withdrawal_survives_restart():
    uid = _user("kyc50f@example.com", "emp")
    _sql("UPDATE users SET is_verified = TRUE WHERE id = :u", u=uid)
    _sql("INSERT INTO kyc_submissions (user_id, step, status) VALUES (:u, 'review', 'approved')", u=uid)
    auth._migrate_verified_source()                 # first boot → carried over
    assert _sql("SELECT is_verified FROM profiles WHERE user_id = :u", u=uid)[0][0] is True
    with auth.db_conn() as c:
        auth.set_user_verified(uid, False, c)       # admin withdraws the badge
    auth._migrate_verified_source()                 # restart
    auth._migrate_verified_source()                 # restart
    assert _sql("SELECT is_verified FROM profiles WHERE user_id = :u", u=uid)[0][0] is False
    assert _sql("SELECT count(*) FROM app_migrations WHERE name = 'verified_source'")[0][0] == 1

    # the first run after the mark shipped (no mark yet) never overwrites an existing row
    _sql("DELETE FROM app_migrations")
    auth._migrate_verified_source()
    assert _sql("SELECT is_verified FROM profiles WHERE user_id = :u", u=uid)[0][0] is False
