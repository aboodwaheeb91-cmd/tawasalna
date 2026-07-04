# Company Jobs & Applicants — Design Contracts

> **شامل:** كرت الوظيفة للمالك · نظام الموقع · مودال المتقدمين · روابط البروفايل · قرارات PR #327–#339

---

## 1. صفحة الشركة — مشاهدة الوظائف

### عام

صفحة الشركة (`/company-profile`) تعرض تبويب "الوظائف" لكلا المالك والزائر، لكن المحتوى يختلف حسب `companyState.permissions`.

| المستخدم | ما يراه |
|---------|---------|
| مالك الشركة (`isOwner: true`) | كرت المالك (صورة + حالة + إجراءات) + أدوات نشر وإدارة وظيفة جديدة |
| زائر / موظف | كرت الزائر (بيانات الوظيفة + زر "تقديم" فقط) |

- `companyState.permissions.isOwner` هو المصدر الوحيد للتمييز بين المالك والزائر داخل الـ frontend. لا تُضف شرط مالكية ثانٍ.
- الصلاحية الحقيقية تُتحقق دائماً server-side عبر `token["user_id"] == jobs.company_id`.

---

## 2. كرت الوظيفة للمالك — تصميم معتمد (PR #335–#339)

### بنية الكرت

```
┌──────────────────────────────────────────────────────────────┐
│  [صورة الشركة]   اسم الوظيفة                [عدد المتقدمين] │
│  [حالة الوظيفة]  الصنف الرئيسي (أخضر)       [زر: مشاهدة]   │
│                  📍 الموقع · 💼 نوع الدوام · 🕒 وقت النشر   │
│                                              [زر: الإدارة]   │
└──────────────────────────────────────────────────────────────┘
```

الكرت `flex-direction: row` بعنصرين:
- **يمين الكرت** — `.job-logo-col`: عمود يحتوي صورة الشركة + شارة الحالة أسفلها مباشرة.
- **وسط الكرت** — `.job-card-body`: عمود يحتوي اسم الوظيفة + الصنف الأخضر + سطر الميتا.
- **يسار الكرت** — `.job-owner-col`: عمود ثابت يحتوي عداد المتقدمين + الزرين.

### العناصر المعتمدة

| العنصر | الكلاس | الوصف |
|-------|--------|-------|
| صورة الشركة | `.job-card-logo` | 44px, border-radius:10px |
| شارة الحالة | `.job-logo-status--active/paused/closed` | أسفل الصورة مباشرة |
| اسم الوظيفة | `.job-title` | — |
| الصنف الرئيسي | `.job-card-sub` | font-size:.67rem; color:#00c896; font-weight:700 |
| سطر الميتا | `.job-meta-row` | flex-wrap:wrap; gap:4px 3px |
| عنصر ميتا واحد | `.jmr-item` | inline-flex; align-items:center; gap:4px |
| فاصل الميتا | `.jmr-sep` | الحرف `│` بلون خافت |
| أيقونة الميتا | SVG داخل `.jmr-item` | 10×10px، لا emoji |
| عداد المتقدمين | `.job-applicant-count` + `.job-cnt-badge` | داخل `.job-owner-col` |
| زر مشاهدة | `.joc-btn.joc-btn--primary` | تيل، rounded rectangle خفيف |
| زر الإدارة | `.joc-btn.joc-btn--muted` | أزرق، rounded rectangle خفيف |

### سطر الميتا — ترتيب الحقول

```
📍 الموقع  │  💼 نوع الدوام  │  🕒 وقت النشر
```

السبب: الموقع الأهم معلومة، ثم نوع الدوام، ثم تاريخ النشر. الترتيب ثابت.

### قواعد ثابتة — كرت الوظيفة

```
✅ الأزرار دائماً داخل الكرت — لا تحت الكرت بعرض 100% خارجي
✅ على الموبايل: .job-owner-col يبقى عموداً (column) ولا يتحول إلى row
✅ .job-owner-col ثابت على اليسار — لا يُكسر إلى سطر جديد
✅ .joc-btn--primary و.joc-btn--muted بنفس الحجم والشكل
✅ لا زر حذف داخل كرت الوظيفة
✅ أزرار الكرت rounded rectangle بزوايا خفيفة (border-radius:6px) — متناسقة مع أزرار المرشح من حيث الحجم والإحساس، لكن ليست pill كاملة

❌ flex-wrap:wrap على .job-card في الموبايل — يكسر layout الكرت
❌ height ثابت على .joc-btn — استخدم padding فقط
❌ emoji بدلاً من SVG في سطر الميتا
❌ نص حر مباشر داخل attribute بدون _escAttr
```

### أمان — `_escAttr` مقابل `_esc`

| الدالة | تستخدم في |
|-------|----------|
| `_esc(str)` | محتوى HTML — تهرب `& < >` |
| `_escAttr(str)` | قيم الـ attributes — تهرب `& " ' < >` |

**ممنوع** استخدام `_esc` داخل `src=""` أو `data-*=""` أو أي attribute — استخدم `_escAttr` دائماً.

---

## 3. دورة حياة الوظيفة — Job Lifecycle (PR feat/job-lifecycle)

### الحالات الأربع

| `effective_status` | الشارة | مخزّن في DB | ما يراه الزائر | ما يراه المالك |
|-------------------|--------|-------------|----------------|----------------|
| `active` | "نشطة" — أخضر | `status='active'` | كرت + زر تقديم | كرت + مشاهدة + إدارة |
| `paused` | "موقوفة" — أصفر | `status='paused'` | كرت فقط (بدون تقديم) | كرت + مشاهدة + إدارة |
| `closed` | "منتهية" — رمادي | `status='closed'` | يُخفى (يُحسب في closed_count) | كرت + مشاهدة متقدمين فقط |
| `expired` | "انتهت صلاحيته" — رمادي | `status='closed'` + 30d | يُخفى | كرت فقط (سجل، لا أزرار) |

### قاعدة `effective_status`

**`effective_status` محسوب server-side — لا يُخزَّن أبداً في DB**. يُعاد حسابه في كل طلب API:

```python
def _eff_status(status, closed_at, expires_at) -> str:
    if status == 'closed':
        ref = closed_at or expires_at
        return 'expired' if ref and (now - ref).days >= 30 else 'closed'
    if status in ('active', 'paused') and expires_at and now > expires_at:
        # Auto-close: listing duration (30 days active) elapsed
        return 'expired' if (now - expires_at).days >= 30 else 'closed'
    return status  # 'active' or 'paused'
```

### مدة الإعلان والـ Timer

- كل وظيفة جديدة تحصل على `expires_at = NOW() + 30 days` تلقائياً.
- عند الإيقاف (`paused`): يُسجَّل `paused_at = NOW()`.
- عند الاستئناف (`active`): `expires_at = expires_at + (NOW() - paused_at)` → الوقت المتوقف لا يُحسب من مدة الإعلان.
- عند الإنهاء اليدوي (`closed`): `closed_at = NOW()`.
- الإغلاق التلقائي يحدث عند `expires_at < NOW()` — محسوب بدون cron job.

### الانتقالات المسموحة والمحجوبة

| من \ إلى | `active` | `paused` | `closed` |
|---------|---------|---------|---------|
| `active` | — | ✅ | ✅ |
| `paused` | ✅ | — | ✅ |
| `closed` | ❌ | ❌ | — |
| `expired` | ❌ | ❌ | ❌ |

الحجب يحدث server-side في `set_job_status()` + `apply_job()` + `update_job_endpoint`.

### حماية server-side (ممنوعات)

```
❌ التقديم على وظيفة موقوفة أو منتهية أو انتهت صلاحيتها
❌ إعادة فتح وظيفة منتهية أو انتهت صلاحيتها
❌ تعديل وظيفة انتهت صلاحيتها (PUT /company/jobs/{id})
```

### ما يراه الزائر (company-profile)

- `GET /jobs?company_id=X` يعيد `active + paused` فقط.
- يتضمن حقل `closed_count` لعدد الوظائف المنتهية/الموقوفة تلقائياً.
- `effective_status='active'` → زر "تقديم الآن".
- `effective_status='paused'` → كرت بدون زر تقديم.
- إذا `closed_count > 0` → سطر ملخص في أسفل القائمة: "تم إنهاء X إعلانات وظيفية".

### شارة الحالة — CSS

```
.job-logo-status--active  → أخضر
.job-logo-status--paused  → أصفر
.job-logo-status--closed  → رمادي (يُستخدم لـ closed + expired)
```

`expired` يعيد استخدام `--closed` لأنه نفس الإحساس البصري — لا class CSS جديد.

### الإضاءة

- الإضاءة تُطبَّق عبر `CSS: .job-card[data-status="active"]` فقط.
- `data-status` يُضبط من `j.effective_status` في `renderJobs()`.

### أعمدة DB الجديدة (migration: `_migrate_job_lifecycle`)

| العمود | النوع | الاستخدام |
|--------|------|---------|
| `closed_at` | `TIMESTAMP NULL` | وقت الإغلاق اليدوي |
| `paused_at` | `TIMESTAMP NULL` | وقت آخر إيقاف (NULL إذا نشط) |
| `expires_at` | موجود مسبقاً — مستخدم الآن | موعد انتهاء مدة الإعلان |
| `duration_days` | `SMALLINT DEFAULT 7` | مدة استقبال الطلبات المختارة عند النشر |

### مدة استقبال الطلبات (`duration_days`)

- القيم المسموحة: **3، 7، 14، 30** يوماً فقط.
- الافتراضي: **7 أيام** (يُطبَّق server-side إذا لم تُرسَل قيمة أو كانت القيمة غير مسموحة).
- عند الإنشاء: `expires_at = NOW() + duration_days days`.
- عند التعديل (active/paused فقط): تعيين قيمة جديدة يُعيد ضبط `expires_at = NOW() + duration_days days` (reset للساعة).
- ممنوع تعديل `duration_days` على إعلان `closed` أو `expired`.
- الوظائف القديمة (بدون `duration_days`) تُعامَل كـ 7 أيام بفضل `DEFAULT 7` — لا reset لـ `expires_at` الموجود.

### القاعدة الذهبية

```
✅ effective_status يُحسب server-side في كل طلب
✅ لا cron job — الانتهاء التلقائي computed في _eff_status()
✅ الحجب يحدث في auth.py: set_job_status + apply_job + update_job_endpoint
✅ Frontend يعتمد على j.effective_status فقط (لا j.status مباشرة)
✅ expired يعيد استخدام --closed CSS class (لا CSS جديد)

❌ تخزين 'expired' في DB كـ status value
❌ فتح إعلان منتهٍ
❌ تعديل إعلان انتهت صلاحيته
❌ إضافة cron job لتغيير status تلقائياً
```

---

## 4. نظام موقع الوظيفة — القاعدة الجديدة (PR #338)

### المصدر الرسمي للبيانات

- `TW.fillCountries()` و`TW.fillCities()` من `static/shared/tw-options-data.js`.
- لا نستخدم input نص حر لحقل الموقع في نشر وظيفة أو تعديلها.

### بنية الحقول داخل الـ modal

```html
<!-- اختيار البلد -->
<select id="j-loc-country" class="ep-select">...</select>

<!-- اختيار المحافظة — يظهر فقط بعد اختيار البلد -->
<div id="j-city-wrap">
  <select id="j-loc-city" class="ep-select">...</select>
</div>
```

### التخزين في DB

الحقل `jobs.location` (النص القديم) يبقى ويُخزَّن بصيغة:

```
البلد - المحافظة
مثال: الأردن - عمان
```

لا يوجد جدول منفصل للموقع. الحقل القديم يُعاد استخدامه بصيغة مهيكلة.

### `_shortLoc(str)` — للبيانات القديمة فقط

```js
// يحوّل "الأردن، عمان، طبربور" → "الأردن - عمان"
// fallback للبيانات القديمة التي كانت نصاً حراً طويلاً
```

`_shortLoc` لا يُستخدم للبيانات الجديدة — البيانات الجديدة مخزّنة بصيغة `"بلد - مدينة"` مباشرة.

### قواعد ثابتة — نظام الموقع

```
✅ اختيار البلد أولاً، ثم تظهر قائمة المحافظة تلقائياً
✅ TW.fillCountries() للبلدان — نفس مصدر سائر الصفحات
✅ TW.fillCities() للمحافظات — نفس مصدر سائر الصفحات
✅ scSelectInit() بعد كل ملء dynamic للـ <select>
✅ العرض في كرت الوظيفة: "الأردن - عمان" فقط (لا تفاصيل إضافية)
✅ _shortLoc كـ fallback للبيانات القديمة فقط

❌ input نص حر لحقل موقع الوظيفة
❌ جدول DB منفصل للموقع
❌ عرض العنوان الكامل (شارع / حي) داخل إعلان الوظيفة
❌ TW.fillCountries بدون scSelectInit بعده
```

---

## 5. مودال المتقدمين / المرشحين

### الهيكل العام

مودال المتقدمين هو المكان الأساسي لإدارة المتقدمين على وظيفة معينة. يُفتح عبر زر "مشاهدة المتقدمين" في كرت الوظيفة للمالك.

### فلاتر الحالات

| الفلتر | `data-val` | المعنى |
|--------|-----------|-------|
| الكل | `all` | جميع المتقدمين |
| محفوظ | `saved` | حُفظ كمرشح |
| مرشح قوي | `shortlisted` | مرشح قوي |
| تم التواصل | `contacted` | تم التواصل معه |
| مقابلة | `interview` | في مرحلة المقابلة |
| تم التوظيف | `hired` | تم التوظيف |
| غير مناسب | `rejected` | غير مناسب |
| بدون وظيفة | `unlinked` | لم يُربط بوظيفة |

### أزرار كرت المرشح

| الزر | الكلاس | الوظيفة |
|-----|--------|---------|
| فتح البروفايل | `.co-app-profile-link` | `href=/u/{tw_id}` |
| إدارة | `.co-app-save-btn` | يغير حالة المرشح |
| إزالة | — | يزيل المرشح من القائمة |

**مهم:** زر "إزالة" موجود فقط في مودال المتقدمين وليس داخل كرت الوظيفة في الصفحة الرئيسية.

### أزرار كرت الوظيفة — المرجع البصري

أزرار `.joc-btn--primary/muted` في كرت الوظيفة تتناسق بصرياً مع أزرار المرشح من حيث الحجم والإحساس، لكن شكلها **rounded rectangle خفيف** وليس pill كاملة:
- `border-radius: 6px` (rounded rectangle — ليس pill)
- `padding: 4px 10px`
- `font-size: .62rem`
- `font-weight: 700`
- تحتفظ بألوانها الخاصة (تيل + أزرق)، ليس بلون أزرار المرشح

---

## 6. الخصوصية

### ما يظهر للزائر والمتقدم

- مودال المتقدمين هو owner-only تماماً — لا يظهر للزائر.
- بيانات المتقدم المعروضة للشركة: الاسم، الصورة، التخصص، المدينة، البلد، تاريخ التقديم، الحالة.
- **لا تُعرض:** الهاتف، البريد الإلكتروني، العنوان التفصيلي، أو أي بيانات KYC.

### اتجاه المحادثة

- الموظف لا يبدأ محادثة مع الشركة من خلال التقديم.
- الشركة هي التي تبدأ المحادثة بعد مراجعة المتقدم.
- لا يوجد زر "تواصل" في كرت المتقدم يُرسل رسالة مباشرة.

---

## 7. روابط البروفايل — القاعدة الرسمية

### الرابط العام الرسمي

```
/u/{tw_id}
```

يعمل لجميع أنواع الحسابات (موظف / شركة / جهة تعليمية) عبر Smart Router في `server.py`.

### ممنوع في أي كود جديد

```
❌ /profile?id=        → قديم، ممنوع في روابط جديدة
❌ /profile.html       → ممنوع
❌ /company-profile    → كرابط عام خارجي
❌ /edu-profile        → كرابط عام خارجي
❌ /u/{user_id}        → الـ user_id رقمي داخلي، لا يُكشف
❌ /u/{company_id}     → نفس السبب
✅ /u/{tw_id}          → الرابط الرسمي الوحيد
```

الروابط القديمة (`/company-profile?id=`, `/profile-showcase`) تبقى تعمل للـ backward compatibility لكن لا تُضاف في أي كود جديد.

---

## 8. سجل القرارات — PR #327–#339

| PR | الفرع | ما تغيّر |
|----|-------|---------|
| #327 | feat/company-job-management | إدارة وظائف الشركة بعد النشر: تعديل، إيقاف، حذف |
| #329 | fix/company-job-card-status | إصلاح عرض حالة الوظيفة وتحديث الكرت بعد toggle |
| #330 | fix/company-jobs-display | إصلاح اختفاء الوظائف عند `_mergeCompanyState` |
| #331 | fix/company-jobs-cache | إصلاح مشكلة الكاش وقوائم الوظائف القديمة |
| #332 | fix/job-edit-form-populate | تعبئة نموذج تعديل الوظيفة بكل الحقول (profession, skills…) |
| #333 | feat/company-post-card-redesign | إعادة تصميم كرت منشور الشركة |
| #334 | feat/company-post-card-polish | تحسينات كرت المنشور |
| #335 | design/company-owner-job-card | إعادة بناء كرت الوظيفة للمالك: صورة شركة + حالة + `_escAttr` |
| #336 | design/company-owner-job-card-v2 | أيقونات SVG، شارة الحالة أسفل الصورة، عمود الإجراءات |
| #337 | fix/owner-job-card-profession | إصلاح ظهور الصنف: `_prefetchProfCatalog` عند تحميل الموديول |
| #338 | fix/owner-job-card-mobile-layout | موبايل بدون horizontal overflow + نظام موقع مهيكل (بلد/محافظة) |
| #339 | design/align-job-card-buttons | محاذاة أزرار كرت الوظيفة مع أزرار كرت المرشح (pill shape) |
| #340 | docs/company-jobs-applicants | توثيق نظام الوظائف والمتقدمين |
| #341 | fix/owner-job-card-polish | تلميع كرت المالك: dropdown أصغر، border-radius 6px، رابط job-detail صحيح |
| #342 | fix/bfcache-owner-state | إصلاح Mixed State عند history.back() بعد bfcache restore |
| #? | feat/job-lifecycle | 4 حالات + auto-close + effective_status + إنهاء الإعلان |

### قرارات تقنية تراكمت

1. **`_mergeCompanyState`**: لا تُحدَّث `companyState.jobs` إلا إذا أعاد الـ API `Array.isArray(jobs)`. يمنع اختفاء الوظائف عند toggle الحالة.
2. **`_prefetchProfCatalog`**: fetch مبكر لـ `/professions` عند تحميل `company.jobs.js`، قبل فتح الـ modal، لأن `_loadProfessions()` تبايكوت إذا لم يكن `#j-prof` موجوداً.
3. **`_shortLoc`**: fallback للبيانات القديمة فقط. البيانات الجديدة تُخزَّن بصيغة `"بلد - مدينة"`.
4. **`data-status` attribute**: الإضاءة تُطبَّق بـ CSS فقط — لا JS.
5. **`effective_status`**: محسوب في `_eff_status()` (auth.py) — لا يُخزَّن. يُعاد حسابه في كل request. الـ frontend يعتمد عليه فقط.

---

## 9. QA Checklist — كرت الوظيفة والمتقدمين

يجب التحقق من هذه النقاط في كل PR يمس صفحة الشركة أو الوظائف:

```
□ لا horizontal overflow على عرض 390px (iPhone SE)
□ كرت الوظيفة لا يخرج من الشاشة على الموبايل
□ أزرار المالك داخل الكرت وليست أسفله بعرض كامل
□ .job-owner-col يبقى عموداً على الموبايل (flex-direction:column)
□ زر "مشاهدة المتقدمين" يفتح مودال المتقدمين
□ زر "الإدارة" يفتح القائمة
□ الصنف (profession) يظهر تحت اسم الوظيفة باللون الأخضر
□ الموقع يظهر بصيغة "بلد - محافظة" فقط (لا تفاصيل زائدة)
□ الوظيفة النشطة لها إضاءة داخلية خفيفة فقط (paused/closed/expired لا إضاءة)
□ روابط البروفايل تعتمد /u/{tw_id} فقط
□ لا backend / API / DB changes في PR التوثيق
□ لا زر حذف داخل كرت الوظيفة
□ الحالة تظهر كشارة أسفل صورة الشركة داخل الكرت
□ نموذج نشر/تعديل الوظيفة يستخدم قائمة بلد + قائمة محافظة (لا input نص حر)
□ الوظيفة المنتهية (closed) تعرض "مشاهدة المتقدمين" فقط لمدة 30 يوم
□ الوظيفة منتهية الصلاحية (expired) لا أزرار — سجل فقط
□ زر "إنهاء الإعلان" يظهر فقط للوظائف النشطة أو الموقوفة
□ الزائر يرى سطر "تم إنهاء X إعلانات وظيفية" إذا كان closed_count > 0
□ التقديم على وظيفة موقوفة/منتهية يُرفض server-side (422)
```

---

*آخر تحديث: 2026-07-04 — يعكس القرارات كما في PR feat/job-lifecycle.*
