"""
test_certificates_87.py — task 8.7: certificate PDFs of courses / education (docs/rules/certificates.md · SYSTEMS_INDEX §29b).

Real FastAPI app (in-process HTTP) + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and
with TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py SECURITY_TESTS). Supabase Storage faked
(httpx.AsyncClient for upload + sign · server.storage_delete recorded).
  upload: not a PDF (magic) · JavaScript (plain / #xx-escaped / inside a Flate stream) · encrypted · over the limit → 422
  · another user's row → 404 + nothing stored · not emp → 403 · replace deletes the old file · DB failure deletes the new
  file (500) · two uploads at once → one file linked, every other stored file deleted
  view: every cell of the access table (owner · in review · withdrawn · withdrawn + re-applied · rejected before /
  after the period · closed job before / after · hired · company never applied · other user · no token · block both
  ways · owner / company suspended or deleted) · one 404 for «no file» and «no access» · rate before the check · TTL ·
  no-store · certificate_url new → 422, legacy kept + hidden from non-owners · purge deletes the certificate files only
  of the account · export carries has_certificate, never the path.
Run: python -m pytest tests/test_certificates_87.py -q
"""
import base64
import os
import sys
import threading
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import httpx
import pytest
from fastapi.testclient import TestClient

import account_deletion as ad
import account_purge
import auth
import blocks_suspension as bs
import cert_access
import data_export
import server as srv
import tw_limits

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
DAYS = tw_limits.LIMITS["cert_access_after_close_days"]


def _du(b, mime="application/pdf"):
    return f"data:{mime};base64," + base64.b64encode(b).decode()


class FakeStorage:
    stored = []
    lock = threading.Lock()

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def post(self, url, content=None, json=None, headers=None):
        if "/object/sign/" in url:
            name = url.split("/object/sign/", 1)[1]
            FakeStorage.signed.append((name, json))
            return httpx.Response(200, json={"signedURL": f"/object/sign/{name}?token=SIGNED"})
        with FakeStorage.lock:
            FakeStorage.stored.append(url.split("/storage/v1/object/", 1)[1])
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
    yield


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "_RATE_LIMIT", 100_000)
    monkeypatch.setattr(httpx, "AsyncClient", FakeStorage)
    monkeypatch.setenv("SUPABASE_URL", "https://sb.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test")
    monkeypatch.delenv("TW_DEV_UPLOAD", raising=False)
    FakeStorage.stored, FakeStorage.signed = [], []
    deleted = []
    monkeypatch.setattr(srv, "storage_delete",
                        lambda b, n: deleted.append((b, n)) or {"ok": True, "status": 200, "reason": None})
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
    yield deleted


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut="emp"):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', :ut) RETURNING id, tw_id",
                   t={"co": "C", "edu": "T"}.get(ut, "U") + n, n="N" + n, e=f"{n}@t87.test", ut=ut)[0]
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT (user_id) DO NOTHING", u=uid)
    return {"id": int(uid), "tw": tw, "ut": ut}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _course(u, url=None):
    return int(_sql("INSERT INTO courses (user_id, title, certificate_url) VALUES (:u, 'C', :url) RETURNING id",
                    u=u["id"], url=url)[0][0])


def _edu(u):
    return int(_sql("INSERT INTO education (user_id, institution) VALUES (:u, 'I') RETURNING id", u=u["id"])[0][0])


def _path(kind, rid):
    return _sql(f"SELECT certificate_path FROM {cert_access.KINDS[kind]} WHERE id = :id", id=rid)[0][0]


def _up(u, kind, rid, b=PDF, mime="application/pdf"):
    return client.post(f"/{kind}/{rid}/certificate", headers=_h(u), json={"data_url": _du(b, mime)})


def _view(u, kind, rid, hdr=None):
    return client.get(f"/certificates/{kind}/{rid}/view", headers=_h(u) if hdr is None else hdr)


def _with_file(u, kind="course"):
    rid = _course(u) if kind == "course" else _edu(u)
    assert _up(u, kind, rid).status_code == 200
    return rid


def _job(co):
    return int(_sql("INSERT INTO jobs (company_id, title, status, expires_at) "
                    "VALUES (:c, 'J', 'active', NOW() + INTERVAL '30 days') RETURNING id", c=co["id"])[0][0])


def _apply(emp, job):
    return int(auth.apply_job(job, emp["id"])["id"])


def _age_rejection(emp, co, days):
    _sql("UPDATE pipeline_stage_events SET created_at = NOW() - make_interval(days => :d) "
         "WHERE to_stage = 'rejected' AND pipeline_entry_id IN (SELECT id FROM job_pipeline_entries "
         "WHERE candidate_id = :e AND company_id = :c)", d=days, e=emp["id"], c=co["id"])


# ── upload checks ──

@pytest.mark.parametrize("body,mime,code", [
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "application/pdf", "not_pdf"),
    (PDF.replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction 3 0 R"), "application/pdf", "pdf_unsafe"),
    (PDF + b"<< /S /JavaScript /JS (app.alert(1)) >>", "application/pdf", "pdf_unsafe"),
    (PDF + b"<< /S /J#61vaScript >>", "application/pdf", "pdf_unsafe"),
    (PDF + b"<< /Type /EmbeddedFile >>", "application/pdf", "pdf_unsafe"),
    (PDF + b"<< /S /Launch >>", "application/pdf", "pdf_unsafe"),
    (PDF + b"5 0 obj\n<< /Type /ObjStm /Filter /FlateDecode >>\nstream\n"
     + zlib.compress(b"<< /OpenAction 6 0 R >>") + b"\nendstream\n", "application/pdf", "pdf_unsafe"),
    (PDF.replace(b"<< /Root 1 0 R >>", b"<< /Root 1 0 R /Encrypt 9 0 R >>"), "application/pdf", "pdf_encrypted"),
    (b"%PDF-1.4 plain", "image/png", None),   # the declared type decides nothing — real PDF accepted
])
def test_upload_content_check(env, body, mime, code):
    u = _user()
    cid = _course(u)
    r = _up(u, "course", cid, body, mime)
    if code is None:
        assert r.status_code == 200, r.text
        return
    assert r.status_code == 422 and r.json()["error"]["code"] == code, r.text
    assert _path("course", cid) is None and FakeStorage.stored == []


def test_upload_too_large_422(env, monkeypatch):
    monkeypatch.setitem(tw_limits.LIMITS, "cert_max_bytes", 200)
    u = _user()
    cid = _course(u)
    r = _up(u, "course", cid, PDF + b"0" * 200)
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_large"
    assert _up(u, "course", cid, PDF).status_code == 200


def test_upload_other_users_row_404_nothing_written(env):
    a, b = _user(), _user()
    cid, eid = _course(b), _edu(b)
    assert _up(a, "course", cid).status_code == 404
    assert _up(a, "education", eid).status_code == 404
    assert client.delete(f"/course/{cid}/certificate", headers=_h(a)).status_code == 404
    assert FakeStorage.stored == [] and _path("course", cid) is None


@pytest.mark.parametrize("ut", ["co", "edu"])
def test_not_emp_403(env, ut):
    o = _user(ut)
    cid = _course(o)
    assert _up(o, "course", cid).status_code == 403
    assert client.post(f"/course/{o['id']}", headers=_h(o), json={"title": "T"}).status_code == 403
    assert client.post(f"/education/{o['id']}", headers=_h(o), json={"institution": "I"}).status_code == 403
    assert client.put(f"/course/{cid}", headers=_h(o), json={"title": "T"}).status_code == 403
    assert client.delete(f"/course/{cid}", headers=_h(o)).status_code == 403
    assert FakeStorage.stored == []


def test_name_from_server_and_replace_deletes_old(env):
    u = _user()
    eid = _edu(u)
    assert _up(u, "education", eid).status_code == 200
    first = _path("education", eid)
    assert cert_access.name_of(first, u["id"]) and first.startswith(f"cert-docs/{u['id']}_cert_")
    assert _up(u, "education", eid).status_code == 200
    second = _path("education", eid)
    assert second != first and env == [("cert-docs", first.split("/", 1)[1])]
    r = client.delete(f"/education/{eid}/certificate", headers=_h(u))
    assert r.status_code == 200 and _path("education", eid) is None
    assert env[-1] == ("cert-docs", second.split("/", 1)[1])


def test_db_failure_deletes_new_file(env, monkeypatch):
    u = _user()
    cid = _course(u)

    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(srv, "_cert_link", boom)
    r = _up(u, "course", cid)
    assert r.status_code == 500 and "db down" not in r.text
    assert len(FakeStorage.stored) == 1
    assert env == [("cert-docs", FakeStorage.stored[0].split("/", 1)[1])]


def test_two_uploads_at_once_no_orphan(env):
    u = _user()
    cid = _course(u)
    with ThreadPoolExecutor(4) as ex:
        codes = [f.result().status_code for f in [ex.submit(_up, u, "course", cid) for _ in range(4)]]
    assert codes == [200] * 4
    linked = _path("course", cid).split("/", 1)[1]
    stored = {s.split("/", 1)[1] for s in FakeStorage.stored}
    assert len(stored) == 4 and linked in stored
    assert {n for _, n in env} == stored - {linked}


def test_deleting_the_row_deletes_its_file(env):
    u = _user()
    cid = _with_file(u)
    p = _path("course", cid)
    assert client.delete(f"/course/{cid}", headers=_h(u)).status_code == 200
    assert ("cert-docs", p.split("/", 1)[1]) in env


# ── certificate_url (legacy) ──

def test_new_certificate_url_refused_legacy_kept_and_owner_only(env):
    u, co = _user(), _user("co")
    r = client.post(f"/course/{u['id']}", headers=_h(u), json={"title": "T", "certificate_url": "https://x.example/c"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "url_not_allowed"
    cid = _course(u, "https://legacy.example/c")
    ok = client.put(f"/course/{cid}", headers=_h(u), json={"title": "T2", "certificate_url": "https://legacy.example/c"})
    assert ok.status_code == 200 and ok.json()["course"]["certificate_url"] == "https://legacy.example/c"
    assert client.put(f"/course/{cid}", headers=_h(u), json={"title": "T3"}).status_code == 200
    bad = client.put(f"/course/{cid}", headers=_h(u), json={"title": "T", "certificate_url": "https://new.example/c"})
    assert bad.status_code == 422
    assert _sql("SELECT certificate_url FROM courses WHERE id = :i", i=cid)[0][0] == "https://legacy.example/c"
    own = client.get(f"/profile/{u['id']}", headers=_h(u)).json()["profile"]["courses"]
    assert own[0]["certificate_url"] == "https://legacy.example/c"
    for hdr in (_h(co), {}):
        txt = client.get(f"/profile/{u['id']}", headers=hdr).text
        assert "legacy.example" not in txt and "certificate_url" not in txt
    full = client.get(f"/profile/{u['id']}/full", headers=_h(u)).json()["profile"]["courses"]
    assert full[0]["certificate_url"] == "https://legacy.example/c"
    # «استبدل بملف PDF» — the upload replaces the legacy link
    assert _up(u, "course", cid).status_code == 200
    assert _sql("SELECT certificate_url FROM courses WHERE id = :i", i=cid)[0][0] is None


# ── view: access table ──

def _ok(viewer, kind, rid):
    r = _view(viewer, kind, rid)
    return r.status_code == 200


def test_owner_views_ttl_and_no_store(env):
    u = _user()
    cid = _with_file(u)
    r = _view(u, "course", cid)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["expires_in"] == tw_limits.LIMITS["cert_url_ttl_s"]
    assert d["url"].startswith("https://sb.supabase.co/storage/v1/object/sign/cert-docs/")
    assert FakeStorage.signed[-1][1] == {"expiresIn": tw_limits.LIMITS["cert_url_ttl_s"]}
    assert r.headers["cache-control"] == "no-store"
    assert _view(u, "course", 999999999).headers["cache-control"] == "no-store"


def test_company_application_states(env):
    emp, co = _user(), _user("co")
    cid = _with_file(emp)
    assert not _ok(co, "course", cid)                     # never applied
    job = _job(co)
    app = _apply(emp, job)
    assert _ok(co, "course", cid)                         # in review
    auth.withdraw_application(app, emp["id"])
    assert not _ok(co, "course", cid)                     # withdrawn
    auth.apply_job(job, emp["id"])
    assert _ok(co, "course", cid)                         # re-applied → back
    auth.update_application_status(app, "rejected", co["id"])
    assert _ok(co, "course", cid)                         # rejected, within the period
    _age_rejection(emp, co, DAYS + 1)
    assert not _ok(co, "course", cid)                     # rejected, after the period
    auth.update_application_status(app, "hired", co["id"])
    assert _ok(co, "course", cid)                         # hired


def test_closed_job_before_and_after_period(env):
    emp, co = _user(), _user("co")
    eid = _with_file(emp, "education")
    job = _job(co)
    _apply(emp, job)
    auth.set_job_status(job, co["id"], "closed")
    assert _ok(co, "education", eid)
    _sql("UPDATE jobs SET closed_at = NOW() - make_interval(days => :d) WHERE id = :j", d=DAYS + 1, j=job)
    assert not _ok(co, "education", eid)
    # one granting application is enough — another open job of the same company
    _apply(emp, _job(co))
    assert _ok(co, "education", eid)


def test_admin_hidden_and_expired_job(env):
    emp, co = _user(), _user("co")
    cid = _with_file(emp)
    job = _job(co)
    _apply(emp, job)
    _sql("UPDATE jobs SET admin_hidden_at = NOW() - make_interval(days => :d) WHERE id = :j", d=DAYS + 1, j=job)
    assert not _ok(co, "course", cid)
    _sql("UPDATE jobs SET admin_hidden_at = NULL, expires_at = NOW() - INTERVAL '1 day' WHERE id = :j", j=job)
    assert _ok(co, "course", cid)
    _sql("UPDATE jobs SET expires_at = NOW() - make_interval(days => :d) WHERE id = :j", d=DAYS + 1, j=job)
    assert not _ok(co, "course", cid)


def test_other_user_and_no_token(env):
    emp, other = _user(), _user()
    cid = _with_file(emp)
    assert _view(other, "course", cid).status_code == 404
    assert _view(emp, "course", cid, hdr={}).status_code == 401
    assert _view(emp, "nope", cid).status_code == 404


@pytest.mark.parametrize("direction", ["owner_blocks", "company_blocks"])
def test_block_either_way(env, direction):
    emp, co = _user(), _user("co")
    cid = _with_file(emp)
    _apply(emp, _job(co))
    assert _ok(co, "course", cid)
    a, b = (emp, co) if direction == "owner_blocks" else (co, emp)
    bs.block(a["id"], b["id"])
    assert _view(co, "course", cid).status_code == 404
    prof = client.get(f"/profile/{emp['id']}", headers=_h(co))
    assert prof.status_code == 404


@pytest.mark.parametrize("who,how", [("owner", "suspend"), ("owner", "delete"),
                                     ("company", "suspend"), ("company", "delete")])
def test_suspended_or_deleted(env, who, how):
    emp, co = _user(), _user("co")
    cid = _with_file(emp)
    _apply(emp, _job(co))
    assert cert_access.can_view(co["id"], emp["id"])
    target = emp if who == "owner" else co
    if how == "suspend":
        bs.set_suspension(target["id"], True, None, "admin")
    else:
        ad.soft_delete(target["id"], "admin", "admin", None)
    srv._pwd_changed_cache.clear()
    assert not cert_access.can_view(co["id"], emp["id"])
    assert _view(co, "course", cid).status_code in ((404,) if who == "owner" else (401,))
    if who == "owner":
        assert not cert_access.can_view(emp["id"], emp["id"])


def test_same_404_no_file_vs_no_access(env):
    emp, other = _user(), _user()
    no_file = _course(emp)
    with_file = _with_file(emp)
    a = _view(emp, "course", no_file)            # owner, no file
    b = _view(other, "course", with_file)        # file, no access
    c = _view(other, "course", 987654321)        # no row
    assert a.status_code == b.status_code == c.status_code == 404
    assert a.json() == b.json() == c.json()


def test_rate_checked_before_access(env, monkeypatch):
    u = _user()
    cid = _with_file(u)
    calls = []
    real = cert_access.can_view
    monkeypatch.setattr(cert_access, "can_view", lambda *a, **k: calls.append(1) or real(*a, **k))
    hits, _w = tw_limits.RATES["cert_view"]
    for _ in range(hits):
        assert _view(u, "course", cid).status_code == 200
    n = len(calls)
    r = _view(u, "course", 987654321)
    assert r.status_code == 429 and len(calls) == n


def test_upload_rate(env):
    u = _user()
    cid = _course(u)
    hits, _w = tw_limits.RATES["cert_upload"]
    for _ in range(hits):
        assert _up(u, "course", cid).status_code == 200
    assert _up(u, "course", cid).status_code == 429


# ── profile flags ──

def test_profile_flags_per_viewer(env):
    emp, co, other = _user(), _user("co"), _user()
    cid = _with_file(emp)
    _course(emp)
    _apply(emp, _job(co))

    def flags(hdr):
        cs = client.get(f"/profile/{emp['id']}", headers=hdr).json()["profile"]["courses"]
        return {c["id"]: (c["has_certificate"], c["can_view_certificate"]) for c in cs}
    assert flags(_h(emp))[cid] == (True, True)
    assert flags(_h(co))[cid] == (True, True)
    assert flags(_h(other))[cid] == (True, False)
    assert flags({})[cid] == (True, False)
    assert all(v == (False, False) for k, v in flags(_h(co)).items() if k != cid)
    txt = client.get(f"/profile/{emp['id']}", headers=_h(co)).text + \
        client.get(f"/profile/{emp['id']}/full", headers=_h(emp)).text
    assert "cert-docs" not in txt and "certificate_path" not in txt


# ── purge + export ──

def test_purge_deletes_certificate_files_of_the_account_only(env):
    emp, other = _user(), _user()
    cid = _with_file(emp)
    eid = _with_file(emp, "education")
    oc = _with_file(other)
    other_path = _path("course", oc)
    _sql("INSERT INTO courses (user_id, title, certificate_path) VALUES (:u, 'forged', :p)",
         u=emp["id"], p=other_path)                 # someone else's object named in this account's row
    old = dict(account_purge._storage)
    deleted = []
    try:
        account_purge.set_storage(
            lambda b, n: deleted.append((b, n)) or {"ok": True, "status": 200},
            lambda b, prefix: [f"{emp['id']}_cert_{'a' * 12}.pdf"] if b == "cert-docs" else [])
        assert account_purge.delete_files(emp["id"]) is None
    finally:
        account_purge._storage.update(old)
    names = {n for b, n in deleted if b == "cert-docs"}
    assert names == {_path("course", cid).split("/", 1)[1], _path("education", eid).split("/", 1)[1],
                     f"{emp['id']}_cert_{'a' * 12}.pdf"}


def test_export_has_flag_never_path(env):
    emp = _user()
    _with_file(emp)
    _with_file(emp, "education")
    out = data_export.build_export(emp["id"])
    assert out["profile"]["courses"][0]["has_certificate"] is True
    assert out["profile"]["education"][0]["has_certificate"] is True
    assert "cert-docs" not in repr(out) and "certificate_path" not in repr(out)
