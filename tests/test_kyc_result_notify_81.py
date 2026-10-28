"""Task 8.1 — KYC review result → the user (notification + email) + the rejection reason.

No DB — fake connections record what runs:
  route    PUT /admin/kyc/{id}/reject: reason missing / blank / not text / too long → 422 field reason
           (nothing written) · ok → reason trimmed + internal note reach admin_reject_kyc · approve unchanged
  review   reject writes reject_reason, approve clears it (NULL) — same UPDATE, before the COMMIT
  status   get_kyc_status never returns admin_note · reject_reason only while status = rejected
  notify   after the COMMIT · its failure never breaks the review · one event_key per review ·
           link /settings · mapped to a notification email whose template carries no reason
  upload   new documents clear reject_reason

Run: python -m pytest tests/test_kyc_result_notify_81.py -q
"""
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-kyc-result-81-" + "x" * 32)

import pytest
from fastapi.testclient import TestClient

import auth
import email_service
import server
import tw_settings

client = TestClient(server.app)
REVIEWED = datetime(2026, 10, 28, 9, 30, tzinfo=timezone.utc)


class FakeConn:
    """Records (sql, params); answers the few statements the KYC code runs."""

    def __init__(self, log, row=None, update_hits=True):
        self.log, self.row, self.update_hits, self.columns = log, row, update_hits, []

    def run(self, sql, **kw):
        self.log.append((" ".join(sql.split()), kw))
        if sql.startswith("UPDATE kyc_submissions"):
            return [[7]] if self.update_hits else []
        if sql.startswith("SELECT reviewed_at"):
            return [[REVIEWED]]
        if sql.startswith("SELECT ks.step") and self.row:
            self.columns = [{"name": k} for k in self.row]
            return [list(self.row.values())]
        return []


@pytest.fixture
def db(monkeypatch):
    log, state = [], {"row": None, "update_hits": True}

    @contextmanager
    def fake_db_conn():
        yield FakeConn(log, state["row"], state["update_hits"])

    monkeypatch.setattr(auth, "db_conn", fake_db_conn)
    monkeypatch.setattr(auth, "get_conn", lambda: FakeConn(log, state["row"], state["update_hits"]))
    monkeypatch.setattr(auth, "release_conn", lambda c: None)
    return log, state


def _update(log):
    return [(q, kw) for q, kw in log if q.startswith("UPDATE kyc_submissions")]


def _index(log, sql):
    return next(i for i, (q, _) in enumerate(log) if q == sql)


# ── route ──
@pytest.fixture
def route(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "check_admin", lambda request, *a, **k: {"sub": "admin"})
    monkeypatch.setattr(server, "admin_reject_kyc", lambda uid, reason, note="": calls.append((uid, reason, note)) or {"success": True})
    monkeypatch.setattr(server, "admin_approve_kyc", lambda uid, note="": calls.append((uid, "approve", note)) or {"success": True})
    return calls


@pytest.mark.parametrize("body", [{}, {"note": "x"}, {"reason": ""}, {"reason": "   \n "}, {"reason": None}])
def test_reject_without_reason_is_422_field_reason(route, body):
    r = client.put("/admin/kyc/5/reject", json=body)
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["field"] == "reason" and err["code"] == "required" and err["message"]
    assert route == []


def test_reject_reason_not_text_or_too_long_is_422(route):
    assert client.put("/admin/kyc/5/reject", json={"reason": 12}).json()["error"]["field"] == "reason"
    assert client.put("/admin/kyc/5/reject", json={"reason": "ok", "note": ["x"]}).json()["error"]["field"] == "note"
    long = "س" * (tw_settings.limit("kyc_reject_reason_max") + 1)
    r = client.put("/admin/kyc/5/reject", json={"reason": long})
    assert r.status_code == 422 and r.json()["error"]["field"] == "reason"
    assert route == []


def test_reject_passes_trimmed_reason_and_internal_note(route):
    r = client.put("/admin/kyc/5/reject", json={"reason": "  صورة غير واضحة  ", "note": " داخلي "})
    assert r.status_code == 200, r.text
    assert route == [(5, "صورة غير واضحة", "داخلي")]


def test_approve_unchanged(route):
    assert client.put("/admin/kyc/5/approve", json={"note": ""}).status_code == 200
    assert route == [(5, "approve", "")]


# ── review + notification ──
def test_reject_writes_reason_and_notifies_after_commit(db, monkeypatch):
    log, _ = db
    sent = []
    monkeypatch.setattr(auth, "create_notification", lambda **kw: log.append(("NOTIFY", kw)) or sent.append(kw) or {"id": 1})
    assert auth.admin_reject_kyc(5, "صورة غير واضحة", "داخلي") == {"success": True}
    (q, kw), = _update(log)
    assert kw["reason"] == "صورة غير واضحة" and kw["note"] == "داخلي" and kw["st"] == "rejected"
    assert "reject_reason=:reason" in q.replace(" ", "")
    assert _index(log, "COMMIT") < next(i for i, (q, _) in enumerate(log) if q == "NOTIFY")
    n, = sent
    assert n["user_id"] == 5 and n["type_"] == "kyc_rejected" and n["link"] == "/settings"
    assert n["entity_type"] == "kyc_submission" and n["entity_id"] == 7
    assert "صورة غير واضحة" not in (n["title"] + n["body"])          # the reason is shown on /settings only


def test_approve_clears_reason_and_notifies(db, monkeypatch):
    log, _ = db
    sent = []
    monkeypatch.setattr(auth, "create_notification", lambda **kw: sent.append(kw) or {"id": 1})
    auth.admin_approve_kyc(5, "")
    (_, kw), = _update(log)
    assert kw["reason"] is None and kw["st"] == "approved"
    assert sent[0]["type_"] == "kyc_approved"


def test_event_key_is_per_review(db, monkeypatch):
    keys = []
    monkeypatch.setattr(auth, "create_notification", lambda **kw: keys.append(kw["event_key"]) or {"id": 1})
    auth.notify_kyc_result(5, 7, False)
    global REVIEWED
    old, REVIEWED = REVIEWED, datetime(2026, 11, 2, tzinfo=timezone.utc)   # the re-submission reviewed later
    try:
        auth.notify_kyc_result(5, 7, False)
    finally:
        REVIEWED = old
    assert len(set(keys)) == 2


def test_notification_failure_never_breaks_the_review(db, monkeypatch, capsys):
    def boom(**kw):
        raise RuntimeError("notifications down")
    monkeypatch.setattr(auth, "create_notification", boom)
    assert auth.admin_reject_kyc(5, "سبب") == {"success": True}
    assert "COMMIT" in [q for q, _ in db[0]]
    assert "[NOTIF] kyc result not sent" in capsys.readouterr().out


def test_not_in_review_is_409_and_no_notification(db, monkeypatch):
    log, state = db
    state["update_hits"] = False
    sent = []
    monkeypatch.setattr(auth, "create_notification", lambda **kw: sent.append(kw))
    with pytest.raises(auth.KycStateError):
        auth.admin_reject_kyc(5, "سبب")
    assert sent == [] and "COMMIT" not in [q for q, _ in log]


def test_both_types_map_to_a_notification_email_without_reason():
    for type_ in auth.KYC_RESULT_TYPES.values():
        spec = email_service.TEMPLATES[auth.NOTIFICATION_EMAIL_TEMPLATES[type_]]
        assert spec["category"] == email_service.NOTIFICATION
        assert set(spec["vars"]) == {"name", "link"}                 # no reason / details variable
    out = email_service.render("notify_kyc_rejected", {"name": "رنا", "link": "https://tawasolna.com/settings",
                                                       "details": "SECRET-REASON"})
    assert "SECRET-REASON" not in out["html"] + out["text"] and out["subject"]


# ── status ──
_ROW = {"step": "rejected", "status": "rejected", "email_verified": True, "phone_verified": True,
        "submitted_at": None, "reviewed_at": None, "is_verified": False, "reject_reason": "صورة غير واضحة"}


def test_status_reason_only_when_rejected_never_admin_note(db):
    log, state = db
    state["row"] = dict(_ROW)
    out = auth.get_kyc_status(5)
    assert out["reject_reason"] == "صورة غير واضحة" and "admin_note" not in out
    assert "admin_note" not in log[-1][0]
    for st in ("pending", "approved"):
        state["row"] = dict(_ROW, step=st, status=st)
        out = auth.get_kyc_status(5)
        assert "reject_reason" not in out and "admin_note" not in out


def test_new_documents_clear_the_reason(db):
    log, _ = db
    auth.upload_kyc_docs(5, "kyc-docs/5_kyc-id-front_abcdef012345.jpg")
    (q, _), = _update(log)
    assert "reject_reason=NULL" in q.replace(" ", "")
