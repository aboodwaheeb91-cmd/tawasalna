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
| 22 | No Emoji in Professional Data | **P0** |
| 36 | Immediate UI Update Contract | **P1** |
| 37 | Controlled Inputs over Free Text | **P1** |
| 38 | No JSON in data-* Attributes | **P0** |
| 39 | Profile V2 Internal Back Navigation | **P1** |
| 40 | Clearable Profile Fields — Always Send Null | **P1** |
| 41 | Experience end_date Nullable Update | **P1** |
| 42 | About Tab Summary Cards | **P2** |

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

---

## [P0] 22. No Emoji in Professional Data

الرموز التعبيرية (emoji / pictographs) ممنوعة في جميع حقول النصوص المهنية.

### النطاق الحالي

| Scope | الحقول |
|-------|--------|
| Profile | `full_name`, `bio`, `headline`, `title`, `location`, `phone`, `website` |
| Experience | `title`, `company`, `location`, `description` |
| Education | `institution`, `degree`, `field`, `description` |
| Courses | `title`, `provider`, `description` |
| Skills | `skill` |
| Languages | `language` |
| Future | links (URL fields — not applicable), company profiles, jobs |

### التطبيق (طبقتان)

**Backend (الحماية الأساسية — `auth.py`):**
```python
# دالة مشتركة لجميع الحقول
validate_no_emoji(value, field)  # raises EmojiError(field)
```

**Frontend (UX — `profile-showcase.html` → window.hasEmoji):**
```javascript
if (window.hasEmoji(inputValue)) {
    showError('لا يسمح باستخدام الرموز التعبيرية');
    return;
}
```

### صيغة الـ Error Response (422)

```json
{
  "detail": {
    "status": "error",
    "message": "لا يسمح باستخدام الرموز التعبيرية داخل هذا الحقل",
    "field": "<field_name>"
  }
}
```

### القواعد الصارمة

```
✅ Backend يرفض أي قيمة تحتوي emoji في الحقول المحددة
✅ Frontend يمنع الإرسال قبل الوصول للـ API (UX فقط)
✅ validate_no_emoji تُستدعى قبل أي DB operation
❌ لا تعديل على البيانات الموجودة في DB بدون موافقة صريحة
❌ لا silent stripping — الرفض الصريح فقط
❌ لا bypass للـ backend validation عبر API مباشرة
```

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

---

## [P1] Controlled Exception 06 — Rating eligibility (Phase 2)

- **القاعدة الأصلية:** التقييم من موظف سابق فقط (verified employment via hired status)
- **الوضع المؤقت (Phase 2):** أي مستخدم user_type='emp' يستطيع التقييم
- **السبب:** قيد "موظف سابق" يحتاج job_applications مع status='hired' flow — غير جاهز في Phase 2
- **الحد:** Phase 3 يضيف القيد. الحقل permissions.can_rate يبقى محكوماً من backend فقط
- **الأمان:** لا أثر أمني — مجرد قيد business يُضيَّق لاحقاً
- **الإزالة:** عند بناء hired-status flow في Phase 3

## Phase 2 Schema — company tables (مثبّت)

```
company_profiles: user_id PK+FK (1:1، لا id مستقل)
  → company_type, founded_year, company_size, industry,
    description, headquarters, contact_email, cover_url, verified_co

company_follows: id PK، UNIQUE(company_id, follower_id)
  → idx_follows_company, idx_follows_follower

company_ratings: id PK، UNIQUE(company_id, rater_id), CHECK(score 1-5)
  → idx_ratings_company

كل company identity = users.id (متسق مع jobs.company_id).
البيانات المشتقة (followers_count, rating_avg) لا تُخزَّن — COUNT/AVG عند الطلب.
```

---

# E — PROFILE V2 SYSTEM


> نظام البروفايل الجديد يُبنى في `profile-showcase.html`.  
> `profile.html` القديم **Read-only** — لا يُلمس حتى يكتمل V2 ويُعتمد.  
> أي قرار في هذا القسم يسري على V2 ويصبح جزءاً من النظام النهائي.

---

## [P0] 22. Profile V2 — API Security Contract

### Endpoint
```
GET /profile/{user_id}
```

### Authentication
- JWT اختياري — يُرسَل في `Authorization: Bearer <token>`
- بدون JWT: `viewer_type = "guest"`

- مع JWT صاحب البروفايل: `viewer_type = "owner"`, `is_owner = true`
- مع JWT مستخدم آخر: `viewer_type = "public-user"`, `is_owner = false`

### Response Contract (additive — لا يُحذف أي field قديم)
```json
{
  "status": "success",
  "profile": { ... },
  "viewer_type": "owner | public-user | guest",
  "is_owner": true,
  "permissions": {
    "can_edit":    true,
    "can_follow":  false,
    "can_message": false,
    "can_save":    false,
    "can_report":  false
  }
}
```


### قواعد الأمان
- المصدر الوحيد لـ `viewer_type` هو الـ JWT المُحقَّق server-side
- `localStorage` لا يُستخدم لتحديد الصلاحيات — يُستخدم فقط لتمرير JWT
- أي mutation (PUT/POST/DELETE) يتحقق من ownership بشكل مستقل

---

## [P1] 23. Profile V2 — View Mode & Body Classes


### المصدر
`viewer_type` من API response فقط — لا من localStorage ولا URL.

### Body Classes
```
viewMode (API)   →  body CSS class   →  ما يراه المستخدم
────────────────────────────────────────────────────────
"owner"          →  view-owner       →  كامل + أدوات الإدارة
"public-user"    →  public-view      →  محتوى البروفايل فقط
"guest"          →  view-guest       →  محتوى + CTA تسجيل دخول
```

### تطبيق الـ Classes (frontend)
```javascript

var _vt = res.viewer_type || 'guest';
document.body.classList.remove('view-owner', 'public-view', 'view-guest');
if      (_vt === 'owner')       document.body.classList.add('view-owner');
else if (_vt === 'public-user') document.body.classList.add('public-view');
else                            document.body.classList.add('view-guest');
```

### إرسال JWT
```javascript
var _jwt = localStorage.getItem('tw_jwt') || '';
var _fetchOpts = _jwt ? { headers: { 'Authorization': 'Bearer ' + _jwt } } : {};
fetch('/profile/' + id, _fetchOpts)
```

### ممنوعات
```
❌ body class من localStorage
❌ body class من URL params
❌ إعادة قراءة الـ class من DOM لقرارات منطقية
❌ تغيير body class خارج نقطة التطبيق الواحدة
```

---

## [P1] 24. Profile V2 — Preview Mode


### الهدف
يتيح لصاحب البروفايل (owner) معاينة كيف يبدو بروفايله لمستخدم مسجل أو لزائر، بدون تغيير البيانات أو استدعاء API جديد.

### Preview Classes (تُضاف على body فوق view-owner)
```
body.view-owner                          → الوضع الطبيعي للمالك
body.view-owner.preview-public-user      → معاينة كمستخدم مسجل
body.view-owner.preview-guest            → معاينة كزائر
```

**القاعدة:** `view-owner` يبقى دائماً — preview تُضاف فوقه ولا تحذفه.

### زر العين — Preview Eye Button
- يظهر فقط عند `body.view-owner` (CSS فقط — لا JS)
- أيقونة: `eye-off` في الوضع العادي، `eye` (خضراء) عند تفعيل preview
- يفتح قائمة بثلاثة خيارات:
  1. معاينة كمستخدم مسجل → يضيف `preview-public-user`، يحذف `preview-guest`
  2. معاينة كزائر → يضيف `preview-guest`، يحذف `preview-public-user`
  3. إنهاء المعاينة → يحذف `preview-public-user` و`preview-guest`


### قواعد Preview Mode
```
✅ Preview = CSS class على body فقط
✅ البيانات لا تتغير
✅ لا API calls جديدة
✅ لا reload
✅ زر العين يبقى ظاهراً دائماً أثناء المعاينة
❌ preview لا تغيّر viewer_type
❌ preview لا تغيّر permissions
❌ preview لا تحفظ state في localStorage أو DB
```

---

## [P2] 25. Profile V2 — Owner-Only Elements


### المبدأ
كل عنصر مخصص لصاحب البروفايل فقط (أدوات تعديل/إدارة) يحمل class موحد:
```html
class="owner-only"
```

### إخفاء owner-only في Preview
```css
body.preview-public-user .owner-only,
body.preview-guest       .owner-only { display: none !important; }
```


### أمثلة على عناصر owner-only
- زر تعديل الملف الشخصي (scEditBtn)
- زر تعديل صورة البروفايل / الغلاف
- أزرار إضافة خبرة / شهادة / مهارة
- قوائم التعديل (ثلاث نقاط) على كل بند

### عناصر عامة — لا تحمل owner-only أبداً
```
الاسم، التخصص، النبذة، الأفاتار، الكفر
Stats، Tabs، QR، الموقع، العمر
زر متابعة، تواصل، الملف الكامل، رابط البروفايل
```

---

## [P1] 26. Profile V2 — Rendering Order

```

1. قراءة JWT من localStorage ('tw_jwt') — script level
2. fetch('/profile/{id}', {Authorization: Bearer jwt})
3. تطبيق body class من viewer_type (view-owner / public-view / view-guest)
4. عرض زر التعديل إذا owner
5. render البيانات (profile fields)
6. ربط event listeners (بعد render)
7. fetch مستقل للـ score (non-blocking)
```


**Steps 1-5:** sync بعد API response — لا flicker.  
**Step 7:** async — لا يُعطَّل الـ render.

**بعد حفظ Edit Modal:** re-fetch GET /profile/{id} → استدعاء renderProfile مجدداً.

---

## [P2] 27. Profession Icons System

### المصدر الوحيد للأيقونة
```
profession_categories.icon → API → profile.profession.icon → frontend
```

### تطبيق في profile-showcase.html
```javascript
var profIcon = (p.profession && p.profession.icon) ? p.profession.icon : 'briefcase';
```

### القواعد
```
✅ الأيقونة من backend فقط — لا تخمين من النص
✅ fallback = briefcase (أيقونة مهنية)
❌ ممنوع: user, user-round, person لتمثيل التخصص
```

### أي تخصص جديد في profession_categories يجب أن يملك icon رسمي.

---


## [P2] 28. Profession Selection System

### المبدأ
التخصص يُحدَّد بـ `profession_id` (FK → profession_categories) وليس بنص حر.

### مصدر قائمة التخصصات
```
GET /professions
← profession_categories WHERE is_active = TRUE
ORDER BY category_group, sort_order, name_ar
```

القائمة تُجلَب من API — لا hardcoded داخل frontend.

### تحديث التخصص
```
PUT /profile/{user_id}  { profession_id: <int> }
```

Backend يتحقق:
- `profession_id` موجود في `profession_categories`
- `is_active = TRUE`
- خطأ 400 إذا فشل التحقق

### عرض التخصص في V2
```
profession.icon + profession.name_ar      → إذا يوجد profession
briefcase + headline                      → fallback إذا لا يوجد
```

### headline
- يبقى موجوداً كحقل نصي اختياري / fallback
- ليس المصدر الرئيسي للتخصص في V2

### Edit Modal — flow
```
1. openModal() → fetch('/professions') → يبني <select> مع optgroup
2. pre-select من window._scProfile.profession.id
3. onSave() → PUT /profile/{id} + JWT
4. onSuccess() → closeModal → re-fetch GET /profile → renderProfile()
```

### ممنوعات
```
❌ قائمة التخصصات hardcoded في frontend
❌ التخصص كـ text input حر فقط
❌ تخمين profession icon من النص
❌ حفظ profession_id بدون التحقق من is_active
❌ تلمس profile.html القديم
```

---

## [P0] الممنوعات الصارمة — Profile V2

```
❌ تعديل profile.html (Read-only حتى اكتمال V2)
❌ viewer_type من localStorage
❌ is_owner من URL أو DOM
❌ preview class تحذف view-owner
❌ owner action بدون permission guard في JS
❌ mutation API بدون JWT
❌ hardcoded viewer state
❌ تخمين profession icon من النص

❌ profession list hardcoded في frontend
```

---

## [P2] 29. Profession Suggestion System

### المبدأ
التخصصات الرسمية فقط تأتي من `profession_categories`. أي تخصص غير موجود يذهب كاقتراح للمراجعة.

### الجدول
```sql
profession_suggestions (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    suggested_name_ar TEXT NOT NULL,
    suggested_name_en TEXT,
    normalized_name   TEXT,       -- lowercase + collapsed spaces لمنع التكرار
    status           VARCHAR(20) DEFAULT 'pending',
    reviewed_by      INTEGER REFERENCES users(id),
    reviewed_at      TIMESTAMPTZ,
    review_note      TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
)
```

### Status values
```
pending  → اقتراح جديد ينتظر المراجعة
approved → تمت الموافقة — يُنشأ تخصص رسمي في profession_categories
rejected → مرفوض
merged   → مدمج مع تخصص رسمي موجود
```

### Endpoint
```
POST /profession-suggestions
Auth: JWT مطلوب
Body: { suggested_name_ar: str, suggested_name_en?: str }

Rules:
- suggested_name_ar: 2–100 حرف
- normalized_name = lowercase + collapse spaces
- إذا pending موجود بنفس normalized_name لنفس المستخدم → return existing (no duplicate)
- لا يضاف إلى profession_categories تلقائياً
```

### Edit Modal Flow
```
1. select profession:
   ├── التخصصات الرسمية (من GET /professions)
   └── "تخصصي غير موجود في القائمة"

2. عند اختيار "غير موجود":
   → يظهر: input عربي (مطلوب) + input إنجليزي (اختياري)

3. عند الحفظ:
   أ. POST /profession-suggestions  → يحفظ الاقتراح
   ب. PUT /profile  → { profession_id: null, headline: suggested_name_ar }

4. عرض مؤقت في البروفايل:
   headline + briefcase icon (fallback path في Doctrine §27)
```

### Admin Review (Phase لاحق)
```
1. Admin يرى profession_suggestions حيث status='pending'
2. إذا approved: يضيف تخصص رسمي في profession_categories مع icon رسمي
3. يربط يدوياً المستخدمين المقترِحين بـ profession_id الجديد
4. يحدّث status → 'approved' مع reviewed_by و reviewed_at
```

### ممنوعات
```
❌ أي نص حر يدخل profession_categories مباشرة
❌ frontend يُنشئ profession رسمياً
❌ frontend يخمن profession icon
❌ profession_id يتغير تلقائياً بعد الاقتراح
❌ duplicate suggestions — normalized_name يمنعها
```

---

## [P1] 30. Profile V2 — Modular Architecture

> **هذا Refactor فقط — ليس Feature work.**
> لا تغيير في التصميم أو السلوك أو API contracts.
> أي ميزة جديدة تُبنى فوق هذا الهيكل — لا داخله.

### قاعدة المسؤولية الواحدة
كل ملف له مسؤولية واحدة فقط — لا يخلط logic مع rendering، ولا API مع state.

---

### هيكل الملفات

```
profile-showcase.html       ← HTML skeleton + <link>/<script> فقط. لا style. لا logic.

/home/user/tawasalna/ (يُخدَّم عبر /static/)
  profile-v2.css            ← كل CSS الخاص بـ Profile V2. لا logic.
  profile-v2.state.js       ← globals: _jwt, _fetchOpts, _scProfileId, _scProfileKey, _scUserId
  profile-v2.utils.js       ← esc, setText, toast, renderIcons, fitName, toggleBio, scTab
  profile-v2.api.js         ← getProfile(), getScore(), getProfessions(), updateProfile()
  profile-v2.qr.js          ← renderQR(el, showcaseUrl)
  profile-v2.render.js      ← renderProfile(), header wiring, initial fetch, eye button
  profile-v2.edit.js        ← Edit Modal IIFE (profession + bio)
  profile-v2.exp.js         ← Experience Module: add/edit/delete/reorder + three-dots menu
  profile-v2.cover.js       ← Cover Upload + Crop 6:1 (720×120 JPEG)
  profile-v2.avatar.js      ← Avatar Upload + Crop 1:1 (circular)
  profile-v2.select.js      ← Custom Select: dark-themed dropdown لكل modal selects
```

### ترتيب التحميل (ثابت — لا يتغير)

```html
<script src="/tw_shared.js"></script>
<script src="/static/profile-v2.state.js"></script>   <!-- no deps -->
<script src="/static/profile-v2.utils.js"></script>   <!-- no deps -->
<script src="/static/profile-v2.api.js"></script>     <!-- needs: state (_jwt, _fetchOpts) -->
<script src="/static/profile-v2.qr.js"></script>      <!-- no deps -->
<script src="/static/profile-v2.render.js"></script>  <!-- needs: state, utils, api, qr -->
<script src="/static/profile-v2.edit.js"></script>    <!-- needs: state, api, render -->
<script src="/static/profile-v2.exp.js"></script>     <!-- needs: state, api, render -->
<script src="/static/profile-v2.cover.js"></script>   <!-- needs: state, api -->
<script src="/static/profile-v2.avatar.js"></script>  <!-- needs: state, api -->
<script src="/static/profile-v2.select.js"></script>  <!-- LAST: reads all .ep-select -->
```

**القاعدة:** كل ملف يعتمد فقط على ملفات تُحمَّل قبله في الترتيب أعلاه.

---

### مسؤولية كل ملف وممنوعاته

| الملف | يحتوي | ممنوع فيه |
|-------|-------|----------|
| `profile-v2.css` | CSS كامل للصفحة | أي JS أو logic |
| `profile-v2.state.js` | globals مشتركة (`_jwt`, `_fetchOpts`, `_scProfileKey`, `_scUserId`) | DOM manipulation، fetch |
| `profile-v2.utils.js` | دوال مساعدة: `esc`, `setText`, `toast`, `renderIcons`, `fitName`, `scTab`, `toggleBio` | fetch مباشر، تعديل state |
| `profile-v2.api.js` | wrapper functions لكل fetch: `getProfile`, `getScore`, `getProfessions`, `updateProfile` | DOM rendering، window.* غير API |
| `profile-v2.qr.js` | `renderQR(el, showcaseUrl)` فقط | أي fetch غير QR external service |
| `profile-v2.render.js` | `renderProfile()`, header wiring، initial fetch، Eye Button IIFE | fetch مباشر (يستدعي api.js)، Edit Modal logic |
| `profile-v2.edit.js` | Edit Modal IIFE كاملاً | business permissions من localStorage، DOM manipulation خارج المودال |
| `profile-v2.exp.js` | Experience: add/edit/delete/reorder + three-dots menu IIFE | fetch مباشر (يستدعي api.js)، تعديل state خارج IIFE |
| `profile-v2.cover.js` | Cover upload + crop 6:1 IIFE | fetch مباشر (يستدعي api.js)، DOM خارج cover scope |
| `profile-v2.avatar.js` | Avatar upload + crop 1:1 IIFE | fetch مباشر (يستدعي api.js)، DOM خارج avatar scope |
| `profile-v2.select.js` | Custom Select IIFE: يستبدل كل `.ep-select` بـ dark dropdown | fetch، direct DOM mutations خارج scope |

---

### ممنوعات عامة (Profile V2 Modular)

```
❌ API داخل render functions مباشرة — استخدم api.js
❌ DOM rendering داخل api.js
❌ business permissions من localStorage
❌ تعديل profile.html القديم (Read-only حتى اكتمال V2)
❌ إضافة features جديدة داخل ملفات الـ refactor
❌ تغيير أسماء CSS classes
❌ تغيير API contracts أو endpoints
❌ خلط Modularization مع Feature development
```

### التحقق بعد كل Phase

```
✅ الصفحة تفتح بدون console errors
✅ البيانات تظهر (الاسم، التخصص، الأيقونة)
✅ QR يظهر
✅ Stats تظهر
✅ Tabs تعمل
✅ Toast يعمل
✅ GET /profile يعمل
✅ GET /score يعمل
✅ زر التعديل لا ينكسر
```

---

# F — DEPLOYMENT VERIFICATION CONTRACT

> **P0 — غير قابل للكسر.**
> لا يُعتبر أي تعديل "منتهياً" إلا بعد اجتياز جميع الخطوات أدناه بشكل صريح.
> ممنوع قول "تم" دون تقرير نشر كامل.

---

## [P0] 31. Deployment Verification Contract

### القاعدة الأساسية

```
committed + pushed + merged + deployed + live verified
```

كل خطوة واجبة. أي خطوة مفقودة = التعديل لم يصل للمستخدم.

---

### نموذج تقرير النشر الإلزامي

بعد أي تعديل، يجب إعطاء التقرير التالي بهذا الترتيب:

#### 1. الملفات المتغيرة
```
- اسم الملف: profile-showcase.html | النوع: frontend
- اسم الملف: server.py              | النوع: backend
- اسم الملف: ARCHITECTURE.md       | النوع: docs
```

#### 2. Git Status قبل الـ commit
```bash
git status --short
# يجب أن يظهر الملف المعدّل
```

#### 3. Commit
```
SHA:     c8913b9
Message: fix: وصف واضح لما تغيّر ولماذا
Files:   profile-showcase.html
```

#### 4. Push
```
تم push: نعم / لا
Branch:  claude/add-claude-documentation-giKNS
```

#### 5. Pull Request
```
رقم PR:      #33
رابط PR:     https://github.com/.../pull/33
يحتوي التعديل: نعم / لا
Conflicts:   لا يوجد / يوجد
أمام main:   نعم / لا
```

#### 6. Merge
```
تم merge: نعم / لا / في انتظار الموافقة
Merge SHA: (بعد الدمج)
```

#### 7. Deploy
```
بدأ deploy:  نعم / لا
انتهى deploy: نعم / لا
```
> **ملاحظة:** إذا المنصة (Heroku/Railway/...) تعمل auto-deploy عند merge،
> يكفي تأكيد merge + انتظار deploy. لا تقل "غالباً deployed".

#### 8. Live Verification
```bash
# اختبر الملفات المعدّلة مباشرة من الموقع الحي
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/profile-showcase?id=3
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/static/profile-v2.edit.js
# المتوقع: HTTP 200
```

#### 9. Version Marker
كل تعديل frontend مهم يجب أن يحمل version marker يمكن التحقق منه في المتصفح:

```js
// في profile-v2.state.js أو الملف المعدّل
window.PROFILE_SHOWCASE_VERSION = "edit-modal-fix-v1";
```

أو عبر query string في الـ script tags:
```html
<script src="/static/profile-v2.edit.js?v=edit-modal-fix-v1"></script>
```

---

### حالات التقرير الصريحة

| الحالة | ما يجب قوله |
|--------|------------|
| التعديل موجود محلياً فقط | **"التعديل محلي فقط ولم يُرفع بعد"** |
| تم push لكن لم يُدمج | **"التعديل مرفوع على PR فقط ولم يصل للموقع الحي"** |
| تم merge لكن لم ينتشر | **"merged لكن لم يتم deploy بعد"** |
| تم deploy | **"deployed — تأكيد حي: GET /file → 200"** |

---

### ممنوعات صريحة

```
❌ قول "تم" بدون commit SHA
❌ قول "تم رفع" بدون تأكيد branch و push output
❌ قول "deployed" بدون دليل من لوج أو HTTP 200 من الموقع الحي
❌ البدء باختبار من المتصفح قبل: committed + pushed + merged + deployed
❌ قول "غالباً وصل" أو "يجب أن يكون"
```

---

### سبب هذا القرار (2026-06-06)

تكررت مشكلة "قلت إنه تم لكن لم يصل للموقع":
- PR #32 (modularization): أُعلن عنه كـ "تم" قبل أن يُدمج فعلاً
- Fix زر القلم (`c8913b9`): أُعلن عنه كـ "تم" في جلسة سابقة لكن المستخدم لم يتأكد من وصوله

هذا العقد يمنع تكرار المشكلة.

---

## [P0] 34. Official Development Workflow (2026-06-07)

### الدومين الحي
```
https://tawasolna.com                                          ← الصحيح
❌ https://tawasalna.com                                       ← خاطئ — لا تستخدم
```

### روابط حية مرجعية
```
صفحة البروفايل:    https://tawasolna.com/profile.html?id=U0000db005c71b0
Profile Showcase:  https://tawasolna.com/profile-showcase?id=U0000db005c71b0
```
يُستخدم في كل live verification بعد deploy.

### دورة العمل الرسمية

```
1. Claude: كود + commit + push + PR + تحديث ARCHITECTURE.md
2. Claude: ملخص تقني + صيغة مختصرة (تم رفع / رقم PR / الحالة)
3. المستخدم: يقرر الـ merge
4. بعد merge + deploy: Claude يُشغّل live verification عبر curl
5. إذا احتاج الفحص متصفح أو بصري: المستخدم يختبر ويُرسل النتيجة
```

### Live Verification Routine (بعد كل deploy)

```bash
# 1. الصفحة الرئيسية
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/

# 2. Profile (الحالي)
curl -o /dev/null -sw "%{http_code}" "https://tawasolna.com/profile.html?id=U0000db005c71b0"

# 3. Static JS files
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/static/profile-v2.exp.js
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/static/profile-v2.render.js
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/static/profile-v2.css

# 4. التأكد من وجود function في الملف الحي
curl -s https://tawasolna.com/static/profile-v2.exp.js | grep -c "_expMenuToggle"
curl -s https://tawasolna.com/static/profile-v2.exp.js | grep -c "_expMoveUp"

# 5. API endpoint أساسي
curl -o /dev/null -sw "%{http_code}" https://tawasolna.com/stats
```
المتوقع: كل شيء يرجع 200.

### قواعد التوثيق التلقائي

| الحالة | الإجراء |
|--------|---------|
| Feature مكتملة + merged + لا اعتراض | توثيق كـ `Done / Stable` في ARCHITECTURE.md |
| Fix مهم + merged | توثيق كـ `Done / Stable` |
| مرفوع فقط (لم يُدمج) | توثيق كـ `Pending merge` |
| يوجد خطأ مفتوح | توثيق كـ `Needs testing` أو لا توثيق |
| المستخدم انتقل لموضوع جديد بدون اعتراض | = implicit approval → توثيق كـ Stable |

### تقسيم المسؤوليات (نهائي)

| المهمة | المسؤول |
|--------|---------|
| قراءة الكود + تعديل الملفات + commit + push + PR | Claude |
| تحديث ARCHITECTURE.md | Claude (تلقائي) |
| curl verification بعد deploy | Claude |
| merge إلى main | المستخدم فقط |
| deploy (إذا احتاج إجراء يدوي) | المستخدم |
| فحص المتصفح بصرياً | المستخدم |
| Supabase / Heroku / Railway / DNS / Gmail | المستخدم |

### إذا احتجت logs أو Console أو DB
Claude لا يطلب tokens أو secrets إلا لسبب ضروري محدد.
بدلاً من ذلك: Claude يُخبر المستخدم بالضبط ماذا يفحص ويرسل النتيجة.

```
مثال:
Claude: "افتح Heroku logs وابحث عن السطر الذي يحتوي [reorder_experience]"
Claude: "شغّل هذا الـ SQL في Supabase: SELECT sort_order FROM experience LIMIT 5"
Claude: "افتح Console في المتصفح وأرسل لي أي خطأ يظهر باللون الأحمر"
```

### ممنوعات صريحة (نهائي)

```
❌ merge إلى main بدون موافقة صريحة من المستخدم
❌ deploy مباشر بدون PR
❌ قول "تم" بدون commit SHA + push output
❌ قول "deployed" بدون curl 200 من tawasolna.com
❌ توثيق كـ Stable إذا يوجد خطأ مفتوح
❌ طلب tokens أو secrets بدون سبب ضروري محدد
```

---

# G — PERFORMANCE CONTRACTS

---

## [P1] 32. PUT /profile Fast Save Contract

### المبدأ

```
PUT /profile = حفظ فقط → response خفيف
GET /profile = قراءة كاملة → يُستدعى من frontend عند الحاجة
```

### ما يفعله PUT /profile
1. يتحقق من ownership (JWT)
2. يُنفِّذ UPDATE واحد فقط على جدول `profiles`
3. يرجع response خفيف فوراً

### Response الرسمي
```json
{
  "status": "success",
  "profile": { "id": ..., "updated": true, "<saved_fields>": "..." },
  "updated_fields": ["bio", "profession_id"]
}
```

**`profile` في الـ response:** يحتوي فقط الحقول التي تم حفظها + `id` + `updated`.
لا يُنفذ `get_full_profile` داخل PUT.

### Backward Compatibility
- `profile.html` يقرأ `d.profile.bio`, `d.profile.headline`, إلخ. بعد الحفظ.
  هذه الحقول موجودة في الـ response الخفيف لأنها نفس الحقول التي أُرسلت في الـ payload.
- باقي الصفحات تتجاهل `response.profile` — آمن تماماً.

### قاعدة Schema Migrations
```
❌ ALTER TABLE داخل update_profile (يعمل على كل PUT)
✅ ALTER TABLE داخل init_db فقط (يعمل مرة عند startup)
```

كل أعمدة `profiles` مضمونة في `init_db`:
`dob, country, city, avail, title, sections_order, custom_sections, profile_color, profile_style, profession_id`

### Timing Logging
كل PUT يطبع:
```
[update_profile] ✅ DB UPDATE success for user X, rows=1 — 0.123s
[update_profile] ⏱ total: 0.125s
[PUT /profile] ✅ Updated user X: ['bio', 'profession_id'] — 0.126s total
```

### الوفر المتوقع
| قبل | بعد |
|-----|-----|
| 10 ALTER TABLE + get_full_profile (10 queries) | UPDATE واحد |
| 6-7 ثواني | < 500ms |

---

## Profile V2 — Cover Module

### الملفات
| الملف | المسؤولية |
|-------|-----------|
| `profile-v2.cover.js` | كامل منطق cover upload + crop |
| `profile-v2.api.js` | `uploadCover()` — POST /upload/image bucket=covers |
| `profile-v2.css` | `.cv-edit-btn` + `.cv-crop-overlay` styles |
| `profile-showcase.html` | HTML: زر + file input + crop overlay |

### قاعدة البيانات
```sql
-- profiles table
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS cover_url TEXT;
```
الحقل: `cover_url TEXT` — يُخزن URL كامل من Supabase Storage.

### Bucket
```
bucket: "covers"
filename: "cover"
endpoint: POST /upload/image
```

### Crop
- نسبة العرض/الارتفاع: **6:1** (canvas 6:1 display + export 720×120)
- drag ✓  zoom ✓  touch ✓
- Export: JPEG quality 0.88 بدون clip (مستطيل)

### Owner-only
```css
body.view-owner .cv-edit-btn { display:flex; }
```
لا يظهر للزوار ولا في preview mode.

### Save Flow
```
1. owner يضغط زر تعديل الكفر
2. file input يفتح
3. validation: jpeg/png/webp فقط، max 5MB
4. crop overlay يظهر (6:1)
5. export canvas 720×120 JPEG
6. POST /upload/image → url
7. PUT /profile { cover_url: url }
8. تحديث DOM فوري + toast
9. re-fetch في الخلفية (silent)
```

### Fallback
إذا فشل upload: يُحفظ data_url مباشرة عبر PUT /profile.
إذا فشل PUT: toast خطأ، الكفر القديم يبقى كما هو.

### قاعدة Render
- `renderProfile()` يضع `cover_url` من API على `scCover.style.backgroundImage`
- إذا لا يوجد `cover_url`: CSS default (Cover.png) يبقى كما هو
- `aspect-ratio: 6/1` لا يتغير

### profile.html القديم
Read-only — لا يُعدَّل نهائياً.

---

## Profile V2 — Experience Module

### الملفات
| الملف | المسؤولية |
|-------|-----------|
| `profile-v2.exp.js` | كامل منطق add / edit / delete + confirm modal |
| `profile-v2.api.js` | `addExperience()`, `updateExperience()`, `deleteExperience()` |
| `profile-v2.render.js` | `_buildExpHTML(exp, isOwner)` — HTML builder مشترك |
| `profile-v2.css` | `.sc-section-add`, `.sc-item-exp`, `.sc-item-btn`, `.sc-item-btn-del` |
| `profile-showcase.html` | Experience Modal HTML (يعيد استخدام ep-* classes) |

### Endpoints
| Method | Path | وصف |
|--------|------|-----|
| POST | `/experience/{user_id}` | إضافة خبرة |
| PUT | `/experience/{exp_id}` | تعديل خبرة — يتحقق JWT + ownership |
| DELETE | `/experience/{exp_id}` | حذف خبرة — يتحقق JWT + ownership |

### Owner-only controls
```css
/* أزرار تعديل/حذف تظهر فقط للمالك عبر _vt === 'owner' في _buildExpHTML */
/* لا تُضاف عناصر للـ DOM للزوار */
```

### Add / Update / Delete Flow
```
1. owner يضغط "إضافة خبرة" أو قلم التعديل
2. modal يُفتح مع بيانات مملوءة مسبقاً (edit) أو فارغة (add)
3. validation: title + company مطلوبان
4. POST أو PUT → رد يحتوي experience object
5. _scProfile.experience يُحدَّث في الذاكرة فوراً
6. _reRenderExp() يعيد رسم الـ tab
7. toast نجاح + re-fetch بالخلفية

للحذف:
1. زر الحذف → scConfirm() modal (لا alert)
2. بعد تأكيد المستخدم → DELETE /experience/{id}
3. تحديث _scProfile.experience + إعادة رسم + toast
```

### Delete Confirmation
`window.scConfirm(msg, onYes)` — modal مبني ديناميكياً بـ JS بدون HTML مسبق.
لا `alert()`, لا `confirm()`.

### `_buildExpHTML`
`window._buildExpHTML(exp, isOwner)` — دالة مشتركة في render.js:
- render.js تستخدمها عند التحميل الأول
- exp.js تستخدمها عند `_reRenderExp()`
- isOwner = true → تُضاف زر ⋮ + قائمة الإجراءات
- isOwner = false → cards بدون أي أدوات

### profile.html القديم
Read-only — لا يُعدَّل نهائياً.

---

## Profile V2 — Experience Sort Order

**الحالة:** Done / Stable — PR #48

### الملفات المتغيرة
| الملف | التغيير |
|-------|---------|
| `auth.py` | migration: `sort_order INTEGER DEFAULT 0`، ORDER BY في `_get_extras`، `reorder_experience()` |
| `server.py` | `ExperienceReorderInput` model، `PUT /experience/reorder` endpoint |
| `profile-v2.api.js` | `reorderExperience(orderedIds)` — wrapper للـ endpoint |
| `profile-v2.exp.js` | `_expMoveUp`, `_expMoveDown`, `_saveExperienceOrder` |
| `profile-v2.render.js` | يمرر `i` و`n` لـ `_buildExpHTML` لتحديد disabled state |
| `profile-v2.css` | `.sc-item-btn-ord[disabled]` — opacity للأزرار المعطّلة |

### Endpoint
```
PUT /experience/reorder
Auth: JWT مطلوب
Body: { ordered_ids: [int, ...] }
```
**مهم:** يجب أن يكون هذا الـ endpoint قبل `PUT /experience/{exp_id}` في server.py لتجنب تفسير "reorder" كـ `exp_id`.

### Pattern المعتمد — Optimistic Update + Rollback
```
1. snapshot = list.slice()             ← نسخ الترتيب القديم قبل التغيير
2. swap في _scProfile.experience       ← تحديث state فوراً
3. _reRenderExp()                      ← إعادة رسم UI فوراً
4. PUT /experience/reorder             ← API في الخلفية
5a. نجاح → _bgRefetch() صامت
5b. فشل  → _scProfile.experience = snapshot → _reRenderExp() + toast
```

### Security
- Backend يتحقق من ownership لكل id قبل أي UPDATE
- إذا `len(rows) != len(ordered_ids)` → رفض كامل (لا partial update)

### Schema
```sql
ALTER TABLE experience ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;
-- SELECT ORDER BY sort_order ASC, id DESC
```

---

## Profile V2 — Experience Three-Dots Action Menu

**الحالة:** Done / Stable — PR #49 + #50

### المشكلة المحلولة
4 أزرار مستقلة (تعديل، حذف، رفع، إنزال) على كل بطاقة = ازدحام بصري يخرب شكل الكارد.

### الحل
زر ⋮ واحد لكل بطاقة → قائمة منسدلة بالإجراءات الأربعة.

### الملفات المتغيرة
| الملف | التغيير |
|-------|---------|
| `profile-v2.render.js` | استبدال 4 أزرار بـ `sc-exp-menu-wrap` + `sc-exp-menu` في `_buildExpHTML` |
| `profile-v2.exp.js` | `_expMenuToggle(btn)`, `_expMenuClose()`, document click listener |
| `profile-v2.css` | `.sc-exp-menu-wrap`, `.sc-exp-menu`, `.sc-exp-menu-item` styles |

### HTML Pattern
```html
<div class="sc-exp-menu-wrap owner-only">
  <button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)">⋮</button>
  <div class="sc-exp-menu">
    <button class="sc-exp-menu-item" data-exp-id="..." onclick="...تعديل...">تعديل</button>
    <button class="sc-exp-menu-item sc-exp-menu-move" [disabled?] ...>رفع للأعلى</button>
    <button class="sc-exp-menu-item sc-exp-menu-move" [disabled?] ...>إنزال للأسفل</button>
    <div class="sc-exp-menu-sep"></div>
    <button class="sc-exp-menu-item sc-exp-menu-del" ...>حذف</button>
  </div>
</div>
```

### Owner-only
- `owner-only` class على `sc-exp-menu-wrap` ← يختفي في preview mode تلقائياً
- لا يُضاف للـ DOM أصلاً للزوار (شرط `isOwner` في `_buildExpHTML`)

### Disabled State (محسوب في HTML مباشرة)
- رفع للأعلى: `disabled` عند `i === 0`
- إنزال للأسفل: `disabled` عند `i === n-1`

---

## [P2] 33. Dropdown Overflow Patterns — Two Official Approaches

**الحالة:** محدّث — PR #49+#50 (exp menu → position:absolute) + PR #53 (custom select → portal)

### النمط 1 — position:absolute (قائمة ⋮ داخل البطاقة)

يُستخدم بعد تحويل `.sc-main-card` من `overflow:hidden` إلى `overflow:visible`.

```css
/* parent: overflow:visible بدلاً من overflow:hidden */
.sc-main-card { overflow: visible; }
/* قص الـ cover فقط بـ border-radius مستقل */
.sc-cover { border-radius: 13px 13px 0 0; overflow: hidden; }

.sc-exp-menu {
  position: absolute;
  left: 0;
  top: calc(100% + 4px);
  min-width: 156px;
  z-index: 500;
}
.sc-exp-menu.open-up { top: auto; bottom: calc(100% + 4px); }
```

```javascript
window._expMenuToggle = function(btn){
  var menu = btn.nextElementSibling;
  if(!menu) return;
  var isOpen = menu.classList.contains('open');
  window._expMenuClose();
  if(!isOpen){
    var rect = btn.getBoundingClientRect();
    menu.classList.add('open');
    if(window.innerHeight - rect.bottom < 180) menu.classList.add('open-up');
  }
};
```

**متى:** الـ container يمكن تحويله لـ `overflow:visible` + القائمة صغيرة.

---

### النمط 2 — position:fixed Portal (Custom Select داخل Modal)

يُستخدم عندما الـ parent هو `overflow:auto` ولا يمكن تغييره (مثل `.ep-body`).

```javascript
// الـ dropdown يُلحق بـ document.body — خارج الـ modal DOM تماماً
document.body.appendChild(drop);

var rect = trg.getBoundingClientRect();
drop.style.position = 'fixed';
drop.style.left     = rect.left + 'px';
drop.style.top      = (rect.bottom + 3) + 'px';
drop.style.zIndex   = '600';  // فوق modal z-index:300
```

**لماذا portal:**
- `.ep-body { overflow-y:auto }` يقص `position:absolute` المرتبط بالـ modal
- portal على `document.body` يتموضع نسبةً للـ viewport مباشرة
- `z-index:600` يضمن ظهوره فوق modal (`z-index:300`)

**متى:** داخل modal أو scroll container — لا يمكن تغيير `overflow`.

---

### قاعدة الاختيار

| الحالة | النمط |
|--------|-------|
| parent يمكن `overflow:visible` | النمط 1 (position:absolute) |
| داخل modal / overflow:auto | النمط 2 (position:fixed portal) |

---

## Profile V2 — Avatar Module

### الملفات
| الملف | المسؤولية |
|-------|-----------|
| `profile-v2.avatar.js` | كامل منطق avatar upload + crop |
| `profile-v2.api.js` | `uploadAvatar()` — POST /upload/image bucket=avatars |
| `profile-v2.css` | `.av-edit-btn` + `.av-crop-overlay` styles |
| `profile-showcase.html` | HTML: زر + file input + crop overlay |

### قاعدة البيانات
```sql
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;
```

### Bucket
```
bucket: "avatars"  |  filename: "avatar"  |  endpoint: POST /upload/image
```

### Crop
- نسبة العرض/الارتفاع: **1:1** (دائرية في العرض — مستطيل في التصدير)
- drag ✓  zoom ✓  touch ✓  |  Export: JPEG quality 0.88

### Save Flow
```
owner يضغط زر الصورة → file input → validation (jpeg/png/webp ≤ 5MB)
→ crop overlay 1:1 → export canvas → POST /upload/image → url
→ PUT /profile { avatar_url } → تحديث DOM فوري + toast → re-fetch صامت
```

### Owner-only
```css
body.view-owner .av-edit-btn { display:flex; }
```

---

## Profile V2 — Edit Profile Modal

**الحالة:** Done / Stable

### الملف
`profile-v2.edit.js` — IIFE مستقل

### حقول المودال

| الحقل | النوع | الإرسال |
|-------|-------|---------|
| الاسم الأول | text input | `first_name` |
| الاسم الأوسط | text input | `middle_name` (اختياري) |
| الاسم الأخير | text input | `last_name` |
| تاريخ الميلاد | 3 selects (يوم/شهر/سنة) | `dob` بصيغة `YYYY-MM-DD` |
| الدولة | select (18 دولة عربية) | `country` |
| المدينة | select ديناميكي من `EP_CITIES` | `city` |
| الإتاحة | select | `avail` |
| التخصص | select مع optgroups + data-icon | `profession_id` |
| النبذة | textarea | `bio` |

### Name Architecture
```
PUT /profile { first_name, middle_name, last_name }
← backend يبني full_name تلقائياً
← applyLocalUpdate يبني full_name محلياً فوراً بدون re-fetch
← openModal يقرأ الأجزاء من window._scProfile مباشرة
```

### Profession Dropdown
```
1. openModal() → fetch('/professions')
2. بناء <optgroup> لكل category_group
3. كل <option> يحمل data-icon = profession.icon
4. Custom Select يقرأ data-icon ويعرض الأيقونة في الـ trigger
5. onSave() → profession_id في payload
```

### Confirmed Local Update Pattern
```
PUT → onSuccess():
  1. closeModal() + toast فوراً
  2. applyLocalUpdate(payload) → تحديث name/bio/age/profession في DOM فوراً
  3. getProfile() في الخلفية → renderProfile() صامت
```

### ممنوعات
```
❌ profession list hardcoded في edit.js
❌ full_name كـ text input واحد (يجب 3 أجزاء منفصلة)
❌ re-fetch قبل إغلاق المودال
❌ DOM manipulation خارج المودال من edit.js
```

---

## [P2] 35. Custom Select System — Profile V2

**الحالة:** Done / Stable — PR #53 + PR #54

### المشكلة المحلولة
Native `<select>` على الموبايل يفتح بستايل النظام (أبيض) خارج تصميم الموقع.

### Architecture
```
native <select class="ep-select">
  → مخفي: display:none + data-sc-sel="1"
  → .sc-sel wrapper (position:relative)
  → .sc-sel-trg button (visible trigger)
  → portal .sc-sel-drop → appended to document.body, position:fixed
```

### MutationObserver Per Select
```javascript
new MutationObserver(function(){
  _syncTrigger(wrap, native);
  // إذا dropdown مفتوح → أغلق وأعد فتحه بالـ options الجديدة
}).observe(native, {childList:true, subtree:true});
```
يُحدَّث trigger label تلقائياً عند تغيير options (cities، professions).

### Modal Open Observer
```javascript
// يتزامن جميع triggers 80ms بعد فتح .ep-overlay
// يلتقط select.value = x البرمجي الذي لا يُطلق change event
new MutationObserver(function(muts){
  if(ov.classList.contains('open')){ setTimeout(_syncAll, 80); }
}).observe(ov, {attributes:true, attributeFilter:['class']});
```

### Scroll Fix (PR #54)
```javascript
window.addEventListener('scroll', function(e){
  if(_cur && _cur.drop.contains(e.target)) return;  // لا تغلق scroll داخل dropdown
  _close();
}, true);
```

### z-index Stack
```
modal (.ep-overlay)     → z-index: 300
dropdown (.sc-sel-drop) → z-index: 600  ← فوق المودال
```

### Loading Order Rule
```
profile-v2.select.js يجب أن يُحمَّل LAST
← بعد edit.js (يبني DOB day/year options)
← بعد exp.js (يبني experience year options)
← window.scSelectInit() يعمل مرة عند load
```

### Supported Selects (11 total)
```
Edit Profile Modal:  epCountry, epCity, epAvail, epDobD, epDobM, epDobY, epProfession
Experience Modal:    exCountry, exCity, exStart, exEnd
```

### ممنوعات
```
❌ تحميل select.js قبل أي script يبني options
❌ إضافة native <select> جديد بدون class="ep-select"
❌ تغيير native.value بدون إطلاق change event أو فتح/إغلاق modal
```

---

# H — PROFILE V2 PHASE 1 MILESTONE

> **الحالة:** مكتمل ومستقر — 2026-06-07
> هذه المرحلة تُعدّ نقلة جوهرية في شكل وتجربة بروفايل تواصلنا.
> كل مكوّن اختُبر على الموقع الحي وأصبح جزءاً من النظام النهائي.

---

## ملخص المكوّنات المكتملة

| المكوّن | الملف | الحالة | PR |
|---------|-------|--------|----|
| Profile V2 Modularization (8 ملفات) | render.js + state.js + utils.js + api.js + qr.js | ✅ Stable | #32 |
| View Mode ثلاثي (owner/public-user/guest) | render.js | ✅ Stable | #32 |
| Owner-only elements (.owner-only + CSS) | profile-v2.css | ✅ Stable | #32 |
| Edit Profile Modal | profile-v2.edit.js | ✅ Stable | #32 |
| الاسم المفصل (first/middle/last) | edit.js | ✅ Stable | — |
| التخصص الرسمي (profession_id + icon) | edit.js + api.js | ✅ Stable | — |
| Avatar Upload + Crop 1:1 | profile-v2.avatar.js | ✅ Stable | — |
| Cover Upload + Crop 6:1 | profile-v2.cover.js | ✅ Stable | — |
| Experience Module (add/edit/delete) | profile-v2.exp.js | ✅ Stable | #44 |
| Experience Sort Order (reorder ↑↓) | exp.js + server.py | ✅ Stable | #48 |
| Three-dots Action Menu (⋮) | exp.js + render.js | ✅ Stable | #49+#50 |
| Custom Select System (11 selects) | profile-v2.select.js | ✅ Stable | #53 |
| Custom Select Scroll Fix | profile-v2.select.js | ✅ Stable | #54 |

---

## القرارات المعمارية المستقرة (Phase 1)

### Name Architecture
```
PUT /profile { first_name, middle_name, last_name }
backend يبني full_name ← frontend يعرض 3 حقول منفصلة
Confirmed Local Update يبني full_name محلياً من الأجزاء
```

### Profession Architecture
```
profession_id (FK → profession_categories)
icon من backend (profession.icon) ← fallback: briefcase
قائمة من GET /professions مع optgroups
data-icon attribute في <option> لدعم Custom Select
```

### Dropdown Position Architecture
```
قائمة ⋮ داخل البطاقة  →  position:absolute + overflow:visible على parent
Modal selects           →  position:fixed portal على document.body
```

### Confirmed Local Update Pattern
```
PUT /profile → onSuccess:
  1. closeModal() + toast فوراً
  2. applyLocalUpdate(payload) ← تحديث DOM بلا انتظار
  3. getProfile() ← re-fetch صامت في الخلفية
```

### Custom Select Load Order
```
select.js يُحمَّل LAST ← يحتاج جميع options مبنية مسبقاً
MutationObserver يتابع التغييرات ← لا حاجة لاستدعاء يدوي عند تغيير options
```

---

## ما تغيّر في المشروع (before → after Phase 1)

| قبل | بعد |
|-----|-----|
| profile.html كبير ومتشابك (147KB) | 12 ملف منفصل، كل له مسؤولية واحدة |
| لا تحكم في View Mode | نظام صلاحيات server-verified كامل |
| selects بستايل النظام (أبيض) | custom dark-themed selects موحدة |
| 4 أزرار على كل بطاقة خبرة | قائمة ⋮ واحدة نظيفة |
| لا ترتيب للخبرات | ترتيب بأزرار ↑↓ مع Optimistic Update + Rollback |
| لا رفع صور | upload + crop للـ avatar (1:1) والـ cover (6:1) |
| لا Edit Modal كامل | Edit Modal بـ 9 حقول + Confirmed Local Update |

---

> Phase 2 تُبنى فوق هذا الأساس — لا تعيد بناءه.

---

## [P1] 36. Immediate UI Update Contract

**الحالة:** مُطبَّق — PR #73 (2026-06-07)

### المبدأ

أي Modal يحفظ بيانات يجب أن يتبع 3 مراحل بالترتيب:

```
1. Save to DB    → PUT/POST إلى API
2. Local Update  → تحديث DOM فوراً بدون انتظار re-fetch (applyLocalUpdate)
3. Background    → getProfile() للـ full sync الصامت
```

**لا يكفي** تحديث الـ cache (`window._scProfile`) فقط دون تحديث الـ DOM — المستخدم لا يرى التغيير حتى يجري refresh.

---

### Mapping كامل — Edit Profile Modal

| الحقل | Input ID | Payload Key | DOM Element | في applyLocalUpdate |
|-------|---------|-------------|-------------|---------------------|
| الاسم الأول | epFirstName | first_name | scName | ✅ |
| الاسم الأوسط | epMidName | middle_name | scName | ✅ |
| الاسم الأخير | epLastName | last_name | scName | ✅ |
| تاريخ الميلاد | epDobY/M/D | dob | scAge | ✅ |
| البلد | epCountry | country | scLoc | ✅ (PR #73) |
| المدينة | epCity | city | scLoc | ✅ (PR #73) |
| التخصص | epProfession | profession_id | scTitle + icon | ✅ |
| النبذة (header) | epBio | bio | scBio | ✅ |
| النبذة (tab نبذة عني) | epBio | bio | scAboutText | ✅ (PR #73) |
| زر اقرأ المزيد | epBio | bio | scBioMore | ✅ (PR #73) |
| حالة التوظيف | epAvail | avail | — | cache فقط (لا عرض مخصص) |

---

### _buildLocText — دالة مشتركة للموقع

```javascript
// في profile-v2.render.js — متاحة عبر window._buildLocText
window._SC_COUNTRIES = { JO:'الأردن', SA:'السعودية', AE:'الإمارات', ... };
window._buildLocText = function(country, city, fallback){
  if(country && window._SC_COUNTRIES[country]){
    var name = window._SC_COUNTRIES[country];
    return city ? (name + ' - ' + city) : name;
  }
  return fallback || '';
};
```

تُستخدم في **مكانين** دائماً بنفس المنطق:
- `renderProfile()` — عند التحميل وبعد كل re-fetch
- `applyLocalUpdate()` — بعد الحفظ المباشر

---

### قاعدة إضافة Modal جديد

عند بناء أي Modal يحفظ بيانات، يجب تعبئة هذا الجدول قبل البناء:

| input id | payload key | DOM element | في applyLocalUpdate؟ |
|----------|-------------|-------------|----------------------|
| ... | ... | ... | ✅ / ❌ لا DOM ظاهر |

كل ❌ يعني إما إصلاح مطلوب أو توثيق سبب غياب العرض.

---

### الأخطاء الشائعة

```javascript
// ❌ cache فقط — المستخدم لا يرى التغيير
if(payload.country) window._scProfile.country = payload.country;

// ✅ cache + DOM معاً
if('country' in payload) window._scProfile.country = payload.country || '';
var _loc = document.getElementById('scLoc');
if(_loc && window._buildLocText){
  var _lt = window._buildLocText(_scProfile.country, _scProfile.city, _scProfile.location);
  _loc.innerHTML = _lt ? '... ' + esc(_lt) : '';
}

// ❌ bio يُحدَّث في header فقط — tab النبذة يبقى قديماً
bioEl.textContent = payload.bio;

// ✅ bio يُحدَّث في الأماكن الثلاثة
bioEl.textContent = payload.bio;
document.getElementById('scAboutText').textContent = payload.bio || 'لا توجد نبذة بعد';
requestAnimationFrame(function(){ /* re-check scBioMore overflow */ });
```

---

### ممنوعات

```
❌ تحديث الـ cache فقط إذا الحقل له عرض ظاهر في الـ DOM
❌ الاعتماد على getProfile() الخلفية للـ immediate feedback
❌ إضافة حقل جديد دون تحديث كل DOM elements المرتبطة به
❌ _buildLocText في render فقط بدون نفس المنطق في applyLocalUpdate
```

---

# E — PROFILE V2 MODULAR ARCHITECTURE

> `profile-showcase.html` — الصفحة العامة / صاحب البروفايل.
> كل قسم (section) لديه ملف JS مستقل.

---

## Script Load Order (ثابت — لا تغيّر)

```
state.js → utils.js → api.js → qr.js → render.js → edit.js →
exp.js → cover.js → avatar.js → select.js →
edu.js → courses.js → skills.js → langs.js → links.js
```

**القاعدة:** كل module يعتمد على state.js/utils.js/api.js بشكل ضمني.
`exp.js` يجب أن يحمّل قبل edu/courses/langs/links لأنه يعرّف `_expMenuToggle` / `_expMenuClose`.

---

## Globals المعتمدة (تُعيَّن من render.js بعد profile load)

| المتغير | المعيّن من | الغرض |
|---------|-----------|-------|
| `window._scProfile` | render.js | cache كامل للـ profile data |
| `window._scViewerType` | render.js | `'owner'` / `'public-user'` / `'guest'` |
| `window._scUserId` | render.js | numeric user ID للـ API calls |

**القاعدة:** Section modules تقرأ هذه الـ globals فقط بعد user interaction (click) — أي بعد اكتمال render.js.

---

## Pattern قياسي لكل Section Module

```javascript
// كل module يتبع هذا النمط
(function(){
  // 1. Guard — يوقف إذا الـ overlay غير موجودة
  var overlay = document.getElementById('XxxOverlay');
  if(!overlay) return;

  // 2. Save handler — يتحقق + emoji + API call + cache update + re-render
  saveBtn.onclick = function(){
    var val = fv('XxxField');
    if(!val){ toast('الحقل مطلوب'); return; }
    if(typeof hasEmoji==='function' && hasEmoji(val)){ toast('لا يسمح باستخدام الرموز التعبيرية'); return; }
    // ... API call
    // ... update window._scProfile cache
    // ... _reRenderXxx()
  };

  // 3. Build HTML — function نقية، تأخذ data + isOwner
  window._buildXxxHTML = function(data, isOwner){ /* ... */ };

  // 4. Re-render — يقرأ من window._scProfile
  window._reRenderXxx = function(){
    var el = document.getElementById('scXxxPane');
    if(!el) return;
    el.innerHTML = window._buildXxxHTML(window._scProfile.xxx, window._scViewerType === 'owner');
  };

  // 5. Public API
  window._xxxOpenAdd = function(){ /* open modal */ };
  window._xxxConfirmDelete = function(id){ /* confirm + delete + re-render */ };
})();
```

---

## Sections المكتملة (CRUD كامل)

| Section | Module | Add | Edit | Delete | Emoji FE | Emoji BE |
|---------|--------|-----|------|--------|----------|----------|
| Experience | profile-v2.exp.js | ✅ | ✅ | ✅ | ✅ | ✅ |
| Education | profile-v2.edu.js | ✅ | ✅ | ✅ | ✅ | ✅ |
| Courses | profile-v2.courses.js | ✅ | ✅ | ✅ | ✅ | ✅ |
| Skills | profile-v2.skills.js | ✅ | — | ✅ | ✅ | ✅ |
| Languages | profile-v2.langs.js | ✅ | — | ✅ | ✅ | ✅ |
| Links | profile-v2.links.js | ✅ | — | ✅ | N/A | N/A |

**ملاحظة Skills/Languages/Links:** لا edit (add يُحدّث ON CONFLICT — يعني add يعمل كـ upsert).
**ملاحظة Links:** حقول URL فقط — emoji غير قابل للتطبيق على URLs.

---

## Add Button — القاعدة الموحّدة

### Class المعتمد: `.sc-section-add`

```css
.sc-section-add {
  display:flex; align-items:center; gap:5px; margin-bottom:10px;
  padding:4px 10px; border-radius:20px; border:1px solid rgba(0,200,150,.35);
  background:rgba(0,200,150,.07); color:#00c896;
  font-family:inherit; font-size:.76rem; font-weight:700; cursor:pointer;
  transition:background .15s;
}
```

### قواعد ثابتة

```
✅ يظهر دائماً في أعلى القسم (قبل الـ list — addBtn + rows)
✅ يحمل class="sc-section-add owner-only" دائماً
✅ الأيقونة: + SVG مع class="ico-sm"
✅ يُخفى لغير المالك عبر CSS (.owner-only) + body:not(.view-owner)
❌ ممنوع return rows + addBtn (الزر يكون أسفل = خطأ)
❌ ممنوع تغيير الـ padding أو الـ border-radius أو اللون لأي قسم
❌ لا section له زر بحجم أو ستايل مختلف
```

### النمط المعتمد لكل section module

```javascript
window._buildXxxHTML = function(data, isOwner){
  var addBtn = isOwner
    ? '<button class="sc-section-add owner-only" onclick="window._xxxOpenAdd()">'
      + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
      + ' إضافة ...</button>'
    : '';
  if(!data || !data.length) return addBtn + '<div class="sc-empty">...</div>';
  var rows = '...';
  return addBtn + rows;  // ← الزر دائماً أعلى
};
```

---

# F — CONTROLLED INPUTS

---

## [P1] 37. Controlled Inputs over Free Text

> أي قيمة يمكن ضبطها بقائمة يجب أن تكون قائمة، والكتابة الحرة فقط للوصف أو النصوص الشخصية.

### القاعدة الأساسية

```
✅ استخدم <select class="ep-select"> لكل حقل ذي قيم متوقعة
✅ استخدم <textarea> أو <input type="text"> للوصف والنصوص الشخصية فقط
❌ ممنوع حقل نصي حر لأي قيمة يمكن تحديدها من قائمة
```

### جدول الحقول — الحالة المعتمدة

| Section | الحقل | النوع | ملاحظة |
|---------|-------|-------|---------|
| **Profile** | البلد | `<select>` ✅ | مرتبط بالمدينة |
| | المدينة | `<select>` ✅ | تتغير بتغيير البلد |
| | تاريخ الميلاد | `<select>` × 3 ✅ | يوم/شهر/سنة |
| | حالة التوظيف | `<select>` ✅ | متاح/غير متاح/فريلانس |
| | التخصص المهني | `<select>` ✅ | من endpoint |
| | النبذة | `<textarea>` ✅ | نص شخصي |
| **Experience** | سنة البداية | `<select>` ✅ | dynamic |
| | سنة الانتهاء | `<select>` ✅ | dynamic |
| | البلد | `<select>` ✅ | |
| | المدينة | `<select>` ✅ | conditional |
| | ما زلت أعمل | `checkbox` ✅ | |
| | المسمى / الشركة / الوصف | `<input>` / `<textarea>` ✅ | نصوص مخصصة |
| **Education** | الدرجة العلمية | `<select>` ✅ | ثانوية/دبلوم/بكالوريوس/ماجستير/دكتوراه/... |
| | سنة البداية | `<select>` ✅ | dynamic |
| | سنة التخرج | `<select>` ✅ | dynamic |
| | المؤسسة / التخصص / الوصف | `<input>` / `<textarea>` ✅ | نصوص مخصصة |
| **Courses** | سنة الإتمام | `<select>` ✅ | dynamic |
| | العنوان / الجهة / الوصف | `<input>` / `<textarea>` ✅ | نصوص مخصصة |
| | رابط الشهادة | `<input type="url">` ✅ | URL |
| **Skills** | اسم المهارة | `<input>` (مؤقت) | مُعدّ لـ suggestions لاحقاً |
| | المستوى | `<select>` ✅ | مبتدئ/متوسط/متقدم/خبير |
| **Languages** | اللغة | `<select>` ✅ | قائمة شاملة مع optgroups |
| | مستوى الإتقان | `<select>` ✅ | مبتدئ/متوسط/جيد/متقدم/محترف/اللغة الأم |
| **Links** | نوع الرابط | `<select>` ✅ | LinkedIn/GitHub/Website/... |
| | الرابط | `<input type="url">` ✅ | URL مع validation |

### قواعد صارمة

```
✅ كل <select> يستخدم class="ep-select" → يُكسى بـ custom select component
✅ <select> داخل .sc-modal-overlay يعمل تلقائياً عبر MutationObserver
✅ قيم المستوى موحّدة: مبتدئ/متوسط/جيد/متقدم/محترف/اللغة الأم (للغات)
❌ ممنوع استخدام <select> بدون class="ep-select"
❌ ممنوع تحويل حقول الوصف والنصوص الشخصية إلى قوائم
```

### Skills — خارطة طريق

```
الحالة الحالية: <input type="text"> — free text مؤقت
المرحلة القادمة: datalist مع suggestions من endpoint /skills/suggestions
المرحلة النهائية: combobox — select + custom input
```

### Custom Select + Modal Integration

```javascript
// select.js يُراقب كلا نوعي الـ overlays
var overlays = document.querySelectorAll('.ep-overlay, .sc-modal-overlay');
// عند .open → _syncAll() بعد 80ms → triggers تتزامن مع القيم المُعيَّنة بـ sv()
```

---

## Owner Detection

```
GET /profile/{user_id}  →  Authorization: Bearer {jwt}
  response.viewer_type  →  'owner' | 'public-user' | 'guest'
render.js               →  window._scViewerType = res.viewer_type
                        →  body.classList.toggle('view-owner', res.viewer_type === 'owner')
CSS: body.view-owner .owner-only { display: ... }
```

---

## Cache Invalidation Contract

بعد كل mutation (POST/PUT/DELETE) في section modules:
1. **Backend:** `_cache_del('profile:'+str(uid))` مباشرة في الـ endpoint
2. **Frontend:** تحديث `window._scProfile` يدوياً (no re-fetch) ثم `_reRenderXxx()`

هذا يضمن Rule #36 (Immediate UI Update) بدون انتظار API fetch.

---

## [P0] 38. No JSON in data-* Attributes — ID Only + State Lookup

**الحالة:** مُطبَّق — PR #79 (2026-06-10)

### المشكلة المكتشفة

`esc()` تُشفّر `<`, `>`, `&` فقط — **لا تُشفّر `"`**.

عند وضع `JSON.stringify(entry)` داخل attribute بـ double-quotes:
```html
data-edu-json="{"id":9,"institution":"University",...}"
```
البراوزر يقطع القيمة عند أول `"` داخل الـ JSON → `dataset.eduJson = "{"` فقط → `JSON.parse` يرمي SyntaxError → catch يُظهر "حدث خطأ".

**يحدث لكل entry دون استثناء** لأن JSON دائماً تحتوي `"` في keys والقيم.

---

### القاعدة الصارمة

```
❌ ممنوع:   data-xxx-json="' + esc(JSON.stringify(entry)) + '"
✅ المسموح: data-xxx-id="' + entry.id + '"  ثم lookup من state
```

---

### النمط الصحيح — مطابق للخبرات (المرجع الرسمي)

**زر التعديل في `_buildXxxHTML`:**
```javascript
// ❌ ممنوع
+'<button data-xxx-json="'+esc(JSON.stringify(e))+'" onclick="window._xxxOpenEdit(this.dataset.xxxJson)">'

// ✅ الصحيح
+'<button data-xxx-id="'+e.id+'" onclick="window._xxxOpenEdit(this.dataset.xxxId)">'
```

**دالة `_xxxOpenEdit`:**
```javascript
// ❌ ممنوع
window._xxxOpenEdit = function(json){
  try{ openEdit(JSON.parse(json)); } catch(e){ toast('حدث خطأ'); }
};

// ✅ الصحيح — نفس نمط الخبرات
window._xxxOpenEdit = function(itemId){
  var id   = parseInt(itemId, 10);
  var list = (window._scProfile && Array.isArray(window._scProfile.xxx))
    ? window._scProfile.xxx : [];
  var entry = null;
  for(var i = 0; i < list.length; i++){
    if(list[i].id === id){ entry = list[i]; break; }
  }
  if(!entry){ toast('لم يتم العثور على العنصر'); return; }
  openEdit(entry);
};
```

---

### لماذا ID Lookup أفضل

| | JSON في attribute | ID + state lookup |
|--|-------------------|-------------------|
| يكسر عند `"` في البيانات | ❌ دائماً | ✅ لا |
| يكسر عند `<` أو `>` في البيانات | ❌ | ✅ لا |
| يعتمد على encoding صحيح | ❌ هش | ✅ لا |
| يُمرر بيانات قديمة (stale) | ❌ ممكن | ✅ دائماً من الـ cache الحالي |
| أمان (XSS احتمال) | ❌ أعلى | ✅ أقل |

---

### Sections المتأثرة (تم الإصلاح)

| القسم | قبل | بعد |
|-------|-----|-----|
| Education | `data-edu-json` + JSON.parse ❌ | `data-edu-id` + cache lookup ✅ |
| Courses | `data-course-json` + JSON.parse ❌ | `data-course-id` + cache lookup ✅ |
| Experience | `data-exp-id` + cache lookup ✅ | بدون تغيير — المرجع الصحيح |

**Skills / Languages / Links:** لا edit buttons → لا تأثير.

---

### ممنوعات صارمة

```
❌ JSON.stringify في أي data-* attribute
❌ JSON.parse من dataset في أي edit handler
❌ استخدام esc() كبديل لـ JSON escaping في attributes
❌ وضع أي كائن مُسلسَل في HTML attribute
✅ الوحيد المسموح: data-id = رقم صحيح، ثم lookup من window._scProfile
```

---

## [P1] 39. Profile V2 Internal Back Navigation

### المشكلة

على Android يضغط المستخدم زر الرجوع الصلب (hardware back button) أثناء وجود modal مفتوح ← المتصفح يرجع للصفحة السابقة كلياً بدلاً من إغلاق الـ modal.

---

### الحل — History Stack داخلي

**الملف المسؤول:** `profile-v2.history.js` — يُحمَّل **آخر** script في الصفحة.

#### مبدأ العمل

```
تحميل الصفحة      → replaceState({ scLayer: 'profile-base' })
فتح أي طبقة       → pushState({ scLayer: 'layer-name' })    ← _pushed = true
ضغط Back          → popstate fires → close topmost → re-push إذا بقيت طبقات
لا شيء مفتوح      → back ينتقل للصفحة السابقة طبيعياً
```

#### `_pushed` Flag

- يمنع تكرار `pushState` لنفس مجموعة الطبقات المفتوحة.
- يُعاد ضبطه على `false` عند popstate وعند إغلاق آخر طبقة.

---

### أولوية إغلاق الطبقات (من الأعلى للأسفل)

| # | الطبقة | آلية الكشف | آلية الإغلاق |
|---|--------|------------|--------------|
| 1 | Three-dot menus | `.sc-exp-menu.open` | `window._expMenuClose()` |
| 2 | Custom select dropdown | `.sc-sel-drop-open` | `window.scSelectClose()` |
| 3 | Avatar crop | `#avCropOverlay.open` | `#avCropCancelBtn.click()` |
| 4 | Cover crop | `#cvCropOverlay.open` | `#cvCropCancelBtn.click()` |
| 5 | Experience modal | `#exOverlay.open` | `#exClose.click()` |
| 6 | Edit Profile modal | `#epOverlay.open` | `#epClose.click()` |
| 7 | Education modal | `#eduOverlay.open` | `#eduClose.click()` |
| 8 | Courses modal | `#courseOverlay.open` | `#courseClose.click()` |
| 9 | Skills modal | `#skillOverlay.open` | `#skillClose.click()` |
| 10 | Languages modal | `#langOverlay.open` | `#langClose.click()` |
| 11 | Links modal | `#linkOverlay.open` | `#linkClose.click()` |

---

### نقاط التكامل (modules أخرى تستدعي history.js)

| الملف | المكان | ما يُضاف |
|-------|--------|---------|
| `profile-v2.exp.js` | `_expMenuToggle` عند فتح القائمة | `if(window._scPushHistory) window._scPushHistory('menu')` |
| `profile-v2.select.js` | `_openFor` بعد تعيين `_cur` | `if(window._scPushHistory) window._scPushHistory('select')` |
| `profile-v2.select.js` | نهاية IIFE | `window.scSelectClose = _close` |

الـ static overlays (avCrop, cvCrop, exOverlay, epOverlay, eduOverlay, courseOverlay, skillOverlay, langOverlay, linkOverlay) تُراقَب تلقائياً بـ **MutationObserver** داخل `history.js`.

---

### ممنوعات

```
❌ لا تستدعي history.back() مباشرة من أي modal close handler
❌ لا تضيف history.pushState من أكثر من مكان لنفس الطبقة (يكفي history.js)
❌ لا تحمّل history.js قبل باقي modules — يجب أن يكون آخر script
✅ أي طبقة جديدة: أضف entry في _layers() داخل history.js فقط
```

---

### إضافة طبقة جديدة

```javascript
// في profile-v2.history.js — داخل دالة _layers()
{
  test:  function(){ var el=document.getElementById('myNewOverlay'); return !!(el && el.classList.contains('open')); },
  close: function(){
    var btn=document.getElementById('myNewCloseBtn');
    if(btn) btn.click();
    else { var el=document.getElementById('myNewOverlay'); if(el) el.classList.remove('open'); }
  }
},
```

إذا كانت الطبقة dynamic (كـ three-dot menus) وليس لها ID ثابت: أضف استدعاء `window._scPushHistory('layerName')` داخل دالة الفتح في الـ module المسؤول.

---

## [P1] 40. Clearable Profile Fields — Always Send Null

### المشكلة

حقول Profile Core كـ `avail`, `country`, `city`, `dob` لا يمكن مسحها بعد ضبطها، لأن الـ frontend يستخدم `if(value) payload.field = value` مما يمنع إرسال null.

### القاعدة

```
❌ ممنوع:   if(avail) payload.avail = avail;
✅ المسموح: payload.avail = avail || null;
```

الـ backend يجب أن يقبل null لهذه الحقول ويحولها إلى SQL NULL.

### الحقول المؤهلة للمسح (clearable)

| الحقل | Frontend | Backend |
|-------|---------|---------|
| `avail` | `payload.avail = avail || null` | `_clearable = {"dob","country","city","avail"}` |
| `country` | `payload.country = country || null` | نفس المجموعة |
| `city` | `payload.city = city || null` | نفس المجموعة |
| `dob` | `payload.dob = dob || null` | نفس المجموعة |

### `applyLocalUpdate` عند المسح

عند مسح `dob = null`: يجب إخفاء عنصر `scAge` (`style.display = 'none'`).
عند مسح `country`/`city`: `_buildLocText` يعيد `''` تلقائياً عند استقبال null لأن `_p.country || ''`.

---

## [P1] 41. Experience end_date Nullable Update

### المشكلة

`update_experience()` في auth.py يستخدم `data[k] is not None` للفلترة، مما يمنع مسح `end_date` عند تعديل الخبرة (إلا عند `is_current=True`).

### السبب

```python
# ❌ قبل الإصلاح — يفلتر end_date=None
fields = {k: data[k] for k in allowed if k in data and data[k] is not None}

# ✅ بعد الإصلاح — يسمح بـ end_date=None
_nullable = {"end_date"}
fields = {k: data[k] for k in allowed if k in data and (data[k] is not None or k in _nullable)}
```

### القاعدة

أي حقل يمثل "نهاية" (end_date, end_year) يجب أن يكون قابلاً للإرسال كـ null لمسحه.

### نمط `_nullable` / `_clearable`

```python
# في update_experience:
_nullable = {"end_date"}

# في update_profile:
_clearable = {"dob", "country", "city", "avail"}

# كلاهما:
fields = {k: data[k] for k in allowed if k in data and (data[k] is not None or k in _nullable_or_clearable)}
```

---

## Back Navigation — `_scHistoryReset` Pattern

### المشكلة

الطبقات الديناميكية (three-dot menus, custom select) تُبقي `_pushed = true` بعد إغلاقها العادي (بدون Back button). هذا يمنع المودالات التالية من الحصول على `pushState` وحماية Back button.

### الإصلاح

```javascript
// في history.js — دالة reset مُصدَّرة
window._scHistoryReset = function(){
    if(!_hasOpenLayer()) _pushed = false;
};

// في _expMenuClose (exp.js):
window._expMenuClose = function(){
    // ... close menus ...
    if(window._scHistoryReset) window._scHistoryReset();
};

// في _close() (select.js):
function _close(){
    // ... close dropdown ...
    if(window._scHistoryReset) window._scHistoryReset();
}
```

### متى يجب استدعاء `_scHistoryReset`؟

```
✅ في نهاية دالة إغلاق كل طبقة ديناميكية
✅ بعد _expMenuClose
✅ بعد _close في select.js
❌ لا تستدعيه من داخل popstate handler (يُعاد ضبطه تلقائياً)
❌ لا تستدعيه عند إغلاق static overlays (MutationObserver يتولى ذلك)
```

---

## [P1] 42. City/Country Linked Integrity — Frontend-Only Constraint

### الحالة الحالية

العلاقة بين حقلَي `country` و `city` في Edit Profile Modal محمية **من جهة الـ frontend فقط**.

| الضمانة | الآلية | الملف |
|---------|--------|-------|
| city options مرتبطة دائماً بـ country | `EP_CITIES[countryCode]` — بيانات مرجعية ثابتة | `profile-v2.edit.js` |
| changing country يُصفّر city | `onchange="epLoadCities()"` بدون args → لا pre-selection | `profile-showcase.html` |
| invalid city تُمنع هيكلياً | `epCity` هو `<select>` مغلق — لا free text input | `profile-showcase.html` |
| mismatch في prefill يُصلَح تلقائياً | `epLoadCities(p.city)` لا تُطابق مدينة خارج قائمة البلد → placeholder | `profile-v2.edit.js` |

### ما لا يوجد حالياً

```
❌ لا يوجد جدول DB مرجعي للمدن والدول
❌ backend لا يتحقق من صحة العلاقة city ↔ country
❌ هجوم API مباشر (بدون واجهة) يمكنه حفظ city غير صالحة
```

### لماذا مقبول حالياً

- `epCity` هو `<select>` لا `<input type="text">` — المستخدم العادي لا يستطيع تجاوزه
- تطبيقات المستخدمين العاديين لا تتضمن هجمات API مباشرة
- `EP_CITIES` يغطي 18 دولة عربية — مصدر موثوق وكافٍ

### مسار الحماية الكاملة (مستقبلاً)

لو احتجنا حماية backend كاملة:

```python
# 1. إضافة جدول DB
CREATE TABLE city_country_ref (
    country_code TEXT NOT NULL,
    city_name    TEXT NOT NULL,
    PRIMARY KEY (country_code, city_name)
);

# 2. validation في update_profile
if data.get('city') and data.get('country'):
    valid = conn.run(
        "SELECT 1 FROM city_country_ref WHERE country_code=:cc AND city_name=:c",
        cc=data['country'], c=data['city']
    )
    if not valid:
        raise ValueError("المدينة غير صالحة للدولة المختارة")
```

### القاعدة

> عند إضافة أي حقل مرتبط بـ `country` أو `city`:
> 1. استخدم `<select>` مغلقاً — لا `<input type="text">` حراً
> 2. اجعل `onchange` على `country` يُعيد بناء القائمة المرتبطة
> 3. اجعل القائمة المرتبطة تُصفَّر (بدون pre-selection) عند تغيير `country`
> 4. لا تثق بـ `city` القادمة من DB بدون تحقق — استخدم `epLoadCities(p.city)` الذي يُصلح المشكلة تلقائياً

---

## [P1] 43. Skill Catalog & Searchable Skills System

### المشكلة التي تحلها هذه القاعدة

المهارات المخزنة كنص حر (free text) تجعل البحث المستقبلي مستحيلاً:
- `Java` / `java` / `JAVA` / `جافا` = 4 قيم مختلفة في DB
- الشركات لا تستطيع البحث عن موظفين عندهم "Java" بشكل موثوق
- الإحصائيات تعطي أرقاماً خاطئة
- AI matching لا يستطيع ربط المهارات المتشابهة

**القاعدة:** المهارات يجب أن تكون normalized وقابلة للبحث عبر `skill_id` أو `slug`، وليس فقط نص حر، لأن الشركات والأدمن سيحتاجون مستقبلاً للبحث عن المستخدمين حسب المهارة.

---

### المعمارية الحالية (Phase 1 — مكتملة)

| الطبقة | الآلية |
|--------|--------|
| **Catalog** | `SKILL_CATALOG` array مدمج في `profile-v2.skills.js` — 300+ مهارة رسمية عبر 20 مجالاً |
| **Normalization** | `_normalize(raw)` → يُرجع `name_en` القياسي إذا طابق أي entry في الـ catalog |
| **Autocomplete** | عند الكتابة يبحث في `name_en + name_ar + slug + keywords` → يعرض 8 اقتراحات |
| **Dedup** | Case-insensitive check في frontend + UNIQUE(user_id, skill) في DB |
| **Validation** | min 2 chars + must-contain-letters + no emoji + no profanity + no skill+level combo |
| **Display** | `name` chip + `level` badge + `مخصصة` badge للمهارات غير الرسمية — منفصلة كلها |
| **Official check** | `_isOfficial(name)` → يطابق الكتالوج → يضيف CSS class `sc-skill-chip-custom` للمهارات المخصصة |

### Schema الحالي (Phase 1)

```sql
user_skills:
  id        SERIAL PRIMARY KEY
  user_id   INTEGER FK → users(id)
  skill     TEXT NOT NULL          -- canonical name_en من الـ catalog
  level     TEXT                   -- مبتدئ / متوسط / جيد / متقدم / محترف
  UNIQUE (user_id, skill)          -- يمنع التكرار الدقيق
```

### Phase 2 — المطلوب لاحقاً (DB migration)

```sql
-- كتالوج رسمي
CREATE TABLE skills_catalog (
    id            SERIAL PRIMARY KEY,
    name_en       TEXT NOT NULL,
    name_ar       TEXT NOT NULL,
    slug          TEXT UNIQUE NOT NULL,
    keywords      TEXT,
    category      TEXT,
    is_active     BOOLEAN DEFAULT TRUE
);

-- تحديث user_skills
ALTER TABLE user_skills ADD COLUMN skill_id INTEGER REFERENCES skills_catalog(id);
ALTER TABLE user_skills ADD COLUMN custom_name TEXT;
-- skill_id NOT NULL للمهارات القياسية، custom_name للمهارات المخصصة pending review

-- Index للبحث السريع
CREATE INDEX ON user_skills (skill_id);
```

**متى ننتقل لـ Phase 2؟**
عندما نحتاج:
- الشركات تبحث بـ `skill_id` (ليس نصاً)
- Admin analytics بـ slug
- AI matching normalized
- Pending review للمهارات المخصصة

### Validation Rules (موثّقة للـ frontend والـ backend)

| القاعدة | Frontend | Backend |
|---------|---------|---------|
| اسم فارغ | ✅ | ✅ |
| أقل من حرفين | ✅ | ✅ |
| لا يحتوي حروف | ✅ | ✅ (`[a-zA-Z؀-ۿ]`) |
| emoji + profanity | ✅ (`_scCheckProfessional`) | ✅ (`validate_professional_text`) |
| skill+level مدموجان | ✅ (LEVEL_WORDS list) | ❌ (frontend فقط) |
| تكرار case-insensitive | ✅ | ❌ (UNIQUE case-sensitive فقط) |
| Normalization | ✅ (`_normalize`) | ❌ (frontend فقط) |

### قائمة المستويات الرسمية (ثابتة — لا تغيّرها بدون تحديث الـ DB)

```
مبتدئ → #9ca3af
متوسط → #60a5fa
جيد    → #a78bfa
متقدم → #00c896
محترف → #fbbf24
```

### Custom Skills — مهارات مخصصة

الكتالوج الرسمي قابل للتوسع، **ليس حصرياً**. المستخدم يستطيع إضافة مهارة غير موجودة في الكتالوج:

- يُضاف الـ chip بـ CSS class `sc-skill-chip-custom` + badge "مخصصة" (بنفسجي)
- `_isOfficial(name)` يُحدد هل المهارة رسمية أم مخصصة
- في Phase 2: Admin Skill Review workflow — المهارات المخصصة تمر بـ pending review ويمكن دمجها بالكتالوج الرسمي أو رفضها

### Phase 2 — Admin Skill Review (لاحقاً)

```
Custom Skill → pending_review → Admin reviews → approve (add to catalog) | reject
```

### ممنوعات

```
❌ لا تخزن المهارة كـ "Java متقدم" نص واحد — skill وlevel حقلان منفصلان
❌ لا تستخدم free text input بدون autocomplete من catalog
❌ لا تجلب اقتراحات من API خارجي — الـ catalog داخلي فقط
❌ لا تسمح بمستوى خارج القائمة الرسمية الخمسة
❌ لا تعتمد على UNIQUE(user_id, skill) وحده للـ case-insensitive dedup — الـ frontend مسؤول عن ذلك في Phase 1
```

---

## [P1] 44. Professional Content Validation

### المشكلة التي تحلها هذه القاعدة

حقول النصوص في ملفات المستخدمين (الاسم، السيرة، الخبرة، التعليم، المهارات...) يجب حمايتها من:
- الرموز التعبيرية (emoji) — تُشوّه المظهر المهني
- الكلمات البذيئة والمحتوى الجنسي/الإباحي — لا يليق بمنصة توظيف

**القاعدة:** كل حقل نصي مرئي (user-generated content) يجب أن يمر بـ `validate_professional_text()` قبل الحفظ في DB.

---

### المعمارية

#### Backend — `auth.py`

```python
# هرمية الاستثناءات
ContentValidationError(ValueError)     # base class — field + message
├── EmojiError(ContentValidationError) # رموز تعبيرية — "لا يسمح باستخدام الرموز التعبيرية"
└── ProfanityError(ContentValidationError) # محتوى غير لائق — "لا يسمح باستخدام كلمات غير لائقة"

# الدالة الموحدة
validate_professional_text(value, field) → None
  يستدعي: validate_no_emoji(value, field)  # emoji check
           + فحص _PROFANITY frozenset       # profanity check
```

> **تحديث (2026-06-12 → follow-up):** توسيع القائمتين `_PROFANITY` / `_BAD` إلى ~80 مصطلحاً، وتحسين normalization شامل: إزالة التشكيل العربي، التطويل، توحيد الهمزات وألف المقصورة والتاء المربوطة، leet-speak (`5→s`), إزالة رموز التمويه بين الحروف (`f.u.c.k`, `sh!t`, ...)، وpre-normalization للقائمة نفسها. القائمة التفصيلية داخل الكود فقط ولا تُنشر.

**قائمة الحقول المحمية (backend):**

| Endpoint | الحقول |
|----------|--------|
| `PUT /profile/{user_id}` | full_name, first_name, middle_name, last_name, bio, headline, title, location, phone, website |
| `POST /experience/{user_id}` | title, company, location, description |
| `PUT /experience/{exp_id}` | title, company, location, description |
| `POST /education/{user_id}` | institution, degree, field, description |
| `PUT /education/{edu_id}` | institution, degree, field, description |
| `POST /course/{user_id}` | title, provider, description |
| `PUT /course/{course_id}` | title, provider, description |
| `POST /skills/{user_id}` | skill |
| `POST /langs/{user_id}` | language |

#### Frontend — `profile-v2.utils.js`

```javascript
window._scCheckProfessional(text)
  // Returns: null (clean) | string (error message)
  // Mirrors backend: emoji check + same _PROFANITY wordlist
  // Used by: profile-v2.edit.js, profile-v2.exp.js, profile-v2.edu.js,
  //          profile-v2.courses.js, profile-v2.langs.js, profile-v2.skills.js
```

رسالة الخطأ الموحدة:
```
"لا يسمح باستخدام كلمات غير لائقة أو غير مهنية داخل هذا الحقل"
```

---

### ضوابط القائمة

- **قائمة محافظة** — فقط الكلمات الفاحشة الصريحة التي ليس لها استخدام مهني/طبي مشروع
- **لا false positives** على المصطلحات الطبية والمهنية
- **العربية والإنجليزية** — بديل الأحرف الشائع (`0→o`, `@→a`...) و تكرار الحروف (`fuuuck`)
- **word-level check** للكلمات القصيرة + **substring check** للكلمات الطويلة (≥5 أحرف)

---

### ممنوعات

```
❌ لا تستخدم hasEmoji وحده — استخدم _scCheckProfessional في الـ frontend
❌ لا تستخدم validate_no_emoji وحده — استخدم validate_professional_text في الـ backend
❌ لا تُضيف كلمات طبية أو مهنية مشروعة للقائمة (قضيب، ثدي، جنس في سياق تعليمي...)
❌ لا تُضيف كلمات قصيرة ذات استخدام مزدوج (ass ← assistant, cock ← cock-up)
```

---

## Hybrid Skill Icon System

> **نظام الأيقونات للمهارات** — توثيق الهندسة والقانونيات والمراحل.

### المرحلة الحالية: Phase 1 — Lucide Only

- **مكتبة الأيقونات:** [Lucide](https://lucide.dev/) v0.460.0 (CDN مُحمَّل مسبقاً في profile-showcase.html)
- **التقديم:** `<i data-lucide="icon-name" class="sk-ic">` + `lucide.createIcons()` بعد كل تحديث DOM
- **الحقل في CATALOG:** `icon: 'lucide-icon-name'` — اسم الأيقونة بالصيغة kebab-case
- **الـ fallback للمهارات المخصصة:** `circle-check` (ثابت: `_CUSTOM_FALLBACK_ICON`)
- **Helper:** `_skillIconHtml(iconName)` — تُنتج `<i data-lucide="..." class="sk-ic"></i>`
- **مواضع الظهور:** داخل chip المهارة (قبل الاسم) + داخل قائمة autocomplete

### Phase 2 — Font Awesome (مؤجّلة)

- Font Awesome Free سيُضاف فقط كـ CDN إضافي في مرحلة لاحقة
- سيُستخدم **فقط** لأيقونات العلامات التجارية التقنية (Python, Docker, GitHub, إلخ) حين يكون التطابق دقيقاً
- سيُعرَّف `FA_BRAND_ALLOWLIST` ويُضاف حقل `icon_provider` للكتالوج
- **لا تُطبَّق Phase 2 قبل موافقة صريحة**

### القواعد القانونية وحقوق الملكية الفكرية

```
✅ Lucide — مرخّص MIT — مناسب للاستخدام التجاري بلا قيود
✅ Font Awesome Free (Phase 2) — مرخّص SIL OFL + MIT — مناسب للاستخدام التجاري
⚠️  شعارات العلامات التجارية (Python, Docker, AWS...) مملوكة لأصحابها
⚠️  الاستخدام لأغراض تعريفية فقط — لا يُفيد بأي شراكة أو تأييد
❌  لا تستخدم صوراً خارجية أو Google Images داخل الكود
❌  لا تستخدم أيقونة علامة تجارية لمهارة عامة (لا تضع شعار Python على "البرمجة")
❌  عند أي شك قانوني، استخدم Lucide generic icon بدلاً من أيقونة العلامة التجارية
```

### ممنوعات

```
❌ لا تُضيف Font Awesome أو CDN جديد دون موافقة صريحة
❌ لا تستخدم emoji كأيقونات للمهارات
❌ لا تستخدم صور خارجية أو URLs للأيقونات
❌ لا تغيّر منطق الحفظ أو الـ validation بسبب تغييرات الأيقونات
❌ لا تلمس profile.html القديم
```

---

## Skill Notes & Vertical Cards

> Skill notes are optional professional annotations added by the employee.

### القواعد

- **Note اختياري دائماً** — لا تجعله إجبارياً أبداً
- **الحد الأقصى** 160 حرف — مطبَّق backend (`len > 160 → 422`) وfrontend (`maxlength="160"`)
- **Validation مزدوج**: `validate_professional_text()` server-side + `_scCheckProfessional()` client-side — no emoji, no profanity
- **عرض مشروط**: `noteHtml` يُبنى فقط إذا `note.trim()` غير فارغ — لا فراغ، لا placeholder
- **UPSERT يحدّث level و note معاً**: `DO UPDATE SET level=EXCLUDED.level, note=EXCLUDED.note`
- **مهارات قديمة**: `note = NULL` طبيعي — لا تحتاج migration لبياناتها

### بنية الكرت

```
[icon] اسم المهارة    [badge المستوى] [مخصصة?] [× للمالك]
ملاحظة اختيارية تظهر هنا فقط إذا كانت موجودة
```

### ألوان المستويات (تنت هادئ، dark-theme)

| المستوى | border-color | background |
|---------|-------------|------------|
| مبتدئ   | `rgba(156,163,175,.28)` | `rgba(156,163,175,.05)` |
| متوسط   | `rgba(96,165,250,.28)`  | `rgba(96,165,250,.05)`  |
| جيد     | `rgba(167,139,250,.28)` | `rgba(167,139,250,.05)` |
| متقدم   | `rgba(0,200,150,.28)`   | `rgba(0,200,150,.05)`   |
| محترف   | `rgba(251,191,36,.32)`  | `rgba(251,191,36,.05)`  |

### Legend

- يظهر دائماً فوق قائمة المهارات (حتى عند عدم وجود مهارات) بجانب زر الإضافة
- على الموبايل يُلتف تلقائياً تحت زر الإضافة عبر `flex-wrap:wrap`

### ممنوعات

```
❌ لا تجعل note إجبارياً
❌ لا تعرض فراغاً إذا note غير موجود
❌ لا تُخزّن string فارغ في DB — أرسل null إذا note فارغ
❌ لا تكسر skill catalog أو autocomplete أو duplicate prevention
```

---

## [P1] 45. Profile Interest System

> PRs: #130 (schema), #131 (endpoints), #132 (frontend)

### الهدف

استبدال زر "الملف" القديم (`scFullBtn`) في Profile V2 بزر ذكي يتكيف مع نوع المشاهد، ويخدم التوظيف والتدريب والتفاعل المهني.

### مبدأ التصميم — Backend is the Source of Truth

**Frontend لا يقرر أي شيء.** Backend يرجع `viewer_action` كاملاً في `GET /profile/{id}`. Frontend يعرض فقط ما يرجعه Backend.

المحظور على Frontend:
- حساب `label` أو `type` أو `hidden` أو `is_active`
- إرسال `interest_type` من Frontend
- الاعتماد على `localStorage` لتحديد نوع المستخدم

### جدول DB

```sql
CREATE TABLE profile_interests (
    id             BIGSERIAL PRIMARY KEY,
    actor_user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_type     TEXT NOT NULL,
    interest_type  TEXT NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_profile_interest     UNIQUE (actor_user_id, target_user_id),
    CONSTRAINT no_self_profile_interest CHECK  (actor_user_id != target_user_id)
);
-- Indexes: actor_user_id, target_user_id, interest_type
```

### تحويل نوع الحساب → interest_type

| user_type | interest_type |
|-----------|--------------|
| `emp` | `profile_like` |
| `co` | `candidate_save` |
| `edu` | `training_invite` |

يتم التحويل في `get_profile_interest_type(actor_user_type)` — Backend فقط.

### viewer_action في GET /profile/{id}

```json
"viewer_action": {
  "label":        "string",
  "type":         "string",
  "is_active":    false,
  "can_interact": true,
  "hidden":       false
}
```

| الحالة | النتيجة |
|-------|---------|
| Owner (صاحب البروفايل) | `hidden=true` |
| Target ليس `emp` | `hidden=true` |
| Guest | `type=login_prompt`, `label=سجّل للتفاعل`, `can_interact=false` |
| Emp يشاهد emp | `label=أعجبني ملفك` / `تم الإعجاب`, `type=profile_like` |
| Co يشاهد emp | `label=حفظ كمرشح` / `محفوظ كمرشح`, `type=candidate_save` |
| Edu يشاهد emp | `label=دعوة للتدريب` / `تم حفظ الدعوة`, `type=training_invite` |

### API Endpoints

```
POST   /profile/{id}/interest   # يتطلب JWT، يمنع self، يمنع guest
DELETE /profile/{id}/interest   # يتطلب JWT، idempotent
```

كلاهما يرجع `viewer_action` محدّثاً في الـ response.

### دوال Backend (`auth.py`)

| الدالة | الوظيفة |
|--------|---------|
| `get_profile_interest_type(actor_user_type)` | تحديد `interest_type` |
| `get_profile_interest_label(actor_user_type, is_active)` | نص الزر بالعربي |
| `save_profile_interest(actor_id, target_id)` | UPSERT idempotent |
| `remove_profile_interest(actor_id, target_id)` | DELETE idempotent |
| `is_profile_interest_active(actor_id, target_id)` | bool |

### Frontend Integration

**الملفات:**
- `profile-v2.api.js`: `saveProfileInterest(id)`, `removeProfileInterest(id)`
- `profile-v2.render.js`: `window._scViewerAction` + scFullBtn wiring
- `profile-v2.css`: `.sc-btn--interested` (active state) + type-specific classes

**سلوك scFullBtn:**
1. `hidden=true` → `display:none`
2. `login_prompt` → Toast فقط، لا POST
3. `can_interact=true` → POST/DELETE toggle، تحديث label/class من `response.viewer_action`

### ستايل الأزرار حسب النوع

| `interest_type` | Class إضافي | الأيقونة | اللون | الحالة النشطة |
|----------------|------------|---------|-------|--------------|
| `profile_like` (emp) | `.sc-btn--like` | `heart` | بنفسجي هادئ `#a78bfa` | `rgba(139,92,246,.16)` |
| `candidate_save` (co) | `.sc-btn--candidate` | `user-check` | أزرق رسمي `#93c5fd` | `rgba(59,130,246,.17)` |
| `training_invite` (edu) | — | يرثه من `.sc-btn-ghost` | — | — |

**بعد حفظ candidate_save:** تظهر `.sc-candidate-hint` أسفل `.sc-actions` مباشرةً لـ 5 ثوانٍ تحتوي:
- نص: "تم حفظ المرشح — يمكنك إضافة ملاحظة خاصة"
- زر: "إضافة ملاحظة" → Toast "سيتم إضافة ملاحظات المرشحين قريباً"

### Candidate Notes — مؤجلة

ملاحظات المرشحين **غير منفذة** في المرحلة الحالية. تحتاج:
- حقل `candidate_note TEXT` في `profile_interests`
- endpoint `PUT /profile/{id}/interest/note` (auth: actor فقط)
- الملاحظة **خاصة بالشركة** — الموظف لا يراها نهائياً

```
❌ لا تُنفذ Candidate Notes بدون migration + endpoint
❌ الموظف ممنوع من رؤية candidate_note
```

### حالة التنفيذ

| الميزة | الحالة |
|-------|-------|
| Schema + دوال Backend | ✅ PR #130 |
| API Endpoints + viewer_action | ✅ PR #131 |
| Frontend button wiring | ✅ PR #132 |
| Button style per type (purple/blue) + icons | ✅ PR #134/#135 |
| Candidate Notes (note field + endpoint) | ⏳ مؤجلة |
| صفحة قائمة المرشحين | ⏳ لم تُنفذ |
| صفحة ملفات أعجبتني | ⏳ لم تُنفذ |
| إشعارات عند الحفظ | ⏳ لم تُنفذ |

### ممنوعات النظام

```
❌ لا localStorage
❌ لا Frontend guessing للـ label أو type
❌ لا interest_type من Frontend
❌ لا guest POST/DELETE
❌ لا owner self-interest
❌ لا تعديل على profile.html القديم
❌ لا كسر Follow / Contact / QR
❌ لا تغيير ستايل زر profile_like بتغيير candidate_save والعكس
```

---

## [P2] 42. About Tab Summary Cards

The About tab is a **read-only snapshot** of the profile, auto-generated from `window._scProfile` on each `renderProfile()` call. It is not a separate data source.

**Rules:**
- Summary cards are built from existing profile state — no extra API calls.
- Empty cards are hidden from public viewers; owner sees an "add content" hint.
- Each card shows max 3 items with a "عرض الكل" button that switches to the full tab via `window.scTab`.
- Bio has a dedicated inline editor (`window._aboutBioEdit/Save/Cancel`) that sends `{bio}` only to `PUT /profile/{id}`.
- The About pane does NOT auto-update after adding items to other tabs (full tabs update in real time; About pane is rebuilt only on full page load or via `window._reRenderAbout()`).

