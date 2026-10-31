// admin-otp-ui.js — TwOtpUi: authenticator binding + recovery codes box (task 8.4c-2b-1 · docs/rules/admin-staff.md rule 15).
// ONE implementation shared by the owner's first-time binding on the admin login (admin.html → static/admin/admin.js)
// and the public staff link pages (staff-link.html → static/staff-link/staff-link.js).
//   - groupKey(secret)              → the base32 secret in groups of 4 (manual entry)
//   - validUri(uri)                 → only otpauth://totp/… is drawn / linked
//   - binding(box, {secret, uri})   → QR (local qrcode.min.js, drawn in the browser — no request, no external image)
//                                     + the grouped key + "copy key" + "open in the app" link; false = bad uri
//   - clear(box)                    → removes the QR / key / codes from the DOM
//   - codes(box, codes, onDone)     → the 10 recovery codes once + copy + optional TXT download (local Blob +
//                                     revokeObjectURL, never automatic) + "the file is not encrypted" warning +
//                                     the continue button disabled until "I saved them"; continue → the box is
//                                     emptied, then onDone()
//   - copy(text, okKey)             → clipboard + toast
// Secrets / codes live in the DOM only while shown — never storage, never the URL, never console.
(function () {
  'use strict';

  var OTPAUTH = /^otpauth:\/\/totp\//;
  var FILE_NAME = 'tawasolna-recovery-codes.txt';
  var QR_SIZE = 192;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function button(variant, key, onClick) {
    var b = el('button', 'tw-act tw-act-' + variant + ' adm-login-btn', twT(key));
    b.type = 'button';
    b.addEventListener('click', onClick);
    return b;
  }

  function groupKey(secret) {
    return String(secret || '').replace(/[^A-Z2-7]/g, '').replace(/(.{4})/g, '$1 ').trim();
  }
  function validUri(uri) { return typeof uri === 'string' && OTPAUTH.test(uri); }

  function copy(text, okKey) {
    var fail = function () { showToast(twT('admin.login.codes_copy_fail'), 'error'); };
    try {
      navigator.clipboard.writeText(text).then(function () { showToast(twT(okKey || 'admin.login.codes_copied'), 'success'); }, fail);
    } catch (e) { fail(); }
  }

  function clear(box) { if (box) box.textContent = ''; }

  // QR + key + copy + open link → box. Returns false (box left empty) when the uri is not otpauth://totp/.
  function binding(box, data) {
    clear(box);
    data = data || {};
    if (!validUri(data.uri) || !data.secret) return false;
    var key = groupKey(data.secret);
    var qr = el('div', 'adm-login-qr');
    qr.setAttribute('role', 'img');
    qr.setAttribute('aria-label', twT('admin.login.enroll_qr'));
    box.appendChild(el('p', 'adm-login-hint', twT('admin.login.enroll_scan')));
    box.appendChild(qr);
    if (typeof window.QRCode === 'function') {
      try {
        new window.QRCode(qr, {
          text: data.uri, width: QR_SIZE, height: QR_SIZE,
          colorDark: '#000000',  // tw-color-literal: QR image modules (scanner contrast — image data)
          colorLight: '#ffffff', // tw-color-literal: QR image matte (scanner contrast — image data)
          correctLevel: window.QRCode.CorrectLevel ? window.QRCode.CorrectLevel.M : undefined
        });
      } catch (e) { qr.textContent = ''; qr.hidden = true; }
    } else {
      qr.hidden = true;   // the key + the link below still work
    }
    var open = el('a', 'tw-act tw-act-secondary adm-login-btn', twT('admin.login.enroll_open'));
    open.setAttribute('href', data.uri);
    box.appendChild(open);
    box.appendChild(el('p', 'adm-login-hint', twT('admin.login.enroll_manual')));
    box.appendChild(el('p', 'adm-login-key', key));
    box.appendChild(button('ghost', 'admin.login.enroll_copy_key', function () { copy(key.replace(/\s+/g, ''), 'admin.login.enroll_key_copied'); }));
    return true;
  }

  function download(codes) {
    var text = twT('admin.login.codes_file_head') + '\n\n' + codes.join('\n') + '\n';
    var url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    var a = el('a');
    a.href = url;
    a.download = FILE_NAME;
    a.hidden = true;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  // Recovery codes box → box (emptied first). Continue only after "I saved them"; continue → box emptied → onDone().
  function codes(box, list, onDone) {
    clear(box);
    list = (Array.isArray(list) ? list : []).map(String);
    box.appendChild(el('h1', 'adm-login-sub', twT('admin.login.codes_title')));
    box.appendChild(el('p', 'adm-login-hint', twT('admin.login.codes_hint')));
    var ol = el('ol', 'adm-login-codes');
    list.forEach(function (c) { ol.appendChild(el('li', null, c)); });
    box.appendChild(ol);
    box.appendChild(button('secondary', 'admin.login.codes_copy', function () { copy(list.join('\n')); }));
    box.appendChild(button('ghost', 'admin.login.codes_download', function () { download(list); }));
    box.appendChild(el('p', 'adm-login-hint adm-login-warn', twT('admin.login.codes_file_warn')));
    var lbl = el('label', 'adm-login-check'), saved = el('input');
    saved.type = 'checkbox';
    lbl.appendChild(saved);
    lbl.appendChild(el('span', null, twT('admin.login.codes_saved')));
    box.appendChild(lbl);
    var done = button('primary', 'admin.login.codes_done', function () {
      if (!saved.checked) return;
      list = [];
      clear(box);
      onDone();
    });
    done.disabled = true;
    saved.addEventListener('change', function () { done.disabled = !saved.checked; });
    box.appendChild(done);
    try { saved.focus(); } catch (e) {}
  }

  window.TwOtpUi = { groupKey: groupKey, validUri: validUri, binding: binding, clear: clear, codes: codes, copy: copy,
                     FILE_NAME: FILE_NAME };
}());
