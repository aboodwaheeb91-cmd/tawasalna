# خريطة الحالات والتحكم لكل كيان — ADMIN ENTITY MAP (task 5.3m)

> **الهدف:** قبل بناء تحكم الأدمن — لكل كيان بالموقع: شو حالاته، مين بيشوفه، شو بيقدر يعمل فيه، وشو الأدمن بيقدر يعمل هلق وشو ناقص.
> **المصدر:** الكود الحقيقي فقط (`auth.py` · `server.py` · `admin_insights.py` · `static/admin/admin.js` · `static/admin-view/admin-view.js`) — مش التوثيق القديم. أرقام الأسطر تقريبية (حالة `main` بتاريخ 2026-10-15).
> **توثيق فقط:** هالملف ما بيغيّر أي سلوك. المشاكل اللي انلقت مسجّلة بقسم «مشاكل لقيتها» — المشطوبة انصلحت (task 5.0c: #2 #3 #4 #5 #6 #10 #11 #12 #16 #17)، الباقي مفتوح.
> **شاشة الأدمن:** «لوحة» = `admin.html` + `static/admin/admin.js` (أقسام `admin-sections.js`: المستخدمون · الشركات · الوظائف · التوثيق · البلاغات · السجل · الأخطاء · الإيميل · النظام). «صفحة المستخدم» = `admin-view.html` + `static/admin-view/admin-view.js`.
> **مفتاح الأدوار:** زائر = بدون جلسة · صاحبه = المالك (JWT `user_id`) · الشركة = حساب `co` (و `edu` حيث الكود بيسمح `co`/`edu`) · المتقدم = الحساب الشخصي `emp` · الأدمن = admin JWT (`check_admin`).
> **السجل الأمني:** كل `POST/PUT/PATCH/DELETE` تحت `/admin/` بيتسجّل تلقائياً بـ `admin_audit_log` (`server.py → admin_audit_middleware`) — بدون الـ body (يعني ما في «قبل / بعد»).

---

## فهرس الكيانات

1. [الحسابات (حساب شخصي / حساب شركة / حساب جهة تعليمية)](#1-الحسابات)
2. [الوظائف](#2-الوظائف--jobs) ← **الأولوية الأولى**
3. [طلبات التوظيف](#3-طلبات-التوظيف--job_applications)
4. [مراحل التوظيف (Pipeline)](#4-مراحل-التوظيف--job_pipeline_entries)
5. [بنك المواهب + تصنيف المرشحين لكل وظيفة](#5-بنك-المواهب--company_saved_candidates--company_candidate_job_refs)
6. [المواعيد](#6-المواعيد--appointments)
7. [المنشورات](#7-المنشورات--company_posts)
8. [التعليقات](#8-التعليقات--company_post_comments)
9. [الرسائل](#9-الرسائل--messages)
10. [البلاغات](#10-البلاغات--reports)
11. [التوثيق (KYC)](#11-التوثيق-kyc--kyc_submissions)
12. [الأخبار](#12-الأخبار--news_posts)
13. [الخبرات / الشهادات / الدورات / المهارات / اللغات / الروابط](#13-الخبرات--الشهادات--الدورات--المهارات--اللغات--الروابط)
14. [الإشعارات](#14-الإشعارات--notifications)
15. [المتابعة + الاهتمام + المشاهدات](#15-المتابعة--الاهتمام--مشاهدات-البروفايل)
16. [تقييمات الشركات](#16-تقييمات-الشركات--company_ratings)
17. [اقتراحات المهن](#17-اقتراحات-المهن--profession_suggestions)
18. [مهام المجدول](#18-مهام-المجدول--scheduler_jobs)
19. [كيانات تانية (بدون حالات — للعلم)](#19-كيانات-تانية-بدون-حالات)
20. [مشاكل لقيتها](#20-مشاكل-لقيتها)
21. [جدول الأولويات المقترح](#21-جدول-الأولويات-المقترح)

---

## 1. الحسابات

**الجداول:** `users` (`auth.py → init_db`) + `profiles` (1:1) + `company_profiles` (1:1 للشركة).

### 1.1 الحالات

| الحالة | المصدر (عمود / دالة) | مخزّنة / محسوبة |
|---|---|---|
| نوع الحساب `emp` / `co` / `edu` | `users.user_type` | مخزّنة |
| موجود (فعّال) | وجود الصف بـ `users` + `deleted_at IS NULL` | — لا يوجد `status` |
| معلّق (task 5.4) | `users.suspended_at` (+ `suspended_reason` / `suspended_by` — للأدمن بس) — كل طلباته 401 + محتواه مخفي بالاستعلام · `docs/rules/blocks-suspension.md` | مخزّنة |
| موثّق (شارة عامة) | `profiles.is_verified` — **المصدر الوحيد** (5.0c): بيطلع بالبروفايل العام والوظائف والأدمن · الكاتب الوحيد `auth.set_user_verified` (موافقة KYC · رفض KYC · توثيق / إلغاء يدوي) | مخزّنة |
| ~~موثّق (KYC)~~ | `users.is_verified` — legacy: ما حدا بيكتبه ولا بيقراه (5.0c) | — |
| شركة موثّقة | `company_profiles.verified_co` — بينقرأ بس، **ما في ولا كاتب** (F30 — مفتوح) | مخزّنة (دايماً FALSE) |
| الإيميل / الجوال موثّق | `users.email_verified` / `users.phone_verified` (من KYC OTP) | مخزّنة |
| نسخة الجلسة | `users.session_version` + `password_changed_at` — تغيير كلمة السر بينهي الجلسات | مخزّنة |
| محذوف (task 8.5a — ناعم) | `users.deleted_at` (+ `deleted_by` / `deleted_kind` `admin`\|`self` / `deleted_reason` — للأدمن بس) — كل طلباته 401 + محتواه مخفي بنفس قاعدة التعليق + السجلات المشتركة باسم «حساب محذوف» · الصف ما بينمسح · `docs/rules/account-deletion.md` | مخزّنة |
| محذوف نهائياً (task 8.5c) | `users.purged_at` + طابور `account_purge` (`files` → `db` → `done`) — بعد `account_purge_days` (30) من `deleted_at` · tombstone (`id` · `user_type` · `deleted_at` · `deleted_kind` · `purged_at`) والإيميل حر · `docs/rules/account-deletion.md` «الحذف النهائي» | مخزّنة |

### 1.2 مين بيشوف شو

| الدور | بيشوف | بيقدر يعمل |
|---|---|---|
| زائر | `/u/{tw_id}` — Tier 1 العام (`project_public_profile`) | يبلّغ (بعد الدخول) |
| صاحبه | Tier 2 (`GET /profile/{id}/full`) + KYC Tier 3 | يعدّل البروفايل · كلمة السر · الإيميل · **بيحذف حسابه حذف ناعم** (task 8.5d — `DELETE /auth/user/{id}/delete` بكلمة السر + «حذف» → `ad.soft_delete(kind='self')`) وبيستعيده ضمن المهلة من صفحة الدخول (`POST /auth/restore`) |
| حساب تاني مسجّل | نفس الزائر + متابعة / مراسلة / اهتمام | — |
| الأدمن | كل البروفايل (`GET /admin/profile/{id}`) · قائمة كل الحسابات (`GET /auth/users` — بدون pagination) | تحت |

### 1.3 الانتقالات

| من → إلى | مين | كيف |
|---|---|---|
| (لا شي) → موجود | المستخدم | `POST /auth/register` |
| غير موثّق ↔ موثّق (شارة) | الأدمن | `PUT /admin/user/{id}/verify` `{is_verified: true\|false}` (إلزامي) → `set_user_verified` |
| غير موثّق → موثّق (KYC) | الأدمن | `PUT /admin/kyc/{id}/approve` (طلب بانتظار المراجعة بس — غير هيك 409) → `set_user_verified(TRUE)` · الرفض → FALSE |
| نوع → نوع | الأدمن | `PUT /admin/user/{id}/type` |
| موجود → محذوف | الأدمن (`DELETE /admin/user/{id}` `{reason?}`) + صاحبه (8.5d) | **حذف ناعم** (task 8.5a — `ad.soft_delete`): `deleted_*` + `session_version + 1` · شركة: وظائفها المفتوحة بتتسكّر + إشعار واحد لكل متقدم · المقابلات القادمة بتنلغى · مسار صاحبه `DELETE /auth/user/{id}/delete` (task 8.5d — كلمة السر + «حذف»، نفس الأثر) · الاستعادة: حذف الأدمن بالأدمن بس، حذف صاحبه بصاحبه ضمن المهلة |
| محذوف → محذوف نهائياً (task 8.5c) | تلقائي — المهمة اليومية `account_purge` بعد `account_purge_days` (30) من `deleted_at` | الملفات بالتخزين أول (إعادة محاولة بتأخير متزايد، 404 = نجاح) ← القاعدة بـ transaction وحدة ← صف `users` tombstone (الإيميل حر · `purged_at`) · الاستعادة بعد البدء 409 · الجدول: `docs/rules/account-deletion.md` «الحذف النهائي» |
| محذوف → موجود | الأدمن بس (`POST /admin/user/{id}/restore` `{reason}` إجباري) | `ad.restore` — المحتوى بيرجع · التوكنات القديمة بتضل 401 · الوظائف بتضل مسكّرة والمقابلات ملغاة |
| تلقائي | — | لا يوجد أي انتقال تلقائي |

### 1.4 الأدمن هلق

| الإجراء | Endpoint | شاشة |
|---|---|---|
| قائمة الحسابات | `GET /auth/users` | ✅ لوحة → المستخدمون / الشركات |
| عرض / تعديل البروفايل | `GET` / `PUT /admin/profile/{id}` | ✅ صفحة المستخدم |
| توثيق / إلغاء توثيق (شارة) | `PUT /admin/user/{id}/verify` | ✅ صفحة المستخدم (الاتنين) |
| تغيير النوع | `PUT /admin/user/{id}/type` | ✅ صفحة المستخدم (كتابة «تغيير») |
| تغيير كلمة السر | `PUT /admin/user/{id}/password` — نفس `_password_policy_error` (ضعيفة → 422) | ✅ صفحة المستخدم |
| حذف (ناعم — task 8.5a) | `DELETE /admin/user/{id}` `{reason?}` (`users.delete` + التحقق الإضافي) | ✅ صفحة المستخدم (سبب اختياري + كتابة «حذف») · القائمة · البلاغات |
| استعادة (task 8.5a) | `POST /admin/user/{id}/restore` `{reason}` | ✅ صفحة المستخدم (شارة «محذوف» + التاريخ + النوع + السبب) |
| حذف نهائي (task 8.5c) | ما في endpoint — المهمة اليومية `account_purge` بس | ✅ صفحة المستخدم: شارة «محذوف نهائياً» / «الحذف النهائي جارٍ» (`deletion.purge`) بدون زر استعادة · الاستعادة 409 `purging` / `already_purged` |
| تعليق / فك تعليق (task 5.4) | `PUT /admin/user/{id}/suspension` `{suspended, reason?}` | ✅ صفحة المستخدم |
| «رسالة للمستخدم» | `POST /admin/message` | ✅ شاشة — **بس الـ endpoint ما بيبعت شي** (مشكلة #9) |

### 1.5 ناقص للتحكم الكامل

- ~~إيقاف / تعليق حساب~~ — انعمل (task 5.4: `users.suspended_at` + فحص الجلسة + الدخول + `_ws_revoke_user`).
- ~~حذف ناعم + إرجاع الحساب (F27)~~ — انعمل (task 8.5a). ~~الحذف النهائي~~ — انعمل (task 8.5c). ~~حذف الحساب لصاحبه + «استعادة حسابي»~~ — انعمل (task 8.5d).
- ~~مصدر واحد للتوثيق (مشكلة #4)~~ — انعمل (5.0c). باقي: `company_profiles.verified_co` بلا كاتب.
- تعديل الإيميل / الاسم من الأدمن (`PUT /admin/profile` بيمشي على قواعد `_apply_profile_update` بس).
- pagination + فلترة لقائمة الحسابات.
- إنهاء جلسات الحساب بدون تغيير كلمة السر.

### 1.6 ملاحظات خطر

- البلاغات ضد الحساب **ما بتنمسح** (5.0c — `reported_id` SET NULL، اللوحة بتبيّن «حساب محذوف»).
- **الحذف النهائي (task 8.5c):** ما بيمسح صف `users` (tombstone) فالـ CASCADE ما بيشتغل — كل جدول بقرار صريح (حذف / تجهيل / بيضل) بـ `docs/rules/account-deletion.md` «الحذف النهائي»، وملفات Storage (أفاتار / غلاف / وثائق KYC + القديمة `{uid}_…`) بتنحذف قبل القاعدة. **المسار القديم (قبل 5.0e) كان بيمسح بـ CASCADE:** profiles · company_profiles · experience / education / courses / skills / langs / links · jobs (→ طلباتها، refs، targets) · job_applications · messages (الطرفين) · notifications · company_posts (→ تعليقات، تقديرات، حفظ، مشاهدات) · تعليقات الشخص على منشورات غيره · company_ratings (اللي عطاها واللي أخدها) · profile_follows / interests / views · company_saved_candidates · job_pipeline_entries (→ stage events + notes) · candidate_bank_notes · appointments (→ participants / events / messages) · kyc_submissions · password_reset_tokens · company_settings · company_branches. ملفات Storage (أفاتار / غلاف / وثائق KYC) **ما بتنحذف**.
- تغيير النوع (`co` → `emp` مثلاً): الوظائف والمنشورات والـ pipeline بتضل مربوطة بحساب صار `emp`؛ `tw_id` بيضل ببادئته القديمة (C/U/T) — حالة متضاربة.
- ~~ما في حالة «معلّق»~~ — في «معلّق» (5.4) و«محذوف ناعم» قابل للاستعادة (8.5a).

---

## 2. الوظائف — `jobs`

**الأعمدة الحالية:** `status` (`active` / `paused` / `closed`) · `expires_at` · `duration_days` (3 / 7 / 14 / 30 — `_ALLOWED_DURATIONS`) · `paused_at` · `closed_at` · `archived_at` + `archived_by` · `views`. · `admin_hidden_at` + `admin_hidden_reason` (5.3j — إخفاء الأدمن)

### 2.1 الحالات

| الحالة | المصدر | مخزّنة / محسوبة |
|---|---|---|
| `active` — نشطة، بتستقبل طلبات | `jobs.status='active'` و `expires_at` لسا ما خلص | مخزّنة |
| `paused` — موقوفة مؤقتاً — **المدة مجمّدة** (5.3j #7) | `jobs.status='paused'` + `paused_at` | مخزّنة |
| `closed` — مغلقة (يدوياً أو انتهت مدتها) | `status='closed'` + `closed_at` **أو** `active` و `expires_at` مضى (< 30 يوم) | مخزّنة أو **محسوبة** — `_eff_status()` (`auth.py`) + توأمها بالـ SQL `job_eff_status_sql()` (5.3j) |
| `expired` — انتهت صلاحيتها (30 يوم بعد الإغلاق) | `_eff_status()`: مرجع الإغلاق + 30 يوم | **محسوبة فقط** (`effective_status` بالرد) |
| مؤرشفة (محذوفة من الشركة) | `jobs.archived_at IS NOT NULL` — مستقلة عن `status` | مخزّنة |
| مخفية من الإدارة (5.3j) | `jobs.admin_hidden_at IS NOT NULL` + `admin_hidden_reason` — مستقلة عن `status` | مخزّنة |
| محذوفة نهائياً | `DELETE FROM jobs` (أدمن بس) | — |

> `status` بالـ DB ممكن يضل `active` لوظيفة فعلياً `closed` / `expired` — الحقيقة بـ `effective_status` المحسوبة. **من 5.3j:** أي فلترة «نشطة» بالسيرفر = `job_active_sql()` (فيد · `/home/feed` · `jobs_count` صفحة الشركة · `/stats` · لوحة القيادة · الاقتراحات) — ❌ `status='active'` لحاله.

### 2.2 مين بيشوف شو

| الحالة | زائر / حساب شخصي | الشركة صاحبتها | المتقدم عليها | الأدمن |
|---|---|---|---|---|
| active | بالفيد العام (`GET /jobs` · `/home/feed`) + صفحة الشركة + `/job-detail` · يقدّم | إيقاف · إغلاق · أرشفة · المتقدمون | بيشوفها بـ «طلباتي» | ✅ `GET /admin/jobs` (كل الحالات — 5.3j) |
| paused | مش بالفيد · بصفحة الشركة (ما بيقدر يقدّم) · `/job-detail` | استئناف · إغلاق · أرشفة | بطلباته | ✅ تبويب «موقوفة» (5.3j) |
| closed | مش بالفيد · مش بصفحة الشركة (بتنعدّ بـ `closed_count`) · `/job-detail` بيفتح (التقديم مرفوض) | أرشفة · المتقدمون | بطلباته | ✅ تبويب «مغلقة» (5.3j) |
| expired | متل closed | أرشفة بس | بطلباته | ✅ تبويب «منتهية» (5.3j) |
| مؤرشفة | 404 بكل مكان عام | بتبويب «المؤرشفة» (`GET /company/jobs?view=archived`) — قراءة بس | بطلباته (`get_user_applications` ما بيفلتر الأرشيف) | ✅ تبويب «مؤرشفة» (5.3j) |
| مخفية من الإدارة | مش بالفيد · مش بصفحة الشركة · `/job-detail` 404 · التقديم مرفوض | بتشوفها بقائمتها «مخفية من الإدارة» + السبب (`GET /company/jobs`) + إشعار `job_admin` | بطلباته | ✅ تبويب «مخفية من الإدارة» + إرجاع (5.3j) |

> **5.3j5 (قرار صاحب المشروع):** الشركة ما بتقدر تعدّل أي وظيفة بعد نشرها (لا الحقول ولا المدة) — `PUT /company/jobs/{id}` → 403. التعديل للأدمن بس.

### 2.3 الانتقالات

| من → إلى | مين | تلقائي / يدوي | كيف |
|---|---|---|---|
| (جديد) → active | الشركة (`co`/`edu`) | يدوي | `POST /company/jobs` · `expires_at = NOW() + duration` · تذكير `job_expiring_soon` قبل 48 ساعة (scheduler) |
| active → paused | الشركة | يدوي | `PATCH /company/jobs/{id}/status {paused}` |
| paused → active | الشركة | يدوي | نفسه — `expires_at += مدة الإيقاف` (المدة مجمّدة وقت الإيقاف — #7) + تذكير جديد (#13) |
| active / paused → closed | الشركة | يدوي | `{closed}` → `closed_at=NOW()` |
| active → closed | — | **تلقائي** (محسوب عند القراءة) | `expires_at` مضى (الموقوفة ما بتنغلق تلقائياً — 5.3j #7) |
| closed → expired | — | **تلقائي** (محسوب) | 30 يوم بعد الإغلاق |
| أي حالة (تعديل حقول / مدة جديدة) | الشركة | **ممنوع** (5.3j5) | `PUT /company/jobs/{id}` → 403 «لا يمكن تعديل الوظيفة بعد نشرها» · المدة من الأدمن (`/extend` · `/reactivate`) |
| closed / expired → active | الأدمن | يدوي | `POST /admin/jobs/{id}/reactivate {duration_days}` → `expires_at = NOW() + المدة` + تذكير + إشعار (5.3j) |
| closed / expired → active | الشركة | **ممنوع** | `set_job_status` بيرفض (422 «لا يمكن إعادة فتح…») — إعادة الفتح للأدمن بس (قرار صاحب المشروع 5.3j4) |
| active ↔ paused · → closed | الأدمن | يدوي | `POST /admin/jobs/{id}/status {status, reason}` = نفس `set_job_status` · سبب إلزامي للإغلاق + إشعار (5.3j المرحلة 3) |
| active / paused (مدة أطول) | الأدمن | يدوي | `POST /admin/jobs/{id}/extend {duration_days}` → `expires_at += المدة` + إشعار (5.3j) |
| أي حالة ↔ مخفية | الأدمن | يدوي | `POST /admin/jobs/{id}/hide {reason}` / `unhide` + إشعار (5.3j) |
| أي حالة → مؤرشفة | الشركة | يدوي | `DELETE /company/jobs/{id}` → `archive_job` (حذف ناعم) |
| مؤرشفة → غير مؤرشفة | الأدمن | يدوي | `POST /admin/jobs/{id}/unarchive` + إشعار (5.3j المرحلة 3) |
| أي حالة → محذوفة | الأدمن | يدوي | `DELETE /admin/jobs/{id}` (حذف نهائي — مراحل التوظيف + الوظيفة بنفس الـ transaction، 5.3j) |

### 2.4 الأدمن هلق

| الإجراء | Endpoint | شاشة |
|---|---|---|
| قائمة | `GET /admin/jobs` = `admin_insights.jobs_list` — **كل الحالات** (نشطة · موقوفة · مغلقة · منتهية · مؤرشفة) + عدد كل حالة + بحث عنوان / شركة + صفحات بالسيرفر + `applicant_count` (5.3j) | ✅ لوحة → الوظائف (تبويبات + شارة لون) |
| حذف نهائي | `DELETE /admin/jobs/{id}` → `auth.admin_hard_delete_job` (مراحل التوظيف ثم الوظيفة بـ transaction وحدة · 404 لغير الموجودة) | ✅ (كتابة «حذف» + عدد المتقدمين بالرسالة) |
| إخفاء (بسبب) / إرجاع | `POST /admin/jobs/{id}/hide` · `/unhide` | ✅ (نافذة السبب + تأكيد) |
| إعادة تفعيل (مغلقة / منتهية) | `POST /admin/jobs/{id}/reactivate` | ✅ (اختيار مدة + تأكيد) |
| تمديد (نشطة / موقوفة) | `POST /admin/jobs/{id}/extend` | ✅ (اختيار مدة + تأكيد) |
| إيقاف / استئناف / إغلاق (بسبب) | `POST /admin/jobs/{id}/status` | ✅ |
| إلغاء الأرشفة | `POST /admin/jobs/{id}/unarchive` | ✅ |
| صفحة الوظيفة + تعديل الحقول (سبب إلزامي + إشعار للشركة + إشعار لكل متقدم طلبه لسا قيد المراجعة (`applicant_visible_status` — المقبول نهائياً والمرفوض لا — 5.3j7) مرة لكل تعديل) | `GET` / `PUT /admin/jobs/{id}` · `/admin-job?id=N` | ✅ (5.3j المرحلة 4) |
| المتقدمون (قراءة بس) | `GET /admin/jobs/{id}` → `applicants` | ✅ |
| معاينة قبل الحذف (متقدمين · مراحل · مواعيد) | `GET /admin/jobs/{id}/delete-preview` | ✅ بنافذة تأكيد الحذف |

### 2.5 ناقص للتحكم الكامل

- ~~قائمة أدمن بكل الحالات + فلتر + بحث + pagination + عدد المتقدمين~~ ✅ 5.3j.
- ~~إخفاء / إرجاع من الأدمن بسبب~~ · ~~إعادة التفعيل~~ · ~~تمديد المدة~~ · ~~#7~~ · ~~#13~~ ✅ 5.3j المرحلة 2.
- ~~إيقاف / استئناف / إغلاق من الأدمن~~ · ~~إلغاء الأرشفة~~ ✅ 5.3j المرحلة 3 · إعادة فتح الشركة لوظيفتها المغلقة: انضافت بالمرحلة 3 وانشالت بـ 5.3j4 (قرار صاحب المشروع — إعادة الفتح للأدمن بس).
- ~~صفحة تفاصيل أدمن للوظيفة (تعديل كل الحقول + المتقدمون)~~ · ~~معاينة قبل الحذف~~ ✅ 5.3j المرحلة 4 — التحكم بالوظائف كامل.

### 2.6 ملاحظات خطر

- **حذف الأدمن النهائي:** `job_applications` CASCADE · `company_candidate_job_refs` CASCADE · `job_profession_targets` · `company_saved_candidates.job_id` → NULL · `appointments.job_id` → NULL · **`job_pipeline_entries.job_id` = RESTRICT** → من 5.3j الحذف بيشيلهم أول بنفس الـ transaction (أحداثهم وملاحظاتهم CASCADE).
- `status` المخزّن ≠ الحالة الحقيقية (محسوبة) → أي فلترة بالـ DB على `status='active'` لحالها غلط — من 5.3j كلها عبر `job_active_sql()`.
- ~~`paused` ما بيوقف العدّاد فعلياً~~ ✅ 5.3j #7: الموقوفة بتضل `paused` والاستئناف بيكمّل المدة الباقية.
- `closed` / `expired`: مخرجها إعادة تفعيل الأدمن بس (`/reactivate` — 5.3j4)؛ الشركة ما بتقدر.

---

## 3. طلبات التوظيف — `job_applications`

**الحالة:** `job_applications.status` — المسموح بـ `PUT /jobs/applications/{id}/status`: `pending` · `viewed` · `accepted` · `contacted` · `interview` · `hired` · `rejected`. `UNIQUE(job_id, user_id)`.

### 3.1 الحالات ومين بيشوف

| الحالة | المتقدم | الشركة | الأدمن |
|---|---|---|---|
| `pending` (افتراضي) | بـ «طلباتي» (`GET /my/applications`) — «قيد المراجعة» (`in_review` — 5.0c) | بالمتقدمون (`GET /jobs/{id}/applicants`) | ❌ |
| `viewed` · `accepted` · `contacted` · `interview` | «قيد المراجعة» — الحالة الداخلية ما بتطلع من السيرفر (`auth.applicant_visible_status`) | تغيير الحالة · ترقية لمرشح (`promote`) | ❌ |
| `hired` / `rejected` | «مقبول» / «غير مقبول» + إشعار + إيميل مرة وحدة (5.1d — `notify_application_result`، حسب `company_settings.notify_applicant_result`) | — | ❌ |

### 3.2 الانتقالات

| من → إلى | مين | كيف |
|---|---|---|
| (جديد) → pending | المتقدم (`emp`) | `POST /jobs/{id}/apply` — بس إذا `effective_status='active'` وغير مؤرشفة · بيكتب entry بالـ pipeline (`source='application'`) بنفس الـ transaction |
| أي → أي (من القائمة) | الشركة صاحبة الوظيفة | `PUT /jobs/applications/{id}/status` — ذرّي مع `company_candidate_job_refs.candidate_status` + `job_pipeline_entries.stage` (`_APP_TO_CANDIDATE_STATUS` · `LEGACY_APP_STATUS_TO_PIPELINE_STAGE`) |
| → accepted + مرشح قوي | الشركة | `POST /jobs/applications/{id}/promote` |
| سحب الطلب | المتقدم | **ما في endpoint** (المرحلة `withdrawn` موجودة بالـ CHECK بس) |
| تلقائي | — | ما في (إغلاق الوظيفة ما بيغيّر الطلبات) |

### 3.3 الأدمن

- هلق: **ولا شي** (لا endpoint ولا شاشة).
- ناقص: عرض طلبات حساب / وظيفة · تصحيح حالة غلط · حذف ناعم لطلب (سبام).
- خطر: حذف الوظيفة أو أي من الطرفين → حذف الطلب نهائياً (CASCADE)؛ `appointments.application_id` و `job_pipeline_entries.application_id` → NULL.
- تضارب ممكن: الحالة مكتوبة بـ 3 أماكن (application · job ref · pipeline) — الكتابة ذرّية من مسار الشركة، بس أي تعديل أدمن مستقبلي لازم يمرق من نفس الدوال.

---

## 4. مراحل التوظيف — `job_pipeline_entries`

**الأعمدة:** `stage` CHECK (`new` · `reviewing` · `shortlisted` · `contacted` · `interview` · `offer` · `hired` · `rejected` · `withdrawn`) · `source` CHECK (`application` · `company_add` · `bank_link` · `migration` · `legacy_unknown`) · `archived_at` · سجل ثابت `pipeline_stage_events` · ملاحظات `pipeline_notes` (حذف ناعم `deleted_at`).

| البند | الحقيقة بالكود |
|---|---|
| مين بيشوف | الشركة صاحبتها بس (ملاحظات: `GET/POST/PATCH/DELETE /company/pipeline/...`) · المتقدم ما بيشوف المرحلة |
| الانتقالات | dual-write من تغيير حالة الطلب / تصنيف المرشح لكل وظيفة / الترقية؛ ما في endpoint مباشر لتغيير `stage` |
| مراحل ما بيكتبها أي مسار | `offer` · `withdrawn` (بالـ CHECK والـ rank بس) · `archived_at` ما في كاتب |
| الأدمن هلق | `POST /admin/pipeline/backfill` · `GET /admin/pipeline/backfill/dry-run` · `POST /admin/pipeline/migrate-index` — صيانة بس، **بدون شاشة** |
| ناقص | قراءة الـ pipeline لوظيفة / شركة من الأدمن (للدعم الفني) |
| خطر | `job_id` RESTRICT (بيمنع حذف الوظيفة) · `company_id` / `candidate_id` CASCADE → حذف الحساب بيمسح السجل والملاحظات |

---

## 5. بنك المواهب — `company_saved_candidates` + `company_candidate_job_refs`

| البند | الحقيقة بالكود |
|---|---|
| الحالات (بنك عام) | `company_saved_candidates.status` ∈ `VALID_CANDIDATE_STATUSES` = `saved` · `shortlisted` · `contacted` · `interview` · `hired` · `rejected` · + `priority` (low/medium/high) · `rating` 1–5 · `follow_up_status` (none/pending/done) + `follow_up_at` · `save_source` |
| الحالات (لكل وظيفة) | `company_candidate_job_refs.candidate_status` (نفس القيم أو NULL) |
| حد | `TALENT_BANK_FREE_LIMIT = 25` لكل شركة (`/company/saved-candidates/quota`) |
| مين بيشوف | الشركة بس. المرشح ما بيعرف إنه محفوظ |
| الانتقالات | الشركة: حفظ `POST` · تعديل `PATCH /company/saved-candidates/{id}` · تصنيف لوظيفة `PATCH …/jobs/{job_id}` · إزالة `DELETE` (حذف نهائي) · تلقائي: ولا شي (`follow_up_at` ما إله scheduler) |
| الأدمن هلق | ولا شي |
| ناقص | قراءة فقط للدعم + رفع الحد لشركة معيّنة (الحد ثابت بالكود — يخالف «التحكم الكامل») |
| خطر | حذف الوظيفة → refs CASCADE + `job_id` NULL · حذف أي طرف → الصف ينمسح · 3 مصادر حقيقة (`docs/rules/saved-candidates.md`) |

---

## 6. المواعيد — `appointments`

**الحالة:** `appointments.status` ∈ `_APPT_VALID_STATUSES` = `draft` · `pending_response` · `reschedule_requested` · `confirmed` · `cancelled` · `expired` · `missed` · `completed` · `closed`. نهائية (ما في رسائل ولا قرار): `cancelled` · `expired` · `closed`. سجل ثابت `appointment_events`، رسائل `appointment_messages` (حذف ناعم).

### 6.1 مين بيشوف

المشاركين بس (`appointment_participants`: الشركة + المدعو + الممثل) — `GET /api/appointments`, `/appointment-room`. ما في زائر ولا أدمن.

### 6.2 الانتقالات

| من → إلى | مين | تلقائي / يدوي |
|---|---|---|
| (جديد) → draft | الشركة | يدوي `POST /api/appointments` (مربوط بوظيفة — PR 3.10؛ مرفوض إذا الشخص `rejected` / `withdrawn` على الوظيفة) |
| draft → pending_response | الشركة | يدوي `…/send` (موعد + مهلة رد 24/48/72/168 ساعة) |
| pending_response → confirmed | المدعو | يدوي `…/accept` |
| pending_response → reschedule_requested | المدعو | يدوي `…/request-reschedule` |
| reschedule_requested → pending_response | الشركة | يدوي `…/reschedule` |
| pending_response → expired | — | **تلقائي** (scheduler `_handle_appointment_deadline_expire`) + محسوب عند القراءة `_appt_computed_status` |
| confirmed → missed | — | **تلقائي** (scheduler `_handle_appointment_missed` — النهاية + 15 د، أو الموعد + 2 س) |
| confirmed / missed → completed | الشركة | يدوي `…/complete` |
| completed / cancelled / missed / expired → closed | الشركة | يدوي `…/close` |
| draft / pending_response / confirmed / reschedule_requested → cancelled | أي مشارك | يدوي `…/cancel` |

### 6.3 الأدمن

- هلق: **ولا شي**.
- ناقص: قراءة موعد + سجله (نزاع / شكوى) · إلغاء من الأدمن مع سبب · إخفاء رسالة مسيئة بغرفة الموعد.
- خطر / حالات بلا مخرج: `draft` ما إلها انتهاء تلقائي (بتضل للأبد إذا ما انبعتت) · `reschedule_requested` ما إلها مهلة — إذا الشركة ما ردّت بتضل معلّقة (المخرج الوحيد الإلغاء اليدوي) · حذف الشركة أو المدعو → الموعد وسجله ورسائله بينمسحوا (CASCADE)؛ حذف الوظيفة / الطلب → `job_id` / `application_id` NULL (الموعد بيضل بدون سياق وظيفة).

---

## 7. المنشورات — `company_posts`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | **ما في عمود حالة.** موجود أو محذوف نهائياً. خاصية واحدة: `comments_enabled` (TRUE/FALSE) |
| مين بيشوف | الكل (`GET /company/posts/{company_id}` عام · `/home/feed`) |
| صاحبه (`co`/`edu`) | نشر `POST /company/posts` · تعديل `PATCH` (نص / وسوم / لون / تفعيل التعليقات) · حذف `DELETE` |
| أي مسجّل | تقدير (`PUT …/appreciation`) · حفظ (`PUT …/save`) · تعليق · مشاهدة |
| تلقائي | ولا شي |
| الأدمن هلق | **ولا شي** (لا endpoint ولا شاشة) — المنشور حتى ما بينبلّغ عنه (`twReportDialog` مش موصول بالمنشورات) |
| ناقص | قائمة منشورات للأدمن · إخفاء (حالة `hidden` + سبب) بدل الحذف · حذف ناعم (F27) · قفل التعليقات من الأدمن · بلاغ على منشور |
| خطر | حذف صاحبه = **حذف نهائي** → CASCADE على التعليقات + الإشارات + التقديرات + الحفظ + المشاهدات |

---

## 8. التعليقات — `company_post_comments`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `status` = `active` / `deleted` (+ `deleted_at`) — حذف ناعم ✅ · `updated_at` = معدّل |
| مين بيشوف | الكل بيشوف `active` (`GET /company/posts/{id}/comments`) |
| صاحب التعليق | تعديل (`PATCH /company/posts/comments/{id}`) · حذف |
| صاحب المنشور | حذف تعليقات غيره على منشوره |
| الانتقالات | active → deleted (يدوي، صاحب التعليق أو صاحب المنشور) · deleted → active: **ما في** |
| الأدمن هلق | ولا شي |
| ناقص | إخفاء / حذف من الأدمن · إرجاع تعليق محذوف · قراءة المحذوف (الجسم محفوظ) |
| خطر | ردّ على تعليق محذوف: `reply_to_comment_id` بيضل يشاور على تعليق `deleted` · حذف المنشور نهائياً بيمسح حتى المحذوف ناعماً |

---

## 9. الرسائل — `messages`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | رسالة: `is_read` · `delivered_at` · `read_at` · محادثة (5.0g): مفتوحة / **منتهية** (صف بـ `conversation_endings` — `user_a < user_b` · `ended_by` · `ended_at`). ما في حذف ولا إخفاء ولا حظر |
| مين بيشوف | المرسل والمستقبل بس (`GET /messages/{user_id}/{other_id}` — JWT) · المحادثة المنتهية بتضل مقروءة للطرفين |
| مين بيبعت | `auth.can_send_message` (5.0g — النوع والمتابعة والإنهاء من القاعدة): محادثة موجودة (رسالة سابقة بأي اتجاه) → الطرفين · جديدة: شركة / جهة تعليمية → أي حدا · شخصي → جهة تعليمية · شخصي ↔ شخصي بمتابعة متبادلة بس · شخصي → شركة ❌ (الشركة بتبدأ) · منتهية → الشركة بس. رفض → 403 (`company_start` / `mutual_follow` / `ended`) · ممنوع لنفسك · إيميل تنبيه للرسالة غير المقروءة (5.1c) |
| الانتقالات | مُرسلة → مُسلّمة (WS) → مقروءة (فتح المحادثة) — تلقائية · محادثة: مفتوحة → منتهية (الشركة — `POST /messages/conversations/{id}/end`، بدون إشعار) → مفتوحة (أول رسالة من الشركة — تلقائي بنفس الـ transaction) |
| الأدمن هلق | ولا شي |
| ناقص | ~~حظر مستخدم~~ (انعمل — task 5.4) · بلاغ على رسالة / محادثة · قراءة محادثة مبلّغ عنها (بموافقة وسجل) · حذف / إخفاء رسالة مسيئة |
| خطر | حذف أي طرف → كل المحادثة بتنمسح للطرف التاني كمان (CASCADE على `sender_id` و `receiver_id`؛ و `conversation_endings` كمان CASCADE) |

---

## 10. البلاغات — `reports`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `status` = `pending` (افتراضي) → `resolved`. بس |
| أنواع | `reported_type`: `user` · `company` → `reported_id` (users) · `job` → `job_id` (jobs) — تحقق بالسيرفر (غير هيك 422 · الهدف مش موجود 404 — 5.0c) · `report_type` (سبب) بدون تحقق |
| مين بيشوف | المبلِّغ: ولا شي بعد الإرسال (ما في «بلاغاتي») · المبلَّغ عنه: ما بيعرف · الأدمن: الكل |
| الانتقالات | أي مسجّل → pending (`POST /reports/submit`) · الأدمن pending → resolved (`PUT /admin/reports/{id}/resolve`) · ما في رجوع |
| الأدمن هلق | ✅ قائمة `GET /admin/reports` + شارة العدد — الهدف الصح (`target`: اسم الوظيفة أو الحساب + رابط · «محذوف») · عطل DB → خطأ واضح · ✅ «حل» · «حذف الحساب» لهدف حساب بس |
| ناقص | حالات أكتر (`reviewing` · `dismissed` · `action_taken`) · ملاحظة الأدمن + مين حلّه + متى · إجراء مباشر (إخفاء الوظيفة / تعليق الحساب) · بلاغ على منشور / تعليق / رسالة · pagination |
| خطر | ~~CASCADE (#12) · رقم الوظيفة بـ `reported_id` (#2)~~ — انصلحوا (5.0c): `reported_id` / `job_id` = SET NULL، والبلاغات القديمة انقلبت لـ `job_id` بالـ migration |

---

## 11. التوثيق (KYC) — `kyc_submissions`

**الأعمدة:** `step` (`email` → `phone` → `id_upload` → `review` / `rejected`) · `status` (`pending` افتراضي → `approved` / `rejected`) · `email_verified` · `phone_verified` · `admin_note` · `submitted_at` · `reviewed_at` · `UNIQUE(user_id)`.

### 11.1 الانتقالات

| من → إلى | مين | كيف |
|---|---|---|
| (لا شي) → step=email | صاحبه | `POST /kyc/start` |
| email → phone | صاحبه | `POST /kyc/email/verify` (OTP) + `users.email_verified=TRUE` |
| phone → id_upload | صاحبه | `POST /kyc/phone/verify` + `users.phone_verified=TRUE` |
| id_upload / rejected → review (status pending) | صاحبه | `POST /kyc/docs` — بس بعد توثيق الإيميل + الجوال، غير هيك 409 (5.0c) |
| review → step=status=approved | الأدمن | `PUT /admin/kyc/{user_id}/approve` → الشارة العامة (`set_user_verified`) · بدون طلب بانتظار المراجعة → 409 |
| review → step=status=rejected | الأدمن | `PUT /admin/kyc/{user_id}/reject` → الشارة بتنشال · بدون طلب بانتظار المراجعة → 409 |
| rejected → إعادة المحاولة | صاحبه | `POST /kyc/docs` من جديد (الإيميل والجوال موثّقين) → review / pending |

### 11.2 مين بيشوف

صاحبه: Tier 3 (7 حقول — `GET /kyc/status/{id}`). الأدمن: القائمة (`GET /admin/kyc` — allowlist) + روابط موقّعة للوثائق 5 دقائق (`GET /admin/kyc/{submission_id}/docs`). ما في غيرهم.

### 11.3 الأدمن

- هلق: ✅ قائمة · ✅ موافقة / ✅ رفض (للطلبات بانتظار المراجعة بس — الشاشة بتبعت `note: ''` دايماً، ما في خانة سبب) · ✅ عرض الوثائق · سحب التوثيق بعد الموافقة = «إلغاء التوثيق» من صفحة المستخدم.
- ناقص: سبب الرفض بالواجهة + إشعار المستخدم.
- خطر: حذف الحساب → صف KYC بينمسح بس **الوثائق بالـ Storage بتضل**.

---

## 12. الأخبار — `news_posts`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `status` = `draft` (افتراضي) · `published` · `archived` (`server.py → admin_create_news`) |
| مين بيشوف | `published` بس بالفيد (`/home/feed` فلتر `news`/`all`) · draft / archived: الأدمن بس |
| الانتقالات | كلها يدوية من الأدمن (`POST` / `PUT /admin/news/{id}`) — قيمة غلط بتنقلب `draft` بصمت · ما في نشر مجدول ولا انتهاء |
| الأدمن هلق | API كامل: `GET` / `POST` / `PUT` / `DELETE /admin/news` — **بدون أي شاشة** (ولا ملف بالواجهة بينادي `/admin/news`) |
| ناقص | شاشة أخبار · `published_at` (الفيد بيرتّب بـ `created_at` — خبر منشور اليوم من مسودة قديمة بيطلع تحت) |
| خطر | `DELETE` = حذف نهائي (في `archived` كبديل ناعم موجود) · `created_by` ما بينكتب أبداً (الأدمن مش user) |

---

## 13. الخبرات / الشهادات / الدورات / المهارات / اللغات / الروابط

**الجداول:** `experience` (`is_current`, `sort_order`) · `education` (`is_current`) · `courses` · `user_skills` · `user_langs` · `user_links`.

| البند | الحقيقة بالكود |
|---|---|
| الحالات | ما في حالة — موجود أو محذوف نهائياً. `is_current` = بيانات عرض مش حالة |
| مين بيشوف | الكل (Tier 1 بالبروفايل العام) |
| صاحبه | إضافة / تعديل / حذف (`/experience` · `/education` · `/course` · `/skills` · `/langs` · `/links`) · ترتيب الخبرات |
| الأدمن هلق | ✅ حذف خبرة / شهادة / دورة (`DELETE /admin/experience|education|course/{id}`) — صفحة المستخدم · ❌ مهارات / لغات / روابط · ❌ تعديل أي عنصر |
| ناقص | إخفاء عنصر مخالف بدل حذفه · تعديل · حذف رابط مسيء (روابط خارجية = أعلى خطر محتوى) |
| خطر | حذف الحساب → كلها CASCADE · حذف الأدمن نهائي بدون نسخة |

> «الدورات / التعليم» للجهة التعليمية: ما في كيان «دورة منشورة» من حساب `edu` — جدول `courses` هو دورات الشخص على بروفايله بس. حساب `edu` بينشر وظائف ومنشورات متل الشركة.

---

## 14. الإشعارات — `notifications`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `is_read` (+ تجميع `aggregation_*`) · `event_key` UNIQUE لكل مستخدم (منع التكرار) |
| مين بيشوف | صاحبه بس (`GET /notifications/{user_id}` — JWT) |
| الانتقالات | تلقائي عند الحدث (`create_notification`) → مقروء (`PUT …/read` كلها أو وحدة) · ما في حذف |
| الأدمن هلق | ولا شي — والأدمن ما بيقدر يبعت إشعار (مش user) |
| ناقص | إشعار نظام من الأدمن (لمستخدم / للكل) · سياسة تنظيف القديم |
| خطر | ما في حذف → الجدول بيكبر للأبد · روابط قديمة (`link="/company-profile"` بإشعار `job_expiring_soon`) بتمرق على redirect |

---

## 15. المتابعة + الاهتمام + مشاهدات البروفايل

| الجدول | الحالات | مين | الأدمن |
|---|---|---|---|
| `profile_follows` | موجود / لا (UNIQUE + منع متابعة النفس) | أي مسجّل بيتابع أي حساب · الأعداد عامة · القوائم `GET /profile/{id}/followers|following` | ولا شي |
| `profile_interests` | `interest_type` (من نوع الفاعل) | أي مسجّل · `POST` / `DELETE /profile/{id}/interest` | ولا شي |
| `profile_views` | سجل أحداث | تلقائي عند الزيارة · صاحبه بيشوف الأعداد | ولا شي |

ناقص: لا شي ضروري للأدمن هلق (قراءة بس للدعم). خطر: كلها CASCADE من الطرفين.

---

## 16. تقييمات الشركات — `company_ratings`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | ما في — `score` 1–5 + `comment` نص حر · UNIQUE (شركة، مقيّم) |
| مين | أي مسجّل بيقيّم (`POST /company/rate/{id}`) · الكل بيشوف (`GET /company/{id}/ratings`) |
| الأدمن هلق | ولا شي |
| ناقص | **إخفاء تعليق تقييم مسيء** (نص حر عام بدون أي إشراف) · بلاغ على تقييم |
| خطر | حذف المقيّم → التقييم بينمسح ومتوسط الشركة بيتغيّر |

---

## 17. اقتراحات المهن — `profession_suggestions`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `status` افتراضي `pending` + `reviewed_by` · `reviewed_at` · `review_note` |
| مين | المستخدم بيقترح (`POST /profession-suggestions`) |
| الانتقالات | **ما في أي كود بيغيّر الحالة** → كل اقتراح `pending` للأبد |
| الأدمن هلق | ولا شي |
| ناقص | قائمة + قبول (إضافة لـ `profession_categories`) / رفض · تفعيل / إيقاف مهنة (`profession_categories.is_active` موجود بدون endpoint) |
| خطر | `reviewed_by` → `users` بدون ON DELETE (NO ACTION) — بيمنع حذف حساب كان مراجِع (ما بينكتب حالياً) |

---

## 18. مهام المجدول — `scheduler_jobs`

| البند | الحقيقة بالكود |
|---|---|
| الحالات | `status` CHECK: `pending` · `running` · `done` · `failed` · `cancelled` · `attempts` / `max_attempts` (5) |
| مين | داخلي — `POST /internal/run-due-jobs` (`X-Scheduler-Secret`) |
| الانتقالات | تلقائية (pending → running → done / pending (retry) / failed) |
| الأدمن هلق | ولا شي (ولا عدد الفاشلة بـ `/health`) |
| ناقص | قراءة الفاشلة + إعادة تشغيل وحدة |
| خطر | `failed` = نهائية بدون تنبيه → تذكير موعد / انتهاء مهلة ممكن ما يصير بصمت |

---

## 19. كيانات تانية (بدون حالات)

| الكيان | الجدول | ملاحظة للأدمن |
|---|---|---|
| فروع الشركة | `company_branches` | صاحبها بس · ما في أدمن |
| إعدادات الشركة | `company_settings` (`notify_applicant_result`) | صاحبها بس |
| ملاحظات بنك المواهب | `candidate_bank_notes` (حذف ناعم `deleted_at`) | الشركة بس |
| تفضيلات الإيميل | `email_notify_prefs` | صاحبها · (إعداد الإيميل العام = `/admin/email` ✅ شاشة) |
| سجل الإيميل | `email_send_log` | عدّاد — ما في شاشة قراءة تفصيلية |
| روابط الإيميل | `password_reset_tokens` (`purpose`) | داخلي · مرة وحدة · 30 د |
| إعدادات الموقع | `site_settings` (نصوص `/admin/strings` · أزرار `/admin/actions` · ألوان `/admin/theme/colors` · لوغو) | لوغو ✅ شاشة · النصوص / الأزرار / الألوان: API بس **بدون شاشة** |
| السجل الأمني | `admin_audit_log` | ✅ لوحة → السجل |

---

## 20. مشاكل لقيتها

> مسجّلة بمهمة 5.3m (توثيق بس). المشطوب انصلح بـ task 5.0c أو 5.3j (رقم المهمة جنبه) — الباقي مفتوح، كل وحدة بتحتاج مهمة لحالها.

| # | الخطورة | المشكلة | المكان | الأثر |
|---|---|---|---|---|
| 1 | عالية | ~~حذف الأدمن للوظيفة بيفشل لأي وظيفة إلها متقدم: `job_pipeline_entries.job_id` = `ON DELETE RESTRICT` وكل تقديم بيعمل entry، والـ endpoint ما بيلتقط الخطأ~~ ✅ 5.3j | `server.py → admin_delete_job` | زر «حذف» باللوحة بيرجّع 500 للوظائف الحقيقية؛ الحذف بينجح بس لوظيفة بدون متقدمين |
| 2 | عالية | ~~بلاغ على وظيفة: `twReportDialog({reportedId: _jobId, reportedType: 'job'})` بيحط **رقم الوظيفة** بـ `reports.reported_id` اللي هو FK → `users(id)`~~ ✅ انصلحت (5.0c) | `static/job/job-detail.js ~642` · `server.py → submit_report` · `auth.py → ensure_reports_table` | إذا ما في user بنفس الرقم → FK error → 500 «خطأ في الخادم»؛ إذا في → البلاغ بينربط بحساب ما إله علاقة (اسم غلط باللوحة، وحذف هالحساب بيمسح البلاغ) |
| 3 | متوسطة | ~~موافقة KYC ما بتغيّر `step` (بيضل `review`)~~ ✅ انصلحت (5.0c) | `auth.py → admin_approve_kyc` | لوحة القيادة `pending_kyc` و «النشاط» (`step='review'`) بيعدّوا الموثّقين كـ «بانتظار المراجعة» للأبد |
| 4 | متوسطة | ~~3 مصادر للتوثيق: `users.is_verified` (KYC) · `profiles.is_verified` (زر الأدمن — **هو اللي بيطلع بالشارة العامة**) · `company_profiles.verified_co` (ما في كاتب)~~ ✅ انصلحت (5.0c) | `auth.py` · `server.py → verify_user` | موافقة KYC ما بتعطي شارة؛ رفض KYC ما بيلغي `users.is_verified` إذا كان موافق عليه قبل |
| 5 | متوسطة | ~~`admin_approve_kyc` / `admin_reject_kyc` ما بيفحصوا وجود طلب ولا إنه بـ `review`~~ ✅ انصلحت (5.0c) | `auth.py` | موافقة على حساب ما قدّم شي = `users.is_verified=TRUE` (الـ UPDATE على KYC بيأثر على 0 صف) |
| 6 | متوسطة | ~~`POST /kyc/docs` ما بيفحص الـ step~~ ✅ انصلحت (5.0c) | `auth.py → upload_kyc_docs` | بيقدر يتخطى توثيق الإيميل / الجوال ويوصل `review` مباشرة؛ بدون صف KYC بيرجّع «submitted» وهو ما حفظ شي |
| 7 | متوسطة | ~~الإيقاف المؤقت ما بيجمّد المدة: `_eff_status` بيعتبر `paused` منتهية إذا `expires_at` مضى~~ ✅ 5.3j | `auth.py → _eff_status` / `set_job_status` | شركة بتوقف وظيفة أطول من المدة الباقية → بتصير «مغلقة» وما بتقدر ترجّعها |
| 8 | متوسطة | ~~`GET /admin/jobs` = `get_jobs({})` = الفيد العام~~ ✅ 5.3j | `server.py → admin_list_jobs` | الأدمن ما بيشوف الوظائف الموقوفة / المغلقة / المنتهية / المؤرشفة أبداً |
| 9 | متوسطة | `POST /admin/message` بيطبع الرسالة بالـ log وبيرجّع `success` بدون إرسال | `server.py → admin_send_message` | الأدمن بيشوف «تم» والمستخدم ما بيوصله شي (F9) · نص الرسالة بالـ log |
| 10 | متوسطة | ~~`PUT /admin/user/{id}/password` بيقبل ≥ 6 أحرف — مش `_password_policy_error`~~ ✅ انصلحت (5.0c) | `server.py → admin_reset_password` | قاعدة كلمة سر تانية (CLAUDE.md: قاعدة وحدة) |
| 11 | منخفضة | ~~`GET /admin/reports` بيبلع أي خطأ وبيرجّع قائمة فاضية~~ ✅ انصلحت (5.0c) | `server.py → admin_get_reports` | عطل DB بيبين «ما في بلاغات» (F9) |
| 12 | منخفضة | ~~`reports.reported_id` CASCADE~~ ✅ انصلحت (5.0c) | `auth.py → ensure_reports_table` | حذف الحساب المبلَّغ عنه بيمسح الدليل |
| 13 | منخفضة | ~~استئناف وظيفة أو تغيير مدتها ما بيجدول تذكير `job_expiring_soon` جديد~~ ✅ 5.3j | `server.py → update_job_endpoint` · `auth.py → set_job_status` | التذكير القديم بيتخطّى نفسه (stale) وما في جديد → الشركة ما بتنبّه |
| 14 | منخفضة | ~~`/stats` بيعدّ `status='active'` بدون فحص `expires_at`~~ ✅ 5.3j | `server.py → stats` | رقم «الوظائف» أعلى من الحقيقي |
| 15 | منخفضة | ~~`/home/feed` بيفلتر `status IN ('active','open')` — `open` مش حالة موجودة~~ ✅ 5.3j | `server.py ~1171` | قيمة ميتة (بدون أثر حالياً) |
| 16 | منخفضة | ~~`admin.js` بيبعت `{verified: true}` والسيرفر بيقرأ `is_verified` (افتراضي TRUE)~~ ✅ انصلحت (5.0c) | `static/admin/admin.js:22` | بيشتغل بالصدفة؛ أي «إلغاء» من هالمسار رح يوثّق بدل ما يلغي |
| 17 | منخفضة | ~~`my/applications` بيرجّع الحالة الداخلية للمتقدم (`viewed` / `interview` / `rejected`…) بينما 5.1d بيعتبر المراحل الوسطى داخلية للشركة~~ ✅ انصلحت (5.0c) | `auth.py → get_user_applications` · `profile-v2.apps.js` | قرار منتج مش محسوم — للمراجعة |
| 18 | منخفضة | مراحل / حالات بدون كاتب: `pipeline.stage` `offer` / `withdrawn` · `job_pipeline_entries.archived_at` · `profession_suggestions.status` · `company_profiles.verified_co` · `users.is_verified` (legacy من 5.0c) | — | قيم بالـ schema بدون مسار — أي شاشة أدمن لازم تعرف إنها ما بتصير |

---

## 21. جدول الأولويات المقترح

| الترتيب | الكيان | ليش أول | أول خطوة مقترحة |
|---|---|---|---|
| **1** | **الوظائف** | أكتر كيان عام بالموقع؛ إلها 5 حالات وأكتر من مخرج مسدود (closed / expired بلا رجوع)؛ قائمة الأدمن عمياء عن 4 حالات (#8) والحذف الوحيد مكسور (#1) | قائمة أدمن بكل الحالات + `effective_status` · إخفاء من الأدمن بسبب (بدل الحذف) · إرجاع تفعيل + تمديد مدة (نفس قواعد `_ALLOWED_DURATIONS`) · إلغاء أرشفة · إصلاح #1 / #7 / #13 |
| 2 | الحسابات | الأدمن ما عنده إلا «حذف للأبد» لحساب مخالف؛ والحذف بيمسح بلاغات ومحادثات الناس التانيين | حالة تعليق (login + `verify_token` + WS) · حذف ناعم · مصدر توثيق واحد (#4) |
| 3 | البلاغات | هي مدخل الأدمن لكل مشكلة محتوى؛ بلاغ الوظيفة مكسور (#2) والإجراء الوحيد «حل» | إصلاح #2 (عمود هدف حسب النوع) · حالات + ملاحظة + إجراء مباشر من البلاغ (إخفاء وظيفة / تعليق حساب) · بلاغ منشور / تعليق / رسالة |
| 4 | التوثيق (KYC) | فيه شاشة، بس الحالات متضاربة (#3 · #5 · #6) والشارة ما بتظهر | توحيد الحالة (step + status) · سبب رفض + إشعار · إعادة المحاولة · سحب التوثيق |
| 5 | المنشورات + التعليقات + التقييمات | محتوى عام بدون أي إشراف أدمن | إخفاء / إرجاع (منشور: حذف ناعم أولاً) |
| 6 | الأخبار | الـ API جاهز — ناقص شاشة بس | شاشة بالـ Admin Shell + `published_at` |
| 7 | الرسائل | خصوصية — بحاجة قرار منتج قبل أي قراءة أدمن | حظر مستخدم + بلاغ على محادثة أولاً |
| 8 | طلبات التوظيف + Pipeline + بنك المواهب + المواعيد | خاصة بين الشركة والشخص — الأدمن بيحتاجهم للدعم بس | قراءة فقط (بدون تعديل) |
| 9 | اقتراحات المهن · مهام المجدول · الإعدادات بدون شاشة (نصوص / أزرار / ألوان) | تشغيلي | شاشات صغيرة على الـ Admin Shell |

**قاعدة لكل كيان رح يتبنى تحكمه:** الإخفاء / التعليق قبل الحذف (F27) · كل إجراء عبر `TwAdminShell.run` (تأكيد) وبيتسجّل تلقائياً بـ `admin_audit_log` · الحالة المحسوبة (`effective_status`) من دالة وحدة بالسيرفر — ما تنحسب بالواجهة.
