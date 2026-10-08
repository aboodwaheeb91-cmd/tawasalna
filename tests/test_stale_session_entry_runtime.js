/**
 * test_stale_session_entry_runtime.js — fix/stale-session-entry-redirect
 * Runs the REAL tw_shared.js + static/shared/auth-sync.js + index.auth.js in a
 * Node vm context and checks the Auth Gateway on-load entry check:
 *   - expired JWT  → no redirect + tw_jwt/tw_user cleared (stale_entry)
 *   - valid JWT    → redirect to twAccountHref() = /u/{tw_id}
 *
 * Run: node tests/test_stale_session_entry_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name); }
}

function b64url(obj) {
  return Buffer.from(JSON.stringify(obj)).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function makeJwt(claims) { return b64url({ alg: 'HS256' }) + '.' + b64url(claims) + '.sig'; }

const SRC = ['tw_shared.js', 'static/shared/auth-sync.js', 'index.auth.js']
  .map(f => fs.readFileSync(f, 'utf8'));

function runEntry(store) {
  const nav = { replaced: null, href: '' };
  const ls = {
    getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  };
  const noop = () => {};
  const doc = {
    visibilityState: 'visible', addEventListener: noop,
    getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, classList: { add: noop } }),
    body: { appendChild: noop, classList: { add: noop } },
    documentElement: { style: {} },
  };
  const ctx = {
    localStorage: ls, document: doc, console,
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    setTimeout: () => 0, clearTimeout: noop, setInterval: () => 0, clearInterval: noop,
    navigator: { userAgent: 'node' }, JSON, Math, Date, Number, String, Object, Array, isFinite,
    encodeURIComponent,
  };
  ctx.window = ctx;
  ctx.addEventListener = noop;
  ctx.location = {
    protocol: 'http:', host: 'x', pathname: '/login',
    replace: u => { nav.replaced = u; },
    set href(u) { nav.href = u; }, get href() { return nav.href; },
  };
  vm.createContext(ctx);
  SRC.forEach(code => vm.runInContext(code, ctx));
  return nav;
}

const now = Math.floor(Date.now() / 1000);
const user = { id: 7, tw_id: 'U9620abcdef1234', user_type: 'emp' };

console.log('\nstale-session entry check (index.auth.js on-load)');

// 1. Expired JWT → no redirect, session keys cleared, preferences kept
{
  const store = {
    tw_user: JSON.stringify(user),
    tw_jwt: makeJwt({ user_id: 7, user_type: 'emp', exp: now - 60 }),
    tw_prefs: 'keep',
  };
  const nav = runEntry(store);
  check('expired JWT → no redirect', nav.replaced === null && nav.href === '');
  check('expired JWT → tw_jwt + tw_user cleared, tw_prefs kept',
    !('tw_jwt' in store) && !('tw_user' in store) && store.tw_prefs === 'keep');
}

// 2. Valid JWT → redirect to the unified destination /u/{tw_id}
{
  const store = {
    tw_user: JSON.stringify(user),
    tw_jwt: makeJwt({ user_id: 7, user_type: 'emp', exp: now + 3600 }),
  };
  const nav = runEntry(store);
  check('valid JWT → redirect to /u/{tw_id}', nav.replaced === '/u/' + user.tw_id);
  check('valid JWT → session kept', 'tw_jwt' in store && 'tw_user' in store);
}

console.log('\nTests run: ' + (passed + failed) + '  |  Passed: ' + passed + '  |  Failed: ' + failed);
process.exit(failed ? 1 : 0);
