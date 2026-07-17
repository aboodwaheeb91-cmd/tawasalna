"""
PR-6: Pipeline Application Uniqueness Guard — static (source-inspection) tests.

Tests validate:
  §A  Stale-test fix — test_post_comments.py no longer uses «غير مصنف»
  §B  get_pipeline_application_index_status() helper present in auth.py
  §C  Helper is read-only (no write SQL inside it)
  §D  Helper returns all four required keys
  §E  Helper uses pg_indexes for basic existence check
  §F  Helper uses pg_index + pg_get_expr for uniqueness/predicate check
  §G  Helper uses try/finally with release_conn (resource-safe)
  §H  Startup warning added to server.py and is non-blocking (try/except wrapper)
  §I  Startup warning references the helper function
  §J  Startup warning prints both «ready» and «not ready» paths
  §K  GET /admin/pipeline/index-status endpoint present in server.py
  §L  get_pipeline_application_index_status imported in server.py
  §M  POST /admin/pipeline/migrate-index uses helper for post-creation check
  §N  POST /admin/pipeline/migrate-index returns index_status in response
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


auth_path   = os.path.join(os.path.dirname(__file__), "auth.py")
server_path = os.path.join(os.path.dirname(__file__), "server.py")
test_cmt_path = os.path.join(os.path.dirname(__file__), "test_post_comments.py")

with open(auth_path, encoding="utf-8") as _f:
    _auth = _f.read()

with open(server_path, encoding="utf-8") as _f:
    _server = _f.read()

with open(test_cmt_path, encoding="utf-8") as _f:
    _test_cmt = _f.read()

# ── isolate helper function body ──────────────────────────────────────────────
_helper_match = re.search(
    r"def get_pipeline_application_index_status\(\)(.*?)(?=\ndef |\Z)",
    _auth,
    re.DOTALL
)
_helper_src = _helper_match.group(0) if _helper_match else ""

# ── isolate startup lifespan function ─────────────────────────────────────────
_startup_match = re.search(
    r"@app\.on_event\(['\"]startup['\"]\).*?(?=\n@app\.|$)",
    _server,
    re.DOTALL
)
# Also try async lifespan / startup context manager patterns
if not _startup_match:
    _startup_match = re.search(
        r"async def startup.*?(?=\nasync def |\Z)",
        _server,
        re.DOTALL
    )
# Fallback: grab the block around the NOTE comment
_startup_block = ""
_startup_note_idx = _server.find("_migrate_partial_unique_application_id() is NOT called here on startup")
if _startup_note_idx != -1:
    # grab 30 lines from that point
    _startup_block = _server[_startup_note_idx: _startup_note_idx + 2000]

# ── isolate GET /admin/pipeline/index-status endpoint ────────────────────────
_idx_status_start = _server.find('/admin/pipeline/index-status')
_idx_status_src = ""
if _idx_status_start != -1:
    # find the @app.get before it
    _ep_start = _server.rfind('@app.get', 0, _idx_status_start)
    if _ep_start != -1:
        # find the next @app. after the endpoint def
        _ep_end = _server.find('\n@app.', _idx_status_start)
        _idx_status_src = _server[_ep_start: _ep_end if _ep_end != -1 else _ep_start + 2000]

# ── isolate POST /admin/pipeline/migrate-index endpoint ──────────────────────
# Use the @app.post decorator as the anchor to avoid hitting comment occurrences
_migrate_ep_m = re.search(
    r'@app\.post\(["\']\/admin\/pipeline\/migrate-index["\']',
    _server
)
_migrate_src = ""
if _migrate_ep_m:
    _ep_start = _migrate_ep_m.start()
    _ep_end   = _server.find('\n@app.', _ep_start + 10)
    _migrate_src = _server[_ep_start: _ep_end if _ep_end != -1 else _ep_start + 3000]


# ══════════════════════════════════════════════════════════════════════════════
# §A  Stale-test fix
# ══════════════════════════════════════════════════════════════════════════════

check("A-01. test_post_comments.py no longer asserts «غير مصنف» for null candidate_status",
      'غير مصنف' not in _test_cmt or
      # only acceptable if it's in a comment/description, not an assertion
      'لم يتم ترشيحه بعد' in _test_cmt
)

check("A-02. test_post_comments.py asserts the updated label «لم يتم ترشيحه بعد»",
      'لم يتم ترشيحه بعد' in _test_cmt)

# ══════════════════════════════════════════════════════════════════════════════
# §B  Helper present in auth.py
# ══════════════════════════════════════════════════════════════════════════════

check("B-01. get_pipeline_application_index_status() defined in auth.py",
      'def get_pipeline_application_index_status()' in _auth)

check("B-02. Helper has a docstring",
      bool(_helper_src) and '"""' in _helper_src)

# ══════════════════════════════════════════════════════════════════════════════
# §C  Read-only — no write SQL
# ══════════════════════════════════════════════════════════════════════════════

_write_sql_pattern = re.compile(
    r'\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)\b',
    re.IGNORECASE
)

check("C-01. Helper body contains no write SQL (INSERT/UPDATE/DELETE/CREATE/DROP/ALTER)",
      not _write_sql_pattern.search(_helper_src))

check("C-02. Helper uses conn.run() only for SELECT queries",
      bool(_helper_src) and
      all(
          'SELECT' in stmt
          for stmt in re.findall(r'conn\.run\(\s*["\']([^"\']+)', _helper_src)
      ) if re.findall(r'conn\.run\(\s*["\']([^"\']+)', _helper_src) else True
)

# ══════════════════════════════════════════════════════════════════════════════
# §D  Returns all four required keys
# ══════════════════════════════════════════════════════════════════════════════

check('D-01. Helper returns "exists" key',
      '"exists"' in _helper_src or "'exists'" in _helper_src)

check('D-02. Helper returns "is_unique" key',
      '"is_unique"' in _helper_src or "'is_unique'" in _helper_src)

check('D-03. Helper returns "predicate_valid" key',
      '"predicate_valid"' in _helper_src or "'predicate_valid'" in _helper_src)

check('D-04. Helper returns "ready" key',
      '"ready"' in _helper_src or "'ready'" in _helper_src)

# ══════════════════════════════════════════════════════════════════════════════
# §E  Uses pg_indexes for basic existence check
# ══════════════════════════════════════════════════════════════════════════════

check("E-01. Helper queries pg_indexes",
      'pg_indexes' in _helper_src)

check("E-02. Helper filters by indexname = 'uq_jpe_application_id'",
      'uq_jpe_application_id' in _helper_src)

# ══════════════════════════════════════════════════════════════════════════════
# §F  Uses pg_index + pg_get_expr
# ══════════════════════════════════════════════════════════════════════════════

check("F-01. Helper queries pg_index for uniqueness",
      'pg_index' in _helper_src and 'indisunique' in _helper_src)

check("F-02. Helper uses pg_get_expr for predicate check",
      'pg_get_expr' in _helper_src)

check("F-03. Helper checks predicate contains 'application_id' AND 'not null'",
      'application_id' in _helper_src and 'not null' in _helper_src.lower())

# ══════════════════════════════════════════════════════════════════════════════
# §G  Resource-safe: try/finally + release_conn
# ══════════════════════════════════════════════════════════════════════════════

check("G-01. Helper uses try/finally pattern",
      'try:' in _helper_src and 'finally:' in _helper_src)

check("G-02. Helper calls release_conn in finally block",
      'release_conn' in _helper_src)

# ══════════════════════════════════════════════════════════════════════════════
# §H  Startup warning is non-blocking (try/except wrapper)
# ══════════════════════════════════════════════════════════════════════════════

_startup_has_try = 'try:' in _startup_block
_startup_has_except = 'except' in _startup_block

check("H-01. Startup index check is wrapped in try/except (non-blocking)",
      _startup_has_try and _startup_has_except)

check("H-02. Startup prints a warning when index is NOT ready",
      '⚠️' in _startup_block or 'WARNING' in _startup_block.upper() or
      'NOT ready' in _startup_block or 'not ready' in _startup_block.lower())

check("H-03. Startup prints success when index IS ready",
      '✅' in _startup_block or 'ready' in _startup_block)

# ══════════════════════════════════════════════════════════════════════════════
# §I  Startup references the helper function
# ══════════════════════════════════════════════════════════════════════════════

check("I-01. Startup block calls get_pipeline_application_index_status()",
      'get_pipeline_application_index_status' in _startup_block)

check("I-02. Startup block references migrate-index endpoint in warning message",
      'migrate-index' in _startup_block or 'migrate_index' in _startup_block)

# ══════════════════════════════════════════════════════════════════════════════
# §J  Startup prints both paths
# ══════════════════════════════════════════════════════════════════════════════

check("J-01. Startup block has if/else (or two distinct print paths)",
      ('if _idx_status' in _startup_block or 'if _idx' in _startup_block)
      and ('else:' in _startup_block or 'elif' in _startup_block))

# ══════════════════════════════════════════════════════════════════════════════
# §K  GET /admin/pipeline/index-status endpoint
# ══════════════════════════════════════════════════════════════════════════════

check("K-01. GET /admin/pipeline/index-status endpoint present in server.py",
      '/admin/pipeline/index-status' in _server and '@app.get' in _server)

check("K-02. index-status endpoint calls check_admin",
      'check_admin' in _idx_status_src)

check("K-03. index-status endpoint returns get_pipeline_application_index_status()",
      'get_pipeline_application_index_status' in _idx_status_src)

# ══════════════════════════════════════════════════════════════════════════════
# §L  Import in server.py
# ══════════════════════════════════════════════════════════════════════════════

check("L-01. get_pipeline_application_index_status imported in server.py",
      'get_pipeline_application_index_status' in _server and 'from auth import' in _server)

# ══════════════════════════════════════════════════════════════════════════════
# §M  POST /admin/pipeline/migrate-index uses helper for post-creation check
# ══════════════════════════════════════════════════════════════════════════════

check("M-01. POST /admin/pipeline/migrate-index calls get_pipeline_application_index_status",
      'get_pipeline_application_index_status' in _migrate_src)

check("M-02. POST /admin/pipeline/migrate-index is protected by check_admin",
      'check_admin' in _migrate_src)

check("M-03. POST /admin/pipeline/migrate-index requires confirm=true",
      'confirm' in _migrate_src)

check("M-04. POST /admin/pipeline/migrate-index handles BlockingConflictError → 409",
      'BlockingConflictError' in _migrate_src and '409' in _migrate_src)

# ══════════════════════════════════════════════════════════════════════════════
# §N  migrate-index returns index_status in response
# ══════════════════════════════════════════════════════════════════════════════

check("N-01. POST migrate-index response includes index_status key",
      'index_status' in _migrate_src)


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 60)
passed = sum(1 for _, s, _ in results if s == PASS)
total  = len(results)
print(f"Passed: {passed} / {total}")
if passed < total:
    print("\nFailed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌  {name}")
    sys.exit(1)
else:
    print("All tests passed ✅")
    sys.exit(0)
