"""Task 4.1 — Unified Admin Settings (SYSTEMS_INDEX §25g · docs/rules/settings.md).

Behaviour only — real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it):
  - GET / PUT / POST /admin/settings…: no token → 401 · admin token without settings.edit → 403 · owner → 200
  - out of range / wrong type / missing value → 422 (Arabic message) · key outside the allowlist → 404
  - a change applies at once on the real limit code (_rate_ok message_send · _too_long message_max ·
    window.TW_LIMITS in a served page) · reset → default, row deleted
  - the admin audit log records both (key · old · new · operation · actor)
  - DB failure → defaults (logged), never an exception
  - the registry: an allowlist of tw_limits keys only, 4.2 keys only as security=True (never
    password_max_bytes), no secret, minimums ≥ 1 (security keys: tests/test_admin_settings_security.py)
Run: python -m pytest tests/test_admin_settings.py -q
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-settings-41-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-41-" + "s" * 32)
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
    yield
    tw_settings._set_overrides({})


def _owner():
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _staff():   # a valid admin token without settings.edit
    return {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:7", perms=["reports.read"])}


def _put(key, value, headers=None):
    return client.put(f"/admin/settings/{key}", json={"value": value}, headers=_owner() if headers is None else headers)


# ── gate ──
def test_gate_401_403_200():
    calls = (("get", "/admin/settings", None), ("put", "/admin/settings/message_max", {"value": 900}),
             ("post", "/admin/settings/message_max/reset", None))
    for method, url, body in calls:
        kw = {"json": body} if body else {}
        assert getattr(client, method)(url, **kw).status_code == 401, url
        assert getattr(client, method)(url, headers={"X-Admin-Token": "bad"}, **kw).status_code == 401, url
        assert getattr(client, method)(url, headers=_staff(), **kw).status_code == 403, url
    assert tw_settings.value("message_max") == tw_limits.LIMITS["message_max"]   # nothing written by 401 / 403
    assert _sql("SELECT COUNT(*) FROM app_settings")[0][0] == 0
    r = client.get("/admin/settings", headers=_owner())
    assert r.status_code == 200
    d = r.json()["data"]
    keys = [it["key"] for it in d["items"]]
    assert keys == list(tw_settings.REGISTRY)
    it = next(x for x in d["items"] if x["key"] == "message_send_hits")
    assert it["value"] == it["default"] == tw_limits.RATES["message_send"][0]
    assert it["min"] >= 1 and it["label"] and it["description"] and it["requires_restart"] is False
    assert d["cache_ttl_s"] == 30


# ── validation ──
def test_validation_range_type_unknown():
    lo = tw_settings.REGISTRY["message_max"]["min"]
    r = _put("message_max", lo - 1)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "out_of_range" and err["field"] == "value" and re.search(r"[؀-ۿ]", err["message"])
    assert _put("message_send_hits", 0).status_code == 422          # never 0 for a send limit
    r = _put("mention_search_hits", 121)                             # 4.1a: max 120
    assert r.status_code == 422 and r.json()["error"]["code"] == "out_of_range"
    assert tw_settings.REGISTRY["mention_search_hits"]["max"] == 120
    assert tw_settings._clean([("mention_search_hits", 300)]) == {}  # old stored value ignored
    for bad in ("900", 900.5, True, None, [900]):
        r = _put("message_max", bad)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_type", bad
    assert client.put("/admin/settings/message_max", json={}, headers=_owner()).status_code == 422
    for key in ("password_max_bytes", "view_count_hits", "report_repeat_hits", "JWT_SECRET", "nope"):
        assert _put(key, 10).status_code == 404, key
        assert client.post(f"/admin/settings/{key}/reset", headers=_owner()).status_code == 404, key
    assert _sql("SELECT COUNT(*) FROM app_settings")[0][0] == 0


# ── applies at once + reset + audit ──
def test_change_applies_now_reset_and_audit():
    uid = 990041
    r = _put("message_send_hits", 5)
    assert r.status_code == 200 and r.json()["data"]["setting"]["value"] == 5
    assert r.json()["data"]["old"] == tw_limits.RATES["message_send"][0]
    assert _sql("SELECT value FROM app_settings WHERE key = 'message_send_hits'") == [[5]]
    assert [srv._rate_ok("message_send", uid) for _ in range(6)] == [True] * 5 + [False]

    assert _put("message_max", 600).status_code == 200
    assert srv._too_long("x" * 600, "message_max", "content") is None
    assert srv._too_long("x" * 601, "message_max", "content").status_code == 422
    assert '"message_max":600' in srv.read_html("admin-settings.html")   # window.TW_LIMITS rebuilt

    r = client.post("/admin/settings/message_send_hits/reset", headers=_owner())
    assert r.status_code == 200 and r.json()["data"]["setting"]["value"] == tw_limits.RATES["message_send"][0]
    assert _sql("SELECT COUNT(*) FROM app_settings WHERE key = 'message_send_hits'")[0][0] == 0
    assert tw_settings.rate("message_send") == tw_limits.RATES["message_send"]

    # a value equal to the default stores nothing
    assert _put("message_max", tw_limits.LIMITS["message_max"]).status_code == 200
    assert _sql("SELECT COUNT(*) FROM app_settings")[0][0] == 0

    rows = _sql("SELECT actor, action, target, result, old_value, new_value FROM admin_audit_log "
                "WHERE action LIKE 'admin_settings_%' ORDER BY id")
    default_hits = str(tw_limits.RATES["message_send"][0])
    assert rows[0] == ["owner", "admin_settings_update", "key=message_send_hits", "ok", default_hits, "5"]
    assert ["owner", "admin_settings_reset", "key=message_send_hits", "ok", "5", default_hits] in rows
    listed = client.get("/admin/audit?action=admin_settings_reset", headers=_owner()).json()["data"]["items"]
    assert listed[0]["old_value"] == "5" and listed[0]["new_value"] == default_hits


def test_other_worker_sees_db_value_on_reload():
    _sql("INSERT INTO app_settings (key, value) VALUES ('post_tags_max', 3), ('nope', 1), ('message_max', 1)")
    assert tw_settings.reload() is True
    assert tw_settings.limit("post_tags_max") == 3                       # stored value
    assert tw_settings.limit("message_max") == tw_limits.LIMITS["message_max"]   # out of range → ignored


# ── DB failure → defaults ──
def test_db_failure_falls_back_to_defaults(monkeypatch):
    assert _put("message_max", 700).status_code == 200
    assert tw_settings.limit("message_max") == 700

    def boom():
        raise ConnectionError("db down")
    monkeypatch.setattr(tw_settings, "db_conn", boom)
    assert tw_settings.reload() is False                                 # never raises
    assert tw_settings.limit("message_max") == tw_limits.LIMITS["message_max"]
    assert srv._too_long("x" * 701, "message_max", "content") is None


# ── registry ──
def test_registry_is_an_allowlist():
    security_only = re.compile(r"^(login_|mem_store_|ip_country_cache_|otp|pwreset|view_count|report_repeat|"
                               r"comments_page|mention_limit_max|blocks_page_max|public_ip)")   # task 4.2 (+ 6 public_ip) → security=True
    for key, d in tw_settings.REGISTRY.items():
        src = d["source"]
        assert src[0] in ("LIMITS", "RATES") and not src[1].startswith("password_"), key   # bcrypt cut: never
        assert d["security"] is bool(security_only.match(src[1])), key
        assert not re.search(r"secret|token|(?<!max_)key|password|url_token", src[1], re.I), key   # max_keys = a count
        assert d["min"] >= 1 and d["min"] <= d["default"] <= d["max"], key
    # every registry source is read through tw_settings — no direct LIMITS["x"] / RATES["x"] in server.py / auth.py
    root = os.path.dirname(srv.__file__)
    src = "".join(open(os.path.join(root, f), encoding="utf-8").read() for f in ("server.py", "auth.py"))
    names = {d["source"][1] for d in tw_settings.REGISTRY.values()}
    direct = [n for n in names if re.search(r"tw_limits\.(LIMITS|RATES)\[\s*[\"']" + n + r"[\"']", src)]
    assert not direct, direct
