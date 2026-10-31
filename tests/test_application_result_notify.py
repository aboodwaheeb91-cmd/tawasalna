"""Task 5.1d — the applicant hears the FINAL result of an application, nothing else.

Behaviour only — real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), Resend faked at the
HTTP layer (urllib.request.urlopen inside email_service):
  - intermediate statuses (pending … interview) → no notification, no email
  - hired / rejected → one in-site notification + one notification email, once per application
    per final status (back to an intermediate status and forward again → no repeat)
  - both write paths: PUT /jobs/applications/{id}/status and the per-job candidate status
  - the admin type switch / the company setting / the user's switch are respected
  - the rejection text names no stage
Run: python -m pytest tests/test_application_result_notify.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-result-51d-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-51d-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server


def _owner_stepup_hdr():
    """The owner after the step-up (task 8.4c-1 — owner-only writes / the export need X-Admin-Stepup, else 428)."""
    tok = server._admin_jwt_issue()
    return {"X-Admin-Token": tok, "X-Admin-Stepup": server._admin_step_up_issue("owner", 1, tok)}

client = TestClient(server.app)

DROP = ("pipeline_stage_events", "pipeline_notes", "job_pipeline_entries", "candidate_bank_notes",
        "company_candidate_job_refs", "company_saved_candidates", "appointments", "job_applications",
        "company_settings", "email_notify_prefs", "email_send_log", "notifications", "jobs", "profiles", "users")
PREREQ = [
    "CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT UNIQUE, full_name TEXT, email TEXT UNIQUE, "
    "user_type TEXT NOT NULL DEFAULT 'emp')",
    "CREATE TABLE profiles (id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE)",
    "CREATE TABLE jobs (id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', "
    "archived_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE TABLE job_applications (id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, "
    "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, status TEXT NOT NULL DEFAULT 'pending', "
    "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(job_id, user_id))",
    "CREATE TABLE company_saved_candidates (id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES users(id), "
    "candidate_id INTEGER NOT NULL REFERENCES users(id), job_id INTEGER, saved_by INTEGER, "
    "status TEXT NOT NULL DEFAULT 'saved', notes TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(company_id, candidate_id))",
    "CREATE TABLE company_candidate_job_refs (company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, candidate_status TEXT, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (company_id, candidate_id, job_id))",
    "CREATE TABLE appointments (id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL, "
    "job_id INTEGER, scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), status TEXT NOT NULL DEFAULT 'pending', "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE TABLE notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), type TEXT, "
    "title TEXT, body TEXT, link TEXT, is_read BOOLEAN DEFAULT FALSE, actor_id INTEGER, entity_id INTEGER, "
    "entity_type TEXT, event_key TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE UNIQUE INDEX uniq_notif_event_key ON notifications (user_id, event_key) WHERE event_key IS NOT NULL",
]
STAGE_WORDS = ("مقابلة", "التواصل", "القائمة", "المراجعة", "interview", "contacted", "shortlisted")


class FakeResend:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(json.loads(req.data.decode("utf-8")))

        class _R:
            status = 200
            def read(self): return b'{"id":"re_msg_1"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R()


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
        for t in DROP:
            c.run(f"DROP TABLE IF EXISTS {t} CASCADE")
        for q in PREREQ:
            c.run(q)
    finally:
        auth.release_conn(c)
    auth._migrate_pipeline_schema_v1()
    auth._migrate_pr5_pipeline_linking()
    auth._migrate_applicants_candidates_split()
    auth._migrate_email_notify()
    server.ad.migrate_account_deletion()      # task 8.5a — users.deleted_* (read by create_notification)
    server.admin_staff.migrate_admin_staff()   # task 8.4b — check_admin reads the owner session_version
    auth._migrate_company_settings()
    auth._migrate_company_settings()          # idempotent
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", "re_TEST_KEY_51d")
    monkeypatch.setattr(auth, "_email_submit", lambda fn, *a: fn(*a))   # inline instead of the pool
    email_service.set_settings(email_service.DEFAULTS)
    yield f
    email_service.set_settings(email_service.DEFAULTS)


def _world():
    """→ (company_id, applicant_id, job_id, app_id)."""
    co = _sql("INSERT INTO users (tw_id, full_name, email, user_type) VALUES ('C1', 'شركة النور', 'co@x.com', 'co') "
              "RETURNING id")[0][0]
    emp = _sql("INSERT INTO users (tw_id, full_name, email) VALUES ('U1', 'أمل', 'amal@x.com') RETURNING id")[0][0]
    job = _sql("INSERT INTO jobs (company_id, title) VALUES (:c, 'مصمم واجهات') RETURNING id", c=co)[0][0]
    app = _sql("INSERT INTO job_applications (job_id, user_id) VALUES (:j, :u) RETURNING id", j=job, u=emp)[0][0]
    return co, emp, job, app


def _hdr(uid, user_type):
    return {"Authorization": "Bearer " + server._jwt_encode({"sv": 0, "user_id": uid, "user_type": user_type, "tw_id": ""})}


def _status(co, app, status):
    r = client.put(f"/jobs/applications/{app}/status", headers=_hdr(co, "co"), json={"status": status})
    assert r.status_code == 200, r.text


def _notifs(uid):
    return [tuple(r) for r in _sql("SELECT type, title, body FROM notifications WHERE user_id = :u ORDER BY id", u=uid)]


# ── 1. intermediate statuses stay internal ───────────────────────────────────
def test_intermediate_statuses_send_nothing(env):
    co, emp, job, app = _world()
    for s in ("viewed", "accepted", "contacted", "interview", "pending"):
        _status(co, app, s)
    assert _notifs(emp) == [] and env.calls == []
    assert _sql("SELECT COUNT(*) FROM email_send_log")[0][0] == 0


# ── 2. hired / rejected — once per application per final status ─────────────
def test_hired_sends_once_with_job_and_company(env):
    co, emp, job, app = _world()
    _status(co, app, "hired")
    ((typ, title, body),) = _notifs(emp)
    assert typ == "application_hired" and "مصمم واجهات" in body and "شركة النور" in body
    (call,) = env.calls
    assert call["to"] == ["amal@x.com"] and "مصمم واجهات" in call["subject"]
    assert f"https://tawasolna.com/job-detail?id={job}" in call["text"]
    _status(co, app, "interview")        # back to an intermediate stage — nothing
    _status(co, app, "hired")            # final again — no repeat
    _status(co, app, "hired")
    assert len(_notifs(emp)) == 1 and len(env.calls) == 1


def test_rejected_text_names_no_stage(env):
    co, emp, job, app = _world()
    _status(co, app, "interview")
    _status(co, app, "rejected")
    ((typ, title, body),) = _notifs(emp)
    assert typ == "application_rejected"
    (call,) = env.calls
    for text in (title, body, call["subject"], call["text"]):
        assert not any(w in text for w in STAGE_WORDS), text
    _status(co, app, "contacted")
    _status(co, app, "rejected")
    assert len(_notifs(emp)) == 1 and len(env.calls) == 1


def test_candidate_status_path_sends_too(env):
    co, emp, job, app = _world()
    _status(co, app, "accepted")                     # creates the per-job ref
    assert auth.update_candidate_job_status(co, emp, job, "interview", actor_id=co) is True
    assert _notifs(emp) == []
    assert auth.update_candidate_job_status(co, emp, job, "rejected", actor_id=co) is True
    assert [n[0] for n in _notifs(emp)] == ["application_rejected"]
    _status(co, app, "rejected")                     # same final status via the other path — no repeat
    assert len(_notifs(emp)) == 1 and len(env.calls) == 1


# ── 3. switches: admin · company · user ──────────────────────────────────────
def test_admin_switch_off_stops_that_status_only(env):
    co, emp, job, app = _world()
    adm = _owner_stepup_hdr()
    assert client.put("/admin/email", headers=adm,
                      json={"types": {"notify_application_rejected": False}}).status_code == 200
    _status(co, app, "rejected")
    assert _notifs(emp) == [] and env.calls == []    # no in-site notification, no email
    _status(co, app, "hired")
    assert [n[0] for n in _notifs(emp)] == ["application_hired"] and len(env.calls) == 1


def test_company_setting_off_sends_nothing(env):
    co, emp, job, app = _world()
    assert client.get("/company/settings", headers=_hdr(co, "co")).json()["data"] == {"notify_applicant_result": True}
    assert client.put("/company/settings", headers=_hdr(emp, "emp"),
                      json={"notify_applicant_result": False}).status_code == 403
    assert client.put("/company/settings", headers=_hdr(co, "co"),
                      json={"notify_applicant_result": "no"}).status_code == 422
    r = client.put("/company/settings", headers=_hdr(co, "co"), json={"notify_applicant_result": False})
    assert r.status_code == 200 and r.json()["data"]["notify_applicant_result"] is False
    _status(co, app, "hired")
    assert _notifs(emp) == [] and env.calls == []


def test_user_switch_off_blocks_the_email_only(env):
    co, emp, job, app = _world()
    r = client.put("/my/email-notifications", headers=_hdr(emp, "emp"),
                   json={"types": {"notify_application_result": False}})
    assert r.status_code == 200
    assert {t["key"]: t["enabled"] for t in r.json()["data"]["types"]}["notify_application_result"] is False
    _status(co, app, "hired")
    assert len(_notifs(emp)) == 1 and env.calls == []
    assert [tuple(x) for x in _sql("SELECT template_key, status FROM email_send_log")] == \
        [("notify_application_hired", "skipped_pref")]
