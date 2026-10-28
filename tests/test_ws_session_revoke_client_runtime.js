/**
 * test_ws_session_revoke_client_runtime.js — WS Session Revocation, client side (PR 4.0).
 * REAL code in Node vm: tw_shared.js badge WS (@vm-extract badge-ws) + messages.ws.js.
 * Same device changes its password → server closes the socket with 4008 — the reply with the
 * new JWT may land before OR after that close:
 *   1  new JWT already stored when 4008 arrives → reconnect at once, auth frame = new JWT
 *   2  4008 first, the new JWT lands within the 2s (TwAuthSync.renewToken) → reconnect with the
 *      new JWT, never with the revoked one (no 4001) · no logout (no invalidateSession)
 *   3  4008 and still the same JWT after 2s (session ended on the server — task 8.3b) →
 *      TwAuthSync.invalidateSession('ws_revoked') once · no reconnect
 * Run: node tests/test_ws_session_revoke_client_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, extra) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else { failed++; console.log('  FAIL  ' + name + (extra !== undefined ? ' — ' + JSON.stringify(extra) : '')); }
}
function extract(src, key) {
  const b = '// @vm-extract-begin: ' + key, e = '// @vm-extract-end: ' + key;
  const si = src.indexOf(b), ei = src.indexOf(e, si);
  if (si < 0 || ei < 0) throw new Error('marker not found: ' + key);
  return src.slice(si, ei + e.length);
}
function mkStorage(init) {
  const m = new Map(Object.entries(init || {}));
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) };
}
function mkTimers() {
  let id = 0; const q = new Map();
  return {
    setTimeout: f => { q.set(++id, f); return id; },
    clearTimeout: h => q.delete(h),
    runAll() { const fns = [...q.values()]; q.clear(); fns.forEach(f => f()); },
  };
}
function mkWsClass(log) {
  function WS(url) { this.url = url; this.readyState = 0; this.sent = []; log.push(this); }
  WS.prototype.send = function (d) { this.sent.push(JSON.parse(d)); };
  WS.prototype.close = function () { this.readyState = 3; };
  return WS;
}
// open → auth frame → auth_ok; returns the token the socket sent
function openSocket(ws, uid) {
  ws.readyState = 1; ws.onopen();
  ws.onmessage({ data: JSON.stringify({ type: 'auth_ok', user_id: uid }) });
  return (ws.sent[0] || {}).token;
}
function serverRevoke(ws) { ws.readyState = 3; ws.onclose({ code: 4008 }); }

const UID = 42, OLD = 'jwt-old', NEW = 'jwt-new';
const SNAP = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: UID };

// Shared fake TwAuthSync: renewToken writes tw_jwt + fires token_renewed like auth-sync.js
function mkAuth(store) {
  const a = { handlers: [], invalidations: [] };
  a.api = {
    onSessionChange: f => a.handlers.push(f),
    getSessionSnapshot: () => SNAP,
    getToken: () => store.getItem('tw_jwt') || '',
    invalidateSession: reason => { a.invalidations.push(reason); },
    renewToken: jwt => { store.setItem('tw_jwt', jwt); a.handlers.forEach(h => h({ jwt, reason: 'token_renewed', snapshot: SNAP })); return true; },
  };
  return a;
}

function loadBadge() {
  const store = mkStorage({ tw_jwt: OLD }), timers = mkTimers(), sockets = [], auth = mkAuth(store);
  const win = { location: { protocol: 'https:', host: 'x' }, addEventListener() {} };
  const ctx = vm.createContext({
    window: win, localStorage: store, WebSocket: mkWsClass(sockets), TwAuthSync: auth.api,
    document: { querySelectorAll: () => [], querySelector: () => null },
    setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout, JSON, Math, Number,
    _badgeGeneration: 0, loadGlobalBadges: () => {}, twNotifBadgeLabel: n => String(n),
  });
  vm.runInContext(extract(fs.readFileSync('./tw_shared.js', 'utf8'), 'badge-ws'), ctx);
  win._twBadgeWsStart();
  return { store, timers, sockets, auth };
}

function loadMessages() {
  const store = mkStorage({ tw_jwt: OLD }), timers = mkTimers(), sockets = [], auth = mkAuth(store);
  const loc = { protocol: 'https:', host: 'x' };
  const ctx = vm.createContext({
    WebSocket: mkWsClass(sockets), setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout,
    localStorage: store, JSON, Number, Math, TwAuthSync: auth.api,
    document: { hidden: false, getElementById: () => null },
  });
  ctx.window = { location: loc }; ctx.location = loc;
  vm.runInContext('var _user = {id:' + UID + '}; var _jwt = ' + JSON.stringify(OLD) + '; var _currentConvId = null; var _typingHideTimer = null;', ctx);
  vm.runInContext(fs.readFileSync('./messages.ws.js', 'utf8'), ctx);
  vm.runInContext('connectWS()', ctx);
  return { store, timers, sockets, auth };
}

for (const [name, load] of [['badge WS (tw_shared.js)', loadBadge], ['conversation WS (messages.ws.js)', loadMessages]]) {
  console.log('\n' + name);

  // 1 — reply with the new JWT stored before the 4008 close
  let t = load();
  check('1a connected with the old JWT', openSocket(t.sockets[0], UID) === OLD);
  t.store.setItem('tw_jwt', NEW);
  serverRevoke(t.sockets[0]);
  check('1b 4008 + new JWT stored → reconnect at once', t.sockets.length === 2, t.sockets.length);
  check('1c the new socket authenticates with the new JWT', openSocket(t.sockets[1], UID) === NEW);

  // 2 — 4008 first, the new JWT lands inside the 2s window (same device changed its password)
  t = load();
  openSocket(t.sockets[0], UID);
  serverRevoke(t.sockets[0]);
  check('2a 4008 before the reply → no immediate reconnect', t.sockets.length === 1);
  t.auth.api.renewToken(NEW);   // settings.js: PUT /auth/password reply → TwAuthSync.renewToken
  t.timers.runAll();
  const tokens = t.sockets.slice(1).map(s => openSocket(s, UID));
  check('2b token renewed → reconnect, every new auth frame = new JWT', tokens.length >= 1 && tokens.every(x => x === NEW), tokens);
  check('2c no logout (invalidateSession never called)', t.auth.invalidations.length === 0, t.auth.invalidations);

  // 3 — 4008 and no new JWT after 2s → the session ended on the server
  t = load();
  openSocket(t.sockets[0], UID);
  serverRevoke(t.sockets[0]);
  check('3a no invalidation before the 2s second look', t.auth.invalidations.length === 0);
  t.timers.runAll();
  check("3b still the same JWT after 2s → invalidateSession('ws_revoked') once",
    t.auth.invalidations.length === 1 && t.auth.invalidations[0] === 'ws_revoked', t.auth.invalidations);
  check('3c no reconnect with the revoked JWT', t.sockets.length === 1, t.sockets.length);
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
