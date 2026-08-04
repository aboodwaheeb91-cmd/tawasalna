/**
 * WebSocket Client Lifecycle Tests
 * ==================================
 * Verifies the client-side security properties of messages.ws.js by
 * exercising the logic with mock DOM and WebSocket objects.
 * No real server required.
 *
 * 13 scenarios:
 *   T01  connectWS without _user → no socket
 *   T02  onopen sends {type:'auth',token:...} as first message
 *   T03  auth_ok with correct uid sets _wsReady = true
 *   T04  auth_ok with wrong uid closes socket
 *   T05  Messages before auth_ok are dropped
 *   T06  Messages after auth_ok are processed (badge_update)
 *   T07  onclose with code 4001 → no reconnect
 *   T08  onclose with code 4007 → no reconnect
 *   T09  onclose with code 1006 → reconnect scheduled
 *  T10  Generation counter prevents stale reconnect
 *  T11  _wsReady reset to false on close
 *  T12  _wsGen increments on each connectWS call
 *  T13  Client-side auth timeout scheduled in onopen
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
(function test_T07() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;
  ws.close(4001);
  const timersAfter = scheduledTimers.filter(t => !t.cancelled).length;
  check('T07  onclose code=4001 → no reconnect timer added',
        timersAfter === timersBefore);
})();

// T08: onclose with code 4007 → no reconnect
(function test_T08() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;
  ws.close(4007);
  const timersAfter = scheduledTimers.filter(t => !t.cancelled).length;
  check('T08  onclose code=4007 → no reconnect timer added',
        timersAfter === timersBefore);
})();

// T09: onclose with code 1006 → reconnect scheduled
(function test_T09() {
  const ctx = makeFreshContext();
  ctx._user = { id: 42 };
  ctx.connectWS();
  const ws = MockWebSocket.last();
  ws.onopen && ws.onopen();
  const timersBefore = scheduledTimers.filter(t => !t.cancelled).length;
  ws.close(1006);
  const timersAfter = scheduledTimers.filter(t => !t.cancelled).length;
  check('T09  onclose code=1006 → reconnect timer scheduled',
        timersAfter > timersBefore);
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

// ── Summary ──────────────────────────────────────────────────────────────

const total = PASS + FAIL;
console.log(`\n${'─'.repeat(60)}`);
console.log(`  ${PASS}/${total} passed  ${FAIL === 0 ? '✓  all green' : `✗  ${FAIL} FAILED`}`);
console.log(`${'─'.repeat(60)}\n`);
process.exit(FAIL === 0 ? 0 : 1);
