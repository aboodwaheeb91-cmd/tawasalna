"""
test_support_inbound.py — task 7.3: inbound support mail (Resend Receiving → tickets · docs/rules/support.md →
البريد الوارد).

Behaviour over HTTP (real PostgreSQL, in-process client). Resend is fake: the received email comes from a
monkeypatched email_service.fetch_received, outgoing emails are recorded — no real email, no network.
  1  Svix signature: right → 200 · wrong → 401 · timestamp older than 5 min → 401 · secret missing → 503
  2  the same event twice (same svix-id, or same email_id) → one ticket, the second has no effect
  3  a recipient outside info@ / support@ / support+<token>@ → 200, nothing created
  4  new email from an account's address → a GUEST ticket (user_id NULL · source email · category general) +
     the admin's «matches account» hint — never linked
  5  admin reply → the email carries Reply-To support+<token>@ (token stored as sha256 only) · a reply with that
     token + the owner's From → a message on the ticket · same token + another From → ignored
  6  Auto-Submitted ≠ no → ignored · mailer-daemon → ignored
  7  HTML only → plain text (tags + script removed) · cut at support_body_max
  8  switch types.support_inbound off (default) → 200, nothing written
  9  send_email: reply_to outside the support templates → invalid (nothing sent)

TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_support_inbound.py -q
"""
import base64, hashlib, hmac, json, os, sys, time, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server as srv
import tw_settings

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
SECRET = "whsec_" + base64.b64encode(b"inbound-test-key-7.3-" + b"k" * 11).decode()
MAILS = {}    # email_id → the "received email" Resend would return
SENT = []     # (to, template, vars, reply_to)
PATH = "/webhooks/resend/inbound"


def _record(to, key, vars=None, **kw):
    SENT.append((to, key, dict(vars or {}), kw.get("reply_to")))
    return {"ok": True, "code": "sent"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-73-" + "a" * 32)
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    monkeypatch.setattr(email_service, "fetch_received", lambda eid, mx: (MAILS[eid], None))
    monkeypatch.setattr(email_service, "can_send", lambda key: True)
    monkeypatch.setattr(email_service, "send_email", _record)
    before = email_service.get_settings()
    email_service.set_settings(email_service.validate_settings({"types": {"support_inbound": True}}, before))
    SENT.clear()
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield
    email_service.set_settings(before)
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


def _sign(raw: bytes, msg_id: str, ts: int, secret: str = SECRET) -> str:
    key = base64.b64decode(secret.split("_", 1)[1])
    return "v1," + base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + raw, hashlib.sha256).digest()).decode()


def _post(to, sender="Sami <sami@example.org>", subject="مشكلة", text="نص الرسالة", html=None, headers=None,
          svix_id=None, email_id=None, ts=None, sig=None):
    email_id = email_id or str(uuid.uuid4())
    svix_id = svix_id or "msg_" + uuid.uuid4().hex
    MAILS[email_id] = {"id": email_id, "from": sender, "to": to, "subject": subject, "text": text, "html": html,
                       "headers": headers or {}}
    raw = json.dumps({"type": "email.received", "created_at": "2026-10-24T00:00:00Z",
                      "data": {"email_id": email_id, "from": sender, "to": to, "subject": subject}}).encode()
    ts = int(time.time()) if ts is None else ts
    h = {"svix-id": svix_id, "svix-timestamp": str(ts), "svix-signature": sig or _sign(raw, svix_id, ts),
         "content-type": "application/json", "X-Real-IP": "44.0.0." + str(len(MAILS) % 250)}
    return client.post(PATH, content=raw, headers=h), svix_id, email_id


def _tickets(email):
    return _sql("SELECT id, public_id, user_id, category, source, subject FROM support_tickets "
                "WHERE guest_email = :e ORDER BY id", e=email)


def _admin():
    return {"X-Admin-Token": srv._admin_jwt_issue(sub="owner", perms=None)}


def _addr():
    return uuid.uuid4().hex[:10] + "@example.org"


# ── 1 signature ──
def test_signature_right_wrong_old_missing(monkeypatch):
    a = _addr()
    r, _, _ = _post(["support@tawasolna.com"], sender=a, sig="v1," + base64.b64encode(b"x" * 32).decode())
    assert r.status_code == 401
    r, _, _ = _post(["support@tawasolna.com"], sender=a, ts=int(time.time()) - 301)
    assert r.status_code == 401
    assert _tickets(a) == []
    r, _, _ = _post(["support@tawasolna.com"], sender=a)
    assert r.status_code == 200, r.text
    assert len(_tickets(a)) == 1
    monkeypatch.delenv("RESEND_WEBHOOK_SECRET")
    r, _, _ = _post(["support@tawasolna.com"], sender=_addr())
    assert r.status_code == 503


# ── 2 duplicate ──
def test_duplicate_event_no_effect():
    a = _addr()
    r, svix_id, email_id = _post(["info@tawasolna.com"], sender=a)
    assert r.status_code == 200 and len(_tickets(a)) == 1
    r, _, _ = _post(["info@tawasolna.com"], sender=a, svix_id=svix_id)            # same svix-id (retry)
    assert r.status_code == 200
    r, _, _ = _post(["info@tawasolna.com"], sender=a, email_id=email_id)          # same email, new event id
    assert r.status_code == 200
    assert len(_tickets(a)) == 1
    assert _sql("SELECT COUNT(*) FROM support_inbound_events WHERE email_id = :e", e=email_id)[0][0] == 1


# ── 3 recipient ──
def test_recipient_not_allowed_ignored():
    a = _addr()
    for to in (["sales@tawasolna.com"], ["support@other.com"], ["support+nothex@tawasolna.com"]):
        r, _, _ = _post(to, sender=a)
        assert r.status_code == 200
    assert _tickets(a) == []


# ── 4 new ticket from an account's address = guest + hint ──
def test_account_email_makes_guest_ticket_with_hint():
    n = uuid.uuid4().hex[:10]
    email = n + "@acc.test"
    _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES (:t, :n, :e, 'x', 'emp')",
         t="U" + n, n="User" + n, e=email)
    r, _, _ = _post(["Support <SUPPORT@tawasolna.com>"], sender=f"User <{email.upper()}>", subject="")
    assert r.status_code == 200, r.text
    rows = _tickets(email)
    assert len(rows) == 1
    _, pid, uid, cat, source, subject = rows[0]
    assert uid is None and cat == "general" and source == "email"
    assert subject == srv._tw_text("support.inbound.no_subject")
    t = client.get(f"/admin/support/tickets/{pid}", headers=_admin()).json()["data"]
    assert t["requester"] == {"kind": "guest", "email": email, "matches_account": True}
    assert t["source"] == "email"
    other = _addr()
    _post(["support@tawasolna.com"], sender=other)
    pid2 = _tickets(other)[0][1]
    assert client.get(f"/admin/support/tickets/{pid2}", headers=_admin()).json()["data"]["requester"]["matches_account"] is False


# ── 5 reply by email ──
def test_reply_token_owner_only():
    a = _addr()
    _post(["support@tawasolna.com"], sender=a)
    tid, pid = _tickets(a)[0][:2]
    r = client.post(f"/admin/support/tickets/{pid}/messages", json={"body": "رد", "next_status": "awaiting_user"},
                    headers=_admin())
    assert r.status_code == 200, r.text
    [(to, key, _, reply_to)] = SENT
    assert (to, key) == (a, "support_guest_reply")
    assert reply_to.startswith("support+") and reply_to.endswith("@tawasolna.com")
    token = reply_to.split("+", 1)[1].split("@", 1)[0]
    stored = [h for (h,) in _sql("SELECT token_hash FROM support_reply_tokens WHERE ticket_id = :t", t=tid)]
    assert hashlib.sha256(token.encode()).hexdigest() in stored and token not in stored

    def count():
        return _sql("SELECT COUNT(*) FROM support_messages WHERE ticket_id = :t", t=tid)[0][0]
    n0 = count()
    r, _, _ = _post([reply_to], sender="intruder@example.org", text="محاولة")
    assert r.status_code == 200 and count() == n0
    r, _, _ = _post([reply_to], sender=f"Me <{a}>", text="شكراً، لسا المشكلة موجودة")
    assert r.status_code == 200 and count() == n0 + 1
    st = _sql("SELECT status FROM support_tickets WHERE id = :t", t=tid)[0][0]
    assert st == "in_review"
    assert _sql("SELECT author_type FROM support_messages WHERE ticket_id = :t ORDER BY id DESC LIMIT 1", t=tid)[0][0] == "guest"
    assert len(_tickets(a)) == 1   # a reply never opens a new ticket


# ── 6 automatic mail ──
def test_auto_submitted_and_daemon_ignored():
    a = _addr()
    r, _, _ = _post(["support@tawasolna.com"], sender=a, headers={"auto-submitted": "auto-replied"})
    assert r.status_code == 200
    r, _, _ = _post(["support@tawasolna.com"], sender="MAILER-DAEMON@example.org")
    assert r.status_code == 200
    assert _tickets(a) == [] and _tickets("mailer-daemon@example.org") == []
    r, _, _ = _post(["support@tawasolna.com"], sender=a, headers={"Auto-Submitted": "no"})
    assert len(_tickets(a)) == 1


# ── 7 HTML → text + cut ──
def test_html_to_text_and_cut():
    a = _addr()
    html = "<p>مرحبا <b>فريق</b></p><script>alert(1)</script><style>p{}</style><div>" + "ك" * 9000 + "</div>"
    _post(["support@tawasolna.com"], sender=a, text=None, html=html)
    tid = _tickets(a)[0][0]
    body = _sql("SELECT body FROM support_messages WHERE ticket_id = :t", t=tid)[0][0]
    assert body.startswith("مرحبا فريق")
    assert "<" not in body and "alert" not in body
    assert len(body) <= tw_settings.limit("support_body_max")


# ── 8 switch off ──
def test_switch_off_no_effect():
    email_service.set_settings(email_service.validate_settings({"types": {"support_inbound": False}},
                                                               email_service.get_settings()))
    a = _addr()
    r, svix_id, _ = _post(["support@tawasolna.com"], sender=a)
    assert r.status_code == 200
    assert _tickets(a) == []
    assert _sql("SELECT COUNT(*) FROM support_inbound_events WHERE svix_id = :s", s=svix_id)[0][0] == 0
    assert email_service.DEFAULTS["types"]["support_inbound"] is False   # off until the admin turns it on


# ── 9 reply_to allowlist ──
def test_reply_to_only_support_templates(monkeypatch):
    monkeypatch.undo()   # the real send_email (no key → would stop later; the allowlist answers first)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_never_used")
    monkeypatch.setattr(email_service, "_post", lambda payload, key: pytest.fail("must not send"))
    res = email_service.send_email("x@example.org", "password_reset", {"link": "https://tawasolna.com/x"},
                                   reply_to="support+" + "a" * 32 + "@tawasolna.com")
    assert res == {"ok": False, "code": "invalid"}
