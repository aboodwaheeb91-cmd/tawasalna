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
- [ ] **P2** — Unify `profile_follows` و `company_follows` في جدول واحد مع `entity_type` (يحتاج migration plan)

---

### Company Profile

- [ ] **P2** — Improve empty states: أيقونة + CTA واضحة عند عدم وجود وظائف أو منشورات
- [ ] **P2** — Company analytics dashboard: عدد مشاهدات الوظائف والمتقدمين في لوحة داخلية للمالك

---

### Employee Profile

- [ ] **P2** — Improve public profile empty states: أيقونة + CTA عند غياب خبرة أو مهارات
- [ ] **P3** — Drag-to-reorder profile sections (Needs Decision Before Build)

---

### Education Profile

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
- [ ] **P2** — News posts management: إنشاء وتعديل وحذف `news_posts` من لوحة الأدمن

---

### Mobile App Readiness

- [ ] **P1** — API audit for mobile: مراجعة كل endpoints وتأكيد JSON نظيف + pagination + error shapes (F8 في ARCHITECTURE_FOUNDATION)
- [ ] **P2** — Flutter/React Native prototype: تقييم framework الجوال

---

### UI/UX Polish

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

*أُنشئ: 2026-07-09 — ملف Backlog/Roadmap للأفكار المستقبلية. لا يعطي صلاحية تنفيذ بدون طلب صريح.*
