"""Privacy Boundary — HTTP groups of tests/test_privacy_boundary.py without a live server (task 5.0e).

Same checks as groups A–F + H of the live-server file, in-process (TestClient) on a real PostgreSQL
whose schema comes from the real startup migrations (server._run_startup_migrations):
  A  GET /profile/{id}/full — JWT + owner only
  B  GET /auth/user/{id}    — JWT + owner only
  C  GET /profile/{id}      — public, never email / phone / dob / verify_request (owner included)
  D  GET /kyc/status/{id}   — JWT + owner only, no OTP codes
  E  KYC writes             — user from the JWT only (a body user_id is ignored)
  F  OTP fail-closed        — no provider → 503 otp_delivery_unavailable, no code, no state change
  H  register / login of every account type still works
The static / mock groups (G, I–L) of the live-server file are not ported — see run_tests.sh EXCLUDED.

  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_privacy_boundary_http.py -q
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-privacy-http-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)
PW = "TwTest@9999"
PRIVATE = ("email", "phone", "dob", "verify_request")
OTP_FIELDS = ("email_code", "phone_code", "dev_code")


@pytest.fixture(scope="module", autouse=True)
def schema():
    try:
        auth.release_conn(auth.get_conn())
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    server._run_startup_migrations()


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)   # OTP delivery unavailable → fail closed
    server._rate_store.clear()
    yield


def _register(utype="emp"):
    email = f"priv_{uuid.uuid4().hex[:10]}@example.com"
    body = {"email": email, "password": PW, "user_type": utype}
    body.update({"first_name": "رنا", "last_name": "خالد"} if utype == "emp" else {"full_name": "جهة اختبار"})
    server._rate_store.clear()
    r = client.post("/auth/register", json=body)
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"], {"Authorization": "Bearer " + r.json()["token"]}, email


@pytest.fixture
def two():
    return _register(), _register()


# ── A — /profile/{id}/full ──
def test_a_full_profile_owner_only(two):
    (uid, h, email), (_, h2, _) = two
    assert client.get(f"/profile/{uid}/full").status_code == 401
    assert client.get(f"/profile/{uid}/full", headers=h2).status_code == 403
    r = client.get(f"/profile/{uid}/full", headers=h)
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["email"] == email and p["id"] == uid


# ── B — /auth/user/{id} ──
def test_b_auth_user_owner_only(two):
    (uid, h, email), (_, h2, _) = two
    assert client.get(f"/auth/user/{uid}").status_code == 401
    assert client.get(f"/auth/user/{uid}", headers=h2).status_code == 403
    r = client.get(f"/auth/user/{uid}", headers=h)
    assert r.status_code == 200 and r.json()["user"]["id"] == uid and r.json()["user"]["email"] == email


# ── C — public /profile/{id} ──
@pytest.mark.parametrize("as_owner", [False, True])
def test_c_public_profile_strips_private_fields(two, as_owner):
    (uid, h, _), _ = two
    r = client.get(f"/profile/{uid}", headers=h if as_owner else {})
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["id"] == uid and p["full_name"]
    for f in PRIVATE:
        assert f not in p, f


# ── D — /kyc/status/{id} ──
def test_d_kyc_status_owner_only_no_codes(two):
    (uid, h, _), (_, h2, _) = two
    assert client.get(f"/kyc/status/{uid}").status_code == 401
    assert client.get(f"/kyc/status/{uid}", headers=h2).status_code == 403
    r = client.get(f"/kyc/status/{uid}", headers=h)
    assert r.status_code == 200
    kyc = r.json()["kyc"]
    assert kyc["status"] == "not_started" and "step" in kyc
    for f in OTP_FIELDS:
        assert f not in kyc, f


# ── E — KYC writes use the JWT user only ──
def test_e_kyc_writes_from_jwt_only(two):
    (uid, h, _), (uid2, h2, _) = two
    assert client.post("/kyc/start").status_code == 401
    assert client.post("/kyc/phone/verify", json={"user_id": uid, "code": "123456"}).status_code == 401
    r = client.post("/kyc/start", headers=h)
    assert r.status_code in (200, 400), r.text
    r = client.post("/kyc/email/send", headers=h, json={"user_id": uid2, "email": "x@example.com"})
    assert r.status_code not in (403, 422), r.text
    assert client.get(f"/kyc/status/{uid2}", headers=h2).json()["kyc"]["status"] == "not_started"   # no IDOR
    assert client.get(f"/kyc/status/{uid}", headers=h).json()["kyc"]["status"] != "not_started"


# ── F — OTP fail-closed, never in a response ──
@pytest.mark.parametrize("path,body", [("/kyc/email/send", {"email": "x@example.com"}),
                                       ("/kyc/phone/send", {"phone": "+962799000000"})])
def test_f_otp_send_fails_closed(two, path, body):
    (uid, h, _), _ = two
    before = client.get(f"/kyc/status/{uid}", headers=h).json()["kyc"]
    r = client.post(path, headers=h, json=body)
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["code"] == "otp_delivery_unavailable"
    for f in OTP_FIELDS:
        assert f not in r.text
    after = client.get(f"/kyc/status/{uid}", headers=h).json()["kyc"]
    assert after == before and after.get("step") not in ("email_sent", "email_verified")


# ── H — registration / login of every account type ──
@pytest.mark.parametrize("utype", ["emp", "co", "edu"])
def test_h_register_and_login(utype):
    uid, h, email = _register(utype)
    server._rate_store.clear()
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200 and r.json()["user"]["id"] == uid and r.json()["token"]
    assert client.get(f"/profile/{uid}/full", headers=h).status_code == 200
