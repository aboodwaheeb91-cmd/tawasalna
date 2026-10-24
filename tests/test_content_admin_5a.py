"""
test_content_admin_5a.py — phase 5a: content screens backend (SYSTEMS_INDEX §25h).

content.edit on /admin/strings · /admin/theme/colors · /admin/news: no / bad token → 401 · admin token
without the permission → 403 (same as settings.edit) · owner → 200 · every write = one admin_audit_log row
(action · target = key / token / news id · actor · status) without the text / color / news content.
Colors: only --color-brand-primary / --color-brand-accent, #RRGGBB only (else 400) · applied in /theme.css ·
an older stored override of another token kept + still served.
News: ends_at ≤ starts_at → 400 · /home/feed shows active only · GET /news/banner (guest): newest active or
null · drafts hidden · javascript: link → null.

Real PostgreSQL, in-process client. TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_content_admin_5a.py -q
"""
import json
import re, os, sys, uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import admin_insights
import theme_tokens
import tw_strings
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-5a-" + "a" * 32
PRIMARY, ACCENT = theme_tokens.EDITABLE


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    srv._rate_store.clear()
    yield
    srv._strings_set_overrides({})
    srv.set_site_setting(theme_tokens.THEME_SETTING_KEY, "{}")
    srv._theme_css_cache["css"] = None


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
    srv.ensure_site_settings_table()
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _owner():
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _staff():   # valid admin token without content.edit
    return {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:5a", perms=["settings.edit"])}


def _editor():  # admin token holding content.edit only
    return {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:ed", perms=[srv.CONTENT_PERM])}


def _audit(action):
    rows = _sql("SELECT actor, target, status, old_value, new_value FROM admin_audit_log "
                "WHERE action = :a ORDER BY id DESC LIMIT 1", a=action)
    return rows[0] if rows else None


def _user():
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id",
                   t="U" + n, n="User" + n, e=n + "@t.test")[0]
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": int(uid), "user_type": "emp", "tw_id": tw})}


def _news(status="published", starts=None, ends=None, url="https://example.com/n", title=None):
    title = title or "خبر " + uuid.uuid4().hex[:6]
    return int(_sql("INSERT INTO news_posts (title, summary, body, source_url, status, starts_at, ends_at) "
                    "VALUES (:t, 'ملخص', 'نص داخلي', :u, :s, :st, :en) RETURNING id",
                    t=title, u=url, s=status, st=starts, en=ends)[0][0])


NOW = datetime.now(timezone.utc)
KEY = sorted(tw_strings.DEFAULTS[tw_strings.DEFAULT_LANG])[0]
WRITES = (
    ("put", "/admin/strings", {"overrides": {}}),
    ("put", "/admin/theme/colors", {"overrides": {}}),
    ("post", "/admin/news", {"title": "x"}),
    ("put", "/admin/news/999999999", {"title": "x"}),
    ("delete", "/admin/news/999999999", None),
)
READS = ("/admin/strings", "/admin/theme/colors", "/admin/news")


# ── content.edit gate ──
def test_gate_401_403_200():
    for method, url, body in WRITES + tuple(("get", u, None) for u in READS):
        kw = {"json": body} if body is not None else {}
        assert getattr(client, method)(url, **kw).status_code == 401, url
        assert getattr(client, method)(url, headers={"X-Admin-Token": "bad"}, **kw).status_code == 401, url
        assert getattr(client, method)(url, headers=_staff(), **kw).status_code == 403, url
    for url in READS:
        assert client.get(url, headers=_editor()).status_code == 200, url


def test_writes_audited_without_content():
    text = "نص سري للتجربة"
    r = client.put("/admin/strings", headers=_editor(), json={"overrides": {KEY: text}})
    assert r.status_code == 200, r.text
    a = _audit("admin_put_strings")
    assert a[:3] == ["staff:ed", "keys=" + KEY, 200] and a[3] is None and a[4] is None

    r = client.put("/admin/theme/colors", headers=_owner(), json={"overrides": {PRIMARY: "#123abc"}})
    assert r.status_code == 200, r.text
    a = _audit("admin_theme_colors_put")
    assert a[:3] == ["owner", "tokens=" + PRIMARY, 200] and a[3] is None and a[4] is None

    r = client.post("/admin/news", headers=_owner(), json={"title": "عنوان سري", "summary": text})
    assert r.status_code == 200, r.text
    nid = r.json()["id"]
    assert _audit("admin_create_news")[:3] == ["owner", f"news_id={nid}", 200]
    assert client.put(f"/admin/news/{nid}", headers=_owner(), json={"title": "y"}).status_code == 200
    assert _audit("admin_update_news")[:3] == ["owner", f"news_id={nid}", 200]
    assert client.delete(f"/admin/news/{nid}", headers=_owner()).status_code == 200
    assert _audit("admin_delete_news")[:3] == ["owner", f"news_id={nid}", 200]

    client.put("/admin/strings", headers=_staff(), json={"overrides": {KEY: text}})
    assert _audit("admin_put_strings")[:3] == ["staff:5a", None, 403]   # refused, still recorded
    dump = json.dumps(_sql("SELECT * FROM admin_audit_log"), default=str, ensure_ascii=False)
    assert text not in dump and "#123abc" not in dump and "عنوان سري" not in dump


# ── colors ──
def test_colors_get_defaults_5b():
    """phase 5b: GET returns the tw_shared.css default (#rrggbb) of every EDITABLE token for the screen."""
    d = client.get("/admin/theme/colors", headers=_owner()).json()["data"]
    assert set(d["defaults"]) == set(d["tokens"]) == set(theme_tokens.EDITABLE)
    assert all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in d["defaults"].values()), d["defaults"]


def test_colors_narrowed_and_applied():
    for body in ({"--color-text-primary": "#123456"}, {PRIMARY: "#12345"}, {PRIMARY: "#1234567"},
                 {PRIMARY: "red"}, {ACCENT: "rgb(1,2,3)"}, {PRIMARY: 123}, {PRIMARY: "#abc"}):
        r = client.put("/admin/theme/colors", headers=_owner(), json={"overrides": body})
        assert r.status_code == 400, (body, r.text)
    # an older stored override of another token: kept on save + still served
    srv.set_site_setting(theme_tokens.THEME_SETTING_KEY, json.dumps({"--color-text-primary": "#010203"}))
    r = client.put("/admin/theme/colors", headers=_owner(),
                   json={"overrides": {PRIMARY: "#AA0011", ACCENT: "#00bb22"}})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["overrides"] == {"--color-text-primary": "#010203",
                                             PRIMARY: "#aa0011", ACCENT: "#00bb22"}
    css = client.get("/theme.css").text
    assert f"{PRIMARY}: #aa0011;" in css and f"{ACCENT}: #00bb22;" in css
    assert "--color-text-primary: #010203;" in css


# ── news ──
def test_news_window_validation():
    s = NOW.isoformat()
    for ends in (s, (NOW - timedelta(hours=1)).isoformat()):
        r = client.post("/admin/news", headers=_owner(), json={"title": "x", "starts_at": s, "ends_at": ends})
        assert r.status_code == 400, r.text
    r = client.post("/admin/news", headers=_owner(), json={
        "title": "x", "starts_at": s, "ends_at": (NOW + timedelta(days=1)).isoformat()})
    assert r.status_code == 200, r.text
    nid = r.json()["id"]
    assert client.put(f"/admin/news/{nid}", headers=_owner(),
                      json={"title": "x", "starts_at": s, "ends_at": s}).status_code == 400
    item = next(n for n in client.get("/admin/news", headers=_owner()).json()["news"] if n["id"] == nid)
    assert item["starts_at"] and item["ends_at"]


def test_feed_and_banner_active_only():
    _sql("UPDATE news_posts SET status = 'archived'")
    h = _user()
    assert client.get("/news/banner").json() == {"ok": True, "data": None}
    future = _news(starts=NOW + timedelta(days=1))
    expired = _news(starts=NOW - timedelta(days=2), ends=NOW - timedelta(days=1))
    draft = _news(status="draft")
    assert client.get("/news/banner").json()["data"] is None
    active = _news(starts=NOW - timedelta(hours=1), ends=NOW + timedelta(hours=1))
    ids = {i["id"] for i in client.get("/home/feed?filter=news&limit=50", headers=h).json()["items"]}
    assert active in ids and not ids & {future, expired, draft}

    b = client.get("/news/banner").json()["data"]
    assert set(b) == {"id", "title", "summary", "source_url"}
    assert b["id"] == active and b["source_url"] == "https://example.com/n"
    newest = _news(url="javascript:alert(1)")
    b = client.get("/news/banner").json()["data"]
    assert b["id"] == newest and b["source_url"] is None
    _sql("UPDATE news_posts SET status = 'draft' WHERE id = :i", i=newest)
    assert client.get("/news/banner").json()["data"]["id"] == active
    # phase 5b: the admin list carries active_now (NEWS_ACTIVE_SQL) + body for the edit form
    rows = {n["id"]: n for n in client.get("/admin/news", headers=_owner()).json()["news"]}
    assert rows[active]["active_now"] is True and rows[active]["body"] == "نص داخلي"
    assert not any(rows[i]["active_now"] for i in (future, expired, draft, newest))
