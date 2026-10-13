// static/settings/settings.js — /settings (PR 1.2 · PR 4.7 — unified page checklist)
//   - guard: twRequireAuth (SHELL-09) — TwAuthSync snapshot only, never tw_user / tw_jwt
//   - every request through twApi (JWT + 401 → invalidateSession are twApi's)
//   - dialogs: twModal (DS-OVL) · toasts: showToast (DS-FEEDBACK) · text: twT · icons: twIcon
//   - account data from GET /profile/{uid}/full (owner-only)
//   - KYC (SYSTEMS_INDEX §23): row «توثيق الهوية» → twAction('verify_identity') → steps
//     email OTP → phone OTP → ID (+ selfie) upload (TW.uploadImage) → admin review
//   - email change hidden until plan 5.1 · account delete hidden until plan 5.5 (soft delete — F27)
(function () {
  'use strict';
  var snap = twRequireAuth();
  if (!snap) return;
  var uid = Number(snap.userId);
  var acct = { user_type: snap.userType, tw_id: '', full_name: '', email: '', phone: '' };
  var kyc = null;   // Tier 3 KYC-owner fields from GET /kyc/status/{uid}

  document.title = twT('page.title', { page: twT('settings.title') });
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(labelKey) {
    var b = el('button', 'tw-btn', twT(labelKey));
    b.type = 'button';
    return b;
  }

  // ── form field (label + .tw-input + inline error) ──
  var _fid = 0;
  function field(labelKey, attrs) {
    var wrap = el('div', 'st-field');
    var input = document.createElement('input');
    input.id = 'st-f' + (++_fid);
    input.className = 'tw-input' + (attrs.cls ? ' ' + attrs.cls : '');
    Object.keys(attrs).forEach(function (k) {
      if (k === 'cls') return;
      if (k === 'value') input.value = attrs.value || '';
      else input.setAttribute(k, attrs[k]);
    });
    var label = el('label', null, twT(labelKey));
    label.setAttribute('for', input.id);
    input._err = el('div', 'st-err');
    input._err.setAttribute('aria-live', 'polite');
    input.addEventListener('input', function () { clrErr(input); });
    wrap.appendChild(label);
    wrap.appendChild(input);
    wrap.appendChild(input._err);
    return { wrap: wrap, input: input };
  }
  function setErr(input, msg) {
    input.parentNode.classList.add('has-error');
    input.setAttribute('aria-invalid', 'true');
    input._err.textContent = msg;
  }
  function clrErr(input) {
    input.parentNode.classList.remove('has-error');
    input.removeAttribute('aria-invalid');
    input._err.textContent = '';
  }

  // ── account display (API truth) ──
  function renderAccount() {
    var type = acct.user_type === 'co' || acct.user_type === 'edu' ? acct.user_type : 'emp';
    $('dispName').textContent = acct.full_name || '—';
    $('dispEmail').textContent = acct.email || '—';
    $('dispPhone').textContent = acct.phone || twT('settings.phone_empty');
    $('dispType').textContent = twT('account.type.' + type);
    $('dispID').textContent = acct.tw_id || '—';
  }

  function loadAccount() {
    return twApi('/profile/' + uid + '/full').then(function (res) {
      var p = res.ok && res.data && res.data.profile;
      if (!p) {
        if (res.status !== 401) showToast(twApiMessage(res, twT('settings.load_error')), 'error');
        return;
      }
      acct = { user_type: p.user_type || acct.user_type, tw_id: p.tw_id || '',
               full_name: p.full_name || '', email: p.email || '', phone: p.phone || '' };
      renderAccount();
    });
  }

  // ── phone ──
  function openPhone() {
    var f = field('settings.phone', { type: 'tel', autocomplete: 'tel', dir: 'ltr',
                                      placeholder: twT('settings.phone_placeholder'), value: acct.phone });
    var form = el('div', 'st-form');
    form.appendChild(f.wrap);
    twModal({ title: twT('settings.phone'), content: form, actions: [
      { text: twT('common.cancel') },
      { text: twT('common.save'), variant: 'primary', onClick: function () { return savePhone(f.input); } },
    ] });
  }
  // false keeps the dialog open (twModal) — success only on res.ok
  function savePhone(input) {
    var phone = input.value.trim();
    if (!phone) { setErr(input, twT('settings.phone_required')); return false; }
    return twApi('/profile/' + uid, { method: 'PUT', body: { phone: phone } }).then(function (res) {
      if (!res.ok) { setErr(input, twApiMessage(res, twT('settings.phone_error'))); return false; }
      showToast(twT('settings.phone_saved'), 'success');
      loadAccount();
    });
  }

  // ── password — PUT /auth/password (server checks the current password + the register rule) ──
  var PW_FIELD = { current_password: 'old', new_password: 'new' };
  function openPassword() {
    var f = {
      old:  field('settings.pw.old',  { type: 'password', autocomplete: 'current-password' }),
      new:  field('settings.pw.new',  { type: 'password', autocomplete: 'new-password' }),
      conf: field('settings.pw.conf', { type: 'password', autocomplete: 'new-password' }),
    };
    var form = el('div', 'st-form');
    form.appendChild(f.old.wrap); form.appendChild(f.new.wrap); form.appendChild(f.conf.wrap);
    twModal({ title: twT('settings.pw.title'), content: form, actions: [
      { text: twT('common.cancel') },
      { text: twT('settings.pw.submit'), variant: 'primary', onClick: function () { return savePassword(f); } },
    ] });
  }
  function savePassword(f) {
    var oldP = f.old.input.value, newP = f.new.input.value, conf = f.conf.input.value, ok = true;
    if (!oldP) { setErr(f.old.input, twT('settings.pw.old_required')); ok = false; }
    if (!newP) { setErr(f.new.input, twT('settings.pw.new_required')); ok = false; }
    if (newP !== conf) { setErr(f.conf.input, twT('settings.pw.mismatch')); ok = false; }
    if (!ok) return false;
    return twApi('/auth/password', { method: 'PUT', body: { current_password: oldP, new_password: newP } }).then(function (res) {
      if (res.ok) {
        // Server invalidated every older session (PR 1.8) and sent a fresh JWT for this device.
        var token = res.data && res.data.token;
        if (!token || !window.TwAuthSync || !TwAuthSync.renewToken(token)) {
          showToast(twT('settings.pw.changed_relogin'), 'success');
          setTimeout(function () { if (window.TwAuthSync) TwAuthSync.invalidateSession('password_changed'); }, 1500);
          return;
        }
        showToast(twT('settings.pw.changed'), 'success');
        return;
      }
      var fe = res.error && res.error.fieldErrors[0];
      if (fe && PW_FIELD[fe.field]) { setErr(f[PW_FIELD[fe.field]].input, fe.message); return false; }
      if (res.status !== 401) showToast(twApiMessage(res, twT('settings.pw.error')), 'error');
      return false;
    });
  }

  // ══ KYC ══
  var KYC_STEP = { none: 1, email: 1, phone: 2, id_upload: 3 };
  var kycBody = null, kycFiles = { id: '', selfie: '' };

  // 1 / 2 / 3 = a form step · 'review' / 'approved' / 'rejected' = a result
  function kycView(k) {
    if (k && k.status === 'approved') return 'approved';
    if (k && k.status === 'rejected') return 'rejected';
    if (k && k.step === 'review') return 'review';
    return (k && KYC_STEP[k.step]) || 1;
  }

  function renderKycRow() {
    var v = kycView(kyc);
    var state = typeof v === 'number' ? (kyc && kyc.step && kyc.step !== 'none' ? 'progress' : 'none') : v;
    var label = $('kycState');
    label.textContent = twT('settings.kyc.state.' + state);
    label.className = 'st-val st-kyc-state is-' + state;
    var slot = $('kycAction');
    slot.textContent = '';
    if (v === 'approved') { slot.appendChild(twIconEl('verified', { size: 'sm' })); return; }
    var b = twAction('verify_identity', {
      labelKey: state === 'review' ? 'settings.kyc.view' : state === 'none' ? null : 'settings.kyc.continue',
      onClick: openKYC,
    });
    if (b) slot.appendChild(b);
  }

  function loadKyc() {
    return twApi('/kyc/status/' + uid).then(function (res) {
      if (res.ok && res.data) kyc = res.data.kyc || null;
      renderKycRow();
    });
  }

  function openKYC() {
    kycBody = el('div');
    kycFiles = { id: '', selfie: '' };
    twModal({ title: twT('settings.kyc.title'), content: kycBody,
              actions: [{ text: twT('common.close') }],
              onClose: function () { kycBody = null; } });
    var shown = kycView(kyc);
    showKycView(shown);
    loadKyc().then(function () { if (kycBody && kycView(kyc) !== shown) showKycView(kycView(kyc)); });
  }

  function showKycView(v) {
    if (!kycBody) return;
    kycBody.textContent = '';
    if (typeof v !== 'number') { kycBody.appendChild(kycResult(v)); return; }
    var steps = el('div', 'st-steps');
    for (var i = 1; i <= 3; i++) {
      if (i > 1) steps.appendChild(el('span', 'st-line'));
      steps.appendChild(el('span', 'st-dot' + (i < v ? ' is-done' : i === v ? ' is-active' : ''), String(i)));
    }
    kycBody.appendChild(steps);
    kycBody.appendChild(v === 3 ? kycDocsStep() : kycOtpStep(v === 1 ? 'email' : 'phone'));
  }

  function kycResult(v) {
    var box = el('div', 'st-result is-' + v);
    box.appendChild(twIconEl(v === 'approved' ? 'verified' : v === 'review' ? 'clock' : 'error'));
    box.appendChild(el('div', 'st-result-title', twT('settings.kyc.' + v + '.title')));
    box.appendChild(el('p', 'st-hint', twT('settings.kyc.' + v + '.hint')));
    if (v === 'rejected') {
      var retry = btn('settings.kyc.retry');
      retry.addEventListener('click', function () { kycRestart(retry); });
      box.appendChild(retry);
    }
    return box;
  }

  function kycRestart(b) {
    setBtnLoad(b, true);
    return twApi('/kyc/start', { method: 'POST' }).then(function (res) {
      setBtnLoad(b, false);
      if (!res.ok) { if (res.status !== 401) showToast(twApiMessage(res, twT('settings.kyc.error')), 'error'); return; }
      kyc = (res.data && res.data.kyc) || { step: 'email', status: 'pending' };
      renderKycRow();
      showKycView(kycView(kyc));
    });
  }

  // Send / verify failure text — 503 otp_delivery_unavailable = no provider yet (fail closed — §54c)
  function kycErrText(res, fallbackKey) {
    var e = res.error || {};
    var code = ((e.fieldErrors || [])[0] || e.generalError || {}).code;
    if (res.status === 503 || code === 'otp_delivery_unavailable') return twT('settings.kyc.otp_unavailable');
    return twApiMessage(res, twT(fallbackKey));
  }

  function kycOtpStep(ch) {
    var box = el('div', 'st-form');
    box.appendChild(el('p', 'st-hint', twT('settings.kyc.' + ch + '.hint')));
    var target = field('settings.kyc.' + ch + '.label', { type: ch === 'email' ? 'email' : 'tel', dir: 'ltr',
                                                         value: ch === 'email' ? acct.email : acct.phone });
    var send = btn('settings.kyc.send_code');
    var code = field('settings.kyc.code', { inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: '6', cls: 'st-code' });
    var verify = btn('settings.kyc.verify_code');
    code.wrap.hidden = true;
    verify.hidden = true;
    send.addEventListener('click', function () { kycSendCode(ch, target.input, send, code.wrap, verify); });
    verify.addEventListener('click', function () { kycVerifyCode(ch, code.input, verify); });
    box.appendChild(target.wrap); box.appendChild(send); box.appendChild(code.wrap); box.appendChild(verify);
    return box;
  }

  // Success only on HTTP 2xx + status "success"; 401 → twApi invalidates, the guard redirects.
  function kycSendCode(ch, input, b, codeWrap, verify) {
    var v = input.value.trim();
    if (!v) { setErr(input, twT('settings.kyc.' + ch + '.required')); return Promise.resolve(false); }
    setBtnLoad(b, true);
    return twApi('/kyc/' + ch + '/send', { method: 'POST', body: ch === 'email' ? { email: v } : { phone: v } }).then(function (res) {
      setBtnLoad(b, false);
      if (res.ok && res.data && res.data.status === 'success') {
        codeWrap.hidden = false;
        verify.hidden = false;
        showToast(twT('settings.kyc.code_sent'), 'success');
        return true;
      }
      if (res.status !== 401) showToast(kycErrText(res, 'settings.kyc.error'), 'error');
      return false;
    });
  }

  function kycVerifyCode(ch, input, b) {
    var code = input.value.trim();
    if (!/^\d{6}$/.test(code)) { setErr(input, twT('settings.kyc.code_invalid')); return Promise.resolve(false); }
    setBtnLoad(b, true);
    return twApi('/kyc/' + ch + '/verify', { method: 'POST', body: { code: code } }).then(function (res) {
      setBtnLoad(b, false);
      if (res.ok && res.data && res.data.status === 'success') {
        showToast(twT('settings.kyc.' + ch + '.verified'), 'success');
        kyc = Object.assign({}, kyc, { step: ch === 'email' ? 'phone' : 'id_upload' });
        renderKycRow();
        showKycView(kycView(kyc));
        return true;
      }
      if (res.status !== 401) showToast(kycErrText(res, 'settings.kyc.code_wrong'), 'error');
      return false;
    });
  }

  function kycDocsStep() {
    var box = el('div', 'st-form');
    box.appendChild(el('p', 'st-hint', twT('settings.kyc.docs.hint')));
    box.appendChild(kycFilePicker('id', 'settings.kyc.docs.id', 'id-card'));
    box.appendChild(kycFilePicker('selfie', 'settings.kyc.docs.selfie', 'camera'));
    var submit = btn('settings.kyc.docs.submit');
    submit.addEventListener('click', function () { kycSubmitDocs(submit); });
    box.appendChild(submit);
    return box;
  }

  // A picked file shows its name (no preview <img> — a local data: URL never reaches src, §54)
  function kycFilePicker(slot, labelKey, icon) {
    var wrap = el('div');
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/jpeg,image/png,image/webp';
    input.hidden = true;
    var pick = el('button', 'st-file');
    pick.type = 'button';
    var lbl = el('span', null, twT(labelKey));
    pick.appendChild(twIconEl(icon));
    pick.appendChild(lbl);
    pick.addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function (e) {
        kycFiles[slot] = e.target.result;
        pick.classList.add('is-picked');
        lbl.textContent = twT('settings.kyc.docs.picked', { name: file.name });
      };
      reader.readAsDataURL(file);
    });
    wrap.appendChild(pick);
    wrap.appendChild(input);
    return wrap;
  }

  // Upload (PR-7a shared client — kyc-docs is private → data.path) → POST /kyc/docs → review
  function kycSubmitDocs(b) {
    if (!kycFiles.id) { showToast(twT('settings.kyc.docs.id_required'), 'error'); return Promise.resolve(false); }
    setBtnLoad(b, true);
    var jwt = TwAuthSync.getToken();
    return Promise.all([
      TW.uploadImage({ kind: 'kyc-id-front', dataUrl: kycFiles.id, jwt: jwt }),
      kycFiles.selfie ? TW.uploadImage({ kind: 'kyc-selfie', dataUrl: kycFiles.selfie, jwt: jwt }) : Promise.resolve(null),
    ]).then(function (results) {
      var bad = results.filter(function (r) { return r && (!r.ok || !r.data || !r.data.path); })[0];
      if (bad) throw TW.uploadError(bad, twT('settings.kyc.docs.upload_error'), 'upload_failed');
      return twApi('/kyc/docs', { method: 'POST', body: {
        id_front_url: results[0].data.path, selfie_url: results[1] ? results[1].data.path : null } });
    }).then(function (res) {
      setBtnLoad(b, false);
      if (!res.ok) { if (res.status !== 401) showToast(twApiMessage(res, twT('settings.kyc.docs.save_error')), 'error'); return false; }
      showToast(twT('settings.kyc.docs.sent'), 'success');
      kyc = Object.assign({}, kyc, { step: 'review', status: 'pending' });
      renderKycRow();
      showKycView('review');
      return true;
    }).catch(function (e) {
      setBtnLoad(b, false);
      showToast(TW.uploadFailureMessage(e, twT('settings.kyc.error')), 'error');
      return false;
    });
  }

  // ── wire up ──
  var OPEN = { phone: openPhone, password: openPassword };
  document.querySelectorAll('[data-st-open]').forEach(function (b) {
    b.addEventListener('click', function () { OPEN[b.getAttribute('data-st-open')](); });
  });
  renderAccount();
  renderKycRow();
  loadAccount();
  loadKyc();
}());
