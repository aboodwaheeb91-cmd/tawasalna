"""
test_pr2b_flow_fixes.py — PR 2B focused checks.

  A. Startup migration policy (critical / optional) + /health status — no DB.
  B. PUT /admin/profile/{id} rejects a user JWT — no DB.
  C. Unique-index migration succeeds with duplicate rows (keeps the oldest) — real PostgreSQL.
  D. Appointment status transitions (complete / close from missed + expired, missed timing,
     latest-N messages) — real PostgreSQL.
  E. promote_application_to_shortlist never moves a candidate backwards — real PostgreSQL.
  F. PUT /admin/profile/{id} with an admin JWT uses the PUT /profile rules — real PostgreSQL.

C–F need TW_TEST_DB_URL=postgresql://user:pass@host:port/db (a throwaway database —
the tests create their own rows). Without it they are skipped.

Run: python -m pytest test_pr2b_flow_fixes.py -q
"""
import os, sys, uuid
from datetime import datetime, timedelta, timezone

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
needs_db = pytest.mark.skipif(not _DB_URL, reason="TW_TEST_DB_URL not set")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)
    monkeypatch.setattr(auth, "get_password_changed_epoch", lambda uid: None)
    srv._pwd_changed_cache.clear()
    yield


# ── A. Startup migration policy ──────────────────────────────────────────────

def test_optional_failure_is_recorded_and_startup_continues(monkeypatch):
    monkeypatch.setattr(srv, "_MIGRATION_STATUS", {})
    ran = []
    def boom():
        raise RuntimeError("secret detail must not leak")
    status = srv._run_startup_migrations([
        ("opt_a", lambda: ran.append("a"), False),
        ("opt_b", boom, False),
        ("crit_c", lambda: ran.append("c"), True),
    ])
    assert ran == ["a", "c"]
    assert status == {"opt_a": "ok", "opt_b": "failed", "crit_c": "ok"}
    monkeypatch.setattr(srv, "db_conn", None)  # /health DB check fails → still answers
    body = client.get("/health").json()
    assert body["migrations"] == {"opt_a": "ok", "opt_b": "failed", "crit_c": "ok"}
    assert body["status"] == "degraded"
    assert "secret detail" not in str(body)


def test_critical_failure_stops_startup(monkeypatch):
    monkeypatch.setattr(srv, "_MIGRATION_STATUS", {})
    def boom():
        raise RuntimeError("x")
    with pytest.raises(RuntimeError, match="crit_x"):
        srv._run_startup_migrations([("crit_x", boom, True), ("never", lambda: None, False)])
    assert srv._MIGRATION_STATUS == {"crit_x": "failed"}


def test_registry_classification():
    reg = {n: c for n, _, c in srv._startup_migrations()}
    assert reg["init_db"] is True and reg["appointments"] is True
    assert reg["user_unique_indexes"] is False and reg["feed_indexes"] is False


# ── B. Admin profile endpoint rejects a user JWT ─────────────────────────────

def test_admin_profile_rejects_user_jwt():
    user_tok = srv._jwt_encode({"user_id": 7, "user_type": "co", "tw_id": "C1"})
    r1 = client.put("/admin/profile/7", json={"headline": "x"},
                    headers={"X-Admin-Token": user_tok})
    r2 = client.put("/admin/profile/7", json={"headline": "x"},
                    headers={"Authorization": "Bearer " + user_tok})
    assert r1.status_code == 401 and r2.status_code == 401


# ── DB fixtures (C–F) ────────────────────────────────────────────────────────

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


def _appt(conn, co, emp, status, sched, end_at=None, deadline=None):
    aid = int(conn.run(
        "INSERT INTO appointments (company_id, applicant_id, created_by, status, mode, "
        "scheduled_at, end_at, response_deadline_at, online_url) "
        "VALUES (:c, :e, :c, :s, 'online', :sch, :end, :dl, 'https://x.test') RETURNING id",
        c=co, e=emp, s=status, sch=sched, end=end_at, dl=deadline)[0][0])
    for uid, role in ((co, "company"), (emp, "applicant")):
        conn.run("INSERT INTO appointment_participants (appointment_id, user_id, role, can_message, can_decide) "
                 "VALUES (:a, :u, :r, TRUE, TRUE)", a=aid, u=uid, r=role)
    return aid


def _now():
    return datetime.now(timezone.utc)


# ── C. Unique-index migration with duplicates ────────────────────────────────

@needs_db
def test_unique_index_migration_dedupes_and_keeps_oldest(db):
    with auth.db_conn() as conn:
        for _t, _c, idx in auth._USER_UNIQUE_INDEXES:
            conn.run(f"DROP INDEX IF EXISTS {idx}")
        uid = _user(conn)
        first = int(conn.run("INSERT INTO user_skills (user_id, skill) VALUES (:u, 'SQL') RETURNING id", u=uid)[0][0])
        conn.run("INSERT INTO user_skills (user_id, skill) VALUES (:u, 'SQL'), (:u, 'SQL'), (:u, 'Go')", u=uid)
        conn.run("INSERT INTO user_langs (user_id, language) VALUES (:u, 'ar'), (:u, 'ar')", u=uid)
        conn.run("INSERT INTO user_links (user_id, link_type, url) VALUES (:u, 'gh', 'https://a'), (:u, 'gh', 'https://b')", u=uid)
    auth._migrate_user_unique_indexes()
    auth._migrate_user_unique_indexes()   # idempotent
    with auth.db_conn() as conn:
        assert conn.run("SELECT id FROM user_skills WHERE user_id=:u AND skill='SQL'", u=uid) == [[first]]
        assert conn.run("SELECT COUNT(*) FROM user_langs WHERE user_id=:u", u=uid)[0][0] == 1
        assert conn.run("SELECT url FROM user_links WHERE user_id=:u", u=uid) == [["https://a"]]
        idx = {r[0] for r in conn.run("SELECT indexname FROM pg_indexes WHERE indexname LIKE 'user_%_unique_uq'")}
        assert idx == {"user_skills_unique_uq", "user_langs_unique_uq", "user_links_unique_uq"}
        # the POST /skills upsert now works
        conn.run("INSERT INTO user_skills (user_id, skill, level) VALUES (:u, 'SQL', 'pro') "
                 "ON CONFLICT (user_id, skill) DO UPDATE SET level=EXCLUDED.level", u=uid)


# ── D. Appointment transitions ───────────────────────────────────────────────

@needs_db
def test_complete_and_close_from_missed_and_expired(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
        past = _now() - timedelta(hours=3)
        a_missed = _appt(conn, co, emp, "missed", past)
        a_missed2 = _appt(conn, co, emp, "missed", past)
        a_expired = _appt(conn, co, emp, "expired", _now() + timedelta(days=2))
        a_computed = _appt(conn, co, emp, "pending_response", _now() + timedelta(days=2),
                           deadline=_now() - timedelta(hours=1))
        a_confirmed = _appt(conn, co, emp, "confirmed", past)
    # missed → messages still allowed (not terminal)
    assert auth.create_appointment_message(a_missed, emp, "مرحبا")["body"] == "مرحبا"
    assert auth.complete_appointment(a_missed, co)["status"] == "completed"
    assert auth.close_appointment(a_missed, co)["status"] == "closed"
    assert auth.close_appointment(a_missed2, co)["status"] == "closed"
    assert auth.close_appointment(a_expired, co)["status"] == "closed"
    assert auth.close_appointment(a_computed, co)["status"] == "closed"
    with pytest.raises(ValueError):
        auth.close_appointment(a_confirmed, co)          # still confirmed → complete first
    with pytest.raises(PermissionError):
        auth.complete_appointment(a_confirmed, emp)      # company only
    with pytest.raises(ValueError):
        auth.create_appointment_message(a_expired, emp, "x")   # closed room


@needs_db
def test_missed_waits_for_end_of_appointment(db):
    sched = _now() - timedelta(minutes=30)
    assert auth._appt_missed_at({"scheduled_at": sched.isoformat()}) == sched + timedelta(hours=2)
    end = _now() + timedelta(minutes=30)
    assert auth._appt_missed_at({"scheduled_at": sched.isoformat(), "end_at": end.isoformat()}) \
        == end + timedelta(minutes=15)
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
        aid = _appt(conn, co, emp, "confirmed", sched)
    ts = int(sched.timestamp())
    # a job queued the old way (scheduled_at + 15 min) fires 30 min in → no missed, re-queued
    auth._handle_appointment_missed({"payload": {"appointment_id": aid, "scheduled_at_ts": ts}})
    with auth.db_conn() as conn:
        assert conn.run("SELECT status FROM appointments WHERE id=:a", a=aid)[0][0] == "confirmed"
        jobs = conn.run("SELECT run_at FROM scheduler_jobs WHERE job_type='appointment_missed' "
                        "AND dedupe_key LIKE :k", k=f"appointment_missed:{aid}:%")
        assert len(jobs) == 1
        conn.run("UPDATE appointments SET scheduled_at=:s WHERE id=:a",
                 s=_now() - timedelta(hours=3), a=aid)
        # same truncation as accept_appointment / the handler (int(timestamp()), not SQL rounding)
        ts2 = auth._ts_from_db_val(conn.run("SELECT scheduled_at FROM appointments WHERE id=:a", a=aid)[0][0])
    auth._handle_appointment_missed({"payload": {"appointment_id": aid, "scheduled_at_ts": ts2}})
    with auth.db_conn() as conn:
        assert conn.run("SELECT status FROM appointments WHERE id=:a", a=aid)[0][0] == "missed"


@needs_db
def test_room_messages_return_latest_page(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
        aid = _appt(conn, co, emp, "confirmed", _now() + timedelta(days=1))
        for i in range(60):
            conn.run("INSERT INTO appointment_messages (appointment_id, sender_id, body, created_at) "
                     "VALUES (:a, :u, :b, NOW() + make_interval(secs => :i))", a=aid, u=co, b=f"m{i}", i=i)
    page = auth.get_appointment_messages(aid, emp)
    assert [m["body"] for m in page] == [f"m{i}" for i in range(10, 60)]
    older = auth.get_appointment_messages(aid, emp, before_id=page[0]["id"])
    assert [m["body"] for m in older] == [f"m{i}" for i in range(10)]


# ── E. Pipeline: no moving backwards ─────────────────────────────────────────

def _job_app(conn, co, emp, app_status="pending"):
    jid = int(conn.run("INSERT INTO jobs (company_id, title, description) VALUES (:c, 'J', 'd') RETURNING id", c=co)[0][0])
    aid = int(conn.run("INSERT INTO job_applications (job_id, user_id, status) VALUES (:j, :u, :s) RETURNING id",
                       j=jid, u=emp, s=app_status)[0][0])
    return jid, aid


@needs_db
def test_promote_never_moves_backwards(db):
    with auth.db_conn() as conn:
        co, emp1, emp2, emp3 = _user(conn, "co"), _user(conn), _user(conn), _user(conn)
        j1, a1 = _job_app(conn, co, emp1, "accepted")
        conn.run("INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
                 "VALUES (:c, :u, :j, 'interview')", c=co, u=emp1, j=j1)
        conn.run("INSERT INTO job_pipeline_entries (company_id, candidate_id, job_id, application_id, stage, source) "
                 "VALUES (:c, :u, :j, :a, 'interview', 'application')", c=co, u=emp1, j=j1, a=a1)
        j2, a2 = _job_app(conn, co, emp2, "rejected")
        j3, a3 = _job_app(conn, co, emp3, "pending")

    r1 = auth.promote_application_to_shortlist(a1, co)
    assert r1["candidate"]["action"] == "kept_higher" and r1["candidate_status"] == "interview"
    r2 = auth.promote_application_to_shortlist(a2, co)
    assert r2["candidate"]["action"] == "rejected_noop" and r2["message"]
    r3 = auth.promote_application_to_shortlist(a3, co)
    assert r3["candidate"]["action"] == "promoted" and r3["candidate_status"] == "shortlisted"
    assert auth.promote_application_to_shortlist(a3, co)["candidate"]["action"] == "unchanged"
    with auth.db_conn() as conn:
        assert conn.run("SELECT candidate_status FROM company_candidate_job_refs WHERE job_id=:j", j=j1)[0][0] == "interview"
        assert conn.run("SELECT stage FROM job_pipeline_entries WHERE job_id=:j", j=j1)[0][0] == "interview"
        assert conn.run("SELECT status FROM job_applications WHERE id=:a", a=a2)[0][0] == "rejected"
        assert conn.run("SELECT COUNT(*) FROM company_candidate_job_refs WHERE job_id=:j", j=j2)[0][0] == 0


# ── F. Admin profile edit — same rules as PUT /profile ───────────────────────

@needs_db
def test_admin_profile_edit_uses_profile_rules(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
    h = {"X-Admin-Token": srv._admin_jwt_issue()}
    r = client.put(f"/admin/profile/{co}", json={"headline": "عنوان جديد", "full_name": "شركة جديدة"}, headers=h)
    assert r.status_code == 200, r.text
    with auth.db_conn() as conn:
        assert conn.run("SELECT full_name FROM users WHERE id=:u", u=co)[0][0] == "شركة جديدة"
    r = client.put(f"/admin/profile/{emp}", json={"full_name": "اسم"}, headers=h)
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "emp_name_mutation_forbidden"
    assert client.put("/admin/profile/999999999", json={"bio": "x"}, headers=h).status_code == 404
