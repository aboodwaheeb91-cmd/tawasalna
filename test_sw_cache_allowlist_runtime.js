'use strict';
/**
 * test_sw_cache_allowlist_runtime.js — runtime tests for the Service Worker
 * cache allowlist + session-end cache wipe (security/sw-cache-allowlist).
 * Runs the REAL sw.js / auth-sync.js / tw_shared.js code in Node `vm` with fakes.
 *
 * Run: node test_sw_cache_allowlist_runtime.js
 */
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond) {
  if (cond) { passed++; console.log('  ✓ ' + name); }
  else      { failed++; console.log('  ✗ ' + name); }
}
const flush = () => new Promise(r => setTimeout(r, 0));

// ─── 1. sw.js fetch handler ─────────────────────────────────────────
const ORIGIN = 'https://tawasolna.com';
function loadSw() {
  const listeners = {};
  const puts = [];
  const cacheObj = { put(req) { puts.push(req.url); return Promise.resolve(); },
                     addAll() { return Promise.resolve(); } };
  const ctx = {
    self: { location: { origin: ORIGIN }, addEventListener(t, fn) { listeners[t] = fn; },
            skipWaiting() {}, clients: { claim() {} }, registration: {} },
    caches: { open() { return Promise.resolve(cacheObj); }, match() { return Promise.resolve(undefined); },
              keys() { return Promise.resolve([]); }, delete() { return Promise.resolve(true); } },
    fetch() { return Promise.resolve({ status: 200, type: 'basic', clone() { return this; } }); },
    URL, Response: function (b, o) { this.status = o && o.status; },
    clients: { openWindow(u) { ctx._opened = u; return Promise.resolve(); } },
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('./sw.js', 'utf8'), ctx);
  return { listeners, puts, ctx };
}
function makeReq(path, opts) {
  opts = opts || {};
  const headers = opts.headers || {};
  return { url: (opts.origin || ORIGIN) + path, method: opts.method || 'GET',
           mode: opts.mode || 'cors', destination: opts.destination || '',
           headers: { has(k) { return Object.keys(headers).some(h => h.toLowerCase() === k.toLowerCase()); } } };
}
async function dispatch(sw, req) {
  let responded = false, p = null;
  sw.listeners.fetch({ request: req, respondWith(x) { responded = true; p = x; } });
  if (p) await p;
  await flush(); await flush();
  return responded;
}

async function testSw() {
  console.log('\n[sw.js] fetch allowlist');
  let sw = loadSw();
  let r = await dispatch(sw, makeReq('/home/feed?filter=all'));
  check('/home/feed → no respondWith (network only)', r === false);
  check('/home/feed → no cache.put', sw.puts.length === 0);

  sw = loadSw();
  await dispatch(sw, makeReq('/static/x.css', { destination: 'style', headers: { Authorization: 'Bearer t' } }));
  check('request with Authorization header → no cache.put', sw.puts.length === 0);

  sw = loadSw();
  for (const p of ['/company/saved-candidates/5', '/api/appointments/1', '/my/applications', '/mention/search?q=a'])
    await dispatch(sw, makeReq(p));
  check('private API endpoints (not in any list) → no cache.put', sw.puts.length === 0);

  sw = loadSw();
  await dispatch(sw, makeReq('/static/x.png', { destination: '' }));
  check('/static/ path with empty destination (fetch/XHR) → no cache.put', sw.puts.length === 0);

  sw = loadSw();
  await dispatch(sw, makeReq('/static/x.css', { destination: 'style', origin: 'https://evil.com' }));
  check('cross-origin static → no cache.put', sw.puts.length === 0);

  sw = loadSw();
  r = await dispatch(sw, makeReq('/static/x.css', { destination: 'style' }));
  check('/static/x.css (style) → respondWith + cache.put', r === true && sw.puts.indexOf(ORIGIN + '/static/x.css') !== -1);

  sw = loadSw();
  await dispatch(sw, makeReq('/icon-192.png', { destination: 'image' }));
  await dispatch(sw, makeReq('/manifest.json', { destination: 'manifest' }));
  check('/icon-192.png + /manifest.json → cached', sw.puts.length === 2);

  sw = loadSw();
  await dispatch(sw, makeReq('/messages', { mode: 'navigate', destination: 'document' }));
  check('HTML navigation → no cache.put', sw.puts.length === 0);

  console.log('\n[sw.js] notificationclick');
  const urls = { '/messages?c=1': '/messages?c=1', '//evil.com': '/', '/\\evil.com': '/',
                 'https://evil.com': '/', 'javascript:alert(1)': '/', undefined: '/' };
  for (const [inp, exp] of Object.entries(urls)) {
    sw = loadSw();
    sw.listeners.notificationclick({ notification: { close() {}, data: { url: inp === 'undefined' ? undefined : inp } },
                                     waitUntil() {} });
    check('notificationclick ' + JSON.stringify(inp) + ' → ' + exp, sw.ctx._opened === exp);
  }
}

// ─── 2. auth-sync.js invalidateSession → shared helper ──────────────
function testAuthSync() {
  console.log('\n[auth-sync.js] invalidateSession');
  const store = { tw_jwt: 'x.y.z', tw_user: '{"id":1}' };
  let helperCalls = 0;
  const win = { location: { href: '' }, addEventListener() {},
                twClearAppCaches() { helperCalls++; return Promise.resolve(); } };
  const ctx = {
    window: win, document: { addEventListener() {} }, console, JSON, Math, Date, String,
    setTimeout, clearTimeout, atob: s => Buffer.from(s, 'base64').toString(),
    localStorage: { getItem: k => (k in store ? store[k] : null), removeItem: k => { delete store[k]; } },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('./static/shared/auth-sync.js', 'utf8'), ctx);
  win.TwAuthSync.invalidateSession('logout', { redirect: '/login' });
  check('invalidateSession calls window.twClearAppCaches once', helperCalls === 1);
  check('invalidateSession still redirects', win.location.href === '/login');
  check('session keys removed', !('tw_jwt' in store) && !('tw_user' in store));

  win.twClearAppCaches = () => { throw new Error('boom'); };
  win.location.href = '';
  const origWarn = console.warn; console.warn = () => {};
  win.TwAuthSync.invalidateSession('logout', { redirect: '/login' });
  console.warn = origWarn;
  check('helper throwing does not block redirect', win.location.href === '/login');
}

// ─── 3. tw_shared.js helper + twLogout fallback (real code) ─────────
function extractFn(src, name) {
  const start = src.indexOf('function ' + name + '(');
  let i = src.indexOf('{', start), depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}' && --depth === 0) break;
  }
  return src.slice(start, i + 1);
}
async function testTwShared() {
  console.log('\n[tw_shared.js] twClearAppCaches + twLogout fallback');
  const src = fs.readFileSync('./tw_shared.js', 'utf8');
  const deleted = [];
  const ctx = {
    window: { location: { href: '' } }, console,
    caches: { keys: () => Promise.resolve(['tawasolna-v5-old', 'other']),
              delete: k => { deleted.push(k); return Promise.resolve(true); } },
    localStorage: { removeItem() {} },
  };
  vm.createContext(ctx);
  vm.runInContext(extractFn(src, 'twClearAppCaches') + '\n' + extractFn(src, 'twLogout'), ctx);
  await ctx.twClearAppCaches();
  check('twClearAppCaches deletes every cache key', deleted.length === 2);

  deleted.length = 0;
  ctx.twLogout();  // no TwAuthSync → fallback branch
  check('twLogout fallback redirects synchronously', ctx.window.location.href === '/login');
  await flush(); await flush();
  check('twLogout fallback clears caches via the same helper', deleted.length === 2);

  ctx.caches = undefined;
  let ok = true;
  try { await ctx.twClearAppCaches(); } catch (e) { ok = false; }
  check('no Cache API → resolves without throwing', ok);
}

(async () => {
  await testSw();
  testAuthSync();
  await testTwShared();
  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
