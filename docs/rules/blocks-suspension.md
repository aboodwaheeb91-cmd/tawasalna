# Account Suspension + User Blocks — تعليق الحساب + الحظر (task 5.4)

> إلزامي بنفس قوة `CLAUDE.md`. Spec: `docs/SYSTEMS_INDEX.md §25f` · `ARCHITECTURE.md §77` · test `python -m pytest tests/test_blocks_suspension.py -q`.

## المصدر الوحيد

- **`blocks_suspension.py`** — الـ migration (`migrate_blocks_suspension`، حرجة) · قاعدة الظهور (`visible_sql` / `active_sql` / `is_hidden`) · الحظر (`block` / `unblock` / `list_blocked`) · التعليق (`set_suspension` / `get_suspension`).
- **الجداول:** `users.suspended_at` / `suspended_reason` / `suspended_by` · `blocks (blocker_id, blocked_id, created_at)` — PK على الزوج، `CHECK` ممنوع حظر النفس، `ON DELETE CASCADE`، RLS مفعّل وما في أي صلاحية لـ `anon` / `authenticated`.

## التعليق (الأدمن بس)

1. **`PUT /admin/user/{id}/suspension`** `{suspended: true|false, reason?}` — الكاتب الوحيد `bs.set_suspension`. السبب اختياري، ≤ `LIMITS["suspend_reason_max"]`، **للأدمن بس** (`GET /admin/profile/{id}` → `profile.suspension`) — ما بيطلع بأي رد عام. `suspended_by` = `sub` بتوكن الأدمن.
2. **المعلّق = 401 بكل طلب:** `auth.get_session_state` بيرجّع `suspended` → `server._jwt_revoked_by_password_change` بيرفض التوكن (نفس مسار الحساب المحذوف). بعد التعليق: الكاش بيتحدّث فوراً + `_ws_revoke_user(uid, "admin_suspend")`. الدخول: باسورد صح → 401 `account_suspended` بدون توكن. شاشة الدخول (`index.auth.js` `_loginErrorText`) بتعرض لأي فشل حساب (كلمة سر غلط · إيميل مش موجود · معلّق · محذوف) نفس النص `login.err.failed` — ما بتكشف حالة الحساب أبداً؛ القفل (429) بيضل برسالته.
3. **قابل للرجوع:** فك التعليق بيرجّع نفس الحساب ونفس التوكن (ما في `session_version` bump) ونفس المحتوى. **ممنوع حذف أو تعديل بيانات** عند التعليق.
4. **محتواه مخفي عن الكل بالاستعلام:** الملف (`/profile/{id}` · `/company/profile/{id}` · `/u/{tw_id}` → 404) · المنشورات (الفيد + `/company/posts/{id}` → 404) · التعليقات (بتنشال من القائمة) · وظائف الشركة (`get_jobs` · `get_job` · فيد الوظائف عبر `bs.active_sql`) · المحادثات · البحث.
5. غير الأدمن: `check_admin(request, "users.suspend")` — توكن أدمن بدون صلاحية `users.suspend` (موظف — خطة 5.3) → **403** · توكن مستخدم (Bearer أو بـ `X-Admin-Token`) أو بدون توكن → **401** (عقد بوابة الأدمن نفسه لكل endpoints الأدمن — PR 1.5).

## الحظر (مستخدم يحظر مستخدم)

1. **`PUT /blocks/{id|tw_id}`** · **`DELETE /blocks/{id|tw_id}`** · **`GET /blocks?limit&offset`** — JWT لازم. كل قراءة / كتابة على صفوف المستخدم نفسه بس (`blocker_id` = JWT). حد: `RATES["block_set"]` (حظر + فك) · الصفحة ≤ `LIMITS["blocks_page_max"]`. نفسك → 422 `self_block` · حساب مش موجود → 404.
2. **بالاتجاهين:** صف واحد بيخفي الطرفين عن بعض — قاعدة `bs.visible_sql(col, viewer)` (مش معلّق **و** ما في صف حظر بأي اتجاه).
3. **الحظر بيطبّق على:** الملف (+ `/profile/{id}/follow` · followers / following · `/user/lookup`) · الفيد (المنشورات) · المنشور (عرض / تقدير / حفظ / تعليقات → 404) · التعليقات (قائمة + إنشاء + المنشن + **الرد** — task 5.4c: الرد على تعليق كاتبه، أو كاتب أصل الـ thread، بينه وبين المستخدم حظر بأي اتجاه → نفس رد التعليق المش موجود (404 «التعليق المرجعي غير موجود…») عبر `bs.visible_sql("c.user_id")` بـ `auth.create_company_post_comment`، وما في إشعار رد) · البحث (`/mention/search` · اقتراحات المرشحين) · المراسلة (بدء + رد: `MESSAGE_POLICY_FACTS_SQL` عمود سادس → `not_found` 404 · قائمة المحادثات · عدّاد غير المقروء) · المتابعة (ممنوعة + `block()` بيمسح المتابعة بالاتجاهين بنفس الـ transaction) · **أحداث الـ WebSocket** (task 5.4c): `typing` / `typing_stop` / `active_conversation` بين طرفين بينهم حظر بأي اتجاه بتنرمى بصمت (ما بتوصل، ما بتعلّم المحادثة مفتوحة، وما في خطأ للمرسل) — `server._ws_peer_hidden_async` = `bs.is_hidden` (نفس قاعدة إرسال الرسائل)، بعد الـ rate limit وفحص وجود المحادثة، **بدون كاش** (الحظر بيسري فوراً)، والخطأ = مخفي (fail closed).
4. **بدون إشعار:** ولا notification ولا رسالة ولا إيميل. الطرف المحظور بيشوف «غير موجود» — نفس رد الحساب المش موجود بنص الـ endpoint نفسه. ❌ رسالة «محظور».
5. **طلبات التوظيف ما بتتأثر أبداً:** التقديم · قائمة المتقدمين · تغيير حالة الطلب · الـ pipeline · المواعيد — ما في فحص حظر فيها. الوظيفة نفسها (`/jobs` · `/jobs/{id}`) بتضل ظاهرة للمحظور (الحظر ما بيخفي وظيفة — التعليق بس).
6. **الواجهة:** زر «حظر» = `twAction('block', ctx)` (السجل فيه التأكيد DS-OVL) → `twBlockUser(id)` بـ `tw_shared.js` (الطلب الوحيد للحظر — بعد النجاح الصفحة بتروح على `twHomeHref()`) — بملف الشخص (`profile-v2.render.js`) والشركة (`company.render.js`) والجهة التعليمية (`edu-profile.html`). قائمة «المحظورون» + «إلغاء الحظر» (`twAction('unblock')`) بـ `/settings` (`static/settings/settings.js`).
7. **الأدمن:** `admin-view` — «تعليق الحساب» (نافذة سبب اختياري `TwAdminShell.formDialog` ثم تأكيد) / «فك التعليق» + شارة «معلّق» + التاريخ والسبب. كل كتابة عبر `TwAdminShell.run` وبتنسجّل بسجل الأدمن (`admin_audit_middleware`).

## ممنوعات

- ❌ قاعدة ظهور تانية (فحص حظر / تعليق يدوي بـ SQL أو بصفحة) — `bs.visible_sql` / `bs.active_sql` / `bs.is_hidden` بس.
- ❌ حذف بيانات المعلّق أو المحظور (منشورات، تعليقات، رسائل، وظائف) — الإخفاء بالاستعلام بس.
- ❌ فحص حظر بمسار طلب توظيف (apply · applicants · status · pipeline · appointments).
- ❌ إشعار أو رسالة للطرف المحظور · ❌ رد بيقول «محظور».
- ❌ كتابة `users.suspended_*` برّا `bs.set_suspension` · ❌ endpoint تعليق بدون `check_admin`.
- ❌ رقم حد مكتوب بالكود — `tw_limits.py`.
- ❌ `fetch` / `localStorage` للحظر بالصفحات — `twApi` + `twBlockUser`.
