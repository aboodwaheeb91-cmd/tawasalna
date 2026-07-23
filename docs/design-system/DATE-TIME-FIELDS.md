# [DS-DATE] Date & Time Fields System V1

> **ملاحظة للـ AI:** هذا الملف عقد معماري رسمي — ليس توثيق Runtime.
> كل أمثلة الكود أدناه هي **Pseudocode/Concepts** ما لم يُنص صراحةً على أنها Runtime.
> ممنوع بناء Runtime مباشرةً من هذا الملف دون PR مستقل يحدد ذلك.

---

## DATE-00 — Routing Protocol

**اقرأ هذا القسم أولاً قبل أي تنفيذ يمس حقل تاريخ أو وقت.**

| إذا كنت تعمل على... | الأقسام المطلوبة |
|---------------------|-----------------|
| حقل سنة فقط (founded، course year) | DATE-03A + DATE-05 + DATE-06 |
| حقل شهر + سنة (بداية/نهاية خبرة أو دراسة) | DATE-03B + DATE-08 + DATE-10 |
| حقل تاريخ كامل (DOB) | DATE-03C + DATE-08 + DATE-09 |
| حقل وقت | DATE-03D + DATE-12 |
| حقل موعد (تاريخ + وقت) | DATE-03E + DATE-13 + DATE-14 |
| فترة بداية/نهاية | DATE-03F + DATE-10 + DATE-11 |
| Hydration / تعبئة من قيمة محفوظة | DATE-17 |
| Payload / إرسال للـ Backend | DATE-23 + DATE-16 |
| Clear / إفراغ الحقل | DATE-21 |
| Disabled / Readonly | DATE-24 + DATE-25 |
| Validation / أخطاء | DATE-26 + DATE-27 + DATE-28 |
| ربط بـ DS-FRM / Dirty State | DATE-22 |
| سؤال عن "حتى الآن" | DATE-11 |
| سؤال عن Timezone | DATE-14 |

**إذا لم يكن نوع حقلك في هذا الجدول → STOP واسأل صاحب المشروع (F30).**

---

## DATE-01 — Purpose & Scope

### ما هو DS-DATE؟

DS-DATE هو النظام المعماري الرسمي لكل حقول التاريخ والوقت التي يتفاعل معها المستخدم في منصة تواصلنا.

### ماذا يملك DS-DATE؟

- **القرار المعماري الأساسي:** Custom DS-SEL Dropdowns فقط — لا Calendar popup، لا native picker.
- **أنواع الحقول الرسمية:** 7 أنواع معرَّفة (DATE-03).
- **توليد الخيارات الزمنية:** الأيام، الأشهر، السنوات، الوقت — من الكود مباشرةً.
- **Dependency Logic الزمنية:** عدد أيام الشهر، leap year، Start/End dependency.
- **Data Precision Contract:** سنة ≠ تاريخ كامل — لا قيم وهمية.
- **Hydration Contract:** تعبئة حقول التاريخ من قيمة محفوظة بترتيب dependency صحيح.
- **Canonical Temporal Value:** ما تُعيده كل أداة تاريخ كقيمة نقية.
- **State Model:** 4 محاور مستقلة للحالة (DATE-19).

### ما لا يملكه DS-DATE (تفويض للأنظمة الأخرى)

| المسؤولية | النظام المالك |
|-----------|--------------|
| Dropdown behavior (فتح/إغلاق/Keyboard/Portal/ARIA) | DS-SEL |
| Dirty State / originalHydratedValue | DS-FRM |
| متى يظهر الخطأ ورسالته | DS-VAL |
| شكل Payload النهائي (null/omit/value) | DS-FRM + API-MUT |
| ملكية DB column / API field name | Feature Contract |
| timezone conversion للـ Backend | Feature/API Contract |
| Overlay / Bottom Sheet mechanics | DS-OVL (غير موثَّق بعد) |
| قائمة Timezones | DS-REF (غير موثَّق بعد) |

---

## DATE-02 — Core Principle: DS-SEL as the Foundation

### القرار المعماري الأساسي

**كل حقول التاريخ والوقت التي يتفاعل معها المستخدم في تواصلنا تستخدم Custom DS-SEL Dropdowns.**

DS-DATE يبني فوق DS-SEL. ممنوع أن يخترع DS-DATE Dropdown Engine جديد.

### ما يُبنى فوق DS-SEL (DS-DATE يضيفه)

| DS-SEL يوفر | DS-DATE يضيف |
|------------|-------------|
| Dropdown open/close behavior | توليد خيارات الأيام (1-28/29/30/31) |
| Keyboard navigation | توليد أسماء الأشهر + canonical values |
| Search (Searchable mode) | توليد السنوات حسب Field Contract |
| Option rendering | Leap year logic |
| Portal (position:fixed) | Month→Day dependency |
| ARIA/combobox contract | Start→End dependency |
| Focus management | Canonical Temporal Value composition |
| Disabled presentation | Range validation rules |
| Readonly contract | Hydration ordering (parent before child) |

### ما هو ممنوع في DS-DATE V1

```
❌ Calendar popup / calendar grid
❌ native <input type="date"> كواجهة للمستخدم
❌ native <input type="time"> كواجهة للمستخدم
❌ <input type="number"> لإدخال السنة
❌ native <select> مرئي للمستخدم (غير DS-SEL)
❌ كتابة نص حر للتاريخ
❌ Android/iOS native date picker
❌ Browser native date picker (مهما كان المتصفح)
❌ Bottom Sheet / DS-OVL مستقل داخل DS-DATE (DS-OVL غير موثَّق بعد)
```

### موقف Calendar View المستقبلي

أي Calendar View مستقبلي ليس جزءاً من V1 ولا مخططاً محسوماً.
إذا أُريد في المستقبل يحتاج قراراً معمارياً منفصلاً وموثَّقاً في ARCHITECTURE.md.
لا تضع Calendar كـ "V2 مخطط" داخل عقد DS-DATE.

---

## DATE-03 — Field Types (الأنواع الرسمية في V1)

DS-DATE V1 يعرِّف 7 أنواع حقول زمنية رسمية:

---

### DATE-03A — Year-Only (سنة فقط)

**الواجهة:**
```
[ السنة ▼ ]
```

**الاستخدامات الحالية:**
- سنة تأسيس الشركة / المؤسسة
- سنة الدورة التدريبية
- أي Feature يحتاج Year Precision فقط

**القاعدة الأساسية:**
ممنوع اختراع شهر أو يوم وهمي لتحويل السنة إلى Full Date.
`2022` يبقى `2022` — لا `2022-01-01`.

---

### DATE-03B — Month + Year (شهر + سنة)

**الواجهة:**
```
[ الشهر ▼ ] [ السنة ▼ ]
```

**الاستخدامات:**
- بداية الخبرة / نهايتها
- بداية الدراسة / نهايتها
- أي Feature يحتاج Month Precision

**القاعدة الأساسية:**
ممنوع تخزين يوم 01 وهمي فقط لأن الحقل يحتاج Month-Year.
`مارس 2022` يبقى `{year:2022, month:3}` — لا `2022-03-01`.

---

### DATE-03C — Day + Month + Year (تاريخ كامل)

**الواجهة:**
```
[ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]
```

**الاستخدامات:**
- تاريخ الميلاد (DOB)
- أي تاريخ يحتاج Full Date Precision

**قاعدة Dependency:**
Month + Year يحددان الأيام المتاحة (DATE-08 — Leap Year + Month Days).

---

### DATE-03D — Time (وقت فقط)

**الواجهة — خياران حسب Field Contract:**
```
// 12-hour:
[ الساعة ▼ ] [ الدقيقة ▼ ] [ ص/م ▼ ]

// 24-hour:
[ الساعة ▼ ] [ الدقيقة ▼ ]
```

**القاعدة:**
Format (12h/24h) وMintue Step يحددهما Field Contract — ليس DS-DATE عالمياً.
القيمة الـ Canonical مستقلة عن format العرض (DATE-12).

---

### DATE-03E — DateTime (تاريخ + وقت = Date Group + Time Group)

**الواجهة:**
```
[ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]
[ الساعة ▼ ] [ الدقيقة ▼ ] [ ص/م ▼ ]
```

DateTime = تركيب رسمي من Date Group + Time Group.
لا يحتاج Date Picker مختلفاً.
Timezone semantics تخص Feature/API Contract (DATE-14).

---

### DATE-03F — Temporal Range (فترة بداية/نهاية)

**الواجهة (Year Range مثالاً):**
```
بداية: [ السنة ▼ ]
نهاية: [ السنة ▼ ]  ← مُقيَّد بـ Start
```

**Month-Year Range:**
```
بداية: [ الشهر ▼ ] [ السنة ▼ ]
نهاية: [ الشهر ▼ ] [ السنة ▼ ]  ← مُقيَّد بـ Start
```

**Full Date Range:**
```
بداية: [ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]
نهاية: [ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]  ← End ≥ Start
```

**القاعدة:**
Start وEnd يجب أن يستخدموا نفس Precision (لا Year Start + Full Date End).
تفاصيل الـ Dependency في DATE-10.

---

### DATE-03G — Open-ended Range (فترة مفتوحة النهاية)

مفهوم مدمج في Temporal Range عندما يكون الوضع الحالي مستمراً:

```
بداية: [ الشهر ▼ ] [ السنة ▼ ]
□ لا تزال مستمرة ← Domain State (Feature يملك الاسم)
نهاية: [ الشهر ▼ ] [ السنة ▼ ]  ← تُخفى/تُعطَّل عند Domain State = مستمر
```

**DS-DATE يملك:**
- منطق إخفاء/إظهار مجموعة النهاية بناءً على Open-ended state
- قيمة End = null عند الحالة المستمرة

**DS-DATE لا يملك:**
- اسم الـ Domain State (مثل `is_current` — هذا ملك الـ Feature)
- Label العرض (مثل "أعمل هنا حالياً" — ملك الـ Feature)
- API field name — ملك الـ Feature Contract

---

## DATE-04 — Data Precision Contract

### القانون الأساسي

**Precision هي جزء من معنى البيانات — لا يُخفَّض ولا يُرفَع.**

| القيمة المحفوظة | تبقى كـ | ممنوع تحويلها إلى |
|----------------|---------|-------------------|
| `2022` (year-only) | `2022` | `2022-01-01` |
| `{year:2022, month:3}` (month-year) | `{year:2022, month:3}` | `2022-03-01` |
| `{year:1991, month:11, day:10}` (full date) | `1991-11-10` | `1991-11-10T00:00:00` (datetime) |

### لماذا هذه القاعدة مهمة؟

- سنة التأسيس `2005` لا تعني `2005-01-01 00:00:00`.
- بداية الخبرة `مارس 2022` لا تعني اليوم الأول من مارس.
- اختراع قيم وهمية = تشويه معنى البيانات + صعوبة الـ migration لاحقاً.

### Legacy Adapter / Compatibility Boundary

إذا كان Legacy API حالي يتطلب صراحةً تاريخاً كاملاً لحقل Month-Year (مثل: "أرسِل `2022-03-01` لتمثيل مارس 2022")، هذا يُعالَج عبر **Legacy Adapter مستقل** — طبقة تحويل بين الـ Canonical Temporal Value وحاجة الـ Legacy API.

```
// Concept — ليس Runtime API
// Legacy Adapter (مستقل عن DS-DATE)
function toMonthYearLegacy(canonicalMonthYear):
  // { year: 2022, month: 3 } → "2022-03-01"
  // Convention رسمي محدد في Feature/API Contract
```

**الـ Canonical Precision تبقى كما هي:**
`مارس 2022` يبقى `{year:2022, month:3}` داخل DS-DATE.
التحويل يحدث فقط في طبقة الـ Adapter — ليس داخل DS-DATE وليس كاستثناء معماري.

هذا Compatibility Boundary — ليس إذناً بتغيير معنى البيانات في القاعدة.

---

## DATE-05 — Generated vs DB-sourced Temporal Data

### المبدأ

بيانات التاريخ والوقت البسيطة **تُولَّد في الكود** — لا تأتي من DB Reference Tables.

| البيانات | المصدر | السبب |
|---------|--------|-------|
| أيام الشهر (1-28/29/30/31) | Generated (مرتبط بـ month+year) | حسابية بحتة |
| أسماء الأشهر (يناير...ديسمبر) | Generated Constant | ثابتة — 12 شهر فقط |
| السنوات | Generated Loop (حسب Field Contract min/max) | بسيطة + configurable |
| ساعات (0-23 أو 1-12) | Generated Loop | ثابتة |
| دقائق (حسب minuteStep) | Generated Loop | configurable |

### ممنوع

```
❌ إنشاء جدول DB باسم "years" أو "months" أو "days"
❌ fetch من endpoint لجلب قائمة سنوات
❌ fetch من endpoint لجلب قائمة أشهر
❌ أسماء الأشهر العربية كـ source of truth في DB
❌ ربط DS-DATE بـ DS-REF لهذه البيانات البسيطة
```

### الخط الفاصل بين DS-DATE وDS-REF

- DS-DATE يولد: الأيام، الأشهر، السنوات، الساعات، الدقائق.
- DS-REF (مستقبلاً) يخدم: الدول، المدن، الجنسيات، المؤسسات، Timezones.

---

## DATE-06 — Year Range Policy

### القانون الأساسي

**DS-DATE لا يفرض Year Range عالمي واحد.**

كل حقل/Feature يحدد `minYear` و `maxYear` الخاص به في Field Contract.

### Pseudocode — ليس Runtime API

```
// Pseudocode — concept فقط، ليس Runtime API
FieldContract = {
  yearMin: number,                    // مثلاً 1950
  yearMax: number | 'now' | 'now+N', // مثلاً 'now' أو 'now+6'
  ...
}

// DS-DATE يولد السنوات ضمن المجال المعطى فقط
generateYears(yearMin, yearMax) → number[]
```

### أمثلة من الـ Legacy Evidence (ليست قواعد عامة)

| الحقل | minYear | maxYear | السبب |
|-------|---------|---------|-------|
| DOB | 1900 | now | تاريخ ميلاد |
| Experience | 1980 | now | بداية مسيرة مهنية |
| Education Start | 1950 | now | ضمن العمر المعقول |
| Education End | من start | now+6 | يسمح بتاريخ تخرج مستقبلي |
| Courses | 1990 | now | دورات حديثة |
| Founded (company) | 1900 | now | شركات قديمة موجودة |

**هذه أمثلة — كل Feature Contract يحدد قيمته الخاصة بحسب منطق النطاق.**

### `now+N` — مسموح متى؟

بعض Domains تسمح بسنة مستقبلية (سنة تخرج متوقعة).
Field Contract يحدد ذلك صراحةً.
DS-DATE فقط يولد الخيارات ضمن المجال المحدد.

---

## DATE-07 — Month Labels Contract

### المبدأ

الشهر له **canonical value** منفصل عن **display label**.

| canonical value | display label (عربي) |
|---------------|---------------------|
| 1 | يناير |
| 2 | فبراير |
| 3 | مارس |
| 4 | أبريل |
| 5 | مايو |
| 6 | يونيو |
| 7 | يوليو |
| 8 | أغسطس |
| 9 | سبتمبر |
| 10 | أكتوبر |
| 11 | نوفمبر |
| 12 | ديسمبر |

### القواعد

```
✅ canonical value هو رقم الشهر (1-12)
✅ display label هو الاسم العربي للعرض فقط
✅ القيمة المُرسَلة للـ Backend هي الـ canonical value (حسب Field/API Contract)
❌ ممنوع: "نوفمبر" كـ source of truth في Payload أو DB
❌ ممنوع: الاعتماد على ترتيب DOM لاستخراج رقم الشهر
```

### نفس المبدأ ينطبق على الساعات في 12-hour mode

| canonical value | display |
|---------------|---------|
| 14 | 2 م |
| 9 | 9 ص |
| 0 | 12 ص / منتصف الليل |

---

## DATE-08 — Dependent Options: Days per Month (Leap Year)

### الـ Dependency الأولى: Month + Year → Days Available

عدد أيام الشهر يعتمد على الشهر والسنة معاً (بسبب فبراير في السنوات الكبيسة).

**Pseudocode — ليس Runtime API:**

```
// Pseudocode — concept فقط

function daysInMonth(year, month):
  if month in [1,3,5,7,8,10,12]: return 31
  if month in [4,6,9,11]: return 30
  if month == 2: return isLeapYear(year) ? 29 : 28

function isLeapYear(year):
  return (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0)
```

### أمثلة

| Year + Month | أيام متاحة |
|-------------|-----------|
| 2025 + فبراير (2) | 1-28 |
| 2024 + فبراير (2) | 1-29 (سنة كبيسة) |
| أي سنة + أبريل (4) | 1-30 |
| أي سنة + يناير (1) | 1-31 |

### متى تُعاد بناء الأيام

- عند تغيير الشهر → أعِد بناء الأيام
- عند تغيير السنة + الشهر الحالي = فبراير → أعِد بناء الأيام
- عند تغيير السنة + الشهر الحالي ≠ فبراير → لا يحتاج إعادة بناء

### الضمان الذي يوفره DS-DATE

المستخدم لا يستطيع تكوين تاريخ مستحيل مثل `31 فبراير` أو `30 فبراير` — لأن DS-DATE لا يعرض هذه الأرقام أصلاً عند اختيار فبراير.

---

## DATE-09 — On Parent Change: Clear or Keep

### القاعدة الأساسية

**إذا القيمة التابعة ما زالت صالحة بعد تغيير الـ Parent → احتفظ بها.**
**إذا أصبحت غير صالحة → امسحها.**
**ممنوع اختيار قيمة بديلة تلقائياً.**

### السيناريوهات

| الحالة | السلوك الصحيح |
|--------|--------------|
| مستخدم اختار 15 يناير ثم غير الشهر لفبراير | 15 ما زال صالحاً → احتفظ به |
| مستخدم اختار 31 يناير ثم غير الشهر لفبراير | 31 غير صالح → امسح اليوم |
| مستخدم اختار 29 فبراير 2024 ثم غير السنة لـ 2025 | 29 فبراير 2025 غير موجود → امسح اليوم |
| مستخدم اختار 28 فبراير 2024 ثم غير السنة لـ 2025 | 28 فبراير 2025 صالح → احتفظ به |

### ممنوع

```
❌ التحويل التلقائي: "المستخدم اختار 31 يناير → أحوله لـ 28 فبراير"
❌ اختيار أول يوم صالح تلقائياً
❌ اختيار آخر يوم صالح في الشهر تلقائياً
❌ اختيار أي قيمة بديلة دون طلب من المستخدم
```

### متى يظهر خطأ Validation؟

مسح القيمة التابعة لأنها أصبحت غير صالحة **لا يُظهر خطأ فوراً**.
توقيت الخطأ ملك DS-VAL — ليس DS-DATE.
DS-DATE يمسح القيمة فقط.

---

## DATE-10 — Start / End Temporal Dependency

### المبدأ العام

**End مُقيَّد بـ Start.** خيارات End لا تعرض قيماً أقدم من Start.

هذا Pattern عام — ليس خاصاً بالدراسة أو الخبرة.

**Pseudocode — ليس Runtime API:**
```
// Pseudocode — concept فقط

Temporal Parent:  Start field
Temporal Dependent: End field
Constraint: End.value >= Start.value
```

### مثال Year Range

```
Start = 2022
End Options: 2022, 2023, 2024, 2025, ... (حسب maxYear)
End Options: ❌ 2021, ❌ 2020, ❌ 2019  ← محجوبة
```

### مثال Month-Year Range

```
Start = مارس 2022 (month=3, year=2022)
End Options متاحة: مارس 2022, أبريل 2022, ..., يناير 2023, ...
End Options محجوبة: يناير 2022, فبراير 2022  ← أقدم من Start
```

### إذا تغير Start بعد اختيار End

```
مثال:
  Start = 2022
  End = 2025 (مختار)

  Start تغير → 2023
  End = 2025 ما زال صالحاً (2025 > 2023) → احتفظ بـ End

  Start تغير → 2026
  End = 2025 أصبح غير صالح (2025 < 2026) → امسح End
```

**ممنوع اختيار بديل تلقائياً عند مسح End.**

### Precision التوافق

Start وEnd يجب أن يكونا بنفس الـ Precision:
- Year Range: كلاهما year-only
- Month-Year Range: كلاهما month+year
- Full Date Range: كلاهما full date

**ممنوع:** Start = year-only + End = month-year في نفس الـ Range Field.

---

## DATE-11 — Open-ended Range ("حتى الآن")

### المبدأ الرسمي

```
❌ ممنوع تماماً: قيمة "حتى الآن" كـ Canonical Temporal Value
❌ ممنوع: magic string في DB
❌ ممنوع: DS-DATE يُنتج "حتى الآن" كـ date value
```

### العقد الصحيح (Pseudocode — Concept)

```
// Pseudocode — concept فقط — أسماء الـ API تحددها Feature Contract

Open-ended Range يُعبَّر عنه بـ:
  Start = قيمة صالحة
  End = null/absent
  Domain State = مستمر (is_current / ongoing / active — حسب Feature)

// DS-DATE يملك: إخفاء/إظهار End Group
// DS-DATE لا يملك: اسم الـ Domain State أو API field
```

### المسؤوليات

| الجانب | المالك |
|--------|--------|
| Display label ("أعمل هنا حالياً"، "أدرس حالياً") | Feature / UI |
| Toggle behavior (checkbox/switch) | Feature / DS-SEL |
| إخفاء/إظهار مجموعة End | DS-DATE |
| قيمة End = null | DS-DATE (يُنتج null) |
| API field name (`is_current`، `ongoing`...) | Feature Contract |
| تخزين Domain State في DB | Feature Contract |

### مثال تطبيقي

```
// Pseudocode concept — أسماء API وDomain State تحددها Feature Contract
// Label: "أعمل هنا حالياً" (مثال — Feature يملك النص)
// Domain State: feature-defined — مثل: is_current أو ongoing أو active

السلوك عند تفعيل Domain State (الحالة مستمرة):
  1. DS-DATE: يُخفي End Group
  2. DS-DATE: يُنتج End = null  ← Canonical End Value
  3. Feature: يُرسل { end_date: null, is_current: true }
     ← أسماء الـ fields (end_date, is_current) تحددها Feature/API Contract

السلوك عند تعطيل Domain State:
  1. DS-DATE: يُظهر End Group
  2. DS-DATE: يُعيد بناء End options من Start
  3. End = فارغ (المستخدم يختار)
```

---

## DATE-12 — Time Field Contract

### الـ Field Contract يحدد

```
// Pseudocode — ليس Runtime API
TimeFieldContract = {
  format: '12h' | '24h',     // طريقة العرض
  minuteStep: number,         // مثلاً: 1, 5, 10, 15, 30
  minTime?: { hour, minute }, // حد أدنى (اختياري)
  maxTime?: { hour, minute }, // حد أقصى (اختياري)
}
```

### Minute Step — ليس رقماً عالمياً ثابتاً

| الاستخدام | minuteStep مقترح |
|-----------|----------------|
| موعد دقيق | 5 أو 10 |
| موعد عام | 15 أو 30 |
| حقل وقت دقيق | 1 |

DS-DATE لا يفرض واحداً منها. Field Contract يحدد.

### Seconds

خارج نطاق V1 ما لم يوجد استخدام حالي موثَّق يتطلبه.

### Canonical Time Value (Pseudocode)

```
// Pseudocode — concept فقط
{ hour: number, minute: number }
// hour: دائماً 0-23 (24-hour) بغض النظر عن format العرض
// minute: 0-59
// الـ display (ص/م) عرض فقط — لا يؤثر على الـ canonical value
```

---

## DATE-13 — DateTime = Date Group + Time Group

### المبدأ

DateTime ليس نوعاً مستقلاً — هو تركيب من:

```
DateTime = Date Group (DATE-03C) + Time Group (DATE-03D)
```

### الواجهة

```
Date Group:
[ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]

Time Group:
[ الساعة ▼ ] [ الدقيقة ▼ ] [ ص/م ▼ ]
```

### الـ Canonical Value (Pseudocode)

```
// Pseudocode — concept فقط
{
  year: number,
  month: number,   // 1-12
  day: number,     // 1-31
  hour: number,    // 0-23
  minute: number,  // 0-59
}
```

### حدود مسؤولية DS-DATE في DateTime

DS-DATE يُنتج **Local Temporal Components** فقط:

```
// Canonical DateTime Value (Pseudocode)
{ year, month, day, hour, minute }
// هذه قيم محلية — DS-DATE لا يعرف الـ timezone ولا يُحوِّل للـ UTC
```

**ما يجب على Feature/API Contract تحديده:**
- هل الوقت محلي أم UTC؟
- ما الـ timezone المرجعية للـ Feature؟
- كيف يُحوَّل `{ year, month, day, hour, minute }` لـ ISO string أو TIMESTAMPTZ؟

**ممنوع:**
```
❌ new Date(`${year}-${month}-${day}T${hour}:${minute}:00`).toISOString()
   ← يعتمد ضمنياً على timezone جهاز المستخدم
   ← النتيجة تختلف بين مستخدمين في دول/timezones مختلفة
```

التحويل الصحيح لـ instant/UTC يتطلب timezone context صريح تملكه طبقة Feature/API.
Backend هو المرجع النهائي للتحقق من المواعيد وتحويلات التوقيت (DATE-14).

---

## DATE-14 — Timezone Boundary

### حد المسؤولية

DS-DATE يُنتج **Temporal Local Value** — لا يملك Timezone conversion.

### Date-only: لا timezone shift

```
DOB: 1991-11-10
→ يبقى 1991-11-10 بغض النظر عن الدولة
→ ممنوع تحويله لـ 1991-11-09 أو 1991-11-11 بسبب timezone
```

### DateTime: Timezone ملك الـ Feature/API Contract

```
موعد: 2025-12-15 09:00 (محلي)
→ DS-DATE يُنتج: { year:2025, month:12, day:15, hour:9, minute:0 }
→ Timezone conversion (UTC/local): ملك Feature layer
→ ISO Z-suffix: ملك Feature layer — يتطلب timezone context صريح (انظر DATE-13)
→ Backend تحقق: ملك Backend (TIMESTAMPTZ)
```

### قائمة Timezones

إذا احتجنا قائمة Timezones للاختيار في المستقبل:
- هذه ملك DS-REF أو نظام مستقل — ليست DS-DATE.
- V1 لا يتضمن Timezone Picker.

### Backend Authority

Backend هو المرجع النهائي للمواعيد الفعلية وتحويلات التوقيت.

---

## DATE-15 — Canonical Values (Pseudocode Concepts)

> **تنبيه:** جميع الأمثلة أدناه Pseudocode/Concepts — ليست Runtime API names محددة.
> أسماء الـ properties والـ functions تحددها Runtime Implementation.

### Year-only
```
canonical type: number
example: 2022
```

### Month-Year
```
canonical type (concept): { year: number, month: number }
example: { year: 2022, month: 3 }
```

### Full Date
```
canonical type (concept): { year: number, month: number, day: number }
example: { year: 1991, month: 11, day: 10 }
```

### Time
```
canonical type (concept): { hour: number, minute: number }
// hour: 0-23 دائماً (canonical) — العرض 12h أو 24h
example: { hour: 14, minute: 30 }
```

### DateTime
```
canonical type (concept): { year, month, day, hour, minute }
example: { year: 2025, month: 12, day: 15, hour: 9, minute: 0 }
```

### Temporal Range
```
canonical type (concept): { start: TemporalValue, end: TemporalValue | null }
// null end = open-ended — اسم Domain State (is_current / ongoing / ...) يحدده Feature Contract
```

---

## DATE-16 — Serialization ≠ UI Concern

### المشكلة الحالية (Legacy Evidence)

المشروع يحتوي Legacy Contracts مختلفة لنفس نوع البيانات:

| الحقل | DB Type | Format |
|-------|---------|--------|
| `experience.start_date` | TEXT | "YYYY" |
| `experience.end_date` | TEXT | "YYYY" أو null |
| `education.start_year` | INTEGER | number |
| `education.end_year` | INTEGER | number |
| `profiles.dob` | TEXT | "YYYY-MM-DD" |
| `courses.completion_date` | TEXT | "YYYY" (أو "YYYY-MM-DD" أحياناً) |
| `company_profiles.founded_year` | INTEGER | number |
| `appointments.scheduled_at` | TIMESTAMPTZ | ISO 8601 UTC |
| `company_saved_candidates.follow_up_at` | TIMESTAMPTZ | ISO 8601 UTC |

### المبدأ المعماري

**Serialization (التحويل بين DS-DATE value والـ API payload) ملك Feature/API Contract — ليس DS-DATE.**

DS-DATE يُنتج Canonical Value. Feature layer يُسلسله:
```
// Pseudocode — ليس Runtime
year-only → feature يُقرر: "2022" (TEXT) أو 2022 (INTEGER)
full date → feature يُقرر: "1991-11-10" (TEXT) أو { year, month, day }
datetime → feature يُقرر: ISO UTC string
```

### DS-DATE لا يغير DB Schema

هذا التوثيق لا يغير DB Types الموجودة. Migration = PR مستقل.
DS-DATE يدعم Legacy Contracts عبر Feature Serialization layer.

---

## DATE-17 — Hydration Contract (DS-FRM Compliance)

### المبدأ

Hydration = تعبئة حقول التاريخ من قيمة محفوظة عند فتح Edit.

**DS-DATE يلتزم بـ DS-FRM FRM-06 (Hydration).**

### قاعدة الترتيب: Parent before Dependent

```
// Pseudocode — ليس Runtime

Full Date Hydration:
  1. Hydrate Year (parent)
  2. Hydrate Month (parent)
  3. Rebuild Days based on (year, month)  ← DS-DATE
  4. Hydrate Day (dependent)

Month-Year Range Hydration:
  1. Hydrate Start Month
  2. Hydrate Start Year
  3. Rebuild End options from Start  ← DS-DATE
  4. Hydrate End Month
  5. Hydrate End Year
```

### مثال DOB محفوظة: "1991-11-10"

```
// Pseudocode
1. Parse: year=1991, month=11, day=10
2. Hydrate Year selector → 1991
3. Hydrate Month selector → 11 (نوفمبر)
4. Rebuild Days: نوفمبر → 30 يوماً
5. Hydrate Day selector → 10
Result: Day=10, Month=نوفمبر, Year=1991 ← صحيح
```

### ممنوع

```
❌ setTimeout hacks: setTimeout(() => sel.value = day, 80)
❌ DOM text parsing لاستخراج القيمة من Label
❌ Hydrate Child قبل Parent (يُنتج خيارات غير صحيحة)
❌ Auto-select إذا لم تكن قيمة محفوظة
❌ إظهار قيمة قديمة مؤقتاً ثم استبدالها (Flash of Wrong Content)
```

---

## DATE-18 — No Auto-select

### القانون الأساسي

**DS-DATE لا يختار قيمة للمستخدم بدون طلب واضح.**

```
❌ لا تختار السنة الحالية تلقائياً عند فتح حقل جديد
❌ لا تختار الشهر الحالي
❌ لا تختار اليوم الحالي
❌ لا تختار أول يوم صالح في الشهر
❌ لا تختار أول End صالح بعد تغيير Start
❌ لا تختار آخر End صالح
❌ لا تختار "01" كيوم افتراضي
```

### الاستثناء المقبول الوحيد

إذا Feature Contract نفسه يوفر قيمة Default/Initial رسمية (مثل: "الموعد الافتراضي = اليوم + يومان")، Feature layer يضبطها قبل تسليم الـ Initial Value لـ DS-DATE كـ Hydration value.

DS-DATE يُنفِّذ Hydration — لا يُقرِّر الـ Default.

---

## DATE-19 — State Model

DS-DATE يُعبِّر عن حالته عبر **4 محاور مستقلة**:

### المحور 1: Interaction State

| الحالة | المعنى |
|--------|--------|
| `enabled` | تفاعل عادي |
| `disabled` | لا تفاعل، DS-SEL disabled presentation |
| `readonly` | مقروء فقط، لا dropdown |

### المحور 2: Completion State

| الحالة | المعنى |
|--------|--------|
| `empty` | لا قيمة في أي جزء |
| `partial` | بعض الأجزاء فقط (مثلاً Month+Year بدون Day) |
| `complete` | كل الأجزاء المطلوبة موجودة |

### المحور 3: Validation State

| الحالة | المعنى |
|--------|--------|
| `normal` | لا خطأ معروض |
| `error` | خطأ مرتبط بهذا الحقل (DS-VAL يملك العرض) |

### المحور 4: Range Dependency State

(للـ Range Fields فقط)

| الحالة | المعنى |
|--------|--------|
| `empty` | لا Start ولا End |
| `start-only` | Start مختار، End فارغ |
| `complete` | Start و End مختاران |
| `open-ended` | Start مختار + Domain State = مستمر |
| `end-invalidated` | End كان مختاراً لكن Start تغير وأبطله |

### ممنوع

```
❌ لا تُنشئ enum ضخم يجمع كل المحاور مثل: ENABLED_PARTIAL_ERROR_START_ONLY
❌ لا تربط محاور الـ State ببعضها بدون سبب وظيفي واضح
```

---

## DATE-20 — Partial Composite Value

### التمييز الرسمي

| الحالة | اليوم | الشهر | السنة | Completion State |
|--------|-------|-------|-------|----------------|
| empty | - | - | - | `empty` |
| partial | - | 11 | 1991 | `partial` |
| partial | 10 | - | 1991 | `partial` |
| complete | 10 | 11 | 1991 | `complete` |

**نفس المبدأ للوقت:**

| الحالة | الساعة | الدقيقة | Completion State |
|--------|--------|---------|----------------|
| partial | 9 | - | `partial` |
| complete | 9 | 30 | `complete` |

### ما يعنيه DS-DATE

DS-DATE يعرف Completion State ويُعيد الـ Canonical Value فقط عند `complete`.
عند `partial`: الـ Canonical Value = null أو undefined (حسب Implementation).

### ما لا يعنيه DS-DATE

متى يظهر خطأ "الحقل ناقص" ← **DS-VAL** يملك هذا.

---

## DATE-21 — Clear Contract

### Clear الكامل

Clear على حقل مركب يُفرغ كل أجزائه:

```
// Full Date Clear (Pseudocode)
Day = empty
Month = empty
Year = empty

// Month-Year Clear
Month = empty
Year = empty

// Range Clear (if all cleared)
Start = empty
End = empty
```

### DS-DATE لا يقرر

```
DS-DATE يُفرغ القيمة المركبة.
لكن DS-DATE لا يقرر:
❌ هل يُرسَل null للـ API؟
❌ هل يُحذَف الحقل من Payload؟
❌ هل الحقل required؟

هذه مسؤوليات: DS-FRM + API-MUT + Feature Contract
```

---

## DATE-22 — Dirty / Pristine (DS-FRM Compliance)

### المبدأ

DS-DATE لا يملك Dirty State.

**DS-FRM (FRM-13) هو المالك الوحيد للـ Dirty/Pristine.**

### دور DS-DATE

DS-DATE يُعلِم DS-FRM أن Canonical Temporal Value تغيرت.
DS-FRM يُقرِّر إذا كان هذا يجعل الـ form Dirty بالمقارنة مع originalHydratedValue.

### السيناريو الحرج

```
المستخدم يغير: 2022 → 2023 → يرجع لـ 2022
→ DS-DATE يُعلِم بكل تغيير
→ DS-FRM يقارن مع originalHydratedValue
→ إذا القيمة الحالية = القيمة الأصلية → Form يرجع Pristine
```

### ممنوع

```
❌ DS-DATE يستدعي markDirty() بشكل دائم
❌ DS-DATE يتجاهل المقارنة مع originalHydratedValue
❌ DS-DATE يملك متغير _isDirty خاص به
```

---

## DATE-23 — Payload Ownership (DS-FRM + API-MUT)

### المبدأ

DS-DATE لا يبني Mutation Payload النهائي.

**DS-FRM + API-MUT يملكان ذلك.**

### ما يوفره DS-DATE

```
// Pseudocode — ليس Runtime API
getTemporalValue() → CanonicalValue | null
// partial → null (لا Canonical Value جزئية — DATE-20)
getCompletionState() → 'empty' | 'partial' | 'complete'
```

### قواعد Payload Building (من DS-FRM × API-MUT)

```
// Pseudocode — concept من DS-FRM FRM-09

unchanged (لم يمس المستخدم الحقل) → omit من Payload
changed (قيمة مختلفة عن originalHydratedValue) → أرسِل Canonical Value
empty (بعد Clear متعمد) → null أو [] حسب Field/API Contract (API-MUT-03)
```

### buildDatePayload

لا تضع `buildDatePayload()` كـ Runtime API إلزامية داخل DS-DATE.
إذا استُخدم في مثال Pseudocode فيوضَح صراحةً أنه مفهوم تصويري:

```
// Pseudocode concept — ليس Runtime API
function buildDatePayload(dateField, fieldName, { originalHydratedValue, fieldContract }):
  const value = dateField.getTemporalValue()
  const completion = dateField.getCompletionState()

  if (unchanged from originalHydratedValue) return  // omit
  if (completion === 'empty' && fieldContract.clearable) payload[fieldName] = null
  if (completion === 'complete') payload[fieldName] = serialize(value, fieldContract)
  // partial: لا يُرسَل (DS-VAL يرفضه عند Validation قبل Submit)
```

---

## DATE-24 — Disabled State

### التعريف

```
Disabled:
- لا يفتح Dropdown
- لا يسمح بأي تغيير من المستخدم
- يظهر بالشكل الرسمي من DS-SEL (Disabled presentation)
```

**Disabled يمنع User Interaction فقط — لا يمنع:**
- Hydration (تعبئة الحقل برمجياً من قيمة محفوظة)
- إعادة بناء Options بعد تغيير parent dependency (قبل إعادة تمكين الحقل)
- Programmatic sync رسمي من نظام آخر

### ملاحظات إضافية

DS-DATE لا يقرر Payload semantics بسبب Disabled state.
قرار "إذا Disabled هل يُرسَل في Payload؟" ملك DS-FRM + Feature Contract.

---

## DATE-25 — Readonly State

### التعريف

```
Readonly:
- يعرض القيمة الحالية بشكل مقروء
- لا يفتح Dropdown عند النقر
- لا Popup، لا Interaction، لا fake clickable control
- يظهر كـ display text وليس كـ form control
- لا يشبه Dropdown المفتوح/المنتظر
```

### ملاحظات إضافية

DS-SEL يملك كيفية عرض Readonly.
DS-DATE لا يقرر قيمة الـ Payload عند Readonly.

---

## DATE-26 — Validation Ownership

### ما يعرفه DS-DATE (Structural Temporal Validation)

```
✅ عدد أيام الشهر + leap year
✅ End >= Start في Range Fields
✅ القيمة ضمن minYear/maxYear
✅ كل أجزاء الحقل المركب موجودة (Partial vs Complete)
✅ Day المختار صالح للشهر والسنة المختارَين
```

### ما يملكه DS-VAL (Timing + Display)

```
✅ متى يظهر الخطأ (on Submit، on Blur، on Change)
✅ كيف يظهر (inline message، border color، icon)
✅ ترتيب الأخطاء وأولوية العرض
✅ ربط الخطأ بالحقل المعني
✅ ARIA error linking
```

### ما يملكه Backend (Final Authority)

```
✅ التحقق الكامل بغض النظر عن Frontend validation
✅ Business rules الخاصة بالـ Domain (مثل: العمر الأدنى للتسجيل)
✅ Timezone validity للمواعيد
✅ Leap year فعلياً في DB (TIMESTAMPTZ يتحقق)
```

---

## DATE-27 — Backend Authority

### القانون الأساسي

Backend يُعيد التحقق من كل حقل تاريخ/وقت بغض النظر عن Frontend validation.

### ما يتحقق Backend منه (per Feature/API Contract)

| الفحص | المسؤول |
|-------|---------|
| الشهر 1-12 | Backend |
| اليوم صالح فعلياً للشهر والسنة | Backend |
| Leap year validity | Backend |
| السنة ضمن المجال المسموح | Backend (per Feature rules) |
| Start/End relationship | Backend |
| ممنوع تاريخ مستقبلي للـ DOB | Backend (Feature rule) |
| DateTime + Timezone صالحان | Backend |

### مثال Business Rules (ليست ملك DS-DATE)

```
DOB يبدأ 1900 — Feature Rule (ليس DS-DATE Rule)
Courses لا تتجاوز السنة الحالية — Feature Rule
Experience Start ≥ 1950 — Feature Rule
```

DS-DATE لا يُثبِّت هذه القواعد كـ Global rules. كل Feature يحدد قواعده.

---

## DATE-28 — Error Mapping for Composite Fields

### المشكلة

Backend قد يُرسِل خطأ على `birth_date` لكن الـ UI يعرضه في 3 حقول: `birth_day`, `birth_month`, `birth_year`.

### المبدأ (DS-VAL-07a Compliance)

```
❌ ممنوع: API field name == DOM id تلقائياً
✅ مطلوب: Explicit mapping بين Backend error field وDS-DATE Group/Component
```

DS-DATE يجب أن يُعرِّف لكل حقل مركب:
- **Group identifier:** اسم مجموعة الحقل (مثل `birth_date`) للـ Backend
- **Component mapping:** أي مكون (day/month/year) يتأثر بنوع الخطأ

Feature/DS-VAL يستخدم هذه المعلومات لتوجيه الخطأ للمكان المرئي الصحيح.

---

## DATE-29 — Accessibility

### DS-DATE لا يخترع Accessibility Pattern جديد للـ Dropdowns

يعتمد كلياً على DS-SEL Accessibility Contract.

### ما يضيفه DS-DATE فوق DS-SEL

```
✅ Labels واضحة لكل جزء مركب:
  - حقل اليوم: aria-label="اليوم"
  - حقل الشهر: aria-label="الشهر"
  - حقل السنة: aria-label="السنة"

✅ Composite field يكون له accessible group/relationship:
  - fieldset + legend للـ Date Group
  - ترتيب tab منطقي: اليوم → الشهر → السنة (RTL-aware)

✅ Error mapping واضح (DATE-28):
  - خطأ على الـ Group يمكن ربطه بـ aria-describedby

✅ Keyboard: Tab بين أجزاء المجموعة بترتيب منطقي حسب RTL/Layout
```

### ممنوع

```
❌ إعادة اختراع keyboard navigation للـ Dropdowns (DS-SEL يملك هذا)
❌ Custom ARIA roles للتاريخ (استخدم ما يوفره DS-SEL)
```

---

## DATE-30 — RTL Contract

### المبدأ

**ترتيب العرض ≠ ترتيب معنى القيمة.**

### عرض التاريخ في RTL

```
العرض (RTL, من اليمين لليسار):
[ اليوم ▼ ] [ الشهر ▼ ] [ السنة ▼ ]

Canonical Object (لا يتغير بسبب RTL):
{ year: 1991, month: 11, day: 10 }
```

### القاعدة الأساسية

```
✅ بناء القيمة الـ Canonical من خصائص الأجزاء (by name) — ليس من ترتيب DOM
❌ ممنوع: بناء القيمة من ترتيب children في DOM
❌ ممنوع: "أول Dropdown = Year دائماً" — الترتيب Visual فقط
```

---

## DATE-31 — Mobile UX

### على الهاتف: نفس DS-SEL Dropdowns

```
✅ Custom DS-SEL Dropdowns على Mobile — نفس Desktop
❌ ممنوع: Android native date/time picker
❌ ممنوع: iOS native date/time picker
❌ ممنوع: Bottom Sheet مستقل داخل DS-DATE (DS-OVL غير موثَّق بعد)
```

### Year Dropdown الطويل على Mobile

Year list قد تحتوي 50+ خياراً.
يُسمح بتفعيل Searchable Mode من DS-SEL على Year Dropdown إذا Field Contract يوضح ذلك.

```
// Field Contract قد يحدد (Pseudocode):
yearDropdown: { searchable: true }
// DS-DATE يطلب DS-SEL تفعيل Searchable mode
// DS-DATE لا يبني Search Engine مستقل
```

---

## DATE-32 — Flutter Readiness

### الفصل المعماري

| Platform-neutral (contract) | Web-only (implementation) |
|---------------------------|--------------------------|
| Precision: year/month/day/hour/minute | DOM elements |
| Canonical Values | DS-SEL web widget |
| Range semantics | CSS |
| Open-ended semantics | Event listeners |
| Dependencies (month→days, start→end) | ARIA implementation |
| minYear/maxYear policy | Portal behavior |
| minuteStep | scrollbar behavior |
| Clearability | keyboard shortcuts |
| Hydration ordering rules | |
| Validation rules | |

### الـ Canonical API Contract

```
// Platform-neutral — أي Client يستخدمه
// Web: DS-SEL Dropdowns
// Flutter (مستقبل): Flutter Picker widgets
// API Payload: نفس القيمة Canonical بغض النظر عن Platform
```

### قرار V1

الواجهة الحالية لتواصلنا = Dropdown-based (DS-SEL).
Flutter قد يختار Implementation مختلفة (Flutter date picker) مع نفس Backend/API contract.
DS-DATE لا يمنع ذلك — يُفصل Platform-neutral contract.

---

## DATE-33 — Legacy Runtime Evidence & Migration Inventory

> **تحذير:** هذا القسم توثيق للواقع الحالي كـ Evidence — ليس Source of Truth.
> التوثيق الجديد (هذا الملف) هو Target Contract.
> **لا تُعدَّل ملفات Runtime في هذا PR.**

### الحقول الحالية التي تحتاج Migration

| الملف | الحقل / العنصر | النمط الحالي | المشكلة | الأولوية |
|-------|--------------|-------------|---------|---------|
| `profile.html` | `#m-dob-d/m/y` | 3 native `<select>` + inline styles | ليس DS-SEL، inline style، DOB range (36 سنة فقط) مكسور | P1 |
| `profile.html` | `#m-es` (exp start) | native `<select>` + `[...Array(36)]` | تكرار pattern | P1 |
| `profile.html` | `#m-ee` (exp end) | native `<select>` + `"حتى الآن"` magic string | F29 violation | P1 |
| `profile.html` | Course year | native `<select>` + `[...Array(36)]` | تكرار pattern | P2 |
| `profile-v2.exp.js` | `exStart` / `exEnd` | native select (NOT DS-SEL) | ليس DS-SEL | P2 |
| `profile-v2.edu.js` | `eduSY` / `eduEY` | native select (NOT DS-SEL) | ليس DS-SEL | P2 |
| `profile-v2.courses.js` | `courseCD` | native select (NOT DS-SEL) | ليس DS-SEL | P2 |
| `edu-profile.html` | `#e-founded` | `<input type="number">` | أسوأ pattern — لا DS-SEL | P3 |
| `company-profile.html` | `#coApptDate` | `<input type="date">` native | native browser picker | P3 |
| `company-profile.html` | `#coApptTime` | `<input type="time">` native | native browser picker | P3 |
| `company.main.js:3534` | `.co-panel-followup-date` | `<input type="date">` native (inline HTML) | native browser picker | P3 |

### الحقل الوحيد الصحيح حالياً

| الملف | الحقل | النمط الحالي | الحالة |
|-------|-------|-------------|--------|
| `company.main.js:314` | Founded Year | `TW.fillFoundedYears()` + `ep-select` (DS-SEL) | ✅ صحيح — نموذج للـ Migration |

### بنية DB الحالية (Legacy)

```
profiles.dob                     → TEXT "YYYY-MM-DD"
experience.start_date            → TEXT "YYYY"
experience.end_date              → TEXT "YYYY" | null  (V2) | "حتى الآن" (V1 legacy — BUG)
experience.is_current            → BOOLEAN
education.start_year             → INTEGER
education.end_year               → INTEGER
education.is_current             → BOOLEAN
courses.completion_date          → TEXT "YYYY" (أحياناً "YYYY-MM-DD" — inconsistent)
company_profiles.founded_year    → INTEGER
appointments.scheduled_at        → TIMESTAMPTZ
company_saved_candidates.follow_up_at → TIMESTAMPTZ
```

### المشاكل الموثقة التي تحتاج Migration منفصلة

| المشكلة | التفاصيل | الحل المقترح |
|---------|---------|-------------|
| DOB range مكسور | `[...Array(36)]` = 36 سنة فقط → مولود قبل 1989 لا يستطيع إدخال DOB | Field Contract: minYear=1900 |
| "حتى الآن" في DB | `experience.end_date` قد يحتوي "حتى الآن" من V1 القديم — F29 violation | Server يرفض magic string + backfill: UPDATE SET end_date=NULL WHERE end_date='حتى الآن' |
| `[...Array(36)]` مكرر 4+ مرات | في profile.html لـ Experience Start/End + Education + Courses | `TW.fillYears(el, {min, max})` helper مشترك |
| `edu-profile.html` `<input type="number">` | أسوأ UX — لا validation، لا اتساق | DS-SEL + `TW.fillFoundedYears()` |
| `courses.completion_date` inconsistent | بعضها "YYYY" وبعضها "YYYY-MM-DD" | توحيد: "YYYY" فقط (year-only) |

### Migration Principle (للـ PRs اللاحقة)

```
عند Migration لاحقاً:
✅ Hydrate canonical legacy value عبر Adapter
✅ لا تُفقِد قيمة قديمة صالحة
✅ لا تُغيِّر القيمة أثناء تعديل حقل غير متعلق
✅ لا auto-normalize DB silently من الـ Frontend
✅ Server يرفض "حتى الآن" كـ end_date قبل Migration الـ DB
```

---

## DATE-34 — Out of Scope

الأمور التالية خارج نطاق DS-DATE V1 وأي V مستقبلي ما لم يُقرَر معمارياً:

```
❌ Calendar UI / calendar grid
❌ native date/time pickers (أي شكل)
❌ Reference Data catalogs (الدول، المدن)
❌ Business-specific domain labels ("أعمل هنا حالياً")
❌ Calculation/display systems مشتقة من التاريخ (حساب العمر، "منذ 3 أيام")
❌ Relative timestamps ("قبل 5 دقائق")
❌ Recurrence / scheduling rules
❌ DB migration
❌ Runtime migration لملفات موجودة
❌ Historical data cleanup
❌ Timezone picker / Timezone list (DS-REF مستقبلاً)
❌ Notification scheduling
❌ Search/filter preset logic
❌ DS-OVL mechanics (Overlay/Sheet)
❌ DS-ASSET (icons/assets)
❌ General form lifecycle
❌ Mutation payload ownership
❌ Seconds (خارج V1 ما لم يُوثَّق استخدام)
❌ Hijri Calendar support
❌ Multi-timezone display
```

---

## DATE-35 — Forbidden Patterns

```
❌ native <input type="date"> كواجهة مرئية للمستخدم
❌ native <input type="time"> كواجهة مرئية للمستخدم
❌ native <select> مرئي في الصفحات الموحدة (ليس DS-SEL)
❌ <input type="number"> لإدخال السنة
❌ لا تعمل Auto-select لأي قيمة تاريخية بدون طلب صريح من المستخدم
❌ لا تختزن "حتى الآن" أو أي magic string كـ Temporal Canonical Value
❌ لا تُحوِّل Year-only إلى Full Date بدون Field Contract رسمي
❌ لا تُحوِّل Month-Year إلى Full Date بدون Field Contract رسمي
❌ لا تخترع Dropdown Engine مستقل — DS-SEL هو المحرك
❌ لا تضع Leap Year logic داخل Feature Module بشكل مكرر — DS-DATE يملكه مركزياً
❌ لا تُكرِّر [...]Array(N)] لتوليد السنوات — استخدم Helper مشترك
❌ لا تستخدم setTimeout لـ Hydration
❌ لا تُحدِّد Dirty State داخل DS-DATE — DS-FRM يملكه
❌ لا تبني Payload مباشرةً من DS-DATE — DS-FRM + API-MUT يملكانه
❌ لا تُوقِّت Validation errors داخل DS-DATE — DS-VAL يملك هذا
❌ لا تُنشئ نظام Timezone داخل DS-DATE
❌ لا تُنشئ جدول DB لـ days/months/years — بيانات مولَّدة
❌ لا تضع Business Domain rules (عمر أدنى، تاريخ تخرج مستقبلي) كـ Global DS-DATE rules
❌ لا تبنِ Year Range Dropdown Searchable مستقل — استخدم DS-SEL Searchable mode
❌ لا تُنشئ Calendar لأي سبب في V1
```

---

*أُنشئ في PR docs/ds-date-v1 — 2026-07-23*
*DS-DATE V1: 36 قسماً (DATE-00 → DATE-35) — Documentation Only — لا Runtime.*
