// static/admin-content/admin-content.js — admin content screens (route: server.py → admin_content_page · phase 5b)
//   three tabs (role=tablist), each loaded when first opened:
//   - strings: GET /admin/strings → every key of tw_strings.json (no new keys) · search by key or text ·
//     default + current value · save = PUT /admin/strings with the whole override map (this key set) ·
//     reset = the same PUT with this key left out (empty = default — tw_strings.validate_overrides)
//   - colors: GET /admin/theme/colors → the EDITABLE tokens (--color-brand-primary · --color-brand-accent) +
//     their tw_shared.css defaults · color picker + #RRGGBB field · live preview (button · link · badge) ·
//     WCAG contrast vs the page background and the button text: < 4.5 warning · < 3 save blocked ·
//     save / reset = PUT /admin/theme/colors (a token left out = its default)
//   - news: GET /admin/news → table (title · status · start · end · active_now from the server's
//     NEWS_ACTIVE_SQL — no "active" rule here) · create / edit (DS-DATE twDateTimeField, browser local
//     time → toISOString UTC) · archive · delete (typed word)
//   - 401 = session over → TwAdminShell back to login · 403 = no content.edit → message on the page /
//     toast on a write, session kept (permissionAware — same as admin-settings)
//   - every write = TwAdminShell.run (confirm first) · the server validates — page checks are UX only
//   - text: twT (admin.content.*) · dates: twFormatDateTime · icons: twIcon · colors: --color-* tokens
(function () {
  'use strict';
  if (!TwAdminShell.start()) return;
  var root = document.getElementById('acRoot');
  var TABS = ['strings', 'colors', 'news'];
  var STR_MAX_ROWS = 50;
  var FORBIDDEN = 'admin.content.forbidden';
  var panels = {}, loaded = {}, loading = {}, tabBtns = {};

  document.title = twT('page.title', { page: twT('admin.content.title') });
  TwAdminShell.mount();
  twTApply(document.body);
  twIcon.hydrate(document.body);

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, key, fn) {
    var b = el('button', cls, twT(key));
    b.type = 'button';
    b.addEventListener('click', fn);
    return b;
  }
  function message(box, key) {
    box.textContent = '';
    box.appendChild(el('p', 'tw-adm-msg', twT(key)));
  }

  // GET through the admin session — 403 → {forbidden} (message here, session kept) · 401 → shell → login
  function getJson(url) {
    return TwAdminSession.fetch(url, { permissionAware: true, cache: 'no-store' })
      .then(function (r) {
        if (r.status === 403) return { forbidden: true };
        return r.ok ? r.json() : null;
      })
      .catch(function () { return null; });
  }
  function loadInto(box, url, render) {
    message(box, 'common.loading');
    return getJson(url).then(function (j) {
      if (j && j.forbidden) { message(box, FORBIDDEN); return false; }
      if (!j) { if (TwAdminSession.hasLiveToken()) message(box, 'admin.content.load_error'); return false; }
      render(j);
      return true;
    });
  }

  // ══ the only writes on this page ══
  var ok = function (d) { return !!(d && d.ok); };
  var okNews = function (d) { return !!(d && d.success); };
  var ACTIONS = {
    'strings.save': {
      confirm: { title: 'admin.content.strings.save.title', message: 'admin.content.strings.save.message', confirm: 'admin.content.save' },
      request: function (c) { return { url: '/admin/strings', method: 'PUT', body: { overrides: c.overrides } }; },
      ok: ok, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.string_saved' },
    'strings.reset': {
      confirm: { title: 'admin.content.strings.reset.title', message: 'admin.content.strings.reset.message', confirm: 'admin.content.reset' },
      request: function (c) { return { url: '/admin/strings', method: 'PUT', body: { overrides: c.overrides } }; },
      ok: ok, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.string_reset' },
    'colors.save': {
      confirm: { title: 'admin.content.colors.save.title', message: 'admin.content.colors.save.message', confirm: 'admin.content.save' },
      request: function (c) { return { url: '/admin/theme/colors', method: 'PUT', body: { overrides: c.overrides } }; },
      ok: ok, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.colors_saved' },
    'colors.reset': {
      confirm: { title: 'admin.content.colors.reset.title', message: 'admin.content.colors.reset.message', confirm: 'admin.content.reset' },
      request: function (c) { return { url: '/admin/theme/colors', method: 'PUT', body: { overrides: c.overrides } }; },
      ok: ok, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.colors_reset' },
    'news.save': {
      confirm: { title: 'admin.content.news.save.title', message: 'admin.content.news.save.message', confirm: 'admin.content.save' },
      request: function (c) {
        return c.id ? { url: '/admin/news/' + encodeURIComponent(c.id), method: 'PUT', body: c.body }
                    : { url: '/admin/news', method: 'POST', body: c.body };
      },
      ok: okNews, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.news_saved' },
    'news.archive': {
      confirm: { title: 'admin.content.news.archive.title', message: 'admin.content.news.archive.message', confirm: 'admin.content.news.archive' },
      request: function (c) { return { url: '/admin/news/' + encodeURIComponent(c.id), method: 'PUT', body: c.body }; },
      ok: okNews, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.news_archived' },
    'news.delete': {
      confirm: { title: 'admin.content.news.delete.title', message: 'admin.content.news.delete.message',
                 confirm: 'admin.content.news.delete', danger: true, typeWord: 'admin.content.news.delete.word' },
      request: function (c) { return { url: '/admin/news/' + encodeURIComponent(c.id), method: 'DELETE' }; },
      ok: okNews, permissionAware: true, forbidden: FORBIDDEN, done: 'admin.done.news_deleted' },
  };

  // ══ strings ══
  var str = null;   // {defaults, overrides, max_len}

  function strOverridesWith(key, text) {
    var o = {};
    Object.keys(str.overrides || {}).forEach(function (k) { o[k] = str.overrides[k]; });
    if (text == null || text === '' || text === str.defaults[key]) delete o[key];
    else o[key] = text;
    return o;
  }
  function strSaved(res) {
    if (res && res.ok && res.data && res.data.data) { str.overrides = res.data.data.overrides || {}; strList(); }
  }
  function strSave(key, input) {
    var text = input.value;
    var cur = Object.prototype.hasOwnProperty.call(str.overrides, key) ? str.overrides[key] : str.defaults[key];
    if (text === cur) { showToast(twT('admin.content.same'), 'info'); return; }
    if (str.max_len && text.length > str.max_len) { showToast(twT('admin.content.strings.too_long', { max: twFormatNumber(str.max_len) }), 'error'); return; }
    TwAdminShell.run(ACTIONS['strings.save'], { key: key, overrides: strOverridesWith(key, text) }).then(strSaved);
  }
  function strReset(key) {
    TwAdminShell.run(ACTIONS['strings.reset'], { key: key, overrides: strOverridesWith(key, '') }).then(strSaved);
  }
  function strRow(list, key) {
    var changed = Object.prototype.hasOwnProperty.call(str.overrides, key);
    var def = str.defaults[key], cur = changed ? str.overrides[key] : def;
    var row = el('div', 'ac-item'), head = el('div', 'ac-head'), id = 'ac-s-' + key.replace(/[^a-zA-Z0-9_-]/g, '_');
    row.setAttribute('data-string', key);
    var label = el('label', 'ac-key', key);
    label.setAttribute('for', id);
    head.appendChild(label);
    if (changed) head.appendChild(el('span', 'tw-adm-pill is-warn', twT('admin.content.changed')));
    row.appendChild(head);
    row.appendChild(el('p', 'ac-def', twT('admin.content.strings.default', { text: def })));
    var input = el(String(def).length > 60 ? 'textarea' : 'input', 'tw-input');
    if (input.tagName.toLowerCase() === 'input') input.type = 'text';
    input.id = id;
    input.value = cur;
    if (str.max_len) input.maxLength = str.max_len;
    row.appendChild(input);
    var line = el('div', 'ac-row');
    line.appendChild(btn('tw-btn', 'admin.content.save', function () { strSave(key, input); }));
    var reset = btn('tw-btn tw-btn-ghost', 'admin.content.reset', function () { strReset(key); });
    reset.disabled = !changed;
    line.appendChild(reset);
    row.appendChild(line);
    list.appendChild(row);
  }
  var strSearch = null, strBox = null;
  function strMatches(q) {
    q = String(q || '').trim().toLowerCase();
    return Object.keys(str.defaults).filter(function (k) {
      if (!q) return true;
      var cur = Object.prototype.hasOwnProperty.call(str.overrides, k) ? str.overrides[k] : '';
      return k.toLowerCase().indexOf(q) !== -1 || String(str.defaults[k]).toLowerCase().indexOf(q) !== -1
        || String(cur).toLowerCase().indexOf(q) !== -1;
    });
  }
  function strList() {
    var keys = strMatches(strSearch.value);
    strBox.textContent = '';
    strBox.appendChild(el('p', 'ac-meta', twT('admin.content.strings.count', {
      shown: twFormatNumber(Math.min(keys.length, STR_MAX_ROWS)), total: twFormatNumber(keys.length) })));
    if (!keys.length) { strBox.appendChild(el('p', 'tw-adm-msg', twT('admin.content.strings.empty'))); return; }
    keys.slice(0, STR_MAX_ROWS).forEach(function (k) { strRow(strBox, k); });
    if (keys.length > STR_MAX_ROWS) strBox.appendChild(el('p', 'ac-meta', twT('admin.content.strings.more')));
  }
  function renderStrings(j) {
    var box = panels.strings;
    str = { defaults: (j.data && j.data.defaults) || {}, overrides: (j.data && j.data.overrides) || {},
            max_len: (j.data && j.data.max_len) || 0 };
    box.textContent = '';
    var body = TwAdminShell.card(box, { titleKey: 'admin.content.tab.strings', hintKey: 'admin.content.strings.hint' });
    strSearch = el('input', 'tw-input ac-search');
    strSearch.type = 'search';
    strSearch.placeholder = twT('admin.content.strings.search');
    strSearch.setAttribute('aria-label', twT('admin.content.strings.search'));
    strSearch.addEventListener('input', strList);
    body.appendChild(strSearch);
    strBox = el('div');
    body.appendChild(strBox);
    strList();
  }

  // ══ colors ══
  var HEX = /^#[0-9a-fA-F]{6}$/;
  var WARN_RATIO = 4.5, BLOCK_RATIO = 3;
  // What each color is checked against: the page background + the text that sits on it in a button
  var PAIRS = {
    '--color-brand-primary': { label: 'admin.content.colors.primary', on: '--color-text-on-brand' },
    '--color-brand-accent':  { label: 'admin.content.colors.accent',  on: '--color-text-on-fill' },
  };
  var BG_TOKEN = '--color-surface-page';
  var col = null;   // {overrides, tokens, defaults}

  function tokenValue(name) {
    try { return String(getComputedStyle(document.documentElement).getPropertyValue(name) || '').trim(); }
    catch (e) { return ''; }
  }
  function rgbOf(c) {
    c = String(c || '').trim().toLowerCase();
    var m = /^#([0-9a-f]{6})$/.exec(c);
    if (m) return [0, 2, 4].map(function (i) { return parseInt(m[1].substr(i, 2), 16); });
    m = /^#([0-9a-f]{3})$/.exec(c);
    if (m) return m[1].split('').map(function (h) { return parseInt(h + h, 16); });
    m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(c);
    return m ? [+m[1], +m[2], +m[3]] : null;
  }
  // WCAG 2.x relative luminance + contrast ratio
  function luminance(rgb) {
    var v = rgb.map(function (x) { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  }
  function contrast(a, b) {
    var ra = rgbOf(a), rb = rgbOf(b);
    if (!ra || !rb) return null;
    var la = luminance(ra), lb = luminance(rb);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }
  // → {bg, text, min, level: 'ok' | 'warn' | 'block' | 'unknown'}
  function colorCheck(token, value) {
    var bg = contrast(value, tokenValue(BG_TOKEN)), text = contrast(value, tokenValue(PAIRS[token].on));
    if (bg == null || text == null) return { bg: bg, text: text, min: null, level: 'unknown' };
    var min = Math.min(bg, text);
    return { bg: bg, text: text, min: min, level: min < BLOCK_RATIO ? 'block' : min < WARN_RATIO ? 'warn' : 'ok' };
  }
  function ratio(n) { return n == null ? '—' : (Math.floor(n * 100) / 100).toFixed(2); }

  function colSaved(res) {
    if (res && res.ok && res.data && res.data.data) {
      var o = res.data.data.overrides || {};
      col.overrides = {};
      col.tokens.forEach(function (t) { if (o[t]) col.overrides[t] = o[t]; });
      renderColorsBody();
    }
  }
  // the PUT body: every EDITABLE token with a saved override, with `token` set to `value` (null = left out)
  function colOverridesWith(token, value) {
    var o = {};
    col.tokens.forEach(function (t) { if (col.overrides[t]) o[t] = col.overrides[t]; });
    if (value) o[token] = value.toLowerCase(); else delete o[token];
    return o;
  }
  function colorRow(body, token) {
    var p = PAIRS[token];
    if (!p) return;
    var saved = col.overrides[token] || '', def = col.defaults[token] || '', cur = saved || def;
    var row = el('div', 'ac-item'), head = el('div', 'ac-head');
    row.setAttribute('data-color', token);
    head.appendChild(el('span', 'tw-adm-card-title', twT(p.label)));
    if (saved) head.appendChild(el('span', 'tw-adm-pill is-warn', twT('admin.content.changed')));
    row.appendChild(head);
    row.appendChild(el('p', 'ac-def', twT('admin.content.colors.default', { value: def || '—' })));
    var line = el('div', 'ac-row');
    var pick = el('input', 'ac-pick');
    pick.type = 'color';
    pick.setAttribute('aria-label', twT('admin.content.colors.picker', { name: twT(p.label) }));
    var hex = el('input', 'tw-input ac-hex');
    hex.type = 'text';
    hex.maxLength = 7;
    hex.spellcheck = false;
    hex.setAttribute('aria-label', twT('admin.content.colors.hex', { name: twT(p.label) }));
    hex.value = cur;
    if (HEX.test(cur)) pick.value = cur.toLowerCase();
    line.appendChild(pick);
    line.appendChild(hex);
    var save = btn('tw-btn', 'admin.content.save', function () { onColorSave(token, hex.value); });
    var reset = btn('tw-btn tw-btn-ghost', 'admin.content.reset', function () {
      TwAdminShell.run(ACTIONS['colors.reset'], { name: twT(p.label), value: def,
                                                  overrides: colOverridesWith(token, null) }).then(colSaved);
    });
    reset.disabled = !saved;
    line.appendChild(save);
    line.appendChild(reset);
    row.appendChild(line);
    // live preview — the candidate color on a scoped variable (--pv), nothing applied to the site
    var pv = el('div', 'ac-pv');
    pv.setAttribute('aria-label', twT('admin.content.colors.preview'));
    var pb = el('span', 'ac-pv-btn', twT('admin.content.colors.preview.button'));
    var pl = el('span', 'ac-pv-link', twT('admin.content.colors.preview.link'));
    var pg = el('span', 'ac-pv-badge', twT('admin.content.colors.preview.badge'));
    pv.appendChild(pb); pv.appendChild(pl); pv.appendChild(pg);
    row.appendChild(pv);
    var info = el('p', 'ac-note'), note = el('p', 'ac-warn');
    row.appendChild(info);
    row.appendChild(note);
    function update(v) {
      var valid = HEX.test(v);
      if (pv.style && typeof pv.style.setProperty === 'function') {
        pv.style.setProperty('--pv', valid ? v : 'var(' + token + ')');
        pv.style.setProperty('--pv-on', 'var(' + p.on + ')');
      }
      if (!valid) {
        info.textContent = '';
        note.className = 'ac-block';
        note.textContent = twT('admin.content.colors.invalid');
        save.disabled = true;
        return;
      }
      var c = colorCheck(token, v);
      info.textContent = twT('admin.content.colors.contrast', { bg: ratio(c.bg), text: ratio(c.text) });
      note.className = c.level === 'block' ? 'ac-block' : 'ac-warn';
      note.textContent = c.level === 'block' ? twT('admin.content.colors.block')
        : c.level === 'warn' ? twT('admin.content.colors.warn') : '';
      save.disabled = c.level === 'block';
    }
    pick.addEventListener('input', function () { hex.value = pick.value; update(hex.value); });
    hex.addEventListener('input', function () {
      var v = hex.value.trim();
      if (HEX.test(v)) pick.value = v.toLowerCase();
      update(v);
    });
    update(cur);
    body.appendChild(row);
  }
  function onColorSave(token, value) {
    value = String(value || '').trim().toLowerCase();
    if (!HEX.test(value)) { showToast(twT('admin.content.colors.invalid'), 'error'); return; }
    if (colorCheck(token, value).level === 'block') { showToast(twT('admin.content.colors.block'), 'error'); return; }
    if (value === (col.overrides[token] || col.defaults[token] || '')) { showToast(twT('admin.content.same'), 'info'); return; }
    TwAdminShell.run(ACTIONS['colors.save'], { name: twT(PAIRS[token].label), value: value,
                                               overrides: colOverridesWith(token, value) }).then(colSaved);
  }
  function renderColorsBody() {
    var box = panels.colors;
    box.textContent = '';
    var body = TwAdminShell.card(box, { titleKey: 'admin.content.tab.colors', hintKey: 'admin.content.colors.hint' });
    col.tokens.forEach(function (t) { colorRow(body, t); });
  }
  function renderColors(j) {
    var d = j.data || {};
    col = { tokens: d.tokens || [], defaults: d.defaults || {}, overrides: {} };
    col.tokens.forEach(function (t) { if (d.overrides && d.overrides[t]) col.overrides[t] = d.overrides[t]; });
    renderColorsBody();
  }

  // ══ news ══
  var news = [];
  var STATUSES = ['draft', 'published', 'archived'];
  function whenText(v) { return v ? twFormatDateTime(v) : twT('admin.content.news.no_date'); }
  function newsBody(n, patch) {
    var b = { title: n.title || '', summary: n.summary || '', body: n.body || '', category: n.category || 'general',
              country: n.country || '', source_url: n.source_url || '', status: n.status || 'draft',
              starts_at: n.starts_at || null, ends_at: n.ends_at || null };
    Object.keys(patch || {}).forEach(function (k) { b[k] = patch[k]; });
    return b;
  }
  function newsReload(res) { if (res && res.ok) loadInto(panels.news, '/admin/news', renderNews); return res; }

  function newsForm(n) {
    n = n || {};
    var form = el('div', 'ac-form'), err = el('p', 'ac-err');
    err.setAttribute('role', 'alert');
    function field(key, control) {
      var l = el('label', null, twT(key));
      l.appendChild(control);
      form.appendChild(l);
      return control;
    }
    var title = field('admin.content.news.field.title', el('input', 'tw-input'));
    title.type = 'text';
    title.value = n.title || '';
    var summary = field('admin.content.news.field.summary', el('textarea', 'tw-input'));
    summary.value = n.summary || '';
    var body = field('admin.content.news.field.body', el('textarea', 'tw-input'));
    body.value = n.body || '';
    var url = field('admin.content.news.field.source_url', el('input', 'tw-input'));
    url.type = 'url';
    url.dir = 'ltr';
    url.value = n.source_url || '';
    var status = el('select', 'tw-input ep-select');
    STATUSES.forEach(function (s) { status.appendChild(new Option(twT('admin.content.news.status.' + s), s)); });
    status.value = n.status || 'draft';
    field('admin.content.news.field.status', status);
    function dt(key, v) {
      var f = twDateTimeField({ value: v ? new Date(v) : null });
      var box = el('div', 'ac-f');
      box.appendChild(el('span', null, twT(key)));
      box.appendChild(f.dateRow);
      box.appendChild(f.timeRow);
      form.appendChild(box);
      return f;
    }
    var starts = dt('admin.content.news.field.starts', n.starts_at);
    var ends = dt('admin.content.news.field.ends', n.ends_at);
    form.appendChild(el('p', 'ac-meta', twT('admin.content.news.window_hint')));
    form.appendChild(err);
    // → {body} or {error: twT key}
    function collect() {
      if (!title.value.trim()) return { error: 'admin.content.news.err.title' };
      var link = url.value.trim();
      if (link && !twSafeLinkUrl(link)) return { error: 'admin.content.news.err.url' };
      var s = starts.value(), e = ends.value();
      if ((!s && !starts.empty()) || (!e && !ends.empty())) return { error: 'admin.content.news.err.partial' };
      if (s && e && e <= s) return { error: 'admin.content.news.err.window' };
      // browser-local pick → ISO with time zone (UTC "Z") — the server stores TIMESTAMPTZ
      return { body: newsBody(n, { title: title.value.trim(), summary: summary.value, body: body.value, source_url: link,
                                   status: status.value, starts_at: s ? s.toISOString() : null,
                                   ends_at: e ? e.toISOString() : null }) };
    }
    return { form: form, err: err, collect: collect };
  }
  function openNewsDialog(n) {
    var f = newsForm(n);
    twModal({
      title: twT(n ? 'admin.content.news.edit_title' : 'admin.content.news.new_title'), content: f.form,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT('admin.content.save'), variant: 'primary', onClick: function () {
          var c = f.collect();
          if (c.error) { f.err.textContent = twT(c.error); return false; }
          f.err.textContent = '';
          return TwAdminShell.run(ACTIONS['news.save'], { id: n ? n.id : null, title: c.body.title, body: c.body })
            .then(newsReload).then(function (res) { return !!(res && res.ok); });
        } },
      ],
    });
    if (window.scSelectInit) scSelectInit();   // DS-SEL engine for the status + date / time dropdowns
  }
  function renderNews(j) {
    var box = panels.news;
    news = (j && j.news) || [];
    box.textContent = '';
    var body = TwAdminShell.card(box, { titleKey: 'admin.content.tab.news', hintKey: 'admin.content.news.hint' });
    body.appendChild(btn('tw-btn', 'admin.content.news.add', function () { openNewsDialog(null); }));
    if (!news.length) { body.appendChild(el('p', 'tw-adm-msg', twT('admin.content.news.empty'))); return; }
    var wrap = el('div', 'ac-table-wrap'), table = el('table', 'ac-table'), thead = el('thead'), hr = el('tr');
    ['title', 'status', 'starts', 'ends', 'active', 'actions'].forEach(function (c) {
      var th = el('th', null, twT('admin.content.news.col.' + c));
      th.scope = 'col';
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tb = el('tbody');
    news.forEach(function (n) {
      var tr = el('tr');
      tr.setAttribute('data-news', String(n.id));
      tr.appendChild(el('td', null, n.title || ''));
      tr.appendChild(el('td', null, twT('admin.content.news.status.' + (STATUSES.indexOf(n.status) !== -1 ? n.status : 'draft'))));
      tr.appendChild(el('td', null, whenText(n.starts_at)));
      tr.appendChild(el('td', null, whenText(n.ends_at)));
      var act = el('td');
      act.appendChild(el('span', 'tw-adm-pill' + (n.active_now ? ' is-ok' : ''),
                         twT(n.active_now ? 'admin.content.news.active.yes' : 'admin.content.news.active.no')));
      tr.appendChild(act);
      var acts = el('td'), row = el('div', 'ac-acts');
      row.appendChild(btn('tw-btn tw-btn-ghost', 'admin.content.news.edit', function () { openNewsDialog(n); }));
      if (n.status !== 'archived') {
        row.appendChild(btn('tw-btn tw-btn-ghost', 'admin.content.news.archive', function () {
          TwAdminShell.run(ACTIONS['news.archive'], { id: n.id, title: n.title || '',
                                                      body: newsBody(n, { status: 'archived' }) }).then(newsReload);
        }));
      }
      row.appendChild(btn('tw-btn tw-btn-ghost', 'admin.content.news.delete', function () {
        TwAdminShell.run(ACTIONS['news.delete'], { id: n.id, title: n.title || '' }).then(newsReload);
      }));
      acts.appendChild(row);
      tr.appendChild(acts);
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    wrap.appendChild(table);
    body.appendChild(wrap);
  }

  // ══ tabs ══
  var LOADERS = {
    strings: function () { return loadInto(panels.strings, '/admin/strings', renderStrings); },
    colors:  function () { return loadInto(panels.colors, '/admin/theme/colors', renderColors); },
    news:    function () { return loadInto(panels.news, '/admin/news', renderNews); },
  };
  function show(tab) {
    TABS.forEach(function (t) {
      tabBtns[t].setAttribute('aria-selected', String(t === tab));
      tabBtns[t].tabIndex = t === tab ? 0 : -1;
      panels[t].hidden = t !== tab;
    });
    // «loaded» only after a successful load — a failed one is retried when the tab is opened again;
    // `loading` keeps one request in flight per tab
    if (loaded[tab] || loading[tab]) return loading[tab] || Promise.resolve();
    loading[tab] = LOADERS[tab]().then(function (done) {
      loaded[tab] = done === true;
      loading[tab] = null;
    }, function () { loading[tab] = null; });
    return loading[tab];
  }
  function build() {
    root.textContent = '';
    root.appendChild(el('p', 'tw-adm-hint', twT('admin.content.hint')));
    var list = el('div', 'ac-tabs');
    list.setAttribute('role', 'tablist');
    list.setAttribute('aria-label', twT('admin.content.tabs_label'));
    root.appendChild(list);
    TABS.forEach(function (t, i) {
      var b = btn('tw-btn tw-btn-ghost', 'admin.content.tab.' + t, function () { show(t); });
      b.id = 'ac-tab-' + t;
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-controls', 'ac-panel-' + t);
      b.setAttribute('data-tab', t);
      b.addEventListener('keydown', function (e) {
        var k = e.key, d = k === 'ArrowLeft' ? 1 : k === 'ArrowRight' ? -1 : 0;   // RTL: left = next
        if (!d) return;
        var next = TABS[(i + d + TABS.length) % TABS.length];
        show(next);
        try { tabBtns[next].focus(); } catch (er) {}
      });
      list.appendChild(b);
      tabBtns[t] = b;
      var p = el('div');
      p.id = 'ac-panel-' + t;
      p.setAttribute('role', 'tabpanel');
      p.setAttribute('aria-labelledby', b.id);
      p.setAttribute('data-panel', t);
      root.appendChild(p);
      panels[t] = p;
    });
  }

  // First tab decides access: 403 → one "no permission" message for the whole page (session kept)
  function start() {
    var first = String(location.hash || '').replace('#', '');
    if (TABS.indexOf(first) === -1) first = 'strings';
    getJson('/admin/strings').then(function (j) {
      if (j && j.forbidden) { message(root, FORBIDDEN); return; }
      if (!j) { if (TwAdminSession.hasLiveToken()) message(root, 'admin.content.load_error'); return; }
      build();
      loaded.strings = true;
      renderStrings(j);
      show(first);
    });
  }

  // test hook (node tests/test_admin_shell_runtime.js — I) — read only
  window.TwAdminContent = { ACTIONS: ACTIONS, contrast: contrast, colorCheck: colorCheck, show: show };
  start();
}());
