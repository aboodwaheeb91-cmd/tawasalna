// static/staff-link/staff-link.js — staff link pages (task 8.4c-2b-1 · docs/rules/admin-staff.md rule 15)
//   /staff/invite          start → QR + key → password + confirm + code → complete → recovery codes → panel link
//   /staff/mfa-reset       start → QR + key → code → complete → recovery codes → "sign in with your panel link"
//   /staff/password-reset  password + confirm → complete → "password changed; the login still asks for the app code"
// Token: read from #t= ONCE, then history.replaceState removes the fragment before any request. It lives in this
// closure only and is sent only in the POST body — never storage, never the URL, never console. No #t= → the
// "invalid link" message and no request at all. The server decides everything (password length too — the hint here
// only helps). API: twApi (auth:false — no user session on this page) · QR + codes box: TwOtpUi (shared with the
// owner's first-time binding on the admin login).
(function () {
  'use strict';

  var MODES = {
    '/staff/invite':         { api: '/staff/invite',         bind: true,  password: true,  panel: true,  ask: 'staff.link.err.ask_owner' },
    '/staff/mfa-reset':      { api: '/staff/mfa-reset',      bind: true,  password: false, panel: false, ask: 'staff.link.err.ask_owner' },
    '/staff/password-reset': { api: '/staff/password-reset', bind: false, password: true,  panel: false, ask: 'staff.link.err.ask_forgot' }
  };
  var KEY = { '/staff/invite': 'invite', '/staff/mfa-reset': 'mfa', '/staff/password-reset': 'password' };
  var TOKEN_RE = /^[A-Za-z0-9_-]{20,200}$/;
  var PANEL_RE = /^\/[A-Za-z0-9_-]{1,200}$/;
  var CODE_ERRORS = ['invalid_code', 'invalid_code_format', 'weak_password', 'password_too_long'];

  var S = { token: '', mode: null, key: '', busy: false };

  function $(id) { return document.getElementById(id); }

  // #t=<token> → the token ('' when absent / malformed). The fragment leaves the address bar first, whatever it holds.
  function takeToken() {
    var h = String(location.hash || '');
    if (h) { try { history.replaceState(null, '', location.pathname); } catch (e) {} }
    var m = /^#t=(.*)$/.exec(h);
    return m && TOKEN_RE.test(m[1]) ? m[1] : '';
  }

  function minLen() { return twLimit('staff_password_min') || 12; }
  function maxBytes() { return twLimit('password_max_bytes') || 72; }

  function errText(res) {
    var code = res && res.raw && res.raw.error && typeof res.raw.error === 'object' ? res.raw.error.code : '';
    if (res && res.status === 429) return { code: 'rate', text: twT('staff.link.err.rate') };
    if (code === 'invalid_link') return { code: code, text: twT('staff.link.err.invalid_link') + ' ' + twT(S.mode.ask) };
    if (CODE_ERRORS.indexOf(code) !== -1) {
      return { code: code, text: twT('admin.staff.error.' + code, { min: twFormatNumber(minLen()), max: twFormatNumber(maxBytes()) }) };
    }
    return { code: 'generic', text: twT('staff.link.err.generic') };
  }

  // A dead link: message + who to ask; nothing secret stays on the page.
  function dead(text) {
    S.token = '';
    TwOtpUi.clear($('slBind'));
    $('slForm').hidden = true;
    $('slRetry').hidden = true;
    $('slHint').textContent = '';
    $('slMsg').textContent = text;
  }

  function showForm() {
    var m = S.mode;
    $('slPassRow').hidden = !m.password;
    $('slPass2Row').hidden = !m.password;
    $('slPassHint').hidden = !m.password;
    $('slPassHint').textContent = m.password ? twT('staff.link.password_hint', { min: twFormatNumber(minLen()) }) : '';
    $('slCodeRow').hidden = !m.bind;
    $('slSubmit').textContent = twT('staff.link.' + S.key + '.submit');
    $('slErr').textContent = '';
    $('slForm').hidden = false;
    var first = m.password ? $('slPass') : $('slCode');
    try { first.focus(); } catch (e) {}
  }

  function start() {
    if (S.busy || !S.token) return;
    S.busy = true;
    $('slRetry').hidden = true;
    $('slMsg').textContent = '';
    twApi(S.mode.api + '/start', { method: 'POST', auth: false, body: { token: S.token } }).then(function (res) {
      S.busy = false;
      var d = (res.ok && res.data) || null;
      if (d && TwOtpUi.binding($('slBind'), { secret: d.secret, uri: d.otpauth_uri })) {
        if (d.name) $('slTitle').textContent = twT('staff.link.' + S.key + '.title_name', { name: String(d.name) });
        showForm();
        return;
      }
      var e = res.ok ? { code: 'generic', text: twT('staff.link.err.generic') } : errText(res);
      if (e.code === 'invalid_link') { dead(e.text); return; }
      $('slMsg').textContent = e.text;
      $('slRetry').hidden = false;   // 429 / network / 500 — the token is still in memory, try again
    });
  }

  function submit(ev) {
    ev.preventDefault();
    if (S.busy || !S.token) return;
    var m = S.mode, body = { token: S.token }, err = $('slErr');
    err.textContent = '';
    if (m.password) {
      var p = $('slPass').value, p2 = $('slPass2').value;
      if (!p) { err.textContent = twT('staff.link.err.password_empty'); return; }
      if (p !== p2) { err.textContent = twT('staff.link.err.mismatch'); return; }
      body.password = p;
    }
    if (m.bind) {
      var c = $('slCode').value.replace(/\s+/g, '');
      if (!/^\d{6}$/.test(c)) { err.textContent = twT('admin.staff.error.invalid_code_format'); return; }
      body.code = c;
    }
    S.busy = true;
    $('slSubmit').disabled = true;
    twApi(m.api + '/complete', { method: 'POST', auth: false, body: body }).then(function (res) {
      S.busy = false;
      $('slSubmit').disabled = false;
      if (!res.ok) {
        var e = errText(res);
        if (e.code === 'invalid_link') { dead(e.text); return; }
        if (e.code === 'invalid_code' || e.code === 'invalid_code_format') $('slCode').value = '';
        err.textContent = e.text;
        return;
      }
      completed((res.data) || {});
    });
  }

  function completed(d) {
    S.token = '';
    $('slPass').value = ''; $('slPass2').value = ''; $('slCode').value = '';
    TwOtpUi.clear($('slBind'));
    $('slBox').hidden = true;
    var panel = S.mode.panel && typeof d.panel === 'string' && PANEL_RE.test(d.panel) ? d.panel : '';
    if (S.mode.bind) {
      var box = $('slCodes');
      box.hidden = false;
      TwOtpUi.codes(box, d.recovery_codes, function () { box.hidden = true; finish(panel); });
      return;
    }
    finish(panel);
  }

  function finish(panel) {
    $('slDoneTitle').textContent = twT('staff.link.' + S.key + '.done_title');
    $('slDoneText').textContent = twT('staff.link.' + S.key + '.done_text');
    if (panel) {
      var url = location.origin + panel;
      $('slPanelUrl').textContent = url;
      $('slPanelGo').setAttribute('href', panel);
      $('slPanelCopy').onclick = function () { TwOtpUi.copy(url, 'staff.link.panel_copied'); };
      $('slPanel').hidden = false;
    }
    $('slDone').hidden = false;
  }

  function boot() {
    document.title = twT('page.title', { page: twT('staff.link.page') });
    var logo = document.querySelector('.adm-login-logo');
    if (logo) logo.alt = twT('brand.name');
    var path = String(location.pathname || '').replace(/\/+$/, '');
    S.mode = MODES[path] || null;
    S.key = KEY[path] || 'invite';
    S.token = takeToken();
    $('slTitle').textContent = twT('staff.link.' + S.key + '.title');
    if (!S.mode || !S.token) {
      if (!S.mode) S.mode = MODES['/staff/invite'];
      dead(twT('staff.link.err.invalid_link') + ' ' + twT(S.mode.ask));
      return;
    }
    $('slHint').textContent = twT('staff.link.' + S.key + '.hint');
    $('slForm').addEventListener('submit', submit);
    $('slRetry').addEventListener('click', start);
    if (S.mode.bind) start();
    else showForm();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}());
