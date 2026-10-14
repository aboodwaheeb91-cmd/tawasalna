# Unified Email System + Forgot Password (task 5.1a)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتبعت إيميل أو بتلمس إعادة تعيين كلمة السر.
> المواصفة: `docs/SYSTEMS_INDEX.md` §54j (الإيميل) + §1b (نسيت كلمة المرور) · `ARCHITECTURE.md → Unified Email System + Password Reset (5.1a)`.

## Email Rules (mandatory for all AI sessions)

1. **مرسل واحد:** `email_service.send_email(to, template_key, vars)` هي الدالة الوحيدة اللي بتبعت إيميل بالموقع (Resend HTTP API — Railway بيسكّر SMTP). ما بترمي أبداً؛ بترجّع `{ok, code}` — `sent` · `unavailable` (مفتاح غايب) · `disabled` (النوع مطفّى) · `invalid` · `failed`.
2. **المفتاح:** `RESEND_API_KEY` من البيئة بس. ممنوع يطلع بأي log أو رد أو صفحة. `/health` → `email: configured | missing` · `GET /admin/email` → `status` بس.
3. **التحكم الكامل:** `site_settings[email_settings]` = `from_address` (افتراضي `no-reply@tawasolna.com`) · `from_name` («تواصلنا») · `site_url` (أصل روابط الإيميل — **مش** من `Host` header: reset-link poisoning) · `types` (تشغيل / إيقاف كل نوع). الأدمن: `GET` / `PUT /admin/email` + `POST /admin/email/test` (`check_admin`).
4. **القوالب:** نوع جديد = سطر بـ `TEMPLATES` (`email_service.py`) + مفاتيح `email.<type>.<part>` بـ `tw_strings.json` (قابلة للتعديل من الأدمن عبر `PUT /admin/strings`) + بـ `TYPES` إذا الأدمن لازم يقدر يطفّيه. قالب HTML واحد RTL (ألوان من primitives `tw_shared.css`) + نسخة نص عادي. كل متغيّر مُهرَّب بالـ HTML؛ العنوان بدون أسطر جديدة؛ زر الرابط بس لـ `https://`.
5. **الـ logs:** النوع + السبب بس (`http 500` / نوع الخطأ) — ❌ المفتاح · ❌ عنوان المستلم · ❌ النص · ❌ رابط / توكن.
- ❌ `smtplib` / مزوّد تاني / `urlopen` لـ Resend برّا `email_service.py` · ❌ نص إيميل ثابت بالكود · ❌ رابط إيميل مبني من `request` · ❌ تشغيل `is_email_otp_delivery_available()` (KYC = 5.1b).

## Forgot Password Rules (mandatory for all AI sessions)

1. **طلب الرابط** `POST /auth/password-reset/request {email}` → **نفس الرد دايماً** `{ok:true, data:{sent:true}}` لإيميل موجود وغير موجود؛ البحث + التوكن + الإيميل بـ `BackgroundTasks` بعد الرد (ما في فرق وقت). حدود على `_rate_store` المشترك: لكل IP (`get_client_ip`) 10 / ساعة → 429 · لكل إيميل 3 / ساعة → نفس الرد بدون إرسال. خدمة الإيميل غير متاحة / النوع مطفّى → 503 `email_unavailable` (عام — ما بيكشف شي).
2. **التوكن** (`auth.py`): `secrets.token_urlsafe(32)` · مخزّن HMAC بس (`v1$` — متل الـ OTP) بجدول `password_reset_tokens` · 30 دقيقة (ساعة الـ DB) · استعمال مرة (`DELETE … RETURNING`) · توكن جديد بيحذف كل الأقدم لنفس المستخدم.
3. **الرابط** `{site_url}/reset-password#token=…` — بالـ fragment (ما بيوصل للسيرفر / الـ logs / Referer)؛ الصفحة بتشيله من شريط العنوان فوراً.
4. **التعيين** `POST /auth/password-reset/confirm {token, new_password}` → `_password_policy_error` (نفس قاعدة التسجيل) → `set_user_password` (بيكتب `password_changed_at`) → `_password_changed_cache_set` + `_ws_revoke_user(uid, "password_reset")` (كل الجلسات القديمة بتطلع) + فك قفل الدخول للإيميل + إيميل «تغيّرت كلمة مرورك». ما في دخول تلقائي.
- ❌ رد بيختلف حسب وجود الإيميل · ❌ التوكن نص عادي بالـ DB أو بالـ log · ❌ التوكن بـ query string · ❌ كتابة `password_hash` بدون `set_user_password` · ❌ مسار بينهي جلسات بدون `_ws_revoke_user`.

Test: `python -m pytest tests/test_password_reset_email.py -q` (Resend مزيّف على مستوى HTTP + PostgreSQL حقيقي).
