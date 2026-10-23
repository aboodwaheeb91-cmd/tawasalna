"""AUD-P2-49 — experience.sort_order is the display order · «حفظ الوظيفة» placeholder removed.

1. _migrate_experience_sort_order backfills 0..n-1 per user in the order shown before
   (sort_order ASC, id DESC) — nothing moves — and a second run changes nothing.
2. add_experience → the new row gets the user's last position (after the existing ones).
3. Equal sort_order → secondary order id ASC (stable).
4. PUT /experience/reorder: own ids → saved in that order · another user's id → 403, nothing moved.
5. The save-job button is gone from job-detail.html, the company job cards and tw_strings.json.

Real PostgreSQL: TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db (run_tests.sh sets it)
Run: python -m pytest tests/test_experience_sort_order_49.py -q
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-experience-49-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture
def db():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    for t in ("app_migrations", "experience", "users"):
        c.run(f"DROP TABLE IF EXISTS {t} CASCADE")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp', password_hash TEXT, created_at TIMESTAMPTZ DEFAULT NOW())")
    # the table as production has it before this PR: sort_order DEFAULT 0, never filled
    c.run("CREATE TABLE experience (id SERIAL PRIMARY KEY, "
          "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
          "title TEXT NOT NULL, company TEXT NOT NULL, location TEXT, start_date TEXT, end_date TEXT, "
          "is_current BOOLEAN DEFAULT FALSE, description TEXT, created_at TIMESTAMP DEFAULT NOW(), "
          "sort_order INTEGER DEFAULT 0)")
    auth.release_conn(c)
    auth._migrate_password_changed_at()
    auth._migrate_session_version()
    server._pwd_changed_cache.clear()
    yield


def _user(email):
    return int(_sql("INSERT INTO users (tw_id, email, full_name) VALUES ('U1', :e, 'ن') RETURNING id",
                    e=email)[0][0])


def _exp(uid, title, sort_order=0):
    return int(_sql("INSERT INTO experience (user_id, title, company, sort_order) "
                    "VALUES (:u, :t, 'C', :s) RETURNING id", u=uid, t=title, s=sort_order)[0][0])


def _shown(uid):
    """What the API returns — the profile's experience list, in order."""
    with auth.db_conn() as c:
        return [e["title"] for e in auth._get_extras(c, uid)["experience"]]


def _h(uid):
    return {"Authorization": "Bearer " + server._jwt_encode(
        {"user_id": uid, "user_type": "emp", "tw_id": "U1", "sv": 0})}


def test_backfill_keeps_the_order_shown_before_and_runs_once(db):
    a = _user("a@x.io")
    for t in ("old", "mid", "new"):          # never reordered: all 0 → shown newest first
        _exp(a, t)
    b = _user("b@x.io")
    _exp(b, "second", 1)                     # reordered, then a new one added at 0 (tie)
    _exp(b, "first", 0)
    _exp(b, "added_later", 0)
    before_b = [r[0] for r in _sql("SELECT title FROM experience WHERE user_id = :u "
                                   "ORDER BY sort_order ASC, id DESC", u=b)]

    auth._migrate_experience_sort_order()

    assert _shown(a) == ["new", "mid", "old"]
    assert _shown(b) == before_b == ["added_later", "first", "second"]
    assert [r[0] for r in _sql("SELECT sort_order FROM experience WHERE user_id = :u "
                               "ORDER BY sort_order", u=a)] == [0, 1, 2]
    # a later reorder must survive the next startup (the backfill is one-time)
    _sql("UPDATE experience SET sort_order = 2 - sort_order WHERE user_id = :u", u=a)
    auth._migrate_experience_sort_order()
    assert _shown(a) == ["old", "mid", "new"]
    assert _sql("SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'experience' AND column_name = 'sort_order'")[0][0] == "NO"


def test_new_experience_takes_the_last_position(db):
    auth._migrate_experience_sort_order()
    u = _user("c@x.io")
    first = auth.add_experience(u, {"title": "first", "company": "C"})
    second = auth.add_experience(u, {"title": "second", "company": "C"})
    assert (first["sort_order"], second["sort_order"]) == (0, 1)
    assert _shown(u) == ["first", "second"]
    other = _user("d@x.io")                  # positions are per user
    assert auth.add_experience(other, {"title": "x", "company": "C"})["sort_order"] == 0


def test_equal_sort_order_falls_back_to_id_ascending(db):
    auth._migrate_experience_sort_order()
    u = _user("e@x.io")
    _exp(u, "tie_old", 5)
    _exp(u, "top", 0)
    _exp(u, "tie_new", 5)
    assert _shown(u) == ["top", "tie_old", "tie_new"]


def test_reorder_only_the_users_own_experiences(db):
    auth._migrate_experience_sort_order()
    u, other = _user("f@x.io"), _user("g@x.io")
    e1 = auth.add_experience(u, {"title": "one", "company": "C"})["id"]
    e2 = auth.add_experience(u, {"title": "two", "company": "C"})["id"]
    foreign = auth.add_experience(other, {"title": "theirs", "company": "C"})["id"]

    r = client.put("/experience/reorder", json={"ordered_ids": [e2, e1]}, headers=_h(u))
    assert r.status_code == 200, r.text
    assert _shown(u) == ["two", "one"]

    r = client.put("/experience/reorder", json={"ordered_ids": [foreign, e1]}, headers=_h(u))
    assert r.status_code == 403
    assert _shown(u) == ["two", "one"] and _shown(other) == ["theirs"]
    r = client.put("/experience/reorder", json={"ordered_ids": [e1, e1]}, headers=_h(u))
    assert r.status_code == 403             # duplicates rejected too
    assert client.put("/experience/reorder", json={"ordered_ids": [e1]}).status_code in (401, 403)


def test_save_job_button_is_gone():
    html = open("job-detail.html", encoding="utf-8").read()
    buttons = re.findall(r"<button\b[^>]*>.*?</button>", html, re.S)
    assert not [b for b in buttons if 'data-tw-icon="bookmark"' in b], "save button still on job-detail"
    assert "jd-save-trigger" not in open("static/job/job-detail.js", encoding="utf-8").read()
    for f in ("static/company/company.render.js", "static/company/company.jobs.js",
              "static/company/company.css"):
        assert "vjc-btn--save" not in open(f, encoding="utf-8").read(), f
    strings = json.load(open("tw_strings.json", encoding="utf-8"))
    assert not [k for k in strings["ar"] if k in ("job.save", "job.save_label", "job.save_soon")]
