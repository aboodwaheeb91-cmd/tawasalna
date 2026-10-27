"""Task 8.0 — add_job publishes the job + its job_profession_targets in ONE transaction.

No DB: a fake connection records every SQL call (auth.get_conn / release_conn patched).
Run: python -m pytest tests/test_add_job_transaction.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "test-secret-add-job-80-" + "x" * 32)

import pytest

import auth


class _FakeConn:
    """Answers the INSERT INTO jobs RETURNING row; fails the target INSERT when fail_target."""
    def __init__(self, fail_target=False):
        self.fail_target = fail_target
        self.calls = []
        self.columns = []

    def run(self, sql, **params):
        head = " ".join(sql.split())
        self.calls.append(head)
        if head.startswith("INSERT INTO jobs"):
            names = ["id", "company_id", "title", "expires_at"]
            self.columns = [{"name": n} for n in names]
            return [[42, params["cid"], params["title"], None]]
        if head.startswith("INSERT INTO job_profession_targets") and self.fail_target:
            raise RuntimeError("target insert failed")
        return []

    def count(self, prefix):
        return sum(1 for c in self.calls if c.startswith(prefix))


@pytest.fixture
def fake(monkeypatch):
    holder = {}

    def use(conn):
        holder["conn"] = conn
        monkeypatch.setattr(auth, "get_conn", lambda: conn)
        monkeypatch.setattr(auth, "release_conn", lambda c: None)
        monkeypatch.setattr(auth, "_validate_accepted_profession_ids", lambda c, p, ids: list(ids))
        monkeypatch.setattr(auth, "_fetch_accepted_professions_batch",
                            lambda c, ids: {ids[0]: [{"id": 7}, {"id": 8}]})
        scheduled = []
        monkeypatch.setattr(auth, "schedule_job_expiry_reminder",
                            lambda jid, exp: scheduled.append(jid) or True)
        holder["scheduled"] = scheduled
        return holder
    return use


DATA = {"title": "مطور", "profession_id": 3, "accepted_profession_ids": [7, 8], "duration_days": 7}


def test_target_insert_failure_rolls_back(fake):
    h = fake(_FakeConn(fail_target=True))
    with pytest.raises(RuntimeError):
        auth.add_job(1, dict(DATA))
    c = h["conn"]
    assert c.count("BEGIN") == 1
    assert c.count("ROLLBACK") == 1
    assert c.count("COMMIT") == 0
    assert c.calls.index("BEGIN") < next(i for i, s in enumerate(c.calls) if s.startswith("INSERT INTO jobs"))
    assert h["scheduled"] == []          # nothing scheduled for a job that was rolled back


def test_success_commits_once(fake):
    h = fake(_FakeConn())
    out = auth.add_job(1, dict(DATA))
    c = h["conn"]
    assert out["id"] == 42
    assert out["accepted_professions"] == [{"id": 7}, {"id": 8}]
    assert c.count("COMMIT") == 1 and c.count("ROLLBACK") == 0
    assert c.count("INSERT INTO job_profession_targets") == 2
    assert c.calls[-1] == "COMMIT"       # every write (and the targets read) is before COMMIT
    assert h["scheduled"] == [42]        # reminder only after COMMIT


def test_bad_duration_writes_nothing(fake):
    h = fake(_FakeConn())
    with pytest.raises(ValueError):
        auth.add_job(1, dict(DATA, duration_days=5))
    c = h["conn"]
    assert not any(s.startswith("INSERT") for s in c.calls)
    assert c.count("BEGIN") == 0 and c.count("COMMIT") == 0
    assert h["scheduled"] == []
