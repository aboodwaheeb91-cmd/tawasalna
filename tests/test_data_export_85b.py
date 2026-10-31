"""
test_data_export_85b.py — task 8.5b: «تنزيل بياناتي» (docs/rules/data-export.md · SYSTEMS_INDEX §1e).

Real FastAPI app (in-process HTTP) + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped,
and with TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py SECURITY_TESTS):
  wrong / missing password → refused, no data · the rate bucket answers 429 BEFORE bcrypt · no token / suspended /
  deleted → 401 · no-store on every reply · users A / B / company C with sentinel values: A's file carries none of
  B's private values (B's messages · the company's notes about A) and C's file carries no applicant data (a count
  per job only) · no forbidden key at any depth · KYC links: the caller's own valid paths only, lifetime ≤ the limit,
  nothing taken from the request · no documents → empty list.
Run: python -m pytest tests/test_data_export_85b.py -q
"""
import json
import os
import sys
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import httpx
import pytest

import account_deletion as ad
import auth
import blocks_suspension as bs
import server as srv
import tw_limits
import tw_settings
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    _env, _migrated, client, db)

PW = "Passw0rd-85b!"
# The test's own list (independent of data_export.FORBIDDEN_KEYS) — must never appear as a key, at any depth.
FORBIDDEN = {"password", "password_hash", "session_version", "sv", "token", "jwt", "email_code", "phone_code",
             "email_code_target", "phone_code_target", "email_code_expires_at", "phone_code_attempts",
             "otp", "token_hash", "mfa_secret", "mfa_secret_enc", "secret", "deleted_at", "deleted_by",
             "deleted_kind", "deleted_reason", "suspended_at", "suspended_reason", "suspended_by", "admin_note",
             "admin_hidden_reason", "notes", "ip", "ip_address", "id_front_url", "selfie_url"}


class FakeStorage:
    calls = []

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def post(self, url, content=None, json=None, headers=None):
        FakeStorage.calls.append((url, json))
        name = url.split("/object/sign/", 1)[1]
        return httpx.Response(200, json={"signedURL": f"/object/sign/{name}?token=SIGNED"})


@pytest.fixture(autouse=True)
def _env85b(monkeypatch, _env):
    monkeypatch.setattr(srv, "_asyncpg_pool", None)
    FakeStorage.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeStorage)
    monkeypatch.setenv("SUPABASE_URL", "https://sb.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test")
    srv._pwd_changed_cache.clear()
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut, tag):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, :h, :ut) RETURNING id, tw_id",
                   t=("C" if ut == "co" else "U") + n, n="Name" + tag + n, e=f"{tag.lower()}{n}@t85b.test",
                   h=auth.hash_password(PW), ut=ut)[0]
    phone = "+9627" + str(abs(hash(n)))[:8]
    _sql("INSERT INTO profiles (user_id, phone, headline) VALUES (:u, :p, :h) "
         "ON CONFLICT (user_id) DO UPDATE SET phone = :p, headline = :h", u=uid, p=phone, h="HEAD_" + tag + n)
    return {"id": int(uid), "tw": tw, "ut": ut, "email": f"{tag.lower()}{n}@t85b.test", "phone": phone,
            "headline": "HEAD_" + tag + n, "name": "Name" + tag + n}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _export(u, pw=PW, hdr=None):
    return client.post("/me/export", headers=_h(u) if hdr is None else hdr, json={"password": pw})


def _kyc(u, pw=PW, hdr=None, **extra):
    return client.post("/me/export/kyc-docs", headers=_h(u) if hdr is None else hdr, json={"password": pw, **extra})


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k).lower())
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


# ── password + rate ──
def test_wrong_or_missing_password_refused_without_data(db):
    a = _user("emp", "A")
    for pw in ("wrong-password", ""):
        r = _export(a, pw)
        assert r.status_code == 422, r.text
        assert r.json()["error"]["field"] == "password"
        assert a["email"] not in r.text and a["phone"] not in r.text and a["tw"] not in r.text
        assert "attachment" not in r.headers.get("content-disposition", "")
        assert r.headers["cache-control"] == "no-store"
    r = _kyc(a, "wrong-password")
    assert r.status_code == 422 and "docs" not in r.text
    assert FakeStorage.calls == []


@pytest.mark.parametrize("path,rate", [("/me/export", "data_export"), ("/me/export/kyc-docs", "data_export_kyc")])
def test_rate_limit_429_before_bcrypt(db, monkeypatch, path, rate):
    a = _user("emp", "A")
    calls = []
    real = srv.check_user_password
    monkeypatch.setattr(srv, "check_user_password", lambda uid, pw: calls.append(uid) or real(uid, pw))
    limit = tw_settings.rate(rate)[0]
    for i in range(limit):
        r = client.post(path, headers=_h(a), json={"password": PW if i == 0 else "wrong"})
        assert r.status_code in (200, 422), r.text
    r = client.post(path, headers=_h(a), json={"password": PW})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert len(calls) == limit                      # the refused call never reached bcrypt
    assert a["email"] not in r.text


# ── session gate ──
def test_no_token_suspended_deleted_401(db):
    for path in ("/me/export", "/me/export/kyc-docs"):
        r = client.post(path, json={"password": PW})
        assert r.status_code == 401 and r.headers["cache-control"] == "no-store"
    s, d = _user("emp", "S"), _user("emp", "D")
    bs.set_suspension(s["id"], True, "r", "owner")
    ad.soft_delete(d["id"], "owner", "admin")
    srv._pwd_changed_cache.clear()
    for u in (s, d):
        for r in (_export(u), _kyc(u)):
            assert r.status_code == 401, r.text
            assert u["email"] not in r.text


# ── content + isolation ──
def test_export_file_has_own_data_only(db):
    a, b, c = _user("emp", "A"), _user("emp", "B"), _user("co", "C")
    _sql("INSERT INTO experience (user_id, title, company) VALUES (:u, 'EXP_A_TITLE', 'ACME')", u=a["id"])
    _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:a, :b, 'MSG_FROM_A')", a=a["id"], b=b["id"])
    _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:b, :a, 'MSG_FROM_B_SENTINEL')",
         a=a["id"], b=b["id"])
    _sql("INSERT INTO profile_follows (follower_id, followed_id) VALUES (:b, :a)", a=a["id"], b=b["id"])
    job = _sql("INSERT INTO jobs (company_id, title, status) VALUES (:c, 'JOB_C_TITLE', 'active') RETURNING id",
               c=c["id"])[0][0]
    _sql("INSERT INTO job_applications (job_id, user_id, status, cover_letter) "
         "VALUES (:j, :a, 'interview', 'COVER_A')", j=job, a=a["id"])
    _sql("INSERT INTO company_saved_candidates (company_id, candidate_id, notes) VALUES (:c, :a, 'CO_NOTE_SENTINEL')",
         c=c["id"], a=a["id"])
    _sql("INSERT INTO candidate_bank_notes (company_id, candidate_id, body) VALUES (:c, :a, 'BANK_NOTE_SENTINEL')",
         c=c["id"], a=a["id"])
    _sql("INSERT INTO appointments (job_id, company_id, applicant_id, created_by, status, mode, notes, scheduled_at) "
         "VALUES (:j, :c, :a, :c, 'confirmed', 'online', 'CO_APPT_NOTE_SENTINEL', NOW() + interval '2 days')",
         j=job, c=c["id"], a=a["id"])
    _sql("INSERT INTO kyc_submissions (user_id, step, status, email_code, admin_note, reject_reason, id_front_url) "
         "VALUES (:a, 'rejected', 'rejected', '654321', 'ADMIN_NOTE_SENTINEL', 'REASON_FOR_A', :p)",
         a=a["id"], p=f"kyc-docs/{a['id']}_kyc-id-front_0123456789ab.jpg")
    pw_hash = _sql("SELECT password_hash FROM users WHERE id = :a", a=a["id"])[0][0]

    r = _export(a)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].startswith("attachment;")
    text, f = r.text, r.json()
    # own data
    assert f["account"]["email"] == a["email"] and f["account"]["phone"] == a["phone"]
    assert f["account"]["tw_id"] == a["tw"] and f["account"]["user_type"] == "emp"
    assert f["profile"]["experience"][0]["title"] == "EXP_A_TITLE"
    assert [m["content"] for m in f["messages_sent"]] == ["MSG_FROM_A"]
    assert f["messages_sent"][0]["conversation_with_tw_id"] == b["tw"]
    assert f["applications"][0]["status"] == "in_review"            # applicant view — never 'interview'
    assert f["applications"][0]["company_tw_id"] == c["tw"]
    assert f["followers"] == [{"tw_id": b["tw"], "full_name": b["name"], "created_at": f["followers"][0]["created_at"]}]
    assert f["kyc"]["status"] == "rejected" and f["kyc"]["reject_reason"] == "REASON_FOR_A"
    assert f["appointments"][0]["status"] == "confirmed" and f["appointments"][0]["my_notes"] is None
    # nothing private of anyone else · no secret · no admin note · no KYC path
    for v in ("MSG_FROM_B_SENTINEL", b["email"], b["phone"], b["headline"], "CO_NOTE_SENTINEL",
              "BANK_NOTE_SENTINEL", "CO_APPT_NOTE_SENTINEL", "ADMIN_NOTE_SENTINEL", "654321", pw_hash,
              "kyc-docs/"):
        assert v not in text, v
    assert not (_keys(f) & FORBIDDEN), _keys(f) & FORBIDDEN

    # company file: its job + a count only — no applicant data
    r = _export(c)
    assert r.status_code == 200, r.text
    fc = r.json()
    assert fc["company"]["jobs"][0]["title"] == "JOB_C_TITLE" and fc["company"]["jobs"][0]["applicants_count"] == 1
    for v in (a["name"], a["email"], a["phone"], a["tw"], a["headline"], "COVER_A", "EXP_A_TITLE", "MSG_FROM_A"):
        assert v not in r.text, v
    assert not (_keys(fc) & FORBIDDEN)


# ── KYC document links ──
def test_kyc_links_own_paths_only_short_lived(db):
    a, b, n = _user("emp", "A"), _user("emp", "B"), _user("emp", "N")
    own = f"kyc-docs/{a['id']}_kyc-id-front_0123456789ab.jpg"
    foreign = f"kyc-docs/{b['id']}_kyc-selfie_0123456789ab.jpg"     # a row pointing at someone else's file
    _sql("INSERT INTO kyc_submissions (user_id, step, status, id_front_url, selfie_url) "
         "VALUES (:a, 'review', 'pending', :o, :f)", a=a["id"], o=own, f=foreign)
    _sql("INSERT INTO kyc_submissions (user_id, step, status, id_front_url) VALUES (:b, 'review', 'pending', :p)",
         b=b["id"], p=f"kyc-docs/{b['id']}_kyc-id-front_0123456789ab.jpg")

    r = _kyc(a, name=f"{b['id']}_kyc-id-front_0123456789ab.jpg", path=foreign)   # request names are ignored
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    d = r.json()["data"]
    ttl = tw_limits.LIMITS["data_export_kyc_url_ttl_s"]
    assert d["expires_in"] <= ttl
    by_kind = {x["kind"]: x for x in d["docs"]}
    assert by_kind["id_front"]["url"].startswith(
        f"https://sb.supabase.co/storage/v1/object/sign/kyc-docs/{a['id']}_kyc-id-front_")
    assert by_kind["selfie"]["url"] is None and by_kind["selfie"]["reason"] == "invalid_path"
    assert [u for u, _ in FakeStorage.calls] == [
        f"https://sb.supabase.co/storage/v1/object/sign/{own}"]           # only the caller's own valid path
    assert all(0 < body["expiresIn"] <= ttl for _, body in FakeStorage.calls)
    assert f"{b['id']}_kyc-id-front" not in r.text

    FakeStorage.calls = []
    r = _kyc(n)                                                        # no documents → empty list, nothing signed
    assert r.status_code == 200 and r.json()["data"]["docs"] == [] and FakeStorage.calls == []
