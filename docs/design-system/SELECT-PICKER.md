# [DS-SEL] Select & Searchable Picker System — V1

> **الـ contract المعماري الرسمي لعناصر الاختيار من القوائم في منصة تواصلنا**
>
> V1 — توثيق فقط · لا يمس أي Runtime code.
> المرجع الرسمي للـ AI sessions والمطورين عند كل مهمة تخص القوائم المنسدلة أو الـ Pickers.
>
> **الـ Runtime القائم:** `static/shared/tw-select.js` (321 سطر) — لا تعديل عليه في هذا PR.

---

## جدول المحتويات

| القسم | العنوان |
|-------|---------|
| SEL-00 | Routing Protocol — متى تقرأ هذا الملف |
| SEL-01 | الغرض والنطاق |
| SEL-02 | الأوضاع الثلاثة (Modes) |
| SEL-03 | Source Mode |
| SEL-04 | OptionItem Interface |
| SEL-05 | نموذج الحالة — المحاور الستة (State Model) |
| SEL-06 | المحور 1 — Disclosure State |
| SEL-07 | المحور 2 — Data State |
| SEL-08 | المحور 3 — Selection State |
| SEL-09 | المحور 4 — Interaction State |
| SEL-10 | المحور 5 — Validation Modifier |
| SEL-11 | المحور 6 — Search State |
| SEL-12 | Search Query ≠ Canonical Selection |
| SEL-13 | Trigger & Control Contract |
| SEL-14 | Option List / Dropdown Contract |
| SEL-15 | Hydration Contract |
| SEL-16 | Selection Resolution |
| SEL-17 | Blur Without Selection |
| SEL-18 | القيم المحفوظة غير النشطة (Saved Inactive Values) |
| SEL-19 | Remote Search & Race Safety |
| SEL-20 | Dependent Selects |
| SEL-21 | Arabic Normalization |
| SEL-22 | لا إنشاء قيمة حرة — V1 |
| SEL-23 | لا Auto-selection للخيار الأول |
| SEL-24 | Custom Tawasolna UI دائماً |
| SEL-25 | Portal Contract |
| SEL-26 | Keyboard Navigation |
| SEL-27 | Accessibility / ARIA |
| SEL-28 | Multi-select Contract |
| SEL-29 | التكامل مع DS-FRM |
| SEL-30 | التكامل مع DS-VAL |
| SEL-31 | حدود المسؤولية (Ownership Boundaries) |
| SEL-32 | الـ Runtime الحالي — tw-select.js |
| SEL-33 | الأنظمة القديمة (Legacy Systems) |
| SEL-34 | حالة V1 ومسار الانتقال |
| SEL-35 | Forbidden Patterns |
| SEL-36 | خارج النطاق — V1 |

---

## SEL-00 — Routing Protocol

**قبل كتابة أي كود يخص قائمة منسدلة أو picker، تحقق من هذا الجدول أولاً:**

| المهمة | الأقسام |
|--------|---------|
| فهم الأوضاع المتاحة (single / searchable / multi) | SEL-02 + SEL-03 |
| تعريف بيانات الخيارات (OptionItem) | SEL-04 |
| فهم حالات الـ picker (State Model) | SEL-05 → SEL-11 |
| بناء منطق البحث | SEL-12 + SEL-19 + SEL-21 |
| ربط الـ picker بالفورم (Hydration / Reset) | SEL-15 + SEL-29 |
| التعامل مع قيم محفوظة غير نشطة | SEL-18 |
| Dependent selects (الدولة → المدينة) | SEL-20 |
| Portal / overflow escape | SEL-25 |
| Keyboard navigation / Accessibility | SEL-26 + SEL-27 |
| خطأ validation على الـ picker | SEL-10 + SEL-30 |
| Multi-select | SEL-28 |
| فهم ما هو خارج نطاق DS-SEL | SEL-31 + SEL-36 |
| الـ Runtime الحالي وقيوده | SEL-32 + SEL-33 |

> **F31 — System Routing Before Implementation:**
> أي كود يخص قائمة منسدلة ينتمي إلى DS-SEL.
> قبل كتابة أي منطق picker → اقرأ SEL-00 أولاً.

---

## SEL-01 — الغرض والنطاق

### الغرض

DS-SEL هو الـ contract المعماري الرسمي لكل عناصر الاختيار من القوائم في منصة تواصلنا:

- القوائم المنسدلة أحادية الاختيار (single-select)
- القوائم مع بحث (searchable)
- القوائم متعددة الاختيار (multi-select)
- الـ pickers التي تعتمد على بيانات catalog (دول، مهارات، مهن، مدن)

### ما يملكه DS-SEL

| العنصر | المالك |
|--------|--------|
| سلوك الـ UI (فتح/إغلاق القائمة) | DS-SEL |
| الـ Trigger / Control (العنصر المرئي الذي يُفتح منه) | DS-SEL |
| منطق الاختيار وتأكيده | DS-SEL |
| منطق البحث والفلترة | DS-SEL |
| عرض الخيارات | DS-SEL |
| Keyboard navigation | DS-SEL |
| Accessibility / ARIA | DS-SEL |
| Integration hooks (onChange, onBlur, onOpen, onClose) | DS-SEL |

### ما لا يملكه DS-SEL

راجع SEL-31 للجدول الشامل لحدود المسؤولية.

---

## SEL-02 — الأوضاع الثلاثة (Modes)

كل picker في المنصة يعمل بأحد الأوضاع الثلاثة:

| الوضع | الكود | الوصف |
|-------|-------|-------|
| أحادي | `single` | اختيار خيار واحد من قائمة بدون بحث |
| مع بحث | `searchable` | اختيار خيار واحد مع حقل بحث/فلترة |
| متعدد | `multi` | اختيار أكثر من خيار واحد (راجع SEL-28) |

### Dependent Select — قدرة وليس وضعاً

**الـ Dependent Select ليس وضعاً (mode) مستقلاً.**
هو قدرة (capability) يمكن تفعيلها على أي من الأوضاع الثلاثة:

```
خيار الدولة (single) ──يُقيِّد──▶ خيارات المدينة (single)
خيار التخصص (searchable) ──يُقيِّد──▶ خيارات المستوى (single)
```

تعريف الـ dependency يكون عبر `meta.parentValue` في OptionItem (SEL-04)
أو عبر آلية فلترة خارجية تمرّها DS-FRM إلى DS-SEL.

**قاعدة ثابتة:** لا تُنشئ "وضعاً" رابعاً باسم `dependent` —
الـ Dependency علاقة بين pickerَين، ليست خاصية في الـ picker نفسه.

---

## SEL-03 — Source Mode

كل picker يعتمد على أحد مصدرَي البيانات:

| المصدر | الكود | متى يُستخدم |
|--------|-------|-------------|
| محلي | `local` | البيانات محملة مسبقاً في الذاكرة (دول، سنوات، أنواع شركات) |
| بعيد | `remote` | البيانات تُجلب عند الطلب أو عند الكتابة في حقل البحث |

**قاعدة ثابتة:** `local` و `remote` ليسا نظامَين منفصلَين — هما خاصية واحدة على نفس الـ picker.

### متى يُستخدم `remote`

- قائمة مهارات (catalog كبير جداً — لا يمكن تحميله كاملاً)
- بحث عن مستخدمين أو شركات (unbounded dataset)
- بيانات تتغير بشكل متكرر وتحتاج fresh fetch

### `local` مع `searchable`

`sourceMode: local` + `mode: searchable` = فلترة على جانب العميل فقط.
لا يحتاج fetch إضافياً — البيانات موجودة في memory ويُفلَّتر عليها.

---

## SEL-04 — OptionItem Interface

كل خيار في أي picker يجب أن يتبع هذا الـ contract:

```js
/**
 * OptionItem — الـ contract الكامل لكل خيار في الـ picker
 */
{
  value:    string | number,  // القيمة الـ canonical المُرسَلة في الـ payload
  label:    string,           // النص المعروض للمستخدم (Arabic)
  disabled: boolean,          // اختياري — الافتراضي false
  meta: {                     // اختياري — بيانات مساعدة
    keywords: string[],       // كلمات بحث إضافية تتجاوز label (للـ matching)
    icon:     any,            // أيقونة الخيار — DS-ASSET يملك القيم الحقيقية
    flag:     any,            // علم الدولة — DS-ASSET + flags/*.svg
    parentValue: string | number  // قيمة الـ parent picker (للـ Dependent Selects)
  }
}
```

### قواعد OptionItem

1. **`value` غير قابل للتغيير** — بعد بناء القائمة، لا يُعدَّل `value` لأي خيار.
2. **`label` للعرض فقط** — لا تُرسِل `label` في payload — أرسِل `value` دائماً (API-MUT).
3. **`disabled: true`** — يمنع الاختيار UI-side؛ منطق الرفض يُؤكَّد server-side.
4. **`meta.keywords`** — تُستخدم في البحث جانب DS-SEL فقط — لا تُرسَل في payload.
5. **`meta.parentValue`** — تُستخدم لفلترة الـ Dependent Selects (SEL-20).
6. **`meta.icon` و `meta.flag`** — DS-ASSET يملك القيم الحقيقية؛ DS-SEL يعرضها فقط.

---

## SEL-05 — نموذج الحالة — المحاور الستة (State Model)

حالة الـ picker في أي لحظة هي نقطة تقاطع **ستة محاور مستقلة**.
كل محور مستقل عن الآخرين — لا تخلط بينها.

| # | المحور | القيم الممكنة |
|---|--------|--------------|
| 1 | Disclosure | `closed` \| `open` |
| 2 | Data | `idle` \| `loading` \| `ready` \| `empty` \| `error` |
| 3 | Selection | `empty` \| `resolved` \| `unresolved` |
| 4 | Interaction | `enabled` \| `disabled` \| `readonly` |
| 5 | Validation Modifier | `normal` \| `error` |
| 6 | Search | `inactive` \| `active` |

### مثال على التقاطع

```
Disclosure:  closed
Data:        ready
Selection:   unresolved    // قيمة محفوظة من DB لكن غير موجودة في الـ catalog الحالي
Interaction: enabled
Validation:  error         // الـ picker به خطأ validation
Search:      inactive
```

هذه الحالة: picker مغلق، بيانات محملة، قيمة موجودة لكن unresolved، عليه خطأ.
كل محور حالته مستقلة — الـ error لا يُغلق القائمة، والـ unresolved لا يمنع التعديل.

---

## SEL-06 — المحور 1 — Disclosure State

| الحالة | الوصف |
|--------|-------|
| `closed` | القائمة مخفية — الـ Trigger مرئي فقط |
| `open` | القائمة مفتوحة ومرئية |

### قواعد الانتقال

| الحدث | الانتقال |
|-------|---------|
| Trigger click | `closed → open` (إذا Interaction = enabled) |
| Option selection | `open → closed` (بعد تأكيد الاختيار — single/searchable فقط؛ multi لا يُغلَق عند كل اختيار — راجع SEL-28) |
| Outside click | `open → closed` |
| Escape key | `open → closed` (SEL-26) |
| Tab key أثناء الفتح | `open → closed` |
| Interaction = disabled/readonly | يبقى `closed` دائماً |
| Scroll الصفحة أثناء الفتح | `open → closed` (SEL-25) |

**قاعدة:** لا يُفتح أكثر من picker واحد في نفس الوقت — DS-OVL يُنسِّق.

---

## SEL-07 — المحور 2 — Data State

| الحالة | الوصف |
|--------|-------|
| `idle` | لم تُحمَّل البيانات بعد (remote + لم يُطلَق بعد) |
| `loading` | جارٍ جلب البيانات |
| `ready` | البيانات محملة وجاهزة (قد تكون القائمة فارغة من نتائج البحث) |
| `empty` | البيانات محملة لكن لا توجد نتائج للبحث الحالي |
| `error` | فشل جلب البيانات (remote fetch failed) |

### قواعد Data State

- **`error` يعرض رسالة آمنة** — لا raw error object للمستخدم (F9).
- **`idle → loading`** عند أول فتح للـ remote picker (lazy load).
- **`loading` يعرض skeleton أو spinner داخل القائمة** — لا يُغلق القائمة.
- **`error` يعرض زر "إعادة المحاولة"** داخل القائمة — لا يُغلقها.
- **`empty` ≠ `error`** — نتيجة بحث فارغة ليست خطأ.
- **`local` picker**: Data State يبدأ `ready` مباشرةً (البيانات موجودة في memory).

---

## SEL-08 — المحور 3 — Selection State

| الحالة | الوصف |
|--------|-------|
| `empty` | لا يوجد اختيار حالي — الـ placeholder مرئي |
| `resolved` | يوجد اختيار + الـ option موجود في الـ catalog الحالي ومُعرَّف |
| `unresolved` | يوجد قيمة محفوظة لكن الـ option غير موجود أو معطَّل في الـ catalog |

### الفرق بين الحالات الثلاث

```
empty      → الـ picker لم يُختار منه أصلاً أو أُفرِغ بـ Reset
resolved   → value موجود + label موجود + option قابل للعرض الكامل
unresolved → value موجود في DB لكن الـ option:
               - مُعطَّل (disabled: true)، أو
               - غير موجود في catalog الحالي (حُذف أو تغيَّر)، أو
               - الـ catalog لا يزال في loading (_pendingSelection بانتظار resolution)
```

راجع SEL-16 للتفاصيل الكاملة لكل حالة.
راجع SEL-18 للتعامل مع `unresolved` في السياق الفعلي.

---

## SEL-09 — المحور 4 — Interaction State

| الحالة | الوصف |
|--------|-------|
| `enabled` | قابل للتفاعل — المستخدم يستطيع فتحه والاختيار منه |
| `disabled` | غير قابل للتفاعل — لا يُفتح، لا يُعدَّل، يُتجاوَز في Keyboard nav |
| `readonly` / `display-only` | يعرض القيمة الحالية ولا يسمح بتغييرها — للقراءة فقط |

### الفرق الجوهري بين disabled و readonly

| | `disabled` | `readonly` |
|--|-----------|-----------|
| يُفتح؟ | ❌ لا | ❌ لا |
| Visual cue | تعتيم (opacity) | border مختلف أو خلفية مختلفة |
| ARIA | `aria-disabled="true"` | `aria-readonly="true"` |
| Keyboard focus | لا يقبل focus | يقبل focus للقراءة |

**حد المسؤولية:** DS-SEL يملك **سلوك الـ UI** فقط — قابلية الفتح والتغيير والعرض.
قرار تضمين الحقل في الـ payload أو حذفه يملكه **DS-FRM وAPI-MUT** — راجع SEL-29 وSEL-31.

> مثال: picker `disabled` قد يُرسَل أو لا يُرسَل في payload حسب semantics الحقل في DS-FRM؛
> picker `readonly` قد يُرسَل في payload الحفظ لأنه part of the record — DS-SEL لا يقرر هذا.

---

## SEL-10 — المحور 5 — Validation Modifier

| الحالة | الوصف |
|--------|-------|
| `normal` | لا خطأ حالياً |
| `error` | يوجد خطأ validation مرئي على هذا الـ picker |

### توزيع المسؤولية

- **DS-SEL لا يُطلِق الـ validation** — DS-VAL يملك الـ timing (راجع SEL-30).
- **DS-SEL يُطبِّق حالة `error` البصرية** عبر class مثل `.has-error` عند إخباره من DS-VAL.
- **الـ error يُعرض على الـ Trigger** — border أحمر + رسالة خطأ أسفله (DS-INP + DS-VAL).
- **الـ error يختفي** حسب قواعد DS-VAL (VAL-12) — عند أول تغيير فعلي للاختيار.

---

## SEL-11 — المحور 6 — Search State

| الحالة | الوصف |
|--------|-------|
| `inactive` | لا يوجد بحث نشط — القائمة تعرض الخيارات كاملة |
| `active` | المستخدم يكتب في حقل البحث — القائمة مفلترة |

### ينطبق فقط على

- `mode: searchable`
- `mode: multi` مع بحث مدمج

### قواعد الانتقال

```
inactive → active  : المستخدم يبدأ الكتابة في حقل البحث (أي حرف)
active → inactive  : المستخدم يمسح حقل البحث كاملاً
active → inactive  : يُغلَق الـ picker (Disclosure → closed)
```

---

## SEL-12 — Search Query ≠ Canonical Selection

**هذه القاعدة من أهم قواعد DS-SEL — لا تتجاوزها:**

```
الكتابة في حقل البحث ≠ تأكيد اختيار
_searchQuery ≠ _canonicalSelection
```

### الفصل الصارم بين المتغيرات

| العنصر | المتغير | يُرسَل في payload؟ |
|--------|---------|------------------|
| نص البحث | `_searchQuery` | ❌ أبداً |
| قيمة الاختيار الـ canonical | `_canonicalSelection.value` | ✅ نعم |
| النص المعروض في Trigger | `_displayLabel` | ❌ للعرض فقط |

### دورة حياة البحث والاختيار

```
1. المستخدم يفتح picker                         → Disclosure: open
2. المستخدم يكتب "أرد"                          → _searchQuery = "أرد" (Search: active)
3. القائمة تُفلَّت بناءً على "أرد"
4. المستخدم يضغط على "الأردن"                   → _canonicalSelection = {value:"JO", label:"الأردن"}
5. picker يُغلق                                 → Disclosure: closed
6. _searchQuery يُصفَّر                         → Search: inactive
7. _displayLabel = "الأردن" (يُعرض في Trigger)
```

### الخطر الشائع

```js
// ❌ ممنوع — لا تأخذ نص البحث كـ canonical value
if (_searchQuery) payload.country = _searchQuery

// ✅ صحيح — الاختيار يحتاج ضغطة صريحة على خيار
payload.country = _canonicalSelection?.value ?? null
```

الكتابة في حقل البحث ثم Blur بدون اختيار → **لا تؤكد اختياراً** (راجع SEL-17).

---

## SEL-13 — Trigger & Control Contract

الـ **Trigger** هو العنصر المرئي الذي يُفتح منه الـ picker.

### متطلبات الـ Trigger

| العنصر | المتطلب |
|--------|---------|
| العنصر الأساسي | `<button>` أو `<div role="combobox">` |
| نص الحالة الفارغة | Placeholder text عربي |
| نص الحالة المختارة | `_displayLabel` للخيار الحالي |
| مؤشر الاتجاه | Arrow/chevron يعكس حالة Disclosure |
| حالة Error | `.has-error` class + border أحمر |
| حالة Disabled | `aria-disabled="true"` + تعتيم بصري |
| حالة Readonly | `aria-readonly="true"` + مظهر مميَّز |

### الفرق بين single و searchable

```
mode: single     → الـ Trigger زر — click يفتح القائمة
mode: searchable → الـ Trigger حقل نص — typing يفتح القائمة ويفلترها
```

في `searchable`، الـ Trigger هو حقل النص نفسه (combobox pattern).
**لا تُضف حقل بحث منفصل داخل القائمة** — البحث يكون في الـ Trigger مباشرةً.

---

## SEL-14 — Option List / Dropdown Contract

الـ **Option List** هو القائمة المنسدلة المحتوية على الخيارات.

### هيكل القائمة (مثال)

```html
<ul role="listbox" aria-label="الدول المتاحة">
  <li role="option" id="opt-JO" aria-selected="false">الأردن</li>
  <li role="option" id="opt-SA" aria-selected="true">السعودية</li>
  <li role="option" id="opt-SY" aria-selected="false" aria-disabled="true">سوريا</li>
</ul>
```

### قواعد عرض الخيارات

1. **Highlight الخيار النشط** (hover / keyboard focus) — بصرياً واضح.
2. **Disabled options مرئية** لكن غير قابلة للاختيار ومتجاوَزة في Keyboard nav.
3. **Scroll-into-view** عند التنقل بالـ keyboard.
4. **الخيار المختار** يُمار بـ `aria-selected="true"`.
5. **حالة loading** — skeleton loader داخل القائمة (لا تُخفي القائمة).
6. **حالة empty** — رسالة "لا توجد نتائج" داخل القائمة.
7. **حالة error (remote)** — رسالة خطأ آمنة + زر "إعادة المحاولة".

### ترتيب الخيارات (Baseline — بدون بحث)

- **`local` source** — الترتيب كما يُمرَّر من DS-REF.
- **`remote` source** — الترتيب يعود من الـ API.
- **لا تُعيد ترتيب الـ options تلقائياً** بدون بحث — الترتيب الأساسي قرار DS-REF وليس DS-SEL.

### V1 Search Ranking — ترتيب نتائج البحث

قاعدة "لا تُعيد ترتيب" تخص **الترتيب الأساسي** (baseline) بدون بحث نشط.
**عند تفعيل البحث (`Search: active`)**, DS-SEL يُرتِّب النتائج المفلترة بأولوية التطابق:

| الأولوية | معيار المطابقة | مثال (بحث: "سع") |
|---------|--------------|-----------------|
| 1 | تطابق تام بعد التطبيع | "سع" يساوي الـ label كاملاً (نادر) |
| 2 | الـ label يبدأ بنص البحث (`startsWith`) | "السعودية" يبدأ بـ "سع" |
| 3 | كلمة في الـ label تبدأ بنص البحث (word-starts-with) | "مملكة السعودية" — "السعودية" تبدأ بـ "سع" |
| 4 | الـ label يحتوي نص البحث في أي مكان (`includes`) | "عمان السعيدة" — يحتوي "سع" |
| 5 | مطابقة في `meta.keywords`/aliases فقط | label لا يطابق لكن الـ keywords تطابق |

**تنبيه:** هذا ترتيب بحث نصي داخل DS-SEL — لا علاقة له بـ "match score" أعمالي أو domain scoring (راجع SEL-36).

---

## SEL-15 — Hydration Contract

الـ **Hydration** هو تعيين قيمة محفوظة مسبقاً (من DB أو form state) إلى الـ picker.

### الخطأ الشائع الذي يمنعه هذا القسم

```js
// ❌ ممنوع — setTimeout هش وسيُخفق عند بطء الشبكة
setTimeout(() => {
  picker.value = savedValue
}, 80)
```

### شكل `_pendingSelection` — عقد ثابت

**`_pendingSelection` دائماً object بشكل واحد أو null — لا scalar أبداً:**

```js
// الشكل الوحيد المرخَّص:
picker._pendingSelection = {
  value:          "JO",       // القيمة الـ canonical من DB — إلزامي دائماً
  confirmedLabel: "الأردن"    // label مُؤكَّد من Backend — أو null إذا لم يُرسَل
}
```

### عقد الـ Hydration الصحيح

**خطوة 1 — بناء pending wrapper وعرض label فوري إذا متاح:**
```js
picker._pendingSelection = {
  value:          savedValue,        // e.g. "JO"
  confirmedLabel: backendLabel ?? null  // e.g. "الأردن" أو null
}

// إذا وصل confirmedLabel → اعرضه فوراً بدون انتظار Resolution
if (picker._pendingSelection.confirmedLabel) {
  picker._displayLabel = picker._pendingSelection.confirmedLabel
}
```

**خطوة 2 — تحميل الـ catalog:**
الـ picker يُحدِّث `Data State → loading` ويُطلِق جلب البيانات إذا `remote`.

**خطوة 3 — Resolution بعد اكتمال التحميل:**
```js
// عند انتهاء load الـ options
const pending = picker._pendingSelection
const match   = options.find(o => o.value === pending.value)  // دائماً pending.value
// تحقق من Active: الخيار موجود AND غير معطَّل
const isActive = match && !match.disabled

if (isActive) {
  // ✅ موجود في الـ catalog وقابل للاختيار → resolved
  picker._canonicalSelection = match                     // full OptionItem من الـ catalog
  picker._displayLabel       = match.label               // label من الـ catalog هو الـ canonical
  picker._selectionState     = 'resolved'
} else {
  // ❌ غير موجود في الـ catalog، أو موجود لكن disabled: true → unresolved (SEL-16 + SEL-18)
  // القيمة لا تضيع — تُحفَظ في _canonicalSelection
  // الخيار المعطَّل لا يصبح resolved — يبقى inactive/unresolved حتى يختار المستخدم بديلاً
  picker._canonicalSelection = {
    value: pending.value,
    label: pending.confirmedLabel  // قد يكون null — راجع SEL-16 unresolved
  }
  picker._displayLabel       = pending.confirmedLabel    // أو null إذا لم يتوفر
  picker._selectionState     = 'unresolved'
}

// تنظيف الـ wrapper — القيمة منقولة الآن إلى _canonicalSelection
picker._pendingSelection = null
```

### القواعد الصارمة

- **لا `setTimeout`** — Hydration يكتمل فقط بعد تأكيد جاهزية الـ catalog.
- **`_pendingSelection` دائماً `{value, confirmedLabel}` أو `null`** — ممنوع scalar (string/number مجرَّد).
- **Resolution يستخدم دائماً `pending.value`** — لا `pending` مباشرةً (لأنه object).
- **`resolved` يتطلب match نشط** — الخيار موجود في catalog AND `!match.disabled`. الخيار الموجود لكن `disabled:true` يبقى `unresolved`.
- **`_canonicalSelection.value` لا تضيع أبداً** — حتى في `unresolved` state.
- **`_displayLabel` لا يُعيَّن من `value` وحده** — يتطلب `confirmedLabel` أو `resolved` state.
- **لا Partial Hydration** — إما تُعيَّن القيمة كاملةً أو تبقى `empty`/`unresolved`.

---

## SEL-16 — Selection Resolution

### الحالات الثلاث مفصَّلة

#### `empty` — لا يوجد اختيار

```js
{
  _canonicalSelection: null,
  _displayLabel:       null,
  _selectionState:     'empty'
}
```
الـ picker لم يُختار منه — يعرض الـ placeholder.

#### `resolved` — اختيار مؤكَّد وموجود في الـ catalog

```js
{
  _canonicalSelection: { value: "JO", label: "الأردن" },
  _displayLabel:       "الأردن",
  _selectionState:     'resolved'
}
```
القيمة محفوظة + الخيار موجود في الـ catalog الحالي + يُعرض بشكل طبيعي.

#### `unresolved` — قيمة موجودة لكن الخيار غير متاح

```js
{
  _canonicalSelection: { value: "oldValue", label: "confirmedLabelOrNull" },  // value لا تضيع أبداً
  _displayLabel:       "confirmedLabelOrNull",  // قد يكون null إذا لم يُرسَل Backend label
  _selectionState:     'unresolved'
}
```

- **`_canonicalSelection.value`** — القيمة الـ canonical من DB، لا تضيع أبداً حتى في `unresolved`.
- **`_canonicalSelection.label`** — الـ `confirmedLabel` الذي أرسله Backend، أو `null` إذا لم يُرسَل.
- **`_displayLabel`** — يُعرض ما أرسله Backend (إن توفر)؛ أو `null` (يُعرض placeholder أو مؤشر unresolved).

الـ `unresolved` يحدث عندما:
- الخيار موجود في الـ catalog لكن `disabled: true` — **موجود ≠ selectable** (SEL-15 `isActive` check)
- الخيار غير موجود في الـ catalog الحالي أصلاً
- الـ catalog لا يزال في `loading` والـ `_pendingSelection` لم يُحلَّل بعد

**قاعدة:** الخيار الـ `disabled` لا يصبح `resolved` — يبقى `unresolved` حتى يختار المستخدم بديلاً نشطاً.

راجع SEL-18 لقواعد التعامل مع `unresolved`.

---

## SEL-17 — Blur Without Selection

**السيناريو:** المستخدم فتح الـ picker (searchable) وبدأ الكتابة — ثم نقر خارج القائمة بدون اختيار خيار.

### القرار

| الحالة السابقة للـ picker | ما يحدث عند Blur |
|--------------------------|----------------|
| كان `empty` (فارغاً) | يبقى `empty` — يعرض الـ placeholder |
| كان `resolved` (به اختيار سابق) | يُستعاد `_displayLabel` السابق — لا يتغير الاختيار |
| كان `unresolved` | يبقى `unresolved` — لا يتغير |

### سلوك Blur المطلوب

```js
function onPickerBlur() {
  _searchQuery = ''             // يُصفَّر حقل البحث دائماً
  _searchState = 'inactive'
  
  // الاختيار الـ canonical لا يتغير عند Blur
  // _canonicalSelection يبقى كما هو
  
  if (_selectionState !== 'empty') {
    // استعادة الـ displayLabel من canonicalSelection فقط — لا _savedDisplayLabel (غير مُعرَّف)
    _displayLabel = _canonicalSelection?.label ?? null
  }
  
  close()
}
```

**قاعدة:** الكتابة في حقل البحث ثم Blur **لا تُؤكِّد أي اختيار** (راجع SEL-12).

---

## SEL-18 — القيم المحفوظة غير النشطة (Saved Inactive Values)

**السيناريو:** المستخدم سبق أن اختار قيمة وحفظها في DB. لاحقاً، تلك القيمة:
- حُذفت من الـ catalog، أو
- مُعطَّلة (`disabled: true`)، أو
- خارج النطاق الحالي (مثال: تغيرت الدولة المختارة فصارت المدينة القديمة لا تنتمي للدولة الجديدة)

### القواعد الثلاث الإلزامية

**القاعدة 1 — أظهِر مع مؤشر بصري واضح:**

الـ picker يُعرِض القيمة المحفوظة مع مؤشر (مثل: نص باهت، أيقونة تحذير)
ولا يُفرِغ الـ picker تلقائياً.

```
[قيمة محفوظة ⚠️]  ← مرئي للمستخدم مع مؤشر unresolved
```

**القاعدة 2 — لا توقف التعديل:**

الـ picker في `unresolved` لا يمنع المستخدم من:
- تعديل حقول أخرى في نفس الفورم
- تعديل هذا الـ picker باختيار قيمة جديدة
- حفظ الفورم (الحفظ مسموح)

**القاعدة 3 — أغفِل في الـ payload إذا لم يُعدَّل:**

```js
if (picker._selectionState === 'unresolved') {
  if (userChangedPicker) {
    // اختار المستخدم قيمة جديدة → أرسِلها
    payload[field] = picker._canonicalSelection.value
  } else {
    // لم يُغيِّرها → omit من الـ payload (API-MUT Tri-state)
    // لا ترسل القيمة القديمة كأنها تغيير جديد
  }
}
```

### لماذا هذه القواعد؟

تمنع تجربة "الفورم المحجوب" — حيث لا يستطيع المستخدم حفظ أي شيء
بسبب حقل واحد بقيمة قديمة غير نشطة.
القيمة القديمة في DB لا تُمحى حتى يختار المستخدم بديلاً.

---

## SEL-19 — Remote Search & Race Safety

**المشكلة:**
المستخدم يكتب بسرعة → تُطلَق طلبات متعددة → تأتي النتائج بترتيب مختلف →
آخر نتيجة تصل ≠ آخر طلب أُرسِل (stale response يُلوِّث الـ UI).

### الحل — Per-instance Generation Counter

**قاعدة أساسية: العداد per-instance وليس global.**

```js
// ✅ صحيح — كل picker له عداده الخاص، وinvalidateSearchContext هي المالك الوحيد للـ ++
const pickerState = {
  _searchGen: 0,

  invalidateSearchContext(reason) {
    return ++this._searchGen  // يُعيد القيمة الجديدة لاستخدامها كـ generation token
  },

  async search(query) {
    const myGen = this.invalidateSearchContext('new-search')  // مالك واحد — لا ++_searchGen مباشرةً

    try {
      const results = await fetchOptions(query)
      if (myGen !== this._searchGen) return  // stale — تجاهَل
      this._renderOptions(results)
    } catch (err) {
      if (myGen !== this._searchGen) return  // stale
      this._showRemoteError()  // رسالة آمنة — لا raw err للمستخدم
    }
  }
}

// ❌ ممنوع — عداد global يتداخل بين pickers مختلفة
window._globalSearchGen++
```

### القواعد الخمس

1. **كل picker instance له `_searchGen` مستقل** — لا يتأثر بأي picker آخر.
2. **كل بحث جديد يزيد العداد** (`++_searchGen`).
3. **أول شيء عند وصول النتائج** — تحقق أن `myGen === _searchGen`؛ إذا لا → تجاهَل.
4. **العداد لا يُعاد إلى 0** خلال عمر الـ picker — يزيد فقط (راجع FRM-10 للمبدأ).
5. **AbortController اختياري** — يُضاف إذا كان الطلب ثقيلاً ومُكلِفاً.

### مع AbortController (اختياري)

```js
const pickerState = {
  _searchGen:   0,
  _searchAbort: null,

  async search(query) {
    this._searchAbort?.abort()
    this._searchAbort = new AbortController()
    const myGen = this.invalidateSearchContext('new-search')  // مالك واحد

    try {
      const results = await fetchOptions(query, {signal: this._searchAbort.signal})
      if (myGen !== this._searchGen) return
      this._renderOptions(results)
    } catch (err) {
      if (err.name === 'AbortError') return   // طلب ملغى — طبيعي
      if (myGen !== this._searchGen) return
      this._showRemoteError()
    }
  }
}
```

### الإبطال عند الـ Lifecycle Transitions — Lifecycle Invalidation

الـ generation check يحمي حالة "search while searching" فقط:
المستخدم يكتب بسرعة → طلبات متعددة في الجو → العداد يميز الأحدث.

**ثغرة لا تُعالجها هذه الحالة:**
إذا حدث Reset أو Destroy بعد طلب ولم يُطلَق بحث جديد،
يبقى العداد بدون تغيير → يصل الـ response القديم بـ `myGen === _searchGen` → stale result يُطبَّق.

### الأحداث التي تستوجب `invalidateSearchContext(reason)`

| الحدث | السبب المُمرَّر |
|-------|----------------|
| بحث جديد (أي كتابة في searchable) | `'new-search'` |
| `resetPickerState()` | `'reset'` |
| Destroy / unmount | `'destroy'` |
| تغيير parent في Dependent Select (SEL-20) | `'dependency-change'` |
| `close()` standalone بعد بحث نشط | `'close'` |
| `close()` داخلي من `resetPickerState()` | **لا invalidation** — الـ Reset سبق وأبطل |

### قاعدة المالك الواحد — `invalidateSearchContext(reason)`

`++_searchGen` لها مالك واحد فقط: الـ concept **`invalidateSearchContext(reason)`** (Pseudocode — ليس Runtime API name).
لا تستدعي `++_searchGen` مباشرةً من أي transition — ادمجها في هذا الـ concept الواحد:

```js
// Pseudocode concept — يُركِّز كل increment في نقطة واحدة
function invalidateSearchContext(reason) {
  ++_searchGen   // increment فقط، لا reset إلى 0 (راجع FRM-10)
  // _searchAbort?.abort()  // اختياري مع AbortController
}
```

| من يستدعي `invalidateSearchContext`؟ | السبب |
|--------------------------------------|--------|
| `search(query)` — كل بحث جديد | `'new-search'` |
| `resetPickerState()` — مرة واحدة | `'reset'` |
| Destroy / unmount | `'destroy'` |
| `onParentChange()` — SEL-20 | `'dependency-change'` |
| `close()` — standalone بعد بحث نشط | `'close'` |

**قاعدة Double-increment المحظور:**
`close()` الذي يُستدعى كجزء داخلي من `resetPickerState()` **لا تستدعي** `invalidateSearchContext` مرة ثانية.
الـ Reset يستدعيها مرة واحدة قبل `close()` — والـ `close()` الداخلي يُنفَّذ بدون invalidation إضافية.

```js
// ❌ ممنوع — reset إلى 0 يُتيح collision مع طلبات قديمة
this._searchGen = 0

// ✅ صحيح — increment عبر المالك الواحد
invalidateSearchContext('reset')
```

---

## SEL-20 — Dependent Selects

الـ Dependent Select علاقة بين pickerَين: **parent** و **child**.
اختيار قيمة في الـ parent يُقيِّد الخيارات المتاحة في الـ child.

**مثال كلاسيكي:** قائمة الدولة (parent) → قائمة المدينة (child)

### القواعد الأربع

**القاعدة 1 — الـ child يُفرَّغ فوراً في form state عند تغيير الـ parent:**

```js
function onParentChange(newValue) {
  // فوري في form state — قبل أي fetch للـ child options
  childPicker._canonicalSelection = null
  childPicker._displayLabel       = null
  childPicker._selectionState     = 'empty'

  // إبطال أي request بحث قديم للـ child قبل تحميل options جديدة
  // Pseudocode concept — المالك الوحيد لـ ++_searchGen، راجع SEL-19
  childPicker.invalidateSearchContext('dependency-change')

  // ثم جلب الـ child options المناسبة لـ newValue
  childPicker.loadOptions({parentValue: newValue})
}
```

**الفراغ في form state أولاً** — لا تنتظر جلب الـ options الجديدة قبل الإفراغ.
**Invalidation قبل loadOptions** — أي response قديم يصل بعد تغيير الـ parent يُتجاهَل فوراً.

**القاعدة 2 — الـ child يكون `disabled` بدون parent:**

إذا لم يُختر قيمة في الـ parent →
الـ child يكون في `Interaction: disabled` مع رسالة مثل "اختر الدولة أولاً".

**القاعدة 3 — Hydration الـ child يحتاج قيمة الـ parent أولاً:**

عند فتح فورم تعديل بسجل موجود:
1. Hydrate الـ parent أولاً (انتظار resolution).
2. اجلب خيارات الـ child بناءً على قيمة الـ parent.
3. ثم Hydrate الـ child (SEL-15).

**القاعدة 4 — تعريف الـ dependency خارج DS-SEL:**

DS-SEL لا يملك منطق "أي picker parent لأي child" —
هذا تعريفه في DS-FRM أو في منطق الصفحة.
DS-SEL يستقبل فقط `loadOptions({parentValue})` أو القائمة المفلترة.

---

## SEL-21 — Arabic Normalization

عند فلترة الخيارات بالبحث، يجب تطبيع نص البحث ونص الـ label/keywords.

### التطبيع الإلزامي

| الخطوة | ما يحدث | مثال |
|--------|---------|------|
| 1 — Trim | إزالة المسافات من البداية والنهاية | `" الأردن "` → `"الأردن"` |
| 2 — Collapse whitespace | تحويل المسافات المتعددة إلى مسافة واحدة | `"الأردن  عمان"` → `"الأردن عمان"` |
| 3 — إزالة التطويل (tatweel) | حذف حرف التطويل `ـ` (U+0640) | `"بيـروت"` → `"بيروت"` |
| 4 — إزالة التشكيل | حذف حركات الإعراب والمد والسكون | `"أُردُنّ"` → `"اردن"` |
| 5 — توحيد أشكال الألف | `أ إ آ ٱ` → `ا` | `"إردن"` → `"اردن"` |

### ما هو ممنوع كتطبيع إلزامي عالمي

```
❌ ة → ه    (التاء المربوطة ليست هاء — يتغير المعنى في بعض السياقات)
❌ ى → ي    (الألف المقصورة ليست ياء — يتغير المعنى في بعض السياقات)
```

هذه التحويلات **مقبولة كاختيار** في بعض السياقات إذا قرَّر الفريق الهندسي ذلك لـ catalog معين،
لكن ممنوع تطبيقها عالمياً كجزء من الـ normalization function القياسية في DS-SEL.

### مثال تطبيق صحيح

```js
function normalizeArabic(text) {
  if (!text) return ''
  return text
    .trim()
    .replace(/\s+/g, ' ')                // collapse whitespace
    .replace(/\u0640/g, '')              // إزالة التطويل (tatweel U+0640)
    .replace(/[ً-ٰٟ]/g, '')  // إزالة التشكيل والمد والسكون
    .replace(/[أإآٱ]/g, 'ا')           // توحيد أشكال الألف
    .toLowerCase()
}

function matchesSearch(option, query) {
  const nq    = normalizeArabic(query)
  const nl    = normalizeArabic(option.label)
  const nkeys = (option.meta?.keywords ?? []).map(normalizeArabic)

  return nl.includes(nq) || nkeys.some(k => k.includes(nq))
}
```

---

## SEL-22 — لا إنشاء قيمة حرة (No Free-text Creation) — V1

**القاعدة:** DS-SEL V1 لا يدعم إنشاء قيمة جديدة من النص المكتوب في حقل البحث.

```
❌ المستخدم يكتب "مدينة غير موجودة" ثم يضغط Enter → يُضاف كخيار جديد
❌ "Add [input] to list" pattern
❌ Creatable Select / Free-solo Input داخل DS-SEL V1
```

### لماذا ممنوع في V1

- يتجاوز DS-REF كمصدر الـ canonical catalog (F5).
- يُنشئ بيانات غير معيارية في DB بدون validation مناسب.
- يتطلب نظام Moderation وValidation مختلف عن DS-VAL.

إذا احتاج سياق معين إدخال قيمة حرة →
يجب استخدام حقل نصي منفصل (DS-INP) — ليس DS-SEL.

---

## SEL-23 — لا Auto-selection للخيار الأول

**القاعدة الصارمة:** DS-SEL لا يختار الخيار الأول تلقائياً في أي سيناريو.

```
❌ عند فتح picker لأول مرة → لا يُختار الخيار الأول
❌ عند البحث وتبقى نتيجة واحدة → لا تُختار تلقائياً
❌ عند تغيير الـ parent في Dependent Select → لا يُختار أول خيار في الـ child
❌ عند Hydration فاشل (unresolved) → لا fallback للخيار الأول
❌ عند Reset → يعود لـ empty وليس للخيار الأول
```

### السبب

الاختيار الضمني يُلوِّث الـ payload بقيمة لم يختَرها المستخدم صراحةً (F5، API-MUT).

**الاستثناء الوحيد المقبول:**
إذا كانت هناك قيمة واحدة **فقط** ممكنة AND أعلنت منطق الأعمال ذلك صراحةً
AND موثَّق في ARCHITECTURE.md — هذا قرار domain وليس سلوك DS-SEL الافتراضي.

---

## SEL-24 — Custom Tawasolna UI دائماً

**القاعدة الصارمة:** الـ native browser picker (`<select>` HTML) لا يُستخدم **أبداً** كعنصر مرئي رئيسي في تجربة المستخدم.

```
❌ <select> مرئي للمستخدم في أي صفحة تواصلنا
❌ الاعتماد على native mobile picker (iOS wheel / Android dropdown)
❌ تغليف <select> بـ CSS فقط بدون custom JS dropdown
```

### الاستثناء الوحيد المقبول

نسخة no-JS للتدهور السلس (graceful degradation) —
`<select>` كـ fallback مخفي تحت `.ep-select` مع custom UI فوقه
(النمط الحالي في `tw-select.js`).

### لماذا

- `<select>` native لا يدعم RTL بشكل متسق عبر المتصفحات.
- لا يدعم Arabic search normalization.
- لا يدعم icons أو flags.
- لا يتوافق مع design system تواصلنا.
- لا يدعم combobox / searchable pattern قابل للتخصيص.

---

## SEL-25 — Portal Contract

الـ **Portal** هو تقنية عرض الـ dropdown خارج DOM parent الأصلي
لتجاوز `overflow: hidden` أو `overflow: auto` في أي container في الصفحة.

### المشكلة

```html
<!-- ❌ القائمة محجوبة بـ overflow:hidden على الـ modal -->
<div style="overflow:hidden; position:relative">
  <div class="picker">
    <!-- dropdown محجوبة هنا ولا تظهر كاملة -->
  </div>
</div>
```

### الحل — Portal إلى `document.body`

```js
// الـ dropdown يُرفَق مباشرةً بـ document.body
const dropdownEl = createDropdownElement()
document.body.appendChild(dropdownEl)

// يُحسَب موقعه بـ getBoundingClientRect() من الـ Trigger
const triggerRect = triggerEl.getBoundingClientRect()
dropdownEl.style.position = 'fixed'
dropdownEl.style.top      = triggerRect.bottom + 'px'
dropdownEl.style.insetInlineStart = triggerRect.left + 'px'

// يُزال عند الإغلاق
function close() {
  document.body.removeChild(dropdownEl)
}
```

### توزيع المسؤولية في Portal

| المسؤولية | المالك |
|-----------|--------|
| قرار استخدام Portal | DS-SEL |
| إضافة الـ dropdown إلى `document.body` | DS-SEL |
| حساب الموقع (getBoundingClientRect) | DS-SEL |
| إزالة الـ dropdown عند الإغلاق | DS-SEL |
| cleanup عند unmount الصفحة | DS-SEL |
| طلب "semantic layer" (dropdown layer) | DS-SEL |
| تحديد z-index الفعلي لـ dropdown layer | DS-OVL |

### قراءة z-index من DS-OVL

```js
// DS-SEL لا يُشفِّر z-index أرقاماً مباشرةً
// يقرأ القيمة من CSS custom property تُعرِّفها DS-OVL:
const zIndex = getComputedStyle(document.documentElement)
                .getPropertyValue('--tw-drop-z').trim()
// ملاحظة: إذا لم تُعرَّف --tw-drop-z بعد (DS-OVL مؤجَّل)،
// القيمة الاحتياطية يُحدِّدها DS-OVL — لا رقم مُشفَّر هنا (راجع SEL-35).

dropdownEl.style.zIndex = zIndex
```

### قواعد Portal إضافية

```js
// إغلاق عند scroll (أي scroll في الصفحة)
window.addEventListener('scroll', close, {passive: true, capture: true})

// إغلاق عند resize
window.addEventListener('resize', close, {passive: true})

// إغلاق عند Outside click
document.addEventListener('click', (e) => {
  if (!triggerEl.contains(e.target) && !dropdownEl.contains(e.target)) {
    close()
  }
}, {capture: true})
```

---

## SEL-26 — Keyboard Navigation

DS-SEL يُعرِّف ثلاثة أنماط Keyboard مختلفة بحسب نوع الـ picker.
**لا يوجد جدول عالمي واحد** — كل نمط له قواعده الخاصة.
المرجع النهائي للتفاصيل: Current WAI-ARIA / APG Combobox + Listbox patterns وقت تنفيذ الـ Runtime.

---

### النمط A — `single` (Select-only)

| المفتاح | السلوك |
|---------|--------|
| `Tab` | ينتقل focus إلى الـ Trigger |
| `Space` / `Enter` على Trigger | يفتح القائمة (`Disclosure → open`) |
| `ArrowDown` / `ArrowUp` | ينقل DOM focus إلى الخيارات — التالي / السابق |
| `Home` | ينتقل بـ DOM focus إلى أول خيار مرئي |
| `End` | ينتقل بـ DOM focus إلى آخر خيار مرئي |
| `Enter` على خيار | يُؤكِّد الاختيار → يُغلِق القائمة |
| `Escape` | يُغلِق القائمة بدون اختيار |
| `Tab` أثناء فتح القائمة | يُغلِق القائمة وينتقل للعنصر التالي |

**نموذج Focus:** DOM focus ينتقل فعلياً إلى عناصر `role="option"` داخل القائمة.

---

### النمط B — `searchable` (Editable Combobox)

| المفتاح | السلوك |
|---------|--------|
| `Tab` | ينتقل focus إلى الـ Trigger (combobox input) |
| أي حرف قابل للطباعة + `Space` | يُدخَل في حقل البحث — يُفتح الـ dropdown إذا كان مغلقاً |
| `ArrowDown` / `ArrowUp` | virtual focus عبر `aria-activedescendant` — DOM focus يبقى على الـ input |
| `Home` / `End` | يُحرِّك cursor الـ text داخل الـ input — لا يُسرَق لصالح القائمة |
| `Enter` | يُؤكِّد الخيار الـ virtually-highlighted → يُغلِق القائمة |
| `Escape` | يُغلِق القائمة بدون اختيار |
| `Tab` أثناء فتح القائمة | يُغلِق القائمة وينتقل للعنصر التالي |

**نموذج Focus:** DOM focus يبقى على الـ combobox input طوال التنقل.
`aria-activedescendant` يتتبع virtual focus على الخيارات — لا نقل DOM focus إلى `role="option"`.

---

### النمط C — `multi` (Multi-select Listbox)

| المفتاح | السلوك |
|---------|--------|
| `Tab` | ينتقل focus إلى الـ Trigger |
| أي حرف قابل للطباعة + `Space` | يُدخَل في حقل البحث (إذا وُجد) |
| `ArrowDown` / `ArrowUp` | virtual focus عبر `aria-activedescendant` — DOM focus يبقى على الـ input/trigger |
| `Home` / `End` | cursor في حقل البحث (إذا وُجد)؛ أو virtual focus إلى أول/آخر خيار |
| `Enter` | يُضيف أو يُزيل الخيار المُحدَّد **بدون إغلاق القائمة** |
| `Escape` | يُغلِق القائمة بدون تغيير `_selections` |
| `Tab` أثناء فتح القائمة | يُغلِق القائمة |

**نموذج Focus:** DOM focus يبقى على الـ Trigger/input — `aria-activedescendant` للتنقل بين الخيارات.

---

### القواعد المشتركة (جميع الأنماط)

1. **Wrap-around:** `ArrowDown` من الأخير → يعود للأول؛ `ArrowUp` من الأول → ينتقل للآخر.
2. **disabled options:** مُتجاهَلة في التنقل — السهم يتجاوزها تلقائياً.
3. **Scroll-into-view:** كل انتقال يُظهِر الخيار المُحدَّد داخل القائمة المنسدلة.
4. **`aria-activedescendant`:** يُحدَّث عند كل انتقال بـ id الخيار المُحدَّد (راجع SEL-27).
5. **المرجع النهائي:** Current WAI-ARIA / APG Combobox + Listbox patterns — هذا الـ contract يُطبَّق وقت Runtime implementation.

---

## SEL-27 — Accessibility / ARIA

### الـ Pattern المطلوب: Combobox + Listbox (Current WAI-ARIA / APG)

```html
<!-- Trigger -->
<div
  role="combobox"
  aria-haspopup="listbox"
  aria-expanded="false"
  aria-controls="sel-list-1"
  aria-activedescendant=""
  aria-label="اختر دولة"
  tabindex="0"
>
  اختر دولة
</div>

<!-- Option List -->
<ul
  id="sel-list-1"
  role="listbox"
  aria-label="الدول المتاحة"
>
  <li role="option" id="opt-JO" aria-selected="false">الأردن</li>
  <li role="option" id="opt-SA" aria-selected="true">السعودية</li>
  <li role="option" id="opt-SY" aria-selected="false" aria-disabled="true">سوريا</li>
</ul>
```

### جدول متطلبات ARIA الإلزامية

| الـ Attribute | الـ Element | القيمة | يتغير؟ |
|--------------|------------|--------|--------|
| `role="combobox"` | Trigger | ثابت | لا |
| `aria-haspopup="listbox"` | Trigger | ثابت | لا |
| `aria-expanded` | Trigger | `"true"` / `"false"` | ✅ ديناميكياً |
| `aria-controls` | Trigger | id الـ listbox | لا |
| `aria-activedescendant` | Trigger | id الخيار المُحدَّد | ✅ عند كل انتقال |
| `aria-label` | Trigger | نص وصفي عربي | لا |
| `role="listbox"` | قائمة الخيارات | ثابت | لا |
| `aria-label` | listbox | نص وصفي عربي | لا |
| `role="option"` | كل خيار | ثابت | لا |
| `id` | كل خيار | فريد | لا |
| `aria-selected` | كل خيار | `"true"` / `"false"` | ✅ عند الاختيار |
| `aria-disabled` | خيار معطَّل | `"true"` | لا |
| `aria-invalid` | Trigger | `"true"` عند error | ✅ DS-VAL يُضيفه |

### ملاحظة على tw-select.js الحالي

`tw-select.js` يملك `role="listbox"` و `role="option"` لكنه يفتقر إلى:
- `aria-activedescendant` على الـ Trigger (Gap موثَّق — SEL-32)
- `role="combobox"` صريح (Gap موثَّق)
- `aria-haspopup="listbox"` (Gap موثَّق)

يجب معالجة هذه الـ Gaps عند Runtime implementation.

### نموذج Focus حسب نوع الـ picker

| الوضع | نموذج Focus | آلية التنقل |
|-------|------------|------------|
| `single` | DOM focus ينتقل إلى `role="option"` | ArrowKeys تُحرِّك DOM focus بين الخيارات |
| `searchable` | DOM focus يبقى على الـ combobox input | `aria-activedescendant` يتتبع virtual focus |
| `multi` | DOM focus يبقى على الـ Trigger/input | `aria-activedescendant` للتنقل بين الخيارات |

**قاعدة ثابتة لـ `searchable`:**
لا تنقل DOM focus إلى `role="option"` أثناء الكتابة —
الكتابة في الـ input يجب أن تستمر بدون انقطاع.
استخدم `aria-activedescendant` على الـ combobox input وحدِّثه مع كل انتقال ArrowKey.

راجع SEL-26 النمط B و C للتفاصيل الكاملة.

---

## SEL-28 — Multi-select Contract

`mode: multi` يسمح باختيار أكثر من خيار واحد.

### Selection State في Multi

```js
_selections = [
  { value: "JS",  label: "JavaScript" },
  { value: "PY",  label: "Python" },
  { value: "SQL", label: "SQL" }
]
```

### عرض المختارات في Trigger

- **Chips/Tags** للمختارات مرئية في الـ Trigger.
- كل chip له زر `✕` للإزالة الفردية.
- إذا كثرت المختارات → عرض `+N` مع عدد الباقي.
- زر لمسح كل المختارات (Clear All) اختياري.

### في Option List

- الخيارات المختارة تُمار بـ checkmark أو تعبئة.
- الضغط عليها مرة أخرى يُلغي اختيارها.
- القائمة لا تُغلَق عند كل اختيار (بخلاف single-select).

### الـ Payload في Multi

```js
// multi-select → أرسِل array من القيم
payload.skills = _selections.map(s => s.value)  // ["JS", "PY", "SQL"]

// إذا كانت القائمة فارغة بعد إلغاء كل الاختيارات
payload.skills = []  // أو null حسب API-MUT contract للحقل
```

### قواعد Multi-select

1. **الاختيار مُراكَم** — كل ضغطة تُضيف أو تُزيل من `_selections`.
2. **لا حد افتراضي** — الحد يُحدَّد من سياق الاستخدام (مثلاً: max 5 مهارات).
3. **Escape يُغلِق** بدون تغيير `_selections` الحالية.
4. **`aria-multiselectable="true"`** على الـ listbox.
5. **كل خيار مختار** له `aria-selected="true"` (في `role="listbox"` مع `aria-multiselectable="true"` — لا تستخدم `aria-checked` وهو للـ checkbox/menuitem فقط).
6. **Keyboard navigation** — راجع SEL-26 النمط C للقواعد الكاملة (virtual focus، Enter بدون إغلاق، Space في البحث).

---

## SEL-29 — التكامل مع DS-FRM

DS-SEL ينخرط في دورة حياة الفورم عبر نقاط تكامل محددة:

### نقطة 1 — Reset (FRM-05)

```js
// DS-FRM يستدعي reset على DS-SEL
function resetPickerState() {
  _canonicalSelection = null
  _displayLabel       = null
  _selectionState     = 'empty'
  _searchQuery        = ''
  _searchState        = 'inactive'
  _pendingSelection   = null
  invalidateSearchContext('reset')  // Pseudocode — المالك الوحيد لـ ++_searchGen (راجع SEL-19)
  if (isOpen) close()  // close() الداخلي هنا لا يُعيد invalidation — مرة واحدة فقط لهذا الـ Reset
}
```

**DS-FRM يملك قرار "متى تُعاد"** — DS-SEL يملك "كيف تُعاد".

### نقطة 2 — Hydration (FRM-06 + SEL-15)

DS-FRM يُمرِّر بيانات الـ Hydration إلى DS-SEL وفق العقد الرسمي الثابت في SEL-15:

```js
// الشكل الوحيد المرخَّص — Pseudocode concept (ليس Runtime API name)
picker._pendingSelection = {
  value:          canonicalValue,           // القيمة الـ canonical من DB — إلزامي
  confirmedLabel: backendConfirmedLabel ?? null  // label من Backend — أو null
}
```

**ممنوع** أن يُمرِّر DS-FRM قيمة scalar مباشرةً:

```js
// ❌ ممنوع — scalar يكسر Resolution ويخالف SEL-15
picker._pendingSelection = "JO"
picker._pendingSelection = savedValue
```

DS-SEL يكمل الـ Resolution بعد جاهزية الـ catalog (SEL-15 خطوة 3).

### نقطة 3 — Dirty State (FRM-13)

DS-SEL **لا يقرر** Dirty/Pristine — هذا ملك DS-FRM حصراً (FRM-13).
DS-SEL يُبلِّغ DS-FRM بأن القيمة تغيَّرت؛ DS-FRM يُعيد حساب Dirty/Pristine مقارنةً بالقيمة الأصلية عند الـ Hydration.
إذا أعاد المستخدم اختيار القيمة الأصلية، قد يعود الفورم `Pristine` — DS-SEL لا يقرر ذلك.

```js
// Pseudocode concept — اسم الدالة ليس Runtime API
function onSelectionConfirmed(newOption) {
  _canonicalSelection = newOption
  _selectionState     = 'resolved'
  // DS-SEL يُبلِّغ DS-FRM بالقيمة الجديدة؛ DS-FRM يحسب Dirty/Pristine بنفسه
  formLifecycleHook.onFieldValueChanged(newOption.value)  // إشعار — ليس قرار Dirty
  onChange?.(newOption.value)    // integration hook
}
```

**ممنوع** استدعاء ما يعادل `markDirty()` مباشرةً من DS-SEL — ذلك تدخل في FRM-13.

### نقطة 4 — Payload Building (FRM-09 + API-MUT)

DS-FRM يملك منطق الـ Payload Building — DS-SEL يُوفِّر الحالة والقيمة الحالية **فقط** عبر مفهوم موحَّد لجميع الـ modes.
القرار يعتمد على مقارنة **مُعيَّرة** (normalized) للقيمة الحالية بالأصلية — لا `strict ===` ولا `_selectionState` وحدها.

#### Canonical Value — ما يُوفِّره DS-SEL

DS-SEL يُوفِّر القيمة الحالية حسب الـ mode. اسم `getCanonicalValue()` Pseudocode concept — ليس Runtime API:

```
// Pseudocode concept — اسم getCanonicalValue() ليس Runtime API موجوداً

// single / searchable → scalar أو null
picker.getCanonicalValue()   //  picker._canonicalSelection?.value ?? null

// multi → array من canonical IDs/codes (SEL-28 — _selections)
picker.getCanonicalValue()   //  picker._selections.map(s => s.value)   // [] إذا لا اختيارات
```

DS-SEL لا يُقرِّر شكل المقارنة ولا معنى ترتيب العناصر في الـ multi — هذا ملك DS-FRM وفق field contract.

#### Comparison & Payload — ما يملكه DS-FRM

```
// Pseudocode concept — buildPickerPayload, getCanonicalValue, valuesEqualNormalized
// أسماء Pseudocode جميعها — ليست Runtime API موجودة
// originalHydratedValue: حفظه DS-FRM عند Hydration (FRM-06) — scalar | array
// fieldContract: { clearable, emptyPayloadValue, orderSignificant? }
function buildPickerPayload(picker, fieldName, { originalHydratedValue, fieldContract }) {
  const { clearable, emptyPayloadValue, orderSignificant } = fieldContract
  const currentValue = picker.getCanonicalValue()   // Pseudocode — scalar لـ single، array لـ multi

  // ① unresolved لم يمسّه المستخدم → omit (SEL-18)
  if (picker._selectionState === 'unresolved') return

  // ② القيمة لم تتغير (مقارنة مُعيَّرة) → omit (FRM-09: "omitted = no change")
  // valuesEqualNormalized: Pseudocode — ليس Runtime API
  // single: normalized string comparison (trim ± case حسب fieldContract)
  // multi: set comparison إذا !orderSignificant — ordered comparison إذا orderSignificant
  if (valuesEqualNormalized(currentValue, originalHydratedValue, { orderSignificant })) return

  // ③ فارغ بعد Clear (null لـ single/searchable، [] لـ multi) → null أو []
  const isEmpty = Array.isArray(currentValue)
    ? currentValue.length === 0
    : currentValue === null
  if (isEmpty) {
    if (clearable) payload[fieldName] = emptyPayloadValue   // null | [] حسب API-MUT-03
    // غير clearable → omit
    return
  }

  // ④ قيمة مختلفة عن الأصلية → أرسِل canonical value فقط، لا labels (API-MUT)
  // single/searchable: scalar string/number
  // multi: string[] من canonical IDs/codes
  payload[fieldName] = currentValue
}
```

#### Multi Order Contract

`valuesEqualNormalized()` (Pseudocode) تعتمد على `fieldContract.orderSignificant`:

| `orderSignificant` | المقارنة | مثال |
|---|---|---|
| `false` (الأكثر شيوعاً — مهارات، لغات، اهتمامات) | set comparison | `["JS","PY"]` == `["PY","JS"]` → equal |
| `true` (الترتيب جزء من القيمة — أولوية، تسلسل) | ordered comparison | `["JS","PY"]` ≠ `["PY","JS"]` → different |

DS-SEL لا يُقرِّر قيمة `orderSignificant` — DS-FRM يُحدِّدها حسب field contract حصراً.

#### قواعد Payload Building — الملكية DS-FRM

| الحالة | الشرط | الإجراء |
|--------|--------|---------|
| `unresolved` | لم يمسّه المستخدم | **omit** (SEL-18) |
| أي حالة | `valuesEqualNormalized(...)` → true | **omit** (FRM-09) |
| `null` / `[]` | `clearable: true` | `null` أو `[]` حسب API-MUT-03 |
| `null` / `[]` | `clearable: false` | **omit** |
| single/searchable changed | scalar مختلف عن الأصلي | **أرسِل scalar** |
| multi changed | array مختلف عن الأصلي | **أرسِل `string[]`** |

**الأخطاء الشائعة:**

```
❌ picker._canonicalSelection?.value ?? null لـ multi — يُحوِّل multi إلى null
❌ currentValue === originalHydratedValue لـ arrays — مقارنة مرجعية (reference) لا دلالية (semantic)
❌ DS-SEL يُقرِّر orderSignificant — هذا ملك DS-FRM وfield contract
❌ resolved → payload مباشرةً (بدون مقارنة بالأصلية) — يُرسِل قيماً لم تتغير
❌ empty/[] → omit دائماً — يُفوِّت Clear متعمد (يجب null/[] للـ clearable)
❌ switch على _selectionState وحدها — المعيار هو valuesEqualNormalized مقارنةً بـ originalHydratedValue
```

---

## SEL-30 — التكامل مع DS-VAL

### كيف يصل الـ error إلى DS-SEL

```
Backend response
  → API-MUT normalizeErrorResponse()
  → DS-VAL routeErrors()
  → DS-VAL resolveFieldControl()
  → DS-SEL يُطبِّق .has-error على الـ Trigger
  → DS-INP يُعرِض رسالة الخطأ أسفله
```

### توزيع المسؤولية الدقيقة

| المسؤولية | المالك |
|-----------|--------|
| timing إظهار الـ error | DS-VAL |
| تحديد "أي picker يخص أي API field" | DS-VAL (VAL-07a) |
| إضافة `.has-error` على الـ Trigger | DS-SEL (بتعليمات من DS-VAL) |
| عرض نص رسالة الخطأ | DS-VAL + DS-INP |
| `aria-invalid="true"` على الـ Trigger | DS-SEL (يُضاف عند error) |
| إزالة `.has-error` | DS-SEL يُبلِّغ DS-VAL عند تغيير الاختيار → DS-VAL يقرر |

**DS-SEL لا يتحكم في timing الـ validation** — يُطبِّق الحالة البصرية فقط.

---

## SEL-31 — حدود المسؤولية (Ownership Boundaries)

### الجدول الشامل

| المسألة | المالك | المرجع |
|---------|--------|--------|
| UI behavior (open/close/select) | DS-SEL | SEL-06 |
| Trigger contract | DS-SEL | SEL-13 |
| Option rendering | DS-SEL | SEL-14 |
| Search & filtering logic | DS-SEL | SEL-12 + SEL-19 |
| Keyboard navigation | DS-SEL | SEL-26 |
| ARIA attributes | DS-SEL | SEL-27 |
| Integration hooks (onChange/onBlur) | DS-SEL | SEL-29 + SEL-30 |
| بيانات الـ catalog (دول/مهارات/مهن) | DS-REF | tw-options-data.js · tw-skills.js |
| الـ canonical IDs والـ codes | DS-REF | — |
| Active/inactive state للـ entries | DS-REF | — |
| Hierarchy (country → city) | DS-REF | TW.CITIES |
| دورة حياة الفورم كاملة | DS-FRM | FORM-LIFECYCLE.md |
| Dirty / Pristine state | DS-FRM | FRM-13 |
| Payload building | DS-FRM | FRM-09 |
| Validation timing | DS-VAL | VAL-05 |
| Error routing من API إلى الـ picker | DS-VAL | VAL-07a |
| Focus-first-invalid | DS-VAL | VAL-10 |
| z-index hierarchy العالمي | DS-OVL | (غير موثَّق بعد) |
| Bottom Sheet mechanics (mobile) | DS-OVL | (غير موثَّق بعد) |
| Flag images | DS-ASSET | flags/*.svg |
| Skill icons | DS-ASSET | TW.getSkillIcon() |
| Visual assets داخل الـ Options | DS-ASSET | — |
| omit/value/null semantics في payload | API-MUT | API-MUT-03 |
| Mutation response shapes | API-MUT | API-MUT-08 + API-MUT-10 |

---

## SEL-32 — الـ Runtime الحالي — tw-select.js

> **توثيق للحالة القائمة فقط** — لا تعديل على أي Runtime في هذا PR.

الـ Runtime الحالي هو `static/shared/tw-select.js` (321 سطر، `scSelectInit()` نقطة دخول).

### ما يُوفِّره tw-select.js حالياً ✅

| الميزة | الحالة |
|--------|--------|
| Single-select | ✅ مُنفَّذ |
| Portal إلى `document.body` (position:fixed) | ✅ مُنفَّذ |
| `role="listbox"` و `role="option"` | ✅ موجود |
| CSS custom property `--tw-drop-z` (fallback 9500) | ✅ موجود |
| MutationObserver + modal-open watcher | ✅ موجود (بقيود — راجع أدناه) |
| Scroll-to-close | ✅ موجود |

### ما يفتقره tw-select.js ❌

| الـ Gap | الأثر على DS-SEL |
|--------|-----------------|
| `aria-activedescendant` مفقود | Accessibility gap — SEL-27 |
| `role="combobox"` غير صريح | ARIA pattern ناقص — SEL-27 |
| `aria-haspopup="listbox"` مفقود | ARIA pattern ناقص — SEL-27 |
| Hydration عبر `setTimeout(80ms)` | هش — يُخالِف SEL-15 |
| MutationObserver يُغطي overlays وقت التحميل فقط | Modal ديناميكي بعد التحميل لا يُرصَد — SEL-25 |
| لا `mode: searchable` | لا بحث — SEL-02 |
| لا `mode: multi` | لا تعدد اختيار — SEL-28 |
| لا touch handling مخصَّص | قد يُعطَّل على mobile — F8 |
| لا per-instance `_searchGen` | غير ذي صلة (لا search) — SEL-19 |

### القرار المعماري

`tw-select.js` يبقى بدون تعديل حتى يُقرَّر تنفيذ DS-SEL Runtime في PR مستقل.
مناسب لـ `mode: single` البسيط مع إدراك الـ Gaps المُوثَّقة.

---

## SEL-33 — الأنظمة القديمة (Legacy Systems)

### النظام الأول: `profile-v2.select.js`

| المعلومة | التفاصيل |
|---------|---------|
| المسار | `/profile-v2.select.js` (جذر المشروع) |
| الحالة | **Legacy — غير مُحمَّل من أي صفحة HTML حالياً** |
| المشاكل | z-index مشفَّر (600)، لا `_syncAll()`، غير متزامن مع `tw-select.js` |
| القرار | **ممنوع حذفه** في PR توثيقي — يحتاج قراراً مستقلاً موثَّقاً |
| المسار المستقبلي | عند Runtime Implementation لـ DS-SEL → إعادة تقييم حذفه |

### النظام الثاني: `co-dp-*` في `company.main.js`

| المعلومة | التفاصيل |
|---------|---------|
| المسار | `static/company/company.main.js` — IIFEs منفصلة |
| الحالة | **نظام picker ثالث مستقل** — Custom dark inline design |
| المزايا | تصميم مميَّز يناسب Company Profile UI |
| الثغرات | لا Portal، لا ARIA، لا Keyboard navigation |
| القرار | **ممنوع حذفه** — يخدم سياقاً خاصاً |
| المسار المستقبلي | عند Runtime Implementation لـ DS-SEL → إعادة تقييم دمجه |

### خلاصة: ثلاثة أنظمة متوازية

المنصة تملك حالياً **ثلاثة أنظمة picker متوازية**:

| النظام | المسار | الوضع |
|--------|--------|-------|
| `tw-select.js` | `static/shared/` | الأكثر شيوعاً — single-select فقط |
| `profile-v2.select.js` | جذر المشروع | غير مستخدم فعلياً |
| `co-dp-*` | `static/company/company.main.js` | مخصَّص Company Profile |

**V1 Documentation لا يُوحِّد هذه الأنظمة** —
التوحيد يتطلب Runtime PR مستقل بقرار صريح.

---

## SEL-34 — حالة V1 ومسار الانتقال

### ما أنجزه V1 (هذا PR) ✅

- تعريف الـ contract المعماري الكامل لـ DS-SEL
- تعريف جميع الـ State Axes (6 محاور)
- تعريف OptionItem Interface
- تعريف Hydration Contract (بدون setTimeout)
- تعريف Race Safety pattern (per-instance generation counter)
- تعريف Dependent Selects contract (قدرة وليست وضعاً)
- تعريف Arabic Normalization rules
- توثيق الـ Runtime القائم (tw-select.js) وثغراته بالتفصيل
- توثيق Legacy Systems والقرار بشأنها
- تعريف حدود المسؤولية مع DS-REF وDS-FRM وDS-VAL وDS-OVL وDS-ASSET

### ما يتطلب PR مستقل 🔜

| المهمة | الحالة |
|--------|--------|
| Runtime implementation: searchable mode | PR مستقل |
| Runtime implementation: multi-select | PR مستقل |
| ترقية tw-select.js (ARIA gaps) | PR مستقل |
| توحيد الأنظمة القديمة (co-dp-*, profile-v2.select.js) | قرار مستقل |
| CSS layer (`tw-ui-tokens.css` لـ DS-SEL tokens) | FUTURE_ROADMAP |
| Bottom Sheet على mobile (DS-OVL أولاً) | بعد توثيق DS-OVL |

### مسار الانتقال المقترح

```
V1 (هذا PR):      Contract موثَّق — لا تعديل Runtime
V2 (PR مستقل):    ترقية tw-select.js (ARIA + Hydration)
V3 (PR مستقل):    searchable mode implementation
V4 (PR مستقل):    multi-select mode implementation
```

---

## SEL-35 — Forbidden Patterns

```
❌ لا تأخذ _searchQuery كـ canonical value في الـ payload
❌ لا تستخدم setTimeout لانتظار جاهزية الـ catalog في Hydration
❌ لا تُؤكِّد اختياراً عند Blur بدون ضغطة صريحة على خيار
❌ لا تُختار الخيار الأول تلقائياً في أي حالة
❌ لا تُنشئ "وضعاً" رابعاً باسم "dependent" — الـ Dependency علاقة وليست mode
❌ لا تستخدم <select> native كعنصر مرئي رئيسي
❌ لا تُشفِّر z-index أرقاماً مباشرةً في DS-SEL — اقرأ من CSS var تُعرِّفها DS-OVL
❌ لا تُحدِّث _displayLabel من value مجرَّد (bare value) بدون backend-confirmed label أو resolved state
❌ لا تستخدم عداد global للـ remote search — كل picker له _searchGen مستقل
❌ لا تُنشئ قيمة حرة من النص المكتوب في حقل البحث (SEL-22)
❌ لا تُعرِّف منطق "أي picker parent لأي child" داخل DS-SEL — ذلك DS-FRM
❌ لا تُطبِّق ة→ه أو ى→ي كتطبيع عالمي إلزامي (SEL-21)
❌ لا تحذف profile-v2.select.js في PR توثيقي
❌ لا تُرسِل label في الـ payload — أرسِل value فقط (API-MUT)
❌ لا تفتح أكثر من picker واحد في نفس الوقت
❌ لا تُحوِّل timing الـ validation إلى DS-SEL — يبقى ملكاً لـ DS-VAL
❌ لا تُؤدِّ aria-activedescendant بـ empty string ثابت — حدِّثه عند كل انتقال
❌ لا تُفرِّغ الـ child picker في UI قبل form state (الفراغ في state أولاً)
❌ لا تُرسِل قيمة unresolved في payload كأنها تغيير جديد (SEL-18)
❌ لا تُنفِّذ Runtime implementation في PR توثيقي
❌ لا تُعيِّن `_pendingSelection` كـ scalar (string أو number مجرَّد) — الشكل الوحيد المرخَّص: `{value, confirmedLabel}` أو `null` (SEL-15)
❌ لا تستخدم `_savedDisplayLabel` — متغير غير مُعرَّف؛ استخدم `_canonicalSelection?.label ?? null` (SEL-17)
❌ لا تتجاهل `++_searchGen` عند Reset أو تغيير Dependency أو Destroy — إبطال lifecycle إلزامي (SEL-19)
❌ لا تُمرِّر DS-FRM قيمة scalar مباشرةً كـ `_pendingSelection` — الشكل الإلزامي: `{value, confirmedLabel}` (SEL-15 × SEL-29)
❌ لا تعتبر الخيار الـ `disabled: true` resolved — موجود في catalog ≠ selectable active (SEL-15 `isActive` check × SEL-16)
❌ لا تستدعي ما يعادل `markDirty()` من DS-SEL — DS-SEL يُبلِّغ بتغيير القيمة فقط؛ DS-FRM يحسب Dirty/Pristine (SEL-29 × FRM-13)
❌ لا تزيد `_searchGen` مرتين لنفس transition — استخدم `invalidateSearchContext(reason)` كمالك واحد؛ `close()` الداخلي من Reset لا يُعيد الإبطال (SEL-19)
❌ لا تُضِف resolved picker إلى payload دون مقارنة القيمة الحالية بـ originalHydratedValue — resolved ≠ always send (FRM-09: omitted = no change)
❌ لا تعتبر empty دائماً omit — empty بعد Clear المتعمد يُرسَل كـ null/[] حسب API-MUT-03 للحقل (SEL-29 × FRM-09)
❌ لا تستخدم `picker._canonicalSelection?.value ?? null` في Generic Payload Contract — multi canonical value هو `picker._selections.map(s => s.value)` (SEL-28 × SEL-29)
❌ لا تقارن canonical values بـ `===` في Payload Building — مقارنة مرجعية لا دلالية؛ استخدم مقارنة مُعيَّرة حسب fieldContract (SEL-29 × FRM-13)
❌ لا تُقرِّر DS-SEL قيمة `orderSignificant` للـ multi — هذا ملك DS-FRM وfield contract حصراً (SEL-29 × FRM-13)
```

---

## SEL-36 — خارج النطاق — V1

الأمور التالية خارج نطاق DS-SEL V1:

| العنصر | النظام المسؤول |
|--------|---------------|
| Bottom Sheet على mobile | DS-OVL (غير موثَّق بعد — راجع DESIGN_SYSTEM.md) |
| Global z-index hierarchy | DS-OVL |
| Date picker / Time picker | DS-DATE (غير موثَّق بعد) |
| Dial code / Phone input | DS-PHONE (غير موثَّق بعد) |
| OTP / Pin input | DS-OTP (غير موثَّق بعد) |
| Upload / File picker | DS-UPLOAD |
| Rich text / WYSIWYG | DS-RICH |
| ترتيب الخيارات بـ business/domain match score (مثال: ملاءمة السيرة الذاتية للوظيفة — ليس ترتيب بحث نصي داخل DS-SEL؛ راجع SEL-14) | Domain logic في page module |
| بيانات الـ catalog نفسها (ليس عرضها) | DS-REF |
| Content moderation لنصوص البحث | DS-MODERATION |
| Profanity filter | DS-MODERATION |
| إنشاء قيمة حرة من حقل البحث | خارج DS-SEL V1 نهائياً (SEL-22) |

---

*DS-SEL V1 — توثيق فقط — أُنشئ في PR #508 — 2026-07-22.*
*الـ Runtime implementation مؤجَّل لـ PR مستقل بطلب صريح.*
*الـ Runtime القائم: `static/shared/tw-select.js` — لا تعديل عليه في هذا PR.*
