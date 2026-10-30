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
   - `static/home-v2.css` — أنماط الصفحة (`.hw-*` namespace)
   - `static/home/home.utils.js` — constants + DOM helpers
   - `static/home/home.state.js` — shared state (`window.Home.state`)
   - `static/home/home.api.js` — feed fetch (`Home.api.loadFeed`)
   - `static/home/home.cards.js` — card renderers (opportunity / post / news) — post = `TwPostCard.html` (task 8.6b-2)
   - `static/home/home.posts.js` — company posts controller (task 8.6b-2): `TwPostCard.create` + `TwPostComments.create`, bound once to `#hwFeed`
   - `static/home/home.render.js` — feed UI states (skeleton / empty / error / feed)
   - `static/home/home.filters.js` — filter tab wiring + orchestration
   - ~~`static/home/home.header.js`~~ — deleted PR 3.2: header + bottom nav = unified app chrome (`<header data-tw-header>` / `<nav data-tw-bottom-nav>` — `docs/design-system/HEADER-NAV.md`)
   - `static/home/home.nav.js` — sidebar + banner per user type
   - `static/home/home.main.js` — bootstrap only (auth guard + init + load)
   - ممنوع دمج CSS/JS الكبير داخل HTML
   - **ممنوع** إضافة feature جديدة قبل تحديد module المناسب لها

4. **`/preview/home-v2` is deleted.** لا تعيد إضافته. Route المعاينة المؤقت أُزيل عند shipping Home V2.

5. **`GET /home/feed` is the feed API.** Auth: `Depends(verify_token)` — `user_id` من JWT فقط، ليس من query param. `filter` مُقيَّد server-side بـ allowlist: `{"all","opportunities","posts","news"}`.

6. **Rendering is always safe:** كل بيانات API تُعرض عبر `createElement` + `textContent`. لا `innerHTML = apiData`. السماح بـ `innerHTML` للـ skeleton الثابت، ولـ HTML بطاقة المنشور من `TwPostCard.html` بس (DS-CARD — كل حقل بيتعمله escape جوّا المكوّن، §54 — task 8.6b-2).

7. **Home feed filters are final: `all / opportunities / posts / news`.**
   - `opportunities` — يعرض `jobs` حالياً (مع `opp_type="job"`). مستقبلاً يدعم training/scholarship/overseas.
   - `news` — أخبار رسمية من `news_posts` table، يُنشر من الأدمن فقط.
   - **ممنوع** إعادة `companies` كـ filter — مكانها صفحة استكشاف/بحث مستقلة في PR منفصل.
   - **ممنوع** إضافة `questions` أو `courses` أو أي filter آخر قبل بناء جدوله وendpoint حقيقي.
   - فلتر `news` فارغ بسبب غياب بيانات = **مقبول**. فلتر بدون جدول/API = **ممنوع**.

8. **كل طلب عبر `twApi` (PR 4.1).** الـ JWT بيحطّه `twApi` (`getAuthHeaders`) — ممنوع `fetch` مباشر أو قراءة `tw_jwt` / `tw_user` بأي module. أرقام الشريط الجانبي والبانر من API بس: اكتمال الملف (emp) = `GET /profile/{id}/score` (الصندوق مخفي لحد ما يوصل الرقم أو لو فشل) · وظائف نشطة (co) = `GET /company/jobs?view=active` · رقم بدون API ما بينعرض (ممنوع `—` أو رقم ثابت). روابط الحساب = `twAccountHref(user)` بس (ممنوع `/profile` · `/company-profile` · `/edu-profile`).

9. **CSS offset is single-source:** الهيدر الموحّد `position:sticky` (في التدفق الطبيعي) — لا `padding-top` على الـ body؛ مسافة الشريط السفلي = `body.tw-has-bnav` (`app-header.css`). `.hw-fbar` هو `position:fixed` على `top:var(--ah-h,56px)`. ممنوع إضافة `margin-block-start` على `.hw-page`.

10. **`home.html` و `static/home-v2.js` محذوفان (PR-4).** ممنوع إعادتهما. Auth guard في `home.main.js` = `twRequireAuth()` (SHELL-09 — PR 4.1) بس.

11. **App Header is unified.** `static/app-header.css` هو المرجع الرسمي لـ CSS vars وshared header classes (`.sc-header`, `.sc-hicon`, `.sc-home-btn`, `.sc-menu-*`). الهيدر نفسه = DS-HNAV (`docs/design-system/HEADER-NAV.md` — PR 3.2). ممنوع إنشاء header styles منفصلة لصفحة جديدة — يجب استخدام CSS vars من `app-header.css`. أي تعديل على شكل الهيدر يجب أن يكون في `app-header.css` فقط.

12. **Home مصمم لملايين المستخدمين — لا ديون تقنية.** قواعد إلزامية:
    - **ممنوع** إضافة feature جديدة فوق ملف واحد كبير — كل feature تذهب لـ module مناسب
    - **ممنوع** حلول مؤقتة أو TODO داخل production code
    - **ممنوع** `ORDER BY RANDOM()` في أي query على `/home/feed`
    - **ممنوع** table scan بدون index على columns مستخدمة في WHERE/ORDER — راجع `_migrate_feed_indexes()`
    - **مطلوب** اتباع `window.Home` namespace لأي module جديد
    - **مطلوب** تحديد module المناسب قبل إضافة أي سلوك جديد على Home

13. **منشورات الشركات بالفيد = `TwPostCard` + `TwPostComments` (task 8.6b-2 — SYSTEMS_INDEX §12 / §61).** نفس بطاقة صفحة الشركة: أقدّر · حفظ · مشاهدة · وسوم · مشاركة · تعليقات بتنفتح **جوّا الفيد**.
    - الحقول من `GET /home/feed` (`theme_color` · `comments_enabled` · `author_type` + `auth.get_company_post_stats`) — نفس مصدر `/company/posts`.
    - controller واحد `home.posts.js` بيتربط بـ `#hwFeed` مرة وحدة (`home.main.js`) · `Home.render.renderFeed` → `Home.posts.remember(items)` قبل الرسم + `afterRender` (clamp + المشاهدة) بعده · إعادة الرسم بتبني لوحة جديدة من الصفر.
    - البطاقة ما بتنقل لأي مكان: الاسم واللوغو بس رابط `/u/{tw_id}` (`authorHref` = `twAccountHref`) · ما في تعديل / حذف من الفيد.
    - ⋯ = إبلاغ + حظر لغير الكاتب (task 8.6c — `authorId` = `author_id` · `viewerId` من snapshot الجلسة · SYSTEMS_INDEX §61) · الشركة على منشورها ما بتشوف ⋯ · الصفحة بتحمّل `tw-overlay.js` (DS-OVL — تأكيد الحظر + نافذة الإبلاغ).
    - ❌ بطاقة منشور خاصة بالرئيسية (`hw-p*`) · ❌ click على البطاقة كلها · ❌ controller تاني أو `bind` بكل رسم · ❌ نسخة محلية من التعليقات أو حساب العدّادات.
    - Test: `node tests/test_post_card_runtime.js` (M) · `node tests/test_home_landing_runtime.js` (J) · `python -m pytest tests/test_home_feed_posts_86b2.py -q`.

14. **تحميل المزيد بالفيد — السيرفر (task 8.6d-1 — SYSTEMS_INDEX §12).** `GET /home/feed?cursor=` بنفس شكل الرد `{items, filter, total, next_cursor}`؛ `next_cursor = null` لما تخلص كل الأنواع.
    - الترتيب: الوظائف = التطابق ↓ (`_taxonomy_score` بدون تعديل) ثم `created_at` ↓ ثم `id` ↓ على **كل** الوظائف النشطة (`job_active_sql` + `bs.active_sql` — الحظر ما بيخفي وظيفة، §25f) · المنشورات والأخبار = `created_at` ↓ ثم `id` ↓.
    - «الكل» = نمط ثابت بكل صفحة (وظيفة، منشور، خبر، …)، كل نوع بترتيبه؛ النوع اللي خلص مكانه بيروح للباقيين. ❌ ترتيب بالتاريخ بين الأنواع.
    - الوظائف: أول صفحة بتحفظ الترتيب الكامل بـ `feed_snapshots`؛ الصفحات اللاحقة بتمشي عليه بالـ offset وبتعيد فحص كل دفعة — المخفي / المعلّق بينشال بس، والمعدّل بيضل بمكانه. المنشورات والأخبار keyset مع `created_at <= as_of`.
    - الـ cursor موقّع HMAC-SHA256 (مفتاح مشتق من `JWT_SECRET` بـ label `feed_cursor`) · 422 `invalid_cursor` (توقيع / حساب / فلتر / انتهاء / شكل / قائمة حساب تاني) · 409 `feed_reset` (القائمة مش موجودة / منتهية / تغيّرت مهنة أو مهارات المستخدم).
    - الحدود من `tw_settings` بس: `feed_page_max` · `feed_snapshot_ttl_min` · `feed_snapshots_per_user`؛ التنظيف وقت الإدخال (ممنوع thread). فشل حفظ القائمة → أول صفحة عادي و `next_cursor = null`.
    - ❌ cursor بدون توقيع · ❌ قائمة بالذاكرة · ❌ رجوع حد الـ 200 وظيفة.
    - Test: `python -m pytest tests/test_home_feed_cursor_86d.py -q -s`.

15. **«عرض المزيد» بالفيد — الواجهة (task 8.6d-2 — SYSTEMS_INDEX §12).** زر واحد `#hwMoreBtn` آخر الفيد، بيطلع بس لما `Home.state.nextCursor` موجود (`next_cursor` من `GET /home/feed`)؛ ما في تحميل تلقائي مع السكرول.
    - `Home.api.loadMore(filter)` = نفس `twApi` + نفس `state.abortCtrl` (`?cursor=next_cursor`) — `loadFeed` (تغيير الفلتر) بيلغي الطلب الجاري وبيصفّر الـ cursor؛ الرد المتأخر بيرجع `null` وبينرمى. ضغطة تانية وقت التحميل ما بتبعت شي (الزر `disabled` + `common.loading`).
    - `Home.render.renderFeed(items, filter, true)` بيضيف تحت البطاقات بدون مسح · `state.seen` (`type:id`) حماية إضافية من التكرار · `Home.posts.remember(items, true)` بيدمج · `afterRender(feedEl, cards)`: الـ clamp على البطاقات الجديدة بس، و `trackViews(feedEl)` بيبدّل الـ observer الوحيد (المنشور اللي انحسب ما بينبعت مرة تانية) · الـ controller مربوط مرة وحدة على `#hwFeed` فالتعليقات / الإبلاغ / الحظر / أقدّر / الحفظ شغّالين على البطاقات المضافة.
    - 409 `feed_reset` / 422 `invalid_cursor` → `showToast(twT('home.more.reset'))` + نفس الفلتر من أوله · أي خطأ تاني → `home.more.error` جنب الزر + الزر نفسه «إعادة المحاولة» بنفس الـ cursor، والبطاقات بتضل · `next_cursor = null` → الزر بيختفي بدون رسالة.
    - ❌ تحميل تلقائي مع السكرول · ❌ `fetch` مباشر · ❌ `initClamps` على كل الفيد بعد إضافة (بيقصّ منشور مفتوح) · ❌ `bind` بكل صفحة.
    - Test: `node tests/test_home_landing_runtime.js` (K + L).
