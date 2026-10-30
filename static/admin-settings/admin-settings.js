// static/admin-settings/admin-settings.js — admin settings page (route: server.py → admin_settings_page · task 4.1)
//   - GET /admin/settings → items grouped (messages · posts · comments · reports · admin): label · description ·
//     current value · default · allowed range · changed · requires_restart (shown before saving)
//   - security settings (item.security — task 4.2) in their own section after the others: warning hint · «أمني»
//     badge · save / reset need the typed word (TwAdminShell.confirm typeWord) with the warning text
//   - 401 = session over → TwAdminShell back to login · 403 = no settings.edit → message / toast on this page,
//     session kept (permissionAware — task 4.2)
//   - save = PUT /admin/settings/{key} {value} · reset = POST /admin/settings/{key}/reset — both through
//     TwAdminShell.run (confirm with old → new first) · the server checks type + range (422) — the page check is UX only
//   - session / header / menu / expiry = TwAdminShell · text: twT (admin.settings.* / settings.item.*) ·
//     numbers: twFormatNumber · icons: twIcon · colors: --color-* tokens
(function () {
  'use strict';
  if (!TwAdminShell.start()) return;
  var root = document.getElementById('asRoot');
  var data = null;

  document.title = twT('page.title', { page: twT('admin.settings.title') });
  TwAdminShell.mount();
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function message(key) {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-msg', twT(key)));
  }
  function num(n) { return twFormatNumber(n); }

  // ── the only writes on this page ──
  var SEC_WORD = 'admin.settings.security.word';
  var ACTIONS = {
    save: {
      confirm: function (c) {
        if (c.security) return { title: 'admin.settings.save.title', confirm: 'admin.settings.save.confirm', danger: true,
                                 message: 'admin.settings.security.save.message', typeWord: SEC_WORD };
        return { title: 'admin.settings.save.title', confirm: 'admin.settings.save.confirm',
                 message: c.restart ? 'admin.settings.save.message_restart' : 'admin.settings.save.message' };
      },
      request: function (c) { return { url: '/admin/settings/' + encodeURIComponent(c.key), method: 'PUT', body: { value: c.value } }; },
      ok: function (d) { return d && d.ok && d.data && d.data.setting; },
      permissionAware: true, forbidden: 'admin.settings.forbidden',
      done: 'admin.done.setting_saved' },
    reset: {
      confirm: function (c) {
        if (c.security) return { title: 'admin.settings.reset.title', confirm: 'admin.settings.reset.confirm', danger: true,
                                 message: 'admin.settings.security.reset.message', typeWord: SEC_WORD };
        return { title: 'admin.settings.reset.title', message: 'admin.settings.reset.message', confirm: 'admin.settings.reset.confirm' };
      },
      request: function (c) { return { url: '/admin/settings/' + encodeURIComponent(c.key) + '/reset', method: 'POST' }; },
      ok: function (d) { return d && d.ok && d.data && d.data.setting; },
      permissionAware: true, forbidden: 'admin.settings.forbidden',
      done: 'admin.done.setting_reset' },
  };

  function replaceItem(it) {
    data.items = data.items.map(function (x) { return x.key === it.key ? it : x; });
    render();
  }

  function onSave(it, input) {
    var v = Number(input.value);
    if (input.value.trim() === '' || !Number.isInteger(v) || v < it.min || v > it.max) {
      showToast(twT('admin.settings.invalid', { min: num(it.min), max: num(it.max) }), 'error');
      return;
    }
    if (v === it.value) { showToast(twT('admin.settings.same'), 'info'); return; }
    TwAdminShell.run(ACTIONS.save, { key: it.key, value: v, label: it.label, old: num(it.value), new: num(v),
                                     restart: it.requires_restart, security: !!it.security })
      .then(function (res) { if (res && res.ok) replaceItem(res.data.data.setting); });
  }

  function onReset(it) {
    TwAdminShell.run(ACTIONS.reset, { key: it.key, label: it.label, old: num(it.value), new: num(it.default),
                                      security: !!it.security })
      .then(function (res) { if (res && res.ok) replaceItem(res.data.data.setting); });
  }

  function itemRow(body, it) {
    var row = el('div', 'as-item'), head = el('div', 'as-head'), id = 'as-' + it.key;
    row.setAttribute('data-setting', it.key);
    var label = el('label', 'as-label', it.label);
    label.setAttribute('for', id);
    head.appendChild(label);
    if (it.security) head.appendChild(el('span', 'tw-adm-pill is-danger', twT('admin.settings.security.badge')));
    if (it.changed) head.appendChild(el('span', 'tw-adm-pill is-warn', twT('admin.settings.changed')));
    row.appendChild(head);
    row.appendChild(el('p', 'as-desc', it.description));
    if (it.requires_restart) row.appendChild(el('p', 'as-restart', twT('admin.settings.restart')));
    var line = el('div', 'as-row'), input = el('input', 'tw-input');
    input.type = 'number';
    input.id = id;
    input.min = it.min;
    input.max = it.max;
    input.step = 1;
    input.inputMode = 'numeric';
    input.value = it.value;
    var save = el('button', 'tw-btn', twT('admin.settings.save'));
    save.type = 'button';
    save.addEventListener('click', function () { onSave(it, input); });
    var reset = el('button', 'tw-btn tw-btn-ghost', twT('admin.settings.reset'));
    reset.type = 'button';
    reset.disabled = !it.changed;
    reset.addEventListener('click', function () { onReset(it); });
    line.appendChild(input);
    line.appendChild(save);
    line.appendChild(reset);
    row.appendChild(line);
    row.appendChild(el('p', 'as-range', twT('admin.settings.range', { min: num(it.min), max: num(it.max), default: num(it.default) })));
    body.appendChild(row);
  }

  function groupCards(parent, security) {
    data.groups.forEach(function (g) {
      var items = data.items.filter(function (it) { return it.group === g && !!it.security === security; });
      if (!items.length) return;
      var body = TwAdminShell.card(parent, { titleKey: 'admin.settings.group.' + g, hintKey: 'admin.settings.group.' + g + '.hint' });
      items.forEach(function (it) { itemRow(body, it); });
    });
  }

  function render() {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-hint', twT('admin.settings.hint')));
    groupCards(root, false);
    if (!data.items.some(function (it) { return it.security; })) return;
    var sec = el('section', 'as-sec');
    sec.setAttribute('data-settings-section', 'security');
    sec.appendChild(el('h2', 'as-sec-title', twT('admin.settings.security.title')));
    sec.appendChild(el('p', 'as-sec-hint', twT('admin.settings.security.hint')));
    groupCards(sec, true);
    root.appendChild(sec);
  }

  function load() {
    TwAdminSession.fetch('/admin/settings', { permissionAware: true })
      .then(function (r) {
        if (r.status === 403) return { forbidden: true };   // no settings.edit — message here, session kept
        return r.ok ? r.json() : null;                       // 401 → session over → shell → login
      })
      .then(function (j) {
        if (j && j.forbidden) { message('admin.settings.forbidden'); return; }
        if (!j || !j.data) { if (TwAdminSession.hasLiveToken()) message('admin.settings.load_error'); return; }
        data = j.data;
        render();
      })
      .catch(function () { message('admin.settings.load_error'); });
  }

  // test hook (node tests/test_admin_shell_runtime.js · tests/test_admin_settings_page_runtime.js) — read only
  window.TwAdminSettings = { ACTIONS: ACTIONS };
  TwAdminShell.whenAllowed(root, load);   // task 8.4c-1 — no settings.edit → empty state
}());
