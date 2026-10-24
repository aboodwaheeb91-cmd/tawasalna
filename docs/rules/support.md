# Support Tickets — نظام الدعم (task 7.1)

> إلزامي بنفس قوة `CLAUDE.md` لأي مهمة بتلمس الدعم. Spec: `docs/SYSTEMS_INDEX.md §62` · `ARCHITECTURE.md §81` · migration `docs/migrations/7.1_support_tickets.sql` · test `python -m pytest tests/test_support_tickets.py -q`.
>
> **⚠️ النظام غير مكتمل لحد 7.2 و 7.3:** 7.1 = التذاكر من الموقع + صندوق الأدمن، نص فقط. **ما في بريد** لردود التذاكر (الزائر ما بيوصله رد الأدمن لحد 7.2 — بيتخزّن `guest_email` بس) و **ما في مرفقات**. الإيميل الوحيد بـ 7.1 = رمز التحقق للزائر (`support_guest_otp`).

## المصدر الوحيد

- **`support.py`** — الـ schema (`SCHEMA_SQL` + `migrate_support`، migration اختيارية `support_tickets`) · كل قراءة وكتابة للتذاكر (`create_user_ticket` · `list_user_tickets` · `get_user_ticket` · `user_reply` · `user_close` · `create_guest_ticket` · `admin_list` · `admin_get` · `admin_reply` · `admin_update`) · القوائم الثابتة `CATEGORIES` · `STATUSES` · `PRIORITIES` · `REOPEN_DAYS = 14`. `server.py` بيتحقق من المدخلات والحدود والصلاحية وبينادي هالدوال بس.
- **الجداول:** `support_tickets` (`public_id` · `user_id` NULL للزائر · `guest_email` · `category` · `status` · `priority` · `subject` · `created_at` · `updated_at` · `last_message_at` · `closed_at`) · `support_messages` (`ticket_id` · `author_type` user / guest / admin · `author_id` (رقم الحساب أو `sub` الأدمن، الزائر NULL) · `body` · `created_at`) · `support_guest_otp` (رمز الزائر — جدول ثالث صغير بموافقة صاحب المشروع). `CHECK` على التصنيف والحالة والأولوية + زائر = تصنيف `account` بس + موضوع / رسالة مش فاضيين. RLS مفعّل (`rls_lockdown`) بدون أي صلاحية لـ `anon` / `authenticated`.
- **المعرّف العام:** `auth.generate_public_id("H")` — المولّد الوحيد (`{H}{10 A-Z0-9}`، بدون رمز دولة — CLAUDE.md → Smart Public Profile Router القاعدة 9). هوية بس، مش صلاحية: الملكية بتنفحص بكل طلب.

## القيم المعتمدة

| | القيم |
|--|------|
| التصنيف | `account` الحساب وتسجيل الدخول · `profile` الملف والتوثيق · `jobs` الوظائف والدورات · `technical` مشكلة تقنية · `complaint` شكوى أو بلاغ · `other` أخرى (ما في «الدفع والاشتراكات») |
| الحالة | `open` مفتوحة · `awaiting_user` بانتظار ردّك · `closed` مغلقة |
| الأولوية | `normal` عادية (افتراضي) · `high` مرتفعة · `urgent` عاجلة — **الأدمن بس** |
| الطول | الموضوع ≤ `support_subject_max` (120) · الرسالة ≤ `support_body_max` (5000) — `tw_limits.py`؛ فاضي (بعد `strip`) → 422 `required` |

## الحساب المسجّل (`verify_token`)

1. `GET /support/tickets` (تذاكري بس، الأحدث رسالة أولاً) · `POST /support/tickets` `{category, subject, body}` → 201 `{public_id}` · `GET /support/tickets/{public_id}` (المحادثة + `can_reopen`) · `POST …/messages` `{body}` · `POST …/close`.
2. **تذكرة غيرك = 404** (قراءة · رد · إغلاق) — نفس رد التذكرة المش موجودة. الأولوية ما بتطلع بردود المستخدم.
3. **ردّه → `open`.** على تذكرة مغلقة: خلال 14 يوم من `closed_at` بيرجّع يفتحها (`reopened: true`)، بعدها 409 `reopen_expired` «افتح تذكرة جديدة».
4. **الحدود (tw_settings، مجموعة `support`):** `support_open_max` (5 — مفتوحة + بانتظار الرد بنفس الوقت؛ بتنطبق على الفتح **وعلى إعادة الفتح**، قفل صف `users` بنفس الـ transaction) → 409 `too_many_open` · `support_create` (10 / ساعة لكل حساب) → 429 `rate_limited`.
5. **الحظر والتعليق ما بيأثروا على التذاكر:** ما في `bs.visible_sql` بالدعم — الأدمن بيشوف تذاكر الحساب المعلّق، والحظر بين مستخدمين ما إله علاقة. (الحساب المعلّق بياخد 401 على كل طلب بحسابه — مساره نموذج الزائر.)

## الزائر (مشاكل الدخول بس)

1. **خطوتين:** `POST /support/guest/code` `{email}` → رمز على الإيميل · `POST /support/guest/tickets` `{email, code, subject, body}` → 201 `{public_id}`. ما في صفحة متابعة؛ الرد بالإيميل لاحقاً (7.2).
2. **التصنيف من السيرفر:** دايماً `account`؛ أي `category` تانية → 422 `guest_category` (+ `CHECK` بالقاعدة).
3. **الرمز = نفس نظام OTP:** `auth.guest_otp_issue` / `guest_otp_verify` — نفس `_otp_hash` (HMAC، subject `support-guest`) · نفس `otp_ttl_minutes()` / `otp_max_attempts()` · مرة وحدة · `hmac.compare_digest`. نفس حدود الإرسال `otp_send_target` (`email:<الإيميل>`) + `otp_send_ip` → 429 `otp_rate_limited`. بدون رمز أو رمز غلط / منتهي → 400 `invalid_code` (ما بتنكتب تذكرة). الإرسال عبر `email_service.send_email(…, "support_guest_otp")` — مزوّد مش جاهز أو النوع مطفّي → 503 (fail closed).
4. **الحدود (tw_settings، أمنية، مجموعة `sec_support`):** `support_guest_email` (2 / ساعة لكل إيميل) · `support_guest_ip` (2 / ساعة لكل IP) · `support_guest_global` (60 / ساعة لكل الزوار مع بعض) — بخطوة وحدة مقفولة (`_rate_ok_all`) بعد التحقق من الرمز → 429. **حد الإيميل + السقف العام بيحموا حتى لو الـ IP مزوّر** — ما في اعتماد على حد الـ IP لحاله.
5. **المسارين عليهم `_public_rate`** (§54o — تست البنية بـ `tests/test_public_rate_limit.py`).
6. **الـ IP:** `get_client_ip()` بس — ما انعدّلت بهالمهمة.

## الأدمن (`support.manage`)

1. الصلاحية `server.SUPPORT_PERM = "support.manage"` — `check_admin(request, SUPPORT_PERM)` أول شي بكل endpoint. الأدمن الرئيسي (`perms: ["*"]`) عنده ياها افتراضياً. **بدون توكن / توكن مستخدم → 401 · توكن أدمن بدون الصلاحية → 403** (عقد بوابة الأدمن الحالي — PR 1.5، نفس `settings.edit` / `content.edit`).
2. `GET /admin/support/tickets?status&category&priority&page&limit` (الأحدث رسالة أولاً، ≤ 50 بالصفحة، قيمة فلتر غلط → 422) · `GET /admin/support/tickets/{public_id}` (صاحب التذكرة: حساب أو إيميل الزائر + المحادثة) · `POST …/messages` `{body}` → الحالة `awaiting_user` (مغلقة كمان) · `PUT /admin/support/tickets/{public_id}` `{status?, priority?}` — الكاتب الوحيد للأولوية؛ `closed` → `closed_at = NOW()`، غيرها → `NULL`.
3. **السجل:** `admin_audit_middleware` بس (§25b) — `actor` (sub) · `action` = `admin_support_reply` / `admin_support_update` · `target` = `ticket=<public_id>` (حتى للطلب المرفوض) · `old_value` / `new_value` (`status=…;priority=…`) · `created_at`. ❌ نص الرسالة أو الإيميل بالسجل.
4. **الشاشة:** `admin-support.html` = جذر اللوحة + `/support` (سطر `support` بـ `TW_ADMIN_SECTIONS`) + `static/admin-support/admin-support.js` على الـ Admin Shell: فلاتر (حالة · تصنيف · أولوية) · قائمة · فتح التذكرة · رد · تغيير الحالة والأولوية — كل كتابة عبر `TwAdminShell.run` بتأكيد، `permissionAware` (403 → رسالة `admin.support.forbidden`).

## الواجهة

- **`/support`** (`support.html` + `static/support/support.js`، `twRequireAuth`، Page Shell + الهيدر الموحّد): نموذج تذكرة جديدة + تذاكري + المحادثة. التسمية فوق الحقل + «إلزامي» / «اختياري» باهت (`TwSupportForm.field` بـ `static/support/support-form.js`، تصميم Profile V2). التصنيف `.ep-select` + `scSelectInit` (القائمة من السيرفر، الأسماء `support.category.*`). كل نص API عبر `textContent` (escaped).
- **«مشكلة بالدخول؟»** بصفحة الدخول (`index.html`، `[data-support-guest]`) → `TwSupportForm.guestOpen()` — نافذة DS-OVL `twModal`، `twApi(…, {auth: false})`.
- كل النصوص بـ `tw_strings.json` (`support.*` · `admin.support.*` · `settings.item.support_*` · `email.support_guest_otp.*`).

## ممنوعات

- ❌ قراءة / كتابة تذكرة برّا `support.py` · ❌ `priority` من المستخدم أو الزائر (422) · ❌ تذكرة زائر بتصنيف غير `account` · ❌ تذكرة زائر بدون رمز.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py` + `tw_settings` · ❌ store rate تاني · ❌ IP من غير `get_client_ip`.
- ❌ فحص حظر / تعليق على التذاكر · ❌ رد بيكشف إذا التذكرة لحساب تاني (404 بس).
- ❌ مرفقات · ❌ إيميل رد تذكرة قبل 7.2 · ❌ `innerHTML` بنص تذكرة.
