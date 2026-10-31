# Data Export — «تنزيل بياناتي» (task 8.5b · الخصوصية)

> إلزامي بنفس قوة `CLAUDE.md`. Spec: `docs/SYSTEMS_INDEX.md §1e` · `ARCHITECTURE.md → Data Export (task 8.5b)` · test `python -m pytest tests/test_data_export_85b.py -q` (SECURITY_TESTS) + `node tests/test_settings_edu_runtime.js` (O).

## المصدر الوحيد

- **`data_export.py`** — `build_export(user_id)` الباني الوحيد لملف البيانات. كل قسم من القاعدة مباشرة بقائمة أعمدة صريحة (❌ `SELECT *`) — عمود جديد ما بيدخل الملف لحاله.
- **`server.py`** — `POST /me/export` (الملف) · `POST /me/export/kyc-docs` (روابط وثائق التوثيق) · البوابة المشتركة `_export_password_gate`.
- **الحدود (`tw_limits.py`):** `RATES["data_export"]` و `RATES["data_export_kyc"]` (3 / ساعة لكل حساب، كل محاولة بتنعد) · `LIMITS["data_export_kyc_url_ttl_s"]` = 300 ثانية (عمر الرابط). ثابتة — مش بـ `tw_settings.REGISTRY` (فتحها للأدمن بيحتاج موافقة صاحب المشروع — `docs/rules/settings.md` القاعدة 1).

## القواعد

1. **البوابة (الترتيب ثابت):** JWT (`verify_token` — معلّق / محذوف = 401 أصلاً) → كلمة السر بالجسم مطلوبة (422 `required`، بدون حجز) → `_rate_reserve([(rate, uid)])` **قبل bcrypt** (ممتلئ → 429 `rate_limited` وما في `check_user_password`) → `check_user_password` (غلط → **422** `wrong_password` بالحقل `password` — مش 401، لأن `twApi` بيطلّع المستخدم على 401). الحجز ما بيرجع (`_rate_release` ممنوع هون) — الحد بيعدّ التنزيلات مش الفشل بس.
2. **الملف:** `Content-Disposition: attachment; filename="tawasalna-data-YYYY-MM-DD.json"` · `Cache-Control: no-store` · JSON بدون مفاتيح `ok` / `data` بالمستوى الأعلى (الصفحة بتقرأ `res.raw`).
3. **no-store لكل رد** من `/me/export*` (نجاح · 401 · 422 · 429) عبر `security_headers_middleware` — القرار على المسار من `_req_path(request)` بس.
4. **المحتوى (أقسام الملف):** `export` (نسخة الصيغة · الوقت · tw_id) · `account` (الاسم · الإيميل · الهاتف · النوع · tw_id · تاريخ التسجيل · قبول الشروط) · `profile` (كامل + خبرات · تعليم · دورات/شهادات · مهارات · لغات · روابط + روابط الصورة والغلاف — كل سجل دورة / تعليم فيه `has_certificate` بس، **بدون** `certificate_path` (task 8.7 — بـ `FORBIDDEN_KEYS`؛ الملف نفسه بيوصله المالك من `GET /certificates/{kind}/{id}/view` — `docs/rules/certificates.md`)) · `company` (للشركة: الملف · الشعار · الفروع · الوظائف + `applicants_count` بس · إعدادات الشركة) · `posts` · `comments` (تبعه هو) · `saved_posts` · `appreciated_posts` · `following` / `followers` (tw_id + الاسم العام، حسابات فعّالة بس `bs.active_sql`) · `blocked` (tw_id بس) · `applications` (الوظيفة · الشركة · التاريخ · رسالة التقديم تبعه · الحالة من `applicant_visible_status`) · `messages_sent` (اللي هو بعتها بس: النص · الوقت · `conversation_with_tw_id` — المحادثة = الطرف التاني، ما في جدول محادثات) · `appointments` (الوقت · الحالة · الدور · `my_notes` بس إذا هو كاتبها) · `notifications` (النص كما وصله) · `email_notifications` · `kyc` (الخطوة · الحالة · التواريخ · `reject_reason` بس إذا مرفوض · هل في وثيقة — بدون مسارها).
5. **طرف تاني محذوف** (رسالة · حظر · شركة طلب) → tw_id = `null` + `is_deleted` / الاسم «حساب محذوف» (`account_deletion.scrub`) — نفس قاعدة السجلات المشتركة.
6. **ممنوع بالملف (أي عمق):** `password_hash` · `session_version` · أي توكن / OTP / رابط reset / سر MFA · `deleted_*` · `suspended_*` · `admin_note` / `admin_hidden_reason` / سجل الأدمن · IPs · مسارات وثائق KYC (`id_front_url` / `selfie_url`) · بيانات خاصة بغيره (رسائل الطرف التاني · ملاحظات الشركة / الـ pipeline / بنك المواهب · بيانات المتقدمين لوظائف الشركة). `data_export.forbidden_keys()` بيفحص الملف قبل ما يطلع (لقى مفتاح ممنوع → خطأ سيرفر 500، الملف ما بيطلع).
7. **وثائق KYC = طلب منفصل:** `POST /me/export/kyc-docs` بنفس البوابة (كلمة السر من جديد · حجز `data_export_kyc` قبل bcrypt) → `{ok, data:{expires_in, docs:[{kind, url, reason}]}}`. المسارات من صف `kyc_submissions` تبع المستخدم بس (`WHERE user_id = <JWT>`) ← `_kyc_doc_path_reason(value, uid, kind)` (لازم `kyc-docs/{uid}_{kind}_{12hex}.{ext}`) ← `_sign_kyc_doc(name, ttl)` (نفس دالة توقيع الأدمن). مسار مش إله → `url: null` + `reason`. ما في وثائق → `docs: []`. ❌ اسم ملف / مسار من الطلب.
8. **الواجهة (`settings.html` قسم «الخصوصية وبياناتك» + `static/settings/settings.js`):** سطر «تنزيل بياناتي» → `twModal` بكلمة السر → `twApi('/me/export')` → حفظ الملف (Blob) + toast نجاح **بس على `res.ok`** · غلط → خطأ تحت الحقل والنافذة بتضل · 401 → بدون toast. جوّا النافذة خيار منفصل «تنزيل وثائق التوثيق» بتحذير (حساسة · الروابط بتنتهي خلال `twLimit('data_export_kyc_url_ttl_s')`) → طلب منفصل → روابط عبر `twSafeLinkUrl` (`rel="noopener noreferrer"`، تبويب جديد). نصوص `settings.export.*` (twT) · أيقونات `download` / `alert` (DS-ICON) · ألوان tokens.

## ممنوعات

- ❌ باني تاني لملف البيانات أو قسم بيتجمّع بالواجهة · ❌ `SELECT *` بأي قسم.
- ❌ bcrypt قبل `_rate_reserve` · ❌ 401 لكلمة سر غلط · ❌ `_rate_release` بعد التنزيل.
- ❌ مسار ملف شهادة (`certificate_path`) أو رابطه الموقّع بالملف (task 8.7).
- ❌ وثائق KYC جوّا ملف JSON · ❌ توقيع مسار من الطلب أو مسار مستخدم تاني · ❌ رابط أطول من `data_export_kyc_url_ttl_s` · ❌ تسجيل رابط موقّع باللوج.
- ❌ رسائل الطرف التاني · ملاحظات / مراحل الشركة · بيانات المتقدمين (غير العدد) بالملف.
- ❌ قرار على المسار من غير `_req_path(request)` · ❌ رقم حد مكتوب بالكود — `tw_limits.py`.
