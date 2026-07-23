# ARCHITECTURE FOUNDATION — تواصلنا

> **الدستور المعماري لمشروع تواصلنا**
>
> هذا الملف أعلى أولوية من توثيق الميزات التفصيلية.
> إذا تعارض أي توثيق تفصيلي مع هذا الملف، يُعتمد هذا الملف.
>
> **This file has higher priority than feature-level documentation.**
> **If a feature document conflicts with ARCHITECTURE_FOUNDATION.md, the foundation file wins.**
>
> **إلزامي القراءة قبل أي تعديل أو ميزة جديدة.**

---

## Priority Marker

| المستوى | التعريف |
|---------|---------|
| **P0** | غير قابل للكسر. لا استثناء إلا بوثيقة معمارية معتمدة. |
| **P1** | قابل للاستثناء بموافقة صريحة + تسجيل في ARCHITECTURE.md §C |
| **P2** | توجيه مفضّل. مقبول الانحراف إذا كان مبرراً. |

---

## القواعد العليا (Foundation Rules)

| # | القاعدة | Priority |
|---|---------|----------|
| F1 | Platform, Not Website | **P0** |
| F2 | API-first Rule | **P0** |
| F3 | Single Backend / Single Database | **P0** |
| F4 | Shared System First | **P0** |
| F5 | One Source of Truth | **P0** |
| F6 | Backend Owns Permissions | **P0** |
| F7 | Public Routes Contract | **P0** |
| F8 | Mobile-ready Architecture | **P1** |
| F9 | No Silent Failures | **P0** |
| F10 | No Patch-first Development | **P1** |
| F11 | Tests / Static Checks Required | **P1** |
| F12 | Documentation Must Follow Architecture | **P1** |
| F13 | Pre-push GitHub State Check | **P0** |
| F14 | Backward Compatibility Rule | **P0** |
| F15 | Standard API Response Rule | **P1** |
| F16 | Database Migration Rule | **P1** |
| F17 | Security by Default | **P0** |
| F18 | Important Actions Audit-ready Rule | **P1** |
| F19 | Notification-ready Rule | **P2** |
| F20 | Role and Permission Matrix Rule | **P1** |
| F21 | No Client-only Trust | **P0** |
| F22 | Idempotency Rule | **P1** |
| F23 | Observability Rule | **P1** |
| F24 | Storage Ownership Rule | **P1** |
| F25 | Search-ready Data Rule | **P2** |
| F26 | Multi-language Ready Rule | **P2** |
| F27 | Soft Delete Rule | **P1** |
| F28 | Admin-ready Rule | **P2** |
| F29 | One Concept = One Source of Truth (Form & UI) | **P0** |
| F30 | No Matching System = Stop and Report | **P0** |
| F31 | System Routing Before Implementation | **P0** |
| F32 | Date & Time Fields System (DS-DATE) | **P0** |

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

// فشل:
{ "ok": false, "error": "رسالة واضحة للمستخدم أو المطوّر" }
```

### قواعد التطبيق

```
✅ كل endpoint يُرجع "ok": true أو "ok": false
✅ البيانات دائماً تحت "data" أو "result"
✅ الأخطاء دائماً تحت "error" أو "message"
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
# في server.py — كل migration يُضاف في دالة _migrate_*() مستقلة
def _migrate_new_feature():
    try:
        conn = get_conn()
        conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS new_field TEXT")
        conn.run("CREATE TABLE IF NOT EXISTS new_table (...)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_new ON new_table(field)")
    except Exception as e:
        print(f"[migration] new_feature: {e}")
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

---

## F32 — [P0] Date & Time Fields System (DS-DATE)

**DS-DATE هو النظام الرسمي الوحيد لكل حقول التاريخ والوقت في منصة تواصلنا.**

### القواعد الأساسية

1. **DS-SEL هو المحرك البصري** — كل Date/Time field مرئي للمستخدم يستخدم Custom DS-SEL Dropdown لا native `<input type="date">` ولا native `<select>`.
2. **Data Precision Contract صارم** — Year-only ≠ Full Date ≠ Month+Year. لا قيم وهمية لإكمال الدقة المفقودة (مثل: `2022` لا تصبح `2022-01-01`).
3. **الخيارات الزمنية تُوَلَّد بالكود** — الأيام والشهور والسنوات والساعات والدقائق تُنشأ برمجياً. لا جداول DB لهذه القيم.
4. **الاعتماديات الزمنية تنتمي لـ DS-DATE** — حساب أيام الشهر (Leap Year)، تقييد نطاق نهاية بناءً على البداية، Cascade Clear عند تغيير الشهر — كلها DS-DATE وليست منطقاً مستقلاً في كل page.
5. **DS-FRM/DS-VAL/API-MUT تحتفظ بمسؤولياتها** — DS-DATE يُنتج Canonical Values؛ DS-FRM يبني الـ Payload؛ DS-VAL يُقرِّر توقيت الخطأ وشكله؛ API-MUT يحكم Tri-state (null/omit/value).
6. **"حتى الآن" = `null` في DB** — ليست Magic String. DS-DATE يُعرِّف حالة `is_current: true` + `end: null` كـ Open-ended Range.
7. **لا Auto-select** — DS-DATE لا يُخمِّن قيمة للمستخدم عند فتح الحقل أو تغيير Dependent.

### ممنوعات F32

```
❌ <input type="date"> أو <input type="time"> مرئية للمستخدم في الصفحات الموحدة
❌ حساب daysInMonth داخل page module بدون مرجع DS-DATE
❌ "حتى الآن" كـ magic string في DB أو في Payload
❌ قيمة وهمية لإكمال الدقة (2022 → 2022-01-01)
❌ نطاق سنوات Global hardcoded خارج contract الحقل
❌ <input type="number"> لإدخال السنة
❌ منطق Temporal Dependency منفصل لكل صفحة
```

**المرجع التفصيلي:** `docs/design-system/DATE-TIME-FIELDS.md` (DATE-00 → DATE-35)

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

*أُنشئ في PR #420 — 2026-07-09 — الدستور المعماري الأساسي لمشروع تواصلنا.*
*حُدِّث في PR #420 (commit 2) — 2026-07-09 — أُضيفت القواعد F14–F28 (15 قاعدة مستقبلية). المجموع: 28 قاعدة عليا.*
*حُدِّث في PR docs/design-system-forms-v1 — 2026-07-21 — أُضيفت القواعد F29–F31: One Concept = One Source of Truth (Form & UI) · No Matching System = Stop and Report · System Routing Before Implementation. المجموع: 31 قاعدة عليا.*
*حُدِّث في PR #508 — 2026-07-22 — F31 جدول التوجيه: صف dropdown/select حُدِّث للإشارة إلى `docs/design-system/SELECT-PICKER.md` بعد توثيق DS-SEL V1 رسمياً — STOP أُزيل من هذا الصف.*
*حُدِّث في PR docs/ds-date-v1 — 2026-07-23 — أُضيفت القاعدة F32: Date & Time Fields System (DS-DATE). F31 جدول التوجيه: صف تاريخ/وقت أُضيف للإشارة إلى `docs/design-system/DATE-TIME-FIELDS.md`. المجموع: 32 قاعدة عليا.*
