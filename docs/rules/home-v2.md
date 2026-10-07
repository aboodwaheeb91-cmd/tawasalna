# Home V2 — الصفحة الرئيسية

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Home V2 Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions:

1. **`/home` serves `home-v2.html`** — `home.html` القديم حُذف (PR-4)؛ `/home.html` صار redirect عبر صفحة التحويل المشتركة (`_LEGACY_REDIRECT_HTML`). `/home` هو وجهة `twHomeHref()` لكل أنواع الحسابات (emp / co / edu).

2. **Feed-first is mandatory.** أي تعديل على Home V2 يجب أن يبدأ بـ filter tabs ثم feed. ممنوع إعادة Dashboard-first (بطاقة مستخدم ضخمة أول الصفحة).

3. **Files are split — keep them split (modular structure):**
   - `home-v2.html` — HTML هيكل فقط
   - `static/app-header.css` — CSS vars + `.sc-header` / `.sc-*` shared header classes
   - `static/app-header.js` — `initAppHeader(user)` — layout-only (VM-10 compliant): avatar + logout delegation; no polling, no setInterval, no session resolution
   - `static/home-v2.css` — أنماط الصفحة (`.hw-*` namespace)
   - `static/home/home.utils.js` — constants + DOM helpers
   - `static/home/home.state.js` — shared state (`window.Home.state`)
   - `static/home/home.api.js` — feed fetch (`Home.api.loadFeed`)
   - `static/home/home.cards.js` — card renderers (opportunity / post / news)
   - `static/home/home.render.js` — feed UI states (skeleton / empty / error / feed)
   - `static/home/home.filters.js` — filter tab wiring + orchestration
   - ~~`static/home/home.header.js`~~ — deleted PR 3.2: header + bottom nav = unified app chrome (`<header data-tw-header>` / `<nav data-tw-bottom-nav>` — `docs/design-system/HEADER-NAV.md`)
   - `static/home/home.nav.js` — sidebar + banner per user type
   - `static/home/home.main.js` — bootstrap only (auth guard + init + load)
   - ممنوع دمج CSS/JS الكبير داخل HTML
   - **ممنوع** إضافة feature جديدة قبل تحديد module المناسب لها

4. **`/preview/home-v2` is deleted.** لا تعيد إضافته. Route المعاينة المؤقت أُزيل عند shipping Home V2.

5. **`GET /home/feed` is the feed API.** Auth: `Depends(verify_token)` — `user_id` من JWT فقط، ليس من query param. `filter` مُقيَّد server-side بـ allowlist: `{"all","opportunities","posts","news"}`.

6. **Rendering is always safe:** كل بيانات API تُعرض عبر `createElement` + `textContent`. لا `innerHTML = apiData`. السماح بـ `innerHTML` للـ skeleton الثابت فقط (لا يحتوي بيانات API).

7. **Home feed filters are final: `all / opportunities / posts / news`.**
   - `opportunities` — يعرض `jobs` حالياً (مع `opp_type="job"`). مستقبلاً يدعم training/scholarship/overseas.
   - `news` — أخبار رسمية من `news_posts` table، يُنشر من الأدمن فقط.
   - **ممنوع** إعادة `companies` كـ filter — مكانها صفحة استكشاف/بحث مستقلة في PR منفصل.
   - **ممنوع** إضافة `questions` أو `courses` أو أي filter آخر قبل بناء جدوله وendpoint حقيقي.
   - فلتر `news` فارغ بسبب غياب بيانات = **مقبول**. فلتر بدون جدول/API = **ممنوع**.

8. **`tw_jwt` is the auth token.** `localStorage.getItem('tw_jwt')` يُرسل كـ `Authorization: Bearer` في كل API call من Home V2.

9. **CSS offset is single-source:** الهيدر الموحّد `position:sticky` (في التدفق الطبيعي) — لا `padding-top` على الـ body؛ مسافة الشريط السفلي = `body.tw-has-bnav` (`app-header.css`). `.hw-fbar` هو `position:fixed` على `top:var(--ah-h,56px)`. ممنوع إضافة `margin-block-start` على `.hw-page`.

10. **`home.html` و `static/home-v2.js` محذوفان (PR-4).** ممنوع إعادتهما. Auth guard في `home.main.js` يقرر من `TwAuthSync.getSessionSnapshot()` فقط (expired/stale/invalid → `invalidateSession('home_guard')` ثم `/login`؛ guest أو TwAuthSync غير موجود → `/login`).

11. **App Header is unified.** `static/app-header.css` هو المرجع الرسمي لـ CSS vars وshared header classes (`.sc-header`, `.sc-hicon`, `.sc-home-btn`, `.sc-menu-*`). الهيدر نفسه = DS-HNAV (`docs/design-system/HEADER-NAV.md` — PR 3.2). ممنوع إنشاء header styles منفصلة لصفحة جديدة — يجب استخدام CSS vars من `app-header.css`. أي تعديل على شكل الهيدر يجب أن يكون في `app-header.css` فقط.

12. **Home مصمم لملايين المستخدمين — لا ديون تقنية.** قواعد إلزامية:
    - **ممنوع** إضافة feature جديدة فوق ملف واحد كبير — كل feature تذهب لـ module مناسب
    - **ممنوع** حلول مؤقتة أو TODO داخل production code
    - **ممنوع** `ORDER BY RANDOM()` في أي query على `/home/feed`
    - **ممنوع** table scan بدون index على columns مستخدمة في WHERE/ORDER — راجع `_migrate_feed_indexes()`
    - **مطلوب** اتباع `window.Home` namespace لأي module جديد
    - **مطلوب** تحديد module المناسب قبل إضافة أي سلوك جديد على Home
