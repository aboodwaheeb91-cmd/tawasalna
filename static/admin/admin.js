// static/admin/admin.js — admin panel root (admin.html · task 5.3a · docs/rules/admin-shell.md)
//   - session / header / menu / confirm gate = TwAdminShell (static/shared/admin-shell.js)
//   - one section shown at a time, chosen by the menu (#users · #jobs · … → TW_ADMIN_SECTIONS key)
//   - every change goes through TwAdminShell.run(ACTIONS[x], ctx): confirm first (typed word for
//     delete / migrate), then TwAdminSession.fetch. Same endpoints as before (no API change).
//   - text: twT (admin.*) · icons: twIcon · colors: --color-* tokens · dialogs: DS-OVL
(function () {
  'use strict';
  var PAG = 20;
  var S = { users: [], jobs: [], kyc: [], reports: [], usersPage: 1, filter: '', logo: '', built: false, logoLoaded: false };

  // ── actions (the only writes on this page) ──
  var DEL_WORD = 'admin.confirm.word.delete';
  var ACTIONS = {
    'user.verify': {
      confirm: { title: 'admin.verify.title', message: 'admin.verify.message', confirm: 'admin.verify.confirm' },
      request: function (c) { return { url: '/admin/user/' + Number(c.id) + '/verify', method: 'PUT', body: { verified: true } }; },
      done: 'admin.done.verified' },
    'user.delete': {
      confirm: { title: 'admin.delete_user.title', message: 'admin.delete_user.message', confirm: 'admin.delete.confirm',
                 danger: true, typeWord: DEL_WORD },
      request: function (c) { return { url: '/admin/user/' + Number(c.id), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'job.delete': {
      confirm: { title: 'admin.delete_job.title', message: 'admin.delete_job.message', confirm: 'admin.delete.confirm',
                 danger: true, typeWord: DEL_WORD },
      request: function (c) { return { url: '/admin/jobs/' + Number(c.id), method: 'DELETE' }; },
      done: 'admin.done.deleted' },
    'kyc.approve': {
      confirm: { title: 'admin.kyc.approve.title', message: 'admin.kyc.approve.message', confirm: 'admin.kyc.approve.confirm' },
      request: function (c) { return { url: '/admin/kyc/' + Number(c.id) + '/approve', method: 'PUT', body: { note: '' } }; },
      done: 'admin.done.kyc_approved' },
    'kyc.reject': {
      confirm: { title: 'admin.kyc.reject.title', message: 'admin.kyc.reject.message', confirm: 'admin.kyc.reject.confirm', danger: true },
      request: function (c) { return { url: '/admin/kyc/' + Number(c.id) + '/reject', method: 'PUT', body: { note: '' } }; },
      done: 'admin.done.kyc_rejected' },
    'report.resolve': {
      confirm: { title: 'admin.report.resolve.title', message: 'admin.report.resolve.message', confirm: 'admin.report.resolve.confirm' },
      request: function (c) { return { url: '/admin/reports/' + Number(c.id) + '/resolve', method: 'PUT' }; },
      done: 'admin.done.resolved' },
    'logo.upload': {
      confirm: { title: 'admin.logo.confirm.title', message: 'admin.logo.confirm.message', confirm: 'admin.logo.upload' },
      request: function (c) { return { url: '/admin/logo', method: 'POST', body: { filename: 'logo_wide', data_url: c.dataUrl } }; },
      done: 'admin.done.logo' },
    'maintenance.migrate': {
      confirm: { title: 'admin.migrate.title', message: 'admin.migrate.message', confirm: 'admin.migrate.confirm',
                 danger: true, typeWord: 'admin.confirm.word.migrate' },
      request: function () { return { url: '/admin/maintenance/migrate-data-images?dry_run=0', method: 'POST' }; },
      done: 'admin.done.migrated' },
    // read-only dry run — changes nothing, so no confirm
    'maintenance.scan': {
      request: function () { return { url: '/admin/maintenance/migrate-data-images?dry_run=1', method: 'POST' }; },
      done: 'admin.done.scanned' },
    // the message dialog itself is the confirm step (recipient + text shown before «إرسال»)
    'message.send': {
      request: function (c) { return { url: '/admin/message', method: 'POST',
                                       body: { user_id: Number(c.id), subject: twT('admin.msg.subject'), message: c.text } }; },
      done: 'admin.done.sent' },
  };
  window.TwAdminDash = { ACTIONS: ACTIONS };

  function run(name, ctx) { return TwAdminShell.run(ACTIONS[name], ctx); }

  // ── DOM helpers ──
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(variant, icon, labelKey, onClick) {
    var b = el('button', 'tw-act tw-act-' + variant);
    b.type = 'button';
    if (icon) b.appendChild(twIconEl(icon, { size: 'xs' }));
    b.appendChild(el('span', null, twT(labelKey)));
    b.addEventListener('click', onClick);
    return b;
  }
  function msg(parent, key) { parent.textContent = ''; parent.appendChild(el('p', 'tw-adm-msg', twT(key))); }
  function pill(text, mod) { return el('span', 'tw-adm-pill' + (mod ? ' is-' + mod : ''), text); }
  function row(title, sub, extra) {
    var r = el('div', 'tw-adm-row'), main = el('div', 'tw-adm-row-main');
    main.appendChild(el('div', 'tw-adm-row-title', title || '—'));
    (sub || []).forEach(function (s) { if (s) main.appendChild(el('div', 'tw-adm-row-sub', s)); });
    r.appendChild(main);
    if (extra) r.appendChild(extra);
    var acts = el('div', 'tw-adm-row-acts');
    r.appendChild(acts);
    return { row: r, main: main, acts: acts };
  }
  function getJson(url) {
    return TwAdminSession.fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  // ── sections (built once, after login) ──
  var BODY = {};
  function build() {
    if (S.built) return;
    S.built = true;

    var ov = $('sec-overview');
    var b1 = TwAdminShell.card(ov, { titleKey: 'admin.overview.users', hintKey: 'admin.overview.users.hint', icon: 'users' });
    var g1 = el('div', 'tw-adm-stats');
    [['statTotalUsers', 'admin.stat.total', true], ['statEmployees', 'admin.stat.emp'],
     ['statCompanies', 'admin.stat.co'], ['statEdu', 'admin.stat.edu']].forEach(function (s) { g1.appendChild(stat(s[0], s[1], s[2])); });
    b1.appendChild(g1);
    var b2 = TwAdminShell.card(ov, { titleKey: 'admin.overview.activity', hintKey: 'admin.overview.activity.hint', icon: 'activity' });
    var g2 = el('div', 'tw-adm-stats');
    g2.appendChild(stat('statTotalJobs', 'admin.stat.jobs'));
    g2.appendChild(stat('statKYC', 'admin.stat.kyc'));
    b2.appendChild(g2);

    // users: search + type filter + list
    var bu = TwAdminShell.card($('sec-users'), { titleKey: 'admin.users.title', hintKey: 'admin.users.hint', icon: 'users' });
    var search = el('input', 'tw-input');
    search.type = 'search';
    search.id = 'userSearch';
    search.setAttribute('placeholder', twT('admin.users.search'));
    search.setAttribute('aria-label', twT('admin.users.search'));
    search.addEventListener('input', function () { S.usersPage = 1; renderUsers(); });
    bu.appendChild(search);
    var chips = el('div', 'adm-btns');
    chips.setAttribute('role', 'group');
    ['', 'emp', 'co', 'edu'].forEach(function (t) {
      var c = btn('secondary', null, t ? 'admin.user.type.' + t : 'common.all', function () {
        S.filter = t; S.usersPage = 1;
        chips.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
        renderUsers();
      });
      c.setAttribute('aria-pressed', String(!t));
      chips.appendChild(c);
    });
    bu.appendChild(chips);
    BODY.users = el('div');
    bu.appendChild(BODY.users);
    BODY.usersPag = el('div', 'tw-adm-pag');
    bu.appendChild(BODY.usersPag);
    msg(BODY.users, 'common.loading');

    var bj = TwAdminShell.card($('sec-jobs'), { titleKey: 'admin.jobs.title', hintKey: 'admin.jobs.hint', icon: 'briefcase' });
    var js = el('input', 'tw-input');
    js.type = 'search';
    js.setAttribute('placeholder', twT('admin.jobs.search'));
    js.setAttribute('aria-label', twT('admin.jobs.search'));
    js.addEventListener('input', function () { renderJobs(js.value); });
    bj.appendChild(js);
    BODY.jobs = el('div');
    bj.appendChild(BODY.jobs);
    msg(BODY.jobs, 'common.loading');

    BODY.reports = TwAdminShell.card($('sec-reports'), { titleKey: 'admin.reports.title', hintKey: 'admin.reports.hint', icon: 'report' });
    BODY.kyc = TwAdminShell.card($('sec-kyc'), { titleKey: 'admin.kyc.title', hintKey: 'admin.kyc.hint', icon: 'id-card' });
    BODY.errors = TwAdminShell.card($('sec-errors'), { titleKey: 'admin.errors.title', hintKey: 'admin.errors.hint', icon: 'alert' });

    // system: site logo + maintenance (legacy data: images)
    var bl = TwAdminShell.card($('sec-system'), { titleKey: 'admin.logo.title', hintKey: 'admin.logo.hint', icon: 'image' });
    var file = el('input');
    file.type = 'file';
    file.accept = 'image/jpeg,image/png,image/webp';
    file.hidden = true;
    var prev = el('button', 'adm-logo-prev');
    prev.type = 'button';
    prev.id = 'prevWide';
    prev.setAttribute('aria-label', twT('admin.logo.pick'));
    prev.appendChild(twIconEl('upload', { size: 'md' }));
    prev.addEventListener('click', function () { file.click(); });
    file.addEventListener('change', function () { previewLogo(file, prev); });
    bl.appendChild(prev);
    bl.appendChild(file);
    var up = btn('primary', 'upload', 'admin.logo.upload', function () {
      if (!S.logo) { showToast(twT('admin.logo.pick_first'), 'error'); return; }
      up.disabled = true;
      run('logo.upload', { dataUrl: S.logo }).then(function () { up.disabled = false; });
    });
    bl.appendChild(up);

    var bm = TwAdminShell.card($('sec-system'), { titleKey: 'admin.maint.title', hintKey: 'admin.maint.hint', icon: 'wrench' });
    var mb = el('div', 'adm-btns');
    var scan = btn('secondary', 'search', 'admin.maint.scan', function () { migrate('maintenance.scan', scan); });
    var go = btn('danger', 'upload', 'admin.maint.migrate', function () { migrate('maintenance.migrate', go); });
    mb.appendChild(scan);
    mb.appendChild(go);
    bm.appendChild(mb);
    BODY.mig = el('div', 'adm-report');
    BODY.mig.setAttribute('aria-live', 'polite');
    bm.appendChild(BODY.mig);
  }

  function stat(id, labelKey, wide) {
    var s = el('div', 'tw-adm-stat' + (wide ? ' is-wide' : ''));
    var n = el('div', 'tw-adm-stat-num', '—');
    n.id = id;
    s.appendChild(n);
    s.appendChild(el('div', 'tw-adm-stat-lbl', twT(labelKey)));
    return s;
  }
  function setStat(id, n) { var e = $(id); if (e) e.textContent = String(n); }
  function updateStats() {
    setStat('statTotalUsers', S.users.length);
    setStat('statEmployees', S.users.filter(function (u) { return u.user_type === 'emp'; }).length);
    setStat('statCompanies', S.users.filter(function (u) { return u.user_type === 'co'; }).length);
    setStat('statEdu', S.users.filter(function (u) { return u.user_type === 'edu'; }).length);
    setStat('statTotalJobs', S.jobs.length);
    setStat('statKYC', S.kyc.filter(function (k) { return k.step === 'review'; }).length);
  }

  // ── section switching (menu → hash) ──
  var LOADERS = {
    users: function () { renderUsers(); },
    jobs: loadJobs, reports: loadReports, kyc: loadKYC, errors: loadErrors,
    system: function () { if (!S.logoLoaded) loadLogo(); },
  };
  function show() {
    var key = TwAdminShell.currentKey();
    if (!$('sec-' + key)) key = 'overview';
    document.querySelectorAll('[data-adm-section]').forEach(function (s) { s.hidden = s.getAttribute('data-adm-section') !== key; });
    if (LOADERS[key]) LOADERS[key]();
  }

  // ── users ──
  function typeLabel(t) { return twT('admin.user.type.' + (t === 'co' || t === 'edu' ? t : 'emp')); }
  function loadUsers() {
    return getJson('/auth/users').then(function (d) {
      S.users = d.users || [];
      updateStats();
      renderUsers();
    }).catch(function (e) { console.error('[admin] users:', e); msg(BODY.users, 'admin.load_error'); });
  }
  function filteredUsers() {
    var q = (($('userSearch') || {}).value || '').toLowerCase();
    return S.users.filter(function (u) {
      var hit = !q || String(u.full_name || '').toLowerCase().indexOf(q) !== -1 || String(u.email || '').toLowerCase().indexOf(q) !== -1;
      return hit && (!S.filter || u.user_type === S.filter);
    });
  }
  function renderUsers() {
    var list = filteredUsers(), box = BODY.users;
    box.textContent = '';
    BODY.usersPag.textContent = '';
    if (!list.length) { msg(box, 'admin.users.empty'); return; }
    list.slice((S.usersPage - 1) * PAG, S.usersPage * PAG).forEach(function (u) {
      var id = Number(u.id), name = u.full_name || twT('admin.user.unnamed');
      var t = u.user_type === 'co' || u.user_type === 'edu' ? u.user_type : '';
      var r = row(u.full_name, [u.email], pill(typeLabel(u.user_type), t));
      r.main.classList.add('is-link');
      r.main.setAttribute('role', 'link');
      r.main.setAttribute('tabindex', '0');
      var open = function () { location.href = '/admin-view?id=' + id; };
      r.main.addEventListener('click', open);
      r.main.addEventListener('keydown', function (e) { if (e.key === 'Enter') open(); });
      r.acts.appendChild(btn('secondary', 'mail', 'admin.users.message', function () { openMsg(id, name); }));
      r.acts.appendChild(btn('primary', 'verified', 'admin.users.verify', function () {
        run('user.verify', { id: id }).then(function (res) { if (res && res.ok) loadUsers(); });
      }));
      r.acts.appendChild(btn('danger', 'delete', 'admin.users.delete', function () {
        run('user.delete', { id: id }).then(function (res) { if (res && res.ok) loadUsers(); });
      }));
      box.appendChild(r.row);
    });
    var pages = Math.ceil(list.length / PAG);
    if (pages > 1) for (var i = 1; i <= pages; i++) (function (p) {
      var b = el('button', 'tw-act tw-act-secondary' + (p === S.usersPage ? ' is-current' : ''), String(p));
      b.type = 'button';
      if (p === S.usersPage) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', function () { S.usersPage = p; renderUsers(); });
      BODY.usersPag.appendChild(b);
    })(i);
  }

  // ── jobs ──
  function loadStatsJobs() {
    return TwAdminSession.fetch('/jobs').then(function (r) { return r.ok ? r.json() : { jobs: [] }; })
      .then(function (d) { if (!S.jobsLoaded) S.jobs = d.jobs || []; updateStats(); })
      .catch(function (e) { console.error('[admin] jobs stats:', e); });
  }
  function loadJobs() {
    return getJson('/admin/jobs').then(function (d) {
      S.jobs = d.jobs || [];
      S.jobsLoaded = true;
      updateStats();
      renderJobs('');
    }).catch(function (e) { console.error('[admin] jobs:', e); msg(BODY.jobs, 'admin.load_error'); });
  }
  function renderJobs(q) {
    q = String(q || '').toLowerCase();
    var list = S.jobs.filter(function (j) {
      return !q || String(j.title || '').toLowerCase().indexOf(q) !== -1 || String(j.company_name || '').toLowerCase().indexOf(q) !== -1;
    });
    BODY.jobs.textContent = '';
    if (!list.length) { msg(BODY.jobs, 'admin.jobs.empty'); return; }
    list.forEach(function (j) {
      var active = j.status === 'active';
      var r = row(j.title, [j.company_name], pill(twT(active ? 'admin.jobs.active' : 'admin.jobs.paused'), active ? 'ok' : 'warn'));
      r.acts.appendChild(btn('danger', 'delete', 'admin.jobs.delete', function () {
        run('job.delete', { id: j.id }).then(function (res) { if (res && res.ok) loadJobs(); });
      }));
      BODY.jobs.appendChild(r.row);
    });
  }

  // ── reports ──
  function loadReports() {
    msg(BODY.reports, 'common.loading');
    return getJson('/admin/reports').then(function (d) {
      S.reports = d.reports || [];
      TwAdminShell.refreshBadges();
      BODY.reports.textContent = '';
      if (!S.reports.length) { msg(BODY.reports, 'admin.reports.empty'); return; }
      S.reports.forEach(function (rep) {
        var pending = rep.status === 'pending';
        var r = row(rep.reported_name || twT('admin.reports.unknown'), [
          (rep.report_type || twT('admin.reports.default_type')) + (rep.created_at ? ' · ' + twFormatDate(rep.created_at) : ''),
          rep.reason || '—',
          twT('admin.reports.from', { name: rep.reporter_name || twT('admin.reports.unknown') }),
        ], pill(twT(pending ? 'admin.reports.new' : 'admin.reports.resolved'), pending ? 'danger' : 'ok'));
        var href = rep.target_url ? (twSafeNext(rep.target_url) || twSafeLinkUrl(rep.target_url)) : '';
        if (href) {
          var a = el('a', 'tw-act tw-act-secondary');
          a.href = href;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.appendChild(twIconEl('eye', { size: 'xs' }));
          a.appendChild(el('span', null, twT('admin.reports.view')));
          r.acts.appendChild(a);
        }
        if (rep.reported_id) r.acts.appendChild(btn('danger', 'delete', 'admin.reports.delete_user', function () {
          run('user.delete', { id: rep.reported_id }).then(function (res) { if (res && res.ok) loadReports(); });
        }));
        if (pending) r.acts.appendChild(btn('primary', 'check', 'admin.reports.resolve', function () {
          run('report.resolve', { id: rep.id }).then(function (res) { if (res && res.ok) loadReports(); });
        }));
        BODY.reports.appendChild(r.row);
      });
    }).catch(function (e) { console.error('[admin] reports:', e); msg(BODY.reports, 'admin.load_error'); });
  }

  // ── KYC ──
  function loadKYC() {
    return getJson('/admin/kyc').then(function (d) {
      S.kyc = d.submissions || [];
      updateStats();
      renderKYC();
    }).catch(function (e) { console.error('[admin] kyc:', e); if (BODY.kyc) msg(BODY.kyc, 'admin.load_error'); });
  }
  function kycStatus(step) {
    if (step === 'review') return [twT('admin.kyc.status.review'), 'warn'];
    if (step === 'approved') return [twT('admin.kyc.status.approved'), 'ok'];
    if (step === 'rejected') return [twT('admin.kyc.status.rejected'), 'danger'];
    return [twT('admin.kyc.status.other', { step: step || '—' }), ''];
  }
  function kycAct(name, uid) {
    return run(name, { id: uid }).then(function (res) {
      if (res && res.ok) { loadKYC(); TwAdminShell.refreshBadges(); }
    });
  }
  function renderKYC() {
    var box = BODY.kyc;
    if (!box) return;
    box.textContent = '';
    if (!S.kyc.length) { msg(box, 'admin.kyc.empty'); return; }
    S.kyc.forEach(function (k) {
      var st = kycStatus(k.step), uid = Number(k.user_id);
      var r = row(k.full_name, [k.email], pill(st[0], st[1]));
      r.acts.appendChild(btn('secondary', 'id-card', 'admin.kyc.docs', function () { openKYCDocs(Number(k.id), uid); }));
      r.acts.appendChild(btn('primary', 'check', 'admin.kyc.approve', function () { kycAct('kyc.approve', uid); }));
      r.acts.appendChild(btn('danger', 'close', 'admin.kyc.reject', function () { kycAct('kyc.reject', uid); }));
      box.appendChild(r.row);
    });
  }
  // documents — GET /admin/kyc/{id}/docs → short-lived signed URLs (PR-7c), never cached
  function docCell(titleKey, doc, prefix) {
    var c = el('div', 'adm-doc');
    c.appendChild(el('div', 'adm-doc-title', twT(titleKey)));
    var url = doc && doc.url;
    if (typeof url === 'string' && /^https:\/\//.test(prefix) && url.indexOf(prefix) === 0) {
      var a = el('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      var img = el('img');
      img.src = url;
      img.referrerPolicy = 'no-referrer';
      img.alt = twT(titleKey);
      a.appendChild(img);
      c.appendChild(a);
    } else {
      var reason = doc && doc.reason;
      var known = ['missing', 'legacy_data_url', 'legacy_url', 'invalid_path', 'sign_failed', 'storage_unavailable'];
      c.appendChild(el('p', 'tw-adm-msg', twT(known.indexOf(reason) !== -1 ? 'admin.kyc.doc.' + reason : 'admin.kyc.doc.unavailable')));
    }
    return c;
  }
  function openKYCDocs(subId, uid) {
    var grid = el('div', 'adm-docs');
    grid.appendChild(el('p', 'tw-adm-msg', twT('common.loading')));
    var later = function (name) { return function () { setTimeout(function () { kycAct(name, uid); }, 0); }; };
    twModal({
      title: twT('admin.kyc.docs_title'), content: grid,
      actions: [
        { text: twT('admin.kyc.approve'), variant: 'primary', onClick: later('kyc.approve') },
        { text: twT('admin.kyc.reject'), variant: 'danger', onClick: later('kyc.reject') },
        { text: twT('common.close'), variant: 'secondary' },
      ],
      onClose: function () { grid.textContent = ''; },
    });
    getJson('/admin/kyc/' + Number(subId) + '/docs').then(function (d) {
      var prefix = (d.storage_base || '') + '/storage/v1/object/sign/kyc-docs/', docs = d.docs || {};
      grid.textContent = '';
      grid.appendChild(docCell('admin.kyc.doc.id', docs.id_front, prefix));
      grid.appendChild(docCell('admin.kyc.doc.selfie', docs.selfie, prefix));
    }).catch(function () { grid.textContent = ''; grid.appendChild(el('p', 'tw-adm-msg', twT('admin.kyc.docs_error'))); });
  }

  // ── errors ──
  function loadErrors() {
    msg(BODY.errors, 'common.loading');
    return getJson('/admin/errors').then(function (d) {
      var list = d.errors || [];
      BODY.errors.textContent = '';
      if (!list.length) { msg(BODY.errors, 'admin.errors.empty'); return; }
      BODY.errors.appendChild(el('p', 'tw-adm-hint', twT('admin.errors.count', { n: Number(d.count || 0) })));
      list.forEach(function (e) {
        var r = row(e.msg, [String(e.page || '') + (e.line ? ' · ' + twT('admin.errors.line', { n: Number(e.line) }) : '')],
                    el('span', 'adm-err-type', e.type || ''));
        BODY.errors.appendChild(r.row);
      });
    }).catch(function (e) { console.error('[admin] errors:', e); msg(BODY.errors, 'admin.load_error'); });
  }

  // ── logo ──
  function setLogoPreview(prev, url) {
    prev.textContent = '';
    var img = el('img');
    img.src = url;
    img.alt = '';
    prev.appendChild(img);
  }
  function loadLogo() {
    S.logoLoaded = true;
    getJson('/admin/logo').then(function (d) {
      var logo = twSafeImageUrl(d.logo_wide);
      if (logo && !S.logo) setLogoPreview($('prevWide'), logo);
    }).catch(function (e) { console.error('[admin] logo:', e); });
  }
  function previewLogo(input, prev) {
    if (!input.files || !input.files[0]) return;
    var reader = new FileReader();
    reader.onload = function (e) { S.logo = String(e.target.result || ''); setLogoPreview(prev, S.logo); };
    reader.readAsDataURL(input.files[0]);
  }

  // ── maintenance: migrate legacy data: images (PR-7c) ──
  var MIG_COLS = { 'profiles.avatar_url': 'avatar', 'profiles.cover_url': 'emp_cover', 'company_profiles.cover_url': 'co_cover',
                   'kyc_submissions.id_front_url': 'kyc_id', 'kyc_submissions.selfie_url': 'kyc_selfie', 'site_settings.logo': 'logo' };
  function renderMig(d) {
    var rep = (d && d.report) || {};
    BODY.mig.textContent = '';
    if (d.dry_run) BODY.mig.appendChild(el('div', 'tw-adm-hint', twT('admin.maint.dry_note')));
    Object.keys(rep).forEach(function (c) {
      var v = rep[c] || {}, reasons = v.reasons || {};
      var rs = Object.keys(reasons).map(function (k) { return k + ': ' + Number(reasons[k]); }).join(' · ');
      BODY.mig.appendChild(el('div', null, twT(d.dry_run ? 'admin.maint.line_dry' : 'admin.maint.line_done', {
        col: MIG_COLS[c] ? twT('admin.maint.col.' + MIG_COLS[c]) : c, found: Number(v.found || 0),
        n: Number(d.dry_run ? v.would_migrate || 0 : v.migrated || 0), skipped: Number(v.skipped || 0),
      }) + (rs ? ' (' + rs + ')' : '')));
    });
  }
  function migrate(name, b) {
    b.disabled = true;
    run(name).then(function (res) {
      b.disabled = false;
      if (res && res.ok) renderMig(res.data || {});
    });
  }

  // ── message dialog ──
  var TEMPLATES = ['welcome', 'verify', 'warning', 'interview'];
  function openMsg(id, name) {
    var form = el('div', 'adm-msg-form');
    var to = el('label', 'adm-field');
    to.appendChild(el('span', null, twT('admin.msg.to')));
    var toIn = el('input', 'tw-input');
    toIn.readOnly = true;
    toIn.value = name;
    to.appendChild(toIn);
    form.appendChild(to);
    var tl = el('div', 'adm-field');
    tl.appendChild(el('span', null, twT('admin.msg.templates')));
    var tb = el('div', 'adm-btns');
    var ta = el('textarea', 'tw-input');
    ta.setAttribute('aria-label', twT('admin.msg.body'));
    ta.setAttribute('placeholder', twT('admin.msg.body'));
    TEMPLATES.forEach(function (t) {
      tb.appendChild(btn('secondary', null, 'admin.msg.tpl.' + t, function () { ta.value = twT('admin.msg.tpl.' + t + '.text'); }));
    });
    tl.appendChild(tb);
    form.appendChild(tl);
    form.appendChild(ta);
    twModal({
      title: twT('admin.msg.title'), content: form,
      actions: [
        { text: twT('common.cancel'), variant: 'secondary' },
        { text: twT('admin.msg.send'), variant: 'primary', onClick: function () {
            var text = ta.value.trim();
            if (!text) { showToast(twT('admin.msg.empty'), 'error'); return false; }
            return run('message.send', { id: id, text: text }).then(function (res) { return !!(res && res.ok); });
          } },
      ],
    });
  }

  // ── login / enter ──
  function enter() {
    $('loginWrap').hidden = true;
    $('main-content').hidden = false;
    TwAdminShell.mount();
    build();
    window.addEventListener('hashchange', show);
    show();
    loadUsers();
    loadStatsJobs();
    loadKYC();
  }
  function showLogin(expired) {
    $('main-content').hidden = true;
    $('loginWrap').hidden = false;
    if (expired) {
      $('loginErr').textContent = twT('admin.session.expired');
      try { history.replaceState(null, '', TwAdminShell.base() + location.hash); } catch (e) {}
    }
    $('admin-pass').focus();
  }
  function login(e) {
    e.preventDefault();
    var pass = $('admin-pass').value, b = $('loginBtn'), err = $('loginErr');
    if (!pass) return;
    b.disabled = true;
    err.textContent = '';
    // No admin session yet → shared client without user auth (a 401 here = wrong password, not expiry).
    twApi(TwAdminShell.base() + '/login', { method: 'POST', auth: false, body: { password: pass } }).then(function (r) {
      b.disabled = false;
      var token = r.ok && r.data && r.data.token;
      if (token) {
        TwAdminSession.setToken(token);
        $('admin-pass').value = '';
        enter();
        return;
      }
      err.textContent = twT(r.status === 401 ? 'admin.login.wrong' : r.status === 429 ? 'admin.login.rate' : 'admin.login.error');
    });
  }

  function boot() {
    document.title = twT('page.title', { page: twT('admin.shell.title') });
    var logo = document.querySelector('.adm-login-logo');
    if (logo) logo.alt = twT('brand.name');
    $('loginForm').addEventListener('submit', login);
    if (TwAdminShell.start({ loginPage: true })) enter();
    else showLogin(TwAdminShell.wasExpired());
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}());
