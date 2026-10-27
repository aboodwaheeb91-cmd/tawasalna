"""Task 7.7 — www.tawasolna.com → tawasolna.com (ARCHITECTURE §34 → Canonical host).

Behaviour, no DB: the redirect runs before every other middleware, so no endpoint body runs.
  1  GET www + path + query → 301 · Location = https://tawasolna.com + same path + query
  2  POST www → 308 (method + body kept) · HEAD → 301
  3  Host is case-insensitive and the port is ignored
  4  primary / other Host → no redirect · X-Forwarded-Host: www on another Host → no redirect
  5  // or /\\ paths stay on https://tawasolna.com
  6  runs before the rate limits (auth login on www never reaches 429)
  7  WebSocket scope on www passes through untouched

Run: python -m pytest tests/test_www_redirect_77.py -q
"""
import asyncio
import os
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-www-redirect-77-" + "x" * 32)

from fastapi.testclient import TestClient

import server as srv

client = TestClient(srv.app)   # no `with` → no startup migrations (no DB needed)
WWW = {"host": "www.tawasolna.com"}


def test_get_www_301_keeps_path_and_query():
    r = client.get("/u/U123?ref=qr&x=1", headers=WWW, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://tawasolna.com/u/U123?ref=qr&x=1"


def test_get_www_root_no_query():
    r = client.get("/", headers=WWW, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://tawasolna.com/"


def test_post_www_308_head_301():
    r = client.post("/auth/login", headers=WWW, json={"a": 1}, follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"] == "https://tawasolna.com/auth/login"
    assert client.head("/x", headers=WWW, follow_redirects=False).status_code == 301


def test_host_case_and_port():
    r = client.get("/jobs?q=a", headers={"host": "WWW.Tawasolna.com:443"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://tawasolna.com/jobs?q=a"


def test_other_hosts_untouched():
    for host in ("tawasolna.com", "tawasalna-production.up.railway.app", "localhost:8000", "testserver"):
        r = client.get("/robots.txt", headers={"host": host}, follow_redirects=False)
        assert r.status_code not in (301, 308), host
        assert "tawasolna.com/robots" not in r.headers.get("location", "")


def test_forwarded_host_ignored():
    r = client.get("/robots.txt", headers={"host": "evil.example", "x-forwarded-host": "www.tawasolna.com"},
                   follow_redirects=False)
    assert r.status_code not in (301, 308)


def test_odd_paths_stay_on_primary_host():
    for path in ("//evil.com", "/\\evil.com", "//evil.com/a?b=c"):
        r = client.get(path, headers=WWW, follow_redirects=False)
        assert r.status_code == 301, path
        loc = r.headers["location"]
        assert loc.startswith("https://tawasolna.com/"), loc
        assert urlsplit(loc).hostname == "tawasolna.com", loc


def test_runs_before_rate_limit():
    srv._rate_store.clear()
    try:
        for _ in range(srv._RATE_LIMIT + 5):
            r = client.post("/auth/login", headers=WWW, json={}, follow_redirects=False)
            assert r.status_code == 308
    finally:
        srv._rate_store.clear()


def test_websocket_on_www_passes_through():
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    mw = srv.CanonicalHostMiddleware(inner)
    scope = {"type": "websocket", "path": "/ws/1", "raw_path": b"/ws/1", "query_string": b"",
             "headers": [(b"host", b"www.tawasolna.com")]}
    asyncio.run(mw(scope, None, None))
    assert seen == ["websocket"]
