# [DS-BTN] Button System V1 — Tawasolna

> **نظام الأزرار الرسمي لمنصة تواصلنا.**
> هذا الملف هو مرجع الـ contract المعماري للأزرار — web أولاً، مع مراعاة Flutter مستقبلاً (F1).
> المحتوى: سلوك + هوية بصرية + دورة حياة + قواعد لا استثناء منها.
> الأمثلة التقنية للتوضيح فقط — هذا ليس CSS Manual ولا JavaScript Manual.

---

## [BTN-00] Button System Routing Contract

**الخطوة الأولى دائماً:** حدِّد نوع المهمة ثم اقرأ الأقسام المرتبطة فقط.

| المهمة | اقرأ |
|--------|------|
| زر حفظ / إرسال / تأكيد | **BTN-09** + BTN-07 عند الحاجة |
| زر toggle (حفظ، متابعة، تعليق) | **BTN-10** + BTN-07 عند الحاجة |
| زر أيقونة (header، toolbar) | **BTN-06** + BTN-07 |
| زر navigation / tab / رابط | **BTN-12** + BTN-11 |
| إجراء خطير / حذف | **BTN-13** + BTN-11 |
| زر جديد معروف النوع | **BTN-02 → BTN-03 → BTN-04 → BTN-11** |
| نوع زر غير معروف أو لا يطابق | **BTN-00 → BTN-01 → STOP** |

> **لا تقرأ BUTTONS.md كاملاً تلقائياً.** اقرأ فقط الأقسام التي تخص مهمتك.
> هدف هذا النظام: تقليل Context/Token وتركيز القراءة على ما يخص المهمة فعلاً.

---

## [BTN-01] No Matching System Contract — قاعدة STOP

> **هذه القاعدة الأولى والحاكمة. تُطبَّق قبل أي تنفيذ.**

**إذا طُلب إنشاء أو تعديل زر ولم يوجد نوع أو قاعدة أو Lifecycle معتمدة تطابقه في هذا الملف:**

### STOP — ممنوع التنفيذ

الممنوعات عند عدم وجود نظام مطابق:

```
❌ اختيار أقرب نوع زر بالاجتهاد
❌ اختيار Primary أو Secondary أو Danger باجتهاد شخصي
❌ نسخ نظام زر مشابه من صفحة أخرى
❌ اختراع Visual Style جديد
❌ اختراع Lifecycle جديد
❌ تنفيذ Custom Button من تلقاء نفسك (AI أو مطور)
❌ تنفيذ الزر أولاً ثم توثيقه لاحقاً
❌ اعتبار غياب القاعدة تصريحاً بالاختيار الشخصي
```

### الإجراء المطلوب: إيقاف التنفيذ والرجوع لصاحب المشروع

الرسالة الإلزامية:

> "لا يوجد حالياً نظام معتمد لهذا النوع من الأزرار داخل Tawasolna Button System.
> يجب تحديد نظامه أو إضافته إلى Button System قبل التنفيذ."

ثم انتظار قرار صاحب المشروع.

**عدم وجود نظام لا يعني السماح بالاجتهاد.**

---

## [BTN-02] Base Button Visual Contract

### الهوية البصرية الأساسية

- **الشكل:** مستطيل — ليس Pill، ليس Capsule.
- **الارتفاع:** منخفض ومشدود بصرياً (slim).
- **الخلفية:** شفافة افتراضياً — **لا Solid Fill كتصميم افتراضي**.
- **الحدود:** Border مضيء Glow خفيف — من نفس الـ Semantic Color Family للزر.
- **اللون:** Border + Text + Icon + Glow كلها من نفس Semantic Color Family.
- **Hover:** يقوي الـ Glow قليلاً — يُسمح بـ Tint شفاف خفيف جداً.
- **Pressed:** Press Feedback بسيط جداً — بدون Layout Shift.
- **الأنيميشن:** قصيرة وهادئة — لا Glow ثقيل، لا Animation مستمرة.

### الخصائص التقنية الإلزامية

| الخاصية | المطلوب | السبب |
|---------|---------|--------|
| `cursor` | `pointer` | لا يُترك للمتصفح |
| `user-select` | `none` → BTN-08 | لا يُحدَّد نص الزر |
| `border` | explicit | يمنع تضارب الـ reset |
| `border-radius` | صغير وموحَّد | شكل مستطيل slim |
| `font-family` | `inherit` | يحافظ على Cairo + RTL |
| `transition` | محددة ومنطقية | لا transitions غير ضرورية |

### الممنوعات البصرية

```
❌ Solid Fill كتصميم افتراضي
❌ Pill أو Capsule كشكل افتراضي
❌ Glow ثقيل أو متحرك باستمرار
❌ outline: none بدون :focus-visible بديل
❌ pointer-events: none إلا في حالة disabled الموثَّقة
❌ تعديل z-index داخل الزر نفسه
```

---

## [BTN-03] Semantic Button Types

أربعة أنواع دلالية. الـ Semantic Color يتحكم في:
**Border + Text + Icon + Glow — وليس Solid Background افتراضياً.**

| النوع | المرجع الحالي (existing token) | الاستخدام |
|-------|-------------------------------|-----------|
| **Primary** | `#00c896` (`--ac`) | الإجراء الأبرز في Action Group أو Modal |
| **Secondary** | محايد / subdued | إلغاء، رجوع، إجراءات مساندة |
| **Danger** | `#ef4444` | إجراءات مدمِّرة أو سلبية حقيقية فقط |
| **Success** | `#22c55e` | حالة تأكيد نجاح — لا تظهر ابتداءً |

> **ملاحظة:** الألوان المذكورة هي existing tokens مرجعية — ليست final Design Tokens.
> المصدر النهائي مستقبلاً سيكون Shared Design Tokens عند بناء `tw-ui-tokens.css`.

### قواعد الاستخدام

1. **Primary مفضَّل واحداً** داخل نفس Action Group أو Modal — ليس منعاً مطلقاً على مستوى الصفحة إذا كانت هناك سياقات مستقلة.
2. **Danger** للإجراءات المدمِّرة أو السلبية الحقيقية فقط — راجع [BTN-13].
3. **Success** لا يظهر كحالة ابتدائية — يظهر فقط بعد Backend Confirmation.
4. **لا تستخدم Danger باللون الأخضر، ولا Primary باللون الأحمر.**

---

## [BTN-04] Button Size & Layout

### المبدأ الأساسي

- الزر **Slim بصرياً** — الارتفاع يبقى منخفضاً.
- **العرض** يتحدد حسب المحتوى أو الـ Layout — ليس Full Width افتراضياً.
- **Button Group أو Container** مسؤول عن width وspacing وposition.
- **Base Button لا يحمل margins خارجية** — الـ spacing ينتمي للـ container.

### قيم موجودة (Existing Constraints — ليست Universal Tokens)

| الحجم | height | padding أفقي | font-size | تنطبق على |
|-------|--------|--------------|-----------|-----------|
| SM | 27px | 18px | 11px | Profile V2 action buttons — **مجمَّدة في CLAUDE.md** |
| MD | 36px | 20px | 13px | مودالات، forms |
| LG | 44px | 28px | 15px | CTAs رئيسية |

> هذه قيم قائمة في صفحات محددة — **ليست Design Tokens موحَّدة معتمدة**.
> لا تطبِّقها على صفحات جديدة بدون قرار موثَّق.
> القيم SM مجمَّدة في `.sc-btn` — راجع CLAUDE.md قبل أي تعديل.

### Layout داخل الزر

- `display: inline-flex`
- `align-items: center`
- `justify-content: center`
- `gap`: المسافة بين أيقونة ونص — تُحدَّد حسب السياق
- `flex-shrink: 0` — الزر لا يتقلص داخل flex container

### على الموبايل

يبقى الشكل المرئي Slim مع الحفاظ على Touch Target مريح حوله (لا تقلص الـ target).

---

## [BTN-05] Button Groups

### أزرار عمودية (فوق بعضها)

```
✓ نفس العرض تماماً
✓ نفس الارتفاع
✓ نفس الـ border-radius
✓ نفس المحاذاة
✓ نفس المسافات بين الأزرار
✓ الحواف تبدأ وتنتهي على نفس الخط العمودي
❌ ممنوع: عرض مختلف يدوياً لكل زر
```

### أزرار أفقية (بجانب بعضها)

- نفس الارتفاع.
- محاذاة رأسية موحَّدة.

### Container

- `display: flex` + `gap` على الـ container.
- لا `margin` على الأزرار أنفسها للـ spacing.

### ترتيب DOM في RTL

في RTL flex-row: أول عنصر في DOM يظهر على اليمين بصرياً.
الزر الأبرز (Primary أو Danger) يُوضع أولاً في DOM — يظهر على اليمين.
الزر الثانوي (Secondary، إلغاء) يأتي ثانياً — يظهر على اليسار.

---

## [BTN-06] Icon Buttons

### أزرار الأيقونة في Header وToolbars

**الافتراضي: Borderless.**

```
✓ لا Permanent Border افتراضياً
✓ لا Solid Background افتراضياً
✓ الأيقونة تحمل Glow خفيفاً عند الحاجة
✓ Hover/Touch: Halo أو Tint شفاف خفيف (اختياري)
✓ Touch Area ثابت ومريح للموبايل
✓ No Text Selection → BTN-08
✓ aria-label إلزامي عند غياب النص
```

أمثلة: Back، Close، Settings، More، Search، Notifications، Share.

### مصدر الأيقونات

استخدم نظام الأيقونات الرسمي عند وجوده.
إذا لم يوجد نظام: SVG inline مقبول.
ممنوع: font-icon، emoji كأيقونة احترافية.

### أزرار بأيقونة + نص

الأيقونة تأتي قبل النص في DOM (تظهر يميناً في RTL).

---

## [BTN-07] Button Interaction States

### الحالات الممكنة

| الحالة | المطلوب |
|--------|---------|
| **Default** | الـ base visual من BTN-02 |
| **Hover** | Glow يقوى قليلاً — Tint شفاف خفيف اختياري — لا تغيير layout |
| **Pressed** | Press Feedback بسيط جداً — لا Layout Shift |
| **Focus** | `focus-visible` واضح من نفس Semantic Color Family — إلزامي للـ accessibility |
| **Loading** | راجع BTN-09 أو BTN-10 |
| **Success** | راجع BTN-09 أو BTN-10 |
| **Error** | عودة لحالة قابلة للاستخدام + إظهار الخطأ |
| **Disabled** | Visual State فقط — `opacity ~0.45`، `cursor: not-allowed`، `pointer-events: none` |
| **Selected** | Glow أقوى بدرجة بسيطة أو Accent Indicator |

كل زر يستخدم **فقط الحالات التي يحتاجها** — لا تضيف حالات غير مبررة.

### ملاحظات مهمة

- **Disabled ليس بديلاً عن Backend Permission** — التحكم الأمني يبقى server-side دائماً.
- **لا تخترع States جديدة** من داخل صفحة — الإضافة تكون على مستوى النظام فقط.
- **Focus يجب أن يكون مرئياً** — لا `:focus { outline: none }` بدون `:focus-visible` بديل.

### الممنوعات

```
❌ :focus { outline: none } بدون :focus-visible بديل
❌ حالة hover تغير layout (width, height, padding)
❌ حالة disabled تغير اللون إلى أحمر
```

---

## [BTN-08] No Text Selection Contract

```
user-select: none
-webkit-user-select: none
-webkit-touch-callout: none
```

تنطبق على كل زر رسمي وعلى Custom Button — ما لم يطلب صاحب المشروع عكس ذلك صراحةً.
لا تطبِّقها على النص المجاور للزر — فقط على الزر نفسه.

---

## [BTN-09] Action Save Button Lifecycle

> زر "حفظ" أو "إرسال" يُرسل بيانات إلى backend.

### دورة الحياة الرسمية

```
حفظ  (Default — هادئ)
  ↓ [user clicks]
جارٍ الحفظ…  (Loading — يمنع duplicate click)
  ↓ [Backend Success]
✓ تم الحفظ  (Success State — Glow Pulse واحد قصير)
  ↓ [بعد مدة قصيرة أو عند بدء تعديل جديد]
حفظ  (Default — هادئ مجدداً)
```

**عند تعديل البيانات من جديد:** يصبح زر الحفظ Active/Ready.

**State Flow:** Default → Loading → Success → Default

### قواعد إلزامية

1. **لا Success قبل Backend Confirmation** — النجاح يأتي فقط بعد response إيجابي من الـ server.
2. **Loading يمنع Duplicate Click** — الزر لا يقبل نقرة ثانية أثناء الـ fetch.
3. **على Success:** Success State داخل الزر (✓ تم الحفظ) + Glow Pulse واحد قصير.
4. **على Error:** الزر يعود لحالة Default قابلة للاستخدام + الخطأ يظهر عبر Error System.
5. **الزر لا يختفي** بعد النجاح.
6. **عرض الزر لا يتغير** بين الحالات — لا Layout Shift.

### قواعد السياق

- **إغلاق Modal بعد النجاح:** يعتمد على سياق الـ flow — ليس قاعدة عامة إلزامية.
- **Toast بعد النجاح:** اختياري حسب السياق — Success State داخل الزر هو الإلزامي.
- **لا تستخدم `setTimeout` لمحاكاة Loading** — Loading حقيقي مرتبط بـ fetch promise فقط.

---

## [BTN-10] Toggle Save Button Lifecycle

> زر يحمل حالة ثنائية: نشط / غير نشط (حفظ، متابعة، تقدير...).

### دورة الحياة الرسمية (Backend-Confirmed — الافتراضي)

```
حفظ في بنك المواهب  (Default — غير نشط)
  ↓ [user clicks]
جارٍ الحفظ…  (Loading)
  ↓ [Backend Success]
✓ محفوظ في بنك المواهب  (Active/Selected)

ثم عند الضغط مجدداً:

✓ محفوظ في بنك المواهب  (Active)
  ↓ [user clicks]
جارٍ الإزالة…  (Loading)
  ↓ [Backend Success]
حفظ في بنك المواهب  (Default — غير نشط)
```

### قواعد إلزامية

1. **لا تظهر Saved State قبل Backend Confirmation** — هذا هو النظام العام لتواصلنا.
2. **لا Optimistic UI كقاعدة عامة** — لا تعكس الحالة بصرياً ثم تعمل rollback.
3. **Desired State Queue ليس إلزامياً** على كل Toggle Button — راجع الـ carve-out أدناه.
4. **يمنع Duplicate/Race** حسب Lifecycle الخاص بالزر والنظام المرتبط به.
5. **حالة Selected** تحصل على Glow أقوى أو Accent Indicator بسيط.

### Carve-out: الأنظمة ذات Contract خاص

Post Save وPost Appreciation في CLAUDE.md لهما contract خاص (Optimistic UI + Desired State Queue).
هذا الـ contract يخص **هذين النظامين تحديداً** — لا يُعمَّم على كل أزرار Toggle في المنصة.

---

## [BTN-11] Button Lifecycle Contract

> فحص شامل لأي زر جديد أو مُعدَّل.

### الأسئلة الإلزامية

**الوجود:**
- لماذا هذا الزر موجود؟
- ما نوعه؟ (Action / Toggle / Navigation / Dangerous)

**السلوك عند الضغط:**
- ماذا يحدث؟ (Operation / Modal / Drawer / Overlay / Navigation / Toggle / State Change)
- هل هو Operation يستدعي backend؟

**التنقل:**
- ما هو Canonical Route بعد الإجراء؟
- أين يعود المستخدم عند الضغط على Back؟
- هل Back يغلق UI Layer أولاً قبل التنقل؟

**الحالات الطارئة:**
- ماذا يحدث عند الضغط السريع المتكرر؟
- ماذا يحدث أثناء API Loading؟
- ماذا يحدث عند Success؟
- ماذا يحدث عند Failure؟
- ماذا يحدث بعد Page Refresh؟

**الصلاحيات والبيانات:**
- هل Direct/Deep Link يعمل؟
- هل Permissions محمية Backend-side؟
- هل الحالة المهمة مصدرها Backend/DB؟

### اختبار الحياة الأساسي

```
Before → Click → Loading → Result → Back → Refresh
```

أي زر Navigation يلتزم بـ Back Button Navigation Contract في ARCHITECTURE.md،
وبنظام Navigation الرسمي مستقبلاً عند إنشائه.

---

## [BTN-12] Navigation Element Semantics

> Tab bars، bottom nav، sidebar links، breadcrumbs.
> للـ URL contract والروابط الرسمية: انظر **[NAV-02]** في `docs/design-system/NAVIGATION.md`.

### قواعد

1. **استخدم `<a>`** عندما الإجراء هو navigation (تغيير URL أو page route).
2. **استخدم `<button>`** عندما الإجراء هو سلوك داخل الصفحة (toggle panel، فتح modal).
3. **لا تخلط الاثنين** — `<a>` مع onclick يغير state داخلي = خطأ معماري.
4. **Tab المحدد:** `aria-current="page"` على الـ `<a>` النشط.
5. **Bottom nav active state:** class `active` + visual indicator (dot أو underline) — لا تعتمد على اللون وحده.
6. **روابط Back:** استخدم `<button>` (ليس `<a>`) مع fallback check قبل `history.back()` — انظر NAV-05.

---

## [BTN-13] Dangerous Actions

> إجراء مدمِّر أو سلبي — حذف، إزالة، reset.

### القرار حسب قابلية التراجع

**الإجراء قابل للتراجع بسهولة:**
يمكن استخدام Undo إذا كان هناك نظام Undo رسمي مناسب — لا يستلزم Confirmation Modal.

**الإجراء غير قابل للتراجع أو عالي الخطورة:**
استخدم Confirmation مناسباً لمستوى الخطورة.

**لا تستخدم Confirmation مزعجاً** لكل إجراء صغير قابل للتراجع.

### عند استخدام Confirmation

1. الزر Danger type — لا يُخفى، لا يُعطَّل ابتداءً.
2. Modal تأكيد يصف الإجراء بوضوح + يذكر عدم إمكانية التراجع عند الاقتضاء.
3. داخل Modal: زر Danger للتأكيد النهائي + زر Secondary للإلغاء.
4. **لا `confirm()` المدمج في المتصفح** — يخالف تصميم المنصة.
5. بعد التنفيذ: Feedback مناسب (toast أو UI update فوري).

### الممنوعات

```
❌ حذف مباشر بدون أي feedback أو confirmation لإجراء غير قابل للتراجع
❌ زر Danger باللون الأخضر (Primary)
❌ modal تأكيد بزرَّين Primary
❌ Confirmation مزعج على كل إجراء صغير
```

---

## [BTN-14] Performance Contract

### قواعد الـ Glow والـ Animation

```
✓ Default: Glow خفيف ثابت
✓ Hover: يقوى قليلاً
✓ Success: Pulse واحد قصير فقط
✓ Animations قصيرة وهادئة
✓ احترام prefers-reduced-motion عند التنفيذ
❌ Glow ثقيل جداً
❌ Animation مستمرة بلا سبب
❌ Glow متحرك دائماً على عشرات الأزرار
❌ عدة box-shadows ثقيلة متراكبة
❌ مؤثرات تسبب Layout Reflow متكرراً
```

### قواعد الـ Event Handling

- لا تُنشئ event listener على الزر في كل render — استخدم delegation أو أنشئ مرة واحدة.
- لا fetch داخل `mouseenter` أو `mouseover`.
- الـ state يُحفظ في متغير JS، لا يُقرأ من DOM.

---

## [BTN-15] Custom Button Exception

> يتطلب طلباً صريحاً من صاحب المشروع — ليس قراراً مستقلاً للمطور أو الـ AI.

### عند عدم وجود نظام مطابق

```
لا تنشئ Custom Button.
لا توثِّق استثناءً من تلقاء نفسك.
لا تنفِّذ.
ارجع لصاحب المشروع → BTN-01.
```

### عند طلب Custom Button صراحةً من صاحب المشروع

القواعد الوظيفية الأساسية تبقى مطبَّقة افتراضياً:

```
✓ No Text Selection — BTN-08
✓ Touch Target مريح
✓ Loading عند الحاجة
✓ Duplicate Click Prevention
✓ Backend-confirmed Success
✓ Lifecycle Review — BTN-11
✓ Accessibility (aria-label، focus-visible)
```

**Custom Button لا يصبح جزءاً من النظام العام تلقائياً.**
يُضاف للنظام فقط بقرار منفصل من صاحب المشروع.

---

## [BTN-16] Forbidden Patterns

قائمة شاملة بما هو ممنوع في أي زر في المنصة:

```
❌ اختراع نوع زر غير موجود في النظام
❌ اختيار أقرب Variant عند عدم وجود match
❌ اختيار Primary/Secondary/Danger باجتهاد شخصي بدون نظام مطابق
❌ إنشاء Custom Button بدون طلب صريح من صاحب المشروع
❌ إنشاء CSS خاص لزر جديد خارج النظام بدون طلب صريح
❌ تنفيذ الزر ثم توثيقه لاحقاً
❌ اعتبار غياب القاعدة إذناً بالاختيار الشخصي

❌ Solid Fill كافتراضي
❌ Pill أو Capsule كافتراضي
❌ Glow ثقيل أو متحرك باستمرار
❌ Success قبل Backend Confirmation
❌ Optimistic UI على Toggle Button بدون contract خاص موثَّق
❌ Desired State Queue كقاعدة عامة على كل toggle

❌ <div> أو <span> كزر بدون role="button" و tabindex="0"
❌ <a> بـ href="#" كزر — استخدم <button>
❌ <button type="submit"> خارج <form> حقيقي
❌ onclick="location.href='...'" — استخدم <a href>
❌ outline: none بدون :focus-visible بديل
❌ user-select: text على button
❌ Loading state بـ setTimeout وهمي
❌ تنفيذ إجراء غير قابل للتراجع أو عالي الخطورة بدون Confirmation مناسب
❌ تنفيذ Action بدون Feedback مناسب عندما يحتاج المستخدم معرفة نتيجة العملية
❌ Primary button أحمر اللون
❌ Danger button أخضر اللون
❌ استخدام Disabled State بدون تعريف سلوكه والسبب الذي يستدعيه
❌ إخفاء الزر في حالة Loading بدلاً من تعطيله
❌ تغيير width/height عند hover
❌ <button> داخل <button>
❌ Glow متحرك دائماً على عشرات الأزرار في نفس الوقت
❌ إضافة حالة State جديدة داخل صفحة بدون قرار على مستوى النظام
```

---

## [BTN-17] Button Visibility & Permission Contract

> **العقد الرسمي لكل زر مرتبط بصلاحية أو Viewer Mode.**
>
> يُقرأ هذا القسم مع:
> → **[VM-05]** — الفصل بين Authentication / Authorization / Ownership / Visibility
> → **[VM-06]** — Backend كمرجع نهائي
> → **[VM-07]** — Frontend Visibility = UX فقط
> من ملف `docs/design-system/VIEWER-MODES.md`

---

### ثلاثة أحوال للزر من منظور الصلاحية

| الحال | التعريف | متى يُستخدَم |
|-------|---------|-------------|
| **Visible & Enabled** | الزر ظاهر وقابل للضغط | الـ Viewer Mode يُتيح الإجراء لهذا المستخدم |
| **Hidden** | الزر غير موجود في الـ DOM أو مخفي | هذا الـ Viewer Mode لا يُفترض أن يرى هذا الزر أصلاً |
| **Disabled** | الزر ظاهر لكن غير تفاعلي | المستخدم يرى الإجراء لكن الشروط لا تسمح به حالياً |

---

### السبعة بنود الإلزامية لكل زر مرتبط بصلاحية

**عند توثيق أو تنفيذ أي زر مرتبط بصلاحية، يجب الإجابة على هذه البنود السبعة:**

#### 1. من يرى الزر؟

حدِّد بوضوح أيٌّ من الأوضاع التالية يرى الزر:

```
□ Owner فقط
□ Registered User فقط (كل الأنواع)
□ Registered User من نوع محدد (emp / co / edu)
□ Guest فقط
□ الجميع (بما في ذلك Guest)
□ Owner + Registered User (لكن ليس Guest)
□ تركيبة أخرى — وضِّحها بدقة
```

#### 2. من لا يرى الزر؟

حدِّد من يُفترض ألَّا يرى الزر نهائياً (Hidden — ليس Disabled):

```
□ Guest لا يرى زر "متابعة" — يرى بدلاً منه زر "سجّل للمتابعة"
□ Registered User لا يرى أزرار التحرير في صفحة شخص آخر
□ emp لا يرى زر "حفظ مرشح" في صفحة الموظف (هذا للشركات)
```

#### 3. متى يكون الزر Disabled؟

الـ Disabled للحالة، لا للصلاحية. أمثلة:

```
□ زر "إرسال" معطَّل لأن الـ form فارغ — ليس لأن المستخدم ليس مالكاً
□ زر "التقديم" معطَّل لأن الوظيفة مُغلقة — ليس لأن المستخدم emp
□ زر "حفظ" معطَّل في حالة Loading
```

**ممنوع:** استخدام Disabled كبديل عن Hidden عند اختلاف Viewer Mode.

#### 4. من يملك الصلاحية الفعلية؟

```
□ المالك فقط (jwt.user_id == owner_id في DB)
□ نوع حساب محدد (user_type من JWT)
□ المالك + نوع محدد
□ أي مستخدم مسجَّل
□ لا أحد (الإجراء مقيَّد حالياً)
```

#### 5. مصدر قرار الرؤية (Visibility Source)

```
□ window._scViewerType (Profile V2)
□ companyState.permissions.isOwner (Company Profile)
□ مقارنة session.id مع owner_id من API response
□ user_type من localStorage.tw_user (للعرض فقط — ليس أمناً)
□ غياب JWT في localStorage (للتمييز بين guest والبقية)
```

> **تذكير:** أي من هذه المصادر هي UX signal فقط (VM-07). لا توفِّر أماناً.

#### 6. مصدر قرار الصلاحية (Permission Source)

```
□ JWT: user_type من الـ token (server-side)
□ DB: مقارنة jwt.user_id مع owner_id في الجدول المعني
□ DB: حقل محدد يحدد الصلاحية (مثل: jobs.status, profiles.is_verified)
□ تركيبة من الأعلى
```

> **إلزامي:** الصلاحية الفعلية تُتحقَّق دائماً server-side — ليس من frontend signal.

#### 7. سلوك الـ Backend عند محاولة الوصول غير المُصرَّح بها

```
□ 401 — لا يوجد JWT أو JWT منتهٍ
□ 403 — JWT صالح لكن بدون صلاحية
□ 404 — المورد غير موجود أو الوصول إليه محجوب (لإخفاء وجوده)
```

يجب تحديد الكود المتوقَّع وصياغة الـ response body عند توثيق كل زر.

---

### مثال: زر "تعديل الملف الشخصي" في Profile V2

| البند | القيمة |
|-------|--------|
| من يرى؟ | Owner فقط |
| من لا يرى؟ | Registered User + Guest → Hidden |
| متى Disabled؟ | لا يُعطَّل — إما ظاهر (Owner) أو مخفي (غيره) |
| من يملك الصلاحية؟ | المالك — `jwt.user_id == profiles.user_id` في DB |
| مصدر الرؤية | `window._scViewerType === 'owner'` |
| مصدر الصلاحية | DB: `profiles.user_id == jwt.user_id` في PUT endpoint |
| Backend لغير المالك | `403 Forbidden` |

---

### مثال: زر "التقديم للوظيفة"

| البند | القيمة |
|-------|--------|
| من يرى؟ | Registered User من نوع `emp` فقط |
| من لا يرى؟ | Owner (صاحب الشركة) → Hidden · Guest → زر "سجّل للتقديم" |
| متى Disabled؟ | الوظيفة مؤرشفة / مُغلقة · المستخدم طبَّق مسبقاً |
| من يملك الصلاحية؟ | أي `emp` مُتحقَّق منه + الوظيفة لا تزال نشطة |
| مصدر الرؤية | `user_type === 'emp'` من `localStorage.tw_user` (عرض فقط) |
| مصدر الصلاحية | JWT `user_type == 'emp'` + `jobs.archived_at IS NULL` في server.py |
| Backend للشركة | `403 Forbidden` |
| Backend للوظيفة المؤرشفة | `409 {"code":"job_archived"}` |

---

### قواعد BTN-17 الإلزامية

```
✓ كل زر مرتبط بصلاحية يجب توثيق البنود السبعة قبل التنفيذ
✓ Hidden هو قرار UX/Visibility فقط — سواء كان غياباً من DOM أو display:none،
  كلاهما ليس حماية أمنية. الحماية الفعلية دائماً في Backend endpoint بصرف النظر عن DOM state
✓ Disabled يُعني حالة وظيفية، لا صلاحية — أوضح للمستخدم لماذا
✓ الـ Backend endpoint مُؤمَّن دائماً بصرف النظر عن الـ UI
✓ مصدر الصلاحية دائماً server-side — Visibility Source مجرد UX
```

```
❌ استخدام Disabled بدلاً من Hidden عند اختلاف Viewer Mode
❌ الاعتماد على UI state وحده لمنع إجراء
❌ إرسال بيانات خاصة من الـ backend دون تحقق من الصلاحية
❌ نقل منطق الصلاحية من backend إلى frontend
❌ تنفيذ زر صلاحياته غير موثَّقة في البنود السبعة
```

---

*آخر تحديث: 2026-07-18 — Button System V1 rev.2 (corrections: BTN-01 STOP rule, BTN-02 outlined/glow visual, BTN-03 semantic color clarification, BTN-04 slim principle + existing constraints, BTN-05 vertical stack rules, BTN-06 borderless header icons, BTN-07 full states list, BTN-08 touch-callout, BTN-09 correct save lifecycle, BTN-10 backend-confirmed toggle, BTN-11 full checklist, BTN-13 context-based confirmation, BTN-14 glow performance, BTN-15 owner-request-only, BTN-16 expanded) · BTN-17 Visibility & Permission Contract (links to VIEWER-MODES.md)*
