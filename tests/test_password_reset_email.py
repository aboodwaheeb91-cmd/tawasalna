"""Task 5.1a — Unified Email System (email_service.send_email) + «نسيت كلمة المرور».

Resend is faked at the HTTP layer (urllib.request.urlopen inside email_service) — the request
the site would send is captured and checked; nothing leaves the machine. Tokens use a real
PostgreSQL (tables created here):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_password_reset_email.py -q
"""
import io
import json
import os
import re
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-pwreset-51a-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-51a-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
KEY = "re_TEST_SECRET_KEY_must_never_leak_123456"
EMAIL = "member@example.com"
OLD_PW = "old-secret-1"


class FakeResend:
    """Stands in for urllib.request.urlopen — records every request."""
    def __init__(self):
        self.calls, self.fail = [], None

    def __call__(self, req, timeout=None):
        self.calls.append({"url": req.full_url, "method": req.get_method(),
                           "headers": {k.lower(): v for k, v in req.header_items()},
                           "body": json.loads(req.data.decode("utf-8")), "timeout": timeout})
        if self.fail == "http":
            raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, io.BytesIO(b'{"message":"x"}'))
        if self.fail == "network":
            raise OSError("connection reset")

        class _R:
            status = 200
            def read(self): return b'{"id":"re_msg_1"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R()


@pytest.fixture(scope="module")
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP TABLE IF EXISTS password_reset_tokens")
    c.run("DROP TABLE IF EXISTS users")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT UNIQUE, full_name TEXT, "
          "password_hash TEXT, password_changed_at TIMESTAMPTZ)")
    c.run("INSERT INTO users (email, full_name, password_hash) VALUES (:e, :n, :h)",
          e=EMAIL, n="سارة <b>x</b>", h=auth.hash_password(OLD_PW))
    auth.release_conn(c)
    auth._migrate_password_reset_tokens()
    auth._migrate_password_reset_tokens()   # idempotent
    auth._migrate_session_version()
    auth.bs.migrate_blocks_suspension()     # task 5.4 — users.suspended_* + blocks (read by the session check)
    return auth


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", KEY)
    email_service.set_settings(email_service.DEFAULTS)
    server._rate_store.clear()
    yield f
    server._rate_store.clear()
    email_service.set_settings(email_service.DEFAULTS)


def _token_from(call) -> str:
    m = re.search(r"/reset-password#token=([A-Za-z0-9_-]+)", call["body"]["text"])
    assert m, "reset link missing from the email"
    return m.group(1)


def _request(email=EMAIL, ip="9.9.9.9"):
    return client.post("/auth/password-reset/request", json={"email": email}, headers={"X-Real-IP": ip})


# ── 1. send_email → the right Resend request ────────────────────────────────
def test_send_email_builds_the_right_request(fake):
    res = email_service.send_email("to@example.com", "password_reset",
                                   {"name": "<script>x</script>", "link": "https://tawasolna.com/reset-password#token=abc",
                                    "minutes": 30})
    assert res == {"ok": True, "code": "sent", "id": "re_msg_1"}
    (call,) = fake.calls
    assert call["url"] == "https://api.resend.com/emails" and call["method"] == "POST"
    assert call["headers"]["authorization"] == "Bearer " + KEY
    assert call["headers"]["content-type"] == "application/json" and call["timeout"]
    b = call["body"]
    assert b["from"] == "تواصلنا <no-reply@tawasolna.com>" and b["to"] == ["to@example.com"]
    strings = server.tw_strings.merged(server._STRINGS_OVERRIDES)
    assert b["subject"] == strings["email.password_reset.subject"]
    assert 'dir="rtl"' in b["html"] and "<script>x</script>" not in b["html"]
    assert "&lt;script&gt;x&lt;/script&gt;" in b["html"]          # variable escaped in HTML
    assert "30" in b["text"] and "https://tawasolna.com/reset-password#token=abc" in b["text"]


def test_admin_string_override_reaches_the_email(fake, monkeypatch):
    monkeypatch.setattr(server, "_STRINGS_OVERRIDES", {"email.admin_test.subject": "عنوان من الأدمن"})
    email_service.send_email("to@example.com", "admin_test", {})
    assert fake.calls[0]["body"]["subject"] == "عنوان من الأدمن"


# ── 2. the key never shows up ───────────────────────────────────────────────
def test_key_never_in_logs_or_responses(fake, capsys, db):
    email_service.send_email("to@example.com", "admin_test", {})
    fake.fail = "http"
    assert email_service.send_email("to@example.com", "admin_test", {})["code"] == "failed"
    fake.fail = "network"
    assert email_service.send_email("to@example.com", "admin_test", {})["code"] == "failed"
    fake.fail = None
    r = client.get("/health")
    assert r.json()["email"] == "configured"
    admin = {"X-Admin-Token": server._admin_jwt_issue()}
    g = client.get("/admin/email", headers=admin)
    assert g.status_code == 200 and g.json()["data"]["status"] == "configured"
    out = capsys.readouterr()
    for text in (out.out, out.err, r.text, g.text):
        assert KEY not in text and "to@example.com" not in text


def test_missing_key_is_unavailable_not_a_crash(fake, monkeypatch, db):
    monkeypatch.delenv("RESEND_API_KEY")
    assert email_service.send_email("to@example.com", "admin_test", {}) == {"ok": False, "code": "unavailable"}
    assert client.get("/health").json()["email"] == "missing"
    r = _request()
    assert r.status_code == 503 and r.json()["error"]["code"] == "email_unavailable"
    assert fake.calls == []


# ── 3. admin settings + test email ──────────────────────────────────────────
def test_admin_settings_and_test_email(fake, db):
    assert client.put("/admin/email", json={"from_name": "x"}).status_code == 401
    admin = {"X-Admin-Token": server._admin_jwt_issue()}
    bad = client.put("/admin/email", headers=admin, json={"from_address": "no at sign"})
    assert bad.status_code == 422 and bad.json()["error"]["field"] == "from_address"
    ok = client.put("/admin/email", headers=admin,
                    json={"from_name": "فريق تواصلنا", "types": {"password_reset": False}})
    assert ok.status_code == 200
    assert email_service.send_email(EMAIL, "password_reset", {})["code"] == "disabled"
    assert _request().status_code == 503                                # type off → no reset emails
    t = client.post("/admin/email/test", headers=admin, json={"to": "admin@example.com"})
    assert t.status_code == 200 and t.json()["data"]["sent"] is True
    assert fake.calls[-1]["body"]["from"] == "فريق تواصلنا <no-reply@tawasolna.com>"
    assert fake.calls[-1]["body"]["to"] == ["admin@example.com"]


# ── 4. same reply for a known and an unknown address · limits ──────────────
def test_same_reply_known_and_unknown(fake, db):
    known, unknown = _request(EMAIL), _request("nobody@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"ok": True, "data": {"sent": True}}
    assert len(fake.calls) == 1 and fake.calls[0]["body"]["to"] == [EMAIL]


def test_rate_limits_per_email_and_per_ip(fake, db):
    replies = [_request(EMAIL, ip=f"1.1.1.{i}").json() for i in range(5)]
    assert all(r == {"ok": True, "data": {"sent": True}} for r in replies)
    assert len(fake.calls) == server._PWRESET_EMAIL_LIMIT                # per-email cap: silent
    server._rate_store.clear()
    codes = [_request(f"u{i}@example.com", ip="2.2.2.2").status_code for i in range(server._PWRESET_IP_LIMIT + 1)]
    assert codes[:-1] == [200] * server._PWRESET_IP_LIMIT and codes[-1] == 429


# ── 5. token: hash only · single use · older dies · 30 minutes ─────────────
def test_token_lifecycle(fake, db):
    _request()
    tok1 = _token_from(fake.calls[-1])
    rows = _sql("SELECT token_hash, EXTRACT(EPOCH FROM expires_at - created_at) FROM password_reset_tokens")
    assert len(rows) == 1 and tok1 not in rows[0][0] and rows[0][0].startswith("v1$")
    assert int(rows[0][1]) == 30 * 60
    _request(ip="3.3.3.3")
    tok2 = _token_from(fake.calls[-1])
    assert tok2 != tok1
    old = client.post("/auth/password-reset/confirm", json={"token": tok1, "new_password": "new-secret-2"})
    assert old.status_code == 400 and old.json()["error"]["code"] == "invalid_token"   # older token died
    weak = client.post("/auth/password-reset/confirm", json={"token": tok2, "new_password": "123"})
    assert weak.status_code == 422 and weak.json()["errors"][0]["field"] == "new_password"
    ok = client.post("/auth/password-reset/confirm", json={"token": tok2, "new_password": "new-secret-2"})
    assert ok.status_code == 200
    again = client.post("/auth/password-reset/confirm", json={"token": tok2, "new_password": "new-secret-3"})
    assert again.status_code == 400                                      # single use
    uid = _sql("SELECT id FROM users WHERE email = :e", e=EMAIL)[0][0]
    assert auth.check_user_password(uid, "new-secret-2") is True


def test_token_expires_after_30_minutes(fake, db):
    _request(ip="4.4.4.4")
    tok = _token_from(fake.calls[-1])
    _sql("UPDATE password_reset_tokens SET expires_at = NOW() - INTERVAL '1 second'")
    r = client.post("/auth/password-reset/confirm", json={"token": tok, "new_password": "new-secret-9"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token"


# ── 6. reset ends every old session + sends the «تغيّرت كلمة مرورك» email ──
def test_reset_revokes_sessions_and_notifies(fake, db, monkeypatch):
    uid = _sql("SELECT id FROM users WHERE email = :e", e=EMAIL)[0][0]
    now = int(time.time())
    old_jwt = server._jwt_sign({"sv": 0, "user_id": uid, "user_type": "emp", "iat": now - 120, "exp": now + 3600},
                               server.JWT_SECRET)
    _sql("UPDATE users SET password_changed_at = NULL, session_version = 0")
    server._pwd_changed_cache.clear()
    assert server._jwt_decode(old_jwt)                                   # valid before the reset
    revoked = []
    monkeypatch.setattr(server, "_ws_revoke_user", lambda u, reason: revoked.append((u, reason)) or 0)
    _request(ip="5.5.5.5")
    tok = _token_from(fake.calls[-1])
    r = client.post("/auth/password-reset/confirm", json={"token": tok, "new_password": "brand-new-7"})
    assert r.status_code == 200
    assert revoked == [(uid, "password_reset")]
    server._pwd_changed_cache.clear()                                    # read the DB stamp, not the cache
    assert server._jwt_decode(old_jwt) == {}
    stale = client.put("/auth/password", headers={"Authorization": "Bearer " + old_jwt},
                       json={"current_password": "brand-new-7", "new_password": "other-pw-8"})
    assert stale.status_code == 401                                      # old session is dead
    last = fake.calls[-1]["body"]
    assert last["to"] == [EMAIL]
    assert last["subject"] == server.tw_strings.merged({})["email.password_changed.subject"]
