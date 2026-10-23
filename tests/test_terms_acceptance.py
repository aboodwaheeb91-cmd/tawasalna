"""
test_terms_acceptance.py — task terms: /privacy + /terms pages + required consent at registration.

  1. POST /auth/register without terms_accepted (missing / false / "yes") → 422 terms_required,
     field terms_accepted, the twT text — and no account is created.
  2. With terms_accepted: true → 200; users.terms_accepted_at is set and users.terms_version
     is the server's tw_terms.TERMS_VERSION (a version sent by the client is ignored).
  3. The terms_acceptance migration is registered (critical, before rls_lockdown) and idempotent.
  4. /privacy and /terms open (200, indexable, the version filled in) and link to each other;
     the register form and the landing footer link to both.

Real PostgreSQL — needs TW_TEST_DB_URL (run_tests.sh sets it). Without it: DB tests skipped.
Run: python -m pytest tests/test_terms_acceptance.py -q
"""
import os, sys, uuid
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-user-secret-" + "t" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv
import tw_terms

client = TestClient(srv.app)
_DB_URL = os.environ.get("TW_TEST_DB_URL", "").strip()


@pytest.fixture(scope="module")
def db():
    if not _DB_URL:
        pytest.skip("TW_TEST_DB_URL not set")
    rest = _DB_URL.split("://", 1)[1]
    userinfo, hostinfo = rest.split("@", 1)
    user, pw = (userinfo.split(":", 1) + [""])[:2]
    hostport, name = hostinfo.split("/", 1)
    host, port = hostport.rsplit(":", 1) if ":" in hostport else (hostport, "5432")
    auth._db_params = dict(host=host, port=int(port), user=user, password=pw,
                           database=name.split("?")[0], ssl_context=None)
    srv._run_startup_migrations()
    yield


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(srv, "JWT_SECRET", "test-user-secret-" + "t" * 32)
    monkeypatch.setattr(srv, "get_country_from_ip", lambda ip: "DEFAULT")  # no ip-api call
    srv._rate_store.clear()
    yield


def _body(email, **extra):
    return {"first_name": "سارة", "last_name": "خالد", "email": email,
            "password": "secret-pass-1", "user_type": "emp", **extra}


def _user_row(email):
    with auth.db_conn() as conn:
        rows = conn.run("SELECT terms_accepted_at, terms_version FROM users WHERE email = :e", e=email)
    return rows[0] if rows else None


@pytest.mark.parametrize("extra", [{}, {"terms_accepted": False}, {"terms_accepted": None}])
def test_register_without_consent_is_rejected(db, extra):
    email = f"terms_no_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json=_body(email, **extra))
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "terms_required" and err["field"] == "terms_accepted"
    assert err["message"] == srv._tw_text("register.err.terms_required")
    assert _user_row(email) is None   # nothing written


def test_register_with_consent_stores_time_and_version(db):
    email = f"terms_ok_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json=_body(email, terms_accepted=True, terms_version="1999-01-01"))
    assert r.status_code == 200, r.text
    accepted_at, version = _user_row(email)
    assert accepted_at is not None
    assert version == tw_terms.TERMS_VERSION   # the server's version, never the client's


def test_create_user_without_version_leaves_columns_null(db):
    email = f"terms_old_{uuid.uuid4().hex[:8]}@example.com"
    auth.create_user("حساب قديم", email, "secret-pass-1", "co")
    assert _user_row(email) == [None, None]


def test_migration_registered_and_idempotent(db):
    reg = [(n, c) for n, _, c in srv._startup_migrations()]
    names = [n for n, _ in reg]
    assert ("terms_acceptance", True) in reg
    assert names.index("terms_acceptance") < names.index("rls_lockdown")
    tw_terms.migrate_terms_acceptance()   # second run → no error
    with auth.db_conn() as conn:
        cols = {r[0]: r[1] for r in conn.run(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name IN ('terms_accepted_at', 'terms_version')")}
    assert cols == {"terms_accepted_at": "timestamp with time zone", "terms_version": "text"}


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.ids, self.keys = [], {}, set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if a.get("id"):
            self.ids[a["id"]] = (tag, a)
        if a.get("data-tw-t"):
            self.keys.add(a["data-tw-t"])


def _parse(html):
    p = _Links()
    p.feed(html)
    return p


@pytest.mark.parametrize("path,other", [("/privacy", "/terms"), ("/terms", "/privacy")])
def test_legal_pages_open_and_link(path, other):
    r = client.get(path)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "X-Robots-Tag" not in r.headers   # public page — indexable (§54m)
    page = _parse(r.text)
    assert other in page.hrefs
    assert {"legal.draft_title", "legal.draft_body", "legal.contact_email"} <= page.keys
    assert page.ids["lgVersion"] and tw_terms.TERMS_VERSION in r.text and "{{" not in r.text
    strings = srv.tw_strings.merged({})
    assert all(k in strings for k in page.keys), [k for k in page.keys if k not in strings]
    assert strings["legal.contact_email"] == "CONTACT_EMAIL_TBD"
    assert other in client.get("/sitemap.xml").text and path in client.get("/sitemap.xml").text


def test_register_form_and_footer_link_to_both():
    login = _parse(client.get("/login").text)
    tag, attrs = login.ids["rTerms"]
    assert tag == "input" and attrs.get("type") == "checkbox"
    assert {"/privacy", "/terms"} <= set(login.hrefs)
    landing = _parse(client.get("/").text)
    assert {"/privacy", "/terms"} <= set(landing.hrefs)
