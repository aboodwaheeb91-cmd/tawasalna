// static/support/support-form.js — support form pieces + the guest form (task 7.1 · docs/rules/support.md)
//   TwSupportForm.field(o)   label above the field + «إلزامي» / «اختياري» muted (Profile V2 look) + error line
//   TwSupportForm.setError(f, text)  show / clear the field error (text '' = clear)
//   TwSupportForm.guestOpen()        «مشكلة بالدخول؟» — DS-OVL twModal: email + subject + message → a code to the
//                                    email (POST /support/guest/code) → the code → POST /support/guest/tickets.
//                                    Category = account on the server; no priority; no follow-up page (reply by
//                                    email later — 7.2). Any element with [data-support-guest] opens it.
//   - API: twApi only ({auth:false} for the guest) · text: twT (support.*) · limits: twLimit · tokens only
(function () {
  'use strict';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  var seq = 0;
  function field(o) {
    var wrap = el('div', 'sp-field'), id = 'sp-f' + (++seq);
    var label = el('label', 'sp-label');
    label.setAttribute('for', id);
    label.appendChild(el('span', null, twT(o.labelKey)));
    label.appendChild(el('span', 'sp-mark', twT(o.required ? 'support.form.required' : 'support.form.optional')));
    var input;
    if (o.kind === 'textarea') {
      input = el('textarea', 'tw-textarea');
      input.rows = o.rows || 5;
    } else if (o.kind === 'select') {
      input = el('select', 'ep-select');
      (o.options || []).forEach(function (op) { input.appendChild(new Option(twT(op[1]), op[0])); });
    } else {
      input = el('input', 'tw-input');
      input.type = o.kind || 'text';
    }
    input.id = id;
    if (o.name) input.name = o.name;
    if (o.max) input.maxLength = o.max;
    if (o.ltr) input.dir = 'ltr';
    if (o.autocomplete) input.autocomplete = o.autocomplete;
    if (o.inputMode) input.inputMode = o.inputMode;
    if (o.required) input.setAttribute('aria-required', 'true');
    var err = el('span', 'sp-err');
    err.id = id + '-err';
    err.hidden = true;
    err.setAttribute('role', 'alert');
    input.setAttribute('aria-describedby', err.id);
    wrap.appendChild(label);
    wrap.appendChild(input);
    if (o.hintKey) wrap.appendChild(el('p', 'sp-hint', twT(o.hintKey, o.vars)));
    wrap.appendChild(err);
    return { wrap: wrap, input: input, err: err };
  }

  function setError(f, text) {
    f.err.textContent = text || '';
    f.err.hidden = !text;
    f.wrap.classList.toggle('has-error', !!text);
    f.input.setAttribute('aria-invalid', text ? 'true' : 'false');
  }

  // the server's field → the form field (422 / 400 carry error.field)
  function serverError(res, fields, msg, fallbackKey) {
    var f = res && res.error && res.error.field && fields[res.error.field];
    var text = twApiMessage(res, twT(fallbackKey || 'support.error.generic'));
    if (f) { setError(f, text); msg.textContent = ''; return; }
    msg.textContent = text;
    msg.className = 'sp-msg is-error';
  }

  function requiredOk(fields) {
    var ok = true;
    Object.keys(fields).forEach(function (k) {
      var f = fields[k];
      if (f.skip) return;
      var empty = !f.input.value.trim();
      setError(f, empty ? twT('support.error.required') : '');
      if (empty) ok = false;
    });
    return ok;
  }

  function guestOpen() {
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-hint', twT('support.guest.intro')));
    var fields = {
      email: field({ labelKey: 'support.guest.email', required: true, kind: 'email', ltr: true, autocomplete: 'email' }),
      subject: field({ labelKey: 'support.form.subject', required: true, max: twLimit('support_subject_max') }),
      body: field({ labelKey: 'support.form.body', required: true, kind: 'textarea',
                    max: twLimit('support_body_max') }),
      code: field({ labelKey: 'support.guest.code', required: true, ltr: true, inputMode: 'numeric',
                    autocomplete: 'one-time-code', max: 6 }),
    };
    fields.code.skip = true;
    fields.code.wrap.hidden = true;
    ['email', 'subject', 'body', 'code'].forEach(function (k) { box.appendChild(fields[k].wrap); });
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    box.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var sendBtn = el('button', 'tw-btn', twT('support.guest.send_code'));
    sendBtn.type = 'button';
    var openBtn = el('button', 'tw-btn', twT('support.guest.submit'));
    openBtn.type = 'button';
    openBtn.hidden = true;
    actions.appendChild(sendBtn);
    actions.appendChild(openBtn);
    box.appendChild(actions);

    twModal({ title: twT('support.guest.title'), content: box,
              actions: [{ text: twT('common.close'), variant: 'secondary' }] });

    sendBtn.addEventListener('click', function () {
      msg.textContent = '';
      if (!requiredOk(fields)) return;
      sendBtn.disabled = true;
      twApi('/support/guest/code', { method: 'POST', auth: false, body: { email: fields.email.input.value.trim() } })
        .then(function (res) {
          sendBtn.disabled = false;
          if (!res.ok) { serverError(res, fields, msg); return; }
          fields.code.skip = false;
          fields.code.wrap.hidden = false;
          fields.email.input.readOnly = true;
          openBtn.hidden = false;
          sendBtn.textContent = twT('support.guest.resend');
          msg.textContent = twT('support.guest.code_sent', { minutes: (res.data && res.data.minutes) || '' });
          msg.className = 'sp-msg is-ok';
          fields.code.input.focus();
        });
    });

    openBtn.addEventListener('click', function () {
      msg.textContent = '';
      if (!requiredOk(fields)) return;
      openBtn.disabled = true;
      twApi('/support/guest/tickets', { method: 'POST', auth: false, body: {
        email: fields.email.input.value.trim(), code: fields.code.input.value.trim(),
        subject: fields.subject.input.value.trim(), body: fields.body.input.value.trim() } })
        .then(function (res) {
          openBtn.disabled = false;
          if (!res.ok) { serverError(res, fields, msg); return; }
          box.textContent = '';
          var done = el('div', 'sp-done');
          done.appendChild(el('p', 'sp-msg is-ok', twT('support.guest.done')));
          var idLine = el('p', 'sp-msg', twT('support.ticket.number') + ' ');
          idLine.appendChild(el('span', 'sp-id', (res.data && res.data.public_id) || ''));
          done.appendChild(idLine);
          done.appendChild(el('p', 'sp-hint', twT('support.guest.done_hint')));
          box.appendChild(done);
        });
    });
  }

  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-support-guest]');
    if (!t) return;
    e.preventDefault();
    guestOpen();
  });

  window.TwSupportForm = { el: el, field: field, setError: setError, serverError: serverError,
                           requiredOk: requiredOk, guestOpen: guestOpen };
})();
