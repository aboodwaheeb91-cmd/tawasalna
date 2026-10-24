"""
test_support_tickets.py — task 7.1: support tickets (docs/rules/support.md · SYSTEMS_INDEX §62).

Behaviour over HTTP (real PostgreSQL, in-process client):
  1  ownership — another account's ticket = 404 (read · reply · close); the list shows own tickets only
  2  priority — only the admin sets it: `priority` in a user / guest body → 422; admin PUT changes it
  3  account limits — open tickets at once (support_open_max, also on reopen) · new tickets per window (support_create)
  4  guest — no / wrong code → refused · category other than account → 422 · with the code → ticket opens
     (category account, guest_email stored) · per email · per IP · global cap (tw_settings, security)
  5  statuses (7.2a) — every transition (support.transition) · reopen within 14 days of closed_at (13 / 15 days),
     after that 409 · open max on reopen · closed_at set on resolved, cleared on reopen
  6  support.manage — no token / user JWT → 401 · admin token without it → 403 · with it → 200
  7  audit — admin reply / status / priority / category = admin_audit_log rows (actor · action · ticket · old → new)
  8  legacy values (7.2a transition) — open → new / in_review · closed → resolved · other → general on read
  9  details / faq_id (7.2a) — unknown key · external link · future date · too big · bad faq → 422 · /support/meta
  10 admin inbox (7.2a) — filters · q (H id / email) · sort · counts · category change + legacy_category

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
    third = _open(u)                                     # a resolved one frees a place
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


# ── 5 statuses + reopen window ──
def _status(pid):
    return _sql("SELECT status, closed_at IS NOT NULL FROM support_tickets WHERE public_id = :p", p=pid)[0]


def _areply(pid, nxt="awaiting_user", **kw):
    body = {"body": "جرّب هيك"}
    if nxt is not None:
        body["next_status"] = nxt
    return client.post(f"/admin/support/tickets/{pid}/messages", json=body, headers=kw.get("headers") or _admin())


def test_transition_rule():
    t = srv.support.transition
    assert t(None, "open") == "new"
    assert t("new", "admin_reply", target="awaiting_user") == "awaiting_user"
    assert t("in_review", "admin_reply", target="resolved") == "resolved"
    for bad in (None, "new", "in_review", "x"):
        with pytest.raises(srv.support.SupportError) as e:
            t("new", "admin_reply", target=bad)
        assert e.value.status == 422
    for st in srv.support.STATUSES:
        assert t("resolved", "admin_set", target=st) == st
    for cur in ("new", "in_review", "awaiting_user"):
        assert t(cur, "requester_reply") == "in_review"
    assert t("resolved", "requester_reply", reopen_ok=True) == "in_review"
    with pytest.raises(srv.support.SupportError) as e:
        t("resolved", "requester_reply", reopen_ok=False)
    assert (e.value.status, e.value.code) == (409, "reopen_expired")
    assert t("awaiting_user", "requester_resolve") == "resolved"


def test_status_flow_over_http():
    u = _user()
    pid = _open(u)
    assert _status(pid) == ["new", False]                                         # written explicitly
    assert _areply(pid, None).status_code == 422                                  # next_status required
    assert _areply(pid, "in_review").json()["error"]["code"] == "invalid_next_status"
    assert _areply(pid).json()["data"]["status"] == "awaiting_user"
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "ما زبط"}, headers=_h(u))
    assert r.json()["data"] == {"public_id": pid, "status": "in_review", "reopened": False}
    assert _areply(pid, "resolved").json()["data"]["status"] == "resolved"
    assert _status(pid) == ["resolved", True]                                     # closed_at = resolved time
    assert client.put(f"/admin/support/tickets/{pid}", json={"status": "new"}, headers=_admin()).status_code == 200
    assert _status(pid) == ["new", False]
    r = client.post(f"/support/tickets/{pid}/close", headers=_h(u))                # «انحلّت»
    assert r.json()["data"]["status"] == "resolved" and _status(pid) == ["resolved", True]


def test_reopen_within_14_days_only():
    u = _user()
    pid = _open(u)
    client.post(f"/support/tickets/{pid}/close", headers=_h(u))
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '13 days' WHERE public_id = :p", p=pid)
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "رجعت"}, headers=_h(u))
    assert r.status_code == 200 and r.json()["data"]["reopened"] is True and r.json()["data"]["status"] == "in_review"
    assert _status(pid) == ["in_review", False]                                   # closed_at cleared
    client.post(f"/support/tickets/{pid}/close", headers=_h(u))
    _sql("UPDATE support_tickets SET closed_at = NOW() - INTERVAL '15 days' WHERE public_id = :p", p=pid)
    r = client.post(f"/support/tickets/{pid}/messages", json={"body": "رجعت"}, headers=_h(u))
    assert r.status_code == 409 and r.json()["error"]["code"] == "reopen_expired"
    assert client.get(f"/support/tickets/{pid}", headers=_h(u)).json()["data"]["can_reopen"] is False


# ── 6 permission ──
def test_support_manage_permission():
    pid = _open(_user())
    paths = [("get", "/admin/support/tickets", None), ("get", f"/admin/support/tickets/{pid}", None),
             ("get", "/admin/support/counts", None),
             ("post", f"/admin/support/tickets/{pid}/messages", {"body": "x", "next_status": "resolved"}),
             ("put", f"/admin/support/tickets/{pid}", {"status": "resolved"})]
    for method, path, body in paths:
        kw = {"json": body} if body else {}
        assert getattr(client, method)(path, **kw).status_code == 401, path
        assert getattr(client, method)(path, headers=_h(_user()), **kw).status_code == 401, path
        assert getattr(client, method)(path, headers=_admin(["settings.edit"], "staff:3"), **kw).status_code == 403, path
    assert client.get("/admin/support/tickets", headers=_admin(["support.manage"], "staff:4")).status_code == 200
    items = client.get("/admin/support/tickets?status=new", headers=_admin()).json()["data"]["items"]
    assert items and all(t["status"] == "new" for t in items)
    assert client.get("/admin/support/tickets?status=open", headers=_admin()).status_code == 422   # legacy value
    assert client.get("/admin/support/tickets?status=nope", headers=_admin()).status_code == 422


# ── 7 audit ──
def test_admin_actions_audited():
    pid = _open(_user())
    _sql("DELETE FROM admin_audit_log")
    _areply(pid, headers=_admin(["support.manage"], "staff:9"))
    client.put(f"/admin/support/tickets/{pid}", json={"status": "resolved", "priority": "high"}, headers=_admin())
    client.put(f"/admin/support/tickets/{pid}", json={"status": "new"}, headers=_admin(["reports.read"], "staff:2"))
    client.put(f"/admin/support/tickets/{pid}", json={"category": "jobs"}, headers=_admin(["support.manage"], "staff:5"))
    rows = _sql("SELECT actor, action, target, result, old_value, new_value FROM admin_audit_log ORDER BY id")
    assert rows[0] == ["staff:9", "admin_support_reply", f"ticket={pid}", "ok", "status=new", "status=awaiting_user"]
    assert rows[1] == ["owner", "admin_support_update", f"ticket={pid}", "ok",
                       "priority=normal;status=awaiting_user", "priority=high;status=resolved"]
    assert rows[2][:4] == ["staff:2", "admin_support_update", f"ticket={pid}", "denied"]
    assert rows[3] == ["staff:5", "admin_support_update", f"ticket={pid}", "ok", "category=technical", "category=jobs"]
    assert "جرّب" not in str(rows)                                               # never the message text
    assert _sql("SELECT closed_at IS NOT NULL FROM support_tickets WHERE public_id = :p", p=pid)[0][0] is True


# ── 8 legacy values (production rows before stage B) ──
def test_legacy_values_normalised_on_read():
    u = _user()
    p_open, p_answered, p_closed = _open(u), _open(u), _open(u)
    _areply(p_answered)
    _sql("ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_status_chk")
    _sql("ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_category_chk")
    try:
        _sql("UPDATE support_tickets SET status = 'open', category = 'other' WHERE public_id IN (:a, :b)",
             a=p_open, b=p_answered)
        _sql("UPDATE support_tickets SET status = 'closed', closed_at = NOW() WHERE public_id = :p", p=p_closed)
        got = {t["public_id"]: (t["status"], t["category"])
               for t in client.get("/support/tickets", headers=_h(u)).json()["data"]["items"]}
        assert got == {p_open: ("new", "general"), p_answered: ("in_review", "general"), p_closed: ("resolved", "technical")}
        assert client.get(f"/admin/support/tickets/{p_open}", headers=_admin()).json()["data"]["status"] == "new"
        ids = [t["public_id"] for t in client.get("/admin/support/tickets?status=resolved&category=technical&q=" + p_closed,
                                                  headers=_admin()).json()["data"]["items"]]
        assert ids == [p_closed]
        # open max counts legacy open rows; a write stores the new value only
        r = client.post(f"/support/tickets/{p_open}/messages", json={"body": "و؟"}, headers=_h(u))
        assert r.json()["data"]["status"] == "in_review"
        client.put(f"/admin/support/tickets/{p_open}", json={"category": "account"}, headers=_admin())
        assert _sql("SELECT status, category, legacy_category FROM support_tickets WHERE public_id = :p", p=p_open)[0] \
            == ["in_review", "account", "other"]
    finally:
        _sql("UPDATE support_tickets SET status = CASE status WHEN 'open' THEN 'new' WHEN 'closed' THEN 'resolved' "
             "ELSE status END, category = CASE category WHEN 'other' THEN 'general' ELSE category END")
        _sql("ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_status_chk CHECK "
             "(status IN ('new', 'in_review', 'awaiting_user', 'resolved'))")
        _sql("ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_category_chk CHECK (category IN "
             "('account', 'verification', 'profile', 'jobs', 'education', 'technical', 'complaint', 'general'))")


# ── 9 details + faq_id ──
def test_details_allowlist_and_faq():
    u = _user()
    ok = _new(u, category="technical", details={"page_url": "https://tawasolna.com/home", "device": "mobile"},
              faq_id="page_broken")
    assert ok.status_code == 201, ok.text
    pid = ok.json()["data"]["public_id"]
    d = client.get(f"/admin/support/tickets/{pid}", headers=_admin()).json()["data"]
    assert d["details"] == {"page_url": "https://tawasolna.com/home", "device": "mobile"} and d["faq_id"] == "page_broken"
    assert d["legacy_category"] is None
    bad = [
        ({"category": "technical", "details": {"color": "x"}}, "unknown_detail"),
        ({"category": "general", "details": {"page_url": "https://tawasolna.com/x"}}, "unknown_detail"),
        ({"category": "complaint", "details": {"content_url": "https://evil.com/x"}}, "invalid_detail"),
        ({"category": "profile", "details": {"page_url": "http://tawasolna.com/x"}}, "invalid_detail"),
        ({"category": "profile", "details": {"page_url": "https://tawasolna.com/" + "a" * 300}}, "invalid_detail"),
        ({"category": "verification", "details": {"submitted_date": "2999-01-01"}}, "invalid_detail"),
        ({"category": "verification", "details": {"submitted_date": "2026-02-30"}}, "invalid_detail"),
        ({"category": "account", "details": {"issue": "hacked", "account_email": "bad"}}, "invalid_detail"),
        ({"category": "account", "details": {"account_name": "a\u0007b"}}, "invalid_detail"),
        ({"category": "account", "details": {"account_phone": "+96279abc"}}, "invalid_detail"),
        ({"category": "education", "details": {"name": "س" * 121}}, "invalid_detail"),
        ({"category": "jobs", "details": {"kind": 3}}, "invalid_detail"),
        ({"category": "jobs", "details": {"x" * 10: "y" * 5000}}, "details_too_large"),
        ({"category": "jobs", "details": ["kind"]}, "invalid_details"),
        ({"category": "jobs", "faq_id": "nope"}, "invalid_faq"),
    ]
    for over, code in bad:
        r = _new(u, **over)
        assert r.status_code == 422 and r.json()["error"]["code"] == code, (over, r.text)
    assert _new(u, category="verification", details={"request_type": "company", "submitted_date": "2026-01-02"}).status_code == 201
    m = client.get("/support/meta").json()["data"]
    assert m["categories"] == list(srv.support.CATEGORIES) and m["guest_category"] == "account"
    assert [f["key"] for f in m["fields"]["jobs"]] == ["job_url", "kind"] and m["fields"]["general"] == []
    assert m["faq"]["education"] == ["where"]


# ── 10 admin inbox ──
def test_admin_filters_search_sort_counts_category():
    u = _user()
    email = _sql("SELECT email FROM users WHERE id = :i", i=u["id"])[0][0]
    a, b, c = _open(u), _open(u), _open(u)
    client.put(f"/admin/support/tickets/{b}", json={"priority": "urgent"}, headers=_admin())
    _areply(c)
    _sql("UPDATE support_tickets SET last_message_at = NOW() - INTERVAL '30 days' WHERE public_id = :p", p=a)

    def ids(qs):
        r = client.get("/admin/support/tickets?" + qs, headers=_admin())
        assert r.status_code == 200, r.text
        return [t["public_id"] for t in r.json()["data"]["items"]]
    assert ids("q=" + email.upper()) == [c, b, a]                                 # newest = created
    assert ids("q=" + b.lower()) == [b]
    assert ids("q=" + email + "&sort=oldest_waiting")[0] == a
    assert ids("q=" + email + "&sort=priority")[0] == b
    assert ids("q=" + email + "&status=awaiting_user") == [c]
    assert ids("q=" + email + "&requester=guest") == []
    assert set(ids("q=" + email + "&requester=user")) == {a, b, c}
    for bad in ("sort=x", "requester=x", "q=abc"):
        assert client.get("/admin/support/tickets?" + bad, headers=_admin()).status_code == 422, bad
    n = client.get("/admin/support/counts", headers=_admin()).json()["data"]["new"]
    assert n == _sql("SELECT COUNT(*) FROM support_tickets WHERE status = 'new'")[0][0] and n >= 2
    client.put(f"/admin/support/tickets/{a}", json={"category": "jobs"}, headers=_admin())
    client.put(f"/admin/support/tickets/{a}", json={"category": "general"}, headers=_admin())
    assert _sql("SELECT category, legacy_category FROM support_tickets WHERE public_id = :p", p=a)[0] == ["general", "technical"]
    assert client.put(f"/admin/support/tickets/{a}", json={"category": "other"}, headers=_admin()).status_code == 422
