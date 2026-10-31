// static/admin-staff/admin-staff.js — the owner's staff screen (route: server.py → admin_staff_page ·
// task 8.4c-2b-2 · docs/rules/admin-staff.md rule 16)
//   - section 'staff' (perm staff.manage — owner only): a staff member never sees it in the menu; the page itself
//     asks for data only through TwAdminShell.whenAllowed (else the empty state admin.perm.denied)
//   - tab «الموظفون»: GET /admin/staff + GET /admin/roles (catalog GRANTABLE with its Arabic labels) → per member:
//     name · email · status (invited / active / suspended) · role · last login · authenticator bound · details =
//     the effective perms with their source (role / extra allow / denied — permRows)
//   - actions by status (STATUS_ACTIONS — the rest never render): invited → resend · cancel (DELETE) ·
//     active → access · suspend · mfa-reset · suspended → restore · access. a danger confirmation (name + effect) before
//     suspend · mfa-reset · cancel · role delete.
//   - tab «الأدوار»: list + staff count · add / edit (name + checkboxes from the catalog) · delete (role_in_use → a
//     message, the page stays)
//   - every write = TwAdminShell.run (confirm → TwAdminSession.fetch → 428 → the shell's ONE step-up dialog → one
//     retry) · every error code → its own twT text (ERRORS) · success → both lists read again · a button is
//     disabled while its request runs (one request per action at a time)
//   - no token / invite link anywhere (the server never returns them) · text: twT · icons: twIcon · colors: tokens
(function () {
  'use strict';
  if (!TwAdminShell.start()) return;
  var root = document.getElementById('stRoot');

  document.title = twT('page.title', { page: twT('admin.staff.title') });
  TwAdminShell.mount();
  twTApply(document.body);
  twIcon.hydrate(document.body);

  var state = { staff: [], roles: [], grantable: [], tab: 'staff' };
  var busy = {};

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, key, onClick) {
    var b = el('button', cls, twT(key));
    b.type = 'button';
    b.addEventListener('click', function () { onClick(b); });
    return b;
  }
  function message(key) {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-msg', twT(key)));
  }
  function has(list, v) { return (list || []).indexOf(v) !== -1; }

  // ── error code → message (docs/rules/admin-staff.md rules 10 + 14) ──
  var ERRORS = {
    not_invited: 'admin.staff.error.not_invited', not_active: 'admin.staff.error.not_active',
    staff_active: 'admin.staff.error.staff_active', not_suspended: 'admin.staff.error.not_suspended',
    role_in_use: 'admin.staff.error.role_in_use', already_invited: 'admin.staff.error.already_invited',
    email_taken: 'admin.staff.error.email_taken', name_taken: 'admin.staff.error.name_taken',
    invalid_perms: 'admin.staff.error.invalid_perms', invalid_role: 'admin.staff.error.invalid_role',
    role_not_found: 'admin.staff.error.role_not_found', staff_not_found: 'admin.staff.error.staff_not_found',
    invalid_name: 'admin.staff.error.invalid_name', name_too_long: 'admin.staff.error.name_too_long',
    invalid_staff_name: 'admin.staff.error.invalid_staff_name', staff_name_too_long: 'admin.staff.error.staff_name_too_long',
    invalid_email: 'admin.staff.error.invalid_email',
    '429': 'admin.staff.error.rate', '500': 'admin.staff.error.server',
  };
  // fields a 4xx code belongs to (shown under the field in the open form, the form stays)
  var FIELD_OF = { already_invited: 'email', email_taken: 'email', invalid_email: 'email',
                   invalid_staff_name: 'name', staff_name_too_long: 'name',
                   invalid_name: 'name', name_too_long: 'name', name_taken: 'name' };

  function okBody(d) { return !!(d && d.ok === true); }
  function act(a) {
    a.permissionAware = true;                 // 403 = "owner only" toast, the session stays
    a.forbidden = 'admin.staff.forbidden';
    a.fail = 'admin.staff.error.network';     // network / unknown error
    a.errors = ERRORS;
    a.ok = okBody;
    return a;
  }
  function danger(name) {
    return { title: 'admin.staff.' + name + '.title', message: 'admin.staff.' + name + '.message',
             confirm: 'admin.staff.' + name + '.confirm', danger: true };
  }
  function plain(name) {
    return { title: 'admin.staff.' + name + '.title', message: 'admin.staff.' + name + '.message',
             confirm: 'admin.staff.' + name + '.confirm' };
  }

  // ── the only writes on this page ──
  var ACTIONS = {
    invite:  act({ request: function (c) { return { url: '/admin/staff/invite', method: 'POST',
                     body: { name: c.name, email: c.email, role_id: c.role_id, allow: c.allow, deny: c.deny } }; } }),
    resend:  act({ confirm: plain('resend'),
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id) + '/invite/resend', method: 'POST' }; } }),
    cancel:  act({ confirm: danger('cancel'), done: 'admin.staff.done.cancelled',
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id), method: 'DELETE' }; } }),
    access:  act({ done: 'admin.staff.done.access',
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id) + '/access', method: 'PUT',
                     body: { role_id: c.role_id, allow: c.allow, deny: c.deny } }; } }),
    suspend: act({ confirm: danger('suspend'), done: 'admin.staff.done.suspended',
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id) + '/suspend', method: 'POST' }; } }),
    restore: act({ confirm: plain('restore'), done: 'admin.staff.done.restored',
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id) + '/restore', method: 'POST' }; } }),
    mfa:     act({ confirm: danger('mfa'),
                   request: function (c) { return { url: '/admin/staff/' + Number(c.id) + '/mfa-reset', method: 'POST' }; } }),
    roleSave: act({ done: 'admin.staff.done.role_saved',
                    request: function (c) {
                      return c.id ? { url: '/admin/roles/' + Number(c.id), method: 'PUT', body: { name: c.name, perms: c.perms } }
                                  : { url: '/admin/roles', method: 'POST', body: { name: c.name, perms: c.perms } }; } }),
    roleDelete: act({ confirm: danger('role_delete'), done: 'admin.staff.done.role_deleted',
                      request: function (c) { return { url: '/admin/roles/' + Number(c.id), method: 'DELETE' }; } }),
  };
  // the link was emailed or not (email_sent from the reply — the link itself never reaches this page)
  var SENT_TOAST = { invite: 'admin.staff.done.invited', resend: 'admin.staff.done.resent', mfa: 'admin.staff.done.mfa' };

  // buttons that apply per status — anything else never renders
  var STATUS_ACTIONS = { invited: ['resend', 'cancel'], active: ['access', 'suspend', 'mfa'], suspended: ['restore', 'access'] };
  var DANGER = { cancel: 1, suspend: 1, mfa: 1 };

  // Pure (tests read it): one staff member → its effective perms with the source of each
  //   [{perm, label, source: 'role' | 'allow' | 'deny'}] — role ∪ allow − deny (the server's effective_perms decides
  //   what is on; denied perms are listed as such so the owner sees what is blocked)
  function permRows(st, roles, grantable) {
    var role = null;
    (roles || []).forEach(function (r) { if (st.role && r.id === st.role.id) role = r; });
    var rolePerms = role ? role.perms : [], eff = st.effective_perms || [];
    var out = [];
    (grantable || []).forEach(function (g) {
      var p = g.perm;
      if (has(st.deny, p)) { if (has(rolePerms, p) || has(st.allow, p)) out.push({ perm: p, label: g.label, source: 'deny' }); return; }
      if (!has(eff, p)) return;
      out.push({ perm: p, label: g.label, source: has(rolePerms, p) || !has(st.allow, p) ? 'role' : 'allow' });
    });
    return out;
  }

  function codeOf(res) {
    var d = res && res.data;
    return d && d.error && typeof d.error === 'object' ? d.error.code || '' : '';
  }

  // one request per action + target at a time; the button stays disabled until the reply
  function doRun(key, ctx, b) {
    var id = key + ':' + (ctx.id || '');
    if (busy[id]) return Promise.resolve(null);
    busy[id] = true;
    if (b) b.disabled = true;
    return TwAdminShell.run(ACTIONS[key], ctx).then(function (res) {
      busy[id] = false;
      if (b) b.disabled = false;
      if (res && res.ok) {
        if (SENT_TOAST[key]) {
          var sent = res.data && res.data.data && res.data.data.email_sent === true;
          showToast(twT(SENT_TOAST[key] + (sent ? '' : '_no_email')), sent ? 'success' : 'info');
        }
        load();
      }
      return res;
    });
  }

  // ── forms ──
  function field(labelKey, input) {
    var l = el('label', '', twT(labelKey));
    l.appendChild(input);
    var err = el('span', 'tw-adm-field-err');
    err.setAttribute('role', 'alert');
    err.hidden = true;
    l.appendChild(err);
    input.addEventListener('input', function () { err.hidden = true; err.textContent = ''; });
    return { label: l, input: input, error: function (t) { err.textContent = t || ''; err.hidden = !t; } };
  }
  function textInput(type, value) {
    var i = el('input', 'tw-input');
    i.type = type;
    i.autocomplete = 'off';
    if (value != null) i.value = value;
    return i;
  }
  function roleById(id) {
    var out = null;
    state.roles.forEach(function (r) { if (r.id === id) out = r; });
    return out;
  }

  // role select + one choice per GRANTABLE perm: by role / allow / deny → read() = {role_id, allow, deny}
  function accessFields(form, init) {
    var sel = el('select', 'tw-input ep-select');
    sel.appendChild(new Option(twT('admin.staff.role.none'), ''));
    state.roles.forEach(function (r) { sel.appendChild(new Option(r.name, String(r.id))); });
    sel.value = init.role ? String(init.role.id) : '';
    var roleF = field('admin.staff.field.role', sel);
    form.appendChild(roleF.label);
    var wrap = el('div', 'st-f');
    wrap.appendChild(el('span', '', twT('admin.staff.field.perms')));
    wrap.appendChild(el('span', 'tw-adm-hint', twT('admin.staff.access.hint')));
    var list = el('div', 'st-plist'), choices = {}, inRole = {};
    state.grantable.forEach(function (g) {
      var row = el('div', 'st-prow'), lab = el('span', 'st-plabel', g.label);
      var tag = el('span', 'tw-adm-pill is-ok', twT('admin.staff.perm.in_role'));
      lab.appendChild(tag);
      var c = el('select', 'tw-input ep-select');
      c.setAttribute('aria-label', g.label);
      c.setAttribute('data-perm', g.perm);
      [['', 'admin.staff.perm.inherit'], ['allow', 'admin.staff.perm.allow'], ['deny', 'admin.staff.perm.deny']]
        .forEach(function (o) { c.appendChild(new Option(twT(o[1]), o[0])); });
      c.value = has(init.deny, g.perm) ? 'deny' : has(init.allow, g.perm) ? 'allow' : '';
      row.appendChild(lab);
      row.appendChild(c);
      list.appendChild(row);
      choices[g.perm] = c;
      inRole[g.perm] = tag;
    });
    function markRole() {
      var r = roleById(Number(sel.value));
      Object.keys(inRole).forEach(function (p) { inRole[p].hidden = !(r && has(r.perms, p)); });
    }
    sel.addEventListener('change', markRole);
    markRole();
    wrap.appendChild(list);
    form.appendChild(wrap);
    return {
      read: function () {
        var allow = [], deny = [];
        Object.keys(choices).forEach(function (p) {
          if (choices[p].value === 'allow') allow.push(p);
          else if (choices[p].value === 'deny') deny.push(p);
        });
        return { role_id: sel.value ? Number(sel.value) : null, allow: allow, deny: deny };
      },
      role: roleF,
    };
  }

  // a form in a DS-OVL dialog: send → run(); a field error keeps the dialog open
  function formModal(titleKey, vars, sendKey, form, fields, send) {
    return twModal({
      title: twT(titleKey, vars), content: form,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT(sendKey), variant: 'primary', onClick: function () {
          return send().then(function (res) {
            if (res && res.ok) return true;
            var f = fields[FIELD_OF[codeOf(res)]];
            if (f) f.error(twT(ERRORS[codeOf(res)]));
            return false;
          });
        } },
      ],
    });
  }

  function openInvite() {
    var form = el('div', 'st-form');
    var name = field('admin.staff.field.name', textInput('text'));
    var email = field('admin.staff.field.email', textInput('email'));
    email.input.dir = 'ltr';
    form.appendChild(name.label);
    form.appendChild(email.label);
    var acc = accessFields(form, { role: null, allow: [], deny: [] });
    return formModal('admin.staff.invite.title', null, 'admin.staff.invite.send', form, { name: name, email: email, role_id: acc.role },
      function () {
        var a = acc.read();
        return doRun('invite', { name: name.input.value.trim(), email: email.input.value.trim(),
                                 role_id: a.role_id, allow: a.allow, deny: a.deny });
      });
  }

  function openAccess(st) {
    var form = el('div', 'st-form');
    var acc = accessFields(form, st);
    return formModal('admin.staff.access.title', { name: st.name }, 'admin.staff.access.save', form, { role_id: acc.role },
      function () {
        var a = acc.read();
        return doRun('access', { id: st.id, name: st.name, role_id: a.role_id, allow: a.allow, deny: a.deny });
      });
  }

  function openRole(role) {
    var form = el('div', 'st-form');
    var name = field('admin.staff.role.field.name', textInput('text', role ? role.name : ''));
    form.appendChild(name.label);
    var box = el('div', 'st-f');
    box.appendChild(el('span', '', twT('admin.staff.field.perms')));
    var list = el('div', 'st-plist'), checks = [];
    state.grantable.forEach(function (g) {
      var l = el('label', 'st-check'), c = el('input');
      c.type = 'checkbox';
      c.value = g.perm;
      c.checked = !!(role && has(role.perms, g.perm));
      l.appendChild(c);
      l.appendChild(el('span', '', g.label));
      list.appendChild(l);
      checks.push(c);
    });
    box.appendChild(list);
    form.appendChild(box);
    return formModal(role ? 'admin.staff.role.edit.title' : 'admin.staff.role.new.title', { name: role ? role.name : '' },
      'admin.staff.role.save', form, { name: name },
      function () {
        var perms = checks.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
        return doRun('roleSave', { id: role ? role.id : 0, name: name.input.value.trim(), perms: perms });
      });
  }

  // ── staff tab ──
  var STATUS_PILL = { invited: 'is-warn', active: 'is-ok', suspended: 'is-danger' };
  function staffRow(body, st) {
    var row = el('div', 'tw-adm-row'), main = el('div', 'tw-adm-row-main'), head = el('div', 'st-head');
    row.setAttribute('data-staff', String(st.id));
    head.appendChild(el('span', 'tw-adm-row-title', st.name));
    var pill = el('span', 'tw-adm-pill ' + (STATUS_PILL[st.status] || 'is-muted'), twT('admin.staff.status.' + st.status));
    pill.setAttribute('data-status', st.status);
    head.appendChild(pill);
    main.appendChild(head);
    if (st.email) {
      var em = el('div', 'tw-adm-row-sub', st.email);
      em.dir = 'ltr';
      main.appendChild(em);
    }
    var meta = el('div', 'st-meta');
    meta.appendChild(el('span', '', twT('admin.staff.role_label', { role: st.role ? st.role.name : twT('admin.staff.role.none') })));
    meta.appendChild(el('span', '', st.last_login_at ? twT('admin.staff.last_login', { when: twFormatDateTime(st.last_login_at) })
                                                     : twT('admin.staff.last_login_never')));
    meta.appendChild(el('span', '', twT(st.mfa_bound ? 'admin.staff.mfa.bound' : 'admin.staff.mfa.unbound')));
    main.appendChild(meta);
    row.appendChild(main);

    var acts = el('div', 'tw-adm-row-acts'), perms = el('ul', 'st-perms');
    perms.hidden = true;
    perms.setAttribute('data-perms', '');
    var toggle = btn('tw-act tw-act-secondary', 'admin.staff.act.details', function () {
      perms.hidden = !perms.hidden;
      toggle.setAttribute('aria-expanded', String(!perms.hidden));
    });
    toggle.setAttribute('aria-expanded', 'false');
    acts.appendChild(toggle);
    (STATUS_ACTIONS[st.status] || []).forEach(function (k) {
      var b = btn('tw-act ' + (DANGER[k] ? 'tw-act-danger' : 'tw-act-secondary'), 'admin.staff.act.' + k, function (bt) {
        if (k === 'access') openAccess(st);
        else doRun(k, { id: st.id, name: st.name }, bt);
      });
      b.setAttribute('data-act', k);
      acts.appendChild(b);
    });
    row.appendChild(acts);

    var rows = permRows(st, state.roles, state.grantable);
    if (!rows.length) perms.appendChild(el('li', '', twT('admin.staff.perms.none')));
    rows.forEach(function (p) {
      var li = el('li', p.source === 'deny' ? 'is-deny' : '');
      li.setAttribute('data-perm', p.perm);
      li.setAttribute('data-source', p.source);
      li.appendChild(el('span', '', p.label));
      li.appendChild(el('span', 'tw-adm-pill ' + (p.source === 'deny' ? 'is-danger' : p.source === 'allow' ? 'is-warn' : 'is-muted'),
                        twT('admin.staff.src.' + p.source)));
      perms.appendChild(li);
    });
    row.appendChild(perms);
    body.appendChild(row);
  }

  function renderStaff(panel) {
    panel.textContent = '';
    var tools = el('div', 'st-tools');
    tools.appendChild(btn('tw-act tw-act-primary', 'admin.staff.add', openInvite));
    panel.appendChild(tools);
    var body = TwAdminShell.card(panel, { titleKey: 'admin.staff.tab.staff', hintKey: 'admin.staff.list.hint', icon: 'users' });
    if (!state.staff.length) { body.appendChild(el('p', 'tw-adm-msg', twT('admin.staff.empty'))); return; }
    state.staff.forEach(function (st) { staffRow(body, st); });
  }

  // ── roles tab ──
  function renderRoles(panel) {
    panel.textContent = '';
    var tools = el('div', 'st-tools');
    tools.appendChild(btn('tw-act tw-act-primary', 'admin.staff.roles.add', function () { openRole(null); }));
    panel.appendChild(tools);
    var body = TwAdminShell.card(panel, { titleKey: 'admin.staff.tab.roles', hintKey: 'admin.staff.roles.hint', icon: 'shield' });
    if (!state.roles.length) { body.appendChild(el('p', 'tw-adm-msg', twT('admin.staff.roles.empty'))); return; }
    var labels = {};
    state.grantable.forEach(function (g) { labels[g.perm] = g.label; });
    state.roles.forEach(function (r) {
      var row = el('div', 'tw-adm-row'), main = el('div', 'tw-adm-row-main'), head = el('div', 'st-head');
      row.setAttribute('data-role', String(r.id));
      head.appendChild(el('span', 'tw-adm-row-title', r.name));
      head.appendChild(el('span', 'tw-adm-pill is-muted', twT('admin.staff.roles.count', { n: twFormatNumber(r.staff_count) })));
      main.appendChild(head);
      main.appendChild(el('div', 'tw-adm-row-sub', r.perms.length
        ? r.perms.map(function (p) { return labels[p] || p; }).join(' · ') : twT('admin.staff.perms.none')));
      row.appendChild(main);
      var acts = el('div', 'tw-adm-row-acts');
      var e = btn('tw-act tw-act-secondary', 'admin.staff.act.edit', function () { openRole(r); });
      e.setAttribute('data-act', 'role_edit');
      var d = btn('tw-act tw-act-danger', 'admin.staff.act.delete', function (bt) { doRun('roleDelete', { id: r.id, name: r.name }, bt); });
      d.setAttribute('data-act', 'role_delete');
      acts.appendChild(e);
      acts.appendChild(d);
      row.appendChild(acts);
      body.appendChild(row);
    });
  }

  // ── tabs ──
  var TABS = ['staff', 'roles'], panels = {}, tabBtns = {};
  function show(tab) {
    state.tab = tab;
    TABS.forEach(function (t) {
      tabBtns[t].setAttribute('aria-selected', String(t === tab));
      tabBtns[t].tabIndex = t === tab ? 0 : -1;
      panels[t].hidden = t !== tab;
    });
  }
  function build() {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-hint', twT('admin.staff.hint')));
    var list = el('div', 'st-tabs');
    list.setAttribute('role', 'tablist');
    list.setAttribute('aria-label', twT('admin.staff.tabs_label'));
    root.appendChild(list);
    TABS.forEach(function (t, i) {
      var b = btn('tw-btn tw-btn-ghost', 'admin.staff.tab.' + t, function () { show(t); });
      b.id = 'st-tab-' + t;
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-controls', 'st-panel-' + t);
      b.setAttribute('data-tab', t);
      b.addEventListener('keydown', function (e) {
        var d = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : 0;   // RTL: left = next
        if (!d) return;
        var next = TABS[(i + d + TABS.length) % TABS.length];
        show(next);
        try { tabBtns[next].focus(); } catch (er) {}
      });
      list.appendChild(b);
      tabBtns[t] = b;
      var p = el('div');
      p.id = 'st-panel-' + t;
      p.setAttribute('role', 'tabpanel');
      p.setAttribute('aria-labelledby', b.id);
      p.setAttribute('data-panel', t);
      root.appendChild(p);
      panels[t] = p;
    });
  }
  function render() {
    if (!panels.staff) build();
    renderStaff(panels.staff);
    renderRoles(panels.roles);
    show(state.tab);
  }

  function getJson(url) {
    return TwAdminSession.fetch(url, { cache: 'no-store', permissionAware: true }).then(function (r) {
      if (r.status === 403) return { forbidden: true };   // not the owner — message here, session kept
      return r.ok ? r.json() : null;                       // 401 → session over → shell → login
    });
  }
  function load() {
    return Promise.all([getJson('/admin/staff'), getJson('/admin/roles')]).then(function (res) {
      var s = res[0], r = res[1];
      if ((s && s.forbidden) || (r && r.forbidden)) { message('admin.staff.forbidden'); return; }
      if (!s || !s.data || !r || !r.data) { if (TwAdminSession.hasLiveToken()) message('admin.staff.load_error'); return; }
      state.staff = s.data.staff || [];
      state.roles = r.data.roles || [];
      state.grantable = r.data.grantable || [];
      render();
    }).catch(function (e) { console.error('[admin-staff] load:', e); message('admin.staff.load_error'); });
  }

  // test hook (node tests/test_admin_staff_runtime.js) — read only
  window.TwAdminStaff = { ACTIONS: ACTIONS, ERRORS: ERRORS, STATUS_ACTIONS: STATUS_ACTIONS, permRows: permRows,
                          openInvite: openInvite, openAccess: openAccess, openRole: openRole, load: load };
  TwAdminShell.whenAllowed(root, load);   // staff.manage (owner only) — a staff member gets the empty state
}());
