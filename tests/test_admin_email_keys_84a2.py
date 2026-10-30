"""Task 8.4a2 — email keys ("email" / "*_email") need users.email.view, phone keys ("phone" / "*_phone")
users.phone.view, in every admin reply (independent; the owner "*" sees both).

  - guard (no DB): every support.FIELDS field of type "email" / "phone" matches admin_perms.is_email_key /
    is_phone_key, so a new contact field in the support form cannot leak silently; strip_contacts at any depth
  - PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it those tests skip): an account with a profile
    phone + an account ticket and a guest ticket with details.account_email / account_phone → users · profile ·
    kyc · support (list + ticket) — the whole JSON text: neither perm → no seed email / phone · email only →
    email shown, phone hidden · phone only → the reverse · owner → both · no email-shaped text from the seed
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


@pytest.mark.parametrize("kind,rule", [("email", admin_perms.is_email_key), ("phone", admin_perms.is_phone_key)])
def test_support_contact_fields_match_the_rule(kind, rule):
    fields = [(cat, k) for cat, specs in support.FIELDS.items() for k, spec in specs.items() if spec.get("type") == kind]
    assert fields, f"support.FIELDS has no {kind} field — update this guard"
    for cat, k in fields:
        assert rule(k), f"support.FIELDS[{cat!r}][{k!r}] is a {kind} but the key rule misses it"


def test_strip_contacts_by_key_name():
    data = {"email": "a@x.io", "guest_email": "b@x.io", "phone": "1", "name": "n", "emails_sent": 3,
            "email_verified": True, "phone_verified": True,
            "items": [{"details": {"account_email": "c@x.io", "account_phone": "2", "account_name": "z"}}]}
    rest = {"name": "n", "emails_sent": 3, "email_verified": True, "phone_verified": True}
    assert admin_perms.strip_contacts(data, False, False) == {**rest, "items": [{"details": {"account_name": "z"}}]}
    assert admin_perms.strip_contacts(data, True, False) == {
        **rest, "email": "a@x.io", "guest_email": "b@x.io",
        "items": [{"details": {"account_email": "c@x.io", "account_name": "z"}}]}
    assert admin_perms.strip_contacts(data, False, True) == {
        **rest, "phone": "1", "items": [{"details": {"account_phone": "2", "account_name": "z"}}]}
    assert admin_perms.strip_contacts(data, True, True) == data
    assert admin_perms.PHONE_VIEW in admin_perms.GRANTABLE


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
    """An emp account (profile phone + KYC row) with an account ticket carrying details.account_email /
    account_phone + a guest account ticket with both."""
    n = uuid.uuid4().hex[:10]
    d = str(uuid.uuid4().int)[:8]
    emails = {"user": f"own{n}@t.test", "detail": f"lost{n}@t.test", "guest": f"guest{n}@t.test",
              "guest_detail": f"gdet{n}@t.test"}
    phones = {"profile": "+9627" + d, "detail": "+9628" + d, "guest_detail": "+9629" + d}
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id", t="U" + n, n="Name" + n, e=emails["user"])[0]
    _sql("INSERT INTO profiles (user_id, phone) VALUES (:u, :p) "
         "ON CONFLICT (user_id) DO UPDATE SET phone = EXCLUDED.phone", u=uid, p=phones["profile"])
    _sql("INSERT INTO kyc_submissions (user_id, step, status) VALUES (:u, 'review', 'pending')", u=uid)
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": tw})}
    r = client.post("/support/tickets", headers=h, json={
        "category": "account", "subject": "حسابي", "body": "نص",
        "details": {"issue": "lost_access", "account_email": emails["detail"], "account_phone": phones["detail"]}})
    assert r.status_code == 201, r.text
    with auth.db_conn() as c:
        _, guest_ticket = support._insert_ticket(c, None, emails["guest"], "account", "زائر",
                                                 {"account_email": emails["guest_detail"],
                                                  "account_phone": phones["guest_detail"]}, None)
    return {"id": int(uid), "tw": tw, "emails": emails, "phones": phones,
            "ticket": r.json()["data"]["public_id"], "guest_ticket": guest_ticket}


def _admin(perms):
    return {"X-Admin-Token": srv._admin_jwt_issue(perms=perms)}


_READS = ["users.view", "kyc.review", "support.manage"]
_EMAIL, _PHONE = "users.email.view", "users.phone.view"


def _get(url, h):
    r = client.get(url, headers=h)
    assert r.status_code == 200, (url, r.status_code, r.text)
    return r.text


def _replies(s, perms):
    h = _admin(perms)
    return {"users": _get(f"/admin/users?q={s['tw']}", h), "profile": _get(f"/admin/profile/{s['id']}", h),
            "kyc": _get("/admin/kyc", h), "list": _get("/admin/support/tickets?limit=100", h),
            "ticket": _get(f"/admin/support/tickets/{s['ticket']}", h),
            "guest_ticket": _get(f"/admin/support/tickets/{s['guest_ticket']}", h)}


def _absent(replies, values):
    for name, body in replies.items():
        for v in values:
            assert v not in body, (name, v)


# where each seeded value must show when its perm is there
_EMAIL_AT = {"user": ("users", "profile", "kyc", "ticket"), "detail": ("ticket",),
             "guest": ("guest_ticket",), "guest_detail": ("guest_ticket",)}
_PHONE_AT = {"profile": ("profile",), "detail": ("ticket",), "guest_detail": ("guest_ticket",)}


def _present(replies, seeded, where):
    for key, names in where.items():
        for name in names:
            assert seeded[key] in replies[name], (name, key)


@pytest.mark.parametrize("extra", [[], [_EMAIL], [_PHONE], [_EMAIL, _PHONE], None])
def test_contacts_follow_their_own_permission(seed, extra):
    perms = None if extra is None else _READS + extra   # None = the owner token ("*")
    email_ok = extra is None or _EMAIL in extra
    phone_ok = extra is None or _PHONE in extra
    replies = _replies(seed, perms)
    if email_ok:
        _present(replies, seed["emails"], _EMAIL_AT)
    else:
        _absent(replies, seed["emails"].values())
    if phone_ok:
        _present(replies, seed["phones"], _PHONE_AT)
    else:
        _absent(replies, seed["phones"].values())


def test_no_seed_email_text_in_any_admin_contacts_reply(seed):
    seeded = {e.lower() for e in seed["emails"].values()}
    for name, body in _replies(seed, _READS + [_PHONE]).items():
        found = {m.lower() for m in _EMAIL_RE.findall(body)}
        assert not (found & seeded), (name, found & seeded)


def test_no_otp_secret_in_admin_replies(seed):
    _sql("UPDATE kyc_submissions SET phone = :p, phone_code = 'otp-secret-x', phone_code_target = :p "
         "WHERE user_id = :u", p=seed["phones"]["profile"], u=seed["id"])
    for name, body in _replies(seed, None).items():   # even the owner
        assert "otp-secret-x" not in body and "phone_code" not in body and "email_code" not in body, name
