# تواصلنا — Architecture Doctrine

> **Single Source of Truth** للمعمارية.  
> أي تطوير جديد يلتزم بهذا الملف. أي استثناء يُسجَّل هنا قبل التطبيق.

---

## قائمة القواعد السريعة

| # | القاعدة | Priority |
|---|---------|----------|
| 1 | API = المصدر النهائي للصلاحيات | **P0** |
| 2 | View Mode ثلاثي | **P1** |
| 3 | CSS = عرض فقط | **P2** |
| 4 | JS = سلوك فقط | **P2** |
| 5 | صفحة واحدة + View Mode | **P1** |
| 6 | Unified Components | **P2** |
| 7 | قواعد الإضافات المستقبلية | **P2** |
| 8 | Single Source of State | **P1** |
| 9 | Rendering Order | **P2** |
| 10 | Bootstrap Idempotency | **P1** |
| 11 | Controlled Exceptions | **P0** |
| 12 | Theme Ownership | **P1** |
| 13 | Theme System | **P2** |
| 14 | Script Integrity | **P0** |

---

# A — ARCHITECTURE CORE

> **P0/P1:** غير قابل للكسر. أي تجاوز يتطلب Exception مسجّل.

---

## [P0] 1. API = المصدر النهائي للصلاحيات

```python
# كل endpoint يتحقق من الصلاحية server-side
if str(token.get("user_id")) != str(resource_owner_id):
    raise HTTPException(403, "Unauthorized")
```

- UI checks هي UX فقط — ليست حماية.
- أي mutation (POST/PUT/DELETE) يتحقق من token ownership.
- لا تعتمد على frontend لمنع عمليات غير مصرح بها.

---

## [P0] 11. Controlled Exceptions Rule

أي استثناء مسموح **فقط** بالشروط الثلاثة معاً:

1. **موثّق في هذا الملف** — لا استثناءات ضمنية.
2. **سبب تقني واضح** — performance / UX / platform limitation.
3. **لا يتجاوز الـ security model** — صلاحيات / state / auth.

**صيغة التسجيل:**
```markdown
Exception [N]: [اسم]
- القاعدة: Rule #X
- السبب: [تقني واضح]
- الحد: [ما يُسمح به بالضبط]
- أمان: لا يوجد / [وصف]
```

---

## [P0] 14. Script Integrity

- كل `<script>` له `</script>` مطابق — العدد دائماً متساوٍ.
- لا `</script>` يدوي خارج block.
- لا debug strings داخل `innerHTML` أو template literals.

**Invariant قبل كل deploy:**
```bash
opens=$(grep -c "<script" profile.html)
closes=$(grep -c "</script>" profile.html)
[ "$opens" = "$closes" ] || { echo "❌ Script tag mismatch!"; exit 1; }
```

---

## [P1] 2. View Mode — ثلاث حالات واضحة

```javascript
const viewMode = isOwner ? "owner" : _sessionUser ? "public-user" : "guest";
```

| Mode | من | CSS class | يرى |
|------|-----|-----------|-----|
| `owner` | صاحب البروفايل | — | App Shell + أدوات الإدارة |
| `public-user` | مسجّل يشوف غيره | `public-view` | Public Header + محتوى |
| `guest` | غير مسجّل | `public-view` | Public Header + CTA login |

**تطبيق Feature جديدة لـ owner:**
```javascript
// 1. HTML
class="owner-only"
// 2. CSS
body.public-view .my-widget { display:none }
// 3. JS
function myAction() { if(!isOwner) return; ... }
// 4. API
if token.user_id != resource.user_id → 403
```

---

## [P1] 5. صفحة واحدة + View Mode

```
✅ profile.html + viewMode switch
❌ profile.html + profile-public.html (نسختان)
```

استثناء: إذا الصفحتان مختلفتان جذرياً في البنية.

---

## [P1] 8. Single Source of State

```javascript
// ✅ State من Backend فقط
const isOwner = profile.user_id === token.user_id;  // server-verified

// ❌ ممنوع
const isOwner = window.location.href.includes(userId);  // DOM/URL
const isOwner = localStorage.getItem("isOwner");         // LS
```

- `localStorage` مرآة مؤقتة فقط — تُعاد بناؤها من API في كل Step 2.
- URL params و DOM state هي hints، ليست source of truth.

---

## [P1] 10. Bootstrap Idempotency

```javascript
window.__profileBooted = window.__profileBooted || false;
if (window.__profileBooted) {
    document.body.classList.remove("profile-loading");
    return;
}
window.__profileBooted = true;
// ... rest of init
```

كل صفحة تملك `window.__[pageName]Booted` flag يمنع double render.

---

## [P1] 12. Theme Ownership

**المبدأ:** الثيم ملك صاحب البروفايل — لا المشاهد.

```
DB (profiles.profile_style) → API → Step 2 → body.sX
```

| من يفتح | مصدر الثيم | يكتب LS؟ | يكتب DB؟ |
|---------|-----------|---------|---------|
| Owner | DB → API | ✅ | ✅ عند تغيير |
| Non-owner | DB → API | ❌ | ❌ |
| Guest | DB → API | ❌ | ❌ |

**Init rule:**
```javascript
// ✅ Owner فقط يقرأ LS theme
if(isOwner) { apply LS theme + curStyle = savedStyle }
// Non-owner: body stays as SSR class until Step 2
```

**Type safety:**
```javascript
// ✅ دائماً string للـ API
{ profile_style: String(n) }
// ❌ int → Pydantic v2 يرفض → 422
```

---

# B — CODING STANDARDS

> **P2/P3:** يُطبَّق على كل كود جديد. تغييره يتطلب مناقشة.

---

## [P2] 3. CSS = عرض فقط

```css
/* ✅ CSS للإظهار/الإخفاء */
body.public-view .owner-only { display: none; }

/* ❌ CSS لا يحمي — يخفي فقط */
```

---

## [P2] 4. JS = سلوك فقط

```javascript
// ✅ كل owner action يبدأ بـ guard
function saveProfile() {
    if (!isOwner) return;
    if (!_sessionUser?.id) return;
    // ... logic
}
```

---

## [P2] 6. Unified Components

```javascript
// ✅ Component واحد مع isOwner
function renderSkillItem(item) {
    const controls = isOwner ? `<div class="item-menu-wrap">...</div>` : "";
    return `<div class="item">${content}${controls}</div>`;
}

// ❌ نسختان منفصلتان
function renderSkillItem_owner(item) { ... }
function renderSkillItem_public(item) { ... }
```

---

## [P2] 7. قواعد الإضافات المستقبلية

**Component جديد:**
- مكوّن واحد يقرأ `isOwner` أو `window.isOwner`.
- لا نسخ منفصلة.

**Migration للكود القديم:**
```javascript
// عنصر يظهر خطأ في public-view:
body.public-view #elementId { display:none }  // CSS
if(!isOwner) return;                           // JS
```

---

## [P2] 9. Rendering Order

```
1. viewMode detection   → من Backend response
2. global flags         → isOwner, _sessionUser
3. layout render        → CSS class switch
4. event listeners      → bind بعد render
5. async data fetch     → Step 2
6. DOM update           → من API فقط
```

- Steps 1-3 sync → لا flicker.
- Steps 5-6 async → لا blocking.

---

## [P2] 13. Theme System

### المتغيرات الرسمية

```css
body.sX {
    --text-color:  /* النص الأساسي */
    --muted-text:  /* النص الثانوي */
    --drag-color:  /* drag handles */
    --surface:     /* خلفية الكروت */
    --border:      /* الحدود */
    /* UI Controls tokens */
    --ui-muted:    /* #64748b في light */
    --ui-soft:     /* #94a3b8 في light */
    --ui-border:   /* #555 في light */
    --ui-strong:   /* #1f2937 في light */
}
```

### ثيم جديد = 9 متغيرات فقط، لا لمس لأي component.

### Hard Ban

```css
/* ❌ ممنوع في render functions / inline JS */
color: #fff;  color: rgba(255,255,255,.X);  color: white;
color: rgba(0,0,0,.X)  /* بدون var() */

/* ✅ البديل */
color: var(--text-color);  color: var(--muted-text);
color: var(--ui-muted);    color: var(--ui-soft);
```

### Render Function Separation

```javascript
// ✅ Logic أعلى، Template أسفل
function renderItem(item) {
    const escaped = sanitize(item.name);
    const badge = item.level || "";
    return `<div>${escaped}<span>${badge}</span></div>`;
}

// ❌ Logic + HTML + debug مخلوطين
```

---

## [P3] Schema Drift Prevention

```python
# كل column في SELECT يجب أن يكون في _migrations
_migrations = [
    "ALTER TABLE experience ADD COLUMN IF NOT EXISTS company TEXT",
]
```

- `_safe_query` تفرق بين EMPTY RESULT و QUERY FAILURE.
- `[SCHEMA_ERROR]` في logs = migration ناقصة.

---

# C — EXCEPTIONS LOG

> الاستثناءات الموثّقة. أي استثناء جديد يُضاف هنا **قبل** التطبيق.

---

### Exception 01 — localStorage كـ session cache
- **القاعدة:** Rule #8 (Single Source of State)
- **السبب:** تجنب re-fetch عند كل page navigation — UX performance
- **الحد:** LS مرآة مؤقتة فقط، تُعاد من API في كل Step 2
- **أمان:** لا يوجد — API يتحقق من JWT في كل request

### Exception 02 — CSS يخفي owner elements
- **القاعدة:** Rule #3 (CSS = عرض فقط)
- **السبب:** atomic reveal بدون flicker
- **الحد:** CSS للإخفاء البصري فقط؛ JS guard مطلوب أيضاً لكل owner action
- **أمان:** لا يوجد — API هو المصدر النهائي

### Exception 03 — Init: CSS Only, No Mutations
- **القاعدة:** Rule #9 (Rendering Order)
- **السبب:** عدم استدعاء setStyle في init يمنع 422 من Pydantic type mismatch
- **الحد:** Init يطبق CSS class فقط؛ Step 2 يطبق القيمة الحقيقية من DB
- **أمان:** لا يوجد

---

## الحالة النهائية المعتمدة (2026-05-30)

```
CSS   → متى يظهر العنصر (display/visibility)
JS    → ماذا يفعل العنصر (behavior/logic)
API   → هل مسموح بالعملية (authorization)
```

**Theme:**
- `profile_style` و `profile_color` يُطبَّقان لجميع المشاهدين من DB
- LS write للـ owner فقط
- SSR injection يمنع FOUC — cache يُمسح عند تغيير الثيم

**Schema:**
- EMPTY RESULT ≠ QUERY FAILURE — `_safe_query` تفرق بينهما
- `[SCHEMA_ERROR]` في logs = ارتفع على الفور ونفّذ migration

---

## الحالة المعتمدة — View Mode & CSS Classes (2026-05-30)

### النظام الحالي (مستقر — لا تغيّر)

```
viewMode (JS)     →  body CSS class     →  UI rendering
─────────────────────────────────────────────────────
"owner"           →  (no class)         →  full app shell
"public-user"     →  public-view        →  public header only
"guest"           →  public-view        →  public header + CTA
"owner+preview"   →  public-view        →  simulates public-user
```

**`public-view` = derived CSS alias من viewMode، وليس state مستقل.**

لا يُقرأ منه الـ state — يُكتب إليه فقط من:
```javascript
document.body.classList.add('public-view');        // non-owner init
document.body.classList.toggle('public-view', previewMode); // preview
```

**`preview-mode` = sync trigger فقط:**
```javascript
// togglePreview يعمل شيئاً واحداً فقط:
document.body.classList.toggle('preview-mode', previewMode);
document.body.classList.toggle('public-view', previewMode);
// لا يغيّر viewMode — لا يحفظ state — trigger فقط
```

---

### Future Optimization (مؤجّل — ليس أولوية)

**اقتراح:** rename إلى `view-owner` / `view-public-user` / `view-guest`  
**السبب:** cleaner semantics، single class per state  
**الحالة:** مؤجّل — refactor كبير بدون فائدة وظيفية فورية  
**متى يُنفَّذ:** عند بناء صفحة جديدة من الصفر أو عند وجود فريق  
**شرط التنفيذ:** يُسجَّل كـ Exception هنا قبل البدء

---

## 15. Card Clipping Pattern — Background Clip vs Glow Escape

**المشكلة:** `overflow:hidden + border-radius` على card container يقص
كل الـ visual effects على العناصر الداخلية (box-shadow, filter:drop-shadow).

### النمط الرسمي للـ Cards التي تحتاج:
- قص الخلفية عند الـ border-radius ✅
- السماح لـ glow/shadow الداخلية بالخروج ✅

```css
/* ❌ المشكلة */
.card {
  overflow: hidden;        /* يقص الخلفية ✅ لكن يقص glow أيضاً ❌ */
  border-radius: 22px;
}

/* ✅ الحل المعتمد */
.card {
  overflow: visible;                  /* glow يخرج بحرية */
  border-radius: 22px;                /* بصري فقط */
  clip-path: inset(0 round 22px);    /* يقص الخلفية بنفس الشكل */
}
```

### لماذا يعمل:
- `clip-path` يقص الـ painted result للعنصر نفسه → gradient يبقى داخل الحدود ✅
- `clip-path` لا يقص filter output على الأبناء → glow يخرج بحرية ✅
- `overflow:visible` يمنع المتصفح من إنشاء clip region تلقائي ✅

### متى تستخدم هذا النمط:
- Card بـ gradient background + avatar/icon بـ glow
- Card بـ colored background + shadow effects داخلية
- أي container يحتاج border-radius clipping لكن لا يريد قص الـ children effects

### التوافق مع باقي properties:
```css
.card {
  overflow: visible;
  clip-path: inset(0 round 22px);
  isolation: isolate;    /* ✅ يعمل — لـ z-index stacking */
  border-radius: 22px;   /* ✅ يبقى للـ visual reference */
}
```

### تطبيق حالي في المشروع:
```css
/* S3 cv-head — gradient card + avatar glow */
body.s3 .cv-head {
  overflow: visible;
  clip-path: inset(0 round 22px);
  isolation: isolate;
  border-radius: 22px;
}
```

---

## 16. Flex Media Container Rule

أي عنصر يحتوي **صورة أو media** داخل flex container → **يجب** أن يكون له حجم ثابت.

```html
<!-- ❌ غلط — wrapper يتمدد ويكبر الصورة معه -->
<div style="position:relative; padding:10px">
  <img ...>
</div>

<!-- ✅ صح — حجم ثابت يمنع التمدد -->
<div style="position:relative; padding:10px; flex-shrink:0">
  <img ...>
</div>

<!-- أو بـ width ثابت -->
<div style="position:relative; padding:10px; width:102px">
  <img ...>
</div>
```

**القاعدة:**
```css
/* أي wrapper لـ avatar أو media داخل flex */
.avatar-wrapper,
.media-wrapper {
  flex-shrink: 0;  /* لا يتمدد */
  /* أو: width: Xpx (ثابت) */
}
```

**لماذا:** flex items بدون `flex-shrink:0` أو `width` ثابت تتمدد/تنكمش بناءً على المساحة المتاحة — خصوصاً عند وجود `overflow:visible` على الـ parent.

**ينطبق على:** avatar، thumbnail، icon wrapper، QR code، أي صورة داخل flex row.

---

## 17. Back Button Navigation Contract

### القواعد النهائية (غير قابلة للكسر)

```
replaceState  → مرة واحدة فقط عند bootstrap
pushState     → فقط لفتح UI layer (modal/panel/overlay/QR)
popstate      → UI close stack فقط (A→B→C)
/system       → خارج النظام بالكامل (لا قراءة ولا كتابة)
```

### popstate Contract

```javascript
window.addEventListener('popstate', function(e){
  // A: close overlay (QR/crop)
  // B: close modal
  // C: close panel
  // No UI open → STRICT NO-OP (browser handles naturally)
});
```

**ممنوع داخل popstate:**
```javascript
// ❌
history.pushState(...)     // re-anchor
history.replaceState(...)  // re-anchor
location.href = '...'      // redirect
if(e.state.profilePage)    // routing logic on marker
```

### profilePage:true = marker فقط

```javascript
// ✅ صح — marker للـ UI stack root
history.replaceState({profilePage:true}, '', location.href)
history.pushState({modal:'exp', profilePage:true}, '', location.href)

// ❌ غلط — routing logic على الـ marker
if(e.state && e.state.profilePage){ history.pushState(...) }
```

### Back Button Flow

```
UI مفتوح:   Back → popstate → close UI layer (no navigation)
لا UI:       Back → browser handles naturally (may leave profile — OK)
```

---

# D — COMPANY PROFILE SYSTEM

> قواعد خاصة بـ Company Profile System.
> أي تغيير يتطلب تحديث هذا الملف أولاً.

---

## [P0] 18. Data Ownership — Company Profile

### Schema Contract (ثابت — لا يتغير بدون تحديث Doctrine)

**profiles table** — بيانات مشتركة بين جميع user_types:
```
display_name      → users.full_name (source)
avatar_url        → شعار الشركة / صورة الموظف
location          → الموقع الجغرافي
website           → الموقع الإلكتروني
verification_status → is_verified
bio               → وصف مختصر
phone             → رقم الهاتف
```

**company_profiles table** — حصراً للشركات (user_type = 'co' | 'edu'):
```
cover_url         → صورة الغلاف
founded_year      → سنة التأسيس
company_size      → حجم الشركة
industry          → القطاع / المجال
description       → وصف مفصّل (يختلف عن bio)
headquarters      → المقر الرئيسي
contact_email     → بريد التواصل التجاري
company_type      → نوع الجهة (private/gov/edu/...)
verified_co       → توثيق الشركة كجهة
```

**القاعدة الصارمة:**
```
❌ ممنوع نقل أي field من profiles → company_profiles أو العكس
   بدون:
   1. تحديث هذا الملف أولاً
   2. كتابة migration script
   3. تحديث كل endpoints تتعامل مع هذا الـ field
   4. تحديث Frontend State Contract

❌ ممنوع إضافة company-specific field في profiles table
❌ ممنوع إضافة employee-specific field في company_profiles table
```

**جداول مستقبلية (Phase 3+):**
```
company_follows   → follower_id, company_id, created_at
company_ratings   → rater_id, company_id, score, comment, created_at
company_posts     → company_id, content, media_url, created_at
```

---

## [P0] 19. Company State Contract

### Single Source of Truth — Frontend

```javascript
// الـ State الرسمي الوحيد للـ Company Profile
window.companyState = {
  profile: {},      // من profiles table (bio, location, website, avatar_url)
  company: {},      // من company_profiles table (cover_url, founded_year, ...)
  jobs: [],         // من jobs table
  stats: {          // محسوب من DB — لا hardcoded
    jobs_count: 0,
    followers_count: 0,
    rating_avg: null,
    verified_count: 0
  },
  permissions: {    // من API response فقط
    is_owner: false,
    can_edit: false,
    can_post_jobs: false
  },
  viewMode: ""      // "owner" | "public-user" | "guest"
};
```

### قواعد الـ State (غير قابلة للكسر):

```
✅ UI يقرأ من companyState فقط
✅ API response يحدّث companyState فقط
✅ كل render function تأخذ data كـ parameter — لا تقرأ من DOM

❌ DOM ليس مصدر بيانات
❌ localStorage ليس مصدر بيانات (للـ jwt فقط — وليس بيانات الشركة)
❌ hidden inputs ليست مصدر بيانات
❌ dataset attributes ليست مصدر بيانات
❌ URL params ليست مصدر بيانات (hints فقط للـ routing)
❌ hardcoded values ممنوعة في أي render function
```

### State Update Flow:
```
API response
    ↓
_mergeCompanyState(data)   ← دالة واحدة تحدّث الـ state
    ↓
renderAll()                ← يقرأ من companyState فقط
    ↓
DOM                        ← output فقط، ليس input
```

### _mergeCompanyState Contract:
```javascript
function _mergeCompanyState(apiResponse) {
  // الدالة الوحيدة المسموح لها بتحديث companyState
  // كل شيء آخر يقرأ فقط
  companyState.profile     = apiResponse.profile     || {};
  companyState.company     = apiResponse.company     || {};
  companyState.jobs        = apiResponse.jobs        || [];
  companyState.stats       = apiResponse.stats       || {};
  companyState.permissions = apiResponse.permissions || {};
  companyState.viewMode    = apiResponse.viewer_type || "guest";
}
```

---

## [P0] 20. Company API Security Contract

### Authentication:
```
كل mutating request: Authorization: Bearer {jwt}
❌ X-User-Id header: ممنوع كـ auth mechanism
✅ verify_token: Depends(verify_token) على كل POST/PUT/DELETE
```

### Authorization per Endpoint:
```
GET  /company/profile/{id}   → Optional JWT | Public read
PUT  /company/profile/{id}   → JWT + token.user_id == id + user_type=='co'
POST /company/jobs           → JWT + user_type=='co'
PUT  /company/jobs/{job_id}  → JWT + token.user_id == jobs.company_id
DELETE /company/jobs/{job_id}→ JWT + token.user_id == jobs.company_id
POST /company/{id}/follow    → JWT + user_type=='emp'
```

### viewMode Response Contract:
```json
{
  "viewer_type": "owner | public-user | guest",
  "is_owner": true,
  "permissions": {
    "can_edit": true,
    "can_post_jobs": true,
    "can_follow": false
  }
}
```

---

## [P1] Controlled Exceptions — Company Profile

### Exception 04 — Hybrid Schema
- **القاعدة:** Rule #8 (Single Source of State)
- **السبب:** profiles تبقى للبيانات المشتركة؛ company_profiles للخاصة — backward compatible
- **الحد:** profiles لا تحتوي company-only fields بعد اليوم
- **أمان:** لا يوجد أثر أمني

### Exception 05 — X-User-Id في /company/jobs (مؤقت)
- **القاعدة:** Rule #1 (API Authorization)
- **السبب:** migration تدريجية
- **الحد:** يُزال في Phase 1 قبل أي deploy لـ production
- **أمان:** ⚠️ قابل للتزوير — مقبول في dev فقط

---

## Phase Roadmap — Company Profile

```
Phase 1 — Security Foundation (الحالي):
  ✅ JWT ownership validation
  ✅ API authorization (Depends verify_token)
  ✅ viewMode system من API
  ✅ CSS visibility system
  ✅ Bootstrap idempotency
  ✅ Duplicate request prevention

Phase 2 — Schema + Real Data:
  company_profiles table migration
  Real data: jobs_count, verified_count من DB
  Skeleton loader
  إخفاء hardcoded sections

Phase 3 — Social Features:
  company_follows table + endpoints
  company_ratings table + endpoints
  follow/unfollow real
  rating display real

Phase 4 — Polish:
  Back button (Rule #17)
  Render functions موحدة
  State deduplication

ممنوع الانتقال لـ Phase التالية قبل إغلاق الحالية واختبارها.
```

---

## [P0] 21. Company Frontend — Step 3 Implementation Contract

### Render Pipeline (ثابت — لا يتغير بدون Doctrine update)

```
initCompanyProfile()     ← __companyBooted guard
_applyLoadingState(true) ← CSS class فقط
loadData()               ← fetch + AbortController
_mergeCompanyState(data) ← ONLY state writer
_applyViewMode()         ← CSS class من viewMode
renderAll()              ← reads companyState only
  renderProfile()
  renderStats()
  renderJobs()
_applyLoadingState(false)
bindEvents()             ← بعد render فقط
```

### _mergeCompanyState() — Sole State Writer

```javascript
// الدالة الوحيدة المسموح لها بتعديل companyState
function _mergeCompanyState(apiResponse) {
  if (!apiResponse || apiResponse.status !== "success") return;
  companyState.profile     = apiResponse.profile     || {};
  companyState.company     = apiResponse.company     || {};
  companyState.jobs        = apiResponse.jobs        || [];
  companyState.stats       = apiResponse.stats       || companyState.stats;
  companyState.permissions = apiResponse.permissions || {};
  companyState.viewMode    = apiResponse.viewer_type || "guest";
}
```

### _applyViewMode() — CSS Setter Only

```javascript
function _applyViewMode() {
  const vm = companyState.viewMode;
  document.body.classList.remove('view-owner','public-view','view-guest');
  if      (vm === 'owner')       document.body.classList.add('view-owner');
  else if (vm === 'public-user') document.body.classList.add('public-view');
  else                           document.body.classList.add('view-guest');
}
// تُستدعى مرة واحدة فقط — لا من event handlers
```

### Event Boundary Contract

```
UI event → permission guard → API call → _mergeCompanyState → renderAll()
```

```javascript
// ✅ صح
function saveEdit() {
  if (!companyState.permissions.can_edit) return;
  fetch(PUT, JWT) → _mergeCompanyState → renderAll();
}

// ❌ غلط
function saveEdit() {
  _coData.name = input.value;  // state mutation outside contract
  document.getElementById('coName').textContent = _coData.name; // DOM as output
}
```

### Forbidden Patterns (Step 3+)

```javascript
❌ if (_isOwner) {}                          // local flag
❌ if (_user.user_type === 'co') {}          // localStorage
❌ el.style.display = is_owner ? '' : 'none' // JS visibility
❌ hardcoded: '47', '4.2', '12'             // fake stats
❌ _coData.x = value                         // old state object
❌ state mutation outside _mergeCompanyState
❌ DOM read for data decisions
```
