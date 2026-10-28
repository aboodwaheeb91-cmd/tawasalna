# [DS-CARD] Card System V1 — نظام البطاقات الموحّد

> **النظام الرسمي الوحيد لكل بطاقة بتعرض بيانات حقيقية بتواصلنا:** منشور · وظيفة · شخص · شركة / جهة تعليمية.
> **الحالة:** 🟡 U.2 منفّذ كامل (رسم بطاقة المنشور + سلوك أزرارها بـ `static/shared/tw-post-card.js` + CSS بـ `static/shared/tw-card.css` — بدون تغيير شكل ولا سلوك؛ القسم CARD-13) · ✅ U.3 (تنظيف المكوّن — CARD-13 → U.3) · الباقي U.4 → U.10 (القسم CARD-12).
> **المرجع (المصدر):** بطاقة المنشور بصفحة الشركة — `static/company/company.render.js → _postCardHtml()` · `renderPosts()` · `_initPostClamps()` + السلوك بـ `static/company/company.posts.js` (`_toggleAppreciation` · `_toggleSave` · `_toggleCommentPanel` · `_sharePost` · `initPostViewTracking` · `deletePost`) + الـ CSS بـ `static/company/company.css` (قسم `POST CARDS` + `POST COMMENTS PANEL`).
> **التقرير:** `docs/audits/cards-audit.md` (U.0 — PR #641). أرقام الأماكن (P1 · J1 · U1 · C1 …) والتكرار (D1 … D12) من التقرير نفسه.
> **الأنظمة اللي بيعتمد عليها (ما بيعيد بناءها):** DS-IMAGE (F38) · DS-ICON (F37) · DS-SIZE (F36) · DS-COLOR (F35) · DS-OVL (F33) · DS-FEEDBACK (F34) · Actions Registry (BTN-19 · SYSTEMS_INDEX §60) · Strings `twT` (§59) · `twFormatDate` / `twFormatNumber` (§59a) · Skeleton `tw-skeleton.css` (§35) · Blocks + Suspension (`docs/rules/blocks-suspension.md` · §25f) · Post Appreciation / Save / Comments (§22a / §22b / §22c).

---

## [CARD-00] Routing — شو تقرا

| المهمة | اقرأ |
|--------|------|
| أي تعديل على بطاقة منشور | CARD-02 + CARD-03 (منشور) + CARD-04 + CARD-07 + CARD-09 |
| بطاقة وظيفة / شخص / شركة | CARD-02 + CARD-03 (النوع) + CARD-04 + CARD-05 |
| رابط المنشور `/post/{id}` | CARD-08 |
| شو المطلوب ومتى | CARD-10 (المتطلبات) + CARD-12 (الخطة) |
| بطاقة جديدة ما إلها نوع هون | **STOP (F30)** — اشرح وانطر قرار قبل أي كود |

---

## [CARD-01] المبادئ

1. **مكوّن واحد لكل نوع** (منشور · وظيفة · شخص · شركة) فوق **أساس واحد** (`tw-card`). الصفحة بتمرّق البيانات + السياق (`viewer` · `variant` · `ctx`) بس — ما بتبني HTML بطاقة لحالها.
2. **DOM مش نص HTML:** المكوّن بيرجّع `HTMLElement` (`createElement` + `textContent`) — نفس نمط `home.cards.js`. بيانات المستخدم ما بتمرق على `innerHTML` أبداً (§54).
3. **كل جزء من نظامه:** صورة / لوغو → `twAvatarEl` · أيقونة → `twIconEl` · نص → `twT` · تاريخ → `twFormatDate` / وقت نسبي مشترك · عدد → `twFormatNumber` · زر إجراء → `twAction` · قائمة / تأكيد → DS-OVL · toast → DS-FEEDBACK · قياس → `--size-*` / `--space-*` / `--radius-*` · لون → `--color-*`.
4. **البطاقة ما بتقرّر مين بيشوف شو:** الظهور (حظر / تعليق / حذف) من السيرفر بس (CARD-07)، وظهور الأزرار من السجل (`twAction`) بس — ما في شرط ظهور بالصفحة (BTN-19).
5. **عقد بيانات واحد لكل نوع (F29):** كل endpoint بيرجّع نفس النوع بيرجّعه بنفس الحقول (CARD-03 → «عقد البيانات»). إضافة حقول بس — ما في كسر (F14).
6. **المرجع بيتحوّل أول:** بطاقة منشور صفحة الشركة بتصير `TwPostCard` بسلوكها الحالي حرفياً (U.2)، وبعدين كل التحسينات بتنعمل بالمكوّن المشترك — مش بالصفحة.

---

## [CARD-02] التشريح (Anatomy)

```
article.tw-card[.tw-card--{type}][.tw-card--{variant}]   ← aria-labelledby = id الاسم
├── __head      (رأس)
│   ├── __media      صورة / لوغو — twAvatarEl(entity, size)          [إجباري بالمنشور والشخص والشركة · اختياري بالوظيفة compact]
│   ├── __title      الاسم / العنوان — <a href="/u/{tw_id}"> لما في رابط [إجباري]
│   ├── __subtitle   سطر تاني (مسمّى · شركة · مدينة)                 [اختياري]
│   ├── __meta       الوقت (+ مشاهدات بالمنشور)                       [اختياري — إجباري بالمنشور]
│   └── __menu       زر ⋯ ← قائمة إجراءات (DS-OVL)                    [اختياري — بيبين بس إذا في إجراء واحد على الأقل من السجل]
├── __body      (جسم)    نص مقصوص + «المزيد / أقل» · وسوم · chips      [إجباري بالمنشور · اختياري بالباقي]
├── __media-block (وسائط)  صور / مرفقات                               [اختياري — ما في وسائط بالمنشورات حالياً؛ محجوز]
├── __stats     (عدّادات) span منفصل لكل عدّاد، tabular-nums          [اختياري]
├── __actions   (شريط تفاعل) أزرار twAction بس                         [اختياري — بالمنشور: أقدّر · تعليق · مشاركة · حفظ]
└── __comments  (تعليقات) لوحة post-comments (§22c)                    [اختياري — بالمنشور بس، ولما comments_enabled]
```

| الجزء | المرجع اليوم (P1) | قاعدة DS-CARD |
|-------|-------------------|---------------|
| الحاوية | `div.post-card` | `article.tw-card` + `aria-labelledby` (R15) |
| الصورة | `<img>` يدوي جوّا `.post-ava` 48px | `twAvatarEl({…, user_type}, 'lg')` (R03) — الشكل حسب النوع (emp دائرة · co / edu مربع) |
| الاسم | `.post-nm` نص، بدون رابط | `<a href="/u/{tw_id}">` لما البطاقة برّا صفحة صاحبها (R08) |
| الوقت | `_relativeTime` محلي + `toLocaleDateString('ar')` | وقت نسبي مشترك + `twFormatDate` بعد الحد (R05) |
| المشاهدات | بالرأس جنب الوقت | بـ `__stats` أو بأيقونة أوضح (R10) |
| ⋯ | `position:absolute; left:14px` + menu يدوي | `inset-inline-end` + قائمة DS-OVL + aria (R14 · R18) |
| النص | قص 3 أسطر ببحث ثنائي مرة وحدة | `line-clamp` CSS أو إعادة حساب عند تغيّر العرض (R13) |
| الأزرار | 4 `button.pc-btn` نص ثابت + SVG يدوي | `twAction` + `twIconEl` + `twT` + `type="button"` + `aria-pressed` / `aria-expanded` (R01 · R02 · R06 · R16 · R17) |
| العدّاد | جوّا نص الزر («أقدّر · 12») | `span` منفصل بعرض ثابت (R11) |
| التعليقات | `.pc-cmts-panel` مخفية | نفس النظام (§22c) — ما بيتغيّر |

**الترتيب (RTL):** المحتوى بيمشي من اليمين؛ الصورة أول عنصر بالرأس، و`__menu` بآخره (`inset-inline-end`).

---

## [CARD-03] الأنواع (Variants)

### الأساس المشترك (`tw-card`) — بياخده كل نوع

الحاوية + الحدّ + الزاوية + الـ padding + الظل + `:hover` · رأس (صورة + اسم + meta) · حالات CARD-05 (skeleton · فاضي · خطأ) · قواعد CARD-06 (RTL · موبايل · وصول) · قاعدة الظهور CARD-07.

### 1) بطاقة منشور — `TwPostCard` (P1 ⭐ · P2)

| الـ variant | المكان | بياخد من الأساس | بيزيد |
|-------------|--------|-----------------|-------|
| `full` (المرجع) | صفحة الشركة (P1) · صفحة المنشور `/post/{id}` (CARD-08) | كل الأساس | لون المنشور (`--pa` / `--pa-s` / `--pa-g` من `TW.POST_THEME_COLORS`) · قص النص + «المزيد / أقل» · وسوم ملوّنة · مشاهدات + تتبّع مشاهدة · شريط تفاعل 4 أزرار · لوحة تعليقات · قائمة ⋯ للمالك (تعديل / حذف) |
| `feed` | الرئيسية (P2) | كل الأساس | نفس `full` بدون لوحة التعليقات جوّا البطاقة (التعليق → رابط المنشور — **سؤال مفتوح Q4**) · الاسم رابط لـ `/u/{tw_id}` |

**عقد البيانات (منشور):** `id · body · tags · theme_color · comments_enabled · created_at · views_count · appreciations_count · viewer_appreciated · comments_count · viewer_saved · author{id, tw_id, full_name, avatar_url, user_type}`. اليوم `/company/posts/{id}` بيرجّع معظمها (المؤلف من `companyState.profile`)، و`/home/feed` ناقصه التقدير / الحفظ / التعليقات / اللون → U.7.

### 2) بطاقة وظيفة — `TwJobCard` (J1 → J5)

| الـ variant | المكان | بياخد من الأساس | بيزيد |
|-------------|--------|-----------------|-------|
| `visitor` | صفحة الشركة — تبويب الوظائف للزائر (J1) | رأس (لوغو + عنوان + وقت) | «عرض التفاصيل» · مشاركة · حالة التقديم — **العقد المجمّد بـ `docs/company-jobs-and-applicants.md §2` بيضل نفسه** |
| `owner` | صفحة الشركة — المالك (J1) | رأس | شارة حالة الوظيفة · عدد المتقدمين (`—` لما ما ينقرا) · «المتقدمون» · «الإدارة» (نفس العقد المجمّد) |
| `feed` | الرئيسية (J2) | رأس + جسم (chips) | «عرض الوظيفة» (رابط) |
| `compact` | تفاصيل الوظيفة — «وظائف مشابهة» (J3) | رأس بس (بدون جسم) | البطاقة كلها `<a>` |
| `application` | بروفايل الموظف — «طلباتي» (J4) · الإشعارات (J5) | رأس | شارة حالة الطلب (`twStatusPill`) · «عرض الوظيفة» · «صفحة الشركة» |

> J6 (جدول وظائف الأدمن) **مش بطاقة** — بيضل جدول Admin Shell (`docs/rules/admin-shell.md`)، برّا DS-CARD.

### 3) بطاقة شخص — `TwPersonCard` (U1 → U8)

| الـ variant | المكان | بياخد من الأساس | بيزيد |
|-------------|--------|-----------------|-------|
| `row` | نافذة «المتابعون / المتابَعون» للشركة (U4) وللبروفايل (U5) | رأس (أفاتار + اسم رابط + شارة نوع) | زر متابعة (`twAction('follow')`) — يوحّد D5 |
| `conv` | الرسائل — قائمة المحادثات (U6) | رأس | آخر رسالة · وقت · عدّاد غير مقروء — بيفتح المحادثة (`docs/rules/messenger.md`) |
| `applicant` | نافذة «المتقدمون» (U1) | رأس + سطر حالة | أزرار الـ pipeline (عرض · تصنيف · بنك · ملاحظات · موعد) — **منطق الـ pipeline ما بيتغيّر** |
| `candidate` | «بنك المواهب» (U2) · «اقتراحات» (U3) | رأس | أولوية / نجوم (U2) · `%` توافق (U3) · فتح · حفظ · موعد (`twScheduleButton`) |
| `hero` | رأس بروفايل الموظف (U7) | — (برّا الأساس — بطاقة الصفحة) | توثيق بس؛ ما بتتحوّل لمكوّن (سؤال مفتوح Q11) |

> U8 (QR — canvas) · U9 / U10 (جداول الأدمن) **مش بطاقات DOM** — برّا DS-CARD.
> `applicant` / `candidate` بيدخلوا بس بعد U.10 (سؤال مفتوح Q11) — المرحلة U.10 بتوحّد الأساس تبعهم بس، بدون لمس منطق الـ pipeline.

### 4) بطاقة شركة / جهة — `TwOrgCard` (C1 → C3)

| الـ variant | المكان | بياخد من الأساس | بيزيد |
|-------------|--------|-----------------|-------|
| `side` | تفاصيل الوظيفة — بطاقة الشركة بالجنب (C2) | رأس (لوغو `lg` + اسم رابط) | شارة «موثّقة» |
| `row` | قوائم مستقبلية (بحث / اقتراح شركات) | رأس | زر متابعة |
| `hero` | رأس صفحة الشركة (C1) · رأس الجهة التعليمية (C3) | — | توثيق بس؛ رأس الصفحة مش بطاقة قائمة (Q11) |

> C4 (جدول الأدمن) برّا DS-CARD.

---

## [CARD-04] التوكنز (أسماء موجودة فعلياً بـ `tw_shared.css`)

> القيم بين قوسين للتوضيح. «المرجع اليوم» = قيمة ثابتة بـ `company.css` لازم تتحوّل. **ما في token جديد إلا المعلّم «جديد».**

### المسافات (`--space-*` — DS-SIZE)

| الاستعمال | المرجع اليوم | التوكن |
|-----------|--------------|--------|
| padding البطاقة | `14px 16px` | `var(--space-7) var(--space-8)` (14 / 16) |
| بين البطاقات | `margin-bottom:10px` | `--space-5` (10) |
| فجوة الرأس | `gap:10px` · `margin-bottom:10px` | `--space-5` |
| فجوة سطر الـ meta | `gap:6px` | `--space-3` (6) |
| فجوة أيقونة + نص بالزر | `gap:4px` | `--space-2` (4) |
| فوق شريط التفاعل | `margin-top:10px` · `padding-top:8px` | `--space-5` · `--space-4` (8) |
| padding الزر | `5px 4px` | `--space-2` + لمس ≥ `--size-touch-min` بالموبايل (CARD-06) |

### الحواف (`--radius-*`)

| الاستعمال | المرجع اليوم | التوكن |
|-----------|--------------|--------|
| البطاقة | `14px` | `--radius-xl` (14) |
| لوحة التعليقات (أسفل) | `0 0 12px 12px` | `--radius-lg` (12) |
| الزر | `7px` | `--radius-xs` (6) |
| قائمة ⋯ | `8px` | `--radius-sm` (8) |
| زر «المزيد / أقل» | `999px` | `--radius-pill` |
| اللوغو | `11px` (يدوي) | من DS-IMAGE (`.tw-ava--org` lg = `--radius-lg`) — ما بيتحدّد بالبطاقة |

### الظلال

ما في `--shadow-*` بـ `tw_shared.css`. ظل المرجع مبني من لون المنشور: `0 4px 18px var(--pa-g)` + `inset 0 1px 0 var(--pa-s)` (hover: `0 6px 24px var(--pa-g)`). قائمة ⋯: `0 4px 16px rgba(var(--color-overlay-rgb), .4)`.
- **«جديد» (مقترح، بيتقرّر بـ U.3):** `--shadow-card` · `--shadow-card-hover` · `--shadow-popover` — بقسم DS-SIZE / DS-COLOR بـ `tw_shared.css` بس (F35 / F36). لحد ما ينضافوا: القيم فوق كما هي، ومن `rgba(var(--color-*-rgb), …)` بس.

### الخطوط (`--size-font-*`)

| الاستعمال | المرجع اليوم | التوكن |
|-----------|--------------|--------|
| الاسم | `.8rem` / 800 | `--size-font-md` (.82rem) / 800 |
| الوقت + المشاهدات | `.63rem` | `--size-font-2xs` (.65rem) — حد أدنى (R21) |
| النص | `.8rem` / line-height 1.75 | `--size-font-md` / 1.75 |
| نص الزر | `.72rem` | `--size-font-xs` (.72rem) |
| بنود قائمة ⋯ | `.78rem` | `--size-font-sm` (.78rem) |
| أيقونة الزر | `14px` | `--size-icon-sm` (14) |
| أيقونة الـ meta | `10px` | `--size-icon-xs` (12) |
| الأفاتار | `48px` | `--size-avatar-lg` (48) · `md` (40) للـ `row` / `conv` |

الخط نفسه: Cairo (موروث من الصفحة) — ما في `font-family` بالبطاقة.

### الألوان (`--color-*` — DS-COLOR)

| الاستعمال | المرجع اليوم | التوكن |
|-----------|--------------|--------|
| خلفية البطاقة | `rgba(var(--color-ink-rgb), .02)` | `--color-surface-card` (ink .03) |
| الحدّ (افتراضي) | `rgba(var(--color-ink-rgb), .06)` | `--color-border-subtle` |
| حدّ / ظل المنشور | `--pa` / `--pa-s` / `--pa-g` | نفسهم، من `TW.POST_THEME_COLORS` (8 ألوان `--color-categorical-*`) |
| خط شريط التفاعل | `rgba(var(--color-ink-rgb), .04)` | `--color-border-subtle` |
| الاسم | موروث | `--color-text-primary` |
| النص | `--color-text-meta` | `--color-text-body` (نص طويل — CLR) |
| الوقت / الزر الهادي | `--color-text-muted` | `--color-text-meta` إذا فشل التباين (R21) |
| hover الزر | `--color-surface-raised` | نفسه |
| قائمة ⋯ | `--color-surface-elevated` | نفسه |
| حذف | `--color-status-danger` | نفسه |
| أقدّر فعّال | `--pa` | نفسه |
| حفظ فعّال | `--color-status-warning` ❌ (معناه تحذير) | **`--color-action-save`** (+`-rgb` — `sky-400`) ✅ Q3 مُجاب (R07 · U.3) |
| focus | — | `--color-border-focus` (نفس `.tw-act:focus-visible`) |

---

## [CARD-05] الحالات (States)

| الحالة | السلوك الموحّد | المرجع اليوم |
|--------|----------------|--------------|
| **تحميل** | `twCardSkeleton(kind, n)` من `tw-skeleton.css` (§35) — نفس أبعاد البطاقة | ما في skeleton للمنشورات (R22) · الرئيسية عندها نسخة `hw-sk*` (D10) |
| **فاضي** | `twEmptyState({icon, titleKey, subKey})` — نص twT | `#postsEmpty` · `hw-empty` · `tw-empty` … (D11) |
| **خطأ** | نفس الـ empty state + زر «إعادة المحاولة» (بيعيد نفس الطلب) — مش toast بس | toast بس، القائمة بتضل فاضية (R22) |
| **مخفي** (صاحبه معلّق، أو حظر بأي اتجاه) | **ما بيوصل من السيرفر أصلاً** — ما في بطاقة ولا placeholder ولا «محتوى مخفي» | ✅ (`bs.visible_sql` / `_404_if_hidden`) |
| **محذوف** | ما بيوصل · طلب مباشر → 404 (نفس رد المخفي — CARD-08) · بطاقة اتحذفت وهي معروضة → بتنشال من القائمة بعد نجاح `DELETE` | الحذف اليوم **نهائي** (`DELETE FROM company_posts`) — سؤال مفتوح Q7 |
| **زائر غير مسجّل** | قراءة كاملة (نص · وسوم · عدّادات · تعليقات) · كل إجراء بيكتب (أقدّر · حفظ · تعليق · متابعة) = `twActionState → login` → `twLoginHref(path)` · مشاركة شغّالة | toast «سجّل دخولك…» (نص ثابت) |
| **صاحب المحتوى** | قائمة ⋯ (تعديل · حذف بـ `twConfirm`) — ظهورها من السجل (`visibleTo: owner`)، والسيرفر بيتحقق من الملكية (403) | `permissions.can_edit` شرط بالصفحة (R06) |
| **أدمن** | الأدمن ما بيشوف البطاقة بجلسة مستخدم؛ لوحة الأدمن جداول (Admin Shell). **ما في إدارة منشورات للأدمن حالياً** → F30 · سؤال مفتوح Q8 | ما في |

حالات الأزرار (من المرجع — بتنتقل كما هي): تبديل متفائل (optimistic) + «desired-state queue» (طلب واحد بالطيران لكل منشور، آخر رغبة بتربح، فشل → رجوع للحالة الأصلية) لأقدّر والحفظ.

---

## [CARD-06] RTL · الموبايل · إمكانية الوصول

**RTL**
- اتجاه الصفحة `dir="rtl"`؛ البطاقة ما بتحط `direction` / `text-align:right` لحالها (المرجع حاططها على `.post-body` و`.pc-dots-*`).
- مواضع منطقية بس: `inset-inline-*` · `margin-inline-*` · `padding-inline-*` · ❌ `left` / `right` ثابتة (المرجع: `.pc-dots { left:14px }` — R14).
- أيقونات الاتجاه بتنقلب لحالها من DS-ICON (F37).
- نص لاتيني / أرقام جوّا نص عربي: `unicode-bidi: plaintext` على النص.

**الموبايل**
- أصغر عرض مدعوم 320px بدون scroll أفقي.
- شريط التفاعل: تحت عرض معيّن الزر = أيقونة + رقم بس، والنص بـ `aria-label` (R12).
- أهداف اللمس ≥ `--size-touch-min` (44px) للأزرار والـ ⋯.
- القص بيتعاد حسابه عند تغيّر العرض / التدوير (R13).
- قائمة ⋯ ما بتطلع برّا الشاشة (DS-OVL — R14).

**إمكانية الوصول**
- `article` + `aria-labelledby` = id الاسم (R15).
- كل `button` إله `type="button"` (R17).
- أقدّر / حفظ: `aria-pressed="true|false"` · تعليق: `aria-expanded` + `aria-controls="pc-cmt-panel-{id}"` (R16).
- قائمة ⋯: `aria-haspopup="menu"` + `aria-expanded` + `role="menu"` / `menuitem` · Escape بيسكّر · الـ focus بيرجع للزر (R18).
- كل أيقونة زينة `aria-hidden="true"` (R19) — `twIconEl` بيعملها.
- `:focus-visible` على كل عنصر تفاعلي: `outline: 2px solid var(--color-border-focus); outline-offset: 2px` (R20).
- التباين: نص ≥ 4.5:1 (AA)، والنص الصغير (≤ `--size-font-2xs`) لازم يتقاس — إذا فشل → `--color-text-meta` (R21).
- العدّادات بـ `span` منفصل `font-variant-numeric: tabular-nums` (R11) — القارئ بيقرأ «أقدّر، 12».

---

## [CARD-07] الحظر والإخفاء — القاعدة

1. **المصدر الوحيد للظهور هو السيرفر:** `blocks_suspension.visible_sql` / `active_sql` / `is_hidden` (`docs/rules/blocks-suspension.md`). أي endpoint بيرجّع بطاقات بيفلتر بالاستعلام قبل ما يرجّع.
2. **الواجهة ما فيها أي منطق إخفاء:** ❌ فلترة بطاقات بالـ JS حسب حظر / تعليق / نوع · ❌ قائمة محظورين محلية · ❌ «هذا المحتوى مخفي». اللي بيوصل بينعرض، واللي ما وصل ما إله وجود.
3. **العدّادات من نفس الفلتر** (task 5.4e): `comments_count` = عدد القائمة اللي بيشوفها نفس المشاهد. أي عدّاد جديد بالبطاقة بيطلع من نفس فلتر قائمته.
4. **الطلب المباشر لمحتوى مخفي = 404** بنفس نص المحتوى المش موجود — بدون تمييز (ولا «محظور»، ولا «معلّق»).
5. **طلبات التوظيف ما بتتأثر** (القاعدة 5 بـ blocks-suspension) — بطاقات `applicant` / `application` ما فيها فحص حظر.
6. **ظهور الأزرار ≠ حماية** (F21): `twAction` للـ UX بس، والسيرفر بيرجّع 401 / 403 / 404 دايماً.

---

## [CARD-08] رابط المنشور — `/post/{id}` (قرار معتمد · متطلب)

| البند | المتطلب |
|-------|---------|
| الرابط | `https://tawasolna.com/post/{id}` — `{id}` = رقم المنشور الحالي (`company_posts.id`) |
| المحتوى | صفحة بتعرض **البطاقة الموحّدة** (`TwPostCard` variant `full`) **مع التعليقات** |
| الزائر | متاح بدون حساب — قراءة بس؛ كل إجراء بيكتب بيطلب دخول (`twLoginHref('/post/{id}')` — NAV-07) |
| مخفي / محذوف | المنشور المخفي (صاحبه معلّق، أو حظر بأي اتجاه مع المشاهد) أو المحذوف = **404 بدون تمييز** — نفس الـ status ونفس النص ونفس الصفحة |
| `id` مش رقم | 404 (نفس فحص الأرقام بقاعدة Legacy Redirect 10: ASCII digits، ≤ 18) |
| المشاركة | `_sharePost` بيشارك `/post/{id}` بدل `/u/{tw_id}` (R09) |
| الأمان (F17) | قراءة عامة · JWT اختياري (لـ `viewer_appreciated` / `viewer_saved` / الحظر) · نفس rate limit القراءة · الرد بنفس عقد المنشور (CARD-03) |

> ⚠️ **تعارض موثّق:** CLAUDE.md → Smart Router rule 8 («Numeric id stays internal») و rule 9 (public_id بادئة `P`). القرار هون رقم المنشور الحالي بقرار صاحب المشروع → لازم يتسجّل كاستثناء صريح قبل تنفيذ U.6 — **سؤال مفتوح Q1**.

---

## [CARD-09] الممنوعات

- ❌ HTML بطاقة مبني بصفحة (template literal / `innerHTML`) بدل مكوّن DS-CARD — للأنواع اللي اتحوّلت.
- ❌ CSS بطاقة خاص بصفحة (`post-*` · `hw-*` · `co-fl-*` · `sc-fl-*` …) بعد ما نوعها يتحوّل.
- ❌ `<svg>` مكتوب يدوياً · ❌ `<img>` أفاتار يدوي · ❌ نص عربي ثابت · ❌ px / rem / hex خام.
- ❌ دالة وقت نسبي / عدّاد مختصر / مشاركة / نسخ محلية (D1 · D4 · D6).
- ❌ شرط ظهور زر بالصفحة (`can_edit` · `comments_enabled` · `IS_CO`) بدل `twAction`.
- ❌ أي إخفاء بالواجهة (CARD-07).
- ❌ عدّاد جوّا نص الزر.
- ❌ قائمة ⋯ أو تأكيد يدوي بدل DS-OVL.
- ❌ endpoint قائمة بطاقات بدون صفحات (R23 · Input Limits).

---

## [CARD-10] المتطلبات المعتمدة (الـ 23 اقتراح من التقرير — U.0 §4)

| # | المتطلب | البطاقات المتأثرة | المرحلة |
|---|---------|-------------------|---------|
| CARD-R01 | كل نص بالبطاقة (أزرار · قائمة · «المزيد / أقل» · مشاهدة · وقت · toasts) مفتاح `twT` (`post.*` / `card.*`) | P1 · P2 · J1 | U.3 |
| CARD-R02 | كل أيقونة من DS-ICON (`twIconEl`) — حذف 27 SVG يدوي (D2) وتوحيد أيقونة المشاركة | P1 · J1 · U5 | U.3 |
| CARD-R03 | الصورة / اللوغو عبر DS-IMAGE (`twAvatarEl` مع `user_type`) + fallback | P1 · P2 · J1 · U5 | U.3 |
| CARD-R04 | كل الأحجام من `--size-*` / `--space-*` / `--radius-*` (CARD-04) | P1 · P2 · كل الأنواع | U.3 |
| CARD-R05 | التاريخ بعد الحد النسبي عبر `twFormatDate` + دالة وقت نسبي مشتركة وحدة (D1) | P1 · P2 · J1 · J2 · J3 · J5 | U.3 |
| CARD-R06 | كل أزرار البطاقة عبر `twAction` — شرط التعليق (`comments_enabled`) والـ ⋯ (`can_edit`) من السجل / السياق، مش بالصفحة | P1 · P2 · J1 · U4 · U5 | U.3 |
| CARD-R07 | لون الحفظ الفعّال token بمعنى صحيح (مش `--color-status-warning`) — ✅ `--color-action-save` (Q3) | P1 · P2 | U.3 ✅ |
| CARD-R08 | الاسم / اللوغو `<a>` لـ `/u/{tw_id}` لما البطاقة برّا صفحة صاحبها | P2 · U4 · J2 · C2 | U.6 |
| CARD-R09 | المشاركة بتشارك رابط المنشور `/post/{id}` (CARD-08) | P1 · P2 | U.6 |
| CARD-R10 | المشاهدات بمكان / أيقونة ما بتنقرا كجزء من التاريخ | P1 · P2 | U.4 |
| CARD-R11 | العدّاد بـ `span` منفصل `tabular-nums` — بدون قفزة بعرض الزر | P1 · P2 | U.4 |
| CARD-R12 | تحت عرض معيّن: زر = أيقونة + رقم، والنص بـ `aria-label` | P1 · P2 | U.4 |
| CARD-R13 | القص بيتعاد عند تغيّر العرض (`ResizeObserver`) أو `line-clamp` CSS + زر «المزيد» | P1 · P2 | U.4 |
| CARD-R14 | قائمة ⋯ بـ `inset-inline-end` + DS-OVL — ما بتطلع برّا الشاشة | P1 | U.4 |
| CARD-R15 | الحاوية `article` + `aria-labelledby` | P1 · كل الأنواع | U.4 |
| CARD-R16 | أقدّر / حفظ `aria-pressed` · تعليق `aria-expanded` + `aria-controls` | P1 · P2 | U.4 |
| CARD-R17 | كل `button` إله `type="button"` | P1 · كل الأنواع | U.4 |
| CARD-R18 | قائمة ⋯: `aria-haspopup` / `aria-expanded` / `role="menu"` + Escape + رجوع الـ focus | P1 | U.4 |
| CARD-R19 | كل SVG زينة `aria-hidden="true"` | P1 · J1 | U.4 |
| CARD-R20 | `:focus-visible` واضح على كل عنصر تفاعلي (`--color-border-focus`) | P1 · كل الأنواع | U.4 |
| CARD-R21 | تباين AA للنص الثانوي الصغير — قياس + تصحيح التوكن | P1 · P2 · كل الأنواع | U.4 |
| CARD-R22 | skeleton للمنشورات + حالة خطأ بالقائمة مع «إعادة المحاولة» (نمط الرئيسية) | P1 · P2 · J3 | U.5 |
| CARD-R23 | pagination لـ `GET /company/posts/{id}` (الحجم من `tw_limits.py`) | P1 | U.5 |

---

## [CARD-11] أسئلة مفتوحة (قرار منتج — ما انقرّرت هون)

1. **Q1 — رابط المنشور الرقمي:** `/post/{id}` بيتعارض مع Smart Router rule 8 (الرقم داخلي) و rule 9 (public_id بادئة `P`). نسجّله استثناء صريح بـ CLAUDE.md / `ARCHITECTURE.md §C`، ولا نستعمل public_id `P…` بنفس المسار؟ (لازم قبل U.6)
2. **Q2 — الثيمات s1–s5:** مش موجودة بالكود (التقرير 0.2). المقصود الـ 8 ألوان `TW.POST_THEME_COLORS`، ولا تصميم جديد؟
3. **Q3 — لون الحفظ الفعّال:** ✅ **مُجاب (2026-10-24 — صاحب المشروع): token جديد بدل لون التحذير** — `--color-action-save` بـ DS-COLOR Section B (`tw_shared.css`) = `var(--color-prim-sky-400)` (`#38bdf8`) + توأم `-rgb`، تباين ≈ 9.2:1 على خلفية الصفحة. مش `--pa`. المستهلك: `.pc-btn--save.save-active` / `:hover` بـ `tw-card.css` (U.3 · R07 · COLOR-SYSTEM.md → task U.3).
4. **Q4 — التعليقات بالرئيسية:** لوحة تعليقات جوّا البطاقة (متل صفحة الشركة)، ولا زر «تعليق» بيفتح `/post/{id}`؟
5. **Q5 — الضغط على بطاقة الرئيسية:** البطاقة كلها بتفتح صفحة الشركة (اليوم)، ولا الاسم بس رابط والنص بيفتح `/post/{id}`؟
6. **Q6 — المشاهدات:** بتبين لكل الناس (اليوم) ولا للمالك بس؟ وزيارة `/post/{id}` بتنعدّ مشاهدة؟
7. **Q7 — حذف المنشور:** اليوم نهائي (`DELETE`). نخلّيه، ولا يصير soft delete (F27) قبل `/post/{id}`؟ (النتيجة للمستخدم بتضل 404 بالحالتين.)
8. **Q8 — الأدمن والمنشورات:** ما في نظام إخفاء / حذف منشور للأدمن (F30). مطلوب؟ وإذا آه، الأدمن بيشوف المنشور المخفي بصفحة `/post/{id}`؟
9. **Q9 — فهرسة `/post/{id}`:** بتنفهرس بمحركات البحث + sitemap (§54m)، ولا `noindex`؟
10. **Q10 — المشاركة بباقي البطاقات:** زر مشاركة لكل بطاقة وظيفة (اليوم بصفحة الشركة بس)؟
11. **Q11 — النطاق:** بطاقات الشركة الداخلية (المتقدمون · بنك المواهب · اقتراحات) ورؤوس الصفحات (U7 · C1 · C3) بتدخل DS-CARD كمكوّنات، ولا بتاخد التوكنز بس؟
12. **Q12 — الـ pagination:** «عرض المزيد» ولا تمرير لانهائي؟ وكم منشور بالصفحة؟
13. **Q13 — شارة النوع بقائمة المتابعين:** النص من GLOSSARY («حساب شخصي / حساب شركة / حساب جهة تعليمية») ولا اختصار أقصر بالبطاقة؟
14. **Q14 — الزائر والتعليقات:** الزائر بيشوف التعليقات (CARD-08)؛ بيشوف كمان قائمة المنشن / أسماء المقدّرين، ولا العدد بس؟

---

## [CARD-12] خطة التنفيذ U.2 → U.10

> كل مرحلة PR صغير ومستقل · اختبار مركّز واحد (CLAUDE.md Testing & CI) بيتسجّل بـ `run_tests.sh` · `python tools/page_audit.py` ما بيزيد · القائمة الموحّدة لكل صفحة بتنلمس · توثيق هالملف + SYSTEMS_INDEX §61 بنفس الـ PR.

| المرحلة | النطاق | الملفات المتوقعة | المتطلبات | التستات اللي لازم تنضاف |
|---------|--------|------------------|-----------|--------------------------|
| **U.2** ✅ كامل (CARD-13): رسم (U.2) + سلوك + CSS (U.2b) | **المرجع → المكوّن المشترك أول:** نقل `_postCardHtml` + سلوك الأزرار (desired-state queue · تتبّع المشاهدة · قص النص · لوحة التعليقات) لـ `TwPostCard` **بدون تغيير سلوك ولا شكل** + أساس `tw-card.css` (classes بس، نفس القيم) · صفحة الشركة بتستعمله · حذف النسخ المكررة D2 / D3 | جديد `static/shared/tw-post-card.js` · `static/shared/tw-card.css` · `partials/` (shell) · `company.render.js` · `company.posts.js` · `company.css` (حذف `POST CARDS` المنقول) | — (أساس لكل المتطلبات) | `node tests/test_post_card_runtime.js` (vm): render → عناصر الرأس / الجسم / الأزرار · تبديل أقدّر وحفظ + رجوع عند الفشل · المالك بيشوف ⋯ والزائر لا |
| **U.3** ✅ (CARD-13 → U.3) | تنظيف المكوّن نفسه: twT · DS-ICON · DS-IMAGE · tokens · `twFormatDate` + وقت نسبي مشترك · `twAction` لكل الأزرار + إجراءات السجل (`post_appreciate` · `post_save` · `post_comment` · `share` · `post_edit` · `post_delete`) · لون الحفظ (بعد Q3) | `tw-post-card.js` · `tw-card.css` · `tw_strings.json` · `tw_actions.json` · `tw_shared.js` (الوقت النسبي) · `tw_shared.css` (shadow — «جديد» إذا انقرّر) | R01 · R02 · R03 · R04 · R05 · R06 · R07 | نفس `test_post_card_runtime.js`: النص من twT · ما في `<svg>` يدوي · `twActionState` بيخفي ⋯ لغير المالك · الوقت النسبي input → output |
| **U.4** | وصول + موبايل بالمكوّن: `article` · aria · `type="button"` · `:focus-visible` · قائمة ⋯ DS-OVL + Escape · عدّاد منفصل · وضع الأيقونة + رقم · إعادة القص · مكان المشاهدات · قياس التباين | `tw-post-card.js` · `tw-card.css` | R10 · R11 · R12 · R13 · R14 · R15 · R16 · R17 · R18 · R19 · R20 · R21 | runtime: `aria-pressed` بيتبدّل مع الضغط · `aria-expanded` على التعليق والـ ⋯ · Escape بيسكّر ويرجّع الـ focus · كل button `type=button` |
| **U.5** | الحالات + الصفحات: `twCardSkeleton` · `twEmptyState` (+ «إعادة المحاولة») بـ `tw_shared.js` / `tw-skeleton.css` · pagination لـ `GET /company/posts/{id}` (حد بـ `tw_limits.py`، إضافة params بس — F14) · «عرض المزيد» (Q12) | `server.py` · `auth.py` (`get_company_posts`) · `tw_limits.py` · `tw_shared.js` · `tw-skeleton.css` · `tw-post-card.js` · `company.render.js` | R22 · R23 | `python -m pytest tests/test_company_posts_pagination.py -q`: الحد بيتطبّق · الصفحة التانية ما بتكرر · الفلتر `visible_sql` لسا شغّال بالصفحة التانية |
| **U.6** | رابط المنشور: `GET /post/{id}` (صفحة) + endpoint قراءة منشور واحد (JWT اختياري · 404 موحّد للمخفي / المحذوف / id غلط) · صفحة بالـ Page Shell بتعرض `TwPostCard full` + تعليقات · المشاركة → `/post/{id}` · الاسم رابط `/u/{tw_id}` · `twShare` مشترك (D4) — **بعد Q1 (+ Q7 / Q9)** | `server.py` · `auth.py` · جديد `post.html` + `static/post/post.js` · `tw-post-card.js` · `tw_shared.js` (`twShare`) · `ARCHITECTURE.md` (route) · `docs/rules/` (إذا انقرّر استثناء Q1) | R08 · R09 (+ CARD-08) | `python -m pytest tests/test_post_link.py -q`: منشور ظاهر → 200 للزائر · صاحبه معلّق → 404 · حظر بأي اتجاه → 404 · محذوف → 404 · id مش رقم → 404 · نفس الرد بالحالات الأربعة |
| **U.7** | الرئيسية: `/home/feed` بيرجّع عقد المنشور الكامل (إضافة حقول بس) + `home.cards.js` بيستعمل `TwPostCard feed` (تقدير / حفظ / مشاركة / وسوم / «المزيد») · حذف `renderPostCard` و`hw-*` الخاص بالمنشور + skeleton `hw-sk*` (D10) | `server.py` (`home_feed`) · `home.cards.js` · `home.render.js` · `home-v2.css` · `home-v2.html` (shell) | R08 · R09 · R22 على P2 (+ Q4 / Q5) | `python -m pytest tests/test_home_feed_post_contract.py -q`: المنشور بالفيد فيه نفس حقول `/company/posts` · `viewer_appreciated` / `viewer_saved` صح للمستخدم |
| **U.8** | `TwPersonCard row` + توحيد قائمتي المتابعين (D5): نافذة وحدة لـ `co-fl-*` و`sc-fl-*` · زر `twAction('follow')` · شارة نوع twT (Q13) · حذف Lucide CDN بالبروفايل | جديد `static/shared/tw-person-card.js` · `company.main.js` · `profile-v2.render.js` · `company.css` · `profile-v2.css` | R01 · R02 · R03 · R06 · R08 · R15 · R17 · R20 على U4 / U5 | `node tests/test_person_card_runtime.js`: نفس المدخل → نفس العنصر بالصفحتين · زر المتابعة من السجل · الاسم `<a href="/u/{tw_id}">` |
| **U.9** | `TwJobCard` variants `feed` · `compact` · `application` · `visitor` · `owner` — **العقد المجمّد بـ `docs/company-jobs-and-applicants.md §2` بيضل نفسه** · `twStatusPill` (D7) | جديد `static/shared/tw-job-card.js` · `home.cards.js` · `job-detail.js` · `profile-v2.apps.js` · `notifications.html` · `company.render.js` (`renderJobs`) · `tw-card.css` | R01 · R02 · R03 · R04 · R05 · R06 · R17 · R22 على J1 → J5 | `node tests/test_job_card_runtime.js`: كل variant بيرسم أجزاءه · `owner` عدد المتقدمين `—` لما ما ينقرا · الحالة من الـ pill المشترك |
| **U.10** | `TwOrgCard` (`side` · `row`) لـ job-detail + edu · حذف `.tw-card-lift` المكرر (D8) وإعادة تعريف `.tw-card` الرسمية · `applicant` / `candidate` بياخدوا الأساس والتوكنز بس (بدون منطق الـ pipeline — Q11) | جديد `static/shared/tw-org-card.js` · `job-detail.js` · `edu-profile.html` · `tw_shared.css` · `company.css` · `index.css` | R03 · R04 · R08 · R15 · R20 على C2 / C3 (+ U1 → U3 حسب Q11) | `node tests/test_org_card_runtime.js`: لوغو مربّع (co / edu) · شارة «موثّقة» بس لما `verified` · الاسم رابط |

**الترتيب ليش هيك:** U.2 بيحط المرجع بمكوّن واحد بدون أي تغيير مرئي (مخاطرة أقل) → U.3 / U.4 بيصلّحوه بمكان واحد → U.5 / U.6 بيضيفوا القدرات (صفحات + رابط) → U.7 بيعمّمه على الرئيسية → U.8 / U.9 / U.10 باقي الأنواع، كل نوع لحاله.

---

## [CARD-13] المنفّذ — `TwPostCard` (U.2 ✅ · U.2b ✅ · 2026-10-24)

**المكان:** `static/shared/tw-post-card.js` (المكوّنات المشتركة بـ `static/shared/` متل `tw-schedule.js` — CARD-12 / التقرير §5.2) · بيتحمّل بـ `company-profile.html` عبر `PAGE_ASSETS` (`{{v:tw-post-card.js}}`) قبل `company.*.js` · بيحتاج `twEscHtml` / `twEscAttr` / `twSafeImageUrl` (`tw_shared.js`) + `TW.POST_THEME_COLORS` (`tw-options-data.js`) وقت الاستدعاء · السلوك بيحتاج `twApi` / `twApiMessage` / `showToast` (`tw_shared.js`).
**CSS:** `static/shared/tw-card.css` (U.2b) — قسم `POST CARDS` من `company.css` منقول كما هو (نفس الـ selectors والقيم، ما في token جديد) · بيتحمّل عبر `PAGE_ASSETS` (`{{v:tw-card.css}}`) **مباشرة قبل** `company.css` (نفس ترتيب الـ cascade: ولا قاعدة بـ `company.css` بتلمس نفس العناصر) · `.posts-owner-bar` / `#postsEmpty` ضلّوا بـ `company.css` (قائمة الصفحة، مش البطاقة) · `POST COMMENTS PANEL` ضل مكانه.

| الـ API | المدخلات | المخرجات |
|---------|----------|----------|
| `TwPostCard.html(post, opts)` | `post` = عنصر `/company/posts` (`id` · `body` · `tags[]` · `theme_color` · `created_at` · `views_count` · `appreciations_count` · `viewer_appreciated` · `comments_enabled` · `comments_count` · `viewer_saved`) · `opts.authorName` (بيتعمله escape هون؛ أول حرف = بديل الصورة) · `opts.avatarUrl` (رابط خام — بيمرق على `twSafeImageUrl` هون؛ غير آمن → الحرف) · `opts.canEdit` (`true` → قائمة ⋯ تعديل / حذف · غير هيك ما في) | HTML string لـ `.post-card` وحدة — نفس الـ DOM / الكلاسات / `data-*` / النص اللي كان بـ `_postCardHtml` حرفياً |
| `TwPostCard.apprButtonInner(active, count)` | حالة أقدّر + العدد | محتوى `.pc-btn--appr` (أيقونة + «أقدّر · N») — نفس الرسم الأول وبعد الضغط (حذف D2 / D3) |
| `TwPostCard.saveButtonInner(active)` | حالة الحفظ | محتوى `.pc-btn--save` (أيقونة + «حفظ / محفوظ») |
| `TwPostCard.initClamps(container)` | الحاوية بعد الرسم | قص 3 أسطر + «المزيد» لكل `.post-body-wrap` (كان `_initPostClamps`) |
| `TwPostCard.relativeTime(iso)` · `TwPostCard.formatViews(n)` | تاريخ / رقم | نص الـ meta (كانوا `_relativeTime` / `_fmtViews` بـ render + `_fmtViewsCount` بـ posts — نسخة وحدة هلق) |
| `TwPostCard.create(opts)` (U.2b) | `opts.signedIn()` → bool (فحص الجلسة — الصفحة) · `opts.paths.appreciation(id)` / `.save(id)` / `.view(id)` → مسار `twApi` · `opts.visitorKeyName` (مفتاح `localStorage` لمفتاح الزائر المجهول بالمشاهدة) · `opts.shareInfo(id)` → `{name, url}` · `opts.onEdit(id)` / `opts.onDelete(id)` (id رقم، القائمة مسكّرة) · `opts.comments.build(id)` / `.load(id)` (نظام التعليقات §22c بيعبّي اللوحة) | controller: `bind(root)` — click delegation على القائمة (مرة) + سكّر ⋯ عند الضغط برّا (مرة بالصفحة) · `trackViews(container)` — بعد كل رسم · `toggleComments(id)` |

**الصفحة:** `company.render.js → _postCardHtml(post)` صار wrapper رفيع داخلي (مش على `window`): بيعطي اسم الشركة (`|| 'الشركة'`) + اللوغو + `permissions.can_edit` · `renderPosts` → `TwPostCard.initClamps`. `company.posts.js` بيرسم الأزرار بعد الضغط عبر `apprButtonInner` / `saveButtonInner` والمشاهدات عبر `formatViews`.
**السلوك (U.2b — منقول من `company.posts.js` حرفياً):** desired-state queue لأقدّر والحفظ (طلب واحد بالطيران لكل منشور، الواجهة فورية، طلب الطابور بآخر حالة مطلوبة، رجوع لحالة ما قبل الضغط عند 403 / 429 / فشل) · تتبّع المشاهدة (`IntersectionObserver` 50% + 800ms، مرة لكل منشور بالجلسة، العدّاد +1 لما `recorded`) · فتح / سكّر لوحة التعليقات (وحدة مفتوحة بس) · قائمة ⋯ · «المزيد / أقل» · المشاركة (`navigator.share` → clipboard → textarea، نفس النص — `/post/{id}` = U.6). المكوّن ما بيعرف إنه بصفحة شركة.
**التعليقات (task 8.6b-1):** `opts.comments` = controller من `TwPostComments.create({ signedIn, postOwner })` — `static/shared/tw-post-comments.js` + `tw-post-comments.css` (نظام التعليقات §22c منقول من `company.posts.js` / `company.css` كما هو؛ القواعد `docs/rules/post-comments.md` القاعدة 0).

**ضل بالصفحة (ليش):** `company.posts.js` → `TwPostCard.create({...})` بالأجزاء الخاصة بالشركة: مسارات `/company/posts/{id}/…` · `TwCompanyPage.signedIn` · `cp_vk` · اسم الشركة + `/u/{tw_id}` للمشاركة · التعديل (`_getPostById` → `openPostModal`) · الحذف (`deletePost` — تأكيد DS-OVL + طلب) · محتوى التعليقات كلّه (§22c: بناء اللوحة، تحميل، إرسال، ردود، منشن، قائمة ⋮ التعليق — نفس delegation الصفحة) · `window.initPostViewTracking` ضل اسم (بيستدعيه `company.render.js`) وبينادي `trackViews`. اختيار `html()` (string) بدل `render()` → `HTMLElement` بالتقرير §5.2: عشان المخرجات تضل حرفياً نفس `list.innerHTML = posts.map(...).join('')`.
**Test (U.2 / U.2b — الفحص الحرفي اتبدّل بـ U.3، شوف تحت):** `node tests/test_post_card_runtime.js` — `TwPostCard.html` = نسخة مجمّدة من الكود القديم (`tests/fixtures/legacy_company_post_card.js` — انحذفت بـ U.3) حرف بحرف: مالك · زائر · لوغو · بدون لوغو · لوغو غير آمن · تعليقات مطفّاة · حالات نشطة + عدّادات + وسوم · نص طويل · HTML / سكربت (escape) + أزرار ما بعد الضغط + `renderPosts` عبر المكوّن · **U.2b** (DOM صغير بيقرا الـ markup الحقيقي — `tests/fixtures/post_card_dom.js`): أقدّر / حفظ + رجوع عند الفشل / 403 / 429 · ضغطات سريعة = طلب واحد بالطيران + طابور · الزائر → toast بدون طلب · ⋯ للمالك بس + سكّر برّا + callbacks · المشاهدة مرة وحدة + العدّاد · المشاركة (share / clipboard / fallback بنفس النص) · ربط `company.posts.js` · `tw-card.css` = القسم القديم المجمّد (`tests/fixtures/legacy_post_cards.css`) وما ضل منه شي بـ `company.css`.

### U.3 ✅ — تنظيف المكوّن (2026-10-24)

كل جزء بالبطاقة صار من نظامه — نفس الـ DOM / الكلاسات / `data-*` / السلوك، ونفس API (`html` · `create` · `bind` · `trackViews` · `toggleComments`) + خيار جديد اختياري `opts.authorType`.

| المتطلب | شو انعمل |
|---------|----------|
| R01 نص | كل نص من `twT`: `post.card.*` (أزرار · ⋯ · «المزيد / أقل» · مشاهدة · toasts · نص المشاركة) + `action.share` + الوقت `time.rel.*` — صفر نص عربي بالكود |
| R02 أيقونات | 12 SVG يدوي → `twIcon` (`heart` · `comment` · `share` · `bookmark` / `bookmark-check` · `edit` · `delete` · `more` · `clock` · `eye` · `show-more` / `show-less`) |
| R03 صورة | `twAvatarHtml({full_name, avatar_url, user_type: opts.authorType}, 'lg')` — الصفحة بتمرّق `authorType: 'co'` · انحذف `<img>` / حرف البديل اليدوي + `.post-ava img` / `.post-ava--init` |
| R04 أحجام | كل padding / margin / gap / font-size / radius / أبعاد أيقونة بـ `tw-card.css` من `--space-*` / `--radius-*` / `--size-font-*` / `--size-icon-*` (جدول CARD-04). ضل خام: حدود `1px` · الظلال (`--shadow-*` لسّا ما انقرّر — CARD-04) · `min-width:90px` لقائمة ⋯ (مش بجدول CARD-04 — U.4 / R14 بتحوّلها لـ DS-OVL) |
| R05 وقت | `twRelativeTime` جديد بـ `tw_shared.js` (SYSTEMS_INDEX §59a) — بعد 30 يوم `twFormatDate` (كان `toLocaleDateString('ar')`) · `TwPostCard.relativeTime` = هي نفسها |
| R06 أزرار | السجل `tw_actions.json`: `post_appreciate` · `post_save` (`auth`) · `post_comment` (`visibleWhen: comments_enabled` → `ctx.commentsEnabled`) · `share` (موجود) · `post_edit` / `post_delete` (`owner`). الظهور = `twActionState` (المالك = `canEdit` من السيرفر كـ `ctx.mode:'owner'`) · ⋯ بيبين بس إذا في بند واحد ظاهر · كل `button` إله `type="button"` + `data-tw-action`. البطاقة HTML string (قائمة الشركة `innerHTML`) فالضغط بيضل بالـ delegation تبع `bind()` |
| R07 لون الحفظ | `--color-action-save` (Q3) بدل `--color-status-warning` — الحفظ الفعّال + hover · علامة الصح بأيقونة `bookmark-check` مقصوصة بـ `--color-surface-page` (متل قبل) |

**تغيير سلوك (من السجل — BTN-19 القاعدة 3 · CARD-05 «زائر غير مسجّل»):** الضيف بيكبس «أقدّر» أو «حفظ» → `twLoginHref(path + query)` (صفحة الدخول ومنها رجعة لنفس الصفحة) بدل toast «سجّل دخولك…». التعليق والمشاركة للضيف ما تغيّروا.
**فرق مرئي (نصي):**

| العنصر | قبل | بعد |
|--------|-----|-----|
| زر ⋯ | حرف `⋯` (أفقي) | أيقونة DS-ICON `more` (نقاط عمودية) |
| أيقونات الأزرار / القائمة | SVG يدوي stroke 1.8 | DS-ICON (نفس الأشكال تقريباً — Lucide الأحدث) · أيقونات القائمة 13 → 14px · أيقونات الـ meta 10 → 12px |
| اللوغو | مربع 48 بزاوية 11px + تدرّج خلفية | DS-IMAGE `.tw-ava--lg` مربع (`--radius-lg` 12) + بديل الحرف تبع النظام |
| الاسم / النص | `.8rem` | `--size-font-md` (.82rem) |
| «محفوظ» الفعّال | كهرماني (لون التحذير) | `--color-action-save` سماوي |
| تاريخ أقدم من 30 يوم | `toLocaleDateString('ar')` | «1 يناير 2025» (`twFormatDate`) |

**Test:** `node tests/test_post_card_runtime.js` (A–D + K لـ U.3 · E–J سلوك U.2b) · `python tests/test_post_save.py` (10 أيقونة DS-ICON · 14 الضيف → الدخول). النسختين المجمّدتين (`tests/fixtures/legacy_company_post_card.js` · `legacy_post_cards.css`) انحذفوا — U.3 بيغيّر المخرجات عن قصد، والفحص صار سلوكي.

### 8.6b-2 ✅ — منشورات الرئيسية بـ `TwPostCard` (2026-10-28)

- **المستهلك التاني:** `/home` (`home-v2.html`) — منشورات الشركات بالفيد = نفس بطاقة صفحة الشركة (أقدّر · حفظ · مشاهدة · وسوم · مشاركة · تعليقات بتنفتح جوّا الفيد بـ `TwPostComments`). البطاقة القديمة `hw-p*` + الـ CSS تبعها انحذفوا. يجاوب Q5 للرئيسية: البطاقة ما بتنقل لأي مكان — الاسم واللوغو بس رابط `/u/{tw_id}`؛ وصف `feed` بـ CARD-03 (التعليق → رابط المنشور) لسا مفتوح لـ U.6 / U.7.
- **خيار جديد اختياري `opts.authorHref`** بـ `TwPostCard.html`: موجود → `.post-nm` و `.post-ava` بيصيروا `<a href>` (الصورة `tabindex="-1"` + `aria-hidden` — الاسم هو الرابط؛ CARD-R08) · مش موجود → نفس المخرجات القديمة حرفياً (صفحة الشركة ما تغيّرت). الشكل من `tw-card.css` (`a.post-nm` / `a.post-ava` — نفس النص، بدون لون جديد).
- **الـ controller:** `static/home/home.posts.js` — `TwPostComments.create({signedIn: TwAuthSync snapshot, postOwner: صاحب المنشور من عناصر الفيد})` + `TwPostCard.create({signedIn, paths: /company/posts/{id}/(appreciation|save|view), visitorKeyName: 'cp_vk', shareInfo: اسم الشركة + /u/{author_tw_id}, comments})` بدون `onEdit` / `onDelete` · `bind(#hwFeed)` مرة وحدة · `initClamps` + `trackViews` بعد كل رسم.
- **`TwPostComments`:** لوحة جديدة لمنشور انرسم قبل (إعادة رسم الفيد) بتبلّش من الصفر — حالة الرد / المنشن المختار / القوائم المفتوحة لهالمنشور بتنمسح وقت البناء.
- **Test:** `node tests/test_post_card_runtime.js` القسم M (ملفات `static/home/*.js` الحقيقية على `tests/fixtures/post_card_dom.js`).
