/**
 * WebSocket Client Lifecycle Tests
 * ==================================
 * Verifies the client-side security properties of messages.ws.js by
 * exercising the logic with mock DOM and WebSocket objects.
 * No real server required.
 *
 * 42 scenarios:
 *   T01  connectWS without _user → no socket
 *   T02  onopen sends {type:'auth',token:...} as first message
 *   T03  auth_ok with correct uid sets _wsReady = true
 *   T04  auth_ok with wrong uid closes socket
 *   T05  Messages before auth_ok are dropped
 *   T06  Messages after auth_ok are processed (badge_update)
 *   T07  onclose with code 4001 → no reconnect (_wsReconnectTimer === null)
 *   T08  onclose with code 4007 → no reconnect (_wsReconnectTimer === null)
 *   T09  onclose with code 1006 → reconnect scheduled (_wsReconnectTimer !== null)
 *  T10  Generation counter prevents stale reconnect
 *  T11  _wsReady reset to false on close
 *  T12  _wsGen increments on each connectWS call
 *  T13  Client-side auth timeout scheduled in onopen
 *  T15  Logout (empty jwt) → location.replace('/login'), no reconnect timer
 *  T16  Account switch (different userId) → window.location.reload() called
 *  T17  Account switch → no new WebSocket (page reload handles re-init)
 *  T18  isAuthenticated=false → location.replace('/login') called
 *  T19  Logout after switch → switch timer cancelled
 *  T31  5-cycle retry lifecycle → _wsRetries not reset in onopen, stops at 5
 *  T32  Auth timeout timer cleared on auth_ok
 *  T33  Auth timeout timer cleared on onclose
 *  T34  Badge WS V2 snapshot (no jwt) + localStorage JWT → socket created
 *  T35  Logout → _user/_currentConvId cleared, replace('/login') called
 *  T36  Same user + authenticated → no reload/replace, reconnect timer scheduled
 *  T37  Account switch → location.reload() called, no new WS
 *  T38  Typing throttle: 30 rapid keystrokes → exactly 1 typing event sent
 *  T39  Typing debounce: 1800ms idle → typing_stop sent, throttle cleared
 *  T40  closeConversationUI clears both _typingTimer and _typingThrottle
 *  T41  doSendMessage clears throttle timer and sends typing_stop
 *  T42  Input with no active conversation (_currentConvId=null) → no sendTyping
 *
 * Run:  node test_ws_client.mjs
 */

import vm from 'vm';
import { readFileSync } from 'fs';
import { strict as assert } from 'assert';

let PASS = 0, FAIL = 0;
function check(name, condition, detail = '') {
  if (condition) { PASS++; console.log(`  PASS  ${name}`); }
  else           { FAIL++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
}

// ── Mock WebSocket ────────────────────────────────────────────────────────

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.OPEN;
    this.sent = [];
    this.closedCode = null;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    MockWebSocket._instances.push(this);
  }
  send(data) { this.sent.push(data); }
  close(code = 1000) {
    this.closedCode = code;
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code });
  }
  _receive(data) {
    if (this.onmessage) this.onmessage({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }
  static OPEN   = 1;
  static CLOSED = 3;
  static _instances = [];
  static last() { return MockWebSocket._instances[MockWebSocket._instances.length - 1] || null; }
  static reset() { MockWebSocket._instances = []; }
}

// ── Build context ─────────────────────────────────────────────────────────

const scheduledTimers = [];
let timerCounter = 1;

function makeFreshContext() {
  scheduledTimers.length = 0;
  MockWebSocket.reset();

  const ctx = {
    // WebSocket
    WebSocket: MockWebSocket,
    // localStorage
    localStorage: {
      _data: { tw_jwt: 'test.jwt.token' },
      getItem(k) { return this._data[k] || null; },
      setItem(k, v) { this._data[k] = v; },
    },
    // performance
    performance: { now: () => Date.now() },
    // document stubs
    document: {
      getElementById: () => null,
      querySelector:  () => null,
      querySelectorAll: () => ({ forEach: () => {} }),
      _badgeCalled: false,
    },
    // window
    window: { location: { protocol: 'https:', host: 'tawasolna.com' } },
    // timer stubs (shared reference so tests can inspect them)
    _scheduledTimers: scheduledTimers,
    setTimeout(fn, delay) {
      const id = timerCounter++;
      scheduledTimers.push({ id, fn, delay, cancelled: false });
      return id;
    },
    clearTimeout(id) {
      const t = scheduledTimers.find(t => t.id === id);
      if (t) t.cancelled = true;
    },
    // App state used by messages.ws.js
    _user: null,
    _currentConvId: null,
    _typingHideTimer: null,
    _pendingStatus: {},
    // App functions called by messages.ws.js
    twDebugLog: () => {},
    scrollDown:  () => {},
    loadConversations: () => {},
    esc: (s) => s,
    // TwAuthSync not present → should not throw
    TwAuthSync: undefined,
    // JSON (needed inside vm context)
    JSON,
    Math,
  };

  // Evaluate messages.ws.js inside this context so var declarations become ctx properties
  const src = readFileSync('messages.ws.js', 'utf8');
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx;
}

// ── Tests ─────────────────────────────────────────────────────────────────

console.log('\n── Client lifecycle tests (messages.ws.js) ────────────────────────────');

// T01: connectWS without _user → no socket created
(function test_T01() {
  const ctx = makeFreshContext();
  ctx._user = null;
  ctx.connectWS();
  check('T01  connectWS() without _user → no WebSocket created',
        MockWebSocket._instances.length === 0);
})();

// T02: onopen sends {type:'auth',token:...} as first message
(function test_T02() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.localStorage._data.tw_jwt = 'my.test.jwt';
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  check('T02  onopen sends auth frame as first message',
        ws.sent.length >= 1 && (() => {
          try { const m = JSON.parse(ws.sent[0]); return m.type === 'auth' && m.token === 'my.test.jwt'; }
          catch { return false; }
        })());
})();

// T03: auth_ok with correct user_id sets _wsReady = true
(function test_T03() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 42 });
  check('T03  auth_ok with correct user_id sets _wsReady = true',
        ctx._wsReady === true);
})();

// T04: auth_ok with wrong user_id closes socket or clears _wsReady
(function test_T04() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 99 });  // wrong uid
  check('T04  auth_ok with wrong user_id → socket closed or _wsReady not set',
        ws.closedCode !== null || ctx._wsReady === false);
})();

// T05: Messages before auth_ok are dropped (_wsReady guard)
(function test_T05() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  let badgeCalled = false;
  ctx.document.querySelectorAll = () => ({ forEach: () => { badgeCalled = true; } });
  ctx.connectWS();
  const ws = MockWebSocket.last();
  // Do NOT trigger auth; send operational message directly
  ws._receive({ type: 'badge_update', badge: 'messages', count: 5 });
  check('T05  badge_update before auth_ok is dropped',
        badgeCalled === false);
})();

// T06: badge_update processed after auth_ok
(function test_T06() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  let badgeCalled = false;
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 42 });
  ctx.document.querySelectorAll = () => ({ forEach: () => { badgeCalled = true; } });
  ws._receive({ type: 'badge_update', badge: 'messages', count: 3 });
  check('T06  badge_update processed after auth_ok',
        badgeCalled === true);
})();

// T07: onclose with code 4001 → no reconnect timer
// (auth timer is cancelled in onclose, so timer-count comparison breaks;
//  use ctx._wsReconnectTimer instead)
(function test_T07() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws.close(4001);
  check('T07  onclose code=4001 → no reconnect timer scheduled',
        ctx._wsReconnectTimer === null);
})();

// T08: onclose with code 4007 → no reconnect
(function test_T08() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws.close(4007);
  check('T08  onclose code=4007 → no reconnect timer scheduled',
        ctx._wsReconnectTimer === null);
})();

// T09: onclose with code 1006 → reconnect scheduled
// (auth timer cancelled + reconnect timer added = net-count unchanged;
//  verify directly via ctx._wsReconnectTimer)
(function test_T09() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws.close(1006);
  check('T09  onclose code=1006 → reconnect timer scheduled',
        ctx._wsReconnectTimer !== null);
})();

// T10: Generation counter prevents stale reconnect
(function test_T10() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws1 = MockWebSocket.last();
  ws1.onopen && ws1.onopen();
  // Start second connection — advances _wsGen
  ctx.connectWS();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;
  // Trigger onclose on the old socket — it should detect stale generation
  if (ws1.onclose) ws1.onclose({ code: 1006 });
  const timersAfter = scheduledTimers.filter(t => !t.cancelled).length;
  check('T10  Stale socket onclose (superseded gen) → no reconnect timer',
        timersAfter === timersBefore);
})();

// T11: _wsReady reset to false after onclose
(function test_T11() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 42 });
  const wasReady = ctx._wsReady;
  ws.close(1000);
  check('T11  _wsReady reset to false after onclose',
        wasReady === true && ctx._wsReady === false);
})();

// T12: _wsGen increments on each connectWS call
(function test_T12() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  const gen1 = ctx._wsGen;
  ctx.connectWS();
  const gen2 = ctx._wsGen;
  ctx.connectWS();
  const gen3 = ctx._wsGen;
  check('T12  _wsGen increments on each connectWS call',
        gen2 === gen1 + 1 && gen3 === gen2 + 1);
})();

// T13: Client-side auth timeout timer is scheduled in onopen
(function test_T13() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;
  ws.onopen && ws.onopen();
  const authTimeoutTimer = scheduledTimers.find(t => t.delay === 5000 && !t.cancelled);
  check('T13  Client-side 5s auth timeout timer scheduled in onopen',
        authTimeoutTimer !== undefined);
})();

// ─────────────────────────────────────────────────────────────────────────────
// TwAuthSync lifecycle tests (T14–T22) and retry limit (T23)
// Uses makeFreshContextWithAuth: same as makeFreshContext but provides TwAuthSync
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n── TwAuthSync lifecycle tests (messages.ws.js) ──────────────────────────');

function makeFreshContextWithAuth(snapshot = null) {
  scheduledTimers.length = 0;
  MockWebSocket.reset();

  let sessionChangeCb = null;
  const locationCalls = [];

  const ctx = {
    WebSocket: MockWebSocket,
    localStorage: {
      _data: {
        tw_jwt: 'test.jwt.token',
        tw_user: JSON.stringify({ id: 42 }),
      },
      getItem(k) { return this._data[k] || null; },
      setItem(k, v) { this._data[k] = v; },
    },
    performance: { now: () => Date.now() },
    document: {
      getElementById: () => null,
      querySelector:  () => null,
      querySelectorAll: () => ({ forEach: () => {} }),
    },
    window: {
      location: {
        protocol: 'https:',
        host: 'tawasolna.com',
        replace(url) { locationCalls.push({ action: 'replace', url }); },
        reload()     { locationCalls.push({ action: 'reload' }); },
      },
    },
    _locationCalls: locationCalls,
    _scheduledTimers: scheduledTimers,
    setTimeout(fn, delay) {
      const id = timerCounter++;
      scheduledTimers.push({ id, fn, delay, cancelled: false });
      return id;
    },
    clearTimeout(id) {
      const t = scheduledTimers.find(t => t.id === id);
      if (t) t.cancelled = true;
    },
    _user: { id: 42 },
    _jwt: 'test.jwt.token',
    _currentConvId: null,
    _typingHideTimer: null,
    _pendingStatus: {},
    twDebugLog: () => {},
    scrollDown: () => {},
    loadConversations: () => {},
    esc: (s) => s,
    TwAuthSync: {
      onSessionChange(cb) { sessionChangeCb = cb; },
      getSessionSnapshot: snapshot !== null ? () => snapshot : undefined,
    },
    JSON,
    Math,
  };

  const src = readFileSync('messages.ws.js', 'utf8');
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  ctx._fireSessionChange = (info) => sessionChangeCb && sessionChangeCb(info);
  return ctx;
}

// Helper: fire the first non-cancelled pending timer
function firePendingTimer() {
  const t = scheduledTimers.find(t => !t.cancelled);
  if (t) { t.cancelled = true; t.fn(); return true; }
  return false;
}

// T14: TwAuthSync.onSessionChange is registered when TwAuthSync is present
(function test_T14() {
  let registered = false;
  const orig = {};
  // Use a flag approach: if the session change fires, it registered
  const ctx = makeFreshContextWithAuth();
  const genBefore = ctx._wsGen;
  ctx._fireSessionChange({});   // logout signal
  check('T14  TwAuthSync.onSessionChange registered (fires on session change)',
        ctx._wsGen > genBefore);  // gen advances on any session change
})();

// T15: Logout → location.replace('/login') called, no reconnect timer
// Proper logout simulation: clear JWT from localStorage AND fire with empty jwt
(function test_T15() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 42 });

  scheduledTimers.length = 0;
  // Simulate real logout: clear JWT from localStorage, then fire with empty jwt
  ctx.localStorage._data.tw_jwt = '';
  ctx._fireSessionChange({ jwt: '' });

  check('T15  Logout (empty jwt) → location.replace(\'/login\') called, no reconnect timer',
        ctx._locationCalls.some(c => c.action === 'replace' && c.url === '/login') &&
        scheduledTimers.filter(t => !t.cancelled).length === 0);
})();

// T16: Account switch (different userId) → window.location.reload() called
// Cross-account switch triggers a full page reload for clean re-init
(function test_T16() {
  const snapshot = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 55, reason: 'ok' };
  const ctx = makeFreshContextWithAuth(snapshot);
  ctx.connectWS();
  const ws1 = MockWebSocket.last();
  ws1.onopen && ws1.onopen();

  MockWebSocket.reset();
  ctx._fireSessionChange({ jwt: 'user.b.jwt' });

  check('T16  Account switch (different userId) → window.location.reload() called',
        ctx._locationCalls.some(c => c.action === 'reload'));
})();

// T17: Account switch → no new WebSocket (page reload handles re-init)
// After reload() is called, no WS reconnect is scheduled or created
(function test_T17() {
  const snapshot = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 55, reason: 'ok' };
  const ctx = makeFreshContextWithAuth(snapshot);
  ctx.connectWS();

  MockWebSocket.reset();
  ctx._fireSessionChange({ jwt: 'fresh.b.jwt' });

  check('T17  Account switch → no new WebSocket created (page reload handles re-init)',
        MockWebSocket._instances.length === 0 &&
        ctx._locationCalls.some(c => c.action === 'reload'));
})();

// T18: getSessionSnapshot returns isAuthenticated=false → location.replace('/login'), no new socket
// V2 snapshot format with explicit unauthenticated state — JWT present but session invalid
(function test_T18() {
  const snapshot = { state: 'unauthenticated', isAuthenticated: false, userType: null, userId: null, reason: 'ok' };
  const ctx = makeFreshContextWithAuth(snapshot);
  ctx.connectWS();

  MockWebSocket.reset();
  ctx._fireSessionChange({ jwt: 'some.jwt' });

  check('T18  V2 snapshot isAuthenticated=false → location.replace(\'/login\'), no new WS',
        ctx._locationCalls.some(c => c.action === 'replace' && c.url === '/login') &&
        MockWebSocket._instances.length === 0);
})();

// T19: Session switch then real logout → switch timer cancelled
(function test_T19() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();

  scheduledTimers.length = 0;
  ctx._fireSessionChange({ jwt: 'new.jwt' });
  const switchTimerAfterSwitch = scheduledTimers.find(t => !t.cancelled && t.delay === 500);
  // Simulate real logout: clear JWT, then fire empty jwt
  ctx.localStorage._data.tw_jwt = '';
  ctx._fireSessionChange({ jwt: '' });
  // Switch timer must be cancelled by step 1 of the logout handler
  check('T19  Logout after switch → switch timer cancelled',
        switchTimerAfterSwitch !== undefined && switchTimerAfterSwitch.cancelled === true);
})();

// T20: auth_ok uid mismatch → _wsGen advanced, socket closed 4003, no reconnect
(function test_T20() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();

  scheduledTimers.length = 0;
  const genBefore = ctx._wsGen;
  ws._receive({ type: 'auth_ok', user_id: 999 });  // wrong uid

  check('T20  auth_ok uid mismatch → 4003 close, _wsGen advanced, no reconnect timer',
        ws.closedCode === 4003 &&
        ctx._wsGen > genBefore &&
        scheduledTimers.filter(t => !t.cancelled).length === 0);
})();

// T21: Stale onmessage (generation superseded) → operational message ignored
(function test_T21() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();
  const ws1 = MockWebSocket.last();
  ws1.onopen && ws1.onopen();
  ws1._receive({ type: 'auth_ok', user_id: 42 });

  // Advance generation (start new connection — supersedes ws1)
  ctx.connectWS();

  let badgeCalled = false;
  ctx.document.querySelectorAll = () => ({ forEach: () => { badgeCalled = true; } });

  // Deliver operational message to stale socket ws1
  ws1._receive({ type: 'badge_update', badge: 'messages', count: 7 });
  check('T21  Stale socket onmessage (superseded gen) → message ignored',
        badgeCalled === false);
})();

// T22: Stale onclose → no reconnect timer scheduled
(function test_T22() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();
  const ws1 = MockWebSocket.last();
  ws1.onopen && ws1.onopen();

  // Supersede ws1 by connecting again
  ctx.connectWS();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;

  // Trigger onclose on stale ws1
  if (ws1.onclose) ws1.onclose({ code: 1006 });
  const timersAfter = scheduledTimers.filter(t => !t.cancelled).length;
  check('T22  Stale onclose (superseded gen) → no reconnect timer',
        timersAfter === timersBefore);
})();

// T23: Retry count (_wsRetries) at max 5 → no further reconnect timer
// (auth timer is cancelled in onclose, so use ctx._wsReconnectTimer for the check)
(function test_T23() {
  const ctx = makeFreshContextWithAuth();
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  ws._receive({ type: 'auth_ok', user_id: 42 });

  // auth_ok resets retries to 0; manually set to max
  ctx._wsRetries = 5;
  ws.close(1006);
  check('T23  _wsRetries at limit (5) → no reconnect timer scheduled',
        ctx._wsReconnectTimer === null);
})();

// ─────────────────────────────────────────────────────────────────────────────
// Badge WS runtime tests (T24–T30)
// Loads only the Badge WS IIFE from tw_shared.js in a minimal context
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n── Badge WS runtime tests (tw_shared.js) ────────────────────────────────');

function makeBadgeContext(opts = {}) {
  scheduledTimers.length = 0;
  MockWebSocket.reset();

  const { uid = 42, jwt = 'badge.test.jwt', snapshot = null, noUser = false } = opts;
  let sessionChangeCb = null;
  let loadCb = null;

  const ctx = {
    WebSocket: MockWebSocket,
    localStorage: {
      _data: noUser ? {} : {
        tw_user: JSON.stringify({ id: uid }),
        tw_jwt: jwt,
      },
      getItem(k) { return this._data[k] || null; },
      setItem(k, v) { this._data[k] = v; },
    },
    TwAuthSync: {
      onSessionChange(cb) { sessionChangeCb = cb; },
      getSessionSnapshot: snapshot !== null ? () => snapshot : undefined,
    },
    window: {
      location: { protocol: 'https:', host: 'tawasolna.com' },
      addEventListener(evt, fn) { if (evt === 'load') loadCb = fn; },
    },
    document: {
      querySelectorAll() { return { forEach() {} }; },
    },
    setTimeout(fn, delay) {
      const id = timerCounter++;
      scheduledTimers.push({ id, fn, delay, cancelled: false });
      return id;
    },
    clearTimeout(id) {
      const t = scheduledTimers.find(t => t.id === id);
      if (t) t.cancelled = true;
    },
    JSON,
    Math,
  };

  // Extract only the Badge WS IIFE from tw_shared.js
  const full = readFileSync('tw_shared.js', 'utf8');
  const marker = '// ══ Global Real-time Badge WebSocket ══';
  const start = full.indexOf(marker);
  const iifeSrc = start !== -1 ? full.slice(start) : full;

  vm.createContext(ctx);
  vm.runInContext(iifeSrc, ctx);

  return {
    ctx,
    fireLoad()            { loadCb && loadCb(); },
    fireSessionChange(i)  { sessionChangeCb && sessionChangeCb(i); },
  };
}

// T24: Badge WS with valid user → socket created after load
(function test_T24() {
  const b = makeBadgeContext();
  b.fireLoad();
  // Fire the 200ms init delay
  const initTimer = scheduledTimers.find(t => !t.cancelled);
  if (initTimer) { initTimer.cancelled = true; initTimer.fn(); }
  check('T24  Badge WS with valid user → socket created after load',
        MockWebSocket._instances.length === 1);
})();

// T25: Badge WS without user → no socket created
(function test_T25() {
  const b = makeBadgeContext({ noUser: true });
  b.fireLoad();
  const initTimer = scheduledTimers.find(t => !t.cancelled);
  if (initTimer) { initTimer.cancelled = true; initTimer.fn(); }
  check('T25  Badge WS without user in localStorage → no socket',
        MockWebSocket._instances.length === 0);
})();

// T26: Badge WS auth_ok uid mismatch → _gen++ and ws.close(4003)
(function test_T26() {
  const b = makeBadgeContext();
  b.fireLoad();
  const initTimer = scheduledTimers.find(t => !t.cancelled);
  if (initTimer) { initTimer.cancelled = true; initTimer.fn(); }

  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  scheduledTimers.length = 0;  // clear any onopen timers

  // Send auth_ok with wrong uid
  ws._receive({ type: 'auth_ok', user_id: 999 });

  check('T26  Badge WS auth_ok uid mismatch → close 4003, no reconnect timer',
        ws.closedCode === 4003 &&
        scheduledTimers.filter(t => !t.cancelled).length === 0);
})();

// T27: Badge WS retries stop after 5
(function test_T27() {
  const b = makeBadgeContext();
  b.fireLoad();

  let retryTimersScheduled = 0;
  const MAX = 5;

  // Drive through init + 5 retry cycles
  for (let i = 0; i <= MAX + 1; i++) {
    const t = scheduledTimers.filter(t2 => !t2.cancelled).pop();
    if (!t) break;
    t.cancelled = true;
    t.fn();  // calls _initBadgeWS

    const ws = MockWebSocket.last();
    if (!ws) break;

    const before = scheduledTimers.filter(t2 => !t2.cancelled).length;
    // Close with non-auth code to trigger retry
    ws.close(1006);
    const after = scheduledTimers.filter(t2 => !t2.cancelled).length;
    if (after > before) retryTimersScheduled++;
  }

  check('T27  Badge WS retries stop at 5',
        retryTimersScheduled === MAX);
})();

// T28: Badge WS session logout → no reconnect
(function test_T28() {
  const b = makeBadgeContext();
  b.fireLoad();
  const initTimer = scheduledTimers.find(t => !t.cancelled);
  if (initTimer) { initTimer.cancelled = true; initTimer.fn(); }

  scheduledTimers.length = 0;
  b.fireSessionChange({});   // logout — no jwt

  check('T28  Badge WS session logout → no reconnect timer',
        scheduledTimers.filter(t => !t.cancelled).length === 0);
})();

// T29: Badge WS session switch resets _retries (new session allows 5 fresh retries)
(function test_T29() {
  const b = makeBadgeContext();
  b.fireLoad();

  // Exhaust retries (5 disconnects)
  for (let i = 0; i < 6; i++) {
    const t = scheduledTimers.filter(t2 => !t2.cancelled).pop();
    if (!t) break;
    t.cancelled = true; t.fn();
    const ws = MockWebSocket.last();
    if (ws) ws.close(1006);
  }

  // Now fire a session switch → _retries should reset
  scheduledTimers.length = 0;
  b.fireSessionChange({ jwt: 'new.jwt.for.switch' });

  // Fire the 300ms reinit timer
  const switchTimer = scheduledTimers.find(t => !t.cancelled);
  if (switchTimer) { switchTimer.cancelled = true; switchTimer.fn(); }

  // The new socket should exist and allow a retry on close
  const ws2 = MockWebSocket.last();
  const before = scheduledTimers.filter(t => !t.cancelled).length;
  if (ws2) ws2.close(1006);
  const after = scheduledTimers.filter(t => !t.cancelled).length;

  check('T29  Badge WS session switch resets _retries → retry scheduled after switch',
        after > before);
})();

// T30: Badge WS auth_ok success resets _retries
(function test_T30() {
  const b = makeBadgeContext();
  b.fireLoad();

  // Use up some retries (3 disconnects before auth)
  for (let i = 0; i < 3; i++) {
    const t = scheduledTimers.filter(t2 => !t2.cancelled).pop();
    if (!t) break;
    t.cancelled = true; t.fn();
    const ws = MockWebSocket.last();
    if (ws) ws.close(1006);
  }

  // Fire 4th init
  const t4 = scheduledTimers.filter(t2 => !t2.cancelled).pop();
  if (t4) { t4.cancelled = true; t4.fn(); }
  const ws4 = MockWebSocket.last();
  if (!ws4) { check('T30  Badge WS auth_ok success resets _retries', false, 'no socket'); return; }
  ws4.onopen && ws4.onopen();
  // Authenticate successfully → _retries should reset to 0
  ws4._receive({ type: 'auth_ok', user_id: 42 });

  // Now close with normal code — should schedule retry (proving _retries reset)
  scheduledTimers.length = 0;
  ws4.close(1006);
  const afterClose = scheduledTimers.filter(t => !t.cancelled).length;

  check('T30  Badge WS auth_ok success resets _retries → retry still allowed',
        afterClose > 0);
})();

// ─────────────────────────────────────────────────────────────────────────────
// New lifecycle and contract tests (T31–T34)
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n── Retry lifecycle and auth-timer contract tests (T31–T34) ─────────────');

// T31: Real 5-cycle retry lifecycle — _wsRetries NOT reset in onopen
// Simulates 5 failed connections (auth never arrives) and verifies retries accumulate
(function test_T31() {
  const ctx = makeFreshContextWithAuth();
  ctx._user = { id: 42 };
  ctx.connectWS();

  let reconnTimersScheduled = 0;
  for (let attempt = 0; attempt <= 6; attempt++) {
    const ws = MockWebSocket.last();
    if (!ws) break;
    ws.onopen && ws.onopen();                           // auth timeout scheduled, retries NOT reset
    const wsReconnBefore = ctx._wsReconnectTimer;
    ws.onclose && ws.onclose({ code: 1006 });           // auth timeout cancelled, retry counter++
    const wsReconnAfter = ctx._wsReconnectTimer;
    const timerAdded = wsReconnAfter !== null && wsReconnAfter !== wsReconnBefore;
    if (timerAdded) {
      reconnTimersScheduled++;
      const t = scheduledTimers.find(t2 => t2.id === wsReconnAfter && !t2.cancelled);
      if (t) { t.cancelled = true; t.fn(); }            // fire reconnect → new connectWS()
    } else { break; }
  }
  check('T31  5-cycle retry: _wsRetries not reset in onopen → stops at exactly 5',
        reconnTimersScheduled === 5 && ctx._wsRetries === 5);
})();

// T32: Auth timeout timer cleared on auth_ok
(function test_T32() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();                             // schedules _wsAuthTimeoutTimer
  const timerSetAfterOpen = ctx._wsAuthTimeoutTimer !== null;
  ws._receive({ type: 'auth_ok', user_id: 42 });        // should cancel and null the timer
  check('T32  Auth timeout timer cleared on auth_ok',
        timerSetAfterOpen === true && ctx._wsAuthTimeoutTimer === null);
})();

// T33: Auth timeout timer cleared on onclose
(function test_T33() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();                             // schedules _wsAuthTimeoutTimer
  const timerSetAfterOpen = ctx._wsAuthTimeoutTimer !== null;
  ws.onclose && ws.onclose({ code: 1006 });             // should cancel timer (ws === _ws)
  check('T33  Auth timeout timer cleared on onclose (ws === _ws)',
        timerSetAfterOpen === true && ctx._wsAuthTimeoutTimer === null);
})();

// T34: Badge WS V2 snapshot (no jwt field) + localStorage JWT → socket created
(function test_T34() {
  const v2snapshot = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 42, reason: 'ok' };
  const b = makeBadgeContext({ uid: 42, jwt: 'ls.badge.jwt', snapshot: v2snapshot });
  b.fireLoad();
  const initTimer = scheduledTimers.find(t => !t.cancelled);
  if (initTimer) { initTimer.cancelled = true; initTimer.fn(); }
  check('T34  Badge WS V2 snapshot (no jwt field) + localStorage JWT → socket created at /42',
        MockWebSocket._instances.length === 1 && (MockWebSocket.last() || {}).url?.includes('/42'));
})();

// ─────────────────────────────────────────────────────────────────────────────
// Session switch / logout navigation tests (T35–T37)
// Verifies that the new TwAuthSync handler correctly redirects on logout,
// reloads on account switch, and reconnects on same-user JWT refresh.
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n── Session switch / logout navigation tests (T35–T37) ──────────────────');

// T35: Logout → _user/_currentConvId cleared, location.replace('/login') called
(function test_T35() {
  const ctx = makeFreshContextWithAuth();
  ctx._currentConvId = 123;
  ctx.connectWS();

  ctx.localStorage._data.tw_jwt = '';
  ctx._fireSessionChange({ jwt: '' });

  check('T35  Logout → _user cleared, _currentConvId cleared, replace(\'/login\') called',
        ctx._user === null &&
        ctx._currentConvId === null &&
        ctx._locationCalls.some(c => c.action === 'replace' && c.url === '/login'));
})();

// T36: Same user + still authenticated → no reload/replace, reconnect timer scheduled
(function test_T36() {
  const snapshot = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 42, reason: 'ok' };
  const ctx = makeFreshContextWithAuth(snapshot);
  ctx.connectWS();

  scheduledTimers.length = 0;
  ctx._fireSessionChange({ jwt: 'same.user.fresh.jwt' });

  const switchTimer = scheduledTimers.find(t => !t.cancelled && t.delay === 500);
  check('T36  Same user + authenticated → no reload/replace, reconnect timer scheduled',
        ctx._locationCalls.length === 0 &&
        switchTimer !== undefined);
})();

// T37: Account switch → location.reload() called, no new WS created
(function test_T37() {
  const snapshot = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 77, reason: 'ok' };
  const ctx = makeFreshContextWithAuth(snapshot);
  ctx.connectWS();

  MockWebSocket.reset();
  ctx._fireSessionChange({ jwt: 'user.c.jwt' });

  check('T37  Account switch (userId 77 ≠ 42) → location.reload() called, no new WS',
        ctx._locationCalls.some(c => c.action === 'reload') &&
        MockWebSocket._instances.length === 0);
})();

// ─────────────────────────────────────────────────────────────────────────────
// Typing throttle tests (T38–T42)
// Loads messages.render.js in a minimal DOM context and exercises the
// input event handler throttle/debounce logic.
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n── Typing throttle tests (messages.render.js) ───────────────────────────');

function makeRenderThrottleContext() {
  scheduledTimers.length = 0;

  const sendTypingCalls    = [];
  const sendTypingStopCalls = [];
  let   inputEventFn       = null;
  let   domLoadFn          = null;

  const mockMsgInput = {
    value: '',
    scrollHeight: 20,
    style: {},
    addEventListener(event, fn) { if (event === 'input') inputEventFn = fn; },
  };

  const ctx = {
    document: {
      addEventListener(event, fn) { if (event === 'DOMContentLoaded') domLoadFn = fn; },
      getElementById(id) {
        if (id === 'msgInput') return mockMsgInput;
        return null;
      },
      querySelector:    () => null,
      querySelectorAll: () => ({ forEach() {} }),
    },
    location: { search: '' },
    window:   { addEventListener: () => {} },
    localStorage: {
      _data: { tw_jwt: 'render.test.jwt' },
      getItem(k) { return this._data[k] || null; },
    },
    _scheduledTimers: scheduledTimers,
    setTimeout(fn, delay) {
      const id = timerCounter++;
      scheduledTimers.push({ id, fn, delay, cancelled: false });
      return id;
    },
    clearTimeout(id) {
      const t = scheduledTimers.find(t => t.id === id);
      if (t) t.cancelled = true;
    },
    setInterval:  () => 9999,
    clearInterval: () => {},
    URLSearchParams: class { constructor() {} get() { return null; } },
    // State globals (mirrors messages.state.js)
    _user:          { id: 42 },
    _jwt:           'render.test.jwt',
    _currentConvId: 100,
    _activeConvMeta: null,
    _pendingStatus:  {},
    _typingTimer:    null,
    _typingThrottle: null,
    _typingHideTimer: null,
    // External functions called by messages.render.js
    sendTyping(convId)     { sendTypingCalls.push(convId); },
    sendTypingStop(convId) { sendTypingStopCalls.push(convId); },
    sendInactiveConversation: () => {},
    hideTypingBubble:     () => {},
    connectWS:            () => {},
    // messages.api.js functions (render.js references but does not define)
    apiGetConversations:  () => Promise.resolve({ ok: false, data: { conversations: [] } }),
    apiGetMessages:       () => Promise.resolve({ ok: false, data: { messages: [] } }),
    apiGetUnreadCount:    () => Promise.resolve({ ok: false, data: {} }),
    apiLookupByTwId:      () => Promise.resolve(null),
    apiSendMessage:       () => Promise.resolve({ ok: false }),
    requestAnimationFrame: fn => { fn && fn(); return 0; },
    performance: { now: () => Date.now() },
    Promise,
    esc(s) {
      return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },
    twDebugLog: () => {},
    scrollDown:  () => {},
    JSON, Math,
  };

  const src = readFileSync('messages.render.js', 'utf8');
  vm.createContext(ctx);
  vm.runInContext(src, ctx);

  // Fire DOMContentLoaded so event listeners are attached
  if (domLoadFn) domLoadFn();

  const fireInput = () => { if (inputEventFn) inputEventFn.call(mockMsgInput); };

  return { ctx, mockMsgInput, sendTypingCalls, sendTypingStopCalls, fireInput };
}

// T38: 30 rapid keystrokes → exactly 1 typing event (throttle guards the rest)
(function test_T38() {
  const { ctx, sendTypingCalls, fireInput } = makeRenderThrottleContext();
  ctx._currentConvId = 100;
  for (let i = 0; i < 30; i++) fireInput();
  check('T38  30 rapid keystrokes → exactly 1 sendTyping call (throttle)',
        sendTypingCalls.length === 1,
        `sendTyping called ${sendTypingCalls.length} time(s)`);
})();

// T39: After 1800ms idle (fire debounce timer) → sendTypingStop called, _typingThrottle cleared
(function test_T39() {
  const { ctx, sendTypingStopCalls, fireInput } = makeRenderThrottleContext();
  ctx._currentConvId = 100;
  // Trigger one keystroke so both timers are set
  fireInput();
  // Find and fire the 1800ms debounce timer
  const debounceTimer = scheduledTimers.find(t => !t.cancelled && t.delay === 1800);
  if (debounceTimer) { debounceTimer.cancelled = true; debounceTimer.fn(); }
  check('T39  1800ms idle → sendTypingStop called once, _typingThrottle cleared',
        sendTypingStopCalls.length === 1 && ctx._typingThrottle === null,
        `sendTypingStop calls: ${sendTypingStopCalls.length}, _typingThrottle: ${ctx._typingThrottle}`);
})();

// T40: closeConversationUI clears both _typingTimer and _typingThrottle
(function test_T40() {
  const { ctx, fireInput } = makeRenderThrottleContext();
  ctx._currentConvId = 100;
  fireInput();  // sets both _typingTimer and _typingThrottle
  const hadTimer    = ctx._typingTimer !== null;
  const hadThrottle = ctx._typingThrottle !== null;
  // closeConversationUI is defined in messages.render.js and exposed on ctx
  if (typeof ctx.closeConversationUI === 'function') {
    ctx.closeConversationUI();
  }
  check('T40  closeConversationUI clears _typingTimer and _typingThrottle',
        hadTimer && hadThrottle && ctx._typingTimer === null && ctx._typingThrottle === null,
        `hadTimer:${hadTimer} hadThrottle:${hadThrottle} after: timer=${ctx._typingTimer} throttle=${ctx._typingThrottle}`);
})();

// T41: doSendMessage clears throttle and sends typing_stop
(function test_T41() {
  const { ctx, sendTypingStopCalls, fireInput } = makeRenderThrottleContext();
  ctx._currentConvId = 100;
  fireInput();  // arm both timers
  const hadThrottle = ctx._typingThrottle !== null;
  // Provide mock DOM elements doSendMessage needs
  ctx.document.getElementById = (id) => {
    if (id === 'msgInput')  return { value: 'hello', style: {}, scrollHeight: 20, focus() {} };
    if (id === 'messages')  return { insertAdjacentHTML() {}, scrollTop: 0, scrollHeight: 0 };
    return null;
  };
  // Override apiSendMessage with one that returns a resolved promise (avoids .then crash)
  ctx.apiSendMessage = () => Promise.resolve({ ok: false, message: {} });
  if (typeof ctx.doSendMessage === 'function') ctx.doSendMessage();
  check('T41  doSendMessage clears _typingThrottle and sends typing_stop',
        hadThrottle && ctx._typingThrottle === null && sendTypingStopCalls.length >= 1,
        `hadThrottle:${hadThrottle} _typingThrottle:${ctx._typingThrottle} typingStops:${sendTypingStopCalls.length}`);
})();

// T42: Input event when _currentConvId is null → no sendTyping, no timers
(function test_T42() {
  const { ctx, sendTypingCalls, sendTypingStopCalls, fireInput } = makeRenderThrottleContext();
  ctx._currentConvId = null;  // no active conversation
  fireInput();
  check('T42  Input with _currentConvId=null → no sendTyping, no typing timers set',
        sendTypingCalls.length === 0 &&
        ctx._typingTimer === null &&
        ctx._typingThrottle === null,
        `sendTyping:${sendTypingCalls.length} timer:${ctx._typingTimer} throttle:${ctx._typingThrottle}`);
})();


// ── Summary ──────────────────────────────────────────────────────────────

const total = PASS + FAIL;
console.log(`\n${'─'.repeat(60)}`);
console.log(`  ${PASS}/${total} passed  ${FAIL === 0 ? '✓  all green' : `✗  ${FAIL} FAILED`}`);
console.log(`${'─'.repeat(60)}\n`);
process.exit(FAIL === 0 ? 0 : 1);
