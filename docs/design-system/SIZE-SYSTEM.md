# Size System V1 (DS-SIZE)

> النظام الرسمي الوحيد لأحجام الواجهة في تواصلنا: أحجام الخط، الزوايا (border-radius)، المسافات (padding / margin / gap)، أحجام الأيقونات، وارتفاعات العناصر التفاعلية.
>
> **القاعدة العليا:** `ARCHITECTURE_FOUNDATION.md` → F36.
> **Runtime Source of Truth:** `tw_shared.css` → قسم `1b. DS-SIZE` (بعد DS-COLOR مباشرة).
> **قوانين الـ AI:** `docs/rules/ds-size.md`.
> **المرجع:** تقرير المرحلة A (جرد 75 ملف CSS/HTML/JS — PR-5 / المرحلة A) + القرارات المعتمدة من صاحب المشروع.

---

## SIZE-00 — Routing Protocol

| إذا كنت… | اذهب إلى |
|----------|----------|
| تكتب `font-size` | SIZE-02 |
| تكتب `border-radius` | SIZE-03 (+ `--radius-control` للأزرار والحقول) |
| تكتب `padding` / `margin` / `gap` | SIZE-04 |
| تحدد حجم أيقونة (`width`/`height` لـ svg) | SIZE-06 |
| تحدد ارتفاع زر / زر أيقونة / touch target | SIZE-06 |
| تنقل قيمة خام موجودة إلى token | SIZE-05 (تصنيف الفرق) ثم SIZE-07 (tiers) |
| تلمس `.sc-actions` / `.sc-btn` أو post-comments | SIZE-08 (استثناءات مجمّدة) — **لا تلمس** |
| القيمة ما إلها token مطابق | SIZE-09 (قيمة محلية موثقة) — لا تخترع token |
| لون | ليس DS-SIZE → DS-COLOR (`COLOR-SYSTEM.md` CLR-00) |

---

## SIZE-01 — Scope & Ownership

**DS-SIZE يملك:** القيم والأسماء لـ `--size-*` و `--radius-*` و `--space-*`.
**DS-BTN / DS-INP / DS-OVL يملكون:** أي token يُستعمل لأي عنصر (مثلاً: الزر يستعمل `--radius-control`).
**DS-COLOR:** منفصل تماماً — DS-SIZE لا يعرّف ألواناً، و DS-COLOR لا يعرّف أبعاداً.

### Namespaces المحجوزة

```
--size-*    أحجام الخط + الأيقونات + ارتفاعات العناصر + touch target
--radius-*  الزوايا
--space-*   المسافات
```

تُعرَّف **فقط** في `tw_shared.css`. أي ملف CSS/HTML/JS آخر ممنوع يعرّفها أو يعيد تعريفها (F36).

### الأساس

- rem على أساس 16px. ما في صفحة بتغيّر حجم خط الـ root.
- **Phase 1 (هذا الـ PR):** تعريف الـ tokens فقط. ما في selector بيستعملها، وما في أي تغيير بصري.

### صفحات ما بتحمّل `tw_shared.css`

`home-v2.html` · `job-detail.html` · `landing.html` · `appointments.html` · `appointment-room.html`.
هاي الصفحات ما بتشوف الـ tokens لحد ما ينضاف إلها `tw_shared.css` بـ PR منفصل مع فحص بصري (FUTURE_ROADMAP). ممنوع تنسخ الـ tokens لجوّاها.

---

## SIZE-02 — Font Size Scale

| Token | القيمة | px | القيم الحالية اللي بتروح له (الفرق بـ px → التصنيف SIZE-05) |
|-------|--------|----|-----------------------------------------------------------|
| `--size-font-3xs` | .6rem | 9.6 | .6rem مطابق · .62 (−.32) · .58 · .57 · .61 · .59 · 10px — تحت البكسل · **.55 (+.8) · .56 (+.64) · .54 (+.96) · 9px (+.6) — مرئي** |
| `--size-font-2xs` | .65rem | 10.4 | .65 مطابق · .68 (−.48) · .66 · .67 · .63 · .64 — تحت البكسل |
| `--size-font-xs` | .72rem | 11.52 | .72 مطابق · .75 (−.48) · .7 · .74 · .73 · .71 · .69 · 12px (−.48) — تحت البكسل · **11px (+.52) — مرئي** |
| `--size-font-sm` | .78rem | 12.48 | .78 مطابق · .76 · .77 · .79 — تحت البكسل |
| `--size-font-md` | .82rem | 13.12 | .82 مطابق · .8 · 13px · .85 (−.48) · .84 · .83 — تحت البكسل · **.86 (−.64) — مرئي** |
| `--size-font-lg` | .9rem | 14.4 | .9 مطابق · .88 · 14px · .92 — تحت البكسل |
| `--size-font-xl` | .95rem | 15.2 | .95 مطابق · 15px — تحت البكسل (قرار 1: token منفصل) |
| `--size-font-2xl` | 1rem | 16 | 1rem · 16px مطابق · **1.05 (−.8) · 17px (−1) — مرئي** |
| `--size-font-3xl` | 1.2rem | 19.2 | 1.2 مطابق · **1.1 (+1.6) · 18px (+1.2) · 20px · 1.15 · 1.25 — مرئي** |
| `--size-font-4xl` | 1.4rem | 22.4 | 1.4 مطابق · **1.3 (+1.6) · 24px · 1.5 · 1.35 — مرئي** |
| `--size-font-5xl` | 1.6rem | 25.6 | 1.6 مطابق |
| `--size-font-display` | 2rem | 32 | 2rem مطابق |

جرد المرحلة A: 930 استعمال، 79 قيمة → 12 token. 396 مطابق · 434 تحت البكسل · 67 مرئي.

**قيم محلية (SIZE-09):** أحجام emoji وأيقونات الحالات الفاضية (2.2–3.5rem، 40px، 48px) · `clamp()` بـ landing · .5rem · .52rem · .42rem · .7em · 8px.

---

## SIZE-03 — Radius Scale

| Token | القيمة | القيم الحالية اللي بتروح له |
|-------|--------|---------------------------|
| `--radius-2xs` | 4px | 4px مطابق · **2px · 5px · 3px · 1px — مرئي** |
| `--radius-xs` | 6px | 6px مطابق · **7px (−1) — مرئي** |
| `--radius-sm` | 8px | 8px مطابق · **9px (−1) — مرئي** (منها `.sc-btn` المجمّد — SIZE-08) |
| `--radius-md` | 10px | 10px مطابق · **11px — مرئي** |
| `--radius-lg` | 12px | 12px مطابق · **13px — مرئي** |
| `--radius-xl` | 14px | 14px مطابق |
| `--radius-2xl` | 16px | 16px مطابق · **18px (−2) · 17px — مرئي** |
| `--radius-3xl` | 20px | 20px مطابق · **22px · 24px (−4) — مرئي** |
| `--radius-pill` | 999px | 999px مطابق · 99px · 50px — نفس الشكل (مطابق بصرياً) |
| `--radius-circle` | 50% | 50% مطابق |

### `--radius-control` (قرار 3)

```css
--radius-control: var(--radius-md);  /* 10px */
```

Role alias للأزرار والحقول (BTN-02 "صغير وموحَّد"). الحالي: `.tw-btn` 10 (مطابق) · `.tw-ab` 8 · `.sc-btn` 9 (مجمّد) · 12 بأماكن ثانية — نقل 8/9/12 إليه = **مرئي** → redesign معلن.

جرد المرحلة A: 647 استعمال، 44 قيمة → 10 tokens. 389 مطابق · 97 مرئي.

**قيم محلية (SIZE-09):** القيم المركّبة (`20px 20px 0 0`، حوالي 40 استعمال) تبقى محلية لحد ما تتحوّل لصيغة tokens لكل زاوية (`var(--radius-3xl) var(--radius-3xl) 0 0`) — وهاد مطابق إذا القيم نفسها بالسلّم.

---

## SIZE-04 — Spacing Scale

| Token | القيمة | المطابق | قيم قريبة (تبقى محلية — قرار 5) |
|-------|--------|---------|-------------------------------|
| `--space-1` | 2px | 2px | 3px |
| `--space-2` | 4px | 4px | 5px |
| `--space-3` | 6px | 6px | 7px |
| `--space-4` | 8px | 8px | 9px |
| `--space-5` | 10px | 10px | 11px |
| `--space-6` | 12px | 12px | 13px |
| `--space-7` | 14px | 14px | 15px |
| `--space-8` | 16px | 16px | — |
| `--space-9` | 18px | 18px | — |
| `--space-10` | 20px | 20px | 22px |
| `--space-11` | 24px | 24px | 26px · 28px |
| `--space-12` | 32px | 32px | 30px · 36px |
| `--space-13` | 40px | 40px | 42px · 44px |

**قرار 5:** المسافات الفردية (3/5/7/9/11/13px) **ما بتصير tokens**. بتبقى قيم محلية لحد redesign معلن لكل صفحة. كمان 15/22/26/28/30/36/42/44 بتبقى محلية — نقلها لأقرب token مرئي.

جرد المرحلة A: 2246 قيمة. 1696 مطابق · 463 مرئي (أكبر مخاطرة — لهيك المسافات migration للمطابق فقط).

**قيم محلية (SIZE-09):** 1px · 0.5px · 1.5px (ضبط محاذاة) · أقسام landing الكبيرة (48/50/60/72/80/90/100px و5%).

---

## SIZE-05 — Visual Difference Classification & Migration Rule

### التصنيف (يُحسب بالـ px على أساس 16px)

| التصنيف | التعريف | مثال |
|---------|---------|------|
| **مطابق** | نفس القيمة بالضبط (أو نفس الشكل: 99px/50px pill → 999px) | `.82rem` → `var(--size-font-md)` |
| **تحت البكسل** | الفرق أقل من 0.5px | `.85rem` (13.6) → `--size-font-md` (13.12) = −.48 |
| **مرئي** | الفرق 0.5px أو أكثر | `11px` → `--size-font-xs` (11.52) = +.52 |

### القاعدة

> **Migration = استبدال المطابق وتحت البكسل فقط.**
> **المرئي ما بيدخل migration — بيروح لـ PR redesign معلن** لكل صفحة (مع screenshots وموافقة صريحة)، على نفس مبدأ CLR-27 (Migration ≠ Redesign).

- PR الـ migration لازم يذكر الصفحة/الملف، وعدد القيم المطابقة وتحت البكسل اللي انبدلت، ويأكد إنه ما في قيمة مرئية انبدلت.
- القيمة المرئية بتضل خام بمكانها لحد الـ redesign، ومنعتبرها قيمة محلية مؤقتة (SIZE-07 Tier 3).

### استثناء معتمد مسبقاً — أيقونات 13px (قرار 2)

أيقونات 13px (23 استعمال) **تندمج بـ `--size-icon-sm` = 14px** عند migration الصفحة، رغم إنه الفرق (+1px) مرئي. هاد قرار معتمد من صاحب المشروع — لازم ينذكر بوصف PR الـ migration كتغيير مرئي معتمد بقرار 2. ما في استثناء ثاني غيره.

---

## SIZE-06 — Icons & Interactive Control Heights

### أحجام الأيقونات (الرسمة نفسها)

| Token | القيمة | المطابق | قيم بتروح له |
|-------|--------|---------|-------------|
| `--size-icon-xs` | 12px | 12 | **10 · 11 — مرئي** |
| `--size-icon-sm` | 14px | 14 (منها `.sc-btn .ico-sm` المجمّد) | 13px — قرار 2 (SIZE-05) |
| `--size-icon-md` | 16px | 16 | **15 — مرئي** |
| `--size-icon-lg` | 18px | 18 | **19 (`app-header`) — مرئي** |
| `--size-icon-xl` | 20px | 20 | — |
| `--size-icon-2xl` | 22px | 22 | **24 — مرئي** |

قيم محلية: 28px (`index.css` و notifications) · 1.1em.

### أزرار الأيقونة (مربعة)

| Token | القيمة | المستهلكين الحاليين (مطابق) |
|-------|--------|---------------------------|
| `--size-control-icon-xs` | 28px | `.sc-item-btn` · `.sc-exp-menu-btn` · `.job-mgmt-btn` (h) |
| `--size-control-icon-sm` | 30px | `.ep-close` · `.sc-modal-close` · `.sc-fl-close` · `.modal-head-close` · `.cv-edit-btn` · `.co-ic-btn` |
| `--size-control-icon-md` | 32px | `.sc-hicon` (app-header و profile-v2) · `.sc-home-btn` (profile-v2 و company) · `.sc-qr-close` · `.co-csc-toggle` |
| `--size-control-icon-lg` | 40px | `app-header.css .sc-home-btn` |

### أزرار الهيدر — بدون قرار (قرار 4)

نفس الكلاس `.sc-home-btn` = 32 بالبروفايل والشركة، 40 بالهيدر المشترك، 34 بالرسائل؛ و `.hdr-back` بالمواعيد 34/36. **غير موحّدة.** الميل لـ 40، بس التوحيد تغيير بصري مقصود → PR بصري منفصل مع screenshots (FUTURE_ROADMAP). لحد هداك الـ PR: كل زر بيستعمل الـ token المطابق لقيمته الحالية فقط، والقيم 34/36 بتبقى محلية.

### أزرار وحقول فيها نص

| Token | القيمة | المطابق | ملاحظة |
|-------|--------|---------|--------|
| `--size-control-sm` | 28px | `.job-mgmt-btn` | 30px (`.co-ic-btn` و `.job-manage-btn`) = مرئي |
| `--size-control-md` | 40px | `.sc-sel-trg` (min-height) | 38px (`.msg-send-btn` و `.notif-tab`) و 42px (`.modal-foot .mbtn`) = مرئي |
| `--size-touch-min` | 44px | `.pass-eye` (min 44) · `.send-btn` · `--ah-h` | |

- **`.sc-btn` بـ 27px مجمّد** — برّا السلّم (SIZE-08).
- **BTN-04 MD = 36px ما إله أي مستهلك فعلي كارتفاع زر** (36 موجود بس كارتفاع لوغو). لهيك **ما في token لـ 36** (نفس مبدأ CLR-28: no token without real consumer).
### أفاتار / لوغو (DS-IMAGE — PR-7b)

| Token | القيمة | المالك |
|-------|--------|--------|
| `--size-avatar-md` | 40px | DS-IMAGE IMG-02 (`.tw-ava--md`) |
| `--size-avatar-lg` | 48px | DS-IMAGE IMG-02 (`.tw-ava--lg`) |
| `--size-avatar-xl` | 88px | DS-IMAGE IMG-02 (`.tw-ava--xl`) |
| `--size-avatar-2xl` | 106px | DS-IMAGE IMG-02 (`.tw-ava--2xl`) |

- المستهلك الوحيد هلّق `.tw-ava` بـ `tw_shared.css` (بدون صفحة). 22 / 32 (post-comments) مجمّدة (SIZE-08). توحيد 38/42/44/84–94 = مرئي → DS-IMAGE المرحلة C. التفاصيل: `docs/design-system/IMAGE-SYSTEM.md`.

- **الحقول ما إلها `height` صريح** — ارتفاعها من الـ padding والـ line-height (`.ep-input` / `.sc-sel-trg`: `10px 13px` / `.84rem` · `.tw-input`: `10px 12px` / `.82rem` · company: `9px 12px` / `.78rem` · appointments: `10px 14px` / `14px`). التوحيد بيصير عبر tokens الـ padding والخط — **ممنوع فرض `height`** على الحقول.

---

## SIZE-07 — Tier Policy

| Tier | المكان | الشكل | مثال |
|------|--------|-------|------|
| **T1 — عالمي** | `tw_shared.css` فقط | `--size-*` / `--radius-*` / `--space-*` بقيمة خام | `--radius-md: 10px;` |
| **T2 — alias محلي** | ملف CSS الصفحة/الـ feature | اسم domain بيشاور على T1 — **بدون قيمة خام** | `--r-sm: var(--radius-md);` ✅ · `--r-sm: 10px;` ❌ (بعد migration الملف) |
| **T3 — قيمة محلية موثقة** | ملف CSS الصفحة | قيمة خام ما إلها token مطابق (مرئي، شاذ، أو مجمّد) — بتنذكر بالـ PR أو بـ SIZE-08/09 | `--flt: 46px;` (home-v2) |

### Tokens محلية موجودة اليوم (تتحوّل لـ T2 عند migration ملفها)

| الملف | الحالي | يصير | ملاحظة |
|-------|--------|------|--------|
| `company.css` | `--r-sm: 10px` | `var(--radius-md)` | تشابه أسماء مربك (`--r-sm` ≠ `--radius-sm`) — الاسم المحلي يبقى، القيمة بتشاور على T1 |
| `company.css` | `--r-md: 14px` | `var(--radius-xl)` | |
| `company.css` | `--r-lg: 20px` | `var(--radius-3xl)` | |
| appointments* | `--r: 14px` | `var(--radius-xl)` | الصفحة ما بتحمّل `tw_shared.css` بعد — بعد PR التحميل فقط |
| `app-header.css` | `--ah-h: 44px` | `var(--size-touch-min)` | |
| `home-v2.css` | `--flt: 46px` | T3 يبقى | ما في token مطابق |

**ممنوع:** اسم محلي يبدأ بـ `--size-` / `--radius-` / `--space-` (هاي namespaces محجوزة لـ T1).

---

## SIZE-08 — Frozen Exceptions (بالاسم)

هاي القيم **ممنوع تنلمس** بأي migration لـ DS-SIZE. تغييرها فقط بـ PR مخصّص لإلها بالاسم.

### 1) `.sc-actions` / `.sc-btn` — Profile V2 action buttons

المصدر: `docs/rules/profile-v2.md → Profile V2 Action Buttons Rule`.

| القيمة المجمّدة | علاقتها بالسلّم |
|----------------|----------------|
| `.sc-btn` height 27px | برّا السلّم |
| `.sc-btn` border-radius 9px | برّا السلّم (أقرب: `--radius-sm` 8 — مرئي) |
| `.sc-btn` font-size 11px | برّا السلّم (أقرب: `--size-font-xs` — مرئي +.52) |
| `.sc-btn` gap 5px | قيمة فردية (قرار 5) |
| `.sc-btn-*` padding 0 18px | 18 = `--space-9` مطابق — **ومع هيك مجمّد، ما بيتبدّل** |
| `.sc-actions` gap 10px | 10 = `--space-5` مطابق — **مجمّد، ما بيتبدّل** |
| `.sc-actions` padding 6px 20px 13px | 13 فردية |
| `.sc-btn .ico-sm` 14×14 | 14 = `--size-icon-sm` مطابق — **مجمّد، ما بيتبدّل** |

حتى القيم المطابقة جوّا هاد البلوك ما بتتبدّل بـ tokens — البلوك كله مجمّد كوحدة.

### 2) post-comments

المصدر: `docs/rules/post-comments.md`.

| القيمة المجمّدة | ملاحظة |
|----------------|--------|
| `.pc-cmt-visual-reply` `margin-inline-start: 28px` | برّا سلّم المسافات |
| avatar التعليق 32px | |
| avatar قائمة الـ mention 22px | |
| قائمة التعليقات `max-height: 280px` | |

---

## SIZE-09 — Local Values (T3) — موثقة

قيم بتضل خام بملفها بدون ما تكون مخالفة:

1. **القيم المرئية** (SIZE-05) لحد redesign معلن.
2. **المسافات الفردية** 3/5/7/9/11/13px (قرار 5) + 15/22/26/28/30/36/42/44px.
3. **الشاذ:** emoji / empty-state (2.2–3.5rem، 40/48px)، `clamp()`، 1px/0.5px/1.5px، مسافات landing الكبيرة، 28px للأيقونات، 1.1em.
4. **الزوايا المركّبة** لحد ما تنكتب بـ tokens لكل زاوية.
5. **الاستثناءات المجمّدة** (SIZE-08).
6. **أزرار الهيدر** 34/36px (قرار 4).

قيمة جديدة برّا السلّم بكود جديد = لازم سبب بوصف الـ PR. الافتراضي لكود جديد: token من السلّم.

---

## SIZE-10 — Forbidden

```
❌ تعريف أو إعادة تعريف --size-* / --radius-* / --space-* برّا tw_shared.css
❌ نسخ tokens الـ DS-SIZE لصفحة ما بتحمّل tw_shared.css (الحل: PR تحميل tw_shared.css)
❌ T2 alias بقيمة خام بدل var(--…) بعد migration ملفه
❌ استبدال قيمة مرئية بـ token جوّا PR migration (المرئي = redesign معلن)
❌ لمس .sc-actions / .sc-btn أو قيم post-comments المجمّدة ضمن migration
❌ tokens للمسافات الفردية (3/5/7/9/11/13px)
❌ token لارتفاع 36px (MD بـ BTN-04 بدون مستهلك)
❌ فرض height على حقول الإدخال
❌ توحيد أزرار الهيدر (32/34/40) بدون PR بصري منفصل
❌ تغيير قيمة أي DS-SIZE token بدون PR DS-SIZE معلن
❌ نظام أحجام موازٍ (ملف tokens ثاني مثل tw-ui-tokens.css)
```

---

## SIZE-11 — Phases

| المرحلة | المحتوى | الحالة |
|---------|---------|--------|
| A | جرد + سلالم مقترحة + قرارات | ✅ (تقرير PR-5 / المرحلة A) |
| B (Phase 1) | توثيق + tokens بـ `tw_shared.css` — بدون تغيير بصري وبدون migration | ✅ هذا الـ PR |
| Phase 2 | migration صفحة صفحة — المطابق وتحت البكسل فقط (+ استثناء قرار 2) — موافقة صريحة لكل صفحة | 🔜 FUTURE_ROADMAP |
| — | توحيد أزرار الهيدر (PR بصري منفصل مع screenshots) | 🔜 FUTURE_ROADMAP |
| — | إضافة `tw_shared.css` للصفحات الخمس (PR منفصل مع فحص بصري) | 🔜 FUTURE_ROADMAP |
| — | redesign معلن لكل صفحة للقيم المرئية | عند الطلب |

---

## SIZE-12 — Changelog

| التاريخ | الـ PR | التغيير |
|---------|-------|---------|
| 2026-10-06 | PR-7b | `--size-avatar-md/lg/xl/2xl` (40/48/88/106) لـ DS-IMAGE (SIZE-06) |
| 2026-10-06 | PR-5 / المرحلة B | إنشاء النظام: SIZE-00 → SIZE-12 · قسم `1b. DS-SIZE` بـ `tw_shared.css` · F36 · `docs/rules/ds-size.md` · `test_ds_size_tokens.py` |
