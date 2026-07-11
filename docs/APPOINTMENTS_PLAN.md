# Appointments & Interview Rooms System — Phase 0 Audit & Architecture Plan

> **هذا الملف خطة معمارية docs-only. لا تنفيذ لأي كود حتى طلب صريح من المستخدم.**
> وجود هذا الملف لا يعني إذناً بتنفيذ أي مرحلة — كل مرحلة تحتاج موافقة صريحة.
> إذا تعارض أي بند مع `ARCHITECTURE_FOUNDATION.md` — الدستور يفوز.

---

## 1. Appointments System Purpose

نظام المواعيد والمقابلات هو نظام **رسمي ومستقل** لإدارة دورة حياة مقابلات العمل على المنصة.

الهدف: ربط الشركة بالموظف المتقدم ضمن إطار رسمي محكوم بصلاحيات وسجل أحداث لا يُحذف.

**ما يديره النظام:**

- دعوات مقابلات العمل من الشركة للموظف
- اقتراح موعد محدد (تاريخ + وقت + طريقة)
- موافقة الموظف على الموعد
- طلب موعد آخر من الموظف
- تأكيد الموعد من الطرفين
- إلغاء الموعد من أحد الطرفين
- إنهاء الموعد وإغلاق الغرفة
- غرفة موعد خاصة بكل مقابلة
- محادثة appointment thread مقيّدة بموضوع الموعد
- سجل أحداث رسمي لكل إجراء مهم

**ما لا يديره النظام:**

- الكلام العام بين المستخدمين (→ Messenger العام)
- إشعارات زمنية (→ مؤجلة حتى بناء Scheduler)
- تسجيل نتيجة المقابلة كقرار HR (→ مستقبلي)

---

## 2. Core Rule — القاعدة الذهبية

```
Messenger العام  → الكلام العام بين المستخدمين.
Appointment Room → أي شيء متعلق بموعد محدد.
```

**القرارات الرسمية لا تُؤخذ من رسائل الشات.**

أي إجراء رسمي — موافقة، طلب تغيير موعد، اعتذار، إلغاء — لا يُعتبر مقبولاً إلا إذا جاء من **زر رسمي** داخل غرفة الموعد:

```
❌ الموظف يكتب "تمام" في الشات → لا تعتبر موافقة.
✅ الموظف يضغط زر "موافق على الموعد" → موافقة رسمية مسجَّلة.

❌ الشركة تعتبر الموظف موافقاً لأنه ردّ بـ"حسناً" في الشات.
✅ الشركة ترى أن الموظف ضغط زر الموافقة الرسمية.
```

**العلاقة بين القنوات الثلاث:**

| القناة | الغرض | القرارات الرسمية |
|--------|--------|------------------|
| **Messenger العام** | كلام عام بين أي مستخدمين | ❌ لا |
| **Appointment Room** | محادثة خاصة بموعد واحد | ✅ عبر أزرار رسمية فقط |
| **Notifications** | أحداث قابلة للفعل (دعوة، رد، تذكير) | 🔔 إشعار + توجيه للغرفة |

---

## 3. User Flows

### Employee Flow — الموظف

1. يرى زر "المواعيد" في شريط التنقل.
2. يفتح صفحة المواعيد — يرى بطاقات مواعيده مع الشركات.
3. يضغط "فتح غرفة الموعد" على بطاقة مقابلة.
4. داخل الغرفة يرى: اسم الشركة + الوظيفة + التاريخ والوقت + الحالة + ممثل الشركة.
5. إذا الحالة `pending_response`:
   - يضغط **"موافق على الموعد"** → ينتقل إلى `confirmed`.
   - يضغط **"طلب موعد آخر"** → يكتب سبباً → ينتقل إلى `reschedule_requested`.
   - يضغط **"اعتذار / إلغاء"** → يكتب سبباً → ينتقل إلى `cancelled`.
6. يستخدم **محادثة الموعد** للأسئلة المتعلقة بالموعد فقط (موقع، طريقة الاتصال، تفاصيل).
7. القرارات الرسمية فقط بالأزرار — ليس بالشات.

### Company Flow — الشركة

1. من قائمة طلبات وظيفة، تختار متقدماً.
2. تضغط "دعوة لمقابلة" → تنشئ دعوة جديدة في حالة `draft`.
3. تحدد:
   - التاريخ والوقت المقترح.
   - النوع: أونلاين (`online`) أو حضوري (`onsite`).
   - إذا أونلاين: رابط المقابلة.
   - إذا حضوري: موقع واضح.
   - ممثل الشركة (اختياري — fallback: "ممثل الشركة").
   - مهلة الرد: 24ساعة / 48ساعة / 3أيام / 7أيام.
4. ترسل الدعوة → تنتقل إلى `pending_response`.
5. تتابع رد الموظف من غرفة الموعد.
6. إذا الموظف طلب موعداً آخر (`reschedule_requested`):
   - تقترح موعداً جديداً → تُعيد إلى `pending_response`.
7. إذا الموظف وافق → `confirmed`.
8. بعد إجراء المقابلة → تضغط "إنهاء المقابلة" → `completed` → تُغلق الغرفة → `closed`.

---

## 4. Appointment Cards

### بطاقة الموظف

| الحقل | المحتوى |
|-------|---------|
| اسم الشركة | الشركة التي أرسلت الدعوة |
| اسم الوظيفة | الوظيفة المرتبطة بالموعد |
| حالة الموعد | `pending_response` / `confirmed` / `cancelled` / ... |
| التاريخ والوقت | الموعد المقترح أو المؤكَّد |
| المتبقي على الموعد | عداد تنازلي — حساب frontend-only من `scheduled_at` |
| زر | "فتح غرفة الموعد" |

### بطاقة الشركة

| الحقل | المحتوى |
|-------|---------|
| اسم المتقدم | الموظف المدعو |
| اسم الوظيفة | الوظيفة المرتبطة |
| حالة الدعوة | `pending_response` / `confirmed` / `expired` / ... |
| آخر رد | آخر إجراء من الموظف (نص مختصر من `appointment_events`) |
| الموعد المقترح | التاريخ والوقت |
| زر | "فتح غرفة الموعد" |

---

## 5. Appointment Room — غرفة الموعد

كل موعد له غرفة مستقلة تحتوي:

| العنصر | التفاصيل |
|--------|---------|
| ملخص الموعد | نوع المقابلة + الوظيفة |
| تفاصيل الموعد | التاريخ + الوقت + أونلاين/حضوري |
| رابط المقابلة | للأونلاين فقط — **مرئي للأطراف المصرح لهم فقط** (موظف + ممثل الشركة) |
| موقع المقابلة | للحضوري — عنوان واضح |
| اسم الشركة | الشركة الداعية |
| اسم المتقدم | الموظف المدعو |
| ممثل الشركة | اسم مسؤول المقابلة، أو "ممثل الشركة" كـ fallback |
| حالة الموعد | badge واضح يعكس الحالة الحالية |
| أزرار القرار | تظهر حسب الدور والحالة (موافق / طلب موعد آخر / إلغاء / إنهاء) |
| سجل الأحداث | timeline رسمي لكل حدث — chronological — read-only |
| محادثة الموعد | appointment thread — رسائل خاصة بهذا الموعد فقط |
| عداد تنازلي | الوقت المتبقي على الموعد أو على مهلة الرد — frontend-only (بدون server-push) |

**قواعد الغرفة:**

- الغرفة لا تُحذف أبداً — حتى بعد `closed`.
- بعد `closed` → الغرفة read-only — لا رسائل، لا أزرار إجراء.
- رابط المقابلة الأونلاين لا يظهر إلا للطرفين المصرح لهم — الشركة والموظف المدعو.
- سجل الأحداث يُعرض للطرفين.

---

## 6. Appointment States — حالات الموعد

| الحالة | الوصف |
|--------|-------|
| `draft` | الشركة تجهّز الدعوة — لم ترسلها بعد. الموظف لا يراها. |
| `pending_response` | الدعوة مُرسَلة — في انتظار رد الموظف. مهلة الرد تعمل من هنا. |
| `reschedule_requested` | الموظف طلب موعداً آخر — ينتظر الشركة تقترح موعداً جديداً. |
| `confirmed` | الطرفان وافقا على الموعد — الموعد مؤكَّد. |
| `cancelled` | أحد الطرفين ألغى الموعد. الغرفة تبقى مقروءة. |
| `expired` | انتهت مهلة الرد بدون رد من الموظف. يحتاج scheduler للتحديث التلقائي — مؤجل. |
| `missed` | مرّ وقت الموعد بدون إغلاق أو تأكيد نتيجة واضحة. |
| `completed` | تمت المقابلة — الشركة ضغطت "إنهاء المقابلة". |
| `closed` | الغرفة مغلقة نهائياً — read-only — لا أزرار إجراء. |

### State Transitions المقترحة

```
draft
  └─(الشركة ترسل الدعوة)──────────→ pending_response
       ├─(الموظف يوافق)──────────→ confirmed
       │     └─(بعد الموعد)──────→ completed → closed
       ├─(الموظف يطلب موعد آخر)──→ reschedule_requested
       │     └─(الشركة تقترح)────→ pending_response (دورة جديدة)
       ├─(الموظف يلغي)────────────→ cancelled → closed
       ├─(الشركة تلغي)────────────→ cancelled → closed
       └─(انتهاء المهلة)──────────→ expired → closed
```

---

## 7. Response Deadline — مهلة الرد

الشركة تختار مهلة الرد عند إرسال الدعوة:

| الخيار | المدة |
|--------|-------|
| خيار 1 | 24 ساعة |
| خيار 2 | 48 ساعة |
| خيار 3 | 3 أيام |
| خيار 4 | 7 أيام |

**قواعد مهلة الرد:**

- `response_deadline_at` يُحسب من وقت الإرسال + المهلة المختارة.
- **لا يجوز أن تكون مهلة الرد بعد وقت المقابلة** — validation server-side إلزامي.
- إذا لم يرد الموظف خلال المهلة → الحالة تصبح `expired` تلقائياً.
- الدعوة المنتهية لا تُحذف — تظهر بحالة `expired` مع سجل واضح.
- الشركة تستطيع بعد `expired` إرسال دعوة جديدة (appointment جديد من الصفر).
- **auto-expire يحتاج scheduler** — مؤجل حتى بناء Scheduler Infrastructure.
- بدون scheduler: الحالة `expired` تُعرض based on `response_deadline_at < NOW()` عند فتح الصفحة (computed at request-time) — لكن لا إشعارات تلقائية.

---

## 8. Proposed Data Model — نموذج البيانات المقترح (بدون تنفيذ)

> **هذه اقتراحات فقط. لا migration، لا CREATE TABLE، لا كود.**
> المرحلة 1 من Build Phases ستُنفّذ هذا النموذج.

### جدول `appointments`

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `id` | SERIAL PK | معرّف فريد |
| `job_id` | INT FK → jobs(id) | الوظيفة المرتبطة |
| `application_id` | INT FK → job_applications(id) | طلب التوظيف المرتبط |
| `company_id` | INT FK → users(id) | الشركة الداعية |
| `applicant_id` | INT FK → users(id) | الموظف المدعو |
| `created_by` | INT FK → users(id) | من أنشأ الدعوة |
| `representative_user_id` | INT FK → users(id) NULL | ممثل الشركة (nullable) |
| `representative_name` | TEXT NULL | اسم الممثل كـ fallback |
| `status` | TEXT | draft / pending_response / reschedule_requested / confirmed / cancelled / expired / missed / completed / closed |
| `mode` | TEXT | online / onsite |
| `scheduled_at` | TIMESTAMPTZ | التاريخ والوقت المقترح |
| `response_deadline_at` | TIMESTAMPTZ | موعد انتهاء مهلة الرد |
| `location_text` | TEXT NULL | موقع المقابلة الحضورية |
| `online_url` | TEXT NULL | رابط المقابلة الأونلاين (مقيَّد بالأطراف المصرح لهم) |
| `notes` | TEXT NULL | ملاحظات الشركة |
| `created_at` | TIMESTAMPTZ | تاريخ الإنشاء |
| `updated_at` | TIMESTAMPTZ | آخر تحديث |
| `closed_at` | TIMESTAMPTZ NULL | تاريخ الإغلاق |

### جدول `appointment_participants`

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `id` | SERIAL PK | |
| `appointment_id` | INT FK → appointments(id) | |
| `user_id` | INT FK → users(id) | |
| `role` | TEXT | company / applicant / representative |
| `joined_at` | TIMESTAMPTZ | |

### جدول `appointment_events`

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `id` | SERIAL PK | |
| `appointment_id` | INT FK → appointments(id) | |
| `actor_id` | INT FK → users(id) NULL | من أجرى الحدث (NULL للأحداث التلقائية) |
| `event_type` | TEXT | نوع الحدث — انظر §11 |
| `old_status` | TEXT NULL | الحالة السابقة |
| `new_status` | TEXT NULL | الحالة الجديدة |
| `metadata` | JSONB NULL | بيانات إضافية (تاريخ مقترح، سبب، ...) |
| `created_at` | TIMESTAMPTZ | |

### جدول `appointment_messages` (أو `appointment_threads`)

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `id` | SERIAL PK | |
| `appointment_id` | INT FK → appointments(id) | |
| `sender_id` | INT FK → users(id) | |
| `body` | TEXT | نص الرسالة |
| `status` | TEXT | active / deleted |
| `created_at` | TIMESTAMPTZ | |
| `deleted_at` | TIMESTAMPTZ NULL | soft delete |

**ملاحظة:** `appointment_messages` منفصل عن `messages` (الماسنجر العام). لا يُدمجان.

---

## 9. Proposed API Endpoints — نقاط النهاية المقترحة (بدون تنفيذ)

> **هذه اقتراحات فقط. لا تنفيذ في هذا PR.**
> كل endpoint يحتاج `Depends(verify_token)` و ownership check.

| الـ Method | المسار | الوصف | الصلاحية |
|-----------|--------|-------|----------|
| `POST` | `/appointments` | إنشاء دعوة جديدة (draft) | `co` فقط + owner check |
| `GET` | `/appointments` | قائمة مواعيدي | كل مستخدم — يرى مواعيده فقط |
| `GET` | `/appointments/{id}` | تفاصيل موعد واحد + thread | أطراف الموعد فقط |
| `POST` | `/appointments/{id}/send` | إرسال الدعوة draft → pending_response | `co` + owner |
| `POST` | `/appointments/{id}/accept` | الموظف يوافق | `emp` + applicant |
| `POST` | `/appointments/{id}/request-reschedule` | الموظف يطلب موعداً آخر | `emp` + applicant |
| `POST` | `/appointments/{id}/reschedule` | الشركة تقترح موعداً جديداً | `co` + owner |
| `POST` | `/appointments/{id}/cancel` | إلغاء الموعد | أي طرف (مع سبب) |
| `POST` | `/appointments/{id}/complete` | إنهاء المقابلة | `co` + owner فقط |
| `POST` | `/appointments/{id}/close` | إغلاق الغرفة نهائياً | `co` + owner فقط |
| `POST` | `/appointments/{id}/messages` | إرسال رسالة في thread الموعد | أطراف الموعد |
| `GET` | `/appointments/{id}/messages` | جلب رسائل thread الموعد | أطراف الموعد فقط |
| `GET` | `/appointments/{id}/events` | جلب سجل الأحداث | أطراف الموعد |

---

## 10. Permissions — قواعد الصلاحيات

```
✅ الموظف يرى مواعيده فقط — لا مواعيد الشركات الأخرى.
✅ الشركة ترى مواعيدها فقط — لا مواعيد الشركات الأخرى.
✅ ممثل الشركة يدخل فقط إذا أُضيف صراحةً أو كان owner.
✅ الموظف لا يستطيع تعديل تفاصيل الموعد مباشرة — فقط يطلب reschedule.
✅ الشركة لا تستطيع اعتبار الموظف موافقاً — يجب فعل الموظف من حسابه.
✅ أي تعديل بعد confirmed يحتاج موافقة الطرف الثاني.
✅ online_url لا يظهر إلا للأطراف المصرح لهم (applicant + representative).
✅ بعد closed الغرفة read-only للجميع.
✅ كل action رسمي يُسجَّل في appointment_events.
✅ لا hard delete لأي appointment أو event.

❌ ممنوع: guest يرى غرفة موعد.
❌ ممنوع: شركة أخرى ترى بيانات موعد.
❌ ممنوع: الموظف يلغي موعد غيره.
❌ ممنوع: الشركة تُكمل موعداً لم يُؤكَّد بعد (يجب confirmed أولاً).
❌ ممنوع: القرارات الرسمية عبر رسائل الشات.
```

---

## 11. Appointment Events / Timeline — أنواع الأحداث

| نوع الحدث | مَن يُحدِّثه | الوصف |
|-----------|------------|-------|
| `appointment_created` | الشركة | إنشاء الدعوة في حالة draft |
| `appointment_sent` | الشركة | إرسال الدعوة للموظف |
| `appointment_accepted` | الموظف | الموظف وافق على الموعد |
| `appointment_reschedule_requested` | الموظف | الموظف طلب موعداً آخر |
| `appointment_rescheduled` | الشركة | الشركة اقترحت موعداً جديداً |
| `appointment_confirmed` | النظام | بعد قبول الموعد الجديد |
| `appointment_cancelled` | أي طرف | مع تسجيل السبب |
| `appointment_expired` | النظام | انتهاء مهلة الرد (computed) |
| `appointment_completed` | الشركة | إنهاء المقابلة |
| `appointment_closed` | الشركة | إغلاق الغرفة نهائياً |
| `message_sent` | أي طرف | إرسال رسالة في thread |

**عرض الـ timeline:**

```
✦ تم إنشاء دعوة مقابلة.
✦ الشركة أرسلت دعوة بتاريخ [التاريخ والوقت].
✦ الموظف طلب موعداً آخر.
✦ الشركة اقترحت موعداً جديداً: [التاريخ والوقت].
✦ الموظف وافق على الموعد.
✦ تم تأكيد الموعد.
✦ تمت المقابلة.
✦ تم إغلاق غرفة الموعد.
```

الـ timeline يُعرض للطرفين. كل حدث يحتوي actor + timestamp + وصف مختصر.

---

## 12. Notifications — الإشعارات المستقبلية

### إشعارات فورية (event-driven — قابلة للتنفيذ بدون scheduler)

| الحدث | المستلم | النوع المقترح |
|-------|---------|--------------|
| وصلتك دعوة مقابلة جديدة | الموظف | `appointment_invited` |
| الموظف وافق على الموعد | الشركة | `appointment_accepted` |
| الموظف طلب موعداً آخر | الشركة | `appointment_reschedule_requested` |
| الشركة اقترحت موعداً جديداً | الموظف | `appointment_rescheduled` |
| تم تأكيد الموعد | الطرفان | `appointment_confirmed` |
| تم إلغاء الموعد | الطرف الثاني | `appointment_cancelled` |
| تم إغلاق غرفة الموعد | الطرفان | `appointment_closed` |

**ملاحظة:** هذه الإشعارات مرتبطة بـ `create_notification` في `auth.py`. تُنفَّذ في **Phase 7** فقط.

### تذكيرات زمنية (reminder-based — تحتاج scheduler — مؤجلة)

| التذكير | المستلم | السبب |
|---------|---------|-------|
| قبل الموعد بـ 24 ساعة | الطرفان | يحتاج scheduler |
| قبل الموعد بساعة | الطرفان | يحتاج scheduler |
| قبل انتهاء مهلة الرد | الموظف | يحتاج scheduler |

**هذه التذكيرات مؤجلة حتى بناء Scheduler Infrastructure بقرار مستقل.**
انظر: `docs/NOTIFICATIONS_PLAN.md → Scheduler Blocker Note`.

### سياسة event_key

```
appointment_invited:{appointment_id}:{applicant_id}
appointment_accepted:{appointment_id}:{company_id}
appointment_reschedule_requested:{appointment_id}:{company_id}
appointment_rescheduled:{appointment_id}:{applicant_id}
appointment_confirmed:{appointment_id}:{actor_id}
appointment_cancelled:{appointment_id}:{affected_party_id}
appointment_closed:{appointment_id}:{affected_party_id}
```

---

## 13. Security / Abuse Risks — المخاطر والتخفيفات

| الخطر | التخفيف |
|-------|---------|
| **تسريب رابط مقابلة أونلاين** | `online_url` لا يُعاد في GET العام — فقط لأطراف الموعد المصرح لهم (server-side check) |
| **دخول شخص غير طرف في الموعد** | كل endpoint يتحقق من `user_id in appointment_participants` — لا توثيق بالـ URL |
| **شركة تدّعي أن الموظف وافق** | الحالة `confirmed` لا تتغير إلا بعد `POST /appointments/{id}/accept` من حساب الموظف نفسه (JWT) |
| **استعمال الشات بدل الأزرار الرسمية** | القرارات لا تُستخلص من نص الرسائل — النظام يتجاهل مضمون الرسائل في قرارات الحالة |
| **حذف السجل** | `appointment_events` لا يُحذف أبداً — soft delete فقط على الرسائل — F27 |
| **مواعيد spam من شركة** | rate limiting على `POST /appointments` + server-side check: موعد واحد نشط per (job_id, applicant_id) |
| **روابط خارجية مشبوهة في `online_url`** | validation: URL scheme يجب أن يكون `https://` فقط — لا `javascript:` أو `data:` |
| **تغيير موعد confirmed بدون موافقة الطرف الثاني** | بعد `confirmed`، أي تعديل يمر عبر `reschedule_requested` flow — لا تعديل مباشر |

---

## 14. Build Phases — مراحل التنفيذ المقترحة

> **لا تنفيذ لأي مرحلة إلا بطلب صريح من المستخدم.**

| المرحلة | العنوان | الحالة | ما يشمل | الملفات |
|---------|---------|--------|---------|---------|
| **Phase 1** | Schema + Migration only | ✅ **مُنجز — PR #460** | `_migrate_appointments()` في `auth.py` — الجداول الأربعة + indexes + FK — لا endpoints | `auth.py`, `server.py` |
| **Phase 2** | Backend APIs الأساسية | 🔜 pending | `auth.py` helpers + `server.py` endpoints (POST/GET/accept/cancel/complete/close) — بدون frontend | `auth.py`, `server.py` |
| **Phase 3** | Employee Appointments List | 🔜 pending | صفحة المواعيد للموظف — بطاقات + حالات | `static/appointments/`, `appointments.html` (جديد) |
| **Phase 4** | Company Appointments List | 🔜 pending | قائمة المواعيد للشركة في company profile | تعديل على `company-profile.html` + modules |
| **Phase 5** | Appointment Room | 🔜 pending | غرفة الموعد — تفاصيل + أزرار + timeline + عداد تنازلي | صفحة جديدة `appointment-room.html` |
| **Phase 6** | Appointment Thread / Messages | 🔜 pending | محادثة الموعد داخل الغرفة | endpoint messages + frontend |
| **Phase 7** | Appointment Notifications | 🔜 pending | hooks في `auth.py` للإشعارات الفورية (بدون scheduler) | `auth.py` |
| **Phase 8** | Scheduler-based Reminders | ⏸ مؤجل | تذكيرات قبل الموعد وقبل انتهاء المهلة | **يحتاج Scheduler Infrastructure** |

---

## 15. Phase 1 — Final Schema (PR #460)

> **هذا القسم يوثّق الجداول الفعلية التي أُنشئت في Phase 1.**

### `appointments` table

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | SERIAL PK | |
| job_id | INTEGER NULL → jobs(id) SET NULL | |
| application_id | INTEGER NULL → job_applications(id) SET NULL | |
| company_id | INTEGER NOT NULL → users(id) CASCADE | |
| applicant_id | INTEGER NOT NULL → users(id) CASCADE | |
| created_by | INTEGER NOT NULL → users(id) CASCADE | |
| representative_user_id | INTEGER NULL → users(id) SET NULL | |
| representative_name | TEXT NULL | اسم المندوب إذا لم يكن حساباً مسجلاً |
| status | TEXT NOT NULL DEFAULT 'draft' | القيم: انظر §6 |
| mode | TEXT NOT NULL DEFAULT 'online' | online \| onsite |
| scheduled_at | TIMESTAMPTZ NULL | |
| response_deadline_at | TIMESTAMPTZ NULL | |
| location_text | TEXT NULL | للمقابلات onsite |
| online_url | TEXT NULL | للمقابلات online — محجوب عن غير الأطراف |
| notes | TEXT NULL | ملاحظات داخلية من المنشئ |
| created_at | TIMESTAMPTZ DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ DEFAULT NOW() | |
| closed_at | TIMESTAMPTZ NULL | يُملأ عند status='closed' |

**Indexes:** company_id · applicant_id · application_id · job_id · status · scheduled_at · response_deadline_at

---

### `appointment_participants` table

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | SERIAL PK | |
| appointment_id | INTEGER NOT NULL → appointments(id) CASCADE | |
| user_id | INTEGER NOT NULL → users(id) CASCADE | |
| role | TEXT NOT NULL | company \| applicant \| representative |
| can_message | BOOLEAN DEFAULT TRUE | |
| can_decide | BOOLEAN DEFAULT FALSE | |
| created_at | TIMESTAMPTZ DEFAULT NOW() | |
| — | UNIQUE(appointment_id, user_id) | لا تكرار لنفس المشارك |

**Indexes:** appointment_id · user_id

---

### `appointment_events` table (immutable — F18/F27)

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | SERIAL PK | |
| appointment_id | INTEGER NOT NULL → appointments(id) CASCADE | |
| actor_id | INTEGER NULL → users(id) SET NULL | |
| event_type | TEXT NOT NULL | انظر §11 |
| old_status | TEXT NULL | |
| new_status | TEXT NULL | |
| payload | JSONB NULL | بيانات إضافية |
| created_at | TIMESTAMPTZ DEFAULT NOW() | |

**Indexes:** appointment_id · event_type · created_at

> **ملاحظة F27:** `appointment_events` لا تُحذف نهائياً أبداً — سجل حوادث دائم.

---

### `appointment_messages` table

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | SERIAL PK | |
| appointment_id | INTEGER NOT NULL → appointments(id) CASCADE | |
| sender_id | INTEGER NOT NULL → users(id) CASCADE | |
| body | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ DEFAULT NOW() | |
| edited_at | TIMESTAMPTZ NULL | |
| deleted_at | TIMESTAMPTZ NULL | Soft delete — F27 |

**Indexes:** appointment_id · created_at · sender_id

---

### Phase 1 — Migration Startup Rule

> **Appointments migration is startup-critical.**
> Failure in `_migrate_appointments()` raises and stops startup — the app must not run with missing appointments tables.
> Pattern in `server.py`: `print(f"❌ ...") → raise` (not `⚠️` warning-only).

### Phase 1 — Non-goals (ما لا يوجد بعد)

```
❌ لا endpoints
❌ لا UI أو صفحات
❌ لا notifications hooks
❌ لا Messenger changes
❌ لا scheduler
❌ لا WebSocket
❌ لا push
```

**Phase 0 Non-goals (للمرجعية):**
هذا PR الأصلي كان docs-only (PR #459) — Phase 0 Architecture Plan فقط. التنفيذ بدأ من Phase 1.

---

## Related Systems

| النظام | المرجع |
|--------|--------|
| Jobs & Applications | `docs/SYSTEMS_INDEX.md §13, §15` · `ARCHITECTURE.md §62` |
| Notifications | `docs/NOTIFICATIONS_PLAN.md` · `docs/SYSTEMS_INDEX.md §19` |
| Messaging (Messenger) | `docs/SYSTEMS_INDEX.md §18` · `ARCHITECTURE.md §47–48` |
| Auth / JWT | `docs/SYSTEMS_INDEX.md §2` |
| Smart Router `/u/{tw_id}` | `docs/SYSTEMS_INDEX.md §4` · F7 |
| Scheduler Blocker | `docs/NOTIFICATIONS_PLAN.md → Scheduler Blocker Note` |
| Future Roadmap | `docs/FUTURE_ROADMAP.md §15` |

---

## Source of Truth

| العنصر | المرجع |
|--------|--------|
| Architecture Plan | هذا الملف (Phase 0–1) |
| Vision / Backlog | `docs/FUTURE_ROADMAP.md §15` |
| Related Systems Index | `docs/SYSTEMS_INDEX.md §21` |
| Foundation Rules | `ARCHITECTURE_FOUNDATION.md` |

---

*أُنشئ: 2026-07-10 — Phase 0 Audit & Architecture Plan — docs-only (PR #459).*
*حُدِّث: 2026-07-11 — Phase 1 Schema + Migration — auth.py + server.py (PR #460). جداول: appointments, appointment_participants, appointment_events, appointment_messages. لا endpoints، لا UI، لا notifications.*
