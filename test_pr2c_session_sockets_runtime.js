// test_pr2c_session_sockets_runtime.js — PR 2C focused runtime tests
// Runs REAL production code via Node.js vm (+ @vm-extract markers where needed):
//   auth-sync.js (focus/visibility no longer force) · tw_shared.js badge WS ·
//   messages.ws.js session handler · messages.render.js poll controller ·
//   company.main.js suggestion save delegation · company.jobs.js job location mode.
// Run: node test_pr2c_session_sockets_runtime.js
'use strict';

const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function assert(label, cond) {
  if (cond) { console.log('  ✅ PASS:', label); passed++; }
  else      { console.error('  ❌ FAIL:', label); failed++; }
}
function extract(src, key) {
  const b = '// @vm-extract-begin: ' + key, e = '// @vm-extract-end: ' + key;
  const si = src.indexOf(b), ei = src.indexOf(e, si);
  if (si < 0 || ei < 0) throw new Error('marker not found: ' + key);
  return src.slice(si, ei + e.length);
}
function b64url(o) { return Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_'); }
function jwtFor(uid, type, exp) { return 'h.' + b64url({ user_id: uid, user_type: type, exp: exp }) + '.s'; }
function mkStorage(init) {
  const m = new Map(Object.entries(init || {}));
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) };
}
function mkTarget() {
  const ls = {};
  return {
    addEventListener(t, f) { (ls[t] = ls[t] || []).push(f); },
    fire(t, ev) { (ls[t] || []).forEach(f => f(ev || {})); },
  };
}
// Manual timers so tests control time without real waits
function mkTimers() {
  let id = 0; const q = new Map();
  return {
    setTimeout: (f, ms) => { q.set(++id, f); return id; },
    clearTimeout: h => q.delete(h),
    setInterval: (f, ms) => { q.set(++id, f); return id; },
    clearInterval: h => q.delete(h),
    runAll() { const fs2 = [...q.values()]; q.clear(); fs2.forEach(f => f()); },
    size: () => q.size,
  };
}

const NOW = Math.floor(Date.now() / 1000);

// ════════════════════════════════════════════════════════════════════════
// 1. auth-sync.js — focus / visibilitychange only fire on a real change
// ════════════════════════════════════════════════════════════════════════
console.log('\n1. auth-sync — focus / visibility');
function loadAuthSync(store) {
  const win = mkTarget(), doc = mkTarget();
  doc.visibilityState = 'visible';
  const timers = mkTimers();
  const ctx = vm.createContext({
    localStorage: store, document: doc, atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout, Date, JSON, Math, String, isFinite, console,
  });
  ctx.window = Object.assign(win, { location: { href: '' } });
  vm.runInContext(fs.readFileSync('./static/shared/auth-sync.js', 'utf8'), ctx);
  const calls = [];
  ctx.window.TwAuthSync.onSessionChange(i => calls.push(i));
  return { ctx, win, doc, calls };
}
{
  const jwtA = jwtFor(42, 'co', NOW + 3600);
  const store = mkStorage({ tw_jwt: jwtA, tw_user: JSON.stringify({ id: 42, user_type: 'co' }) });
  const t = loadAuthSync(store);
  t.win.fire('focus'); t.doc.fire('visibilitychange');
  assert('same session: focus + visibilitychange fire no handler', t.calls.length === 0);

  // Account switch written without a storage event reaching us → focus catches it
  store.setItem('tw_jwt', jwtFor(99, 'emp', NOW + 3600));
  store.setItem('tw_user', JSON.stringify({ id: 99, user_type: 'emp' }));
  t.win.fire('focus');
  assert('user change: focus fires handler with new userId',
    t.calls.length === 1 && t.calls[0].snapshot.userId === 99 && t.calls[0].reason === 'focus');

  // Logout in another tab → storage event (unchanged path)
  store.removeItem('tw_jwt'); store.removeItem('tw_user');
  t.win.fire('storage', { key: 'tw_jwt' });
  assert('logout in other tab: storage fires guest snapshot',
    t.calls.length === 2 && t.calls[1].snapshot.state === 'guest' && t.calls[1].jwt === '');

  // bfcache restore stays forced even with an unchanged session
  t.win.fire('pageshow', { persisted: true });
  assert('bfcache pageshow still fires (forced)', t.calls.length === 3 && t.calls[2].reason === 'pageshow');
}
{
  // Expired while hidden (same JWT string) → state change → visibilitychange fires
  const jwtShort = jwtFor(42, 'co', NOW + 5);
  const store = mkStorage({ tw_jwt: jwtShort, tw_user: JSON.stringify({ id: 42, user_type: 'co' }) });
  const t = loadAuthSync(store);
  const realNow = Date.now;
  Date.now = () => realNow() + 60 * 1000;
  try { t.doc.fire('visibilitychange'); } finally { Date.now = realNow; }
  assert('expiry while hidden: visibilitychange fires expired snapshot',
    t.calls.length === 1 && t.calls[0].snapshot.state === 'expired');
}

// ════════════════════════════════════════════════════════════════════════
// Fake WebSocket shared by the socket tests
// ════════════════════════════════════════════════════════════════════════
function mkWsClass(log) {
  function WS(url) { this.url = url; this.readyState = 0; this.closed = false; log.push(this); }
  WS.prototype.send = function () {};
  WS.prototype.close = function () { this.closed = true; this.readyState = 3; };
  WS.OPEN = 1;
  return WS;
}

// ════════════════════════════════════════════════════════════════════════
// 2. tw_shared.js badge WS — same session keeps the socket
// ════════════════════════════════════════════════════════════════════════
console.log('\n2. badge WS');
{
  const src = extract(fs.readFileSync('./tw_shared.js', 'utf8'), 'badge-ws');
  const sockets = [], timers = mkTimers();
  const jwtA = jwtFor(42, 'co', NOW + 3600), jwtB = jwtFor(99, 'emp', NOW + 3600);
  let snap = { state: 'authenticated', isAuthenticated: true, userType: 'co', userId: 42 };
  let cb = null, badgeLoads = 0;
  const store = mkStorage({ tw_jwt: jwtA });
  const win = mkTarget();
  win.location = { protocol: 'https:', host: 'x' };
  const ctx = vm.createContext({
    window: win, localStorage: store, WebSocket: mkWsClass(sockets),
    TwAuthSync: { onSessionChange: f => { cb = f; }, getSessionSnapshot: () => snap },
    document: { querySelectorAll: () => [] },
    setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout, JSON, Math, Number,
    _badgeGeneration: 0, loadGlobalBadges: () => { badgeLoads++; },
  });
  vm.runInContext(src, ctx);
  win._twBadgeWsStart();
  const s1 = sockets[0]; s1.readyState = 1;
  cb({ jwt: jwtA, reason: 'pageshow', snapshot: snap });
  timers.runAll();
  assert('same JWT + user + open socket → not closed, no new socket, no badge GET',
    !s1.closed && sockets.length === 1 && badgeLoads === 0);

  store.setItem('tw_jwt', jwtB);
  snap = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 99 };
  cb({ jwt: jwtB, reason: 'storage', snapshot: snap });
  assert('user change → old socket closed', s1.closed);
  timers.runAll();
  assert('user change → reconnect for new user', sockets.length === 2 && /\/ws\/99$/.test(sockets[1].url));

  sockets[1].readyState = 3;   // really closed (retries exhausted)
  cb({ jwt: jwtB, reason: 'pageshow', snapshot: snap });
  timers.runAll();
  assert('closed socket + same session → reconnects', sockets.length === 3);
}

// ════════════════════════════════════════════════════════════════════════
// 3. messages.ws.js — conversation socket on session change
// ════════════════════════════════════════════════════════════════════════
console.log('\n3. messages conversation socket');
function loadMessagesWs(snap0) {
  const sockets = [], timers = mkTimers();
  let cb = null; const loc = { protocol: 'https:', host: 'x', reloaded: 0, replaced: '' };
  loc.reload = () => { loc.reloaded++; }; loc.replace = u => { loc.replaced = u; };
  const jwtA = jwtFor(42, 'emp', NOW + 3600);
  const ctx = vm.createContext({
    WebSocket: mkWsClass(sockets), setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout,
    localStorage: mkStorage({ tw_jwt: jwtA }), JSON, Number, Math,
    document: { hidden: false, getElementById: () => null },
    TwAuthSync: { onSessionChange: f => { cb = f; }, getSessionSnapshot: () => ctx.__snap },
  });
  ctx.window = { location: loc }; ctx.location = loc;
  vm.runInContext('var _user = {id:42}; var _jwt = ' + JSON.stringify(jwtA) + '; var _currentConvId = 7; var _typingHideTimer = null;', ctx);
  vm.runInContext(fs.readFileSync('./messages.ws.js', 'utf8'), ctx);
  ctx.__snap = snap0;
  vm.runInContext('connectWS()', ctx);
  sockets[0].readyState = 1;
  return { ctx, sockets, timers, loc, cb: i => cb(i), jwtA };
}
{
  const snap = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 42 };
  const t = loadMessagesWs(snap);
  t.cb({ jwt: t.jwtA, reason: 'pageshow', snapshot: snap });
  t.timers.runAll();
  assert('same session → conversation socket kept, no reconnect',
    !t.sockets[0].closed && t.sockets.length === 1 && t.loc.reloaded === 0);

  const snapB = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 99 };
  t.ctx.__snap = snapB;
  t.cb({ jwt: jwtFor(99, 'emp', NOW + 3600), reason: 'storage', snapshot: snapB });
  assert('user change → socket closed + page reload', t.sockets[0].closed && t.loc.reloaded === 1);
}
{
  const snap = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 42 };
  const t = loadMessagesWs(snap);
  t.ctx.__snap = { state: 'guest', isAuthenticated: false, userId: null };
  t.cb({ jwt: '', reason: 'storage', snapshot: t.ctx.__snap });
  assert('logout in other tab → socket closed + redirect /login',
    t.sockets[0].closed && t.loc.replaced === '/login');
}

// ════════════════════════════════════════════════════════════════════════
// 4. messages.render.js poll controller — no polling while hidden
// ════════════════════════════════════════════════════════════════════════
console.log('\n4. conversation polling');
{
  const src = extract(fs.readFileSync('./messages.render.js', 'utf8'), 'msg-poll');
  const timers = mkTimers();
  const ctx = vm.createContext({ document: { hidden: true }, setInterval: timers.setInterval, clearInterval: timers.clearInterval });
  vm.runInContext(src, ctx);
  vm.runInContext('_startMsgPoll()', ctx);
  assert('hidden → poll not started', timers.size() === 0);
  ctx.document.hidden = false;
  vm.runInContext('_startMsgPoll(); _startMsgPoll()', ctx);
  assert('visible → exactly one interval', timers.size() === 1);
  vm.runInContext('_stopMsgPoll()', ctx);
  assert('stop → interval cleared', timers.size() === 0);
  const rq = fs.readFileSync('./messages.render.js', 'utf8');
  assert('reloadMessagesQuiet returns while document.hidden (no GET → no read)',
    /function reloadMessagesQuiet\(\) \{[\s\S]{0,200}if \(!_currentConvId \|\| document\.hidden\) return;/.test(rq));
}

// ════════════════════════════════════════════════════════════════════════
// 5. company.main.js — one delegated save listener; popover uses TwCompanyPage
// ════════════════════════════════════════════════════════════════════════
console.log('\n5. company suggestions save + namespace');
{
  const main = fs.readFileSync('./static/company/company.main.js', 'utf8');
  const src = extract(main, 'co-sugg-save');
  const listeners = new Set();
  const body = {
    addEventListener: (t, f) => listeners.add(f),      // DOM dedupes identical listeners
    removeEventListener: (t, f) => listeners.delete(f),
  };
  let saves = 0;
  const ctx = vm.createContext({ _body: body, _saveSuggestion: () => { saves++; } });
  vm.runInContext(src, ctx);
  vm.runInContext('_wireSaveButtons(); _wireSaveButtons(); _wireSaveButtons();', ctx);   // render + 2× "عرض المزيد"
  assert('after render + load-more ×2 → one listener', listeners.size === 1);
  const btn = { disabled: false, classList: { contains: () => false } };
  listeners.forEach(f => f({ target: { closest: () => btn } }));
  assert('one click → one save request', saves === 1);
  btn.disabled = true;
  listeners.forEach(f => f({ target: { closest: () => btn } }));
  assert('disabled (in flight) button → no second request', saves === 1);
  assert('popover uses TwCompanyPage, no typeof cross-IIFE check',
    /TwCompanyPage\.openNotesPanel\(/.test(main) && /TwCompanyPage\.openApptModal\(/.test(main)
    && !/typeof _openNotesPanel/.test(main) && !/typeof _openApptModal/.test(main));
  assert('namespace created in company.state.js',
    /window\.TwCompanyPage = window\.TwCompanyPage \|\| \{\}/.test(fs.readFileSync('./static/company/company.state.js', 'utf8')));
}

// ════════════════════════════════════════════════════════════════════════
// 6. company.jobs.js — job location mode detected on edit
// ════════════════════════════════════════════════════════════════════════
console.log('\n6. job location mode');
{
  const src = extract(fs.readFileSync('./static/company/company.jobs.js', 'utf8'), 'job-loc-mode');
  const ctx = vm.createContext({ String });
  vm.runInContext(src, ctx);
  const d = (loc, p, b) => ctx._detectJobLocMode(loc, p, b);
  const prof = { country: 'الأردن', city: 'عمّان' };
  const br = [{ branch_name: 'فرع', country: 'السعودية', city: 'الرياض', district: 'العليا' }];
  assert('remote', d('عن بُعد', prof, br).mode === 'remote');
  assert('hq', d('الأردن، عمّان', prof, br).mode === 'hq');
  const r = d('السعودية، الرياض، العليا', prof, br);
  assert('branch (+ option value)', r.mode === 'branch' && r.value === 'السعودية، الرياض، العليا');
  assert('custom', d('مصر، القاهرة', prof, br).mode === 'custom');
  assert('empty → custom (nothing invented)', d('', prof, br).mode === 'custom');
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
