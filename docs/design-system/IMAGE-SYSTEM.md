# Image Display System V1 (DS-IMAGE)

> النظام الرسمي الوحيد لعرض صور الحسابات في تواصلنا: أفاتار الموظف، لوغو الشركة / الجهة التعليمية، الحرف البديل، وأمان رابط الصورة بالعرض.
>
> **القاعدة العليا:** `ARCHITECTURE_FOUNDATION.md` → F38.
> **Runtime Source of Truth:** `tw_shared.js` (`twSafeImageUrl` · `twCssUrl` · `twAvatarHtml` · `twAvatarEl`) + `tw_shared.css` (قسم `16. DS-IMAGE` + `--size-avatar-*` بقسم `1b. DS-SIZE`) — Phase B ✅، بدون مستهلك.
> **قوانين الـ AI:** `docs/rules/ds-image.md`.
> **الاختبار:** `node test_ds_image_runtime.js`.
> **المرجع:** تقرير فحص DS-IMAGE (المرحلة A) + القرارات المعتمدة من صاحب المشروع (1–5) — PR-7b.

---

## IMG-00 — Routing Protocol

| إذا كنت… | اذهب إلى |
|----------|----------|
| بدك تعرض أفاتار موظف أو لوغو جهة | IMG-03 → IMG-05 (`twAvatarHtml` / `twAvatarEl`) |
| بتحط رابط صورة من الـ API بـ `src` أو `href` | IMG-08 (`twSafeImageUrl` + `twEscAttr`) |
| بتحط غلاف بـ `background-image` | IMG-08 (`twCssUrl`) + IMG-10 |
| بتحدد حجم أفاتار | IMG-02 → DS-SIZE |
| بتحدد لون الحرف البديل | IMG-04 → DS-COLOR |
| صورة فشلت / ما في صورة | IMG-06 + IMG-07 |
| hero (أفاتار كبير فوق الصفحة) | IMG-09 (`opts.eager`) |
| رفع صورة | §29a (`TW.uploadImage`) — مش هون |
| قص صورة | §29b (`TW.createCropper`) — مش هون |
| تحوّل صفحة قديمة للنظام | IMG-13 (المرحلة C) |

---

## IMG-01 — Scope & Ownership

**DS-IMAGE يملك:** markup الأفاتار / اللوغو، الشكل حسب نوع الحساب، الحرف البديل، حالة الفشل، `loading` / `decoding` / الأبعاد، والتحقق من رابط الصورة وقت العرض.

| الشي | مالكه |
|------|-------|
| قيم الأحجام والزوايا | DS-SIZE (`--size-avatar-*` · `--radius-*`) |
| ألوان الحرف والخلفية | DS-COLOR (categorical + surface) |
| الرفع + التحقق من الرابط وقت الحفظ | §29a (`_validate_stored_image_url` بالسيرفر) |
| القص ونسبة الإخراج | §29b |
| escaping النص | §54 (`twEscHtml` / `twEscAttr`) |

---

## IMG-02 — Size Scale

| الدرجة | Token | px | الاستعمال المتوقع |
|--------|-------|----|-------------------|
| `md` | `--size-avatar-md` | 40 | قوائم، محادثات، كروت صغيرة |
| `lg` | `--size-avatar-lg` | 48 | كروت مرشحين / وظائف |
| `xl` | `--size-avatar-xl` | 88 | hero مضغوط / مودال |
| `2xl` | `--size-avatar-2xl` | 106 | hero البروفايل |

- الـ tokens بقسم DS-SIZE بـ `tw_shared.css` (F36) — مش ملف ثاني.
- **22 و 32** (post-comments) مجمّدة محلياً (SIZE-08) — خارج السلّم.
- **التوحيد مرئي:** 38 / 42 → 40 · 44 → 48 · 84 / 86 / 90 / 94 → الأقرب = تغيير مرئي (SIZE-05) → المرحلة C فقط، صفحة صفحة مع screenshots.
- حجم الحرف: md `--size-font-2xl` · lg `--size-font-3xl` · xl / 2xl `--size-font-display` (بدون tokens جديدة).

---

## IMG-03 — Shape

| نوع الحساب | class | الشكل |
|------------|-------|-------|
| `emp` (موظف) | `tw-ava--emp` | دائرة `--radius-circle` |
| `co` / `edu` (جهة) | `tw-ava--org` | مربع بزوايا مدوّرة — بكل مكان (hero وكروت) |

**Mapping الزاوية للجهات** (متناسبة مع الحجم، من tokens موجودة — بدون قيم جديدة):

| الحجم | Token | النسبة |
|-------|-------|--------|
| md 40 | `--radius-md` (10px) | 25% |
| lg 48 | `--radius-lg` (12px) | 25% |
| xl 88 | `--radius-3xl` (20px) | ≈23% |
| 2xl 106 | `--radius-3xl` (20px) | ≈19% |

> 2xl بياخد أكبر درجة موجودة (20px) — درجة 24px ما إلها مستهلك حالي، فما انضافت (SIZE-07 / CLR-28: لا token بدون مستهلك).

---

## IMG-04 — Fallback Colors

| النوع | لون الحرف | خلفية |
|-------|-----------|-------|
| `emp` | `--color-categorical-teal` | `--color-surface-card-solid` |
| `co` | `--color-categorical-blue` | `--color-surface-card-solid` |
| `edu` | `--color-categorical-purple` | `--color-surface-card-solid` |

**ليش categorical مش brand:** نوع الحساب "فئة بيانات" (موظف / شركة / جهة) — CLR-11 + CLR-13 بيفرضوا `--color-categorical-*` لتمييز الفئات، و `--color-brand-*` لهوية المنتج. القيم الحالية مطابقة للقرار (primary teal · secondary blue · accent purple) → بدون فرق بصري، بس الهوية مستقلة (CLR-12). ممنوع hex.

---

## IMG-05 — Fallback Letter

- `Array.from(full_name.trim())[0]` — بيحافظ على emoji / surrogate pairs كاملة.
- بدون `toUpperCase` (عربي أولاً؛ ما بنغيّر شكل الاسم).
- اسم فارغ / مسافات / مش string → `؟`.
- بيمر على `twEscHtml` (string) أو `textContent` (DOM). `aria-hidden="true"` — الاسم بيكون جنب الأفاتار.

---

## IMG-06 — Fallback State (`data-fb`)

- ما في رابط، أو الرابط رفضه `twSafeImageUrl` → بدون `<img>` + `data-fb="1"` مباشرة.
- `data-fb="1"` → `<img>` مخفي + الحرف ظاهر. بدونه → الحرف مخفي (ما بيبيّن ورا لوغو PNG شفاف).
- خلال التحميل: الخلفية فقط.

---

## IMG-07 — Error Listener

- **listener واحد** على `document` (`addEventListener('error', fn, true)` — capture، لأن `error` تبع الصور ما بيعمل bubble) بـ `tw_shared.js`.
- `<img>` أبوه `[data-tw-ava]` فشل → `data-fb="1"` على الأب. أي صورة ثانية → تجاهل.
- **ممنوع `onerror` inline** (ولا `img.onerror` لكل صورة).

---

## IMG-08 — Security (§54)

| الدالة | العقد |
|--------|-------|
| `twSafeImageUrl(url)` | يرجّع `url` إذا بلش بـ `https://` (case-insensitive) أو مسار `/` نسبي — مش `//` ولا `/\` (المتصفح بيعاملهم protocol-relative). غير هيك → `''` (`javascript:` · `data:` · `vbscript:` · `http:` · `blob:` · مسافة بالأول · نسبي بدون `/`). |
| `twCssUrl(url)` | `twSafeImageUrl` + `url("…")` مع تهريب سياق CSS (`\` `"` newline → hex escape). غير صالح → `''` والمستدعي بيترك الخلفية الافتراضية. |
| `twAvatarHtml` | الرابط → `twEscAttr` بالـ `src` · الحرف → `twEscHtml` · النوع والحجم من allowlist. |

- `esc(url)` (escaping HTML) **مش** تحقق رابط ومش تهريب CSS — `img.src = esc(url)` غلط (بيخرّب `&`) و `src="' + esc(url) + '"` ثغرة (`esc` المحلي ما بيهرّب `"`).
- `http://` مرفوض: كل الصور المحفوظة روابط Supabase `https` (§29a)، والموقع https (mixed content).
- الـ regex القديم `/^(https?:\/\/|\/(?!\/))/` بـ §54 صار legacy — كود جديد بيستعمل `twSafeImageUrl`.

---

## IMG-09 — Loading & Dimensions

- `loading="lazy"` افتراضياً · `opts.eager` → `loading="eager"` للـ hero فقط (LCP).
- دائماً `alt=""` (زخرفي — الاسم نص جنبه) + `decoding="async"` + `width` / `height` = px الدرجة (يمنع layout shift).

---

## IMG-10 — Cover (Decision)

- **نسبة ثابتة 4:1** لغلاف الموظف (نفس الشركة: `company-cover` 800×200).
- **الحالة الفعلية (دين موثّق):** غلاف الموظف `.sc-cover` ارتفاعه 80px ثابت وعرضه حسب الشاشة؛ الـ cropper (`profile-v2.cover.js → openCrop`) بيحسب النسبة ديناميكياً `offsetWidth / 80` وبيطلّع `W×240` — مش 6:1 الموثّق سابقاً بـ §29b. الصورة بتتقص بشكل مختلف حسب جهاز الرفع.
- **التنفيذ (العرض + الـ cropper 4:1)** → المرحلة C. هلّق: عرض الغلاف بس صار عبر `twCssUrl` (بدون تغيير بصري).

---

## IMG-11 — Frozen Exceptions

- post-comments: أفاتار 32 / 22 (SIZE-08) — خارج DS-IMAGE V1.
- أي شكل / حجم داخل `.sc-actions` / `.sc-btn` (SIZE-08).

---

## IMG-12 — Known Debt

| الدين | المكان | الحل |
|-------|--------|------|
| 8 دوال escaping محلية على مسارات صور | `messages.state.js → esc` · `profile-v2.utils.js → esc` · `static/company/company.main.js → _esc` (×3) · `static/company/company.jobs.js → _esc` · `static/company/company.render.js → _esc` + `_escapeHtml` | بتنشال بالمرحلة C مع تحويل كل صفحة (مش بـ PR-7b) |
| `src="' + esc(url)` بدون تحقق رابط | `messages.render.js` · `static/company/company.main.js` (كروت المرشحين) | المرحلة C (`twAvatarHtml`) |
| غلاف الموظف ديناميكي W×240 | `profile-v2.cover.js` · `.sc-cover` | IMG-10 — المرحلة C |
| `company-logo` cropper دائري | `company.main.js → openLogoCrop` | يصير مربع (IMG-03) — المرحلة C |
| `[data-ah-av]` ميت | `static/app-header.js` | حذف — Roadmap |
| home-v2 / job-detail بدون `tw_shared.*` | الصفحتين | تحميل `tw_shared.*` قبل تحويلهم |

---

## IMG-13 — Phase Plan

| المرحلة | الحالة |
|---------|--------|
| A — فحص | ✅ |
| B — helper + CSS + tokens + توثيق + إصلاح §54 بـ profile-v2 (بدون مستهلك وبدون تغيير بصري) | ✅ PR-7b (2026-10-06) |
| C — تحويل صفحة صفحة | 🔜 بالترتيب: messages ← company ← profile، وبعدها home و job-detail (بعد تحميل `tw_shared.*` عندهم). كل صفحة: helper + شيل الـ escaping المحلي + توحيد الأحجام + screenshots. + غلاف الموظف 4:1 + cropper · لوغو الشركة مربع + cropper مربع |
| الجهة التعليمية | 🔜 PR مستقل: upload لوغو + غلاف عبر §29a / §29b (بدل localStorage) |

> المرحلة C ممنوعة إلا بموافقة صريحة لكل صفحة.
