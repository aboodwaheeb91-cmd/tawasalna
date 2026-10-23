"""
test_blocks_suspension.py — task 5.4: admin account suspension + user blocks (SYSTEMS_INDEX §25f ·
docs/rules/blocks-suspension.md).

Suspension: every request of the account → 401 (session check, same path as a deleted account) · login
refused · its profile / posts / comments / jobs hidden from everyone · all back when lifted · only the
admin may suspend (signed-in user → 403, nobody → 401).
Blocks: both directions on profile · feed · comments · search · messages (start + reply) · follow;
follows of both directions removed; no notification; a job application between the two still works.

Real PostgreSQL, in-process client. TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_blocks_suspension.py -q
"""
import asyncio, json, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-54-" + "a" * 32
PW = "Passw0rd-54!"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    monkeypatch.setattr(srv, "_asyncpg_pool", None)            # HTTP tests → pg8000 path
    monkeypatch.setattr(srv, "schedule_message_email", lambda *a, **k: None)
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    yield


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


def _user(ut):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, :h, :ut) RETURNING id, tw_id",
        t=("C" if ut == "co" else "U") + n, n="User" + n, e=n + "@t.test", h=auth.hash_password(PW), ut=ut)[0]
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return {"id": int(uid), "tw": tw, "email": n + "@t.test", "ut": ut}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _admin():
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _post(co, body="منشور"):
    return int(_sql("INSERT INTO company_posts (company_id, body) VALUES (:c, :b) RETURNING id", c=co["id"], b=body)[0][0])


def _comment(post_id, u, body="تعليق"):
    r = client.post(f"/company/posts/{post_id}/comments", headers=_h(u), json={"body": body})
    assert r.status_code == 200, r.text
    return r.json()["comment"]["id"]


def _job(co):
    return int(_sql("INSERT INTO jobs (company_id, title, status) VALUES (:c, :t, 'active') RETURNING id",
                    c=co["id"], t="وظيفة " + uuid.uuid4().hex[:6])[0][0])


def _feed_ids(u, kind):
    r = client.get("/home/feed?filter=all&limit=50", headers=_h(u))
    assert r.status_code == 200, r.text
    return {i["id"] for i in r.json()["items"] if i["type"] == kind}


def _comment_ids(post_id, u=None):
    r = client.get(f"/company/posts/{post_id}/comments?limit=50", headers=_h(u) if u else {})
    return r.status_code, {c["id"] for c in r.json().get("comments", [])} if r.status_code == 200 else set()


def _job_list_ids(hdr=None):
    r = client.get("/jobs", headers=hdr or {})
    assert r.status_code == 200, r.text
    return {j["id"] for j in r.json()["jobs"]}


def _suspend(u, on, reason=None):
    body = {"suspended": on}
    if reason is not None:
        body["reason"] = reason
    return client.put(f"/admin/user/{u['id']}/suspension", headers=_admin(), json=body)


# ── Suspension ───────────────────────────────────────────────────────────────

def test_only_admin_can_suspend():
    emp, other = _user("emp"), _user("emp")
    url = f"/admin/user/{other['id']}/suspension"
    # admin token without the users.suspend permission (plan 5.3 staff) → 403
    staff = {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:1", perms=["jobs.edit"])}
    assert client.put(url, headers=staff, json={"suspended": True}).status_code == 403
    # a user JWT is not an admin session (admin-gate contract, PR 1.5) → 401 · nobody → 401
    assert client.put(url, headers=_h(emp), json={"suspended": True}).status_code == 401
    assert client.put(url, headers={"X-Admin-Token": _h(emp)["Authorization"][7:]}, json={"suspended": True}).status_code == 401
    assert client.put(url, json={"suspended": True}).status_code == 401
    assert _sql("SELECT suspended_at FROM users WHERE id = :u", u=other["id"])[0][0] is None
    assert client.put(url, headers=_admin(), json={"suspended": "yes"}).status_code == 422
    assert client.put("/admin/user/999999999/suspension", headers=_admin(), json={"suspended": True}).status_code == 404


def test_suspended_account_gets_401_and_login_refused_then_back():
    emp = _user("emp")
    h = _h(emp)
    assert client.post("/auth/verify-token", headers=h).status_code == 200
    r = _suspend(emp, True, "مخالفة")
    assert r.status_code == 200 and r.json()["data"]["suspended"] is True, r.text
    assert client.post("/auth/verify-token", headers=h).status_code == 401
    assert client.get("/home/feed", headers=h).status_code == 401
    r = client.post("/auth/login", json={"email": emp["email"], "password": PW})
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_suspended"
    assert "token" not in r.text
    # the reason is admin-only: visible on the admin profile, never on the public one
    adm = client.get(f"/admin/profile/{emp['id']}", headers=_admin()).json()["profile"]["suspension"]
    assert adm["suspended"] and adm["suspended_reason"] == "مخالفة" and adm["suspended_by"] == "owner"

    assert _suspend(emp, False).status_code == 200
    assert client.post("/auth/verify-token", headers=h).status_code == 200      # same account, same token
    r = client.post("/auth/login", json={"email": emp["email"], "password": PW})
    assert r.status_code == 200 and r.json()["token"]
    assert _sql("SELECT suspended_reason FROM users WHERE id = :u", u=emp["id"])[0][0] is None


def test_suspended_content_hidden_from_everyone_and_back():
    co, emp, viewer = _user("co"), _user("emp"), _user("emp")
    post = _post(co)
    c_emp = _comment(post, emp)
    job = _job(co)
    srv._cache_del("jobs:")

    assert _suspend(co, True).status_code == 200
    assert _suspend(emp, True).status_code == 200
    for hdr in ({}, _h(viewer)):
        assert client.get(f"/company/profile/{co['id']}", headers=hdr).status_code == 404
        assert client.get(f"/company/posts/{co['id']}", headers=hdr).status_code == 404
        assert client.get(f"/profile/{emp['id']}", headers=hdr).status_code == 404
        assert client.get(f"/jobs/{job}", headers=hdr).status_code == 404
        assert job not in _job_list_ids(hdr)
    assert client.get(f"/u/{co['tw']}").status_code == 404
    assert post not in _feed_ids(viewer, "post")
    assert job not in _feed_ids(viewer, "opportunity")

    assert _suspend(co, False).status_code == 200
    st, ids = _comment_ids(post, viewer)
    assert st == 200 and c_emp not in ids                      # the suspended commenter's comment is hidden
    assert _suspend(emp, False).status_code == 200
    st, ids = _comment_ids(post, viewer)
    assert c_emp in ids
    assert client.get(f"/profile/{emp['id']}", headers=_h(viewer)).status_code == 200
    assert client.get(f"/company/profile/{co['id']}", headers=_h(viewer)).status_code == 200
    assert client.get(f"/jobs/{job}").status_code == 200
    assert job in _job_list_ids()
    assert post in _feed_ids(viewer, "post")
    # nothing was deleted
    assert _sql("SELECT COUNT(*) FROM company_post_comments WHERE id = :c", c=c_emp)[0][0] == 1


# ── Blocks ───────────────────────────────────────────────────────────────────

def test_block_both_directions_everywhere_silent_and_unblock():
    a, b = _user("emp"), _user("co")          # a = person, b = company (has posts)
    a2 = _user("emp")                         # mutual-follow emp for the emp ↔ emp message path
    post_b = _post(b)
    c_a = _comment(post_b, a)
    c_a2 = _comment(post_b, a2)
    for x, y in ((a, b), (b, a), (a, a2), (a2, a)):
        _sql("INSERT INTO profile_follows (follower_id, followed_id) VALUES (:x, :y) ON CONFLICT DO NOTHING",
             x=x["id"], y=y["id"])
    assert client.post("/messages/send", headers=_h(b), json={"receiver_id": a["id"], "content": "مرحبا"}).status_code == 200
    notif_before = _sql("SELECT COUNT(*) FROM notifications WHERE user_id IN (:b, :a2)", b=b["id"], a2=a2["id"])[0][0]

    assert client.put(f"/blocks/{b['id']}", headers=_h(a)).json()["ok"] is True
    assert client.put(f"/blocks/{a2['tw']}", headers=_h(a)).json()["ok"] is True     # tw_id works too

    # follows removed both ways · no notification · blocked side never told
    assert _sql("SELECT COUNT(*) FROM profile_follows WHERE (follower_id = :a AND followed_id IN (:b, :c)) "
                "OR (followed_id = :a AND follower_id IN (:b, :c))", a=a["id"], b=b["id"], c=a2["id"])[0][0] == 0
    assert _sql("SELECT COUNT(*) FROM notifications WHERE user_id IN (:b, :a2)", b=b["id"], a2=a2["id"])[0][0] == notif_before

    for me, other in ((a, b), (b, a), (a, a2), (a2, a)):
        h = _h(me)
        # profile = «غير موجود» (same as a missing account)
        prof = f"/company/profile/{other['id']}" if other["ut"] == "co" else f"/profile/{other['id']}"
        assert client.get(prof, headers=h).status_code == 404
        assert client.get(f"/profile/{other['id']}/follow", headers=h).status_code == 404
        assert client.get(f"/user/lookup/{other['tw']}", headers=h).status_code == 404
        # follow
        assert client.post(f"/profile/{other['id']}/follow", headers=h).status_code == 404
        # messages: start + reply (existing conversation a ↔ b) both refused, the button off
        r = client.post("/messages/send", headers=h, json={"receiver_id": other["id"], "content": "x"})
        assert r.status_code == 404, r.text
        assert client.get(f"/messages/can-send/{other['id']}", headers=h).json()["data"]["can_message"] is False
        convs = client.get(f"/messages/conversations/{me['id']}", headers=h).json()["conversations"]
        assert other["id"] not in {c["other_id"] for c in convs}
        # search (@mention)
        q = other["tw"][1:7]
        name_q = client.get(f"/mention/search?q=User{q}", headers=h).json()["candidates"]
        assert other["tw"] not in {c["tw_id"] for c in name_q}

    # feed + posts + comments both ways
    assert post_b not in _feed_ids(a, "post")
    assert client.get(f"/company/posts/{b['id']}", headers=_h(a)).status_code == 404
    assert client.get(f"/company/posts/{post_b}/comments", headers=_h(a)).status_code == 404
    assert client.post(f"/company/posts/{post_b}/comments", headers=_h(a), json={"body": "x"}).status_code == 404
    st, ids = _comment_ids(post_b, b)                      # the company no longer sees a's comment
    assert st == 200 and c_a not in ids and c_a2 in ids
    st, ids = _comment_ids(post_b, a2)                     # a2 blocked by a → a's comment hidden for a2
    assert c_a not in ids
    st, ids = _comment_ids(post_b)                         # a guest sees everything
    assert {c_a, c_a2} <= ids
    # followers lists leave the hidden account out
    fl = client.get(f"/profile/{b['id']}/followers", headers=_h(a2)).json()
    assert a["id"] not in {i["id"] for i in fl["items"]}

    # own list + unblock
    lst = client.get("/blocks", headers=_h(a)).json()["data"]
    assert lst["total"] == 2 and {i["id"] for i in lst["items"]} == {b["id"], a2["id"]}
    assert client.get("/blocks", headers=_h(b)).json()["data"]["total"] == 0          # only your own blocks
    assert client.delete(f"/blocks/{a['id']}", headers=_h(b)).json()["data"]["blocked"] is False   # not b's row
    assert client.get(f"/company/profile/{b['id']}", headers=_h(a)).status_code == 404               # a's block stays
    assert client.delete(f"/blocks/{b['id']}", headers=_h(a)).status_code == 200
    assert client.get(f"/company/profile/{b['id']}", headers=_h(a)).status_code == 200
    assert post_b in _feed_ids(a, "post")
    assert client.get("/blocks", headers=_h(a)).json()["data"]["total"] == 1


class _FakeWS:
    """Just what websocket_endpoint uses: an auth frame, then the given events."""
    def __init__(self, frames, on_end=None):
        self.headers, self._frames, self.sent, self._on_end = {}, list(frames), [], on_end

    async def accept(self):
        pass

    async def receive_text(self):
        from starlette.websockets import WebSocketDisconnect
        if not self._frames:
            if self._on_end:
                self._on_end()        # state before the endpoint's disconnect clean-up
            raise WebSocketDisconnect(code=1000)
        return self._frames.pop(0)

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def close(self, code=1000, reason=""):
        pass


def _ws_events(me, events, mgr):
    """me sends events over a real websocket_endpoint run → (what me received, me's open conversation)."""
    token = _h(me)["Authorization"][7:]
    seen = {}
    ws = _FakeWS([json.dumps({"type": "auth", "token": token})] + [json.dumps(e) for e in events],
                 on_end=lambda: seen.update(active=mgr.active_conversations.get(me["id"])))
    srv._ws_typing_log.clear(); srv._ws_ctrl_log.clear()
    old = srv.ws_manager
    srv.ws_manager = mgr
    try:
        asyncio.run(srv.websocket_endpoint(ws, me["id"]))
    finally:
        srv.ws_manager = old
    return ws.sent, seen.get("active")


def test_ws_typing_and_active_conversation_dropped_both_ways_when_blocked():
    """task 5.4c — typing / typing_stop / active_conversation never cross a block (either direction),
    silently; before the block they do (the check is real)."""
    a, b = _user("emp"), _user("co")
    assert client.post("/messages/send", headers=_h(b), json={"receiver_id": a["id"], "content": "مرحبا"}).status_code == 200

    def run(me, other):
        mgr = srv.ConnectionManager()
        peer = _FakeWS([])
        mgr.active[other["id"]] = [peer]
        events = [{"type": "typing", "to_user_id": other["id"]},
                  {"type": "typing_stop", "to_user_id": other["id"]},
                  {"type": "active_conversation", "other_id": other["id"]}]
        got, active = _ws_events(me, events, mgr)
        return got, peer.sent, active

    for me, other in ((a, b), (b, a)):                       # control: no block → delivered
        got, peer_got, active = run(me, other)
        assert [e["type"] for e in peer_got] == ["typing", "typing_stop"]
        assert active == other["id"]

    assert client.put(f"/blocks/{b['id']}", headers=_h(a)).status_code == 200
    for me, other in ((a, b), (b, a)):                       # blocker → blocked and blocked → blocker
        got, peer_got, active = run(me, other)
        assert peer_got == []                                # nothing reached the other side
        assert active is None                                # the conversation is not marked open
        assert [e["type"] for e in got] == ["auth_ok"]       # sender got no error (block not revealed)


def test_reply_to_blocked_users_comment_refused_without_notification():
    """task 5.4c — A blocked B; A commented on C's post: B's reply to A's comment (or into A's thread)
    gets the hidden-content answer and A is never notified; the post owner C is untouched."""
    a, b, c, d = _user("emp"), _user("emp"), _user("co"), _user("emp")
    post_c = _post(c)
    c_a = _comment(post_c, a)
    r = client.post(f"/company/posts/{post_c}/comments", headers=_h(d), json={"body": "رد", "reply_to_comment_id": c_a})
    assert r.status_code == 200, r.text
    d_reply = r.json()["comment"]["id"]
    assert client.put(f"/blocks/{b['id']}", headers=_h(a)).status_code == 200

    def a_notifs():
        return _sql("SELECT COUNT(*) FROM notifications WHERE user_id = :a", a=a["id"])[0][0]

    missing = client.post(f"/company/posts/{post_c}/comments", headers=_h(b),
                          json={"body": "رد", "reply_to_comment_id": 999999999})
    before = a_notifs()
    for target in (c_a, d_reply):                            # A's comment, and a reply in A's thread
        r = client.post(f"/company/posts/{post_c}/comments", headers=_h(b),
                        json={"body": "رد", "reply_to_comment_id": target})
        assert r.status_code == missing.status_code == 404, r.text
        if target == c_a:
            assert r.json() == missing.json()                 # same answer as a comment that does not exist
    # the other direction: A replies to B's comment
    c_b = _sql("INSERT INTO company_post_comments (post_id, user_id, body) VALUES (:p, :u, 'x') RETURNING id",
               p=post_c, u=b["id"])[0][0]
    r = client.post(f"/company/posts/{post_c}/comments", headers=_h(a), json={"body": "رد", "reply_to_comment_id": c_b})
    assert r.status_code == 404, r.text
    assert a_notifs() == before
    assert _sql("SELECT COUNT(*) FROM company_post_comments WHERE user_id = :b AND reply_to_comment_id IS NOT NULL",
                b=b["id"])[0][0] == 0
    # a plain comment on C's post still works for B (only A's thread is closed to B)
    _comment(post_c, b)


def test_block_errors_and_rate():
    a = _user("emp")
    r = client.put(f"/blocks/{a['id']}", headers=_h(a))
    assert r.status_code == 422 and r.json()["error"]["code"] == "self_block"
    assert client.put("/blocks/999999999", headers=_h(a)).status_code == 404
    assert client.put("/blocks/1").status_code == 401
    import tw_limits
    n = tw_limits.RATES["block_set"][0]
    others = [_user("emp") for _ in range(n)]
    srv._rate_store.clear()   # the refused calls above counted too
    for o in others:
        assert client.put(f"/blocks/{o['id']}", headers=_h(a)).status_code == 200
    assert client.put(f"/blocks/{others[0]['id']}", headers=_h(a)).status_code == 429


def test_job_application_unaffected_by_block():
    emp, co = _user("emp"), _user("co")
    job = _job(co)
    srv._cache_del("jobs:")
    assert client.put(f"/blocks/{co['id']}", headers=_h(emp)).status_code == 200
    assert client.put(f"/blocks/{emp['id']}", headers=_h(co)).status_code == 200    # both sides blocked
    # the job itself stays visible and open to the blocked person
    assert client.get(f"/jobs/{job}", headers=_h(emp)).status_code == 200
    r = client.post(f"/jobs/{job}/apply", headers=_h(emp), json={"cover_letter": "مهتم"})
    assert r.status_code == 200, r.text
    app_id = _sql("SELECT id FROM job_applications WHERE job_id = :j AND user_id = :u", j=job, u=emp["id"])[0][0]
    r = client.get(f"/jobs/{job}/applicants", headers=_h(co))
    assert r.status_code == 200 and str(emp["id"]) in r.text, r.text
    r = client.put(f"/jobs/applications/{app_id}/status", headers=_h(co), json={"status": "interview"})
    assert r.status_code == 200, r.text
