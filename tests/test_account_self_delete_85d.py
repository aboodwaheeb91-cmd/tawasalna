"""
test_account_self_delete_85d.py — task 8.5d: the owner's own account delete + «استعادة حسابي» + the security emails +
a conversation with a deleted account (docs/rules/account-deletion.md → حذف صاحب الحساب والاستعادة · SYSTEMS_INDEX §25i).

Real FastAPI app (in-process HTTP) + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and
with TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py SECURITY_TESTS):
  delete: another user's path 403 (nothing changes) · password / confirm 422 (nothing reserved) · wrong password 422 ·
  bucket full → 429 without bcrypt · success → old token 401 + jobs closed + interviews cancelled + one email ·
  two parallel deletes → one change, effects once, email once.
  restore: unknown email = wrong password = deleted + wrong password (same reply) · admin delete 403 · expired 409 ·
  purge started 409 · restore vs purge claim → exactly one wins · two parallel restores → changed once, email once ·
  success → working token, old token dead, jobs stay closed.
  login: restorable for self in grace / admin / expired / purging.
  messaging: peer_deleted only with earlier messages (else not_found) · sending refused.
Run: python -m pytest tests/test_account_self_delete_85d.py -q
"""
import os, sys, threading, uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import account_purge
import auth
import email_service
import server as srv
import tw_settings
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    _env, _migrated, client, db)

PW = "Passw0rd-85d!"
_REAL_SEND = email_service.send_email


@pytest.fixture(autouse=True)
def _env85d(monkeypatch, _env):
    monkeypatch.setattr(srv, "_asyncpg_pool", None)            # HTTP tests → pg8000 path
    monkeypatch.setattr(srv, "schedule_message_email", lambda *a, **k: None)
    sent = []
    lock = threading.Lock()

    def _send(to, template, vars=None, **k):
        with lock:
            sent.append((to, template, dict(vars or {})))
        return {"ok": True}
    monkeypatch.setattr(email_service, "send_email", _send)
    monkeypatch.setattr(email_service, "can_send", lambda *a, **k: True)
    monkeypatch.setattr(auth, "_notification_email", lambda *a, **k: None)
    srv._pwd_changed_cache.clear()
    yield sent


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut="emp"):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, :h, :ut) RETURNING id, tw_id",
        t=("C" if ut == "co" else "U") + n, n="User" + n, e=n + "@t85d.test", h=auth.hash_password(PW), ut=ut)[0]
    return {"id": int(uid), "tw": tw, "email": n + "@t85d.test", "ut": ut, "name": "User" + n}


def _h(u, sv=0):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": sv, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _del(u, body=None, hdr=None, path_id=None):
    return client.request("DELETE", f"/auth/user/{path_id or u['id']}/delete", headers=hdr or _h(u), json=body)


def _ok_body():
    return {"password": PW, "confirm": "delete"}


def _restore(email, password=PW):
    srv._rate_store.clear()
    return client.post("/auth/restore", json={"email": email, "password": password})


def _login(email, password=PW):
    srv._rate_store.clear()
    return client.post("/auth/login", json={"email": email, "password": password})


def _job(co, status="active"):
    return int(_sql("INSERT INTO jobs (company_id, title, status) VALUES (:c, :t, :s) RETURNING id",
                    c=co["id"], t="وظيفة " + uuid.uuid4().hex[:6], s=status)[0][0])


def _apply(job, emp, status="pending"):
    return int(_sql("INSERT INTO job_applications (job_id, user_id, status) VALUES (:j, :u, :s) RETURNING id",
                    j=job, u=emp["id"], s=status)[0][0])


def _appt(co, emp):
    aid = int(_sql(
        "INSERT INTO appointments (company_id, applicant_id, created_by, status, mode, scheduled_at) "
        "VALUES (:c, :e, :c, 'confirmed', 'online', NOW() + interval '3 days') RETURNING id",
        c=co["id"], e=emp["id"])[0][0])
    for u, role in ((co, "company"), (emp, "applicant")):
        _sql("INSERT INTO appointment_participants (appointment_id, user_id, role, can_message, can_decide) "
             "VALUES (:a, :u, :r, TRUE, TRUE)", a=aid, u=u["id"], r=role)
    return aid


def _deleted(u):
    return _sql("SELECT deleted_at IS NOT NULL, deleted_kind, session_version FROM users WHERE id = :u", u=u["id"])[0]


def _parallel(*fns):
    out, start = [None] * len(fns), threading.Barrier(len(fns))

    def go(i):
        start.wait()
        out[i] = fns[i]()
    ts = [threading.Thread(target=go, args=(i,)) for i in range(len(fns))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return out


def _age(u, days):
    """Test data only: move the deletion back in time."""
    _sql("UPDATE users SET deleted_at = NOW() - make_interval(days => :d) WHERE id = :u", d=days, u=u["id"])


def _days():
    return int(tw_settings.limit("account_purge_days"))


# ══ delete ══
def test_delete_other_users_path_403_nothing_changes(db):
    me, other = _user(), _user()
    r = _del(me, _ok_body(), path_id=other["id"])
    assert r.status_code == 403 and other["email"] not in r.text
    assert _deleted(other) == [False, None, 0] and _deleted(me) == [False, None, 0]
    assert client.request("DELETE", f"/auth/user/{me['id']}/delete", json=_ok_body()).status_code == 401


def test_delete_password_and_confirm_required_without_reservation(db, monkeypatch):
    me = _user()
    calls = []
    monkeypatch.setattr(srv, "check_user_password", lambda *a: calls.append(a) or True)
    for body in (None, {}, {"confirm": "delete"}, {"password": "", "confirm": "delete"}):
        r = _del(me, body)
        assert r.status_code == 422 and r.json()["error"]["code"] == "required" \
            and r.json()["error"]["field"] == "password", r.text
    for confirm in ("", "Delete", "حذف", "delete "):
        r = _del(me, {"password": PW, "confirm": confirm})
        assert r.status_code == 422 and r.json()["error"]["code"] == "confirm_required" \
            and r.json()["error"]["field"] == "confirm", r.text
    assert calls == [] and _deleted(me)[0] is False
    # nothing was reserved: the full budget is still there
    assert srv._rate_store.get(f"account_delete:{me['id']}") in (None, [], ())


def test_wrong_password_422_not_401_session_stays(db):
    me = _user()
    r = _del(me, {"password": "Wrong-1234", "confirm": "delete"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "wrong_password" \
        and r.json()["error"]["field"] == "password", r.text
    assert _deleted(me)[0] is False
    assert client.post("/auth/verify-token", headers=_h(me)).status_code == 200


def test_bucket_full_429_without_bcrypt(db, monkeypatch):
    me = _user()
    limit = tw_settings.rate("account_delete")[0]
    for _ in range(limit):
        assert _del(me, {"password": "Wrong-1234", "confirm": "delete"}).status_code == 422

    def _boom(*a):
        raise AssertionError("bcrypt must not run when the bucket is full")
    monkeypatch.setattr(srv, "check_user_password", _boom)
    r = _del(me, _ok_body())
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited", r.text
    assert _deleted(me)[0] is False


def test_company_delete_success_effects_and_one_email(db, _env85d):
    co, a = _user("co"), _user("emp")
    j = _job(co)
    _apply(j, a)
    ap = _appt(co, a)
    old = _h(co)
    r = _del(co, _ok_body())
    assert r.status_code == 200 and r.json()["data"]["deleted"] is True, r.text
    assert r.json()["data"]["purge_after"]
    assert _deleted(co)[:2] == [True, "self"]
    assert client.post("/auth/verify-token", headers=old).status_code == 401
    assert _sql("SELECT status FROM jobs WHERE id = :j", j=j)[0][0] == "closed"
    assert _sql("SELECT status FROM appointments WHERE id = :a", a=ap)[0][0] == "cancelled"
    mails = [m for m in _env85d if m[1] == "account_deleted"]
    assert len(mails) == 1 and mails[0][0] == co["email"]
    assert mails[0][2]["date"] and "http" not in str(mails[0][2])
    exp = _sql("SELECT EXTRACT(YEAR FROM deleted_at + make_interval(days => :d))::int FROM users WHERE id = :u",
               d=_days(), u=co["id"])[0][0]
    assert str(exp) in mails[0][2]["date"]
    # the template renders its date and no link (security email)
    msg = email_service.render("account_deleted", {"name": "x", "date": mails[0][2]["date"]})
    assert mails[0][2]["date"] in msg["text"] and "https://" not in msg["text"]


def test_two_parallel_deletes_one_change_effects_once_email_once(db, _env85d, monkeypatch):
    co, a = _user("co"), _user("emp")
    _apply(_job(co), a)
    effects = []
    real = srv.ad.apply_effects
    monkeypatch.setattr(srv.ad, "apply_effects", lambda uid: effects.append(uid) or real(uid))
    h = _h(co)
    r1, r2 = _parallel(lambda: _del(co, _ok_body(), hdr=h), lambda: _del(co, _ok_body(), hdr=h))
    codes = sorted([r1.status_code, r2.status_code])
    assert codes in ([200, 200], [200, 401]), (r1.text, r2.text)   # the loser may already see the dead token
    assert effects == [co["id"]]
    assert len([m for m in _env85d if m[1] == "account_deleted"]) == 1
    assert _deleted(co)[2] == 1                                       # session_version bumped once
    assert _sql("SELECT COUNT(*) FROM notifications WHERE user_id = :u AND type = 'application_closed'",
                u=a["id"])[0][0] == 1


# ══ restore ══
def _self_deleted():
    u = _user()
    assert _del(u, _ok_body()).status_code == 200
    return u


def test_restore_unknown_email_and_wrong_password_same_reply(db):
    u = _self_deleted()
    live = _user()
    nobody = _restore("nobody-" + uuid.uuid4().hex[:6] + "@t85d.test")
    wrong_deleted = _restore(u["email"], "Wrong-1234")
    wrong_live = _restore(live["email"], "Wrong-1234")
    login_wrong = _login(live["email"], "Wrong-1234")
    assert nobody.status_code == wrong_deleted.status_code == wrong_live.status_code == 401
    assert nobody.json() == wrong_deleted.json() == wrong_live.json() == login_wrong.json()
    for r in (nobody, wrong_deleted):
        assert "deleted" not in r.text and "محذوف" not in r.text and "restorable" not in r.text
    assert _deleted(u)[0] is True


def test_restore_not_deleted_409(db):
    u = _user()
    r = _restore(u["email"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_deleted"


def test_restore_admin_deleted_403(db):
    u = _user()
    out = srv.ad.soft_delete(u["id"], "owner", "admin", "سبب")
    assert out["changed"]
    r = _restore(u["email"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "admin_deleted", r.text
    assert r.json()["error"]["message"] == srv._tw_text("auth.restore.err.admin_deleted")
    assert _deleted(u)[:2] == [True, "admin"]


def test_restore_expired_409(db):
    u = _self_deleted()
    _age(u, _days() + 1)
    r = _restore(u["email"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "expired", r.text
    assert _deleted(u)[0] is True


def test_restore_purge_started_409(db):
    u = _self_deleted()
    _sql("INSERT INTO account_purge (user_id) VALUES (:u)", u=u["id"])
    r = _restore(u["email"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "purging", r.text
    assert _deleted(u)[0] is True


def test_restore_and_purge_claim_together_one_wins(db, monkeypatch):
    monkeypatch.setattr(account_purge, "_days", lambda name: 0)   # the claim sees the account as due right away
    for _ in range(4):
        u = _self_deleted()
        srv._rate_store.clear()
        r, _claimed = _parallel(lambda: client.post("/auth/restore", json={"email": u["email"], "password": PW}),
                                account_purge.claim_due)
        queued = bool(_sql("SELECT 1 FROM account_purge WHERE user_id = :u", u=u["id"]))
        is_del = _deleted(u)[0]
        if r.status_code == 200:
            assert not queued and is_del is False, r.text
        else:
            assert r.status_code == 409 and r.json()["error"]["code"] == "purging" and queued and is_del, r.text


def test_two_parallel_restores_changed_once_email_once(db, _env85d):
    u = _self_deleted()
    srv._rate_store.clear()
    body = {"email": u["email"], "password": PW}
    r1, r2 = _parallel(lambda: client.post("/auth/restore", json=body),
                       lambda: client.post("/auth/restore", json=body))
    ok = [r for r in (r1, r2) if r.status_code == 200]
    assert len(ok) >= 1 and all(r.status_code in (200, 409) for r in (r1, r2)), (r1.text, r2.text)
    assert len([m for m in _env85d if m[1] == "account_restored"]) == 1
    assert _deleted(u)[0] is False


def test_restore_success_new_token_works_old_dead_jobs_stay_closed(db, _env85d):
    co = _user("co")
    j = _job(co)
    old = _h(co)
    assert _del(co, _ok_body()).status_code == 200
    r = _restore(co["email"])
    assert r.status_code == 200 and r.json()["restored"] is True, r.text
    tok = r.json()["token"]
    assert "session_version" not in r.json()["user"] and "deleted" not in r.json()["user"]
    assert client.post("/auth/verify-token", headers={"Authorization": "Bearer " + tok}).status_code == 200
    assert client.post("/auth/verify-token", headers=old).status_code == 401
    assert _sql("SELECT status FROM jobs WHERE id = :j", j=j)[0][0] == "closed"
    mails = [m for m in _env85d if m[1] == "account_restored"]
    assert len(mails) == 1 and mails[0][0] == co["email"]
    assert "https://" not in email_service.render("account_restored", {"name": "x"})["text"]
    assert _login(co["email"]).status_code == 200


# ══ login ══
def test_login_restorable_four_cases(db):
    inside = _self_deleted()
    r = _login(inside["email"])
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_deleted" and "token" not in r.json()
    assert r.json()["restorable"] is True and r.json()["restore_until"]

    adm = _user()
    srv.ad.soft_delete(adm["id"], "owner", "admin", None)
    expired = _self_deleted()
    _age(expired, _days() + 1)
    purging = _self_deleted()
    _sql("INSERT INTO account_purge (user_id) VALUES (:u)", u=purging["id"])
    for u in (adm, expired, purging):
        r = _login(u["email"])
        assert r.status_code == 401 and r.json()["error"]["code"] == "account_deleted", r.text
        assert r.json()["restorable"] is False and r.json()["restore_until"] is None
    # wrong password = the normal reply (nothing about the deletion)
    r = _login(inside["email"], "Wrong-1234")
    assert r.status_code == 401 and "restorable" not in r.text and "account_deleted" not in r.text


# ══ messaging ══
def test_peer_deleted_only_with_history_send_refused(db):
    co, talked, stranger = _user("co"), _user("emp"), _user("emp")
    hc = _h(co)
    assert client.post("/messages/send", headers=hc, json={"receiver_id": talked["id"], "content": "مرحبا"}).status_code == 200
    for u in (talked, stranger):
        assert _del(u, _ok_body()).status_code == 200

    st = client.get(f"/messages/can-send/{talked['id']}", headers=hc).json()["data"]
    assert st["can_message"] is False and st["reason"] == "peer_deleted" and st["reason_key"] == "msg.policy.peer_deleted"
    assert st["can_end"] is False
    st = client.get(f"/messages/can-send/{stranger['id']}", headers=hc).json()["data"]
    assert st["can_message"] is False and st["reason"] == "not_found"
    r = client.post("/messages/send", headers=hc, json={"receiver_id": talked["id"], "content": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "peer_deleted"
    r = client.post("/messages/send", headers=hc, json={"receiver_id": stranger["id"], "content": "x"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    # the history stays readable, scrubbed by the server
    msgs = client.get(f"/messages/{co['id']}/{talked['id']}", headers=hc)
    assert msgs.status_code == 200 and len(msgs.json()["messages"]) == 1


# ══ fixes found on the way ══
def test_unknown_email_runs_one_bcrypt_check(db, monkeypatch):
    """/auth/login + /auth/restore: an unknown email costs the same bcrypt check as a real one (no timing tell)."""
    calls = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda p, h: calls.append(1) or real(p, h))
    assert _restore("nobody-" + uuid.uuid4().hex[:6] + "@t85d.test").status_code == 401
    assert _login("nobody-" + uuid.uuid4().hex[:6] + "@t85d.test").status_code == 401
    assert len(calls) == 2


def test_security_email_reaches_a_deleted_recipient(db, monkeypatch):
    """send_email itself never blocks the deletion / restore email of a deleted account (create_notification does)."""
    u = _self_deleted()
    posted = []
    monkeypatch.setattr(email_service, "_api_key", lambda: "re_test_key")
    monkeypatch.setattr(email_service, "_post", lambda payload, key: posted.append(payload) or (200, {"id": "x1"}))
    for tpl, vars_ in (("account_deleted", {"name": u["name"], "date": "1 يناير 2027"}),
                       ("account_restored", {"name": u["name"]})):
        out = _REAL_SEND(u["email"], tpl, vars_)
        assert out["ok"] is True and out["code"] == "sent", (tpl, out)
    assert [p["to"] for p in posted] == [[u["email"]], [u["email"]]]
    assert all("https://" not in p["text"] for p in posted)
