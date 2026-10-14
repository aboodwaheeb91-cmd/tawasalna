// static/reset-password/reset-password.js — /reset-password (task 5.1a · SYSTEMS_INDEX §1b)
//   - public page (no twRequireAuth): a guest who forgot the password
//   - no #token → request form: POST /auth/password-reset/request → always the same text
//     (the server never says whether the email exists)
//   - #token=… (email link) → new password form: POST /auth/password-reset/confirm
//     the token is read once and removed from the address bar (fragment → never in server
//     logs / Referer); the password rule is the server's (_password_policy_error) — no copy here
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

  document.title = twT('page.title', { page: twT('reset.title') });
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function setErr(input, errEl, msg) {
    input.parentNode.classList.add('has-error');
    input.setAttribute('aria-invalid', 'true');
    errEl.textContent = msg;
  }
  function clrErr(input, errEl) {
    input.parentNode.classList.remove('has-error');
    input.removeAttribute('aria-invalid');
    errEl.textContent = '';
  }
  function showMsg(el, text, isError) {
    el.textContent = text;
    el.classList.toggle('is-error', !!isError);
    el.hidden = false;
  }
  function busy(btn, on) {
    btn.disabled = on;
    btn.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  // ── Step 1: request a link ──
  function initRequest() {
    var form = $('rpRequestForm'), email = $('rpEmail'), err = $('rpEmailErr');
    var btn = $('rpRequestBtn'), msg = $('rpRequestMsg');
    $('rpRequest').hidden = false;
    email.addEventListener('input', function () { clrErr(email, err); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clrErr(email, err);
      msg.hidden = true;
      var v = email.value.trim();
      if (!v || !email.checkValidity()) { setErr(email, err, twT(v ? 'login.err.email_format' : 'login.err.email_required')); email.focus(); return; }
      busy(btn, true);
      twApi('/auth/password-reset/request', { method: 'POST', auth: false, body: { email: v } }).then(function (res) {
        busy(btn, false);
        if (res.ok) {
          form.hidden = true;
          showMsg(msg, twT('reset.sent'), false);
          return;
        }
        var fe = res.error && res.error.fieldErrors && res.error.fieldErrors[0];
        if (fe && fe.field === 'email') setErr(email, err, fe.message);
        else showMsg(msg, twApiMessage(res, twT('reset.send_error')), true);
      });
    });
  }

  // ── Step 2: new password ──
  function initNew() {
    var form = $('rpNewForm'), pass = $('rpPass'), pass2 = $('rpPass2');
    var passErr = $('rpPassErr'), pass2Err = $('rpPass2Err');
    var btn = $('rpNewBtn'), msg = $('rpNewMsg');
    $('rpNew').hidden = false;
    pass.addEventListener('input', function () { clrErr(pass, passErr); });
    pass2.addEventListener('input', function () { clrErr(pass2, pass2Err); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clrErr(pass, passErr); clrErr(pass2, pass2Err);
      msg.hidden = true;
      if (pass.value !== pass2.value) { setErr(pass2, pass2Err, twT('reset.mismatch')); pass2.focus(); return; }
      busy(btn, true);
      twApi('/auth/password-reset/confirm', { method: 'POST', auth: false,
                                              body: { token: token, new_password: pass.value } }).then(function (res) {
        busy(btn, false);
        if (res.ok) {
          token = '';
          form.hidden = true;
          showMsg(msg, twT('reset.done'), false);
          var a = $('rpLoginLink').querySelector('a');
          a.textContent = twT('reset.go_login');
          return;
        }
        var fe = res.error && res.error.fieldErrors && res.error.fieldErrors[0];
        if (fe && fe.field === 'new_password') { setErr(pass, passErr, fe.message); pass.focus(); return; }
        var g = res.error && res.error.generalError;
        if (g && g.code === 'invalid_token') {
          token = '';
          form.hidden = true;
          $('rpRequestAgain').hidden = false;
        }
        showMsg(msg, twApiMessage(res, twT('reset.save_error')), true);
      });
    });
  }

  if (token) initNew(); else initRequest();
}());
