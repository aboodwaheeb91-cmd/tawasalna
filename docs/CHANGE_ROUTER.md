# CRS — Change Routing System
# نظام توجيه التعديلات

> **CRS هو Workflow يُطبِّق F30/F31 على مستوى الطلب — ليس Source of Truth لأي نظام، وليس طبقة فوق القواعد العليا.**
>
> القرار النهائي يملكه النظام الحاكم. ARCHITECTURE_FOUNDATION يبقى أعلى سلطة دائماً.

---

## Workflow Order (ليس Authority Hierarchy)

```
Workflow:  ARCHITECTURE_FOUNDATION → SYSTEMS_INDEX → CRS → Governing System → Runtime
Authority: ARCHITECTURE_FOUNDATION F1–F35 > كل ما عداه دائماً
```

CRS لا يُقدَّم على F30/F31 — بل يُطبِّقهما:
- **F30:** لا نظام موثَّق → STOP وبلِّغ
- **F31:** قبل كتابة أي سطر، حدِّد النظام الحاكم
- **CRS:** ينظِّم عملية تحديد النطاق + المالك + الحد الأدنى للقراءة + الحكم

---

## CRS-01 — Routing Engine

```
User Request
↓ A: Scope Detection
↓ B: Change Classification
↓ C: Owner Resolution (via F31 + SYSTEMS_INDEX)
↓ D: Required Reading
↓ F: Architectural Check (CRS-02)
↓ G: Impact Matrix
↓ H: Verdict — PROCEED / STOP / DISCUSS
↓ I: Execution Scope
```

### A — Scope Detection

حدِّد Target بأكبر دقة ممكنة من الطلب قبل أي قراءة.

- Target محدد → لا full-page audit تلقائياً.
- Target غامض → `Verdict: DISCUSS` + سؤال واحد محدد.

### B — Change Types

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
| `FEEDBACK` | operational toast/snackbar |
| `NAVIGATION` | routing، history، back |
| `PERMISSION` | visibility، access control |
| `API` | endpoint، payload shape، contract |
| `DATA` | DB schema، table، migration |
| `NOTIFICATION` | persistent notification، hook، event |

لا تُوسِّع القائمة بنوع جديد إلا إذا كان النوع غير مُغطَّى فعلاً.

### C — Owner Resolution

بعد تحديد Change Type، حدِّد النظام المالك بهذا الترتيب:

```
1. ابحث في F31 جدول التوجيه (ARCHITECTURE_FOUNDATION.md)
2. إذا لم يكن في F31 → ابحث في SYSTEMS_INDEX (docs/SYSTEMS_INDEX.md)
3. افتح Routing Protocol للنظام المُحدَّد (مثلاً BTN-00, CLR-00, OVL-00)
4. لا نظام موثَّق → F30 = STOP + وضِّح النقص
```

**Supporting Owners:** الأنظمة التي يدخل نطاقها نوع التغيير فعلاً — لا تُقرأ تلقائياً.

**API Subclassification** — عند نوع `API`، صنِّف أولاً:

| API Kind | Route |
|----------|-------|
| mutation (POST/PUT/PATCH/DELETE) | API-MUT + governing feature/backend |
| GET / read-only | governing feature/API contract via SYSTEMS_INDEX |
| auth | Auth governing contract |
| upload | Upload System (§29a SYSTEMS_INDEX) |
| WebSocket | Messaging/WebSocket governing system |
| لا نظام موثَّق | F30 STOP |

API-MUT يملك mutation contract فقط — لا يغطي GET/auth/upload/WebSocket.

**أنواع بدون F31 row** (CONTENT / LAYOUT / DATA / NOTIFICATION):
→ SYSTEMS_INDEX مباشرةً → إذا لا يوجد نظام موثَّق → F30 STOP.

### D — Required Reading

```
Read:
- [Primary Owner — القسم الحاكم لهذا التغيير تحديداً]
- [Supporting — فقط إذا تقاطع نوع التغيير فعلاً]

Do Not Read:
- أي شيء خارج الـ Route المحدد
- قراءة كاملة إذا قسم محدد يكفي
- أنظمة مُسمَّاة لكن غير متقاطعة
```

---

## CRS-02 — Architectural Sanity Check

| السؤال | إذا YES |
|--------|---------|
| هل يخالف الطلب Contract موجود؟ | `STOP` — أذكر العقد المخالَف |
| هل يوجد Shared System يجب استخدامه؟ | `DISCUSS` — اقترح النظام |
| هل الحل يُنشئ Duplicate Implementation؟ | `DISCUSS` |
| هل هو Local Workaround بدلاً من Root-Cause Fix؟ | `DISCUSS` |
| هل يُضع Security Logic في Frontend؟ | `STOP` — F6 + F17 |
| هل يؤثر على API Contract (Mobile Future)؟ | لاحظ في Impact Matrix |
| هل يوجد System Gap؟ | وثِّق — انظر System Gap Contract |
| هل يوجد حل معماري أفضل؟ | `DISCUSS` |

لا توجد مشكلة → `PROCEED`.

---

## System Gap Contract

إذا كشف الطلب عن غياب أو خطأ في عقد النظام الحاكم:

1. حدِّد النظام المالك.
2. هل العقد ناقص؟ أم فقط Runtime Adoption مخالف؟
3. **Gap حقيقي** → حدِّث Governing Docs في نفس PR مع Runtime.
4. **Adoption فقط** → صحِّح Runtime فقط.

```
System Gap: NONE / POSSIBLE / CONFIRMED
```

---

## Shared System First

```
1. نظام موثَّق موجود ويغطي الحاجة → استخدمه.
2. نظام موجود جزئياً → F30 STOP + وضِّح الجزء الناقص.
3. لا نظام موثَّق → F30 STOP + اشرح ما هو مطلوب.
```

إنشاء أو توسيع نظام يتم فقط إذا كانت المهمة الحالية تُفوِّض ذلك صراحةً.
لا repo-wide search غير ضروري. الفحص يبدأ من SYSTEMS_INDEX.

---

## CRS-03 — Execution Scope / Credit Control

| الحجم | الوصف | نطاق القراءة |
|-------|-------|-------------|
| `TINY` | تعديل صغير محدد | نظام واحد أو قسمان |
| `MEDIUM` | يتقاطع مع عدة Contracts | الأنظمة المتأثرة مباشرة فقط |
| `ARCHITECTURAL` | Auth / Permission / API / Navigation / System creation | قراءة أوسع عند الحاجة الفعلية |

**القاعدة الإلزامية:** لا تقرأ توثيقاً لا يستلزمه الـ Route المحدد.

---

## Context Reuse

إذا تم Audit لنفس Target في نفس جلسة الـ AI ولم يتغير HEAD بشكل يؤثر على الـ Target:
- **Reuse existing context.** لا تُعيد الـ Audit.
- إذا تغيَّر الكود في الـ Target: أعِد الفحص للجزء المتغير فقط.

---

## Ambiguity / Confidence

```
Routing Confidence: HIGH / MEDIUM / LOW
```

- **HIGH** — Target محدد، نوع التغيير واضح → نفِّذ مباشرة.
- **MEDIUM** — يمكن تفسيره بأكثر من طريقة.
- **LOW** → `Verdict = DISCUSS` + سؤال واحد محدد فقط.

---

## Impact Matrix (Template)

```
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
```

لا تُشغِّل Audit كامل لكل بند إذا النتيجة واضحة من الـ Scope.
**الـ Output يكون قصيراً إذا المهمة بسيطة.** لا تملأ كل بند إذا الجواب N/A.

---

## Mobile / API-First Guard

- إخفاء زر = UX فقط → Frontend.
- منع صلاحية = Backend authority — لا Frontend-only security (F6).

أي تغيير يؤثر على API Shape → لاحظ "Mobile: INSPECT".

---

## Notification Routing

```
Notifications: NOT NEEDED / NEEDED / INSPECT
```

- **Persistent / bell notifications** → Notification System (§19/§36 · ARCHITECTURE.md).
- **Operational transient feedback** (toast/snackbar) → DS-FEEDBACK — دور مستقل تماماً.

لا تفتح Notification System إلا إذا `NEEDED` أو `INSPECT`.
لا تستخدم DS-FEEDBACK كـ delivery channel للإشعارات الدائمة.

---

## User Intent ≠ Implementation Method

طلب صاحب المشروع يُحدِّد الهدف — لا يُلزِم بطريقة التنفيذ.

إذا طريقة التنفيذ تخالف نظاماً قائماً أو يوجد حل Shared أفضل:
```
Verdict: DISCUSS — اشرح الحل الأفضل بجملة واحدة قبل التنفيذ.
```

---

## Audit Mode / Execution Mode

**AUDIT MODE** — عند طلب فحص Target:
- ناتجه: Target + الموجود + Change Types + Governing Systems + Violations/Gaps.
- لا تعديلات Runtime.

**EXECUTION MODE** — بعد Audit موثوق:
- لا يُعيد الـ Audit من الصفر.
- يُحدِّد الملفات والعقود اللازمة فقط.
- تنفيذ محدود ودقيق.

---

## No Auto-Fix

CRS لا يُعدِّل Runtime تلقائياً. وظيفته: Route · Inspect · Classify · Recommend · Verdict.
التنفيذ يحدث فقط ضمن Task مصرح به.

---

## Documentation Discipline

```
Existing contract + Runtime adoption only → لا docs update.
Actual System Gap / Contract change       → update governing docs in same PR.
```

القاعدة الكاملة: `ARCHITECTURE_FOUNDATION.md F12`.

---

## Standard Output Format

```
CHANGE ROUTE

Target:         [صفحة → عنصر → sub-element]
Requested Change: [وصف مختصر]
Change Type:    [BUTTON / VISUAL / ...]
Primary Owner:  [from F31 / SYSTEMS_INDEX / F30 STOP]
Supporting:     [فقط إذا تقاطع نوع التغيير فعلاً]

Read:
- [قسم محدد في النظام الحاكم]

Do Not Read:
- [ما لا علاقة له بهذا الطلب]

Impact:
Frontend/Backend/API Contract/DB/Permissions/Navigation/Notifications/Mobile/Docs/Tests

Architectural Check: PASS / [مشكلة محددة]
System Gap:          NONE / POSSIBLE / CONFIRMED
Routing Confidence:  HIGH / MEDIUM / LOW
Verdict:             PROCEED / STOP / DISCUSS
Next Action:         AUDIT / EXECUTE / ASK ONE CLARIFICATION
```

---

## Mandatory Architectural Opinion

CRS لا يُحوِّل الـ AI إلى منفذ أعمى.

أبدِ رأيك إذا:
- يوجد حل معماري أفضل أو أضمن.
- يوجد خطأ معماري أو System Gap.
- يوجد خطر مستقبلي على API / Mobile / Permissions.
- يوجد تعارض مع Shared System قائم.

لا يوجد شيء مهم → لا تستهلك الرصيد. نفِّذ مباشرة.

---

## Cross-references

`ARCHITECTURE_FOUNDATION.md` — F4 · F30 · F31 (Constitutional Source of Truth)
`docs/SYSTEMS_INDEX.md` — الفهرس الرسمي لتحديد Primary Owner

الـ Routing Protocols التفصيلية داخل كل نظام (BTN-00 / CLR-00 / OVL-00 / …) هي المرجع الحاكم — ليس هذا الملف.

---

*أُنشئ في PR #526 — 2026-07-29*
*Status: ✅ Architecture Documentation*
