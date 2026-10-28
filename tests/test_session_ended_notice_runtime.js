/**
 * test_session_ended_notice_runtime.js — task 8.3b: one «انتهت الجلسة» notice when the session
 * ends on the server / expires. REAL tw_shared.js + auth-sync.js in Node vm (Page Shell order).
 *   A  3 parallel 401 (twApi) → guest at once · ONE twModal · twRequireAuth does not leave first
 *   B  «موافق» / Escape → location.replace('/login?next=<path+query>')
 *   C  logout → no notice, no mark · admin_email_change → no notice
 *   D  other tab: tw_session_ended mark + wipe → same notice · plain logout wipe → no notice
 *   E  jwt_expired / ws_revoked → notice · /login page → no notice · toast silent while it is up
 * Run: node tests/test_session_ended_notice_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}
const noop = () => {};
const b64url = o => Buffer.from(JSON.stringify(o)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const now = Math.floor(Date.now() / 1000);
const EMP = { id: 7, tw_id: 'U9620abcdef1234', user_type: 'emp' };
const JWT = b64url({ alg: 'HS256' }) + '.' + b64url({ user_id: 7, user_type: 'emp', exp: now + 3600 }) + '.sig';
const session = () => ({ tw_user: JSON.stringify(EMP), tw_jwt: JWT });
const STRINGS = { dict: JSON.parse(fs.readFileSync('tw_strings.json', 'utf8')).ar };
const NEXT = '/login?next=' + encodeURIComponent('/appointments?tab=2');

function page(store, opts) {
  opts = opts || {};
  const nav = { replaced: [], href: [] };
  const modals = [], sets = [], appended = [];
  const listeners = {};
  const on = (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); };
  const doc = {
    visibilityState: 'visible', addEventListener: on,
    getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, classList: { add: noop } }),
    body: { appendChild: el => appended.push(el), classList: { add: noop } }, documentElement: { style: {} },
  };
  const ctx = {
    localStorage: {
      getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
      setItem: (k, v) => { sets.push(k); store[k] = String(v); }, removeItem: k => { delete store[k]; },
    },
    document: doc, console, URLSearchParams, encodeURIComponent, Promise,
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: () => 0, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    navigator: { userAgent: 'node' },
    fetch: () => Promise.resolve({ status: 401, ok: false, text: () => Promise.resolve('{"detail":"x"}') }),
    TW_STRINGS: STRINGS,
    twModal: o => { modals.push(o); return { close: noop }; },
  };
  ctx.window = ctx;
  ctx.addEventListener = on;
  const loc = { protocol: 'http:', host: 'x', pathname: opts.path || '/appointments', search: opts.path ? '' : '?tab=2', hash: '',
    replace: u => { nav.replaced.push(u); }, reload: noop };
  Object.defineProperty(loc, 'href', { set: u => nav.href.push(u), get: () => '' });
  ctx.location = loc;
  vm.createContext(ctx);
  ['tw_shared.js', 'static/shared/auth-sync.js'].forEach(f => vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f }));
  const fire = (t, ev) => (listeners[t] || []).forEach(fn => fn(ev || {}));
  fire('DOMContentLoaded');
  return { ctx, nav, modals, sets, appended, fire };
}
const tick = () => new Promise(r => setImmediate(r));

(async () => {
  console.log('\nA — parallel 401s → one notice, guest at once, guard waits');
  {
    const store = session();
    const p = page(store);
    check('A0 guard returns the snapshot', !!p.ctx.twRequireAuth());
    await Promise.all([p.ctx.twApi('/a'), p.ctx.twApi('/b'), p.ctx.twApi('/c')]);
    await tick();
    check('A1 session wiped at once (guest)', store.tw_jwt === undefined && store.tw_user === undefined
      && p.ctx.TwAuthSync.getSessionSnapshot().state === 'guest');
    check('A2 exactly one twModal', p.modals.length === 1, p.modals.length);
    const m = p.modals[0] || {};
    check('A3 text session.ended.message + one «common.ok» button',
      m.message === STRINGS.dict['session.ended.message'] && !!STRINGS.dict['common.ok']
      && (m.actions || []).length === 1 && m.actions[0].text === STRINGS.dict['common.ok']);
    check('A4 twRequireAuth did not redirect before the click', p.nav.replaced.length === 0, p.nav.replaced);
    check('A5 mark written next to the wipe, then removed', p.sets.indexOf('tw_session_ended') >= 0 && store.tw_session_ended === undefined);

    console.log('\nB — «موافق» / any close → login with ?next=');
    m.onClose && m.onClose('action');
    check('B1 موافق → /login?next=<path+query>', p.nav.replaced.length === 1 && p.nav.replaced[0] === NEXT, p.nav.replaced);
    const p2 = page(session());
    p2.ctx.twRequireAuth();
    p2.ctx.TwAuthSync.invalidateSession('api_401');
    p2.modals[0] && p2.modals[0].onClose('escape');
    check('B2 Escape / backdrop → same destination', p2.nav.replaced.join() === NEXT, p2.nav.replaced);
  }

  console.log('\nC — logout / admin_email_change → no notice');
  {
    const store = session();
    const p = page(store);
    p.ctx.twRequireAuth();
    p.ctx.twLogout();
    check('C1 logout → no twModal', p.modals.length === 0);
    check('C2 logout → no tw_session_ended mark', p.sets.indexOf('tw_session_ended') === -1);
    check('C3 logout → /login as before', p.nav.href.indexOf('/login') >= 0, p.nav.href);
    const q = page(session(), { path: '/confirm-email' });
    q.ctx.TwAuthSync.invalidateSession('admin_email_change');
    check('C4 admin_email_change → no twModal', q.modals.length === 0);
  }

  console.log('\nD — other tabs (storage event)');
  {
    const store = session();
    const p = page(store);
    p.ctx.twRequireAuth();
    const ts = String(Date.now());
    store.tw_session_ended = ts;
    p.fire('storage', { key: 'tw_session_ended', newValue: ts });
    delete store.tw_jwt;   p.fire('storage', { key: 'tw_jwt', newValue: null });
    delete store.tw_user;  p.fire('storage', { key: 'tw_user', newValue: null });
    delete store.tw_session_ended; p.fire('storage', { key: 'tw_session_ended', newValue: null });
    check('D1 mark + wipe in another tab → one twModal', p.modals.length === 1, p.modals.length);
    check('D2 no redirect before the click', p.nav.replaced.length === 0, p.nav.replaced);

    const s2 = session();
    const q = page(s2);
    q.ctx.twRequireAuth();
    delete s2.tw_jwt;  q.fire('storage', { key: 'tw_jwt', newValue: null });
    check('D3 logout in another tab (no mark) → no twModal, guard redirects as before',
      q.modals.length === 0 && q.nav.replaced.length === 1, q.nav.replaced);

    const s3 = session();
    const r = page(s3);
    r.fire('storage', { key: 'tw_session_ended', newValue: String(Date.now() - 120000) });
    delete s3.tw_jwt;  r.fire('storage', { key: 'tw_jwt', newValue: null });
    check('D4 mark older than a minute → ignored', r.modals.length === 0);
  }

  console.log('\nE — other reasons · /login · toast');
  {
    const a = page(session());
    a.ctx.TwAuthSync.invalidateSession('jwt_expired');
    check('E1 jwt_expired → notice', a.modals.length === 1);
    const b = page(session());
    b.ctx.TwAuthSync.invalidateSession('ws_revoked');
    check('E2 ws_revoked → notice', b.modals.length === 1);
    const c = page(session(), { path: '/login' });
    c.ctx.TwAuthSync.invalidateSession('api_401');
    check('E3 /login page → no notice', c.modals.length === 0);
    const d = page({});
    d.ctx.TwAuthSync.invalidateSession('api_401');
    check('E4 guest from the start → no notice', d.modals.length === 0);
    const before = b.appended.length;
    b.ctx.showToast('x', 'error');
    check('E5 toast silent while the notice is up', b.appended.length === before);
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
