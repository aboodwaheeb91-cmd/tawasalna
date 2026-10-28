"""Task 8.6d-1 — GET /home/feed «load more": signed cursor + saved job order (SYSTEMS_INDEX §12 · docs/rules/home-v2.md).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), schema from the
real startup migrations:
  - walking every page of every filter returns everything exactly once, in order
    (jobs: match ↓ · created_at ↓ · id ↓ · posts / news: created_at ↓ · id ↓)
  - «all": one fixed pattern per page (job, post, news); an exhausted type's slot goes to the others
  - a job edited between pages keeps its place (no repeat, no skip) · a job hidden by the admin / a suspended company
    → only those jobs + posts drop · a company blocked by the viewer → its posts drop, its jobs stay
  - content created after the first page never shows on later pages
  - profession / skills changed → 409 feed_reset · expired / missing list → 409
  - tampered / other account / other filter / expired cursor → 422 invalid_cursor
  - the list insert failing → first page works, next_cursor null · per-account cap on saved lists
  - timing: 5,000 jobs + 20,000 posts + 1,000 news — first and tenth page (wide bound, numbers printed)
Run: python -m pytest tests/test_home_feed_cursor_86d.py -q -s
"""
import base64
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-home-feed-86d-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import blocks_suspension as bs
import server as srv

client = TestClient(srv.app)
USER_SECRET = "test-user-secret-86d-" + "u" * 32


@pytest.fixture(scope="module")
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP SCHEMA public CASCADE")
    c.run("CREATE SCHEMA public")
    auth.release_conn(c)
    srv._run_startup_migrations()
    assert srv._MIGRATION_STATUS.get("feed_snapshots") == "ok"
    yield


@pytest.fixture(autouse=True)
def env(monkeypatch, db):
    monkeypatch.setattr(srv, "JWT_SECRET", USER_SECRET)
    monkeypatch.setattr(auth, "get_session_state", lambda uid: {"changed": None, "sv": 0})
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    _sql("TRUNCATE jobs, company_posts, news_posts, feed_snapshots CASCADE")
    yield
    srv._rate_store.clear()


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut, pid=None, skills=()):
    n = uuid.uuid4().hex[:10]
    uid = int(_sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', :ut) RETURNING id",
                   t={"co": "C", "emp": "U"}[ut] + n, n="Acc " + n, e=n + "@t.test", ut=ut)[0][0])
    _sql("INSERT INTO profiles (user_id, profession_id) VALUES (:u, :p) ON CONFLICT DO NOTHING", u=uid, p=pid)
    for s in skills:
        _sql("INSERT INTO user_skills (user_id, skill) VALUES (:u, :s)", u=uid, s=s)
    return uid


def _prof(group):
    n = uuid.uuid4().hex[:8]
    return int(_sql("INSERT INTO profession_categories (name_ar, name_en, slug, category_group) "
                    "VALUES (:n, :n, :n, :g) RETURNING id", n="p" + n, g=group)[0][0])


def _job(co, mins_ago, pid=None, skills=()):
    return int(_sql("INSERT INTO jobs (company_id, title, status, profession_id, skills, created_at) "
                    "VALUES (:c, 'وظيفة', 'active', :p, CAST(:s AS TEXT[]), NOW() - make_interval(mins => :m)) "
                    "RETURNING id", c=co, p=pid, s=list(skills), m=mins_ago)[0][0])


def _post(co, mins_ago):
    return int(_sql("INSERT INTO company_posts (company_id, body, created_at) "
                    "VALUES (:c, 'منشور', NOW() - make_interval(mins => :m)) RETURNING id", c=co, m=mins_ago)[0][0])


def _news(mins_ago):
    return int(_sql("INSERT INTO news_posts (title, status, created_at) "
                    "VALUES ('خبر', 'published', NOW() - make_interval(mins => :m)) RETURNING id", m=mins_ago)[0][0])


def _h(uid, ut="emp"):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": ut, "tw_id": "X"})}


def _page(uid, f, limit, cursor=None, ut="emp"):
    params = {"filter": f, "limit": limit}
    if cursor:
        params["cursor"] = cursor
    return client.get("/home/feed", params=params, headers=_h(uid, ut))


def _walk(uid, f, limit, max_pages=200):
    pages, cursor = [], None
    for _ in range(max_pages):
        r = _page(uid, f, limit, cursor)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"items", "filter", "total", "next_cursor"} and body["total"] == len(body["items"])
        pages.append([(i["type"], i["id"]) for i in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages
    raise AssertionError("feed never ended")


def _flat(pages):
    return [x for p in pages for x in p]


def _pattern(queues, limit):
    """Expected «all" pages: per page cycle job → post → news, skipping an exhausted type."""
    q = {t: list(v) for t, v in queues.items()}
    order, pages = ("opportunity", "post", "news"), []
    while any(q.values()):
        page, i = [], 0
        while len(page) < limit and any(q.values()):
            t = order[i % 3]
            i += 1
            if q[t]:
                page.append((t, q[t].pop(0)))
        pages.append(page)
    return pages


def _rest(uid, f, limit, cursor):
    pages, c = [], cursor
    while c:
        r = _page(uid, f, limit, c)
        assert r.status_code == 200, r.text
        pages.append([(i["type"], i["id"]) for i in r.json()["items"]])
        c = r.json()["next_cursor"]
    return _flat(pages)


# ── order + completeness ────────────────────────────────────────────────────

def test_jobs_walk_match_then_date_then_id():
    g = "grp-" + uuid.uuid4().hex[:6]
    p1, p2, p3 = _prof(g), _prof(g), _prof("other-" + g)
    emp = _user("emp", pid=p1, skills=("a", "b"))
    co = _user("co")
    want = {}   # id → (score by the documented table, minutes ago)
    want[_job(co, 500, pid=p1)] = (100, 500)                     # exact profession
    want[_job(co, 10, pid=p2, skills=("a",))] = (50, 10)         # same group + 1 skill
    want[_job(co, 200, pid=p3, skills=("a", "b"))] = (20, 200)   # 2 skills
    t1, t2 = _job(co, 100, pid=p3, skills=("A", "b")), _job(co, 100, pid=p3, skills=("a", "B"))
    want[t1] = want[t2] = (20, 100)                              # equal score + equal created_at → id ↓
    _sql("UPDATE jobs SET created_at = (SELECT created_at FROM jobs WHERE id = :a) WHERE id = :b", a=t1, b=t2)
    for m in range(20):
        want[_job(co, 30 + m * 7, pid=p3)] = (0, 30 + m * 7)
    expected = sorted(want, key=lambda j: (-want[j][0], want[j][1], -j))
    pages = _walk(emp, "opportunities", 4)
    got = [i for _, i in _flat(pages)]
    assert got == expected and len(set(got)) == len(got)
    assert got.index(t2) + 1 == got.index(t1)                    # tie → higher id first
    assert all(len(p) == 4 for p in pages[:-1])


def test_every_filter_walks_everything_once_with_the_all_pattern():
    co = _user("co")
    emp = _user("emp")
    jobs = [_job(co, 3 + i * 10) for i in range(8)]              # no match context → created_at ↓
    posts = [_post(co, 1 + i * 5) for i in range(11)]
    news = [_news(2 + i * 20) for i in range(3)]                 # runs out mid-walk
    tie = _post(co, 1)
    _sql("UPDATE company_posts SET created_at = (SELECT created_at FROM company_posts WHERE id = :a) "
         "WHERE id = :b", a=posts[0], b=tie)
    posts = [tie] + posts                                        # same created_at → higher id first
    assert [i for _, i in _flat(_walk(emp, "opportunities", 3))] == jobs
    assert [i for _, i in _flat(_walk(emp, "posts", 5))] == posts
    assert [i for _, i in _flat(_walk(emp, "news", 2))] == news
    for limit in (5, 7):
        pages = _walk(emp, "all", limit)
        assert pages == _pattern({"opportunity": jobs, "post": posts, "news": news}, limit)
        assert all(len(p) == limit for p in pages[:-1])          # no empty slot once news is gone
    _sql("DELETE FROM news_posts")
    pages = _walk(emp, "all", 6)
    assert pages == _pattern({"opportunity": jobs, "post": posts, "news": []}, 6)
    assert pages[0][:4] == [("opportunity", jobs[0]), ("post", posts[0]), ("opportunity", jobs[1]), ("post", posts[1])]


# ── changes between pages ───────────────────────────────────────────────────

def test_job_edited_between_pages_keeps_its_place():
    g = "grp-" + uuid.uuid4().hex[:6]
    p1, p3 = _prof(g), _prof("other-" + g)
    emp = _user("emp", pid=p1, skills=("a",))
    co = _user("co")
    jobs = [_job(co, 5 + i * 10, pid=p3) for i in range(12)]
    r = _page(emp, "opportunities", 4)
    first = [i["id"] for i in r.json()["items"]]
    assert first == jobs[:4]
    _sql("UPDATE jobs SET profession_id = :p, skills = ARRAY['a'] WHERE id = :j", p=p1, j=jobs[9])   # would rank first now
    _sql("UPDATE jobs SET accepts_all_professions = true WHERE id = :j", j=jobs[6])
    _sql("UPDATE jobs SET profession_id = :p WHERE id = :j", p=p1, j=jobs[1])                         # already seen
    rest = [i for _, i in _rest(emp, "opportunities", 4, r.json()["next_cursor"])]
    assert first + rest == jobs


def _split_after_first_page(emp, limit, change):
    r = _page(emp, "all", limit)
    seen = [(i["type"], i["id"]) for i in r.json()["items"]]
    change()
    got = seen + _rest(emp, "all", limit, r.json()["next_cursor"])
    assert len(set(got)) == len(got)
    return [i for t, i in got if t == "opportunity"], [i for t, i in got if t == "post"]


def test_hidden_job_or_suspended_company_between_pages_drops_only_those():
    co, co2 = _user("co"), _user("co")
    emp = _user("emp")
    jobs = [_job(co2 if i in (7, 10) else co, 5 + i * 10) for i in range(12)]
    posts = [_post(co2 if i in (5, 8) else co, 2 + i * 10) for i in range(9)]

    def change():
        _sql("UPDATE jobs SET admin_hidden_at = NOW() WHERE id = :j", j=jobs[5])   # admin hides one job
        bs.set_suspension(co2, True, None, "test")                                  # company suspended

    got_jobs, got_posts = _split_after_first_page(emp, 6, change)
    assert got_jobs == [j for i, j in enumerate(jobs) if i not in (5, 7, 10)]      # its jobs gone, rest complete
    assert got_posts == [p for i, p in enumerate(posts) if i not in (5, 8)]         # its posts gone, rest complete


def test_blocked_company_between_pages_hides_its_posts_not_its_jobs():
    co, co3 = _user("co"), _user("co")
    emp = _user("emp")
    jobs = [_job(co3 if i in (6, 9) else co, 5 + i * 10) for i in range(12)]
    posts = [_post(co3 if i in (5, 7) else co, 2 + i * 10) for i in range(9)]
    got_jobs, got_posts = _split_after_first_page(emp, 6, lambda: bs.block(emp, co3))
    assert got_jobs == jobs                                                          # a block never hides a job (§25f)
    assert got_posts == [p for i, p in enumerate(posts) if i not in (5, 7)]


def test_content_created_after_the_first_page_does_not_show():
    g = "grp-" + uuid.uuid4().hex[:6]
    p1 = _prof(g)
    emp = _user("emp", pid=p1)
    co = _user("co")
    jobs = [_job(co, 5 + i * 10) for i in range(5)]
    posts = [_post(co, 5 + i * 10) for i in range(5)]
    news = [_news(5 + i * 10) for i in range(5)]
    r = _page(emp, "all", 3)
    seen = [(i["type"], i["id"]) for i in r.json()["items"]]
    new = {("opportunity", _job(co, 0, pid=p1)), ("post", _post(co, 0)), ("news", _news(0))}
    got = seen + _rest(emp, "all", 3, r.json()["next_cursor"])
    assert not new & set(got)
    assert sorted(got) == sorted([("opportunity", j) for j in jobs] + [("post", p) for p in posts]
                                 + [("news", n) for n in news])


# ── 409 feed_reset ──────────────────────────────────────────────────────────

def _first_cursor(emp, f="opportunities"):
    co = _user("co")
    for i in range(6):
        _job(co, 5 + i)
        _post(co, 5 + i)
    r = _page(emp, f, 2)
    assert r.status_code == 200 and r.json()["next_cursor"]
    return r.json()["next_cursor"]


def _err(r):
    return r.status_code, r.json().get("error", {}).get("code")


def test_profile_change_or_expired_list_is_409():
    g = "grp-" + uuid.uuid4().hex[:6]
    p1, p2 = _prof(g), _prof(g)
    emp = _user("emp", pid=p1, skills=("a",))
    cur = _first_cursor(emp)
    assert _page(emp, "opportunities", 2, cur).status_code == 200
    _sql("INSERT INTO user_skills (user_id, skill) VALUES (:u, 'z')", u=emp)
    assert _err(_page(emp, "opportunities", 2, cur)) == (409, "feed_reset")
    cur = _first_cursor(emp)
    _sql("UPDATE profiles SET profession_id = :p WHERE user_id = :u", p=p2, u=emp)
    assert _err(_page(emp, "opportunities", 2, cur)) == (409, "feed_reset")
    cur = _first_cursor(emp, "all")
    _sql("UPDATE feed_snapshots SET created_at = NOW() - INTERVAL '2 days' WHERE user_id = :u", u=emp)
    assert _err(_page(emp, "all", 2, cur)) == (409, "feed_reset")
    cur = _first_cursor(emp, "all")
    _sql("DELETE FROM feed_snapshots WHERE user_id = :u", u=emp)
    assert _err(_page(emp, "all", 2, cur)) == (409, "feed_reset")


# ── 422 invalid_cursor ──────────────────────────────────────────────────────

def _payload(cur):
    body = cur.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def test_bad_cursor_is_422():
    emp, other = _user("emp"), _user("emp")
    cur = _first_cursor(emp, "all")
    body, sig = cur.split(".")
    p = _payload(cur)
    p["jo"] = 0
    forged = base64.urlsafe_b64encode(json.dumps(p, separators=(",", ":")).encode()).rstrip(b"=").decode()
    cases = [
        forged + "." + sig,                                            # edited body, old signature
        body + "." + sig[:-2] + ("AA" if sig[-2:] != "AA" else "BB"),  # edited signature
        "garbage", "a.b.c", "",
    ]
    for c in cases:
        if c:
            assert _err(_page(emp, "all", 2, c)) == (422, "invalid_cursor"), c
    assert _err(_page(other, "all", 2, cur)) == (422, "invalid_cursor")            # another account
    assert _err(_page(emp, "posts", 2, cur)) == (422, "invalid_cursor")            # another filter
    old = dict(p, exp=int(time.time()) - 5)
    assert _err(_page(emp, "all", 2, srv._feed_cursor_encode(old))) == (422, "invalid_cursor")   # expired
    stolen = dict(p, uid=other)                                                    # validly signed, list of emp
    assert _err(_page(other, "all", 2, srv._feed_cursor_encode(stolen))) == (422, "invalid_cursor")
    assert _page(emp, "all", 2, cur).status_code == 200                            # the real one still works


# ── list storage ────────────────────────────────────────────────────────────

def test_list_insert_failure_first_page_still_works():
    emp = _user("emp")
    co = _user("co")
    for i in range(5):
        _job(co, i + 1)
    _sql("ALTER TABLE feed_snapshots RENAME TO feed_snapshots_off")
    try:
        r = _page(emp, "opportunities", 2)
        assert r.status_code == 200 and len(r.json()["items"]) == 2 and r.json()["next_cursor"] is None
        r = _page(emp, "posts", 2)                                     # no list needed → still pages
        assert r.status_code == 200
    finally:
        _sql("ALTER TABLE feed_snapshots_off RENAME TO feed_snapshots")


def test_saved_lists_per_account_are_capped():
    emp = _user("emp")
    co = _user("co")
    for i in range(3):
        _job(co, i + 1)
    for _ in range(srv.tw_settings.limit("feed_snapshots_per_user") + 3):
        assert _page(emp, "all", 1).status_code == 200
    n = int(_sql("SELECT COUNT(*) FROM feed_snapshots WHERE user_id = :u", u=emp)[0][0])
    assert n == srv.tw_settings.limit("feed_snapshots_per_user")


# ── timing (wide bound against a collapse — the full load test is step 11) ───

def test_timing_realistic_volume():
    g = "grp-" + uuid.uuid4().hex[:6]
    p1, p2 = _prof(g), _prof(g)
    emp = _user("emp", pid=p1, skills=("python", "sql"))
    cos = [_user("co") for _ in range(50)]
    _sql("INSERT INTO jobs (company_id, title, status, profession_id, skills, created_at) "
         "SELECT (CAST(:cos AS BIGINT[]))[1 + g % 50], 'وظيفة ' || g, 'active', "
         "CASE g % 3 WHEN 0 THEN CAST(:p1 AS INT) WHEN 1 THEN CAST(:p2 AS INT) ELSE NULL END, "
         "CASE WHEN g % 4 = 0 THEN ARRAY['python','sql'] ELSE ARRAY['excel'] END, "
         "NOW() - make_interval(mins => g) FROM generate_series(1, 5000) g", cos=cos, p1=p1, p2=p2)
    _sql("INSERT INTO company_posts (company_id, body, created_at) "
         "SELECT (CAST(:cos AS BIGINT[]))[1 + g % 50], 'منشور ' || g, NOW() - make_interval(secs => g * 7) "
         "FROM generate_series(1, 20000) g", cos=cos)
    _sql("INSERT INTO news_posts (title, status, created_at) "
         "SELECT 'خبر ' || g, 'published', NOW() - make_interval(mins => g) FROM generate_series(1, 1000) g")
    for t in ("jobs", "company_posts", "news_posts"):
        _sql("ANALYZE " + t)
    for f in ("all", "opportunities"):
        t0 = time.perf_counter()
        r = _page(emp, f, 20)
        first = time.perf_counter() - t0
        assert r.status_code == 200 and len(r.json()["items"]) == 20
        cur, tenth = r.json()["next_cursor"], 0.0
        for _ in range(9):
            t0 = time.perf_counter()
            r = _page(emp, f, 20, cur)
            tenth = time.perf_counter() - t0
            assert r.status_code == 200 and len(r.json()["items"]) == 20
            cur = r.json()["next_cursor"]
        print(f"\n[8.6d-1 timing] filter={f}: first page {first * 1000:.0f} ms · tenth page {tenth * 1000:.0f} ms")
        assert first < 2.0 and tenth < 2.0
