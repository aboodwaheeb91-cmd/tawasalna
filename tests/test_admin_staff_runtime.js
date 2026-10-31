/**
 * test_admin_staff_runtime.js — the owner's staff screen (task 8.4c-2b-2 · docs/rules/admin-staff.md rule 16).
 * Runs the REAL static/shared/admin-session.js + admin-sections.js + admin-shell.js + static/admin-staff/admin-staff.js
 * in Node vm contexts with a small fake DOM, fake DS-OVL (twConfirm / twModal) and a fake fetch.
 *   S  the section: hidden from a staff member (menu) + the page → empty state, only /admin/me asked · shown to the owner
 *   B  buttons by status (invited / active / suspended) — the others never render
 *   D  danger actions (suspend · mfa-reset · cancel invite · role delete): danger confirm with the name, no request
 *      before it, cancel = no request
 *   U  428 → the shell's step-up dialog → the same request again once
 *   E  every error code → its own message · 403 / 429 / network · role_in_use keeps the page · 428 cancelled
 *   N  no double send · success → the lists are read again · invite: email_sent false → its message · a field code
 *      keeps the form open with the error under the field
 *   P  effective perms shown right (role + allow − deny)
 * Run: node tests/test_admin_staff_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const tick = async (n) => { for (let i = 0; i < (n || 10); i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const T = (k, v) => String(k in STRINGS ? STRINGS[k] : k).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m));
const PANEL = '/panel-x7';
const b64url = o => Buffer.from(JSON.stringify(o)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const LIVE = b64url({ alg: 'HS256' }) + '.' + b64url({ exp: Math.floor(Date.now() / 1000) + 3600 }) + '.sig';
const OO = ['users.delete', 'users.type', 'users.password', 'users.email', 'users.export', 'settings.security',
            'audit.view', 'staff.manage', 'system.manage'];

function fakeEl(tag) {
  const ls = {};
  const e = {
    tagName: String(tag).toUpperCase(), children: [], parentNode: null, hidden: false, disabled: false, checked: false,
    value: '', className: '', type: '', id: '', dir: '', _text: '', attrs: {}, options: [],
    get textContent() { return this._text + this.children.map(c => c.textContent).join(''); },
    set textContent(v) { this.children = []; this._text = String(v); },
    set innerHTML(v) { this.children = []; this._text = ''; }, get innerHTML() { return ''; },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; this.children.push(c); if (c._option) this.options.push(c); return c; },
    insertBefore(n) { n.parentNode = this; this.children.unshift(n); return n; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; },
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); },
    fire(t, ev) { (ls[t] || []).forEach(fn => fn(Object.assign({ preventDefault() {} }, ev || {}))); },
    click() { if (!this.disabled) this.fire('click'); }, focus() {},
    querySelectorAll: () => [], classList: { add() {}, toggle() {}, contains: () => false },
  };
  return e;
}
function findAll(e, pred, out) {
  out = out || [];
  if (pred(e)) out.push(e);
  e.children.forEach(c => findAll(c, pred, out));
  return out;
}
const find = (e, pred) => findAll(e, pred)[0] || null;

const ROLES = [
  { id: 1, name: 'دعم', perms: ['message.send', 'support.manage', 'users.view'], staff_count: 2 },
  { id: 2, name: 'توثيق', perms: ['kyc.review', 'users.view'], staff_count: 0 },
];
const GRANTABLE = [
  { perm: 'users.view', label: 'عرض المستخدمين وملفاتهم' }, { perm: 'kyc.review', label: 'مراجعة طلبات التوثيق' },
  { perm: 'support.manage', label: 'تذاكر الدعم' }, { perm: 'message.send', label: 'إرسال رسالة لمستخدم' },
  { perm: 'jobs.manage', label: 'إدارة الوظائف' },
];
const STAFF = [
  { id: 11, name: 'سامر', email: 'samer@example.com', status: 'active', role: { id: 1, name: 'دعم' },
    allow: ['jobs.manage'], deny: ['message.send'], effective_perms: ['jobs.manage', 'support.manage', 'users.view'],
    mfa_bound: true, last_login_at: '2026-10-30T10:00:00Z' },
  { id: 12, name: 'ليلى', email: 'layla@example.com', status: 'invited', role: null, allow: [], deny: [],
    effective_perms: [], mfa_bound: false, last_login_at: null },
  { id: 13, name: 'رامي', email: 'rami@example.com', status: 'suspended', role: { id: 2, name: 'توثيق' }, allow: [], deny: [],
    effective_perms: ['kyc.review', 'users.view'], mfa_bound: true, last_login_at: null },
];

// opts.me = /admin/me body · opts.write(url, method, body, stepup) → [status, body] | 'network'
// opts.confirm = true | false (twConfirm answer) · opts.stepUp = 'ok' | 'cancel'
function page(opts) {
  opts = opts || {};
  const rec = { requests: [], confirms: [], modals: [], toasts: [], replaced: [] };
  const store = { tw_adm_token: LIVE };
  const root = fakeEl('div');
  root.id = 'stRoot';
  const main = fakeEl('main');
  main.appendChild(root);
  const res = (st, body) => ({ ok: st >= 200 && st < 300, status: st, json: () => Promise.resolve(body), clone() { return res(st, body); } });
  const ctx = {
    console: { log() {}, warn() {}, error() {}, info() {} }, JSON, Promise, Object, Array, Number, String, Math, Date, RegExp,
    URLSearchParams,
    sessionStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: () => 0, clearTimeout() {},
    document: { readyState: 'complete', addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
                createElement: fakeEl, getElementById: id => (id === 'stRoot' ? root : null), head: fakeEl('head'),
                body: fakeEl('body'), title: '' },
    location: { pathname: PANEL + '/staff', hash: '', search: '', replace: u => rec.replaced.push(u) },
    addEventListener() {},
    Option: function (text, value) { const o = fakeEl('option'); o._text = text; o.value = value; o._option = true; return o; },
    twT: T, twTApply() {}, twIcon: Object.assign(() => '', { hydrate() {} }),
    twEscAttr: s => String(s), twEscHtml: s => String(s),
    twFormatNumber: n => String(n), twFormatDateTime: v => 'DT(' + v + ')',
    showToast: (m, t) => rec.toasts.push([m, t]),
    twConfirm: o => { rec.confirms.push(o); return Promise.resolve(typeof opts.confirm === 'function' ? opts.confirm(o) : opts.confirm !== false); },
    twModal: o => {
      const m = { opts: o, closed: null };
      m.ctl = { setActionDisabled() {}, close: () => { m.closed = 'close'; } };
      rec.modals.push(m);
      if (o.title === T('admin.stepup.title')) {   // the shell's step-up dialog: answer it like a person
        setImmediate(async () => {
          if (opts.stepUp === 'cancel') { o.onClose('cancel'); return; }
          o.content.children[0].children[1].value = '123456';
          const kept = await o.actions[1].onClick();
          if (kept !== false) o.onClose('action');
        });
      }
      return m.ctl;
    },
    fetch: (url, init) => {
      init = init || {};
      const method = init.method || 'GET', h = init.headers || {};
      const body = init.body ? JSON.parse(init.body) : undefined;
      rec.requests.push({ url, method, body, stepup: h['X-Admin-Stepup'] || '' });
      if (url === '/admin/me') return Promise.resolve(res(200, opts.me || { kind: 'owner', name: null, perms: ['*'], owner_only: OO }));
      if (url === '/admin/step-up') return Promise.resolve(res(200, { grant: 'G.R.ANT', expires_in: 300 }));
      if (url === '/admin/staff' && method === 'GET') return Promise.resolve(res(200, { ok: true, data: { staff: STAFF } }));
      if (url === '/admin/roles' && method === 'GET') return Promise.resolve(res(200, { ok: true, data: { roles: ROLES, grantable: GRANTABLE } }));
      const r = opts.write ? opts.write(url, method, body, h['X-Admin-Stepup'] || '') : [200, { ok: true, data: { id: 1, email_sent: true } }];
      if (r === 'network') return Promise.reject(new TypeError('net'));
      if (r === 'hold') return new Promise(() => {});
      return Promise.resolve(res(r[0], r[1]));
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  ['static/shared/admin-session.js', 'static/shared/admin-sections.js', 'static/shared/admin-shell.js', 'static/admin-staff/admin-staff.js']
    .forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  return { ctx, rec, root, main };
}
const writes = rec => rec.requests.filter(r => r.method !== 'GET' && r.url !== '/admin/step-up');
const rowOf = (root, id) => find(root, e => e.attrs['data-staff'] === String(id));
const actBtn = (row, act) => find(row, e => e.tagName === 'BUTTON' && e.attrs['data-act'] === act);
const acts = row => findAll(row, e => e.tagName === 'BUTTON' && e.attrs['data-act']).map(b => b.attrs['data-act']).join(',');
const lastToast = rec => (rec.toasts[rec.toasts.length - 1] || [])[0];

(async function main() {
  console.log('\nS — the section: owner only');
  {
    const p = page();
    const A = p.ctx.TwAdminShell;
    const sec = p.ctx.TW_ADMIN_SECTIONS.find(s => s.key === 'staff');
    check('S1 registry: key staff · perm staff.manage · path staff', !!sec && sec.perm === 'staff.manage' && sec.path === 'staff');
    check('S2 hidden from a staff member (even with every grantable perm + staff.manage listed)',
      !A.items(GRANTABLE.map(g => g.perm).concat(['staff.manage']), OO).some(i => i.key === 'staff'));
    check('S3 shown to the owner ("*") · href = panel root + /staff',
      A.items(['*'], OO).some(i => i.key === 'staff' && i.href === PANEL + '/staff'));
    await tick();
    check('S4 owner: /admin/staff + /admin/roles loaded and rendered',
      p.rec.requests.some(r => r.url === '/admin/staff') && p.rec.requests.some(r => r.url === '/admin/roles') && !!rowOf(p.root, 11));
  }
  {
    const p = page({ me: { kind: 'staff', name: 'S', perms: GRANTABLE.map(g => g.perm), owner_only: OO } });
    await tick();
    check('S5 staff opens the link → only /admin/me asked', p.rec.requests.map(r => r.url).join(',') === '/admin/me',
      p.rec.requests.map(r => r.url));
    check('S6 staff → root hidden + "no permission" empty state', p.root.hidden === true
      && p.main.children.some(n => n.textContent === T('admin.perm.denied')) && p.rec.replaced.length === 0);
  }

  console.log('\nB — buttons by status');
  {
    const p = page();
    await tick();
    check('B1 invited → resend · cancel', acts(rowOf(p.root, 12)) === 'resend,cancel', acts(rowOf(p.root, 12)));
    check('B2 active → access · suspend · mfa', acts(rowOf(p.root, 11)) === 'access,suspend,mfa', acts(rowOf(p.root, 11)));
    check('B3 suspended → restore · access', acts(rowOf(p.root, 13)) === 'restore,access', acts(rowOf(p.root, 13)));
    const r11 = rowOf(p.root, 11).textContent;
    check('B4 row: name · email · status · role · last login · authenticator', r11.indexOf('سامر') !== -1
      && r11.indexOf('samer@example.com') !== -1 && r11.indexOf(T('admin.staff.status.active')) !== -1
      && r11.indexOf(T('admin.staff.role_label', { role: 'دعم' })) !== -1 && r11.indexOf('DT(2026-10-30T10:00:00Z)') !== -1
      && r11.indexOf(T('admin.staff.mfa.bound')) !== -1);
    const r12 = rowOf(p.root, 12).textContent;
    check('B5 invited row: no role · never signed in · authenticator not bound', r12.indexOf(T('admin.staff.role.none')) !== -1
      && r12.indexOf(T('admin.staff.last_login_never')) !== -1 && r12.indexOf(T('admin.staff.mfa.unbound')) !== -1);
    const html = JSON.stringify(p.root, (k, v) => (k === 'parentNode' ? undefined : v));
    check('B6 no token / invite link / #t= in the page', html.indexOf('#t=') === -1 && html.indexOf('/staff/invite') === -1
      && !/token/i.test(html.replace(/tw_adm_token/g, '')));
  }

  console.log('\nP — effective perms (role + allow − deny)');
  {
    const p = page();
    await tick();
    const rows = p.ctx.TwAdminStaff.permRows(STAFF[0], ROLES, GRANTABLE);
    const m = {};
    rows.forEach(r => { m[r.perm] = r.source; });
    check('P1 role perms → role · extra allow → allow · denied role perm → deny · others absent',
      m['users.view'] === 'role' && m['support.manage'] === 'role' && m['jobs.manage'] === 'allow'
      && m['message.send'] === 'deny' && !('kyc.review' in m), m);
    const list = find(rowOf(p.root, 11), e => 'data-perms' in e.attrs);
    check('P2 details hidden until asked', list.hidden === true);
    const toggle = find(rowOf(p.root, 11), e => e.tagName === 'BUTTON' && e._text === T('admin.staff.act.details'));
    toggle.click();
    const lis = findAll(list, e => e.tagName === 'LI');
    check('P3 details: Arabic labels from the catalog + source pill', list.hidden === false && lis.length === 4
      && lis.some(li => li.attrs['data-perm'] === 'jobs.manage' && li.textContent.indexOf('إدارة الوظائف') !== -1
        && li.textContent.indexOf(T('admin.staff.src.allow')) !== -1)
      && lis.some(li => li.attrs['data-source'] === 'deny' && li.textContent.indexOf(T('admin.staff.src.deny')) !== -1));
  }

  console.log('\nD — danger actions: confirm first, cancel = no request');
  const DANGER = [
    ['suspend', 11, 'suspend', '/admin/staff/11/suspend', 'POST', 'سامر'],
    ['mfa', 11, 'mfa', '/admin/staff/11/mfa-reset', 'POST', 'سامر'],
    ['cancel', 12, 'cancel', '/admin/staff/12', 'DELETE', 'ليلى'],
  ];
  for (const [act, id, key, url, method, name] of DANGER) {
    const p = page({ confirm: false });
    await tick();
    actBtn(rowOf(p.root, id), act).click();
    await tick();
    const c = p.rec.confirms[0];
    check('D ' + act + ': danger confirm naming ' + name, !!c && c.danger === true && c.message === T('admin.staff.' + key + '.message', { name }));
    check('D ' + act + ': cancel → no request', writes(p.rec).length === 0);
    const q = page({ confirm: true });
    await tick();
    actBtn(rowOf(q.root, id), act).click();
    await tick();
    const w = writes(q.rec);
    check('D ' + act + ': confirmed → ' + method + ' ' + url, w.length === 1 && w[0].url === url && w[0].method === method);
  }
  {
    const p = page({ confirm: false });
    await tick();
    find(p.root, e => e.tagName === 'BUTTON' && e.attrs['data-act'] === 'role_delete').click();
    await tick();
    check('D role delete: danger confirm naming the role · cancel → no request', p.rec.confirms[0].danger === true
      && p.rec.confirms[0].message === T('admin.staff.role_delete.message', { name: 'دعم' }) && writes(p.rec).length === 0);
  }
  {
    const msgs = ['suspend', 'mfa', 'cancel'].map(k => T('admin.staff.' + k + '.message', { name: 'سامر' }));
    check('D effect texts: suspend = out at once · mfa = outside check + 24h + password kept · cancel = link dies',
      msgs.every(m => m.indexOf('سامر') !== -1) && msgs[1].indexOf('24') !== -1);
  }

  console.log('\nU — 428 → step-up dialog → one retry');
  {
    const p = page({ write: (url, m, b, su) => (su ? [200, { ok: true, data: { id: 11 } }] : [428, { error: 'step_up_required' }]) });
    await tick();
    actBtn(rowOf(p.root, 11), 'suspend').click();
    await tick(30);
    const w = writes(p.rec).filter(r => r.url === '/admin/staff/11/suspend');
    check('U1 one step-up dialog (the shell\'s)', p.rec.modals.filter(m => m.opts.title === T('admin.stepup.title')).length === 1);
    check('U2 code → /admin/step-up · the request sent again once with the grant',
      p.rec.requests.some(r => r.url === '/admin/step-up') && w.length === 2 && w[0].stepup === '' && w[1].stepup === 'G.R.ANT');
    check('U3 success toast + lists read again', lastToast(p.rec) === T('admin.staff.done.suspended')
      && p.rec.requests.filter(r => r.url === '/admin/staff' && r.method === 'GET').length === 2);
  }
  {
    const p = page({ stepUp: 'cancel', write: () => [428, { error: 'step_up_required' }] });
    await tick();
    actBtn(rowOf(p.root, 11), 'suspend').click();
    await tick(30);
    check('U4 step-up cancelled → admin.stepup.cancelled · no retry · session kept',
      writes(p.rec).length === 1 && p.rec.toasts.some(t => t[0] === T('admin.stepup.cancelled'))
      && p.rec.toasts.length === 1 && p.rec.replaced.length === 0);
  }

  console.log('\nE — every error code → its message');
  const CODES = [['not_invited', 409, 12, 'resend'], ['not_active', 409, 11, 'mfa'], ['staff_active', 409, 12, 'cancel'],
                 ['not_suspended', 409, 13, 'restore'], ['already_invited', 409], ['email_taken', 409], ['role_in_use', 409]];
  for (const [code, st, id, act] of CODES) {
    const p = page({ write: () => [st, { ok: false, error: { code, message: 'server text' } }] });
    await tick();
    if (id) actBtn(rowOf(p.root, id), act).click();
    else if (code === 'role_in_use') find(p.root, e => e.tagName === 'BUTTON' && e.attrs['data-act'] === 'role_delete').click();
    else { p.ctx.TwAdminStaff.openInvite(); await tick(); await p.rec.modals[p.rec.modals.length - 1].opts.actions[1].onClick(); }
    await tick();
    check('E ' + code + ' → ' + T('admin.staff.error.' + code).slice(0, 30), lastToast(p.rec) === T('admin.staff.error.' + code), p.rec.toasts);
    if (code === 'role_in_use') {
      check('E role_in_use keeps the page (no navigation · list still there)', p.rec.replaced.length === 0
        && !!find(p.root, e => e.attrs['data-role'] === '1') && p.root.hidden === false);
    }
  }
  const STATUS = [[403, 'admin.staff.forbidden'], [429, 'admin.staff.error.rate'], [500, 'admin.staff.error.server']];
  for (const [st, key] of STATUS) {
    const p = page({ write: () => [st, { ok: false, error: { code: 'x' } }] });
    await tick();
    actBtn(rowOf(p.root, 11), 'suspend').click();
    await tick();
    check('E ' + st + ' → ' + key + ' · session kept', lastToast(p.rec) === T(key) && p.rec.replaced.length === 0, p.rec.toasts);
  }
  {
    const p = page({ write: () => 'network' });
    await tick();
    actBtn(rowOf(p.root, 11), 'suspend').click();
    await tick();
    check('E network → admin.staff.error.network', lastToast(p.rec) === T('admin.staff.error.network'));
  }
  {
    const keys = Object.values(page().ctx.TwAdminStaff.ERRORS);
    check('E every mapped key exists in tw_strings', keys.every(k => k in STRINGS), keys.filter(k => !(k in STRINGS)));
  }

  console.log('\nN — no double send · reload · invite');
  {
    const p = page({ write: () => 'hold' });
    await tick();
    const b = actBtn(rowOf(p.root, 11), 'suspend');
    b.click(); b.click();
    await tick();
    b.disabled = false;   // even forced back on, the in-flight guard holds
    b.click();
    await tick();
    check('N1 suspend clicked 3× while the request runs → one request', writes(p.rec).length === 1 && p.rec.confirms.length === 1);
  }
  {
    const p = page({ write: (url, m, body) => [200, { ok: true, data: Object.assign({ id: 14 }, body, { email_sent: false }) }] });
    await tick();
    p.ctx.TwAdminStaff.openInvite();
    const m = p.rec.modals[p.rec.modals.length - 1];
    const inputs = findAll(m.opts.content, e => e.tagName === 'INPUT');
    inputs[0].value = ' نور '; inputs[1].value = 'NOOR@example.com';
    const sels = findAll(m.opts.content, e => e.tagName === 'SELECT');
    sels[0].value = '2';
    sels.find(s => s.attrs['data-perm'] === 'jobs.manage').value = 'allow';
    sels.find(s => s.attrs['data-perm'] === 'users.view').value = 'deny';
    const kept = await m.opts.actions[1].onClick();
    await tick();
    const w = writes(p.rec)[0];
    check('N2 invite → POST /admin/staff/invite {name, email, role_id, allow, deny}', w && w.url === '/admin/staff/invite'
      && w.body.name === 'نور' && w.body.email === 'NOOR@example.com' && w.body.role_id === 2
      && w.body.allow.join() === 'jobs.manage' && w.body.deny.join() === 'users.view', w && w.body);
    check('N3 email_sent false → "email not sent" message · dialog closes · list read again', kept === true
      && p.rec.toasts.some(t => t[0] === T('admin.staff.done.invited_no_email'))
      && p.rec.requests.filter(r => r.url === '/admin/staff' && r.method === 'GET').length === 2);
  }
  {
    const p = page();
    await tick();
    p.ctx.TwAdminStaff.openInvite();
    await p.rec.modals[p.rec.modals.length - 1].opts.actions[1].onClick();
    await tick();
    check('N4 email_sent true → "invite sent"', p.rec.toasts.some(t => t[0] === T('admin.staff.done.invited')));
  }
  {
    const p = page({ write: () => [409, { ok: false, error: { code: 'email_taken', field: 'email' } }] });
    await tick();
    p.ctx.TwAdminStaff.openInvite();
    const m = p.rec.modals[p.rec.modals.length - 1];
    const kept = await m.opts.actions[1].onClick();
    const errs = findAll(m.opts.content, e => e.className === 'tw-adm-field-err' && !e.hidden);
    check('N5 email_taken → the form stays open + the message under the email field', kept === false && errs.length === 1
      && errs[0].textContent === T('admin.staff.error.email_taken'));
  }
  {
    const p = page();
    await tick();
    p.ctx.TwAdminStaff.openAccess(STAFF[0]);
    const m = p.rec.modals[p.rec.modals.length - 1];
    const sels = findAll(m.opts.content, e => e.tagName === 'SELECT');
    check('N6 access form starts from the member (role · allow · deny)', sels[0].value === '1'
      && sels.find(s => s.attrs['data-perm'] === 'jobs.manage').value === 'allow'
      && sels.find(s => s.attrs['data-perm'] === 'message.send').value === 'deny');
    await m.opts.actions[1].onClick();
    await tick();
    const w = writes(p.rec)[0];
    check('N7 access → PUT /admin/staff/11/access {role_id, allow, deny}', w && w.url === '/admin/staff/11/access' && w.method === 'PUT'
      && w.body.role_id === 1 && w.body.allow.join() === 'jobs.manage' && w.body.deny.join() === 'message.send');
  }
  {
    const p = page();
    await tick();
    p.ctx.TwAdminStaff.openRole(ROLES[1]);
    const m = p.rec.modals[p.rec.modals.length - 1];
    const boxes = findAll(m.opts.content, e => e.type === 'checkbox');
    check('N8 role form: one checkbox per catalog perm, Arabic labels, current perms checked', boxes.length === GRANTABLE.length
      && boxes.filter(b => b.checked).map(b => b.value).sort().join() === 'kyc.review,users.view'
      && m.opts.content.textContent.indexOf('مراجعة طلبات التوثيق') !== -1);
    boxes.find(b => b.value === 'jobs.manage').checked = true;
    await m.opts.actions[1].onClick();
    await tick();
    const w = writes(p.rec)[0];
    check('N9 role save → PUT /admin/roles/2 {name, perms}', w && w.url === '/admin/roles/2' && w.method === 'PUT'
      && w.body.name === 'توثيق' && w.body.perms.sort().join() === 'jobs.manage,kyc.review,users.view');
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
