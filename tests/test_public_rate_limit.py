"""Task 6 — Public Rate Limit (SYSTEMS_INDEX §54o · ARCHITECTURE.md §80).

Behaviour + structure, no DB (the limit runs before any endpoint body; the one allowed call uses a
route served from its in-memory cache):
  1  over the limit → 429 + Retry-After (seconds until a hit leaves the window) — API → {ok:false, error}
  2  HTML route over the limit → 429 small HTML page (twT text) + Retry-After
  3  a public route counts in public_ip:{ip} · exempt routes never count
  4  _RATE_LIMITED_PATHS bucket (ip:) + log-error bucket untouched and still separate
  5  IP = get_client_ip only (X-Real-IP on Railway; a forged X-Forwarded-For changes nothing)
  6  tw_settings: public_ip_hits 60–2000 · public_ip_window_s 10–600 · security · sec_public · applied at once
  7  structure: every route that works for a guest has _public_rate or a PUBLIC_RATE_EXEMPT reason

Run: python -m pytest tests/test_public_rate_limit.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-public-rate-6-" + "x" * 32)

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server as srv
import tw_settings

client = TestClient(srv.app)   # no `with` → no startup migrations (no DB needed)
IP = "testclient"              # TestClient peer; get_client_ip falls back to it without X-Real-IP


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("CLIENT_IP_SOURCE", "x_real_ip")
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield
    srv._rate_store.clear()
    tw_settings._set_overrides({})


def _fill(key, n, age):
    """n hits, `age` seconds ago."""
    t = time.time() - age
    srv._rate_store[key] = [t] * n


def _hits(key):
    return len(srv._rate_store.get(key, ()))


# ── 1 + 2 ──
def test_api_over_limit_429_retry_after():
    hits, window = tw_settings.rate("public_ip")
    _fill("public_ip:" + IP, hits, 20)
    r = client.get("/jobs")
    assert r.status_code == 429
    assert window - 21 <= int(r.headers["Retry-After"]) <= window - 19
    body = r.json()
    assert body["ok"] is False and body["error"]["code"] == "rate_limited"
    assert body["error"]["message"] == srv._tw_text("limits.rate_limited")
    assert _hits("public_ip:" + IP) == hits      # a refused request is not counted


def test_html_over_limit_429_page():
    hits, _ = tw_settings.rate("public_ip")
    _fill("public_ip:" + IP, hits, 5)
    for path in ("/u/U12345678", "/company-profile?id=7"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 429, path
        assert r.headers["content-type"].startswith("text/html")
        assert int(r.headers["Retry-After"]) >= 1
        assert srv._tw_text("limits.rate_limited") in r.text


def test_retry_after_when_admin_lowers_the_limit():
    # 100 hits in the window, limit 60 → wait until 41 hits are out (the 41st oldest leaves)
    now = time.time()
    srv._rate_store["public_ip:x"] = [now - 50 + i * 0.1 for i in range(100)]
    retry = srv._rate_hit_retry("public_ip:x", 60, 60)
    assert 13 <= retry <= 15   # 41st oldest hit = now − 46 s → leaves the 60 s window in ≈ 14 s


# ── 3 ──
def test_public_route_counted_exempt_not(monkeypatch):
    monkeypatch.setattr(srv, "_skill_catalog_cache", {"skills": []})
    monkeypatch.setattr(srv, "_skill_catalog_cache_ts", time.time())
    assert client.get("/skills/catalog").status_code == 200
    assert _hits("public_ip:" + IP) == 1
    assert client.get("/u").status_code == 404
    assert client.get("/robots.txt").status_code == 200
    assert _hits("public_ip:" + IP) == 1


def test_exempt_routes_pass_when_public_bucket_full():
    hits, _ = tw_settings.rate("public_ip")
    _fill("public_ip:" + IP, hits, 1)
    assert client.get("/robots.txt").status_code == 200
    assert client.post("/log/error", json={"msg": "x"}).status_code == 200


# ── 4 ──
def test_other_buckets_unchanged_and_separate():
    hits, _ = tw_settings.rate("public_ip")
    # log-error keeps its own bucket and old 429 shape
    _fill("log-error:" + IP, srv._LOG_ERROR_RATE, 1)
    r = client.post("/log/error", json={"msg": "x"})
    assert r.status_code == 429 and "error" in r.json() and "Retry-After" not in r.headers
    assert _hits("public_ip:" + IP) == 0
    # _RATE_LIMITED_PATHS keeps its ip: bucket (refused before the endpoint — no DB)
    _fill("ip:" + IP, srv._RATE_LIMIT, 1)
    r = client.post("/auth/login", json={"email": "a@b.c", "password": "x"})
    assert r.status_code == 429 and "Retry-After" not in r.headers
    assert _hits("public_ip:" + IP) == 0
    assert _hits("ip:" + IP) == srv._RATE_LIMIT and _hits("log-error:" + IP) == srv._LOG_ERROR_RATE
    # a full public bucket does not touch them
    _fill("public_ip:" + IP, hits, 1)
    assert client.get("/jobs").status_code == 429
    assert _hits("ip:" + IP) == srv._RATE_LIMIT and _hits("log-error:" + IP) == srv._LOG_ERROR_RATE


# ── 5 ──
def test_ip_from_get_client_ip_only():
    hits, _ = tw_settings.rate("public_ip")
    _fill("public_ip:203.0.113.9", hits, 1)
    r = client.get("/jobs", headers={"X-Real-IP": "203.0.113.9", "X-Forwarded-For": "198.51.100.1"})
    assert r.status_code == 429
    r = client.get("/u", headers={"X-Real-IP": "198.51.100.1", "X-Forwarded-For": "203.0.113.9"})
    assert r.status_code == 404   # other IP, exempt route — and the forged XFF is not the key
    assert _hits("public_ip:198.51.100.1") == 0


# ── 6 ──
def test_settings_registry_and_ranges():
    for key, mn, mx in (("public_ip_hits", 60, 2000), ("public_ip_window_s", 10, 600)):
        d = tw_settings.REGISTRY[key]
        assert (d["min"], d["max"], d["security"], d["group"]) == (mn, mx, True, "sec_public")
        assert tw_settings.is_security(key)
        for bad in (mn - 1, mx + 1):
            with pytest.raises(tw_settings.SettingError) as e:
                tw_settings.validate(key, bad)
            assert e.value.status == 422
        assert tw_settings.validate(key, mn) == mn and tw_settings.validate(key, mx) == mx
    assert tw_settings.rate("public_ip") == (240, 60)
    assert "sec_public" in tw_settings.GROUPS
    for k in ("admin.settings.group.sec_public", "settings.item.public_ip_hits", "settings.item.public_ip_window_s"):
        assert srv._tw_text(k) != k


def test_admin_value_applies_at_once():
    _fill("public_ip:" + IP, 60, 1)
    tw_settings._set_overrides({"public_ip_hits": 60})
    assert client.get("/jobs").status_code == 429
    tw_settings._set_overrides({"public_ip_hits": 61})
    srv._rate_store["public_ip:" + IP] = [time.time() - 1] * 61
    assert client.get("/jobs").status_code == 429


# ── 7 ──
# Auth that the endpoint itself always runs first (admin JWT · scheduler secret · the settings write
# wrapper = check_admin first). Only the endpoint's own calls — an optional check deeper down (e.g. the
# owner / admin detail of /profile/{id}/score) does not make a guest route private.
_GUARDS = {"check_admin", "SCHEDULER_SECRET", "_settings_write"}


def _deps(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _deps(d)


def _guarded_in_body(fn):
    return bool(set(getattr(getattr(fn, "__code__", None), "co_names", ())) & _GUARDS)


def test_every_guest_route_is_limited_or_exempt():
    missing, both, limited = [], [], set()
    for r in srv.app.routes:
        if not isinstance(r, APIRoute):
            continue   # WebSocket before auth = AUD-P2-19 (out of scope)
        deps = set(_deps(r.dependant))
        if srv.verify_token in deps or _guarded_in_body(r.endpoint):
            continue
        has = srv._public_rate in deps
        exempt = r.path in srv.PUBLIC_RATE_EXEMPT
        if has:
            limited.add(r.path)
        if has and exempt:
            both.append(r.path)
        elif not has and not exempt:
            missing.append(f"{sorted(r.methods)} {r.path}")
    assert not missing, "guest routes without _public_rate or PUBLIC_RATE_EXEMPT: " + ", ".join(missing)
    assert not both, both
    paths = {r.path for r in srv.app.routes if isinstance(r, APIRoute)}
    assert not set(srv.PUBLIC_RATE_EXEMPT) - paths, "stale exempt entries"
    assert all(srv.PUBLIC_RATE_EXEMPT.values())
    assert {"/news/banner", "/u/{tw_id}", "/company-profile", "/jobs", "/profile/{user_id}/score"} <= limited
