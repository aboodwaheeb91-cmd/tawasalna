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

**الشرط:** لا يوجد `localStorage.tw_jwt`، أو JWT منتهي الصلاحية.

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
| `admin` | صلاحيات الإدارة الكاملة عبر endpoints محمية بـ `X-Admin-Token` |

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
- **يعتمد على:** `user_type` + `user_id` + طبيعة المورد + نوع العملية
- **مثال:** موظف لا يستطيع نشر وظيفة؛ شركة لا تستطيع التقديم للوظائف
- **لا يعتمد أبداً على:** URL، query param، request body، localStorage

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

كل عملية تُغيِّر بيانات (POST / PUT / PATCH / DELETE) تتطلب:

1. JWT صالح مرفق في `Authorization: Bearer`
2. استخراج `user_id` و `user_type` من الـ JWT (لا من الـ body أو الـ header المخصص)
3. تحقق server-side من صلاحية المستخدم للعملية المطلوبة
4. تحقق من الـ ownership إذا كان المورد شخصياً

### قاعدة إرسال البيانات

```
البيانات التي لا يحق لمستخدم رؤيتها → يُفضَّل عدم إرسالها من الـ backend أصلاً.
إخفاؤها client-side فقط هو آخر خيار — ليس الحل الآمن.
```

**تطبيق عملي:**
- بيانات الملف الشخصي الخاصة بالمالك (مثل إعدادات الـ privacy) لا تُرسَل في طلبات الزوار
- ملاحظات Pipeline الداخلية للشركة لا تُرسَل لغير موظفي الشركة
- البيانات المحمية server-side: تحقق أولاً → إرسال فقط عند الإذن

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
✓ يستخدم JWT للتحقق server-side (VM-06)
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

*آخر تحديث: 2026-07-18 — V1: Viewer Modes & Permissions System foundation.
يُغطي: VM-00 (Routing Protocol) → VM-09 (Forbidden Patterns).
موثَّق في: docs/DESIGN_SYSTEM.md + docs/SYSTEMS_INDEX.md §40.*
