# Notifications Full Delivery Plan — تواصلنا

> **هذا الملف هو الخطة المرحلية لنظام الإشعارات. أي تعديل على النظام يجب أن يرجع لهذا الملف أولاً.**
> وجود Phase هنا لا يعني إذناً بتنفيذها — كل Phase تحتاج طلباً صريحاً من المستخدم.

---

## Phase 0 — Audit & Plan (this PR — docs only) ✅

### What exists (audit — 2026-07-09)

| العنصر | الحالة | الملاحظات |
|--------|--------|-----------|
| `notifications` table | ✅ موجود | `id, user_id FK, type, title, body, link, is_read, created_at` — بدون `event_key` أو `actor_id` |
| `create_notification(user_id, type_, title, body, link)` | ✅ موجود في `auth.py` | INSERT بسيط، بلا idempotency |
| `get_notifications(user_id, limit=50)` | ✅ موجود | يفلتر `type != 'message'`، مرتب بـ `created_at DESC` |
| `mark_notifications_read(user_id)` | ✅ موجود | يحدّث الكل دفعة واحدة (bulk only) |
| `get_unread_notifications(user_id)` | ✅ موجود | COUNT حيث `is_read=FALSE AND type != 'message'` |
| `GET /notifications/{user_id}` | ⚠️ موجود لكن معطوب | **بلا JWT** — أي مستخدم يستطيع قراءة إشعارات أي مستخدم آخر |
| `PUT /notifications/{user_id}/read` | ⚠️ موجود لكن معطوب | JWT موجود لكن **لا يتحقق من تطابق user_id مع التوكن** |
| `notifications.html` | ⚠️ موجود لكن معطوب | يستخدم `X-User-Id` (محظور)، بلا Bearer token، `innerHTML` مع بيانات API (XSS) |

### Security bugs found (must fix in Phase 1 before any other work)

| # | الخلل | التأثير |
|---|-------|---------|
| **S1** | `GET /notifications/{user_id}` بلا JWT | أي مستخدم يقرأ إشعارات أي آخر |
| **S2** | `PUT /notifications/{user_id}/read` لا يتحقق من `token.user_id == user_id` | المستخدم يمسح إشعارات غيره |
| **S3** | `notifications.html` يرسل `X-User-Id` بدل Bearer (محظور بموجب CLAUDE.md) | يخترق نمط الأمان الموحد |
| **S4** | `notifications.html` لا يرسل JWT في `fetch('/notifications/...')` | يعتمد على الـ URL فقط |
| **S5** | `notifications.html` يستخدم `innerHTML` مع `n.title` و `n.body` | XSS — المهاجم ينفذ script عبر إشعار |
| **S6** | `create_notification` في report flow: 3 args بدل 4 (`body` مفقود) + `except: pass` | يخالف F9 (No Silent Failures) |

### Missing features (roadmap for Phase 2+)

- لا `event_key` (idempotency) — الإشعار المكرر يُنشأ عدة مرات
- لا `actor_id` — لا معرفة من أرسل الإشعار
- لا `entity_id` / `entity_type` — لا ربط الإشعار بكيان محدد
- لا mark-single-read (فقط bulk mark-all)
- لا pagination
- لا soft delete
- لا hooks في: تعليق / رد / mention / job-apply / follow / verify
- لا unread badge في الهيدر العام (polling)

---

## Architecture Rules (permanent — applies to all phases)

هذه القواعد لا تتغير بين الـ phases:

1. **Backend فقط ينشئ الإشعارات** — frontend لا يقرر recipient ولا ينشئ notification مباشرةً.
2. **JWT Bearer فقط** — ممنوع X-User-Id. كل endpoint يستخدم `Depends(verify_token)`.
3. **المستخدم لا يرى إلا إشعاراته** — الـ endpoint يستخرج `user_id` من التوكن دائماً، ويتجاهل أي `user_id` في الـ URL إن تعارض.
4. **لا WebSocket الآن** — إلا إذا تم حل أمان WebSocket أولاً (P0 Security Debt في SYSTEMS_INDEX §19).
5. **لا realtime/push إلا كـ Phase 11** — وبعد قرار واضح من المستخدم.
6. **`except: pass` محظور** داخل أي transaction أو `create_notification` call (F9).
7. **لا `innerHTML` مع API data** — كل نص من الـ API عبر `textContent` فقط.
8. **Standard response shape:** `{ok, data, error}` موافق F15.
9. **Idempotency via `event_key`** (من Phase 2) — `INSERT ... ON CONFLICT (event_key) DO NOTHING`.
10. **Soft delete** (من Phase 9) — لا hard delete من الـ DB.

---

## Phase 1 — Security Hardening ✅ (منفَّذ في PR #431)

> **مكتمل — جميع ثغرات S1–S6 محلولة.**

### التغييرات المطلوبة

**`server.py`:**
```python
# قبل:
@app.get("/notifications/{user_id}")
def user_notifications(user_id: int):
    ...

# بعد:
@app.get("/notifications/{user_id}")
def user_notifications(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    ...
```

```python
# قبل:
@app.put("/notifications/{user_id}/read")
def read_notifications(user_id: int, token=Depends(verify_token)):
    ...

# بعد — إضافة cross-check:
@app.put("/notifications/{user_id}/read")
def read_notifications(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    ...
```

```python
# إصلاح create_notification في report flow:
# قبل (خطأ — 3 args + except: pass):
try:
    create_notification(
        data.reported_user_id if hasattr(data,'reported_user_id') else 1,
        f"بلاغ جديد: {data.report_type}", "report"
    )
except: pass

# بعد (صحيح — 4 args + logging):
try:
    admin_user_id = 1  # TODO: replace with real admin lookup
    create_notification(admin_user_id, "report", "بلاغ جديد", f"نوع: {data.report_type}")
except Exception as _ne:
    print(f"[TW-WARN] create_notification failed: {_ne}")
```

**`notifications.html`:**
- استبدال `fetch('/notifications/'+_user.id)` بـ `fetch('/notifications/'+_user.id, {headers: {Authorization:'Bearer '+localStorage.getItem('tw_jwt')}})`
- حذف `X-User-Id` من كل `fetch` في الملف
- استبدال `innerHTML` بـ `createElement` + `textContent` لكل بيانات API

---

## Phase 2 — Schema Hardening (Idempotency + Actor) ✅ (منفَّذ في PR #432)

> مكتمل — migration + helper محدَّث.

### DB migration (في `auth.py` داخل `_migrate_*()`)

```sql
ALTER TABLE notifications
  ADD COLUMN IF NOT EXISTS actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS entity_id INTEGER,
  ADD COLUMN IF NOT EXISTS entity_type TEXT,
  ADD COLUMN IF NOT EXISTS event_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_notif_event_key
  ON notifications (user_id, event_key)
  WHERE event_key IS NOT NULL;
```

### تحديث `create_notification` في `auth.py`

```python
def create_notification(
    user_id: int, type_: str, title: str, body: str,
    link: str = "", actor_id: int = None,
    entity_id: int = None, entity_type: str = None,
    event_key: str = None
) -> dict | None:
    """Returns None if event_key already exists (idempotent)."""
    conn = get_conn()
    try:
        rows = conn.run(
            """
            INSERT INTO notifications
              (user_id, type, title, body, link, actor_id, entity_id, entity_type, event_key)
            VALUES
              (:uid, :type, :title, :body, :link, :actor, :eid, :etype, :ekey)
            ON CONFLICT (user_id, event_key) DO NOTHING
            RETURNING id, user_id, type, title, body, link, is_read, created_at
            """,
            uid=user_id, type=type_, title=title, body=body, link=link,
            actor=actor_id, eid=entity_id, etype=entity_type, ekey=event_key
        )
        if not rows:
            return None  # duplicate — idempotent skip
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)
```

### event_key format (standard)

```
{type}:{entity_type}:{entity_id}:{actor_id}
```

أمثلة:
- `comment:post:42:7` — المستخدم 7 علّق على منشور 42
- `reply:comment:15:9` — المستخدم 9 ردّ على تعليق 15
- `mention:comment:18:3` — المستخدم 3 ذكر شخصاً في تعليق 18
- `follow:user:12:5` — المستخدم 5 تابع المستخدم 12
- `job_applied:job:77:14` — المستخدم 14 تقدّم لوظيفة 77
- `verify_approved:verify_request:6:admin` — طلب توثيق رقم 6 تمت الموافقة عليه

---

## Phase 3 — Comment Notification Hook ✅ (منفَّذ في PR #433)

> يُشعر صاحب المنشور عند التعليق عليه.

**Hook location:** `create_company_post_comment()` in `auth.py` — بعد `COMMIT`.

```python
# بعد COMMIT:
if post_owner_id != commenter_id:
    create_notification(
        user_id=post_owner_id,
        type_="comment",
        title="علّق شخص على منشورك",
        body=f"{commenter_name}: {body[:60]}",
        link=f"/u/{company_tw_id}#post-{post_id}",
        actor_id=commenter_id,
        entity_id=comment_id,
        entity_type="comment",
        event_key=f"comment:post:{post_id}:{commenter_id}"
    )
```

**القاعدة:** لا إشعار إذا `post_owner_id == commenter_id` — لا تُشعر نفسك.

---

## Phase 4 — Reply Notification Hook ✅ (منفَّذ في PR #434)

> يُشعر صاحب التعليق عند الرد عليه.

**Hook location:** نفس `create_company_post_comment()` — إضافي على Phase 3.

```python
# إذا reply_to_comment_id موجود وصاحب التعليق الأصلي مختلف:
if reply_to_comment_id and original_author_id != commenter_id:
    create_notification(
        user_id=original_author_id,
        type_="reply",
        title="ردّ شخص على تعليقك",
        body=f"{commenter_name}: {body[:60]}",
        link=f"/u/{company_tw_id}#comment-{reply_to_comment_id}",
        actor_id=commenter_id,
        entity_id=comment_id,
        entity_type="comment",
        event_key=f"reply:comment:{reply_to_comment_id}:{commenter_id}"
    )
```

---

## Phase 5 — @Mention Notification Hook ✅ (منفَّذ في PR #435)

> يُشعر كل مستخدم تم ذكره في تعليق.

**Hook location:** نفس `create_company_post_comment()` — بعد حفظ `company_post_comment_mentions` — داخل نفس الـ transaction.

```python
for tw_id in mentioned_tw_ids:
    mentioned_user = get_user_info_by_tw_id(tw_id)
    if mentioned_user and mentioned_user["id"] != commenter_id:
        create_notification(
            user_id=mentioned_user["id"],
            type_="mention",
            title=f"ذكرك {commenter_name} في تعليق",
            body=body[:60],
            link=f"/u/{company_tw_id}#comment-{comment_id}",
            actor_id=commenter_id,
            entity_id=comment_id,
            entity_type="comment",
            event_key=f"mention:comment:{comment_id}:{mentioned_user['id']}"
        )
```

---

## Phase 6 — Job Application Notification Hook ✅ (منفَّذ في PR #436)

> يُشعر الشركة عند تقدّم موظف لوظيفتها.

**Hook location:** في `server.py` داخل `POST /apply/{job_id}` — بعد نجاح INSERT.

```python
create_notification(
    user_id=company_user_id,
    type_="job_applied",
    title=f"تقدّم شخص لوظيفة {job_title}",
    body=f"{applicant_name} تقدّم للوظيفة",
    link=f"/company-profile#jobs",
    actor_id=applicant_id,
    entity_id=job_id,
    entity_type="job",
    event_key=f"job_applied:job:{job_id}:{applicant_id}"
)
```

---

## Phase 7 — Follow Notification Hook ✅ (منفَّذ في PR #437)

> يُشعر المستخدم عند متابعة شخص له.

**Hook location:** في `server.py` داخل endpoint المتابعة — بعد INSERT في `profile_follows` أو `company_follows`.

```python
if follower_id != followed_id:
    create_notification(
        user_id=followed_id,
        type_="follow",
        title="شخص جديد يتابعك",
        body=f"{follower_name} بدأ بمتابعتك",
        link=f"/u/{follower_tw_id}",
        actor_id=follower_id,
        entity_id=follower_id,
        entity_type="user",
        event_key=f"follow:user:{followed_id}:{follower_id}"
    )
```

---

## Phase 8 — Verification Status Notification Hook ✅ (منفَّذ في PR #438)

> يُشعر المستخدم عند موافقة الأدمن أو رفض طلب التوثيق.

**Hook location:** في `server.py` داخل `PUT /admin/verify/{req_id}` — بعد UPDATE verify_requests.

```python
create_notification(
    user_id=req_owner_id,
    type_="verify",
    title="تم مراجعة طلب توثيقك" if status == "approved" else "طلب توثيقك يحتاج مراجعة",
    body="تمت الموافقة على طلب التوثيق ✅" if status == "approved" else f"ملاحظة: {admin_note}",
    link="/settings",
    entity_id=req_id,
    entity_type="verify_request",
    event_key=f"verify_{status}:verify_request:{req_id}:admin"
)
```

---

## Phase 9 — Per-Notification Read + Pagination ✅ (منفَّذ في PR #439)

> يتيح تحديد إشعار واحد كمقروء ويضيف pagination.

### تغييرات endpoint

**جديد:** `PUT /notifications/{user_id}/read/{notif_id}` — تحديد إشعار واحد كمقروء.

**محدّث:** `GET /notifications/{user_id}?page=1&per_page=20` — مع pagination.

### تغييرات `auth.py`

```python
def mark_notification_read(user_id: int, notif_id: int) -> bool:
    """Mark single notification as read — only if it belongs to user_id."""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE notifications SET is_read=TRUE WHERE id=:nid AND user_id=:uid",
            nid=notif_id, uid=user_id
        )
        return True
    finally:
        release_conn(conn)
```

---

## Phase 10 — Unread Badge in App Header ✅ (منفَّذ في PR #440)

> يعرض عداد الإشعارات غير المقروءة في هيدر كل صفحة.

**الآلية:** polling — `setInterval(() => fetch('/notifications/{user_id}/unread-count'), 60_000)`

**Endpoint جديد:** `GET /notifications/{user_id}/unread-count` — يعيد `{ok: true, data: {count: N}}`

**Frontend:** `static/app-header.js` يستدعي `_pollUnreadBadge()` ويحدّث badge عنصر في `.sc-header`.

**القواعد:**
- لا polling بدون JWT
- polling interval: 60 ثانية كحد أدنى
- إذا `count == 0` → يخفي الـ badge
- لا يخزن الـ count في localStorage

---

## Phase 11 — Real-time / Push Notifications (مؤجل — Intentionally Deferred)

> **هذه المرحلة مؤجلة حتى إشعار آخر. Phase 11 is intentionally deferred and must not start until all three conditions below are met.**

**Conditions before Phase 11 can start:**

1. **WebSocket P0 Security Debt must be resolved first.** `/ws/{user_id}` currently accepts any user_id without JWT verification — this is a P0 security issue (see `SYSTEMS_INDEX.md §18`). Real-time notifications share the same transport risks.
2. **User must explicitly approve.** Choose from: WebSocket (via `/ws/{user_id}` after hardening) · Server-Sent Events (SSE) · Web Push API. No default choice — user decides.
3. **Existing polling V1 (Phases 1–10) must remain stable.** Do not break the current HTTP polling system while building Phase 11.

**Options under consideration (no decision made):**
- **WebSocket** (via `/ws/{user_id}` after hardening): fastest, higher complexity
- **Server-Sent Events (SSE)**: simpler than WS, unidirectional, no extra auth needed
- **Web Push API**: works even when page is closed (requires Service Worker)

**لا تنفيذ لأي خيار حتى يُطلب صراحةً.**

---

---

## Runtime QA Bugfix — 2026-07-10 (PR #444)

> **Bug found during manual QA:** job application and follow notifications were never created in production.

### Root Cause

`create_notification()` in `auth.py` used:

```sql
ON CONFLICT (user_id, event_key) DO NOTHING
```

But the unique index defined in `_migrate_notifications_schema_v2()` is **partial**:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uniq_notif_event_key
  ON notifications (user_id, event_key) WHERE event_key IS NOT NULL
```

PostgreSQL requires `ON CONFLICT` to include the matching `WHERE` predicate when referencing a partial unique index. Without it, the engine raises:

```
ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification
```

This exception was caught by all callers' `try/except` and logged as `[TW-WARN]`, **silently preventing every notification from being created**.

### Fix Applied

One-line change in `create_notification()` (`auth.py` line 2859):

```python
# Before (buggy — fails against partial index):
"ON CONFLICT (user_id, event_key) DO NOTHING "

# After (correct — matches partial index predicate):
"ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING "
```

### Refollow Behavior (by design — documented)

After unfollow + refollow, the `event_key` `follow:user:{company_id}:{follower_id}` is unchanged. The second follow-notification is **silently skipped** (idempotent ON CONFLICT). This is intentional:

- The `if ins_rows:` guard in `follow_company()` ensures the notification block only executes on a **genuine new follow** (when the INSERT returns a row).
- On re-follow, `company_follows ON CONFLICT DO NOTHING` returns empty rows → `ins_rows` is falsy → notification block is skipped entirely → `create_notification` is never called.
- If a different requirement is needed (e.g., notify on refollow after N days), a new `event_key` format would be required. Until then, **refollow does not trigger a second notification — by design**.

### Diagnostic Checklist Applied

| الفحص | النتيجة |
|-------|---------|
| `create_notification` hook in `apply_job` | ✅ موجود — `auth.py:2244` |
| `create_notification` hook in `follow_company` | ✅ موجود — `auth.py:3242` |
| `create_notification` hook in `follow_profile` | ✅ موجود — `auth.py:3950` |
| Recipient for job notification | ✅ `jobs.company_id` = company's `users.id` |
| Recipient for follow notification | ✅ `company_id` via `_resolve_company_id()` |
| `event_key` format for jobs | ✅ `job_applied:job:{job_id}:{applicant_id}` |
| `event_key` format for follows | ✅ `follow:user:{followed_id}:{follower_id}` |
| `_typeMap` has `job_applied` | ✅ `notifications.html` line ~678 |
| `_typeMap` has `follow` | ✅ `notifications.html` line ~679 |
| `_filterGroups` includes `job_applied` in `job` group | ✅ `['job', 'job_applied']` |
| `_filterGroups` includes `follow` in `follow` group | ✅ `['follow']` |
| "all" filter shows both types | ✅ `filterVal === 'all'` shows all |
| Partial unique index predicate correct | ✅ `WHERE event_key IS NOT NULL` |
| ON CONFLICT matches partial index | ✅ **Fixed** — `WHERE event_key IS NOT NULL DO NOTHING` |

---

## Notifications V1 Status

> **Notifications V1 is complete.** All phases 0–10 are implemented and merged. Phase 11 is intentionally deferred.

| Phase | Status | PR |
|-------|--------|----|
| Phase 0 — Audit & Plan | ✅ complete | (docs only) |
| Phase 1 — Security Hardening | ✅ complete | PR #431 |
| Phase 2 — Schema Hardening (event_key, actor_id) | ✅ complete | PR #432 |
| Phase 3 — Comment Notification Hook | ✅ complete | PR #433 |
| Phase 4 — Reply Notification Hook | ✅ complete | PR #434 |
| Phase 5 — Mention Notification Hook | ✅ complete | PR #435 |
| Phase 6 — Job Application Hook | ✅ complete | PR #436 |
| Phase 7 — Follow Hook | ✅ complete | PR #437 |
| Phase 8 — Verification Hook | ✅ complete | PR #438 |
| Phase 9 — Per-Notification Read + Pagination | ✅ complete | PR #439 |
| Phase 10 — Unread Badge in App Header | ✅ complete | PR #440 |
| Phase 11 — Real-time / Push | ⏸ deferred | requires WebSocket P0 fix + user approval |

**Phase 11 — Real-time / Push is intentionally deferred and must not start until:**
1. WebSocket P0 security debt (`/ws/{user_id}` unauthenticated) is resolved.
2. User explicitly approves realtime/push work and chooses transport (WS / SSE / Push API).
3. Existing polling V1 remains stable and is not broken during transition.

---

---

## Notification Coverage Audit

> **تاريخ الـ audit: 2026-07-10 — بناءً على V1 Phase 0–10.**
> هذا الجدول يوثّق كل الأحداث المهمة في النظام وحالة الإشعار لكل منها.
> يُحدَّث عند إضافة نظام جديد أو feature جديدة.

### Status Legend

| الرمز | المعنى |
|-------|--------|
| ✅ impl | منفَّذ في V1 |
| ❌ missing | يجب تنفيذه — غير موجود |
| 🔜 future | مخطط في مراحل لاحقة |
| 🚫 n/a | لا يحتاج إشعار — مبرر واضح |
| ❓ decide | يحتاج قرار قبل التنفيذ |

---

### Area 1 — Posts / Comments / Replies / Mentions

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| علّق شخص على منشورك | commenter → post owner | ✅ impl | `comment` | post `#post-{id}` | V2-4 per post | PR #433 |
| ردّ شخص على تعليقك | replier → comment author | ✅ impl | `reply` | comment thread | V2-4 per thread | PR #434 |
| ذكرك شخص في تعليق (@mention) | commenter → mentioned user | ✅ impl | `mention` | `#comment-{id}` | ❓ needs decision | PR #435 |
| منشور جديد من صفحة تتابعها | company → follower | 🔜 future | `new_post` | post | agg per company | يحتاج قرار follow+feed |
| @Mention في متن منشور | poster → mentioned | 🔜 future | `mention_post` | post | ❓ | company_posts لا تدعم mentions حالياً |
| حذف تعليقك (soft delete) | page owner → commenter | 🚫 n/a | — | — | — | soft delete فقط — لا notification |

---

### Area 2 — Jobs / Applications

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| موظف تقدّم لوظيفة شركتك | applicant → company | ✅ impl | `job_applied` | applicants list | V2-3 per job | PR #436 |
| الشركة غيّرت حالة طلبك | company → applicant | ❌ missing | `application_status` | `/home` أو job | No agg (individual) | `update_application_status()` auth.py:2300 — لا hook |
| اقتراب انتهاء الوظيفة | system → company | ❌ missing | `job_expiring` | job card | No agg | محجوب — يحتاج cron/scheduler |
| وظيفة انتهت (expires_at) | system → company | 🔜 future | `job_expired` | job card | No agg | computed at request-time — ليس event-driven |
| شركة شاهدت طلبك | company → applicant | 🚫 n/a | — | — | — | لا يوجد "viewed" status في job_applications حالياً |
| وظيفة جديدة من شركة تتابعها | company → follower | 🔜 future | `new_job` | job detail | agg per company | يحتاج follow+feed notification |

---

### Area 3 — Follow / Followers

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| شخص تابع بروفايلك | follower → user | ✅ impl | `follow` | `/u/{follower_tw_id}` | V2-2 | PR #437 `follow_profile()` |
| شخص تابع صفحة شركتك | follower → company | ✅ impl | `follow` | `/u/{follower_tw_id}` | V2-2 | PR #437 `follow_company()` |
| شخص ألغى متابعتك | ex-follower → user | 🚫 n/a | — | — | — | لا notification عند unfollow — by design |
| إعادة متابعة (refollow) | follower → user | 🚫 n/a | — | — | — | idempotent — موثَّق في Runtime QA §444 |

---

### Area 4 — Verification / Admin Review

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| تمت الموافقة على طلب توثيقك | admin → user | ✅ impl | `verify` | `/settings` | No agg | PR #438 |
| تم رفض طلب توثيقك | admin → user | ✅ impl | `verify` | `/settings` | No agg | PR #438 |
| طلب توثيق جديد (للأدمن) | user → admin | ✅ impl (partial) | `report` | `/admin` | No agg | user_id=1 placeholder — يحتاج admin lookup |
| طلب تعديل مستندات | admin → user | 🔜 future | `verify_revision` | `/settings` | No agg | يحتاج status جديد في verify_requests |

---

### Area 5 — Profile / Company / Education Page Updates

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| اكتمال إعداد الصفحة لأول مرة | system → user | 🚫 n/a | — | — | — | UI prompt فقط (completion card) — لا notification |
| تغيير مهم في صفحة تتابعها | page owner → follower | 🔜 future | `profile_update` | `/u/{tw_id}` | ❓ | ليس requirement حالياً |
| تذكير باكتمال الصفحة | system → user | 🔜 future | `completion_reminder` | profile | No agg | push/email — خارج نطاق V2 |

---

### Area 6 — Messaging / Direct Messages

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| رسالة مباشرة جديدة | sender → recipient | ❓ decide | `message` | `/messages?conv={id}` | No agg | `type='message'` مفلتر من notifications.html — نظام WebSocket منفصل |
| رسائل غير مقروءة تراكمت | sender → recipient | 🔜 future | — | `/messages` | No agg | badge على messages icon — غير منفَّذ |

---

### Area 7 — Education / Courses

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| مؤسسة تعليمية أضافت دورة | edu → followers | 🔜 future | `new_course` | course page | agg per edu | لا follow system للـ edu حالياً |
| قبول/رفض تسجيل دورة | edu → student | 🔜 future | `course_enrollment` | course | No agg | يحتاج enrollment system |

---

### Area 8 — Polls (Roadmap)

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| poll جديد من صفحة تتابعها | page owner → follower | 🔜 future | `new_poll` | poll | agg per page | Polls غير موجود في DB بعد — roadmap |
| poll انتهى — نتائج جاهزة | system → poll owner | 🔜 future | `poll_result` | poll | No agg | يحتاج poll system |

---

### Area 9 — Ratings / Reviews

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| شخص قيّم شركتك | rater → company owner | ❌ missing | `rating` | ratings section `#ratings` | agg per company (V3+) | `rate_company()` auth.py:3343 — لا hook |
| rating يحتاج مراجعة | system → admin | 🔜 future | `rating_review` | admin panel | No agg | يحتاج moderation system |

---

### Area 10 — System / Security / Account

| Event | Actor → Recipient | Status | Type | Click Target | Aggregation? | Notes |
|-------|------------------|--------|------|-------------|-------------|-------|
| تسجيل دخول من جهاز جديد | system → user | 🔜 future | `security_login` | `/settings` | No agg | يحتاج device fingerprinting |
| تغيير كلمة المرور | user → user | 🔜 future | `password_changed` | `/settings` | No agg | لا hook في settings flow |
| إعلان عام من النظام | admin → all | 🔜 future | `announcement` | — | No agg | يحتاج broadcast system |

---

### Coverage Summary

| Status | Count | الأحداث الرئيسية |
|--------|-------|-----------------|
| ✅ implemented | 7 | comment, reply, mention, job_applied, follow×2, verify×2, report (partial) |
| ❌ missing (P1/P2) | 3 | application_status_changed, rating, job_expiring_soon |
| 🔜 future planned | 12+ | new_post, new_job, new_course, polls, security, announcement, … |
| 🚫 not needed | 5 | unfollow, refollow, viewed_app, completion_card, soft_delete_comment |
| ❓ needs decision | 2 | mention agg policy, messaging badge |

---

### Missing Notifications — Priority Queue

أحداث `❌ missing` يجب تنفيذها قبل أو خلال V2:

**1. `application_status_changed` (P1 — Missing)**
- Actor: company, Recipient: applicant (employee)
- Hook location: `update_application_status()` — `auth.py:2300`
- event_key مقترح: `application_status:{app_id}:{new_status}`
- Click target: job detail أو `/home`
- Aggregation: فردي — كل طلب وظيفة مختلف

**2. `rating` (P2 — Missing)**
- Actor: rater, Recipient: company owner
- Hook location: `rate_company()` — `auth.py:3343`
- event_key مقترح: `rating:company:{company_id}:{rater_id}`
- Click target: ratings section على صفحة الشركة
- Aggregation: اgg per company — مستقبلاً (V3+)

**3. `job_expiring_soon` (P2 — Missing / Blocked)**
- Blocked: يحتاج cron job أو background scheduler
- الوضع الحالي: `_eff_status()` تحسب انتهاء الوظيفة at request-time — ليس event-driven
- لا تنفيذ حتى يوجد scheduler مناسب

---

---

## Future Notification Decision Rule

> **قاعدة إلزامية لكل الـ PRs المستقبلية. لا استثناء.**
> أي PR يضيف feature أو action تغيّر حالة مهمة يجب أن يُصرّح بقرار notification.

---

### Checklist — أسئلة يجب الإجابة عليها قبل تنفيذ أي feature

1. هل هذا الحدث يغيّر حالة تهم مستخدماً آخر؟
2. هل يحتاج أن يعرفه صاحب الحساب أو الشركة أو الموظف؟
3. من هو **actor**؟ (user_id من JWT — لا hardcoded IDs)
4. من هو **recipient**؟ (user_id في `users` table — واضح، ليس غامضاً)
5. هل recipient هو `users.id` مباشرة وليس company_id يحتاج lookup؟
6. هل يجب منع self-notification؟ (actor != recipient — إلزامي)
7. ما **notification type**؟ (اسم واضح ومتسق مع `_typeMap` في notifications.html)
8. ما **click target**؟ (URL أو anchor محدد — لا "صفحة الرئيسية" بدون تفصيل)
9. هل الإشعار **فردي** أم **قابل للتجميع**؟
10. إذا قابل للتجميع، ما **aggregation_key**؟ (يتبع format: `{kind}:{entity_type}:{entity_id}`)
11. هل **event_key** يمنع التكرار بدون حجب أحداث جديدة مشروعة؟
12. هل يحتاج **unread count** (header badge)?
13. هل يظهر في **notifications.html**؟ هل يحتاج إدخالاً في `_typeMap` و `_filterGroups`؟
14. هل يظهر في **header badge** (`/unread-count`)?
15. هل يحتاج **notification preferences** مستقبلاً؟ (مثلاً: إيقاف تشغيل نوع معين)
16. هل فيه **privacy concern**؟ (مثلاً: لا تُخبر المتابع بمعلومة خاصة)
17. هل يجب أن **يبقى بدون إشعار**؟ ولماذا؟ (يجب التصريح بسبب واضح)

---

### Mandatory PR Declaration

كل PR يضيف action جديد يُصرّح في التقرير بواحد من التالي:

```
Notification: added          — hook مُضاف، event_key: ..., recipient: ..., type: ...
Notification: not needed     — السبب: [سبب واضح]
Notification: planned later  — السبب: [...]، الـ Phase المقترح: [...]
Notification: needs decision — السؤال المفتوح: [...]
```

```
❌ ممنوع: إضافة action مهم بدون قرار notification في التقرير
❌ ممنوع: ترك TODO بدون تصريح في التقرير
❌ ممنوع: "سيتم لاحقاً" بدون تفصيل Phase أو سبب واضح
```

### أمثلة على التصريح الصحيح

```
# مثال 1 — hook مُضاف:
Notification: added — type: application_status, recipient: applicant_user_id,
  event_key: application_status:{app_id}:{status}, hook: update_application_status() auth.py

# مثال 2 — غير مطلوب:
Notification: not needed — السبب: عملية حذف ناعم (soft delete) لا تغير حالة مستخدم آخر

# مثال 3 — مؤجل:
Notification: planned later — السبب: يحتاج cron scheduler غير موجود حالياً
  Phase المقترح: يُضاف مع نظام scheduler في V3+

# مثال 4 — يحتاج قرار:
Notification: needs decision — هل نُشعر المتابعين بكل تحديث على الصفحة؟
  السؤال: ما الحد الأدنى للتغيير الذي يستدعي إشعاراً؟
```

---

---

## Notifications V2 — Smart Aggregation Plan ⏳ (Phase V2-0 — docs only, PR #447)

> **هذا القسم خطة توثيقية فقط. لا تنفيذ في هذا PR.**
> وجود هذا القسم لا يعني إذناً بتنفيذ أي Phase من V2.

---

### المشكلة

Notifications V1 تُنشئ إشعاراً مستقلاً لكل حدث. إذا تابع 100 شخص صفحة شركة، تُنشأ 100 صف في `notifications`. هذا يُحوّل الجرس إلى spam ويُنتج ضجيجاً بدل قيمة.

---

### القاعدة الذهبية للتجميع

> إذا كانت عدة إشعارات تؤدي إلى **نفس الوجهة** عند الضغط عليها، يمكن تجميعها في إشعار واحد.
> إذا كان لكل إشعار وجهة مختلفة أو قرار مستقل، يجب أن يبقى فردياً.

---

### أنواع التجميع المقررة

#### 1. Follow Aggregation

| | |
|---|---|
| **المشكلة** | 100 متابع → 100 إشعار منفصل |
| **الحل** | "أحمد ومحمد و 8 آخرين تابعوا صفحتك" |
| **aggregation_key** | `follow_agg:user:{followed_id}` |
| **Click target** | followers section/page/modal — **يحتاج قرار نهائي قبل التنفيذ** |
| **ملاحظة** | إذا لا يوجد followers page: يفتح صفحة البروفايل مع anchor `#followers`، أو `/notifications?filter=follow` |

#### 2. Job Application Aggregation Per Job

| | |
|---|---|
| **المشكلة** | 20 متقدم على وظيفة واحدة → 20 إشعار |
| **الحل** | "12 متقدماً جديداً على وظيفة «معلمة صف أول»" |
| **aggregation_key** | `job_applications_agg:job:{job_id}` |
| **Click target** | صفحة المتقدمين للوظيفة `job_id` المحدد |
| **قاعدة** | التجميع لكل `job_id` فقط — ليس لكل الشركة |

#### 3. Comment / Reply Aggregation Per Post

| | |
|---|---|
| **المشكلة** | 5 تعليقات على نفس المنشور → 5 إشعارات |
| **الحل** | "5 تعليقات جديدة على منشورك" |
| **aggregation_key (تعليقات)** | `comments_agg:post:{post_id}` |
| **aggregation_key (ردود على تعليق)** | `replies_agg:comment:{comment_id}` |
| **Click target** | المنشور `post_id` + comments section |
| **قاعدة** | التجميع لكل `post_id` فقط — ليس لكل تعليقات الحساب |

#### 4. Mention Aggregation — Needs Decision

**الأسئلة المفتوحة (يجب الإجابة قبل V2-4):**

- هل نجمع mentions إذا كانت في نفس المنشور؟
- هل نبقي mentions فردية دائماً؟
- إذا تجمّعت، هل click يفتح المنشور أم `/notifications?filter=mention`؟

**التوجه الأولي:** إبقاء mentions فردية في V2 — كل mention يحتاج سياقاً مستقلاً.

---

### الأنواع التي تبقى فردية (لا تجميع)

| النوع | السبب |
|-------|-------|
| `verify` — تغيير حالة توثيق | كل طلب قرار مستقل |
| `application_status_changed` | كل إشعار يمثل وظيفة / قرار مختلف |
| رسائل مباشرة | كل رسالة لها محادثة خاصة |
| تنبيهات أمنية / إدارية | حساسة — لا تجميع إطلاقاً |
| أي إشعار يحتاج إجراء مستقلاً | يبقى فردياً |

---

### اقتراح تصميم البيانات (لا تنفيذ في V2-0)

**Option A — أعمدة إضافية في جدول `notifications` (التوصية):**

```sql
-- لا تُنفَّذ الآن — V2-1 فقط
ALTER TABLE notifications
  ADD COLUMN IF NOT EXISTS aggregation_key    TEXT,
  ADD COLUMN IF NOT EXISTS aggregation_count  INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS aggregation_kind   TEXT,
  ADD COLUMN IF NOT EXISTS last_actor_id      INTEGER,
  ADD COLUMN IF NOT EXISTS last_event_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS target_type        TEXT,
  ADD COLUMN IF NOT EXISTS target_id          INTEGER;
```

**Option B — payload JSONB مع aggregation بدون تعديل schema:**
تخزين `aggregation_key + count + last_actors` داخل `payload` JSONB موجود.

| المعيار | Option A (أعمدة) | Option B (payload) |
|---------|-----------------|-------------------|
| Performance | ✅ أسرع — indexed columns | ⚠️ أبطأ — JSON extraction |
| Migration | ⚠️ يحتاج ALTER TABLE | ✅ لا تغيير schema |
| Queryability | ✅ سهل | ⚠️ يحتاج JSON operators |
| Type safety | ✅ كل column له type محدد | ⚠️ كل شيء في JSON |

**التوصية: Option A** — أعمدة إضافية مع index على `aggregation_key`.

---

### Helper المقترح (لا تنفيذ في V2-0)

```python
def create_or_update_aggregated_notification(
    recipient_user_id: int,
    type_: str,
    title_template: str,
    body_template: str,
    aggregation_key: str,
    target_type: str,
    target_id: int,
    actor_id: int = None,
    action_url: str = None,
    payload: dict = None
) -> dict | None:
    """
    Future helper — لا تُنفَّذ في V2-0 — مقترح فقط.

    الفكرة:
    1. إذا لا يوجد notification غير مقروء بنفس aggregation_key:
       → ينشئ notification جديد (aggregation_count=1)
    2. إذا يوجد notification غير مقروء بنفس aggregation_key:
       → يُحدَّث نفس الصف:
         aggregation_count += 1
         last_actor_id = actor_id
         last_event_at = NOW()
         title/body = apply_count_template(title_template, count)
    3. إذا الإشعار السابق مقروء (is_read=TRUE):
       → ينشئ aggregate جديد من الصفر (aggregation_count=1)
    """
    pass  # NOT IMPLEMENTED — Phase V2-1
```

---

### سياسة التجميع المقترحة

#### Option A — Aggregate While Unread ✅ (التوصية)

الإشعارات تتجمع طالما الإشعار الأول غير مقروء:

1. أحمد يتابع الشركة → إشعار جديد: `"أحمد تابعك"` (count=1)
2. محمد يتابع الشركة → يُحدَّث نفس الصف: `"أحمد ومحمد تابعاك"` (count=2)
3. صاحب الصفحة يقرأ الإشعار (`is_read=TRUE`)
4. سارة تتابع الشركة → إشعار aggregate جديد: `"سارة تابعتك"` (count=1)

**مميزاته:** بسيط، عملي، لا يحتاج windows زمنية، واضح للمستخدم.

#### Option B — Aggregate by Time Window

التجميع حسب يوم أو window زمنية (24 ساعة). أعقد، يربك read/unread semantics.

**القرار: Option A — aggregate while unread.**

---

### Click Target Rules

```
القاعدة الذهبية:
ممنوع aggregate notification يفتح آخر actor فقط إذا يمثل مجموعة.
الوجهة يجب أن تمثّل المجموعة — وليس فرداً واحداً.
```

| نوع الـ aggregate | Click target |
|------------------|--------------|
| Follow aggregate | followers section / page / modal |
| Job applications aggregate | applicants list للوظيفة `job_id` |
| Comments aggregate | المنشور `post_id` + comments section |
| Replies aggregate | المنشور أو comment thread |
| Mentions | **Needs Decision** |
| Sensitive individual | الوجهة الحالية كما هي (لا تغيير) |

---

### Anti-spam Rules

```
❌ لا تنشئ 100 rows لنفس الحدث المجمع
❌ لا ترسل إشعار للفاعل نفسه (actor == recipient)
❌ لا تجمع أحداث مختلفة الوجهة في نفس notification
❌ لا تجمع job applications لوظائف مختلفة
❌ لا تجمع comments لمنشورات مختلفة
❌ لا تكسر event_key format الموجود في V1 بدون migration plan
❌ لا تحذف إشعارات V1 القديمة
❌ لا تغيّر read semantics بدون توثيق واضح
```

---

### Notifications V2 Phases

| Phase | العنوان | الوصف | الحالة |
|-------|---------|-------|--------|
| **V2-0** | Smart Aggregation Plan | هذا القسم — docs only | ✅ PR #447 |
| **V2-1** | Aggregation Schema + Helper | حقول إضافية + helper بدون تفعيل hooks | 🔜 مستقبلي |
| **V2-2** | Follow Aggregation | تجميع إشعارات المتابعة | 🔜 مستقبلي |
| **V2-3** | Job Application Aggregation | تجميع المتقدمين لكل وظيفة | 🔜 مستقبلي |
| **V2-4** | Comment/Reply Aggregation | تجميع التعليقات/الردود لكل منشور أو thread | 🔜 مستقبلي |
| **V2-5** | UI Support for Aggregated Notifications | تحديث كروت الإشعارات: count + "و X آخرين" | 🔜 مستقبلي |
| **V2-6** | Final Runtime QA | فحص يدوي + static checks + توثيق نهائي | 🔜 مستقبلي |

> **مهم:** لا تنفيذ لأي Phase V2 غير V2-0 حتى يُطلب صراحةً من المستخدم.

---

### V2 Constraints (mandatory — applies to all V2 phases)

```
✅ لا تكسر Notifications V1 (Phases 1–10) في أي V2 phase
✅ V2-0 يعدّل docs فقط — لا auth.py ولا server.py ولا HTML/CSS/JS ولا schema ولا hooks
✅ event_key format الحالي يبقى — aggregation_key هو field منفصل
✅ لا WebSocket ولا push (قيد V1 مستمر حتى قرار صريح)
✅ create_or_update_aggregated_notification هو helper مستقبلي فقط — لا يُنفَّذ في V2-0
```

---

## Phases Summary

| Phase | العنوان | الملفات | الأولوية |
|-------|---------|---------|---------|
| **0** | Audit & Plan (هذا الملف) | `docs/NOTIFICATIONS_PLAN.md` (docs only) | ✅ مكتمل |
| **1** | Security Hardening | `server.py`, `notifications.html` | ✅ مكتمل (PR #431) |
| **2** | Schema Hardening (`event_key`, `actor_id`) | `auth.py` (migration + helper) | ✅ مكتمل (PR #432) |
| **3** | Comment Notification Hook | `auth.py` | ✅ مكتمل (PR #433) |
| **4** | Reply Notification Hook | `auth.py` | ✅ مكتمل (PR #434) |
| **5** | Mention Notification Hook | `auth.py` | ✅ مكتمل (PR #435) |
| **6** | Job Application Hook | `auth.py` | ✅ مكتمل (PR #436) |
| **7** | Follow Hook | `auth.py` | ✅ مكتمل (PR #437) |
| **8** | Verification Hook | `server.py` | ✅ مكتمل (PR #438) |
| **9** | Per-Notification Read + Pagination | `auth.py`, `server.py` | ✅ مكتمل (PR #439) |
| **10** | Unread Badge in App Header | `server.py`, `static/app-header.js`, `static/app-header.css` | ✅ مكتمل (PR #440) |
| **11** | Real-time / Push (WS or SSE or Push API) | TBD — needs decision | P3 — مؤجل |
| **V2-0** | Smart Aggregation Plan | `docs/NOTIFICATIONS_PLAN.md` (docs only) | ✅ PR #447 |
| **V2-1** | Aggregation Schema + Helper | `auth.py` migration + helper | 🔜 مستقبلي |
| **V2-2** | Follow Aggregation | `auth.py` follow hook | 🔜 مستقبلي |
| **V2-3** | Job Application Aggregation | `auth.py` job hook | 🔜 مستقبلي |
| **V2-4** | Comment/Reply Aggregation | `auth.py` comment hook | 🔜 مستقبلي |
| **V2-5** | UI Support | `notifications.html` | 🔜 مستقبلي |
| **V2-6** | Final Runtime QA | static checks + manual QA | 🔜 مستقبلي |

---

## Source of Truth

| العنصر | المرجع |
|--------|--------|
| DB Table | `notifications` في `auth.py` (migration line ~725) |
| Backend Helpers | `auth.py`: `create_notification`, `get_notifications`, `mark_notifications_read`, `get_unread_notifications` |
| API Endpoints | `server.py`: `GET/PUT /notifications/{user_id}` |
| Frontend (current) | `notifications.html` (needs refactor in Phase 1) |
| Full Plan | هذا الملف |

---

*أُنشئ: 2026-07-09 — Phase 0 audit. حُدِّث: 2026-07-10 — Phase 1 مكتمل (PR #431). حُدِّث: 2026-07-10 — Phase 2 مكتمل (PR #432). حُدِّث: 2026-07-10 — Phase 3 مكتمل (PR #433). حُدِّث: 2026-07-10 — Phase 4 مكتمل (PR #434). حُدِّث: 2026-07-10 — Phase 5 مكتمل (PR #435). حُدِّث: 2026-07-10 — Phase 6 مكتمل (PR #436). حُدِّث: 2026-07-10 — Phase 7 مكتمل (PR #437). حُدِّث: 2026-07-10 — Phase 8 مكتمل (PR #438). حُدِّث: 2026-07-10 — Phase 9 مكتمل (PR #439). حُدِّث: 2026-07-10 — Phase 10 Unread Badge in App Header مكتمل (PR #440). Phase 11 مؤجل — يحتاج قرار معماري. حُدِّث: 2026-07-10 — Notifications V1 Final QA + Closure: إضافة قسم "Notifications V1 Status"، تحديث Phase 11 deferral بتفصيل أكبر، تنظيف test 139q (PR #441). حُدِّث: 2026-07-10 — Runtime QA Bugfix: ON CONFLICT partial-index fix في create_notification، توثيق سلوك refollow، إضافة §153 checks (PR #444). حُدِّث: 2026-07-10 — Notifications V2 Smart Aggregation Plan: إضافة قسم V2-0 (docs only) — تجميع Follow / Job Applications / Comments / Replies — Click Target Rules — Option A (aggregate while unread) — Helper مقترح — V2 Phases V2-0 to V2-6 (PR #447).*
