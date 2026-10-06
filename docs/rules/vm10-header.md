# VM-10 Global Session UI Visibility / Header — الهيدر وظهور الجلسة

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Global Session UI Visibility System Rules — VM-10 (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `docs/design-system/VIEWER-MODES.md §VM-10`.

1. **`initGlobalHeaderMenu(btnId, ddId[, dynId])` is the ONLY approved way** to wire a header menu dropdown. No per-page toggle logic, no per-page visibility checks. Idempotent — a second call for the same btnId is silently ignored.

2. **`data-tw-session="authenticated|guest|all"` is the ONLY approved way** to show/hide elements based on session state. `_twApplyDeclarativeVisibility()` runs once on `initGlobalHeaderMenu()` call and on every session change. This is NOT a security layer — it is purely visual.

3. **`_TW_HEADER_MENU_POLICY` in `tw_shared.js` is the single source** for all header menu items. Every item must declare `show: 'auth' | 'guest' | 'all'`. Never add a menu item without `show`.

4. **Guest Menu URL contract (permanent):**
   - Login item → href: `/login` (opens login form)
   - Register item (إنشاء حساب) → href: `/login#register` (opens registration form directly)
   - These MUST be different. Do NOT change Register's href back to `/login`.

5. **`static/app-header.js` is layout-only (VM-10 compliant):**
   - Only allowed to: set avatar initials/image, wire `[data-ah-logout]` buttons to `window.twLogout()`.
   - Forbidden: `setInterval`, polling, session resolution, `Object.keys(localStorage)`, `startsWith('tw_')`, `_pollUnreadBadge`, parallel WS.
   - Badge counts handled by `loadGlobalBadges()` + Badge WS IIFE in `tw_shared.js`.

6. **Badge WebSocket lifecycle (permanent — origin/main version is canonical):**
   - Variables: `_gen`, `_activeUid`, `_activeSocket`, `_reconnectTimer`, `_retries`, `_sessionReinitTimer`
   - `_clearSocket()` is the ONLY approved way to stop the WS + cancel timers + increment `_gen`
   - `_initBadgeWS(pendingJwt)` — reads TwAuthSync V2 snapshot; falls back to `tw_user` + `tw_jwt` for non-TwAuthSync pages
   - First-message JWT auth: `ws.onopen` sends `{"type":"auth","token":"..."}` → only processes `badge_update` after `auth_ok` with matching `user_id`
   - `onclose` codes 4001–4007 → no reconnect (permanent no-reconnect contract)
   - Exponential backoff: `Math.min(30000, 2^_retries * 1000 + jitter)`, max 5 retries
   - `_clearBadges()` clears `[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]`
   - `window._twBadgeWsStop()` / `window._twBadgeWsStart()` exposed for external lifecycle control
   - `_twBadgeWsStop()` MUST call `_badgeGeneration++` to cancel in-flight HTTP badge requests

7. **`twLogout()` in `tw_shared.js` is the ONLY approved logout function.** It uses `TwAuthSync.invalidateSession('logout', {redirect:'/login'})` when TwAuthSync is available, else removes only `['tw_jwt','tw_user']` allowlist. Never use `Object.keys(localStorage).filter(k => k.startsWith('tw_'))` for logout.

8. **`invalidateSession(reason, opts)` allowlist (permanent):** Only removes `['tw_jwt', 'tw_user']`. `startsWith('tw_')` is permanently forbidden — it would destroy user preferences.

9. **Pages adopted by VM-10 (all 6 are complete):** `company-profile.html`, `home-v2.html`, `messages.html`, `notifications.html`, `profile-showcase.html`, `edu-profile.html`. Any new page using `.sc-menu-dropdown` must follow the adoption pattern: load `tw_shared.js` → `auth-sync.js` → call `initGlobalHeaderMenu`.

### Forbidden (VM-10 — permanent)

```
❌ Per-page toggle logic for .sc-menu-dropdown (use initGlobalHeaderMenu)
❌ Per-page session check for menu items (use _TW_HEADER_MENU_POLICY)
❌ Register menu item href = '/login' (must be '/login#register')
❌ Object.keys(localStorage).filter(k => k.startsWith('tw_')) anywhere
❌ setInterval for badge polling in any page or module (use loadGlobalBadges + Badge WS)
❌ Parallel Badge WS outside tw_shared.js IIFE
❌ app-header.js calling _pollUnreadBadge or setInterval
❌ _generation/_activeUserId in Badge WS (canonical names are _gen/_activeUid)
❌ viewer_type or isOwner used in _twApplyDeclarativeVisibility (that's VM-01)
❌ data-tw-session treated as a security boundary (it is visual-only)
❌ new badge WS IIFE outside tw_shared.js
```
