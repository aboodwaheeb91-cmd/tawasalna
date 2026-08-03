// auth-sync.js V2 — Session Resolver + Cross-tab Invalidation
// VM-10 compliant (docs/design-system/VIEWER-MODES.md)
// Fires registered callbacks when tw_jwt changes in any tab,
// on bfcache restore (pageshow), or when tab regains focus.
// V2 adds: getSessionSnapshot(), invalidateSession(), JWT expiry timer.
// Safe to load on any page; no-op until TwAuthSync methods are called.
(function () {
  'use strict';

  var _prevJwt     = localStorage.getItem('tw_jwt') || '';
  var _handlers    = [];
  var _expiryTimer = null;

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
  // States: guest | authenticated | expired | invalid | stale
  function _resolveSession() {
    var jwt  = localStorage.getItem('tw_jwt') || '';
    if (!jwt) {
      return { state: 'guest', isAuthenticated: false, userType: null, userId: null, reason: 'no_jwt' };
    }
    var claims = _parseJwtPayload(jwt);
    if (!claims) {
      return { state: 'invalid', isAuthenticated: false, userType: null, userId: null, reason: 'malformed_jwt' };
    }
    var now = Math.floor(Date.now() / 1000);
    if (claims.exp && claims.exp < now) {
      return { state: 'expired', isAuthenticated: false, userType: null, userId: null, reason: 'jwt_expired' };
    }
    var user = null;
    try { user = JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch (e) {}
    if (!user || !user.id) {
      return { state: 'stale', isAuthenticated: false, userType: null, userId: null, reason: 'no_user_object' };
    }
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
    if (!claims || !claims.exp) return;
    var now  = Math.floor(Date.now() / 1000);
    var msLeft = (claims.exp - now) * 1000 + 500;
    if (msLeft <= 0) return;
    _expiryTimer = setTimeout(function () {
      _expiryTimer = null;
      _check('jwt_expired', true);
    }, msLeft);
  }

  // ── Core check — fires handlers when session changes ─────────────
  function _check(reason, force) {
    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!force && jwt === _prevJwt) return;
    _prevJwt = jwt;
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

  // bfcache restoration — always fire regardless of JWT value
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) _check('pageshow', true);
  });

  // Tab becomes visible again
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') _check('visibilitychange');
  });

  // Window focus (OS window switch)
  window.addEventListener('focus', function () { _check('focus'); });

  // ── Public API ───────────────────────────────────────────────────
  window.TwAuthSync = {
    // Backward-compatible: callback receives { jwt, reason, snapshot }
    // snapshot is new in V2; legacy callbacks that ignore extra fields still work.
    onSessionChange: function (cb) { _handlers.push(cb); },

    // Returns the current session snapshot synchronously.
    // Never throws; always returns a valid snapshot object.
    getSessionSnapshot: function () { return _resolveSession(); },

    // Clears all tw_* localStorage keys, fires handlers, then optionally redirects.
    // opts: { redirect: '/login' }
    invalidateSession: function (reason, opts) {
      opts = opts || {};
      try {
        Object.keys(localStorage)
          .filter(function (k) { return k.startsWith('tw_'); })
          .forEach(function (k) { localStorage.removeItem(k); });
      } catch (e) {}
      if (_expiryTimer) { clearTimeout(_expiryTimer); _expiryTimer = null; }
      _prevJwt = '';
      var snapshot = _resolveSession(); // will be 'guest'
      for (var i = 0; i < _handlers.length; i++) {
        try { _handlers[i]({ jwt: '', reason: reason || 'invalidate', snapshot: snapshot }); } catch (e) {}
      }
      if (opts.redirect) {
        window.location.href = opts.redirect;
      }
    },
  };
}());
