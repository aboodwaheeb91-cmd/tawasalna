# [DS-FRM] Form Lifecycle System V1

> **نظام دورة حياة الفورم** — الـ contract الرسمي لسلوك النماذج من اللحظة التي تُفتح حتى تُغلَق.

---

## FRM-00 Reading & Routing Protocol

**هذا الملف راوتر — اقرأ الأقسام ذات الصلة فقط:**

| المهمة | الأقسام |
|--------|---------|
| فهم دورة الحياة الكاملة | FRM-03 (خريطة الحالات) |
| فتح فورم Add جديد | FRM-04 + FRM-05 |
| فتح فورم Edit (بيانات موجودة) | FRM-04 + FRM-05 + FRM-06 + FRM-07 |
| بناء الـ Payload قبل الإرسال | FRM-09 |
| Async Hydration (بيانات تُجلَب بعد الفتح) | FRM-10 |
| Dirty State / تحذير التغييرات | FRM-13 + FRM-14 |
| ما يحدث عند نجاح الحفظ | FRM-16 + FRM-17 |
| ما يحدث عند فشل الحفظ | FRM-21 |
| قائمة الـ Regression | FRM-22 |
| الأنماط الفاشلة الموثَّقة | FRM-24 |

**الأنظمة المكملة:**
- `DS-INP` (INPUT-FIELDS.md) — شكل حقول الإدخال البصرية
- `DS-VAL` (VALIDATION-ERRORS.md) — توقيت التحقق وعرض الأخطاء
- `DS-BTN` (BUTTONS.md) — سلوك زر الحفظ (Loading، Disabled)
- `API-MUT` (contracts/API-MUTATIONS-ERRORS.md) — Tri-state semantics والـ Error shape

---

## FRM-01 Purpose

يُعرِّف هذا النظام **دورة حياة الفورم** كاملةً:
- متى يُفتَح ويُغلَق وكيف يُهيَّأ
- كيف تُبنى الـ Payload قبل الإرسال
- ما يحدث عند النجاح وعند الفشل
- الـ Dirty State وتحذير المستخدم عند الإغلاق بدون حفظ

هذا النظام **لا يُعرِّف** الشكل البصري للحقول (DS-INP)، ولا توقيت رسائل الخطأ (DS-VAL)، ولا شكل زر الحفظ (DS-BTN).

---

## FRM-02 Scope & Ownership

**داخل النطاق:**
- كل نموذج تحرير (Edit Modal، Edit Form، Add Modal، Add Form)
- نماذج الإعدادات والمعلومات الشخصية
- نماذج نشر المحتوى (وظيفة، منشور، دورة)

**داخل النطاق جزئياً — نماذج المصادقة (تسجيل الدخول / الاشتراك):**
نماذج المصادقة تشترك مع DS-FRM في:
- **Submission Integration** (FRM-15) — نفس خطوات الإرسال
- **Failure Contract** (FRM-21) — الفورم يبقى مفتوحاً + زر يُستعاد عند الفشل
- **DS-BTN** — سلوك زر الإرسال (Loading / Disabled)
- **DS-VAL** — توقيت الأخطاء وعرضها
- **API-MUT** — تفسير Error Response من Backend

نماذج المصادقة **لا تشترك** في:
- Dirty State / تحذير التغييرات (FRM-13 + FRM-14) — لا معنى لها في login/register
- Hydration (FRM-06) — لا record موجود يُحمَّل
- Edit Record lifecycle — مسار إنشاء فقط

**خارج النطاق V1 — انظر FRM-23:**
- نماذج البحث والفلترة — لا حفظ، لا Reset، لا Dirty State
- نماذج الرسائل (compose message)
- Wizard / Multi-step forms
## FRM-03 Canonical Lifecycle — الحالات الرسمية

```
                    ┌─────────────────────────────────────────────┐
                    │                 CLOSED                       │
                    └──────────────────┬──────────────────────────┘
                                       │ user triggers open
                                       ▼
                               ┌──────────────┐
                               │   OPENING    │ ← DOM ready, initial state
                               └──────┬───────┘
                                      │
                                      ▼
                               ┌──────────────┐
                               │  RESETTING   │ ← clear values + errors
                               └──────┬───────┘
                                      │
                               ┌──────▼───────┐
                               │  HYDRATING   │ ← load existing data (Edit only)
                               └──────┬───────┘
                                      │
                              ┌───────▼────────┐
                              │ READY-PRISTINE │ ← values = original, no changes
                              └───────┬────────┘
                                      │ user types/selects
                                      ▼
                              ┌───────────────┐
                              │  READY-DIRTY  │ ← current ≠ original
                              └───────┬───────┘
                                      │ user presses submit
                                      ▼
                             ┌────────────────┐
                             │  VALIDATING    │ ← client-side checks (DS-VAL)
                             └────────┬───────┘
                                      │ all valid
                                      ▼
                             ┌────────────────┐
                             │  SUBMITTING    │ ← request in-flight, button disabled
                             └────────┬───────┘
                              ┌───────┴────────┐
                              ▼                ▼
                     ┌──────────────┐  ┌──────────────┐
                     │   SUCCESS    │  │    ERROR     │
                     └──────┬───────┘  └──────┬───────┘
                            │                  │
                            ▼                  ▼
                        CLOSING           READY-DIRTY
                        → CLOSED          (فورم يبقى مفتوحاً)
```

### وصف الحالات

| الحالة | المعنى | دخول منها | خروج إليها |
|--------|--------|-----------|-----------|
| `CLOSED` | الفورم غير مرئي | SUCCESS / CLOSING | OPENING |
| `OPENING` | يجهِّز DOM ويُهيِّئ state | CLOSED | RESETTING |
| `RESETTING` | يمسح القيم والأخطاء السابقة | OPENING | HYDRATING (Edit) / READY-PRISTINE (Add) |
| `HYDRATING` | يجلب ويُطبِّق البيانات الموجودة | RESETTING | READY-PRISTINE |
| `READY-PRISTINE` | الفورم جاهز، لا تغييرات | HYDRATING / RESETTING | READY-DIRTY |
| `READY-DIRTY` | فيه تغييرات لم تُحفَظ | READY-PRISTINE / ERROR | VALIDATING / CLOSING |
| `VALIDATING` | يتحقق client-side | READY-DIRTY | SUBMITTING / READY-DIRTY |
| `SUBMITTING` | طلب في الطريق | VALIDATING | SUCCESS / ERROR |
| `SUCCESS` | حُفِظ بنجاح | SUBMITTING | CLOSING |
| `ERROR` | فشل الحفظ | SUBMITTING | READY-DIRTY |
| `CLOSING` | يُعالِج الإغلاق | SUCCESS / READY-DIRTY (cancel) | CLOSED |

---

## FRM-04 Add vs Edit Open Contract

### فورم Add (إضافة جديدة)

```
Open()
  → RESETTING: مسح كل الحقول
  → READY-PRISTINE: الفورم فارغ جاهز للكتابة
```

لا Hydration، لا طلب API عند الفتح.

**Exception (Async Catalog):** إذا احتاج الفورم تحميل قوائم (مهن، مهارات) قبل العرض → Hydration للقوائم فقط، ليس للقيم.

### فورم Edit (تحرير موجود)

```
Open(recordId)
  → RESETTING: مسح القيم والأخطاء السابقة
  → HYDRATING: جلب البيانات أو أخذها من cache
  → Apply values to fields
  → READY-PRISTINE: القيم = النسخة المحفوظة
```

**القاعدة الذهبية:** فتح Edit على سجل مختلف = Reset كامل. لا يُفترَض أن البيانات السابقة لا تزال صالحة.

---

## FRM-05 Reset Before Hydration

**Reset إلزامي قبل أي Hydration — بدون استثناء.**

### ما يفعله Reset

1. مسح قيم كل الحقول (`value = ''`)
2. إزالة `.has-error` من كل الـ wrappers
3. إخفاء `.field-error` messages
4. إعادة `aria-invalid` إلى الوضع الافتراضي
5. حذف أي `_pendingValue` أو Async state من جولة سابقة
6. إعادة زر الحفظ لحالته الطبيعية (إذا كان Disabled/Loading من جولة سابقة)

### ما لا يفعله Reset

- لا يُغلِق المودال أو يُخفي الفورم
- لا يُعيِّن قيم — ذلك من Hydration
- لا يستدعي API

### متى يحدث Reset

| الحدث | Reset؟ |
|-------|--------|
| فتح فورم Add | ✅ دائماً |
| فتح فورم Edit (سجل جديد) | ✅ دائماً |
| فتح نفس السجل مجدداً | ✅ دائماً |
| فشل الحفظ (Retry) | ❌ لا — احتفظ بالقيم |
| إلغاء المستخدم (Cancel) | ✅ عند الفتح التالي |

---

## FRM-06 Complete Edit Hydration Contract

### ما يجب أن تُطبِّقه Hydration

**كل حقل في الفورم يجب أن يأخذ قيمته من البيانات المجلوبة:**

```js
// ✅ صحيح: Hydrate كل الحقول
function hydrateForm(record) {
  nameInput.value      = record.name ?? ''
  bioInput.value       = record.bio  ?? ''
  citySelect.value     = record.city ?? ''
  websiteInput.value   = record.website ?? ''
  // ... كل الحقول
}
```

### ممنوع: Partial Hydration

```js
// ❌ خطأ: بعض الحقول تُترَك بقيم سابقة
function hydrateForm(record) {
  nameInput.value = record.name  // ما بالـ bio؟ ما بالـ city؟
  // المستخدم قد يحفظ بيانات سجل A في حقل كان يُحرِّر سجل B
}
```

---

## FRM-07 Canonical Fields Only

### القاعدة

الحقول التي تظهر في الفورم يجب أن تتطابق مع الحقول التي يستطيع Backend قبولها.

**أمثلة على المشاكل:**
- حقل `website` في الفورم لكنه **محذوف من الـ allowlist** في Backend → القيمة تُهمَل صامتةً
- حقل لا يظهر في الفورم لكنه يُرسَل بقيم افتراضية في الـ payload → يُعيِّن قيم المستخدم لم يقصدها

### الحل

عند حذف حقل من UI → احذفه أيضاً من `payload builder` (FRM-09).
عند إضافة حقل للـ allowlist → أضفه للـ UI أو تأكد أنه لا يُرسَل بقيمة افتراضية تؤثر على البيانات.

---

## FRM-08 Form Field Ownership

### القاعدة

**لا حقلان في صفحة واحدة يتحكمان في نفس البيانات.**

إذا كان `profiles.headline` يُعدَّل من modal رئيسي، لا يجوز أن يُعدَّل أيضاً من inline edit مستقل في نفس الصفحة — إلا إذا كانا **متزامنَين** بشكل صريح ومضمون.

### بعد الحفظ الناجح

**جميع نقاط العرض للبيانات المحفوظة تُحدَّث** — ليس الفورم وحده:
- العنوان في header
- البطاقة في القائمة
- أي عرض summary آخر

يُنجَز هذا عبر **Confirmed Immediate Update** (FRM-16) أو Background Sync (FRM-18).

---

## FRM-09 Frontend Tri-state Payload Building

### الـ Tri-state

| القيمة في الـ Payload | التفسير في Backend |
|----------------------|--------------------|
| **حقل غائب (omitted)** | لا تغيير — احتفظ بالقيمة الحالية |
| **قيمة** | تحديث بهذه القيمة |
| **`null`** | مسح / حذف |

### قواعد البناء

```js
// ✅ صحيح
const payload = {}

// حقل نصي اختياري:
const name = nameInput.value.trim()
if (name !== _originalValues.name) {
  payload.name = name || null  // string → value, empty → null (clear)
}

// حقل نصي إجباري:
const title = titleInput.value.trim()
if (title !== _originalValues.title) {
  payload.title = title  // لا null — الـ validation أوقفت الفارغ مسبقاً
}

// حقل boolean:
const isPublic = publicCheckbox.checked
if (isPublic !== _originalValues.is_public) {
  payload.is_public = isPublic  // ✅ false هنا قيمة حقيقية — لا تُسقِطها
}

// حقل رقمي:
const salary = salaryInput.value
if (salary !== _originalValues.salary) {
  payload.salary = salary !== '' ? Number(salary) : null
}
```

### ❌ الأنماط الممنوعة

```js
// ❌ يُسقِط null وfalse و0 و''
if (value) payload.field = value

// ❌ يُسقِط null وfalse
if (value !== undefined && value !== null) payload.field = value

// ❌ يُرسِل string فارغ بدلاً من null للـ clearable fields
payload.field = value  // value قد يكون ''
```

### Clearable vs Required fields

| الحالة | القيمة المرسَلة |
|--------|----------------|
| اختياري + المستخدم حذف القيمة (empty) | `null` |
| إجباري + فارغ | ❌ Validation Error — لا تصل للـ payload |
| boolean = false | `false` (قيمة حقيقية) |
| رقم = 0 | `0` (قيمة حقيقية) |

---

## FRM-10 Async-safe Hydration

### المشكلة

المستخدم يفتح Edit على سجل A، ثم فجأةً يضغط على سجل B قبل أن تنتهي Hydration سجل A.
بدون حماية، بيانات A ستظهر في فورم B.

### الحل: Generation Counter (إلزامي)

```js
let _editSession = 0

function openEdit(id) {
  const mySession = ++_editSession  // رقم فريد لكل فتح
  resetForm()
  loadOptions(id).then(data => {
    if (mySession !== _editSession) return  // stale — تجاهَل
    applyHydration(data)
  })
}
```

### AbortController (اختياري — للطلبات الثقيلة فقط)

```js
let _editController = null

function openEdit(id) {
  _editController?.abort()
  _editController = new AbortController()
  const { signal } = _editController
  const mySession = ++_editSession

  fetch(`/api/records/${id}`, { signal })
    .then(r => r.json())
    .then(data => {
      if (mySession !== _editSession) return
      applyHydration(data)
    })
    .catch(err => {
      if (err.name === 'AbortError') return
      showFormError(err)
    })
}
```

### القاعدة

- **Generation Counter** إلزامي في كل حالة Async Hydration
- **AbortController** اختياري — يُضاف إذا كان الطلب ثقيلاً ومُكلِفاً
- كلاهما معاً لا ضرر منه

---

## FRM-11 Hydration Must Not Trigger Validation

### القاعدة

تطبيق قيم على الحقول أثناء Hydration **لا يُطلِق** حالة Error.

```js
// ✅ صحيح: تعيين القيمة مباشرةً دون المرور بـ validateField
field.value = record.phone  // مباشر — لا event-triggered validation

// ❌ خطأ: dispatchEvent يُطلِق blur handler الذي يفحص الخطأ
field.value = record.phone
field.dispatchEvent(new Event('blur'))  // يُطلِق validation!
```

### السبب

البيانات المحفوظة في DB مرَّت بـ validation من قبل. إظهار أخطاء على بيانات صالحة محيِّر للمستخدم ويُشعِره أن النظام معطوب.

**Exception:** إذا تغيَّرت قواعد Validation بعد حفظ البيانات (مثلاً: field أصبح required) — يُعالَج بـ Server-side check عند المحاولة التالية للحفظ، ليس بـ Hydration validation.

---

## FRM-12 Conditional Field Hydration

### السياق

بعض الحقول تظهر فقط بناءً على قيمة حقل آخر (Parent-Child).

**مثال:** تحديد "دوام جزئي" يُظهِر حقل "ساعات العمل".

### قواعد الـ Hydration الشرطية

1. **رتِّب الـ Hydration بالترتيب الصحيح:** Parent أولاً → ثم أظهِر Child → ثم اضبط قيمة Child
2. **لا تضبط قيمة حقل مخفي** — اضبطه فقط بعد إظهاره
3. **عند Reset:** أخفِ كل Child fields وامسح قيمها

```js
function applyHydration(record) {
  // 1. Parent
  jobTypeSelect.value = record.job_type

  // 2. إذا يستلزم child
  if (record.job_type === 'part_time') {
    hoursWrapper.hidden = false   // أظهِر أولاً
    hoursInput.value = record.hours_per_week ?? ''
  } else {
    hoursWrapper.hidden = true
    hoursInput.value = ''
  }
}
```

---

## FRM-13 Dirty State

### تعريف Dirty

```
Dirty = current normalized values ≠ original hydrated values
```

الفورم يعود لـ Pristine إذا أعاد المستخدم القيم لأصلها — حتى لو عدَّل ثم تراجع.

### Normalization إلزامية قبل المقارنة

| النوع | المقارنة الصحيحة |
|-------|----------------|
| String | `.trim()` على الطرفين |
| Number from string | `Number(a) === Number(b)` |
| null vs '' | كلاهما يُمثِّل "فارغ" — قد يكونان متساويَين |
| Boolean | `Boolean(a) === Boolean(b)` |
| Array | مقارنة عناصر بالترتيب بعد `sort()` إذا الترتيب غير مهم |
| Select ID | string comparison بعد `String()` |

### استخدام Dirty State

- عند Cancel/Close بحالة Dirty: أظهِر تأكيداً (FRM-14)
- لا تُعطِّل زر Save بناءً على Pristine وحده — قد يريد المستخدم إعادة الحفظ

---

## FRM-14 Cancel & Unsaved Changes

### السيناريوهات

| الحالة عند Cancel | الإجراء |
|------------------|---------|
| READY-PRISTINE (لا تغييرات) | أغلِق فوراً — لا تأكيد |
| READY-DIRTY (فيه تغييرات) | أظهِر تأكيداً قبل الإغلاق |
| SUBMITTING (طلب في الطريق) | لا تسمح بالإغلاق (الزر disabled) |

### رسالة التأكيد

```
"لديك تغييرات لم تُحفَظ. هل تريد الخروج؟"
[تجاهل] [البقاء والمتابعة]
```

- "تجاهل" → CLOSED (تفقد التغييرات)
- "البقاء والمتابعة" → READY-DIRTY (يبقى في الفورم)

### Cancel أثناء Hydration

إذا ضغط المستخدم Cancel أثناء HYDRATING:
- أوقِف الـ request (AbortController) أو تجاهَل الـ response (Generation Counter)
- أغلِق الفورم — لا حاجة لتأكيد (لم يُغيِّر شيئاً)

---

## FRM-15 Submission Integration

### خطوات Submission

```
1. [FRM] يُطلِق Validation (DS-VAL)
2. [DS-VAL] يعرض أخطاء أو يُقِر بأن كل شيء صحيح
3. [FRM] عند النجاح: يُحوِّل زر Save إلى Loading (DS-BTN-09)
4. [FRM] يبني الـ Payload (FRM-09)
5. [API-MUT] يُرسِل الطلب
6. [FRM] يستقبل الـ response: نجاح → FRM-16 / فشل → FRM-21
```

### Double Submit Prevention

```js
let _submitting = false

async function handleSave() {
  if (_submitting) return  // احتياط إضافي
  _submitting = true
  saveBtn.disabled = true

  try {
    // ... validation + fetch
  } finally {
    _submitting = false
    saveBtn.disabled = false  // يُستعاد في كلتا الحالتين (نجاح/فشل)
  }
}
```

---

## FRM-16 Mutation Confirmation Contract

### الـ Contract الذهبي

**كل حفظ ناجح يُطبِّق البيانات الفعلية من الـ Response — لا القيم المُحلِّية.**

```
Validate → Submit → Backend Confirmation → Apply Canonical Response → Update All Display
```

### مراحل التطبيق

```js
async function handleSave() {
  // 1. Validate (DS-VAL)
  if (!validateForm()) return

  // 2. Build payload (FRM-09)
  const payload = buildPayload()

  // 3. Submit
  saveBtn.disabled = true
  const res = await fetch('/api/profile', { method: 'PUT', body: JSON.stringify(payload) })

  if (!res.ok) {
    handleSaveError(await res.json())  // FRM-21
    return
  }

  // 4. Apply canonical response
  const saved = await res.json()
  applyToState(saved)         // تحديث window._state أو companyState
  renderDisplayViews(saved)   // تحديث كل نقاط العرض
  updateOriginalValues(saved) // تحديث مرجع Dirty State

  // 5. Close form
  closeModal()
}
```

---

## FRM-17 Save Response First

### القاعدة

**الـ Save Response يجب أن يكون كاملاً كفاية لتحديث الـ UI فوراً** — بدون Background Refetch.

### ماذا يعني "كافٍ"

الـ response يحتوي على:
- كل الحقول التي تُعرَض في Display View
- المعرِّفات اللازمة (id، tw_id، إلخ)
- أي computed fields تعتمد على الحقول المحفوظة

### إذا كان الـ Response غير كافٍ

- Background Sync مقبول (FRM-18)
- **ممنوع Optimistic Update** — لا تُعرَض قيم تخمينية قبل تأكيد Backend
- **ممنوع:** عرض قيم stale للمستخدم واعتبار الحفظ ناجحاً
## FRM-18 Background Synchronization Safety

### متى يُستخدَم

Background Refetch يُستخدَم **فقط** إذا كان الـ Save Response لا يكفي لتحديث الـ UI (FRM-17).

### القواعد الإلزامية

1. **Session Check:** تأكد أن المستخدم لا يزال في نفس الـ context قبل تطبيق الـ response

```js
const sessionId = _currentSessionId

fetch('/api/profile')
  .then(r => r.json())
  .then(fresh => {
    if (_currentSessionId !== sessionId) return  // context تغيَّر — تجاهَل
    mergeIntoState(fresh)
  })
```

2. **Merge Strategy:** لا تُستبدَل القيم التي عدَّلها المستخدم خلال الـ refetch (optimistic lock)
3. **Error Handling:** فشل الـ refetch لا يُلغي نجاح الحفظ — يُسجَّل في console فقط
4. **لا Blocking:** الـ refetch يحدث في الخلفية — الـ UI لا ينتظره

---

## FRM-19 Clearing Must Propagate

### السياق

عندما يُحذَف `skill` أو `language` أو أي tag:
- يُحذَف من قائمة العرض فقط بعد تأكيد Backend — لا Optimistic delete
- يُرسَل `null` أو `[]` في الـ payload
- عند النجاح: تُؤكَّد البيانات من الـ response

### Parent → Child Clearing

```js
// مثال: تغيير الدولة يمسح المدينة
countrySelect.addEventListener('change', () => {
  citySelect.value = ''       // مسح القيمة
  citySelect.innerHTML = ''   // مسح الخيارات
  refreshCityOptions(countrySelect.value)  // تحميل خيارات جديدة
})
```

---

## FRM-20 DOM Readiness & Initialization

### القاعدة

لا تُطبِّق Hydration على حقل قبل أن يكون في DOM.

مرئية العنصر (`hidden = false`) ≠ وجوده في DOM. الحقل يجب أن يكون موجوداً بالفعل في الـ DOM قبل أي `querySelector` أو `value =` عليه.

### الحلول الصحيحة للـ DOM Readiness

| السيناريو | الحل الصحيح |
|-----------|------------|
| Modal موجود في HTML من البداية | HTML `<script defer>` أو `DOMContentLoaded` |
| Modal يُضاف ديناميكياً بـ JS | `applyHydration()` مباشرةً بعد `appendChild()` في نفس الـ call stack |
| Bootstrap Modal | استخدم حدث `shown.bs.modal` الرسمي |
| Custom show/hide بـ `hidden` | `hidden = false` ثم استدعاء `applyHydration()` في نفس الـ call stack |

```js
// ✅ Modal موجود في HTML — DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  // الآن الحقول موجودة في DOM
  initFormHandlers()
})

// ✅ Modal يُنشأ ديناميكياً
function openModal(record) {
  const modal = buildModalDOM(record)  // يُنشئ العناصر
  document.body.appendChild(modal)     // يضيفها للـ DOM
  applyHydration(record)               // الآن querySelector يعمل
}

// ✅ Bootstrap Modal
document.getElementById('editModal').addEventListener('shown.bs.modal', () => {
  applyHydration(currentRecord)
})

// ❌ خطأ: await nextTick() / requestAnimationFrame — ليسا ضماناً لوجود الـ DOM
// document.getElementById('edit-modal').hidden = false
// await nextTick()  // ← لا يضمن وجود العناصر — يضمن فقط render cycle
// applyHydration(record)  // ← قد تفشل إذا العناصر لم تُضَف للـ DOM بعد
```

### الفرق الجوهري

```
Visible ≠ In DOM

hidden = false  → العنصر موجود في DOM ولكن كان مخفياً — querySelector يعمل
appendChild()   → العنصر يُضاف للـ DOM — querySelector يعمل بعده مباشرةً
nextTick()      → يضمن render cycle فقط — لا يضمن وجود عناصر لم تُضَف بعد
```

### Initializing Select Elements

```js
// ✅ بعد ملء الـ <select> بخيارات جديدة:
select.value = record.country
if (window.scSelectInit) scSelectInit()  // إعادة تهيئة custom dropdown
```
## FRM-21 Failure Contract

### ما يجب أن يحدث عند فشل الحفظ

**الثلاثية الإلزامية:**

1. **الفورم يبقى مفتوحاً** — لا إغلاق تلقائي
2. **قيم المستخدم تُحفَظ** — لا Reset، لا Hydration
3. **زر الحفظ يُستعاد** — يخرج من Loading ويعود للعمل

```js
function handleSaveError(errorData) {
  // 1. زر Save يُستعاد
  saveBtn.disabled = false
  saveBtn.classList.remove('loading')

  // 2. DS-VAL يعرض الأخطاء المناسبة
  displayErrors(errorData)  // inline أو form-level حسب DS-VAL

  // 3. الفورم يبقى مفتوحاً
  // لا closeModal() هنا
}
```

### Retry بعد Failure

**لا Reset، لا Hydration قبل Retry.**

المستخدم يُصلِح ما يلزم (بناءً على رسائل الخطأ) ويضغط Save مجدداً. إعادة الـ Reset تفقده تعديلاته.

**الإجراء الوحيد المسموح قبل Retry:**
- مسح رسائل الخطأ السابقة التي قد تعارض رسائل جديدة (الـ DS-VAL تتكفل بذلك عبر VAL-12)

---

## FRM-22 Core & Extended Regression Matrix

### Core Regression (إلزامي عند تعديل Lifecycle أو Save أو Hydration — لا يُطبَّق على تغييرات Label أو Placeholder أو CSS فقط)

| السيناريو | الاختبار |
|-----------|---------|
| **Add: فتح نظيف** | لا قيم من جلسة سابقة، لا أخطاء |
| **Edit: Prefill صحيح** | كل الحقول تعكس البيانات المحفوظة |
| **Save Success** | الفورم يُغلَق + Display يتحدث |
| **Save Failure: الفورم يبقى** | قيم المستخدم محفوظة + زر يُستعاد |
| **Reopen: لا stale** | بيانات سجل جديد، لا بيانات سجل سابق |
| **Double Submit** | الضغط المزدوج لا يُرسِل طلبَين |

### Extended Regression (يُضاف فوق Core عندما يمس التغيير هذه السيناريوهات تحديداً)

| السيناريو | متى يُطبَّق |
|-----------|------------|
| **Clearable field** | عند تعديل حقل nullable |
| **Conditional field** | عند وجود parent-child |
| **Async catalog** | عند وجود قوائم تُجلَب async |
| **Format validation** | عند تعديل validation rules |
| **Backend field error** | عند تعديل error mapping |
| **Parent select clears child** | عند وجود dependent selects |
| **Derived UI updates** | عند وجود computed display values |

---

## FRM-23 Out of Scope V1

| الحالة | السبب |
|--------|-------|
| نماذج تسجيل الدخول / الاشتراك | مسار مختلف — لا Dirty State، لا Record |
| نماذج البحث والفلترة | لا حفظ، لا Reset، لا Dirty |
| Wizard / Multi-step | يحتاج sub-states خاصة — DS-FRM V2 |
| Compose Message | no persistence model |
| نماذج التعليقات / الردود | مسار مختلف (live feedback) |
| Optimistic Updates مع Rollback | DS-FRM V2 |

---

## FRM-24 Historical Failure Modes

أنماط ظهرت في codebase وسببت مشاكل — موثَّقة للتجنب:

| الفشل | المشكلة | الحل |
|-------|---------|------|
| **Stale Modal** | فتح Edit على سجل B يعرض بيانات سجل A | Reset إلزامي قبل Hydration (FRM-05) |
| **Phantom Save** | `if (value) payload.field = value` يُسقِط null/false/0 | استخدم FRM-09 pattern |
| **Lost Changes on Retry** | Reset بعد فشل يمسح تعديلات المستخدم | الـ Reset فقط عند فتح جديد (FRM-21) |
| **Race Condition** | Hydration سجل A تُطبَّق على فورم B المفتوح لاحقاً | Generation Counter (FRM-10) |
| **Validation on Hydrate** | إظهار أخطاء على بيانات صالحة من DB | لا validation events أثناء Hydration (FRM-11) |
| **Partial Hydration** | بعض الحقول بقيم سجل سابق | Complete Hydration إلزامية (FRM-06) |
| **Double Submit** | ضغطتان سريعتان → طلبَان | guard `_submitting` (FRM-15) |

---

## FRM-25 Migration Status

### الحالة الراهنة في الـ Codebase

| الصفحة / الملف | الامتثال |
|----------------|---------|
| `company.main.js` (edit modal) | جزئي — Hydration موجودة، لكن بعض Failure patterns قائمة |
| `profile-v2.*.js` (edit modals) | جزئي — Save Success صحيح، Async Safety قائمة جزئياً |
| `company.jobs.js` (job modal) | جزئي — Add يعمل، Edit يحتاج مراجعة للـ Race Condition |

**هذا التوثيق هو الـ contract المستهدَف — الثغرات توثَّق هنا ولا تستلزم migration فورية.**

---

*[DS-FRM] V1 — أُنشئ في PR docs/design-system-forms-v1 — 2026-07-21*
*يُكمله: [DS-INP] INPUT-FIELDS.md · [DS-VAL] VALIDATION-ERRORS.md · [API-MUT] API-MUTATIONS-ERRORS.md*
