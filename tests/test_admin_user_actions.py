"""Task 5.3b2 — admin actions on one user (docs/rules/admin-shell.md → Admin user actions).

1. POST /admin/message → an in-site notification of type admin_message for THAT user (text stored
   as written — renderers escape), its mapped email (admin_message, category notification) passes
   the user's preference; notification not created → the reply is not ok (UI shows no «تم»).
2. PUT /admin/user/{id}/type bumps users.session_version → the user's old JWT → 401;
   a fresh login carries the new type.

Real PostgreSQL (tables created here; Resend faked at the HTTP layer):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_admin_user_actions.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-admin-actions-53b2-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-53b2-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
A, B = "rana53b2@example.com", "omar53b2@example.com"
PW = "rana-secret-1"


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
    for t in ("email_notify_prefs", "email_send_log", "notifications", "password_reset_tokens", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', country_code TEXT, password_hash TEXT, "
          "created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("CREATE TABLE notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), type TEXT, "
          "title TEXT, body TEXT, link TEXT, is_read BOOLEAN DEFAULT FALSE, actor_id INTEGER, entity_id INTEGER, "
          "entity_type TEXT, event_key TEXT, created_at TIMESTAMP DEFAULT NOW())")
    c.run("CREATE UNIQUE INDEX uniq_notif_event_key ON notifications (user_id, event_key) WHERE event_key IS NOT NULL")
    for e, n, tw in ((A, "رنا", "U53A"), (B, "عمر", "U53B")):
        c.run("INSERT INTO users (tw_id, email, full_name, password_hash) VALUES (:t, :e, :n, :h)",
              t=tw, e=e, n=n, h=auth.hash_password(PW))
    auth.release_conn(c)
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    auth._migrate_password_reset_tokens()
    auth._migrate_email_notify()
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", "re_TEST_KEY_53b2")
    monkeypatch.setattr(auth, "_email_submit", lambda fn, *a: fn(*a))   # inline instead of the thread pool
    email_service.set_settings(email_service.DEFAULTS)
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    yield f
    server._rate_store.clear()
    server._pwd_changed_cache.clear()
    email_service.set_settings(email_service.DEFAULTS)


def _uid(email):
    return _sql("SELECT id FROM users WHERE email = :e", e=email)[0][0]


def _admin():
    return {"X-Admin-Token": server._admin_jwt_issue()}


def _login(email):
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _msg(uid, text):
    return client.post("/admin/message", headers=_admin(),
                       json={"user_id": uid, "subject": "رسالة من الإدارة", "message": text})


# ── 1. the message reaches the right user ────────────────────────────────────
def test_message_creates_a_notification_for_that_user_and_its_email(env):
    a, b = _uid(A), _uid(B)
    text = '<img src=x onerror="alert(1)"> مرحبا'
    r = _msg(a, text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["data"]["notification_id"]
    rows = _sql("SELECT id, user_id, type, body FROM notifications")
    assert [tuple(x) for x in rows] == [(body["data"]["notification_id"], a, "admin_message", text)]
    assert not _sql("SELECT 1 FROM notifications WHERE user_id = :b", b=b)
    # the user's own unread counter sees it
    tok = {"Authorization": "Bearer " + _login(A)}
    assert client.get(f"/notifications/{a}/unread-count", headers=tok).json()["data"]["count"] == 1
    # mapped email → the recipient's address, admin text escaped in the HTML
    assert len(env.calls) == 1 and env.calls[0]["to"] == [A]
    assert "<img" not in env.calls[0]["html"] and "&lt;img" in env.calls[0]["html"]


def test_message_email_respects_the_user_preference(env):
    a = _uid(A)
    tok = _login(A)
    assert client.put("/my/email-notifications", headers={"Authorization": "Bearer " + tok},
                      json={"types": {"admin_message": False}}).status_code == 200
    assert _msg(a, "تنبيه").json()["ok"] is True
    assert _sql("SELECT COUNT(*) FROM notifications WHERE user_id = :a", a=a)[0][0] == 1
    assert env.calls == []                      # in-site notification yes, email no


def test_message_not_ok_when_the_notification_is_not_created(env, monkeypatch):
    monkeypatch.setattr(server, "create_notification", lambda *a, **k: None)
    r = _msg(_uid(A), "مرحبا")
    assert r.status_code >= 400 and r.json().get("ok") is not True
    assert client.post("/admin/message", headers=_admin(),
                       json={"user_id": 999999, "subject": "x", "message": "y"}).status_code == 404
    assert _msg(_uid(A), "   ").status_code == 422


def test_message_needs_the_admin(env):
    r = client.post("/admin/message", json={"user_id": _uid(A), "subject": "x", "message": "y"})
    assert r.status_code in (401, 403)


# ── 2. account type change ends the user's sessions ──────────────────────────
def test_type_change_kills_the_old_token_and_new_login_carries_the_new_type(env):
    a = _uid(A)
    old = {"Authorization": "Bearer " + _login(A)}
    assert client.get(f"/notifications/{a}/unread-count", headers=old).status_code == 200
    r = client.put(f"/admin/user/{a}/type", headers=_admin(), json={"user_type": "co"})
    assert r.status_code == 200, r.text
    assert client.get(f"/notifications/{a}/unread-count", headers=old).status_code == 401
    server._pwd_changed_cache.clear()           # another process reading the DB sees the same
    assert client.get(f"/notifications/{a}/unread-count", headers=old).status_code == 401
    new = _login(A)
    assert server._jwt_decode(new)["user_type"] == "co"
    assert client.get(f"/notifications/{a}/unread-count", headers={"Authorization": "Bearer " + new}).status_code == 200
    assert client.put("/admin/user/999999/type", headers=_admin(), json={"user_type": "co"}).status_code == 404
