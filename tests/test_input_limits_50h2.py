"""Task 5.0h-2 — the rest of the input / flood limits (tw_limits.py — SYSTEMS_INDEX §54n).

Behaviour only (real endpoints + real PostgreSQL schema):
  1  POST /messages/send: RATES["message_send"] per account → 429, after the length check, before the DB
  2  AUD-P2-07 / 18  views: same viewer + same target once per RATES["view_count"] window (posts: account,
                     else client IP — a new visitor_key does not count again) · owner never counted ·
                     profile views use the same window in SQL
  3  AUD-P2-17       password > LIMITS["password_max_bytes"] UTF-8 bytes → 422 on register / reset / change;
                     login unchanged
  4  AUD-P2-16       login lock per email + per IP + per IP and email pair — one reply, never says
                     whether the email exists
  5  AUD-P2-13       _rate_store swept on use (TTL by window + key cap) · IP_TO_COUNTRY_CACHE capped + TTL
  6  #626 note       run_scheduler_cycle: failed pg_advisory_unlock → connection closed, never pooled

  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_input_limits_50h2.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-input-limits-50h2-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv
import tw_limits
import tw_terms

client = TestClient(srv.app)
L, R = tw_limits.LIMITS, tw_limits.RATES


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(name, utype="emp"):
    return _sql("INSERT INTO users (tw_id, email, full_name, user_type, password_hash) "
                "VALUES (:tw, :e, :n, :t, 'x') RETURNING id",
                tw=("C" if utype == "co" else "U") + name, e=name + "@x.com", n=name, t=utype)[0][0]


def _bearer(uid, utype="emp"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": utype})}


def _err(r):
    body = r.json()
    assert body["ok"] is False, body
    return body["error"]


@pytest.fixture
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP SCHEMA public CASCADE")
    c.run("CREATE SCHEMA public")
    auth.release_conn(c)
    auth.init_db()
    auth._migrate_profiles_user_unique()
    auth._migrate_session_version()
    auth.bs.migrate_blocks_suspension()     # task 5.4 — users.suspended_* + blocks (read by the session check)
    auth._migrate_password_changed_at()
    auth.ensure_company_tables()
    auth._migrate_conversation_endings()   # read by GET /profile/{id} (message policy)
    tw_terms.migrate_terms_acceptance()    # written by POST /auth/register (task terms)
    yield


@pytest.fixture(autouse=True)
def clean_stores():
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
    yield
    srv._rate_store.clear()


# ── 1. message send flood ──
def test_message_send_flood_is_429_before_the_db(db, monkeypatch):
    a, b = _user("ma"), _user("mb")
    max_hits, _ = R["message_send"]
    assert (max_hits, R["message_send"][1]) == (30, 60)
    srv._rate_store["message_send:%d" % a] = [srv._time.time()] * max_hits   # the minute is full

    def no_db(*a, **k):
        raise AssertionError("DB reached after the rate limit")
    monkeypatch.setattr(srv, "send_message_pipeline", no_db)
    monkeypatch.setattr(srv, "_asyncpg_pool", None)
    r = client.post("/messages/send", headers=_bearer(a), json={"receiver_id": b, "content": "hi"})
    assert r.status_code == 429
    e = _err(r)
    assert e["code"] == "rate_limited" and e["message"] == srv._tw_text("limits.rate_limited")
    # length is checked first → a too-long text is still 422, not 429
    r = client.post("/messages/send", headers=_bearer(a),
                    json={"receiver_id": b, "content": "x" * (L["message_max"] + 1)})
    assert r.status_code == 422 and _err(r)["code"] == "too_long"
    # another account is not affected
    srv._rate_store.pop("message_send:%d" % a)
    monkeypatch.setattr(srv, "send_message_pipeline", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db")))
    assert client.post("/messages/send", headers=_bearer(b), json={"receiver_id": a, "content": "x"}).status_code != 429


# ── 2. view counters ──
def _views(pid):
    return _sql("SELECT COUNT(*) FROM company_post_views WHERE post_id = :p", p=pid)[0][0]


def test_post_view_counted_once_per_viewer_and_not_for_owner(db):
    co, viewer = _user("vco", "co"), _user("vemp")
    pid = client.post("/company/posts", headers=_bearer(co, "co"), json={"body": "منشور"}).json()["post"]["id"]
    url = f"/company/posts/{pid}/view"
    assert client.post(url, headers=_bearer(co, "co"), json={}).json()["reason"] == "owner"
    assert client.post(url, headers=_bearer(viewer), json={}).json()["recorded"] is True
    r = client.post(url, headers=_bearer(viewer), json={}).json()
    assert r["status"] == "skipped" and r["reason"] == "duplicate"
    # anonymous: a new visitor_key per request from the same IP does not count again
    ip = {"X-Real-IP": "198.51.100.7"}
    assert client.post(url, headers=ip, json={"visitor_key": "k1"}).json()["recorded"] is True
    assert client.post(url, headers=ip, json={"visitor_key": "k2"}).json()["reason"] == "duplicate"
    assert client.post(url, headers={"X-Real-IP": "198.51.100.8"}, json={"visitor_key": "k3"}).json()["recorded"] is True
    assert _views(pid) == 3
    # the window passes → the same viewer counts again (the DB still keeps one row per account)
    for k in [k for k in srv._rate_store if k.startswith("view_count:")]:
        srv._rate_store[k] = [t - R["view_count"][1] for t in srv._rate_store[k]]
    assert client.post(url, headers=ip, json={"visitor_key": "k4"}).json()["recorded"] is True


def test_profile_view_window_comes_from_rates(db, monkeypatch):
    owner, viewer = _user("pown"), _user("pview")
    win = R["view_count"][1]
    assert auth.record_profile_view(owner, owner, win) is False             # owner never counted
    assert auth.record_profile_view(owner, viewer, win) is True
    assert auth.record_profile_view(owner, viewer, win) is False            # inside the window
    _sql("UPDATE profile_views SET viewed_at = NOW() - make_interval(secs => :s)", s=win + 5)
    assert auth.record_profile_view(owner, viewer, win) is True             # window passed
    seen = []
    monkeypatch.setattr(srv, "record_profile_view", lambda a, b, w=None: seen.append(w))
    client.get(f"/profile/{owner}", headers=_bearer(viewer))
    assert seen == [win]


# ── 3. password longer than 72 bytes ──
PW_OK = "ب" * (L["password_max_bytes"] // 2)            # 36 Arabic chars = 72 bytes
PW_LONG = "ب" * (L["password_max_bytes"] // 2 + 1)      # 37 chars = 74 bytes — bytes, not characters


def _pw_err(r, field):
    assert r.status_code == 422, r.text
    e = _err(r)
    assert e["code"] == "password_too_long" and e["field"] == field
    assert e["message"] == srv._tw_text("limits.password_too_long", max=L["password_max_bytes"])


def test_password_too_long_register_change_reset(db):
    assert L["password_max_bytes"] == 72 and len(PW_LONG) < 72
    reg = {"user_type": "emp", "email": "p1@x.com", "first_name": "أ", "last_name": "ب", "terms_accepted": True}
    _pw_err(client.post("/auth/register", json={**reg, "password": PW_LONG}), "password")
    assert _sql("SELECT COUNT(*) FROM users")[0][0] == 0
    r = client.post("/auth/register", json={**reg, "password": PW_OK})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    _pw_err(client.put("/auth/password", headers=_bearer(uid),
                       json={"current_password": PW_OK, "new_password": PW_LONG}), "new_password")
    _pw_err(client.post("/auth/password-reset/confirm", json={"token": "t", "new_password": PW_LONG}),
            "new_password")
    # login is unchanged: a long password is checked as before (wrong → 401, never 422)
    assert client.post("/auth/login", json={"email": "p1@x.com", "password": "z" * 80}).status_code == 401
    assert client.post("/auth/login", json={"email": "p1@x.com", "password": PW_OK}).status_code == 200


# ── 4. login lock: email · IP · IP + email ──
def _login(email, ip):
    return client.post("/auth/login", json={"email": email, "password": "bad"}, headers={"X-Real-IP": ip})


def _locked(r):
    assert r.status_code == 429, r.text
    e = _err(r)
    assert e["code"] == "login_locked"
    return e["message"]


def test_login_lock_per_ip_and_pair(monkeypatch):
    monkeypatch.setattr(srv, "authenticate_user", lambda e, p: None)
    pair_max = R["login_ip_email"][0]
    for _ in range(pair_max):
        assert _login("a@x.com", "203.0.113.1").status_code == 401
    pair_msg = _locked(_login("a@x.com", "203.0.113.1"))
    assert _login("a@x.com", "203.0.113.2").status_code == 401        # same email, other IP — not yet
    srv._rate_store.clear()
    ip_max = R["login_ip"][0]
    for i in range(ip_max):                                            # one IP, many emails
        assert _login(f"u{i}@x.com", "203.0.113.9").status_code == 401
    srv._rate_store.pop("ip:203.0.113.9", None)   # the per-minute /auth/* request limit — not this lock
    ip_msg = _locked(_login("fresh@x.com", "203.0.113.9"))
    assert _login("fresh@x.com", "203.0.113.10").status_code == 401   # other IP unaffected
    assert pair_msg == ip_msg                                          # one text for every lock


def test_login_lock_never_tells_whether_the_email_exists(db):
    _sql("INSERT INTO users (tw_id, email, full_name, user_type, password_hash) "
         "VALUES ('Ureal', 'real@x.com', 'r', 'emp', :h)", h=auth.hash_password("right-pass"))
    bodies = []
    for email in ("real@x.com", "ghost@x.com"):
        for i in range(R["login_email"][0]):
            r = _login(email, f"192.0.2.{i}")
            assert r.status_code == 401
            bodies.append(("401", r.json()))
        bodies.append(("429", _login(email, "192.0.2.200").json()))
    by_email = len(bodies) // 2
    assert bodies[:by_email] == bodies[by_email:]
    assert "real@x.com" not in str(bodies) and "ghost" not in str(bodies)


# ── 5. bounded in-memory stores ──
def test_rate_store_sweep_ttl_and_key_cap(monkeypatch):
    now = srv._time.time()
    srv._rate_store["message_send:1"] = [now - R["message_send"][1] - 1]   # expired by its own window
    srv._rate_store["message_send:2"] = [now]
    srv._rate_store["pwreset-ip:x"] = [now - 10]                           # unknown prefix → longest window
    srv._pwd_changed_cache[7] = (None, srv._time.monotonic() - srv._PWD_CHANGED_TTL - 1)
    srv._rate_sweep(force=True)
    assert "message_send:1" not in srv._rate_store
    assert "message_send:2" in srv._rate_store and "pwreset-ip:x" in srv._rate_store
    assert 7 not in srv._pwd_changed_cache
    # key cap: past the cap the oldest last-hit keys go first — on use, no thread
    monkeypatch.setitem(tw_limits.LIMITS, "mem_store_max_keys", 10)
    srv._rate_store.clear()
    for i in range(10):
        srv._rate_store[f"mention_search:old{i}"] = [now - 30 + i]
    assert srv._rate_ok("mention_search", "new")                           # 11th key → sweep
    assert len(srv._rate_store) <= 10
    assert "mention_search:new" in srv._rate_store and "mention_search:old0" not in srv._rate_store


def test_rate_hit_is_atomic_across_threads(monkeypatch):
    """Task 5.0h-3: check + count is one locked step — threads at the same instant never pass the limit."""
    import threading
    limit, n = 5, 40
    real_prune = srv._rate_prune_locked

    def slow_prune(key, window):          # widen the check → count gap a race would need
        hits = real_prune(key, window)
        srv._time.sleep(0.002)
        return hits
    monkeypatch.setattr(srv, "_rate_prune_locked", slow_prune)
    start, allowed = threading.Barrier(n), []

    def worker():
        start.wait()
        if srv._rate_hit("race:k", limit, 60):
            allowed.append(1)
    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(allowed) == limit and len(srv._rate_store["race:k"]) == limit


def test_login_lock_survives_a_full_store(monkeypatch):
    """Task 5.0h-3: a full store never evicts a running login lock — only its window ends it."""
    monkeypatch.setattr(srv, "authenticate_user", lambda e, p: None)
    for _ in range(R["login_ip_email"][0]):
        assert _login("victim@x.com", "203.0.113.50").status_code == 401
    lock_keys = {k for k in srv._rate_store if k.split(":", 1)[0] in srv._LOGIN_LOCKS}
    assert lock_keys
    cap = 10
    monkeypatch.setitem(tw_limits.LIMITS, "mem_store_max_keys", cap)
    now = srv._time.time()
    for i in range(cap * 3):                                  # flood with newer, ordinary keys
        srv._rate_store[f"mention_search:flood{i}"] = [now + i]
    srv._rate_sweep(force=True)
    assert lock_keys <= set(srv._rate_store)
    _locked(_login("victim@x.com", "203.0.113.50"))
    # only login keys left → the store may stay over the cap for a while
    srv._rate_store.clear()
    for i in range(cap * 2):
        srv._rate_store[f"login_ip:198.51.100.{i}"] = [now]
    srv._rate_sweep(force=True)
    assert len(srv._rate_store) == cap * 2
    # the window ends → the lock goes
    for k in srv._rate_store:
        srv._rate_store[k] = [now - R["login_ip"][1] - 1]
    srv._rate_sweep(force=True)
    assert srv._rate_store == {}


def test_ip_country_cache_cap_and_ttl(monkeypatch):
    srv.IP_TO_COUNTRY_CACHE.clear()
    monkeypatch.setitem(tw_limits.LIMITS, "ip_country_cache_max", 3)
    for i in range(5):
        srv._ip_country_cache_put(f"10.0.0.{i}", "JO")
    assert list(srv.IP_TO_COUNTRY_CACHE) == ["10.0.0.2", "10.0.0.3", "10.0.0.4"]
    assert srv.get_country_from_ip("10.0.0.4") == "JO"                     # fresh → no lookup
    srv.IP_TO_COUNTRY_CACHE["10.0.0.4"] = ("JO", srv.time.time() - L["ip_country_cache_ttl_s"] - 1)

    def lookup_fails(*a, **k):
        raise OSError("no network in tests")
    monkeypatch.setattr(srv.urllib.request, "urlopen", lookup_fails)
    assert srv.get_country_from_ip("10.0.0.4") == "DEFAULT"                # expired → looked up again
    assert "10.0.0.4" not in srv.IP_TO_COUNTRY_CACHE
    srv.IP_TO_COUNTRY_CACHE.clear()


# ── 6. scheduler: failed advisory unlock → connection closed, not pooled ──
class _Conn:
    def __init__(self, unlock_fails):
        self.unlock_fails, self.closed = unlock_fails, False

    def run(self, q, **kw):
        if "pg_try_advisory_lock" in q:
            return [[True]]
        if "pg_advisory_unlock" in q and self.unlock_fails:
            raise RuntimeError("connection lost")
        return []

    def close(self):
        self.closed = True


@pytest.mark.parametrize("unlock_fails", [True, False])
def test_scheduler_failed_unlock_closes_the_connection(monkeypatch, unlock_fails):
    conn, released = _Conn(unlock_fails), []
    monkeypatch.setattr(auth, "get_conn", lambda: conn)
    monkeypatch.setattr(auth, "release_conn", lambda c: released.append(c))
    monkeypatch.setattr(auth, "reset_stale_scheduler_jobs", lambda c: 0)
    monkeypatch.setattr(auth, "run_due_scheduler_jobs", lambda limit, runner_id: {"ok": False})
    auth.run_scheduler_cycle()
    if unlock_fails:
        assert conn.closed and released == []
    else:
        assert not conn.closed and released == [conn]
