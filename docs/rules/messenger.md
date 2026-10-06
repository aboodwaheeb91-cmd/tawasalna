# Messenger Session Lifecycle — الرسائل

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Messenger Session Lifecycle Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §47 → Messenger Session Lifecycle`.

### TwAuthSync.onSessionChange handler (messages.ws.js) — permanent decision tree

| Condition | Action |
|-----------|--------|
| `capturedJwt` empty (logout / expired) | `_jwt = ''` + `_user = null` + `_currentConvId = null` + `window.location.replace('/login')` |
| JWT present but `snapshot.isAuthenticated === false` | Same as above — redirect to `/login` |
| JWT present, `newUserId !== prevUserId` (account switch) | `window.location.reload()` — clean re-init |
| JWT present, same userId (token refresh) | Update `_jwt` + `_wsPendingJwt` + schedule 500ms WS reconnect |

1. **`capturedJwt` is always sourced synchronously:** `info.jwt` first, then `localStorage.getItem('tw_jwt')`. Never from `snapshot.jwt` (V2 snapshot has no jwt field).

2. **Account switch = full page reload.** Do NOT attempt partial state clearing (conv list, messages, `_user`, `_currentConvId`, etc.) — it is error-prone and incomplete. `window.location.reload()` is the only approved account-switch action.

3. **Logout/invalid → redirect, not reconnect.** Empty JWT or `isAuthenticated=false` → `window.location.replace('/login')`. Never reconnect WS after logout.

4. **`_jwt = ''` must be assigned before redirect** in the logout/invalid path. This prevents in-flight callbacks from using the old JWT.

5. **`_currentConvId = null` must be assigned before redirect** in the logout/invalid path. This prevents a stale conversation ID from appearing if navigation is delayed.

### messages.api.js — permanent API session contract

6. **`getMessagesJwt()` is the only approved JWT source** in `messages.api.js`. It reads `localStorage.getItem('tw_jwt')` at call time — never uses the stale in-memory `_jwt` variable.

7. **`_isMessagesAuthValid()` must guard every API function** before making any `fetch()`. The guard is a four-layer check — all must pass:
   - `_user` and `_user.id` are set in memory
   - `getMessagesJwt()` returns a non-empty JWT from localStorage
   - `localStorage.getItem('tw_user')` parses to a valid user whose `id` matches `_user.id` (cross-account race guard — see rule 10)
   - When `TwAuthSync.getSessionSnapshot()` is available: `snapshot.isAuthenticated` must be `true` AND `snapshot.userId` (when present) must match `_user.id`

8. **`'Bearer ' + _jwt` is permanently forbidden** in `messages.api.js`. All Authorization headers must use `'Bearer ' + getMessagesJwt()`.

9. **`_isMessagesAuthValid()` return values are final:** functions returning null-on-not-found (`apiLookupByTwId`, `apiGetUser`) resolve with `null`; functions rejecting on error reject with `'unauthenticated'`.

10. **HTTP messaging API calls require the current localStorage `tw_user.id` to match the in-memory Messenger `_user.id`; mismatch blocks the request before fetch.** This closes the account-switch race window: during the brief period between `TwAuthSync.onSessionChange` firing and `window.location.reload()` completing, Account A's stale in-memory `_user` cannot send HTTP requests using Account B's JWT or `tw_user` data.

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

### Forbidden (permanent)

```
❌ Using _jwt directly in Authorization headers in messages.api.js
❌ Adding a new fetch() in messages.api.js without an _isMessagesAuthValid() guard
❌ Partial account-switch handling in messages page — only window.location.reload()
❌ Reconnecting WS after logout (empty JWT or isAuthenticated=false)
❌ Reading snapshot.jwt — V2 TwAuthSync snapshot has no jwt field
❌ Clearing conversation state manually on account switch (reload handles it)
❌ Redirecting to any URL other than '/login' on logout/invalid session
❌ Skipping the localStorage tw_user.id comparison in _isMessagesAuthValid() — it is the cross-account race guard
❌ Sending typing events without throttle (no _typingThrottle guard in the input handler)
❌ Closing the WS (code 4005) when _ws_typing_rate_ok() returns False — use continue instead
❌ Reversing the rate-limit-before-DB ordering for typing events
❌ Clearing _typingThrottle on conversation switch without also clearing _typingTimer
```
