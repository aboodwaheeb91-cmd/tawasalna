/**
 * test_tw_shared_runtime.js — Node.js behavioral tests for tw_shared.js
 * Tests menu policy, badge fetch 401/403 handling, stale-generation guard,
 * twLogout fallback allowlist, and loadGlobalBadges guard contracts.
 *
 * Run: node test_tw_shared_runtime.js
 */

const fs = require('fs');

// ─── Fake global state ──────────────────────────────────────────────
var _store = {};
var _windowListeners = {};
var _queryRegistry = {};   // selector → [fakeEl, ...]

var fakeLocalStorage = {
  getItem:    function(k)    { return Object.prototype.hasOwnProperty.call(_store, k) ? _store[k] : null; },
  setItem:    function(k, v) { _store[k] = String(v); },
  removeItem: function(k)    { delete _store[k]; },
  clear:      function()     { _store = {}; },
};

var fakeWindow = {
  TwAuthSync: null,
  location: { href: '' },
  addEventListener: function(evt, fn) {
    if (!_windowListeners[evt]) _windowListeners[evt] = [];
    _windowListeners[evt].push(fn);
  },
};

function makeFakeEl(attrs) {
  return {
    textContent: '',
    style: { display: '' },
    hidden: false,
    _attrs: attrs || {},
    getAttribute:  function(k)    { return this._attrs[k] != null ? this._attrs[k] : null; },
    setAttribute:  function(k, v) { this._attrs[k] = v; },
    classList: { add: function(){}, remove: function(){}, contains: function(){ return false; }, toggle: function(){} },
    parentNode: null,
    remove:      function(){},
    appendChild: function(){},
    closest:          function(){ return null; },
    querySelector:    function(){ return null; },
    querySelectorAll: function(){ return []; },
  };
}

function fakeQuerySelectorAll(selector) {
  return _queryRegistry[selector] || [];
}

var fakeDocument = {
  visibilityState: 'visible',
  addEventListener: function(){},
  body: {
    appendChild: function(){},
    prepend:     function(){},
    style:       {},
    querySelectorAll: fakeQuerySelectorAll,
  },
  documentElement: { style: {} },
  createElement:  function() { return makeFakeEl({}); },
  querySelectorAll: fakeQuerySelectorAll,
  getElementById:   function(id) { return (_queryRegistry['#' + id] || [])[0] || null; },
};

var fakeNavigator = {
  userAgent: 'node-test',
  clipboard: { writeText: function() { return Promise.resolve(); } },
};

function FakeWebSocket(url) {
  this.url = url;
  this.onmessage = null;
  this.onclose   = null;
  this.onerror   = null;
  this.readyState = 1;
  this._closed = false;
}
FakeWebSocket.prototype.close = function() {
  if (!this._closed) {
    this._closed = true;
    this.readyState = 3;
    if (this.onclose) this.onclose({});
  }
};

// ─── Assign globals BEFORE loading tw_shared.js ─────────────────────
global.localStorage           = fakeLocalStorage;
global.window                 = fakeWindow;
global.document               = fakeDocument;
global.navigator              = fakeNavigator;
global.setTimeout             = function(fn, ms) { return 0; };
global.clearTimeout           = function(){};
global.WebSocket              = FakeWebSocket;
global.requestAnimationFrame  = function(fn) { return 0; };
global.fetch                  = function() { return Promise.reject(new Error('fetch not mocked')); };

// ─── Load tw_shared.js ──────────────────────────────────────────────
// NOTE: 'use strict' is intentionally omitted at module level so that
// function declarations from eval() are accessible in this scope.
var _sharedCode = fs.readFileSync('./tw_shared.js', 'utf8');
eval(_sharedCode);

// ─── Helpers ────────────────────────────────────────────────────────

// In a browser window === global. In Node tests they are separate objects.
// tw_shared.js checks window.TwAuthSync but also uses bare `TwAuthSync`
// after the guard, so both must point to the same object.
function setTwAuthSync(auth) {
  fakeWindow.TwAuthSync = auth;
  global.TwAuthSync = auth;
}

function resetAll() {
  Object.keys(_store).forEach(function(k) { delete _store[k]; });
  _queryRegistry = {};
  _invalidateCalls.length = 0;
  fakeWindow.location.href = '';
  setTwAuthSync(null);
  global.fetch = function() { return Promise.reject(new Error('fetch not mocked')); };
}

// Flush microtask queue (loadGlobalBadges has two fetch().then().then() chains).
async function flushAll() {
  for (var i = 0; i < 12; i++) await Promise.resolve();
}

function makeJwt(payload) {
  var header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  var body   = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return header + '.' + body + '.fakesig';
}
function makeValidJwt(userId, userType) {
  var now = Math.floor(Date.now() / 1000);
  return makeJwt({ user_id: userId, user_type: userType, exp: now + 86400, iat: now });
}

var _invalidateCalls = [];

function makeFakeTwAuthSync(snap) {
  var _handlers = [];
  return {
    getSessionSnapshot: function()        { return snap; },
    onSessionChange:    function(fn)      { _handlers.push(fn); },
    invalidateSession:  function(reason, opts) {
      _invalidateCalls.push({ reason: reason, opts: opts });
      snap = { state: 'guest', isAuthenticated: false, userType: null, userId: null };
      _handlers.forEach(function(fn) { try { fn({ reason: reason, snapshot: snap }); } catch(e){} });
      if (opts && opts.redirect) fakeWindow.location.href = opts.redirect;
    },
  };
}

// ─── Test runner ────────────────────────────────────────────────────
var testsRun = 0, passed = 0;
var failures = [];
var PASS = '\x1b[32mPASS\x1b[0m';
var FAIL = '\x1b[31mFAIL\x1b[0m';

function check(name, condition, detail) {
  testsRun++;
  if (condition) {
    console.log('  ' + PASS + '  ' + name);
    passed++;
  } else {
    console.log('  ' + FAIL + '  ' + name + (detail ? ' — ' + detail : ''));
    failures.push(name);
  }
}

// ════════════════════════════════════════════════════════════════════
(async function main() {

  // ────────────────────────────────────────────────────────────────
  console.log('\n1 — Menu policy: guest session');
  resetAll();
  {
    var snap  = { state: 'guest', isAuthenticated: false, userType: null, userId: null };
    var items = _twMenuItemsForSnapshot(snap).map(function(i) { return i.key; });
    check('S01 — guest sees login',              items.indexOf('login') !== -1);
    check('S02 — guest sees register',           items.indexOf('register') !== -1);
    check('S03 — guest does NOT see settings',   items.indexOf('settings') === -1);
    check('S04 — guest does NOT see logout',     items.indexOf('logout') === -1);
    check('S05 — guest does NOT see candidates', items.indexOf('candidates') === -1);
    // Login vs Register must navigate to different URLs (VM-10 Guest Menu contract)
    var fullItems = _twMenuItemsForSnapshot(snap);
    var loginItem    = fullItems.filter(function(i) { return i.key === 'login'; })[0];
    var registerItem = fullItems.filter(function(i) { return i.key === 'register'; })[0];
    check('S05b — register href is /login#register',        registerItem && registerItem.href === '/login#register');
    check('S05c — login href is /login (plain)',             loginItem    && loginItem.href    === '/login');
    check('S05d — login and register hrefs are different',  loginItem && registerItem && loginItem.href !== registerItem.href);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n2 — Menu policy: authenticated emp session');
  resetAll();
  {
    var snap  = { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 1 };
    var items = _twMenuItemsForSnapshot(snap).map(function(i) { return i.key; });
    check('S06 — emp sees settings',           items.indexOf('settings') !== -1);
    check('S07 — emp sees logout',             items.indexOf('logout') !== -1);
    check('S08 — emp does NOT see login',      items.indexOf('login') === -1);
    check('S09 — emp does NOT see candidates', items.indexOf('candidates') === -1);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n3 — Menu policy: authenticated co session');
  resetAll();
  {
    var snap  = { state: 'authenticated', isAuthenticated: true, userType: 'co', userId: 2 };
    var items = _twMenuItemsForSnapshot(snap).map(function(i) { return i.key; });
    check('S10 — co sees candidates',    items.indexOf('candidates') !== -1);
    check('S11 — co sees settings',      items.indexOf('settings') !== -1);
    check('S12 — co does NOT see login', items.indexOf('login') === -1);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n4 — loadGlobalBadges: no TwAuthSync → no-op');
  resetAll();
  {
    var fetchCalled = false;
    global.fetch = function() { fetchCalled = true; return Promise.resolve({}); };
    setTwAuthSync(null);
    loadGlobalBadges();
    check('S13 — no TwAuthSync → fetch not called', !fetchCalled);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n5 — loadGlobalBadges: guest session → no-op');
  resetAll();
  {
    var fetchCalled = false;
    global.fetch = function() { fetchCalled = true; return Promise.resolve({}); };
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'guest', isAuthenticated: false, userType: null, userId: null }
    ));
    loadGlobalBadges();
    check('S14 — guest → fetch not called', !fetchCalled);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n6 — loadGlobalBadges: 401 on notifications → invalidateSession');
  resetAll();
  {
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');
    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1)
        return Promise.resolve({ status: 401, ok: false, json: function(){ return Promise.resolve({}); } });
      return Promise.resolve({ status: 200, ok: true, json: function(){ return Promise.resolve({ count: 0 }); } });
    };
    loadGlobalBadges();
    await flushAll();
    check('S15 — 401 on notif → invalidateSession called', _invalidateCalls.length > 0);
    check('S16 — 401 on notif → reason is api_401',
      _invalidateCalls[0] && _invalidateCalls[0].reason === 'api_401');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n7 — loadGlobalBadges: 403 on notifications → session preserved');
  resetAll();
  {
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');
    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1)
        return Promise.resolve({ status: 403, ok: false, json: function(){ return Promise.resolve({}); } });
      return Promise.resolve({ status: 200, ok: true, json: function(){ return Promise.resolve({ count: 0 }); } });
    };
    loadGlobalBadges();
    await flushAll();
    check('S17 — 403 on notif → no invalidateSession', _invalidateCalls.length === 0);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n8 — loadGlobalBadges: 401 on messages → invalidateSession');
  resetAll();
  {
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');
    global.fetch = function(url) {
      if (url.indexOf('/messages/unread/') !== -1)
        return Promise.resolve({ status: 401, ok: false, json: function(){ return Promise.resolve({}); } });
      return Promise.resolve({ status: 200, ok: true, json: function(){ return Promise.resolve({ unread: 0 }); } });
    };
    loadGlobalBadges();
    await flushAll();
    check('S18 — 401 on messages → invalidateSession called', _invalidateCalls.length > 0);
    check('S19 — 401 on messages → reason is api_401',
      _invalidateCalls[0] && _invalidateCalls[0].reason === 'api_401');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n9 — loadGlobalBadges: 403 on messages → session preserved');
  resetAll();
  {
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');
    global.fetch = function(url) {
      if (url.indexOf('/messages/unread/') !== -1)
        return Promise.resolve({ status: 403, ok: false, json: function(){ return Promise.resolve({}); } });
      return Promise.resolve({ status: 200, ok: true, json: function(){ return Promise.resolve({ unread: 0 }); } });
    };
    loadGlobalBadges();
    await flushAll();
    check('S20 — 403 on messages → no invalidateSession', _invalidateCalls.length === 0);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n10 — loadGlobalBadges: badges cleared before fetch');
  resetAll();
  {
    var notifEl = makeFakeEl({ 'data-badge': 'notif' });
    notifEl.textContent = '5';
    notifEl.style.display = 'inline-block';
    var msgsEl = makeFakeEl({ 'data-badge': 'msgs' });
    msgsEl.textContent = '3';
    msgsEl.style.display = 'inline-block';
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"]'] = [notifEl, msgsEl];
    _queryRegistry['[data-badge="notif"]'] = [notifEl];
    _queryRegistry['[data-badge="msgs"]']  = [msgsEl];

    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');

    var clearObservedNotif = null;
    var clearObservedMsgs  = null;
    global.fetch = function(url) {
      // Snapshot display state at fetch time — must already be cleared
      if (clearObservedNotif === null) {
        clearObservedNotif = notifEl.style.display;
        clearObservedMsgs  = msgsEl.style.display;
      }
      return Promise.resolve({
        status: 200, ok: true,
        json: function() { return Promise.resolve({ unread: 1, count: 1 }); }
      });
    };

    loadGlobalBadges();  // must clear badges, THEN call fetch

    check('S21 — notif badge cleared before fetch', clearObservedNotif === 'none');
    check('S22 — msgs badge cleared before fetch',  clearObservedMsgs  === 'none');
    await flushAll();
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n11 — _badgeGeneration guard: stale response not written after stop');
  resetAll();
  {
    var notifEl = makeFakeEl({ 'data-badge': 'notif' });
    notifEl.textContent = '';
    notifEl.style.display = 'none';
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"]'] = [notifEl];
    _queryRegistry['[data-badge="notif"]'] = [notifEl];
    _queryRegistry['[data-badge="msgs"]']  = [];

    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 1 }
    ));
    _store['tw_jwt'] = makeValidJwt(1, 'emp');

    // Notifications response is slow — we control when it resolves
    var resolveNotif;
    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1) {
        return new Promise(function(resolve) {
          resolveNotif = function() {
            resolve({
              status: 200, ok: true,
              json: function() { return Promise.resolve({ unread: 99 }); }
            });
          };
        });
      }
      return Promise.resolve({
        status: 200, ok: true,
        json: function() { return Promise.resolve({ count: 0 }); }
      });
    };

    loadGlobalBadges();  // captures gen = N, starts slow notif fetch

    // Simulate account switch: _twBadgeWsStop() increments _badgeGeneration
    if (typeof fakeWindow._twBadgeWsStop === 'function') fakeWindow._twBadgeWsStop();

    // Now the stale response from old account arrives
    if (resolveNotif) resolveNotif();
    await flushAll();

    // notifEl must NOT have been updated with stale data (99)
    check('S23 — stale generation response not written to badge',
      notifEl.textContent !== '99');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n12 — twLogout fallback: allowlist only (not startsWith tw_)');
  resetAll();
  {
    setTwAuthSync(null);  // force fallback path (no TwAuthSync)
    fakeWindow.location.href = '/original';
    _store['tw_jwt']         = 'token123';
    _store['tw_user']        = JSON.stringify({ id: 1 });
    _store['tw_cover_edu_1'] = 'data:image/png;...';
    _store['app_theme']      = 'dark';
    _store['tw_prefs']       = 'some-preference';  // must NOT be deleted

    twLogout();

    check('S24 — fallback removes tw_jwt',            fakeLocalStorage.getItem('tw_jwt')         === null);
    check('S25 — fallback removes tw_user',           fakeLocalStorage.getItem('tw_user')        === null);
    check('S26 — fallback preserves tw_cover_edu_1',  fakeLocalStorage.getItem('tw_cover_edu_1') !== null);
    check('S27 — fallback preserves app_theme',       fakeLocalStorage.getItem('app_theme')       !== null);
    check('S28 — fallback preserves tw_prefs',        fakeLocalStorage.getItem('tw_prefs')        !== null);
    check('S29 — fallback redirects to /login',       fakeWindow.location.href === '/login');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n13 — twLogout: uses TwAuthSync.invalidateSession when available');
  resetAll();
  {
    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 1 }
    ));
    twLogout();
    check('S30 — TwAuthSync path calls invalidateSession', _invalidateCalls.length > 0);
    check('S31 — reason is logout',  _invalidateCalls[0] && _invalidateCalls[0].reason === 'logout');
    check('S32 — redirect to /login', fakeWindow.location.href === '/login');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n' + '='.repeat(55));
  console.log('Tests run: ' + testsRun + '  |  Passed: ' + passed + '  |  Failed: ' + (testsRun - passed));
  if (failures.length) {
    console.log('\nFailed:');
    failures.forEach(function(f) { console.log('  - ' + f); });
    process.exit(1);
  } else {
    console.log('All runtime checks passed.');
    process.exit(0);
  }

})();
