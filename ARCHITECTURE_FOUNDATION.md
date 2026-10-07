# ARCHITECTURE FOUNDATION — تواصلنا

> **الدستور المعماري لمشروع تواصلنا**
>
> هذا الملف أعلى أولوية من توثيق الميزات التفصيلية.
> إذا تعارض أي توثيق تفصيلي مع هذا الملف، يُعتمد هذا الملف.
>
> **This file has higher priority than feature-level documentation.**
> **If a feature document conflicts with ARCHITECTURE_FOUNDATION.md, the foundation file wins.**
>
> **طريقة القراءة الإلزامية (بروتوكول المهام — `CLAUDE.md` البند 1):** اقرأ "فهرس القواعد" أدناه أولاً، ثم `docs/SYSTEMS_INDEX.md` كفهرس، ثم فقط نص القواعد والأنظمة المرتبطة بالمهمة. لا حاجة لقراءة هذا الملف كاملاً في كل مهمة.

---

## فهرس القواعد (Rule Index)

> اقرأ هذا الجدول أولاً في كل مهمة، ثم افتح فقط القاعدة (أو القواعد) المرتبطة بالمهمة. السطر هنا ملخّص للتوجيه فقط — **النص الملزِم هو قسم القاعدة نفسه أدناه**.

| # | الأولوية | القاعدة (سطر واحد) |
|---|---------|-------------------|
| F1 | **P0** | منصة متعددة العملاء (Web / Mobile / Admin) — نفس Backend ونفس Database ونفس REST API؛ الفرق في الواجهة فقط. |
| F2 | **P0** | API-first — أي ميزة تحمل بيانات أو منطقاً تُبنى عبر API قابلة لإعادة الاستخدام، لا داخل HTML/JS فقط. |
| F3 | **P0** | Backend واحد (FastAPI في `server.py`) وقاعدة بيانات واحدة — ممنوع app أو DB أو Supabase project ثانٍ. |
| F4 | **P0** | Shared System First — افحص `static/shared/` و SYSTEMS_INDEX و CLAUDE.md قبل إنشاء أي helper/system جديد. |
| F5 | **P0** | لكل معلومة مهمة مصدر حقيقة واحد؛ localStorage cache فقط. |
| F6 | **P0** | الصلاحيات يفرضها Backend (JWT + ملكية + نوع حساب)؛ الواجهة تُخفي للـ UX فقط. |
| F7 | **P0** | `/u/{tw_id}` هو المسار العام الوحيد لكل أنواع الحسابات؛ الروابط القديمة redirects فقط. |
| F8 | **P1** | كل ميزة جاهزة للجوال: JSON نظيف، pagination، error shapes ثابتة، JWT فقط. |
| F9 | **P0** | No Silent Failures — ممنوع `except: pass`؛ كل خطأ مهم يُسجَّل ويُعاد بوضوح. |
| F10 | **P1** | لا حلول مؤقتة — السبب الجذري أولاً، ثم الإصلاح، ثم منع التكرار. |
| F11 | **P1** | أي PR يعدّل نظاماً مهماً يضيف أو يحدّث static checks/اختبارات بحدود مضبوطة. |
| F12 | **P1** | التوثيق يتبع المعمارية — يُحدَّث في نفس الـ PR، لا في وصف الـ PR فقط. |
| F13 | **P0** | Pre-push GitHub State Check قبل أي commit / push / PR؛ PR مدموج → branch جديد من main. |
| F14 | **P0** | Backward Compatibility — ممنوع كسر API أو route مستخدم بدون migration وموافقة. |
| F15 | **P1** | شكل رد API موحَّد: `{ok, data}` / `{ok:false, error}` مع HTTP status صحيح. |
| F16 | **P1** | أي تغيير DB عبر دالة `_migrate_*()` idempotent وموثَّقة. |
| F17 | **P0** | Security by Default — كل endpoint جديد يحدد security model (JWT/owner/type/rate limit/validation) قبل التنفيذ. |
| F18 | **P1** | العمليات المهمة تُنفَّذ بشكل قابل للمراجعة (audit log) — على الأقل log واضح الآن. |
| F19 | **P2** | الميزات التي قد تولّد إشعاراً تُبنى مع نقطة hook واضحة للإشعارات. |
| F20 | **P1** | مصفوفة الصلاحيات حسب نوع الحساب مركزية وتُحدَّث مع كل صلاحية جديدة. |
| F21 | **P0** | No Client-only Trust — إخفاء الزر ليس حماية؛ Backend يمنع التنفيذ فعلياً. |
| F22 | **P1** | العمليات القابلة للتكرار idempotent (`ON CONFLICT DO NOTHING` / get-or-create). |
| F23 | **P1** | Observability — logs واضحة + أخطاء واضحة + رد موحَّد في كل نظام مهم. |
| F24 | **P1** | كل ملف مرفوع له مالك ومسار يعكس الملكية وسياسة عرض/حذف واضحة. |
| F25 | **P2** | البيانات المهمة تُخزَّن قابلة للبحث (indexes)؛ ممنوع `ORDER BY RANDOM()` على Feed. |
| F26 | **P2** | النصوص الثابتة لا تُربط بالمنطق بطريقة تمنع الترجمة لاحقاً. |
| F27 | **P1** | Soft Delete للبيانات المهمة؛ Hard delete فقط بموافقة صريحة. |
| F28 | **P2** | كل ميزة عامة قابلة للإدارة لاحقاً من لوحة الأدمن (status fields + admin endpoints). |
| F29 | **P0** | مفهوم واحد = مصدر Canonical واحد في Backend و Frontend (نماذج + UI + Validation). |
| F30 | **P0** | لا يوجد نظام موثَّق يغطي الحاجة (أو تغطية جزئية) → STOP واشرح قبل البناء. |
| F31 | **P0** | قبل كتابة أي كود حدّد النظام الذي ينتمي له عبر جدول التوجيه الرسمي. |
| F32 | **P0** | DS-DATE هو النظام الوحيد لكل حقول التاريخ والوقت. |
| F33 | **P0** | DS-OVL هو النظام الوحيد لكل Overlays (Modal / Drawer / Sheet / Confirmation / Dialog). |
| F34 | **P0** | DS-FEEDBACK هو النظام الوحيد لـ Toast / Snackbar. |
| F35 | **P0** | DS-COLOR هو النظام الوحيد لكل color tokens؛ `--color-*` في `tw_shared.css` فقط. |
| F36 | **P0** | DS-SIZE هو النظام الوحيد لأحجام الخط/الزوايا/المسافات/الأيقونات/ارتفاعات العناصر؛ `--size-*` / `--radius-*` / `--space-*` في `tw_shared.css` فقط. |
| F37 | **P0** | DS-ICON هو النظام الوحيد لأيقونات الواجهة؛ registry واحد `static/shared/tw-icons.js` (Lucide 0.460 فقط)، أسماء حسب المعنى، قلب RTL تلقائي، ممنوع emoji كأيقونة. |
| F38 | **P0** | DS-IMAGE هو النظام الوحيد لعرض صور الأفاتار/اللوغو (`twAvatarHtml` / `twAvatarEl` + `.tw-ava`)؛ رابط الصورة يمر فقط على `twSafeImageUrl` (§54). |
| F39 | **P0** | DS-SHELL هو المصدر الوحيد لكتلة `<head>` والسكربتات المشتركة لكل صفحة — markers `<!--tw:shell-*-->` يبدّلها `read_html` من `partials/`؛ المشترك أولاً؛ `?v=` = hash المحتوى. |

---

## Priority Marker

| المستوى | التعريف |
|---------|---------|
| **P0** | غير قابل للكسر. لا استثناء إلا بوثيقة معمارية معتمدة. |
| **P1** | قابل للاستثناء بموافقة صريحة + تسجيل في ARCHITECTURE.md §C |
| **P2** | توجيه مفضّل. مقبول الانحراف إذا كان مبرراً. |

---

## F1 — [P0] Platform, Not Website

تواصلنا ليست موقعاً فقط. هي **منصة متعددة العملاء (multi-client platform):**

| Client | الحالة | الواجهة |
|--------|--------|---------|
| Web App | ✅ الحالي | HTML / CSS / Vanilla JS |
| Mobile App | 🔜 مستقبلي | Flutter أو React Native |
| Admin Dashboard | 🔜 مستقبلي | Web Admin Panel |

**القاعدة:** كل العملاء يستخدمون نفس Backend ونفس Database ونفس REST API.
لا يوجد Backend منفصل للتطبيق.
لا يوجد Database منفصل للتطبيق.
الفرق بين العملاء هو **الواجهة فقط** — وليس المنطق أو البيانات.

```
Web  ──┐
App  ──┼──→ server.py (FastAPI) ──→ PostgreSQL/Supabase
Admin──┘
```

---

## F2 — [P0] API-first Rule

أي ميزة تحمل بيانات أو منطق يجب أن تكون **API-first**.

ممنوع بناء ميزة مهمة داخل HTML/JS فقط بدون API قابلة لإعادة الاستخدام.

الأنظمة التالية يجب أن تكون جميعها عبر API واضحة يمكن استخدامها من الويب والتطبيق والإدارة:

```
login / register / logout
profiles (employee / company / edu)
jobs / applications
posts / comments / replies / mentions
messages / notifications
uploads / media
settings / preferences
follows / connections
verifications / KYC
search / matching
```

### صيغة توثيق كل endpoint جديد (إلزامي)

```
#### METHOD /path/endpoint

Auth: Bearer JWT (verify_token) | public
Permission: owner only | public | admin only

Request:
  { "field": type }

Response 200:
  { "ok": true, "data": { ... } }

Response 4xx/5xx:
  { "ok": false, "error": "رسالة واضحة" }
```

### ممنوعات F2

```
❌ ميزة مهمة للجوال تُنفَّذ فقط في frontend JS بدون endpoint
❌ منطق حساب أو تقييم أو ترتيب في frontend فقط
❌ HTML داخل JSON response
❌ بيانات مُضمَّنة hardcoded في page JS لا يستطيع الجوال الوصول إليها
```

---

## F3 — [P0] Single Backend / Single Database

```
❌ ممنوع: إنشاء FastAPI app ثانٍ للتطبيق
❌ ممنوع: إنشاء Database منفصلة للتطبيق
❌ ممنوع: تكرار البيانات بين الموقع والتطبيق
❌ ممنوع: إنشاء router file منفصل بدون قرار معماري موثَّق
❌ ممنوع: Supabase project ثانٍ
```

```
✅ صحيح: توسيع server.py بـ endpoints جديدة
✅ صحيح: إضافة جداول جديدة في نفس PostgreSQL
✅ صحيح: استخدام نفس JWT من الجوال والويب
```

**`server.py` هو الـ Backend الوحيد.** أي قرار بخلاف ذلك يحتاج وثيقة معمارية معتمدة تُضاف إلى `ARCHITECTURE.md §C`.

---

## F4 — [P0] Shared System First

قبل إنشاء أي helper أو system أو component جديد، يجب فحص ما يلي:

1. هل يوجد shared system موجود في `static/shared/`؟
2. هل يوجد مدخل في `docs/SYSTEMS_INDEX.md` يغطي الحاجة؟
3. هل يوجد قاعدة في `CLAUDE.md` تمنع التكرار؟

إذا كانت الإجابة **نعم** لأي منها → **استخدم الموجود**.

### أمثلة أنظمة مشتركة لا تُعاد:

| النظام | المصدر |
|--------|--------|
| رفع الملفات | `TW.uploadImage()` في `tw-upload.js` |
| قص الصور | `TW.createCropper()` في `tw-image-cropper.js` |
| بحث @mention | `GET /mention/search` (JWT) |
| بيانات الدول/المدن | `TW.COUNTRY_MAP` في `tw-options-data.js` |
| القوائم المنسدلة | `scSelectInit()` في `tw-select.js` |
| الأعلام | `TW.countryFlagEl()` + `flags/*.svg` |
| المهارات | `TW.searchSkills()` في `tw-skills.js` |
| نظام المتابعة | `profile_follows` + `company_follows` tables |
| المصادقة / JWT | `verify_token` في `server.py` |

### القاعدة الذهبية

> أي شيء ممكن يتكرر في صفحتين أو أكثر، لا تعمله كحل خاص لصفحة واحدة.
> اعمله أو اربطه بـ shared system.

---

## F5 — [P0] One Source of Truth

أي معلومة مهمة يجب أن يكون لها **مصدر حقيقة واحد فقط**.

| البيانات | المصدر الصحيح |
|----------|--------------|
| بيانات البروفايل | Database → API → `window._scProfile` |
| العلاقات (متابعة) | `profile_follows` / `company_follows` tables |
| الصور والوسائط | Storage bucket → API URL |
| الصلاحيات | Backend (server.py) → API response |
| المسارات العامة | `/u/{tw_id}` (Smart Router) |
| مستوى الإنجاز | `profiles.avail` فقط |
| حالة التطبيق | `companyState` / `window._scProfile` |

```
❌ ممنوع: نفس المعلومة بمصدرين مختلفين
❌ ممنوع: localStorage كمصدر حقيقة أساسي للبيانات (cache فقط)
❌ ممنوع: حساب نفس القيمة بمنطق مختلف في frontend و backend
```

---

## F6 — [P0] Backend Owns Permissions

الصلاحيات لا تعتمد على الواجهة وحدها.

**الواجهة تُخفي الأزرار لتحسين UX — لكن backend هو الذي يمنع التنفيذ.**

أي API حساس يجب أن يتحقق من:

```python
# 1. JWT صالح
token = Depends(verify_token)

# 2. ملكية المورد
if str(token.get("user_id")) != str(resource_owner_id):
    raise HTTPException(403, "Unauthorized")

# 3. نوع الحساب إذا لزم
if token.get("user_type") != "co":
    raise HTTPException(403, "Company account required")
```

```
❌ ممنوع: صلاحية تُطبَّق فقط في JS (hide/show) بدون فحص server-side
❌ ممنوع: الاعتماد على user_id من request body بدلاً من JWT
❌ ممنوع: X-User-Id header — Bearer JWT فقط
```

---

## F7 — [P0] Public Routes Contract

المسار الرسمي للبروفايلات العامة لجميع أنواع الحسابات هو:

```
/u/{tw_id}
```

يشمل: موظف (U...) + شركة (C...) + جهة تعليمية (T...)

```
❌ ممنوع: /profile?id=123         (legacy — redirect only)
❌ ممنوع: /company-profile?id=123  (legacy — redirect only)
❌ ممنوع: /edu-profile?id=123      (legacy — redirect only)
❌ ممنوع: روابط تحتوي على numeric id في الـ URL العام
❌ ممنوع: بناء رابط عام من اسم المستخدم فقط
```

الروابط القديمة مقبولة **كـ redirects فقط** — وليس كروابط نهائية في share buttons أو copy-link flows.

---

## F8 — [P1] Mobile-ready Architecture

أي ميزة جديدة تُبنى بطريقة يمكن استخدامها لاحقاً في Flutter أو React Native.

**الفرق بين الويب والتطبيق يجب أن يكون UI فقط** — وليس منطق أو data مختلفة.

### Checklist لكل ميزة

- [ ] هل الـ endpoint يعيد JSON نظيف بدون HTML؟
- [ ] هل Pagination موجود (cursor أو page-based) إذا القائمة قابلة للنمو؟
- [ ] هل error shapes ثابتة: `{"ok": false, "error": "..."}`؟
- [ ] هل Auth عبر JWT فقط (لا cookie، لا session)؟
- [ ] هل الـ state لا يعتمد على `localStorage` للعمل؟

---

## F9 — [P0] No Silent Failures

```python
# ❌ ممنوع تماماً:
except Exception:
    pass

except Exception as e:
    pass  # silent — dangerous
```

أي خطأ مهم يجب:

```python
# ✅ صحيح:
except Exception as exc:
    print(f"[endpoint_name] ERROR context={...}: {exc}")
    return {"ok": False, "error": "رسالة واضحة"}
```

### القاعدة

- **Operations DB:** أي INSERT/UPDATE/DELETE يجب أن يُغلَّف في try/except مع logging واضح
- **Transactions:** إذا تعذَّر COMMIT → ROLLBACK فوري + raise الخطأ → لا صمت
- **Endpoints:** خطأ غير متوقع → HTTP 500 + `{"ok": false, "error": "..."}` — لا 200 مع data ناقصة
- **Frontend:** fetch فاشل → toast واضح للمستخدم — لا صمت

---

## F10 — [P1] No Patch-first Development

ممنوع الحلول المؤقتة إذا كان يوجد سبب معماري واضح.

**الأولوية دائماً:**

```
1. فهم الجذر (root cause)
2. إصلاح السبب الحقيقي
3. منع تكرار المشكلة بـ test أو قاعدة
```

```
❌ ممنوع: حذف test حتى يمر الـ CI بدلاً من إصلاح الكود
❌ ممنوع: --no-verify أو تجاوز hooks
❌ ممنوع: workaround مؤقت مع "TODO: fix later" في production code
❌ ممنوع: force push على main لحل merge conflict
```

---

## F11 — [P1] Tests / Static Checks Required

أي PR يعدّل نظام مهم يجب أن يُضيف أو يُحدّث static checks في `test_post_comments.py`.

### ما يجب اختباره

- السلوك الجديد (يثبت أن الميزة شُغِّلت)
- عدم كسر الأنظمة المجاورة
- عدم كسر shared systems
- الممنوعات — تأكد أنها غائبة

### حدود الاختبار

| نوع التعديل | الاختبار المطلوب |
|------------|----------------|
| تعديل CSS بسيط | فحص بصري مختصر أو اختبار واحد |
| تعديل JS بسيط | اختبار واحد مركّز على السلوك |
| تعديل save/API | اختبارات النجاح والفشل فقط |
| تعديل docs فقط | اختبار static وجود الملف والمحتوى |
| تعديل backend أو DB | توقف + شرح قبل توسيع الفحص |

---

## F12 — [P1] Documentation Must Follow Architecture

إذا تم تثبيت قاعدة معمارية أو تعديل نظام مشترك، يجب تحديث التوثيق المناسب في نفس الـ PR:

| التغيير | التوثيق المطلوب |
|---------|----------------|
| قاعدة عليا جديدة | `ARCHITECTURE_FOUNDATION.md` + `CLAUDE.md` |
| نظام جديد (DB + endpoint + frontend) | `ARCHITECTURE.md` + `docs/SYSTEMS_INDEX.md` |
| قاعدة دائمة للـ AI sessions | `CLAUDE.md` |
| تغيير في API contract | `ARCHITECTURE.md` في قسم النظام المعني |
| تغيير صغير لا أثر معماري | اكتب في PR: `Docs: not needed — [سبب]` |

```
❌ ممنوع: إغلاق PR مع قواعد موثَّقة في description فقط
❌ ممنوع: "سيتم التوثيق في PR لاحق" للعمل ضمن نفس الجلسة
❌ ممنوع: قاعدة AI بدون إضافة في CLAUDE.md
```

---

## F13 — [P0] Pre-push GitHub State Check

قبل أي commit / push / PR أو إضافة على PR موجود، يجب الإجابة على:

```
Pre-push GitHub State Check:
- PR number:        [رقم الـ PR إن وجد]
- PR state:         open | closed
- merged:           true | false
- current branch:   [اسم الـ branch الحالي]
- base branch:      main | other
- هل PR مفتوح أم مدموج؟
- القرار:           push على branch حالي / branch جديد / PR جديد
```

### قواعد القرار

| الحالة | القرار |
|--------|--------|
| PR مدموج (`merged: true`) | branch جديد من main + PR جديد |
| PR مفتوح (`state: open`) | يمكن إضافة commits على نفس الـ branch |
| لا يوجد PR | branch جديد + PR جديد |

```
❌ خطأ شائع: إضافة commits على branch قديم بعد دمج PR المرتبط به
✅ صحيح: fetch origin/main → branch جديد → PR جديد
```

---

## F14 — [P0] Backward Compatibility Rule

أي API أو route مستخدم ممنوع ينكسر فجأة بدون إشعار أو migration واضح.

### متى يُعتبر التغيير breaking change؟

```
❌ تغيير اسم field في response (مثال: "name" → "full_name")
❌ حذف field من response كان موجوداً
❌ تغيير نوع البيانات (مثال: string → int)
❌ تغيير HTTP method للـ endpoint
❌ تغيير URL path بدون redirect
❌ تغيير سلوك endpoint بطريقة تكسر الـ client الحالي
```

### متى يُسمح بالتغيير؟

```
✅ إضافة field جديد في response (additive — safe)
✅ إضافة endpoint جديد
✅ تغيير مع versioning واضح (/v2/...)
✅ تغيير مع redirect من المسار القديم
✅ تغيير موثَّق في ARCHITECTURE.md مع migration plan
```

### قاعدة التطبيق

أي breaking change يحتاج:
1. توثيق في ARCHITECTURE.md
2. migration path واضح للـ clients الحالية
3. موافقة صريحة قبل التنفيذ

---

## F15 — [P1] Standard API Response Rule

ردود الـ API يجب أن تكون موحدة قدر الإمكان.

### الشكل القياسي

```json
// نجاح:
{ "ok": true, "data": { ... } }

// نجاح مع قائمة:
{ "ok": true, "data": [...], "total": 42, "page": 1 }

// فشل (عقد PR 3A / #572 — api_error(status, code, message, field=None) في server.py):
{ "ok": false, "error": { "code": "invalid_url", "message": "رسالة عربية واضحة", "field": "url" } }
//   code = معرّف ثابت للمطوّر · message = نص للمستخدم · field = اختياري (خطأ حقل)
```

### قواعد التطبيق

```
✅ كل endpoint يُرجع "ok": true أو "ok": false
✅ البيانات دائماً تحت "data" أو "result"
✅ الأخطاء دائماً تحت "error" ككائن {code, message, field?} — الواجهة تقرأ النص عبر twApiMessage(res, fallback)
✅ HTTP status codes صحيحة (200/201/400/401/403/404/422/500)
❌ ممنوع: endpoint يُرجع list مباشرة بدون wrapper
❌ ممنوع: كل endpoint بشكل مختلف تماماً بدون سبب
❌ ممنوع: HTML في JSON response
❌ ممنوع: HTTP 200 مع محتوى يعني فشل
```

### استثناءات مقبولة

- Endpoints قديمة (legacy) قبل تثبيت هذه القاعدة — تُحافَظ كما هي حتى migration
- File upload response قد يختلف شكله — موثَّق في `ARCHITECTURE.md §Upload`

---

## F16 — [P1] Database Migration Rule

أي تعديل على قاعدة البيانات يجب أن يكون migration واضح وموثَّق.

### المطلوب لكل تغيير DB

```python
# كل migration في دالة _migrate_*() مستقلة — الفشل يُرفع (raise)، ما يُبلع جوّا الدالة
def _migrate_new_feature():
    with db_conn() as conn:
        conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS new_field TEXT")
        conn.run("CREATE TABLE IF NOT EXISTS new_table (...)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_new ON new_table(field)")

# وتنضاف لسجل _startup_migrations() في server.py مع تصنيفها (PR 2B):
#   ("new_feature", _migrate_new_feature, True)   # True = حرجة · False = اختيارية
```

### قواعد إلزامية

```
✅ كل migration في دالة مستقلة باسم واضح: _migrate_feature_name()
✅ استخدام IF NOT EXISTS / IF EXISTS دائماً (idempotent)
✅ توثيق الـ schema الجديد في ARCHITECTURE.md
✅ الـ migration يعمل عند restart بدون تدخل يدوي
❌ ممنوع: ALTER TABLE يدوي مباشر في Supabase بدون توثيق
❌ ممنوع: تعديل DB بدون migration function مقابلة في server.py
❌ ممنوع: حذف column بدون التحقق من عدم استخدامه في الكود
❌ ممنوع: migration يفشل إذا شُغِّل مرتين
❌ ممنوع: except: pass / بلع الخطأ جوّا دالة الـ migration — السياسة بـ _run_startup_migrations (CLAUDE.md → Startup Migration Policy)
```

---

## F17 — [P0] Security by Default

أي endpoint جديد يجب أن يُحدَّد security model الخاص به قبل التنفيذ.

### Checklist إلزامي لكل endpoint جديد

```
[ ] هل يحتاج JWT؟ → Depends(verify_token)
[ ] من مسموح يستخدمه؟ → guest / emp / co / edu / admin
[ ] هل يحتاج owner check؟ → if token["user_id"] != resource_owner
[ ] هل يحتاج account_type check؟ → if token["user_type"] != "co"
[ ] هل يحتاج rate limiting؟ → حسب حساسية العملية
[ ] هل يحتاج input validation؟ → Pydantic model أو manual checks
```

### الإعدادات الافتراضية

```python
# الافتراضي: كل endpoint جديد يحتاج JWT إلا إذا كان public صريحاً
@app.get("/endpoint")
def my_endpoint(token = Depends(verify_token)):
    user_id = int(token["user_id"])
    ...

# Public endpoint: يجب توثيق السبب الصريح
@app.get("/public/endpoint")  # no auth — public catalog
def public_endpoint():
    ...
```

### ممنوعات F17

```
❌ endpoint جديد بدون تحديد security model
❌ endpoint "مؤقت" يتجاوز الـ auth
❌ قراءة user_id من request body بدلاً من JWT
❌ X-User-Id header في أي endpoint جديد
❌ endpoint حساس بدون owner check
```

---

## F18 — [P1] Important Actions Audit-ready Rule

العمليات المهمة يجب أن تُنفَّذ بطريقة تسمح بمراجعتها لاحقاً.

### ما يُعتبر "عملية مهمة"

```
- حذف أي محتوى (منشور / تعليق / بروفايل / وظيفة)
- تعديل بيانات حساسة (كلمة مرور / إيميل / نوع حساب)
- قبول أو رفض توثيق (credential verification)
- تغيير صلاحيات حساب (admin actions)
- إرسال رسالة مباشرة
- التقديم على وظيفة
- إنشاء أو إغلاق محادثة
```

### المطلوب حالياً (minimum)

```python
# على الأقل: log واضح قبل تنفيذ العملية
print(f"[audit] user={user_id} action=delete_post post_id={post_id}")
```

### المطلوب مستقبلاً (audit log table)

```sql
-- جدول مستقبلي — لا يُنشأ الآن
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    actor_id INT,       -- من فعل العملية
    action TEXT,        -- نوع العملية
    target_type TEXT,   -- post / comment / user / job
    target_id INT,
    metadata JSONB,     -- أي تفاصيل إضافية
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### قاعدة التطبيق

ابنِ العمليات الحساسة الآن بطريقة يسهل إضافة audit logging لاحقاً: عزل منطق الحذف/التعديل في دالة مستقلة، ولا تضمّ منطق الـ audit داخل nested code يصعب فصله.

---

## F19 — [P2] Notification-ready Rule

أي ميزة يمكن أن تولّد إشعاراً يجب أن تُبنى بطريقة تسمح بإضافة notifications لاحقاً.

### الأنظمة التي تستدعي إشعارات مستقبلاً

```
comment     → يُشعر صاحب المنشور
reply       → يُشعر صاحب التعليق الأصلي
mention     → يُشعر الشخص المذكور
message     → يُشعر المستلم (موجود)
job apply   → يُشعر الشركة
verification → يُشعر المستخدم عند القبول/الرفض
follow      → يُشعر الشخص المتابَع
```

### قاعدة التطبيق

```python
# حالياً: بعد حفظ التعليق
# مستقبلاً: استدعاء دالة create_notification()
# المطلوب الآن: اترك مساحة واضحة للـ hook

async def create_comment(...):
    comment_id = save_comment_to_db(...)
    # TODO(notifications): notify post owner
    return comment_id
```

الـ TODO ليس ذريعة للتأجيل، بل placeholder واضح يُسهّل العثور على النقطة الصحيحة عند تنفيذ Notifications Phase 3.

---

## F20 — [P1] Role and Permission Matrix Rule

الصلاحيات يجب أن تكون واضحة ومركَّزة حسب نوع الحساب.

### Matrix الصلاحيات الأساسية

| Action | guest | emp | co | edu | admin |
|--------|-------|-----|----|-----|-------|
| عرض بروفايل عام | ✅ | ✅ | ✅ | ✅ | ✅ |
| تعديل بروفايلي | ❌ | ✅ owner | ✅ owner | ✅ owner | ✅ |
| نشر وظيفة | ❌ | ❌ | ✅ | ❌ | ✅ |
| التقديم على وظيفة | ❌ | ✅ | ❌ | ❌ | ✅ |
| نشر منشور | ❌ | ❌ | ✅ | ✅ | ✅ |
| نشر تعليق | ❌ | ✅ | ✅ | ✅ | ✅ |
| طلب توثيق | ❌ | ✅ | ❌ | ❌ | ✅ |
| قبول/رفض توثيق | ❌ | ❌ | ❌ | ❌ | ✅ |
| حذف أي حساب | ❌ | ❌ | ❌ | ❌ | ✅ |

### قواعد التطبيق

```
✅ الـ matrix يُحدَّث عند إضافة ميزة جديدة تمس الصلاحيات
✅ الفحص يكون server-side في كل endpoint حساس
✅ الواجهة تُخفي العناصر للـ UX فقط — وليس للحماية
❌ ممنوع: صلاحية جديدة تُضاف بدون تحديث الـ matrix هنا
❌ ممنوع: الصلاحيات مبعثرة في JS فقط بدون مقابل في server.py
```

---

## F21 — [P0] No Client-only Trust

هذه القاعدة تُعزِّز F6 (Backend Owns Permissions) بتفصيل إضافي.

**الواجهة يمكن أن تُخفي الأزرار لتحسين UX — لكن backend يجب أن يمنع التنفيذ فعلياً.**

### نماذج الخطأ الشائع

```javascript
// ❌ خطأ: حماية في JS فقط
if (user.id === post.owner_id) {
    showDeleteButton();
}
// الخطر: أي شخص يستطيع إرسال DELETE request مباشرة
```

```python
# ✅ صحيح: الحماية في backend
@app.delete("/posts/{post_id}")
def delete_post(post_id: int, token = Depends(verify_token)):
    post = get_post(post_id)
    if post["owner_id"] != int(token["user_id"]):
        raise HTTPException(403, "Not your post")
    ...
```

### ممنوعات F21

```
❌ ممنوع: إخفاء زر في JS واعتبار ذلك حماية كافية
❌ ممنوع: قراءة user_id من payload بدون تحقق من JWT
❌ ممنوع: افتراض أن الـ client لن يرسل request غير مصرح
❌ ممنوع: "المستخدم العادي لن يعرف الـ endpoint"
```

---

## F22 — [P1] Idempotency Rule

العمليات التي قد تتكرر بالضغط مرتين يجب أن تكون آمنة من التكرار.

### الأنظمة التي تتطلب Idempotency

```
follow / unfollow          → INSERT ... ON CONFLICT DO NOTHING
like / appreciate          → INSERT ... ON CONFLICT DO NOTHING
save post / unsave         → INSERT ... ON CONFLICT DO NOTHING
apply to job               → INSERT ... ON CONFLICT DO NOTHING + UNIQUE(job_id, user_id)
send verification request  → فحص if exists before INSERT
create conversation        → فحص if exists or get-or-create pattern
```

### التطبيق

```python
# ✅ صحيح — idempotent follow
conn.run(
    "INSERT INTO profile_follows (follower_id, followed_id) "
    "VALUES (:a, :b) ON CONFLICT DO NOTHING",
    a=follower_id, b=followed_id
)

# ❌ خطأ — قد يُلقي unique constraint error عند تكرار الضغط
conn.run(
    "INSERT INTO profile_follows (follower_id, followed_id) VALUES (:a, :b)",
    a=follower_id, b=followed_id
)
```

### قاعدة التطبيق

أي endpoint يُمثِّل "عملية يمكن تكرارها" يجب أن يُنفَّذ بـ idempotent SQL ولا يُلقي خطأ عند الاستدعاء المتكرر بنفس المعاملات.

---

## F23 — [P1] Observability Rule

الأنظمة المهمة يجب أن تكون قابلة للفحص والمراقبة.

### المطلوب في كل نظام مهم

```python
# ✅ صحيح: logging واضح في كل operation مهمة
print(f"[system_name] action=create user={user_id} item={item_id}")
print(f"[system_name] ERROR user={user_id}: {exc}")

# ✅ response واضح دائماً
return {"ok": True, "data": result}
return {"ok": False, "error": "رسالة واضحة"}
```

### الأربعة المطلوبة

| المستوى | المطلوب |
|---------|---------|
| **Logs** | print واضح عند كل error + عند كل operation مهمة |
| **Errors** | رسالة error واضحة للمطوّر في logs + للمستخدم في response |
| **Response** | شكل موحَّد (`ok`, `data`, `error`) — راجع F15 |
| **No silent fail** | ممنوع تماماً — راجع F9 |

### ممنوعات F23

```
❌ ممنوع: operation مهمة بدون أي log
❌ ممنوع: error يُبتلع بـ except: pass
❌ ممنوع: HTTP 200 مع محتوى يعني فشل
❌ ممنوع: endpoint لا يُعيد أي response عند الفشل
```

---

## F24 — [P1] Storage Ownership Rule

أي ملف مرفوع يجب أن يكون له مالك وارتباط واضح.

### معلومات المطلوبة لكل ملف مرفوع

```
who uploaded it?   → user_id من JWT عند الرفع
which entity?      → bucket + path يعكسان الملكية (avatars/{user_id}/...)
who can view?      → public vs. private (bucket policy في Supabase)
who can delete?    → owner فقط أو admin — لا أحد آخر
who can replace?   → نفس سياسة الحذف
```

### قاعدة المسارات في Supabase Storage

```
avatars/{user_id}/avatar     → صورة بروفايل الموظف
avatars/{user_id}/cover      → صورة غلاف الموظف
avatars/{company_id}/logo    → شعار الشركة
avatars/{company_id}/cover   → غلاف الشركة
```

### ممنوعات F24

```
❌ ممنوع: رفع ملف بدون ربطه بـ user_id في DB
❌ ممنوع: مسار عشوائي لا يعكس الملكية
❌ ممنوع: السماح لأي مستخدم بحذف ملف مستخدم آخر
❌ ممنوع: public bucket لملفات خاصة
```

---

## F25 — [P2] Search-ready Data Rule

أي بيانات مهمة يجب أن تُخزَّن بطريقة قابلة للبحث لاحقاً.

### البيانات القابلة للبحث

```
الأسماء       → full_name في users — indexed
الشركات       → profiles (co) — indexed on user_id
الوظائف       → jobs.title, jobs.description — ILIKE or FTS
المهارات      → skill_catalog + user_skills — indexed
المدن          → profiles.city — indexed
الجامعات      → education.institution — text
الشهادات      → courses.title + certificate_url
```

### قواعد التطبيق

```
✅ أي column يُستخدم في WHERE أو ORDER يجب أن يكون indexed
✅ النصوص العربية — ILIKE مقبول الآن، FTS (pg_trgm) مستقبلاً
✅ لا تخزّن بيانات ستُبحث فيها كـ JSON blob مضمَّن
❌ ممنوع: ORDER BY RANDOM() في أي query على Feed
❌ ممنوع: table scan بدون index على columns مستخدمة في WHERE
```

---

## F26 — [P2] Multi-language Ready Rule

لا تربط النصوص الثابتة بالمنطق الأساسي بطريقة تمنع الترجمة لاحقاً.

**المنصة عربية الآن، لكن يجب أن تبقى قابلة للتوسع.**

### ممنوعات F26

```python
# ❌ ممنوع: نص مُضمَّن في منطق الـ API
return {"error": "لم يتم العثور على المستخدم"}  # قد تحتاج ترجمة مستقبلاً

# ✅ أفضل: error code + message منفصل أو قابل للـ map
return {"ok": False, "error_code": "USER_NOT_FOUND", "message": "لم يتم العثور على المستخدم"}
```

### قواعد التطبيق الحالي

- النصوص العربية في API responses مقبولة الآن
- لا تضمّ نصوص ترجمة داخل conditionals أو loops بطريقة تجعل فصلها صعباً لاحقاً
- الـ error codes الإنجليزية (USER_NOT_FOUND, FORBIDDEN, ...) أفضل من نصوص عربية hard-coded في code paths حساسة

---

## F27 — [P1] Soft Delete Rule

البيانات المهمة لا تُحذف نهائياً مباشرة إلا بسبب واضح وموافقة صريحة.

### البيانات التي تستحق Soft Delete

```
المنشورات (posts)          → status = 'deleted', deleted_at = NOW()
التعليقات (comments)       → status = 'deleted', deleted_at = NOW()  ✅ مُطبَّق
الوظائف (jobs)             → status = 'closed' أو 'deleted'
طلبات التوثيق             → soft delete أو أرشفة
المحادثات (conversations)  → soft delete أو archive
```

### Schema الموصى به

```sql
-- إضافة هذه الأعمدة لأي جدول يحتاج soft delete
status      TEXT DEFAULT 'active',   -- 'active' | 'deleted' | 'archived'
deleted_at  TIMESTAMPTZ,
deleted_by  INT REFERENCES users(id) -- من حذفه (user أو admin)
```

### قواعد التطبيق

```
✅ SELECT يُفلتر: WHERE status = 'active'
✅ DELETE → UPDATE SET status='deleted', deleted_at=NOW()
✅ Admin يستطيع رؤية المحذوف
✅ Hard delete فقط بموافقة صريحة + legal requirement واضح
❌ ممنوع: DELETE FROM posts WHERE id=... بدون soft delete
❌ ممنوع: حذف بيانات قد تحتاجها في audit أو نزاع قانوني
```

**ملاحظة:** التعليقات (`company_post_comments`) تستخدم soft delete بالفعل (`status='deleted'`). هذا النمط هو المعيار للأنظمة الجديدة.

---

## F28 — [P2] Admin-ready Rule

أي ميزة عامة يجب أن تُبنى بطريقة تسمح بإدارتها لاحقاً من لوحة التحكم.

### الأنظمة التي تحتاج admin interface مستقبلاً

```
البلاغات (reports)          → عرض + قبول + رفض + إجراء
الحسابات المسيئة            → تعليق + حظر + حذف
الشركات الوهمية             → مراجعة + سحب تحقق
الشهادات المزورة            → رفض + تنبيه
المنشورات المخالفة          → إخفاء + حذف + إشعار صاحبها
طلبات التوثيق               → موجود ✅ في admin.html
```

### قاعدة البناء

```python
# ✅ صحيح: كل عملية حساسة لها endpoint admin مستقل
@app.put("/admin/posts/{post_id}/hide")
def admin_hide_post(post_id: int, token = Depends(verify_admin)):
    ...

# المطلوب: status field في الجداول المهمة يسمح بـ admin actions
# posts.status: 'active' | 'hidden' | 'deleted'
# users.status: 'active' | 'suspended' | 'banned'
```

### ممنوعات F28

```
❌ ممنوع: نظام يُحذف فيه المحتوى بدون أي admin trail
❌ ممنوع: بناء نظام لا يمكن مراجعته من admin dashboard
❌ ممنوع: admin actions بدون JWT + verify_admin check
```

---

## F29 — [P0] One Concept = One Source of Truth (Form & UI)

امتداد من F5، مُخصَّص لطبقة الـ UI والنماذج:

**القاعدة:** مفهوم واحد = مصدر بيانات Canonical واحد — في الـ Backend وفي الـ Frontend.

```
profiles.avail     → المصدر الوحيد لحالة التوفر
profiles.country   → المصدر الوحيد للدولة (ISO code للموظف)
```

### التطبيق على النماذج

- **مصدر Canonical واحد للقراءة والكتابة** — كل نقاط الـ UI التي تعرض أو تُعدِّل نفس البيانات تقرأ من وتكتب إلى نفس المصدر
- **سطوح UI متعددة مقبولة** — يمكن أن يكون للبيانات سطح عرض في header + modal + card، شريطة أن كلها تُحدَّث من نفس الـ canonical response بعد الحفظ
- **حقل يُكتَب من مكانَين مقبول** إذا توفَّرت الشروط الأربعة: (١) نفس المصدر الـ Canonical (نفس DB column/table)، (٢) نفس الـ contract المعتمد (ليس بالضرورة نفس الـ endpoint — يمكن endpointَين إذا كلاهما يكتب للمصدر ذاته بدون تضارب)، (٣) تزامن صريح (كل نقاط العرض تُحدَّث من الـ canonical response)، (٤) لا parallel state (مثال: modal + inline edit يكتبان لـ `profiles.headline`)
- **مصدر Display واحد** — بعد الحفظ، كل نقاط العرض تُحدَّث من نفس الـ canonical response

### تطبيقه على Validation

- **Shared Core إلزامي** — القواعد والرسائل والـ schema تُعرَّف مرةً واحدة
- `validateAdd()` و `validateEdit()` كـ wrapper functions **مقبولتان** — الانتهاك هو تكرار القواعد نفسها في منطقَين مستقلَّين

### ممنوعات F29

```
❌ availability_status و avail يحكمان نفس البيانات في نفس الوقت
❌ قواعد Validation مكتوبةً مرتَين في ملفَّين مختلفَين (مكرَّرة لا مشتركة)
❌ حقل يُكتَب من مكانَين بدون تزامن صريح أو بدون نفس مصدر Canonical
❌ جدول ثانٍ لنفس البيانات بحجة "تسريع القراءة" بدون invalidation strategy
```
## F30 — [P0] No Matching System = Stop and Report

**القاعدة:** إذا لم يوجد نظام موثَّق لما تُنشئه — **STOP** واسأل قبل البناء.

### خطوات الفحص الإلزامية

```
1. اقرأ docs/SYSTEMS_INDEX.md (33+ نظاماً)
2. هل يوجد نظام يُغطي هذه الحاجة؟
   → نعم: استخدمه (F4)
   → جزئياً: STOP — وضِّح أي جزء يحتاج توسيع، ونفِّذ فقط إذا كانت المهمة الحالية مُفوَّضة صراحةً بتعديل ذلك النظام
   → لا: STOP — أبلِغ المستخدم واشرح ما ينقص قبل البناء
```

### إذا غطّى النظام الحاجة جزئياً

لا تبتكر حلاً موازياً لـ "الجزء المفقود". توقّف وأبلِغ:
- ما الجزء الموجود الذي يُغطي الحاجة
- ما الجزء المفقود وما الذي يحتاج توسيعاً
- هل توسيع النظام داخل نطاق المهمة الحالية؟

### لماذا هذه القاعدة؟

- منع بناء أنظمة موازية تُنشئ تضارباً (F5)
- منع استهلاك رصيد في بناء شيء موجود
- منع ديون تقنية صعبة التنظيف

### ممنوعات F30

```
❌ بناء نظام dropdown بديل عندما tw-select.js موجود
❌ إنشاء جدول DB عندما جدول بنفس الغرض موجود
❌ كتابة validation logic بدون مراجعة DS-VAL
❌ كتابة form lifecycle بدون مراجعة DS-FRM
❌ بناء نظام "مشابه لكن أبسط" — أبسط = ديون مستقبلية
❌ توسيع نظام موجود بدون موافقة صريحة على التوسيع في نفس المهمة
```
## F31 — [P0] System Routing Before Implementation

**القاعدة:** قبل كتابة أي سطر كود، حدِّد **إلى أي نظام ينتمي** هذا السطر.

### جدول التوجيه الرسمي

| إذا كنت تكتب... | تنتمي إلى |
|----------------|-----------|
| شكل حقل إدخال، border، states | DS-INP |
| دورة حياة الفورم، Reset، Hydration، Dirty | DS-FRM |
| توقيت الخطأ، رسالة الخطأ | DS-VAL |
| شكل Payload للـ API | DS-FRM (FRM-09) + API-MUT |
| زر Save، Loading state | DS-BTN |
| منطق navigation، history | DS-NAV |
| صلاحية من يرى العنصر | DS-VM |
| قاموس مهارات أو مهن | DS-REF → **STOP** (tw-skills.js / tw-options-data.js موجود كـ Runtime — DS-REF غير موثَّق رسمياً بعد؛ راجع F30) |
| dropdown أو select / picker / searchable picker / multi-select | DS-SEL → `docs/design-system/SELECT-PICKER.md` — اقرأ SEL-00 (Routing) ثم القسم المناسب |
| تاريخ / وقت / date picker / month-year / year-only / datetime | DS-DATE → `docs/design-system/DATE-TIME-FIELDS.md` — اقرأ DATE-00 (Routing Protocol) ثم DATE-03A–G |
| Overlay / Modal / Drawer / Confirmation / Sheet / Dialog | DS-OVL → `docs/design-system/OVERLAY-SYSTEM.md` — اقرأ OVL-00 (Routing Protocol) ثم القسم المناسب |
| Toast / Snackbar / Operational Feedback | DS-FEEDBACK → `docs/design-system/FEEDBACK-SYSTEM.md` — اقرأ FBK-00 (Routing Protocol) ثم القسم المناسب |
| color token / `--color-*` / palette / لون / تعريف لون جديد | DS-COLOR → `docs/design-system/COLOR-SYSTEM.md` — اقرأ CLR-00 (Routing Protocol) ثم القسم المناسب |
| font-size / border-radius / padding / margin / gap / حجم أيقونة / ارتفاع زر / `--size-*` / `--radius-*` / `--space-*` | DS-SIZE → `docs/design-system/SIZE-SYSTEM.md` — اقرأ SIZE-00 (Routing Protocol) ثم القسم المناسب |
| أيقونة واجهة / SVG icon / `data-lucide` / سهم رجوع أو تقدّم / emoji كأيقونة / أيقونة مهارة أو مهنة | DS-ICON → `docs/design-system/ICON-SYSTEM.md` — اقرأ ICON-00 (Routing Protocol) ثم القسم المناسب |
| صورة أفاتار / لوغو جهة / حرف بديل / `<img>` لصورة حساب / `background-image` لغلاف / رابط صورة من الـ API | DS-IMAGE → `docs/design-system/IMAGE-SYSTEM.md` — اقرأ IMG-00 (Routing Protocol) ثم القسم المناسب |
| صفحة HTML جديدة / `<head>` مشترك / meta · viewport · manifest · favicon · خط Cairo / تحميل `tw_shared.*` أو `auth-sync.js` / `?v=` لملف مشترك | DS-SHELL → `docs/design-system/PAGE-SHELL.md` — اقرأ SHELL-00 (Routing Protocol) ثم القسم المناسب |
| Tooltip / Popover / Floating label / Context menu | **STOP** — غير موثَّق بعد؛ خارج DS-OVL V1 — راجع `docs/design-system/OVERLAY-SYSTEM.md` OVL-37 |

### لماذا هذه القاعدة؟

تمنع "الكود اليتيم" — منطق لا ينتمي لأي نظام وصعب اكتشافه لاحقاً.
تُجبر على اتخاذ قرار معماري قبل التنفيذ.

### ممنوعات F31

```
❌ validation logic داخل click handler مباشرةً (بدون DS-VAL)
❌ border color مُغيَّر في JS بدون .has-error class (DS-INP يملك هذا)
❌ form.reset() مباشرةً بدون الـ Reset Contract (DS-FRM FRM-05)
❌ payload.field = value بدون Tri-state check (DS-FRM FRM-09)
❌ إعادة تعريف قواعد نظام داخل نظام آخر (مثلاً: Validation Timing في DS-FRM بدلاً من DS-VAL)
❌ خلط مسؤوليات الأنظمة (DS-INP يُقرِّر متى يظهر الخطأ بدلاً من DS-VAL)
```

### مسموح — Orchestration Functions

وظائف الـ submit handler تنسِّق بين أنظمة متعددة — هذا مقبول وإلزامي:

```js
// ✅ مقبول: submit handler يُنسِّق DS-VAL + DS-FRM + DS-BTN
async function handleSave() {
  if (!validateForm()) return          // DS-VAL
  buildPayload()                       // DS-FRM
  enterSaveLoadingState()              // DS-BTN — pseudo-call توضيحي
                                       // (DS-BTN يملك "كيف"، DS-FRM/Orchestration يقرِّر "متى")
  const res = await sendRequest()      // API-MUT
  applyCanonicalResponse(res)          // DS-FRM
}
```

الوظيفة تستدعي الأنظمة — لا تُعيد تعريف قواعدها.

### See also: CRS — Change Routing System

إذا كان السؤال "هذا الطلب — ما نطاقه؟ من يملكه؟ كيف أُحدِّد أقل قراءة لازمة؟"
→ انظر `docs/CHANGE_ROUTER.md` (CRS). CRS يُطبِّق F30/F31 على مستوى الطلب — ليس طبقة فوقهما.
Workflow order: `ARCHITECTURE_FOUNDATION → SYSTEMS_INDEX → CRS → Governing System → Runtime`
Authority يبقى دائماً: `ARCHITECTURE_FOUNDATION F1–F39`

---

## F32 — [P0] Date & Time Fields System (DS-DATE)

**DS-DATE هو النظام الرسمي الوحيد لكل حقول التاريخ والوقت في منصة تواصلنا.**

### القواعد الأساسية

1. **DS-SEL هو المحرك البصري** — كل Date/Time field مرئي للمستخدم يستخدم Custom DS-SEL Dropdown لا native `<input type="date">` ولا native `<select>`.
2. **Data Precision Contract صارم** — Year-only ≠ Full Date ≠ Month+Year. لا قيم وهمية لإكمال الدقة المفقودة (مثل: `2022` لا تصبح `2022-01-01`).
3. **الخيارات الزمنية تُوَلَّد بالكود** — الأيام والشهور والسنوات والساعات والدقائق تُنشأ برمجياً. لا جداول DB لهذه القيم.
4. **الاعتماديات الزمنية تنتمي لـ DS-DATE** — حساب أيام الشهر (Leap Year)، تقييد نطاق نهاية بناءً على البداية، Cascade Clear عند تغيير الشهر — كلها DS-DATE وليست منطقاً مستقلاً في كل page.
5. **DS-FRM/DS-VAL/API-MUT تحتفظ بمسؤولياتها** — DS-DATE يُنتج Canonical Values؛ DS-FRM يبني الـ Payload؛ DS-VAL يُقرِّر توقيت الخطأ وشكله؛ API-MUT يحكم Tri-state (null/omit/value).
6. **Open-ended Range = null كـ Canonical End Value** — Magic String ممنوعة كـ Canonical Temporal Value. DS-DATE يُعبِّر عن الحالة المفتوحة النهاية بـ End = null. DB representation واسم Domain State (is_current / ongoing / active) يملكهما Feature Contract — ليس DS-DATE.
7. **لا Auto-select** — DS-DATE لا يُخمِّن قيمة للمستخدم عند فتح الحقل أو تغيير Dependent.

### ممنوعات F32

```
❌ <input type="date"> أو <input type="time"> مرئية للمستخدم في الصفحات الموحدة
❌ حساب daysInMonth داخل page module بدون مرجع DS-DATE
❌ "حتى الآن" أو أي نص كـ Canonical Temporal Value
❌ فرض is_current أو أي Domain State name من DS-DATE — يملكه Feature Contract
❌ قيمة وهمية لإكمال الدقة (2022 → 2022-01-01)
❌ نطاق سنوات Global hardcoded خارج contract الحقل
❌ <input type="number"> لإدخال السنة
❌ منطق Temporal Dependency منفصل لكل صفحة
```

**المرجع التفصيلي:** `docs/design-system/DATE-TIME-FIELDS.md` (DATE-00 → DATE-35)

---

## F33 — [P0] Overlay System (DS-OVL)

**DS-OVL هو النظام الرسمي الوحيد لكل Overlays في منصة تواصلنا (Modals / Drawers / Sheets / Confirmations / Dialogs).**

### القواعد الأساسية

1. **Orthogonal Model إلزامي** — كل Overlay يُعرَّف بأربعة محاور مستقلة: Modality × Presentation × Semantics × Close Policy. ممنوع Flat Type Enum.
2. **لا Overlay engine موازٍ** — ممنوع إنشاء Modal system أو Overlay handler داخل أي page module خارج DS-OVL contract.
3. **Close Guard Generic** — DS-OVL لا يعتمد على DS-FRM مباشرةً. أي Dirty-state integration يمر عبر Generic Close Guard Interface (`allow | block | require-confirmation`) — لا coupling مباشر بين DS-OVL وDS-FRM.
4. **Background Isolation طوال دورة الحياة** — Isolation تبقى نشطة حتى نهاية Close Animation (حتى في حالة `closing`). ممنوع رفعها مبكراً.
5. **Layer Context ينتجه DS-OVL فقط** — DS-SEL يستهلكه (اختياري). Integration Layer تربط الاثنين — لا coupling CSS أو global query.
6. **DS-NAV يملك Back Intent** — DS-OVL يسجّل Overlay في Layer Stack فقط. ممنوع لأي Overlay بناء `popstate` listener مستقل.
7. **Scroll Lock مركزي** — DS-OVL يملك Reference Counter. Unlock فقط عند count=0.
8. **Responsive = Strategy Presets** — 6 Presets رسمية (OVL-22). ممنوع rule global واحد لكل الـ Overlays.
9. **Semantic Override للـ Initial Focus:** `standard` → `surface-heading` (default) · `confirmation` → `safe-action` (default) · Feature يمكنه Override.
10. **force-close داخلي فقط** — ليس public Close Reason ولا مُعرَّضاً للـ Feature layer.

### ممنوعات F33

```
❌ Modal أو Drawer أو Confirmation يُنفَّذ خارج DS-OVL contract
❌ Flat Type Enum بدلاً من Orthogonal Model
❌ CSS class name كـ Trigger لأي Overlay سلوك
❌ body.overflow-hidden مباشرةً من page module (DS-OVL يملك Scroll Lock)
❌ popstate listener مستقل داخل Overlay — DS-NAV يملك Back Intent
❌ window.confirm() في أي code جديد
❌ DS-OVL Runtime implementation قبل موافقة صريحة
❌ Layer Context binding مباشر بين DS-OVL وDS-SEL (Integration Layer فقط)
❌ إغلاق Background Isolation قبل نهاية Close Animation
```

**المرجع التفصيلي:** `docs/design-system/OVERLAY-SYSTEM.md` (OVL-00 → OVL-37)

---

## F34 — [P0] Operational Feedback System (DS-FEEDBACK)

**DS-FEEDBACK هو النظام الرسمي الوحيد لـ Operational Feedback (Toast / Snackbar) في منصة تواصلنا.**

### القواعد الأساسية

1. **Single Global Feedback Surface** — سطح Snackbar واحد عالمي فقط. لا Stack، لا Queue في V1.
2. **Latest Replaces Current** — كل رسالة جديدة تُلغي الحالية فوراً. `clearTimeout` قبل أي timer جديد إلزامي.
3. **4 أنواع رسمية** — `success / error / warning / info`. جميعها مدعومة في V1.
4. **Duration Policy مركزية** — DS-FEEDBACK يملك مدة كل نوع. Feature code لا تختار مدتها الخاصة. القيم الفعلية في FBK-07.
5. **Mobile Behavior Contract** — الـ Feedback Surface يجب أن تبقى ظاهرة فوق Bottom Navigation وSafe Areas وأي UI ثابت في أسفل الصفحة. لا offset global hardcoded. التفاصيل في FBK-09.
6. **Layer Architecture** — Conceptual Level 4 (Global Feedback Band). `z-index: 9999` placeholder حتى Global Layer Tokens. ممنوع hardcode z-index في Feature layer.
7. **Accessibility V1** — جميع أنواع V1: `role="status"` + `aria-live="polite"` + `aria-atomic="true"`. `role="alert"` مؤجَّل لـ V2.
8. **RTL Centering** — الـ Snackbar يتمركز على المنتصف المادي للـ viewport بصرف النظر عن `dir="rtl"`. ممنوع Logical Properties (`inset-inline-start`) للـ centering على عناصر مُمركَزة. التفاصيل في FBK-10.
9. **DS-FEEDBACK يستقبل رسالة آمنة جاهزة** — لا يُحلِّل API errors. السلسلة: API-MUT-11 → Feature Orchestration → DS-FEEDBACK.
10. **XSS P0 — مُصلَح** — `tw_shared.js` يستخدم الآن `textContent` حصراً (feat/ds-feedback-runtime-v1). Local copies (M9 FBK-24) تُصلَح تدريجياً في PRs Migration.

### ممنوعات F34

```
❌ Toast / Snackbar implementation خارج DS-FEEDBACK contract
❌ showFeedback مع raw API body — normalizeErrorResponse() أولاً
❌ z-index hardcoded في Feature module للـ Snackbar
❌ role="alert" في V1 — polite فقط (assertive مؤجَّل لـ V2 critical:true)
❌ loading state داخل Snackbar V1 — يبقى في Button / Component
❌ dur=99999 كبديل loading — ممنوع
❌ innerHTML لعرض msg في Runtime — textContent حصراً
❌ DS-FEEDBACK Runtime Implementation قبل موافقة صريحة
❌ inset-inline-start: 50% على Snackbar المُمركَز
```

**المرجع التفصيلي:** `docs/design-system/FEEDBACK-SYSTEM.md` (FBK-00 → FBK-29)

---

## F35 — [P0] Color System V1 (DS-COLOR)

**DS-COLOR هو النظام الرسمي الوحيد لكل color tokens في منصة تواصلنا.**

### القواعد الأساسية

1. **`--color-*` namespace محجوز حصراً لـ DS-COLOR** — لا يُعرَّف أو يُعاد تعريف `--color-*` خارج `tw_shared.css`. Page CSS files ممنوعة من إنشاء أو override أي `--color-*` variable.
2. **Three Logical Layers** — Foundation/Primitive (`--color-prim-*`) → Semantic (`--color-brand-*`, `--color-surface-*`, `--color-border-*`, `--color-text-*`, `--color-status-*`, `--color-categorical-*`) → Legacy Aliases (`--ac: var(--color-brand-primary)` إلخ). Feature CSS يستخدم Semantic فقط — لا يلمس Foundation مباشرةً. Feature CSS تستخدم Semantic RGB channels (`--color-brand-primary-rgb`, `--color-status-success-rgb`) — لا Primitive RGB channels مباشرةً.
3. **Token Identity ≠ Token Value** — رمزان مختلفان قد يتشاركان نفس hex value ويبقيان مستقلَّين. تغيير قيمة `--color-brand-primary` لا يُغيِّر `--color-categorical-teal` تلقائياً حتى لو القيمة الحالية متساوية.
4. **Semantic ≠ Categorical** — `--color-status-warning` إشارة UX (خلل/تحذير). `--color-categorical-amber` تمييز بيانات (مستوى مهارة/فئة). ممنوع استخدام Status tokens للتصنيف والعكس.
5. **Domain/Feature Mapping Policy** — DS-COLOR يملك القيمة والهوية. Feature/Domain يملك المعنى (Tier 2 alias يُشير إلى DS-COLOR، لا يُعرِّف قيمة hex بنفسه).
6. **Three-Tier Local Token Policy** — T1: Global DS-COLOR في `tw_shared.css`. T2: Domain Alias في feature CSS (`--co-accent: var(--color-brand-secondary)` — يُشير إلى T1). T3: Local non-color tokens (sizes, durations) + Local Color Role مسموح بشروط (راجع CLR-15). T2 ممنوع أن يُعرِّف ألوانه بنفسه (no `--co-accent: #2563ff`).
7. **Migration ≠ Redesign** — `#00c896 → var(--color-brand-primary)` = ترحيل (لا تغيير بصري). `#00c896 → #00b386` = إعادة تصميم تحتاج موافقة معمارية. ممنوع الخلط.
8. **No Token Without Real Consumer in V1** — لا tokens افتراضية بدون مستهلك حقيقي في نطاق V1.
9. **Phase 0 ✅ Documentation Only (مكتمل). Phase 1 ✅ Runtime Tokens Foundation (مكتمل — PR #520)**: `tw_shared.css` يحتوي الآن على `--color-*` tokens في ثلاثة أقسام (Foundation/Semantic/Legacy Aliases). `--t3` → `var(--color-text-muted)` ✅ (audit مكتمل). `--t4` يبقى raw `rgba(255,255,255,.2)` — mapping مؤجَّل Phase 2 (consumers مختلطة). Phase 2 = page-by-page migration تدريجي عند لمس الصفحات — يحتاج موافقة صريحة لكل صفحة. Phase 4 = حذف Legacy Aliases عند zero consumers. أي تغيير مستقبلي على DS-COLOR يحتاج PR معلن يُحدِّد نوع التغيير (migration / redesign / phase change).

### ممنوعات F35

```
❌ `--color-*` variable تُعرَّف أو تُعاد تعريفها خارج `tw_shared.css`
❌ Page CSS file تُنشئ أو تُعيد تعريف `--color-*` (override DS-COLOR)
❌ تغيير قيمة أي DS-COLOR token أو Legacy Alias بدون PR DS-COLOR معلن
❌ Color system موازٍ خارج DS-COLOR
❌ DS-COLOR Phase 2 (page migration) بدون موافقة صريحة لكل صفحة/نظام
❌ `--color-status-*` tokens لتصنيف البيانات (Categorical)
❌ `--color-categorical-*` tokens لإشارات UX (Semantic Status)
❌ Domain Alias (T2) يُعرِّف قيمة hex بنفسه بدلاً من الإشارة إلى DS-COLOR
❌ Token مُضاف بدون مستهلك حقيقي في V1 scope
```

10. **Color Role Assignment** — كل عنصر مرئي يجب أن يحمل Color Role مقصود ومعروف (Brand / Surface / Text / Status / Categorical). الوراثة مسموحة فقط إذا كانت مقصودة وقابلة للتتبع إلى Color Role رسمي. راجع CLR-33.

**المرجع التفصيلي:** `docs/design-system/COLOR-SYSTEM.md` (CLR-00 → CLR-34, 35 قسماً)

---

## F36 — [P0] Size System V1 (DS-SIZE)

**DS-SIZE هو النظام الرسمي الوحيد لأحجام الواجهة في منصة تواصلنا:** أحجام الخط، الزوايا، المسافات، أحجام الأيقونات، وارتفاعات العناصر التفاعلية.

### القواعد الأساسية

1. **`--size-*` و `--radius-*` و `--space-*` namespaces محجوزة حصراً لـ DS-SIZE** — تُعرَّف فقط في `tw_shared.css` (قسم `1b. DS-SIZE`). أي ملف CSS/HTML/JS آخر ممنوع يعرّفها أو يعيد تعريفها.
2. **السلالم** (SIZE-02 → SIZE-06): خط 12 درجة (`--size-font-3xs` .6rem → `--size-font-display` 2rem، و `--size-font-xl` = .95rem token منفصل) · زوايا 10 درجات (`--radius-2xs` 4px → `--radius-circle` 50%) + `--radius-control: var(--radius-md)` للأزرار والحقول · مسافات `--space-1..13` (2 → 40px) · أيقونات `--size-icon-*` (12 → 22px) · ارتفاعات `--size-control-*` + `--size-touch-min` 44px.
3. **Visual Difference Classification** (SIZE-05): مطابق / تحت البكسل (< 0.5px) / مرئي (≥ 0.5px).
4. **Migration ≠ Redesign** — Migration = استبدال المطابق وتحت البكسل فقط. المرئي بـ PR redesign معلن لكل صفحة. الاستثناء الوحيد المعتمد: أيقونات 13px → `--size-icon-sm` 14px.
5. **Three-Tier Policy** (SIZE-07): T1 عالمي في `tw_shared.css` · T2 alias محلي يُشير إلى T1 (`--r-sm: var(--radius-md)`) · T3 قيمة محلية موثقة (مرئية / شاذة / مجمّدة).
6. **Frozen Exceptions** (SIZE-08): `.sc-actions` / `.sc-btn` (profile-v2) وقيم post-comments — خارج أي migration، حتى القيم المطابقة جوّاها.
7. **لا tokens بدون مستهلك حقيقي** — كل درجة في السلّم إلها استعمالات خام موجودة بجرد المرحلة A. لهيك ما في token لارتفاع 36px (BTN-04 MD) ولا للمسافات الفردية (3/5/7/9/11/13px).
8. **Phase 1 ✅ Tokens Foundation (PR-5 / المرحلة B)**: tokens معرّفة فقط، بدون مستهلك وبدون تغيير بصري. Phase 2 = migration صفحة صفحة بموافقة صريحة لكل صفحة. أي تغيير على قيمة token يحتاج PR DS-SIZE معلن.

### ممنوعات F36

```
❌ `--size-*` / `--radius-*` / `--space-*` تُعرَّف أو تُعاد تعريفها خارج `tw_shared.css`
❌ نسخ tokens لصفحة ما بتحمّل `tw_shared.css`
❌ استبدال قيمة مرئية ضمن PR migration
❌ لمس الاستثناءات المجمّدة (SIZE-08) ضمن migration
❌ DS-SIZE Phase 2 (page migration) بدون موافقة صريحة لكل صفحة
❌ تغيير قيمة أي DS-SIZE token بدون PR DS-SIZE معلن
❌ نظام أحجام موازٍ أو ملف tokens ثاني
```

**المرجع التفصيلي:** `docs/design-system/SIZE-SYSTEM.md` (SIZE-00 → SIZE-12) · `docs/rules/ds-size.md`

---

## F37 — [P0] Icon System V1 (DS-ICON)

**DS-ICON هو النظام الرسمي الوحيد لأيقونات الواجهة في منصة تواصلنا:** مصدر الرسومات، الأسماء، دالة الرسم، والاتجاه بالـ RTL.

### القواعد الأساسية

1. **Registry واحد:** `static/shared/tw-icons.js` — `twIcon(name, opts)` يرجّع string SVG و `twIconEl(name, opts)` يرجّع عنصر DOM. ملف مستقل (مش داخل `tw_shared.js`) ويشتغل بدون `tw_shared.css`.
2. **المصدر:** رسومات Lucide **0.460.0** فقط (ISC — `THIRD_PARTY_NOTICES.md`). أيقونات الكتالوج (`skill_catalog.icon` · `profession_categories.icon` · `TW.SKILL_CATALOG`) داخل الـ registry — الهدف إلغاء مكتبة Lucide كاملة بالمرحلة C.
3. **الأسماء حسب المعنى** للأفعال والتنقّل (`back` / `forward` / `next` / `prev` / `send` / `log-in` / `log-out` / `close` / `delete`…)؛ أسماء الكتالوج = القيمة المخزَّنة بالـ DB. الأسماء القديمة → جدول `ALIASES` واحد.
4. **الاتجاه:** أيقونات `dir:true` بتنقلب تلقائياً بالـ RTL (class `tw-ico-dir` + قاعدة وحدة بيحقنها الملف). ممنوع `arrow-left` / `arrow-right` / `chevron-left` / `chevron-right` يدوي بالصفحات.
5. **الحجم من DS-SIZE** (`opts.size` = `xs`…`2xl` → `var(--size-icon-X, <px>)`) · **اللون `currentColor` فقط** (DS-COLOR) · **stroke-width 2** (استثناء `.sc-btn .ico-sm` 1.8 مجمّد بالـ CSS).
6. **الأمان:** الاسم مفتاح بالـ map فقط — ما بيدخل الـ HTML أبداً؛ اسم غير معروف → fallback ثابت + warning مرّة وحدة.
7. **emoji ممنوعة كأيقونة واجهة.**
8. **لا أيقونات بدون مستهلك.** **Phase B ✅** (PR-6 / المرحلة B): registry + توثيق + اختبار، بدون مستهلك وبدون تغيير بصري. **Phase C** = تحويل صفحة صفحة بموافقة صريحة لكل صفحة، ثم إزالة Lucide و unpkg CDN.

### ممنوعات F37

```
❌ مكتبة أيقونات ثانية / نسخة Lucide غير 0.460 / CDN أيقونات جديد
❌ SVG inline جديد أو <i data-lucide> جديد بأي صفحة
❌ اسم أيقونة يُدمج بالـ HTML (data-lucide="' + name + '")
❌ arrow-left / arrow-right / chevron-left / chevron-right يدوي
❌ لون غير currentColor · stroke-width بالاستدعاء
❌ emoji كأيقونة واجهة
❌ registry ثاني / خريطة أيقونات محلية بصفحة / جدول aliases ثاني
❌ DS-ICON Phase C (تحويل صفحة) بدون موافقة صريحة لكل صفحة
```

**المرجع التفصيلي:** `docs/design-system/ICON-SYSTEM.md` (ICON-00 → ICON-14) · `docs/rules/ds-icon.md`

---

## F38 — [P0] Image Display System V1 (DS-IMAGE)

**DS-IMAGE هو النظام الرسمي الوحيد لعرض صور الحسابات في منصة تواصلنا:** أفاتار الموظف، لوغو الشركة / الجهة التعليمية، الحرف البديل، وأمان رابط الصورة. (الرفع = §29a · القص = §29b — أنظمة منفصلة.)

### القواعد الأساسية

1. **دالة واحدة:** `twAvatarHtml(entity, size, opts)` → string و `twAvatarEl(entity, size, opts)` → عنصر DOM في `tw_shared.js`؛ الاثنين من `_twAvatarSpec` واحد. `entity = { full_name, avatar_url, user_type }`.
2. **سلّم الأحجام** (IMG-02): `--size-avatar-md` 40 · `lg` 48 · `xl` 88 · `2xl` 106 — بقسم DS-SIZE بـ `tw_shared.css`. 22 / 32 (post-comments) مجمّدة محلياً (SIZE-08).
3. **الشكل** (IMG-03): الموظف (`emp`) دائرة `--radius-circle`؛ الجهات (`co` / `edu`) مربع بزوايا مدوّرة بكل مكان — md `--radius-md` · lg `--radius-lg` · xl / 2xl `--radius-3xl`.
4. **الحرف البديل** (IMG-04/05): `Array.from(name.trim())[0]` بدون `toUpperCase`، فارغ → `؟`؛ لونه حسب نوع الحساب من DS-COLOR categorical (emp teal · co blue · edu purple) — بدون hex.
5. **الأمان** (IMG-08 · §54): رابط الصورة يمر فقط على `twSafeImageUrl` (`https://` أو مسار `/` نسبي — مش `//` ولا `/\`)؛ `background-image` فقط عبر `twCssUrl`؛ النص عبر `twEscHtml` / `twEscAttr`.
6. **الفشل** (IMG-06/07): رابط غير صالح → fallback مباشرة (`data-fb="1"`)؛ فشل التحميل → listener واحد (capture، `error`) على `document` بيحط `data-fb="1"`. ممنوع `onerror` inline.
7. **التحميل** (IMG-09): `loading="lazy"` افتراضياً؛ `opts.eager` للـ hero فقط. دائماً `alt=""` + `decoding="async"` + `width` / `height`.
8. **الغلاف** (IMG-10): نسبة 4:1 ثابتة للموظف والشركة (التنفيذ بالمرحلة C).
9. **Phase B ✅** (PR-7b): helper + CSS + tokens + توثيق، بدون مستهلك وبدون تغيير بصري. **Phase C** = تحويل صفحة صفحة بموافقة صريحة + screenshots.

### ممنوعات F38

```
❌ markup أفاتار / لوغو جديد بصفحة بدل twAvatarHtml / twAvatarEl
❌ فحص رابط صورة بـ regex محلي بدل twSafeImageUrl · background-image بدون twCssUrl
❌ img.src = esc(url) أو src="' + esc(url) + '" (escaping HTML ≠ تحقق رابط)
❌ onerror inline · fallback emoji · حرف بـ toUpperCase أو charAt(0)
❌ حجم أفاتار / لون fallback / زاوية بقيمة خام بدل token
❌ دائرة للوغو جهة (co / edu) · مربع لأفاتار موظف
❌ DS-IMAGE Phase C (تحويل صفحة) بدون موافقة صريحة لكل صفحة
```

**المرجع التفصيلي:** `docs/design-system/IMAGE-SYSTEM.md` (IMG-00 → IMG-13) · `docs/rules/ds-image.md`

---

## F39 — [P0] Page Shell V1 (DS-SHELL)

**DS-SHELL هو المصدر الرسمي الوحيد لكتلة `<head>` المشتركة وسكربتات آخر `<body>` المشتركة لكل صفحة HTML.**

### القواعد الأساسية

1. **مصدر واحد:** `page_shell.py` (`apply_shell`) + `partials/shell-*.html` (برّا `static/` — مش منخدمة مباشرة)، مستدعى من `read_html()` بـ `server.py`.
2. **Markers صريحة:** `<!--tw:shell-head-->` + `<!--tw:shell-scripts-->` (app / entry) أو `:admin`. صفحة بدون markers ما بتتغيّر أبداً. markers ناقصة / مكرّرة / مخلوطة → خطأ (F9).
3. **المحتوى:** charset · viewport عادي · theme-color · manifest · `rel="icon"` + `apple-touch-icon` (§32) · Cairo 400–900 · `tw_shared.css` — ثم بآخر body: `tw_shared.js` ← `auth-sync.js`.
4. **عقد الترتيب:** المشترك أولاً (`tw_shared.css` قبل CSS الصفحة) — بيتطبّق على كل صفحة وقت تحويلها فقط (المرحلة C) مع فحص بصري.
5. **النسخة:** `?v=H` = hash قصير لمحتوى الملف، بينحسب مرة وحدة عند بدء السيرفر — بدل `?v=` اليدوي للملفات المشتركة.
6. **الأدمن:** نسخة `:admin` — بدون manifest، بدون `auth-sync.js`، بدون تسجيل SW (`<meta name="tw-sw" content="off">`).
7. **الأمان (§54):** الحقن نص ثابت فقط — ما في بيانات مستخدم.
8. **Phase B ✅** (PR-8): النظام + `home-v2.html` كصفحة تجريبية. **Phase C** = صفحة لكل PR مع screenshots.

### ممنوعات F39

```
❌ نسخ tags الـ shell يدوياً بصفحة محوّلة · ?v= يدوي لملف مشترك
❌ آلية حقن ثانية أو partial ثاني
❌ بيانات مستخدم بالـ partials · خدمة partials/ مباشرة
❌ tw-icons.js أو user-scalable=no بالـ shell
❌ manifest أو auth-sync.js بنسخة الأدمن
❌ تحويل صفحة بدون screenshots قبل/بعد
```

**المرجع التفصيلي:** `docs/design-system/PAGE-SHELL.md` (SHELL-00 → SHELL-08) · `docs/rules/page-shell.md`

---

## أنظمة الحالة الأساسية (System State References)

### Employment Pipeline — مصدر الحالة الوحيد لكل مرشح داخل وظيفة

**المبدأ (F5 — One Source of Truth):**

- `job_pipeline_entries` هو مصدر الحالة الوحيد لكل مرشح داخل وظيفة محددة.
  - كل سجل (company, candidate, job) → مرحلة واحدة (stage) + مصدر واحد (source).
  - لا يوجد جدول ثانٍ يُتتبّع فيه تقدم المرشح داخل وظيفة.
- بنك المواهب (`company_saved_candidates`) مستقل عن الـ Pipeline:
  - يُمثّل علاقة الشركة بالمرشح بغض النظر عن وظيفة بعينها.
  - لا يُستخدم لتتبع مرحلة المقابلة أو العرض أو التوظيف — ذلك من صلاحية `job_pipeline_entries`.

**المرجع التفصيلي:** `ARCHITECTURE.md §66`

---

## ملاحظات التطبيق

### الإشارات المرجعية

- التوثيق التفصيلي للأنظمة: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- فهرس الأنظمة: [`docs/SYSTEMS_INDEX.md`](docs/SYSTEMS_INDEX.md)
- قواعد الـ AI sessions: [`CLAUDE.md`](CLAUDE.md)

### Exceptions المعتمدة

أي استثناء عن هذه القواعد يُسجَّل في:
- `ARCHITECTURE.md §C — EXCEPTIONS LOG`
- مع توضيح السبب والحالة وتاريخ الاعتماد

### التحديثات

هذا الملف يُحدَّث فقط عند:
- إضافة قاعدة عليا جديدة
- تغيير في قاعدة موجودة (يتطلب PR مستقل)
- لا يُحدَّث كجزء من PR ميزة عادية

---

*آخر تحديث: 2026-10-07 — PR 2B — F16 · التاريخ الكامل: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)*
