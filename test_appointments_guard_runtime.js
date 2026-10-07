/**
 * test_appointments_guard_runtime.js — Phase C: appointments + appointment-room + twRequireAuth
 * Runs the REAL tw_shared.js + auth-sync.js in Node vm contexts, plus static checks on both pages.
 *   A  twRequireAuth — every snapshot state · ?next= (path + query) · wrong account type
 *   B  twRequireAuth + TwAuthSync.onSessionChange — logout in another tab · account switch ·
 *      bfcache restore of the same account · one registration only
 *   C  both pages — Page Shell markers · <meta name="tw-page" content="auth"> + one guard call ·
 *      no direct tw_user / tw_jwt · no alert() / emoji / inline SVG · DS-ICON names in the registry ·
 *      DS-IMAGE avatars · no local :root shadowing of shared tokens
 *
 * Run: node test_appointments_guard_runtime.js
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

function b64url(obj) {
  return Buffer.from(JSON.stringify(obj)).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
const now = Math.floor(Date.now() / 1000);
const EMP = { id: 7, tw_id: 'U9620abcdef1234', user_type: 'emp' };
const CO  = { id: 8, tw_id: 'C9620abcdef5678', user_type: 'co' };
const jwtFor = (u, exp) => b64url({ alg: 'HS256' }) + '.'
  + b64url({ user_id: u.id, user_type: u.user_type, exp: exp }) + '.sig';
const session = (u, exp) => ({ tw_user: JSON.stringify(u), tw_jwt: jwtFor(u, exp || now + 3600) });

// Protected page context: tw_shared.js → auth-sync.js (the Page Shell order); page = /appointment-room?id=5
function page(store, opts) {
  opts = opts || {};
  const nav = { replaced: [], reloads: 0 };
  const listeners = {};
  const on = (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); };
  const doc = {
    visibilityState: 'visible', addEventListener: on,
    getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, classList: { add: noop } }),
    body: { appendChild: noop, classList: { add: noop } }, documentElement: { style: {} },
  };
  const ctx = {
    localStorage: {
      getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
      setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; },
    },
    document: doc, console, URLSearchParams, encodeURIComponent,
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: () => 0, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    navigator: { userAgent: 'node' },
  };
  ctx.window = ctx;
  ctx.addEventListener = on;
  ctx.location = {
    protocol: 'http:', host: 'x', pathname: '/appointment-room', search: '?id=5', hash: '',
    replace: u => { nav.replaced.push(u); }, reload: () => { nav.reloads++; },
  };
  vm.createContext(ctx);
  const files = opts.noSync ? ['tw_shared.js'] : ['tw_shared.js', 'static/shared/auth-sync.js'];
  files.forEach(f => vm.runInContext(read(f), ctx, { filename: f }));
  const fire = (t, ev) => (listeners[t] || []).forEach(fn => fn(ev || {}));
  return { ctx, nav, store, fire };
}

const NEXT = '/login?next=' + encodeURIComponent('/appointment-room?id=5');

console.log('\nA — twRequireAuth: snapshot states');
{
  const p = page(session(EMP));
  const snap = p.ctx.twRequireAuth();
  check('A1 authenticated → snapshot returned, no navigation',
    snap && snap.isAuthenticated === true && snap.userId === 7 && p.nav.replaced.length === 0);
}
const STATES = [
  ['guest (no session)', {}],
  ['stale (tw_user without tw_jwt)', { tw_user: JSON.stringify(EMP) }],
  ['invalid (malformed jwt)', { tw_user: JSON.stringify(EMP), tw_jwt: 'not.a-jwt' }],
  ['expired (exp in the past)', session(EMP, now - 60)],
  ['stale (tw_user of another account)', { tw_user: JSON.stringify(CO), tw_jwt: jwtFor(EMP, now + 3600) }],
];
STATES.forEach(([name, store], i) => {
  const p = page(store);
  const snap = p.ctx.twRequireAuth();
  check('A2.' + i + ' ' + name + ' → null + location.replace(/login?next=path+query)',
    snap === null && p.nav.replaced.length === 1 && p.nav.replaced[0] === NEXT, JSON.stringify(p.nav.replaced));
});
{
  const p = page(session(EMP), { noSync: true });
  check('A3 TwAuthSync missing → fail closed (/login?next=)',
    p.ctx.twRequireAuth() === null && p.nav.replaced[0] === NEXT);
}
{
  const p = page(session(EMP));
  check('A4 wrong account type (userTypes [co], emp) → twAccountHref, not /login',
    p.ctx.twRequireAuth({ userTypes: ['co'] }) === null && p.nav.replaced[0] === '/u/' + EMP.tw_id,
    JSON.stringify(p.nav.replaced));
  const q = page(session(CO));
  check('A5 allowed account type → snapshot', q.ctx.twRequireAuth({ userTypes: ['co'] }).userType === 'co'
    && q.nav.replaced.length === 0);
}
{
  const p = page(session(EMP));
  p.ctx.location.search = '?id=5&x=//evil.com';
  p.ctx.localStorage.removeItem('tw_jwt');
  p.ctx.twRequireAuth();
  check('A6 next keeps the query, encoded (one internal path)',
    p.nav.replaced[0] === '/login?next=' + encodeURIComponent('/appointment-room?id=5&x=//evil.com'));
}

console.log('\nB — twRequireAuth + TwAuthSync.onSessionChange');
{
  const p = page(session(EMP));
  p.ctx.twRequireAuth();
  p.ctx.twRequireAuth();                                  // second call — no second registration
  delete p.store.tw_jwt; delete p.store.tw_user;          // logout in another tab
  p.fire('storage', { key: 'tw_jwt' });
  check('B1 logout in another tab → one location.replace(/login?next=)',
    p.nav.replaced.length === 1 && p.nav.replaced[0] === NEXT, JSON.stringify(p.nav.replaced));
  p.fire('storage', { key: 'tw_user' });
  check('B2 later events after leaving → no second navigation', p.nav.replaced.length === 1);
}
{
  const p = page(session(EMP));
  p.ctx.twRequireAuth();
  Object.assign(p.store, session({ id: 9, tw_id: 'U9620zzzz', user_type: 'emp' }));
  p.fire('storage', { key: 'tw_jwt' });
  check('B3 another account signed in (same type) → reload, no /login',
    p.nav.reloads === 1 && p.nav.replaced.length === 0);
}
{
  const p = page(session(EMP));
  p.ctx.twRequireAuth({ userTypes: ['emp'] });
  Object.assign(p.store, session(CO));
  p.fire('storage', { key: 'tw_jwt' });
  check('B4 switch to a type not allowed → twAccountHref of the new account',
    p.nav.replaced[0] === '/u/' + CO.tw_id && p.nav.reloads === 0, JSON.stringify(p.nav.replaced));
}
{
  const p = page(session(EMP));
  p.ctx.twRequireAuth();
  p.fire('pageshow', { persisted: true });               // bfcache restore, same account (VM-01 path)
  check('B5 bfcache restore of the same account → stays (no navigation)',
    p.nav.replaced.length === 0 && p.nav.reloads === 0);
  p.ctx.localStorage.setItem('tw_jwt', jwtFor(EMP, now - 5));
  p.fire('pageshow', { persisted: true });
  check('B6 bfcache restore with an expired token → /login?next=', p.nav.replaced[0] === NEXT);
}
{
  const p = page({});
  p.ctx.twRequireAuth();
  check('B7 no listener registered when the page is left on load', p.ctx._twGuardBound === false);
}
{
  const src = read('tw_shared.js');
  const fn = src.slice(src.indexOf('function _twGuardDestination'), src.indexOf('window.twRequireAuth'));
  check('B8 guard never reads tw_user / tw_jwt directly', !/localStorage|tw_jwt|'tw_user'/.test(fn));
  check('B9 guard has no own pageshow / storage listener (VM-01)', !/addEventListener/.test(fn));
}

console.log('\nC — appointments.html + appointment-room.html');
const REG = read('static/shared/tw-icons.js');
const regNames = new Set([...REG.matchAll(/^\s+'([a-z0-9-]+)': \[[01],/gm)].map(m => m[1]));
const sharedRoot = new Set([...read('tw_shared.css').matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map(m => m[1]));
['appointments.html', 'appointment-room.html'].forEach(f => {
  const raw = read(f);
  const js = raw.slice(raw.lastIndexOf('<script>'), raw.lastIndexOf('</script>'));
  const code = js.replace(/^\s*\/\/.*$/gm, '');
  const tag = f.replace('.html', '');
  check(tag + ' C1 shell markers once, head marker first after <head>',
    raw.includes('<head>\n<!--tw:shell-head-->') && raw.split('<!--tw:shell-head-->').length === 2
    && raw.split('<!--tw:shell-scripts-->').length === 2);
  check(tag + ' C2 no shell-owned tags by hand (charset / viewport / fonts / tw_shared / auth-sync)',
    !/charset=|name="viewport"|fonts\.g|(?:src|href)="[^"]*(?:tw_shared|auth-sync)|apple-mobile|theme-color|rel="manifest"/.test(raw));
  check(tag + ' C3 <meta name="tw-page" content="auth">', raw.split('<meta name="tw-page" content="auth">').length === 2);
  check(tag + ' C4 exactly one twRequireAuth() call, before any api()/fetch',
    code.split('twRequireAuth(').length === 2 && code.indexOf('twRequireAuth(') < code.indexOf('fetch('));
  check(tag + ' C5 no direct tw_user / tw_jwt / localStorage / Bearer', !/localStorage|tw_jwt|tw_user|Bearer/.test(raw));
  check(tag + ' C6 fetch headers via getAuthHeaders', /headers: getAuthHeaders\(true\)/.test(code));
  check(tag + ' C7 no alert() / prompt()', !/\balert\(|\bprompt\(/.test(code));
  check(tag + ' C8 no inline <svg> / emoji', !/<svg|[\u{1F300}-\u{1FAFF}☀-➿]/u.test(raw));
  check(tag + ' C9 tw-icons.js via {{v:tw-icons.js}} after the shell scripts',
    raw.indexOf('<!--tw:shell-scripts-->') < raw.indexOf('/static/shared/tw-icons.js?v={{v:tw-icons.js}}'));
  const names = [...raw.matchAll(/data-tw-icon="([a-z0-9-]+)"/g), ...raw.matchAll(/twIcon(?:El)?\('([a-z0-9-]+)'/g),
                 ...raw.matchAll(/actBtn\('[a-z-]+', '([a-z0-9-]+)'/g), ...raw.matchAll(/(?:metaItem|stateBox|addMeta)\('([a-z0-9-]+)'/g)]
    .map(m => m[1]);
  const bad = names.filter(n => !regNames.has(n));
  check(tag + ' C10 every icon name is in the DS-ICON registry (' + names.length + ')', names.length > 3 && !bad.length, bad);
  check(tag + ' C11 avatar via twAvatarEl (DS-IMAGE), no local initials()', /twAvatarEl\(/.test(code) && !/function initials/.test(code));
  const rootBlock = (raw.match(/:root\{([\s\S]*?)\}/) || [])[1] || '';
  const local = [...rootBlock.matchAll(/(--[a-z0-9-]+)\s*:/g)].map(m => m[1]);
  const shadow = local.filter(n => sharedRoot.has(n));
  check(tag + ' C12 local :root shadows no shared token', !shadow.length, shadow);
  check(tag + ' C13 no back button via history.back()', !/history\.back\(/.test(code));
});
{
  const room = read('appointment-room.html');
  check('room C14 confirm() kept as-is (3 — no shared confirmation system yet, F30)',
    (room.match(/\bconfirm\(/g) || []).length === 3);
  check('room C15 participant avatar uses the room photo fields',
    /avatar_url: appt\.applicant_avatar/.test(room) && /avatar_url: appt\.company_avatar/.test(room));
  check('room C16 no WebSocket of its own (badge WS in tw_shared.js is the only socket)', !/WebSocket/.test(room));
}
{
  const htmls = fs.readdirSync('.').filter(f => f.endsWith('.html'));
  const guarded = htmls.filter(f => read(f).includes('<meta name="tw-page" content="auth">'));
  const missing = guarded.filter(f => !read(f).includes('twRequireAuth('));
  check('C17 every <meta tw-page=auth> page calls twRequireAuth', guarded.length >= 2 && !missing.length, missing);
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
