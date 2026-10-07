# Schedule Interview System — نظام تحديد موعد موحّد (PR 3.10)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتلمس تحديد المواعيد. المواصفة: `ARCHITECTURE.md §75` · الفهرس: `docs/SYSTEMS_INDEX.md §23b`.

## Schedule Interview Rules (mandatory for all AI sessions)

1. **زر واحد ونافذة وحدة:** أي «تحديد موعد» بأي صفحة = `twScheduleButton(opts)` (DOM) أو slot `<span data-tw-schedule-slot …>` + `twScheduleMount(root)` (HTML strings) من `static/shared/tw-schedule.js`. النافذة = `twScheduleInterview(opts)` فقط (DS-OVL `twModal`).
2. **كل موعد مربوط بوظيفة.** الواجهة بترسل `POST /api/appointments` بـ `{candidate_id, job_id}` بس. الشخص مش مرشح → السيرفر بيضيفه عبر `_shortlist_candidate_in_tx` (نفس قلب «ترشيح للوظيفة»، نفس الـ transaction، ما في رجوع لورا). ربط جديد → وظيفة فعّالة. مرفوض / منسحب → 409 برسالة عربية.
3. **الإظهار:** الزر بيقرّر لحاله من `TwAuthSync.getSessionSnapshot()` — حساب `co` على `emp` مش نفسه. موعد مفتوح → «فتح الموعد» → `/appointment-room?id=`. الحماية الحقيقية بالسيرفر (F21).
4. **التحميل:** بعد `tw-overlay.js` — صفحة shell عبر `PAGE_ASSETS` (`{{v:tw-schedule.js}}`)؛ صفحة غير محوّلة بـ `?v=` يدوي. مع `tw-select.js` / `.css` للـ dropdowns.
5. ❌ مودال موعد خاص بصفحة · ❌ حقل `application_id` (أو أي رقم داخلي) يكتبه المستخدم · ❌ `fetch` مباشر لـ `/api/appointments` أو `/api/schedule/*` (كله `twApi`) · ❌ `<input type="date|time">` بالنافذة (DS-DATE dropdowns) · ❌ إضافة شخص لـ pipeline للموعد بغير `_shortlist_candidate_in_tx`.

Tests: `python -m pytest test_schedule_interview.py -q` (`TW_TEST_DB_URL`) · `node test_schedule_interview_runtime.js`.
