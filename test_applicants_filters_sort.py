"""
PR-2: Applicants Filters + Sorting + Match Score Foundation — static source-level tests.

Verifies auth.py and server.py contain the correct patterns for:
- server-side filters (city, country, applied_after, applied_before, q)
- sort whitelist and ORDER BY injection guard
- total semantics (filtered) vs tab counters (unfiltered)
- match_score null placeholder until schema activation
- backward compat: legacy response unchanged

All tests run without a live DB or running server.
"""
import re
import unittest
from pathlib import Path

ROOT       = Path(__file__).parent
AUTH_SRC   = (ROOT / "auth.py").read_text()
SERVER_SRC = (ROOT / "server.py").read_text()


# ── 1. Sort map and whitelist ────────────────────────────────────────────────

class TestSortWhitelist(unittest.TestCase):
    """_APPLICANT_SORT_MAP must exist and contain the four approved values."""

    def test_sort_map_exists(self):
        self.assertIn("_APPLICANT_SORT_MAP", AUTH_SRC,
            "_APPLICANT_SORT_MAP must be defined in auth.py")

    def test_applied_desc_in_sort_map(self):
        self.assertIn('"applied_desc"', AUTH_SRC,
            "applied_desc must be a key in _APPLICANT_SORT_MAP")

    def test_applied_asc_in_sort_map(self):
        self.assertIn('"applied_asc"', AUTH_SRC,
            "applied_asc must be a key in _APPLICANT_SORT_MAP")

    def test_match_desc_in_sort_map(self):
        self.assertIn('"match_desc"', AUTH_SRC,
            "match_desc must be a key in _APPLICANT_SORT_MAP (reserved placeholder)")

    def test_match_asc_in_sort_map(self):
        self.assertIn('"match_asc"', AUTH_SRC,
            "match_asc must be a key in _APPLICANT_SORT_MAP (reserved placeholder)")

    def test_sort_not_injected_raw(self):
        # ORDER BY must use the mapped value, not the raw user-supplied sort param
        # The map lookup pattern must appear: _APPLICANT_SORT_MAP.get(sort, ...)
        self.assertIn("_APPLICANT_SORT_MAP.get(sort", AUTH_SRC,
            "ORDER BY value must come from _APPLICANT_SORT_MAP.get(), never from raw 'sort'")

    def test_order_sql_used_in_query(self):
        self.assertIn("order_sql", AUTH_SRC,
            "The resolved order_sql variable must exist in get_job_applicants")

    def test_sort_map_imported_in_server(self):
        self.assertIn("_APPLICANT_SORT_MAP", SERVER_SRC,
            "_APPLICANT_SORT_MAP must be imported in server.py for endpoint validation")

    def test_server_validates_sort(self):
        self.assertIn("sort not in _APPLICANT_SORT_MAP", SERVER_SRC,
            "Endpoint must validate sort against _APPLICANT_SORT_MAP and return 400 for unknown")

    def test_applied_desc_maps_to_applied_at(self):
        m = re.search(r'"applied_desc":\s*"(.*?)"', AUTH_SRC)
        self.assertIsNotNone(m, "applied_desc key not found in _APPLICANT_SORT_MAP dict")
        self.assertIn("ja.applied_at", m.group(1),
            "applied_desc must map to ja.applied_at ... ORDER")

    def test_applied_asc_maps_to_applied_at_asc(self):
        m = re.search(r'"applied_asc":\s*"(.*?)"', AUTH_SRC)
        self.assertIsNotNone(m, "applied_asc key not found in _APPLICANT_SORT_MAP dict")
        self.assertIn("ASC", m.group(1),
            "applied_asc must include ASC in the ORDER BY value")


# ── 2. New function signature ────────────────────────────────────────────────

class TestFunctionSignature(unittest.TestCase):
    """get_job_applicants must accept all new filter and sort params."""

    def _fn_head(self):
        m = re.search(r"def get_job_applicants\([^)]*\)", AUTH_SRC, re.DOTALL)
        self.assertIsNotNone(m, "get_job_applicants function not found")
        return m.group(0)

    def test_sort_param(self):
        self.assertIn("sort:", self._fn_head(),
            "get_job_applicants must accept 'sort' parameter")

    def test_city_param(self):
        self.assertIn("city:", self._fn_head(),
            "get_job_applicants must accept 'city' parameter")

    def test_country_param(self):
        self.assertIn("country:", self._fn_head(),
            "get_job_applicants must accept 'country' parameter")

    def test_applied_after_param(self):
        self.assertIn("applied_after:", self._fn_head(),
            "get_job_applicants must accept 'applied_after' parameter")

    def test_applied_before_param(self):
        self.assertIn("applied_before:", self._fn_head(),
            "get_job_applicants must accept 'applied_before' parameter")

    def test_q_param(self):
        self.assertIn("q:", self._fn_head(),
            "get_job_applicants must accept 'q' (search) parameter")


# ── 3. Parameterized filter clauses ─────────────────────────────────────────

class TestFilterClauses(unittest.TestCase):
    """All filters must use parameterized SQL — no string interpolation of user values."""

    def _fn_body(self):
        m = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "get_job_applicants body not found")
        return m.group(0)

    def test_city_filter_parameterized(self):
        body = self._fn_body()
        self.assertIn(":f_city", body,
            "city filter must use named param :f_city (not string interpolation)")
        self.assertIn("p.city", body,
            "city filter must compare against p.city column")

    def test_country_filter_parameterized(self):
        body = self._fn_body()
        self.assertIn(":f_country", body,
            "country filter must use named param :f_country")
        self.assertIn("p.country", body,
            "country filter must compare against p.country column")

    def test_applied_after_parameterized(self):
        body = self._fn_body()
        self.assertIn(":f_after", body,
            "applied_after filter must use named param :f_after")
        self.assertIn("ja.applied_at", body,
            "applied_after filter must compare against ja.applied_at")

    def test_applied_before_parameterized(self):
        body = self._fn_body()
        self.assertIn(":f_before", body,
            "applied_before filter must use named param :f_before")

    def test_q_filter_uses_ilike(self):
        body = self._fn_body()
        self.assertIn("ILIKE :f_q", body,
            "q search must use parameterized ILIKE :f_q (no string interpolation)")
        self.assertIn("u.full_name", body,
            "q search must include u.full_name")
        self.assertIn("p.headline", body,
            "q search must include p.headline")

    def test_q_wraps_in_percent(self):
        body = self._fn_body()
        # Percent wrapping should appear: "%" + q.strip() + "%" pattern
        self.assertIn('"%"', body,
            "q param must be wrapped in % for substring ILIKE search")

    def test_filters_combined_with_and(self):
        body = self._fn_body()
        self.assertIn("extra_parts", body,
            "extra filter parts must be accumulated in extra_parts list")
        self.assertIn('" AND ".join(extra_parts)', body,
            "extra filter parts must be joined with AND")

    def test_extra_clause_appended_to_from_where(self):
        body = self._fn_body()
        self.assertIn("extra_clause", body,
            "extra_clause must be defined and used in the query")
        self.assertIn("_FROM_WHERE + extra_clause", body,
            "extra_clause must be appended after _FROM_WHERE")

    def test_view_filter_unchanged(self):
        body = self._fn_body()
        self.assertIn("view_filter", body,
            "view_filter (promoted_at membership) must still exist")
        self.assertIn("jpe.promoted_at IS NULL", body,
            "applicants view filter must still use promoted_at IS NULL")
        self.assertIn("jpe.promoted_at IS NOT NULL", body,
            "candidates view filter must still use promoted_at IS NOT NULL")

    def test_profiles_in_select(self):
        body = self._fn_body()
        self.assertIn("p.city", body,
            "p.city must be added to SELECT for filter + response")
        self.assertIn("p.country", body,
            "p.country must be added to SELECT for filter + response")
        self.assertIn("p.headline", body,
            "p.headline must be added to SELECT for q search + response")


# ── 4. total semantics — filtered vs unfiltered ──────────────────────────────

class TestTotalSemantics(unittest.TestCase):
    """total reflects filtered count; tab counters remain job-wide (unfiltered)."""

    def _fn_body(self):
        m = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "get_job_applicants body not found")
        return m.group(0)

    def test_separate_filtered_count_when_extra_filters(self):
        body = self._fn_body()
        self.assertIn("has_extra", body,
            "has_extra flag must distinguish filtered vs unfiltered pagination")

    def test_membership_aggregate_has_no_extra_clause(self):
        body = self._fn_body()
        # The aggregate query (for tab counters) must NOT include extra_clause
        agg_start = body.find("Membership aggregate")
        agg_end   = body.find("total_all", agg_start) + 50
        agg_block = body[agg_start:agg_end]
        self.assertNotIn("extra_clause", agg_block,
            "Membership aggregate must NOT include extra_clause (tab counters are unfiltered)")

    def test_total_uses_filtered_count_when_has_extra(self):
        body = self._fn_body()
        self.assertIn("if has_extra:", body,
            "When has_extra is true, a separate filtered COUNT query must run")

    def test_total_derives_from_aggregate_when_no_extra(self):
        body = self._fn_body()
        # The else branch (no extra filters) must derive total from the aggregate
        self.assertIn("else:", body,
            "When no extra filters, total must be derived from the aggregate result")
        self.assertIn("total_applicants if view == \"applicants\"", body,
            "No-extra-filter path must derive total from total_applicants or total_candidates")

    def test_total_applicants_not_changed_by_filters(self):
        body = self._fn_body()
        # total_applicants comes from the aggregate query (always unfiltered)
        self.assertIn('"total_applicants"', body,
            "total_applicants must be in the return dict")
        self.assertIn("total_applicants if view", body,
            "total_applicants is used in total derivation — must exist before the if has_extra branch")


# ── 5. Response contract ──────────────────────────────────────────────────────

class TestResponseContract(unittest.TestCase):
    """Response must include sort and filters echo when view is specified."""

    def _fn_body(self):
        m = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "get_job_applicants body not found")
        return m.group(0)

    def test_sort_in_response(self):
        body = self._fn_body()
        self.assertIn('"sort"', body,
            "Response dict must include 'sort' key (effective sort echo)")

    def test_filters_in_response(self):
        body = self._fn_body()
        self.assertIn('"filters"', body,
            "Response dict must include 'filters' key (filter echo)")

    def test_filters_echo_city(self):
        body = self._fn_body()
        self.assertIn('"city"', body,
            "filters echo must include 'city' field")

    def test_filters_echo_country(self):
        body = self._fn_body()
        self.assertIn('"country"', body,
            "filters echo must include 'country' field")

    def test_filters_echo_applied_after(self):
        body = self._fn_body()
        self.assertIn('"applied_after"', body,
            "filters echo must include 'applied_after' field")

    def test_filters_echo_applied_before(self):
        body = self._fn_body()
        self.assertIn('"applied_before"', body,
            "filters echo must include 'applied_before' field")

    def test_filters_echo_min_match_reserved(self):
        body = self._fn_body()
        self.assertIn('"min_match"', body,
            "filters echo must include 'min_match' field (reserved null placeholder)")

    def test_match_score_null_in_items(self):
        body = self._fn_body()
        self.assertIn("'match_score'", body,
            "match_score must be set on each applicant item")
        self.assertIn("a['match_score']      = None", body,
            "match_score must be null (None) until schema is activated")

    def test_legacy_response_unchanged(self):
        # server.py legacy path must still return {applicants, count}
        m = re.search(
            r'@app\.get\("/jobs/\{job_id\}/applicants"\)(.*?)(?=\n@app\.|\Z)',
            SERVER_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "GET /jobs/{job_id}/applicants endpoint not found")
        body = m.group(1)
        self.assertIn('"count"', body,
            "Legacy response (no view) must still use 'count' key")
        self.assertIn("if not view:", body,
            "Legacy branch must check 'if not view:'")


# ── 6. Server endpoint params and validation ─────────────────────────────────

class TestServerEndpoint(unittest.TestCase):
    """Endpoint must declare and validate all new params."""

    def _endpoint_body(self):
        m = re.search(
            r'@app\.get\("/jobs/\{job_id\}/applicants"\)(.*?)(?=\n@app\.|\Z)',
            SERVER_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "GET /jobs/{job_id}/applicants endpoint not found")
        return m.group(1)

    def test_sort_param_declared(self):
        self.assertIn("sort:", self._endpoint_body(),
            "Endpoint must declare sort param")

    def test_city_param_declared(self):
        self.assertIn("city:", self._endpoint_body(),
            "Endpoint must declare city param")

    def test_country_param_declared(self):
        self.assertIn("country:", self._endpoint_body(),
            "Endpoint must declare country param")

    def test_applied_after_param_declared(self):
        self.assertIn("applied_after:", self._endpoint_body(),
            "Endpoint must declare applied_after param")

    def test_applied_before_param_declared(self):
        self.assertIn("applied_before:", self._endpoint_body(),
            "Endpoint must declare applied_before param")

    def test_q_param_declared(self):
        self.assertIn("q:", self._endpoint_body(),
            "Endpoint must declare q (search) param")

    def test_min_match_param_declared(self):
        self.assertIn("min_match:", self._endpoint_body(),
            "Endpoint must declare min_match param (reserved)")

    def test_date_format_validation(self):
        body = self._endpoint_body()
        self.assertIn("YYYY-MM-DD", body,
            "Endpoint must validate date format and mention YYYY-MM-DD in error message")

    def test_min_match_range_validation(self):
        body = self._endpoint_body()
        self.assertIn("min_match", body,
            "min_match must be validated in endpoint")
        self.assertIn("0 <= parsed_min_match <= 100", body,
            "min_match must be constrained to 0-100")

    def test_sort_400_for_invalid(self):
        body = self._endpoint_body()
        self.assertIn("sort not in _APPLICANT_SORT_MAP", body,
            "Endpoint must return 400 for sort values not in whitelist")

    def test_page_min_1_validated(self):
        body = self._endpoint_body()
        self.assertIn("page < 1", body,
            "Endpoint must validate page >= 1")

    def test_ownership_check_preserved(self):
        body = self._endpoint_body()
        self.assertIn("JOB_OWNERSHIP_FAILED", body,
            "Ownership check must still be present")
        self.assertIn("job_company_id", body,
            "company_id must come from DB lookup, never from frontend")

    def test_new_params_passed_to_auth(self):
        body = self._endpoint_body()
        self.assertIn("sort=sort", body,
            "sort must be passed to get_job_applicants")
        self.assertIn("city=city", body,
            "city must be passed to get_job_applicants")
        self.assertIn("country=country", body,
            "country must be passed to get_job_applicants")
        self.assertIn("applied_after=applied_after", body,
            "applied_after must be passed to get_job_applicants")
        self.assertIn("q=q", body,
            "q must be passed to get_job_applicants")

    def test_limit_max_100_preserved(self):
        # Limit clamping still done in auth.py
        auth_fn = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(auth_fn, "get_job_applicants not found")
        self.assertIn("min(max(1, limit), 100)", auth_fn.group(0),
            "limit must still be clamped to 100 in auth.py")


# ── 7. No N+1 query pattern ──────────────────────────────────────────────────

class TestQueryEfficiency(unittest.TestCase):
    """The main paginated SELECT + filtered COUNT must not produce N+1 patterns."""

    def _fn_body(self):
        m = re.search(
            r"def get_job_applicants\(.*?\n    finally:\n        release_conn\(conn\)",
            AUTH_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "get_job_applicants body not found")
        return m.group(0)

    def test_appointment_batch_fetch_not_n_plus_1(self):
        body = self._fn_body()
        # Appointments are batch-fetched using IN clause (DISTINCT ON pattern)
        self.assertIn("DISTINCT ON", body,
            "Next appointments must use DISTINCT ON batch fetch, not per-row query")
        self.assertIn("IN ({id_clause})", body,
            "Appointments batch query must use IN clause, not per-row fetch")

    def test_single_aggregate_query_for_counters(self):
        body = self._fn_body()
        # COUNT(*) FILTER — both filters in one query
        filter_count = body.count("COUNT(*) FILTER (WHERE")
        self.assertGreaterEqual(filter_count, 2,
            "Both applicants and candidates counts must use FILTER aggregate in one query")

    def test_no_python_level_score_computation(self):
        body = self._fn_body()
        # There must be no loop computing scores per row in Python
        self.assertNotIn("for a in items:\n            a['match_score'] = int(",
            body,
            "match_score must NOT be computed per-item in a Python loop (N+1 risk)")

    def test_no_duplicate_rows_from_joins(self):
        body = self._fn_body()
        # All JOINs are 1:0-1 — verify pipeline_entries join is on application_id (1:1)
        self.assertIn("jpe.application_id=ja.id", body,
            "pipeline_entries join must be on application_id (1:0-1 relationship, no duplicates)")


# ── 8. Security ──────────────────────────────────────────────────────────────

class TestSecurity(unittest.TestCase):

    def _endpoint_body(self):
        m = re.search(
            r'@app\.get\("/jobs/\{job_id\}/applicants"\)(.*?)(?=\n@app\.|\Z)',
            SERVER_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "endpoint not found")
        return m.group(1)

    def test_jwt_required(self):
        body = self._endpoint_body()
        self.assertIn("verify_token", body,
            "Endpoint must require JWT via Depends(verify_token)")

    def test_company_id_from_db_not_frontend(self):
        body = self._endpoint_body()
        # company_id must come from DB lookup of jobs table, not from query param
        self.assertIn("SELECT company_id FROM jobs", body,
            "company_id must be fetched from DB, never accepted from frontend")
        self.assertNotIn("company_id:", body.split("def job_applicants")[0],
            "company_id must not be a query param in the endpoint signature")

    def test_security_log_on_ownership_fail(self):
        body = self._endpoint_body()
        self.assertIn("JOB_OWNERSHIP_FAILED", body,
            "Security log must be emitted on ownership check failure")

    def test_no_company_id_param_in_signature(self):
        sig_match = re.search(r"def job_applicants\([^)]*\)", body := self._endpoint_body(), re.DOTALL)
        if sig_match:
            self.assertNotIn("company_id", sig_match.group(0),
                "company_id must NOT be an accepted query param in the endpoint")


if __name__ == "__main__":
    unittest.main(verbosity=2)
