"""
test_logo_upload_save_811a.py — task 8.11a: POST /admin/logo never reports success when the DB save fails.

Save failure (set_site_setting raises / returns False) → 500 · _html_cache unchanged · the just-stored object
deleted via storage_delete (same bucket + name) — a failed delete still answers 500 · success → 200 + value in
site_settings + GET /admin/logo returns it · no / non-content admin token → 401 / 403.

Real PostgreSQL, in-process client, Supabase Storage faked (httpx.AsyncClient). TW_TEST_DB_URL (run_tests.sh
sets it) — without it skipped.
Run: python -m pytest tests/test_logo_upload_save_811a.py -q
"""
import base64, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import httpx
import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-811a-" + "a" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
BODY = {"filename": "logo_wide", "data_url": "data:image/png;base64," + base64.b64encode(PNG).decode()}
PUBLIC = "https://sb.supabase.co/storage/v1/object/public/site/"


class FakeStorage:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def __init__(self, *a, **k): pass

    async def post(self, url, content=None, headers=None):
        return httpx.Response(200, text="{}")


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


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    monkeypatch.setattr(httpx, "AsyncClient", FakeStorage)
    monkeypatch.setenv("SUPABASE_URL", "https://sb.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test")
    monkeypatch.delenv("TW_DEV_UPLOAD", raising=False)
    deleted = []
    monkeypatch.setattr(srv, "storage_delete",
                        lambda bucket, name: deleted.append((bucket, name)) or {"ok": True, "status": 200, "reason": None})
    srv._rate_store.clear()
    old = srv._html_cache.get("logo_wide")
    srv._html_cache["logo_wide"] = "https://cached.example/before.png"
    with auth.db_conn() as c:
        c.run("DELETE FROM site_settings WHERE key = 'logo_wide'")
    yield deleted
    if old is None:
        srv._html_cache.pop("logo_wide", None)
    else:
        srv._html_cache["logo_wide"] = old


def _owner():
    return {"X-Admin-Token": srv._admin_jwt_issue()}


def _stored():
    with auth.db_conn() as c:
        rows = c.run("SELECT value FROM site_settings WHERE key = 'logo_wide'")
    return rows[0][0] if rows else None


@pytest.mark.parametrize("mode", ["raise", "false"])
def test_save_failure_500_cache_unchanged_orphan_deleted(env, monkeypatch, mode):
    def fail(key, value):
        if mode == "raise":
            raise RuntimeError("db down")
        return False
    monkeypatch.setattr(srv, "set_site_setting", fail)
    r = client.post("/admin/logo", json=BODY, headers=_owner())
    assert r.status_code == 500
    assert "success" not in r.text and "db down" not in r.text
    assert srv._html_cache["logo_wide"] == "https://cached.example/before.png"
    assert _stored() is None
    assert len(env) == 1
    bucket, name = env[0]
    assert bucket == "site" and name.startswith("logo_wide_") and name.endswith(".png")


def test_orphan_delete_failure_still_500(env, monkeypatch):
    monkeypatch.setattr(srv, "set_site_setting", lambda k, v: False)
    monkeypatch.setattr(srv, "storage_delete", lambda b, n: {"ok": False, "status": 500, "reason": "rejected"})
    r = client.post("/admin/logo", json=BODY, headers=_owner())
    assert r.status_code == 500
    assert srv._html_cache["logo_wide"] == "https://cached.example/before.png"


def test_success_saved_in_db_and_served(env):
    r = client.post("/admin/logo", json=BODY, headers=_owner())
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith(PUBLIC + "logo_wide_")
    assert _stored() == url
    assert srv._html_cache["logo_wide"] == url
    srv._html_cache.pop("logo_wide", None)          # GET must find it in the DB too (another instance / restart)
    assert client.get("/admin/logo").json()["logo_wide"] == url
    assert env == []


def test_gate_401_403(env):
    assert client.post("/admin/logo", json=BODY).status_code == 401
    staff = {"X-Admin-Token": srv._admin_jwt_issue(sub="staff:811a", perms=["settings.edit"])}
    assert client.post("/admin/logo", json=BODY, headers=staff).status_code == 403
    assert _stored() is None and env == []
