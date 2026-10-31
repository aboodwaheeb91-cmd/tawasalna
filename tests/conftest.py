"""No silent skip for the admin security tests (task 8.4c-0 · docs/rules/admin-staff.md).

With TW_SECURITY_TESTS_REQUIRED=1 (CI — .github/workflows/tests.yml) a skipped test in SECURITY_TESTS
(e.g. TW_TEST_DB_URL missing) is reported as a failure instead of a skip.
"""
import os

import pytest

SECURITY_TESTS = frozenset({
    "test_admin_security_84c0.py",
    "test_data_export_85b.py",
    "test_admin_stepup_84c.py",
    "test_scope_path_88a.py",
    "test_admin_staff_84c2a1.py",
    "test_admin_staff_84c2a2.py",
    "test_admin_staff_84c2b1.py",
    "test_security_84c0b.py",
    "test_admin_mfa_84b.py",
    "test_admin_email_view_84a.py",
    "test_admin_email_keys_84a2.py",
    "test_account_deletion_85a.py",
    "test_account_purge_85c.py",
})


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if (rep.skipped and os.environ.get("TW_SECURITY_TESTS_REQUIRED") == "1"
            and os.path.basename(str(item.fspath)) in SECURITY_TESTS):
        rep.outcome = "failed"
        rep.longrepr = (f"{item.nodeid}: security test skipped while TW_SECURITY_TESTS_REQUIRED=1 "
                        f"(reason: {rep.longrepr[-1] if isinstance(rep.longrepr, tuple) else rep.longrepr})")
