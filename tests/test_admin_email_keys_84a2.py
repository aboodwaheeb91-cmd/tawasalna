"""Task 8.4a2 — any email key (named "email" or "*_email") hidden from admin replies without users.email.view.

  - guard (no DB): every support.FIELDS field of type "email" matches admin_perms.is_email_key, so a new
    email field in the support form cannot leak silently; strip_emails drops such keys at any depth
  - PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it those tests skip): an account ticket with
    details.account_email (+ a guest ticket with one) → support.manage only: neither the list nor the ticket
    carries it anywhere in the JSON text · with users.email.view / the owner: it is there · every reply that
    goes through _admin_emails (users · profile · kyc · support) has no email-shaped text from the seed
Run: python -m pytest tests/test_admin_email_keys_84a2.py -q
"""
import os, re, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import admin_perms
import auth
import server as srv
import support
import tw_settings

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-84a2-" + "a" * 32
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def test_support_email_fields_match_the_rule():
    email_fields = [(cat, k) for cat, fields in support.FIELDS.items()
                    for k, spec in fields.items() if spec.get("type") == "email"]
    assert email_fields, "support.FIELDS has no email field — update this guard"
    for cat, k in email_fields:
        assert admin_perms.is_email_key(k), f"support.FIELDS[{cat!r}][{k!r}] is an email but is_email_key misses it"


def test_strip_emails_by_key_name():
    data = {"email": "a@x.io", "guest_email": "b@x.io", "name": "n", "emails_sent": 3, "email_verified": True,
            "items": [{"details": {"account_email": "c@x.io", "account_name": "z"}}]}
    assert admin_perms.strip_emails(data) == {"name": "n", "emails_sent": 3, "email_verified": True,
                                              "items": [{"details": {"account_name": "z"}}]}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    srv._rate_store.clear()
    srv._pwd_changed_cache.clear()
    tw_settings._set_overrides({})
    yield
    srv._rate_store.clear()


def _db_params():
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    return dict(host=host, port=int(port), user=user, password=pw, database=name.split("?")[0])


@pytest.fixture(scope="module")
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    auth._db_params = dict(_db_params(), ssl_context=None)
    srv._run_startup_migrations()
    yield


def _sql(q, **kw):
    with auth.db_conn() as c:
        return c.run(q, **kw)


@pytest.fixture
def seed(db):
    """An emp account (KYC row) with an account ticket carrying details.account_email + a guest account ticket."""
    n = uuid.uuid4().hex[:10]
    emails = {"user": f"own{n}@t.test", "detail": f"lost{n}@t.test", "guest": f"guest{n}@t.test",
              "guest_detail": f"gdet{n}@t.test"}
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id", t="U" + n, n="Name" + n, e=emails["user"])[0]
    _sql("INSERT INTO kyc_submissions (user_id, step, status) VALUES (:u, 'review', 'pending')", u=uid)
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": tw})}
    r = client.post("/support/tickets", headers=h, json={
        "category": "account", "subject": "حسابي", "body": "نص",
        "details": {"issue": "lost_access", "account_email": emails["detail"]}})
    assert r.status_code == 201, r.text
    with auth.db_conn() as c:
        _, guest_ticket = support._insert_ticket(c, None, emails["guest"], "account", "زائر",
                                                 {"account_email": emails["guest_detail"]}, None)
    return {"id": int(uid), "tw": tw, "emails": emails,
            "ticket": r.json()["data"]["public_id"], "guest_ticket": guest_ticket}


def _admin(perms):
    return {"X-Admin-Token": srv._admin_jwt_issue(perms=perms)}


_SUPPORT_ONLY = ["support.manage"]
_ALL_READS = ["users.view", "kyc.review", "support.manage"]


def _get(url, h):
    r = client.get(url, headers=h)
    assert r.status_code == 200, (url, r.status_code, r.text)
    return r.text


def _support_reads(s, h):
    return {"list": _get("/admin/support/tickets?limit=100", h),
            "ticket": _get(f"/admin/support/tickets/{s['ticket']}", h),
            "guest_ticket": _get(f"/admin/support/tickets/{s['guest_ticket']}", h)}


def test_account_email_hidden_with_support_manage_only(seed):
    for name, body in _support_reads(seed, _admin(_SUPPORT_ONLY)).items():
        for email in seed["emails"].values():
            assert email not in body, (name, email)


def test_account_email_shown_with_permission_and_owner(seed):
    for perms in (_SUPPORT_ONLY + ["users.email.view"], None):   # None = the owner token ("*")
        reads = _support_reads(seed, _admin(perms))
        assert seed["emails"]["detail"] in reads["ticket"], perms
        assert seed["emails"]["guest_detail"] in reads["guest_ticket"], perms
        assert seed["emails"]["detail"] in reads["list"] or seed["emails"]["guest_detail"] in reads["list"], perms


def test_no_seed_email_text_in_any_admin_emails_reply(seed):
    h = _admin(_ALL_READS)
    seeded = {e.lower() for e in seed["emails"].values()}
    replies = {"users": _get(f"/admin/users?q={seed['tw']}", h), "profile": _get(f"/admin/profile/{seed['id']}", h),
               "kyc": _get("/admin/kyc", h), **_support_reads(seed, h)}
    for name, body in replies.items():
        found = {m.lower() for m in _EMAIL_RE.findall(body)}
        assert not (found & seeded), (name, found & seeded)
