# Page Shell V1 (DS-SHELL)

> القالب الموحّد لكل صفحة HTML بتواصلنا: كتلة `<head>` المشتركة وسكربتات آخر `<body>` المشتركة — مصدر واحد بدل نسخها بكل صفحة.
>
> **القاعدة العليا:** `ARCHITECTURE_FOUNDATION.md` → F39.
> **Runtime Source of Truth:** `page_shell.py` (`apply_shell` · `build_shell` · `asset_hash`) + `partials/shell-*.html` · مستدعى من `read_html()` بـ `server.py`.
> **قوانين الـ AI:** `docs/rules/page-shell.md`.
> **الاختبار:** `python test_page_shell.py`.
> **المرجع:** تقرير فحص Page Shell (المرحلة A) + القرارات المعتمدة (1–6) — PR-8 / المرحلة B.

---

## SHELL-00 — Routing Protocol

| إذا كنت… | اذهب إلى |
|----------|----------|
| بتبني صفحة HTML جديدة | SHELL-06 (خطوتين) |
| بدك تضيف meta / font / CSS / JS لكل الصفحات | SHELL-02 (عدّل الـ partial — مش الصفحات) |
| بتحوّل صفحة قديمة للـ shell | SHELL-08 (المرحلة C) |
| صفحة أدمن | SHELL-03 (`:admin`) |
| بدك `?v=` لملف مشترك | SHELL-05 (تلقائي — ممنوع يدوي) |
| ترتيب CSS المشترك مقابل CSS الصفحة | SHELL-04 |
| أيقونات / `tw-icons.js` | **مش هون** — DS-ICON Phase C (F37) |
| صفحة محمية (بدها جلسة) | SHELL-09 (`twRequireAuth` + `<meta name="tw-page" content="auth">`) |
| هيدر / شريط سفلي | **مش هون** — `HEADER-NAV.md` (DS-HNAV: `<header data-tw-header>` + `twMountAppChrome` بـ `tw_shared.js`) |

---

## SHELL-01 — Scope & Ownership

**DS-SHELL يملك:** `charset` · `viewport` · `theme-color` · `manifest` · meta تطبيق الشاشة الرئيسية (`mobile-web-app-*` / `apple-mobile-web-app-*`) · `rel="icon"` + `apple-touch-icon` · preconnect + خط Cairo · `tw_shared.css` · `tw_shared.js` · `auth-sync.js` — وترتيبهم ونسختهم (`?v=`).

| الشي | مالكه |
|------|-------|
| `<title>` + CSS / JS الخاص بالصفحة + `<body>` | الصفحة نفسها |
| ملفات الأيقونات + `manifest.json` + SW | §32 |
| ألوان `theme-color` | DS-COLOR (`--color-brand-primary` = `#00c896`) |
| قرار الدخول (guest → `/login?next=`) | `twRequireAuth` (SHELL-09) — بيقرأ TwAuthSync (§VM-10) بس |
| الهيدر + الشريط السفلي | DS-HNAV (`HEADER-NAV.md`) — JS بـ `tw_shared.js` مش partial: المحتوى حسب الجلسة، وبيشتغل كمان على صفحات لسّا مش على الـ shell |

---

## SHELL-02 — Markers & Partials

الصفحة بتحط markers صريحة، و `read_html()` بيبدّلهم وقت القراءة (مرة وحدة، بعدين cache):

| Marker | Partial (برّا `static/` — مش منخدم مباشرة) | المكان |
|--------|---------------------------------------------|--------|
| `<!--tw:shell-head-->` | `partials/shell-head.html` | أول سطر بعد `<head>` |
| `<!--tw:shell-scripts-->` | `partials/shell-scripts.html` | قبل أول `<script>` خاص بالصفحة بآخر `<body>` |
| `<!--tw:shell-head:admin-->` | `partials/shell-head.admin.html` | نفس المكان |
| `<!--tw:shell-scripts:admin-->` | `partials/shell-scripts.admin.html` | نفس المكان |

**head (app):** `charset UTF-8` · `viewport width=device-width, initial-scale=1.0` (zoom مسموح) · `theme-color #00c896` · `manifest` · `mobile-web-app-capable=yes` + `apple-mobile-web-app-capable=yes` + `apple-mobile-web-app-status-bar-style=black-translucent` + `apple-mobile-web-app-title=تواصلنا` (تطبيق الشاشة الرئيسية standalone — مش بنسخة الأدمن) · `rel="icon"` → `/favicon.ico` · `apple-touch-icon` → `/apple-touch-icon.png` (§32) · preconnect `fonts.googleapis.com` + `fonts.gstatic.com` · Cairo **400–900** · `/static/tw_shared.css?v=H`.
**scripts (app):** `/static/tw_shared.js?v=H` ← `/static/shared/auth-sync.js?v=H`.

> **`/static/tw_shared.js` (المرحلة C — job-detail):** نفس الملف `tw_shared.js` بالجذر، منخدم عبر `/static/{filename}` (fallback الجذر) → جوّا allowlist الـ SW (§32 — `/static/*`). المسار القديم `/tw_shared.js` (route بـ `server.py`) **بيضل شغّال كما هو** (نفس الملف، بدون redirect) للصفحات غير المحوّلة و `_LEGACY_REDIRECT_HTML` — بينشال بس لما ما يضل إله مستهلك. نقل المسار = bump لـ `BUILD_TIME` بـ `sw.js`.

**القواعد:**
- صفحة **بدون** markers → بترجع **مطابقة للملف بالبايت** (التحويل صفحة صفحة).
- صفحة فيها markers → لازم نسخة وحدة (app أو admin)، وكل marker مرة وحدة، والـ head قبل الـ scripts. غير هيك → `ValueError` (F9 — صفحة نص محوّلة = bug، مش صفحة).
- الحقن **نص ثابت فقط** (partials + hashes) — ما في أي بيانات مستخدم ولا request (§54).
- `{{v:<asset>}}` بالـ partial: أسماء `SHELL_ASSETS` فقط؛ placeholder مش معروف → خطأ عند بدء السيرفر.
- `{{v:<asset>}}` **جوّا الصفحة** (صفحة فيها markers فقط): أسماء `PAGE_ASSETS` فقط — allowlist ثابتة بـ `page_shell.py` (حالياً `tw-icons.js` · `tw-overlay.js` — DS-OVL OVL-39). `apply_shell` بيبدّلها بنص الصفحة قبل ما يحط الـ partials. اسم مش بالـ allowlist (ولا اسم من `SHELL_ASSETS`) أو `{{v:` بصفحة بدون markers → `ValueError` (نفس قاعدة الـ partials). أصل جديد → سطر بـ `PAGE_ASSETS` أولاً.

---

## SHELL-03 — النسخ (Variants)

| النسخة | Markers | الفرق |
|--------|---------|-------|
| **app** — صفحات الحساب (محمية) | `shell-head` / `shell-scripts` | الكامل |
| **entry** — `landing` · `/login` · الصفحات العامة | نفس markers الـ app | نفس الـ partials؛ الفرق بالـ guard (SHELL-09: صفحة محمية = `<meta name="tw-page" content="auth">` + `twRequireAuth()`) مش بالـ shell |
| **admin** — `admin-view` · لوحة `/tw-ctrl-*` | `shell-head:admin` / `shell-scripts:admin` | بدون `manifest` · بدون `auth-sync.js` · `<meta name="tw-sw" content="off">` → `tw_shared.js` ما بيسجّل الـ SW |

---

## SHELL-04 — عقد الترتيب

1. **المشترك أولاً:** `tw_shared.css` قبل CSS الصفحة → الصفحة بتقدر تعدّل فوق المشترك، والمشترك ما بيكسر الصفحة.
2. `tw_shared.js` ← `auth-sync.js` ← سكربتات الصفحة.
3. `charset` أول tag بالـ `<head>` (جوّا أول 1024 byte).
4. العقد بيتطبّق على كل صفحة **وقت تحويلها فقط** (المرحلة C) مع فحص بصري — مش على الكل مرة وحدة.

---

## SHELL-05 — الـ hash (`?v=H`)

- `H` = أول 10 أحرف hex من `sha256` لمحتوى الملف (`asset_hash`) — لـ `tw_shared.css` · `tw_shared.js` · `static/shared/auth-sync.js` (`SHELL_ASSETS`).
- بينحسب **مرة وحدة عند بدء السيرفر** (import `page_shell`) → تغيير الملف + deploy = hash جديد = المتصفح والـ SW بيجيبوا النسخة الجديدة.
- بيبدّل `?v=` اليدوي **للملفات المشتركة** (`SHELL_ASSETS` — بالـ partials) **ولأصول `PAGE_ASSETS`** اللي بتحطها صفحة shell بنفسها (`/static/shared/tw-icons.js?v={{v:tw-icons.js}}` — landing · job-detail). ملفات الصفحة الباقية (`messages.css?v=v22` …) خارج النطاق.
- ملف مشترك ناقص → السيرفر ما بيقوم (F9).

---

## SHELL-06 — صفحة جديدة (خطوتين)

```html
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<!--tw:shell-head-->                       <!-- 1 -->
<title>… — تواصلنا</title>
<link rel="stylesheet" href="/static/my-page.css">
</head>
<body>
…
<!--tw:shell-scripts-->                    <!-- 2 -->
<script src="/static/my-page.js"></script>
</body>
</html>
```

والصفحة تنخدم عبر `read_html("my-page.html")` (أي route HTML بـ `server.py`).

---

## SHELL-09 — Guard الصفحات المحمية (`twRequireAuth`)

> **المصدر الوحيد:** `twRequireAuth(opts)` بـ `tw_shared.js` (Auth Gateway rule 14 · CLAUDE.md). أول مستهلك: `appointments.html` + `appointment-room.html` (المرحلة C). اختبار: `node test_appointments_guard_runtime.js`.

**الصفحة:** `<meta name="tw-page" content="auth">` بالـ `<head>` (بعد الـ shell marker) + **نداء واحد** بأول سكربت الصفحة:

```js
const snap = twRequireAuth();            // أو twRequireAuth({ userTypes: ['co'] })
if (!snap) return;                       // الصفحة عم تتحوّل — ولا سطر بعدها
```

| الحالة (`TwAuthSync.getSessionSnapshot()` فقط) | النتيجة |
|-----------------------------------------------|---------|
| `guest` · `expired` · `stale` · `invalid` · TwAuthSync مش موجود (fail-closed) | `location.replace(twLoginHref(pathname + search))` → `null` |
| `authenticated` + `opts.userTypes` وما فيها نوع الحساب | `location.replace(twAccountHref(u))` (مش `/login`) → `null` |
| `authenticated` | بيرجّع الـ snapshot (`userId` · `userType`) |

**بعد التحميل** — تسجيل **واحد** على `TwAuthSync.onSessionChange` (نداء ثاني ما بيسجّل): نفس القرار عند logout / انتهاء الجلسة بتاب تاني أو رجوع bfcache (VM-01 — ما في `pageshow` / `storage` listener خاص)؛ حساب تاني سجّل دخول (`userId` تغيّر، نفس النوع المسموح) → `location.reload()` (ما بتضل بيانات الحساب الأول ظاهرة). بعد أول تحويل ما في تحويل ثاني.

- `401` من API الصفحة → `TwAuthSync.invalidateSession('api_401')` → الـ guard نفسه بيحوّل لـ `/login?next=` (نفس نمط `loadGlobalBadges`).
- الـ guard **UX بس** — الحماية الفعلية بالـ Backend (F6 / F21).
- `twAccountHref(u)` بياخد `tw_id` من `getTwUser()` (الـ snapshot ما فيه `tw_id`) — نفس `twEntryDestination()`.

```
❌ قراءة tw_user / tw_jwt مباشرة لقرار الدخول بصفحة محمية
❌ location.href = '/login' يدوي (بدون ?next=) أو guard ثاني بالصفحة
❌ أكتر من نداء twRequireAuth بالصفحة، أو نداء بعد أي fetch
❌ <meta name="tw-page" content="auth"> بدون twRequireAuth (أو العكس)
❌ twRequireAuth بصفحة entry (landing / login) — هدول عبر twEntryDestination()
```

---

## SHELL-07 — الممنوعات

```
❌ نسخ charset / viewport / theme-color / manifest / icons / Cairo / tw_shared.* / auth-sync.js يدوياً بصفحة فيها markers
❌ ?v= يدوي لـ tw_shared.css / tw_shared.js / auth-sync.js / tw-icons.js (بصفحة shell → {{v:tw-icons.js}})
❌ {{v:<name>}} بصفحة لاسم مش بـ PAGE_ASSETS، أو لملف shell (بيجي من الـ partials)
❌ partial ثاني أو آلية حقن ثانية (template engine / JS include) — page_shell.py هو الوحيد
❌ أي بيانات مستخدم أو request بالـ partials أو الحقن (§54)
❌ tw-icons.js بالـ shell (DS-ICON Phase C بيقرّر — F37)
❌ user-scalable=no / maximum-scale بالـ shell
❌ تحويل صفحة للـ shell بدون screenshots قبل/بعد (موبايل + ديسكتوب)
❌ خدمة partials/ مباشرة (برّا static/ عن قصد)
❌ manifest أو auth-sync.js بنسخة الأدمن
```

---

## SHELL-08 — المرحلة C (التحويل)

- **B ✅ (PR-8):** `page_shell.py` + partials + `read_html` + الصفحة التجريبية `home-v2.html` (screenshots قبل/بعد مطابقة بالبكسل بالـ sandbox).
- **C 🔜 (جاري):** PR لكل صفحة مع فحص بصري، بالترتيب: `job-detail` ✅ (أول صفحة — shell + `/static/tw_shared.js` + DS-ICON / DS-IMAGE / DS-SIZE / DS-FEEDBACK + session من `TwAuthSync.getSessionSnapshot()`؛ اختبار `python test_job_detail_shell.py`) ← `landing` ✅ (entry — بدون guard؛ التحويل عبر `twEntryDestination()` بس · صفحة الـ offline fallback: ملفات الـ shell + `tw-icons.js` بالـ precache بدون `?v=` و `ignoreSearch` offline — §32 · `apple-mobile-web-app-*` و `/icon-192.png` اليدوي انشالوا · SEO بالصفحة؛ اختبار `python test_landing_shell.py`) ← `appointments` ✅ + `appointment-room` ✅ (PR واحد — أول مستهلك لـ `twRequireAuth` SHELL-09 · `fetch` عبر `getAuthHeaders` · `alert()` → `showToast` · emoji / SVG → `twIcon` · أفاتار الطرف التاني `twAvatarEl` lg · `:root` المحلي → `--color-*` أو `--ap-*` بدون shadowing · `confirm()` ×3 بالغرفة باقية لحد نظام تأكيد DS-OVL؛ اختبار `node test_appointments_guard_runtime.js`) ← الباقي. التفاصيل + البنود المرافقة: `docs/FUTURE_ROADMAP.md` → Platform / Architecture.
- كل تحويل: شيل الـ tags المكرّرة + markers + تحديث أي اختبار بيقرأ الملف الخام ليقرأ ناتج `apply_shell` (مثال: `read_page()` بـ `test_global_ui_visibility.py`).
