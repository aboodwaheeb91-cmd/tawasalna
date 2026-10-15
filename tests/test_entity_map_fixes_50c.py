"""Task 5.0c — fixes from the admin entity map (docs/ADMIN_ENTITY_MAP.md §20).

Behaviour only (real endpoints + real PostgreSQL schema from init_db):
  #2 / #12  job report stored by type (job_id → jobs) · no 500 · reported account deleted → report kept
  #11       GET /admin/reports: a DB error → 500, never an empty list
  #3 #4 #5  KYC approve gives the public badge (profiles.is_verified) + step approved · no submission /
            not in review → 409 · reject removes the badge
  #6        POST /kyc/docs before email + phone are verified → 409
  #10       admin password reset uses the one password rule → 422
  #16       PUT /admin/user/{id}/verify {is_verified:false} un-verifies · missing value → 422
  #17       /my/applications never returns an internal stage
  migration old job reports (job id in reported_id) → job_id

  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_entity_map_fixes_50c.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-entitymap-50c-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import admin_insights
import auth
import server as srv

client = TestClient(srv.app)
PASSWORD = "p" * 40
LOGIN = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN + "/login"


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(name, utype="emp"):
    return _sql("INSERT INTO users (tw_id, email, full_name, user_type, password_hash) "
                "VALUES (:tw, :e, :n, :t, 'x') RETURNING id",
                tw=("C" if utype == "co" else "U") + name, e=name + "@x.com", n=name, t=utype)[0][0]


def _doc(uid):
    """A private KYC object path as /upload/image names it for this user."""
    return f"kyc-docs/{uid}_kyc-id-front_abcdef012345.jpg"


def _bearer(uid, utype="emp"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": uid, "user_type": utype})}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP SCHEMA public CASCADE")
    c.run("CREATE SCHEMA public")
    auth.release_conn(c)
    auth.init_db()
    auth._migrate_profiles_user_unique()
    auth._migrate_jobs_v2()
    auth._migrate_job_lifecycle()
    with auth.db_conn() as c:   # jobs.archived_at — same column as auth._migrate_pipeline_schema_v1 (job-status SQL reads it, 5.3j)
        c.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL")
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    auth._migrate_password_reset_tokens()
    auth._migrate_kyc_otp_security()
    auth._migrate_email_notify()
    admin_insights.migrate_admin_audit_log()
    auth._migrate_reports_targets()
    auth._migrate_reports_targets()          # idempotent
    auth._migrate_verified_source()
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-50c-" + "s" * 32)
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
    yield
    srv._rate_store.clear()


def _admin():
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.status_code == 200
    return {"X-Admin-Token": r.json()["token"]}


def _job(company_id, title="مطوّر"):
    return _sql("INSERT INTO jobs (company_id, title, status) VALUES (:c, :t, 'active') RETURNING id",
                c=company_id, t=title)[0][0]


def _badge(uid):
    rows = _sql("SELECT is_verified FROM profiles WHERE user_id = :u", u=uid)
    return bool(rows and rows[0][0])


# ── reports (#2 #11 #12) ──
def test_job_report_is_stored_on_the_job_and_listed_with_its_title():
    co, emp = _user("co1", "co"), _user("emp1")
    jid = _job(co, "محاسب")
    for _ in range(3):                       # job ids beyond the users ids — the old FK would 500
        jid = _job(co, "محاسب")
    r = client.post("/reports/submit", headers=_bearer(emp),
                    json={"reported_id": jid, "reported_type": "job", "report_type": "spam", "reason": "x"})
    assert r.status_code == 200, r.text
    assert [tuple(x) for x in _sql("SELECT job_id, reported_id FROM reports")] == [(jid, None)]
    rep = client.get("/admin/reports", headers=_admin()).json()["reports"][0]
    assert rep["target"] == {"kind": "job", "id": jid, "name": "محاسب",
                             "href": f"/job-detail?id={jid}", "deleted": False}


def test_report_bad_type_or_missing_target():
    emp = _user("emp1")
    body = {"reported_id": 999, "report_type": "spam", "reason": "x"}
    assert client.post("/reports/submit", headers=_bearer(emp), json={**body, "reported_type": "post"}).status_code == 422
    assert client.post("/reports/submit", headers=_bearer(emp), json={**body, "reported_type": "job"}).status_code == 404
    assert client.post("/reports/submit", headers=_bearer(emp), json={**body, "reported_type": "user"}).status_code == 404


def test_deleting_the_reported_account_keeps_the_report():
    bad, emp = _user("bad1"), _user("emp1")
    assert client.post("/reports/submit", headers=_bearer(emp), json={
        "reported_id": bad, "reported_type": "user", "report_type": "fraud", "reason": "x"}).status_code == 200
    h = _admin()
    assert client.get("/admin/reports", headers=h).json()["reports"][0]["target"]["href"] == "/u/Ubad1"
    assert client.delete(f"/admin/user/{bad}", headers=h).status_code == 200
    reps = client.get("/admin/reports", headers=h).json()["reports"]
    assert len(reps) == 1 and reps[0]["target"]["deleted"] is True and reps[0]["target"]["kind"] == "user"


def test_admin_reports_db_error_is_not_an_empty_list():
    h = _admin()
    _sql("DROP TABLE reports")
    assert client.get("/admin/reports", headers=h).status_code == 500


def test_migration_moves_old_job_reports_to_job_id():
    co, emp = _user("co1", "co"), _user("emp1")
    jid = _job(co)
    _sql("INSERT INTO reports (reporter_id, reported_id, reported_type, report_type) VALUES (:e, :j, 'job', 'spam')",
         e=emp, j=jid)        # the old bug: the job id in reported_id (here = an existing account id)
    auth._migrate_reports_targets()
    assert [tuple(x) for x in _sql("SELECT job_id, reported_id FROM reports")] == [(jid, None)]


# ── KYC + badge (#3 #4 #5 #6 #16) ──
def _kyc_in_review(uid):
    _sql("INSERT INTO kyc_submissions (user_id, step, status, email_verified, phone_verified) "
         "VALUES (:u, 'id_upload', 'pending', TRUE, TRUE)", u=uid)
    r = client.post("/kyc/docs", headers=_bearer(uid), json={"id_front_url": _doc(uid)})
    assert r.status_code == 200, r.text


def test_kyc_approve_gives_the_public_badge_and_leaves_review():
    uid = _user("emp1")
    _kyc_in_review(uid)
    h = _admin()
    assert client.put(f"/admin/kyc/{uid}/approve", headers=h, json={"note": ""}).status_code == 200
    assert _badge(uid) is True
    assert tuple(_sql("SELECT step, status FROM kyc_submissions WHERE user_id = :u", u=uid)[0]) == ("approved", "approved")
    assert client.get("/admin/stats/summary", headers=h).json()["data"]["pending_kyc"]["value"] == 0
    assert client.put(f"/admin/kyc/{uid}/approve", headers=h, json={"note": ""}).status_code == 409   # not in review


def test_kyc_approve_or_reject_without_submission_is_409():
    uid = _user("emp1")
    h = _admin()
    assert client.put(f"/admin/kyc/{uid}/approve", headers=h, json={"note": ""}).status_code == 409
    assert client.put(f"/admin/kyc/{uid}/reject", headers=h, json={"note": ""}).status_code == 409
    assert _badge(uid) is False


def test_kyc_reject_removes_the_badge():
    uid = _user("emp1")
    _sql("INSERT INTO profiles (user_id, is_verified) VALUES (:u, TRUE)", u=uid)
    _kyc_in_review(uid)
    assert client.put(f"/admin/kyc/{uid}/reject", headers=_admin(), json={"note": ""}).status_code == 200
    assert _badge(uid) is False


def test_kyc_docs_cannot_skip_email_and_phone():
    uid = _user("emp1")
    h = _bearer(uid)
    assert client.post("/kyc/docs", headers=h, json={"id_front_url": _doc(uid)}).status_code == 409   # no submission
    _sql("INSERT INTO kyc_submissions (user_id, step) VALUES (:u, 'email')", u=uid)
    assert client.post("/kyc/docs", headers=h, json={"id_front_url": _doc(uid)}).status_code == 409
    assert _sql("SELECT step FROM kyc_submissions WHERE user_id = :u", u=uid)[0][0] == "email"


def test_admin_manual_verify_and_unverify():
    uid = _user("co1", "co")
    h = _admin()
    assert client.put(f"/admin/user/{uid}/verify", headers=h, json={"is_verified": True}).status_code == 200
    assert _badge(uid) is True
    assert client.put(f"/admin/user/{uid}/verify", headers=h, json={"is_verified": False}).status_code == 200
    assert _badge(uid) is False
    assert client.put(f"/admin/user/{uid}/verify", headers=h, json={"verified": True}).status_code == 422
    assert _badge(uid) is False


# ── admin password (#10) ──
def test_admin_password_reset_uses_the_password_rule():
    uid = _user("emp1")
    h = _admin()
    r = client.put(f"/admin/user/{uid}/password", headers=h, json={"password": "abc"})
    assert r.status_code == 422 and r.json()["error"]["field"] == "password"
    assert client.put(f"/admin/user/{uid}/password", headers=h, json={"password": "long-enough-1"}).status_code == 200


# ── my applications (#17) ──
def test_my_applications_shows_three_states_only():
    co, emp = _user("co1", "co"), _user("emp1")
    internal = ["pending", "viewed", "accepted", "contacted", "interview", "hired", "rejected"]
    for st in internal:
        jid = _job(co, st)
        _sql("INSERT INTO job_applications (job_id, user_id, status) VALUES (:j, :u, :s)", j=jid, u=emp, s=st)
    r = client.get("/my/applications", headers=_bearer(emp))
    assert r.status_code == 200
    got = {a["title"]: a["status"] for a in r.json()["applications"]}
    assert got == {"pending": "in_review", "viewed": "in_review", "accepted": "in_review",
                   "contacted": "in_review", "interview": "in_review", "hired": "hired", "rejected": "rejected"}
