"""
test_otp_rate_limit_security.py — PR 1.3 + 1.4: client IP resolution, per-email
login lockout, KYC OTP hardening (SYSTEMS_INDEX → Client IP Resolution ·
Auth Rate Limiter · KYC OTP Security).

OTP tests need a throwaway PostgreSQL (tables are created here):
  OTP_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (default below)
Run: python -m pytest tests/test_otp_rate_limit_security.py -q
"""
import os, sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-otp-pr13-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "OTP_TEST_DB_URL", "postgresql://otp_t:otp_t@127.0.0.1:5432/otp_t")

import pytest
from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)


def _req(xff=None, real=None, peer="10.0.0.9"):
    h = {}
    if xff is not None: h["X-Forwarded-For"] = xff
    if real is not None: h["X-Real-IP"] = real
    return SimpleNamespace(headers=h, client=SimpleNamespace(host=peer))


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CLIENT_IP_SOURCE", "TRUSTED_PROXY_HOPS"):
        monkeypatch.delenv(k, raising=False)
    server._rate_store.clear()
    server._client_ip_warned.clear()
    yield
    server._rate_store.clear()


# ── Client IP ────────────────────────────────────────────────────────────────

def test_default_is_x_real_ip():
    # PR 3.9b: no CLIENT_IP_SOURCE → X-Real-IP (Railway); a spoofed XFF is ignored.
    assert server.get_client_ip(_req(xff="1.2.3.4, 5.6.7.8", real="7.7.7.7")) == "7.7.7.7"
    assert server.get_client_ip(_req(xff="1.2.3.4")) == "10.0.0.9"   # no X-Real-IP → peer
    assert server.get_client_ip(_req()) == "10.0.0.9"


def test_env_value_is_respected(monkeypatch):
    monkeypatch.setenv("CLIENT_IP_SOURCE", "xff_left")
    assert server.get_client_ip(_req(xff="1.2.3.4, 5.6.7.8", real="7.7.7.7")) == "1.2.3.4"
    monkeypatch.setenv("CLIENT_IP_SOURCE", "peer")
    assert server.get_client_ip(_req(xff="1.2.3.4", real="7.7.7.7")) == "10.0.0.9"


def test_spoofed_xff_does_not_change_ip(monkeypatch):
    monkeypatch.setenv("CLIENT_IP_SOURCE", "xff_right")
    assert server.get_client_ip(_req(xff="6.6.6.6, 203.0.113.5")) == "203.0.113.5"
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert server.get_client_ip(_req(xff="6.6.6.6, 203.0.113.5, 10.1.1.1")) == "203.0.113.5"
    assert server.get_client_ip(_req(xff="203.0.113.5")) == "10.0.0.9"  # too few hops → peer
    monkeypatch.setenv("CLIENT_IP_SOURCE", "peer")
    assert server.get_client_ip(_req(xff="6.6.6.6", real="6.6.6.7")) == "10.0.0.9"
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    assert server.get_client_ip(_req(xff="6.6.6.6", real="198.51.100.2")) == "198.51.100.2"


def test_invalid_source_or_ip_falls_back_to_peer_warning_once(monkeypatch, capsys):
    monkeypatch.setenv("CLIENT_IP_SOURCE", "bogus")
    server.get_client_ip(_req(xff="1.2.3.4"))
    assert server.get_client_ip(_req(xff="1.2.3.4")) == "10.0.0.9"
    monkeypatch.setenv("CLIENT_IP_SOURCE", "xff_left")
    assert server.get_client_ip(_req(xff="not-an-ip")) == "10.0.0.9"
    assert server.get_client_ip(_req(xff="evil\n[fake log]")) == "10.0.0.9"
    out = capsys.readouterr().out
    assert out.count("CLIENT_IP_SOURCE='bogus'") == 1
    assert out.count("not a valid IP") == 1


def test_rate_limiter_rotating_xff_blocked_under_xff_right(monkeypatch):
    monkeypatch.setenv("CLIENT_IP_SOURCE", "xff_right")
    codes = [client.post("/kyc/email/verify", json={"code": "1"},
                         headers={"X-Forwarded-For": f"9.9.9.{i}, 203.0.113.5"}).status_code
             for i in range(server._RATE_LIMIT + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]


# ── Per-email login lockout (independent of IP) ──────────────────────────────

def test_login_email_lockout_ignores_ip(monkeypatch):
    monkeypatch.setattr(server, "authenticate_user", lambda e, p: None)
    for i in range(server._LOGIN_EMAIL_MAX_FAILS):
        r = client.post("/auth/login", json={"email": "Victim@x.com", "password": "bad"},
                        headers={"X-Forwarded-For": f"8.8.{i}.1"})
        assert r.status_code == 401
    monkeypatch.setattr(server, "authenticate_user", lambda e, p: {"id": 1, "user_type": "emp", "tw_id": "U1"})
    r = client.post("/auth/login", json={"email": " victim@X.com ", "password": "right"},
                    headers={"X-Forwarded-For": "4.4.4.4"})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "login_email_locked"
    # another email is unaffected
    assert client.post("/auth/login", json={"email": "other@x.com", "password": "ok"}).status_code == 200


def test_login_log_client_ip_never_prints_credentials(monkeypatch, capsys):
    monkeypatch.setenv("LOG_CLIENT_IP", "1")
    monkeypatch.setattr(server, "authenticate_user", lambda e, p: None)
    client.post("/auth/login", json={"email": "secret@x.com", "password": "P@ss-123"},
                headers={"X-Forwarded-For": "1.2.3.4"})
    out = capsys.readouterr().out
    assert "[client-ip]" in out and "'1.2.3.4'" in out
    assert "secret@x.com" not in out and "P@ss-123" not in out


# ── KYC OTP (real PostgreSQL) ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP TABLE IF EXISTS kyc_submissions")
    c.run("DROP TABLE IF EXISTS users")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT, email_verified BOOLEAN DEFAULT FALSE, "
          "phone_verified BOOLEAN DEFAULT FALSE)")
    c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE, step TEXT, "
          "email_code TEXT, email_verified BOOLEAN DEFAULT FALSE, phone TEXT, phone_code TEXT, "
          "phone_verified BOOLEAN DEFAULT FALSE)")
    c.run("INSERT INTO users (id, email) VALUES (1, 'a@x.com')")
    c.run("INSERT INTO kyc_submissions (user_id, step, email_code, phone_code) VALUES (1, 'email', '123456', '654321')")
    auth.release_conn(c)
    auth._migrate_kyc_otp_security()
    auth._migrate_kyc_otp_security()  # idempotent
    return auth


def _row(cols):
    c = auth.get_conn()
    try:
        return c.run(f"SELECT {cols} FROM kyc_submissions WHERE user_id=1")[0]
    finally:
        auth.release_conn(c)


def _reset():
    c = auth.get_conn()
    try:
        c.run("UPDATE kyc_submissions SET email_verified=FALSE, phone_verified=FALSE WHERE user_id=1")
        c.run("UPDATE users SET email='a@x.com', email_verified=FALSE WHERE id=1")
    finally:
        auth.release_conn(c)


def test_migration_wiped_legacy_plaintext_codes(db):
    assert _row("email_code, phone_code") == [None, None]
    assert db.verify_email_code(1, "123456") is False


def test_code_stored_hashed_bound_and_single_use(db):
    _reset()
    code = db.send_email_code(1, " A@x.com ")
    assert len(code) == 6 and code.isdigit()
    stored, target = _row("email_code, email_code_target")
    assert stored.startswith("v1$") and code not in stored and target == "a@x.com"
    assert db.verify_email_code(1, code) is True
    assert _row("email_code, email_verified") == [None, True]
    assert db.verify_email_code(1, code) is False  # used


def test_expired_code_rejected(db):
    _reset()
    code = db.send_email_code(1, "a@x.com")
    c = auth.get_conn()
    c.run("UPDATE kyc_submissions SET email_code_expires_at = NOW() - INTERVAL '1 second' WHERE user_id=1")
    auth.release_conn(c)
    assert db.verify_email_code(1, code) is False


def test_five_wrong_attempts_kill_code(db):
    _reset()
    code = db.send_phone_code(1, "+962 79-000-0000")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(db._OTP_MAX_ATTEMPTS):
        assert db.verify_phone_code(1, wrong) is False
    assert db.verify_phone_code(1, code) is False
    assert _row("phone_code, phone_verified") == [None, False]


def test_code_for_other_email_rejected(db):
    _reset()
    code = db.send_email_code(1, "attacker@evil.com")
    assert db.verify_email_code(1, code) is False
    assert _row("email_verified")[0] is False


def test_phone_changed_after_send_rejected(db):
    _reset()
    code = db.send_phone_code(1, "+962790000001")
    c = auth.get_conn()
    c.run("UPDATE kyc_submissions SET phone='+962790000002' WHERE user_id=1")
    auth.release_conn(c)
    assert db.verify_phone_code(1, code) is False


def test_verify_routes_503_when_delivery_off(monkeypatch):
    called = []
    monkeypatch.setattr(server, "verify_email_code", lambda *a: called.append(a) or True)
    monkeypatch.setattr(server, "verify_phone_code", lambda *a: called.append(a) or True)
    hdr = {"Authorization": "Bearer " + server._jwt_encode({"user_id": 1, "user_type": "emp", "tw_id": "U1"})}
    for path in ("/kyc/email/verify", "/kyc/phone/verify"):
        r = client.post(path, json={"code": "123456"}, headers=hdr)
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "otp_delivery_unavailable"
    assert called == []
