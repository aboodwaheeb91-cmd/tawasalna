"""
test_account_purge_85c.py — task 8.5c: final purge 30 days after deletion + storage files deleted with retries (F27 ·
docs/rules/account-deletion.md «الحذف النهائي» · SYSTEMS_INDEX §25i).

Real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped, and with TW_SECURITY_TESTS_REQUIRED=1
(CI) a skip is a failure — tests/conftest.py SECURITY_TESTS) + real FastAPI app (in-process HTTP). Storage = a
local HTTP server behind the real server.storage_delete / storage_list (only the base URL points at it):
  old account → files deleted → DB scrubbed per the table → done · newer one untouched · file failure → DB
  untouched, the next attempt finishes · 404 = success · twice = same state · restore vs purge one state + 409 ·
  the other side keeps conversation / application / appointment as «حساب محذوف» · same e-mail = a brand-new
  account · retention periods · no personal value left anywhere (sentinel scan of every text column).
Run: python -m pytest tests/test_account_purge_85c.py -q
"""
import json, os, sys, threading, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest

import account_deletion as ad
import account_purge
import auth
import server as srv
from test_admin_security_84c0 import _env, _migrated, client, db  # noqa: F401 — fixtures
from test_account_deletion_85a import (  # noqa: F401 — _env85 autouse (emails off) + helpers
    PW, _apply, _appt, _delete, _env85, _h, _job, _label, _owner, _restore, _sql)

PROJECT = "https://proj85c.supabase.co"


# ── local storage stand-in (HTTP) ──
class _Store:
    def __init__(self):
        self.objects = set()      # (bucket, name)
        self.fail = set()         # names answering 500
        self.old_404 = False      # answer "not found" the old way (400 + statusCode "404")
        self.deletes = []         # (bucket, name)
        self.keys = set()


def _handler(store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_DELETE(self):
            store.keys.add(self.headers.get("apikey"))
            parts = self.path.split("/storage/v1/object/", 1)[1].split("/", 1)
            bucket, name = parts[0], parts[1]
            store.deletes.append((bucket, name))
            if name in store.fail:
                return self._send(500, {"error": "boom"})
            if (bucket, name) not in store.objects:
                return self._send(400, {"statusCode": "404", "error": "not_found"}) if store.old_404 \
                    else self._send(404, {"error": "not_found"})
            store.objects.discard((bucket, name))
            self._send(200, {"message": "Successfully deleted"})

        def do_POST(self):
            store.keys.add(self.headers.get("apikey"))
            bucket = self.path.rsplit("/", 1)[1]
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            names = sorted(n for b, n in store.objects if b == bucket and body.get("search", "") in n)
            off, lim = int(body.get("offset", 0)), int(body.get("limit", 100))
            self._send(200, [{"name": n} for n in names[off:off + lim]])
    return H


@pytest.fixture
def store(monkeypatch):
    st = _Store()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(st))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_test85c")
    monkeypatch.setattr(srv, "_supabase_base_url", lambda: f"http://127.0.0.1:{httpd.server_address[1]}")
    yield st
    httpd.shutdown()


# ── data ──
def _user(ut):
    n = uuid.uuid4().hex[:10]
    name, email = "Sentinel" + n, "sentinel" + n + "@t85c.test"
    phone = "+9627" + str(int(n, 16))[:8]
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) VALUES (:t, :n, :e, :h, :ut) "
                   "RETURNING id, tw_id", t=("C" if ut == "co" else "U") + n, n=name, e=email,
                   h=auth.hash_password(PW), ut=ut)[0]
    return {"id": int(uid), "tw": tw, "email": email, "name": name, "phone": phone, "ut": ut}


def _obj(u, kind, ext="png"):
    return f"{u['id']}_{kind}_{uuid.uuid4().hex[:12]}.{ext}"


def _seed(u, store, other):
    """The person's files + rows in the tables the purge handles."""
    uid = u["id"]
    av, cv, idf, sf, orphan = (_obj(u, "employee-avatar"), _obj(u, "employee-cover"), _obj(u, "kyc-id-front"),
                               _obj(u, "kyc-selfie"), _obj(u, "employee-avatar", "jpg"))
    store.objects |= {("avatars", av), ("avatars", cv), ("kyc-docs", idf), ("kyc-docs", sf), ("avatars", orphan)}
    pub = PROJECT + "/storage/v1/object/public/avatars/"
    _sql("INSERT INTO profiles (user_id, avatar_url, cover_url, headline, phone, bio) VALUES (:u, :a, :c, :h, :p, :b) "
         "ON CONFLICT (user_id) DO UPDATE SET avatar_url = :a, cover_url = :c, headline = :h, phone = :p, bio = :b",
         u=uid, a=pub + av, c=pub + cv, h="Headline " + u["name"], p=u["phone"], b="bio " + u["email"])
    _sql("INSERT INTO kyc_submissions (user_id, step, phone, id_front_url, selfie_url) VALUES (:u, 3, :p, :i, :s)",
         u=uid, p=u["phone"], i="kyc-docs/" + idf, s="kyc-docs/" + sf)
    _sql("INSERT INTO experience (user_id, title, company) VALUES (:u, 'Dev', :c)", u=uid, c="co of " + u["name"])
    _sql("INSERT INTO profile_follows (follower_id, followed_id) VALUES (:a, :b), (:b, :a)", a=uid, b=other["id"])
    _sql("INSERT INTO notifications (user_id, type, title, body, actor_id) VALUES (:o, 'follow', 't', :b, :u)",
         o=other["id"], b=u["name"] + " بدأ بمتابعتك", u=uid)
    _sql("INSERT INTO notifications (user_id, type, title, body) VALUES (:u, 'x', 't', 'b')", u=uid)
    _sql("INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)", a=other["id"], b=uid)
    _sql("INSERT INTO email_send_log (template_key, category, status, user_id) VALUES ('k', 'security', 'sent', :u)",
         u=uid)
    _sql("INSERT INTO reports (reporter_id, reported_id, report_type, reason, target_url) "
         "VALUES (:u, :o, 'spam', :r, :t), (:o, :u, 'spam', :r2, :t2)", u=uid, o=other["id"],
         r="report by " + u["email"], t="/u/" + other["tw"], r2="about " + u["name"], t2="/u/" + u["tw"])
    _sql("INSERT INTO admin_audit_log (actor, action, target, result, status, new_value) "
         "VALUES ('owner', 'suspend_user', :t, 'ok', 200, 'reason text'), "
         "('owner', 'x', 'id=1', 'ok', 200, :v)", t=f"user_id={uid}", v="mentions " + u["email"])
    return {"av": av, "cv": cv, "idf": idf, "sf": sf, "orphan": orphan}


def _deleted(u, days):
    assert _delete(u).status_code == 200
    _sql("UPDATE users SET deleted_at = NOW() - make_interval(days => :d) WHERE id = :u", d=days, u=u["id"])


def _run_job():
    """Through the scheduler (scheduler_jobs → run_due_scheduler_jobs → the account_purge handler)."""
    auth.schedule_job("account_purge", {}, datetime(2000, 1, 1, tzinfo=timezone.utc),
                      "account_purge:test:" + uuid.uuid4().hex)
    res = auth.run_due_scheduler_jobs(limit=50)
    assert res["ok"] is True and any(j["job_type"] == "account_purge" and j["status"] == "done" for j in res["jobs"]), res


def _stage(u):
    r = _sql("SELECT stage, attempts, last_error FROM account_purge WHERE user_id = :u", u=u["id"])
    return tuple(r[0]) if r else None


def _count(table, where, **kw):
    return _sql(f"SELECT COUNT(*) FROM {table} WHERE {where}", **kw)[0][0]


def _identity_absent(text, u):
    for v in (u["tw"], u["email"], u["name"], u["phone"]):
        assert v not in text, (v, text[:300])


def _sentinel_scan(*people):
    """Every text / varchar / jsonb / array column of every public table: no e-mail / name / phone / tw_id left."""
    cols = _sql("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' "
                "AND data_type IN ('text', 'character varying', 'jsonb', 'ARRAY', 'json')")
    hits = []
    for t, c in cols:
        for u in people:
            for v in (u["email"], u["name"], u["phone"], u["tw"]):
                if _sql(f'SELECT COUNT(*) FROM "{t}" WHERE strpos("{c}"::text, :v) > 0', v=v)[0][0]:
                    hits.append((t, c, v))
    assert not hits, hits


# ── 1. old account → files → DB → done · newer one untouched ──
def test_old_account_files_then_db_then_done_newer_untouched(db, store):
    old, recent, other = _user("emp"), _user("emp"), _user("emp")
    f = _seed(old, store, other)
    fr = _seed(recent, store, other)
    foreign = (("avatars", f"{other['id']}_employee-avatar_{uuid.uuid4().hex[:12]}.png"))
    store.objects.add(foreign)
    _deleted(old, 31)
    _deleted(recent, 29)

    _run_job()

    gone = {("avatars", f["av"]), ("avatars", f["cv"]), ("kyc-docs", f["idf"]), ("kyc-docs", f["sf"]),
            ("avatars", f["orphan"])}
    assert gone <= set(store.deletes) and not (gone & store.objects)            # referenced + unreferenced
    assert foreign in store.objects and all(n.startswith(f"{old['id']}_") for _, n in store.deletes)
    assert store.keys == {"sb_secret_test85c"}
    assert _stage(old) == ("done", 0, None)
    tomb = _sql("SELECT tw_id, full_name, email, purged_at IS NOT NULL, deleted_at IS NOT NULL, deleted_kind, "
                "password_hash FROM users WHERE id = :u", u=old["id"])[0]
    assert tomb[0] is None and tomb[1] == "" and tomb[2] == f"#purged:{old['id']}" and tomb[3] and tomb[4]
    assert tomb[5] == "admin"
    assert not auth.verify_password(PW, tomb[6])
    for table, col in (("profiles", "user_id"), ("kyc_submissions", "user_id"), ("experience", "user_id"),
                       ("email_send_log", "user_id"), ("notifications", "user_id"), ("notifications", "actor_id")):
        assert _count(table, f"{col} = :u", u=old["id"]) == 0, table
    assert _count("profile_follows", "follower_id = :u OR followed_id = :u", u=old["id"]) == 0
    assert _count("blocks", "blocked_id = :u", u=old["id"]) == 0
    # reports + audit rows stay with the internal number only
    assert _sql("SELECT COUNT(*), COUNT(reason), COUNT(target_url) FROM reports WHERE reporter_id = :u OR "
                "reported_id = :u", u=old["id"])[0] == [2, 0, 0]
    assert _sql("SELECT new_value FROM admin_audit_log WHERE target = :t AND action = 'suspend_user'",
                t=f"user_id={old['id']}")[0][0] is None
    # the newer account: no file request, every row as it was
    assert not any(n.startswith(f"{recent['id']}_") for _, n in store.deletes)
    assert ("avatars", fr["av"]) in store.objects and _stage(recent) is None
    assert _count("profiles", "user_id = :u", u=recent["id"]) == 1
    assert _sql("SELECT email, purged_at FROM users WHERE id = :u", u=recent["id"])[0] == [recent["email"], None]
    # the admin view: «محذوف نهائياً» state
    dele = client.get(f"/admin/profile/{old['id']}", headers=_owner())
    assert dele.status_code == 200 and dele.json()["profile"]["deletion"]["purge"] == "purged", dele.text
    _identity_absent(dele.text, old)


# ── 2. a file fails → DB untouched → the next attempt finishes · 404 = success ──
def test_file_failure_keeps_db_next_attempt_finishes_404_is_success(db, store):
    u, other = _user("emp"), _user("emp")
    f = _seed(u, store, other)
    store.fail.add(f["idf"])
    store.objects.discard(("avatars", f["cv"]))                                   # already gone → 404 = fine
    _deleted(u, 40)

    out = account_purge.run_daily()
    assert out["files_failed"] == 1 and out["purged"] == 0
    st = _stage(u)
    assert st[0] == "files" and st[1] == 1 and st[2].startswith("storage:1/")
    _identity_absent(st[2], u)
    assert f["idf"] not in st[2]
    assert _sql("SELECT next_attempt_at > NOW() FROM account_purge WHERE user_id = :u", u=u["id"])[0][0]
    assert _sql("SELECT email, purged_at FROM users WHERE id = :u", u=u["id"])[0] == [u["email"], None]
    assert _count("profiles", "user_id = :u", u=u["id"]) == 1 and _count("kyc_submissions", "user_id = :u", u=u["id"]) == 1

    assert account_purge.run_daily()["purged"] == 0                              # not due yet → nothing
    store.fail.clear()
    store.old_404 = True                                                         # the old "not found" shape
    _sql("UPDATE account_purge SET next_attempt_at = NOW() WHERE user_id = :u", u=u["id"])
    assert account_purge.run_daily()["purged"] == 1
    assert _stage(u)[0] == "done" and not any(n.startswith(f"{u['id']}_") for _, n in store.objects)
    assert _count("profiles", "user_id = :u", u=u["id"]) == 0


# ── 3. twice = the same state ──
def test_run_twice_same_state(db, store):
    u, co, other = _user("emp"), _user("co"), _user("emp")
    _seed(u, store, other)
    job = _job(co)
    _apply(job, u)
    _deleted(u, 31)
    _run_job()

    def snap():
        return [_sql("SELECT tw_id, full_name, email, password_hash, session_version, purged_at FROM users "
                     "WHERE id = :u", u=u["id"])[0],
                _sql("SELECT stage, attempts, last_error, updated_at FROM account_purge WHERE user_id = :u",
                     u=u["id"])[0],
                _count("job_applications", "user_id = :u", u=u["id"]), _count("reports", "reporter_id = :u", u=u["id"])]
    first, n_deletes = snap(), len(store.deletes)
    _run_job()
    assert account_purge.purge_db(u["id"]) is False                               # done → never written again
    assert snap() == first and len(store.deletes) == n_deletes


# ── 4. restore vs purge: one consistent state · restore after the start = 409 ──
def test_restore_and_purge_together_consistent_then_409(db, store):
    for _ in range(4):
        u = _user("emp")
        _deleted(u, 31)
        start = threading.Barrier(2)
        errs = []

        def restore():
            start.wait()
            try:
                ad.restore(u["id"], "owner", "r")
            except ad.DeletionError as e:
                errs.append(e.code)

        def claim():
            start.wait()
            account_purge.claim_due()
        ts = [threading.Thread(target=restore), threading.Thread(target=claim)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        deleted = _sql("SELECT deleted_at IS NOT NULL FROM users WHERE id = :u", u=u["id"])[0][0]
        queued = _stage(u) is not None
        # restore won (nothing queued) or the claim won (still deleted + queued + restore refused) — never both
        assert (not deleted and not queued and errs == []) or (deleted and queued and errs == ["purging"]), \
            (deleted, queued, errs)

    u = _user("emp")
    _deleted(u, 31)
    account_purge.claim_due()
    r = _restore(u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "purging", r.text
    account_purge.run_daily()
    r = _restore(u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_purged", r.text
    assert _sql("SELECT deleted_at IS NOT NULL FROM users WHERE id = :u", u=u["id"])[0][0]


# ── 5. the other side keeps the shared records as «حساب محذوف» ──
def test_other_side_keeps_conversation_application_appointment(db, store):
    co, emp = _user("co"), _user("emp")
    _seed(emp, store, co)
    job = _job(co)
    app_id = _apply(job, emp)
    _sql("UPDATE job_applications SET cover_letter = :c WHERE id = :a", c="letter " + emp["phone"], a=app_id)
    _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:c, :e, 'مرحبا'), (:e, :c, 'رد')",
         c=co["id"], e=emp["id"])
    appt = _appt(co, emp, job, app_id, future=False)
    _deleted(emp, 31)
    _run_job()
    assert _stage(emp)[0] == "done"

    hc = _h(co)
    convs = client.get(f"/messages/conversations/{co['id']}", headers=hc)
    mine = [c for c in convs.json()["conversations"] if c["other_id"] == emp["id"]]
    assert len(mine) == 1 and mine[0]["full_name"] == _label() and mine[0]["tw_id"] is None
    _identity_absent(convs.text, emp)
    msgs = client.get(f"/messages/{co['id']}/{emp['id']}", headers=hc)
    assert msgs.status_code == 200 and len(msgs.json()["messages"]) == 2
    _identity_absent(msgs.text, emp)
    r = client.get(f"/jobs/{job}/applicants", headers=hc)
    rows = r.json().get("applicants") or r.json().get("items") or []
    mine = [a for a in rows if a["user_id"] == emp["id"]]
    assert len(mine) == 1 and mine[0]["full_name"] == _label()
    _identity_absent(r.text, emp)
    assert _sql("SELECT cover_letter FROM job_applications WHERE id = :a", a=app_id)[0][0] is None
    for url in (f"/api/appointments/{appt}", f"/api/appointments/{appt}/events"):
        r = client.get(url, headers=hc)
        assert r.status_code == 200, (url, r.text)
        _identity_absent(r.text, emp)
    assert client.get(f"/api/appointments/{appt}", headers=hc).json()["data"]["applicant_name"] == _label()


# ── 6. the same e-mail after the purge = a brand-new account ──
def test_same_email_after_purge_is_a_new_account(db, store):
    old, other = _user("emp"), _user("emp")
    _seed(old, store, other)
    _sql("UPDATE users SET is_verified = TRUE, email_verified = TRUE WHERE id = :u", u=old["id"])
    _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:o, :u, 'hello')", o=other["id"], u=old["id"])
    old_h = _h(old)
    _deleted(old, 31)
    _run_job()

    srv._rate_store.clear()
    body = {"first_name": "Brand", "last_name": "New", "password": PW, "user_type": "emp", "terms_accepted": True,
            "email": old["email"]}
    r = client.post("/auth/register", json=body)
    assert r.status_code in (200, 201), r.text
    new_id = _sql("SELECT id FROM users WHERE email = :e", e=old["email"])[0][0]
    assert new_id != old["id"]
    srv._rate_store.clear()
    login = client.post("/auth/login", json={"email": old["email"], "password": PW})
    assert login.status_code == 200, login.text
    tok = login.json().get("token") or login.json().get("data", {}).get("token")
    hn = {"Authorization": "Bearer " + tok}
    convs = client.get(f"/messages/conversations/{new_id}", headers=hn)
    assert convs.status_code == 200 and convs.json()["conversations"] == []
    assert _count("messages", "sender_id = :n OR receiver_id = :n", n=new_id) == 0
    assert _count("kyc_submissions", "user_id = :n", n=new_id) == 0
    assert _sql("SELECT is_verified, email_verified FROM users WHERE id = :n", n=new_id)[0] == [False, False]
    assert client.post("/auth/verify-token", headers=old_h).status_code == 401      # the old token stays dead


# ── 7. retention periods ──
def test_retention_old_rows_go_newer_stay(db, store):
    p, live, other = _user("emp"), _user("emp"), _user("co")
    _deleted(p, 31)
    _run_job()
    assert _stage(p)[0] == "done"
    appt = _appt(other, live)
    appt_p = _appt(other, p, future=False)

    def audit(target, days):
        return _sql("INSERT INTO admin_audit_log (created_at, actor, action, target, result, status) "
                    "VALUES (NOW() - make_interval(days => :d), 'owner', 'x', :t, 'ok', 200) RETURNING id",
                    d=days, t=target)[0][0]

    def report(rep, days):
        return _sql("INSERT INTO reports (created_at, reporter_id, reported_id, report_type) "
                    "VALUES (NOW() - make_interval(days => :d), :r, :o, 'spam') RETURNING id",
                    d=days, r=rep, o=other["id"])[0][0]

    def event(a, actor, days):
        return _sql("INSERT INTO appointment_events (created_at, appointment_id, actor_id, event_type) "
                    "VALUES (NOW() - make_interval(days => :d), :a, :u, 'note') RETURNING id",
                    d=days, a=a, u=actor)[0][0]
    a_old, a_new, a_live = audit(f"user_id={p['id']}", 731), audit(f"user_id={p['id']}", 700), audit(
        f"user_id={live['id']}", 900)
    r_old, r_new, r_live = report(p["id"], 366), report(p["id"], 300), report(live["id"], 900)
    e_old, e_new, e_live, e_appt = event(appt, p["id"], 366), event(appt, p["id"], 300), event(appt, live["id"], 900), \
        event(appt_p, other["id"], 366)

    out = account_purge.retention()
    assert out["admin_audit_log"] == 1 and out["reports"] == 1 and out["appointment_events"] == 2, out
    ids = lambda t: {r[0] for r in _sql(f"SELECT id FROM {t}")}
    assert a_old not in ids("admin_audit_log") and {a_new, a_live} <= ids("admin_audit_log")
    assert r_old not in ids("reports") and {r_new, r_live} <= ids("reports")
    assert not ({e_old, e_appt} & ids("appointment_events")) and {e_new, e_live} <= ids("appointment_events")


# ── 8. no personal value left anywhere ──
def test_no_personal_value_left_sentinel_scan(db, store):
    emp, co, other = _user("emp"), _user("co"), _user("emp")
    _seed(emp, store, other)
    _seed(co, store, other)
    _sql("INSERT INTO company_profiles (user_id, description, contact_email) VALUES (:u, :d, :e) "
         "ON CONFLICT (user_id) DO UPDATE SET description = :d, contact_email = :e",
         u=co["id"], d="about " + co["name"], e=co["email"])
    _sql("INSERT INTO company_posts (company_id, body) VALUES (:u, :b)", u=co["id"], b="post by " + co["name"])
    job = _sql("INSERT INTO jobs (company_id, title, description, status) VALUES (:c, 'Role', :d, 'active') "
               "RETURNING id", c=co["id"], d="call " + co["phone"])[0][0]
    app_id = _apply(job, emp)
    _sql("UPDATE job_applications SET cover_letter = :c WHERE id = :a", c="I am " + emp["name"], a=app_id)
    appt = _appt(co, emp, job, app_id, future=False)
    _sql("UPDATE appointments SET representative_name = :n, notes = :x WHERE id = :a", n=co["name"],
         x="note " + co["email"], a=appt)
    _sql("INSERT INTO support_tickets (public_id, user_id, category, subject) VALUES (:p, :u, 'account', :s)",
         p="T" + uuid.uuid4().hex[:10], u=emp["id"], s="help " + emp["email"])
    _deleted(emp, 31)
    _deleted(co, 45)
    _run_job()
    assert _stage(emp)[0] == "done" and _stage(co)[0] == "done"
    assert _count("job_applications", "id = :a", a=app_id) == 1 and _count("appointments", "id = :a", a=appt) == 1
    assert _count("jobs", "id = :j", j=job) == 1 and _count("company_posts", "company_id = :c", c=co["id"]) == 0
    _sentinel_scan(emp, co)


# ── 9. the daily job is ensured by the cycle, never due at creation ──
def test_cycle_ensures_next_daily_job(db, store):
    auth.run_scheduler_cycle()
    auth.run_scheduler_cycle()
    rows = _sql("SELECT status, run_at > NOW(), dedupe_key FROM scheduler_jobs WHERE job_type = 'account_purge' "
                "AND dedupe_key NOT LIKE 'account_purge:test:%'")
    assert len(rows) == 1 and rows[0][0] == "pending" and rows[0][1] is True, rows
