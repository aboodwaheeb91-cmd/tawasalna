# Navigation System V1 — تواصلنا

> **[DS-NAV] — Architecture & Contract Documentation**
> **الحالة:** V1 Documentation ✅ · Implementation 🔜 (لا تنفيذ في هذا الـ PR)

---

## [NAV-00] Routing / Reading Protocol

> **قبل أي تعديل يمس Navigation أو URL أو تاريخ المتصفح أو Back Button:**
>
> 1. ابدأ من **Quick Routes** أدناه — حدِّد القسم المناسب لمهمتك.
> 2. اقرأ **ذلك القسم فقط** — لا تقرأ الملف كاملاً.
> 3. إذا لم يوجد Route مناسب → **NAV-01 → STOP** → اسأل صاحب المشروع.
> 4. تحقق من أن تعديلك لا يخالف قسم **Forbidden Patterns** في النهاية.
>
> هذا الملف **توثيق + contract معماري فقط** — لا implementation code هنا.

### Quick Routes

| المهمة | الأقسام |
|--------|---------|
| إضافة رابط / زر navigation | **NAV-02** + BTN-12 |
| إضافة modal / drawer / overlay | **NAV-04** + NAV-05 |
| سلوك زر Back (برمجي أو مدمج) | **NAV-05** + NAV-06 |
| صفحة تحتاج auth guard + redirect | **NAV-10** + NAV-07 |
| صفحة جديدة تعمل بـ Deep Link | **NAV-08** + NAV-02 |
| تمرير scroll بعد navigation | **NAV-09** |
| ربط Navigation بصلاحيات المستخدم | **NAV-11** + VIEWER-MODES.md |
| جهوزية Flutter / Mobile | **NAV-12** |
| نوع غير محدد | **NAV-01 → STOP** |

---

## [NAV-01] Scope & Boundaries

### ما يملكه نظام Navigation

- **Route & URL Contract** — الروابط الرسمية ومتطلباتها.
- **Layer Stack Contract** — LIFO stack للـ modals والـ overlays والـ drawers.
- **Unified Back Contract** — كيف يتصرف الرجوع بصرف النظر عن مصدره.
- **Safe Fallback System** — ما الصفحة التي يرجع إليها المستخدم حين لا يوجد context موثوق.
- **Return Destination (`?next=`)** — حفظ وجهة العودة بعد تسجيل الدخول فقط.
- **Deep Link Safety** — كل صفحة تعمل بشكل مستقل من URL مباشر.
- **Scroll Restoration** — متى يكون `auto` ومتى يكون `manual`.
- **Navigation State** — النموذج الهجين لحفظ حالة التنقل.

### ما لا يملكه نظام Navigation (مؤجَّل)

| الموضوع | السبب | متى؟ |
|---------|-------|-------|
| Modal / Drawer / Overlay System (تفاصيل) | نظام مستقل ينتظر PR منفصل | حين يُطلب |
| Client-side Router | لا يوجد ولا يُخطَّط له (F7) | ممنوع |
| Flutter Universal Links / App Links / Intent Filters | توثيق فقط الآن | مرحلة Flutter |
| WebSocket-driven Navigation | خارج النطاق | حين يُطلب |
| Notifications-driven Navigation | نظام الإشعارات موثَّق منفصلاً | §36 في SYSTEMS_INDEX |

### قيود المنصة (ثوابت)

- **MPA (Multi-Page App):** كل صفحة ملف HTML منفصل — لا client-side router.
- **لا بناء (F7):** لا bundler، لا transpiler، لا code splitting.
- **RTL Arabic:** جميع الصفحات `dir="rtl"`. اتجاه التنقل وإشارات الزر يجب أن يراعيا RTL.
- **Vanilla JS فقط:** لا React Router، لا Vue Router، لا History.js.

---

## [NAV-02] Route & URL Contract

### جدول الروابط الرسمية

| الرابط | الملف | الجمهور | نوع |
|--------|-------|---------|-----|
| `/` | landing.html | عام | صفحة عامة |
| `/login` | index.html | كل المستخدمين | Auth Gateway |
| `/home` | home-v2.html | emp | Feed |
| `/u/{tw_id}` | Smart Router → profile/company/edu | عام | Public Profile |
| `/company-profile` | redirect → `/u/{tw_id}` | co | Legacy Redirect فقط |
| `/edu-profile` | edu-profile.html | edu | Profile |
| `/job-detail?id=` | job-detail.html | كل المستخدمين | Single Job |
| `/messages` | messages.html | كل المستخدمين | Messaging |
| `/notifications` | notifications.html | كل المستخدمين | Notifications |
| `/settings` | settings.html | كل المستخدمين | Settings |
| `/tw-ctrl-{ADMIN_URL_TOKEN}` | admin.html | admin فقط | Admin Panel |

> **ملاحظة:** `/u/{tw_id}` هو الـ canonical URL الموحَّد لجميع أنواع الحسابات.
> انظر: `CLAUDE.md → Smart Public Profile Router Rules`.

### قواعد الـ URL

1. **`tw_id` فقط في الـ public URLs** — ممنوع استخدام الـ `id` الرقمي في روابط مشاركة.
2. **`?id=` هي query params للصفحات الداخلية فقط** (مثال: `/job-detail?id=123`).
3. **Hash routing (`#`) غير مستخدم** ومحجوز للـ anchor links فقط — ممنوع استخدامه كـ router.
4. **`?next=` محجوز لـ Auth Return Destination** (NAV-07) — ممنوع استخدامه لأغراض أخرى.
5. **الـ URL الجديد يجب أن يمثل حالة shareable** — ما يمكن مشاركته يجب أن يعمل كـ deep link مباشر.

### `<a>` مقابل Navigation برمجي

| الحالة | الأداة |
|--------|--------|
| رابط ثابت إلى صفحة أخرى | `<a href="/page">` — دائماً |
| زر يفتح modal / panel داخل الصفحة | `<button>` — لا navigation |
| redirect برمجي بعد action (post-login، post-save) | `window.location.href = '/page'` |
| فتح نافذة خارجية | `<a href="..." target="_blank" rel="noopener noreferrer">` |
| Back برمجي | `<button>` مع back-trust check قبل `history.back()` — انظر NAV-05 |

> انظر أيضاً: **BTN-12** في BUTTONS.md لقواعد دلالات عناصر التنقل.

---

## [NAV-03] Navigation State

### النموذج الهجين — Four Layers

لا يوجد State Manager مركزي. حالة التنقل موزَّعة على أربع طبقات لكل منها غرض محدد:

| الطبقة | ما تخزنه | المدة | مثال |
|--------|---------|-------|-------|
| **URL Params** | حالة قابلة للمشاركة والـ bookmark | طويلة — تبقى في المتصفح | `?id=123`, `?filter=jobs` |
| **`history.state`** | سياق الـ Back ephemeral | جلسة — تُفقد بعد إغلاق التاب | Layer Stack, scrollY, nav context |
| **`sessionStorage`** | حالة الجلسة غير المشاركة | Tab session فقط | Draft محفوظ مؤقتاً، last-filter preference |
| **In-memory (module vars)** | حالة UI مؤقتة جداً | حتى reload الصفحة | Flag "هل فُتح المودال"، animation lock |

### تحذيرات الطبقات

```
❌ ممنوع: حالة الـ modal مع URL params — تخلق روابط تفتح modal تلقائياً
❌ ممنوع: بيانات الأمان أو الهوية في history.state أو sessionStorage
❌ ممنوع: استخدام localStorage للـ navigation state — استخدم sessionStorage
❌ ممنوع: ?next= في URL params إلا في سياق Auth Return Destination (NAV-07)
✅ مسموح: ?filter=all في URL لأنه يعكس حالة shareable
✅ مسموح: history.state للـ layerStack وscrollY وnavigation context فقط
```

### History State Namespace

```js
// الـ namespace المعتمد لأي push/replace في نظام Navigation
history.pushState({
  nav: {
    entryType: 'push',       // 'push' | 'replace-init'
                             // 'push'  = navigation داخلي متحكَّم فيه صراحةً
                             // 'replace-init' = تهيئة الصفحة فقط (replaceState عند load)
    layer: 'modal',          // 'page' | 'modal' | 'drawer' | 'overlay'
    layerStack: ['modal-a'], // مصفوفة أسماء الـ layers المفتوحة حالياً
    context: {               // سياق Navigation للـ Back Trust check
      origin: 'tawasalna',   // علامة أن الـ state جاء من داخل تواصلنا
      from: '/home',         // الصفحة التي جاء منها المستخدم
      id: 123                // resource ID اختياري — لا بيانات أمان
    },
    scrollY: 420             // موضع التمرير للـ baseline — انظر NAV-09
  }
}, '', location.href)
```

**`entryType` هو المعيار الفاصل بين الـ entries:**

| القيمة | المعنى | استخدام Back |
|--------|--------|-------------|
| `'push'` | navigation داخلي متحكَّم فيه — pushed صراحةً بكود تواصلنا | آمن — يعود إلى entry تواصلنا سابق |
| `'replace-init'` | تهيئة أولية فقط (replaceState عند load) | **غير آمن** — الـ previous browser entry غير معروف |
| `undefined` / غير موجود | entry خارجي أو قديم بدون namespace | **غير آمن** — لا يمكن التحقق |

**سياق قراءة `entryType` (مهم):**
- **قبل `history.back()` من زر برمجي:** يُقرأ من `history.state.nav.entryType` الحالي — هذا هو الـ source entry الذي سيُغادَر. الفحص صحيح هنا.
- **داخل `popstate` handler:** `event.state` هو الـ destination entry الذي أصبح active — ليس الـ source الذي غادرناه. فحص `entryType` في الـ popstate يقرأ حالة الـ **target**، وليس الـ source.
- **لـ Layer popstack:** المقارنة تكون بين in-memory active stack snapshot (قبل الانتقال) وبين `event.state.nav.layerStack` (الـ target). انظر NAV-04.

> هذا الـ namespace مقترح للتوحيد المستقبلي. الصفحات الحالية تستخدم `{ modal: 'name' }` —
> اقرأ NAV-04 لفهم الـ pattern الحالي قبل تعديله.

---

## [NAV-04] Layer Stack & Back Contract

### تعريف الـ Layer

**Layer** = أي عنصر UI يعلو فوق الصفحة الأساسية ويُغلق بـ Back:
- Modal (نافذة حوار)
- Drawer / Side Panel
- Full-screen Overlay
- Bottom Sheet

### مبدأ LIFO (Last In First Out)

```
صفحة → [Modal A] → [Modal B]
Back  →            [Modal A]
Back  → صفحة
```

الـ layer الأحدث يُغلق أولاً. لا يُسمح بغلق layer أعمق دون غلق ما فوقه أولاً.

### Pattern الحالي (company.main.js — للمرجعية)

```js
// 1. عند تهيئة الصفحة — إنشاء baseline بدون layers
history.replaceState({ modal: null }, '', location.href)

// 2. عند فتح layer
history.pushState({ modal: 'editModal' }, '', location.href)
_editModalHistoryPushed = true

// 3. عند إغلاق layer برمجياً
if (_editModalHistoryPushed) {
  _editModalHistoryPushed = false
  history.back()  // ← يُطلق popstate → يُغلق الـ modal
}

// 4. الـ popstate listener يعالج الإغلاق
window.addEventListener('popstate', e => {
  if (!e.state?.modal) { _closeAllModals() }
  else if (e.state.modal === 'editModal') { /* handle */ }
})
```

> **ملاحظة على الـ pattern الحالي:**
> - سطر 1975 و 4624 في `company.main.js` يحتويان على `popstate` listeners مستقلَّين.
> - هذا الفصل ينتج عن نمو تدريجي — ليس الـ contract المثالي.
> - موثَّق هنا كـ gap للتوحيد المستقبلي.

### Layer Stack Reconciliation (المستهدف للتنفيذ المستقبلي)

عند انتقال الـ history state من stack إلى آخر، المطلوب مقارنة الـ stacks وإغلاق الـ layers المُزالة بالترتيب العكسي (LIFO):

```
Current stack: ['A', 'B']
Target stack:  ['A']

→ B هو الـ layer المُزال → أغلق B أولاً (لا تلمس A)
```

مثال أكثر تعقيداً:
```
Current stack: ['A', 'B', 'C']
Target stack:  ['A']

→ أغلق C أولاً (LIFO) → ثم أغلق B → A يبقى مفتوحاً
```

المبدأ: **لا تُغلق A لمجرد أنك تريد الوصول إلى Target. أغلق فقط ما أُضيف فوقه بترتيب عكسي.**

```js
// Reconciliation pseudocode (للتوثيق — لا تنفيذ الآن)
// currentStack = in-memory snapshot للـ active stack قبل الانتقال
//               (يجب تتبعه في module-level var — ليس e.state.nav.layerStack)
// targetStack  = e.state.nav.layerStack الموجود في الـ destination entry
function reconcileLayers(currentStack, targetStack) {

  // ── VALIDATION FIRST — قبل أي mutation ──────────────────────────────

  // حالة A: targetStack أطول من currentStack → Forward/Reopen
  // هذه ليست Back-close reconciliation — خارج نطاق V1
  if (targetStack.length > currentStack.length) {
    return // لا تتعامل معه بإغلاق صامت
  }

  // حالة B: targetStack يجب أن يكون prefix حقيقي من currentStack
  // ['A'] هو prefix من ['A','B','C'] ✓
  // ['B'] ليس prefix من ['A','B']   ✗ (A≠B في index 0)
  const isValidPrefix = targetStack.every(
    (layer, i) => currentStack[i] === layer
  )
  if (!isValidPrefix) {
    return // STOP — state غير متسق → لا تغلق أي شيء
  }

  // ── CLOSE — الـ suffix فوق الـ target prefix فقط، LIFO ──────────────
  const toClose = currentStack.slice(targetStack.length).reverse()
  toClose.forEach(layer => window.NavLayers?.[layer]?.close?.())
}
```

**أمثلة:**

```
Current: ['A','B','C'] / Target: ['A']
→ isValidPrefix = true  → toClose = ['C','B'] → أغلق C ثم B → A يبقى

Current: ['A','B']     / Target: ['B']
→ isValidPrefix = false (currentStack[0]='A' ≠ targetStack[0]='B')
→ STOP — لا تغلق أي شيء

Current: ['A']         / Target: ['A','B','C']
→ targetStack.length > currentStack.length → Forward/Reopen → خارج نطاق V1
```

**لماذا validation قبل mutation:**
الـ pseudocode السابق كان يحسب `toClose` ثم يُغلق ثم يعلّق على الـ invalid state.
الترتيب الصحيح: تحقق من صحة الـ state كاملاً **قبل** أي `close()` — لأن الإغلاق الجزئي يُخلّف state غير متسق.

> التنفيذ مؤجَّل. الـ Pattern الحالي يبقى كما هو حتى PR مخصص.

---

## [NAV-05] Unified Back Contract

### Back Intent — نوعان من Back

الـ "Back" في تواصلنا يصدر من مصادر متعددة، لكنه ينقسم إلى نوعين بحسب إمكانية الاعتراض:

#### أ) Interceptable Back — يمر بالـ Navigation Back Resolver

| المصدر | ملاحظة |
|--------|--------|
| زر Back داخل الواجهة (`<button>`) | Back Logic يُنفَّذ صراحةً من JS |
| إغلاق Layer عبر same-document popstate | `history.back()` داخل الصفحة → popstate في نفس document |
| WebView / Flutter — حين توفر المنصة interception | مرحلة مستقبلية (NAV-12) |

هذه الحالات تستخدم الـ 5-step Back Priority Resolution التالية.

#### ب) Native Browser Page-level Back — يتبع Browser History الطبيعي

| المصدر | ملاحظة |
|--------|--------|
| زر Back في المتصفح (page navigation) | المتصفح قد يُغادر الصفحة قبل تنفيذ JS |
| Android Back / Back Gesture (page-level) | platform navigation — غير مضمون الاعتراض في MPA |

**القواعد الثابتة لـ Native Browser Back:**
- **لا History Trap:** ممنوع استخدام `beforeunload` أو أي آلية لمنع المستخدم من مغادرة الصفحة.
- **لا ادعاء باعتراض مضمون:** `popstate` في Web MPA يُعالج الـ same-document navigation فقط — لا يمنع خروج المستخدم من الموقع.
- **Contextual Fallback ليس بديلاً عن Browser Back:** الـ fallback هو الوجهة الصحيحة لزر Back **داخل الواجهة** — ليس اعتراضاً لزر Back في المتصفح.

**النظام يُوحِّد سلوك Interceptable Back** قدر الإمكان، بدون ادعاء قدرة تقنية غير موجودة أو تخريب Browser History الطبيعي.

### خمس خطوات الأولوية (Back Priority Resolution)

> **نطاق الـ Resolver:** يُطبَّق على **Interceptable Back** فقط (زر Back داخل الواجهة + same-document Layer close).
> **لا يُطبَّق** على Native Browser Page-level Back — الذي يتبع Browser History الطبيعي.

عند Interceptable Back، يُحلَّل الموقف بهذا الترتيب:

```
1. هل يوجد Layer مفتوح في الـ Stack؟
   ↳ نعم → أغلق آخر Layer (LIFO) — see NAV-04 → STOP
   ↳ لا  → تابع

2. هل الـ current history entry عبارة عن Internal Controlled Push؟
   ↳ فحص: history.state?.nav?.entryType === 'push'
     (يُقرأ من الـ current active entry — قبل استدعاء history.back())
   ↳ نعم → history.back() آمن — الـ previous entry هو entry تواصلنا السابق
             (لأن هذا الـ entry pushed صراحةً فوقه) → STOP
   ↳ لا  → تابع
     (entryType === 'replace-init' أو undefined → previous entry غير معروف)

3. هل يوجد context.from موثوق وصالح؟
   ↳ فحص: history.state?.nav?.context?.from مع validation (انظر أدناه)
   ↳ نعم → window.location.href = validated_from → STOP
     (لا تستخدم history.back() — browser entry السابق قد يكون خارجياً)
   ↳ لا  → تابع (Deep Link أو أول صفحة في التاب أو مصدر خارجي)

4. هل يوجد Contextual Canonical Fallback للصفحة الحالية؟ (NAV-06)
   ↳ نعم → navigate إلى الـ fallback المحدد لهذه الصفحة ونوع الحساب → STOP
   ↳ لا  → تابع

5. Global Fallback المناسب لنوع الحساب:
   ↳ emp → /home
   ↳ co  → /u/{co_tw_id}
   ↳ edu → /edu-profile
   ↳ guest → /
```

### context.from Validation (إلزامي قبل الاستخدام في خطوة 3)

```
context.from يُقبَل فقط إذا تحقق كل ما يلي:
✓ string غير فارغ
✓ يبدأ بـ / (internal relative path)
✓ لا يبدأ بـ //
✓ same-origin (new URL(from, origin).origin === origin)
✓ لا يبدأ بـ /login (يمنع الـ loop)
```

هذا **Navigation Safety** — ليس Security Boundary. الـ `history.state` ليس مصدراً موثوقاً للـ authorization.

### لماذا لا `history.length > 1` — ولماذا لا يكفي `origin === 'tawasalna'` وحده

- **`history.length > 1`:** لا يعني أن الـ history السابق داخل تواصلنا.
- **`nav.context.origin === 'tawasalna'` في الـ current entry:** يُثبت أن *هذا الـ entry* جاء من code تواصلنا فقط — لا يثبت شيئاً عن الـ *previous* browser entry.
- **`entryType === 'push'`:** يثبت أن هذا الـ entry pushed فوق entry سابق داخلي — `history.back()` آمن. لكن انتبه: هذا الفحص يُقرأ من الـ **current active state قبل** `history.back()` — ليس من `event.state` في الـ popstate.
- **`replaceState` عند init:** لا يُضيف entry جديداً في stack المتصفح — بل يُعدِّل الـ current entry. لذلك بعد `replace-init`، الـ previous entry غير معروف.

**ملاحظة:** هذا UX/Navigation trust فقط — ليس Security Boundary. الـ authorization يبقى server-side.

### قواعد ثابتة

1. **لا `history.back()` مباشر بدون back-trust check** في أي زر Back جديد.
2. **Back لا يُغيَّر بالـ Viewer Mode** — نفس سلوك الرجوع للـ Owner والـ Registered User والـ Guest.
3. **Back لا يُحدِّث حالة Authentication** — الرجوع لا يمنح ولا يسحب صلاحيات.
4. **`?next=` ليس جزءاً من Back Resolution** — هو حصراً لـ Auth Return Destination (NAV-07).

### ثغرات موثقة في الكود الحالي (لا تُصلح هنا)

| الثغرة | الموقع | الـ gap |
|--------|--------|---------|
| `history.back()` مباشر بدون back-trust check | `static/job/job-detail.js:729` | Deep Link يخرج من الموقع |
| `popstate` listener مزدوج | `company.main.js:1975` و `:4624` | قد يتعارضان |
| `redirect()` لا تحفظ `?next=` | `index.auth.js` | ضياع وجهة العودة بعد login |

---

## [NAV-06] Safe Fallback System

### المبدأ

كل صفحة يجب أن تعرف إلى أين ترجع المستخدم حين لا يوجد Navigation Context موثوق.
الـ fallback يجب أن يكون **Context-aware** و**Account-type-safe**.

**ممنوع توجيه شركة أو جهة تعليمية إلى `/home`** — `/home` صفحة feed خاصة بالموظف.

### Contextual Canonical Fallback Map

| الصفحة الحالية | emp | co | edu | guest |
|---------------|-----|-----|-----|-------|
| `/job-detail?id=X` | `/home` | `/u/{co_tw_id}` (صفحة الشركة) | `/edu-profile` | `/` |
| `/messages` | `/home` | `/u/{co_tw_id}` | `/edu-profile` | `/login` |
| `/notifications` | `/home` | `/u/{co_tw_id}` | `/edu-profile` | `/login` |
| `/settings` | `/home` | `/u/{co_tw_id}` | `/edu-profile` | `/login` |
| `/u/{tw_id}` (profile آخر) | `/home` | `/u/{co_tw_id}` | `/edu-profile` | `/` |
| `/u/{tw_id}` (profile خاص) | `/home` | `/u/{co_tw_id}` | `/edu-profile` | — |

### Global Fallback (الملجأ الأخير)

إذا لم يوجد Contextual Canonical Fallback مناسب أو لم يُعرف نوع الحساب:

| نوع الحساب | Global Fallback |
|-----------|-----------------|
| emp | `/home` |
| co | `/u/{co_tw_id}` |
| edu | `/edu-profile` |
| guest (لا auth) | `/` (landing) |
| غير معروف | `/login` |

### قواعد الـ Fallback

1. **الـ fallback يجب أن يكون مناسباً لنوع الحساب** — لا تُوجِّه شركة إلى `/home`.
2. **Guest fallback → `/` (landing)** — ليس `/home` لأن `/home` يتطلب auth.
3. **Fallback لا يحمل `?next=`** — ممنوع إنشاء loop.
4. **لا تخترع routes غير موجودة** — الـ fallback يكون لصفحة موثَّقة فعلاً في NAV-02.
5. **`/home` هو Global Fallback للـ emp فقط** — ليس fallback عاماً لجميع أنواع الحسابات.

---

## [NAV-07] Return Destination (`?next=`)

### الغرض الوحيد

`?next=` مخصص **حصراً** لحفظ Return Destination عند تحويل مستخدم إلى `/login`:

```
// المستخدم يحاول الوصول إلى /job-detail?id=42 بدون auth
→ redirect إلى: /login?next=/job-detail%3Fid%3D42
→ بعد login ناجح: redirect إلى /job-detail?id=42
```

**`?next=` ليس Back fallback عادياً** — لا يُستخدم في Unified Back Contract (NAV-05).

### قواعد Open Redirect Protection (إلزامية)

```
1. يجب أن تبدأ بـ / (slash) — لا https:// ولا // ولا protocol آخر
2. يجب ألا تحتوي على // بعد الـ / الأولى
3. يجب ألا تبدأ بـ //
4. يجب ألا تحتوي domain آخر
5. يجب أن تكون relative path فقط

مثال صالح:   /job-detail?id=42
مثال مرفوض: https://evil.com/phish
مثال مرفوض: //evil.com
مثال مرفوض: /\evil.com
مثال مرفوض: /login (لا تُعيد المستخدم إلى login)
```

### خوارزمية التحقق (للتنفيذ المستقبلي)

```js
function isValidNext(next) {
  if (!next) return false
  if (!next.startsWith('/')) return false
  if (next.startsWith('//')) return false
  if (next.startsWith('/login')) return false // لا loop
  try {
    const url = new URL(next, window.location.origin)
    return url.origin === window.location.origin
  } catch { return false }
}
```

### الحالة الحالية

`redirect()` في `index.auth.js` **لا تقرأ `?next=`** حالياً.
هذه ثغرة موثَّقة (NAV-05) — لا تُصلح في هذا الـ PR.

---

## [NAV-08] Deep Link Safety

### التعريف

**Deep Link** = URL مباشر يفتح الصفحة بدون أي history مسبق.
مثال: مشاركة رابط `/job-detail?id=42` — المستلم يفتحه في tab جديد.

### المتطلب

**كل صفحة يجب أن تعمل بشكل كامل من URL مباشر، بدون أي افتراض عن ما سبق.**

### فحص Deep Link Safety لكل صفحة جديدة

| السؤال | المطلوب |
|--------|---------|
| هل تقرأ `history.state` عند التحميل؟ | يجب أن تنجح حتى لو `history.state` فارغ |
| هل تعتمد على `history.back()` للرجوع؟ | يجب وجود back-trust check أولاً (NAV-05) |
| هل تحتاج بيانات من صفحة سابقة؟ | يجب جلبها من API مجدداً، لا من state |
| هل الـ UI الأولي يحتاج init data؟ | يجب جلبه من API أو من `window._injectedVar` |

### Smart Router — مثال Deep Link صحيح

```python
# server.py — Smart Router يُحقن البيانات الضرورية في الـ HTML
@app.get("/u/{tw_id}")
async def smart_profile_router(tw_id: str):
    # يقرأ من DB → يُحقن في HTML
    return HTMLResponse(f"""
      <script>window._companyProfileIdFromRoute = {int(uid)}</script>
      {html_content}
    """)
```

هذا الـ pattern يضمن أن الصفحة تعمل من Deep Link مباشر بدون سابق تاريخ.

---

## [NAV-09] Scroll Restoration

### السلوك الافتراضي

```
history.scrollRestoration = 'auto'
```

المتصفح يتولى استعادة موضع التمرير تلقائياً. لا code مطلوب في الحالة الطبيعية.

### الاستثناءات الموثَّقة (متى يكون `manual`)

استخدم `manual` فقط في الحالات التالية:

| الحالة | السبب |
|--------|-------|
| فتح modal ثم Back | يجب استعادة scrollY من قبل فتح الـ modal |
| بعد تحديث feed (pull-to-refresh) | scroll إلى الأعلى تجربة UX مقصودة |
| صفحة تبدأ من أعلى دائماً (post-login) | `window.scrollTo(0, 0)` عند init |

### تخزين scrollY للـ Layers

**المبدأ:** `popstate event.state` يمثل الـ destination entry الذي أصبح active بعد التنقل — وليس الـ entry الذي خُرج منه. لذلك يجب حفظ `scrollY` في الـ **baseline/destination** entry قبل push الـ layer، لا في الـ layer entry نفسه.

```js
// Pattern صحيح — حفظ scrollY في الـ baseline entry قبل فتح الـ layer
// 1. قبل push: ابحث عن الـ current baseline entry وحدّثه
const currentScrollY = window.scrollY

// حفظ في الـ baseline entry (replaceState على الـ current entry)
const baselineState = history.state ?? {}
history.replaceState(
  { ...baselineState, nav: { ...(baselineState.nav ?? {}), scrollY: currentScrollY } },
  '', location.href
)

// 2. الآن push الـ layer entry
history.pushState({
  nav: { entryType: 'push', layer: 'modal', layerStack: ['modal-a'],
         context: { origin: 'tawasalna', from: location.pathname } }
}, '', location.href)

// 3. عند Back — e.state هو الـ baseline entry (الـ destination)
//    scrollY محفوظ فيه من الخطوة 1
window.addEventListener('popstate', e => {
  const nav = e.state?.nav ?? {}
  if (!nav.layer && nav.scrollY != null) {
    window.scrollTo({ top: nav.scrollY, behavior: 'instant' })
  }
})
```

> هذا توثيق للـ pattern المعماري الصحيح — لا تنفيذ فعلي في هذا الـ PR.
> الـ pattern الحالي في `company.main.js` يحتاج مراجعة عند تنفيذ Layer Stack الموحَّد.

---

## [NAV-10] Auth-Gated Navigation

### ثلاث حالات

| الحالة | الإجراء |
|--------|---------|
| مستخدم مسجَّل يصل إلى صفحة تتطلب auth | الصفحة تُكمَّل طبيعياً |
| Guest يصل إلى صفحة تتطلب auth | redirect إلى `/login?next={current_path}` |
| مستخدم مسجَّل بنوع خاطئ (مثلاً emp يصل إلى `/company-profile`) | redirect إلى الـ Global Fallback المناسب لنوعه (NAV-06) |

### Auth Guard Pattern الحالي

```js
// كل صفحة محمية تبدأ بهذا
const _u = JSON.parse(localStorage.getItem('tawasalna_user') || 'null')
if (!_u) { location.href = '/login' }
```

> **ثغرة موثَّقة:** الـ pattern الحالي لا يحفظ الـ `?next=` عند redirect إلى login.
> لا يُصلح في هذا الـ PR — موثَّق في NAV-05 وNAV-07.

### قواعد إلزامية

1. **Redirect إلى `/login` دائماً — ليس إلى صفحة auth بديلة.**
2. **`?next=` يجب أن يُمرَّر مع الـ redirect** (عند التنفيذ) — مع Open Redirect validation.
3. **التحقق من الـ token يجب أن يتم server-side** — client-side check هو UX hint فقط.
4. **لا redirect loop:** إذا كانت `?next=` تؤدي إلى `/login`، تجاهلها.

---

## [NAV-11] Navigation & Viewer Modes

### القاعدة الجوهرية

> **Navigation لا يمنح صلاحيات ولا ينتزعها.**
> وصول URL إلى صفحة لا يعني إذناً بالعمليات داخلها.

### العلاقة مع [DS-VM]

| الـ Navigation يتحكم في | الـ Viewer Modes يتحكم في |
|------------------------|-------------------------|
| إلى أين يذهب المستخدم | ماذا يرى ويفعل بعد وصوله |
| Route + URL params | Authentication + Authorization + Ownership |
| UX flow | Security enforcement |

### قواعد الفصل

1. **URL وقراءة params هي عملية تحديد موارد (Resource Identification) — ليست authorization.**
   انظر: `VIEWER-MODES.md → VM-05`.
2. **Viewer Mode يُحدَّد server-side** — لا يُشتَق من URL أو history.
3. **Deep Link إلى صفحة محمية → auth check → إذا Guest → redirect to login.** لا تُسقط الـ Viewer Mode check بسبب طريقة الوصول.
4. **Back Button لا يُغيِّر Viewer Mode** — الرجوع إلى صفحة سبق زيارتها لا يُعيد تحديد الهوية.

---

## [NAV-12] Flutter Readiness

> **هذا القسم توثيق مستقبلي فقط — لا implementation الآن.**

### السياق

تواصلنا منصة Web-first حالياً (F1).
عند بناء تطبيق Flutter في المستقبل، سيحتاج Navigation System إلى امتداد محدد.

### المفاهيم اللازمة (للدراسة المستقبلية)

| المفهوم | المنصة | الغرض |
|---------|--------|-------|
| Universal Links | iOS | فتح رابط https:// في التطبيق مباشرة |
| App Links | Android | نفس الغرض في Android |
| Intent Filters | Android | تعريف الروابط التي يستقبلها التطبيق |
| Deep Link Handler | Flutter | معالجة الرابط الوارد داخل التطبيق |

**ملاحظة على Back Intent في Flutter:**
النظام الحالي يُوحِّد Back Intent سلوكياً. في Flutter، آلية استقبال الـ Intent ستختلف (Navigator 2.0 / GoRouter / platform channel) لكن الـ 5-step Priority Resolution يبقى نفسه.

### متطلبات الويب المستقبلية (لا تُنفَّذ الآن)

```
1. Well-known files:
   /.well-known/apple-app-site-association  (iOS Universal Links)
   /.well-known/assetlinks.json             (Android App Links)

2. هذه الملفات يجب أن تُضاف في server.py كـ static routes
   حين يُطلب — لا تُضاف قبله.

3. الـ URL structure الحالي (/u/{tw_id} إلخ) متوافق مع Deep Links
   بدون تغيير.
```

### الحالة الحالية (مقبولة)

- الـ URL structure موثَّق (NAV-02) وجاهز للتوسع.
- لا Flutter targets الآن.
- لا `.well-known` files الآن.
- ممنوع إضافة أي من هذه الملفات قبل طلب صريح.

---

## Forbidden Patterns

```
❌ client-side router — لا يوجد ولا يُخطَّط له (F7)
❌ hash routing (#) لأغراض navigation — محجوز للـ anchors فقط
❌ ?next= لأغراض غير Auth Return Destination
❌ ?next= داخل Back Resolution (NAV-05) — خطأ معماري
❌ history.back() مباشر بدون back-trust check
❌ history.length > 1 كدليل أن الرجوع داخل تواصلنا
❌ nav.context.origin === 'tawasalna' وحده كدليل أن الـ previous entry داخلي
❌ فحص entryType من event.state في popstate كبديل عن in-memory source snapshot
❌ History Trap — beforeunload أو أي آلية لمنع Browser Back الطبيعي
❌ ادعاء أن Contextual Fallback يستبدل Browser Back دائماً في Web MPA
❌ Layer Reconciliation بدون validation مسبق لـ targetStack كـ prefix صحيح
❌ context.from بدون validation قبل الاستخدام كوجهة navigate
❌ استخدام URL أو query params كمصدر للـ authorization
❌ ربط Viewer Mode بالـ URL
❌ توجيه co أو edu إلى /home كـ fallback
❌ توجيه guest إلى /home (يتطلب auth)
❌ popstate listener مستقل لكل modal بدون Layer Stack namespace
❌ localStorage كمصدر لـ navigation state
❌ ?next= يؤدي إلى domain آخر (Open Redirect)
❌ .well-known files قبل طلب صريح لـ Flutter
❌ إضافة implementation code في هذا الملف
```

---

*آخر تحديث: 2026-07-20 — §41 in SYSTEMS_INDEX.md.*
*الحالة: V1 Documentation ✅ · Implementation 🔜*
