"""Task 8.4c-1 — admin session perms (/admin/me) + owner step-up + new owner recovery codes
(docs/rules/admin-staff.md rules 11–13 · SYSTEMS_INDEX §25h).

Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with
TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py):
  A. /admin/me: owner ["*"] · staff = the effective perms, changed on the same token after allow / deny ·
     no email / phone / sv in the JSON · no token 401 · a site user JWT 401.
  B. every OWNER_ONLY write route + the CSV export: owner without a grant → 428 · with a valid grant → passes.
     Bad grants (expired · other token · old sv · edited · other secret · grant as the admin token · ticket as
     a grant) → refused · GET /admin/audit + /admin/errors need no grant · a grant works for several requests.
  C. /admin/step-up: one TOTP code ×10 in parallel → one grant · one recovery code in parallel → one grant +
     crossed out · 30 wrong codes in parallel → 401s ≤ admin_mfa_acct, the rest 429 · staff 403 · audit rows
     admin_step_up (success + failure) without the code.
  D. new owner recovery codes: 10 · the old ones dead at login and step-up · the new ones work · two parallel
     calls leave ONE valid set · no-store.
  E. the grant and the codes never in logs / admin_audit_log.
Run: python -m pytest tests/test_admin_stepup_84c.py -q
"""
import base64, json, os, re, sys, time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import admin_perms
import admin_staff
import server as srv
import tw_limits
from test_admin_perms_84a import ROUTE_PERMS, _SECURITY_KEY
from test_admin_mfa_84b import PASSWORD, _sql
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db · slow)
    ADMIN_SECRET, _burst, _code, _enroll_owner, _env, _hdr, _limit, _login, _migrated, _staff, _staff_token,
    _ticket, client, db, slow)

STEPUP = "/admin/step-up"
CODES = "/admin/owner/recovery-codes"


def _step_up(token, code):
    return client.post(STEPUP, json={"code": code}, headers=_hdr(token))


def _grant_hdr(token, grant):
    return {"X-Admin-Token": token, "X-Admin-Stepup": grant}


def _owner_grant(clock):
    owner = _enroll_owner(clock)
    r = _step_up(owner["token"], _code(owner["secret"], clock))
    assert r.status_code == 200 and r.json()["expires_in"] == 300, r.text
    return owner, r.json()["grant"]


def _claims_of(token):
    return json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))


def _keys(obj):
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


# ── A. /admin/me ──
def test_me_owner_and_staff(db, _env):
    owner = _enroll_owner(_env)
    r = client.get("/admin/me", headers=_hdr(owner["token"]))
    assert r.status_code == 200 and r.json() == {"kind": "owner", "name": None, "perms": ["*"],
                                                 "owner_only": sorted(admin_perms.OWNER_ONLY)}, r.text

    st = _staff(role_perms=["users.view", "stats.view"])
    tok = _staff_token(st, _env)
    me = client.get("/admin/me", headers=_hdr(tok))
    assert me.status_code == 200 and me.json()["kind"] == "staff"
    assert sorted(me.json()["perms"]) == ["stats.view", "users.view"]
    assert not {k for k in _keys(me.json()) if admin_perms.is_email_key(k) or admin_perms.is_phone_key(k)
                or k in ("sv", "session_version", "secret", "token")}
    assert st["email"] not in me.text and "@" not in me.text
    # the same token, after allow / deny in the DB
    _sql("UPDATE admin_staff SET allow_perms = ARRAY['kyc.review', 'audit.view'] WHERE id = :i", i=st["id"])
    assert sorted(client.get("/admin/me", headers=_hdr(tok)).json()["perms"]) == ["kyc.review", "stats.view", "users.view"]
    _sql("UPDATE admin_staff SET deny_perms = ARRAY['users.view'] WHERE id = :i", i=st["id"])
    assert sorted(client.get("/admin/me", headers=_hdr(tok)).json()["perms"]) == ["kyc.review", "stats.view"]


def test_me_without_admin_session_401(db):
    assert client.get("/admin/me").status_code == 401
    uid = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES "
               "('U84C1ME', 'Me', 'me84c1@t.test', 'x', 'emp') ON CONFLICT DO NOTHING RETURNING id")
    uid = uid[0][0] if uid else _sql("SELECT id FROM users WHERE tw_id = 'U84C1ME'")[0][0]
    user_jwt = srv._jwt_encode({"user_id": uid, "user_type": "emp", "tw_id": "U84C1ME", "sv": 0})
    assert client.get("/admin/me", headers=_hdr(user_jwt)).status_code == 401
    assert client.post(STEPUP, json={"code": "123456"}, headers=_hdr(user_jwt)).status_code == 401


# ── B. owner-only writes + export need the grant ──
def _step_up_routes():
    out = [(m, p, perm) for (m, p), perm in ROUTE_PERMS.items()
           if perm in admin_perms.OWNER_ONLY and (m != "GET" or p == "/admin/users/export")]
    out += [("PUT", "/admin/settings/{key}", "settings.security"),
            ("POST", "/admin/settings/{key}/reset", "settings.security")]
    return out


_OWNER_BODIES = {"/admin/user/{user_id}/type": {"user_type": "emp"}, "/admin/user/{user_id}/password": {"password": "x"},
                 "/admin/user/{user_id}/email": {"email": "bad"}, "/admin/email": {"site_url": "javascript:x"},
                 "/admin/settings/{key}": {"value": "x"}}
_QUERY = {"/admin/pipeline/backfill": "?dry_run=true", "/admin/maintenance/migrate-data-images": "?dry_run=1"}


def _route_url(path):
    url = re.sub(r"\{(\w+)[^}]*\}", lambda m: _SECURITY_KEY if m.group(1) == "key" else "999999999", path)
    return url + _QUERY.get(path, "")


def test_step_up_route_list_is_complete():
    assert ("POST", CODES, "settings.security") in _step_up_routes()
    assert ("GET", "/admin/users/export", "users.export") in _step_up_routes()
    assert not [r for r in _step_up_routes() if r[1] in ("/admin/audit", "/admin/errors")]


@pytest.mark.parametrize("method,path,perm", _step_up_routes())
def test_owner_only_write_needs_grant(db, _env, method, path, perm):
    owner, grant = _owner_grant(_env)
    url, body = _route_url(path), _OWNER_BODIES.get(path, {})
    r = client.request(method, url, json=body, headers=_hdr(owner["token"]))
    assert (r.status_code, r.json()) == (428, {"error": "step_up_required"}), (r.status_code, r.text[:200])
    r = client.request(method, url, json=body, headers=_grant_hdr(owner["token"], grant))
    assert r.status_code not in (401, 403, 428) and r.status_code < 500, (r.status_code, r.text[:200])


def test_bad_grants_refused(db, _env):
    owner, grant = _owner_grant(_env)
    tok = owner["token"]
    other_tok = _login({"ticket": _ticket({"password": PASSWORD}), "code": _code(owner["secret"], _env)}).json()["token"]
    c = _claims_of(grant)
    now = int(time.time())
    h, p, s = grant.split(".")

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    bad = {
        "expired": srv._jwt_sign(dict(c, iat=now - 400, exp=now - 100), ADMIN_SECRET),
        "too long": srv._jwt_sign(dict(c, exp=now + 3600), ADMIN_SECRET),
        "other token": srv._admin_step_up_issue("owner", c["sv"], other_tok),
        "old sv": srv._admin_step_up_issue("owner", c["sv"] - 1, tok),
        "edited payload": h + "." + b64(dict(c, tok=srv._admin_token_digest(other_tok))) + "." + s,
        "one byte": h + "." + p + "." + ("A" if s[0] != "A" else "B") + s[1:],
        "other secret": srv._jwt_sign(c, "another-secret-" + "z" * 40),
        "admin aud": srv._jwt_sign(dict(c, aud=srv._ADMIN_JWT_AUD), ADMIN_SECRET),
        "ticket": _ticket({"password": PASSWORD}),
        "admin token": tok,
    }
    url = "/admin/user/999999999"
    for name, g in bad.items():
        assert client.delete(url, headers=_grant_hdr(tok, g)).status_code == 428, name
    # the grant of token A on token B
    assert client.delete(url, headers=_grant_hdr(other_tok, grant)).status_code == 428
    # the grant is never an admin token
    assert client.get("/admin/me", headers=_hdr(grant)).status_code == 401
    assert client.delete(url, headers=_grant_hdr(grant, grant)).status_code == 401
    # the good one works — for several requests
    for _ in range(3):
        assert client.delete(url, headers=_grant_hdr(tok, grant)).status_code == 404
    # sv bumped → the token itself is dead
    _sql("UPDATE admin_owner_mfa SET session_version = session_version + 1 WHERE id = 1")
    assert client.delete(url, headers=_grant_hdr(tok, grant)).status_code == 401


def test_reads_need_no_grant(db, _env):
    owner = _enroll_owner(_env)
    for p in ("/admin/audit", "/admin/errors"):
        assert client.get(p, headers=_hdr(owner["token"])).status_code == 200, p


# ── C. /admin/step-up ──
def test_one_totp_code_in_parallel_one_grant(db, slow, _env, monkeypatch):
    monkeypatch.setitem(tw_limits.RATES, "admin_mfa_acct", (100, 900))   # every request reaches the code check
    owner = _enroll_owner(_env)
    code = _code(owner["secret"], _env)
    codes = [r.status_code for r in _burst(10, lambda i: _step_up(owner["token"], code))]
    assert codes.count(200) == 1 and codes.count(401) == 9, codes


def test_one_recovery_code_in_parallel_one_grant(db, slow, _env, monkeypatch):
    monkeypatch.setitem(tw_limits.RATES, "admin_mfa_acct", (100, 900))
    owner = _enroll_owner(_env)
    replies = _burst(10, lambda i: _step_up(owner["token"], owner["codes"][0]))
    ok = [r for r in replies if r.status_code == 200]
    assert len(ok) == 1 and ok[0].json()["recovery_remaining"] == 9, [r.status_code for r in replies]
    assert admin_staff.recovery_remaining(admin_staff.OWNER) == 9
    assert _step_up(owner["token"], owner["codes"][0]).status_code == 401


def test_parallel_wrong_codes_stop_at_the_limit(db, slow, _env):
    owner = _enroll_owner(_env)
    codes = [r.status_code for r in _burst(30, lambda i: _step_up(owner["token"], "000000"))]
    assert set(codes) <= {401, 429}, codes
    assert codes.count(401) <= _limit("admin_mfa_acct"), codes
    assert codes.count(429) >= 30 - _limit("admin_mfa_acct")


def test_staff_step_up_403_and_audit(db, _env):
    st = _staff(role_perms=["users.view"], allow=list(admin_perms.GRANTABLE))
    tok = _staff_token(st, _env)
    assert _step_up(tok, _code(st["secret"], _env)).status_code == 403
    owner = _enroll_owner(_env)
    assert _step_up(owner["token"], "000000").status_code == 401
    good = _code(owner["secret"], _env)
    assert _step_up(owner["token"], good).status_code == 200
    rows = _sql("SELECT actor, action, status, target FROM admin_audit_log WHERE action = 'admin_step_up' ORDER BY id")
    assert [(a, s) for a, _, s, _ in rows] == [(st["sub"], 403), ("owner", 401), ("owner", 200)], rows
    assert good not in repr(_sql("SELECT * FROM admin_audit_log")) and "000000" not in repr(rows)


# ── D. new owner recovery codes ──
def test_new_recovery_codes(db, _env):
    owner, grant = _owner_grant(_env)
    old = owner["codes"]
    r = client.post(CODES, headers=_grant_hdr(owner["token"], grant))
    assert r.status_code == 200 and r.headers.get("cache-control") == "no-store", r.text
    new = r.json()["recovery_codes"]
    assert len(new) == 10 == len(set(new)) and not set(new) & set(old)
    # the old ones: dead at login and step-up
    assert _login({"ticket": _ticket({"password": PASSWORD}), "code": old[1]}).status_code == 401
    assert _step_up(owner["token"], old[2]).status_code == 401
    # the new ones work at both
    assert _login({"ticket": _ticket({"password": PASSWORD}), "code": new[0]}).status_code == 200
    assert _step_up(owner["token"], new[1]).status_code == 200
    assert admin_staff.recovery_remaining(admin_staff.OWNER) == 8


def test_parallel_new_codes_leave_one_set(db, _env):
    owner, grant = _owner_grant(_env)
    replies = _burst(2, lambda i: client.post(CODES, headers=_grant_hdr(owner["token"], grant)))
    assert [r.status_code for r in replies] == [200, 200]
    stored = {h for (h,) in _sql("SELECT code_hash FROM admin_recovery_codes WHERE subject = 'owner' AND used_at IS NULL")}
    sets = [{admin_staff.recovery_hash(c) for c in r.json()["recovery_codes"]} for r in replies]
    assert len(stored) == 10 and stored in sets, (len(stored), [len(s & stored) for s in sets])


# ── E. secrets ──
def test_grant_and_codes_never_leak(db, _env, capsys, caplog):
    owner, grant = _owner_grant(_env)
    r = client.post(CODES, headers=_grant_hdr(owner["token"], grant))
    new = r.json()["recovery_codes"]
    r2 = _step_up(owner["token"], new[0])
    grant2 = r2.json()["grant"]
    client.delete("/admin/user/999999999", headers=_grant_hdr(owner["token"], grant2))
    captured = capsys.readouterr()
    logs = captured.out + captured.err + caplog.text
    audit = repr(_sql("SELECT * FROM admin_audit_log"))
    secrets_ = {"grant": grant, "grant 2": grant2, **{f"code {i}": c for i, c in enumerate(new + owner["codes"])}}
    leaks = [(where, name) for where, text in (("logs", logs), ("audit", audit))
             for name, v in secrets_.items() if v in text]
    assert not leaks, leaks
