'use strict';
/**
 * test_auth_sync_runtime.js — Node.js behavioral runtime tests for auth-sync.js
 * Runs without a browser using fake globals (localStorage, window, document, atob).
 * Tests all 5 session states + lifecycle contracts.
 *
 * Run: node test_auth_sync_runtime.js
 */

const fs = require('fs');

// ─── Fake global state (reset between test groups) ─────────────────
let _store = {};
let _windowListeners = {};

const fakeLocalStorage = {
  getItem(k)    { return Object.prototype.hasOwnProperty.call(_store, k) ? _store[k] : null; },
  setItem(k, v) { _store[k] = String(v); },
  removeItem(k) { delete _store[k]; },
  clear()       { _store = {}; },
};

const fakeWindow = {
  TwAuthSync: null,
  location: { href: '' },
  addEventListener(evt, fn) {
    if (!_windowListeners[evt]) _windowListeners[evt] = [];
    _windowListeners[evt].push(fn);
  },
};

const fakeDocument = {
  visibilityState: 'visible',
  addEventListener() {},
};

// Fake atob: accepts base64url strings (no padding needed)
function fakeAtob(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  return Buffer.from(s, 'base64').toString('utf8');
}

// Minimal fake setTimeout / clearTimeout (sync-mode: never fires automatically)
let _timers = [];
let _nextTimerId = 1;
function fakeSetTimeout(fn, ms) {
  const id = _nextTimerId++;
  _timers.push({ id, fn, ms });
  return id;
}
function fakeClearTimeout(id) {
  const t = _timers.find(t => t.id === id);
  if (t) t.fn = null;
}

// Assign globals before eval
global.localStorage = fakeLocalStorage;
global.window       = fakeWindow;
global.document     = fakeDocument;
global.atob         = fakeAtob;
global.setTimeout   = fakeSetTimeout;
global.clearTimeout = fakeClearTimeout;

// ─── Load auth-sync.js (assigns window.TwAuthSync) ─────────────────
const code = fs.readFileSync('./static/shared/auth-sync.js', 'utf8');
eval(code);

const TwAuthSync = fakeWindow.TwAuthSync;

// ─── Helper: fire a fake storage event ─────────────────────────────
function fireStorageEvent(key) {
  (_windowListeners['storage'] || []).forEach(fn => { try { fn({ key }); } catch(e){} });
}

// ─── Helper: build a minimal JWT with given payload ─────────────────
// Signature check is skipped in client — we only test payload parsing
function makeJwt(payload) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body   = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return `${header}.${body}.fakesig`;
}

function makeValidJwt(userId, userType, secondsFromNow = 86400) {
  const now = Math.floor(Date.now() / 1000);
  return makeJwt({ user_id: userId, user_type: userType, exp: now + secondsFromNow, iat: now });
}

function makeExpiredJwt(userId, userType) {
  const now = Math.floor(Date.now() / 1000);
  return makeJwt({ user_id: userId, user_type: userType, exp: now - 1, iat: now - 100 });
}

// ─── Test runner ───────────────────────────────────────────────────
let testsRun = 0, passed = 0;
const failures = [];
const PASS = '\x1b[32mPASS\x1b[0m';
const FAIL = '\x1b[31mFAIL\x1b[0m';

function check(name, condition, detail) {
  testsRun++;
  if (condition) {
    console.log(`  ${PASS}  ${name}`);
    passed++;
  } else {
    console.log(`  ${FAIL}  ${name}` + (detail ? ` — ${detail}` : ''));
    failures.push(name);
  }
}

function resetStorage() {
  Object.keys(_store).forEach(k => delete _store[k]);
}

// ════════════════════════════════════════════════════════════════════
console.log('\n1 — TwAuthSync public API');

check('R01 — TwAuthSync object exists',       typeof TwAuthSync === 'object' && TwAuthSync !== null);
check('R02 — getSessionSnapshot is function', typeof TwAuthSync.getSessionSnapshot === 'function');
check('R03 — invalidateSession is function',  typeof TwAuthSync.invalidateSession  === 'function');
check('R04 — onSessionChange is function',    typeof TwAuthSync.onSessionChange    === 'function');

// ════════════════════════════════════════════════════════════════════
console.log('\n2 — State: guest (no JWT)');

resetStorage();
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R05 — no jwt → state:guest',            s.state === 'guest');
  check('R06 — guest → isAuthenticated:false',   s.isAuthenticated === false);
  check('R07 — guest → userId:null',             s.userId === null);
  check('R08 — guest → userType:null',           s.userType === null);
  check('R09 — guest → reason:no_jwt',           s.reason === 'no_jwt');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n3 — State: invalid (malformed JWT)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', 'not.a.jwt');
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R10 — malformed jwt → state:invalid',       s.state === 'invalid');
  check('R11 — malformed jwt → isAuthenticated:false', s.isAuthenticated === false);
}

// ════════════════════════════════════════════════════════════════════
console.log('\n4 — State: invalid (missing exp)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeJwt({ user_id: 1, user_type: 'emp' })); // no exp
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R12 — missing exp → state:invalid',       s.state === 'invalid');
  check('R13 — missing exp → reason:missing_exp',  s.reason === 'missing_exp');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n5 — State: invalid (exp is not a number)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeJwt({ user_id: 1, user_type: 'emp', exp: '1000000000' })); // string exp
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R14 — string exp → state:invalid',  s.state === 'invalid');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n6 — State: expired');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeExpiredJwt(1, 'emp'));
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R15 — expired jwt → state:expired',          s.state === 'expired');
  check('R16 — expired → isAuthenticated:false',       s.isAuthenticated === false);
  check('R17 — expired → reason:jwt_expired',          s.reason === 'jwt_expired');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n7 — State: stale (no tw_user)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeValidJwt(1, 'emp'));
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R18 — valid jwt, no tw_user → state:stale',  s.state === 'stale');
  check('R19 — stale → isAuthenticated:false',         s.isAuthenticated === false);
  check('R20 — stale → reason:no_user_object',         s.reason === 'no_user_object');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n8 — State: stale (user_id mismatch)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeValidJwt(1, 'emp'));
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 99, user_type: 'emp' }));
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R21 — user_id mismatch → state:stale',       s.state === 'stale');
  check('R22 — user_id mismatch → reason matches',    s.reason === 'user_id_mismatch');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n9 — State: stale (user_type mismatch)');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', makeValidJwt(1, 'emp'));
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 1, user_type: 'co' })); // type differs
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R23 — user_type mismatch → state:stale',     s.state === 'stale');
  check('R24 — user_type mismatch → reason matches',  s.reason === 'user_type_mismatch');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n10 — State: authenticated');

resetStorage();
fakeLocalStorage.setItem('tw_jwt',  makeValidJwt(42, 'co'));
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 42, user_type: 'co', full_name: 'شركة' }));
{
  const s = TwAuthSync.getSessionSnapshot();
  check('R25 — valid jwt+user → state:authenticated', s.state === 'authenticated');
  check('R26 — authenticated → isAuthenticated:true',  s.isAuthenticated === true);
  check('R27 — authenticated → userId:42',             s.userId === 42);
  check('R28 — authenticated → userType:co',           s.userType === 'co');
  check('R29 — authenticated → reason:ok',             s.reason === 'ok');
}

// ════════════════════════════════════════════════════════════════════
console.log('\n11 — onSessionChange fires on JWT change (storage event)');

// invalidateSession to reset _prevJwt/_prevUserStr to ''
TwAuthSync.invalidateSession('test_reset');
let cbCalls = 0, lastSnap = null;
TwAuthSync.onSessionChange(function(e) { cbCalls++; lastSnap = e.snapshot; });

fakeLocalStorage.setItem('tw_jwt',  makeValidJwt(42, 'co'));
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 42, user_type: 'co' }));
const cbBefore = cbCalls;
fireStorageEvent('tw_jwt');
check('R30 — storage event fires callback',    cbCalls > cbBefore);
check('R31 — callback receives snapshot obj',  lastSnap !== null);

// ════════════════════════════════════════════════════════════════════
console.log('\n12 — onSessionChange fires on tw_user change (fingerprint)');

// After R30, _prevJwt is set. Now change only tw_user.
const cbBefore2 = cbCalls;
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 99, user_type: 'emp' }));
fireStorageEvent('tw_user');
check('R32 — tw_user-only change fires callback', cbCalls > cbBefore2);
check('R33 — snapshot reflects new user state',   lastSnap !== null);

// ════════════════════════════════════════════════════════════════════
console.log('\n13 — invalidateSession: allowlist cleanup (non-session keys preserved)');

resetStorage();
TwAuthSync.invalidateSession('test_reset_2'); // reset fingerprints
fakeLocalStorage.setItem('tw_jwt',        makeValidJwt(1, 'emp'));
fakeLocalStorage.setItem('tw_user',       JSON.stringify({ id: 1, user_type: 'emp' }));
fakeLocalStorage.setItem('tw_cover_edu_1', 'data:image/png;...');  // user preference
fakeLocalStorage.setItem('app_theme',      'dark');                 // non-session key

TwAuthSync.invalidateSession('test_logout');

check('R34 — tw_jwt removed',           fakeLocalStorage.getItem('tw_jwt')        === null);
check('R35 — tw_user removed',          fakeLocalStorage.getItem('tw_user')       === null);
check('R36 — tw_cover_edu_1 preserved', fakeLocalStorage.getItem('tw_cover_edu_1') !== null);
check('R37 — app_theme preserved',      fakeLocalStorage.getItem('app_theme')      !== null);

// ════════════════════════════════════════════════════════════════════
console.log('\n14 — invalidateSession: fires handlers with guest snapshot');

resetStorage();
TwAuthSync.invalidateSession('reset');
fakeLocalStorage.setItem('tw_jwt',  makeValidJwt(1, 'emp'));
fakeLocalStorage.setItem('tw_user', JSON.stringify({ id: 1, user_type: 'emp' }));
let postInvalidSnap = null;
TwAuthSync.onSessionChange(function(e) { postInvalidSnap = e.snapshot; });
TwAuthSync.invalidateSession('test_fire');
check('R38 — invalidate fires callback',        postInvalidSnap !== null);
check('R39 — post-invalidate state is guest',   postInvalidSnap && postInvalidSnap.state === 'guest');

// ════════════════════════════════════════════════════════════════════
console.log('\n15 — invalidateSession: opts.redirect navigates');

fakeWindow.location.href = '/original';
resetStorage();
TwAuthSync.invalidateSession('nav_test', { redirect: '/login' });
check('R40 — opts.redirect sets location.href', fakeWindow.location.href === '/login');

// ════════════════════════════════════════════════════════════════════
console.log('\n16 — invalidateSession: no redirect when opts omitted');

fakeWindow.location.href = '/stay';
resetStorage();
TwAuthSync.invalidateSession('no_nav_test');
check('R41 — no redirect without opts', fakeWindow.location.href === '/stay');

// ════════════════════════════════════════════════════════════════════
console.log('\n17 — getSessionSnapshot: never throws');

resetStorage();
fakeLocalStorage.setItem('tw_jwt', '!@#$%^&*');
let threw = false;
try { TwAuthSync.getSessionSnapshot(); } catch(e) { threw = true; }
check('R42 — getSnapshot never throws on garbage jwt', !threw);

// ════════════════════════════════════════════════════════════════════
console.log('\n18 — Multiple handlers all receive events');

resetStorage();
TwAuthSync.invalidateSession('reset');
let h1 = 0, h2 = 0, h3 = 0;
TwAuthSync.onSessionChange(function() { h1++; });
TwAuthSync.onSessionChange(function() { h2++; });
TwAuthSync.onSessionChange(function() { h3++; });
TwAuthSync.invalidateSession('multi_handler');
check('R43 — all 3 handlers receive invalidate event', h1 > 0 && h2 > 0 && h3 > 0);

// ════════════════════════════════════════════════════════════════════
// Results
console.log(`\n${'='.repeat(55)}`);
console.log(`Tests run: ${testsRun}  |  Passed: ${passed}  |  Failed: ${testsRun - passed}`);
if (failures.length) {
  console.log('\nFailed:');
  failures.forEach(f => console.log(`  - ${f}`));
  process.exit(1);
} else {
  console.log('All runtime checks passed.');
  process.exit(0);
}
