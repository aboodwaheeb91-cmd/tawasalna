// static/support/support.js — /support (task 7.1 · docs/rules/support.md · SYSTEMS_INDEX §62)
//   - guard: twRequireAuth (SHELL-09) · every request through twApi
//   - new ticket: category (the server's list — labels twT support.category.*) · subject · message → POST /support/tickets
//     (no priority — the admin sets it) · limits / open max / rate: the server answers (422 / 409 / 429)
//   - my tickets: GET /support/tickets (newest message first) → one conversation: GET /support/tickets/{id}
//     reply → POST …/messages (status back to «مفتوحة»; a closed ticket reopens within 14 days, else the
//     server says «افتح تذكرة جديدة») · close → POST …/close (twConfirm first)
//   - every text through textContent (never innerHTML) · dates twFormatDateTime · text twT · icons twIcon
(function () {
  'use strict';
  var snap = twRequireAuth();
  if (!snap) return;
  var F = window.TwSupportForm, el = F.el;
  var home = document.getElementById('spHome');
  var listBox = document.getElementById('spList');
  var newBox = document.getElementById('spNew');
  var thread = document.getElementById('spThread');
  var categories = [];

  document.title = twT('page.title', { page: twT('support.title') });
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function statusPill(status) {
    return el('span', 'sp-pill is-' + status, twT('support.status.' + status));
  }

  function button(key, cls) {
    var b = el('button', cls || 'tw-btn', twT(key));
    b.type = 'button';
    return b;
  }

  // ── new ticket ──
  function renderNew() {
    newBox.textContent = '';
    var form = el('div', 'sp-form');
    var fields = {
      category: F.field({ labelKey: 'support.form.category', required: true, kind: 'select',
                          options: [['', 'common.pick']].concat(categories.map(function (c) { return [c, 'support.category.' + c]; })) }),
      subject: F.field({ labelKey: 'support.form.subject', required: true, max: twLimit('support_subject_max') }),
      body: F.field({ labelKey: 'support.form.body', required: true, kind: 'textarea', max: twLimit('support_body_max'),
                      hintKey: 'support.form.body_hint' }),
    };
    ['category', 'subject', 'body'].forEach(function (k) { form.appendChild(fields[k].wrap); });
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    form.appendChild(msg);
    var send = button('support.form.submit');
    var actions = el('div', 'sp-actions');
    actions.appendChild(send);
    form.appendChild(actions);
    newBox.appendChild(form);
    if (window.scSelectInit) scSelectInit();

    send.addEventListener('click', function () {
      msg.textContent = '';
      if (!F.requiredOk(fields)) return;
      send.disabled = true;
      twApi('/support/tickets', { method: 'POST', body: {
        category: fields.category.input.value, subject: fields.subject.input.value.trim(),
        body: fields.body.input.value.trim() } })
        .then(function (res) {
          send.disabled = false;
          if (!res.ok) { F.serverError(res, fields, msg); return; }
          showToast(twT('support.done.created'), 'success');
          renderNew();
          loadList().then(function () { if (res.data && res.data.public_id) openTicket(res.data.public_id); });
        });
    });
  }

  // ── my tickets ──
  function renderList(items) {
    listBox.textContent = '';
    listBox.removeAttribute('aria-busy');
    if (!items.length) { listBox.appendChild(el('p', 'sp-empty', twT('support.mine.empty'))); return; }
    var list = el('div', 'sp-list');
    items.forEach(function (t) {
      var row = el('button', 'sp-row');
      row.type = 'button';
      var body = el('span', 'sp-row-body');
      body.appendChild(el('span', 'sp-row-subject', t.subject));
      body.appendChild(el('span', 'sp-row-meta', twT('support.category.' + t.category) + ' · '
        + twFormatDateTime(t.last_message_at)));
      row.appendChild(body);
      row.appendChild(statusPill(t.status));
      row.addEventListener('click', function () { openTicket(t.public_id); });
      list.appendChild(row);
    });
    listBox.appendChild(list);
  }

  function loadList() {
    return twApi('/support/tickets').then(function (res) {
      if (!res.ok) {
        listBox.textContent = '';
        listBox.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
        return;
      }
      var first = !categories.length;
      categories = (res.data && res.data.categories) || [];
      if (first) renderNew();
      renderList((res.data && res.data.items) || []);
    });
  }

  // ── one conversation ──
  function showHome() {
    thread.hidden = true;
    thread.textContent = '';
    home.hidden = false;
  }

  function renderThread(t) {
    thread.textContent = '';
    var back = button('support.thread.back', 'tw-btn tw-btn-ghost sp-back');
    back.addEventListener('click', function () { showHome(); loadList(); });
    thread.appendChild(back);
    var card = el('div', 'sp-card');
    var head = el('div', 'sp-thread-head');
    head.appendChild(el('h2', 'sp-thread-subject', t.subject));
    head.appendChild(statusPill(t.status));
    card.appendChild(head);
    var idLine = el('p', 'sp-hint', twT('support.ticket.number') + ' ');
    idLine.appendChild(el('span', 'sp-id', t.public_id));
    idLine.appendChild(document.createTextNode(' · ' + twT('support.category.' + t.category)));
    card.appendChild(idLine);

    var msgs = el('div', 'sp-msgs');
    (t.messages || []).forEach(function (m) {
      var b = el('div', 'sp-bubble' + (m.author_type === 'admin' ? ' is-admin' : ''));
      b.appendChild(el('span', 'sp-bubble-meta', twT(m.author_type === 'admin' ? 'support.author.admin' : 'support.author.me')
        + ' · ' + twFormatDateTime(m.created_at)));
      b.appendChild(document.createTextNode(m.body));
      msgs.appendChild(b);
    });
    card.appendChild(msgs);

    if (t.status === 'closed' && !t.can_reopen) {
      card.appendChild(el('p', 'sp-msg', twT('support.error.reopen_expired')));
      thread.appendChild(card);
      return;
    }
    var form = el('div', 'sp-form');
    var fields = { body: F.field({ labelKey: 'support.thread.reply', required: true, kind: 'textarea', rows: 4,
                                   max: twLimit('support_body_max'),
                                   hintKey: t.status === 'closed' ? 'support.thread.reopen_hint' : null }) };
    form.appendChild(fields.body.wrap);
    var msg = el('p', 'sp-msg');
    msg.setAttribute('aria-live', 'polite');
    form.appendChild(msg);
    var actions = el('div', 'sp-actions');
    var send = button('support.thread.send');
    actions.appendChild(send);
    var close = null;
    if (t.status !== 'closed') {
      close = button('support.thread.close', 'tw-btn tw-btn-ghost');
      actions.appendChild(close);
    }
    form.appendChild(actions);
    card.appendChild(form);
    thread.appendChild(card);

    send.addEventListener('click', function () {
      msg.textContent = '';
      if (!F.requiredOk(fields)) return;
      send.disabled = true;
      twApi('/support/tickets/' + encodeURIComponent(t.public_id) + '/messages',
            { method: 'POST', body: { body: fields.body.input.value.trim() } })
        .then(function (res) {
          send.disabled = false;
          if (!res.ok) { F.serverError(res, fields, msg); return; }
          showToast(twT('support.done.replied'), 'success');
          openTicket(t.public_id);
        });
    });
    if (close) close.addEventListener('click', function () {
      twConfirm({ title: twT('support.close.title'), message: twT('support.close.message'),
                  confirmText: twT('support.thread.close'), cancelText: twT('common.cancel') })
        .then(function (yes) {
          if (!yes) return;
          twApi('/support/tickets/' + encodeURIComponent(t.public_id) + '/close', { method: 'POST' })
            .then(function (res) {
              if (!res.ok) { showToast(twApiMessage(res, twT('support.error.generic')), 'error'); return; }
              showToast(twT('support.done.closed'), 'success');
              openTicket(t.public_id);
            });
        });
    });
  }

  function openTicket(id) {
    twApi('/support/tickets/' + encodeURIComponent(id)).then(function (res) {
      if (!res.ok) { showToast(twApiMessage(res, twT('common.load_error')), 'error'); return; }
      home.hidden = true;
      thread.hidden = false;
      renderThread(res.data);
      thread.scrollIntoView({ block: 'start' });
    });
  }

  loadList();
})();
