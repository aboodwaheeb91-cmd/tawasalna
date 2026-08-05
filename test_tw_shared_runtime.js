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
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]'] = [notifEl, msgsEl];
    _queryRegistry['[data-badge="notif"],[data-ah-notif-badge]'] = [notifEl];
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
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]'] = [notifEl];
    _queryRegistry['[data-badge="notif"],[data-ah-notif-badge]'] = [notifEl];
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
  console.log('\n14 — company.main.js static checks (T01–T02)');
  {
    var coMainCode = fs.readFileSync('./static/company/company.main.js', 'utf8');

    check('T01 — company.main.js no dangling window.toggleMenu export',
      !/window\.toggleMenu\s*=\s*toggleMenu/.test(coMainCode));
    check('T02 — company.main.js retains doLogout + initGlobalHeaderMenu calls',
      coMainCode.indexOf('doLogout') !== -1 && coMainCode.indexOf('initGlobalHeaderMenu') !== -1);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n15 — _bindBadgeAuthSync lifecycle (T03–T04)');
  // NOTE: _badgeAuthSyncBound persists across tests (IIFE private).
  // T03 must run before any other test that fires window.load with TwAuthSync set.
  {
    var t03HandlerCount = 0;
    setTwAuthSync({
      getSessionSnapshot: function() {
        return { state: 'guest', isAuthenticated: false, userType: null, userId: null };
      },
      onSessionChange: function(fn) { t03HandlerCount++; },
      invalidateSession: function() {},
    });

    // Fire window.load listeners — triggers _bindBadgeAuthSync() retry inside the IIFE
    var loadFns = _windowListeners['load'] || [];
    loadFns.forEach(function(fn) { try { fn(); } catch(e){} });

    check('T03 — window.load fires _bindBadgeAuthSync, registers onSessionChange',
      t03HandlerCount >= 1);

    // T04: fire load listeners AGAIN — _badgeAuthSyncBound=true → no double registration
    var prevCount = t03HandlerCount;
    loadFns.forEach(function(fn) { try { fn(); } catch(e){} });
    check('T04 — _bindBadgeAuthSync idempotent (double window.load does not register twice)',
      t03HandlerCount === prevCount);

    resetAll();
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n16 — Badge WS exposed globals exist (T05–T06)');
  {
    check('T05 — window._twBadgeWsStop is a callable global',
      typeof fakeWindow._twBadgeWsStop === 'function');
    check('T06 — window._twBadgeWsStart is a callable global',
      typeof fakeWindow._twBadgeWsStart === 'function');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n17 — data-ah-notif-badge receives count + zero hides badge (T07–T09)');
  resetAll();
  {
    // T07: Legacy data-ah-notif-badge element receives notification count
    var legacyBadge = makeFakeEl({ 'data-ah-notif-badge': '' });
    legacyBadge.textContent = '';
    legacyBadge.style.display = 'none';
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]'] = [legacyBadge];
    _queryRegistry['[data-badge="notif"],[data-ah-notif-badge]'] = [legacyBadge];
    _queryRegistry['[data-badge="notif"]'] = [];
    _queryRegistry['[data-badge="msgs"]']  = [];

    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');

    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1)
        return Promise.resolve({ status: 200, ok: true,
          json: function() { return Promise.resolve({ unread: 4 }); } });
      return Promise.resolve({ status: 200, ok: true,
        json: function() { return Promise.resolve({ count: 0 }); } });
    };

    loadGlobalBadges();
    await flushAll();

    check('T07 — data-ah-notif-badge element receives notification count',
      legacyBadge.textContent === '4' && legacyBadge.style.display === 'inline-block');
  }

  // T08: 401 from notif fetch bumps _badgeGeneration → sibling msgs write blocked
  resetAll();
  {
    var msgsElT08 = makeFakeEl({ 'data-badge': 'msgs' });
    msgsElT08.textContent = '';
    msgsElT08.style.display = 'none';
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]'] = [msgsElT08];
    _queryRegistry['[data-badge="notif"],[data-ah-notif-badge]'] = [];
    _queryRegistry['[data-badge="notif"]'] = [];
    _queryRegistry['[data-badge="msgs"]']  = [msgsElT08];

    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');

    // Notif returns 401 → _on401() bumps _badgeGeneration
    // Msgs returns 200 with count=7 → _guardOk() fails → NOT written
    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1)
        return Promise.resolve({ status: 401, ok: false,
          json: function() { return Promise.resolve({}); } });
      return new Promise(function(resolve) {
        // Msgs resolves after notif 401 is processed
        resolve({ status: 200, ok: true,
          json: function() { return Promise.resolve({ count: 7 }); } });
      });
    };

    loadGlobalBadges();
    await flushAll();

    check('T08 — 401 from notif fetch (_on401) prevents sibling msgs from writing DOM',
      msgsElT08.textContent !== '7');
  }

  // T09: Zero count → badge stays hidden (display: none)
  resetAll();
  {
    var zeroNotifEl = makeFakeEl({ 'data-badge': 'notif' });
    zeroNotifEl.textContent = '9';  // stale value
    zeroNotifEl.style.display = 'inline-block';
    _queryRegistry['[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]'] = [zeroNotifEl];
    _queryRegistry['[data-badge="notif"],[data-ah-notif-badge]'] = [zeroNotifEl];
    _queryRegistry['[data-badge="notif"]'] = [zeroNotifEl];
    _queryRegistry['[data-badge="msgs"]']  = [];

    setTwAuthSync(makeFakeTwAuthSync(
      { state: 'authenticated', isAuthenticated: true, userType: 'emp', userId: 5 }
    ));
    _store['tw_jwt'] = makeValidJwt(5, 'emp');

    global.fetch = function(url) {
      if (url.indexOf('/notifications/') !== -1)
        return Promise.resolve({ status: 200, ok: true,
          json: function() { return Promise.resolve({ unread: 0 }); } });
      return Promise.resolve({ status: 200, ok: true,
        json: function() { return Promise.resolve({ count: 0 }); } });
    };

    loadGlobalBadges();
    await flushAll();

    check('T09 — zero unread count → notif badge hidden (display: none)',
      zeroNotifEl.style.display === 'none');
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n18 — File content guards: allowlist, no startsWith (T10–T13)');
  {
    var indexAuthCode = fs.readFileSync('./index.auth.js', 'utf8');
    var appHeaderCode = fs.readFileSync('./static/app-header.js', 'utf8');

    // Strip pure comment lines (those whose first non-space chars are //)
    // so that warning comments like "never startsWith('tw_')" don't false-positive
    function codeOnly(src) {
      return src.split('\n').filter(function(line) {
        return !/^\s*\/\//.test(line);
      }).join('\n');
    }
    var indexAuthCodeOnly = codeOnly(indexAuthCode);
    var appHeaderCodeOnly = codeOnly(appHeaderCode);

    // T10: index.auth.js removes ONLY tw_jwt + tw_user (no startsWith scan in code)
    check('T10 — index.auth.js clears only tw_jwt + tw_user (no startsWith scan)',
      indexAuthCodeOnly.indexOf("startsWith('tw_')") === -1 &&
      indexAuthCodeOnly.indexOf('startsWith("tw_")') === -1 &&
      indexAuthCode.indexOf("removeItem('tw_jwt')") !== -1 &&
      indexAuthCode.indexOf("removeItem('tw_user')") !== -1);

    // T11: No startsWith('tw_') in code lines of either file
    check('T11a — index.auth.js: no startsWith(tw_) in code',
      indexAuthCodeOnly.indexOf("startsWith('tw_')") === -1 &&
      indexAuthCodeOnly.indexOf('startsWith("tw_")') === -1);
    check('T11b — app-header.js: no startsWith(tw_) in code',
      appHeaderCodeOnly.indexOf("startsWith('tw_')") === -1 &&
      appHeaderCodeOnly.indexOf('startsWith("tw_")') === -1);

    // T12: app-header.js fail-closed removes both session keys
    check('T12 — app-header.js fail-closed removes tw_jwt',
      appHeaderCode.indexOf("removeItem('tw_jwt')") !== -1 ||
      appHeaderCode.indexOf('removeItem("tw_jwt")') !== -1);

    // T13: redirect in app-header fallback comes AFTER key removal (order in source)
    var ahFallback = appHeaderCode.split('Last-resort fallback')[1] || '';
    var ahRemoveIdx   = ahFallback.indexOf("removeItem('tw_jwt')");
    var ahRedirectIdx = ahFallback.indexOf("location.replace('/login')");
    check('T13 — app-header.js fallback redirects after key removal',
      ahRemoveIdx !== -1 && ahRedirectIdx !== -1 && ahRemoveIdx < ahRedirectIdx);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n19 — #533 / #534 test coverage files exist (T14)');
  {
    var wsTestExists = fs.existsSync('./test_ws_security.py') ||
                       fs.existsSync('./test_ws_behavioral.py');
    check('T14 — WS security/behavioral test files present (#533/#534)',
      wsTestExists);
  }

  // ────────────────────────────────────────────────────────────────
  console.log('\n20 — index.auth.js login path: storage contract (T15–T16)');
  {
    // Load index.auth.js; strip 'use strict' so var declarations (doLogin, _submitting, …)
    // are promoted to the current scope — same eval pattern as tw_shared.js at the top.
    var _authSrc = fs.readFileSync('./index.auth.js', 'utf8')
      .replace(/^['"]use strict['"];\s*\n/m, '');
    // toast is defined in index.ui.js in the browser; provide a no-op for this isolated test
    global.toast = function(){};
    eval(_authSrc);
    // doLogin, redirect, _submitting, … are now in scope

    // T15: Successful login writes only tw_user + tw_jwt — all other keys preserved
    {
      resetAll();
      _store['tw_cover_test'] = 'cover-url-value';
      _store['tw_prefs']      = '{"theme":"dark"}';
      _store['app_theme']     = 'dark';

      var _me15  = { value: 'user@example.com', setAttribute: function(){} };
      var _mp15  = { value: 'password123',      setAttribute: function(){} };
      var _mb15  = { classList: { add: function(){}, remove: function(){} },
                     textContent: '', disabled: false };
      fakeDocument.getElementById = function(id) {
        if (id === 'lEmail')   return _me15;
        if (id === 'lPass')    return _mp15;
        if (id === 'loginBtn') return _mb15;
        return null;
      };
      fakeDocument.querySelector = function() { return null; };
      global.fetch = function() {
        return Promise.resolve({
          ok: true, status: 200,
          json: function() { return Promise.resolve({
            user:  { id: 42, tw_id: 'U9620abc', user_type: 'emp' },
            token: 'fresh.jwt.token',
          }); },
        });
      };

      await doLogin();

      check('T15  login success: preserves tw_cover_test',
        _store['tw_cover_test'] === 'cover-url-value');
      check('T15b login success: preserves tw_prefs',
        _store['tw_prefs'] === '{"theme":"dark"}');
      check('T15c login success: writes tw_user + tw_jwt',
        !!_store['tw_user'] && _store['tw_jwt'] === 'fresh.jwt.token');
    }

    // T16: Storage quota failure → tw_user + tw_jwt rolled back (neither persisted)
    {
      resetAll();
      _submitting = false;   // reset double-submit guard left true by T15 success path
      _store['tw_cover_test'] = 'cover-url-value';

      var _me16  = { value: 'user@example.com', setAttribute: function(){} };
      var _mp16  = { value: 'password123',      setAttribute: function(){} };
      var _mb16  = { classList: { add: function(){}, remove: function(){} },
                     textContent: '', disabled: false };
      var _err16 = { setAttribute: function(){}, removeAttribute: function(){},
                     querySelector: function(){ return null; } };
      fakeDocument.getElementById = function(id) {
        if (id === 'lEmail')       return _me16;
        if (id === 'lPass')        return _mp16;
        if (id === 'loginBtn')     return _mb16;
        if (id === 'l-form-error') return _err16;
        return null;
      };
      fakeDocument.querySelector = function() { return null; };
      global.fetch = function() {
        return Promise.resolve({
          ok: true, status: 200,
          json: function() { return Promise.resolve({
            user:  { id: 42, tw_id: 'U9620abc', user_type: 'emp' },
            token: 'fresh.jwt.token',
          }); },
        });
      };
      // Simulate storage quota exceeded
      fakeLocalStorage.setItem = function() {
        throw new Error('QuotaExceededError: DOM Exception 22');
      };

      await doLogin();

      check('T16  storage failure: tw_user rolled back (absent)',
        !('tw_user' in _store));
      check('T16b storage failure: tw_jwt rolled back (absent)',
        !('tw_jwt' in _store));

      // Restore setItem for subsequent tests
      fakeLocalStorage.setItem = function(k, v) { _store[k] = String(v); };
      _submitting = false;
    }
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
