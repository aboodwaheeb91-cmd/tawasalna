"""Task 4.3 — KYC OTP send limits + the single-instance rate store warning (SYSTEMS_INDEX → KYC OTP Security).

Behaviour only (real endpoints + real PostgreSQL schema · fake delivery — nothing is ever sent):
  1  attempts used → new codes asked again and again → past RATES["otp_send_user"] 429, no new code,
     the attempt count is not reset
  2  same phone from two accounts → otp_send_target
  3  same account from different IPs → otp_send_user (per channel — the other channel still works)
  4  one IP, other accounts / targets → otp_send_ip
  5  values editable from tw_settings (security=True, safe ranges) and applied at once
  6  WEB_CONCURRENCY / --workers > 1 → one startup warning line, never a stop

  TW_TEST_DB_URL=postgresql://user:pass@127.0.0.1:5432/db  (run_tests.sh sets it)
Run: python -m pytest tests/test_otp_send_limits_43.py -q
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-otp-send-43-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv
import tw_limits
import tw_settings

client = TestClient(srv.app)
_ips = (f"198.18.{i // 250}.{i % 250 + 1}" for i in itertools.count())   # a fresh client IP per request


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


def _user(name):
    uid = _sql("INSERT INTO users (tw_id, email, full_name, user_type, password_hash) "
               "VALUES (:tw, :e, :n, 'emp', 'x') RETURNING id", tw="U" + name, e=name + "@x.com", n=name)[0][0]
    auth.start_kyc(uid)
    return uid


def _bearer(uid):
    return {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp"})}


def _send(uid, channel, target=None, ip=None):
    body = {"email": f"{_name[uid]}@x.com"} if channel == "email" else {"phone": target}
    return client.post(f"/kyc/{channel}/send", json=body,
                       headers={**_bearer(uid), "X-Real-IP": ip or next(_ips)})


def _code_row(uid, channel):
    return tuple(_sql(f"SELECT {channel}_code, {channel}_code_attempts FROM kyc_submissions WHERE user_id=:u", u=uid)[0])


_name = {}
_sent = []


@pytest.fixture
def db(monkeypatch):
    try:
        c = auth.get_conn()
    except Exception as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")
    c.run("DROP SCHEMA public CASCADE")
    c.run("CREATE SCHEMA public")
    auth.release_conn(c)
    auth.init_db()
    auth._migrate_session_version()
    auth.bs.migrate_blocks_suspension()
    auth.ad.migrate_account_deletion()     # task 8.5a — users.deleted_* (read by the session check)
    auth._migrate_password_changed_at()
    auth._migrate_kyc_otp_security()
    tw_settings.migrate_app_settings()
    # fake delivery — never a real email / SMS
    monkeypatch.setattr(srv, "is_email_otp_delivery_available", lambda: True)
    monkeypatch.setattr(srv, "is_phone_otp_delivery_available", lambda: True)
    monkeypatch.setattr(srv.email_service, "send_email",
                        lambda to, kind, data: _sent.append((to, data["code"])) or {"ok": True})
    yield


@pytest.fixture(autouse=True)
def clean():
    srv._rate_store.clear()
    _sent.clear()
    _name.clear()
    tw_settings._set_overrides({})
    yield
    srv._rate_store.clear()
    tw_settings._set_overrides({})


def _new_user(name):
    uid = _user(name)
    _name[uid] = name
    return uid


def _limited(r):
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["ok"] is False and body["error"]["code"] == "otp_rate_limited"
    return body["error"]["message"]


# ── 1. attempts used + repeated new-code requests ──
def test_resend_past_limit_no_new_code_and_attempts_kept(db):
    a = _new_user("ra")
    max_sends = tw_settings.rate("otp_send_user")[0]
    for _ in range(max_sends):
        assert _send(a, "email").status_code == 200
    for _ in range(3):                                            # use attempts on the last code
        assert client.post("/kyc/email/verify", json={"code": "000000"},
                           headers={**_bearer(a), "X-Real-IP": next(_ips)}).status_code == 400
    code_before, attempts_before = _code_row(a, "email")
    assert attempts_before == 3 and code_before
    sent_before = len(_sent)
    for _ in range(3):
        _limited(_send(a, "email"))
    assert _code_row(a, "email") == (code_before, attempts_before)   # no new code · attempts not reset
    assert len(_sent) == sent_before                                 # nothing delivered


# ── 2. same target from two accounts ──
def test_same_phone_from_two_accounts_hits_target_limit(db):
    a, b = _new_user("pa"), _new_user("pb")
    max_sends = tw_settings.rate("otp_send_target")[0]
    for _ in range(max_sends):
        assert _send(a, "phone", "+962 79-000-0001").status_code == 200
    code_b = _code_row(b, "phone")
    _limited(_send(b, "phone", "+962790000001"))                  # same number, normalised
    assert _code_row(b, "phone") == code_b
    assert _send(b, "phone", "+962790000002").status_code == 200  # another number still works


# ── 3. same account from different IPs ──
def test_same_account_many_ips_hits_account_limit(db):
    a = _new_user("ua")
    max_sends = tw_settings.rate("otp_send_user")[0]
    for i in range(max_sends):
        assert _send(a, "phone", f"+96279100000{i}").status_code == 200
    _limited(_send(a, "phone", "+962791999999"))                  # new IP + new number
    assert _send(a, "email").status_code == 200                   # per channel


# ── 4. one IP ──
def test_one_ip_many_accounts_hits_ip_limit(db):
    max_sends = tw_settings.rate("otp_send_ip")[0]
    for i in range(max_sends):
        assert _send(_new_user(f"ip{i}"), "email", ip="203.0.113.43").status_code == 200
    _limited(_send(_new_user("iplast"), "email", ip="203.0.113.43"))
    assert _send(_new_user("ipother"), "email", ip="203.0.113.44").status_code == 200


# ── 5. editable from tw_settings, at once ──
def test_otp_send_limits_editable_and_applied_at_once(db):
    for key in ("otp_send_user_hits", "otp_send_user_window_s", "otp_send_target_hits",
                "otp_send_target_window_s", "otp_send_ip_hits", "otp_send_ip_window_s"):
        d = tw_settings.REGISTRY[key]
        assert d["security"] is True and d["group"] == "sec_otp" and d["min"] >= 1, key
    assert tw_settings.REGISTRY["otp_send_user_hits"]["max"] <= 10
    assert tw_settings.REGISTRY["otp_send_target_hits"]["max"] <= 10
    assert tw_settings.REGISTRY["otp_send_user_window_s"]["min"] >= 3600
    with pytest.raises(tw_settings.SettingError):
        tw_settings.validate("otp_send_user_hits", 0)
    a = _new_user("sa")
    tw_settings.set_value("otp_send_user_hits", 2, "test")
    assert _send(a, "email").status_code == 200
    assert _send(a, "email").status_code == 200
    _limited(_send(a, "email"))
    tw_settings.reset_value("otp_send_user_hits", "test")
    assert _send(a, "email").status_code == 200                   # default 5 again


# ── 6. single instance ──
def test_more_than_one_worker_warns_once_never_stops():
    assert srv._single_instance_warning({}, ["uvicorn", "server:app"]) is None
    assert srv._single_instance_warning({"WEB_CONCURRENCY": "1"}, []) is None
    for env, argv in (({"WEB_CONCURRENCY": "2"}, []), ({}, ["uvicorn", "--workers", "3"]),
                      ({}, ["uvicorn", "--workers=4"]), ({}, ["gunicorn", "-w", "2"])):
        msg = srv._single_instance_warning(env, argv)
        assert msg and "rate" in msg, (env, argv)
    assert tw_limits.RATES["otp_send_user"] == tw_settings.rate("otp_send_user")
