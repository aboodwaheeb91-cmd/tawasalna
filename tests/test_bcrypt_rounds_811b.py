"""Task 8.11b — TW_BCRYPT_ROUNDS (tests only) · production refuses it.

Behaviour, no DB:
  - APP_ENV=production + TW_BCRYPT_ROUNDS → the server does not start (TestClient startup raises,
    clear message, no secret) and hash_password refuses too.
  - no TW_BCRYPT_ROUNDS → bcrypt's default cost ($2b$12$).
  - TW_BCRYPT_ROUNDS=4 → "$2b$04$" · below 4 → 4 · verify_password reads the cost from the hash
    (a default-cost hash still verifies while the variable is set).
Run: python -m pytest tests/test_bcrypt_rounds_811b.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-bcrypt-811b-" + "x" * 32)

import bcrypt
import pytest
from fastapi.testclient import TestClient

import auth
import server


def _cost(h):
    return h.split("$")[2]


def test_production_with_rounds_refuses_to_start(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TW_BCRYPT_ROUNDS", "4")
    ran = []
    monkeypatch.setattr(server, "_run_startup_migrations", lambda *a, **k: ran.append("migrations"))
    with pytest.raises(RuntimeError) as e:
        with TestClient(server.app):
            pass
    assert "TW_BCRYPT_ROUNDS" in str(e.value) and "production" in str(e.value)
    assert server.JWT_SECRET not in str(e.value)
    assert ran == []                       # stopped before touching the database
    with pytest.raises(RuntimeError):
        auth.hash_password("secret-pass-1")


def test_unset_app_env_counts_as_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("TW_BCRYPT_ROUNDS", "4")
    with pytest.raises(RuntimeError):
        auth.hash_password("secret-pass-1")


def test_no_variable_uses_default_cost(monkeypatch):
    monkeypatch.delenv("TW_BCRYPT_ROUNDS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    auth.check_bcrypt_env()                # production without the variable boots
    h = auth.hash_password("secret-pass-1")
    assert _cost(h) == _cost(bcrypt.gensalt().decode()) == "12"
    assert auth.verify_password("secret-pass-1", h)


def test_rounds_4_and_minimum(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("TW_BCRYPT_ROUNDS", raising=False)
    old = auth.hash_password("old-pass-1")          # default cost, made before the variable
    monkeypatch.setenv("TW_BCRYPT_ROUNDS", "4")
    h = auth.hash_password("secret-pass-1")
    assert h.startswith("$2b$04$")
    assert auth.verify_password("secret-pass-1", h) and not auth.verify_password("wrong", h)
    assert auth.verify_password("old-pass-1", old)  # cost read from the hash
    monkeypatch.setenv("TW_BCRYPT_ROUNDS", "2")
    assert auth.hash_password("x-pass-1").startswith("$2b$04$")
    monkeypatch.setenv("TW_BCRYPT_ROUNDS", "abc")
    with pytest.raises(RuntimeError):
        auth.hash_password("x-pass-1")
