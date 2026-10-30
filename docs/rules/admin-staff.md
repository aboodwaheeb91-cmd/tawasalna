# Admin Staff Permissions (task 8.4a) + Staff Accounts & Two-Step Login (task 8.4b)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتلمس مسار أدمن (`/admin/*` · مسار اللوحة `/tw-ctrl-…` · `/admin-view` · `/admin-job`).
> المواصفة: `docs/SYSTEMS_INDEX.md` §25h · جلسة الأدمن: §25 · الـ shell: `docs/rules/admin-shell.md`.

## Admin Staff Rules (mandatory for all AI sessions)

1. **قائمة الصلاحيات بمكان واحد:** `admin_perms.py` — `GRANTABLE` (بتنعطى لتوكن موظف — خطة 8.4b) و `OWNER_ONLY` (للمالك بس). كل صلاحية = اسم + وصف عربي قصير. صلاحية جديدة = سطر بالملف + سطر بالجدول تحت بنفس الـ PR. ❌ قائمة صلاحيات تانية بأي ملف.

2. **ما في مسار أدمن بدون perm:** كل endpoint أدمن بينادي `check_admin(request, perm)` **أول سطر** و `perm` من `admin_perms.ALL`. `check_admin(request)` بدون perm = `TypeError` · perm مش بالقائمة = `RuntimeError` (خطأ برمجي → 500، مش 403). الاستثناءات بس بـ `admin_perms.UNGUARDED_ROUTES` مع سبب (صفحات HTML بدون بيانات · الدخول · الشعار العام). التست بيمشي على كل routes الـ app وبيفشل على أي مسار ما بينادي `check_admin` بالـ perm تبع الجدول.

3. **صلاحيات المالك ما بتنعطى:** `admin_perms.allows(perms, perm)` — القرار الوحيد: `"*"` بيمرق كل شي · perm من `OWNER_ONLY` بيمرق **بس** بـ `"*"` حتى لو مكتوب صراحة بـ `perms` التوكن · غير هيك لازم يكون بالتوكن. مفتاح إعداد أمني (`tw_settings.is_security`) بيحتاج `settings.security` (`tw_settings.SECURITY_PERM`) — للمالك بس.

4. **الإيميل والهاتف مخفيين افتراضياً — صلاحيتين مستقلتين:** بدون `users.email.view` ما في رد أدمن فيه إيميل مستخدم، وبدون `users.phone.view` ما في رد فيه رقم هاتف (وحدة ما بتكشف التانية · المالك `"*"` بيشوف الاتنين). كل رد أدمن ممكن يحمل إيميل أو هاتف بيمرق على `_admin_contacts(claims, data)` بـ `server.py` → `admin_perms.strip_contacts(data, email_ok, phone_ok)` (بأي عمق — dict و list)، والقرارين من الصلاحيات الفعلية (`allows`). **القاعدة اسم المفتاح، مش قائمة يدوية (task 8.4a2):** إيميل = `email` أو بيخلص بـ `_email` (`is_email_key` — `guest_email` · `details.account_email`) · هاتف = `phone` أو بيخلص بـ `_phone` (`is_phone_key` — `profile.phone` · `details.account_phone`؛ `phone_verified` / `email_verified` ما بينشالوا). الردود: قائمة المستخدمين (+ البحث الموحّد) · البروفايل (قراءة + رد التعديل — فيه `phone`) · التوثيق · الدعم (القائمة + التذكرة — `details`). البحث بإيميل بدون الصلاحية ما بيطابق: `/admin/users?q=` بيدوّر بالاسم و `tw_id` بس (`users_list(with_email=False)`) · `/admin/support/tickets?q=<email>` → صفر نتائج (`admin_list(email_search=False)`). **ما في بحث أدمن بالهاتف** (`/admin/users?q=` = اسم / `tw_id` / إيميل · `/admin/support/tickets?q=` = رقم H أو إيميل، غير هيك 422) — بحث هاتف جديد لازم يشترط `users.phone.view`. **أسرار OTP (`email_code` / `phone_code` / `phone_code_target` …) ما بترجع بأي رد أدمن ولا للمالك** — قائمة التوثيق allowlist (`_ADMIN_KYC_LIST_COLUMNS`، بدون `phone` كمان) والبروفايل ما بيقرأهم. التصدير CSV = `users.export` (للمالك). رد أدمن جديد فيه إيميل أو هاتف → لازم يمرق على `_admin_contacts`.

- ❌ `check_admin(request)` بدون perm · ❌ perm مكتوب برّا `admin_perms.py` · ❌ endpoint أدمن بيرجّع إيميل أو هاتف بدون `_admin_contacts` · ❌ حقل إيميل / هاتف بأي رد أدمن (أو بـ `support.FIELDS` نوع `email` / `phone`) اسمه ما بيطابق `email` / `*_email` / `phone` / `*_phone` · ❌ قائمة أسماء مفاتيح يدوية · ❌ `users.email.view` بتكشف هاتف أو العكس · ❌ سر OTP بأي رد أدمن · ❌ بحث بهاتف بدون `users.phone.view` · ❌ بحث بإيميل بدون `users.email.view` · ❌ إعطاء صلاحية من `OWNER_ONLY` لموظف.
## Admin Login + Staff Accounts Rules (task 8.4b — mandatory for all AI sessions)

5. **ما في توكن أدمن بدون الخطوتين:** `<panel>/login` نفس المسار بخطوتين. (أ) `{password}` = المالك (`ADMIN_TOKEN`) · `{email, password}` = موظف → `{step: "mfa", ticket}` — **مش** توكن. الـ ticket موقّع بـ `ADMIN_JWT_SECRET` بـ aud خاص (`tw-admin-mfa`، `typ: mfa_ticket`)، 5 دقايق، مربوط بالـ subject + `session_version` — `check_admin` ما بيقبله. (ب) `{ticket, code}` (رمز تطبيق المصادقة أو رمز استرداد) → `{token}`؛ بعد رمز استرداد الرد فيه `recovery_remaining`. (ج) المالك بدون تطبيق مربوط → الخطوة (أ) بترجّع `{step: "enroll", ticket, secret, otpauth_uri}` (السر بينحفظ مشفّر كـ «معلّق»)، وأول رمز صحيح بيربطه → `{token, recovery_codes}` (10 رموز — مرة وحدة).
6. **نفس الـ 401 لكل فشل:** إيميل مش موجود · كلمة سر غلط · موظف مش `active` · موظف بدون MFA · ticket غلط / منتهي / sv قديم · رمز غلط / مستعمل → نفس الرد (`{"error": "Unauthorized"}`) — إيميل مش موجود بيكلّف bcrypt متل كلمة السر الغلط. الأقفال (فشل بس، `tw_limits.RATES`): `admin_login_ip` / `admin_login_acct` (الخطوة أ) · `admin_mfa_ip` / `admin_mfa_acct` (الخطوة ب) → 429 حتى لو البيانات صح. فوقهم حد `rate_limit_middleware` العام للمسار. **الحجز ذرّي (task 8.4c-0):** كل خطوة بتحجز أقفالها (ip + acct مع بعض) بخطوة وحدة تحت `_rate_lock` **قبل** التحقق البطيء (bcrypt / القاعدة) — `_admin_reserve` → `_rate_reserve` (الدالة الوحيدة للفحص والعدّ لكذا سلة؛ `_rate_ok_all` = هي): أي قفل مليان → 429 وما بينحسب شي · غير هيك الحجز بينسجّل بكل المفاتيح، بيضل عند الفشل (هو العدّ) وبينشال عند النجاح (`_rate_release`). هيك طلبات متزامنة ما بتقدر تتجاوز الحد. مفاتيح أقفال الأدمن بـ `_RATE_NO_EVICT` (فيضان حسابات تانية ما بيمسح عدّاد المالك). ما في `/admin/step-up` لسا — أي خطوة تحقق جديدة لازم تمرق على `_admin_reserve`.
7. **TOTP + الأسرار — `admin_staff.py` بس:** RFC 6238 بمكتبة Python (SHA-1 · 6 أرقام · 30 ثانية · ±خطوة وحدة) · الخطوة بتنقبل مرة وحدة (`last_step` بيكبر بس — UPDATE ذرّي) · السر مشفّر Fernet بمفتاح مشتق (SHA-256) من `ADMIN_MFA_KEY` (≥ 32 حرف؛ ناقص → الدخول 503) · رموز الاسترداد 10، `secrets`، بتنحفظ SHA-256 بس، كل رمز مرة وحدة (`used_at`). **الـ ticket لمرة وحدة (task 8.4c-0):** فيه `jti` عشوائي · بينمسك وقت فحص الرمز (طلب متزامن بنفس الـ ticket → 401) · بعد أول توكن بينحرق (`_admin_ticket_take` / `_admin_ticket_done`) · إعادة استعماله → نفس الـ 401 الموحّد · الرمز الغلط ما بيحرقه (القفل بيحدّه). الحرق **بالذاكرة** تحت `_rate_lock` (TTL = عمر الـ ticket، تنظيف وقت الاستعمال، حد `mem_store_max_keys` — مليان = رفض، مش مسح) — replica وحدة، متل حدود الطلبات؛ النقل لمخزن مشترك بالخطوة 11. ❌ السر أو الرموز أو الـ ticket بـ localStorage / sessionStorage / URL / لوج / سجل.
8. **الجلسة بتنقرا من القاعدة بكل طلب (`check_admin`):** التوكن فيه `sv`. المالك (`role: admin`) → `sv` = `admin_owner_mfa.session_version`. الموظف (`role: staff`, `sub: staff:<id>`, `perms: []` بالتوكن) → صف `admin_staff`: `status = active` + MFA مربوط + `sv` مطابق، والصلاحيات الفعلية = (صلاحيات الدور ∪ `allow_perms`) − `deny_perms` ∩ `GRANTABLE` (`admin_staff.effective_perms`) — المنع فوق السماح، و `OWNER_ONLY` / `"*"` ما بيعيشوا أبداً. ما في تطابق → 401 · الصلاحية مش ضمن الفعلية → 403 · القاعدة واقعة → 503. إيقاف موظف / زيادة sv / تغيير دوره أو صلاحياته بينطبق على الطلب الجاي بنفس التوكن. `_admin_contacts` بيقرّر على نفس الصلاحيات الفعلية (الـ claims اللي بترجع من `check_admin`).
9. **السجل:** كل محاولة دخول (نجاح وفشل) بـ `admin_audit_log` — actor `owner` / `staff:<id>` / `-` (إيميل مش معروف أو ticket تالف)، action `admin_login` (الخطوة أ) · `admin_login_mfa` (الخطوة ب) · `admin_mfa_reset` (الاستعادة). ❌ كلمة سر / رمز / سر / ticket بالسجل.
10. **المالك بس بيدير الموظفين** (`staff.manage` — `OWNER_ONLY`). شاشة الموظفين والدعوة (`admin_invites`) والتحقق الإضافي = 8.4c. لهلق الموظف بينضاف بالقاعدة بس (التستات بتعمله seed).

- ❌ توكن أدمن من كلمة السر لحالها · ❌ صلاحيات موظف من التوكن · ❌ تطبيق TOTP / تشفير / كاتب حسابات أدمن تاني برّا `admin_staff.py` · ❌ نسخة تانية من شاشة الدخول · ❌ أي طريق استعادة للمالك غير اللي تحت.
- Test: `python -m pytest tests/test_admin_security_84c0.py -q` (task 8.4c-0 — HTTP حقيقي + PostgreSQL: التزامن (30 طلب) · ticket لمرة وحدة · كل مسار أدمن 401 / 403 بكل نوع توكن · تذاكر معدّلة / منتهية / سر تاني / aud تاني · نفس التوكن بالطلب الجاي بعد كل تغيير · ما في سر بلوج / سجل / رد) · مع `TW_SECURITY_TESTS_REQUIRED=1` (CI) أي skip بتستات الأمان = فشل (`tests/conftest.py`).
- Test: `python -m pytest tests/test_admin_mfa_84b.py -q` (قيم RFC 6238 · ±خطوة · المالك: ربط → رموز → توكن · كلمة السر لحالها · رمز مرة وحدة · رمز استرداد مرة وحدة · `ADMIN_MFA_RESET` اليوم بس · موظف: خطوتين + صلاحيات من القاعدة بكل طلب + الإيميل مخفي · نفس الـ 401 · 429 · السجل).

### الجداول (migration حرجة `admin_staff` — `admin_staff.migrate_admin_staff`)

| الجدول | الأعمدة |
|--------|--------|
| `admin_roles` | `id` · `name` UNIQUE · `perms text[]` · `created_at` |
| `admin_staff` | `id` · `email` (CHECK = lower + UNIQUE على `lower(email)`) · `name` · `password_hash` NULL · `role_id` NULL → `admin_roles` (SET NULL) · `allow_perms text[]` · `deny_perms text[]` · `status` invited / active / suspended · `mfa_secret_enc` NULL · `mfa_enabled_at` NULL · `mfa_last_step bigint` · `session_version` (1) · `created_at` · `last_login_at` |
| `admin_owner_mfa` | صف واحد (`id = 1`): `secret_enc` · `enabled_at` · `last_step` · `session_version` (1) · `reset_on date` (يوم `ADMIN_MFA_RESET` اللي انطبق — حتى ما ينعاد بنفس اليوم) |
| `admin_recovery_codes` | `subject` (`owner` / `staff:<id>`) · `code_hash` (SHA-256) · `used_at` |
| `admin_invites` | `token_hash` UNIQUE · `staff_id` → `admin_staff` (CASCADE) · `kind` invite / mfa_reset · `expires_at` · `used_at` — الجدول بس، الاستعمال بـ 8.4c |

### استعادة المالك (خطوة خطوة — ما في أي طريق تاني)

1. **ضيّعت الجهاز وعندك رموز الاسترداد:** ادخل بكلمة السر عادي → بشاشة الرمز اضغط «استعمل رمز استرداد» → اكتب رمز واحد. الرمز بينشطب، والشاشة بتقلّك كم ضل. (لربط جهاز جديد بدون ما تضيّع الرموز: استعمل الطريق 2.)
2. **ضيّعت الجهاز والرموز:**
   1. بـ Railway → Variables: غيّر `ADMIN_TOKEN` لقيمة جديدة (`openssl rand -hex 32`).
   2. ضيف `ADMIN_MFA_RESET` = تاريخ اليوم بتوقيت UTC بالشكل `YYYY-MM-DD` (مثال `2026-10-30`). Railway بيعيد التشغيل.
   3. ادخل بكلمة السر الجديدة: أول دخول ناجح بهداك اليوم بيمسح تطبيق المصادقة القديم ورموز الاسترداد، وبيزيد `session_version` (كل جلسات المالك القديمة بتطلع)، وبتطلعلك شاشة ربط جديدة → اربط → احفظ الرموز الجديدة.
   4. ارجع لـ Railway واحذف `ADMIN_MFA_RESET`.
   - تاريخ مش اليوم (مبارح / بكرا / شكل غلط) = ما بيصير شي. كلمة سر غلط = ما بيصير شي. بنفس اليوم بينطبق مرة وحدة بس (`reset_on`).
   - بينسجّل بالسجل (`admin_mfa_reset`، actor `owner`) + سطر لوج `[admin-auth] ADMIN_MFA_RESET applied`.

## مؤجّل (8.4c)

- شاشة الموظفين (إضافة / تعديل / إيقاف) + الدعوة بالإيميل (`admin_invites` kind `invite`) + إعادة ربط MFA لموظف (`mfa_reset`) + التحقق الإضافي. لهلق ما في واجهة لإضافة موظفين.

- `static/admin-support/admin-support.js` بيعرض `r.email` لتذكرة الزائر (`' · ' + r.email`) — بدون `users.email.view` الحقل غايب فبتطلع «undefined». لازم الصفحة تتعامل مع غيابه (ما تعرض شي / نص twT) — المهمة 8.4a سيرفر بس.

- Test: `python -m pytest tests/test_admin_perms_84a.py -q` (كل المسارات + سلوك `check_admin` بتوكنات حقيقية) · `python -m pytest tests/test_admin_email_view_84a.py -q` (PostgreSQL — الإيميل والبحث) · `python -m pytest tests/test_admin_email_keys_84a2.py -q` (حارس `support.FIELDS` email / phone + الإيميل والهاتف بكل تركيبة صلاحيات بنص الـ JSON كامل على users · profile · kyc · support + regex إيميل + ما في سر OTP حتى للمالك).

## الصلاحيات

| الصلاحية | المجموعة | الوصف |
|---------|---------|-------|
| `users.view` | قابلة للإعطاء | عرض المستخدمين وملفاتهم |
| `users.edit` | قابلة للإعطاء | تعديل ملفات المستخدمين وحذف عناصر منها |
| `users.suspend` | قابلة للإعطاء | تعليق الحسابات وإرجاعها |
| `users.email.view` | قابلة للإعطاء | رؤية إيميلات المستخدمين |
| `users.phone.view` | قابلة للإعطاء | رؤية أرقام هواتف المستخدمين (task 8.4a2 — مستقلة عن الإيميل) |
| `kyc.review` | قابلة للإعطاء | مراجعة طلبات التوثيق |
| `jobs.manage` | قابلة للإعطاء | إدارة الوظائف |
| `reports.manage` | قابلة للإعطاء | مراجعة البلاغات |
| `content.edit` | قابلة للإعطاء | النصوص والألوان والأخبار والشعار |
| `support.manage` | قابلة للإعطاء | تذاكر الدعم |
| `settings.edit` | قابلة للإعطاء | الإعدادات العادية وأزرار الإجراءات وقراءة إعدادات الإيميل + إيميل تجربة |
| `stats.view` | قابلة للإعطاء | لوحة القيادة والإحصائيات والنشاط |
| `message.send` | قابلة للإعطاء | إرسال رسالة لمستخدم |
| `users.delete` | المالك بس | حذف حساب |
| `users.type` | المالك بس | تغيير نوع الحساب |
| `users.password` | المالك بس | تغيير كلمة سر مستخدم |
| `users.email` | المالك بس | تغيير إيميل مستخدم |
| `users.export` | المالك بس | تصدير المستخدمين CSV |
| `settings.security` | المالك بس | الإعدادات الأمنية + تعديل إعدادات الإيميل (`PUT /admin/email`) |
| `audit.view` | المالك بس | السجل الأمني |
| `staff.manage` | المالك بس | إدارة فريق الإدارة (ما إلها مسار لسا — 8.4c) |
| `system.manage` | المالك بس | صيانة النظام وسجل الأخطاء |

## المسار → الصلاحية

| Method | المسار | الصلاحية |
|--------|--------|---------|
| GET | `/admin/users` | `users.view` (+ `users.email.view` للإيميل والبحث فيه) |
| GET | `/admin/profile/{user_id}` | `users.view` (+ `users.email.view` للإيميل · `users.phone.view` للهاتف) |
| PUT | `/admin/profile/{user_id}` | `users.edit` (الرد: + `users.email.view` / `users.phone.view`) |
| DELETE | `/admin/experience/{exp_id}` · `/admin/education/{edu_id}` · `/admin/course/{course_id}` | `users.edit` |
| PUT | `/admin/user/{user_id}/suspension` | `users.suspend` |
| GET | `/admin/kyc` · `/admin/kyc/{submission_id}/docs` | `kyc.review` |
| PUT | `/admin/kyc/{user_id}/approve` · `/admin/kyc/{user_id}/reject` · `/admin/user/{user_id}/verify` | `kyc.review` |
| GET | `/admin/jobs` · `/admin/jobs/{job_id}` · `/admin/jobs/{job_id}/delete-preview` | `jobs.manage` |
| PUT · DELETE | `/admin/jobs/{job_id}` | `jobs.manage` |
| POST | `/admin/jobs/{job_id}/hide` · `unhide` · `reactivate` · `extend` · `status` · `unarchive` | `jobs.manage` |
| GET · PUT | `/admin/reports` · `/admin/reports/{report_id}/resolve` | `reports.manage` |
| GET · PUT | `/admin/strings` · `/admin/theme/colors` | `content.edit` |
| GET · POST · PUT · DELETE | `/admin/news` · `/admin/news/{news_id}` | `content.edit` |
| POST | `/admin/logo` | `content.edit` |
| GET · POST · PUT | `/admin/support/tickets` · `/admin/support/counts` · `/admin/support/tickets/{public_id}` (+ `/messages`) | `support.manage` (+ `users.email.view` للإيميل والبحث فيه · `users.phone.view` لـ `details.account_phone`) |
| GET | `/admin/settings` | `settings.edit` |
| PUT · POST | `/admin/settings/{key}` · `/admin/settings/{key}/reset` | `settings.edit` — مفتاح أمني: `settings.security` |
| GET · PUT | `/admin/actions` | `settings.edit` |
| GET | `/admin/email` | `settings.edit` |
| POST | `/admin/email/test` | `settings.edit` |
| GET | `/admin/stats/summary` · `/admin/stats/timeseries` · `/admin/activity` | `stats.view` |
| POST | `/admin/message` | `message.send` |
| DELETE | `/admin/user/{user_id}` | `users.delete` |
| PUT | `/admin/user/{user_id}/type` | `users.type` |
| PUT | `/admin/user/{user_id}/password` | `users.password` |
| PUT | `/admin/user/{user_id}/email` | `users.email` |
| GET | `/admin/users/export` | `users.export` |
| GET | `/admin/audit` | `audit.view` |
| PUT | `/admin/email` | `settings.security` — بيغيّر `site_url` / `from_address`، و `site_url` مصدر روابط إعادة كلمة السر والتوثيق بالإيميلات (موظف ما لازم يقدر يحوّلها لموقع تاني) |
| GET | `/admin/errors` | `system.manage` |
| POST | `/admin/maintenance/migrate-data-images` · `/admin/pipeline/backfill` · `/admin/pipeline/migrate-index` | `system.manage` |
| GET | `/admin/pipeline/backfill/dry-run` | `system.manage` |
| — | تفاصيل الإكمال بـ `GET /profile/{id}/score` (توكن أدمن اختياري) | `users.view` |
| POST | `<panel>/login` | بدون — الدخول نفسه (خطوتين — task 8.4b، القواعد 5–9) |
| GET | `/admin/logo` | بدون — عام (الشعار بكل صفحة) |
| GET | `<panel>` · `/email` · `/settings` · `/content` · `/support` · `/admin-view` · `/admin-job` | بدون — صفحة HTML بس، البيانات من `/admin/*` بصلاحيتها |
