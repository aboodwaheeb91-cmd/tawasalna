# [DS-BTN] Button System V1 — Tawasolna

> **نظام الأزرار الرسمي لمنصة تواصلنا.**
> هذا الملف هو مرجع الـ contract المعماري للأزرار — web أولاً، مع مراعاة Flutter مستقبلاً (F1).
> لا يحتوي هذا الملف على كود CSS جاهز — التنفيذ يتبع Contract.

---

## [BTN-00] Button System Routing Contract

| إذا كنت تعمل على... | ابدأ من |
|---------------------|---------|
| زر حفظ / إلغاء تعديل | [BTN-09] Action Save Button Lifecycle |
| زر toggle (حفظ منشور، متابعة) | [BTN-10] Toggle Save Button Lifecycle |
| زر navigation أو tab | [BTN-12] Navigation Element Semantics |
| زر حذف / إجراء مدمِّر | [BTN-13] Dangerous Actions |
| أي زر جديد | [BTN-02] → [BTN-03] → [BTN-04] |
| استثناء خارج الـ contract | [BTN-15] Custom Button Exception |

---

## [BTN-01] No Matching System Contract

> قبل إنشاء أي زر جديد — تحقق من هذا القسم أولاً.

**الأنظمة الموجودة حالياً:** لا يوجد shared button component أو CSS class موحَّد بعد.
كل صفحة تعرِّف أزرارها داخل ملف CSS الخاص بها.

**النتيجة المطلوبة:**
- لا تنسخ styles من صفحة لأخرى.
- استخدم نفس الـ contract الموثَّق هنا في كل صفحة جديدة.
- عند إنشاء `tw-ui-tokens.css` مستقبلاً — ستُحوَّل هذه الـ contracts إلى shared classes.

---

## [BTN-02] Base Button Visual Contract

### الخصائص الأساسية (مطلوبة في كل زر)

| خاصية | القيمة المطلوبة | السبب |
|--------|----------------|--------|
| `cursor` | `pointer` | UX — لا يُترك للمتصفح |
| `user-select` | `none` | BTN-08 — لا يُحدَّد نص الزر |
| `border` | explicit (لا `border: none` ضمني) | يمنع تضارب الـ reset |
| `border-radius` | consistent per page | تحديد في كل صفحة بشكل صريح |
| `font-family` | `inherit` أو `'Cairo', sans-serif` | يحافظ على الـ RTL font |
| `direction` | يرث من `<html dir="rtl">` | لا تحتاج تحديد صريح عادةً |
| `transition` | `opacity`, `background-color`, `transform` | لا تضيف transition غير ضرورية |

### ما لا يجوز في أي زر

```
❌ outline: none   بدون بديل focus visible
❌ pointer-events: none إلا في حالة disabled الموثَّقة
❌ تعديل z-index داخل الزر نفسه
```

---

## [BTN-03] Semantic Button Types

أربعة أنواع دلالية — كل نوع له لون ثابت من design tokens المنصة:

| النوع | الاسم | اللون | الاستخدام |
|-------|-------|-------|-----------|
| **Primary** | زر رئيسي | `#00c896` (--ac) | الإجراء الرئيسي الوحيد في الصفحة/المودال |
| **Secondary** | زر ثانوي | `rgba(255,255,255,.08)` | إلغاء، رجوع، إجراءات ثانوية |
| **Danger** | زر خطر | `#ef4444` | حذف، إزالة، إجراءات لا رجعة فيها |
| **Success** | زر نجاح | `#22c55e` | تأكيد ناجح (نادراً — بعد backend confirmation) |

### قواعد الاستخدام

1. **Primary واحد فقط** في كل سياق (مودال، section، صفحة). لا يوجد اثنان Primary في نفس المكان.
2. **Danger لا يُستخدم إلا للإجراءات المدمِّرة** — راجع [BTN-13].
3. **Success لا يظهر ابتداءً** — يظهر فقط كحالة تأكيد بعد backend response ناجح.
4. اللون يُحدَّد على `background-color` — لا تستخدم `background` shorthand إذا أردت دعم transparency.

---

## [BTN-04] Button Size & Layout Contract

### الأحجام المستخدمة (reference — ليست global classes بعد)

| الحجم | height | padding horizontal | font-size | استخدام |
|-------|--------|--------------------|-----------|---------|
| SM | 27px | 18px | 11px | Profile V2 action buttons (مجمَّدة — CLAUDE.md) |
| MD | 36px | 20px | 13px | مودالات، forms |
| LG | 44px | 28px | 15px | CTA رئيسية في الصفحة |

> **ملاحظة:** القيم SM مجمَّدة في `.sc-btn` — راجع CLAUDE.md قسم "Profile V2 Action Buttons Rule".
> لا تعدِّل هذه القيم إلا بـ PR مخصص.

### Layout داخل الزر

- `display: inline-flex`
- `align-items: center`
- `justify-content: center`
- `gap`: المسافة بين أيقونة ونص — ثابتة per size (5px لـ SM، 6px لـ MD، 8px لـ LG)
- `flex-shrink: 0` — الزر لا يتقلص داخل flex container

---

## [BTN-05] Button Groups

عند وجود مجموعة أزرار في سياق واحد:

1. استخدم `display: flex` + `gap` على container — لا `margin` على الأزرار أنفسها.
2. RTL الترتيب: **الزر الأبرز (Primary/Danger) على اليسار** في RTL flex-row (يظهر على اليمين بصرياً).
3. لا تختلط secondary وdanger في نفس المجموعة إلا إذا كان هناك سبب UX واضح.
4. في المودالات: Primary يأتي أولاً في DOM (يظهر يميناً في RTL)، Secondary يأتي ثانياً.

```html
<!-- مثال RTL صحيح — DOM order يعكس أهمية الإجراء -->
<div class="modal-actions">
  <button class="btn-primary">حفظ</button>    <!-- يظهر يميناً -->
  <button class="btn-secondary">إلغاء</button> <!-- يظهر يساراً -->
</div>
```

---

## [BTN-06] Icon Buttons

### أزرار بأيقونة فقط (no text)

- يجب أن يحتوي على `aria-label` بالعربية يصف الإجراء.
- الأيقونة: SVG inline فقط — لا font-icon، لا emoji.
- حجم الأيقونة: `14×14px` (SM context)، `16×16px` (MD)، `18×18px` (LG).
- `stroke-width`: `1.8` (SM)، `2` (MD/LG).
- `flex-shrink: 0` على الـ SVG داخل الزر.

### أزرار بأيقونة + نص

- الأيقونة تأتي قبل النص في DOM (تظهر يميناً في RTL).
- `gap` بينهما: راجع [BTN-04].

---

## [BTN-07] Button Interaction States

كل زر يجب أن يعرِّف الحالات التالية بشكل صريح:

| الحالة | المطلوب |
|--------|---------|
| `default` | base styles من [BTN-02] |
| `hover` | تغيير `opacity` أو `background-color` — لا transform مبالغ فيه |
| `active` (mousedown) | `transform: scale(0.97)` أو تأثير مماثل — اختياري لكن موحَّد |
| `focus-visible` | حد مرئي (`outline: 2px solid var(--ac)`) — إلزامي للـ accessibility |
| `disabled` | `opacity: 0.45`، `cursor: not-allowed`، `pointer-events: none` |
| `loading` | راجع [BTN-09] |

### ما هو ممنوع

```
❌ :focus { outline: none } بدون :focus-visible بديل
❌ حالة hover تغير layout (width, height, padding)
❌ حالة disabled تغير اللون إلى أحمر (لا يوجد error state على disabled)
```

---

## [BTN-08] No Text Selection Contract

```css
/* مطلوب على كل زر */
user-select: none;
-webkit-user-select: none;
```

المستخدم لا يحدِّد نص الزر. هذا ليس اختيارياً.

لا تطبِّقه على النص المجاور للزر — فقط على `<button>` نفسه.

---

## [BTN-09] Action Save Button Lifecycle

> زر "حفظ" يُرسل بيانات إلى backend ثم يُغلق مودال أو يُحدِّث UI.

### دورة حياة الزر

```
Default
  ↓ [user clicks]
Loading  (spinner + disabled + نص "جارٍ الحفظ...")
  ↓ [fetch resolves]
  ├─ Success → UI updates + modal closes (لا تغيير لوني دائم على الزر)
  └─ Error   → Default (مع toast يوضح الخطأ)
```

### قواعد إلزامية

1. **تعطيل الزر فوراً** عند click — `btn.disabled = true` — قبل الـ fetch.
2. **نص Loading** يجب أن يكون وصفياً: `"جارٍ الحفظ..."` لا `"..."` فقط.
3. **لا تغيير لوني دائم** على الزر بعد النجاح — التأكيد يكون بإغلاق المودال أو toast.
4. **على الخطأ:** أعِد الزر لحالة Default + أظهر toast يصف الخطأ — لا تُخفِ الزر.
5. **لا تستخدم `setTimeout` لمحاكاة Loading** — Loading حقيقي فقط، مرتبط بـ fetch promise.

```javascript
// النمط الإلزامي
async function handleSave(btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = 'جارٍ الحفظ...';
  try {
    await fetch(...);
    // نجاح: أغلق المودال أو حدِّث UI
  } catch (e) {
    btn.disabled = false;
    btn.textContent = orig;
    showToast('حدث خطأ، حاول مجدداً');
  }
}
```

---

## [BTN-10] Toggle Save Button Lifecycle

> زر يحمل حالة ثنائية: محفوظ / غير محفوظ (bookmark, follow, appreciation).

### دورة حياة الزر

```
State A (inactive)
  ↓ [user clicks]
Optimistic UI → switch to State B immediately
  ↓ [fetch in background]
  ├─ Success → keep State B
  └─ Error   → rollback to State A + toast
```

### قواعد إلزامية

1. **Optimistic UI إلزامي** — اعكس الحالة فوراً لا بعد response.
2. **Desired State Queue إلزامي** — راجع Post Appreciation / Post Save rules في CLAUDE.md.
   - متغيرات: `_desired[id]`, `_inFlight[id]`, `_origState[id]`
3. **لا تستخدم `disabled` أثناء في الـ flight** — الزر يبقى قابلاً للنقر (قد يُعيد الضغط).
4. **الحالتان لهما visual contract ثابت** — راجع "Post Save System Rules" في CLAUDE.md:
   - `active=true`: أيقونة مملوءة + لون accent
   - `active=false`: أيقونة outline + لون محايد

---

## [BTN-11] Button Lifecycle Contract

> الـ contract الشامل لكل زر — مجموع [BTN-09] و[BTN-10].

**كل زر في المنصة يجب أن يحدِّد:**

| العنصر | المطلوب |
|--------|---------|
| نوعه الدلالي | Primary / Secondary / Danger / Success |
| حجمه | SM / MD / LG |
| حالاته | Default, Hover, Focus, Disabled, Loading (إن وُجد) |
| سلوك النقر | Action (BTN-09) / Toggle (BTN-10) / Navigation (BTN-12) |
| backend confirmation | كيف تُعكَس النتيجة على الـ UI |

**ممنوع:**

```
❌ زر بدون تعريف حالة disabled
❌ زر Loading بدون تعطيل النقر
❌ زر يُخفي نفسه بدلاً من showing error state
❌ زر يغيّر لونه بشكل دائم بعد نجاح الحفظ (إلا إذا كان toggle)
```

---

## [BTN-12] Navigation Element Semantics

> Tab bars، bottom nav، sidebar links، breadcrumbs.

### قواعد

1. **استخدم `<a>` لا `<button>`** عندما الإجراء هو navigation (تغيير URL أو page route).
2. **استخدم `<button>`** عندما الإجراء هو سلوك داخل الصفحة (toggle panel، فتح مودال).
3. **لا تخلط الاثنين** — `<a>` مع `onclick` يغير state داخلي = خطأ معماري.
4. **Tab المحدد:** `aria-current="page"` على الـ `<a>` النشط.
5. **Bottom nav active state:** class `active` على container + visual indicator (dot أو underline) — لا تعتمد على اللون وحده.

---

## [BTN-13] Dangerous Actions

> حذف، إزالة، reset، إجراء لا رجعة فيه.

### Pattern الإلزامي

1. **الزر نفسه:** Danger type (أحمر `#ef4444`) — لا يُخفَى، لا يُعطَّل ابتداءً.
2. **عند النقر:** مودال تأكيد يصف الإجراء بوضوح ("هل تريد حذف الوظيفة؟ لا يمكن التراجع.").
3. **داخل مودال التأكيد:**
   - زر Danger للتأكيد النهائي.
   - زر Secondary للإلغاء — يُغلق المودال فقط.
4. **لا تستخدم `confirm()` المدمج في المتصفح** — يخالف تصميم المنصة.
5. **بعد التنفيذ:** toast يؤكد الإجراء + redirect أو UI update فوري.

```
❌ حذف مباشر بدون تأكيد
❌ زر الحذف باللون الأخضر (Primary)
❌ مودال تأكيد بزرَّين Primary
```

---

## [BTN-14] Performance Contract

1. **لا تُنشئ event listener على الزر في كل render** — استخدم delegation أو أنشئ الزر مرة واحدة.
2. **لا `innerHTML = '...<button>...'` داخل loop** لأزرار كثيرة — استخدم `createElement`.
3. **لا fetch داخل mouseenter/mouseover** — الـ prefetch يكون بطريقة أخرى.
4. **الزر لا يقرأ من DOM لاسترجاع state** — الـ state يُحفظ في متغير JS، لا في الـ DOM.

---

## [BTN-15] Custom Button Exception

> عندما يكون الزر المطلوب خارج هذا الـ contract.

**الإجراء المطلوب قبل البناء:**

1. وثِّق سبب الاستثناء في PR description.
2. أضف تعليقاً في الكود يشير إلى هذا الـ section.
3. لا تعمِّم الاستثناء — يبقى محدوداً في الموقع الذي يحتاجه.

**أمثلة مقبولة:**

- زر chip في محتوى ديناميكي (job chip popover) — له سلوك خاص بسياقه.
- زر داخل SVG أو canvas — قواعد HTML لا تنطبق.

**أمثلة غير مقبولة:**

- "أريد لوناً مختلفاً" — استخدم [BTN-03].
- "المودال هذا خاص" — المودالات تتبع نفس الـ contract.

---

## [BTN-16] Forbidden Patterns

قائمة شاملة بما هو ممنوع في أي زر في المنصة:

```
❌ <div> أو <span> كزر بدون role="button" و tabindex="0"
❌ <a> بـ href="#" كزر — استخدم <button>
❌ <button type="submit"> خارج <form> حقيقي
❌ onclick="location.href='...'" — استخدم <a href>
❌ outline: none بدون :focus-visible بديل
❌ تحديد نص الزر (user-select: text على button)
❌ Loading state بـ setTimeout وهمي
❌ حذف مباشر بدون confirmation modal
❌ Primary button أحمر اللون
❌ Danger button أخضر اللون
❌ استنساخ style من صفحة أخرى بدون مراجعة هذا الملف
❌ زر بدون حالة disabled موثَّقة
❌ إخفاء الزر بدلاً من تعطيله في حالة Loading
❌ تغيير width/height عند hover
❌ <button> داخل <button>
```

---

*آخر تحديث: 2026-07-18 — Button System V1 (foundation documentation only — no CSS implementation)*
