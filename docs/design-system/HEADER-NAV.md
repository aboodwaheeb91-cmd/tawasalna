# Header & Bottom Nav V1 (DS-HNAV)

> هيدر واحد وشريط سفلي واحد لكل الموقع. صفحة بتحط placeholder، و `tw_shared.js` بيرسمه.
>
> **Runtime Source of Truth:** `tw_shared.js` → `twMountAppChrome()` · `_twHeaderHtml()` · `_TW_BOTTOM_NAV` / `twBottomNavItems()` · `twNavBack()` · `TW_LOGO_SRC` — والستايل بـ `static/app-header.css` (قسم «Unified App Header + Bottom Nav»).
> **أنظمة مرتبطة:** VM-10 (`initGlobalHeaderMenu` · `data-tw-session` — `docs/rules/vm10-header.md`) · DS-NAV NAV-05 / NAV-06 (الرجوع) · DS-ICON (`twIcon`) · DS-SIZE / DS-COLOR (tokens) · DS-SHELL (`PAGE-SHELL.md`).
> **الاختبار:** `python test_header_nav.py`.
> **PR:** 3.2 (2026-10-07).

---

## HNAV-00 — ليش JS مشترك ومش partial؟

| الخيار | ليش لأ / ليش أه |
|--------|-----------------|
| partial بالـ Page Shell (`<!--tw:header-->`) | الـ shell بيحقن نص ثابت بس (§54) وما بيعرف الجلسة. محتوى الهيدر والشريط بيعتمد على الجلسة ونوع الحساب والـ `tw_id` — يعني JS على كل حال. وكمان 4 من الصفحات المحوّلة (`edu-profile` · `settings` · `notifications` · `messages`) **مش** على الـ shell لسّا، فـ partial ما كان رح يوصلها. |
| **JS بـ `tw_shared.js`** ✅ | موجود على كل صفحة (shell أو لأ)، وفيه أصلاً الـ badges + القائمة + `twHomeHref` / `twAccountHref` / `twLoginHref`. ما في سكربت جديد ولا ترتيب تحميل جديد. ارتفاع الهيدر محجوز بالـ CSS قبل الرسم (`[data-tw-header]{height:var(--ah-h)}`) — ما في قفزة. |

---

## HNAV-01 — الاستعمال (صفحة)

```html
<link rel="stylesheet" href="/static/app-header.css">           <!-- بعد tw_shared.css -->
…
<body>
<header data-tw-header></header>                                 <!-- أول عنصر بالـ body -->
…
<nav data-tw-bottom-nav></nav>                                   <!-- اختياري -->
<!-- tw_shared.js → auth-sync.js → tw-icons.js (DS-ICON — بتحمّله الصفحة) → سكربتات الصفحة -->
```

- `twMountAppChrome()` بيشتغل لحاله عند `DOMContentLoaded` (مرة وحدة — `data-tw-mounted`).
- الهيدر بيحمل **تنقّل بس**. أزرار خاصة بالصفحة (تعديل، حفظ، عنوان) بتنحط بالصفحة نفسها تحت الهيدر — مثال: زر «تعديل الملف» بـ `edu-profile` (`#ownerActions` بكرت الجهة) وسطر عنوان الغرفة `.room-head` بـ `appointment-room`.
- الهيدر `position: sticky; top: 0` — الصفحة ما بتحط `padding-top` / `margin-top` تعويض.

---

## HNAV-02 — الترتيب الثابت

| الجلسة | الترتيب (يمين ← يسار بالـ RTL) |
|--------|-------------------------------|
| مسجّل | [رجوع؟] · رئيسية · **لوغو** (بالنص) · جرس · رسائل · قائمة ☰ |
| زائر | [رجوع؟] · **لوغو** (بالنص) · تسجيل الدخول · إنشاء حساب |

- المجموعتين موجودين بالـ DOM؛ `data-tw-session="authenticated|guest"` + `_twApplyDeclarativeVisibility()` (VM-10) بيختار — بيتحدّث لحاله مع أي تغيير جلسة.
- «تسجيل الدخول» = `twLoginHref(path + query)` (بيرجع لنفس الصفحة بعد الدخول — NAV-07) · «إنشاء حساب» = `/login#register` (VM-10 rule 4).
- القائمة = `initGlobalHeaderMenu('twHdrMenuBtn', 'twHdrMenuDd')` — بنودها من `_TW_HEADER_MENU_POLICY` بس.
- الأيقونة الحالية (جرس بـ `/notifications`، رسائل بـ `/messages`، رئيسية بـ `/home`) بتاخد `.is-current` + `aria-current="page"`.

---

## HNAV-03 — زر الرجوع (صفحات فرعية)

`<header data-tw-header data-back="…">` → زر رجوع **بنفس الهيدر** (مش هيدر تاني). القيمة = وين نروح لما ما في تاريخ موثوق داخل الموقع:

| `data-back` | الوجهة البديلة |
|-------------|----------------|
| `home` | `twHomeHref()` |
| `account` | `twAccountHref(tw_user)` (بدون `tw_id` → `twHomeHref()`) |
| `/internal/path` | المسار إذا مرق من `twSafeNext` (داخلي بس)، غير هيك `twHomeHref()` |

الضغط → `twNavBack(fallback)` (NAV-05): `history.state.nav.entryType === 'push'` → `history.back()` · `nav.context.from` آمن (مش `/login…`) → هو · غير هيك → الوجهة البديلة. ❌ `history.back()` مباشر (deep link بيطلع من الموقع).

| الصفحة | `data-back` |
|--------|-------------|
| `job-detail.html` | `home` |
| `settings.html` | `account` |
| `appointment-room.html` | `/appointments` |

---

## HNAV-04 — اللوغو

مصدر واحد: `TW_LOGO_SRC = '/static/33333.svg'` (`tw_shared.js`). ❌ نسخة Supabase (`…/site/33333.svg` أو `Logo.svg`) بأي صفحة محوّلة. (`applyNavLogo` / `.nav-logo` باقية للأدمن بس.)

---

## HNAV-05 — الشارات (جرس + رسائل)

- `<span class="tw-hdr-badge" data-badge="notif">` و `data-badge="msgs"` — بيعبّوهم `loadGlobalBadges()` (مرة عند الرسم) + Badge WS (`tw_shared.js`) + `applyMsgBadge` (`messages.ws.js`).
- **حد واحد للاثنين:** `twNotifBadgeLabel(count)` → `1..99` / `99+` (كان الرسائل `9+`).
- نفس الشكل للاثنين (`.tw-hdr-badge` — `--color-status-danger`).

---

## HNAV-06 — الشريط السفلي

تعريف واحد: `_TW_BOTTOM_NAV` → `twBottomNavItems(userType, u)`:

| key | emp | co | edu | href |
|-----|-----|----|-----|------|
| `home` | الرئيسية | الرئيسية | الرئيسية | `twHomeHref()` |
| `appointments` | مواعيد | مواعيد | مواعيد | `/appointments` |
| `messages` | رسائل | رسائل | رسائل | `/messages` |
| `notifications` | إشعارات | إشعارات | إشعارات | `/notifications` |
| `account` | ملفي (`user`) | شركتي (`briefcase`) | مؤسستي (`graduation-cap`) | `twAccountHref(u)` |

- ❌ `href="#"` أو href فاضي — كل بند إله وجهة حقيقية (فرص الموظف كانت `#` — انحذفت: الفرص فلتر جوّا `/home`).
- بند ممكن ياخد `types: ['co']` لو لزم بند خاص بنوع حساب.
- التبويب الحالي: `data-tw-current="<key>"` على الـ `<nav>`، أو تلقائي من المسار (`/home` · `/appointments` · `/messages` · `/notifications` · `/u/{own tw_id}`) → `.is-current` + `aria-current="page"`.
- **مسجّل بس** (الزائر: `hidden`) · **موبايل/تابلت بس** (`< 1020px`) · `body.tw-has-bnav` بيعطي مسافة تحت المحتوى — الصفحة ما بتحط `padding-bottom` خاص فيه.
- بيترسم من جديد بس لما يتغيّر `نوع|id|tw_id` (تسجيل واحد على `TwAuthSync.onSessionChange`).
- **النصوص (PR 3.6):** كل نص بالهيدر والشريط وقائمة الهيدر (تسميات · `aria-label` / `title` · alt اللوغو) مفتاح `twT` (`labelKey` بالـ registries · `_twLbl(key)` للأيقونات) — Strings System SYSTEMS_INDEX §59. ❌ نص عربي ثابت بـ `_twHeaderHtml` / `_TW_BOTTOM_NAV` / `_TW_HEADER_MENU_POLICY`.
- الصفحات اللي فيها الشريط: `home-v2` · `notifications` · `appointments` · `edu-profile`. بدونه: `messages` (شريط الكتابة تحت) · `job-detail` (شريط «تقدّم» الثابت) · `settings` · `appointment-room` (صفحات فرعية).

---

## HNAV-07 — حالة التحويل

| الصفحة | الحالة |
|--------|--------|
| `home-v2` · `notifications` · `messages` · `edu-profile` · `settings` · `appointments` · `appointment-room` · `job-detail` | ✅ PR 3.2 |
| `profile-showcase.html` | 🔜 المرحلة 4 — الهيدر فيه قسم «معاينة كزائر» ثابت داخل القائمة (`scEyeWrap` + `scMenuDynamic`) وأزرار مالك، و `profile-v2.css` فيه نسخة مجمّدة من `.sc-header` (SIZE-08)، ونفس الملفات فيها منطق المتابعة اللي ممنوع نلمسه هلّق. |
| `company-profile.html` | 🔜 المرحلة 4 — `.co-hdr` فيه أزرار مالك + `coMenuDynamic`، و `company.main.js` بيعتمد عليه، ونفس الصفحة فيها منطق المتابعة. |
| `landing.html` · `index.html` (login) · الأدمن | خارج النطاق — صفحات دخول / أدمن إلها هيدرها الخاص. |

---

## HNAV-08 — الممنوعات

```
❌ هيدر أو شريط سفلي خاص بصفحة (HTML / CSS / JS) — placeholder + twMountAppChrome فقط
❌ نسختين: صفحة محوّلة فيها .sc-header يدوي / .nav / .hdr / .bnav / hw-bnav / notif-bnav
❌ أزرار صفحة جوّا الهيدر (تعديل، لوحة تحكم، عنوان) — تحت الهيدر بالصفحة
❌ initGlobalHeaderMenu من صفحة محوّلة — الهيدر بيعمله
❌ لوغو من غير TW_LOGO_SRC · emoji / inline <svg> / lucide بالهيدر
❌ href="#" أو بند بدون href بالشريط السفلي · بند جديد خارج _TW_BOTTOM_NAV
❌ cap تاني للشارات (9+) — twNotifBadgeLabel بس
❌ history.back() مباشر لزر رجوع — twNavBack
❌ padding-top / margin-top تعويض للهيدر · padding-bottom للشريط بصفحة محوّلة
```
