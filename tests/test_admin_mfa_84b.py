"""Task 8.4b — admin staff accounts + two-step admin login (docs/rules/admin-staff.md · SYSTEMS_INDEX §25h).

  A. TOTP (no DB): RFC 6238 SHA-1 test vectors · ±1 step · format · secret encryption.
  B. Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped):
     owner: no MFA → bind → recovery codes → token · then the password alone never gives a token ·
       a code is accepted once · a recovery code works once · ADMIN_MFA_RESET (today only) re-binds and ends
       the old sessions · ticket ≠ admin token
     staff (seeded): two steps · perms from the DB on every request (deny over allow · owner-only never ·
       suspend / sv / perms change → the next request with the same token) · email hidden without users.email.view
     same 401 for every failure · 429 per account on both steps · audit rows name the account.
Run: python -m pytest tests/test_admin_mfa_84b.py -q
"""
import os, sys, uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import admin_staff
import auth
import server as srv
import tw_settings

client = TestClient(srv.app)
LOGIN = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN + "/login"
PASSWORD = "owner-pass-84b-" + "p" * 30
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
T0 = 1_900_000_000.0          # fixed TOTP clock (step aligned below)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", "test-admin-secret-84b-" + "s" * 32)
    monkeypatch.setenv("ADMIN_MFA_KEY", "test-mfa-key-84b-" + "k" * 32)
    monkeypatch.delenv("ADMIN_MFA_RESET", raising=False)
    clock = {"t": T0}
    monkeypatch.setattr(admin_staff, "_now", lambda: clock["t"])
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield clock
    srv._rate_store.clear()


# ── A. TOTP ──
def test_rfc6238_sha1_vectors():
    key = b"12345678901234567890"
    for t, want in ((59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
                    (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")):
        assert admin_staff.totp_code(key, t // 30, digits=8) == want
        assert admin_staff.totp_code(key, t // 30) == want[-6:]


def test_match_step_window_and_format():
    secret = admin_staff.new_secret()
    key = admin_staff._b32(secret)
    step = int(T0 // 30)
    for d in (-1, 0, 1):
        assert admin_staff.match_step(secret, admin_staff.totp_code(key, step + d), T0) == step + d
    for d in (-2, 2):
        assert admin_staff.match_step(secret, admin_staff.totp_code(key, step + d), T0) is None
    assert admin_staff.match_step(secret, "12a456", T0) is None
    assert admin_staff.match_step(secret, "1234567", T0) is None


def test_secret_encrypted_with_key(monkeypatch):
    enc = admin_staff.encrypt("JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in enc and admin_staff.decrypt(enc) == "JBSWY3DPEHPK3PXP"
    monkeypatch.setenv("ADMIN_MFA_KEY", "another-key-" + "z" * 32)
    assert admin_staff.decrypt(enc) is None
    monkeypatch.setenv("ADMIN_MFA_KEY", "short")
    assert client.post(LOGIN, json={"password": PASSWORD}).status_code == 503


def test_effective_perms_rule():
    eff = admin_staff.effective_perms(["users.view", "stats.view"], ["settings.edit", "audit.view", "*"], ["stats.view"])
    assert eff == {"users.view", "settings.edit"}


# ── B. login flows (PostgreSQL) ──
def _db_params():
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    return dict(host=host, port=int(port), user=user, password=pw, database=name.split("?")[0])


@pytest.fixture(scope="module")
def _migrated():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


@pytest.fixture
def db(_migrated):
    _sql("UPDATE admin_owner_mfa SET secret_enc = NULL, enabled_at = NULL, last_step = NULL, "
         "session_version = 1, reset_on = NULL WHERE id = 1")
    _sql("DELETE FROM admin_recovery_codes")
    _sql("DELETE FROM admin_staff")
    _sql("DELETE FROM admin_roles")
    _sql("DELETE FROM admin_audit_log")
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _code(secret, d=0):
    return admin_staff.totp_code(admin_staff._b32(secret), int(T0 // 30) + d)


def _hdr(token):
    return {"X-Admin-Token": token}


def _enroll_owner(d=0):
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.status_code == 200 and r.json()["step"] == "enroll" and "token" not in r.json()
    secret, ticket = r.json()["secret"], r.json()["ticket"]
    r = client.post(LOGIN, json={"ticket": ticket, "code": _code(secret, d)})
    assert r.status_code == 200, r.text
    return secret, r.json()["token"], r.json()["recovery_codes"]


def test_owner_binds_then_password_alone_never_gives_a_token(db):
    r = client.post(LOGIN, json={"password": PASSWORD})
    body = r.json()
    assert body["step"] == "enroll" and "token" not in body
    assert body["otpauth_uri"].startswith("otpauth://totp/") and "secret=" + body["secret"] in body["otpauth_uri"]
    stored = _sql("SELECT secret_enc FROM admin_owner_mfa WHERE id = 1")[0][0]
    assert stored and body["secret"] not in stored                     # encrypted at rest
    # the ticket is not an admin token
    assert client.get("/admin/settings", headers=_hdr(body["ticket"])).status_code == 401
    assert client.post(LOGIN, json={"ticket": body["ticket"], "code": "000000"}).status_code == 401
    r = client.post(LOGIN, json={"ticket": body["ticket"], "code": _code(body["secret"])})
    assert r.status_code == 200
    codes, token = r.json()["recovery_codes"], r.json()["token"]
    assert len(codes) == 10 and len(set(codes)) == 10
    assert client.get("/admin/settings", headers=_hdr(token)).status_code == 200
    assert client.get("/admin/audit", headers=_hdr(token)).status_code == 200      # owner = "*" (owner-only perms)
    assert srv._admin_jwt_claims(token)["perms"] == ["*"]
    hashes = repr(_sql("SELECT code_hash FROM admin_recovery_codes"))
    assert all(c not in hashes for c in codes)                        # SHA-256 only
    # now: password → step mfa (no token, no secret) · the bind code is never accepted again
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.json()["step"] == "mfa" and "token" not in r.json() and "secret" not in r.json()
    ticket = r.json()["ticket"]
    assert client.post(LOGIN, json={"ticket": ticket, "code": _code(body["secret"])}).status_code == 401
    r = client.post(LOGIN, json={"ticket": ticket, "code": _code(body["secret"], 1)})
    assert r.status_code == 200 and "recovery_remaining" not in r.json()
    assert client.post(LOGIN, json={"ticket": ticket, "code": _code(body["secret"], 1)}).status_code == 401  # ticket used
    # a fresh ticket each time from here (one token per ticket — task 8.4c-0)
    ticket = client.post(LOGIN, json={"password": PASSWORD}).json()["ticket"]
    assert client.post(LOGIN, json={"ticket": ticket, "code": _code(body["secret"], 1)}).status_code == 401  # replay
    # recovery code: once, and the reply says how many are left
    r = client.post(LOGIN, json={"ticket": ticket, "code": codes[0].upper()})
    assert r.status_code == 200 and r.json()["recovery_remaining"] == 9
    assert client.post(LOGIN, json={"ticket": ticket, "code": codes[0]}).status_code == 401


def test_admin_mfa_reset_today_only(db, monkeypatch):
    _, old_token, _ = _enroll_owner()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    monkeypatch.setenv("ADMIN_MFA_RESET", tomorrow)                     # not today → nothing
    assert client.post(LOGIN, json={"password": PASSWORD}).json()["step"] == "mfa"
    assert client.get("/admin/settings", headers=_hdr(old_token)).status_code == 200
    monkeypatch.setenv("ADMIN_MFA_RESET", datetime.now(timezone.utc).date().isoformat())
    bad = client.post(LOGIN, json={"password": "wrong-" + "w" * 30})  # wrong password → no reset
    assert bad.status_code == 401
    assert _sql("SELECT enabled_at IS NOT NULL FROM admin_owner_mfa")[0][0] is True
    r = client.post(LOGIN, json={"password": PASSWORD})
    assert r.json()["step"] == "enroll"
    assert client.get("/admin/settings", headers=_hdr(old_token)).status_code == 401   # old sessions over
    assert _sql("SELECT COUNT(*) FROM admin_recovery_codes WHERE subject = 'owner'")[0][0] == 0
    secret = r.json()["secret"]
    r = client.post(LOGIN, json={"ticket": r.json()["ticket"], "code": _code(secret)})
    new_token = r.json()["token"]
    # same day, variable still set → not applied twice
    assert client.post(LOGIN, json={"password": PASSWORD}).json()["step"] == "mfa"
    assert client.get("/admin/settings", headers=_hdr(new_token)).status_code == 200
    assert ("owner", "admin_mfa_reset") in [tuple(x) for x in _sql("SELECT actor, action FROM admin_audit_log")]


def _staff(role_perms=(), allow=(), deny=(), status="active", mfa=True, email=None):
    rid = _sql("INSERT INTO admin_roles (name, perms) VALUES (:n, :p) RETURNING id",
               n="role-" + uuid.uuid4().hex[:8], p=list(role_perms))[0][0]
    secret = admin_staff.new_secret()
    email = email or f"staff{uuid.uuid4().hex[:8]}@t.test"
    sid = _sql("INSERT INTO admin_staff (email, name, password_hash, role_id, allow_perms, deny_perms, status, "
               "mfa_secret_enc, mfa_enabled_at) VALUES (:e, 'S', :h, :r, :a, :d, :s, :m, "
               + ("NOW()" if mfa else "NULL") + ") RETURNING id",
               e=email, h=auth.hash_password("staff-pass-1"), r=rid, a=list(allow), d=list(deny), s=status,
               m=admin_staff.encrypt(secret))[0][0]
    return {"id": sid, "email": email, "secret": secret, "role": rid}


def _staff_login(st, d=0):
    r = client.post(LOGIN, json={"email": st["email"].upper(), "password": "staff-pass-1"})
    assert r.status_code == 200 and r.json()["step"] == "mfa" and "token" not in r.json()
    r = client.post(LOGIN, json={"ticket": r.json()["ticket"], "code": _code(st["secret"], d)})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_staff_perms_from_db_every_request(db):
    st = _staff(role_perms=["users.view", "stats.view"], allow=["settings.edit", "audit.view"], deny=["stats.view"])
    tok = _staff_login(st)
    c = srv._admin_jwt_claims(tok)
    assert c["sub"] == f"staff:{st['id']}" and c["role"] == "staff" and c["perms"] == []
    h = _hdr(tok)
    assert client.get("/admin/users", headers=h).status_code == 200          # role
    assert client.get("/admin/settings", headers=h).status_code == 200       # allow
    assert client.get("/admin/stats/summary", headers=h).status_code == 403  # deny over role
    assert client.get("/admin/audit", headers=h).status_code == 403          # owner-only, even in allow
    _sql("UPDATE admin_staff SET deny_perms = ARRAY['users.view'] WHERE id = :i", i=st["id"])
    assert client.get("/admin/users", headers=h).status_code == 403          # next request
    _sql("UPDATE admin_roles SET perms = ARRAY['stats.view'] WHERE id = :i", i=st["role"])
    _sql("UPDATE admin_staff SET deny_perms = '{}' WHERE id = :i", i=st["id"])
    assert client.get("/admin/stats/summary", headers=h).status_code == 200
    _sql("UPDATE admin_staff SET status = 'suspended' WHERE id = :i", i=st["id"])
    assert client.get("/admin/stats/summary", headers=h).status_code == 401
    _sql("UPDATE admin_staff SET status = 'active', session_version = session_version + 1 WHERE id = :i", i=st["id"])
    assert client.get("/admin/stats/summary", headers=h).status_code == 401
    assert client.post(LOGIN, json={"email": st["email"], "password": "staff-pass-1"}).status_code == 200
    rows = [tuple(x) for x in _sql("SELECT actor, action, status FROM admin_audit_log WHERE action LIKE 'admin_login%'")]
    assert (f"staff:{st['id']}", "admin_login", 200) in rows and (f"staff:{st['id']}", "admin_login_mfa", 200) in rows


def test_staff_email_hidden_without_view(db):
    n = uuid.uuid4().hex[:10]
    email = f"seen{n}@t.test"
    _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES (:t, :n, :e, 'x', 'emp')",
         t="U" + n, n="Name" + n, e=email)
    st = _staff(role_perms=["users.view"])
    h = _hdr(_staff_login(st))
    r = client.get("/admin/users", params={"q": "Name" + n}, headers=h)
    assert r.status_code == 200 and "Name" + n in r.text and email not in r.text
    _sql("UPDATE admin_staff SET allow_perms = ARRAY['users.email.view'] WHERE id = :i", i=st["id"])
    assert email in client.get("/admin/users", params={"q": "Name" + n}, headers=h).text


def test_same_401_for_every_failure(db):
    active = _staff(role_perms=["users.view"])
    susp = _staff(role_perms=["users.view"], status="suspended")
    nomfa = _staff(role_perms=["users.view"], mfa=False)
    replies = [client.post(LOGIN, json=b) for b in (
        {"email": "nobody@t.test", "password": "staff-pass-1"},
        {"email": active["email"], "password": "wrong-pass"},
        {"email": susp["email"], "password": "staff-pass-1"},
        {"email": nomfa["email"], "password": "staff-pass-1"},
        {"password": "wrong-" + "w" * 30})]
    assert {(r.status_code, r.text) for r in replies} == {(401, replies[0].text)}
    actors = [x[0] for x in _sql("SELECT actor FROM admin_audit_log ORDER BY id")]
    assert actors == ["-", f"staff:{active['id']}", f"staff:{susp['id']}", f"staff:{nomfa['id']}", "owner"]


def test_rate_limits_both_steps(db):
    st = _staff(role_perms=["users.view"])
    for _ in range(5):
        assert client.post(LOGIN, json={"email": st["email"], "password": "nope"}).status_code == 401
    assert client.post(LOGIN, json={"email": st["email"], "password": "staff-pass-1"}).status_code == 429
    srv._rate_store.clear()
    ticket = client.post(LOGIN, json={"email": st["email"], "password": "staff-pass-1"}).json()["ticket"]
    for _ in range(5):
        assert client.post(LOGIN, json={"ticket": ticket, "code": "000000"}).status_code == 401
    assert client.post(LOGIN, json={"ticket": ticket, "code": _code(st["secret"])}).status_code == 429
