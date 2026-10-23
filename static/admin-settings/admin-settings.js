// static/admin-settings/admin-settings.js — admin settings page (route: server.py → admin_settings_page · task 4.1)
//   - GET /admin/settings → items grouped (messages · posts · comments · reports · admin): label · description ·
//     current value · default · allowed range · changed · requires_restart (shown before saving)
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
  var ACTIONS = {
    save: {
      confirm: function (c) {
        return { title: 'admin.settings.save.title', confirm: 'admin.settings.save.confirm',
                 message: c.restart ? 'admin.settings.save.message_restart' : 'admin.settings.save.message' };
      },
      request: function (c) { return { url: '/admin/settings/' + encodeURIComponent(c.key), method: 'PUT', body: { value: c.value } }; },
      ok: function (d) { return d && d.ok && d.data && d.data.setting; },
      done: 'admin.done.setting_saved' },
    reset: {
      confirm: { title: 'admin.settings.reset.title', message: 'admin.settings.reset.message', confirm: 'admin.settings.reset.confirm' },
      request: function (c) { return { url: '/admin/settings/' + encodeURIComponent(c.key) + '/reset', method: 'POST' }; },
      ok: function (d) { return d && d.ok && d.data && d.data.setting; },
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
                                     restart: it.requires_restart })
      .then(function (res) { if (res && res.ok) replaceItem(res.data.data.setting); });
  }

  function onReset(it) {
    TwAdminShell.run(ACTIONS.reset, { key: it.key, label: it.label, old: num(it.value), new: num(it.default) })
      .then(function (res) { if (res && res.ok) replaceItem(res.data.data.setting); });
  }

  function itemRow(body, it) {
    var row = el('div', 'as-item'), head = el('div', 'as-head'), id = 'as-' + it.key;
    row.setAttribute('data-setting', it.key);
    var label = el('label', 'as-label', it.label);
    label.setAttribute('for', id);
    head.appendChild(label);
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

  function render() {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-hint', twT('admin.settings.hint')));
    data.groups.forEach(function (g) {
      var items = data.items.filter(function (it) { return it.group === g; });
      if (!items.length) return;
      var body = TwAdminShell.card(root, { titleKey: 'admin.settings.group.' + g, hintKey: 'admin.settings.group.' + g + '.hint' });
      items.forEach(function (it) { itemRow(body, it); });
    });
  }

  function load() {
    TwAdminSession.fetch('/admin/settings')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.data) { if (TwAdminSession.hasLiveToken()) message('admin.settings.load_error'); return; }   // 401 / 403 → shell → login
        data = j.data;
        render();
      })
      .catch(function () { message('admin.settings.load_error'); });
  }

  // test hook (node tests/test_admin_shell_runtime.js) — the page's actions, read only
  window.TwAdminSettings = { ACTIONS: ACTIONS };
  load();
}());
