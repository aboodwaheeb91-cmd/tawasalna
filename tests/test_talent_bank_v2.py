"""
test_talent_bank_v2.py — PR-4: Talent Bank V2 UI + General Talent Management
Tests cover new fields (rating/priority/tags/follow_up_at/follow_up_status),
new filter params (priority/min_rating/tag/save_source_filter),
new sort options (rating_desc/priority_asc), and CRUD operations.

Runs on real PostgreSQL (SUPABASE_DB_URL).
No Skips allowed — all 45 tests run against the actual DB.

Auth call reduction: each class uses setUpClass (one register+login per class)
instead of per-test _setup_company_and_employee(), staying well under the
60-requests/minute rate limit on /auth/* endpoints.
"""

import os
import sys
import time
import random
import string
import unittest
import requests

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
DB_URL   = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _rand(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))

def _register(name, email, password, user_type, country_code="9620"):
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "full_name": name, "email": email, "password": password,
        "user_type": user_type, "country_code": country_code
    })
    d = r.json()
    return d.get("user") or d

def _login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    d = r.json()
    tok = d.get("token") or d.get("jwt") or d.get("access_token") or ""
    assert tok, f"Login failed for {email}: {d}"
    return tok

def _save(jwt, candidate_id, job_id=None):
    url = f"{BASE_URL}/company/saved-candidates/{candidate_id}"
    if job_id:
        url += f"?job_id={job_id}"
    return requests.post(url, headers={"Authorization": f"Bearer {jwt}"})

def _patch(jwt, candidate_id, payload):
    return requests.patch(
        f"{BASE_URL}/company/saved-candidates/{candidate_id}",
        json=payload,
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
    )

def _get_list(jwt, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/company/saved-candidates"
    if qs:
        url += "?" + qs
    return requests.get(url, headers={"Authorization": f"Bearer {jwt}"})

def _delete(jwt, candidate_id):
    return requests.delete(
        f"{BASE_URL}/company/saved-candidates/{candidate_id}",
        headers={"Authorization": f"Bearer {jwt}"}
    )

def _make_company_with_employee():
    """Register one company + one employee, save employee, return (jwt, emp_id, emp_tw)."""
    suffix = _rand()
    co  = _register(f"شركة {suffix}", f"co_{suffix}@ex.com", "pass123", "co")
    emp = _register(f"موظف {suffix}", f"emp_{suffix}@ex.com", "pass123", "emp")
    jwt = _login(f"co_{suffix}@ex.com", "pass123")
    emp_id = emp.get("id") or 0
    emp_tw = emp.get("tw_id") or ""
    _save(jwt, emp_id)
    return jwt, emp_id, emp_tw


# ── Group 1: Schema migration — follow_up_status column ──────────────────────

class TestFollowUpStatusColumn(unittest.TestCase):
    """Verify follow_up_status column exists after migration."""

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def test_01_column_exists_in_patch_response(self):
        """PATCH with follow_up_status='pending' succeeds — column must exist."""
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_status": "pending"})
        self.assertEqual(r.status_code, 200, r.text)
        item = r.json().get("item") or {}
        self.assertIn("follow_up_status", item, "follow_up_status missing from response")

    def test_02_column_appears_in_get_list(self):
        """GET list includes follow_up_status field per item."""
        _patch(self.co_jwt, self.emp_id, {"follow_up_status": "done"})
        r = _get_list(self.co_jwt, limit=5)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        self.assertTrue(len(items) > 0)
        self.assertIn("follow_up_status", items[0], "follow_up_status missing from list item")


# ── Group 2: Rating CRUD ──────────────────────────────────────────────────────

class TestRatingCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        _patch(self.co_jwt, self.emp_id, {"rating": None})

    def test_03_set_rating_1(self):
        r = _patch(self.co_jwt, self.emp_id, {"rating": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["rating"], 1)

    def test_04_set_rating_5(self):
        r = _patch(self.co_jwt, self.emp_id, {"rating": 5})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["rating"], 5)

    def test_05_update_rating(self):
        _patch(self.co_jwt, self.emp_id, {"rating": 3})
        r = _patch(self.co_jwt, self.emp_id, {"rating": 4})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["rating"], 4)

    def test_06_clear_rating_with_null(self):
        _patch(self.co_jwt, self.emp_id, {"rating": 3})
        r = _patch(self.co_jwt, self.emp_id, {"rating": None})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["item"]["rating"])

    def test_07_invalid_rating_0_rejected(self):
        r = _patch(self.co_jwt, self.emp_id, {"rating": 0})
        self.assertEqual(r.status_code, 400, "rating=0 should be rejected")

    def test_08_invalid_rating_6_rejected(self):
        r = _patch(self.co_jwt, self.emp_id, {"rating": 6})
        self.assertEqual(r.status_code, 400, "rating=6 should be rejected")


# ── Group 3: Priority CRUD ───────────────────────────────────────────────────

class TestPriorityCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        _patch(self.co_jwt, self.emp_id, {"priority": None})

    def test_09_set_priority_high(self):
        r = _patch(self.co_jwt, self.emp_id, {"priority": "high"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["priority"], "high")

    def test_10_set_priority_medium(self):
        r = _patch(self.co_jwt, self.emp_id, {"priority": "medium"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["priority"], "medium")

    def test_11_set_priority_low(self):
        r = _patch(self.co_jwt, self.emp_id, {"priority": "low"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["priority"], "low")

    def test_12_clear_priority_with_null(self):
        _patch(self.co_jwt, self.emp_id, {"priority": "high"})
        r = _patch(self.co_jwt, self.emp_id, {"priority": None})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["item"]["priority"])

    def test_13_invalid_priority_rejected(self):
        r = _patch(self.co_jwt, self.emp_id, {"priority": "urgent"})
        self.assertEqual(r.status_code, 400, "invalid priority should be rejected")


# ── Group 4: Tags CRUD ──────────────────────────────────────────────────────

class TestTagsCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        _patch(self.co_jwt, self.emp_id, {"tags": None})

    def test_14_set_tags(self):
        r = _patch(self.co_jwt, self.emp_id, {"tags": ["Python", "FastAPI", "SQL"]})
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertIn("tags", item)
        self.assertEqual(set(item["tags"]), {"Python", "FastAPI", "SQL"})

    def test_15_tags_dedup(self):
        r = _patch(self.co_jwt, self.emp_id, {"tags": ["Python", "python", "PYTHON"]})
        self.assertEqual(r.status_code, 200)
        tags = r.json()["item"]["tags"]
        # After dedup (case-insensitive), only 1 entry
        self.assertEqual(len(tags), 1)

    def test_16_clear_tags_with_null(self):
        _patch(self.co_jwt, self.emp_id, {"tags": ["Python"]})
        r = _patch(self.co_jwt, self.emp_id, {"tags": None})
        self.assertEqual(r.status_code, 200)
        tags = r.json()["item"]["tags"]
        self.assertFalse(tags, "tags should be empty after clearing")

    def test_17_empty_tags_list_clears(self):
        _patch(self.co_jwt, self.emp_id, {"tags": ["Python"]})
        r = _patch(self.co_jwt, self.emp_id, {"tags": []})
        self.assertEqual(r.status_code, 200)
        tags = r.json()["item"]["tags"]
        self.assertFalse(tags, "empty list should clear tags")

    def test_18_tag_too_long_rejected(self):
        long_tag = "A" * 31
        r = _patch(self.co_jwt, self.emp_id, {"tags": [long_tag]})
        self.assertEqual(r.status_code, 400, "tag > 30 chars should be rejected")

    def test_19_too_many_tags_rejected(self):
        tags = [f"tag{i}" for i in range(21)]
        r = _patch(self.co_jwt, self.emp_id, {"tags": tags})
        self.assertEqual(r.status_code, 400, "more than 20 tags should be rejected")


# ── Group 5: Follow-up CRUD ──────────────────────────────────────────────────

class TestFollowUpCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        _patch(self.co_jwt, self.emp_id, {"follow_up_at": None, "follow_up_status": None})

    def test_20_set_follow_up_pending(self):
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_at": "2026-09-01", "follow_up_status": "pending"})
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertEqual(item["follow_up_status"], "pending")
        self.assertIn("2026-09-01", item.get("follow_up_at", ""))

    def test_21_set_follow_up_done(self):
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_at": "2026-08-15", "follow_up_status": "done"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["follow_up_status"], "done")

    def test_22_set_follow_up_none(self):
        _patch(self.co_jwt, self.emp_id, {"follow_up_status": "pending"})
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_status": "none"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["item"]["follow_up_status"], "none")

    def test_23_clear_follow_up_with_null(self):
        _patch(self.co_jwt, self.emp_id, {"follow_up_at": "2026-09-01", "follow_up_status": "pending"})
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_at": None, "follow_up_status": None})
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertIsNone(item.get("follow_up_at"))
        self.assertIsNone(item.get("follow_up_status"))

    def test_24_invalid_follow_up_status_rejected(self):
        r = _patch(self.co_jwt, self.emp_id, {"follow_up_status": "overdue"})
        self.assertEqual(r.status_code, 400, "invalid follow_up_status should be rejected")


# ── Group 6: New filter params ───────────────────────────────────────────────

class TestNewFilters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up one company with two saved employees with different attributes."""
        suffix = _rand()
        co  = _register(f"شركة {suffix}", f"co_{suffix}@ex.com", "pass123", "co")
        e1  = _register(f"موظف1 {suffix}", f"emp1_{suffix}@ex.com", "pass123", "emp")
        e2  = _register(f"موظف2 {suffix}", f"emp2_{suffix}@ex.com", "pass123", "emp")
        cls.co_jwt = _login(f"co_{suffix}@ex.com", "pass123")
        cls.emp1_id = e1.get("id") or 0
        cls.emp2_id = e2.get("id") or 0
        # Save both
        _save(cls.co_jwt, cls.emp1_id)
        _save(cls.co_jwt, cls.emp2_id)
        # Set different attributes
        _patch(cls.co_jwt, cls.emp1_id, {
            "priority": "high", "rating": 5,
            "tags": ["Python", "React"], "follow_up_status": "pending"
        })
        _patch(cls.co_jwt, cls.emp2_id, {
            "priority": "low", "rating": 2,
            "tags": ["Java", "Spring"], "follow_up_status": "done"
        })

    def test_25_filter_by_priority_high(self):
        r = _get_list(self.co_jwt, priority="high", limit=50)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        for item in items:
            self.assertEqual(item["priority"], "high")
        # emp1 should be in results
        ids = [i["candidate_id"] for i in items]
        self.assertIn(self.emp1_id, ids)
        self.assertNotIn(self.emp2_id, ids)

    def test_26_filter_by_min_rating_4(self):
        r = _get_list(self.co_jwt, min_rating=4, limit=50)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        for item in items:
            self.assertGreaterEqual(item.get("rating") or 0, 4)
        ids = [i["candidate_id"] for i in items]
        self.assertIn(self.emp1_id, ids)
        self.assertNotIn(self.emp2_id, ids)

    def test_27_filter_by_tag(self):
        r = _get_list(self.co_jwt, tag="Python", limit=50)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        ids = [i["candidate_id"] for i in items]
        self.assertIn(self.emp1_id, ids)
        self.assertNotIn(self.emp2_id, ids)

    def test_28_filter_by_save_source_manual(self):
        r = _get_list(self.co_jwt, save_source_filter="manual", limit=50)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        for item in items:
            self.assertEqual(item.get("save_source"), "manual")

    def test_29_invalid_priority_filter_400(self):
        r = _get_list(self.co_jwt, priority="extreme")
        self.assertEqual(r.status_code, 400)

    def test_30_invalid_min_rating_filter_400(self):
        r = _get_list(self.co_jwt, min_rating=6)
        self.assertEqual(r.status_code, 400)

    def test_31_invalid_save_source_filter_400(self):
        r = _get_list(self.co_jwt, save_source_filter="unknown_source")
        self.assertEqual(r.status_code, 400)


# ── Group 7: New sort options ────────────────────────────────────────────────

class TestNewSortOptions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        suffix = _rand()
        co  = _register(f"شركة {suffix}", f"co_{suffix}@ex.com", "pass123", "co")
        e1  = _register(f"موظف1 {suffix}", f"emp1_{suffix}@ex.com", "pass123", "emp")
        e2  = _register(f"موظف2 {suffix}", f"emp2_{suffix}@ex.com", "pass123", "emp")
        cls.co_jwt = _login(f"co_{suffix}@ex.com", "pass123")
        cls.emp1_id = e1.get("id") or 0
        cls.emp2_id = e2.get("id") or 0
        _save(cls.co_jwt, cls.emp1_id)
        _save(cls.co_jwt, cls.emp2_id)
        _patch(cls.co_jwt, cls.emp1_id, {"rating": 5, "priority": "high"})
        _patch(cls.co_jwt, cls.emp2_id, {"rating": 2, "priority": "low"})

    def test_32_sort_rating_desc(self):
        r = _get_list(self.co_jwt, sort="rating_desc", limit=50)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        ratings = [i.get("rating") or 0 for i in items]
        # Ratings should be non-increasing (DESC NULLS LAST means rated items first)
        rated = [rt for rt in ratings if rt]
        for i in range(len(rated) - 1):
            self.assertGreaterEqual(rated[i], rated[i+1])

    def test_33_sort_priority_asc(self):
        r = _get_list(self.co_jwt, sort="priority_asc", limit=50)
        self.assertEqual(r.status_code, 200)
        # Should return 200 without error
        items = r.json().get("items") or []
        self.assertIsInstance(items, list)

    def test_34_invalid_sort_400(self):
        r = _get_list(self.co_jwt, sort="magic_sort")
        self.assertEqual(r.status_code, 400)


# ── Group 8: GET response shape includes new fields ──────────────────────────

class TestGetResponseShape(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def test_35_list_item_has_all_new_fields(self):
        _patch(self.co_jwt, self.emp_id, {
            "rating": 3, "priority": "medium",
            "tags": ["Django"],
            "follow_up_at": "2026-10-01", "follow_up_status": "pending"
        })
        r = _get_list(self.co_jwt, limit=5)
        self.assertEqual(r.status_code, 200)
        items = r.json().get("items") or []
        self.assertTrue(len(items) > 0)
        # Find our candidate
        item = next((i for i in items if i["candidate_id"] == self.emp_id), None)
        self.assertIsNotNone(item, "candidate not found in list")
        self.assertEqual(item["rating"], 3)
        self.assertEqual(item["priority"], "medium")
        self.assertIn("Django", item.get("tags") or [])
        self.assertIn("2026-10-01", item.get("follow_up_at") or "")
        self.assertEqual(item["follow_up_status"], "pending")

    def test_36_patch_response_has_all_new_fields(self):
        r = _patch(self.co_jwt, self.emp_id, {
            "rating": 4, "priority": "high",
            "tags": ["Rust", "Go"],
            "follow_up_at": "2026-11-15", "follow_up_status": "done"
        })
        self.assertEqual(r.status_code, 200)
        item = r.json().get("item") or {}
        self.assertEqual(item.get("rating"), 4)
        self.assertEqual(item.get("priority"), "high")
        self.assertIn("Rust", item.get("tags") or [])
        self.assertIn("2026-11-15", item.get("follow_up_at") or "")
        self.assertEqual(item.get("follow_up_status"), "done")

    def test_37_filters_returned_in_response(self):
        r = _get_list(self.co_jwt, priority="high", min_rating=3, tag="Python",
                      save_source_filter="manual")
        self.assertEqual(r.status_code, 200)
        filters = r.json().get("filters") or {}
        self.assertEqual(filters.get("priority"), "high")
        self.assertEqual(filters.get("min_rating"), 3)
        self.assertEqual(filters.get("tag"), "Python")
        self.assertEqual(filters.get("save_source_filter"), "manual")


# ── Group 9: Backward compatibility ─────────────────────────────────────────

class TestBackwardCompat(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def test_38_old_fields_still_work(self):
        """Existing fields (status, notes, job_id) still work after PR-4."""
        r = _patch(self.co_jwt, self.emp_id, {"status": "shortlisted", "notes": "مرشح جيد"})
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertEqual(item["status"], "shortlisted")
        self.assertEqual(item["notes"], "مرشح جيد")

    def test_39_old_sort_options_still_work(self):
        for sort in ["updated_desc", "updated_asc", "created_desc", "created_asc", "name_asc", "status_asc"]:
            r = _get_list(self.co_jwt, sort=sort)
            self.assertEqual(r.status_code, 200, f"sort={sort} failed")

    def test_40_quota_endpoint_still_works(self):
        r = requests.get(
            f"{BASE_URL}/company/saved-candidates/quota",
            headers={"Authorization": f"Bearer {self.co_jwt}"}
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("used", d)
        self.assertIn("limit", d)
        self.assertGreater(d["limit"], 0)


# ── Group 10: Multi-field update in one PATCH ─────────────────────────────────

class TestMultiFieldPatch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        # Clear all mutable fields before each test for clean state
        _patch(self.co_jwt, self.emp_id, {
            "rating": None, "priority": None, "tags": None,
            "follow_up_at": None, "follow_up_status": None,
            "notes": None, "status": "saved"
        })

    def test_41_all_new_fields_in_single_patch(self):
        payload = {
            "rating": 5,
            "priority": "high",
            "tags": ["Leadership", "Management"],
            "follow_up_at": "2026-12-31",
            "follow_up_status": "pending",
            "notes": "مدير محتمل",
            "status": "shortlisted"
        }
        r = _patch(self.co_jwt, self.emp_id, payload)
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertEqual(item["rating"], 5)
        self.assertEqual(item["priority"], "high")
        self.assertIn("Leadership", item.get("tags") or [])
        self.assertIn("2026-12-31", item.get("follow_up_at") or "")
        self.assertEqual(item["follow_up_status"], "pending")
        self.assertEqual(item["notes"], "مدير محتمل")
        self.assertEqual(item["status"], "shortlisted")

    def test_42_partial_patch_only_updates_sent_fields(self):
        """Only sent fields change; unsent fields remain as they were."""
        # First set all fields
        _patch(self.co_jwt, self.emp_id, {
            "rating": 3, "priority": "medium",
            "tags": ["Python"], "status": "saved"
        })
        # Now only update rating
        r = _patch(self.co_jwt, self.emp_id, {"rating": 5})
        self.assertEqual(r.status_code, 200)
        item = r.json()["item"]
        self.assertEqual(item["rating"], 5)
        # Other fields should be unchanged
        self.assertEqual(item["priority"], "medium")
        self.assertIn("Python", item.get("tags") or [])
        self.assertEqual(item["status"], "saved")

    def test_43_empty_patch_body_400(self):
        r = _patch(self.co_jwt, self.emp_id, {})
        self.assertEqual(r.status_code, 400, "empty patch body should return 400")


# ── Group 11: Security — company_id from JWT only ────────────────────────────

class TestSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Company A saves an employee; Company B has no access."""
        suffix = _rand()
        co_a = _register(f"شركة A {suffix}", f"co_a_{suffix}@ex.com", "pass123", "co")
        co_b = _register(f"شركة B {suffix}", f"co_b_{suffix}@ex.com", "pass123", "co")
        emp  = _register(f"موظف {suffix}", f"emp_{suffix}@ex.com", "pass123", "emp")
        cls.jwt_a = _login(f"co_a_{suffix}@ex.com", "pass123")
        cls.jwt_b = _login(f"co_b_{suffix}@ex.com", "pass123")
        cls.emp_id = emp.get("id") or 0
        # Only Company A saves the employee
        _save(cls.jwt_a, cls.emp_id)

    def test_44_cannot_patch_other_company_candidate(self):
        """Company A cannot PATCH a candidate saved by Company B."""
        # Company B tries to patch Company A's saved candidate — should get 404
        r = _patch(self.jwt_b, self.emp_id, {"rating": 5})
        self.assertIn(r.status_code, [403, 404], "should not allow cross-company patch")

    def test_45_unauth_patch_401(self):
        r = requests.patch(
            f"{BASE_URL}/company/saved-candidates/{self.emp_id}",
            json={"rating": 3},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(r.status_code, 401)


# ── Group 12: Panel isolation — PATCH touches only company_saved_candidates ──

def _db_count(table, where_clause, **params):
    """Count rows via direct pg8000 connection."""
    import pg8000.native as _pg
    from urllib.parse import urlparse
    p = urlparse(DB_URL)
    conn = _pg.Connection(
        user=p.username, password=p.password,
        host=p.hostname, port=(p.port or 5432),
        database=p.path.lstrip('/')
    )
    try:
        rows = conn.run(
            f"SELECT COUNT(*) FROM {table} WHERE {where_clause}",
            **params
        )
        return rows[0][0]
    finally:
        conn.close()


class TestPanelIsolation(unittest.TestCase):
    """
    PR-4 manage panel PATCH touches ONLY company_saved_candidates.
    No side-effects on job_applications, company_candidate_job_refs,
    job_pipeline_entries, or pipeline_stage_events.
    No fake job link is created in company_candidate_job_refs.
    """

    @classmethod
    def setUpClass(cls):
        cls.co_jwt, cls.emp_id, cls.emp_tw = _make_company_with_employee()

    def setUp(self):
        _patch(self.co_jwt, self.emp_id, {
            "rating": None, "priority": None, "tags": None,
            "follow_up_at": None, "follow_up_status": None
        })

    def _patch_pr4(self):
        """PATCH with talent fields only — no status, no job_id."""
        return _patch(self.co_jwt, self.emp_id, {
            "rating": 3, "priority": "medium",
            "tags": ["Python"], "notes": "isolation-test",
            "follow_up_at": "2026-10-01", "follow_up_status": "pending"
        })

    def test_46_patch_pr4_status_unchanged(self):
        """PATCH with PR-4 fields: response status == original (status not sent)."""
        # Get original status
        r0 = _get_list(self.co_jwt, limit=50)
        items = r0.json().get("items") or []
        orig = next((i for i in items if i["candidate_id"] == self.emp_id), None)
        orig_status = (orig or {}).get("status", "saved")

        r = self._patch_pr4()
        self.assertEqual(r.status_code, 200)
        # Status returned equals original (we never sent status in payload)
        self.assertEqual(r.json()["item"]["status"], orig_status,
                         "PATCH with PR-4 fields must not change status")

    def test_47_patch_pr4_job_links_empty(self):
        """PATCH with PR-4 fields: job_links remains [] (no fake job link)."""
        r = self._patch_pr4()
        self.assertEqual(r.status_code, 200)

        r2 = _get_list(self.co_jwt, limit=50)
        items = r2.json().get("items") or []
        item = next((i for i in items if i["candidate_id"] == self.emp_id), None)
        self.assertIsNotNone(item, "candidate not found in list")
        self.assertEqual(item.get("job_links", []), [],
                         "PATCH with PR-4 fields must not create a company_candidate_job_refs row")

    def test_48_no_new_ccjr_row_after_patch(self):
        """Direct DB: company_candidate_job_refs count unchanged after PR-4 PATCH."""
        before = _db_count(
            "company_candidate_job_refs",
            "candidate_id = :cid",
            cid=self.emp_id
        )
        r = self._patch_pr4()
        self.assertEqual(r.status_code, 200)
        after = _db_count(
            "company_candidate_job_refs",
            "candidate_id = :cid",
            cid=self.emp_id
        )
        self.assertEqual(before, after,
                         "PATCH must not insert into company_candidate_job_refs")

    def test_49_no_new_pipeline_entry_after_patch(self):
        """Direct DB: job_pipeline_entries count unchanged after PR-4 PATCH."""
        before = _db_count(
            "job_pipeline_entries",
            "candidate_id = :cid",
            cid=self.emp_id
        )
        r = self._patch_pr4()
        self.assertEqual(r.status_code, 200)
        after = _db_count(
            "job_pipeline_entries",
            "candidate_id = :cid",
            cid=self.emp_id
        )
        self.assertEqual(before, after,
                         "PATCH must not insert into job_pipeline_entries")

    def test_50_no_new_pipeline_event_after_patch(self):
        """Direct DB: pipeline_stage_events count unchanged after PR-4 PATCH."""
        # pipeline_stage_events has no candidate_id; join through job_pipeline_entries
        before = _db_count(
            "pipeline_stage_events pse "
            "JOIN job_pipeline_entries jpe ON jpe.id = pse.pipeline_entry_id",
            "jpe.candidate_id = :cid",
            cid=self.emp_id
        )
        r = self._patch_pr4()
        self.assertEqual(r.status_code, 200)
        after = _db_count(
            "pipeline_stage_events pse "
            "JOIN job_pipeline_entries jpe ON jpe.id = pse.pipeline_entry_id",
            "jpe.candidate_id = :cid",
            cid=self.emp_id
        )
        self.assertEqual(before, after,
                         "PATCH must not insert into pipeline_stage_events")

    def test_51_payload_without_status_and_job_id_accepted(self):
        """Server accepts payload with no status/job_id — returns 200."""
        r = requests.patch(
            f"{BASE_URL}/company/saved-candidates/{self.emp_id}",
            json={"rating": 4, "tags": ["Go"]},
            headers={"Authorization": f"Bearer {self.co_jwt}",
                     "Content-Type": "application/json"}
        )
        self.assertEqual(r.status_code, 200)
        item = r.json().get("item") or {}
        self.assertNotIn("status_changed", item,
                         "PATCH without status must not modify status")
        # Confirm status is still a valid pipeline status (not null, not garbage)
        self.assertIn(item.get("status", "saved"),
                      ["saved", "shortlisted", "contacted", "interview", "hired", "rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
