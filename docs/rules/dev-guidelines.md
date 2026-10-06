# Development Guidelines for AI Assistants — إرشادات التطوير

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Development Guidelines for AI Assistants

1. **Backend = `server.py` + `auth.py`** — `server.py` holds the FastAPI app (routes, JWT, WebSocket, middleware, migrations); `auth.py` holds the DB data layer and business logic. There is no further routes/models/services split.

2. **Frontend pages are self-contained** — each HTML file includes its own `<style>` and `<script>` blocks. Do not introduce a build system unless explicitly requested.

3. **Database migrations are handled inline** — `server.py` runs `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` on startup. Add new migrations there.

4. **Respect RTL** — all UI text is Arabic. Use `dir="rtl"` and the Cairo font. Avoid left-to-right assumptions in CSS (use `margin-inline-start` instead of `margin-left` when adding new styles).

5. **Security notes:**
   - `ADMIN_TOKEN`, `JWT_SECRET`, `ADMIN_URL_TOKEN` are all environment variables — never hardcoded in source
   - `hmac.compare_digest` is used for all token comparisons (timing-safe)
   - No secrets are logged or returned in error responses
   - Passwords are never returned from any endpoint

6. **Real-time transport is WebSocket for messages, polling for notifications.**
   - Messaging: WebSocket IS implemented — `/ws/{user_id}` in `server.py` + `messages.ws.js` client. ✅ P0 Security Debt Fully Resolved (PR `security/ws-auth-hardening`): the route uses First-Message JWT Authentication with fail-closed origin policy, bounded cache, async DB, per-user connection limits, and rate-limit-before-DB ordering.
   - **WS auth handshake (permanent contract):** Client sends `{"type":"auth","token":"<jwt>"}` as the very first message; server validates via `_ws_validate_auth_frame()` and responds with `{"type":"auth_ok","user_id":<int>}` before any operational events flow. Client validates `auth_ok.user_id` matches expected uid.
   - **Application close codes 4001–4007 (do not reconnect on any of these):**
     - 4001 Unauthorized — invalid/expired JWT, missing claims, invalid user_type
     - 4002 Auth Failed — auth timeout, oversized/malformed frame, wrong frame type
     - 4003 Forbidden — JWT uid ≠ URL path user_id
     - 4004 Bad Payload — JSON error or oversized frame in message loop
     - 4005 Policy — typing rate limit or too many unknown events
     - 4006 Origin Denied — origin rejected by fail-closed policy
     - 4007 Too Many Connections — user already has 10 active connections
   - **Origin policy (fail-closed):** Production defaults = `{https://tawasolna.com, https://www.tawasolna.com}`. `"null"` origin always rejected. No-origin = native clients, allowed with valid JWT. `WS_ALLOWED_ORIGINS="*"` raises RuntimeError at startup. `APP_ENV=development` adds localhost variants.
   - **Connection limit:** max 10 simultaneous WS connections per user (`_WS_MAX_CONN_PER_USER`). `register()` returns `False` → caller sends 4007.
   - **Rate-limit-before-DB:** For `typing`/`typing_stop` AND `active_conversation`, the rate limiter (`_ws_typing_rate_ok()` / `_ws_ctrl_rate_ok()`) is called BEFORE `_ws_conversation_exists_async()`. This ordering is permanent and must never be reversed.
   - **Rate limiter values (permanent):** Typing: `_WS_TYPING_MAX=10` / `_WS_TYPING_WINDOW=10.0s`. Control (active_conversation): `_WS_CTRL_MAX=30` / `_WS_CTRL_WINDOW=10.0s`.
   - **Schema validation (permanent):** The `type` field in message-loop frames is validated as a non-empty string ≤ 80 chars BEFORE `len()` or slicing. Non-string/empty/oversized `type` → close 4004. Valid unknown strings → violation counter → close 4005 at limit.
   - **Dead socket cleanup contract (permanent):** `send_to_user()` must route dead sockets through `self.disconnect(user_id, dead_ws)` — never direct list removal. When the last connection dies, `_ws_cleanup_typing_log(user_id)` is also called.
   - **Legacy WS send path removed:** The path accepting `{receiver_id, content}` without `type` has been permanently removed. All message sends use HTTP (`POST /messages/{user_id}`).
   - **Client lifecycle requirements (permanent):** `_wsGen` generation counter; `_wsAuthTimeoutTimer` (cancellable 5s auth timeout handle); `_wsRetries` reset ONLY on `auth_ok` success or session change (NOT in `onopen`); `auth_ok.user_id` validation; `TwAuthSync.onSessionChange` integration; exponential backoff with jitter (max 5 retries, 30s cap); `messages.html` must load `auth-sync.js` before `messages.ws.js`.
   - **TwAuthSync V2 snapshot contract (permanent):** `getSessionSnapshot()` returns `{state, isAuthenticated, userType, userId, reason}` — **no `jwt` field**. JWT always from `info.jwt` (callback param) or `localStorage.getItem('tw_jwt')`. Never `snapshot.jwt`. Badge WS `_sessionReinitTimer` must be cancelled by `_clearSocket()`.
   - **`_ws_ctrl_rate_ok()` (permanent):** defined in `server.py`; handles rate limiting for `active_conversation` events (30/10s). Called BEFORE `_ws_conversation_exists_async()` for `active_conversation` events.
   - Notifications: HTTP polling only — `fetch('/notifications/{user_id}')`. No WebSocket for notifications.
   - Do not add a second WebSocket route for messages or notifications.
   - Do not call `ws_manager.register()` before JWT verification completes.
   - Identity is always from JWT claims (`auth_uid`) — the URL path `user_id` is a routing hint only and must match JWT but never overrides it.

7. **Supabase is the only database** — `SUPABASE_DB_URL` must be set. There is no local SQLite fallback.

8. **No front-end framework** — keep it vanilla JS. Adding React/Vue requires an explicit request and build tooling setup.

9. **IP geolocation** — `ip-api.com` is used to detect user country. Results are cached in `IP_TO_COUNTRY_CACHE` dict (in-memory, resets on restart).
