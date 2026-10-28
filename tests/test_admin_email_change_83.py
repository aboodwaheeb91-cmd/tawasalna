"""Task 8.3 — admin email change (SYSTEMS_INDEX §1c · docs/rules/email.md rule 5).

PUT /admin/user/{id}/email {new_email} → the same email_change token (auth.email_change_request) +
the same email_change template to the NEW address; users.email changes only when the link is opened
(POST /auth/email-change/confirm). Perm users.email (owner "*" passes). Audit target = user_id=N, no address.

Real PostgreSQL (tables created here; Resend faked at the HTTP layer):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_admin_email_change_83.py -q
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-admin-email-83-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-83-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import admin_insights
import auth
import email_service
import server

client = TestClient(server.app)
A, B = "rana83@example.com", "omar83@example.com"
NEW = "rana83.new@example.com"
PW = "rana-secret-1"


class FakeResend:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(json.loads(req.data.decode("utf-8")))

        class _R:
            status = 200
            def read(self): return b'{"id":"re_83"}'
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
    for t in ("admin_audit_log", "blocks", "email_notify_prefs", "email_send_log", "notifications", "password_reset_tokens", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', country_code TEXT, password_hash TEXT, "
          "created_at TIMESTAMPTZ DEFAULT NOW())")
    for e, n, tw in ((A, "رنا", "U83A"), (B, "عمر", "U83B")):
        c.run("INSERT INTO users (tw_id, email, full_name, password_hash) VALUES (:t, :e, :n, :h)",
              t=tw, e=e, n=n, h=auth.hash_password(PW))
    auth.release_conn(c)
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    auth.bs.migrate_blocks_suspension()
    auth._migrate_password_reset_tokens()
    auth._migrate_email_notify()
    admin_insights.migrate_admin_audit_log()
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", "re_TEST_KEY_83")
    email_service.set_settings(email_service.DEFAULTS)
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    yield f
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    email_service.set_settings(email_service.DEFAULTS)


def _uid(email):
    return _sql("SELECT id FROM users WHERE email = :e", e=email)[0][0]


def _email(uid):
    return _sql("SELECT email FROM users WHERE id = :u", u=uid)[0][0]


def _put(uid, new_email, headers=None):
    return client.put(f"/admin/user/{uid}/email", json={"new_email": new_email},
                      headers=headers if headers is not None else {"X-Admin-Token": server._admin_jwt_issue()})


def _token(call):
    return re.search(r"/confirm-email#token=([A-Za-z0-9_\-]+)", call["html"]).group(1)


def _err(r):
    e = r.json()["error"]
    return e["code"], e.get("field")


# ── gate ─────────────────────────────────────────────────────────────────────
def test_no_admin_token_401_staff_without_perm_403_with_perm_passes(env):
    a = _uid(A)
    assert _put(a, NEW, headers={}).status_code == 401
    user_jwt = client.post("/auth/login", json={"email": A, "password": PW}).json()["token"]
    assert _put(a, NEW, headers={"X-Admin-Token": user_jwt}).status_code == 401
    staff = {"X-Admin-Token": server._admin_jwt_issue(sub="staff:1", perms=["users.suspend"])}
    assert _put(a, NEW, headers=staff).status_code == 403
    assert env.calls == [] and not _sql("SELECT 1 FROM password_reset_tokens")
    ok = {"X-Admin-Token": server._admin_jwt_issue(sub="staff:2", perms=["users.email"])}
    assert _put(a, NEW, headers=ok).status_code == 200


# ── validation ───────────────────────────────────────────────────────────────
def test_validation_errors_on_the_field(env):
    a = _uid(A)
    for value, code in (("", "required"), ("   ", "required"), ("not-an-email", "invalid_email"),
                        (" RANA83@Example.com ", "same_email"), (B.upper(), "email_taken")):
        r = _put(a, value)
        assert r.status_code == 422, (value, r.text)
        assert _err(r) == (code, "new_email"), value
    assert _put(99999, NEW).status_code == 404
    assert env.calls == [] and not _sql("SELECT 1 FROM password_reset_tokens")
    assert _email(a) == A


def test_email_unavailable_503(env, monkeypatch):
    email_service.set_settings(email_service.validate_settings({"types": {"email_change": False}}))
    r = _put(_uid(A), NEW)
    assert r.status_code == 503 and _err(r)[0] == "email_unavailable"
    email_service.set_settings(email_service.DEFAULTS)
    monkeypatch.delenv("RESEND_API_KEY")
    assert _put(_uid(A), NEW).status_code == 503
    assert env.calls == []


def test_rate_limit_429_per_user(env):
    a = _uid(A)
    for i in range(5):
        assert _put(a, f"r{i}.83@example.com").status_code == 200
    r = _put(a, "r9.83@example.com")
    assert r.status_code == 429 and _err(r)[0] == "rate_limited"
    assert _put(_uid(B), "omar.new83@example.com").status_code == 200   # another account — own bucket


# ── the flow ─────────────────────────────────────────────────────────────────
def test_request_sends_link_to_new_address_and_changes_nothing_until_confirm(env):
    a = _uid(A)
    r = _put(a, "  " + NEW.upper() + " ")
    assert r.status_code == 200 and r.json() == {"ok": True, "data": {"sent": True}}
    assert _email(a) == A                                     # not changed by the admin request
    rows = _sql("SELECT user_id, purpose, payload FROM password_reset_tokens")
    assert [tuple(x) for x in rows] == [(a, "email_change", NEW)]
    assert len(env.calls) == 1 and env.calls[0]["to"] == [NEW]
    r = client.post("/auth/email-change/confirm", json={"token": _token(env.calls[0])})
    assert r.status_code == 200 and r.json()["data"]["changed"] is True
    assert _email(a) == NEW
    assert env.calls[-1]["to"] == [A]                         # «email changed» notice to the old address


def test_new_request_kills_the_old_link(env):
    a = _uid(A)
    assert _put(a, "first83@example.com").status_code == 200
    old_tok = _token(env.calls[-1])
    assert _put(a, NEW).status_code == 200
    new_tok = _token(env.calls[-1])
    assert client.post("/auth/email-change/confirm", json={"token": old_tok}).status_code == 400
    assert _email(a) == A
    assert client.post("/auth/email-change/confirm", json={"token": new_tok}).status_code == 200
    assert _email(a) == NEW


def test_audit_target_is_the_user_id_without_any_address(env):
    a = _uid(A)
    assert _put(a, NEW).status_code == 200
    assert _put(a, B).status_code == 422
    rows = _sql("SELECT action, target, old_value, new_value FROM admin_audit_log ORDER BY id")
    assert [tuple(x) for x in rows] == [("admin_email_change", f"user_id={a}", None, None)] * 2
    dump = json.dumps([list(x) for x in _sql("SELECT * FROM admin_audit_log")], default=str).lower()
    assert "@" not in dump
