"""Task 5.3a2 — Admin Audit Log + Admin Stats (SYSTEMS_INDEX §25b / §25c · docs/rules/admin-shell.md).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it):
  - every new admin endpoint answers 401 without an admin session
  - GET /admin/stats/timeseries: metric outside the allowlist → 422 · bad days → 422 · daily counts
  - GET /admin/stats/summary + GET /admin/activity read the real tables
  - the audit log records admin writes + admin logins (ok / denied) with the client IP, and never
    a password, a token or a body · GET /admin/audit filters + pages
  - /health reports storage (configured | missing) · the audit table is a critical startup migration
  - (task 5.3a3) GET /admin/users: search · type · verification · sort · server pages · no sensitive field ·
    GET /admin/users/export: same filters → CSV, recorded in the audit log · GET /admin/activity pages
Run: python -m pytest tests/test_admin_insights.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-insights-53a2-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-53a2-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import admin_insights
import server as srv

client = TestClient(srv.app)
PASSWORD = "p" * 40
LOGIN = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN + "/login"   # the panel login path (slug from the env, never in a file)
NEW_ENDPOINTS = ("/admin/stats/summary", "/admin/stats/timeseries?metric=users&days=30",
                 "/admin/activity", "/admin/audit", "/admin/users", "/admin/users/export")


# every table auth.ensure_company_tables() creates (dropped so the real migration rebuilds them)
_COMPANY_TABLES = ("company_post_comment_mentions", "company_post_comments", "company_post_saves",
                   "company_post_appreciations", "company_post_views", "company_posts", "company_ratings",
                   "company_profiles")


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
        for t in ("admin_audit_log", "reports", "email_send_log", "messages", "kyc_submissions",
                  "job_applications", "jobs", "profile_follows", *_COMPANY_TABLES, "profiles", "users"):
            c.run(f"DROP TABLE IF EXISTS {t} CASCADE")
        c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, full_name TEXT, email TEXT, user_type TEXT DEFAULT 'emp', "
              "is_verified BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW(), tw_id TEXT, "
              "password_hash TEXT DEFAULT 'HASH-SECRET', phone TEXT DEFAULT '0790000000')")
        c.run("CREATE TABLE profiles (id SERIAL PRIMARY KEY, user_id INTEGER, is_verified BOOLEAN DEFAULT FALSE, "
              "avatar_url TEXT)")
        # profile_follows — same columns as auth.init_db (needed by /mention/search)
        c.run("CREATE TABLE profile_follows (id SERIAL PRIMARY KEY, follower_id INTEGER NOT NULL, "
              "followed_id INTEGER NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())")
        c.run("CREATE TABLE jobs (id SERIAL PRIMARY KEY, company_id INTEGER, title TEXT, status TEXT DEFAULT 'active', "
              "created_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP, closed_at TIMESTAMP, "
              "archived_at TIMESTAMPTZ, admin_hidden_at TIMESTAMPTZ)")
        c.run("CREATE TABLE job_applications (id SERIAL PRIMARY KEY, job_id INTEGER, user_id INTEGER, "
              "applied_at TIMESTAMP DEFAULT NOW())")
        c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER, step TEXT, "
              "submitted_at TIMESTAMP DEFAULT NOW())")
        c.run("CREATE TABLE messages (id SERIAL PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, content TEXT, "
              "created_at TIMESTAMP DEFAULT NOW())")
        c.run("CREATE TABLE email_send_log (id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ DEFAULT NOW(), "
              "template_key TEXT, category TEXT, status TEXT)")
        c.run("CREATE TABLE reports (id SERIAL PRIMARY KEY, reporter_id INTEGER, reported_id INTEGER, "
              "reported_type TEXT DEFAULT 'user', report_type TEXT, reason TEXT, target_url TEXT, "
              "status TEXT DEFAULT 'pending', created_at TIMESTAMPTZ DEFAULT NOW())")
    finally:
        auth.release_conn(c)
    admin_insights.migrate_admin_audit_log()
    auth.ensure_company_tables()   # company_profiles from the real migration — never a hand-made column (5.3a4)
    assert _sql("SELECT to_regclass('company_profiles')")[0][0], "company_profiles migration failed"
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-53a2-" + "s" * 32)
    srv._rate_store.clear()
    yield
    srv._rate_store.clear()


def _admin():
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.status_code == 200
    return {"X-Admin-Token": r.json()["token"]}


def _audit_rows():
    return [tuple(r) for r in _sql("SELECT actor, action, target, result, status, ip FROM admin_audit_log ORDER BY id")]


# ── access ──
def test_new_endpoints_need_an_admin_session():
    user_jwt = srv._jwt_encode({"sv": 0, "user_id": 1, "user_type": "emp"})   # a user session is not an admin session
    for url in NEW_ENDPOINTS:
        assert client.get(url).status_code == 401, url
        assert client.get(url, headers={"X-Admin-Token": PASSWORD}).status_code == 401, url   # raw password ≠ session
        assert client.get(url, headers={"X-Admin-Token": user_jwt}).status_code == 401, url


# ── time series ──
def test_timeseries_rejects_metric_outside_allowlist_and_bad_days():
    h = _admin()
    for metric in ("", "messages", "users; DROP TABLE users", "password_hash"):
        r = client.get("/admin/stats/timeseries", params={"metric": metric, "days": "30"}, headers=h)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_metric", metric
    for days in ("0", "91", "-1", "abc", "٣٠"):
        r = client.get("/admin/stats/timeseries", params={"metric": "users", "days": days}, headers=h)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_days", days
    assert _sql("SELECT COUNT(*) FROM users")[0][0] == 0   # table still there


def test_timeseries_daily_counts():
    _sql("INSERT INTO users (full_name, email, created_at) VALUES "
         "('a','a@x', NOW()), ('b','b@x', NOW()), ('c','c@x', NOW() - INTERVAL '2 days'), "
         "('d','d@x', NOW() - INTERVAL '40 days')")
    r = client.get("/admin/stats/timeseries?metric=users&days=7", headers=_admin())
    assert r.status_code == 200
    d = r.json()["data"]
    counts = [p["count"] for p in d["points"]]
    assert len(counts) == 7 and counts[-1] == 2 and counts[-3] == 1 and sum(counts) == 3
    assert d["in_range"] == 3 and d["total"] == 4
    assert d["points"][-1]["date"] > d["points"][0]["date"]


# ── summary + activity ──
def test_summary_reads_the_real_tables():
    _sql("INSERT INTO users (full_name, email, user_type, is_verified, created_at) VALUES "
         "('co1','c1@x','co', TRUE, NOW()), ('co2','c2@x','co', FALSE, NOW()), ('co3','c3@x','co', FALSE, NOW()), "
         "('e1','e1@x','emp', FALSE, NOW() - INTERVAL '45 days')")
    # badge source = profiles.is_verified only (task 5.0c) — users.is_verified (co1) is legacy, not counted
    _sql("INSERT INTO profiles (user_id, is_verified) VALUES (2, TRUE), (3, TRUE)")
    _sql("INSERT INTO jobs (company_id, title, status) VALUES (1,'j1','active'), (1,'j2','active'), (1,'j3','closed')")
    _sql("INSERT INTO job_applications (job_id, user_id) VALUES (1, 4)")
    _sql("INSERT INTO kyc_submissions (user_id, step) VALUES (3, 'review'), (4, 'approved')")
    _sql("INSERT INTO messages (sender_id, receiver_id, content, created_at) VALUES "
         "(1,2,'x', NOW()), (1,2,'y', NOW()), (1,2,'z', CURRENT_DATE - INTERVAL '12 hours')")
    _sql("INSERT INTO email_send_log (template_key, category, status) VALUES ('a','security','sent'), ('b','security','failed')")
    _sql("INSERT INTO reports (reported_id, report_type, status) VALUES (3,'spam','pending'), (3,'spam','resolved')")
    r = client.get("/admin/stats/summary", headers=_admin())
    assert r.status_code == 200 and r.json()["ok"] is True
    d = r.json()["data"]
    assert d["users"]["value"] == 4 and d["users"]["period"] == "month"
    assert d["verified_companies"] == {"value": 2, "change": None, "period": None}
    assert d["active_jobs"]["value"] == 2 and d["applications"]["value"] == 1
    assert d["open_reports"]["value"] == 1 and d["pending_kyc"]["value"] == 1
    assert d["messages_today"]["value"] == 2 and d["messages_today"]["change"] == 100.0
    assert d["emails_today"]["value"] == 1 and d["emails_today"]["change"] is None   # nothing yesterday


def test_activity_lists_latest_events_without_private_fields():
    _sql("INSERT INTO users (full_name, email, user_type) VALUES ('شركة','secret@x','co'), ('سارة','s@x','emp')")
    _sql("INSERT INTO jobs (company_id, title) VALUES (1, 'مطور')")
    _sql("INSERT INTO kyc_submissions (user_id, step) VALUES (2, 'review')")
    _sql("INSERT INTO reports (reported_id, report_type, reason) VALUES (2, 'spam', 'private reason text')")
    r = client.get("/admin/activity", headers=_admin())
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert {i["kind"] for i in items} == {"register", "job", "kyc", "report"}
    job = [i for i in items if i["kind"] == "job"][0]
    assert job["title"] == "مطور" and job["sub"] == "شركة"
    body = r.text
    assert "secret@x" not in body and "private reason text" not in body


# ── audit log ──
def test_audit_records_login_success_and_failure_without_secrets():
    client.post(LOGIN, json={"password": "wrong-" + "w" * 30}, headers={"X-Real-IP": "203.0.113.9"})
    r = client.post(LOGIN, json={"password": PASSWORD}, headers={"X-Real-IP": "203.0.113.10"})
    token = r.json()["token"]
    rows = _audit_rows()
    assert [(x[1], x[3], x[4], x[5]) for x in rows] == [
        ("admin_login", "denied", 401, "203.0.113.9"), ("admin_login", "ok", 200, "203.0.113.10")]
    assert rows[0][0] == "-" and rows[1][0] == "owner"
    dump = repr(_sql("SELECT * FROM admin_audit_log"))
    assert PASSWORD not in dump and token not in dump and "wrong-" not in dump


def test_audit_records_admin_writes_and_denied_attempts():
    _sql("INSERT INTO reports (reported_id, report_type) VALUES (1, 'spam')")
    h = _admin()
    assert client.put("/admin/reports/1/resolve", headers=h).status_code == 200
    assert client.put("/admin/reports/1/resolve").status_code == 401                 # no session
    client.get("/admin/reports", headers=h)                                          # reads are not logged
    client.post("/admin/message", headers=h, json={"user_id": 999, "subject": "s", "message": "very private text"})
    rows = _audit_rows()[1:]   # [0] = the login above
    assert rows[0] == ("owner", "resolve_report", "report_id=1", "ok", 200, "testclient")
    assert rows[1][:4] == ("-", "resolve_report", "report_id=1", "denied")
    assert len(rows) == 3 and rows[2][1] == "admin_send_message"
    assert "very private text" not in repr(_sql("SELECT * FROM admin_audit_log"))


def test_audit_list_filter_and_pages():
    for i in range(5):
        admin_insights.audit_record("owner", "delete_user", f"user_id={i}", 200, "1.2.3.4")
    admin_insights.audit_record("owner", "verify_user", "user_id=9", 403, "1.2.3.4")
    h = _admin()
    d = client.get("/admin/audit?limit=2&action=delete_user", headers=h).json()["data"]
    assert d["total"] == 5 and len(d["items"]) == 2 and d["items"][0]["target"] == "user_id=4"
    assert set(d["actions"]) >= {"delete_user", "verify_user", "admin_login"}
    d3 = client.get("/admin/audit?limit=2&page=3&action=delete_user", headers=h).json()["data"]
    assert [i["target"] for i in d3["items"]] == ["user_id=0"]
    v = client.get("/admin/audit?action=verify_user", headers=h).json()["data"]["items"][0]
    assert v["result"] == "denied" and v["status"] == 403
    assert client.get("/admin/audit?limit=500", headers=h).status_code == 422
    assert client.get("/admin/audit?page=0", headers=h).status_code == 422


def test_health_storage_and_critical_migration():
    body = client.get("/health").json()
    assert body["storage"] in ("configured", "missing")
    crit = {n: c for n, _, c in srv._startup_migrations()}
    assert crit.get("admin_audit_log") is True


# ── activity pages (task 5.3a3 — the dashboard shows 8, «عرض الكل» pages through all) ──
def test_activity_pages():
    for i in range(12):
        _sql("INSERT INTO users (full_name, email, created_at) VALUES (:n, :e, NOW() - make_interval(mins => :m))",
             n=f"u{i}", e=f"u{i}@x", m=i)
    h = _admin()
    d = client.get("/admin/activity", headers=h).json()["data"]
    assert d["limit"] == 8 and len(d["items"]) == 8 and d["total"] == 12 and d["items"][0]["title"] == "u0"
    d2 = client.get("/admin/activity?page=2&limit=5", headers=h).json()["data"]
    assert [i["title"] for i in d2["items"]] == ["u5", "u6", "u7", "u8", "u9"]
    assert client.get("/admin/activity?limit=500", headers=h).status_code == 422
    assert client.get("/admin/activity?page=0", headers=h).status_code == 422


# ── users table (task 5.3a3 · SYSTEMS_INDEX §25d) ──
def _seed_users():
    _sql("INSERT INTO users (full_name, email, user_type, is_verified, tw_id, created_at) VALUES "
         "('سارة أحمد','sara@x.com','emp', FALSE, 'U100', NOW() - INTERVAL '3 days'), "      # 1 pending (KYC)
         "('شركة النور','info@noor.co','co', TRUE, 'C200', NOW() - INTERVAL '2 days'), "     # 2 verified (profile)
         "('=HYPERLINK(1)','evil@x.com','co', FALSE, 'C300', NOW() - INTERVAL '1 days'), "   # 3 verified (profile)
         "('معهد 100%','edu@x.com','edu', FALSE, 'T400', NOW())")                            # 4 unverified
    # the company logo lives in profiles.avatar_url (company_profiles has no image column)
    _sql("INSERT INTO profiles (user_id, is_verified, avatar_url) VALUES (1, FALSE, 'https://cdn.x/a.png'), "
         "(2, TRUE, 'https://cdn.x/logo.png'), (3, TRUE, NULL)")
    _sql("INSERT INTO company_profiles (user_id, industry) VALUES (2, 'tech')")
    _sql("INSERT INTO kyc_submissions (user_id, step) VALUES (1, 'review'), (4, 'rejected')")


def _users(h, **params):
    r = client.get("/admin/users", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_admin_users_fields_filters_search_pages():
    _seed_users()
    h = _admin()
    d = _users(h)
    assert d["total"] == 4 and d["page"] == 1 and d["limit"] == 20
    assert [u["id"] for u in d["items"]] == [4, 3, 2, 1]                       # newest first
    assert set(d["items"][0]) == {"id", "tw_id", "full_name", "avatar_url", "user_type", "email",
                                  "verification", "created_at"}
    by_id = {u["id"]: u for u in d["items"]}
    assert {i: u["verification"] for i, u in by_id.items()} == {1: "pending", 2: "verified", 3: "verified", 4: "unverified"}
    assert by_id[1]["avatar_url"] == "https://cdn.x/a.png" and by_id[2]["avatar_url"] == "https://cdn.x/logo.png"
    assert "HASH-SECRET" not in client.get("/admin/users", headers=h).text
    assert "0790000000" not in client.get("/admin/users", headers=h).text
    # filters
    assert [u["id"] for u in _users(h, type="co")["items"]] == [3, 2]
    assert [u["id"] for u in _users(h, status="verified")["items"]] == [3, 2]
    assert [u["id"] for u in _users(h, status="pending")["items"]] == [1]
    assert [u["id"] for u in _users(h, status="unverified")["items"]] == [4]
    assert [u["id"] for u in _users(h, type="co", status="verified", sort="oldest")["items"]] == [2, 3]
    # search: name · email · tw_id, case-insensitive; LIKE wildcards are literal
    assert [u["id"] for u in _users(h, q="سارة")["items"]] == [1]
    assert [u["id"] for u in _users(h, q="NOOR.CO")["items"]] == [2]
    assert [u["id"] for u in _users(h, q="t400")["items"]] == [4]
    assert [u["id"] for u in _users(h, q="100%")["items"]] == [4]
    assert _users(h, q="%")["total"] == 1 and _users(h, q="_")["total"] == 0
    # pages
    p2 = _users(h, page="2", limit="3")
    assert p2["total"] == 4 and [u["id"] for u in p2["items"]] == [1]
    # bad input → 422 (allowlists — nothing from the request reaches SQL text)
    for bad in ({"type": "admin"}, {"status": "x"}, {"sort": "created_at; DROP TABLE users"}, {"limit": "101"},
                {"page": "0"}, {"limit": "abc"}, {"q": "x" * 101}):
        assert client.get("/admin/users", params=bad, headers=h).status_code == 422, bad
    assert _sql("SELECT COUNT(*) FROM users")[0][0] == 4


def test_admin_users_and_export_ok_with_company_row_and_logo():
    # 5.3a4: a company with a company_profiles row + a logo in profiles → 200, the logo comes back
    _seed_users()
    h = _admin()
    d = _users(h, type="co")
    assert {u["id"]: u["avatar_url"] for u in d["items"]} == {2: "https://cdn.x/logo.png", 3: None}
    r = client.get("/admin/users/export", params={"type": "co"}, headers=h)
    assert r.status_code == 200 and "info@noor.co" in r.text


def test_mention_search_returns_company_logo_from_profiles():
    # 5.3a4: the follow branch of /mention/search used to fail on company_profiles.avatar_url → ok:false
    _seed_users()
    _sql("INSERT INTO profile_follows (follower_id, followed_id) VALUES (1, 2)")
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": 1, "user_type": "emp"})}
    r = client.get("/mention/search", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["candidates"] == [{"tw_id": "C200", "name": "شركة النور",
                                   "avatar": "https://cdn.x/logo.png", "user_type": "co"}]
    r = client.get("/mention/search", params={"q": "النور"}, headers=h)
    assert r.json()["ok"] is True and [c["tw_id"] for c in r.json()["candidates"]] == ["C200"]


def test_admin_users_export_csv_same_filters_and_audited():
    _seed_users()
    h = _admin()
    r = client.get("/admin/users/export", params={"type": "co"}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("\ufeff")
    import csv as _csv
    rows = list(_csv.reader(text.lstrip("\ufeff").splitlines()))
    assert rows[0] == ["id", "tw_id", "full_name", "user_type", "email", "verification", "created_at"]
    assert [x[0] for x in rows[1:]] == ["3", "2"]
    assert rows[1][2] == "'=HYPERLINK(1)"                                     # formula injection neutralised
    assert "HASH-SECRET" not in text and "0790000000" not in text and "logo.png" not in text
    assert client.get("/admin/users/export", params={"status": "nope"}, headers=h).status_code == 422
    # the export is recorded (a read, but data leaves the site); plain list reads are not
    client.get("/admin/users", headers=h)
    acts = [x[1] for x in _audit_rows()]
    assert acts.count("admin_users_export") == 2 and "admin_users" not in acts
    assert client.get("/admin/users/export").status_code == 401
    assert [x[3] for x in _audit_rows() if x[1] == "admin_users_export"][-1] == "denied"


def test_old_unpaged_users_list_is_gone():
    h = _admin()
    assert client.get("/auth/users", headers=h).status_code in (404, 405)
