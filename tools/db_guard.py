"""db_guard.py — refuse a test database that could be a real one (task 5.0e · SYSTEMS_INDEX §54g).

run_tests.sh DROPs and re-CREATEs the test database before every DB test file. It calls this guard
ONCE, before any connection, and stops (exit 2) when the target is not clearly a throwaway test DB:

  - APP_ENV = production                                  → refused
  - the database name does not contain "test"             → refused
  - the host is not localhost / 127.0.0.1 / ::1           → refused, unless TW_TEST_DB_ALLOW_REMOTE=1

Nothing here connects to anything — it only reads the URL and the environment.
Run:  python tools/db_guard.py "<postgresql://user:pass@host:port/db>"   (exit 0 = allowed)
"""
import os
import sys
from urllib.parse import urlparse

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def check(url: str, env=None):
    """None when the URL is safe to drop + re-create; otherwise the reason (str)."""
    env = os.environ if env is None else env
    if (env.get("APP_ENV") or "").strip().lower() == "production":
        return "APP_ENV=production — the test runner never touches a production database"
    try:
        u = urlparse(url or "")
        name = (u.path or "").lstrip("/").split("?")[0]
        host = (u.hostname or "").lower()
    except ValueError:
        return "the database URL cannot be parsed"
    if u.scheme not in ("postgres", "postgresql") or not name:
        return "not a postgresql://…/<database> URL"
    if "test" not in name.lower():
        return f'database name "{name}" does not contain "test"'
    if host not in _LOCAL_HOSTS and (env.get("TW_TEST_DB_ALLOW_REMOTE") or "").strip() != "1":
        return f'host "{host or "-"}" is not localhost / 127.0.0.1 (set TW_TEST_DB_ALLOW_REMOTE=1 to allow it)'
    return None


if __name__ == "__main__":
    reason = check(sys.argv[1] if len(sys.argv) > 1 else "")
    if reason:
        print(f"✗ refusing to DROP / CREATE the test database: {reason}")
        sys.exit(2)
    sys.exit(0)
