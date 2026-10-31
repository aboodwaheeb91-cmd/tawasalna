"""Task 8.4c-2b-1 — the staff link pages (docs/rules/admin-staff.md rule 15 · SYSTEMS_INDEX §25h).

Real FastAPI app, no DB (the POST flows are covered by tests/test_admin_staff_84c2a2.py — not repeated here).
  A. GET /staff/invite · /staff/mfa-reset · /staff/password-reset → 200 HTML without any token
  B. their replies carry Cache-Control: no-store + Referrer-Policy: no-referrer
  C. the served HTML holds no panel path (ADMIN_URL_TOKEN), no "t=" and no secret of the environment
  D. the three routes are in admin_perms.UNGUARDED_ROUTES as "HTML shell only" and never call check_admin
     (the walker of rule 2 — tests/test_admin_perms_84a.py — covers them too)
Run: python -m pytest tests/test_admin_staff_84c2b1.py -q
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-" + "s" * 32)
os.environ.setdefault("ADMIN_URL_TOKEN", "panelslug7k2q")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import admin_perms
import server as srv

client = TestClient(srv.app)
PAGES = {"/staff/invite": "staff_invite_page", "/staff/mfa-reset": "staff_mfa_reset_page",
         "/staff/password-reset": "staff_password_reset_page"}


@pytest.mark.parametrize("path", sorted(PAGES))
def test_page_served_without_token(path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers.get("cache-control") == "no-store"
    assert r.headers.get("referrer-policy") == "no-referrer"
    html = r.text
    assert "staff-link.js" in r.text and "admin-otp-ui.js" in html and "qrcode.min.js" in html   # the page loads its scripts
    assert srv.ADMIN_URL_TOKEN and srv.ADMIN_URL_TOKEN not in html and "tw-ctrl" not in html                          # no panel path
    assert not re.search(r"[#?&]t=", html)                                                    # no token / token template
    for secret in ("JWT_SECRET", "ADMIN_TOKEN", "ADMIN_JWT_SECRET", "ADMIN_MFA_KEY", "RESEND_API_KEY"):
        val = os.environ.get(secret)
        if val:
            assert val not in html, secret


def test_query_or_fragment_token_never_reflected():
    r = client.get("/staff/invite?t=SHOULD_NOT_APPEAR_abcdefghijklmnop")
    assert r.status_code == 200 and "SHOULD_NOT_APPEAR" not in r.text


def test_routes_are_unguarded_html_shells(monkeypatch):
    calls = []

    def rec(request, *a, **kw):
        calls.append(a[0] if a else kw.get("perm"))
        raise HTTPException(418, "recorded")
    monkeypatch.setattr(srv, "check_admin", rec)
    by_path = {r.path: r for r in srv.app.routes if getattr(r, "path", "") in PAGES}
    assert set(by_path) == set(PAGES)
    for path, name in PAGES.items():
        route = by_path[path]
        assert route.name == name
        assert route.methods <= {"GET", "HEAD"} and route.response_class is srv.HTMLResponse
        assert admin_perms.UNGUARDED_ROUTES.get(name, "").startswith("HTML shell only")
        assert path in srv.PUBLIC_RATE_EXEMPT
        assert client.get(path).status_code == 200
    assert calls == []
