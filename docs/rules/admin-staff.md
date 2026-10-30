# Admin Staff Permissions (task 8.4a)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتلمس مسار أدمن (`/admin/*` · مسار اللوحة `/tw-ctrl-…` · `/admin-view` · `/admin-job`).
> المواصفة: `docs/SYSTEMS_INDEX.md` §25h · جلسة الأدمن: §25 · الـ shell: `docs/rules/admin-shell.md`.

## Admin Staff Rules (mandatory for all AI sessions)

1. **قائمة الصلاحيات بمكان واحد:** `admin_perms.py` — `GRANTABLE` (بتنعطى لتوكن موظف — خطة 8.4b) و `OWNER_ONLY` (للمالك بس). كل صلاحية = اسم + وصف عربي قصير. صلاحية جديدة = سطر بالملف + سطر بالجدول تحت بنفس الـ PR. ❌ قائمة صلاحيات تانية بأي ملف.

2. **ما في مسار أدمن بدون perm:** كل endpoint أدمن بينادي `check_admin(request, perm)` **أول سطر** و `perm` من `admin_perms.ALL`. `check_admin(request)` بدون perm = `TypeError` · perm مش بالقائمة = `RuntimeError` (خطأ برمجي → 500، مش 403). الاستثناءات بس بـ `admin_perms.UNGUARDED_ROUTES` مع سبب (صفحات HTML بدون بيانات · الدخول · الشعار العام). التست بيمشي على كل routes الـ app وبيفشل على أي مسار ما بينادي `check_admin` بالـ perm تبع الجدول.

3. **صلاحيات المالك ما بتنعطى:** `admin_perms.allows(perms, perm)` — القرار الوحيد: `"*"` بيمرق كل شي · perm من `OWNER_ONLY` بيمرق **بس** بـ `"*"` حتى لو مكتوب صراحة بـ `perms` التوكن · غير هيك لازم يكون بالتوكن. مفتاح إعداد أمني (`tw_settings.is_security`) بيحتاج `settings.security` (`tw_settings.SECURITY_PERM`) — للمالك بس.

4. **الإيميل مخفي افتراضياً:** بدون `users.email.view` ما في رد أدمن فيه إيميل مستخدم — `_admin_emails(claims, data)` بـ `server.py` (بيشيل كل مفتاح `email` / `guest_email` بأي عمق عبر `admin_perms.strip_emails`) على: قائمة المستخدمين (+ البحث الموحّد لأنه نفس الـ endpoint) · البروفايل (قراءة + رد التعديل) · التوثيق · الدعم (القائمة + التذكرة). البحث بإيميل بدون الصلاحية ما بيطابق: `/admin/users?q=` بيدوّر بالاسم و `tw_id` بس (`users_list(with_email=False)`) · `/admin/support/tickets?q=<email>` → صفر نتائج (`admin_list(email_search=False)`). التصدير CSV = `users.export` (للمالك). رد أدمن جديد فيه إيميل → لازم يمرق على `_admin_emails`.

- ❌ `check_admin(request)` بدون perm · ❌ perm مكتوب برّا `admin_perms.py` · ❌ endpoint أدمن بيرجّع إيميل بدون `_admin_emails` · ❌ بحث بإيميل بدون `users.email.view` · ❌ إعطاء صلاحية من `OWNER_ONLY` لموظف.
- Test: `python -m pytest tests/test_admin_perms_84a.py -q` (كل المسارات + سلوك `check_admin` بتوكنات حقيقية) · `python -m pytest tests/test_admin_email_view_84a.py -q` (PostgreSQL — الإيميل والبحث).

## الصلاحيات

| الصلاحية | المجموعة | الوصف |
|---------|---------|-------|
| `users.view` | قابلة للإعطاء | عرض المستخدمين وملفاتهم |
| `users.edit` | قابلة للإعطاء | تعديل ملفات المستخدمين وحذف عناصر منها |
| `users.suspend` | قابلة للإعطاء | تعليق الحسابات وإرجاعها |
| `users.email.view` | قابلة للإعطاء | رؤية إيميلات المستخدمين |
| `kyc.review` | قابلة للإعطاء | مراجعة طلبات التوثيق |
| `jobs.manage` | قابلة للإعطاء | إدارة الوظائف |
| `reports.manage` | قابلة للإعطاء | مراجعة البلاغات |
| `content.edit` | قابلة للإعطاء | النصوص والألوان والأخبار والشعار |
| `support.manage` | قابلة للإعطاء | تذاكر الدعم |
| `settings.edit` | قابلة للإعطاء | الإعدادات العادية والإيميل وأزرار الإجراءات |
| `stats.view` | قابلة للإعطاء | لوحة القيادة والإحصائيات والنشاط |
| `message.send` | قابلة للإعطاء | إرسال رسالة لمستخدم |
| `users.delete` | المالك بس | حذف حساب |
| `users.type` | المالك بس | تغيير نوع الحساب |
| `users.password` | المالك بس | تغيير كلمة سر مستخدم |
| `users.email` | المالك بس | تغيير إيميل مستخدم |
| `users.export` | المالك بس | تصدير المستخدمين CSV |
| `settings.security` | المالك بس | الإعدادات الأمنية |
| `audit.view` | المالك بس | السجل الأمني |
| `staff.manage` | المالك بس | إدارة فريق الإدارة (ما إلها مسار لسا — 8.4b) |
| `system.manage` | المالك بس | صيانة النظام وسجل الأخطاء |

## المسار → الصلاحية

| Method | المسار | الصلاحية |
|--------|--------|---------|
| GET | `/admin/users` | `users.view` (+ `users.email.view` للإيميل والبحث فيه) |
| GET | `/admin/profile/{user_id}` | `users.view` |
| PUT | `/admin/profile/{user_id}` | `users.edit` |
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
| GET · POST · PUT | `/admin/support/tickets` · `/admin/support/counts` · `/admin/support/tickets/{public_id}` (+ `/messages`) | `support.manage` (+ `users.email.view` للإيميل والبحث فيه) |
| GET | `/admin/settings` | `settings.edit` |
| PUT · POST | `/admin/settings/{key}` · `/admin/settings/{key}/reset` | `settings.edit` — مفتاح أمني: `settings.security` |
| GET · PUT | `/admin/actions` · `/admin/email` | `settings.edit` |
| POST | `/admin/email/test` | `settings.edit` |
| GET | `/admin/stats/summary` · `/admin/stats/timeseries` · `/admin/activity` | `stats.view` |
| POST | `/admin/message` | `message.send` |
| DELETE | `/admin/user/{user_id}` | `users.delete` |
| PUT | `/admin/user/{user_id}/type` | `users.type` |
| PUT | `/admin/user/{user_id}/password` | `users.password` |
| PUT | `/admin/user/{user_id}/email` | `users.email` |
| GET | `/admin/users/export` | `users.export` |
| GET | `/admin/audit` | `audit.view` |
| GET | `/admin/errors` | `system.manage` |
| POST | `/admin/maintenance/migrate-data-images` · `/admin/pipeline/backfill` · `/admin/pipeline/migrate-index` | `system.manage` |
| GET | `/admin/pipeline/backfill/dry-run` | `system.manage` |
| — | تفاصيل الإكمال بـ `GET /profile/{id}/score` (توكن أدمن اختياري) | `users.view` |
| POST | `<panel>/login` | بدون — الدخول نفسه |
| GET | `/admin/logo` | بدون — عام (الشعار بكل صفحة) |
| GET | `<panel>` · `/email` · `/settings` · `/content` · `/support` · `/admin-view` · `/admin-job` | بدون — صفحة HTML بس، البيانات من `/admin/*` بصلاحيتها |
