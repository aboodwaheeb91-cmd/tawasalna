"""
test_hidden_account_subpaths.py — account hiding (suspension / blocks) on public sub-paths
(docs/rules/blocks-suspension.md · SYSTEMS_INDEX §25f).

  GET /profile/{id}/score            — suspended → 404 for everyone · block → 404 both ways
  GET /company/branches/{company_id} — suspended → 404 for everyone · block → 404 both ways
  GET /company/{company_id}/ratings  — suspended → 404 for everyone · block → 404 both ways (task 5.4g)
  Normal account → the same 200 response as before.
  GET /company/profile/{id} (non-owner) — company.contact_email public · users.email / phone never (5.4g)
  followers_count = total follow rows, not filtered per viewer; the list hides blocked (5.4g)

Real PostgreSQL, in-process client. TW_TEST_DB_URL (run_tests.sh sets it) — without it skipped.
Run: python -m pytest tests/test_hidden_account_subpaths.py -q
"""
import os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "u" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()
_ADMIN_SECRET = "test-admin-secret-hs-" + "a" * 32


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "u" * 32)
    monkeypatch.setattr(srv, "ADMIN_JWT_SECRET", _ADMIN_SECRET)
    monkeypatch.setattr(srv, "_asyncpg_pool", None)
    srv._pwd_changed_cache.clear()
    srv._rate_store.clear()
    yield


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


def _user(ut):
    n = uuid.uuid4().hex[:10]
    uid, tw = _sql(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:t, :n, :e, 'x', :ut) RETURNING id, tw_id",
        t=("C" if ut == "co" else "U") + n, n="User" + n, e=n + "@t.test", ut=ut)[0]
    _sql("INSERT INTO profiles (user_id) VALUES (:u) ON CONFLICT DO NOTHING", u=uid)
    return {"id": int(uid), "tw": tw, "ut": ut}


def _h(u):
    return {"Authorization": "Bearer " + srv._jwt_encode(
        {"sv": 0, "user_id": u["id"], "user_type": u["ut"], "tw_id": u["tw"]})}


def _suspend(u, on):
    r = client.put(f"/admin/user/{u['id']}/suspension",
                   headers={"X-Admin-Token": srv._admin_jwt_issue()}, json={"suspended": on})
    assert r.status_code == 200, r.text


def _paths(u):
    return {"score": f"/profile/{u['id']}/score",
            "branches": f"/company/branches/{u['id']}",
            "ratings": f"/company/{u['id']}/ratings"}


def test_normal_account_unchanged():
    co, viewer = _user("co"), _user("emp")
    p = _paths(co)
    for hdr in ({}, _h(viewer)):
        r = client.get(p["score"], headers=hdr)
        assert r.status_code == 200 and set(r.json()) == {"score", "level"}, r.text
        r = client.get(p["branches"], headers=hdr)
        assert r.status_code == 200 and r.json() == {"branches": []}, r.text
        r = client.get(p["ratings"], headers=hdr)
        assert r.status_code == 200 and r.json()["status"] == "success", r.text


def test_suspended_account_404_for_guest_and_signed_in_then_back():
    co, viewer = _user("co"), _user("emp")
    p = _paths(co)
    _suspend(co, True)
    for name, path in p.items():
        for hdr in ({}, _h(viewer)):
            assert client.get(path, headers=hdr).status_code == 404, (name, bool(hdr))
    _suspend(co, False)
    for name, path in p.items():
        assert client.get(path).status_code == 200, name


def test_block_404_both_ways_on_score_and_branches():
    a, b = _user("co"), _user("co")
    assert client.put(f"/blocks/{b['id']}", headers=_h(a)).status_code == 200
    for me, other in ((a, b), (b, a)):
        p = _paths(other)
        for name in ("score", "branches"):
            assert client.get(p[name], headers=_h(me)).status_code == 404, (name, me["id"])
            assert client.get(p[name]).status_code == 200, (name, "guest")
    # the owner still sees their own
    assert client.get(_paths(a)["score"], headers=_h(a)).status_code == 200
    assert client.get(_paths(a)["branches"], headers=_h(a)).status_code == 200


def test_ratings_block_404_both_ways_guest_and_owner_unchanged():
    co, viewer = _user("co"), _user("emp")
    path = _paths(co)["ratings"]
    before = client.get(path)
    assert before.status_code == 200, before.text
    # the company blocks the viewer → 404
    assert client.put(f"/blocks/{viewer['id']}", headers=_h(co)).status_code == 200
    assert client.get(path, headers=_h(viewer)).status_code == 404
    assert client.delete(f"/blocks/{viewer['id']}", headers=_h(co)).status_code == 200
    assert client.get(path, headers=_h(viewer)).status_code == 200
    # the viewer blocks the company → 404
    assert client.put(f"/blocks/{co['id']}", headers=_h(viewer)).status_code == 200
    assert client.get(path, headers=_h(viewer)).status_code == 404
    # guest + the company itself → 200, same response as before
    for hdr in ({}, _h(co)):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200 and r.json() == before.json(), r.text


def test_company_contact_email_public_login_email_and_phone_owner_only():
    co, viewer = _user("co"), _user("emp")
    _sql("INSERT INTO company_profiles (user_id, contact_email) VALUES (:u, 'hr@co.test') "
         "ON CONFLICT (user_id) DO UPDATE SET contact_email = EXCLUDED.contact_email", u=co["id"])
    _sql("UPDATE profiles SET phone = '0790000000' WHERE user_id = :u", u=co["id"])
    login_email = _sql("SELECT email FROM users WHERE id = :u", u=co["id"])[0][0]
    for hdr in ({}, _h(viewer)):
        r = client.get(f"/company/profile/{co['id']}", headers=hdr)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["company"]["contact_email"] == "hr@co.test"
        assert "email" not in body["profile"] and "phone" not in body["profile"]
        assert login_email not in r.text and "0790000000" not in r.text
    own = client.get(f"/company/profile/{co['id']}", headers=_h(co)).json()
    assert own["profile"]["email"] == login_email and own["profile"]["phone"] == "0790000000"


def test_followers_count_is_total_while_list_hides_blocked_follower():
    page, follower, viewer = _user("co"), _user("emp"), _user("emp")
    assert client.post(f"/profile/{page['id']}/follow", headers=_h(follower)).status_code == 200

    def _count():
        return client.get(f"/company/profile/{page['id']}", headers=_h(viewer)).json()["stats"]["followers_count"]

    def _listed():
        r = client.get(f"/profile/{page['id']}/followers", headers=_h(viewer))
        assert r.status_code == 200, r.text
        return {int(f["id"]) for f in r.json()["items"]}

    count_before = _count()
    assert follower["id"] in _listed()
    assert client.put(f"/blocks/{follower['id']}", headers=_h(viewer)).status_code == 200
    assert follower["id"] not in _listed()
    assert _count() == count_before == 1
