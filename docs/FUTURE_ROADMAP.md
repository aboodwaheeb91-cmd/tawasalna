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

> **ملاحظة — مراجعة أمنية شاملة مؤجلة:**
> مراجعة الأمن الشاملة للمنصة (security audit كامل للـ endpoints والـ auth flow والـ permissions) مؤجلة إلى ما بعد اكتمال ميزات المنصة الأساسية.
> الأولوية الآن هي بناء الوظائف. بعد الانتهاء من الـ core features يُفتح PR مستقل بعنوان واضح للمراجعة الأمنية.
> ليس معنى التأجيل إهمال الأمن — الـ P0 Security Debt (WebSocket) لا يزال مفتوحاً ويجب حله.

---

---

## Future Product Notes — Global Platform, Education, Trust, Monetization, and Internal Collaboration

> **هذا القسم يوثّق رؤية المنتج المستقبلية ومتطلباتها المعمارية عالية المستوى.**
> لا تنفيذ لأي بند إلا بطلب صريح من المستخدم.
> أُضيف هذا القسم بعد اكتمال Notifications V2 (PR #453) قبل البدء بـ Missing Priority Queue.

---

### 1. Full Internationalization / Localization

الموقع حالياً عربي بالكامل. مستقبلاً يجب أن يدعم نظام لغات عالمي.

**المطلوب مستقبلاً:**

- كل نصوص الموقع قابلة للترجمة — لا hardcoded Arabic داخل HTML/JS في الأنظمة الجديدة.
- المستخدم يختار اللغة من الإعدادات.
- عند اختيار English أو أي لغة LTR:
  - اتجاه الموقع يتحول إلى left-to-right.
  - التخطيط، المحاذاة، القوائم، spacing، والأيقونات تتحول بشكل صحيح.
- عند اختيار Arabic أو أي لغة RTL:
  - اتجاه الموقع يتحول إلى right-to-left.
- النظام جاهز لأي لغة مستقبلية — ليس فقط Arabic/English.
- لا حلول متفرقة صفحة بصفحة — i18n architecture موحدة للموقع كله.
- `dir="rtl"` / `dir="ltr"` يُضبط ديناميكياً حسب اللغة المختارة، ليس hardcoded في HTML.

**الأساس المعماري المطلوب:**

- ملف translations مركزي (مثل `i18n/ar.json`, `i18n/en.json`).
- helper واحد `t("key")` يُستخدم في كل الصفحات.
- backend يدعم `Accept-Language` header أو user preference مستقبلاً.

**مهم:** هذا بعد اكتمال أساس الموقع — ليس الآن.

---

### 2. Global Countries & Flags

بيانات الدول يجب أن تكون عالمية وليست محصورة بالدول العربية.

**لكل دولة نحتاج:**

- `name_ar` — الاسم بالعربية.
- `name_en` — الاسم بالإنجليزية.
- `name_local` — الاسم باللغة المحلية إذا اختلف.
- `iso_code` — مثل `JO`, `US`, `CN`, `DE`.
- `flag` — ملف SVG موثوق (نفس نظام flags/*.svg الموجود، يُوسَّع ليشمل العالم).
- `dial_code` — مفتاح الاتصال الدولي (+962, +1, +86) إذا احتجناه.
- دعم البحث داخل قائمة الدول (بالعربية والإنجليزية والاسم المحلي).
- عرض العلم بجانب اسم الدولة في كل dropdown.
- مصدر بيانات موثوق وموحد (مثل `restcountries.com` أو `geonames.org` أو حزمة npm موثوقة).

**قاعدة ثابتة:**
ممنوع مستقبلاً hardcoded country lists عشوائية. كل بيانات الدول تأتي من `TW.COUNTRY_MAP` الموسَّع (الحالي: دول عربية فقط).

**الأولوية:** توسيع `tw-options-data.js` بدول العالم كخطوة مشتركة تسبق أي feature تحتاجها.

---

### 3. Global World Directory

فكرة World Directory عالمي يشمل المؤسسات الأساسية في كل بلد.

**الأنواع المستقبلية:**

- جامعات العالم.
- مدارس العالم (حسب توفر البيانات المفتوحة).
- مستشفيات العالم.
- مراكز تدريب.
- مؤسسات تعليمية وصحية أساسية.
- جهات معروفة وأساسية حسب البلد.

**Schema المقترح لكل مؤسسة:**

```
name_en          TEXT        الاسم الإنجليزي الرسمي
name_local       TEXT        الاسم باللغة المحلية
name_ar          TEXT        الاسم العربي إذا توفر
aliases          TEXT[]      اختصارات وتهجئات مختلفة وأسماء قديمة
country          TEXT        ISO code مثل JO, CN, DE
city             TEXT        المدينة الرئيسية
type             TEXT        university / school / hospital / training_center / institution
website          TEXT        الموقع الرسمي إذا توفر
location         TEXT        العنوان التفصيلي إذا توفر
data_source      TEXT        مصدر البيانات: wikidata / geonames / manual / user_submitted
verification_status TEXT     imported / user_submitted / verified / needs_review
```

**قواعد:**

- لا hardcoding عشوائي — البيانات تأتي من datasets مفتوحة أو APIs موثوقة.
- يمكن لاحقاً السماح للمستخدم باقتراح مؤسسة غير موجودة، لكن تمر بمراجعة قبل اعتمادها.
- البحث يدعم العربية والإنجليزية والاسم المحلي والـ aliases.
- المؤسسات المقترحة من المستخدم تبقى `user_submitted` حتى تراجعها الإدارة.

**الأولوية:** يُبنى هذا النظام كـ `world_directory` table في DB قبل أي integration.

---

### 4. Institution Naming Rule

قاعدة ثابتة لتسمية الجامعات والمؤسسات العالمية داخل المنصة.

**لكل مؤسسة:**

| الحقل | الوصف |
|-------|-------|
| `name_en` | الاسم الإنجليزي الرسمي أو الأكثر استخداماً دولياً |
| `name_local` | الاسم باللغة المحلية للبلد |
| `name_ar` | الاسم العربي إذا كان موجوداً أو مطلوباً للعرض العربي |
| `aliases` | اختصارات، تهجئات مختلفة، أسماء قديمة، أسماء شائعة |

**أمثلة:**

```
الأردن:
  name_en:    University of Jordan
  name_local: الجامعة الأردنية
  name_ar:    الجامعة الأردنية
  aliases:    [UJ, الجامعة]

الصين:
  name_en:    Tsinghua University
  name_local: 清华大学
  name_ar:    جامعة تسينغهوا
  aliases:    [THU, Qinghua]
```

**Display logic حسب لغة الموقع:**

- إذا لغة الموقع **English**: اعرض `name_en` أولاً، ويمكن عرض `name_local` تحته.
- إذا لغة الموقع **Arabic**: اعرض `name_ar` إذا موجود، وإلا `name_en`، ويمكن عرض `name_local` تحته.
- إذا لغة الموقع **نفس لغة البلد**: اعرض `name_local` أولاً مع `name_en` كاسم عالمي.
- البحث يعمل عبر `name_en` + `name_ar` + `name_local` + `aliases` معاً.

---

### 5. Smart Selection Instead of Manual Typing

المستخدم لا يكتب إلا عند الضرورة القصوى. الأفضل أن يختار من قوائم ذكية وبيانات موثوقة.

**أمثلة:**

- اختيار الدولة من قائمة عالمية.
- اختيار المدينة حسب الدولة (dependent select).
- اختيار الجامعة حسب الدولة.
- اختيار المدرسة حسب الدولة.
- اختيار المستشفى حسب الدولة.
- اختيار التخصصات من قوائم جاهزة.
- اختيار المسمى الوظيفي من اقتراحات.
- اختيار القطاع / المجال / نوع المؤسسة.
- اختيار اللغات والمهارات من قوائم مع بحث.

**UI Patterns المطلوبة:**

```
searchable dropdowns         — البحث داخل القائمة أثناء الكتابة
autocomplete                 — اقتراحات تظهر أثناء الكتابة
dependent selects            — country → city → institution (كل مستوى يعتمد على السابق)
"غير موجود؟ أضف اقتراحاً"  — خيار أخير عند غياب المؤسسة، يحتاج مراجعة قبل اعتماد
```

**قاعدة ثابتة مستقبلاً:**

أي نموذج جديد يجيب على هذا السؤال أولاً:
> هل هذا الحقل يمكن أن يكون اختياراً من قائمة بدل input يدوي؟

إذا نعم → لا نستخدم input عادي إلا لسبب واضح ومبرر.

---

### 6. Educational Institution Platform

المؤسسة التعليمية ليست مجرد نسخة من الشركة — هي product area مستقبلية مستقلة.

**الفكرة:**

Educational Institution Profile يشبه صفحة الشركة من حيث: header، logo/cover، posts، followers، verification، settings، notifications، contact.

لكن بهوية تعليمية خاصة:

```
courses              دورات تدريبية
training programs    برامج تدريبية متكاملة
free / paid courses  دورات مجانية أو مدفوعة
online / offline / hybrid  طريقة التقديم
trainers             إدارة المدرّبين والأساتذة
student registration تسجيل الطلاب
training offers      إرسال عروض تدريبية للشركات والجهات
certificates         شهادات (مرحلة لاحقة)
reviews              تقييمات (مرحلة لاحقة)
```

**القاعدة المعمارية:**

لا نبني منصة تعليمية منفصلة.
نبنيها فوق نفس shared backend/profile/notifications/permissions/upload architecture.
كل شيء من `server.py` و PostgreSQL الحالي (F3).

---

### 7. Education Platform Roles

الأدوار في منظومة التعليم على المنصة:

#### Student (الطالب)

- يبحث عن دورات.
- يسجّل في دورات.
- يرى دوراته المسجَّل بها.
- يستلم إشعارات دوراته.
- يستطيع حضور الدورة أونلاين إذا متاح.
- يحصل على شهادة إذا أنهى الدورة وكانت تدعم ذلك (مرحلة لاحقة).

#### Educational Institution (المؤسسة التعليمية)

أنواعها:
```
مركز تدريب / معهد / مدرسة / جامعة / أكاديمية / جهة تدريب مرخصة
```

هي الجهة المسؤولة عن:

- إنشاء الدورات ونشر البرامج.
- إدارة تسجيل الطلاب.
- تعيين الأساتذة والمدرّبين.
- إرسال عروض تدريبية للشركات والمدارس والجامعات.
- طلب توظيف أساتذة.
- إصدار شهادات (مرحلة لاحقة).

#### Teacher / Trainer (الأستاذ / المدرّب)

- له بروفايل شخصي (emp account).
- لا يستطيع نشر دورة رسمية أو مدفوعة من حسابه الشخصي مباشرة.
- يظهر كمدرّب داخل دورة تابعة لمؤسسة تعليمية مسؤولة.
- يمكنه الانضمام لمؤسسة أو التقديم كمدرّب.
- يمكن أن يكون مشهوراً — لكن الدورة تبقى باسم مؤسسة تعليمية مسؤولة.

**القاعدة الذهبية:**

> No official course without a responsible educational institution.
> الأستاذ يدرّس. الطالب يتعلم. المؤسسة تنشر وتدير وتتحمل المسؤولية.

---

### 8. Courses and Training Offers

#### Courses V1 — مكونات الدورة

```
title                عنوان الدورة
description          وصف تفصيلي
category             التصنيف
level                beginner / intermediate / advanced
free / paid          مجانية أم مدفوعة
price                السعر إذا مدفوعة
online / offline / hybrid  طريقة التقديم
location             المكان إذا حضوري
online_link          رابط الحضور إذا أونلاين
start_date           تاريخ البداية
end_date             تاريخ النهاية
seats                عدد المقاعد
certificate_available  هل تصدر شهادة؟
language             لغة التدريس
instructor           المدرّب
target_audience      students / employees / companies / schools / universities / public
```

#### Training Offers — عروض التدريب

المؤسسة التعليمية تقدر ترسل عروض تدريب رسمية إلى:
- companies (شركات)
- schools (مدارس)
- universities (جامعات)
- other institutions (جهات أخرى)

**العرض يحتوي:**

```
target_organization  الجهة المستهدفة
program_title        عنوان البرنامج
description          وصف مفصّل
duration             المدة
free / paid          مجانية أم مدفوعة
proposed_price       السعر المقترح
online / offline / hybrid
expected_participants  عدد المشاركين المتوقع
proposed_dates       التواريخ المقترحة
attachments          مرفقات (مرحلة لاحقة)
status               pending / accepted / rejected / needs_changes / completed
```

---

### 9. Education Content Safety

**القاعدة الأساسية:**

لا توجد دورة، بث، فيديو، أو محتوى تعليمي رسمي إلا تحت مؤسسة تعليمية معتمدة/مقبولة داخل المنصة.
الأستاذ لا يفتح دورة فيديو من حسابه الشخصي مباشرة.
الأستاذ يظهر كمدرّس داخل مؤسسة تعليمية مسؤولة.

**Safety Layers:**

```
1. المؤسسة التعليمية فقط تنشر الدورات.
2. المؤسسة تحتاج تحقق أو مراجعة قبل تفعيل الدورات.
3. الأستاذ مرتبط بمؤسسة — لا يعمل منفرداً.
4. أي دورة فيديو تكون بحالة:
   draft → pending_review → approved / rejected / suspended
5. المحتوى المدفوع أو الفيديوهات لا تظهر للعامة إلا بعد الموافقة.
6. report button واضح للمحتوى المخالف.
7. البلاغات الخطيرة تؤدي لإخفاء مؤقت لحين المراجعة (auto-hold).
8. فحص الروابط الخارجية داخل وصف الدورة (حماية من phishing).
```

**Audit Log المطلوب لاحقاً:**

```
من أنشأ الدورة؟
من رفع الفيديو؟
من وافق؟
متى تم التعديل؟
من أبلغ؟
```

**Penalties:**

```
suspend course / suspend institution / ban teacher / request additional verification
```

**السبب:**
منع إساءة استخدام "تعليمي" كغطاء لمحتوى مخالف أو احتيالي.

---

### 10. Educational Institution Verification Gate

الصفحة التعليمية لا تستطيع استخدام الميزات الحساسة إلا بعد التحقق المناسب.

**قبل التحقق (Unverified):**

```
✅ صفحة تعريفية محدودة
✅ تعديل معلومات أساسية
❌ لا نشر دورات
❌ لا رفع فيديوهات
❌ لا بيع دورات
❌ لا إصدار شهادات
❌ لا إرسال عروض تدريب
❌ لا تعيين مدربين رسميين على دورات منشورة
```

**بعد التحقق:**

```
✅ تفعيل الدورات
✅ تفعيل التسجيل
✅ تفعيل العروض التدريبية
✅ تفعيل إدارة المدرّبين
✅ تفعيل الفيديوهات (حسب سياسة المنصة)
```

**Country-Based Verification:**

كل بلد له متطلبات تحقق مختلفة. أمثلة على الوثائق المطلوبة:

```
رقم ترخيص تعليمي
رقم تسجيل شركة أو مؤسسة
الاسم القانوني
وثيقة من وزارة التعليم / وزارة العمل / هيئة التدريب
رابط حكومي رسمي إن وجد
بريد رسمي بنطاق المؤسسة (ليس Gmail)
موقع رسمي
عنوان فعلي
رقم هاتف رسمي
إثبات ملكية الدومين
إثبات أن مقدم الطلب مخوَّل بإدارة الصفحة
```

**Verification Levels:**

| المستوى | الوصف |
|---------|-------|
| Level 0 | Unverified — صفحة مقيَّدة |
| Level 1 | Basic Verified — معلومات أساسية تحققت |
| Level 2 | Licensed Education Provider — مرخصة رسمياً |
| Level 3 | Trusted / High Trust — موثوقية عالية |

**Risk Score:**

يزيد الثقة:
```
بريد رسمي بدومين المؤسسة
موقع رسمي واضح
سجل حكومي أو تعليمي قابل للتحقق
رقم ترخيص قابل للتحقق
عنوان مطابق + هاتف مطابق + اسم قانوني مطابق
وجودها على مصادر موثوقة (ويكيبيديا، بيانات وزارات)
```

يرفع الخطر:
```
Gmail فقط (لا دومين مؤسسي)
لا موقع رسمي
وثائق غير واضحة أو منقوصة
اختلاف الأسماء بين الوثائق والصفحة
رقم شخصي فقط
عنوان غير واضح
طلب سريع لنشر فيديوهات أو بيع دورات قبل إتمام التحقق
```

---

### 11. Monetization and Access Control Before Launch

الموقع حالياً مفتوح أثناء التطوير. قبل الإطلاق الرسمي يجب عمل Access Control + Premium Monetization.

**تقسيم الميزات:**

| المستوى | المعنى |
|---------|--------|
| Free | متاح لكل المستخدمين |
| Verified | يحتاج تحقق مسبق |
| Premium | اشتراك مدفوع |
| Premium + Verified | الاثنان معاً |
| Admin Approved | موافقة يدوية من الإدارة |

**أمثلة Gate Matrix:**

**Employee:**
```
profile basic:         Free
images:               Free
boosted visibility:   Premium
profile analytics:    Premium
verification:         Verified
high-volume messages: limited أو Premium
```

**Company:**
```
basic page:           Free
limited jobs (3-5):   Free أو Trial
many jobs:            Premium
featured job:         Premium
applicant analytics:  Premium
verification:         Verified
mass outreach:        Premium + Verified
```

**Educational Institution:**
```
basic page:           Free
publish courses:      Verified
video uploads:        Verified + Admin Approved
paid courses:         Verified + Premium
certificates:         Verified + High Trust (Level 3)
training offers:      Verified + Premium
```

**القاعدة المعمارية:**

```
لا نعتمد على إخفاء الأزرار وحده (F6 + F21).
أي Premium/Verified feature يُقفل من backend أيضاً.
Frontend يخفي للـ UX — Backend يمنع التنفيذ.
```

**مراحل تنفيذ Monetization مستقبلاً:**

```
1. Feature Inventory         — حصر كل الميزات وتصنيفها
2. Gate Matrix               — جدول من يرى ماذا
3. Backend Permission Gates  — فحوصات في server.py
4. Frontend Upgrade UX       — شاشات الترقية وعرض الفوائد
5. Subscriptions             — نظام الاشتراكات + plans
6. Payment Integration       — دفع إلكتروني (يحتاج قرار gateway)
7. Launch QA                 — اختبار شامل قبل الإطلاق
```

---

### 12. Admin Support / Business Messenger

نظام تواصل رسمي بين إدارة تواصلنا والحسابات المهمة.

**المستهدفون:**

```
companies (شركات)
educational institutions (مؤسسات تعليمية)
training centers (مراكز تدريب)
schools / universities (مستقبلاً)
verified accounts
premium / business / education accounts
```

**أنواع الطلبات:**

```
technical issue       مشكلة تقنية
verification request  طلب توثيق
subscription/payment  اشتراك أو دفع
job issue             مشكلة وظيفة
course issue          مشكلة دورة
suggestion            اقتراح
report                بلاغ
partnership           طلب شراكة أو تعاون
```

**النموذج:** Support Tickets + Chat

**من جهة الشركة/المركز:**

```
يفتح محادثة (ticket) مع تواصلنا
يختار نوع الطلب
يكتب الرسالة
يرفق ملف أو صورة (مرحلة لاحقة)
يرى الردود وحالة الطلب:
  open / waiting_reply / in_progress / solved / closed
```

**من جهة الأدمن:**

```
inbox لكل الطلبات
filters حسب النوع والأولوية والحالة
رد باسم فريق تواصلنا
internal notes (لا تظهر للمستخدم)
assign to admin (مرحلة لاحقة)
close / reopen ticket
```

**Auto Reply:**

- رد آلي حسب نوع الطلب (confirmation + توقع وقت الرد).
- لا يستبدل الدعم الحقيقي — للإشعار فقط.

**Support Priority:**

```
Free:            normal priority
Verified:        higher priority
Premium:         higher priority
Enterprise/Edu+: priority support
safety/security/content reports: أعلى أولوية بغض النظر عن الخطة
```

**مهم — التمييز الواضح:**

```
❌ هذا ليس User Messaging (messages.html)
❌ هذا ليس Company Internal Groups
✅ هذا قناة رسمية بين الحساب وإدارة المنصة فقط
```

---

### 13. Company Internal Groups / Team Channels

الشركة تقدر تنشئ groups داخلية لأعضائها وموظفيها.

**Owner:**

الشركة / صاحب الشركة / company admin

**Members:**

- موظفون داخل الشركة (بروفايلات emp).
- يُضيفهم صاحب الشركة أو admin الشركة.
- لاحقاً: أقسام (Departments) مثل HR / Sales / Training / Project Team.

**Group Modes:**

**1. Chat Mode:**
كل الأعضاء يقدروا يرسلوا رسائل.

**2. Announcement / Discussion Mode:**
الشركة فقط تنشر رسائل أساسية (announcements).
الأعضاء يقدروا يعلقوا على رسالة الشركة — حسب إعدادات الجروب.

**Read Receipts:**

صاحب الجروب أو admin الشركة يرى:
```
عدد الذين شاهدوا الرسالة
عدد الذين لم يشاهدوها
قائمة من شاهد + وقت المشاهدة
قائمة من لم يشاهد بعد
```

**Group Permissions:**

```
create group
edit name / description / image
add / remove members
choose group mode (chat / announcement)
choose who can send
choose who can comment
pin message
delete / moderate message
archive group
```

**أمثلة Groups:**

```
الإدارة / الموارد البشرية / المبيعات / الدعم الفني
التدريب / مشروع معين / الموظفون الجدد / إعلانات الشركة
```

**التمييز الواضح (مهم):**

```
❌ هذا ليس Direct Messaging (messages.html) — رسائل فردية 1-to-1
❌ هذا ليس Admin Support Messenger — تواصل مع إدارة المنصة
✅ هذا قنوات داخلية بين الشركة وموظفيها فقط
```

**Company Groups Monetization:**

| الخطة | الحد |
|-------|------|
| Free | جروبات محدودة (2-3) + أعضاء محدودون (10-20) + لا read receipts |
| Premium / Business | جروبات أكثر + أعضاء أكثر + read receipts + pinned messages + advanced permissions + archive/search |
| Enterprise | جروبات غير محدودة + departments + advanced reporting + export (مستقبلاً) |

---

### 14. Next Phase Marker

```
NEXT ACTIVE DEVELOPMENT PHASE:
rating notification hook
```

**Missing Priority Queue المتبقي من `docs/NOTIFICATIONS_PLAN.md`:**

```
✅ DONE: application_status_changed hook (PR #455) + Policy correction (PR #456)
         — accepted/rejected = internal states. viewed + fallback مسموحان.

P2: rating notification hook
    — company_ratings لا تولّد إشعاراً حالياً — مرحلة منفصلة.

P2: job_expiring_soon notification
    — يحتاج scheduler أو cron job — مؤجل بسبب غياب infrastructure.

Phase 11: Realtime / Push
    — مؤجل حتى قرار صريح + حل P0 Security Debt على WebSocket.
```

**لا تنفيذ لأي Future Product Note** في هذا الملف — هذا توثيق رؤية فقط.

---

### 15. Appointments & Interview Rooms System

> **توثيق رؤية — لا تنفيذ الآن. لا schema، لا صفحات، لا endpoints.**
> يُبنى هذا النظام بطلب صريح من المستخدم.

#### الفكرة العامة

نظام مستقل للمواعيد والمقابلات، مرتبط بالوظائف والإشعارات، لكنه ليس بديلاً عن Messenger العام.

**القاعدة الأساسية:**

| القناة | الغرض |
|--------|--------|
| **Messenger العام** | الكلام العام بين المستخدمين |
| **Appointment Room** | محادثة خاصة بموعد واحد محدد |
| **Notifications** | أحداث قابلة للفعل (دعوة جديدة، رد، تذكير) |

- كل Appointment له غرفة خاصة.
- أي كلام متعلق بموعد محدد يكون داخل غرفة الموعد — وليس في الماسنجر العام.
- القرارات الرسمية (موافقة / طلب تغيير موعد) تكون بزر رسمي — لا برسالة نصية.

---

#### زر المواعيد

زر "المواعيد" يظهر في navigation bar:

- **عند الموظف:** يعرض بطاقات مواعيده مع الشركات.
- **عند الشركة:** يعرض بطاقات مواعيد المرشحين/المتقدمين.

---

#### صفحة المواعيد — بطاقات فقط

**بطاقة الموظف:**

| الحقل | المحتوى |
|-------|---------|
| اسم الشركة | الشركة التي أرسلت الدعوة |
| اسم الوظيفة | الوظيفة المرتبطة |
| حالة الموعد | pending_response / confirmed / cancelled / ... |
| التاريخ والوقت | الموعد المقترح |
| المتبقي على الموعد | عداد تنازلي |
| زر | فتح غرفة الموعد |

**بطاقة الشركة:**

| الحقل | المحتوى |
|-------|---------|
| اسم المتقدم | الموظف المدعو |
| اسم الوظيفة | الوظيفة المرتبطة |
| حالة الدعوة | pending_response / confirmed / expired / ... |
| آخر رد | آخر رسالة أو إجراء من الموظف |
| الموعد المقترح | التاريخ والوقت |
| زر | فتح غرفة الموعد |

---

#### غرفة الموعد (Appointment Room)

كل appointment له غرفة تحتوي:

| العنصر | التفاصيل |
|--------|---------|
| ملخص الموعد | نوع المقابلة + الوظيفة |
| التاريخ والوقت | أونلاين / حضوري |
| رابط المقابلة | للأونلاين فقط — مرئي للأطراف المصرح لهم |
| الموقع | للحضوري — عنوان واضح |
| اسم الشركة | الشركة الداعية |
| اسم المتقدم | الموظف المدعو |
| ممثل الشركة | اسم مسؤول المقابلة إذا حُدِّد — وإلا: "ممثل الشركة" |
| أزرار القرار | موافق / طلب موعد آخر / رفض |
| محادثة الموعد | appointment thread — رسائل خاصة بهذا الموعد فقط |
| سجل الأحداث | timeline رسمي للأحداث |
| عداد تنازلي | الوقت المتبقي على الموعد أو على مهلة الرد |

---

#### حالات الموعد (Appointment States)

| الحالة | الوصف |
|--------|-------|
| `draft` | الشركة تجهز الدعوة — لم ترسلها بعد |
| `pending_response` | تم إرسال الدعوة — بانتظار رد الموظف |
| `reschedule_requested` | الموظف طلب موعداً آخر |
| `confirmed` | الطرفان وافقا على الموعد |
| `cancelled` | تم الإلغاء من أحد الطرفين |
| `expired` | انتهت مهلة الرد بدون رد من الموظف |
| `missed` | مر الموعد بدون إغلاق أو نتيجة واضحة |
| `completed` | تمت المقابلة |
| `closed` | تم إغلاق الغرفة — قراءة فقط |

---

#### مهلة الرد (Response Deadline)

الدعوة لا تبقى مفتوحة للأبد.

الشركة تختار مهلة رد عند الإرسال:

| الخيار | المدة |
|--------|-------|
| خيار 1 | 24 ساعة |
| خيار 2 | 48 ساعة |
| خيار 3 | 3 أيام |
| خيار 4 | 7 أيام |

**قواعد مهلة الرد:**

- لا يجوز أن تكون مهلة الرد بعد وقت المقابلة.
- إذا لم يرد الموظف خلال المهلة → الحالة تصبح `expired` تلقائياً.
- الدعوة المنتهية لا تُحذف — تظهر مطفية مع سجل واضح.
- الشركة تستطيع إرسال دعوة جديدة أو أرشفة الطلب بعد الانتهاء.
- Scheduler مطلوب للانتهاء التلقائي — **مؤجل** حتى بناء infrastructure مناسبة.

---

#### محادثة الموعد (Appointment Thread)

كل موعد له محادثة خاصة (appointment thread):

**القواعد:**

- المحادثة داخل غرفة الموعد فقط — للأمور المتعلقة بهذا الموعد.
- القرارات الرسمية لا تُؤخذ من الرسائل النصية.
- الموافقة أو طلب تغيير الموعد يجب أن تكون عبر **زر رسمي** فقط.
- لو كتب الموظف "تمام" في الشات — لا يعتبر موافقة رسمية. يجب الضغط على زر "موافق على الموعد".
- الشركة لا تستطيع اعتبار الموظف موافقاً بدون ضغط زر رسمي من حساب الموظف.

---

#### سجل الأحداث (Event Timeline)

الغرفة تحتوي timeline رسمي يتتبع الأحداث المهمة:

```
✦ تم إنشاء دعوة مقابلة.
✦ الشركة اقترحت موعداً: [التاريخ والوقت].
✦ الموظف طلب موعداً آخر.
✦ الشركة اقترحت موعداً جديداً: [التاريخ والوقت].
✦ الموظف وافق على الموعد.
✦ تم تأكيد الموعد.
✦ تم إغلاق غرفة الموعد.
```

كل حدث مهم يُسجَّل في audit log (مستقبلي — F18).

---

#### إشعارات Appointments (مستقبلية)

**إشعارات فورية (event-driven — قابلة للتنفيذ بدون scheduler):**

| الحدث | المستلم |
|-------|---------|
| وصلتك دعوة مقابلة جديدة | الموظف |
| الموظف وافق على الموعد | الشركة |
| الموظف طلب موعداً آخر | الشركة |
| الشركة اقترحت موعداً جديداً | الموظف |
| تم تأكيد الموعد | الطرفان |
| تم إلغاء الموعد | الطرف الثاني |
| تم إغلاق غرفة الموعد | الطرفان |

**تذكيرات (reminder-based — تحتاج scheduler — مؤجلة):**

- قبل الموعد بـ 24 ساعة.
- قبل الموعد بساعة.
- قبل انتهاء مهلة الرد.

---

#### الأمن والصلاحيات (Security Rules)

| القاعدة | التفاصيل |
|---------|---------|
| رؤية الموعد | لا أحد يرى موعداً ليس طرفاً فيه |
| صلاحية الشركة | الشركة ترى مواعيدها فقط |
| صلاحية الموظف | الموظف يرى مواعيده فقط |
| ممثل الشركة | يدخل فقط إذا كان لديه صلاحية من الشركة |
| الموافقة | الشركة لا تستطيع اعتبار الموظف موافقاً بدون زر من حساب الموظف |
| التعديل | الموظف لا يعدل الموعد مباشرة — يطلب موعداً آخر فقط |
| بعد confirmed | أي تعديل يحتاج موافقة الطرف الثاني |
| روابط المقابلات | لا تظهر إلا للأطراف المصرح لهم |
| بعد closed | الغرفة تصبح read-only |
| Audit log | كل حدث مهم يُسجَّل (F18) |

---

#### العلاقة مع Messenger العام

| المقارنة | Messenger العام | Appointment Room |
|---------|----------------|-----------------|
| الغرض | كلام عام بين المستخدمين | محادثة خاصة بموعد واحد |
| القرارات | لا تُؤخذ قرارات رسمية هنا | لا — فقط عبر أزرار رسمية |
| الوصول | أي مستخدم مع أي آخر | مقيّد بأطراف الموعد فقط |

- **Messenger العام يبقى للكلام العام.** لا يُستخدم لأمور الموعد.
- **Appointment Room يحتوي محادثة خاصة** بهذا الموعد فقط.
- **لا خلط** بين قرارات الموعد وشات الماسنجر العام.
- أي appointment-related conversation يجب أن يكون داخل appointment room.

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

*أُنشئ: 2026-07-09 — آخر تحديث: 2026-07-10 — أُضيف قسم "Future Product Notes" بعد اكتمال Notifications V2 (PR #453): 13 قسماً يغطي i18n / Global Countries / World Directory / Institution Naming / Smart Selection / Education Platform / Education Roles / Courses & Training Offers / Content Safety / Verification Gate / Monetization / Admin Support / Company Internal Groups / Next Phase Marker. حُدِّث: 2026-07-10 — PR #456: أُضيف §15 Appointments & Interview Rooms System (11 قسماً: فكرة عامة / زر المواعيد / بطاقات / غرفة الموعد / حالات / مهلة الرد / محادثة الموعد / سجل الأحداث / إشعارات / الأمن / العلاقة مع Messenger). تحديث Next Phase Marker إلى rating notification hook.*
