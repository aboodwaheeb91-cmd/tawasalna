"""
test_support_track_session.py — task 7.4: the guest follow-up link names the ticket only; the conversation
needs a session after a code to the ticket's own address (docs/rules/support.md → رابط متابعة الزائر).

Behaviour over HTTP (real PostgreSQL, in-process client, fake Resend):
  1  link only → H number + masked address, no subject / status / messages · reply / resolve with the link
     token (as token or as session) → 401
  2  /support/track/code → the STORED guest_email only (an email in the body is ignored) · same reply for a
     wrong link · cooldown + per-ticket hourly cap (same reply, no email) · per-IP → 429
  3  verify → a session that opens its own ticket only · both keys → the session only (bad session → 401,
     no fallback to the link) · a session row on an account ticket → 401
  4  code of ticket A never verifies on B · the «open a ticket» code never opens a session (and the other
     way round) · a used code fails · the last wrong attempt kills the code · two concurrent verifies with
     one code → one session
  5  session: ≤ 24 h, never extended · expired / revoked → 401 · admin reply (new link, keep=3) keeps it ·
     track/resend revokes it

TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_support_track_session.py -q
"""
import os, re, sys, threading, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server as srv
import support
import tw_settings

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
SENT = []   # (to, template, vars)
_IP = {"X-Real-IP": "8.8.4.5"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-74-" + "a" * 32)
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    monkeypatch.setattr(email_service, "can_send", lambda key: True)
    monkeypatch.setattr(email_service, "send_email",
                        lambda to, key, vars, **kw: SENT.append((to, key, dict(vars))) or {"ok": True, "code": "sent"})
    SENT.clear()
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield
    tw_settings._set_overrides({})
    srv._rate_store.clear()


def _db_params():
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    return dict(host=host, port=int(port), user=user, password=pw, database=name.split("?")[0])


@pytest.fixture(scope="module", autouse=True)
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _post(action, body, ip=None):
    return client.post("/support/track/" + action, json=body, headers={"X-Real-IP": ip} if ip else _IP)


def _guest_ticket(email=None):
    """→ (email, public_id, link token) through the real flow (code → ticket → link email)."""
    email = email or "ab" + uuid.uuid4().hex[:6] + "@guest.test"
    srv._rate_store.clear()
    assert client.post("/support/guest/code", json={"email": email}, headers=_IP).status_code == 200
    r = client.post("/support/guest/tickets", json={"email": email, "code": SENT[-1][2]["code"], "subject": "سري",
                                                    "body": "نص المحادثة"}, headers=_IP)
    assert r.status_code == 201, r.text
    to, key, v = SENT[-1]
    assert key == "support_guest_link"
    return email, r.json()["data"]["public_id"], re.search(r"#t=([A-Za-z0-9_-]+)$", v["link"]).group(1)


def _code(token):
    """Asks for a code (cooldown cleared) → the plain code from the fake email (None when nothing sent)."""
    for k in [k for k in list(srv._rate_store) if k.startswith("support_track_code")]:
        del srv._rate_store[k]
    n = len(SENT)
    assert _post("code", {"token": token}).status_code == 200
    return SENT[-1][2]["code"] if len(SENT) > n else None


def _session(token):
    r = _post("verify", {"token": token, "code": _code(token)})
    assert r.status_code == 200, r.text
    return r.json()["data"]["session"]


def _tid(pid):
    return _sql("SELECT id FROM support_tickets WHERE public_id = :p", p=pid)[0][0]


# ── 1 the link alone ──
def test_link_only_names_the_ticket():
    email, pid, token = _guest_ticket()
    r = _post("view", {"token": token})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d == {"ticket": pid, "email": email[0] + "***@guest.test", "verified": False}
    assert "سري" not in r.text and "نص المحادثة" not in r.text
    for action, body in (("reply", {"token": token, "body": "x"}), ("reply", {"session": token, "body": "x"}),
                         ("resolve", {"token": token}), ("resolve", {"session": token}),
                         ("view", {"session": token})):
        res = _post(action, body)
        assert res.status_code == 401 and res.json()["error"]["code"] == "session_required", (action, body)
    assert _sql("SELECT COUNT(*) FROM support_messages WHERE ticket_id = :t", t=_tid(pid))[0][0] == 1
    assert _post("view", {"token": "Z" * 43}).status_code == 404


# ── 2 sending the code ──
def test_code_goes_to_stored_address_with_limits():
    email, pid, token = _guest_ticket()
    SENT.clear()
    r = _post("code", {"token": token, "email": "attacker@evil.test"})
    assert r.status_code == 200 and r.json()["data"]["cooldown_s"] == 60
    assert [(to, key) for to, key, _ in SENT] == [(email, "support_guest_otp")]
    same = _post("code", {"token": token})                                       # cooldown → same reply, no email
    wrong = _post("code", {"token": "Q" * 43})
    assert same.json() == wrong.json() == r.json() and len(SENT) == 1
    hits = tw_settings.rate("support_track_code_ticket")[0]
    for _ in range(hits - 1):
        srv._rate_store.pop(f"support_track_code_gap:{_tid(pid)}", None)
        _post("code", {"token": token}, ip="9.9.9.1")
    assert len(SENT) == hits
    srv._rate_store.pop(f"support_track_code_gap:{_tid(pid)}", None)
    assert _post("code", {"token": token}, ip="9.9.9.2").status_code == 200 and len(SENT) == hits   # hourly cap
    tw_settings._set_overrides({})
    srv._rate_store.clear()
    for _ in range(tw_settings.rate("support_track_code_ip")[0]):
        _post("code", {"token": "Q" * 43}, ip="9.9.9.3")
    assert _post("code", {"token": token}, ip="9.9.9.3").status_code == 429


# ── 3 the session ──
def test_session_opens_its_own_ticket_only():
    _, pid_a, tok_a = _guest_ticket()
    _, pid_b, tok_b = _guest_ticket()
    sa = _session(tok_a)
    r = _post("view", {"session": sa})
    assert r.status_code == 200 and r.json()["data"]["public_id"] == pid_a
    assert r.json()["data"]["messages"][0]["body"] == "نص المحادثة"
    both = _post("view", {"session": sa, "token": tok_b})                        # session wins
    assert both.json()["data"]["public_id"] == pid_a
    assert _post("view", {"session": "B" * 43, "token": tok_a}).status_code == 401   # no fallback to the link
    assert _post("reply", {"session": sa, "body": "رد"}).json()["data"]["status"] == "in_review"
    assert _sql("SELECT COUNT(*) FROM support_messages WHERE ticket_id = :t", t=_tid(pid_b))[0][0] == 1
    raw = _sql("SELECT token_hash, expires_at <= NOW() + INTERVAL '24 hours' FROM support_guest_sessions "
               "WHERE ticket_id = :t", t=_tid(pid_a))
    assert len(raw) == 1 and raw[0][0] != sa and raw[0][1] is True              # hash only · ≤ 24 h
    # a session row on an account's ticket never opens it
    uid = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES "
               "(:t, 'U', :e, 'x', 'emp') RETURNING id", t="U" + uuid.uuid4().hex[:10],
               e=uuid.uuid4().hex[:8] + "@t.test")[0][0]
    _sql("UPDATE support_guest_sessions SET ticket_id = (SELECT id FROM support_tickets WHERE public_id = :p) "
         "WHERE ticket_id = :t", p=pid_b, t=_tid(pid_a))
    _sql("UPDATE support_tickets SET user_id = :u WHERE public_id = :p", u=uid, p=pid_b)
    assert _post("view", {"session": sa}).status_code == 401


# ── 4 codes never cross ──
def test_codes_do_not_cross():
    email_a, pid_a, tok_a = _guest_ticket()
    _, pid_b, tok_b = _guest_ticket()
    code_a = _code(tok_a)
    assert _post("verify", {"token": tok_b, "code": code_a}).status_code == 422   # A's code on B
    # the «open a ticket» code of the same address never opens a session …
    srv._rate_store.clear()
    client.post("/support/guest/code", json={"email": email_a}, headers=_IP)
    form_code = SENT[-1][2]["code"]
    r = _post("verify", {"token": tok_a, "code": form_code})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_code"
    # … and the follow-up code never opens a ticket (the pending form code stays valid)
    track_code = _code(tok_a)
    r = client.post("/support/guest/tickets", json={"email": email_a, "code": track_code, "subject": "s", "body": "b"},
                    headers=_IP)
    assert r.status_code == 400
    assert _sql("SELECT COUNT(*) FROM support_guest_otp WHERE email = :e", e=email_a)[0][0] == 1
    # single use
    assert _post("verify", {"token": tok_a, "code": track_code}).status_code == 200
    assert _post("verify", {"token": tok_a, "code": track_code}).status_code == 422
    # the last wrong attempt kills the code
    good = _code(tok_b)
    bad = "000000" if good != "000000" else "111111"
    for _ in range(auth.otp_max_attempts()):
        assert _post("verify", {"token": tok_b, "code": bad}).status_code == 422
    assert _sql("SELECT COUNT(*) FROM support_track_otp WHERE ticket_id = :t", t=_tid(pid_b))[0][0] == 0
    assert _post("verify", {"token": tok_b, "code": good}).status_code == 422


def test_concurrent_verify_one_session():
    _, pid, token = _guest_ticket()
    code = _code(token)
    barrier, out = threading.Barrier(2), []

    def go():
        barrier.wait()
        out.append(support.guest_verify(token, code, 24))
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(x is None for x in out) == [False, True]
    assert _sql("SELECT COUNT(*) FROM support_guest_sessions WHERE ticket_id = :t", t=_tid(pid))[0][0] == 1


# ── 5 lifetime + revocation ──
def test_session_expiry_and_revocation():
    email, pid, token = _guest_ticket()
    tid = _tid(pid)
    s1 = _session(token)
    exp = _sql("SELECT expires_at FROM support_guest_sessions WHERE ticket_id = :t", t=tid)[0][0]
    assert _post("view", {"session": s1}).status_code == 200
    assert _sql("SELECT expires_at FROM support_guest_sessions WHERE ticket_id = :t", t=tid)[0][0] == exp   # not extended
    # admin reply → a new link (keep=3) + email — the session stays valid
    r = client.post(f"/admin/support/tickets/{pid}/messages", json={"body": "جرّب", "next_status": "awaiting_user"},
                    headers={"X-Admin-Token": srv._admin_jwt_issue(sub="staff:7")})
    assert r.status_code == 200 and SENT[-1][1] == "support_guest_reply"
    assert _post("view", {"session": s1}).status_code == 200
    # expired → 401
    _sql("UPDATE support_guest_sessions SET expires_at = NOW() - INTERVAL '1 second' WHERE ticket_id = :t", t=tid)
    assert _post("view", {"session": s1}).status_code == 401
    # resend → every session + link + pending code revoked
    s2 = _session(token)
    _code(token)
    srv._rate_store.clear()
    assert client.post("/support/track/resend", json={"email": email}, headers=_IP).status_code == 200
    for action, body in (("view", {"session": s2}), ("reply", {"session": s2, "body": "x"}), ("resolve", {"session": s2})):
        assert _post(action, body).status_code == 401
    assert _post("view", {"token": token}).status_code == 404
    assert _sql("SELECT COUNT(*) FROM support_track_otp WHERE ticket_id = :t", t=tid)[0][0] == 0
    new = SENT[-1][2]["link"].split("#t=")[1]
    assert _post("view", {"session": _session(new)}).json()["data"]["public_id"] == pid
