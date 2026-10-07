"""
test_schedule_interview.py — PR 3.10 Schedule Interview System (focused).

  Backend (real PostgreSQL — needs TW_TEST_DB_URL=postgresql://user:pass@host:port/db,
  a throwaway database; skipped without it):
    1. candidate_id + job_id with no pipeline entry → added to the job's pipeline
       (shortlisted + promoted_at, application accepted) in the same transaction, then the
       appointment; GET /api/schedule/open then returns it.
    2. Rejected on that job → 409 candidate_rejected, nothing written.
    3. Another company's job → 403.
    4. Non-emp person → 400.
    5. Inactive (paused) job for a new link → 409 job_not_active.
  Frontend (node vm — real tw-schedule.js): test_schedule_interview_runtime.js.

Run: python -m pytest test_schedule_interview.py -q
"""
import os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(auth, "get_password_changed_epoch", lambda uid: None)
    srv._pwd_changed_cache.clear()
    yield


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


def _user(conn, ut="emp"):
    n = uuid.uuid4().hex[:10]
    uid = int(conn.run(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, 'x', :ut) RETURNING id",
        t="T" + n, n="User " + n, e=n + "@t.test", ut=ut)[0][0])
    conn.run("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return uid


def _job(conn, co, status="active"):
    return int(conn.run(
        "INSERT INTO jobs (company_id, title, description, status) VALUES (:c, 'J', 'd', :s) RETURNING id",
        c=co, s=status)[0][0])


def _h(uid, ut="co"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": uid, "user_type": ut, "tw_id": "X"})}


def _create(co, cand, job):
    return client.post("/api/appointments", headers=_h(co),
                       json={"candidate_id": cand, "job_id": job, "appointment_type": "interview",
                             "mode": "online", "online_url": "https://meet.test/x"})


def test_auto_add_to_pipeline_then_open(db):
    with auth.db_conn() as conn:
        co, emp, emp2 = _user(conn, "co"), _user(conn), _user(conn)
        j = _job(conn, co)
        app_id = int(conn.run("INSERT INTO job_applications (job_id, user_id, status) "
                              "VALUES (:j, :u, 'pending') RETURNING id", j=j, u=emp)[0][0])
    # applicant without a pipeline entry + a person with no link at all (Talent Bank style)
    for cand in (emp, emp2):
        r = _create(co, cand, j)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True and r.json()["data"]["status"] == "draft"
    with auth.db_conn() as conn:
        rows = conn.run("SELECT candidate_id, stage, source, application_id, promoted_at IS NOT NULL "
                        "FROM job_pipeline_entries WHERE job_id = :j ORDER BY candidate_id", j=j)
        got = {int(r[0]): r[1:] for r in rows}
        assert got[emp] == ["shortlisted", "application", app_id, True]
        assert got[emp2] == ["shortlisted", "company_add", None, True]
        assert conn.run("SELECT status FROM job_applications WHERE id=:a", a=app_id)[0][0] == "accepted"
    # second create on the same job → structured 409
    r = _create(co, emp, j)
    assert r.status_code == 409 and r.json()["error"]["code"] == "appointment_exists"
    # open lookup (for «فتح الموعد») — by person, and by person + job
    r = client.get(f"/api/schedule/open?candidate_ids={emp},{emp2}", headers=_h(co))
    assert r.status_code == 200 and r.json()["data"][str(emp)]["job_id"] == j
    r = client.get(f"/api/schedule/open?candidate_ids={emp}&job_id={j + 999}", headers=_h(co))
    assert r.json()["data"][str(emp)] is None
    # jobs picker + people search (co only)
    assert {"id": j, "title": "J"} in client.get("/api/schedule/jobs", headers=_h(co)).json()["data"]
    people = client.get("/api/schedule/people?q=User", headers=_h(co)).json()["data"]
    assert {p["id"] for p in people} >= {emp, emp2}
    assert client.get("/api/schedule/jobs", headers=_h(emp, "emp")).status_code == 403


def test_rejected_on_job_is_refused(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
        j = _job(conn, co)
        conn.run("INSERT INTO job_applications (job_id, user_id, status) VALUES (:j, :u, 'rejected')", j=j, u=emp)
    r = _create(co, emp, j)
    assert r.status_code == 409 and r.json()["error"]["code"] == "candidate_rejected"
    assert "غير مناسب" in r.json()["error"]["message"]
    with auth.db_conn() as conn:
        assert conn.run("SELECT COUNT(*) FROM job_pipeline_entries WHERE job_id=:j", j=j)[0][0] == 0
        assert conn.run("SELECT COUNT(*) FROM appointments WHERE job_id=:j", j=j)[0][0] == 0


def test_other_company_job_and_non_emp_and_inactive(db):
    with auth.db_conn() as conn:
        co, co2, emp, edu = _user(conn, "co"), _user(conn, "co"), _user(conn), _user(conn, "edu")
        j_other = _job(conn, co2)
        j_own = _job(conn, co)
        j_paused = _job(conn, co, "paused")
    assert _create(co, emp, j_other).status_code == 403
    r = _create(co, edu, j_own)
    assert r.status_code == 400 and r.json()["ok"] is False
    r = _create(co, emp, j_paused)
    assert r.status_code == 409 and r.json()["error"]["code"] == "job_not_active"
    with auth.db_conn() as conn:
        assert conn.run("SELECT COUNT(*) FROM job_pipeline_entries WHERE job_id IN (:a, :b, :c)",
                        a=j_other, b=j_own, c=j_paused)[0][0] == 0
