"""
test_upload_security.py — PR-7a: POST /upload/image + POST /admin/logo hardening
(SYSTEMS_INDEX §29a · docs/rules/upload.md). Runs against the real FastAPI app
with Supabase Storage mocked (no network, no DB).

Run: python -m pytest test_upload_security.py -q
"""
import base64, os, sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET", "test-secret-pr7a-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)

import httpx
import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
HTML = b"<html><script>alert(1)</script></html>"


def durl(mime, raw):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def auth(uid=7):
    return {"Authorization": "Bearer " + server._jwt_encode({"user_id": uid, "user_type": "emp"})}


class FakeStorage:
    """Replaces httpx.AsyncClient; records calls; returns `status` or raises."""
    calls = []
    status = 200
    raise_exc = False

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def post(self, url, content=None, headers=None):
        FakeStorage.calls.append({"url": url, "headers": headers, "len": len(content)})
        if FakeStorage.raise_exc:
            raise httpx.ConnectError("boom-secret-detail")
        return httpx.Response(FakeStorage.status, text="storage said no")


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    FakeStorage.calls, FakeStorage.status, FakeStorage.raise_exc = [], 200, False
    monkeypatch.setattr(httpx, "AsyncClient", FakeStorage)
    monkeypatch.setenv("SUPABASE_URL", "https://sb.example")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.delenv("TW_DEV_UPLOAD", raising=False)
    return FakeStorage


def up(body, uid=7):
    return client.post("/upload/image", json=body, headers=auth(uid))


def test_valid_upload_server_decides_bucket_and_name(storage):
    r = up({"kind": "employee-avatar", "data_url": durl("image/png", PNG)})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://sb.example/storage/v1/object/public/avatars/7_employee-avatar_")
    assert url.endswith(".png")
    assert storage.calls[0]["headers"].get("x-upsert") is None


def test_unknown_kind_400(storage):
    assert up({"kind": "site-logo", "data_url": durl("image/png", PNG)}).status_code == 400
    assert up({"data_url": durl("image/png", PNG)}).status_code == 400
    assert storage.calls == []


def test_forged_bucket_and_filename_ignored(storage):
    r = up({"kind": "employee-cover", "bucket": "site", "filename": "../logo_wide",
            "data_url": durl("image/jpeg", JPEG)})
    assert r.status_code == 200
    target = storage.calls[0]["url"]
    assert "/object/covers/7_employee-cover_" in target
    assert "site" not in target and "logo_wide" not in target and ".." not in target


def test_body_user_id_ignored(storage):
    r = up({"kind": "employee-avatar", "user_id": 999, "data_url": durl("image/png", PNG)}, uid=7)
    assert r.status_code == 200
    assert "/avatars/7_employee-avatar_" in storage.calls[0]["url"]
    assert "999" not in storage.calls[0]["url"]


def test_html_disguised_as_png_400(storage):
    assert up({"kind": "employee-avatar", "data_url": durl("image/png", HTML)}).status_code == 400
    # declared jpeg, real png → mismatch
    assert up({"kind": "employee-avatar", "data_url": durl("image/jpeg", PNG)}).status_code == 400
    assert storage.calls == []


def test_svg_rejected(storage):
    assert up({"kind": "employee-avatar", "data_url": durl("image/svg+xml", SVG)}).status_code == 400
    assert up({"kind": "employee-avatar", "data_url": durl("image/png", SVG)}).status_code == 400


def test_too_large(storage):
    big = JPEG + b"\x00" * (5 * 1024 * 1024)
    assert up({"kind": "employee-cover", "data_url": durl("image/jpeg", big)}).status_code == 413
    huge = "data:image/jpeg;base64," + "A" * (8 * 1024 * 1024)
    assert up({"kind": "employee-cover", "data_url": huge}).status_code == 413
    assert storage.calls == []


def test_broken_base64_400(storage):
    assert up({"kind": "employee-avatar", "data_url": "data:image/png;base64,@@@not-b64!!"}).status_code == 400


@pytest.mark.parametrize("mode", ["status", "exception", "no_keys"])
def test_storage_failure_never_returns_data_url(storage, monkeypatch, mode):
    if mode == "status":
        storage.status = 500
    elif mode == "exception":
        storage.raise_exc = True
    else:
        monkeypatch.delenv("SUPABASE_SERVICE_KEY")
    r = up({"kind": "employee-avatar", "data_url": durl("image/png", PNG)})
    assert r.status_code in (502, 503)
    body = r.text
    assert "data:" not in body and "url" not in r.json()
    assert "boom-secret-detail" not in body and "storage said no" not in body


def test_dev_mode_only_with_explicit_flag(storage, monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_KEY")
    monkeypatch.setenv("TW_DEV_UPLOAD", "1")
    r = up({"kind": "employee-avatar", "data_url": durl("image/png", PNG)})
    assert r.status_code == 200 and r.json().get("dev_mode") is True


def test_requires_jwt(storage):
    r = client.post("/upload/image", json={"kind": "employee-avatar", "data_url": durl("image/png", PNG)})
    assert r.status_code == 401


def test_admin_logo_validation(storage):
    h = {"X-Admin-Token": os.environ["ADMIN_TOKEN"]}
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/svg+xml", SVG)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", HTML)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "../x", "data_url": durl("image/png", PNG)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", PNG)}).status_code == 403
    storage.status = 500
    r = client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", PNG)}, headers=h)
    assert r.status_code == 502 and "data:" not in r.text
