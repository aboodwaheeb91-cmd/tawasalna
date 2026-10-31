"""Task 5.0b — password change ends pending email links + session_version JWT claim.

1. set_user_password deletes every emailed token of the user (all purposes): an email_change
   link issued before the password change → confirm = invalid_token, email unchanged.
2. A JWT carrying sv is valid only while sv == users.session_version — even when it was issued
   in the same second as the change. The token returned by PUT /auth/password carries the new sv.
   Old tokens without sv keep the iat check until server._NO_SV_REJECT_FROM (task 5.0f → 401 after).

Real PostgreSQL (tables created here; Resend faked at the HTTP layer):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_session_version_tokens.py -q
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-sessionversion-50b-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-50b-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
EMAIL, NEW_EMAIL = "owner50b@example.com", "fresh50b@example.com"
PW, PW2 = "owner-secret-1", "owner-secret-2"


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
    for t in ("blocks", "password_reset_tokens", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', country_code TEXT, password_hash TEXT, "
          "created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("INSERT INTO users (tw_id, email, full_name, password_hash) VALUES ('U50B', :e, 'سارة', :h)",
          e=EMAIL, h=auth.hash_password(PW))
    auth.release_conn(c)
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    auth._migrate_session_version()          # idempotent
    auth.bs.migrate_blocks_suspension()     # task 5.4 — users.suspended_* + blocks (read by the session check)
    auth.ad.migrate_account_deletion()     # task 8.5a — users.deleted_* (read by the session check)
    auth._migrate_password_reset_tokens()
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", "re_TEST_KEY_50b")
    email_service.set_settings(email_service.DEFAULTS)
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    yield f
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    email_service.set_settings(email_service.DEFAULTS)


def _uid():
    return _sql("SELECT id FROM users WHERE email = :e", e=EMAIL)[0][0]


def _login(pw=PW):
    r = client.post("/auth/login", json={"email": EMAIL, "password": pw})
    assert r.status_code == 200, r.text
    assert "session_version" not in r.json()["user"]          # internal — never sent
    return r.json()["token"]


def _H(tok):
    return {"Authorization": "Bearer " + tok}


def _ok(tok):
    return client.post("/auth/verify-token", headers=_H(tok)).status_code


def test_password_change_kills_pending_email_change_link(env):
    tok = _login()
    r = client.post("/auth/email-change/request", headers=_H(tok),
                    json={"new_email": NEW_EMAIL, "current_password": PW})
    assert r.status_code == 200, r.text
    m = re.search(r"/confirm-email#token=([A-Za-z0-9_-]+)", env.calls[-1]["text"])
    link_tok = m.group(1)

    r = client.put("/auth/password", headers=_H(tok), json={"current_password": PW, "new_password": PW2})
    assert r.status_code == 200, r.text

    r = client.post("/auth/email-change/confirm", json={"token": link_tok})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token"
    assert _sql("SELECT email FROM users WHERE id = :u", u=_uid())[0][0] == EMAIL
    assert _sql("SELECT COUNT(*) FROM password_reset_tokens")[0][0] == 0


def test_admin_reset_also_kills_pending_tokens(env):
    auth.email_token_issue("email_change", _uid(), NEW_EMAIL)
    auth.password_reset_issue(_uid())
    state = auth.set_user_password(_uid(), PW2)
    assert state["sv"] == 1
    assert _sql("SELECT COUNT(*) FROM password_reset_tokens")[0][0] == 0


def test_same_second_token_dies_new_token_lives(env):
    old = _login()
    assert _ok(old) == 200
    # Same-second token: iat == password_changed_at would pass the old iat check.
    r = client.put("/auth/password", headers=_H(old), json={"current_password": PW, "new_password": PW2})
    assert r.status_code == 200, r.text
    new = r.json()["token"]
    changed = _sql("SELECT EXTRACT(EPOCH FROM password_changed_at) FROM users")[0][0]
    same_sec = server._jwt_sign({"user_id": _uid(), "user_type": "emp", "sv": 0,
                                 "iat": int(changed), "exp": int(time.time()) + 3600}, server.JWT_SECRET)
    for cached in (True, False):              # this process's cache and a fresh DB read
        if not cached:
            server._pwd_changed_cache.clear()
        assert _ok(old) == 401
        assert _ok(same_sec) == 401
        assert _ok(new) == 200
    assert _ok(_login(PW2)) == 200            # a new login carries the current sv


def test_legacy_token_without_sv_keeps_iat_check(env, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(server, "_NO_SV_REJECT_FROM", now + 86400)   # compatibility window still open
    legacy_old = server._jwt_sign({"user_id": _uid(), "user_type": "emp", "iat": now - 60,
                                   "exp": now + 3600}, server.JWT_SECRET)
    assert _ok(legacy_old) == 200             # no password change yet → still valid
    auth.set_user_password(_uid(), PW2)
    server._pwd_changed_cache.clear()
    assert _ok(legacy_old) == 401
    legacy_new = server._jwt_sign({"user_id": _uid(), "user_type": "emp", "iat": now + 5,
                                   "exp": now + 3600}, server.JWT_SECRET)
    assert _ok(legacy_new) == 200
    monkeypatch.setattr(server, "_NO_SV_REJECT_FROM", now - 1)       # task 5.0f — window closed
    assert _ok(legacy_new) == 401
