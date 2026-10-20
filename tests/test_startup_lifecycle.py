"""Task 5.0f — the startup hook still runs after the FastAPI 0.121.3 / Starlette 0.50.0 upgrade.

Behaviour, no DB: TestClient(app) used as a context manager runs the app's startup →
_run_startup_migrations() is called once (before the other loaders); a failing CRITICAL
migration stops the startup (the context manager raises), an optional one does not.
Run: python -m pytest tests/test_startup_lifecycle.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-startup-50f-" + "x" * 32)

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture
def quiet_startup(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_strings_load_overrides", lambda: calls.append("strings"))
    monkeypatch.setattr(server, "_actions_load_overrides", lambda: calls.append("actions"))
    monkeypatch.setattr(server, "_email_load_settings", lambda: calls.append("email"))
    monkeypatch.setattr(server, "get_pipeline_application_index_status", lambda: {"ready": True})

    async def _no_pool():
        calls.append("asyncpg")
    monkeypatch.setattr(server, "_init_asyncpg_pool", _no_pool)
    server._MIGRATION_STATUS.clear()
    return calls


def test_startup_runs_migrations_then_loaders(quiet_startup, monkeypatch):
    calls = quiet_startup
    monkeypatch.setattr(server, "_run_startup_migrations", lambda *a, **k: calls.append("migrations"))
    with TestClient(server.app):
        pass
    assert calls[0] == "migrations" and calls.count("migrations") == 1, calls
    assert {"strings", "actions", "email", "asyncpg"} <= set(calls), calls


def _boom():
    raise RuntimeError("schema broken")


def test_critical_migration_failure_stops_startup(quiet_startup, monkeypatch):
    monkeypatch.setattr(server, "_startup_migrations",
                        lambda: (("ok_one", lambda: None, True), ("core", _boom, True)))
    with pytest.raises(RuntimeError):
        with TestClient(server.app):
            pass
    assert server._MIGRATION_STATUS == {"ok_one": "ok", "core": "failed"}
    assert "strings" not in quiet_startup          # nothing after the failed migration ran


def test_optional_migration_failure_keeps_starting(quiet_startup, monkeypatch):
    monkeypatch.setattr(server, "_startup_migrations",
                        lambda: (("feature", _boom, False), ("after", lambda: None, True)))
    with TestClient(server.app):
        pass
    assert server._MIGRATION_STATUS == {"feature": "failed", "after": "ok"}
    assert "strings" in quiet_startup
