// static/support/support-track.js — /support/track, the guest follow-up page (task 7.2a واجهة · 7.4 · docs/rules/support.md)
//   - the link token: location.hash (#t=…) read once → history.replaceState removes it from the address bar →
//     sessionStorage (one key, STORE_KEY) + the POST body only (never a query string)
//   - the link names the ticket only (7.4): POST /support/track/view {token} → H number + masked email → «أرسل الرمز»
//     (/code {token}, disabled until the reply) + the code → /verify {token, code} → {session} (sessionStorage)
//   - session → POST /support/track/view {session} → status · messages · reply (/reply) · «تم الحل» (/resolve,
//     twConfirm first) · 401 → back to the code screen · a refresh keeps the session (same tab)
//   - no link and no session → «افتح الرابط من الإيميل» · 404 (wrong · expired · revoked — one answer) → one
//     general text + «إعادة إرسال الرابط»
//   - twApi {auth:false} only · every text through textContent (never innerHTML)
(function () {
  'use strict';
  var F = window.TwSupportForm, el = F.el;
  var STORE_KEY = 'tw_support_track';
  var root = document.getElementById('stRoot');

  function read() {
    try { return JSON.parse(sessionStorage.getItem(STORE_KEY) || '{}') || {}; } catch (e) { return {}; }
  }
  function write(st) {
    try {
      if (st.t || st.s) sessionStorage.setItem(STORE_KEY, JSON.stringify(st));
      else sessionStorage.removeItem(STORE_KEY);
    } catch (e) { console.warn('[support-track] storage failed:', e); }
  }

  var state = read();
  var m = /^#t=([A-Za-z0-9_-]+)$/.exec(location.hash || '');
  if (m && m[1] !== state.t) state = { t: m[1] };   // another link = another ticket → the old session goes
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);
  write(state);

  document.title = twT('page.title', { page: twT('support.track.title') });
  twTApply(document.body);
  if (window.twIcon && twIcon.hydrate) twIcon.hydrate(document.body);

  function post(action, body) {
    return twApi('/support/track/' + action, { method: 'POST', auth: false, body: body });
  }
  function withSession(action, body) {
    body = body || {};
    body.session = state.s;
    return post(action, body).then(function (res) {
      if (res.status === 401) expired();
      return res;
    });
  }
  function expired() {
    state.s = '';
    write(state);
    load();
  }

  function card(box) {
    root.textContent = '';
    var c = el('div', 'sp-card');
    c.appendChild(box);
    root.appendChild(c);
  }

  function resendBlock(box) {
    var link = F.button('support.track.resend', 'sp-link');
    var form = F.resendForm();
    form.hidden = true;
    link.addEventListener('click', function () { form.hidden = !form.hidden; });
    box.appendChild(link);
    box.appendChild(form);
  }

  function notFound(res) {
    state = {};
    write(state);
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('support.error.track_not_found'))));
    resendBlock(box);
    card(box);
  }

  function noLink() {
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-hint', twT('support.track.open_from_email')));
    resendBlock(box);
    card(box);
  }

  function codeScreen(info) {
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-hint', twT('support.track.code_intro', { ticket: info.ticket || '', email: info.email || '' })));
    var fields = { code: F.field({ labelKey: 'support.guest.code', required: true, ltr: true, inputMode: 'numeric',
                                   autocomplete: 'one-time-code', max: 12 }) };
    box.appendChild(fields.code.wrap);
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    box.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var send = F.button('support.track.send_code', 'tw-btn tw-btn-ghost');
    var verify = F.button('support.track.verify');
    actions.appendChild(send);
    actions.appendChild(verify);
    box.appendChild(actions);

    send.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      send.disabled = true;
      post('code', { token: state.t }).then(function (res) {
        send.disabled = false;
        if (!res.ok) { F.serverError(res, fields, msg); return; }
        send.textContent = twT('support.track.resend_code');
        msg.textContent = twT('support.track.code_sent', { minutes: (res.data && res.data.minutes) || '' });
        msg.className = 'sp-msg is-ok';
        if (fields.code.input.focus) fields.code.input.focus();
      });
    });
    verify.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      if (!F.requiredOk(fields)) return;
      verify.disabled = true;
      post('verify', { token: state.t, code: fields.code.input.value.trim() }).then(function (res) {
        verify.disabled = false;
        if (res.status === 404) { notFound(res); return; }
        if (!res.ok || !res.data || !res.data.session) { F.serverError(res, fields, msg); return; }
        state.s = res.data.session;
        write(state);
        load();
      });
    });
    card(box);
  }

  function failed(res) {
    root.textContent = '';
    root.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
  }

  function load() {
    if (state.s) {
      withSession('view').then(function (res) {
        if (res.status === 401) return;                 // expired() already went back to the code screen
        if (!res.ok || !res.data) { failed(res); return; }
        root.textContent = '';
        root.appendChild(F.thread(res.data, {
          reply: function (body) { return withSession('reply', { body: body }); },
          resolve: function () { return withSession('resolve'); },
          reload: load,
        }));
      });
      return;
    }
    if (!state.t) { noLink(); return; }
    post('view', { token: state.t }).then(function (res) {
      if (res.status === 404) { notFound(res); return; }
      if (!res.ok || !res.data) { failed(res); return; }
      codeScreen(res.data);
    });
  }

  load();
})();
