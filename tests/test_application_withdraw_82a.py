"""Task 8.2a — the applicant withdraws an application + re-applies (backend only).

No DB: a small stateful fake connection (auth.get_conn / release_conn patched) answers the SQL of
withdraw_application / apply_job / _fetch_applicant_counts_batch; the HTTP mapping (404 / 409 / 429)
goes through the real routes with verify_token overridden.
Run: python -m pytest tests/test_application_withdraw_82a.py -q
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "test-secret-withdraw-82a-" + "x" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import server as srv

APPLICANT, OTHER, COMPANY, JOB, APP = 11, 12, 50, 7, 300


class _FakeDB:
    """In-memory job / application / pipeline / appointment state behind conn.run(sql, **params)."""

    def __init__(self, app_status="interview", job_status="active", with_app=True):
        self.job = {"status": job_status, "closed_at": None, "expires_at": None, "company_id": COMPANY,
                    "title": "مطور", "archived_at": None, "admin_hidden_at": None}
        self.apps = {}
        if with_app:
            self.apps[APP] = {"job_id": JOB, "user_id": APPLICANT, "status": app_status, "cover_letter": ""}
        self.entry = ({"id": 900, "application_id": APP, "source": "application", "stage": "interview"}
                      if with_app else None)
        self.stage_events = []      # {from, to, by, reason, at}
        future = datetime.now(timezone.utc) + timedelta(days=2)
        self.appointments = [
            {"id": 70, "status": "confirmed", "scheduled_at": future, "applicant_id": APPLICANT, "job_id": JOB},
            {"id": 71, "status": "completed", "scheduled_at": future, "applicant_id": APPLICANT, "job_id": JOB},
        ]
        self.appt_events = []
        self.columns = []
        self.tx = []

    # ── conn.run ─────────────────────────────────────────────────────────────
    def run(self, sql, **p):
        q = " ".join(sql.split())
        if q in ("BEGIN", "COMMIT", "ROLLBACK"):
            self.tx.append(q)
            return []
        if q.startswith("SELECT ja.user_id, ja.job_id, ja.status, j.company_id"):
            a = self.apps.get(p["id"])
            if not a:
                return []
            j = self.job
            return [[a["user_id"], a["job_id"], a["status"], j["company_id"], j["title"], j["status"],
                     j["closed_at"], j["expires_at"], j["archived_at"], j["admin_hidden_at"]]]
        if q.startswith("UPDATE job_applications SET status = 'withdrawn'"):
            self.apps[p["id"]]["status"] = "withdrawn"
            return []
        if q.startswith("SELECT id, application_id, source FROM job_pipeline_entries"):
            e = self.entry
            return [[e["id"], e["application_id"], e["source"]]] if e else []
        if q.startswith("INSERT INTO job_pipeline_entries"):
            self.entry = {"id": 901, "application_id": p["app"], "source": p["src"], "stage": p["stage"]}
            return [[901]]
        if q.startswith("SELECT id, stage FROM job_pipeline_entries"):
            e = self.entry
            return [[e["id"], e["stage"]]] if e else []
        if q.startswith("SELECT id FROM job_pipeline_entries"):
            return [[self.entry["id"]]] if self.entry else []
        if q.startswith("UPDATE job_pipeline_entries SET stage"):
            self.entry["stage"] = p["stage"]
            return [[self.entry["id"]]]
        if q.startswith("INSERT INTO pipeline_stage_events"):
            self.stage_events.append({"from": p.get("from_s"), "to": p["to_s"], "by": p["by"],
                                      "reason": p["reason"], "at": datetime.now(timezone.utc)})
            return []
        if q.startswith("SELECT id, status FROM appointments"):
            assert "scheduled_at > NOW()" in q
            return [[a["id"], a["status"]] for a in self.appointments
                    if a["applicant_id"] == p["uid"] and a["job_id"] == p["jid"]
                    and a["status"] in auth._APPT_CANCEL_FROM]
        if q.startswith("UPDATE appointments SET status='cancelled'"):
            next(a for a in self.appointments if a["id"] == p["id"])["status"] = "cancelled"
            return []
        if q.startswith("INSERT INTO appointment_events"):
            self.appt_events.append(p)
            return []
        # apply_job
        if q.startswith("SELECT status, closed_at, expires_at, company_id, title, archived_at"):
            j = self.job
            return [[j["status"], j["closed_at"], j["expires_at"], j["company_id"], j["title"],
                     j["archived_at"], j["admin_hidden_at"]]]
        if q.startswith("INSERT INTO job_applications"):
            if any(a["job_id"] == p["jid"] and a["user_id"] == p["uid"] for a in self.apps.values()):
                return []
            self.apps[APP] = {"job_id": p["jid"], "user_id": p["uid"], "status": "pending", "cover_letter": p["cl"]}
            self.columns = [{"name": n} for n in ("id", "job_id", "user_id", "status", "applied_at")]
            return [[APP, p["jid"], p["uid"], "pending", None]]
        if q.startswith("SELECT id, status FROM job_applications"):
            return [[i, a["status"]] for i, a in self.apps.items()
                    if a["job_id"] == p["jid"] and a["user_id"] == p["uid"]]
        if q.startswith("SELECT changed_by FROM pipeline_stage_events"):
            ev = [e for e in self.stage_events if e["to"] == "withdrawn"]
            return [[ev[-1]["by"]]] if ev else []
        if q.startswith("SELECT COUNT(*) FROM pipeline_stage_events"):
            week = datetime.now(timezone.utc) - timedelta(days=7)
            return [[sum(1 for e in self.stage_events
                         if e["from"] == "withdrawn" and e["to"] == "new" and e["at"] > week)]]
        if q.startswith("UPDATE job_applications SET status = 'pending'"):
            a = self.apps[p["id"]]
            a["status"] = "pending"
            self.columns = [{"name": n} for n in ("id", "job_id", "user_id", "status", "applied_at")]
            return [[p["id"], a["job_id"], a["user_id"], "pending", None]]
        if q.startswith("SELECT full_name FROM users"):
            return [["سامي"]]
        if q.startswith("SELECT aggregation_count FROM notifications"):
            return []
        if q.startswith("SELECT job_id, COUNT(*) AS cnt FROM job_applications"):
            active_only = "<> 'withdrawn'" in q
            out = {}
            for a in self.apps.values():
                if active_only and a["status"] == "withdrawn":
                    continue
                out[a["job_id"]] = out.get(a["job_id"], 0) + 1
            return [[k, v] for k, v in out.items()]
        raise AssertionError("unexpected SQL: " + q[:120])


@pytest.fixture
def db(monkeypatch):
    holder = {}

    def use(**kw):
        d = _FakeDB(**kw)
        monkeypatch.setattr(auth, "get_conn", lambda: d)
        monkeypatch.setattr(auth, "release_conn", lambda c: None)
        d.notifications = []
        monkeypatch.setattr(auth, "create_or_update_aggregated_notification",
                            lambda **n: d.notifications.append(n))
        monkeypatch.setattr(auth, "create_notification", lambda **n: d.notifications.append(n))
        holder["db"] = d
        return d
    yield use
    srv.app.dependency_overrides.clear()


def _client(uid, utype="emp"):
    srv.app.dependency_overrides[srv.verify_token] = lambda: {"user_id": uid, "user_type": utype}
    return TestClient(srv.app)


def _withdraw(uid=APPLICANT):
    return _client(uid).post(f"/jobs/applications/{APP}/withdraw")


def _apply(uid=APPLICANT):
    return _client(uid).post(f"/jobs/{JOB}/apply", json={"cover_letter": ""})


# ── withdraw ─────────────────────────────────────────────────────────────────
def test_owner_withdraws_cancels_upcoming_interview(db):
    d = db(app_status="interview")
    r = _withdraw()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["data"]["status"] == "withdrawn"
    assert body["data"]["cancelled_appointments"] == [70]
    assert d.apps[APP]["status"] == "withdrawn" and d.entry["stage"] == "withdrawn"
    assert d.stage_events[-1] == {**d.stage_events[-1], "from": "interview", "to": "withdrawn",
                                  "by": APPLICANT, "reason": auth.WITHDRAW_REASON}
    assert [a["status"] for a in d.appointments] == ["cancelled", "completed"]
    assert len(d.appt_events) == 1 and d.appt_events[0]["etype"] == "appointment_cancelled"
    assert json.loads(d.appt_events[0]["payload"]) == {"reason": auth.WITHDRAW_APPT_CANCEL_REASON,
                                                        "cause": auth.WITHDRAW_REASON}
    assert d.notifications == []          # no notification to the company
    assert d.tx[-1] == "COMMIT"


def test_not_owner_is_404(db):
    d = db()
    r = _withdraw(uid=OTHER)
    assert r.status_code == 404 and r.json()["ok"] is False
    assert d.apps[APP]["status"] == "interview" and d.tx[-1] == "ROLLBACK"


@pytest.mark.parametrize("kw,code", [
    ({"app_status": "hired"}, "application_final"),
    ({"app_status": "rejected"}, "application_final"),
    ({"app_status": "pending", "job_status": "closed"}, "job_not_active"),
])
def test_final_or_closed_job_is_409(db, kw, code):
    d = db(**kw)
    r = _withdraw()
    assert r.status_code == 409 and r.json()["error"]["code"] == code
    assert d.stage_events == [] and d.appt_events == []


def test_company_cannot_reclassify_withdrawn(db):
    d = db(app_status="withdrawn")

    def fake_run(sql, **p):    # update_application_status lock row: user, job, company, title, status
        if " ".join(sql.split()).startswith("SELECT ja.user_id, ja.job_id, j.company_id"):
            return [[APPLICANT, JOB, COMPANY, "مطور", "withdrawn"]]
        return _FakeDB.run(d, sql, **p)
    d.run = fake_run
    with pytest.raises(auth.ApplicationStateError):
        auth.update_application_status(APP, "interview", actor_id=COMPANY)
    assert d.apps[APP]["status"] == "withdrawn"


# ── apply / re-apply ─────────────────────────────────────────────────────────
def test_first_apply_sends_new_applicant_notification(db):
    d = db(with_app=False)
    r = _apply()
    assert r.status_code == 200 and r.json().get("reapplied") is None
    assert len(d.notifications) == 1 and d.notifications[0]["type_"] == "job_applied"


def test_reapply_updates_same_row_without_notification(db):
    d = db(app_status="contacted")
    assert _withdraw().status_code == 200
    r = _apply()
    assert r.status_code == 200, r.text
    assert r.json()["reapplied"] is True and r.json()["id"] == APP
    assert list(d.apps) == [APP] and d.apps[APP]["status"] == "pending"
    assert d.entry["stage"] == "new"
    assert (d.stage_events[-1]["from"], d.stage_events[-1]["to"]) == ("withdrawn", "new")
    assert d.notifications == []
    # _final_status_on_job reads the current state only → the old withdrawal no longer blocks
    d.run_orig = d.run
    d.run = lambda sql, **p: ([] if "company_candidate_job_refs" in sql
                              else [[d.entry["stage"]]] if "SELECT stage FROM job_pipeline_entries" in sql
                              else d.run_orig(sql, **p))
    assert auth._final_status_on_job(d, COMPANY, APPLICANT, JOB, d.apps[APP]["status"]) is None


def test_fourth_reapply_in_a_week_is_429(db):
    d = db(app_status="pending")
    for _ in range(3):
        assert _withdraw().status_code == 200
        assert _apply().json().get("reapplied") is True
    assert _withdraw().status_code == 200
    r = _apply()
    assert r.status_code == 429 and r.json()["error"]["code"] == "reapply_limit"
    assert d.apps[APP]["status"] == "withdrawn" and d.tx[-1] == "ROLLBACK"


def test_other_state_stays_already_applied(db):
    db(app_status="viewed")
    r = _apply()
    assert r.status_code == 200 and r.json()["already_applied"] is True


# ── counters / applicant's own list ──────────────────────────────────────────
def test_applicant_count_excludes_withdrawn(db):
    d = db(app_status="pending")
    d.apps[301] = {"job_id": JOB, "user_id": OTHER, "status": "withdrawn", "cover_letter": ""}
    assert auth._fetch_applicant_counts_batch(d, [JOB]) == {JOB: 1}


def test_applicant_sees_withdrawn_and_map_covers_it():
    assert auth.applicant_visible_status("withdrawn") == "withdrawn"
    assert auth.LEGACY_APP_STATUS_TO_PIPELINE_STAGE["withdrawn"] == "withdrawn"
