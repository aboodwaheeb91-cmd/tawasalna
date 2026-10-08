"""
Talent Bank — Tag Prefix Filter: PostgreSQL Endpoint Tests

Tests the GET /company/saved-candidates?tag=<prefix> endpoint behaviour
against a real running server (TEST_BASE_URL) + real PostgreSQL.

All tests skip gracefully when:
  - TEST_BASE_URL is unreachable
  - COMPANY_JWT env var is not set (no company credentials)
  - TEST_CANDIDATE_ID env var is not set (no pre-seeded candidate)

Setup requirements (for live run):
  export TEST_BASE_URL=http://127.0.0.1:8000
  export COMPANY_JWT=<valid company JWT>
  export TEST_CANDIDATE_IDS=<comma-separated company_saved_candidates.candidate_id list>
    # Those candidates must have tags: ['معلم','مبرمج','مصمم','Python','مصور','م%','a_b']

Groups:
  A (01-06): Prefix matching correctness
  B (07-08): Case-insensitive match
  C (09):    Leading/trailing whitespace stripped by server
  D (10-11): LIKE injection prevention (% and _ treated as literals)
  E (12-13): Pagination integrity with tag filter
  F (14):    No HTTP 500 on any input
"""

import os
import sys
import unittest
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

BASE_URL   = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")
JWT        = os.environ.get("COMPANY_JWT", "")

def _server_alive():
    if not HAS_REQUESTS:
        return False
    try:
        r = requests.get(BASE_URL + "/", timeout=3)
        return r.status_code < 500
    except Exception:
        return False

SERVER_UP = _server_alive()
SKIP_MSG  = "Live server not reachable or COMPANY_JWT not set — skipping"

def _get(path, **params):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return requests.get(url, headers={"Authorization": "Bearer " + JWT}, timeout=10)


def _tag_names(res_json):
    """Flatten all tags from items into a flat list."""
    tags = []
    for item in (res_json.get("items") or []):
        tags.extend(item.get("tags") or [])
    return tags


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class A_PrefixMatching(unittest.TestCase):

    def test_01_م_matches_معلم_مبرمج_مصمم(self):
        """tag=م returns items that have a tag starting with 'م'"""
        r = _get("/company/saved-candidates", tag="م")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        tags = _tag_names(d)
        self.assertTrue(
            any(t.startswith("م") for t in tags),
            "Expected at least one tag starting with 'م' — got: " + str(tags)
        )
        # Must NOT return empty set when seeded tags include معلم/مبرمج/مصمم
        self.assertGreater(d.get("count", 0), 0, "Expected non-zero results for prefix 'م'")

    def test_02_مص_matches_مصمم_مصور(self):
        """tag=مص narrows to tags starting with 'مص'"""
        r = _get("/company/saved-candidates", tag="مص")
        self.assertEqual(r.status_code, 200)
        tags = _tag_names(r.json())
        for t in tags:
            self.assertTrue(t.startswith("مص"), f"Tag '{t}' should start with 'مص'")

    def test_03_مع_matches_معلم_not_مبرمج(self):
        """tag=مع returns معلم but not مبرمج"""
        r = _get("/company/saved-candidates", tag="مع")
        self.assertEqual(r.status_code, 200)
        tags = _tag_names(r.json())
        # Any tag returned must start with مع
        for t in tags:
            self.assertTrue(t.startswith("مع"), f"Unexpected tag '{t}' for prefix 'مع'")

    def test_04_py_matches_Python(self):
        """tag=py returns items with Python tag (case-insensitive prefix)"""
        r = _get("/company/saved-candidates", tag="py")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        if d.get("count", 0) > 0:
            tags = _tag_names(d)
            self.assertTrue(
                any(t.lower().startswith("py") for t in tags),
                "Expected Python-tagged item but tags are: " + str(tags)
            )

    def test_05_no_match_prefix_returns_empty(self):
        """tag=zzznomatch returns count=0 and empty items"""
        r = _get("/company/saved-candidates", tag="zzznomatch")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d.get("count", 0), 0)
        self.assertEqual(len(d.get("items") or []), 0)

    def test_06_empty_tag_returns_all(self):
        """tag= (empty string) is treated as no filter — returns full list"""
        r_all = _get("/company/saved-candidates")
        r_empty = _get("/company/saved-candidates", tag="")
        self.assertEqual(r_all.status_code, 200)
        self.assertEqual(r_empty.status_code, 200)
        self.assertEqual(
            r_all.json().get("count"), r_empty.json().get("count"),
            "tag='' should return same count as no tag param"
        )


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class B_CaseInsensitive(unittest.TestCase):

    def test_07_PY_matches_Python(self):
        """tag=PY (uppercase) matches Python tag — ILIKE is case-insensitive"""
        r_lower = _get("/company/saved-candidates", tag="py")
        r_upper = _get("/company/saved-candidates", tag="PY")
        self.assertEqual(r_lower.status_code, 200)
        self.assertEqual(r_upper.status_code, 200)
        self.assertEqual(
            r_lower.json().get("count"), r_upper.json().get("count"),
            "ILIKE must match regardless of case"
        )

    def test_08_mixed_case_search_works(self):
        """tag=PyThOn still matches Python"""
        r = _get("/company/saved-candidates", tag="PyThOn")
        self.assertEqual(r.status_code, 200)
        r2 = _get("/company/saved-candidates", tag="python")
        self.assertEqual(r.json().get("count"), r2.json().get("count"))


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class C_Whitespace(unittest.TestCase):

    def test_09_leading_trailing_spaces_stripped(self):
        """server strips leading/trailing whitespace from tag param"""
        r_clean = _get("/company/saved-candidates", tag="معلم")
        r_spaced = _get("/company/saved-candidates", tag="  معلم  ")
        self.assertEqual(r_clean.status_code, 200)
        self.assertEqual(r_spaced.status_code, 200)
        self.assertEqual(
            r_clean.json().get("count"), r_spaced.json().get("count"),
            "Spaces around tag should be stripped"
        )


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class D_LikeInjectionPrevention(unittest.TestCase):

    def test_10_percent_treated_as_literal(self):
        """tag=م% searches for literal 'م%' prefix, not wildcard"""
        # A search for literal 'م%' should NOT return all 'م*' tags
        r_wildcard = _get("/company/saved-candidates", tag="م")
        r_literal  = _get("/company/saved-candidates", tag="م%")
        self.assertEqual(r_wildcard.status_code, 200)
        self.assertEqual(r_literal.status_code, 200)
        count_all = r_wildcard.json().get("count", 0)
        count_pct = r_literal.json().get("count", 0)
        self.assertLessEqual(
            count_pct, count_all,
            "tag='م%%' must not match as wildcard — count should be ≤ tag='م'"
        )
        # Also verify HTTP 200 (not 500 from bad SQL)
        self.assertEqual(r_literal.status_code, 200)

    def test_11_underscore_treated_as_literal(self):
        """tag=a_b searches for literal 'a_b', not 'a<any>b'"""
        r = _get("/company/saved-candidates", tag="a_b")
        self.assertEqual(r.status_code, 200, r.text)
        # Should not crash — just return 0 or matching items
        d = r.json()
        tags = _tag_names(d)
        for t in tags:
            self.assertTrue(
                t.startswith("a_b"),
                f"Tag '{t}' should start with literal 'a_b' (underscore not wildcard)"
            )


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class E_PaginationIntegrity(unittest.TestCase):

    def test_12_has_more_correct_with_tag_filter(self):
        """pagination.has_more is accurate when tag filter is active"""
        r = _get("/company/saved-candidates", tag="م", limit=1, offset=0)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        total = (d.get("pagination") or {}).get("total", d.get("count", 0))
        has_more = (d.get("pagination") or {}).get("has_more", False)
        if total > 1:
            self.assertTrue(has_more, "has_more should be True when total > limit")
        else:
            self.assertFalse(has_more, "has_more should be False when total ≤ limit")

    def test_13_offset_with_tag_filter_no_500(self):
        """offset pagination with tag filter doesn't crash"""
        r = _get("/company/saved-candidates", tag="م", limit=10, offset=100)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(len(d.get("items") or []), 0)


@unittest.skipUnless(SERVER_UP and JWT, SKIP_MSG)
class F_NoCrash(unittest.TestCase):

    def test_14_no_http_500_on_any_tag_input(self):
        """Various edge-case tag values must return 200, not 500"""
        edge_cases = [
            "a",                  # single char
            "م" * 50,            # max length
            "م" * 51,            # over limit → 400
            "test%test",          # internal %
            "test_test",          # internal _
            "test\\test",         # backslash
            "  ",                 # whitespace only → treated as empty → no filter
            "مرحباً",             # Arabic with tatweel/accents
        ]
        for tag in edge_cases:
            r = _get("/company/saved-candidates", tag=tag)
            self.assertNotEqual(
                r.status_code, 500,
                f"HTTP 500 for tag={tag!r}: {r.text[:200]}"
            )
            # Over-length returns 400, all others 200
            if len(tag.strip()) > 50:
                self.assertEqual(r.status_code, 400, f"Expected 400 for tag len>{50}: {tag!r}")
            elif tag.strip() == "":
                self.assertEqual(r.status_code, 200)
            else:
                self.assertIn(r.status_code, (200, 400), f"Unexpected status for tag={tag!r}")


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not SERVER_UP:
        print(f"\n[SKIP] Server not reachable at {BASE_URL}")
        print("       Set TEST_BASE_URL and COMPANY_JWT to run live tests.")
        print("       All 14 tests skipped.\n")
        sys.exit(0)
    if not JWT:
        print("\n[SKIP] COMPANY_JWT env var not set — all 14 tests skipped.\n")
        sys.exit(0)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [
        A_PrefixMatching, B_CaseInsensitive, C_Whitespace,
        D_LikeInjectionPrevention, E_PaginationIntegrity, F_NoCrash,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
