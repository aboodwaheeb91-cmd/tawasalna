/**
 * test_tw_api_runtime.js — twApi (API Client, PR 3A · SYSTEMS_INDEX §45a), real tw_shared.js code in vm.
 *   A — success: new {ok, data} + legacy shapes (list, status:success, "pong")
 *   B — errors: {ok:false, error:{code,message,field?}} · {error:"..."} · {detail:{message}} · {ok:false, code, message}
 *   C — 401 with the user's JWT → TwAuthSync.invalidateSession('api_401') once; auth:false → never
 *   D — timeout · network down · never rejects
 *   E — appointments.html uses twApi (no direct fetch)
 *   F — report only: direct fetch( count per frontend file (never fails)
 * Run: node tests/test_tw_api_runtime.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ✅ ' + name); }
  else { fail++; console.log('  ❌ ' + name + (extra !== undefined ? ' → ' + JSON.stringify(extra) : '')); }
}

// ── sandbox (window === global, like a browser) ──
const store = {};
const invalidations = [];
const sb = {
  console, setTimeout, clearTimeout, Promise, JSON, Object, Array, Number, String, Math, Date,
  AbortController, URLSearchParams, Blob,
  localStorage: {
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  },
  document: { addEventListener() {}, querySelectorAll: () => [], body: { appendChild() {} } },
  navigator: { userAgent: 'node' },
  location: { href: '', pathname: '/x', search: '' },
  addEventListener() {},
  requestAnimationFrame() {},
  TwAuthSync: {
    getSessionSnapshot: () => ({ isAuthenticated: !!store.tw_jwt }),
    invalidateSession: reason => { invalidations.push(reason); delete store.tw_jwt; delete store.tw_user; },
  },
};
sb.window = sb;
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'tw_shared.js'), 'utf8'), sb);

let lastInit = null;
function respond(status, body) {
  sb.fetch = (url, init) => {
    lastInit = init;
    const txt = typeof body === 'string' ? body : JSON.stringify(body);
    return Promise.resolve({ ok: status >= 200 && status < 300, status, text: () => Promise.resolve(txt) });
  };
}

(async () => {
  console.log('\nA — success shapes');
  store.tw_jwt = 'JWT-A';
  respond(200, { ok: true, data: [{ id: 1 }], total: 5 });
  let r = await sb.twApi('/api/x');
  check('A1 new shape → ok, data = body.data, error null', r.ok && r.status === 200 && r.data[0].id === 1 && r.error === null);
  check('A2 raw keeps list meta (total)', r.raw.total === 5);
  check('A3 Authorization from getAuthHeaders', lastInit.headers.Authorization === 'Bearer JWT-A' && lastInit.method === 'GET');
  respond(200, [1, 2]);
  r = await sb.twApi('/api/list');
  check('A4 legacy bare list → data = whole body', r.ok && Array.isArray(r.data) && r.data.length === 2);
  respond(200, { status: 'success', items: [3] });
  r = await sb.twApi('/api/legacy');
  check('A5 legacy {status:success} → data = whole body', r.ok && r.data.items[0] === 3);
  respond(200, '"pong"');
  r = await sb.twApi('/ping', { auth: false });
  check('A6 "pong" → data string · auth:false sends no Authorization', r.ok && r.data === 'pong' && !lastInit.headers.Authorization);
  respond(201, { ok: true, data: { id: 9 } });
  r = await sb.twApi('/api/x', { method: 'post', body: { a: 1 } });
  check('A7 object body → JSON + Content-Type, method upper-cased',
    r.ok && r.data.id === 9 && lastInit.method === 'POST' && lastInit.body === '{"a":1}'
    && lastInit.headers['Content-Type'] === 'application/json');

  console.log('\nB — error shapes');
  respond(422, { ok: false, error: { code: 'invalid_url', message: 'رابط غير صالح', field: 'url' } });
  r = await sb.twApi('/api/x');
  check('B1 new error with field → fieldErrors', !r.ok && r.status === 422 && r.error.fieldErrors[0].field === 'url'
    && sb.twApiMessage(r, 'x') === 'رابط غير صالح');
  respond(403, { ok: false, error: { code: 'forbidden', message: 'ممنوع' } });
  r = await sb.twApi('/api/x');
  check('B2 new error without field → generalError', r.error.generalError.code === 'forbidden' && sb.twApiMessage(r) === 'ممنوع');
  respond(404, { error: 'غير موجود' });
  r = await sb.twApi('/api/x');
  check('B3 legacy string error', !r.ok && sb.twApiMessage(r, 'x') === 'غير موجود' && r.data === null);
  respond(400, { error: 'x', detail: { status: 400, message: 'رسالة dict' } });
  r = await sb.twApi('/api/x');
  check('B4 legacy dict detail', sb.twApiMessage(r, 'f') === 'رسالة dict');
  respond(409, { ok: false, code: 'pipeline_entry_required', message: 'لازم مرحلة' });
  r = await sb.twApi('/api/x');
  check('B5 legacy {ok:false, code, message}', r.error.generalError.code === 'pipeline_entry_required' && sb.twApiMessage(r) === 'لازم مرحلة');
  respond(200, { ok: false, error: 'فشل' });
  r = await sb.twApi('/api/x');
  check('B6 HTTP 200 with ok:false → ok:false', !r.ok && sb.twApiMessage(r) === 'فشل');
  respond(502, '<html>bad gateway</html>');
  r = await sb.twApi('/api/x');
  check('B7 non-JSON error body → fallback text, no HTML', !r.ok && sb.twApiMessage(r, 'تعذّر') === 'تعذّر');

  console.log('\nC — 401');
  store.tw_jwt = 'JWT-C'; invalidations.length = 0;
  respond(401, { error: 'انتهت الجلسة' });
  const [x1, x2] = await Promise.all([sb.twApi('/api/a'), sb.twApi('/api/b')]);
  check('C1 two parallel 401 → invalidateSession(api_401) once', invalidations.length === 1 && invalidations[0] === 'api_401', invalidations);
  check('C2 401 result is ok:false with status 401', !x1.ok && x1.status === 401 && x2.status === 401);
  store.tw_jwt = 'JWT-D'; invalidations.length = 0;
  r = await sb.twApi('/auth/login', { auth: false });
  check('C3 401 on auth:false request → no invalidation', invalidations.length === 0 && store.tw_jwt === 'JWT-D');
  sb.fetch = () => { store.tw_jwt = 'JWT-NEW'; return Promise.resolve({ ok: false, status: 401, text: () => Promise.resolve('') }); };
  r = await sb.twApi('/api/a');
  check('C4 401 for an old JWT after a new login → new session kept', invalidations.length === 0 && store.tw_jwt === 'JWT-NEW');

  console.log('\nD — timeout / network');
  sb.fetch = (u, init) => new Promise((_, rej) => init.signal.addEventListener('abort', () => rej(new Error('AbortError'))));
  r = await sb.twApi('/api/slow', { timeout: 20 });
  check('D1 timeout → ok:false status 0 code timeout (Arabic)', !r.ok && r.status === 0
    && r.error.generalError.code === 'timeout' && /مهلة/.test(r.error.generalError.message));
  sb.fetch = () => Promise.reject(new TypeError('Failed to fetch'));
  let threw = false;
  try { r = await sb.twApi('/api/x'); } catch (e) { threw = true; }
  check('D2 network down → resolves ok:false code network (Arabic), no exception',
    !threw && !r.ok && r.status === 0 && r.error.generalError.code === 'network' && /الاتصال/.test(sb.twApiMessage(r)));

  console.log('\nE — appointments.html (reference page)');
  const html = fs.readFileSync(path.join(__dirname, '..', 'appointments.html'), 'utf8');
  const js = html.slice(html.lastIndexOf('<script>')).replace(/^\s*\/\/.*$/gm, '');
  check('E1 uses twApi + twApiMessage', /twApi\('\/api\/appointments/.test(js) && /twApiMessage\(/.test(js));
  check('E2 no direct fetch / local api() / getAuthHeaders', !/\bfetch\(|function api\(|getAuthHeaders/.test(js));

  console.log('\nF — direct fetch( report (API Client Rule — report only, never fails)');
  const skip = /^(test_|sw\.js$|tw_shared\.js$)|node_modules|vendor|\.git\//;
  const rows = [];
  (function walk(dir) {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, f.name), rel = path.relative(path.join(__dirname, '..'), p);
      if (skip.test(f.name) || skip.test(rel + (f.isDirectory() ? '/' : ''))) continue;
      if (f.isDirectory()) { if (!f.name.startsWith('.') && f.name !== 'docs') walk(p); continue; }
      if (!/\.(html|js)$/.test(f.name)) continue;
      const n = (fs.readFileSync(p, 'utf8').match(/\bfetch\(/g) || []).length;
      if (n) rows.push([rel, n]);
    }
  })(path.join(__dirname, '..'));
  rows.sort((a, b) => b[1] - a[1]);
  rows.forEach(([f, n]) => console.log('  ' + String(n).padStart(4) + '  ' + f));
  console.log('  ── ' + rows.length + ' files · ' + rows.reduce((s, r) => s + r[1], 0) + ' direct fetch( calls left');

  console.log('\n' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail ? 1 : 0);
})();
