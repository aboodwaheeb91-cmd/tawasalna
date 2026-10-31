# Account Deletion — الحذف الناعم + الاستعادة + «حساب محذوف» + الحذف النهائي + حذف صاحب الحساب (task 8.5a · 8.5c · 8.5d · F27)

> إلزامي بنفس قوة `CLAUDE.md`. Spec: `docs/SYSTEMS_INDEX.md §25i` · `docs/ADMIN_ENTITY_MAP.md §1` · tests `python -m pytest tests/test_account_deletion_85a.py -q` · `python -m pytest tests/test_account_purge_85c.py -q` · `python -m pytest tests/test_account_self_delete_85d.py -q` (SECURITY_TESTS).

## المصدر الوحيد

- **`account_deletion.py`** (`ad`) — الـ migration (`migrate_account_deletion`، حرجة، بعد `blocks_suspension`) · الكاتب الوحيد `soft_delete(uid, by, kind, reason)` / `restore(uid, by, reason)` · أثر الحذف على الناس التانيين `apply_effects(uid)` · القراءة للأدمن `get_deletion` · التنقية `scrub()` + `deleted_label()` (twT `account.deleted` = «حساب محذوف»).
- **الأعمدة:** `users.deleted_at` · `deleted_by` (`sub` الأدمن) · `deleted_kind` (`'admin'` | `'self'` — `CHECK users_deleted_kind_chk`) · `deleted_reason` (للأدمن بس، ≤ `LIMITS["account_reason_max"]`، فاضي لـ `self`). الإنتاج: `docs/migrations/8.5a_soft_delete.sql` (فحص قراءة أولاً).
- **ما في حذف نهائي من أي مسار طلب** — الحذف الناعم بيخلّي الصف وكل الصفوف المربوطة فيه. النهائي بس من المهمة المجدولة اليومية `account_purge` (task 8.5c — القسم «الحذف النهائي» تحت).

## القواعد

1. **الحذف = `ad.soft_delete`** بتحديث واحد: `deleted_*` + `session_version + 1` + حذف روابط استرجاع كلمة السر المعلّقة، بشرط `deleted_at IS NULL` (طلبين مع بعض → واحد بيغيّر، التاني `changed: false`). الاستعادة = `ad.restore` بتحديث واحد: `deleted_* = NULL` + `session_version + 1` (التوكنات القديمة بتضل ميتة → دخول جديد).
2. **الجلسة:** `auth.get_session_state` بيرجّع `deleted` → `server._jwt_revoked_by_password_change` بيرفض → 401 بكل طلب · بعد الحذف الكاش بيتحدّث فوراً + `_ws_revoke_user(uid, "admin_deleted")` (4008).
3. **الظهور = نفس قاعدة التعليق:** `bs.active_sql` / `bs.visible_sql` / `bs.is_hidden` / `bs.is_suspended` بتخفي المحذوف متل المعلّق (الملف · `/u/{tw_id}` · المنشورات · التعليقات + عدّادها · الوظائف · البحث · المتابعون + عدّادهم). `followers_count` = صفوف المتابعة من حسابات فعّالة (`bs.active_sql` — مش معلّق ومش محذوف)، ونفس الرقم لكل المشاهدين: الحظر بيخفي من القائمة بس، مش من العدّاد (نفس الشي `following_count`) — `docs/rules/blocks-suspension.md` القاعدة 3.
4. **السجلات المشتركة بتضل باسم «حساب محذوف»:** المحادثات + عدّاد غير المقروء (`bs.visible_sql(..., keep_deleted=True)` — للسجلات المشتركة بس) · قائمة المتقدمين + الـ pipeline (`get_job_applicants`) · «طلباتي» (`company_name`) · المواعيد (القائمة · الغرفة · المشاركون · الأحداث · الرسائل) · إشعار إلغاء المقابلة. التنقية **بالسيرفر** عبر `ad.scrub` / `_appt_scrub`: الاسم = «حساب محذوف»، و `tw_id` / الصورة / الإيميل / الهاتف / headline = `null` + علم `is_deleted` (أو `company_deleted` / `applicant_deleted` / `sender_deleted` / `actor_deleted`).
5. **الإرسال للمحذوف مرفوض:** `MESSAGE_POLICY_FACTS_SQL` (قاعدة الظهور العادية) → 404 `not_found` · `can-send` = false · أحداث الـ WS بتنرمى. **(8.5d)** في رسائل سابقة بينهم → السبب `peer_deleted` (403، twT `msg.policy.peer_deleted` «لا يمكن الرد على هذا الحساب») والمحادثة قراءة بس؛ بدون رسائل سابقة → نفس `not_found` (تجربة أرقام ما بتكشف الحذف).
6. **الدخول:** محذوف + كلمة سر صح → 401 `account_deleted` «الحساب غير متاح» بدون توكن + `restorable` / `restore_until` (8.5d — القسم تحت) · كلمة سر غلط → نفس الرد العادي · استرجاع كلمة السر → نفس الرد العام وما بينبعت إيميل (`get_user_for_password_reset` بيتجاهل المحذوف) · التسجيل بإيميله → نفس رد «الإيميل مستعمل» (الصف موجود). ما في رد بيقول «محذوف» لغير الأدمن.
7. **أثر الحذف (`ad.apply_effects` — بيتنادى من الطلب اللي غيّر الحالة بس):** شركة → وظائفها النشطة / الموقوفة بتتسكّر عبر `auth.set_job_status` + إشعار داخلي **واحد** لكل متقدم لسا قيد المراجعة (`application_closed`، بدون سبب، `event_key account_closed:{uid}:{وقت الحذف}`) · أي حساب → المقابلات القادمة بتنلغى عبر `auth.cancel_appointment` (الطرف التاني بيوصله إشعاره باسم «حساب محذوف»). `create_notification` ما بيكتب شي لمستلم محذوف (ولا إيميل).
8. **الاستعادة:** ما بتفتح الوظائف ولا بترجّع المقابلات · المحتوى بيرجع يظهر · السبب إجباري وبينحفظ بسجل الأدمن (`new_value`). **بعد ما يبلّش الحذف النهائي ← 409** `purging` / `already_purged` (task 8.5c).
9. **الأدمن:** `DELETE /admin/user/{id}` `{reason?}` · `POST /admin/user/{id}/restore` `{reason}` — `check_admin(request, "users.delete")` بأول سطر (صلاحية المالك → التحقق الإضافي 428 `step_up_required`) · مستخدم / بدون توكن 401 · أدمن بدون الصلاحية 403 · بيتسجّلوا بـ `admin_audit_middleware`. الواجهة: `admin-view` — «حذف الحساب» (سبب اختياري ثم كتابة «حذف») / شارة «محذوف» + التاريخ + النوع + السبب / «استعادة الحساب» (سبب إجباري ثم تأكيد) · قائمة المستخدمين بتعرض الشارة وبتشيل زر الحذف · هدف البلاغ لحساب محذوف = «حساب محذوف» بدون رابط ولا زر حذف. كل كتابة عبر `TwAdminShell.run`.
10. **مسار صاحب الحساب** `DELETE /auth/user/{id}/delete` = حذف ناعم `kind='self'` عبر `ad.soft_delete` + نفس `apply_effects` (task 8.5d — القسم «حذف صاحب الحساب والاستعادة»).

## حذف صاحب الحساب والاستعادة (task 8.5d)

قرارات صاحب المشروع: مهلة التراجع = `tw_settings.limit("account_purge_days")` (30 — ممنوع الرقم بالكود) · الدخول لحاله ما بيرجّع الحساب · الاستعادة طلب منفصل بكلمة السر ونجاحها بيرجّع توكن جديد · حذف الأدمن بيرجع بقرار الأدمن بس · التأكيد = كلمة السر + كتابة «حذف» · إيميل أمان عند الحذف وعند الاستعادة بدون رابط · الرسائل بتضل عند الطرف التاني والـ composer مع المحذوف قراءة بس.

1. **الحذف** `DELETE /auth/user/{id}/delete` `{password, confirm}` (`Optional[AccountDeleteInput] = Body(None)`) — الترتيب ثابت: JWT → رقم المسار ≠ JWT → 403 بدون أي معلومة → كلمة السر فاضية → 422 `required` (بدون حجز) → `confirm !== "delete"` → 422 `confirm_required` بالحقل `confirm` (بدون حجز) → `_rate_reserve([("account_delete", uid)])` **قبل bcrypt** (ممتلئ → 429، والحجز ما بيرجع) → `check_user_password` غلط → 422 `wrong_password` بالحقل `password` (مش 401). بعدها: `ad.soft_delete(uid, "self", "self")` → `_password_changed_cache_set` → `_ws_revoke_user(uid, "self_deleted")` → إذا `changed`: `ad.apply_effects(uid)` (الفشل بيتسجّل والحذف بيضل) + `send_email` قالب `account_deleted` **مرة وحدة** → `{deleted, purge_after}`. `changed=false` (طلبين مع بعض) → ما في effects ولا إيميل تاني.
2. **الاستعادة** `POST /auth/restore` `{email, password}` بدون JWT — `_login_reserve` (نفس ميزانية الدخول) + `RATES["account_restore"]` (لكل إيميل) **قبل bcrypt**. إيميل مش موجود / كلمة سر غلط / حساب مش موجود → رد الدخول العام 401 **حرفياً** (`authenticate_user` بيعمل bcrypt وهمي للإيميل المش موجود — نفس التوقيت). كلمة سر صح → `ad.restore(uid, "self", None, self_only=True)` بيفحص **جوّا نفس الـ `FOR UPDATE`** بالترتيب: مش محذوف → 409 `not_deleted` · `deleted_kind='admin'` → 403 `admin_deleted` «الحساب غير متاح، تواصل مع الدعم» · الحذف النهائي بلّش / خلص → 409 `purging` / `already_purged` · `deleted_at` أقدم من المدة → 409 `expired` · نجاح → توكن بـ `session_version` الجديد (متل الدخول — التوكنات القديمة ميتة) + `_rate_release` + إيميل `account_restored` مرة وحدة (`changed` بس).
3. **الدخول** محذوف + كلمة سر صح → 401 `account_deleted` + `restorable` (true بس لـ `self` ضمن المهلة وبدون صف purge — `ad.restore_info`) + `restore_until` (`deleted_at + المدة`، null لغير القابل للاستعادة). كلمة سر غلط → نفس الرد العادي بدون أي تغيير.
4. **الإيميل:** قالبين SECURITY (`account_deleted` {name, date} · `account_restored` {name}) — `send_email` ما بيمنع مستلم محذوف (القوالب الأمنية)؛ `create_notification` بيضل يمنعه. التاريخ عبر `server._fmt_date` (نفس شكل `twFormatDate`). بدون رابط — طريقة الاستعادة = صفحة الدخول بكلمة السر (`docs/rules/email.md`).
5. **الواجهة:** `/settings` «منطقة الخطر» → `twModal`: تحذير (المهلة `twLimit('account_purge_days')` + طريقة الاستعادة؛ للشركة: الوظائف بتتسكّر والمقابلات بتنلغى) + حقل كلمة السر + حقل «اكتب حذف» · الزر معطّل لحد ما الكلمة تطابق (والسيرفر بيفحص `confirm`) · 422 → الخطأ تحت الحقل والنافذة بتضل · 429 → toast · نجاح → `TwAuthSync.invalidateSession('account_deleted', {redirect: '/login?account=deleted'})` (نفس طريقة الخروج) → `/login` برسالة. `/login` (`index.auth.js`): `account_deleted` + `restorable` → رسالة فيها `restore_until` + زر «استعادة حسابي» → `twConfirm` → `POST /auth/restore` بنفس الإيميل وكلمة السر المكتوبين (طلب منفصل) → نفس مسار نجاح الدخول · `restorable=false` → «الحساب غير متاح» بس · 403 `admin_deleted` → نص التواصل مع الدعم. `/messages`: `peer_deleted` → الـ composer مخفي ومكانه السبب، بدون «إنهاء المحادثة» ولا زر موعد ولا رابط ملف؛ الاسم «حساب محذوف» من السيرفر (`ad.scrub`).

## الحذف النهائي (task 8.5c)

- **المصدر الوحيد:** `account_purge.py` — migration `account_purge` (حرجة، بعد `account_deletion`؛ الإنتاج `docs/migrations/8.5c_account_purge.sql`) · المهمة اليومية `account_purge` بـ `scheduler_jobs` (`auth._SCHEDULER_HANDLERS`؛ كل دورة scheduler بتتأكد إن مهمة اليوم الجاي موجودة — `ensure_daily_job`، 03:00 UTC، `dedupe_key account_purge:{التاريخ}`، ما بتكون مستحقة وقت إنشائها) → `run_daily()`.
- **المدة:** `tw_settings.limit("account_purge_days")` = 30 يوم من `deleted_at` (للنوعين `admin` و `self`) · `account_purge_batch` · `account_purge_retry_max_hours` — كلهم بـ `tw_limits.py`.
- **الطابور `account_purge`:** `user_id` (PK) · `stage` `files` → `db` → `done` · `attempts` · `next_attempt_at` · `last_error` (كود / عدد / status بس — ما في اسم ولا إيميل ولا هاتف ولا اسم ملف).
  1. **claim:** لكل حساب: `SELECT … FROM users … FOR UPDATE` (نفس قفل `ad.restore`) + لسا محذوف + أقدم من المدة → صف `files`.
  2. **files:** كل ملفات الحساب بكل الـ buckets (`avatars` · `kyc-docs`): المسارات المخزّنة بصفوفه (`profiles.avatar_url` / `cover_url` · `company_profiles.cover_url` · `kyc_submissions.id_front_url` / `selfie_url`) + كل object اسمه `{uid}_…` من `storage_list` (الصور القديمة اللي انبدلت) — بس الأسماء `{uid}_{kind}_{12 hex}.{ext}` لنفس الحساب (F24، ما بينحذف ملف غيره) → `server.storage_delete` (`docs/rules/upload.md` القاعدة 11). 404 = نجاح. أي فشل → `attempts + 1` + `next_attempt_at = NOW() + 2^attempts ساعة` (≤ السقف) والقاعدة **ما بتنلمس**؛ المحاولة الجاية بتعيد الكل (المحذوف = 404 = نجاح).
  3. **db:** transaction وحدة: صف users `FOR UPDATE` + لسا محذوف + أقدم من المدة + الطابور `db` → الجدول تحت → tombstone → `done`.
  4. **retention** (بنفس المهمة): صفوف مربوطة بحساب انحذف نهائياً بتنحذف بعد مدتها — `admin_audit_log` (`target user_id=N`) بعد `retention_admin_audit_days` (730) · `reports` (مبلّغ أو مبلَّغ عنه) بعد `retention_reports_days` (365) · `appointment_events` (الفاعل أو موعد هو طرفه) بعد `retention_appointment_events_days` (365).
- **tombstone `users`:** بيضل `id` · `user_type` · `created_at` · `deleted_at` · `deleted_kind` · `purged_at` (حتى الـ FKs والسجلات المشتركة تضل) · `email = '#purged:{id}'` (قيمة داخلية فريدة مش إيميل → الإيميل الأصلي حر: التسجيل فيه = حساب جديد ما بيورث شي) · `password_hash` = bcrypt لسر عشوائي محدش بيعرفه · `full_name = ''` · `tw_id` / `deleted_by` / `deleted_reason` / `suspended_*` / `terms_*` / `country_code` = NULL · التوثيق false · `session_version + 1`.
- **الظهور بعد النهائي:** نفس الحذف الناعم (`deleted_at` باقي) — المحتوى مخفي والسجلات المشتركة باسم «حساب محذوف». admin-view: شارة «محذوف نهائياً» / «الحذف النهائي جارٍ» (`profile.deletion.purge` = `purged` | `purging`) بدون زر استعادة.

### جدول الحذف النهائي (القاعدة: اللي عمله عن حاله ← حذف · سجل مشترك ← الصف بيضل والنسخ الشخصية NULL · سجل طرف تاني عنه ← بيضل)

| الجدول | القرار | السبب |
|--------|--------|-------|
| `profiles` · `company_profiles` · `company_branches` · `company_settings` · `experience` · `education` · `user_skills` · `user_langs` · `user_links` · `courses` | حذف | ملفه هو |
| `kyc_submissions` (+ ملفاتها) · `password_reset_tokens` (استرجاع + تغيير إيميل) · `email_notify_prefs` · `email_send_log` · `feed_snapshots` · `profession_suggestions` | حذف | توثيقه / توكناته / OTP / تفضيلاته |
| `company_posts` (+ CASCADE تعليقات وتقديرات وحفظ ومشاهدات غيره عليها) · `company_post_comments` (تبعه — ردود غيره `reply_to` → NULL) · `company_post_appreciations` · `company_post_saves` · `company_post_views` (هو المشاهد) · `company_post_comment_mentions` (بتشير لـ `tw_id` تبعه) | حذف | محتواه وتفاعله |
| `profile_follows` · `profile_interests` · `profile_views` · `blocks` (الاتجاهين) | حذف | متابعاته / حظره — الطرف التاني انحذف |
| `notifications` | حذف: إله + أي إشعار هو فاعله (`actor_id` / `last_actor_id`) + أي إشعار نصّه فيه معرّف دقيق (إيميله / `tw_id` / هاتفه / `contact_email`) · **الاسم ما بينحذف فيه أبداً**: بإشعارات اللي تعامل معهم بس (طرف رسائل · شركة قدّم عندها / متقدم على وظائفه · طرف موعد · متابِع / متابَع · `profile_interests` · `profile_views` · تفاعل / تعليق على منشوراته أو على منشور علّق عليه) الاسم بـ `title` / `body` بيصير «حساب محذوف» (`ad.deleted_label()`) — المجموعة بتنحسب بأول الـ transaction قبل `_OWN_DELETES` | اسم شائع كان بيحذف إشعارات ناس ما إلهم علاقة (task 8.5c-2) |
| `company_ratings` (هو المقيِّم) | حذف | محتواه |
| `company_saved_candidates` · `candidate_bank_notes` · `company_candidate_job_refs` (هو الشركة) · `pipeline_notes` (كتبها أو على pipeline شركته) | حذف | ملاحظات شركته الخاصة |
| `support_tickets` (حسابه أو `guest_email` = إيميله — CASCADE رسائلها وتوكناتها) · `support_guest_otp` (إيميله) | حذف | تذاكره هو |
| `messages` · `appointment_messages` | بيضل كما هو | رسائله بتضل عند الطرف التاني باسم «حساب محذوف» |
| `job_applications` | بيضل · `cover_letter` = NULL | سجل مشترك (الشركة) |
| `jobs` (هو الشركة) | بيضل (مسكّرة من 8.5a) · `description` = NULL | طلبات غيره مربوطة فيها (CASCADE كان رح يمسحها) |
| `appointments` · `appointment_participants` | بيضل · هو الشركة / المنشئ → `representative_name` / `notes` / `location_text` / `online_url` = NULL · هو الممثّل → `representative_user_id` / `representative_name` = NULL | سجل مشترك |
| `appointment_events` | بيضل برقم داخلي · `payload` (سبب كتبه) = NULL لأحداثه · بينحذف بعد سنة | سجل المواعيد |
| `job_pipeline_entries` · `conversation_endings` | بيضل كما هو | سجل مشترك بدون نص شخصي |
| `pipeline_stage_events` | بيضل · `reason` = NULL لأحداثه | سجل مشترك |
| `reports` (مبلِّغ أو مبلَّغ عنه) | بيضل برقم داخلي · `reason` / `target_url` = NULL · بينحذف بعد سنة | البلاغات |
| `admin_audit_log` | بيضل برقم داخلي · `old_value` / `new_value` = NULL للصفوف عنه (`target user_id=N`) + لأي صف نصه فيه معرّف دقيق (إيميله / `tw_id` / هاتفه / `contact_email`) — **مش الاسم** (ما بيلمس سجل حساب تاني بنفس الاسم — task 8.5c-2) · بينحذف بعد سنتين | سجل الأدمن — `actor` دايماً أدمن / موظف (ما في `ip` لأفعال المستخدم بهالجدول) |
| `company_ratings` (عن شركته) · `company_saved_candidates` / `candidate_bank_notes` / `company_candidate_job_refs` / `job_pipeline_entries` / `pipeline_notes` (هو المرشّح عند شركة تانية) | بيضل | سجلات أطراف تانية عنه (نصوصهم مش نصه) |
| `scheduler_jobs` | بيضل | `payload` أرقام داخلية بس؛ handlers بتعيد قراءة القاعدة |
| `account_purge` | بيضل (`done`) | رقم داخلي بس |

## ممنوعات

- ❌ `DELETE FROM users` بأي مسار (الحذف النهائي = tombstone) · ❌ كتابة `users.deleted_*` برّا `ad.soft_delete` / `ad.restore` · ❌ كتابة `purged_at` / الـ tombstone برّا `account_purge.purge_db`.
- ❌ حذف نهائي من طلب HTTP · ❌ مرحلة القاعدة قبل ما تخلص الملفات · ❌ حذف ملف مش مسمّى `{uid}_…` لنفس الحساب · ❌ استدعاء Supabase Storage للحذف برّا `server.storage_delete`.
- ❌ استعادة بعد ما بلّش الحذف النهائي · ❌ claim أو استعادة بدون `FOR UPDATE` على صف users.
- ❌ اسم / إيميل / هاتف / اسم ملف بـ `account_purge.last_error` أو بالـ log · ❌ مدة (30 / 365 / 730) مكتوبة بالكود — `tw_limits.py`.
- ❌ قاعدة ظهور تانية للمحذوف — `bs.active_sql` / `bs.visible_sql` بس · ❌ `keep_deleted=True` برّا السجلات المشتركة (محادثات · عدّاد غير المقروء).
- ❌ إرجاع اسم / صورة / `tw_id` / إيميل / هاتف حساب محذوف بأي رد لغير الأدمن · ❌ التنقية بالواجهة بدل السيرفر.
- ❌ رد بيقول «محذوف» بالدخول / الاسترجاع / التسجيل.
- ❌ إشعار أو إيميل للحساب المحذوف · ❌ إشعار متقدم مرتين لنفس الحذف · ❌ ذكر سبب الحذف بإشعار.
- ❌ الاستعادة بترجّع التوكنات القديمة أو بتفتح الوظائف / المقابلات.
- ❌ قرار على المسار من غير `_req_path(request)`.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py`.
- ❌ bcrypt قبل الحجز بالحذف أو الاستعادة · ❌ 401 لكلمة سر غلط بالحذف · ❌ `Body(default={})` بدون `Optional`.
- ❌ رد استعادة بيختلف (نص أو توقيت) بين إيميل مش موجود وكلمة سر غلط · ❌ رد بيكشف «محذوف» لحدا ما معه كلمة السر.
- ❌ فحص المهلة / النوع بالاستعادة قبل القفل (`self_only` جوّا `FOR UPDATE` بس) · ❌ صاحب الحساب بيستعيد حذف الأدمن.
- ❌ الدخول لحاله بيرجّع الحساب · ❌ رابط بإيميل الحذف / الاستعادة · ❌ إيميل أو effects مرتين لنفس الحذف.
- ❌ composer أو «إنهاء المحادثة» أو زر موعد مع محذوف · ❌ `peer_deleted` بدون رسائل سابقة.
