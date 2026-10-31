# Certificate PDFs — ملفات الشهادات للدورات والتعليم (task 8.7)

> إلزامي بنفس قوة `CLAUDE.md`. Spec: `docs/SYSTEMS_INDEX.md §29c` · `ARCHITECTURE.md → Certificate PDFs (task 8.7)` · tests `python -m pytest tests/test_certificates_87.py -q` (SECURITY_TESTS) · `node tests/test_certificates_87_runtime.js`.

## المصدر الوحيد

- **`cert_access.py`** — `can_view(viewer_id, owner_id)` **فحص الصلاحية الوحيد** (السيرفر، قبل كل رابط عرض ولكل علم `can_view_certificate`) · `validate_pdf(data_url)` فحص الرفع الوحيد · `object_name(uid)` / `name_of(path, uid)` اسم الملف · `migrate_certificates()` (migration `certificates`، حرجة، بعد `account_purge`).
- **الأعمدة:** `courses.certificate_path` · `education.certificate_path` (`TEXT NULL`) = `cert-docs/{uid}_cert_{12hex}.pdf`. الإنتاج: `docs/migrations/8.7_certificates.sql` (فحص قراءة أول بـ `UNION ALL` · التغيير · فحص تاني) + الـ bucket الخاص `cert-docs` (`storage.buckets`، `public = false`، PDF بس، 5MB).
- **`server.py`** — `POST` / `DELETE` `/course/{id}/certificate` و `/education/{id}/certificate` · `GET /certificates/{kind}/{id}/view` (`kind` = `course` | `education`) · `_cert_flags` (علمين بردّ الملف) · `_require_emp_profile` · `_refuse_new_cert_url`.
- **الحدود (`tw_limits.py`):** `LIMITS["cert_max_bytes"]` (5MB) · `cert_url_ttl_s` (300) · `cert_access_after_close_days` (14) · `RATES["cert_upload"]` (10 / ساعة لكل حساب) · `RATES["cert_view"]` (60 / ساعة لكل حساب).
- **الواجهة:** `profile-v2.certs.js` (`TwProfileCert` — حقل الرفع بنافذتي الدورة والتعليم · زر «عرض الشهادة» · المعاينة · الرابط القديم) — بيتحمّل بـ `profile-showcase.html` قبل `profile-v2.edu.js` / `profile-v2.courses.js`.

## القواعد

1. **ملف PDF واحد لكل سجل** `courses` / `education`. ما في صور ولا أنواع تانية. **رفع PDF ما بيعطي أي توثيق.**
2. **الرفع** (`POST …/certificate` `{data_url}`) — الترتيب: JWT → `user_type = 'emp'` من القاعدة (غيره 403) → `_rate_reserve([("cert_upload", uid)])` (429) → السجل إله (`WHERE id AND user_id` — غيره 404 بدون أي كتابة) → `validate_pdf`:
   - أول البايتات `%PDF-` · الحجم بعد فك الترميز ≤ `cert_max_bytes` (والنص قبل الفك) · مشفّر (`/Encrypt`) → 422 `pdf_encrypted` · أي اسم `/JavaScript` · `/JS` · `/Launch` · `/EmbeddedFile(s)` · `/OpenAction` (حتى لو مكتوب بـ `#xx`، وحتى جوّا stream مضغوط Flate — الفك محدود بـ `cert_max_bytes × 10`، أكتر = رفض) → 422 `pdf_unsafe`.
   - نوع الطلب (`data:<أي نوع>;base64,`) والامتداد **ما بيقرّروا شي** — البايتات بس.
   - كل رفض = **422** `{ok:false, error:{code, message, field:"file"}}` (`invalid_file` · `too_large` · `not_pdf` · `pdf_encrypted` · `pdf_unsafe`) — النص twT `cert.err.*`.
3. **الاسم من السيرفر بس:** `{uid}_cert_{12hex}.pdf` بـ `cert-docs` (`_PRIVATE_BUCKETS`)، والمخزّن `cert-docs/{name}`. ❌ مسار / اسم / bucket من الطلب.
4. **الحفظ بالقاعدة أول ثم حذف القديم:** رفع الملف الجديد → transaction: `SELECT certificate_path … FOR UPDATE` + `UPDATE` (للدورة كمان `certificate_url = NULL` — الـ PDF بيستبدل الرابط القديم) → `COMMIT` → حذف القديم عبر `server.storage_delete`. فشل القاعدة → حذف الملف الجديد + 500 (`_server_error`). السجل انحذف بالنص → حذف الجديد + 404. رفعين مع بعض: القفل بيرتّبهم وكل واحد بيحذف اللي استبدله → ملف واحد مربوط وما في يتيم. حذف السجل نفسه (`DELETE /course|education/{id}` + مسارات الأدمن) بيحذف ملفه. فشل حذف القديم بينسجّل (بدون الاسم) — الحذف النهائي بيلقطه بالـ prefix.
5. **العرض** (`GET /certificates/{kind}/{id}/view` → `{ok, data:{url, expires_in}}`): JWT → `_rate_reserve([("cert_view", viewer)])` **قبل أي شي** → السجل → `cert_access.can_view` → المسار لازم `cert-docs/{owner}_cert_…` → التوقيع عبر **`_sign_kyc_doc(name, ttl, bucket="cert-docs")`** (نفس دالة توقيع KYC) بعمر `cert_url_ttl_s`. ما في سجل / ما في صلاحية / ما في ملف / kind غلط → **نفس الـ 404** (ما بنكشف إذا في ملف). فشل التوقيع → 503. الرابط الموقّع ما بينكتب باللوج أبداً (اللوج: viewer · kind · id).
6. **no-store** لكل رد من `/certificates/*` و `/course|education/{id}/certificate` (كل status) عبر `security_headers` — القرار من `_req_path(request)` بس.
7. **رد الملف** (`GET /profile/{id}` · `/profile/{id}/full`): كل سجل دورة / تعليم فيه `has_certificate` + `can_view_certificate` محسوبين بالسيرفر **لهالمشاهد** (`can_view` مرّة وحدة لكل ملف). ❌ المسار أو الرابط بأي رد. `certificate_url` القديم بيرجع **للمالك بس** (`project_public_profile` بتشيله، و `/profile` بيرجّعه للمالك من `get_full_profile`).
8. **courses / education + الشهادات = `user_type = 'emp'` بس** (إضافة · تعديل · حذف · رفع · حذف ملف) — غيره 403 (`_require_emp_profile` = `_require_org_account(token, ("emp",))`). حسابات `edu` ما بتستعمل هالمسارات (صفحتها `edu-profile.html` ما بتنادي `/course` ولا `/education`). العرض ما إله قيد نوع — `can_view` بيقرّر.
9. **ما في روابط خارجية جديدة للشهادات:** `POST /course` بـ `certificate_url` غير فاضي → 422 `url_not_allowed` (قبل أي قاعدة) · `PUT /course/{id}` بقيمة جديدة أو متغيّرة → 422 `url_not_allowed`؛ فاضية أو نفس المخزّنة → مقبولة و`update_course` **ما بيكتب** `certificate_url` أبداً (القديم بيضل). القديم بيروح بس لما المالك يرفع PDF («استبدل بملف PDF»).
10. **التصدير:** `has_certificate` لكل سجل (بدون المسار — `certificate_path` بـ `data_export.FORBIDDEN_KEYS`). الملف نفسه بيوصله المالك من العرض.
11. **الحذف النهائي:** `account_purge` بيجمع `certificate_path` من `courses` + `education` + كل object بـ `cert-docs` اسمه `{uid}_cert_…` (`BUCKETS` فيها `cert-docs` · `_OBJECT_RE` بيقبل `pdf`) — نفس قاعدة F24، الملفات قبل القاعدة (`docs/rules/account-deletion.md`).

## جدول الصلاحية — `cert_access.can_view(viewer_id, owner_id)`

| المشاهد | الحالة | النتيجة |
|---------|--------|---------|
| المالك | دايماً (إذا حسابه فعّال) | ✅ |
| صاحب وظيفة (شركة) المالك قدّم عليها | قيد المراجعة (أي مرحلة قبل النتيجة) والوظيفة مفتوحة | ✅ |
| | `withdrawn` (`ja.status` أو مرحلة الـ pipeline) | ❌ — التقديم من جديد بيرجّعها (الحالة بتصير `pending` / `new`) |
| | `rejected` (بأي مصدر من التلاتة متل `_result_status_on_job`) | ✅ لحد آخر `pipeline_stage_events.created_at` بـ `to_stage = 'rejected'` + `cert_access_after_close_days`، بعدين ❌ · ما في وقت قرار → ❌ |
| | `hired` (بأي مصدر) | ✅ |
| | الوظيفة مسكّرة / منتهية / مخفية من الأدمن / مؤرشفة والطلب لسا قيد المراجعة | ✅ لحد وقت الإغلاق + المدة، بعدين ❌ — وقت الإغلاق = الأبكر من: `closed_at` (أو `expires_at` ثم `created_at` لوظيفة `closed` بدونه) · `expires_at` الماضي لوظيفة `active` · `admin_hidden_at` · `archived_at`. الموقوفة (`paused`) مش مسكّرة |
| | أكتر من طلب | أي طلب بيعطي ✅ بيكفي |
| أي حدا تاني (زائر بتوكن · شركة ما قدّم عندها) | — | ❌ (بدون توكن = 401) |
| أي طرف | المالك أو المشاهد محذوف / معلّق · حظر بأي اتجاه | ❌ — `bs.active_sql` (المشاهد) + `bs.visible_sql` (المالك) بس |

> ملاحظة: `docs/rules/blocks-suspension.md` القاعدة 5 (الحظر ما بيأثّر على طلبات التوظيف) بتضل صح — ملف الشهادة **مش** مسار طلب توظيف؛ هون الحظر بيمنع العرض بقرار صاحب المشروع.

## الواجهة (`profile-showcase.html`)

- نافذة الدورة: انشال حقل «رابط الشهادة»، وانضاف حقل «ملف الشهادة (PDF)» (نفس الحقل بنافذة التعليم): رفع / استبدال / حذف (`twConfirm` danger) بحالة تحميل، والخطأ **تحت الحقل** (نص السيرفر عبر `twApiMessage`). سجل جديد: الملف المختار بيترفع بعد ما ينحفظ السجل؛ فشل الرفع → النافذة بتضل (وضع تعديل) والخطأ تحت الحقل.
- «عرض الشهادة» بس إذا `can_view_certificate` → `GET …/view` → `twModal` فيه `iframe` (`sandbox="allow-scripts allow-same-origin"` — الملف من origin التخزين، يعني ما بيعطي شي على موقعنا؛ بدون forms / popups / top-navigation · `referrerpolicy="no-referrer"`) + نص «إذا ما ظهرت المعاينة…» + زر «فتح بتبويب جديد» (`twSafeLinkUrl` · `target="_blank"` · `rel="noopener noreferrer"`) ظاهر دايماً (بعض المتصفحات بترفض PDF بـ sandbox).
- الرابط القديم: للمالك بس + زر «استبدل بملف PDF» (بيفتح نافذة التعديل على حقل الملف). الشركة بتوصل للعرض من ملف المرشّح (`/u/{tw_id}` من قائمة المتقدمين).
- نصوص `cert.*` (twT) · أيقونات `upload` / `delete` / `eye` / `link` (DS-ICON) · ألوان tokens بس · ❌ inline onclick (event delegation على `data-tw-cert-view` / `data-tw-cert-replace`).

## ممنوعات

- ❌ مسار أو اسم ملف أو bucket من الطلب · ❌ رابط عام (`/object/public/`) لملف شهادة · ❌ `public = true` على `cert-docs`.
- ❌ فحص صلاحية بالواجهة بدل السيرفر · ❌ فحص صلاحية تاني غير `cert_access.can_view` · ❌ قاعدة ظهور تانية (حظر / تعليق / حذف) — `bs.visible_sql` / `bs.active_sql` بس.
- ❌ رد بيفرّق بين «ما في ملف» و «ما في صلاحية» · ❌ `can_view` قبل `_rate_reserve` · ❌ رابط أطول من `cert_url_ttl_s` · ❌ تسجيل رابط موقّع.
- ❌ رابط شهادة خارجي جديد · ❌ حذف `certificate_url` القديم من غير رفع PDF · ❌ إرجاع `certificate_url` لغير المالك · ❌ `certificate_path` بأي رد أو بالتصدير.
- ❌ توثيق (badge / `is_verified`) من رفع PDF.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py` · ❌ قرار على المسار من غير `_req_path(request)` · ❌ `Body(default={})` بدون `Optional`.
- ❌ حذف ملف برّا `server.storage_delete` · ❌ ملف يتيم بعد فشل الحفظ أو رفعين مع بعض.
