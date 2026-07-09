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
