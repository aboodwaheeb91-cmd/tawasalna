# U.0 — فحص البطاقات (Cards Audit)

> قراءة بس — ولا سطر كود اتعدّل بهالمهمة. التحليل كله من الكود، بدون screenshots.
> **المرجع المعتمد:** بطاقة المنشور بصفحة الشركة — `static/company/company.render.js → _postCardHtml()` + السلوك تبعها بـ `static/company/company.posts.js` + الـ CSS بـ `static/company/company.css` (قسم `POST CARDS`، تقريباً السطور 708–850).
> التاريخ: 2026-10-23 · قاعدة الفحص: `main` @ `d959201`.

---

## 0) ملاحظات قبل الجداول (F30)

| # | الملاحظة | الأثر على التقرير |
|---|----------|-------------------|
| 0.1 | **ما في نظام بطاقات موثّق.** ما في إدخال «Card» بـ `docs/SYSTEMS_INDEX.md`، ولا ملف بـ `docs/design-system/`. الموجود بس `.tw-card` / `.tw-card-sm` / `.tw-card-accent` بـ `tw_shared.css` (قسم «6. Cards»)، وهي **شبه مش مستعملة** (مكان واحد بكل الصفحات). | أي توحيد (القسم 5) معناه **نظام جديد** → لازم يتوثّق أول (SYSTEMS_INDEX + `docs/design-system/CARDS.md`) قبل أي كود. |
| 0.2 | **الثيمات s1–s5 مش موجودة بالكود.** بحثت بالـ CSS / JS / HTML / JSON / Python عن `s1`…`s5` وعن `data-theme`: ما في ولا ثيم بهالأسماء. الموجود: (أ) ثيم واحد بس (Dark Default — `ds-color.md` CLR-23، و`data-theme="light"` مؤجّل)، و(ب) **8 ألوان للمنشور** `TW.POST_THEME_COLORS` بـ `tw-options-data.js` (teal · blue · purple · orange · pink · red · gold · gray) بتنحفظ بعمود `company_posts.theme_color`. | قارنت عمود «الثيمات» على هالـ 8 ألوان. **إذا s1–s5 قصدك فيها شي تاني (تصميم مقترح؟) → لازم تعريف قبل أي تنفيذ.** |
| 0.3 | المنشورات حالياً **للشركات بس** (`company_posts`)؛ ما في منشورات لحساب شخصي أو جهة تعليمية، وما في صفحة «المنشورات المحفوظة». | بطاقة المنشور موجودة بمكانين بس: صفحة الشركة (المرجع) + الرئيسية. |

---

## 1) جدول كل الأماكن اللي بتعرض بطاقة

الرموز: **ز** = زائر (بدون حساب) · **ش** = حساب شخصي · **ك** = حساب شركة · **ت** = حساب جهة تعليمية · **أ** = أدمن.

### 1.أ بطاقات المنشور

| # | الصفحة | الملف · الدالة | مين بيشوفها |
|---|--------|----------------|-------------|
| P1 ⭐ | صفحة الشركة `/u/{C…}` — تبويب «المنشورات» | `static/company/company.render.js → _postCardHtml()` · `renderPosts()` · `_initPostClamps()` · الأزرار بـ `company.posts.js` (`_toggleAppreciation` · `_toggleSave` · `_toggleCommentPanel` · `_sharePost`) | ز · ش · ك · ت (المالك بيشوف قائمة ⋯ تعديل / حذف) |
| P2 | الرئيسية `/home` (`home-v2.html`) — الفلتر «الكل» و«المنشورات» | `static/home/home.cards.js → renderPostCard()` (عبر `renderCard()` ← `home.render.js → renderFeed()`) | ش · ك · ت (`twRequireAuth`) |

### 1.ب بطاقات الوظيفة

| # | الصفحة | الملف · الدالة | مين بيشوفها |
|---|--------|----------------|-------------|
| J1 | صفحة الشركة — تبويب «الوظائف» | `company.render.js → renderJobs()` (map جوّا الدالة) + `_buildTabHtml()` | ز · ش · ت (عرض الزائر) · ك المالك (عرض المالك — عقد مجمّد بـ `docs/company-jobs-and-applicants.md §2`) |
| J2 | الرئيسية — «الكل» و«الوظائف» | `home.cards.js → renderOpportunityCard()` | ش · ك · ت |
| J3 | تفاصيل الوظيفة `/job-detail` — «وظائف مشابهة» | `static/job/job-detail.js → loadSimilarJobs()` (`.jd-sim-item`) | ز · ش · ك · ت |
| J4 | بروفايل الموظف — تبويب «طلباتي» | `profile-v2.apps.js → _buildList()` (`.sc-app-card`) | ش (المالك بس) |
| J5 | الإشعارات `/notifications` — مجموعة طلبات التوظيف | `notifications.html → _appCard()` ← `_buildNotifCard()` | ش (عملياً — `/my/applications`) |
| J6 | لوحة الأدمن — قسم الوظائف (جدول، مش بطاقة) | `static/admin/admin.js → renderJobs()` (`table.adm-utable`) | أ |

### 1.ج بطاقات الشخص

| # | الصفحة | الملف · الدالة | مين بيشوفها |
|---|--------|----------------|-------------|
| U1 | صفحة الشركة — نافذة «المتقدمون» | `company.main.js → _renderApplicants()` (`.co-app-card`) | ك (المالك) |
| U2 | صفحة الشركة — «بنك المواهب» | `company.main.js → _savedCardHTML()` (`.co-cand-saved-card`) | ك (المالك) |
| U3 | صفحة الشركة — «اقتراحات» | `company.main.js → _suggItemHTML()` (`.co-cand-item.co-sugg-item`) | ك (المالك) |
| U4 | صفحة الشركة — نافذة «المتابعون» | `company.main.js → _renderItems()` (سطر ~1714، `.co-fl-item`) | ز · ش · ك · ت |
| U5 | بروفايل الموظف — نافذة «المتابعون / المتابَعون» | `profile-v2.render.js → _renderItems()` (سطر ~1298، `.sc-fl-item`) | ز · ش · ك · ت |
| U6 | الرسائل `/messages` — قائمة المحادثات | `messages.render.js → renderConvList()` (`.conv-item`) | ش · ك · ت |
| U7 | بروفايل الموظف — رأس الصفحة (بطاقة الشخص الكبيرة) | `profile-v2.render.js → renderProfile()` | ز · ش · ك · ت |
| U8 | بطاقة QR (صورة canvas) | `profile-v2.qr.js → _drawCard()` | ش (المالك — تصدير) |
| U9 | الأدمن — جدول المستخدمين | `admin.js → renderUsers()` (صف جدول) | أ |
| U10 | الأدمن — متقدمو وظيفة | `static/admin-job/admin-job.js → renderApplicants()` (`.tw-adm-row`) | أ |

### 1.د بطاقات الشركة / الجهة

| # | الصفحة | الملف · الدالة | مين بيشوفها |
|---|--------|----------------|-------------|
| C1 | صفحة الشركة — رأس الصفحة | `company.render.js → renderProfile()` + `renderStats()` | ز · ش · ك · ت |
| C2 | تفاصيل الوظيفة — بطاقة الشركة بالجنب | `job-detail.js → renderJob()` (`#jdCoCardAv` / `#jdCoCardName` / `#jdCoCardVerif`) | ز · ش · ك · ت |
| C3 | صفحة الجهة التعليمية — بطاقة الرأس + «قريباً» | `edu-profile.html` (`.ep-card`) | ز · ش · ك · ت |
| C4 | الأدمن — جدول المستخدمين بنوع شركة / جهة | `admin.js → renderUsers()` | أ |

> برّا النطاق (مش بيانات حقيقية): `landing.html` (`.profile-card` / `.value-card` / `.who-card` = بطاقات تسويقية ثابتة) · `appointments.html → renderCard()` (بطاقة موعد، مش شخص/شركة/وظيفة/منشور).

---

## 2) الفروقات عن المرجع

### 2.0 ملخّص المرجع (P1) — شو هو فعلياً

| البند | المرجع |
|-------|--------|
| التخطيط | `div.post-card` → رأس (لوغو 48px + اسم + سطر وقت · مشاهدات + ⋯) → نص مقصوص على 3 أسطر (قص بالـ JS ببحث ثنائي + زر «…⌄» / «⌃») → وسوم ملوّنة → صف أزرار 4 متساوية (`flex:1`) فوقه خط → لوحة تعليقات مخفية |
| الصورة والاسم | `<img>` يدوي جوّا `.post-ava` (48×48، زاوية 11px، خلفية تدرّج) — **مش `twAvatarHtml`** · الاسم `.post-nm` = `.8rem` / 800 · ما في رابط على الاسم / اللوغو |
| الأزرار | أقدّر (قلب) · تعليق (إذا `comments_enabled`) · مشاركة · حفظ (علامة) — كلها `button.pc-btn` بدون `type` |
| العدّادات | مشاهدات بالرأس (`_fmtViews` → «1.2K مشاهدة») · «أقدّر · N» · «تعليق · N» جوّا نص الزر · الحفظ بدون عدّاد |
| الألوان | لون المنشور `--pa` / `--pa-s` / `--pa-g` من `TW.POST_THEME_COLORS` (افتراضي teal) على الحدّ + الظل + الوسوم + أزرار «المزيد» + زر أقدّر الفعّال · الحفظ الفعّال = `--color-status-warning` |
| الخطوط والأحجام | rem ثابتة: اسم `.8rem` · وقت `.63rem` · نص `.8rem`/1.75 · زر `.72rem` · أيقونات زر 14px · زاوية 14px · padding `14px 16px` — **ولا قيمة من `--size-*`** |
| الأيقونات | **19 `<svg>` مكتوب يدوياً** بـ `company.render.js` + 8 بـ `company.posts.js` (نسخ مكررة من القلب والعلامة) — **مش DS-ICON (`twIcon`)** |
| التحميل / الفاضي / الخطأ | تحميل: ما في skeleton للمنشورات (فاضي لحد ما توصل البيانات) · فاضي: `#postsEmpty` (`company.posts_empty`) · خطأ: toast بس، ما في حالة بالقائمة ولا «إعادة المحاولة» |
| الثيمات | 8 ألوان منشور (القسم 0.2) |

### 2.1 بطاقة المنشور بالرئيسية (P2) ضد المرجع — **أكبر فرق**

| البند | المرجع P1 | الرئيسية P2 |
|-------|-----------|-------------|
| التخطيط | رأس + نص + وسوم + 4 أزرار + تعليقات | رأس + نص + «مشاركة» بس. **ما في وسوم** (السيرفر بيرجّعها `tags` وما بتنعرض) |
| الصورة والاسم | لوغو 48px مربّع مدوّر | `twAvatarEl(..., 'md')` **بدون `user_type: 'co'`** → شكل الأفاتار الدائري تبع الشخص، مش شكل لوغو الشركة · اسم 14px/700 |
| الكرت كلّه | مش قابل للضغط | الكرت كله رابط لصفحة الشركة (click على `article`) — بدون `<a>`، مش واصل بالكيبورد |
| تقدير | ✅ | ❌ (السيرفر ما بيرجّع `appreciations_count` / `viewer_appreciated` بـ `/home/feed`) |
| حفظ | ✅ | ❌ |
| تعليق | ✅ (لوحة كاملة + mentions) | ❌ |
| مشاركة | ✅ `navigator.share` / نسخ | **زر ميّت**: `span.hw-pact` بدون أي listener — الضغط عليه بيفتح صفحة الشركة (click الكرت) |
| العدّادات | مشاهدات + تقدير + تعليقات | ولا عدّاد · ما في تتبّع مشاهدة (`initPostViewTracking` مش مستدعى) |
| النص | قص 3 أسطر + «المزيد / أقل» | قص 3 أسطر بالـ CSS بس، **بدون أي طريقة لقراءة الباقي** |
| الألوان | `--pa` حسب لون المنشور | ما في لون منشور (`theme_color` مش بالـ SELECT) · ألوان عبر aliases محلية (`--muted` / `--g` / `--brd`) بـ `home-v2.css` |
| الخطوط والأحجام | rem | px ثابتة (14 / 13 / 11 / 12) — مقياس مختلف |
| الأيقونات | SVG يدوي | DS-ICON (`U.icon`) ✅ |
| الوقت | `_relativeTime` (محلي، ونص ثابت) | `Home.utils.timeAgo` (دالة تانية) |
| التحميل / الفاضي / الخطأ | toast بس | ✅ skeleton + فاضي + خطأ مع «إعادة المحاولة» (`home.render.js`) — **أحسن من المرجع** |
| ملكية | ⋯ تعديل / حذف | ما في |

### 2.2 بطاقات الوظيفة ضد المرجع (القواعد العامة: تخطيط، صورة، أزرار، ألوان…)

| البند | J1 صفحة الشركة | J2 الرئيسية | J3 مشابهة | J4 طلباتي | J5 الإشعارات |
|-------|----------------|-------------|-----------|-----------|--------------|
| التخطيط | صف أفقي مضغوط (لوغو · جسم · عمود أزرار) + تبويب حالة فوق | عمودي: رأس + chips + ذيل | سطر رابط (أيقونة + عنوان + شركة) | عمودي: عنوان · شركة · حالة · زرين | بطاقة إشعار عامة |
| الصورة | `<img>` يدوي + حرف (`.job-card-logo`) — مش DS-IMAGE | `twAvatarEl(co)` ✅ | أيقونة `building-2` بدل اللوغو | ما في | أيقونة نوع |
| الأزرار | زائر: «عرض التفاصيل» + مشاركة + حالة التقديم (أيقونة) · مالك: المتقدمون + الإدارة | «عرض الوظيفة» (رابط) | الكرت كله رابط | «عرض الوظيفة» + «صفحة الشركة» | ما في |
| مشاركة | ✅ (`company.jobs.js → _shareJob`) | ❌ | ❌ | ❌ | ❌ |
| العدّادات | عدد المتقدمين (مالك) + `—` لما ما ينقرا ✅ | ما في | ما في | ما في | ما في |
| الحالة | badge تحت اللوغو (`job-logo-status`) + تبويب عدّاد | ما في | ما في | `sc-app-status--*` | النص بالعنوان |
| النصوص | **نص عربي ثابت** («نشطة»، «عرض التفاصيل»، «عدد المتقدمين»، «منذ N أيام»…) — مش twT | twT ✅ | twT ✅ | twT ✅ | twT ✅ |
| التاريخ | حساب نسبي محلي جوّا `renderJobs` (تالت دالة وقت) | `timeAgo` | ما في | `twFormatDate` ✅ | `.slice(0,10)` خام (مش `twFormatDate`) |
| الأيقونات | 6 `<svg>` يدوية | DS-ICON ✅ | DS-ICON ✅ | ما في | — |
| الأحجام | padding `7px 10px` · زاوية 14px | 16px · زاوية 12px | — | `14px 16px` · زاوية 12px | — |
| التحميل / الفاضي / الخطأ | فاضي: `tw-empty` (SVG يدوي + نص ثابت) · تحميل: skeleton الصفحة العام | skeleton + فاضي + خطأ ✅ | فاضي `jd-sim-empty` · خطأ = نفس الفاضي (بيبلع الخطأ) | `_loadApps` | skeleton + فاضي + خطأ ✅ |
| الثيمات | لون حسب الحالة (active = أخضر) | — | — | لون حسب الحالة | — |

### 2.3 بطاقات الشخص ضد المرجع

| البند | U1 المتقدمون | U2 بنك المواهب | U3 اقتراحات | U4 متابعو الشركة | U5 متابعو البروفايل | U6 المحادثات |
|-------|--------------|----------------|-------------|------------------|---------------------|---------------|
| الصورة | `twAvatarHtml(emp,'md')` ✅ | `twAvatarHtml` ✅ | `twAvatarHtml` ✅ | `twAvatarEl(type,'md')` ✅ | **`<img>` يدوي + `data-lucide="user"`** ❌ | `twAvatarHtml` ✅ |
| الاسم | `.co-app-name` | `.co-csc-name` | `.co-cand-name` | `.co-fl-name` | `.sc-fl-name` (جوّا `<a>`) | `.ci-name` + شارة نوع |
| رابط البروفايل | زر «عرض الملف» | داخل اللوحة | زر «فتح الملف» | **ما في رابط** | الكرت كله `<a>` ✅ | بيفتح المحادثة |
| زر المتابعة | — | — | — | `co-fl-follow-btn` (نص ثابت «تابع / متابَع») | `sc-fl-follow-btn` (نفس الشي، class تاني) | — |
| شارة النوع | — | — | — | نص ثابت «موظف / شركة / تعليمية» (مش مصطلحات GLOSSARY) | `_typeBadge` | `typeBadgePillHtml` |
| حالة | `co-app-status--*` | badge أولوية + نجوم | `%` توافق | — | — | عدّاد غير مقروء |
| الأزرار | 5 (عرض · تصنيف · بنك · ملاحظات · موعد) — `twScheduleButton` ✅ · الباقي مش `twAction` | لوحة إدارة | 3 (فتح · حفظ · موعد) | متابعة | متابعة | — |
| الأيقونات | — | DS-ICON ✅ | — | — | Lucide CDN (`data-lucide` + `lucide.createIcons()`) ❌ | DS-ICON |
| الفاضي / التحميل | `co-app-empty` | — | زر «عرض المزيد» | `co-fl-spin` (نص ثابت «جاري التحميل...») | `sc-fl-spin` / `sc-fl-empty` (نص ثابت) | `conv-empty` (twT) |

### 2.4 بطاقات الشركة

| البند | C1 رأس صفحة الشركة | C2 بطاقة الشركة بتفاصيل الوظيفة | C3 الجهة التعليمية |
|-------|--------------------|---------------------------------|--------------------|
| الصورة | لوغو الصفحة (`renderProfile`) | `twAvatarHtml(co,'lg')` ✅ | `twAvatarEl` ✅ |
| التوثيق | شارة بالرأس | «شركة موثّقة» + `check` | — |
| العدّادات | منشورات · مشاهدات · متابعون · تقييم (`_fmtCount`) | ما في | ما في |
| الأزرار | متابعة · مراسلة · مشاركة · تقييم (`twAction` جزئياً) | رابط الاسم بس | — |

> **الخلاصة:** ما في مكانين بيرسموا نفس النوع بنفس الشكل. كل صفحة عندها CSS خاص (`post-*` / `hw-*` / `job-card` / `jd-sim-*` / `sc-app-*` / `co-app-*` / `co-fl-*` / `sc-fl-*` / `conv-item`)، وزوايا بين 10 و16px، وpadding بين `7px 10px` و`16px`، ومقياس خط مرة rem ومرة px.

---

## 3) الكود المكرر

| # | التكرار | الأماكن | ملاحظة |
|---|---------|---------|--------|
| D1 | **دالة «منذ …» (وقت نسبي)** — 5 نسخ | `company.render.js → _relativeTime` · `company.render.js → renderJobs` (inline `relDate`) · `company.posts.js → _formatRelativeTime` · `home.utils.js → timeAgo` · `job-detail.js → _timeAgo` (+ `messages → convTimeLabel`) | `_relativeTime` بيرجّع `toLocaleDateString('ar')` بعد الشهر — مخالف لقاعدة `twFormatDate` (CLAUDE.md Strings §4) |
| D2 | **SVG القلب والعلامة** — نسختين حرفيتين | `company.render.js → _postCardHtml` (`icoHeart*` / `icoBookmark*`) + `company.posts.js` (`_ICO_HEART_*` / `_ICO_BOOKMARK_*`) | لو تغيّر واحد بيصير الزر يتغيّر شكله بعد أول ضغطة |
| D3 | **نص الزر «أقدّر · N» / «حفظ / محفوظ»** — نسختين | `_postCardHtml` (رسم أول) + `_renderAppreciationButton` / `_renderSaveButton` (بعد الضغط) | نفس المنطق بمكانين + نص ثابت مش twT |
| D4 | **المشاركة + نسخ fallback** — 3 نسخ | `company.posts.js → _sharePost` + `_sharePostFallback` · `company.jobs.js → _shareJob` + `_shareFallback` · `company.render.js → _shareCompany` + `_copyText` | `document.execCommand('copy')` منسوخ 3 مرات |
| D5 | **قائمة المتابعين** — نظامين كاملين | `company.main.js` (`co-fl-*`، ~1690–1830) · `profile-v2.render.js` (`sc-fl-*`، ~1220–1340) + CSS بـ `company.css` (~1659) و`profile-v2.css` (~1246) | نفس الـ endpoint، نفس الفلاتر، نفس زر المتابعة — شكلين مختلفين |
| D6 | **تنسيق العدّاد المختصر** — 4 نسخ | `company.render.js → _fmtCount` / `_fmtViews` · `company.posts.js → _fmtViewsCount` · `profile-v2 → formatCompactCount` | في `twFormatNumber` مشترك بس ما في «مختصر» مشترك |
| D7 | **شارة الحالة (pill)** — 4 أنظمة | `job-logo-status--*` · `co-app-status--*` · `sc-app-status--*` · `tw-adm-pill is-*` | كل وحدة ألوانها وأحجامها |
| D8 | **`.tw-card-lift`** — معرّفة مرتين | `company.css` (~1416) + `index.css` (~266) بقيم ظل مختلفة | والـ `.tw-card` الرسمية بـ `tw_shared.css` شبه مهجورة |
| D9 | **لوغو / أفاتار يدوي** بدل DS-IMAGE | `_postCardHtml` (`.post-ava`) · `renderJobs` (`.job-card-logo`) · `profile-v2.render.js → _renderItems` (`.sc-fl-avatar`) | مخالف F38 — ما في `onerror` fallback، وما في شكل حسب النوع |
| D10 | **skeleton** — 3 طرق | `tw-skeleton.css` + `.co-sk-*` (الشركة) · `.hw-skl/.hw-skc/.hw-skr` + `@keyframes hw-p` (الرئيسية — HTML inline styles) · `.sc-sk-*` | SYSTEMS_INDEX بيقول `tw-skeleton.css` هو المصدر؛ الرئيسية عاملة نسختها |
| D11 | **حالة فاضي** — 5 أشكال | `tw-empty` (+ SVG يدوي) · `#postsEmpty` · `hw-empty` · `co-app-empty` · `sc-fl-empty` / `jd-sim-empty` | |
| D12 | **أسماء escape محلية** | `company.render.js → _esc` / `_escAttr` | aliases مباشرة لـ `twEscHtml` / `twEscAttr` (سطر 14–15) — مش تنفيذ تاني، بس القاعدة بتطلب حذف الـ helpers المحلية لما الصفحة تنلمس |

---

## 4) نقاط ضعف بالمرجع نفسه (اقتراحات — بدون تنفيذ)

**التناسق مع أنظمة المشروع**
1. **نصوص ثابتة بدل twT:** «أقدّر» · «تعليق» · «مشاركة» · «حفظ / محفوظ» · «الشركة» · «خيارات» · «تعديل» · «حذف» · «عرض المزيد / أقل» · «مشاهدة» · «الآن / منذ …» · toasts المشاركة والحفظ. → كلها مفاتيح `post.*` (بعضها موجود: `action.share`).
2. **الأيقونات SVG يدوية (27 نسخة)** → `twIcon('heart' | 'bookmark' | 'comment' | 'share' | 'eye' | 'clock' | 'edit' | 'delete' | 'more')` (F37). حتى أيقونة المشاركة بالمنشور (3 دوائر) غير أيقونة مشاركة الوظيفة (سهم لفوق) بنفس الصفحة.
3. **اللوغو مش DS-IMAGE** → `twAvatarHtml({…, user_type:'co'}, 'md')` (F38) — بيضيف fallback عند فشل الصورة.
4. **الأحجام ثابتة** (`.8rem` / `.63rem` / `14px` / `48px` / `14px` radius) → `--size-font-*` / `--radius-*` / `--space-*` / `--size-avatar-md` (F36).
5. **التاريخ بعد 30 يوم = `toLocaleDateString('ar')`** → `twFormatDate` (قاعدة Strings §4).
6. **الأزرار مش `twAction`** — شرط ظهور زر التعليق (`comments_enabled`) وقائمة ⋯ (`can_edit`) مكتوبين بالصفحة (BTN-19 بيمنع شرط ظهور بالصفحة).
7. **الحفظ لونه `--color-status-warning`** (لون تحذير) — معناه غلط؛ الأفضل token مخصص (`--color-action-save` مثلاً) أو `--pa`.

**الوضوح**
8. **ما في رابط على اللوغو / الاسم** — بصفحة الشركة مقبول، بس لما تنعاد البطاقة بالرئيسية لازم الاسم يكون `<a>` لـ `/u/{tw_id}`.
9. **المشاركة بتشارك رابط الشركة مش المنشور** (`_sharePost` → `/u/{tw_id}`) — المستلم ما بيوصل للمنشور نفسه. محتاج رابط منشور (`/u/{tw_id}?post={id}` أو public_id بادئة `P` حسب قاعدة 9 بالـ Smart Router) → **F30: ما في عقد رابط منشور حالياً.**
10. **المشاهدات بالرأس جنب التاريخ بنفس الحجم** — ممكن تنقرا كجزء من التاريخ؛ الأوضح تنتقل لصف العدّادات أو تاخد أيقونة أوضح.
11. **العدّاد جوّا نص الزر** («أقدّر · 12») بيغيّر عرض الزر مع كل ضغطة (قفزة بالتخطيط) — الأفضل عدّاد بـ `span` منفصل بعرض ثابت (`tabular-nums`).

**الموبايل**
12. **4 أزرار `flex:1` + `white-space:nowrap`** — على 320px مع «أقدّر · 128» و«تعليق · 45» النص بيطلع برّا الزر. اقتراح: تحت عرض معيّن أيقونة + رقم بس (والنص بـ `aria-label`).
13. **القص بالبحث الثنائي بيشتغل مرة وحدة** (بعد rAF مزدوج) — ما في إعادة حساب عند تدوير الشاشة / تغيير العرض، فالنص المقصوص بيضل مقصوص على عرض قديم. اقتراح: `ResizeObserver` أو الرجوع لـ `line-clamp` CSS بس + زر «المزيد» تحت النص.
14. **قائمة ⋯ `position:absolute; left:14px`** — ثابتة على اليسار (مش `inset-inline-end`) ومش عبر DS-OVL؛ ممكن تنقص برّا الشاشة على الموبايل.

**Accessibility**
15. **`<div class="post-card">`** → `<article aria-labelledby>` (الرئيسية أصلاً `article`).
16. **أزرار التبديل بدون حالة:** أقدّر / حفظ لازم `aria-pressed="true|false"`، وزر التعليق `aria-expanded` + `aria-controls="pc-cmt-panel-{id}"`.
17. **كل `button` بدون `type="button"`** (`.pc-btn` · `.pc-dots-btn` · `.pc-dots-edit` · `.pc-dots-delete`).
18. **قائمة ⋯:** بدون `aria-haspopup` / `aria-expanded` / `role="menu"`، وما في إغلاق بـ Escape ولا رجوع الـ focus للزر.
19. **الـ SVG بدون `aria-hidden="true"`** (القارئ بيقرا أشكال فاضية) · الأفاتار `alt=""` مقبول بس لأن الاسم جنبه.
20. **ما في `:focus-visible`** على `.pc-btn` / `.post-more-inline` (التركيز بالكيبورد مش واضح على خلفية غامقة).
21. **لون النص الثانوي** (`--color-text-muted` على `.63rem`) — حجم صغير جداً (~10px) لازم يتفحص تباين AA.

**الحالات**
22. **ما في skeleton للمنشورات ولا حالة خطأ بالقائمة** — الخطأ toast بس والقائمة بتضل فاضية بدون «إعادة المحاولة». (الرئيسية عاملتها صح — يُنقل نمطها.)
23. **ما في pagination** — `GET /company/posts/{id}` بيرجّع الكل (قارن قاعدة Input Limits: «❌ endpoint بيرجّع كل … بدون صفحات»).

---

## 5) خطة توحيد مقترحة

### 5.1 المبدأ

نظام واحد **DS-CARD** (جديد — لازم يتوثّق أول: `docs/design-system/CARDS.md` + إدخال SYSTEMS_INDEX + سطر بجدول «قوانين الأنظمة» بـ CLAUDE.md). مكوّن واحد لكل نوع بطاقة، بيرجّع **DOM element** (createElement + textContent متل `home.cards.js` — أأمن من نص HTML)، والصفحة بتمرّق البيانات + السياق بس. كل الأزرار عبر `twAction`، الصور عبر `twAvatarEl`، الأيقونات عبر `twIconEl`، النصوص عبر `twT`، الأحجام من `--size-*`.

### 5.2 المكوّنات والـ API

| المكوّن | الملف | الـ API المقترح | بيستبدل |
|---------|-------|------------------|---------|
| أساس مشترك | `static/shared/tw-card.css` (+ helpers بـ `tw_shared.js`) | classes: `.tw-card` (إعادة تعريف القائم) · `__head` · `__body` · `__foot` · `__actions` · modifiers `--compact` / `--interactive` · `twTimeAgo(iso)` · `twFormatCompact(n)` · `twShare({title, text, url})` | D1 · D4 · D6 · D8 · D10 (skeleton موحّد `twCardSkeleton(kind, n)`) · D11 (`twEmptyState({icon, titleKey, subKey, retry})`) |
| بطاقة منشور | `static/shared/tw-post-card.js` | `TwPostCard.render(post, { viewer, mode: 'full' \| 'feed', onChange })` → `HTMLElement` · `TwPostCard.mount(container)` (event delegation واحدة: أقدّر / حفظ / تعليق / مشاركة / ⋯) · منطق «desired-state queue» للأقدّر والحفظ ينتقل من `company.posts.js` كما هو | `_postCardHtml` + `renderPostCard` + D2 · D3 |
| بطاقة وظيفة | `static/shared/tw-job-card.js` | `TwJobCard.render(job, { variant: 'owner' \| 'visitor' \| 'feed' \| 'compact' \| 'application', viewer })` | `renderJobs` (map) · `renderOpportunityCard` · `jd-sim-item` · `sc-app-card` |
| بطاقة شخص | `static/shared/tw-person-card.js` | `TwPersonCard.render(person, { variant: 'row' \| 'applicant' \| 'candidate' \| 'conv', actions: [actionIds], meta })` | `co-fl-*` + `sc-fl-*` (D5) · لاحقاً `co-app-card` / `co-cand-*` / `conv-item` |
| بطاقة شركة | `static/shared/tw-org-card.js` | `TwOrgCard.render(org, { variant: 'side' \| 'row', stats })` | بطاقة `job-detail` الجانبية · `ep-card` |
| شارة حالة | ضمن `tw-card.css` | `twStatusPill(kind, status)` — ألوان من tokens | D7 |

**عقد البيانات (F29):** كل endpoint بيرجّع منشور (`/company/posts/{id}` و`/home/feed`) لازم يرجّع **نفس الحقول** للمنشور: `id · body · tags · theme_color · comments_enabled · created_at · views_count · appreciations_count · viewer_appreciated · comments_count · viewer_saved · author{id, tw_id, full_name, avatar_url, user_type}`. حالياً `/home/feed` ناقصه نصّها → **تغيير عقد** (F14: إضافة حقول بس، ما في كسر).

### 5.3 ترتيب PRs صغيرة

| PR | المحتوى | اختبار مركّز | المخاطرة |
|----|---------|--------------|----------|
| U.1 | **توثيق DS-CARD بس** (CARDS.md + SYSTEMS_INDEX + CLAUDE.md) + قرار s1–s5 (القسم 0.2) + قرار رابط المنشور (اقتراح 9) | — | صفر |
| U.2 | تنظيف المرجع بمكانه (بدون نقل): twT لكل النصوص · `twIcon` بدل 27 SVG · `twAvatarHtml` · `twFormatDate` · `aria-pressed` / `aria-expanded` / `type="button"` · حذف نسخ D2/D3 | runtime vm: الزر بيتبدّل + aria-pressed | منخفضة |
| U.3 | `tw-card.css` + helpers المشتركة (`twTimeAgo` · `twFormatCompact` · `twShare` · `twEmptyState` · `twCardSkeleton`) + تحويل D1/D4/D6 بصفحة الشركة | input → output للـ helpers | منخفضة |
| U.4 | `TwPostCard` من المرجع (نقل حرفي للسلوك) + صفحة الشركة بتستعمله + skeleton / خطأ مع إعادة المحاولة | runtime: render → عناصر + أزرار | متوسطة |
| U.5 | `/home/feed` بيرجّع عقد المنشور الكامل + الرئيسية بتستعمل `TwPostCard` mode `feed` (تقدير / حفظ / مشاركة شغّالين، تعليق = رابط للمنشور) | endpoint بيرجّع الحقول | متوسطة (backend) |
| U.6 | `TwPersonCard` variant `row` + توحيد قائمتي المتابعين (D5) | runtime | منخفضة |
| U.7 | `TwJobCard` variants `feed` / `compact` / `application` (الرئيسية · مشابهة · طلباتي · الإشعارات) | runtime | منخفضة |
| U.8 | `TwJobCard` variant `owner` / `visitor` لصفحة الشركة — **العقد المجمّد بـ `company-jobs-and-applicants.md §2` بيضل نفسه**، بس النصوص twT والأيقونات DS-ICON | runtime + فحص العقد | متوسطة |
| U.9 | `TwOrgCard` (job-detail · edu) + `twStatusPill` (D7) | runtime | منخفضة |
| U.10 | (اختياري) بطاقات الشركة الداخلية: المتقدمون / بنك المواهب / الاقتراحات → `TwPersonCard` variants — كبيرة، تتقسم لكل وحدة PR | runtime | عالية (منطق pipeline) |

> كل PR بيمرق على `python tools/page_audit.py` (ما يزيد رقم) + القائمة الموحّدة للصفحة اللي بينلمسها.

---

## ما لم يُفحص

- ما شغّلت الصفحات (ممنوع screenshots) — كل الفروقات البصرية مستنتجة من الـ CSS والـ JS.
- ما فحصت تباين الألوان بالأرقام (اقتراح 21 بحاجة قياس).
- لوحة التعليقات جوّا بطاقة المنشور (`_cmtBuildItem` …) — نظام مستقل (`docs/rules/post-comments.md`)، برّا هالفحص.
