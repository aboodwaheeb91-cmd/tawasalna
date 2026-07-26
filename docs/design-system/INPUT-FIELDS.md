# [DS-INP] Input Fields System V1

> **نظام حقول الإدخال** — الـ contract البصري والتنظيمي لكل حقول الإدخال في المنصة.

---

## INP-00 Reading & Routing Protocol

**هذا الملف راوتر — اقرأ الأقسام ذات الصلة فقط:**

| المهمة | الأقسام |
|--------|---------|
| بناء حقل إدخال جديد | INP-03 + INP-04 + INP-05 |
| تحديد حالة بصرية (Error / Focus / Disabled) | INP-05 |
| Label / Placeholder / Helper Text | INP-06 |
| Textarea vs Input | INP-07 |
| Character Counter | INP-08 |
| Password / Email / Tel / URL | INP-09 + INP-11 + INP-13 |
| RTL + Accessibility | INP-12 |
| ما يجب تجنبه | INP-14 |

**الأنظمة المكملة (اقرأها إذا كانت مهمتك تتجاوز البصريات):**
- `DS-FRM` (FORM-LIFECYCLE.md) — متى يُعرَض Error وكيف تُدار حياة الفورم
- `DS-VAL` (VALIDATION-ERRORS.md) — توقيت التحقق وربط رسائل الخطأ بالحقل
- `DS-BTN` (BUTTONS.md) — زر الحفظ ضمن الفورم

---

## INP-01 Purpose

يُعرِّف هذا النظام **الشكل البصري** لعناصر الإدخال النصي في المنصة:
- الهيكل الدلالي لكل حقل (wrapper → label → input → helper)
- الحالات البصرية (Normal / Focus / Error / Disabled)
- قواعد العرض (اتجاه / label / placeholder / counter)

هذا النظام **لا يحدِّد** متى تظهر الأخطاء أو كيف تُرسَل البيانات — ذلك من اختصاص `DS-VAL` و `DS-FRM`.

---

## INP-02 Scope & Ownership

**داخل النطاق:**
- `<input type="text/email/password/tel/url/number/search">`
- `<textarea>`
- حقول البحث البسيطة

**خارج النطاق V1 — انظر INP-16:**
- `<select>` والقوائم المنسدلة → `static/shared/tw-select.js` موجود Runtime — لكن **DS-SEL غير موثَّق كنظام Design System رسمي بعد**؛ STOP عند الحاجة إلى Select جديد (F30)
- Datepicker / Date range
- Multi-select / Tags input
- File upload → `static/shared/tw-upload.js`
- Rich text editor / WYSIWYG
- OTP / Pin input
- Slider / Range
- Radio / Checkbox / Toggle

**ملكية الـ CSS:**
- لا يوجد global `tw-input.css` بعد — V1 توثيق فقط
- CSS الحالي: موزَّع per-page (`company.css`، `profile-v2.css`، إلخ)
- ممنوع إنشاء `tw-input.css` حتى يُطلب صراحةً

---

## INP-03 Canonical Field Anatomy

كل حقل إدخال يتبع هذا الهيكل الدلالي بالترتيب:

```
┌─ .field-wrapper ──────────────────────────────────┐
│  <label>  ← للحقل + optional indicator عند الحاجة │
│  ┌─ .input-wrapper ──────────────────────────────┐│
│  │  <input> / <textarea>                         ││
│  │  [أيقونة / suffix / زر show-password]        ││
│  └───────────────────────────────────────────────┘│
│  <span class="field-error">  ← رسالة الخطأ       │
│  <span class="field-hint">   ← نص مساعد ثابت    │
└───────────────────────────────────────────────────┘
```

**قواعد الهيكل:**
1. `.field-wrapper` يحتوي الحقل كاملاً ويستقبل state classes (`.has-error`، `.is-disabled`)
2. `<label>` يأتي **قبل** `<input>` دائماً في DOM — لا يُوضع بعده حتى لو يُعرَض بصرياً بشكل مختلف
3. `.field-error` و `.field-hint` يرتبطان معاً بالحقل عبر `aria-describedby` — يُعرَض كلاهما أو أحدهما حسب السياق؛ الخطأ يأخذ الأولوية البصرية لكن إخفاء `.field-hint` عند الخطأ ليس إلزامياً
4. لا يوجد `.field-success` — لا حالة "Valid" مرئية بعد الكتابة (انظر INP-05)

---

## INP-04 Required & Optional Presentation

### القاعدة الأساسية

**الإجباري (Required):** يُعرَض باسم الحقل فقط — **ممنوع استخدام `*` للإشارة للإجباري**.

**الاختياري (Optional):** يُكتب `(اختياري)` بجانب الـ Label.

**عند وجود 2+ حقل اختياري:** يُضاف تنبيه واحد أسفل العنوان أو أعلى الفورم:
> *"جميع الحقول مطلوبة إلا المشار إليها بأنها اختيارية."*

### المعادلة

```
إذا (كل الحقول إجبارية):
  لا تعليم مرئي — الـ aria-required يكفي

إذا (حقل واحد اختياري):
  الاختياري → label + " (اختياري)"

إذا (عدد الاختياري >= 2):
  الاختياري     → label + " (اختياري)"
  تنبيه واحد   → "جميع الحقول مطلوبة إلا المشار إليها بأنها اختيارية."
```

### مثال HTML

```html
<!-- إجباري: لا علامة مرئية إضافية -->
<label for="field-email">البريد الإلكتروني</label>
<input id="field-email" type="email" required aria-required="true" />

<!-- اختياري -->
<label for="field-bio">
  نبذة <span class="optional-label">(اختياري)</span>
</label>
<input id="field-bio" type="text" />
```

### ممنوعات INP-04

```
❌ <span class="required-star">*</span> — لا نجمة لأي غرض
❌ الاعتماد على اللون أو الرمز وحده للتفريق بين إجباري واختياري — يجب نص صريح
```
## INP-05 Visual States

### الحالات المعرَّفة

| الحالة | المحفِّز | المؤشر البصري |
|--------|---------|--------------|
| **Normal** | الحالة الافتراضية | خلفية الحقل + حد محايد خافت (contrast ≥ 3:1 مع خلفية الصفحة) |
| **Focus** | `:focus` أو `:focus-visible` | حد أخضر accent (`--ac`) يحل محل الحد المحايد — **لا layout shift** |
| **Error** | DS-VAL يُطلِق حالة الخطأ | حد أحمر يحل محل المحايد + `.field-error` مرئية |
| **Error + Focus** | خطأ موجود + المستخدم يكتب | الحد الأحمر يبقى — Focus indicator ممكن منفصلاً — يتحول للأخضر فقط عندما تصبح القيمة صحيحة |
| **Disabled** | `disabled` attribute | opacity مخففة + cursor not-allowed + لا focus + **يُلغي Error بصرياً** |
| **Filled/Normal** | بعد كتابة قيمة صحيحة | مثل Normal — **لا حد أخضر دائم "Valid"** |

### أولوية الحالات (State Priority)

```
Disabled > Error > Focus > Filled/Normal
```

- إذا الحقل Disabled + به خطأ سابق → يُعرَض كـ Disabled فقط (الخطأ لا يظهر بصرياً)
- إذا الحقل Error + يحصل على Focus → الخطأ يبقى (لا يُخفى)
- لا تُنشئ حالة "Valid" مرئية (حد أخضر دائم) — تسبب ضوضاء بصرية

### CSS Pattern (مرجعي)

```css
.field-input {
  border: 1.5px solid var(--border-subtle); /* neutral */
  outline: none;
  transition: border-color 0.15s ease;
}

.field-input:focus {
  border-color: var(--ac); /* accent green */
}

.has-error .field-input {
  border-color: var(--error-border);  /* Design Token — لا قيم hex مباشرة */
}

.has-error .field-input:focus {
  /* Red border stays; optional: extra focus ring */
  outline: 2px solid var(--error-ring);  /* Design Token */
  outline-offset: 1px;
}


.field-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: var(--border-subtle); /* overrides error */
}
```

---

## INP-06 Labels / Placeholders / Helper Text

### Label

- **إلزامي** لكل حقل — لا حقل بدون `<label>` مرتبط
- الارتباط عبر `for` / `id` أو wrapping — لا `aria-label` وحده كبديل عن Label مرئي
- يُكتب بالعربية، يعبِّر عن محتوى الحقل (لا عن الإجراء)
- ✅ `"الاسم الكامل"` — ❌ `"أدخل اسمك الكامل"`

### Placeholder

- **مكمِّل** للـ Label — لا يُستخدم **بديلاً** عنه
- يختفي عند الكتابة — لذلك لا يصلح للمعلومات الضرورية
- استخدمه لمثال أو hint قصير: `"مثال: عمان، الأردن"`
- ممنوع: placeholder بدون label، placeholder يكرِّر الـ label حرفياً

### Helper Text (`.field-hint`)

- نص ثابت يظهر دائماً تحت الحقل (قبل أي خطأ)
- للإرشادات: الطول المطلوب، الشكل المقبول، ملاحظة
- يمكن إخفاؤه عند ظهور `.field-error` إذا كان الخطأ يحل محله بصرياً — ليس إلزامياً؛ السياق هو الفيصل
- طوله ≤ 2 سطر — للتفسير الطويل استخدم tooltip منفصل

---

## INP-07 Single-line Inputs & Textareas

### متى تستخدم كلاً منهما

| نوع الحقل | العنصر |
|-----------|--------|
| نص قصير (اسم، email، رابط، مدينة) | `<input type="text/email/url/...">` |
| نص متوسط (سطر إلى سطرين) | `<input>` + `maxlength` |
| نص طويل (وصف، bio، ملاحظة) | `<textarea>` |
| محتوى يتوقع المستخدم تنسيقه بأسطر | `<textarea>` |

### Textarea — قواعد خاصة

- `rows` الابتدائي: 3–4 أسطر مرئية كحد أدنى
- `resize: vertical` فقط إذا كان مسموحاً — `resize: none` إذا كان المحتوى ذو حجم مُقيَّد
- نفس الـ visual states المطبَّقة على `<input>`

> **Auto-resize / Auto-grow:** خارج نطاق V1 — انظر INP-16.

---

## INP-08 Character Limits & Counters

### متى يُستخدم Counter

- عند وجود `maxlength` **وضيق الهامش** مهم للمستخدم (bio، وصف وظيفة، تغريدة)
- لا يُستخدم في حقول اسم قصيرة (50–100 حرف) ما لم يكن هناك سبب UX

### Counter Pattern

```
[textarea]
                              47 / 300
```

- يُعرَض أسفل يمين الـ textarea (في RTL: أسفل يسار)
- يتحدث لحظياً عند الكتابة
- عند الاقتراب من الحد (مثلاً < 10% متبقية): اللون يتغير للتحذير
- عند تجاوز الحد: يُعرَض بالأحمر + `.field-error` تظهر

### HTML Pattern

```html
<div class="field-wrapper">
  <label for="bio">نبذة</label>
  <textarea id="bio" maxlength="300" aria-describedby="bio-counter bio-error"></textarea>
  <div class="field-footer">
    <span class="field-error" id="bio-error" role="alert" hidden></span>
    <span class="field-counter" id="bio-counter">
      <span class="char-count">0</span> / 300
    </span>
  </div>
</div>
```

---

## INP-09 Input Types & Direction

### Input Type المناسب

| البيانات | النوع | ملاحظة |
|---------|-------|--------|
| نص عام | `type="text"` | الافتراضي |
| بريد إلكتروني | `type="email"` | keyboard مناسب على mobile |
| كلمة مرور | `type="password"` | انظر INP-11 |
| رقم هاتف | `type="tel"` | لا validation تلقائي — انظر INP-13 |
| رابط URL | `type="url"` | انظر INP-13 |
| رقم | `type="number"` | احتياط: سلوك iOS يختلف |
| بحث | `type="search"` | |

### اتجاه النص (dir)

- **العربي:** `dir="rtl"` (افتراضي الصفحة) — لا تحتاج تحديداً إضافياً
- **Latin / أرقام:** `dir="ltr"` على الحقل نفسه للأرقام والروابط والبريد الإلكتروني

```html
<!-- بريد إلكتروني: LTR + spellcheck=false (إلزامي — انظر INP-09A) -->
<input type="email" dir="ltr" autocomplete="email" spellcheck="false" placeholder="example@domain.com" />

<!-- هاتف: LTR -->
<input type="tel" dir="ltr" placeholder="+962799..." />

<!-- URL: LTR -->
<input type="url" dir="ltr" placeholder="https://..." />

<!-- اسم عربي: RTL (الافتراضي) -->
<input type="text" placeholder="أحمد محمد" />
```

---

## INP-09A Email Field Mandatory Attributes Contract

### الـ Attributes الإلزامية لكل Email Input

```html
<input
  type="email"
  dir="ltr"
  autocomplete="email"
  spellcheck="false"
  placeholder="example@domain.com"
/>
```

| الـ Attribute | القيمة | السبب |
|--------------|--------|-------|
| `type="email"` | إلزامي | keyboard مناسب على mobile |
| `dir="ltr"` | إلزامي | البريد دائماً LTR |
| `autocomplete="email"` | إلزامي | يُحسِّن UX ويسهِّل autofill |
| `spellcheck="false"` | **إلزامي** | يمنع Android Chrome/Gboard من الدخول في IME composition mode |

### لماذا `spellcheck="false"` إلزامي لـ Email

على Android Chrome + Gboard، عند غياب `spellcheck="false"`:

1. المتصفح يُطبِّق spellcheck على الـ **local-part** (النص قبل `@`) — لأنه يبدو كلمة لغوية
2. الـ local-part يدخل في **IME composition mode** — طبقة OS/IME بدلاً من CSS layer
3. `-webkit-text-fill-color:#fff` (من INP-10A) يعمل على CSS layer فقط — لا يُغطي IME composition rendering
4. النتيجة: local-part يظهر **أسود** مع **خط تدقيق إملائي أحمر**، بينما `@domain.com` يبقى أبيض

`spellcheck="false"` يمنع المتصفح من الدخول في composition/spellcheck mode كلياً — يُبقي النص تحت CSS rendering حيث `color` و `-webkit-text-fill-color` يعملان بشكل صحيح.

### الممنوعات الدائمة

```
❌ Email input بدون spellcheck="false"
❌ محاولة إصلاح هذه المشكلة بـ CSS وحده — IME composition layer لا يخضع لـ CSS
❌ إضافة autocorrect="off" كبديل — غير قياسي على Android، لا يُغني عن spellcheck="false"
```

---

## INP-10 Autofill & Autocomplete

### `autocomplete` attribute

يُحدَّد دائماً على الحقول المعروفة — يساعد المستخدم ويحسِّن UX:

```html
<input type="text"  autocomplete="name" />
<input type="email" autocomplete="email" />
<input type="tel"   autocomplete="tel" />
<input type="password" autocomplete="current-password" />
<!-- كلمة مرور جديدة: -->
<input type="password" autocomplete="new-password" />
```

### ممنوعات Autofill

- ممنوع `autocomplete="off"` على حقول اعتيادية لتعطيل الـ autofill — يضرّ بـ UX
- مقبول فقط لحقول OTP أو حقول تقنية لا يجب أن يُخزِّنها المتصفح

---

## INP-10A Input Value Text Color Stability Contract

### المشكلة

على Android Chrome (وبعض إصدارات Chromium/WebKit)، الـ UA stylesheet يُطبِّق `-webkit-text-fill-color` على الـ input المُوجَّه أو المُملَّء من المتصفح. هذه القيمة **تتغلب على `color`** لأن `-webkit-text-fill-color` ذو أولوية أعلى في Chromium. النتيجة: نص الـ input يظهر بلون مختلف عن الثيم عند Focus أو Autofill.

### Contract الرسمي

**قيمة الـ Input المكتوبة من المستخدم يجب أن تحافظ على لون النص المخصص للثيم في جميع الحالات:**

| الحالة | السلوك المطلوب |
|--------|---------------|
| Normal | لون النص = لون الثيم |
| Focus | لون النص = لون الثيم — لا تغيير عند التحديد |
| Filled (قيمة مكتوبة + blur) | لون النص = لون الثيم |
| Autofill | لون النص = لون الثيم |
| Autofill + Focus | لون النص = لون الثيم |
| Password-manager / browser-filled | لون النص = لون الثيم |

### قواعد التطبيق CSS

```css
/* القاعدة الأساسية — تغطي Normal + Focus + Filled */
.field input,
.field select {
  color: #fff;                    /* للمتصفحات غير WebKit */
  -webkit-text-fill-color: #fff;  /* يمنع Chromium UA من تغيير لون النص عند Focus */
  caret-color: #fff;              /* الـ cursor يبقى مرئياً على خلفية داكنة */
}

/* Autofill: تحتاج !important لأن browser-injected autofill styling ذو specificity أعلى */
.field input:-webkit-autofill,
.field input:-webkit-autofill:hover,
.field input:-webkit-autofill:focus {
  -webkit-text-fill-color: #fff !important;
  caret-color: #fff;
}
```

### لماذا `-webkit-text-fill-color` ليس `color` وحده

- `color` يُعيَّن في الـ Author stylesheet لكن Chromium قد يُطبِّق UA override بـ `-webkit-text-fill-color`
- `-webkit-text-fill-color` في Author stylesheet يأخذ أولوية فوق UA override بدون `!important`
- Autofill rules تستخدم `!important` لأن الـ browser-injected autofill styling يأتي بـ specificity مرتفعة

### ما لا يُغيِّره هذا الـ Contract

```
✅ قيمة النص المكتوبة (value text)    → ثابتة على لون الثيم في كل الحالات
✅ Caret (مؤشر الكتابة)               → لون الثيم (لا يختفي على خلفية داكنة)

❌ Placeholder text                    → له Contract منفصل — انظر INP-10B أدناه
❌ Label text                          → خارج نطاق هذا الـ Contract
❌ Field error message                 → DS-VAL يتحكم فيه
❌ Border color                        → INP-05 يتحكم فيه
❌ Selection highlight / text-select   → لم يُثبَت أنه سبب المشكلة — خارج النطاق
```

---

## INP-10B Placeholder Text Color Separation Contract

### المشكلة (Regression من INP-10A)

عند تعريف `-webkit-text-fill-color` على `.field input` لحماية لون القيمة (INP-10A)، تَرِث هذه الخاصية تلقائياً إلى `::placeholder` في Chromium/WebKit. والنتيجة: placeholder يظهر بـ `#fff` (أبيض كامل) بدلاً من اللون الخافت المعتمد — حتى لو كانت `color` على `::placeholder` صحيحة.

**السبب التقني:** `-webkit-text-fill-color` خاصية موروثة (inherited). `::placeholder` يرث القيمة من `input` الأب عند غياب تعريف صريح على `::placeholder` نفسه.

### قاعدة الفصل الإلزامية

**Value Text و Placeholder Text قناتان بصريتان منفصلتان ومستقلتان.**

| القناة | الحالة | الخاصية المعتمدة | القيمة |
|--------|--------|------------------|--------|
| Value Text (normal/focus/filled) | `-webkit-text-fill-color` | `#fff` |
| Value Text (autofill) | `-webkit-text-fill-color !important` | `#fff` |
| **Placeholder Text** | **`-webkit-text-fill-color` صريح على `::placeholder`** | **`rgba(255,255,255,.28)`** |

### قاعدة التطبيق CSS

```css
/* قاعدة Placeholder — تعريف صريح يمنع inheritance من الـ input الأب */
.field input::placeholder {
  color: rgba(255,255,255,.28);
  -webkit-text-fill-color: rgba(255,255,255,.28);  /* يُلغي الـ inherited value من .field input */
}
```

### Contract الرسمي للـ Placeholder

| الحالة | المطلوب |
|--------|---------|
| Normal (حقل فارغ) | placeholder خافت `rgba(255,255,255,.28)` |
| Focus (حقل فارغ مُحدَّد) | placeholder خافت — لا يصبح أبيض |
| Blur (بعد التحديد) | placeholder خافت — يبقى كما هو |
| بعد مسح القيمة | placeholder يرجع خافت |

### الممنوعات الدائمة

```
❌ -webkit-text-fill-color: #fff على ::placeholder
❌ ترك ::placeholder بدون -webkit-text-fill-color صريح عند وجود -webkit-text-fill-color على الـ input الأب
❌ استخدام !important على ::placeholder — لا يلزم إذا كان التعريف صريحاً
❌ تغيير قيمة لون الـ placeholder عن rgba(255,255,255,.28)
```

### ملاحظة معمارية

هذا الـ Bug كشف Gap في INP-10A: عند تعريف `-webkit-text-fill-color` لحماية Value Text، يجب تعريفها أيضاً على `::placeholder` صراحةً في نفس الـ PR — الخاصيتان مرتبطتان inheritance-حتماً في Chromium/WebKit.

### Browser Notes

- **Desktop Chrome/Chromium:** `color:#fff` قد يكفي في بعض الإصدارات، لكن `-webkit-text-fill-color` ضروري للاتساق
- **Android Chrome:** UA stylesheet يُطبِّق `-webkit-text-fill-color` عند Focus → يجب تعريفه صراحةً
- **Safari/iOS:** نفس سلوك WebKit — `-webkit-text-fill-color` مطلوب
- **Firefox:** لا يدعم `-webkit-text-fill-color` لكن يحترم `color` — القاعدة الحالية تعمل

### التحقق النهائي

الاختبار الآلي بـ Playwright Desktop **لا يُعيد إنتاج** Android Chrome UA behavior. التحقق البصري النهائي يتطلب:

```
المسار التدريجي:
  1. Email filled (ليس focused) → النص أبيض ✓
  2. Click/focus الحقل → النص يبقى أبيض ✓
  3. Blur الحقل → النص يبقى أبيض ✓
  4. Browser autofill → النص أبيض ✓
  5. Password manager fill + focus → النص أبيض ✓
```

يُختبَر يدوياً على Android Chrome بعد deployment.

---

## INP-11 Password Field Visual Contract

### العناصر الإلزامية

1. `<input type="password">` — مخفية افتراضياً
2. زر Show/Hide Password (أيقونة عين) داخل الحقل (suffix)
3. يتبدَّل `type="password"` ↔ `type="text"` عند الضغط
4. `aria-label` على زر العين: `"إظهار كلمة المرور"` / `"إخفاء كلمة المرور"`

### Password Strength (اختياري في V1)

- يُضاف في نماذج التسجيل وتغيير كلمة المرور
- يُعرَض كـ progress bar أسفل الحقل بعد اتجاه الكتابة
- لا يُعرَض في نموذج تسجيل الدخول

### ما هو **خارج** نطاق INP-11

- Validation المحتوى (الطول، التعقيد) → DS-VAL
- إرسال البيانات → DS-FRM + API-MUT

---

## INP-12 Accessibility & RTL

### ARIA إلزامي

```html
<!-- ربط الـ label بالحقل -->
<label for="field-id">...</label>
<input id="field-id" aria-describedby="field-id-error field-id-hint" />

<!-- رسالة الخطأ -->
<span id="field-id-error" class="field-error" role="alert" aria-live="polite"></span>

<!-- نص مساعد -->
<span id="field-id-hint" class="field-hint"></span>
```

### قواعد ARIA

- `aria-required="true"` على الحقول الإجبارية
- `aria-invalid="true"` عند وجود خطأ — يُضاف بـ JS عند إضافة `.has-error`
- `aria-invalid="false"` أو إزالته عند تصحيح الخطأ
- `role="alert"` + `aria-live="polite"` على `.field-error`
- لا `aria-label` كبديل كامل عن `<label>` المرئية

### RTL

- الصفحة كاملها `dir="rtl"` — لا تحتاج إعادة تعريف per-field إلا للـ LTR fields (INP-09)
- الـ Counter يُعرَض أسفل اليسار (بسبب RTL)
- أيقونة العين في حقل Password: inline-end (يسار في RTL = يمين في LTR)

---

## INP-13 Password / Email / URL / Tel Boundaries

هذا القسم يُحدِّد ما يملكه `DS-INP` وما يُفوَّض لأنظمة أخرى:

| الجانب | المالك |
|--------|--------|
| الشكل البصري للحقل | DS-INP (هذا النظام) |
| `type` attribute | DS-INP |
| `dir` attribute | DS-INP |
| `autocomplete` attribute | DS-INP |
| زر Show/Hide كلمة المرور | DS-INP (INP-11) |
| متى تظهر رسالة خطأ Format | DS-VAL (VAL-05) |
| ما محتوى رسالة الخطأ | DS-VAL (VAL-08 + VAL-17) |
| التحقق من صحة الـ email فعلياً | DS-VAL → Backend (VAL-03) |
| إرسال كلمة المرور | DS-FRM → API-MUT |

**ممنوع في DS-INP:** تضمين منطق validation (regex، طول، نمط) — ذلك من DS-VAL.

---

## INP-14 Forbidden Patterns

```
❌ حقل بدون <label> مرئية (aria-label وحده لا يكفي)
❌ placeholder بدون label
❌ placeholder يكرِّر الـ label حرفياً
❌ حد أخضر دائم بعد "قيمة صحيحة" (Valid state) — تسبب ضوضاء بصرية
❌ إظهار .field-error قبل أن يُغادر المستخدم الحقل (blur) أو يضغط Submit — راجع DS-VAL
❌ حقل email/tel/url بـ dir="rtl" — يجب LTR
❌ autocomplete="off" على حقول اعتيادية
❌ CSS validation-state مباشر في DS-INP (مثل: border-color: red عند input كذا) — DS-VAL هو من يُعلِّق .has-error
❌ type="number" لأرقام الهاتف — استخدم type="tel"
❌ إنشاء tw-input.css قبل أن يُطلب صراحةً
❌ منطق validation (regex، طول) داخل مكوِّن Input — يذهب إلى DS-VAL
```

---

## INP-15 Current Inventory & Migration Notes

### الحالة الراهنة (V1)

CSS الحقول موزَّع عبر ملفات متعددة:
- `static/company/company.css` — حقول edit modal الشركة
- `static/profile-v2.css` — حقول edit modal البروفايل
- `static/home/home-v2.css` — حقول home page

لا يوجد global token موحَّد لـ border، focus، error color على مستوى المنصة بعد.

### خطة V2 (مؤجَّلة)

- `static/shared/tw-ui-tokens.css` (موثَّقة في FUTURE_ROADMAP.md)
- توحيد Input tokens عبر هذا الملف
- لا يُنشأ حتى يُطلب صراحةً

### التطابق مع هذا التوثيق

التوثيق الحالي (INP-00 → INP-16) يصف **الـ contract المستهدَف** — التنفيذ الحالي يتطابق جزئياً. الثغرات لا تستوجب migration فورية — توثيقها هنا للإشارة فقط.

---

## INP-16 Out of Scope V1

الأنظمة التالية **خارج** نطاق هذا التوثيق:

| العنصر | النظام المسؤول | الحالة |
|--------|---------------|--------|
| `<select>` والقوائم المنسدلة | `[DS-SEL]` — `static/shared/tw-select.js` | موجود — غير موثَّق في DESIGN_SYSTEM |
| Skills / Tags autocomplete | `static/shared/tw-skills.js` | موجود |
| File upload | `static/shared/tw-upload.js` | موجود |
| Image crop | `static/shared/tw-image-cropper.js` | موجود |
| Datepicker / Date range | `[DS-DATE]` — لم يُوثَّق | **ممنوع البناء قبل توثيق DS-DATE** |
| Phone input / Dial code picker | `[DS-PHONE]` — لم يُوثَّق | **ممنوع البناء قبل توثيق DS-PHONE** |
| Multi-select / Tags input | `[DS-SEL]` — لم يُوثَّق كاملاً | **ممنوع البناء قبل توثيق** |
| OTP / Pin input | `[DS-OTP]` — لم يُوثَّق | **ممنوع البناء قبل توثيق** |
| Radio / Checkbox / Toggle | `[DS-INP V2]` — مؤجَّل | **ممنوع البناء قبل توثيق** |
| Slider / Range | `[DS-INP V2]` — مؤجَّل | **ممنوع البناء قبل توثيق** |
| Rich text / WYSIWYG | `[DS-RICH]` — لم يُخطَّط | **ممنوع في V1** |
| Auto-resize / Auto-grow Textarea | `[DS-INP V2]` — مؤجَّل | **ممنوع البناء قبل توثيق** |
| Upload Input UI (drag & drop) | `[DS-UPLOAD]` — لم يُوثَّق كـ DS | راجع `tw-upload.js` للـ HTTP upload |
| Overlay / Modal لعرض Input معقد | `[DS-OVL]` — لم يُوثَّق | **ممنوع البناء قبل توثيق DS-OVL** |
| Reference Data Picker | `[DS-REF]` — `tw-options-data.js` موجود | غير موثَّق كـ DS كامل |
| Feedback / Toast من نتيجة Input | `[DS-FEEDBACK]` Feedback / Toast System — غير موثَّق بعد | **STOP — ممنوع البناء قبل توثيق DS-FEEDBACK (F30)** |

> **قاعدة الأنظمة المستقبلية:** لا يُبنى على أي نظام في هذا الجدول لم يُوثَّق في PR مستقل.
> إذا احتاجت المهمة أحد هذه الأنظمة — **STOP** واسأل صاحب المشروع (F30).
---

*[DS-INP] V1 — أُنشئ في PR docs/design-system-forms-v1 — 2026-07-21*
*يُكمله: [DS-FRM] FORM-LIFECYCLE.md · [DS-VAL] VALIDATION-ERRORS.md · [API-MUT] API-MUTATIONS-ERRORS.md*
