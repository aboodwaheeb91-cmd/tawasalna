# [API-MUT] API Mutation & Error Contract V1

> **عقد تحويلات الـ API والأخطاء** — الـ contract الرسمي لتفسير الـ PATCH semantics وشكل Error responses في المنصة.

---

## API-MUT-00 Reading & Routing Protocol

**هذا الملف راوتر — اقرأ الأقسام ذات الصلة فقط:**

| المهمة | الأقسام |
|--------|---------|
| فهم PATCH vs PUT semantics | API-MUT-03 |
| كيف يُفسَّر empty string في Backend | API-MUT-04 |
| شكل Success Response | API-MUT-07 |
| شكل Error Response (حقل محدد) | API-MUT-08 |
| شكل Error Response (عام) | API-MUT-10 |
| تصنيف الأخطاء | API-MUT-12 |
| ما يجب على Backend التحقق منه | API-MUT-13 |
| الممنوعات | API-MUT-16 |

**الأنظمة المكملة:**
- `DS-FRM` (FORM-LIFECYCLE.md) — بناء الـ Payload (FRM-09) قبل الإرسال
- `DS-VAL` (VALIDATION-ERRORS.md) — تفسير Error Response وعرضه (VAL-07)
- `DS-INP` (INPUT-FIELDS.md) — عرض الخطأ على الحقل بصرياً (INP-05)

---

## API-MUT-01 Purpose

يُعرِّف هذا الـ contract:
- **Tri-state Patch Semantics:** كيف يُفسِّر Backend الـ payload المُرسَل
- **Empty String:** كيف تُعالَج قبل الإرسال (Frontend) وبعده (Backend)
- **Field Ownership:** أي الحقول يقبلها كل endpoint
- **Error Response Shape:** الشكل الموحَّد لكل أخطاء الـ mutation
- **Success Response Shape:** ما يُعيده الـ endpoint عند النجاح

---

## API-MUT-02 Scope & Ownership

**هذا الـ contract يخص:**
- جميع endpoints التي تُعدِّل بيانات (`PUT`، `PATCH`، `POST` للإنشاء)
- ردود الـ API على طلبات التعديل

**خارج النطاق:**
- `GET` endpoints (read-only)
- Auth endpoints (لها contract منفصل)
- Upload endpoints (`POST /upload/image` — `tw-upload.js`)
- WebSocket messages

---

## API-MUT-03 Tri-state Backend Semantics

### المبدأ

Backend يُفرِّق بين ثلاث حالات في الـ PATCH payload:

| ما يصل لـ Backend | التفسير |
|-----------------|---------|
| **الحقل غائب (omitted)** | لا تغيير — احتفظ بالقيمة الحالية في DB |
| **قيمة (string، number، bool، array)** | تحديث بهذه القيمة |
| **`null` صريح** | مسح / حذف القيمة (NULL في DB) |

### مثال

```json
// PATCH /profile/123
{
  "name": "أحمد",
  "bio": null,
  "website": "https://example.com"
}
// → name تُحدَّث
// → bio تُمسَح (NULL)
// → website تُحدَّث
// → city لم يُذكَر → لا تغيير (تبقى كما هي في DB)
```

### المتطلبات في Backend

```python
# auth.py — مثال على update_profile

ALLOWED_FIELDS = {'name', 'bio', 'website', 'city', 'country'}
CLEARABLE_FIELDS = {'bio', 'website', 'city'}

def update_profile(user_id: int, data: dict):
    updates = []
    params = {}

    for field, value in data.items():
        if field not in ALLOWED_FIELDS:
            continue  # حقول غير مصرَّح بها تُتجاهَل صامتةً

        if value is None:
            if field not in CLEARABLE_FIELDS:
                continue  # لا يُمسَح حقل non-clearable
            updates.append(f"{field} = NULL")
        else:
            updates.append(f"{field} = :{field}")
            params[field] = value

    if not updates:
        return  # لا تغييرات — لا query

    conn.run(f"UPDATE profiles SET {', '.join(updates)} WHERE user_id = :uid",
             uid=user_id, **params)
```

---

## API-MUT-04 Empty String Contract

### القاعدة

**Empty string (`""`) لا يصل للـ Backend إلا في حالة استثنائية صريحة.**

### المسؤوليات

| الطرف | المسؤولية |
|-------|----------|
| **Frontend (DS-FRM)** | يُحوِّل `""` → `null` لكل الحقول الاختيارية القابلة للمسح |
| **Frontend (DS-VAL)** | يُوقِف الإرسال إذا حقل إجباري فارغ (Validation Error) |
| **Backend** | يُعالِج `null` على أنه CLEAR — لا يُعالِج `""` على أنه CLEAR |

### الحالات

| الحقل | القيمة المُرسَلة | الدلالة |
|-------|----------------|---------|
| اختياري + المستخدم مسح القيمة | `null` | Backend يُفرِّغ الحقل في DB |
| إجباري + فارغ | الطلب لا يُرسَل | DS-VAL توقفه |
| **Exception:** حقل يقبل `""` بشكل مقصود | `""` | يُوثَّق صراحةً لكل endpoint |

### ممنوع

```python
# ❌ Backend يعامل "" كـ CLEAR دون اتفاق
if value == "" or value is None:
    updates.append(f"{field} = NULL")
```

```js
// ❌ Frontend يُرسِل "" دون تحويل
payload.bio = bioInput.value  // قد يكون ""
```

---

## API-MUT-05 Field Ownership & Allowlist

### القاعدة

كل endpoint يملك **allowlist صريحة** للحقول المقبولة.

```python
# ✅ صحيح
ALLOWED = {'name', 'bio', 'city', 'country', 'website'}

for field in incoming_data:
    if field not in ALLOWED:
        continue  # تُتجاهَل صامتةً — لا HTTP 400

# ❌ خطأ
for field in incoming_data:
    db_update(field, incoming_data[field])  # SQL injection risk + unintended writes
```

### الـ allowlist والـ clearable قائمتان منفصلتان

```python
ALLOWED   = {'name', 'bio', 'city', 'country', 'website', 'is_public'}
CLEARABLE = {'bio', 'city', 'country', 'website'}
# → name و is_public في ALLOWED لكن ليسا في CLEARABLE → null مُتجاهَل
```

---

## API-MUT-06 One Source of Truth Reference

### المبدأ (من ARCHITECTURE_FOUNDATION.md — F5)

**لا حقلان يحكمان نفس البيانات.**

تطبيقه على API Mutations:
- `profiles.avail` هو المصدر الوحيد لحالة التوفر — لا `availability_status`
- `profiles.country` للموظف يُخزِّن ISO code — لا Arabic name
- لا تُعدِّل نفس البيانات عبر endpointَين مختلفَين بدون تنسيق صريح

---

## API-MUT-07 Mutation Success Response

### المتطلبات

عند نجاح الـ mutation، الـ response يحتوي:

```json
{
  "status": "ok",
  "data": {
    // الـ record المحدَّث كاملاً — ليس الـ fields التي تغيَّرت فقط
    "id": 42,
    "name": "أحمد",
    "bio": null,
    "city": "عمان",
    // ... كل الـ fields التي يحتاجها الـ Display View
  }
}
```

### القاعدة

الـ response يجب أن يكفي لتحديث الـ UI **بدون Refetch إضافي** — راجع DS-FRM FRM-17.

### HTTP Status

| الحالة | الـ Status |
|--------|-----------|
| إنشاء ناجح | `201 Created` |
| تحديث ناجح | `200 OK` |

---

## API-MUT-08 Target Field Error Shape

### الشكل الرسمي

عند وجود خطأ مرتبط بحقل محدد:

```json
{
  "errors": [
    {
      "field": "email",
      "code": "already_exists",
      "message": "البريد الإلكتروني مستخدم مسبقاً"
    }
  ]
}
```

### الحقول

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `field` | string | اسم الـ field في Frontend (يطابق `id` أو `name` الـ input) |
| `code` | string | رمز آلي للخطأ (للـ Frontend logic) |
| `message` | string | رسالة بالعربية للمستخدم |

### قيم `code` المعيارية

| الكود | المعنى |
|-------|--------|
| `required` | الحقل مطلوب ولم يُرسَل |
| `already_exists` | قيمة مكررة (email، username) |
| `invalid_format` | صيغة غير صحيحة |
| `too_long` | تجاوز الحد الأقصى |
| `too_short` | أقل من الحد الأدنى |
| `invalid_value` | قيمة غير مقبولة من القائمة |
| `not_found` | مرجع غير موجود (FK) |

---

## API-MUT-09 Multiple Field Errors

### السيناريو

Backend يُعيد أخطاء لأكثر من حقل في نفس الوقت:

```json
{
  "errors": [
    {
      "field": "email",
      "code": "already_exists",
      "message": "البريد الإلكتروني مستخدم مسبقاً"
    },
    {
      "field": "phone",
      "code": "invalid_format",
      "message": "صيغة رقم الهاتف غير صحيحة"
    }
  ]
}
```

### المعالجة في Frontend

```js
if (body.errors?.length) {
  body.errors.forEach(err => {
    if (err.field) showFieldError(err.field, err.message)
    else showFormError(err.message)
  })
  focusFirstError()
}
```

---

## API-MUT-10 Target General Error Shape

### شكل الخطأ العام (بدون حقل محدد)

```json
{
  "errors": [
    {
      "code": "permission_denied",
      "message": "ليس لديك صلاحية تنفيذ هذا الإجراء"
    }
  ]
}
```

أو للأخطاء البسيطة:

```json
{
  "error": "ليس لديك صلاحية تنفيذ هذا الإجراء"
}
```

**Frontend يعرضه كـ Form-level error (DS-VAL VAL-09).**

---

## API-MUT-11 Legacy Adapter

### السياق

بعض الـ endpoints الحالية تُعيد أشكالاً مختلفة من الأخطاء (موروثة من مراحل سابقة).

### قاعدة التعامل

Frontend يطبِّق **adapter** لتوحيد الأشكال الموروثة:

```js
function normalizeErrorResponse(body) {
  // الشكل الجديد: { errors: [{ field, code, message }] }
  if (Array.isArray(body?.errors)) return body.errors

  // الشكل القديم: { message: "..." }
  if (body?.message) return [{ message: body.message }]

  // الشكل القديم: { detail: "..." }
  if (body?.detail) return [{ message: body.detail }]

  // Fallback
  return [{ message: 'حدث خطأ، حاول مجدداً' }]
}
```

### قاعدة Migration

**الـ endpoint الجديد يستخدم الشكل الرسمي فقط** (API-MUT-08 / API-MUT-10).
الشكل القديم يُحتفَظ به فقط لـ backward compat مع endpoints موجودة.

---

## API-MUT-12 Error Classification

### التصنيف

| HTTP Status | الخطأ الشائع | التفسير في DS-VAL |
|------------|-------------|-----------------|
| `400` | Validation error | `errors[]` يحتوي تفاصيل الحقول |
| `401` | Not authenticated | redirect للـ login |
| `403` | Not authorized | form-level error |
| `404` | Resource not found | form-level error |
| `409` | Conflict (duplicate، quota) | `errors[]` بـ code محدد |
| `422` | Unprocessable entity | مثل 400 |
| `429` | Rate limited | form-level error + "حاول لاحقاً" |
| `5xx` | Server error | form-level error + "حاول لاحقاً" |

### HTTP Status كـ Signal ثانوي

HTTP status يوجِّه التصنيف لكن **Response body هو المصدر الأساسي** للرسائل والحقول المتأثرة.

---

## API-MUT-13 Backend Validation Authority

### ما يجب أن يتحقق منه Backend دائماً

- **أن الـ user_id من JWT** — لا من body أو query param
- **أن للمستخدم صلاحية** تعديل هذا الـ record
- **أن القيم ضمن الـ constraints** (طول، format، uniqueness)
- **أن الـ FK references** موجودة في DB
- **أن الـ allowlist مُحترَمة** — حقول خارج allowlist تُتجاهَل

### ما يُوفِّره Frontend (UX فقط)

- Required check قبل الإرسال
- Format check قبل الإرسال
- Character limit client-side

**Frontend validation لا تُغني عن Backend validation.**

---

## API-MUT-14 Backward Compatibility

### القاعدة

تغيير شكل Response لـ endpoint موجود يُعتبَر **Breaking Change**.

### إجراء Breaking Change

1. تغيير مسار الـ endpoint (`/profile/v2`) **أو**
2. توثيق migration plan + `?version=2` query param **أو**
3. الإبقاء على الشكل القديم مع إضافة الشكل الجديد بجانبه

لا تُغيِّر Response shape لـ endpoint مستخدَم بدون خطة migration موثَّقة.

---

## API-MUT-15 Flutter Compatibility

### سياق المستقبل (F1)

المنصة ستدعم Flutter (F1 في ARCHITECTURE_FOUNDATION.md).

### قواعد مراعاة Flutter

1. **لا `undefined` في JSON** — استخدم `null` أو احذف الـ field
2. **لا أنواع ديناميكية** — حقل `value` إما `string` دائماً أو `number` دائماً، ليس مرةً `string` ومرةً `number`
3. **Error shape موحَّدة** — `errors: [{ field?, code, message }]` ثابتة لا تتغير بالـ status code
4. **لا HTML في رسائل الخطأ** — Flutter لا يُعالِج HTML
5. **`data` wrapper للـ Success** — يسهِّل parsing في Dart

```json
// ✅ Flutter-safe response
{
  "status": "ok",
  "data": { ... }
}

// ❌ Flutter-unfriendly
{
  "id": 42,
  "name": "أحمد"
  // لا wrapper — harder to parse
}
```

---

## API-MUT-16 Forbidden Patterns

```
❌ user_id أو company_id مقروء من request body لأغراض الأمان — من JWT فقط
❌ Response body يكشف DB errors (column names، constraint names، table names)
❌ Response body يكشف Stack traces
❌ Empty string يُعامَل كـ null في Backend بدون اتفاق صريح
❌ null يُرفَض لحقل clearable — يجب قبوله وتخزينه كـ NULL في DB
❌ false يُعامَل كـ "لا تغيير" — false قيمة حقيقية
❌ 0 يُعامَل كـ "لا تغيير" — 0 قيمة حقيقية
❌ الأخطاء تُعاد بـ HTML بدلاً من JSON
❌ رسائل الخطأ بالإنجليزية أو رموز تقنية مكشوفة للمستخدم
❌ Breaking change في Response shape بدون توثيق migration
❌ الـ allowlist غائبة — كل الـ fields يُقبَل
❌ تغيير user_id من Frontend — دائماً من JWT
❌ إرسال "" (empty string) بدون تحويل لـ null من Frontend
❌ PUT endpoint يُعيد 204 No Content بدون response body — يجبر Refetch
❌ PATCH بدون allowlist يكتب كل ما يأتيه (Mass Assignment)
```

---

## API-MUT-17 Current Gaps

### الـ endpoints الحالية التي لا تطابق هذا الـ contract بالكامل

| الـ Endpoint | الثغرة |
|-------------|--------|
| `PUT /profile/{user_id}` | بعض أخطاء الـ Backend تُعاد كـ `{"message":"..."}` بدون `errors[]` |
| `PUT /company/profile/{id}` | نفس الثغرة |
| معظم endpoints | لا `code` في Error Response — فقط `message` |

**هذا التوثيق هو الـ contract المستهدَف — الثغرات توثَّق هنا ولا تستلزم migration فورية.**

---

## API-MUT-18 Out of Scope V1

| الحالة | السبب |
|--------|-------|
| `GET` endpoints | read-only — لا mutations |
| `DELETE` endpoints | مسار مختلف — لا payload |
| Auth endpoints (login/register) | contract منفصل |
| Upload endpoints | `tw-upload.js` contract |
| GraphQL mutations | ليس مستخدَماً في V1 |
| Optimistic Updates مع conflict resolution | DS-FRM V2 |
| Idempotency keys | V2 |

---

*[API-MUT] V1 — أُنشئ في PR docs/design-system-forms-v1 — 2026-07-21*
*يُكمله: [DS-INP] INPUT-FIELDS.md · [DS-FRM] FORM-LIFECYCLE.md · [DS-VAL] VALIDATION-ERRORS.md*
