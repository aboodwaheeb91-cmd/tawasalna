"""
test_support_guest_link.py — task 7.2a: the guest follow-up link (docs/rules/support.md → رابط متابعة الزائر ·
ARCHITECTURE.md §81 → guest link security).

Behaviour over HTTP (real PostgreSQL, in-process client):
  1  guest ticket → a support_guest_link email (H number + /support/track#t=<token>) · the reply carries the H
     number only · the DB holds the sha256 hex only (no raw token in the DB or in the server output)
  2  view / reply / resolve with a session (code → verify — task 7.4; the link alone = H number + masked
     address) · wrong / expired / revoked link → the same 404 · last_used_at · a reply no longer extends the
     link (7.4) · reopen window 14 days · no internal data (author_id, priority)
  3  a link never reaches an account's ticket or another guest's ticket
  4  issue_guest_link keep=3 · resend revokes every link + a new one, same reply for a known / unknown email,
     only unresolved / resolved < 14 days, newest 5
  5  limits — support_link_resend_email (silent) · support_link_resend_ip · support_guest_reply_ticket ·
     support_track_ip (tw_settings, sec_support)
  6  headers on every /support/track path (page + API): no-store · no-referrer · noindex
  7  support_guest_link switched off → code / tickets 503 (no code issued, no ticket) · resend same reply, no new link

TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_support_guest_link.py -q
"""
import hashlib, os, re, sys, uuid

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
_IP = {"X-Real-IP": "8.8.4.4"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-72a-" + "a" * 32)
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


def _guest_ticket(email=None):
    """→ (email, public_id, token) through the real flow (code → ticket → link email)."""
    email = email or uuid.uuid4().hex[:8] + "@guest.test"
    for k in [k for k in list(srv._rate_store) if k.startswith(("support_guest_", "otp_send", "public_ip"))]:
        del srv._rate_store[k]                    # the 7.1 ticket limits are tested in test_support_tickets.py
    assert client.post("/support/guest/code", json={"email": email}, headers=_IP).status_code == 200
    code = SENT[-1][2]["code"]
    r = client.post("/support/guest/tickets", json={"email": email, "code": code, "subject": "ما بقدر أدخل",
                                                    "body": "الرمز ما بيوصل", "details": {"issue": "no_code"}},
                    headers=_IP)
    assert r.status_code == 201, r.text
    pid = r.json()["data"]["public_id"]
    return email, pid, _token_of(pid)


def _token_of(pid):
    to, key, v = SENT[-1]
    assert key == "support_guest_link" and v["ticket"] == pid
    m = re.fullmatch(r"https://tawasolna\.com/support/track#t=([A-Za-z0-9_-]+)", v["link"])
    assert m, v["link"]
    return m.group(1)


def _view(token, ip="8.8.4.4"):
    return client.post("/support/track/view", json={"token": token}, headers={"X-Real-IP": ip})


def _session(token):
    """7.4: the link + the emailed code → a session (the conversation needs it)."""
    for k in [k for k in list(srv._rate_store) if k.startswith(("support_track_code", "support_track_ip"))]:
        del srv._rate_store[k]
    assert client.post("/support/track/code", json={"token": token}, headers=_IP).status_code == 200
    to, key, v = SENT[-1]
    assert key == "support_guest_otp"
    r = client.post("/support/track/verify", json={"token": token, "code": v["code"]}, headers=_IP)
    assert r.status_code == 200, r.text
    return r.json()["data"]["session"]


def _sview(session, ip="8.8.4.4"):
    return client.post("/support/track/view", json={"session": session}, headers={"X-Real-IP": ip})


def _reply(session, body="لسا ما زبط", ip="8.8.4.4"):
    return client.post("/support/track/reply", json={"session": session, "body": body}, headers={"X-Real-IP": ip})


def _resend(email, ip="8.8.4.4"):
    return client.post("/support/track/resend", json={"email": email}, headers={"X-Real-IP": ip})


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ── 1 issue ──
def test_ticket_sends_link_hash_only(capsys):
    email, pid, token = _guest_ticket()
    assert SENT[-1][0] == email
    rows = _sql("SELECT a.token_hash FROM support_guest_access a JOIN support_tickets t ON t.id = a.ticket_id "
                "WHERE t.public_id = :p", p=pid)
    assert rows == [[_h(token)]]
    dump = str(_sql("SELECT * FROM support_guest_access")) + str(_sql("SELECT * FROM support_tickets"))
    assert token not in dump                                                     # never the raw token
    assert token not in capsys.readouterr().out                                  # nor in the server output
    assert len(token) >= 40


# ── 2 view / reply / resolve ──
def test_view_reply_resolve_and_404s():
    email, pid, token = _guest_ticket()
    sess = _session(token)
    r = _sview(sess)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["public_id"] == pid and d["status"] == "new" and d["details"] == {"issue": "no_code"}
    assert "priority" not in d and "legacy_category" not in d and "guest_email" not in d
    assert _sql("SELECT last_used_at IS NOT NULL FROM support_guest_access WHERE token_hash = :h", h=_h(token))[0][0]
    client.post(f"/admin/support/tickets/{pid}/messages", json={"body": "جرّب", "next_status": "awaiting_user"},
                headers={"X-Admin-Token": srv._admin_jwt_issue(sub="staff:7")})
    msgs = _sview(sess).json()["data"]["messages"]
    assert [m["author_type"] for m in msgs] == ["guest", "admin"] and all("author_id" not in m for m in msgs)
    _sql("UPDATE support_guest_access SET expires_at = NOW() + INTERVAL '1 day' WHERE token_hash = :h", h=_h(token))
    r = _reply(sess)
    assert r.status_code == 200 and r.json()["data"]["status"] == "in_review"
    assert _sql("SELECT expires_at < NOW() + INTERVAL '2 days' FROM support_guest_access WHERE token_hash = :h",
                h=_h(token))[0][0] is True                                       # 7.4: no longer extended
    assert client.post("/support/track/resolve", json={"session": sess}, headers=_IP).json()["data"]["status"] == "resolved"
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '15 days' WHERE public_id = :p", p=pid)
    assert _reply(sess).status_code == 409
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '13 days' WHERE public_id = :p", p=pid)
    assert _reply(sess).json()["data"]["reopened"] is True
    # wrong / expired / revoked / malformed → the same 404
    wrong = _view("A" * 43).json()
    _sql("UPDATE support_guest_access SET expires_at = NOW() - INTERVAL '1 second' WHERE token_hash = :h", h=_h(token))
    expired = _view(token).json()
    _, _, t2 = _guest_ticket()
    _sql("UPDATE support_guest_access SET revoked_at = NOW() WHERE token_hash = :h", h=_h(t2))
    revoked = _view(t2).json()
    for res in (wrong, expired, revoked, _view("").json(), _view(None).json(),
                client.post("/support/track/verify", json={"token": token, "code": "123456"}, headers=_IP).json()):
        assert res == wrong and res["error"]["code"] == "not_found"


# ── 3 isolation ──
def test_link_reaches_its_own_guest_ticket_only():
    _, pid_a, token_a = _guest_ticket()
    _, pid_b, _ = _guest_ticket()
    assert _view(token_a).json()["data"]["ticket"] == pid_a
    # a link row pointing at an account's ticket never opens it
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES "
                   "(:t, 'U', :e, 'x', 'emp') RETURNING id, tw_id", t="U" + uuid.uuid4().hex[:10],
                   e=uuid.uuid4().hex[:8] + "@t.test")[0]
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": tw})}
    upid = client.post("/support/tickets", json={"category": "jobs", "subject": "s", "body": "b"}, headers=h).json()["data"]["public_id"]
    tid = _sql("SELECT id FROM support_tickets WHERE public_id = :p", p=upid)[0][0]
    tok = support.issue_guest_link(tid)
    assert _view(tok).status_code == 404 and _reply(tok).status_code == 401
    assert _sql("SELECT COUNT(*) FROM support_messages WHERE ticket_id = :t", t=tid)[0][0] == 1
    assert pid_b not in str(_view(token_a).json())


# ── 4 keep=3 + resend ──
def test_keep_three_and_resend_revokes_all():
    email, pid, first = _guest_ticket()
    tid = _sql("SELECT id FROM support_tickets WHERE public_id = :p", p=pid)[0][0]
    toks = [first] + [support.issue_guest_link(tid) for _ in range(4)]
    active = [r[0] for r in _sql("SELECT token_hash FROM support_guest_access WHERE ticket_id = :t AND revoked_at IS NULL "
                                 "ORDER BY id", t=tid)]
    assert active == [_h(t) for t in toks[-3:]]
    assert _view(toks[0]).status_code == 404 and _view(toks[-1]).status_code == 200
    # resend: same reply for a known and an unknown address; known → every old link revoked + one new each
    _, pid2, _ = _guest_ticket(email)
    _, pid3, _ = _guest_ticket(email)
    _sql("UPDATE support_tickets SET status = 'resolved', closed_at = NOW() - INTERVAL '20 days' WHERE public_id = :p", p=pid3)
    SENT.clear()
    srv._rate_store.clear()
    known, unknown = _resend(email.upper()), _resend("nobody-" + uuid.uuid4().hex[:6] + "@guest.test")
    assert known.status_code == unknown.status_code == 200 and known.json() == unknown.json()
    assert sorted(v["ticket"] for _, k, v in SENT if k == "support_guest_link") == sorted([pid, pid2])
    assert all(to == email for to, _, _ in SENT)
    for t in toks:
        assert _view(t).status_code == 404
    new = {v["ticket"]: v["link"].split("#t=")[1] for _, _, v in SENT}
    assert _view(new[pid]).json()["data"]["ticket"] == pid
    assert _sql("SELECT COUNT(*) FROM support_guest_access WHERE ticket_id = :t AND revoked_at IS NULL", t=tid)[0][0] == 1


def test_resend_newest_five():
    email = uuid.uuid4().hex[:8] + "@guest.test"
    pids = [_guest_ticket(email)[1] for _ in range(6)]
    SENT.clear()
    srv._rate_store.clear()
    _resend(email)
    assert sorted(v["ticket"] for _, _, v in SENT) == sorted(pids[1:])


# ── 5 limits ──
def test_limits():
    for key in ("support_link_resend_email_hits", "support_link_resend_ip_hits", "support_guest_reply_ticket_hits",
                "support_track_ip_hits"):
        assert tw_settings.is_security(key) and tw_settings.REGISTRY[key]["group"] == "sec_support", key
    assert tw_settings.rate("support_link_resend_email") == (3, 3600)
    assert tw_settings.rate("support_link_resend_ip") == (10, 3600)
    assert tw_settings.rate("support_guest_reply_ticket") == (20, 3600)
    assert tw_settings.rate("support_track_ip") == (60, 60)
    email, pid, token = _guest_ticket()
    srv._rate_store.clear()
    SENT.clear()
    for _ in range(4):                                                           # per email: silent after 3
        assert _resend(email, ip="1.1.1.1").status_code == 200
    assert len(SENT) == 3
    token = SENT[-1][2]["link"].split("#t=")[1]                                  # the resend revoked the old one
    sess = _session(token)
    tw_settings._set_overrides({"support_link_resend_ip_hits": 2})
    srv._rate_store.clear()
    assert _resend("a@x.test", ip="2.2.2.2").status_code == 200
    assert _resend("b@x.test", ip="2.2.2.2").status_code == 200
    assert _resend("c@x.test", ip="2.2.2.2").status_code == 429
    srv._rate_store.clear()
    tw_settings._set_overrides({"support_guest_reply_ticket_hits": 2})
    assert _reply(sess, ip="3.3.3.1").status_code == 200
    assert _reply(sess, ip="3.3.3.2").status_code == 200
    n = _sql("SELECT COUNT(*) FROM support_messages m JOIN support_tickets t ON t.id = m.ticket_id WHERE t.public_id = :p", p=pid)[0][0]
    r = _reply(sess, ip="3.3.3.3")                                              # per ticket — any IP
    assert r.status_code == 429
    assert _sql("SELECT COUNT(*) FROM support_messages m JOIN support_tickets t ON t.id = m.ticket_id WHERE t.public_id = :p", p=pid)[0][0] == n
    srv._rate_store.clear()
    tw_settings._set_overrides({"support_track_ip_hits": 10})
    for _ in range(10):
        assert _view(token, ip="4.4.4.4").status_code == 200
    assert _view(token, ip="4.4.4.4").status_code == 429
    assert _view("B" * 43, ip="4.4.4.4").status_code == 429                      # counted before the lookup


# ── 6 headers ──
def test_track_headers():
    _, _, token = _guest_ticket()
    res = [client.get("/support/track"), _view(token), _view("C" * 43), _reply(token, body=""),
           client.post("/support/track/code", json={"token": token}, headers=_IP),
           client.post("/support/track/verify", json={"token": token, "code": "1"}, headers=_IP),
           client.post("/support/track/resolve", json={"token": "x"}, headers=_IP), _resend("q@x.test")]
    assert res[0].status_code == 200 and "text/html" in res[0].headers["content-type"]
    for r in res:
        assert r.headers["Cache-Control"] == "no-store", r.url
        assert r.headers["Referrer-Policy"] == "no-referrer", r.url
        assert r.headers["X-Robots-Tag"] == "noindex", r.url
    assert client.get("/support").headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ── 7 support_guest_link off → fail closed ──
def test_link_type_off_fails_closed(monkeypatch):
    email, pid, _ = _guest_ticket()                                              # one ticket while the type is on
    monkeypatch.setattr(email_service, "can_send", lambda key: key != "support_guest_link")
    other = uuid.uuid4().hex[:8] + "@guest.test"
    SENT.clear()
    r = client.post("/support/guest/code", json={"email": other}, headers=_IP)
    assert r.status_code == 503 and r.json()["error"]["code"] == "otp_delivery_unavailable"
    assert SENT == [] and _sql("SELECT COUNT(*) FROM support_guest_otp WHERE email = :e", e=other)[0][0] == 0
    n = _sql("SELECT COUNT(*) FROM support_tickets")[0][0]
    r = client.post("/support/guest/tickets", json={"email": other, "code": "123456", "subject": "s", "body": "b"},
                    headers=_IP)
    assert r.status_code == 503 and r.json()["error"]["code"] == "otp_delivery_unavailable"
    assert _sql("SELECT COUNT(*) FROM support_tickets")[0][0] == n
    links = _sql("SELECT COUNT(*) FROM support_guest_access")[0][0]
    srv._rate_store.clear()
    off, unknown = _resend(email), _resend("nobody-" + uuid.uuid4().hex[:6] + "@guest.test")
    assert off.status_code == unknown.status_code == 200 and off.json() == unknown.json()
    assert SENT == [] and _sql("SELECT COUNT(*) FROM support_guest_access")[0][0] == links
