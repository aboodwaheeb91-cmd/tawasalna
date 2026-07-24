# [DS-OVL] Overlay System — V1

> **الـ contract المعماري الرسمي للـ Overlays في منصة تواصلنا**
>
> V1 — توثيق فقط · لا يمس أي Runtime code.
> المرجع الرسمي للـ AI sessions والمطورين عند كل مهمة تخص الـ Overlays والـ Modals والـ Drawers والـ Sheets.
>
> **الـ Runtime الحالي:** غير مُنفَّذ بعد — هذا Contract مرجعي.
> اقرأ OVL-36 (Runtime Direction) لمعرفة الاتجاه المخطط له.

---

## جدول المحتويات

| القسم | العنوان |
|-------|---------|
| OVL-00 | Routing Protocol — متى تقرأ هذا الملف |
| OVL-01 | الغرض والنطاق |
| OVL-02 | النموذج المتعامد (Orthogonal Model) — نظرة عامة |
| OVL-03 | محور Modality |
| OVL-04 | محور Presentation |
| OVL-05 | محور Semantics |
| OVL-06 | محور Close Policy |
| OVL-07 | دورة الحياة (Lifecycle) |
| OVL-08 | إدارة الـ Stack (Layer Management) |
| OVL-09 | عقد Parent/Child |
| OVL-10 | الهوية ومنع التكرار (Identity & Duplicate Policy) |
| OVL-11 | Close Intent وClose Reasons |
| OVL-12 | عقد Close Guard (عام) |
| OVL-13 | مفهوم النتيجة (Result Concept — V1 Conceptual) |
| OVL-14 | معمارية الطبقات (Layer Architecture) |
| OVL-15 | تكامل DS-SEL — Layer Context |
| OVL-16 | تكامل DS-NAV |
| OVL-17 | عقد Focus (تركيز لوحة المفاتيح) |
| OVL-18 | عزل الخلفية (Background Isolation) |
| OVL-19 | عقد Scroll Lock |
| OVL-20 | عقد Backdrop |
| OVL-21 | Surface Slot Contract |
| OVL-22 | Responsive Strategy Presets |
| OVL-23 | Mobile Contract |
| OVL-24 | Animation Strategy |
| OVL-25 | Size Strategy |
| OVL-26 | Accessibility — V1 |
| OVL-27 | Confirmation Contract |
| OVL-28 | DS-OVL × DS-FRM — حدود المسؤولية |
| OVL-29 | Migration Strategy |
| OVL-30 | Ownership Matrix |
| OVL-31 | Must-Have V1 |
| OVL-32 | Nice-to-Have |
| OVL-33 | Defer |
| OVL-34 | Forbidden Patterns |
| OVL-35 | الأمان والصلاحيات (Security & Permission Separation) |
| OVL-36 | Runtime Direction (Non-binding) |
| OVL-37 | خارج النطاق — V1 |

---

## OVL-00 — Routing Protocol

**قبل كتابة أي كود يخص Modal أو Drawer أو Sheet أو Overlay أو Confirmation، تحقق من هذا الجدول أولاً:**

| المهمة | الأقسام |
|--------|---------|
| بناء أي Overlay جديد | OVL-00 → OVL-02 → OVL-03 إلى OVL-06 → OVL-07 → OVL-09 → OVL-17 → OVL-18 → OVL-26 |
| Confirmation dialog / حوار تأكيد | OVL-05 → OVL-06 → OVL-27 → OVL-17 → OVL-26 |
| Close Guard / حماية من الإغلاق العرضي | OVL-11 → OVL-12 → OVL-28 |
| Nested Overlay / Overlay داخل Overlay | OVL-08 → OVL-09 |
| Responsive behavior / تكيف الشاشات | OVL-22 → OVL-23 |
| DS-SEL (dropdown) داخل Overlay | OVL-15 |
| Back button / سلوك الرجوع | OVL-16 |
| Focus management | OVL-17 |
| Scroll lock أو body overflow | OVL-19 |
| Animation / حركة | OVL-24 |
| حجم Overlay / dimensions | OVL-25 |
| Legacy overlay موجود يحتاج مراجعة | OVL-29 |
| Forbidden patterns / ما لا يُفعل | OVL-34 |
| من يملك ماذا؟ | OVL-30 |
| الحالة الراهنة للـ Runtime | OVL-36 |

**إذا المهمة تخص:**
- Tooltip, Popover, Floating label → **STOP** — ليست DS-OVL → راجع OVL-37
- Select/Dropdown/Picker → DS-SEL → `SELECT-PICKER.md` (SEL-00 أولاً)
- Toast/Snackbar/Banner → DS-FEEDBACK → **STOP — غير موثَّق بعد**
- Accessibility فقط لعنصر ثابت → DS-INP أو DS-BTN

---

## OVL-01 — الغرض والنطاق

### ما الذي يملكه DS-OVL؟

DS-OVL هو النظام الموحد الرسمي لإدارة كل الـ Overlays في منصة تواصلنا. **Overlay** هو أي طبقة تُفتح فوق محتوى الصفحة وتتطلب إدارة مركزية للـ Stack والـ Focus والـ Lifecycle.

يملك DS-OVL:
- Stack إدارة Layer
- Lifecycle كامل (opening → open → closing)
- Focus Management (containment + restoration)
- Background Isolation (منع تفاعل الخلفية)
- Scroll Lock (مركزي ومُرجَّح بالعد Reference Counting)
- Escape Intent routing
- Backdrop semantics
- Close Guard Contract (عام، بلا معرفة business domain)
- DS-NAV integration (تسجيل طبقة — لا امتلاك Back Intent)
- DS-SEL Layer Context (إنتاج Context — لا معرفة DS-SEL مباشرة)
- Responsive Strategy Presets
- Accessibility

### ما الذي لا يملكه DS-OVL؟

- **Navigation Back Intent** — DS-NAV يملكه
- **Form dirty state** — DS-FRM يملكه
- **Business logic الإغلاق** — Feature/Integration Layer تملكه
- **Toast/Feedback** — DS-FEEDBACK (غير موثَّق بعد)
- **Select/Dropdown rendering** — DS-SEL يملكه
- **Authorization** — Backend يملكه
- **UI Visibility (trigger)** — DS-VM يملكه
- **Z-index لـ Toast أو Skip Links** — Design Tokens + أنظمة مستقلة

### النطاق الجغرافي

Web أولاً (HTML/CSS/JS vanilla). Contract مصمم ليكون behavior-neutral قدر الإمكان لدعم Flutter مستقبلاً (F1).

---

## OVL-02 — النموذج المتعامد (Orthogonal Model)

DS-OVL يصف كل Overlay بأربعة محاور **مستقلة** — كل محور له قيمه الخاصة، وكل تركيبة منطقية ممكنة دون اختراع Engine جديد.

```
Overlay = Modality × Presentation × Semantics × Close Policy
```

**المحاور الأربعة:**

| المحور | السؤال | القيم |
|--------|--------|-------|
| Modality | كيف تتعامل مع الخلفية؟ | `blocking` (V1 فقط) |
| Presentation | كيف تبدو؟ | `center` / `side` / `bottom` / `fullscreen` |
| Semantics | ما الغرض؟ | `standard` / `confirmation` |
| Close Policy | من يُغلقها وكيف؟ | `dismissible` / `guarded` / `locked` |

**أمثلة:**

| المثال | Modality | Presentation | Semantics | Close Policy |
|--------|----------|-------------|-----------|-------------|
| تعديل بيانات الشركة | blocking | side | standard | guarded |
| حوار تأكيد الحذف | blocking | center | confirmation | locked |
| عرض صورة كاملة | blocking | fullscreen | standard | dismissible |
| اختيار تصنيف مرشح | blocking | bottom | standard | dismissible |
| تأكيد إلغاء الموعد | blocking | center | confirmation | guarded |

**القاعدة الحاسمة:**
لا تُنشئ Giant Enum من كل التركيبات. لا تُضف نوع `confirm-center` أو `edit-drawer` كـ flat type. الأربعة محاور مستقلة دائماً.

---

## OVL-03 — محور Modality

**تعريف:** كيف تتعامل الـ Overlay مع ما وراءها؟

### القيم المدعومة في V1

**`blocking`** (الوحيد في V1)
- الخلفية غير قابلة للتفاعل بالكامل (pointer + keyboard + screen reader)
- DS-OVL يُطبق Background Isolation فوراً عند opening state
- Scroll Lock يبدأ مع opening state

### مؤجل (ليس V1)

**`non-blocking`** — Overlay مرئية لكن الخلفية تبقى تفاعلية جزئياً (نوافذ حوار ثانوية، sidebars توضيحية). يُضاف في PR مستقل بمبرر.

### ملاحظة معمارية

Contract لا يمنع إضافة Modality جديدة مستقبلاً بدون كسر الـ Overlays الموجودة.

---

## OVL-04 — محور Presentation

**تعريف:** الشكل البصري للـ Surface. Presentation لا تُحدد Priority في الـ Stack ولا تُحدد Close Policy.

### القيم الأربعة في V1

**`center`**
Surface معلقة في وسط الـ viewport.
مناسب لـ: Confirmation, Quick forms, Pickers.

**`side`**
Surface تدخل من الجانب.
في RTL (العربية): تدخل من اليمين.
مناسب لـ: Edit forms, Detail panels, Long workflows.

**`bottom`**
Surface تصعد من الأسفل.
مناسب لـ: Quick selection, Mobile-first actions, Context menus.

**`fullscreen`**
Surface تغطي كامل الـ viewport.
مناسب لـ: Image viewers, Complete workflows, Critical flows on mobile.

### قاعدة مهمة

Presentation تصف الشكل فقط. Confirmation ليست Presentation — هي Semantics (OVL-05). يمكن دمج `confirmation` مع أي Presentation مناسب.

---

## OVL-05 — محور Semantics

**تعريف:** الغرض أو المعنى الدلالي للـ Overlay. يؤثر على Focus Policy الافتراضية وقواعد Accessibility.

### القيم في V1

**`standard`**
محتوى عادي: forms, views, lists, pickers, editors.
- Initial Focus الافتراضي: `surface-heading` (راجع OVL-17)
- ARIA role: `dialog` + `aria-modal="true"`

**`confirmation`**
طلب تأكيد قرار من المستخدم.
- Initial Focus الافتراضي: `safe-action` (راجع OVL-17)
- يختار Feature المناسب بين `role="dialog"` و`role="alertdialog"` — راجع OVL-27

### قاعدة حاسمة

`confirmation` هي Semantics، ليست Presentation.
يمكن بناء Confirmation بأي Presentation:
```
confirmation + center     ← الأكثر شيوعاً
confirmation + bottom     ← ممكن مستقبلاً بدون Engine جديد
```

لا تُنشئ "confirmation" كـ Presentation type. الـ orthogonal model يُحل هذا تلقائياً.

---

## OVL-06 — محور Close Policy

**تعريف:** من يُسمح له بطلب الإغلاق وكيف.

**لا يوجد default عالمي** — كل Feature تُحدد Close Policy مناسبة.

### القيم الثلاثة

**`dismissible`**
Close Intent (backdrop / Escape / close button / back) يُغلق الـ Overlay مباشرة دون سؤال.
مناسب لـ: Image viewers, Info panels, Quick pickers.

**`guarded`**
أي Close Intent يمر عبر Close Guard أولاً.
Guard تقرر: `allow` أو `block` أو `require-confirmation`.
مناسب لـ: Edit forms, Long workflows, Anything with unsaved state.

**`locked`**
بعض أو كل Close Intents محظورة. Feature/System تُحدد مسارات الإغلاق المتاحة صراحةً.
مناسب لـ: Blocking processes, Mandatory confirmations, Critical system dialogs.

### Cross-reference

- Close Guard implementation → OVL-12
- Close Reasons (من أين جاء الإغلاق؟) → OVL-11

---

## OVL-07 — دورة الحياة (Lifecycle)

### حالات Overlay

```
closed → opening → open → closing → closed
```

### تفاصيل كل حالة

**`closed`**
Overlay غير موجودة في الـ Stack. لا DOM (أو DOM مُخفي خارج Stack).

**`opening`**
- Overlay دخلت الـ Stack
- Background Isolation تُطبَّق فوراً (لا تنتظر اكتمال Animation)
- Scroll Lock يبدأ فوراً
- Enter animation تعمل
- Focus ينتقل إلى Overlay (حسب Initial Focus Policy — OVL-17)

**`open`**
- Animation اكتملت
- Overlay نشطة ومتفاعلة
- Focus محجوز داخل Overlay (containment نشط)
- Background Isolation فعالة

**`closing`**
- Close Intent استُقبل وسُمح به (Guard أجازته أو Policy = dismissible)
- Exit animation تعمل
- **Background Isolation تبقى فعالة** — الخلفية ما زالت غير تفاعلية
- **Focus ownership تبقى داخل Overlay** — ما زالت Top Layer بصرياً
- Timeout Fallback نشط (راجع الجزء أدناه)

**`closed` (بعد الإغلاق)**
- Exit animation انتهت (أو Timeout انتهى)
- Overlay تُزال من الـ Stack
- يُعاد حساب Top Active Layer
- Background Isolation تُرفع للطبقة الجديدة
- Focus يُعاد حسب Restore Policy (OVL-17)

### قاعدة حاسمة: Isolation خلال Closing

```
❌ غلط: closing → رفع inert/isolation → animation → إزالة DOM
✅ صح:  closing → animation تعمل → isolation فعالة طوال animation → اكتمال animation → رفع isolation → إزالة
```

### Timeout Fallback

Lifecycle لا تعتمد `animationend` event وحده.
Timeout (مثلاً animation-duration + هامش آمن) يُنهي `closing` state بأمان إذا:
- الـ event لم يصل
- الـ animation عُطِّلت بـ `prefers-reduced-motion`
- مشكلة في CSS

هذا يمنع stuck state حيث Overlay تبقى في `closing` إلى الأبد.

---

## OVL-08 — إدارة الـ Stack (Layer Management)

### مفهوم الـ Stack

DS-OVL يدير **Stack مرتبة** من الـ Overlays النشطة.
**آخر layer مُفتوحة = Top Active Layer**.

### Top Active Layer

- تستقبل Escape Intent وBackdrop Click وBack Intent (عبر DS-NAV)
- تملك Focus containment
- صاحبة Backdrop interaction

### فتح Layer جديدة

عند فتح Overlay وهناك Overlay أخرى مفتوحة:
- الجديدة تُضاف فوق الـ Stack
- الجديدة تصبح Top Active Layer
- السابقة تُصبح Parent وتفقد Top status
- Parent تستقبل `onLayerDeactivate` signal
- DS-SEL المفتوحة داخل Parent تُغلق (راجع OVL-15)

### إغلاق Layer

عند إغلاق Top Layer:
- تُزال من الـ Stack (بعد اكتمال exit animation)
- Parent (إن وجدت) تستعيد Top Active status
- Parent تستقبل `onLayerActivate` signal
- Focus يعود للـ Parent (راجع OVL-17 → Restore Chain)

---

## OVL-09 — عقد Parent/Child

### التعريف

Overlay B تُفتح بينما Overlay A مفتوحة → A = Parent، B = Child.

الوضع الطبيعي المعتمد: **مستويان** (Parent + Child واحد).
أكثر من مستويين يحتاج مبرراً واضحاً (استثناء، لا نمط معتاد).

### القواعد السبع

**1. Parent Relation معروف دائماً**
كل Child يُعرف من فتحه (Parent identity في الـ Stack).

**2. Top Active Layer فقط**
Back، Escape، Backdrop تصل للـ Top Layer فقط.
لا تمر مباشرة للـ Parent.

**3. Child Close → Parent Active**
عند إغلاق Child:
- Parent تستعيد Top Active status
- الخلفية العامة لا تصبح interactive
- Focus يعود للـ Parent (حسب Restore Policy)

**4. Parent Cascade**
Parent لا تُغلق مباشرة بينما Child موجود.
إذا طلب النظام إغلاق Parent:
- Child يُغلق أولاً (cascade controlled)
- ثم Parent تُغلق

**5. Focus Ownership**
بينما Child مفتوح:
- Focus محجوز داخل Child
- Child لا يُعيد Focus للصفحة العامة عند إغلاقه
- يُعيده للـ Parent (Restore Chain يبدأ من Parent target)

**6. Parent's Surface = Background**
من منظور Child، surface الـ Parent تُعامل كخلفية (غير تفاعلية).

**7. DS-SEL داخل Parent**
عند فتح Child، Parent تفقد Top status → `onLayerDeactivate` → DS-SEL المفتوح في Parent يُغلق.
عند إغلاق Child، Parent تستعيد Top → `onLayerActivate`.

---

## OVL-10 — الهوية ومنع التكرار (Identity & Duplicate Policy)

### Identity Contract

كل Overlay لها **Logical Identity** تُحدد سلوك DS-OVL تجاه تكرارها.

**أنواع Identity:**

**Singleton**
Overlay واحدة فقط ممكنة في أي وقت.
مثال: Edit Profile Drawer، Followers Modal.
إذا طُلب فتحها وهي موجودة → no-op أو reference لـ existing instance.

**Entity-keyed**
Overlay مرتبطة بكيان محدد. مثال: Candidate Drawer لمرشح ID=42.
Identity = `type + entity_id`.
نفس الكيان → no-op/reference. كيان مختلف → مختلف.

**Transient**
كل فتح يُنشئ instance جديدة (لا conflict check).
مثال: Confirmation dialogs، Alert dialogs.

### Duplicate Policy

نفس Logical Identity لا تُفتح مرتين بدون مبرر صريح:
- لا تُنشئ duplicate طبقات
- لا blind `bringToTop` يكسر Parent/Child stack
- Identity تُحددها Feature صراحةً — DS-OVL لا يُخمنها

### ملاحظة مهمة

Presentation نفسها لكيانات مختلفة = Overlays مختلفة، ليست duplicates.
مثال: Drawer لـ Candidate A ≠ Drawer لـ Candidate B.

---

## OVL-11 — Close Intent وClose Reasons

### Close Intent

الإشارة الواردة التي تطلب إغلاق Overlay.
DS-OVL يُوجِّه Close Intent للـ Top Active Layer فقط.

**مصادر Close Intent:**

| السبب | المصدر |
|-------|--------|
| `close-button` | زر × أو رابط إلغاء صريح |
| `cancel` | زر Cancel واضح |
| `escape` | مفتاح Escape |
| `backdrop` | النقر على الخلفية الداكنة |
| `back` | Browser Back / Android Back (عبر DS-NAV) |
| `save-success` | حفظ ناجح أنهى الـ Overlay |
| `parent-close` | Cascade من Parent Overlay |
| `system` | استدعاء برمجي داخلي |

### Force-Close

ليست Close Reason عامة متاحة لـ Features.
هي Internal/System-controlled capability للحالات القصوى (session expiry، navigation إجباري، error recovery).
Feature عادية لا تستخدم Force-Close لتجاوز Guard.

### Close Reason = Must-Have V1

كل إغلاق يحمل Close Reason.
Reason تُمرَّر للـ Close Guard (OVL-12) وللـ Result (OVL-13).

---

## OVL-12 — عقد Close Guard (عام)

### المبدأ

DS-OVL يوفر Close Guard Contract — واجهة عامة لا تعرف business domain.

Feature/Integration Layer هي التي تستشير:
- DS-FRM (هل الـ Form dirty؟)
- Upload Manager (هل رفع ملف جاري؟)
- أي نظام آخر يملك state

### Contract (Pseudocode — غير ملزم بأسماء)

```
// عند استقبال Close Intent على Overlay ذات Close Policy = guarded أو locked
beforeClose(reason: CloseReason) → CloseDecision

CloseDecision:
  | allow                        ← أكمل الإغلاق
  | block(reason?)               ← ارفض، أبلغ المستخدم اختيارياً
  | require-confirmation(spec)   ← اطلب تأكيداً قبل الإغلاق
```

### قواعد Close Guard

1. Guard يُفعَّل فقط على Policy = `guarded` أو `locked`
2. DS-OVL لا تعرف سبب الـ Guard (dirty form، upload، workflow) — تسأل Feature فقط
3. DS-OVL لا تستدعي DS-FRM مباشرة — لا dependency مباشر
4. DS-OVL لا تُعيد تعيين (reset) أي state عند الإغلاق — ذلك من مسؤولية Feature
5. Force-close يتجاوز Guard — لكنه ليس Close Reason عادية (راجع OVL-11)

---

## OVL-13 — مفهوم النتيجة (Result Concept — V1 Conceptual)

### المفهوم

Overlay يمكن أن تنتهي بنتيجة معنوية يستخدمها Feature الذي فتحها.

### النتائج الممكنة (V1 Conceptual)

| النتيجة | المعنى |
|---------|--------|
| `confirmed` | المستخدم أكد الإجراء |
| `cancelled` | المستخدم ألغى صراحةً |
| `dismissed` | أُغلق بدون قرار صريح (backdrop, escape) |
| `saved` | حفظ ناجح أنهى الـ Overlay |
| custom | نتيجة تُحددها Feature حسب حاجتها |

### الوضع الراهن

- Result Concept يدخل V1 كمفهوم رسمي
- Runtime API (مثل `open().then(result => ...)` أو Callback signature) مؤجل لمرحلة التنفيذ
- DS-OVL يُمرر Result عبر callback/event عند الإغلاق — الآلية الدقيقة تُحسم في Runtime phase

---

## OVL-14 — معمارية الطبقات (Layer Architecture)

### Layer Bands (Conceptual — لا أرقام z-index نهائية الآن)

```
Conceptual Level 0: Base Page Content
Conceptual Level 1: Sticky / Floating Page UI (headers, sidebars, FABs)
Conceptual Level 2: Overlay Stack Band     ← DS-OVL يملك هذا
Conceptual Level 3: Overlay-local Floating ← DS-SEL dropdown داخل Overlay
Conceptual Level 4: Global Feedback Band   ← Toast, Tooltip (DS-FEEDBACK — غير موثَّق بعد)
Conceptual Level 5: Accessibility Layer    ← Skip links, Critical dialogs
```

أرقام z-index الفعلية تُحدد في Global Layer Tokens (لم تُنشأ بعد). DS-OVL يستهلك band الخاص به فقط.

### مبدأ الترتيب

**لا type-based ordering:**
- Confirmation ليست دائماً فوق Modal بسبب اسمها
- Fullscreen ليست دائماً فوق Drawer

**الترتيب الفعلي = Stack depth:**
الطبقة التي فُتحت أخيراً تكون في الأعلى.
Parent/Child relation والوقت هما اللذان يحكمان — ليس Presentation name.

### DS-OVL × Design Tokens

DS-OVL لا يملك z-index لـ:
- Toast/Snackbar → DS-FEEDBACK
- Tooltip → نظام منفصل
- Skip Links → Accessibility Layer
- DS-SEL dropdown → Overlay-local Floating (OVL-15)

Global Layer System يُوزِّع Bands. DS-OVL يُحدد تخصيصاته فقط داخل band الـ Overlay.

---

## OVL-15 — تكامل DS-SEL — Layer Context

### المشكلة الحالية (Runtime Debt)

`tw-select.js` حالياً يراقب `.ep-overlay, .sc-modal-overlay` بأسماء CSS محددة عبر MutationObserver، ويستخدم `z-index: 9500` كـ hack عالمي.

هذا يعني:
- أي تغيير في أسماء CSS classes يكسر DS-SEL
- لا Layer Context حقيقي — مجرد z-index سحري
- Dropdowns قد تبقى orphan عند إغلاق Overlay

### الحل المعماري: Layer Context

DS-OVL يُنتج **Layer Context** لكل Overlay.
DS-SEL تستهلك هذا Context عند تهيئتها داخل Overlay.

### Layer Context — Architecture Contract

```
// Architecture Contract — لا تثبيت لأسماء API بعد
LayerContext [Conceptual]:

  layerId              — هوية فريدة للـ Layer في الـ Stack

  floatingZone         — Zone/Container للعناصر الطائرة المحلية لهذه Layer
                         (Portal target — ليس document.body مباشرة)
                         تُتيح Dropdown أن تظهر فوق Surface الأب
                         وتحت Child Overlay التي فُتحت لاحقاً

  floatingZAllocation  — Z-ordering داخل floatingZone
                         مشتق من Global Layer Tokens
                         لا magic number مستقل

  isActive()           — هل هذه الـ Layer هي Top Active Layer الآن؟

  onLayerClose(cb)     — اشترك في "بدأ الإغلاق"
                         يُطلَق عند دخول closing state (قبل اكتمال animation)
                         يعيد دالة unsubscribe

  onLayerDeactivate(cb) — اشترك في "فقدت Top Active status"
                          يُطلَق عند فتح Child Overlay فوق هذه Layer
                          يعيد دالة unsubscribe

  onLayerActivate(cb)  — اشترك في "استعادت Top Active status"
                         يُطلَق عند إغلاق Child Overlay
                         يعيد دالة unsubscribe
```

### قواعد Layer Context

1. **DS-SEL لا تستعلم DS-OVL عالمياً**
   DS-SEL لا تعرف DS-OVL ولا تستدعيه مباشرة.
   DS-SEL تعتمد فقط على Layer Context interface الذي تستقبله.

2. **Binding mechanism = Runtime detail**
   كيف تصل LayerContext لـ DS-SEL (explicit parameter، data attribute، registration event) — يُحسم في Runtime phase. لا نثبته الآن.

3. **Layer Context اختياري لـ DS-SEL**
   Selects خارج Overlays (على الصفحة العادية) لا تملك LayerContext.
   DS-SEL تعمل بكلا الحالتين:
   - **مع LayerContext**: Portal للـ floatingZone، z-order من floatingZAllocation
   - **بدون LayerContext (page-level)**: Portal لـ document.body، z-index من Global Layer Tokens

   هذا يضمن Migration تدريجي — Selects غير المُحدَّثة تبقى تعمل بالطريقة القديمة.

4. **سيناريو Child Overlay**
   - Parent مفتوحة، Select Dropdown مفتوح داخلها
   - Child Overlay تُفتح فوق Parent
   - Parent تستقبل `onLayerDeactivate`
   - DS-SEL يُغلق Dropdown المفتوح فوراً
   - Child تصبح Top Active Layer

5. **سيناريو الإغلاق**
   - Overlay تدخل closing state
   - `onLayerClose` يُطلَق فوراً (قبل اكتمال animation)
   - DS-SEL يُنظِّف event listeners
   - floatingZone يُزال من DOM بعد اكتمال animation

6. **floatingZAllocation من Global Layer Tokens لا من magic numbers**
   DS-SEL لا تحتاج z-index 9500. تحصل على z-order مناسب داخل floatingZone من خلال LayerContext.

### تأثير على SELECT-PICKER.md

SEL-25 (Portal Contract) يجب أن يُحدَّث في PR مستقل ليرجع إلى Layer Context بدلاً من `--tw-drop-z` المستقل. يُنفَّذ هذا التحديث عند بدء تنفيذ DS-OVL Runtime.

---

## OVL-16 — تكامل DS-NAV

### المبدأ

**DS-NAV هو المالك الوحيد للـ Navigation Back Intent.**

DS-OVL لا تُنشئ History system موازياً.
DS-OVL لا تستدعي `history.pushState` مباشرة.

### دور DS-OVL

- DS-OVL تُسجِّل Layer مع DS-NAV عند opening (تُزوِّده بـ Close capability)
- DS-OVL تُلغي التسجيل عند closing

### Escape vs Back

| الإشارة | المصدر | الـ Router |
|---------|--------|-----------|
| Escape | Interaction intent | DS-OVL معالجة مباشرة |
| Back | Navigation intent | DS-NAV → ثم DS-OVL |

كلاهما ينتج Close Intent للـ Top Active Layer بنفس Close Intent contract، لكن مصدر الـ routing مختلف.

### الديون الراهنة (Migration)

`company.main.js` يملك Dual popstate listeners (lines 1975, 4624) — موثقة في NAVIGATION.md كـ debt.
DS-OVL Contract يمنع حدوث هذا النمط في overlays جديدة.

---

## OVL-17 — عقد Focus (تركيز لوحة المفاتيح)

### ١. Initial Focus Policy

عند opening overlay، DS-OVL ينقل Focus حسب Strategy.

**Default بحسب Semantics:**

| Semantics | Default Strategy |
|-----------|-----------------|
| `standard` | `surface-heading` |
| `confirmation` | `safe-action` |

Feature تستطيع Override صراحةً بأي Strategy.

**Strategies المتاحة:**

| Strategy | الوصف | مناسب لـ |
|----------|--------|----------|
| `surface-heading` | أول heading/title صالح في Surface | Forms طويلة, Drawers, Views |
| `first-logical-field` | أول input منطقي | Forms قصيرة بسيطة |
| `safe-action` | الخيار الآمن/الإلغاء | Confirmation dialogs |
| `surface-close` | زر إغلاق Surface | Info dialogs |
| `auto` / `feature-defined` | Feature تحدد target صراحةً | Custom flows |

**Fallback Chain لـ `surface-heading`:**
1. أول element بـ heading role أو title role داخل Surface
2. Surface container نفسه (مع تفعيل programmatic focus)
3. أول عنصر focusable صالح

**Fallback Chain لـ `safe-action`:**
1. الزر الآمن (Cancel / الإبقاء / الرجوع) المحدد صراحةً
2. Primary action button
3. أول عنصر focusable صالح

### ٢. Focus Containment

أثناء `open` state: Tab وShift-Tab لا يخرجان من حدود الـ Surface.
Focus Containment = Must-Have V1.

### ٣. Focus Restoration

عند إغلاق Overlay، Focus يعود حسب Fallback Chain بالترتيب:

```
1. Original trigger
   → إذا ما زال في DOM، مرئياً، وقابلاً للـ focus

2. Feature-provided logical fallback
   → Feature تُحدده صراحةً عند open time

3. Parent Overlay logical focus target
   → إذا كنا نُغلق Child، يعود Focus للـ Parent Surface

4. Stable page landmark
   → navigation, main, أو heading صالح في الصفحة

5. Last resort
   → عنصر آمن محدد مسبقاً — ليس document.body مباشرة
```

### ٤. Focus لا يُفقد أبداً

إذا فشلت كل مستويات الـ Fallback → الـ Last Resort يضمن بقاء Focus في مكان صالح.
`document.body.focus()` غير مقبول كـ restoration target.

---

## OVL-18 — عزل الخلفية (Background Isolation)

### Architecture Requirement (Must-Have V1)

Blocking Overlay يجب أن تجعل الخلفية غير قابلة للتفاعل بالكامل:

- **Pointer interaction** — لا click، لا hover
- **Keyboard/Tab navigation** — لا Tab يصل للخلفية
- **Screen reader exposure** — العناصر الخلفية لا تُقرأ (حسب التقنية الصحيحة)

### القاعدة الحاسمة

**Background Isolation تبقى فعالة طوال closing state.**
لا تُرفع قبل انتهاء exit animation (راجع OVL-07).

### Web Direction (لا يُثبَّت الآن)

Web V1 قد يستخدم `inert` attribute أو mechanism مكافئ.
هذا implementation detail يُحسم في Runtime phase.
Architecture Requirement نفسها Must-Have بغض النظر عن Implementation.

### Parent/Child

بينما Child مفتوح:
- Parent's Surface تُعامل كخلفية (غير تفاعلية)
- إزالة Child → Parent تستعيد interaction بشكل كامل

---

## OVL-19 — عقد Scroll Lock

### Behavior Contract (Must-Have V1)

- **Ownership مركزي** — DS-OVL يملك Scroll Lock، لا Feature
- **Reference Counting** — عداد يزيد عند opening، يقل عند closing
  - Unlock فقط عند وصول العداد للصفر (آخر blocking overlay أُغلقت)
- **Scroll Position محفوظ** — لا layout jump عند lock أو unlock
- **No layout shift** — الصفحة لا تقفز عند ظهور scrollbar
- **Mobile/iOS safe** — تطبيق مناسب للـ mobile browsers (راجع OVL-23)
- **Nested overlays آمنة** — Reference Counting تحل هذا تلقائياً

### Implementation Note

CSS code المحدد (مثل `position:fixed` trick أو `overflow:hidden`) هو Runtime implementation detail.
لا نثبته في Documentation — السلوك المطلوب هو الرسمي.

### تعارض Migration

خلال فترة الانتقال: Legacy overlays تستخدم `document.body.style.overflow = 'hidden'` مباشرة.
هذا يتعارض مع Reference Counting الخاص بـ DS-OVL.
قيد Migration: لا تفتح DS-OVL overlay وlegacy overlay بشكل متداخل — راجع OVL-29.

---

## OVL-20 — عقد Backdrop

### ما الذي يملكه DS-OVL

- **Backdrop semantics** — من "يملك" الـ backdrop interaction
- **Close Intent routing** — backdrop click يصل للـ Top Active Layer فقط
- **Visual hierarchy** — nested overlays تحافظ على تسلسل بصري صحيح

### ما لا يُحسم الآن

DOM implementation: هل Runtime يستخدم backdrop واحد أو backdrop لكل layer أو pseudo-elements أو hybrid — هذا Implementation detail.

### قاعدة توجيه

Backdrop click → Close Intent بـ reason=`backdrop` → يصل للـ Top Active Layer → يمر عبر Close Policy → Guard (إذا guarded/locked) → إغلاق أو رفض.

لا يصل لـ Parent مباشرة. لا يُغلق Parent طالما Child موجود.

---

## OVL-21 — Surface Slot Contract

### الهيكل المرن

```
Surface
├ Header (optional)   — title + optional actions + close mechanism
├ Body                — main content / scroll container
└ Footer (optional)   — action area
```

### قواعد Slots

**لا يوجد mandatory structure** — Feature تستخدم ما تحتاجه:

| Use case | Slots المستخدمة |
|----------|----------------|
| Confirmation | Body (compact) + inline actions |
| Edit Form | Header + Body (scrollable) + Footer (save/cancel) |
| Fullscreen view | Header + Body |
| Quick picker | Body فقط |
| Info dialog | Header + Body |

### RTL

جميع الـ Slots RTL-aware بشكل افتراضي.
Header: العنوان يميناً، Actions/Close يساراً (حسب RTL conventions).

### Close Mechanism

إذا Close Policy = `dismissible` أو `guarded`:
Surface يجب أن تحتوي على close mechanism مرئي ومُيسَّر لـ Focus (Accessibility — OVL-26).

إذا Close Policy = `locked`:
Close mechanism يُوجَّه حسب مسارات الإغلاق المتاحة التي يُحددها Feature.

---

## OVL-22 — Responsive Strategy Presets

### المبدأ

Feature لا تكتب responsive logic خاصة.
Feature تختار **Preset رسمياً** من القائمة المحدودة.

### Presets V1 (أسماء Conceptual — لا تُثبَّت)

| Preset | Desktop | Mobile |
|--------|---------|--------|
| `center-fixed` | مركز ثابت | مركز ثابت (confirmation، quick info) |
| `center-to-bottom` | مركز | bottom sheet |
| `center-to-fullscreen` | مركز | fullscreen |
| `side-to-fullscreen` | side drawer | fullscreen |
| `bottom-fixed` | bottom sheet | bottom sheet |
| `fullscreen-fixed` | fullscreen | fullscreen |

### أمثلة التطبيق

| Feature | الـ Preset المناسب |
|---------|------------------|
| Confirmation dialog | `center-fixed` |
| Edit Profile Drawer | `side-to-fullscreen` |
| Quick status picker | `center-to-bottom` |
| Image viewer | `fullscreen-fixed` |
| Notes editor | `center-to-fullscreen` |

### ملاحظة

أسماء الـ Presets تُحسم في Runtime phase. Documentation تصف السلوك المطلوب.

---

## OVL-23 — Mobile Contract

### Must-Have V1 (Behavior Contracts)

**Safe Area Insets**
Surface لا تتجاوز مناطق iOS home indicator وNotch.
Footer/Actions تبقى فوق safe-area-inset-bottom.

**Dynamic Viewport**
ارتفاع Surface يُحسب بشكل صحيح يأخذ بعين الاعتبار browser chrome المتحرك (يختلف عن 100vh على Safari).

**Virtual Keyboard**
عند ظهور لوحة المفاتيح:
- Action Footer يظل مرئياً (لا يختفي خلف keyboard)
- Surface Content area تتكيف (scrollable داخلياً)
- Surface لا تتجاوز usable viewport المتاح

**Orientation Change**
Surface تُعيد حساب أبعادها عند تدوير الجهاز.

**Scrollable Body Area**
المحتوى الطويل قابل للـ scroll داخل Surface بدون overflow الـ viewport.
Scroll داخلي (scroll داخل Surface) لا scroll الصفحة الكاملة.

**Header/Footer/Actions Remain Usable**
لا تختفي خلف keyboard أو navigation bar أو browser chrome.

### ملاحظة Implementation

CSS values محددة (مثل `env(safe-area-inset-bottom)` أو `100dvh`) تُحسم في Runtime phase.
السلوك المطلوب هو الرسمي.

---

## OVL-24 — Animation Strategy

### Directional Minimal

| Presentation | Enter | Exit |
|-------------|-------|------|
| `center` | fade + subtle scale-up | fade + subtle scale-down |
| `side` | slide in من اليمين (RTL) | slide out اليمين |
| `bottom` | slide up من الأسفل | slide down |
| `fullscreen` | minimal fade أو direct | minimal fade أو direct |

### قواعد Animation

- **Exit animation = Must-Have V1** — الإغلاق ليس `display:none` فوري
- **Timeout Fallback إلزامي** — راجع OVL-07
- **لا Flashy animations** — لا bouncing، لا elastic، لا full-page reveal effects
- **RTL Direction** — side overlay يتكيف مع `dir="rtl"` تلقائياً (يدخل من اليمين، يخرج اليمين)

### Reduced Motion

```
@media (prefers-reduced-motion: reduce) {
  /* Animation تُلغى أو transition قصير جداً < 0.1s */
}
```

Must-Have V1. لا تُعطِّل Timeout Fallback عند تعطيل Animation.

---

## OVL-25 — Size Strategy

### Named Presets (Conceptual — لا pixel values الآن)

Feature تختار من presets رسمية محدودة:

| Preset | الاستخدام |
|--------|----------|
| `compact` | Confirmation، alerts، quick pickers |
| `standard` | Forms وDrawers العادية |
| `wide` | Tables، complex forms، multi-column content |
| `full` | Max-width مع margins (تقريباً fullscreen) |

### قواعد Size

- كل preset له max-size relative to viewport
- Content أطول → Surface تُفعِّل scroll داخلي (لا تكبر خارج viewport)
- Surface لا تُحدد widths عشوائية خارج الـ presets

### تحذير

Pixel values وCSSproperties تُحدد في Runtime phase.
لا تثبت `430px` أو `520px` أو `675px` كـ Documentation contract.

---

## OVL-26 — Accessibility — V1 (قائمة كاملة)

كل blocking overlay **يجب** أن تلتزم بالكامل بـ:

### Semantics & Labeling

- **Accessible name** — `aria-labelledby` (يُشير لـ heading/title) أو `aria-label`
- **Title association** — heading/title داخل Surface يُربط بـ `aria-labelledby`
- **`aria-modal="true"`** — على blocking modal semantics فقط (ليس على كل شيء)
- **`role="dialog"`** — الافتراضي
- **`role="alertdialog"`** — فقط عند urgency حقيقية في Semantics (راجع OVL-27)

### Interaction

- **Background isolation** — راجع OVL-18 (keyboard، pointer، screen reader)
- **Focus containment** — Tab/Shift-Tab لا يخرجان من Surface
- **Initial focus policy** — حسب Semantics default (راجع OVL-17)
- **Escape routing** — Escape يُرسل Close Intent للـ Top Active Layer
  (إلا إذا Close Policy = `locked` — حسب القيود المُحددة)
- **Visible close mechanism** — إذا close مسموح، يجب أن يكون visible وfocusable

### Content & Layout

- **Scrollable content accessible** — Long content قابل للـ scroll بـ keyboard
- **Focus not obscured** — Active element لا تكون محجوبة بـ sticky elements داخل Surface

### Motion & Direction

- **`prefers-reduced-motion`** — Animation تُلغى أو تُقلل (راجع OVL-24)
- **RTL compatibility** — Presentation تعكس `dir="rtl"` (side يدخل اليمين، header يُرتَّب RTL)

### Focus Lifecycle

- **Focus restoration** — Fallback Chain إلزامي (راجع OVL-17)
- **Parent/Child focus ownership** — Child يُعيد Focus للـ Parent عند إغلاقه (OVL-09)

### Confirmation Specific

- `role="alertdialog"` — فقط عند urgency حقيقية في Semantics
  - حذف record عادي → `role="dialog"` كافٍ
  - فقدان بيانات غير قابلة للاسترداد أثناء عملية حرجة → `role="alertdialog"` مبرَّر

---

## OVL-27 — Confirmation Contract

### التعريف

Overlay من Semantics = `confirmation` تطلب تأكيد قرار من المستخدم.

### مكونات Confirmation Overlay

**المحتوى المطلوب:**
- **Question/Statement واضحة** — "ماذا سيحدث إذا أكدت؟"
- **Primary action** — يُنفِّذ القرار (مثل: "حذف"، "تأكيد")
- **Secondary action** — يُلغي أو يعود (مثل: "إلغاء"، "العودة")

**Initial Focus (Semantics override):**
- **Destructive/risky action** → Focus على Secondary/Safe action
- **Positive confirmation** → Focus على Primary action
- Feature تختار بحسب السياق

### `role="alertdialog"` — ليس تلقائياً

| الحالة | ARIA role |
|--------|-----------|
| حذف record عادي | `role="dialog"` |
| تأكيد إجراء (مقابلة، نشر) | `role="dialog"` |
| فقدان بيانات غير قابلة للاسترداد | `role="alertdialog"` |
| إجراء حرج يحتاج انتباهاً عاجلاً | `role="alertdialog"` |

**القاعدة:** `alertdialog` يُستخدم عندما Semantics تحتاج فعلاً انتباهاً عاجلاً وخاصاً. لا يتبع لون الزر أو كون الفعل "delete" فقط.

### Close Policy المعتادة

- `locked` أو `guarded` (نادراً `dismissible`)
- Backdrop click وEscape — مقيَّدان حسب Policy

---

## OVL-28 — DS-OVL × DS-FRM — حدود المسؤولية

### المبدأ

DS-OVL لا تعرف Business domain.
DS-OVL لا تستدعي DS-FRM مباشرة.
DS-OVL لا تُعيد تعيين Form state عند الإغلاق.

### ما يملكه كل نظام

| DS-OVL يملك | DS-FRM / Feature يملك |
|------------|----------------------|
| Close Guard Contract (الواجهة) | Logic الـ Guard (هل Form dirty؟) |
| توجيه Close Intent | استشارة DS-FRM.isDirty() |
| إرجاع CloseDecision | قرار "discard" أو "save first" |
| إدارة lifecycle الإغلاق | Reset / Discard / Rollback |

### Future Integrations

Close Guard قابل لاستشارة أنظمة أخرى بنفس Pattern:
- Upload Manager (هل رفع ملف جاري؟)
- Editor State (هل يوجد unsaved draft؟)
- Recording (هل تسجيل نشط؟)
- Workflow (هل عملية في منتصفها؟)

DS-OVL لا تعرف أياً من هذه — Feature/Integration Layer تستشيرها.

---

## OVL-29 — Migration Strategy

### المبدأ: Migration تدريجي

**ممنوع Big Bang Migration** — لا تُحوِّل الـ 47 overlay الحالية دفعة واحدة.

### القاعدة الأساسية

**كل Overlay جديد بعد اعتماد DS-OVL Runtime يجب أن يستخدم النظام الرسمي.**
Legacy overlays الحالية تُوثَّق كـ Migration Debt وتُنقل تدريجياً.

### Migration Priority

**أولوية 1 (عند إنجاز DS-OVL Runtime):**
- `window.scConfirm` في `profile-v2.exp.js` (مستخدم في 6 modules)
- سبب الأولوية: implementation مشترك خاطئ (no focus trap، no role، no accessibility)

**أولوية 2:**
- 19 موضع `window.confirm()` (company.main.js، company.jobs.js، company.posts.js، admin.html، admin-view.html، appointment-room.html وغيرها)

**أولوية 3:**
- 47 overlay instance موزعة على 6 CSS Pattern Families (A–F) في 20+ ملف

### قيود فترة الانتقال

**قيد 1: لا Parent/Child بين DS-OVL وLegacy**
DS-OVL overlay لا يُفتح كـ child لـ legacy overlay والعكس.
النظامان يعملان بشكل مستقل خلال فترة الانتقال.
Stacking بين النظامين = undefined behavior.

```
❌ legacy overlay مفتوحة → DS-OVL overlay يُفتح فوقها
❌ DS-OVL overlay مفتوحة → legacy overlay يُفتح فوقها
✅ كلٌّ مستقل في سياقه
```

**قيد 2: Scroll Lock conflict**
Legacy overlays تستخدم `document.body.style.overflow = 'hidden'` مباشرة.
DS-OVL يستخدم Reference-counted scroll lock.
إذا اثنين نشطان معاً، unlock قد يحدث بشكل غير صحيح.
**Migration rule:** لا تفتح DS-OVL وLegacy overlay في نفس الوقت على نفس المستوى.

**قيد 3: Escape routing conflict**
Legacy: `tw_shared.js` first-defined-wins pattern.
DS-OVL: يعالج Escape للـ Top Layer.
إذا اثنين نشطان معاً، Escape routing غير محدد.
**Migration rule:** نفس القيد 2 — لا تداخل.

### ترتيب Migration لـ scConfirm

```
DS-OVL Documentation (هذا PR)
→ DS-OVL Runtime Foundation
→ DS-OVL Confirmation Implementation
→ Automated Tests
→ Migration لـ 6 modules مستخدمة لـ scConfirm
→ إزالة scConfirm القديم فقط بعد التأكد من عدم وجود مستهلكين
```

---

## OVL-30 — Ownership Matrix

| المسؤولية | المالك |
|---|---|
| Stack إدارة Layer | DS-OVL |
| Lifecycle (opening/open/closing) | DS-OVL |
| Background Isolation | DS-OVL |
| Focus Containment | DS-OVL |
| Focus Initial Strategy (execution) | DS-OVL |
| Focus Initial Target (decision) | Feature (من presets DS-OVL) |
| Focus Restoration | DS-OVL (chain) + Feature (logical fallback) |
| Scroll Lock | DS-OVL (مركزي، reference-counted) |
| Escape Intent processing | DS-OVL |
| Back Intent | DS-NAV يملكه، DS-OVL يُسجِّل |
| Backdrop semantics | DS-OVL |
| Close Guard Contract (واجهة) | DS-OVL |
| Close Guard logic (dirty, upload...) | Feature/Integration Layer |
| DS-FRM.isDirty() | DS-FRM |
| DS-FRM reset/discard | Feature/DS-FRM |
| Layer Context للـ DS-SEL | DS-OVL يُنتج، DS-SEL تستهلك |
| Binding Layer Context لـ DS-SEL | Feature/Integration Layer |
| Responsive Strategy Selection | Feature (من presets DS-OVL) |
| Animation execution | DS-OVL |
| Size Preset Selection | Feature (من presets DS-OVL) |
| Z-index allocation | Global Layer Tokens (DS-OVL يستهلك band) |
| Toast/Feedback z-index | DS-FEEDBACK (نظام منفصل) |
| DS-SEL dropdown z-index | DS-SEL (ضمن Layer Context) |
| Accessibility contract | DS-OVL |
| Authorization | Backend |
| UI Visibility (trigger) | DS-VM |

---

## OVL-31 — Must-Have V1

هذه المتطلبات يجب أن تكون موجودة في Runtime V1 قبل استخدام DS-OVL في production.

1. ✅ Unified manager concept — كل overlays جديدة تمر عبر نظام واحد
2. ✅ Orthogonal model — Modality × Presentation × Semantics × Close Policy
3. ✅ Blocking modality
4. ✅ Presentation modes — center, side, bottom, fullscreen
5. ✅ Stack management — ordered layers
6. ✅ Parent/Child contract — 7 rules (OVL-09)
7. ✅ Lifecycle — closed/opening/open/closing + timeout fallback
8. ✅ Close Intent routing (Top Layer فقط)
9. ✅ Close Reasons contract
10. ✅ Close Guard contract (generic)
11. ✅ Background isolation (Must-Have)
12. ✅ Initial Focus Policies (surface-heading/safe-action defaults)
13. ✅ Focus containment (keyboard trap)
14. ✅ Focus restoration (fallback chain)
15. ✅ Scroll lock (reference-counted, behavior contract)
16. ✅ DS-NAV integration (registration)
17. ✅ DS-SEL Layer Context integration (contract)
18. ✅ Responsive strategy presets (6 presets)
19. ✅ Mobile: safe-area + dynamic viewport + virtual keyboard behavior
20. ✅ Accessibility — complete list (OVL-26)
21. ✅ Background isolation active during closing state
22. ✅ Duplicate identity prevention
23. ✅ Confirmation semantics contract (OVL-27)
24. ✅ Result concept (conceptual)
25. ✅ Reduced motion support
26. ✅ Layer Architecture (bands concept, no type-based z-index)
27. ✅ Exit animation + timeout fallback
28. ✅ Backdrop semantics ownership
29. ✅ RTL compatibility
30. ✅ Forbidden patterns enforcement

---

## OVL-32 — Nice-to-Have

غير ضرورية لـ V1 الأساسي، لكن مرحباً بها في V1 الناضج:

- Scroll-snapping داخل Surface (مفيد للـ bottom sheets)
- Skeleton loading state أثناء async content load داخل Surface
- Header collapse on scroll (للـ drawers الطويلة)
- Focus group management (Tab islands داخل Surface)
- Drag handle visual للـ bottom sheets (بدون swipe gesture logic)
- Accessibility audit logging (للـ development mode)

---

## OVL-33 — Defer

مؤجل بشكل صريح — لا تُبنى في V1:

- **Swipe-to-dismiss gestures** — touch interaction معقد، يحتاج PR مستقل
- **Snap points** — مرتبط بـ swipe
- **Non-blocking drawer** (modality = non-blocking) — Modality توسيع، PR مستقل
- **Deep-link Overlay state** — overlay تُفتح من URL مباشرة
- **Analytics/telemetry logging hooks** — optional hook، ليس architecture requirement
- **Native `<dialog>` reconsideration** — ليس rejected للأبد، Defer حالياً (راجع OVL-36)
- **Advanced lazy content** — render on demand لتحسين الأداء
- **Advanced testing hooks** — test harness متخصص

---

## OVL-34 — Forbidden Patterns

```
// Overlay Architecture

❌ Page-local overlay engines
   Feature تبني Stack أو Focus management أو Escape listener خاصة بها

❌ Arbitrary hardcoded z-index
   أرقام z-index مباشرة في Feature code خارج Global Layer Tokens

❌ Feature-level body scroll lock
   document.body.style.overflow = 'hidden' أو ما شابه مباشرة من Feature
   (company.main.js:2265, 2430, 2950 هي الديون الحالية — يُحلّ في Migration)

❌ Feature-level global Escape listeners
   document.addEventListener('keydown', ...) للـ Escape مباشرة من Feature

❌ Feature-level popstate listeners
   window.addEventListener('popstate', ...) مباشرة من Feature
   (company.main.js:1975, 4624 هي الديون الحالية — يُحلّ في Migration)

❌ window.confirm() في أي Overlay جديدة
   (19 موضع حالي كديون — يُحلّ في Migration)

❌ Background interactive behind blocking overlay
   أي حالة يصل فيها Tab أو click أو Screen Reader للخلفية

❌ Public force-close flag
   close('force') كـ Close Reason عامة للـ Features

❌ Duplicate overlay identity
   فتح نفس Logical Identity مرتين بدون مبرر صريح

❌ Nested overlay بدون parent relation
   طبقة تُفتح بدون تسجيل Parent في Stack

❌ DS-SEL treated as DS-OVL
   Select/Dropdown ليست Overlay — Layer Context مختلف

❌ Body portal + giant z-index بدون Layer Context
   الحل الحالي (z-index 9500) يُحلّ عبر Layer Context في DS-OVL (OVL-15)

❌ Separate mobile Feature logic
   Feature تكتب responsive code منفصل بدلاً من اختيار Preset (OVL-22)

❌ Hidden private data as authorization
   Overlay بـ display:none كبديل عن Backend auth — DS-VM + Backend هما الحل

❌ Focus escaping active blocking overlay
   Tab/Shift-Tab يخرجان من Surface

❌ Removing background isolation before closing finishes
   inert/mechanism يُرفع قبل اكتمال exit animation

❌ DS-OVL directly resetting DS-FRM state
   DS-OVL لا تستدعي DS-FRM.reset() أو ما يعادله

❌ Type-based z-index ordering
   "confirmation دائماً فوق modal" بسبب الاسم — الترتيب من Stack depth

❌ CSS class name coupling in DS-SEL
   مراقبة .ep-overlay أو .sc-modal-overlay بالاسم (كما في tw-select.js حالياً)
   يُحلّ عبر Layer Context في Migration

❌ alertdialog لكل destructive action
   alertdialog فقط عند urgency حقيقية في Semantics (OVL-27)

❌ Native <dialog> كـ V1 foundation
   مؤجل حالياً (OVL-36) — لكن ليس forbidden للأبد

❌ window.scConfirm في Overlays جديدة
   scConfirm implementation مكسور (no focus trap، no role، no accessibility)
   يُهجر في Migration بعد DS-OVL Confirmation جاهز

❌ Cloning DOM للـ mobile
   لا duplicate DOM لـ mobile-only — Responsive Presets يحل هذا

❌ Overlay بدون Close Reason
   كل إغلاق يحمل Close Reason من قائمة OVL-11

❌ DS-FRM dependency مباشر داخل DS-OVL
   DS-OVL.beforeClose لا تستدعي DS-FRM.isDirty() مباشرة

❌ >2 active overlay levels بدون justification
   أكثر من مستويين يحتاج مبرراً معمارياً واضحاً (OVL-09)
```

---

## OVL-35 — الأمان والصلاحيات (Security & Permission Separation)

### مسؤولية كل نظام

| النظام | المسؤولية |
|--------|-----------|
| **DS-VM** | من يرى الـ trigger (الزر الذي يفتح Overlay) |
| **Backend** | Authorization النهائي — من يملك البيانات |
| **DS-OVL** | Layer behavior فقط — كيف تُفتح وتُغلق |

### القاعدة المحظورة

```
❌ hidden overlay containing private data as authorization bypass
```

**مثال خاطئ:**
```js
// خطأ: إرسال بيانات حساسة وإخفاء overlay للزوار
const privateData = await fetchSensitiveData(); // لكل المستخدمين!
if (!isOwner) overlay.style.display = 'none';   // إخفاء UI فقط
```

**الصح:**
- Backend لا يُرسل بيانات حساسة إلا لمن يملك صلاحية رؤيتها
- DS-VM يُحدد visibility الـ trigger
- DS-OVL يُدير layer behavior فقط

---

## OVL-36 — Runtime Direction (Non-binding)

هذا القسم يصف الاتجاه المخطط للـ Runtime — **غير ملزم** بأسماء أو APIs.
كل ما يلي قد يتغير في Runtime phase.

### Web V1 Direction

**Implementation preferred:** Custom body-level implementation.
Contract يبقى implementation-neutral.

**السبب:** DS-NAV integration + DS-SEL layer context + Stack control + migration reality من 47 overlay موجودة.

**Native `<dialog>` ليست V1 choice** — لكنها ليست forbidden للأبد.
إذا صارت مناسبة مستقبلاً (بعد حل DS-NAV + DS-SEL + migration issues)، يمكن إعادة النظر بدون كسر DS-OVL contract.

**Popover API** — خارج نطاق DS-OVL V1. DS-OVL = Blocking Overlays فقط.

### Possible Runtime Artifacts (Non-binding names)

```
// هذه أمثلة فقط — لا تُثبَّت كـ Contract
TwOverlay / window.TwOverlay        ← نقطة دخول محتملة
#tw-ovl-root                        ← Portal root محتمل على document.body
tw-ovl:* events                     ← Custom events محتملة
tw-overlay.js / tw-overlay.css      ← اسم الملف محتمل
```

**القاعدة:** لا تُطبِّق أي من هذه الأسماء قبل Runtime phase.
Architecture Contract (هذا الملف) يصف capabilities/ownership/behavior.

---

## OVL-37 — خارج النطاق — V1

الأنظمة التالية ليست DS-OVL:

| النوع | النظام المناسب |
|-------|--------------|
| Select / Dropdown / Picker | DS-SEL → `SELECT-PICKER.md` |
| Tooltip | غير موثَّق بعد (Popover API / custom) |
| Popover / Floating label | غير موثَّق بعد |
| Toast / Snackbar / Banner | DS-FEEDBACK — غير موثَّق بعد |
| Context menu | غير موثَّق بعد |
| Date Picker UI | DS-DATE → `DATE-TIME-FIELDS.md` |
| Notification badge | DS-Notifications (راجع SYSTEMS_INDEX) |
| Sidebar ثابتة (non-overlay) | جزء من Layout / Navigation |

---

*أُنشئ في PR docs/ds-ovl-v1 — 2026-07-24 — [DS-OVL] Overlay System V1 Architecture Contract (OVL-00 → OVL-37، 38 قسماً). Orthogonal Model (Modality × Presentation × Semantics × Close Policy). Layer Context contract مع DS-SEL. DS-NAV integration. Generic Close Guard (بلا DS-FRM dependency). Focus Contract (surface-heading / safe-action defaults + fallback chains). Background Isolation active during closing. Reference-counted Scroll Lock. Migration Strategy مع 3 transition constraints. 25+ Forbidden Patterns. Must-Have V1 (30 items). DESIGN_SYSTEM.md + SYSTEMS_INDEX.md + ARCHITECTURE_FOUNDATION.md F33 مُحدَّثة في نفس الـ PR.*
