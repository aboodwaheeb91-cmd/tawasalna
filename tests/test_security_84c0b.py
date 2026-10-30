"""Task 8.4c-0b — security fixes from the site scan, real FastAPI app + real PostgreSQL
(docs/rules/blocks-suspension.md · messenger.md · auth-identity.md).

  1. messages + block / suspension: GET /messages/{a}/{b} both ways → 404 (the messaging «not found»), read_at /
     delivered_at / is_read untouched · the same for a suspended / missing peer · unblock → 200 · every messaging
     route (send · can-send · end conversation · conversations list · unread count · the unread-message email job).
  2. /auth/login: 30 parallel wrong passwords for one email → 401s ≤ the lock limit, the rest 429 · a correct
     login after two failures leaves no extra hit.
  3. email_token_issue: 10 parallel issues for one user + purpose (and for both email change purposes) → one
     valid row.
  4. KYC code: 7 digits / letters / 10 000 chars → 422, attempts unchanged (guest support code too).
  5. Strict-Transport-Security on an HTML page and an API reply.
TW_TEST_DB_URL (run_tests.sh sets it); without it skipped — and with TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is
a failure (tests/conftest.py SECURITY_TESTS).
Run: python -m pytest tests/test_security_84c0b.py -q
"""
import os, sys, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import blocks_suspension as bs
import email_service
import server as srv
import tw_settings
from test_admin_mfa_84b import _db_params

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
PW = "Corr3ct-pass-84c0b"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "_RATE_LIMIT", 100_000)   # the per-IP path limit — the login locks are measured
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield
    srv._rate_store.clear()


@pytest.fixture(scope="module")
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(user_type="emp"):
    email = f"u{uuid.uuid4().hex[:10]}@t.test"
    u = auth.create_user("Test User", email, PW, user_type, "DEFAULT", terms_version="t")
    tok = srv._jwt_encode({"user_id": u["id"], "user_type": user_type, "tw_id": u.get("tw_id", ""), "sv": 0})
    return {"id": u["id"], "email": email, "h": {"Authorization": "Bearer " + tok}}


def _burst(n, fn):
    start = threading.Barrier(n)

    def go(i):
        start.wait()
        return fn(i)

    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(go, range(n)))


# ── 1. messages + block / suspension ──
def _pair():
    """A company + an emp with one unread, undelivered message each way."""
    a, b = _user("co"), _user("emp")
    for s, r in ((a, b), (b, a)):
        _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:s, :r, 'hi')", s=s["id"], r=r["id"])
    return a, b


def _marks(a, b):
    return _sql("SELECT id, is_read, read_at, delivered_at FROM messages WHERE sender_id IN (:a, :b) "
                "AND receiver_id IN (:a, :b) ORDER BY id", a=a["id"], b=b["id"])


def _hidden_everywhere(a, b, b_can_call=True):
    """Every messaging route of a (and of b while b has a session) answers «not found» / leaves b out."""
    before = _marks(a, b)
    readers = [(a, b)] + ([(b, a)] if b_can_call else [])
    for me, other in readers:
        r = client.get(f"/messages/{me['id']}/{other['id']}", headers=me["h"])
        assert r.status_code == 404, r.text
        assert r.json()["error"]["code"] == "not_found"
        assert "messages" not in r.json()
    assert _marks(a, b) == before                                       # nothing marked read / delivered
    r = client.post("/messages/send", json={"receiver_id": b["id"], "content": "x"}, headers=a["h"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", r.text
    r = client.get(f"/messages/can-send/{b['id']}", headers=a["h"])
    assert r.status_code == 200 and r.json()["data"]["can_message"] is False
    assert r.json()["data"]["reason"] == "not_found"
    r = client.post(f"/messages/conversations/{b['id']}/end", headers=a["h"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", r.text
    assert not _sql("SELECT 1 FROM conversation_endings WHERE ended_by = :a", a=a["id"])
    convs = client.get(f"/messages/conversations/{a['id']}", headers=a["h"]).json()["conversations"]
    assert b["id"] not in [c["other_id"] for c in convs]
    assert client.get(f"/messages/unread/{a['id']}", headers=a["h"]).json()["count"] == 0
    assert _marks(a, b) == before


def _no_ws(monkeypatch):
    sent = []

    async def rec(uid, payload):
        sent.append((uid, payload))
        return False
    monkeypatch.setattr(srv.ws_manager, "send_to_user", rec)
    return sent


def test_block_hides_the_conversation_both_ways(db, monkeypatch):
    sent = _no_ws(monkeypatch)
    a, b = _pair()
    assert client.put(f"/blocks/{b['id']}", headers=a["h"]).status_code == 200
    _hidden_everywhere(a, b)
    assert sent == []                                                   # no WS read receipt
    assert client.delete(f"/blocks/{b['id']}", headers=a["h"]).status_code == 200
    r = client.get(f"/messages/{a['id']}/{b['id']}", headers=a["h"])
    assert r.status_code == 200 and len(r.json()["messages"]) == 2
    assert _sql("SELECT is_read FROM messages WHERE sender_id = :b AND receiver_id = :a",
                a=a["id"], b=b["id"])[0][0] is True                    # b → a read once visible again


def test_block_by_the_other_side_hides_it_too(db, monkeypatch):
    _no_ws(monkeypatch)
    a, b = _pair()
    assert client.put(f"/blocks/{a['id']}", headers=b["h"]).status_code == 200
    _hidden_everywhere(a, b)


def test_suspended_peer_hides_the_conversation(db, monkeypatch):
    _no_ws(monkeypatch)
    a, b = _pair()
    bs.set_suspension(b["id"], True, None, "owner")
    _hidden_everywhere(a, b, b_can_call=False)
    bs.set_suspension(b["id"], False, None, "owner")
    assert client.get(f"/messages/{a['id']}/{b['id']}", headers=a["h"]).status_code == 200


def test_missing_peer_is_not_found(db):
    a = _user()
    r = client.get(f"/messages/{a['id']}/2000000000", headers=a["h"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_unread_message_email_skipped_after_a_block(db, monkeypatch):
    a, b = _pair()
    mid = _sql("SELECT id FROM messages WHERE sender_id = :a AND receiver_id = :b", a=a["id"], b=b["id"])[0][0]
    calls = []
    monkeypatch.setattr(auth, "email_notify_user", lambda *a_, **k: calls.append(a_) or {"code": "sent"})
    job = {"payload": {"receiver_id": b["id"], "sender_id": a["id"], "message_id": mid}}
    bs.block(b["id"], a["id"])
    auth._handle_message_email(job)
    assert calls == []
    bs.unblock(b["id"], a["id"])
    auth._handle_message_email(job)
    assert len(calls) == 1


# ── 2. login lock under concurrency ──
def _ip_hdr(ip):
    return {"X-Real-IP": ip}


def test_parallel_wrong_passwords_stop_at_the_lock(db, monkeypatch):
    u = _user()
    real = srv.authenticate_user
    monkeypatch.setattr(srv, "authenticate_user", lambda e, p: (time.sleep(0.05), real(e, p))[1])
    codes = [r.status_code for r in _burst(30, lambda i: client.post(
        "/auth/login", json={"email": u["email"], "password": "wrong-" + str(i)}, headers=_ip_hdr("198.51.100.7")))]
    print("login burst:", {c: codes.count(c) for c in set(codes)})
    assert set(codes) <= {401, 429}, codes
    limit = min(tw_settings.rate(n)[0] for n in srv._LOGIN_LOCKS)
    assert codes.count(401) <= limit <= tw_settings.rate("login_email")[0], codes
    r = client.post("/auth/login", json={"email": u["email"], "password": PW}, headers=_ip_hdr("198.51.100.7"))
    assert r.status_code == 429 and r.json()["error"]["code"] == "login_locked"   # same reply as before


def test_correct_login_after_two_failures_leaves_no_extra_hit(db):
    u, ip = _user(), "198.51.100.8"
    for _ in range(2):
        r = client.post("/auth/login", json={"email": u["email"], "password": "nope"}, headers=_ip_hdr(ip))
        assert r.status_code == 401
    assert client.post("/auth/login", json={"email": u["email"], "password": PW}, headers=_ip_hdr(ip)).status_code == 200
    assert "login_email:" + u["email"] not in srv._rate_store
    assert f"login_ip_email:{ip}|{u['email']}" not in srv._rate_store
    assert len(srv._rate_store["login_ip:" + ip]) == 2                  # the two failures only — success released


# ── 3. email links under concurrency ──
def _valid_links(uid, purposes):
    return _sql("SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = :u AND purpose = ANY(:p) "
                "AND expires_at > NOW()", u=uid, p=list(purposes))[0][0]


def test_parallel_email_token_issue_leaves_one_link(db):
    u = _user()
    _burst(10, lambda i: auth.email_token_issue("password_reset", u["id"]))
    n = _valid_links(u["id"], ["password_reset"])
    print("password_reset rows after 10 parallel issues:", n)
    assert n == 1
    purposes = ["email_change", "email_change_admin"]
    _burst(10, lambda i: auth.email_token_issue(purposes[i % 2], u["id"], f"n{i}@t.test"))
    assert _valid_links(u["id"], purposes) == 1
    assert _valid_links(u["id"], ["password_reset"]) == 1              # another purpose untouched


# ── 4. OTP shape ──
_BAD_CODES = ["1234567", "abcdef", "12345", "x" * 10000, "١٢٣٤٥٦", ""]


def _attempts(uid):
    return _sql("SELECT email_code_attempts, phone_code_attempts FROM kyc_submissions WHERE user_id = :u", u=uid)[0]


def test_kyc_code_shape_422_no_attempt(db, monkeypatch):
    monkeypatch.setattr(srv, "is_email_otp_delivery_available", lambda: True)
    monkeypatch.setattr(srv, "is_phone_otp_delivery_available", lambda: True)
    u = _user()
    _sql("INSERT INTO kyc_submissions (user_id, step) VALUES (:u, 'email')", u=u["id"])
    auth._otp_issue(u["id"], "email", u["email"])
    auth._otp_issue(u["id"], "phone", "+962790000000")
    for code in _BAD_CODES:
        for path in ("/kyc/email/verify", "/kyc/phone/verify"):
            r = client.post(path, json={"code": code}, headers=u["h"])
            assert r.status_code == 422, (path, code[:10], r.text)
            assert r.json()["details"][0]["loc"] == ["body", "code"]
    assert tuple(_attempts(u["id"])) == (0, 0)
    r = client.post("/kyc/email/verify", json={"code": " 000000 "}, headers=u["h"])   # right shape, wrong code
    assert r.status_code == 400 and _attempts(u["id"])[0] == 1


def test_guest_support_code_shape_422_no_attempt(db, monkeypatch):
    monkeypatch.setattr(email_service, "can_send", lambda *a, **k: True)
    email = f"g{uuid.uuid4().hex[:8]}@t.test"
    auth.guest_otp_issue(email)
    for code in _BAD_CODES:
        r = client.post("/support/guest/tickets", json={
            "email": email, "subject": "Login help", "body": "I cannot sign in to my account.", "code": code})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_code", (code[:10], r.text)
        assert auth.guest_otp_verify(email, code) is False
    assert _sql("SELECT attempts FROM support_guest_otp WHERE email = :e", e=email)[0][0] == 0


# ── 5. HSTS ──
def test_hsts_on_html_and_api():
    want = "max-age=31536000; includeSubDomains"
    assert client.get("/").headers.get("strict-transport-security") == want
    r = client.get("/messages/1/2")                                     # API reply (401 without a token)
    assert r.headers.get("strict-transport-security") == want
    assert "preload" not in want
