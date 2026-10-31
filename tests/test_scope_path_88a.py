"""Task 8.8a — path decisions read scope["path"] (_req_path), never request.url.path
(GHSA-86qp-5c8j-p5mr / CVE-2026-48710 · docs/rules/dev-guidelines.md).

On starlette 0.50.0 request.url is rebuilt from the Host header: Host "a#" → request.url.path == "" while
routing still uses scope["path"]. The first test pins that poisoning (if it stops reproducing, the behavioural
tests below no longer prove anything — they must fail on the old code and pass on the new one).

Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with
TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py), every request with the bad Host:
  A. an owner admin write (PUT /admin/settings/{normal key}) → a row in admin_audit_log.
  B. a failed admin login → an admin_login row.
  C. a path in _RATE_LIMITED_PATHS → 429 after the limit.
  D. a public /staff/* route → recorded.
  E. guard: no request.url.path / request.url.hostname in server.py code.
Run: python -m pytest tests/test_scope_path_88a.py -q
"""
import io, os, sys, tokenize

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import server as srv
import tw_settings
from test_admin_mfa_84b import _sql
from test_admin_perms_84a import _NORMAL_KEY
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    LOGIN, _enroll_owner, _env, _migrated, client, db)

BAD_HOST = {"host": "a#"}


def _audit(action):
    return _sql("SELECT actor, status FROM admin_audit_log WHERE action = :a", a=action)


def test_bad_host_poisons_request_url_path():
    async def h(request):
        return JSONResponse({"url": request.url.path, "scope": request.scope["path"]})
    c = TestClient(Starlette(routes=[Route("/auth/login", h)]))
    assert c.get("/auth/login", headers=BAD_HOST).json() == {"url": "", "scope": "/auth/login"}


# ── A. admin write audited ──
def test_admin_write_audited_with_bad_host(db, _env):
    owner = _enroll_owner(_env)
    value = tw_settings.item(_NORMAL_KEY)["default"]
    r = client.put(f"/admin/settings/{_NORMAL_KEY}", json={"value": value},
                   headers={"X-Admin-Token": owner["token"], **BAD_HOST})
    assert r.status_code == 200, r.text
    assert _audit("admin_settings_update") == [["owner", 200]]


# ── B. failed admin login audited ──
def test_failed_admin_login_audited_with_bad_host(db):
    r = client.post(LOGIN, json={"password": "wrong-password-88a"}, headers=BAD_HOST)
    assert r.status_code == 401, r.text
    assert [row[1] for row in _audit("admin_login")] == [401]


# ── C. per-IP path limit ──
def test_rate_limited_path_with_bad_host(monkeypatch):
    monkeypatch.setattr(srv, "_RATE_LIMIT", 3)
    codes = [client.post("/auth/login", json={}, headers=BAD_HOST).status_code for _ in range(4)]
    assert 429 not in codes[:3] and codes[3] == 429, codes


# ── D. public /staff/* audited ──
def test_staff_public_route_audited_with_bad_host(db):
    r = client.post("/staff/invite/start", json={"token": "x" * 43}, headers=BAD_HOST)
    assert r.status_code >= 400, r.text
    assert [row[0] for row in _audit("staff_invite_start")] == ["-"]


# ── E. guard (in addition to the behaviour above) ──
def test_no_request_url_path_in_server_code():
    with open(os.path.join(os.path.dirname(_HERE), "server.py"), encoding="utf-8") as f:
        src = f.read()
    code = [t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type not in (tokenize.COMMENT, tokenize.STRING)]
    joined = "".join(code)
    for bad in ("request.url.path", "request.url.hostname"):
        assert bad not in joined, bad
