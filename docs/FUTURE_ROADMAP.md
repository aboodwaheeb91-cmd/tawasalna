# Future Roadmap — تواصلنا

> **هذا الملف لتجميع الأفكار والخطط المستقبلية فقط.**
> وجود بند هنا لا يعني أنه مطلوب تنفيذه الآن.
> أي AI أو مطوّر ممنوع ينفذ أي بند من هذا الملف إلا بطلب صريح من المستخدم.
> إذا تعارض أي بند مع `ARCHITECTURE_FOUNDATION.md` — الدستور يفوز.

---

## Purpose

ملف Backlog مركزي لتسجيل الأفكار والتحسينات والقرارات المستقبلية لمنصة تواصلنا.
يُستخدم كمرجع أثناء التخطيط — وليس كأمر تنفيذي.

---

## Usage Rules

1. **لا تنفيذ بدون طلب صريح** من المستخدم. وجود البند هنا ليس إذناً بتنفيذه.
2. **عند تنفيذ بند** → انقله إلى قسم [Done](#done) مع رقم PR إن وجد.
3. **إذا تعارض بند مع `ARCHITECTURE_FOUNDATION.md`** → الدستور يفوز، حدّث البند أو احذفه.
4. **إذا احتاج بند قرار معماري** → ضعه في [Needs Decision Before Build](#needs-decision-before-build) أولاً.
5. **أبقِ كل بند صغيراً وواضحاً** — لا توصيف طويل، وصف سطر أو سطرين.
6. **هذا الملف لا يغيّر API ولا backend ولا database** — هو توثيق فقط.

---

## Priority Buckets

| المستوى | المعنى |
|---------|--------|
| **P0** | قريب / مهم جداً — سيُنفَّذ في أقرب فرصة |
| **P1** | مهم لكن ليس الآن |
| **P2** | تحسين UX/UI — مفيد لكن غير ضروري |
| **P3** | فكرة مستقبلية بعيدة |

---

## Areas

### Platform / Architecture

- [ ] **P1** — Service Worker / PWA: توثيق cache strategy في `ARCHITECTURE.md` (§32 في SYSTEMS_INDEX يشير لغياب التوثيق)
- [ ] **P1** — Field validation shared helper: دالة مشتركة للـ validation بدلاً من تكرار المنطق في كل صفحة
- [ ] **P1** — Unified Profile Settings Menu: توحيد زر وقائمة إعدادات البروفايل عبر employee/company/education — نفس الشكل والسلوك والخيارات المشتركة، مع إضافات حسب نوع الحساب. القائمة تُبنى حسب صلاحيات viewer من backend فقط — ممنوع الاعتماد على localStorage.
- [ ] **P1** — Unified Profile UI Tokens: قواعد موحدة لأحجام الواجهة (أيقونات، خطوط، مسافات، border radius، أزرار هيدر، meta text) عبر صفحات employee/company/education. لاحقاً تُنفَّذ عبر `static/shared/tw-ui-tokens.css` — لا تنشئ الملف حتى يُطلب صراحةً.
- [ ] **P1** — Unified Profile Media Sizing: توحيد قواعد عرض الصور في صفحات البروفايل (avatar دائري للموظف، rounded square logo للشركة والمؤسسة، نظام موحد للكفر). لا يعني تعديل upload/cropper الآن.
- [ ] **P1** — First-time Profile Setup Wizard: flow إعداد أولي خطوة بخطوة لحسابات جديدة بدلاً من صفحة فارغة. يختلف حسب نوع الحساب. يفرّق بين Required وRecommended. يدعم حفظ جزئي. لا يعتمد على frontend فقط — يحتاج backend support.
- [ ] **P1** — Unified section IDs: تعريف section IDs موحدة (`#posts`, `#jobs`, `#courses`, `#experience`, `#skills`, `#followers`) لدعم clickable stats وguided tour بشكل متسق وغير هش.
- [ ] **P2** — Unify `profile_follows` و `company_follows` في جدول واحد مع `entity_type` (يحتاج migration plan)

---

### Company Profile

- [ ] **P1** — Company/Education Poll Posts — "اسأل متابعينك": نوع منشور تفاعلي يسمح للشركات والمؤسسات بطرح سؤال مع خيارات تصويت. النتائج لا تظهر إلا بعد التصويت. صاحب الصفحة يرى النتائج دائماً. backend يمنع التصويت المتكرر ويتحقق من صحة الخيارات. لا اعتماد على localStorage في الحساب أو الصلاحيات. _(خيار single vs multi-choice: يحتاج قرار — انظر Needs Decision)_
- [ ] **P1** — Company/Education Verification Badge & Flow: شارة توثيق ظاهرة في الهيدر بجانب الاسم. حالات: غير موثق / قيد المراجعة / موثق / مرفوض يحتاج تعديل. صاحب الصفحة يرى CTA واضحاً "وثّق حسابك". إذا مرفوض يظهر السبب وخيار إعادة الإرسال. التوثيق backend-owned — يحتاج admin review flow.
- [ ] **P2** — Generic About Section Label: استبدال "عن الشركة" بعنوان عام مثل "حول" يصلح لكل أنواع الكيانات (مصنع، مؤسسة، محل، مركز، منظمة). لاحقاً يمكن جعله ديناميكياً حسب `entity_type`.
- [ ] **P2** — Improve empty states: أيقونة + CTA واضحة عند عدم وجود وظائف أو منشورات
- [ ] **P2** — Company analytics dashboard: عدد مشاهدات الوظائف والمتقدمين في لوحة داخلية للمالك

---

### Employee Profile

- [ ] **P1** — Employee Profile Posts: قسم منشورات داخل بروفايل الموظف يسمح بنشر تحديثات مهنية ومعرفية (إنجازات، خبرات، مشاريع، شهادات، طلب نصيحة، تحديث مهني، البحث عن فرصة). ظهوره في feed يحتاج قرار منفصل.
- [ ] **P2** — Improve public profile empty states: أيقونة + CTA عند غياب خبرة أو مهارات
- [ ] **P3** — Drag-to-reorder profile sections (Needs Decision Before Build)

---

### Education Profile

- [ ] **P1** — Company/Education Poll Posts — "اسأل متابعينك": نفس نظام Polls المذكور في Company Profile — مفتوح للمؤسسات التعليمية من نفس الإطلاق الأول. _(خيار single vs multi-choice وfollowers-only: يحتاج قرار — انظر Needs Decision)_
- [ ] **P1** — Company/Education Verification Badge & Flow: نفس نظام التوثيق المذكور في Company Profile — ينطبق على المؤسسات التعليمية بنفس الحالات والسلوك.
- [ ] **P1** — Unified Settings Menu (Education extensions): نفس القائمة الموحدة مع إضافات خاصة بالمؤسسة: إدارة الدورات، إعدادات الاعتمادات أو التوثيق.
- [ ] **P2** — Education profile public page: تحسين عرض الدورات والتحقق في الصفحة العامة

---

### Jobs & Applications

- [ ] **P1** — Save System backend: تنفيذ `saved_jobs` table + `/jobs/{id}/save` endpoint (UI placeholder موجود)
- [ ] **P2** — Job search page: صفحة بحث مستقلة بفلاتر متقدمة (مدينة، نوع، مهارة)

---

### Posts / Comments / Mentions

- [ ] **P2** — Post reporting: زر إبلاغ عن منشور مع `reports` table (§24 في SYSTEMS_INDEX)
- [ ] **P3** — Post media: دعم صور في المنشورات (يحتاج قرار storage + API)

---

### Notifications

- [ ] **P1** — Comment / mention notifications (Phase 3): إشعار لصاحب المنشور عند التعليق، وللشخص المذكور عند @mention
- [ ] **P2** — Push notifications (PWA): إشعارات browser عبر Service Worker

---

### Messaging

- [ ] **P0** — WebSocket Security Hardening (P0 Security Debt): تحقق JWT على `/ws/{user_id}` — موثَّق في SYSTEMS_INDEX §18
- [ ] **P2** — Message read receipts UI: عرض "تمت القراءة" في واجهة المحادثة

---

### Admin Dashboard

- [ ] **P1** — Reports review panel: واجهة أدمن لمراجعة البلاغات (`reports` table موجود)
- [ ] **P1** — Verification requests review: واجهة أدمن لمراجعة طلبات توثيق الشركات والمؤسسات (مرتبط بـ Verification Badge & Flow)
- [ ] **P2** — News posts management: إنشاء وتعديل وحذف `news_posts` من لوحة الأدمن

---

### Mobile App Readiness

- [ ] **P1** — API audit for mobile: مراجعة كل endpoints وتأكيد JSON نظيف + pagination + error shapes (F8 في ARCHITECTURE_FOUNDATION)
- [ ] **P2** — Flutter/React Native prototype: تقييم framework الجوال

---

### UI/UX Polish

- [ ] **P1** — Interactive Profile Stats / Clickable Counters: تحويل عدادات الهيدر (منشورات، وظائف، دورات، خبرات، مهارات، متابعون) إلى عناصر تفاعلية تعمل smooth scroll إلى القسم المرتبط في الصفحة، أو تفتح modal مناسب. الرقم صفر → ينقل إلى القسم مع empty state. يتطلب section IDs موحدة واccessible.
- [ ] **P2** — First-time Guided Tour / Page Coach: جولة إرشادية لصاحب الصفحة عند أول دخول — رسائل صغيرة تشرح أجزاء الصفحة مع خيارات "التالي / تخطي / عدم الإظهار مرة أخرى". لا تظهر للزائر. تختلف حسب نوع الحساب. يُفضَّل لاحقاً حفظ الحالة في backend user preferences. _(localStorage مؤقتاً مقبول إذا وُثِّق كحل مؤقت — انظر Needs Decision)_
- [ ] **P2** — Unified toast system: shared helper بدلاً من `showToast` مكرر في كل صفحة
- [ ] **P2** — Dark mode refinements: مراجعة تباين الألوان على الشاشات المختلفة

---

### Performance

- [ ] **P1** — Feed indexes audit: مراجعة `_migrate_feed_indexes()` والتأكد من indexes على columns مستخدمة في WHERE/ORDER
- [ ] **P2** — Lazy loading for company posts: تحميل المنشورات عند التمرير بدلاً من كلها دفعة واحدة

---

### Security

- [ ] **P0** — WebSocket auth hardening (مكرر من Messaging — مذكور للأولوية)
- [ ] **P1** — `POST /auth/verify-token` endpoint: التحقق من صلاحية JWT من client قبل الاعتماد على localStorage (موثَّق في CLAUDE.md §Auth Gateway Rules §6)
- [ ] **P2** — Rate limiting audit: مراجعة rate limits على endpoints الحساسة (تعليق، تقدير، متابعة)

---

## Needs Decision Before Build

هذه بنود تحتاج **قرار معماري صريح** قبل البدء بأي تنفيذ:

| الفكرة | السبب |
|--------|-------|
| Drag-to-reorder profile sections | يحتاج قرار: هل الترتيب يُحفظ في DB أم localStorage؟ schema جديد؟ |
| Post media (صور في المنشورات) | يحتاج قرار: storage bucket + حد الحجم + CDN policy |
| Unify follows tables (`profile_follows` + `company_follows`) | يحتاج migration plan كامل + backward compat test |
| Flutter vs React Native | قرار platform قبل بدء أي mobile work |
| Real-time notifications via WebSocket | يتوقف على حل P0 Security Debt في WebSocket أولاً |
| Employee Polls — السماح للموظفين بإنشاء Polls | الميزة قد تزيد social noise إذا فُتحت مبكراً. يُقيَّم بعد إطلاق Polls للشركات والمؤسسات أولاً. |
| Poll choice type — single vs multi-choice | هل النسخة الأولى تدعم اختياراً واحداً فقط أم متعدداً؟ قرار يُحسم وقت التنفيذ. |
| Poll audience — من يحق له التصويت؟ | followers فقط أم كل المستخدمين المسجّلين؟ يؤثر على DB schema والـ privacy model. |
| Company/Education logo shape — circle or rounded square? | الموظف: avatar دائري محسوم. الشركة والمؤسسة: circle أم rounded square؟ القرار يؤثر على Unified Media Sizing وcropper config. |
| Verification documents storage | أين تُخزَّن وثائق توثيق الشركات/المؤسسات؟ نفس Supabase bucket؟ bucket منفصل؟ |
| Setup Wizard completion state — backend or localStorage? | هل نحفظ تقدم المستخدم في الـ wizard في backend (user preferences table) أم يكفي localStorage مؤقتاً؟ |
| Guided Tour completion state — backend or localStorage? | نفس قرار الـ Setup Wizard. localStorage مقبول كحل مؤقت إذا وُثِّق صراحةً. |

---

## Done

| البند | PR | التاريخ |
|------|-----|---------|
| Skeleton loading for public profile pages (employee + company) | #424 | 2026-07-09 |
| Legacy profile.html QR/share route fixed to `/u/{tw_id}` | #426 | 2026-07-09 |
| Public profile error and retry state (employee + company) | #427 | 2026-07-09 |
| iOS PWA meta tags for `profile-showcase.html` | #428 | 2026-07-09 |
| Architecture Foundation (`ARCHITECTURE_FOUNDATION.md`) — 28 rules | #420 | 2026-07-09 |

---

*أُنشئ: 2026-07-09 — آخر تحديث: 2026-07-09 (Profile System Ideas: Employee Posts, Polls, UI Tokens, Media Sizing, Settings Menu, Verification Badge, Interactive Stats, Setup Wizard, Guided Tour)*
