"""
test_conversation_policy.py — task 5.0g: who may send a direct message to whom (AUD-P1-01).

One rule — auth.can_send_message — checked by POST /messages/send (pg8000 + asyncpg paths) in
the same transaction as the INSERT under a per-pair lock; GET /messages/can-send/{id} reports it
for the «مراسلة» button; POST /messages/conversations/{id}/end lets a company end a conversation.
Types / follows / endings come from the DB (the JWT only names the caller).

Needs TW_TEST_DB_URL=postgresql://user:pass@host:port/db (throwaway database). Without it skipped.
Run: python -m pytest tests/test_conversation_policy.py -q
"""
import asyncio, os, sys, threading, time, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(auth, "get_session_state", lambda uid: {"changed": None, "sv": 0})
    monkeypatch.setattr(srv, "_asyncpg_pool", None)            # HTTP tests → pg8000 path
    monkeypatch.setattr(srv, "schedule_message_email", lambda *a, **k: None)
    srv._pwd_changed_cache.clear()
    yield


def _db_params():
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    return dict(host=host, port=int(port), user=user, password=pw, database=name.split("?")[0])


@pytest.fixture(scope="module")
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


def _user(ut):
    n = uuid.uuid4().hex[:10]
    with auth.db_conn() as conn:
        return int(conn.run(
            "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
            "VALUES (:t, :n, :e, 'x', :ut) RETURNING id",
            t="T" + n, n="User " + n, e=n + "@t.test", ut=ut)[0][0])


def _follow(a, b):
    with auth.db_conn() as conn:
        conn.run("INSERT INTO profile_follows (follower_id, followed_id) VALUES (:a, :b) "
                 "ON CONFLICT DO NOTHING", a=a, b=b)


def _unfollow(a, b):
    with auth.db_conn() as conn:
        conn.run("DELETE FROM profile_follows WHERE follower_id = :a AND followed_id = :b", a=a, b=b)


def _h(uid, ut="emp"):
    # the JWT's user_type is deliberately wrong-able: the rule reads the DB
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": ut, "tw_id": "X"})}


def _send(frm, to, ut="emp", text="hi"):
    return client.post("/messages/send", json={"receiver_id": to, "content": text}, headers=_h(frm, ut))


def _end(frm, other, ut="co"):
    return client.post(f"/messages/conversations/{other}/end", headers=_h(frm, ut))


def _can(frm, other):
    r = client.get(f"/messages/can-send/{other}", headers=_h(frm))
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _code(r):
    return r.json()["error"]["code"]


# ── starting a conversation ──────────────────────────────────────────────────

def test_emp_cannot_start_with_company_company_starts_emp_replies(db):
    emp, co = _user("emp"), _user("co")
    r = _send(emp, co, ut="co")                       # forged JWT type changes nothing
    assert r.status_code == 403 and _code(r) == "company_start"
    assert r.json()["error"]["message"] == "لا يمكنك بدء محادثة مع شركة"
    assert _can(emp, co)["can_message"] is False
    assert _send(co, emp, ut="co").status_code == 200
    assert _send(emp, co).status_code == 200
    assert _can(emp, co)["can_message"] is True


def test_emp_emp_needs_mutual_follow(db):
    a, b = _user("emp"), _user("emp")
    r = _send(a, b)
    assert r.status_code == 403 and _code(r) == "mutual_follow"
    _follow(a, b)                                      # one side only
    assert _send(a, b).status_code == 403
    assert _send(b, a).status_code == 403
    _follow(b, a)
    assert _can(a, b)["can_message"] is True
    assert _send(a, b).status_code == 200


def test_existing_conversation_survives_unfollow(db):
    a, b = _user("emp"), _user("emp")
    _follow(a, b); _follow(b, a)
    assert _send(a, b).status_code == 200
    _unfollow(a, b); _unfollow(b, a)
    assert _send(b, a).status_code == 200
    assert _send(a, b).status_code == 200


def test_emp_to_edu_and_org_to_anyone(db):
    emp, edu, co, emp2 = _user("emp"), _user("edu"), _user("co"), _user("emp")
    assert _send(emp, edu).status_code == 200
    assert _send(edu, emp2, ut="edu").status_code == 200
    assert _send(co, edu, ut="co").status_code == 200


def test_unknown_receiver_and_self(db):
    emp = _user("emp")
    assert _send(emp, 987654321).status_code == 404
    assert _send(emp, emp).status_code == 400
    assert _can(emp, emp)["can_message"] is False


# ── ending a conversation ────────────────────────────────────────────────────

def test_company_ends_emp_blocked_company_reopens(db):
    co, emp = _user("co"), _user("emp")
    assert _send(co, emp, ut="co").status_code == 200
    assert _can(co, emp)["can_end"] is True
    r = _end(co, emp)
    assert r.status_code == 200 and r.json() == {"ok": True, "data": {"ended": True}}
    assert _end(co, emp).status_code == 200            # idempotent
    r = _send(emp, co)
    assert r.status_code == 403 and _code(r) == "ended"
    assert r.json()["error"]["message"] == "أنهت الشركة هذه المحادثة"
    st = _can(emp, co)
    assert st == {"can_message": False, "reason": "ended", "reason_key": "msg.policy.ended",
                  "ended": True, "can_end": False}
    # old messages stay readable for the person
    msgs = client.get(f"/messages/{emp}/{co}", headers=_h(emp)).json()["messages"]
    assert len(msgs) == 1
    # no notification about the end
    with auth.db_conn() as conn:
        assert conn.run("SELECT COUNT(*) FROM notifications WHERE user_id = :u", u=emp)[0][0] == 0
    # the company writes again → re-opened → the person replies
    assert _send(co, emp, ut="co").status_code == 200
    assert _can(emp, co)["ended"] is False
    assert _send(emp, co).status_code == 200


def test_only_the_company_of_the_conversation_can_end(db):
    co, emp, other_co, emp2 = _user("co"), _user("emp"), _user("co"), _user("emp")
    assert _send(co, emp, ut="co").status_code == 200
    r = _end(emp, co, ut="co")                         # emp with a forged co JWT
    assert r.status_code == 403 and _code(r) == "end_forbidden"
    r = _end(other_co, emp)                            # a company with no conversation with emp
    assert r.status_code == 404 and _code(r) == "no_conversation"
    r = _end(emp2, emp)
    assert r.status_code == 403
    assert _send(emp, co).status_code == 200           # still open


def test_third_party_cannot_read_or_list_others_conversation(db):
    co, emp, intruder = _user("co"), _user("emp"), _user("emp")
    assert _send(co, emp, ut="co").status_code == 200
    assert client.get(f"/messages/{emp}/{co}", headers=_h(intruder)).status_code == 403
    assert client.get(f"/messages/conversations/{emp}", headers=_h(intruder)).status_code == 403
    r = _send(intruder, co)                            # writing into it = a new emp → co start
    assert r.status_code == 403 and _code(r) == "company_start"


def test_guest_gets_401(db):
    assert client.post("/messages/send", json={"receiver_id": 1, "content": "x"}).status_code == 401
    assert client.get("/messages/can-send/1").status_code == 401
    assert client.post("/messages/conversations/1/end").status_code == 401


# ── concurrency: the check runs after the pair lock, in the INSERT's transaction ──

def test_send_waits_for_pair_lock_and_sees_the_end(db):
    co, emp = _user("co"), _user("emp")
    assert _send(co, emp, ut="co").status_code == 200
    holder = auth.get_conn()
    try:
        holder.run("BEGIN")
        holder.run(auth.MESSAGE_PAIR_LOCK_SQL_PG8000, s=emp, r=co)
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("r", _send(emp, co)))
        t.start()
        time.sleep(0.5)
        assert t.is_alive()                            # blocked on the lock
        a, b = sorted((co, emp))
        holder.run("INSERT INTO conversation_endings (user_a, user_b, ended_by) VALUES (:a, :b, :c)",
                   a=a, b=b, c=co)
        holder.run("COMMIT")
    finally:
        auth.release_conn(holder)
    t.join(10)
    assert out["r"].status_code == 403 and _code(out["r"]) == "ended"
    with auth.db_conn() as conn:
        assert conn.run("SELECT COUNT(*) FROM messages WHERE sender_id = :e", e=emp)[0][0] == 0


# ── asyncpg path: the same rule ──────────────────────────────────────────────

def test_asyncpg_path_same_rule(db):
    asyncpg = pytest.importorskip("asyncpg")
    emp, co = _user("emp"), _user("co")

    async def run():
        pool = await asyncpg.create_pool(min_size=1, max_size=2, ssl=False, **_db_params())
        srv._asyncpg_pool = pool
        try:
            with pytest.raises(auth.MessagePolicyError) as ei:
                await srv._pipeline_asyncpg(emp, co, "x", False)
            assert ei.value.code == "company_start" and ei.value.status == 403
            msg, unread, _ = await srv._pipeline_asyncpg(co, emp, "hello", False)
            assert msg["sender_id"] == co and unread >= 1
            await srv._pipeline_asyncpg(emp, co, "reply", True)
            auth.end_conversation(co, emp)
            with pytest.raises(auth.MessagePolicyError) as ei:
                await srv._pipeline_asyncpg(emp, co, "x", False)
            assert ei.value.code == "ended"
            await srv._pipeline_asyncpg(co, emp, "again", False)      # re-opens
            await srv._pipeline_asyncpg(emp, co, "ok", False)
        finally:
            srv._asyncpg_pool = None
            await pool.close()

    asyncio.run(run())
