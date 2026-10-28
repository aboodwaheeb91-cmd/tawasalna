"""Task 8.6a — GET /home/feed: hidden salary + «all professions" (SYSTEMS_INDEX §12) · POST /admin/logo-sizes removed.

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), schema from the
real startup migrations:
  - a job with salary_hidden → no salary numbers / currency in the feed (even an old row that still holds them)
  - a normal job → its salary comes back
  - accepts_all_professions + salary_hidden are in every feed job
  - POST /admin/logo-sizes is gone (404)
Run: python -m pytest tests/test_home_feed_86a.py -q
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-home-feed-86a-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
USER_SECRET = "test-user-secret-86a-" + "u" * 32


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
    monkeypatch.setattr(srv, "JWT_SECRET", USER_SECRET)
    monkeypatch.setattr(auth, "get_session_state", lambda uid: {"changed": None, "sv": 0})
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    yield
    srv._rate_store.clear()


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut):
    n = uuid.uuid4().hex[:10]
    uid = int(_sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', :ut) RETURNING id", t="C" + n, n="Co " + n, e=n + "@t.test", ut=ut)[0][0])
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return uid


def _h(uid, ut):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": ut, "tw_id": "X"})}


def _job(co, hidden, all_prof=False):
    # numbers stored even when hidden — an old row from before the write rule nulled them
    return int(_sql("INSERT INTO jobs (company_id, title, description, status, expires_at, salary_min, salary_max, "
                    "currency, salary_hidden, accepts_all_professions) VALUES (:c, :t, 'd', 'active', "
                    "NOW() + INTERVAL '5 days', 700, 900, 'JOD', :h, :a) RETURNING id",
                    c=co, t="وظيفة " + uuid.uuid4().hex[:6], h=hidden, a=all_prof)[0][0])


def test_feed_never_returns_a_hidden_salary(db):
    co, emp = _user("co"), _user("emp")
    hidden_id, shown_id = _job(co, True, all_prof=True), _job(co, False)
    for f in ("opportunities", "all"):
        r = client.get(f"/home/feed?filter={f}&limit=50", headers=_h(emp, "emp"))
        assert r.status_code == 200
        jobs = {it["id"]: it for it in r.json()["items"] if it.get("type") == "opportunity"}
        assert hidden_id in jobs and shown_id in jobs, f
        hid, shown = jobs[hidden_id], jobs[shown_id]
        assert hid["salary_hidden"] is True
        assert hid["salary_min"] is None and hid["salary_max"] is None and hid["currency"] is None
        assert hid["accepts_all_professions"] is True
        assert shown["salary_hidden"] is False and shown["accepts_all_professions"] is False
        assert (float(shown["salary_min"]), float(shown["salary_max"]), shown["currency"]) == (700, 900, "JOD")


def test_admin_logo_sizes_route_removed():
    assert not any(getattr(r, "path", "") == "/admin/logo-sizes" for r in srv.app.routes)
    assert client.post("/admin/logo-sizes", json={}).status_code in (404, 405)
