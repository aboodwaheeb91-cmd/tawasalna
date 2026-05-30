# تواصلنا — Project Architecture Doctrine

> هذا الملف هو المرجع المعماري الرسمي للمشروع.
> أي تطوير جديد يجب أن يلتزم بهذه القواعد.

---

## 1. API = المصدر النهائي للصلاحيات

```python
# كل endpoint يتحقق من الصلاحية server-side
if str(token.get('user_id')) != str(resource_owner_id):
    raise HTTPException(403, "Unauthorized")
```

- UI checks هي UX فقط، ليست حماية.
- لا تعتمد على frontend لمنع عمليات غير مصرح بها.
- أي mutation (POST/PUT/DELETE) يتحقق من token ownership.

---

## 2. View Mode — ثلاث حالات واضحة

```javascript
// تُحدد مرة واحدة عند page init
const viewMode = isOwner ? 'owner' : _sessionUser ? 'public-user' : 'guest';
```

| Mode | من | CSS class | يرى |
|------|-----|-----------|-----|
| `owner` | صاحب البروفايل | — | App Shell + أدوات الإدارة كاملة |
| `public-user` | مستخدم مسجّل يشوف غيره | `public-view` | Public Header + محتوى البروفايل |
| `guest` | زائر غير مسجّل | `public-view` | Public Header + محتوى + CTA login |

---

## 3. CSS = عرض فقط

```css
/* صح */
body.public-view .owner-only { display: none; }

/* غلط — CSS لا يحمي، يخفي فقط */
/* لا تعتمد عليه لحماية بيانات حساسة */
```

---

## 4. JavaScript = سلوك فقط

```javascript
// كل owner action يبدأ بـ guard
function saveProfile() {
    if (!isOwner) return;           // JS behavior guard
    if (!_sessionUser?.id) return;  // auth guard
    // ... rest of logic
}
```

- لا تضع business logic داخل CSS.
- لا تستخدم DOM manipulation لإخفاء بيانات حساسة.

---

## 5. صفحة واحدة + View Mode (لا نسخ)

```
✅ profile.html + viewMode switch
❌ profile.html + profile-public.html (نسختان)
```

- استخدم View Mode بدل صفحات منفصلة.
- استثناء: إذا الصفحتان مختلفتان جذرياً في البنية.

---

## 6. Unified Components (لا تكرار)

```javascript
// صح — component واحد مع isOwner
function renderSkillItem(item, lid) {
    const controls = isOwner ? `
        <div class="item-menu-wrap">...</div>
    ` : '';
    return `<div class="item">${content}${controls}</div>`;
}

// غلط — نسختان
function renderSkillItem_owner(item) { ... }
function renderSkillItem_public(item) { ... }
```

---

## 7. قواعد الإضافات المستقبلية

### Feature جديدة خاصة بالـ owner:
1. HTML: `class="owner-only"` على العنصر
2. CSS: `body.public-view .my-widget { display:none }`
3. JS: `if(!isOwner) return;` في بداية الـ handler
4. API: ownership check في الـ endpoint

### Component جديد:
1. مكوّن واحد يقبل `isOwner` أو يقرأ `window.isOwner`
2. يُخرج HTML مختلف بناءً على الـ mode
3. لا نسخ منفصلة

### Migration للكود القديم:
- اكتشفت عنصراً يظهر في public-view بشكل خاطئ؟
  → `body.public-view #elementId { display:none }` + `if(!isOwner) return;`
- لا تعيد بناء الصفحة، فقط أضف الـ guard.

---

## Schema Drift Prevention

```python
# كل column تستخدمه في SELECT يجب أن يكون في _migrations list
_migrations = [
    "ALTER TABLE experience ADD COLUMN IF NOT EXISTS company TEXT",
    # ... أضف هنا أي column جديد قبل استخدامه
]
```

- لا تضيف column في الكود بدون migration مقابل.
- `_safe_query` تفرق بين EMPTY RESULT و QUERY FAILURE.
- أي `[SCHEMA_ERROR]` في الـ logs = migration ناقصة.

---

## ملخص: ماذا يفعل كل طرف

```
CSS   → متى يظهر العنصر (display/visibility)
JS    → ماذا يفعل العنصر (behavior/logic)
API   → هل مسموح بالعملية (authorization)
```

---

## 8. Single Source of State

```javascript
// ✅ State comes from Backend response only
const isOwner = profile.user_id === token.user_id;  // server-verified

// ❌ Never derive state from DOM, URL, or localStorage alone
const isOwner = window.location.href.includes(userId);  // wrong
const isOwner = localStorage.getItem('isOwner');         // wrong
```

**القاعدة:**
- `isOwner`, `_sessionUser`, `viewMode` تُحدَّد من Backend response فقط.
- `localStorage` مرآة للـ state فقط — ليست مصدره.
- URL params و DOM state هي hints، ليست source of truth.

**التطبيق الحالي:**
```javascript
// profile.html — Step 2
const prof = data.profile;
const isOwner = String(_urlId) === String(prof.tw_id) && !!_sessionUser;
// _sessionUser مأخوذ من JWT token verify في الـ backend
```

---

## 9. Rendering Order Rule

ترتيب التنفيذ ثابت ولا يتغير:

```
1. viewMode detection   → من Backend response
2. global flags         → isOwner, _sessionUser, viewMode
3. layout render        → CSS class switch (public-view / owner)
4. event listeners      → bind بعد render فقط
5. async data fetch     → Step 2 يجلب البيانات
6. DOM update           → من API response فقط
```

**لماذا هذا الترتيب؟**
- Steps 1-3 sync → لا flicker
- Step 4 بعد render → لا event on non-existent elements
- Steps 5-6 async → لا blocking للـ UI

**anti-patterns:**
```javascript
// ❌ render قبل تحديد viewMode
renderLayout();
if(isOwner) { ... }  // too late

// ❌ event listener قبل DOM element
document.getElementById('btn').addEventListener(...);  // btn not yet rendered
document.body.classList.add('public-view');  // after listener — flicker!

// ✅ الترتيب الصحيح
document.body.classList.add('public-view');  // 3. layout
document.getElementById('btn').addEventListener(...);  // 4. listeners
fetch('/profile/full').then(render);  // 5-6. async
```

---

## 10. Bootstrap Idempotency

كل initialization يجب أن يكون **مرة واحدة فقط**:

```javascript
// ✅ Bootstrap guard — في بداية كل IIFE أو init function
window.__profileBooted = window.__profileBooted || false;
if (window.__profileBooted) {
    document.body.classList.remove('profile-loading');
    return;  // skip — already initialized
}
window.__profileBooted = true;
// ... rest of init
```

**القاعدة:**
- كل صفحة تملك `window.__[pageName]Booted` flag.
- أي إعادة تشغيل (SW update, back navigation, tab focus) يُمنع بهذا الـ guard.
- Guard يُعاد في حالة حقيقية واحدة فقط: تسجيل الخروج وإعادة الدخول (new window context).

**أمثلة:**
```javascript
// profile.html
window.__profileBooted = window.__profileBooted || false;
if (window.__profileBooted) return;
window.__profileBooted = true;

// home.html (مستقبلاً)
window.__homeBooted = window.__homeBooted || false;
if (window.__homeBooted) return;
window.__homeBooted = true;
```

---

## 11. Controlled Exceptions Rule

أي استثناء لقاعدة في هذا الملف مسموح **فقط** بالشروط الثلاثة معاً:

### الشروط

**1. موثّق في ARCHITECTURE.md**
الاستثناء يُسجَّل هنا بشكل صريح — لا استثناءات ضمنية أو غير مرئية.

**2. له سبب تقني واضح**
```
مقبول:   performance / UX / platform limitation / third-party constraint
غير مقبول: "أسرع في التطوير" / "مؤقت" / "سأصلحه لاحقاً"
```

**3. لا يتجاوز الـ security model**
الاستثناء لا يؤثر على:
- صلاحيات API
- state ownership
- authentication / authorization flow

---

### صيغة تسجيل الاستثناء

```markdown
**Exception [رقم]: [اسم مختصر]**
- القاعدة المستثناة: Rule #[رقم]
- السبب: [سبب تقني واضح]
- الحد: [ما يُسمح به بالضبط]
- التأثير على الأمان: لا يوجد / [وصف إن وجد]
- تاريخ الإضافة: [YYYY-MM-DD]
```

---

### استثناءات مسجّلة حالياً

**Exception 01: localStorage كـ session cache**
- القاعدة المستثناة: Rule #8 (Single Source of State)
- السبب: تجنب re-fetch عند كل page navigation — UX performance
- الحد: `localStorage` مرآة مؤقتة فقط، تُعاد بناؤها من API في كل Step 2
- التأثير على الأمان: لا يوجد — API يتحقق من JWT في كل request
- تاريخ الإضافة: 2025-05-25

**Exception 02: CSS يخفي owner elements (public-view)**
- القاعدة المستثناة: Rule #3 (CSS = عرض فقط)
- السبب: atomic reveal بدون flicker — لا JS delay في إخفاء عناصر الـ owner
- الحد: CSS للإخفاء البصري فقط، JS guard (`if(!isOwner) return`) مطلوب أيضاً لكل owner action
- التأثير على الأمان: لا يوجد — API هو المصدر النهائي للصلاحيات
- تاريخ الإضافة: 2025-05-25

---

### ما لا يُعدّ استثناءً مقبولاً

```
❌ "مؤقت" بدون تاريخ انتهاء
❌ bypass للـ API auth check
❌ قراءة state من DOM أو URL بدون verify
❌ double bootstrap بدون __booted guard
❌ استثناء غير مسجّل في هذا الملف
```
