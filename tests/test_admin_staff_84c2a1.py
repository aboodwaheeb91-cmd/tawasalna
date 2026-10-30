"""Task 8.4c-2a1 — roles + staff API, owner only (docs/rules/admin-staff.md rule 10 · SYSTEMS_INDEX §25h).

Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with
TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py):
  A. every new route: no token 401 · staff with every GRANTABLE 403 · owner write without step-up 428 · owner
     with the grant passes · GET /admin/staff carries no hash / secret.
  B. OWNER_ONLY / "*" / unknown perms → 422 (role · allow · deny) · written straight into the DB → dropped from
     effective_perms and refused by check_admin.
  C. the same staff token on the very next request after: suspend · role change · allow / deny · shared role edit
     → 401 or 403 · restore never revives it · restore → active / invited.
  D. concurrency: delete role ‖ assign it → 409 or the assignment fails, never a staff row whose role became NULL ·
     seeding from two connections → the 4 roles once · a deleted / edited seeded role never comes back.
  E. emails: suspend · restore · effective-perm change only (shared role edit changing 2 of 3 active staff → 2
     emails; suspended / invited → none) · no panel path, no perm names · a failed email keeps the write.
  F. no hash / secret / grant in replies, logs or admin_audit_log · audit rows actor owner.
Run: python -m pytest tests/test_admin_staff_84c2a1.py -q
"""
import os, sys, uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import admin_perms
import admin_staff
import auth
import email_service
import server as srv
from test_admin_mfa_84b import _sql
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    STAFF_PW, _burst, _code, _env, _hdr, _migrated, _staff_token, client, db)
from test_admin_stepup_84c import _grant_hdr, _owner_grant

_HASH = {}
ALL_GRANTABLE = sorted(admin_perms.GRANTABLE)


def _role(perms=(), name=None):
    return _sql("INSERT INTO admin_roles (name, perms) VALUES (:n, :p) RETURNING id",
                n=name or "r-" + uuid.uuid4().hex[:8], p=list(perms))[0][0]


def _member(role_id=None, allow=(), deny=(), status="active", mfa=True):
    if "h" not in _HASH:
        _HASH["h"] = auth.hash_password(STAFF_PW)
    secret = admin_staff.new_secret()
    email = f"m{uuid.uuid4().hex[:8]}@t.test"
    sid = _sql("INSERT INTO admin_staff (email, name, password_hash, role_id, allow_perms, deny_perms, status, "
               "mfa_secret_enc, mfa_enabled_at) VALUES (:e, :n, :h, :r, :a, :d, :s, :m, "
               + ("NOW()" if mfa else "NULL") + ") RETURNING id",
               e=email, n="Name" + email[:5], h=_HASH["h"], r=role_id, a=list(allow), d=list(deny), s=status,
               m=admin_staff.encrypt(secret))[0][0]
    return {"id": sid, "email": email, "secret": secret, "name": "Name" + email[:5]}


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, "send_email",
                        lambda to, tpl, vars=None, **kw: sent.append((to, tpl, dict(vars or {}))) or {"ok": True})
    return sent


@pytest.fixture
def owner(db, _env):
    o, grant = _owner_grant(_env)
    return {"token": o["token"], "w": _grant_hdr(o["token"], grant), "r": _hdr(o["token"]), "grant": grant}


def _routes(role_id, staff_id):
    """(method, url, body, write) of every new route."""
    return [
        ("GET", "/admin/roles", None, False),
        ("POST", "/admin/roles", {"name": "n-" + uuid.uuid4().hex[:6], "perms": ["users.view"]}, True),
        ("PUT", f"/admin/roles/{role_id}", {"perms": ["users.view", "stats.view"]}, True),
        ("GET", "/admin/staff", None, False),
        ("PUT", f"/admin/staff/{staff_id}/access", {"role_id": role_id, "allow": [], "deny": []}, True),
        ("POST", f"/admin/staff/{staff_id}/suspend", None, True),
        ("POST", f"/admin/staff/{staff_id}/restore", None, True),
        ("DELETE", f"/admin/roles/{_role()}", None, True),
    ]


# ── A. auth matrix ──
def test_every_route_401_403_428_then_ok(owner, _env, mails):
    rid = _role(["users.view"])
    target = _member(rid)
    full = _member(_role(ALL_GRANTABLE), allow=ALL_GRANTABLE)
    full_tok = _staff_token(full, _env)
    for method, url, body, write in _routes(rid, target["id"]):
        assert client.request(method, url, json=body).status_code == 401, (method, url)
        assert client.request(method, url, json=body, headers=_hdr(full_tok)).status_code == 403, (method, url)
        if write:
            r = client.request(method, url, json=body, headers=owner["r"])
            assert (r.status_code, r.json()) == (428, {"error": "step_up_required"}), (method, url, r.text)
        r = client.request(method, url, json=body, headers=owner["w"])
        assert r.status_code == 200 and r.json()["ok"] is True, (method, url, r.text)
    roles = client.get("/admin/roles", headers=owner["r"]).json()["data"]
    assert [g["perm"] for g in roles["grantable"]] == list(admin_perms.GRANTABLE)
    assert not set(g["perm"] for g in roles["grantable"]) & set(admin_perms.OWNER_ONLY)
    st = next(s for s in client.get("/admin/staff", headers=owner["r"]).json()["data"]["staff"] if s["id"] == target["id"])
    assert set(st) == {"id", "name", "email", "status", "role", "allow", "deny", "effective_perms", "mfa_bound",
                       "last_login_at"}
    assert st["role"]["id"] == rid and st["mfa_bound"] is True


def test_validation(owner):
    w = owner["w"]
    assert client.post("/admin/roles", json={"name": "  ", "perms": []}, headers=w).status_code == 422
    assert client.post("/admin/roles", json={"name": "x" * 61, "perms": []}, headers=w).status_code == 422
    r = client.post("/admin/roles", json={"name": "dup", "perms": []}, headers=w)
    assert r.status_code == 200
    r2 = client.post("/admin/roles", json={"name": "dup", "perms": []}, headers=w)
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "name_taken"
    other = client.post("/admin/roles", json={"name": "dup2", "perms": []}, headers=w).json()["data"]["id"]
    assert client.put(f"/admin/roles/{other}", json={"name": "dup"}, headers=w).status_code == 409
    assert client.put("/admin/roles/999999999", json={"name": "zz"}, headers=w).status_code == 404
    assert client.delete("/admin/roles/999999999", headers=w).status_code == 404
    assert client.put("/admin/staff/999999999/access", json={}, headers=w).status_code == 404
    assert client.post("/admin/staff/999999999/suspend", headers=w).status_code == 404
    sid = _member()["id"]
    assert client.put(f"/admin/staff/{sid}/access", json={"role_id": 999999999}, headers=w).status_code == 422
    assert client.put(f"/admin/staff/{sid}/access", json={"role_id": "1"}, headers=w).status_code == 422
    assert client.post(f"/admin/staff/{sid}/restore", headers=w).status_code == 409   # not suspended


# ── B. owner perms never reach staff ──
@pytest.mark.parametrize("bad", [["staff.manage"], ["*"], ["users.view", "audit.view"], ["nope"], "users.view", [1]])
def test_owner_only_star_unknown_refused(owner, bad):
    w = owner["w"]
    rid = _role(["users.view"])
    sid = _member(rid)["id"]
    for method, url, body in (("POST", "/admin/roles", {"name": "b-" + uuid.uuid4().hex[:6], "perms": bad}),
                              ("PUT", f"/admin/roles/{rid}", {"perms": bad}),
                              ("PUT", f"/admin/staff/{sid}/access", {"role_id": rid, "allow": bad, "deny": []}),
                              ("PUT", f"/admin/staff/{sid}/access", {"role_id": rid, "allow": [], "deny": bad})):
        r = client.request(method, url, json=body, headers=w)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_perms", (method, url, r.text)
    assert _sql("SELECT perms FROM admin_roles WHERE id = :i", i=rid)[0][0] == ["users.view"]


def test_owner_perms_written_in_db_never_live(owner, _env):
    rid = _role(["*", "audit.view", "users.view"])
    st = _member(rid, allow=["staff.manage", "settings.security", "*"])
    tok = _staff_token(st, _env)
    row = next(s for s in client.get("/admin/staff", headers=owner["r"]).json()["data"]["staff"] if s["id"] == st["id"])
    assert row["effective_perms"] == ["users.view"]
    assert client.get("/admin/me", headers=_hdr(tok)).json()["perms"] == ["users.view"]
    for url in ("/admin/audit", "/admin/roles", "/admin/staff", "/admin/errors"):
        assert client.get(url, headers=_hdr(tok)).status_code == 403, url
    assert client.post(f"/admin/staff/{st['id']}/suspend", headers=_hdr(tok)).status_code == 403


# ── C. the same token after each change ──
def _ok(tok):
    return client.get("/admin/users", headers=_hdr(tok)).status_code


def test_token_dies_or_loses_perm_on_next_request(owner, _env, mails):
    w = owner["w"]
    rid = _role(["users.view"])
    other = _role(["stats.view"])
    changes = {
        "suspend": lambda st: client.post(f"/admin/staff/{st['id']}/suspend", headers=w),
        "role change": lambda st: client.put(f"/admin/staff/{st['id']}/access",
                                             json={"role_id": other, "allow": [], "deny": []}, headers=w),
        "no role": lambda st: client.put(f"/admin/staff/{st['id']}/access",
                                         json={"role_id": None, "allow": [], "deny": []}, headers=w),
        "deny": lambda st: client.put(f"/admin/staff/{st['id']}/access",
                                      json={"role_id": rid, "allow": [], "deny": ["users.view"]}, headers=w),
        "allow removed": lambda st: client.put(f"/admin/staff/{st['id']}/access",
                                               json={"role_id": other, "allow": [], "deny": []}, headers=w),
    }
    for name, change in changes.items():
        st = _member(rid, allow=["users.view"] if name == "allow removed" else ())
        tok = _staff_token(st, _env)
        assert _ok(tok) == 200, name
        assert change(st).status_code == 200, name
        assert _ok(tok) in (401, 403), name
    # shared role edit — every staff member on it, same tokens
    shared = _role(["users.view"])
    members = [_member(shared) for _ in range(2)]
    toks = [_staff_token(m, _env) for m in members]
    assert [_ok(t) for t in toks] == [200, 200]
    assert client.put(f"/admin/roles/{shared}", json={"perms": ["stats.view"]}, headers=w).status_code == 200
    assert all(_ok(t) in (401, 403) for t in toks)


def test_restore_never_revives_old_token(owner, _env, mails):
    w = owner["w"]
    st = _member(_role(["users.view"]))
    tok = _staff_token(st, _env)
    assert client.post(f"/admin/staff/{st['id']}/suspend", headers=w).json()["data"]["status"] == "suspended"
    assert _ok(tok) == 401
    r = client.post(f"/admin/staff/{st['id']}/restore", headers=w)
    assert r.status_code == 200 and r.json()["data"]["status"] == "active"
    assert _ok(tok) == 401 and client.get("/admin/me", headers=_hdr(tok)).status_code == 401
    assert _ok(_staff_token(st, _env)) == 200            # a fresh login works again
    # never bound the authenticator → restore gives invited
    inv = _member(status="suspended", mfa=False)
    assert client.post(f"/admin/staff/{inv['id']}/restore", headers=w).json()["data"]["status"] == "invited"


# ── D. concurrency + seeding ──
def test_delete_role_vs_assign_never_orphans(owner, mails):
    w = owner["w"]
    home = _role(["users.view"])
    for _ in range(8):
        rid = _role(["stats.view"])
        st = _member(home)

        def go(i, rid=rid, st=st):
            if i == 0:
                return client.delete(f"/admin/roles/{rid}", headers=w)
            return client.put(f"/admin/staff/{st['id']}/access", json={"role_id": rid, "allow": [], "deny": []},
                              headers=w)
        d, a = _burst(2, go)
        now = _sql("SELECT role_id FROM admin_staff WHERE id = :i", i=st["id"])[0][0]
        assert now is not None, (d.status_code, a.status_code)
        if d.status_code == 200:
            assert a.status_code == 422 and now == home, (d.text, a.text)
        else:
            assert d.status_code == 409 and d.json()["error"]["code"] == "role_in_use", d.text
            assert a.status_code == 200 and now == rid
    assert not _sql("SELECT 1 FROM admin_staff WHERE role_id IS NULL")


def test_role_in_use_cannot_be_deleted(owner, mails):
    rid = _role(["users.view"])
    _member(rid, status="suspended")
    assert client.delete(f"/admin/roles/{rid}", headers=owner["w"]).status_code == 409
    assert _sql("SELECT 1 FROM admin_roles WHERE id = :i", i=rid)


def _seeded():
    return {n: sorted(p) for n, p in _sql("SELECT name, perms FROM admin_roles ORDER BY id")}


def test_seed_once_even_in_parallel(db):
    _sql("DELETE FROM app_migrations WHERE name = :n", n=admin_staff.SEED_MARK)
    firsts = _burst(2, lambda i: admin_staff.seed_default_roles())
    assert sorted(firsts) == [False, True]
    want = {n: sorted(p) for n, p in admin_staff.DEFAULT_ROLES}
    assert _seeded() == want and len(want) == 4
    for perms in want.values():
        assert admin_perms.EMAIL_VIEW not in perms and admin_perms.PHONE_VIEW not in perms
        assert set(perms) <= set(admin_perms.GRANTABLE)
    # deleted + edited by the owner → the migration again changes nothing
    names = list(want)
    _sql("DELETE FROM admin_roles WHERE name = :n", n=names[0])
    _sql("UPDATE admin_roles SET perms = ARRAY['stats.view'] WHERE name = :n", n=names[1])
    srv._run_startup_migrations([("admin_roles_seed", admin_staff.seed_default_roles, False)])
    assert admin_staff.seed_default_roles() is False
    assert _seeded() == {names[1]: ["stats.view"], names[2]: want[names[2]], names[3]: want[names[3]]}


# ── E. emails ──
def _rendered(sent):
    return [email_service.render(tpl, vars) for _, tpl, vars in sent]


def test_shared_role_edit_emails_only_changed_active_staff(owner, mails):
    rid = _role(["users.view"])
    a, b = _member(rid), _member(rid)
    same = _member(rid, allow=["kyc.review"])                 # already has it → effective unchanged
    _member(rid, status="suspended"), _member(rid, status="invited", mfa=False)
    svs = {m["id"]: _sql("SELECT session_version FROM admin_staff WHERE id = :i", i=m["id"])[0][0] for m in (a, b, same)}
    r = client.put(f"/admin/roles/{rid}", json={"perms": ["users.view", "kyc.review"]}, headers=owner["w"])
    assert r.status_code == 200 and r.json()["data"]["staff_count"] == 5
    assert sorted((to, tpl) for to, tpl, _ in mails) == sorted([(a["email"], "staff_perms_changed"),
                                                               (b["email"], "staff_perms_changed")])
    after = {i: _sql("SELECT session_version FROM admin_staff WHERE id = :i", i=i)[0][0] for i in svs}
    assert after[a["id"]] == svs[a["id"]] + 1 and after[same["id"]] == svs[same["id"]]
    # a rename alone sends nothing
    mails.clear()
    assert client.put(f"/admin/roles/{rid}", json={"name": "renamed-" + uuid.uuid4().hex[:4]}, headers=owner["w"]).status_code == 200
    assert mails == []


def test_access_suspend_restore_emails(owner, mails):
    w = owner["w"]
    rid = _role(["users.view"])
    st = _member(rid)
    # no effective change (allow = what the role already gives) → no email
    client.put(f"/admin/staff/{st['id']}/access", json={"role_id": rid, "allow": ["users.view"], "deny": []}, headers=w)
    assert mails == []
    client.put(f"/admin/staff/{st['id']}/access", json={"role_id": rid, "allow": ["stats.view"], "deny": []}, headers=w)
    client.post(f"/admin/staff/{st['id']}/suspend", headers=w)
    client.post(f"/admin/staff/{st['id']}/suspend", headers=w)                     # already suspended → no 2nd
    client.put(f"/admin/staff/{st['id']}/access", json={"role_id": None, "allow": [], "deny": []}, headers=w)
    client.post(f"/admin/staff/{st['id']}/restore", headers=w)
    inv = _member(rid, status="invited", mfa=False)
    client.put(f"/admin/staff/{inv['id']}/access", json={"role_id": None, "allow": [], "deny": []}, headers=w)
    assert [(to, tpl) for to, tpl, _ in mails] == [(st["email"], "staff_perms_changed"),
                                                  (st["email"], "staff_suspended"),
                                                  (st["email"], "staff_restored")]
    assert all(set(v) == {"name"} for _, _, v in mails)
    for msg in _rendered(mails):
        text = msg["subject"] + msg["html"] + msg["text"]
        assert "tw-ctrl" not in text and (not srv.ADMIN_URL_TOKEN or srv.ADMIN_URL_TOKEN not in text) and "http" not in msg["text"]
        assert not [p for p in admin_perms.ALL if p in text]
        assert not [v for v in admin_perms.ALL.values() if v in text]


def test_failed_email_keeps_the_write(owner, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(email_service, "send_email", boom)
    st = _member(_role(["users.view"]))
    assert client.post(f"/admin/staff/{st['id']}/suspend", headers=owner["w"]).status_code == 200
    assert _sql("SELECT status FROM admin_staff WHERE id = :i", i=st["id"])[0][0] == "suspended"


# ── F. secrets + audit ──
def test_no_hash_or_secret_in_replies_logs_audit(owner, _env, mails, capsys, caplog):
    w = owner["w"]
    rid = _role(["users.view"])
    st = _member(rid)
    _sql("INSERT INTO admin_recovery_codes (subject, code_hash) VALUES (:s, :h)", s=f"staff:{st['id']}",
         h=admin_staff.recovery_hash("abcde-fghjk"))
    replies = [client.get("/admin/staff", headers=w), client.get("/admin/roles", headers=w),
               client.put(f"/admin/staff/{st['id']}/access", json={"role_id": rid, "allow": ["stats.view"], "deny": []},
                          headers=w),
               client.post(f"/admin/staff/{st['id']}/suspend", headers=w),
               client.post(f"/admin/staff/{st['id']}/restore", headers=w),
               client.post("/admin/roles", json={"name": "audit-r", "perms": []}, headers=w)]
    assert all(r.status_code == 200 for r in replies), [r.text for r in replies]
    pw_hash, enc = _sql("SELECT password_hash, mfa_secret_enc FROM admin_staff WHERE id = :i", i=st["id"])[0]
    secrets_ = {"password_hash": pw_hash, "mfa_secret_enc": enc, "secret": st["secret"], "grant": owner["grant"],
                "token": owner["token"], "recovery": admin_staff.recovery_hash("abcde-fghjk")}
    out = capsys.readouterr()
    places = {"replies": "".join(r.text for r in replies), "logs": out.out + out.err + caplog.text,
              "audit": repr(_sql("SELECT * FROM admin_audit_log"))}
    leaks = [(p, n) for p, text in places.items() for n, v in secrets_.items() if v and v in text]
    assert not leaks, leaks
    for word in ("password_hash", "mfa_secret", "hash"):
        assert word not in places["replies"]
    rows = _sql("SELECT actor, action, status FROM admin_audit_log WHERE action LIKE 'admin_staff%' "
                "OR action LIKE 'admin_roles%' ORDER BY id")
    assert [(a, act, s) for a, act, s in rows] == [
        ("owner", "admin_staff_access", 200), ("owner", "admin_staff_suspend", 200),
        ("owner", "admin_staff_restore", 200), ("owner", "admin_roles_create", 200)], rows
