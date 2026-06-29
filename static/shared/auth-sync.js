// auth-sync.js — Cross-tab session invalidation
// Fires registered callbacks when tw_jwt changes in any tab,
// on bfcache restore (pageshow), or when tab regains focus.
// Safe to load on any page; no-op until TwAuthSync.onSessionChange() is called.
(function () {
  'use strict';

  var _prevJwt  = localStorage.getItem('tw_jwt') || '';
  var _handlers = [];

  function _currentJwt() {
    return localStorage.getItem('tw_jwt') || '';
  }

  function _check(reason, force) {
    var jwt = _currentJwt();
    if (!force && jwt === _prevJwt) return;
    _prevJwt = jwt;
    for (var i = 0; i < _handlers.length; i++) {
      try { _handlers[i]({ jwt: jwt, reason: reason }); } catch (e) {}
    }
  }

  // Another tab modified localStorage — fires only in OTHER tabs
  window.addEventListener('storage', function (e) {
    if (e.key === 'tw_jwt' || e.key === 'tw_user' || e.key === null) {
      _check('storage');
    }
  });

  // bfcache restoration — always fire; page may be stale regardless of JWT value
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) _check('pageshow', true);
  });

  // Tab becomes visible after being hidden (user switched back)
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') _check('visibilitychange');
  });

  // Window gains focus (e.g. user switches OS windows)
  window.addEventListener('focus', function () { _check('focus'); });

  window.TwAuthSync = {
    onSessionChange: function (cb) { _handlers.push(cb); },
  };
}());
