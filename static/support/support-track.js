// static/support/support-track.js — /support/track, the guest follow-up page (task 7.2a واجهة · docs/rules/support.md)
//   - the token: location.hash (#t=…) read once → history.replaceState removes it from the address bar → kept in
//     memory and sent in the POST body only (never a query string, never stored)
//   - POST /support/track/view → status · messages · reply (/reply) · «تم الحل» (/resolve, twConfirm first)
//   - no token / 404 (wrong · expired · revoked — one answer) → one general text + «إعادة إرسال الرابط»
//   - twApi {auth:false} only · every text through textContent (never innerHTML)
(function () {
  'use strict';
  var F = window.TwSupportForm, el = F.el;
  var root = document.getElementById('stRoot');
  var m = /^#t=([A-Za-z0-9_-]+)$/.exec(location.hash || '');
  var token = m ? m[1] : '';
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);

  document.title = twT('page.title', { page: twT('support.track.title') });
  twTApply(document.body);
  if (window.twIcon && twIcon.hydrate) twIcon.hydrate(document.body);

  function call(action, body) {
    body = body || {};
    body.token = token;
    return twApi('/support/track/' + action, { method: 'POST', auth: false, body: body });
  }

  function notFound(res) {
    root.textContent = '';
    var card = el('div', 'sp-card');
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-msg is-error', res ? twApiMessage(res, twT('support.error.track_not_found'))
                                                  : twT('support.error.track_not_found')));
    var link = F.button('support.track.resend', 'sp-link');
    var form = F.resendForm();
    form.hidden = true;
    link.addEventListener('click', function () { form.hidden = !form.hidden; });
    box.appendChild(link);
    box.appendChild(form);
    card.appendChild(box);
    root.appendChild(card);
  }

  function load() {
    if (!token) { notFound(null); return; }
    call('view').then(function (res) {
      if (res.status === 404) { notFound(res); return; }
      if (!res.ok || !res.data) {
        root.textContent = '';
        root.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
        return;
      }
      root.textContent = '';
      root.appendChild(F.thread(res.data, {
        reply: function (body) { return call('reply', { body: body }); },
        resolve: function () { return call('resolve'); },
        reload: load,
      }));
    });
  }

  load();
})();
