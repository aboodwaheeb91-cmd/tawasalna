"""
PR-2: Pipeline Backfill + Dual-write — static (source-inspection) tests.

Tests validate source-code structure for all 12 correction points (Bnd-1 through Bnd-12).

  §A  Mapping constants
  §B  _pipeline_upsert_entry helper — source='application' on link (Bnd-2)
  §C  _pipeline_update_stage helper — reason parameter present
  §D  pipeline_backfill_dry_run — comprehensive conflicts, LEFT JOINs (Bnd-3)
  §E  run_pipeline_backfill — atomic conflict check (Bnd-8), NULL CCJR (Bnd-1),
                              source='application' in Pass-2 DO UPDATE (Bnd-2),
                              notes.strip() in Pass-3 (Bnd-7)
  §F  _migrate_partial_unique_application_id — advisory lock, BlockingConflictError (Bnd-9)
  §G  apply_job — created_by=user_id (Bnd-6), initial_event_reason='application_submitted'
  §H  update_application_status — reason='application_status_changed' (Bnd-6)
  §I  promote_application_to_shortlist — Option B: no company_saved_candidates write (Bnd-4),
                                         reason='application_shortlisted' (Bnd-6)
  §J  update_candidate_job_status — ensure-entry (Bnd-5), None handling (Bnd-5),
                                    reason='candidate_job_status_changed' (Bnd-6)
  §K  Compatibility — legacy tables still writable, no read switch
  §L  BlockingConflictError class + server.py JSONResponse (Bnd-8, Bnd-9)
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"{'✅' if condition else '❌'}  {name}{suffix}")

auth_path = os.path.join(os.path.dirname(__file__), "auth.py")
with open(auth_path, encoding="utf-8") as _f:
    _auth = _f.read()

server_path = os.path.join(os.path.dirname(__file__), "server.py")
with open(server_path, encoding="utf-8") as _f:
    _server = _f.read()

# ── helpers ──────────────────────────────────────────────────────────────────
def _fn(src, name, window=5000):
    """Extract a window of source starting at the function definition."""
    idx = src.find(f"def {name}(")
    if idx == -1:
        return ""
    return src[idx: idx + window]

def _block(src, marker, window=3000):
    idx = src.find(marker)
    if idx == -1:
        return ""
    return src[idx: idx + window]

# ═══════════════════════════════════════════════════════════════════════════════
# §A  Mapping constants
# ═══════════════════════════════════════════════════════════════════════════════
# Extract the dict literal body for each mapping (finds assignment line = { ... })
def _dict_body(src, var_name):
    # Search for the assignment pattern: VAR_NAME: dict = { or VAR_NAME = {
    import re as _re
    pattern = rf'\b{_re.escape(var_name)}\b[^=]*=\s*\{{'
    m = _re.search(pattern, src)
    if not m:
        return ""
    start = src.find("{", m.start())
    end   = src.find("}", start)
    return src[start:end+1] if start != -1 and end != -1 else ""

_la2p = _dict_body(_auth, "LEGACY_APP_STATUS_TO_PIPELINE_STAGE")
_lc2p = _dict_body(_auth, "LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE")

def _kv(d, k, v):
    """Check that k→v mapping appears in dict body (handles both quote styles)."""
    return any(
        (f"{q1}{k}{q1}" in d and f"{q2}{v}{q2}" in d)
        for q1 in ('"', "'") for q2 in ('"', "'")
    )

check("A-01. LEGACY_APP_STATUS_TO_PIPELINE_STAGE defined in auth.py",
      "LEGACY_APP_STATUS_TO_PIPELINE_STAGE" in _auth)
check("A-02. Maps 'pending' → 'new'",
      _kv(_la2p, "pending", "new"))
check("A-03. Maps 'viewed' → 'reviewing'",
      _kv(_la2p, "viewed", "reviewing"))
check("A-04. Maps 'accepted' → 'shortlisted'",
      _kv(_la2p, "accepted", "shortlisted"))
check("A-05. Maps 'contacted' → 'contacted'",
      _kv(_la2p, "contacted", "contacted"))
check("A-06. Maps 'interview' → 'interview'",
      _kv(_la2p, "interview", "interview"))
check("A-07. Maps 'hired' → 'hired'",
      _kv(_la2p, "hired", "hired"))
check("A-08. Maps 'rejected' → 'rejected'",
      _kv(_la2p, "rejected", "rejected"))

check("A-09. LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE defined",
      "LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE" in _auth)
check("A-10. Maps 'saved' → 'new'",
      _kv(_lc2p, "saved", "new"))
check("A-11. Maps 'shortlisted' → 'shortlisted'",
      _kv(_lc2p, "shortlisted", "shortlisted"))

# ═══════════════════════════════════════════════════════════════════════════════
# §B  _pipeline_upsert_entry helper
# ═══════════════════════════════════════════════════════════════════════════════
_pu = _fn(_auth, "_pipeline_upsert_entry")

check("B-01. _pipeline_upsert_entry defined",
      "def _pipeline_upsert_entry(" in _auth)
check("B-02. Inserts into job_pipeline_entries",
      "INSERT INTO job_pipeline_entries" in _pu)
check("B-03. Uses SELECT ... FOR UPDATE (race-safe upsert — no ON CONFLICT DO NOTHING)",
      "FOR UPDATE" in _pu)
check("B-04. RETURNING id",
      "RETURNING id" in _pu)
check("B-05. application_id parameter accepted",
      "application_id" in _pu)
check("B-06. source parameter accepted",
      "source" in _pu and ":src" in _pu)
check("B-07. Does NOT commit/rollback",
      "conn.run(\"COMMIT\")" not in _pu and "COMMIT" not in _pu)
check("B-08. Updates source='application' when linking application_id (Bnd-2)",
      "source = 'application'" in _pu or "source='application'" in _pu)
check("B-09. initial_event_reason parameter accepted",
      "initial_event_reason" in _pu)
check("B-10. Creates initial stage event when initial_event_reason provided",
      "INSERT INTO pipeline_stage_events" in _pu)

# ═══════════════════════════════════════════════════════════════════════════════
# §C  _pipeline_update_stage helper
# ═══════════════════════════════════════════════════════════════════════════════
_ups = _fn(_auth, "_pipeline_update_stage")

check("C-01. _pipeline_update_stage defined",
      "def _pipeline_update_stage(" in _auth)
check("C-02. UPDATE job_pipeline_entries",
      "UPDATE job_pipeline_entries" in _ups)
check("C-03. Sets stage, stage_updated_at, updated_at",
      "stage_updated_at" in _ups and "updated_at" in _ups)
check("C-04. RETURNING id to detect no-op",
      "RETURNING id" in _ups)
check("C-05. Returns bool — True if row found",
      "return bool(rows)" in _ups)
check("C-06. Does NOT commit/rollback",
      "COMMIT" not in _ups)

# ═══════════════════════════════════════════════════════════════════════════════
# §D  pipeline_backfill_dry_run
# ═══════════════════════════════════════════════════════════════════════════════
# Narrow the dry_run body to only the function itself (ends before run_pipeline_backfill)
def _fn_body(src, name, window=5000):
    idx = src.find(f"def {name}(")
    if idx == -1:
        return ""
    # Find next top-level def after this function
    next_def = src.find("\ndef ", idx + 1)
    if next_def == -1:
        end = idx + window
    else:
        end = min(idx + window, next_def)
    return src[idx:end]

_dr = _fn_body(_auth, "pipeline_backfill_dry_run", window=20000)

check("D-01. pipeline_backfill_dry_run defined",
      "def pipeline_backfill_dry_run(" in _auth)
check("D-02. Reads job_applications",
      "FROM job_applications" in _dr)
check("D-03. Reads company_candidate_job_refs",
      "FROM company_candidate_job_refs" in _dr)
check("D-04. Reads company_saved_candidates notes",
      "company_saved_candidates" in _dr and "notes" in _dr)
check("D-05. Returns dry_run=True in result",
      '"dry_run": True' in _dr or "'dry_run': True" in _dr)
check("D-06. No INSERT/UPDATE/DELETE (read-only)",
      "INSERT" not in _dr and "UPDATE" not in _dr and "DELETE" not in _dr)
check("D-07. Uses LEFT JOIN (no hidden rows) for comprehensive conflicts (Bnd-3)",
      "LEFT JOIN" in _dr)
check("D-08. Detects null_ccjr_without_application (Bnd-1/Bnd-3)",
      "null_ccjr_without_application" in _dr)
check("D-09. Detects job_owner_mismatch (Bnd-3)",
      "job_owner_mismatch" in _dr)
check("D-10. Detects application_identity_mismatch (Bnd-3)",
      "application_identity_mismatch" in _dr)
check("D-11. Detects duplicate_application_claim (Bnd-3)",
      "duplicate_application_claim" in _dr)
check("D-12. Blocking is a bool (not just one field) (Bnd-3)",
      "blocking = " in _dr or "blocking=" in _dr)

# ═══════════════════════════════════════════════════════════════════════════════
# §E  run_pipeline_backfill
# ═══════════════════════════════════════════════════════════════════════════════
_bf = _fn(_auth, "run_pipeline_backfill", window=25000)

check("E-01. run_pipeline_backfill defined",
      "def run_pipeline_backfill(" in _auth)
check("E-02. dry_run=True delegates to pipeline_backfill_dry_run",
      "pipeline_backfill_dry_run" in _bf)
check("E-03. Pass-1 from company_candidate_job_refs",
      "company_candidate_job_refs" in _bf)
check("E-04. Pass-1 uses 'migration' source",
      "'migration'" in _bf)
check("E-05. Pass-2 from job_applications",
      "job_applications" in _bf)
check("E-06. Pass-2 sets application_id",
      "application_id" in _bf and "EXCLUDED.application_id" in _bf)
check("E-07. Pass-3 migrates company_saved_candidates.notes",
      "company_saved_candidates" in _bf and "candidate_bank_notes" in _bf)
check("E-08. migration_source_key prevents re-insertion",
      "migration_source_key" in _bf and "ON CONFLICT" in _bf)
check("E-09. Wrapped in single transaction (BEGIN/COMMIT/ROLLBACK)",
      'conn.run("BEGIN")' in _bf
      and 'conn.run("COMMIT")' in _bf
      and 'conn.run("ROLLBACK")' in _bf)
check("E-10. committed guard present",
      "committed = False" in _bf and "committed = True" in _bf)
check("E-11. Returns entries_created + application_links_added + backward-compat aliases",
      "entries_created" in _bf and "application_links_added" in _bf
      and "inserted_entries" in _bf and "skipped_entries" in _bf)
check("E-12. Returns bank_notes_created + backward-compat aliases",
      "bank_notes_created" in _bf and "inserted_notes" in _bf and "skipped_notes" in _bf)
check("E-13. Atomic blocking conflict check inside advisory lock (Bnd-8)",
      "blocking_check" in _bf and "BlockingConflictError" in _bf)
check("E-14. NULL CCJR fallback: looks up application (Bnd-1)",
      "cand_status is None" in _bf or "null_ccjr_without_application" in _bf)
check("E-15. Pass-2 DO UPDATE also sets source='application' (Bnd-2)",
      "source = 'application'" in _bf or "source='application'" in _bf)
check("E-16. Pass-3 notes.strip() (Bnd-7)",
      ".strip()" in _bf)
check("E-17. Pass-3 preserves created_at (Bnd-7)",
      "created_at" in _bf and "legacy_created_at" in _bf)

# ═══════════════════════════════════════════════════════════════════════════════
# §F  _migrate_partial_unique_application_id
# ═══════════════════════════════════════════════════════════════════════════════
_pui = _fn(_auth, "_migrate_partial_unique_application_id")

check("F-01. _migrate_partial_unique_application_id defined",
      "def _migrate_partial_unique_application_id(" in _auth)
check("F-02. Creates UNIQUE INDEX on application_id",
      "UNIQUE INDEX" in _pui and "application_id" in _pui)
check("F-03. Partial index WHERE application_id IS NOT NULL",
      "WHERE application_id IS NOT NULL" in _pui)
check("F-04. IF NOT EXISTS (idempotent)",
      "IF NOT EXISTS" in _pui)
check("F-05. Handles duplicate_object / 42710 silently",
      "42710" in _pui or "duplicate_object" in _pui)
check("F-06. Advisory lock before index creation (Bnd-9)",
      "pg_advisory_xact_lock" in _pui)
check("F-07. Rechecks duplicate application_ids before creating index (Bnd-9)",
      "HAVING COUNT(*) > 1" in _pui or "duplicate_application_claim" in _pui)
check("F-08. Raises BlockingConflictError on blocking conflicts (Bnd-9)",
      "BlockingConflictError" in _pui)
check("F-09. Verifies index exists via pg_indexes (Bnd-9)",
      "pg_indexes" in _pui)

# ═══════════════════════════════════════════════════════════════════════════════
# §G  apply_job dual-write
# ═══════════════════════════════════════════════════════════════════════════════
_aj = _fn(_auth, "apply_job", window=4000)

check("G-01. apply_job calls _pipeline_upsert_entry",
      "_pipeline_upsert_entry(" in _aj)
# apply_job has two COMMITs: early return (already_applied) and main path.
# We verify the pipeline upsert comes BEFORE the LAST COMMIT (main path).
check("G-02. Pipeline upsert is before COMMIT on the main path",
      "_pipeline_upsert_entry(" in _aj
      and _aj.rfind("_pipeline_upsert_entry(") < _aj.rfind('conn.run("COMMIT")'))
check("G-03. source='application'",
      "source=\"application\"" in _aj or "source='application'" in _aj)
check("G-04. stage='new'",
      "stage=\"new\"" in _aj or "stage='new'" in _aj)
check("G-05. created_by=user_id (employee, NOT company) (Bnd-6)",
      "created_by=user_id" in _aj or "created_by = user_id" in _aj)
check("G-06. initial_event_reason='application_submitted' (Bnd-6)",
      "application_submitted" in _aj)

# ═══════════════════════════════════════════════════════════════════════════════
# §H  update_application_status dual-write
# ═══════════════════════════════════════════════════════════════════════════════
_uas = _fn(_auth, "update_application_status", window=4000)

check("H-01. update_application_status calls _pipeline_update_stage",
      "_pipeline_update_stage(" in _uas)
check("H-02. Pipeline update is before COMMIT",
      _uas.find("_pipeline_update_stage(") < _uas.find('conn.run("COMMIT")'))
check("H-03. Uses LEGACY_APP_STATUS_TO_PIPELINE_STAGE",
      "LEGACY_APP_STATUS_TO_PIPELINE_STAGE" in _uas)
check("H-04. Legacy table writes are NOT removed (job_applications UPDATE still present)",
      "UPDATE job_applications SET status" in _uas)
check("H-05. Legacy company_candidate_job_refs UPSERT still present",
      "company_candidate_job_refs" in _uas)
check("H-06. reason='application_status_changed' passed to _pipeline_update_stage (Bnd-6)",
      "application_status_changed" in _uas)

# ═══════════════════════════════════════════════════════════════════════════════
# §I  promote_application_to_shortlist dual-write
# ═══════════════════════════════════════════════════════════════════════════════
_pa = _fn(_auth, "promote_application_to_shortlist", window=9000)

check("I-01. promote_application_to_shortlist calls _pipeline_update_stage",
      "_pipeline_update_stage(" in _pa)
check("I-02. Pipeline update is before COMMIT",
      _pa.find("_pipeline_update_stage(") < _pa.find('conn.run("COMMIT")'))
check("I-03. new_stage='shortlisted'",
      "new_stage=\"shortlisted\"" in _pa or "new_stage='shortlisted'" in _pa)
check("I-04. Option B: NO INSERT/UPSERT to company_saved_candidates (Bnd-4)",
      "INSERT INTO company_saved_candidates" not in _pa)
check("I-05. Reads general_status via SELECT only (no FOR UPDATE, no write) (Bnd-4)",
      "SELECT status FROM company_saved_candidates" in _pa
      and "FOR UPDATE" not in _pa.split("SELECT status FROM company_saved_candidates")[0][-200:])
check("I-06. reason='application_shortlisted' passed (Bnd-6)",
      "application_shortlisted" in _pa)

# ═══════════════════════════════════════════════════════════════════════════════
# §J  update_candidate_job_status transaction + dual-write
# ═══════════════════════════════════════════════════════════════════════════════
_ucjs = _fn(_auth, "update_candidate_job_status", window=3000)

_ucjs = _fn(_auth, "update_candidate_job_status", window=9000)

check("J-01. update_candidate_job_status calls _pipeline_update_stage",
      "_pipeline_update_stage(" in _ucjs)
check("J-02. Now wrapped in BEGIN/COMMIT/ROLLBACK transaction",
      'conn.run("BEGIN")' in _ucjs
      and 'conn.run("COMMIT")' in _ucjs
      and 'conn.run("ROLLBACK")' in _ucjs)
check("J-03. Uses LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE",
      "LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE" in _ucjs)
check("J-04. Legacy UPDATE company_candidate_job_refs still present",
      "UPDATE company_candidate_job_refs" in _ucjs)
check("J-05. committed guard present",
      "committed = False" in _ucjs and "committed = True" in _ucjs)
check("J-06. Calls _pipeline_upsert_entry (ensure-entry before update_stage) (Bnd-5)",
      "_pipeline_upsert_entry(" in _ucjs)
check("J-07. Handles candidate_status=None: looks up application (Bnd-5)",
      "candidate_status is None" in _ucjs)
check("J-08. Raises ValueError when None + no application (Bnd-5)",
      "ValueError" in _ucjs and "null" in _ucjs.lower())
check("J-09. reason='candidate_job_status_changed' (Bnd-6)",
      "candidate_job_status_changed" in _ucjs)

# ═══════════════════════════════════════════════════════════════════════════════
# §K  Compatibility — legacy tables stay, no read switch, no frontend change
# ═══════════════════════════════════════════════════════════════════════════════
check("K-01. No DROP TABLE on legacy tables",
      "DROP TABLE company_saved_candidates" not in _auth
      and "DROP TABLE company_candidate_job_refs" not in _auth
      and "DROP TABLE job_applications" not in _auth)
check("K-02. job_applications.status column not removed",
      "DROP COLUMN status" not in _auth)
check("K-03. company_saved_candidates.notes column not removed",
      "DROP COLUMN notes" not in _auth)
check("K-04. No SELECT from job_pipeline_entries in get_company_saved_candidates",
      "job_pipeline_entries" not in _fn(_auth, "get_company_saved_candidates", 6000))
check("K-05. server.py imports new pipeline functions",
      "run_pipeline_backfill" in _server
      and "_migrate_partial_unique_application_id" in _server)
check("K-06. Admin migrate-index endpoint calls _migrate_partial_unique_application_id",
      "_migrate_partial_unique_application_id()" in _server
      and '"/admin/pipeline/migrate-index"' in _server)
check("K-07. Admin backfill endpoint exists with confirm= guard",
      '"/admin/pipeline/backfill"' in _server and "confirm" in _server)
check("K-08. Backfill endpoint requires X-Admin-Token (uses check_admin)",
      "check_admin(request)" in _block(_server, '"/admin/pipeline/backfill"', 800))

# ═══════════════════════════════════════════════════════════════════════════════
# §L  BlockingConflictError class + server.py JSONResponse (Bnd-8, Bnd-9)
# ═══════════════════════════════════════════════════════════════════════════════
check("L-01. BlockingConflictError class defined in auth.py (Bnd-8)",
      "class BlockingConflictError(Exception):" in _auth)
check("L-02. BlockingConflictError has .report attribute",
      "self.report = report" in _auth)
check("L-03. BlockingConflictError imported in server.py (Bnd-8)",
      "BlockingConflictError" in _server)
check("L-04. server.py uses JSONResponse (not HTTPException with dict) for 409 (Bnd-9)",
      "JSONResponse" in _server and "JSONResponse(status_code=409" in _server)
check("L-05. Backfill endpoint catches BlockingConflictError → JSONResponse (Bnd-8)",
      "BlockingConflictError" in _block(_server, '"/admin/pipeline/backfill"', 1200))
check("L-06. migrate-index endpoint catches BlockingConflictError → JSONResponse (Bnd-9)",
      "BlockingConflictError" in _block(_server, '"/admin/pipeline/migrate-index"', 1200))
check("L-07. run_pipeline_backfill raises BlockingConflictError (not RuntimeError) on conflicts",
      "raise BlockingConflictError" in _bf)
check("L-08. run_pipeline_backfill re-raises BlockingConflictError without wrapping",
      "except BlockingConflictError:" in _bf and "raise" in _bf)

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
passed = sum(1 for _, s, _ in results if s == PASS)
failed = len(results) - passed
print()
print("=" * 60)
print(f"Results: {passed}/{len(results)} passed, {failed} failed")
if failed:
    print("\nFailed:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌  {name}" + (f"  [{detail}]" if detail else ""))
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
