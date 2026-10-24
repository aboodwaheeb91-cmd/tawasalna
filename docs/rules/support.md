# Support Tickets — نظام الدعم (task 7.1 · 7.2a · 7.2b · 7.3)

> إلزامي بنفس قوة `CLAUDE.md` لأي مهمة بتلمس الدعم. Spec: `docs/SYSTEMS_INDEX.md §62` · `ARCHITECTURE.md §81` · migrations `docs/migrations/7.1_support_tickets.sql` · `7.2a_A_expand.sql` · `7.2a_B_migrate.sql` · `7.3_inbound.sql` · tests `python -m pytest tests/test_support_tickets.py -q` · `python -m pytest tests/test_support_guest_link.py -q` · `python -m pytest tests/test_support_inbound.py -q` · `node tests/test_support_pages_runtime.js`.
>
> **7.2a = Backend + واجهة (مهمتين).** ما في مرفقات. الواجهة: قسم «الواجهة» تحت.

## المصدر الوحيد

- **`support.py`** — الـ schema (`SCHEMA_SQL` = الشكل النهائي للـ DB الجديدة والـ CI، `migrate_support` = `CREATE … IF NOT EXISTS` بس، migration اختيارية `support_tickets`) · كل قراءة وكتابة للتذاكر وروابط الزائر · `transition()` (الانتقالات) · `normalize_sql()` (توحيد القيم القديمة) · `clean_details()` / `clean_faq()` · `issue_guest_link()` · القوائم الثابتة `CATEGORIES` · `STATUSES` · `PRIORITIES` · `FIELDS` · `FAQ_IDS` · `REOPEN_DAYS = 14`. `server.py` بيتحقق من المدخلات والحدود والصلاحية وبينادي هالدوال بس.
- **الجداول:** `support_tickets` (`public_id` · `user_id` NULL للزائر · `guest_email` · `category` · `status` · `priority` · `subject` · `details` JSONB · `faq_id` · `legacy_category` · `created_at` · `updated_at` · `last_message_at` · `closed_at` = وقت الحل) · `support_messages` (`ticket_id` · `author_type` user / guest / admin · `author_id` · `body` · `created_at`) · `support_guest_otp` (رمز الزائر) · `support_guest_access` (رابط المتابعة — hash بس) · `support_reply_tokens` (رمز Reply-To — hash بس، 7.3) · `support_inbound_events` (منع تكرار البريد الوارد، 7.3) · `support_tickets.source` (`web` / `email`، 7.3). RLS مفعّل (`rls_lockdown` بتغطي كل جدول بـ `public` تلقائياً) بدون أي صلاحية لـ `anon` / `authenticated`.
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

- **الزائر:** `GUEST_CATEGORY = account` بس (السيرفر + `CHECK`) — إلا تذكرة البريد الوارد (`source = email` → `general`، والأدمن بيقدر يغيّر تصنيفها — 7.3).
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

## إشعارات الرد (task 7.2b)

رد الأدمن (`POST /admin/support/tickets/{public_id}/messages`) → `support.admin_reply` بيرجّع `(old, new, notice)` (`ticket_id` · `public_id` · `message_id` · `user_id` · `guest_email` — بدون نص الرد) → `_support_reply_notice` بـ `server.py` **بعد الـ commit وبعد الرد** (`BackgroundTasks`).

1. **تذكرة زائر:** `support.issue_guest_link(ticket_id, keep=3)` → رابط جديد وبيضلوا آخر 3 فعّالين + إيميل `support_guest_reply` (`ticket` · `link`) — «يوجد رد جديد على طلبك H…» + زر الرابط. **بدون نص الرد.**
2. **تذكرة حساب:** جرس عبر `auth.create_notification` — النوع `support_reply` · `entity_type = support_ticket` · `event_key = support_reply:support_ticket:{ticket_id}:{message_id}` (إشعار واحد لكل رسالة، التكرار ما بيعمل شي) · الرابط من الـ backend `support.ticket_path(public_id)` = `/support?ticket=H…` (`support.js` بيفتح التذكرة؛ تذكرة غيرك = 404 من السيرفر) · النص `notif.support_reply.title` / `.body` من `tw_strings`. + إيميل `support_reply` منفصل (`name` · `ticket` · `link`) عبر `auth.email_notify_user` → `send_email`.
3. **SECURITY:** القالبين ما بيتأثروا بتفضيلات المستخدم ولا بحدود الإشعارات، والجرس كمان ما بيتأثر بالتفضيلات. `support_reply` **مش** بـ `NOTIFICATION_EMAIL_TEMPLATES` / `NOTIFY_TYPES` → إيميل واحد بس (السبب: `docs/rules/email.md` البند 9).
4. **الفشل:** أي خطأ (إيميل / إشعار / رابط) → سطر لوج `[support] reply notice …` (نوع الخطأ أو `code` بس — بدون إيميل ولا رمز ولا رابط) والرد بيضل 200.
5. **`support_guest_link` أو `support_guest_reply` مطفي (أو المزوّد مش جاهز):** الرد ناجح · ما بينصدر رابط ولا بينلغى رابط · سطر لوج بس.
6. الرمز الخام بيروح للإيميل بس — ❌ بأي رد API أو لوج. ❌ ربط تلقائي لتذاكر الزائر بالحساب.
- Test: `python -m pytest tests/test_support_reply_notice.py -q`.

## البريد الوارد (task 7.3 — Resend Receiving)

قرار زعتر: إيميل جديد على `info@` أو `support@tawasolna.com` = تذكرة جديدة · الرد على إيميل دعم = رسالة على نفس التذكرة.

1. **المسار** `POST /webhooks/resend/inbound` (حدث `email.received` بس) + `_public_rate`. `RESEND_WEBHOOK_SECRET` غايب → 503 · الجسم أكبر من `support_inbound_request_max` → 413 · توقيع Svix غلط أو timestamp أبعد من 5 دقايق → 401 (قبل أي DB) — `email_service.verify_webhook` (hmac من مكتبة بايثون، بدون اعتمادية). الجسم الخام بـ `await` والباقي بـ `asyncio.to_thread`.
2. **مفتاح الإطفاء** `email_settings.types.support_inbound` (`PUT /admin/email` — متل `support_guest_link`) · **الافتراضي مطفي** · مطفي = 200 بدون أي أثر.
3. **منع التكرار:** `support_inbound_events` (`svix_id` UNIQUE + `email_id` UNIQUE) بنفس transaction التذكرة / الرسالة · نفس الحدث مرتين = 200 بدون أثر. ما فيه إيميل ولا نص.
4. **الفلترة:** المستلم `info@` / `support@` / `support+<token>@` بس (غيره 200 وتجاهل) · From فاضي / `mailer-daemon` / `postmaster` · `Auto-Submitted` ≠ `no` · نص فاضي → تجاهل. ❌ أي رد تلقائي على بريد وارد.
5. **المحتوى:** الحدث ما فيه النص → `email_service.fetch_received(email_id)` (Resend `GET /emails/receiving/{id}` بـ `RESEND_API_KEY`) — فشل → 503 (Resend بيعيد). نص عادي بس: `text`، وإلا HTML بدون أي وسم (و `script` / `style` بمحتواهم) · قص بـ `support_body_max` / `support_subject_max` · ❌ المرفقات · ❌ نص / إيميل / رمز بالـ logs (`[support] inbound <outcome>` بس). **صلاحية المفتاح:** مفتاح Resend «Sending access» بيبعت بس — القراءة بدها «Full access» (F30 — مبلَّغ، ما في مفتاح جديد).
6. **إيميل جديد = تذكرة زائر دايماً** (`support.inbound_new_ticket`): `guest_email` = From (lower) · `category = general` · `source = email` · الموضوع مقصوص، فاضي → `support.inbound.no_subject` · ❌ ربط بحساب. إيميل مطابق لحساب → `requester.matches_account` بصندوق الأدمن («مطابق لحساب (غير مؤكَّد)») تلميح بس. حد `support_inbound_sender` (لكل مرسل) + `support_inbound_global` (سقف عام) — التجاوز = تجاهل.
7. **الرد** (`support.inbound_reply`): كل إيميل دعم صادر (`support_reply` · `support_guest_reply` · `support_guest_link`) بيحمل `Reply-To: support+<token>@tawasolna.com` — `support.issue_reply_token` (الكاتب الوحيد): `secrets.token_hex(16)` لكل إيميل، sha256 بس، آخر 5 لكل تذكرة. بريد على `support+<token>@` = رسالة على تلك التذكرة **بشرط From = إيميل صاحبها** (`users.email` للحساب أو `guest_email`)، غير هيك تجاهل · `author_type` user / guest حسب التذكرة · نفس `_requester_reply` (in_review · إعادة فتح خلال 14 يوم · `support_open_max`) — رفض = تجاهل · **حساب معلّق** (`blocks_suspension.is_suspended` بنفس الـ transaction) → تجاهل `ignored_suspended` بدون رسالة (متل الـ 401 بالموقع). ❌ رقم H وحده كتفويض. رد الأدمن على تذكرة بريد = إشعار 7.2b (رابط متابعة جديد + `support_guest_reply`).
8. **الإنتاج:** `docs/migrations/7.3_inbound.sql` بإيد زعتر قبل الدمج (فحص قراءة بـ UNION ALL · التغيير · فحص بعدي · رجوع). كود الإقلاع بينشئ الجدولين الجداد بس.
- ❌ تذكرة من بريد بحساب · ❌ رد من بريد بدون رمز + From صاحب التذكرة · ❌ رد تلقائي · ❌ مرفقات · ❌ تحقق توقيع بمكتبة خارجية أو برّا `email_service`.
- Test: `python -m pytest tests/test_support_inbound.py -q`.

## الأدمن (`support.manage`)

1. `check_admin(request, SUPPORT_PERM)` أول شي بكل endpoint — بدون توكن / توكن مستخدم → 401 · توكن أدمن بدون الصلاحية → 403.
2. `GET /admin/support/tickets?status&category&priority&requester&q&sort&page&limit` — `requester` ∈ guest · user · `q` = رقم H بالضبط أو الإيميل (الزائر أو الحساب) · `sort` ∈ `newest` (الافتراضي — وقت الفتح) · `oldest_waiting` (أقدم رسالة أخيرة أولاً) · `priority` (urgent → high → normal) · قيمة غلط → 422. الرد فيه القوائم (`statuses` · `categories` · `priorities` · `sorts` · `requesters` · `next_statuses`).
3. `GET /admin/support/counts` → `{new}` (عدد التذاكر بحالة `new`).
4. `GET /admin/support/tickets/{public_id}` → صاحب التذكرة + `details` + `faq_id` + `legacy_category` + المحادثة.
5. `POST …/messages` `{body, next_status}` · `PUT /admin/support/tickets/{public_id}` `{status?, priority?, category?}` — تغيير التصنيف: أول تغيير لتذكرة `legacy_category` فيها NULL بيحفظ القيمة القديمة · تذكرة زائر من الموقع بتضل `account` (422 `guest_category`) — تذكرة البريد الوارد (7.3) بتقبل أي تصنيف.
6. **السجل:** `admin_audit_middleware` بس — `actor` · `action` (`admin_support_reply` / `admin_support_update`) · `target ticket=<public_id>` · `old_value` / `new_value` (`category=…;priority=…;status=…`). ❌ نص الرسالة أو الإيميل بالسجل.

## الواجهة (7.2a واجهة — بدون تغيير بالـ API)

- **الملفات:** `support.html` + `static/support/support.js` · `support-track.html` + `static/support/support-track.js` · `admin-support.html` + `static/admin-support/admin-support.js` · القطع المشتركة بـ `static/support/support-form.js` (`TwSupportForm`: `field` · `detailFields` · `ticketForm` · `thread` · `resendForm` · `guestOpen`) — نموذج واحد للمسجّل والزائر (صفحة الدعم + نافذة «مشكلة بالدخول؟» بصفحة الدخول).
- **`/support` عامة** (بدون `twRequireAuth`) — الجلسة من `TwAuthSync.getSessionSnapshot()` بس:
  - الأسئلة الشائعة لكل الزوار من `GET /support/meta` (ترتيب التصنيفات والأسئلة = ترتيب السيرفر) · النص `twT('support.faq.{cat}.{id}.q|a')` كنص (`textContent`) · بحث محلي بالسؤال والجواب.
  - تحت كل جواب «لم تُحلّ مشكلتي» ← النموذج بالتصنيف + `faq_id` معبّيين (تغيير التصنيف بيشيل `faq_id` إذا مش من التصنيف الجديد).
  - المسجّل: أي تصنيف · قائمة طلباته بحالات المستخدم (`support.status_user.*`: وصلنا طلبك · قيد المراجعة · نحتاج معلومات منك · تم الحل) + المحادثة + الرد + «تم الحل» (`POST …/close`، `twConfirm` قبل).
  - الزائر: «الدخول والحساب» بس (`meta.guest_category`) بمسار OTP الموجود · أسئلة التصنيفات التانية ← رابط دخول `twLoginHref('/support')` · بعد الإرسال «أرسلنا رابط المتابعة إلى بريدك» + رقم H — الرابط ما بينعرض أبداً · «فقدت رابط المتابعة؟» ← إيميل ← `POST /support/track/resend` ← نفس الرسالة العامة دائماً.
  - الحقول الاختيارية من `meta.fields[category]`: `enum` → قائمة (`support.field.{key}.{value}`) · `date` → قوائم يوم / شهر (`date.month.*`) / سنة (`TW.fillFoundedYears`) — نص جزئي = خطأ بالصفحة · غيرها → حقل بالـ `max` من meta. ثابت تحت النموذج: «لا تكتب كلمة المرور أو أي رمز تحقق» · تحت إيميل الزائر: «بريد تستطيع الوصول إليه…».
- **`/support/track`:** الرمز من `location.hash` (`#t=…`) مرة وحدة ← `history.replaceState` بيمسحه من الشريط ← بالذاكرة وبالـ POST body بس · الحالة والرسائل والرد و«تم الحل» من `TwSupportForm.thread` · بدون رمز / 404 → رسالة عامة + «إعادة إرسال الرابط» · `<meta name="robots" content="noindex">` + `<meta name="referrer" content="no-referrer">` بالصفحة فوق ترويسات السيرفر.
- **الأدمن:** فلاتر الحالة · التصنيف · الأولوية · زائر / مسجّل · الترتيب (القوائم من رد السيرفر) + بحث برقم H أو الإيميل (`q`؛ 422 → رسالة) · التذكرة: `details` كنص (قيمة القائمة بتسميتها) · `faq_id` = السؤال نفسه (التصنيف من `GET /support/meta`) · `legacy_category` · الرد بزرّين من `next_statuses` («نحتاج معلومات» = awaiting_user · «تم الحل» = resolved) · الحالة / الأولوية / التصنيف بحفظ واحد (تصنيف تذكرة الزائر مقفول) — كله عبر `TwAdminShell.run` (تأكيد قبل).
- **badge** `support` بـ `admin-sections.js` ← `BADGE_SOURCES.support` = `GET /admin/support/counts` (`new`) بـ `permissionAware` (أدمن بدون `support.manage` = بدون badge والجلسة بتضل).
- **الروابط:** القائمة ☰ للكل (زائر + مسجّل) (`_TW_HEADER_MENU_POLICY` key `support`) · سطر «تواصل مع الدعم» بـ `/settings` (قسم «المساعدة») · أسفل `landing.html` للزوار.
- ❌ `innerHTML` لأي نص من API أو `tw_strings` · ❌ الرمز بـ query string أو storage أو بالشريط بعد القراءة · ❌ رابط المتابعة بأي رد / صفحة · ❌ رقم حد بالكود (الـ `max` من meta / `twLimit`).
- Test: `node tests/test_support_pages_runtime.js` · نصوص الأسئلة: `python tests/test_strings_system.py` (G).
- النصوص بـ `tw_strings.json` (`support.*` · `support.faq.*` · `support.field.*` · `support.status_user.*` · `admin.support.*` · `menu.support` · `settings.support` · `settings.item.support_*` · `email.support_guest_otp.*` · `email.support_guest_link.*` · `email.support_guest_reply.*` · `email.support_reply.*` · `notif.support_reply.*`).

## ممنوعات

- ❌ قراءة / كتابة تذكرة أو رابط برّا `support.py` · ❌ انتقال حالة برّا `transition()` · ❌ توحيد قيم قديمة برّا `normalize_sql()` · ❌ كتابة قيمة قديمة (`open` / `closed` / `other`).
- ❌ `priority` من المستخدم أو الزائر (422) · ❌ تذكرة زائر بتصنيف غير `account` · ❌ تذكرة زائر بدون رمز.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py` + `tw_settings` · ❌ store rate تاني · ❌ IP من غير `get_client_ip`.
- ❌ أي حقل لكلمة سر أو OTP أو مستندات بـ `details` · ❌ مفتاح `details` برّا `FIELDS`.
- ❌ فحص حظر / تعليق على التذاكر · ❌ رد بيكشف إذا التذكرة لحساب تاني (404 بس).
- ❌ مرفقات · ❌ `innerHTML` بنص تذكرة · ❌ ربط تلقائي لتذكرة زائر بحساب.
