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

*أُنشئ: 2026-07-09 — Phase 0 audit. حُدِّث: 2026-07-10 — Phase 1 مكتمل (PR #431). حُدِّث: 2026-07-10 — Phase 2 مكتمل (PR #432). حُدِّث: 2026-07-10 — Phase 3 مكتمل (PR #433). حُدِّث: 2026-07-10 — Phase 4 مكتمل (PR #434). حُدِّث: 2026-07-10 — Phase 5 مكتمل (PR #435). حُدِّث: 2026-07-10 — Phase 6 مكتمل (PR #436). حُدِّث: 2026-07-10 — Phase 7 مكتمل (PR #437). حُدِّث: 2026-07-10 — Phase 8 مكتمل (PR #438). حُدِّث: 2026-07-10 — Phase 9 مكتمل (PR #439). حُدِّث: 2026-07-10 — Phase 10 Unread Badge in App Header مكتمل (PR #440). Phase 11 مؤجل — يحتاج قرار معماري. حُدِّث: 2026-07-10 — Notifications V1 Final QA + Closure: إضافة قسم "Notifications V1 Status"، تحديث Phase 11 deferral بتفصيل أكبر، تنظيف test 139q (PR #441). حُدِّث: 2026-07-10 — Runtime QA Bugfix: ON CONFLICT partial-index fix في create_notification، توثيق سلوك refollow، إضافة §153 checks (PR #444).*
