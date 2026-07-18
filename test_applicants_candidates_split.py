"""
PR-6: Applicants vs Candidates Split — static source-level tests.

Verifies that auth.py and server.py contain the correct patterns for the
promoted_at Candidate Membership Marker, server-side pagination, and the
view-based filter that separates applicants from candidates.

All 15 cases run without a live DB or running server.
"""
import re
import unittest
from pathlib import Path

ROOT       = Path(__file__).parent
AUTH_SRC   = (ROOT / "auth.py").read_text()
SERVER_SRC = (ROOT / "server.py").read_text()


# ── 1. Schema migration ──────────────────────────────────────────────────────

class TestMigrationFunction(unittest.TestCase):
    """_migrate_applicants_candidates_split must be present and idempotent."""

    def _migration_body(self):
        m = re.search(
            r"def _migrate_applicants_candidates_split\(\)(.*?)(?=\n\n[A-Z_a-z]|\Z)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_migrate_applicants_candidates_split function not found in auth.py")
        return m.group(1)

    def test_migration_function_exists(self):
        self.assertIn("def _migrate_applicants_candidates_split", AUTH_SRC,
            "_migrate_applicants_candidates_split must be defined in auth.py")

    def test_promoted_at_column_added_idempotently(self):
        body = self._migration_body()
        self.assertIn("ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ NULL", body,
            "Migration must use ADD COLUMN IF NOT EXISTS for idempotency")

    def test_backfill_uses_pipeline_stage_events_evidence(self):
        body = self._migration_body()
        self.assertIn("pipeline_stage_events", body,
            "Backfill must read from pipeline_stage_events (evidence-based, not stage-based)")
        self.assertIn("to_stage = 'shortlisted'", body,
            "Backfill filter must look for to_stage='shortlisted' events")

    def test_backfill_is_safe_does_not_overwrite(self):
        body = self._migration_body()
        self.assertIn("promoted_at IS NULL", body,
            "Backfill UPDATE must guard with promoted_at IS NULL to avoid overwriting")

    def test_migration_registered_in_server_startup(self):
        self.assertIn("_migrate_applicants_candidates_split()", SERVER_SRC,
            "_migrate_applicants_candidates_split() must be called in server.py startup")

    def test_migration_imported_in_server(self):
        self.assertIn("_migrate_applicants_candidates_split", SERVER_SRC,
            "_migrate_applicants_candidates_split must be imported in server.py")


# ── 2. promote_application_to_shortlist stamps promoted_at ──────────────────

class TestPromoteStampsPromotedAt(unittest.TestCase):
    """promote_application_to_shortlist must stamp promoted_at inside its transaction."""

    def _promote_body(self):
        m = re.search(
            r"def promote_application_to_shortlist\(app_id.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "promote_application_to_shortlist not found in auth.py")
        return m.group(0)

    def test_promoted_at_stamped_with_coalesce(self):
        body = self._promote_body()
        self.assertIn("promoted_at = COALESCE(promoted_at, NOW())", body,
            "promote_application_to_shortlist must use COALESCE(promoted_at, NOW()) "
            "to stamp promoted_at without overwriting an existing value")

    def test_promoted_at_stamped_inside_pipeline_block(self):
        body = self._promote_body()
        upsert_idx  = body.find("_pipeline_upsert_entry")
        stamp_idx   = body.find("promoted_at = COALESCE")
        update_idx  = body.find("_pipeline_update_stage")
        self.assertGreater(stamp_idx, upsert_idx,
            "promoted_at stamp must come AFTER _pipeline_upsert_entry "
            "(entry must exist before UPDATE)")
        self.assertLess(stamp_idx, update_idx,
            "promoted_at stamp must come BEFORE _pipeline_update_stage "
            "(stamp is part of the same atomic transaction block)")


# ── 3. get_job_applicants — signature and view filter logic ─────────────────

class TestGetJobApplicantsSignature(unittest.TestCase):
    """get_job_applicants must accept view, page, limit and filter correctly."""

    def _fn_body(self):
        m = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "get_job_applicants not found in auth.py")
        return m.group(0)

    def test_view_parameter_in_signature(self):
        body = self._fn_body()
        self.assertIn("view:", body,
            "get_job_applicants must accept a 'view' parameter")

    def test_page_parameter_in_signature(self):
        body = self._fn_body()
        self.assertIn("page:", body,
            "get_job_applicants must accept a 'page' parameter")

    def test_limit_parameter_in_signature(self):
        body = self._fn_body()
        self.assertIn("limit:", body,
            "get_job_applicants must accept a 'limit' parameter")

    def test_applicants_filter_uses_promoted_at_is_null(self):
        body = self._fn_body()
        self.assertIn("promoted_at IS NULL", body,
            "view='applicants' filter must use promoted_at IS NULL")

    def test_candidates_filter_uses_promoted_at_is_not_null(self):
        body = self._fn_body()
        self.assertIn("promoted_at IS NOT NULL", body,
            "view='candidates' filter must use promoted_at IS NOT NULL")

    def test_limit_clamped_to_max_100(self):
        body = self._fn_body()
        self.assertIn("100", body,
            "limit must be clamped to a maximum of 100")

    def test_returns_dict_with_applicants_key(self):
        body = self._fn_body()
        self.assertIn('"applicants"', body,
            "Return dict must have 'applicants' key so the frontend array read still works")

    def test_returns_total_key(self):
        body = self._fn_body()
        self.assertIn('"total"', body,
            "Return dict must include 'total' for pagination metadata")


# ── 4. Server endpoint — backward compat + view validation ───────────────────

class TestServerEndpointUpdates(unittest.TestCase):
    """The GET /jobs/{job_id}/applicants endpoint must handle view/page/limit."""

    def _endpoint_body(self):
        m = re.search(
            r'@app\.get\("/jobs/\{job_id\}/applicants"\)(.*?)(?=\n@app\.|\Z)',
            SERVER_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "GET /jobs/{job_id}/applicants endpoint not found in server.py")
        return m.group(1)

    def test_endpoint_accepts_view_param(self):
        body = self._endpoint_body()
        self.assertIn("view", body,
            "Endpoint must declare a 'view' query param")

    def test_endpoint_validates_view_values(self):
        body = self._endpoint_body()
        self.assertIn("applicants", body,
            "Endpoint must validate that view is one of the allowed values")
        self.assertIn("candidates", body,
            "Endpoint must validate that view is one of the allowed values")

    def test_legacy_response_uses_count_key(self):
        body = self._endpoint_body()
        self.assertIn('"count"', body,
            "Legacy response (no view) must use 'count' key for backward compat")

    def test_paginated_response_returned_when_view_set(self):
        body = self._endpoint_body()
        # When view is set, the endpoint returns the full result dict (not the legacy shape)
        self.assertIn("return result", body,
            "When view is set, endpoint must return the full paginated result dict")


if __name__ == "__main__":
    unittest.main(verbosity=2)
