"""PR 1.2 — settings account operations: PUT /auth/password + account delete (closed — always 403, task 5.0e).

Run: python -m pytest tests/test_account_security.py -q
DB helpers (check_user_password / set_user_password / get_conn) are monkeypatched — no database.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-account-sec-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)

import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)
UID = 4242
CURRENT = "old-secret-1"


def _auth(uid=UID):
    return {"Authorization": "Bearer " + server._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": "U1"})}


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    state = {"pw": CURRENT, "deleted": [], "set": []}
    server._pwd_changed_cache.clear()   # a password change in an earlier test bumped sv in the cache

    def check(uid, pw):
        return None if uid != UID else (bool(pw) and pw == state["pw"])

    class _Conn:
        def run(self, sql, **kw):
            state["deleted"].append((sql, kw))

    monkeypatch.setattr(server, "check_user_password", check)
    monkeypatch.setattr(server, "set_user_password", lambda uid, pw: state["set"].append((uid, pw)) or {"changed": 0, "sv": 1})
    monkeypatch.setattr(server, "get_conn", lambda: _Conn())
    monkeypatch.setattr(server, "release_conn", lambda c: None)
    monkeypatch.setattr(server, "_cache_del", lambda k: None)
    server._rate_store.clear()
    return state


def _field(r):
    return r.json()["errors"][0]["field"], r.json()["errors"][0]["code"]


# ── PUT /auth/password ──
def test_password_requires_jwt(fake_db):
    r = client.put("/auth/password", json={"current_password": CURRENT, "new_password": "new-secret-2"})
    assert r.status_code == 401 and fake_db["set"] == []


def test_password_wrong_current(fake_db):
    r = client.put("/auth/password", headers=_auth(),
                   json={"current_password": "nope", "new_password": "new-secret-2"})
    assert r.status_code == 422 and _field(r) == ("current_password", "wrong_password")
    assert r.json()["error"] == "كلمة المرور الحالية غير صحيحة" and fake_db["set"] == []


def test_password_weak_new_uses_register_rule(fake_db):
    r = client.put("/auth/password", headers=_auth(), json={"current_password": CURRENT, "new_password": "12345"})
    assert r.status_code == 422 and _field(r) == ("new_password", "weak_password")
    assert r.json()["error"] == server._password_policy_error("12345") and fake_db["set"] == []


def test_password_same_as_current(fake_db):
    r = client.put("/auth/password", headers=_auth(), json={"current_password": CURRENT, "new_password": CURRENT})
    assert r.status_code == 422 and _field(r) == ("new_password", "same_password") and fake_db["set"] == []


def test_password_success(fake_db):
    r = client.put("/auth/password", headers=_auth(),
                   json={"current_password": CURRENT, "new_password": "new-secret-2"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert fake_db["set"] == [(UID, "new-secret-2")]


def test_password_endpoint_rate_limited(fake_db, monkeypatch):
    monkeypatch.setattr(server, "_RATE_LIMIT", 2)
    body = {"current_password": "nope", "new_password": "new-secret-2"}
    codes = [client.put("/auth/password", headers=_auth(), json=body).status_code for _ in range(3)]
    assert codes == [422, 422, 429]


def test_register_rule_is_shared():
    assert server._password_policy_error("123456") is None
    assert server._password_policy_error("12345") == "كلمة المرور يجب أن تكون 6 أحرف على الأقل"


# ── DELETE /auth/user/{id}/delete — closed until soft delete (task 5.0e · ADMIN_ENTITY_MAP §1) ──
def test_delete_is_closed_even_with_right_password(fake_db, monkeypatch):
    def _no_db():
        raise AssertionError("the closed delete path must not touch the database")
    monkeypatch.setattr(server, "get_conn", _no_db)
    for body in ({"password": CURRENT}, {"password": "nope"}, None):
        r = client.request("DELETE", f"/auth/user/{UID}/delete", headers=_auth(), json=body)
        assert r.status_code == 403 and r.json()["error"] == "حذف الحساب غير متاح حالياً"
    assert fake_db["deleted"] == []


def test_delete_requires_jwt(fake_db):
    assert client.request("DELETE", f"/auth/user/{UID}/delete", json={"password": CURRENT}).status_code == 401
    r = client.request("DELETE", f"/auth/user/{UID}/delete", headers=_auth(UID + 1), json={"password": CURRENT})
    assert r.status_code == 403 and fake_db["deleted"] == []
