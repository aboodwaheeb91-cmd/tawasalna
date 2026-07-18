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

ROOT = Path(__file__).parent
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

    def test_hmac_compare_digest_used_in_check_admin(self):
        # Extract check_admin function body
        m = re.search(
            r"def check_admin\(request.*?\n(?:.*\n)*?(?=\ndef |\n@app\.)",
            SERVER_SRC
        )
        self.assertIsNotNone(m, "check_admin function not found")
        self.assertIn("hmac.compare_digest", m.group(),
            "check_admin must use hmac.compare_digest")

    def test_hmac_compare_digest_used_in_jwt_decode(self):
        m = re.search(
            r"def _jwt_decode\(.*?\n(?:.*\n)*?(?=\ndef |\n@app\.)",
            SERVER_SRC
        )
        self.assertIsNotNone(m, "_jwt_decode function not found")
        self.assertIn("hmac.compare_digest", m.group(),
            "_jwt_decode must use hmac.compare_digest")

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

    def test_check_admin_raises_503_when_token_not_set(self):
        """503 when ADMIN_TOKEN is empty — fail closed."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = ""
            with self.assertRaises(Exception) as ctx:
                srv.check_admin(self._make_request("anything"))
            exc = ctx.exception
            # FastAPI HTTPException has status_code attribute
            self.assertEqual(exc.status_code, 503)
        finally:
            srv.ADMIN_TOKEN = original

    def test_check_admin_raises_503_when_token_too_short(self):
        """503 when ADMIN_TOKEN is shorter than 32 chars."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "short"
            with self.assertRaises(Exception) as ctx:
                srv.check_admin(self._make_request("short"))
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            srv.ADMIN_TOKEN = original

    def test_check_admin_raises_403_on_wrong_token(self):
        """403 when ADMIN_TOKEN is set but header value is wrong."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "a" * 64
            with self.assertRaises(Exception) as ctx:
                srv.check_admin(self._make_request("wrong_token"))
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            srv.ADMIN_TOKEN = original

    def test_check_admin_passes_with_correct_token(self):
        """No exception when correct token is provided."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "b" * 64
            # Should not raise
            result = srv.check_admin(self._make_request("b" * 64))
            self.assertIsNone(result)
        finally:
            srv.ADMIN_TOKEN = original

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
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "c" * 64
            data = MagicMock()
            data.password = "wrong"
            with self.assertRaises(Exception) as ctx:
                srv.admin_login(data)
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            srv.ADMIN_TOKEN = original

    def test_admin_login_succeeds_with_correct_admin_token(self):
        """admin_login returns success when password == ADMIN_TOKEN."""
        import server as srv
        original = srv.ADMIN_TOKEN
        try:
            srv.ADMIN_TOKEN = "d" * 64
            data = MagicMock()
            data.password = "d" * 64
            result = srv.admin_login(data)
            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("token"), "d" * 64)
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
