"""
test_upload_security.py — PR-7a: POST /upload/image + POST /admin/logo hardening
(SYSTEMS_INDEX §29a · docs/rules/upload.md). Runs against the real FastAPI app
with Supabase Storage mocked (no network, no DB).

Run: python -m pytest tests/test_upload_security.py -q
"""
import base64, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-pr7a-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-jwt-pr7a-" + "s" * 32)

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
    monkeypatch.setenv("SUPABASE_URL", "https://sb.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test")
    monkeypatch.delenv("TW_DEV_UPLOAD", raising=False)
    return FakeStorage


def up(body, uid=7):
    return client.post("/upload/image", json=body, headers=auth(uid))


def test_valid_upload_server_decides_bucket_and_name(storage):
    r = up({"kind": "employee-avatar", "data_url": durl("image/png", PNG)})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://sb.supabase.co/storage/v1/object/public/avatars/7_employee-avatar_")
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
    assert "/object/avatars/7_employee-cover_" in target
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
    if not server._admin_jwt_secret_ok():   # server imported earlier by another test file
        server.ADMIN_JWT_SECRET = os.environ["ADMIN_JWT_SECRET"]
    h = {"X-Admin-Token": server._admin_jwt_issue()}   # PR 1.5: admin session JWT
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/svg+xml", SVG)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", HTML)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "../x", "data_url": durl("image/png", PNG)}, headers=h).status_code == 400
    assert client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", PNG)}).status_code == 401
    storage.status = 500
    r = client.post("/admin/logo", json={"filename": "logo_wide", "data_url": durl("image/png", PNG)}, headers=h)
    assert r.status_code == 502 and "data:" not in r.text


# ── Stored image URL gate (_validate_stored_image_url) — every endpoint that saves an image URL ──

SB = "https://sb.supabase.co/storage/v1/object/public"
GOOD_AVATAR = f"{SB}/avatars/7_employee-avatar_0123456789ab.jpg"
LEGACY = "https://old.cdn.example/whatever.png"


@pytest.fixture
def db(monkeypatch):
    """Stub DB: current stored values + capture of what endpoints try to save."""
    saved = {}
    current = {"avatar_url": LEGACY, "cover_url": None,
               "id_front_url": "data:image/png;base64,AAAA", "selfie_url": None}
    monkeypatch.setattr(server, "_current_image_urls", lambda sql, uid: dict(current))
    monkeypatch.setattr(server, "update_profile",
                        lambda uid, data, user_type=None: saved.update(data) or {"id": uid})
    monkeypatch.setattr(server, "get_company_profile_row", lambda cid: {"cover_url": LEGACY})
    monkeypatch.setattr(server, "update_company_profile", lambda cid, d: saved.update(d) or True)
    monkeypatch.setattr(server, "upload_kyc_docs",
                        lambda uid, a, b: saved.update(id_front_url=a, selfie_url=b) or {"step": "review"})
    return saved


def put_profile(body, uid=7, utype="emp"):
    h = {"Authorization": "Bearer " + server._jwt_encode({"user_id": uid, "user_type": utype})}
    return client.put(f"/profile/{uid}", json=body, headers=h)


@pytest.mark.parametrize("bad", [
    "https://evil.example/x.jpg",                                   # external
    "data:image/png;base64," + base64.b64encode(PNG).decode(),     # data:
    "javascript:alert(1)",                                          # scheme
    f"{SB}/site/7_employee-avatar_0123456789ab.jpg",               # wrong bucket
    f"{SB}/avatars/8_employee-avatar_0123456789ab.jpg",            # another uid
    f"{SB}/avatars/7_company-logo_0123456789ab.jpg",               # wrong kind
    f"{SB}/avatars/7_employee-avatar_0123456789ab.jpg?x=1",        # query
    f"{SB}/avatars/7_employee-avatar_../../site/logo_wide.png",    # traversal
    f"{SB}/avatars/7_employee-avatar_0123456789ab.svg",            # extension
])
def test_profile_avatar_rejects_bad_urls(db, bad):
    r = put_profile({"avatar_url": bad})
    assert r.status_code == 400, (bad, r.text)
    assert "avatar_url" not in db


def test_profile_valid_url_legacy_value_and_clear_pass(db):
    assert put_profile({"avatar_url": GOOD_AVATAR}).status_code == 200
    assert db["avatar_url"] == GOOD_AVATAR
    assert put_profile({"avatar_url": LEGACY}).status_code == 200      # unchanged legacy value
    assert put_profile({"avatar_url": None}).status_code == 200        # clear
    assert put_profile({"cover_url": ""}).status_code == 200
    ok_cover = f"{SB}/avatars/7_employee-cover_abcdef012345.webp"
    assert put_profile({"cover_url": ok_cover}).status_code == 200


def test_company_logo_and_cover(db):
    logo = f"{SB}/avatars/9_company-logo_abcdef012345.png"
    assert put_profile({"avatar_url": logo}, uid=9, utype="co").status_code == 200
    assert put_profile({"avatar_url": GOOD_AVATAR}, uid=9, utype="co").status_code == 400
    h = {"Authorization": "Bearer " + server._jwt_encode({"user_id": 9, "user_type": "co"})}
    cover = f"{SB}/avatars/9_company-cover_abcdef012345.jpg"
    assert client.put("/company/cover/9", json={"cover_url": cover}, headers=h).status_code == 200
    assert client.put("/company/cover/9", json={"cover_url": "https://evil.example/c.jpg"}, headers=h).status_code == 400
    assert client.put("/company/cover/9", json={"cover_url": LEGACY}, headers=h).status_code == 200
    body = {"industry": "tech", "cover_url": "data:image/jpeg;base64,/9j/"}
    assert client.put("/company/profile/9", json=body, headers=h).status_code == 400


def test_kyc_upload_returns_private_path_not_public_url(storage):
    r = up({"kind": "kyc-id-front", "data_url": durl("image/jpeg", JPEG)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "url" not in body and "public" not in r.text
    assert body["path"].startswith("kyc-docs/7_kyc-id-front_") and body["path"].endswith(".jpg")
    assert storage.calls[0]["url"].startswith("https://sb.supabase.co/storage/v1/object/kyc-docs/7_kyc-id-front_")


def test_kyc_urls(db):
    h = auth(7)
    good = "kyc-docs/7_kyc-id-front_abcdef012345.jpg"                    # private object path
    assert client.post("/kyc/docs", json={"id_front_url": good}, headers=h).status_code == 200
    assert db["id_front_url"] == good
    public = f"{SB}/kyc-docs/7_kyc-id-front_abcdef012345.jpg"            # public URL of a private bucket
    assert client.post("/kyc/docs", json={"id_front_url": public}, headers=h).status_code == 400
    for bad in ("kyc-docs/7_kyc-selfie_abcdef012345.jpg",               # selfie kind in id field
                "kyc-docs/8_kyc-id-front_abcdef012345.jpg",             # another uid
                "avatars/7_kyc-id-front_abcdef012345.jpg",              # wrong bucket
                "kyc-docs/7_kyc-id-front_../../x.jpg"):                 # traversal
        assert client.post("/kyc/docs", json={"id_front_url": bad}, headers=h).status_code == 400, bad
    assert client.post("/kyc/docs", json={"id_front_url": good, "selfie_url": "https://evil.example/s.jpg"},
                       headers=h).status_code == 400
    # unchanged legacy data: value already stored → still accepted
    assert client.post("/kyc/docs", json={"id_front_url": "data:image/png;base64,AAAA"}, headers=h).status_code == 200


def test_stored_data_url_only_in_dev(db, monkeypatch):
    d = "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert put_profile({"avatar_url": d}).status_code == 400
    monkeypatch.setenv("TW_DEV_UPLOAD", "1")
    assert put_profile({"avatar_url": d}).status_code == 200


@pytest.mark.parametrize("raw", ["https://sb.supabase.co/", " https://sb.supabase.co/ \n"])
def test_upload_then_save_roundtrip_with_untrimmed_supabase_url(db, storage, monkeypatch, raw):
    # Production incident (after PR #549): the URL /upload/image returned must
    # always pass PUT /profile — one normalised base (_supabase_base_url).
    monkeypatch.setenv("SUPABASE_URL", raw)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", " sb_secret_test\n")
    r = up({"kind": "employee-avatar", "data_url": durl("image/jpeg", JPEG)})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://sb.supabase.co/storage/v1/object/public/avatars/7_employee-avatar_")
    assert storage.calls[0]["url"].startswith("https://sb.supabase.co/storage/v1/object/avatars/")
    assert storage.calls[0]["headers"]["apikey"] == "sb_secret_test"
    assert "Authorization" not in storage.calls[0]["headers"]
    assert put_profile({"avatar_url": url}).status_code == 200
    assert db["avatar_url"] == url
