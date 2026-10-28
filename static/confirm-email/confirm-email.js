// static/confirm-email/confirm-email.js — /confirm-email (task 5.1b · SYSTEMS_INDEX §1c)
//   - public page (no twRequireAuth): the link from the NEW inbox may be opened on any device
//   - #token=… is read once and removed from the address bar (fragment → never in server logs / Referer)
//   - the token is sent only on an explicit click (mail link scanners must not consume it):
//     POST /auth/email-change/confirm → users.email changes, the old address gets a notice
//   - signed_out (an admin's change — task 8.3): the server ended every session → the local one is
//     cleared the logout way (TwAuthSync.invalidateSession) + reason message + login button
//   - every request through twApi (auth:false) · text: twT · icons: twIcon
(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }

  var token = '';
  var m = /^#token=([A-Za-z0-9_-]{16,200})$/.exec(location.hash || '');
  if (m) token = m[1];
  if (location.hash && history.replaceState) {
    history.replaceState(history.state, '', location.pathname + location.search);
  }

  document.title = twT('page.title', { page: twT('confirm_email.title') });
  twTApply(document.body);
  twIcon.hydrate(document.body);

  var btn = $('ceBtn'), msg = $('ceMsg');
  function showMsg(text, isError) {
    msg.textContent = text;
    msg.classList.toggle('is-error', !!isError);
    msg.hidden = false;
  }
  function done(text, isError) {
    token = '';
    btn.hidden = true;
    $('ceSub').hidden = true;
    showMsg(text, isError);
  }

  if (!token) { done(twT('confirm_email.invalid'), true); return; }
  btn.hidden = false;
  btn.addEventListener('click', function () {
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    msg.hidden = true;
    twApi('/auth/email-change/confirm', { method: 'POST', auth: false, body: { token: token } }).then(function (res) {
      btn.disabled = false;
      btn.setAttribute('aria-busy', 'false');
      if (res.ok && res.data && res.data.signed_out) {
        if (window.TwAuthSync) TwAuthSync.invalidateSession('admin_email_change');
        done(twT('confirm_email.done_signed_out'), false);
        $('ceSettings').hidden = true;
        $('ceLogin').hidden = false;
        return;
      }
      if (res.ok) { done(twT('confirm_email.done'), false); return; }
      var g = res.error && res.error.generalError;
      // invalid_token / email_taken: the token is spent — no retry button
      if (g && (g.code === 'invalid_token' || g.code === 'email_taken')) {
        done(g.code === 'invalid_token' ? twT('confirm_email.invalid') : twApiMessage(res, twT('confirm_email.error')), true);
        return;
      }
      showMsg(twApiMessage(res, twT('confirm_email.error')), true);
    });
  });
}());
