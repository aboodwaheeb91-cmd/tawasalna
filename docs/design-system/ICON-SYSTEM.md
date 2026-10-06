# Icon System V1 (DS-ICON)

> النظام الرسمي الوحيد لأيقونات الواجهة في تواصلنا: مصدر الرسومات، الأسماء، طريقة الرسم (render)، الاتجاه بالـ RTL، والممنوعات.
>
> **القاعدة العليا:** `ARCHITECTURE_FOUNDATION.md` → F37.
> **Runtime Source of Truth:** `static/shared/tw-icons.js` (registry — Phase B ✅ · Phase C: أول مستهلك `job-detail.html`).
> **قوانين الـ AI:** `docs/rules/ds-icon.md`.
> **الاختبار:** `node test_ds_icon_registry.js`.
> **المرجع:** تقرير المرحلة A (PR-6 / المرحلة A — جرد الأيقونات) + القرارات المعتمدة من صاحب المشروع (1–7).

---

## ICON-00 — Routing Protocol

| إذا كنت… | اذهب إلى |
|----------|----------|
| بدك تعرض أيقونة بأي صفحة | ICON-03 (`twIcon` / `twIconEl`) + ICON-04 (الاسم) |
| ما لقيت الاسم بالـ registry | ICON-12 (إضافة أيقونة) — لا تكتب SVG inline ولا `data-lucide` |
| أيقونة سهم / رجوع / تقدّم / إرسال / دخول / خروج | ICON-08 (الاتجاه) — أسماء المعنى فقط |
| تحدد حجم أيقونة | ICON-05 → DS-SIZE (`SIZE-SYSTEM.md` SIZE-06) |
| تحدد لون أيقونة | ICON-06 → DS-COLOR (`currentColor` فقط) |
| تغيّر سماكة الخط (stroke-width) | ICON-07 |
| زر أيقونة (header / toolbar) | DS-BTN BTN-06 (شكل الزر) + هاد الملف (الأيقونة) |
| emoji مكان أيقونة | ICON-11 — ممنوع |
| تحوّل صفحة قديمة للنظام | ICON-13 (المرحلة C) |
| أيقونة مهارة / مهنة من الكتالوج | ICON-04.3 — الاسم المخزَّن بالـ DB هو المفتاح |

---

## ICON-01 — Scope & Ownership

**DS-ICON يملك:** أسماء الأيقونات، رسوماتها (SVG children)، دالة الرسم، خريطة الأسماء القديمة (aliases)، وقاعدة الاتجاه بالـ RTL.

**DS-ICON لا يملك:**

| الشي | مالكه |
|------|-------|
| حجم الأيقونة | DS-SIZE (`--size-icon-*` — SIZE-06) |
| لون الأيقونة | DS-COLOR (الأيقونة ترث `currentColor` من العنصر الأب) |
| شكل زر الأيقونة، الـ touch target، الـ aria-label | DS-BTN (BTN-06 + BTN-07) |
| أيقونة مهارة/مهنة أي اسم بتحمل | الكتالوج (`skill_catalog.icon` · `profession_categories.icon`) — DS-ICON بيضمن إنه الاسم إله رسمة |

**نطاق V1:** أيقونات الواجهة (UI glyphs) بالـ Web. خارج النطاق: الصور، الشعارات (logo)، الأعلام (`TW.countryFlagEl()` + `flags/*.svg`)، أيقونات PWA و favicon (FUTURE_ROADMAP).

---

## ICON-02 — Source & License

- **المصدر الوحيد للرسومات:** Lucide **0.460.0** — نفس النسخة الموجودة بـ `static/vendor/lucide/lucide.min.js`.
- **الترخيص:** ISC (أجزاء من Feather — MIT). النص الكامل بـ `THIRD_PARTY_NOTICES.md` → Lucide.
- كل رسمة بالـ registry نسخة حرفية من عقد (nodes) الأيقونة بـ Lucide 0.460 — الاختبار بيتحقق إنه كل رسمة مطابقة لرسمة موجودة بالـ bundle.
- **العلامات التجارية** (`linkedin` · `github` · `twitter` · `instagram`): للتعريف بالخدمة فقط، الملكية لأصحابها، ولا تُستعمل لمهارة عامة.
- ❌ مكتبة ثانية (Font Awesome، Material، Heroicons…) · ❌ رسم SVG يدوي جديد · ❌ نسخة Lucide ثانية.

---

## ICON-03 — Runtime API

الملف: `static/shared/tw-icons.js` (مستقل — ما بيعتمد على `tw_shared.js` ولا على `tw_shared.css`).

```js
el.innerHTML = twIcon('back', { size: 'md' });  // string SVG
btn.appendChild(twIconEl('delete'));            // عنصر SVG (DOM)
twIcon.has('briefcase');                        // true / false — بدون warning
```

### عقد المخرجات (ثابت)

```html
<svg xmlns="http://www.w3.org/2000/svg" class="tw-ico" width="24" height="24"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">…</svg>
```

### الخيارات (`opts`)

| الخيار | القيم | الأثر |
|--------|-------|-------|
| `size` | `xs` · `sm` · `md` · `lg` · `xl` · `2xl` | `style="width:var(--size-icon-X, Npx);height:…"` — الـ fallback بالـ px بيخلّيها تشتغل بالصفحات اللي ما بتحمّل `tw_shared.css` (ICON-05). قيمة غير معروفة → تُتجاهل + warning |
| (بدون `size`) | — | `width="24" height="24"` كـ attributes — CSS الصفحة بيحدد الحجم (نفس سلوك Lucide اليوم) |
| `filled` | `true` | `fill="currentColor"` — للحالة المفعّلة بس (قلب أقدّر، حفظ) |
| `className` | كلاسات إضافية | تُقبل بس tokens من `[A-Za-z0-9_-]`؛ أي شي ثاني بينحذف |

- الأيقونة **زخرفية دائماً** (`aria-hidden="true"`). الاسم المقروء للزر مسؤولية DS-BTN (`aria-label` / نص).
- `twIconEl` بيرجع عنصر SVG حقيقي (namespace SVG) عن طريق `<template>`.

---

## ICON-04 — Names

### ICON-04.1 — القاعدة

1. **أيقونات الأفعال والتنقّل = اسم المعنى** (`back` · `close` · `delete` · `edit` · `more` · `expand`…) مش اسم الرسمة.
2. **أيقونات الأشياء = اسم Lucide** (`briefcase` · `calendar` · `map-pin`…) لأنه الاسم هو المعنى.
3. **أيقونات الكتالوج = الاسم المخزَّن بالـ DB حرفياً** (ICON-04.3).
4. اسم واحد لكل معنى. معنيين مختلفين بنفس الرسمة = اسمين (`collapse` و `move-up` كلاهما chevron-up).

### ICON-04.2 — أسماء الواجهة (106)

| المجموعة | الأسماء (`اسم` (رسمة Lucide) إذا مختلفة) |
|----------|----------------------------------------|
| اتجاهية — `dir:true` (ICON-08) | `back` (arrow-left) · `forward` (arrow-right) · `prev` (chevron-left) · `next` (chevron-right) · `send` · `log-in` · `log-out` |
| فتح / ترتيب | `expand` (chevron-down) · `collapse` (chevron-up) · `move-up` (chevron-up) · `move-down` (chevron-down) · `show-more` (circle-arrow-down) · `show-less` (circle-arrow-up) |
| هيكل التطبيق | `home` · `notifications` (bell) · `messages` (message-circle-more) · `chat` (message-circle) · `comment` (message-square) · `menu` · `more` (ellipsis-vertical) · `list` · `settings` · `search` · `zoom-in` · `zoom-out` |
| أفعال | `add` (plus) · `add-circle` (plus-circle) · `edit` (square-pen) · `pencil` · `delete` (trash-2) · `close` (x) · `check` · `copy` · `share` (share-2) · `report` (flag — إبلاغ عن محتوى؛ أول مستهلك job-detail) · `download` · `upload` (upload-cloud) · `refresh` (refresh-cw) · `camera` |
| حالات | `success` (check-circle) · `error` (circle-x) · `alert` (circle-alert) · `info` · `help` (circle-help — **الـ fallback**) · `circle-check` (fallback المهارة المخصّصة) · `verified` (badge-check) · `shield-check` · `wifi-off` |
| أشخاص | `user` · `user-round` · `users` · `user-plus` · `user-check` · `user-minus` |
| تبديل (outline؛ المفعّل بـ `filled`) | `bookmark` · `bookmark-check` · `star` · `heart` · `eye` · `eye-off` |
| أشياء / بيانات | `calendar` · `calendar-clock` · `clock` · `map-pin` · `map` · `briefcase` · `briefcase-business` · `building-2` · `graduation-cap` · `book-open` · `book` · `languages` · `mail` · `phone` · `globe` · `link` · `link-2` · `at-sign` · `file-text` · `tag` · `id-card` · `qr-code` · `cake` · `laptop` · `wrench` · `newspaper` · `layout-dashboard` · `layout-template` · `layers` · `sparkles` · `zap` · `target` · `trending-up` · `gem` · `rss` · `git-branch` · `clipboard-check` · `circle-dollar-sign` · `bar-chart-2` · `search-check` · `messages-square` |
| علامات (LINK_ICONS) | `linkedin` · `github` · `twitter` · `instagram` · `layout` |

كل اسم إله مستهلك موجود اليوم (`data-lucide` · SVG inline · خرائط JS · `home.nav.js`). `external-link` **مش موجود** — ما إله مستهلك بعد؛ بيندخل مع أول مستهلك (ICON-12) كـ `dir:true`.

### ICON-04.3 — أسماء الكتالوج (82 إضافية)

المصادر: `skill_catalog.icon` (seed بـ `auth.py`) · `profession_categories.icon` (seed بـ `auth.py`) · `TW.SKILL_CATALOG` (fallback بـ `tw-options-data.js`). الاسم المخزَّن هو مفتاح الـ registry — **ما في إعادة تسمية لقيم الـ DB**. الأسماء اللي بتتقاطع مع أسماء الواجهة (`briefcase` · `users` · `settings`…) بتستعمل نفس المدخل.

`activity` · `archive` · `atom` · `award` · `bar-chart` · `bot` · `brain` · `brain-circuit` · `building` · `cable` · `calculator` · `car` · `check-square` · `chef-hat` · `clipboard` · `clipboard-list` · `cloud` · `code` · `code-2` · `coffee` · `compass` · `cpu` · `database` · `dollar-sign` · `edit-3` · `figma` · `film` · `fingerprint` · `flame` · `flask-conical` · `hammer` · `handshake` · `hard-drive` · `hard-hat` · `headphones` · `headset` · `heart-pulse` · `hospital` · `hotel` · `image` · `inbox` · `lightbulb` · `lock` · `megaphone` · `mic` · `monitor` · `network` · `package` · `paint-bucket` · `palette` · `pen-tool` · `pencil-ruler` · `pill` · `plane` · `plug` · `presentation` · `router` · `scale` · `scan` · `scan-search` · `server` · `settings-2` · `shield` · `shield-off` · `ship` · `shirt` · `shopping-cart` · `signal` · `smartphone` · `smile` · `stethoscope` · `syringe` · `table` · `terminal` · `triangle` · `truck` · `type` · `utensils` · `video` · `warehouse` · `wifi` · `wind`

أي مهارة/مهنة جديدة بالـ seed لازم أيقونتها تكون بالـ registry بنفس الـ PR (الاختبار بيفشل غير هيك).

### ICON-04.4 — Aliases (مكان واحد: `ALIASES` بـ `tw-icons.js`)

| الاسم القديم | → | السبب |
|-------------|---|-------|
| `x` · `plus` · `plus-circle` · `share-2` · `bell` · `message-circle-more` · `message-circle` · `check-circle` · `badge-check` · `upload-cloud` · `refresh-cw` | `close` · `add` · `add-circle` · `share` · `notifications` · `messages` · `chat` · `success` · `verified` · `upload` · `refresh` | أسماء Lucide مستعملة اليوم (`data-lucide` / الكتالوج) → اسم المعنى |
| `tool` | `wrench` | اسم بـ `TW.SKILL_CATALOG` مش موجود بـ Lucide 0.460 (اليوم ما بيرسم شي) |

- ❌ **ممنوع alias لـ `arrow-left` / `arrow-right` / `chevron-left` / `chevron-right`** — لازم المستهلك يختار المعنى (`back` / `forward` / `prev` / `next`).
- ❌ جدول aliases ثاني بأي ملف.

---

## ICON-05 — Sizes (DS-SIZE)

| `opts.size` | Token | px |
|-------------|-------|----|
| `xs` | `--size-icon-xs` | 12 |
| `sm` | `--size-icon-sm` | 14 |
| `md` | `--size-icon-md` | 16 |
| `lg` | `--size-icon-lg` | 18 |
| `xl` | `--size-icon-xl` | 20 |
| `2xl` | `--size-icon-2xl` | 22 |

- الـ fallback (`var(--size-icon-md, 16px)`) **مش نسخ tokens** — هو قيمة احتياطية بالاستدعاء نفسه، ما بيعرّف `--size-*` (F36 محفوظة).
- **أحجام برّا السلّم (10 · 11 · 15 · 19 · 24):** بتتوحّد على أقرب token **وقت تحويل كل صفحة** (المرحلة C) — تغيير مرئي بيتذكر بوصف الـ PR.
- **13px → `sm`** (قرار DS-SIZE 2).
- **26 · 28 · 40:** قيم محلية Tier 3 (SIZE-07/SIZE-09) — أيقونات شعار/avatar احتياطية. بتنعمل بـ CSS الصفحة (بدون `size`)، ما في token إلها.

---

## ICON-06 — Color (DS-COLOR)

- الأيقونة **دائماً** `stroke="currentColor"` (و `fill="currentColor"` بحالة `filled`) — اللون بيجي من `color` العنصر الأب عبر DS-COLOR tokens.
- ❌ لون hex / rgb جوّا الأيقونة · ❌ `stroke:#…` بـ style inline · ❌ لون ثاني جوّا نفس الأيقونة (two-tone).
- الأيقونة بتورث Color Role العنصر الأب (CLR-33) — الوراثة هون مقصودة.

---

## ICON-07 — Stroke Width

- الافتراضي **2** (attribute بالـ SVG).
- **استثناء مجمّد:** `.sc-btn .ico-sm` = **1.8** — بيضل بالـ CSS تبعه (CSS أقوى من الـ attribute). ما بيتلمس.
- قيم `stroke-width` محلية ثانية (1.5 · 1.8 · 2.2 · 2.5 بـ company.css / notifications / posts / landing…) بتشيلها الصفحة وقت تحويلها → 2؛ تغيير مرئي بيتذكر بوصف الـ PR.
- ❌ خيار `strokeWidth` بالـ API — السماكة قرار نظام مش قرار استدعاء.

---

## ICON-08 — Direction (RTL)

- أي أيقونة معناها اتجاه (رجوع، تقدّم، التالي، السابق، إرسال، دخول، خروج) مسجّلة بـ `dir:true` → بتاخد class `tw-ico-dir`.
- `tw-icons.js` بيحقن **قاعدة وحدة** مرّة وحدة (`<style id="tw-ico-style">`) أول ما تنرسم أيقونة اتجاهية:

```css
[dir="rtl"] .tw-ico-dir{transform:scaleX(-1)}
.tw-ico-dir:dir(ltr){transform:none}
```

- **ليش class + قاعدة جوّا الملف (مش inline):** القلب بيتبع اتجاه الصفحة الحالي (حتى لو تغيّر `dir` بعد الرسم أو حاوية `dir="ltr"` جوّا صفحة RTL)، وبيشتغل بدون `tw_shared.css`. الـ inline بيثبّت القرار وقت الرسم.
- الرسومات بالـ registry مرسومة LTR (Lucide). مثال: `back` = سهم لليسار بـ LTR → لليمين بـ RTL.
- ❌ `arrow-left` / `arrow-right` / `chevron-left` / `chevron-right` يدوي بالصفحات · ❌ `transform: scaleX(-1)` يدوي على أيقونة · ❌ اختيار رسمة حسب اللغة بالـ JS.

---

## ICON-09 — Security

- الاسم المطلوب **مفتاح بالـ map بس** — ما بيدخل الـ HTML أبداً. اسم غير معروف (أو `__proto__` / `constructor` / غير string) → رسمة `help` + `console.warn` مرّة وحدة لكل اسم.
- هاد بيسكّر الحقن الحالي: `'<i data-lucide="' + name + '">'` بيحط الاسم بالـ HTML (بعض المواضع بدون escaping — `profile-v2.skills.js`).
- `className` بيقبل بس `[A-Za-z0-9_-]` · `size` بيقبل بس أسماء الـ tokens.
- الرسومات ثابتة بالملف — ما في بيانات API بتدخلها.

---

## ICON-10 — Frozen Exceptions

| الاستثناء | الحالة |
|-----------|--------|
| `.sc-btn .ico-sm` stroke 1.8 · 14×14 (profile-v2 — SIZE-08) | مجمّد — بيضل بـ CSS |
| أيقونات post-comments (`_ICO_CMT_EXPAND` / `_ICO_CMT_COLLAPSE` 12px) | بتتحوّل بس ضمن PR post-comments معلن (`docs/rules/post-comments.md`) |

---

## ICON-11 — Emoji

- **emoji ممنوعة كأيقونة واجهة** (زر، عنوان قسم، حالة، قائمة، شارة). محتوى المستخدم (منشورات، رسائل) مش مشمول.
- الـ emoji الموجودة بتنستبدل ضمن تحويل كل صفحة (المرحلة C)، و **admin بالآخر**.
- ❌ emoji جديدة بأي واجهة من اليوم.

---

## ICON-12 — Adding a New Icon

1. تأكد إنه ما في اسم موجود بنفس المعنى (`twIcon.has`).
2. اختار الاسم حسب ICON-04.1 (معنى للأفعال/التنقّل، اسم Lucide للأشياء، اسم الـ DB للكتالوج).
3. انسخ عقد الأيقونة من **Lucide 0.460.0** (`lucide-static@0.460.0/icons/<name>.svg` أو `lucide.icons` بالـ bundle المحلي) — بدون تعديل.
4. ضيفها لـ `ICONS` بـ `tw-icons.js` بالمجموعة الصح (`[1, …]` إذا اتجاهية).
5. **بنفس الـ PR:** المستهلك الحقيقي (لا أيقونات بدون مستهلك) + `node test_ds_icon_registry.js` أخضر.
6. اسم قديم لازم يضل شغّال → سطر بـ `ALIASES` بس.

---

## ICON-13 — Phases

| المرحلة | الحالة |
|---------|--------|
| A — جرد الأيقونات + القرارات | ✅ |
| B — registry + توثيق + اختبار، **بدون مستهلك وبدون تغيير بصري** | ✅ PR-6 / المرحلة B (2026-10-06) |
| C — تحويل صفحة صفحة | 🔜 جاري — ✅ `job-detail.html` (أول مستهلك: `data-lucide` + emoji → `twIconEl`، `_lucideIcon` انحذفت، Lucide ما عاد ينحمّل بالصفحة، زر الرجوع `prev`) · الباقي: `docs/FUTURE_ROADMAP.md` → DS-ICON Phase C |

**المرحلة C (ملخّص — التفاصيل بالـ roadmap):**
1. أول PR: زر الرجوع بـ `profile-showcase.html:46` → `twIcon('back')` + باقي أيقونات الصفحة نفسها.
2. صفحة صفحة: `data-lucide` + SVG inline + emoji → `twIcon`؛ توحيد الأحجام والسماكة (ICON-05/07) مع ذكر التغيير المرئي.
3. دمج `_lucideIcon` المكرّرة (job-detail ✅ · home.cards.js) · تحويل `LINK_ICONS` / `_FILTER_ICONS` / قائمة الهيدر لأسماء registry · سهم القائمة المنسدلة بـ `company.css`.
4. بالآخر: إزالة `static/vendor/lucide/lucide.min.js` + unpkg CDN (`index.html` · `profile-showcase.html`) + `lucide.createIcons()`؛ فحص "رسمة = Lucide 0.460" بالاختبار بيتحوّل لمقارنة مع snapshot ثابت.
5. admin بالآخر.

كل صفحة بموافقة صريحة، وكل تغيير مرئي بيتذكر بوصف الـ PR.

---

## ICON-14 — Forbidden

```
❌ مكتبة أيقونات ثانية أو نسخة Lucide غير 0.460 أو CDN جديد
❌ SVG inline جديد أو <i data-lucide> جديد بأي صفحة
❌ registry ثاني / خريطة أيقونات محلية بصفحة (LINK_ICONS وأخواتها بتتحوّل لأسماء registry)
❌ وضع اسم الأيقونة بالـ HTML (data-lucide="' + name + '")
❌ arrow-left / arrow-right / chevron-left / chevron-right يدوي — استعمل back / forward / prev / next
❌ لون غير currentColor · stroke-width بالاستدعاء
❌ emoji كأيقونة واجهة
❌ أيقونة بالـ registry بدون مستهلك
❌ جدول aliases ثاني
❌ تحميل tw-icons.js بصفحة خارج PR المرحلة C الخاص فيها
```

---

*أُنشئ في PR-6 / المرحلة B — 2026-10-06 — DS-ICON V1: registry (`static/shared/tw-icons.js`، 187 رسمة + 12 alias، Lucide 0.460 فقط)، بدون مستهلك وبدون تغيير بصري.*
