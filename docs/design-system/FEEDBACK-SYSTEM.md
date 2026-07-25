# [DS-FEEDBACK] Operational Feedback System — V1

> **الـ contract المعماري الرسمي لنظام Operational Feedback في منصة تواصلنا**
>
> V1 — توثيق فقط · لا يمس أي Runtime code.
> المرجع الرسمي للـ AI sessions والمطورين عند كل مهمة تخص التغذية الراجعة للمستخدم (Toast / Snackbar / Feedback لحظي).
>
> **الـ Runtime الحالي:** `showToast()` في `tw_shared.js` — يحتاج تحسينات موثَّقة في FBK-24. راجع FBK-28 (Runtime Direction) للاتجاه المخطط له.

---

## جدول المحتويات

| القسم | العنوان |
|-------|---------|
| FBK-00 | Routing Protocol — متى تقرأ هذا الملف |
| FBK-01 | الغرض والنطاق |
| FBK-02 | Ownership Boundaries — ما DS-FEEDBACK يملك وما لا يملك |
| FBK-03 | Feedback Event — المفهوم الأساسي (Platform-neutral) |
| FBK-04 | الأنواع الرسمية في V1 |
| FBK-05 | Single Global Feedback Surface |
| FBK-06 | Replacement Policy |
| FBK-07 | Duration Policy — مركزية |
| FBK-08 | دورة الحياة (Lifecycle) |
| FBK-09 | Mobile Positioning Behavior Contract |
| FBK-10 | RTL والـ Centering |
| FBK-11 | Layer Architecture × DS-OVL |
| FBK-12 | Accessibility Contract V1 |
| FBK-13 | Pointer Interaction Contract |
| FBK-14 | Icons Contract |
| FBK-15 | Operation Identity — V1 Policy / V2 Concept |
| FBK-16 | Action Zone Architecture — V2 Concept |
| FBK-17 | Navigation Integration |
| FBK-18 | Reduced Motion |
| FBK-19 | Error Normalization Ownership |
| FBK-20 | DS-VAL × DS-FEEDBACK — Orchestration Decision Rule |
| FBK-21 | XSS Security Contract — P0 Runtime Debt |
| FBK-22 | Flutter / Multi-platform Semantics |
| FBK-23 | Migration Inventory (Runtime Audit) |
| FBK-24 | Runtime Debts Catalogue |
| FBK-25 | Must-Have V1 |
| FBK-26 | Defer V2+ |
| FBK-27 | Forbidden Patterns |
| FBK-28 | Runtime Direction (Non-binding) |
| FBK-29 | خارج النطاق — V1 |

---

## FBK-00 — Routing Protocol

**قبل كتابة أي كود يخص رسائل المستخدم، الإشعارات القصيرة، أو أي شكل من أشكال Feedback لحظي — تحقق من هذا الجدول أولاً:**

| المهمة | الأقسام |
|--------|---------|
| عرض رسالة نجاح/فشل عملية مستقلة | FBK-00 → FBK-01 → FBK-04 → FBK-05 → FBK-19 → FBK-20 |
| تحديد نوع الـ Feedback (success/error/…) | FBK-04 |
| حدود مع DS-VAL (Form vs Action) | FBK-20 |
| Accessibility | FBK-12 |
| Mobile positioning | FBK-09 |
| RTL / Centering | FBK-10 |
| Layer / z-index | FBK-11 |
| Operation Identity / Loading feedback | FBK-15 |
| Action في الـ Snackbar (Undo/Retry) | FBK-16 |
| تكامل مع Navigation/twNavigate | FBK-17 |
| Forbidden patterns | FBK-27 |
| الحالة الراهنة للـ Runtime | FBK-28 |
| Migration من alert() / local toast | FBK-23 |

**إذا المهمة تخص:**
- خطأ حقل داخل نموذج → **DS-VAL** → `docs/design-system/VALIDATION-ERRORS.md` VAL-08
- خطأ عام ضمن سياق Form → **DS-VAL** → VAL-09 (Form-level banner)
- تأكيد قرار خطير → **DS-OVL** → `docs/design-system/OVERLAY-SYSTEM.md` OVL-27
- إشعار جرس مستمر → **Notifications 🔔** → `ARCHITECTURE.md §19`
- رسالة دردشة → **Messenger** → `ARCHITECTURE.md §18`
- Tooltip أو Popover → **STOP** — غير موثَّق بعد (راجع OVL-37)

---

## FBK-01 — الغرض والنطاق

### ما الذي يملكه DS-FEEDBACK؟

DS-FEEDBACK هو النظام الموحد الرسمي لـ **Operational Feedback اللحظي** في منصة تواصلنا. وهو أي رسالة قصيرة مؤقتة تُعلم المستخدم بنتيجة عملية قام بها، وتختفي تلقائياً دون أن تمنع التفاعل مع الصفحة.

**أمثلة ضمن نطاق DS-FEEDBACK:**

| المثال | النوع |
|--------|-------|
| تم حفظ التعديلات بنجاح | success |
| تم حذف الخبرة | success |
| تم نسخ الرابط | success |
| تم إرسال الطلب | success |
| تعذر حفظ التعديلات — حاول مجدداً | error |
| تعذر الاتصال بالخادم | error |
| الجلسة ستنتهي قريباً | warning |
| تم إرسال الرمز لبريدك الإلكتروني | info |

### ما الذي لا يملكه DS-FEEDBACK؟

| الحالة | المالك الصحيح |
|--------|--------------|
| أخطاء حقول النموذج (required، format) | DS-VAL → VAL-08 |
| Form-level error banner داخل Form | DS-VAL → VAL-09 |
| تأكيد قرار خطير (هل تريد الحذف؟) | DS-OVL → OVL-27 |
| إشعارات الجرس 🔔 (وصلك طلب جديد) | Notifications `ARCHITECTURE.md §19` |
| رسائل الدردشة | Messenger `ARCHITECTURE.md §18` |
| Loading indicator | DS-BTN / Component المُعني |
| Progress Bar لرفع ملف | Upload Component |
| Tooltip / Popover | غير موثَّق بعد |
| Banner دائم (لا يختفي تلقائياً) | Feature/Layout — خارج DS-FEEDBACK |
| ترجمة Raw Backend Errors | Feature / Orchestration Layer |
| Business error parsing | API-MUT-11 |

---

## FBK-02 — Ownership Boundaries

### مبدأ الملكية

**DS-FEEDBACK يملك:**
- الـ Surface البصرية للـ Snackbar (شكل العنصر، موضعه، animation الدخول والخروج)
- Lifecycle المركزي لكل الـ Feedback (timer، replace، animate)
- Accessibility contract للـ Surface (role، aria-live، aria-atomic)
- Duration Policy المركزية لكل الأنواع
- Layer Band (Conceptual Level 4)

**DS-FEEDBACK لا يملك:**
- قرار "ماذا أعرض؟" — تملكه Feature/Orchestration Layer
- ترجمة الأخطاء من Backend إلى رسائل إنسانية — تملكها Feature Layer (بعد API-MUT-11)
- توجيه الأخطاء لـ DS-VAL أو DS-FEEDBACK — يملكه Orchestration (راجع FBK-20)
- Navigation — يملكه DS-NAV
- Form Dirty State — يملكه DS-FRM
- Scroll Lock — يملكه DS-OVL
- Focus Management — يملكه DS-OVL (للـ Overlays) · DS-FEEDBACK لا يسرق Focus

### مبدأ الفصل

```
Feature/Orchestration Layer
  ├── حدد السياق (داخل Form؟ خارجه؟)
  ├── نظّم الأخطاء (API-MUT-11)
  ├── وزّع الأخطاء: DS-VAL (Form) أو DS-FEEDBACK (Action)
  └── استدعِ DS-FEEDBACK بـ user-safe message جاهزة

DS-FEEDBACK:
  └── اعرض الرسالة فقط — لا يعلم من أين أتت
```

---

## FBK-03 — Feedback Event — المفهوم الأساسي (Platform-neutral)

### FeedbackEvent — الوحدة المفاهيمية

كل رسالة يعالجها DS-FEEDBACK تُمثَّل مفاهيمياً كـ **FeedbackEvent** مستقل عن منصة التنفيذ:

```
FeedbackEvent [Conceptual — Platform-neutral]:
  type:     'success' | 'error' | 'warning' | 'info'
  message:  string  — نص آمن جاهز، مُعالَج مسبقاً بالـ Orchestration Layer
  duration: number | Policy  — تُحدده Duration Policy (FBK-07) — لا Feature
```

**المفاهيم المؤجلة (V2):**

```
FeedbackEvent V2 [Conceptual]:
  operationId?: string  — لمستقبل Operation Identity (FBK-15)
  action?:      { label, onAction }  — لمستقبل Action Zone (FBK-16)
```

### لماذا Platform-neutral؟

Web Runtime تُنشئ `div.tw-snackbar` في DOM وتُحرِّكها بـ CSS.
Flutter Runtime ستستخدم `SnackBar` widget بنفس semantics.
العقد المفاهيمي (type / message / duration) هو المشترك — طريقة الرسم تفصيل تنفيذي.

---

## FBK-04 — الأنواع الرسمية في V1

### الأنواع الأربعة

| النوع | المعنى | مثال |
|-------|--------|-------|
| `success` | نجحت العملية | "تم الحفظ" |
| `error` | فشلت العملية | "تعذر الحفظ" |
| `warning` | تحذير / انتبه | "الجلسة ستنتهي" |
| `info` | معلومة مرتبطة بعملية | "تم إرسال الرمز" |

### الـ CSS Semantic Tokens

| النوع | Token المقترح | Fallback الحالي في `tw_shared.css` |
|-------|--------------|-------------------------------------|
| `success` | `var(--ac)` | `#00c896` |
| `error` | `var(--danger)` | `#f87171` |
| `warning` | `var(--warning)` | `#fbbf24` |
| `info` | `var(--ac2)` | `#2563ff` |

**قاعدة:** استخدام الـ Semantic Tokens الرسمية من `tw_shared.css` — ممنوع اختراع ألوان محلية جديدة.

---

## FBK-05 — Single Global Feedback Surface

### القاعدة

في V1: **سطح Feedback واحد عالمي لكل الصفحة.**

لا Stack ولا Queue متعددة في V1. لا أكثر من رسالة ظاهرة في نفس الوقت.

### التبرير

- تواصلنا نادراً ما تُشغِّل عمليتين متوازيتين تنتجان Feedback في نفس اللحظة.
- Stack/Queue يُضيف تعقيداً معمارياً غير مبرر في V1.
- Replacement Policy (FBK-06) يعالج جميع الحالات الواقعية.

### التنفيذ الحالي

`tw_shared.js` يحتفظ بـ `_twToast` كـ reference للعنصر الحالي. هذا النمط صحيح ويجب الحفاظ عليه في Runtime المستقبلي مع إضافة `_twTimer` reference للـ timeout (FBK-24 — Runtime Debt M2).

---

## FBK-06 — Replacement Policy

### القاعدة: Latest Replaces Current

إذا ظهر FeedbackEvent جديد بينما الحالي لا يزال ظاهراً:

```
1. clearTimeout(_twTimer)        ← إلغاء timer القديم
2. إزالة الـ Surface الحالية (أو تحديث محتواها)
3. عرض الـ Surface الجديدة
4. بدء lifecycle الجديد (timer الجديد)
```

### لماذا "Latest Wins"؟

| السيناريو | النتيجة |
|-----------|---------|
| نجاح يستبدل نجاح | مقبول — آخر عملية تُعلَن |
| خطأ يستبدل نجاح | مقبول — الخطأ أهم |
| نجاح يستبدل خطأ | مقبول — العملية التالية نجحت |
| نفس الرسالة 5 مرات | Replacement يمنع التراكم ✅ |

لا Priority-aware replacement في V1 — يُضاف فقط عند وجود حاجة واقعية موثَّقة.

### الـ clearTimeout ضروري

```js
// ممنوع (M2 — Runtime Debt الحالي):
// setTimeout جديد بدون إلغاء القديم → timer القديم يُخفي الرسالة الجديدة

// الصحيح:
clearTimeout(_twTimer);
_twTimer = setTimeout(hideFeedback, duration);
```

---

## FBK-07 — Duration Policy — مركزية

### القاعدة

**Duration ملك DS-FEEDBACK مركزياً — Feature code لا تختار أرقاماً.**

| النوع | المدة | المبرر |
|-------|-------|--------|
| `success` | **2800ms** | قصيرة — نجاح يُقرأ بلمحة |
| `info` | **3200ms** | عادية — معلومة تحتاج لحظة |
| `warning` | **4000ms** | أطول — تحذير يجب قراءته |
| `error` | **4500ms** | الأطول — خطأ يحتاج المستخدم وقتاً لقراءته |

`success = 2800ms` يُعتمَد من الـ Runtime الحالي للتوافق مع 36 صفحة.

### ممنوعات

```js
// ❌ Feature تختار مدتها بنفسها
showToast('تم الحذف', 'success', 5000)     // لا
showToast('جارٍ التحميل...', 'info', 99999) // ❌❌ Loading Workaround ممنوع
```

### Persist Duration — V2 فقط

رسائل "تبقى حتى يتصرف المستخدم" تتطلب Action Zone (FBK-16) وهي V2 فقط.

---

## FBK-08 — دورة الحياة (Lifecycle)

### الحالات

```
hidden
  ↓ (FeedbackEvent arrives)
entering   ← animation إدخال / fade-in + translateY
  ↓ (animation complete)
visible    ← timer يعمل
  ↓ (timer fires)
exiting    ← animation خروج / fade-out
  ↓ (animation complete)
hidden     ← cleanup: remove element (or set hidden)
```

### قواعد الـ Lifecycle

1. **Replacement أثناء `visible`:** ينتقل مباشرة إلى `entering` للرسالة الجديدة بعد `clearTimeout`.
2. **Replacement أثناء `exiting`:** يُلغي animation الخروج، ينتقل إلى `entering` للجديد.
3. **Reduced Motion:** `entering` و `exiting` تصبح fades مختصرة بدون translateY (راجع FBK-18).
4. **Timer cleanup:** عند أي تنتقال جديد يجب `clearTimeout` أولاً.
5. **DOM cleanup:** عند دخول `hidden` يُزال العنصر أو يُخفى بـ `hidden attribute`.

### Stuck State Guard

إذا لم تكتمل animation الخروج (نادر — browser bug أو tab hidden):
- Timeout Fallback بعد 1000ms يُجبر على `hidden`
- مشابه لـ DS-OVL OVL-07 (Timeout Fallback يمنع Stuck State)

---

## FBK-09 — Mobile Positioning Behavior Contract

### العقد السلوكي (لا رقم ثابت)

```
Behavior Contract — DS-FEEDBACK Mobile Positioning:

الـ Feedback Surface يجب أن تبقى ظاهرة بالكامل فوق:
  1. Bottom Navigation Bar (إن وُجد على هذه الصفحة)
  2. env(safe-area-inset-bottom) (Safe Area لأجهزة Notch)
  3. أي UI ثابت مُثبَّت في أسفل الـ viewport على هذه الصفحة
     (مثال: Message Composer في messages.html)
```

### آلية التنفيذ المقترحة (Implementation Direction — غير إلزامية)

**CSS Custom Property لكل Layout:**

```css
/* الافتراضي — صفحات بـ Bottom Nav */
:root {
  --tw-feedback-bottom: 80px;
}

/* صفحات بدون Bottom Nav (desktop, admin, etc.) */
.no-bottom-nav {
  --tw-feedback-bottom: 24px;
}

/* صفحة messages — فوق Composer */
.messages-page {
  --tw-feedback-bottom: 130px;  /* يتغير إذا تغير ارتفاع Composer */
}
```

```css
/* DS-FEEDBACK Surface */
.tw-snackbar {
  bottom: var(--tw-feedback-bottom, 24px);
}

@media (min-width: 600px) {
  .tw-snackbar {
    bottom: 24px;  /* Desktop — لا Bottom Nav */
  }
}
```

**الفائدة:** إذا تغير ارتفاع الـ Composer أو Bottom Nav، يُحدَّث `--tw-feedback-bottom` في ملف Layout — لا تعديل في DS-FEEDBACK.

### Interim Heuristic (V1)

حتى تُنشأ Layout Tokens الرسمية:
- `bottom: 80px` على Mobile (يعلو Bottom Nav الحالي)
- `bottom: 24px` على Desktop (≥ 600px)

هذه أرقام مؤقتة وليست Architecture Contract — توثَّق كـ Runtime Debt (FBK-24 M1).

### قاعدة التغيير

أي تغيير على الـ offset لا يمس DS-FEEDBACK — يمس فقط `--tw-feedback-bottom` في Layout.

---

## FBK-10 — RTL والـ Centering

### القاعدة

الـ Snackbar في DS-FEEDBACK **يتمركز أفقياً في منتصف الشاشة** بصرف النظر عن اتجاه `dir="rtl"`.

### السبب

`inset-inline-start: 50%` في صفحات RTL يُعيد تفسيره إلى `right: 50%`، مما قد يُنتج نتيجة غير متوقعة عند الجمع مع `transform: translateX(-50%)`.

الـ Snackbar ليست عنصراً يبدأ من حافة — هي عنصر مُرتكز على المنتصف المادي للشاشة.

### Implementation Direction

```css
/* ✅ صحيح — يعمل بشكل موثوق في RTL وLTR */
.tw-snackbar {
  left: 50%;
  transform: translateX(-50%) translateY(20px);
}
.tw-snackbar.show {
  transform: translateX(-50%) translateY(0);
}
```

`left` هنا physical وليس logical — صحيح تماماً لعنصر يُرتكز على المنتصف.

### Direction العنصر الداخلي

نص الرسالة يرث `dir="rtl"` من `<body>` — هذا صحيح ومطلوب لعرض النص العربي بشكل سليم.

---

## FBK-11 — Layer Architecture × DS-OVL

### المستوى الرسمي

من DS-OVL OVL-14 (Layer Architecture):

```
Conceptual Level 5: Accessibility Layer    ← Skip links, Critical dialogs
Conceptual Level 4: Global Feedback Band  ← DS-FEEDBACK يملك هذا المستوى
Conceptual Level 3: Overlay-local Floating ← DS-SEL dropdown داخل Overlay
Conceptual Level 2: Overlay Stack Band     ← DS-OVL يملك هذا المستوى
Conceptual Level 1: Sticky / Floating Page UI
Conceptual Level 0: Base Page Content
```

**DS-FEEDBACK يشغل Conceptual Level 4 — فوق DS-OVL Stack.**

### قاعدة الـ z-index

**DS-FEEDBACK لا يملك رقم z-index ثابتاً.**

الأرقام الفعلية تُحدَّد في **Global Layer Tokens** لم تُنشأ بعد (راجع OVL-14).

- الـ Runtime الحالي: `z-index: 9999` في `tw_shared.css` — **placeholder مؤقت** وليس Architecture Contract.
- عندما تُنشأ Global Layer Tokens، يُستبدَل `9999` بـ token المستوى 4.
- Feature code **ممنوع** يكتب z-index للـ Feedback مباشرةً.

### العلاقة مع DS-OVL

| العنصر | يملكه |
|--------|-------|
| z-index للـ Overlay Stack | DS-OVL (Level 2-3) |
| z-index للـ DS-FEEDBACK | DS-FEEDBACK (Level 4) — من Global Layer Tokens |
| z-index للـ DS-SEL dropdown داخل Overlay | DS-OVL Layer Context (Level 3) |
| Global Layer Tokens | نظام مركزي — لم يُنشأ بعد |

DS-FEEDBACK وDS-OVL لا يتواصلان مباشرةً. يتعايشان عبر Layer Bands فقط.

---

## FBK-12 — Accessibility Contract V1

### المتطلبات الإلزامية

**جميع الأنواع في V1 تستخدم نفس الـ ARIA attributes:**

```html
<div
  class="tw-snackbar success"
  role="status"
  aria-live="polite"
  aria-atomic="true"
>
  تم الحفظ بنجاح
</div>
```

| Attribute | القيمة V1 | السبب |
|-----------|-----------|-------|
| `role` | `status` | غير طارئ — announcement هادئ |
| `aria-live` | `polite` | ينتظر انتهاء القراءة الحالية |
| `aria-atomic` | `true` | يقرأ كامل محتوى العنصر عند تغييره |

### لماذا `polite` لـ error؟

"تعذر الحفظ" و "تعذر رفع الصورة" ليستا طوارئ. Screen reader يُعلن بعد انتهاء الكلام الحالي. المستخدم لا يفقد شيئاً إذا انتظر.

`role="alert"` + `aria-live="assertive"` = مقاطعة فورية — مناسب فقط للطوارئ الحقيقية (انتهاء الجلسة، فقدان الاتصال الكامل). يُضاف في V2 عبر `critical: true` flag.

### Focus — ممنوع

DS-FEEDBACK **لا يسرق Focus** عند الظهور. المستخدم يواصل تفاعله مع الصفحة.

إذا أُضيف Action Zone مستقبلاً (FBK-16): يكون Keyboard reachable عبر Tab، لكن لا auto-focus.

### Announcement Timing

الـ `aria-live` يعمل عند تغيير `textContent` داخل العنصر الموجود في DOM.
لضمان الإعلان الصحيح — اقرأ FBK-28 (Runtime Direction) للنمط المقترح.

---

## FBK-13 — Pointer Interaction Contract

### V1 — Message Body غير تفاعلية

```css
/* V1 */
.tw-snackbar { pointer-events: none; }
```

Snackbar V1 لا تمنع النقر على ما تحتها من المحتوى.

### V2 — Action Zone تفاعلية

Architecture يجب أن تسمح مستقبلاً بـ Action Zone تفاعلية:

```
Surface Architecture [Conceptual]:
  ┌──────────────────────────────────┐
  │  Message Body                    │  ← pointer-events: none (دائم)
  │  "تم حذف الخبرة"                │
  ├──────────────────────────────────┤
  │  Action Zone (V2)                │  ← pointer-events: auto (V2 فقط)
  │  [تراجع]  [إعادة المحاولة]       │
  └──────────────────────────────────┘
```

**القاعدة:** ممنوع كتابة Contract يقول "Snackbar دائماً `pointer-events: none` على كل شيء" — هذا يكسر Action Zone مستقبلاً.

---

## FBK-14 — Icons Contract

### الأيقونة دور زخرفي

إذا كان نص الرسالة ينقل المعنى وحده ("تم الحفظ بنجاح"):
```html
<span aria-hidden="true"><!-- icon here --></span>
```

الأيقونة `aria-hidden="true"` لأن Screen Reader يقرأ النص فقط.

### Icon System المطلوب

الـ Runtime الحالي يستخدم Emoji (`✅ ❌ ℹ️`) كـ placeholder. هذه **ليست** Architecture Contract النهائي.

**المطلوب في Runtime Phase:**
- استخدام Icon System الرسمي للمشروع عند توثيقه (DS-ASSET — مؤجل).
- إذا لم يُوثَّق DS-ASSET: استخدم SVG icons مضمَّنة بـ `aria-hidden="true"`.
- ممنوع تعريف Icon Contract محلي داخل DS-FEEDBACK — يُدخَّر لـ DS-ASSET.

### العلامات الحالية كـ Runtime Placeholder

| النوع | Emoji الحالي | ملاحظة |
|-------|-------------|---------|
| `success` | `✅` | Placeholder — ليس Architecture Contract |
| `error` | `❌` | Placeholder — ليس Architecture Contract |
| `info` | `ℹ️` | Placeholder — ليس Architecture Contract |
| `warning` | لا يوجد | يُضاف في Runtime Phase |

---

## FBK-15 — Operation Identity — V1 Policy / V2 Concept

### V1 Policy (إلزامي الآن)

**Loading state لا يدخل Snackbar في V1.**

| العملية | V1 الصحيح |
|---------|-----------|
| رفع صورة | Loading في الزر (DS-BTN) · Snackbar تظهر عند اكتمال الرفع |
| حفظ البروفايل | زر "جارٍ الحفظ..." (DS-BTN) · Snackbar "تم الحفظ" عند النجاح |
| إرسال طلب | زر Disabled أثناء الإرسال · Snackbar للنتيجة فقط |

Loading يبقى في: الزر، الـ Component، Spinner.

**ممنوع في V1:**
```js
showToast('جارٍ رفع الصورة...', 'info', 99999)  // ❌ Loading workaround
```

**إذا أردت "Loading → نتيجة" بدون Snackbar V2:**
اجعل الزر يُظهر loading ثم اجعل `showToast()` تُظهر النتيجة — replace تلقائي.

### V2 Concept (موثَّق الآن — غير مُنفَّذ)

```
Operation Identity V2 [Conceptual]:
  - كل عملية لها operationId فريد
  - showFeedback({ id, type, message }) يُنشئ أو يُحدِّث Feedback بنفس الـ id
  - updateFeedback(id, { type, message }) يُحوِّل Loading → Success / Error على نفس الـ Surface
  - بدون glitch بصري — نفس العنصر يتحدث محتواه
```

لا يُنفَّذ حتى يُطلب صراحةً. توثيقه الآن يمنع كسر API عند التنفيذ مستقبلاً.

---

## FBK-16 — Action Zone Architecture — V2 Concept

### V1 — لا Actions

لا تُنفَّذ Action buttons داخل Snackbar في V1.

### V2 Concept (موثَّق الآن — غير مُنفَّذ)

```
Snackbar with Action Zone V2 [Conceptual]:
┌──────────────────────────────────────────┐
│  Message Body                            │
│  "تم حذف الخبرة"                        │
│                              [تراجع]  ✕  │
└──────────────────────────────────────────┘
```

```
FeedbackEvent V2 [Conceptual]:
  action?: {
    label:    string           // نص الزر ("تراجع" / "إعادة المحاولة")
    onAction: () => void       // callback
  }
  dismissible?: boolean        // ✕ يظهر أو لا (افتراضي: لا)
```

**قيود V2 الـ Action Zone:**
- Action Zone فقط — ليس Mini Modal
- لا أكثر من Action واحد في V1 Action support
- Keyboard reachable (Tab) لكن لا auto-focus
- `pointer-events: auto` على Action Zone فقط (راجع FBK-13)

---

## FBK-17 — Navigation Integration

### القاعدة

لا تُشغِّل `twNavigate()` أو أي navigation فوري مباشرةً بعد `showToast()`.

**السبب:** `twNavigate()` في `tw_shared.js` يُخفي الصفحة بـ `opacity: 0` خلال 180ms ثم ينتقل. Snackbar قد تختفي مع الصفحة قبل أن يُطلع المستخدم عليها.

### القاعدة المعمارية

```
DS-FEEDBACK لا يملك Navigation.
DS-NAV يملك Navigation.
Feature/Orchestration Layer تقرر التنسيق.
```

### الخيارات عند الاحتياج لـ Feedback + Navigation

| الخيار | المتى |
|--------|-------|
| اعرض Feedback، انتظر، ثم انتقل | إذا كان Feedback ضرورياً قبل الانتقال |
| اعرض Feedback في الصفحة الجديدة | أفضل — Snackbar تظهر بعد الوصول |
| لا Feedback + انتقل فوراً | إذا كانت الصفحة الجديدة تُوضِّح النجاح |

---

## FBK-18 — Reduced Motion

### العقد

```css
@media (prefers-reduced-motion: reduce) {
  .tw-snackbar {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- **لا bouncing** في أي حالة.
- **لا flashy animation** تمنع القراءة.
- Reduced Motion يُلغي الـ translateY وينتج fade بسيط.
- Lifecycle يبقى سليماً — فقط الـ animation تتغير.

---

## FBK-19 — Error Normalization Ownership

### السلسلة الرسمية

```
API Response (raw)
    ↓
normalizeErrorResponse()        ← API-MUT-11 يملك هذا
    ↓
{ fieldErrors[], generalError: { code, message } }
    ↓
Feature / Orchestration Layer
    ├── إذا fieldErrors[] → routeErrors(normalized)  → DS-VAL VAL-08 (Inline)
    ├── إذا generalError + في Form context → showFormError(msg) → DS-VAL VAL-09
    └── إذا generalError + Action context → showFeedback(msg, 'error') → DS-FEEDBACK
```

### القاعدة الحرجة

**DS-FEEDBACK لا يستقبل Raw Backend Response ولا يُقرِّر ماذا يقول.**

```js
// ❌ ممنوع — Raw backend data وصل مباشرة للـ Feedback
showToast(res.detail, 'error')
showToast(d.error || d.detail || r.status, 'error')

// ✅ الصحيح — message مُعالَجة من Feature Layer
const normalized = normalizeErrorResponse(body)
showToast(normalized.generalError.message, 'error')
```

### ملاحظة على `generalError.message`

`normalizeErrorResponse()` في API-MUT-11 يُعيد `body.detail` كـ Fallback للـ Endpoints القديمة.
إذا كانت `body.detail` رسالة تقنية غير إنسانية:
- Feature Layer مسؤولة عن الـ mapping إلى رسالة إنسانية.
- لا DS-FEEDBACK ولا API-MUT يملكان Business Error Map.

---

## FBK-20 — DS-VAL × DS-FEEDBACK — Orchestration Decision Rule

### الإشكالية

DS-VAL VAL-07 يقول: "Network error / Timeout / 5xx → General toast **أو** form-level message".

هذا "أو" قرار غير محسوم — DS-FEEDBACK يحسمه بهذه القاعدة:

### قاعدة التوجيه

```
إذا العملية نشأت في سياق Form (Submit, Form Action):
  → DS-VAL VAL-09 (Form-level banner — يبقى حتى Submit التالي)

إذا العملية نشأت من Action مستقل (زر حذف، نسخ، متابعة، إرسال طلب):
  → DS-FEEDBACK (Snackbar — تختفي تلقائياً)
```

### من يقرر السياق؟

**Feature / Orchestration Layer** — تعرف إذا كانت العملية داخل Form أم لا.

```js
// ✅ مثال orchestration صحيح

// Action مستقل (خارج Form)
async function handleFollowClick() {
  const res = await api('/follow/123', { method: 'POST' })
  const normalized = normalizeErrorResponse(await res.json())
  if (res.ok) {
    showToast('تمت المتابعة', 'success')             // ← DS-FEEDBACK
  } else {
    showToast(normalized.generalError.message, 'error') // ← DS-FEEDBACK
  }
}

// داخل Form Submit
async function handleSaveProfile() {
  const res = await api('/profile/123', { method: 'PATCH', body: ... })
  const normalized = normalizeErrorResponse(await res.json())
  if (res.ok) {
    showToast('تم الحفظ', 'success')                  // ← DS-FEEDBACK (نجاح مناسب)
  } else if (normalized.fieldErrors.length) {
    routeErrors(normalized)                            // ← DS-VAL
  } else {
    showFormError(normalized.generalError.message)     // ← DS-VAL VAL-09
  }
}
```

### حدود الأنظمة

DS-FEEDBACK لا يعرف DS-VAL.
DS-VAL لا يعرف DS-FEEDBACK.
Orchestration تستدعي الاثنين — لا coupling مباشر.

---

## FBK-21 — XSS Security Contract — P0 Runtime Debt

### المشكلة الحالية (P0)

في `tw_shared.js` السطر الحالي:

```js
t.innerHTML = '<span>' + ico + '</span><span>' + msg + '</span>';
```

`msg` يدخل مباشرةً في `innerHTML`. إذا كانت `msg` تحتوي على نص مصدره API أو input خارجي — هذا **XSS Vulnerability نشط**.

### الـ Architecture Contract (إلزامي في Runtime Phase)

```
قاعدة P0: أي نص dynamic داخل DS-FEEDBACK يجب أن يُعيَّن عبر textContent فقط.
ممنوع innerHTML للنص الديناميكي.
```

```js
// ✅ الصحيح في Runtime Phase
const surface = document.createElement('div')
const icoSpan = document.createElement('span')
const msgSpan = document.createElement('span')
icoSpan.setAttribute('aria-hidden', 'true')
icoSpan.textContent = ico         // ← الأيقونة — safe أيضاً
msgSpan.textContent = msg         // ← XSS-safe
surface.appendChild(icoSpan)
surface.appendChild(msgSpan)
```

### الأثر

- لا يُصلَح هذا في Documentation PR الحالي.
- كل مسؤول عن استدعاء `showToast()` يجب أن يُمرِّر رسائل مُصنَّفة لا HTML خام.
- الـ Runtime Fix مُدرَج في FBK-24 (Runtime Debts Catalogue) Priority P0.

---

## FBK-22 — Flutter / Multi-platform Semantics

### المبدأ

**الـ Semantics والـ Contract مشتركان بين المنصات — طريقة الرسم فقط تتفاوت.**

| الـ Concept | Web Implementation | Flutter (مستقبلاً) |
|------------|-------------------|---------------------|
| FeedbackEvent.type | `success/error/warning/info` | نفس القيم |
| FeedbackEvent.message | `string` في Snackbar | `string` في SnackBar widget |
| Duration Policy | `--feedback-duration-*` tokens | Duration في Dart |
| Replace Policy | Latest replaces current | `.currentSnackBar.close()` ثم `showSnackBar()` |
| Accessibility | `role="status" aria-live="polite"` | `Semantics` widget + `LiveRegion` |
| Action Zone V2 | Action Button داخل Snackbar | `SnackBarAction` في Flutter |
| Operation Identity V2 | `operationId` + `updateFeedback()` | `ScaffoldMessenger` key-based |

### لا تربط DS-FEEDBACK بـ `div.tw-toast`

DS-FEEDBACK هو النظام المفاهيمي. `div.tw-toast` هو أحد implementations على Web.

---

## FBK-23 — Migration Inventory (Runtime Audit)

### الأنواع الأربعة للـ Migration

كل استخدام في الكود الحالي يُصنَّف إلى فئة واحدة:

| الفئة | الوصف | الهدف |
|-------|-------|-------|
| **A** | Operational Success/Info — نتيجة عملية مستقلة | DS-FEEDBACK ✅ |
| **B** | General Error خارج Form — فشل عملية مستقلة (بعد normalization) | DS-FEEDBACK ✅ |
| **C** | Field/Form Validation — خطأ مرتبط بحقل أو سياق Form | DS-VAL |
| **D** | محتوى يحتاج عرضاً أطول (قوائم، تأكيدات) | DS-OVL أو Feature UI |

### Audit الملفات الرئيسية

#### `tw_shared.js` — `showToast(msg, type, dur)`

التنفيذ الأساسي والمشترك. الـ callers الأبرز:

| الملف | الاستخدامات | الفئة الغالبة |
|-------|------------|--------------|
| `static/company/company.main.js` | ~63 استدعاء | A + B |
| `settings.html` (local implementation) | ~6 استدعاءات | A + B |
| `profile-v2.*.js` (via `toast()`) | متعدد | A |
| `static/job/job-detail.js` | متعدد | A + B |
| `employees-group.html` | متعدد | A + B |
| `admin.html` / `admin-view.html` | متعدد | A + B |

#### `alert()` — المهاجِر الأول

| الملف | المثال | الفئة |
|-------|--------|-------|
| `company.html:544` | `alert('✅ تم نشر الوظيفة بنجاح')` | **A** → DS-FEEDBACK |
| `company.html:546` | `alert('خطأ في نشر الوظيفة')` | **B** → DS-FEEDBACK |
| `company.html:606` | `alert('خطأ: ' + d.error)` | **B** → DS-FEEDBACK (بعد normalization) |
| `company.html:624` | `alert('المتقدمون: ' + names)` | **D** → يحتاج UI مناسب (Modal أو Toast مختصر) |
| `appointment-room.html:768` | `alert(res.detail \|\| 'خطأ في إرسال الرسالة')` | **B** → DS-FEEDBACK |
| `appointment-room.html:779` | `alert(res.detail \|\| 'خطأ')` | **B** → DS-FEEDBACK |
| `appointment-room.html:829` | `alert('اختر التاريخ والوقت')` | **C** → DS-VAL |
| `appointment-room.html:836` | `alert('رابط المقابلة مطلوب...')` | **C** → DS-VAL |
| `appointments.html:392` | `alert('أدخل رقم طلب التوظيف')` | **C** → DS-VAL |
| `appointments.html:406` | `alert(res.detail \|\| 'خطأ في إنشاء الموعد')` | **B** → DS-FEEDBACK |

#### Local Toast Implementations (مكررة)

| الملف | الـ API | الملاحظة |
|-------|--------|---------|
| `tw_shared.js` | `showToast(msg, type, dur)` | **الأساسي** — يُصلَح ويُعمَّم |
| `profile-v2.utils.js` | `toast(msg)` — `#scToast` existing element | يُهاجَر ليستدعي Canonical API |
| `static/job/job-detail.js` | `showToast(msg, type)` — `#jdToast` + clearTimeout | **أفضل implementation حالي** |
| `profile-v2.completion.js` | `_showToast(msg)` — `#scGrowthToast` private | مختلف معمارياً — يُراجَع في V2 |
| `settings.html` (lines 478+) | `showToast(msg, type, dur)` محلية | تكرار غير ضروري — يُزال ويستخدم `tw_shared.js` |
| Legacy `.toast/#toast` | `home.html` / `index.html` قديمة | Legacy — يُزال بعد migration callers |

### Migration Priority

```
P0 (أمان): إصلاح XSS في tw_shared.js innerHTML → textContent
P1 (صحة): إضافة clearTimeout + aria attributes لـ tw_shared.js
P2 (تنظيف): إزالة alert() Category A+B واستبدالها بـ showToast بعد normalization
P3 (توحيد): دمج settings.html local implementation مع tw_shared.js
P4 (إزالة): إزالة Local implementations بعد انتهاء مستخدميها
```

---

## FBK-24 — Runtime Debts Catalogue

| معرّف | الملف | المشكلة | الأولوية | الحل |
|-------|-------|---------|---------|------|
| **M0** | `tw_shared.js:22` | `t.innerHTML = '<span>'+msg+'</span>'` — XSS | **P0** | `textContent` + DOM construction آمن |
| **M1** | `tw_shared.css` | `bottom: 24px` على Mobile — يغطي Bottom Nav | P1 | `--tw-feedback-bottom: 80px` + media query |
| **M2** | `tw_shared.js` | لا `clearTimeout(_twTimer)` — timer قديم يخفي Feedback أحدث | P1 | إضافة `_twTimer` reference + `clearTimeout` |
| **M3** | `tw_shared.js` | لا `role="status" aria-live="polite" aria-atomic="true"` | P1 | إضافة ARIA attributes عند إنشاء العنصر |
| **M4** | `tw_shared.css` | `left: 50%; transform: translateX(-50%)` بحاجة تحقق RTL | P1 | تأكيد behavior في RTL context |
| **M5** | `tw_shared.css` | `z-index: 9999` hardcoded — ليس Global Layer Token | P2 | استبدال بـ token عند إنشاء Global Layer Tokens |
| **M6** | `tw_shared.css` | `white-space: nowrap` بدون `max-width` | P2 | `max-width: min(90vw, 400px); white-space: normal` |
| **M7** | `tw_shared.css` | لا `warning` type border-color | P2 | إضافة `.warning { border-color: rgba(251,191,36,.3); }` |
| **M8** | `profile-v2.utils.js` | `toast(msg)` — API مختلف، لا type، مدة مختلفة (2200ms) | P2 | يستدعي Canonical API أو يتماشى معه |
| **M9** | `settings.html:478` | Local `showToast` مكررة | P2 | حذف + استخدام `tw_shared.js` |
| **M10** | متعدد | Emoji `✅ ❌ ℹ️` كـ icon — Placeholder | P3 | استبدال بـ Icon System رسمي (DS-ASSET) |
| **M11** | `tw_shared.js` | لا `pointer-events: none` على المستوى الصحيح | P3 | توضيح لا يكسر V2 Action Zone |
| **M12** | `company.html` `appointment-room.html` `appointments.html` | `alert()` Category A+B | P2 | استبدال بـ DS-FEEDBACK |
| **M13** | `appointment-room.html` `appointments.html` | `alert()` Category C — validation | P2 | استبدال بـ DS-VAL |
| **M14** | `company.html:624` | `alert()` لعرض قائمة متقدمين | P3 | Modal أو DS-OVL solution |
| **M15** | متعدد | `showToast(res.detail, 'error')` بدون normalization | P2 | Wrap بـ `normalizeErrorResponse()` |

---

## FBK-25 — Must-Have V1

الـ Runtime المستقبلي لـ DS-FEEDBACK يجب أن يُطبِّق جميع هذه البنود:

| # | المتطلب |
|---|---------|
| 1 | سطح Feedback واحد عالمي لكل صفحة |
| 2 | الأنواع الأربعة: success / error / warning / info |
| 3 | Duration Policy مركزية من DS-FEEDBACK (2800 / 3200 / 4000 / 4500 ms) |
| 4 | Latest Replaces Current — Replace Policy |
| 5 | `clearTimeout` إلزامي قبل timer جديد |
| 6 | `role="status"` + `aria-live="polite"` + `aria-atomic="true"` على جميع الأنواع |
| 7 | `textContent` فقط للرسالة — ممنوع `innerHTML` |
| 8 | `left: 50%; transform: translateX(-50%)` للـ centering |
| 9 | `prefers-reduced-motion` support |
| 10 | لا يسرق Focus |
| 11 | لا يغطي Bottom Navigation أو Composer |
| 12 | Conceptual Level 4 (Global Feedback Band) — placeholder z-index: 9999 مؤقت |
| 13 | CSS Semantic Tokens (`--ac`, `--danger`, `--warning`, `--ac2`) للأنواع |
| 14 | Lifecycle محدد: hidden → entering → visible → exiting → hidden |
| 15 | Stuck State Guard (Timeout Fallback بعد 1000ms إذا animation لم تنتهِ) |
| 16 | `max-width: min(90vw, 400px)` لمنع Overflow على Mobile |
| 17 | لا `white-space: nowrap` بدون `max-width` |
| 18 | Animation RTL-safe (لا تعتمد على `right` أو `left` للـ translate) |
| 19 | `--tw-feedback-bottom` CSS custom property للـ offset المتغير |

---

## FBK-26 — Defer V2+

يُؤجَّل إلى V2 أو أبعد:

| المؤجَّل | السبب |
|----------|-------|
| Operation Identity Runtime (`updateFeedback(id, opts)`) | يتطلب API Change + تنسيق مع Feature layer |
| Action Zone Runtime (Undo / Retry) | يتطلب `pointer-events: auto` + Action Contract كامل |
| Stack/Queue متعدد | غير ضروري V1 — Replacement يكفي |
| Loading State داخل Snackbar | Loading يبقى في الزر/Component V1 |
| `critical: true` + `role="alert"` / `aria-live="assertive"` | نادر الاستخدام V1 |
| Global Layer Tokens (رقم z-index نهائي) | ينتظر بناء Global Layer System |
| DS-ASSET Icon System (SVG icons للـ Feedback) | ينتظر توثيق DS-ASSET |
| Rich message (icon + title + description) | Snackbar يبقى compact في V1 |
| `env(keyboard-inset-bottom)` | لا دعم كافٍ في المتصفحات بعد |
| History/Log للرسائل السابقة | لا حاجة واقعية |
| Multi-line animated messages | تبسيط V1 |
| Error Map مشترك (Business Error Dictionary) | يبقى في Feature Layer |

---

## FBK-27 — Forbidden Patterns

```
❌ إنشاء Feedback engine محلي داخل صفحة بدلاً من استخدام النظام المشترك
❌ أكثر من Global Feedback Surface واحدة في V1
❌ Stack / Queue عشوائية في V1
❌ t.innerHTML = msg  أو  innerHTML = '<span>' + msg + ...  — XSS مباشر
❌ Raw Backend data وصل مباشرة: showToast(res.detail, 'error')
❌ showToast لأخطاء حقول محددة — DS-VAL VAL-08 هو المالك
❌ showToast بديلاً عن Form-level banner ضمن Form context — DS-VAL VAL-09
❌ alert() لنجاح عملية عادية
❌ alert() كـ Field/Form Validation feedback
❌ window.confirm() في أي code — DS-OVL OVL-27
❌ dur > 8000ms كـ Loading workaround — Loading يبقى في الزر
❌ Loading indicator طويل داخل Snackbar V1
❌ hardcoded z-index في Feature code للـ Feedback — يجب استهلاك Layer Token
❌ اعتبار 9999 Architecture Token — هو placeholder مؤقت فقط
❌ hardcoded bottom offset ثابت كعقد عالمي — يجب استخدام --tw-feedback-bottom
❌ Snackbar تغطي Bottom Navigation أو Message Composer
❌ DS-FEEDBACK يسرق Focus عند الظهور
❌ role="alert" / aria-live="assertive" تلقائياً على كل Error في V1
❌ Emoji كـ Icon Contract نهائي — هي Placeholder فقط
❌ ألوان warning محلية hardcoded — استخدم var(--warning)
❌ Navigation فوري (twNavigate) مباشرة بعد showToast بدون تنسيق
❌ timer قديم يخفي Feedback أحدث — clearTimeout إلزامي
❌ DS-FEEDBACK يتحول إلى Notification Bell System (🔔)
❌ DS-FEEDBACK يتحول إلى DS-VAL للـ Field Errors
❌ DS-FEEDBACK يتحول إلى Modal/Confirmation system
❌ coupling مباشر بين DS-FEEDBACK وDS-VAL (Orchestration فقط)
❌ DS-FEEDBACK يُرسَل قيمة null أو undefined كـ message
❌ pointer-events: none كـ Architecture Contract ثابت على كامل الـ Surface
❌ `showToast()` داخل `twNavigate()` callback أو بعده مباشرةً
❌ استدعاء `showToast` من كود غير JS (CSS counter، template literal في HTML)
❌ Duration مختلفة لنفس النوع في صفحات مختلفة — Duration Policy مركزية
```

---

## FBK-28 — Runtime Direction (Non-binding)

> **هذا القسم غير مُلزِم.** يصف اتجاهاً مقترحاً للـ Runtime phase عند طلبه. لا تُنشئ أي Runtime file قبل موافقة صريحة.

### الملف المقترح: `tw_shared.js` (تحديث — لا ملف جديد)

DS-FEEDBACK V1 Runtime يُطبَّق **بتحسين `tw_shared.js` الموجود** — لا بإنشاء `tw-feedback.js` منفصل.

`showToast(msg, type, dur)` هو المدخل الوحيد في V1. `dur` يُتجاهَل إذا كانت Duration Policy مركزية (`dur` للـ backward compat فقط).

### نمط منشئ العنصر الآمن

```js
// نمط V1 Runtime المقترح
var _twTimer = null;
var _twSurface = null;

var FBK_DURATION = { success: 2800, info: 3200, warning: 4000, error: 4500 };

function showToast(msg, type, _legacyDur) {
  type = type || 'success';
  var dur = FBK_DURATION[type] || FBK_DURATION.success;

  clearTimeout(_twTimer);           // إلغاء timer القديم
  if (_twSurface) _twSurface.remove();

  var surface = document.createElement('div');
  surface.setAttribute('role', 'status');
  surface.setAttribute('aria-live', 'polite');
  surface.setAttribute('aria-atomic', 'true');
  surface.className = 'tw-snackbar ' + type;

  var msgSpan = document.createElement('span');
  msgSpan.textContent = msg;        // XSS-safe
  surface.appendChild(msgSpan);

  document.body.appendChild(surface);
  _twSurface = surface;

  requestAnimationFrame(function() {
    requestAnimationFrame(function() {
      surface.classList.add('show');
    });
  });

  _twTimer = setTimeout(function() {
    surface.classList.remove('show');
    setTimeout(function() {
      if (surface.parentNode) surface.remove();
    }, 350);
  }, dur);
}
window.showToast = showToast;
```

### نمط الـ CSS (V1)

```css
.tw-snackbar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%) translateY(20px);
  bottom: var(--tw-feedback-bottom, 24px);
  opacity: 0;
  background: rgba(7,11,24,.97);
  border: 1px solid var(--bdr);
  border-radius: 14px;
  padding: 10px 16px;
  font-size: .78rem;
  font-weight: 700;
  font-family: 'Cairo', sans-serif;
  z-index: 9999;  /* placeholder — سيُستبدَل بـ Global Layer Token */
  transition: opacity .3s, transform .3s;
  pointer-events: none;   /* Message Body — V1 */
  max-width: min(90vw, 400px);
  white-space: normal;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tw-snackbar.show {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.tw-snackbar.success { border-color: rgba(0,200,150,.3); }
.tw-snackbar.error   { border-color: rgba(248,113,113,.3); }
.tw-snackbar.warning { border-color: rgba(251,191,36,.3); }
.tw-snackbar.info    { border-color: rgba(37,99,255,.3); }

@media (prefers-reduced-motion: reduce) {
  .tw-snackbar { transition-duration: 0.01ms !important; }
}

@media (min-width: 600px) {
  .tw-snackbar { bottom: 24px; }
}
```

---

## FBK-29 — خارج النطاق — V1

الأنظمة التالية ليست DS-FEEDBACK:

| النوع | النظام المناسب |
|-------|--------------|
| خطأ حقل محدد في Form | DS-VAL → VAL-08 |
| Form-level error banner | DS-VAL → VAL-09 |
| تأكيد حذف / تأكيد قرار | DS-OVL → OVL-27 |
| Tooltip / Popover | غير موثَّق بعد (راجع OVL-37) |
| Banner دائم / Alert ثابت | Feature Layout — خارج DS-FEEDBACK |
| Notification 🔔 مستمرة | Notifications System `ARCHITECTURE.md §19` |
| رسالة Messenger | Messenger System `ARCHITECTURE.md §18` |
| Loading indicator | DS-BTN / Component |
| Progress Bar | Upload Component / Feature |
| Alert Browser Native | `window.alert()` — ممنوع في F33 + FBK-27 |
| `window.confirm()` | ممنوع في F33 / DS-OVL — استخدم DS-OVL OVL-27 |
| خطأ تقني خام من Backend | API-MUT-11 (normalization) — ليس DS-FEEDBACK |

---

*أُنشئ في PR docs/ds-feedback-v1 — 2026-07-24 — [DS-FEEDBACK] Operational Feedback System V1 Architecture Contract (FBK-00 → FBK-29، 30 قسماً). Single Global Surface. 4 Types (success/error/warning/info). Duration Policy مركزية. Lifecycle محدد. Mobile Behavior Contract. RTL Centering. Layer Architecture (Level 4). Accessibility V1 (role=status + polite). Operation Identity V1 Policy + V2 Concept. Action Zone V2 Concept. XSS P0 Runtime Debt. Error Normalization Ownership. DS-VAL Boundary + Orchestration Decision Rule. Flutter Platform-neutral Semantics. Migration Inventory (6 implementations + alert() audit). Runtime Debts Catalogue (16 items). Must-Have V1 (19 items). Forbidden Patterns (30+). ARCHITECTURE_FOUNDATION.md + docs/DESIGN_SYSTEM.md + docs/SYSTEMS_INDEX.md مُحدَّثة في نفس الـ PR.*
