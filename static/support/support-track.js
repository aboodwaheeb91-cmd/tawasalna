// static/support/support-track.js — /support/track, the guest follow-up page (task 7.2a واجهة · 7.4 · docs/rules/support.md)
//   - the link token: location.hash (#t=…) read once → history.replaceState removes it from the address bar →
//     sessionStorage (one key, with the session) → sent in the POST body only (never a query string)
//   - the link only NAMES the ticket (7.4): POST /support/track/view {token} → H number + masked address →
//     «أرسل الرمز» (/code — disabled until the reply, then the cooldown counts down) → code → /verify → {session}
//   - the session (sessionStorage — a reload keeps it) → /view {session, token} → messages · reply · «تم الحل»
//     (twConfirm first) — reply / resolve {session} only; 401 → the session dropped → back to the code screen
//   - a new link with a session (7.5b): both kept, /view {session, token} — the server opens the conversation
//     only when the session is of the link's ticket, else 401 (never a session on another ticket)
//   - no link and no session → «افتح الرابط من الإيميل» · 404 (wrong · expired · revoked link) → general text
//     + «إعادة إرسال الرابط»
//   - twApi {auth:false} only · every text through textContent (never innerHTML)
(function () {
  'use strict';
  var F = window.TwSupportForm, el = F.el;
  var root = document.getElementById('stRoot');
  var KEY = 'tw_support_track';   // {t: link token, s: session} — this tab only

  function readStore() {
    try {
      var v = JSON.parse(sessionStorage.getItem(KEY) || '{}');
      return v && typeof v === 'object' ? v : {};
    } catch (e) { return {}; }
  }
  function writeStore() {
    try { sessionStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { /* storage blocked — memory only */ }
  }

  var st = readStore();
  var m = /^#t=([A-Za-z0-9_-]+)$/.exec(location.hash || '');
  // a new link keeps the session (7.5b): /view sends both and the SERVER decides — same ticket → the
  // conversation, anything else → 401 → the session is dropped and the link alone names its ticket
  if (m && m[1] !== st.t) { st.t = m[1]; writeStore(); }
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);

  document.title = twT('page.title', { page: twT('support.track.title') });
  twTApply(document.body);
  if (window.twIcon && twIcon.hydrate) twIcon.hydrate(document.body);

  function post(action, body) {
    return twApi('/support/track/' + action, { method: 'POST', auth: false, body: body });
  }

  function show(card) {
    root.textContent = '';
    root.appendChild(card);
  }

  function resendBox(box) {
    var link = F.button('support.track.resend', 'sp-link');
    var form = F.resendForm();
    form.hidden = true;
    link.addEventListener('click', function () { form.hidden = !form.hidden; });
    box.appendChild(link);
    box.appendChild(form);
  }

  function notice(text) {
    var card = el('div', 'sp-card');
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-msg is-error', text));
    resendBox(box);
    card.appendChild(box);
    show(card);
  }

  function notFound(res) {
    notice(res ? twApiMessage(res, twT('support.error.track_not_found')) : twT('support.error.track_not_found'));
  }

  function openFromEmail() {
    var card = el('div', 'sp-card');
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-msg', twT('support.track.open_from_email')));
    resendBox(box);
    card.appendChild(box);
    show(card);
  }

  function failed(res) {
    root.textContent = '';
    root.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
  }

  // the session ended (401) → forget it, back to the code screen of the link (or «افتح الرابط»)
  function expired() {
    delete st.s;
    writeStore();
    load();
  }

  function codeScreen(info) {
    var card = el('div', 'sp-card');
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-hint', twT('support.track.code_intro', { ticket: info.ticket, email: info.email })));
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    var send = F.button('support.track.send_code', 'tw-btn tw-btn-ghost');
    var fields = { code: F.field({ labelKey: 'support.guest.code', required: true, ltr: true, max: 12,
                                   inputMode: 'numeric', autocomplete: 'one-time-code' }) };
    var verify = F.button('support.track.verify');
    var actions = el('div', 'sp-actions');
    actions.appendChild(send);
    box.appendChild(actions);
    box.appendChild(fields.code.wrap);
    box.appendChild(msg);
    var actions2 = el('div', 'sp-actions');
    actions2.appendChild(verify);
    box.appendChild(actions2);
    card.appendChild(box);

    function countdown(seconds) {
      if (seconds <= 0) {
        send.disabled = false;
        send.textContent = twT('support.track.send_code');
        return;
      }
      send.disabled = true;
      send.textContent = twT('support.track.code_wait', { seconds: seconds });
      setTimeout(function () { countdown(seconds - 1); }, 1000);
    }

    send.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      send.disabled = true;
      post('code', { token: st.t }).then(function (res) {
        if (!res.ok) { send.disabled = false; F.serverError(res, fields, msg); return; }
        msg.textContent = twT('support.track.code_sent', { minutes: res.data && res.data.minutes });
        msg.className = 'sp-msg is-ok';
        countdown(Number(res.data && res.data.cooldown_s) || 0);
      });
    });

    verify.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      if (!F.requiredOk(fields)) return;
      verify.disabled = true;
      post('verify', { token: st.t, code: fields.code.input.value.trim() }).then(function (res) {
        verify.disabled = false;
        if (res.status === 404) { notFound(res); return; }
        if (!res.ok || !res.data || !res.data.session) { F.serverError(res, fields, msg); return; }
        st.s = res.data.session;
        writeStore();
        load();
      });
    });
    show(card);
  }

  function withSession(action, body) {
    body = body || {};
    body.session = st.s;
    return post(action, body).then(function (res) {
      if (res.status === 401) expired();
      return res;
    });
  }

  function load() {
    if (st.s) {
      post('view', st.t ? { session: st.s, token: st.t } : { session: st.s }).then(function (res) {
        if (res.status === 401) { expired(); return; }
        if (!res.ok || !res.data) { failed(res); return; }
        show(F.thread(res.data, {
          reply: function (body) { return withSession('reply', { body: body }); },
          resolve: function () { return withSession('resolve'); },
          reload: load,
        }));
      });
      return;
    }
    if (!st.t) { openFromEmail(); return; }
    post('view', { token: st.t }).then(function (res) {
      if (res.status === 404) { notFound(res); return; }
      if (!res.ok || !res.data) { failed(res); return; }
      codeScreen(res.data);
    });
  }

  load();
})();
