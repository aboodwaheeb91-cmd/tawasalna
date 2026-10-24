"""
test_support_reply_notice.py — task 7.2b: the notice of an admin reply (docs/rules/support.md → إشعارات الرد).

Behaviour over HTTP (real PostgreSQL, in-process client — BackgroundTasks run before the client returns):
  1  guest ticket → each admin reply = a new link (issue_guest_link keep=3 → 3 active) + one support_guest_reply
     email (ticket + link only — the reply text is not in its vars nor in the rendered email)
  2  account ticket → one bell support_reply per message (event_key support_reply:support_ticket:{id}:{msg}),
     link /support?ticket=H… · exactly one email (support_reply, SECURITY) even with every notification
     preference off — no second email through the notification → email mapping
  3  the email failing (raises / provider error) → the reply is still 200 · one log line without address / token
  4  support_guest_link switched off → reply 200, no new link, no email
  5  no raw token in any reply body or in the server output

TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_support_reply_notice.py -q
"""
import os, re, sys, uuid

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
SENT = []   # (to, template, vars)
_IP = {"X-Real-IP": "8.8.4.4"}
REPLY = "نص الرد السري من الدعم 7.2b"


def _record(to, key, vars=None, **kw):
    SENT.append((to, key, dict(vars or {})))
    return {"ok": True, "code": "sent"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-72b-" + "a" * 32)
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    monkeypatch.setattr(email_service, "can_send", lambda key: True)
    monkeypatch.setattr(email_service, "send_email", _record)
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


def _admin():
    return {"X-Admin-Token": srv._admin_jwt_issue(sub="owner", perms=None)}


def _reply(pid, status="awaiting_user"):
    return client.post(f"/admin/support/tickets/{pid}/messages", json={"body": REPLY, "next_status": status},
                       headers=_admin())


def _guest_ticket():
    email = uuid.uuid4().hex[:8] + "@guest.test"
    assert client.post("/support/guest/code", json={"email": email}, headers=_IP).status_code == 200
    r = client.post("/support/guest/tickets", json={"email": email, "code": SENT[-1][2]["code"],
                                                    "subject": "ما بقدر أدخل", "body": "الرمز ما بيوصل"}, headers=_IP)
    assert r.status_code == 201, r.text
    return email, r.json()["data"]["public_id"]


def _user():
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id", t="U" + n, n="User" + n, e=n + "@t.test")[0]
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": int(uid), "user_type": "emp", "tw_id": tw})}
    return int(uid), n + "@t.test", h


def _active_links(pid):
    return _sql("SELECT COUNT(*) FROM support_guest_access a JOIN support_tickets t ON t.id = a.ticket_id "
                "WHERE t.public_id = :p AND a.revoked_at IS NULL AND a.expires_at > NOW()", p=pid)[0][0]


# ── 1 + 5 guest ──
def test_guest_reply_new_link_keep_three_no_reply_text(capsys):
    email, pid = _guest_ticket()
    tokens = []
    for _ in range(3):
        SENT.clear()
        r = _reply(pid)
        assert r.status_code == 200, r.text
        assert [(to, key) for to, key, _ in SENT] == [(email, "support_guest_reply")]
        v = SENT[0][2]
        assert set(v) == {"ticket", "link"} and v["ticket"] == pid
        m = re.fullmatch(r"https://tawasolna\.com/support/track#t=([A-Za-z0-9_-]+)", v["link"])
        assert m, v["link"]
        tokens.append(m.group(1))
        assert m.group(1) not in r.text                               # never in the API reply
        msg = email_service.render("support_guest_reply", v)
        assert REPLY not in msg["html"] and REPLY not in msg["text"] and pid in msg["subject"]
    assert _active_links(pid) == 3                                     # 1 (ticket) + 3 new, keep=3
    assert client.post("/support/track/view", json={"token": tokens[-1]}, headers=_IP).status_code == 200
    out = capsys.readouterr().out
    assert not any(t in out for t in tokens) and email not in out


# ── 2 account ──
def test_account_bell_per_message_and_one_email_with_prefs_off(monkeypatch):
    uid, addr, h = _user()
    assert client.put("/my/email-notifications", headers=h,
                      json={"types": {k: False for k in email_service.PREF_TYPES}}).status_code == 200
    pid = client.post("/support/tickets", json={"category": "technical", "subject": "مشكلة", "body": "ما بتفتح"},
                      headers=h).json()["data"]["public_id"]
    # the real sender (SECURITY path) with a fake provider — counts what really leaves
    posts, queued = [], []
    monkeypatch.setattr(email_service, "send_email", _REAL_SEND)
    monkeypatch.setattr(email_service, "can_send", _REAL_CAN_SEND)
    monkeypatch.setattr(email_service, "_api_key", lambda: "re_test")
    monkeypatch.setattr(email_service, "_post", lambda payload, key: posts.append(payload) or (200, {"id": "x"}))
    monkeypatch.setattr(auth, "_email_submit", lambda *a: queued.append(a))
    for _ in range(2):
        assert _reply(pid).status_code == 200
    rows = _sql("SELECT type, link, event_key FROM notifications WHERE user_id = :u ORDER BY id", u=uid)
    mids = [r[0] for r in _sql("SELECT m.id FROM support_messages m JOIN support_tickets t ON t.id = m.ticket_id "
                               "WHERE t.public_id = :p AND m.author_type = 'admin' ORDER BY m.id", p=pid)]
    tid = _sql("SELECT id FROM support_tickets WHERE public_id = :p", p=pid)[0][0]
    assert [tuple(r) for r in rows] == [("support_reply", "/support?ticket=" + pid,
                                         f"support_reply:support_ticket:{tid}:{m}") for m in mids]
    assert [p["to"] for p in posts] == [[addr], [addr]]                # one email per reply, not two
    assert all(pid in p["subject"] and REPLY not in p["html"] and REPLY not in p["text"] for p in posts)
    assert queued == []                                                # no notification → email mapping
    # the same message again (idempotent event_key) → no second bell
    srv._support_reply_notice({"ticket_id": tid, "public_id": pid, "message_id": mids[-1], "user_id": uid,
                               "guest_email": None})
    assert len(_sql("SELECT 1 FROM notifications WHERE user_id = :u", u=uid)) == 2


# ── 3 failure ──
def test_email_failure_keeps_reply_ok(monkeypatch, capsys):
    uid, addr, h = _user()
    pid = client.post("/support/tickets", json={"category": "general", "subject": "س", "body": "ب"},
                      headers=h).json()["data"]["public_id"]
    email, gpid = _guest_ticket()

    def boom(*a, **kw):
        raise RuntimeError("provider down " + addr)
    monkeypatch.setattr(email_service, "send_email", boom)
    r = _reply(pid, "resolved")
    assert r.status_code == 200 and r.json()["data"]["status"] == "resolved"
    out = capsys.readouterr().out
    assert "[support] reply notice failed: RuntimeError" in out and addr not in out
    r = _reply(gpid)
    assert r.status_code == 200
    out = capsys.readouterr().out
    assert email not in out and "#t=" not in out


# ── 4 link type off ──
def test_guest_link_off_reply_ok_no_link(monkeypatch, capsys):
    email, pid = _guest_ticket()
    SENT.clear()
    monkeypatch.setattr(email_service, "can_send", lambda key: key != "support_guest_link")
    assert _reply(pid).status_code == 200
    assert SENT == [] and _active_links(pid) == 1
    assert "[support] guest reply notice skipped" in capsys.readouterr().out


_REAL_SEND = email_service.send_email
_REAL_CAN_SEND = email_service.can_send
