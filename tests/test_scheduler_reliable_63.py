"""Task 6.3 — reliable scheduler (SYSTEMS_INDEX §37 · docs/SCHEDULER_PLAN.md §15).

Behaviour only, real PostgreSQL (TW_TEST_DB_URL — run_tests.sh sets it), Resend faked at the
HTTP layer (urllib.request.urlopen inside email_service):
  - one cycle runs the due jobs (not the future ones) and writes the heartbeat → /health ok
  - another holder of the advisory lock → the cycle runs nothing (no double run)
  - a job stuck in 'running' goes back to pending (or failed when its attempts are used up)
  - a message email that failed to send is not marked done — retried later, then done
  - /health → scheduler: stale when the heartbeat is old or missing
  - the internal loop survives a failing cycle and stops on shutdown
Run: python -m pytest tests/test_scheduler_reliable_63.py -q
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-scheduler-63-" + "x" * 32)
os.environ["SUPABASE_DB_URL"] = os.environ.get(
    "TW_TEST_DB_URL", "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline")

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server

client = TestClient(server.app)
SECRET = "test-scheduler-secret-63"


class FakeResend:
    def __init__(self):
        self.calls, self.code = [], 200

    def __call__(self, req, timeout=None):
        self.calls.append(json.loads(req.data.decode("utf-8")))
        code = self.code

        class _R:
            status = code
            def read(self): return b'{"id":"re_63"}'
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
    for t in ("email_notify_prefs", "email_send_log", "scheduler_jobs", "site_settings", "messages", "blocks", "users"):
        c.run(f"DROP TABLE IF EXISTS {t}")
    c.run("CREATE TABLE users (id SERIAL PRIMARY KEY, tw_id TEXT, email TEXT UNIQUE, full_name TEXT, "
          "user_type TEXT DEFAULT 'emp')")
    c.run("CREATE TABLE messages (id SERIAL PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, content TEXT, "
          "is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW())")
    c.run("INSERT INTO users (email, full_name, tw_id) VALUES ('amal@example.com', 'أمل', 'U-A1'), "
          "('bassam@example.com', 'بسام', 'U-B2')")
    auth.release_conn(c)
    auth.ensure_site_settings_table()
    auth._migrate_scheduler_jobs()
    auth._migrate_email_notify()
    server.bs.migrate_blocks_suspension()   # task 8.4c-0b — the message email job reads the block rule
    f = FakeResend()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", f)
    monkeypatch.setenv("RESEND_API_KEY", "re_TEST_KEY_63")
    email_service.set_settings(email_service.DEFAULTS)
    yield f
    email_service.set_settings(email_service.DEFAULTS)


def _job(job_type="noop", minutes=-1, status="pending", attempts=0, max_attempts=5, payload=None, locked_ago=None):
    return _sql(
        "INSERT INTO scheduler_jobs (job_type, payload, run_at, status, attempts, max_attempts, dedupe_key, "
        "locked_at, locked_by) VALUES (:t, CAST(:p AS JSONB), NOW() + make_interval(mins => :m), :s, :a, :mx, "
        "md5(random()::text), CASE WHEN CAST(:la AS INTEGER) IS NULL THEN NULL ELSE NOW() - make_interval(mins => CAST(:la AS INTEGER)) END, "
        "CASE WHEN CAST(:la AS INTEGER) IS NULL THEN NULL ELSE 'dead-runner' END) RETURNING id",
        t=job_type, p=json.dumps(payload or {}), m=minutes, s=status, a=attempts, mx=max_attempts,
        la=locked_ago)[0][0]


def _state(jid):
    return tuple(_sql("SELECT status, attempts FROM scheduler_jobs WHERE id = :id", id=jid)[0])


def _health():
    return client.get("/health").json()["scheduler"]


# ── 1. the cycle runs due jobs + heartbeat ──
def test_cycle_runs_due_jobs_and_writes_heartbeat():
    assert _health() == "stale"                                    # never ran
    due, future = _job(minutes=-1), _job(minutes=30)
    res = auth.run_scheduler_cycle()
    assert res["ok"] is True and res["picked"] == 1 and res["done"] == 1
    assert _state(due) == ("done", 1) and _state(future) == ("pending", 0)
    assert _health() == "ok"


def test_endpoint_runs_the_same_cycle(monkeypatch):
    monkeypatch.setattr(server, "SCHEDULER_SECRET", SECRET)
    jid = _job()
    assert client.post("/internal/run-due-jobs", headers={"X-Scheduler-Secret": "wrong"}).status_code == 403
    r = client.post("/internal/run-due-jobs", headers={"X-Scheduler-Secret": SECRET})
    assert r.status_code == 200 and r.json()["done"] == 1 and "stale_reset" in r.json()
    assert _state(jid) == ("done", 1) and _health() == "ok"


# ── 2. advisory lock: a second worker / instance runs nothing ──
def test_lock_held_elsewhere_runs_nothing():
    jid = _job()
    other = auth.get_conn()
    try:
        assert other.run("SELECT pg_try_advisory_lock(:k)", k=auth._SCHEDULER_LOCK)[0][0] is True
        res = auth.run_scheduler_cycle()
        assert res["skipped"] == "locked" and res["picked"] == 0
        assert _state(jid) == ("pending", 0) and _health() == "stale"
    finally:
        other.run("SELECT pg_advisory_unlock(:k)", k=auth._SCHEDULER_LOCK)
        auth.release_conn(other)
    assert auth.run_scheduler_cycle()["done"] == 1                 # lock released → runs once
    assert _state(jid) == ("done", 1)


# ── 3. stuck 'running' jobs (AUD-P2-31) ──
def test_stuck_running_job_returns_then_runs():
    stuck = _job(status="running", attempts=1, locked_ago=auth.SCHEDULER_STALE_RUNNING_MINUTES + 5)
    fresh = _job(status="running", attempts=1, locked_ago=1)       # a live runner — untouched
    spent = _job(status="running", attempts=5, max_attempts=5, locked_ago=60)
    res = auth.run_scheduler_cycle()
    assert res["stale_reset"] == 2
    assert _state(stuck) == ("done", 2)                            # back to pending → picked again
    assert _state(fresh) == ("running", 1)
    assert _state(spent) == ("failed", 5)


# ── 4. a failed email is not done (AUD-P2-43) ──
def test_failed_message_email_is_retried_not_done(env):
    a, b = (r[0] for r in _sql("SELECT id FROM users ORDER BY id"))
    mid = _sql("INSERT INTO messages (sender_id, receiver_id, content) VALUES (:s, :r, 'hi') RETURNING id",
               s=b, r=a)[0][0]
    jid = _job("message_email", payload={"receiver_id": a, "sender_id": b, "message_id": mid})
    env.code = 500                                                 # Resend down
    res = auth.run_scheduler_cycle()
    assert res["retried"] == 1 and res["done"] == 0
    assert _state(jid) == ("pending", 1)
    (wait,) = _sql("SELECT EXTRACT(EPOCH FROM run_at - NOW()) FROM scheduler_jobs WHERE id = :id", id=jid)[0]
    assert float(wait) > 60                                        # later, not the next 60 s cycle
    env.code = 200
    _sql("UPDATE scheduler_jobs SET run_at = NOW() WHERE id = :id", id=jid)
    assert auth.run_scheduler_cycle()["done"] == 1
    assert _state(jid) == ("done", 2) and len(env.calls) == 2


# ── 5. /health → stale ──
def test_health_stale_when_heartbeat_is_old():
    auth.run_scheduler_cycle()
    assert _health() == "ok"
    _sql("UPDATE site_settings SET value = (NOW() - interval '11 minutes')::text WHERE key = :k",
         k=auth.SCHEDULER_HEARTBEAT_KEY)
    body = client.get("/health").json()
    assert body["scheduler"] == "stale"


# ── 6. the internal loop ──
def test_loop_survives_a_failed_cycle_and_stops_on_shutdown(monkeypatch):
    calls = []

    def cycle():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("db down")
        return {"ok": True, "picked": 0}

    monkeypatch.setattr(server, "run_scheduler_cycle", cycle)
    monkeypatch.setattr(server, "SCHEDULER_INTERVAL_SECONDS", 0.01)
    monkeypatch.setenv("SCHEDULER_LOOP", "1")

    async def main():
        server._scheduler_loop_start()
        await asyncio.sleep(0.2)
        task = server._scheduler_task
        await server.on_shutdown()
        return task

    task = asyncio.run(main())
    assert len(calls) >= 3                                         # kept going after the failure
    assert task.cancelled() and server._scheduler_task is None
