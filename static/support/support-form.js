// static/support/support-form.js — support form pieces shared by /support · /support/track · the admin inbox
// (task 7.1 · 7.2a واجهة · docs/rules/support.md → الواجهة)
//   TwSupportForm.field(o)            label above the field + «إلزامي» / «اختياري» muted (Profile V2 look) + error line
//   TwSupportForm.setError(f, text)   show / clear the field error (text '' = clear)
//   TwSupportForm.detailFields(specs) the optional fields of one category from GET /support/meta → fields
//                                     (enum = list · date = day / month / year lists · other = input, max from meta)
//   TwSupportForm.ticketForm(o)       the ticket form: o.meta · o.guest · o.category · o.faqId · o.onDone(public_id)
//                                     account: any category → POST /support/tickets · guest: account only, email +
//                                     code (the OTP path) → POST /support/guest/tickets — the link goes by email only
//   TwSupportForm.thread(t, o)        one conversation (requester view): status · messages · reply · «تم الحل»
//                                     o.reply(body) / o.resolve() return twApi promises · o.reload()
//   TwSupportForm.resendForm()        «فقدت رابط المتابعة؟» — email → POST /support/track/resend → one general text
//   TwSupportForm.guestOpen()         «مشكلة بالدخول؟» on the login page — the guest form in a DS-OVL twModal
//   - API: twApi only ({auth:false} for the guest) · text: twT (support.*) · limits: twLimit / meta · tokens only
//   - every text from the API or tw_strings through textContent — never innerHTML
(function () {
  'use strict';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function button(key, cls) {
    var b = el('button', cls || 'tw-btn', twT(key));
    b.type = 'button';
    return b;
  }

  function addOption(select, value, text) {
    var o = el('option', null, text);
    o.value = value;
    select.appendChild(o);
  }

  var seq = 0;
  function field(o) {
    var wrap = el('div', 'sp-field'), id = 'sp-f' + (++seq);
    var label = el('label', 'sp-label');
    label.setAttribute('for', id);
    label.appendChild(el('span', null, o.label != null ? o.label : twT(o.labelKey)));
    if (!o.noMark) label.appendChild(el('span', 'sp-mark', twT(o.required ? 'support.form.required' : 'support.form.optional')));
    var input;
    if (o.kind === 'textarea') {
      input = el('textarea', 'tw-textarea');
      input.rows = o.rows || 5;
    } else if (o.kind === 'select') {
      input = el('select', 'ep-select');
      (o.options || []).forEach(function (op) { addOption(input, op[0], twT(op[1])); });
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

  // the server's field → the form field (422 / 400 carry error.field — details.<key> for an optional field)
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
      if (f.skip || f.optional) return;
      var empty = !f.input.value.trim();
      setError(f, empty ? twT('support.error.required') : '');
      if (empty) ok = false;
    });
    return ok;
  }

  // ── optional fields of one category (GET /support/meta → fields[category]) ──
  function dateField(spec) {
    var f = field({ labelKey: 'support.field.' + spec.key, required: false, kind: 'select',
                    options: [['', 'support.date.day']] });
    f.input.setAttribute('aria-label', twT('support.date.day'));
    for (var d = 1; d <= 31; d++) addOption(f.input, String(d), String(d));
    var month = el('select', 'ep-select');
    month.setAttribute('aria-label', twT('support.date.month'));
    addOption(month, '', twT('support.date.month'));
    for (var m = 1; m <= 12; m++) addOption(month, String(m), twT('date.month.' + m));
    var year = el('select', 'ep-select');
    year.setAttribute('aria-label', twT('support.date.year'));
    addOption(year, '', twT('support.date.year'));
    if (window.TW && TW.fillFoundedYears) TW.fillFoundedYears(year);   // the shared year list (current year first)
    var row = el('div', 'sp-date');
    f.wrap.insertBefore(row, f.input);
    row.appendChild(f.input);
    row.appendChild(month);
    row.appendChild(year);
    f.parts = [f.input, month, year];
    f.value = function () {
      var p = f.parts.map(function (s) { return s.value; });
      if (!p[0] && !p[1] && !p[2]) return '';
      if (!p[0] || !p[1] || !p[2]) return null;   // partly picked
      return p[2] + '-' + ('0' + p[1]).slice(-2) + '-' + ('0' + p[0]).slice(-2);
    };
    return f;
  }

  function detailFields(specs) {
    var out = {};
    (specs || []).forEach(function (spec) {
      var f;
      if (spec.type === 'enum') {
        f = field({ labelKey: 'support.field.' + spec.key, required: false, kind: 'select',
                    options: [['', 'common.pick']].concat((spec.values || []).map(function (v) {
                      return [v, 'support.field.' + spec.key + '.' + v]; })) });
      } else if (spec.type === 'date') {
        f = dateField(spec);
      } else {
        var ltr = spec.type !== 'text';
        f = field({ labelKey: 'support.field.' + spec.key, required: false, max: spec.max, ltr: ltr,
                    kind: spec.type === 'email' ? 'email' : spec.type === 'url' ? 'url' : spec.type === 'phone' ? 'tel' : 'text',
                    hintKey: spec.type === 'url' ? 'support.field.url_hint' : null });
      }
      f.optional = true;
      if (!f.value) f.value = function () { return f.input.value.trim(); };
      out['details.' + spec.key] = f;
    });
    return out;
  }

  // {key: value} of the filled optional fields — null when a date is half picked (error shown)
  function collectDetails(fields) {
    var details = {}, ok = true;
    Object.keys(fields).forEach(function (k) {
      if (k.indexOf('details.') !== 0) return;
      var v = fields[k].value();
      setError(fields[k], v === null ? twT('support.error.date_partial') : '');
      if (v === null) ok = false;
      else if (v) details[k.slice(8)] = v;
    });
    return ok ? details : null;
  }

  // ── the ticket form (account or guest) ──
  function ticketForm(o) {
    var meta = o.meta || { categories: [], fields: {}, faq: {} };
    var guest = !!o.guest;
    var box = el('div', 'sp-form');
    var state = { faqId: o.faqId || '' };
    var fields = {};
    var detailsBox = el('div', 'sp-form');

    if (guest) {
      box.appendChild(el('p', 'sp-hint', twT('support.guest.intro')));
      fields.email = field({ labelKey: 'support.guest.email', required: true, kind: 'email', ltr: true,
                             autocomplete: 'email', hintKey: 'support.guest.email_hint' });
      box.appendChild(fields.email.wrap);
      var catLine = el('p', 'sp-msg', twT('support.form.category') + ': ' + twT('support.category.' + meta.guest_category));
      box.appendChild(catLine);
    } else {
      fields.category = field({ labelKey: 'support.form.category', required: true, kind: 'select',
                                options: [['', 'common.pick']].concat(meta.categories.map(function (c) {
                                  return [c, 'support.category.' + c]; })) });
      box.appendChild(fields.category.wrap);
    }
    var faqLine = el('p', 'sp-hint');
    faqLine.hidden = true;
    box.appendChild(faqLine);
    box.appendChild(detailsBox);
    fields.subject = field({ labelKey: 'support.form.subject', required: true, max: twLimit('support_subject_max') });
    fields.body = field({ labelKey: 'support.form.body', required: true, kind: 'textarea', max: twLimit('support_body_max'),
                          hintKey: 'support.form.body_hint' });
    box.appendChild(fields.subject.wrap);
    box.appendChild(fields.body.wrap);
    if (guest) {
      fields.code = field({ labelKey: 'support.guest.code', required: true, ltr: true, inputMode: 'numeric',
                            autocomplete: 'one-time-code', max: 6 });
      fields.code.skip = true;
      fields.code.wrap.hidden = true;
      box.appendChild(fields.code.wrap);
    }
    box.appendChild(el('p', 'sp-warn', twT('support.form.no_secrets')));
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    box.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var send = button(guest ? 'support.guest.send_code' : 'support.form.submit');
    var open = guest ? button('support.guest.submit') : null;
    actions.appendChild(send);
    if (open) { open.hidden = true; actions.appendChild(open); }
    box.appendChild(actions);

    function category() { return guest ? meta.guest_category : fields.category.input.value; }

    function showCategory() {
      var cat = category();
      Object.keys(fields).forEach(function (k) { if (k.indexOf('details.') === 0) delete fields[k]; });
      detailsBox.textContent = '';
      var extra = detailFields((meta.fields || {})[cat]);
      Object.keys(extra).forEach(function (k) { fields[k] = extra[k]; detailsBox.appendChild(extra[k].wrap); });
      detailsBox.hidden = !Object.keys(extra).length;
      if (state.faqId && ((meta.faq || {})[cat] || []).indexOf(state.faqId) === -1) state.faqId = '';
      faqLine.hidden = !state.faqId;
      faqLine.textContent = state.faqId ? twT('support.form.about') + ' ' + twT('support.faq.' + cat + '.' + state.faqId + '.q') : '';
      if (window.scSelectInit) scSelectInit();
    }

    if (!guest) {
      fields.category.input.value = o.category && meta.categories.indexOf(o.category) !== -1 ? o.category : '';
      fields.category.input.addEventListener('change', showCategory);
    }
    showCategory();

    function payload() {
      var details = collectDetails(fields);
      if (details === null) return null;
      var p = { subject: fields.subject.input.value.trim(), body: fields.body.input.value.trim() };
      if (!guest) p.category = category();
      if (Object.keys(details).length) p.details = details;
      if (state.faqId) p.faq_id = state.faqId;
      return p;
    }

    function done(publicId) {
      if (!guest) { if (o.onDone) o.onDone(publicId); return; }
      box.textContent = '';
      var d = el('div', 'sp-done');
      d.appendChild(el('p', 'sp-msg is-ok', twT('support.guest.done')));
      var idLine = el('p', 'sp-msg', twT('support.ticket.number') + ' ');
      idLine.appendChild(el('span', 'sp-id', publicId || ''));
      d.appendChild(idLine);
      d.appendChild(el('p', 'sp-hint', twT('support.guest.done_hint')));
      box.appendChild(d);
      if (o.onDone) o.onDone(publicId);
    }

    send.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      if (!requiredOk(fields)) return;
      var p = payload();
      if (!p) return;
      send.disabled = true;
      if (!guest) {
        twApi('/support/tickets', { method: 'POST', body: p }).then(function (res) {
          send.disabled = false;
          if (!res.ok) { serverError(res, fields, msg); return; }
          done(res.data && res.data.public_id);
        });
        return;
      }
      twApi('/support/guest/code', { method: 'POST', auth: false, body: { email: fields.email.input.value.trim() } })
        .then(function (res) {
          send.disabled = false;
          if (!res.ok) { serverError(res, fields, msg); return; }
          fields.code.skip = false;
          fields.code.wrap.hidden = false;
          fields.email.input.readOnly = true;
          open.hidden = false;
          send.textContent = twT('support.guest.resend');
          msg.textContent = twT('support.guest.code_sent', { minutes: (res.data && res.data.minutes) || '' });
          msg.className = 'sp-msg is-ok';
          if (fields.code.input.focus) fields.code.input.focus();
        });
    });

    if (open) open.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      if (!requiredOk(fields)) return;
      var p = payload();
      if (!p) return;
      p.email = fields.email.input.value.trim();
      p.code = fields.code.input.value.trim();
      open.disabled = true;
      twApi('/support/guest/tickets', { method: 'POST', auth: false, body: p }).then(function (res) {
        open.disabled = false;
        if (!res.ok) { serverError(res, fields, msg); return; }
        done(res.data && res.data.public_id);
      });
    });

    return { el: box, fields: fields, category: category, faqId: function () { return state.faqId; } };
  }

  // ── one conversation (the requester's view — account or guest) ──
  function thread(t, o) {
    var card = el('div', 'sp-card');
    var head = el('div', 'sp-thread-head');
    head.appendChild(el('h2', 'sp-thread-subject', t.subject));
    head.appendChild(el('span', 'sp-pill is-' + t.status, twT('support.status_user.' + t.status)));
    card.appendChild(head);
    var idLine = el('p', 'sp-hint', twT('support.ticket.number') + ' ');
    idLine.appendChild(el('span', 'sp-id', t.public_id));
    idLine.appendChild(document.createTextNode(' · ' + twT('support.category.' + t.category)));
    card.appendChild(idLine);

    var msgs = el('div', 'sp-msgs');
    (t.messages || []).forEach(function (m) {
      var admin = m.author_type === 'admin';
      var b = el('div', 'sp-bubble' + (admin ? ' is-admin' : ''));
      b.appendChild(el('span', 'sp-bubble-meta', twT(admin ? 'support.author.admin' : 'support.author.me')
        + ' · ' + twFormatDateTime(m.created_at)));
      b.appendChild(document.createTextNode(m.body));
      msgs.appendChild(b);
    });
    card.appendChild(msgs);

    if (t.status === 'resolved' && !t.can_reopen) {
      card.appendChild(el('p', 'sp-msg', twT('support.error.reopen_expired')));
      return card;
    }
    var form = el('div', 'sp-form');
    var fields = { body: field({ labelKey: 'support.thread.reply', required: true, kind: 'textarea', rows: 4,
                                 max: twLimit('support_body_max'),
                                 hintKey: t.status === 'resolved' ? 'support.thread.reopen_hint' : null }) };
    form.appendChild(fields.body.wrap);
    form.appendChild(el('p', 'sp-warn', twT('support.form.no_secrets')));
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    form.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var send = button('support.thread.send');
    actions.appendChild(send);
    var resolve = null;
    if (t.status !== 'resolved') {
      resolve = button('support.thread.resolve', 'tw-btn tw-btn-ghost');
      actions.appendChild(resolve);
    }
    form.appendChild(actions);
    card.appendChild(form);

    send.addEventListener('click', function () {
      msg.textContent = '';
      if (!requiredOk(fields)) return;
      send.disabled = true;
      o.reply(fields.body.input.value.trim()).then(function (res) {
        send.disabled = false;
        if (!res.ok) { serverError(res, fields, msg); return; }
        showToast(twT('support.done.replied'), 'success');
        o.reload();
      });
    });
    if (resolve) resolve.addEventListener('click', function () {
      twConfirm({ title: twT('support.resolve.title'), message: twT('support.resolve.message'),
                  confirmText: twT('support.thread.resolve'), cancelText: twT('common.cancel') })
        .then(function (yes) {
          if (!yes) return;
          o.resolve().then(function (res) {
            if (!res.ok) { showToast(twApiMessage(res, twT('support.error.generic')), 'error'); return; }
            showToast(twT('support.done.resolved'), 'success');
            o.reload();
          });
        });
    });
    return card;
  }

  // ── «فقدت رابط المتابعة؟» — always the same general text (the server says nothing about the address) ──
  function resendForm() {
    var box = el('div', 'sp-form');
    box.appendChild(el('p', 'sp-hint', twT('support.resend.intro')));
    var fields = { email: field({ labelKey: 'support.guest.email', required: true, kind: 'email', ltr: true,
                                  autocomplete: 'email' }) };
    box.appendChild(fields.email.wrap);
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    box.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var send = button('support.resend.submit');
    actions.appendChild(send);
    box.appendChild(actions);
    send.addEventListener('click', function () {
      msg.textContent = '';
      msg.className = 'sp-msg';
      if (!requiredOk(fields)) return;
      send.disabled = true;
      twApi('/support/track/resend', { method: 'POST', auth: false, body: { email: fields.email.input.value.trim() } })
        .then(function (res) {
          send.disabled = false;
          if (!res.ok) { serverError(res, fields, msg); return; }
          msg.textContent = twT('support.resend.done');
          msg.className = 'sp-msg is-ok';
        });
    });
    return box;
  }

  // ── «مشكلة بالدخول؟» on the login page — the same guest form in a modal ──
  function guestOpen() {
    twApi('/support/meta', { auth: false }).then(function (res) {
      if (!res.ok || !res.data) { showToast(twApiMessage(res, twT('common.load_error')), 'error'); return; }
      var form = ticketForm({ meta: res.data, guest: true });
      twModal({ title: twT('support.guest.title'), content: form.el,
                actions: [{ text: twT('common.close'), variant: 'secondary' }] });
    });
  }

  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-support-guest]');
    if (!t) return;
    e.preventDefault();
    guestOpen();
  });

  window.TwSupportForm = { el: el, button: button, field: field, setError: setError, serverError: serverError,
                           requiredOk: requiredOk, detailFields: detailFields, ticketForm: ticketForm,
                           thread: thread, resendForm: resendForm, guestOpen: guestOpen };
})();
