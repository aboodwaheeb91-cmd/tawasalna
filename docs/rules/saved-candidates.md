# Saved Candidates — المرشحون المحفوظون

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Saved Candidates — Three Sources of Truth (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

The saved candidates system has **three independent status sources**. Never conflate them, never auto-copy between them:

1. **`job_applications.status`** — application lifecycle status tracking the candidate's progress through a job's hiring pipeline (`pending / viewed / accepted / contacted / interview / hired / rejected`). The company manages transitions; it is NOT purely applicant-driven. Writers: `update_application_status()` (general transitions) AND `promote_application_to_shortlist()` (atomically sets to `'accepted'`). `PATCH /company/saved-candidates/{id}` is NOT the entry point for this.
2. **`company_saved_candidates.status`** — general pipeline classification (one per company-candidate pair). Allowed values: `saved / shortlisted / contacted / interview / hired / rejected` (via `VALID_CANDIDATE_STATUSES`). Writers: `update_company_saved_candidate()` via `PATCH /company/saved-candidates/{id}` AND `promote_application_to_shortlist()` (creates or upserts record, sets to `'shortlisted'` unless already at a higher pipeline stage).
3. **`company_candidate_job_refs.candidate_status`** — per-job classification of the candidate (one per company-candidate-job triple). Same allowed values as source 2 (`VALID_CANDIDATE_STATUSES`). Writers: `update_candidate_job_status()` via `PATCH /company/saved-candidates/{id}/jobs/{job_id}` AND `update_application_status()` (atomically maps app status → candidate_status via `_APP_TO_CANDIDATE_STATUS`) AND `promote_application_to_shortlist()` (sets to `'shortlisted'`). NULL = not yet classified.

**Applicant Classification Sync carve-out (feat/applicant-classification-sync):** `update_application_status()` intentionally writes BOTH `job_applications.status` (source 1) AND `company_candidate_job_refs.candidate_status` (source 3) in a single atomic transaction. This is a deliberate business operation (classify from the applicants screen syncs both sources) — NOT auto-copying. The mapping is one-way only via `_APP_TO_CANDIDATE_STATUS` dict: `pending/viewed → saved`, `accepted → shortlisted`, `contacted → contacted`, `interview → interview`, `hired → hired`, `rejected → rejected`. **Reverse direction is permanently forbidden:** the Saved Candidates picker (`PATCH /company/saved-candidates/{id}/jobs/{job_id}`) must NEVER write `job_applications.status`. `company_saved_candidates.status` (source 2) is only modified by `promote_application_to_shortlist()` or explicit manage-panel saves — never auto-synced from sources 1 or 3.

**Note:** `VALID_CANDIDATE_STATUSES` applies to sources 2 and 3 only. Source 1 (`job_applications.status`) uses a separate set of lifecycle values and is never validated against `VALID_CANDIDATE_STATUSES`.

**`job_links[]` contract:** `{job_id, title, apply_date, application_status, status (deprecated alias), candidate_status}`. `application_status` is the canonical name. `status` is a backward-compat alias equal to `application_status` — present in all API responses, but **do not use `status` in new code**. The `status` alias will be removed only in an explicit API breaking-change release. Full spec: `docs/SYSTEMS_INDEX.md §20c`.

**`PATCH /company/saved-candidates/{id}/jobs/{jid}` security rules (permanent):**
- JWT only — `company_id` NEVER accepted from frontend.
- NEVER modifies `job_applications.status`.
- NEVER modifies `company_saved_candidates.status`.
- Returns 404 if the `company_candidate_job_refs` row doesn't exist.

**Job chip popover = 2 info rows + 1 pipeline actions row (`_showJobChipPop` in `static/company/company.main.js` — fix/job-chip-pop-simplify, supersedes the 3-row layout of feat/candidate-status-per-job; actions row from PR-5 §69):** Row 1 «حالة المرشح في هذه الوظيفة» = `candidate_status` (`data-cand-status`; null → «لم يتم ترشيحه بعد»). Row 2 «تاريخ التقدم» = `job_links[].apply_date` — shown only when the chip has a real application (`data-app-id` AND `data-apply-date` non-empty). Actions row (`.co-cjp-actions`) — shown **only when the candidate has a pipeline entry for this job** (`data-pe-id` non-empty ← `job_links[].pipeline_entry_id`): button «ملاحظات الوظيفة» (with `(N)` when `data-notes-count` > 0 ← `job_links[].pipeline_notes_count`) → `_openNotesPanel(pe_id)`; button «تحديد موعد» when `data-next-appt-id` is empty → `_openApptModal(...)`, or «فتح الموعد» when `job_links[].next_appointment.id` exists → `/appointment-room?id=`. `application_status` and `company_saved_candidates.status` are NOT shown in this popover (they stay in the `job_links[]` contract and the manage panel). Do NOT re-add حالة الطلب or التصنيف العام rows. Full spec: `docs/SYSTEMS_INDEX.md §20c`.
