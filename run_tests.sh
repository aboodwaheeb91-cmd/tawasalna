#!/usr/bin/env bash
# run_tests.sh — the ONE test runner (PR 6.4). CI (.github/workflows/tests.yml) runs exactly
# this script; run it locally the same way. Spec: docs/SYSTEMS_INDEX.md §54g · CLAUDE.md → Testing & CI.
#
#   ./run_tests.sh            everything (needs PostgreSQL with SSL — see DB below)
#   ./run_tests.sh --no-db    skip the DB tests (they are listed, never silently ignored)
#
# Rules:
#   - Every test_*.py / test_*.js / test_*.mjs (root + tests/) is in EXACTLY ONE list below.
#     A new test file that is in no list fails the run (no silent ignore).
#   - EXCLUDED = needs a live server (:8000) / Playwright / a real account — one line each
#     with the reason. Everything else runs on every PR.
#   - DB tests get a fresh database each (dropped + re-created before every file).
#
# DB: PostgreSQL ≥ 14 with ssl=on (auth.get_conn always connects with SSL, like Supabase),
#     superuser tawasalna_test_user / test_pass_pr1 @ 127.0.0.1:5432 — the URL the
#     integration tests already use. Override with TW_TEST_DB_URL.
# Git: a full clone with origin/main (two tests diff against `git merge-base origin/main HEAD`).
set -u
cd "$(dirname "$0")"

PY="${PYTHON:-python}"
NO_DB=0
[ "${1:-}" = "--no-db" ] && NO_DB=1

# ── Test environment (never production values) ─────────────────────────────
export APP_ENV="${APP_ENV:-development}"
export JWT_SECRET="${JWT_SECRET:-ci-test-jwt-secret-0123456789abcdef0123456789abcdef}"
export PYTHONDONTWRITEBYTECODE=1
DB_URL="${TW_TEST_DB_URL:-postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline}"

# ── Python — run with pytest (test functions / TestCase, no own __main__) ───
PY_PYTEST=(
  test_account_security.py
  test_admin_session_security.py
  test_db_conn_async_safety.py
  test_kyc_docs_migration.py
  test_no_dummy_content.py
  test_safe_link_url.py
  test_server_error_leak.py
  test_supabase_settings.py
  test_upload_security.py
)

# ── Python — run as a script (own checks + exit code) ──────────────────────
PY_SCRIPT=(
  test_admin_safe_rendering.py
  test_app_icons.py
  test_applicants_candidates_split.py
  test_applicants_filters_sort.py
  test_auth_gateway.py
  test_company_save_static.py
  test_ds_size_tokens.py
  test_ds_color_tokens.py
  test_edit_profile_phase1.py
  test_global_ui_visibility.py
  test_header_nav.py
  test_strings_system.py
  test_job_archive_http.py
  test_job_detail_shell.py
  test_landing_shell.py
  test_legacy_routes_cleanup.py
  test_page_shell.py
  test_page_shell_security.py
  test_pipeline_backfill.py
  test_pipeline_backfill_http.py
  test_pipeline_pr6_index_guard.py
  test_post_comments.py
  test_post_save.py
  test_security_admin_jwt.py
  test_talent_bank_polish.py
  test_talent_bank_v3.py
  test_ws_behavioral.py
  test_ws_security.py
  tests/test_modal_a11y.py
)

# ── Python — need a real PostgreSQL ("pytest:" prefix = run with pytest) ────
PY_DB=(
  test_job_archive_integration.py
  test_pipeline_backfill_integration.py
  test_pipeline_integration.py
  test_talent_bank_quota.py
  pytest:test_follow_system.py
  pytest:test_otp_rate_limit_security.py
  pytest:test_pr2b_flow_fixes.py
  pytest:test_schedule_interview.py
)

# ── Node (vm / static — no browser) ────────────────────────────────────────
NODE_TESTS=(
  test_appointments_guard_runtime.js
  test_auth_next_icon_hydrate_runtime.js
  test_auth_sync_runtime.js
  test_ds_icon_registry.js          # its RTL browser part prints SKIP without Playwright
  test_ds_image_runtime.js
  test_ds_overlay_runtime.js
  test_pr2c_session_sockets_runtime.js
  test_schedule_interview_runtime.js
  test_stale_session_entry_runtime.js
  test_sw_cache_allowlist_runtime.js
  test_tw_api_runtime.js
  test_tw_shared_runtime.js
  test_upload_client_runtime.js
  test_vm01_bfcache_runtime.js
  test_ws_api.mjs
  test_ws_client.mjs
)

# ── EXCLUDED — not run in CI (file|reason) ─────────────────────────────────
EXCLUDED=(
  "test_company_save.py|live server :8000 + Playwright + real company account — static twin: test_company_save_static.py"
  "test_ds_feedback.py|Playwright (real Chromium)"
  "test_inp_textcolor_regression.py|live server :8000 + Playwright"
  "test_login_ds.py|live server :8000 + Playwright"
  "test_regbtn_ds.py|live server :8000 + Playwright"
  "test_register_ds.py|live server :8000 + Playwright"
  "test_pipeline_pr5.py|live server :8000 (HTTP via requests) + its DB"
  "test_privacy_boundary.py|live server :8000 (HTTP via requests)"
  "test_talent_bank_tag_pg.py|live server :8000 + COMPANY_JWT of a real account (every test skips otherwise)"
  "test_talent_bank_v2.py|live server :8000 (HTTP via requests) + its DB"
  "test_candidate_job_status_picker_runtime.js|Playwright (real Chromium)"
)

# ── Guard: every test file is in exactly one list ──────────────────────────
listed=$(printf '%s\n' "${PY_PYTEST[@]}" "${PY_SCRIPT[@]}" "${PY_DB[@]#pytest:}" \
                       "${NODE_TESTS[@]}" "${EXCLUDED[@]%%|*}" | sort)
actual=$(ls test_*.py test_*.js test_*.mjs tests/test_*.py 2>/dev/null | sort)
dupes=$(printf '%s\n' "$listed" | uniq -d)
missing=$(comm -13 <(printf '%s\n' "$listed" | sort -u) <(printf '%s\n' "$actual"))
stale=$(comm -23 <(printf '%s\n' "$listed" | sort -u) <(printf '%s\n' "$actual"))
if [ -n "$dupes$missing$stale" ]; then
  [ -n "$missing" ] && echo "✗ test file(s) in no list of run_tests.sh — add to a run list or EXCLUDED (with reason):" && echo "$missing"
  [ -n "$stale" ]   && echo "✗ run_tests.sh lists file(s) that do not exist:" && echo "$stale"
  [ -n "$dupes" ]   && echo "✗ file(s) listed twice:" && echo "$dupes"
  exit 1
fi

FAILED=()
run() {  # run <label> <cmd...>
  local label="$1"; shift
  local log; log=$(mktemp)
  if "$@" >"$log" 2>&1; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label"; echo "──── output: $label ────"; tail -n 60 "$log"; echo "────"
    FAILED+=("$label")
  fi
  rm -f "$log"
}

echo "== Syntax =="
js_files=$(git ls-files '*.js' '*.mjs' | grep -v -E '(^|/)vendor/|\.min\.js$')
run "node --check ($(echo "$js_files" | wc -l | tr -d ' ') JS files)" \
  bash -c 'for f in "$@"; do node --check "$f" || { echo "syntax error: $f"; exit 1; }; done' _ $js_files
run "python syntax (*.py)" \
  bash -c 'for f in $(git ls-files "*.py"); do '"$PY"' -c "import ast,sys; ast.parse(open(sys.argv[1],encoding=\"utf-8\").read(), sys.argv[1])" "$f" || exit 1; done'

echo "== Python (pytest) =="
for t in "${PY_PYTEST[@]}"; do run "$t" "$PY" -m pytest -q -p no:cacheprovider "$t"; done

echo "== Python (script) =="
for t in "${PY_SCRIPT[@]}"; do run "$t" "$PY" "$t"; done

echo "== Python (PostgreSQL) =="
reset_db() {  # drop + re-create the test database (fresh schema per test file)
  "$PY" - "$DB_URL" <<'EOF'
import sys, pg8000.native as pg
from urllib.parse import urlparse
u = urlparse(sys.argv[1]); name = u.path.lstrip("/").split("?")[0]
c = pg.Connection(user=u.username, password=u.password, host=u.hostname,
                  port=u.port or 5432, database="postgres")
c.run(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
c.run(f'CREATE DATABASE "{name}"')
c.close()
EOF
}
if [ "$NO_DB" = 1 ]; then
  for t in "${PY_DB[@]}"; do echo "  - SKIPPED (--no-db): ${t#pytest:}"; done
elif ! reset_db >/dev/null 2>&1; then
  echo "  ✗ PostgreSQL not reachable at $DB_URL"
  echo "    start one (ssl=on, see header) or run ./run_tests.sh --no-db"
  FAILED+=("PostgreSQL unavailable")
else
  export TW_TEST_DB_URL="$DB_URL" OTP_TEST_DB_URL="$DB_URL"
  for t in "${PY_DB[@]}"; do
    reset_db || { FAILED+=("reset_db before $t"); continue; }
    case "$t" in
      pytest:*) run "${t#pytest:}" "$PY" -m pytest -q -p no:cacheprovider -rs "${t#pytest:}" ;;
      *)        run "$t" "$PY" "$t" ;;
    esac
  done
fi

echo "== Node =="
for t in "${NODE_TESTS[@]}"; do run "$t" node "$t"; done

echo "== Excluded (not run here — reason) =="
for e in "${EXCLUDED[@]}"; do echo "  - ${e%%|*} — ${e#*|}"; done

echo
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "✗ ${#FAILED[@]} failed: ${FAILED[*]}"; exit 1
fi
[ "$NO_DB" = 1 ] && echo "⚠ DB tests skipped (--no-db) — CI runs them."
echo "✓ all tests passed"
