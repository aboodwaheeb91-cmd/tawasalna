# Unified Admin Settings (task 4.1)

> قوانين إلزامية بنفس قوة `CLAUDE.md` لأي مهمة بتلمس حد أو rate قابل للتعديل من الأدمن، أو بتضيف إعداد جديد.
> المواصفة: `docs/SYSTEMS_INDEX.md` §25g · `ARCHITECTURE.md` §78 · الحدود الافتراضية: §54n / `tw_limits.py`.

## Settings Rules (mandatory for all AI sessions)

1. **مصدر واحد:** `tw_settings.py` — `REGISTRY` = allowlist صريحة (المفتاح · النوع · min · max · الافتراضي من `tw_limits` · `security` · `requires_restart` · المجموعة · مفتاح twT للاسم والوصف `settings.item.<key>` / `.desc`). إعداد جديد = سطر بـ `_DEFS` + مفتاحين نص + سطر بجدول PR بيعتمده صاحب المشروع. ❌ فتح كل مفاتيح `tw_limits` تلقائياً.

2. **القراءة من دالة وحدة:** `tw_settings.limit(name)` / `tw_settings.rate(name)` / `tw_settings.value(key)` — ذاكرة بس (ما في DB بالقراءة، آمنة جوّا `async def` وتحت `_rate_lock`). `_too_long` · `_rate_ok` · `_rate_key_ttl` · `post_tags_max` · `window.TW_LIMITS` (`tw_limits.page_block(tw_settings.limit)`) كلهم بيمرّوا منها. ❌ `tw_limits.LIMITS["x"]` / `RATES["x"]` مباشرة لمفتاح بالـ registry.

3. **التخزين:** جدول `app_settings` (القيم المعدّلة بس — قيمة = الافتراضي → السطر بينحذف). الكتابة بـ transaction وحدة (`FOR UPDATE` على السطر → القيمة السابقة → الجديدة). migration: `tw_settings.migrate_app_settings` (اختيارية) + `docs/migrations/4.1_app_settings.sql` للإنتاج (فحص قراءة قبل التطبيق).

4. **الكاش:** التعديل بيسري فوراً بالـ worker اللي حفظ (الكاش بيتحدّث بعد الـ commit + `window.TW_LIMITS` بينبنى من جديد). أي worker / instance تاني بيقرأ القاعدة كل `CACHE_TTL_S` = **30 ثانية** (`_settings_loop` بـ `server.py`) — التأخير ما بيتعدّى 30 ثانية. فشل القاعدة → الافتراضي + تسجيل الخطأ، والموقع ما بيوقع. قيمة مخزّنة برّا النطاق أو مفتاح مش بالـ registry → بتنتجاهل (مع log).

5. **الـ API (`server.py`):** `GET /admin/settings` (القائمة: القيمة · الافتراضي · النطاق · الاسم · الوصف · `changed` · `requires_restart` · `cache_ttl_s`) · `PUT /admin/settings/{key}` `{value: int}` · `POST /admin/settings/{key}/reset`. الصلاحية `settings.edit` عبر `check_admin(request, "settings.edit")` على التلاتة (الأدمن الرئيسي `perms: ["*"]`): بدون توكن / توكن غلط → 401 · توكن أدمن بدون الصلاحية → 403 — قبل أي شي عن المفتاح. مفتاح برّا الـ allowlist → 404 · نوع غلط (نص · كسر · bool · فاضي) → 422 `invalid_type` · برّا النطاق → 422 `out_of_range` — رسالة عربية من twT (`settings.error.*`)، `field: "value"`.

6. **السجل:** نفس `admin_audit_log` (§25b) — `admin_audit_middleware` الكاتب الوحيد؛ الـ endpoint بيحط `request.state.audit_change = (old, new)` والصف بيطلع فيه: `actor` (المستخدم) · `target` = `key=<المفتاح>` · `old_value` · `new_value` · `action` = `admin_settings_update` / `admin_settings_reset` (نوع العملية) · `created_at` (الوقت). ❌ جدول سجل تاني · ❌ نداء تسجيل من الـ endpoint.

7. **الحدود الدنيا:** ما في min بيسمح بقيمة بتوقف وظيفة أساسية — عدد المرات ≥ 1 لكل rate (رسائل ≥ 5)، الأطوال فوق أي نص طبيعي. الافتراضي لازم يكون جوّا [min, max] (غير هيك السيرفر ما بيشتغل).

8. **برّا 4.1 (لـ 4.2):** أقفال الدخول `login_*` · OTP و pwreset · `password_max_bytes` · `mem_store_*` · السعات والكاش (`ip_country_cache_*`) · أحجام الصفحات (`mention_limit_max` · `comments_page*` · `blocks_page_max`) · `view_count` / `report_repeat` (نوافذ منع تكرار). `security: true` محجوز لهدول.

9. **ممنوع أي سر:** الـ registry أرقام حدود بس — ❌ مفتاح خدمة / توكن / كلمة سر / متغيّر بيئة بالشاشة أو بالـ API.

10. **الشاشة:** `admin-settings.html` = جذر اللوحة + `/settings` (سطر `settings` بـ `TW_ADMIN_SECTIONS`) + `static/admin-settings/admin-settings.js` على الـ Admin Shell: كرت لكل مجموعة · لكل إعداد: الاسم · الوصف · حقل رقم · «المسموح من … لـ … · الافتراضي …» · شارة «معدّل» · حفظ · إرجاع للافتراضي (مطفّي إذا مش معدّل) · تنبيه `requires_restart` قبل الحفظ (بالسطر وبنص التأكيد). الحفظ والإرجاع عبر `TwAdminShell.run` بتأكيد فيه القيمة القديمة والجديدة. فحص الصفحة UX بس — السيرفر هو اللي بيرفض.
   - ملاحظة: `TwAdminSession.fetch` بيعتبر 403 نهاية جلسة (5.3a) — لما تنضاف حسابات staff بصلاحيات أقل، لازم يتفرّق 403 الصلاحية عن انتهاء الجلسة.

Test: `python -m pytest tests/test_admin_settings.py -q` (401 / 403 / 200 · نطاق / نوع / مفتاح مش بالقائمة · `message_send` و `message_max` بيسروا فوراً · الإرجاع · السجل للحالتين · فشل القاعدة → الافتراضي · الـ registry allowlist).
