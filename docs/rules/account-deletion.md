# Account Deletion — الحذف الناعم + الاستعادة + «حساب محذوف» (task 8.5a · F27)

> إلزامي بنفس قوة `CLAUDE.md`. Spec: `docs/SYSTEMS_INDEX.md §25i` · `docs/ADMIN_ENTITY_MAP.md §1` · test `python -m pytest tests/test_account_deletion_85a.py -q` (SECURITY_TESTS).

## المصدر الوحيد

- **`account_deletion.py`** (`ad`) — الـ migration (`migrate_account_deletion`، حرجة، بعد `blocks_suspension`) · الكاتب الوحيد `soft_delete(uid, by, kind, reason)` / `restore(uid, by, reason)` · أثر الحذف على الناس التانيين `apply_effects(uid)` · القراءة للأدمن `get_deletion` · التنقية `scrub()` + `deleted_label()` (twT `account.deleted` = «حساب محذوف»).
- **الأعمدة:** `users.deleted_at` · `deleted_by` (`sub` الأدمن) · `deleted_kind` (`'admin'` | `'self'` — `CHECK users_deleted_kind_chk`) · `deleted_reason` (للأدمن بس، ≤ `LIMITS["account_reason_max"]`، فاضي لـ `self`). الإنتاج: `docs/migrations/8.5a_soft_delete.sql` (فحص قراءة أولاً).
- **ما في حذف نهائي من أي مسار** — الصف وكل الصفوف المربوطة فيه بتضل (رسائل · طلبات · pipeline · مواعيد · منشورات · تعليقات · وظائف). النهائي بمهمة 8.5c.

## القواعد

1. **الحذف = `ad.soft_delete`** بتحديث واحد: `deleted_*` + `session_version + 1` + حذف روابط استرجاع كلمة السر المعلّقة، بشرط `deleted_at IS NULL` (طلبين مع بعض → واحد بيغيّر، التاني `changed: false`). الاستعادة = `ad.restore` بتحديث واحد: `deleted_* = NULL` + `session_version + 1` (التوكنات القديمة بتضل ميتة → دخول جديد).
2. **الجلسة:** `auth.get_session_state` بيرجّع `deleted` → `server._jwt_revoked_by_password_change` بيرفض → 401 بكل طلب · بعد الحذف الكاش بيتحدّث فوراً + `_ws_revoke_user(uid, "admin_deleted")` (4008).
3. **الظهور = نفس قاعدة التعليق:** `bs.active_sql` / `bs.visible_sql` / `bs.is_hidden` / `bs.is_suspended` بتخفي المحذوف متل المعلّق (الملف · `/u/{tw_id}` · المنشورات · التعليقات + عدّادها · الوظائف · البحث · المتابعون + عدّادهم). `followers_count` = صفوف المتابعة من حسابات فعّالة (`bs.active_sql` — مش معلّق ومش محذوف)، ونفس الرقم لكل المشاهدين: الحظر بيخفي من القائمة بس، مش من العدّاد (نفس الشي `following_count`) — `docs/rules/blocks-suspension.md` القاعدة 3.
4. **السجلات المشتركة بتضل باسم «حساب محذوف»:** المحادثات + عدّاد غير المقروء (`bs.visible_sql(..., keep_deleted=True)` — للسجلات المشتركة بس) · قائمة المتقدمين + الـ pipeline (`get_job_applicants`) · «طلباتي» (`company_name`) · المواعيد (القائمة · الغرفة · المشاركون · الأحداث · الرسائل) · إشعار إلغاء المقابلة. التنقية **بالسيرفر** عبر `ad.scrub` / `_appt_scrub`: الاسم = «حساب محذوف»، و `tw_id` / الصورة / الإيميل / الهاتف / headline = `null` + علم `is_deleted` (أو `company_deleted` / `applicant_deleted` / `sender_deleted` / `actor_deleted`).
5. **الإرسال للمحذوف مرفوض:** `MESSAGE_POLICY_FACTS_SQL` (قاعدة الظهور العادية) → 404 `not_found` · `can-send` = false · أحداث الـ WS بتنرمى.
6. **الدخول:** محذوف + كلمة سر صح → 401 `account_deleted` «الحساب غير متاح» بدون توكن · كلمة سر غلط → نفس الرد العادي · استرجاع كلمة السر → نفس الرد العام وما بينبعت إيميل (`get_user_for_password_reset` بيتجاهل المحذوف) · التسجيل بإيميله → نفس رد «الإيميل مستعمل» (الصف موجود). ما في رد بيقول «محذوف» لغير الأدمن.
7. **أثر الحذف (`ad.apply_effects` — بيتنادى من الطلب اللي غيّر الحالة بس):** شركة → وظائفها النشطة / الموقوفة بتتسكّر عبر `auth.set_job_status` + إشعار داخلي **واحد** لكل متقدم لسا قيد المراجعة (`application_closed`، بدون سبب، `event_key account_closed:{uid}:{وقت الحذف}`) · أي حساب → المقابلات القادمة بتنلغى عبر `auth.cancel_appointment` (الطرف التاني بيوصله إشعاره باسم «حساب محذوف»). `create_notification` ما بيكتب شي لمستلم محذوف (ولا إيميل).
8. **الاستعادة:** ما بتفتح الوظائف ولا بترجّع المقابلات · المحتوى بيرجع يظهر · السبب إجباري وبينحفظ بسجل الأدمن (`new_value`).
9. **الأدمن:** `DELETE /admin/user/{id}` `{reason?}` · `POST /admin/user/{id}/restore` `{reason}` — `check_admin(request, "users.delete")` بأول سطر (صلاحية المالك → التحقق الإضافي 428 `step_up_required`) · مستخدم / بدون توكن 401 · أدمن بدون الصلاحية 403 · بيتسجّلوا بـ `admin_audit_middleware`. الواجهة: `admin-view` — «حذف الحساب» (سبب اختياري ثم كتابة «حذف») / شارة «محذوف» + التاريخ + النوع + السبب / «استعادة الحساب» (سبب إجباري ثم تأكيد) · قائمة المستخدمين بتعرض الشارة وبتشيل زر الحذف · هدف البلاغ لحساب محذوف = «حساب محذوف» بدون رابط ولا زر حذف. كل كتابة عبر `TwAdminShell.run`.
10. **مسار صاحب الحساب** `DELETE /auth/user/{id}/delete` لسا 403 (بيفتح بـ 8.5d عبر `ad.soft_delete(kind='self')` + نفس `apply_effects`).

## ممنوعات

- ❌ `DELETE FROM users` بأي مسار · ❌ كتابة `users.deleted_*` برّا `ad.soft_delete` / `ad.restore`.
- ❌ قاعدة ظهور تانية للمحذوف — `bs.active_sql` / `bs.visible_sql` بس · ❌ `keep_deleted=True` برّا السجلات المشتركة (محادثات · عدّاد غير المقروء).
- ❌ إرجاع اسم / صورة / `tw_id` / إيميل / هاتف حساب محذوف بأي رد لغير الأدمن · ❌ التنقية بالواجهة بدل السيرفر.
- ❌ رد بيقول «محذوف» بالدخول / الاسترجاع / التسجيل.
- ❌ إشعار أو إيميل للحساب المحذوف · ❌ إشعار متقدم مرتين لنفس الحذف · ❌ ذكر سبب الحذف بإشعار.
- ❌ الاستعادة بترجّع التوكنات القديمة أو بتفتح الوظائف / المقابلات.
- ❌ قرار على المسار من غير `_req_path(request)`.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py`.
