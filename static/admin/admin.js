// static/admin/admin.js — admin panel root (admin.html · task 5.3a · docs/rules/admin-shell.md)
//   - session / header / menu / confirm gate = TwAdminShell (static/shared/admin-shell.js)
//   - one section shown at a time, chosen by the menu (#users · #jobs · … → TW_ADMIN_SECTIONS key)
//   - overview = dashboard (task 5.3a2): cards (GET /admin/stats/summary) · 30-day charts (GET /admin/stats/timeseries,
//     drawn by twChart) · review queues · live activity (GET /admin/activity) · system (/health) · recent audit
//   - companies = the users view with a fixed type filter · audit = GET /admin/audit (read only)
//   - every change goes through TwAdminShell.run(ACTIONS[x], ctx): confirm first (typed word for
//     delete / migrate), then TwAdminSession.fetch. Same endpoints as before (no API change).
//   - text: twT (admin.*) · icons: twIcon · colors: --color-* tokens · dialogs: DS-OVL
(function () {
  'use strict';
  var PAG = 20;
  var S = { users: null, jobs: [], kyc: [], reports: [], logo: '', built: false, logoLoaded: false, auditPage: 1, auditAction: '' };
  // users table views — 'companies' = the same view with a fixed type filter (task 5.3a2, no 2nd table code)
  var VIEWS = { users: { fixed: '', filter: '', page: 1 }, companies: { fixed: 'co', filter: 'co', page: 1 } };

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

    buildOverview($('sec-overview'));
    buildUsersView('users', $('sec-users'), 'admin.users.title', 'admin.users.hint', 'users');
    buildUsersView('companies', $('sec-companies'), 'admin.companies.title', 'admin.companies.hint', 'building-2');
    buildAudit($('sec-audit'));

    var bj = TwAdminShell.card($('sec-jobs'), { titleKey: 'admin.jobs.title', hintKey: 'admin.jobs.hint', icon: 'briefcase' });
    var js = el('input', 'tw-input');
    js.type = 'search';
    js.id = 'jobSearch';
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

  // ── overview = dashboard (task 5.3a2) — real data only: no card without a source ──
  // [summary key, DS-ICON, twT base (… + '.hint'), section key the card opens]
  var KPIS = [
    ['users', 'users', 'admin.kpi.users', 'users'],
    ['verified_companies', 'badge-check', 'admin.kpi.verified_companies', 'companies'],
    ['active_jobs', 'briefcase', 'admin.kpi.active_jobs', 'jobs'],
    ['applications', 'file-text', 'admin.kpi.applications', ''],
    ['open_reports', 'report', 'admin.kpi.open_reports', 'reports'],
    ['pending_kyc', 'id-card', 'admin.kpi.pending_kyc', 'kyc'],
    ['messages_today', 'messages-square', 'admin.kpi.messages_today', ''],
    ['emails_today', 'mail', 'admin.kpi.emails_today', 'email'],
  ];
  // [metric (GET /admin/stats/timeseries allowlist), chart type, twT base, icon]
  var CHARTS = [
    ['users', 'line', 'admin.chart.users', 'trending-up'],
    ['jobs', 'bar', 'admin.chart.jobs', 'briefcase'],
    ['applications', 'line', 'admin.chart.applications', 'file-text'],
  ];
  var DAYS = 30, QUEUE_MAX = 5, OV = {};
  function sectionHref(key) {
    var s = (window.TW_ADMIN_SECTIONS || []).filter(function (x) { return x.key === key; })[0];
    return s ? TwAdminShell.hrefFor(s) : '';
  }
  function moreLink(parent, key) {
    var a = el('a', 'adm-more', twT('admin.dash.view_all'));
    a.href = sectionHref(key);
    parent.appendChild(a);
  }
  function buildOverview(ov) {
    var kpis = el('div', 'adm-kpis');
    ov.appendChild(kpis);
    OV.kpi = {};
    KPIS.forEach(function (k) {
      var body = TwAdminShell.card(kpis, { titleKey: k[2], hintKey: k[2] + '.hint', icon: k[1] });
      body.parentNode.classList.add('is-kpi');
      var val = el('div', 'adm-kpi-val', '—'), chg = el('div', 'adm-kpi-chg');
      body.appendChild(val);
      body.appendChild(chg);
      if (k[3]) moreLink(body, k[3]);
      OV.kpi[k[0]] = { val: val, chg: chg };
    });
    var dash = el('div', 'adm-dash'), mainCol = el('div', 'adm-col'), side = el('div', 'adm-col');
    dash.appendChild(mainCol);
    dash.appendChild(side);
    ov.appendChild(dash);
    var charts = el('div', 'adm-charts');
    mainCol.appendChild(charts);
    OV.chart = {};
    CHARTS.forEach(function (c) {
      var body = TwAdminShell.card(charts, { titleKey: c[2], hintKey: c[2] + '.hint', icon: c[3] });
      var sum = el('div', 'adm-chart-sum'), box = el('div', 'adm-chart-box');
      body.appendChild(sum);
      body.appendChild(box);
      msg(box, 'common.loading');
      OV.chart[c[0]] = { sum: sum, box: box, type: c[1], title: c[2] };
    });
    var queues = el('div', 'adm-queues');
    mainCol.appendChild(queues);
    OV.qKyc = TwAdminShell.card(queues, { titleKey: 'admin.queue.kyc', hintKey: 'admin.queue.kyc.hint', icon: 'id-card' });
    OV.qRep = TwAdminShell.card(queues, { titleKey: 'admin.queue.reports', hintKey: 'admin.queue.reports.hint', icon: 'report' });
    OV.activity = TwAdminShell.card(side, { titleKey: 'admin.activity.title', hintKey: 'admin.activity.hint', icon: 'activity' });
    OV.system = TwAdminShell.card(side, { titleKey: 'admin.system.title', hintKey: 'admin.system.hint', icon: 'server' });
    OV.audit = TwAdminShell.card(side, { titleKey: 'admin.audit.recent', hintKey: 'admin.audit.recent.hint', icon: 'shield' });
  }
  function apiData(url) {   // new admin endpoints answer {ok, data}
    return getJson(url).then(function (d) { return d && d.data; });
  }
  function renderKpis(sum) {
    KPIS.forEach(function (k) {
      var c = sum[k[0]] || {}, ui = OV.kpi[k[0]];
      ui.val.textContent = String(Number(c.value) || 0);
      ui.chg.textContent = '';
      ui.chg.className = 'adm-kpi-chg';
      if (c.change === null || c.change === undefined || !c.period) return;
      var n = Number(c.change);
      ui.chg.classList.add(n > 0 ? 'is-up' : n < 0 ? 'is-down' : 'is-flat');
      ui.chg.textContent = twT('admin.kpi.change.' + (c.period === 'day' ? 'day' : 'month'), { n: (n > 0 ? '+' : '') + n + '%' });
    });
  }
  function renderChart(metric, d) {
    var c = OV.chart[metric];
    c.sum.textContent = twT('admin.chart.sum', { n: Number(d.in_range) || 0, days: DAYS, total: Number(d.total) || 0 });
    twChart(c.box, { type: c.type, title: twT(c.title),
                     points: (d.points || []).map(function (p) { return { label: twFormatDate(p.date), value: p.count }; }) });
  }
  function queueRow(parent, title, sub, sectionKey) {
    var r = row(title, sub);
    var a = el('a', 'tw-act tw-act-secondary');
    a.href = sectionHref(sectionKey);
    a.appendChild(twIconEl('eye', { size: 'xs' }));
    a.appendChild(el('span', null, twT('admin.dash.review')));
    r.acts.appendChild(a);
    parent.appendChild(r.row);
  }
  function renderQueues() {
    var k = S.kyc.filter(function (x) { return x.step === 'review'; });
    OV.qKyc.textContent = '';
    if (!k.length) msg(OV.qKyc, 'admin.queue.kyc.empty');
    k.slice(0, QUEUE_MAX).forEach(function (x) {
      queueRow(OV.qKyc, x.full_name, [typeLabel(x.user_type) + (x.submitted_at ? ' · ' + twFormatDate(x.submitted_at) : '')], 'kyc');
    });
    if (k.length) moreLink(OV.qKyc, 'kyc');
    var r = S.reports.filter(function (x) { return x.status === 'pending'; });
    OV.qRep.textContent = '';
    if (!r.length) msg(OV.qRep, 'admin.queue.reports.empty');
    r.slice(0, QUEUE_MAX).forEach(function (x) {
      queueRow(OV.qRep, x.reported_name || twT('admin.reports.unknown'),
               [(x.report_type || twT('admin.reports.default_type')) + (x.created_at ? ' · ' + twFormatDate(x.created_at) : '')], 'reports');
    });
    if (r.length) moreLink(OV.qRep, 'reports');
  }
  var ACT_SECTION = { job: 'jobs', kyc: 'kyc', report: 'reports' };
  function renderActivity(list) {
    var box = OV.activity;
    box.textContent = '';
    if (!list.length) { msg(box, 'admin.activity.empty'); return; }
    list.forEach(function (a) {
      var kind = (ACT_SECTION[a.kind] || a.kind === 'register') ? a.kind : 'register';
      var sub = kind === 'job' || kind === 'report' ? (a.sub || '') : typeLabel(a.sub);
      var it = el('a', 'adm-act');
      it.href = a.kind === 'register' ? '/admin-view?id=' + Number(a.ref) : sectionHref(ACT_SECTION[a.kind]);
      it.appendChild(el('span', 'adm-act-ico')).appendChild(twIconEl(
        { register: 'user-plus', job: 'briefcase', kyc: 'id-card', report: 'report' }[kind], { size: 'sm' }));
      var txt = el('span', 'adm-act-txt');
      txt.appendChild(el('span', 'adm-act-title', twT('admin.activity.' + kind, { name: a.title || '—' })));
      txt.appendChild(el('span', 'adm-act-sub', [sub, a.at ? twFormatDateTime(a.at) : ''].filter(Boolean).join(' · ')));
      it.appendChild(txt);
      box.appendChild(it);
    });
  }
  function sysRow(box, labelKey, ok, textKey) {
    var r = el('div', 'adm-sys');
    r.appendChild(el('span', 'adm-sys-lbl', twT(labelKey)));
    r.appendChild(pill(twT(textKey), ok ? 'ok' : 'danger'));
    box.appendChild(r);
  }
  function renderSystem(h) {
    var box = OV.system;
    box.textContent = '';
    if (!h) { msg(box, 'admin.health.down'); return; }
    var mig = h.migrations || {}, names = Object.keys(mig), bad = names.filter(function (n) { return mig[n] !== 'ok'; });
    sysRow(box, 'admin.system.db', h.db === 'ok', h.db === 'ok' ? 'admin.system.ok' : 'admin.system.error');
    sysRow(box, 'admin.system.email', h.email === 'configured', h.email === 'configured' ? 'admin.system.configured' : 'admin.system.missing');
    sysRow(box, 'admin.system.storage', h.storage === 'configured', h.storage === 'configured' ? 'admin.system.configured' : 'admin.system.missing');
    var r = el('div', 'adm-sys');
    r.appendChild(el('span', 'adm-sys-lbl', twT('admin.system.migrations')));
    r.appendChild(pill(bad.length ? twT('admin.system.migrations_failed', { n: bad.length }) : twT('admin.system.migrations_ok', { n: names.length }),
                       bad.length ? 'danger' : 'ok'));
    box.appendChild(r);
    if (bad.length) box.appendChild(el('p', 'tw-adm-hint', bad.join(' · ')));
  }
  var AUDIT_LABELS = ['admin_login', 'delete_user', 'verify_user', 'change_user_type', 'admin_reset_password', 'admin_update_profile',
                      'admin_delete_job', 'admin_kyc_approve', 'admin_kyc_reject', 'resolve_report', 'upload_logo',
                      'admin_migrate_data_images', 'admin_send_message', 'admin_put_email', 'admin_test_email'];
  function auditLabel(a) { return AUDIT_LABELS.indexOf(a) !== -1 ? twT('admin.audit.action.' + a) : String(a || '—'); }
  var RESULT_MOD = { ok: 'ok', denied: 'danger', failed: 'warn' };
  function auditRows(box, items) {
    items.forEach(function (it) {
      var r = row(auditLabel(it.action), [
        [it.created_at ? twFormatDateTime(it.created_at) : '', it.target || '', it.ip ? twT('admin.audit.ip', { ip: it.ip }) : '']
          .filter(Boolean).join(' · '),
        twT('admin.audit.actor', { actor: it.actor || '—' }),
      ], pill(twT('admin.audit.result.' + (RESULT_MOD[it.result] ? it.result : 'failed')), RESULT_MOD[it.result] || 'warn'));
      box.appendChild(r.row);
    });
  }
  function renderRecentAudit(d) {
    OV.audit.textContent = '';
    if (!d.items.length) { msg(OV.audit, 'admin.audit.empty'); return; }
    auditRows(OV.audit, d.items);
    moreLink(OV.audit, 'audit');
  }
  function failBox(box) { return function (e) { console.error('[admin] overview:', e); msg(box, 'admin.load_error'); }; }
  function loadOverview() {
    apiData('/admin/stats/summary').then(renderKpis).catch(function (e) { console.error('[admin] summary:', e); });
    CHARTS.forEach(function (c) {
      apiData('/admin/stats/timeseries?metric=' + c[0] + '&days=' + DAYS).then(function (d) { renderChart(c[0], d); })
        .catch(failBox(OV.chart[c[0]].box));
    });
    Promise.all([getJson('/admin/kyc'), getJson('/admin/reports')]).then(function (r) {
      S.kyc = r[0].submissions || [];
      S.reports = r[1].reports || [];
      renderQueues();
    }).catch(failBox(OV.qKyc));
    apiData('/admin/activity').then(function (d) { renderActivity(d || []); }).catch(failBox(OV.activity));
    TwAdminShell.health(true).then(renderSystem);
    apiData('/admin/audit?limit=5').then(renderRecentAudit).catch(failBox(OV.audit));
  }

  // ── security log (GET /admin/audit — read only) ──
  var AUDIT_PAG = 20;
  function buildAudit(sec) {
    var box = TwAdminShell.card(sec, { titleKey: 'admin.audit.title', hintKey: 'admin.audit.hint', icon: 'shield' });
    var lbl = el('label', 'adm-field');
    lbl.appendChild(el('span', null, twT('admin.audit.filter')));
    var sel = el('select', 'tw-input ep-select');
    sel.id = 'auditAction';
    sel.appendChild(new Option(twT('common.all'), ''));
    sel.addEventListener('change', function () { S.auditAction = sel.value; S.auditPage = 1; loadAudit(); });
    lbl.appendChild(sel);
    box.appendChild(lbl);
    BODY.audit = el('div');
    box.appendChild(BODY.audit);
    BODY.auditPag = el('div', 'tw-adm-pag');
    box.appendChild(BODY.auditPag);
    if (typeof window.scSelectInit === 'function') window.scSelectInit();
  }
  function loadAudit() {
    msg(BODY.audit, 'common.loading');
    var q = '/admin/audit?page=' + S.auditPage + '&limit=' + AUDIT_PAG + (S.auditAction ? '&action=' + encodeURIComponent(S.auditAction) : '');
    return apiData(q).then(function (d) {
      var sel = $('auditAction');
      if (sel && sel.options.length - 1 !== d.actions.length) {
        while (sel.options.length > 1) sel.remove(1);
        d.actions.forEach(function (a) { sel.appendChild(new Option(auditLabel(a), a)); });
        sel.value = S.auditAction;
      }
      BODY.audit.textContent = '';
      BODY.auditPag.textContent = '';
      if (!d.items.length) { msg(BODY.audit, 'admin.audit.empty'); return; }
      auditRows(BODY.audit, d.items);
      var pages = Math.ceil(d.total / d.limit);
      if (pages > 1) {
        var prev = btn('secondary', 'prev', 'admin.pag.prev', function () { S.auditPage--; loadAudit(); });
        var next = btn('secondary', 'next', 'admin.pag.next', function () { S.auditPage++; loadAudit(); });
        prev.disabled = d.page <= 1;
        next.disabled = d.page >= pages;
        BODY.auditPag.appendChild(prev);
        BODY.auditPag.appendChild(el('span', 'adm-pag-txt', twT('admin.pag.of', { page: d.page, pages: pages })));
        BODY.auditPag.appendChild(next);
      }
    }).catch(function (e) { console.error('[admin] audit:', e); msg(BODY.audit, 'admin.load_error'); });
  }

  // ── section switching (menu → hash) ──
  var LOADERS = {
    overview: loadOverview,
    users: function () { showUsers('users'); },
    companies: function () { showUsers('companies'); },
    audit: function () { loadAudit(); },
    jobs: loadJobs, reports: loadReports, kyc: loadKYC, errors: loadErrors,
    system: function () { if (!S.logoLoaded) loadLogo(); },
  };
  function show() {
    var key = TwAdminShell.currentKey();
    if (!$('sec-' + key)) key = 'overview';
    document.querySelectorAll('[data-adm-section]').forEach(function (s) { s.hidden = s.getAttribute('data-adm-section') !== key; });
    if (LOADERS[key]) LOADERS[key]();
  }

  // ── users / companies (one view, VIEWS[name]) ──
  function typeLabel(t) { return twT('admin.user.type.' + (t === 'co' || t === 'edu' ? t : 'emp')); }
  function buildUsersView(name, sec, titleKey, hintKey, icon) {
    var v = VIEWS[name];
    var box = TwAdminShell.card(sec, { titleKey: titleKey, hintKey: hintKey, icon: icon });
    v.search = el('input', 'tw-input');
    v.search.type = 'search';
    v.search.setAttribute('placeholder', twT('admin.users.search'));
    v.search.setAttribute('aria-label', twT('admin.users.search'));
    v.search.addEventListener('input', function () { v.page = 1; renderUsers(name); });
    box.appendChild(v.search);
    if (!v.fixed) {
      var chips = el('div', 'adm-btns');
      chips.setAttribute('role', 'group');
      ['', 'emp', 'co', 'edu'].forEach(function (t) {
        var c = btn('secondary', null, t ? 'admin.user.type.' + t : 'common.all', function () {
          v.filter = t; v.page = 1;
          chips.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
          renderUsers(name);
        });
        c.setAttribute('aria-pressed', String(!t));
        chips.appendChild(c);
      });
      box.appendChild(chips);
    }
    v.body = el('div');
    box.appendChild(v.body);
    v.pag = el('div', 'tw-adm-pag');
    box.appendChild(v.pag);
    msg(v.body, 'common.loading');
  }
  function showUsers(name) { if (S.users) renderUsers(name); else loadUsers(); }
  function loadUsers() {
    return getJson('/auth/users').then(function (d) {
      S.users = d.users || [];
      renderUsers('users');
      renderUsers('companies');
    }).catch(function (e) {
      console.error('[admin] users:', e);
      msg(VIEWS.users.body, 'admin.load_error');
      msg(VIEWS.companies.body, 'admin.load_error');
    });
  }
  function filteredUsers(v) {
    var q = String(v.search.value || '').toLowerCase();
    return (S.users || []).filter(function (u) {
      var hit = !q || String(u.full_name || '').toLowerCase().indexOf(q) !== -1 || String(u.email || '').toLowerCase().indexOf(q) !== -1;
      return hit && (!v.filter || u.user_type === v.filter);
    });
  }
  function renderUsers(name) {
    var v = VIEWS[name], list = filteredUsers(v), box = v.body;
    box.textContent = '';
    v.pag.textContent = '';
    if (!list.length) { msg(box, 'admin.users.empty'); return; }
    list.slice((v.page - 1) * PAG, v.page * PAG).forEach(function (u) {
      var id = Number(u.id), uname = u.full_name || twT('admin.user.unnamed');
      var t = u.user_type === 'co' || u.user_type === 'edu' ? u.user_type : '';
      var r = row(u.full_name, [u.email], pill(typeLabel(u.user_type), t));
      r.main.classList.add('is-link');
      r.main.setAttribute('role', 'link');
      r.main.setAttribute('tabindex', '0');
      var open = function () { location.href = '/admin-view?id=' + id; };
      r.main.addEventListener('click', open);
      r.main.addEventListener('keydown', function (e) { if (e.key === 'Enter') open(); });
      r.acts.appendChild(btn('secondary', 'mail', 'admin.users.message', function () { openMsg(id, uname); }));
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
      var b = el('button', 'tw-act tw-act-secondary' + (p === v.page ? ' is-current' : ''), String(p));
      b.type = 'button';
      if (p === v.page) b.setAttribute('aria-current', 'page');
      b.addEventListener('click', function () { v.page = p; renderUsers(name); });
      v.pag.appendChild(b);
    })(i);
  }

  // ── jobs ──
  function loadJobs() {
    return getJson('/admin/jobs').then(function (d) {
      S.jobs = d.jobs || [];
      renderJobs(($('jobSearch') || {}).value || '');
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
    // unified search → a job result opens the jobs section filtered by that title
    document.addEventListener('tw-adm:pick', function (e) {
      var d = (e && e.detail) || {};
      if (d.section === 'jobs' && $('jobSearch')) { $('jobSearch').value = d.q || ''; renderJobs(d.q || ''); }
    });
    show();
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
