// static/shared/admin-shell.js — Admin Shell (task 5.3a · docs/rules/admin-shell.md · SYSTEMS_INDEX §25a)
// The ONE header + menu + session gate + confirm/run gate for every admin page.
//   Page loads (after the admin Page Shell scripts): admin-session.js → DS-ICON registry → tw-overlay.js
//   → admin-sections.js (registry) → admin-shell.js → the page script.
//   <header data-tw-header="admin" hidden></header>  (twMountAppChrome skips this variant)
//
//   TwAdminShell.start({loginPage})  → one call first thing in the page script.
//        live admin session → true. None → login page: false (page shows its form) ·
//        any other admin page: location.replace(panel root) and false.
//   TwAdminShell.start({outside, current}) → a page served outside the panel path (admin-view.html, 5.3b):
//        panel root = the one this tab saved (TwAdminSession.panelHref) · menu item `current` marked.
//        No saved root (tab never opened the panel) → false, no navigation (page asks to open the panel).
//   TwAdminShell.mount()             → renders the side menu (desktop) + top bar from TW_ADMIN_SECTIONS:
//        unified search (users · companies · jobs) · system status (/health) · badge shortcuts · logout.
//        Mobile: menu button → openMenu() = the same links in a DS-OVL twModal.
//   TwAdminShell.health()            → cached GET /health (the dashboard's system card reuses it).
//   TwAdminShell.run(action, ctx)    → the ONE way an admin page changes data: confirm (twConfirm,
//        or typed-word confirm for the most dangerous) → TwAdminSession.fetch → toast. No confirm → no request.
//   TwAdminShell.confirm(opts)       → twConfirm, or (opts.typeWord) a twModal whose confirm button
//        stays disabled until that word is typed.
//   TwAdminShell.card(parent, opts)  → card with an ⓘ button that shows one plain sentence.
//   TwAdminShell.me()                → GET /admin/me once (task 8.4c-1) → {kind, name, perms} | null (failed).
//        The menu links / badges / quick icons of sections whose `perm` (registry) the session lacks are hidden
//        (allows() = the JS twin of admin_perms.allows) — UX only: the server checks every route; null → full menu.
//   TwAdminShell.whenAllowed(target, fn, key?) → fn() when the current section (or `key`) is allowed, else
//        `target` hidden + an empty state (admin.perm.denied) — a page never asks for data it may not read.
//   Step-up (task 8.4c-1): TwAdminSession.onStepUp → ONE DS-OVL dialog (authenticator code / «استعمل رمز
//        استرداد») → TwAdminSession.stepUp(code); cancelled → toast admin.stepup.cancelled, the session stays.
//   Session over (401 / 403 / exp — TwAdminSession.onExpired) → registered ONCE here:
//        location.replace(panel root + '?session=expired') → the login page shows admin.session.expired.
// Paths: the panel root is read from location.pathname at runtime — ❌ the slug or its prefix in any
// served file. Text: twT · icons: twIcon · colors: --color-* tokens (admin-shell.css).
(function () {
  'use strict';

  var EXPIRED_PARAM = 'session=expired';
  var BADGE_SOURCES = {
    reports: { url: '/admin/reports',
               count: function (d) { return ((d && d.reports) || []).filter(function (r) { return r.status === 'pending'; }).length; } },
    kyc:     { url: '/admin/kyc',
               count: function (d) { return ((d && d.submissions) || []).filter(function (k) { return k.step === 'review'; }).length; } },
    support: { url: '/admin/support/counts', permissionAware: true,   // status new — task 7.2a · 403 (no support.manage) = no badge, session kept
               count: function (d) { return (d && d.data && d.data.new) || 0; } },
  };

  function sections() { return window.TW_ADMIN_SECTIONS || []; }

  var _outside = false, _outsideKey = '';

  // Panel root = first path segment of the current admin page (runtime only, never in a file).
  // Outside page → the root this tab saved when it opened the panel ('' = unknown).
  function base() {
    if (_outside) return TwAdminSession.panelHref();
    var seg = String(location.pathname || '/').split('/')[1] || '';
    return '/' + seg;
  }
  // Sub page of the panel ('' = root page).
  function page() {
    var rest = String(location.pathname || '/').split('/').slice(2).join('/');
    return rest.replace(/\/+$/, '');
  }

  function hrefFor(s) {
    var p = s.path || '';
    if (!p) return base();
    return p.charAt(0) === '#' ? base() + p : base() + '/' + p;
  }

  function currentKey() {
    if (_outside) return _outsideKey;
    var pg = page(), hash = String(location.hash || '').replace(/^#/, ''), list = sections(), i;
    for (i = 0; i < list.length; i++) {
      var p = list[i].path || '';
      if (pg && p === pg) return list[i].key;
      if (!pg && hash && p === '#' + hash) return list[i].key;
    }
    if (!pg) for (i = 0; i < list.length; i++) if (!list[i].path) return list[i].key;
    return '';
  }

  function ico(name, size) { return typeof window.twIcon === 'function' ? window.twIcon(name, { size: size }) : ''; }

  // ── session perms (GET /admin/me — task 8.4c-1) ──
  var _me = null, _mePromise = null;
  // JS twin of admin_perms.allows: "*" passes everything · an owner-only perm only with "*" · else listed.
  // perms null (unknown / /admin/me failed) → true: the full menu, the server still decides.
  function allows(perms, perm, ownerOnly) {
    if (!perm || !Array.isArray(perms)) return true;
    if (perms.indexOf('*') !== -1) return true;
    if (Array.isArray(ownerOnly) && ownerOnly.indexOf(perm) !== -1) return false;
    return perms.indexOf(perm) !== -1;
  }
  function _perms() { return _me ? _me.perms : null; }
  function _ownerOnly() { return _me ? _me.owner_only : null; }
  function allowedKey(key) {
    var list = sections();
    for (var i = 0; i < list.length; i++) if (list[i].key === key) return allows(_perms(), list[i].perm, _ownerOnly());
    return true;
  }
  function me() {
    if (!_mePromise) {
      _mePromise = TwAdminSession.fetch('/admin/me', { cache: 'no-store', permissionAware: true })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { _me = d && Array.isArray(d.perms) ? d : null; return _me; })
        .catch(function (e) { console.error('[TwAdminShell] me:', e); _me = null; return null; });
    }
    return _mePromise;
  }

  // Menu items from the registry → [{key, href, label, icon, badge}] (pure — tests read it).
  // perms (optional) = an /admin/me perms list (+ ownerOnly) — default the session's; unknown → every item.
  function items(perms, ownerOnly) {
    var p = perms === undefined ? _perms() : perms, oo = perms === undefined ? _ownerOnly() : ownerOnly;
    return sections().filter(function (s) { return allows(p, s.perm, oo); }).map(function (s) {
      return { key: s.key, href: hrefFor(s), label: twT(s.labelKey), icon: s.icon, badge: s.badge || '' };
    });
  }

  function navHtml(current) {
    return items().map(function (it) {
      var on = it.key === current;
      return '<a class="tw-adm-link' + (on ? ' is-current" aria-current="page' : '') + '" href="' + twEscAttr(it.href)
        + '" data-adm-key="' + twEscAttr(it.key) + '">' + ico(it.icon, 'sm') + '<span>' + twEscHtml(it.label) + '</span>'
        + (it.badge ? '<span class="tw-adm-badge" data-adm-badge="' + twEscAttr(it.badge) + '" hidden></span>' : '')
        + '</a>';
    }).join('');
  }

  // Desktop: side menu (brand color) + top bar · mobile: top bar + menu button → the same links in a
  // DS-OVL twModal (openMenu). Top bar: unified search · system status (/health) · badge shortcuts.
  function headerHtml(current) {
    var logo = '<img class="tw-adm-logo" src="/static/33333.svg" alt="' + twEscAttr(twT('brand.name')) + '" width="96" height="26">';
    var quick = sections().filter(function (s) { return s.badge; }).map(function (s) {
      return '<a class="tw-adm-iconbtn" data-adm-quick="' + twEscAttr(s.key) + '" href="' + twEscAttr(hrefFor(s)) + '" aria-label="' + twEscAttr(twT(s.labelKey))
        + '" title="' + twEscAttr(twT(s.labelKey)) + '">' + ico(s.icon, 'sm')
        + '<span class="tw-adm-badge" data-adm-badge="' + twEscAttr(s.badge) + '" hidden></span></a>';
    }).join('');
    return '<aside class="tw-adm-side">'
      + '<div class="tw-adm-brand"><span class="tw-adm-brand-logo">' + logo + '</span>'
      + '<span class="tw-adm-title">' + twEscHtml(twT('admin.shell.title')) + '</span></div>'
      + '<nav class="tw-adm-nav" aria-label="' + twEscAttr(twT('admin.shell.nav')) + '">' + navHtml(current) + '</nav>'
      + '</aside>'
      + '<div class="tw-adm-bar">'
      + '<button type="button" class="tw-adm-iconbtn tw-adm-menu-btn" data-adm-menu aria-label="' + twEscAttr(twT('admin.shell.menu'))
      + '" title="' + twEscAttr(twT('admin.shell.menu')) + '">' + ico('menu', 'sm') + '</button>'
      + '<span class="tw-adm-bar-logo">' + logo + '</span>'
      + '<div class="tw-adm-search" role="search">' + '<span class="tw-adm-search-ico">' + ico('search', 'sm') + '</span>'
      + '<input class="tw-input" type="search" data-adm-search autocomplete="off" aria-autocomplete="list" aria-expanded="false"'
      + ' aria-controls="tw-adm-search-res" aria-label="' + twEscAttr(twT('admin.search.label'))
      + '" placeholder="' + twEscAttr(twT('admin.search.placeholder')) + '">'
      + '<div class="tw-adm-search-res" id="tw-adm-search-res" data-adm-search-res hidden></div></div>'
      + '<span class="tw-adm-health" role="status" data-adm-health><span class="tw-adm-dot"></span>'
      + '<span class="tw-adm-health-text" data-adm-health-text>' + twEscHtml(twT('admin.health.checking')) + '</span></span>'
      + quick
      + '<button type="button" class="tw-act tw-act-secondary tw-adm-logout" data-adm-logout aria-label="'
      + twEscAttr(twT('admin.shell.logout')) + '">' + ico('log-out', 'sm') + '<span>' + twEscHtml(twT('admin.shell.logout')) + '</span></button>'
      + '</div>';
  }

  // ── mobile menu: the same registry links inside a DS-OVL dialog (F33) ──
  function openMenu() {
    var nav = document.createElement('nav');
    nav.className = 'tw-adm-nav tw-adm-drawer-nav';
    nav.setAttribute('aria-label', twT('admin.shell.nav'));
    nav.innerHTML = navHtml(currentKey());
    var h = hdr();
    nav.querySelectorAll('[data-adm-badge]').forEach(function (b) {
      var src = h && h.querySelector('[data-adm-badge="' + b.getAttribute('data-adm-badge') + '"]');
      if (src) { b.textContent = src.textContent; b.hidden = src.hidden; }
    });
    var ctl = twModal({ title: twT('admin.shell.nav'), content: nav,
                        actions: [{ text: twT('common.close'), variant: 'secondary' }] });
    nav.addEventListener('click', function (e) {
      if (e.target && e.target.closest && e.target.closest('a')) ctl.close();
    });
    return ctl;
  }

  // ── unified search: users · companies (GET /admin/users?q= — searched on the server, task 5.3a3) ·
  //    jobs (GET /admin/jobs?q= — every state, searched on the server, task 5.3j) ──
  var SEARCH_MAX = 5, SEARCH_DELAY = 300;
  function _getList(url) {
    return TwAdminSession.fetch(url, { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (d) { return (d && d.data && d.data.items) || []; })
      .catch(function (e) { console.error('[TwAdminShell] search ' + url + ':', e); return []; });
  }
  function loadSearch(q) {
    q = String(q || '').trim();
    if (!q) return Promise.resolve({ users: [], jobs: [] });
    var enc = encodeURIComponent(q);
    return Promise.all([_getList('/admin/users?limit=' + (SEARCH_MAX * 2) + '&q=' + enc),
                        _getList('/admin/jobs?limit=' + SEARCH_MAX + '&q=' + enc)])
      .then(function (r) { return { users: r[0], jobs: r[1] }; });
  }
  function _has(v, q) { return String(v == null ? '' : v).toLowerCase().indexOf(q) !== -1; }
  // Pure (tests read it): data + query → [{key, items:[{title, sub, href, section?, q?}]}] (empty groups dropped)
  function searchResults(data, q) {
    q = String(q || '').trim().toLowerCase();
    if (!q || !data) return [];
    var users = [], cos = [], jobs = [];
    (data.users || []).forEach(function (u) {
      if (!_has(u.full_name, q) && !_has(u.email, q) && !_has(u.tw_id, q)) return;
      var it = { title: u.full_name || u.email || '', sub: u.email || '', href: '/admin-view?id=' + Number(u.id) };
      (u.user_type === 'co' ? cos : users).push(it);
    });
    (data.jobs || []).forEach(function (j) {
      if (!_has(j.title, q) && !_has(j.company_name, q)) return;
      jobs.push({ title: j.title || '', sub: j.company_name || '', href: hrefFor({ path: '#jobs' }), section: 'jobs', q: j.title || '' });
    });
    return [['users', users], ['companies', cos], ['jobs', jobs]]
      .filter(function (g) { return g[1].length; })
      .map(function (g) { return { key: g[0], items: g[1].slice(0, SEARCH_MAX) }; });
  }
  function searchHtml(groups) {
    if (!groups.length) return '<p class="tw-adm-res-empty">' + twEscHtml(twT('admin.search.empty')) + '</p>';
    return groups.map(function (g) {
      return '<div class="tw-adm-res-group"><div class="tw-adm-res-title">' + twEscHtml(twT('admin.nav.' + g.key)) + '</div>'
        + g.items.map(function (it) {
          return '<a class="tw-adm-res-item" href="' + twEscAttr(it.href) + '"'
            + (it.section ? ' data-adm-pick="' + twEscAttr(it.section) + '" data-adm-q="' + twEscAttr(it.q) + '"' : '') + '>'
            + '<span class="tw-adm-res-name">' + twEscHtml(it.title) + '</span>'
            + (it.sub ? '<span class="tw-adm-res-sub">' + twEscHtml(it.sub) + '</span>' : '') + '</a>';
        }).join('') + '</div>';
    }).join('');
  }
  function bindSearch(h) {
    var input = h.querySelector('[data-adm-search]'), box = h.querySelector('[data-adm-search-res]');
    if (!input || !box) return;
    var close = function () { box.hidden = true; input.setAttribute('aria-expanded', 'false'); };
    var render = function () {
      var q = input.value;
      if (!q.trim()) { close(); return; }
      loadSearch(q).then(function (data) {
        if (input.value !== q) return;
        box.innerHTML = searchHtml(searchResults(data, q));
        box.hidden = false;
        input.setAttribute('aria-expanded', 'true');
      });
    };
    var timer = null;
    input.addEventListener('focus', function () { loadSearch(''); });
    // wait until typing stops before asking the server (task 5.3a3)
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(render, SEARCH_DELAY); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Escape') { close(); } });
    box.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('[data-adm-pick]') : null;
      if (a) {
        try {
          document.dispatchEvent(new CustomEvent('tw-adm:pick',
            { detail: { section: a.getAttribute('data-adm-pick'), q: a.getAttribute('data-adm-q') } }));
        } catch (err) { console.error('[TwAdminShell] pick:', err); }
      }
      close();
    });
    document.addEventListener('click', function (e) { if (!h.querySelector('.tw-adm-search').contains(e.target)) close(); });
  }

  // ── system status from /health (db · email · storage · migrations) — shared with the dashboard ──
  var _health = null;
  function health(force) {
    if (!_health || force) {
      _health = TwAdminSession.fetch('/health', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .catch(function (e) { console.error('[TwAdminShell] health:', e); return null; });
    }
    return _health;
  }
  // Pure: /health body → 'ok' | 'degraded' | 'down'
  function healthState(h) {
    if (!h || h.db !== 'ok') return 'down';
    return h.status === 'ok' && h.email === 'configured' && h.storage === 'configured' ? 'ok' : 'degraded';
  }
  function showHealth(h) {
    var el = hdr() && hdr().querySelector('[data-adm-health]');
    if (!el) return;
    var st = healthState(h);
    el.className = 'tw-adm-health is-' + st;
    el.querySelector('[data-adm-health-text]').textContent = twT('admin.health.' + st);
    el.setAttribute('title', twT('admin.health.' + st));
  }

  function hdr() { return document.querySelector('[data-tw-header="admin"]'); }

  function setCurrent(key) {
    var h = hdr();
    if (!h) return;
    h.querySelectorAll('[data-adm-key]').forEach(function (a) {
      var on = a.getAttribute('data-adm-key') === key;
      a.classList.toggle('is-current', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  }

  function setBadge(name, n) {
    var h = hdr();
    if (!h) return;
    h.querySelectorAll('[data-adm-badge="' + name + '"]').forEach(function (b) {
      n = Number(n) || 0;
      b.textContent = n > 99 ? '99+' : String(n);
      b.hidden = n <= 0;
    });
  }

  function refreshBadges() {
    var used = {};
    sections().forEach(function (s) { if (s.badge && BADGE_SOURCES[s.badge] && allowedKey(s.key)) used[s.badge] = 1; });
    return Promise.all(Object.keys(used).map(function (name) {
      var src = BADGE_SOURCES[name];
      return TwAdminSession.fetch(src.url, src.permissionAware ? { permissionAware: true } : undefined).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d) setBadge(name, src.count(d)); })
        .catch(function (e) { console.error('[TwAdminShell] badge ' + name + ':', e); });
    }));
  }

  function logout() {
    TwAdminSession.clear();
    location.replace(base());
  }

  var _mounted = false;
  function mount() {
    var h = hdr();
    if (!h || _mounted) return;
    _mounted = true;
    h.classList.add('tw-adm-hdr');
    h.innerHTML = headerHtml(currentKey());
    h.hidden = false;
    if (document.body && document.body.classList) document.body.classList.add('tw-adm-has-side');
    h.querySelector('[data-adm-logout]').addEventListener('click', logout);
    h.querySelector('[data-adm-menu]').addEventListener('click', openMenu);
    bindSearch(h);
    window.addEventListener('hashchange', function () { setCurrent(currentKey()); });
    me().then(function () { applyPerms(h); refreshBadges(); });
    health().then(showHealth);
  }

  // hide the links / quick icons of sections the session may not open (after /admin/me)
  function applyPerms(h) {
    h.querySelectorAll('[data-adm-key], [data-adm-quick]').forEach(function (a) {
      a.hidden = !allowedKey(a.getAttribute('data-adm-key') || a.getAttribute('data-adm-quick'));
    });
  }

  function whenAllowed(target, fn, key) {
    return me().then(function () {
      document.querySelectorAll('[data-adm-denied]').forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
      if (allowedKey(key || currentKey())) {
        if (typeof fn === 'function') fn();
        return true;
      }
      if (target) {
        var p = document.createElement('p');
        p.className = 'tw-adm-msg';
        p.setAttribute('data-adm-denied', '');
        p.setAttribute('role', 'status');
        p.textContent = twT('admin.perm.denied');
        target.hidden = true;
        if (target.parentNode) target.parentNode.insertBefore(p, target);
      }
      return false;
    });
  }

  // ── step-up dialog (task 8.4c-1) — one at a time; parallel 428s share it ──
  var _stepUp = null;
  function stepUpDialog() {
    if (_stepUp) return _stepUp;
    _stepUp = new Promise(function (resolve) {
      var ok = false, recovery = false;
      var wrap = document.createElement('div');
      wrap.className = 'tw-adm-form-group';
      var label = document.createElement('label');
      label.className = 'tw-adm-form';
      var hint = document.createElement('span');
      hint.className = 'tw-adm-hint';
      var input = document.createElement('input');
      input.className = 'tw-input';
      input.type = 'text';
      var err = document.createElement('span');
      err.className = 'tw-adm-field-err';
      err.setAttribute('role', 'alert');
      err.hidden = true;
      var sw = document.createElement('button');
      sw.type = 'button';
      sw.className = 'tw-act tw-act-secondary';
      label.appendChild(hint);
      label.appendChild(input);
      label.appendChild(err);
      wrap.appendChild(label);
      wrap.appendChild(sw);
      function setErr(t) { err.textContent = t || ''; err.hidden = !t; }
      function mode(rec) {
        recovery = rec;
        input.value = '';
        input.inputMode = rec ? 'text' : 'numeric';
        input.autocomplete = rec ? 'off' : 'one-time-code';
        hint.textContent = twT(rec ? 'admin.login.recovery_hint' : 'admin.login.code_hint');
        input.setAttribute('aria-label', hint.textContent);
        sw.textContent = twT(rec ? 'admin.login.use_app' : 'admin.login.use_recovery');
        setErr('');
      }
      mode(false);
      sw.addEventListener('click', function () { mode(!recovery); });
      input.addEventListener('input', function () { setErr(''); });
      twModal({
        title: twT('admin.stepup.title'), message: twT('admin.stepup.message'), content: wrap,
        actions: [
          { text: twT('common.cancel'), variant: 'secondary' },
          { text: twT('admin.stepup.confirm'), variant: 'primary', onClick: function () {
            var code = String(input.value || '').replace(/\s+/g, '');
            if (!code) { setErr(twT('admin.stepup.empty')); return false; }
            return TwAdminSession.stepUp(code).then(function (res) {
              if (res.ok) {
                ok = true;
                if (res.remaining != null) showToast(twT('admin.login.recovery_left', { n: res.remaining }), 'info');
                return true;
              }
              input.value = '';
              setErr(twT(res.status === 429 ? 'admin.stepup.locked' : 'admin.stepup.wrong'));
              return false;
            });
          } },
        ],
        onClose: function () {
          _stepUp = null;
          if (!ok) showToast(twT('admin.stepup.cancelled'), 'info');
          resolve(ok);
        },
      });
      try { input.focus(); } catch (e) {}
    });
    return _stepUp;
  }
  if (typeof TwAdminSession.onStepUp === 'function') TwAdminSession.onStepUp(stepUpDialog);

  // ── session gate ──
  function goLogin(expired) {
    var b = base();
    if (!b) return;   // outside page in a tab that never opened the panel — the page shows its message
    location.replace(b + (expired ? '?' + EXPIRED_PARAM : ''));
  }
  function wasExpired() { return String(location.search || '').indexOf(EXPIRED_PARAM) !== -1; }

  function start(opts) {
    opts = opts || {};
    if (opts.outside) {
      _outside = true;
      _outsideKey = opts.current || '';
      if (!base()) return false;
      if (TwAdminSession.hasLiveToken()) return true;
      goLogin(false);
      return false;
    }
    try { TwAdminSession.setPanelHref(base()); } catch (e) { console.error('[TwAdminShell] panel href:', e); }
    if (TwAdminSession.hasLiveToken()) return true;
    if (!opts.loginPage) goLogin(false);
    return false;
  }

  TwAdminSession.onExpired(function () { goLogin(true); });

  // ── confirm gate (DS-OVL) ──
  function confirm(opts) {
    opts = opts || {};
    if (!opts.typeWord) {
      return twConfirm({ title: opts.title, message: opts.message, confirmText: opts.confirmText,
                         cancelText: twT('common.cancel'), danger: !!opts.danger });
    }
    return new Promise(function (resolve) {
      var ok = false, word = String(opts.typeWord);
      var wrap = document.createElement('div');
      wrap.className = 'tw-adm-typed';
      var label = document.createElement('label');
      label.className = 'tw-adm-typed-label';
      label.textContent = twT('admin.confirm.type_word', { word: word });
      var input = document.createElement('input');
      input.className = 'tw-input tw-adm-typed-input';
      input.type = 'text';
      input.autocomplete = 'off';
      input.setAttribute('aria-label', label.textContent);
      label.appendChild(input);
      wrap.appendChild(label);
      var matches = function () { return input.value.trim() === word; };
      var ctl = twModal({
        title: opts.title, message: opts.message, content: wrap, dismissible: false,
        actions: [
          { text: twT('common.cancel'), variant: 'secondary' },
          { text: opts.confirmText, variant: 'danger', disabled: true,
            onClick: function () { if (!matches()) return false; ok = true; } },
        ],
        onClose: function () { resolve(ok); },
      });
      input.addEventListener('input', function () { ctl.setActionDisabled(1, !matches()); });
      try { input.focus(); } catch (e) {}
    });
  }

  function _errText(d) {
    if (d && typeof d.error === 'string') return d.error;
    if (d && d.error && typeof d.error.message === 'string') return d.error.message;
    if (d && typeof d.detail === 'string') return d.detail;
    return '';
  }

  // action.errors = {code | 'status': twT key} (task 8.4c-2b-2) → that key's text for an error reply
  //   ({error: {code}} / {error: "code"} first, then the HTTP status) instead of the server text
  function _mapped(action, d, status) {
    var m = action.errors;
    if (!m) return '';
    var code = d && d.error && typeof d.error === 'object' ? d.error.code : (d && typeof d.error === 'string' ? d.error : '');
    return (code && m[code]) || m[String(status)] || '';
  }

  // action = { confirm?: {title, message, confirm, danger?, typeWord?} (twT keys) | fn(ctx) → same,
  //            request: fn(ctx) → {url, method, body?}, done?: twT key, fail?: twT key, as?: 'blob',
  //            ok?: fn(body) → true only when the body proves the change (task 5.3b2),
  //            permissionAware?: true → 403 = "no permission" toast (action.forbidden key), session kept (task 4.2),
  //            errors?: {code | status: twT key} — a fixed message per error code (task 8.4c-2b-2) }
  // → Promise<{ok, status, data} | null>  (null = not confirmed → no request was sent)
  function run(action, ctx) {
    ctx = ctx || {};
    var c = typeof action.confirm === 'function' ? action.confirm(ctx) : action.confirm;
    var gate = c ? confirm({ title: twT(c.title, ctx), message: twT(c.message, ctx), confirmText: twT(c.confirm),
                             danger: !!c.danger, typeWord: c.typeWord ? twT(c.typeWord) : '' })
                 : Promise.resolve(true);
    return gate.then(function (yes) {
      if (!yes) return null;
      var req = action.request(ctx);
      var init = { method: req.method || 'GET', permissionAware: !!action.permissionAware };
      if (req.body !== undefined) init.body = JSON.stringify(req.body);
      return TwAdminSession.fetch(req.url, init).then(function (r) {
        // as: 'blob' (a download — task 5.3a3) → data = the Blob on success; errors stay JSON
        var body = action.as === 'blob' && r.ok ? r.blob() : r.json();
        return body.catch(function () { return {}; }).then(function (d) {
          // action.ok(d) = the body proves the change happened (e.g. a notification id) — 2xx alone is not enough
          var ok = r.ok && (typeof action.ok !== 'function' || !!action.ok(d));
          if (ok) { if (action.done) showToast(twT(action.done), 'success'); }
          else if (r.status === 428) { /* step-up cancelled — the dialog already said so (admin.stepup.cancelled) */ }
          else if (r.status === 403 && action.permissionAware) showToast(twT(action.forbidden || 'admin.action.error'), 'error');
          else if (_mapped(action, d, r.status)) showToast(twT(_mapped(action, d, r.status)), 'error');
          else if (r.status !== 401 && r.status !== 403) showToast(_errText(d) || twT(action.fail || 'admin.action.error'), 'error');
          return { ok: ok, status: r.status, data: d };
        });
      }).catch(function (e) {
        console.error('[TwAdminShell] run:', e);
        showToast(twT(action.fail || 'admin.action.error'), 'error');
        return { ok: false, status: 0, data: null };
      });
    });
  }

  // ── dialog that collects one value (task 5.3j — was admin-view's own) — the send button calls
  //    onSend(value); it usually runs an action whose confirm stacks on top. false / a falsy promise
  //    keeps the dialog open. kind: text | password | textarea | select (options = [[value, labelKey], …]).
  //    o.extra = {labelKey, kind?, hintKey?} — an optional second field (task 8.1 — KYC reject: reason
  //    for the user + internal note) → onSend(value, extraValue, fieldError) ·
  //    fieldError(text) = a server 422 message under the main field ('' clears it — task 8.3) ──
  function formField(o) {
    var form = document.createElement('label'), input;
    form.className = 'tw-adm-form';
    form.textContent = twT(o.labelKey);
    if (o.kind === 'select') {
      input = document.createElement('select');
      input.className = 'tw-input ep-select';
      (o.options || []).forEach(function (op) { input.appendChild(new Option(twT(op[1]), op[0])); });
    } else {
      input = document.createElement(o.kind === 'textarea' ? 'textarea' : 'input');
      input.className = 'tw-input';
      if (o.kind !== 'textarea') input.type = o.kind || 'text';
      input.autocomplete = o.kind === 'password' ? 'new-password' : 'off';
    }
    if (o.value != null) input.value = o.value;
    form.appendChild(input);
    var err = document.createElement('span');
    err.className = 'tw-adm-field-err';
    err.setAttribute('role', 'alert');
    err.hidden = true;
    form.appendChild(err);
    if (o.hintKey) {
      var h = document.createElement('span');
      h.className = 'tw-adm-hint';
      h.textContent = twT(o.hintKey, o.vars);
      form.appendChild(h);
    }
    function setError(text) {
      err.textContent = text || '';
      err.hidden = !text;
      if (text) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
    }
    input.addEventListener('input', function () { setError(''); });
    return { form: form, input: input, setError: setError };
  }
  function formDialog(o) {
    var main = formField(o), extra = o.extra ? formField(o.extra) : null, content = main.form;
    if (extra) {
      content = document.createElement('div');
      content.className = 'tw-adm-form-group';
      content.appendChild(main.form);
      content.appendChild(extra.form);
    }
    return twModal({
      title: twT(o.titleKey, o.vars), content: content,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT(o.sendKey), variant: o.danger ? 'danger' : 'primary',
          onClick: function () { return o.onSend(main.input.value, extra ? extra.input.value : undefined, main.setError); } },
      ],
    });
  }

  // ── card with an ⓘ hint (hidden until asked) ──
  var _cid = 0;
  function card(parent, opts) {
    var c = document.createElement('section'), head = document.createElement('div'), id = 'tw-adm-hint-' + (++_cid);
    c.className = 'tw-adm-card';
    head.className = 'tw-adm-card-hdr';
    if (opts.icon) { var i = document.createElement('span'); i.className = 'tw-adm-card-ico'; i.innerHTML = ico(opts.icon, 'sm'); head.appendChild(i); }
    var h = document.createElement('h2');
    h.className = 'tw-adm-card-title';
    h.textContent = twT(opts.titleKey);
    head.appendChild(h);
    var info = document.createElement('button');
    info.type = 'button';
    info.className = 'tw-adm-info';
    info.setAttribute('aria-label', twT('admin.shell.info'));
    info.setAttribute('title', twT('admin.shell.info'));
    info.setAttribute('aria-expanded', 'false');
    info.setAttribute('aria-controls', id);
    info.innerHTML = ico('info', 'xs');
    head.appendChild(info);
    var hint = document.createElement('p');
    hint.className = 'tw-adm-hint';
    hint.id = id;
    hint.hidden = true;
    hint.textContent = twT(opts.hintKey);
    info.addEventListener('click', function () {
      hint.hidden = !hint.hidden;
      info.setAttribute('aria-expanded', String(!hint.hidden));
    });
    var body = document.createElement('div');
    body.className = 'tw-adm-body';
    c.appendChild(head);
    c.appendChild(hint);
    c.appendChild(body);
    if (parent) parent.appendChild(c);
    return body;
  }

  window.TwAdminShell = {
    base: base, page: page, hrefFor: hrefFor, currentKey: currentKey, items: items, navHtml: navHtml,
    start: start, mount: mount, setCurrent: setCurrent, setBadge: setBadge, refreshBadges: refreshBadges,
    wasExpired: wasExpired, logout: logout, confirm: confirm, run: run, card: card, formDialog: formDialog,
    openMenu: openMenu, searchResults: searchResults, health: health, healthState: healthState,
    me: me, allows: allows, allowedKey: allowedKey, whenAllowed: whenAllowed, stepUpDialog: stepUpDialog,
  };
}());
