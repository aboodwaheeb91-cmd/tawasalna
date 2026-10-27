"""Task 4.2 — security settings on the unified admin settings (SYSTEMS_INDEX §25g · docs/rules/settings.md).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it):
  - every security key: min - 1 / max + 1 → 422 out_of_range, nothing stored
  - every security write is one audit row with action "<route>_security" (200 · 403 · 422), filterable
  - a change applies at once on the real code: login locks (count + window) · OTP attempts + lifetime ·
    password-reset per IP / per email · rate store cap + sweep · IP country cache cap + TTL ·
    comments / mention / blocks page sizes · view dedup window
  - password_max_bytes is never editable (404)
Run: python -m pytest tests/test_admin_settings_security.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-settings-42-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-42-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import admin_insights
import tw_limits
import tw_settings
import server as srv

client = TestClient(srv.app)


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def env():
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    try:
        c.run("DROP TABLE IF EXISTS app_settings")
        c.run("DROP TABLE IF EXISTS admin_audit_log")
    finally:
        auth.release_conn(c)
    admin_insights.migrate_admin_audit_log()
    tw_settings.migrate_app_settings()
    tw_settings.reload()
    srv._rate_store.clear()
    yield
    tw_settings._set_overrides({})
    srv._rate_store.clear()
    srv.app.dependency_overrides.clear()


def _owner():
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _set(key, value):
    r = client.put(f"/admin/settings/{key}", json={"value": value}, headers=_owner())
    assert r.status_code == 200, (key, r.text)


SEC = sorted(tw_settings.SECURITY_KEYS)


# ── the list + range ──
def test_security_list_and_ranges():
    assert len(SEC) == 22 + 6 + 2 + 6 + 8 + 4 + 7   # 4.2 list + 4.3 otp_send_user / otp_send_target / otp_send_ip + 6 public_ip (hits + window)
                                            # + 7.1 support_guest_email / _ip / _global (hits + window)
                                            # + 7.2a support_link_resend_email / _ip · support_reply_ticket (7.5a) · support_track_ip
                                            # + 7.3 support_inbound_sender / _global (hits + window)
                                            # + 7.4 support_track_code_gap / _ticket / _ip (hits + window) + support_track_session_hours
    assert "password_max_bytes" not in tw_settings.REGISTRY
    assert client.put("/admin/settings/password_max_bytes", json={"value": 72}, headers=_owner()).status_code == 404
    items = {it["key"]: it for it in client.get("/admin/settings", headers=_owner()).json()["data"]["items"]}
    for key in SEC:
        it = items[key]
        assert it["security"] is True and it["group"].startswith("sec_") and it["requires_restart"] is False, key
        for bad in (it["min"] - 1, it["max"] + 1):
            r = client.put(f"/admin/settings/{key}", json={"value": bad}, headers=_owner())
            assert r.status_code == 422 and r.json()["error"]["code"] == "out_of_range", (key, bad)
    assert _sql("SELECT COUNT(*) FROM app_settings")[0][0] == 0
    # minimums never open guessing / never lock normal users out
    assert tw_settings.REGISTRY["login_email_hits"]["min"] >= 3 and tw_settings.REGISTRY["login_email_hits"]["max"] <= 20
    assert tw_settings.REGISTRY["login_email_window_s"]["min"] >= 300
    assert tw_settings.REGISTRY["otp_max_attempts"]["max"] <= 10


# ── audit: marked security ──
def test_audit_rows_marked_security():
    _set("login_email_hits", 4)
    assert client.post("/admin/settings/login_email_hits/reset", headers=_owner()).status_code == 200
    assert client.put("/admin/settings/otp_ttl_min", json={"value": 999}, headers=_owner()).status_code == 422
    staff = {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:7", perms=["reports.read"])}
    assert client.put("/admin/settings/login_ip_hits", json={"value": 30}, headers=staff).status_code == 403
    _set("message_max", 900)                                              # a normal setting stays unmarked
    rows = _sql("SELECT actor, action, target, result, old_value, new_value FROM admin_audit_log ORDER BY id")
    assert rows[0] == ["owner", "admin_settings_update_security", "key=login_email_hits", "ok", "5", "4"]
    assert rows[1] == ["owner", "admin_settings_reset_security", "key=login_email_hits", "ok", "4", "5"]
    assert rows[2][1:3] == ["admin_settings_update_security", "key=otp_ttl_min"] and rows[2][3] == "failed"
    assert rows[3][:4] == ["staff:7", "admin_settings_update_security", "key=login_ip_hits", "denied"]
    assert rows[4][1:3] == ["admin_settings_update", "key=message_max"]
    listed = client.get("/admin/audit?action=admin_settings_update_security", headers=_owner()).json()["data"]["items"]
    assert {it["target"] for it in listed} == {"key=login_email_hits", "key=otp_ttl_min", "key=login_ip_hits"}


# ── applies at once ──
def test_login_locks_follow_the_setting():
    email, ip = "lock42@example.com", "9.9.9.9"
    _set("login_email_hits", 3)
    _set("login_email_window_s", 300)
    for _ in range(2):
        srv._login_fail(email, ip)
    assert srv._login_locked(email, ip) is None
    srv._login_fail(email, ip)
    assert srv._login_locked(email, ip) == 300                            # locked after the NEW count, new window
    srv._rate_store.clear()
    _set("login_ip_hits", 10)
    for i in range(10):
        srv._login_fail(f"u{i}@example.com", "8.8.8.8")
    assert srv._login_locked("other@example.com", "8.8.8.8") == tw_limits.RATES["login_ip"][1]
    srv._rate_store.clear()
    _set("login_ip_email_hits", 4)
    _set("login_email_hits", 20)
    for _ in range(3):
        srv._login_fail(email, ip)
    assert srv._login_locked(email, ip) is None                           # default pair cap (3) no longer applies
    srv._login_fail(email, ip)
    assert srv._login_locked(email, ip) is not None


def test_otp_attempts_and_lifetime_follow_the_setting():
    c = auth.get_conn()
    try:
        c.run("DROP TABLE IF EXISTS kyc_submissions")
        c.run("CREATE TABLE kyc_submissions (id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE, step TEXT, "
              "email_code TEXT, email_verified BOOLEAN DEFAULT FALSE, phone TEXT, phone_code TEXT, "
              "phone_verified BOOLEAN DEFAULT FALSE)")
        c.run("INSERT INTO kyc_submissions (user_id, step) VALUES (42, 'phone')")
    finally:
        auth.release_conn(c)
    auth._migrate_kyc_otp_security()
    _set("otp_max_attempts", 3)
    _set("otp_ttl_min", 5)
    code = auth._otp_issue(42, "phone", "+962790000000")
    left = _sql("SELECT EXTRACT(EPOCH FROM phone_code_expires_at - NOW()) FROM kyc_submissions WHERE user_id = 42")[0][0]
    assert 240 < float(left) <= 300                                       # 5 minutes, not the default 10
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(3):
        assert auth._otp_verify(42, "phone", wrong, "+962790000000") is False
    assert auth._otp_verify(42, "phone", code, "+962790000000") is False  # dead after 3 (default 5)


def test_password_reset_limits_follow_the_setting(monkeypatch):
    sent = []
    monkeypatch.setattr(srv.email_service, "can_send", lambda kind: True)
    monkeypatch.setattr(srv.email_service, "valid_address", lambda e: True)
    monkeypatch.setattr(srv, "_password_reset_send", lambda e: sent.append(e))
    req = lambda email, ip: client.post("/auth/password-reset/request", json={"email": email},
                                        headers={"X-Real-IP": ip}).status_code
    _set("pwreset_ip_hits", 3)
    assert [req(f"p{i}@example.com", "7.7.7.7") for i in range(4)] == [200, 200, 200, 429]
    srv._rate_store.clear()
    sent.clear()
    _set("pwreset_email_hits", 1)
    assert [req("same@example.com", f"6.6.6.{i}") for i in range(3)] == [200, 200, 200]
    assert sent == ["same@example.com"]                                   # one email (default 3)


def test_rate_store_cap_and_sweep_follow_the_setting():
    _set("mem_store_max_keys", 5000)
    for i in range(5050):
        srv._rate_hit(f"message_send:{i}", 100, 60)
    assert len(srv._rate_store.section("message_send")) <= 5000
    srv._rate_store.clear()
    _set("mem_store_sweep_s", 10)
    now = time.time()
    srv._rate_store["message_send:old"] = [now - 10_000]
    srv._rate_sweep_at = now
    assert srv._rate_sweep(now + 5) == 0                                  # within 10 s: no sweep
    assert srv._rate_sweep(now + 11) == 1                                 # past 10 s (default 60): swept


def test_ip_country_cache_follows_the_setting(monkeypatch):
    srv.IP_TO_COUNTRY_CACHE.clear()
    _set("ip_country_cache_max", 1000)
    for i in range(1010):
        srv._ip_country_cache_put(f"10.0.{i // 256}.{i % 256}", "JO")
    assert len(srv.IP_TO_COUNTRY_CACHE) == 1000
    monkeypatch.setattr(srv.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    srv.IP_TO_COUNTRY_CACHE.clear()
    srv.IP_TO_COUNTRY_CACHE["5.5.5.5"] = ("JO", time.time() - 4000)
    assert srv.get_country_from_ip("5.5.5.5") == "JO"                     # default TTL 1 day: still cached
    _set("ip_country_cache_ttl_s", 3600)
    assert srv.get_country_from_ip("5.5.5.5") == "DEFAULT"                # 1 h: stale → looked up again
    srv.IP_TO_COUNTRY_CACHE.clear()


def test_page_sizes_follow_the_setting(monkeypatch):
    seen = {}
    monkeypatch.setattr(srv, "get_post_owner", lambda pid: None)
    monkeypatch.setattr(srv, "get_company_post_comments",
                        lambda pid, vid, limit, cursor: (seen.setdefault("c", []).append(limit), ([], None))[1])
    _set("comments_page", 7)
    _set("comments_page_max", 12)
    client.get("/company/posts/1/comments")
    client.get("/company/posts/1/comments?limit=99")
    assert seen["c"] == [7, 12]

    srv.app.dependency_overrides[srv.verify_token] = lambda: {"user_id": 4242, "user_type": "emp"}
    monkeypatch.setattr(srv.bs, "list_blocked", lambda me, limit, offset: seen.setdefault("b", limit) and {})
    _set("blocks_page_max", 15)
    client.get("/blocks?limit=500")
    assert seen["b"] == 15

    class _Conn:
        def run(self, sql, **kw):
            return [(f"U{i}", "n", None, "emp") for i in range(100)]
    monkeypatch.setattr(srv, "get_conn", lambda: _Conn())
    monkeypatch.setattr(srv, "release_conn", lambda c: None)
    _set("mention_limit_max", 6)
    r = client.get("/mention/search?q=n&limit=50")
    assert len(r.json()["candidates"]) == 6                               # default ceiling 20


def test_view_dedup_window_follows_the_setting():
    assert srv._rate_ok("view_count", "post1:u1") is True
    srv._rate_store["view_count:post1:u1"] = [time.time() - 4000]
    assert srv._rate_ok("view_count", "post1:u1") is False                # default 1 day: same view
    _set("view_count_window_s", 3600)
    srv._rate_store["view_count:post1:u1"] = [time.time() - 4000]
    assert srv._rate_ok("view_count", "post1:u1") is True                 # 1 h: counted again
    _set("report_repeat_window_s", 7200)
    assert tw_settings.rate("report_repeat") == (1, 7200)                 # the value the report SQL reads
