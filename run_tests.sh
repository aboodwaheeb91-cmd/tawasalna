#!/usr/bin/env bash
# run_tests.sh — the ONE test runner (PR 6.4). CI (.github/workflows/tests.yml) runs exactly
# this script; run it locally the same way. Spec: docs/SYSTEMS_INDEX.md §54g · CLAUDE.md → Testing & CI.
#
#   ./run_tests.sh            everything (needs PostgreSQL with SSL — see DB below)
#   ./run_tests.sh --no-db    skip the DB tests (they are listed, never silently ignored)
#
# Rules:
#   - Every tests/test_*.py / test_*.js / test_*.mjs is in EXACTLY ONE list below (names are
#     relative to tests/ — PR 3.9b moved every test there). Tests run from the repo root
#     (relative paths = repo files) with PYTHONPATH=repo root (import server / auth).
#     A new test file that is in no list fails the run (no silent ignore).
#   - EXCLUDED = needs a live server (:8000) / Playwright / a real account — one line each
#     with the reason. Everything else runs on every PR.
#   - DB tests get a fresh database each (dropped + re-created before every file).
#
# DB: PostgreSQL ≥ 14 with ssl=on (auth.get_conn always connects with SSL, like Supabase),
#     superuser tawasalna_test_user / test_pass_pr1 @ 127.0.0.1:5432 — the URL the
#     integration tests already use. Override with TW_TEST_DB_URL.
#     Guarded (tools/db_guard.py): never APP_ENV=production, the name must contain "test", and the
#     host must be local unless TW_TEST_DB_ALLOW_REMOTE=1 — checked before anything connects.
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
export SCHEDULER_LOOP=0   # task 6.3 — no internal scheduler loop inside test servers (tests drive the cycle)
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
T=tests
DB_URL="${TW_TEST_DB_URL:-postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline}"

# ── DB safety guard (task 5.0e) — BEFORE any connection / DROP / CREATE DATABASE ──
# Refuses (exit 2): APP_ENV=production · a database name without "test" · a host that is not
# localhost / 127.0.0.1 unless TW_TEST_DB_ALLOW_REMOTE=1. Rules: tools/db_guard.py.
if [ "$NO_DB" = 0 ]; then
  "$PY" tools/db_guard.py "$DB_URL" || exit 2
fi

# ── Python — run with pytest (test functions / TestCase, no own __main__) ───
PY_PYTEST=(
  test_account_security.py
  test_admin_session_security.py
  test_db_conn_async_safety.py
  test_kyc_docs_migration.py
  test_no_dummy_content.py
  test_page_audit.py
  test_changelog_collect.py
  test_company_colors.py
  test_ds_color_gap_tokens.py
  test_safe_link_url.py
  test_server_error_leak.py
  test_supabase_settings.py
  test_upload_security.py
  test_startup_lifecycle.py   # task 5.0f — startup hook still runs after the FastAPI / Starlette upgrade
  test_migration_classification_doc.py   # task 7.6 — §54f Classification line = _startup_migrations() (ast, no fastapi)
)

# ── Python — run as a script (own checks + exit code) ──────────────────────
PY_SCRIPT=(
  test_admin_pages_min.py
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
  test_profile_v2_structure.py
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
  test_ws_session_revoke.py
  test_modal_a11y.py
)

# ── Python — need a real PostgreSQL ("pytest:" prefix = run with pytest) ────
PY_DB=(
  test_job_archive_integration.py
  test_pipeline_backfill_integration.py
  test_pipeline_integration.py
  test_talent_bank_quota.py
  pytest:test_follow_system.py
  pytest:test_otp_rate_limit_security.py
  pytest:test_email_change_kyc_email.py
  pytest:test_email_notify.py
  pytest:test_application_result_notify.py
  pytest:test_password_reset_email.py
  pytest:test_session_version_tokens.py
  pytest:test_admin_user_actions.py
  pytest:test_pr2b_flow_fixes.py
  pytest:test_conversation_policy.py   # task 5.0g — who may message whom + ending a conversation
  pytest:test_register_profiles_unique.py
  pytest:test_terms_acceptance.py     # task terms — required terms consent at registration + /privacy · /terms
  pytest:test_schedule_interview.py
  pytest:test_admin_insights.py       # task 5.3a2 — admin audit log + stats endpoints
  pytest:test_admin_settings.py       # task 4.1 — unified admin settings (gate · validation · applies now · audit)
  pytest:test_admin_settings_security.py  # task 4.2 — security settings (range · applies now · audit marked security)
  pytest:test_content_admin_5a.py     # phase 5a — content.edit (strings · colors · news) · colors narrowed · news window + /news/banner
  pytest:test_entity_map_fixes_50c.py  # task 5.0c — reports by target · KYC badge · admin password · my applications
  pytest:test_admin_jobs.py           # task 5.3j — admin jobs list (every state) + status source + hard delete
  pytest:test_admin_jobs_control.py   # task 5.3j phase 2 — hide / reactivate / extend + #7 + #13
  pytest:test_security_50f.py         # task 5.0f — RLS lockdown · deleted account · org gate · no-sv cutoff · badge once
  pytest:test_audit_fixes_50e.py      # task 5.0e — /log/error · swallowed errors · Google off · soon badges · noindex · DB guard
  pytest:test_input_limits_50h.py     # task 5.0h — input / flood limits: messages · posts · reports · mention search · comment pages
  pytest:test_input_limits_50h2.py    # task 5.0h-2 — message rate · view dedupe · password bytes · login lock IP + email · bounded stores · scheduler unlock
  pytest:test_otp_send_limits_43.py   # task 4.3 — KYC OTP send limits (account · target · IP) + single-instance warning
  pytest:test_public_rate_limit.py   # task 6 — public routes per-IP limit (429 + Retry-After · HTML vs JSON · exempt · structure · settings)
  pytest:test_www_redirect_77.py     # task 7.7 — www.tawasolna.com → tawasolna.com (301 / 308 · Location from a constant · before rate limits · WS untouched)
  pytest:test_support_tickets.py     # task 7.1 — support tickets: ownership · priority admin-only · account / guest / global limits · reopen 14 days · support.manage · audit
  pytest:test_support_guest_link.py  # task 7.2a — guest follow-up link: hash only · same 404 · +90 days · keep=3 · resend · four limits · headers
  pytest:test_support_track_session.py  # task 7.4 — link names the ticket only · code to the stored guest_email · session (hash · 24 h · revoked by resend) · codes never cross · one session per code
  pytest:test_support_reply_notice.py  # task 7.2b — admin reply notice: guest new link keep=3 + email · account bell per message + one SECURITY email · failure keeps 200 · no raw token
  pytest:test_support_inbound.py     # task 7.3 — inbound mail: Svix signature · dedupe · recipients · guest ticket + account hint · Reply-To token + owner From · Auto-Submitted · HTML → text · switch off
  pytest:test_rate_store_54d.py       # task 5.4d — _rate_store: one capped section per kind · login locks never evict other counters · no sort per request
  pytest:test_privacy_boundary_http.py  # task 5.0e — privacy boundary groups A–F + H, in-process (no live server)
  pytest:test_scheduler_reliable_63.py  # task 6.3 — internal loop · advisory lock · stale reset · email retry · /health scheduler
  pytest:test_blocks_suspension.py    # task 5.4 — admin suspension (401 · hidden content · back) + user blocks both ways · applications untouched
  pytest:test_experience_sort_order_49.py  # AUD-P2-49 — experience sort_order backfill / add / tie order / reorder ownership + save-job button gone
)

# ── Node (vm / static — no browser) ────────────────────────────────────────
NODE_TESTS=(
  test_actions_registry_runtime.js
  test_appointments_guard_runtime.js
  test_auth_next_icon_hydrate_runtime.js
  test_auth_sync_runtime.js
  test_company_profile_page_runtime.js
  test_post_card_runtime.js         # task U.2 — TwPostCard = legacy company post card (vm, golden)
  test_company_admin_runtime.js     # PR 4.3c — company edit save / applicants / rating (vm)
  test_ds_icon_registry.js          # its RTL browser part prints SKIP without Playwright
  test_ds_image_runtime.js
  test_ds_overlay_runtime.js
  test_admin_email_inbound_runtime.js   # task 7.3a — «استقبال بريد الدعم» switch: own card · off unless true · on asks warn.inbound_on · off no warning (vm)
  test_admin_shell_runtime.js       # task 5.3a — Admin Shell: menu registry · confirm gate · 401 → login (vm)
  test_news_banner_runtime.js       # phase 5b — news banner: null / failed → nothing · text only · safe link · close per id (vm)
  test_header_hidden_runtime.js     # real headless Chrome (ubuntu-latest google-chrome); SKIP locally without one
  test_login_jobdetail_runtime.js
  test_messages_page_runtime.js
  test_notifications_page_runtime.js
  test_home_landing_runtime.js
  test_pr2c_session_sockets_runtime.js
  test_schedule_interview_runtime.js
  test_session_change_stale_runtime.js   # task 5.0b — stale profile reply · job-detail session reload (vm)
  test_settings_edu_runtime.js
  test_stale_session_entry_runtime.js
  test_support_pages_runtime.js     # task 7.2a واجهة — /support FAQ search · «لم تُحلّ» → category + faq_id · guest account only · track hash cleared · no innerHTML (vm)
  test_sw_cache_allowlist_runtime.js
  test_tw_api_runtime.js
  test_tw_shared_runtime.js
  test_upload_client_runtime.js
  test_vm01_bfcache_runtime.js
  test_ws_api.mjs
  test_ws_client.mjs
  test_ws_session_revoke_client_runtime.js
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
  "test_privacy_boundary.py|live server :8000 (HTTP via requests) — HTTP groups A–F + H run in CI as test_privacy_boundary_http.py; static / mock groups G, I–L not ported (task 5.0e F30)"
  "test_talent_bank_tag_pg.py|live server :8000 + COMPANY_JWT of a real account (every test skips otherwise)"
  "test_talent_bank_v2.py|live server :8000 (HTTP via requests) + its DB"
  "test_candidate_job_status_picker_runtime.js|Playwright (real Chromium)"
)

# ── Guard: every test file is in exactly one list ──────────────────────────
listed=$(printf '%s\n' "${PY_PYTEST[@]}" "${PY_SCRIPT[@]}" "${PY_DB[@]#pytest:}" \
                       "${NODE_TESTS[@]}" "${EXCLUDED[@]%%|*}" | sort)
actual=$(cd "$T" && ls test_*.py test_*.js test_*.mjs 2>/dev/null | sort)
root_left=$(ls test_*.py test_*.js test_*.mjs *.test.js 2>/dev/null)
if [ -n "$root_left" ]; then
  echo "✗ test file(s) outside tests/ — move them to tests/:"; echo "$root_left"; exit 1
fi
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
FAILED_MSG=()
run() {  # run <label> <cmd...>
  local label="$1"; shift
  local log; log=$(mktemp)
  if "$@" >"$log" 2>&1; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label"; echo "──── output: $label ────"; tail -n 60 "$log"; echo "────"
    FAILED+=("$label")
    # first error line of this file → the summary at the end
    local first
    first=$(grep -m1 -E '❌|✗|^[[:space:]]*FAIL|FAILED|^E[[:space:]]|^[A-Za-z]*Error:|^>[[:space:]]|not ok' "$log" || tail -n 1 "$log")
    FAILED_MSG+=("$(printf '%s' "$first" | tr -d '\r' | cut -c1-200)")
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
for t in "${PY_PYTEST[@]}"; do run "$t" "$PY" -m pytest -q -p no:cacheprovider "$T/$t"; done

echo "== Python (script) =="
for t in "${PY_SCRIPT[@]}"; do run "$t" "$PY" "$T/$t"; done

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
  FAILED_MSG+=("not reachable at $DB_URL")
else
  export TW_TEST_DB_URL="$DB_URL" OTP_TEST_DB_URL="$DB_URL"
  for t in "${PY_DB[@]}"; do
    reset_db || { FAILED+=("reset_db before $t"); FAILED_MSG+=("could not reset the test database"); continue; }
    case "$t" in
      pytest:*) run "${t#pytest:}" "$PY" -m pytest -q -p no:cacheprovider -rs "$T/${t#pytest:}" ;;
      *)        run "$t" "$PY" "$T/$t" ;;
    esac
  done
fi

echo "== Page audit (tools/page_audit.py — every number only goes down) =="
run "page_audit.py vs tools/page_audit_baseline.json" "$PY" tools/page_audit.py
run "changelog.d fragments (tools/changelog_collect.py --check)" "$PY" tools/changelog_collect.py --check

echo "== Node =="
for t in "${NODE_TESTS[@]}"; do run "$t" node "$T/$t"; done

echo "== Excluded (not run here — reason) =="
for e in "${EXCLUDED[@]}"; do echo "  - ${e%%|*} — ${e#*|}"; done

echo
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "══ Summary: ${#FAILED[@]} failed ══"
  for i in "${!FAILED[@]}"; do echo "  ✗ ${FAILED[$i]} — ${FAILED_MSG[$i]}"; done
  exit 1
fi
[ "$NO_DB" = 1 ] && echo "⚠ DB tests skipped (--no-db) — CI runs them."
echo "✓ all tests passed"
