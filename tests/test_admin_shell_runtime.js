/**
 * test_admin_shell_runtime.js — Admin Shell (task 5.3a · docs/rules/admin-shell.md)
 * Runs the REAL static/shared/admin-session.js + admin-sections.js + admin-shell.js (+ static/admin/admin.js
 * for its action table) in Node vm contexts.
 *   A  the registry builds the menu — one link per entry, hrefs relative to the panel root at runtime,
 *      current section from path / hash, a new registry line = a new link
 *   B  no panel prefix in any admin file the browser gets
 *   C  big actions never send a request without confirmation (twConfirm / typed-word twModal)
 *   D  401 from any admin call → back to the panel login with the "expired" flag · no session → login
 *   E  admin-view.html (task 5.3b — static/admin-view/admin-view.js): page outside the panel path uses this
 *      tab's panel root · every write needs a confirm · account type change needs the typed word ·
 *      cancel → no request · every confirm / done text key exists
 *   F  (task 5.3a2) desktop: side menu from the registry · mobile: menu button → the same links in a DS-OVL
 *      dialog that closes on a link · unified search groups · /health state · twChart geometry
 *   G  (task 5.3a3) users table: query from the view state (fixed type for companies) · page numbers ·
 *      CSV export needs a confirm and returns the file · unified search asks GET /admin/users only after typing stops
 *   H  (task 4.2) admin-settings: 403 → "no permission" on the page, session kept · 401 → login ·
 *      security settings in their own section · their save / reset need the typed word · 403 on save → toast only
 *   I  (phase 5b) admin-content: 403 → "no permission", session kept · 401 → login · strings save sends the
 *      whole override map, reset leaves the key out · colors: WCAG ratio · < 3:1 blocks the save, < 4.5 warns ·
 *      news: archive keeps every field (status archived) · delete needs the typed word · start / end sent as ISO UTC
 *
 *   L  task 8.6a — admin-content tab retried after a failed load · KYC docs window: approve / reject only in review
 *
 * Run: node tests/test_admin_shell_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const noop = () => {};
const PANEL = '/panel-x7';   // any first path segment — the real one is never in a file

function fakeEl(tag) {
  const ls = {};
  return {
    tagName: tag, value: '', textContent: '', className: '', hidden: false, children: [], attrs: {},
    setAttribute(k, v) { this.attrs[k] = String(v); }, removeAttribute(k) { delete this.attrs[k]; },
    getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); }, fire(t, ev) { (ls[t] || []).forEach(fn => fn(ev || {})); },
    focus: noop, querySelectorAll: () => [], classList: { add: noop, toggle: noop },
  };
}

// ctx: pathname / hash / token; stubs record navigation, requests, dialogs
function shell(opts) {
  opts = opts || {};
  const rec = { replaced: [], requests: [], confirms: [], modals: [], toasts: [] };
  const store = {};
  if (opts.token) store.tw_adm_token = opts.token;
  if (opts.panel) store.tw_adm_panel = opts.panel;
  const ctx = {
    console, JSON, Promise, URLSearchParams,
    sessionStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); },
                      removeItem: k => { delete store[k]; } },
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: opts.timers ? ((fn, ms) => { opts.timers.push([fn, ms]); return opts.timers.length; }) : () => 0, clearTimeout: noop,
    document: { readyState: 'loading', addEventListener: noop, querySelector: opts.header ? (q => (q === '[data-tw-header="admin"]' ? opts.header : null)) : () => null,
                querySelectorAll: () => [], createElement: fakeEl, getElementById: id => (opts.root && id === (opts.rootId || 'asRoot') ? opts.root : null), head: fakeEl('head'),
                body: { classList: { list: [], add(c) { this.list.push(c); } } } },
    location: { pathname: opts.path || PANEL, hash: opts.hash || '', search: opts.search || '',
                replace: u => rec.replaced.push(u) },
    addEventListener: noop,
    twT: (k, v) => k + (v && v.word ? ':' + v.word : ''), twTApply: noop,
    twEscAttr: s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'),
    twEscHtml: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'),
    twIcon: n => '<svg data-i="' + n + '"></svg>',
    twFormatNumber: n => String(n),
    showToast: (m, t) => rec.toasts.push([m, t]),
    twConfirm: o => { rec.confirms.push(o); return Promise.resolve(!!opts.confirmAnswer); },
    twModal: o => {
      const m = { opts: o, disabled: o.actions.map(a => !!a.disabled) };
      m.ctl = { setActionDisabled: (i, on) => { m.disabled[i] = !!on; }, close: noop };
      rec.modals.push(m);
      return m.ctl;
    },
    fetch: (url, init) => {
      const method = (init && init.method) || 'GET';
      rec.requests.push([url, method, init && init.body]);
      const st = (method === 'GET' && opts.getStatus) || opts.status || 200;
      // POST /admin/message answers like the server (task 5.3b2): {ok, data: {notification_id}} ·
      // the admin job actions (task 5.3j) answer {ok: true, data} like api_ok
      const jobAct = /^\/admin\/jobs\/\d+\/(hide|unhide|reactivate|extend|status|unarchive)$/.test(url)
        || (method === 'PUT' && /^\/admin\/jobs\/\d+$/.test(url));
      // GET …/delete-preview answers like the server (task 5.3j phase 4)
      const preview = /^\/admin\/jobs\/\d+\/delete-preview$/.test(url);
      // PUT /admin/user/{id}/email answers {ok, data: {sent: true}} (task 8.3)
      const emailAct = method === 'PUT' && /^\/admin\/user\/\d+\/email$/.test(url);
      const body = opts.json || (st < 300 && url === '/admin/message' ? { ok: true, data: { notification_id: 1 } }
        : st < 300 && emailAct ? { ok: true, data: { sent: true } }
        : st < 300 && jobAct ? { ok: true, data: { id: 3 } }
        : st < 300 && preview ? { ok: true, data: { id: 3, title: 'T', applicants: 4, pipeline_entries: 4, appointments: 1 } } : {});
      return Promise.resolve({ ok: st < 300, status: st, json: () => Promise.resolve(body),
                               blob: () => Promise.resolve({ size: 3, type: 'text/csv' }) });
    },
  };
  ctx.twIcon.hydrate = noop;
  Object.assign(ctx, opts.extra || {});
  ctx.window = ctx;
  vm.createContext(ctx);
  ['static/shared/admin-session.js', 'static/shared/admin-sections.js', 'static/shared/admin-shell.js',
   'static/shared/admin-jobs.js']
    .concat(opts.page ? [opts.page === true ? 'static/admin/admin.js' : opts.page] : []).concat(opts.chart ? ['static/shared/tw-chart.js'] : [])
    .forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  return { ctx, rec, store };
}
const b64url = o => Buffer.from(JSON.stringify(o)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const LIVE = b64url({ alg: 'HS256' }) + '.' + b64url({ exp: Math.floor(Date.now() / 1000) + 3600 }) + '.sig';
const tick = () => new Promise(r => setImmediate(r));

(async function main() {
  console.log('\nA — the registry builds the menu');
  {
    const { ctx } = shell();
    const reg = ctx.TW_ADMIN_SECTIONS, items = ctx.TwAdminShell.items();
    check('A1 one menu item per registry entry', reg.length > 0 && items.length === reg.length, items.length);
    const want = reg.map(s => !s.path ? PANEL : s.path[0] === '#' ? PANEL + s.path : PANEL + '/' + s.path);
    check('A2 hrefs are the runtime panel root + the relative path',
      JSON.stringify(items.map(i => i.href)) === JSON.stringify(want), JSON.stringify(items.map(i => i.href)));
    check('A3 label = twT(labelKey) · icon = registry icon',
      items.every((it, i) => it.label === reg[i].labelKey && it.icon === reg[i].icon));
    const html = ctx.TwAdminShell.navHtml('kyc');
    check('A4 menu HTML: one link per entry', (html.match(/<a /g) || []).length === reg.length);
    check('A5 current section marked once (aria-current)', (html.match(/aria-current="page"/g) || []).length === 1
      && /aria-current="page" href="[^"]*#kyc"/.test(html));
    check('A6 badge slots only for entries with a badge',
      (html.match(/data-adm-badge=/g) || []).length === reg.filter(s => s.badge).length);
    check('A7 every registry key is unique', new Set(reg.map(s => s.key)).size === reg.length);
    reg.push({ key: 'news', icon: 'newspaper', labelKey: 'admin.nav.news', path: 'news' });
    const after = ctx.TwAdminShell.items();
    check('A8 a new registry line = a new menu link', after.length === reg.length
      && after[after.length - 1].href === PANEL + '/news');
  }
  {
    check('A9 current = sub page by path', shell({ path: PANEL + '/email' }).ctx.TwAdminShell.currentKey() === 'email');
    check('A10 current = root section by hash', shell({ hash: '#reports' }).ctx.TwAdminShell.currentKey() === 'reports');
    check('A11 root without hash → the root entry', shell().ctx.TwAdminShell.currentKey() === 'overview');
  }

  console.log('\nB — no panel prefix in admin files the browser gets');
  {
    const files = ['admin.html', 'admin-email.html', 'admin-view.html', 'admin-job.html', 'static/shared/admin-jobs.js',
      'static/admin-job/admin-job.js', 'static/shared/admin-session.js',
      'static/shared/admin-sections.js', 'static/shared/admin-shell.js', 'static/shared/admin-shell.css',
      'static/admin/admin.js', 'static/admin-email/admin-email.js', 'static/admin-view/admin-view.js',
      'admin-settings.html', 'static/admin-settings/admin-settings.js'];   // task 4.1
    const bad = files.filter(f => read(f).indexOf('tw-ctrl') !== -1);
    check('B1 no "tw-ctrl" in any admin page / script / style', bad.length === 0, bad);
  }

  console.log('\nC — big actions never run without confirmation');
  const BIG = ['user.delete', 'job.delete', 'kyc.reject', 'report.resolve', 'maintenance.migrate', 'logo.upload'];
  const TYPED = ['user.delete', 'job.delete', 'maintenance.migrate'];
  {
    const A = shell({ page: true, token: LIVE }).ctx.TwAdminDash.ACTIONS;
    check('C1 every big action has a confirm step', BIG.every(k => A[k] && A[k].confirm), BIG.filter(k => !(A[k] && A[k].confirm)));
    check('C2 delete / migrate need a typed word and are danger', TYPED.every(k => A[k].confirm.typeWord && A[k].confirm.danger));
    check('C3 actions without a confirm are read-only or carry their own dialog',
      Object.keys(A).filter(k => !A[k].confirm).sort().join() === 'maintenance.scan');
  }
  for (const k of Object.keys(shell({ page: true }).ctx.TwAdminDash.ACTIONS)) {
    const s = shell({ page: true, token: LIVE, confirmAnswer: false });
    const a = s.ctx.TwAdminDash.ACTIONS[k];
    if (!a.confirm || a.confirm.typeWord) continue;
    const res = await s.ctx.TwAdminShell.run(a, { id: 3, dataUrl: 'data:x' });
    check('C4 ' + k + ': cancel → no request', res === null && s.rec.requests.length === 0 && s.rec.confirms.length === 1);
    const y = shell({ page: true, token: LIVE, confirmAnswer: true });
    const r2 = await y.ctx.TwAdminShell.run(y.ctx.TwAdminDash.ACTIONS[k], { id: 3, dataUrl: 'data:x' });
    check('C5 ' + k + ': confirm → exactly one request', r2 && r2.ok && y.rec.requests.length === 1, JSON.stringify(y.rec.requests));
  }
  for (const k of TYPED) {
    const s = shell({ page: true, token: LIVE });
    const p = s.ctx.TwAdminShell.run(s.ctx.TwAdminDash.ACTIONS[k], { id: 9 });
    await tick();
    const m = s.rec.modals[0];
    const input = m && m.opts.content.children[0].children[0];
    const word = s.ctx.twT(s.ctx.TwAdminDash.ACTIONS[k].confirm.typeWord);
    check('C6 ' + k + ': typed-word dialog opens with the confirm button disabled',
      !!m && m.disabled[1] === true && s.rec.confirms.length === 0 && m.opts.dismissible === false);
    input.value = 'خطأ';
    input.fire('input');
    check('C7 ' + k + ': wrong word keeps it disabled + click is refused',
      m.disabled[1] === true && m.opts.actions[1].onClick() === false);
    input.value = ' ' + word + ' ';
    input.fire('input');
    check('C8 ' + k + ': the right word enables it', m.disabled[1] === false);
    check('C9 ' + k + ': no request before the dialog closes', s.rec.requests.length === 0);
    m.opts.actions[1].onClick();
    m.opts.onClose('action');
    const res = await p;
    check('C10 ' + k + ': confirmed → one DELETE / POST request', res && res.ok && s.rec.requests.length === 1
      && /^(DELETE|POST)$/.test(s.rec.requests[0][1]), JSON.stringify(s.rec.requests));
    const c = shell({ page: true, token: LIVE });
    const pc = c.ctx.TwAdminShell.run(c.ctx.TwAdminDash.ACTIONS[k], { id: 9 });
    await tick();
    c.rec.modals[0].opts.onClose('cancel');
    check('C11 ' + k + ': cancelled → no request', (await pc) === null && c.rec.requests.length === 0);
  }

  console.log('\nD — session gate');
  {
    const s = shell({ path: PANEL + '/email', token: LIVE, status: 401 });
    check('D1 live session → start() true, no navigation', s.ctx.TwAdminShell.start() === true && s.rec.replaced.length === 0);
    await s.ctx.TwAdminSession.fetch('/admin/email');
    check('D2 401 → panel login with the expired flag (once)', s.rec.replaced.length === 1
      && s.rec.replaced[0] === PANEL + '?session=expired', JSON.stringify(s.rec.replaced));
    check('D3 the dead token is cleared', !s.store.tw_adm_token);
    await s.ctx.TwAdminSession.fetch('/admin/email');
    check('D4 a second 401 does not navigate again', s.rec.replaced.length === 1);
    const f = shell({ path: PANEL, token: LIVE, status: 403 });
    await f.ctx.TwAdminSession.fetch('/admin/users');
    check('D5 403 → same', f.rec.replaced[0] === PANEL + '?session=expired');
  }
  {
    const s = shell({ path: PANEL + '/email' });
    check('D6 no session on a sub page → login (no flag)', s.ctx.TwAdminShell.start() === false
      && s.rec.replaced.length === 1 && s.rec.replaced[0] === PANEL);
    const l = shell({ path: PANEL });
    check('D7 no session on the login page → false, page shows its form', l.ctx.TwAdminShell.start({ loginPage: true }) === false
      && l.rec.replaced.length === 0);
    check('D8 login page reads the expired flag', shell({ search: '?session=expired' }).ctx.TwAdminShell.wasExpired() === true
      && l.ctx.TwAdminShell.wasExpired() === false);
    check('D9 start() saves the panel root for admin-view (runtime only)', l.ctx.TwAdminSession.panelHref() === PANEL);
  }

  console.log('\nE — admin-view.html (one user · outside the panel path)');
  const VIEW = 'static/admin-view/admin-view.js';
  const STR = JSON.parse(read('tw_strings.json')).ar;
  // the page loads the user (GET) itself — 404 keeps it on its message; only writes are counted below
  const view = o => shell(Object.assign({ page: VIEW, path: '/admin-view', search: '?id=5', getStatus: 404 }, o));
  const writes = s => s.rec.requests.filter(r => r[1] !== 'GET');
  {
    const none = view({});
    check('E1 tab never opened the panel → no session use, no navigation, no request',
      none.rec.replaced.length === 0 && none.rec.requests.length === 0);
    const out = view({ panel: PANEL });
    check('E2 panel known, no session → back to the panel login', out.rec.replaced[0] === PANEL && out.rec.requests.length === 0);
    const live = view({ panel: PANEL, token: LIVE });
    check('E3 live session → loads the user once', live.rec.requests.length === 1
      && live.rec.requests[0][0] === '/admin/profile/5' && live.rec.replaced.length === 0);
    check('E4 menu links = this tab\'s panel root · «users» marked',
      live.ctx.TwAdminShell.items().every(i => i.href.indexOf(PANEL) === 0) && live.ctx.TwAdminShell.currentKey() === 'users');
    const bad = view({ panel: PANEL, token: LIVE, search: '?id=5x' });
    check('E5 invalid id → no request', bad.rec.requests.length === 0);
    const exp = view({ panel: PANEL, token: LIVE, getStatus: 401 });
    await tick(); await tick();
    check('E6 401 → panel login with the expired flag', exp.rec.replaced[0] === PANEL + '?session=expired', JSON.stringify(exp.rec.replaced));
  }
  const VA = view({ panel: PANEL, token: LIVE }).ctx.TwAdminUserView.ACTIONS;
  const VCTX = { id: 5, item: 7, type: 'co', password: 'secret77', field: 'headline', value: 'x', text: 'hi', email: 'new@x.com' };
  {
    const keys = Object.keys(VA);
    check('E7 every write on the page has a confirm step', keys.length >= 10 && keys.every(k => VA[k].confirm),
      keys.filter(k => !VA[k].confirm));
    check('E8 type change + account delete need a typed word and are danger',
      ['user.type', 'user.delete'].every(k => VA[k].confirm.typeWord && VA[k].confirm.danger));
    check('E9 password change + item deletes are danger',
      ['user.password', 'exp.delete', 'edu.delete', 'course.delete'].every(k => VA[k].confirm.danger));
    const missing = [];
    keys.forEach(k => {
      const c = VA[k].confirm;
      [c.title, c.message, c.confirm, c.typeWord, VA[k].done].forEach(x => { if (x && !(x in STR)) missing.push(k + ':' + x); });
    });
    check('E10 every confirm / done text key exists in tw_strings.json', missing.length === 0, missing);
  }
  for (const k of Object.keys(VA)) {
    if (VA[k].confirm.typeWord) continue;
    const s = view({ panel: PANEL, token: LIVE, confirmAnswer: false });
    const res = await s.ctx.TwAdminShell.run(s.ctx.TwAdminUserView.ACTIONS[k], VCTX);
    check('E11 ' + k + ': cancel → no request', res === null && writes(s).length === 0 && s.rec.confirms.length === 1);
    const y = view({ panel: PANEL, token: LIVE, confirmAnswer: true });
    const r2 = await y.ctx.TwAdminShell.run(y.ctx.TwAdminUserView.ACTIONS[k], VCTX);
    check('E12 ' + k + ': confirm → exactly one write', r2 && r2.ok && writes(y).length === 1, JSON.stringify(writes(y)));
  }
  {
    const s = view({ panel: PANEL, token: LIVE });
    const p = s.ctx.TwAdminShell.run(s.ctx.TwAdminUserView.ACTIONS['user.type'], VCTX);
    await tick();
    const m = s.rec.modals[0];
    const input = m && m.opts.content.children[0].children[0];
    check('E13 type change: dialog opens with the confirm button disabled', !!m && m.disabled[1] === true);
    input.value = 'نعم';
    input.fire('input');
    check('E14 type change without the word: still disabled + click refused + no request',
      m.disabled[1] === true && m.opts.actions[1].onClick() === false && writes(s).length === 0);
    m.opts.onClose('cancel');
    check('E15 closed without the word → no request', (await p) === null && writes(s).length === 0);
    const y = view({ panel: PANEL, token: LIVE });
    const py = y.ctx.TwAdminShell.run(y.ctx.TwAdminUserView.ACTIONS['user.type'], VCTX);
    await tick();
    const my = y.rec.modals[0], iy = my.opts.content.children[0].children[0];
    iy.value = y.ctx.twT('admin.confirm.word.type');
    iy.fire('input');
    my.opts.actions[1].onClick();
    my.opts.onClose('action');
    const ry = await py, w = writes(y);
    check('E16 the right word → one PUT /admin/user/5/type {user_type: co}', ry && ry.ok && w.length === 1
      && w[0][0] === '/admin/user/5/type' && w[0][1] === 'PUT' && JSON.parse(w[0][2]).user_type === 'co', JSON.stringify(w));
  }
  {
    const s = view({ panel: PANEL, token: LIVE, confirmAnswer: true, status: 422 });
    const res = await s.ctx.TwAdminShell.run(s.ctx.TwAdminUserView.ACTIONS['profile.edit'], VCTX);
    check('E17 a failed write → no «done» toast (result checked first)', res && !res.ok
      && s.rec.toasts.every(t => t[1] !== 'success'), JSON.stringify(s.rec.toasts));
  }
  {
    // 5.3b2: a 2xx reply without notification_id = the message did not arrive → no «done»
    const s = view({ panel: PANEL, token: LIVE, confirmAnswer: true, json: { success: true } });
    const res = await s.ctx.TwAdminShell.run(s.ctx.TwAdminUserView.ACTIONS['message.send'], VCTX);
    check('E18 message.send: 200 without notification_id → not ok, no «done» toast', res && !res.ok
      && s.rec.toasts.every(t => t[1] !== 'success') && s.rec.toasts.length === 1, JSON.stringify(s.rec.toasts));
  }

  console.log('\nF — side menu (desktop) · menu dialog (mobile) · search · health · chart (task 5.3a2)');
  {
    // a header placeholder that records what mount() renders and the listeners it binds
    const parts = {};
    const header = {
      innerHTML: '', hidden: true, classList: { add: noop },
      querySelector: q => (parts[q] = parts[q] || Object.assign(fakeEl('x'), { contains: () => false, querySelector: () => fakeEl('y') })),
      querySelectorAll: () => [],
    };
    const s = shell({ token: LIVE, hash: '#kyc', header });
    s.ctx.TwAdminShell.mount();
    const html = header.innerHTML, reg = s.ctx.TW_ADMIN_SECTIONS;
    const side = (html.match(/<aside class="tw-adm-side">([\s\S]*?)<\/aside>/) || [])[1] || '';
    check('F1 mount: header shown + side menu holds one link per registry entry',
      header.hidden === false && (side.match(/<a /g) || []).length === reg.length);
    check('F2 side menu marks the current section', /aria-current="page" href="[^"]*#kyc"/.test(side));
    check('F3 body gets the side-menu layout class', s.ctx.document.body.classList.list.indexOf('tw-adm-has-side') !== -1);
    check('F4 top bar: menu button · search · system status · badge shortcuts · logout',
      /data-adm-menu/.test(html) && /data-adm-search/.test(html) && /data-adm-health/.test(html)
      && (html.match(/class="tw-adm-iconbtn" href=/g) || []).length === reg.filter(x => x.badge).length && /data-adm-logout/.test(html));
    check('F5 no request for search data before the search is used', !s.rec.requests.some(r => r[0] === '/admin/jobs'));
    parts['[data-adm-menu]'].fire('click');
    const m = s.rec.modals[0];
    const nav = m && m.opts.content;
    check('F6 menu button opens a DS-OVL dialog with the same registry links',
      !!m && (nav.innerHTML.match(/<a /g) || []).length === reg.length && /aria-current="page" href="[^"]*#kyc"/.test(nav.innerHTML));
    let closed = 0;
    m.ctl.close = () => { closed++; };
    nav.fire('click', { target: { closest: () => null } });
    check('F7a a click outside a link keeps the menu dialog open', closed === 0);
    nav.fire('click', { target: { closest: sel => (sel === 'a' ? {} : null) } });
    check('F7 choosing a link closes the menu dialog', closed === 1);
    const css = read('static/shared/admin-shell.css');
    const desk = (css.match(/@media \(min-width: 1024px\) \{([\s\S]*?)\n\}/) || [])[1] || '';
    check('F8 desktop (≥1024): side menu fixed, menu button hidden · below: side menu hidden',
      /\.tw-adm-side \{ display: flex;[^}]*position: fixed/.test(desk) && /\.tw-adm-menu-btn[^{]*\{ display: none/.test(desk)
      && /^\.tw-adm-side \{ display: none; \}/m.test(css));

    const data = { users: [{ id: 1, full_name: 'سارة', email: 's@x', user_type: 'emp' }, { id: 2, full_name: 'Tech Co', email: 'hr@t', user_type: 'co' }],
                   jobs: [{ id: 5, title: 'Tech lead', company_name: 'Tech Co' }] };
    const g = s.ctx.TwAdminShell.searchResults(data, 'tech');
    check('F9 search: companies and jobs grouped, users without a match left out',
      g.map(x => x.key).join() === 'companies,jobs' && g[0].items[0].href === '/admin-view?id=2'
      && g[1].items[0].href === PANEL + '#jobs' && g[1].items[0].section === 'jobs');
    check('F10 search: empty query → nothing', s.ctx.TwAdminShell.searchResults(data, '  ').length === 0);
    const hs = s.ctx.TwAdminShell.healthState;
    check('F11 health: ok · degraded · down', hs({ status: 'ok', db: 'ok', email: 'configured', storage: 'configured' }) === 'ok'
      && hs({ status: 'ok', db: 'ok', email: 'missing', storage: 'configured' }) === 'degraded'
      && hs({ status: 'degraded', db: 'error' }) === 'down' && hs(null) === 'down');
  }
  {
    const c = shell({ chart: true }).ctx;
    const L = c.twChart.layout([{ value: 0 }, { value: 5 }, { value: 10 }], 'line');
    check('F12 chart: highest value reaches the top, zero sits on the base', L.max === 10 && L.ys[2] < L.ys[1] && L.ys[1] < L.ys[0]
      && L.xs[0] < L.xs[2] && L.bars[2].h > L.bars[1].h && L.bars[0].h === 0);
    const box = fakeEl('div');
    box.textContent = 'old';
    const w = c.twChart(box, { type: 'bar', title: 'T', points: [{ label: '<b>', value: 2 }, { label: 'b', value: 1 }] });
    check('F13 chart: drawn into the container, accessible name, labels escaped',
      box.children[0] === w && w.attrs.role === 'img' && /^T: /.test(w.attrs['aria-label'])
      && (w.innerHTML.match(/<rect /g) || []).length === 2 && w.innerHTML.indexOf('<b>') === -1);
  }

  console.log('\nG — users table · CSV export · server search (task 5.3a3)');
  {
    const D = shell({ page: true }).ctx.TwAdminDash;
    const q = D.usersQuery({ fixed: '', type: 'edu', status: 'pending', sort: 'oldest', q: 'سارة & co', page: 3 }, true);
    check('G1 view state → query (search encoded · type · status · sort · page · limit)',
      q === 'q=' + encodeURIComponent('سارة & co') + '&type=edu&status=pending&sort=oldest&page=3&limit=20', q);
    check('G2 companies view: the fixed type wins · export query has no page',
      D.usersQuery({ fixed: 'co', type: '', status: '', sort: 'newest', q: '', page: 2 }, false) === 'type=co&sort=newest');
    // task 5.3j phase 2 — row actions follow the server's state / effective_status
    const acts = j => D.jobActions(j).join();
    check('G1b job actions: active → hide · pause · extend · close · delete',
      acts({ status: 'active', effective_status: 'active' }) === 'hide,pause,extend,close,delete');
    check('G1b2 job actions: paused → hide · resume · extend · close · delete',
      acts({ status: 'paused', effective_status: 'paused' }) === 'hide,resume,extend,close,delete');
    check('G1c job actions: hidden + closed → unhide · reactivate · delete',
      acts({ status: 'hidden', effective_status: 'closed', admin_hidden_at: '2026-01-01' }) === 'unhide,reactivate,delete');
    check('G1d job actions: archived → unarchive · delete', acts({ status: 'archived', effective_status: 'active' }) === 'unarchive,delete');
    // task 5.3j phase 4 — delete asks the server what goes first; its counts reach the typed-word confirm
    {
      const s = shell({ page: true, token: LIVE, confirmAnswer: false });
      s.ctx.TwAdminJobs.confirmDelete({ id: 3, title: 'T' }, {});   // the typed-word dialog stays open
      await tick(); await tick(); await tick();
      check('G1f delete: the preview (GET …/delete-preview) comes first, then the typed-word confirm — no DELETE yet',
        s.rec.requests.length === 1 && s.rec.requests[0][0] === '/admin/jobs/3/delete-preview'
        && s.rec.modals.length === 1, JSON.stringify(s.rec.requests));
      const f = shell({ page: true, token: LIVE, getStatus: 500 });
      await f.ctx.TwAdminJobs.confirmDelete({ id: 3, title: 'T' }, {});
      await tick();
      check('G1g delete: no preview → no confirm, no delete (and an error toast)',
        !f.rec.requests.some(r => r[1] === 'DELETE') && f.rec.modals.length === 0 && f.rec.toasts.some(t => t[1] === 'error'));
    }
    check('G1e job query: hidden is a status tab', D.jobsQuery({ q: '', status: 'hidden', page: 1 }) === 'status=hidden&page=1&limit=20');
    check('G3 page numbers: first · around current · last, gaps as 0',
      D.pageList(5, 20).join() === '1,0,4,5,6,0,20' && D.pageList(1, 3).join() === '1,2,3' && D.pageList(1, 1).join() === '1');
    const A = D.ACTIONS['users.export'];
    check('G4 export: a confirm step + a download (blob) answer', !!(A && A.confirm && A.as === 'blob'));
    const n = shell({ page: true, token: LIVE, confirmAnswer: false });
    const r0 = await n.ctx.TwAdminShell.run(n.ctx.TwAdminDash.ACTIONS['users.export'], { query: 'type=co&sort=newest' });
    check('G5 export cancelled → no request', r0 === null && n.rec.requests.length === 0 && n.rec.confirms.length === 1);
    const y = shell({ page: true, token: LIVE, confirmAnswer: true });
    const r1 = await y.ctx.TwAdminShell.run(y.ctx.TwAdminDash.ACTIONS['users.export'], { query: 'type=co&sort=newest' });
    check('G6 export confirmed → one GET to /admin/users/export with the filters → the file',
      r1 && r1.ok && r1.data.size === 3 && y.rec.requests.length === 1
      && y.rec.requests[0][0] === '/admin/users/export?type=co&sort=newest' && y.rec.requests[0][1] === 'GET',
      JSON.stringify(y.rec.requests));
  }
  {
    const timers = [];
    const parts = {};
    const mk = sel => { const e = fakeEl('x'); e.contains = () => true; e.querySelector = () => fakeEl('y'); parts[sel] = e; return e; };
    const header = fakeEl('header');
    header.querySelector = sel => parts[sel] || mk(sel);
    header.querySelectorAll = () => [];
    const s = shell({ token: LIVE, header, timers, json: { ok: true, data: { items: [{ id: 7, full_name: 'Tech Co', email: 'hr@t', user_type: 'co' }] } } });
    s.ctx.TwAdminShell.mount();
    const input = parts['[data-adm-search]'];
    s.rec.requests.length = 0;
    input.value = 'te';
    input.fire('input');
    input.value = 'tech';
    input.fire('input');
    check('G7 search: nothing asked while typing', !s.rec.requests.some(r => /^\/admin\/users/.test(r[0])));
    const last = timers[timers.length - 1];
    check('G8 search waits a short pause', !!last && last[1] >= 200);
    last[0]();
    await tick(); await tick();
    const ureq = s.rec.requests.filter(r => /^\/admin\/users/.test(r[0]));
    check('G9 then one server search for the final text', ureq.length === 1 && /[?&]q=tech(&|$)/.test(ureq[0][0]), JSON.stringify(ureq));
  }

  console.log('\nH — admin-settings: 403 vs 401 · security section + typed word (task 4.2)');
  {
    const PAGE = 'static/admin-settings/admin-settings.js';
    const page = o => shell(Object.assign({ page: PAGE, path: PANEL + '/settings', token: LIVE, root: fakeEl('div') }, o));
    const texts = el => [el.textContent].concat((el.children || []).flatMap(texts));
    const f = page({ status: 403 });
    await tick(); await tick(); await tick();
    check('H1 403 → "no permission" message on the page', texts(f.ctx.document.getElementById('asRoot')).includes('admin.settings.forbidden'),
      JSON.stringify(texts(f.ctx.document.getElementById('asRoot'))));
    check('H2 403 → no navigation, session token kept', f.rec.replaced.length === 0 && !!f.store.tw_adm_token);
    const e = page({ status: 401 });
    await tick(); await tick(); await tick();
    check('H3 401 → back to the panel login (expired)', e.rec.replaced[0] === PANEL + '?session=expired' && !e.store.tw_adm_token,
      JSON.stringify(e.rec.replaced));
    const it = (key, group, security) => ({ key, group, security, value: 5, default: 5, min: 3, max: 20, changed: false,
      requires_restart: false, label: key, description: 'd', unit: 'count' });
    const ok = page({ json: { ok: true, data: { groups: ['messages', 'sec_login'], cache_ttl_s: 30,
      items: [it('message_send_hits', 'messages', false), it('login_email_hits', 'sec_login', true)] } } });
    await tick(); await tick(); await tick();
    const root = ok.ctx.document.getElementById('asRoot');
    const sec = root.children.find(c => c.attrs && c.attrs['data-settings-section'] === 'security');
    const rowsIn = el => (el.children || []).flatMap(c => (c.attrs && c.attrs['data-setting'] ? [c.attrs['data-setting']] : rowsIn(c)));
    check('H4 security settings only in their own section, after the others',
      !!sec && JSON.stringify(rowsIn(sec)) === '["login_email_hits"]' && root.children.indexOf(sec) === root.children.length - 1
      && !rowsIn({ children: root.children.filter(c => c !== sec) }).includes('login_email_hits'), JSON.stringify(rowsIn(root)));
    const A = ok.ctx.TwAdminSettings.ACTIONS;
    for (const k of ['save', 'reset']) {
      const s = page({ status: 200, getStatus: 403 });
      const p = s.ctx.TwAdminShell.run(A[k], { key: 'login_email_hits', value: 4, security: true, label: 'x', old: 5, new: 4 });
      await tick();
      const m = s.rec.modals[0];
      check('H5 ' + k + ' security: typed-word dialog (not a plain confirm), button off until the word',
        !!m && s.rec.confirms.length === 0 && m.disabled[1] === true, s.rec.confirms.length);
      check('H6 ' + k + ' security: the warning text', m && m.opts.message === 'admin.settings.security.' + k + '.message');
      m.opts.onClose('cancel');
      check('H7 ' + k + ' security: cancelled → no request', (await p) === null && s.rec.requests.filter(r => r[1] !== 'GET').length === 0);
      const n = page({ getStatus: 403, confirmAnswer: false });
      await n.ctx.TwAdminShell.run(A[k], { key: 'message_send_hits', value: 4, security: false });
      check('H8 ' + k + ' normal setting: plain confirm', n.rec.confirms.length === 1 && n.rec.modals.length === 0);
    }
    const d = page({ getStatus: 200, status: 403, confirmAnswer: true });
    const res = await d.ctx.TwAdminShell.run(A.save, { key: 'message_send_hits', value: 4, security: false });
    check('H9 save 403 → "no permission" toast, session kept, no navigation', res && res.status === 403
      && d.rec.toasts.some(t => t[0] === 'admin.settings.forbidden') && d.rec.replaced.length === 0 && !!d.store.tw_adm_token,
      JSON.stringify(d.rec.toasts));
    const S = JSON.parse(read('tw_strings.json')).ar;
    const keys = ['admin.settings.forbidden', 'admin.settings.security.title', 'admin.settings.security.hint',
      'admin.settings.security.badge', 'admin.settings.security.save.message', 'admin.settings.security.reset.message',
      'admin.settings.security.word', 'admin.audit.action.admin_settings_update_security', 'admin.audit.action.admin_settings_reset_security'];
    check('H10 every text key exists', keys.every(k => typeof S[k] === 'string'), keys.filter(k => typeof S[k] !== 'string'));
  }

  console.log('\nI — admin-content: strings · colors contrast · news (phase 5b)');
  {
    const PAGE = 'static/admin-content/admin-content.js';
    const CSS = { '--color-surface-page': '#070b18', '--color-text-on-brand': '#070b18', '--color-text-on-fill': '#ffffff' };
    const extra = {
      getComputedStyle: () => ({ getPropertyValue: n => CSS[n] || '' }),
      twFormatDateTime: v => 'D(' + v + ')',
      twSafeLinkUrl: u => (/^https?:\/\/\w/.test(u) ? u : ''),
      Option: function (t, v) { this.text = t; this.value = v; },
      twDateTimeField: o => ({ dateRow: fakeEl('div'), timeRow: fakeEl('div'), empty: () => !o.value,
        value: () => (o.value ? o.value : null) }),
    };
    const page = o => shell(Object.assign({ page: PAGE, path: PANEL + '/content', token: LIVE, root: fakeEl('div'),
                                            rootId: 'acRoot', extra }, o));
    const texts = el => [el.textContent].concat((el.children || []).flatMap(texts));
    const all = el => [el].concat((el.children || []).flatMap(all));
    const find = (el, fn) => all(el).find(fn);
    const settle = async () => { for (let i = 0; i < 6; i++) await tick(); };
    const puts = r => r.requests.filter(q => q[1] !== 'GET');

    const f = page({ status: 403 });
    await settle();
    check('I1 403 → "no permission" message, no navigation, session kept',
      texts(f.ctx.document.getElementById('acRoot')).includes('admin.content.forbidden') && f.rec.replaced.length === 0 && !!f.store.tw_adm_token);
    const e = page({ status: 401 });
    await settle();
    check('I2 401 → back to the panel login (expired)', e.rec.replaced[0] === PANEL + '?session=expired');

    // strings: save = whole map with this key · reset = map without it
    const SJ = { ok: true, data: { defaults: { 'a.one': 'واحد', 'b.two': 'اتنين' }, overrides: { 'b.two': 'معدّل' }, max_len: 300 } };
    const s = page({ json: SJ, confirmAnswer: true });
    await settle();
    const root = s.ctx.document.getElementById('acRoot');
    const rows = all(root).filter(x => x.attrs && x.attrs['data-string']);
    check('I3 every key listed with default + current value', rows.length === 2
      && find(rows[1], x => x.tagName === 'input').value === 'معدّل', rows.map(r => r.attrs['data-string']));
    const btnIn = (row, key) => find(row, x => x.tagName === 'button' && x.textContent === key);
    find(rows[0], x => x.tagName === 'input').value = 'جديد';
    btnIn(rows[0], 'admin.content.save').fire('click');
    await settle();
    let w = puts(s.rec);
    check('I4 save → PUT /admin/strings with the whole override map', w.length === 1 && w[0][0] === '/admin/strings' && w[0][1] === 'PUT'
      && JSON.stringify(JSON.parse(w[0][2]).overrides) === JSON.stringify({ 'b.two': 'معدّل', 'a.one': 'جديد' }), JSON.stringify(w));
    const s2 = page({ json: SJ, confirmAnswer: true });
    await settle();
    const r2 = all(s2.ctx.document.getElementById('acRoot')).filter(x => x.attrs && x.attrs['data-string']);
    check('I5 reset off for a key without override', btnIn(r2[0], 'admin.content.reset').disabled === true);
    btnIn(r2[1], 'admin.content.reset').fire('click');
    await settle();
    w = puts(s2.rec);
    check('I6 reset → the key left out (empty = default)', w.length === 1 && JSON.stringify(JSON.parse(w[0][2]).overrides) === '{}', JSON.stringify(w));
    const s3 = page({ json: SJ });
    await settle();
    const search = find(s3.ctx.document.getElementById('acRoot'), x => x.tagName === 'input' && x.type === 'search');
    search.value = 'اتنين';
    const list = find(s3.ctx.document.getElementById('acRoot'), x => (x.children || []).some(c => c.attrs && c.attrs['data-string']));
    list.children = [];   // the fake element keeps children on textContent = '' — the page clears it there
    search.fire('input');
    const shown = all(s3.ctx.document.getElementById('acRoot')).filter(x => x.attrs && x.attrs['data-string']).map(x => x.attrs['data-string']);
    check('I7 search by text finds the key', JSON.stringify(shown) === '["b.two"]', JSON.stringify(shown));

    // colors: contrast + block / warn
    const C = s.ctx.TwAdminContent;
    check('I8 WCAG ratio white / black = 21', Math.abs(C.contrast('#ffffff', '#000000') - 21) < 0.01);
    const lv = v => C.colorCheck('--color-brand-primary', v).level;
    check('I9 levels: teal ok · #777777 warn (< 4.5) · #5a5a5a block (< 3)',
      lv('#00c896') === 'ok' && lv('#777777') === 'warn' && lv('#5a5a5a') === 'block', [lv('#00c896'), lv('#777777'), lv('#5a5a5a')]);
    const CJ = { ok: true, data: { tokens: ['--color-brand-primary', '--color-brand-accent'],
      defaults: { '--color-brand-primary': '#00c896', '--color-brand-accent': '#8b5cf6' }, overrides: { '--color-brand-accent': '#7c3aed' } } };
    const c = page({ json: CJ, confirmAnswer: true });
    await settle();
    await c.ctx.TwAdminContent.show('colors');
    await settle();
    const crow = find(c.ctx.document.getElementById('acRoot'), x => x.attrs && x.attrs['data-color'] === '--color-brand-primary');
    const hex = find(crow, x => x.tagName === 'input' && x.type === 'text');
    const save = btnIn(crow, 'admin.content.save');
    hex.value = '#5a5a5a';
    hex.fire('input');
    const blocked = save.disabled === true && texts(crow).includes('admin.content.colors.block');
    save.fire('click');
    await settle();
    check('I10 contrast < 3:1 → save off + message, no request', blocked && puts(c.rec).length === 0, JSON.stringify(puts(c.rec)));
    hex.value = '#777777';
    hex.fire('input');
    check('I11 contrast < 4.5:1 → warning, save allowed', save.disabled === false && texts(crow).includes('admin.content.colors.warn'));
    save.fire('click');
    await settle();
    w = puts(c.rec);
    check('I12 save keeps the other saved color', w.length === 1 && w[0][0] === '/admin/theme/colors'
      && JSON.stringify(JSON.parse(w[0][2]).overrides) === JSON.stringify({ '--color-brand-accent': '#7c3aed', '--color-brand-primary': '#777777' }), JSON.stringify(w));

    // news
    const NJ = { news: [{ id: 7, title: 'T', summary: 'S', body: 'B', category: 'general', country: '', source_url: '',
      status: 'published', starts_at: null, ends_at: null, active_now: true }] };
    const n = page({ json: NJ, confirmAnswer: true });
    await settle();
    await n.ctx.TwAdminContent.show('news');
    await settle();
    const nroot = n.ctx.document.getElementById('acRoot');
    const tr = find(nroot, x => x.attrs && x.attrs['data-news'] === '7');
    check('I13 table row: title · status · active_now from the server', !!tr && texts(tr).includes('T')
      && texts(tr).includes('admin.content.news.active.yes'));
    btnIn(tr, 'admin.content.news.archive').fire('click');
    await settle();
    w = puts(n.rec);
    const ab = w[0] && JSON.parse(w[0][2]);
    check('I14 archive → PUT with every field kept + status archived', w.length === 1 && w[0][0] === '/admin/news/7' && w[0][1] === 'PUT'
      && ab.status === 'archived' && ab.body === 'B' && ab.summary === 'S' && ab.title === 'T', JSON.stringify(w));
    const d = page({ json: NJ, confirmAnswer: true });
    await settle();
    await d.ctx.TwAdminContent.show('news');
    await settle();
    const dtr = find(d.ctx.document.getElementById('acRoot'), x => x.attrs && x.attrs['data-news'] === '7');
    btnIn(dtr, 'admin.content.news.delete').fire('click');
    await settle();
    const dm = d.rec.modals[0];
    check('I15 delete → typed-word dialog (not a plain confirm), button off', !!dm && d.rec.confirms.length === 0 && dm.disabled[1] === true);
    dm.opts.onClose('cancel');
    await settle();
    check('I16 delete cancelled → no request', puts(d.rec).length === 0);
    // create: local pick → ISO UTC
    const k = page({ json: { news: [] }, confirmAnswer: true });
    await settle();
    await k.ctx.TwAdminContent.show('news');
    await settle();
    const START = new Date(2026, 9, 1, 9, 30);
    k.ctx.twDateTimeField = () => ({ dateRow: fakeEl('div'), timeRow: fakeEl('div'), empty: () => false, value: () => START });
    btnIn(k.ctx.document.getElementById('acRoot'), 'admin.content.news.add').fire('click');
    const fm = k.rec.modals[0];
    find(fm.opts.content, x => x.tagName === 'input').value = 'خبر';
    const bad = fm.opts.actions[1].onClick();
    check('I17 end not after start → stays open, no request', bad === false && puts(k.rec).length === 0);
    const k2 = page({ json: { news: [] }, confirmAnswer: true });
    await settle();
    await k2.ctx.TwAdminContent.show('news');
    await settle();
    let call = 0;
    k2.ctx.twDateTimeField = () => { const v = call++ ? null : START;
      return { dateRow: fakeEl('div'), timeRow: fakeEl('div'), empty: () => !v, value: () => v }; };
    btnIn(k2.ctx.document.getElementById('acRoot'), 'admin.content.news.add').fire('click');
    const fm2 = k2.rec.modals[0];
    find(fm2.opts.content, x => x.tagName === 'input').value = 'خبر';
    await fm2.opts.actions[1].onClick();
    w = puts(k2.rec);
    const nb = w[0] && JSON.parse(w[0][2]);
    check('I18 create → POST /admin/news, start = ISO UTC of the local pick, open end = null',
      w.length === 1 && w[0][0] === '/admin/news' && w[0][1] === 'POST' && nb.starts_at === START.toISOString()
      && /Z$/.test(nb.starts_at) && nb.ends_at === null && nb.title === 'خبر', JSON.stringify(w));
    const S = JSON.parse(read('tw_strings.json')).ar;
    const used = read(PAGE).match(/'admin\.(?:content|done)\.[a-z_.]+'/g).map(x => x.slice(1, -1))
      .filter(x => !/\.$/.test(x));
    check('I19 every literal text key exists', used.every(x => typeof S[x] === 'string'), used.filter(x => typeof S[x] !== 'string'));
  }

  console.log('\nJ — KYC reject: reason for the user + internal note (task 8.1)');
  {
    const s = shell({ page: true, token: LIVE, confirmAnswer: true });
    const got = [];
    s.ctx.TwAdminShell.formDialog({ titleKey: 't', labelKey: 'a', kind: 'textarea', sendKey: 's', danger: true,
      extra: { labelKey: 'b', kind: 'textarea' }, onSend: (v, x) => { got.push([v, x]); return true; } });
    const m = s.rec.modals[s.rec.modals.length - 1];
    const fields = m.opts.content.children.map(l => l.children[0]);
    check('J1 extra → two fields in one dialog', fields.length === 2 && fields.every(f => f.tagName === 'textarea'));
    fields[0].value = 'سبب'; fields[1].value = 'داخلي';
    m.opts.actions[1].onClick();
    check('J2 send → onSend(value, extraValue)', got.length === 1 && got[0][0] === 'سبب' && got[0][1] === 'داخلي');
    const one = shell({ page: true, token: LIVE });
    one.ctx.TwAdminShell.formDialog({ titleKey: 't', labelKey: 'a', sendKey: 's', onSend: (v, x) => got.push([v, x]) });
    one.rec.modals[0].opts.actions[1].onClick();
    check('J3 no extra → one field, extraValue undefined (old callers unchanged)',
      one.rec.modals[0].opts.content.className === 'tw-adm-form' && got[1][1] === undefined);
    const r = await s.ctx.TwAdminShell.run(s.ctx.TwAdminDash.ACTIONS['kyc.reject'], { id: 3, reason: 'سبب', note: 'داخلي' });
    const req = s.rec.requests[s.rec.requests.length - 1];
    check('J4 kyc.reject sends {reason, note} after the confirm', !!r && req[0] === '/admin/kyc/3/reject' && req[1] === 'PUT'
      && JSON.stringify(JSON.parse(req[2])) === JSON.stringify({ reason: 'سبب', note: 'داخلي' }), req);
  }

  console.log('\nK — admin email change: a request, the link goes to the new address (task 8.3)');
  {
    const VK = view({ panel: PANEL, token: LIVE }).ctx.TwAdminUserView.ACTIONS['user.email'];
    check('K1 user.email: danger confirm, texts exist', !!VK && VK.confirm.danger
      && [VK.confirm.title, VK.confirm.message, VK.confirm.confirm, VK.done].every(k => k in STR));
    const s = view({ panel: PANEL, token: LIVE, confirmAnswer: true });
    const r = await s.ctx.TwAdminShell.run(s.ctx.TwAdminUserView.ACTIONS['user.email'], VCTX);
    const w = writes(s);
    check('K2 confirm → one PUT /admin/user/5/email {new_email} + «done»', r && r.ok && w.length === 1
      && w[0][0] === '/admin/user/5/email' && w[0][1] === 'PUT' && JSON.parse(w[0][2]).new_email === 'new@x.com'
      && s.rec.toasts.some(t => t[1] === 'success'), JSON.stringify(w));
    const n = view({ panel: PANEL, token: LIVE, confirmAnswer: true, json: { ok: true, data: {} } });
    const rn = await n.ctx.TwAdminShell.run(n.ctx.TwAdminUserView.ACTIONS['user.email'], VCTX);
    check('K3 200 without sent → not ok, no «done»', rn && !rn.ok && n.rec.toasts.every(t => t[1] !== 'success'));
    const c = view({ panel: PANEL, token: LIVE, confirmAnswer: false });
    check('K4 cancel → no request', (await c.ctx.TwAdminShell.run(c.ctx.TwAdminUserView.ACTIONS['user.email'], VCTX)) === null
      && writes(c).length === 0);
    // formDialog fieldError: a server 422 message under the field, cleared on typing
    const f = shell({ page: true, token: LIVE });
    let setErr = null;
    f.ctx.TwAdminShell.formDialog({ titleKey: 't', labelKey: 'a', kind: 'email', sendKey: 's',
      onSend: (v, x, fe) => { setErr = fe; fe('مستخدم'); return false; } });
    const m = f.rec.modals[0], label = m.opts.content, input = label.children[0], err = label.children[1];
    check('K5 email field type', input.type === 'email');
    m.opts.actions[1].onClick();
    check('K6 fieldError(text) → message shown + aria-invalid', typeof setErr === 'function' && !err.hidden
      && err.textContent === 'مستخدم' && input.attrs['aria-invalid'] === 'true');
    input.fire('input');
    check('K7 typing clears it', err.hidden && !('aria-invalid' in input.attrs));
  }

  console.log('\nL — task 8.6a: content tab retried after a failed load · KYC docs window buttons only in review');
  {
    const extra = { getComputedStyle: () => ({ getPropertyValue: () => '' }), twFormatDateTime: v => v,
      twSafeLinkUrl: u => u, Option: function () {}, twDateTimeField: () => ({ dateRow: fakeEl('div'), timeRow: fakeEl('div'),
        empty: () => true, value: () => null }) };
    const p = shell({ page: 'static/admin-content/admin-content.js', path: PANEL + '/content', token: LIVE, root: fakeEl('div'),
                      rootId: 'acRoot', extra, json: { ok: true, data: { defaults: {}, overrides: {} }, news: [] } });
    for (let i = 0; i < 6; i++) await tick();
    const realFetch = p.ctx.fetch;
    let newsCalls = 0;
    p.ctx.fetch = (url, init) => {
      if (url === '/admin/news' && ++newsCalls === 1) return Promise.reject(new Error('net'));
      return realFetch(url, init);
    };
    await p.ctx.TwAdminContent.show('news');
    await p.ctx.TwAdminContent.show('strings');
    await p.ctx.TwAdminContent.show('news');
    await p.ctx.TwAdminContent.show('strings');
    await p.ctx.TwAdminContent.show('news');
    check('L1 failed tab load → requested again on return · after success → not again', newsCalls === 2, newsCalls);

    const k = shell({ page: true, token: LIVE });
    const labels = m => m.opts.actions.map(a => a.text);
    k.ctx.TwAdminDash.openKYCDocs(1, 2, false);
    k.ctx.TwAdminDash.openKYCDocs(1, 2, true);
    const [closed, open] = k.rec.modals.slice(-2);
    check('L2 docs window outside review → close only (no approve / reject)',
      JSON.stringify(labels(closed)) === '["common.close"]', JSON.stringify(labels(closed)));
    check('L3 docs window in review → approve + reject + close',
      JSON.stringify(labels(open)) === '["admin.kyc.approve","admin.kyc.reject","common.close"]', JSON.stringify(labels(open)));
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
