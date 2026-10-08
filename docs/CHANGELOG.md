# سجل التحديثات — تواصلنا (CHANGELOG)

> **القاعدة (CLAUDE.md → بروتوكول المهام — البند 13 · PR 3.11):** الـ PR ما بيكتب هون — بيكتب بنده بـ `changelog.d/<رقم-المهمة>.md`، و `python tools/changelog_collect.py` بينقل البنود لهون (الأحدث فوق) بعد الدمج. ممنوع تطويل سطر "Last updated" بأي ملف.
>
> هذا الملف **لا يُقرأ** بكل جلسة — فقط عند الحاجة لتاريخ تغيير معيّن.

## فهرس

- [سجل `docs/SYSTEMS_INDEX.md`](#سجل-docssystems_indexmd)
- [سجل `ARCHITECTURE_FOUNDATION.md`](#سجل-architecture_foundationmd)
- [سجل `docs/design-system/VIEWER-MODES.md`](#سجل-docsdesign-systemviewer-modesmd)
- [سجل `docs/design-system/BUTTONS.md`](#سجل-docsdesign-systembuttonsmd)

## PR 3.9b — ترتيب الاختبارات + بقايا 3.9 + IP الافتراضي — 2026-10-08

- **`tests/`:** 73 ملف اختبار انتقلوا لـ `tests/` بنفس الأسماء. `run_tests.sh` بيشغّلهم من جذر الريبو (`PYTHONPATH` = الجذر)، الـ guard بيرفض أي `test_*` / `*.test.js` برّا `tests/`، وبالآخر بيطبع ملخص: كل ملف فاشل بسطر مع أول سطر خطأ. المسارات جوّا الاختبارات (`__file__` / `__dirname`) + أوامر التشغيل بالتوثيق صارت `tests/…`.
- **بقايا 3.9 (كود الموقع −146 / +59 مع `run_tests.sh`):** `_onPromote` · `_updateChips` · `_cmtFindMentionStart` · `apiGetUser` · `_save_accepted_professions` (نسخة مكررة — `add_job` / `update_job` بيحفظوا المهن) · `send_message` + `mark_message_read_immediate` (بدون مستدعي) · `_timing` من رد `POST /messages` (ضل بسطر الـ log) · قاعدة `canSchedule` الاحتياطية + زر `twScheduleButton` البديل (السجل `twActionState` / `twAction` بس) · `company_follows` (CREATE + فهارس + `_migrate_company_follows_to_profile_follows` + مدخلها بسجل الـ migrations) · أي ذكر لـ `verify_requests` بالكود. ما في `DROP` من الكود — زعتر بيحذف الجداول بإيده.
- **`CLIENT_IP_SOURCE`:** الافتراضي صار `x_real_ip` (كان `xff_left`)؛ بدون الهيدر → `request.client.host`. `.env.example` (جديد — أسماء بس).
- **قاعدة جديدة:** `CLAUDE.md → Testing & CI` 5 + 6 (كل الاختبارات بـ `tests/` · الاختبارات الجديدة تفحص سلوك مش نص حرفي) · SYSTEMS_INDEX §54g.
- Docs: SYSTEMS_INDEX §20 · §23 · §34 · §52a · §54g · §60 · ARCHITECTURE (follow · messages · timing · job professions · client IP · schema) · ARCHITECTURE_FOUNDATION · FUTURE_ROADMAP. Tests: `test_follow_system.py` (DB جديدة بدون `company_follows`) · `test_schedule_interview_runtime.js` (بيحمّل Actions Registry من `tw_shared.js` + `TW_ACTIONS`، + A0 بدون سجل → ما في زر) · `test_ws_api.mjs` API11 · `test_otp_rate_limit_security.py` (الافتراضي + احترام المتغيّر) · `test_post_comments.py` (−3 فحوصات لدوال محذوفة).

## PR 3.7 — سجل إجراءات موحّد (Actions Registry) — 2026-10-07

- `tw_actions.json` + `tw_actions.py` (جديد — SYSTEMS_INDEX §60 · BUTTONS.md BTN-19): لكل إجراء labelKey · أيقونة · نوع · visibleTo · targets · auth · enabledWhen · confirm. `twActionState` / `twAction` بـ `tw_shared.js` + `.tw-act-*` بـ `tw_shared.css`.
- `server.py`: `window.TW_ACTIONS` مع كتلة النصوص بـ `<!--tw:strings-->` · `GET/PUT /admin/actions` (`check_admin`، override بـ `site_settings.actions_override`).
- مرجع: `tw-schedule.js` (زر «تحديد موعد») + `appointments.html` (FAB + «فتح غرفة الموعد»). `tw_strings.json` += مفاتيح `action.*`. اختبار: `test_actions_registry_runtime.js`.
- تصحيح القيم مقابل SYSTEMS_INDEX: `follow` بدون `targets` (§20 — أي حساب بيتابع أي حساب) · `close_room` → `co` بس (`auth.close_appointment`) · `open_room` → `emp` + `co` (§23).

## PR 3.9 — حذف الكود الميت والمؤقت — 2026-10-07

- **الأرقام:** كود الإنتاج −586 / +16 سطر (15 ملف) · الاختبارات والتوثيق الباقي. ملفين انحذفوا كاملين: `messages.debug.js` · `static/app-header.js`.
- **نظام طلب التوثيق القديم (قرار زعتر — التوثيق = KYC بس):** `POST /verify-request` · `GET /admin/verify-requests` · `PUT /admin/verify/{req_id}` · `VerifyRequestInput` / `VerifyUpdateInput` · `create_verify_request` · حقل `verify_request` بملف المالك · `stats.verified_count` بصفحة الشركة (كان دايماً 0) · `CREATE TABLE verify_requests` · تبويب «توثيق» + كرت «طلبات توثيق» بـ `admin.html` (KYC تبويبه موجود). الجدول نفسه ما انحذف (`DROP` بقرار زعتر).
- **سطر «المتصلون الآن» (قرار زعتر):** `#onlineRow` + `renderOnlineRow()` + CSS `.online-*` (ما كان إله مصدر بيانات).
- **Aliases المتابعة (#576):** `POST|DELETE /company/follow/{id}` · `GET /company/{id}/followers` — الواجهة بتستعمل `/profile/{id}/*` بس.
- **هيدر قديم بعد #577:** `static/app-header.js` (`initAppHeader` ما حدا بيستدعيه) + سطرين `<script>` بـ `company-profile.html` / `profile-showcase.html`.
- **مؤقت/ميت:** `messages.debug.js` + 3 استدعاءات `twDebugLog` · `get_full_profile_by_tw_id` · `adminToast` · `loadUserApplications` / `loadCompanyJobs` (admin-view) · `_showFieldErr` (profile-v2.exp) · `showSaved` (settings) · `_statusKey` (company.main).
- **ما انحذف:** `company_follows` + migration تبعه (ما في تأكيد من الإنتاج) · `/admin/message` + `/admin/news` (مستعملين) · `applyNavLogo` (بـ `tw_shared.js` — جلسة تانية) · دوال مقفولة باختبارات أو مشكوكة (تقرير PR 3.9).
- Docs: SYSTEMS_INDEX §19 · §20 · §20a · §23 · §29 · §52 · ARCHITECTURE (company stats · KYC · Follow · Admin · messages online row · public_id V · schema) · `docs/rules/{project-reference,vm10-header,home-v2}.md` · `PROFILE-DATA-VISIBILITY.md` · `NOTIFICATIONS_PLAN.md` · IMAGE-SYSTEM · FUTURE_ROADMAP. Tests: `test_follow_system.py` (aliases → 404) · `test_post_comments.py` (§147 · §SEC-3 · §150f · §154h/j) · `test_global_ui_visibility.py` M02 · `test_page_shell_security.py` · `test_tw_shared_runtime.js` T11b.

## PR 3.8 — DS-COLOR المرحلة 2: كل لون من التوكنز + override أدمن — 2026-10-07

- `tw_shared.css`: مجموعة توكنز كاملة (COLOR-SYSTEM CLR-35) — brand text/hover · `--color-ink(-rgb)` / `--color-overlay(-rgb)` · surface glass/raised/hover/elevated · border subtle/medium · text body/soft/meta/on-brand/on-fill · status `*-strong` · categorical لوحة المنشور. قاعدة التوأم `-rgb` + جدول دمج (من ← إلى). القواعد الموجودة صارت مبنية على `--color-ink-rgb` (نفس القيمة) — جاهزة لـ `[data-theme="light"]` (CLR-23، بدون بناء).
- Override أدمن واحد (CLR-36): `theme_tokens.py` (جديد) · `GET /theme.css` (فاضي بدون override) · `GET/PUT /admin/theme/colors` (`check_admin` · مفاتيح معروفة + ألوان صالحة · log لكل حفظ) · `<link href="/theme.css">` بـ `partials/shell-head*.html`.
- محوّل لصفر ألوان ثابتة: `tw_shared.css` · `static/app-header.css` · `static/home-v2.css` · `static/shared/{tw-select.css, tw-skeleton.css, tw-options-data.js, tw-image-cropper.js}`. تقرير الباقي: `scripts/ds_color_audit.py` (2339 بـ 31 ملف).
- Docs: COLOR-SYSTEM (CLR-04 · CLR-23 · CLR-28 · CLR-35 · CLR-36 · CLR-34) · `docs/rules/ds-color.md` (12–15) · SYSTEMS_INDEX §50 · ARCHITECTURE §57 Admin Endpoints. Test: `test_ds_color_tokens.py` (جديد).

## PR 3.6 — نظام نصوص واحد + قاموس تسميات (Strings System) — 2026-10-07

- نظام جديد: `tw_strings.json` (افتراضي `{"ar": …}`) + `tw_strings.py` + override أدمن بـ `site_settings` (`strings_override.ar`) + `GET` / `PUT /admin/strings` (تحقق: مفاتيح معروفة · ≤ 300 · بدون HTML · بدون متغيرات جديدة) + `twT(key, vars)` / `twTApply` بـ `tw_shared.js`. `read_html` بيبدّل `<!--tw:strings-->` (بـ `shell-scripts.html` + كل صفحة بتحمّل `/tw_shared.js`).
- محوّل لـ `twT`: الهيدر · الشريط السفلي · قائمة الهيدر · `appointments.html`. تغيير نص: فلاتر المواعيد «طلب تغيير» ← «طلب تغيير موعد» و «مكتمل» ← «مكتملة» (نفس كلمة شارة الحالة).
- Docs: `docs/GLOSSARY.md` (جديد) · SYSTEMS_INDEX §59 · `CLAUDE.md` (Full Control + Strings Rules) · ARCHITECTURE §57 Admin Endpoints. Tests: `test_strings_system.py` (جديد) · `test_header_nav.py` B / D (النص صار مفاتيح twT).
- تصحيح CI: `test_legacy_routes_cleanup.py` §2 — كان يفحص النص الثابت `label: 'بنك المواهب'` بقائمة الهيدر؛ صار يفحص `labelKey: 'people.talent_bank'` + `twTalentBankHref` + إن نص المفتاح بـ `tw_strings.json` = «بنك المواهب».

## PR 3.2 — هيدر واحد + شريط سفلي واحد (DS-HNAV) — 2026-10-07

- نظام جديد: `twMountAppChrome()` بـ `tw_shared.js` بيرسم `<header data-tw-header [data-back]>` + `<nav data-tw-bottom-nav>` — ترتيب ثابت (مسجّل: رئيسية · لوغو · جرس · رسائل · قائمة / زائر: لوغو · دخول · تسجيل) · زر رجوع اختياري بنفس الهيدر (`twNavBack` — NAV-05) · لوغو `/static/33333.svg` بس · شريط سفلي من تعريف واحد `_TW_BOTTOM_NAV` حسب نوع الحساب، بدون `href="#"` · حد شارات واحد 99+ للجرس والرسائل (`twNotifBadgeLabel` — كانت الرسائل 9+). CSS بـ `static/app-header.css` (DS-SIZE / DS-COLOR tokens).
- صفحات محوّلة (الكود القديم انحذف): `edu-profile` · `settings` · `appointments` · `appointment-room` · `job-detail` · `home-v2` · `notifications` · `messages`. انحذف `static/home/home.header.js`. `profile-showcase` + `company-profile` → المرحلة 4 (السبب بـ HEADER-NAV.md HNAV-07).
- Docs: `docs/design-system/HEADER-NAV.md` (جديد) · SYSTEMS_INDEX §28 / §41 / §53 / §58 · PAGE-SHELL.md · NAVIGATION.md (ثغرة job-detail ✅) · `docs/rules/` (vm10-header · ds-icon · ds-size · home-v2) · سطر بـ `CLAUDE.md` + `DESIGN_SYSTEM.md`. Tests: `test_header_nav.py` (جديد) + تحديث `test_global_ui_visibility.py` · `test_post_comments.py` §151 · `test_page_shell.py` F05 · `test_job_detail_shell.py` B06 · `test_legacy_routes_cleanup.py` · `test_ds_icon_registry.js` (PHASE_C_PAGES) · `test_ds_size_tokens.py` (`app-header.css`).

## PR 3.5 — نظام متابعة واحد (Follow System — جدول واحد) — 2026-10-07

- Backend: `profile_follows` هو المصدر الوحيد. `_follow_set()` = عملية المتابعة الوحيدة (أي حساب مسجّل يتابع أي حساب، إلا نفسه؛ ضيف 401؛ حساب مش موجود 404). جديد: `GET /profile/{id}/follow` (الحالة + العدّادات) · `get_follow_state()`. migration `company_follows_to_profile_follows` (اختيارية، `ON CONFLICT DO NOTHING`، العدد بالـ log). `/company/follow/{id}` + `GET /company/{id}/followers` = aliases لنفس الدوال (بينحذفوا بـ 3.9). انحذف `follow_company` / `unfollow_company` / `get_company_followers_list`. `get_company_extras` + `/mention/search` صاروا يقروا `profile_follows`. تغيير سلوك: الشركة والجهة التعليمية بيقدروا يتابعوا (كان موظف بس على صفحة الشركة)؛ إشعار متابعة الشركة صار بمفتاح `follow_agg:user:`.
- Frontend: صفحة الشركة (الزر + قائمة المتابعين) وبروفايل الموظف (الزر + القوائم) عبر `twApi` على `/profile/{id}/follow*`؛ الضيف → `twLoginHref(الصفحة)`.
- Docs: SYSTEMS_INDEX §20 / §20a · ARCHITECTURE §53 / §53a. Tests: `test_follow_system.py` (جديد) · `test_post_comments.py` (فحوص `follow_company` المحذوفة صارت تفحص المسار الواحد).
- تصحيح CI: `test_post_comments.py` §124 / §125 / §146 — كانت تفحص فرع `/mention/search` الخاص بالشركة (`company_follows` · `:vid_c`) و«hookين» للمتابعة؛ صارت تفحص الاستعلام الواحد على `profile_follows` (بدون ILIKE لما `q` فاضي، params فريدة لكل فرع، ما في `company_follows`) والـ hook الواحد.

## PR 3.10 — نظام تحديد موعد موحّد (Schedule Interview System) — 2026-10-07

- Backend: `POST /api/appointments` Path B — الشخص مش مرشح على الوظيفة → بينضاف بنفس الـ transaction عبر `_shortlist_candidate_in_tx` (القلب المشترك مع `promote_application_to_shortlist`)؛ ربط جديد بيحتاج وظيفة فعّالة؛ مرفوض / منسحب → 409 (`AppointmentRuleError`). الـ endpoint صار `{ok, data}` / `{ok:false, error}`. جديد: `GET /api/schedule/jobs` · `/api/schedule/open` · `/api/schedule/people`. تغيير سلوك: الترقية بتنقل الطلب لـ `accepted` من `pending` / `viewed` بس.
- Frontend: `static/shared/tw-schedule.js` (جديد) — `twScheduleInterview` / `twScheduleButton` / `twScheduleMount`. الأماكن: بروفايل الموظف · بنك المواهب + الاقتراحات · المتقدمين (كل متقدم) · قائمة الوظيفة المنبثقة · هيدر الماسنجر · «+» بالمواعيد. انحذف `#coApptModal` + منطقه + `.co-appt-*` CSS + `#newApptModal` وحقل `application_id`. `PAGE_ASSETS` += `tw-schedule.js` · `tw-select.js` · `tw-select.css`.
- Docs: SYSTEMS_INDEX §23b · ARCHITECTURE §75 (+ §69 Path B) · APPOINTMENTS_PLAN §18 · `docs/rules/schedule-interview.md` + سطر بـ `CLAUDE.md`. Tests: `test_schedule_interview.py` · `test_schedule_interview_runtime.js` (جديدين) · `test_pr2c_session_sockets_runtime.js` (assert الـ popover اتحدّث).
- تصحيحات قبل الدمج: merge لـ main (#574 CI) · الاختبار الجديدين بـ `run_tests.sh` · `test_post_comments.py` (§171 / §182–187 / §486–489 / §491) صارت تفحص نفس السلوك بـ `tw-schedule.js` + القلب المشترك بدل المودال المحذوف · `list_schedule_jobs` → `list_jobs_for_scheduling` (فحص 175-29: ما في `schedule_job` بـ server.py) · Escape: القائمة المنسدلة المفتوحة جوّا نافذة بتتسكّر لحالها (`tw-select.js` window capture + `tw-overlay.js` بيتجاهل `defaultPrevented`) — `docs/rules/ds-overlay.md` + `test_ds_overlay_runtime.js` القسم E. · `test_applicants_candidates_split.py` + `test_pipeline_backfill.py` (شريحة الترقية بتبلّش من القلب المشترك) · `test_ds_image_runtime.js` B3 (+ `tw-schedule.js` — أفاتار البحث) · ستايل زر الماسنجر وسطر البروفايل صار من `tw-schedule.js` (`.tw-sch-bar`) — ولا CSS صفحة اتغيّر (DS-SIZE S4)، و `profile-v2.css` رجع متل ما كان.

## PR 6.4 — CI شامل: `tests.yml` + `run_tests.sh` + `runtime.txt` — 2026-10-07

- `.github/workflows/tests.yml` (جديد): كل PR لـ main + كل push لـ main، بدون فلترة مسارات — Python 3.11 + Node 20 + `postgres:16` (SSL) → `./run_tests.sh`. انحذفوا `vm01-bfcache.yml` · `vm10-session-visibility.yml` · `ws-security.yml` (مغطّاين كاملين: نفس الاختبارات + `node --check` لكل JS). `scheduler-cron.yml` باقي (مش اختبار).
- `run_tests.sh` (جديد — SYSTEMS_INDEX §54g): القائمة الوحيدة (pytest / script / DB / Node / EXCLUDED بسبب) + حارس لأي ملف اختبار مش بقائمة + DB جديدة لكل اختبار DB. `requirements-dev.txt` (pytest) · `runtime.txt` = `python-3.11`.
- اختبارات قديمة اتحدّثت (الكود صح): `test_post_comments.py` (ما كان عنده exit code — 35 فحص قديم مخفي: سجل migrations PR 2B، `twRequireAuth` PR 1.2، `twApi` PR 3A، بدون `alert` PR 3B، `_server_error` PR 1.6، حذف الحساب بكلمة سر، بلاغ بدون إشعار PR 1.5) · `test_security_admin_jwt.py` + `test_pipeline_backfill_http.py` (admin JWT PR 1.5، migrate-index PR6) · `test_talent_bank_quota.py` (first/last name، rate limiter، schema) · `test_job_archive_integration.py` + `test_pipeline_backfill_integration.py` (schema الإنتاج) · `test_ds_icon_registry.js` (`tw-overlay.js` مش صفحة) · `test_ds_image_runtime.js` + `docs/rules/ds-image.md` (`edu-profile.html` — PR 1.7).
- `test_company_save.py` → `/u/{COMPANY_TW_ID}` + مستثنى (سيرفر حي + Playwright)؛ نسخة ثابتة جديدة `test_company_save_static.py` بالـ CI.
- `ARCHITECTURE_FOUNDATION.md` F15: مثال الفشل = `{"ok": false, "error": {"code", "message", "field"?}}` (عقد #572). `CLAUDE.md`: قسم **Testing & CI** + قاعدة توفير الرصيد ثابتة.

## PR 3B — DS-OVL Runtime V1: `twConfirm` / `twAlert` / `twModal` (بند 3.3) — 2026-10-07

- `static/shared/tw-overlay.js` (جديد — OVERLAY-SYSTEM.md OVL-39 · `docs/rules/ds-overlay.md`): `twConfirm` → `Promise<boolean>` · `twAlert` → `Promise` · `twModal` → `{close, setBusy, el}`. role=dialog + aria-modal + aria-labelledby · Escape (إلا وقت busy) · focus trap · رجوع الـ focus · `inert` للخلفية · scroll lock بالعدّ · backdrop بيسكّر غير الخطرة بس · danger → زر خطر + focus أول على «إلغاء». ألوان/أحجام/أيقونات من DS-COLOR / DS-SIZE / DS-ICON.
- `page_shell.py`: `PAGE_ASSETS` += `tw-overlay.js`. `appointment-room.html`: 3 × `confirm()` → `twConfirm` (إغلاق الغرفة نهائياً = `danger:true`).
- قاعدة: ممنوع `alert` / `confirm` / `prompt` بأي صفحة بتنلمس من هلق. `test_ds_overlay_runtime.js` (جديد — فيه تقرير عدّ للباقي، مش فشل). `test_appointments_guard_runtime.js` C14 اتحدّث (كان بيتأكد إن الـ 3 confirm باقيين).

## PR 3A — نظام طلبات API موحّد (twApi + عقد API) — 2026-10-07

- `tw_shared.js`: **`twApi(path, opts)`** + `twApiMessage()` (جديد — SYSTEMS_INDEX §45a): هيدرات المصادقة، JSON، مهلة 20 ث، نتيجة `{ok, status, data, error, raw}` دايماً، 401 → `invalidateSession('api_401')` مرة وحدة، النت / المهلة → `ok:false` برسالة عربية. `normalizeErrorResponse`: + `error:{field}` → `fieldErrors` و `{ok:false, code, message}` القديم.
- `server.py`: **`api_ok()` / `api_error()`** (جديد — §45b · ARCHITECTURE §74). ولا endpoint موجود تغيّر شكله.
- `appointments.html` → `twApi` (المرجع). قاعدة جديدة: `CLAUDE.md → API Client Rule`. اختبار: `test_tw_api_runtime.js` (جديد، فيه تقرير عدد `fetch(` المباشر). `test_appointments_guard_runtime.js` C4/C6 بتقبل `twApi`.

## PR 2B — منطق المواعيد + مراحل التوظيف + migrations + تعديل الأدمن + بوابة المرحلة 2 — 2026-10-07

- Migrations (SYSTEMS_INDEX §54f · CLAUDE.md → Startup Migration Policy): `ADD CONSTRAINT IF NOT EXISTS` (مش PostgreSQL صالح — كان دايماً بيفشل بصمت) → `_migrate_user_unique_indexes()`: حذف المكرر (بيضل الأقدم) + `CREATE UNIQUE INDEX IF NOT EXISTS` على `user_skills/user_langs/user_links`. `on_startup` → سجل `_startup_migrations()` (حرجة / اختيارية) + `/health.migrations`. `init_db` صارت حرجة (كانت بتبلع خطأها). `_migrate_job_lifecycle`: انشال `except: pass`.
- المواعيد (ARCHITECTURE.md §73): `missed` → `completed` / `closed` و `expired` → `closed`؛ `missed` مش نهائية؛ الـ scheduler بيعلّم `missed` بعد `end_at + 15 د` أو `scheduled_at + 2 س` (job قديم بيوصل بكير بيعيد جدولة حاله)؛ رسائل الغرفة = آخر 50 + `?before_id=` + زر «عرض الرسائل الأقدم».
- مراحل التوظيف: `promote_application_to_shortlist` ما بيرجّع لورا (`_CANDIDATE_STATUS_RANK`)، المرفوض/المنسحب no-op مع رسالة، و`candidate.action` حقيقي (`promoted` / `unchanged` / `kept_higher` / `rejected_noop`). `company.main.js` بيعرض الرسالة.
- الأدمن: `PUT /admin/profile/{id}` (`check_admin`) + `_apply_profile_update()` المشتركة مع `PUT /profile/{id}`؛ `admin-view.html` عبر `TwAdminSession`.
- اختبارات قديمة اتحدّثت: `test_post_save.py` (Test 10 → `icoBookmarkCheck`) · `test_pipeline_backfill.py` (K-04 → no read switch) · `test_talent_bank_polish.py` (test_03 → `' من '`) · `test_company_save.py` (مسار نسبي) · `test_applicants_candidates_split.py` + `test_post_comments.py` 489-09 (سجل الـ migrations) · `test_pipeline_backfill_integration.py` §46 (`promoted`). جديد: `test_pr2b_flow_fixes.py`.

## PR 2A — تسريب اتصالات DB + أعطال مؤكّدة + async بيوقف السيرفر — 2026-10-07

- `auth.py`: **`db_conn()`** (جديد — SYSTEMS_INDEX §54e) — `with db_conn() as conn:` بيرجّع الاتصال بـ `finally`، والاتصال المكسور (`InterfaceError`) بيتسكّر بدل ما يرجع للـ pool. `get/set_site_setting` + `ensure_site_settings_table` + `ensure_reports_table` صاروا عليه (كان release بمسار النجاح بس + `except:` عامة). `ensure_company_tables`: release بـ `finally`. `release_conn`: `except:` → log.
- `server.py`: `mention_search` (ما كان يرجّع الاتصال أبداً) · `submit_report` · `/health` → release بـ `finally`.
- `PUT /auth/user/{id}/name`: كان دايماً 500 (`auth.get_conn` و `auth` مش مستورد). صار `def` + `_norm_name` + حد 100 حرف + `validate_professional_text`؛ `emp` → 422 `emp_name_mutation_forbidden` (G-contract).
- `GET /company/{id}/ratings`: `created_at` بـ `isoformat()` (كان `_serialize(datetime)` → 500 لأي تقييم فيه تعليق).
- async: `submit_report` · `update_user_name` · `change_user_type` · `verify_user` · `admin_reset_password` → `def`. `get_msgs` · `upload_logo` · `admin_kyc_docs` · `admin_migrate_data_images` → الجزء الـ DB بـ `asyncio.to_thread`.
- قاعدة جديدة: `CLAUDE.md → DB Connection & Async Rules`. اختبار: `test_db_conn_async_safety.py` (جديد).

## PR 2C — الاتصالات ما بتنقطع مع رجعة التبويب + أعطال صفحة الشركة — 2026-10-07

- `static/shared/auth-sync.js`: `focus` / `visibilitychange` ما بيعملوا force — بيطلقوا بس لما يتغيّر JWT / tw_user أو `state|userId` (`_checkOnForeground`). `pageshow` (bfcache) لسا forced · `storage` متل ما هو.
- `tw_shared.js` (badge WS) + `messages.ws.js`: نفس JWT + نفس المستخدم + سوكيت شغّال → ولا شي (ما في إغلاق / مسح شارات / GET). إعادة اتصال بس عند تغيير JWT أو المستخدم أو سوكيت مسكّر فعلاً.
- `messages.render.js`: polling الـ 10 ثواني بيوقف لما `document.hidden` وبيرجع (مع تحديث فوري) لما تبيّن الصفحة؛ `reloadMessagesQuiet` ما بيطلب `GET /messages` والصفحة مخفية؛ إخفاء التاب → `inactive_conversation`، رجوعه → `active_conversation` (السيرفر بيعلّم مقروء للمحادثة النشطة).
- `tw_shared.js`: انشال fade-in الصفحة (`<html>` opacity 0 لحد `window.load`).
- صفحة الشركة: `window.TwCompanyPage` (namespace جديد — `company.state.js`) لـ `openNotesPanel` / `openApptModal` بالقائمة المنبثقة · زر «حفظ كمرشح» بـ listener delegated واحد · `_detectJobLocMode()` بيرجّع وضع الموقع الصح بتعديل الوظيفة.
- التوثيق: `docs/rules/vm01-bfcache.md` (10b + ممنوعات) · VIEWER-MODES · SYSTEMS_INDEX §8 + §11a · ARCHITECTURE (Company Frontend → Page Namespace).
- اختبار: `test_pr2c_session_sockets_runtime.js` (جديد).

## PR 1.6 — منع تسريب تفاصيل السيرفر برسائل الخطأ — 2026-10-07

- `server.py`: **`_server_error(where, e)`** (جديد — SYSTEMS_INDEX §54d) — log كامل + traceback، والعميل بياخد 500 «خطأ في الخادم، حاول مرة أخرى». استبدل 60 مكان `HTTPException(500, str(e))` / `detail=f"خطأ: {str(e)}"`.
- `http_exception_handler`: `detail` dict → JSON حقيقي `{"error": message, "detail": {...}}` بدل `str(dict)` · النص بيضل `{"error": "..."}`. `validation_exception_handler`: `details` = `[{loc, type}]` بدل `str(exc)` (بدون قيم المستخدم). `general_exception_handler`: نفس الرسالة الثابتة.
- `auth.py`: رسائل `RuntimeError` الثابتة بدون نص DB (`promote_application_to_shortlist` · `update_application_status` · `create_company_post_comment` · `update_candidate_job_status` · backfill / partial index · scheduler) — التفاصيل بالـ log. `save/remove_profile_interest` + `get_pipeline_application_index_status` → خطأ ثابت.
- `tw_shared.js` → `normalizeErrorResponse`: بيفهم `detail.message` (dict بدون field) و `error` كنص — متل عقد API-MUT-11 الموثّق.
- اختبار: `test_server_error_leak.py` (فحص AST ثابت + runtime). تحديث تأكيد 114d بـ `test_post_comments.py` (الرسالة صارت بدون f-string).

## PR 1.7 — شيل المحتوى الوهمي (صفحة الشركة + الجهة التعليمية «قريباً») — 2026-10-07

- `company-profile.html` + `company.render.js`: سطر «جهة موثقة من تواصلنا» (تبويب عن الشركة) مخفي افتراضياً وبيطلع بس لما `is_verified=true` من الـ API — ما في نص «غير موثقة».
- `edu-profile.html`: انشال المحتوى الثابت (3 دورات وأسعار · تقييم 4.8 / 34 · 17 متسجل · 12 شهادة · منشوران · شارة «جهة موثقة» · نوع «مركز تدريب» وسنة التأسيس والبريد) + زر المتابعة الوهمي + رفع الغلاف (data URL بـ localStorage). مكانهم بطاقة «صفحات الجهات التعليمية قيد التطوير — قريباً». الظاهر من `GET /profile/{id}` بس: الاسم · اللوغو (`twAvatarEl`) · النبذة · الموقع · الموقع الإلكتروني.
- التواصل: `/messages?with=<tw_id>` (الضيف → `twLoginHref`) بدل `/admin/message` + `tw_adm_token`. الملكية من `TwAuthSync` بس (ما في `tw_user`). الحفظ بيبيّن نجاح بس بعد `r.ok`.
- التوثيق: FUTURE_ROADMAP (خطة 5.2 — كل اللي انشال بيرجع من الـ API) · SYSTEMS_INDEX §10 · ARCHITECTURE (Ownership Check edu) · `docs/rules/vm01-bfcache.md` + VIEWER-MODES (انشال `uploadCover`).
- اختبار: `test_no_dummy_content.py` (جديد). `test_vm01_bfcache_runtime.js`: انشال تأكيد `coverUploadBtn`.

## PR 1.5 + 1.8 — توكن أدمن مؤقت موقّع + إبطال الجلسات بعد تغيير كلمة السر — 2026-10-07

- `server.py`: **`_jwt_sign` / `_jwt_verify`** — تطبيق HS256 واحد لسرّين. **`/tw-ctrl-login`** بيرجّع JWT أدمن (`ADMIN_JWT_SECRET`، `role=admin` · `sub=owner` · `perms=["*"]` · ساعة) بدل `ADMIN_TOKEN` الخام. **`check_admin`** بيقبل هاد الـ JWT بس (401 للخام / المنتهي / JWT مستخدم · 403 دور ناقص · 503 بدون سر). SYSTEMS_INDEX §25.
- `static/shared/admin-session.js` (جديد — `TwAdminSession`): `admin.html` + `admin-view.html` — 401/403 أو انتهاء الساعة → شاشة الدخول برسالة واضحة.
- البلاغات: انشال `create_notification(1, …)` — البلاغ محفوظ وبيبيّن بتبويب البلاغات بلوحة الأدمن.
- **إبطال الجلسات** (§2a): `users.password_changed_at` (`_migrate_password_changed_at`) · `set_user_password` بيختمه (تغيير ذاتي + reset الأدمن) · `_jwt_decode` بيرفض `iat` الأقدم · كاش بالذاكرة 60 ثانية بينمسح للمستخدم لحظة التغيير · `PUT /auth/password` بيرجّع `token` جديد · `TwAuthSync.renewToken()` (جديد) بـ `settings.html`.
- ARCHITECTURE → Client IP Resolution: نتيجة قياس Railway — `CLIENT_IP_SOURCE=x_real_ip` (`xff_right` غلط).
- اختبار: `test_admin_session_security.py`. تحديث تأكيدات قديمة بـ `test_security_admin_jwt.py` / `test_kyc_docs_migration.py` / `test_upload_security.py`.

## PR 1.3 + 1.4 — تقوية OTP + IP العميل + حد الدخول لكل إيميل — 2026-10-07

- `auth.py`: **`_otp_issue` / `_otp_verify`** (جديد — SYSTEMS_INDEX §54c) — منطق واحد للإيميل والجوال: `secrets` · hash بس (`v1$` HMAC) · صلاحية 10 دقايق · 5 محاولات (ذرّي) · `hmac.compare_digest` · بينمسح بعد النجاح · مربوط بالإيميل/الجوال الحالي. `_migrate_kyc_otp_security()`: 6 أعمدة `ADD COLUMN IF NOT EXISTS` + مسح الرموز القديمة النصّية.
- `server.py`: **`get_client_ip`** هي المصدر الوحيد (§54a) — `CLIENT_IP_SOURCE` (الافتراضي `xff_left` = نفس السلوك) / `TRUSTED_PROXY_HOPS` / `LOG_CLIENT_IP=1` للقياس. الـ middleware ما عاد يقرأ XFF لحاله.
- Rate limit (§54b): `/kyc/email/verify` + `/kyc/phone/verify` انضافوا · حد الـ IP 60 → 20/دقيقة · حد لكل إيميل بالدخول 5 فاشلة / 15 دقيقة → 429 `login_email_locked` (نفس `_rate_store`).
- KYC: verify بيرجّع 503 لما الإرسال موقّف · رسالة خطأ ثابتة بدل `str(e)` (start / status / send / verify) · `/kyc/start` بيرجّع Tier 3 allowlist بدل `SELECT *`.
- `index.auth.js` (`auth-gw-v12`): نص ثابت لقفل الإيميل.

## PR 1.2 — صفحة الإعدادات: عمليات حقيقية بدل «تم» الكاذبة — 2026-10-07

- `server.py`: **`PUT /auth/password`** (جديد — JWT + bcrypt للقديمة + `_password_policy_error` نفس قاعدة التسجيل + لازم تختلف + rate limiter) · `AccountFieldError` → 422 عربي على الحقل · `POST /auth/register` صار يستعمل `_password_policy_error` (نفس الرسالة والـ 400).
- `DELETE /auth/user/{id}/delete`: بدها `{password}` (bcrypt) · خطأ ثابت بدل `str(e)` · على الـ rate limiter. `auth.py`: `check_user_password` / `set_user_password`.
- `settings.html`: `twRequireAuth()` + `auth-sync.js` · البيانات من `GET /profile/{uid}/full` بدل `tw_user` / `tw_profile_data` · كلمة السر عبر `PUT /auth/password` · الجوال بـ JWT + `r.ok` + إعادة تحميل من الـ API · تغيير الإيميل **مخفي** (قريباً — 5.1) و`saveEmail` انحذفت · حذف الحساب **مخفي** (قرار زعتر — soft delete أولاً، F27) · النجاح بس عند `r.ok`.
- توثيق: SYSTEMS_INDEX §1a · ARCHITECTURE → Account Security Operations (مع جدول أثر حذف `users`) · FUTURE_ROADMAP → Security. اختبار: `test_account_security.py`.

## PR 1.1 — روابط خارجية آمنة (Stored XSS) — 2026-10-07

- `tw_shared.js`: **`twSafeLinkUrl(url)`** (جديد — §54 rule 4b) — `http://` / `https://` + host بس؛ غير هيك `''` → الرابط بينعرض نص بدون `<a>`.
- العرض: profile-v2 روابط البروفايل + رابط الشهادة · edu-profile الموقع · home مصدر الخبر · appointment-room رابط الاجتماع. الحفظ: links / الدورات / تعديل الجهة التعليمية بيفحص قبل الإرسال.
- `server.py`: **`_validate_external_url`** + `ExternalUrlError` → 422 عربي على الحقل — `POST /links` · `POST/PUT /course` · `PUT /profile` (`website`) · `POST/PUT /admin/news` (`source_url`).
- `profile-v2.utils.js`: `esc()` صارت alias لـ `twEscHtml` (بتهرّب `"` و `'`). `tw_shared.js?v=` على profile-showcase + edu-profile.
- `test_ds_icon_registry.js`: ملفات `.py` مستثناة من فحص "only phase-C pages" (`page_shell.py`).

## Phase C / appointments + appointment-room — 2026-10-07 — ثالث تحويل + guard الصفحات المحمية (`twRequireAuth`)

- `tw_shared.js`: **`twRequireAuth(opts)`** (جديد — SHELL-09 · Auth Gateway rule 14) — قرار من `TwAuthSync.getSessionSnapshot()` بس: guest / expired / stale / invalid / بدون TwAuthSync → `location.replace(twLoginHref(path + query))` · `opts.userTypes` ونوع غلط → `twAccountHref` · تسجيل واحد على `onSessionChange` (logout بتاب تاني / bfcache → نفس القرار · حساب تاني → `location.reload()`).
- `appointments.html` + `appointment-room.html`: markers الـ shell (انشالت charset / viewport / Cairo — صار 400–900 / preconnect؛ الـ reset `*` صار من `tw_shared.css`) · `<meta name="tw-page" content="auth">` + `twRequireAuth()` بدل `tw_user` / `tw_jwt` المباشر · `fetch` عبر `getAuthHeaders(true)` · `401` → `invalidateSession('api_401')` → `/login?next=` · `alert()` → `showToast` (`error` / `warning`) + `normalizeErrorResponse` · `safeText` / `initials` المحلية انحذفت (المشتركة / `twAvatarEl`).
- DS-ICON: SVG يدوي + emoji (أزرار الغرفة · الحالات الفاضية · البانر المغلق · صفحة "غير مصرح") + `‹` → `<i data-tw-icon>` + `twIcon.hydrate` / `twIconEl` · `tw-icons.js?v={{v:tw-icons.js}}`.
- DS-IMAGE: الطرف التاني بالموعد → `twAvatarEl(..., 'lg')` (الغرفة مع `applicant_avatar` / `company_avatar`).
- DS-SIZE / DS-COLOR: المطابق وتحت البكسل → tokens · `--bg/--card/--ac/--ac2/--ac3` → `--color-*` · المختلف → `--ap-border` (.07) · `--ap-text` (#e8eaf0) · `--ap-text-sub` (#8892a4) · `--ap-danger` (#ef4444 — كان بيغطّي `--danger` المشترك) · `--ap-warn` (#f59e0b) · `--ap-surface-modal` (#0d1526) · `--r: var(--radius-xl)` (T2) · inline `style.cssText` بالغرفة → classes.
- WebSocket: الغرفة polling HTTP كل 5 ثواني بس (ما فيها WS) — `tw_shared.js` بيضيف اتصال واحد للـ badge WS العام (نفس كل الصفحات)، ما في تكرار ولا تعارض.
- باقي (F30): 3 × `confirm()` بالغرفة · NAV-06 بدون صف للمواعيد · ما في helper لرابط خارجي — FUTURE_ROADMAP.
- اختبارات: `node test_appointments_guard_runtime.js` (جديد — 49 فحص) · allowlists المرحلة C بـ `test_ds_icon_registry.js` / `test_ds_image_runtime.js` / `test_ds_size_tokens.py`.
- توثيق: PAGE-SHELL (SHELL-00 · SHELL-01 · SHELL-03 · SHELL-08 · **SHELL-09**) · `docs/rules/page-shell.md` (10) · CLAUDE.md Auth Gateway rule 14 · ICON-SYSTEM · IMAGE-SYSTEM · SIZE-SYSTEM · FEEDBACK-SYSTEM (M12 / M13) · `docs/rules/{ds-icon,ds-image,ds-size}.md` · SYSTEMS_INDEX §23 · §55–§58 · ARCHITECTURE · FUTURE_ROADMAP.

## landing F30 close-out (بعد PR #560) — 2026-10-06 — أزرار التسجيل · لوغو offline · `?v=` لأصول الصفحة · صورة المشاركة

- `landing.html`: «ابدأ مجاناً» (nav · hero · CTA) و«تسجيل» (footer) → `/login#register` · «كموظف / كشركة / كجهة تعليمية» → `/login#register-emp|co|edu` (hash router الموجود بـ `index.ui.js`). «دخول» بيضل `/login`.
- `page_shell.py`: `PAGE_ASSETS` (allowlist ثابتة — `tw-icons.js`) · `apply_shell` بيبدّل `{{v:<name>}}` بنص الصفحة كمان؛ اسم مش معروف أو placeholder بصفحة بدون markers → `ValueError`. `landing.html` + `job-detail.html` → `/static/shared/tw-icons.js?v={{v:tw-icons.js}}`.
- `sw.js`: `/static/33333.svg` بالـ precache (لوغو صفحة الـ offline) · `BUILD_TIME` → `20261006_2100`.
- `scripts/gen_app_icons.py` بيولّد كمان `static/og-image.png` (1200×630 — الشعار كامل بالنص على `--color-surface-page` من `tw_shared.css`) · landing: `og:site_name` · `og:image` (+ width / height / type / alt) · `twitter:card=summary_large_image` · `twitter:image` — بدون نص جديد.
- اختبار: `python test_landing_shell.py` (قسم H جديد — 12 فحص؛ 47/47).
- توثيق: PAGE-SHELL (SHELL-02 · SHELL-05 · SHELL-07) · `docs/rules/page-shell.md` · SYSTEMS_INDEX §32 · §58 · FUTURE_ROADMAP.

## Phase C / landing — 2026-10-06 — ثاني صفحة محوّلة: Shell + DS-ICON + DS-SIZE + DS-COLOR + offline fallback

- `landing.html` (`/` · `/landing.html`): markers `<!--tw:shell-head-->` / `<!--tw:shell-scripts-->` — انشالت charset / viewport / preconnect + dns-prefetch الخطوط / Cairo (300–900 → 400–900 من الـ shell) / manifest / theme-color / `apple-mobile-web-app-*` (صارت بالـ shell — H01) / apple-touch-icon (`/icon-192.png` → `/apple-touch-icon.png`) / `/tw_shared.js` → `/static/tw_shared.js?v=H`. صارت تحمّل `tw_shared.css` قبل `<style>` الصفحة. SEO (title · description · OG · twitter · robots · canonical) بيضل بالصفحة مرة وحدة. الدخول بيضل عبر `twEntryDestination()` (TwAuthSync) — بدون guard.
- DS-ICON: Lucide (vendor) انشال من الصفحة · 29 أيقونة `<i data-tw-icon>` + `twIcon.hydrate(document.body)` (24 `data-lucide` + SVG يدوي + glyphs `←` / `✓`) · `badge-check` → `verified` · `message-circle` → `chat` · `upload-cloud` → `upload` · `arrow-left` / `←` → `forward` · `stroke` بالـ CSS → `color` (currentColor).
- DS-SIZE / DS-COLOR: المطابق وتحت البكسل → tokens · `--ac/--ac2/--ac3/--bg/--card/--border` المحلية → `--color-*` (نفس القيم) · `--t/--t2/--t3` المحلية (.87/.5/.28 — بتختلف عن `--t2`/`--t3` المشتركة .7/.4) → `--lp-text*` محلية (ما بتغطّي الـ aliases المشتركة) · `rgba(0,200,150|37,99,255,…)` → `--color-brand-*-rgb`.
- `sw.js`: precache ملفات الـ shell (`/static/tw_shared.css` · `/static/tw_shared.js` · `/static/shared/auth-sync.js`) + `/static/shared/tw-icons.js` · offline: exact URL أولاً ثم `ignoreSearch` (الـ precache بدون `?v=`) · `BUILD_TIME` → `20261006_2000`.
- تغيير مرئي: `←` النصي → أيقونة سهم · `✓` النصي → أيقونة check (12px) · أيقونات 11→12 · 13→14 · 24→22 · سماكة 1.7/1.8/2.5/3 → 2 (ICON-05/07) · خطوط تحت البكسل (.8/.85/.75/.7rem → tokens) — فرق ارتفاع الصفحة 2px (ديسكتوب) / 6px (موبايل) · وزن 800 صار ينحمّل فعلاً (كان fallback لـ 900) · `-webkit-font-smoothing: antialiased` من `tw_shared.css` (macOS فقط).
- اختبارات: `python test_landing_shell.py` (جديد — 35 فحص: shell · SEO · DS-ICON · entry · DS-SIZE/COLOR · offline precache · BUILD_TIME · `?v=`) · `test_ds_icon_registry.js` (`PHASE_C_PAGES` + landing؛ `sw.js` مش مستهلك) · `test_ds_size_tokens.py` (`_PHASE_C_FILES` + landing).
- توثيق: PAGE-SHELL SHELL-08 · ICON-SYSTEM ICON-13 · SIZE-SYSTEM (SIZE-01 · SIZE-11 · SIZE-12) · `docs/rules/{ds-icon,ds-size,sw-cache}.md` · SYSTEMS_INDEX §32 · §55–§58 · ARCHITECTURE §59 (Landing — entry عبر TwAuthSync بدل وصف localStorage القديم) · §71 (precache) · Hybrid Skill Icon · FUTURE_ROADMAP.

## PR #559 — 2026-10-06 — picker «تصنيف المرشح لكل وظيفة» بكارت بنك المواهب + سقف عدّاد الإشعارات `99+`

- `static/company/company.main.js`: section «تصنيف المرشح لكل وظيفة» بكارت المرشح المحفوظ — picker `co-cand-job-status-dp` (`.co-dp-*` §55g) لكل `job_links[]`: «غير مصنّف» (`null`) + القيم الست. الـ handlers الموجودة (`_handleJobStatusDpSelect` · `_jobStatusInFlight` · rollback من `data-job-links`) صارت حيّة بدون تغيير. builders مشتركة: `_buildChip` + `_jobChipSectionsHTML` + `_jobStatusSectionHTML` — `_savedCardHTML` و `_renderCandidateJobLinksUI` بيبنوا نفس الـ DOM (كان الـ re-render يدمج chips «تقدّم إلى» و«مرتبط بوظيفة» بقسم واحد ويضيفها لـ `.co-cand-info` غير الموجود). حدث `tw:candidate-job-classification-updated` بيحدّث الـ picker؛ الـ picker ما بيلمس `job_applications.status`.
- `static/company/company.css`: لون الـ picker من palette الحالات (`.co-cand-status--*` على الـ wrap) · قواعد الحجم صارت على `.co-cand-job-status-row` (كانت على manage panel).
- `tw_shared.js`: `twNotifBadgeLabel(count)` — المكان الوحيد لسقف عدّاد الإشعارات (`> 99` → `99+`؛ رجع لـ `9+` بالغلط مع VM-10 #532). عدّاد الرسائل ما تغيّر (`9+`).
- `static/app-header.css`: `.ah-bell--active` انشال (ما إله مستهلك من VM-10).
- اختبارات: `node test_candidate_job_status_picker_runtime.js` (جديد — Playwright، 27 فحص) · `test_post_comments.py` 1896/1896: 486-16 · 490-03 خضر بدون تعديل؛ 488-07 · 489-07 · 185-09 · 185-10 · 484-05 · 484-06 صاروا يفحصوا الـ builder المشترك بدل مكان الكود داخل الدالة؛ 154f · 155j · 155k حسب `99+` وشيل الـ class.
- توثيق: SYSTEMS_INDEX §20c (picker مكتمل + تصحيح سطر Option B) · §53 (سقف العدّاد) · ARCHITECTURE §52 · §55g · FUTURE_ROADMAP (3 بنود انشالت).

## PR #558 — 2026-10-06 — F30 من #557 (job-detail) + تنظيف `test_post_comments.py`

- `auth.py get_job`: `u.user_type AS company_user_type` → `GET /jobs/{id}` بيرجّع نوع حساب الجهة الناشرة. `job-detail.js` بيمرّره لـ `twAvatarHtml` (`edu` → لون fallback الـ edu؛ غيابه → `co`). الوظائف المشابهة (`GET /jobs` — مصدر ثاني) ما بتعرض لوغو → ما تغيّرت.
- `tw_shared.js`: `twSafeNext(next)` + `twLoginHref(next)` (NAV-07). `index.auth.js` (`auth-gw-v11`): `?next=` آمن بيغلب `twAccountHref(u)` بعد login/register وبالـ entry check (authenticated بس). `job-detail`: تقديم / حفظ / إبلاغ للزائر → `/login?next=<الوظيفة>`.
- `static/shared/tw-icons.js`: `twIcon.hydrate(root)` (ICON-03.1). `job-detail.html`: 24 أيقونة ثابتة صارت `<i data-tw-icon>`؛ `_paintStaticIcons` / `_prependIcon` / `_setApplyLabels` انحذفوا. نفس الـ SVG ونفس الـ DOM — بدون تغيير مرئي.
- `test_post_comments.py`: 45 فحص فاشل على main → 41 صاروا خضر (6 بيئية: `JWT_SECRET` < 32 حرف · 35 قديمة: VM-10 #532 · PR-7a #549 · PR-5 §69 · job_links #481 · محاذاة مسافات · slices غير محدودة)؛ **4 حمر = خلل فعلي** (picker التصنيف لكل وظيفة — FUTURE_ROADMAP). ولا فحص انحذف.
- اختبارات: `node test_auth_next_icon_hydrate_runtime.js` (جديد) · `test_job_detail_shell.py` B06 · B10 · C04.
- توثيق: NAVIGATION NAV-07 / NAV-08 · ICON-SYSTEM ICON-03.1 · `docs/rules/ds-icon.md` · CLAUDE.md Auth Gateway rule 13 · SYSTEMS_INDEX §1 · §41 · §56 · ARCHITECTURE (job-detail backend + session) · FUTURE_ROADMAP.

## Phase C / job-detail — 2026-10-06 — أول صفحة محوّلة: Shell + DS-ICON + DS-IMAGE + DS-SIZE + DS-FEEDBACK

- `job-detail.html`: markers `<!--tw:shell-head-->` / `<!--tw:shell-scripts-->` — انشالت charset / viewport / preconnect / Cairo / manifest / theme-color / apple-touch-icon (`/icon-192.png` → `/apple-touch-icon.png` من الـ shell) + `apple-mobile-web-app-*` (صارت بالـ shell — انظر التصحيح تحت). صارت تحمّل `tw_shared.css` (قبل `app-header.css` و `job-detail.css`) + `tw_shared.js` + `auth-sync.js` لأول مرة. Lucide انشال؛ `tw-icons.js` سكربت صفحة (أول مستهلك). `#jdToast` انشال.
- `partials/shell-scripts*.html`: `/tw_shared.js` → `/static/tw_shared.js` (نفس الملف عبر `/static/` fallback — جوّا allowlist الـ SW §32). route `/tw_shared.js` القديم باقي للصفحات غير المحوّلة. `sw.js` `BUILD_TIME` → `20261006_1800`. (home-v2 بتاخد المسار الجديد تلقائياً.)
- `static/job/job-detail.js`: session من `TwAuthSync.getSessionSnapshot()` فقط (بدون `localStorage` مباشر؛ `getTwUser()` / `getAuthHeaders()` من `tw_shared.js`) · تقديم / حفظ / إبلاغ للزائر → `/login` · `_lucideIcon` / `_iconsRefresh` / `showToast` المحلي / `goHome` (ميتة) انحذفوا → `twIconEl` + `showToast` الموحّد · لوغو الشركة `twAvatarHtml` (xl eager بالهيدر · lg بكرت الشركة) · emoji / رموز الواجهة (★ ✓ ⚐ 🚨 ⚠️ ℹ️ ← 🔖 ✅) → `twIconEl` أو انشالت من نص الـ toast.
- `static/shared/tw-icons.js`: أيقونة جديدة `report` (flag — Lucide 0.460) بمستهلك حقيقي.
- `static/job/job-detail.css`: 163 قيمة مطابق / تحت البكسل → DS-SIZE tokens · شيل CSS الـ toast و `i[data-lucide]` · `.jd-logo` / `.jd-co-av` صاروا wrappers (الحجم والشكل من `.tw-ava`).
- تغيير مرئي: لوغو الشركة دائرة → مربع بزوايا (IMG-03) · اللوغو بالموبايل 80 → 88 · fallback بدون صورة: أيقونة مبنى → أول حرف من اسم الشركة · أيقونات 13→14 · 10→12 · 15→16 · نجمة الشارة والـ ✓ صاروا SVG · زر "رجوع" بحالة الخطأ: `←` → أيقونة `back` · الـ toast صار `.tw-snackbar` الموحّد.
- تصحيح (#557): `apple-mobile-web-app-*` كانت انشالت من home-v2 و job-detail بدون بديل (تطبيق الآيفون كان ممكن يفتح بواجهة Safari) → صارت بـ `partials/shell-head.html` (app فقط): `mobile-web-app-capable=yes` · `apple-mobile-web-app-capable=yes` · `apple-mobile-web-app-status-bar-style=black-translucent` · `apple-mobile-web-app-title=تواصلنا`. اختبار: `test_page_shell.py` A09 · C04b · H01–H02.
- اختبارات: `python test_job_detail_shell.py` (جديد) · `test_ds_icon_registry.js` / `test_ds_image_runtime.js` / `test_ds_size_tokens.py`: "بدون مستهلك" → allowlist صفحات المرحلة C · `test_page_shell.py` (`/static/tw_shared.js`) · `test_post_comments.py` 132b/c/f/g/h.
- توثيق: PAGE-SHELL (SHELL-02 · SHELL-08) · ICON-SYSTEM (ICON-04.2 · ICON-13) · IMAGE-SYSTEM (IMG-12 · IMG-13) · SIZE-SYSTEM (SIZE-01 · SIZE-11 · SIZE-12) · FEEDBACK-SYSTEM (جدول النسخ المحلية) · `docs/rules/{page-shell,ds-icon,ds-image,ds-size}.md` · SYSTEMS_INDEX §14 · §55–§58 · ARCHITECTURE §62 (Session بدل Auth Guard القديم) + Vendor Assets · FUTURE_ROADMAP.

## PR-8 — 2026-10-06 — Page Shell (DS-SHELL) المرحلة B + home-v2 تجريبية (F39)

- `page_shell.py` (جديد): `apply_shell` · `build_shell` · `asset_hash` — markers `<!--tw:shell-head-->` / `<!--tw:shell-scripts-->` (+ `:admin`) → `partials/shell-*.html` (4 ملفات جديدة، برّا `static/`). `?v=` = أول 10 hex من sha256 لـ `tw_shared.css` / `tw_shared.js` / `auth-sync.js`، مرة وحدة عند بدء السيرفر.
- `server.py read_html`: بيمرّر كل صفحة على `apply_shell` (قبل الـ cache). صفحة بدون markers → مطابقة بالبايت.
- `tw_shared.js`: ما بيسجّل الـ SW إذا الصفحة فيها `<meta name="tw-sw" content="off">` (نسخة الأدمن فقط).
- `home-v2.html`: شيل charset / viewport / preconnect / Cairo / `tw_shared.js` / `auth-sync.js` → markers. صار يحمّل `tw_shared.css` (قبل CSS الصفحة) + manifest + theme-color + icons + Cairo 800/900. screenshots قبل/بعد (390×844 + 1366×900) مطابقة بالبكسل.
- توثيق: `docs/design-system/PAGE-SHELL.md` (SHELL-00 → SHELL-08) · `docs/rules/page-shell.md` · F39 + صف F31 + فهرس القواعد (F1–F39) · CLAUDE.md (جدول) · SYSTEMS_INDEX §58 · `DESIGN_SYSTEM.md` · `ARCHITECTURE.md` (HTML Page Routes) · `CHANGE_ROUTER.md` · `FUTURE_ROADMAP.md` (Phase C).
- اختبار: `python test_page_shell.py` (جديد) · `test_global_ui_visibility.py` صار يقرأ الصفحات عبر `apply_shell` (`read_page`) — K01–K03 + I01–I04.

## fix/page-shell-security — 2026-10-06 — Page Shell أمني قبل PR-8/B

- `admin-view.html`: شيل HTML محشور جوّا `<!DOCTYPE` (كان بيحط الصفحة بـ quirks mode — قسمين ميتين ما بينادوا) · شيل slug الأدمن المكتوب بالكود (`/tw-ctrl-…`) والـ redirect لـ `admin.html` المحذوف → رسالة "افتح لوحة الإدارة" + `history.back()`. (الـ slug القديم موجود بتاريخ git — انغيّر بالإنتاج.)
- `index.html` + `profile-showcase.html`: Lucide من unpkg → `/static/vendor/lucide/lucide.min.js`.
- `static/app-header.js`: `img.src` → `twSafeImageUrl` (§54) · الرابط → `twAccountHref` (بدل `/profile` · `/company-profile` · `/edu-profile`) · بدون `tw_shared.js` (job-detail) → حرف أول + `/login`.
- `server.py read_html`: ملف ناقص → 404 بدل 200 + "الصفحة غير موجودة: {name}".
- SYSTEMS_INDEX §H (`/admin` → `/admin-view` + صفحات المواعيد) · §54 · ARCHITECTURE Safe Rendering.
- تغيير سلوك: admin-view بدون جلسة أدمن ما عاد يحوّل — بيعرض رسالة. صفحة ناقصة = 404 JSON. رابط أفاتار الهيدر مش https / `/` → حرف أول.
- اختبار: `python test_page_shell_security.py` (جديد، 7).

## PR-7b — 2026-10-06 — إصلاح §54 بعرض الصور + تأسيس DS-IMAGE (F38)

- (أ) أمني — السبب الجذري: `profile-v2` بيحط روابط الصور بـ `esc()` المحلي (escaping HTML، ما بيهرّب `"` ومش تحقق رابط): `.sc-avatar` (`img.src = esc(url)`) · مودال المتابعين `.sc-fl-avatar` + href `/u/{tw_id}` (innerHTML — كسر attribute ممكن) · غلاف الموظف (`'url(' + esc(url) + ')'` — بدون تحقق ولا تهريب CSS؛ وبعد الرفع بدون أي escaping). الإصلاح: `twSafeImageUrl` (https أو `/` نسبي فقط) + `twCssUrl` بـ `tw_shared.js`؛ الأماكن الأربعة صارت عليهم (+ `twEscAttr`). الـ 8 دوال المحلية = دين معروف (IMG-12).
- (ب) DS-IMAGE Phase B: `twAvatarHtml` / `twAvatarEl` + listener `error` واحد (capture) · `.tw-ava` بـ `tw_shared.css` (قسم 16) · `--size-avatar-md/lg/xl/2xl` (40/48/88/106) بقسم DS-SIZE. بدون مستهلك وبدون تغيير بصري.
- تغيير سلوك: رابط صورة / غلاف مش `https://` ولا `/` نسبي (مثلاً `http:` أو `data:` قديم، أو `data:` بوضع `TW_DEV_UPLOAD`) ما عاد ينعرض بالبروفايل → placeholder / الغلاف الافتراضي.
- توثيق: `docs/design-system/IMAGE-SYSTEM.md` (IMG-00 → IMG-13) · `docs/rules/ds-image.md` · F38 + صف F31 + فهرس القواعد (F1–F38) · CLAUDE.md (جدول + Safe Rendering قاعدة 4) · SYSTEMS_INDEX §57 + §54 + §55 + §29b · `DESIGN_SYSTEM.md` · `SIZE-SYSTEM.md` · `docs/rules/ds-size.md` · `docs/rules/image-cropper.md` + `ARCHITECTURE.md` (Image Cropper: غلاف الموظف ديناميكي W×240 = دين + قرار 4:1 + لوغو مربع) · `ARCHITECTURE.md` Safe Rendering · `FUTURE_ROADMAP.md`.
- اختبار: `node test_ds_image_runtime.js` (جديد) · `test_ds_size_tokens.py` (الـ tokens الجديدة + S4 صار يفحص "ما في مستهلك DS-SIZE جديد" بدل "ما في ملف HTML متغيّر").

## fix/supabase-settings-key-migration — 2026-10-06 — تقوية قراءة إعدادات Supabase + دعم مفاتيح `sb_secret_`

- السبب الجذري: (1) `SUPABASE_URL` بالإنتاج كان فيه حرف اتجاه مخفي بأوله (لصق من موبايل) و `.strip()` ما بيشيله → httpx `UnsupportedProtocol`. (2) المفتاح كان غلط والكود بيبعته دايماً `Authorization: Bearer` → Storage 400 "Invalid Compact JWS"؛ ومفاتيح `sb_secret_` الجديدة مش JWT ولازم تنبعت بـ `apikey`.
- الإصلاح (`server.py`): `_clean_supabase_env` (مسافات + Unicode Cf + BOM + تنصيص) · `_supabase_url_status()` (لازم `https://<project>.supabase.co`) · `_supabase_key_status()` (`sb_secret_` / JWT `service_role`؛ anon → "anon key, not service_role") · `_supabase_auth_headers()` المصدر الوحيد للـ headers (`_store_image` ← `/upload/image` + `POST /admin/logo` + الترحيل · `_sign_kyc_doc`) · سطر حالة عند startup بدون أي قيمة + تحذير المفتاح القديم.
- تغيير سلوك: رابط مش `*.supabase.co` أو مفتاح anon/publishable/مش معروف = غير مضبوط → 503 (كان بيحاول ويفشل 502). `sb_secret_` ما عاد ينبعت Bearer.
- توثيق: CLAUDE.md (جدول المتغيرات) · SYSTEMS_INDEX §29a · `docs/rules/upload.md` · `ARCHITECTURE.md` (Image Upload Security Contract) · `docs/FUTURE_ROADMAP.md`. اختبار: `test_supabase_settings.py` (+ تحديث fixtures بـ `test_upload_security.py` / `test_kyc_docs_migration.py`).

## fix/vm01-same-owner-focus-carveout — 2026-10-06 — أول "حفظ" بعد اختيار صورة بيطلع "انتهت الجلسة"

- السبب الجذري: `auth-sync.js` بيستدعي الـ handlers على `visibilitychange` / `focus` (force) حتى لو الجلسة ما تغيّرت، والـ carve-out للمالك نفسه بـ `profile-v2.render.js` (`p2-authsync`) كان بس لـ `pageshow` → revocation مؤقت (`_scViewerType='guest'` + إغلاق `.ep-overlay`) لما الموبايل يرجع من معرض الصور → `_ownerGuard()` يرفض أول حفظ قبل ما يرجع الـ re-verify.
- الإصلاح: الـ carve-out صار لـ `pageshow` / `visibilitychange` / `focus` (نفس المالك + جلسة صالحة → re-verify بس). نفس الإصلاح بـ `company.main.js` (`co-authsync` — كان يسكّر `editOverlay` ويعطّل زر الحفظ). الـ revoke الفوري باقي لـ logout · expired/invalid/stale · account switch · `storage`. `edu-profile.html` ما فيه نفس المشكلة.
- توثيق: `VIEWER-MODES.md §VM-01-BFCACHE`. اختبار: `node test_vm01_bfcache_runtime.js` (سيناريوهات 17–20).

## PR-7c — 2026-10-06 — KYC docs للأدمن (signed URL) + ترحيل صور `data:` القديمة

- (أ) `GET /admin/kyc/{submission_id}/docs` (`check_admin`): روابط Supabase مؤقتة (300s) للهوية والسيلفي، بس لمسار `kyc-docs/{user_id الطلب}_{kind}_{12hex}.{ext}`؛ غير هيك `null` + سبب. `Cache-Control: no-store`، الرابط ممنوع بالـ log. `GET /admin/kyc` ما عاد يرجّع `id_front_url` / `selfie_url`. `admin.html`: زر "عرض المستندات" → modal بالصورتين + قبول/رفض.
- (ب) `POST /admin/maintenance/migrate-data-images?dry_run=1`: ترحيل `data:` من `profiles.avatar_url` / `cover_url` · `company_profiles.cover_url` · `kyc_submissions` · `site_settings` logos إلى Storage بنفس قواعد PR-7a؛ UPDATE مشروط بالقيمة القديمة؛ غير الصالح بينترك ويتذكر؛ idempotent. `admin.html`: قسم صيانة (فحص + ترحيل بتأكيد).
- توثيق: SYSTEMS_INDEX §23 + §29a · `docs/rules/upload.md` (بنود 9–10) · `ARCHITECTURE.md` (Admin Endpoints · KYC · Image Upload Security Contract) · `docs/FUTURE_ROADMAP.md` (شيل P0 KYC + بند تنظيف ملفات Storage اليتيمة). اختبار: `test_kyc_docs_migration.py`.
- تصحيح (نفس الـ PR): `GET /admin/kyc` كان بيرجّع `email_code` / `phone_code` (`SELECT ks.*` — مخالف Tier 4 Never-Returned) → allowlist صريح (`auth._ADMIN_KYC_LIST_COLUMNS`): `id, user_id, full_name, email, user_type, step, status, email_verified, phone_verified, admin_note, submitted_at, reviewed_at` — ممنوع `email_code` / `phone_code` / `id_front_url` / `selfie_url` / `ks.*`.
- merge main (#551): التوقيع (`_sign_kyc_doc`) و`admin_kyc_docs` (`storage_base`) والترحيل صاروا يقرأوا الـ base عبر `_supabase_base_url()` بس (+ `_supabase_service_key()` مع trim) — ما في قراءة مباشرة لـ `SUPABASE_URL`. اختبار: base فيه `/` بالآخر.

## fix/upload-error-classes — 2026-10-06 — حادثة رفع الصور بعد PR #549

- السبب الجذري (الأرجح — قيمة المتغير بالإنتاج ما انفحصت من هون؛ الـ logs الجديدة بتأكّده): الرفع لـ Storage بينجح، بس `PUT /profile` بيرفض الرابط (400 `رابط الصورة غير صالح`) لأن `_store_image` كان يبني الرابط من `SUPABASE_URL` الخام و`_validate_stored_image_url` يقارن بـ base بدون `/` بالآخر — قيمة المتغير بـ `/` بالآخر (أو مسافة) تنتج `//storage`. الواجهة كانت ترمي `Error('profile update failed')` بدون رسالة → toast عام، ونجاح الرفع ما كان يطبع شي بالـ log (يعني "ما في طلب").
- السيرفر: `_supabase_base_url()` مصدر وحيد (trim + rstrip `/`)، trim لـ `SUPABASE_SERVICE_KEY`، log نجاح `[Upload] stored …` ورفض `[ImageURL] rejected …`.
- الواجهة: `tw-upload.js` بيصنّف (session / network / non_json + status / server) + `TW.uploadResult` / `TW.uploadError` / `TW.uploadFailureMessage`؛ مطبّق على avatar · cover · company logo/cover · KYC. `console.error` بدون بيانات الصورة.
- الـ cropper ما تغيّر: avatar 260×260 JPEG 0.85 (~بضع KB) — الحجم مش السبب.
- اختبارات: `test_upload_security.py` (round-trip بـ SUPABASE_URL فيه `/`) · `node test_upload_client_runtime.js`.

## PR-7a — 2026-10-06 — upload security (`POST /upload/image` · `POST /admin/logo`)

- السيرفر: `kind` → bucket map ثابت (`_UPLOAD_KINDS`)، اسم ملف يولّده السيرفر، user_id من الـ JWT فقط، JPEG/PNG/WebP + فحص magic bytes (لا SVG)، حدود حجم 7MB نص / 5MB، لا fallback لـ data URL بالإنتاج (502/503؛ dev فقط بـ `TW_DEV_UPLOAD=1`). `/admin/logo` نفس الفحص.
- الواجهة: `TW.uploadImage({ kind, dataUrl, jwt })` + `TW.uploadErrorText()`؛ المستدعين (profile-v2 avatar/cover · company logo/cover · KYC بـ settings.html · admin logo) ما عاد يحفظوا data URL.
- توثيق: SYSTEMS_INDEX §29a · `docs/rules/upload.md` · `ARCHITECTURE.md → Image Upload Security Contract` · `CLAUDE.md` جدول المتغيرات (`TW_DEV_UPLOAD`). اختبار: `test_upload_security.py`.
- تصحيح (نفس الـ PR): `_validate_stored_image_url()` على كل حفظ لرابط صورة (`PUT /profile` avatar/cover · `PUT /company/profile` + `PUT /company/cover` · `POST /kyc/docs`) — لازم رابط Storage تبع نفس المستخدم ونفس الـ kind، أو القيمة الحالية بدون تغيير، أو فاضي؛ `data:` بـ `TW_DEV_UPLOAD=1` بس.
- تصحيح 2 (نفس الـ PR): `employee-cover` → bucket `avatars` (bucket `covers` ما كان موجود بـ Supabase — رفع غلاف الموظف كان بيفشل دايماً وينحفظ base64). `kyc-docs` خاص (`_PRIVATE_BUCKETS`): الرفع بيرجع `{path}` = `kyc-docs/{name}` وهو اللي بينحفظ، والتحقق لـ KYC على المسار الخاص. عرض الأدمن بـ signed URL → `docs/FUTURE_ROADMAP.md` P0.

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

- PR 2B — 2026-10-07 — F16: مثال الـ migration صار بيرفع الخطأ (ما بيبلعه) + التسجيل بـ `_startup_migrations()` (حرجة / اختيارية) + ممنوع `except: pass` جوّا الـ migration. بدون قاعدة جديدة — توضيح لـ F9 / F16.
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

- 2026-10-06 (fix/vm01-same-owner-focus-carveout): §VM-01-BFCACHE — carve-out المالك نفسه صار يشمل `visibilitychange` / `focus` (مش بس `pageshow`)؛ `storage` يضل revoke فوري.
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
