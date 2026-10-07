"""
test_admin_session_security.py — PR 1.5 (admin session JWT) + PR 1.8 (session
invalidation after password change). SYSTEMS_INDEX §25 · §2a.
Real FastAPI app; DB helpers mocked.

Run: python -m pytest test_admin_session_security.py -q
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import auth
import server as srv

client = TestClient(srv.app)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_TOKEN", "a" * 40)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    monkeypatch.setattr(auth, "get_password_changed_epoch", lambda uid: None)
    yield
    srv._pwd_changed_cache.clear()


def _req(admin_token):
    r = MagicMock()
    r.headers.get = lambda k, d="": admin_token if k == "X-Admin-Token" else d
    return r


def _status(fn, *a):
    try:
        fn(*a)
        return 200
    except HTTPException as e:
        return e.status_code


# ── PR 1.5 — admin session JWT ───────────────────────────────────────────────

def test_login_returns_short_admin_jwt_not_raw_secret():
    r = client.post("/tw-ctrl-login", json={"password": "a" * 40})
    assert r.status_code == 200
    tok = r.json()["token"]
    assert tok != srv.ADMIN_TOKEN and srv.ADMIN_TOKEN not in tok
    c = srv._admin_jwt_claims(tok)
    assert c["role"] == "admin" and c["sub"] == "owner" and c["perms"] == ["*"]
    assert 0 < c["exp"] - c["iat"] <= 3600
    assert srv.check_admin(_req(tok))["sub"] == "owner"
    assert client.post("/tw-ctrl-login", json={"password": "b" * 40}).status_code == 401


def test_raw_admin_token_rejected_as_session():
    assert _status(srv.check_admin, _req("a" * 40)) == 401
    assert _status(srv.check_admin, _req("")) == 401


def test_expired_admin_jwt_rejected():
    now = int(time.time())
    expired = srv._jwt_sign({"iss": "tawasalna", "aud": "tw-admin", "sub": "owner", "role": "admin",
                             "perms": ["*"], "iat": now - 4000, "exp": now - 400},
                            srv.ADMIN_JWT_SECRET)
    assert _status(srv.check_admin, _req(expired)) == 401
    # lifetime longer than 1h is refused even when not yet expired
    long = srv._jwt_sign({"iss": "tawasalna", "aud": "tw-admin", "sub": "owner", "role": "admin",
                          "perms": ["*"], "iat": now, "exp": now + 86400}, srv.ADMIN_JWT_SECRET)
    assert _status(srv.check_admin, _req(long)) == 401


def test_user_jwt_rejected_by_admin_and_admin_jwt_rejected_as_user():
    user_tok = srv._jwt_encode({"user_id": 7, "user_type": "emp", "tw_id": "U1"})
    assert _status(srv.check_admin, _req(user_tok)) == 401
    admin_tok = srv._admin_jwt_issue()
    r = client.post("/auth/verify-token", headers={"Authorization": "Bearer " + admin_tok})
    assert r.status_code == 401
    # signed with the admin secret but a non-admin role → 403
    staff = srv._admin_jwt_issue(sub="staff:3", role="viewer", perms=[])
    assert _status(srv.check_admin, _req(staff)) == 403


def test_admin_jwt_secret_missing_or_shared_fails_closed(monkeypatch):
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "")
    assert client.post("/tw-ctrl-login", json={"password": "a" * 40}).status_code == 503
    assert _status(srv.check_admin, _req("x")) == 503
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", srv.JWT_SECRET)   # never reuse JWT_SECRET
    assert client.post("/tw-ctrl-login", json={"password": "a" * 40}).status_code == 503


def test_report_no_longer_notifies_user_1():
    src = open(os.path.join(os.path.dirname(__file__), "server.py"), encoding="utf-8").read()
    assert "create_notification(1," not in src


# ── PR 1.8 — session invalidation after password change ──────────────────────

def test_old_jwt_rejected_after_password_change_new_accepted(monkeypatch):
    stamp = {"v": None}
    calls = {"n": 0}

    def _epoch(uid):
        calls["n"] += 1
        return stamp["v"]

    def _set(uid, pw):
        stamp["v"] = int(time.time())
        return stamp["v"]

    monkeypatch.setattr(auth, "get_password_changed_epoch", _epoch)
    monkeypatch.setattr(srv, "check_user_password", lambda uid, pw: True)
    monkeypatch.setattr(srv, "set_user_password", _set)

    now = int(time.time())
    old = srv._jwt_sign({"user_id": 9, "user_type": "emp", "tw_id": "U9",
                         "iat": now - 30, "exp": now + 3600}, srv.JWT_SECRET)
    H = lambda t: {"Authorization": "Bearer " + t}
    assert client.post("/auth/verify-token", headers=H(old)).status_code == 200
    assert client.post("/auth/verify-token", headers=H(old)).status_code == 200
    assert calls["n"] == 1   # cached — no DB query per request

    r = client.put("/auth/password", headers=H(old),
                   json={"current_password": "OldPass123", "new_password": "NewPass456"})
    assert r.status_code == 200, r.text
    new = r.json()["token"]

    assert client.post("/auth/verify-token", headers=H(old)).status_code == 401
    ok = client.post("/auth/verify-token", headers=H(new))
    assert ok.status_code == 200 and ok.json()["user_id"] == 9
    assert calls["n"] == 1   # the change refreshed the cache directly
