"""
Security P0 — Admin Token & JWT Secret tests
Static (source-level) + behavioral (mock-level) checks.
"""
import re
import os
import hmac
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
SERVER_SRC = (ROOT / "server.py").read_text()
ARCH_SRC   = (ROOT / "ARCHITECTURE.md").read_text()
CLAUDE_SRC = (ROOT / "CLAUDE.md").read_text()
INDEX_SRC  = (ROOT / "docs" / "SYSTEMS_INDEX.md").read_text()

# ─── Static source checks ─────────────────────────────────────────────────────

class TestNoHardcodedSecrets(unittest.TestCase):

    def test_no_admin_password_string_in_server(self):
        self.assertNotIn("tw@admin", SERVER_SRC,
            "tw@admin2025 must not appear in server.py")

    def test_no_sha256_admin_derivation_in_server(self):
        # Old pattern: hashlib.sha256(ADMIN_PASSWORD...)
        self.assertNotIn("ADMIN_PASSWORD", SERVER_SRC,
            "ADMIN_PASSWORD must not exist in server.py")

    def test_no_hardcoded_url_token_in_server(self):
        self.assertNotIn("kPuOWhpIYjdLQXmh", SERVER_SRC,
            "Hardcoded ADMIN_URL_TOKEN must not appear in server.py")

    def test_no_hashlib_import_in_server(self):
        self.assertNotIn("import hashlib", SERVER_SRC,
            "hashlib is no longer needed and must not be imported")

    def test_admin_token_reads_from_environ(self):
        self.assertIn('os.environ.get("ADMIN_TOKEN"', SERVER_SRC,
            "ADMIN_TOKEN must be read from os.environ")

    def test_jwt_secret_reads_from_environ(self):
        self.assertIn('os.environ.get("JWT_SECRET"', SERVER_SRC,
            "JWT_SECRET must be read from os.environ")

    def test_admin_url_token_reads_from_environ(self):
        self.assertIn('os.environ.get("ADMIN_URL_TOKEN"', SERVER_SRC,
            "ADMIN_URL_TOKEN must be read from os.environ")

    def test_jwt_secret_not_derived_from_admin_token(self):
        # Must not see "JWT_SECRET = ... ADMIN_TOKEN" on same line
        for line in SERVER_SRC.splitlines():
            if "JWT_SECRET" in line and "ADMIN_TOKEN" in line and "=" in line:
                self.fail(f"JWT_SECRET must not be derived from ADMIN_TOKEN: {line!r}")

    # PR 1.5 / 1.8: the signature check lives in ONE place — _jwt_verify — shared by
    # the user JWT (_jwt_decode) and the admin JWT (check_admin → _admin_jwt_claims).
    def _fn_body(self, name):
        m = re.search(
            r"def " + name + r"\(.*?\n(?:.*\n)*?(?=\ndef |\n@app\.)",
            SERVER_SRC
        )
        self.assertIsNotNone(m, name + " function not found")
        return m.group()

    def test_hmac_compare_digest_used_in_jwt_verify(self):
        self.assertIn("hmac.compare_digest", self._fn_body("_jwt_verify"),
            "_jwt_verify must use hmac.compare_digest")

    def test_check_admin_verifies_through_jwt_verify(self):
        self.assertIn("_admin_jwt_claims(", self._fn_body("check_admin"),
            "check_admin must verify the admin JWT via _admin_jwt_claims")
        self.assertIn("_jwt_verify(", self._fn_body("_admin_jwt_claims"),
            "_admin_jwt_claims must verify the signature via _jwt_verify")

    def test_jwt_decode_verifies_through_jwt_verify(self):
        self.assertIn("_jwt_verify(", self._fn_body("_jwt_decode"),
            "_jwt_decode must verify the signature via _jwt_verify")

    def test_no_secrets_in_architecture_docs(self):
        self.assertNotIn("tw@admin", ARCH_SRC,
            "tw@admin2025 must not appear in ARCHITECTURE.md")
        self.assertNotIn("kPuOWhpIYjdLQXmh", ARCH_SRC,
            "Hardcoded URL token must not appear in ARCHITECTURE.md")

    def test_no_secrets_in_claude_md(self):
        self.assertNotIn("tw@admin", CLAUDE_SRC,
            "tw@admin2025 must not appear in CLAUDE.md")
        self.assertNotIn("kPuOWhpIYjdLQXmh", CLAUDE_SRC,
            "Hardcoded URL token must not appear in CLAUDE.md")

    def test_no_secrets_in_systems_index(self):
        self.assertNotIn("tw@admin", INDEX_SRC,
            "tw@admin2025 must not appear in docs/SYSTEMS_INDEX.md")
        self.assertNotIn("kPuOWhpIYjdLQXmh", INDEX_SRC,
            "Hardcoded URL token must not appear in docs/SYSTEMS_INDEX.md")

    def test_startup_blocks_on_missing_jwt_secret(self):
        self.assertIn("JWT_SECRET", SERVER_SRC,
            "Startup must reference JWT_SECRET for validation")
        # Must raise RuntimeError if JWT_SECRET is short
        self.assertIn("RuntimeError", SERVER_SRC,
            "Missing JWT_SECRET must raise RuntimeError at startup")

    def test_check_admin_has_503_guard(self):
        self.assertIn("503", SERVER_SRC,
            "check_admin must return 503 when ADMIN_TOKEN is not configured")


# ─── Behavioral checks ────────────────────────────────────────────────────────

class TestCheckAdminBehavior(unittest.TestCase):
    """
    Behavioral tests for check_admin via direct calls with mocked module state.
    """

    def _make_request(self, token_value: str):
        req = MagicMock()
        req.headers.get = lambda k, d="": token_value if k == "X-Admin-Token" else d
        return req

    # PR 1.5: check_admin accepts ONLY an admin JWT (ADMIN_JWT_SECRET) — the raw
    # ADMIN_TOKEN is the login password, never a session. Full matrix:
    # test_admin_session_security.py.
    def test_check_admin_raises_503_when_admin_jwt_secret_not_set(self):
        """503 when ADMIN_JWT_SECRET is empty — fail closed."""
        import server as srv
        original = srv.ADMIN_JWT_SECRET
        try:
            srv.ADMIN_JWT_SECRET = ""
            with self.assertRaises(Exception) as ctx:
                srv.check_admin(self._make_request("anything"))
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            srv.ADMIN_JWT_SECRET = original

    def test_check_admin_rejects_raw_admin_token(self):
        """401 when the header carries the raw ADMIN_TOKEN instead of an admin JWT."""
        import server as srv
        o_tok, o_sec = srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET
        try:
            srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET = "a" * 64, "s" * 64
            with self.assertRaises(Exception) as ctx:
                srv.check_admin(self._make_request("a" * 64))
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET = o_tok, o_sec

    def test_check_admin_passes_with_admin_jwt(self):
        """Claims returned when a valid admin JWT is provided."""
        import server as srv
        original = srv.ADMIN_JWT_SECRET
        try:
            srv.ADMIN_JWT_SECRET = "s" * 64
            claims = srv.check_admin(self._make_request(srv._admin_jwt_issue()))
            self.assertEqual(claims["role"], "admin")
        finally:
            srv.ADMIN_JWT_SECRET = original

    def test_admin_login_returns_503_when_token_not_set(self):
        """admin_login returns 503 when ADMIN_TOKEN is unconfigured."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = ""
            data = MagicMock()
            data.password = "anything"
            with self.assertRaises(Exception) as ctx:
                srv.admin_login(data)
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            srv.ADMIN_TOKEN = original

    def test_admin_login_returns_401_on_wrong_password(self):
        """admin_login returns 401 when password doesn't match ADMIN_TOKEN."""
        import server as srv
        original, o_sec = srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET
        try:
            # PR 1.5: without a valid ADMIN_JWT_SECRET admin_login is 503 (fail closed)
            srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET = "c" * 64, "s" * 64
            data = MagicMock()
            data.password = "wrong"
            with self.assertRaises(Exception) as ctx:
                srv.admin_login(data)
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            srv.ADMIN_TOKEN, srv.ADMIN_JWT_SECRET = original, o_sec

    def test_admin_login_succeeds_with_correct_admin_token(self):
        """admin_login returns success when password == ADMIN_TOKEN."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "d" * 64
            o_sec = srv.ADMIN_JWT_SECRET
            srv.ADMIN_JWT_SECRET = "s" * 64
            data = MagicMock()
            data.password = "d" * 64
            result = srv.admin_login(data)
            self.assertTrue(result.get("success"))
            # PR 1.5: an admin JWT, never the raw ADMIN_TOKEN
            self.assertNotEqual(result.get("token"), "d" * 64)
            self.assertTrue(srv._admin_jwt_claims(result.get("token")))
            srv.ADMIN_JWT_SECRET = o_sec
        finally:
            srv.ADMIN_TOKEN = original

    def test_jwt_decode_returns_empty_when_jwt_secret_not_set(self):
        """_jwt_decode returns {} when JWT_SECRET is not configured."""
        import server as srv
        original = srv.JWT_SECRET
        try:
            srv.JWT_SECRET = ""
            result = srv._jwt_decode("any.token.value")
            self.assertEqual(result, {})
        finally:
            srv.JWT_SECRET = original

    def test_jwt_encode_raises_when_jwt_secret_not_set(self):
        """_jwt_encode raises RuntimeError when JWT_SECRET is not configured."""
        import server as srv
        original = srv.JWT_SECRET
        try:
            srv.JWT_SECRET = ""
            with self.assertRaises(RuntimeError):
                srv._jwt_encode({"user_id": 1})
        finally:
            srv.JWT_SECRET = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
