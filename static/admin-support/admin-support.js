// static/admin-support/admin-support.js — admin support inbox (route: server.py → admin_support_page · task 7.1 · 7.2a واجهة)
//   - GET /admin/support/tickets?status&category&priority&requester&q&sort&page · filters + sorts = the server's lists
//     · q = an H number or an email (searched on the server)
//   - one ticket: GET /admin/support/tickets/{id} → requester (account / guest email) · details (text only) ·
//     faq_id (the question itself — twT support.faq.*, category from GET /support/meta) · legacy_category · messages
//   - reply = POST …/messages {body, next_status} — two buttons «نحتاج معلومات» (awaiting_user) · «تم الحل» (resolved)
//     · status / priority / category = PUT /admin/support/tickets/{id} (a guest ticket stays «الدخول والحساب»)
//     — both through TwAdminShell.run (confirm first); every write lands in the audit log (server middleware)
//   - 401 = session over → TwAdminShell back to login · 403 = no support.manage → message here (permissionAware)
//   - every text through textContent · dates twFormatDateTime · text twT (admin.support.* / support.*) · tokens only
(function () {
  'use strict';
  if (!TwAdminShell.start()) return;
  var root = document.getElementById('aspRoot');
  var F = window.TwSupportForm, el = F.el;
  var meta = { statuses: [], categories: [], priorities: [], sorts: [], requesters: [], next_statuses: [] };
  var faqCat = {};      // faq_id → its category (GET /support/meta)
  var enumField = {};   // details key → true when its value is a list value (label = twT)
  var filters = { status: '', category: '', priority: '', requester: '', sort: '', q: '', page: 1 };

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
    var cls = kind === 'status' ? (value === 'new' ? 'is-warn' : value === 'resolved' ? 'is-ok' : 'is-muted')
      : (value === 'urgent' ? 'is-danger' : value === 'high' ? 'is-warn' : 'is-muted');
    return el('span', 'tw-adm-pill ' + cls, twT('support.' + kind + '.' + value));
  }
  function requesterText(r) {
    if (!r) return '';
    // inbound mail (7.3): a hint only — the address matching an account proves nothing, never a link
    if (r.kind === 'guest') return twT('admin.support.guest') + ' · ' + r.email
      + (r.matches_account ? ' · ' + twT('admin.support.matches_account') : '');
    return (r.name || r.tw_id || '') + ' · ' + (r.email || '');
  }
  function sourceText(t) {
    return t.source === 'email' ? ' · ' + twT('admin.support.source.email') : '';
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
      request: function (c) { return { url: '/admin/support/tickets/' + encodeURIComponent(c.id) + '/messages', method: 'POST',
                                       body: { body: c.body, next_status: c.next } }; },
      ok: function (d) { return d && d.ok; },
      permissionAware: true, forbidden: 'admin.support.forbidden', done: 'admin.support.done.replied' },
    update: {
      confirm: { title: 'admin.support.update.title', message: 'admin.support.update.message', confirm: 'admin.support.update.confirm' },
      request: function (c) { return { url: '/admin/support/tickets/' + encodeURIComponent(c.id), method: 'PUT', body: c.body }; },
      ok: function (d) { return d && d.ok; },
      permissionAware: true, forbidden: 'admin.support.forbidden', done: 'admin.support.done.updated' },
  };

  // ── list ──
  var VALUE_KEY = { status: 'support.status.', category: 'support.category.', priority: 'support.priority.',
                    requester: 'admin.support.requester.', sort: 'admin.support.sort.' };
  function filterSelect(parent, name, values) {
    var opts = values.map(function (v) { return [v, VALUE_KEY[name] + v]; });
    var f = F.field({ labelKey: 'admin.support.filter.' + name, noMark: true, kind: 'select',   // a filter is neither required nor optional
                      options: name === 'sort' ? opts : [['', 'common.all']].concat(opts) });
    f.input.value = filters[name] || (name === 'sort' ? values[0] : '');
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
    filterSelect(bar, 'requester', meta.requesters);
    filterSelect(bar, 'sort', meta.sorts);
    var q = F.field({ labelKey: 'admin.support.filter.q', noMark: true, kind: 'search', ltr: true });
    q.input.value = filters.q;
    q.input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { filters.q = q.input.value.trim(); filters.page = 1; loadList(); } });
    var go = button('admin.support.filter.search', 'tw-btn tw-btn-ghost');
    go.addEventListener('click', function () { filters.q = q.input.value.trim(); filters.page = 1; loadList(); });
    q.wrap.appendChild(go);
    bar.appendChild(q.wrap);
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
        + requesterText(t.requester) + sourceText(t) + ' · ' + twFormatDateTime(t.last_message_at)));
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
      if (j && j.failed && j.failed.error && j.failed.error.code === 'invalid_filter') {   // a bad q / filter → say so, keep the page
        showToast(twT('admin.support.bad_filter'), 'error');
        return;
      }
      if (!j || !j.data) { if (TwAdminSession.hasLiveToken()) message('admin.support.load_error'); return; }
      meta = { statuses: j.data.statuses, categories: j.data.categories, priorities: j.data.priorities,
               sorts: j.data.sorts, requesters: j.data.requesters, next_statuses: j.data.next_statuses };
      renderList(j.data);
    }).catch(function (e) { console.error('[admin-support] list:', e); message('admin.support.load_error'); });
  }

  // ── one ticket ──
  function infoRow(list, labelKey, value) {
    var row = el('div', 'asp-info-row');
    row.appendChild(el('dt', null, twT(labelKey)));
    row.appendChild(el('dd', null, value));
    list.appendChild(row);
  }

  // details (text only — an enum value through its twT label) · the FAQ question · the value before stage B
  function renderDetails(parent, t) {
    var list = el('dl', 'asp-info');
    Object.keys(t.details || {}).forEach(function (k) {
      var v = String(t.details[k]);
      infoRow(list, 'support.field.' + k, enumField[k] ? twT('support.field.' + k + '.' + v) : v);
    });
    if (t.faq_id) {
      var cat = faqCat[t.faq_id];
      infoRow(list, 'admin.support.faq', cat ? twT('support.faq.' + cat + '.' + t.faq_id + '.q') : t.faq_id);
    }
    if (t.legacy_category) infoRow(list, 'admin.support.legacy_category', twT('support.category.' + t.legacy_category));
    if (list.children.length) parent.appendChild(list);
  }

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
      + requesterText(t.requester) + sourceText(t) + ' · ' + twFormatDateTime(t.created_at)));
    renderDetails(body, t);

    var msgs = el('div', 'sp-msgs');
    (t.messages || []).forEach(function (m) {
      var b = el('div', 'sp-bubble' + (m.author_type === 'admin' ? ' is-admin' : ''));
      b.appendChild(el('span', 'sp-bubble-meta', twT('admin.support.author.' + m.author_type)
        + (m.author_type === 'admin' && m.author_id ? ' (' + m.author_id + ')' : '') + ' · ' + twFormatDateTime(m.created_at)));
      b.appendChild(document.createTextNode(m.body));
      msgs.appendChild(b);
    });
    body.appendChild(msgs);

    // status + priority + category
    var ctl = el('div', 'asp-controls');
    var st = F.field({ labelKey: 'admin.support.filter.status', required: true, kind: 'select',
                       options: meta.statuses.map(function (v) { return [v, 'support.status.' + v]; }) });
    var pr = F.field({ labelKey: 'admin.support.filter.priority', required: true, kind: 'select',
                       options: meta.priorities.map(function (v) { return [v, 'support.priority.' + v]; }) });
    var ca = F.field({ labelKey: 'admin.support.filter.category', required: true, kind: 'select',
                       options: meta.categories.map(function (v) { return [v, 'support.category.' + v]; }) });
    st.input.value = t.status;
    pr.input.value = t.priority;
    ca.input.value = t.category;
    // a web guest ticket stays account (server 422) — an inbound-email ticket (7.3) may move
    ca.input.disabled = t.requester && t.requester.kind === 'guest' && t.source !== 'email';
    var save = button('admin.support.update.save');
    ctl.appendChild(st.wrap);
    ctl.appendChild(pr.wrap);
    ctl.appendChild(ca.wrap);
    ctl.appendChild(save);
    body.appendChild(ctl);
    save.addEventListener('click', function () {
      var change = {};
      if (st.input.value !== t.status) change.status = st.input.value;
      if (pr.input.value !== t.priority) change.priority = pr.input.value;
      if (ca.input.value !== t.category) change.category = ca.input.value;
      if (!Object.keys(change).length) { showToast(twT('admin.support.same'), 'info'); return; }
      TwAdminShell.run(ACTIONS.update, { id: t.public_id, body: change })
        .then(function (res) { if (res && res.ok) openTicket(t.public_id); });
    });

    // reply
    var form = el('div', 'sp-form');
    var reply = F.field({ labelKey: 'admin.support.reply.label', required: true, kind: 'textarea', rows: 4,
                          max: twLimit('support_body_max'), hintKey: 'admin.support.reply.hint' });
    form.appendChild(reply.wrap);
    var acts = el('div', 'sp-actions');
    meta.next_statuses.forEach(function (next) {   // awaiting_user «نحتاج معلومات» · resolved «تم الحل»
      var send = button('admin.support.reply.' + next, next === 'resolved' ? 'tw-btn' : 'tw-btn tw-btn-ghost');
      send.addEventListener('click', function () {
        var text = reply.input.value.trim();
        F.setError(reply, text ? '' : twT('support.error.required'));
        if (!text) return;
        TwAdminShell.run(ACTIONS.reply, { id: t.public_id, body: text, next: next })
          .then(function (res) { if (res && res.ok) openTicket(t.public_id); });
      });
      acts.appendChild(send);
    });
    form.appendChild(acts);
    body.appendChild(form);
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

  twApi('/support/meta', { auth: false }).then(function (res) {
    var faq = (res.ok && res.data && res.data.faq) || {};
    Object.keys(faq).forEach(function (cat) { faq[cat].forEach(function (id) { faqCat[id] = cat; }); });
    var fields = (res.ok && res.data && res.data.fields) || {};
    Object.keys(fields).forEach(function (cat) {
      fields[cat].forEach(function (f) { if (f.type === 'enum') enumField[f.key] = true; });
    });
  });
  loadList();
})();
