// admin-session.js — Admin Session Client (PR 1.5) — admin pages only (admin.html · admin-view.html).
// The admin session token is a short-lived admin JWT returned by POST /tw-ctrl-login
// (≤ 1h, signed server-side with ADMIN_JWT_SECRET). It lives in sessionStorage
// (per tab, gone when the tab closes) and is sent as the X-Admin-Token header.
// Every admin API call goes through TwAdminSession.fetch(): a 401/403 (expired /
// invalid token) clears the token and fires the page's onExpired handler once —
// the page shows its login screen / message instead of hanging.
// The token is NEVER the raw ADMIN_TOKEN, and never touches localStorage.
(function () {
  'use strict';

  var KEY = 'tw_adm_token';
  var EXPIRED_MSG = 'انتهت جلسة الإدارة (صلاحيتها ساعة واحدة) — سجّل الدخول من جديد.';
  var _handlers = [];
  var _timer = null;
  var _fired = false;

  function getToken() {
    try { return sessionStorage.getItem(KEY) || ''; } catch (e) { return ''; }
  }

  function _exp(token) {
    try {
      var b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      while (b64.length % 4) b64 += '=';
      var c = JSON.parse(atob(b64));
      return (typeof c.exp === 'number' && isFinite(c.exp)) ? c.exp : 0;
    } catch (e) { return 0; }
  }

  function _expire() {
    clear();
    if (_fired) return;
    _fired = true;
    for (var i = 0; i < _handlers.length; i++) {
      try { _handlers[i](EXPIRED_MSG); } catch (e) { console.error('[TwAdminSession] onExpired handler:', e); }
    }
  }

  // Proactive: fire at exp even if the admin makes no request (UI never sits on a dead session).
  function _schedule(initial) {
    if (_timer) { clearTimeout(_timer); _timer = null; }
    var exp = _exp(getToken());
    if (!exp) return;
    var ms = exp * 1000 - Date.now();
    // On load no page handler is registered yet: just drop a dead token (page shows login).
    if (ms <= 0) { if (initial) clear(); else _expire(); return; }
    _timer = setTimeout(_expire, Math.min(ms, 0x7FFFFFFF));
  }

  function setToken(token) {
    try { sessionStorage.setItem(KEY, token); }
    catch (e) { console.error('[TwAdminSession] token write failed:', e); }
    _fired = false;
    _schedule();
  }

  function clear() {
    if (_timer) { clearTimeout(_timer); _timer = null; }
    try { sessionStorage.removeItem(KEY); } catch (e) {}
  }

  function hasLiveToken() {
    var t = getToken();
    return !!t && _exp(t) * 1000 > Date.now();
  }

  function headers() {
    return { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() };
  }

  // fetch with the admin header merged in; 401/403 → session over.
  function adminFetch(url, opts) {
    opts = opts || {};
    var h = headers();
    var extra = opts.headers || {};
    for (var k in extra) { if (Object.prototype.hasOwnProperty.call(extra, k) && k !== 'X-Admin-Token') h[k] = extra[k]; }
    return fetch(url, Object.assign({}, opts, { headers: h })).then(function (r) {
      if (r.status === 401 || r.status === 403) _expire();
      return r;
    });
  }

  window.TwAdminSession = {
    EXPIRED_MSG: EXPIRED_MSG,
    getToken: getToken,
    setToken: setToken,
    clear: clear,
    hasLiveToken: hasLiveToken,
    headers: headers,
    fetch: adminFetch,
    onExpired: function (cb) { _handlers.push(cb); }
  };

  _schedule(true);
}());
