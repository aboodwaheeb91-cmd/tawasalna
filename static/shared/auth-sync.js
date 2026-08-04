// auth-sync.js V2 — Session Resolver + Cross-tab Invalidation
// VM-10 compliant (docs/design-system/VIEWER-MODES.md)
// Fires registered callbacks when tw_jwt or tw_user changes in any tab,
// on bfcache restore (pageshow), or when tab regains focus.
// V2 adds: getSessionSnapshot(), invalidateSession(), JWT expiry timer,
//          session fingerprinting (tw_user change detection),
//          mismatch detection (JWT user_id vs tw_user.id → stale).
// Safe to load on any page; no-op until TwAuthSync methods are called.
(function () {
  'use strict';

  // Explicit allowlist — only true session keys are wiped on invalidation.
  // startsWith('tw_') is forbidden: would destroy user preferences (tw_cover_edu_*, etc.)
  var _SESSION_KEYS = ['tw_jwt', 'tw_user'];

  // Fingerprint both tokens at init time so any change triggers callbacks.
  var _prevJwt     = localStorage.getItem('tw_jwt')  || '';
  var _prevUserStr = localStorage.getItem('tw_user') || '';
  var _handlers    = [];
  var _expiryTimer = null;

  // setTimeout is capped at 32-bit signed int (~24.8 days).
  // 7-day tokens produce ~604 800 000 ms — well inside the cap, but we clamp
  // defensively in case a future token lifetime exceeds 24 days.
  var _MAX_TIMEOUT_MS = 0x7FFFFFFF;

  // ── JWT parsing ──────────────────────────────────────────────────
  function _parseJwtPayload(jwt) {
    if (!jwt) return null;
    try {
      var parts = jwt.split('.');
      if (parts.length !== 3) return null;
      var b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      while (b64.length % 4) b64 += '=';
      return JSON.parse(atob(b64));
    } catch (e) { return null; }
  }

  // ── Session state resolver ───────────────────────────────────────
  // Returns: { state, isAuthenticated, userType, userId, reason }
  //
  // State machine (exact order per VM-10A):
  //   1. no jwt AND no tw_user                          → guest
  //   2. tw_user present but no jwt                     → stale   (partial session — jwt was cleared without user)
  //   3. jwt present but unparseable                    → invalid
  //   4. jwt.user_id missing or null                    → invalid  (server.py always sets user_id)
  //   5. jwt.user_type missing or null                  → invalid  (server.py always sets user_type)
  //   6. jwt.exp missing, non-numeric, or non-finite    → invalid
  //   7. jwt.exp <= now                                 → expired  (<= catches exp exactly equal to now)
  //   8. tw_user absent or missing .id                  → stale
  //   9. jwt.user_id ≠ tw_user.id                       → stale   (account switch mid-session)
  //  10. jwt.user_type ≠ tw_user.user_type              → stale
  //  11. all checks pass                                → authenticated
  function _resolveSession() {
    var jwt     = localStorage.getItem('tw_jwt')  || '';
    var userStr = localStorage.getItem('tw_user') || '';

    var user = null;
    try { user = JSON.parse(userStr || 'null'); } catch (e) {}
    var hasUser = !!(user && user.id);

    // 1. No session data at all → guest
    if (!jwt && !hasUser) {
      return { state: 'guest', isAuthenticated: false, userType: null, userId: null, reason: 'no_jwt' };
    }
    // 2. tw_user present but JWT missing → stale
    if (!jwt && hasUser) {
      return { state: 'stale', isAuthenticated: false, userType: null, userId: null, reason: 'no_jwt_with_user' };
    }
    // 3. JWT present — validate structure
    var claims = _parseJwtPayload(jwt);
    if (!claims) {
      return { state: 'invalid', isAuthenticated: false, userType: null, userId: null, reason: 'malformed_jwt' };
    }
    // 4. user_id MUST be present (server.py _jwt_encode always sets it)
    if (claims.user_id === undefined || claims.user_id === null) {
      return { state: 'invalid', isAuthenticated: false, userType: null, userId: null, reason: 'missing_user_id' };
    }
    // 5. user_type MUST be present
    if (claims.user_type === undefined || claims.user_type === null) {
      return { state: 'invalid', isAuthenticated: false, userType: null, userId: null, reason: 'missing_user_type' };
    }
    // 6. exp MUST be a finite numeric Unix timestamp
    if (typeof claims.exp !== 'number' || !isFinite(claims.exp)) {
      return { state: 'invalid', isAuthenticated: false, userType: null, userId: null, reason: 'missing_exp' };
    }
    // 7. Token expiry check — <= to catch exp exactly equal to current second
    var now = Math.floor(Date.now() / 1000);
    if (claims.exp <= now) {
      return { state: 'expired', isAuthenticated: false, userType: null, userId: null, reason: 'jwt_expired' };
    }
    // 8. JWT valid — check tw_user
    if (!hasUser) {
      return { state: 'stale', isAuthenticated: false, userType: null, userId: null, reason: 'no_user_object' };
    }
    // 9-10. Cross-check JWT claims against tw_user
    if (String(claims.user_id) !== String(user.id)) {
      return { state: 'stale', isAuthenticated: false, userType: null, userId: null, reason: 'user_id_mismatch' };
    }
    if (claims.user_type !== user.user_type) {
      return { state: 'stale', isAuthenticated: false, userType: null, userId: null, reason: 'user_type_mismatch' };
    }
    // 11. All checks pass
    return {
      state: 'authenticated',
      isAuthenticated: true,
      userType: user.user_type || null,
      userId: user.id,
      reason: 'ok'
    };
  }

  // ── Expiry timer — fires once at token expiry time ───────────────
  function _scheduleExpiryTimer() {
    if (_expiryTimer) { clearTimeout(_expiryTimer); _expiryTimer = null; }
    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!jwt) return;
    var claims = _parseJwtPayload(jwt);
    if (!claims || typeof claims.exp !== 'number' || !isFinite(claims.exp)) return;
    var now    = Math.floor(Date.now() / 1000);
    var msLeft = (claims.exp - now) * 1000 + 500;
    if (msLeft <= 0) return;
    msLeft = Math.min(msLeft, _MAX_TIMEOUT_MS);
    _expiryTimer = setTimeout(function () {
      _expiryTimer = null;
      // Guard: if JWT was renewed while timer slept, reschedule instead of expiring
      var fresh = _parseJwtPayload(localStorage.getItem('tw_jwt') || '');
      if (fresh && typeof fresh.exp === 'number' && isFinite(fresh.exp)
          && fresh.exp > Math.floor(Date.now() / 1000)) {
        _scheduleExpiryTimer();
        return;
      }
      _check('jwt_expired', true);
    }, msLeft);
  }

  // ── Core check — fires handlers when session changes ─────────────
  // Detects BOTH jwt changes and tw_user changes (session fingerprint).
  function _check(reason, force) {
    var jwt     = localStorage.getItem('tw_jwt')  || '';
    var userStr = localStorage.getItem('tw_user') || '';
    if (!force && jwt === _prevJwt && userStr === _prevUserStr) return;
    _prevJwt     = jwt;
    _prevUserStr = userStr;
    _scheduleExpiryTimer();
    var snapshot = _resolveSession();
    for (var i = 0; i < _handlers.length; i++) {
      try { _handlers[i]({ jwt: jwt, reason: reason, snapshot: snapshot }); } catch (e) {}
    }
  }

  // Schedule initial expiry timer on load
  _scheduleExpiryTimer();

  // ── Cross-tab events ─────────────────────────────────────────────
  window.addEventListener('storage', function (e) {
    if (e.key === 'tw_jwt' || e.key === 'tw_user' || e.key === null) {
      _check('storage');
    }
  });

  // bfcache restoration — always fire regardless of fingerprint
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) _check('pageshow', true);
  });

  // Tab becomes visible — re-check in case timer fired while page was hidden
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') _check('visibilitychange', true);
  });

  // OS window focus
  window.addEventListener('focus', function () { _check('focus', true); });

  // ── Public API ───────────────────────────────────────────────────
  window.TwAuthSync = {
    // Backward-compatible: callback receives { jwt, reason, snapshot }
    // snapshot is new in V2; legacy callbacks that ignore extra fields still work.
    onSessionChange: function (cb) { _handlers.push(cb); },

    // Returns the current session snapshot synchronously.
    // Never throws; always returns a valid snapshot object.
    getSessionSnapshot: function () { return _resolveSession(); },

    // Clears session keys (allowlist only), cancels expiry timer,
    // fires handlers with a guest snapshot, then optionally redirects.
    // opts: { redirect: '/login' }
    invalidateSession: function (reason, opts) {
      opts = opts || {};
      try {
        for (var i = 0; i < _SESSION_KEYS.length; i++) {
          localStorage.removeItem(_SESSION_KEYS[i]);
        }
      } catch (e) {}
      if (_expiryTimer) { clearTimeout(_expiryTimer); _expiryTimer = null; }
      _prevJwt     = '';
      _prevUserStr = '';
      var snapshot = _resolveSession(); // will be 'guest' — storage was just cleared
      for (var i = 0; i < _handlers.length; i++) {
        try { _handlers[i]({ jwt: '', reason: reason || 'invalidate', snapshot: snapshot }); } catch (e) {}
      }
      if (opts.redirect) {
        window.location.href = opts.redirect;
      }
    },
  };
}());
