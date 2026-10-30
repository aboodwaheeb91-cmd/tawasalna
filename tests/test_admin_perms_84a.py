"""Task 8.4a — a permission for every admin route (docs/rules/admin-staff.md · SYSTEMS_INDEX §25h).

Real FastAPI app, no DB.
  A. Route coverage (registration, not source text): every app route under /admin/, the panel path
     (/tw-ctrl-<slug>…) and /admin-view · /admin-job is called once with check_admin swapped for a recorder.
     Each one must either be in admin_perms.UNGUARDED_ROUTES (HTML shell / login / public logo) or call
     check_admin first with exactly the perm of ROUTE_PERMS below (always a perm of admin_perms.ALL).
     A new admin route without a perm → no recorded call → fails. A changed perm → fails.
  B. Real check_admin with issued tokens: in scope 200 · out of scope 403 · an owner-only perm listed
     explicitly → 403 · "*" → everything as before · unknown / missing perm = programming error.
Run: python -m pytest tests/test_admin_perms_84a.py -q
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import admin_perms
import server as srv
import tw_settings

client = TestClient(srv.app)
PANEL = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN

# (method, route path) → perm — the table of docs/rules/admin-staff.md
ROUTE_PERMS = {
    ("GET", "/admin/users"): "users.view",
    ("GET", "/admin/profile/{user_id}"): "users.view",
    ("PUT", "/admin/profile/{user_id}"): "users.edit",
    ("DELETE", "/admin/experience/{exp_id}"): "users.edit",
    ("DELETE", "/admin/education/{edu_id}"): "users.edit",
    ("DELETE", "/admin/course/{course_id}"): "users.edit",
    ("PUT", "/admin/user/{user_id}/suspension"): "users.suspend",
    ("GET", "/admin/kyc"): "kyc.review",
    ("PUT", "/admin/kyc/{user_id}/approve"): "kyc.review",
    ("PUT", "/admin/kyc/{user_id}/reject"): "kyc.review",
    ("GET", "/admin/kyc/{submission_id}/docs"): "kyc.review",
    ("PUT", "/admin/user/{user_id}/verify"): "kyc.review",
    ("GET", "/admin/jobs"): "jobs.manage",
    ("GET", "/admin/jobs/{job_id}"): "jobs.manage",
    ("PUT", "/admin/jobs/{job_id}"): "jobs.manage",
    ("DELETE", "/admin/jobs/{job_id}"): "jobs.manage",
    ("GET", "/admin/jobs/{job_id}/delete-preview"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/hide"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/unhide"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/reactivate"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/extend"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/status"): "jobs.manage",
    ("POST", "/admin/jobs/{job_id}/unarchive"): "jobs.manage",
    ("GET", "/admin/reports"): "reports.manage",
    ("PUT", "/admin/reports/{report_id}/resolve"): "reports.manage",
    ("GET", "/admin/strings"): "content.edit",
    ("PUT", "/admin/strings"): "content.edit",
    ("GET", "/admin/theme/colors"): "content.edit",
    ("PUT", "/admin/theme/colors"): "content.edit",
    ("GET", "/admin/news"): "content.edit",
    ("POST", "/admin/news"): "content.edit",
    ("PUT", "/admin/news/{news_id}"): "content.edit",
    ("DELETE", "/admin/news/{news_id}"): "content.edit",
    ("POST", "/admin/logo"): "content.edit",
    ("GET", "/admin/support/tickets"): "support.manage",
    ("GET", "/admin/support/counts"): "support.manage",
    ("GET", "/admin/support/tickets/{public_id}"): "support.manage",
    ("POST", "/admin/support/tickets/{public_id}/messages"): "support.manage",
    ("PUT", "/admin/support/tickets/{public_id}"): "support.manage",
    ("GET", "/admin/settings"): "settings.edit",
    ("PUT", "/admin/settings/{key}"): "settings.edit",            # a security key → settings.security (test below)
    ("POST", "/admin/settings/{key}/reset"): "settings.edit",
    ("GET", "/admin/actions"): "settings.edit",
    ("PUT", "/admin/actions"): "settings.edit",
    ("GET", "/admin/email"): "settings.edit",
    ("POST", "/admin/email/test"): "settings.edit",
    ("GET", "/admin/stats/summary"): "stats.view",
    ("GET", "/admin/stats/timeseries"): "stats.view",
    ("GET", "/admin/activity"): "stats.view",
    ("POST", "/admin/message"): "message.send",
    # owner only
    ("DELETE", "/admin/user/{user_id}"): "users.delete",
    ("PUT", "/admin/user/{user_id}/type"): "users.type",
    ("PUT", "/admin/user/{user_id}/password"): "users.password",
    ("PUT", "/admin/user/{user_id}/email"): "users.email",
    ("GET", "/admin/users/export"): "users.export",
    ("GET", "/admin/audit"): "audit.view",
    ("PUT", "/admin/email"): "settings.security",               # site_url / from_address = reset / verify link source
    ("GET", "/admin/errors"): "system.manage",
    ("POST", "/admin/maintenance/migrate-data-images"): "system.manage",
    ("POST", "/admin/pipeline/backfill"): "system.manage",
    ("GET", "/admin/pipeline/backfill/dry-run"): "system.manage",
    ("POST", "/admin/pipeline/migrate-index"): "system.manage",
    ("POST", "/admin/owner/recovery-codes"): "settings.security",   # task 8.4c-1 — new owner recovery codes
}
# bodies validated by a model before the endpoint runs (else 422 before check_admin)
_BODIES = {"/admin/logo": {"data_url": "x"}, "/admin/message": {"user_id": 1, "subject": "s", "message": "m"},
           "/admin/news": {"title": "t"}, "/admin/news/{news_id}": {"title": "t"}}
_NORMAL_KEY = next(k for k in tw_settings.REGISTRY if not tw_settings.is_security(k))
_SECURITY_KEY = next(iter(tw_settings.SECURITY_KEYS))


def _admin_area(path: str) -> bool:
    return (path.startswith("/admin/") or path == PANEL or path.startswith(PANEL + "/")
            or path.split(".")[0] in ("/admin-view", "/admin-job"))


def _url(path: str, key: str = _NORMAL_KEY) -> str:
    vals = {"public_id": "HABCDEFGHIJ", "key": key}
    return re.sub(r"\{(\w+)[^}]*\}", lambda m: vals.get(m.group(1), "1"), path)


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    def rec(request, *a, **kw):
        calls.append(a[0] if a else kw.get("perm"))
        raise HTTPException(418, "recorded")
    monkeypatch.setattr(srv, "check_admin", rec)
    srv._rate_store.clear()
    return calls


def _hit(calls, method, path, key=_NORMAL_KEY):
    calls.clear()
    r = client.request(method, _url(path, key), json=_BODIES.get(path, {}))
    return r.status_code, list(calls)


# ── A. every admin route → check_admin with a catalog perm ──
def test_every_admin_route_calls_check_admin_with_its_perm(recorder):
    seen, problems = set(), []
    for route in srv.app.routes:
        path = getattr(route, "path", "")
        if not _admin_area(path):
            continue
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            status, calls = _hit(recorder, method, path)
            if route.name in admin_perms.UNGUARDED_ROUTES:
                if calls:
                    problems.append(f"{method} {path}: listed as unguarded but calls check_admin")
                continue
            seen.add((method, path))
            if status != 418 or len(calls) != 1:
                problems.append(f"{method} {path}: no check_admin(perm) first (status {status}, calls {calls})")
            elif calls[0] not in admin_perms.ALL:
                problems.append(f"{method} {path}: perm {calls[0]!r} not in admin_perms")
            elif ROUTE_PERMS.get((method, path)) != calls[0]:
                problems.append(f"{method} {path}: perm {calls[0]!r} ≠ table {ROUTE_PERMS.get((method, path))!r}")
    assert not problems, "\n".join(problems)
    assert set(ROUTE_PERMS) == seen, set(ROUTE_PERMS) ^ seen   # the table has no stale row


def test_unguarded_routes_are_known_html_or_login_or_public_logo():
    by_name = {r.name: r for r in srv.app.routes if _admin_area(getattr(r, "path", ""))}
    assert set(admin_perms.UNGUARDED_ROUTES) <= set(by_name)    # no stale exemption
    for name in admin_perms.UNGUARDED_ROUTES:
        r = by_name[name]
        if name == "admin_login":
            assert r.methods == {"POST"} and r.path == PANEL + "/login"
        elif name == "get_logos":
            assert r.methods == {"GET"} and r.path == "/admin/logo"
        elif name in ("admin_me", "admin_step_up"):   # task 8.4c-1 — session-only (check_admin_session)
            assert "check_admin_session" in admin_perms.UNGUARDED_ROUTES[name]
            # no admin session → no data (401; 503 when another module left ADMIN_JWT_SECRET unset)
            assert client.request(next(iter(r.methods)), r.path, json={}).status_code in (401, 503)
        else:   # page shell: GET HTML, no data
            assert r.methods <= {"GET", "HEAD"} and r.response_class is srv.HTMLResponse, name


def test_security_setting_needs_settings_security(recorder):
    assert _hit(recorder, "PUT", "/admin/settings/{key}", _SECURITY_KEY)[1] == ["settings.security"]
    assert _hit(recorder, "POST", "/admin/settings/{key}/reset", _SECURITY_KEY)[1] == ["settings.security"]
    assert _hit(recorder, "PUT", "/admin/settings/{key}", _NORMAL_KEY)[1] == ["settings.edit"]


def test_catalog_groups():
    assert not set(admin_perms.GRANTABLE) & set(admin_perms.OWNER_ONLY)
    for p in ("users.delete", "users.type", "users.password", "users.email", "users.export",
              "settings.security", "audit.view", "staff.manage"):
        assert p in admin_perms.OWNER_ONLY
    assert tw_settings.PERM in admin_perms.GRANTABLE and tw_settings.SECURITY_PERM in admin_perms.OWNER_ONLY
    assert srv.CONTENT_PERM in admin_perms.GRANTABLE and srv.SUPPORT_PERM in admin_perms.GRANTABLE


# ── B. real check_admin with issued tokens ──
@pytest.fixture
def real(monkeypatch):
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)
    monkeypatch.setattr(srv, "ADMIN_TOKEN", "a" * 40)
    monkeypatch.setattr(srv.admin_staff, "owner_session_version", lambda: 1)   # task 8.4b — owner sv lives in the DB (1 = never reset)
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield
    tw_settings._set_overrides({})


def _h(perms):
    return {"X-Admin-Token": srv._admin_jwt_issue(perms=perms)}


def _h_stepup():
    """The owner token + a step-up grant for it (task 8.4c-1 — owner-only writes need it, else 428)."""
    tok = srv._admin_jwt_issue()
    return {"X-Admin-Token": tok, "X-Admin-Stepup": srv._admin_step_up_issue("owner", 1, tok)}


def test_in_scope_200_out_of_scope_403(real):
    h = _h(["settings.edit"])
    assert client.get("/admin/settings", headers=h).status_code == 200
    assert client.get("/admin/actions", headers=h).status_code == 200
    assert client.get("/admin/strings", headers=h).status_code == 403          # content.edit
    assert client.get("/admin/stats/summary", headers=h).status_code == 403    # stats.view
    assert client.get("/admin/users", headers=h).status_code == 403            # users.view
    # normal key passes the gate (bad value → 422) · security key → 403
    assert client.put(f"/admin/settings/{_NORMAL_KEY}", json={"value": "x"}, headers=h).status_code == 422
    assert client.put(f"/admin/settings/{_SECURITY_KEY}", json={"value": "x"}, headers=h).status_code == 403
    assert client.get("/admin/settings", headers=_h([])).status_code == 403


def test_owner_only_perm_in_token_still_403(real):
    for perms, method, url in ((["audit.view"], "GET", "/admin/audit"),
                               (["users.export"], "GET", "/admin/users/export"),
                               (["system.manage"], "GET", "/admin/errors"),
                               (["users.delete"], "DELETE", "/admin/user/1"),
                               (["users.type"], "PUT", "/admin/user/1/type"),
                               (["users.password"], "PUT", "/admin/user/1/password"),
                               (["users.email"], "PUT", "/admin/user/1/email"),
                               (["settings.edit", "settings.security"], "PUT", f"/admin/settings/{_SECURITY_KEY}")):
        r = client.request(method, url, json={"value": "x"}, headers=_h(perms))
        assert r.status_code == 403, (perms, url, r.status_code)


def test_email_settings_write_is_owner_only(real):
    """PUT /admin/email changes site_url — the base of every password-reset / verify link → settings.security."""
    staff = _h(["settings.edit"])
    assert client.get("/admin/email", headers=staff).status_code == 200
    assert client.put("/admin/email", json={"site_url": "https://evil.example"}, headers=staff).status_code == 403
    assert client.post("/admin/email/test", json={"to": "bad"}, headers=staff).status_code == 422   # passes the gate
    assert client.put("/admin/email", json={"site_url": "x"}, headers=_h(["settings.edit", "settings.security"])).status_code == 403
    assert client.put("/admin/email", json={"site_url": "javascript:x"}, headers=_h(None)).status_code == 428   # owner without step-up
    r = client.put("/admin/email", json={"site_url": "javascript:x"}, headers=_h_stepup())   # owner + step-up: gate passed, validation as before
    assert r.status_code == 422 and r.json()["error"]["field"] == "site_url"


def test_owner_star_unchanged(real):
    h = _h(None)   # default = ["*"] (the owner login)
    assert client.get("/admin/errors", headers=h).status_code == 200
    assert client.get("/admin/settings", headers=h).status_code == 200
    assert client.put(f"/admin/settings/{_SECURITY_KEY}", json={"value": "x"}, headers=h).status_code == 428
    assert client.put(f"/admin/settings/{_SECURITY_KEY}", json={"value": "x"}, headers=_h_stepup()).status_code == 422
    assert client.get("/admin/settings").status_code == 401
    # the owner token (issued after both login steps — tests/test_admin_mfa_84b.py) carries "*"
    assert srv._admin_jwt_claims(srv._admin_jwt_issue())["perms"] == ["*"]


def test_unknown_or_missing_perm_is_a_programming_error(real):
    req = MagicMock()
    req.headers.get = lambda k, d="": srv._admin_jwt_issue() if k == "X-Admin-Token" else d
    with pytest.raises(RuntimeError):
        srv.check_admin(req, "users.everything")
    with pytest.raises(RuntimeError):
        srv.check_admin(req, None)
    with pytest.raises(TypeError):
        srv.check_admin(req)
    assert srv.check_admin(req, "audit.view")["perms"] == ["*"]
