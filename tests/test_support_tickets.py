"""
test_support_tickets.py — task 7.1: support tickets (docs/rules/support.md · SYSTEMS_INDEX §62).

Behaviour over HTTP (real PostgreSQL, in-process client):
  1  ownership — another account's ticket = 404 (read · reply · close); the list shows own tickets only
  2  priority — only the admin sets it: `priority` in a user / guest body → 422; admin PUT changes it
  3  account limits — open tickets at once (support_open_max, also on reopen) · new tickets per window (support_create)
  4  guest — no / wrong code → refused · category other than account → 422 · with the code → ticket opens
     (category account, guest_email stored) · per email · per IP · global cap (tw_settings, security)
  5  reopen window — reply on a closed ticket reopens it within 14 days of closed_at, after that 409 reopen_expired;
     user reply → open · admin reply → awaiting_user
  6  support.manage — no token / user JWT → 401 · admin token without it → 403 · with it → 200
  7  audit — admin reply / status / priority = admin_audit_log rows (actor · action · ticket · old → new)

TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_support_tickets.py -q
"""
import os, sys, uuid

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
_ADMIN_SECRET = "test-admin-secret-71-" + "a" * 32
SENT = []   # (to, template, vars) — the guest code email


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    monkeypatch.setattr(email_service, "can_send", lambda key: True)
    monkeypatch.setattr(email_service, "send_email",
                        lambda to, key, vars, **kw: SENT.append((to, key, dict(vars))) or {"ok": True, "code": "sent"})
    SENT.clear()
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
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


def _user():
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id", t="U" + n, n="User" + n, e=n + "@t.test")[0]
    return {"id": int(uid), "tw": tw}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": u["id"], "user_type": "emp", "tw_id": u["tw"]})}


def _admin(perms=None, sub="owner"):
    return {"X-Admin-Token": srv._admin_jwt_issue(sub=sub, perms=perms)}


def _new(u, **over):
    body = {"category": "technical", "subject": "مشكلة", "body": "الصفحة ما بتفتح"}
    body.update(over)
    return client.post("/support/tickets", json=body, headers=_h(u))


def _open(u):
    r = _new(u)
    assert r.status_code == 201, r.text
    return r.json()["data"]["public_id"]


# ── 1 ownership ──
def test_other_accounts_ticket_is_404():
    a, b = _user(), _user()
    pid = _open(a)
    assert pid.startswith("H") and len(pid) == 11
    assert client.get(f"/support/tickets/{pid}", headers=_h(a)).status_code == 200
    assert client.get(f"/support/tickets/{pid}", headers=_h(b)).status_code == 404
    assert client.post(f"/support/tickets/{pid}/messages", json={"body": "رد"}, headers=_h(b)).status_code == 404
    assert client.post(f"/support/tickets/{pid}/close", headers=_h(b)).status_code == 404
    assert client.get("/support/tickets", headers=_h(b)).json()["data"]["items"] == []
    assert [t["public_id"] for t in client.get("/support/tickets", headers=_h(a)).json()["data"]["items"]] == [pid]
    assert client.get("/support/tickets").status_code == 401
    # nothing written by the refused calls
    assert _sql("SELECT COUNT(*) FROM support_messages m JOIN support_tickets t ON t.id = m.ticket_id "
                "WHERE t.public_id = :p", p=pid)[0][0] == 1


def test_input_checks():
    u = _user()
    assert _new(u, subject="   ").status_code == 422
    assert _new(u, body="").status_code == 422
    assert _new(u, subject="س" * 121).json()["error"]["code"] == "too_long"
    assert _new(u, body="س" * 5001).json()["error"]["field"] == "body"
    assert _new(u, category="billing").json()["error"]["code"] == "invalid_category"
    assert _new(u, subject="س" * 120, body="س" * 5000).status_code == 201


# ── 2 priority ──
def test_priority_only_from_the_admin():
    u = _user()
    r = _new(u, priority="urgent")
    assert r.status_code == 422 and r.json()["error"]["code"] == "priority_forbidden"
    pid = _open(u)
    assert "priority" not in client.get(f"/support/tickets/{pid}", headers=_h(u)).json()["data"]
    assert _sql("SELECT priority FROM support_tickets WHERE public_id = :p", p=pid)[0][0] == "normal"
    assert client.put(f"/admin/support/tickets/{pid}", json={"priority": "urgent"}, headers=_admin()).status_code == 200
    assert client.put(f"/admin/support/tickets/{pid}", json={"priority": "x"}, headers=_admin()).status_code == 422
    assert _sql("SELECT priority FROM support_tickets WHERE public_id = :p", p=pid)[0][0] == "urgent"
    g = client.post("/support/guest/tickets", json={"email": "p@t.test", "code": "1", "subject": "s", "body": "b",
                                                    "priority": "high"})
    assert g.status_code == 422 and g.json()["error"]["code"] == "priority_forbidden"


# ── 3 account limits ──
def test_open_max_and_create_rate():
    u = _user()
    tw_settings._set_overrides({"support_open_max": 2})
    p1, _ = _open(u), _open(u)
    r = _new(u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_open"
    client.post(f"/support/tickets/{p1}/close", headers=_h(u))
    third = _open(u)                                     # a closed one frees a place
    # reopening counts too
    r = client.post(f"/support/tickets/{p1}/messages", json={"body": "رجعت"}, headers=_h(u))
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_open"
    assert third
    srv._rate_store.clear()
    v = _user()
    tw_settings._set_overrides({"support_create_hits": 2})
    _open(v), _open(v)
    r = _new(v)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


# ── 4 guest ──
def _code(email):
    r = client.post("/support/guest/code", json={"email": email}, headers={"X-Real-IP": "7.7.7.7"})
    assert r.status_code == 200, r.text
    return SENT[-1][2]["code"]


def _guest(email, code, ip="7.7.7.7", **over):
    body = {"email": email, "code": code, "subject": "ما بقدر أدخل", "body": "كلمة السر ما بتزبط"}
    body.update(over)
    return client.post("/support/guest/tickets", json=body, headers={"X-Real-IP": ip})


def test_guest_needs_the_code_and_login_category():
    email = uuid.uuid4().hex[:8] + "@guest.test"
    assert _guest(email, "").status_code == 400
    assert _guest(email, "123456").json()["error"]["code"] == "invalid_code"     # no code sent yet
    code = _code(email)
    assert SENT[-1][:2] == (email, "support_guest_otp")
    assert _guest(email, code, category="technical").json()["error"]["code"] == "guest_category"
    wrong = "000000" if code != "000000" else "111111"
    assert _guest(email, wrong).status_code == 400
    r = _guest(email, code)
    assert r.status_code == 201, r.text
    pid = r.json()["data"]["public_id"]
    assert _sql("SELECT user_id, guest_email, category FROM support_tickets WHERE public_id = :p", p=pid)[0] \
        == [None, email, "account"]
    assert _sql("SELECT author_type FROM support_messages m JOIN support_tickets t ON t.id = m.ticket_id "
                "WHERE t.public_id = :p", p=pid) == [["guest"]]
    assert _guest(email, code).status_code == 400                                 # single use


def test_guest_limits_email_ip_global():
    email = uuid.uuid4().hex[:8] + "@guest.test"
    for _ in range(2):
        assert _guest(email, _code(email)).status_code == 201
    r = _guest(email, _code(email), ip="7.7.7.8")                                 # another IP — same email
    assert r.status_code == 429
    srv._rate_store.clear()
    for i in range(2):
        e = f"{uuid.uuid4().hex[:8]}@guest.test"
        assert _guest(e, _code(e), ip="5.5.5.5").status_code == 201
    e = f"{uuid.uuid4().hex[:8]}@guest.test"
    assert _guest(e, _code(e), ip="5.5.5.5").status_code == 429                  # same IP — new email
    srv._rate_store.clear()
    tw_settings._set_overrides({"support_guest_global_hits": 3})
    for i in range(3):
        e = f"{uuid.uuid4().hex[:8]}@guest.test"
        assert _guest(e, _code(e), ip=f"6.6.6.{i}").status_code == 201
    e = f"{uuid.uuid4().hex[:8]}@guest.test"
    assert _guest(e, _code(e), ip="6.6.6.99").status_code == 429                 # every IP / email new — global cap
    for key in ("support_guest_email_hits", "support_guest_ip_hits", "support_guest_global_hits"):
        assert tw_settings.is_security(key) and tw_settings.REGISTRY[key]["group"] == "sec_support"
    assert tw_settings.value("support_guest_global_hits") == 3 and tw_settings.REGISTRY["support_guest_global_hits"]["default"] == 60


# ── 5 reopen window + status ──
def test_reopen_within_14_days_only():
    u = _user()
    pid = _open(u)
    assert client.post(f"/admin/support/tickets/{pid}/messages", json={"body": "جرّب هيك"}, headers=_admin()).json()["data"]["status"] == "awaiting_user"
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "ما زبط"}, headers=_h(u))
    assert r.json()["data"]["status"] == "open"
    client.post(f"/support/tickets/{pid}/close", headers=_h(u))
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '13 days' WHERE public_id = :p", p=pid)
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "رجعت"}, headers=_h(u))
    assert r.status_code == 200 and r.json()["data"]["reopened"] is True
    assert _sql("SELECT status, closed_at FROM support_tickets WHERE public_id = :p", p=pid)[0] == ["open", None]
    client.post(f"/support/tickets/{pid}/close", headers=_h(u))
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '15 days' WHERE public_id = :p", p=pid)
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "رجعت"}, headers=_h(u))
    assert r.status_code == 409 and r.json()["error"]["code"] == "reopen_expired"
    assert client.get(f"/support/tickets/{pid}", headers=_h(u)).json()["data"]["can_reopen"] is False


# ── 6 permission ──
def test_support_manage_permission():
    pid = _open(_user())
    paths = [("get", "/admin/support/tickets", None), ("get", f"/admin/support/tickets/{pid}", None),
             ("post", f"/admin/support/tickets/{pid}/messages", {"body": "x"}),
             ("put", f"/admin/support/tickets/{pid}", {"status": "closed"})]
    for method, path, body in paths:
        kw = {"json": body} if body else {}
        assert getattr(client, method)(path, **kw).status_code == 401, path
        assert getattr(client, method)(path, headers=_h(_user()), **kw).status_code == 401, path
        assert getattr(client, method)(path, headers=_admin(["settings.edit"], "staff:3"), **kw).status_code == 403, path
    assert client.get("/admin/support/tickets", headers=_admin(["support.manage"], "staff:4")).status_code == 200
    items = client.get("/admin/support/tickets?status=open", headers=_admin()).json()["data"]["items"]
    assert items and all(t["status"] == "open" for t in items)
    assert client.get("/admin/support/tickets?status=nope", headers=_admin()).status_code == 422


# ── 7 audit ──
def test_admin_actions_audited():
    pid = _open(_user())
    _sql("DELETE FROM admin_audit_log")
    client.post(f"/admin/support/tickets/{pid}/messages", json={"body": "ردنا"}, headers=_admin(["support.manage"], "staff:9"))
    client.put(f"/admin/support/tickets/{pid}", json={"status": "closed", "priority": "high"}, headers=_admin())
    client.put(f"/admin/support/tickets/{pid}", json={"status": "open"}, headers=_admin(["reports.read"], "staff:2"))
    rows = _sql("SELECT actor, action, target, result, old_value, new_value FROM admin_audit_log ORDER BY id")
    assert rows[0] == ["staff:9", "admin_support_reply", f"ticket={pid}", "ok", "status=open", "status=awaiting_user"]
    assert rows[1] == ["owner", "admin_support_update", f"ticket={pid}", "ok",
                       "priority=normal;status=awaiting_user", "priority=high;status=closed"]
    assert rows[2][:4] == ["staff:2", "admin_support_update", f"ticket={pid}", "denied"]
    assert "ردنا" not in str(rows)                                               # never the message text
    assert _sql("SELECT closed_at IS NOT NULL FROM support_tickets WHERE public_id = :p", p=pid)[0][0] is True
