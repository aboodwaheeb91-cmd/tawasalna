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

## Source of Truth

| العنصر | الحالة | المرجع |
|--------|--------|--------|
| Scheduler schema | docs-only — لم يُنفَّذ | هذا الملف §7 |
| Deferred features | موثَّقة | هذا الملف §2 |
| Appointments deferral | موثَّق | `docs/APPOINTMENTS_PLAN.md § Scheduler-Dependent Features` |
| Notifications blocked | موثَّق | `docs/NOTIFICATIONS_PLAN.md § Scheduler Blocker Note` |
| System index entry | مضاف | `docs/SYSTEMS_INDEX.md §37` |
| Implementation decision | ❌ لم يُتَّخذ | موافقة مستخدم مطلوبة |

---

*أُنشئ: 2026-07-11 — Architecture Decision Document — docs-only (PR: scheduler-infrastructure-decision). لا كود، لا schema، لا endpoints. فقط توثيق القرار وإرشادات التنفيذ المستقبلي.*
