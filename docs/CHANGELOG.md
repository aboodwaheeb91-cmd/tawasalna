# سجل التحديثات — تواصلنا (CHANGELOG)

> **القاعدة (CLAUDE.md → بروتوكول المهام — البند 13):** تاريخ التعديلات يُكتب كبند جديد هنا فقط (الأحدث فوق، بند لكل PR/تاريخ). ممنوع تطويل سطر "Last updated" بأي ملف — الملفات تحتفظ بسطر واحد قصير: آخر تاريخ + آخر PR + رابط لهذا الملف.
>
> هذا الملف **لا يُقرأ** بكل جلسة — فقط عند الحاجة لتاريخ تغيير معيّن.

## فهرس

- [سجل `docs/SYSTEMS_INDEX.md`](#سجل-docssystems_indexmd)
- [سجل `ARCHITECTURE_FOUNDATION.md`](#سجل-architecture_foundationmd)
- [سجل `docs/design-system/VIEWER-MODES.md`](#سجل-docsdesign-systemviewer-modesmd)
- [سجل `docs/design-system/BUTTONS.md`](#سجل-docsdesign-systembuttonsmd)

## PR-7a — 2026-10-06 — upload security (`POST /upload/image` · `POST /admin/logo`)

- السيرفر: `kind` → bucket map ثابت (`_UPLOAD_KINDS`)، اسم ملف يولّده السيرفر، user_id من الـ JWT فقط، JPEG/PNG/WebP + فحص magic bytes (لا SVG)، حدود حجم 7MB نص / 5MB، لا fallback لـ data URL بالإنتاج (502/503؛ dev فقط بـ `TW_DEV_UPLOAD=1`). `/admin/logo` نفس الفحص.
- الواجهة: `TW.uploadImage({ kind, dataUrl, jwt })` + `TW.uploadErrorText()`؛ المستدعين (profile-v2 avatar/cover · company logo/cover · KYC بـ settings.html · admin logo) ما عاد يحفظوا data URL.
- توثيق: SYSTEMS_INDEX §29a · `docs/rules/upload.md` · `ARCHITECTURE.md → Image Upload Security Contract` · `CLAUDE.md` جدول المتغيرات (`TW_DEV_UPLOAD`). اختبار: `test_upload_security.py`.

## PR-6c — 2026-10-06 — docs: changelog split

- سطر `*Last updated*` بـ `docs/SYSTEMS_INDEX.md` (~22KB) + قسم "التحديثات" بـ `ARCHITECTURE_FOUNDATION.md` + تذييلَي `VIEWER-MODES.md` و`BUTTONS.md` نُقلت حرفياً لهذا الملف؛ كل ملف بقي فيه سطر واحد قصير.
- `CLAUDE.md` بروتوكول المهام: البند 13 (قاعدة هذا الملف).
- إشارات `F1–F35` → `F1–F37` (README.md · docs/SYSTEMS_INDEX.md §30a · docs/CHANGE_ROUTER.md).
- `docs/FUTURE_ROADMAP.md`: بند P2 تعدد اللغات (i18n) + بند manifest.json shortcut.

## سجل `docs/SYSTEMS_INDEX.md`

> منقول حرفياً من سطر `*Last updated: …*` بآخر `docs/SYSTEMS_INDEX.md` (PR-6c). البنود مرتّبة كما وردت بالأصل: الأحدث فوق. البنود بدون تاريخ صريح بالأصل مكتوب عندها "بدون تاريخ" — ترتيبها الزمني حسب موقعها.

### SI-31 · 2026-10-06 — PR-6 / Phase B (DS-ICON)

PR-6 / Phase B (DS-ICON): §56 Icon System V1 added (`static/shared/tw-icons.js` registry — Lucide 0.460 only, 105 UI names + 82 catalog names + one alias table, RTL mirroring for `dir:true`; no consumers, zero visual change; `docs/design-system/ICON-SYSTEM.md` ICON-00–ICON-14; `docs/rules/ds-icon.md`; F37; `test_ds_icon_registry.js`).

### SI-30 · 2026-10-06 — PR-5 / Phase B (DS-SIZE)

PR-5 / Phase B (DS-SIZE): §55 Size System V1 added (`tw_shared.css` section `1b. DS-SIZE` tokens, no consumers, zero visual change; `docs/design-system/SIZE-SYSTEM.md` SIZE-00–SIZE-12; `docs/rules/ds-size.md`; F36); §31 source + DS-SIZE; §39 `tw-ui-tokens.css` → replaced by DS-SIZE.

### SI-29 · 2026-10-06 — PR #544 corrections

PR #544 corrections: legacy page URLs with `?id=N` (existing account, any type) → server 302 `/u/{tw_id}` via the single lookup `_tw_id_for_user_id()` (replaces `_get_co_tw_id`); unknown / non-numeric / no id → redirect page; messages home → `twHomeHref()` for all types; edu-profile `goHome` → `twHomeHref()`; settings `goBack` → `twAccountHref()`.

### SI-28 · 2026-10-06 — PR-4 (dead files & routes cleanup)

PR-4 (dead files & routes cleanup): deleted `profile.html`, `home.html`, `company-profile.js`, `static/home-v2.js`, `profile_showcase.html`, `employees-group.html`, `jobs.html`, `edu.html`, `company.html`, `auto_sync.py`, `.replit`, `test.py`, old QR template; deleted `POST /feedback`, `GET /jobs/match/{user_id}`, `POST /company/posts/{id}/appreciate`; retired page URLs → one legacy redirect page `_LEGACY_REDIRECT_HTML` (Pages Index); `twHomeHref()` → `/home` for all types; `twTalentBankHref()` + empty `?cand=` deep-link; `sanitize()` alias deleted (§54); §33 Auto Sync removed; Systems Needing Documentation pruned.

### SI-27 · 2026-10-06 — PR-3b (docs/claude-md-split)

PR-3b (docs/claude-md-split): per-system rules moved verbatim from `CLAUDE.md` to `docs/rules/*.md`; all Details pointers updated; §20c popover = 2 info rows + pipeline actions row (matches `_showJobChipPop`); §30a Do-not-recreate allows `docs/rules/`.

### SI-26 · 2026-10-06 — PR-3 (docs/protocol-conflicts)

PR-3 (docs/protocol-conflicts): §30a updated (Rule Index F1–F35 + CLAUDE.md Task Protocol); §16 CV Matching removed (`POST /match` no longer exists in `server.py`); §20c popover = 2 rows (matches `_showJobChipPop`); §29b company-logo shape → circle (matches `openLogoCrop`); §31 source → DS-COLOR in `tw_shared.css`; §25 Safe Rendering ref §39 → §54.

### SI-25 · 2026-10-06 — §32 Service Worker / PWA fully documented (security/sw-cache-allowlist)

2026-10-06 — §32 Service Worker / PWA fully documented (security/sw-cache-allowlist): blocklist → allowlist, no API/Authorization caching, session-end cache wipe via `twClearAppCaches()`, BUILD_TIME bump rule; removed from Systems Needing Documentation.

### SI-24 · 2026-08-05 — §53 updated (VM-10 Phase 3 ✅)

2026-08-05 — §53 updated (VM-10 Phase 3 ✅): Badge Race Prevention contract expanded (`_badgeGeneration` + `_guardOk()` triple-guard + `_on401()` sibling-cancel + `_bindBadgeAuthSync()` idempotent binding + `data-ah-notif-badge` support). `test_ws_client.mjs` harness fixed (extraction marker changed from `// ══ Global Real-time Badge WebSocket ══` → `// ══ Global Badge Loader ══` to include `_badgeGeneration` in scope — 42/42 tests passing T24–T34). `test_tw_shared_runtime.js` extended to 55 tests (+5 for index.auth.js login path storage contract T15–T16b). `test_global_ui_visibility.py` extended to 154 checks (+M07/M08 repo-wide `Object.keys(localStorage)` + `startsWith('tw_')` guards, +M09 no `setInterval` badge polling in `static/**`). `company-profile.js` (legacy superseded root file) `doLogout()` fixed: `Object.keys(localStorage).filter(startsWith('tw_'))` → `_LOGOUT_KEYS` allowlist. Total test suite: 154 Python + 55 JS runtime + 42 WS client + 54 auth-sync = 305 VM-10 tests. `test_login_ds.py`: NOT RUN — server not available (requires live http://127.0.0.1:8000).

### SI-23 · 2026-07-26 — §50 updated (DS-COLOR Phase 2 🔄 — Index/Auth migration ✅)

2026-07-26 — §50 updated (DS-COLOR Phase 2 🔄 — Index/Auth migration ✅): `index.css` fully migrated. Auth Local Color Roles block (`--auth-*`, CLR-15 Tier 3, 34 tokens). System Gap resolved: `--color-surface-input` added to `tw_shared.css` Section B. `index.ui.js` password strength: raw hex → CSS var strings. Non-CSS Color Mirror note added to CLAUDE.md + INPUT-FIELDS.md `--color-surface-input` contract added. CLR-34 changelog updated. Zero visual change (CLR-27).

### SI-22 · بدون تاريخ — §50 updated (DS-COLOR Phase 1 ✅)

§50 updated (DS-COLOR Phase 1 ✅): `tw_shared.css` Runtime Tokens Foundation added. Three-section `:root` block: Section A (Foundation/Primitive — 9 hue primitives + 5 RGB channels), Section B (Semantic — 30 tokens: Brand/Surface/Border/Text/Status/Categorical + 6 RGB channels), Section C (Legacy Aliases — all 16 legacy names → Semantic targets). Consumer audit: --t3 → --color-text-muted safe; --t4 raw kept (mixed consumers, mapping deferred Phase 2); purple confirmed (profile-v2/messages/company/home-v2) → --color-brand-accent added. Zero visual change verified. company.css not touched (CLR-16, separate PR). CLR-30 checklist: all items complete. CLR-34 changelog updated. SYSTEMS_INDEX.md §50 status: Phase 1 ✅

### SI-21 · 2026-07-26 — §50 added (Color System V1 [DS-COLOR])

2026-07-26 — §50 added (Color System V1 [DS-COLOR]): `docs/design-system/COLOR-SYSTEM.md` created and refined (CLR-00–CLR-34, 35 sections). ARCHITECTURE_FOUNDATION.md updated: F35 (Color System DS-COLOR) added; F31 routing table row for color token/`--color-*`/palette added. DESIGN_SYSTEM.md updated: DS-COLOR Quick Route added, DS-COLOR added to main Systems Table, DS-COLOR added to Implementation Status, DS-COLOR Runtime note added. CLAUDE.md updated: DS-COLOR mandatory rules section added. Total systems: 50.

### SI-20 · 2026-07-24 — §49 added (Operational Feedback System V1 [DS-FEEDBACK])

2026-07-24 — §49 added (Operational Feedback System V1 [DS-FEEDBACK]): `docs/design-system/FEEDBACK-SYSTEM.md` created (FBK-00–FBK-29, 30 sections). ARCHITECTURE_FOUNDATION.md updated: F34 (Operational Feedback System DS-FEEDBACK) added; F31 routing table row for Toast/Snackbar/Operational Feedback added. DESIGN_SYSTEM.md updated: DS-FEEDBACK Quick Route updated (removed STOP), DS-FEEDBACK moved from future-systems table to main Systems Table, DS-FEEDBACK added to Implementation Status, DS-FEEDBACK Runtime note added. Total systems: 49.

### SI-19 · 2026-07-24 — F31 تعارض Routing أُصلح

2026-07-24 [routing fix] — F31 تعارض Routing أُصلح: Popover حُذف من صف DS-OVL في ARCHITECTURE_FOUNDATION.md (OVL-00 + OVL-37 يُحددانه خارج DS-OVL V1)؛ صف Tooltip/Popover/Floating label/Context menu → STOP أُضيف لـ F31 + DESIGN_SYSTEM.md Quick Routes. لا تغيير على §48 — النص الصحيح مسبقاً.

### SI-18 · 2026-07-24 — §48 added (Overlay System V1 [DS-OVL])

2026-07-24 — §48 added (Overlay System V1 [DS-OVL]): `docs/design-system/OVERLAY-SYSTEM.md` created (OVL-00–OVL-37, 38 sections). ARCHITECTURE_FOUNDATION.md updated: F33 (Overlay System DS-OVL) added; F31 routing table row for Overlay/Modal/Drawer added. DESIGN_SYSTEM.md updated: DS-OVL Quick Route updated (removed STOP), DS-OVL moved from future-systems table to main Systems Table, DS-OVL added to Implementation Status, DS-OVL Runtime note added. Total systems: 48.

### SI-17 · 2026-07-23 — §47 added (Date & Time Fields System V1 [DS-DATE])

2026-07-23 — §47 added (Date & Time Fields System V1 [DS-DATE]): `docs/design-system/DATE-TIME-FIELDS.md` created (DATE-00–DATE-35, 36 sections). ARCHITECTURE_FOUNDATION.md updated: F32 (Date & Time Fields System) added; F31 routing table row for date/time added. DESIGN_SYSTEM.md updated: DS-DATE Quick Routes section added, DS-DATE moved from future-systems table to main Systems Table, DS-DATE added to Implementation Status, DS-DATE Runtime note added. Total systems: 47.

### SI-16 · 2026-07-22 — §46 added (Select & Searchable Picker System V1 [DS-SEL])

2026-07-22 — §46 added (Select & Searchable Picker System V1 [DS-SEL]): `docs/design-system/SELECT-PICKER.md` created (SEL-00–SEL-36, 37 sections). ARCHITECTURE_FOUNDATION.md F31 dropdown routing row updated to reference SELECT-PICKER.md. DESIGN_SYSTEM.md updated: DS-SEL Quick Route added, DS-SEL moved from future-systems table to main Systems Table, DS-SEL added to Implementation Status. §42 DS-INP cross-reference to DS-SEL updated (STOP removed — DS-SEL now documented). Total systems: 46.

### SI-15 · 2026-07-21 — §42–§45 added (Input Fields [DS-INP] · Form Lifecycle [DS-FRM] · Validation & Errors [DS-VAL] · API Mutations [API-MUT])

2026-07-21 — §42–§45 added (Input Fields [DS-INP] · Form Lifecycle [DS-FRM] · Validation & Errors [DS-VAL] · API Mutations [API-MUT]): docs/design-system/INPUT-FIELDS.md (INP-00–INP-16) · docs/design-system/FORM-LIFECYCLE.md (FRM-00–FRM-25) · docs/design-system/VALIDATION-ERRORS.md (VAL-00–VAL-20) · docs/contracts/API-MUTATIONS-ERRORS.md (API-MUT-00–API-MUT-18) created. ARCHITECTURE_FOUNDATION.md updated: F29 (One Concept = One Source of Truth Form & UI) · F30 (No Matching System = Stop and Report) · F31 (System Routing Before Implementation). DESIGN_SYSTEM.md updated: 20+ new Quick Routes + 4 new Systems Table entries + 11 future system placeholders. Total systems: 45.

### SI-14 · 2026-07-20 — §41 added (Navigation System V1 [DS-NAV])

2026-07-20 — §41 added (Navigation System V1 [DS-NAV]): docs/design-system/NAVIGATION.md created (13 sections NAV-00–NAV-12). Unified Back Contract: 5-step behavioral priority (Layer Close → Internal Nav State → Trusted Tawasolna Context → Contextual Canonical Fallback → Global Fallback). history.length > 1 removed as trust signal. ?next= scoped to Auth Return Destination only. Platform Back = Back Intent (behavioral contract, not implementation-specific). Layer Stack reconciliation: top-down LIFO diff between current and target stacks. Safe Fallback Map: account-type-aware (emp/co/edu/guest). BTN-12 rule 6 added (Back = button + back-trust check → NAV-05). docs/DESIGN_SYSTEM.md updated (DS-NAV entry + 4 navigation Quick Routes).

### SI-13 · 2026-07-20 — §40 added (docs/design-system Viewer Modes & Permissions System V1 [DS-VM])

2026-07-20 — §40 added (docs/design-system Viewer Modes & Permissions System V1 [DS-VM]): VIEWER-MODES.md created (VM-00–VM-09). Three viewer modes: Owner/Registered User/Guest. Formal separation: Authentication vs Authorization vs Ownership vs Visibility. Backend as final authority. Frontend Visibility = UX only. Compatible with window._scViewerType (Profile V2) + companyState.permissions.isOwner (Company Profile). Forbidden: localStorage as auth source, hiding UI instead of securing endpoint, sending private data then hiding it client-side. §39 updated: BTN-17 Visibility & Permission Contract added to BUTTONS.md (7 mandatory fields per permission-dependent button). DESIGN_SYSTEM.md updated: [DS-VM] added to Systems Table + 4 new Quick Routes for permission/viewer-mode tasks + Implementation Status updated.

### SI-12 · بدون تاريخ — §39 added (docs/design-system Button System V1)

§39 added (docs/design-system Button System V1): Tawasolna Design System V1 foundation documentation created. docs/DESIGN_SYSTEM.md (index/router). docs/design-system/BUTTONS.md (16 sections BTN-00–BTN-16: routing, base contract, semantic types, size/layout, groups, icon buttons, interaction states, no-text-selection, action save lifecycle, toggle save lifecycle, full lifecycle contract, navigation semantics, dangerous actions, performance, exception, forbidden patterns). CSS implementation layer (tw-ui-tokens.css) NOT created — planned only.

### SI-11 · بدون تاريخ — §38 updated (PR-6 Applicants vs Candidates Split)

§38 updated (PR-6 Applicants vs Candidates Split): promoted_at TIMESTAMPTZ NULL added to job_pipeline_entries as Candidate Membership Marker; _migrate_applicants_candidates_split() idempotent migration + evidence-based backfill via pipeline_stage_events; promote_application_to_shortlist stamps promoted_at = COALESCE(promoted_at, NOW()) inside existing atomic transaction; get_job_applicants() extended with view/page/limit params (limit clamped 1–100); GET /jobs/{job_id}/applicants extended with view validation + legacy backward compat (no view → {applicants:[...], count:N}); ARCHITECTURE.md §70 added; 20 tests in test_applicants_candidates_split.py all passing.

### SI-10 · 2026-07-17 — §23 + §38 updated (PR-5 second correction round)

2026-07-17 — §23 + §38 updated (PR-5 second correction round): Path A exception handler narrowed (only PipelineEntryRequiredError swallowed — PipelineApplicationConflictError + ValueError now propagate); ambiguous payload guard added (application_id + candidate_id + job_id → 400 ambiguous_appointment_context); create_pipeline_appointment dead code removed from auth.py; test count 40→41 (Group G test_41 added for ambiguous payload); all 8 skipTest removed; test_40 assertion corrected to use r2.text (global exception_handler wraps HTTPException as {"error":"..."}).

### SI-09 · 2026-07-17 — §23 updated (PR-5 correction round)

2026-07-17 — §23 updated (PR-5 correction round): POST /company/appointments/pipeline removed → unified POST /api/appointments Path B; GET /jobs/{job_id}/applicants/v2 removed → GET /jobs/{job_id}/applicants extended additively; _resolve_pipeline_entry DB-authoritative (PipelineApplicationConflictError 409 on conflict); strict ISO timezone + no hybrid mode; 40 tests (up from 30); ARCHITECTURE.md §69 corrected. §38 updated (PR-5 correction round): test count 30→40; forbidden patterns extended; docs updated.

### SI-08 · 2026-07-17 — §38 updated (PR-4 Talent Bank V2 UI + General Talent Management)

2026-07-17 — §38 updated (PR-4 Talent Bank V2 UI + General Talent Management): follow_up_status column + CHECK constraint added; rating/priority/tags/follow_up_at/follow_up_status CRUD in update_company_saved_candidate; 4 new filter params (priority/min_rating/tag/save_source_filter); 2 new sorts (rating_desc/priority_asc); UpdateSavedCandidateInput extended; GET /company/saved-candidates validation extended; V2 card UI (compact with priority badge, stars, tags chips, follow-up strip); V2 manage panel (7 sections incl. stars widget, priority picker, tag editor, follow-up date+status, read-only source); quota bar "X من 25"; _savedPriority/_savedMinRating/_savedTag/_savedSaveSource state vars; 45 tests (test_talent_bank_v2.py) all passing; ARCHITECTURE.md §68 added.

### SI-07 · 2026-07-16 — §38 updated (PR-3 Applicant Flow Separation + Atomic Talent Bank Quota)

2026-07-16 — §38 updated (PR-3 Applicant Flow Separation + Atomic Talent Bank Quota): TALENT_BANK_FREE_LIMIT=25; TalentBankLimitError; save_company_candidate rewritten (advisory lock + SELECT-first + no CCJR/pipeline writes); idempotent re-save bypasses quota; GET /company/saved-candidates/quota endpoint; POST handler 409 JSONResponse (talent_bank_limit_reached); save_source server-side only; two separate frontend buttons (ترشيح للوظيفة + حفظ في بنك المواهب); "حفظ وتصنيف" removed; 62 tests in test_talent_bank_quota.py; ARCHITECTURE.md §67 added.

### SI-06 · 2026-07-16 — §38 updated (PR-2 Bnd-R2-1–Bnd-R2-8 second correction round)

2026-07-16 — §38 updated (PR-2 Bnd-R2-1–Bnd-R2-8 second correction round): _pipeline_build_conflict_report() unified helper added (all 8 blocking types + informational); _BLOCKING_CONFLICT_TYPES frozenset added; missing_job/missing_candidate/missing_company/candidate_not_employee promoted to blocking; stage_source_disagreement definition corrected (CCJR.candidate_status vs JA.status, not pipeline entry vs JA); source normalization added for already-matched entries in _pipeline_upsert_entry; initial_event_reason='application_status_changed' added to update_application_status; update_candidate_job_status rewritten to lock CCJR FOR UPDATE first (returns False if not found); candidate.action='unchanged' added to promote_application_to_shortlist response; _migrate_partial_unique_application_id verification upgraded to pg_index+pg_get_expr (indisunique + IS NOT NULL predicate); admin HTTP tests added (27 tests in test_pipeline_backfill_http.py); integration tests §43–§47 added (135 total); static tests §M added (129 total).

### SI-05 · 2026-07-16 — §38 updated (PR-2 Bnd-1–Bnd-12 correction round)

2026-07-16 — §38 updated (PR-2 Bnd-1–Bnd-12 correction round): BlockingConflictError class added; _pipeline_upsert_entry gains initial_event_reason param + source='application' on link; 8-category conflicts_by_type with LEFT JOINs in pipeline_backfill_dry_run; blocking_conflicts is bool not count; atomic blocking check inside advisory lock in run_pipeline_backfill; NULL CCJR fallback removed — now does per-row job_applications lookup (null_ccjr_without_application conflict if not found); Pass-2 DO UPDATE now sets source='application'; Pass-3 now preserves legacy created_at and uses created_by=NULL; promote_application_to_shortlist Option B (no csc writes, SELECT-only for general_status); update_candidate_job_status gains ensure-entry + None handling + ValueError; apply_job created_by=user_id (not company_id) + initial_event_reason='application_submitted'; standardised reason values documented; _migrate_partial_unique_application_id hardened (advisory lock, recheck, BlockingConflictError, pg_indexes verify); admin endpoints use JSONResponse(409) not HTTPException for BlockingConflictError; static tests 73→108, integration tests 82→123 (§28–§42 new).

### SI-04 · 2026-07-15 — §38 corrected (PR-1 final corrections)

2026-07-15 — §38 corrected (PR-1 final corrections): FK behaviors corrected (CASCADE/CASCADE/RESTRICT not RESTRICT/all); column renames documented (reason not note, created_by not author_id, stage_updated_at/by not moved_at/by); priority values corrected to low/medium/high only (normal/urgent removed); index name corrected to idx_jobs_company_not_archived_created; body CHECK constraints added to notes tables; 68 PostgreSQL integration tests (test_pipeline_integration.py) added; forbidden patterns expanded. — §38 added (PR-1 Additive Pipeline Schema): Employment Pipeline System schema foundation — 7 additive changes: jobs.archived_at/archived_by, job_pipeline_entries, pipeline_stage_events, pipeline_notes, candidate_bank_notes, company_saved_candidates (rating/priority/tags/follow_up_at/save_source), appointments.pipeline_entry_id. _migrate_pipeline_schema_v1() in auth.py. ARCHITECTURE.md §66 added. 25 tests (pr-1-01 through pr-1-10e) in test_post_comments.py. No endpoints, no frontend, no backfill, no behaviour change.

### SI-03 · 2026-07-11 — §23a added (PR feat/company-communication-hub)

2026-07-11 — §23a added (PR feat/company-communication-hub): Company Communication Hub — owner-only "التواصل والمواعيد" button in company-profile.html; hub IIFE in company.main.js; loadCompanyAppointments() in company.api.js; .co-hub-* CSS in company.css. No new backend/WebSocket/tables. §180 added (4 static checks). Security review deferral note added to FUTURE_ROADMAP.md §Security. — §37 updated (PR scheduler-s3-runner): S3 Runner + Secure Endpoint مكتملة — `run_due_scheduler_jobs()` في `auth.py` (FOR UPDATE SKIP LOCKED، two-phase transaction، retry/exhaustion). `POST /internal/run-due-jobs` في `server.py` (X-Scheduler-Secret، hmac.compare_digest، SCHEDULER_SECRET env var). §177 added (33 static checks). S4 hooks مؤجلة. — §37 updated (PR scheduler-s2-helper): S2 Helper مكتملة — `schedule_job()` idempotent INSERT في `auth.py`. §176 added (26 static checks). — §37 updated (PR scheduler-s1-schema): S1 Schema مكتملة — `_migrate_scheduler_jobs()` في `auth.py`. §175 added (33 static checks). — §37 updated (PR scheduler-s0-tooling-decision): S0 Tooling Decision مكتمل — قرار: External Cron + Secure Endpoint (X-Scheduler-Secret) + scheduler_jobs DB storage. APScheduler مرفوض. §174 added (20 static checks). No code/schema/endpoints. — §37 added (PR scheduler-infrastructure-decision): Scheduler Infrastructure — docs/SCHEDULER_PLAN.md created; Architecture Decision Document (docs-only); deferred features: appointment_reminder, appointment_deadline_expire, appointment_missed, job_expiring_soon; Proposed schema: scheduler_jobs table (dedupe_key UNIQUE, locked_at, locked_by, attempts, last_error); Recommended: Option D (DB-driven) + Option A (External Cron). §173 added (20 static checks). No code/schema/endpoints — docs-only. — §23 updated (PR #460): Appointments Phase 1 Schema implemented. 4 tables: appointments, appointment_participants, appointment_events, appointment_messages. FK + 14 indexes. Migration: _migrate_appointments() in auth.py. Status: Phase 1 ✅ / Phase 2–8 pending. §169 checks updated to reflect Phase 1 completion.

### SI-02 · بدون تاريخ — §23 added (PR #459)

§23 added (PR #459): Appointments & Interview Rooms System — Phase 0 Architecture Documented. docs/APPOINTMENTS_PLAN.md created (15 sections). No code/schema/frontend implemented — docs-only. Scheduler reminders deferred to Phase 8. Related: §14 Jobs, §15 Applications, §18 Messaging, §19 Notifications.

### SI-01 · بدون تاريخ — PR #386–#430 (سجل مجمّع قديم)

reflects systems as of PR #386–#430 (pending).

- §22c updated (PR #400): 6-arg _renderCommentBody, multi-mention via junction table, atomic transaction, _cmtMentionedCandidates array, full-text @mention scan, backward compat.
- §29a added (PR #402): shared upload client TW.uploadImage() in static/shared/tw-upload.js.
- §29b added (PR #403, docs-only) then fully implemented (PR #404–#408): Image Cropper System — tw-image-cropper.js built and wired to all 4 image types (employee-avatar, employee-cover, company-logo, company-cover).
- §29b updated (PR #409): status changed from planned to Implemented & Stable.
- §30a added (PR #420): Architecture Foundation — ARCHITECTURE_FOUNDATION.md created; 28 foundation rules (F1–F28); linked from ARCHITECTURE.md and CLAUDE.md.
- §35 added (PR #424): Skeleton Loading CSS — static/shared/tw-skeleton.css + co-loading mechanism for company-profile + sc-loading skeleton blocks for profile-showcase. No placeholder text in HTML.
- §30b added (PR #428–#429): Future Roadmap — docs/FUTURE_ROADMAP.md created as project Backlog/Roadmap file, updated with 11 Profile System ideas.
- §19 updated + §36 added (PR #430): Notifications Full Delivery Plan — docs/NOTIFICATIONS_PLAN.md created; Phase 0 audit complete; 6 security bugs identified (S1–S6); 12-phase plan (Phase 0–11).
- §19 + §36 updated (PR #441): Notifications V1 Final QA + Closure — Phases 0–10 all complete (PRs #431–#440); Phase 11 deferred; Notifications V1 Status table added to NOTIFICATIONS_PLAN.md; test 139q fixed.
- §19 + §36 updated (PR #447): Notifications V2 Smart Aggregation Plan (V2-0) — docs only; Follow/JobApp/Comment/Reply aggregation types; Click Target Rules; Option A (aggregate while unread); Helper proposal; V2 Phases V2-0 to V2-6 documented; no implementation started.
- §19 updated (PR #455): Missing Priority Queue P1 — application_status_changed hook implemented in update_application_status (auth.py); actor_id param added; self-guard; per-status title/body (accepted/rejected/viewed/fallback); event_key `application_status:{app_id}:{status}`; link=/job-detail; exception logging F9-compliant. server.py call site updated.
- §165 added (44 static checks).
- §19 + §30b updated (PR #456): Policy correction — accepted/rejected are internal company states, no direct notification to applicant. Appointments & Interview Rooms System documented in FUTURE_ROADMAP.md §15 (11 subsections). Next Phase Marker updated to rating notification hook.
- §166 added (38 static checks).
- §19 updated (PR #457): rating_received hook in rate_company() — type_=rating_received, event_key=rating:{company_id}:{rater_id}, link=/u/{tw_id}, individual, F9 logging. Missing Priority Queue: app_status + rating ✅. Remaining: job_expiring_soon (Blocked).
- §167 added (45 static checks).

## سجل `ARCHITECTURE_FOUNDATION.md`

> منقول حرفياً من نهاية `ARCHITECTURE_FOUNDATION.md` (قسم "التحديثات"). الأحدث فوق.

- AF-11 · حُدِّث في PR-6 / المرحلة B (DS-ICON) — 2026-10-06 — أُضيفت القاعدة F37: Icon System (DS-ICON). فهرس القواعد: سطر F37. F31 جدول التوجيه: صف أيقونة واجهة / SVG / `data-lucide` / emoji كأيقونة → `docs/design-system/ICON-SYSTEM.md`. المجموع: 37 قاعدة عليا.
- AF-10 · حُدِّث في PR-5 / المرحلة B (DS-SIZE) — 2026-10-06 — أُضيفت القاعدة F36: Size System (DS-SIZE). فهرس القواعد: سطر F36. F31 جدول التوجيه: صف font-size/radius/spacing/icon/control height → `docs/design-system/SIZE-SYSTEM.md`. المجموع: 36 قاعدة عليا.
- AF-09 · حُدِّث في PR-3 (docs/protocol-conflicts) — 2026-10-06 — أُضيف "فهرس القواعد" (F1–F35 بسطر واحد لكل قاعدة) بأول الملف بدلاً من جدول "القواعد العليا" (نفس الأرقام والأولويات)؛ سطر "إلزامي القراءة" عُدِّل ليطابق بروتوكول المهام (CLAUDE.md البند 1). لم يتغيّر نص أي قاعدة.
- AF-08 · حُدِّث في PR #520 (DS-COLOR Phase 1 Final Documentation Sync) — 2026-07-26 — F35 قاعدة 9 حُدِّثت: Phase 0 ✅ + Phase 1 ✅ (Runtime Tokens Foundation مكتمل). ممنوعات F35 حُدِّثت: Phase 1 Runtime restriction أُزيلت (مكتملة)؛ Phase 2 page migration restriction أُضيفت.
- AF-07 · حُدِّث في PR docs/ds-feedback-v1 — 2026-07-24 — أُضيفت القاعدة F34: Operational Feedback System (DS-FEEDBACK). F31 جدول التوجيه: صف Toast/Snackbar/Operational Feedback أُضيف للإشارة إلى `docs/design-system/FEEDBACK-SYSTEM.md`. المجموع: 34 قاعدة عليا.
- AF-06 · حُدِّث في PR docs/ds-ovl-v1 — 2026-07-24 — أُضيفت القاعدة F33: Overlay System (DS-OVL). F31 جدول التوجيه: صف Overlay/Modal/Drawer أُضيف للإشارة إلى `docs/design-system/OVERLAY-SYSTEM.md`؛ تعارض Routing أُصلح: Popover حُذف من صف DS-OVL (OVL-00 + OVL-37 يُصرِّحان أنه خارج DS-OVL V1)؛ صف Tooltip/Popover/Floating label/Context menu أُضيف → STOP. المجموع: 33 قاعدة عليا.
- AF-05 · حُدِّث في PR docs/ds-date-v1 — 2026-07-23 — أُضيفت القاعدة F32: Date & Time Fields System (DS-DATE). F31 جدول التوجيه: صف تاريخ/وقت أُضيف للإشارة إلى `docs/design-system/DATE-TIME-FIELDS.md`. المجموع: 32 قاعدة عليا.
- AF-04 · حُدِّث في PR #508 — 2026-07-22 — F31 جدول التوجيه: صف dropdown/select حُدِّث للإشارة إلى `docs/design-system/SELECT-PICKER.md` بعد توثيق DS-SEL V1 رسمياً — STOP أُزيل من هذا الصف.
- AF-03 · حُدِّث في PR docs/design-system-forms-v1 — 2026-07-21 — أُضيفت القواعد F29–F31: One Concept = One Source of Truth (Form & UI) · No Matching System = Stop and Report · System Routing Before Implementation. المجموع: 31 قاعدة عليا.
- AF-02 · حُدِّث في PR #420 (commit 2) — 2026-07-09 — أُضيفت القواعد F14–F28 (15 قاعدة مستقبلية). المجموع: 28 قاعدة عليا.
- AF-01 · أُنشئ في PR #420 — 2026-07-09 — الدستور المعماري الأساسي لمشروع تواصلنا.

## سجل `docs/design-system/VIEWER-MODES.md`

> منقول حرفياً من تذييل "آخر تحديث" بـ `VIEWER-MODES.md`. الأحدث فوق.

- rev.7 (2026-08-05): Final runtime integrity — preview no-exemption، .catch() generation guard، renderProfile non-owner clear، _isCurrentEduOwner() fail-closed، _applyEduOwnerMode unified، saveEdit() live snapshot، company identity-aware carve-out، tests rewritten with Node.js vm module + @vm-extract markers.
- rev.6 (2026-08-05): إضافة VM-01-BFCACHE — bfcache session revalidation hotfix (PR fix/vm01-bfcache-session-revalidation)؛ Generation guard + edu live guard + Authorization header fix.
- rev.5 (2026-08-04): اعتماد edu-profile.html (6 صفحات مكتملة)؛ إزالة edu-profile.html من _LEGACY_ALLOWED؛ إزالة employees-group.html من _LEGACY_ALLOWED (لا session actions فيها).
- rev.4 (2026-08-04): إضافة VM-10J — Global Site Header Auto-Detection Marker؛ اعتماد home-v2.html (5 صفحات مكتملة).
- rev.3 (2026-08-03): إضافة VM-10 — Global Session UI Visibility System (PR fix/global-ui-visibility-system).
- rev.2: تصحيح VM-01 (Guest بدون localStorage)، VM-02 (admin auth contract مستقل)، VM-05 (Resource Identifiers vs identity claims)، VM-06 (JWT ليس مطلقاً + قاعدة البيانات الحساسة إلزامية)، VM-08 (Authentication Contract بدلاً من JWT).
- آخر تحديث: 2026-07-18 — V1: Viewer Modes & Permissions System foundation.
  يُغطي: VM-00 (Routing Protocol) → VM-09 (Forbidden Patterns).
  موثَّق في: docs/DESIGN_SYSTEM.md + docs/SYSTEMS_INDEX.md §40.

## سجل `docs/design-system/BUTTONS.md`

> منقول حرفياً من سطر "آخر تحديث" بـ `BUTTONS.md` (البنود بنفس ترتيب الأصل).

- 2026-07-26 — BTN-18 Loading Indicator Alignment Contract (fix/spinner-centering: margin-based centering, no transform conflict) — Button System V1 rev.2 (corrections: BTN-01 STOP rule, BTN-02 outlined/glow visual, BTN-03 semantic color clarification, BTN-04 slim principle + existing constraints, BTN-05 vertical stack rules, BTN-06 borderless header icons, BTN-07 full states list, BTN-08 touch-callout, BTN-09 correct save lifecycle, BTN-10 backend-confirmed toggle, BTN-11 full checklist, BTN-13 context-based confirmation, BTN-14 glow performance, BTN-15 owner-request-only, BTN-16 expanded)
- BTN-17 Visibility & Permission Contract (links to VIEWER-MODES.md)
- BTN-17 VM-10 Extension (2026-08-03): applies to links + dropdown items + header icons, not just buttons.
