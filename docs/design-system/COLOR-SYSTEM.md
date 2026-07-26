# DS-COLOR — Color System V1

> **Phase 0 — Architecture & Documentation Foundation**
>
> هذا الملف هو الـ contract المعماري الرسمي لنظام الألوان في منصة تواصلنا.
> المحتوى: توثيق وقواعد فقط — لا تعديل CSS أو Runtime في Phase 0.
> التنفيذ الفعلي (إضافة `--color-*` tokens إلى `tw_shared.css`) يبدأ في Phase 1.

---

## CLR-00 — Routing Protocol

**اقرأ هذا القسم أولاً قبل كل شيء.**

| إذا كنت... | اذهب إلى |
|------------|----------|
| تريد استخدام لون موجود | CLR-06 → CLR-11 — ابحث عن الـ Semantic token المناسب |
| تضيف لوناً جديداً لنظام موجود (DS-INP / DS-BTN / DS-FEEDBACK) | CLR-20 + CLR-21 + CLR-22 — حدود المسؤولية أولاً |
| تضيف Domain Alias في ملف CSS صفحة | CLR-15 — Local Alias Policy |
| تحتاج لون من `--fbk-bdr-*` أو DS-FEEDBACK | CLR-21 — هذه ليست DS-COLOR canonical |
| تريد تعديل `--ac` أو `--ac2` مباشرة | CLR-04 + CLR-27 — ممنوع؛ استخدم Semantic token |
| تريد إضافة `--color-*` token جديد | CLR-28 — V1 Scope Rule (No Token Without Real Consumer) |
| تريد ترحيل لون hardcoded إلى token | CLR-26 — Migration ≠ Redesign |
| تريد تعديل company.css (blue/teal swap) | CLR-16 — Migration Intent only; لا تغيير الآن |
| لون يبدو محلياً (مثل الـ cyan في messages.css) | CLR-25 — Promotion Criteria |
| تعمل على Phase 1 (إضافة tokens إلى tw_shared.css) | CLR-02 + CLR-03 + CLR-05 → CLR-11 + CLR-27 + CLR-30 |

---

## CLR-01 — Purpose & Scope

### ما هو DS-COLOR؟

DS-COLOR هو نظام الألوان المركزي لمنصة تواصلنا. يُحدِّد:
- **الـ token names** — الأسماء الرسمية لكل لون يُستخدم في المنصة
- **الـ token values** — القيم الفعلية الموجودة في `tw_shared.css`
- **القواعد** — من يملك ماذا، ما الفرق بين Semantic وCategorical، كيف يُستخدم الـ Alpha

### النطاق

**داخل النطاق (DS-COLOR يملكه):**
- كل `--color-*` tokens في `tw_shared.css`
- الـ palette الأساسي (Brand / Background / Border / Text / Status / Categorical)
- الـ Legacy Aliases (`--ac`, `--ac2`, `--bg`, إلخ) بعد Phase 1
- قواعد Alpha Policy
- قواعد Light/Dark theme (Dark Only في V1)
- الـ conceptual naming للـ Flutter

**خارج النطاق (DS-COLOR يُزوِّد الـ channel فقط):**
- كيفية تطبيق الألوان على Input states → DS-INP
- كيفية تطبيق الألوان على Button states → DS-BTN
- كيفية تطبيق الألوان على Feedback types → DS-FEEDBACK
- Border color لرسائل DS-FEEDBACK (`--fbk-bdr-*`) → DS-FEEDBACK يملكها، ليست DS-COLOR canonical
- Glow effects، Box shadows، Text shadows → DS-Shadow (مستقبلي) — DS-COLOR يُزوِّد الـ channel فقط

---

## CLR-02 — Runtime Source of Truth

**المصدر الوحيد لكل `--color-*` tokens هو `tw_shared.css` .**

```
tw_shared.css (السطر 11–34 حالياً)
└── :root { ... }
    ├── Foundation / Primitive tokens  (يُضاف في Phase 1)
    ├── Semantic tokens                (يُضاف في Phase 1)
    └── Legacy Aliases                 (يُضاف في Phase 1 — يُزال في Phase 4)
```

### الحالة الحالية (Phase 0 — قبل التغيير)

`tw_shared.css` يحتوي حالياً:
- `--ac`, `--ac2`, `--bg`, `--bg2`, `--bdr`, `--t1`–`--t4` — (Legacy names; ستُحوَّل إلى Aliases في Phase 1)
- `--danger`, `--warning`, `--success` — (Status tokens; ستُحوَّل إلى Aliases في Phase 1)
- `--ac-rgb`, `--danger-rgb`, `--warning-rgb`, `--ac2-rgb` — (RGB channels; راجع CLR-05)
- `--tw-feedback-bottom` — **ليس color token** — DS-FEEDBACK يملكه (FBK-09)
- `--fbk-bdr-*` — **ليست DS-COLOR canonical** — DS-FEEDBACK يملكها (CLR-21)

### الحالة المستهدفة (Phase 1 — بعد التغيير)

```css
/* Section 1: Foundation / Primitive */
--color-prim-teal:   #00c896;
--color-prim-blue:   #2563ff;
/* ... */

/* Section 2: Semantic */
--color-brand-primary: var(--color-prim-teal);
/* ... */

/* Section 3: Legacy Aliases */
--ac:  var(--color-brand-primary);
--ac2: var(--color-brand-secondary);
/* ... (حتى Phase 4 حيث تُزال عند zero consumers) */
```

### ممنوعات CLR-02

```
❌ تعريف --color-* tokens خارج tw_shared.css (في أي page CSS file)
❌ إعادة تعريف (redefine) --color-* token موجود في page CSS
❌ إضافة --color-* token جديد في Phase 0 (documentation only)
```

---

## CLR-03 — Three Logical Layers

DS-COLOR V1 يُنظِّم `tw_shared.css` في ثلاثة أقسام منطقية:

### Section 1 — Foundation / Primitive Layer

```
الغرض:    تسمية وحصر القيم الخام للألوان
التسمية:  --color-prim-*
الاستخدام: Semantic tokens فقط (لا page CSS مباشرة)
مثال:     --color-prim-teal: #00c896;
```

**القاعدة:** لا تُستخدم Foundation tokens مباشرةً في feature CSS. يستخدمها Semantic layer فقط.

### Section 2 — Semantic Layer

```
الغرض:    ربط اللون بدور وظيفي، لا بقيمة مادية
التسمية:  --color-brand-* / --color-bg-* / --color-border-* / --color-text-* / --color-status-* / --color-categorical-*
الاستخدام: Feature CSS، page modules، domain aliases
مثال:     --color-brand-primary: var(--color-prim-teal);
```

**القاعدة:** هذه الطبقة هي ما يُستخدم في page CSS وfeature CSS.

### Section 3 — Legacy Aliases Layer

```
الغرض:    التوافق العكسي — حماية الكود الموجود الذي يستخدم --ac وما شابهها
التسمية:  --ac, --ac2, --bg, --t1, --t2, إلخ (الأسماء القديمة)
المصدر:   يُشير إلى Semantic tokens (لا قيم مباشرة)
الدورة:   Phase 1 (إضافة) → Phase 4 (حذف عند zero consumers)
```

**القاعدة:** لا تُضاف Legacy Aliases جديدة. القديمة تُزال تدريجياً بعد توفر Semantic البديل.

### ترتيب القراءة في Phase 1

```css
/* === SECTION 1: Foundation / Primitive ===
   Raw color palette. Not for direct use in feature CSS. */
:root {
  --color-prim-teal: #00c896;
  /* ... */
}

/* === SECTION 2: Semantic ===
   Role-based tokens. Use these in feature CSS. */
:root {
  --color-brand-primary: var(--color-prim-teal);
  /* ... */
}

/* === SECTION 3: Legacy Aliases ===
   Backward compat. Do NOT add new entries.
   Will be removed in Phase 4 when consumers = 0. */
:root {
  --ac: var(--color-brand-primary); /* was: #00c896 */
  /* ... */
}
```

---

## CLR-04 — `--color-*` Namespace Reservation

**`--color-*` محجوز حصراً لـ DS-COLOR.**

### القاعدة

```
✅ مسموح:   --color-brand-primary   (في tw_shared.css — Semantic Layer)
✅ مسموح:   --co-accent             (في company.css — Domain Alias، يُشير إلى DS-COLOR)
✅ مسموح:   --msg-accent            (في messages.css — Domain Alias محلي، بدون --color-)
❌ ممنوع:   تعريف --color-* في company.css أو أي page CSS
❌ ممنوع:   إعادة تعريف --color-brand-primary في page CSS
❌ ممنوع:   استخدام --color-* لأي شيء غير لون (مثلاً --color-spacing أو --color-font-size)
```

### الاستثناء الوحيد

DS-FEEDBACK يعرِّف `--fbk-bdr-*` tokens — هذه ليست في `--color-*` namespace. (راجع CLR-21)

---

## CLR-05 — Foundation / Primitive Layer (V1 Palette)

هذا الجدول هو **الـ Phase 1 target** — القيم التي ستُضاف عند تنفيذ Phase 1.
*في Phase 0، هذه قيم موجودة في tw_shared.css بأسماء قديمة (--ac، إلخ).*

### Brand Primitives

| Token | القيمة | الوصف |
|-------|--------|-------|
| `--color-prim-teal` | `#00c896` | أخضر مزرق — اللون الأساسي للمنصة |
| `--color-prim-blue` | `#2563ff` | أزرق — اللون الثانوي |
| `--color-prim-purple` | `#8b5cf6` | بنفسجي — اللون التمييزي (Accent) |

### Background Primitives

| Token | القيمة | الوصف |
|-------|--------|-------|
| `--color-prim-bg-page` | `#070b18` | خلفية الصفحة (كحلي داكن) |
| `--color-prim-bg-s1` | `#0d1426` | سطح أول (أخف قليلاً) |

### Text Primitives

| Token | القيمة | الوصف |
|-------|--------|-------|
| `--color-prim-white` | `#ffffff` | أبيض — نص أساسي |

*ملاحظة:* قيم النص الشفافة (rgba) تُعرَّف مباشرةً في Semantic Layer لأنها تعتمد على Alpha Policy — لا Foundation Primitive لها في V1.

### Status Primitives

| Token | القيمة | الوصف |
|-------|--------|-------|
| `--color-prim-success` | `#34d399` | أخضر — النجاح |
| `--color-prim-warning` | `#fbbf24` | عنبري — التحذير |
| `--color-prim-danger` | `#f87171` | أحمر — الخطر |

### RGB Channels

| Token | القيمة | الوصف |
|-------|--------|-------|
| `--color-prim-teal-rgb` | `0,200,150` | RGB channel لـ teal (يُستخدم للـ alpha variants) |
| `--color-prim-blue-rgb` | `37,99,255` | RGB channel لـ blue |
| `--color-prim-danger-rgb` | `248,113,113` | RGB channel لـ danger |
| `--color-prim-warning-rgb` | `251,191,36` | RGB channel لـ warning |

*ملاحظة:* `--ac-rgb`, `--ac2-rgb`, `--danger-rgb`, `--warning-rgb` ستُصبح Legacy Aliases لهذه الـ RGB Channels في Phase 1.

---

## CLR-06 — Semantic Layer — Brand Tokens

| Token | يُشير إلى | الوصف |
|-------|-----------|-------|
| `--color-brand-primary` | `var(--color-prim-teal)` | اللون الأساسي للمنصة — تواصلنا الأخضر |
| `--color-brand-secondary` | `var(--color-prim-blue)` | اللون الثانوي — الأزرق |
| `--color-brand-accent` | `var(--color-prim-purple)` | اللون التمييزي — البنفسجي |

**الاستخدام:** أزرار CTA، highlight، شريط التقدم، أيقونات النوع.

**تعارض الأسماء الحالية في V1:**
- `--color-brand-accent` (purple `#8b5cf6`) يُذكَر في CLAUDE.md كـ "Accent" لكنه **غير موجود في tw_shared.css** حالياً. يُضاف كـ Foundation + Semantic في Phase 1 عند وجود consumer حقيقي.

---

## CLR-07 — Semantic Layer — Background Tokens

| Token | يُشير إلى | الوصف |
|-------|-----------|-------|
| `--color-bg-page` | `var(--color-prim-bg-page)` | خلفية الصفحة الرئيسية |
| `--color-bg-surface-01` | `var(--color-prim-bg-s1)` | كروت، panels، أسطح أولى |
| `--color-bg-surface-02` | `rgba(255,255,255,.03)` | أسطح ثانوية (glassmorphism base) |
| `--color-bg-surface-03` | `rgba(255,255,255,.06)` | hover states، overlays خفيفة |

---

## CLR-08 — Semantic Layer — Border Tokens

| Token | يُشير إلى | الوصف |
|-------|-----------|-------|
| `--color-border-default` | `rgba(255,255,255,.08)` | الحدود الافتراضية (= `--bdr` الحالي) |
| `--color-border-strong` | `rgba(255,255,255,.16)` | حدود أقوى (focus indicator، separator) |
| `--color-border-focus` | `var(--color-brand-primary)` | حدود focus لحقول الإدخال |

---

## CLR-09 — Semantic Layer — Text Tokens

| Token | يُشير إلى | الوصف |
|-------|-----------|-------|
| `--color-text-primary` | `var(--color-prim-white)` | نص أساسي — `#ffffff` (= `--t1`) |
| `--color-text-secondary` | `rgba(255,255,255,.7)` | نص ثانوي (= `--t2`) |
| `--color-text-tertiary` | `rgba(255,255,255,.4)` | نص ثالثي (= `--t3`) |
| `--color-text-quaternary` | `rgba(255,255,255,.2)` | نص رابعي، متعطّل بصرياً (= `--t4`) |
| `--color-text-placeholder` | `rgba(255,255,255,.28)` | نص placeholder |
| `--color-text-disabled` | `rgba(255,255,255,.20)` | نص حقول معطَّلة (Disabled state) |

**هام — راجع CLR-17:** `--color-text-placeholder` و`--color-text-disabled` **رمزان مستقلان** حتى لو كانت قيمهما متشابهة في V1. سبب الفصل: دلالة مختلفة + يمكن اختلاف القيم في Light Theme أو إصدارات مستقبلية.

---

## CLR-10 — Semantic Layer — Status Tokens

| Token | يُشير إلى | الوصف |
|-------|-----------|-------|
| `--color-status-success` | `var(--color-prim-success)` | النجاح (= `--success`) |
| `--color-status-warning` | `var(--color-prim-warning)` | التحذير (= `--warning`) |
| `--color-status-danger` | `var(--color-prim-danger)` | الخطر / الخطأ (= `--danger`) |
| `--color-status-info` | `var(--color-brand-secondary)` | المعلومات (يُشير إلى blue — V1 فقط) |

**Token Identity ≠ Token Value:** `--color-status-info` و`--color-brand-secondary` كلاهما `#2563ff` في V1 — لكنهما **رمزان مستقلان** (راجع CLR-12). تغيير اللون الثانوي لا يجب أن يُغير لون المعلومات تلقائياً.

---

## CLR-11 — Categorical Color Layer (`--color-categorical-*`)

الـ Categorical Colors مخصصة للتصنيف البصري (skill levels، profession types، data chips) — ليس للحالات (status) ولا للعلامة التجارية (brand).

### القاعدة الجوهرية

```
--color-categorical-* يُعبِّر عن "نوع" أو "فئة" — لا عن "حالة" (جيد/سيئ/تحذير).
```

### V1 Categorical Tokens (الحد الأدنى بوجود consumer حقيقي)

| Token | القيمة المقترحة | Consumer الحالي |
|-------|-----------------|-----------------|
| `--color-categorical-teal` | `#00c896` | Skill type، level chips |
| `--color-categorical-blue` | `#2563ff` | Profession category chips |
| `--color-categorical-purple` | `#8b5cf6` | Expert/Advanced level indicator |
| `--color-categorical-amber` | `#fbbf24` | Intermediate level، timeline |
| `--color-categorical-red` | `#f87171` | Beginner level (visual hierarchy فقط — ليس خطأ) |
| `--color-categorical-green` | `#34d399` | Certified/Verified chip |

**تحذير Token Identity:** كل `--color-categorical-*` token مستقل، حتى لو كانت قيمته نفس `--color-status-warning` أو `--color-brand-primary`. (راجع CLR-12 + CLR-13)

### تعريف V1 في Phase 1

يُضاف في Semantic Layer ضمن قسم Categorical:

```css
/* === Categorical: visual grouping, not status === */
--color-categorical-teal:   var(--color-prim-teal);
--color-categorical-blue:   var(--color-prim-blue);
--color-categorical-purple: var(--color-prim-purple);
--color-categorical-amber:  var(--color-prim-warning); /* same value, separate identity */
--color-categorical-red:    var(--color-prim-danger);  /* same value, separate identity */
--color-categorical-green:  var(--color-prim-success); /* same value, separate identity */
```

---

## CLR-12 — Token Identity ≠ Token Value

**مبدأ أساسي: تمامثل الـ hex لا يعني تمامثل الـ token.**

### المعنى

رمزان مختلفان يمكن أن يحملا نفس القيمة اللونية في V1 — لكنهما يظلان رمزَين مستقلَّين:

```
--color-brand-primary: #00c896
--color-categorical-teal: #00c896
```

← كلاهما نفس اللون. لكن تغيير `--color-brand-primary` لا يُغير `--color-categorical-teal` لأن كل منهما له identity مستقلة.

### لماذا؟

- **Brand Primary** يُعبِّر عن هوية العلامة التجارية
- **Categorical Teal** يُعبِّر عن تصنيف بصري في UI

قد يتغير أحدهما مستقبلاً بدون تغيير الآخر. ربطهما معاً بنفس المتغير يخلط المسؤوليات.

### التطبيق في Phase 1

```css
/* Foundation: كلاهما يرجع لنفس primitive */
--color-prim-teal: #00c896;

/* Semantic: رمزان مستقلان بهوية مختلفة */
--color-brand-primary:      var(--color-prim-teal); /* تُحدَّث لأسباب brand */
--color-categorical-teal:   var(--color-prim-teal); /* تُحدَّث لأسباب data viz */
```

### ممنوعات CLR-12

```
❌ --color-categorical-amber: var(--color-status-warning)  (coupling مباشر — خطأ)
❌ --color-status-info: var(--color-brand-secondary)  (coupling مباشر — قد يُقبل مؤقتاً لكن ليس canonical)
✅ --color-categorical-amber: var(--color-prim-warning)  (كلاهما يرجع للـ primitive)
```

---

## CLR-13 — Semantic ≠ Categorical

**مبدأ أساسي: لون الحالة ≠ لون التصنيف.**

| ما هو | DS-COLOR group | مثال |
|-------|----------------|------|
| "هذا ناجح / خاطئ / تحذير" | Status (`--color-status-*`) | نجاح الحفظ، خطأ API، حذف مخيف |
| "هذا نوع بيانات أ ، نوع ب" | Categorical (`--color-categorical-*`) | مستوى مبتدئ، مستوى خبير، مهنة X |

### الفرق العملي

```
--color-status-warning (amber) → يُستخدم لتحذير المستخدم من شيء مهم
--color-categorical-amber      → يُستخدم لتمييز مستوى "متوسط" في جدول مهارات

✅ مستوى المهارة "متوسط" يُعرَض بـ --color-categorical-amber
❌ مستوى المهارة "متوسط" لا يُعرَض بـ --color-status-warning
    (لأن "متوسط" ليس "تحذيراً" — هو تصنيف بيانات فقط)
```

### قاعدة التحقق

اسأل: "هل هذا اللون يُخبر المستخدم بأن شيئاً يحتاج اهتمامه؟"
- **نعم** → استخدم Status token
- **لا، هو مجرد تمييز بصري لفئة** → استخدم Categorical token

---

## CLR-14 — Domain / Feature Mapping Policy

**DS-COLOR يُحدِّد اللون. Feature / Domain يُحدِّد المعنى.**

DS-COLOR لا يعرف ماذا تعني "مستوى خبير" أو "حالة محقق". Feature هو من يُقرِّر أن `--color-categorical-purple` تُمثِّل مستوى expert في نظام المهارات.

### نمط الـ Mapping

```
DS-COLOR:
  --color-categorical-purple: #8b5cf6   ← لون فقط

Feature (profile-v2.css أو skills.css):
  .skill-level-expert { color: var(--color-categorical-purple); }   ← الربط بالمعنى
```

### القاعدة

- **DS-COLOR** يُعرِّف `--color-categorical-purple` فقط (لون + identity)
- **Feature** يربطه بـ "expert" أو "advanced" أو أي تصنيف domain
- **لا يوجد** `--color-skill-expert` في DS-COLOR — هذا feature-specific alias

### Domain Alias المسموح

```css
/* في static/shared/tw-skills.css أو profile-v2.css: */
--skill-expert:  var(--color-categorical-purple);  ✅ مسموح (Tier 2 Alias)
--skill-adv:     var(--color-categorical-blue);    ✅ مسموح (Tier 2 Alias)
```

---

## CLR-15 — Local Alias Policy (Three Tiers)

### Tier 1 — DS-COLOR Global Tokens (in `tw_shared.css`)

```
المكان:    tw_shared.css فقط
الاسم:    --color-* (namespace محجوز لـ DS-COLOR)
الاستخدام: كل الصفحات والـ feature CSS
```

### Tier 2 — Domain Alias (in feature CSS)

```
المكان:    ملف CSS الخاص بالـ feature (company.css, profile-v2.css, messages.css, إلخ)
الاسم:    --co-*, --sc-*, --msg-* (namespace مخصص للـ domain)
القاعدة:  يجب أن يُشير دائماً إلى DS-COLOR Semantic token (لا قيمة مباشرة)
مثال:     --co-accent: var(--color-brand-secondary);  ✅
          --co-accent: #2563ff;  ❌ (hardcoded value — يُكسر الـ theming)
```

### Tier 3 — Local Implementation Tokens

```
المكان:    feature CSS
الاسم:    لا يبدأ بـ --color-
المحتوى:  أبعاد، مدد، z-index، غير لون
مثال:     --co-modal-radius: 12px;  ✅
          --co-anim-dur: 250ms;     ✅
```

### قاعدة الاستخدام

```
feature CSS:
  color: var(--co-accent);              ✅ يُشير لـ Tier 2 Alias
  color: var(--color-brand-secondary);  ✅ يُشير مباشرة لـ DS-COLOR Semantic
  color: #2563ff;                       ❌ hardcoded — ممنوع في feature CSS الجديد
  color: var(--ac2);                    ⚠️ مقبول مؤقتاً (Legacy Alias) — يُستبدَل عند migration
```

---

## CLR-16 — company.css — Architectural Debt & Migration Intent

### الوضع الحالي

`static/company/company.css` يُعيد تعريف `--ac` و`--ac2`:

```css
/* company.css — الحالة الحالية */
:root {
  --ac:  #2563ff;  /* تبادل: الأزرق يصبح الـ accent الأول */
  --ac2: #00c896;  /* تبادل: الأخضر يصبح الثاني */
}
```

### التصنيف الصحيح

- **ليست مشكلة بصرية (Visual Bug):** اختيار الأزرار الأولية للشركة بالأزرق قد يكون قراراً تصميمياً مقصوداً.
- **مشكلة معمارية:** تعريف page CSS لـ global tokens في `--color-*` namespace أو إعادة تعريف global tokens هو انتهاك لـ CLR-04 وCLR-15.

### Migration Intent (ليس Bug Fix)

**المسار المستهدف في Phase 1+:**

```css
/* company.css — الحالة المستهدفة */
:root {
  --co-accent:  var(--color-brand-secondary);  /* الأزرق لصفحة الشركة */
  --co-accent2: var(--color-brand-primary);    /* الأخضر ثانوي */
}
```

ثم يُستبدَل كل استخدام لـ `--ac` و`--ac2` في `company.css` بـ `--co-accent` و`--co-accent2`.

### القاعدة الحالية

```
❌ لا تُعدِّل company.css كجزء من DS-COLOR Phase 0 أو Phase 1 الأساسي
❌ لا تُصنِّف هذا الوضع كـ "Bug P0" يستدعي إصلاحاً فورياً
✅ وثِّق الأمر كـ Migration Debt ويُنفَّذ في PR مستقل بعد توافر Semantic tokens
```

---

## CLR-17 — Text Hierarchy Contract

### الـ Text Tokens المستقلة

| Token | Alpha | الاستخدام |
|-------|-------|-----------|
| `--color-text-primary` | 100% | عناوين، نصوص رئيسية |
| `--color-text-secondary` | 70% | نصوص فرعية، وصف |
| `--color-text-tertiary` | 40% | meta text، timestamps |
| `--color-text-quaternary` | 20% | نص شبه مخفي |
| `--color-text-placeholder` | 28% | placeholder text في input fields |
| `--color-text-disabled` | 20% | نص حقل معطَّل (Disabled state) |

### سبب الفصل بين Placeholder وDisabled

على الرغم من أن `--color-text-placeholder` و`--color-text-disabled` قد يتشاركان نفس قيمة Alpha في V1 (`.20` – `.28`)، إلا أنهما **رمزان مستقلان** لأن:

1. **دلالة مختلفة:** Placeholder = نص إرشادي مؤقت داخل الحقل الفارغ. Disabled = نص حقل لا يمكن التفاعل معه.
2. **تطبيق مختلف:** Placeholder يُطبَّق عبر `::placeholder` pseudo-element. Disabled يُطبَّق عبر `[disabled]` selector.
3. **قيمة مختلفة محتملة:** في Light theme أو V2، الاثنان يحتاجان قيماً مختلفة.

### ممنوعات CLR-17

```
❌ استخدام --color-text-disabled في ::placeholder selector
❌ استخدام --color-text-placeholder في [disabled] selector
❌ دمج الرمزَين في رمز واحد --color-text-muted
```

---

## CLR-18 — Accessibility Policy

DS-COLOR V1 يستهدف **WCAG 2.1 Level AA** كحد أدنى:

| زوج اللونين | النسبة المطلوبة |
|-------------|----------------|
| نص عادي (< 18pt أو < 14pt bold) على خلفية | 4.5:1 |
| نص كبير (≥ 18pt أو ≥ 14pt bold) على خلفية | 3:1 |
| مكوِّنات UI وحالات focus على خلفية | 3:1 |

### تحذيرات V1

- `--color-text-tertiary` (`rgba(255,255,255,.4)`) قد يقع دون 4.5:1 على بعض الخلفيات — يُستخدم فقط لنصوص غير حرجة (timestamps، meta).
- `--color-text-placeholder` (`rgba(255,255,255,.28)`) مقبول للـ Placeholder (WCAG يُقلِّل متطلبات placeholder).
- أي استخدام لـ DS-COLOR يُخالف AA على نص حرج يحتاج مراجعة في PR مستقل.

### قاعدة التطبيق

أي token جديد يُضاف في Phase 1+ يُرفق بتقرير contrast ratio في PR.

---

## CLR-19 — Alpha Policy

DS-COLOR V1 يُعرِّف Alpha Scale **كتوثيق** لا كـ CSS Variables.

### الـ Scale الرسمي

| الاسم | القيمة | الاستخدام |
|-------|--------|-----------|
| `subtle` | `.06` | خلفيات شفافة جداً |
| `soft` | `.12` | hover، تظليل خفيف |
| `muted` | `.20` | نصوص رابعية، disabled |
| `medium` | `.28` | placeholder، حدود متوسطة |
| `strong` | `.35` | overlays، تأثيرات |
| `overlay` | `.70` | طبقات أمامية، modals خلفية |

### القواعد

1. **DS-COLOR يملك الـ channel** — قيم الـ alpha المُستخدمة مع ألوان DS-COLOR يجب أن تنتمي للـ Scale.
2. **القيم خارج الـ Scale** تحتاج تبريراً موثَّقاً في PR (مثال: `.08` في `--color-border-default` = وسط بين `.06` و`.12`، مقبول بسبب البصري).
3. **الـ Alpha لا تُحوَّل إلى CSS Variables** — لا `--alpha-subtle: .06` — تُستخدم مضمَّنة كـ `rgba(255,255,255,.06)`.
4. **DS-COLOR يُحدِّد الـ channel** — النظام المستهلك (DS-INP / DS-BTN / DS-FEEDBACK) يُقرِّر الـ alpha المناسب من الـ Scale.

### مثال تطبيق صحيح

```css
/* ✅ صحيح: brand primary مع alpha من الـ Scale */
.badge-teal { background: rgba(var(--color-prim-teal-rgb), .12); }   /* soft */

/* ❌ خطأ: alpha عشوائي خارج الـ Scale بدون تبرير */
.badge-teal { background: rgba(var(--color-prim-teal-rgb), .17); }
```

---

## CLR-20 — System Boundaries (DS-INP / DS-BTN)

DS-COLOR يُزوِّد الـ **color channel** فقط. الأنظمة الأخرى تُقرِّر كيفية تطبيقه.

### DS-INP Boundary

```
DS-COLOR يملك:
  --color-text-primary      → لون النص داخل الحقل
  --color-text-placeholder  → لون الـ placeholder
  --color-border-focus      → لون الـ border في Focus state
  --color-text-disabled     → لون النص في Disabled state

DS-INP يملك:
  متى يُطبَّق كل لون (Normal / Focus / Error / Disabled states)
  البنية الدلالية (wrapper → label → input → helper)
  خصائص مثل -webkit-text-fill-color (DS-INP INP-10A)
```

### DS-BTN Boundary

```
DS-COLOR يملك:
  --color-brand-primary      → لون الزر الأساسي
  --color-brand-secondary    → لون الزر الثانوي

DS-BTN يملك:
  حالات الزر (Idle / Loading / Disabled / Success)
  أبعاد وشكل الزر
  semantic type (CTA / Ghost / Danger / إلخ)
```

### القاعدة العامة

```
❌ DS-COLOR لا يُعرِّف: .cta-btn { background: var(--color-brand-primary); }
✅ DS-BTN يُعرِّف هذا في contract
✅ Page CSS يُطبِّقه بتوجيه DS-BTN
```

---

## CLR-21 — DS-FEEDBACK Boundary Clarification

### تحذير مهم: `--fbk-bdr-*` ليست DS-COLOR canonical

`tw_shared.css` يحتوي:
```css
--fbk-bdr-success: rgba(var(--ac-rgb), .3);
--fbk-bdr-error:   rgba(var(--danger-rgb), .3);
--fbk-bdr-warning: rgba(var(--warning-rgb), .3);
--fbk-bdr-info:    rgba(var(--ac2-rgb), .3);
```

**هذه DS-FEEDBACK semantic tokens، لا DS-COLOR canonical tokens:**
- `--fbk-bdr-*` تقع في `--fbk-*` namespace — ملك DS-FEEDBACK
- DS-FEEDBACK يعرِّفها ويُشير إلى DS-COLOR color channels
- تغييرها يتطلب PR يمس DS-FEEDBACK، لا DS-COLOR

### العلاقة الصحيحة

```
DS-COLOR:
  --color-status-success → #34d399  (V1 Phase 1)
  --color-prim-teal-rgb  → 0,200,150

DS-FEEDBACK (يستهلك DS-COLOR):
  --fbk-bdr-success: rgba(var(--color-prim-teal-rgb), .3)
```

---

## CLR-22 — Glow & Shadow Boundary

**DS-COLOR يُزوِّد الـ color channel فقط للـ glows وshadows. تعريفها يقع في الـ feature CSS.**

```css
/* ✅ صحيح: feature CSS تُعرِّف الـ glow باستخدام DS-COLOR channel */
.cta:hover {
  box-shadow: 0 0 20px rgba(var(--color-prim-teal-rgb), .35);  /* strong alpha */
}

/* ❌ خطأ: DS-COLOR يُعرِّف glow effect كاملاً */
/* DS-COLOR لا يُعرِّف .cta-glow أو --color-brand-glow */
```

**DS-Shadow (مستقبلي):** عند توثيق نظام Shadow مستقل، هو من سيُقرِّر كيفية استخدام DS-COLOR channels في shadows/glows.

---

## CLR-23 — Theme Readiness (Dark-Only V1)

### Dark Only في V1

DS-COLOR V1 هو **Dark Theme فقط**. لا Light Theme في V1.

### لماذا التصميم الحالي يُيسِّر Light Theme مستقبلاً

لأن Feature CSS تُشير إلى **Semantic tokens** لا Foundation tokens:
```css
/* feature CSS تُشير لـ Semantic — لا لقيمة مباشرة */
body { background: var(--color-bg-page); }
```

عند إضافة Light Theme في المستقبل:
```css
/* يكفي تعريف Foundation tokens مرة أخرى في [data-theme="light"] */
[data-theme="light"] {
  --color-prim-bg-page: #f8fafc;
  /* ... */
}
```

لا يحتاج تغيير feature CSS لأنها تستخدم Semantic tokens بالفعل.

### شرط V1

لا تُعرِّف `@media (prefers-color-scheme: dark)` أو `[data-theme="dark"]` في Phase 1. الـ theme الوحيد هو Dark Default.

---

## CLR-24 — Flutter Readiness

DS-COLOR V1 يُوثِّق **Conceptual Mapping فقط** — لا JSON، لا build tooling.

### الـ Naming Convention المشترك

| DS-COLOR Web Token | الاسم المفاهيمي (Flutter) |
|-------------------|--------------------------|
| `--color-brand-primary` | `AppColors.brandPrimary` |
| `--color-brand-secondary` | `AppColors.brandSecondary` |
| `--color-status-success` | `AppColors.statusSuccess` |
| `--color-text-primary` | `AppColors.textPrimary` |
| `--color-categorical-teal` | `AppColors.categoricalTeal` |

### القاعدة

- Naming يتبع pattern مشترك: `color-{category}-{role}` في CSS → `{Category}.{role}` في Flutter.
- **لا code generation، لا JSON export** في V1.
- عند بناء التطبيق الفعلي، تُنشأ `app_colors.dart` بنفس المنطق.

---

## CLR-25 — Pending Color Principle

### المعنى

"Pending" في السياق المرئي (حالة انتظار في applicant pipeline مثلاً) دلالتها **محايدة / رمادية** — ليست نجاحاً ولا خطأً.

### القاعدة

```
حالة Pending → لا تستخدم Status tokens (success / warning / danger / info)
              → استخدم Categorical gray أو Text tertiary

✅ .status-badge--pending { color: var(--color-text-tertiary); }
❌ .status-badge--pending { color: var(--color-status-warning); }
    (pending ليست تحذيراً — هي مجرد انتظار)
```

### التحقق

قبل تعيين لون لحالة "pending"، تحقق من المعنى الحرفي في سياق الـ domain. بعض الـ "pending" في تواصلنا قد تكون توجيهاً للمستخدم لإكمال خطوة — عندها يكون `--color-status-info` مناسباً. الافتراضي: محايد/رمادي.

---

## CLR-26 — Local Color Promotion Criteria

بعض الألوان تظهر محلياً (في ملف CSS واحد) قبل أن تصبح globally useful.

### مثال: Cyan في `messages.css`

الـ cyan (`--ac3: #00b8c4` في `messages.css`) هو لون محلي حالياً.

**يبقى محلياً حتى يتحقق أحد هذه الشروط:**
1. يُستخدم في **3 surfaces مستقلة** (messages + profile + company + إلخ)
2. له **معنى categorical مشترك** عبر الـ features (لا feature-specific)
3. يُطلب صراحةً من المستخدم ترقيته

**إذا تحقق شرط، يُضاف كـ:**
```css
/* tw_shared.css — Section 2 Semantic */
--color-categorical-cyan: #00b8c4;
```

**قبل ذلك:**
```css
/* messages.css — يبقى محلياً */
--msg-accent3: #00b8c4;  /* Tier 3 — لا يُشير لـ DS-COLOR categorical */
```

---

## CLR-27 — Migration ≠ Redesign

**مبدأ جوهري:** استبدال قيمة hardcoded بـ token لا يُغير اللون المرئي.

```
Migration:
  color: #00c896  →  color: var(--color-brand-primary)
  النتيجة المرئية: لا تغيير

Redesign:
  color: #00c896  →  color: #00b386
  النتيجة المرئية: لون أغمق

DS-COLOR Phase 1 = Migration فقط.
أي Redesign (تغيير قيمة اللون نفسها) يحتاج:
  1. موافقة تصميمية صريحة
  2. PR مستقل موثَّق
  3. لا يُدمَج مع migration PR
```

### القاعدة العملية

```
Phase 1 يُسمح:   hex → var(--color-*)        بدون تغيير القيمة المرئية
Phase 1 ممنوع:   تغيير #00c896 إلى #00b386  حتى لو "أفضل"
```

---

## CLR-28 — V1 Scope Rule (No Token Without Real Consumer)

**لا token بدون consumer حقيقي في V1.**

### ما يعني

```
✅ --color-brand-primary موجود: consumer = كل الأزرار الأساسية، الشريط العلوي
✅ --color-categorical-purple موجود: consumer = Expert level chips في profile
❌ --color-brand-quaternary: لا يوجد له consumer حالي — لا يُضاف في V1
❌ --color-categorical-pink: لا يوجد له consumer حالي — يُؤجَّل لـ V2
```

### شرط إضافة Token جديد في Phase 1

1. وُجد استخدام فعلي في الكود الحالي (غير موثَّق كـ token بعد)
2. أو: طُلب feature جديد يحتاجه بشكل واضح
3. **لا "قد نحتاجه مستقبلاً"** — هذا V2+ (CLR-29)

---

## CLR-29 — Deferred to V2+

الأنظمة التالية خارج نطاق DS-COLOR V1:

| البند | السبب |
|-------|-------|
| Light Theme | لا consumer حالي — dark-only في V1 |
| `[data-theme]` implementation | يتبع Light Theme |
| Color tokens للـ animations / transitions | لا نظام animation رسمي بعد |
| Gradient system | لا pattern موحَّد حالياً |
| Semantic color per user-type (emp/co/edu تثيم) | لا قرار تصميمي بعد |
| Dark/Light semantic split (--color-*-dark / --color-*-light) | يتبع Light Theme |
| JSON export للـ Flutter | يتبع Flutter implementation |
| CSS Build pipeline | لا bundler — F7 |
| `--color-categorical-pink` و`--color-categorical-cyan` (global) | لا consumer مشترك بعد |
| DS-Shadow system | يُبنى بـ PR مستقل |

---

## CLR-30 — Must-Have V1

قائمة البنود الإلزامية التي يجب أن تُكتمَل في Phase 1:

- [ ] إضافة Foundation / Primitive tokens إلى `tw_shared.css` (Section 1)
- [ ] إضافة Semantic tokens: Brand, Background, Border, Text, Status, Categorical (Section 2)
- [ ] إضافة Legacy Aliases لكل tokens الحالية: `--ac`, `--ac2`, `--bg`, `--bg2`, `--bdr`, `--t1`–`--t4`, `--danger`, `--warning`, `--success`, `--ac-rgb`, `--danger-rgb`, `--warning-rgb`, `--ac2-rgb` (Section 3)
- [ ] التحقق من وجود consumer حقيقي لكل Categorical token قبل إضافته
- [ ] التحقق من أن `--color-text-placeholder` و`--color-text-disabled` موثَّقان كـ tokens مستقلة
- [ ] عدم تغيير أي قيمة لونية مرئية (Migration Only — CLR-27)
- [ ] توثيق Phase 1 في ARCHITECTURE.md
- [ ] تحديث SYSTEMS_INDEX.md بعد Phase 1
- [ ] تحديث Changelog هذا الملف

---

## CLR-31 — Legacy Aliases (Phase 1 → Phase 4)

| Legacy Alias | الـ Semantic Target | الحالة |
|--------------|---------------------|--------|
| `--ac` | `var(--color-brand-primary)` | يُضاف في Phase 1 |
| `--ac2` | `var(--color-brand-secondary)` | يُضاف في Phase 1 |
| `--ac-rgb` | `var(--color-prim-teal-rgb)` | يُضاف في Phase 1 |
| `--bg` | `var(--color-bg-page)` | يُضاف في Phase 1 |
| `--bg2` | `var(--color-bg-surface-01)` | يُضاف في Phase 1 |
| `--bdr` | `var(--color-border-default)` | يُضاف في Phase 1 |
| `--t1` | `var(--color-text-primary)` | يُضاف في Phase 1 |
| `--t2` | `var(--color-text-secondary)` | يُضاف في Phase 1 |
| `--t3` | `var(--color-text-tertiary)` | يُضاف في Phase 1 |
| `--t4` | `var(--color-text-quaternary)` | يُضاف في Phase 1 |
| `--danger` | `var(--color-status-danger)` | يُضاف في Phase 1 |
| `--warning` | `var(--color-status-warning)` | يُضاف في Phase 1 |
| `--success` | `var(--color-status-success)` | يُضاف في Phase 1 |
| `--danger-rgb` | `var(--color-prim-danger-rgb)` | يُضاف في Phase 1 |
| `--warning-rgb` | `var(--color-prim-warning-rgb)` | يُضاف في Phase 1 |
| `--ac2-rgb` | `var(--color-prim-blue-rgb)` | يُضاف في Phase 1 |

### دورة الحياة

```
Phase 0: توثيق فقط — لا تغيير
Phase 1: إضافة Foundation + Semantic + Legacy Aliases في tw_shared.css
Phase 2: ترحيل page CSS من --ac/--ac2 إلى Semantic tokens
Phase 3: التحقق من zero consumers للـ Legacy Aliases
Phase 4: حذف Legacy Aliases من tw_shared.css
```

---

## CLR-32 — Forbidden Patterns

```
❌ تعريف --color-* في أي ملف خلاف tw_shared.css
❌ إعادة تعريف --color-* token موجود في page CSS (override)
❌ استخدام Foundation tokens مباشرةً في feature CSS (--color-prim-teal في .btn)
❌ دمج --color-text-placeholder و--color-text-disabled في رمز واحد
❌ ربط --color-categorical-amber: var(--color-status-warning) — coupling مباشر بين Semantic وCategorical
❌ تغيير أي قيمة لونية مرئية في Phase 1 (Migration ≠ Redesign — CLR-27)
❌ إضافة token بدون consumer حقيقي (CLR-28)
❌ استخدام Alpha خارج الـ Scale بدون تبرير موثَّق (CLR-19)
❌ الافتراض بأن --fbk-bdr-* هي DS-COLOR canonical tokens (CLR-21)
❌ إضافة Light Theme في Phase 1 (CLR-23 — مؤجَّل لـ V2)
❌ تعديل company.css من داخل DS-COLOR Phase 1 (CLR-16 — Migration Debt منفصل)
❌ استخدام --color-status-warning لتمثيل مستوى "متوسط" في المهارات (CLR-13)
❌ استبدال --color-brand-primary بـ --color-categorical-teal أو العكس (CLR-12)
❌ تعريف --color-categorical-* بدون صلة لـ Foundation primitive (CLR-11)
❌ إضافة DS-COLOR Runtime قبل موافقة صريحة بتنفيذ Phase 1
❌ تعريف alpha scale كـ CSS Variables: --alpha-subtle: .06 (CLR-19)
❌ ترقية لون محلي (cyan) إلى categorical بدون استيفاء Promotion Criteria (CLR-25)
❌ دمج Migration PR مع Redesign PR (CLR-27)
```

---

## CLR-33 — Changelog

| التاريخ | التغيير |
|---------|---------|
| 2026-07-26 | Phase 0 — Document created. DS-COLOR V1 Architecture & Documentation Foundation. 33 sections (CLR-00 → CLR-32). No runtime changes. SYSTEMS_INDEX.md §50 added. ARCHITECTURE_FOUNDATION.md F35 + F31 row added. DESIGN_SYSTEM.md updated. CLAUDE.md DS-COLOR routing rule added. |
