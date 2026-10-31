"""
test_account_deletion_85a.py — task 8.5a: soft account delete + admin restore + «حساب محذوف» (F27 ·
docs/rules/account-deletion.md · SYSTEMS_INDEX §25i).

Real FastAPI app (in-process HTTP) + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped,
and with TW_SECURITY_TESTS_REQUIRED=1 (CI) a skip is a failure — tests/conftest.py SECURITY_TESTS):
  gate 401 / 403 / 428 · session 401 + WS 4008 at once · login 401 account_deleted (wrong password = the normal
  reply) · content hidden + counters down · shared records stay scrubbed (conversation · applicants · pipeline ·
  appointments) and sending refused · company effects (jobs closed · one notice per applicant · interviews
  cancelled) · concurrency · restore (old token dead · jobs stay closed · reason required) · password reset +
  register for a deleted email = the normal reply, no email · rows never removed · self delete still 403.
Run: python -m pytest tests/test_account_deletion_85a.py -q
"""
import os, sys, threading, uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import auth
import email_service
import server as srv
from test_admin_security_84c0 import (  # noqa: F401 — fixtures (_env autouse · _migrated · db)
    _env, _migrated, _staff, _staff_token, client, db)

PW = "Passw0rd-85a!"


@pytest.fixture(autouse=True)
def _env85(monkeypatch, _env):
    monkeypatch.setattr(srv, "_asyncpg_pool", None)            # HTTP tests → pg8000 path
    monkeypatch.setattr(srv, "schedule_message_email", lambda *a, **k: None)
    sent = []
    monkeypatch.setattr(email_service, "send_email", lambda to, *a, **k: sent.append(to) or {"ok": True})
    monkeypatch.setattr(email_service, "can_send", lambda *a, **k: True)
    monkeypatch.setattr(auth, "_notification_email", lambda *a, **k: None)
    srv._pwd_changed_cache.clear()
    yield sent


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(ut, name=None):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, :h, :ut) RETURNING id, tw_id",
        t=("C" if ut == "co" else "U") + n, n=name or ("User" + n), e=n + "@t85a.test",
        h=auth.hash_password(PW), ut=ut)[0]
    avatar = "https://cdn.t85a.test/" + n + ".png"
    _sql("INSERT INTO profiles (user_id, avatar_url, headline, phone) VALUES (:u, :a, :hl, :ph) "
         "ON CONFLICT (user_id) DO UPDATE SET avatar_url = :a, headline = :hl, phone = :ph",
         u=uid, a=avatar, hl="Headline" + n, ph="+9627" + n[:8].translate(str.maketrans("abcdef", "123456")))
    return {"id": int(uid), "tw": tw, "email": n + "@t85a.test", "ut": ut, "name": name or ("User" + n),
            "avatar": avatar, "headline": "Headline" + n}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _owner():
    tok = srv._admin_jwt_issue()                                 # sv 1 = the reset owner row (db fixture)
    return {"X-Admin-Token": tok, "X-Admin-Stepup": srv._admin_step_up_issue("owner", 1, tok)}


def _delete(u, reason=None, hdr=None):
    return client.request("DELETE", f"/admin/user/{u['id']}", headers=_owner() if hdr is None else hdr,
                          json={"reason": reason} if reason is not None else None)


def _restore(u, reason="خطأ بالحذف", hdr=None):
    return client.post(f"/admin/user/{u['id']}/restore", headers=_owner() if hdr is None else hdr, json={"reason": reason})


def _job(co, status="active"):
    return int(_sql("INSERT INTO jobs (company_id, title, status) VALUES (:c, :t, :s) RETURNING id",
                    c=co["id"], t="وظيفة " + uuid.uuid4().hex[:6], s=status)[0][0])


def _apply(job, emp, status="pending"):
    return int(_sql("INSERT INTO job_applications (job_id, user_id, status) VALUES (:j, :u, :s) RETURNING id",
                    j=job, u=emp["id"], s=status)[0][0])


def _appt(co, emp, job=None, app=None, future=True):
    aid = int(_sql(
        "INSERT INTO appointments (job_id, application_id, company_id, applicant_id, created_by, status, mode, "
        "scheduled_at) VALUES (:j, :a, :c, :e, :c, 'confirmed', 'online', NOW() + (:d || ' days')::interval) "
        "RETURNING id", j=job, a=app, c=co["id"], e=emp["id"], d="3" if future else "-3")[0][0])
    for u, role in ((co, "company"), (emp, "applicant")):
        _sql("INSERT INTO appointment_participants (appointment_id, user_id, role, can_message, can_decide) "
             "VALUES (:a, :u, :r, TRUE, TRUE)", a=aid, u=u["id"], r=role)
    return aid


def _notifs(u, type_=None):
    q = "SELECT COUNT(*) FROM notifications WHERE user_id = :u" + (" AND type = :t" if type_ else "")
    return _sql(q, u=u["id"], **({"t": type_} if type_ else {}))[0][0]


def _identity_absent(text, u):
    for v in (u["tw"], u["email"], u["name"], u["avatar"], u["headline"]):
        assert v not in text, (v, text[:400])


def _label():
    return srv._tw_text("account.deleted")


# ── gate ──
def test_gate_401_403_428_and_self_delete_still_403(db, _env):
    target, emp = _user("emp"), _user("emp")
    for call in (lambda h: _delete(target, hdr=h), lambda h: _restore(target, hdr=h)):
        assert call({}).status_code == 401                                         # no token
        assert call(_h(emp)).status_code == 401                                    # a site user JWT
        assert call({"X-Admin-Token": _h(emp)["Authorization"][7:]}).status_code == 401
        st = _staff(role_perms=["users.view", "users.suspend"])                    # admin without the permission
        assert call({"X-Admin-Token": _staff_token(st, _env)}).status_code == 403
        tok = srv._admin_jwt_issue()                                               # owner without step-up
        r = call({"X-Admin-Token": tok})
        assert r.status_code == 428 and "step_up_required" in r.text
    assert _sql("SELECT deleted_at FROM users WHERE id = :u", u=target["id"])[0][0] is None
    assert client.delete(f"/auth/user/{emp['id']}/delete", headers=_h(emp)).status_code == 403
    assert _sql("SELECT deleted_at FROM users WHERE id = :u", u=emp["id"])[0][0] is None
    # the audit log names every refused / accepted call
    assert _sql("SELECT COUNT(*) FROM admin_audit_log WHERE action IN ('delete_user', 'restore_user') "
                "AND target = :t", t=f"user_id={target['id']}")[0][0] >= 10


# ── session + login ──
def test_delete_kills_token_ws_and_login(db):
    emp = _user("emp")
    h = _h(emp)
    with client.websocket_connect(f"/ws/{emp['id']}") as ws:
        ws.send_json({"type": "auth", "token": h["Authorization"][7:]})
        assert ws.receive_json().get("type") == "auth_ok"
        r = _delete(emp, "مخالفة")
        assert r.status_code == 200 and r.json()["data"]["deleted"] is True, r.text
        closed = ws.receive()
        assert closed.get("type") == "websocket.close" and closed.get("code") == 4008, closed
    assert client.post("/auth/verify-token", headers=h).status_code == 401
    assert client.get("/home/feed", headers=h).status_code == 401
    r = client.post("/auth/login", json={"email": emp["email"], "password": PW})
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_deleted" and "token" not in r.text
    srv._rate_store.clear()
    wrong = client.post("/auth/login", json={"email": emp["email"], "password": "Wrong-pass-1"})
    srv._rate_store.clear()
    nobody = client.post("/auth/login", json={"email": "nobody-" + emp["email"], "password": "Wrong-pass-1"})
    assert wrong.status_code == nobody.status_code == 401 and wrong.json() == nobody.json()
    assert "محذوف" not in wrong.text and "account_deleted" not in wrong.text
    adm = client.get(f"/admin/profile/{emp['id']}", headers=_owner()).json()["profile"]["deletion"]
    assert adm["deleted"] and adm["deleted_kind"] == "admin" and adm["deleted_reason"] == "مخالفة"


# ── content hidden + counters ──
def test_content_hidden_and_counters_down(db):
    co, emp, viewer, other_co = _user("co"), _user("emp"), _user("emp"), _user("co")
    post = int(_sql("INSERT INTO company_posts (company_id, body) VALUES (:c, 'منشور') RETURNING id",
                    c=co["id"])[0][0])
    post2 = int(_sql("INSERT INTO company_posts (company_id, body) VALUES (:c, 'منشور') RETURNING id",
                     c=other_co["id"])[0][0])
    r = client.post(f"/company/posts/{post2}/comments", headers=_h(emp), json={"body": "تعليق"})
    assert r.status_code == 200, r.text
    _sql("INSERT INTO profile_follows (follower_id, followed_id) VALUES (:a, :b)", a=emp["id"], b=other_co["id"])
    job = _job(co)
    srv._cache_del("jobs:")

    def counts():
        posts = client.get(f"/company/posts/{other_co['id']}", headers=_h(viewer)).json()
        items = posts.get("posts") or posts.get("items") or []
        cc = [p for p in items if p["id"] == post2][0]["comments_count"]
        prof = client.get(f"/company/profile/{other_co['id']}", headers=_h(viewer)).json()
        return int(cc), int(prof["stats"]["followers_count"])

    assert counts() == (1, 1)
    assert _delete(co).status_code == 200 and _delete(emp).status_code == 200
    for hdr in ({}, _h(viewer)):
        assert client.get(f"/company/profile/{co['id']}", headers=hdr).status_code == 404
        assert client.get(f"/company/posts/{co['id']}", headers=hdr).status_code == 404
        assert client.get(f"/profile/{emp['id']}", headers=hdr).status_code == 404
        assert client.get(f"/jobs/{job}", headers=hdr).status_code == 404
        assert job not in {j["id"] for j in client.get("/jobs", headers=hdr).json()["jobs"]}
    assert client.get(f"/u/{co['tw']}").status_code == 404
    feed = client.get("/home/feed?filter=all&limit=50", headers=_h(viewer)).json()["items"]
    assert post not in {i["id"] for i in feed if i["type"] == "post"}
    ids = {c["id"] for c in client.get(f"/company/posts/{post2}/comments?limit=50", headers=_h(viewer)).json()["comments"]}
    assert r.json()["comment"]["id"] not in ids
    assert counts() == (0, 0)


# ── shared records ──
def test_shared_records_stay_scrubbed_and_sending_refused(db):
    co, emp = _user("co"), _user("emp")
    job = _job(co)
    app_id = _apply(job, emp)
    r = client.post("/messages/send", headers=_h(co), json={"receiver_id": emp["id"], "content": "مرحبا"})
    assert r.status_code == 200, r.text
    _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:e, :c, 'رد')", e=emp["id"], c=co["id"])
    assert client.post(f"/jobs/applications/{app_id}/promote", headers=_h(co)).status_code == 200
    appt = _appt(co, emp, job, app_id, future=False)          # a past one — stays as it is (not cancelled)
    before = {t: _sql(f"SELECT COUNT(*) FROM {t} WHERE {c} = :u", u=emp["id"])[0][0]
              for t, c in (("messages", "sender_id"), ("job_applications", "user_id"), ("appointments", "applicant_id"))}

    assert _delete(emp).status_code == 200
    hc = _h(co)
    convs = client.get(f"/messages/conversations/{co['id']}", headers=hc)
    assert convs.status_code == 200
    mine = [c for c in convs.json()["conversations"] if c["other_id"] == emp["id"]]
    assert len(mine) == 1 and mine[0]["full_name"] == _label() and mine[0]["is_deleted"] is True
    assert mine[0]["tw_id"] is None and mine[0]["avatar_url"] is None
    _identity_absent(convs.text, emp)
    msgs = client.get(f"/messages/{co['id']}/{emp['id']}", headers=hc)
    assert msgs.status_code == 200 and len(msgs.json()["messages"]) == 2, msgs.text
    _identity_absent(msgs.text, emp)
    assert client.get(f"/messages/unread/{co['id']}", headers=hc).json()["count"] == 0
    r = client.post("/messages/send", headers=hc, json={"receiver_id": emp["id"], "content": "x"})
    assert r.status_code == 404, r.text
    assert client.get(f"/messages/can-send/{emp['id']}", headers=hc).json()["data"]["can_message"] is False

    for q in ("", "?view=candidates"):
        r = client.get(f"/jobs/{job}/applicants{q}", headers=hc)
        assert r.status_code == 200, r.text
        rows = r.json().get("applicants") or r.json().get("items") or []
        mine = [a for a in rows if a["user_id"] == emp["id"]]
        assert len(mine) == 1 and mine[0]["full_name"] == _label() and mine[0]["tw_id"] is None
        _identity_absent(r.text, emp)
    for url in ("/api/appointments", f"/api/appointments/{appt}", f"/api/appointments/{appt}/events",
                f"/api/appointments/{appt}/messages"):
        r = client.get(url, headers=hc)
        assert r.status_code == 200, (url, r.text)
        _identity_absent(r.text, emp)
    room = client.get(f"/api/appointments/{appt}", headers=hc).json()["data"]
    assert room["applicant_name"] == _label() and not room["applicant_avatar"] and room["status"] == "confirmed"
    after = {t: _sql(f"SELECT COUNT(*) FROM {t} WHERE {c} = :u", u=emp["id"])[0][0]
             for t, c in (("messages", "sender_id"), ("job_applications", "user_id"), ("appointments", "applicant_id"))}
    assert after == before                                    # nothing removed
    assert _sql("SELECT COUNT(*) FROM users WHERE id = :u", u=emp["id"])[0][0] == 1


# ── company effects ──
def test_company_delete_closes_jobs_notifies_once_cancels_interviews(db):
    co, a1, a2, hired, other = _user("co"), _user("emp"), _user("emp"), _user("emp"), _user("emp")
    j1, j2, j3 = _job(co), _job(co), _job(co, "paused")
    _apply(j1, a1); _apply(j2, a1); _apply(j3, a2); _apply(j1, hired, "hired")
    up = _appt(co, a1, j1)
    up_other = _appt(_user("co"), other)                       # someone else's — untouched
    co_notifs = _notifs(co)

    r = _delete(co)
    assert r.status_code == 200 and r.json()["data"]["changed"] is True
    assert {row[0] for row in _sql("SELECT status FROM jobs WHERE id IN (:a, :b, :c)", a=j1, b=j2, c=j3)} == {"closed"}
    assert _notifs(a1, "application_closed") == 1 and _notifs(a2, "application_closed") == 1
    assert _notifs(hired, "application_closed") == 0
    txt = _sql("SELECT title || ' ' || body FROM notifications WHERE user_id = :u AND type = 'application_closed'",
               u=a1["id"])[0][0]
    assert co["name"] not in txt
    assert _sql("SELECT status FROM appointments WHERE id = :a", a=up)[0][0] == "cancelled"
    assert _sql("SELECT status FROM appointments WHERE id = :a", a=up_other)[0][0] == "confirmed"
    assert _notifs(a1, "appointment_cancelled") == 1
    body = _sql("SELECT body FROM notifications WHERE user_id = :u AND type = 'appointment_cancelled'", u=a1["id"])[0][0]
    assert co["name"] not in body
    assert _notifs(co) == co_notifs                            # nothing to the deleted account

    r = _delete(co)                                            # twice → nothing new
    assert r.status_code == 200 and r.json()["data"]["changed"] is False
    assert _notifs(a1, "application_closed") == 1 and _notifs(a1, "appointment_cancelled") == 1

    # a deleted person: upcoming interviews cancelled too, the company gets the notice
    co2, p = _user("co"), _user("emp")
    a = _appt(co2, p)
    assert _delete(p).status_code == 200
    assert _sql("SELECT status FROM appointments WHERE id = :a", a=a)[0][0] == "cancelled"
    assert _notifs(co2, "appointment_cancelled") == 1
    assert p["name"] not in _sql("SELECT body FROM notifications WHERE user_id = :u AND type = 'appointment_cancelled'",
                                 u=co2["id"])[0][0]


# ── concurrency ──
def _parallel(*fns):
    out, start = [None] * len(fns), threading.Barrier(len(fns))

    def go(i):
        start.wait()
        out[i] = fns[i]()
    ts = [threading.Thread(target=go, args=(i,)) for i in range(len(fns))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return out


def test_two_deletes_one_state_one_notice(db):
    co, a = _user("co"), _user("emp")
    _apply(_job(co), a)
    h1, h2 = _owner(), _owner()
    r1, r2 = _parallel(lambda: _delete(co, hdr=h1), lambda: _delete(co, hdr=h2))
    assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
    assert sorted([r1.json()["data"]["changed"], r2.json()["data"]["changed"]]) == [False, True]
    assert _notifs(a, "application_closed") == 1
    assert _sql("SELECT session_version FROM users WHERE id = :u", u=co["id"])[0][0] == 1


def test_delete_and_restore_together_consistent(db):
    for _ in range(3):
        emp = _user("emp")
        assert _delete(emp).status_code == 200
        h1, h2 = _owner(), _owner()
        r1, r2 = _parallel(lambda: _delete(emp, hdr=h1), lambda: _restore(emp, hdr=h2))
        assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
        at, by, kind = _sql("SELECT deleted_at, deleted_by, deleted_kind FROM users WHERE id = :u", u=emp["id"])[0]
        assert (at is None) == (by is None) == (kind is None)


# ── restore ──
def test_restore_old_token_dead_jobs_stay_closed_reason_required(db):
    co, viewer = _user("co"), _user("emp")
    job = _job(co)
    h = _h(co)
    assert _delete(co).status_code == 200
    r = _restore(co, "")
    assert r.status_code == 422 and r.json()["error"]["field"] == "reason"
    assert client.post(f"/admin/user/{co['id']}/restore", headers=_owner(), json={}).status_code == 422
    assert _restore(co, "x" * 501).status_code == 422
    assert _sql("SELECT deleted_at FROM users WHERE id = :u", u=co["id"])[0][0] is not None
    r = _restore(co)
    assert r.status_code == 200 and r.json()["data"]["changed"] is True
    srv._pwd_changed_cache.clear()
    assert client.post("/auth/verify-token", headers=h).status_code == 401       # old token stays dead
    assert _sql("SELECT status FROM jobs WHERE id = :j", j=job)[0][0] == "closed"
    assert client.get(f"/company/profile/{co['id']}", headers=_h(viewer)).status_code == 200
    r = client.post("/auth/login", json={"email": co["email"], "password": PW})
    assert r.status_code == 200 and r.json()["token"]
    assert _sql("SELECT new_value FROM admin_audit_log WHERE action = 'restore_user' AND status = 200 "
                "ORDER BY id DESC LIMIT 1")[0][0] == "خطأ بالحذف"
    assert _restore(_user("emp")).json()["data"]["changed"] is False              # not deleted → no change
    assert _restore({"id": 999999999}).status_code == 404


# ── password reset + register for a deleted email ──
def test_reset_and_register_same_reply_no_email(db, _env85):
    gone, live = _user("emp"), _user("emp")
    assert _delete(gone).status_code == 200
    srv._rate_store.clear()
    r_gone = client.post("/auth/password-reset/request", json={"email": gone["email"]})
    r_live = client.post("/auth/password-reset/request", json={"email": live["email"]})
    assert r_gone.status_code == r_live.status_code == 200 and r_gone.json() == r_live.json()
    assert gone["email"] not in _env85 and live["email"] in _env85
    assert _sql("SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = :u", u=gone["id"])[0][0] == 0

    body = {"first_name": "Someone", "last_name": "New", "password": PW, "user_type": "emp", "terms_accepted": True}
    srv._rate_store.clear()
    reg_gone = client.post("/auth/register", json=dict(body, email=gone["email"]))
    srv._rate_store.clear()
    reg_live = client.post("/auth/register", json=dict(body, email=live["email"]))
    assert reg_gone.status_code == reg_live.status_code == 409, (reg_gone.text, reg_live.text)
    assert reg_gone.json() == reg_live.json() and "محذوف" not in reg_gone.text


# ── reports target ──
def test_report_target_of_deleted_account(db):
    reporter, target = _user("emp"), _user("emp")
    _sql("INSERT INTO reports (reporter_id, reported_id, reported_type, report_type, reason) "
         "VALUES (:r, :t, 'user', 'spam', 'x')", r=reporter["id"], t=target["id"])
    assert _delete(target).status_code == 200
    reps = client.get("/admin/reports", headers=_owner()).json()["reports"]
    t = [x for x in reps if x["reported_id"] == target["id"]][0]["target"]
    assert t["deleted"] is True and t["href"] is None and t["name"] is None
    users = client.get(f"/admin/users?q={target['tw']}", headers=_owner()).json()["data"]["items"]
    assert users and users[0]["deleted_at"]
