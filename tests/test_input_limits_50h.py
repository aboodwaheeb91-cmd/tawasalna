"""Task 5.0h — input limits + flood limits (tw_limits.py — SYSTEMS_INDEX §54n).

Behaviour only (real endpoints + real PostgreSQL schema):
  AUD-P2-10        POST /messages/send content > message_max → 422 too_long (twT text), before the DB
  AUD-P2-12 / 36   company posts: body > post_body_max → 422 · tag not in TW.POST_TAGS → 422 ·
                   more than post_tags_max → 422 · create / edit flood → 429
  AUD-P2-11        reports: unknown report_type → 422 · long reason / target_url → 422 · same target
                   again → 429 duplicate_report · per-account flood → 429
  AUD-P2-33        /mention/search: ?limit= clamped to mention_limit_max · flood → 429
  AUD-P2-35        post comments paged by thread (limit + cursor), replies stay with their root
  page block       window.TW_LIMITS reaches the pages (twLimit reads the same numbers)

  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_input_limits_50h.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-input-limits-50h-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv
import tw_limits

client = TestClient(srv.app)
L, R = tw_limits.LIMITS, tw_limits.RATES
TAG = sorted(tw_limits.POST_TAGS)[0]


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


@pytest.fixture(autouse=True)
def env():
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
    auth._migrate_password_changed_at()
    auth.ensure_company_tables()
    auth._migrate_reports_targets()
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
    yield
    srv._rate_store.clear()


# ── page block ──
def test_limits_reach_the_pages():
    html = srv.read_html("messages.html")
    assert "window.TW_LIMITS=" in html
    assert '"message_max":%d' % L["message_max"] in html
    assert "fraud" in html.split("window.TW_LIMITS=", 1)[1].split("</script>", 1)[0]


# ── 1. messages ──
def test_message_too_long_is_422_with_twt_text():
    a, b = _user("ma"), _user("mb")
    r = client.post("/messages/send", headers=_bearer(a),
                    json={"receiver_id": b, "content": "x" * (L["message_max"] + 1)})
    assert r.status_code == 422
    e = _err(r)
    assert e["code"] == "too_long" and e["field"] == "content"
    assert e["message"] == srv._tw_text("limits.too_long", max=srv._fmt_number(L["message_max"]))
    assert _sql("SELECT COUNT(*) FROM messages")[0][0] == 0


# ── 2. company posts ──
def _post(co, **body):
    return client.post("/company/posts", headers=_bearer(co, "co"), json={"body": "منشور", **body})


def test_post_body_too_long_is_422():
    co = _user("co1", "co")
    r = _post(co, body="x" * (L["post_body_max"] + 1))
    assert r.status_code == 422 and _err(r)["code"] == "too_long"
    assert _post(co, body="x" * L["post_body_max"]).status_code == 200


def test_post_tags_allowlist_and_max():
    co = _user("co1", "co")
    r = _post(co, tags=["وسم من خارج القائمة"])
    assert r.status_code == 422 and _err(r)["code"] == "invalid_tags"
    assert _post(co, tags=[123]).status_code == 422
    many = sorted(tw_limits.POST_TAGS)[:L["post_tags_max"] + 1]
    r = _post(co, tags=many)
    assert r.status_code == 422 and _err(r)["code"] == "too_many_tags"
    r = _post(co, tags=[TAG, TAG])
    assert r.status_code == 200 and r.json()["post"]["tags"] == [TAG]
    pid = r.json()["post"]["id"]
    r = client.patch(f"/company/posts/{pid}", headers=_bearer(co, "co"), json={"body": "x", "tags": ["غريب"]})
    assert r.status_code == 422 and _err(r)["code"] == "invalid_tags"


def test_post_create_and_edit_flood_is_429():
    co = _user("co1", "co")
    pid = None
    for _ in range(R["post_create"][0]):
        r = _post(co)
        assert r.status_code == 200
        pid = r.json()["post"]["id"]
    r = _post(co)
    assert r.status_code == 429 and _err(r)["code"] == "rate_limited"
    for _ in range(R["post_edit"][0]):
        assert client.patch(f"/company/posts/{pid}", headers=_bearer(co, "co"), json={"body": "y"}).status_code == 200
    r = client.patch(f"/company/posts/{pid}", headers=_bearer(co, "co"), json={"body": "y"})
    assert r.status_code == 429


# ── 3. reports ──
def _report(emp, target, **over):
    body = {"reported_id": target, "reported_type": "user", "report_type": "spam", "reason": "سبب"}
    body.update(over)
    return client.post("/reports/submit", headers=_bearer(emp), json=body)


def test_report_type_and_lengths():
    emp, bad = _user("emp1"), _user("bad1")
    r = _report(emp, bad, report_type="sexual")
    assert r.status_code == 422 and _err(r)["code"] == "invalid_report_type"
    r = _report(emp, bad, reason="x" * (L["report_reason_max"] + 1))
    assert r.status_code == 422 and _err(r)["field"] == "reason"
    r = _report(emp, bad, target_url="https://x.com/" + "a" * L["report_url_max"])
    assert r.status_code == 422 and _err(r)["field"] == "target_url"
    assert _report(emp, bad, reason="   ").status_code == 422
    assert _sql("SELECT COUNT(*) FROM reports")[0][0] == 0


def test_same_report_twice_is_429_other_target_ok():
    emp, bad, bad2 = _user("emp1"), _user("bad1"), _user("bad2")
    assert _report(emp, bad).status_code == 200
    r = _report(emp, bad, report_type="fraud")
    assert r.status_code == 429 and _err(r)["code"] == "duplicate_report"
    assert _report(emp, bad2).status_code == 200
    assert _report(_user("emp2"), bad).status_code == 200      # another reporter — allowed
    assert _sql("SELECT COUNT(*) FROM reports")[0][0] == 3


def test_report_flood_is_429():
    emp = _user("emp1")
    targets = [_user(f"t{i}") for i in range(R["report_submit"][0] + 1)]
    for t in targets[:-1]:
        assert _report(emp, t).status_code == 200
    r = _report(emp, targets[-1])
    assert r.status_code == 429 and _err(r)["code"] == "rate_limited"


# ── 4. mention search ──
def test_mention_limit_is_clamped_and_rate_limited():
    me = _user("me")
    for i in range(L["mention_limit_max"] + 5):
        _user(f"نور{i}")
    r = client.get("/mention/search", params={"q": "نور", "limit": 500}, headers=_bearer(me))
    assert r.status_code == 200 and len(r.json()["candidates"]) == L["mention_limit_max"]
    for _ in range(R["mention_search"][0] - 1):
        assert client.get("/mention/search", headers=_bearer(me)).status_code == 200
    r = client.get("/mention/search", headers=_bearer(me))
    assert r.status_code == 429 and _err(r)["code"] == "rate_limited"


# ── 5. comments pagination ──
def test_comments_are_paged_by_thread():
    co, emp = _user("co1", "co"), _user("emp1")
    pid = _post(co).json()["post"]["id"]
    roots = []
    for i in range(5):
        roots.append(_sql("INSERT INTO company_post_comments (post_id, user_id, body) VALUES (:p, :u, :b) "
                          "RETURNING id", p=pid, u=emp, b=f"root{i}")[0][0])
    _sql("INSERT INTO company_post_comments (post_id, user_id, body, reply_to_comment_id) "
         "VALUES (:p, :u, 'reply0', :r)", p=pid, u=emp, r=roots[0])
    url = f"/company/posts/{pid}/comments"
    page1 = client.get(url, params={"limit": 2}).json()
    assert [c["body"] for c in page1["comments"]] == ["root0", "root1", "reply0"]
    assert page1["next_cursor"] == roots[1]
    page2 = client.get(url, params={"limit": 2, "cursor": page1["next_cursor"]}).json()
    assert [c["body"] for c in page2["comments"]] == ["root2", "root3"]
    page3 = client.get(url, params={"limit": 2, "cursor": page2["next_cursor"]}).json()
    assert [c["body"] for c in page3["comments"]] == ["root4"] and page3["next_cursor"] is None
    # no limit → default page size; ?limit= above the ceiling → the ceiling
    assert len(client.get(url).json()["comments"]) == 6
    assert client.get(url, params={"limit": 10_000}).status_code == 200
