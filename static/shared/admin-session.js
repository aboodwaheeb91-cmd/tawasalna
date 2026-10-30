// admin-session.js — Admin Session Client (PR 1.5) — admin pages only (admin.html · admin-email.html · admin-view.html).
// The admin session token is a short-lived admin JWT returned by the admin login endpoint
// (POST <panel root>/login — task 5.3a; ≤ 1h, signed server-side with ADMIN_JWT_SECRET). It lives in sessionStorage
// (per tab, gone when the tab closes) and is sent as the X-Admin-Token header.
// Every admin API call goes through TwAdminSession.fetch(): a 401/403 (expired /
// invalid token) clears the token and fires the page's onExpired handler once —
// the page shows its login screen / message instead of hanging.
// opts.permissionAware (task 4.2 — admin-settings first): only 401 ends the session; a 403
// (valid token without the permission — check_admin) is returned to the page, which shows its
// own "no permission" message and keeps the session.
// The token is NEVER the raw ADMIN_TOKEN, and never touches localStorage.
// Step-up (task 8.4c-1 · docs/rules/admin-staff.md rule 11): an owner-only write / the export answers
// 428 {"error": "step_up_required"} → the handler TwAdminShell registers (onStepUp — DS-OVL code dialog →
// stepUp(code) → POST /admin/step-up) → the original request is sent again ONCE with X-Admin-Stepup.
// The grant lives in this script's memory only (never storage / URL) until it expires or the token changes.
(function () {
  'use strict';

  var KEY = 'tw_adm_token';
  var PANEL_KEY = 'tw_adm_panel';   // panel root path, written by TwAdminShell.start (task 5.3a)
  var EXPIRED_MSG = 'انتهت جلسة الإدارة (صلاحيتها ساعة واحدة) — سجّل الدخول من جديد.';
  var _handlers = [];
  var _timer = null;
  var _fired = false;
  var _grant = '', _grantExp = 0;   // step-up grant — memory only
  var _stepUpHandler = null;

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
    _grant = ''; _grantExp = 0;
    _schedule();
  }

  function clear() {
    if (_timer) { clearTimeout(_timer); _timer = null; }
    _grant = ''; _grantExp = 0;
    try { sessionStorage.removeItem(KEY); } catch (e) {}
  }

  function hasLiveToken() {
    var t = getToken();
    return !!t && _exp(t) * 1000 > Date.now();
  }

  function _liveGrant() { return _grant && _grantExp > Date.now() ? _grant : ''; }

  function headers() {
    var h = { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() };
    var g = _liveGrant();
    if (g) h['X-Admin-Stepup'] = g;
    return h;
  }

  // 428 step_up_required (owner-only write / export) — not a session end
  function _needsStepUp(r) {
    if (r.status !== 428 || typeof r.clone !== 'function') return Promise.resolve(false);
    return r.clone().json().then(function (d) { return !!d && d.error === 'step_up_required'; },
                                 function () { return false; });
  }

  // fetch with the admin header merged in; 401/403 → session over (permissionAware: 401 only);
  // 428 step_up_required → the step-up dialog, then the same request again once (cancelled → the 428 back).
  function adminFetch(url, opts) {
    opts = opts || {};
    var aware = !!opts.permissionAware;
    function send() {
      var h = headers();
      var extra = opts.headers || {};
      for (var k in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, k) && k !== 'X-Admin-Token' && k !== 'X-Admin-Stepup') h[k] = extra[k];
      }
      var init = Object.assign({}, opts, { headers: h });
      delete init.permissionAware;
      return fetch(url, init).then(function (r) {
        if (r.status === 401 || (r.status === 403 && !aware)) _expire();
        return r;
      });
    }
    return send().then(function (r) {
      if (!_stepUpHandler) return r;
      return _needsStepUp(r).then(function (need) {
        if (!need) return r;
        return Promise.resolve(_stepUpHandler()).then(function (ok) { return ok && _liveGrant() ? send() : r; },
                                                      function () { return r; });
      });
    });
  }

  // POST /admin/step-up {code} → {ok, status, remaining?}. ok → the grant is kept in memory for its lifetime.
  // A wrong code is 401 here — the dialog shows it; the session is NOT ended by this call.
  function stepUp(code) {
    return fetch('/admin/step-up', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() },
                                     body: JSON.stringify({ code: String(code || '') }) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (r.ok && d && typeof d.grant === 'string' && d.grant) {
            var ttl = Number(d.expires_in) > 0 ? Number(d.expires_in) : 300;
            _grant = d.grant;
            _grantExp = Date.now() + (ttl - 10) * 1000;   // a little early — never sent after the server's exp
            return { ok: true, status: r.status, remaining: d.recovery_remaining };
          }
          if (r.status === 401 && !hasLiveToken()) _expire();
          return { ok: false, status: r.status };
        });
      })
      .catch(function (e) { console.error('[TwAdminSession] step-up:', e); return { ok: false, status: 0 }; });
  }

  // Panel root for pages outside it (admin-view.html back link). Runtime value only — never in a file.
  function setPanelHref(path) {
    if (!/^\/[A-Za-z0-9_-]+$/.test(String(path || ''))) return;
    try { sessionStorage.setItem(PANEL_KEY, path); } catch (e) { console.error('[TwAdminSession] panel write failed:', e); }
  }
  function panelHref() {
    var p = '';
    try { p = sessionStorage.getItem(PANEL_KEY) || ''; } catch (e) { return ''; }
    return /^\/[A-Za-z0-9_-]+$/.test(p) ? p : '';
  }

  window.TwAdminSession = {
    EXPIRED_MSG: EXPIRED_MSG,
    getToken: getToken,
    setToken: setToken,
    clear: clear,
    hasLiveToken: hasLiveToken,
    headers: headers,
    fetch: adminFetch,
    setPanelHref: setPanelHref,
    panelHref: panelHref,
    stepUp: stepUp,
    hasStepUp: function () { return !!_liveGrant(); },
    onStepUp: function (fn) { _stepUpHandler = fn; },
    onExpired: function (cb) { _handlers.push(cb); }
  };

  _schedule(true);
}());
