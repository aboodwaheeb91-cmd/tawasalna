# CRS — Change Routing System
# نظام توجيه التعديلات

> **CRS هو Router/Orchestration Layer فقط — ليس Source of Truth لأي نظام.**
>
> CRS يُحدِّد من يملك القرار ومتى يُقرأ ماذا.
> القرار نفسه يملكه النظام الحاكم.
>
> الترتيب: `ARCHITECTURE_FOUNDATION → CRS → SYSTEMS_INDEX → Governing System → Runtime`

---

## Constitutional Position

CRS يجلس بين طلب صاحب المشروع وبين F31 (System Routing Before Implementation).

- **F31** يجيب على: "هذا السطر من الكود ينتمي لأي نظام؟"
- **CRS** يجيب على: "هذا الطلب — ما نطاقه؟ من يملكه؟ كيف يُحدَّد أقل قراءة لازمة؟ هل نُنفِّذ؟"

CRS لا يتجاوز ARCHITECTURE_FOUNDATION ولا يُعيد تعريف عقود أي نظام آخر.

---

## CRS-01 — Routing Engine

كل طلب يمر بهذه المراحل بالترتيب:

```
User Request
↓
A: Scope Detection
↓
B: Change Classification
↓
C: Primary Owner
↓
D: Supporting Owners
↓
E: Required Reading
↓
F: Architectural Check (CRS-02)
↓
G: Impact Matrix
↓
H: Verdict — PROCEED / STOP / DISCUSS
↓
I: Execution Scope
```

### A — Scope Detection

حدِّد Target بأكبر دقة ممكنة من الطلب قبل أي قراءة.

```
Example:
Employee Profile
→ Edit Profile Modal (#epOverlay)
→ Footer Actions
→ #epSaveBtn Visual Style
```

- Target محدد → لا full-page audit تلقائياً.
- Target غامض → `Verdict: DISCUSS` + سؤال واحد محدد.

### B — Change Types

الطلب يُصنَّف في واحدة أو أكثر من:

| نوع | وصف |
|-----|-----|
| `CONTENT` | نص، ترجمة، placeholder |
| `LAYOUT` | ترتيب عناصر، DOM order، flex/grid |
| `VISUAL` | لون، border، shadow، radius، opacity |
| `COLOR_ROLE` | تعريف token أو تغيير لون semantic |
| `BUTTON` | شكل زر، states، lifecycle |
| `INPUT` | شكل حقل، states، autofill |
| `SELECT` | dropdown، picker، searchable |
| `DATE` | date/time field |
| `FORM` | lifecycle، payload، hydration |
| `VALIDATION` | توقيت خطأ، رسالة خطأ، field error |
| `OVERLAY` | modal، drawer، sheet، dialog |
| `FEEDBACK` | toast، snackbar |
| `NAVIGATION` | routing، history، back |
| `PERMISSION` | visibility، access control |
| `API` | endpoint، payload shape، contract |
| `DATA` | DB schema، table، migration |
| `NOTIFICATION` | إشعار، hook، event |

لا تُوسِّع القائمة بنوع جديد إلا إذا كان النوع غير مُغطَّى فعلاً.

### C — Primary Owner / Supporting Owners

**Primary Owner:** النظام صاحب القرار الأساسي للتغيير.
**Supporting Owners:** أنظمة قد تتأثر بناءً على نوع التغيير المحدد فقط.

| Change Type | Primary Owner | Supporting (inspect only if affected) |
|-------------|---------------|---------------------------------------|
| `BUTTON` | DS-BTN | DS-COLOR (للألوان) · DS-FRM (lifecycle) |
| `COLOR_ROLE` | DS-COLOR | Feature CSS (consumer) |
| `VISUAL` | DS-BTN / DS-INP / DS-COLOR | حسب العنصر |
| `INPUT` | DS-INP | DS-VAL (errors) · DS-COLOR (colors) |
| `SELECT` | DS-SEL | DS-INP (parent form field) |
| `DATE` | DS-DATE | DS-SEL (UI engine) · DS-FRM (payload) |
| `FORM` | DS-FRM | DS-VAL · API-MUT · DS-BTN |
| `VALIDATION` | DS-VAL | DS-INP (field states) · DS-FRM |
| `OVERLAY` | DS-OVL | DS-FRM (Dirty Guard) |
| `FEEDBACK` | DS-FEEDBACK | DS-VAL (form context) |
| `NAVIGATION` | DS-NAV | — |
| `PERMISSION` | DS-VM | Backend (always final authority) |
| `API` | API-MUT | DS-FRM · Backend |
| `NOTIFICATION` | Notification System | DS-FEEDBACK (delivery) |

قاعدة: لا تقرأ Supporting Systems تلقائياً. اقرأها فقط إذا كان نوع التغيير يدخل نطاقها فعلاً.

### D — Required Reading

بعد تحديد Primary + Supporting، حدِّد:

```
Read:
- [Primary Owner § or section that governs this specific change]
- [Supporting Owner section — only if change type intersects]

Do Not Read:
- [Anything outside the resolved route]
- [Full-file reads if a specific section suffices]
- [Systems that are named but not intersecting]
```

---

## CRS-02 — Architectural Sanity Check

قبل إصدار Verdict، اسأل هذه الأسئلة:

| السؤال | إذا YES |
|--------|---------|
| هل يخالف الطلب Contract موجود؟ | `STOP` — أذكر العقد المخالَف |
| هل يوجد Shared System يجب استخدامه بدل بناء جديد؟ | `DISCUSS` — اقترح الـ Shared System |
| هل الحل يُنشئ Duplicate Implementation؟ | `DISCUSS` |
| هل هو Local Workaround بدلاً من Root-Cause Fix؟ | `DISCUSS` |
| هل يُضع Business/Security Logic في Frontend؟ | `STOP` — Security يملكه Backend (F6 + F17) |
| هل يؤثر على API Contract (Flutter / Mobile Future)؟ | لاحظ في Impact Matrix |
| هل يوجد System Gap (نقص في العقد الحاكم)؟ | وثِّق كـ Gap — انظر System Gap Contract |
| هل يوجد حل معماري أفضل أو أبسط؟ | `DISCUSS` — اشرح الاقتراح |

إذا لا توجد مشكلة → `PROCEED`.

---

## System Gap Contract

إذا كشف الطلب عن غياب أو خطأ في عقد النظام الحاكم:

1. **حدِّد النظام المالك.**
2. **حدِّد: هل العقد ناقص؟ أم فقط Runtime Adoption مخالف؟**
3. إذا **Gap حقيقي** (العقد غائب أو متناقض) → حدِّث الـ Governing Docs في نفس الـ PR مع الـ Runtime.
4. إذا **Adoption فقط** (العقد واضح، التنفيذ مخالف) → صحِّح الـ Runtime فقط. لا تُعدِّل الـ Docs بدون داعٍ.

```
System Gap: NONE / POSSIBLE / CONFIRMED
```

---

## Shared System First (CRS Enforcement)

قبل بناء أي CSS pattern / helper / component / behavior:

1. هل يوجد نظام مشترك موجود بالفعل؟ (SYSTEMS_INDEX → الملف الحاكم)
2. هل يغطي الحاجة الفعلية؟ نعم → استخدمه.
3. لا → هل الحاجة ستتكرر في صفحتين أو أكثر؟ نعم → أنشئ Shared System أولاً.

لا repo-wide search غير ضروري. الفحص يبدأ من SYSTEMS_INDEX.

---

## CRS-03 — Execution Scope / Credit Control

### حجم المهمة (تقريبي)

| الحجم | الوصف | الحد التقريبي للقراءة |
|-------|-------|----------------------|
| `TINY` | تعديل صغير محدد النطاق | نظام واحد أو قسمان |
| `MEDIUM` | يتقاطع مع عدة Contracts | الأنظمة المتأثرة مباشرة فقط |
| `ARCHITECTURAL` | Auth / Permission / API / Navigation / System creation | قراءة أوسع عند الحاجة الفعلية |

هذه تقديرات ضد القراءة العشوائية — ليست حدوداً صارمة بالأرقام.

**القاعدة الإلزامية:**
> Do not read documentation that the resolved Route does not require.

---

## Context Reuse

إذا تم Audit لنفس Target في نفس جلسة الـ AI ولم يتغير الـ HEAD بشكل يؤثر على الـ Target:
- **Reuse existing context.** لا تُعيد نفس الـ Audit.
- إذا تغيَّر الكود في الـ Target بعد الـ Audit: يجوز إعادة الفحص المحدد للجزء المتغير فقط.

---

## Ambiguity / Confidence

```
Routing Confidence: HIGH / MEDIUM / LOW
```

- **HIGH** — Target محدد، نوع التغيير واضح.
- **MEDIUM** — Target معقول لكن يمكن أن يُفسَّر بأكثر من طريقة.
- **LOW** — Target غامض.

إذا `LOW` أو Target مبهم: `Verdict = DISCUSS` + سؤال واحد محدد فقط.
إذا `HIGH`: لا أسئلة إضافية — نفِّذ مباشرة.

---

## Impact Matrix (Template)

```
Frontend:     YES / NO / INSPECT
Backend:      YES / NO / INSPECT
API Contract: YES / NO / INSPECT
DB:           YES / NO / INSPECT
Permissions:  YES / NO / INSPECT
Navigation:   YES / NO / INSPECT
Notifications:NOT NEEDED / NEEDED / INSPECT
Mobile:       YES / NO / INSPECT
Docs:         YES / NO / INSPECT
Tests:        YES / NO / INSPECT
```

لا تُشغِّل Audit كامل لكل بند إذا النتيجة واضحة من الـ Scope.

---

## Mobile / API-First Guard

Web و Flutter في المستقبل كلاهما Frontend لنفس Backend / API / DB / Auth / Permissions.

- إخفاء زر = UX فقط → Frontend.
- منع صلاحية = Backend authority → لا Frontend-only security.

أي تغيير يؤثر على API Shape → لاحظ "Mobile: INSPECT" في Impact Matrix.

---

## Notification Routing

كل Feature change يُحدِّد:
```
Notifications: NOT NEEDED / NEEDED / INSPECT
```

لا تفتح Notification System إلا إذا `NEEDED` أو `INSPECT`.

---

## User Intent ≠ Implementation Method

طلب صاحب المشروع يُحدِّد **الهدف** — لا يُلزِم بطريقة التنفيذ.

إذا طريقة التنفيذ المقترحة تخالف نظاماً قائماً أو يوجد حل Shared أفضل:
```
Verdict: DISCUSS
```
اشرح الحل الأفضل بجملة واحدة قبل التنفيذ.

مثال: صاحب المشروع طلب Select محلي → النظام يملك DS-SEL → اقترح DS-SEL.

---

## Audit Mode / Execution Mode

**AUDIT MODE** — يُستخدم عند طلب فحص Target:
- ناتجه: Target + الموجود + Change Types + Governing Systems + Violations/Gaps.
- لا تعديلات Runtime.

**EXECUTION MODE** — بعد Audit موثوق:
- لا يُعيد الـ Audit من الصفر.
- يستخدم النتيجة الحالية.
- يُحدِّد الملفات والعقود اللازمة فقط.
- تنفيذ محدود ودقيق.

---

## No Auto-Fix

CRS نفسه لا يُعدِّل Runtime تلقائياً لمجرد اكتشاف مشكلة.

وظيفة CRS: Route · Inspect · Classify · Recommend · Verdict.
التنفيذ يحدث فقط ضمن Task مصرح به.

---

## Documentation Discipline

```
Existing contract + Runtime adoption only → لا docs update.
Actual System Gap / Contract change       → update governing docs in same PR.
```

لا Documentation Spam. القاعدة الكاملة: `ARCHITECTURE_FOUNDATION.md F12`.

---

## Standard Output Format

```
CHANGE ROUTE

Target:
[صفحة → عنصر → sub-element بأكبر دقة متاحة]

Requested Change:
[وصف مختصر]

Change Type:
[BUTTON / VISUAL / COLOR_ROLE / ...]

Primary Owner:
[DS-BTN / DS-COLOR / DS-FRM / ...]

Supporting Owners:
[أنظمة فقط إذا نوع التغيير يدخل نطاقها]

Read:
- [قسم محدد في النظام الحاكم]
- [قسم في Supporting إذا لازم]

Do Not Read:
- [ما لا علاقة له بهذا الطلب]

Impact:
Frontend:      YES / NO / INSPECT
Backend:       YES / NO / INSPECT
API Contract:  YES / NO / INSPECT
DB:            YES / NO / INSPECT
Permissions:   YES / NO / INSPECT
Navigation:    YES / NO / INSPECT
Notifications: NOT NEEDED / NEEDED / INSPECT
Mobile:        YES / NO / INSPECT
Docs:          YES / NO / INSPECT
Tests:         YES / NO / INSPECT

Architectural Check:
[PASS / أو وصف مشكلة محددة]

System Gap:
NONE / POSSIBLE / CONFIRMED [+ تفاصيل إذا وجدت]

Routing Confidence:
HIGH / MEDIUM / LOW

Verdict:
PROCEED / STOP / DISCUSS

Next Action:
AUDIT / EXECUTE / ASK ONE CLARIFICATION
```

**الـ Output يكون قصيراً إذا المهمة بسيطة.** لا تملأ كل بند إذا الجواب "N/A".

---

## Mandatory Architectural Opinion

CRS لا يُحوِّل الـ AI إلى منفذ أعمى.

قبل التنفيذ، يجب على الـ AI إبداء رأيه إذا:
- يوجد حل معماري أفضل أو أضمن.
- يوجد خطأ معماري أو System Gap.
- يوجد خطر مستقبلي على API / Mobile / Permissions.
- يوجد تعارض مع Shared System قائم.

أما إذا لا يوجد شيء مهم: لا يستهلك الرصيد بعبارات عامة. ينفِّذ مباشرة.

---

## Cross-references

| النظام | المرجع |
|--------|--------|
| ARCHITECTURE_FOUNDATION.md | F4 (Shared System First) · F31 (System Routing Before Implementation) |
| docs/SYSTEMS_INDEX.md | فهرس 50+ نظام — المرجع الأول لتحديد Primary Owner |
| docs/design-system/BUTTONS.md | DS-BTN — BUTTON Change Type |
| docs/design-system/COLOR-SYSTEM.md | DS-COLOR — COLOR_ROLE Change Type |
| docs/design-system/INPUT-FIELDS.md | DS-INP — INPUT Change Type |
| docs/design-system/SELECT-PICKER.md | DS-SEL — SELECT Change Type |
| docs/design-system/DATE-TIME-FIELDS.md | DS-DATE — DATE Change Type |
| docs/design-system/OVERLAY-SYSTEM.md | DS-OVL — OVERLAY Change Type |
| docs/design-system/FEEDBACK-SYSTEM.md | DS-FEEDBACK — FEEDBACK Change Type |
| docs/design-system/FORM-LIFECYCLE.md | DS-FRM — FORM Change Type |
| docs/design-system/VALIDATION-ERRORS.md | DS-VAL — VALIDATION Change Type |
| docs/design-system/NAVIGATION.md | DS-NAV — NAVIGATION Change Type |
| docs/design-system/VIEWER-MODES.md | DS-VM — PERMISSION Change Type |
| docs/contracts/API-MUTATIONS-ERRORS.md | API-MUT — API Change Type |

---

*أُنشئ في PR claude/crs-change-routing-system — 2026-07-29*
*Status: ✅ Architecture Documentation*
