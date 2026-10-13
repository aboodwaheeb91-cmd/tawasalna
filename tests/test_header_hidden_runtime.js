/**
 * test_header_hidden_runtime.js — HNAV-09 (PR 4.10 · docs/design-system/HEADER-NAV.md)
 *
 * Mounts the REAL unified header + bottom nav (tw_shared.js → twMountAppChrome,
 * auth-sync.js, static/app-header.css) in headless Chrome, once as a signed-in
 * account and once as a guest, and reads getComputedStyle — not just the `hidden`
 * attribute: every data-tw-session element of the other state must be display:none.
 *
 * Browser: $CHROME_BIN · /opt/pw-browsers/chromium · google-chrome · chromium (no npm deps).
 * None found → SKIP locally, FAIL under CI (CI=true — ubuntu-latest ships google-chrome).
 *
 * Run: node tests/test_header_hidden_runtime.js
 */
'use strict';
const fs = require('fs');
const http = require('http');
const path = require('path');
const { execFile, execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
let failures = 0;
function check(name, cond, detail) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + name + (cond ? '' : '  [' + (detail || '') + ']'));
  if (!cond) failures++;
}

function findChrome() {
  const cands = [process.env.CHROME_BIN, '/opt/pw-browsers/chromium'].filter(Boolean);
  for (const c of cands) if (fs.existsSync(c)) return c;
  for (const bin of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
    try { return execFileSync('which', [bin]).toString().trim(); } catch (_) { /* next */ }
  }
  return null;
}

// Fake but well-formed session (auth-sync only decodes the payload — no server check here).
function b64url(o) { return Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_'); }
const JWT = b64url({ alg: 'HS256' }) + '.' + b64url({ user_id: 7, user_type: 'emp', exp: 4102444800 }) + '.sig';
const USER = { id: 7, user_type: 'emp', tw_id: 'U7', full_name: 'Test' };

function pageHtml(mode) {
  const seed = mode === 'auth'
    ? 'localStorage.setItem("tw_jwt",' + JSON.stringify(JWT) + ');localStorage.setItem("tw_user",' + JSON.stringify(JSON.stringify(USER)) + ');'
    : 'localStorage.clear();';
  return '<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">'
    + '<script>window.__errs=[];window.addEventListener("error",function(e){__errs.push(String(e.message))});' + seed + '</script>'
    + '<link rel="stylesheet" href="/static/tw_shared.css"><link rel="stylesheet" href="/static/app-header.css">'
    + '</head><body><header data-tw-header></header><main>x</main><nav data-tw-bottom-nav></nav>'
    + '<script src="/static/tw_shared.js"></script><script src="/static/shared/auth-sync.js"></script>'
    + '<script>window.addEventListener("load",function(){setTimeout(function(){'
    + 'var rows=[].map.call(document.querySelectorAll("[data-tw-header] [data-tw-session]"),function(el){'
    + 'return {s:el.getAttribute("data-tw-session"),cls:el.className,hidden:el.hidden,d:getComputedStyle(el).display};});'
    + 'var nav=document.querySelector("[data-tw-bottom-nav]");'
    + 'var o=document.createElement("pre");o.id="twOut";'
    + 'o.textContent=JSON.stringify({errs:window.__errs,mounted:document.querySelector("[data-tw-header]").hasAttribute("data-tw-mounted"),'
    + 'rows:rows,nav:{hidden:nav.hidden,d:getComputedStyle(nav).display,items:nav.querySelectorAll(".tw-bnav-item").length}});'
    + 'document.body.appendChild(o);},300);});</script></body></html>';
}

const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/__hnav') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(pageHtml(u.searchParams.get('mode')));
  }
  // Same lookup as server.py GET /static/{filename}: static/<f> first, then the repo root
  const rel = u.pathname.replace(/^\/static\//, '');
  const f = [path.join(ROOT, 'static', rel), path.join(ROOT, rel)]
    .find(p => p.startsWith(ROOT + path.sep) && fs.existsSync(p) && fs.statSync(p).isFile());
  if (u.pathname.startsWith('/static/') && f) {
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
    return res.end(fs.readFileSync(f));
  }
  res.writeHead(404); res.end();   // API calls (badges …) — irrelevant here
});

function run(chrome, port, mode) {
  return new Promise((resolve, reject) => {
    execFile(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--window-size=390,800',
      '--virtual-time-budget=5000', '--dump-dom', 'http://127.0.0.1:' + port + '/__hnav?mode=' + mode],
    { timeout: 60000, maxBuffer: 8 << 20 }, (err, stdout) => {
      const m = /<pre id="twOut">([\s\S]*?)<\/pre>/.exec(stdout || '');
      if (!m) return reject(new Error('no result from browser (' + mode + '): ' + (err ? err.message : 'empty')));
      resolve(JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')));
    });
  });
}

function assertMode(mode, r) {
  const shown = mode === 'auth' ? 'authenticated' : 'guest';
  const other = mode === 'auth' ? 'guest' : 'authenticated';
  console.log('\n[' + mode + ']');
  if (r.errs && r.errs.length) console.log('  page errors: ' + r.errs.join(' | '));
  check(mode + ': header mounted by twMountAppChrome', r.mounted === true);
  const mine = r.rows.filter(x => x.s === shown), theirs = r.rows.filter(x => x.s === other);
  check(mode + ': header has elements of both states', mine.length > 0 && theirs.length > 0, mine.length + '/' + theirs.length);
  theirs.forEach(x => check(mode + ': ' + other + ' element ".' + x.cls + '" computed display = none',
    x.hidden === true && x.d === 'none', 'hidden=' + x.hidden + ' display=' + x.d));
  mine.forEach(x => check(mode + ': ' + shown + ' element ".' + x.cls + '" visible',
    x.hidden === false && x.d !== 'none', 'hidden=' + x.hidden + ' display=' + x.d));
  if (mode === 'auth') check('auth: bottom nav visible (< 1020px)', !r.nav.hidden && r.nav.d !== 'none' && r.nav.items > 0, JSON.stringify(r.nav));
  else check('guest: bottom nav computed display = none', r.nav.hidden && r.nav.d === 'none', JSON.stringify(r.nav));
}

(async () => {
  const chrome = findChrome();
  if (!chrome) {
    console.log((process.env.CI ? '  FAIL  ' : '  SKIP  ') + 'no Chrome / Chromium found (set CHROME_BIN)');
    process.exit(process.env.CI ? 1 : 0);
  }
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  try {
    for (const mode of ['auth', 'guest']) assertMode(mode, await run(chrome, port, mode));
  } catch (e) {
    check('browser run', false, e.message);
  } finally {
    server.close();
  }
  console.log('\n' + (failures ? failures + ' FAILED' : 'ALL PASS'));
  process.exit(failures ? 1 : 0);
})();
