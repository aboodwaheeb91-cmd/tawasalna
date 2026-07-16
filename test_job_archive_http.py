"""
PR-JOB HTTP Tests — Soft Archive for Jobs (TestClient)
Tests server.py endpoint contracts without requiring a live DB.
All auth functions are patched; only HTTP routing + validation is exercised.

Run: python test_job_archive_http.py

Tests:
  http-01  DELETE /company/jobs/{id} by owner → 200 + {success, archived, was_already_archived}
  http-02  archived_by comes from JWT user_id, not from body or query param
  http-03  DELETE by non-owner → 403
  http-04  DELETE missing job → 404
  http-05  GET /company/jobs?view=invalid → 422
  http-06  GET /company/jobs by employee → 403 (companies/edu only)
  http-07  POST /jobs/{id}/apply on archived job → 409 exact JSON {code, message}
  http-08  409 body NOT wrapped in {"error":...} or {"detail":...}
  http-09  GET /jobs/{id} for archived job → 404
  http-10  GET /stats excludes archived jobs from jobs_count
  http-11  GET /company/jobs?view=active returns active jobs only
  http-12  GET /company/jobs?view=archived returns archived jobs
  http-13  Non-company user cannot DELETE /company/jobs (emp → 403)
  http-14  Idempotent archive returns was_already_archived=True
  Exit code: 0 on all pass, 1 on any failure
"""

import sys, os, json

# Point to a dummy DB URL — all DB calls are patched in these tests
os.environ.setdefault('SUPABASE_DB_URL', 'postgresql://x:x@127.0.0.1:5432/notused')

from unittest.mock import patch, MagicMock

# Import server (and transitively auth) — app is built at import time
import server
from server import app, verify_token
from auth import JobArchivedError
from fastapi.testclient import TestClient

# Suppress startup event failures (DB not available in mock mode)
client = TestClient(app, raise_server_exceptions=True)

# ── Result tracking ────────────────────────────────────────────────────────────
PASS, FAIL = '✅ PASS', '❌ FAIL'
results = []

def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = '✅' if condition else '❌'
    suffix = f'  [{detail}]' if detail and not condition else ''
    print(f'{marker}  {name}{suffix}')

# ── Dependency helpers ─────────────────────────────────────────────────────────
def _co_dep(user_id=10):
    def _f():
        return {"valid": True, "user_id": user_id, "user_type": "co"}
    return _f

def _emp_dep(user_id=20):
    def _f():
        return {"valid": True, "user_id": user_id, "user_type": "emp"}
    return _f

print("=" * 60)
print("PR-JOB — HTTP Endpoint Tests (TestClient + mocks)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# http-01  Owner archives job → 200 + correct response shape
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
_archive_ret = {"archived": True, "was_already_archived": False}
with patch('server.archive_job', return_value=_archive_ret) as _mock01:
    _r01 = client.delete("/company/jobs/55")
app.dependency_overrides.clear()

check("http-01a. DELETE /company/jobs/55 → 200", _r01.status_code == 200, f"status={_r01.status_code}")
_body01 = _r01.json()
check("http-01b. Response has success=True", _body01.get('success') is True, f"body={_body01}")
check("http-01c. Response has archived=True", _body01.get('archived') is True, f"body={_body01}")
check("http-01d. Response has was_already_archived=False", _body01.get('was_already_archived') is False, f"body={_body01}")

# ─────────────────────────────────────────────────────────────────────────────
# http-02  archived_by comes from JWT user_id only (not body, not query)
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=77)
with patch('server.archive_job', return_value=_archive_ret) as _mock02:
    # Even if client sends a fake query param, server ignores it and uses JWT
    _r02 = client.delete("/company/jobs/55?company_id=999&archived_by=999")
app.dependency_overrides.clear()

check("http-02. archive_job called with JWT user_id=77 (not 999 from body)",
      _mock02.call_args[0][1] == 77 and _mock02.call_args[0][2] == 77,
      f"call_args={_mock02.call_args}")

# ─────────────────────────────────────────────────────────────────────────────
# http-03  Non-owner → 403
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=88)
with patch('server.archive_job', side_effect=PermissionError("ليست وظيفتك")):
    _r03 = client.delete("/company/jobs/55")
app.dependency_overrides.clear()

check("http-03. Non-owner DELETE → 403", _r03.status_code == 403, f"status={_r03.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-04  Missing job → 404
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
with patch('server.archive_job', side_effect=LookupError("الوظيفة غير موجودة")):
    _r04 = client.delete("/company/jobs/999999")
app.dependency_overrides.clear()

check("http-04. Missing job DELETE → 404", _r04.status_code == 404, f"status={_r04.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-05  GET /company/jobs?view=invalid → 422
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
_r05 = client.get("/company/jobs?view=invalid")
app.dependency_overrides.clear()

check("http-05. GET /company/jobs?view=invalid → 422", _r05.status_code == 422, f"status={_r05.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-06  GET /company/jobs by employee → 403
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _emp_dep(user_id=20)
_r06 = client.get("/company/jobs")
app.dependency_overrides.clear()

check("http-06. Employee GET /company/jobs → 403", _r06.status_code == 403, f"status={_r06.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-07  Apply to archived job → 409 with exact {code, message} body
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _emp_dep(user_id=20)
with patch('server.apply_job', side_effect=JobArchivedError()):
    _r07 = client.post("/jobs/55/apply", json={"cover_letter": "test"})
app.dependency_overrides.clear()

check("http-07a. Apply to archived job → 409", _r07.status_code == 409, f"status={_r07.status_code}")
_body07 = _r07.json()
check("http-07b. 409 body has 'code' key", 'code' in _body07, f"body={_body07}")
check("http-07c. 409 body code == 'job_archived'", _body07.get('code') == 'job_archived', f"body={_body07}")
check("http-07d. 409 body has 'message' key", 'message' in _body07, f"body={_body07}")

# ─────────────────────────────────────────────────────────────────────────────
# http-08  409 body NOT wrapped in {"error":...} or {"detail":...}
# ─────────────────────────────────────────────────────────────────────────────
check("http-08a. 409 body top-level has NO 'error' key", 'error' not in _body07, f"body={_body07}")
check("http-08b. 409 body top-level has NO 'detail' key", 'detail' not in _body07, f"body={_body07}")

# ─────────────────────────────────────────────────────────────────────────────
# http-09  GET /jobs/{id} for archived job → 404
# ─────────────────────────────────────────────────────────────────────────────
with patch('server.get_job', return_value=None):
    _r09 = client.get("/jobs/55")

check("http-09. GET /jobs/{id} for archived job → 404", _r09.status_code == 404, f"status={_r09.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-10  GET /stats excludes archived jobs (jobs_count uses archived_at IS NULL)
# ─────────────────────────────────────────────────────────────────────────────
_mock_conn = MagicMock()
# pg8000 rows: conn.run(...) returns list-of-rows; each row is subscriptable.
# stats() does conn.run(...)[0][0] for each count.
_mock_conn.run.side_effect = [[[100]], [[70]], [[20]], [[10]], [[5]]]
_mock_release = MagicMock()

with patch('server.get_conn', return_value=_mock_conn), \
     patch('server.release_conn', _mock_release):
    _r10 = client.get("/stats")

check("http-10a. GET /stats → 200", _r10.status_code == 200, f"status={_r10.status_code}")
_body10 = _r10.json()
check("http-10b. /stats returns jobs_count field", 'jobs_count' in _body10, f"body={_body10}")
# Verify the 5th SQL call (jobs_count) includes archived_at IS NULL
_calls10 = [c.args[0] if c.args else '' for c in _mock_conn.run.call_args_list]
_jobs_query = _calls10[4] if len(_calls10) >= 5 else ""
check("http-10c. /stats jobs query includes archived_at IS NULL",
      "archived_at IS NULL" in _jobs_query,
      f"query={_jobs_query}")

# ─────────────────────────────────────────────────────────────────────────────
# http-11  GET /company/jobs?view=active returns active (mock)
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
_active_jobs = [{"id": 1, "title": "وظيفة نشطة"}]
with patch('server.get_company_jobs_all', return_value=_active_jobs):
    _r11 = client.get("/company/jobs?view=active")
app.dependency_overrides.clear()

check("http-11a. GET /company/jobs?view=active → 200", _r11.status_code == 200, f"status={_r11.status_code}")
_body11 = _r11.json()
check("http-11b. Response has view='active'", _body11.get('view') == 'active', f"body={_body11}")
check("http-11c. Response has jobs array", isinstance(_body11.get('jobs'), list), f"body={_body11}")

# ─────────────────────────────────────────────────────────────────────────────
# http-12  GET /company/jobs?view=archived returns archived (mock)
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
_arch_jobs = [{"id": 2, "title": "وظيفة مؤرشفة", "archived_at": "2026-01-01T00:00:00Z"}]
with patch('server.get_company_jobs_all', return_value=_arch_jobs) as _mock12:
    _r12 = client.get("/company/jobs?view=archived")
app.dependency_overrides.clear()

check("http-12a. GET /company/jobs?view=archived → 200", _r12.status_code == 200, f"status={_r12.status_code}")
_body12 = _r12.json()
check("http-12b. Response has view='archived'", _body12.get('view') == 'archived', f"body={_body12}")
check("http-12c. get_company_jobs_all called with view='archived'",
      _mock12.call_args[1].get('view') == 'archived' if _mock12.call_args[1] else
      (_mock12.call_args[0][1] == 'archived' if len(_mock12.call_args[0]) > 1 else False),
      f"call_args={_mock12.call_args}")

# ─────────────────────────────────────────────────────────────────────────────
# http-13  Employee cannot DELETE /company/jobs (403)
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _emp_dep(user_id=20)
_r13 = client.delete("/company/jobs/55")
app.dependency_overrides.clear()

check("http-13. Employee DELETE /company/jobs → 403", _r13.status_code == 403, f"status={_r13.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-14  Idempotent archive returns was_already_archived=True
# ─────────────────────────────────────────────────────────────────────────────
app.dependency_overrides[verify_token] = _co_dep(user_id=10)
_idem_ret = {"archived": True, "was_already_archived": True}
with patch('server.archive_job', return_value=_idem_ret):
    _r14 = client.delete("/company/jobs/55")
app.dependency_overrides.clear()

check("http-14a. Idempotent archive → 200", _r14.status_code == 200, f"status={_r14.status_code}")
_body14 = _r14.json()
check("http-14b. was_already_archived=True in response", _body14.get('was_already_archived') is True, f"body={_body14}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = total - passed
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌ {name}" + (f"  [{detail}]" if detail else ""))
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
