"""
test_supabase_settings.py — Supabase Storage settings hardening (§29a):
SUPABASE_URL / SUPABASE_SERVICE_KEY cleaning, key type → headers, startup
status lines. No network, no DB. Keys here are fake and never printed.

Run: python -m pytest tests/test_supabase_settings.py -q
"""
import base64, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-supabase-" + "x" * 32)
os.environ.setdefault("ADMIN_TOKEN", "a" * 40)

import pytest

import server

BASE = "https://abc.supabase.co"
SECRET = "sb_secret_FAKEfakeFAKE123"


def _jwt(role):
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{seg({'alg': 'HS256', 'typ': 'JWT'})}.{seg({'iss': 'supabase', 'role': role})}.FAKEsig"


SERVICE_JWT, ANON_JWT = _jwt("service_role"), _jwt("anon")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", BASE)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", SECRET)


@pytest.mark.parametrize("raw", [
    "‏" + BASE,                          # RTL mark pasted from mobile
    "﻿‪" + BASE + "‬⁩",   # BOM + bidi embedding/isolate
    '"' + BASE + '"', "'" + BASE + "/'",      # surrounding quotes
    "  " + BASE + "/ \n",                     # whitespace + trailing slash
    "‏ “" + BASE + "//” ",
])
def test_url_cleaned(monkeypatch, raw):
    monkeypatch.setenv("SUPABASE_URL", raw)
    assert server._supabase_base_url() == BASE


@pytest.mark.parametrize("raw,reason", [
    ("", "SUPABASE_URL is not set"),
    ("abc.supabase.co", "SUPABASE_URL must start with https://"),
    ("http://abc.supabase.co", "SUPABASE_URL must start with https://"),
    ("‏http://abc.supabase.co", "SUPABASE_URL must start with https://"),
    ("https://evil.example", "SUPABASE_URL must be https://<project>.supabase.co"),
    ("https://abc.supabase.co.evil.example", "SUPABASE_URL must be https://<project>.supabase.co"),
    ("https://abc.supabase.co/rest/v1", "SUPABASE_URL must be https://<project>.supabase.co"),
])
def test_url_invalid_not_configured(monkeypatch, raw, reason):
    monkeypatch.setenv("SUPABASE_URL", raw)
    assert server._supabase_url_status() == ("", reason)
    assert server._supabase_base_url() == ""
    assert server._supabase_storage_status_lines() == [f"⚠️ Supabase storage: NOT CONFIGURED — {reason}"]


def test_secret_key_apikey_only(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "‏\"" + SECRET + "\"\n")
    assert server._supabase_auth_headers() == {"apikey": SECRET}
    assert server._supabase_storage_status_lines() == ["✅ Supabase storage: OK (key type: secret)"]


def test_legacy_service_role_jwt_both_headers_and_warning(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", " " + SERVICE_JWT + " ")
    assert server._supabase_auth_headers() == {"apikey": SERVICE_JWT, "Authorization": "Bearer " + SERVICE_JWT}
    lines = server._supabase_storage_status_lines()
    assert lines[0] == "✅ Supabase storage: OK (key type: legacy JWT)"
    assert "deprecates these by end of 2026" in lines[1] and "sb_secret_" in lines[1]


@pytest.mark.parametrize("key,reason", [
    (ANON_JWT, "SUPABASE_SERVICE_KEY is an anon key, not service_role"),
    ("sb_publishable_FAKE", "SUPABASE_SERVICE_KEY is a publishable key, not a secret key"),
    ("svc", "SUPABASE_SERVICE_KEY is not a service key"),
    ("eyJbroken", "SUPABASE_SERVICE_KEY is not a service key"),
    ("", "SUPABASE_SERVICE_KEY is not set"),
])
def test_bad_keys_rejected(monkeypatch, key, reason):
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
    assert server._supabase_auth_headers() == {}
    assert server._supabase_service_key() == ""
    assert server._supabase_storage_status_lines() == [f"⚠️ Supabase storage: NOT CONFIGURED — {reason}"]


def test_status_lines_never_contain_key_or_url(monkeypatch):
    for key in (SECRET, SERVICE_JWT, ANON_JWT):
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
        for url in (BASE, "https://evil.example/secret-path"):
            monkeypatch.setenv("SUPABASE_URL", url)
            text = "\n".join(server._supabase_storage_status_lines())
            assert key not in text and key[:12] not in text and key[-6:] not in text
            assert "abc" not in text and "evil" not in text and "secret-path" not in text


def test_no_manual_bearer_for_supabase_in_server():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py"), encoding="utf-8").read()
    assert 'f"Bearer {' not in src
    assert src.count('os.environ.get("SUPABASE_SERVICE_KEY")') == 0
    assert src.count('os.environ.get("SUPABASE_URL")') == 0
