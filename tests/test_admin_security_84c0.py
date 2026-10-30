"""Task 8.4c-0 — admin login under concurrency + behavioural security tests for 8.4a / 8.4a2 / 8.4b
(docs/rules/admin-staff.md rules 6–7 · SYSTEMS_INDEX §25h).

  0. (no DB) _rate_reserve: threads on the function itself → never more reservations than the limit · a full
     bucket counts nothing · release · admin lock keys are never evicted by a full section.
  Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with
  TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py):
  A. concurrency (30 / 10 parallel requests, password / code checks slowed so the requests overlap):
     wrong owner password · wrong staff password · wrong codes on a valid ticket → 401s ≤ the account limit,
     the rest 429 · one TOTP code / one recovery code in parallel → one success · one ticket with different
     valid codes in parallel → one token.
  B. every admin route (app routes, minus admin_perms.UNGUARDED_ROUTES): no token · a site JWT (X-Admin-Token /
     Authorization) · staff without the perm · staff with every GRANTABLE + the perm + "*" on an owner-only
     route · staff with the perm (writes probed with a wrong body / a missing id — no effect) · no email / phone
     in any GET 200 without users.email.view / users.phone.view.
  C. tickets (expired · one byte · other secret · other aud · sub edited · A's ticket + B's code · old sv ·
     ticket ↔ admin token · used once) + the same admin token on the very next request after each DB change.
  D. secrets never in logs / audit rows / other admin replies · stored encrypted / hashed.
Run: python -m pytest tests/test_admin_security_84c0.py -q
"""
import base64, json, os, re, sys, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import admin_perms
import admin_staff
import auth
import email_service
import server as srv
import tw_limits
import tw_settings
from test_admin_perms_84a import ROUTE_PERMS, _BODIES, _NORMAL_KEY, _admin_area
from test_admin_mfa_84b import PASSWORD, T0, _db_params, _sql

client = TestClient(srv.app)
LOGIN = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN + "/login"
ADMIN_SECRET = "test-admin-secret-84c0-" + "s" * 32
STAFF_PW = "staff-pass-84c0"
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_REAL_HMAC = srv.hmac


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_TOKEN", PASSWORD)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", ADMIN_SECRET)
    monkeypatch.setattr(srv, "_RATE_LIMIT", 100_000)       # the per-IP path limit — the admin locks are measured
    monkeypatch.setenv("ADMIN_MFA_KEY", "test-mfa-key-84c0-" + "k" * 32)
    monkeypatch.delenv("ADMIN_MFA_RESET", raising=False)
    clock = {"t": T0}
    monkeypatch.setattr(admin_staff, "_now", lambda: clock["t"])
    srv._rate_store.clear()
    tw_settings._set_overrides({})
    yield clock
    srv._rate_store.clear()


def _limit(name):
    return tw_settings.rate(name)[0]


# ── 0. the reservation itself (no DB) ──
def test_rate_reserve_threads_never_pass_the_limit():
    keys = [("admin_login_ip", "10.0.0.1"), ("admin_login_acct", "owner")]
    start = threading.Barrier(50)

    def go(_):
        start.wait()
        return srv._rate_reserve(keys)

    with ThreadPoolExecutor(50) as ex:
        held = [h for h in ex.map(go, range(50)) if h is not None]
    assert len(held) == _limit("admin_login_acct")
    # the full account bucket counted nothing in the IP bucket
    assert len(srv._rate_store["admin_login_ip:10.0.0.1"]) == _limit("admin_login_acct")
    srv._rate_release(held[0])
    assert len(srv._rate_store["admin_login_acct:owner"]) == _limit("admin_login_acct") - 1
    assert srv._rate_reserve(keys) is not None and srv._rate_reserve(keys) is None
    assert srv._rate_ok_all(keys) is False                     # the same function under the old name


def test_admin_lock_keys_never_evicted(monkeypatch):
    real = tw_settings.limit
    monkeypatch.setattr(srv.tw_settings, "limit", lambda n: 3 if n == "mem_store_max_keys" else real(n))
    srv._rate_reserve([("admin_login_acct", "owner")])
    for i in range(10):                                         # a flood of other accounts
        srv._rate_reserve([("admin_login_acct", f"email:x{i}@t.test")])
    assert "admin_login_acct:owner" in srv._rate_store


# ── DB fixtures ──
@pytest.fixture(scope="module")
def _migrated():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


def _reset_admin_tables():
    _sql("UPDATE admin_owner_mfa SET secret_enc = NULL, enabled_at = NULL, last_step = NULL, "
         "session_version = 1, reset_on = NULL WHERE id = 1")
    _sql("DELETE FROM admin_recovery_codes")
    _sql("DELETE FROM admin_staff")
    _sql("DELETE FROM admin_roles")
    _sql("DELETE FROM admin_audit_log")


@pytest.fixture
def db(_migrated):
    _reset_admin_tables()
    yield


_STAFF_HASH = None


def _staff(role_perms=(), allow=(), deny=(), mfa=True):
    global _STAFF_HASH
    if _STAFF_HASH is None:
        _STAFF_HASH = auth.hash_password(STAFF_PW)
    rid = _sql("INSERT INTO admin_roles (name, perms) VALUES (:n, :p) RETURNING id",
               n="role-" + uuid.uuid4().hex[:8], p=list(role_perms))[0][0]
    secret = admin_staff.new_secret()
    email = f"staff{uuid.uuid4().hex[:8]}@t.test"
    sid = _sql("INSERT INTO admin_staff (email, name, password_hash, role_id, allow_perms, deny_perms, status, "
               "mfa_secret_enc, mfa_enabled_at) VALUES (:e, 'S', :h, :r, :a, :d, 'active', :m, "
               + ("NOW()" if mfa else "NULL") + ") RETURNING id",
               e=email, h=_STAFF_HASH, r=rid, a=list(allow), d=list(deny), m=admin_staff.encrypt(secret))[0][0]
    return {"id": sid, "sub": f"staff:{sid}", "email": email, "secret": secret, "role": rid}


def _code(secret, clock, advance=True):
    """A valid authenticator code at a fresh step (the clock moves 30 s — each step is accepted once)."""
    if advance:
        clock["t"] += 30
    return admin_staff.totp_code(admin_staff._b32(secret), int(clock["t"] // 30))


def _hdr(token):
    return {"X-Admin-Token": token}


def _login(body):
    return client.post(LOGIN, json=body)


def _enroll_owner(clock):
    r = _login({"password": PASSWORD})
    assert r.status_code == 200 and r.json()["step"] == "enroll", r.text
    secret = r.json()["secret"]
    r2 = _login({"ticket": r.json()["ticket"], "code": _code(secret, clock)})
    assert r2.status_code == 200, r2.text
    return {"secret": secret, "token": r2.json()["token"], "codes": r2.json()["recovery_codes"],
            "replies": (r, r2)}


def _ticket(body):
    r = _login(body)
    assert r.status_code == 200 and r.json()["step"] == "mfa", r.text
    return r.json()["ticket"]


def _staff_token(st, clock):
    r = _login({"ticket": _ticket({"email": st["email"], "password": STAFF_PW}), "code": _code(st["secret"], clock)})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _burst(n, fn):
    start = threading.Barrier(n)

    def go(i):
        start.wait()
        return fn(i)

    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(go, range(n)))


@pytest.fixture
def slow(monkeypatch):
    """Slows the password / code checks so parallel requests overlap (the race needs a slow check)."""
    class _SlowHmac:
        new = staticmethod(_REAL_HMAC.new)

        @staticmethod
        def compare_digest(a, b):
            if b == srv.ADMIN_TOKEN.encode("utf-8"):
                time.sleep(0.05)
            return _REAL_HMAC.compare_digest(a, b)

    monkeypatch.setattr(srv, "hmac", _SlowHmac)
    real_verify, real_factor = srv._verify_password, admin_staff.verify_second_factor
    monkeypatch.setattr(srv, "_verify_password", lambda p, h: (time.sleep(0.05), real_verify(p, h))[1])
    monkeypatch.setattr(admin_staff, "verify_second_factor",
                        lambda *a, **kw: (time.sleep(0.05), real_factor(*a, **kw))[1])


# ── A. concurrency ──
def test_parallel_wrong_owner_password_stops_at_the_limit(db, slow):
    codes = [r.status_code for r in _burst(30, lambda i: _login({"password": "wrong-" + "w" * 30}))]
    assert set(codes) <= {401, 429}, codes
    assert codes.count(401) <= _limit("admin_login_acct"), codes
    assert codes.count(429) >= 30 - _limit("admin_login_acct")


def test_parallel_wrong_staff_password_stops_at_the_limit(db, slow):
    st = _staff(role_perms=["users.view"])
    codes = [r.status_code for r in _burst(30, lambda i: _login({"email": st["email"], "password": "nope"}))]
    assert set(codes) <= {401, 429}, codes
    assert codes.count(401) <= _limit("admin_login_acct"), codes


def test_parallel_wrong_codes_stop_at_the_mfa_limit(db, slow, _env):
    st = _staff(role_perms=["users.view"])
    ticket = _ticket({"email": st["email"], "password": STAFF_PW})
    codes = [r.status_code for r in _burst(30, lambda i: _login({"ticket": ticket, "code": "000000"}))]
    assert set(codes) <= {401, 429}, codes
    assert codes.count(401) <= _limit("admin_mfa_acct"), codes


def test_one_totp_code_in_parallel_gives_one_token(db, slow, _env, monkeypatch):
    monkeypatch.setitem(tw_limits.RATES, "admin_mfa_acct", (100, 900))   # every request reaches the code check
    owner = _enroll_owner(_env)
    tickets = [_ticket({"password": PASSWORD}) for _ in range(10)]
    code = _code(owner["secret"], _env)
    codes = [r.status_code for r in _burst(10, lambda i: _login({"ticket": tickets[i], "code": code}))]
    assert codes.count(200) == 1 and codes.count(401) == 9, codes


def test_one_recovery_code_in_parallel_used_once(db, slow, _env, monkeypatch):
    monkeypatch.setitem(tw_limits.RATES, "admin_mfa_acct", (100, 900))
    owner = _enroll_owner(_env)
    tickets = [_ticket({"password": PASSWORD}) for _ in range(10)]
    replies = _burst(10, lambda i: _login({"ticket": tickets[i], "code": owner["codes"][0]}))
    ok = [r for r in replies if r.status_code == 200]
    assert len(ok) == 1 and ok[0].json()["recovery_remaining"] == 9, [r.status_code for r in replies]
    assert admin_staff.recovery_remaining(admin_staff.OWNER) == 9


def test_one_ticket_with_different_valid_codes_gives_one_token(db, slow, _env, monkeypatch):
    monkeypatch.setitem(tw_limits.RATES, "admin_mfa_acct", (100, 900))   # the ticket rule stops it, not the lock
    owner = _enroll_owner(_env)
    ticket = _ticket({"password": PASSWORD})
    replies = _burst(10, lambda i: _login({"ticket": ticket, "code": owner["codes"][i]}))
    codes = [r.status_code for r in replies]
    assert codes.count(200) == 1 and codes.count(401) == 9, codes
    assert {r.text for r in replies if r.status_code == 401} == {_login({"password": "x"}).text}
    # used once: a valid code afterwards on the same ticket → the same 401
    r = _login({"ticket": ticket, "code": _code(owner["secret"], _env)})
    assert r.status_code == 401


def test_failed_code_does_not_burn_the_ticket(db, _env):
    st = _staff(role_perms=["users.view"])
    ticket = _ticket({"email": st["email"], "password": STAFF_PW})
    assert _login({"ticket": ticket, "code": "000000"}).status_code == 401
    assert _login({"ticket": ticket, "code": _code(st["secret"], _env)}).status_code == 200
    assert _login({"ticket": ticket, "code": _code(st["secret"], _env)}).status_code == 401


# ── B. every admin route ──
def _scan_routes():
    out = []
    for route in srv.app.routes:
        path = getattr(route, "path", "")
        if not _admin_area(path) or route.name in admin_perms.UNGUARDED_ROUTES:
            continue
        for method in sorted(route.methods or ()):
            if method != "HEAD":
                out.append((method, path))
    return out


_MISSING_ID = "999999999"


def _scan_url(path, method, uid, key=_NORMAL_KEY):
    vals = {"public_id": "HZZZZZZZZZZ", "key": key}
    if method == "GET":
        vals["user_id"] = str(uid)
    return re.sub(r"\{(\w+)[^}]*\}", lambda m: vals.get(m.group(1), _MISSING_ID), path)


@pytest.fixture(scope="module")
def scan(_migrated):
    _reset_admin_tables()
    n = uuid.uuid4().hex[:10]
    uid = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES (:t, :n, :e, 'x', 'emp') "
               "RETURNING id", t="U" + n, n="Scan" + n, e=f"scan{n}@t.test")[0][0]
    sv = _sql("SELECT session_version FROM users WHERE id = :i", i=uid)[0][0]
    sid = _sql("INSERT INTO admin_staff (email, name, password_hash, status, mfa_enabled_at) "
               "VALUES (:e, 'Scan', 'x', 'active', NOW()) RETURNING id", e=f"scanstaff{n}@t.test")[0][0]
    return {"uid": uid, "user_sv": int(sv or 0), "sid": sid, "tw_id": "U" + n}


def _scan_staff(scan, allow):
    _sql("UPDATE admin_staff SET allow_perms = :a WHERE id = :i", a=list(allow), i=scan["sid"])
    sv = _sql("SELECT session_version FROM admin_staff WHERE id = :i", i=scan["sid"])[0][0]
    return srv._admin_jwt_issue(sub=f"staff:{scan['sid']}", role="staff", perms=[], sv=sv)


def _site_email_values():
    """Addresses that are not user data: the site's own sender settings + RFC 2606 placeholders (string catalog)."""
    vals = {"name@example.com"}
    for d in (email_service.DEFAULTS, email_service.get_settings()):
        for v in (d or {}).values():
            if isinstance(v, str):
                vals.update(_EMAIL_RE.findall(v))
    return vals


def _contact_keys(obj, path="$"):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():   # a dotted key = a twT string key (/admin/strings), not a data field
            if "." not in k and (admin_perms.is_email_key(k) or admin_perms.is_phone_key(k)):
                found.append(f"{path}.{k}")
            found += _contact_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += _contact_keys(v, f"{path}[{i}]")
    return found


@pytest.mark.parametrize("method,path", _scan_routes())
def test_every_admin_route_is_guarded(scan, method, path):
    perm = ROUTE_PERMS[(method, path)]                      # a route missing from the table fails here
    url = _scan_url(path, method, scan["uid"])
    body = _BODIES.get(path, {})
    user_jwt = srv._jwt_encode({"user_id": scan["uid"], "user_type": "emp", "tw_id": scan["tw_id"],
                                "sv": scan["user_sv"]})
    srv._rate_store.clear()
    # no token / a site user's JWT
    assert client.request(method, url, json=body).status_code == 401
    assert client.request(method, url, json=body, headers=_hdr(user_jwt)).status_code == 401
    r = client.request(method, url, json=body, headers={"Authorization": "Bearer " + user_jwt})
    assert r.status_code in (401, 403), r.status_code
    assert set(r.json()) <= {"detail", "error", "ok"}, r.text
    grantable = list(admin_perms.GRANTABLE)
    if perm in admin_perms.OWNER_ONLY:
        tok = _scan_staff(scan, grantable + [perm, "*"])
        assert client.request(method, url, json=body, headers=_hdr(tok)).status_code == 403
        return
    tok = _scan_staff(scan, [p for p in grantable if p != perm])
    assert client.request(method, url, json=body, headers=_hdr(tok)).status_code == 403
    tok = _scan_staff(scan, [perm])
    if method == "GET":
        r = client.get(url, headers=_hdr(tok))
        assert r.status_code not in (401, 403, 500, 503), (r.status_code, r.text[:200])
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            assert not _contact_keys(r.json()), _contact_keys(r.json())
            assert not set(_EMAIL_RE.findall(r.text)) - _site_email_values(), r.text[:300]
    else:   # a write: a body of the wrong type (422 before anything runs) / a missing id / an unknown key
        url = _scan_url(path, method, scan["uid"], key="no_such_key_84c0")
        r = client.request(method, url, content=b'"not-an-object"', headers=dict(_hdr(tok), **{"Content-Type": "application/json"}))
        assert r.status_code not in (401, 403, 500, 503) and r.status_code < 500, (r.status_code, r.text[:200])


# ── C. tickets + sessions ──
def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _claims_of(token):
    return json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))


def test_bad_tickets_same_401(db, _env):
    owner = _enroll_owner(_env)
    a, b = _staff(role_perms=["users.view"]), _staff(role_perms=["users.view"])
    good = _ticket({"password": PASSWORD})
    fail_text = _login({"password": "wrong-" + "w" * 30}).text
    c = _claims_of(good)
    now = int(time.time())
    h, p, s = good.split(".")
    bad = {
        "expired": srv._jwt_sign(dict(c, iat=now - 400, exp=now - 100), ADMIN_SECRET),
        "one byte": h + "." + p + "." + ("A" if s[0] != "A" else "B") + s[1:],
        "other secret": srv._jwt_sign(c, "another-secret-" + "z" * 40),
        "other aud": srv._jwt_sign(dict(c, aud=srv._ADMIN_JWT_AUD), ADMIN_SECRET),
        "sub edited": h + "." + _b64(dict(c, sub=a["sub"])) + "." + s,
        "admin token": owner["token"],
    }
    for name, t in bad.items():
        srv._rate_store.clear()
        r = _login({"ticket": t, "code": _code(owner["secret"], _env)})
        assert (r.status_code, r.text) == (401, fail_text), name
    srv._rate_store.clear()
    # A's ticket + B's code
    ta = _ticket({"email": a["email"], "password": STAFF_PW})
    assert _login({"ticket": ta, "code": _code(b["secret"], _env)}).status_code == 401
    # old sv
    tb = _ticket({"email": b["email"], "password": STAFF_PW})
    _sql("UPDATE admin_staff SET session_version = session_version + 1 WHERE id = :i", i=b["id"])
    assert _login({"ticket": tb, "code": _code(b["secret"], _env)}).status_code == 401
    # the ticket is not an admin token
    assert client.get("/admin/users", headers=_hdr(_ticket({"password": PASSWORD}))).status_code == 401
    # the good one still works (nothing above burnt it)
    assert _login({"ticket": good, "code": _code(owner["secret"], _env)}).status_code == 200


def test_same_token_next_request_after_each_change(db, _env, monkeypatch):
    def fresh(**kw):
        st = _staff(**kw)
        return st, _hdr(_staff_token(st, _env))

    st, h = fresh(role_perms=["users.view"])
    assert client.get("/admin/users", headers=h).status_code == 200
    _sql("UPDATE admin_staff SET status = 'suspended' WHERE id = :i", i=st["id"])
    assert client.get("/admin/users", headers=h).status_code == 401
    st, h = fresh(role_perms=["users.view"])
    _sql("UPDATE admin_staff SET session_version = session_version + 1 WHERE id = :i", i=st["id"])
    assert client.get("/admin/users", headers=h).status_code == 401
    st, h = fresh(role_perms=["users.view", "stats.view"])
    _sql("UPDATE admin_roles SET perms = ARRAY['stats.view'] WHERE id = :i", i=st["role"])
    assert client.get("/admin/users", headers=h).status_code == 403
    st, h = fresh(role_perms=["users.view"])
    _sql("UPDATE admin_staff SET deny_perms = ARRAY['users.view'] WHERE id = :i", i=st["id"])
    assert client.get("/admin/users", headers=h).status_code == 403
    st, h = fresh(role_perms=["users.view"])
    _sql("UPDATE admin_staff SET mfa_enabled_at = NULL WHERE id = :i", i=st["id"])
    assert client.get("/admin/users", headers=h).status_code == 401
    srv._rate_store.clear()
    owner = _enroll_owner(_env)
    assert client.get("/admin/audit", headers=_hdr(owner["token"])).status_code == 200
    monkeypatch.setenv("ADMIN_MFA_RESET", datetime.now(timezone.utc).date().isoformat())
    assert _login({"password": PASSWORD}).json()["step"] == "enroll"
    assert client.get("/admin/audit", headers=_hdr(owner["token"])).status_code == 401


# ── D. secrets ──
def test_secrets_never_leak(db, _env, capsys, caplog):
    owner = _enroll_owner(_env)
    designated = list(owner["replies"])                 # enroll reply (secret + ticket) · bind reply (token + codes)
    others = [_login({"password": "wrong-" + "w" * 30})]
    t1 = _login({"password": PASSWORD})
    designated.append(t1)
    used_code = owner["codes"][0]
    r = _login({"ticket": t1.json()["ticket"], "code": used_code})
    designated.append(r)
    owner_token = r.json()["token"]
    st = _staff(role_perms=["users.view", "stats.view", "support.manage", "kyc.review", "settings.edit"])
    others.append(_login({"email": st["email"], "password": "wrong-pass"}))
    t2 = _login({"email": st["email"], "password": STAFF_PW})
    designated.append(t2)
    others.append(_login({"ticket": t2.json()["ticket"], "code": "000000"}))
    staff_code = _code(st["secret"], _env)
    r = _login({"ticket": t2.json()["ticket"], "code": staff_code})
    designated.append(r)
    staff_token = r.json()["token"]
    for tok in (owner_token, staff_token):
        for p in ("/admin/users", "/admin/audit", "/admin/settings", "/admin/stats/summary", "/admin/kyc",
                  "/admin/support/tickets", "/admin/email"):
            others.append(client.get(p, headers=_hdr(tok)))
    secrets_ = {"owner password / ADMIN_TOKEN": PASSWORD, "staff password": STAFF_PW,
                "owner TOTP secret": owner["secret"], "staff TOTP secret": st["secret"],
                "owner ticket": t1.json()["ticket"], "staff ticket": t2.json()["ticket"],
                "enroll ticket": owner["replies"][0].json()["ticket"],
                "owner token": owner_token, "staff token": staff_token, "first owner token": owner["token"]}
    secrets_.update({f"recovery code {i}": c for i, c in enumerate(owner["codes"])})
    codes = {"staff code": staff_code}
    captured = capsys.readouterr()
    logs = captured.out + captured.err + caplog.text
    audit = repr(_sql("SELECT * FROM admin_audit_log"))
    texts = {"logs": logs, "audit": audit, **{f"reply {i} {r.request.url.path}": r.text for i, r in enumerate(others)}}
    leaks = [(where, name) for where, text in texts.items() for name, v in secrets_.items() if v in text]
    leaks += [(where, name) for where, text in texts.items() for name, v in codes.items()
              if re.search(r"(?<!\d)" + v + r"(?!\d)", text)]
    assert not leaks, leaks
    # stored encrypted / hashed only
    enc = _sql("SELECT mfa_secret_enc FROM admin_staff WHERE id = :i", i=st["id"])[0][0]
    assert enc and enc != st["secret"] and st["secret"] not in enc
    owner_enc = _sql("SELECT secret_enc FROM admin_owner_mfa WHERE id = 1")[0][0]
    assert owner["secret"] not in owner_enc
    stored = repr(_sql("SELECT * FROM admin_recovery_codes"))
    for c in owner["codes"]:
        assert c not in stored and c.replace("-", "") not in stored
