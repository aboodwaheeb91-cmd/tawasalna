"""
PR-2 Pipeline Backfill — Admin HTTP Endpoint Tests (TestClient)
Tests server.py admin pipeline endpoints without a live DB.
All auth functions + auth.py pipeline functions are patched; only HTTP routing and
validation logic is exercised.

Run: python test_pipeline_backfill_http.py

Tests:
  http-p-01  POST /admin/pipeline/backfill without X-Admin-Token → 403
  http-p-02  GET  /admin/pipeline/backfill/dry-run without token  → 403
  http-p-03  POST /admin/pipeline/migrate-index without token     → 403
  http-p-04  POST /admin/pipeline/backfill with confirm=false     → 400
  http-p-05  GET  /admin/pipeline/backfill/dry-run (valid token)  → 200 dict
  http-p-06  POST /admin/pipeline/backfill dry_run=true           → 200 dict
  http-p-07  POST /admin/pipeline/backfill confirm=true → BlockingConflictError → 409
  http-p-08  409 body is NOT wrapped in {"error":...} or {"detail":...}
  http-p-09  409 body has conflicts_by_type + blocking=True structure
  http-p-10  POST /admin/pipeline/backfill confirm=true (no conflict) → 200 dict
  http-p-11  POST /admin/pipeline/migrate-index without confirm   → 400
  http-p-12  POST /admin/pipeline/migrate-index confirm=true      → 200 {status, message}
  http-p-13  POST /admin/pipeline/migrate-index → BlockingConflictError → 409
  http-p-14  409 from migrate-index not wrapped in error/detail

  Exit code: 0 on all pass, 1 on any failure
"""

import sys, os, hashlib, json
from unittest.mock import patch, MagicMock

# Point to a dummy DB URL — all DB calls are patched in these tests
os.environ.setdefault('SUPABASE_DB_URL', 'postgresql://x:x@127.0.0.1:5432/notused')

# Import server (and transitively auth) — app is built at import time
import server
from server import app
from auth import BlockingConflictError
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=True)

# Compute the real admin token — same formula as server.py
ADMIN_PASSWORD = "tw@admin2025"
VALID_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
WRONG_TOKEN  = "not-the-right-token"

# ── Result tracking ────────────────────────────────────────────────────────────
PASS, FAIL = "✅ PASS", "❌ FAIL"
results = []

def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = "✅" if condition else "❌"
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"{marker}  {name}{suffix}")

# ── Shared sample reports ──────────────────────────────────────────────────────
# Matches the actual structure raised in auth.py (run_pipeline_backfill)
_BLOCKING_REPORT = {
    "error":             "blocking_conflicts",
    "detail":            "تم اكتشاف تعارضات حاجبة — أصلحها قبل تشغيل الـ backfill.",
    "conflicts_by_type": {"missing_job": 2},
    "conflicts_count":   2,
    "blocking":          True,
}

_DRY_RUN_RESULT = {
    "conflicts_by_type": {},
    "conflicts_count": 0,
    "blocking": False,
    "ja_new": 5,
    "ja_linkable": 3,
    "ccjr_new": 2,
    "ccjr_existing": 4,
    "notes": [],
}

_BACKFILL_RESULT = {
    "status": "ok",
    "entries_created": 5,
    "entries_updated": 2,
    "application_links_added": 3,
    "skipped_entries": 0,
    "stage_events_created": 7,
    "conflicts_by_type": {},
}

print("=" * 64)
print("PR-2 Pipeline Backfill — Admin HTTP Endpoint Tests (TestClient)")
print("=" * 64)

# ─────────────────────────────────────────────────────────────────────────────
# http-p-01  POST /admin/pipeline/backfill without token → 403
# ─────────────────────────────────────────────────────────────────────────────
_r01 = client.post("/admin/pipeline/backfill")
check("http-p-01. POST /admin/pipeline/backfill (no token) → 403",
      _r01.status_code == 403, f"status={_r01.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-02  GET /admin/pipeline/backfill/dry-run without token → 403
# ─────────────────────────────────────────────────────────────────────────────
_r02 = client.get("/admin/pipeline/backfill/dry-run")
check("http-p-02. GET /admin/pipeline/backfill/dry-run (no token) → 403",
      _r02.status_code == 403, f"status={_r02.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-03  POST /admin/pipeline/migrate-index without token → 403
# ─────────────────────────────────────────────────────────────────────────────
_r03 = client.post("/admin/pipeline/migrate-index")
check("http-p-03. POST /admin/pipeline/migrate-index (no token) → 403",
      _r03.status_code == 403, f"status={_r03.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-04  POST /admin/pipeline/backfill with valid token but confirm=false → 400
#            (dry_run=false by default; confirm must be true for real run)
# ─────────────────────────────────────────────────────────────────────────────
_headers = {"X-Admin-Token": VALID_TOKEN}
_r04 = client.post("/admin/pipeline/backfill", headers=_headers)
check("http-p-04. POST /admin/pipeline/backfill (confirm=false) → 400",
      _r04.status_code == 400, f"status={_r04.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-05  GET /admin/pipeline/backfill/dry-run with valid token → 200 dict
# ─────────────────────────────────────────────────────────────────────────────
with patch('server.pipeline_backfill_dry_run', return_value=_DRY_RUN_RESULT):
    _r05 = client.get("/admin/pipeline/backfill/dry-run", headers=_headers)

check("http-p-05a. GET /admin/pipeline/backfill/dry-run (valid token) → 200",
      _r05.status_code == 200, f"status={_r05.status_code}")
_body05 = _r05.json()
check("http-p-05b. dry-run response has 'conflicts_by_type'",
      "conflicts_by_type" in _body05, f"body={_body05}")
check("http-p-05c. dry-run response has 'blocking' field",
      "blocking" in _body05, f"body={_body05}")
check("http-p-05d. dry-run response has 'conflicts_count'",
      "conflicts_count" in _body05, f"body={_body05}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-06  POST /admin/pipeline/backfill?dry_run=true → 200 dict
#            (dry_run=true does not require confirm)
# ─────────────────────────────────────────────────────────────────────────────
with patch('server.run_pipeline_backfill', return_value=_DRY_RUN_RESULT) as _mock06:
    _r06 = client.post("/admin/pipeline/backfill?dry_run=true", headers=_headers)

check("http-p-06a. POST /admin/pipeline/backfill?dry_run=true → 200",
      _r06.status_code == 200, f"status={_r06.status_code}")
check("http-p-06b. run_pipeline_backfill called with dry_run=True",
      _mock06.call_args is not None and _mock06.call_args.kwargs.get("dry_run") is True,
      f"call_args={_mock06.call_args}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-07  POST /admin/pipeline/backfill?confirm=true → BlockingConflictError → 409
# ─────────────────────────────────────────────────────────────────────────────
with patch('server.run_pipeline_backfill',
           side_effect=BlockingConflictError(_BLOCKING_REPORT)):
    _r07 = client.post("/admin/pipeline/backfill?confirm=true", headers=_headers)

check("http-p-07. BlockingConflictError → 409",
      _r07.status_code == 409, f"status={_r07.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-08  409 body is NOT wrapped — conflicts_by_type is at the top level,
#            not nested inside {"detail": {...}} as FastAPI's HTTPException would do.
# ─────────────────────────────────────────────────────────────────────────────
_body07 = _r07.json()
check("http-p-08a. 409 body has 'conflicts_by_type' at top level (not wrapped)",
      isinstance(_body07.get("conflicts_by_type"), dict), f"body={_body07}")
check("http-p-08b. 409 body 'detail' is a string (not a nested conflict dict)",
      isinstance(_body07.get("detail"), str), f"body={_body07}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-09  409 body has conflicts_by_type + blocking=True structure
# ─────────────────────────────────────────────────────────────────────────────
check("http-p-09a. 409 body has 'conflicts_by_type'",
      "conflicts_by_type" in _body07, f"body={_body07}")
check("http-p-09b. 409 body has blocking=True",
      _body07.get("blocking") is True, f"body={_body07}")
check("http-p-09c. 409 body has 'conflicts_count'",
      "conflicts_count" in _body07, f"body={_body07}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-10  POST /admin/pipeline/backfill?confirm=true (no conflicts) → 200 dict
# ─────────────────────────────────────────────────────────────────────────────
with patch('server.run_pipeline_backfill', return_value=_BACKFILL_RESULT):
    _r10 = client.post("/admin/pipeline/backfill?confirm=true", headers=_headers)

check("http-p-10a. backfill (no conflicts) → 200",
      _r10.status_code == 200, f"status={_r10.status_code}")
_body10 = _r10.json()
check("http-p-10b. backfill result has 'entries_created'",
      "entries_created" in _body10, f"body={_body10}")
check("http-p-10c. backfill result has 'status'='ok'",
      _body10.get("status") == "ok", f"body={_body10}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-11  POST /admin/pipeline/migrate-index without confirm → 400
# ─────────────────────────────────────────────────────────────────────────────
_r11 = client.post("/admin/pipeline/migrate-index", headers=_headers)
check("http-p-11. POST /admin/pipeline/migrate-index (confirm=false) → 400",
      _r11.status_code == 400, f"status={_r11.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-12  POST /admin/pipeline/migrate-index?confirm=true → 200 + {status, message}
# ─────────────────────────────────────────────────────────────────────────────
with patch('server._migrate_partial_unique_application_id', return_value=None):
    _r12 = client.post("/admin/pipeline/migrate-index?confirm=true", headers=_headers)

check("http-p-12a. migrate-index (confirm=true) → 200",
      _r12.status_code == 200, f"status={_r12.status_code}")
_body12 = _r12.json()
check("http-p-12b. migrate-index response has 'status'='ok'",
      _body12.get("status") == "ok", f"body={_body12}")
check("http-p-12c. migrate-index response has 'message'",
      "message" in _body12, f"body={_body12}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-13  POST /admin/pipeline/migrate-index → BlockingConflictError → 409
# ─────────────────────────────────────────────────────────────────────────────
with patch('server._migrate_partial_unique_application_id',
           side_effect=BlockingConflictError(_BLOCKING_REPORT)):
    _r13 = client.post("/admin/pipeline/migrate-index?confirm=true", headers=_headers)

check("http-p-13. migrate-index BlockingConflictError → 409",
      _r13.status_code == 409, f"status={_r13.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# http-p-14  409 from migrate-index not wrapped in error/detail
# ─────────────────────────────────────────────────────────────────────────────
_body13 = _r13.json()
check("http-p-14a. migrate-index 409 body has 'conflicts_by_type' at top level",
      isinstance(_body13.get("conflicts_by_type"), dict), f"body={_body13}")
check("http-p-14b. migrate-index 409 body 'detail' is a string (not nested conflict dict)",
      isinstance(_body13.get("detail"), str), f"body={_body13}")
check("http-p-14c. migrate-index 409 body has 'blocking'=True",
      _body13.get("blocking") is True, f"body={_body13}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
total  = len(results)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = total - passed
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌ {name}" + (f"  [{detail}]" if detail else ""))
print("=" * 64)

sys.exit(0 if failed == 0 else 1)
