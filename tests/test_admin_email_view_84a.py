"""Task 8.4a — user emails hidden from admin responses without users.email.view (docs/rules/admin-staff.md).

Real FastAPI app + real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it; without it skipped).
  - without users.email.view: no email in GET /admin/users · /admin/profile/{id} · /admin/kyc ·
    /admin/support/tickets (+ one ticket), and a search by email matches nothing (users + support)
  - with it (and the owner "*"): the email is there and the email search matches
Run: python -m pytest tests/test_admin_email_view_84a.py -q
"""
import json, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv
import tw_settings

def _owner_stepup_hdr():
    """The owner after the step-up (task 8.4c-1 — owner-only writes / the export need X-Admin-Stepup, else 428)."""
    tok = srv._admin_jwt_issue()
    return {"X-Admin-Token": tok, "X-Admin-Stepup": srv._admin_step_up_issue("owner", 1, tok)}


client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-84a-" + "a" * 32


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


@pytest.fixture(scope="module", autouse=True)
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
def account():
    """An emp account with a KYC submission and a support ticket — every admin read that carries its email."""
    n = uuid.uuid4().hex[:10]
    email = f"hide{n}@t.test"
    uid, tw = _sql("INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
                   "VALUES (:t, :n, :e, 'x', 'emp') RETURNING id, tw_id", t="U" + n, n="Name" + n, e=email)[0]
    _sql("INSERT INTO kyc_submissions (user_id, step, status) VALUES (:u, 'review', 'pending')", u=uid)
    h = {"Authorization": "Bearer " + srv._jwt_encode({"sv": 0, "user_id": uid, "user_type": "emp", "tw_id": tw})}
    r = client.post("/support/tickets", json={"category": "technical", "subject": "مشكلة", "body": "نص"}, headers=h)
    assert r.status_code == 201, r.text
    return {"id": int(uid), "tw": tw, "name": "Name" + n, "email": email, "ticket": r.json()["data"]["public_id"]}


def _admin(perms):
    return _owner_stepup_hdr() if perms is None else {"X-Admin-Token": srv._admin_jwt_issue(perms=perms)}


_NO_EMAIL = ["users.view", "kyc.review", "support.manage"]
_WITH_EMAIL = _NO_EMAIL + ["users.email.view"]


def _reads(a, h):
    out = {}
    for name, url in (("users", f"/admin/users?q={a['tw']}"), ("profile", f"/admin/profile/{a['id']}"),
                      ("kyc", "/admin/kyc"), ("support", "/admin/support/tickets"),
                      ("ticket", f"/admin/support/tickets/{a['ticket']}")):
        r = client.get(url, headers=h)
        assert r.status_code == 200, (url, r.status_code, r.text)
        out[name] = r.text
    return out


def _has_email_key(text):
    def walk(o):
        if isinstance(o, dict):
            return any(k in ("email", "guest_email") or walk(v) for k, v in o.items())
        return isinstance(o, list) and any(walk(v) for v in o)
    return walk(json.loads(text))


def test_no_email_without_permission(account):
    for name, body in _reads(account, _admin(_NO_EMAIL)).items():
        assert account["email"] not in body, name
        assert not _has_email_key(body), name


def test_email_with_permission_and_owner(account):
    for perms in (_WITH_EMAIL, None):   # None = the owner token ("*")
        reads = _reads(account, _admin(perms))
        for name in ("users", "profile", "kyc", "support", "ticket"):
            assert account["email"] in reads[name], (perms, name)


def test_search_by_email_needs_permission(account):
    q = account["email"]
    users = client.get("/admin/users", params={"q": q}, headers=_admin(_NO_EMAIL)).json()["data"]
    assert users["total"] == 0 and users["items"] == []
    tickets = client.get("/admin/support/tickets", params={"q": q}, headers=_admin(_NO_EMAIL)).json()["data"]
    assert tickets["total"] == 0
    # name / tw_id still match without it
    by_name = client.get("/admin/users", params={"q": account["name"]}, headers=_admin(_NO_EMAIL)).json()["data"]
    assert [u["tw_id"] for u in by_name["items"]] == [account["tw"]]
    # with it the email matches
    users = client.get("/admin/users", params={"q": q}, headers=_admin(_WITH_EMAIL)).json()["data"]
    assert [u["email"] for u in users["items"]] == [q]
    tickets = client.get("/admin/support/tickets", params={"q": q}, headers=_admin(_WITH_EMAIL)).json()["data"]
    assert [t["public_id"] for t in tickets["items"]] == [account["ticket"]]


def test_export_is_owner_only(account):
    assert client.get("/admin/users/export", headers=_admin(_WITH_EMAIL + ["users.export"])).status_code == 403
    r = client.get("/admin/users/export", headers=_admin(None))
    assert r.status_code == 200 and account["email"] in r.text
