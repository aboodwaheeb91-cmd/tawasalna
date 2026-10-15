"""Task 5.3j phase 2 — admin job control + #7 + #13 (SYSTEMS_INDEX §25e · ADMIN_ENTITY_MAP §2).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), schema from the
real startup migrations:
  - the 4 new admin endpoints answer 401 without an admin session
  - hide: reason required (422) · hidden job gone from the feed, the company page, job-detail (404) and apply ·
    the company still sees it with the reason · company notified · admin list state «hidden» · hide twice → 409 ·
    unhide → public again
  - reactivate: closed / expired → active, expires_at = now + days, reminder scheduled (#13) · active → 409 ·
    duration outside _ALLOWED_DURATIONS → 422 · archived → 409
  - extend: active → expires_at + days · paused → frozen remaining + days · closed → 409
  - #7: a paused job past its expires_at stays «paused» (Python + SQL) and resume continues the remaining time
    (+ a new reminder — #13)
  - phase 3: admin pause / resume / close (reason required) through set_job_status + company notified ·
    wrong state / archived → 409 · unarchive (not archived → 409)
  - 5.3j4 (owner decision): the company cannot reopen a closed / expired job (422, nothing changes) — the admin
    reactivates it (expires_at = now + days, reminder) · the removed company reopen button does not come back
  - 5.3j5 (owner decision): PUT /company/jobs/{id} → 403 for the company, nothing changes · pause / resume / close /
    archive still work · the removed company edit mode does not come back
  - phase 4 (owner decisions): GET /admin/jobs/{id} (job + applicants) · PUT /admin/jobs/{id} = the publish rules +
    a required reason → company notice with the reason · ONE notice per applicant per edit (without the reason) ·
    no change → 409 · GET …/delete-preview counts applicants / pipeline / appointments (kept, detached) · 401 without admin
Run: python -m pytest tests/test_admin_jobs_control.py -q
"""
import os
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-admin-jobs-ctl-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-53j2-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
PASSWORD = "p" * 40
LOGIN = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN + "/login"
USER_SECRET = "test-user-secret-53j2-" + "u" * 32


@pytest.fixture(scope="module")
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP SCHEMA public CASCADE")
    c.run("CREATE SCHEMA public")
    auth.release_conn(c)
    srv._run_startup_migrations()
    yield


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-53j2-" + "s" * 32)
    monkeypatch.setattr(srv, "JWT_SECRET", USER_SECRET)
    monkeypatch.setattr(auth, "get_session_state", lambda uid: None)
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    auth._cache_del("jobs:")
    yield
    srv._rate_store.clear()


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _admin():
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.status_code == 200
    return {"X-Admin-Token": r.json()["token"]}


def _user(ut="co"):
    n = uuid.uuid4().hex[:10]
    uid = int(_sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', :ut) RETURNING id", t="C" + n, n="Co " + n, e=n + "@t.test", ut=ut)[0][0])
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return uid


def _h(uid, ut="co"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": uid, "user_type": ut, "tw_id": "X"})}


def _job(co, status="active", expires="NOW() + INTERVAL '5 days'", closed="NULL", paused="NULL", archived="NULL"):
    return int(_sql("INSERT INTO jobs (company_id, title, description, status, expires_at, closed_at, paused_at, "
                    f"archived_at) VALUES (:c, :t, 'd', :s, {expires}, {closed}, {paused}, {archived}) RETURNING id",
                    c=co, t="وظيفة " + uuid.uuid4().hex[:6], s=status)[0][0])


def _expires(jid):
    return _sql("SELECT expires_at FROM jobs WHERE id=:j", j=jid)[0][0]


def _now():
    return _sql("SELECT NOW()::timestamp")[0][0]


def _reminders(jid):
    return _sql("SELECT COUNT(*) FROM scheduler_jobs WHERE job_type='job_expiring_soon' AND dedupe_key LIKE :k",
                k=f"job_expiring_soon:{jid}:%")[0][0]


def _close_to(a, b, minutes=5):
    return abs((a - b).total_seconds()) < minutes * 60


# ── access ──
def test_actions_need_an_admin_session(db):
    user_jwt = _h(1)["Authorization"].split(" ", 1)[1]
    for path in ("hide", "unhide", "reactivate", "extend", "status", "unarchive"):
        for h in ({}, {"X-Admin-Token": PASSWORD}, {"X-Admin-Token": user_jwt}):
            assert client.post(f"/admin/jobs/1/{path}", json={}, headers=h).status_code == 401, path


# ── hide / unhide ──
def test_hide_removes_job_from_every_public_place_and_unhide_returns_it(db):
    co, emp = _user("co"), _user("emp")
    jid = _job(co)
    h = _admin()
    def in_home_feed():
        items = client.get("/home/feed?filter=opportunities", headers=_h(emp, "emp")).json()["items"]
        return jid in [it.get("id") for it in items if it.get("type") == "opportunity"]
    assert in_home_feed()                                                                          # visible first
    assert client.post(f"/admin/jobs/{jid}/hide", json={"reason": "  "}, headers=h).status_code == 422
    assert client.post("/admin/jobs/999999/hide", json={"reason": "x"}, headers=h).status_code == 404
    r = client.post(f"/admin/jobs/{jid}/hide", json={"reason": "محتوى مخالف"}, headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["data"]["notified"] is True
    auth._cache_del("jobs:")
    assert jid not in [j["id"] for j in client.get("/jobs").json()["jobs"]]                       # feed
    assert jid not in [j["id"] for j in client.get(f"/jobs?company_id={co}").json()["jobs"]]       # company page
    assert client.get(f"/jobs/{jid}").status_code == 404                                           # job-detail
    assert not in_home_feed()                                                                      # home feed
    assert client.post(f"/jobs/{jid}/apply", json={"cover_letter": ""}, headers=_h(emp, "emp")).status_code >= 400
    own = {j["id"]: j for j in client.get("/company/jobs", headers=_h(co)).json()["jobs"]}
    assert own[jid]["admin_hidden_at"] and own[jid]["admin_hidden_reason"] == "محتوى مخالف"
    n = _sql("SELECT type, body FROM notifications WHERE user_id=:u ORDER BY id DESC LIMIT 1", u=co)[0]
    assert n[0] == "job_admin" and "محتوى مخالف" in n[1]
    lst = client.get("/admin/jobs?status=hidden", headers=h).json()["data"]
    assert [it["id"] for it in lst["items"]] == [jid] and lst["items"][0]["effective_status"] == "active"
    assert client.post(f"/admin/jobs/{jid}/hide", json={"reason": "x"}, headers=h).status_code == 409
    assert client.post(f"/admin/jobs/{jid}/unhide", headers=h).status_code == 200
    auth._cache_del("jobs:")
    assert client.get(f"/jobs/{jid}").status_code == 200
    assert jid in [j["id"] for j in client.get("/jobs").json()["jobs"]]
    assert client.post(f"/admin/jobs/{jid}/unhide", headers=h).status_code == 409


# ── reactivate ──
def test_reactivate_closed_and_expired_with_a_new_duration(db):
    co = _user()
    closed = _job(co, "closed", closed="NOW() - INTERVAL '2 days'")
    expired = _job(co, "closed", expires="NOW() - INTERVAL '50 days'", closed="NOW() - INTERVAL '40 days'")
    h = _admin()
    for jid in (closed, expired):
        r = client.post(f"/admin/jobs/{jid}/reactivate", json={"duration_days": 14}, headers=h)
        assert r.status_code == 200, r.text
        assert _close_to(_expires(jid), _now() + timedelta(days=14))
        st = _sql("SELECT status, closed_at, duration_days FROM jobs WHERE id=:j", j=jid)[0]
        assert st[0] == "active" and st[1] is None and st[2] == 14
        assert _reminders(jid) == 1                                                               # #13
    assert client.post(f"/admin/jobs/{closed}/reactivate", json={"duration_days": 7}, headers=h).status_code == 409
    other = _job(co, "closed", closed="NOW()")
    for bad in (5, 0, "abc", None):
        assert client.post(f"/admin/jobs/{other}/reactivate", json={"duration_days": bad}, headers=h).status_code == 422
    arch = _job(co, "closed", closed="NOW()", archived="NOW()")
    assert client.post(f"/admin/jobs/{arch}/reactivate", json={"duration_days": 7}, headers=h).status_code == 409


# ── extend ──
def test_extend_active_and_paused(db):
    co = _user()
    act = _job(co)
    paused = _job(co, "paused", expires="NOW() + INTERVAL '2 days'", paused="NOW() - INTERVAL '1 day'")
    closed = _job(co, "closed", closed="NOW()")
    h = _admin()
    before = _expires(act)
    assert client.post(f"/admin/jobs/{act}/extend", json={"duration_days": 7}, headers=h).status_code == 200
    assert _close_to(_expires(act), before + timedelta(days=7), 1)
    pb = _expires(paused)
    assert client.post(f"/admin/jobs/{paused}/extend", json={"duration_days": 3}, headers=h).status_code == 200
    assert _close_to(_expires(paused), pb + timedelta(days=3), 1)
    assert client.post(f"/admin/jobs/{closed}/extend", json={"duration_days": 3}, headers=h).status_code == 409


# ── #7 + #13 ──
def test_pause_freezes_the_duration_and_resume_continues_it(db):
    co = _user()
    # paused 10 days ago with 3 days left — the old rule called it «closed» and refused the resume
    jid = _job(co, "paused", expires="NOW() - INTERVAL '7 days'", paused="NOW() - INTERVAL '10 days'")
    row = _sql("SELECT status, closed_at, expires_at, paused_at, " + auth.job_eff_status_sql("j")
               + " FROM jobs j WHERE id=:j", j=jid)[0]
    assert auth._eff_status(row[0], row[1], row[2], row[3]) == "paused" and row[4] == "paused"
    r = client.patch(f"/company/jobs/{jid}/status", json={"status": "active"}, headers=_h(co))
    assert r.status_code == 200, r.text
    assert _close_to(_expires(jid), _now() + timedelta(days=3))
    auth._cache_del("jobs:")
    assert jid in [j["id"] for j in client.get("/jobs").json()["jobs"]]
    assert _reminders(jid) == 1


# ── phase 3: admin status · unarchive · company reopen ──
def _status(jid):
    return tuple(_sql("SELECT status, " + auth.job_eff_status_sql("j") + " FROM jobs j WHERE id=:j", j=jid)[0])


def _last_notice(co):
    return _sql("SELECT type, title, body FROM notifications WHERE user_id=:u ORDER BY id DESC LIMIT 1", u=co)[0]


def test_admin_pause_resume_close_use_set_job_status(db):
    co = _user()
    jid = _job(co)
    h = _admin()
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "paused"}, headers=h).status_code == 200
    assert _status(jid)[1] == "paused" and _last_notice(co)[0] == "job_admin"
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "paused"}, headers=h).status_code == 409
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "active"}, headers=h).status_code == 200
    assert _status(jid)[1] == "active"
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "closed"}, headers=h).status_code == 422   # no reason
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "deleted", "reason": "x"}, headers=h).status_code == 422
    r = client.post(f"/admin/jobs/{jid}/status", json={"status": "closed", "reason": "إعلان مكرر"}, headers=h)
    assert r.status_code == 200 and _status(jid) == ("closed", "closed")
    assert "إعلان مكرر" in _last_notice(co)[2]
    assert client.post(f"/admin/jobs/{jid}/status", json={"status": "active"}, headers=h).status_code == 409    # → /reactivate
    assert client.post("/admin/jobs/999999/status", json={"status": "paused"}, headers=h).status_code == 404
    arch = _job(co, archived="NOW()")
    assert client.post(f"/admin/jobs/{arch}/status", json={"status": "paused"}, headers=h).status_code == 409


def test_admin_unarchive(db):
    co = _user()
    arch, live = _job(co, archived="NOW()"), _job(co)
    h = _admin()
    assert client.post(f"/admin/jobs/{arch}/unarchive", headers=h).status_code == 200
    assert _sql("SELECT archived_at FROM jobs WHERE id=:j", j=arch)[0][0] is None
    auth._cache_del("jobs:")
    assert client.get(f"/jobs/{arch}").status_code == 200                       # active again → public
    assert client.post(f"/admin/jobs/{live}/unarchive", headers=h).status_code == 409


def test_only_the_admin_reopens_a_closed_job(db):
    """Owner decision 5.3j4: the company cannot reopen its closed job (422, as before 5.3j3) — the admin can."""
    co = _user()
    closed = _job(co, "closed", closed="NOW() - INTERVAL '3 days'")
    expired = _job(co, "closed", expires="NOW() - INTERVAL '50 days'", closed="NOW() - INTERVAL '40 days'")
    url = lambda j: f"/company/jobs/{j}/status"
    for body in ({"status": "active"}, {"status": "active", "duration_days": 14}):
        assert client.patch(url(closed), json=body, headers=_h(co)).status_code == 422
        assert client.patch(url(expired), json=body, headers=_h(co)).status_code == 422
    assert _status(closed) == ("closed", "closed") and _status(expired)[1] == "expired"   # nothing changed
    h = _admin()
    assert client.post(f"/admin/jobs/{closed}/status", json={"status": "active"}, headers=h).status_code == 409
    r = client.post(f"/admin/jobs/{closed}/reactivate", json={"duration_days": 14}, headers=h)
    assert r.status_code == 200, r.text
    assert _status(closed) == ("active", "active")
    assert _close_to(_expires(closed), _now() + timedelta(days=14)) and _reminders(closed) == 1


def test_company_reopen_button_is_gone():
    """The removed company reopen flow does not come back (function / button class absent)."""
    src = open("static/company/company.jobs.js", encoding="utf-8").read() \
        + open("static/company/company.render.js", encoding="utf-8").read()
    assert "function reopenJob" not in src and "owner-reopen-btn" not in src


# ── 5.3j5 (owner decision): a published job cannot be edited by the company ──
def test_company_cannot_edit_a_published_job(db):
    co, emp = _user(), _user("emp")
    jid = _job(co)
    before = tuple(_sql("SELECT title, description, expires_at, duration_days FROM jobs WHERE id=:j", j=jid)[0])
    body = {"title": "عنوان جديد", "description": "وصف جديد", "duration_days": 30}
    r = client.put(f"/company/jobs/{jid}", json=body, headers=_h(co))
    assert r.status_code == 403 and "لا يمكن تعديل الوظيفة بعد نشرها" in r.text
    assert client.put(f"/company/jobs/{jid}", json=body, headers=_h(emp, "emp")).status_code == 403
    assert client.put(f"/company/jobs/{jid}", json=body).status_code in (401, 403)
    after = tuple(_sql("SELECT title, description, expires_at, duration_days FROM jobs WHERE id=:j", j=jid)[0])
    assert after == before                                                                    # nothing changed


def test_company_still_pauses_closes_and_archives(db):
    co = _user()
    a, b = _job(co), _job(co)
    url = lambda j: f"/company/jobs/{j}/status"
    assert client.patch(url(a), json={"status": "paused"}, headers=_h(co)).status_code == 200
    assert _status(a)[1] == "paused"
    assert client.patch(url(a), json={"status": "active"}, headers=_h(co)).status_code == 200
    assert client.patch(url(a), json={"status": "closed"}, headers=_h(co)).status_code == 200
    assert _status(a)[1] == "closed"
    r = client.delete(f"/company/jobs/{b}", headers=_h(co))
    assert r.status_code == 200 and r.json()["archived"] is True


def test_company_job_edit_mode_is_gone():
    """The removed company edit flow does not come back (functions absent)."""
    src = open("static/company/company.jobs.js", encoding="utf-8").read()
    assert "function openEditJob" not in src and "function hydrateEditJobForm" not in src


# ── phase 4 (owner decisions): admin job page — detail · edit (reason + notices) · delete preview ──
def _apply(jid, uid):
    return int(_sql("INSERT INTO job_applications (job_id, user_id) VALUES (:j, :u) RETURNING id", j=jid, u=uid)[0][0])


def _notices(uid, type_):
    return _sql("SELECT title, body FROM notifications WHERE user_id=:u AND type=:t ORDER BY id", u=uid, t=type_)


def test_phase4_endpoints_need_an_admin_session(db):
    user_jwt = _h(1)["Authorization"].split(" ", 1)[1]
    for h in ({}, {"X-Admin-Token": PASSWORD}, {"X-Admin-Token": user_jwt}):
        assert client.get("/admin/jobs/1", headers=h).status_code == 401
        assert client.put("/admin/jobs/1", json={"title": "x", "reason": "r"}, headers=h).status_code == 401
        assert client.get("/admin/jobs/1/delete-preview", headers=h).status_code == 401


def test_admin_job_detail_with_applicants(db):
    co, e1, e2 = _user(), _user("emp"), _user("emp")
    jid = _job(co)
    _apply(jid, e1), _apply(jid, e2)
    h = _admin()
    d = client.get(f"/admin/jobs/{jid}", headers=h).json()["data"]
    assert d["job"]["id"] == jid and d["job"]["admin_status"] == "active" and d["job"]["company_id"] == co
    assert sorted(a["user_id"] for a in d["applicants"]) == sorted([e1, e2]) and d["durations"] == [3, 7, 14, 30]
    assert "password_hash" not in str(d)
    assert client.get("/admin/jobs/999999", headers=h).status_code == 404


def test_admin_edit_reason_company_notice_and_one_notice_per_applicant_per_edit(db):
    co, e1, e2 = _user(), _user("emp"), _user("emp")
    jid = _job(co)
    _apply(jid, e1), _apply(jid, e2)
    h = _admin()
    base = {"title": "مطوّر واجهات", "description": "d", "job_type": "دوام كامل", "work_mode": "عن بُعد"}
    url = f"/admin/jobs/{jid}"
    assert client.put(url, json=base, headers=h).status_code == 422                                   # no reason
    r = client.put(url, json=dict(base, reason="تصحيح العنوان"), headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "title" in d["changed"] and d["notified"] is True and d["applicants_notified"] == 2
    row = _sql("SELECT title, work_mode FROM jobs WHERE id=:j", j=jid)[0]
    assert list(row) == ["مطوّر واجهات", "عن بُعد"]
    co_n = _notices(co, "job_admin")
    assert co_n and "تصحيح العنوان" in co_n[-1][1]                                                   # reason → company
    for e in (e1, e2):
        n = _notices(e, "job_updated")
        assert len(n) == 1 and "تصحيح العنوان" not in n[0][1]                                         # no internal reason
    assert client.put(url, json=dict(base, reason="مرة تانية"), headers=h).status_code == 409           # nothing changed
    assert len(_notices(e1, "job_updated")) == 1
    r = client.put(url, json=dict(base, title="مطوّر واجهات أول", reason="تعديل تاني"), headers=h)
    assert r.status_code == 200 and len(_notices(e1, "job_updated")) == 2                              # one per edit
    # the publish rules (same function): an unknown accepted profession → 422, nothing written
    bad = client.put(url, json=dict(base, title="X", accepted_profession_ids=[987654], reason="r"), headers=h)
    assert bad.status_code == 422
    assert _sql("SELECT title FROM jobs WHERE id=:j", j=jid)[0][0] == "مطوّر واجهات أول"
    assert client.put("/admin/jobs/999999", json=dict(base, reason="r"), headers=h).status_code == 404
    assert client.put(url, json=dict(base, title="Y", reason="r"), headers=_h(co)).status_code == 401  # company ≠ admin


def test_delete_preview_counts_then_delete(db):
    co, e1, e2 = _user(), _user("emp"), _user("emp")
    jid = _job(co)
    a1 = _apply(jid, e1)
    _apply(jid, e2)
    entry = int(_sql("INSERT INTO job_pipeline_entries (company_id, candidate_id, job_id, application_id, stage, source) "
                     "VALUES (:c, :e, :j, :a, 'new', 'application') RETURNING id", c=co, e=e1, j=jid, a=a1)[0][0])
    _sql("INSERT INTO appointments (company_id, applicant_id, created_by, job_id, pipeline_entry_id) "
         "VALUES (:c, :e, :c, :j, :p)", c=co, e=e1, j=jid, p=entry)
    h = _admin()
    p = client.get(f"/admin/jobs/{jid}/delete-preview", headers=h).json()["data"]
    assert (p["applicants"], p["pipeline_entries"], p["appointments"]) == (2, 1, 1)
    assert client.get("/admin/jobs/999999/delete-preview", headers=h).status_code == 404
    r = client.delete(f"/admin/jobs/{jid}", headers=h)
    assert r.status_code == 200 and r.json()["removed"] == {"applicants": 2, "pipeline_entries": 1}
    assert _sql("SELECT COUNT(*) FROM appointments WHERE company_id=:c AND job_id IS NULL", c=co)[0][0] == 1   # kept, detached
