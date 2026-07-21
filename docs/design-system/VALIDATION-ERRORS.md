# [DS-VAL] Validation & Error Contract V1

> **نظام التحقق والأخطاء** — الـ contract الرسمي لتوقيت التحقق وعرض رسائل الخطأ في المنصة.

---

## VAL-00 Reading & Routing Protocol

**هذا الملف راوتر — اقرأ الأقسام ذات الصلة فقط:**

| المهمة | الأقسام |
|--------|---------|
| متى تظهر الأخطاء (التوقيت) | VAL-05 |
| عرض خطأ مرتبط بحقل معين | VAL-08 |
| خطأ من Backend يستهدف حقلاً | VAL-07 + VAL-08 |
| خطأ عام (لا حقل محدد) | VAL-09 |
| أين يتمركز Focus بعد Submit | VAL-10 |
| تنظيف الأخطاء | VAL-12 |
| صياغة رسالة الخطأ | VAL-17 |
| ما يجب تجنبه | VAL-18 |

**الأنظمة المكملة:**
- `DS-INP` (INPUT-FIELDS.md) — شكل حالة Error البصرية على الحقل (INP-05)
- `DS-FRM` (FORM-LIFECYCLE.md) — دورة الحياة والـ Retry (FRM-21)
- `API-MUT` (contracts/API-MUTATIONS-ERRORS.md) — شكل الـ Error Response من Backend

---

## VAL-01 Purpose

يُعرِّف هذا النظام:
- **متى** تُفعَّل الأخطاء (Timing — VAL-05)
- **أين** تُعرَض (Inline vs Form-level — VAL-08/VAL-09)
- **كيف** تُصنَّف (Frontend vs Backend — VAL-07)
- **كيف** تُنظَّف (Cleanup — VAL-12)

هذا النظام **لا يُعرِّف** شكل حقل الخطأ البصري (DS-INP)، ولا بناء الـ Payload (DS-FRM)، ولا شكل Error Response من API (API-MUT).

---

## VAL-02 Scope & Ownership

**DS-VAL يملك:**
- توقيت إظهار الأخطاء (Blur / Submit / Live)
- التحقق من المعايير الأساسية (Required، Format، Length)
- تصنيف أخطاء Backend وتوزيعها
- Focus/Scroll بعد Submit
- Accessibility لرسائل الأخطاء
- صياغة الرسائل (المحتوى اللغوي)

**DS-VAL لا يملك:**
- الشكل البصري للحقل (حد أحمر، background) → DS-INP
- دورة حياة الفورم (Reset، Hydration، Retry) → DS-FRM
- شكل Response الخطأ من Backend → API-MUT
- Content Moderation / Profanity → نظام Moderation منفصل (غير موثَّق بعد)

---

## VAL-03 Backend Authority

### القاعدة الذهبية

**Backend هو المرجع النهائي لصحة البيانات.**

Frontend validation = UX Layer فقط — يُقلِّل رحلات البيانات غير الضرورية ويُحسِّن التجربة، لكنه **لا يُغني** عن Server-side validation.

### التبعية

| طبقة Validation | المالك | الغرض |
|----------------|--------|-------|
| Required check | Frontend (DS-VAL) + Backend | منع إرسال فارغ |
| Format check (email، URL) | Frontend (DS-VAL) + Backend | تحسين UX + أمان |
| Uniqueness (email مكرر) | Backend فقط | يحتاج DB query |
| Business Rules (quota، conflict) | Backend فقط | يحتاج DB state |
| Security rules | Backend فقط | لا يُعتمَد على Frontend |

---

## VAL-04 Touched State

### تعريف Touched

حقل يُعتبَر **Touched** بعد أن يحصل على Focus ثم يفقده (Blur).

### التمييز

| الحالة | معناه | Validation؟ |
|--------|-------|------------|
| Untouched | لم يُفعَّل بعد | لا |
| Touched + صحيح | مرَّ بـ blur بقيمة صحيحة | لا خطأ |
| Touched + خطأ Format | مرَّ بـ blur بقيمة غير صحيحة | ✅ يظهر خطأ |
| Touched + فارغ (اختياري) | مرَّ بـ blur فارغاً | لا خطأ |

**Touched يُسجَّل بـ Blur — ليس بأول keystroke.**

---

## VAL-05 Validation Timing

### جدول التوقيت الرسمي

| المرحلة | ما يُتحقَّق منه | الشرط |
|---------|----------------|-------|
| **Keystroke (أول مرة)** | لا شيء | الحقل Untouched — لا أخطاء |
| **Input (بدون خطأ سابق)** | لا شيء | لم يُطلَق خطأ بعد |
| **Blur** | أخطاء Format فقط | القيمة غير فارغة وغير صحيحة |
| **Blur + فارغ (إجباري)** | لا خطأ Required | Required errors تظهر فقط عند Submit |
| **Submit** | كل شيء: Required + Format + Length + Conditional | يظهر كل ما يخفق |
| **Input (خطأ موجود)** | Live check | يُصحِّح الخطأ فور صواب القيمة |
| **Server Error (على حقل)** | يبقى حتى أول تغيير فعلي يجعل القيمة الحالية تختلف عن القيمة التي أُرسلت وتسببت بالخطأ | typing / deleting / pasting / selecting — ليس مجرد focus |

### المبدأ

> **لا تُعاقِب المستخدم قبل أن يُكمِل تفكيره.**
> أخطاء Required → عند Submit فقط.
> أخطاء Format → عند Blur (إذا لم يتركه فارغاً).
> بعد خطأ → صحِّح live.

### توقيت Server Errors

```
المستخدم يكتب "example@" → Submit → Backend يُعيد "invalid_email"
→ الخطأ يظهر على حقل email
→ المستخدم يُجري أول تغيير فعلي في حقل email (يكتب، يحذف، يلصق، أو يختار)
   والقيمة الجديدة تختلف عن "example@" التي أُرسلت → الخطأ يختفي
   (لا ينتظر حتى تصبح القيمة صحيحة كلياً)
```

---

## VAL-06 Empty Submit

### السيناريو

المستخدم يضغط Submit دون ملء أي حقل.

### السلوك الصحيح

```
1. تحقق من كل الحقول (Required + Format + Conditional)
2. أظهِر كل الأخطاء في وقت واحد
3. انقل Focus للحقل الأول به خطأ (VAL-10)
4. لا ترسل الطلب
```

### ممنوع

- إظهار خطأ حقل واحد فقط والتوقف
- إرسال الطلب ثم انتظار Backend لإعادة "required"

---

## VAL-07 Error Classification

**ملاحظة للتنفيذ:** DS-VAL يتولى توجيه الأخطاء وعرضها — أما **تحليل الـ Response الخام وتوحيد شكله** فهو مسؤولية `API-MUT` (عبر `normalizeErrorResponse()` في API-MUT-11). لا تُعيد كتابة Response Parser هنا.

### التصنيف بالأولوية

```
1. normalized.errors[].field موجود → Inline على الحقل المحدد
2. normalized.errors[] بدون field  → Form-level (خطأ عام)
3. Network error / Timeout / 5xx → General toast أو form-level message
4. HTTP status وحده              → Signal ثانوي فقط (ليس المصدر الأساسي للتصنيف)
```

### التوجيه بعد Normalization

```js
// DS-VAL يستهلك النموذج الموحَّد من API-MUT-11
function routeErrors(normalized) {
  for (const err of normalized.errors) {
    if (err.field) {
      showFieldError(err.field, err.message)  // Inline
    } else {
      showFormError(err.message || 'حدث خطأ، حاول مجدداً')  // Form-level
    }
  }
  if (normalized.errors.length > 0) focusFirstError()
}

// للاستخدام:
// const normalized = normalizeErrorResponse(body)  // API-MUT-11
// routeErrors(normalized)
```

---

## VAL-08 Inline Field Errors

### متى تُستخدَم

عندما الخطأ مرتبط بحقل محدد:
- Required + فارغ عند Submit
- Format غير صحيح (email، URL) عند Blur
- Backend error يحتوي `field` في response

### الـ DOM Pattern

```html
<div class="field-wrapper" id="wrapper-email">
  <label for="email">البريد الإلكتروني</label>
  <input id="email" type="email" aria-describedby="email-error" aria-invalid="false" />
  <span id="email-error" class="field-error" role="alert" aria-live="polite" hidden></span>
</div>
```

### تطبيق الخطأ بـ JS

```js
function showFieldError(fieldId, message) {
  const wrapper = document.getElementById(`wrapper-${fieldId}`)
  const errorEl = document.getElementById(`${fieldId}-error`)
  const inputEl = document.getElementById(fieldId)

  wrapper?.classList.add('has-error')
  if (errorEl) {
    errorEl.textContent = message  // دائماً textContent — لا innerHTML
    errorEl.hidden = false
  }
  inputEl?.setAttribute('aria-invalid', 'true')
}

function clearFieldError(fieldId) {
  const wrapper = document.getElementById(`wrapper-${fieldId}`)
  const errorEl = document.getElementById(`${fieldId}-error`)
  const inputEl = document.getElementById(fieldId)

  wrapper?.classList.remove('has-error')
  if (errorEl) {
    errorEl.textContent = ''
    errorEl.hidden = true
  }
  inputEl?.setAttribute('aria-invalid', 'false')
}
```

### XSS Safety

```js
// ✅ دائماً
errorEl.textContent = message

// ❌ ممنوع
errorEl.innerHTML = message
```

---

## VAL-09 Form-level Errors

### متى تُستخدَم

عندما الخطأ لا ينتمي لحقل محدد:
- Backend error بدون `field` في response
- Network error / 5xx / Timeout
- Business rule تمس الـ record ككل

### الـ DOM Pattern

```html
<div id="form-error-banner" class="form-error-banner" role="alert" aria-live="assertive" hidden>
  <span class="form-error-text"></span>
</div>
```

```js
function showFormError(message) {
  const banner = document.getElementById('form-error-banner')
  const text = banner?.querySelector('.form-error-text')
  if (text) text.textContent = message
  if (banner) banner.hidden = false
}

function clearFormError() {
  const banner = document.getElementById('form-error-banner')
  if (banner) banner.hidden = true
}
```

### الموضع

أعلى الفورم (قبل كل الحقول) أو أسفله مباشرةً — لا بينها.

---

## VAL-10 Focus & Scroll after Submit

### عند وجود أخطاء بعد Submit

```
1. انقل Focus للحقل الأول به خطأ (DOM order)
2. اطلب Scroll للتأكد أنه مرئي
```

```js
function focusFirstError() {
  const firstError = document.querySelector('.has-error input, .has-error textarea, .has-error select')
  if (!firstError) return
  firstError.focus()
  firstError.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
```

### ترتيب Focus

- DOM order (ليس أهمية الحقل)
- Required قبل Format إذا كانا في نفس الحقل
- لا تنقل Focus لـ Form-level error banner — يُقرأ بـ aria-live تلقائياً

---

## VAL-11 Error State Relationship

### قاعدة البحدود

**DS-VAL يُطلِق حالة الخطأ — DS-INP يُعرِّفها بصرياً.**

```
DS-VAL: showFieldError('email', 'صيغة غير صحيحة')
         ↓
         wrapper.classList.add('has-error')  ← قرار DS-VAL
         ↓
DS-INP: .has-error .field-input { border-color: var(--error-red) }  ← تعريف DS-INP
```

**ممنوع في DS-VAL:** تضمين CSS values مباشرةً (لا `element.style.borderColor = 'red'`)
**ممنوع في DS-INP:** تضمين validation logic (لا `input.oninput = () => { if (!regex.test...) }`)

---

## VAL-12 Error Cleanup Lifecycle

### جدول التنظيف

| الحدث | ما يُنظَّف |
|-------|-----------|
| **Actual value change / تغيير فعلي للقيمة في حقل به Server Error** | خطأ هذا الحقل فقط |
| **Keystroke في حقل به Frontend Error** | يبقى حتى تصبح القيمة صحيحة (Live check) |
| **Reset الفورم** | كل الأخطاء (Inline + Form-level) |
| **Submit ناجح** | كل الأخطاء (قبل الإغلاق) |
| **Submit فاشل** | أخطاء القيم الصحيحة فقط — الأخطاء الجديدة تُعرَض |
| **إغلاق الفورم** | كل الأخطاء (عبر Reset في الفتح التالي) |

### Server Error Cleanup — القاعدة الذهبية

Server Error على حقل يختفي عند **أول تغيير فعلي** في ذلك الحقل يجعل القيمة الحالية تختلف عن القيمة المُرسَلة التي تسببت بالخطأ — لا ينتظر حتى تصبح القيمة صحيحة كلياً.

```js
// يُستمَع لـ 'input' الذي يُطلَق عند كل تغيير فعلي (كتابة، حذف، لصق، اختيار)
field.addEventListener('input', () => {
  if (field.dataset.hasServerError) {
    // القيمة الحالية مختلفة عن المُرسَلة (لأن 'input' لا يُطلَق بدون تغيير)
    clearFieldError(field.id)
    delete field.dataset.hasServerError
  }
  // ثم Live check إذا الحقل كان به Frontend error
})
```

---

## VAL-13 Unified Add & Edit Handling

### القاعدة

**Shared Validation Core للـ Add والـ Edit — ليس بالضرورة وظيفة واحدة.**

المحظور هو **تكرار القواعد** في منطقَين مستقلَّين — ليس وجود wrapper functions منفصلة.

```js
// ✅ صحيح: Shared Core — القواعد تُعرَّف مرةً واحدة
const VALIDATION_RULES = {
  name: { required: true, message: 'الاسم مطلوب' },
  bio:  { maxLength: 300, message: 'النبذة لا تتجاوز 300 حرف' },
}

// Mode-specific wrappers مقبولة — تُطبِّق نفس القواعد
function validateAdd() {
  return runValidation(VALIDATION_RULES, { mode: 'add' })
}
function validateEdit() {
  return runValidation(VALIDATION_RULES, { mode: 'edit', skipEmpty: true })
}

// أو وظيفة واحدة إذا السياق يسمح
function validateForm(mode) {
  return runValidation(VALIDATION_RULES, { mode })
}
```

### ممنوع

```
❌ validateAddForm() بقواعد مكتوبة ← وvalidateEditForm() بنفس القواعد مكتوبةً مرةً ثانية
❌ schema مكرر في ملفين مختلفين لنفس الفورم
❌ رسائل الخطأ مكتوبة مرتَين بنص مختلف قليلاً
```

### مقبول

```
✅ وظيفتان منفصلتان تستدعيان Shared Core أو Shared Schema
✅ mode param يُفرِّق بين Add و Edit داخل وظيفة واحدة
✅ wrapper يُضيف Edit-only checks (مثل: skipEmpty للحقول غير المُعبَّأة)
```
## VAL-14 Safe Messages

### القاعدة

رسائل الخطأ **لا تكشف** عن بنية DB أو Backend internals.

| ممنوع | البديل |
|-------|--------|
| `"Column 'email' has duplicate key"` | `"البريد الإلكتروني مستخدم مسبقاً"` |
| `"Foreign key constraint failed"` | `"لا يمكن تنفيذ هذا الإجراء الآن"` |
| `"500 Internal Server Error"` | `"حدث خطأ في الخادم، حاول لاحقاً"` |
| `"Invalid UUID format"` | `"البيانات المُرسَلة غير صحيحة"` |

Backend مسؤول عن إرسال رسائل آمنة — Frontend لا تعرض `err.detail` أو Stack trace للمستخدم.

---

## VAL-15 Content Moderation Boundary

هذا النظام (DS-VAL) **لا يتعامل** مع:
- فحص الكلمات المسيئة (Profanity Filter)
- Content Moderation
- Spam detection

هذه تنتمي لـ نظام Moderation (غير موثَّق بعد في SYSTEMS_INDEX.md).

DS-VAL يعرض رسالة الخطأ التي يُعيدها Backend من نظام Moderation — ولا يُنفِّذ الفحص بنفسه.

---

## VAL-16 Accessibility

### قواعد إلزامية

1. **`role="alert"` + `aria-live="polite"`** على `.field-error` — يُقرأ تلقائياً عند الظهور
2. **`aria-live="assertive"`** على Form-level error banner — إعلان فوري
3. **`aria-invalid="true"`** على الـ input عند وجود خطأ
4. **`aria-describedby`** يربط الـ input بـ `.field-error` المرتبطة
5. **Focus إلزامي** على أول حقل خاطئ بعد Submit (VAL-10)
6. **`role="alert"` لا يُضاف على كل شيء** — فقط رسائل الخطأ الفعلية

### Screen Reader Testing Pattern

عند إضافة خطأ:
- `aria-live="polite"` → يُقرأ بعد انتهاء القراءة الحالية
- `aria-live="assertive"` → يقاطع القراءة الحالية (للأخطاء الحرجة فقط)

---

## VAL-17 Error Message Quality

### القواعد

1. **محددة** — تقول ماذا حدث بالضبط:
   - ✅ `"البريد الإلكتروني مستخدم مسبقاً"`
   - ❌ `"خطأ في البريد الإلكتروني"`

2. **قابلة للتصرف** — تقول ماذا يفعل المستخدم:
   - ✅ `"يجب أن تحتوي كلمة المرور على 8 أحرف على الأقل"`
   - ❌ `"كلمة المرور ضعيفة"`

3. **لا اعتذار** — مباشرة دون "عذراً" أو "للأسف":
   - ✅ `"الحقل مطلوب"`
   - ❌ `"عذراً، الحقل مطلوب"`

4. **بالعربية** — كل رسائل الخطأ للمستخدم بالعربية
5. **لا HTML أو رموز تقنية** في الرسائل

### قاموس رسائل شائعة (مرجعي)

| الحالة | الرسالة |
|--------|---------|
| Required | `"هذا الحقل مطلوب"` |
| Required + اسم الحقل | `"[اسم الحقل] مطلوب"` |
| Email format | `"أدخل بريداً إلكترونياً صحيحاً"` |
| Email مكرر | `"البريد الإلكتروني مستخدم مسبقاً"` |
| URL format | `"أدخل رابطاً صحيحاً يبدأ بـ https://"` |
| كلمة مرور قصيرة | `"كلمة المرور يجب أن تكون 6 أحرف على الأقل"` |
| طول max تجاوز | `"النص طويل جداً (الحد الأقصى: X حرف)"` |
| خطأ عام | `"حدث خطأ، حاول مجدداً"` |
| Network error | `"تعذَّر الاتصال، تحقق من الإنترنت وأعِد المحاولة"` |
| Server 5xx | `"حدث خطأ في الخادم، حاول لاحقاً"` |

---

## VAL-18 Forbidden Patterns

```
❌ إظهار Required error عند Blur — يُعاقِب المستخدم قبل Submit
❌ إظهار أي خطأ عند أول keystroke (الحقل Untouched)
❌ Server Error يبقى حتى Blur أو حتى تصبح القيمة صحيحة كلياً — يختفي عند أول تغيير فعلي يجعل القيمة تختلف عن المُرسَلة
❌ errorEl.innerHTML = message — يُعرِّض لـ XSS
❌ رسائل خطأ بالإنجليزية للمستخدم
❌ كشف DB errors أو Stack traces للمستخدم
❌ تكرار قواعد Validation بين Add وEdit في منطقَين مستقلَّين (وظيفتان wrapper منفصلتان مقبولتان — المحظور هو تكرار القواعد نفسها)
❌ إعادة التحقق (Revalidate) بدون سبب أثناء Hydration
❌ إغلاق الفورم عند فشل الحفظ — يجب أن يبقى مفتوحاً مع الأخطاء
❌ Profanity check في DS-VAL — ينتمي لنظام Moderation منفصل
❌ استخدام HTTP status كمصدر أساسي لتحديد نوع الخطأ
❌ Form-level error في منتصف الفورم — يكون أعلاه أو أسفله فقط
❌ خطأ بدون حالة بصرية مرئية — يجب دائماً .has-error + .field-error
```

---

## VAL-19 Current Gaps / Migration Notes

### الثغرات القائمة في الـ Codebase (V1)

| الصفحة | الثغرة | الأولوية |
|--------|--------|---------|
| `company.main.js` | بعض Server Errors تبقى حتى Blur بدلاً من تغيير فعلي للقيمة | متوسطة |
| `profile-v2.*.js` | Validation في بعض Modal handlers غير موحَّد | متوسطة |
| `employees-group.html` | لا `role="alert"` على بعض رسائل الخطأ | منخفضة |

**هذا التوثيق هو الـ contract المستهدَف — الثغرات لا تستلزم migration فورية.**

---

## VAL-20 Out of Scope V1

| الحالة | السبب |
|--------|-------|
| Profanity / Content Moderation | نظام منفصل — DS-VAL يعرض نتيجتها فقط |
| Rate limiting errors (429) | API-MUT يُصنِّفها — DS-VAL يعرضها كـ form-level |
| Async validation (email uniqueness client-side) | Backend-only — DS-VAL لا تستدعي API للتحقق |
| Custom Validation Rules per Business Domain | تُضاف في كل Module بالإشارة لـ DS-VAL principles |
| Schema-driven forms | V2 مستقبلي |

---

*[DS-VAL] V1 — أُنشئ في PR docs/design-system-forms-v1 — 2026-07-21*
*يُكمله: [DS-INP] INPUT-FIELDS.md · [DS-FRM] FORM-LIFECYCLE.md · [API-MUT] API-MUTATIONS-ERRORS.md*
