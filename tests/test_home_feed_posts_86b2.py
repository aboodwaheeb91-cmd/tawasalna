"""Task 8.6b-2 — GET /home/feed posts carry the TwPostCard fields (SYSTEMS_INDEX §12 / §61).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), schema from the
real startup migrations:
  - filter=posts → theme_color · comments_enabled · author_type 'co' · views_count · appreciations_count ·
    viewer_appreciated · viewer_saved · comments_count — true / counted for the viewer who did it,
    false for another viewer (counts are the same for both)
  - a comment by an account the viewer blocked is not counted
  - a post of a company the viewer blocked is not in the feed
  - /company/posts: same shape and values as the query it had before 8.6b-2 (kept here as the reference)
  - auth.get_company_post_stats: one entry per id, nothing for other posts, guest = false
Run: python -m pytest tests/test_home_feed_posts_86b2.py -q
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-home-feed-86b2-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import blocks_suspension as bs
import server as srv

client = TestClient(srv.app)
USER_SECRET = "test-user-secret-86b2-" + "u" * 32
STAT_FIELDS = ("views_count", "appreciations_count", "viewer_appreciated", "viewer_saved", "comments_count")


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
    yield


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", USER_SECRET)
    monkeypatch.setattr(auth, "get_session_state", lambda uid: {"changed": None, "sv": 0})
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    yield
    srv._rate_store.clear()


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut):
    n = uuid.uuid4().hex[:10]
    uid = int(_sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', :ut) RETURNING id",
                   t={"co": "C", "emp": "U"}[ut] + n, n="Acc " + n, e=n + "@t.test", ut=ut)[0][0])
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return uid


def _h(uid, ut):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": ut, "tw_id": "X"})}


def _feed_posts(uid):
    r = client.get("/home/feed?filter=posts&limit=50", headers=_h(uid, "emp"))
    assert r.status_code == 200
    return {it["id"]: it for it in r.json()["items"] if it.get("type") == "post"}


# The /company/posts query as it was before 8.6b-2 — the reference for "same values".
def _legacy_company_posts(company_id, viewer):
    with auth.db_conn() as c:
        rows = c.run(
            "SELECT cp.id, cp.body, cp.tags, cp.theme_color, cp.comments_enabled, cp.created_at, "
            "COALESCE(v.cnt, 0), COALESCE(a.cnt, 0), (upa.user_id IS NOT NULL), (ups.user_id IS NOT NULL), "
            "COALESCE(cmt.cnt, 0) FROM company_posts cp "
            "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_views GROUP BY post_id) v ON cp.id = v.post_id "
            "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_appreciations GROUP BY post_id) a ON cp.id = a.post_id "
            "LEFT JOIN company_post_appreciations upa ON upa.post_id = cp.id AND upa.user_id = :v "
            "LEFT JOIN company_post_saves ups ON ups.post_id = cp.id AND ups.user_id = :v "
            "LEFT JOIN (SELECT c.post_id, COUNT(*) AS cnt FROM company_post_comments c "
            "LEFT JOIN company_post_comments rc ON rc.id = c.reply_to_comment_id WHERE c.status = 'active' "
            "AND c.post_id IN (SELECT id FROM company_posts WHERE company_id = :cid) "
            "AND " + bs.visible_sql("c.user_id") + " AND (rc.id IS NULL OR " + bs.visible_sql("rc.user_id") + ") "
            "GROUP BY c.post_id) cmt ON cp.id = cmt.post_id "
            "WHERE cp.company_id = :cid ORDER BY cp.created_at DESC",
            cid=company_id, v=int(viewer or 0), bs_viewer=int(viewer or 0))
    cols = ["id", "body", "tags", "theme_color", "comments_enabled", "created_at"] + list(STAT_FIELDS)
    return [auth._serialize(dict(zip(cols, r))) for r in rows]


@pytest.fixture(scope="module")
def world(db):
    co, emp, other, blocked = _user("co"), _user("emp"), _user("emp"), _user("emp")
    p1 = auth.create_company_post(co, "منشور أول", tags=["توظيف"], theme_color="purple", comments_enabled=True)["id"]
    p2 = auth.create_company_post(co, "منشور تاني", comments_enabled=False)["id"]
    auth.set_company_post_appreciation(p1, emp, True)
    auth.set_company_post_appreciation(p1, other, True)
    auth.set_company_post_save(p1, emp, True)
    auth.record_company_post_view(p1, viewer_user_id=emp)
    auth.record_company_post_view(p1, visitor_key="vk-" + uuid.uuid4().hex)
    auth.create_company_post_comment(p1, emp, "تعليق")
    auth.create_company_post_comment(p1, blocked, "تعليق من حساب محظور")
    bs.block(emp, blocked)   # emp blocks the commenter → its comment is not counted for emp
    return {"co": co, "emp": emp, "other": other, "blocked": blocked, "p1": p1, "p2": p2}


def test_feed_posts_carry_the_card_fields_for_the_viewer(world):
    w = world
    mine = _feed_posts(w["emp"])
    assert w["p1"] in mine and w["p2"] in mine
    a = mine[w["p1"]]
    assert a["author_type"] == "co" and a["author_id"] == w["co"]
    assert a["theme_color"] == "purple" and a["comments_enabled"] is True and a["tags"] == ["توظيف"]
    assert (a["views_count"], a["appreciations_count"]) == (2, 2)
    assert a["viewer_appreciated"] is True and a["viewer_saved"] is True
    assert a["comments_count"] == 1   # the blocked account's comment is not counted
    b = mine[w["p2"]]
    assert b["comments_enabled"] is False and b["theme_color"] is None
    assert [b[k] for k in STAT_FIELDS] == [0, 0, False, False, 0]

    theirs = _feed_posts(w["other"])[w["p1"]]
    assert theirs["viewer_appreciated"] is True and theirs["viewer_saved"] is False
    assert theirs["comments_count"] == 2   # no block for this viewer → both comments
    third = _feed_posts(w["blocked"])
    assert w["p1"] in third   # blocked by emp, but the company is not involved
    t = third[w["p1"]]
    assert t["viewer_appreciated"] is False and t["viewer_saved"] is False
    assert (t["views_count"], t["appreciations_count"]) == (2, 2)


def test_post_of_a_blocked_company_is_not_in_the_feed(world):
    viewer = _user("emp")
    assert world["p1"] in _feed_posts(viewer)
    bs.block(viewer, world["co"])
    assert world["p1"] not in _feed_posts(viewer) and world["p2"] not in _feed_posts(viewer)


def test_company_posts_same_shape_and_values_as_before(world):
    w = world
    for viewer in (w["emp"], w["other"], None):
        headers = _h(viewer, "emp") if viewer else {}
        r = client.get(f"/company/posts/{w['co']}", headers=headers)
        assert r.status_code == 200
        got = r.json()["posts"]
        want = _legacy_company_posts(w["co"], viewer)
        assert [list(p.keys()) for p in got] == [list(p.keys()) for p in want]
        assert got == want, viewer


def test_post_stats_helper_one_entry_per_id(world):
    w = world
    with auth.db_conn() as c:
        assert auth.get_company_post_stats(c, [], w["emp"]) == {}
        st = auth.get_company_post_stats(c, [w["p1"], w["p2"], w["p1"]], None)
    assert set(st) == {w["p1"], w["p2"]}
    assert st[w["p1"]]["viewer_appreciated"] is False and st[w["p1"]]["viewer_saved"] is False
    assert st[w["p1"]]["appreciations_count"] == 2
