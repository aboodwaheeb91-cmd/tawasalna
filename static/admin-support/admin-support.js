// static/admin-support/admin-support.js — admin support inbox (route: server.py → admin_support_page · task 7.1)
//   - GET /admin/support/tickets?status&category&priority&page → newest message first · filters = the server's lists
//   - one ticket: GET /admin/support/tickets/{id} → requester (account / guest email) + the conversation
//   - reply = POST …/messages {body} (status → «بانتظار ردّك») · status / priority = PUT /admin/support/tickets/{id}
//     — both through TwAdminShell.run (confirm first); every write lands in the audit log (server middleware)
//   - 401 = session over → TwAdminShell back to login · 403 = no support.manage → message here (permissionAware)
//   - every text through textContent · dates twFormatDateTime · text twT (admin.support.* / support.*) · tokens only
(function () {
  'use strict';
  if (!TwAdminShell.start()) return;
  var root = document.getElementById('aspRoot');
  var F = window.TwSupportForm, el = F.el;
  var meta = { statuses: [], categories: [], priorities: [] };
  var filters = { status: '', category: '', priority: '', page: 1 };

  document.title = twT('page.title', { page: twT('admin.support.title') });
  TwAdminShell.mount();
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function message(key) {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-msg', twT(key)));
  }
  function button(key, cls) {
    var b = el('button', cls || 'tw-btn', twT(key));
    b.type = 'button';
    return b;
  }
  function pill(kind, value) {
    var cls = kind === 'status' ? (value === 'closed' ? 'is-muted' : value === 'open' ? 'is-warn' : 'is-ok')
      : (value === 'urgent' ? 'is-danger' : value === 'high' ? 'is-warn' : 'is-muted');
    return el('span', 'tw-adm-pill ' + cls, twT('support.' + kind + '.' + value));
  }
  function requesterText(r) {
    if (!r) return '';
    if (r.kind === 'guest') return twT('admin.support.guest') + ' · ' + r.email;
    return (r.name || r.tw_id || '') + ' · ' + (r.email || '');
  }
  function getJson(url) {
    return TwAdminSession.fetch(url, { permissionAware: true }).then(function (r) {
      if (r.status === 403) return { forbidden: true };      // no support.manage — message here, session kept
      return r.ok ? r.json() : r.json().catch(function () { return null; }).then(function (j) { return { failed: j }; });
    });
  }

  // ── the only writes on this page ──
  var ACTIONS = {
    reply: {
      confirm: { title: 'admin.support.reply.title', message: 'admin.support.reply.message', confirm: 'admin.support.reply.confirm' },
      request: function (c) { return { url: '/admin/support/tickets/' + encodeURIComponent(c.id) + '/messages', method: 'POST', body: { body: c.body } }; },
      ok: function (d) { return d && d.ok; },
      permissionAware: true, forbidden: 'admin.support.forbidden', done: 'admin.support.done.replied' },
    update: {
      confirm: { title: 'admin.support.update.title', message: 'admin.support.update.message', confirm: 'admin.support.update.confirm' },
      request: function (c) { return { url: '/admin/support/tickets/' + encodeURIComponent(c.id), method: 'PUT', body: c.body }; },
      ok: function (d) { return d && d.ok; },
      permissionAware: true, forbidden: 'admin.support.forbidden', done: 'admin.support.done.updated' },
  };

  // ── list ──
  function filterSelect(parent, name, values) {
    var f = F.field({ labelKey: 'admin.support.filter.' + name, required: false, kind: 'select',
                      options: [['', 'common.all']].concat(values.map(function (v) { return [v, 'support.' + name + '.' + v]; })) });
    f.wrap.querySelector('.sp-mark').remove();   // a filter is neither required nor optional
    f.input.value = filters[name];
    f.input.addEventListener('change', function () { filters[name] = f.input.value; filters.page = 1; loadList(); });
    parent.appendChild(f.wrap);
  }

  function renderList(d) {
    root.textContent = '';
    var body = TwAdminShell.card(root, { titleKey: 'admin.support.inbox', hintKey: 'admin.support.inbox.hint', icon: 'headset' });
    var bar = el('div', 'asp-filters');
    filterSelect(bar, 'status', meta.statuses);
    filterSelect(bar, 'category', meta.categories);
    filterSelect(bar, 'priority', meta.priorities);
    body.appendChild(bar);
    if (window.scSelectInit) scSelectInit();
    if (!d.items.length) { body.appendChild(el('p', 'tw-adm-msg', twT('admin.support.empty'))); return; }
    var list = el('div');
    d.items.forEach(function (t) {
      var row = el('div', 'tw-adm-row');
      var main = el('div', 'tw-adm-row-main is-link');
      main.setAttribute('role', 'button');
      main.tabIndex = 0;
      main.appendChild(el('div', 'tw-adm-row-title', t.subject));
      main.appendChild(el('div', 'tw-adm-row-sub', t.public_id + ' · ' + twT('support.category.' + t.category) + ' · '
        + requesterText(t.requester) + ' · ' + twFormatDateTime(t.last_message_at)));
      main.addEventListener('click', function () { openTicket(t.public_id); });
      main.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openTicket(t.public_id); } });
      var acts = el('div', 'tw-adm-row-acts');
      acts.appendChild(pill('status', t.status));
      acts.appendChild(pill('priority', t.priority));
      row.appendChild(main);
      row.appendChild(acts);
      list.appendChild(row);
    });
    body.appendChild(list);
    var pages = Math.ceil(d.total / d.limit);
    if (pages > 1) {
      var pag = el('div', 'tw-adm-pag');
      for (var p = 1; p <= pages; p++) {
        (function (n) {
          var b = el('button', 'tw-act' + (n === d.page ? ' is-current' : ''), twFormatNumber(n));
          b.type = 'button';
          b.addEventListener('click', function () { filters.page = n; loadList(); });
          pag.appendChild(b);
        })(p);
      }
      body.appendChild(pag);
    }
  }

  function loadList() {
    var q = Object.keys(filters).filter(function (k) { return filters[k]; })
      .map(function (k) { return k + '=' + encodeURIComponent(filters[k]); }).join('&');
    return getJson('/admin/support/tickets' + (q ? '?' + q : '')).then(function (j) {
      if (j && j.forbidden) { message('admin.support.forbidden'); return; }
      if (!j || !j.data) { if (TwAdminSession.hasLiveToken()) message('admin.support.load_error'); return; }
      meta = { statuses: j.data.statuses, categories: j.data.categories, priorities: j.data.priorities };
      renderList(j.data);
    }).catch(function (e) { console.error('[admin-support] list:', e); message('admin.support.load_error'); });
  }

  // ── one ticket ──
  function renderTicket(t) {
    root.textContent = '';
    var back = button('support.thread.back', 'tw-btn tw-btn-ghost sp-back');
    back.addEventListener('click', loadList);
    root.appendChild(back);
    var body = TwAdminShell.card(root, { titleKey: 'admin.support.ticket', hintKey: 'admin.support.ticket.hint', icon: 'headset' });
    var head = el('div', 'sp-thread-head');
    head.appendChild(el('h2', 'sp-thread-subject', t.subject));
    head.appendChild(pill('status', t.status));
    head.appendChild(pill('priority', t.priority));
    body.appendChild(head);
    body.appendChild(el('p', 'sp-hint', t.public_id + ' · ' + twT('support.category.' + t.category) + ' · '
      + requesterText(t.requester) + ' · ' + twFormatDateTime(t.created_at)));

    var msgs = el('div', 'sp-msgs');
    (t.messages || []).forEach(function (m) {
      var b = el('div', 'sp-bubble' + (m.author_type === 'admin' ? ' is-admin' : ''));
      b.appendChild(el('span', 'sp-bubble-meta', twT('admin.support.author.' + m.author_type)
        + (m.author_type === 'admin' && m.author_id ? ' (' + m.author_id + ')' : '') + ' · ' + twFormatDateTime(m.created_at)));
      b.appendChild(document.createTextNode(m.body));
      msgs.appendChild(b);
    });
    body.appendChild(msgs);

    // status + priority
    var ctl = el('div', 'asp-controls');
    var st = F.field({ labelKey: 'admin.support.filter.status', required: true, kind: 'select',
                       options: meta.statuses.map(function (v) { return [v, 'support.status.' + v]; }) });
    var pr = F.field({ labelKey: 'admin.support.filter.priority', required: true, kind: 'select',
                       options: meta.priorities.map(function (v) { return [v, 'support.priority.' + v]; }) });
    st.input.value = t.status;
    pr.input.value = t.priority;
    var save = button('admin.support.update.save');
    ctl.appendChild(st.wrap);
    ctl.appendChild(pr.wrap);
    ctl.appendChild(save);
    body.appendChild(ctl);
    save.addEventListener('click', function () {
      var change = {};
      if (st.input.value !== t.status) change.status = st.input.value;
      if (pr.input.value !== t.priority) change.priority = pr.input.value;
      if (!Object.keys(change).length) { showToast(twT('admin.support.same'), 'info'); return; }
      TwAdminShell.run(ACTIONS.update, { id: t.public_id, body: change })
        .then(function (res) { if (res && res.ok) openTicket(t.public_id); });
    });

    // reply
    var form = el('div', 'sp-form');
    var reply = F.field({ labelKey: 'admin.support.reply.label', required: true, kind: 'textarea', rows: 4,
                          max: twLimit('support_body_max'), hintKey: 'admin.support.reply.hint' });
    form.appendChild(reply.wrap);
    var send = button('admin.support.reply.send');
    var acts = el('div', 'sp-actions');
    acts.appendChild(send);
    form.appendChild(acts);
    body.appendChild(form);
    send.addEventListener('click', function () {
      var text = reply.input.value.trim();
      F.setError(reply, text ? '' : twT('support.error.required'));
      if (!text) return;
      TwAdminShell.run(ACTIONS.reply, { id: t.public_id, body: text })
        .then(function (res) { if (res && res.ok) openTicket(t.public_id); });
    });
    if (window.scSelectInit) scSelectInit();
  }

  function openTicket(id) {
    getJson('/admin/support/tickets/' + encodeURIComponent(id)).then(function (j) {
      if (j && j.forbidden) { message('admin.support.forbidden'); return; }
      if (!j || !j.data) { showToast(twT('admin.support.load_error'), 'error'); return; }
      renderTicket(j.data);
      window.scrollTo(0, 0);
    }).catch(function (e) { console.error('[admin-support] ticket:', e); showToast(twT('admin.support.load_error'), 'error'); });
  }

  loadList();
})();
