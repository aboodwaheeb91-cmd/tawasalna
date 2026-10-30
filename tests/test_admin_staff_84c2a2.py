"""Task 8.4c-2a2 — staff invite · staff password reset · authenticator reset (docs/rules/admin-staff.md rule 14 ·
SYSTEMS_INDEX §25h).

Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with
TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py):
  A. owner routes (invite · resend · delete · mfa-reset): no token 401 · staff with every GRANTABLE 403 · owner
     without step-up 428 · then ok.
  B. invite: full journey (invite → start → complete → two-step login) · no login before it · 11 chars 422 ·
     passphrase with spaces ok · expired · used · resend kills the old link · delete kills it · 409s.
  C. concurrency: complete ‖ complete → one + exactly 10 codes · resend ‖ complete → the old one completed first or
     failed · forgot ‖ forgot → one live link · password-reset complete ‖ complete → one.
  D. password reset: old token dies · authenticator kept · suspended: no email, same reply, never re-activated ·
     suspended after the request → the link fails · unknown email → same reply.
  E. mfa reset: current token dies at once · old recovery codes dead · password alone gives no token · after
     completion only the new authenticator works.
  F. no link token / TOTP secret / hash in logs, audit rows or replies (except the start secret) · no panel path in
     any email · every public route 429 past its limit · a bad code shape is 422 and counts nothing.
Run: python -m pytest tests/test_admin_staff_84c2a2.py -q
"""
import os, sys, uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import admin_staff
import email_service
import server as srv
import tw_settings
from test_admin_mfa_84b import _sql
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    STAFF_PW, _burst, _code, _env, _hdr, _login, _migrated, _staff_token, _ticket, client, db)
from test_admin_staff_84c2a1 import ALL_GRANTABLE, _member, _role, mails, owner  # noqa: F401 — fixtures

PANEL = "/tw-ctrl-" + srv.ADMIN_URL_TOKEN
FORGOT = PANEL + "/forgot"
PASSPHRASE = "my long pass phrase 2026"


def _token(mail):
    return mail[2]["link"].split("#t=", 1)[1]


def _last(mails, tpl):
    return [m for m in mails if m[1] == tpl][-1]


def _invite(owner, mails, email=None, role_id=None):
    email = email or f"inv{uuid.uuid4().hex[:8]}@t.test"
    r = client.post("/admin/staff/invite", json={"name": "Inv Name", "email": email.upper(), "role_id": role_id,
                                                 "allow": ["users.view"], "deny": []}, headers=owner["w"])
    assert r.status_code == 200, r.text
    return r.json()["data"], _token(_last(mails, "staff_invite")), email


def _start(kind, token):
    return client.post(f"/staff/{kind}/start", json={"token": token})


def _complete_invite(token, clock, password=PASSPHRASE, secret=None):
    if secret is None:
        r = _start("invite", token)
        assert r.status_code == 200, r.text
        secret = r.json()["data"]["secret"]
    code = _code(secret, clock)
    return client.post("/staff/invite/complete", json={"token": token, "password": password, "code": code}), secret


def _staff_login(email, password, secret, clock):
    r = _login({"email": email, "password": password})
    if r.status_code != 200:
        return r
    return _login({"ticket": r.json()["ticket"], "code": _code(secret, clock)})


def _live(sid, kind):
    return _sql("SELECT COUNT(*) FROM admin_invites WHERE staff_id = :s AND kind = :k AND used_at IS NULL",
                s=sid, k=kind)[0][0]


# ── A. owner routes ──
def test_owner_routes_401_403_428_then_ok(owner, _env, mails):
    full_tok = _staff_token(_member(_role(ALL_GRANTABLE), allow=ALL_GRANTABLE), _env)
    inv, _, _ = _invite(owner, mails)
    inv2, _, _ = _invite(owner, mails)
    act = _member(_role(["users.view"]))
    routes = [("POST", "/admin/staff/invite", {"name": "N", "email": f"x{uuid.uuid4().hex[:6]}@t.test"}),
              ("POST", f"/admin/staff/{inv['id']}/invite/resend", None),
              ("POST", f"/admin/staff/{act['id']}/mfa-reset", None),
              ("DELETE", f"/admin/staff/{inv2['id']}", None)]
    for method, url, body in routes:
        assert client.request(method, url, json=body).status_code == 401, url
        assert client.request(method, url, json=body, headers=_hdr(full_tok)).status_code == 403, url
        r = client.request(method, url, json=body, headers=owner["r"])
        assert (r.status_code, r.json()) == (428, {"error": "step_up_required"}), url
        r = client.request(method, url, json=body, headers=owner["w"])
        assert r.status_code == 200 and r.json()["ok"] is True, (url, r.text)


# ── B. invite ──
def test_invite_full_journey(owner, _env, mails):
    rid = _role(["users.view"])
    st, token, email = _invite(owner, mails, role_id=rid)
    assert st["status"] == "invited" and st["email"] == email and st["email_sent"] is True and st["mfa_bound"] is False
    to, tpl, vars_ = _last(mails, "staff_invite")
    assert to == email and vars_["hours"] == 24 and vars_["link"].startswith(email_service.get_settings()["site_url"]
                                                                            + "/staff/invite#t=")
    ttl = _sql("SELECT EXTRACT(EPOCH FROM expires_at - created_at) FROM admin_invites WHERE staff_id = :s", s=st["id"])
    assert abs(float(ttl[0][0]) - 24 * 3600) < 5
    # no login before both the password and the authenticator are set
    assert _login({"email": email, "password": PASSPHRASE}).status_code == 401
    r = _start("invite", token)
    assert r.status_code == 200 and r.json()["data"]["name"] == "Inv Name"
    assert r.json()["data"]["otpauth_uri"].startswith("otpauth://totp/")
    secret = r.json()["data"]["secret"]
    assert _login({"email": email, "password": PASSPHRASE}).status_code == 401   # start alone binds nothing
    # 11 chars → 422, nothing used
    code = _code(secret, _env)
    r = client.post("/staff/invite/complete", json={"token": token, "password": "x" * 11, "code": code})
    assert r.status_code == 422 and r.json()["error"]["code"] == "weak_password"
    r, _ = _complete_invite(token, _env, secret=secret)       # passphrase with spaces
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["recovery_codes"]) == 10 and data["panel"] == PANEL
    assert r.headers["Cache-Control"] == "no-store"
    row = _sql("SELECT status, mfa_enabled_at IS NOT NULL FROM admin_staff WHERE id = :i", i=st["id"])[0]
    assert tuple(row) == ("active", True)
    r = _staff_login(email, PASSPHRASE, secret, _env)
    assert r.status_code == 200 and r.json()["token"], r.text
    assert client.get("/admin/users", headers=_hdr(r.json()["token"])).status_code == 200
    # a recovery code works once
    t = _ticket({"email": email, "password": PASSPHRASE})
    assert _login({"ticket": t, "code": data["recovery_codes"][0]}).status_code == 200
    t = _ticket({"email": email, "password": PASSPHRASE})
    assert _login({"ticket": t, "code": data["recovery_codes"][0]}).status_code == 401
    # the same link again → invalid
    assert _start("invite", token).json()["error"]["code"] == "invalid_link"
    # duplicate email → 409s
    r = client.post("/admin/staff/invite", json={"name": "N", "email": email}, headers=owner["w"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    inv, _, inv_email = _invite(owner, mails)
    r = client.post("/admin/staff/invite", json={"name": "N", "email": inv_email}, headers=owner["w"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_invited"
    for bad in ({"name": "", "email": "a@t.test"}, {"name": "N", "email": "nope"},
                {"name": "N", "email": "b@t.test", "allow": ["staff.manage"]}):
        assert client.post("/admin/staff/invite", json=bad, headers=owner["w"]).status_code == 422, bad


def test_invite_expired_used_resend_delete(owner, _env, mails):
    w = owner["w"]
    st, token, _ = _invite(owner, mails)
    _sql("UPDATE admin_invites SET expires_at = NOW() - INTERVAL '1 second' WHERE staff_id = :s", s=st["id"])
    for r in (_start("invite", token), _complete_invite(token, _env, secret=admin_staff.new_secret())[0]):
        assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_link"), r.text
    # resend → a new link; the old one is dead
    r = client.post(f"/admin/staff/{st['id']}/invite/resend", headers=w)
    assert r.status_code == 200
    new = _token(_last(mails, "staff_invite"))
    assert new != token and _live(st["id"], "invite") == 1
    st2, old2, _ = _invite(owner, mails)
    assert client.post(f"/admin/staff/{st2['id']}/invite/resend", headers=w).status_code == 200
    assert _start("invite", old2).status_code == 400
    r, _ = _complete_invite(new, _env)
    assert r.status_code == 200
    # used link · resend / delete of an active staff member → 409
    assert _complete_invite(new, _env, secret=admin_staff.new_secret())[0].status_code == 400
    r = client.post(f"/admin/staff/{st['id']}/invite/resend", headers=w)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "not_invited")
    r = client.delete(f"/admin/staff/{st['id']}", headers=w)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "staff_active")
    assert client.delete(f"/admin/staff/{_member(status='suspended')['id']}", headers=w).status_code == 409
    # cancel an invite → its link dies + the row is gone
    st3, tok3, _ = _invite(owner, mails)
    assert client.delete(f"/admin/staff/{st3['id']}", headers=w).status_code == 200
    assert _start("invite", tok3).status_code == 400
    assert not _sql("SELECT 1 FROM admin_staff WHERE id = :i", i=st3["id"])
    assert not _sql("SELECT 1 FROM admin_invites WHERE staff_id = :i", i=st3["id"])
    assert client.delete("/admin/staff/999999999", headers=w).status_code == 404


def test_wrong_code_keeps_link_bad_shape_counts_nothing(owner, _env, mails):
    st, token, _ = _invite(owner, mails)
    secret = _start("invite", token).json()["data"]["secret"]
    good = _code(secret, _env)
    wrong = str((int(good) + 1) % 1_000_000).zfill(6)
    r = client.post("/staff/invite/complete", json={"token": token, "password": PASSPHRASE, "code": wrong})
    assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_code")
    before = dict(srv._rate_store.items())
    for bad in ("12ab56", "12345", "", None, "1234567"):
        r = client.post("/staff/invite/complete", json={"token": token, "password": PASSPHRASE, "code": bad})
        assert r.status_code == 422, bad
    assert dict(srv._rate_store.items()) == before                 # nothing counted
    r = client.post("/staff/invite/complete", json={"token": token, "password": PASSPHRASE, "code": good})
    assert r.status_code == 200, r.text                            # the wrong code did not use the link


# ── C. concurrency ──
def test_complete_twice_at_once_one_wins(owner, _env, mails):
    for _ in range(3):
        st, token, _ = _invite(owner, mails)
        secret = _start("invite", token).json()["data"]["secret"]
        code = _code(secret, _env)
        res = _burst(2, lambda i: client.post("/staff/invite/complete",
                                              json={"token": token, "password": PASSPHRASE, "code": code}))
        assert sorted(r.status_code for r in res) == [200, 400], [r.text for r in res]
        assert _sql("SELECT COUNT(*) FROM admin_recovery_codes WHERE subject = :s",
                    s=f"staff:{st['id']}")[0][0] == 10


def test_resend_vs_complete(owner, _env, mails):
    for _ in range(4):
        st, token, _ = _invite(owner, mails)
        secret = _start("invite", token).json()["data"]["secret"]
        code = _code(secret, _env)

        def go(i):
            if i == 0:
                return client.post(f"/admin/staff/{st['id']}/invite/resend", headers=owner["w"])
            return client.post("/staff/invite/complete", json={"token": token, "password": PASSPHRASE, "code": code})
        resend, comp = _burst(2, go)
        status = _sql("SELECT status FROM admin_staff WHERE id = :i", i=st["id"])[0][0]
        if comp.status_code == 200:      # the old link completed first → the resend found an active member
            assert resend.status_code == 409 and status == "active", resend.text
        else:                            # the resend won → the old link failed, a new one is live
            assert comp.status_code == 400 and resend.status_code == 200 and status == "invited", comp.text
            assert _live(st["id"], "invite") == 1


def test_forgot_twice_one_live_link_and_reset_once(mails, _env):
    st = _member(_role(["users.view"]))
    for _ in range(3):
        _burst(2, lambda i: client.post(FORGOT, json={"email": st["email"]}))
        assert _live(st["id"], "password_reset") == 1
        srv._rate_store.clear()
    token = _token(_last(mails, "staff_password_reset"))
    res = _burst(2, lambda i: client.post("/staff/password-reset/complete",
                                          json={"token": token, "password": f"new pass phrase {i} ok"}))
    assert sorted(r.status_code for r in res) == [200, 400], [r.text for r in res]


# ── D. password reset ──
def test_password_reset(mails, _env):
    st = _member(_role(["users.view"]))
    tok = _staff_token(st, _env)
    enc = _sql("SELECT mfa_secret_enc FROM admin_staff WHERE id = :i", i=st["id"])[0][0]
    r = client.post(FORGOT, json={"email": st["email"].upper()})
    assert r.status_code == 200 and r.json() == {"ok": True, "data": {"sent": True}}
    to, tpl, vars_ = _last(mails, "staff_password_reset")
    assert to == st["email"] and vars_["minutes"] == 30 and "/staff/password-reset#t=" in vars_["link"]
    ttl = _sql("SELECT EXTRACT(EPOCH FROM expires_at - created_at) FROM admin_invites WHERE staff_id = :s", s=st["id"])
    assert abs(float(ttl[0][0]) - 1800) < 5
    token = _token(_last(mails, "staff_password_reset"))
    r = client.post("/staff/password-reset/complete", json={"token": token, "password": "short pass"})
    assert r.status_code == 422
    r = client.post("/staff/password-reset/complete", json={"token": token, "password": PASSPHRASE})
    assert r.status_code == 200, r.text
    assert client.get("/admin/users", headers=_hdr(tok)).status_code == 401          # old token dead
    row = _sql("SELECT mfa_secret_enc, mfa_enabled_at IS NOT NULL, status FROM admin_staff WHERE id = :i", i=st["id"])[0]
    assert tuple(row) == (enc, True, "active")                                      # authenticator kept
    assert _last(mails, "staff_password_changed")[0] == st["email"]
    assert _login({"email": st["email"], "password": STAFF_PW}).status_code == 401
    r = _login({"email": st["email"], "password": PASSPHRASE})
    assert r.status_code == 200 and r.json()["step"] == "mfa" and "token" not in r.json()   # still asks for TOTP
    assert _staff_login(st["email"], PASSPHRASE, st["secret"], _env).status_code == 200
    assert client.post("/staff/password-reset/complete", json={"token": token, "password": PASSPHRASE}).status_code == 400


def test_password_reset_suspended_unknown_invited(owner, mails, _env):
    w = owner["w"]
    same = {"ok": True, "data": {"sent": True}}
    sus = _member(_role(["users.view"]), status="suspended")
    inv, _, inv_email = _invite(owner, mails)
    mails.clear()
    for email in (sus["email"], inv_email, "nobody@t.test"):
        r = client.post(FORGOT, json={"email": email})
        assert r.status_code == 200 and r.json() == same, email
    assert mails == []
    # link issued while active → suspended → the link fails and never re-activates
    st = _member(_role(["users.view"]))
    client.post(FORGOT, json={"email": st["email"]})
    token = _token(_last(mails, "staff_password_reset"))
    assert client.post(f"/admin/staff/{st['id']}/suspend", headers=w).status_code == 200
    r = client.post("/staff/password-reset/complete", json={"token": token, "password": PASSPHRASE})
    assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_link")
    assert _sql("SELECT status FROM admin_staff WHERE id = :i", i=st["id"])[0][0] == "suspended"
    # wrong kind: an invite token on the password reset route → the same error
    _, inv_tok, _ = _invite(owner, mails)
    r = client.post("/staff/password-reset/complete", json={"token": inv_tok, "password": PASSPHRASE})
    assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_link")


# ── E. mfa reset ──
def test_mfa_reset(owner, mails, _env):
    w = owner["w"]
    st = _member(_role(["users.view"]))
    _sql("INSERT INTO admin_recovery_codes (subject, code_hash) VALUES (:s, :h)", s=f"staff:{st['id']}",
         h=admin_staff.recovery_hash("abcde-fghjk"))
    tok = _staff_token(st, _env)
    r = client.post(f"/admin/staff/{st['id']}/mfa-reset", headers=w)
    assert r.status_code == 200 and r.json()["data"]["mfa_bound"] is False
    assert client.get("/admin/users", headers=_hdr(tok)).status_code == 401              # dies at once
    assert _login({"email": st["email"], "password": STAFF_PW}).status_code == 401       # password alone: nothing
    assert not _sql("SELECT 1 FROM admin_recovery_codes WHERE subject = :s", s=f"staff:{st['id']}")
    to, tpl, vars_ = _last(mails, "staff_mfa_reset")
    assert to == st["email"] and vars_["hours"] == 24 and "/staff/mfa-reset#t=" in vars_["link"]
    token = _token(_last(mails, "staff_mfa_reset"))
    assert client.post("/staff/invite/start", json={"token": token}).status_code == 400   # other kind
    secret = _start("mfa-reset", token).json()["data"]["secret"]
    r = client.post("/staff/mfa-reset/complete", json={"token": token, "code": _code(secret, _env)})
    assert r.status_code == 200 and len(r.json()["data"]["recovery_codes"]) == 10, r.text
    assert "panel" not in r.json()["data"]
    t = _ticket({"email": st["email"], "password": STAFF_PW})                            # password unchanged
    assert _login({"ticket": t, "code": "abcde-fghjk"}).status_code == 401              # old recovery code dead
    t = _ticket({"email": st["email"], "password": STAFF_PW})
    assert _login({"ticket": t, "code": _code(st["secret"], _env)}).status_code == 401  # old authenticator dead
    assert _staff_login(st["email"], STAFF_PW, secret, _env).status_code == 200
    # invited / suspended → 409 not_active
    inv, _, _ = _invite(owner, mails)
    r = client.post(f"/admin/staff/{inv['id']}/mfa-reset", headers=w)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "not_active")


# ── F. secrets · emails · limits ──
def test_no_token_secret_or_hash_leaks(owner, mails, _env, capsys, caplog):
    replies = []
    st, inv_tok, email = _invite(owner, mails)
    rs = _start("invite", inv_tok)
    start_secret = rs.json()["data"]["secret"]
    rc, _ = _complete_invite(inv_tok, _env, secret=start_secret)
    replies += [rc]
    replies.append(client.post(f"/admin/staff/{st['id']}/mfa-reset", headers=owner["w"]))
    mfa_tok = _token(_last(mails, "staff_mfa_reset"))
    rs2 = _start("mfa-reset", mfa_tok)
    secret2 = rs2.json()["data"]["secret"]
    replies.append(client.post("/staff/mfa-reset/complete", json={"token": mfa_tok, "code": _code(secret2, _env)}))
    replies.append(client.post(FORGOT, json={"email": email}))
    pw_tok = _token(_last(mails, "staff_password_reset"))
    replies.append(client.post("/staff/password-reset/complete", json={"token": pw_tok, "password": "another pass 123"}))
    replies.append(client.get("/admin/staff", headers=owner["r"]))
    assert all(r.status_code == 200 for r in replies), [r.text for r in replies]
    pw_hash, enc = _sql("SELECT password_hash, mfa_secret_enc FROM admin_staff WHERE id = :i", i=st["id"])[0]
    secrets_ = {"invite_token": inv_tok, "mfa_token": mfa_tok, "pw_token": pw_tok, "secret1": start_secret,
                "secret2": secret2, "password_hash": pw_hash, "mfa_secret_enc": enc,
                **{f"hash_{n}": admin_staff.link_hash(t) for n, t in (("i", inv_tok), ("m", mfa_tok), ("p", pw_tok))}}
    out = capsys.readouterr()
    places = {"replies": "".join(r.text for r in replies), "logs": out.out + out.err + caplog.text,
              "audit": repr(_sql("SELECT * FROM admin_audit_log"))}
    leaks = [(p, n) for p, text in places.items() for n, v in secrets_.items() if v and v in text]
    assert not leaks, leaks
    # the start replies carry their own secret only
    assert inv_tok not in rs.text and mfa_tok not in rs2.text
    # audit rows name the staff member, never a token
    acts = {a for a, in _sql("SELECT action FROM admin_audit_log WHERE actor = :a", a=f"staff:{st['id']}")}
    assert {"staff_invite_complete", "staff_mfa_reset_complete", "staff_password_reset_complete"} <= acts
    # no panel path in any email
    for _, tpl, vars_ in mails:
        msg = email_service.render(tpl, vars_)
        text = msg["subject"] + msg["html"] + msg["text"]
        assert "tw-ctrl" not in text and (not srv.ADMIN_URL_TOKEN or srv.ADMIN_URL_TOKEN not in text), tpl


@pytest.mark.parametrize("path,body", [
    ("/staff/invite/start", {"token": "t" * 43}),
    ("/staff/invite/complete", {"token": "t" * 43, "password": PASSPHRASE, "code": "123456"}),
    ("/staff/mfa-reset/start", {"token": "t" * 43}),
    ("/staff/mfa-reset/complete", {"token": "t" * 43, "code": "123456"}),
    ("/staff/password-reset/complete", {"token": "t" * 43, "password": PASSPHRASE}),
])
def test_public_link_routes_429(db, path, body):
    per_token, per_ip = tw_settings.rate("staff_link_token")[0], tw_settings.rate("staff_link_ip")[0]
    for _ in range(per_token):
        assert client.post(path, json=body).status_code == 400
    assert client.post(path, json=body).status_code == 429                    # the same link
    for i in range(per_ip - per_token):
        assert client.post(path, json=dict(body, token=f"other-{i}")).status_code == 400
    assert client.post(path, json=dict(body, token="fresh")).status_code == 429   # the same IP


def test_forgot_429(db, mails):
    per_email, per_ip = tw_settings.rate("staff_forgot_email")[0], tw_settings.rate("staff_forgot_ip")[0]
    for _ in range(per_email):
        assert client.post(FORGOT, json={"email": "a@t.test"}).status_code == 200
    assert client.post(FORGOT, json={"email": "a@t.test"}).status_code == 429
    for i in range(per_ip - per_email):
        assert client.post(FORGOT, json={"email": f"b{i}@t.test"}).status_code == 200
    assert client.post(FORGOT, json={"email": "c@t.test"}).status_code == 429
