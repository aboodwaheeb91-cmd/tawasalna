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
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); }, fire(t) { (ls[t] || []).forEach(fn => fn({})); },
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
    setTimeout: () => 0, clearTimeout: noop,
    document: { readyState: 'loading', addEventListener: noop, querySelector: () => null, querySelectorAll: () => [],
                createElement: fakeEl, getElementById: () => null },
    location: { pathname: opts.path || PANEL, hash: opts.hash || '', search: opts.search || '',
                replace: u => rec.replaced.push(u) },
    addEventListener: noop,
    twT: (k, v) => k + (v && v.word ? ':' + v.word : ''), twTApply: noop,
    twEscAttr: s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'),
    twEscHtml: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'),
    twIcon: n => '<svg data-i="' + n + '"></svg>',
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
      return Promise.resolve({ ok: st < 300, status: st, json: () => Promise.resolve({}) });
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  ['static/shared/admin-session.js', 'static/shared/admin-sections.js', 'static/shared/admin-shell.js']
    .concat(opts.page ? [opts.page === true ? 'static/admin/admin.js' : opts.page] : [])
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
    const files = ['admin.html', 'admin-email.html', 'admin-view.html', 'static/shared/admin-session.js',
      'static/shared/admin-sections.js', 'static/shared/admin-shell.js', 'static/shared/admin-shell.css',
      'static/admin/admin.js', 'static/admin-email/admin-email.js', 'static/admin-view/admin-view.js'];
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
      Object.keys(A).filter(k => !A[k].confirm).sort().join() === 'maintenance.scan,message.send');
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
    await f.ctx.TwAdminSession.fetch('/auth/users');
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
  const VCTX = { id: 5, item: 7, type: 'co', password: 'secret77', field: 'headline', value: 'x', text: 'hi' };
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

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
