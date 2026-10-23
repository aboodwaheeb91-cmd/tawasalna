"""Task 5.0e — fixes from the external audit (SYSTEMS_INDEX §1a / §54g / §54m / §60 · ADMIN_ENTITY_MAP §1).

(Item 1 — account delete closed → tests/test_account_security.py · item 8 → tests/test_privacy_boundary_http.py)
2. POST /log/error: own per-IP rate limit (429) · size limits (422) · no JWT / token / email in the log.
3. Swallowed errors: profile view record failure is logged · interest read failure ≠ «not interested» ·
   interest delete failure ≠ success · applicant counts read failure ≠ «0 applicants».
4. Google sign-in = Actions Registry `login_google`, off by default (admin can switch it on).
5. Landing: every not-built feature line carries the «قريباً» badge (twT common.soon).
6. noindex (X-Robots-Tag) on every non-public HTML page · sitemap = public pages only.
7. run_tests.sh refuses a non-test / remote / production database before connecting.

Real PostgreSQL for the profile tests (schema = the real startup migrations):
  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_audit_fixes_50e.py -q
"""
import os
import re
import subprocess
import sys
import uuid
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "test-secret-audit-50e-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server
import tw_actions
from tools import db_guard

client = TestClient(server.app)


@pytest.fixture(autouse=True)
def _fresh_limits():
    server._rate_store.clear()
    server._error_log.clear()
    yield


@pytest.fixture(scope="module")
def schema():
    try:
        auth.release_conn(auth.get_conn())
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    server._run_startup_migrations()


def _register(utype="emp"):
    tag = uuid.uuid4().hex[:10]
    body = {"email": f"a50e_{tag}@example.com", "password": "TwTest@9999", "user_type": utype,
            "terms_accepted": True}
    body.update({"first_name": "رنا", "last_name": "خالد"} if utype == "emp" else {"full_name": "شركة " + tag})
    server._rate_store.clear()
    r = client.post("/auth/register", json=body)
    assert r.status_code == 200, r.text
    return r.json()["user"], {"Authorization": "Bearer " + r.json()["token"]}


# ── 2. POST /log/error ───────────────────────────────────────────────────────

def test_log_error_redacts_tokens_and_emails(capsys):
    jwt = server._jwt_encode({"user_id": 1, "user_type": "emp", "sv": 0})
    r = client.post("/log/error", json={
        "msg": f"boom Bearer {jwt} for rana@example.com", "page": "/settings?token=abc123&x=1",
        "file": f"/static/a.js?jwt={jwt}", "line": 12})
    assert r.status_code == 200 and r.json() == {"ok": True}
    stored = server._error_log[-1]
    printed = capsys.readouterr().out
    for text in (str(stored), printed):
        assert jwt not in text and "rana@example.com" not in text and "abc123" not in text
    assert "[email]" in stored["msg"] and "[token]" in stored["msg"] and stored["line"] == 12
    admin = client.get("/admin/errors")   # still admin-only
    assert admin.status_code in (401, 503)


def test_log_error_size_limits():
    assert client.post("/log/error", json={"msg": "x" * 2001}).status_code == 422
    assert client.post("/log/error", json={"page": "/" + "p" * 600}).status_code == 422
    assert client.post("/log/error", json={"msg": "x" * 2000}).status_code == 200
    assert len(server._error_log) == 1


def test_log_error_rate_limited_on_its_own_bucket():
    codes = [client.post("/log/error", json={"msg": "e"}).status_code for _ in range(server._LOG_ERROR_RATE + 1)]
    assert codes[:-1] == [200] * server._LOG_ERROR_RATE and codes[-1] == 429
    assert len(server._error_log) == server._LOG_ERROR_RATE
    # the auth budget (login / register …) is untouched by error reports
    assert not any(k.startswith("ip:") for k in server._rate_store)


# ── 3. Swallowed errors ──────────────────────────────────────────────────────

def test_applicant_counts_read_failure_returns_none_not_zero(capsys):
    class _Broken:
        def run(self, *a, **kw):
            raise RuntimeError("db down")
    assert auth._fetch_applicant_counts_batch(_Broken(), [1, 2]) is None
    assert "[applicant_counts] read FAILED" in capsys.readouterr().out
    assert auth._fetch_applicant_counts_batch(_Broken(), []) == {}


def test_job_lists_load_with_null_count_when_count_read_fails(schema, capsys):
    co, co_h = _register("co")
    jid = int(_sql("INSERT INTO jobs (company_id, title, status, expires_at) "
                   "VALUES (:c, 'وظيفة', 'active', NOW() + INTERVAL '30 days') RETURNING id", c=co["id"])[0][0])

    def _counts():
        mine = client.get("/company/jobs", headers=co_h)
        public = client.get(f"/jobs?company_id={co['id']}")
        assert mine.status_code == 200 and public.status_code == 200, (mine.text, public.text)
        pick = lambda rows: [j["applicant_count"] for j in rows if j["id"] == jid]
        pub = public.json()   # the visitor company list is {jobs, …}; a plain search is a list
        return pick(mine.json()["jobs"]), pick(pub["jobs"] if isinstance(pub, dict) else pub)

    assert _counts() == ([0], [0])                      # read OK, no applications → a real 0
    _sql("ALTER TABLE job_applications RENAME TO job_applications_off")
    try:
        assert _counts() == ([None], [None])            # read failed → list still loads, count unknown
    finally:
        _sql("ALTER TABLE job_applications_off RENAME TO job_applications")
    assert "[applicant_counts] read FAILED" in capsys.readouterr().out


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def test_profile_view_failure_logged_page_still_served(schema, monkeypatch, capsys):
    target, _ = _register()
    _, viewer = _register()

    def _boom(*a):
        raise RuntimeError("views table down")
    monkeypatch.setattr(server, "record_profile_view", _boom)
    r = client.get(f"/profile/{target['id']}", headers=viewer)
    assert r.status_code == 200 and r.json()["viewer_type"] == "public-user"
    assert "[profile_view] record FAILED" in capsys.readouterr().out


def test_interest_read_failure_is_not_reported_as_not_interested(schema, monkeypatch, capsys):
    target, _ = _register()
    _, viewer = _register()
    ok = client.get(f"/profile/{target['id']}", headers=viewer).json()["viewer_action"]
    assert ok["is_active"] is False and ok["can_interact"] is True and ok["hidden"] is False

    def _boom(*a):
        raise RuntimeError("interests table down")
    monkeypatch.setattr(server, "is_profile_interest_active", _boom)
    va = client.get(f"/profile/{target['id']}", headers=viewer).json()["viewer_action"]
    assert va["is_active"] is None and va["hidden"] is True and va["can_interact"] is False
    assert va["error"] == "interest_unavailable"
    assert "[profile_interest] read FAILED" in capsys.readouterr().out


def test_interest_delete_failure_is_not_success(schema, monkeypatch):
    target, _ = _register()
    _, viewer = _register()
    assert client.post(f"/profile/{target['id']}/interest", headers=viewer).status_code == 200

    class _Broken:
        def run(self, *a, **kw):
            raise RuntimeError("secret detail")
    monkeypatch.setattr(auth, "get_conn", lambda: _Broken())
    monkeypatch.setattr(auth, "release_conn", lambda c: None)
    r = client.delete(f"/profile/{target['id']}/interest", headers=viewer)
    assert r.status_code == 500 and "success" not in r.text and "secret detail" not in r.text
    monkeypatch.undo()
    assert server.is_profile_interest_active(viewer_id(viewer), target["id"]) is True   # nothing was removed
    r = client.delete(f"/profile/{target['id']}/interest", headers=viewer)
    assert r.status_code == 200 and r.json()["viewer_action"]["is_active"] is False
    assert server.is_profile_interest_active(viewer_id(viewer), target["id"]) is False


def viewer_id(headers):
    return int(server._jwt_decode(headers["Authorization"].split(" ", 1)[1])["user_id"])


# ── 4. Google sign-in — Actions Registry, off by default ─────────────────────

class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.by_id, self.soon = {}, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.by_id[a["id"]] = (tag, a)
        if a.get("data-tw-t") == "common.soon":
            self.soon += 1


def _tags(path):
    r = client.get(path)
    assert r.status_code == 200
    p = _Tags()
    p.feed(r.text)
    return r, p


def test_google_signin_off_by_default_switchable_by_admin():
    assert tw_actions.merged({})["login_google"].get("off") is True
    assert not tw_actions.merged({"login_google": {"enabled": True}})["login_google"].get("off")
    assert tw_actions.validate_overrides({"login_google": {"enabled": True}}) == {"login_google": {"enabled": True}}
    _, page = _tags("/login")
    assert "googleBtn" not in page.by_id                    # no static button — twAction renders it
    assert "hidden" in page.by_id["googleSlot"][1]           # slot (with the «أو» divider) hidden


# ── 5. Landing — «قريباً» on not-built features ──────────────────────────────

def test_landing_soon_badges():
    _, page = _tags("/")
    assert page.soon == 4    # smart matching ×2 (who + features) · courses / programs ×2 (who + features)
    import tw_strings
    assert tw_strings.merged({})["common.soon"]


# ── 6. noindex + sitemap ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/login", "/index.html", "/settings", "/messages", "/notifications",
                                  "/home", "/landing.html", "/admin-job", "/admin-view", "/profile"])
def test_private_pages_noindex(path):
    r = client.get(path, follow_redirects=False)
    assert r.headers.get("content-type", "").startswith("text/html"), path
    assert r.headers.get("x-robots-tag") == "noindex, nofollow", path


def test_admin_panel_noindex():
    r = client.get("/tw-ctrl-" + server.ADMIN_URL_TOKEN, follow_redirects=False)
    if r.headers.get("content-type", "").startswith("text/html"):
        assert r.headers.get("x-robots-tag") == "noindex, nofollow"


@pytest.mark.parametrize("path", ["/", "/job-detail"])
def test_public_pages_indexable(path):
    r = client.get(path)
    assert r.status_code == 200 and "x-robots-tag" not in r.headers


def test_public_profile_indexable(schema):
    user, _ = _register()
    r = client.get(f"/u/{user['tw_id']}")
    assert r.status_code == 200 and "x-robots-tag" not in r.headers


def test_sitemap_public_pages_only():
    locs = re.findall(r"<loc>([^<]+)</loc>", client.get("/sitemap.xml").text)
    assert locs == ["https://tawasolna.com/", "https://tawasolna.com/privacy", "https://tawasolna.com/terms"]   # task terms


# ── 7. run_tests.sh DB guard ─────────────────────────────────────────────────

LOCAL = "postgresql://u:p@127.0.0.1:5432/tawasalna_test_pipeline"


def test_db_guard_rules():
    assert db_guard.check(LOCAL, {}) is None
    assert db_guard.check("postgresql://u:p@localhost/x_test", {"APP_ENV": "development"}) is None
    assert "production" in db_guard.check(LOCAL, {"APP_ENV": "production"})
    assert "test" in db_guard.check("postgresql://u:p@127.0.0.1:5432/tawasalna", {})
    assert db_guard.check("postgresql://u:p@db.supabase.co:5432/x_test", {})
    assert db_guard.check("postgresql://u:p@db.supabase.co:5432/x_test", {"TW_TEST_DB_ALLOW_REMOTE": "1"}) is None
    assert db_guard.check("", {}) and db_guard.check("mysql://u@127.0.0.1/x_test", {})


@pytest.mark.parametrize("env", [{"APP_ENV": "production"},
                                 {"TW_TEST_DB_URL": "postgresql://u:p@127.0.0.1:5432/tawasalna"},
                                 {"TW_TEST_DB_URL": "postgresql://u:p@db.example.com:5432/x_test"}])
def test_run_tests_refuses_before_connecting(env):
    full = dict(os.environ, **env)
    if "TW_TEST_DB_URL" not in env:
        full.pop("TW_TEST_DB_URL", None)
    full.pop("TW_TEST_DB_ALLOW_REMOTE", None)
    p = subprocess.run(["bash", os.path.join(ROOT, "run_tests.sh")], env=full, cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "refusing" in p.stdout and "== Syntax ==" not in p.stdout   # stopped before any test / connection
