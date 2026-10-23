# Messenger Session Lifecycle — الرسائل

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Messenger Session Lifecycle Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §47 → Messenger Session Lifecycle`.

### Page guard + socket session handler (messages.state.js / messages.ws.js — PR 4.4)

0. **`twRequireAuth()` في `messages.state.js` هو الحماية الوحيدة.** `_user = {id, user_type}` من الـ snapshot اللي بيرجّعه · `_jwt` من `TwAuthSync.getToken()` (لإطار auth بالـ WS بس). guest / expired / stale → `/login?next=/messages`؛ logout بتاب تاني → نفس التحويل؛ حساب تاني → reload — كله من twRequireAuth.

| Condition | Action (`TwAuthSync.onSessionChange` في `messages.ws.js`) |
|-----------|--------|
| نفس الـ JWT + نفس المستخدم + socket CONNECTING/OPEN | no-op (PR 2C) |
| `info.jwt` فاضي، أو snapshot مش authenticated، أو `userId` مختلف | سكّر الـ socket والمؤقتات (`_wsGen++` + `_wsTeardown()`) + `_jwt = ''` + `_user = null` + `_currentConvId = null` — **بدون reconnect وبدون تنقّل** |
| JWT موجود، نفس الـ userId (token refresh) | Update `_jwt` + `_wsPendingJwt` + schedule 500ms WS reconnect |

1. **`capturedJwt` = `info.jwt` بس** (متزامن قبل أي تأخير). إطار الـ auth بيقرأ `_wsPendingJwt` ثم `TwAuthSync.getToken()`. ❌ `snapshot.jwt`.

2. **التنقّل مش شغل الـ socket handler.** ❌ `location.replace` / `location.reload` بـ `messages.ws.js` — twRequireAuth بيعملها (تنقّلين متعارضين كانوا بيضيّعوا `?next=`).

3. **Logout / invalid / حساب تاني → ما في reconnect أبداً.**

4. **`_jwt = ''` و `_currentConvId = null`** بيتعيّنوا بنفس المسار — ما في callback معلّق بيستعمل الجلسة القديمة.

5. **socket واحد بالتاب:** `messages.html` فيها `<meta name="tw-ws" content="page">` → الـ Badge WS المشترك (`tw_shared.js`) ما بيفتح؛ `connectWS()` بيعمل `_wsTeardown()` للقديم (socket + reconnect معلّق) قبل `new WebSocket`.

5b. **إعادة الاتصال بحد:** backoff أُسّي مع jitter (2^n ث، ≤ 30ث)، أقصى `WS_MAX_RETRIES` (5) — بعدها `msgOnLiveLost()` → إشعار `#msgConnBar` + «إعادة المحاولة». الـ poll (10ث) بيوقف بعد `MSG_MAX_FAILS` (3) فشل متتالي → نفس الإشعار (`msg.offline`). `msgRetryConnection()` بيصفّر الحدّين.

### messages.api.js — API session contract (PR 4.4)

6. **كل طلب عبر `twApi`** من خلال `_msgApi(path, opts)` → بيرجّع `res.data` أو بيرفض بالـ HTTP status. ❌ `fetch` · ❌ `localStorage` · ❌ `Authorization` يدوي.

7. **`_isMessagesAuthValid()` قبل كل طلب:** `_user.id` موجود + `TwAuthSync.getSessionSnapshot()` authenticated + `snapshot.userId === _user.id` — بيتقرأ وقت الطلب (الـ snapshot نفسه بيطابق `tw_jwt` مع `tw_user`) → حاجز الـ account-switch race.

8. **ترتيب الردود:** `loadConversations()` بـ `_convSeq` — أحدث رد بس بيرسم. تحميل المحادثة مربوط بـ id المحادثة + `_threadSeq` — رد لمحادثة تانية أو أقدم من آخر فتح بيتجاهل (حتى `reloadMessagesQuiet()`).

9. **`_isMessagesAuthValid()` return values are final:** `apiLookupByTwId` بيرجّع `null`؛ الباقي بيرفض بـ `'unauthenticated'`.

10. **زر «تحديد موعد»** بهيدر المحادثة = `twScheduleButton({candidateId, candidateName, candidateType})` بكل `openConversation()` (`docs/rules/schedule-interview.md`) — بينمسح عند الإغلاق.

### messages.render.js — Typing Throttle Contract (permanent)

11. **`_typingThrottle` is a module-level variable in `messages.state.js`** — alongside `_typingTimer`. Both are always `null` or a timer ID. Never use a boolean flag; always use the timer ID so `clearTimeout` works correctly.

12. **Client typing events are throttled at most once per 1500ms per conversation.** The `msgInput` `input` event listener in `messages.render.js` enforces:
    - If `_typingThrottle` is null → send `typing`, set `_typingThrottle = setTimeout(..., 1500)`
    - If `_typingThrottle` is set → skip (no send)
    - On every keystroke: reset `_typingTimer` (1800ms debounce for `typing_stop`)
    - When `_typingTimer` fires: send `typing_stop` + clear `_typingThrottle`

13. **Throttle must be cleared in three places (permanent):**
    - `doSendMessage()` — clears both `_typingTimer` and `_typingThrottle` before sending `typing_stop`
    - `closeConversationUI()` — clears both timers so the previous conversation's pending events never fire after a conversation switch
    - The `_typingTimer` callback itself (1800ms debounce) — clears `_typingThrottle` after sending `typing_stop`

14. **Typing rate limit exceeded on the server side → `continue` (drop), not `close(4005)`.** Close 4005 is reserved for real protocol violations (repeated unknown event types, `active_conversation` ctrl rate limit). A typing burst from a fast typist is NOT a protocol violation and must never disconnect an authenticated socket.

15. **Rate-limit-before-DB ordering is permanent for typing events.** `_ws_typing_rate_ok(auth_uid)` is always called BEFORE `_ws_conversation_exists_async()`. This ordering must never be reversed, regardless of whether the rate limit triggers a `continue` or a disconnect.

### Conversation Policy — مين بيراسل مين (task 5.0g — AUD-P1-01)

16. **`auth.can_send_message(sender, receiver)` هي القاعدة الوحيدة.** النوع (`users.user_type`) والتاريخ (`messages`) والمتابعة (`profile_follows`) والإنهاء (`conversation_endings`) من القاعدة — ❌ من التوكن. القرار نفسه بـ `message_policy_decide(sender_id, row)` (pure) وصف الحقائق من query وحدة (`_MESSAGE_POLICY_FACTS_SQL` بصيغتين للـ drivers).

| الحالة | القرار |
|--------|--------|
| محادثة موجودة (رسالة سابقة بأي اتجاه) — حتى بعد إلغاء المتابعة · المحادثات القديمة بالإنتاج | مسموح للطرفين |
| محادثة منتهية (صف بـ `conversation_endings`) | الشركة اللي أنهتها بس — رسالتها بتفتحها (الصف بينحذف بنفس الـ transaction) · الشخص → 403 `ended` «أنهت الشركة هذه المحادثة» |
| جديدة: شركة / جهة تعليمية → أي حدا | مسموح |
| جديدة: شخصي → جهة تعليمية | مسموح |
| جديدة: شخصي → شخصي | متابعة متبادلة بس، وإلا 403 `mutual_follow` «يجب أن تتابعا بعضكما لبدء محادثة» |
| جديدة: شخصي → شركة | 403 `company_start` «لا يمكنك بدء محادثة مع شركة» |
| نوع مش معروف | 403 `forbidden` (fail closed) · حساب مش موجود → 404 `not_found` |
| حظر بأي اتجاه أو المستلم معلّق (task 5.4 — `docs/rules/blocks-suspension.md`) | 404 `not_found` — بدء ورد، قبل أي قاعدة تانية (عمود سادس بـ `_MESSAGE_POLICY_FACTS_SQL` من `bs.visible_sql`) |

17. **كل مسار بيبعت رسالة بيفحصها بنفس transaction الـ INSERT، بعد `pg_advisory_xact_lock` على الزوج** (`MESSAGE_PAIR_LOCK_SQL_*` — نفس القفل بـ `end_conversation`): `send_message_pipeline` (pg8000) و `_pipeline_asyncpg` (asyncpg) → رفض = `MessagePolicyError` وما في شي انكتب → `_message_policy_error` → `{ok:false, error:{code, message}}` (النص = twT `msg.policy.*` مع override الأدمن). الـ WebSocket ما بيبعت رسائل (typing / active_conversation بس).

18. **إنهاء المحادثة:** `POST /messages/conversations/{other_id}/end` — المتصل `co` والطرف التاني `emp` من القاعدة (غير هيك 403 `end_forbidden`) + في رسالة بيناتهم (غير هيك 404 `no_conversation`) · idempotent · **بدون إشعار** · الرسائل القديمة بتضل ظاهرة.

19. **الواجهة بتقرأ القرار بس:** `GET /messages/can-send/{other_id}` → `{can_message, reason, reason_key, ended, can_end}` عبر `twCanMessage(id)` (`tw_shared.js`، ما بيرمي) → `twAction('message', {canMessage})` بصفحات الملف (profile-showcase · company · edu) و `twAction('end_conversation', {targetType, canEnd})` بهيدر المحادثة (`#chatEndSlot` — confirm من السجل). `messages.html`: مكان الكتابة مخفي لحد ما يوصل الجواب؛ مرفوض → السبب بـ `#chatLocked` بدل مكان الكتابة · فشل إرسال بـ 403 → إعادة قراءة القرار (بدون toast عام). `GET /profile/{id}` → `permissions.can_message` من نفس الدالة.


```
❌ مسار بيبعت رسالة بدون can_send_message بنفس الـ transaction وتحت قفل الزوج (task 5.0g)
❌ قاعدة «مين بيراسل مين» تانية (بالصفحة، من نوع الـ JWT، أو فحص Python تاني)
❌ إشعار للشخص عن إنهاء المحادثة
❌ fetch() أو localStorage بأي ملف messages.*.js — twApi + TwAuthSync (PR 4.4)
❌ طلب من messages.api.js بدون _isMessagesAuthValid()
❌ location.replace / location.reload من handler الـ socket — twRequireAuth بس
❌ Reconnecting WS after logout / invalid session / account switch
❌ socket ثاني بنفس التاب (connectWS بدون _wsTeardown · إزالة <meta name="tw-ws" content="page">)
❌ إعادة محاولة بلا حد (socket أو poll) أو بدون إشعار واضح بعد الحد
❌ رد طلب قديم بيكتب فوق محادثة / قائمة أحدث (لازم فحص id + seq)
❌ Reading snapshot.jwt — V2 TwAuthSync snapshot has no jwt field
❌ Sending typing events without throttle (no _typingThrottle guard in the input handler)
❌ Closing the WS (code 4005) when _ws_typing_rate_ok() returns False — use continue instead
❌ Reversing the rate-limit-before-DB ordering for typing events
❌ Clearing _typingThrottle on conversation switch without also clearing _typingTimer
```

Tests: `python -m pytest tests/test_conversation_policy.py -q` (5.0g) · `node tests/test_messages_page_runtime.js` · `node tests/test_ws_client.mjs` · `node tests/test_ws_api.mjs`.
