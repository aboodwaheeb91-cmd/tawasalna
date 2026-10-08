"""
test_kyc_docs_migration.py — PR-7c: admin KYC document viewing (signed URLs) +
migration of legacy data: images to Storage (SYSTEMS_INDEX §29a / §23 ·
docs/rules/upload.md). Real FastAPI app; DB + Supabase Storage mocked.

Run: python -m pytest tests/test_kyc_docs_migration.py -q
"""
import base64, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-pr7c-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-jwt-pr7c-" + "s" * 32)

import httpx
import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)
if not server._admin_jwt_secret_ok():   # server imported earlier by another test file
    server.ADMIN_JWT_SECRET = os.environ["ADMIN_JWT_SECRET"]
ADMIN = {"X-Admin-Token": server._admin_jwt_issue()}   # PR 1.5: admin session JWT, not the raw ADMIN_TOKEN
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
DATA_PNG = "data:image/png;base64," + base64.b64encode(PNG).decode()
DATA_SVG = "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()
TOKEN = "SECRET-SIGN-TOKEN-xyz"


class FakeStorage:
    calls = []

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def post(self, url, content=None, json=None, headers=None):
        FakeStorage.calls.append(url)
        if "/object/sign/" in url:
            name = url.split("/object/sign/", 1)[1]
            return httpx.Response(200, json={"signedURL": f"/object/sign/{name}?token={TOKEN}"})
        return httpx.Response(200, text="ok")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    FakeStorage.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeStorage)
    monkeypatch.setenv("SUPABASE_URL", "https://sb.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test")
    monkeypatch.delenv("TW_DEV_UPLOAD", raising=False)


# ── (a) KYC docs ──────────────────────────────────────────────────────────────

def _kyc_row(monkeypatch, row):
    monkeypatch.setattr(server, "_current_image_urls", lambda sql, sid: row)


def test_docs_requires_admin(monkeypatch):
    _kyc_row(monkeypatch, {"user_id": 5, "id_front_url": None, "selfie_url": None})
    assert client.get("/admin/kyc/1/docs").status_code == 401
    assert client.get("/admin/kyc/1/docs", headers={"X-Admin-Token": "b" * 40}).status_code == 401
    assert client.get("/admin/kyc/1/docs", headers={"X-Admin-Token": "a" * 40}).status_code == 401


def test_docs_signed_for_own_paths_only_no_store_no_log(monkeypatch, capsys):
    _kyc_row(monkeypatch, {
        "user_id": 5,
        "id_front_url": "kyc-docs/5_kyc-id-front_0123456789ab.jpg",
        "selfie_url": "kyc-docs/9_kyc-selfie_0123456789ab.png",   # another user's path
    })
    r = client.get("/admin/kyc/3/docs", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    d = r.json()["docs"]
    assert d["id_front"]["url"].startswith(
        "https://sb.supabase.co/storage/v1/object/sign/kyc-docs/5_kyc-id-front_0123456789ab.jpg?token=")
    assert d["selfie"] == {"url": None, "reason": "invalid_path"}
    assert len(FakeStorage.calls) == 1        # never signed the foreign path
    assert TOKEN not in capsys.readouterr().out


def test_docs_legacy_values_null_with_reason(monkeypatch):
    _kyc_row(monkeypatch, {"user_id": 5, "id_front_url": DATA_PNG,
                           "selfie_url": "https://evil.example/x.png"})
    d = client.get("/admin/kyc/3/docs", headers=ADMIN).json()["docs"]
    assert d["id_front"] == {"url": None, "reason": "legacy_data_url"}
    assert d["selfie"] == {"url": None, "reason": "legacy_url"}
    assert FakeStorage.calls == []


def test_admin_kyc_list_allowlist_only(monkeypatch):
    """Real get_all_kyc_submissions with a fake connection: explicit columns,
    never OTP codes / document paths; the fields admin.html reads remain."""
    import auth
    seen = []

    class Conn:
        def run(self, sql, **p):
            seen.append(sql)
            return [[1, 5, "Ali", "a@x.com", "emp", "review", "pending",
                     True, False, None, None, None]]
    monkeypatch.setattr(auth, "get_conn", lambda: Conn())
    monkeypatch.setattr(auth, "release_conn", lambda c: None)
    s = client.get("/admin/kyc", headers=ADMIN).json()["submissions"][0]
    for banned in ("email_code", "phone_code", "id_front_url", "selfie_url", "ks.*"):
        assert banned not in seen[0] and banned not in s
    assert set(s) == {name for name, _ in auth._ADMIN_KYC_LIST_COLUMNS}
    # admin.html → renderKYC / renderVerify / updateStats / openKYCDocs
    assert (s["id"], s["user_id"], s["full_name"], s["email"], s["step"], s["status"]) == \
        (1, 5, "Ali", "a@x.com", "review", "pending")


# ── (b) data: image migration ────────────────────────────────────────────────

class FakeDB:
    """profiles.avatar_url rows keyed by user_id; other targets empty."""
    def __init__(self, avatars, user_types):
        self.avatars, self.types, self.updates = dict(avatars), user_types, []
        self.change_before_update = {}

    def run(self, sql, **p):
        if sql.startswith("SELECT"):
            if "p.avatar_url" in sql:
                return [[k, v, self.types[k]] for k, v in sorted(self.avatars.items())
                        if v.startswith("data:")]
            return []
        if sql.startswith("UPDATE profiles SET avatar_url"):
            self.updates.append(p["k"])
            if p["k"] in self.change_before_update:
                self.avatars[p["k"]] = self.change_before_update.pop(p["k"])
            if self.avatars.get(p["k"]) == p["old"]:
                self.avatars[p["k"]] = p["new"]
                return [[1]]
            return []
        raise AssertionError("unexpected SQL: " + sql)


def _mig(monkeypatch, db, dry):
    monkeypatch.setattr(server, "_mig_run", db.run)
    r = client.post(f"/admin/maintenance/migrate-data-images?dry_run={dry}", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert "base64" not in r.text and "sb.supabase.co" not in r.text
    return r.json()["report"]["profiles.avatar_url"]


def test_migrate_requires_admin():
    assert client.post("/admin/maintenance/migrate-data-images").status_code == 401


def test_dry_run_default_writes_nothing(monkeypatch):
    db = FakeDB({1: DATA_PNG, 2: DATA_SVG}, {1: "emp", 2: "emp"})
    monkeypatch.setattr(server, "_mig_run", db.run)
    rep = client.post("/admin/maintenance/migrate-data-images", headers=ADMIN).json()
    a = rep["report"]["profiles.avatar_url"]
    assert rep["dry_run"] is True
    assert (a["found"], a["would_migrate"], a["migrated"], a["skipped"]) == (2, 1, 0, 1)
    assert db.updates == [] and FakeStorage.calls == []


def test_migrate_conditional_invalid_left_and_idempotent(monkeypatch):
    db = FakeDB({1: DATA_PNG, 2: DATA_SVG, 3: DATA_PNG}, {1: "co", 2: "emp", 3: "emp"})
    db.change_before_update[3] = "https://sb.supabase.co/storage/v1/object/public/avatars/3_employee-avatar_aaaaaaaaaaaa.jpg"
    a = _mig(monkeypatch, db, 0)
    assert (a["found"], a["migrated"], a["skipped"]) == (3, 1, 2)
    assert a["reasons"] == {"invalid_image": 1, "changed_concurrently": 1}
    assert db.avatars[1].startswith("https://sb.supabase.co/storage/v1/object/public/avatars/1_company-logo_")
    assert db.avatars[2] == DATA_SVG                     # invalid value untouched
    assert db.avatars[3].endswith("aaaaaaaaaaaa.jpg")    # newer value not overwritten
    uploads = len(FakeStorage.calls)
    a2 = _mig(monkeypatch, db, 0)                        # second run: nothing new
    assert (a2["found"], a2["migrated"]) == (1, 0) and a2["reasons"] == {"invalid_image": 1}
    assert len(FakeStorage.calls) == uploads


def test_docs_base_normalised_trailing_slash(monkeypatch):
    """Base comes from _supabase_base_url() (#551): a raw value with "/" or
    whitespace must not produce "//storage" or break the prefix check."""
    monkeypatch.setenv("SUPABASE_URL", " https://sb.supabase.co/ ")
    _kyc_row(monkeypatch, {"user_id": 5, "selfie_url": None,
                           "id_front_url": "kyc-docs/5_kyc-id-front_0123456789ab.jpg"})
    j = client.get("/admin/kyc/3/docs", headers=ADMIN).json()
    assert j["storage_base"] == "https://sb.supabase.co"
    assert FakeStorage.calls == ["https://sb.supabase.co/storage/v1/object/sign/kyc-docs/5_kyc-id-front_0123456789ab.jpg"]
    assert j["docs"]["id_front"]["url"].startswith("https://sb.supabase.co/storage/v1/object/sign/kyc-docs/")
