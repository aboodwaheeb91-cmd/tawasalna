"""Task 5.1b — email change (link to the new address) + KYC email OTP via send_email.

Resend is faked at the HTTP layer (urllib.request.urlopen inside email_service) — every email
the site would send is captured; nothing leaves the machine. Real PostgreSQL (tables created here):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_email_change_kyc_email.py -q
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-emailchange-51b-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-51b-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
KEY = "re_TEST_SECRET_KEY_51b_never_leak"
OLD, NEW, OTHER = "owner@example.com", "fresh@example.com", "taken@example.com"
PW = "owner-secret-1"


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

    def to(self, addr):
        return [c for c in self.calls if c["to"] == [addr]]


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    for t in ("kyc_submissions", "password_reset_tokens", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', email_verified BOOLEAN DEFAULT FALSE, password_hash TEXT, password_changed_at TIMESTAMPTZ, "
          "created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id), "
          "step TEXT NOT NULL, status TEXT DEFAULT 'pending', email_code TEXT, email_verified BOOLEAN DEFAULT FALSE, "
          "phone TEXT, phone_code TEXT, phone_verified BOOLEAN DEFAULT FALSE)")
    for e in (OLD, OTHER):
        c.run("INSERT INTO users (email, full_name, password_hash) VALUES (:e, 'سارة', :h)",
              e=e, h=auth.hash_password(PW))
    auth.release_conn(c)
    auth._migrate_password_reset_tokens()
    auth._migrate_kyc_otp_security()
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", KEY)
    email_service.set_settings(email_service.DEFAULTS)
    server._rate_store.clear()
    yield f
    server._rate_store.clear()
    email_service.set_settings(email_service.DEFAULTS)


def _uid(email=OLD):
    return _sql("SELECT id FROM users WHERE email = :e", e=email)[0][0]


def _hdr(uid):
    return {"Authorization": "Bearer " + server._jwt_encode({"user_id": uid, "user_type": "emp", "tw_id": ""})}


def _request(new=NEW, pw=PW, uid=None):
    uid = uid or _uid()
    return client.post("/auth/email-change/request", headers=_hdr(uid),
                       json={"new_email": new, "current_password": pw})


def _token(fake, addr=NEW):
    m = re.search(r"/confirm-email#token=([A-Za-z0-9_-]+)", fake.to(addr)[-1]["text"])
    assert m, "confirm link missing"
    return m.group(1)


def _confirm(tok):
    return client.post("/auth/email-change/confirm", json={"token": tok})


def test_email_changes_only_after_the_link_and_old_address_is_notified(env):
    uid = _uid()
    r = _request()
    assert r.status_code == 200 and r.json() == {"ok": True, "data": {"sent": True}}
    assert _sql("SELECT email FROM users WHERE id = :u", u=uid)[0][0] == OLD      # not yet
    assert len(env.to(NEW)) == 1 and env.to(OLD) == []                            # link → new only
    tok = _token(env)
    assert _sql("SELECT COUNT(*) FROM password_reset_tokens WHERE token_hash = :t", t=tok)[0][0] == 0  # hash only
    r = _confirm(tok)
    assert r.status_code == 200 and r.json()["data"] == {"changed": True}
    assert _sql("SELECT email FROM users WHERE id = :u", u=uid)[0][0] == NEW
    strings = server.tw_strings.merged(server._STRINGS_OVERRIDES)
    (notice,) = env.to(OLD)
    assert notice["subject"] == strings["email.email_changed.subject"]
    assert "confirm-email" not in notice["text"]                                  # no link in the notice


def test_wrong_password_and_rate_limit(env):
    r = _request(pw="wrong")
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "wrong_password"
    assert env.calls == []
    for _ in range(4):
        _request(pw="wrong")
    assert _request().status_code == 429                                          # 5 / hour / user


def test_taken_address_refused_at_request_and_at_confirm(env):
    r = _request(new=OTHER)
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "email_taken" and env.calls == []
    assert _request().status_code == 200
    tok = _token(env)
    _sql("INSERT INTO users (email, full_name) VALUES (:e, 'x')", e=NEW)          # race: taken meanwhile
    r = _confirm(tok)
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    assert _sql("SELECT email FROM users WHERE id = :u", u=_uid())[0][0] == OLD
    assert env.to(OLD) == []


def test_token_single_use_newest_only_and_30_minutes(env):
    assert _request().status_code == 200
    first = _token(env)
    server._rate_store.clear()
    assert _request().status_code == 200
    second = _token(env)
    assert _confirm(first).status_code == 400                                     # replaced by the new one
    assert _sql("SELECT expires_at - created_at FROM password_reset_tokens WHERE purpose = 'email_change'"
                )[0][0].total_seconds() == pytest.approx(30 * 60, abs=5)
    _sql("UPDATE password_reset_tokens SET expires_at = NOW() - INTERVAL '1 second'")
    assert _confirm(second).status_code == 400                                    # expired
    assert _request(new="again@example.com").status_code == 200
    third = _token(env, "again@example.com")
    assert _confirm(third).status_code == 200
    assert _confirm(third).status_code == 400                                     # single use
    assert auth.password_reset_consume(third) is None                             # never crosses purposes


def test_kyc_email_otp_goes_through_send_email(env, monkeypatch):
    uid = _uid()
    assert server.is_email_otp_delivery_available() is True
    r = client.post("/kyc/email/send", headers=_hdr(uid), json={"email": OLD})
    assert r.status_code == 200, r.text
    (mail,) = env.to(OLD)
    code = re.search(r"\b(\d{6})\b", mail["text"]).group(1)
    stored = _sql("SELECT email_code FROM kyc_submissions WHERE user_id = :u", u=uid)[0][0]
    assert stored.startswith("v1$") and code not in stored                        # hash only
    # another address → refused, nothing sent
    r = client.post("/kyc/email/send", headers=_hdr(uid), json={"email": "x@example.com"})
    assert r.status_code == 400 and len(env.calls) == 1
    r = client.post("/kyc/email/verify", headers=_hdr(uid), json={"code": code})
    assert r.status_code == 200
    # type switched off by the admin → fail closed (503), no code issued
    email_service.set_settings(email_service.validate_settings({"types": {"kyc_email_otp": False}}))
    assert server.is_email_otp_delivery_available() is False
    assert client.post("/kyc/email/send", headers=_hdr(uid), json={"email": OLD}).status_code == 503
    monkeypatch.delenv("RESEND_API_KEY")
    email_service.set_settings(email_service.DEFAULTS)
    assert server.is_email_otp_delivery_available() is False
