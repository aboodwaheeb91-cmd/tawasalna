"""
test_follow_system.py — PR 3.5 Follow System (one table: profile_follows) — focused.

  Real PostgreSQL — needs TW_TEST_DB_URL=postgresql://user:pass@host:port/db (a throwaway
  database; skipped without it):
    1. A fresh database has no company_follows table (PR 3.9b: legacy table + its copy
       migration removed from the code — the one follow table is profile_follows).
    2. Following a company from the company page shows it in the follower's «أتابعهم» list,
       and every counter (company page · followers list · follow state) says the same.
    3. No self-follow (400) · guest rejected (401) · unknown account (404).
    4. A company / edu account can follow too (one rule for every type).
    5. The old /company/follow + /company/{id}/followers aliases are gone (PR 3.9).

Run: python -m pytest tests/test_follow_system.py -q
"""
import os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    status = srv._run_startup_migrations()
    assert "company_follows_to_profile_follows" not in status
    assert all(v == "ok" for v in status.values()), status
    yield


def _user(conn, ut="emp"):
    n = uuid.uuid4().hex[:10]
    uid = int(conn.run(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, 'x', :ut) RETURNING id",
        t="T" + n, n="User " + n, e=n + "@t.test", ut=ut)[0][0])
    conn.run("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return uid


def _h(uid, ut="emp"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"user_id": uid, "user_type": ut, "tw_id": "X"})}


def _pf(conn, follower, followed):
    return conn.run("SELECT COUNT(*) FROM profile_follows WHERE follower_id=:a AND followed_id=:b",
                    a=follower, b=followed)[0][0]


def test_fresh_db_has_no_legacy_company_follows_table(db):
    with auth.db_conn() as conn:
        assert conn.run("SELECT to_regclass('public.company_follows') IS NULL")[0][0] is True
        assert conn.run("SELECT to_regclass('public.profile_follows') IS NOT NULL")[0][0] is True


def test_company_page_follow_shows_in_following_list_and_counts_match(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
    r = client.post(f"/profile/{co}/follow", headers=_h(emp))          # company page button
    assert r.status_code == 200 and r.json()["is_following"] is True and r.json()["followers_count"] == 1

    mine = client.get(f"/profile/{emp}/following", headers=_h(emp)).json()   # «أتابعهم»
    assert [i["id"] for i in mine["items"]] == [co] and mine["counts"]["co"] == 1

    page = client.get(f"/company/profile/{co}", headers=_h(emp)).json()
    state = client.get(f"/profile/{co}/follow", headers=_h(emp)).json()["data"]
    fl = client.get(f"/profile/{co}/followers").json()
    assert page["stats"]["followers_count"] == state["followers_count"] == fl["counts"]["all"] == 1
    assert page["permissions"]["is_following"] is True and state["is_following"] is True

    r = client.delete(f"/profile/{co}/follow", headers=_h(emp))
    assert r.json()["is_following"] is False and r.json()["followers_count"] == 0
    assert client.get(f"/profile/{emp}/following", headers=_h(emp)).json()["items"] == []


def test_no_self_follow_guest_rejected_unknown_404(db):
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
    assert client.post(f"/profile/{emp}/follow", headers=_h(emp)).status_code == 400
    assert client.post(f"/profile/{co}/follow", headers=_h(co, "co")).status_code == 400
    assert client.post(f"/profile/{co}/follow").status_code == 401
    assert client.post("/profile/999999999/follow", headers=_h(emp)).status_code == 404
    with auth.db_conn() as conn:
        assert _pf(conn, emp, emp) == 0 and _pf(conn, co, co) == 0


def test_every_account_type_can_follow(db):
    with auth.db_conn() as conn:
        co, edu, emp = _user(conn, "co"), _user(conn, "edu"), _user(conn)
    assert client.post(f"/profile/{emp}/follow", headers=_h(co, "co")).status_code == 200
    assert client.post(f"/profile/{co}/follow", headers=_h(edu, "edu")).status_code == 200
    with auth.db_conn() as conn:
        assert _pf(conn, co, emp) == 1 and _pf(conn, edu, co) == 1


def test_company_aliases_removed(db):
    """PR 3.9 — /company/follow/{id} + /company/{id}/followers deleted; /profile/{id}/* only."""
    with auth.db_conn() as conn:
        co, emp = _user(conn, "co"), _user(conn)
    assert client.post(f"/company/follow/{co}", headers=_h(emp)).status_code in (404, 405)
    assert client.delete(f"/company/follow/{co}", headers=_h(emp)).status_code in (404, 405)
    assert client.get(f"/company/{co}/followers").status_code in (404, 405)
    r = client.post(f"/profile/{co}/follow", headers=_h(emp))
    assert r.status_code == 200 and r.json()["is_following"] is True
    with auth.db_conn() as conn:
        assert _pf(conn, emp, co) == 1
