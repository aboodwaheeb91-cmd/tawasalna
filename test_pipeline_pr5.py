"""
PR-5 Integration Tests — Pipeline Notes + Unified Appointment Endpoint

41 tests covering:
  Group A  (01–06): Pipeline notes CRUD
  Group B  (07–13): Appointment creation via POST /api/appointments (unified endpoint)
  Group C  (14–20): Appointment validation and rejection
  Group D  (21–24): Security / ownership isolation
  Group E  (25–32): System isolation + PR-5 field correctness
  Group F  (33–40): New correctness tests (atomic guards, UTC, lifecycle)
  Group G  (41):    Ambiguous payload guard (application_id + candidate_id + job_id → 400)

All appointment creates use POST /api/appointments (parallel route removed).
Runs against real PostgreSQL (SUPABASE_DB_URL env var).
"""

import os
import threading
import unittest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")
DB_URL   = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _register(email, password, user_type, full_name=None, country_code="9620"):
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": password,
        "user_type": user_type,
        "full_name": full_name or email.split("@")[0],
        "country_code": country_code,
    })
    return r

def _login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    d = r.json()
    tok = d.get("token") or d.get("access_token") or (d.get("data") or {}).get("token")
    assert tok, f"Login failed for {email}: {d}"
    return tok

def _headers(jwt):
    return {"Authorization": f"Bearer {jwt}"}

import random, string
def _suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))

def _future_iso(hours=2):
    """UTC ISO with Z suffix — timezone-aware, always accepted by backend."""
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

def _naive_iso(hours=2):
    """Naive ISO — no timezone suffix — must be REJECTED by backend."""
    dt = datetime.utcnow() + timedelta(hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")  # no Z, no offset

def _db_conn():
    import pg8000.native as _pg
    from urllib.parse import urlparse
    p = urlparse(DB_URL)
    return _pg.Connection(
        user=p.username, password=p.password,
        host=p.hostname, port=(p.port or 5432),
        database=p.path.lstrip('/')
    )

def _db_count(table_expr, where_clause, **params):
    conn = _db_conn()
    try:
        rows = conn.run(
            f"SELECT COUNT(*) FROM {table_expr} WHERE {where_clause}",
            **params
        )
        return int(rows[0][0])
    finally:
        conn.close()


def _make_company_with_pipeline_entry(with_application=True):
    """
    Register: company + employee.
    Create: job, optional job_application, then pipeline entry.
    Returns: (co_jwt, co_id, emp_id, emp_tw_id, job_id, pipeline_entry_id, app_id)
    """
    suf = _suffix()
    _register(f"co_{suf}@ex.com", "pass123", "co", f"Company {suf}")
    _register(f"emp_{suf}@ex.com", "pass123", "emp", f"Employee {suf}")
    co_jwt = _login(f"co_{suf}@ex.com", "pass123")

    conn = _db_conn()
    try:
        co_rows  = conn.run("SELECT id FROM users WHERE email=:e", e=f"co_{suf}@ex.com")
        emp_rows = conn.run("SELECT id, tw_id FROM users WHERE email=:e", e=f"emp_{suf}@ex.com")
        co_id  = co_rows[0][0]
        emp_id = emp_rows[0][0]
        emp_tw = emp_rows[0][1]

        job_rows = conn.run(
            "INSERT INTO jobs(company_id, title, status) VALUES (:cid, 'مهندس', 'active') "
            "RETURNING id",
            cid=co_id
        )
        job_id = job_rows[0][0]

        app_id = None
        if with_application:
            app_rows = conn.run(
                "INSERT INTO job_applications(job_id, user_id, status) "
                "VALUES (:jid, :uid, 'pending') RETURNING id",
                jid=job_id, uid=emp_id
            )
            app_id = app_rows[0][0]

        source = "application" if with_application else "company_add"
        pe_rows = conn.run(
            "INSERT INTO job_pipeline_entries"
            "(company_id, candidate_id, job_id, application_id, stage, source, created_by) "
            "VALUES (:cid, :uid, :jid, :appid, 'new', :src, :cb) RETURNING id",
            cid=co_id, uid=emp_id, jid=job_id,
            appid=app_id, src=source, cb=co_id
        )
        pe_id = pe_rows[0][0]

        return co_jwt, co_id, emp_id, emp_tw, job_id, pe_id, app_id
    finally:
        conn.close()


def _make_second_company_with_entry():
    """Create a second independent company + pipeline setup (for cross-company tests)."""
    suf = _suffix()
    _register(f"co2_{suf}@ex.com", "pass123", "co", f"Company2 {suf}")
    _register(f"emp2_{suf}@ex.com", "pass123", "emp", f"Employee2 {suf}")
    co2_jwt = _login(f"co2_{suf}@ex.com", "pass123")

    conn = _db_conn()
    try:
        co2_rows  = conn.run("SELECT id FROM users WHERE email=:e", e=f"co2_{suf}@ex.com")
        emp2_rows = conn.run("SELECT id FROM users WHERE email=:e", e=f"emp2_{suf}@ex.com")
        co2_id  = co2_rows[0][0]
        emp2_id = emp2_rows[0][0]

        job_rows = conn.run(
            "INSERT INTO jobs(company_id, title, status) VALUES (:cid, 'مدير', 'active') "
            "RETURNING id",
            cid=co2_id
        )
        job2_id = job_rows[0][0]
        pe_rows = conn.run(
            "INSERT INTO job_pipeline_entries"
            "(company_id, candidate_id, job_id, stage, source, created_by) "
            "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
            cid=co2_id, uid=emp2_id, jid=job2_id, cb=co2_id
        )
        pe2_id = pe_rows[0][0]
        return co2_jwt, co2_id, emp2_id, job2_id, pe2_id
    finally:
        conn.close()


def _create_draft_appt_path_b(co_jwt, candidate_id, job_id, appt_type="interview"):
    """Create a draft appointment via Path B. Returns response."""
    return requests.post(
        f"{BASE_URL}/api/appointments",
        json={
            "candidate_id":    candidate_id,
            "job_id":          job_id,
            "appointment_type": appt_type,
            "mode":            "online",
        },
        headers=_headers(co_jwt)
    )


def _send_appt(co_jwt, appt_id, hours_ahead=73):
    """Send a draft appointment to pending_response."""
    return requests.post(
        f"{BASE_URL}/api/appointments/{appt_id}/send",
        json={
            "scheduled_at":  _future_iso(hours_ahead),
            "deadline_hours": 48,
            "online_url": "https://meet.example.com/test",
        },
        headers=_headers(co_jwt)
    )


# ══════════════════════════════════════════════════════════════════════════════
# Group A — Pipeline Notes CRUD (tests 01–06)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineNotesCRUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

    def _base(self):
        return f"{BASE_URL}/company/pipeline/{self.pe_id}/notes"

    def test_01_create_note(self):
        """POST creates a pipeline note and returns id + body."""
        r = requests.post(self._base(),
                          json={"body": "أول ملاحظة على الوظيفة"},
                          headers=_headers(self.co_jwt))
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d.get("ok"))
        note = d["data"]["note"]
        self.assertEqual(note["body"], "أول ملاحظة على الوظيفة")
        self.assertEqual(int(note["pipeline_entry_id"]), self.pe_id)
        self.assertIsNone(note.get("deleted_at"))
        self.__class__._note_id = int(note["id"])

    def test_02_list_notes(self):
        """GET returns the created note."""
        r = requests.get(self._base(), headers=_headers(self.co_jwt))
        self.assertEqual(r.status_code, 200, r.text)
        notes = r.json()["data"]["notes"]
        bodies = [n["body"] for n in notes]
        self.assertIn("أول ملاحظة على الوظيفة", bodies)

    def test_03_update_note(self):
        """PATCH updates the note body — self-contained (own note created inside test)."""
        r_create = requests.post(
            self._base(), json={"body": "ملاحظة للتعديل"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r_create.status_code, 200, r_create.text)
        note_id = int(r_create.json()["data"]["note"]["id"])

        r = requests.patch(
            f"{BASE_URL}/company/pipeline/notes/{note_id}",
            json={"body": "ملاحظة معدّلة"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["note"]["body"], "ملاحظة معدّلة")

    def test_04_delete_note(self):
        """DELETE soft-deletes the note — self-contained (own note created inside test)."""
        r_create = requests.post(
            self._base(), json={"body": "ملاحظة للحذف"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r_create.status_code, 200, r_create.text)
        note_id = int(r_create.json()["data"]["note"]["id"])

        r = requests.delete(
            f"{BASE_URL}/company/pipeline/notes/{note_id}",
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 200, r.text)
        r2 = requests.get(self._base(), headers=_headers(self.co_jwt))
        notes = r2.json()["data"]["notes"]
        self.assertNotIn(note_id, [int(n["id"]) for n in notes])

    def test_05_empty_body_rejected(self):
        """POST with whitespace-only body returns 400."""
        r = requests.post(self._base(),
                          json={"body": "   "},
                          headers=_headers(self.co_jwt))
        self.assertEqual(r.status_code, 400, r.text)

    def test_06_note_does_not_affect_general_notes(self):
        """Creating pipeline note does NOT change company_saved_candidates.notes."""
        requests.post(self._base(),
                      json={"body": "ملاحظة pipeline"},
                      headers=_headers(self.co_jwt))
        conn = _db_conn()
        try:
            rows = conn.run(
                "SELECT notes FROM company_saved_candidates "
                "WHERE company_id=:cid AND candidate_id=:uid",
                cid=self.co_id, uid=self.emp_id
            )
            if rows:
                self.assertIsNone(rows[0][0],
                    "Pipeline note creation must not write to company_saved_candidates.notes")
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Group B — Appointment Creation via Unified Endpoint (tests 07–13)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineAppointmentCreation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

    def test_07_create_appointment_path_b_with_application(self):
        """Path B + real applicant: draft created with pipeline_entry_id + application_id."""
        r = _create_draft_appt_path_b(self.co_jwt, self.emp_id, self.job_id)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()["data"]
        self.assertEqual(int(d["pipeline_entry_id"]), self.pe_id)
        self.assertEqual(int(d["application_id"]), self.app_id)
        self.assertEqual(d["appointment_type"], "interview")
        self.assertEqual(d["status"], "draft")
        self.__class__._appt_id = int(d["id"])

    def test_08_create_appointment_without_application(self):
        """Non-applicant with pipeline entry: draft with application_id=null."""
        suf = _suffix()
        _register(f"emp_noapply_{suf}@ex.com", "pass123", "emp", f"NoApply {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_noapply_{suf}@ex.com")
            emp3_id = emp_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=self.co_id, uid=emp3_id, jid=self.job_id, cb=self.co_id
            )
            pe3_id = pe_rows[0][0]
        finally:
            conn.close()

        r = _create_draft_appt_path_b(self.co_jwt, emp3_id, self.job_id, "call")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()["data"]
        self.assertEqual(int(d["pipeline_entry_id"]), pe3_id)
        self.assertIsNone(d.get("application_id"))
        self.assertEqual(d["status"], "draft")

    def test_09_no_pipeline_entry_returns_409(self):
        """Candidate with no pipeline entry → 409 pipeline_entry_required."""
        suf = _suffix()
        _register(f"emp_noentry_{suf}@ex.com", "pass123", "emp", f"NoEntry {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_noentry_{suf}@ex.com")
            emp_id = emp_rows[0][0]
        finally:
            conn.close()

        r = _create_draft_appt_path_b(self.co_jwt, emp_id, self.job_id)
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json().get("code"), "pipeline_entry_required")

    def test_10_appointment_does_not_create_job_applications(self):
        """Creating appointment via Path B must not insert into job_applications."""
        suf = _suffix()
        _register(f"emp_t10_{suf}@ex.com", "pass123", "emp", f"T10 {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_t10_{suf}@ex.com")
            emp_t10_id = emp_rows[0][0]
            # Create a separate job for this test to keep count clean
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Test10 Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_t10 = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_t10_id, jid=job_t10, cb=self.co_id
            )
        finally:
            conn.close()

        before = _db_count("job_applications", "job_id=:jid", jid=job_t10)
        # Create the appointment
        r = _create_draft_appt_path_b(self.co_jwt, emp_t10_id, job_t10)
        self.assertEqual(r.status_code, 200, r.text)
        after = _db_count("job_applications", "job_id=:jid", jid=job_t10)
        self.assertEqual(before, after,
                         "create_appointment (Path B) must not insert into job_applications")

    def test_11_appointment_does_not_save_to_talent_bank(self):
        """Creating appointment via Path B must not insert into company_saved_candidates."""
        suf = _suffix()
        _register(f"emp_t11_{suf}@ex.com", "pass123", "emp", f"T11 {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_t11_{suf}@ex.com")
            emp_t11_id = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Test11 Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_t11 = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_t11_id, jid=job_t11, cb=self.co_id
            )
        finally:
            conn.close()

        before = _db_count("company_saved_candidates",
                           "company_id=:cid AND candidate_id=:uid",
                           cid=self.co_id, uid=emp_t11_id)
        r = _create_draft_appt_path_b(self.co_jwt, emp_t11_id, job_t11)
        self.assertEqual(r.status_code, 200, r.text)
        after = _db_count("company_saved_candidates",
                          "company_id=:cid AND candidate_id=:uid",
                          cid=self.co_id, uid=emp_t11_id)
        self.assertEqual(before, after,
                         "create_appointment (Path B) must not insert into company_saved_candidates")

    def test_12_pipeline_entry_id_set_in_db(self):
        """After appointment creation, appointments.pipeline_entry_id is set correctly."""
        count = _db_count(
            "appointments",
            "pipeline_entry_id=:eid AND company_id=:cid",
            eid=self.pe_id, cid=self.co_id
        )
        self.assertGreater(count, 0,
                           "No appointment row found with correct pipeline_entry_id")

    def test_13_participant_role_is_applicant(self):
        """Appointment participant for applicant has role='applicant' — self-contained."""
        # Create a fresh emp+job+entry for this test to avoid dup-guard conflicts
        suf = _suffix()
        _register(f"emp_role_{suf}@ex.com", "pass123", "emp", f"Role {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_role_{suf}@ex.com")
            emp_r = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'RoleTest Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_r = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_r, jid=job_r, cb=self.co_id
            )
        finally:
            conn.close()

        r = _create_draft_appt_path_b(self.co_jwt, emp_r, job_r, "interview")
        self.assertEqual(r.status_code, 200, r.text)
        appt_id = int(r.json()["data"]["id"])

        conn = _db_conn()
        try:
            rows = conn.run(
                "SELECT role FROM appointment_participants "
                "WHERE appointment_id=:aid AND user_id=:uid",
                aid=appt_id, uid=emp_r
            )
        finally:
            conn.close()
        self.assertTrue(rows, "No participant row found for new applicant")
        self.assertEqual(rows[0][0], "applicant",
                         f"Expected role='applicant', got '{rows[0][0]}'")


# ══════════════════════════════════════════════════════════════════════════════
# Group C — Validation and Rejection (tests 14–20)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineAppointmentValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

    def _post(self, payload):
        return requests.post(
            f"{BASE_URL}/api/appointments",
            json=payload, headers=_headers(self.co_jwt)
        )

    def _send(self, appt_id, scheduled_at_iso):
        return requests.post(
            f"{BASE_URL}/api/appointments/{appt_id}/send",
            json={"scheduled_at": scheduled_at_iso, "deadline_hours": 48,
                  "online_url": "https://meet.example.com/x"},
            headers=_headers(self.co_jwt)
        )

    def test_14_past_scheduled_at_rejected_on_send(self):
        """scheduled_at in the past is rejected by send endpoint — self-contained."""
        # Create isolated emp+job+entry so dup guard cannot fire from other tests
        suf = _suffix()
        _register(f"emp_past_{suf}@ex.com", "pass123", "emp", f"Past {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_past_{suf}@ex.com")
            emp_p = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Past Test Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_p = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_p, jid=job_p, cb=self.co_id
            )
        finally:
            conn.close()

        r_draft = self._post({"candidate_id": emp_p, "job_id": job_p})
        self.assertEqual(r_draft.status_code, 200, r_draft.text)
        appt_id = r_draft.json()["data"]["id"]

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        r = self._send(appt_id, past)
        self.assertEqual(r.status_code, 400, r.text)

    def test_15_application_id_conflict_returns_409(self):
        """Path A: application_id that doesn't match pipeline entry → 409 conflict."""
        # Setup: pipeline entry with no application_id (company_add)
        suf = _suffix()
        _register(f"emp_confl_{suf}@ex.com", "pass123", "emp", f"Conflict {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_confl_{suf}@ex.com")
            emp_c = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Conflict Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_c = job_rows[0][0]
            # Pipeline entry: application_id = NULL (no application)
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_c, jid=job_c, cb=self.co_id
            )
            # Now create an application from emp_c for the same job
            app_rows = conn.run(
                "INSERT INTO job_applications(job_id, user_id, status) "
                "VALUES (:jid, :uid, 'pending') RETURNING id",
                jid=job_c, uid=emp_c
            )
            app_c = app_rows[0][0]
        finally:
            conn.close()

        # Count appointments before the conflict attempt
        before_count = _db_count("appointments", "application_id=:aid", aid=app_c)

        # Path A: send application_id = app_c, but pipeline entry has application_id = NULL → conflict
        r = requests.post(
            f"{BASE_URL}/api/appointments",
            json={"application_id": app_c},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 409, r.text)
        d = r.json()
        self.assertEqual(d.get("code"), "pipeline_application_conflict",
                         f"Expected pipeline_application_conflict, got: {d}")

        # Verify no appointment row was created during the conflict
        after_count = _db_count("appointments", "application_id=:aid", aid=app_c)
        self.assertEqual(before_count, after_count,
                         "Conflict must not create any appointments row")

    def test_16_wrong_job_id_rejected(self):
        """job_id not belonging to this company returns 400 or 409."""
        suf = _suffix()
        _register(f"co_other_{suf}@ex.com", "pass123", "co", f"OtherCo {suf}")
        conn = _db_conn()
        try:
            co_rows = conn.run("SELECT id FROM users WHERE email=:e",
                               e=f"co_other_{suf}@ex.com")
            other_co_id = co_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title) VALUES (:cid, 'وظيفة أخرى') RETURNING id",
                cid=other_co_id
            )
            other_job_id = job_rows[0][0]
        finally:
            conn.close()

        r = self._post({
            "candidate_id": self.emp_id,
            "job_id": other_job_id,
        })
        self.assertIn(r.status_code, [400, 403, 409], r.text)

    def test_17_archived_job_rejected(self):
        """Appointment for archived job → 400."""
        conn = _db_conn()
        try:
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, archived_at) "
                "VALUES (:cid, 'وظيفة مؤرشفة', NOW()) RETURNING id",
                cid=self.co_id
            )
            arch_job_id = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=self.emp_id, jid=arch_job_id, cb=self.co_id
            )
        finally:
            conn.close()

        r = self._post({
            "candidate_id": self.emp_id,
            "job_id": arch_job_id,
        })
        self.assertEqual(r.status_code, 400, r.text)

    def test_18_invalid_mode_rejected(self):
        """mode='hybrid' returns 400 (only online/onsite allowed)."""
        r = self._post({
            "candidate_id": self.emp_id,
            "job_id": self.job_id,
            "mode": "hybrid",
        })
        self.assertEqual(r.status_code, 400, r.text)

    def test_19_naive_iso_rejected_on_send(self):
        """send with naive ISO (no Z or offset) → 400."""
        suf = _suffix()
        _register(f"emp_naive_{suf}@ex.com", "pass123", "emp", f"Naive {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_naive_{suf}@ex.com")
            emp_n = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Naive Test', 'active') RETURNING id",
                cid=self.co_id
            )
            job_n = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_n, jid=job_n, cb=self.co_id
            )
        finally:
            conn.close()

        r_draft = self._post({"candidate_id": emp_n, "job_id": job_n})
        self.assertEqual(r_draft.status_code, 200, f"Draft creation must succeed: {r_draft.text}")
        appt_id = r_draft.json()["data"]["id"]

        # Send with naive ISO (no timezone indicator)
        naive = _naive_iso(hours=75)
        r = requests.post(
            f"{BASE_URL}/api/appointments/{appt_id}/send",
            json={"scheduled_at": naive, "deadline_hours": 48,
                  "online_url": "https://meet.example.com/x"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("Timezone", r.text + r.json().get("detail", ""),
                      "Error message should mention Timezone requirement")

    def test_20_unauthenticated_rejected(self):
        """No JWT returns 401, 403, or 422."""
        r = requests.post(
            f"{BASE_URL}/api/appointments",
            json={"candidate_id": self.emp_id, "job_id": self.job_id}
        )
        self.assertIn(r.status_code, [401, 403, 422], r.text)


# ══════════════════════════════════════════════════════════════════════════════
# Group D — Security / Ownership (tests 21–24)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)
        cls.co2_jwt, cls.co2_id, cls.emp2_id, \
            cls.job2_id, cls.pe2_id = \
            _make_second_company_with_entry()
        r = requests.post(
            f"{BASE_URL}/company/pipeline/{cls.pe_id}/notes",
            json={"body": "ملاحظة خاصة بشركة A"},
            headers=_headers(cls.co_jwt)
        )
        d = r.json()
        cls.note_id = int(d["data"]["note"]["id"]) if r.ok else None

    def test_21_company_b_cannot_read_company_a_notes(self):
        """Company B cannot GET notes for Company A's pipeline entry."""
        r = requests.get(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            headers=_headers(self.co2_jwt)
        )
        self.assertIn(r.status_code, [403, 404], r.text)

    def test_22_company_b_cannot_create_note_in_company_a_entry(self):
        """Company B cannot POST a note to Company A's pipeline entry."""
        r = requests.post(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            json={"body": "محاولة اختراق"},
            headers=_headers(self.co2_jwt)
        )
        self.assertIn(r.status_code, [403, 404], r.text)

    def test_23_company_b_cannot_create_appointment_for_company_a_candidate(self):
        """Company B cannot schedule appointment for Company A's candidate/job."""
        r = requests.post(
            f"{BASE_URL}/api/appointments",
            json={"candidate_id": self.emp_id, "job_id": self.job_id},
            headers=_headers(self.co2_jwt)
        )
        self.assertIn(r.status_code, [400, 403, 404, 409], r.text)

    def test_24_employee_account_cannot_use_pipeline_endpoints(self):
        """Employee JWT cannot create pipeline notes or appointments."""
        suf = _suffix()
        _register(f"emp_intruder_{suf}@ex.com", "pass123", "emp", f"Intruder {suf}")
        emp_jwt = _login(f"emp_intruder_{suf}@ex.com", "pass123")

        r1 = requests.get(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            headers=_headers(emp_jwt)
        )
        self.assertIn(r1.status_code, [403, 404], r1.text)

        r2 = requests.post(
            f"{BASE_URL}/api/appointments",
            json={"candidate_id": self.emp_id, "job_id": self.job_id},
            headers=_headers(emp_jwt)
        )
        self.assertIn(r2.status_code, [403, 404], r2.text)


# ══════════════════════════════════════════════════════════════════════════════
# Group E — System Isolation (tests 25–32)
# ══════════════════════════════════════════════════════════════════════════════

class TestSystemIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

        conn = _db_conn()
        try:
            suf = _suffix()
            _register(f"emp_iso_{suf}@ex.com", "pass123", "emp", "IsoEmp")
            emp_iso_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                    e=f"emp_iso_{suf}@ex.com")
            cls.emp_iso_id = emp_iso_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'وظيفة ثانية', 'active') RETURNING id",
                cid=cls.co_id
            )
            cls.job2_id = job_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=cls.co_id, uid=cls.emp_id, jid=cls.job2_id, cb=cls.co_id
            )
            cls.pe2_id = pe_rows[0][0]
        finally:
            conn.close()

    def test_25_pipeline_note_isolated_per_pipeline_entry(self):
        """Same candidate in 2 jobs has separate notes per pipeline entry."""
        r1 = requests.post(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            json={"body": "ملاحظة على الوظيفة الأولى"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r1.status_code, 200, r1.text)

        r2 = requests.post(
            f"{BASE_URL}/company/pipeline/{self.pe2_id}/notes",
            json={"body": "ملاحظة على الوظيفة الثانية"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        notes1 = requests.get(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            headers=_headers(self.co_jwt)
        ).json()["data"]["notes"]
        bodies1 = [n["body"] for n in notes1]
        self.assertIn("ملاحظة على الوظيفة الأولى", bodies1)
        self.assertNotIn("ملاحظة على الوظيفة الثانية", bodies1)

    def test_26_pipeline_note_does_not_change_stage(self):
        """Adding a pipeline note does not change job_pipeline_entries.stage."""
        conn = _db_conn()
        try:
            before = conn.run(
                "SELECT stage FROM job_pipeline_entries WHERE id=:eid", eid=self.pe_id
            )[0][0]
        finally:
            conn.close()

        requests.post(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            json={"body": "ملاحظة لا تغير المرحلة"},
            headers=_headers(self.co_jwt)
        )

        conn = _db_conn()
        try:
            after = conn.run(
                "SELECT stage FROM job_pipeline_entries WHERE id=:eid", eid=self.pe_id
            )[0][0]
        finally:
            conn.close()

        self.assertEqual(before, after,
                         "Adding pipeline note must not change the pipeline stage")

    def test_27_pipeline_note_does_not_change_application_status(self):
        """Adding a pipeline note does not change job_applications.status."""
        self.assertIsNotNone(
            self.app_id,
            "setUpClass must supply a real app_id (with_application=True)"
        )
        conn = _db_conn()
        try:
            before = conn.run(
                "SELECT status FROM job_applications WHERE id=:aid", aid=self.app_id
            )[0][0]
        finally:
            conn.close()

        requests.post(
            f"{BASE_URL}/company/pipeline/{self.pe_id}/notes",
            json={"body": "لا أغير الحالة"},
            headers=_headers(self.co_jwt)
        )

        conn = _db_conn()
        try:
            after = conn.run(
                "SELECT status FROM job_applications WHERE id=:aid", aid=self.app_id
            )[0][0]
        finally:
            conn.close()

        self.assertEqual(before, after,
                         "Adding pipeline note must not change job_applications.status")

    def test_28_manage_panel_patch_does_not_create_pipeline_note(self):
        """PATCH /company/saved-candidates/{candidate_id} must not create pipeline_notes rows."""
        # Save the candidate first (may already be saved — ignore error)
        requests.post(
            f"{BASE_URL}/company/saved-candidates",
            json={"candidate_id": self.emp_id, "save_source": "manual"},
            headers=_headers(self.co_jwt)
        )

        before_notes = _db_count(
            "pipeline_notes",
            "pipeline_entry_id=:eid", eid=self.pe_id
        )
        # PATCH the manage panel — correct route: /company/saved-candidates/{candidate_id}
        requests.patch(
            f"{BASE_URL}/company/saved-candidates/{self.emp_id}",
            json={"notes": "ملاحظة عامة", "rating": 4},
            headers=_headers(self.co_jwt)
        )
        after_notes = _db_count(
            "pipeline_notes",
            "pipeline_entry_id=:eid", eid=self.pe_id
        )
        self.assertEqual(before_notes, after_notes,
                         "Manage panel PATCH must not create pipeline_notes rows")

    def test_29_general_note_does_not_affect_pipeline_notes(self):
        """Editing general note in manage panel does not change pipeline_notes."""
        before = _db_count(
            "pipeline_notes",
            "pipeline_entry_id=:eid", eid=self.pe_id
        )
        requests.patch(
            f"{BASE_URL}/company/saved-candidates/{self.emp_id}",
            json={"notes": "ملاحظة عامة معدّلة"},
            headers=_headers(self.co_jwt)
        )
        after = _db_count(
            "pipeline_notes",
            "pipeline_entry_id=:eid", eid=self.pe_id
        )
        self.assertEqual(before, after)

    def test_30_applicants_endpoint_includes_pipeline_entry_id(self):
        """GET /jobs/{job_id}/applicants returns pipeline_entry_id per applicant."""
        r = requests.get(
            f"{BASE_URL}/jobs/{self.job_id}/applicants",
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 200, r.text)
        applicants = r.json().get("applicants", [])
        emp_apps = [a for a in applicants if int(a.get("user_id", 0)) == self.emp_id]
        # Must find our specific applicant — test failure if missing
        self.assertTrue(emp_apps,
                        f"Expected emp_id={self.emp_id} in applicants for job {self.job_id}, "
                        f"got: {[a.get('user_id') for a in applicants]}")
        found = emp_apps[0]
        self.assertIn("pipeline_entry_id", found, "pipeline_entry_id missing from response")
        self.assertIn("pipeline_notes_count", found, "pipeline_notes_count missing from response")
        self.assertIn("stage", found, "stage missing from response")
        self.assertEqual(int(found["pipeline_entry_id"]), self.pe_id)

    def test_31_applicants_endpoint_shows_next_appointment(self):
        """GET /jobs/{job_id}/applicants returns next_appointment field."""
        r = requests.get(
            f"{BASE_URL}/jobs/{self.job_id}/applicants",
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 200, r.text)
        applicants = r.json().get("applicants", [])
        emp_apps = [a for a in applicants if int(a.get("user_id", 0)) == self.emp_id]
        self.assertTrue(emp_apps, f"Applicant {self.emp_id} not found")
        # next_appointment can be null (no active future appointments yet) or a dict
        self.assertIn("next_appointment", emp_apps[0],
                      "next_appointment key missing from applicant response")

    def test_32_archived_job_read_still_works(self):
        """GET /jobs/{job_id}/applicants still returns data for archived jobs."""
        conn = _db_conn()
        try:
            arch_rows = conn.run(
                "INSERT INTO jobs(company_id, title, archived_at) "
                "VALUES (:cid, 'Archived Read Test', NOW()) RETURNING id",
                cid=self.co_id
            )
            arch_job = arch_rows[0][0]
            conn.run(
                "INSERT INTO job_applications(job_id, user_id, status) "
                "VALUES (:jid, :uid, 'pending') RETURNING id",
                jid=arch_job, uid=self.emp_id
            )
        finally:
            conn.close()

        r = requests.get(
            f"{BASE_URL}/jobs/{arch_job}/applicants",
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 200, r.text)
        applicants = r.json().get("applicants", [])
        self.assertTrue(applicants, "Should return applicants even for archived job")


# ══════════════════════════════════════════════════════════════════════════════
# Group F — Atomic guards, lifecycle, UTC (tests 33–40)
# ══════════════════════════════════════════════════════════════════════════════

class TestAppointmentAtomicAndLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

    def test_33_path_b_no_application_id_returns_db_value(self):
        """Path B (no application_id sent): response includes correct application_id from DB."""
        # Create a fresh emp+job+entry with an application so the DB value is non-null
        suf = _suffix()
        _register(f"emp_t33_{suf}@ex.com", "pass123", "emp", f"T33 {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_t33_{suf}@ex.com")
            emp_33 = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'T33 Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_33 = job_rows[0][0]
            app_rows = conn.run(
                "INSERT INTO job_applications(job_id, user_id, status) "
                "VALUES (:jid, :uid, 'pending') RETURNING id",
                jid=job_33, uid=emp_33
            )
            app_33 = app_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, application_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, :appid, 'new', 'application', :cb)",
                cid=self.co_id, uid=emp_33, jid=job_33, appid=app_33, cb=self.co_id
            )
        finally:
            conn.close()

        # Path B: send only candidate_id + job_id — no application_id
        r = _create_draft_appt_path_b(self.co_jwt, emp_33, job_33)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()["data"]
        self.assertIsNotNone(d.get("application_id"),
                             "Path B must return application_id from DB when it exists")
        self.assertEqual(int(d["application_id"]), app_33,
                         "Path B must return the DB-stored application_id, not null")

    def test_34_concurrent_creates_only_one_succeeds(self):
        """Concurrent creates for same pipeline entry: exactly one succeeds, others get 400."""
        suf = _suffix()
        _register(f"emp_conc_{suf}@ex.com", "pass123", "emp", f"Concurrent {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_conc_{suf}@ex.com")
            emp_c = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Concurrent Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_c = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_c, jid=job_c, cb=self.co_id
            )
        finally:
            conn.close()

        results = []
        lock = threading.Lock()

        def create():
            r = _create_draft_appt_path_b(self.co_jwt, emp_c, job_c)
            with lock:
                results.append(r.status_code)

        threads = [threading.Thread(target=create) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ok_count  = results.count(200)
        err_count = sum(1 for s in results if s in (400, 409))
        self.assertEqual(ok_count, 1,
                         f"Expected exactly 1 success, got: {results}")
        self.assertEqual(ok_count + err_count, 3,
                         f"Unexpected status codes: {results}")

    def test_35_utc_storage_verified(self):
        """After send, scheduled_at stored in DB has timezone info (UTC)."""
        suf = _suffix()
        _register(f"emp_utc_{suf}@ex.com", "pass123", "emp", f"UTC {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_utc_{suf}@ex.com")
            emp_u = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'UTC Test', 'active') RETURNING id",
                cid=self.co_id
            )
            job_u = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_u, jid=job_u, cb=self.co_id
            )
        finally:
            conn.close()

        r_draft = _create_draft_appt_path_b(self.co_jwt, emp_u, job_u)
        self.assertEqual(r_draft.status_code, 200, r_draft.text)
        appt_id = r_draft.json()["data"]["id"]

        r_send = _send_appt(self.co_jwt, appt_id, hours_ahead=73)
        self.assertEqual(r_send.status_code, 200, r_send.text)

        conn = _db_conn()
        try:
            rows = conn.run(
                "SELECT scheduled_at FROM appointments WHERE id=:aid", aid=appt_id
            )
        finally:
            conn.close()

        self.assertTrue(rows, "Appointment row not found")
        stored_dt = rows[0][0]  # pg8000 returns datetime object
        self.assertIsNotNone(stored_dt, "scheduled_at should be set after send")
        # pg8000 returns timezone-aware datetime for TIMESTAMPTZ columns
        self.assertIsNotNone(stored_dt.tzinfo,
                             f"scheduled_at must be stored with timezone info, got: {stored_dt}")

    def test_36_send_preserves_pipeline_entry_id(self):
        """After send (draft → pending_response), pipeline_entry_id is unchanged in DB."""
        suf = _suffix()
        _register(f"emp_send_{suf}@ex.com", "pass123", "emp", f"Send {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_send_{suf}@ex.com")
            emp_s = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Send Test', 'active') RETURNING id",
                cid=self.co_id
            )
            job_s = job_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=self.co_id, uid=emp_s, jid=job_s, cb=self.co_id
            )
            pe_s = pe_rows[0][0]
        finally:
            conn.close()

        r_draft = _create_draft_appt_path_b(self.co_jwt, emp_s, job_s)
        self.assertEqual(r_draft.status_code, 200, r_draft.text)
        appt_id = r_draft.json()["data"]["id"]
        self.assertEqual(int(r_draft.json()["data"]["pipeline_entry_id"]), pe_s)

        r_send = _send_appt(self.co_jwt, appt_id, hours_ahead=73)
        self.assertEqual(r_send.status_code, 200, r_send.text)
        self.assertEqual(int(r_send.json()["data"]["pipeline_entry_id"]), pe_s,
                         "pipeline_entry_id must be preserved after send")

    def test_37_cancel_preserves_pipeline_entry_id(self):
        """After cancel, pipeline_entry_id is still set in DB (row persists)."""
        suf = _suffix()
        _register(f"emp_canc_{suf}@ex.com", "pass123", "emp", f"Cancel {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_canc_{suf}@ex.com")
            emp_ca = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Cancel Test', 'active') RETURNING id",
                cid=self.co_id
            )
            job_ca = job_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=self.co_id, uid=emp_ca, jid=job_ca, cb=self.co_id
            )
            pe_ca = pe_rows[0][0]
        finally:
            conn.close()

        r_draft = _create_draft_appt_path_b(self.co_jwt, emp_ca, job_ca)
        self.assertEqual(r_draft.status_code, 200, r_draft.text)
        appt_id = r_draft.json()["data"]["id"]
        pe_from_create = int(r_draft.json()["data"]["pipeline_entry_id"])
        self.assertEqual(pe_from_create, pe_ca)

        # Send first so we can cancel (cancel requires pending_response)
        r_send = _send_appt(self.co_jwt, appt_id, hours_ahead=73)
        self.assertEqual(r_send.status_code, 200, r_send.text)

        # Cancel
        r_cancel = requests.post(
            f"{BASE_URL}/api/appointments/{appt_id}/cancel",
            json={"reason": "اختبار"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r_cancel.status_code, 200, r_cancel.text)

        # Verify pipeline_entry_id still in DB
        conn = _db_conn()
        try:
            rows = conn.run(
                "SELECT pipeline_entry_id, status FROM appointments WHERE id=:aid",
                aid=appt_id
            )
        finally:
            conn.close()

        self.assertTrue(rows)
        self.assertEqual(int(rows[0][0]), pe_ca,
                         "pipeline_entry_id must be preserved after cancel")
        self.assertEqual(rows[0][1], "cancelled")

    def test_38_talent_bank_removal_does_not_delete_appointment(self):
        """Removing candidate from talent bank does not delete their appointment rows."""
        suf = _suffix()
        _register(f"emp_tbr_{suf}@ex.com", "pass123", "emp", f"TBRem {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_tbr_{suf}@ex.com")
            emp_tb = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'TBRemove Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_tb = job_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=self.co_id, uid=emp_tb, jid=job_tb, cb=self.co_id
            )
            pe_tb = pe_rows[0][0]
        finally:
            conn.close()

        # Save to talent bank
        requests.post(
            f"{BASE_URL}/company/saved-candidates",
            json={"candidate_id": emp_tb, "save_source": "manual"},
            headers=_headers(self.co_jwt)
        )

        # Create appointment
        r_draft = _create_draft_appt_path_b(self.co_jwt, emp_tb, job_tb)
        self.assertEqual(r_draft.status_code, 200, r_draft.text)
        appt_id = r_draft.json()["data"]["id"]

        # Remove from talent bank
        requests.delete(
            f"{BASE_URL}/company/saved-candidates/{emp_tb}",
            headers=_headers(self.co_jwt)
        )

        # Appointment row must still exist
        conn = _db_conn()
        try:
            rows = conn.run("SELECT id FROM appointments WHERE id=:aid", aid=appt_id)
        finally:
            conn.close()

        self.assertTrue(rows,
                        "Appointment must still exist after removing candidate from talent bank")

    def test_39_talent_bank_removal_does_not_delete_pipeline_notes(self):
        """Removing candidate from talent bank does not delete their pipeline notes."""
        suf = _suffix()
        _register(f"emp_tbn_{suf}@ex.com", "pass123", "emp", f"TBNote {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_tbn_{suf}@ex.com")
            emp_tbn = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'TBNote Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_tbn = job_rows[0][0]
            pe_rows = conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb) RETURNING id",
                cid=self.co_id, uid=emp_tbn, jid=job_tbn, cb=self.co_id
            )
            pe_tbn = pe_rows[0][0]
        finally:
            conn.close()

        # Save to talent bank
        requests.post(
            f"{BASE_URL}/company/saved-candidates",
            json={"candidate_id": emp_tbn, "save_source": "manual"},
            headers=_headers(self.co_jwt)
        )

        # Create pipeline note
        r_note = requests.post(
            f"{BASE_URL}/company/pipeline/{pe_tbn}/notes",
            json={"body": "ملاحظة مهمة لا تُحذف"},
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r_note.status_code, 200, r_note.text)
        note_id = r_note.json()["data"]["note"]["id"]

        # Remove from talent bank
        requests.delete(
            f"{BASE_URL}/company/saved-candidates/{emp_tbn}",
            headers=_headers(self.co_jwt)
        )

        # Note must still exist (not soft-deleted)
        conn = _db_conn()
        try:
            rows = conn.run(
                "SELECT id, deleted_at FROM pipeline_notes WHERE id=:nid",
                nid=note_id
            )
        finally:
            conn.close()

        self.assertTrue(rows, "Pipeline note row must still exist after talent bank removal")
        self.assertIsNone(rows[0][1],
                          "Pipeline note must not be soft-deleted after talent bank removal")

    def test_40_duplicate_create_rejected_returns_400(self):
        """Second create for same active pipeline entry returns 400 (dup guard)."""
        suf = _suffix()
        _register(f"emp_dup_{suf}@ex.com", "pass123", "emp", f"DupTest {suf}")
        conn = _db_conn()
        try:
            emp_rows = conn.run("SELECT id FROM users WHERE email=:e",
                                e=f"emp_dup_{suf}@ex.com")
            emp_d = emp_rows[0][0]
            job_rows = conn.run(
                "INSERT INTO jobs(company_id, title, status) "
                "VALUES (:cid, 'Dup Test Job', 'active') RETURNING id",
                cid=self.co_id
            )
            job_d = job_rows[0][0]
            conn.run(
                "INSERT INTO job_pipeline_entries"
                "(company_id, candidate_id, job_id, stage, source, created_by) "
                "VALUES (:cid, :uid, :jid, 'new', 'company_add', :cb)",
                cid=self.co_id, uid=emp_d, jid=job_d, cb=self.co_id
            )
        finally:
            conn.close()

        r1 = _create_draft_appt_path_b(self.co_jwt, emp_d, job_d)
        self.assertEqual(r1.status_code, 200, r1.text)

        r2 = _create_draft_appt_path_b(self.co_jwt, emp_d, job_d)
        self.assertEqual(r2.status_code, 400, r2.text)
        self.assertIn("موعد نشط", r2.text,
                      "Dup error should mention active appointment")


# ══════════════════════════════════════════════════════════════════════════════
# Group G — Ambiguous Payload (test 41)
# ══════════════════════════════════════════════════════════════════════════════

class TestAmbiguousPayload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.co_id, cls.emp_id, cls.emp_tw, \
            cls.job_id, cls.pe_id, cls.app_id = \
            _make_company_with_pipeline_entry(with_application=True)

    def test_41_ambiguous_payload_rejected(self):
        """Sending application_id + candidate_id + job_id together → 400 ambiguous_appointment_context."""
        # Count appointments before to verify no row is created
        before_count = _db_count(
            "appointments",
            "company_id=:cid AND application_id=:aid",
            cid=self.co_id, aid=self.app_id
        )

        r = requests.post(
            f"{BASE_URL}/api/appointments",
            json={
                "application_id": self.app_id,
                "candidate_id":   self.emp_id,
                "job_id":         self.job_id,
                "appointment_type": "interview",
                "mode": "online",
            },
            headers=_headers(self.co_jwt)
        )
        self.assertEqual(r.status_code, 400, r.text)
        d = r.json()
        self.assertEqual(d.get("code"), "ambiguous_appointment_context",
                         f"Expected ambiguous_appointment_context, got: {d}")

        # Must not create any appointment row
        after_count = _db_count(
            "appointments",
            "company_id=:cid AND application_id=:aid",
            cid=self.co_id, aid=self.app_id
        )
        self.assertEqual(before_count, after_count,
                         "Ambiguous payload must not create any appointments row")


if __name__ == "__main__":
    unittest.main(verbosity=2)
