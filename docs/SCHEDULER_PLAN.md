# Scheduler Infrastructure — Architecture Decision Document

> **قرار معماري — docs-only.** لا تُضف scheduler code أو background jobs أو cron أو endpoints جديدة حتى يُصدر قرار صريح من المستخدم.
> وجود هذا الملف لا يعني إذناً بتنفيذ أي مرحلة — كل مرحلة تحتاج موافقة صريحة.
> إذا تعارض أي بند مع `ARCHITECTURE_FOUNDATION.md` — الدستور يفوز.

---

## 1. Why We Need a Scheduler

The current platform computes time-based state at request-time:

- **`_appt_computed_status(appt)`** — computes `'expired'` when a `pending_response` appointment is fetched, not when the deadline passes. DB value stays `pending_response` forever.
- **`_eff_status()` for jobs** — computes `'expired'` from `expiry_date` at query time. DB value stays as-is.

This at-request-time computation is correct for read-only display but cannot handle:

1. **Time-based notifications** — "1 hour before your interview" must fire at a specific moment, regardless of whether any user is making a request. No request triggers it.
2. **Automatic status transitions** — moving `pending_response` → `missed` when `scheduled_at` passes without action. No user action causes this.
3. **Follow-up actions** — archiving expired jobs, sending "48h before deadline" reminders, enforcing response deadlines.

Without a scheduler, these features are permanently unreachable. The scheduler is the missing infrastructure layer between at-request-time computation and event-driven execution.

---

## 2. Dependent Systems (الأنظمة المعتمدة على Scheduler)

The following features are **permanently deferred** until Scheduler Infrastructure is implemented and approved:

| الميزة | النظام المرتبط | السبب |
|--------|--------------|-------|
| `appointment_reminder` | Appointments / Notifications | إشعار "قبل N ساعة من الموعد" — يحتاج job مجدول على `scheduled_at - N` |
| `appointment_deadline_expire` | Appointments | نقل `pending_response` → `expired` في DB تلقائياً عند `response_deadline_at` |
| `appointment_missed` | Appointments | نقل `confirmed` → `missed` في DB عند `scheduled_at + 15 دقيقة` بدون إجراء |
| `job_expiring_soon` | Notifications / Jobs | إشعار "وظيفتك ستنتهي خلال 48 ساعة" — `_eff_status()` لا تولّد event |
| reminder before interview | Appointments / Notifications | يحتاج scheduler + timezone handling محكوم |

**الحالة الحالية للبديل (at-request-time):**

- `pending_response + response_deadline_at < NOW()` → تُعرض كـ `expired` في `_appt_computed_status()`. DB تبقى `pending_response`.
- `confirmed + scheduled_at < NOW()` → لا تنتقل إلى `missed` تلقائياً — تبقى `confirmed` حتى إجراء يدوي.
- هذا صحيح كحل مؤقت لعرض الحالة، لكنه لا يكفي للإشعارات أو الانتقالات الفعلية في DB.

---

## 3. Architectural Requirements (المتطلبات المعمارية)

أي تنفيذ لـ scheduler على هذه المنصة **يجب** أن يستوفي جميع المتطلبات التالية:

### 3.1 Idempotency (F22)
كل job يجب أن يكون idempotent — تشغيله مرتين ينتج نفس نتيجة تشغيله مرة واحدة.

**آلية التطبيق:** `dedupe_key` — حقل `UNIQUE` في DB. قبل إدراج أي job، يُتحقق من وجود `dedupe_key` في الجدول. إذا وُجد ولم يُنفَّذ → skip. إذا وُجد ونُفِّذ بنجاح → skip. `ON CONFLICT (dedupe_key) DO NOTHING` عند الإدراج.

**مثال dedupe_key:**
- `appointment_reminder:{appointment_id}:{hours_before}:{user_id}` — يضمن إشعاراً واحداً لكل (موعد × وقت × مستلم).
- `appointment_expire:{appointment_id}` — يضمن تنفيذ الانتهاء مرة واحدة.

### 3.2 Retry on Failure (F9)
الـ jobs الفاشلة تُعاد بـ exponential backoff. لا job يُهجر بعد أول فشل.

**التنفيذ:** `attempts` counter يزداد بكل محاولة. `last_error` يحفظ آخر رسالة خطأ. عدد retries القصوى يُحدَّد per job_type. بعد استنفاد الـ retries → `status = 'failed'` + log إلزامي.

### 3.3 Failure Logging (F9, F23)
كل فشل job يُسجَّل فوراً: `job_id`، `job_type`، `error`، `timestamp`، `attempts`. لا فشل صامت. `except: pass` محظور في أي job handler.

### 3.4 Duplicate Prevention
لا يصل المستخدم لنفس الإشعار مرتين للحدث ذاته. طبقتان:
1. `scheduler_jobs.dedupe_key` UNIQUE → يمنع إنشاء job مكرر.
2. `create_notification(event_key=...)` ON CONFLICT DO NOTHING → يمنع إدراج notification مكررة.

### 3.5 Timezone Handling
كل `run_at` مخزَّن بـ UTC. `scheduled_at` في appointments مخزَّن بـ UTC. الـ scheduler يقارن الأوقات بـ UTC حصراً. التحويل لـ timezone المستخدم يحدث في الواجهة فقط.

### 3.6 Distributed Locking
إذا عمل الـ scheduler على أكثر من process/dyno → `locked_at` + `locked_by` يمنعان تنفيذ نفس الـ job من عاملَين في الوقت ذاته.

**Lock timeout:** إذا كان `locked_at` أقدم من N دقائق والـ status لا يزال `running` → treat as stale → reset إلى `pending` + retry.

**استعلام آمن:**
```sql
SELECT * FROM scheduler_jobs
WHERE status = 'pending' AND run_at <= NOW()
FOR UPDATE SKIP LOCKED
LIMIT 10
```

### 3.7 No Double-Send
ثلاث طبقات حماية مشتركة:
1. `scheduler_jobs.dedupe_key` UNIQUE → لا job مكرر.
2. `FOR UPDATE SKIP LOCKED` → لا تنفيذ متوازٍ لنفس الـ job.
3. `create_notification` → ON CONFLICT (user_id, event_key) DO NOTHING → لا notification مكررة.

### 3.8 Observability (F23)
كل تنفيذ job يُنتج سجلاً يحتوي: `job_id`، `job_type`، `run_at`، `started_at`، `finished_at`، `status`، `attempts`. يُستعلم من DB — لا logs أو memory فقط.

### 3.9 No Changes Without Approval
تنفيذ الـ scheduler يتطلب: migration للـ DB، مكوّن server جديد، ربما endpoints جديدة. لا شيء من هذا يُضاف بدون موافقة صريحة.

---

## 4. Implementation Options (خيارات التنفيذ)

### Option A — External Cron + Secure Endpoint
خدمة cron خارجية (GitHub Actions، Render Cron، cron-job.org) تستدعي FastAPI endpoint آمن كل N دقائق. الـ endpoint يقرأ الـ jobs المستحقة من DB وينفذها.

**مزايا:**
- إعداد بسيط — لا process Python جديد.
- فشل الـ scheduler ظاهر في logs الخدمة الخارجية.
- لا lock management إذا تنفيذ cron استدعاء واحد في الوقت.
- المنصة تبقى stateless.

**عيوب:**
- الـ endpoint يجب حمايته (secret token أو IP allowlist) — خطر إذا أُسيء الإعداد.
- الـ latency تعتمد على فترة الـ cron (1 دقيقة minimum لمعظم الخدمات المجانية).
- اعتماد خارجي — خدمة cron قد تكون غير موثوقة أو مدفوعة.

**متى يصلح:** منصة صغيرة–متوسطة على Heroku بدينوات محدودة. نقطة بداية جيدة.

---

### Option B — Heroku Scheduler (Hosted Scheduled Job)
Add-on من Heroku يُشغِّل Python script بفترات ثابتة (كل 10 دقائق / ساعة / يوم). الـ script يقرأ الـ jobs المستحقة من DB وينفذها.

**مزايا:**
- تكامل أصلي مع Heroku — لا اعتماد خارجي.
- إعداد بسيط.
- يعمل في نفس بيئة الـ app.

**عيوب:**
- الحد الأدنى 10 دقائق — غير مناسب لـ "قبل ساعة من الموعد".
- لا ضمان وقت التنفيذ — Heroku Scheduler best-effort.
- يحتاج dyno عامل منفصل (تكلفة إضافية).

**متى يصلح:** Jobs منخفضة الدقة (ملخص يومي، تنظيف أسبوعي). ليس مناسباً لـ appointment reminders.

---

### Option C — Background Worker Thread (In-Process)
Thread خلفي يبدأ عند startup الـ server (مثلاً `asyncio.create_task` أو `threading.Thread`) يستطلع DB كل N ثانية وينفذ الـ jobs المستحقة.

**مزايا:**
- لا خدمات خارجية — مكتفٍ بذاته.
- يمكنه العمل بدقة أقل من دقيقة.
- لا تكلفة إضافية (يعمل داخل نفس Heroku dyno).

**عيوب:**
- خطر عالٍ: إذا انهار الـ FastAPI process أو أُعيد تشغيله، jobs قد تضيع وسط التنفيذ.
- Heroku يُعيد تشغيل الدينوات يومياً — يجب معالجة الـ graceful shutdown.
- على أكثر من dyno، عاملان قد ينفذان نفس الـ job — يحتاج distributed locking.
- يحتاج مكتبة مثل APScheduler.

**متى يصلح:** إعدادات single-dyno حيث الموثوقية أقل أهمية. بيئات prototype / staging.

---

### Option D — Database-Driven `scheduler_jobs` Table (Recommended)
جدول `scheduler_jobs` يخزّن جميع الـ jobs المعلقة مع `run_at`, `status`, `dedupe_key`, `locked_at`, `locked_by`. عامل (cron خارجي أو thread) يستعلم بـ `FOR UPDATE SKIP LOCKED` وينفذ الـ jobs atomically. يعمل مع أي نموذج تنفيذ.

**مزايا:**
- جميع الـ jobs محفوظة في DB — لا ضياع عند restart أو crash.
- `FOR UPDATE SKIP LOCKED` يتيح تنفيذاً متوازياً آمناً بعدة عاملين.
- observability كاملة: استعلم DB لرؤية جميع الـ jobs الماضية/المعلقة/الفاشلة.
- Idempotency مُطبَّقة على مستوى DB (`dedupe_key` UNIQUE).
- قابل للجمع مع Option A أو C (نموذج التخزين مستقل عن نموذج التنفيذ).

**عيوب:**
- يحتاج DB migration (جدول `scheduler_jobs`).
- حمل polling بسيط إذا استطلع العامل كل 30 ثانية.

**متى يصلح:** أي حجم. الخيار الموصى به لهذه المنصة.

---

## 5. Evaluation Matrix

| المعيار | A (External Cron) | B (Heroku Scheduler) | C (Background Thread) | D (DB-driven) |
|---------|-------------------|----------------------|-----------------------|---------------|
| Idempotency | ⚠️ يدوي | ⚠️ يدوي | ⚠️ يعتمد | ✅ DB-enforced |
| Retry on failure | ⚠️ يدوي | ⚠️ يدوي | ⚠️ يدوي | ✅ native |
| Duplicate prevention | ⚠️ يعتمد | ⚠️ يعتمد | ❌ صعب | ✅ dedupe_key |
| Precision (timing) | ⚠️ 1-min min | ❌ 10-min min | ✅ sub-minute | ✅ حسب العامل |
| Observability | ⚠️ logs خارجية | ⚠️ logs خارجية | ❌ in-memory فقط | ✅ queryable |
| Crash safety | ⚠️ إذا ضاع job | ⚠️ best-effort | ❌ خطر عالٍ | ✅ محفوظ دائماً |
| Distributed locking | N/A | N/A | ❌ مطلوب يدوياً | ✅ FOR UPDATE SKIP LOCKED |
| Extra cost | ⚠️ free tier limits | ⚠️ extra dyno | ✅ لا تكلفة إضافية | ✅ لا تكلفة إضافية |
| Setup complexity | منخفضة | منخفضة | متوسطة | متوسطة |
| Production readiness | متوسطة | منخفضة | منخفضة | عالية |

---

## 6. Recommendation

**الموصى به: Option D (DB-driven `scheduler_jobs`) + Option A (External Cron كـ runner)**

التركيبة تعطي أفضل توازن:

- **التخزين:** جدول `scheduler_jobs` مع `dedupe_key`, `locked_at`, `locked_by`, `status`, `attempts`, `last_error` — جميع الـ jobs محفوظة، قابلة للمراقبة، وidempotent.
- **العامل:** External cron (GitHub Actions أو Render Cron) يستدعي `POST /internal/run-due-jobs` كل دقيقة. الـ endpoint ينفذ جميع الـ jobs المستحقة بـ `FOR UPDATE SKIP LOCKED`.
- **الـ fallback:** إذا فاتت ticks، الـ tick التالية تلتقط الـ jobs المعلقة — لا تختفي.
- **Multi-worker safe:** `FOR UPDATE SKIP LOCKED` يتعامل مع التنفيذ المتوازي بأمان.

هذا النهج يتيح الانتقال لاحقاً إلى dedicated worker dyno (Option C) دون تغيير schema التخزين.

---

## 7. Proposed Schema (docs only — لم يُنفَّذ)

> ⚠️ هذا الجدول **لم يُنفَّذ**. يحتاج migration مستقل + موافقة صريحة من المستخدم.
> لا تُضف هذا الجدول إلى `auth.py` بدون PR مخصص وموافقة.

```sql
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id           BIGSERIAL PRIMARY KEY,
    job_type     TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}',
    run_at       TIMESTAMPTZ NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','running','done','failed','cancelled')),
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    dedupe_key   TEXT UNIQUE,          -- يمنع إنشاء نفس الـ job مرتين
    locked_at    TIMESTAMPTZ,          -- يُضبط عندما يلتقط عامل الـ job
    locked_by    TEXT,                 -- هوية العامل (dyno id / process id)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sched_run_at ON scheduler_jobs (run_at)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_sched_status ON scheduler_jobs (status);
CREATE INDEX IF NOT EXISTS idx_sched_dedupe ON scheduler_jobs (dedupe_key)
    WHERE dedupe_key IS NOT NULL;
```

### job_type values (planned)

| job_type | payload | run_at |
|----------|---------|--------|
| `appointment_reminder` | `{appointment_id, user_id, hours_before}` | `scheduled_at - hours_before hours` |
| `appointment_deadline_expire` | `{appointment_id}` | `response_deadline_at` |
| `appointment_missed` | `{appointment_id}` | `scheduled_at + 15 min` |
| `job_expiring_soon` | `{job_id, company_id}` | `expiry_date - 48h` |

### Status transitions

```
pending → running → done
             ↓
           failed  (إذا attempts < max_retries → retry)
             ↓
           failed  (terminal، إذا attempts == max_retries)
```

### dedupe_key format

```
appointment_reminder:{appointment_id}:{hours_before}:{user_id}
appointment_deadline_expire:{appointment_id}
appointment_missed:{appointment_id}
job_expiring_soon:{job_id}:{company_id}
```

---

## 8. Implementation Phases (مراحل التنفيذ — مؤجلة)

> ⚠️ لا تبدأ أي مرحلة بدون طلب صريح من المستخدم. هذا جدول تخطيطي فقط.

| المرحلة | المحتوى | الشرط |
|---------|---------|-------|
| **S0** | قرار الأداة (APScheduler / Celery / External Cron / Other) | موافقة مستخدم |
| **S1** | Migration: جدول `scheduler_jobs` في `auth.py` | بعد S0 |
| **S2** | Helper `schedule_job(job_type, payload, run_at, dedupe_key)` في `auth.py` | بعد S1 |
| **S3** | Runner: `run_due_jobs()` + endpoint `POST /internal/run-due-jobs` في `server.py` | بعد S2 |
| **S4** | Hooks: إضافة `schedule_job()` في trigger points (accept_appointment، create_appointment، ...) | بعد S3 |
| **S5** | Integration tests: job creation + execution + idempotency + retry | بعد S4 |
| **S6** | Observability: admin endpoint لعرض `scheduler_jobs` + status dashboard | بعد S5 |

---

## 9. Constraints (قواعد دائمة)

```
❌ لا scheduler code في server.py أو auth.py حتى قرار صريح
❌ لا background threads أو asyncio.create_task لـ scheduled work
❌ لا cron configuration أو external cron setup حتى قرار صريح
❌ لا endpoints جديدة لـ scheduler حتى قرار صريح (حتى /internal/*)
❌ لا تغيير في schema (لا scheduler_jobs table) حتى قرار صريح
❌ لا notifications hooks زمنية حتى Scheduler مُنفَّذ ومُختبَر
❌ لا WebSocket أو Push للإشعارات الزمنية
❌ لا تغيير في Appointments runtime أو status machine بسبب scheduler
❌ X-User-Id محظور في أي scheduler endpoint
❌ كل الصلاحيات من JWT / verify_token أو secret token للـ internal endpoint
```

```
✅ at-request-time computation (_appt_computed_status, _eff_status) مقبول كحل مؤقت للعرض
✅ schema يبقى بدون scheduler_jobs حتى S1
✅ هذا الملف يُحدَّث عند اتخاذ أي قرار في S0
✅ كل trigger point موثَّق في §2 — ينتظر S4
```

---

## 10. S0 Tooling Decision — قرار مكتمل

> **S0 مكتمل — docs-only.** القرار موثَّق أدناه. لا كود أُضيف، لا schema تغيَّر، لا endpoints جديدة.
> التنفيذ يبدأ من S1 بموافقة صريحة.

---

### الخيارات المدروسة (5 خيارات)

---

#### الخيار 1 — External Cron + Secure Endpoint

**كيف يعمل؟**
خدمة cron خارجية (GitHub Actions، cron-job.org، Render Cron) تستدعي HTTP endpoint محمياً داخل FastAPI كل 60 ثانية. الـ endpoint يستعلم `scheduler_jobs` بـ `FOR UPDATE SKIP LOCKED`، ينفذ الـ jobs المستحقة، ويُحدِّث حالتها في DB.

**المزايا:**
- التطبيق يبقى stateless — الـ runner خارجي منفصل عن الـ web process
- Jobs محفوظة في DB → لا ضياع عند dyno restart أو cron miss
- بسيط: لا process إضافية، لا مكتبات Python جديدة في requirements.txt
- يندمج مثالياً مع `scheduler_jobs` table (Option D)
- يمكن اختباره باستقلالية بـ curl أو Postman قبل ربط cron حقيقي

**السلبيات:**
- الـ endpoint يجب حمايته بـ secret token — خطر إذا أُسيء الإعداد
- الحد الأدنى 60 ثانية (معظم الخدمات المجانية) — كافٍ لجميع use cases الحالية
- اعتماد خارجي — لكن مع DB-driven storage، حتى لو فاتت ticks، لا jobs تضيع

**المخاطر الأمنية:**
- الـ endpoint محمي بـ `X-Scheduler-Secret` header (pre-shared secret في env var)
- الخادم يتحقق بـ `hmac.compare_digest(incoming, expected)` — مقاوم لـ timing attacks
- ممنوع JWT (machine-to-machine call، لا user session) — ممنوع X-User-Id (محظور دائماً بـ F17)
- Secret يُخزَّن فقط في Heroku Config Vars، لا في كود المصدر

**الاعتمادية:**
- Storage: عالية جداً — jobs في DB تبقى حتى لو توقف الـ cron
- Timing: متوسطة (1-minute granularity، كافٍ لجميع use cases المخطط لها)
- إذا فاتت ticks: الـ tick التالية تلتقط جميع الـ jobs المتأخرة تلقائياً

**هل يناسب المشروع الحالي؟** ✅ **نعم — الأنسب لـ FastAPI + Heroku + Postgres.**

**هل يحتاج infra إضافية؟** لا — GitHub Actions مجاني للـ repos، cron-job.org مجاني حتى 5 jobs.

**هل يدعم retry/locking/dedupe بسهولة؟** نعم — كل هذا في `scheduler_jobs` table بـ `dedupe_key` UNIQUE + `FOR UPDATE SKIP LOCKED`.

**هل مناسب للإطلاق الأول؟** ✅ نعم.

---

#### الخيار 2 — APScheduler داخل التطبيق (In-Process)

**كيف يعمل؟**
مكتبة `apscheduler` تُشغَّل داخل نفس FastAPI process. `BackgroundScheduler` أو `AsyncIOScheduler` يعمل في background thread أو coroutine ويُشغِّل jobs بفترات محددة مباشرةً داخل العملية.

**المزايا:**
- لا حاجة لخدمات خارجية — مكتفٍ بذاته
- يمكنه التشغيل بدقة sub-minute (ثوانٍ وليس دقائق)
- لا تكلفة dyno إضافية

**السلبيات:**
- يربط دورة حياة الـ scheduler بدورة حياة الـ web process تماماً
- Heroku يُعيد تشغيل الدينوات يومياً → jobs قد تُقاطع أو تُفقد وسط التنفيذ إذا استُخدمت MemoryJobStore
- إذا كان هناك dyno ثانٍ (scaling) → scheduler يعمل على كلاهما → تنفيذ مزدوج للـ jobs
- APScheduler لديه schema خاص به (إذا استُخدم SQLAlchemy jobstore) → يتعارض مع `scheduler_jobs` الذي صمّمناه

**المخاطر الأمنية:**
- لا endpoint خارجي — لكن فشل في التحكم بـ thread يمكن أن يُعطل الـ API server
- MemoryJobStore (الافتراضي): jobs تُفقد عند restart = silent failure (يخالف F9)

**الاعتمادية:**
- منخفضة على Heroku: daily dyno restarts = تهديد حقيقي ومستمر
- مع SQLAlchemy jobstore → متوسطة، لكن يضيف تعقيداً وتعارضاً مع `scheduler_jobs`

**هل يناسب المشروع الحالي؟** ❌ **لا يُنصح به للإنتاج على Heroku.**

**هل يحتاج infra إضافية؟** لا dyno، لكن يُضيف `apscheduler` لـ requirements.txt.

**هل يدعم retry/locking/dedupe بسهولة؟** لا — يحتاج تخصيصاً كثيراً ويتعارض مع `scheduler_jobs`.

**هل مناسب للإطلاق الأول؟** ❌ لا — خطر الـ silent failure على Heroku غير مقبول (F9).

---

#### الخيار 3 — Background Worker منفصل (Separate Dyno)

**كيف يعمل؟**
Script منفصل (`worker.py`) يعمل كـ Heroku Worker Dyno مستقل. يستطلع `scheduler_jobs` كل N ثوانٍ بـ `FOR UPDATE SKIP LOCKED` وينفذ الـ jobs المستحقة مباشرةً من DB.

**المزايا:**
- منفصل تماماً عن الـ web server — crash في أحدهما لا يؤثر على الآخر
- يدعم `scheduler_jobs` table بشكل مثالي دون تعارض
- يمكن scale مستقلاً
- دقة عالية: sub-minute (يستطلع كل 15–30 ثانية)

**السلبيات:**
- يتطلب Heroku Worker Dyno إضافياً → تكلفة إضافية (~$7+/شهر لـ eco dyno)
- تعقيد deployment إضافي (Procfile يحتاج `worker:` entry)
- يحتاج DB connection pool مستقل للـ worker process

**المخاطر الأمنية:**
- منخفضة — Worker يتصل مباشرة بـ DB، لا HTTP endpoint خارجي
- Race conditions بين workers متعددة محلولة بـ `FOR UPDATE SKIP LOCKED`

**الاعتمادية:**
- عالية — process مستقل، jobs في DB، لا يتأثر بـ web server restarts

**هل يناسب المشروع الحالي؟** ⚠️ **جيد معمارياً، لكن تكلفة إضافية غير مبررة للإطلاق الأول.**

**هل يحتاج infra إضافية؟** نعم — Worker Dyno إضافي على Heroku.

**هل يدعم retry/locking/dedupe بسهولة؟** ✅ نعم — مباشرةً من `scheduler_jobs`.

**هل مناسب للإطلاق الأول؟** ⚠️ فقط إذا كانت الميزانية تسمح. يُنصح به كترقية لاحقة.

---

#### الخيار 4 — Platform Scheduler (Heroku Scheduler Add-on)

**كيف يعمل؟**
Heroku Scheduler Add-on يُشغِّل one-off dynos بفترات ثابتة: كل 10 دقائق، كل ساعة، أو كل يوم. يُنفِّذ script Python يتصل بـ DB.

**المزايا:**
- تكامل native مع Heroku — لا اعتماد على خدمات خارجية
- إعداد بسيط جداً من Heroku Dashboard
- يعمل في نفس بيئة التطبيق

**السلبيات:**
- الحد الأدنى **10 دقائق** — غير مقبول لـ appointment reminders (المطلوب ≤ 1 دقيقة)
- "Best-effort" — Heroku يُصرّح صراحةً بعدم ضمان وقت التنفيذ
- يُشغِّل one-off dynos → يستهلك dyno hours من خطة الاشتراك

**المخاطر الأمنية:**
- لا endpoint خارجي — لكن one-off dyno يأخذ permissions كاملة للـ app

**الاعتمادية:**
- منخفضة جداً للمهام الحساسة للوقت — best-effort بدون SLA

**هل يناسب المشروع الحالي؟** ⚠️ **فقط للمهام غير الحساسة للوقت** (أرشفة يومية، تنظيف أسبوعي). **غير مناسب إطلاقاً لـ appointment reminders**.

**هل يحتاج infra إضافية؟** Heroku Scheduler add-on (مجاني).

**هل يدعم retry/locking/dedupe بسهولة؟** فقط بالجمع مع `scheduler_jobs` table.

**هل مناسب للإطلاق الأول؟** ❌ لـ appointment reminders — ⚠️ لـ non-critical daily jobs.

---

#### الخيار 5 — Manual/Admin Trigger (للاختبار فقط — ليس للإنتاج)

**كيف يعمل؟**
Endpoint admin-only يُشغِّل `run_due_jobs()` يدوياً عند استدعائه. Admin يستدعيه من لوحة التحكم أو curl لاختبار الـ job handlers خلال مراحل التطوير (S1–S4).

**المزايا:**
- صفر infra إضافية
- مفيد جداً خلال S1–S4 للتحقق من handlers قبل ربط cron حقيقي
- يُسرِّع دورة التطوير — لا انتظار لـ cron tick

**السلبيات:**
- ليس scheduler حقيقي — jobs لا تُنفَّذ تلقائياً أبداً
- غير صالح للإنتاج بأي حال

**المخاطر الأمنية:**
- يجب حمايته بـ X-Admin-Token حصراً — إذا أُسيء الإعداد، أي شخص قد يُشغِّل job execution
- يجب تعطيله أو إزالته قبل الإطلاق الفعلي

**الاعتمادية:** لا ينطبق — أداة تطوير فقط.

**هل يناسب المشروع الحالي؟** ❌ **للاختبار في S1–S4 فقط — ليس للإنتاج بأي شكل.**

**هل يحتاج infra إضافية؟** لا.

**هل مناسب للإطلاق الأول؟** ❌ لا.

---

### جدول المقارنة — S0 Summary

| المعيار | 1. External Cron | 2. APScheduler | 3. Worker Dyno | 4. Heroku Scheduler | 5. Admin Trigger |
|---------|----------------|----------------|----------------|---------------------|-----------------|
| الدقة الزمنية | ⚠️ ≥1 دقيقة | ✅ sub-minute | ✅ sub-minute | ❌ ≥10 دقائق | ❌ يدوي |
| Crash safety | ✅ jobs في DB | ❌ in-memory/تعارض | ✅ jobs في DB | ⚠️ best-effort | ✅ jobs في DB |
| تكلفة إضافية | ✅ لا | ✅ لا | ⚠️ dyno إضافي | ✅ لا | ✅ لا |
| أمان الـ endpoint | ⚠️ secret token | N/A | N/A (DB direct) | N/A | ⚠️ admin-only |
| مناسب لـ Heroku | ✅ | ❌ restarts | ⚠️ + تكلفة | ⚠️ non-critical فقط | للاختبار فقط |
| يدعم scheduler_jobs | ✅ | ❌ يتعارض | ✅ | ✅ (بالجمع معه) | ✅ |
| retry/locking/dedupe | ✅ من الجدول | ❌ يحتاج تخصيص | ✅ | ✅ (بالجمع) | ✅ |
| مناسب للإطلاق الأول | ✅ | ❌ | ⚠️ | ❌ | ❌ |

---

### التوصية النهائية لـ S0

**القرار النهائي: الخيار 1 — External Cron + Secure Endpoint**
مع `scheduler_jobs` table (Option D من §4) كطبقة تخزين تُنفَّذ في S1.

#### لماذا هذا الخيار؟

1. **التخزين والـ runner مستقلان:** `scheduler_jobs` يخزّن الـ jobs (S1). الـ cron هو runner يستعلم الجدول فقط. يمكن استبدال الـ cron لاحقاً (بـ Worker Dyno مثلاً) دون تغيير الـ schema أو الـ job handlers.

2. **Heroku restarts يومياً:** APScheduler داخل نفس الـ process = مخاطرة حقيقية بـ silent job loss عند كل restart. External Cron لا يتأثر — الـ jobs في DB دائماً.

3. **صفر تكلفة إضافية:** لا Worker Dyno. GitHub Actions مجاني. cron-job.org مجاني.

4. **بسيط للتطوير والاختبار:** خلال S3، الـ endpoint يمكن استدعاؤه يدوياً بـ curl مع الـ secret لاختبار `run_due_jobs()` قبل ربط الـ cron الحقيقي.

5. **قابل للترقية:** إذا احتجنا sub-minute precision مستقبلاً، نُضيف Worker Dyno (الخيار 3) دون تغيير أي شيء في `scheduler_jobs` أو الـ job handlers.

#### لماذا لم نختر APScheduler (الخيار 2)؟

- **Heroku daily restarts = silent job loss** مع MemoryJobStore (الافتراضي) — يخالف F9
- **Two dynos = double execution** — المنصة قد تُشغِّل dyno ثانٍ عند الضغط دون تنسيق
- **Schema conflict** — APScheduler مع SQLAlchemy jobstore يستخدم جداوله الخاصة مما يُعارض `scheduler_jobs`
- **Tight coupling** — failure في web server = failure في scheduler بشكل مباشر

#### كيف سنحمي الـ endpoint في S3؟

```python
# مخطط التنفيذ في S3 (لم يُنفَّذ بعد في هذا PR):
import hmac, os

SCHEDULER_SECRET = os.getenv("SCHEDULER_SECRET", "")

@app.post("/internal/run-due-jobs")
def run_due_jobs_endpoint(request: Request):
    incoming = request.headers.get("X-Scheduler-Secret", "")
    if not SCHEDULER_SECRET or not hmac.compare_digest(incoming, SCHEDULER_SECRET):
        raise HTTPException(401, "Unauthorized")
    result = run_due_jobs()  # يُشغِّل الـ jobs المستحقة من scheduler_jobs
    return {"ok": True, "data": result}
```

- Secret في Heroku Config Vars فقط — لا في كود المصدر أبداً
- `hmac.compare_digest` — يمنع timing attacks (F17)
- ممنوع JWT لهذا الـ endpoint (machine-to-machine call، لا user)
- ممنوع X-User-Id (محظور دائماً — F6 + F17)
- الـ endpoint prefix `/internal/` يوضّح أنه غير مخصص للعملاء

#### كيف سيمنع الـ scheduler double-run؟

طبقتان تُنفَّذان في S1–S3:
1. **`FOR UPDATE SKIP LOCKED`** في استعلام الـ jobs: إذا كانت تيكتان cron متزامنتان (نادر)، كل واحدة تأخذ rows مختلفة — لا تعارض
2. **`dedupe_key` UNIQUE** في `scheduler_jobs`: يمنع إدراج نفس الـ job مرتين في المصدر (عند `schedule_job()`)

#### كيف سيستخدم scheduler_jobs في S1–S4؟

```
S1: CREATE TABLE scheduler_jobs في auth.py (migration)
S2: schedule_job(job_type, payload, run_at, dedupe_key) helper في auth.py
S3: run_due_jobs() + POST /internal/run-due-jobs (protected)
S4: Hooks في appointment actions:
    - accept_appointment   → schedule_job('appointment_reminder', ...)
    - accept_appointment   → schedule_job('appointment_missed', ...)
    - create_appointment   → schedule_job('appointment_deadline_expire', ...)
    - create/post_job      → schedule_job('job_expiring_soon', ...)
```

#### ما الذي يبقى مؤجلاً إلى S1 (لم يُنفَّذ هنا)؟

```
مؤجل إلى S1+:
- جدول scheduler_jobs (migration في auth.py)
- helper schedule_job()
- endpoint /internal/run-due-jobs
- أي hooks في appointment / notification code
- أي cron configuration أو SCHEDULER_SECRET في env

منجز في S0 (هذا الـ PR — docs-only):
✅ قرار الأداة: External Cron + scheduler_jobs
✅ توثيق حماية الـ endpoint: X-Scheduler-Secret + hmac.compare_digest
✅ توثيق منع double-run: FOR UPDATE SKIP LOCKED + dedupe_key UNIQUE
✅ توثيق integration path كامل (S1–S4)
✅ رفض APScheduler بأسباب موثَّقة
```

---

*S0 Tooling Decision مكتمل — 2026-07-11 — docs-only (PR: scheduler-s0-tooling-decision).*

---

## 11. S1 Schema — مكتملة

> **S1 مكتملة.** تم إضافة migration فقط. لا endpoints، لا runner، لا helpers، لا hooks.

### ما تم في S1 (هذا الـ PR)

```
✅ _migrate_scheduler_jobs() في auth.py — idempotent CREATE TABLE IF NOT EXISTS
✅ ربط Migration في on_startup() بنفس نمط migrations الموجودة (❌ + raise عند الفشل)
✅ scheduler_jobs table بجميع الأعمدة: id, job_type, payload, run_at, status, attempts,
   max_attempts, last_error, dedupe_key, locked_at, locked_by, created_at, updated_at
✅ Constraints: uq_sched_dedupe (UNIQUE dedupe_key), ck_sched_status, ck_sched_attempts, ck_sched_maxatt
✅ 4 indexes: idx_sched_due (status+run_at), idx_sched_locked_at, idx_sched_job_type, idx_sched_created
```

### Schema المُنفَّذ فعلياً (S1)

```sql
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id           BIGSERIAL PRIMARY KEY,
    job_type     TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_at       TIMESTAMPTZ NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error   TEXT,
    dedupe_key   TEXT NOT NULL,
    locked_at    TIMESTAMPTZ,
    locked_by    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sched_dedupe   UNIQUE (dedupe_key),
    CONSTRAINT ck_sched_status   CHECK (status IN ('pending','running','done','failed','cancelled')),
    CONSTRAINT ck_sched_attempts CHECK (attempts >= 0),
    CONSTRAINT ck_sched_maxatt   CHECK (max_attempts >= 1)
);

CREATE INDEX IF NOT EXISTS idx_sched_due       ON scheduler_jobs(status, run_at);
CREATE INDEX IF NOT EXISTS idx_sched_locked_at ON scheduler_jobs(locked_at);
CREATE INDEX IF NOT EXISTS idx_sched_job_type  ON scheduler_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_sched_created   ON scheduler_jobs(created_at DESC);
```

### ما يبقى مؤجلاً (S2+)

```
مؤجل إلى S2:  schedule_job(job_type, payload, run_at, dedupe_key) helper في auth.py
مؤجل إلى S3:  run_due_jobs() + POST /internal/run-due-jobs endpoint
مؤجل إلى S4:  Hooks في appointment/notification trigger points
مؤجل إلى S5:  Integration tests
مؤجل إلى S6:  Admin observability endpoint
```

الجدول يُنشأ عند startup لكنه لا يُقرأ ولا يُكتب فيه حتى S2. لا تأثير على runtime behavior الحالي.

---

*S1 مكتملة — 2026-07-11 — schema-only (PR: scheduler-s1-schema).*

---

## 12. S2 Helper — مكتملة

> **S2 مكتملة.** تم إضافة `schedule_job()` helper فقط. لا endpoints، لا runner، لا hooks، لا cron.

### ما تم في S2 (هذا الـ PR)

```
✅ schedule_job() في auth.py — idempotent INSERT helper
✅ Input validation: job_type غير فارغ، payload dict، dedupe_key غير فارغ، max_attempts >= 1
✅ Idempotency: INSERT ... ON CONFLICT (dedupe_key) DO NOTHING RETURNING
✅ created=True إذا INSERT جديد، created=False إذا dedupe_key موجود مسبقاً
✅ Return shape: {id, job_type, run_at, status, dedupe_key, created_at, created}
✅ payload مُخزَّن كـ JSONB عبر json.dumps + ::jsonb cast
✅ لا تنفيذ jobs، لا notifications، لا تغيير في appointments/jobs tables
```

### Contract النهائي

```python
schedule_job(
    job_type: str,      # Non-empty. e.g. 'appointment_reminder'
    payload: dict,      # JSON-serializable. e.g. {'appointment_id': 42, 'hours_before': 1}
    run_at,             # datetime (UTC). e.g. datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
    dedupe_key: str,    # Non-empty unique string. e.g. 'appointment_reminder:42:1:7'
    max_attempts: int = 5
) -> dict
```

### Input Validation (تُطبَّق قبل لمس DB)

| الحقل | القاعدة | الخطأ |
|-------|---------|-------|
| `job_type` | `isinstance(str) and strip() != ''` | `ValueError` |
| `payload` | `isinstance(dict)` | `ValueError` |
| `dedupe_key` | `isinstance(str) and strip() != ''` | `ValueError` |
| `max_attempts` | `isinstance(int) and >= 1` | `ValueError` |

### Idempotency Behavior

```
INSERT ... ON CONFLICT (dedupe_key) DO NOTHING RETURNING id, ...
    ↓
RETURNING has rows?
    Yes → newly inserted → {"created": True, ...}
    No  → conflict hit  → SELECT by dedupe_key → {"created": False, ...}
```

**لماذا DO NOTHING وليس DO UPDATE؟**
- `DO NOTHING` لا يلمس job موجود بأي حالة (pending/running/done/failed/cancelled)
- `DO UPDATE` قد يُعيد كتابة `run_at` أو `payload` على job قيد التنفيذ → خطر
- المُتصل يتحقق من `created=False` ويقرر ما إذا كان يريد اتخاذ إجراء

### Return Shape

```json
{
  "id":         42,
  "job_type":   "appointment_reminder",
  "run_at":     "2026-07-11T09:00:00+00:00",
  "status":     "pending",
  "dedupe_key": "appointment_reminder:10:1:7",
  "created_at": "2026-07-11T08:00:00+00:00",
  "created":    true
}
```

### ما يبقى مؤجلاً (S3+)

```
مؤجل إلى S3:  run_due_jobs() + POST /internal/run-due-jobs endpoint
مؤجل إلى S4:  Hooks في appointment/notification trigger points
مؤجل إلى S5:  Integration tests
مؤجل إلى S6:  Admin observability endpoint
```

`schedule_job()` يمكن استدعاؤه الآن لكن لا job سيُنفَّذ حتى S3.

---

*S2 مكتملة — 2026-07-11 — helper-only (PR: scheduler-s2-helper).*

---

## 13. S3 Runner + Secure Endpoint — مكتملة

> **S3 مكتملة.** تم إضافة runner + endpoint فقط. لا hooks، لا cron config.

### ما تم في S3 (هذا الـ PR)

```
✅ _execute_scheduler_job(job) في auth.py — handler dispatcher
   - 'noop': ينجح فوراً، لا side effects (للاختبار)
   - unknown job_type: يرفع ValueError (يُعامَل كـ handler failure)
   - لا eval، لا dynamic import
✅ run_due_scheduler_jobs(limit, runner_id) في auth.py — runner
   - Two-phase strategy: Phase 1 (short tx: pick+mark running) + Phase 2 (execute+update)
   - SELECT FOR UPDATE SKIP LOCKED — آمن للتوازي
   - attempts += 1 عند التقاط الـ job
   - Success → done | Retryable → pending | Exhausted → failed
   - limit مُقيَّد [1, 50]، default 20
✅ SCHEDULER_SECRET = os.environ.get("SCHEDULER_SECRET", "") في server.py
✅ POST /internal/run-due-jobs في server.py
   - X-Scheduler-Secret header + hmac.compare_digest (timing-attack safe)
   - 503 إذا SCHEDULER_SECRET غير مضبوط
   - 403 إذا secret ناقص أو خاطئ
   - لا JWT، لا X-User-Id، لا user session
```

### Endpoint Contract

```
POST /internal/run-due-jobs
Auth: X-Scheduler-Secret: <secret>  (machine-to-machine only)
Query: ?limit=20 (optional, clamped 1–50)

Response 200 — all final UPDATEs succeeded:
{
  "ok": true,
  "picked": 3,
  "done": 2,
  "failed": 1,
  "retried": 0,
  "update_failed": 0,
  "stuck_running": 0,
  "runner_id": "runner-1234",
  "jobs": [
    {"id": 1, "job_type": "noop", "status": "done"},
    ...
  ]
}

Response 200 — some final UPDATEs failed (jobs stuck in 'running'):
{
  "ok": false,
  "picked": 3,
  "done": 2,
  "failed": 0,
  "retried": 0,
  "update_failed": 1,
  "stuck_running": 1,
  "runner_id": "runner-1234",
  "jobs": [
    {"id": 1, "job_type": "noop", "status": "done"},
    {"id": 2, "job_type": "noop", "status": "update_failed"}
  ]
}

Response 403: secret wrong/missing
Response 503: SCHEDULER_SECRET env var not set
Response 500: Phase 1 (pick+mark) error (logged server-side)
```

### Locking Strategy

```sql
-- Phase 1 (inside BEGIN/COMMIT):
SELECT id, job_type, payload, max_attempts, attempts
FROM scheduler_jobs
WHERE status = 'pending' AND run_at <= NOW()
ORDER BY run_at ASC
LIMIT :limit
FOR UPDATE SKIP LOCKED;

-- Mark running (inside same tx):
UPDATE scheduler_jobs
SET status='running', attempts=attempts+1,
    locked_at=NOW(), locked_by=:runner_id, updated_at=NOW()
WHERE id = :id;

-- Phase 2 (auto-committed per statement, via _update_scheduler_job_final_status):
UPDATE scheduler_jobs
SET   status='done'|'pending'|'failed', locked_at=NULL, locked_by=NULL,
      last_error=<msg|NULL>, updated_at=NOW()
WHERE id = :id
  AND status = 'running'         -- guard: only update if still ours
  AND locked_by = :runner_id     -- guard: verify ownership
RETURNING id;                    -- zero rows → failure (lock stolen or state mismatch)
```

**Final UPDATE is considered successful only when RETURNING returns one row.**
- Zero rows → `update_failed++`, `ok=false` in response.
- Exception → `update_failed++`, `ok=false` in response.
- Either failure path is logged clearly; no error is swallowed.

### Retry Logic

| الحالة | الشرط | النتيجة | ok |
|--------|-------|---------|-----|
| نجاح + UPDATE ok | handler لم يرفع، UPDATE نجح | `status='done'` | true |
| فشل قابل + UPDATE ok | `new_attempts < max_attempts`، UPDATE نجح | `status='pending'`, `last_error` محفوظ | true |
| فشل منتهٍ + UPDATE ok | `new_attempts >= max_attempts`، UPDATE نجح | `status='failed'`, `last_error` محفوظ | true |
| أي حالة + UPDATE فشل | final UPDATE رفع exception | `status='running'` يبقى (stuck)، `update_failed++` | **false** |

`new_attempts = old_attempts + 1` (القيمة بعد الـ increment في Phase 1)

**قاعدة دائمة:** `done / failed / retried` تُحسَب فقط بعد نجاح الـ UPDATE الأخير.
إذا فشل أي final UPDATE → `"ok": false` في الـ response ← المرسِل يتعامل معها.

### Job Types المدعومة (S3)

| job_type | السلوك |
|----------|--------|
| `noop` | ينجح فوراً، لا side effects، للاختبار فقط |
| أي نوع آخر | `ValueError` → failure → retry/fail عادي |

S4 سيضيف: `appointment_reminder`, `appointment_deadline_expire`, `appointment_missed`, `job_expiring_soon`

### حد Secret

```
✅ SCHEDULER_SECRET من env var فقط — لا في source code
✅ hmac.compare_digest — مقاوم لـ timing attacks
✅ لا يُطبع في logs، لا يُرجع في responses
❌ ممنوع: JWT للـ endpoint
❌ ممنوع: X-User-Id
❌ ممنوع: secret في query params أو request body
```

### ما يبقى مؤجلاً (S5+)

```
مؤجل إلى S5:  Integration tests
مؤجل إلى S6:  Admin observability endpoint
```

---

*S3 مكتملة — 2026-07-11 — runner + endpoint (PR: scheduler-s3-runner).*

---

## 14. S4 Domain Handlers + Scheduling Hooks — مكتملة

**PR:** `scheduler-s4-domain-handlers`  
**تاريخ:** 2026-07-11 (fix: stale-detection + retry-raise + DB-owned company_id)

### الهدف

إضافة handlers حقيقية للـ job types الأربعة، وربطها بـ trigger points في كود الـ appointments والـ jobs. S3 كانت تعمل مع `noop` فقط — S4 تكمل الدورة.

### التغييرات

#### `auth.py`

**`_SCHEDULER_HANDLERS`** مُحدَّث ليشمل الأنواع الأربعة:

```python
_SCHEDULER_HANDLERS = {
    "noop",
    "appointment_reminder",
    "appointment_deadline_expire",
    "appointment_missed",
    "job_expiring_soon",
}
```

**4 Handler Functions** — كل handler:
- يقرأ حالة DB قبل الفعل (idempotent — double-fire آمن)
- يُحرر الـ conn قبل استدعاء `create_notification`
- يرفع `ValueError` إذا كان الـ payload ناقصاً
- لا يبتلع exceptions بصمت

| Handler | المحفّز | الشرط قبل الفعل | الفعل |
|---------|---------|---------------|-------|
| `_handle_appointment_reminder` | run_at = scheduled_at - 24h | `status == 'confirmed'` + stale check | إشعار لـ company + applicant |
| `_handle_appointment_deadline_expire` | run_at = response_deadline_at | `status == 'pending_response'` AND `NOW() >= deadline` + stale check | `UPDATE ... SET status='expired' RETURNING id` + إشعار للشركة |
| `_handle_appointment_missed` | run_at = scheduled_at + 15min | `status == 'confirmed'` AND `NOW() >= scheduled_at + 15min` + stale check | `UPDATE ... SET status='missed' RETURNING id` + إشعار للطرفين |
| `_handle_job_expiring_soon` | run_at = expires_at - 48h | `job.status == 'active'` (paused مستثنى) + stale check | إشعار للشركة (company_id من DB) |

**`_execute_scheduler_job`** مُحدَّث — branches صريحة لكل handler.

**Scheduling Hooks** — غير fatal (try/except مع print):

| Function | Job Scheduled | Dedupe Key | run_at |
|----------|--------------|-----------|--------|
| `accept_appointment` | `appointment_reminder` | `appointment_reminder:{appt_id}:{sched_ts}` | `scheduled_at - 24h` (إذا > NOW) |
| `accept_appointment` | `appointment_missed` | `appointment_missed:{appt_id}:{sched_ts}` | `scheduled_at + 15min` |
| `send_appointment` | `appointment_deadline_expire` | `appointment_deadline_expire:{appt_id}:{dl_ts}` | `deadline_dt` |
| `reschedule_appointment` | `appointment_deadline_expire` | `appointment_deadline_expire:{appt_id}:{dl_ts}` | new `deadline_dt` |
| `add_job` | `job_expiring_soon` | `job_expiring_soon:{job_id}:{exp_ts}` | `expires_at - 48h` (إذا > NOW) |

ملاحظات الـ dedupe (محدَّثة — stale-job protection):
- جميع المفاتيح تحتوي على **epoch-seconds timestamp** يرتبط بالقيمة المجدولة.
- عند reschedule: `dl_ts` الجديد → dedupe key مختلف → job جديد آمن. الـ job القديم يُشغَّل لكن يكتشف handler الـ stale عبر `_ts_from_db_val`.
- `job_expiring_soon`: payload يحتوي `job_id + expected_expires_at_ts` فقط — **بدون `company_id`** (F21/F6: backend يقرأه من DB).
- `sched_ts`, `dl_ts`, `exp_ts` = epoch seconds (UTC)، وليس تقريب الدقيقة.

**`add_job` restructured**: `return result` نُقل خارج الـ `try` block لتمكين الـ scheduling بعد `release_conn`.

### الإيديمبوتنسية (F22)

- **Handlers**: كل handler يقرأ `status` من DB ويعود فوراً إذا لم يعد الشرط متحققاً (إذا تغيّرت الحالة يدوياً أو بـ handler سابق).
- **DB transitions**: `UPDATE ... WHERE status='X' RETURNING id` — يضمن أن التحديث يحدث مرة واحدة فقط. Zero rows = لا فعل.
- **Notifications**: `event_key` + `ON CONFLICT DO NOTHING` في `create_notification`.
- **Hooks**: `ON CONFLICT (dedupe_key) DO NOTHING` في `schedule_job` — تكرار الاستدعاء لا يُنشئ job مكرر.

### Stale-Job Detection

كل handler يقارن timestamp الـ payload مع القيمة الحالية في DB قبل أي فعل:

```python
# helper مشترك
def _ts_from_db_val(val) -> int:
    """Convert DB datetime (ISO string or datetime) to UTC epoch seconds."""
    ...

# مثال داخل handler
if sched_ts_payload is not None:
    db_val = appt.get("scheduled_at")
    if db_val and _ts_from_db_val(db_val) != int(sched_ts_payload):
        return  # stale — safe no-op
```

إذا اختلف الـ timestamp → reschedule حدث بعد الجدولة → safe no-op (لا transition، لا notification).

### Notification Failure Handling (No Silent Swallowing)

- **Dual-party handlers** (`appointment_reminder`, `appointment_missed`): يحاول إرسال الإشعار لكلا الطرفين، يجمع الأخطاء، يرفع `errors[0]` في النهاية إذا فشل أي طرف. الـ runner يُعيد المحاولة. `event_key` يمنع الإشعارات المكررة.
- **Single-party handlers** (`appointment_deadline_expire`, `job_expiring_soon`): `except ... raise` مباشرة.
- **Retry safety**: إذا نجح الـ DB transition لكن فشل الـ notification (أول محاولة) → في المحاولة التالية: `already_expired` / `already_missed` flag يتخطى التحويل ويُعيد محاولة الإشعار فقط.

### ما بقي مؤجلاً

```
مؤجل إلى S6:  Admin observability — تفاصيل scheduler في admin panel
```

---

## 15. S5 Minimal Runtime QA — مكتملة

**PR:** `scheduler-s5-minimal-runtime-qa`  
**تاريخ:** 2026-07-11

5 runtime checks (§179) تُشغَّل بـ `unittest.mock` بدون DB حقيقي:

| # | الحالة | النتيجة |
|---|--------|--------|
| 179-01 | noop: `_execute_scheduler_job` يكتمل بدون DB | ✅ |
| 179-02 | unknown job type → `ValueError` يذكر النوع | ✅ |
| 179-03 | endpoint security: no-secret→503, wrong→403, correct→runner | ✅ |
| 179-04 | dedupe: نفس `dedupe_key` مرتين → `created=False` في الثانية | ✅ |
| 179-05 | stale domain job: timestamp payload مختلف → safe no-op، no notification | ✅ |

**طريقة الاختبار:** import auth.py مباشرة + `patch('auth.get_conn')` + `patch('auth.create_notification')` للتحقق من السلوك بدون اتصال DB. server.py يُستورد ويُختبر endpoint مباشرة مع mock Request.

---

## Source of Truth

| العنصر | الحالة | المرجع |
|--------|--------|--------|
| Scheduler schema | ✅ S1 | `auth.py → _migrate_scheduler_jobs()` |
| schedule_job helper | ✅ S2 | `auth.py → schedule_job()` |
| Runner | ✅ S3 | `auth.py → run_due_scheduler_jobs()` |
| Secure endpoint | ✅ S3 | `server.py → POST /internal/run-due-jobs` |
| Domain handlers (4) | ✅ S4 | `auth.py → _handle_appointment_reminder` / `_deadline_expire` / `_missed` / `_handle_job_expiring_soon` |
| Scheduling hooks (5) | ✅ S4 | `auth.py → accept_appointment` / `send_appointment` / `reschedule_appointment` / `add_job` |
| Runtime QA (5 checks) | ✅ S5 | `test_post_comments.py §179` |
| Proposed schema (docs) | §7 + §11 | هذا الملف |
| S2 contract | §12 | هذا الملف |
| S3 contract | §13 | هذا الملف |
| S4 contract | §14 | هذا الملف |
| Deferred features | موثَّقة | هذا الملف §2 (محدَّث) |
| Appointments deferral | محدَّث | `docs/APPOINTMENTS_PLAN.md` |
| Notifications blocked | محدَّث | `docs/NOTIFICATIONS_PLAN.md` |
| System index entry | مضاف + محدَّث | `docs/SYSTEMS_INDEX.md §37` |
| Runtime QA | ✅ S5 | `test_post_comments.py §179` |
| Admin observability | 🔜 S6 | — |

---

*أُنشئ: 2026-07-11 — Architecture Decision Document (PR: scheduler-infrastructure-decision). S0 توثيق (PR: scheduler-s0-tooling-decision). S1 schema (PR: scheduler-s1-schema). S2 helper (PR: scheduler-s2-helper). S3 runner (PR: scheduler-s3-runner). S4 handlers + hooks (PR: scheduler-s4-domain-handlers).*
