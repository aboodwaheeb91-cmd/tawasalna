# VM-01 bfcache Session Revalidation

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## VM-01 bfcache Session Revalidation Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `docs/design-system/VIEWER-MODES.md §VM-01-BFCACHE`.

1. **`TwAuthSync.onSessionChange` is the only approved mechanism** for bfcache owner-mode revocation. Do NOT poll `localStorage` on `pageshow`, do NOT add a second listener, do NOT use `addEventListener('pageshow', ...)` directly.

2. **bfcache carve-out requires `snapshot.userId === profileId`**, not just JWT presence. The old company.main.js pattern (`reason==='pageshow' && jwt`) is permanently replaced by the identity-aware check. Account B's valid JWT must NOT carve out Account A's owner view.

3. **Preview mode (preview-public-user / preview-guest) does NOT exempt a page from session revocation.** A logout or account switch during preview must still revoke owner UI immediately and clear preview classes. The old early-return guard for preview is removed.

4. **`window._scOwnerHydrationGeneration` is a numeric counter, not a boolean.** It is incremented by `renderProfile` (on each new hydration including non-owner results) AND by the session revoke handler. Both `.then()` AND `.catch()` callbacks must guard with `if (_capturedHydGen !== window._scOwnerHydrationGeneration) return;` before modifying any owner state.

5. **`renderProfile` with a non-owner response must immediately discard private owner state.** When `_vt !== 'owner'`, increment `_scOwnerHydrationGeneration`, clear `_scOwnerProfile`, clear `_scOwnerProfilePromise`. This runs on every renderProfile call, including background re-verify results.

6. **`_isCurrentEduOwner()` is fail-closed.** Without TwAuthSync available → always returns `false`. No localStorage fallback is permitted. Covered operations: `openEditModal()`, `saveEdit()` (`uploadCover()` removed in PR 1.7). Any new owner-only function in `edu-profile.html` must call this guard first.

7. **`_applyEduOwnerMode(isOwner, snap)` is the only approved state controller** for edu-profile owner/guest UI transitions. Do not duplicate the show/hide logic outside this function. It handles both Revoke (isOwner=false) and Guest→Owner activation (isOwner=true) on token refresh.

8. **`edu-profile.html` `saveEdit()` must use live `snapshot.userId`**, not `_user.id`. The live userId is read from `TwAuthSync.getSessionSnapshot()` at call-time to close the account-switch race window. Both `PUT /profile/` and `PUT /auth/user/*/name` require `Authorization: Bearer` headers.

9. **Revocation is immediate.** On any non-carve-out session change: increment `_scOwnerHydrationGeneration`, clear `_scOwnerProfile`/`_scOwnerProfilePromise`, unconditionally set `_scViewerType = 'guest'`, remove `view-owner`/`preview-public-user`/`preview-guest`, add `view-guest`. Do NOT conditioned this on the `view-owner` class existing.

10. **Generation guard has five independent checks inside the hydration `.then()`** AND one check inside `.catch()` (see `VIEWER-MODES.md §VM-01-BFCACHE` for the full list). Do not remove any guard without an explicit architectural PR.

11. **Tests run real production code via Node.js `vm` module.** `@vm-extract-begin/end` markers in production files delimit extractable sections. Tests use `vm.runInContext(realCode, ctx)` to register the real handler, then call it directly. Rewriting handler logic inside the test file is permanently forbidden.

### Forbidden (VM-01-BFCACHE — permanent)

```
❌ bfcache carve-out that checks jwt presence only (must also check snapshot.userId === profileId)
❌ Preview mode used as an early-return to skip session revocation
❌ .catch() in owner hydration without generation guard
❌ _scOwnerHydrationGeneration redefined as boolean
❌ renderProfile non-owner path that skips clearing _scOwnerProfile/_scOwnerProfilePromise
❌ _isCurrentEduOwner() with localStorage fallback (fail-closed: no TwAuthSync → false)
❌ saveEdit() in edu-profile.html using _user.id instead of live snapshot.userId
❌ New owner mutation in edu-profile.html without _isCurrentEduOwner() guard
❌ PUT /profile/ or PUT /auth/user/*/name in edu-profile.html without Authorization header
❌ Parallel TwAuthSync.onSessionChange registration for the same page
❌ Deferring owner-mode revocation until after background fetch completes
❌ Reading snapshot.jwt (V2 TwAuthSync snapshot has no jwt field — use localStorage.getItem('tw_jwt'))
❌ Rewriting handler logic inside test_vm01_bfcache_runtime.js (must use vm module + @vm-extract markers)
```
