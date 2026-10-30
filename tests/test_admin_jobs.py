"""Task 5.3j — admin jobs list + one status source + hard delete (SYSTEMS_INDEX §25e · ADMIN_ENTITY_MAP §2).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it):
  - GET /admin/jobs + DELETE /admin/jobs/{id} answer 401 without an admin session
  - GET /admin/jobs returns every state (active · paused · closed · expired · archived) with counts per
    state, status filter, search (title / company), server pages and applicant_count (#8)
  - job_eff_status_sql (SQL) gives the same state as _eff_status (Python) for every row
  - /stats + the dashboard «active jobs» card count only effectively active jobs (#14 — job_active_sql)
  - deleting a job with applicants + pipeline entries → 200, everything gone, never 500 (#1) · unknown → 404
Run: python -m pytest tests/test_admin_jobs.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-admin-jobs-53j-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-53j-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import admin_insights
import admin_staff
import server as srv

client = TestClient(srv.app)
PASSWORD = "p" * 40


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    try:
        for t in ("admin_audit_log", "pipeline_stage_events", "job_pipeline_entries", "job_applications",
                  "jobs", "users", "profiles", "kyc_submissions", "messages", "email_send_log", "reports"):
            c.run(f"DROP TABLE IF EXISTS {t} CASCADE")
        c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, user_type TEXT DEFAULT 'emp', "
              "tw_id TEXT, created_at TIMESTAMP DEFAULT NOW())")
        c.run("CREATE TABLE jobs (id SERIAL PRIMARY KEY, company_id INTEGER REFERENCES users(id) ON DELETE CASCADE, "
              "title TEXT, status TEXT DEFAULT 'active', views INTEGER DEFAULT 0, duration_days SMALLINT DEFAULT 7, "
              "created_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP, closed_at TIMESTAMP, paused_at TIMESTAMP, "
              "archived_at TIMESTAMPTZ, archived_by INTEGER, admin_hidden_at TIMESTAMPTZ, admin_hidden_reason TEXT)")
        c.run("CREATE TABLE job_applications (id SERIAL PRIMARY KEY, "
              "job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, user_id INTEGER, "
              "applied_at TIMESTAMP DEFAULT NOW())")
        # the real FK rule (auth._migrate_pipeline_*): job_id RESTRICT — the cause of #1
        c.run("CREATE TABLE job_pipeline_entries (id BIGSERIAL PRIMARY KEY, company_id INTEGER, candidate_id INTEGER, "
              "job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT, "
              "application_id INTEGER REFERENCES job_applications(id) ON DELETE SET NULL, stage TEXT)")
        c.run("CREATE TABLE pipeline_stage_events (id BIGSERIAL PRIMARY KEY, "
              "pipeline_entry_id BIGINT NOT NULL REFERENCES job_pipeline_entries(id) ON DELETE CASCADE, to_stage TEXT)")
    finally:
        auth.release_conn(c)
    admin_insights.migrate_admin_audit_log()
    admin_staff.migrate_admin_staff()   # task 8.4b — check_admin reads the owner session_version
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-53j-" + "s" * 32)
    srv._rate_store.clear()
    auth._cache_del("jobs:")
    yield
    srv._rate_store.clear()


def _admin():
    # task 8.4b: the login needs password + authenticator code (tests/test_admin_mfa_84b.py) — the owner token directly
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _seed():
    """One job per state → {state: id}."""
    _sql("INSERT INTO users (id, full_name, user_type, tw_id) VALUES (1, 'شركة النور', 'co', 'C1'), "
         "(2, 'Beta Co', 'co', 'C2'), (3, 'سارة', 'emp', 'U3')")
    ids = {}
    for key, sql in (
        ("active",   "'active', NOW() + INTERVAL '5 days', NULL, NULL, NULL"),
        ("paused",   "'paused', NOW() + INTERVAL '5 days', NULL, NOW(), NULL"),
        ("closed",   "'closed', NOW() + INTERVAL '5 days', NOW() - INTERVAL '2 days', NULL, NULL"),
        ("auto",     "'active', NOW() - INTERVAL '2 days', NULL, NULL, NULL"),        # duration over → closed
        ("expired",  "'closed', NOW() - INTERVAL '50 days', NOW() - INTERVAL '40 days', NULL, NULL"),
        ("old",      "'active', NOW() - INTERVAL '45 days', NULL, NULL, NULL"),       # never closed, 45 d → expired
        ("archived", "'active', NOW() + INTERVAL '5 days', NULL, NULL, NOW()"),
    ):
        cid = 2 if key == "paused" else 1
        ids[key] = _sql("INSERT INTO jobs (company_id, title, status, expires_at, closed_at, paused_at, archived_at) "
                        f"VALUES ({cid}, :t, {sql}) RETURNING id", t="وظيفة " + key)[0][0]
    return ids


# ── access ──
def test_admin_jobs_need_an_admin_session():
    user_jwt = srv._jwt_encode({"sv": 0, "user_id": 1, "user_type": "co"})
    for h in ({}, {"X-Admin-Token": PASSWORD}, {"X-Admin-Token": user_jwt}):
        assert client.get("/admin/jobs", headers=h).status_code == 401
        assert client.delete("/admin/jobs/1", headers=h).status_code == 401


# ── one status source (#14 / #15) ──
def test_sql_status_matches_eff_status():
    _seed()
    rows = _sql("SELECT status, closed_at, expires_at, paused_at, " + auth.job_eff_status_sql("j") + ", "
                + auth.job_active_sql("j") + ", archived_at FROM jobs j")
    assert len(rows) == 7
    for st, closed, exp, paused, sql_state, sql_active, archived in rows:
        py = auth._eff_status(st, closed, exp, paused)
        assert sql_state == py, (st, closed, exp, sql_state, py)
        assert sql_active == (py == "active" and archived is None)


def test_stats_counts_only_active_jobs():
    _seed()
    assert client.get("/stats").json()["jobs_count"] == 1


def test_dashboard_active_jobs_card_uses_the_status_source():
    """Card = job_active_sql: paused / closed / duration over / expired / archived are not counted."""
    _seed()
    with auth.db_conn() as c:   # the other tables the summary reads (empty)
        c.run("CREATE TABLE profiles (id SERIAL PRIMARY KEY, user_id INTEGER, is_verified BOOLEAN DEFAULT FALSE)")
        c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER, step TEXT)")
        c.run("CREATE TABLE messages (id SERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT NOW())")
        c.run("CREATE TABLE email_send_log (id SERIAL PRIMARY KEY, status TEXT, created_at TIMESTAMPTZ DEFAULT NOW())")
    r = client.get("/admin/stats/summary", headers=_admin())
    assert r.status_code == 200, r.text
    assert r.json()["data"]["active_jobs"]["value"] == 1
    want = _sql("SELECT COUNT(*) FROM jobs j WHERE " + auth.job_active_sql("j"))[0][0]
    assert want == 1


# ── list (#8) ──
def test_list_returns_every_state_with_counts():
    ids = _seed()
    _sql("INSERT INTO job_applications (job_id, user_id) VALUES (:a, 3), (:a, 4), (:c, 3)",
         a=ids["active"], c=ids["closed"])
    r = client.get("/admin/jobs", headers=_admin())
    assert r.status_code == 200 and r.json()["ok"] is True
    d = r.json()["data"]
    assert d["total"] == 7 and len(d["items"]) == 7
    by_id = {it["id"]: it for it in d["items"]}
    want = {"active": "active", "paused": "paused", "closed": "closed", "auto": "closed",
            "expired": "expired", "old": "expired", "archived": "archived"}
    for key, state in want.items():
        assert by_id[ids[key]]["status"] == state, key
    assert d["counts"] == {"all": 7, "active": 1, "paused": 1, "closed": 2, "expired": 2, "hidden": 0, "archived": 1}
    assert by_id[ids["active"]]["applicant_count"] == 2 and by_id[ids["closed"]]["applicant_count"] == 1
    assert by_id[ids["paused"]]["company_name"] == "Beta Co"
    assert "password_hash" not in by_id[ids["active"]] and "email" not in by_id[ids["active"]]


def test_list_filter_search_pages():
    ids = _seed()
    h = _admin()
    d = client.get("/admin/jobs?status=closed", headers=h).json()["data"]
    assert sorted(it["id"] for it in d["items"]) == sorted([ids["closed"], ids["auto"]]) and d["total"] == 2
    assert d["counts"]["all"] == 7                                   # tabs keep every state's number
    d = client.get("/admin/jobs", params={"q": "beta"}, headers=h).json()["data"]      # company name
    assert [it["id"] for it in d["items"]] == [ids["paused"]] and d["counts"]["all"] == 1
    d = client.get("/admin/jobs", params={"q": "archived"}, headers=h).json()["data"]  # title
    assert [it["id"] for it in d["items"]] == [ids["archived"]]
    p1 = client.get("/admin/jobs?limit=3&page=1", headers=h).json()["data"]
    p3 = client.get("/admin/jobs?limit=3&page=3", headers=h).json()["data"]
    assert len(p1["items"]) == 3 and len(p3["items"]) == 1 and p1["total"] == 7
    for bad in ("status=open", "status=deleted", "page=0", "limit=101", "limit=abc"):
        assert client.get("/admin/jobs?" + bad, headers=h).status_code == 422, bad


# ── hard delete (#1) ──
def test_delete_job_with_applicants_and_pipeline():
    ids = _seed()
    jid = ids["active"]
    app_id = _sql("INSERT INTO job_applications (job_id, user_id) VALUES (:j, 3) RETURNING id", j=jid)[0][0]
    entry = _sql("INSERT INTO job_pipeline_entries (company_id, candidate_id, job_id, application_id, stage) "
                 "VALUES (1, 3, :j, :a, 'new') RETURNING id", j=jid, a=app_id)[0][0]
    _sql("INSERT INTO pipeline_stage_events (pipeline_entry_id, to_stage) VALUES (:e, 'new')", e=entry)
    r = client.delete(f"/admin/jobs/{jid}", headers=_admin())
    assert r.status_code == 200, r.text
    assert r.json()["removed"] == {"applicants": 1, "pipeline_entries": 1}
    assert _sql("SELECT COUNT(*) FROM jobs WHERE id=:j", j=jid)[0][0] == 0
    assert _sql("SELECT COUNT(*) FROM job_pipeline_entries")[0][0] == 0
    assert _sql("SELECT COUNT(*) FROM pipeline_stage_events")[0][0] == 0
    assert _sql("SELECT COUNT(*) FROM jobs")[0][0] == 6                       # nothing else touched
    assert client.delete(f"/admin/jobs/{jid}", headers=_admin()).status_code == 404
