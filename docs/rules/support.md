# Support Tickets — نظام الدعم (task 7.1 · 7.2a)

> إلزامي بنفس قوة `CLAUDE.md` لأي مهمة بتلمس الدعم. Spec: `docs/SYSTEMS_INDEX.md §62` · `ARCHITECTURE.md §81` · migrations `docs/migrations/7.1_support_tickets.sql` · `7.2a_A_expand.sql` · `7.2a_B_migrate.sql` · tests `python -m pytest tests/test_support_tickets.py -q` · `python -m pytest tests/test_support_guest_link.py -q`.
>
> **⚠️ 7.2a = Backend بس.** الواجهة (صفحة متابعة الزائر، الحقول الإضافية، الحالات الجديدة بالأزرار) بمهمة لاحقة — `/support/track` هلق صفحة placeholder، وزر الرد بشاشة الأدمن لازم يبعت `next_status` (بدونه 422). ما في مرفقات.

## المصدر الوحيد

- **`support.py`** — الـ schema (`SCHEMA_SQL` = الشكل النهائي للـ DB الجديدة والـ CI، `migrate_support` = `CREATE … IF NOT EXISTS` بس، migration اختيارية `support_tickets`) · كل قراءة وكتابة للتذاكر وروابط الزائر · `transition()` (الانتقالات) · `normalize_sql()` (توحيد القيم القديمة) · `clean_details()` / `clean_faq()` · `issue_guest_link()` · القوائم الثابتة `CATEGORIES` · `STATUSES` · `PRIORITIES` · `FIELDS` · `FAQ_IDS` · `REOPEN_DAYS = 14`. `server.py` بيتحقق من المدخلات والحدود والصلاحية وبينادي هالدوال بس.
- **الجداول:** `support_tickets` (`public_id` · `user_id` NULL للزائر · `guest_email` · `category` · `status` · `priority` · `subject` · `details` JSONB · `faq_id` · `legacy_category` · `created_at` · `updated_at` · `last_message_at` · `closed_at` = وقت الحل) · `support_messages` (`ticket_id` · `author_type` user / guest / admin · `author_id` · `body` · `created_at`) · `support_guest_otp` (رمز الزائر) · `support_guest_access` (رابط المتابعة — hash بس). RLS مفعّل (`rls_lockdown` بتغطي كل جدول بـ `public` تلقائياً) بدون أي صلاحية لـ `anon` / `authenticated`.
- **المعرّف العام:** `auth.generate_public_id("H")` — هوية بس، مش صلاحية.
- ❌ **تعديل قيود الإنتاج من كود الإقلاع** — الإنتاج بملفات `docs/migrations/7.2a_*.sql` بإيد زعتر.

## التصنيفات والحقول الإضافية (`details`)

| التصنيف | الحقول المسموحة (مفتاح غريب = 422) |
|--|--|
| `account` | `issue` ∈ forgot_password · no_code · login_failed · lost_access · hacked · other · `account_name` ≤ 100 · `account_ref` (رقم TW) · `account_email` (صيغة صالحة) · `account_phone` (أرقام و `+` ≤ 20) |
| `verification` | `request_type` ∈ personal · company · edu · `submitted_date` (YYYY-MM-DD، مش مستقبل — أحدث تاريخ على الأرض UTC+14 مقبول) |
| `profile` | `page_url` |
| `jobs` | `job_url` · `kind` ∈ apply · post |
| `education` | `name` ≤ 120 |
| `technical` | `page_url` · `device` ∈ mobile · desktop |
| `complaint` | `content_url` |
| `general` | بدون |

- **الزائر:** `GUEST_CATEGORY = account` بس (السيرفر + `CHECK`).
- كل قيمة نص؛ الروابط `https://tawasolna.com/…` بس ≤ 300 (بدون مسافات / `"'<>\`) · بدون أحرف تحكم (Cc) · قيمة فاضية بتنشال · الحجم الكلي ≤ 4000 (CHECK بالقاعدة كمان). الخطأ: 422 `unknown_detail` / `invalid_detail` / `details_too_large` / `invalid_details`، `field = details.<key>`.
- **`faq_id`** اختياري — لازم يكون من `support.FAQ_IDS` (مرتب حسب التصنيف)، غيره 422 `invalid_faq`.
- **`GET /support/meta`** (عام + `_public_rate`): `categories` · `guest_category` · `fields` (لكل تصنيف: `key` · `type` · `values` / `max`) · `faq`. بدون نصوص — النصوص للواجهة من `tw_strings` (`support.category.*` …).

## الحالات والانتقالات (`support.transition` — الدالة الوحيدة)

| الحالة | المعنى |
|--|--|
| `new` | جديدة — ما حدا رد |
| `in_review` | قيد المراجعة |
| `awaiting_user` | بانتظار رد صاحب الطلب |
| `resolved` | انحلّت (`closed_at` = وقت الحل) |

1. الفتح → `new` (بينكتب صراحةً بالـ INSERT).
2. رد الأدمن → `next_status` ∈ {`awaiting_user`, `resolved`} **إلزامي** (غيره / بدونه 422 `invalid_next_status`).
3. الأدمن بيغيّر الحالة يدوياً لأي قيمة (`PUT`).
4. رد المستخدم أو الزائر على `new` / `in_review` / `awaiting_user` → `in_review`.
5. رد على `resolved` خلال 14 يوم من `closed_at` → `in_review` (`reopened: true`، ضمن حد المفتوحة للحساب). بعدها → 409 `reopen_expired` «افتح طلباً جديداً».
6. «انحلّت» من المستخدم (`POST …/close`) أو الزائر (`/support/track/resolve`) → `resolved`.
- `closed_at`: بينكتب عند الدخول لـ `resolved`، بيتصفّر عند أي خروج منها.
- **حد المفتوحة** `support_open_max` = كل تذكرة حالتها غير `resolved` (الفتح + إعادة الفتح، قفل صف `users`).

## فترة الانتقال (بين الدمج ومرحلة B)

- **مرحلة A** (`7.2a_A_expand.sql` — قبل الدمج): القيود بتقبل القديم والجديد + الأعمدة + `support_guest_access`. الـ default بيضل `'open'` → الكود بيكتب `status='new'` صراحةً.
- **القراءة** بتمرق كلها (عرض · فلترة · ترتيب · عدّ) من `support.normalize_sql()`: `open` → `in_review` إذا في رسالة أدمن، غير هيك `new` · `closed` → `resolved` · `other` → `general`. **الكتابة بتكتب الجديد بس.**
- **مرحلة B** (`7.2a_B_migrate.sql` — بعد ما آخر deploy يصير Active على commit الدمج، Replica وحدة): نسخة احتياطية `support_tickets_bak_72` + تحويل الصفوف (`legacy_category` = القديم) + القيود النهائية + default `'new'`. `closed_at` ما بيتغيّر. الاحتياطي بينحذف يدوياً بعد أسبوع.
- بعد B بيصير `normalize_sql()` بلا أثر — حذفه بمهمة لاحقة.

## الحساب المسجّل (`verify_token`)

1. `GET /support/tickets` · `POST /support/tickets` `{category, subject, body, details?, faq_id?}` → 201 `{public_id}` · `GET /support/tickets/{public_id}` (المحادثة + `details` + `faq_id` + `can_reopen`) · `POST …/messages` `{body}` · `POST …/close` («انحلّت»).
2. **تذكرة غيرك = 404**. الأولوية ما بتطلع بردود المستخدم.
3. **الحدود (tw_settings، مجموعة `support`):** `support_open_max` (5) → 409 `too_many_open` · `support_create` (10 / ساعة) → 429.
4. الحظر والتعليق ما بيأثروا على التذاكر.

## الزائر

1. **فتح التذكرة:** `POST /support/guest/code` `{email}` → رمز · `POST /support/guest/tickets` `{email, code, subject, body, details?, faq_id?}` → 201 `{public_id}` — **الرد بيحمل رقم H بس**؛ رابط المتابعة بينبعت بإيميل `support_guest_link` (فئة SECURITY، المتغيرات escaped، «لا تشارك هذا الرابط»).
2. الرمز = نفس نظام OTP (`auth.guest_otp_issue` / `guest_otp_verify`) + حدود `otp_send_target` / `otp_send_ip` + `support_guest_email` / `_ip` / `_global` (كما بـ 7.1).
3. **ما في ربط تلقائي** لتذاكر الزائر بأي حساب.
4. **Fail closed على `support_guest_link`:** إذا `email_service.can_send("support_guest_link")` = False (النوع مطفي من الأدمن أو المزوّد مش جاهز) → `/support/guest/code` و `/support/guest/tickets` بيرجّعوا نفس الـ 503 `otp_delivery_unavailable` (قبل إصدار الرمز / قبل التحقق وأي كتابة — ما بتنفتح تذكرة بدون رابط) · `/support/track/resend` نفس الرد العام بدون إرسال وبدون روابط جديدة.

### رابط متابعة الزائر (7.2a)

- **الإصدار:** `support.issue_guest_link(ticket_id, keep=3)` — الكاتب الوحيد لـ `support_guest_access`. الرمز `secrets.token_urlsafe(32)`، بينحفظ **sha256 hex بس**، صالح 90 يوم. بيلغي كل الفعّالة إلا آخر `keep - 1` قبل ما يصدر الجديد → أكتر شي `keep` فعّالين (keep=0 → الجديد بس).
- **الرابط:** `{site_url}/support/track#t=<token>` — الرمز بالـ fragment (المتصفح ما بيبعته للسيرفر ولا بالـ Referer)، والصفحة بتبعته بالـ body.
- **`POST /support/track/view` `{token}` · `/reply` `{token, body}` · `/resolve` `{token}`:** رمز غلط / منتهي / ملغى / مش لتذكرة زائر → **نفس 404** (`support.error.track_not_found`) بدون تمييز · كل نجاح بيحدّث `last_used_at` · الرد بيمدد `expires_at` للرمز المستخدم لـ 90 يوم من هلق · الزائر ما بيشوف `author_id` ولا الأولوية ولا `legacy_category` ولا الإيميل.
- **`POST /support/track/resend` `{email}`** → **دائماً نفس الرد 200** (الشغل بعد الرد — BackgroundTasks): تذاكر الزائر بهالإيميل (`user_id` NULL) غير المحلولة أو المحلولة من أقل من 14 يوم، أحدث 5 → لكل وحدة `issue_guest_link(…, keep=0)` (إلغاء الكل + جديد) + إيميل لكل تذكرة (رقم H + الرابط). ما في تذاكر → ما بينبعت شي.
- **الحدود (tw_settings، أمنية، `sec_support`)** + `_public_rate` فوقها: `support_link_resend_email` 3 / ساعة (التجاوز → نفس الرد بدون إيميل، متل `pwreset_email`) · `support_link_resend_ip` 10 / ساعة → 429 · `support_guest_reply_ticket` 20 / ساعة لكل تذكرة → 429 · `support_track_ip` 60 / دقيقة على view / reply / resolve → 429 (قبل البحث عن الرمز).
- **الترويسات** على كل مسار `/support/track` (الصفحة والـ API، أي status): `Cache-Control: no-store` · `Referrer-Policy: no-referrer` · `X-Robots-Tag: noindex` (`security_headers` بـ `server.py`).
- ❌ الرمز الخام بالقاعدة / اللوج / الرد · ❌ الرمز بـ query string · ❌ رد مختلف لرمز منتهي عن غلط · ❌ رابط بيوصل لتذكرة حساب.

## الأدمن (`support.manage`)

1. `check_admin(request, SUPPORT_PERM)` أول شي بكل endpoint — بدون توكن / توكن مستخدم → 401 · توكن أدمن بدون الصلاحية → 403.
2. `GET /admin/support/tickets?status&category&priority&requester&q&sort&page&limit` — `requester` ∈ guest · user · `q` = رقم H بالضبط أو الإيميل (الزائر أو الحساب) · `sort` ∈ `newest` (الافتراضي — وقت الفتح) · `oldest_waiting` (أقدم رسالة أخيرة أولاً) · `priority` (urgent → high → normal) · قيمة غلط → 422. الرد فيه القوائم (`statuses` · `categories` · `priorities` · `sorts` · `requesters` · `next_statuses`).
3. `GET /admin/support/counts` → `{new}` (عدد التذاكر بحالة `new`).
4. `GET /admin/support/tickets/{public_id}` → صاحب التذكرة + `details` + `faq_id` + `legacy_category` + المحادثة.
5. `POST …/messages` `{body, next_status}` · `PUT /admin/support/tickets/{public_id}` `{status?, priority?, category?}` — تغيير التصنيف: أول تغيير لتذكرة `legacy_category` فيها NULL بيحفظ القيمة القديمة · تذكرة زائر بتضل `account` (422 `guest_category`).
6. **السجل:** `admin_audit_middleware` بس — `actor` · `action` (`admin_support_reply` / `admin_support_update`) · `target ticket=<public_id>` · `old_value` / `new_value` (`category=…;priority=…;status=…`). ❌ نص الرسالة أو الإيميل بالسجل.

## الواجهة (7.1 — ما انلمست بـ 7.2a)

- `/support` (`support.html` + `static/support/support.js`) · «مشكلة بالدخول؟» بصفحة الدخول (`TwSupportForm.guestOpen()`) · `admin-support.html` + `static/admin-support/admin-support.js`. النصوص بـ `tw_strings.json` (`support.*` · `admin.support.*` · `settings.item.support_*` · `email.support_guest_otp.*` · `email.support_guest_link.*`) — 7.2a زاد مفاتيح الحالات والتصنيفات الجديدة بس.

## ممنوعات

- ❌ قراءة / كتابة تذكرة أو رابط برّا `support.py` · ❌ انتقال حالة برّا `transition()` · ❌ توحيد قيم قديمة برّا `normalize_sql()` · ❌ كتابة قيمة قديمة (`open` / `closed` / `other`).
- ❌ `priority` من المستخدم أو الزائر (422) · ❌ تذكرة زائر بتصنيف غير `account` · ❌ تذكرة زائر بدون رمز.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py` + `tw_settings` · ❌ store rate تاني · ❌ IP من غير `get_client_ip`.
- ❌ أي حقل لكلمة سر أو OTP أو مستندات بـ `details` · ❌ مفتاح `details` برّا `FIELDS`.
- ❌ فحص حظر / تعليق على التذاكر · ❌ رد بيكشف إذا التذكرة لحساب تاني (404 بس).
- ❌ مرفقات · ❌ `innerHTML` بنص تذكرة · ❌ ربط تلقائي لتذكرة زائر بحساب.
