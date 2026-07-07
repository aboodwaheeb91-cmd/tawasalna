# تواصلنا — Architecture Doctrine

> **Single Source of Truth** للمعمارية.  
> أي تطوير جديد يلتزم بهذا الملف. أي استثناء يُسجَّل هنا قبل التطبيق.

> **Systems Index:** قبل أي PR، اقرأ [`docs/SYSTEMS_INDEX.md`](docs/SYSTEMS_INDEX.md) — فهرس الأنظمة الموجودة (33 نظام). لا تبني نظاماً موجوداً من الصفر.

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
GET  /company/profile/{id}          → Optional JWT | Public read
PUT  /company/profile/{id}          → JWT + token.user_id == id + user_type=='co' (requires industry)
PUT  /company/cover/{id}            → JWT + token.user_id == id + user_type=='co' (cover_url only — no industry required)
POST /company/jobs                  → JWT + user_type=='co'
PUT  /company/jobs/{job_id}         → JWT + token.user_id == jobs.company_id
DELETE /company/jobs/{job_id}       → JWT + token.user_id == jobs.company_id
GET  /jobs/{job_id}/applicants      → JWT + token.user_id == jobs.company_id
PUT  /jobs/applications/{id}/status → JWT + token.user_id == jobs.company_id (via JOIN) + status allowlist
GET  /my/applications               → JWT + user_id from token only
POST /company/{id}/follow           → JWT + user_type=='emp'
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

### Exception 05 — X-User-Id في /company/jobs ~~(مؤقت)~~ ✅ مُغلق
- **القاعدة:** Rule #1 (API Authorization)
- **الحل:** جميع endpoints تستخدم `Depends(verify_token)` الآن — X-User-Id أُزيل بالكامل
- **المغلق في:** PR security(company): replace X-User-Id job endpoints with JWT ownership checks

---

## Phase Roadmap — Company Profile

```
Phase 1 — Security Foundation (مكتمل):
  ✅ JWT ownership validation
  ✅ API authorization (Depends verify_token)
  ✅ viewMode system من API
  ✅ CSS visibility system
  ✅ Bootstrap idempotency
  ✅ Duplicate request prevention
  ✅ X-User-Id أُزيل من /jobs/{id}/applicants, /my/applications, /jobs/applications/{id}/status
  ✅ Status allowlist validation على PUT /jobs/applications/{id}/status

Phase 1.5 — Modularization (مكتمل — PR #224 + PR #361):
  ✅ CSS نُقل من company-profile.html → static/company/company.css
  ✅ JS نُقل من company-profile.html + company-profile.js → static/company/ modules
  ✅ company-profile.html أصبح HTML هيكل فقط (no inline <style>, <script>, أو event handlers)
  ✅ company-profile.js (القديم) لا يُحمَّل بعد الآن (superseded by modules)
  ✅ لا تغيير في التصميم / لا تغيير في API / Security P0 محفوظة
  ✅ inline event handlers نُقلت إلى JS delegation في initCompanyProfile() — PR #361

Phase 2 — Schema + Real Data (مكتمل):
  ✅ company_profiles table migration
  ✅ Real data: jobs_count, verified_count من DB
  ✅ Skeleton loader (co-loading CSS state + .tw-skeleton animation)
  ✅ إخفاء hardcoded sections (renderAll() يولد كل المحتوى من companyState)

Phase 3 — Social Features (مكتمل):
  ✅ company_follows table + endpoints
  ✅ company_ratings table + endpoints
  ✅ follow/unfollow real
  ✅ rating display real

Phase 4 — Polish (مكتمل):
  ✅ Back button (Rule #17) — contact / edit / postJob / editJob / postOverlay / applicants (PRs #363 #364)
  ✅ Render functions موحدة (modular architecture — static/company/ modules)
  ✅ State deduplication (companyState SSOT — _mergeCompanyState)

Phase 5 — Quality & Security Fixes (مكتمل — PRs #355–#361):
  ✅ job location mode guard — TW.fillCountries لا يمسح اختيار المستخدم عند التبديل (PR #355)
  ✅ effective_status لـ lifecycle الوظيفة (active/paused/closed/expired) — عرض متسق
  ✅ contact form يرسل عبر /messages/send endpoint
  ✅ location dropdowns: country + city من TW shared system (لا hardcoded)
  ✅ rating يعمل عبر /u/{tw_id} (Smart Router)
  ✅ Applicants Modal: أزرار قبول مبدئي / رفض (PUT /jobs/applications/{id}/status) — PR #356
  ✅ Applicants Modal: avatar من profiles.avatar_url مع char fallback عند الخطأ — PR #357
  ✅ saved-candidates badge يعتمد stats.total حصراً (لا res.data.count) — PR #358
  ✅ _escAttr في HTML attribute positions (بدلاً من _esc) — PR #359
  ✅ production console.info diagnostic أُزيل من loadData().finally() — PR #360
  ✅ inline event handlers نُقلت من HTML إلى JS delegation في initCompanyProfile() — PR #361

ممنوع الانتقال لـ Phase التالية قبل إغلاق الحالية واختبارها.
```

---

## Company Frontend — Modular File Structure (PR #224)

ملفات صفحة الشركة تعيش في `static/company/`. ترتيب التحميل إلزامي:

| الترتيب | الملف | المسؤولية |
|---------|-------|-----------|
| 1 | `static/company/company.state.js` | `companyState` SSOT + `_mergeCompanyState` + `_applyViewMode` + `_jwt()` |
| 2 | `static/company/company.api.js` | `loadData` + `loadJobs` + `loadPosts` — JWT Bearer فقط |
| 3 | `static/company/company.permissions.js` | `_applyLoadingState` + permission guards |
| 4 | `static/company/company.render.js` | `renderProfile/Stats/Jobs/All` + `renderFollowBtn/Rating/Posts` + DOM helpers |
| 5 | `static/company/company.jobs.js` | `_applyJob` + `applyJob` + `bindEvents` + `bindRateStars` + `submitRating` + `openPostJob` + `publishJob` |
| 6 | `static/company/company.posts.js` | `openPostModal` + `createPost` + `deletePost` |
| 7 | `static/company/company.main.js` | bootstrap + `initCompanyProfile` + nav + modals + follow + cover + report + pull-to-refresh |
| CSS | `static/company/company.css` | كل styles الصفحة (منقولة من `<style>` blocks داخل HTML) |

### قواعد إلزامية
- **ممنوع** إضافة `<style>` أو `<script>` inline في `company-profile.html`
- **ممنوع** تحميل `company-profile.js` (القديم) — superseded
- **ممنوع** إضافة module جديد قبل تحديد الترتيب الصحيح له في الجدول أعلاه
- كل namespace: `window.X` — لا ES modules، لا bundler

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
- **الوضع المؤقت (مستمر):** أي مستخدم user_type='emp' يستطيع التقييم
- **السبب:** قيد "موظف سابق" يحتاج job_applications مع status='hired' flow — لم يُبنَ بعد
- **الحد:** الحقل permissions.can_rate يبقى محكوماً من backend فقط
- **الأمان:** لا أثر أمني — مجرد قيد business يُضيَّق لاحقاً
- **الإزالة:** عند بناء hired-status flow (لم يُجدوَل بعد)

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
| `candidate_save` (co) | `.sc-btn--candidate` | inactive=`user-plus` / active=`user-check` | أزرق رسمي `#93c5fd` | `rgba(59,130,246,.17)` |
| `training_invite` (edu) | — | يرثه من `.sc-btn-ghost` | — | — |

**بعد حفظ candidate_save:** تظهر `.sc-candidate-hint` أسفل `.sc-actions` وتبقى ظاهرة حتى يختار المستخدم:
- أيقونة `check-circle` + نص: "تم حفظ المرشح" / "يمكنك إضافة ملاحظة خاصة"
- زر "إضافة ملاحظة" → Toast "سيتم إضافة ملاحظات المرشحين قريباً" ثم تُخفى الـ hint
- زر "ليس الآن" → يُخفي الـ hint فقط بدون أي API call
- عند إلغاء الحفظ: الـ hint تُزال تلقائياً إن كانت ظاهرة

```
❌ الـ hint لا تختفي تلقائياً بـ timeout
❌ "ليس الآن" لا يلغي الحفظ ولا يرسل API call
```

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


---

## [P0] 46. JWT Token System

**Location:** `server.py` lines 90–119

### Token Generation — `_jwt_encode(payload)`

```python
# payload input:
{
  "user_id": <int>,
  "user_type": "emp" | "co" | "edu",
  "tw_id": <str>
}
# Adds automatically:
payload['iat'] = int(time.time())
payload['exp'] = int(time.time()) + 86400 * 7  # 7 days
# Algorithm: HS256 (HMAC-SHA256)
# Encoding: Base64URL without padding (rstrip('='))
# Header: {"alg":"HS256","typ":"JWT"}
# Secret: first 32 chars of ADMIN_TOKEN SHA256
```

### Token Verification — `_jwt_decode(token)`

Returns `{}` (empty dict) if: invalid format / bad signature / expired.

Checks order:
1. Signature verification (HS256 with JWT_SECRET)
2. `exp` claim against `time.time()`

### FastAPI Dependency — `verify_token`

```python
def verify_token(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    payload = _jwt_decode(token) if token else {}
    if not payload:
        raise HTTPException(401, "Token invalid or expired")
    return {"valid": True, "user_id": payload.get("user_id"), "user_type": payload.get("user_type")}
    # Used in endpoints as: token=Depends(verify_token)
```

### Frontend JWT Global

All Profile V2 modules read JWT from `window._jwt` (set in `profile-v2.state.js`):
```javascript
_jwt = sess.jwt;  // From localStorage tawasalna_user.jwt
```

API calls use: `Authorization: Bearer ${_jwt || ''}`

### Rules

```
✅ Expiry: 7 days — no refresh tokens
✅ Secret: derived from ADMIN_PASSWORD hash (deterministic, no DB storage)
✅ No token blacklist — logout is client-side only (localStorage.removeItem)
❌ لا تخزين الـ token في الـ DB
❌ لا تمرير الـ token في الـ URL
❌ لا تنفيذ verify_token بدون الـ Authorization header
```

---

## [P0] 47. WebSocket Real-time Messages

**Location:** `server.py` lines 810–866

### ConnectionManager Class

```python
class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, list] = {}  # {user_id: [ws1, ws2, ...]} — supports multi-tab

    async def connect(self, user_id: int, ws: WebSocket)     # Accepts + registers
    def disconnect(self, user_id: int, ws: WebSocket)         # Removes from active list
    async def send_to_user(self, user_id: int, data: dict)    # Sends to all tabs of user
```

### Endpoint

- **Path:** `WS /ws/{user_id}`
- **Auth:** None (user_id in path param serves as identifier)
- **Protocol:** Text-based JSON

### Message Flow

**Client → Server (send):**
```json
{ "receiver_id": <int>, "content": <str> }
```

**Server → Receiver (receive):**
```json
{ "type": "message", "from": <int>, "content": <str>, "created_at": "<ISO>" }
```

**Server → Sender (confirmation):**
```json
{ "type": "sent", "id": <msg_id> }
```

### Key Implementation Details

- In-memory `active` dict — NOT distributed (single Heroku dyno only)
- Message persisted to `messages` table via `send_message()` before WS delivery
- Dead connection cleanup: WebSocketDisconnect → `manager.disconnect()`
- If receiver offline: message saved in DB, delivered next time they poll GET /messages
- Multi-tab: same user_id can have multiple websockets in `active[user_id]` list

### ممنوعات

```
❌ لا تفترض أن الـ WS متاح على multi-dyno (in-memory فقط)
❌ لا تستبدل HTTP polling بـ WS وحده — WS للـ real-time، HTTP للـ history
```

---

## [P0] 48. Messages System

**Database Table: `messages`**

```sql
CREATE TABLE messages (
    id         SERIAL PRIMARY KEY,
    sender_id  INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    content    TEXT NOT NULL,
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
)
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/messages/send` | JWT (required) | إرسال رسالة — `sender_id` مستخرج من JWT فقط |
| GET | `/messages/conversations/{user_id}` | JWT + owner check | قائمة المحادثات (آخر رسالة لكل محادثة) |
| GET | `/messages/{user_id}/{other_id}` | JWT + owner check | رسائل محادثة (LIMIT 100) — يُحدّث is_read=TRUE |
| GET | `/messages/unread/{user_id}` | JWT + owner check | عدد الرسائل غير المقروءة |

**Request for POST /messages/send:**
```json
{ "receiver_id": <int>, "content": <str> }
```
> **ممنوع:** إرسال `sender_id` في body — يُستخرج من JWT حصراً.

**Owner Check Pattern (GET endpoints):**
```python
if int(token.get("user_id") or 0) != user_id:
    raise HTTPException(403, "غير مصرح")
```

**Response for GET /messages/conversations:**
```json
{
  "conversations": [
    { "other_id": <int>, "content": <str>, "created_at": <str>,
      "is_read": <bool>, "sender_id": <int>, "full_name": <str>, "user_type": <str> }
  ]
}
```

### Key Implementation Details

- `get_conversations()` uses `DISTINCT ON (other_id)` wrapped in a subquery sorted `ORDER BY created_at DESC` — returns one row per partner, ordered by recency
- `get_conversations()` returns `tw_id` of the other party alongside `other_id` (numeric)
- `get_messages()` auto-marks `is_read=TRUE` for receiver's unread messages on read
- `send_message()` looks up sender's `tw_id` and calls `create_notification()` with link `/messages?with={sender_tw_id}` so the notification deep-links to the correct conversation
- No message deletion endpoint in current version
- Frontend (`messages.html`) polls via `setInterval` (client-driven frequency)
- `messages.html` uses `tw_user` key in localStorage (legacy pattern — different from `tawasalna_user` used in profile)
- `_jwt = localStorage.getItem('tw_jwt') || ''` — injected at top of script block after user session load

### Security Debt (Known — Not Fixed in Step 1)

- WebSocket `/ws/{user_id}` — `user_id` comes from URL path, no JWT verification on WS upgrade.
  No change made to avoid breaking real-time delivery. Tracked for a future hardening step.

### Frontend Security Rules (messages.html — Step 1)

- **`esc(s)` helper** must be called before injecting ANY user-supplied string into `innerHTML`.
  Covers: `msg.content`, `full_name`, `c.content` (last message preview), `data.content` (WS), form inputs in interview card.
- **Forbidden:** `innerHTML += rawUserString` anywhere in messages.html — use `esc()` first.
- **Single `sendMessage` function** — no override pattern. Body: WS send (primary) + HTTP fallback. No `sender_id` in body, ever.
- **Messages source: DB only** — no localStorage read/write for message content. `tw_chat_*` keys are removed.
- **`?with=` race condition fix** — resolve `tw_id` first, call `openConversation` (sets `_currentConvId`), then `loadConversations()`. `_activeConvMeta` preserves active item if conversation isn't in DB list yet.
- **Mobile back button** — `toggleConvList()` toggles `.mobile-show` on `#convList`. `openConversation` removes `.mobile-show` on selection.
- **`loadUnreadCount()` called after `openConversation`** — count refreshes when messages are marked read.
- **WebSocket security debt** — `/ws/{user_id}` has no JWT check. Deferred to a dedicated future Step.

---

## [P0] 49. Messenger V1 — Modular Architecture

### Overview

`messages.html` was rebuilt from scratch (Step 2) in a modular structure identical to Profile V2.
All static/demo content was removed. The page is a pure shell — JS files own all dynamic rendering.

### File Map

| File | Role |
|------|------|
| `messages.html` | Shell only: nav, layout skeleton, empty `#convItems`, empty `#messages`, script tags |
| `messages.css` | All styles: layout, conv-list, chat panel, message bubbles, input, mobile |
| `messages.state.js` | State globals: `_user`, `_jwt`, `_currentConvId`, `_activeConvMeta`, `esc()` |
| `messages.api.js` | API layer: `apiGetConversations`, `apiGetMessages`, `apiSendMessage`, `apiGetUnreadCount`, `apiLookupByTwId`, `apiGetUser` |
| `messages.ws.js` | WebSocket: `connectWS()`, reconnect logic, onmessage handler |
| `messages.render.js` | Render + UI + init: `openConversation`, `loadConversations`, `renderConvList`, `renderBubble`, `doSendMessage`, `handleWithParam`, DOMContentLoaded init |

### Script Loading Order

```html
<script src="/tw_shared.js"></script>              <!-- showToast, getAuthHeaders -->
<script src="/static/messages.state.js?v=v1"></script>
<script src="/static/messages.api.js?v=v1"></script>
<script src="/static/messages.ws.js?v=v1"></script>
<script src="/static/messages.render.js?v=v1"></script>
```

Static files served by the existing `/static/{filename:path}` route (reads from repo root as fallback — no server.py changes required).

### Message Bubble HTML Structure

```html
<div class="msg-wrap out">   <!-- out = sent by me, in = received -->
  <div class="msg out">
    <div class="msg-text">content</div>
    <div class="msg-time">10:30 ص ✓</div>
  </div>
</div>
```

- `msg-wrap.out` → `justify-content: flex-start` (RTL: right-aligned)
- `msg-wrap.in`  → `justify-content: flex-end`   (RTL: left-aligned)

### `openConversation(otherId, name, typeIco)` — Single Entry Point

**Rule:** Every conversation open MUST go through `openConversation()`. No other function may load messages directly.

Called by:
- `handleWithParam()` — resolves `?with=` deep-link
- `renderConvList()` — click handlers on list items
- Placeholder item click in `_activeConvMeta` insertion

### `_activeConvMeta` — Race Condition Prevention

Stores `{ id, name, typeIco }` for the active conversation.
When `renderConvList()` rebuilds the list from DB, it checks if `_currentConvId` exists in new data.
If not (new conversation not yet persisted), it inserts a placeholder item at top with `active` class.
This prevents the active item from disappearing during the 30s polling refresh.

### Composer Visibility Rules (`#chatInput`)

| State | Composer |
|-------|----------|
| Page load, no conversation selected | `display:none` (hidden) |
| `openConversation()` called | `display:''` (shown) |
| Empty conversation ("ابدأ المحادثة") | **Shown** — empty state never hides composer |
| Invalid `?with=` tw_id | Stays hidden (error state shown in `#messages`) |

`openConversation()` is the only function that shows the composer. It must always call:
```javascript
document.getElementById('chatInput').style.display = '';
```

### Mobile Layout Contract

```
body / .layout  → height: 100dvh (fallback: 100vh) — prevents Chrome Android overflow
.chat           → flex-column + min-height:0 + overflow:hidden — constrains to grid cell
.messages       → flex:1 + min-height:0 — allows shrink so composer stays on-screen
.chat-input     → flex-shrink:0 + padding-bottom: max(12px, env(safe-area-inset-bottom))
```

- `min-height:0` on `.messages` is mandatory — without it, the flex default `min-height:auto`
  causes `.messages` to expand beyond its container, pushing `.chat-input` off-screen.
- `100dvh` (dynamic viewport height) adjusts for the mobile browser chrome (address bar).
  Older browsers fall back to `100vh` via the cascade (last declaration wins if `dvh` unknown).

### Known Debt

| Ref | Debt | Severity | Status |
|-----|------|----------|--------|
| P0 | `/ws/{user_id}` — no JWT verification on WebSocket upgrade | Critical | Open |
| P1 | `get_conversations` sorted by `other_id` not recency | High | **Fixed** (subquery wrap) |
| P2 | `create_notification()` deep-link was `/messages` without sender tw_id | Low | **Fixed** |

### Send Flow — HTTP Primary (V1 Step 3 fix)

`doSendMessage()` now uses **HTTP as source of truth** for DB save:

```
1. disable send button
2. clear input
3. render pending bubble (opacity .6, time + ···)
4. POST /messages/send (HTTP)
   SUCCESS → opacity 1, ··· → ✓, loadConversations()
   FAILURE → .msg-failed style, ··· → ✗, restore input text
5. re-enable send button (always)
```

**Rules:**
- ✓ is shown ONLY after HTTP 200 response — never before
- HTTP failure shows ✗ with red tint on bubble; input text restored for retry
- WebSocket is NOT used for sending — WS is receive-only (real-time push from server)
- No `sender_id` in POST body — always from JWT

**Why HTTP-only send?**
The WS endpoint (`/ws/{user_id}`) also saves to DB. Sending via BOTH would create duplicates.
The HTTP endpoint (`POST /messages/send`) is stateless, reliable, and returns DB confirmation.
WS real-time delivery to receiver requires server.py changes (HTTP handler would need to call `ws_manager.send_to_user`) — deferred.

### Receiver Delivery — Polling

Since HTTP send does not trigger WS push to receiver, delivery relies on polling:

```javascript
setInterval(function() {
  loadConversations();      // update sidebar preview
  reloadMessagesQuiet();    // reload open conversation from DB
}, 10000);                  // every 10 seconds
```

`reloadMessagesQuiet()` rules:
- Only fires if `_currentConvId` is set
- Compares `list.length` vs current `.msg-wrap` count — skips if no new messages
- Preserves scroll position if user is not at bottom
- Does NOT reset pending/failed bubbles mid-flight

**Delivery guarantee:**
- Sender: ✓ = confirmed in DB
- Receiver: sees message within ≤10s if chat open, or on next `openConversation()` call
- No message shown as delivered if DB save failed

### Forbidden Patterns (Messenger V1)

- ممنوع: `innerHTML` injection without `esc()` first
- ممنوع: `sender_id` في body للـ POST `/messages/send`
- ممنوع: فتح محادثة بدون `openConversation()` (لا تستدعي `apiGetMessages` مباشرة)
- ممنوع: حفظ محتوى الرسائل في localStorage
- ممنوع: demo/static conversations أو messages في HTML
- ممنوع: إضافة `conversations` table أو `conversation_id` لحين القرار المعماري
- ممنوع: إظهار `#chatInput` إلا عبر `openConversation()` فقط
- ممنوع: empty state يستبدل `.chat` كاملاً — يُعرض داخل `#messages` فقط
- ممنوع: إرسال عبر WebSocket من `doSendMessage()` — WS للاستقبال فقط
- ممنوع: إظهار ✓ قبل تأكيد HTTP 200 من `/messages/send`
- ممنوع: `.catch(function(){})` على `apiSendMessage` بدون معالجة الفشل

---

## [P0] 51. Messenger + Notifications Integration

### Notification Deep-Link Contract

When `send_message()` creates a notification for the receiver, the link MUST be:
```
/messages?with={sender_tw_id}
```
This allows the receiver to click the notification and land directly in the correct conversation.

**Implementation (`auth.py`):**
```python
sender_info = get_user_by_id(sender_id)
sender_tw_id = sender_info.get('tw_id', '') if sender_info else ''
notif_link = f'/messages?with={sender_tw_id}' if sender_tw_id else '/messages'
create_notification(receiver_id, 'message', 'رسالة جديدة', content[:60], notif_link)
```

**Forbidden:** hardcoding `/messages` as notification link without `?with=` — the receiver has no way to know which conversation to open.

### `notifications.html` — Click Navigation

Notification items rendered in `container.innerHTML` have no native onclick. Navigation is wired via:

1. Each notification `<div class="ni">` receives `data-link="{n.link}"` attribute
2. Event delegation on the container fires after `innerHTML` is set:
```javascript
container.addEventListener('click', function(e) {
  var item = e.target.closest('.ni[data-link]');
  if (item) { var lnk = item.getAttribute('data-link'); if (lnk) window.location.href = lnk; }
});
```

**Forbidden:** attaching individual `onclick` per item inside `innerHTML` string — use event delegation.
**Forbidden:** navigating to `/messages` (no `?with=`) from a message notification — the conversation list will be empty if link is generic.

### Header Badge — Auth Requirements

| Endpoint | Auth Required | Header in home.html |
|----------|---------------|---------------------|
| `GET /notifications/{user_id}` | None | — |
| `GET /messages/unread/{user_id}` | JWT (`verify_token`) | `Authorization: Bearer {tw_jwt}` |

`home.html` reads `tw_jwt` from localStorage before both badge IIFEs. Both the nav-bar badge IIFE and the home-badges IIFE apply the JWT header to the `/messages/unread/` call.

### `get_conversations()` — Sort Fix

**Problem:** `DISTINCT ON` in PostgreSQL requires the first `ORDER BY` key to match the `DISTINCT ON` key. The old query ordered by `other_id, created_at DESC` — giving one row per partner but sorted by partner ID, not recency.

**Fix:** wrap in a subquery:
```sql
SELECT * FROM (
  SELECT DISTINCT ON (other_id) ..., u.tw_id
  FROM messages m
  JOIN users u ON ...
  WHERE sender_id=:uid OR receiver_id=:uid
  ORDER BY other_id, created_at DESC   -- required by DISTINCT ON
) sub
ORDER BY created_at DESC               -- outer sort by recency
```

`tw_id` is now included in the result so future UI features can build deep-links without a secondary lookup.

---

## [P0] 52. Global Badge System (`loadGlobalBadges`)

### Problem
Each page had its own (or missing) badge-loading logic:
- `home.html` — had logic, fixed in PR #150 with JWT header
- `profile.html` — had `window._triggerBadges()` with JWT
- `company.html` — hardcoded `0`
- `edu.html` — hardcoded `2` (wrong, never updates)
- `edu-profile.html`, `company-profile.html`, `settings.html`, `notifications.html` — no badge loading

### Solution: `loadGlobalBadges()` in `tw_shared.js`

```javascript
function loadGlobalBadges() {
  // reads tw_user + tw_jwt from localStorage
  // fetches /notifications/{id} → populates data-badge="notif"
  // fetches /messages/unread/{id} with JWT → populates data-badge="msgs"
}
```

All badge `<span>` elements in nav menus use `data-badge="msgs"` or `data-badge="notif"` attribute.
`loadGlobalBadges()` finds all matching elements and sets their textContent + visibility.

### Auth Requirements for Badges

| Endpoint | Auth |
|----------|------|
| `GET /notifications/{user_id}` | None |
| `GET /messages/unread/{user_id}` | JWT Bearer required |

**Forbidden:**
- ممنوع: hardcoded numbers in badge spans (always use `data-badge` + `loadGlobalBadges()`)
- ممنوع: calling `/messages/unread/` without `Authorization: Bearer {jwt}` header
- ممنوع: per-page badge-loading logic (use `loadGlobalBadges` from tw_shared.js)

### Pages That Call `loadGlobalBadges()`
- `company.html` — `document.addEventListener('DOMContentLoaded', loadGlobalBadges)`
- `edu.html` — same
- `notifications.html` — called directly after page init
- `home.html` — has its own inline IIFE (compatible, uses same endpoints)
- `profile.html` — has `window._triggerBadges()` (compatible, uses same endpoints)
- `profile-showcase.html` (Profile V2 / `/u/{tw_id}`) — called from header-wiring IIFE in `profile-v2.render.js`; badge spans on `#scBellBtn` and `#scMsgBtn`

### Profile V2 Badge Span Locations
```html
<!-- #scBellBtn — notifications badge -->
<span data-badge="notif" style="position:absolute;top:-3px;left:-3px;..."></span>

<!-- #scMsgBtn — messages badge -->
<span data-badge="msgs" style="position:absolute;top:-3px;left:-3px;..."></span>
```
Both buttons have `position:relative`. Guest users see no badge (loadGlobalBadges returns early if no jwt).

---

## [P0] 53. Messenger ↔ Notifications Separation (Architectural Rule)

### Rule: Messages Are Not General Notifications

Messenger messages and general platform notifications are **separate systems**:

| System | Table | Badge | Page |
|--------|-------|-------|------|
| Messenger | `messages` | `/messages/unread/{id}` (JWT required) | `/messages` |
| Notifications | `notifications` | `/notifications/{id}` (no auth) | `/notifications` |

### Backend Rules

- `send_message()` saves to `messages` table only — **no `create_notification()` call**
- `get_notifications()` filters `WHERE type != 'message'` — legacy rows excluded at DB query level
- `get_unread_notifications()` filters `WHERE type != 'message' AND is_read=FALSE` — notification badge count never includes messages

### Frontend Rules

- `notifications.html` filters out `n.type === 'message'` AND `n.link.startsWith('/messages')` client-side (defense-in-depth for any legacy rows)
- No "💬 رسائل" tab in notifications filter tabs
- `loadGlobalBadges()` always fetches both counts independently:
  - Notif badge ← `/notifications/{id}` (excludes messages at server level)
  - Msg badge ← `/messages/unread/{id}` (exclusive to messenger)

### Legacy Data

Any `notifications` rows with `type='message'` or `link LIKE '/messages%'` are **legacy** (created before this rule was established). They are excluded at both API and UI layers. DB cleanup: `DELETE FROM notifications WHERE type = 'message';` can be run manually.

### Forbidden

- ممنوع: استدعاء `create_notification()` من `send_message()` أو أي دالة إرسال رسائل
- ممنوع: عرض `type='message'` notifications في `/notifications`
- ممنوع: إضافة tab "رسائل" في صفحة الإشعارات
- ممنوع: احتساب رسائل الماسنجر ضمن عداد الإشعارات

---

## [P0] 53b. Static Demo Content Removal — notifications.html

### Problem
`notifications.html` contained 3 hardcoded demo notification groups in HTML that were always visible:
- `#group-today` — 3 fake notifications (interview, job match, message)
- `#group-yesterday` — 2 fake notifications (verify, training, job)
- Unnamed group — 3 more fake notifications

The demo "رسالة جديدة" item had no `data-link`, no onclick — users clicked it expecting navigation but nothing happened. This was the root cause of "الإشعار لا يفتح المحادثة".

### Fix
All static `.notif-group` blocks removed. Only `#dynamicNotifs` remains — populated exclusively from `GET /notifications/{user_id}` DB data.

**Forbidden:**
- ممنوع: أي demo/fake notification content في notifications.html HTML
- ممنوع: `.ni` elements without `data-link` if they represent clickable notifications

---

## [P0] 54. JS Cache Busting Contract

### Problem
`/static/` route serves files with `Cache-Control: public, max-age=86400` (24 hours).
Messenger JS files used `?v=v2` across PRs #147–#150 — same URL, changing content.
Browsers served cached old content for up to 24h after deploy.

### Rule
**Every time the content of a `messages.*.js` or other static JS file changes in a PR, the version query string in `messages.html` (or the importing HTML) MUST be bumped.**

Current versions: `?v=v4` (bumped after mobile default view fix — PR that fixed conv-list hidden on mobile).

### Service Worker
`sw.js` `BUILD_TIME` must be updated on each deploy to trigger SW refresh and clear old caches.
Current: `20260615_1900`.

**Forbidden:**
- ممنوع: تغيير محتوى ملف JS بدون bump للـ version string في الـ HTML الذي يستدعيه

---

## [P0] 50. Contact Button — Profile V2 Integration

### Behavior (Three Modes)

| Viewer | Button Visibility | On Click |
|--------|-------------------|----------|
| Owner (صاحب البروفايل) | **مخفي** (`display:none`) | — |
| Guest (غير مسجل) | ظاهر | Toast: "سجّل الدخول للتواصل" — لا navigation |
| Logged-in non-owner | ظاهر | انتقال إلى `/messages?with={tw_id}` |

### Source of Target

```javascript
var tw = window._scProfile && window._scProfile.tw_id;
window.location.href = '/messages?with=' + encodeURIComponent(tw);
```

- Target = `window._scProfile.tw_id` (البروفايل المعروض)
- **ممنوع:** استخدام id المستخدم المسجل كهدف
- **ممنوع:** استخدام localStorage لتحديد صاحب البروفايل (يُستخرج من `viewer_type` server-side)
- Owner check: `if(_vt === 'owner') contactBtn.style.display = 'none'`

### messages.html — `?with=` Deep-link

```
GET /messages?with={tw_id}
```

1. صفحة الرسائل تقرأ `new URLSearchParams(location.search).get('with')`
2. تستدعي `GET /user/lookup/{tw_id}` (JWT required) → `{ id, full_name, user_type, tw_id }`
3. تفتح المحادثة تلقائياً عبر `openRealConv(el, data.id, name, typeIco)`
4. إذا المحادثة فارغة → تعرض "ابدأ المحادثة" (موجودة في `openRealConv` بالفعل)
5. URL يُنظَّف بعد الفتح: `history.replaceState(null, '', '/messages')`
6. إذا tw_id غير صحيح → تعرض "تعذر فتح المحادثة" بدون كسر الصفحة

### `/user/lookup/{tw_id}` Endpoint

| | |
|---|---|
| Method | `GET` |
| Path | `/user/lookup/{tw_id}` |
| Auth | JWT required |
| Response | `{ id, full_name, user_type, tw_id }` |
| Error | 404 إذا tw_id غير موجود |

### ممنوعات

- لا `conversation_id` — sender_id من JWT فقط
- لا تغيير لـ WebSocket
- لا `sender_id` في body أي رسالة
- `/profile/{id}` ليس رابط محادثة — رابط عرض فقط
- `/u/{tw_id}` رابط عرض البروفايل — ليس رابط رسائل

---

## [P0] 49. Notifications System

**Database Table: `notifications`**

```sql
CREATE TABLE notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    type       TEXT NOT NULL,     -- 'message' | 'report' | 'follow' | free text
    title      TEXT,
    body       TEXT,
    link       TEXT,              -- navigation path (e.g. /messages)
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
)
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications/{user_id}` | None | LIMIT 50 DESC — يُعيد قائمة + unread count |
| PUT | `/notifications/{user_id}/read` | JWT | يُحدّث is_read=TRUE لكل إشعارات المستخدم |

**Response for GET:**
```json
{ "notifications": [{id, user_id, type, title, body, link, is_read, created_at}], "unread": <int> }
```

### Trigger Points

`create_notification(user_id, type, title, body, link)` called from:
- `send_message()` → type='message'
- `report_submit()` → type='report' (للمستخدم المبلَّغ عنه)
- Admin KYC approval → manually

### Rules

```
✅ لا انتهاء صلاحية للإشعارات — تبقى حتى mark-as-read
✅ type هو نص حر — لا enum validation في البيكند
❌ لا حذف فردي للإشعارات في الـ UI الحالي
```

---

## [P0] 50. Profile Views System

**Database Table: `profile_views`**

```sql
CREATE TABLE profile_views (
    id             SERIAL PRIMARY KEY,
    viewed_user_id INTEGER NOT NULL REFERENCES users(id),
    viewer_user_id INTEGER NOT NULL REFERENCES users(id),
    viewed_at      TIMESTAMPTZ DEFAULT NOW()
)
-- Indexes:
-- idx_pv_pair_time ON profile_views(viewed_user_id, viewer_user_id, viewed_at DESC)
-- idx_pv_viewed ON profile_views(viewed_user_id)
```

### Functions

| Function | Logic |
|----------|-------|
| `record_profile_view(viewed_user_id, viewer_user_id)` | 24h deduplication: إذا كان نفس الـ viewer زار في آخر 24 ساعة → لا يُسجَّل مرة ثانية |
| `get_profile_views_count(viewed_user_id)` | `COUNT(*) FROM profile_views WHERE viewed_user_id` |

### Wiring into GET /profile/{user_id}

```python
if viewer_type == "public-user" and token_uid:
    try:
        record_profile_view(profile_id, int(token_uid))
    except Exception:
        pass
views_count = get_profile_views_count(profile_id)
# Returned in response as: "views_count": views_count
```

### Rules

```
✅ 24h deduplication per viewer per profile
✅ Owner لا يُسجَّل كـ view لملفه الشخصي
✅ Guest (غير مسجّل) لا يُسجَّل
❌ لا تسجيل view من /metrics endpoint
❌ لا تسجيل view من admin endpoints
```

---

## [P0] 51. `/u/` Public Profile Showcase

**URL Pattern:** `/u/{tw_id}`

**File:** `profile-showcase.html`

**Server Route:**

```python
@app.get("/u/{tw_id}", response_class=HTMLResponse)
def public_profile_short_url(tw_id: str):
    numeric_id = get_user_id_by_tw_id(tw_id)
    if not numeric_id:
        raise HTTPException(404, "الملف الشخصي غير موجود")
    base = read_html("profile-showcase.html")
    # numeric_id cast to int prevents XSS
    injected = base.replace('</head>',
        '<script>window._scProfileIdFromRoute=' + str(int(numeric_id)) + ';</script></head>', 1)
    return HTMLResponse(content=injected)
```

### Difference vs Regular Profile `/profile`

| الخاصية | `/profile` | `/u/{tw_id}` |
|---------|-----------|-------------|
| الجمهور | مالك الملف (edit) | عام (قابل للمشاركة) |
| URL | numeric id parameter | tw_id (مثل U9620ec95e9c5ca) |
| Inject | لا شيء | `window._scProfileIdFromRoute` |
| Editing | ✅ | ❌ |
| QR Download | ✅ | ✅ |

### QR URL Format

```javascript
'https://tawasolna.com/u/' + encodeURIComponent(tw_id) + '?ref=qr'
```

### Rules

```
✅ tw_id في الـ URL — numeric_id لا يظهر في الـ URL (خصوصية)
✅ numeric_id يُحقن server-side لمنع XSS (int() cast)
❌ لا تُرجع tw_id مباشرة من الـ API في الـ URL
❌ لا تلمس profile-showcase.html بدون تحديث profile-v2.render.js أيضاً
```

---

## [P0] Routing & Navigation Rules (Global)

### Official URLs

| Use case | Correct URL | Forbidden |
|----------|-------------|---------|
| عرض بروفايل مستخدم (موظف) | `/u/{tw_id}` | `profile.html?id=`, `/profile?id=` |
| صفحة الرسائل | `/messages` | `messages.html` |
| فتح محادثة مع مستخدم | `/messages?with={tw_id}` | `messages.html` |
| بروفايل شركة | `/company-profile?id={id}` | `company-profile.html?id=` |
| بروفايل جهة تعليمية | `/edu-profile?id={id}` | `edu-profile.html?id=` |

### Profile Button Pattern

When navigating to another user's profile from any page (Messenger, company search, team list):

```javascript
// CORRECT — always via tw_id
fetch('/auth/user/' + numericId)
  .then(function(r){ return r.ok ? r.json() : null; })
  .then(function(data){
    var tw = data && data.user && data.user.tw_id;
    if (tw) window.location.href = '/u/' + tw;
  });

// FORBIDDEN
window.open('profile.html?id=' + id, '_blank');
window.location.href = '/profile?id=' + id;
```

Note: `GET /auth/user/{id}` returns `{ "user": { id, tw_id, full_name, ... } }` — access via `data.user.tw_id`, NOT `data.tw_id`.

### Messages Link Pattern

```javascript
// CORRECT
window.location.href = '/messages';
window.location.href = '/messages?with=' + twId;
<a href="/messages">الرسائل</a>

// FORBIDDEN
window.location.href = 'messages.html';
<a href="messages.html">الرسائل</a>
```

### Notification Links (auth.py `create_notification`)

| Notification type | Correct link |
|-------------------|-------------|
| رسالة جديدة | `/messages` |
| وظيفة | `/job-detail?id={job_id}` |
| توثيق | `/settings` |

### Legacy Files

| File | Status |
|------|--------|
| `profile.html` | Legacy — لا تُضاف إليه navigation جديد. لا تحذفه. |
| `messages.html` → `/messages` | الـ route يخدم نفس الملف، استخدم `/messages` دائماً |
| `/profile?id=` | لا تُستخدم كـ display URL — للـ API والـ legacy فقط |

---

## [P0] 52. KYC / Credential Verification System

### Database Tables

**`kyc_submissions`** — حالة عملية التحقق من الهوية:

```sql
CREATE TABLE kyc_submissions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER UNIQUE NOT NULL REFERENCES users(id),
    step            TEXT NOT NULL,       -- 'email'|'phone'|'id_upload'|'review'|'approved'|'rejected'
    status          TEXT DEFAULT 'pending',  -- 'pending'|'approved'|'rejected'
    email_code      TEXT,                -- OTP 6 أرقام
    email_verified  BOOLEAN DEFAULT FALSE,
    phone           TEXT,
    phone_code      TEXT,                -- OTP 6 أرقام
    phone_verified  BOOLEAN DEFAULT FALSE,
    id_front_url    TEXT,                -- Supabase storage URL
    selfie_url      TEXT,                -- اختياري
    admin_note      TEXT,
    submitted_at    TIMESTAMP,
    reviewed_at     TIMESTAMP,
    UNIQUE(user_id)
)
```

**`verify_requests`** — توثيق بيانات فردية (خبرة/شهادة/دورة):

```sql
CREATE TABLE verify_requests (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    item_type    TEXT,       -- 'exp'|'edu'|'course'
    item_id      INTEGER,    -- id الخبرة/التعليم/الدورة
    item_title   TEXT,
    item_company TEXT,
    document_url TEXT,
    notes        TEXT,
    status       TEXT DEFAULT 'pending',  -- 'pending'|'verified'|'rejected'
    created_at   TIMESTAMP DEFAULT NOW()
)
```

### KYC Workflow (7 Steps)

```
1. POST /kyc/start          → step='email'
2. POST /kyc/email/send     → يُولّد email_code (OTP 6 أرقام)
3. POST /kyc/email/verify   → email_verified=TRUE, step='phone'
4. POST /kyc/phone/send     → يُولّد phone_code
5. POST /kyc/phone/verify   → phone_verified=TRUE, step='id_upload'
6. POST /kyc/docs           → id_front_url + selfie, step='review', submitted_at=NOW()
7. PUT /admin/kyc/{uid}/approve → status='approved', users.is_verified=TRUE
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/kyc/start` | JWT | يبدأ أو يُعيد العملية |
| GET | `/kyc/status/{user_id}` | None | حالة العملية الحالية |
| POST | `/kyc/email/send` | JWT | يُرسل OTP للإيميل |
| POST | `/kyc/email/verify` | JWT | يتحقق من الـ OTP |
| POST | `/kyc/phone/send` | JWT | يُرسل OTP للهاتف |
| POST | `/kyc/phone/verify` | JWT | يتحقق من الـ OTP |
| POST | `/kyc/docs` | JWT | رفع صور الهوية |
| POST | `/verify-request` | JWT | طلب توثيق بيانة فردية |
| GET | `/admin/kyc` | Admin | قائمة كل الطلبات |
| PUT | `/admin/kyc/{user_id}/approve` | Admin | موافقة + تفعيل الشارة |
| PUT | `/admin/kyc/{user_id}/reject` | Admin | رفض الطلب |
| GET | `/admin/verify-requests` | Admin | طلبات التوثيق الفردية |
| PUT | `/admin/verify/{req_id}` | Admin | تحديث حالة الطلب الفردي |

### Rules

```
✅ kyc_submissions 1:1 per user (UNIQUE user_id)
✅ شارة الـ is_verified تُمنح فقط بعد admin approve
✅ OTP codes: 6 أرقام عشوائية — لا انتهاء صلاحية في الـ DB
❌ لا تُوافق تلقائياً — الموافقة من Admin فقط
❌ الموظف لا يستطيع تعيين is_verified لنفسه
```

---

## [P1] 53. Profile Follows System

**Database Table: `profile_follows`**

```sql
CREATE TABLE profile_follows (
    id          SERIAL PRIMARY KEY,
    follower_id INTEGER NOT NULL REFERENCES users(id),
    followed_id INTEGER NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_profile_follow UNIQUE (follower_id, followed_id),
    CONSTRAINT no_self_follow    CHECK  (follower_id != followed_id)
)
-- Indexes:
-- idx_pf_followed ON profile_follows(followed_id)
-- idx_pf_follower ON profile_follows(follower_id)
```

### API Endpoints — Write

| Method | Path | Auth | Response |
|--------|------|------|----------|
| POST | `/profile/{user_id}/follow` | JWT | `{status, is_following: true, followers_count: <int>}` |
| DELETE | `/profile/{user_id}/follow` | JWT | `{status, is_following: false, followers_count: <int>}` |

### API Endpoints — Read (Paginated Lists)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/profile/{id}/followers?limit=20&offset=0` | None (Public) | من يتابع هذا الحساب |
| GET | `/profile/{id}/following?limit=20&offset=0` | None (Public) | من يتابعه هذا الحساب |

**Response Contract:**

```json
{
  "status": "success",
  "items": [
    {
      "id": 42,
      "tw_id": "U9620...",
      "display_name": "أحمد الخالد",
      "avatar_url": "https://...",
      "user_type": "emp",
      "profession": { "name_ar": "مطوّر برمجيات", "icon": "code" },
      "is_following": true,
      "can_follow": true,
      "followed_at": "2026-06-15T00:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "has_more": true,
    "total": 120
  }
}
```

**Pagination Rules:**
- `limit` default=20, max=50
- `offset` default=0
- `has_more = (offset + limit) < total`

**Permission Rules:**
- القوائم عامة — guest يستطيع الرؤية
- `is_following` = false للـ guest (لا JWT → لا EXISTS query)
- `can_follow` = false للـ guest + للـ owner على نفسه
- `can_follow` = true للـ logged-in public-user على أي حساب آخر

**No N+1 — EXISTS داخل نفس SELECT:**

```sql
SELECT u.id, ...,
  EXISTS(SELECT 1 FROM profile_follows v
         WHERE v.follower_id=:viewer_id AND v.followed_id=u.id) AS is_following
FROM profile_follows pf
JOIN users u ON u.id=pf.follower_id   -- (أو followed_id للـ following list)
LEFT JOIN profiles p ON p.user_id=u.id
LEFT JOIN profession_categories pc ON pc.id=p.profession_id
WHERE pf.followed_id=:profile_id
ORDER BY pf.created_at DESC
LIMIT :limit OFFSET :offset
```

### Backend Functions

| Function | Logic |
|----------|-------|
| `follow_profile(follower_id, followed_id)` | `INSERT ... ON CONFLICT DO NOTHING` (idempotent) — يُعيد `followers_count` |
| `unfollow_profile(follower_id, followed_id)` | `DELETE` idempotent — يُعيد `followers_count` |
| `get_profile_followers_count(followed_id)` | `COUNT(*)` |
| `is_profile_following(follower_id, followed_id)` | `bool` — هل العلاقة موجودة |
| `get_profile_followers_list(followed_id, viewer_id, limit, offset)` | قائمة المتابعين مع pagination + is_following |
| `get_profile_following_list(follower_id, viewer_id, limit, offset)` | قائمة المتابَعين مع pagination + is_following |

### following_count في /metrics

`GET /profile/{id}/metrics` يُعيد الآن:

```json
"metrics": {
  "followers_count": <int>,
  "following_count": <int>,
  ...
}
```

`following_count = COUNT(*) FROM profile_follows WHERE follower_id = :profile_id`

### Frontend — Follow List Modal + Followers Popover (Step 2)

**الملفات المعدَّلة:**
- `profile-v2.api.js`: `getFollowersList(profileId, limit, offset)` + `getFollowingList(profileId, limit, offset)`
- `profile-showcase.html`: `id="scStatFollowersTile"` + `scFlPopover` HTML + `scFollowListModal` HTML
- `profile-v2.render.js`: metrics polling لـ `following_count` + Popover IIFE + modal IIFE
- `profile-v2.css`: `.sc-fl-popover` + `.sc-fl-pop-*` + `.sc-fl-*` modal styles

**Stats Bar — عداد واحد فقط:**
- شريط الإحصائيات يعرض عداد واحد: `scStatFollowers` (followers_count)
- `scStatFollowingTile` لا يوجد — "يتابع" يظهر فقط داخل الـ Popover
- `scStatFollowersTile` — عند الضغط يفتح `scFlPopover`

**Followers Popover (`scFlPopover`):**
- `position:fixed` + `width:fit-content` — يُحسب موقعه via `getBoundingClientRect()` + `scrollY`
- تخطيط أفقي: زر "المتابعون" | divider | زر "يتابع"
- كل زر: icon فوق + count + label (نفس روح Stats Row)
- `scFlPopCountFollowers` — يُحدَّث من `followers_count` (metrics + initial load)
- `scFlPopCountFollowing` — يُحدَّث من `following_count` (metrics polling فقط)
- ألوان: المتابعون = بنفسجي `#8b5cf6` — يتابع = تركواز `#22d3ee`
- عداد المتابعون (`scStatFollowersTile`) لا يحصل على active/highlight state
- الـ Popover مؤقت: يُغلق بعد 5 ثوانٍ من عدم التفاعل (auto-hide)
- mouseenter على Popover يوقف مؤقت الـ auto-hide — mouseleave يُعيد تشغيله
- `min-width:160px; max-width:calc(100vw - 16px)` — يتكيف مع حجم المحتوى
- الضغط على أي زر → يُغلق الـ Popover → يفتح Modal بالتبويب المناسب
- الضغط خارج الـ Popover أو ESC أو الضغط مرة ثانية على الـ tile → يُغلقه

**Follow List Modal (`scFollowListModal`):**
- `scFlTabFollowers` / `scFlTabFollowing` — tab buttons with `_scFlSwitch(mode,el)` — يُعيد الفلتر إلى "الكل"
- `scFlFilters` — حاوية Filter Chips (rendered by JS after first fetch)
- `scFlList` — scrollable list container
- `scFlLoad` / `scFlLoadMore` — load more pagination
- يُفتح عبر `window._scFlOpen('followers' | 'following')`

**Filter Chips:**
- أنواع: `all` / `emp` / `co` / `edu`
- كل chip: اسم عربي + عدد compact
- الضغط على chip يُعيد: `_filter = type`, `_offset = 0`, fetch جديد
- تبديل التبويب (followers ↔ following): يُعيد الفلتر إلى "all"
- Chip مع count=0 → disabled (ما عدا "الكل")

**User Type Badge في القائمة:**
- `emp` → "موظف" بادج أخضر
- `co`  → "شركة" بادج أزرق
- `edu` → "مركز تعليم" بادج برتقالي
- لا يُعرض الكود الخام (emp/co/edu) للمستخدم

**Filter API Contract:**

```
GET /profile/{id}/followers?limit=20&offset=0&type=all
GET /profile/{id}/following?limit=20&offset=0&type=all

type values: all | emp | co | edu
invalid type → HTTP 400
```

**Response Contract (مع counts):**

```json
{
  "status": "success",
  "items": [...],
  "filter": { "type": "all" },
  "counts": { "all": 120, "emp": 80, "co": 25, "edu": 15 },
  "pagination": { "limit": 20, "offset": 0, "has_more": true, "total": 120 }
}
```

- `pagination.total` = عدد النتائج حسب الفلتر الحالي
- `counts.all` = المجموع الكلي دائماً
- عداد الشريط + Popover يستخدمان `/metrics.followers_count` (لا يتأثران بالفلتر)

**قواعد الـ Modal:**
- روابط العرض: `/u/{tw_id}` (ليس `/profile/{id}`)
- Follow button لا يظهر إذا `can_follow = false` (guest / owner)
- Follow toggle داخل Modal يستخدم `followProfile` / `unfollowProfile` الموجودَين
- ESC + click على overlay يُغلق الـ modal
- Offset-based pagination — `has_more` من Backend
- Filtering من Backend (ليس Frontend) — حفاظاً على صحة pagination
- Empty state: رسالة "لا توجد نتائج بعد"
- Avatar fallback: placeholder `<div>` + Lucide user icon

**ممنوعات:**
- لا يظهر `following_count` كـ tile مستقل في شريط الإحصائيات
- لا تُحذف `following_count` من `/metrics` — تُستخدم فقط داخل الـ Popover
- لا تُعمل الفلترة في Frontend فقط — يكسر pagination

### حالة التنفيذ

| الميزة | الحالة |
|--------|--------|
| POST/DELETE follow | ✅ |
| GET followers list | ✅ |
| GET following list | ✅ |
| following_count في /metrics | ✅ |
| Frontend Modal | ✅ |
| Followers Popover (compact UX) | ✅ |
| Filter by user_type (Backend + Frontend) | ✅ |
| User type badge in list items | ✅ |

### viewer_action for Follows (in GET /profile)

```json
{
  "is_following": <bool>,
  "followers_count": <int>
}
```

الـ Follow button مُوصَّل في `profile-v2.render.js` — `scFollowBtn` — مستقل عن `scFullBtn`.

### Rules

```
✅ self-follow محظور في الـ DB (CHECK) وفي الـ endpoint (400 error)
✅ follow/unfollow idempotent — آمنة للاستدعاء المتكرر
✅ followers_count يُعاد فوراً بعد الـ mutation لتحديث الـ UI
✅ Followers/Following lists عامة — لا تحتاج JWT للقراءة
✅ is_following per item بدون N+1 (EXISTS في نفس الـ SELECT)
❌ لا إشعار عند المتابعة (by design)
❌ لا تغيّر زر scFollowBtn من داخل Interest System (scFullBtn)
❌ لا تُرجع is_following=true للـ guest
❌ لا تُرجع can_follow=true للـ owner على نفسه
```

---

## [P1] 53a. Company Followers Modal

**Implemented in:** PR #295 (feat/company-followers-modal)

### Architecture Note — Two Follow Tables (Not Unified)

The platform has **two separate follow tables**:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `profile_follows` | Employee/user follows any user profile | `follower_id`, `followed_id` |
| `company_follows` | User follows a company | `follower_id`, `company_id` |

These tables are **not unified**. A migration to unify them is deferred to a future standalone PR with a clear migration plan. Do not attempt to merge them in an unrelated PR.

### Database Table: `company_follows`

```sql
-- Existing table (created in Phase 2)
company_follows: id PK, company_id FK(users.id), follower_id FK(users.id), created_at
  UNIQUE(company_id, follower_id)
  -- No DB-level self-follow CHECK (only server-level guard)
```

### API Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/company/{company_id}/followers?limit=20&offset=0&type=all` | None (public, optional JWT) | قائمة متابعي الشركة |

- `company_id` accepts numeric id or `tw_id` (resolved via `_resolve_company_id()`)
- `type` values: `all` \| `emp` \| `co` \| `edu` — invalid value → HTTP 400
- `limit` capped at 50; `offset` min 0
- Optional JWT: if provided, `is_following` per item is populated via `profile_follows` (cross-entity follow check)

**Response Contract:**

```json
{
  "status": "success",
  "items": [
    {
      "id": 42,
      "tw_id": "U9620...",
      "full_name": "أحمد الخالد",
      "user_type": "emp",
      "avatar_url": "https://...",
      "profession": { "name_ar": "مطوّر برمجيات", "icon": "code" },
      "is_following": true,
      "followed_at": "2026-06-15T00:00:00Z"
    }
  ],
  "filter": { "type": "all" },
  "counts": { "all": 120, "emp": 80, "co": 25, "edu": 15 },
  "pagination": { "limit": 20, "offset": 0, "has_more": true, "total": 120 }
}
```

### Backend Function

`get_company_followers_list(company_id, viewer_id, limit, offset, user_type="all")` in `auth.py`

- Mirrors `get_profile_followers_list` pattern
- `is_following` = EXISTS in `profile_follows` (viewer → follower) — no N+1
- `viewer_id = None` for unauthenticated requests → `is_following = FALSE`

### Frontend — Company Followers Modal

**Files:**
- `static/company/company.api.js` — `getCompanyFollowersList(companyId, limit, offset, type)`
- `static/company/company.main.js` — Company Followers Modal IIFE (open/close/fetch/render) + Soft Refresh IIFE
- `static/company/company.css` — `.co-fl-*` styles + `.co-stat-clickable`
- `company-profile.html` — `#coStatFollowersTile` (clickable) + `#coFollowListModal` (HTML structure)

**Behaviour:**
- Clicking `#coStatFollowersTile` → `_open()` → resets state → fetches first page
- Bottom-sheet on mobile (≤539px), centered panel on desktop (≥540px)
- Filter chips: `all` / `emp` / `co` / `edu` — filtering done server-side (preserves pagination correctness)
- Load More: offset-based, `has_more` from backend
- Per-item follow button: calls `POST/DELETE /profile/{uid}/follow` (cross-entity follow via `profile_follows`)
- Soft Refresh: `loadData({silent:true})` every 30 s, paused while tab is hidden (`visibilitychange`)
- Close: `#coFlClose` button, backdrop click, ESC key

**Single Tab Only:**
The modal has no "يتابع" tab because companies do not follow other users. Any future addition of company-follows-company must be a separate PR.

### ممنوعات

```
❌ لا تُضيف تبويب "يتابع" لشركة (الشركات لا تتابع حسابات أخرى)
❌ لا تستخدم profile_follows لبيانات متابعي الشركة
❌ لا تدمج company_follows و profile_follows في هذا السياق
❌ لا تعمل DB migration لتوحيد الجدولين إلا في PR مستقل بخطة واضحة
❌ لا تعرض followers_count من localStorage — استخدم companyState.stats.followers_count فقط
```

---

## [P2] 53b. Company Rating Modal

**Implemented in:** PR feat/company-rating-modal

### Purpose

Clicking the rating stat tile (`#coStatRatingTile`) opens a modal with:
- Overall average + star display + total count
- Score distribution (1–5 bars with percentages)
- Up to 5 recent comments (score + text — **no rater names for privacy**)
- Rate CTA (only shown when `companyState.permissions.can_rate === true`)

### Database Table: `company_ratings`

```sql
company_ratings: id PK, company_id FK(users.id), rater_id FK(users.id),
  score INT CHECK(1..5), comment TEXT, created_at, updated_at
  UNIQUE(company_id, rater_id)  -- UPSERT behaviour
  -- No self-rate at server level (rater_id ≠ company_id)
```

### API Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/company/{company_id}/ratings?limit=5` | None (public, optional JWT) | تفاصيل تقييمات الشركة |

- `company_id` accepts numeric id or `tw_id` (resolved via `_resolve_company_id()`)
- Optional JWT: if provided, `my_rating` (viewer's own score) is populated
- `limit` controls number of recent comments returned (default 5)

**Response Contract:**

```json
{
  "status": "success",
  "rating_avg": 4.2,
  "rating_count": 87,
  "distribution": { "5": 40, "4": 25, "3": 12, "2": 7, "1": 3 },
  "recent_comments": [
    { "score": 5, "comment": "شركة ممتازة", "created_at": "2026-06-20T00:00:00Z" }
  ],
  "my_rating": 4
}
```

> **Privacy rule:** `recent_comments` never includes rater name or user_id. Only `score`, `comment`, `created_at`.

### Backend Function

`get_company_ratings_detail(company_id, viewer_id=None, limit=5)` in `auth.py`

- Returns `rating_avg` (rounded 1dp), `rating_count`, `distribution` (dict keyed 1–5), `recent_comments` (list, no rater name), `my_rating` (int or null)
- `viewer_id = None` → `my_rating = null`

### Frontend

**Files:**
- `static/company/company.api.js` — `getCompanyRatingsDetail(companyId, limit)`
- `static/company/company.main.js` — Rating Modal IIFE (open/close/fetch/render/star-picker/submit)
- `static/company/company.css` — `.co-rat-*` styles (reuses `.co-fl-overlay/.co-fl-panel` shell)
- `company-profile.html` — `#coStatRatingTile` (clickable tile) + `#coRatingModal` (HTML structure)

**Behaviour:**
- Clicking `#coStatRatingTile` → `_open()` → shows modal → fetches `getCompanyRatingsDetail`
- Renders summary → distribution → recent comments → rate section
- Rate section visible only when `companyState.permissions.can_rate === true`
- Star picker: hover highlights, click selects, calls `POST /company/rate/{id}`
- After successful rating: updates `companyState.stats.rating_avg/count` optimistically → calls `renderStats()` → re-fetches modal
- Close: `#coRatClose` button, backdrop click, ESC key
- Reuses `.co-fl-overlay/.co-fl-panel/.co-fl-head/.co-fl-close/.co-fl-spin/.co-fl-empty` — no duplication

### ممنوعات

```
❌ لا تعرض اسم المُقيِّم في recent_comments (حماية الخصوصية)
❌ لا تستخدم X-User-Id في fetch calls — Bearer JWT فقط
❌ لا تعرض زر التقييم لغير المستحقين (can_rate من companyState.permissions)
❌ لا تُضيف تبويب "التقييمات" — حُذف في Phase 1 (PR #301)
❌ لا تفتح هذا الـ modal من أي مكان غير #coStatRatingTile
```

---

## [P1] 54. QR Card System

**File:** `profile-v2.qr.js`

### Library

`QRCode.js` — تُحمَّل من `/static/qrcode.min.js`

### Template

```
URL:  /static/img/qr-card-template-ar-v2.png?v=2
Size: 1800 × 1800 pixels (fixed Arabic template)
```

### Canvas Compositing Coordinates

```javascript
QR_X       = 170    // QR code left edge
QR_Y       = 439    // QR code top edge
QR_SIZE    = 700    // QR width and height (pixels)
CARD_CY    = 1412   // Vertical center for name text
NAME_LEFT  = 120    // Name text left boundary
NAME_RIGHT = 1620   // Name text right boundary
// Font: Cairo → Noto Sans Arabic → Arial
// Font size range: 68px (max) → 28px (min, auto-shrink)
```

### Lock Pattern — `_qrDownloading` flag

```javascript
var _qrDownloading = false;  // Global singleton lock
var _qrClickCount  = 0;      // Debug counter

if(_qrDownloading){ return; }  // Skip concurrent call
_qrDownloading = true;
```

### Watchdog Timeout

```javascript
_qrWatchdog = setTimeout(function(){
  _release(null);  // Force-release after 15 seconds
}, 15000);
```

### `_release()` — Idempotent Guard

```javascript
function _release(errMsg){
  if(!_qrDownloading) return;  // Safe to call multiple times
  clearTimeout(_qrWatchdog);
  _qrWatchdog    = null;
  _qrDownloading = false;
  // ... cleanup hidden container
}
```

### Why `a.click()` Only — NOT `dispatchEvent`

```javascript
a.click();  // ✅ الطريقة الوحيدة التي تُطلق <a download> في المتصفحات

// ❌ dispatchEvent(new MouseEvent('click', {bubbles:true}))
// لا تُطلق سلوك <a download> — تُكسر التحميل في جميع المتصفحات
```

### Hidden Container Pattern

```javascript
var _QR_HIDDEN_ID = '__qrHiddenContainer';
// div يُضاف في left:-9999px — خارج الشاشة
// QRCode.js يرسم داخله، ثم يُستخرج الـ canvas
// innerHTML='' لتنظيف بعد كل عملية
```

### Rules

```
✅ لا تستخدم dispatchEvent لتشغيل <a download>
✅ حرّر الـ lock بعد a.click() مباشرةً
✅ الـ watchdog يمنع lock بدون نهاية
❌ لا تغيّر QR URL بدون تحديث _scQrUrl في state
❌ لا تغيّر template URL بدون تحديث الإحداثيات
```

---

## [P3] 55a. Company Saved Candidates

**Implemented in:** PR feat/company-saved-candidates

### Purpose

Allows company owners to privately save employee profiles as candidates for future reference. List is strictly private — never exposed to guests, employees, or other companies. Backend in Phase 3 (PR #304); Frontend button + modal in Phase 4 (PR feat/company-candidates-modal).

### Frontend — Candidates Button + Modal (Phase 4)

**Files:**
- `company-profile.html` — `#candidatesBtn` (owner-only, inside `.jobs-owner-toolbar`) + `#coCandidatesModal` (modal HTML)
- `static/company/company.api.js` — `getSavedCandidatesCount()`, `getSavedCandidates(limit, offset)`, `deleteSavedCandidate(candidateId)` + hook in `loadData()`
- `static/company/company.main.js` — Candidates Modal IIFE
- `static/company/company.css` — `.co-cand-*` styles + `.co-cand-badge`

**Behaviour:**
- Badge `#candidatesBadge` loaded via `_loadCandidatesBadge()` hook in `loadData()` success callback
- Badge hidden when count=0, shown with actual number when count>0 (max "99+")
- Clicking `#candidatesBtn` → `_open()` → fetches `getSavedCandidates(50, 0)` → renders list
- Each item: avatar + name + profession + city/country + saved date + "فتح البروفايل" (→ `/u/{tw_id}`) + "إزالة" button
- "إزالة" → `deleteSavedCandidate(id)` → fades row out → updates badge → empty state if list is now empty
- Modal tab bar structured for Phase 5 "اقتراحات" tab addition without rebuild
- Close: `#coCandClose`, backdrop click, ESC key
- `_isOwner()` guard on every action: checks `companyState.permissions.can_edit`

### Database Table: `company_saved_candidates`

```sql
company_saved_candidates:
  id           BIGSERIAL PRIMARY KEY,
  company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id       INTEGER NULL REFERENCES jobs(id) ON DELETE SET NULL,
  status       TEXT NOT NULL DEFAULT 'saved',
  notes        TEXT,
  saved_by     INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_saved_candidate UNIQUE (company_id, candidate_id)
  -- candidate_id must be user_type='emp' (enforced server-side, not DB constraint)
  -- company_id must be user_type='co' (enforced via JWT check in endpoints)
```

**Indexes:** `idx_saved_cands_company(company_id)`, `idx_saved_cands_candidate(candidate_id)`

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/company/saved-candidates` | JWT (co only) | قائمة المرشحين المحفوظين |
| GET | `/company/saved-candidates/count` | JWT (co only) | عدد المرشحين (للـ badge) |
| POST | `/company/saved-candidates/{candidate_id}` | JWT (co only) | حفظ مرشح (UPSERT) |
| DELETE | `/company/saved-candidates/{candidate_id}` | JWT (co only) | حذف مرشح |
| PATCH | `/company/saved-candidates/{candidate_id}` | JWT (co only) | **Phase 6A** — تحديث status / notes / job_id |

**Authorization:**
- JWT is mandatory (no optional auth)
- `user_type` must be `co` — 403 for all other types
- `company_id` is derived from `token["user_id"]` — **no cross-company access possible**
- `_require_company_owner(token)` helper centralizes this check

**Response Contracts:**

```json
// GET /company/saved-candidates
{
  "status": "success",
  "count": 12,
  "items": [
    {
      "candidate_id": 3,
      "tw_id": "U9620...",
      "full_name": "اسم الموظف",
      "avatar_url": "...",
      "profession": "محاسب",
      "city": "عمان",
      "country": "الأردن",
      "job_id": null,
      "status": "saved",
      "notes": null,
      "created_at": "2026-06-30T..."
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "has_more": false, "total": 12 }
}

// GET /company/saved-candidates/count
{ "status": "success", "count": 12 }

// POST /company/saved-candidates/{id}
{ "status": "success", "saved": true, "count": 13 }

// DELETE /company/saved-candidates/{id}
{ "status": "success", "saved": false, "count": 12 }
```

### Backend Functions (`auth.py`)

| Function | Description |
|----------|-------------|
| `_migrate_company_saved_candidates()` | CREATE TABLE IF NOT EXISTS + indexes (idempotent) |
| `save_company_candidate(company_id, candidate_id, saved_by, job_id, notes)` | UPSERT — raises ValueError if candidate not `emp` |
| `remove_company_candidate(company_id, candidate_id)` | DELETE + return count |
| `get_company_saved_candidates(company_id, limit, offset)` | Paginated list — no sensitive fields |
| `get_company_saved_candidates_count(company_id)` | Count only (badge) |
| `update_company_saved_candidate(company_id, candidate_id, updates)` | **Phase 6A** — partial update status/notes/job_id, returns safe item |
| `get_company_candidate_suggestions(company_id, limit, offset, include_saved)` | **Phase 5A** — scored suggestions based on active jobs |

**Safe fields returned:**
`candidate_id, tw_id, full_name, avatar_url, profession (from profession_categories), city, country, job_id, status, notes, created_at`

**Withheld fields (privacy):**
`email, phone, location (detailed), password_hash, any KYC data`

### ممنوعات

```
❌ لا تُرجع هذه القائمة لأي مستخدم غير صاحب الشركة
❌ لا تعتمد على CSS أو Frontend لحماية البيانات — الحماية في Backend فقط
❌ لا تُضيف company_id كـ query param مفتوح — company_id يأتي من JWT دائماً
❌ لا تُخزن email أو phone في الرد
❌ لا تسمح بحفظ شركة أو جهة تعليمية كمرشح (user_type != 'emp' → 400)
❌ لا تخلط هذا النظام مع التبويبات العامة لصفحة الشركة
❌ لا تضف Frontend في هذا الـ PR — هذه مرحلة 3 (Backend فقط)
```

---

## [P3] 55b. Company Candidate Suggestions — Phase 5A Backend

**Implemented in:** PR feat/company-candidate-suggestions (Phase 5A) + PR feat/phase-5b-suggestions-tab (Phase 5B)
**Status:** Complete — Backend (Phase 5A) + Frontend tab in candidates modal (Phase 5B).

### Purpose

Provides scored employee profile suggestions to a company owner based on its active job postings. Uses existing job taxonomy (profession_id, job_profession_targets, skills) to rank employees by relevance. No new DB table introduced.

### Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/company/candidate-suggestions` | JWT (co only) | اقتراحات مرشحين مرتبة حسب match_score |

**Query params:**
- `limit` — int, default 20, max 50
- `offset` — int, default 0
- `include_saved` — bool, default false (exclude already-saved candidates)

### Scoring Algorithm (max 100)

| Signal | Points | Source |
|--------|--------|--------|
| Candidate profession_id matches any active job's primary `profession_id` | +45 | `jobs.profession_id` |
| Candidate profession_id is in `job_profession_targets` for any active job (secondary, not already primary-matched) | +35 | `job_profession_targets` |
| Skill overlap between candidate skills and job required skills (scaled: 1 skill→+5, 4+→+20) | +20 max | `user_skills` + `profiles.skills[]` |
| City or country match with company location | +10 | `profiles.city/country` |
| Profile quality (has headline +5, avail=looking +5) | +10 max | `profiles.headline/avail` |

**Total max:** 100 (capped with `min(100, score)`)

### Data Sources

All existing tables — no new table created:
- `jobs` — active jobs, primary profession_id, skills[], accepts_all_professions
- `job_profession_targets` — secondary accepted profession IDs
- `profession_categories` — profession names for display
- `profiles` — candidate city, country, avail, skills[], headline, profession_id
- `user_skills` — normalized skills with level (merged with profiles.skills[])
- `company_saved_candidates` — used to flag/exclude already-saved candidates

### Security & Privacy

- JWT mandatory. `user_type` must be `co` — 403 for all others.
- `company_id` derived exclusively from `token["user_id"]`. No query param accepted.
- Cross-company access structurally impossible: company A cannot see company B's suggestions.
- Excluded fields: `email, phone, dob, location (detailed), password_hash`
- Excluded user types: `co`, `edu` — only `emp` candidates appear
- Already-saved candidates: excluded by default (`include_saved=false`)

### Empty State (no active jobs)

```json
{
  "status": "no_jobs",
  "message": "لا توجد اقتراحات بعد — انشر وظيفة أولاً لتحسين الاقتراحات.",
  "items": [], "count": 0,
  "pagination": { "limit": 20, "offset": 0, "has_more": false, "total": 0 }
}
```

### Response Contract

```json
{
  "status": "success",
  "count": 8,
  "items": [
    {
      "candidate_id": 8,
      "tw_id": "U9620...",
      "full_name": "اسم الموظف",
      "avatar_url": "...",
      "profession": "محاسب",
      "city": "عمان",
      "country": "الأردن",
      "match_score": 82,
      "match_reasons": [
        "تخصصه يطابق إحدى وظائفك",
        "يمتلك 3 مهارات مشتركة",
        "في نفس المدينة",
        "يبحث عن فرص عمل"
      ],
      "is_saved": false
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "has_more": false, "total": 8 }
}
```

### Performance Notes

- SQL pre-filter: candidates filtered by `profession_id IN (...)` before scoring (unless job `accepts_all_professions=true`)
- Hard cap: fetches max 500 candidates before Python scoring (sufficient for platform scale)
- Scoring runs in Python after 3 batch SQL queries (no N+1)
- Scoring is idempotent and stateless — no cache needed for v1

### Phase 5B — Frontend Tab (PR feat/phase-5b-suggestions-tab)

Added inside the candidates modal (`#coCandidatesModal`) only. No changes to company page tabs.

**Files changed:**
- `company-profile.html` — added `<button data-tab="suggestions">اقتراحات مناسبة</button>` in `#coCandTabs`
- `static/company/company.api.js` — `getCandidateSuggestions(limit, offset)`, `saveSuggestedCandidate(candidateId)`
- `static/company/company.main.js` — tab state machine (`_activeTab`, `_switchTab`), suggestions fetch/render/append/wire
- `static/company/company.css` — `.co-sugg-score`, `.co-sugg-chip`, `.co-sugg-save-btn`, `.co-sugg-load-more`, `.co-sugg-name-row`, `.co-sugg-reasons`

**Behavior:**
- Modal opens on "المحفوظون" tab (unchanged default)
- Switching to "اقتراحات مناسبة": calls `GET /company/candidate-suggestions?limit=20&offset=0`
- Each suggestion shows: avatar + name + match_score badge + meta + reason chips + "فتح البروفايل" + "حفظ كمرشح"
- "حفظ كمرشح" → `POST /company/saved-candidates/{id}` → fade-out item → update badge → empty state if list empty
- "عرض المزيد" → increments offset and appends results
- Empty state if no active jobs (status=no_jobs): "انشر وظيفة أولاً لتحسين الاقتراحات."
- Empty state if no matches: "لا توجد اقتراحات إضافية حالياً"

### ممنوعات

```
❌ لا تُضيف company_id كـ query param — يأتي من JWT فقط
❌ لا تُرجع email أو phone
❌ لا تُنشئ جدول جديد للاقتراحات — الأنظمة الموجودة كافية
❌ لا تُضيف AI أو embeddings قبل decision صريح من المستخدم
❌ لا تعرض اقتراحات عشوائية بدون وظائف active
❌ لا تُعدِّل نظام /jobs/match الموجود
❌ لا تضف تبويب عام في صفحة الشركة — الاقتراحات داخل المودال فقط
❌ لا تستدعي endpoint الاقتراحات لغير المالك
```

---

## [P3] 55c. Company Candidate Pipeline — Phase 6A Backend

**Implemented in:** PR feat/company-candidate-pipeline-backend (Phase 6A)
**Status:** Backend only. Frontend pipeline UI comes in Phase 6B.

### Purpose

Allows company owners to manage the pipeline state of each saved candidate: update status (from `saved` → `shortlisted` → `contacted` → `interview` → `hired`/`rejected`), add private notes, and optionally link to a specific job posting.

### New Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PATCH | `/company/saved-candidates/{candidate_id}` | JWT (co only) | Partial update of status / notes / job_id |

**Request body (all fields optional — only sent fields are updated):**
```json
{
  "status": "shortlisted",
  "notes":  "مناسب لوظيفة المحاسب، تواصل لاحقاً",
  "job_id": 12
}
```

### Pipeline Statuses

| Value | Label (AR) |
|-------|-----------|
| `saved` | محفوظ |
| `shortlisted` | مرشح قوي |
| `contacted` | تم التواصل |
| `interview` | مقابلة |
| `hired` | تم التوظيف |
| `rejected` | غير مناسب |

Defined in `auth.py` as `VALID_CANDIDATE_STATUSES` (frozenset) and `CANDIDATE_STATUS_LABELS` (dict).

### Validation Rules

| Field | Rule |
|-------|------|
| `status` | Must be one of 6 allowed values. Cannot be null/missing if sent. |
| `notes` | Optional. Max 500 chars after strip. Empty string/null → stored as NULL. |
| `job_id` | Optional. If non-null: must exist in `jobs` table AND belong to the same company. null → detach from job. |

### Security

- JWT mandatory, `user_type='co'` — enforced by `_require_company_owner(token)`
- `company_id` from token only — no body/query param accepted
- Cross-company update structurally impossible: `WHERE company_id=:cid AND candidate_id=:uid`
- job_id validated as belonging to the same company
- Returns 404 if candidate is not in this company's saved list (not found vs access denied: safe)

### Response Contract

```json
// PATCH /company/saved-candidates/{candidate_id}
{
  "status": "success",
  "item": {
    "candidate_id": 8,
    "tw_id": "U9620...",
    "full_name": "اسم الموظف",
    "avatar_url": "...",
    "profession": "محاسب",
    "city": "عمان",
    "country": "الأردن",
    "job_id": 12,
    "status": "shortlisted",
    "status_label": "مرشح قوي",
    "notes": "مناسب لوظيفة المحاسب",
    "created_at": "2026-06-30T...",
    "updated_at": "2026-06-30T..."
  }
}
```

**Withheld fields:** email, phone, dob, detailed location, password_hash

### Data Layer (`auth.py`)

`update_company_saved_candidate(company_id, candidate_id, updates: dict)`
- `updates` keys: any subset of `{status, notes, job_id}`
- Validates → builds dynamic SET clause → updates → returns safe item
- Returns `None` if row not found (endpoint maps to 404)

### ممنوعات

```
❌ لا تُضيف company_id في body/query — يأتي من JWT فقط
❌ لا تسمح بـ job_id من شركة أخرى
❌ لا تسمح لموظف أو زائر باستخدام هذا endpoint
❌ لا تضف جدول جديد — company_saved_candidates يكفي
❌ لا تغيّر status_labels بدون تحديث VALID_CANDIDATE_STATUSES و CANDIDATE_STATUS_LABELS معاً
```

---

## [P3] 55d. Company Candidate Pipeline — Phase 6B Frontend

**Implemented in:** PR feat/company-candidate-pipeline-ui (Phase 6B)
**Status:** Frontend only. Backend PATCH endpoint from Phase 6A unchanged.

### Purpose

Adds a pipeline management UI inside the "المحفوظون" tab of `#coCandidatesModal`. Company owners can update status, add private notes, and link a saved candidate to an active job — all without leaving the modal.

### Files Changed

| File | Change |
|------|--------|
| `static/company/company.api.js` | Added `updateSavedCandidate(candidateId, payload)` → PATCH |
| `static/company/company.main.js` | Rewrote saved-tab render + wiring; added manage panel logic |
| `static/company/company.css` | Added `.co-cand-saved-card`, `.co-cand-top`, `.co-cand-status--*`, panel styles |

### Card Structure (saved tab)

Each saved candidate is now a `.co-cand-saved-card` (column-flex) containing:
1. **`.co-cand-top`** — horizontal row: avatar + info + action buttons
   - Info shows: name, meta (profession/city/country), date + **status badge**, notes preview (2-line clamp), job ref
   - Actions: "فتح البروفايل" | **"إدارة" (NEW)** | "إزالة"
2. **`.co-cand-manage-panel`** — inline panel below the row (hidden by default, toggle with "إدارة")
   - Status `<select>` — locked to 6 valid values
   - Notes `<textarea maxlength="500">` + live char counter (`0 / 500`)
   - Job `<select>` (optional — sourced from `companyState.jobs` open jobs only, no new endpoint)
   - "حفظ التعديل" / "إلغاء" buttons

### Status Badge Colors

| Status | Color |
|--------|-------|
| `saved` | Gray (#94a3b8) |
| `shortlisted` | Blue (#6699ff) |
| `contacted` | Purple (#a78bfa) |
| `interview` | Amber (#fbbf24) |
| `hired` | Teal (#00c896) |
| `rejected` | Red (rgba(255,100,100,.8)) |

### Behavior Rules

- **One panel open at a time:** opening a panel closes any other open panel
- **No optimistic updates:** card only updates after server responds 200 OK
- **In-place update via `_applyCardUpdate(card, data)`:** updates badge, notes preview, job ref without re-rendering the full list
- **Job select:** reuses `companyState.jobs` filtered to `status === 'open'` — no new backend call
- **Notes limit:** `maxlength="500"` on textarea + server-side validation. Counter updates on `input` event
- **Event delegation on `_body`:** single `click` listener handles remove, manage, panel save, panel cancel

### API Wrapper

```js
updateSavedCandidate(candidateId, payload)
// PATCH /company/saved-candidates/{candidateId}
// payload: { status?, notes?, job_id? }
// returns: { ok, status, data: { status: "success", item: {...} } }
```

### ممنوعات (Phase 6B)

```
❌ لا تعرض notes أو manage panel للزوار أو الموظفين (الحماية: المودال نفسه owner-only)
❌ لا تحدّث البطاقة محلياً قبل نجاح السيرفر
❌ لا تضيف endpoint جديد فقط لأسماء الوظائف — استخدم companyState.jobs
❌ لا تغيّر قائمة الحالات في الـ frontend بدون تحديث VALID_CANDIDATE_STATUSES في auth.py
❌ لا تلمس تبويب الاقتراحات أو نظام الحذف أو badge المرشحون
```

---

## [P3] 55e. Company Candidate Filters & Stats — Phase 7A Backend

**Implemented in:** PR feat/company-candidate-filters-stats-backend (Phase 7A)
**Status:** Backend only. Frontend filter UI comes in Phase 7B.

### Purpose

Adds filtering, search, sorting, and pipeline statistics to the saved-candidates system. Company owners can filter their saved list by status, job, or free-text search, and retrieve per-status counts for a dashboard view.

### Updated Endpoint

| Method | Path | Auth | Change |
|--------|------|------|--------|
| GET | `/company/saved-candidates` | JWT (co only) | Now accepts filter query params (backward-compatible) |
| GET | `/company/saved-candidates/stats` | JWT (co only) | **New** — pipeline statistics |

#### New Query Params for `GET /company/saved-candidates`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Pipeline status filter (must be valid) |
| `job_id` | int | — | Filter by linked job (must belong to this company) |
| `unlinked` | bool | `false` | Only show candidates with no job_id |
| `q` | string | — | Search in full_name, tw_id, profession, city, country (max 80 chars) |
| `sort` | string | `updated_desc` | Sort order |
| `limit` | int | 20 | Max 50 |
| `offset` | int | 0 | Pagination offset |

**`status` + `job_id` / `unlinked` are mutually exclusive** with each other only for job/unlinked.
**`job_id` and `unlinked=true` cannot be combined** (400).

#### Sort Values (`VALID_CANDIDATE_SORTS`)

| Value | Order |
|-------|-------|
| `updated_desc` | Latest updated first (default) |
| `updated_asc` | Oldest updated first |
| `created_desc` | Latest saved first |
| `created_asc` | Oldest saved first |
| `name_asc` | Alphabetical by name |
| `status_asc` | Alphabetical by status value |

#### Updated Response Shape

```json
{
  "status": "success",
  "count": 3,
  "items": [...],
  "pagination": {
    "limit": 20, "offset": 0,
    "has_more": false,
    "total": 3
  },
  "filters": {
    "status": "shortlisted",
    "job_id": null,
    "unlinked": false,
    "q": null,
    "sort": "updated_desc"
  }
}
```

**`count` = `pagination.total` = filtered total.** When no filters applied, equals full list count (badge-safe). The `/count` endpoint remains unchanged for unfiltered badge reads.

**`updated_at`** is now included in each item (was absent before).

#### Stats Endpoint Response

```json
// GET /company/saved-candidates/stats
{
  "status": "success",
  "total": 14,
  "by_status": {
    "saved": 5,
    "shortlisted": 3,
    "contacted": 2,
    "interview": 1,
    "hired": 1,
    "rejected": 2
  },
  "with_job": 6,
  "unlinked": 8
}
```

All 6 statuses always present (zero-filled). No candidate data — counts only.

### Data Layer (`auth.py`)

| Function | Description |
|----------|-------------|
| `get_company_saved_candidates_filtered(company_id, limit, offset, status, job_id, unlinked, q, sort)` | Filtered paginated list. Raises `ValueError` if job_id doesn't belong to this company |
| `get_company_saved_candidates_stats(company_id)` | Pipeline statistics |
| `VALID_CANDIDATE_SORTS` | Dict of allowed sort keys → ORDER BY expressions |

### Security

| Rule | Enforcement |
|------|-------------|
| JWT Bearer only | `_require_company_owner(token)` |
| `company_id` from token | Never from query or body |
| `job_id` ownership | Pre-validated via DB check before filtering |
| `status` allowlist | Validated against `VALID_CANDIDATE_STATUSES` (400 if invalid) |
| `sort` allowlist | Validated against `VALID_CANDIDATE_SORTS` keys (400 if invalid) |
| `q` injection prevention | Values are SQL-parameterized — ORDER BY uses pre-validated dict only |
| Privacy | Never returns email, phone, dob, detailed location |

### Backward Compatibility

- `GET /company/saved-candidates` with no params = identical to previous behavior
- `GET /company/saved-candidates/count` — unchanged (always unfiltered total, for badge)
- POST / DELETE / PATCH `/{candidate_id}` — unchanged
- `GET /company/candidate-suggestions` — unchanged

### ممنوعات (Phase 7A)

```
❌ لا تضف Frontend في Phase 7A — الـ UI يأتي في Phase 7B
❌ لا تستخدم company_id من query أو body
❌ لا تُغيّر معنى /count endpoint — يبقى unfiltered total للـ badge
❌ لا تسمح بـ ORDER BY تعتمد على قيم مستخدم مباشرة — استخدم VALID_CANDIDATE_SORTS dict فقط
❌ لا تبحث داخل notes — حقل خاص للشركة لا يُعرَّض للبحث
❌ لا تضف جدول جديد
```

---

## [P3] 55f. Company Candidate Filters & Stats — Phase 7B Frontend

**Implemented in:** PR feat/company-candidate-filters-ui (Phase 7B)

**Files modified:**
- `static/company/company.api.js` — updated `getSavedCandidates` + added `getSavedCandidatesStats`
- `static/company/company.main.js` — filter bar, chips, search, sort, load more inside saved tab
- `static/company/company.css` — `.co-cand-filter-bar`, `.co-cand-chip`, `.co-cand-search`, `.co-cand-sort-sel`, `.co-cand-load-more`

### API changes

| Function | Change |
|----------|--------|
| `getSavedCandidates(limit, offset, filters)` | Added `filters` param — appends `status`, `q`, `sort`, `job_id`, `unlinked` to query string |
| `getSavedCandidatesStats()` | New — `GET /company/saved-candidates/stats`, returns `{total, by_status, with_job, unlinked}` |

### Saved Tab State (module-level)

| Variable | Purpose |
|----------|---------|
| `_savedOffset` | Pagination offset for load more |
| `_savedLoading` | Prevents concurrent page fetches |
| `_savedFilter` | Active filter: `null`=all, status string, or `'_unlinked'` |
| `_savedSearch` | Active search query (max 80 chars) |
| `_savedSort` | Active sort key (default `updated_desc`) |
| `_savedStats` | Last loaded stats object from `/stats` endpoint |
| `_savedDebTimer` | setTimeout handle for 300ms search debounce |

### Filter Bar Structure (`_savedShellHTML`)

```
#coCandSavedShell
  .co-cand-filter-bar
    #coCandChips          ← 8 chips: الكل + 6 statuses + بدون وظيفة
    .co-cand-search-row
      #coCandSearch       ← debounced text input (300ms)
      #coCandSortSel      ← 6 sort options, default updated_desc
  #coCandSavedList        ← cards render here (not full _body)
  #coCandSavedLoadMore    ← appended conditionally when has_more=true
```

### Filter Chips (8 total)

| chip data-filter | Label | Count source |
|-----------------|-------|--------------|
| `""` (null) | الكل | `stats.total` |
| `saved` | محفوظ | `stats.by_status.saved` |
| `shortlisted` | مرشح قوي | `stats.by_status.shortlisted` |
| `contacted` | تم التواصل | `stats.by_status.contacted` |
| `interview` | مقابلة | `stats.by_status.interview` |
| `hired` | تم التوظيف | `stats.by_status.hired` |
| `rejected` | غير مناسب | `stats.by_status.rejected` |
| `_unlinked` | بدون وظيفة | `stats.unlinked` |

### Badge Update Rule

Badge is always updated from `stats.total` (unfiltered) — never from `res.data.count` (filtered). This keeps the badge accurate regardless of active filter.

### Empty States (8 messages)

| Filter | Title |
|--------|-------|
| null (all) | لا يوجد مرشحون محفوظون بعد |
| saved | لا يوجد مرشحون بحالة "محفوظ" |
| shortlisted | لا يوجد مرشحون مرشحون قوياً |
| contacted | لا يوجد مرشحون تم التواصل معهم |
| interview | لا يوجد مرشحون في مرحلة المقابلة |
| hired | لا يوجد مرشحون تم توظيفهم |
| rejected | لا يوجد مرشحون بحالة "غير مناسب" |
| _unlinked | لا يوجد مرشحون بدون وظيفة |
| q search active | لا نتائج للبحث عن "…" |

### Stats Refresh Triggers

| Event | Action |
|-------|--------|
| Delete card | `_loadSavedStats(null)` → updates badge + chips |
| PATCH status change | `_loadSavedStats(null)` → updates badge + chips |
| PATCH with filter mismatch | Card fades out + shows empty state if list is now empty |

### Forbidden Patterns (Phase 7B)

```
❌ لا تُحدِّث الـ badge من res.data.count — استخدم stats.total فقط
❌ لا تضع filter bar خارج #coCandSavedShell — يجب أن يكون داخل _body
❌ لا تستبدل _body.innerHTML بعد بناء الـ shell — استخدم #coCandSavedList فقط
❌ لا تضف infinite scroll — load more button فقط (explicit click)
❌ لا تضف ORDER BY بدون تمريره لـ filters.sort → GET /company/saved-candidates
❌ لا تبحث في notes (server-side الـ q يبحث في full_name/tw_id/profession/city/country فقط)
```

---

## [P3] 55g. Company Candidate Modal UI Polish

**Implemented in:** PR fix/candidate-modal-ui-polish  
**Type:** Frontend-only — no API, no backend, no DB schema changes.

**Files modified:**
- `static/company/company.main.js` — custom dark picker helpers + chip icons/classes + updated event delegation
- `static/company/company.css` — grid chips, rectangular shape, per-status colors, `.co-dp-*` picker styles, slate manage button

### Custom Dark Picker (`.co-dp-*`)

Replaces all native `<select>` inside `#coCandidatesModal` with inline-expanding dark pickers. No floating/absolute positioning — expands as a block below the trigger button (mobile-safe, no z-index/overflow issues).

| Picker | Class | Location |
|--------|-------|---------|
| Sort | `.co-cand-sort-dp` | Filter bar in saved tab shell |
| Status | `.co-cand-dp-status` | Manage panel per card |
| Job (if open jobs exist) | `.co-cand-dp-job` | Manage panel per card |

**How it works:**
- Trigger: `<button class="co-dp-btn">` shows current label + chevron SVG
- List: `<div class="co-dp-list">` expands/collapses on click (inline, not absolute)
- Options: `<button class="co-dp-opt">` with checkmark SVG hidden until `.selected`
- State: `data-selected` attribute on `.co-dp-wrap` — read by `_handlePanelSave()`
- Delegation: `_onSavedClick()` handles all `.co-dp-btn` / `.co-dp-opt` clicks; click outside `.co-dp-wrap` closes all open pickers

**Value contracts (unchanged):**

Status values passed to PATCH:
```
saved | shortlisted | contacted | interview | hired | rejected
```

Sort values passed to GET /company/saved-candidates:
```
updated_desc | updated_asc | created_desc | created_asc | name_asc | status_asc
```

### Filter Chips UI

| Property | Value |
|----------|-------|
| Layout | CSS Grid — `repeat(4, minmax(0, 1fr))` — always 4 columns, 2 rows |
| Shape | Rectangular — `border-radius: 9px` (not pill) |
| Height | `44px` fixed |
| Direction | `flex-direction: column` — icon (13px) → label → count |
| Hover effect | `filter: brightness(1.12)` (preserves per-type color on hover) |

**Color system — always visible (base subtle, active stronger):**

| Filter | Color | Base bg alpha | Active bg alpha |
|--------|-------|--------------|----------------|
| الكل | `#00c896` teal | `.05` | `.15` |
| محفوظ | `#94a3b8` slate | `.06` | `.15` |
| مرشح قوي | `#60a5fa` blue | `.06` | `.15` |
| تم التواصل | `#38bdf8` sky | `.06` | `.15` |
| مقابلة | `#fbbf24` amber | `.06` | `.15` |
| تم التوظيف | `#34d399` emerald | `.06` | `.15` |
| غير مناسب | `#f87171` red | `.06` | `.15` |
| بدون وظيفة | `#9ca3af` cool gray | `.06` | `.15` |

Same color values are used in `.co-cand-status--*` badges — unified palette across chips and cards.

### Other Changes

- **Manage button** (`.co-cand-manage-btn`): changed from purple (`#a78bfa`) to neutral slate (`#94a3b8`)
- **Filter icons**: Lucide-style inline SVGs per filter type via `_FILTER_ICONS` constant

### Forbidden Patterns (UI Polish)

```
❌ لا تُعيد native <select> داخل مودال المرشحين
❌ لا تغيّر قيم status أو sort في JS أو Backend
❌ لا تُعيد filter chips لشكل pill (border-radius: 20px أو أكبر)
❌ لا تُغيّر layout الـ chips من grid إلى flex-wrap
❌ لا تستخدم ألواناً مختلفة في filter chips عن .co-cand-status--* badges
❌ أي تعديل على نظام الـ pickers يجب ألا يغيّر قيم data-selected المُرسَلة للـ PATCH
```

---

## [P1] 55. Score System

**Endpoint:** `GET /profile/{user_id}/score`
**Auth:** None

### Calculation — `_calc_profile_score(uid, conn)`

| الشرط | النقاط |
|-------|--------|
| avatar_url محدّد | 10 |
| headline أو title محدّد | 10 |
| bio محدّدة | 10 |
| location محدّد | 5 |
| خبرة واحدة أو أكثر | 20 |
| تعليم واحد أو أكثر | 15 |
| 3 مهارات أو أكثر | 15 |
| رابط واحد أو أكثر | 5 |
| is_verified = TRUE | 5 |
| **المجموع** | **95** |

### Score Levels

| النطاق | المستوى |
|--------|---------|
| ≥ 90 | ممتاز |
| ≥ 70 | جيد |
| ≥ 50 | متوسط |
| < 50 | يحتاج تحسين |

### Response

```json
{
  "score": <0-95>,
  "tips": [{"tip": <str>, "points": <int>}],  // أعلى 3 نقاط ناقصة
  "level": "ممتاز|جيد|متوسط|يحتاج تحسين"
}
```

### Rules

```
✅ _calc_profile_score مشترك بين /score و/metrics
✅ tips تحتوي الشروط غير المكتملة فقط، مرتبة descending
❌ لا caching — يُحسب fresh في كل طلب
```

---

## [P1] 56. Metrics Endpoint

**Endpoint:** `GET /profile/{user_id}/metrics`
**Auth:** Optional JWT (لتحديد `viewer.is_following`)

### Response

```json
{
  "status": "success",
  "metrics": {
    "views_count":      <int>,
    "followers_count":  <int>,
    "experience_count": <int>,
    "education_count":  <int>,
    "courses_count":    <int>,
    "skills_count":     <int>,
    "languages_count":  <int>,
    "links_count":      <int>,
    "score":            <0-95>
  },
  "viewer": {
    "is_following": <bool>
  }
}
```

### DB Queries (single connection)

```python
courses_count    = COUNT(*) FROM courses    WHERE user_id
lang_count       = COUNT(*) FROM user_langs WHERE user_id
followers_count  = COUNT(*) FROM profile_follows WHERE followed_id
views_count      = COUNT(*) FROM profile_views   WHERE viewed_user_id
is_following     = EXISTS   FROM profile_follows WHERE follower_id=token_uid AND followed_id=uid
score_data       = _calc_profile_score(uid, conn)  # يُعيد exp/edu/skill/link counts أيضاً
```

### Rules

```
✅ لا يُسجّل view (بخلاف GET /profile/{id})
✅ single connection — لا N+1 queries
✅ viewer.is_following = false إذا كان الـ viewer هو الـ owner
❌ لا تستخدم /metrics لتسجيل الزيارات
```

---

## [P1] 57. Admin System

**URL:** `/tw-ctrl-kPuOWhpIYjdLQXmh`
**Files:** `admin.html`, `admin-view.html`

### Token Authentication

```python
ADMIN_PASSWORD  = "tw@admin2025"
ADMIN_URL_TOKEN = "kPuOWhpIYjdLQXmh"  # في الـ URL — security-through-obscurity
ADMIN_TOKEN     = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()  # 64-char hex

def check_admin(request: Request):
    token = request.headers.get("X-Admin-Token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "Forbidden")
```

**Admin Login Flow:**
1. POST `/tw-ctrl-login` بكلمة المرور
2. Server يُعيد JWT token
3. يُخزَّن في `sessionStorage` (لا localStorage)
4. كل استدعاء API يُرسل `X-Admin-Token: <sha256>`

### admin.html — Sections

| القسم | ID | الوظيفة |
|-------|----|---------|
| إحصائيات | — | عدد المستخدمين، الشركات، الوظائف، التوثيق |
| إدارة المستخدمين | `#tab-users` | بحث، تغيير النوع، حذف، إرسال رسالة |
| طلبات التوثيق | `#tab-verify` | verify_requests المعلّقة |
| الوظائف | `#tab-jobs` | قائمة الوظائف، حذف |
| البلاغات | `#tab-reports` | content reports مع status badges |
| KYC | `#tab-kyc` | مراجعة kyc_submissions |
| الأخطاء | `#tab-errors` | JavaScript error logs |

### admin-view.html — Individual User Page

الوصول: `admin.html?id={user_id}` ← يفتح `admin-view.html` في نافذة جديدة

| القسم | الوظيفة |
|-------|---------|
| Sidebar | avatar، name، email، type badge، ID، تاريخ الإنضمام |
| Quick Actions | تغيير النوع، verify/unverify، reset password، إرسال رسالة، حذف الحساب |
| Basic Info | full_name، headline، location، bio، is_verified، tw_id |
| Experience / Education / Courses | قائمة مع زر حذف لكل عنصر |

### Rules

```
✅ Admin token مشتق من كلمة المرور — لا DB storage
✅ ADMIN_URL_TOKEN سري — لا يُكشف في logs أو responses
❌ لا تُعيد ADMIN_TOKEN في أي response
❌ لا تُضف admin endpoints بدون check_admin dependency
```

---

## [P2] 58. Reports System

**Database Table: `reports`**

```sql
CREATE TABLE reports (
    id            SERIAL PRIMARY KEY,
    reporter_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reported_id   INTEGER REFERENCES users(id) ON DELETE CASCADE,
    reported_type TEXT DEFAULT 'user',   -- 'user'|'job'|'company'
    report_type   TEXT NOT NULL,         -- 'sexual'|'fraud'|'harassment'|'spam'|'other'
    reason        TEXT,
    target_url    TEXT,
    status        TEXT DEFAULT 'pending', -- 'pending'|'resolved'
    created_at    TIMESTAMPTZ DEFAULT NOW()
)
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/reports/submit` | JWT | تقديم بلاغ |
| GET | `/admin/reports` | Admin | قائمة كل البلاغات |
| PUT | `/admin/reports/{report_id}/resolve` | Admin | تغيير status إلى 'resolved' |

**Request for POST /reports/submit:**
```json
{ "reported_id": <int>, "reported_type": "user|job|company", "report_type": "sexual|fraud|harassment|spam|other", "reason": <str>, "target_url": <str|null> }
```

### Rules

```
✅ reporter_id: ON DELETE SET NULL — البلاغ يبقى حتى بعد حذف المُبلِّغ
✅ reported_id: ON DELETE CASCADE — البلاغ يُحذف بحذف المُبلَّغ عنه
❌ لا حذف فردي للبلاغات من الـ UI (resolve فقط)
```

---

## [P2] 59. Landing Page

**File:** `landing.html`
**Route:** `GET /` (serves landing.html)
**Last redesign:** PR #203 (June 2026) — complete rebuild

### Sections

| القسم | HTML ID | المحتوى |
|-------|---------|---------|
| Navigation | `nav` | Logo (`/static/33333.svg`) + anchor links + دخول / ابدأ مجاناً → `/login` |
| Hero | `#hero` | 2-column: نص + بطاقة ملف تعريفي (glassmorphism mockup) + floating badges |
| Value Cards | `#values` | 4 بطاقات: ملف موثوق / رابط وQR / فرص عمل / للجميع |
| من نخدم | `#who` | 3 cards ملوّنة: موظف (أخضر) / شركة (أزرق) / جهة تعليمية (بنفسجي) |
| كيف تعمل | `#how` | 3 خطوات مرقّمة بخط gradient رابط (يختفي على موبايل) |
| المميزات | `#features` | 6 بطاقات: توثيق رسمي / ملف شخصي / مطابقة وظائف / دورات / رسائل / QR |
| التوثيق | `#verify` | 3 خطوات: رفع وثيقة → مراجعة → اعتماد رسمي |
| CTA | `#cta` | زر واحد → `/login` + 3 روابط نصية (موظف / شركة / جهة تعليمية) |
| Footer | `footer` | Logo + نسخة حقوق + روابط دخول/تسجيل |

### Dynamic Behavior

```javascript
// لا توجد API calls على هذه الصفحة — جميع المحتوى ثابت
// السبب: /auth/users يتطلب X-Admin-Token (ممنوع من الصفحة العامة)
//         /jobs يعيد 0 لعدم وجود بيانات كافية حالياً

// إذا كان المستخدم مسجّلاً (localStorage key: tw_user):
emp  + tw_id → /u/{tw_id}       ← الملف العام الكنوني
emp  بدون tw_id → /home
co           → /company-profile  ← بدون ?id= query params
edu          → /edu-profile      ← بدون ?id= query params
```

### Forbidden Patterns (Landing Page)

- **ممنوع** استدعاء `/auth/users` من `landing.html` — يتطلب `X-Admin-Token`
- **ممنوع** الرجوع إلى `profile.html?id=`، `company-profile.html?id=`، `edu-profile.html?id=`
- **ممنوع** قراءة `tawasalna_user` من `localStorage` — المفتاح الصحيح هو `tw_user`
- **ممنوع** وضع stat counters ديناميكية إلا إذا كان الـ endpoint عاماً ويعيد بيانات حقيقية
- **ممنوع** وعود تسويقية مبالغة مثل "مؤكدة من مصادرها مباشرة" — استخدم "قابلة للتوثيق والاعتماد"

### Body Visibility Safety

```html
<!-- في <head>: يمنع بقاء الصفحة فارغة إذا فشل JS -->
<noscript><style>body{opacity:1!important}</style></noscript>
```

```javascript
// في أول سطر داخل IIFE: safety net إذا رمى الكود exception
setTimeout(function(){ document.body.classList.add('ready'); }, 400);
```

### Icons

Lucide icons مُحمَّلة من vendor محلي (انظر قسم Vendor Assets أدناه):
```html
<script src="/static/vendor/lucide/lucide.min.js"></script>
```
Guard إلزامي قبل الاستخدام:
```javascript
if (window.lucide) { lucide.createIcons(); }
```

### Animations

- Scroll reveal: `IntersectionObserver` على `.reveal` elements مع stagger للأشقاء
- Smooth scroll: `scrollIntoView({behavior:'smooth'})` للـ anchor links
- Nav `scrolled` class: يُضاف عند `scrollY > 20` لتغميق الخلفية

---

## Vendor Assets

محلي داخل `static/vendor/` لتجنب الاعتماد على CDN خارجي في الإنتاج.

| المكتبة | النسخة | المسار المحلي | الترخيص |
|---------|--------|--------------|---------|
| Lucide | 0.460.0 | `static/vendor/lucide/lucide.min.js` | ISC |
| circle-flags (HatScripts) | gh-pages @ 2026-06-26 | `static/shared/flags/*.svg` (18 ملف) | MIT |

### قواعد Vendor Assets

- **ممنوع** تحديث نسخة vendor دون تحديث هذا الجدول
- عند إضافة مكتبة جديدة: نزّل UMD bundle، ضعه في `static/vendor/{lib}/`، وثّق النسخة هنا
- FastAPI يخدم المسار عبر `@app.get("/static/{filename:path}")` — يدعم subdirectories تلقائياً
- الصفحات التي تستخدم Lucide عبر CDN خارجي (مثل `index.html`): يُنقل تدريجياً للـ vendor في PRs مستقلة

---

## Home V2 — `home-v2.html` (Feed-first — Production)

**File:** `home-v2.html` (مُفعَّل في production)
**Route:** `GET /home` و `GET /home.html` — يخدمان `home-v2.html` (استُبدل `home.html` القديم)
**Preview Route:** `GET /preview/home-v2` — **محذوف**
**Design Direction:** **Feed-first** — أول ما يراه المستخدم = filter tabs + feed cards

### Files

#### CSS / HTML

| الملف | الدور |
|-------|-------|
| `home-v2.html` | HTML هيكل نظيف فقط — لا منطق، لا styles inline |
| `static/app-header.css` | CSS vars مشتركة + `.sc-header` / `.sc-hicon` / `.sc-menu-*` classes |
| `static/home-v2.css` | أنماط الصفحة، namespace `.hw-*` |

#### JS Modules (في `static/home/`) — مُرتّبة حسب ترتيب التحميل

| الملف | المسؤولية |
|-------|----------|
| `home.utils.js` | constants (JOB_TYPES, NEWS_CATS, EMPTY_LABELS) + DOM helpers (el, txt, makeAvatar, timeAgo, icons) |
| `home.state.js` | shared runtime state: `Home.state = { user, jwt, currentFilter, loading, abortCtrl, nextCursor }` |
| `home.api.js` | `Home.api.loadFeed(filter, limit)` — fetch + abort + error handling |
| `home.cards.js` | `Home.cards.renderCard / renderOpportunityCard / renderPostCard / renderNewsCard` |
| `home.render.js` | `Home.render.showSkeleton / showEmpty / showError / renderFeed` |
| `home.filters.js` | `Home.filters.init() / load(filter)` — tab wiring + orchestration |
| `home.header.js` | `Home.header.init()` — home btn, menu dropdown, logout |
| `home.nav.js` | `Home.nav.init(user)` — bottom nav, sidebar, per-user-type adjustments |
| `home.main.js` | bootstrap only: auth guard, populate state, init modules, load initial feed |

**ممنوع** إضافة منطق في `home-v2.js` — هذا الملف deprecated ويحتوي تعليق redirect فقط.  
**ممنوع** تضخيم `home.main.js` بمنطق — هو bootstrap فقط.

### Shared Namespace

جميع الـ modules تكتب على `window.Home`:

```js
window.Home = window.Home || {};
window.Home.utils   = { ... };
window.Home.state   = { ... };
window.Home.api     = { ... };
window.Home.cards   = { ... };
window.Home.render  = { ... };
window.Home.filters = { ... };
window.Home.header  = { ... };
window.Home.nav     = { ... };
```

### App Header (Shared — `static/app-header.css`)

Home V2 و Profile V2 يستخدمان نفس هيكل الهيدر:

```html
<div class="sc-header">
  <button class="sc-hicon sc-home-btn" id="hwHomeBtn">← home icon</button>
  <div class="sc-logo">← logo absolute center</div>
  <div class="sc-head-icons">← bell / messages / menu dropdown</div>
</div>
```

CSS vars مشتركة (من `app-header.css`):
```css
:root {
  --ah-h:    56px;
  --ah-bg:   rgba(7,11,24,.93);
  --ah-blur: blur(14px);
  --ah-brd:  rgba(255,255,255,.09);
}
.sc-header { position:sticky; top:0; min-height:var(--ah-h); background:var(--ah-bg); ... }
.sc-header .sc-logo { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); }
```

- `static/app-header.js` — يبقى للاستخدام المستقبلي (لا يُستخدم في Home V2 أو Profile V2 حالياً)
- Profile V2 logout يديره `initGlobalHeaderMenu()` من `tw_shared.js`
- Home V2 logout يديره `home.header.js` على `#hwLogoutBtn`

### DOM Structure

```
<div.sc-header>   sticky 56px (var --ah-h): sc-home-btn + sc-logo (absolute center) + sc-head-icons
<div.hw-fbar>     fixed 46px (below sc-header): filter tabs — الكل/فرص/منشورات/أخبار
body              padding-top: var(--flt, 46px) only — sc-header is sticky (in flow)
<div.hw-page>
  <main.hw-feed>
    <div#hwBanner>   compact banner for co/edu (hidden for emp)
    <div#hwFeed>     feed items rendered by Home.cards via DOM API
    <div#hwEmpty>    empty state per filter
    <div#hwError>    error state with retry button
  <aside.hw-sidebar> desktop only (≥1020px): completion strip + quick links
<nav.hw-bnav>     fixed bottom 60px (mobile ≤1020px): 5 tabs per user type
```

### API Contract — `GET /home/feed`

**Auth:** `Authorization: Bearer <tw_jwt>` (JWT from localStorage `tw_jwt`) — `Depends(verify_token)`  
**`user_id` comes from JWT only** — client cannot override

| Query Param | Values | Default |
|-------------|--------|---------|
| `filter` | `all\|opportunities\|posts\|news` | `all` |
| `limit` | 1–50 | 20 |

**Response examples:**
```json
{
  "items": [
    {"type":"opportunity", "opp_type":"job", "id":1, "title":"...", "company_name":"...",
     "location":"...", "job_type":"full_time", "salary_min":null, "salary_max":null,
     "currency":"", "skills":[], "created_at":"2025-...", "company_tw_id":"C...", "company_logo":""},
    {"type":"post", "id":2, "body":"...", "tags":[], "created_at":"2025-...",
     "author_name":"...", "author_tw_id":"C...", "author_avatar":""},
    {"type":"news", "id":3, "title":"...", "summary":"...", "body":"...",
     "category":"labor_law", "country":"JO", "source_url":"https://...", "created_at":"2025-..."}
  ],
  "filter": "all",
  "total": 3
}
```

**Data sources per filter:**

| filter | data source | مصدر البيانات | ملاحظة |
|--------|-------------|--------------|--------|
| `all` | opportunities (⅓) + posts (⅓) + news (⅓) → sorted by created_at DESC | مُختلط | مرتب زمنياً |
| `opportunities` | `jobs` table JOIN `users` + `profiles` WHERE `status='open'` | `jobs` | `opp_type="job"` حالياً |
| `posts` | `company_posts` table JOIN `users` + `profiles` | `company_posts` | |
| `news` | `news_posts` WHERE `status='published'` | `news_posts` | admin-only نشر |

> **ملاحظة هامة:** فلتر `news` قد يرجع قائمة فارغة إذا لم يكن الأدمن قد نشر أخباراً بعد. هذا **مقبول ومتوقع** — الجدول والـ API موجودان. الفرق: فلتر فارغ بسبب **غياب البيانات** ≠ فلتر وهمي بدون API/DB (الثاني ممنوع).

### `news_posts` Table Schema

```sql
CREATE TABLE news_posts (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    body TEXT,
    category TEXT DEFAULT 'general',   -- general|labor_law|opportunity|ministry|platform|agreement
    country TEXT,
    source_url TEXT,
    status TEXT DEFAULT 'draft',       -- draft|published|archived
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### News Admin Endpoints (require `X-Admin-Token`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/news` | List all news (all statuses) |
| `POST` | `/admin/news` | Create news post |
| `PUT` | `/admin/news/{id}` | Update news post |
| `DELETE` | `/admin/news/{id}` | Delete news post |

### `opp_type` Field (extensibility)

`type="opportunity"` cards include `opp_type` to allow future sub-types without redesigning the card:

| `opp_type` | الوصف | الجدول |
|-----------|-------|--------|
| `"job"` | وظيفة (الحالي) | `jobs` |
| `"training"` | تدريب (مستقبلي) | جدول مستقبلي |
| `"scholarship"` | منحة (مستقبلي) | جدول مستقبلي |
| `"overseas"` | فرصة خارجية (مستقبلي) | جدول مستقبلي |

**ممنوع** إضافة opp_type جديد بدون جدول + API حقيقي.

### Security Notes

- `user_id` extracted from JWT only (never from query/body param)
- `filter` allowlisted server-side; unknown values → `"all"`
- `limit` capped at 50 server-side
- All text from API rendered via `textContent` — no `innerHTML` from API data
- Skeleton `innerHTML` is static (no API data) — safe
- Opportunity links: `/job-detail?id=<integer>` — integer cast enforced client-side
- Profile links: `/u/<tw_id>` — only used when server returns non-empty `tw_id` string
- News `source_url`: rendered as `<a target="_blank" rel="noopener noreferrer">` — no innerHTML

### Feed State Machine

```
filter tab click
  → Home.filters.load(filter)
      → Home.render.showSkeleton()   — clears #hwFeed, shows static animated placeholders
      → Home.api.loadFeed(filter)    — AbortController (cancels previous in-flight request)
          → success + items          → Home.render.renderFeed(items, filter)
          → success + empty          → Home.render.showEmpty(filter)
          → abort (null returned)    → no-op (filter changed mid-flight)
          → network/server error     → Home.render.showError(retryFn)
```

### DB Indexes (Feed Scalability)

أضيفت في `_migrate_feed_indexes()` — تُنفَّذ على `on_startup` — idempotent:

```sql
CREATE INDEX IF NOT EXISTS idx_jobs_status_created  ON jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cposts_created       ON company_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_status_created  ON news_posts(status, created_at DESC);
```

**ممنوع** حذف هذه الـ indexes — الـ feed يعتمد عليها لـ sequential scan avoidance.

### Cursor Pagination Contract (Reserved — Not Yet Active)

الـ API يرجع `{ items: [...], next_cursor: null }` حالياً (`next_cursor` دائماً `null`).  
عند التطبيق المستقبلي:
- Client يرسل `?cursor=<opaque_string>` بدل `?limit=` على load-more requests
- Server يرجع `next_cursor: "<string>"` أو `null` (نهاية البيانات)
- **ممنوع** تغيير `?filter=` أو `?limit=` behavior الحالي عند إضافة cursor — backward-compatible فقط

### Card Types

| type | fields used | link/action |
|------|-------------|-------------|
| `opportunity` | title, company_name, location, job_type, salary, opp_type, created_at | `/job-detail?id={id}` |
| `post` | author_name, author_avatar, body, created_at | click → `/u/{author_tw_id}` |
| `news` | title, summary, body, category, country, source_url, created_at | expand inline / external source |

### Per-Type User Behavior

| user_type | Banner | Bottom nav tab 2 | Profile link |
|-----------|--------|-----------------|--------------|
| `emp` | hidden | فرص → filter opportunities | `/u/{tw_id}` or `/profile` |
| `co` | فرص شركتك | فرصي → `/company-profile` | `/company-profile` |
| `edu` | دورات مؤسستك | دوراتي → `/edu-profile` | `/edu-profile` |

### CSS Offset System (single source)

```css
/* sc-header is position:sticky — it occupies natural flow space (no padding-top needed for it) */
body     { padding-top: var(--flt, 46px); }   /* only filter bar height */
.sc-header { position: sticky; top: 0; min-height: var(--ah-h, 56px); }
.hw-fbar   { position: fixed;  top: var(--ah-h, 56px); }
.hw-page   { padding: 14px 12px 72px; }       /* no margin-block-start */
```

### Forbidden Patterns (Home V2)

- **ممنوع** `element.innerHTML = apiData.anything` — يجب `createElement` + `textContent`
- **ممنوع** بيانات وهمية أو hardcoded في أي جزء من الـ feed
- **ممنوع** `.html?id=` routes — استخدم `/job-detail?id=` و `/u/{tw_id}` فقط
- **ممنوع** قراءة `user_type` أو `user_id` من أي مكان غير JWT (server) أو `tw_user` (client)
- **ممنوع** ترك `/preview/home-v2` — تم حذفه
- **ممنوع** إعادة Dashboard-first (بطاقة مستخدم ضخمة أول الصفحة)
- **ممنوع** inline CSS/JS كبير في `home-v2.html` — يجب في الملفات المنفصلة
- **ممنوع** إضافة filter في الواجهة قبل وجود جدول/endpoint حقيقي له — filter بدون بيانات = UX ناقص
- **ممنوع** إضافة فلتر `companies` للـ Home — الشركات ليست محتوى feed؛ مكانها صفحة استكشاف/بحث مستقلة
- **ممنوع** إعادة `questions` أو `courses` كـ filters قبل بناء جداولهما الكاملة
- **ممنوع** إنشاء header مستقل لصفحة جديدة بدون استخدام `static/app-header.css` — الـ App Header موحد
- **ممنوع** إضافة منطق في `static/home-v2.js` — الملف deprecated؛ أي logic يذهب إلى module مناسب في `static/home/`
- **ممنوع** إضافة feature جديدة على Home قبل تحديد module المناسب لها في `static/home/`
- **ممنوع** تضخيم `home.main.js` — bootstrap فقط؛ أي منطق يذهب لـ module مخصص
- **ممنوع** `ORDER BY RANDOM()` في أي query على `/home/feed` — يكسر pagination ويُحمّل DB
- **ممنوع** table scan ثقيل بدون index على columns مستخدمة في WHERE/ORDER — راجع indexes section أعلاه

---

## [P0] 55. Messenger Mobile Default View

### Root Cause (documented after bug fix)

On mobile (≤700px), `messages.css` hides `.conv-list` by default:
```css
@media(max-width:700px){
  .conv-list{display:none;}
  .conv-list.mobile-show{display:flex;...}
}
```

`renderConvList()` populates `.conv-items` (inside `.conv-list`) but does NOT add `mobile-show`.  
Result: conversations are rendered in the DOM but invisible. User sees only "اختر محادثة".

### Rule: Mobile Default View = Conversation List

When the user opens `/messages` without a `?with=` param, the conversation list MUST be visible on mobile.

**Implementation:**
```javascript
// DOMContentLoaded — no ?with param path:
var convListEl = document.getElementById('convList');
if (convListEl) convListEl.classList.add('mobile-show');  // ← show list on mobile
loadConversations();
```

### State Transitions (mobile)

| Action | Result |
|--------|--------|
| Open /messages (no ?with) | `mobile-show` added → conv-list visible |
| Click conversation | `openConversation()` removes `mobile-show` → chat visible |
| Click ☰ button | `toggleConvList()` toggles `mobile-show` → list visible |
| Open /messages?with={tw_id} | `handleWithParam()` → chat opens → `mobile-show` removed |

**Forbidden:**
- ممنوع: فتح /messages وعرض "اختر محادثة" فقط إذا يوجد محادثات
- ممنوع: إخفاء conv-list على الموبايل بدون أن يتمكن المستخدم من رؤيتها
- ممنوع: silent catch في loadConversations — أي error يجب أن يُعرض للمستخدم

---

## [P0] 56. Messenger Conversations — SQL Column Qualification Rule

### Root Cause (500 error — documented after production failure)

`get_conversations()` used unqualified column names in a `messages m JOIN users u` query.
Both tables have `created_at`. PostgreSQL threw:
```
ERROR: column reference "created_at" is ambiguous
```

This caused `/messages/conversations/{user_id}` to return 500 while `/messages/unread/{user_id}`
returned 200 — because unread only queries `messages` with no JOIN.

**The fix**: qualify ALL column references with the table alias in any JOIN query:

```python
# WRONG — causes 500 when messages JOIN users
"content, created_at, is_read, sender_id, "
"ORDER BY other_id, created_at DESC"

# CORRECT — all columns qualified
"m.content, m.created_at, m.is_read, m.sender_id, "
"ORDER BY other_id, m.created_at DESC"
```

### Rule: Always Qualify Columns in JOIN Queries

Any SQL that JOINs two or more tables MUST prefix every selected column with its table alias.
Never rely on PostgreSQL to resolve ambiguity — if any two joined tables share a column name,
the query fails at runtime.

Common shared column names across tawasalna tables:
- `created_at` — present in nearly ALL tables (messages, users, profiles, jobs, ...)
- `id` — present in all tables
- `user_id` — present in profiles, experience, education, courses, notifications, ...

**Forbidden:**
- ممنوع: `SELECT content, created_at FROM messages JOIN users ...` — `created_at` is ambiguous
- ممنوع: `ORDER BY created_at DESC` في أي query بها JOIN

---

## [P1] 57. Messenger Conversations — Response Contract

### API Response: `GET /messages/conversations/{user_id}`

**Auth:** `Authorization: Bearer {jwt}` required. Server validates `jwt.user_id == user_id`.

**Response shape (current):**
```json
{
  "status": "success",
  "conversations": [
    {
      "other_id":      42,
      "full_name":     "اسم المستخدم",
      "user_type":     "emp" | "co" | "edu",
      "tw_id":         "U9620...",
      "avatar_url":    "https://..." | null,
      "content":       "آخر رسالة",
      "created_at":    "2026-06-15T19:00:00",
      "is_read":       false,
      "sender_id":     17,
      "unread_count":  3
    }
  ]
}
```

**Empty state (no messages):** `{ "status": "success", "conversations": [] }` — NEVER 500.

**Frontend mapping (`messages.render.js`):**

| Field | Used for |
|-------|----------|
| `other_id` | `data-uid` attribute, `openConversation(otherId)` |
| `full_name` | Conversation name display |
| `user_type` | Type icon (🏢/🎓/👤) |
| `content` | Preview of last message (keep as `content`, NOT `last_message`) |
| `is_read` + `sender_id` | Unread badge (sender ≠ current user AND not read) |
| `avatar_url` | Future: conversation avatar (frontend not yet wired) |
| `unread_count` | Future: per-conversation badge (frontend not yet wired) |

### Sources

| Field | Source Table |
|-------|-------------|
| `other_id` | Computed: `CASE WHEN m.sender_id=uid THEN m.receiver_id ELSE m.sender_id END` |
| `content`, `created_at`, `is_read`, `sender_id` | `messages m` (qualified `m.`) |
| `full_name`, `user_type`, `tw_id` | `users u` |
| `avatar_url` | `profiles p` (LEFT JOIN — may be NULL) |
| `unread_count` | Batch subquery after main SELECT |

### No-Silent-Catch Rule (Frontend)

`loadConversations()` catch MUST show visible feedback:
- 401/403 → "انتهت الجلسة — أعد تسجيل الدخول" (red)
- Other errors → "تعذر تحميل المحادثات" (red, only if no items rendered)
- All statuses → `console.error('[messages] loadConversations failed, status:', status)`

**Forbidden:**
- ممنوع: `catch(function(){})` فارغ في loadConversations
- ممنوع: حذف items صالحة بسبب فشل مؤقت في polling
- ممنوع: unread count badge = 5 ولا يكون conversations endpoint يعمل

### Version Tracking

Current JS version: `?v=v4` (bumped when messages.render.js changed — mobile default fix)


---

## [P1] 58. Messenger — Delivery & Read Receipts

### 4 Message States

| State | DB condition | Status icon | Color |
|-------|-------------|-------------|-------|
| `pending` | Optimistic, no server ack yet | `•••` | dim gray |
| `sent` | Inserted in DB (`id` returned) | `✓` | gray |
| `delivered` | `delivered_at IS NOT NULL` | `✓✓` | gray |
| `read` | `read_at IS NOT NULL` | `✓✓` | green (#00c896) |

### DB Schema Migration

Added to `messages` table (ALTER TABLE migration in `init_db()`):

```sql
ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP NULL;
```

Existing `is_read BOOLEAN` kept for backwards-compat (unread badge queries use it).

### When Each State Is Set

| Transition | Trigger | Code location |
|-----------|---------|--------------|
| pending → sent | HTTP POST /messages/send returns | `messages.render.js doSendMessage.then` |
| sent → delivered | Receiver's WS is online when sender posts | `server.py send_msg()` — calls `mark_message_delivered()` after `ws_manager.send_to_user()` returns `True` |
| sent → delivered | Receiver opens conversation (pulls from DB) | `auth.py get_messages()` — bulk `UPDATE ... SET delivered_at=NOW() WHERE delivered_at IS NULL` |
| delivered → read | Receiver opens conversation | `auth.py get_messages()` — `UPDATE ... SET is_read=TRUE, read_at=NOW()` |

### Backend Functions

**`auth.py`**

- `send_message(sender_id, receiver_id, content) → dict` — RETURNING now includes `delivered_at`, `read_at`
- `mark_message_delivered(msg_id)` — sets `delivered_at=NOW()` if NULL
- `get_messages(user_id, other_id) → (list, list)` — returns `(messages, newly_read_ids)`; marks `delivered_at` and `read_at` on open

**`server.py`**

- `ConnectionManager.send_to_user()` — now returns `bool` (True if at least one WS was alive)
- `POST /messages/send` — now `async def`; pushes WS to receiver; if delivered, calls `mark_message_delivered()` and sends `status_update` WS to sender
- `GET /messages/{user_id}/{other_id}` — now `async def`; after marking read, sends `{"type":"status_update","ids":[...],"status":"read"}` WS to `other_id`

### WebSocket Events

**`type: "message"` (server → receiver):**
```json
{"type": "message", "from": 17, "id": 99, "content": "...", "created_at": "..."}
```

**`type: "status_update"` (server → sender, delivered):**
```json
{"type": "status_update", "id": 99, "status": "delivered"}
```

**`type: "status_update"` (server → sender, read):**
```json
{"type": "status_update", "ids": [99, 100], "status": "read"}
```

### Frontend

**`messages.ws.js`**
- `_applyStatusToEl(el, status)` — updates `.msg-status` class + text on a bubble element
- `updateMessageStatus(data)` — resolves element by `[data-msg-id]`; if not found yet, stashes in `_pendingStatus`

**`messages.render.js`**
- `renderMessageStatus(msg)` — returns HTML span: reads `msg.read_at`, `msg.delivered_at`
- `renderBubble(isMe, content, time, statusHtml, msgId)` — adds `data-msg-id` attribute
- `doSendMessage().then` — sets `data-msg-id` on optimistic bubble; applies `_pendingStatus` if WS arrived first

**`messages.state.js`**
- `_pendingStatus = {}` — map of `{msg_id → 'delivered'|'read'}` for race-condition handling

### CSS Classes

```css
.msg-status.pending   { opacity:.4; color: var(--t3); }   /* ••• */
.msg-status.sent      { color: var(--t3); }                /* ✓ */
.msg-status.delivered { color: var(--t3); }                /* ✓✓ gray */
.msg-status.read      { color: #00c896; opacity: 1; }      /* ✓✓ green */
```

### Forbidden

- ممنوع: تغيير لون ✓✓ بدون `read_at` حقيقي من DB
- ممنوع: إرسال `status_update` إلى الطرف الخاطئ (يجب: delivered/sent → إلى sender؛ read → إلى other_id)
- ممنوع: إعادة رسائل الماسنجر كـ notifications
- ممنوع: polling بديل بدلاً من WS للـ status updates (WS هو المصدر الحقيقي للتحديث الفوري)
- ممنوع: كسر `is_read` (تظل لحساب unread badge في conversations list)

### Version Tracking

Current JS version: `?v=v5` (bumped when delivery/read receipts implemented)

---

## 59. Messenger Realtime UX Contract

### Overview

Three improvements shipped together: immediate read receipts, typing indicator, and global badge WebSocket.

### Read Receipt — Immediate Delivery

**Rule:** ✓✓ turns green immediately when receiver has the conversation open, not on the next poll.

**Mechanism:**
- Server maintains `ws_manager.active_conversations: Dict[int, int]` (in-memory, `user_id → other_user_id`)
- Client signals when it opens a conversation: WS `{type: "active_conversation", other_id: X}`
- Client signals when it leaves: WS `{type: "inactive_conversation"}` (sent in `openConversation` switch, `goHome()`, and `beforeunload`)
- On every message save (HTTP `/messages/send` or WS legacy path): server checks `active_conversations[receiver] == sender`
  - If yes → `mark_message_read_immediate(msg_id)` → DB: `is_read=TRUE, read_at=NOW()` → WS `status_update {status: "read"}` to sender
  - If no + receiver online → WS `status_update {status: "delivered"}` to sender
- `active_conversations` is cleared on WS disconnect (when user's last WS for that user_id drops)

**Constraints:**
- ممنوع: ✓✓ green if receiver is merely online (not in that specific conversation)
- ممنوع: read status update without DB write
- In-memory only — resets on server restart, no persistence

### Typing Indicator

**Rule:** Typing appears as a temporary **in-chat bubble** (not in the header) — a received-message bubble with animated dots, inside `#messages`.

**Client (sender side):**
- `msgInput` `input` event → debounced: send `{type: "typing", to_user_id: X}` once per burst
- After 1.8s idle → send `{type: "typing_stop", to_user_id: X}`
- Timer variable: `_typingTimer` (in `messages.state.js`)

**Server:**
- Routes `typing` → `send_to_user(to_user_id, {type: "typing", from_user_id: sender})`
- Routes `typing_stop` → same pattern
- No DB write; ephemeral

**Client (receiver side — `messages.ws.js`):**

**Bubble lifecycle:**
- `showTypingBubble(fromId)`: idempotent insert of `<div id="typing-bubble-{fromId}" class="msg-wrap in typing-bubble">` with `.typing-dots` spans; scrolls to it; sets 5s failsafe auto-hide timer (resets on each `typing` event)
- `hideTypingBubble(fromId)`: removes `#typing-bubble-{fromId}` immediately; clears timer
- `_scheduleHideTypingBubble(fromId, ms)`: internal — cancels any pending timer, sets new one

**Event handling:**
- `typing` WS event → `showTypingBubble(fromId)` (idempotent; resets 5s failsafe)
- `typing_stop` WS event → `_scheduleHideTypingBubble(fromId, 2500)` — **2.5s delay, not immediate**
- `message` WS event from same user → **transform bubble in-place** (see below); clear timer
- Conversation switch → `hideTypingBubble(previous_conv_id)` in `openConversation()` (immediate)

**Bubble-to-message transform (on `message` event):**
```
if #typing-bubble-{fromId} exists:
  1. clearTimeout(_typingHideTimer)
  2. typingEl.removeAttribute('id')          // deregisters from timer callback
  3. typingEl.classList.remove('typing-bubble')
  4. typingEl.setAttribute('data-msg-id', data.id)
  5. typingEl.innerHTML = real message HTML   // replaces dots with text + time
  NO new element inserted — same DOM node, same scroll position
else:
  insertAdjacentHTML normally
```

**Sender side on send:**
- `doSendMessage()` immediately clears `_typingTimer` and calls `sendTypingStop()` — does NOT wait 1.8s debounce
- This starts receiver's 2.5s hide timer; the `message` WS event (arriving in ~100–500ms) then transforms and cancels it

**Timing trace (temporary debug, console only):**
- Frontend receiver: `[TW-TIMING] WS→DOM: Xms (msg #N from #M)` — measures WS parse + DOM op
- Frontend sender: `[TW-TIMING] HTTP send: Xms (msg #N)` — measures full HTTP round-trip
- Backend: `[TW-TIMING] send_msg #N: DB=Xms WS=Xms badge=Xms total=Xms` — server-side breakdown

**CSS (`.typing-bubble`, `.typing-dots`):**
- Bubble uses existing `.msg-wrap.in` + `.msg.in` styles (received-message appearance)
- `.typing-dots span` animated with `@keyframes tw-typing-dot` (bounce up/down, 0.9s, staggered at 0/0.2/0.4s)

**Forbidden:**
- ممنوع: show typing in `#chatStatus` header
- ممنوع: save typing state to DB
- ممنوع: send typing event per keystroke (must debounce)
- ممنوع: show typing if receiver is not in that conversation
- ممنوع: duplicate bubble (always check id before insert)
- ممنوع: remove typing bubble then add new message bubble when real message arrives
- ممنوع: leave typing bubble after real message is shown

### Global Badge WebSocket

**Rule:** `[data-badge="msgs"]` elements update in real time on ALL pages, not just the messages page.

**Implementation:**
- `tw_shared.js` IIFE opens `/ws/{viewer_id}` 200ms after `load`
- `viewer_id` = `localStorage.getItem('tw_user').id` (authenticated user, never profile owner from URL)
- On `{type: "badge_update", badge: "messages", count: N}`: update all `[data-badge="msgs"]` elements
- Server sends `badge_update` to receiver after EVERY saved message (both HTTP and WS paths)
- Messages page has TWO WS connections: one from `messages.ws.js` (chat) + one from `tw_shared.js` (badge) — this is intentional and harmless

**Forbidden:**
- ممنوع: use `localStorage` as source of badge count
- ممنوع: bind badge count to profile owner (`tw_id` from URL) instead of authenticated viewer
- ممنوع: create notification entries for messages

### Version Tracking

Current version: `?v=v7` (typing bubble UX: in-chat animated dots, 2.5s delayed hide, in-place transform to real message on arrival, immediate typing_stop on send, performance timing trace)

---

## [P1] 60. Messenger Realtime — Directional Fix & Typing Audit

### Root Cause: Read B→A Delayed

`ConnectionManager.disconnect()` cleared `active_conversations[user_id]` whenever the user's connection list became empty. On the messages page, each user has **two** WS connections: the messenger WS (`messages.ws.js`) and the global badge WS (`tw_shared.js`). If the badge WS disconnected (briefly), `self.active[user_id]` temporarily became `[messenger_ws]` — non-empty, so `active_conversations` was safe. BUT if the messenger WS disconnected while the badge WS was in a reconnecting gap, both slots were briefly empty and `active_conversations[user_id]` was wiped, causing the next message to fall through to `delivered` instead of `read`.

### Fix: Per-WS Ownership of `active_conversations`

`ConnectionManager` now tracks which specific WebSocket connection set the active conversation:

```python
self._conv_ws_owner: Dict[int, object] = {}  # user_id → WebSocket
```

- `active_conversation` WS event → sets `active_conversations[user_id] = other_id` AND `_conv_ws_owner[user_id] = websocket`
- `disconnect(user_id, ws)` → clears `active_conversations` ONLY if `_conv_ws_owner[user_id] is ws` (that WS owned it), OR if no connections remain at all
- Badge WS disconnecting → `_conv_ws_owner[user_id]` points to the messenger WS → `is` check fails → state preserved ✓
- Messenger WS reconnecting → `onopen` re-sends `active_conversation` → state restored ✓

**Forbidden:**
- ممنوع: إغلاق `active_conversations` بسبب badge WS أو أي اتصال غير الماسنجر
- ممنوع: مقارنة `active_conversations` بدون `int()` cast

### Root Cause: Typing Not Working

Strict `===` comparison in JavaScript. `data.from_user_id` is a JSON integer (Python int → number). `_currentConvId` should also be a number from `parseInt()`, but any stale path or future change could introduce a string. A single mismatched type silently breaks all typing events.

### Fix: `Number()` Normalization in messages.ws.js

All realtime ID comparisons now normalize both sides:

```javascript
var fromId = Number(data.from || data.from_user_id);
var convId  = Number(_currentConvId);
```

This covers: incoming `message` (`data.from`), `typing` and `typing_stop` (`data.from_user_id`). For events without these fields, `fromId = NaN` and all comparisons are `false` (safe).

**Rule:** Every WebSocket event handler that compares IDs MUST use `Number()` normalization. Never use `===` on raw `data.*` fields without normalizing.

### active_conversation Contract

| Field | Type | Source |
|-------|------|--------|
| `other_id` in WS event | numeric user id (NOT tw_id) | `_currentConvId` from `openConversation(otherId)` |
| `active_conversations[user_id]` | Python int | `int(other_id)` on server |
| Comparison in `/messages/send` | Python int == Python int | both sides must be ints |

**tw_id is NEVER used in active_conversation** — it is a public routing string, not a realtime state key.

### typing Payload Contract

```
Client → Server: {type: "typing", to_user_id: Number(_currentConvId)}
Server → Receiver: {type: "typing", from_user_id: <int user_id from WS path>}
Receiver check: Number(data.from_user_id) === Number(_currentConvId)
```

---

## [P1] 61. Messenger Send Performance Contract

**Target:** `/messages/send` critical path ≤ 300ms server-side, ≤ 800ms net_ms on mobile.

### Measured Baseline (PR #164 debug panel)

| Metric | PR #163 | PR #164 | Root cause identified |
|--------|---------|---------|----------------------|
| `upd_ms` | ~500ms | **0ms** | UPDATE eliminated — hot path INSERT as read |
| `cnt_ms` | ~500ms | **0ms** | COUNT moved off hot path |
| `conn_ms` | 173ms | 173ms | SELECT 1 ping each request |
| `ins_ms` | ~300ms | **524ms** | WAL flush (synchronous_commit=on) |
| `db_ms` | ~1700ms | **697ms** | total |
| `srv_ms` | ~1700ms | **697ms** | ≈ db_ms (WS is negligible) |
| `net_ms` | ~2500ms | **1345ms** | includes ~600ms mobile network RTT |

### Root Cause of `ins_ms: 524ms` — WAL Flush

PostgreSQL default `synchronous_commit=on` means every COMMIT waits for the WAL record to be durably flushed to storage. On Supabase (remote storage), each WAL flush = ~350ms. Combined with 1 query roundtrip (~173ms), INSERT total ≈ 524ms.

**Fix (PR #165):** Set `synchronous_commit=off` at connection level via `options="-c synchronous_commit=off"` in `_db_params`. The COMMIT returns immediately; WAL is flushed asynchronously. In a crash, the last few milliseconds of messages might not persist — acceptable for chat.

### Root Cause of `conn_ms: 173ms` — Pool Ping

Every pool checkout ran `SELECT 1` to verify the connection was still alive (Supabase closes idle connections after ~5 minutes). This added 1 full Supabase roundtrip (~173ms) to every request.

**Fix (PR #165):** Pool stores `(conn, timestamp)`. Connections used within the last 240 seconds skip the ping — they cannot have expired yet. Only connections idle > 4 minutes are pinged. `conn_ms` drops to < 5ms for normal traffic.

### Root Cause of `net_ms - srv_ms ≈ 600ms` — Mobile Network

`net_ms` is measured client-side: start = just before `fetch()`, end = `.then()` receives parsed JSON. The ~600ms gap = mobile upload latency + server response download + TLS overhead. This is infrastructure/network, not reducible from application code.

### Two-path Pipeline (`send_message_pipeline` in `auth.py`)

| Path | Condition | DB queries | Queries detail |
|------|-----------|-----------|----------------|
| **Hot** | `receiver_has_conv_open = True` | **1** | `INSERT ... is_read=TRUE, read_at=NOW()` |
| **Cold** | `receiver_has_conv_open = False` | **2** | `INSERT` unread + `COUNT(*)` for badge |

`receiver_has_conv_open` is determined by `ws_manager.active_conversations.get(receiver_id) == sender_id`.

### Critical Path (blocks HTTP response)

```
get_conn() → [ping only if idle > 4min] → INSERT (hot: +read_at; cold: unread)
→ [cold only] COUNT unread
→ WS send message to receiver
→ WS send status_update to sender
→ return JSON
```

**Hot path total DB = 1 round-trip.  Cold path total DB = 2 round-trips.**

### Background Tasks (do NOT block response)

Cold path only, via `FastAPI.BackgroundTasks`:

| Task | Trigger |
|------|---------|
| `mark_message_delivered` (DB UPDATE) | `was_delivered = True` |
| `badge_update` WS push to receiver | always on cold path |

Hot path skips both — receiver is actively reading, delivered+read already set in INSERT, unread count unchanged.

### Measured After PR #165 + PR #166

| Metric | Before (PR #163) | After PR #165/#166 | Status |
|--------|-----------------|-------------------|--------|
| `conn_ms` | 173ms | **0ms** | ✅ Fixed |
| `upd_ms` | ~500ms | **0ms** | ✅ Fixed |
| `cnt_ms` | ~500ms | **0ms** | ✅ Fixed |
| `ins_ms` | ~524ms | **531ms** | ⏳ Under investigation |
| `db_ms` | ~1700ms | **531ms** | ⬇️ Improved but bottleneck remains |
| `srv_ms` | ~1700ms | **531ms** | ⬇️ |
| `net_ms` | ~2500ms | **912ms** | ⬇️ |

### INSERT Bottleneck — Extended Query Protocol (confirmed by PR #167)

`ins_exec: 523-548ms ≈ 3 × 173ms (RTT)` with `sync_ms:0` confirmed the root cause:

pg8000 sends parameterized queries as **three separate TCP exchanges**:
```
1. Parse     → ParseComplete          ~173ms
2. Bind+Exec → RowDescription+Rows    ~173ms
3. Sync      → ReadyForQuery          ~173ms
                                      ─────
                                      ~519ms ≈ 530ms ✓
```

`SELECT 1` (simple query, no params) = 1 RTT = 173ms. The overhead is purely protocol, not WAL or triggers.

### Fix — asyncpg Single-RTT Pipeline (PR #168)

`asyncpg` pipelines Parse+Bind+Execute+Sync in **one TCP write** and reads all responses together:
```
Parse+Bind+Execute+Sync → ParseComplete+BindComplete+Rows+ReadyForQuery
                                      ─────
                                      ~173ms (1 RTT)
```

Implementation:
- `asyncpg.create_pool()` initializes at startup with `statement_cache_size=0` (safe with Supabase PgBouncer/Transaction Pooler)
- `_pipeline_asyncpg()` in `server.py` uses `conn.fetchrow()` for INSERT
- `/messages/send` uses asyncpg pool if available; falls back to pg8000 `send_message_pipeline` if asyncpg pool fails to init
- `_timing.driver` field indicates which driver was used (`asyncpg` or `pg8000`)

Expected results:
```
drv:asyncpg  conn_ms:0  ins_exec:~173ms  ins_ms:~173ms  db_ms:~180ms  srv_ms:~200ms
```

### Timing Fields Returned in `_timing`

| Field | Meaning |
|-------|---------|
| `driver` | `"asyncpg"` or `"pg8000"` — which pipeline was used |
| `conn_ms` | Pool acquire time (asyncpg: near 0; pg8000: 0 if fresh, 173ms if pinged) |
| `sync_set_ms` | `SET synchronous_commit=off` time (0 for asyncpg; 0 for pg8000 after first use) |
| `insert_exec_ms` | INSERT `conn.run()` / `conn.fetchrow()` time (1 RTT with asyncpg vs 3 RTTs pg8000) |
| `insert_ms` | `sync_set_ms` + `insert_exec_ms` |
| `update_ms` | Always 0 on hot path |
| `count_ms` | COUNT(*) query time (0 on hot path) |
| `db_ms` | Total DB time = conn + set + insert + count |
| `ws_ms` | WS send time (critical path only) |
| `badge_ms` | Always 0 (deferred to background) |
| `total_ms` | Full endpoint wall time |

### Startup Diagnostics (in `init_db`)

- Logs any triggers on `messages` table (`pg_trigger` query) — unexpected triggers add INSERT latency
- Unexpected output: `[TW-WARN] triggers on messages table: [...]` → investigate

### Indexes (created at startup in `init_db`)

```sql
CREATE INDEX IF NOT EXISTS idx_msg_receiver_unread ON messages(receiver_id, is_read) WHERE is_read=FALSE;
CREATE INDEX IF NOT EXISTS idx_msg_pair            ON messages(sender_id, receiver_id);
CREATE INDEX IF NOT EXISTS idx_msg_receiver        ON messages(receiver_id);
```

### Forbidden

- NEVER call `get_conn()` more than once per `/messages/send` invocation on the critical path
- NEVER run `mark_message_delivered` (UPDATE) synchronously in the endpoint handler
- NEVER send `badge_update` synchronously on the cold path (it is a background task)
- NEVER skip the two-path logic and always-UPDATE every message
- NEVER revert `synchronous_commit=off` without documenting the latency regression and reason
- DO NOT add a 4th DB query to the critical path without documenting it here

Same for `typing_stop`.

---

## [P1] 62. Messenger Premium UI Contract

**Scope:** HTML/CSS-only redesign of `messages.html` + `messages.css`. No backend, WebSocket, or message-pipeline logic changed. All element IDs, class names used by JS (`messages.state.js`, `messages.api.js`, `messages.ws.js`, `messages.render.js`), and the typing-bubble/read-receipt markup are unchanged.

### What changed (PR #170)

| Area | Before (V1) | After (Premium V2) |
|------|------------|---------------------|
| Outgoing bubble (`.msg.out .msg-text`) | `rgba(255,255,255,.07)` flat gray — nearly invisible | `linear-gradient(135deg, var(--ac), var(--ac3), var(--ac2))` + white text + `box-shadow` |
| Incoming bubble (`.msg.in .msg-text`) | vibrant blue/teal gradient (backwards — receiver's message looked more prominent than sender's) | neutral glass surface: `rgba(255,255,255,.06)` + 1px border |
| Send button | 12px rounded square | full circle (`border-radius:50%`) with gradient + shadow, scale on hover/active |
| Nav title / logo | inline `style="..."` on `<span>` and `<img>` | `.nav-title` class on span; `.nav-logo img` rule in CSS — no inline styles |
| Nav height | 52px | 56px |
| Composer input | 14px rounded rect | 22px pill (`border-radius:22px`) with focus glow ring |
| Conversation list / chat background | flat single color | subtle radial-gradient accents (`rgba(0,200,150,.03)` / `rgba(37,99,255,.03)`), still dark/teal/blue theme |
| Scrollbars | default | thin custom webkit scrollbar (3px, translucent thumb) on `.conv-items` and `.messages` |
| Cache-busting version | `?v=v8` | `?v=v9` (CSS + all 5 JS files) |

### Explicitly NOT changed

- Typing bubble markup/animation (`.typing-bubble`, `.typing-dots`, `@keyframes tw-typing-dot`) — copied verbatim
- Message status icon classes (`.msg-status.pending/.sent/.delivered/.read`) — same selectors, same read-receipt color (`#00c896`)
- `.msg-wrap.out{justify-content:flex-start}` / `.msg-wrap.in{justify-content:flex-end}` RTL layout direction — unchanged
- Mobile breakpoint (`@media(max-width:700px)`), `.conv-list.mobile-show`, `.ch-back` toggle behavior — unchanged, only padding/sizing refined
- No JS files touched; no new HTTP requests, libraries, or animations beyond what already existed (hover/active transitions only, no new keyframes)
- Mobile keyboard-focus fix (PR #169: `pointerdown` preventDefault + `requestAnimationFrame` focus restore in `messages.render.js`) — untouched

### Forbidden

- NEVER reuse `?v=v8` (or any prior version string) after editing `messages.css`/the JS files — always bump together so browsers don't serve a stale CSS against new HTML structure
- NEVER reintroduce inline `style="..."` attributes on nav elements — use `.nav-title` / `.nav-logo img` classes
- NEVER make the incoming bubble more visually prominent than the outgoing bubble (readability rule: the user's own sent messages should be the most prominent/colorful element in the thread)

### Real Product Polish pass (follow-up PR)

PR #170 only restyled colors/bubbles; this pass wires the conversation list and chat
header to data the backend (`auth.py get_conversations()`, `/user/lookup/{tw_id}`)
already returned but the old markup never displayed. **Scope is still HTML/CSS plus
render-markup-only changes in `messages.render.js`** — no new endpoints, no WebSocket
changes, no changes to send/read-receipt/typing-bubble/debug logic.

| Area | Before | After |
|------|--------|-------|
| Logo | `Logo.svg` (old asset, mismatched brand colors) | `33333.svg` (current official mark — teal→blue gradient matching `--ac`/`--ac2`, used elsewhere only in `profile-showcase.html`) |
| Conv-list avatar | Generic emoji (👤/🏢/🎓) — `avatar_url` from the API was fetched but never rendered | Real photo (`<img>`) when `avatar_url` is set; else initials avatar colored per account type (`.t-emp`/`.t-co`/`.t-edu`) |
| Account type | Implied only by the avatar emoji | Explicit small corner badge (`.ci-type-badge` / `.ch-type-badge`) with icon + Arabic label, separate from the avatar |
| Conv-list time | `.ci-time` existed in CSS but was never populated by JS | Populated from `c.created_at` (already in the API response) |
| Chat header avatar/status | Emoji icon; `#chatStatus` was always cleared to `''` (dead element) | Same avatar/badge treatment as conv-list; `#chatStatus` now shows **"آخر نشاط غير متاح"** |
| Nav back button | Bordered pill with arrow + "رجوع" text — visually heavy | Compact 34×34 icon-only ghost button (border/background only on hover) |
| Search bar | Plain wide rectangular input | Pill-shaped (`border-radius:999px`), tighter padding — same scoping as before (lives only inside `#convList`, never inside `#chatArea`) |
| Spacing | `.messages` padding `20px 20px 12px` | `22px 20px 18px` — more breathing room above the first bubble and above the composer |
| Attach button | `opacity:.45` (nearly invisible) | `opacity:.65` — still visibly disabled/"coming soon", no longer looks broken |

#### Online/offline status — explicitly NOT implemented

There is **no general presence signal exposed to clients** anywhere in the
codebase. `ConnectionManager.active_conversations` (server.py) only tracks which
conversation a user currently has open, for immediate read-receipt delivery — it
is never broadcast to other users and has no "last seen" timestamp backing it.
No DB column or API field carries online/offline/last-seen data today.

Per explicit product instruction, this pass **does not fabricate a fake online
indicator**. `#chatStatus` shows the honest fallback text "آخر نشاط غير متاح"
("activity status unavailable") instead. Wiring real presence would require a
new backend feature (broadcast `ConnectionManager.active` connection state, or a
`last_seen` column) and is out of scope here — track as future work, not implied
by this UI pass.

#### Render-markup-only changes in `messages.render.js`

Added pure-presentation helpers — `typeInfo()`, `avatarHtml()`, `typeBadgeHtml()`,
`formatConvTime()` — and extended `openConversation(otherId, name, type, avatarUrl)`
(previously `(otherId, name, typeIco)`) to carry `user_type`/`avatar_url` through to
the chat header. No new HTTP calls, no new WebSocket messages, no change to
`doSendMessage()`, `renderMessageStatus()`, `showTypingBubble()`, or the debug panel.

### Reference-inspired redesign pass (header / search+filters / online row)

A third pass restructured `messages.html`/`messages.css` (plus small additive
helpers in `messages.render.js`) to match the feel of a reference messenger
screenshot supplied by the product owner — **without copying it literally and
without adding the bottom navigation bar shown in that reference** (a unified
bottom nav for the whole site is planned separately and explicitly out of
scope here). Cache-busting bumped to `?v=v11` on `messages.css` and all 5 JS
files.

| Area | Before | After |
|------|--------|-------|
| Header | `.nb` back button + `.nav-title` span + logo pinned to the edge via `margin-left:auto` | Back button + centered `.nav-brand` (logo + "الرسائل" title + "تواصل احترافي يبني الفرص" subtitle) + a `.nav-spacer` matching the back button's width so the brand block is visually centered. Height `56px → 60px` (still compact, two short lines) |
| Search | Single `.conv-search` input, no filters | `.conv-toolbar` wraps a pill search input (placeholder "ابحث في الرسائل أو الأشخاص...") with an inline 🔍 icon, plus two filter chips (`.cf-chip[data-filter="all"\|"unread"]`) |
| Conversation filtering | None | `applyConvFilter()` in `messages.render.js` — pure client-side DOM filter (hides `.conv-item` elements that don't match the active chip and/or the search text). No new API calls; re-applied automatically every time `renderConvList()` re-renders (e.g. on the 10s poll) so the filter survives list refreshes |
| "Online now" row | Did not exist | New `#onlineRow` / `#onlineRowItems` block between the toolbar and the conversation list, with a `renderOnlineRow(users)` helper in `messages.render.js` |
| Active conversation card | `border-right:3px solid var(--ac)` (hard edge) | `box-shadow:inset 0 0 0 1px rgba(0,200,150,.32)` — a soft full-perimeter cyan ring instead of a hard right-side bar |

#### "المتصلون الآن" (online row) — explicitly NOT populated with real data

Same constraint as the chat-header status field (§62): **no client-accessible
presence/"who is online" signal exists anywhere in the backend.**
`ConnectionManager.active` (in-memory, server-side only) is never exposed via
any endpoint or WebSocket broadcast. `renderOnlineRow(users)` is a
structurally-ready component — it renders a real avatar, short name, a green
online dot, and an account-type corner badge per user *if* an array is ever
passed to it — but nothing in this pass calls it with live data. The static
markup shipped in `messages.html` therefore always shows the honest fallback:
"لا يوجد متصلون حالياً". Wiring this up for real would require a new backend
presence broadcast — out of scope, tracked as future work, not implied by
this UI pass.

#### Verification badge — explicitly NOT shown (data gap, not a UI choice)

The reference image shows an inline checkmark next to some names. `profiles.is_verified`
exists in the schema and is used elsewhere (e.g. public profile pages), but
`get_conversations()` in `auth.py` does not `SELECT p.is_verified`, so this
data never reaches the messages page today. No badge was added to avoid
fabricating verification status; adding it requires a backend query change
(forbidden in this pass) — tracked as future work.

#### Filter icon button — intentionally omitted

The reference's small standalone filter-icon button (beside the search bar)
was not added. The two chips ("الكل" / "غير المقروءة") already cover the only
clearly-specified filter behavior; a third icon button with no defined action
would have shipped as a dead control. Omitted by design, not a missed
requirement — flag if a specific second filter dimension (e.g. by account
type) is wanted and it can be added as a real, working control.

#### Forbidden (still enforced)

- No bottom navigation bar was added anywhere in `messages.html` — confirmed
  by inspection of the final markup; the 5-icon bottom bar in the reference
  image was deliberately not replicated
- No changes to `server.py`, `auth.py`, WebSocket message types, the HTTP
  send pipeline, typing-bubble logic, read-receipt logic, or
  `messages.debug.js` — `git diff --stat` against `main` shows only
  `messages.html`, `messages.css`, `messages.render.js`, `ARCHITECTURE.md`
- `applyConvFilter()` / `initConvFilters()` / `initConvSearch()` /
  `renderOnlineRow()` are additive, render-markup-only helpers — they read
  already-rendered DOM text and already-available conversation data; they
  issue no new HTTP/WebSocket requests

### Unified header pass — `messages.html` now uses profile.html's `.toolbar`

A follow-up correction: the page-specific `.nav`/`.nb`/`.nav-brand` header
built in the previous pass was replaced with the **same header component
`profile.html` actually uses** — `.toolbar` / `.tb-logo` / `.tb-btn.tb-ghost`
— copied verbatim (same selector names, same `height:50px`, same blur/colors)
from `profile.html`'s `<style>` block into `messages.css`, instead of the
generic `.nav` pattern used by `home.html`/`company.html`/`edu.html`. Cache
bump: `?v=v12`.

**Note on "logo in the center":** the request asked for the logo to sit in
the middle "like the profile page," but `profile.html`'s real `.toolbar`
does not center its logo — `.tb-logo{margin-left:auto}` pins it to one edge,
with action buttons clustered on the other side (verified by rendering the
real `/profile` page, not by reading the CSS alone). Since "نفس الهيدر
تماماً" (identical to the profile header) was the more heavily emphasized,
literal, and testable instruction, fidelity to the real component took
priority over the "centered" description — the messages.html toolbar now
positions its logo exactly where profile.html's does (edge-pinned), not
dead-center. Flag if true centering is wanted as an intentional deviation
from `profile.html`'s actual layout.

| Toolbar slot (right → left, RTL source order) | profile.html | messages.html |
|---|---|---|
| Logo | `Logo.svg`, `.tb-logo` | same `Logo.svg`, same `.tb-logo` |
| Next to logo | 🏠 → `home.html` (hardcoded, employee-only page) | 🏠 → `goMessengerHome()`: type-aware (`/home` emp, `/company` co, `/edu` edu), since unlike `profile.html`, `messages.html` is shared by all three user types |
| *(removed)* | 👁 preview toggle | **not present** — preview has no meaning outside profile editing |
| Notifications | 🔔 → `notifications.html` | 🔔 → `/notifications` |
| *(removed)* | 💬 messages → `messages.html` | **not present** — would be a self-link from the messages page |
| Profile | *(not present — page is already "my profile")* | 👤 → `goMessengerProfile()`: `/u/{tw_id}` (same pattern as `home.html`'s `goProfile()`) |
| Menu/settings | ⚙️ → `openPanel()` (opens profile-editing accordion — style/sections/etc., meaningless outside `profile.html`) | ☰ → **visually present, intentionally inert** (`opacity:.65; cursor:not-allowed`, title "القائمة (قريباً)") — same "designed but not wired" treatment already used by the existing `.attach-btn` ("إرفاق ملف (قريباً)"). `profile.html`'s side panel is profile-editing-specific markup/JS and isn't portable to this page; building a new generic menu wasn't requested and would be new scope |

"الرسائل" page title (`.msg-page-title`) + subtitle (`.msg-page-subtitle`)
moved out of the fixed header entirely and now render as the first child of
`#convList`, directly above the search/filter row. This means the title is
part of the conversation-list view only — opening a conversation hides
`#convList` (mobile) or simply isn't where the title lives (desktop column),
so inside a chat only the unified `.toolbar` plus the chat-specific
`.chat-head` show, per the requirement that the per-conversation header
follow directly under the unified site header with no page title in between.

`goMessengerHome()` / `goMessengerProfile()` both call the existing
`sendInactiveConversation()` before navigating away, mirroring `goHome()`'s
existing guard — reusing an already-shipped function, not new WebSocket logic.

### Header source correction — Profile V2, not `profile.html` (supersedes the pass above)

A read-only audit (triggered by user-reported confusion between "the old
profile and the new profile") established that `profile.html`'s `.toolbar`
— used as the copy source in the previous pass — is **not** the site's
current/actively-developed profile surface. Hard evidence:

- `profile.html` git history: ~195 commits, **all** `"Add files via upload"`
  — no descriptive feature commits, ever.
- `profile-showcase.html` git history: ~96 commits with real feature
  messages (`feat: follow list filter`, `fix: Profile V2 header badges`...)
  — actively maintained, internally branded **"Profile V2"**.
- `server.py:443-458` (`/u/{tw_id}`) docstring literally says *"Public share
  URL for Profile V2. Serves profile-showcase.html..."*; commit `ccd94ca`
  is titled *"fix: profile routing — /u/{tw_id} everywhere, no profile.html
  refs"*.
- `profile-showcase.html`'s header (`.sc-header`, defined in external
  `/static/profile-v2.css:14`) centers its logo via real CSS —
  `position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)` —
  unlike `profile.html`'s edge-pinned `.tb-logo{margin-left:auto}`. This is
  the literal source of the "centered logo" mismatch flagged (but not yet
  resolved) in the previous pass.

**Messenger Header Source Contract** (binding for all future header work
on `messages.html` and any other page that unifies its header with the
profile page):

- The approved header source is **Profile V2**: `profile-showcase.html` /
  `/static/profile-v2.css` (`.sc-header` / `.sc-logo` / `.sc-home-pill` /
  `.sc-head-icons` / `.sc-hicon`).
- `profile.html` (`.toolbar` / `.tb-logo` / `.tb-btn` / `.tb-ghost`) must
  **not** be used as a visual reference for any new header work — it is
  legacy (owner-editing surface only, never feature-developed).
- The old `Logo.svg` asset must not be used in any newly-unified header;
  the official mark is `33333.svg`.
- Any future header change must state which of these two sources it is
  built from, in its own ARCHITECTURE.md entry.

### `messages.html` header rebuilt from `.sc-header` (Profile V2)

Replaced the `.toolbar`/`.tb-logo`/`.tb-btn` block (copied from `profile.html`
in the previous pass) with `.sc-header`/`.sc-logo`/`.sc-home-pill`/
`.sc-head-icons`/`.sc-hicon` — copied from `profile-showcase.html:16-60` and
`/static/profile-v2.css:14-44` — into `messages.html` + `messages.css`.
Cache bump: `?v=v14` on `messages.css` and all 5 JS files.

| Slot | Profile V2 source (`profile-showcase.html`) | `messages.html` |
|---|---|---|
| Home pill | `.sc-home-pill` → `/home` (hardcoded) | same class, `goMessengerHome()` (type-aware: `/home` emp, `/company` co, `/edu` edu) |
| Logo | `.sc-logo img`, `33333.svg`, centered via `position:absolute;left:50%;top:50%` | identical — same asset, same centering rule |
| *(removed)* | 👁 eye/preview (`.sc-eye-wrap`, owner-only) | **not present** — no preview concept on the messages page |
| Notifications | `.sc-hicon` bell → `/notifications` | same class, → `/notifications` |
| *(removed)* | 💬 messages → `/messages` | **not present** — self-link from the messages page |
| Profile | *(not present — page is already the profile)* | **added**: `.sc-hicon` user icon → `goMessengerProfile()` (`/u/{tw_id}`, the same Profile V2 public route) |
| Menu | `.sc-hicon` ☰ → `history.back()` | same class, now a **real working dropdown** (`.sc-menu-wrap`/`.sc-menu-dropdown`) — see below |

**Icon rendering — inline local SVG, no emoji, no external CDN (revised):**
The Lucide CDN (`unpkg.com/lucide@0.460.0`, used by `profile-showcase.html`
via `<i data-lucide="...">`) failed to load in this session's test sandbox
(`net::ERR_CERT_AUTHORITY_INVALID`). An earlier pass shipped plain emoji
(🏠/🔔/👤/☰) as a stopgap — this was explicitly rejected ("لا أريد أيقونات
الهيدر تكون إيموجي... هذا لا يعطي شكل Premium") because emoji do not read as
a premium product UI and render inconsistently across platforms/fonts.
**Fix:** all header icons (home, bell, user, hamburger, gear) are now
hand-authored inline `<svg>` markup directly in `messages.html` — no
`data-lucide` attribute, no external script tag, no network dependency at
all. They follow the same outline-icon convention Lucide uses (`viewBox
0 0 24 24`, `fill="none" stroke="currentColor" stroke-width="2"
stroke-linecap="round" stroke-linejoin="round"`) so they are visually
consistent with the rest of the icon language, but the path data is
hand-drawn, not copied from Lucide's source (no network-verified copy of
the exact paths was obtainable in this sandbox). Sized via two new CSS
classes: `.sc-svg-icon` (20×20, header icon buttons) and `.sc-svg-icon-sm`
(14×14, home-pill icon + dropdown-item icons).

**Menu button — real working dropdown, not a dead control (revised):**
The ☰ button no longer just calls `toggleConvList()` silently — it opens an
actual dropdown menu (`#scMenuDropdown`, toggled via `toggleHeaderMenu()` in
`messages.render.js`) styled on the codebase's own existing `.sc-eye-menu`
pattern (`profile-v2.css:485-512` / `profile-v2.render.js:923-955`: toggle
`.open` class on click, `stopPropagation()`, outside-click closes it via a
`document`-level listener). It contains four real links, each with its own
inline SVG icon:

| Item | Target |
|---|---|
| الرئيسية | `goMessengerHome()` — type-aware (`/home`/`/company`/`/edu`) |
| الملف الشخصي | `goMessengerProfile()` — `/u/{tw_id}` |
| الإشعارات | `/notifications` |
| الإعدادات | `/settings` (single shared route for all account types, `server.py:630-634`) |

The button no longer looks active while doing nothing — every item it
exposes is a real, already-existing route.

**Layout height changed 50px → 42px** (real measured height of
`.sc-header` via Playwright on `/profile-showcase`, not assumed) —
`.layout{margin-top}`, the `height:calc(...)` rules, and the mobile
`.conv-list.mobile-show{inset:...}` rule were all updated to match.
`position:fixed` is used instead of the source's `position:sticky`,
because `messages.html` is a fixed-viewport app-shell (`body{overflow:
hidden}`) with no scrolling ancestor for `sticky` to stick within —
`profile-showcase.html` is a normally-scrolling page, so `sticky` works
there but would not behave correctly here. This is a structural adaptation
required by the surrounding layout, not a visual deviation.

Dead code removed: `goHome()` in `messages.render.js` (superseded by
`goMessengerHome()` in the previous pass, had zero remaining callers).

#### Forbidden (still enforced)

- No changes to `server.py`, `auth.py`, WebSocket message types, the HTTP
  send pipeline, typing-bubble logic, read-receipt logic, or
  `messages.debug.js` — confirmed via `git diff --stat HEAD` showing only
  `messages.html`, `messages.css`, `messages.render.js`, `ARCHITECTURE.md`
- No bottom navigation bar added
- `profile.html`/`.toolbar`/`.tb-logo`/`.tb-btn`/old `Logo.svg` are no
  longer referenced anywhere in `messages.html`/`messages.css` (verified
  via grep — zero matches)

### Shared Header — Home Button: Pill → Icon-Only Ghost Button

**Supersedes the "Home pill" row of the `messages.html` header table
above and the original `.sc-home-pill` markup in `profile-showcase.html`.**
Both pages share the same `.sc-header` contract (per the rule at the top
of that section: "any future header change must state which of these two
sources it is built from"), so this change was applied identically to
both `messages.html`/`messages.css` and `profile-showcase.html`/
`profile-v2.css` — there is no longer a `.sc-home-pill` class anywhere in
the codebase.

**Why:** the green "الرئيسية" pill (icon + Arabic label, ~18px side
padding, full accent-color fill) was visually much wider than the other
header buttons (bell/profile/menu — plain 28px ghost icon buttons), so it
dominated one side of the header and made the centered logo look
off-balance even though `.sc-logo`'s `position:absolute;left:50%` keeps
it mathematically centered regardless of sibling width. Reported as
"كبير... وعم يسرق الانتباه من الشعار... لا يعطي إحساس Premium" with a
production screenshot from `/profile`.

**Fix:** the home button now uses the exact same classes as every other
header icon button — `.sc-hicon.sc-hicon-bare` — with no text, icon only,
`title="الرئيسية"` kept for accessibility/desktop-hover tooltip only:
```html
<!-- messages.html -->
<button type="button" class="sc-hicon sc-hicon-bare" onclick="goMessengerHome()" title="الرئيسية">
  <svg class="sc-svg-icon" ...>...</svg>
</button>

<!-- profile-showcase.html -->
<button class="sc-hicon sc-hicon-bare" id="scHomeBtn" title="الرئيسية"><i data-lucide="home" class="ico"></i></button>
```
`onclick`/`id="scHomeBtn"` and their JS wiring (`goMessengerHome()` /
`profile-v2.render.js`'s `homeBtn.onclick`) are untouched — same route
logic (`/home` emp, `/company` co, `/edu` edu on the messages page;
`/home` on the showcase page), confirmed via Playwright click test
(`/messages` → click → lands on `/home`).

**CSS — one ghost-icon rule instead of two near-duplicates.** Previously
`.sc-hicon-bare` only stripped background/border, and a second,
more-specific selector `.sc-head-icons .sc-hicon-bare` shrank it to
`width:auto;height:auto;padding:4px` — but that scoped rule only matched
buttons living inside `.sc-head-icons`, which the home button (on the
opposite side of the logo) is not. Folding the sizing into the base
`.sc-hicon-bare` rule (no `.sc-head-icons` scope needed) means the home
button now renders at the same ~28px (`messages.html`) / ~26px
(`profile-showcase.html`) footprint as the bell/profile/menu icons,
without any new selector dedicated to it — verified via Playwright
`getBoundingClientRect()`: home button and the three other header icons
all measured **28×28px** on `/messages`, logo center exactly equal to
header center on both pages.

- **Files changed:** `messages.html`, `messages.css`, `profile-showcase.html`,
  `profile-v2.css`. No `server.py`/`auth.py`/WebSocket/send-pipeline/
  typing/read-receipt/`messages.debug.js` changes — confirmed via
  `git diff --stat`.
- **Version bump:** `messages.css`/`messages.*.js` `v=v19` → `v=v20`;
  `profile-v2.css` `?v=cards-v1` → `?v=header-v2` (only the CSS changed,
  so only its query param moved — the JS files are untouched).

### Home Button Reversal — Icon-Only Ghost → Medium Brand-Gradient Circle

**Supersedes the previous section ("Pill → Icon-Only Ghost Button") —
explicit user correction.** Making the home button exactly the same size
as the other ghost icons (~28px) was reported as wrong: "زر الرئيسية مهم
جداً، لذلك لا أريده صغيراً مثل باقي الأيقونات تماماً" (the home button
matters too much to be that small) — but the original oversized green text
pill (`.sc-home-pill`, removed in the previous section) is *also*
explicitly ruled out: "لا يرجع كبير مثل زر الرئيسية القديم... لا يكون pill
طويل".

**Fix — new `.sc-home-btn` class**, applied on top of the existing
`.sc-hicon` base (replacing `.sc-hicon-bare` on the home button only; every
other header icon keeps `.sc-hicon-bare` unchanged):
```css
.sc-home-btn{
  width:34px;height:34px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#00c896,#00b8c4,#2563ff);
  box-shadow:0 2px 10px rgba(0,184,196,.35);
  color:#06121c;
}
```
- **34×34px, circular** — between the 28px ghost icons and the old pill;
  matches `.sc-hicon`'s original (pre-ghost) box size, just restored and
  made circular instead of the `border-radius:10px` square.
- **Cyan/teal/blue brand gradient** (`--ac`→`--ac3`-ish/`--ac2` literal hex,
  hardcoded since `--ac3` only exists in `messages.css`, not
  `profile-v2.css` — see root-vars note above) instead of a flat fill, per
  "يكون فيه gradient خفيف cyan/teal/blue".
- **Icon-only, no label** on both pages — `title="الرئيسية"` only, exactly
  as before. Logo stays mathematically centered (`.sc-logo`'s
  `position:absolute;left:50%` is unaffected by sibling width either way).
- **Route/click logic untouched** — same `onclick="goMessengerHome()"` /
  `id="scHomeBtn"` + `profile-v2.render.js` wiring as before (now reading
  `twHomeHref()`, see next section).
- **Files changed:** `messages.html`, `messages.css`, `profile-showcase.html`,
  `profile-v2.css`, `profile-v2.render.js`. No backend/WebSocket/send-pipeline
  changes.

### Global Header Menu Contract

**Rule (mandatory for all AI sessions):**
- The `.sc-header` header contains **primary navigation only** — home, profile, messages, notifications.
- The ☰ dropdown contains **secondary tools only** — settings, contact/report/suggest, logout, preview.
- **Never duplicate primary nav items inside the ☰ menu.** They are already one tap away in the header.

The unified ☰ dropdown is owned by `tw_shared.js` and used by both `messages.html` and
`profile-showcase.html`. Any future page adopting `.sc-header` should wire its ☰ button
with `initGlobalHeaderMenu()` instead of building its own dropdown.

#### Canonical item list (secondary tools only)

1. **المعاينة** — owner-only, first item, static HTML in `#scMenuDropdown` (see eye section below)
2. **الإعدادات** → `/settings` (active link)
3. **تواصل معنا** — disabled / `قريباً` (no route exists yet)
4. **الإبلاغ عن مشكلة** — disabled / `قريباً` (no route exists yet)
5. **اقترح ميزة** — disabled / `قريباً` (no route exists yet)
6. **تسجيل الخروج** — danger/red, `twLogout()` (clears `tw_user` + `tw_jwt`)

Items 2–6 are dynamically rendered by `initGlobalHeaderMenu()` into `#scMenuDynamic`.
Disabled items use `<div class="sc-menu-item disabled">` with a "قريباً" pill — they render visually
but are not clickable, per "لا تضع زر شكله يعمل وهو لا يعمل".

#### Eye preview — migrated from header to menu (profile-showcase.html only)

The eye/preview button was previously a standalone icon in `.sc-head-icons`. It is now
the **first item inside `#scMenuDropdown`**, visible only when `body.view-owner` is set.

**Why static, not dynamically generated:** the eye section has direct `addEventListener`
bindings in `profile-v2.render.js`'s IIFE (bound once at page load, by ID:
`scEyeBtn`, `scEyeMenu`, `scPreviewPublic`, `scPreviewGuest`, `scPreviewEnd`).
If these nodes were regenerated via `dd.innerHTML = ...` on every menu open, the original
DOM nodes would be discarded and the bindings lost. To preserve them: the eye markup lives
as **static HTML** in `#scMenuDropdown`, above a separate `<div id="scMenuDynamic">` into
which tw_shared.js renders the 5 dynamic items — `initGlobalHeaderMenu` renders into
`#scMenuDynamic`, not `#scMenuDropdown`. This means the eye section survives re-renders.

Eye sub-menu (معاينة كمستخدم مسجل / معاينة كزائر / إنهاء المعاينة) is an inline-flow expand
(not a floating absolute popup): `position:static` overridden inside `.sc-menu-dropdown .sc-eye-menu`
so it opens in-place vertically below the trigger row. Selecting any preview option calls
`closeAllMenus()` (profile-v2.render.js) which closes both the eye sub-menu and the parent
`#scMenuDropdown` — consistent with "تغلق بعد اختيار أي عنصر".

All icons are inline local SVG (replaced the original Lucide `<i data-lucide="...">` tags in
the eye section). Toggle behavior (`.open` class, `body.preview-public-user`/`body.preview-guest`
classes, `eyeBtn.stopPropagation()`) is unchanged.

#### `initGlobalHeaderMenu(btnId, ddId, dynId?)` API

| Param | Required | Purpose |
|-------|----------|---------|
| `btnId` | Yes | ID of the `<button>` that toggles the dropdown open/closed |
| `ddId` | Yes | ID of `.sc-menu-dropdown` — the visible box to toggle |
| `dynId` | Optional | ID of the inner container to render dynamic items into. Defaults to `ddId`. Use `'scMenuDynamic'` on profile-showcase.html since `#scMenuDropdown` also contains the static eye section. |

Closing the dropdown also collapses `#scEyeMenu` (if present) so it always resets on next open.
`window.twBeforeHeaderNav(key)` hook (defined per page) runs synchronously before any menu link
navigates away — messages.render.js uses it to call `sendInactiveConversation` on the open
conversation, consistent with what the dedicated header buttons already do.

#### Wiring per page

```js
// messages.render.js — no eye section, renders into #scMenuDropdown directly
initGlobalHeaderMenu('scMenuBtn', 'scMenuDropdown');

// profile-v2.render.js — renders dynamic items into #scMenuDynamic, leaving
// the static eye section above it untouched
initGlobalHeaderMenu('scMenuBtn', 'scMenuDropdown', 'scMenuDynamic');
```

#### Markup contract for `#scMenuDropdown`

**messages.html** (no eye section):
```html
<div class="sc-menu-wrap" id="scMenuWrap">
  <button id="scMenuBtn" class="sc-hicon sc-hicon-bare">...</button>
  <div class="sc-menu-dropdown" id="scMenuDropdown"></div>  <!-- rendered by tw_shared.js -->
</div>
```

**profile-showcase.html** (with static eye section):
```html
<div class="sc-menu-wrap" id="scMenuWrap">
  <button id="scMenuBtn" class="sc-hicon sc-hicon-bare">...</button>
  <div class="sc-menu-dropdown" id="scMenuDropdown">
    <div class="sc-eye-wrap" id="scEyeWrap">  <!-- static, always present in DOM -->
      <button class="sc-menu-item sc-eye-btn" id="scEyeBtn">...</button>
      <div class="sc-eye-menu" id="scEyeMenu">...</div>
    </div>
    <div class="sc-menu-sep" id="scMenuEyeSep"></div>   <!-- visible only body.view-owner -->
    <div id="scMenuDynamic"></div>                       <!-- rendered by tw_shared.js -->
  </div>
</div>
```

#### Forbidden (Global Header Menu)

- **Never put home / profile / messages / notifications inside the ☰ menu** — they are
  primary nav, already present as header buttons.
- **Never add external icon CDN or emoji** to menu items — inline local SVG only.
- No backend / WebSocket / send-pipeline changes for any header or menu work.

- **Version bumps:** `messages.css`/`messages.*.js` `v=v21` → `v=v22`;
  `profile-v2.css` `?v=header-v3` → `?v=header-v4`.

#### Eye button — glassmorphic icon circle (profile-showcase.html)

The preview/eye trigger button inside the dropdown renders its icon wrapped in
a glassmorphic circle, consistent with the premium header-icon visual language.

```html
<span class="sc-eye-ico-wrap" aria-hidden="true">
  <svg …><!-- eye icon only --></svg>
</span>
المعاينة
```

CSS: `.sc-eye-ico-wrap` — 26×26 px, `border-radius:50%`, teal glass tint
(`rgba(0,200,150,.1)` + `border:1px solid rgba(0,200,150,.22)`). The eye icon
is always the "open eye" (indicating "you can preview") — never eye-off inside
the menu. The eye-off / eye-on switching was removed; the preview state is now
communicated by the header back button appearing (see section below).

---

### Global Header Preview Mode Contract

**Rule (mandatory for all AI sessions on profile-showcase.html):**

When the owner enters a preview mode (معاينة كمستخدم مسجل / معاينة كزائر):

1. **☰ button hides** — `#scMenuBtn` gets `display:none`.
2. **Back button appears** — `#scPreviewBackBtn` (inside `#scMenuWrap`, styled
   `.sc-preview-back`) becomes visible in the same position.
3. **Back button exits preview directly** — no need to re-open the menu. Clicking it
   calls `exitPreview()` then `history.back()` to clean up the history entry.
4. **Browser back (hardware/OS) exits preview first** — entering preview pushes a
   history entry with `{ twPreview: true }`. A `popstate` listener calls `exitPreview()`
   if the body has a preview class. The second back press leaves the page normally.
5. **Switching preview modes (public ↔ guest)** does NOT push a second history entry —
   only one entry per preview session, regardless of how many mode switches occur.
6. **"إنهاء المعاينة"** in the eye sub-menu behaves identically to the header back button.

#### State machine

```
Normal ──(choose preview option)──► Preview
           pushState({twPreview:true})      │
                                            │
Preview ──(back btn / إنهاء المعاينة / popstate)──► Normal
           exitPreview()                           history.back() cleans the entry
```

#### DOM additions (profile-showcase.html only)

```html
<div class="sc-menu-wrap" id="scMenuWrap">
  <button id="scMenuBtn" class="sc-hicon sc-hicon-bare">…</button>
  <!-- Shown only during preview; replaces ☰ -->
  <button id="scPreviewBackBtn" class="sc-hicon sc-preview-back" style="display:none">
    <svg …>← arrow</svg>
  </button>
  <div class="sc-menu-dropdown" id="scMenuDropdown">…</div>
</div>
```

#### JS helpers (profile-v2.render.js — eye IIFE)

| Function | Role |
|----------|------|
| `_inPreview()` | Returns true if body has any preview class |
| `updatePreviewHeader(bool)` | Toggles `#scMenuBtn` / `#scPreviewBackBtn` visibility |
| `exitPreview()` | Removes preview classes, closes menus, updates header |
| `enterPreviewMode(type)` | Sets preview class, updates header, pushes history once |

#### Forbidden (Preview Mode)

- **Never call `history.back()` without first calling `exitPreview()`** — DOM state
  and history must stay in sync.
- **Never use browser back to navigate to a different URL** — `pushState` without a
  URL argument keeps the URL unchanged; only the state differs.
- **Never add backend / WebSocket / API calls** for entering or exiting preview — it
  is a purely CSS-class-based client-side feature.
- **Never move the back button outside `#scMenuWrap`** — it must occupy the same
  flex slot as ☰ to avoid header layout shifts.

### Messenger Identity Display Contract

**Binding for all future work on how `messages.html` shows the other party
in a conversation (avatar/name/account-type), and on the chat-head/menu/back
behavior.** This supersedes the chat-head shape used in the previous passes
above.

- **Person identity (avatar + name + account-type badge) must read the same
  way it does in the followers list** (`profile-v2.render.js`'s
  `_renderItems()` / `.sc-fl-*` classes): a real photo when `avatar_url` is
  set, a meaningful fallback when it is not (never a random/generic
  placeholder), the name in full, and the account type shown as a small
  **text-only color-tinted pill** next to/under the name — موظف / شركة /
  جهة تعليمية. No emoji in the type indicator.
  - Avatar fallback in `messages.html` is the first-letter initial on a
    type-colored gradient (`avatarHtml()` in `messages.render.js`, unchanged
    from prior passes) rather than the followers list's generic person-icon
    placeholder — both are "real, meaningful fallbacks, not random
    placeholders"; the messenger's own initials convention was kept because
    it is already used consistently across the conv-list, chat header, and
    (dormant) online row, and rewriting the avatar fallback itself was out
    of scope (only `messages.html`/`.css`/`.render.js` markup, no new
    backend data was introduced or needed).
  - The account-type **badge** is what changed to match the followers
    list's "spirit": `typeBadgePillHtml(type)` (new helper in
    `messages.render.js`) renders `<span class="type-badge-pill {t-emp|t-co|
    t-edu}">{label}</span>` — label only, no emoji, background tinted to
    ~10% opacity of the type's accent color (green/blue/purple), exactly the
    same visual language as `profile-v2.css`'s `.sc-fl-type-badge--*`. This
    replaces the old `.ch-type-badge`/`.ci-type-badge` (emoji + label pill /
    emoji-in-a-circle-on-the-avatar-corner) in both the chat header and the
    conversation-list cards.
- **No placeholder buttons.** Every control shown must do something real:
  - The profile button is **not** a separate header action anymore — it
    lives inside the chat-options menu (`#chMenuDropdown`) as "عرض الملف
    الشخصي", calling the pre-existing `viewConvProfile()`.
  - The one genuinely-not-built-yet option ("إعدادات المحادثة") is rendered
    with the native `disabled` attribute, dimmed (`opacity:.45`,
    `cursor:not-allowed`, no hover state) and tagged "قريباً" — it cannot be
    clicked and does not look interactive.
- **Back-to-list is an explicit UI action, never `history.back()`.**
  `backToConvList()` (new, `messages.render.js`) clears `_currentConvId`/
  `_activeConvMeta`, resets the chat-head to its empty state, re-shows the
  conv-list (`#convList.mobile-show`), and calls
  `history.pushState(null, '', '/messages')` — it adds a history entry
  rather than erasing one, so the browser back button still works normally
  afterward; it never relies on `history.back()`, which would be one
  unrelated page in the user's actual browsing history, not necessarily
  "previous conversation". Two entry points call it: the small chevron
  beside the conversation name (`#chBackArrow`) and "الرجوع لقائمة الرسائل"
  inside the chat-options menu.
- Any future change to person-identity rendering anywhere in the messenger
  must keep avatar/name/badge sourced from `typeInfo()`/`avatarHtml()`/
  `typeBadgePillHtml()` in `messages.render.js` — do not reintroduce a
  one-off inline rendering path.

#### `messages.html` chat-head restructured around this contract

| Before | After |
|---|---|
| `.ch-back` (☰) — toggled `#convList.mobile-show`, mobile-only, called `toggleConvList()` | **removed** (dead code `toggleConvList()` deleted, zero remaining callers) |
| `.ch-actions > #viewProfileBtn` ("👤 الملف") — always-visible standalone button | **removed** — folded into the chat-options menu |
| *(none)* | **added**: `#chMenuBtn` (☰, beside the avatar) opens `#chMenuDropdown` — عرض الملف الشخصي / نسخ رابط الملف (new: `copyConvProfileLink()`, clipboard) / الرجوع لقائمة الرسائل / إعدادات المحادثة (disabled, "قريباً") |
| *(none)* | **added**: `#chBackArrow`, a small chevron beside `#chatName`, calls `backToConvList()` |
| `#chatTypeBadge` — emoji + label, solid gradient fill, `color:#fff` | same id, now `type-badge-pill {t-emp|t-co|t-edu}` — label only, tinted background |
| `#chatStatus` — "آخر نشاط غير متاح" (unchanged; no real presence data exists) | unchanged |

`#chMenuBtn`/`#chBackArrow` are hidden by default and only shown once
`openConversation()` populates the header — there is no conversation
selected, so there is nothing for them to act on (same "don't show an
active-looking button with no function" rule applied to this redesign too).

#### `messages.html` conv-list cards restructured around this contract

`renderConvList()`'s per-item template, the `_activeConvMeta` placeholder
item, and `handleWithParam()`'s placeholder item all moved the type
indicator from an absolutely-positioned emoji badge at the avatar's corner
(`.ci-type-badge`, now unused/removed from CSS) into a `.ci-sub` row under
the name, rendered via `typeBadgePillHtml(type)` — same pill used in the
chat header.

#### Explicitly NOT touched by this pass

- `renderOnlineRow()` ("المتصلون الآن") — still dead code with zero
  production callers (per the prior pass's documented finding); its
  `.online-type-badge` corner-emoji badge was intentionally left as-is since
  it never renders in production and touching unused code was out of scope.
- `server.py`, `auth.py`, WebSocket message types, the HTTP send pipeline,
  typing-bubble logic, read-receipt logic, `messages.debug.js`, the DB —
  confirmed via `git diff --stat HEAD`.

### Messenger Conversation Card Contract

**Binding for the shape of conv-list cards, avatar geometry everywhere in
the messenger, the chat-head "last activity" line, and how the phone/browser
back button behaves while a conversation is open.** Refines (does not
contradict) the Messenger Identity Display Contract above — same
avatar/name/badge source-of-truth, different container shape and history
handling.

- **All avatars are circular, everywhere in `messages.html`.** `.ci-ava`
  (conv-list) and `.ch-ava` (chat header) changed from a rounded-square
  (`border-radius:14px`/`12px`) to `border-radius:50%`, matching the
  followers/profile avatar convention. `.online-ava` (online row) was
  already circular — unchanged. The chat-options menu has no avatars, so
  nothing to change there. Fallback (no `avatar_url`) stays the existing
  initials-on-gradient (`avatarHtml()`), now rendered inside a circle
  instead of a rounded square — never a square placeholder.
- **Conv-list items are cards, not list rows.** `.conv-item` gained
  `margin`, `border-radius:16px`, `background:var(--card)`, and a visible
  `border` — a distinct rectangle per conversation instead of a row
  separated only by a hairline `border-bottom`.
- **Card layout is two columns**, matching the reference: avatar + identity
  block on the right (avatar → name → account-type pill → last message),
  time + unread badge in a separate `.ci-aside` column on the far left.
  Previously time lived inside the name's own row (`.ci-top`, now removed)
  and the unread badge was absolutely-positioned over the card; both are
  now in the same dedicated aside column, vertically centered.
  - **Unread count is now the real per-conversation count.** `get_conversations()`
    in `auth.py` already computes and returns `unread_count` per conversation
    (unchanged, pre-existing, not touched this pass) — the frontend
    previously ignored it and always rendered a hardcoded `"1"` badge
    whenever the latest message was unread. `renderConvList()` now reads
    `c.unread_count` directly and shows the real number (capped at `99+`),
    and applies the (previously dead) `.conv-item.unread` CSS class so the
    already-existing bold/white "unread" name styling actually activates.
  - **No pin icon.** There is no "pinned conversation" concept anywhere in
    the data model (`messages` table has no such column, `get_conversations()`
    returns no such flag) — per the instruction to only prepare a UI slot
    for fields that exist, the aside column has no pin slot at all rather
    than a fake/always-disabled one.
  - **No online dot on conv-list cards.** Same reasoning as the (dormant)
    online row: no backend signal exists for "is this specific conversation
    partner online right now" — inventing one would violate the
    no-fake-presence rule established in the Identity Display Contract
    above. The avatar/card structure has room for one if presence data is
    ever added, but no dot markup is rendered today.
  - **Profession/specialty field:** `get_conversations()`'s `SELECT` only
    joins `profiles.avatar_url`, not `headline`/`title` — no per-conversation
    profession data is available from this endpoint today, and adding it
    would mean touching `auth.py`/`server.py`, out of scope for a
    frontend-only pass. Per the "no ugly gap" rule, the card's `.ci-sub` row
    always shows the account-type pill in that slot instead — never an
    empty line waiting for a field that doesn't exist.
- **The chat-head "last activity" line is hidden, not removed.** Round 1 of
  this contract showed `"آخر نشاط غير متاح"` as visible (soft) text under
  the name. Direct visual feedback on that screenshot was that the line
  still reads as a distracting bar under the name at this size/weight. The
  element (`#chatStatus`) and the code that sets its text are unchanged —
  `.ch-status{display:none}` in CSS is the only change — so the line can be
  shown again instantly (`.has-value` class) the moment a real
  presence/last-seen signal exists, without any further markup work. Today
  it never renders.
- **Phone/browser back button while inside a conversation must return to
  the conversation list, never leave `/messages`.** This requires a real
  `pushState`/`popstate` pair — there is no other way to intercept a phone's
  hardware back button from a web page:
  - `openConversation()` pushes one history entry (`{ twConvOpen: true }`,
    url unchanged at `/messages`) the *first* time a conversation is opened
    in this page-load (tracked by `_convHistoryPushed`); switching directly
    between conversations afterward does not push additional entries — only
    "no conversation → some conversation" creates a back-stop.
  - A `popstate` listener (`messages.render.js`) fires on the actual
    browser/phone back action. If the entry the browser landed on does
    *not* carry `twConvOpen` and a conversation is currently open, it runs
    `closeConversationUI()` (DOM/state reset only, extracted from the old
    `backToConvList()`) and force-sets the URL to `/messages` via
    `history.replaceState`. The listener never calls `history.back()`
    itself — it only reacts to the native event the real back button
    already produced.
  - The on-screen back controls (`#chBackArrow`, "الرجوع لقائمة الرسائل" in
    the menu) call `backToConvList()`, which now also calls
    `closeConversationUI()` and then `history.replaceState(null, '',
    '/messages')` — overwriting the just-pushed `twConvOpen` entry in place
    rather than stacking a new one on top of it (which would have let a
    *second* press of the hardware back button re-open the same
    conversation — a bug avoided by replacing instead of pushing here).
    `history.length` is unaffected either way (replaceState never adds or
    removes entries) — still "without breaking history" as originally
    required.

### Messenger Badge-Beside-Name Contract

**Refines the Messenger Conversation Card Contract above: the account-type
badge moves from its own line to sit directly beside the name, and the card
gets a soft per-account-type accent.** Pure markup/CSS placement change —
no backend, WebSocket, or send-pipeline code touched.

- **Line 1 is name + account-type badge, side by side.** New
  `.ci-name-row` (conv-list) / `.ch-name-row` (chat header, already existed
  but now also hosts the badge) wraps the name `<span>` and the existing
  `typeBadgePillHtml(type)` pill in a flex row with a small gap — the badge
  is never on its own line and never far from the name. `#chatTypeBadge`
  moved out of `.ch-meta` into `.ch-name-row`, right after `#chatName`.
  The pill itself (`typeBadgePillHtml()`) is unchanged — text-only, no
  emoji, tinted background — only its *position* in the markup changed.
- **Line 2 is the profession/specialty caption, falling back to the
  account-type label.** `.ci-sub` (conv-list) and the new `.ch-role`
  (chat header) render `typeInfo(type).label` as plain soft text (not a
  pill — the pill already lives on line 1). As documented in the
  Conversation Card Contract above, `get_conversations()` in `auth.py`
  has no `headline`/`title` column, so there is no profession data to
  show today; this caption always falls back to the type label rather
  than leaving an empty line. If a profession field is ever added to the
  endpoint, this is the one slot to swap it into.
- **New per-account-type card accent — `acc-emp` / `acc-co` / `acc-edu`.**
  Deliberately namespaced separately from the pre-existing `t-emp` /
  `t-co` / `t-edu` classes, which already style the *solid* avatar-gradient
  background (`.ci-ava.t-emp{background:linear-gradient(...)}`). Applying
  `t-emp` directly to `.conv-item` would have painted the whole card with
  that vivid avatar gradient — reusing the namespace was rejected for that
  reason. `accentClass(type)` (`messages.render.js`) derives the new class
  from the existing `typeInfo(type).cls` by swapping the `t-` prefix for
  `acc-`, so both class sets stay derived from the same single source of
  truth (`_TYPE_INFO`).
  - Each accent is a low-opacity border tint + a faint diagonal gradient
    wash fading into the normal card background, not a solid fill:
    `acc-emp` → `rgba(0,200,150,.2)` border / `rgba(0,200,150,.05)` wash
    (soft green/teal), `acc-co` → `rgba(37,99,255,.2)` / `rgba(37,99,255,.05)`
    (soft light blue), `acc-edu` → `rgba(139,92,246,.2)` /
    `rgba(139,92,246,.05)` (soft purple). Same three brand hues used
    everywhere else in the app (avatars, badges) — just diluted, so the
    card reads as calm/premium rather than loud, and only one accent hue
    appears per card.
  - `.conv-item:hover` / `.conv-item.active` rules are declared after the
    `acc-*` rules so hover/active state still wins on interaction.
- **Forbidden items confirmed respected:** no emoji added to any badge
  (the pill markup is unchanged); badge stays the existing small pill, not
  enlarged or squared; avatars stay circular (untouched this pass); no new
  saturated/loud colors — all three accents use the existing brand hues at
  5–20% opacity; no backend, WebSocket, or send-pipeline file touched
  (only `messages.html`, `messages.css`, `messages.render.js`).
- **No pin icon, still.** Re-confirmed unchanged from the Conversation Card
  Contract above — no backing data field exists.
- **Verified with Playwright** (`renderConvList()` / `openConversation()`
  called directly against real production JS, mock conversations covering
  all three account types) for: badge present and adjacent to the name in
  both the conv-list cards and the chat header (`nameRowHasBadge` /
  `badgeInNameRow`), zero emoji in badge text, distinct `acc-*` class and
  border-color per card matching its type, and no horizontal overflow at a
  390px mobile viewport.
- **Version bump:** `messages.css` and all five `messages.*.js` script tags
  in `messages.html` bumped `v=v16` → `v=v17` (cache-busting only, no
  behavior implied by the version number itself).

### Messenger Card Density Fix — No Duplicate Type Label, Shorter Cards

**Fixes a regression visible in production screenshots of the Badge-Beside-Name
Contract above: the line-2 caption was rendering the account-type label a
second time (it already shows once as the line-1 badge), and the extra line
plus loose padding made cards noticeably taller than the reference design.**
Frontend-only; no backend/API/WebSocket/send/typing/read-receipt/debug/DB
code touched.

- **Line 2 no longer repeats the account type.** `professionLineHtml(c)`
  (`messages.render.js`) replaces the old `typeInfo(type).label` fallback in
  `renderConvList()`'s card template. It reads `c.headline` — a field that
  does not exist yet on `GET /messages/conversations/{user_id}`
  (`get_conversations()` in `auth.py` only selects `avatar_url` from
  `profiles`, confirmed again this pass) — and returns `''` when absent, so
  **no `.ci-sub` element is rendered at all** today. The moment a headline
  field is added to that endpoint, this one function is where it surfaces;
  no other call site needs to change. The two placeholder templates
  (`_activeConvMeta` "new conversation" card, `handleWithParam()`'s
  deep-link card) had their `.ci-sub` line removed outright for the same
  reason — both only ever rendered the duplicate type label.
- **Chat header's `.ch-role` follows the same rule, via CSS instead of
  omission.** `openConversation()` now sets `#chatRole`'s text to `''`
  instead of `typeInfo(type).label`. Because `#chatRole` is a fixed element
  in `messages.html` (toggled across opens/closes, not rebuilt from a
  string template like the cards), a new `.ch-role:empty{display:none}`
  rule collapses it automatically whenever its text is empty — no JS
  branching needed, and it starts showing itself the instant real text is
  set, same self-describing pattern as `.ch-status.has-value` above.
- **Card density reduced** to match the reference screenshot, purely via
  spacing (no information removed beyond the duplicate line above):
  `.conv-item` padding `12px 13px` → `9px 12px`, margin `6px 10px` →
  `4px 10px`, border-radius `16px` → `14px`; `.ci-ava` `46px` → `42px`.
  Combined with the removed duplicate-label line, a card with no real
  profession data (today, always) is consistently shorter than before
  (~62px tall at 390px width vs. the previous ~88px) while staying
  readable — name, badge, and last message no longer have a dead line
  wedged between them.
- **Pin icon: still not added.** Re-confirmed, same reasoning as the
  Conversation Card Contract above — `messages`/`profiles` have no
  "pinned" column anywhere in the schema, so no pin slot is rendered
  (faking one was explicitly out of scope this pass too).
- **Avatars: re-confirmed circular everywhere**, no regression — `.ci-ava`,
  `.ch-ava`, `.online-ava` all compute `border-radius: 50%` with their
  `img` children at `object-fit: cover`; verified via Playwright across
  both photo avatars and the initials fallback (no avatar_url → single
  letter inside the same circular container, never a square).
- **Verified with Playwright** (4 mock conversations spanning emp/co/edu,
  one with no `avatar_url`): zero `.ci-sub` elements rendered (no
  duplicate label), badge still adjacent to the name in both the cards and
  the chat header, `#chatRole` computes `display: none` when empty,
  measured card height ≈62px at 390px width, zero horizontal overflow.
- **Version bump:** `messages.css` and all five `messages.*.js` script tags
  in `messages.html` bumped `v=v17` → `v=v18`.

### Messenger — Profession Caption + `get_messages()` Pagination Bug Fix

**Two independent fixes, both scoped to read-only data and frontend
display — no schema change, no send pipeline/WebSocket/typing/read-receipt
code touched.**

**Bug 1 — root cause confirmed: `get_messages()` dropped the newest
messages once a thread passed 100 rows.** `auth.py`'s `get_messages()`
queried `ORDER BY m.created_at ASC LIMIT 100` directly — for a thread
with more than 100 total messages this keeps the **oldest** 100 rows and
silently discards everything after them, including the actual latest
message. This is why a freshly sent message would appear correctly in
the conversation list (`get_conversations()` uses an unrelated
`DISTINCT ON (other_id) ... ORDER BY ... DESC` query that always grabs
the true latest row per conversation, so it was never affected) and at
send time (appended directly to in-memory thread state), but vanish the
next time the same thread was reopened via `GET /messages/{uid}/{oid}`.
Fix: wrap the query so the latest 100 rows are selected first
(`ORDER BY m.created_at DESC LIMIT 100`), then re-sorted ascending in an
outer query — preserving the exact ascending-order response contract the
frontend already relies on (it never re-sorts, just maps over
`data.messages`):
```python
rows = conn.run(
    "SELECT * FROM ("
    "SELECT m.*, u.full_name as sender_name "
    "FROM messages m JOIN users u ON u.id=m.sender_id "
    "WHERE (sender_id=:uid AND receiver_id=:oid) "
    "OR (sender_id=:oid AND receiver_id=:uid) "
    "ORDER BY m.created_at DESC LIMIT 100"
    ") sub ORDER BY created_at ASC",
    uid=user_id, oid=other_id
)
```
Verified end-to-end against a real seeded Postgres database (105 historical
+ 1 sentinel message in one thread) at three levels: raw SQL via `psql`
(old query → sentinel absent; new query → present), the Python function
directly, and the live authenticated HTTP endpoint via curl with a real
signed JWT. Confirmed via Playwright that reopening the thread — even a
second time — now always shows the latest message.

**Bug 2 — line 2 of the conversation card/chat header now shows real
profession data instead of staying empty.** `get_conversations()` never
selected `profiles.headline`/`profiles.title` — the same canonical
"professional headline" fields already used by `profile.html` and
`profile-v2.render.js` (`prof.headline || prof.title`). Added
`p.headline, p.title` to its existing `SELECT`/JOIN (additive, no new
column, no migration). Frontend (`messages.render.js`): added a
`profession(c)` helper (`c.headline || c.title || ''`) feeding
`professionLineHtml()`, threaded through as a new `data-headline`
attribute on `.conv-item` (same pattern as the existing `data-type`/
`data-avatar`), and a new 5th `headline` parameter on `openConversation()`
that populates `#chatRole` when reopening. When no profession data exists,
both line 2 and `#chatRole` render empty — `.ci-sub` is simply omitted
and `.ch-role:empty{display:none}` (from the prior round) collapses the
header line, so the account-type badge next to the name is still never
duplicated below it.

- **Files changed:** `auth.py` (`get_messages`, `get_conversations`),
  `messages.render.js` (`profession`, `professionLineHtml`,
  `renderConvList`, `openConversation`), `messages.html` (version bump).
- **Version bump:** `v=v18` → `v=v19`.

---

### Availability Status Contract

**What it is:** A small colored dot at the bottom-right of the profile avatar in Profile V2 indicating the user's current employment status. It is a **visual shortcut** to the same `حالة التوظيف` field already managed by the profile edit modal — not a separate feature.

#### Single Source of Truth

**`profiles.avail`** is the **only** field for employment/availability status. The avatar dot, the profile edit modal, and the public profile view all read from and write to this single column. There must never be two independent fields controlling the same concept.

> **RULE: The availability dot is a visual representation of Employment Status (`avail`), not a separate state.**

| Surface | Reads from | Writes to |
|---------|-----------|-----------|
| Avatar dot (Profile V2) | `profiles.avail` | `profiles.avail` |
| Profile edit modal (`#epAvail`) | `profiles.avail` | `profiles.avail` |
| Public profile visitor view | `profiles.avail` | — (read-only) |

#### DB Column

| Table | Column | Type |
|-------|--------|------|
| `profiles` | `avail` | `TEXT NULL` |

> `availability_status` was added in an earlier migration and is **deprecated and hardened-out**. The DB column is kept (idempotent `ADD COLUMN IF NOT EXISTS` migration) but the backend no longer reads, writes, or returns it — it is not in any SELECT, not in `ProfileUpdateInput`, not in `update_profile` allowed/clearable. The column can be dropped in a future `DROP COLUMN` migration.

#### Status Values (unified)

| Value | Color | Arabic label | DB column |
|-------|-------|-------------|-----------|
| `available` | `#22c55e` (green) | متاح للعمل | `avail` |
| `open_to_offers` | `#22d3ee` (teal) | منفتح على فرص | `avail` |
| `busy` | `#f59e0b` (orange) | مشغول حالياً | `avail` |
| `not_available` | `#94a3b8` (grey) | غير متاح حالياً | `avail` |
| NULL / empty | — | dot hidden for visitors; ghost ring for owner | `avail` |

**Legacy compat**: old values (`open`, `employed`, `freelance`, `closed`) still in the DB from before unification are handled by `_STATUS_MAP` aliases in `profile-v2.render.js` so existing users' dots show correctly. New saves always write the semantic values above.

#### DOM Structure

Inside `.sc-avatar-wrap` (`#scAvatarWrap`):
```html
<div class="sc-avail-dot" id="scAvailDot" style="display:none" title="" role="button" tabindex="0"></div>
<div class="sc-avail-picker owner-only" id="scAvailPicker" style="display:none" role="menu">
  <!-- four .sc-avail-opt buttons, one .sc-avail-opt-clear -->
</div>
```

The `.sc-avail-picker` carries `owner-only` class — CSS hides it in `body.preview-public-user` and `body.preview-guest` as part of the Global Header Preview Mode Contract.

#### JS API

| Function | Location | Signature | Purpose |
|----------|----------|-----------|---------|
| `window._renderAvailDot(status, isOwner)` | `profile-v2.render.js` (availability IIFE) | `(string\|null, bool)` | Sets dot color, title, cursor; empty-owner state if null+owner |

`renderProfile` calls `window._renderAvailDot(p.avail \|\| null, _vt === 'owner')`.

`profile-v2.edit.js` calls `window._renderAvailDot(payload.avail \|\| null, true)` immediately after a successful save so the dot updates in real time without a page refresh.

The availability IIFE registers three `document.addEventListener` handlers:
- `click` (dot target) — toggle picker for owner only (respects preview mode via `_isOwnerActive()`)
- `keydown` (Enter/Space on dot, Escape) — keyboard access
- `click` (`.sc-avail-opt` target) — saves to `avail`, updates `_scProfile.avail`, optimistic dot update

#### Owner vs Visitor

| Context | `avail = null` | `avail` set | Picker |
|---------|---------------|------------|--------|
| Owner — normal | Ghost ring `.is-empty-owner`, clickable | Colored dot, clickable | Opens on click |
| Owner — preview mode | Dot hidden (visitor-like) | Colored dot, read-only | Never opens |
| Public visitor | Dot hidden | Colored dot, read-only | Never opens |
| Guest (unauthenticated) | Dot hidden | Colored dot, read-only | Never opens |

`effectiveOwner = isOwner && !inPreviewMode`. Checked inside `_renderAvailDot` via body classes.

#### Empty Owner State (`.is-empty-owner`)

When `effectiveOwner = true` and `avail = null`, the dot:
- Is visible with a subtle dashed-ring outline (no fill color)
- Shows tooltip `"تحديد حالة التوفر"`
- Has `cursor:pointer` and `tabindex=0`
- Removed immediately when a real status is applied or cleared

Visitors never see this class.

#### Forbidden Patterns

- Do NOT create a second field to store employment/availability status — `avail` is the only source
- Do NOT let the dot and the edit modal diverge in the status value they show
- Do NOT use `availability_status` for new logic — it is deprecated
- Do NOT hide the dot for owners when `avail = null` — show `.is-empty-owner` instead
- Do NOT show the picker in preview mode or to visitors
- Do NOT invent dot colors outside the four defined values

#### Public Profile URL

The profile share link uses `/u/{tw_id}` (Profile V2 public URL), not the legacy `/profile?id=` route. This applies to:
- The link row displayed on the card (`#scLinkText`)
- The clipboard copy button (`#scLinkCopy`)
- QR code URL (always used `/u/` — unchanged)

#### Files Changed (final state)

| File | Change |
|------|--------|
| `auth.py` | `avail` in all SELECTs; `availability_status` removed from all SELECTs, `allowed`, and `_clearable`; DB migration kept (column not dropped yet) |
| `server.py` | `availability_status` removed from `ProfileUpdateInput`; `avail: Optional[str] = None` remains |
| `profile-showcase.html` | `#epAvail` options use semantic values; `#scAvailDot`+`#scAvailPicker` in avatar wrap; version bumps |
| `profile-v2.css` | `.sc-avail-dot` (18px, 44px tap target), `.sc-avail-dot.is-empty-owner`, `.sc-avail-picker`, `.sc-avail-opt` styles |
| `profile-v2.render.js` | Reads `p.avail`; `_STATUS_MAP` includes legacy compat; saves to `avail`; profile URL uses `/u/{tw_id}`; `_renderAvailDot` with `effectiveOwner` + preview guard |
| `profile-v2.edit.js` | After saving `avail`, calls `_renderAvailDot` to sync dot immediately |

---

## Profile Completion Strip

### Purpose

Owner-only compact strip placed **inside `.sc-main-card`, between `.sc-actions` and `.sc-stats`**. Operates in two modes depending on completion percentage:

- **Completion mode** (score < 100%): one-line progress bar + "تفاصيل" button that expands a checklist of missing items.
- **Growth mode** (score = 100%): one-line strip showing one rule-based improvement suggestion at a time, with "التالي" / "تفاصيل" / "إخفاء" buttons.

Visitors and preview modes never see this strip.

### Design: Compact Strip

- Height: ~44px in collapsed state; expands panel when "تفاصيل" is clicked
- **Completion mode components**: title label | progress bar | percentage | toggle button
- **Completion mode panel**: missing items (clickable) + done items + optional domain-tag suggestions
- **Growth mode components (RTL visual order)**: "اقتراح" badge | suggestion text (clickable → short actionable toast) | تفاصيل button | ↻ cycle button | ✕ إخفاء button
- **Button style**: solid fills, no glassmorphism. تفاصيل = teal; ↻ = neutral gray; ✕ = red. Each styled by ID (`#scGrowthDet`, `#scGrowthNext`, `#scGrowthHide`).
- **Suggestion-text toast** (`#scGrowthToast`): 1-sentence actionable tip ("ابحث عن دورة X، وبعد الحصول عليها أضفها لقسم الدورات"). Auto-dismisses after 4 s. Cleared on ↻ click. Does NOT contain the full explanation — that is reserved for the details panel.
- **Growth mode panel** (`#scGrowthPanel`): shown only via "تفاصيل" button. Contains the full explanation: `reason` (why it matters) + `benefit` (career impact) + "اذهب إلى القسم" action button. This is the only place the full explanation appears.
- **Growth empty state**: text "ملفك قوي! سنقترح لك فرص تطوير لاحقاً", التالي/تفاصيل buttons hidden
- Dismiss: IIFE-level `_dismissed` flag (resets on page reload, no persistence)
- `_growthIdx`: IIFE-level index for cycling through growth suggestions (clamp: `% suggs.length`)
- `_toastTimer`: IIFE-level setTimeout handle; cleared when a new toast is shown or التالي is clicked

### Data Source

Reads exclusively from `window._scProfile` (the global flat profile state set by `renderProfile`). No localStorage, no DB calls, no separate API request.

### Files

| File | Role |
|------|------|
| `profile-v2.completion.js` | IIFE: scoring, rendering, toggle, dismiss, rule-based suggestions |
| `profile-v2.css` | `.sc-compl-strip` and all child element styles |
| `profile-showcase.html` | `#scComplCard` strip markup inside `.sc-main-card`, between `.sc-actions` and `.sc-stats` |
| `profile-v2.render.js` | Shows strip + calls `_renderCompletion()` at end of `renderProfile` (owner only) |
| All section JS files | Call `_updateCompletion()` after every add/edit/delete save |

### Scored Items

| id | Label | Weight |
|----|-------|--------|
| `avatar` | صورة شخصية | 10 |
| `name` | الاسم الكامل | 8 |
| `profession` | التخصص المهني | 8 |
| `avail` | حالة التوظيف | 5 |
| `short_bio` | نبذة قصيرة | 7 |
| `bio` | نبذة عني | 8 |
| `location` | المدينة / الدولة | 6 |
| `skills` | المهارات | 9 |
| `exp` | الخبرات | 10 |
| `edu` | التعليم | 8 |
| `courses` | الدورات | 5 |
| `langs` | اللغات | 5 |
| `links` | روابط التواصل | 5 |
| `tw_id` | رابط مشاركة عام | 6 |
| **Total** | | **100** |

### Visibility Contract

1. `#scComplCard` starts as `style="display:none"` in HTML.
2. `renderProfile` in `profile-v2.render.js` shows the card and calls `window._renderCompletion()` **only** when `_vt === 'owner'`.
3. The card also carries the `owner-only` CSS class, which forces `display:none` in `body.preview-public-user` and `body.preview-guest` via the shared owner-only rule in `profile-v2.css`.
4. Visitors (`body.public-view`, `body.view-guest`) never reach the owner branch, so the card remains `display:none`.

### Global Functions

| Function | Exposed on | Description |
|----------|-----------|-------------|
| `window._renderCompletion()` | `profile-v2.completion.js` | Full re-render of card content from `_scProfile` |
| `window._updateCompletion()` | alias of `_renderCompletion` | Called by section saves to refresh card immediately |

### Action Mapping

| action value | What it does |
|---|---|
| `avatar` | `click()` on `#avCamBtn` |
| `edit-modal` | `click()` on `#scEditProfileBtn` |
| `avail-dot` | `click()` on `#scAvailDot` |
| `tab-skills` | `window._aboutGoTab('skills')` + smooth scroll |
| `tab-exp` | `window._aboutGoTab('exp')` + smooth scroll |
| `tab-edu` | `window._aboutGoTab('edu')` + smooth scroll |
| `tab-courses` | `window._aboutGoTab('courses')` + smooth scroll |
| `tab-langs` | `window._aboutGoTab('langs')` + smooth scroll |
| `tab-links` | `window._aboutGoTab('links')` + smooth scroll |
| `none` | No action (e.g. `tw_id` — set server-side) |

### Completion Mode Suggestions (rule-based topic tags)

`_buildCompletionSuggestions()` matches keywords from `p.title`, `p.profession`, `p.bio`, and `p.skills[]` against a fixed map of 8 domain categories. Returns up to 3 matching topic labels shown as compact tag chips inside the details panel.

### Growth Mode Suggestions (`_buildGrowthSuggestions()`)

Called only when score = 100%. Builds a filtered list of improvement rules from `window._scProfile`. Each rule:

```js
{ id, cond, text, toast, reason, benefit, action }
// text   — short ethical framing: "learn/earn first, then document"
// toast  — 2-3 sentence explanation shown on suggestion-text click (auto-dismiss 4 s)
// reason — why the item is missing or relevant
// benefit — how it strengthens the profile
```

**Ethical framing rule:** All `text` values must frame the suggestion as "do the thing first, then add it to your profile." Never suggest adding a skill or course the user hasn't actually completed. Examples: "تعلّم Git ثم وثّقه ضمن مهاراتك", "احصل على دورة SQL ثم أضفها لملفك".

Rules include: React.js course, Git, Node.js, SQL course, GitHub link, English language, second experience, Python, Laravel course, first course. Each `cond` checks that the suggested item doesn't already exist in the profile — so completing and adding the item removes it from the list automatically on next `_render()` call.

- `_growthIdx` persists across renders within the session; clamped to `% suggs.length` to handle list shrinkage
- `_toastTimer` holds the active setTimeout; cleared on new toast or التالي click
- Returns empty array if all conditions are satisfied → shows empty-state message
- No API call, no randomness — deterministic from `_scProfile`

### HTML Structure (Dual Mode)

```html
<div class="sc-compl-strip owner-only" id="scComplCard" style="display:none">
  <!-- Completion mode row -->
  <div class="sc-compl-row" id="scComplRow"> ... </div>
  <!-- Completion mode panel -->
  <div class="sc-compl-panel" id="scComplPanel" style="display:none"> ... </div>
  <!-- Growth mode row -->
  <div class="sc-growth-row" id="scGrowthRow" style="display:none"> ... </div>
  <!-- Growth mode panel -->
  <div class="sc-growth-panel" id="scGrowthPanel" style="display:none"> ... </div>
  <!-- Toast (auto-dismiss, shown on suggestion text click) -->
  <div class="sc-growth-toast" id="scGrowthToast" style="display:none"></div>
</div>
```

### Forbidden Patterns

- Do NOT read from localStorage for completion state — use `window._scProfile` only
- Do NOT persist dismiss state across sessions — use IIFE-level `_dismissed` variable only
- Do NOT show the strip to visitors or in preview mode
- Do NOT call any API endpoint from `completion.js`
- Do NOT add a new item without ensuring its weight keeps the total at 100
- Do NOT call `_renderCompletion` in non-owner contexts
- Do NOT move the strip outside `.sc-main-card` — it must sit between `.sc-actions` and `.sc-stats`
- Do NOT show growth mode when score < 100% — growth mode only activates at exactly 100%
- Do NOT persist `_growthIdx` to localStorage — it resets with the page
- Do NOT write suggestion `text` that implies adding something without having earned/completed it — all text must follow the "learn/earn first, then document" pattern
- Do NOT put the full explanation in the toast — toast is 1 short actionable sentence; full explanation belongs in the "تفاصيل" panel only
- Do NOT style growth buttons as glassmorphic — each button has a solid colored background via its ID selector
- Do NOT open any new route or add a course automatically from the suggestion — the user must find and complete the course themselves first

---

## Auth Gateway (index.html / `/login`) — P1 Refactor

### File Structure (auth-gw-v1)

| File | Responsibility |
|------|---------------|
| `index.html` | HTML structure only — logo, role selector, forms, skip link |
| `index.css` | Auth page styles only — do NOT import from other pages |
| `index.auth.js` | `redirect()`, `doLogin()`, `doRegister()`, on-load session check, Enter key handler |
| `index.ui.js` | `selectType()`, `showRegister()`, `showLogin()`, `toast()`, `checkPassStrength()`, ITQAN utilities, hash auto-route |

**Loading order in `index.html`:** `tw_shared.js` → `index.auth.js` → `index.ui.js`

Auth module loads first so the on-load redirect check fires before any UI initialises. Both modules are loaded before any user interaction can trigger `doLogin()` or `doRegister()`.

### Role

`index.html` is the **Auth Gateway only** — login form + registration form.
It is NOT a Landing Page and must not be redesigned as one.

- `GET /` → `landing.html` — public marketing page, no auth needed
- `GET /login` (or `/index.html`) → `index.html` — auth gateway

### Role Selector (register-only)

Three explicit cards replace the old 2-button + dropdown:

| Card | user_type sent to API | Hash route |
|------|-----------------------|------------|
| 👤 موظف / باحث عن عمل | `emp` | `/login#register-emp` |
| 🏢 شركة / صاحب عمل | `co` | `/login#register-co` |
| 🎓 مؤسسة تعليمية | `edu` | `/login#register-edu` |

- Role selector is **hidden on login view**, shown only when register form is open.
- Login form derives role from the API response — it never asks the user to pick one.

### Post-Login Redirect Rules (mandatory)

`redirect(u)` in `index.auth.js` is the **single authority** for post-login routing.

| user_type | Redirect target | Notes |
|-----------|----------------|-------|
| `emp` | `/u/{tw_id}` | Canonical public profile URL; fallback `/profile-showcase` if tw_id missing |
| `co` | `/company-profile` | Modern route (no `?id=` query param) |
| `edu` | `/edu-profile` | Modern route (no `?id=` query param) |
| `admin` | `/admin` | Defensive branch only — admin auth uses `/tw-ctrl-login` |

### localStorage Rules

- `localStorage.tw_user` — short-lived session cache; populated by `/auth/login` and `/auth/register` responses
- `localStorage.tw_jwt` — JWT bearer token; 7-day expiry
- **Neither is the authority for roles** — the user object from the API response is the source of truth
- TODO (P1 next): call `POST /auth/verify-token` on page load before trusting the cached session

### Forbidden Patterns

- Do NOT put auth logic in `index.ui.js` — keep `redirect()`, `doLogin()`, `doRegister()` in `index.auth.js` only
- Do NOT put DOM/appearance effects in `index.auth.js` — keep UI in `index.ui.js`
- Do NOT redirect to `profile.html?id=` — this is a legacy URL; use `/u/{tw_id}` for employees
- Do NOT redirect to `company-profile.html?id=` or `edu-profile.html?id=` — use `/company-profile` and `/edu-profile`
- Do NOT redirect to `/messages` or `/notifications` as the post-login landing page
- Do NOT add more than ONE on-load redirect check — exactly one IIFE in `index.auth.js`
- Do NOT use `localStorage.tw_user.user_type` to gate features or permissions — only for display/routing hints; validate with API when security matters
- Do NOT add a role selector inside the login form — role is login-derived from the API only

---

## Company Profile Edit Form (PR #248)

### Location Field Mapping

| Form Field | DB Column | Table | Notes |
|------------|-----------|-------|-------|
| `e-country` (select) | `profiles.country` | `profiles` | Arabic country name, e.g. "الأردن" |
| `e-city-sel` (select) | `profiles.city` | `profiles` | Arabic city name, populated dynamically from `_CO_CITIES` |
| `e-district` (text) | `profiles.location` | `profiles` | Street / district free text; legacy `location` field repurposed |

**Rule:** `profiles.location` is now the street/area free-text field for company profiles. It is NOT the country. `profiles.country` and `profiles.city` are the canonical location fields.

**Display order in render.js:** `country + '، ' + city`. If both are empty, fall back to `p.location`. Never combine all three in the visible string.

### `_CO_COUNTRIES` / `_CO_CITIES`

Defined in `static/company/company.main.js`. Keys in `_CO_CITIES` are Arabic country names (not ISO codes) matching the values saved in `profiles.country`. Do NOT change to ISO codes — the DB stores Arabic names.

### Branches Section (PR feat/company-branches)

`company_branches` table exists. Full DB persistence enabled:

**DB Table:**
```sql
company_branches (
    id            BIGSERIAL PRIMARY KEY,
    company_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    branch_name   TEXT,           -- optional
    country       TEXT NOT NULL,  -- required
    city          TEXT,           -- optional
    district      TEXT,           -- optional, free-text
    display_order INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
)
INDEX idx_company_branches_company ON company_branches(company_id)
```

**API Endpoints:**
- `GET /company/branches/{company_id}` — public, no JWT required
- `PUT /company/branches/{company_id}` — owner only, JWT Bearer, max 10 branches

**Save pattern (snapshot replace):**
`saveEdit()` sends `Promise.all([p1_profile, p2_company_profiles, p3_branches])`.
`save_company_branches()` runs `BEGIN → DELETE → INSERT → COMMIT` atomically.
Empty `country` rows are silently skipped.

**Edit modal:** opens → fetches `GET /company/branches/{id}` → populates rows via `_addBranchRow(data)`.
`_addBranchRow(data)` accepts `{branch_name, country, city, district}` for pre-fill.
DOM query classes: `.b-name`, `.b-country`, `.b-city`, `.b-district`.

**Public display:**
`loadBranches()` in `company.api.js` → `companyState.branches` → `renderBranches()` in `company.render.js`.
1–3 branches: shown as chips separated by `|` below `#coHqRow`.
4+ branches: first 3 chips + `+ N فروع أخرى` label.
0 branches: `#coBranchesRow` hidden.

**Constraints (permanent):**
- ❌ ممنوع localStorage للفروع
- ❌ ممنوع X-User-Id في أي call للفروع
- ❌ ممنوع عرض فروع غير محفوظة للعامة
- ✅ Max 10 branches enforced server-side (HTTP 400 if exceeded)
- ✅ Ownership check: `tok_uid == company_id AND tok_utype == "co"`

### Removed Form Fields (permanent)

The following fields are removed from the edit form. Their DB columns are untouched:

| Field | DB Column | Table |
|-------|-----------|-------|
| `e-web` (website) | `profiles.website` | `profiles` |
| `e-email` (contact email) | `company_profiles.contact_email` | `company_profiles` |
| `e-hq` (headquarters) | `company_profiles.headquarters` | `company_profiles` |

Displaying these in the About tab or other surfaces remains valid.

### District / Area Field

No official data source exists for Arabic city neighborhoods/districts. `e-district` is a free-text `<input>` (not a dropdown). This is intentional — do NOT invent a dropdown with made-up district names. If an official neighborhood API/dataset becomes available, convert to `<select>` at that time.

### `ep-select` in Company Profile — Shared Custom Dropdown (PR #253+)

Company profile loads `static/shared/tw-select.js` and `static/shared/tw-select.css`. All `<select class="ep-select">` elements are wrapped by the shared custom dropdown component — identical behavior and visual to Profile V2. Native `<select>` is hidden by the JS; the styled trigger button takes over.

The old CSS-only fallback (appearance:none + SVG chevron in company.css) is kept as a no-JS degradation path only. Do NOT rely on it as the primary visual experience.

### `PUT /company/profile/{company_id}` Endpoint

- Auth: `Depends(verify_token)` — JWT only, ownership checked server-side
- Validates: `industry` required
- Updates: `company_profiles` table only (not `profiles`)
- Forbidden: `X-User-Id` header, localStorage-based auth, breaking existing endpoints

---

# E — SHARED FORM CONTROLS SYSTEM

> قسم إلزامي — أي dropdown أو select جديد يلتزم بهذه القواعد.
> تاريخ الإضافة: 2026-06-24

---

## [P1] 36. Shared Form Controls Architecture

### المبدأ

أي حقل إدخال متكرر في الموقع — dropdown / select / year picker — يجب أن يكون:
1. **مكوّن مرئي مشترك** من `static/shared/tw-select.js` + `static/shared/tw-select.css`
2. **بيانات مشتركة** من `static/shared/tw-options-data.js`

لا تكرار للكود ولا للبيانات داخل ملفات الصفحات.

---

### ملفات الـ Shared System

| الملف | الوظيفة |
|-------|---------|
| `static/shared/tw-select.js` | Custom dropdown — يستهدف `.ep-select`؛ يدعم `data-icon` (Lucide) و `data-img` (صورة/علم) |
| `static/shared/tw-select.css` | أنماط `.sc-sel-*` + `.tw-flag` (علم دائري) |
| `static/shared/tw-options-data.js` | Single source of truth: `TW.COUNTRY_MAP`, helpers, بيانات الدول والمدن |
| `static/shared/flags/*.svg` | 18 علم دائري (HatScripts/circle-flags — MIT) — الأردن، السعودية، الإمارات... |

---

### API العام

```javascript
// tw-options-data.js — window.TW namespace

// بيانات الدول والمدن
TW.COUNTRY_MAP            // [{code, name_ar, flagPath}] — single source of truth
TW.COUNTRIES              // string[] — أسماء عربية (مشتق من COUNTRY_MAP للتوافق العكسي)
TW.CITIES                 // {[name_ar: string]: string[]} — مفاتيح بالاسم العربي
TW.COMPANY_TYPES          // string[]
TW.COMPANY_SIZES          // string[]

// helpers للدول
TW.countryEntry(value)              // قبول ISO أو اسم عربي → {code, name_ar, flagPath} | null
TW.countryName(value)               // → اسم عربي | value
TW.countryCode(value)               // → ISO code | null
TW.countryFlagEl(value, extraClass) // → <img class="tw-flag"> | null
TW.sameCountry(a, b)                // TW.sameCountry('JO','الأردن') → true (مقارنة مختلطة)

// DOM helpers
TW.fillSelect(sel, items, placeholder)
TW.fillCountries(sel, placeholder, opts)
  // opts = { valueMode: 'name_ar'|'code', withFlags: boolean, force: boolean }
  // بدون opts → valueMode:'name_ar', withFlags:false (توافق عكسي مع الشركات)
TW.fillCities(sel, country, selectedCity)   // يقبل ISO أو اسم عربي
TW.fillFoundedYears(sel)                    // current year → 1900، idempotent

// tw-select.js
scSelectInit()   // يطبق custom dropdown على .ep-select:not([data-sc-sel])
scSelectClose()  // يغلق الـ dropdown المفتوح
```

---

### عرض الأعلام (data-img)

`tw-select.js` يدعم `data-img` على `<option>` لعرض صور (أعلام دائرية) في الـ trigger والـ dropdown.

```js
// TW.fillCountries مع withFlags:true تضع data-img تلقائياً
TW.fillCountries(selEl, '— اختر —', { valueMode: 'name_ar', withFlags: true });
// ← كل <option> يحصل على data-img="/static/shared/flags/jo.svg" ...

// tw-select.js يعرض <img class="tw-flag"> بدل نص emoji
// CSS: .tw-flag { width:18px; height:18px; border-radius:50%; object-fit:cover; }
```

قواعد الاستخدام:
- `data-img` و `data-icon` لا يُجمعان — `data-icon` (Lucide) له الأولوية
- `data-img` يُمنع أن يكون user input — يجب أن يكون من TW.COUNTRY_MAP.flagPath فقط

---

### قواعد بيانات الدول والمدن

```
✅ مصدر واحد: TW.COUNTRY_MAP في tw-options-data.js
✅ CITIES مفاتيحها أسماء عربية (نفس قيمة country في DB الشركات)
✅ TW.sameCountry() تعالج المقارنة المختلطة: 'JO' == 'الأردن' → true
✅ TW.fillCities() تقبل ISO code أو اسم عربي
❌ ممنوع تكرار قائمة الدول أو المدن داخل ملفات الصفحات
❌ ممنوع hard-code أعلام داخل صفحة — يجب أن يأتي flagPath من TW.COUNTRY_MAP
```

**استثناء موثّق — Profile V2 country field:**
`profiles.country` للموظفين يحمل ISO codes (JO, SA, ...) — عقد DB قائم لا يتغير بدون migration.
`TW.fillCountries(el, ph, { valueMode:'code', withFlags:true })` تُولّد options بـ ISO values + أعلام.
`TW.countryEntry(isoCode)` تبني الجسر للوصول لـ TW.CITIES عبر name_ar.

---

### قواعد الصفحات

**صفحة تريد custom dropdown:**
1. تحمّل `tw-select.css` في `<head>` (قبل CSS الصفحة)
2. تحمّل `tw-options-data.js` قبل scripts الصفحة
3. تحمّل `tw-select.js` قبل scripts الصفحة
4. تُضيف class `ep-select` لأي `<select>` تريده مخصصاً
5. تستدعي `scSelectInit()` بعد كل عملية تُضيف `ep-select` جديدة ديناميكياً

**لا تفعل:**
```
❌ native <select> بدون tw-select.js إذا الصفحة تتطلب تجربة موحدة
❌ نسخ TW.COUNTRIES داخل ملف الصفحة
❌ إضافة .sc-sel-* CSS داخل ملف CSS الصفحة
❌ تعديل tw-select.css لصفحة واحدة فقط — التعديلات تنعكس على الكل
```

---

### Profile V2 هو المرجع البصري

`tw-select.css` مستخرج من `profile-v2.css` — نفس الشكل، نفس الألوان، نفس الحركة.
لا يجوز تغيير شكل الـ dropdown من داخل CSS الصفحة — فقط من `tw-select.css`.

---

### حالة الفروع (company_branches)

```
✅ company_branches table موجود — حفظ حقيقي في DB
✅ كل فرع = 4 حقول: branch_name (input) + country (TW.fillCountries) + city (TW.fillCities) + district (input)
✅ حفظ atomic: BEGIN → DELETE → INSERT → COMMIT في save_company_branches()
✅ GET /company/branches/{id} عام | PUT /company/branches/{id} مالك فقط (JWT)
❌ ممنوع حفظ الفروع في localStorage
❌ ممنوع X-User-Id في أي call للفروع
❌ ممنوع عرض فروع غير محفوظة في البروفايل العام
```

---

### تسلسل التحميل للصفحات التي تستخدم النظام

```
lucide (vendor)
  ↓
tw-options-data.js    ← TW namespace + helpers
  ↓
tw-select.js          ← scSelectInit + scSelectClose
  ↓
[page scripts]        ← يستخدمون TW.* و scSelectInit()
```

---

# F — SHARED SYSTEM FIRST PATTERN

> **P1 — إلزامي على كل التعديلات.**
> قبل أي تنفيذ: تحقق من وجود نظام مشترك. استخدمه إن وُجد. وثّقه إن أضفته.

---

## [P1] 37. Shared System First — Architecture Pattern Check

### المبدأ

```
قبل كتابة أي كود جديد:
1. هل يوجد helper / component / CSS class / data source موجود يخدم هذه الحاجة؟
2. هل هذا الشيء موثق في CLAUDE.md أو ARCHITECTURE.md؟
3. هل التعديل يمكن ربطه بـ shared system بدل حل خاص بصفحة واحدة؟
4. إذا الكود سيظهر في صفحتين أو أكثر → انقله إلى shared module أولاً.
5. إذا أضفت نظام مشترك جديد → وثّقه في نفس الـ PR.
```

### مصادر الـ Shared Systems الحالية

| النظام | الملف | يُغطي |
|--------|-------|--------|
| Country / city data | `static/shared/tw-options-data.js` | `TW.COUNTRY_MAP`, `TW.CITIES`, `TW.COMPANY_TYPES`, `TW.COMPANY_SIZES` |
| Flag images | `static/shared/flags/*.svg` + `TW.countryFlagEl()` | أعلام دائرية — MIT |
| Custom dropdown UI | `static/shared/tw-select.js` + `tw-select.css` | `.ep-select` + `scSelectInit()` |
| App header | `static/app-header.css` | `.sc-header`, `.sc-hicon`, CSS vars مشتركة |
| Immediate UI Update | Profile V2 `applyLocalUpdate()` pattern | محدّث state + DOM بعد تأكيد API — موثق في Rule #36 |

### Mandatory "Shared System Check" في كل خطة/تقرير

كل خطة تنفيذ أو تقرير فحص يجب أن يحتوي جدول:

| السؤال | الجواب |
|--------|--------|
| هل تم فحص النظام الموجود؟ | نعم / لا |
| هل استخدمنا shared system موجود؟ | نعم / لا + الاسم |
| هل أضفنا shared pattern جديد؟ | نعم / لا + الملف |
| هل قللنا التكرار أم زدناه؟ | قللنا / زدنا |
| هل يحتاج توثيق؟ | نعم / لا + السبب |

### ممنوعات ثابتة

```
❌ بيانات دول/مدن hardcoded داخل ملف صفحة
❌ formatter متكرر في موديولين منفصلين
❌ dropdown جديد بدون tw-select.js
❌ نمط حفظ جديد يخالف Rule #36
❌ حل مؤقت عندما يوجد نظام مشترك
❌ pattern جديد يُطبَّق بدون توثيق
```

### القاعدة الذهبية

> أي شيء ممكن يتكرر في صفحتين أو أكثر = shared module.
> لا حلول خاصة بصفحة واحدة لمشاكل مشتركة.

---

# G — CONFIRMED IMMEDIATE UPDATE PATTERN

> **P1 — نمط الحفظ الآمن لـ Company Profile (وأي نموذج مهم مستقبلاً).**

---

## [P1] 38. Confirmed Immediate Update Pattern

### المبدأ

```
انتظر تأكيد API أولاً → أغلق المودال → حدّث state + DOM محلياً → background sync صامت
```

### الفرق بينه وبين Optimistic UI

| | Optimistic UI | Confirmed Immediate Update |
|--|--|--|
| توقيت تحديث الـ DOM | قبل نجاح API | بعد نجاح API |
| إذا فشل API | rollback مرئي | لا rollback — المودال ظل مفتوحاً |
| خطر إيهام المستخدم | نعم — إذا فشل API يرى بيانات خاطئة لحظياً | لا — لا شيء يُحدَّث حتى يأتي التأكيد |
| مناسب لـ | عمليات بسيطة سريعة (like, follow) | نماذج مهمة (profile، company data) |

### التدفق الكامل

```
1. المستخدم يضغط "حفظ"
   ↓
2. validation + disable زر الحفظ + نص "جاري الحفظ…"
   ↓
3. Promise.all([PUT profile, PUT company, PUT branches])
   ↓
   ├── فشل أي PUT:
   │     re-enable زر الحفظ + نص "حفظ"
   │     toast خطأ
   │     المودال يبقى مفتوحاً (المستخدم يصحّح ويعيد)
   │
   └── نجاح كل PUTs:
         إغلاق المودال
         toast نجاح
         _applyCompanyLocalUpdate(profilePayload, companyPayload, branchesArr)
           ├── تحديث companyState.profile
           ├── تحديث companyState.company
           ├── تحديث companyState.branches
           ├── renderProfile()  ← جزئي فقط
           └── renderBranches() ← جزئي فقط
         loadData({ silent: true }) ← background sync، لا renderAll
```

### `_applyCompanyLocalUpdate(profilePayload, companyPayload, branchesArr)`

- موقعه: `static/company/company.main.js`
- مكشوف على `window._applyCompanyLocalUpdate` للاختبار والاستخدام الخارجي
- يحدّث فقط الحقول الواردة في الـ payloads (strict field-by-field)
- لا يستخدم `_mergeCompanyState()` — هذه مصممة لـ API response كامل
- يستدعي `renderProfile()` و `renderBranches()` فقط — لا `renderAll()`
- يعيد تشغيل `lucide.createIcons()` بعد الـ render

### `loadData({ silent: true })`

- موقعه: `static/company/company.api.js`
- يرسل fetch لـ `/company/profile/:id`
- يستدعي `_mergeCompanyState(data)` للمزامنة الكاملة
- لا يستدعي: `renderAll()`, `_applyViewMode()`, `bindEvents()`, `loadJobs()`, `loadBranches()`
- لا يستخدم AbortController (يعمل مستقلاً في الخلفية)
- لا يغيّر loading state (`_applyLoadingState`)
- الهدف: مزامنة `companyState` بالبيانات الحقيقية من DB بدون إزعاج المستخدم

### قواعد الاستخدام

```
✅ استخدم هذا النمط لأي نموذج تعديل مهم (بيانات قابلة للتحقق من DB)
✅ دائماً اعمل _applyCompanyLocalUpdate أولاً ثم loadData({silent}) ثانياً
✅ إذا فشل API → لا تغلق المودال → لا تحدث companyState
✅ renderProfile + renderBranches بدل renderAll للسرعة
❌ لا تستخدم Optimistic UI للبيانات الحساسة (اسم الشركة، التصنيف)
❌ لا تغلق المودال قبل نجاح API
❌ لا تخفي فشل الحفظ عن المستخدم
❌ loadData({silent}) لا يعوّض عن _applyCompanyLocalUpdate — الاثنان معاً
```

### الملفات المعنية

| الملف | الدور |
|-------|-------|
| `static/company/company.main.js` | `saveEdit()` + `_applyCompanyLocalUpdate()` |
| `static/company/company.api.js` | `loadData(opts)` — opts.silent |
| `static/company/company.render.js` | `renderProfile()` + `renderBranches()` (partial renders) |

---

## Unified Professional Taxonomy System (PR 1 — feat/taxonomy-db-foundation)

### Overview

نظام تصنيف مهني موحّد يربط الملفات الشخصية، نشر الوظائف، والمطابقة بمصدر بيانات واحد رسمي.

### DB Tables

#### `profession_categories` (موجود من قبل)

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | — |
| name_ar | TEXT | الاسم العربي |
| name_en | TEXT | الاسم الإنجليزي |
| slug | TEXT UNIQUE | معرّف النص |
| icon | TEXT | اسم أيقونة Lucide |
| category_group | TEXT | مجموعة التصنيف |
| sort_order | INTEGER | ترتيب العرض |
| is_active | BOOLEAN | يُعرض للمستخدمين |

يُحمَّل عبر: `GET /professions` (public, no auth)

#### `skill_catalog` (جديد — PR 1)

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | — |
| slug | TEXT UNIQUE NOT NULL | معرّف المهارة (مثال: `python`, `react`) |
| name_en | TEXT | الاسم الإنجليزي |
| name_ar | TEXT | الاسم العربي |
| keywords | TEXT[] | كلمات مفتاحية للبحث |
| icon | TEXT | اسم أيقونة Lucide |
| category_group | TEXT | (tech / security / design / management / marketing / finance / hr / education / engineering / health / trades / hospitality / logistics / customer_service / languages) |
| sort_order | INTEGER DEFAULT 0 | — |
| is_active | BOOLEAN DEFAULT TRUE | — |

Indexes: `idx_skill_catalog_slug`, `idx_skill_catalog_group`, `idx_skill_catalog_active`

Seed: 335 مهارة مُدمجة من `profile-v2.skills.js` CATALOG بدفعات 50 مع `ON CONFLICT (slug) DO NOTHING`

يُحمَّل عبر: `GET /skills/catalog` (public, no auth, in-memory cache 1hr)

#### `jobs.profession_id` (جديد — PR 1)

```sql
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS profession_id INTEGER
    REFERENCES profession_categories(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_profession ON jobs(profession_id);
```

- اختياري (NULL مسموح) — لن يصبح إلزامياً قبل اكتمال PR 3
- يُمرَّر من `JobInput.profession_id` (Optional[int] = None) → `add_job()` → DB

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/professions` | None | قائمة التخصصات المهنية (profession_categories) |
| GET | `/skills/catalog` | None | قائمة المهارات الرسمية (skill_catalog) مع cache 1hr |

### Frontend Fallback

`TW.SKILL_CATALOG` في `static/shared/tw-options-data.js`:
- **FALLBACK ONLY** — تُستخدم فقط عند فشل `GET /skills/catalog` أو قبل PR 2
- تحتوي نسخة مختصرة (~90 مهارة) من الـ 335 مهارة في DB
- لا تضف مهارات هنا — أضفها في `_SKILL_SEED` داخل `_migrate_taxonomy_foundation()` في `auth.py`

### Migration Function

`_migrate_taxonomy_foundation()` في `auth.py`:
- يُنفَّذ عند startup بعد `_migrate_jobs_v2()`
- كامل idempotent: `CREATE IF NOT EXISTS` + `ON CONFLICT DO NOTHING` + `IF NOT EXISTS` column
- بدفعات 50 لتجنب query string overflow

### ممنوعات

```
❌ قوائم مهارات hardcoded داخل ملف صفحة JS/HTML
❌ قوائم تخصصات مهنية hardcoded خارج profession_categories
❌ skills stored as plain text array only — يجب الربط بـ slug من skill_catalog عند PR 2
❌ TW.SKILL_CATALOG كمصدر رئيسي — الـ source الرسمي هو GET /skills/catalog
❌ jobs.profession_id إلزامي قبل اكتمال PR 3
```

### PR Roadmap

| PR | Branch | Focus |
|----|--------|-------|
| PR 1 ✅ | feat/taxonomy-db-foundation | DB + seed + API + fallback |
| PR 2 ✅ | feat/shared-skill-picker | tw-skills.js + Profile V2 يستخدم GET /skills/catalog |
| PR 3 ✅ | feat/job-modal-taxonomy-integration | Job Modal: profession picker + skill picker |
| PR 4 ✅ | feat/taxonomy-aware-matching | Matching algorithm: profession_id boost |
| PR 5 ✅ | cleanup/taxonomy-hardcoded-removal | حذف القوائم القديمة hardcoded |

---

## `static/shared/tw-skills.js` — Shared Skill Catalog Helpers (PR 2)

### Overview

يحمّل `tw-skills.js` قائمة المهارات من DB (`GET /skills/catalog`) ويوفر helpers مشتركة للبحث والتطبيع ولوأيقونات. يستخدمه أي module يحتاج الوصول لـ skill catalog.

### Load Order

```
tw-options-data.js → tw-select.js → tw-skills.js → profile-v2.skills.js
```

### Data Flow

```
startup: TW._catalog = TW.SKILL_CATALOG (static fallback ~90 skills, immediate)
async:   fetch('/skills/catalog') → TW._catalog = full DB list (335+ skills)
helpers: always read from TW._catalog (whichever is available at call time)
```

### Internal Catalog Format

```js
{ slug: string, en: string, ar: string, kw: string, icon: string }
```

All helpers normalize DB format (`name_en`, `name_ar`, `keywords`) and fallback format (`name_ar`, `group`) to this unified shape.

### API Reference

| Function | Returns | Description |
|----------|---------|-------------|
| `TW.loadSkillCatalog(cb)` | void | Call `cb(catalog)` when DB load completes (or now if already loaded) |
| `TW.searchSkills(q, maxResults)` | `{slug,en,ar,kw,icon}[]` | Search by en / ar / slug / keywords (max 8 by default) |
| `TW.normalizeSkill(raw)` | string | Returns canonical `en` name if found, else returns trimmed raw |
| `TW.getSkillIcon(name)` | string | Lucide icon name (falls back to `circle-check`) |
| `TW._getSkillEntry(name)` | entry \| null | Full catalog entry matched by `en` / `slug` / `ar` |
| `TW._isOfficialSkill(name)` | boolean | Whether name exists in catalog |
| `TW._catalog` | array | Live catalog array (starts with fallback, replaced by DB data) |
| `TW._catalogReady` | boolean | Whether DB fetch has completed (or failed) |

### Profile V2 Integration

`profile-v2.skills.js` now delegates all catalog access to `TW`:
- Removed: embedded 335-item `CATALOG` array
- Replaced: `_search()` → `TW.searchSkills(q, 8)`
- Replaced: `_normalize()` → `TW.normalizeSkill(raw)`
- Replaced: `_isOfficial()` → `TW._isOfficialSkill(name)`
- Replaced: `_getCatalogEntry()` → `TW._getSkillEntry(name)`
- `window._getSkillIcon()` now delegates to `TW.getSkillIcon()`

### Rules

```
✅ Use TW.searchSkills / TW.normalizeSkill / TW.getSkillIcon for ALL skill catalog access
✅ tw-skills.js must load AFTER tw-options-data.js (needs TW.SKILL_CATALOG for fallback)
✅ tw-skills.js must load BEFORE any page skill module (profile-v2.skills.js, future Job Modal)
❌ Never access TW._catalog directly from page modules — use the helper functions
❌ Never add a skill list to a page-specific JS file
❌ Never bypass tw-skills.js by calling fetch('/skills/catalog') directly from a page module
```

---

## Job Modal Taxonomy Integration (PR 3 — feat/job-modal-taxonomy-integration)

### Overview

Replaces the old free-text category dropdown (`j-cat` / `TW.JOB_CATEGORIES`) and comma-separated skills input (`j-skills`) in the Company Profile job-posting modal with:

1. **Profession picker** — `<select id="j-prof">` loaded from `GET /professions` with `<optgroup>` per `category_group`; value = integer `profession_id`
2. **Skill chip autocomplete** — chip-based input using `TW.searchSkills` + `TW.normalizeSkill` + `TW.getSkillIcon` from `tw-skills.js`

### Changed Files

| File | Change |
|------|--------|
| `company-profile.html` | Replaced `j-cat` select with `j-prof` select; replaced `j-skills` text input with `j-skill-box-wrap` chip container; added `tw-skills.js` script tag |
| `static/company/company.jobs.js` | Added `_loadProfessions()`, `_rebuildProfSelect()`, `_jSkills` state, chip system (`_jRenderChips`, `_jAddSkill`, `_jRemoveSkill`, `_jShowDrop`, `_jHideDrop`, `_jBindSkillAC`); updated `openPostJob()`, `publishJob()`, `_resetPostJobModal()` |
| `static/company/company.css` | Added `.j-skill-box-wrap`, `.j-skill-box`, `.j-skill-chip`, `.j-skill-chip-del`, `.j-skill-inp`, `.j-skill-drop`, `.j-skill-drop-item` |

### Script Load Order (Company Profile)

```
lucide → tw_shared.js → tw-options-data.js → tw-select.js → tw-skills.js → company.state.js → ...
```

`tw-skills.js` must come before `company.state.js` (and all other company modules) so `TW.searchSkills` etc. are available when `company.jobs.js` runs.

### Payload Changes

`POST /company/jobs` now sends:

```json
{
  "profession_id": 12,       // integer FK → profession_categories(id), or null
  "category": "تقنية المعلومات",  // legacy fallback: derived from optgroup label of selected profession
  "skills": ["Python", "FastAPI"]  // normalized array (via TW.normalizeSkill), replaces comma text
}
```

`profession_id` is optional (NULL allowed) — server already accepts it via `JobInput.profession_id: Optional[int] = None`.

### Skill Chip System Rules

```
✅ _jSkills is the single source of truth for skills in the job modal
✅ _jAddSkill() normalizes via TW.normalizeSkill before pushing
✅ _jBindSkillAC() is idempotent (checks _jACBound flag)
✅ _jHideDrop() is called on blur (180ms delay) and Escape
✅ Max 15 skills enforced client-side
✅ Chip delete uses mousedown to prevent blur race (dropdown case uses mousedown + preventDefault)
❌ Never read j-skills text input for skills (element removed)
❌ Never call fetch('/skills/catalog') directly — always use TW.searchSkills
❌ Never call fetch('/professions') more than once per session (_professions cache in module scope)
```

### Profession Picker Rules

```
✅ _loadProfessions() caches result in _professions module variable (fetches once per page load)
✅ _rebuildProfSelect() groups by category_group using <optgroup>
✅ scSelectInit() called after _rebuildProfSelect() to apply tw-select.js custom UI
✅ Legacy category field derived from optgroup label of selected option
❌ Never hardcode profession options in HTML or JS
❌ Never use j-cat (removed from modal) — it was TW.JOB_CATEGORIES; cleanup in PR 5
```

---

## Taxonomy-Aware Feed Matching (PR 4 — feat/taxonomy-aware-matching)

### Overview

تحسين `/home/feed` لترتيب الوظائف بناءً على تطابق تخصص وظيفة الموظف، ثم المجال العام، ثم المهارات المشتركة. الوظائف القديمة بدون `profession_id` لا تختفي.

### Changed Files

| File | Change |
|------|--------|
| `server.py` | `_FEED_JOB_POOL` constant، `_feed_user_context()`، `_taxonomy_score()`؛ تعديل `home_feed()` — job query يضيف LEFT JOIN profession_categories، يجلب pool أكبر (200)، يطبق scoring + sort |
| `static/home/home.cards.js` | إضافة profession chip (`hw-chip--prof`) في `renderOpportunityCard` إذا `profession_name_ar` موجود |
| `static/home-v2.css` | `.hw-chip--prof` style — أزرق فاتح لتمييز profession chips |

### Scoring Logic

```python
# _taxonomy_score(job, user_pid, user_pgroup, user_skills) → int

if job.profession_id == user.profession_id:
    score += 100          # exact profession match
elif job.profession_category_group == user.category_group:
    score += 40           # same group (elif — no double-count)
elif not job.profession_id and job.category:
    score += 10           # legacy job with text category

score += len(shared_skills) * 10   # +10 per matched skill (always additive)
```

Sorting: stable two-pass — recency DESC first, then score DESC (tiebreak = recency).

### Response Schema Changes (backward-compatible additions)

Each opportunity item now includes:

| Field | Type | Notes |
|-------|------|-------|
| `profession_id` | int \| null | FK → profession_categories |
| `profession_name_ar` | string \| null | Arabic name, null if no profession |
| `profession_name_en` | string \| null | English name |
| `profession_icon` | string \| null | Lucide icon slug |
| `profession_category_group` | string \| null | Category group |

`category` (legacy text) is stripped from the response — `profession_*` fields are the canonical form.

### Helper Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `_FEED_JOB_POOL` | `server.py` | Max jobs fetched for scoring (200) |
| `_feed_user_context(conn, user_id, user_type)` | `server.py` | Returns (profession_id, category_group, skills_set) — always safe, returns (None, None, set()) on error |
| `_taxonomy_score(job, user_pid, user_pgroup, user_skills)` | `server.py` | Returns integer score; 0 for non-emp users or missing context |

### Rules

```
✅ _feed_user_context() is always safe — try/except returns (None, None, set()) on any error
✅ _taxonomy_score() returns 0 for non-emp users (user_pid/user_pgroup/user_skills all None/empty)
✅ Legacy jobs (profession_id = NULL) still appear — they score via category +10 or skill overlap only
✅ Jobs without skills still appear — skill overlap is additive and skipped if user_skills is empty
✅ Non-emp users get same behavior as before (no context fetched, all jobs score 0, sorted by date)
✅ Pool of 200 jobs fetched → top opp_lim returned after scoring (best-match jobs win the slots)
❌ Never use ORDER BY RANDOM() in feed queries
❌ Never add DB migration in PR 4
❌ Never read user data from localStorage for matching — backend is authoritative
❌ Never assume every job has profession_id — always defensive null-checks
❌ Never assume every user has profession_id or skills — always defensive
```

---

## Taxonomy Cleanup (PR 5 — cleanup/taxonomy-hardcoded-removal)

### What Was Removed

| Item | File | Reason |
|------|------|--------|
| `TW.JOB_CATEGORIES` array | `static/shared/tw-options-data.js` | Replaced by `profession_categories` DB table + `GET /professions`; had zero consumers after PR 3 removed `j-cat` from the Job Modal |

### What Was Confirmed Clean (no action needed)

| Item | Status |
|------|--------|
| `j-cat` in HTML/JS | Zero references — removed in PR 3 |
| Internal CATALOG in `profile-v2.skills.js` | Zero — removed in PR 2 |
| `TW.SKILL_CATALOG` | Kept as fallback in `tw-options-data.js` — correct, do not remove |

---

## Unified Taxonomy System — Final Canonical Rules

These rules apply to ALL future AI sessions and development on this project.

### Professions (Specializations)

| Rule | Details |
|------|---------|
| **Single source of truth** | `profession_categories` DB table |
| **Official API** | `GET /professions` — only approved way to load professions on frontend |
| **Job field** | `jobs.profession_id` FK → `profession_categories(id)` |
| **Profile field** | `profiles.profession_id` FK → `profession_categories(id)` |
| **Legacy field** | `jobs.category` — DB column kept, used only as legacy fallback in scoring; never as primary UI source |

```
✅ Profession data always comes from GET /professions
✅ jobs.profession_id is the canonical job specialization field
✅ profiles.profession_id is the canonical user specialization field
❌ Never hardcode profession/category lists inside page JS or HTML
❌ Never add new entries to profession_categories from frontend — admin only
❌ Never use jobs.category as a primary UI data source for new features
❌ Never replace TW.JOB_CATEGORIES — it is deleted; use GET /professions
```

### Skills

| Rule | Details |
|------|---------|
| **Single source of truth** | `skill_catalog` DB table |
| **Official API** | `GET /skills/catalog` — public, no auth, 1-hour server cache |
| **Official frontend helper** | `static/shared/tw-skills.js` — `TW.searchSkills`, `TW.normalizeSkill`, `TW.getSkillIcon`, `TW._getSkillEntry`, `TW._isOfficialSkill` |
| **Static fallback** | `TW.SKILL_CATALOG` in `tw-options-data.js` — used only when API unavailable; never access directly from page modules |
| **Load order** | `tw-options-data.js` → `tw-skills.js` → page skill module |

```
✅ All skill search/normalize/icon operations go through tw-skills.js helpers
✅ TW.SKILL_CATALOG is fallback-only — tw-skills.js uses it automatically
✅ tw-skills.js must load after tw-options-data.js and before any page skill module
❌ Never hardcode a skill list inside a page JS file or HTML file
❌ Never call fetch('/skills/catalog') directly from a page module
❌ Never access TW._catalog directly from page modules
❌ Never add skills to skill_catalog outside auth.py _SKILL_SEED migration
❌ Never remove TW.SKILL_CATALOG — it is the offline fallback
```

### Taxonomy System — PR Completion Status

All 5 PRs complete. The Unified Professional Taxonomy System is fully operational.

| PR | Status | Deliverable |
|----|--------|-------------|
| PR 1 | ✅ merged | `skill_catalog` table + `GET /skills/catalog` + `jobs.profession_id` optional FK |
| PR 2 | ✅ merged | `tw-skills.js` shared helper; Profile V2 delegates to TW |
| PR 3 | ✅ merged | Job Modal: `j-prof` profession picker + skill chip autocomplete |
| PR 4 | ✅ merged | `/home/feed` taxonomy-aware scoring: +100 exact / +40 group / +10 per skill |
| PR 5 | ✅ merged | Removed `TW.JOB_CATEGORIES`; confirmed zero dead code; final rules documented |

---

## Job Accepted Professions (feat/job-accepted-professions + fix/job-post-modal-ux-polish)

### Overview

Many-to-many profession targeting for job postings. A company can either:
- Mark **up to 5 specific additional professions** beyond `jobs.profession_id` (targeting), OR
- Toggle **`accepts_all_professions = true`** to broadcast to all professions (+60 feed score tier).

Individual targets and `accepts_all_professions` are mutually exclusive: enabling the toggle clears `job_profession_targets`.

### DB Schema

```sql
CREATE TABLE job_profession_targets (
    id            SERIAL PRIMARY KEY,
    job_id        INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    profession_id INTEGER NOT NULL REFERENCES profession_categories(id) ON DELETE CASCADE,
    display_order SMALLINT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(job_id, profession_id)
);
CREATE INDEX idx_jpt_job_id ON job_profession_targets(job_id);
```

**`jobs` table additions** (migrated via `_migrate_jobs_v2`, idempotent):
```sql
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS accepts_all_professions BOOLEAN DEFAULT FALSE;
```

### Backend Source of Truth

| Location | Role |
|----------|------|
| `auth.py` → `_migrate_job_profession_targets()` | Creates table on startup (idempotent) |
| `auth.py` → `_fetch_accepted_professions_batch(conn, job_ids)` | Batch-fetches accepted professions for a list of job IDs; returns `{job_id: [{id, name_ar, name_en, icon}]}` |
| `auth.py` → `add_job()` | INSERT accepted_profession_ids after job INSERT; attaches `accepted_professions` to returned dict |
| `auth.py` → `get_jobs()` | Attaches `accepted_professions` to every job in result list (no N+1) |
| `auth.py` → `get_job()` | Attaches `accepted_professions` to single job dict |
| `auth.py` → `_validate_accepted_profession_ids(conn, primary_pid, accepted_ids)` | Server-side validation helper — raises `ValueError` on any rule violation |
| `server.py` → `_save_accepted_professions(conn, job_id, profession_ids, primary_pid=None)` | Calls validator first (no DELETE if validation fails), then snapshot-replace: DELETE + INSERT |
| `server.py` → `JobInput.accepted_profession_ids` | `Optional[List[int]] = None` |
| `server.py` → `PUT /company/jobs/{job_id}` | Pops field before SQL UPDATE; fetches current `profession_id` from DB when not in payload; calls `_save_accepted_professions`; catches `ValueError` → HTTP 422 |
| `server.py` → `POST /company/jobs` | `add_job()` raises `ValueError` on validation failure; endpoint catches → HTTP 422 |

### Scoring Update (`_taxonomy_score`)

```
+100  exact profession match (job.profession_id == user.profession_id)
+80   user's profession is in accepted_profession_ids (targeting)
+60   job.accepts_all_professions = true (open to all professions)
+40   same category_group, different profession
+10   legacy job with category text (no profession_id)
+10   per shared skill
```

Batch-fetch is done in `home_feed` before the scoring loop — single query, no N+1.

### Frontend

| File | Change |
|------|--------|
| `company-profile.html` | Bottom-sheet modal (edit-overlay + co-edit-sheet); accepts_all checkbox; salary show toggle (default OFF); field reorder; simplified labels |
| `static/company/company.jobs.js` | `_jAccProfs[]`, chip management, autocomplete (type-only, no focus trigger); `_onAccAllChange()` hides/clears individual picker; `_onSalShowChange()` replaces old hide toggle; `publishJob()` sends `accepts_all_professions` + `accepted_profession_ids`; defaults: دوام كامل + في الموقع; `TW.EXP_LEVELS` integer options for experience |
| `job-detail.html` | `#jdAccProfSection` + `#jdAccProfChips` hidden section |
| `static/job/job-detail.js` | Experience integer → label via `TW.EXP_LEVELS`; renders "مفتوح لجميع التخصصات" when `accepts_all_professions=true` |
| `static/home/home.cards.js` | Shows count badge "+N تخصص" when `accepted_professions.length > 0` |
| `static/shared/tw-options-data.js` | `TW.EXP_LEVELS` — array of `{value:int, label:string}` for experience levels |
| `static/company/company.css` | `.j-toggle-label` style; `.co-edit-sheet .j-skill-drop { z-index:1000 }` for mobile dropdown fix |

### Experience Levels (`TW.EXP_LEVELS`)

Stored as integers in `jobs.experience_years`. Mapping:
| DB value | Label |
|----------|-------|
| 0 | بدون خبرة |
| 1 | أقل من سنة |
| 2 | 1-2 سنة |
| 3 | 3-5 سنوات |
| 6 | أكثر من 5 سنوات |

### Salary Display

`salary_hidden = true` is the **default** for new jobs. The toggle `#j-sal-show` (OFF by default) must be checked to reveal salary fields. This is stored as `salary_hidden: !isSalShow` in the payload.

### Rules (permanent)

### Validation Rules (server-enforced — `_validate_accepted_profession_ids`)

1. Must be a list of integers
2. Deduplicated automatically (first-occurrence order preserved)
3. **Max 5 entries** — HTTP 422 if exceeded
4. **Primary profession must not appear** — HTTP 422 if `primary_pid` is in the list
5. **All IDs must exist in `profession_categories` with `is_active = true`** — HTTP 422 for any invalid/inactive ID
6. Validation runs **before any DB mutation** — a failed validation never wipes existing `job_profession_targets` data

### Forbidden Patterns

```
❌ Never store accepted_profession_ids as JSON inside jobs table — use job_profession_targets
❌ Never call _fetch_accepted_professions_batch with an already-closed connection
❌ Snapshot replace (DELETE + INSERT) is the only supported update operation — no partial PATCH
❌ Never DELETE job_profession_targets before validation passes — bad input must not wipe existing data
❌ Never enforce max-5 or primary-profession rules in frontend only — server validates independently
❌ Never batch-fetch accepted professions in a separate request per job — always use _fetch_accepted_professions_batch
❌ Never use try/except pass around INSERT into job_profession_targets — validation must guarantee clean input
❌ accepts_all_professions and individual accepted_profession_ids must not both be active — toggle clears individual targets
❌ Never show salary fields by default — salary_hidden=true is the default, opt-in via j-sal-show toggle
❌ Never hardcode experience level labels in HTML — use TW.EXP_LEVELS from tw-options-data.js
```

---

## [P1] 62. Job Detail Page V2

### Overview

`/job-detail` (served from `job-detail.html`) is the real-time job detail page powered by the API.  
All data is fetched at runtime — zero hardcoded content.

### File Structure

| File | Role |
|------|------|
| `job-detail.html` | HTML structure only — no inline `<style>` or `<script>` |
| `static/job/job-detail.css` | All page styles — `.jd-*` namespace |
| `static/job/job-detail.js` | All page logic — single IIFE, `(function(){...}())` |

### Backend — `get_job()` in `auth.py`

`GET /jobs/{job_id}` calls `get_job(job_id)` which JOINs:
- `users u` → `company_name`, `company_tw_id`
- `LEFT JOIN profiles cp ON j.company_id = cp.user_id` → `company_logo`, `company_verified`
- `LEFT JOIN profession_categories pc ON j.profession_id = pc.id` → `profession_name_ar`, `profession_name_en`, `profession_icon`, `profession_category_group`

No auth required for `GET /jobs/{job_id}` — public endpoint.  
`POST /jobs/{job_id}/apply` requires `Authorization: Bearer {jwt}`.

### Auth Guard

```javascript
var _jwt = localStorage.getItem('tw_jwt') || '';
if (!_jwt) { location.href = '/login'; return; }
```
Redirects immediately if no JWT. Does not wait for DOMContentLoaded.

### Match Section — Client-Side Only

1. Fetch `GET /profile/{user_id}/full` with Bearer JWT → extract skills
2. If API fails → check `localStorage.tw_user.skills` as fallback (not source of truth)
3. If no skills found → show "أضف مهاراتك في ملفك الشخصي" + link to `/profile`
4. If skills found → compute `matched` / `missing` arrays → render conic ring + chips
5. Match % = `matched.length / job.skills.length * 100`

No server-side match endpoint — computed entirely in the browser.

### Responsive Layout

- **Desktop ≥720px**: 2-column grid (`1fr 300px`) — sidebar with apply card + job info + company card + similar jobs. Sticky bar hidden.
- **Mobile <720px**: 1-column — sidebar hidden, sticky apply bar fixed at bottom. Similar jobs shown in main column via `.jd-mobile-only` section.

### Security Rules (permanent)

- All fetch calls use `Authorization: Bearer {jwt}` — X-User-Id header forbidden
- All API data set via `textContent` — `innerHTML = apiData` forbidden
- `_user.id` (from `localStorage.tw_user`) sent in apply POST body alongside JWT — the JWT is the auth signal; `user_id` is the payload
- `source_url` from job API: not rendered on job-detail page (no external link needed here; source is always the platform)

### Forbidden Patterns

```
❌ Hardcoded job data — all content from API
❌ innerHTML = apiData — always textContent
❌ X-User-Id header — JWT only
❌ localStorage as source of truth for user skills — API first, localStorage is fallback
❌ Separate CSS/JS file per feature added to job-detail — stays in job-detail.css/js
❌ Additional inline <style> or <script> blocks in job-detail.html
```

---

## Section 63 — Smart Public Profile Router (`/u/{tw_id}`)

> Added: fix/smart-public-profile-router

### Overview

`/u/{tw_id}` is the **unified public URL** for all account types. The server resolves the tw_id to the correct page based on `users.user_type` in the DB — the prefix character (U/C/T) is a **hint only**, never the source of truth.

### Decision Table

| `users.user_type` | Page served | Injected window variable(s) |
|-------------------|-------------|----------------------------|
| `emp` | `profile-showcase.html` | `window._scProfileIdFromRoute = {numeric_id}` |
| `co` | `company-profile.html` | `window._companyProfileIdFromRoute = {numeric_id}` · `window._companyTwIdFromRoute = "{tw_id}"` |
| `edu` | `edu-profile.html` | `window._eduProfileIdFromRoute = {numeric_id}` · `window._eduTwIdFromRoute = "{tw_id}"` |
| unknown / not found | HTTP 404 | — |

### Helper: `get_user_info_by_tw_id(tw_id)` — `auth.py`

Returns `{ id, tw_id, user_type }` or `None`. Single DB query on `users.tw_id` (UNIQUE index — O(1)). Used exclusively by the Smart Router. Do NOT use it for authorization — JWT is still required for protected endpoints.

### Injection Safety

- `uid` cast to `int()` before injection (no XSS from integer literal).
- `tw_id` passed through `json.dumps()` before injection (handles any string safely).
- Injected `<script>` replaces `</head>` once — safe even if `</head>` appears in content.

### Frontend Load Priority

**Company profile (`company.api.js`):**
1. `window._companyProfileIdFromRoute` — injected by Smart Router (highest priority)
2. `?id=` query param — direct link like `/company-profile?id=123`
3. Session owner fallback — company owner visiting `/company-profile` without any id

**Employee profile (`profile-v2.state.js`):**
1. `window._scProfileIdFromRoute` — injected by Smart Router (unchanged)
2. `?id=` query param

**Edu profile (`edu-profile.html` inline script):**
1. `window._eduProfileIdFromRoute` — injected by Smart Router (via `_urlId` variable)
2. `?id=` query param

### Ownership Check (edu-profile.html)

Ownership is determined by: `user_type === 'edu'` **AND** (no id in URL **OR** `user.id === urlId`). This prevents an edu account from seeing owner controls on another edu account's public profile.

### Empty URL Handling

- `/u` (no tw_id) → HTTP 404 `"معرف الحساب مفقود"` (dedicated route before `{tw_id}` param route)
- `/u/` (trailing slash) → FastAPI redirects to `/u` → 404
- `/u/{non-existent-tw_id}` → HTTP 404 `"الحساب غير موجود"`

### Backward-Compatible Routes (untouched)

```
/company-profile          → company-profile.html (unchanged)
/company-profile?id=123   → works; company.api.js reads ?id= as before
/company-profile.html     → works
/edu-profile              → edu-profile.html (unchanged)
/edu-profile?id=123       → works; edu-profile.html reads ?id= as before
/profile-showcase         → profile-showcase.html (unchanged)
/u/{employee_tw_id}       → profile-showcase.html (same as before)
/u/{company_tw_id}        → company-profile.html (NEW — was broken before)
/u/{edu_tw_id}            → edu-profile.html (NEW)
```

### Future Public ID System (planned — NOT implemented in this PR)

> PR #277 scope = Smart Router for `/u/{tw_id}` only. The items below are architectural decisions, not executable code.

#### ID Format — Final Decision

```
{ENTITY_PREFIX}{RANDOM_UNIQUE_CODE}

Examples:
  U8F3K9Q2L1A  →  Employee
  C7M2X9P4R0D  →  Company
  T5Q8L1Z6N3B  →  Education/Training institution
  J9R2L7N5B1   →  Job posting
  P6X3A8Q1M4   →  Company post
  A4K9D2L8Z0   →  Job application
  V2M7Q5R9A1   →  Verification request
  D3L6Q8P2N7   →  Course (دورة)
  E1K5M9R3Z8   →  Enrollment (تسجيل طالب بدورة)
  L7Q2A5X1D4   →  Lesson (درس)
  Q8N3K6P0M2   →  Quiz/Exam (اختبار)
  S5R1L9D7Q3   →  Certificate (شهادة)
```

**No country code inside public_id — ever.**
Country data belongs in the DB on the entity/user record. Reasons: country can change, it adds no uniqueness value, and it permanently brands the link with data that may be inaccurate or privacy-sensitive.

#### Prefix Table

| Prefix | Entity (EN) | Entity (AR) | Table field | Public route (future) |
|--------|-------------|-------------|-------------|----------------------|
| `U` | Employee | موظف | `users.tw_id` | `/u/{tw_id}` ✅ live |
| `C` | Company | شركة | `users.tw_id` | `/u/{tw_id}` ✅ live |
| `T` | Training/Education | تعليم وتدريب | `users.tw_id` | `/u/{tw_id}` ✅ live |
| `J` | Job posting | وظيفة | `jobs.public_id` | `/j/{public_id}` |
| `P` | Post | منشور | `company_posts.public_id` | `/post/{public_id}` |
| `A` | Application | طلب تقديم | `job_applications.public_id` | internal only |
| `V` | Verification | طلب توثيق | `verify_requests.public_id` | internal only |
| `D` | Course | دورة تدريبية | `courses.public_id` | `/course/{public_id}` |
| `E` | Enrollment | تسجيل طالب | `enrollments.public_id` | internal only |
| `L` | Lesson | درس | `lessons.public_id` | internal only |
| `Q` | Quiz/Exam | اختبار | `quizzes.public_id` | internal only |
| `S` | Certificate | شهادة | `certificates.public_id` | `/cert/{public_id}` |

#### Generator Pattern (planned)

One shared function in `auth.py`:
```python
def generate_public_id(prefix: str) -> str:
    """Generates a public ID: {PREFIX}{RANDOM_10_ALPHANUM}
    No country code. Country data lives on the entity record in DB."""
    import random, string
    chars = string.ascii_uppercase + string.digits
    rand = ''.join(random.choices(chars, k=10))
    return f"{prefix}{rand}"

# Account IDs (tw_id) migrate to call generate_public_id internally:
def generate_tw_id(user_type: str, country_code: str = 'DEFAULT') -> str:
    # country_code kept in signature for backward compat — stored in users.country_code, NOT in the id
    prefix = TYPE_PREFIX.get(user_type, 'U')
    return generate_public_id(prefix)
```

`generate_public_id(prefix)` — single argument, no country code.
Do NOT write `generate_public_id(prefix, country_code)` or `generate_public_id(prefix, cc)`.

#### Country Catalog (separate concern)

Country data is a separate project/table:
- Used for: registration, profile display, search/filter, job location, company addresses
- Stored as: `country_iso2`, `country_name`, `dial_code` on the entity row
- NOT embedded in `public_id`

#### Course Platform — Access Rules (planned)

Public route `/course/{course_public_id}` may show course info page (title, description, instructor).
Learning content (lessons, video, quizzes) is always protected:

```
JWT required
+ DB enrollment check (is user enrolled?)
+ payment/access check (if course is paid)
+ owner/instructor/admin permission per endpoint
```

`public_id` = identity + shareable URL only. It is NOT an access credential.

#### File & Video Security Rules (planned)

```
❌ Direct static file URLs for paid/private course content
❌ Permanent CDN links for lesson videos accessible without auth
✅ Backend permission check before serving any protected file
✅ Signed / time-limited URLs for video/file delivery (generated server-side)
✅ Permission check: JWT + enrollment + payment status, every request
```

#### Planned PR Sequence

```
PR #277  /u Smart Router                ← current PR (only this)
PR +1    jobs.public_id (J)             ← /j/{public_id}, backfill, keep /job-detail?id=
PR +2    company_posts.public_id (P)    ← /post/{public_id}
PR +3    job_applications.public_id (A) ← internal; notifications; no public route
PR +4    verify_requests.public_id (V)  ← internal; admin; no public route
PR +5    courses public_id (D/E/L/Q/S)  ← after course platform is designed
```

Each PR is independent. No PR mixes public_id implementation with other features.

### Forbidden Patterns

```
❌ Using tw_id prefix (U/C/T first character) as the source of truth for routing
❌ Exposing numeric id in public share URLs (/u/123, /j/456)
❌ Using localStorage to decide which page to open from /u/{tw_id}
❌ X-User-Id header — JWT only
❌ Two separate routes for the same public entity (/u/C… AND /company-public/…)
❌ Opening an empty profile/company/edu page when tw_id is absent or unknown
❌ Bypassing the injected window var and re-reading id from the URL in new pages
❌ Country code / ISO code / dial code inside any public_id field
❌ generate_public_id(prefix, country_code) — no country param in the generator
❌ Direct static URLs for protected course/lesson/video content
❌ Treating public_id as an access credential (it is identity + URL only)
❌ Mixing public_id implementation with Smart Router in the same PR
```

---

## [P1] 64. Post Save System — حفظ المنشور

**Implemented in:** PR #388 (feat/company-post-save-system)

### Purpose

Private per-user save/bookmark for company posts. State persists in DB, not localStorage. Identical queue architecture to the Post Appreciation System (§22a in SYSTEMS_INDEX.md).

### Database Table: `company_post_saves`

```sql
CREATE TABLE company_post_saves (
    id         SERIAL PRIMARY KEY,
    post_id    INTEGER NOT NULL REFERENCES company_posts(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX  idx_post_saves_post ON company_post_saves(post_id);
CREATE INDEX  idx_post_saves_user ON company_post_saves(user_id);  -- for future /me/saved-posts
CREATE UNIQUE INDEX uq_post_save_user ON company_post_saves(post_id, user_id);
```

**One save per user per post — enforced at DB level via `uq_post_save_user`.**

### auth.py Helper: `set_company_post_save(post_id, user_id, saved)`

```python
# saved=True  → INSERT INTO company_post_saves ... ON CONFLICT DO NOTHING
# saved=False → DELETE FROM company_post_saves WHERE post_id=:pid AND user_id=:uid
# Returns {saved: bool}
```

`get_company_posts(company_id, viewer_user_id)` was extended to include:
```sql
LEFT JOIN company_post_saves ups ON ups.post_id = cp.id AND ups.user_id = :viewer_uid
-- adds: (ups.user_id IS NOT NULL) AS viewer_saved
```
When `viewer_user_id` is absent (unauthenticated), `viewer_saved` is always `FALSE`.

### API Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PUT | `/company/posts/{post_id}/save` | JWT Bearer (required) | حفظ / إلغاء حفظ المنشور |

**Request body:**
```json
{ "saved": true }   // or false
```

**Response:**
```json
{ "status": "success", "saved": true }
```

**Error codes:**
| Code | Condition |
|------|-----------|
| 401 | No JWT |
| 404 | Post not found |
| 429 | Rate limit exceeded (10 req / 10s per (user, post)) |

**No 403 for post owner** — owner may save their own post.

### viewer_saved — Source of Truth

`viewer_saved` is returned by `GET /company/posts/{company_id}` when a JWT is present. It is the **only approved source of save state** on the frontend. Do not cache, infer, or compute save state from localStorage.

### Frontend Architecture (`static/company/company.posts.js`)

**Desired State Queue** — identical pattern to the Post Appreciation System:

| Variable | Purpose |
|----------|---------|
| `_saveDesired[postId]` | Last desired state from user click |
| `_saveInFlight[postId]` | `true` while a request is active |
| `_saveOrigState[postId]` | Pre-click state for rollback on failure |

**`_toggleSave(postId)`** — called on button click:
1. Check JWT → show guest toast `'سجّل دخولك لحفظ المنشور'` if absent
2. Capture `_saveOrigState` (first click only, before flight)
3. Record `_saveDesired`
4. Call `_renderSaveButton(btn, desired)` immediately (optimistic UI)
5. If already in-flight → return; handler picks up new desired on resolve

**`_dispatchSave(postId)`** — HTTP request + no-flicker logic:
1. PUT `/company/posts/{postId}/save` with `{ saved: desired }`
2. On 429 → rollback to `_saveOrigState`
3. On error → rollback to `_saveOrigState`
4. On success → **check `desired !== srvActive` BEFORE render**
   - If stale (user clicked again mid-flight): update `_saveOrigState`, dispatch follow-up, `return` without rendering
   - If match: call `_renderSaveButton(btn, srvActive)`, clear queue

**`_renderSaveButton(btn, active)`** — single DOM update point:
- `active=true` → filled bookmark icon + `save-active` class + `data-saved="1"`
- `active=false` → outline bookmark icon, class removed, `data-saved="0"`

### CSS

```css
.pc-btn--save.save-active       { color: #fbbf24; }
.pc-btn--save.save-active svg   { fill: currentColor; }
```

### Rules (Forbidden Patterns)

```
❌ Using localStorage as the source of truth for save state
❌ Exposing save count publicly (count is private — not shown on the card)
❌ A second DB table for post saves
❌ A second endpoint for post saves (POST toggle, etc.)
❌ Simplifying the Desired State Queue to a plain toggle
❌ Updating .save-active or data-saved outside _renderSaveButton()
❌ Checking save state from viewer_saved before viewer_user_id is resolved
```
