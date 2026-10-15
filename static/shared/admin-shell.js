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
//   TwAdminShell.mount()             → renders header + menu from TW_ADMIN_SECTIONS, loads badges.
//   TwAdminShell.run(action, ctx)    → the ONE way an admin page changes data: confirm (twConfirm,
//        or typed-word confirm for the most dangerous) → TwAdminSession.fetch → toast. No confirm → no request.
//   TwAdminShell.confirm(opts)       → twConfirm, or (opts.typeWord) a twModal whose confirm button
//        stays disabled until that word is typed.
//   TwAdminShell.card(parent, opts)  → card with an ⓘ button that shows one plain sentence.
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

  // Menu items from the registry → [{key, href, label, icon, badge}] (pure — tests read it).
  function items() {
    return sections().map(function (s) {
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

  function headerHtml(current) {
    return '<div class="tw-adm-bar">'
      + '<img class="tw-adm-logo" src="/static/33333.svg" alt="' + twEscAttr(twT('brand.name')) + '" width="96" height="26">'
      + '<span class="tw-adm-title">' + twEscHtml(twT('admin.shell.title')) + '</span>'
      + '<button type="button" class="tw-act tw-act-secondary tw-adm-logout" data-adm-logout>'
      + ico('log-out', 'sm') + '<span>' + twEscHtml(twT('admin.shell.logout')) + '</span></button>'
      + '</div>'
      + '<nav class="tw-adm-nav" aria-label="' + twEscAttr(twT('admin.shell.nav')) + '">' + navHtml(current) + '</nav>';
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
    sections().forEach(function (s) { if (s.badge && BADGE_SOURCES[s.badge]) used[s.badge] = 1; });
    return Promise.all(Object.keys(used).map(function (name) {
      var src = BADGE_SOURCES[name];
      return TwAdminSession.fetch(src.url).then(function (r) { return r.ok ? r.json() : null; })
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
    h.querySelector('[data-adm-logout]').addEventListener('click', logout);
    window.addEventListener('hashchange', function () { setCurrent(currentKey()); });
    refreshBadges();
  }

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

  // action = { confirm?: {title, message, confirm, danger?, typeWord?} (twT keys) | fn(ctx) → same,
  //            request: fn(ctx) → {url, method, body?}, done?: twT key, fail?: twT key }
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
      var init = { method: req.method || 'GET' };
      if (req.body !== undefined) init.body = JSON.stringify(req.body);
      return TwAdminSession.fetch(req.url, init).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (r.ok) { if (action.done) showToast(twT(action.done), 'success'); }
          else if (r.status !== 401 && r.status !== 403) showToast(_errText(d) || twT(action.fail || 'admin.action.error'), 'error');
          return { ok: r.ok, status: r.status, data: d };
        });
      }).catch(function (e) {
        console.error('[TwAdminShell] run:', e);
        showToast(twT(action.fail || 'admin.action.error'), 'error');
        return { ok: false, status: 0, data: null };
      });
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
    wasExpired: wasExpired, logout: logout, confirm: confirm, run: run, card: card,
  };
}());
