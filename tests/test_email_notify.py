"""Task 5.1c — notification emails over email_service.send_email (docs/rules/email.md → Notification Emails).

Behaviour only: Resend is faked at the HTTP layer (urllib.request.urlopen inside email_service);
email_send_log / email_notify_prefs / scheduler_jobs / messages / notifications live in a real
PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it).
  - security emails go out even when the notification cap is used up (and are counted apart)
  - notification emails stop at: the cap · the user's preference · the admin switch
    (the in-site notification is still created)
  - messages: only while unread after N minutes, at most one email per conversation per N hours
  - counters (GET /admin/email → stats) match what happened
Run: python -m pytest tests/test_email_notify.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-notify-51c-" + "x" * 32)
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-51c-" + "s" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
KEY = "re_TEST_SECRET_KEY_51c_never_leak"
A, B = "amal@example.com", "bassam@example.com"


class FakeResend:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(json.loads(req.data.decode("utf-8")))

        class _R:
            status = 200
            def read(self): return b'{"id":"re_msg_1"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R()


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    for t in ("email_notify_prefs", "email_send_log", "scheduler_jobs", "notifications", "messages", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp')")
    c.run("CREATE TABLE messages (id SERIAL PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, content TEXT, "
          "is_read BOOLEAN DEFAULT FALSE, delivered_at TIMESTAMPTZ, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("CREATE TABLE notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), type TEXT, "
          "title TEXT, body TEXT, link TEXT, is_read BOOLEAN DEFAULT FALSE, actor_id INTEGER, entity_id INTEGER, "
          "entity_type TEXT, event_key TEXT, created_at TIMESTAMP DEFAULT NOW())")
    c.run("CREATE UNIQUE INDEX uniq_notif_event_key ON notifications (user_id, event_key) WHERE event_key IS NOT NULL")
    for e, n, tw in ((A, "أمل", "U-A1"), (B, "بسام <b>", "U-B2")):
        c.run("INSERT INTO users (email, full_name, tw_id) VALUES (:e, :n, :t)", e=e, n=n, t=tw)
    auth.release_conn(c)
    auth._migrate_email_notify()
    auth._migrate_email_notify()          # idempotent
    auth._migrate_scheduler_jobs()
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", KEY)
    # notification emails run on the email thread pool in production — inline here
    monkeypatch.setattr(auth, "_email_submit", lambda fn, *a: fn(*a))
    email_service.set_settings(email_service.DEFAULTS)
    yield f
    email_service.set_settings(email_service.DEFAULTS)


def _uid(email):
    return _sql("SELECT id FROM users WHERE email = :e", e=email)[0][0]


def _hdr(uid):
    return {"Authorization": "Bearer " + server._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": ""})}


def _admin():
    return {"X-Admin-Token": server._admin_jwt_issue()}


def _limits(**kw):
    email_service.set_settings(email_service.validate_settings({"notify": kw}, email_service.get_settings()))


def _invite(uid, n=1):
    return auth.create_notification(user_id=uid, type_="appointment_invited", title="دعوة مقابلة من شركة",
                                    body="وصلتك دعوة مقابلة", link=f"/appointment-room?id={n}",
                                    event_key=f"appointment_invited:{n}:{uid}")


def _log():
    return [tuple(r) for r in _sql("SELECT template_key, category, status FROM email_send_log ORDER BY id")]


# ── 1. categories ────────────────────────────────────────────────────────────
def test_every_template_has_a_category():
    cats = {k: v["category"] for k, v in email_service.TEMPLATES.items()}
    for k in ("password_reset", "email_change", "email_changed", "kyc_email_otp"):
        assert cats[k] == "security"
    assert set(email_service.NOTIFY_TYPES) == {k for k, c in cats.items() if c == "notification"}
    assert set(cats.values()) == {"security", "notification"}


# ── 2. security ignores the cap + preferences ────────────────────────────────
def test_security_email_goes_out_even_when_the_cap_is_used_up(env):
    _limits(daily_cap=0, monthly_cap=0)
    uid = _uid(A)
    assert client.put("/my/email-notifications", headers=_hdr(uid),
                      json={"types": {k: False for k in email_service.PREF_TYPES}}).status_code == 200
    res = email_service.send_email(A, "password_reset", {"link": "https://tawasolna.com/reset-password#token=x"})
    assert res["code"] == "sent" and len(env.calls) == 1
    assert "headers" not in env.calls[0]                       # no List-Unsubscribe on security mail
    assert ("password_reset", "security", "sent") in _log()


# ── 3. notification: sent once, then the cap stops it (in-site notification stays) ──
def test_notification_email_then_cap(env):
    uid = _uid(A)
    _limits(daily_cap=1)
    assert _invite(uid, 1) is not None
    (call,) = env.calls
    assert call["to"] == [A] and "دعوة" in call["subject"]
    assert call["headers"]["List-Unsubscribe"] == "<https://tawasolna.com/settings#notifications>"
    assert "https://tawasolna.com/settings#notifications" in call["text"]
    assert "https://tawasolna.com/appointment-room?id=1" in call["text"]   # absolute on site_url
    assert _invite(uid, 2) is not None                       # notification still created …
    assert len(env.calls) == 1                               # … but no email: daily cap = 1
    assert _sql("SELECT COUNT(*) FROM notifications WHERE user_id = :u", u=uid)[0][0] == 2
    assert _log()[-1] == ("notify_appointment_invited", "notification", "skipped_cap")
    _limits(daily_cap=80, monthly_cap=1)                      # monthly cap counts the same rows
    assert email_service.send_email(A, "notify_appointment_invited", {}, user_id=uid)["code"] == "skipped_cap"


def test_cap_counts_only_sent_notifications(env):
    _limits(daily_cap=1)
    email_service.send_email(B, "admin_test", {})            # security — not in the cap
    _sql("INSERT INTO email_send_log (template_key, category, status) VALUES ('notify_message', 'notification', 'failed')")
    assert email_service.send_email(A, "notify_appointment_invited", {}, user_id=_uid(A))["code"] == "sent"


# ── 4. user preference + admin switch ────────────────────────────────────────
def test_user_preference_blocks_only_that_type(env):
    uid = _uid(A)
    assert client.get("/my/email-notifications").status_code == 401
    bad = client.put("/my/email-notifications", headers=_hdr(uid), json={"types": {"password_reset": False}})
    assert bad.status_code == 422                            # security is not a choice
    r = client.put("/my/email-notifications", headers=_hdr(uid),
                   json={"types": {"notify_appointment_invited": False}})
    got = {t["key"]: t["enabled"] for t in r.json()["data"]["types"]}
    assert got["notify_appointment_invited"] is False and got["notify_appointment_cancelled"] is True
    assert _invite(uid) is not None and env.calls == []
    assert _log()[-1][2] == "skipped_pref"
    auth.create_notification(user_id=uid, type_="appointment_cancelled", title="تم إلغاء موعد المقابلة",
                             body="x", link="/appointment-room?id=1", event_key=f"appointment_cancelled:1:{uid}")
    assert len(env.calls) == 1


def test_admin_switch_off_stops_the_type(env):
    r = client.put("/admin/email", headers=_admin(), json={"types": {"notify_appointment_invited": False}})
    assert r.status_code == 200
    uid = _uid(A)
    assert _invite(uid) is not None and env.calls == []
    assert email_service.send_email(A, "notify_appointment_invited", {}, user_id=uid)["code"] == "disabled"
    me = client.get("/my/email-notifications", headers=_hdr(uid)).json()["data"]["types"]
    assert {t["key"]: t["available"] for t in me}["notify_appointment_invited"] is False


def test_admin_limits_are_validated(env):
    h = _admin()
    for bad in ({"daily_cap": -1}, {"message_delay_minutes": 0}, {"monthly_cap": "80"}, {"nope": 1}):
        assert client.put("/admin/email", headers=h, json={"notify": bad}).status_code == 422
    ok = client.put("/admin/email", headers=h, json={"notify": {"daily_cap": 50, "message_throttle_hours": 2}})
    assert ok.json()["data"]["settings"]["notify"] == {"daily_cap": 50, "monthly_cap": 2800,
                                                       "message_delay_minutes": 15, "message_throttle_hours": 2}


def test_admin_email_names_the_inbound_switch(env):
    """task 7.3a — the page draws «استقبال بريد الدعم» from inbound_switch (never a hard-coded key)."""
    assert client.get("/admin/email").status_code == 401
    g = client.get("/admin/email", headers=_admin())
    assert g.status_code == 200
    d = g.json()["data"]
    assert d["inbound_switch"] == email_service.INBOUND_SWITCH
    assert d["inbound_switch"] not in d["notify_types"]


# ── 5. messages: unread after N minutes · one email per conversation per N hours ──
def _send_msg(sid, rid, read=False):
    mid = _sql("INSERT INTO messages (sender_id, receiver_id, content, is_read) VALUES (:s, :r, 'hi', :rd) RETURNING id",
               s=sid, r=rid, rd=read)[0][0]
    auth.schedule_message_email(rid, sid, mid)
    return mid


def _run_message_jobs():
    for (payload,) in _sql("SELECT payload FROM scheduler_jobs WHERE job_type = 'message_email' AND status = 'pending'"):
        auth._execute_scheduler_job({"job_type": "message_email", "payload": payload})
    _sql("UPDATE scheduler_jobs SET status = 'done' WHERE job_type = 'message_email'")


def test_message_email_waits_and_throttles(env):
    a, b = _uid(A), _uid(B)
    _send_msg(b, a)
    (delay,) = _sql("SELECT EXTRACT(EPOCH FROM run_at - NOW()) FROM scheduler_jobs WHERE job_type = 'message_email'")[0]
    assert 14 * 60 < float(delay) <= 15 * 60                 # message_delay_minutes default 15
    _run_message_jobs()
    (call,) = env.calls
    assert call["to"] == [A] and "&lt;b&gt;" in call["html"] and "hi" not in call["text"]   # no message content
    assert "https://tawasolna.com/messages?with=U-B2" in call["text"]
    _sql("DELETE FROM scheduler_jobs")                        # next delay window
    _send_msg(b, a)
    _run_message_jobs()
    assert len(env.calls) == 1 and _log()[-1][2] == "skipped_throttle"   # same conversation < 6 h
    _send_msg(a, b)                                          # other direction = other conversation
    _run_message_jobs()
    assert len(env.calls) == 2 and env.calls[-1]["to"] == [B]


def test_read_message_sends_nothing(env):
    a, b = _uid(A), _uid(B)
    mid = _send_msg(b, a)
    _sql("UPDATE messages SET is_read = TRUE WHERE id = :id", id=mid)
    _run_message_jobs()
    assert env.calls == [] and _log() == []


def test_message_jobs_dedupe_inside_the_window(env):
    a, b = _uid(A), _uid(B)
    _send_msg(b, a), _send_msg(b, a), _send_msg(b, a)
    assert _sql("SELECT COUNT(*) FROM scheduler_jobs WHERE job_type = 'message_email'")[0][0] == 1


# ── 6. counters ──────────────────────────────────────────────────────────────
def test_admin_counters(env):
    a = _uid(A)
    _limits(daily_cap=2)
    email_service.send_email(B, "admin_test", {})
    email_service.send_email(B, "kyc_email_otp", {"code": "123456", "minutes": 10})
    for n in range(1, 5):
        _invite(a, n)                                        # 2 sent, 2 blocked by the cap
    g = client.get("/admin/email", headers=_admin())
    assert g.status_code == 200
    d = g.json()["data"]
    for p in ("day", "month"):
        assert d["stats"][p]["security"] == {"sent": 2}
        assert d["stats"][p]["notification"] == {"sent": 2, "skipped_cap": 2}
    assert d["categories"]["notify_message"] == "notification" and d["settings"]["notify"]["daily_cap"] == 2
    assert KEY not in g.text and A not in g.text
