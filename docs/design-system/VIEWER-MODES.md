# [DS-VM] Viewer Modes & Permissions System V1 — Tawasolna

> **النظام الرسمي لتحديد صلاحيات العرض في منصة تواصلنا.**
> هذا الملف يوثِّق الـ contract المعماري للـ Viewer Modes والـ Permissions —
> Web أولاً، مع مراعاة Flutter مستقبلاً (F1).
> لا يتضمن كوداً تنفيذياً — هذا توثيق معماري، ليس دليل CSS أو JS.

---

## [VM-00] Routing Protocol — متى تقرأ هذا الملف

**اقرأ الأقسام المحددة فقط، لا تقرأ الملف كاملاً:**

| المهمة | اقرأ |
|--------|------|
| تحديد من يرى عنصراً معيناً | **VM-01 + VM-02** |
| ربط زر بصلاحية معينة | **VM-05 + BTN-17 في BUTTONS.md** |
| تحديد مصدر الصلاحية | **VM-06** |
| فهم ما يعنيه "إخفاء" العنصر مقابل "منع الوصول" | **VM-07** |
| فهم Preview / View As | **VM-03** |
| فهم الأربعة مفاهيم: Auth، Authorization، Ownership، Visibility | **VM-05** |
| فهم الـ implementations الحالية | **VM-08** |

---

## [VM-01] الأوضاع الثلاثة للمشاهدة (Viewer Modes)

كل صفحة يتم تحديد وضعها بناءً على هوية الزائر مقارنةً بصاحب الصفحة.

### الوضع 1 — Owner View (وضع المالك)

**التعريف:** المستخدم المسجَّل الذي يُشاهد صفحته الخاصة.

**الشرط الإلزامي — يجب أن يتحقق الأثنان معاً:**
- JWT صالح ومُتحقَّق منه server-side
- `jwt.user_id` يُطابق `owner_id` للمورد (من DB، ليس من URL أو body)

**ما يتيحه:**
- رؤية جميع محتوى صفحته
- جميع أزرار التحرير / الحفظ / الإدارة
- عناصر الإعداد والتهيئة (مثل زر تحميل الصورة)
- بطاقة اكتمال الملف الشخصي (Profile Completion — موظف)
- لوحة إحصاءات خاصة بالمالك

**ما لا يتيحه:**
- لا يتيح الوصول إلى موارد مستخدمين آخرين
- لا يتيح صلاحيات الـ admin

---

### الوضع 2 — Registered User View (مستخدم مسجَّل)

**التعريف:** مستخدم لديه JWT صالح، لكنه يُشاهد صفحة شخص آخر.

**الشرط:**
- JWT صالح ومُتحقَّق منه server-side
- `jwt.user_id` ≠ `owner_id` للمورد

**ما يتيحه (يعتمد على نوع الحساب — انظر VM-02):**
- رؤية البيانات العامة للمورد
- أزرار التفاعل المتاحة لنوع حسابه (متابعة، إرسال رسالة، التقديم للوظيفة…)

**ما لا يتيحه:**
- لا تحرير لمحتوى الآخرين
- لا رؤية بيانات خاصة (تعتمد على ما يرسله الـ backend)

---

### الوضع 3 — Guest View (مستخدم غير مسجَّل)

**التعريف:** زائر بدون JWT صالح.

**الشرط:** الطلب يصل إلى الـ Backend بدون credentials صالحة — لا JWT مرفق، أو JWT منتهٍ، أو JWT غير صالح.

> **ملاحظة frontend:** يستطيع الـ frontend استخدام غياب token محلياً لتقديم تجربة أولية مناسبة — هذا مقبول كـ UX hint. لكنه لا يُثبت Guest status أمنياً، ولا يُغني عن التحقق server-side. المصدر الفعلي هو نتيجة Authentication server-side (VM-04).

**ما يتيحه:**
- رؤية المحتوى العام فقط (الذي يُرسله الـ backend لطلبات بلا JWT)
- رؤية أزرار تحثّ على التسجيل/الدخول

**ما لا يتيحه:**
- لا تفاعل مع أي مورد يتطلب حساباً
- لا رؤية بيانات خاصة

---

## [VM-02] التمييز حسب نوع الحساب داخل Registered User View

داخل الوضع 2 (Registered User)، يختلف ما هو متاح حسب `user_type` من الـ JWT:

| user_type | يمكنه |
|-----------|-------|
| `emp` (موظف) | التقديم للوظائف، متابعة الشركات، طلب التحقق، إرسال رسالة |
| `co` (شركة) | البحث عن المرشحين، حفظهم في بنك المواهب، إرسال موعد |
| `edu` (جهة تعليمية) | نشر الدورات، التحقق من شهادات الطلاب |

> **ملاحظة — Admin Authentication:** صلاحيات لوحة الإدارة محمية بـ `X-Admin-Token` عبر `check_admin()` في server.py (hmac.compare_digest) — وهو Authentication Contract مستقل عن JWT تماماً. `user_type=admin` في JWT لا يمنح صلاحيات admin وحده. انظر VM-06 + CLAUDE.md → Admin Authentication + SYSTEMS_INDEX §25.

**مصدر هذا التمييز:** `jwt.user_type` — لا يُقرأ من `localStorage` ولا من الـ URL، بل يُستخرج من الـ JWT server-side.

**قاعدة عامة:** لا يمنح نوع الحساب وحده صلاحيات خارج نطاق الـ API contract المُوثَّق.

---

## [VM-03] Preview / View As — مفهوم مستقبلي (غير مُنفَّذ حالياً)

> **تحذير:** هذا القسم يوثِّق مفهوماً معمارياً مستقبلياً **فقط**.
> لا توجد أي صفحة في المنصة تُطبِّق "View As" أو "Preview" حالياً كميزة كاملة.
> **ممنوع تنفيذ هذا القسم** حتى يُطلب صراحةً من صاحب المشروع.

### تعريف Preview / View As

آلية تسمح للمالك برؤية صفحته كما سيراها زائر آخر — دون تغيير هويته الحقيقية.

### القواعد الثابتة لأي تنفيذ مستقبلي

```
✓ Preview يُغيِّر منظور العرض فقط — لا يُغيِّر هوية المستخدم الحقيقية
✓ Preview لا يمنح صلاحيات إضافية لأي طرف
✓ Preview لا يتجاوز Backend Permissions بأي شكل
✓ JWT المستخدم في الطلبات يبقى JWT المالك — لا يتحول
✓ أي بيانات لا تُرسل للزائر العادي لا تُرسل في Preview Mode
✓ Preview يجب أن يكون صريحاً في الـ UI (شريط تحذيري واضح)
```

### ما يعنيه وجود مفهوم Preview في الـ implementations الحالية

`window._scViewerType` في Profile V2 يدعم القيم `'public-user'` و `'guest'` — هذه قيم منظور العرض (viewing perspective) التي تتحكم في ما يُعرَض.
هي **ليست** تنفيذاً لـ "View As" أو Preview الكاملة — بل هي تحديد لـ Viewer Mode من VM-01 الذي تتطابق معه جلسة المستخدم الحالية.

---

## [VM-04] كيف يُحدَّد Viewer Mode — مصادر الهوية

### Server-side (المصدر الفعلي)

```
1. يصل الطلب مع Authorization: Bearer {jwt}
2. server.py يُحلِّل الـ JWT → يستخرج user_id, user_type
3. يستعلم DB للحصول على owner_id للمورد المطلوب
4. يقارن: jwt.user_id == owner_id → owner | != → registered_user
5. غياب JWT أو JWT منتهٍ → guest
6. يرسل البيانات المناسبة لكل وضع
```

### Frontend (إشارة UX مساعدة — ليست مصدر أمان)

يستقبل الـ frontend من الـ server إشارات تساعد في تحديد ما يُعرَض:

| المصدر | القيم | الاستخدام |
|--------|-------|-----------|
| `window._scViewerType` (Profile V2) | `'owner'` \| `'public-user'` \| `'guest'` | يتحكم في عرض/إخفاء عناصر الـ owner |
| `companyState.permissions.isOwner` (Company Profile) | `true` \| `false` | يتحكم في عرض أزرار التحرير للشركة |
| `window._companyProfileIdFromRoute` | رقم (int) | Smart Router يحقن هوية الشركة |
| `window._scProfileIdFromRoute` | رقم (int) | Smart Router يحقن هوية الموظف |

**تذكير:** هذه الإشارات هي أدوات UX — لا تُغني عن التحقق server-side.

---

## [VM-05] الفصل الرسمي: أربعة مفاهيم مختلفة

> **هذا القسم إلزامي قراءته قبل تنفيذ أي زر مرتبط بصلاحية.**

### 1. Authentication (التحقق من الهوية)

**السؤال:** هل أنت من تدَّعي أنك؟

- **الآلية:** JWT موقَّع بـ `JWT_SECRET` في server.py
- **المصدر الوحيد:** `_jwt_decode()` في server.py — ليس `localStorage`
- **النتيجة:** `user_id` + `user_type` مُستخرجَين من الـ token
- **الحالتان:** مُتحقَّق منه ✓ | غير مُتحقَّق ✗ (لا توجد "نصف متحقق")

### 2. Authorization (التفويض)

**السؤال:** هل لديك الإذن للوصول إلى هذا المورد بهذه العملية؟

- **الآلية:** server-side check بعد التحقق من الـ JWT
- **يعتمد على:** `user_type` + `user_id` (مستخرجَان من JWT) + طبيعة المورد + نوع العملية
- **مثال:** موظف لا يستطيع نشر وظيفة؛ شركة لا تستطيع التقديم للوظائف
- **Resource Identifiers:** مُعرِّفات الموارد (مثل `job_id`، `profile_id`، `company_id`) تأتي من الـ URL/query/body وتُستخدَم كمدخل لتحديد المورد الذي سيُجرى عليه الفحص. الـ Backend يُحمِّل الحقيقة من DB ثم يُجري Authorization/Ownership check باستخدام الهوية الموثَّقة من الـ JWT.
- **ممنوع قبوله من العميل كمصدر هوية أو صلاحية:** `user_id`، `owner_id`، `user_type`، أو أي claim أمني — هذه تُستخرج دائماً من الـ JWT server-side.
- **لا يعتمد أبداً على:** `localStorage`، DOM state، أي frontend variable

### 3. Ownership (الملكية)

**السؤال:** هل المورد يخصَّك أنت؟

- **الآلية:** مقارنة `jwt.user_id` بـ `owner_id` في DB
- **يختلف عن Authorization:** يمكن تفويض شخص بالوصول بدون أن يكون مالكاً (مستقبلاً)
- **التحقق الإلزامي:** DB query — ليس `?owner_id=` من الـ URL

### 4. Visibility (الرؤية)

**السؤال:** ماذا يُعرَض لهذا المستخدم في الـ UI؟

- **الآلية:** frontend logic بناءً على Viewer Mode + Account Type
- **مصدرها:** إشارات من الـ server (VM-04) + Viewer Mode (VM-01)
- **دورها:** UX فقط — تحسين التجربة بعرض ما هو مناسب لكل مستخدم
- **لا تعوِّض عن:** Authentication أو Authorization — مجرد طبقة عرض

---

## [VM-06] Backend هو المرجع النهائي للصلاحيات

### المبدأ الأساسي

```
Backend Permissions > Frontend Visibility
```

كل عملية user-facing تُغيِّر بيانات تتطلب authentication وauthorization server-side حسب الـ Authentication Contract المُوثَّق للـ endpoint. JWT هو المصدر الرسمي لهوية المستخدم العادي:

1. JWT صالح مرفق في `Authorization: Bearer`
2. استخراج `user_id` و `user_type` من الـ JWT server-side (لا من الـ body أو header مخصص)
3. تحقق server-side من صلاحية المستخدم للعملية المطلوبة
4. تحقق من الـ ownership إذا كان المورد شخصياً

**Authentication Contracts الأخرى الموثَّقة في هذا المشروع:**

| النوع | الآلية | المرجع |
|-------|--------|--------|
| User-facing endpoints | `Authorization: Bearer {jwt}` | SYSTEMS_INDEX §2 |
| Admin endpoints | `X-Admin-Token` → `check_admin()` → `hmac.compare_digest` | CLAUDE.md → Admin Authentication · SYSTEMS_INDEX §25 |
| Internal/Scheduler endpoints | `X-Scheduler-Secret` → `hmac.compare_digest` | SYSTEMS_INDEX §37 |

لكل endpoint نوعه الخاص من الـ authentication — لا يجوز اعتبار Admin أو Internal endpoints استثناءات غير محمية.

### قاعدة إرسال البيانات

```
البيانات الخاصة أو الحساسة التي لا يملك المشاهد صلاحية رؤيتها:
يجب ألا يرسلها الـ Backend أصلاً — هذا إلزامي، ليس تفضيلاً.
إخفاؤها client-side بعد إرسالها ليس حلاً أمنياً بأي شكل.
Frontend hiding مقبول فقط لعناصر UX غير الحساسة،
بعد أن تكون البيانات الحساسة محمية من الإرسال في الـ Backend أصلاً.
```

**تطبيق عملي:**
- بيانات الملف الشخصي الخاصة بالمالك (مثل إعدادات الـ privacy) لا تُرسَل في طلبات الزوار
- ملاحظات Pipeline الداخلية للشركة لا تُرسَل لغير موظفي الشركة
- القاعدة: تحقق من الصلاحية server-side أولاً → أرسل البيانات فقط عند الإذن الصريح

### استجابات الـ backend لمحاولات الوصول غير المُصرَّح بها

| الحالة | كود الاستجابة |
|--------|--------------|
| لا يوجد JWT أو JWT منتهٍ | `401 Unauthorized` |
| JWT صالح لكن بدون صلاحية (نوع حساب خاطئ، ليس المالك) | `403 Forbidden` |
| مورد غير موجود | `404 Not Found` |
| إجراء غير مسموح على مورد موجود | `403 Forbidden` |

---

## [VM-07] Frontend Visibility = UX فقط

> **هذه القاعدة من أهم قواعد هذا النظام.**

### ما تعنيه

```
إخفاء عنصر في الـ UI ≠ منع الوصول إليه.
```

**CSS، JS، DOM، localStorage — ليست مصادر أمان.**

### أمثلة على ما يعنيه ذلك

```
❌ إخفاء زر حذف بـ display:none يمنع الحذف   → خاطئ
❌ إزالة زر التحرير من DOM تمنع التحرير       → خاطئ
❌ localStorage.role === 'owner' يُثبت الملكية  → خاطئ
❌ window._scViewerType === 'owner' يُخوِّل API → خاطئ
```

```
✓ إخفاء زر حذف = تجربة مستخدم أفضل
✓ منع الحذف فعلياً = server-side check في handler الـ DELETE
✓ إظهار زر التحرير للمالك فقط = UX signal
✓ السماح بالتحرير فعلياً = server compares jwt.user_id with owner_id
```

### القاعدة الذهبية

```
إذا كان الإجراء مهماً بما يكفي لإخفائه → فهو مهم بما يكفي لتأمينه في الـ backend.
```

---

## [VM-08] التوافق مع الـ Implementations الحالية

هذا النظام يوثِّق الـ contract المعماري — لا يستبدل الـ implementations الموجودة.
الـ implementations التالية متوافقة مع هذا النظام ولا تتطلب تعديلاً:

### Profile V2 — `window._scViewerType`

```js
window._scViewerType = 'owner'       // VM-01: Owner View
window._scViewerType = 'public-user' // VM-01: Registered User View
window._scViewerType = 'guest'       // VM-01: Guest View
```

- مُحدَّد بواسطة `renderProfile` في `profile-v2.render.js` بعد استلام البيانات من الـ server
- يُستخدَم لإظهار/إخفاء عناصر الـ UI — ليس للتحقق من الصلاحيات
- متوافق مع VM-04 (Frontend signal)

### Company Profile — `companyState.permissions`

```js
companyState.permissions.isOwner = true | false
```

- مُحدَّد بواسطة `company.permissions.js` بعد مقارنة `session.id` مع `profile.user_id`
- يُستخدَم لإظهار/إخفاء أزرار التحرير — ليس للتحقق server-side
- متوافق مع VM-04 (Frontend signal)

### قاعدة التوافق الدائمة

```
أي implementation يُضاف مستقبلاً يجب أن:
✓ يُطابق أحد الأوضاع الثلاثة في VM-01
✓ يستخدم Authentication Contract المُوثَّق للتحقق server-side (VM-06)
✓ يعتبر frontend signal مجرد UX (VM-07)
✓ لا ينشئ وضعاً رابعاً دون تحديث هذا الملف
```

---

## [VM-09] Forbidden Patterns

```
❌ تحديد Viewer Mode من URL أو query param فقط
❌ استخدام localStorage كمصدر لصلاحية أمنية
❌ إخفاء element في CSS كبديل عن تأمين الـ endpoint
❌ اعتبار window._scViewerType أو companyState.permissions.isOwner
   مُخوِّلاً لعمليات الـ API
❌ إرسال بيانات خاصة من backend ثم إخفاؤها client-side
❌ وضع user_type أو owner_id في request body لتحديد الصلاحية
❌ استخدام X-User-Id header بدلاً من JWT
❌ إنشاء وضع رابع خارج [Owner, Registered, Guest] بدون PR منفصل
❌ تنفيذ Preview / View As بدون طلب صريح من صاحب المشروع
❌ التمييز بين أنواع الحسابات في الـ frontend فقط
   دون تطبيق نفس التمييز في الـ backend
```

---

## [VM-10] Global Session UI Visibility System

> **الفرق الجوهري بين VM-10 و VM-01–VM-09:**
> VM-01–VM-09 تُعالج صلاحيات الموارد (Resource Permissions) — من يملك/يعدّل/يرى مورداً محدداً.
> VM-10 يُعالج حالة جلسة المستخدم عالمياً — هل هو مسجّل دخوله أم لا — وينعكس على الهيدر والقوائم فقط.
> الفصل بينهما إلزامي. لا يجوز لـ VM-10 قراءة `viewer_type` أو `isOwner`.

### [VM-10A] Session States (حالات الجلسة)

`TwAuthSync.getSessionSnapshot()` يُعيد كائناً بـ 5 حقول:

| الحالة | الوصف | `isAuthenticated` |
|--------|-------|-------------------|
| `guest` | لا يوجد JWT ولا `tw_user` في localStorage | `false` |
| `authenticated` | JWT صالح + user object + IDs متطابقة | `true` |
| `expired` | JWT منتهي الصلاحية (`claims.exp <= now`) | `false` |
| `invalid` | JWT موجود لكن malformed أو يفتقد `user_id`/`user_type`/`exp` | `false` |
| `stale` | JWT صالح لكن `tw_user` غائب أو ID/type يختلف؛ أو `tw_user` موجود بلا JWT | `false` |

**قواعد `_resolveSession()` بالترتيب (VM-10A — 11 خطوة):**
1. لا `tw_jwt` ولا `tw_user` → `guest` (reason: `no_jwt`)
2. `tw_user` موجود لكن لا `tw_jwt` → `stale` (reason: `no_jwt_with_user`)
3. JWT موجود لكن غير قابل للـ parse → `invalid` (reason: `malformed_jwt`)
4. `claims.user_id` غائب أو null → `invalid` (reason: `missing_user_id`)
5. `claims.user_type` غائب أو null → `invalid` (reason: `missing_user_type`)
6. `typeof claims.exp !== 'number'` أو `!isFinite(claims.exp)` → `invalid` (reason: `missing_exp`)
7. `claims.exp <= now` → `expired` (reason: `jwt_expired`) — `<=` يلتقط القيمة المساوية لـ now بالضبط
8. `tw_user` غائب أو بلا `.id` → `stale` (reason: `no_user_object`)
9. `String(claims.user_id) !== String(user.id)` → `stale` (reason: `user_id_mismatch`)
10. `claims.user_type !== user.user_type` → `stale` (reason: `user_type_mismatch`)
11. كل الشروط تجتازت → `authenticated` (reason: `ok`)

**Session Fingerprint:** `_check()` تتابع `_prevJwt` + `_prevUserStr`. أي تغيير في `tw_user` (حتى مع نفس JWT) يُطلق callbacks — يحمي من account switch داخل نفس التاب.

**Expiry Timer:** `_scheduleExpiryTimer()` تستخدم `setTimeout` مرة واحدة، مُحدودة بـ `_MAX_TIMEOUT_MS = 0x7FFFFFFF`. عند تجديد JWT أثناء النوم تُعيد الجدولة بدلاً من الانتهاء.

### [VM-10B] Global Header Menu Policy

مصدر الحقيقة: `_TW_HEADER_MENU_POLICY` في `tw_shared.js`

كل بند له `show: 'auth' | 'guest' | 'all'` و`accountTypes?: string[]` اختياري:

| البند | show | accountTypes | يظهر لـ |
|-------|------|-------------|---------|
| الإعدادات | `auth` | — | جميع مسجّلي الدخول |
| بحث عن موظفين | `auth` | `['co']` | شركات فقط |
| تواصل معنا | `all` | — | الجميع (disabled) |
| الإبلاغ عن مشكلة | `all` | — | الجميع (disabled) |
| اقترح ميزة | `all` | — | الجميع (disabled) |
| تسجيل الخروج | `auth` | — | جميع مسجّلي الدخول |
| تسجيل الدخول | `guest` | — | زوار غير مسجّلين |
| إنشاء حساب | `guest` | — | زوار غير مسجّلين |

`_twMenuItemsForSnapshot(snapshot)` تُطبّق فلتر `show` ثم `accountTypes` (إذا محدد).

**ممنوع:** إضافة بند بدون تعريف `show` صريح في `_TW_HEADER_MENU_POLICY`.

### [VM-10C] Idempotent Header Renderer

`initGlobalHeaderMenu(btnId, ddId, dynId)` في `tw_shared.js`:
- Idempotent — استدعاء ثانٍ بنفس `btnId` يُتجاهَل صامتاً
- يُسجِّل listener واحداً على TwAuthSync للصفحة كلها (عبر `_ghListenerRegistered`)
- يُعيد عرض القائمة تلقائياً عند كل تغيير في الجلسة
- يستدعي `_twApplyDeclarativeVisibility()` مباشرةً في أول استدعاء

### [VM-10D] Declarative Session Visibility

`data-tw-session="authenticated|guest|all"` على أي element في HTML:
- `authenticated` + `hidden` → مخفي بالافتراضي، يظهر فقط لمسجّلي الدخول
- `guest` → يظهر فقط للزوار
- `all` → يظهر للجميع دائماً
- خاصية `data-tw-account-types="co,emp"` تضيّق الظهور لأنواع حسابات محددة

`_twApplyDeclarativeVisibility()` هي الدالة الوحيدة المسؤولة عن معالجة هذه الخاصية.

**استخدام على صفحات عامة (بدون Auth Guard):**
```html
<a href="/messages" data-tw-session="authenticated" hidden>...</a>
```

### [VM-10E] Preview Boundary

Preview modes (VM-03: `preview-public-user`, `preview-guest`) لا تُغيّر حالة الجلسة العامة.
- `_twApplyDeclarativeVisibility()` تعتمد على `TwAuthSync.getSessionSnapshot()` فقط
- لا تقرأ body classes ولا window._scViewerType
- Preview يُغيّر Resource Viewer Mode (VM-01) — لا يُغيّر Global Session State (VM-10A)

**النتيجة:** زر تسجيل الخروج يبقى ظاهراً أثناء المعاينة لأن المالك ما زال مسجّل الدخول.

### [VM-10F] Security Boundary

```
VM-10 = UX فقط — ليس ضماناً أمنياً.
إخفاء زر الإعدادات للزوار لا يمنعهم من الوصول لـ /settings.
كل endpoint يتحقق من JWT server-side مستقلاً.
```

### [VM-10G] Session Storage Cleanup Contract

`invalidateSession()` تحذف مفاتيح محددة فقط (allowlist) — ليس كل مفاتيح `tw_`:

```javascript
var _SESSION_KEYS = ['tw_jwt', 'tw_user'];
```

**ممنوع:** `startsWith('tw_')` لحذف مفاتيح الجلسة — يمكن أن يحذف تفضيلات المستخدم (`tw_cover_edu_*` إلخ).

### [VM-10H] HTTP 401 vs 403 Contract

في `loadGlobalBadges()`:
- `401` → token منتهي أو غير صالح → `TwAuthSync.invalidateSession('api_401')` **فقط**
- `403` → مصادق لكن ممنوع من هذا المورد → الجلسة محفوظة، لا invalidate

**ممنوع:** `r.status === 401 || r.status === 403` — الجمع يُلغي جلسات صالحة عند خطأ Authorization.

### [VM-10I] Badge WebSocket Generation Lifecycle

الـ WS مُصمَّم لمنع إعادة الاتصال الخاطئة بعد logout/login:

- `_generation` يُزاد عند كل `_twBadgeWsStop()` — يُلغي أي `onclose` معلق من الجيل السابق
- `_activeUserId` يُتابع userId الحالي — account switch يُطلق stop+start دورة كاملة
- `_initBadgeWS(gen)` تتحقق من `gen !== _generation` في البداية وفي `onclose`
- **ممنوع:** استخدام `_stopped` boolean — يمنع إعادة الاتصال بعد logout+login

### [VM-10J] Global Site Header — Auto-Detection Marker

**التعريف:** أي صفحة تحتوي على `.sc-menu-dropdown` تُعتبر تلقائياً ضمن نطاق VM-10.

هذا هو المؤشر الرسمي للكشف التلقائي عن الصفحات المعتمِدة للـ Global Site Header:

```
المؤشر:  class="sc-menu-dropdown"
الوجود:  أي صفحة HTML تحمل هذه الـ class
الالتزام: يجب أن تحمل auth-sync.js وأن تستدعي initGlobalHeaderMenu
```

**الصفحات المعتمِدة (جميعها تحمل `.sc-menu-dropdown`):**

| الصفحة | حالة الاعتماد | الـ IDs |
|--------|--------------|---------|
| `profile-showcase.html` | ✅ مكتمل | `scMenuBtn` / `scMenuDropdown` / `scMenuDynamic` |
| `company-profile.html` | ✅ مكتمل | `coMenuBtn` / `coMenuDropdown` / `coMenuDynamic` |
| `notifications.html` | ✅ مكتمل | `ntMenuBtn` / `ntMenuDropdown` / `ntMenuDynamic` |
| `messages.html` | ✅ مكتمل | `scMenuBtn` / `scMenuDropdown` |
| `home-v2.html` | ✅ مكتمل | `hwMenuBtn` / `hwMenuDropdown` |

**قاعدة الاعتماد (إلزامية لأي صفحة جديدة تحمل `.sc-menu-dropdown`):**
1. تحميل `/tw_shared.js` قبل ملفات الصفحة
2. تحميل `/static/shared/auth-sync.js` بعد `tw_shared.js`
3. استدعاء `initGlobalHeaderMenu(btnId, ddId)` أو `initGlobalHeaderMenu(btnId, ddId, dynId)` عند التهيئة
4. إضافة `data-tw-session="authenticated" hidden` على أيقونات الهيدر الخاصة بالمسجّلين
5. إفراغ محتوى الـ dropdown الثابت — `initGlobalHeaderMenu` يملأه ديناميكياً

**ممنوع:**
```
❌ صفحة تحمل .sc-menu-dropdown بدون auth-sync.js
❌ منطق toggle محلي للـ dropdown موازٍ لـ initGlobalHeaderMenu
❌ startsWith('tw_') في أي logout handler على صفحة VM-10
❌ static Settings/Logout buttons داخل .sc-menu-dropdown
```

### Forbidden (VM-10)

```
❌ إضافة بند لـ _TW_HEADER_MENU_POLICY بدون show صريح
❌ قراءة viewer_type أو isOwner في _twApplyDeclarativeVisibility
❌ اعتبار data-tw-session حماية أمنية
❌ إضافة منطق session check مكرر داخل صفحة جديدة بدلاً من initGlobalHeaderMenu
❌ Preview body class تُؤثر على Global Session menu
❌ إنشاء نظام visibility موازٍ خارج tw_shared.js/_twApplyDeclarativeVisibility
❌ startsWith('tw_') لحذف مفاتيح الجلسة — استخدم _SESSION_KEYS allowlist
❌ معالجة 403 كـ 401 (invalidateSession على 403)
❌ _stopped boolean في WS lifecycle — استخدم _generation counter
❌ تجاوز مطابقة claims.user_id مع tw_user.id في Session Resolver
```

---

*آخر تحديث: 2026-07-18 — V1: Viewer Modes & Permissions System foundation.
يُغطي: VM-00 (Routing Protocol) → VM-09 (Forbidden Patterns).
موثَّق في: docs/DESIGN_SYSTEM.md + docs/SYSTEMS_INDEX.md §40.
rev.2: تصحيح VM-01 (Guest بدون localStorage)، VM-02 (admin auth contract مستقل)، VM-05 (Resource Identifiers vs identity claims)، VM-06 (JWT ليس مطلقاً + قاعدة البيانات الحساسة إلزامية)، VM-08 (Authentication Contract بدلاً من JWT).
rev.3 (2026-08-03): إضافة VM-10 — Global Session UI Visibility System (PR fix/global-ui-visibility-system).
rev.4 (2026-08-04): إضافة VM-10J — Global Site Header Auto-Detection Marker؛ اعتماد home-v2.html (5 صفحات مكتملة).*
