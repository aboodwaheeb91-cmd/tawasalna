/**
 * test_staff_link_runtime.js — staff link pages + admin "forgot password" box (task 8.4c-2b-1 ·
 * docs/rules/admin-staff.md rule 15). Runs the REAL tw_shared.js (twApi · twT · twLimit) + static/shared/admin-otp-ui.js
 * + static/staff-link/staff-link.js (and static/admin/admin.js for the forgot box) in Node vm contexts with a fake DOM
 * and a fake fetch.
 *   S  token: #t= removed (replaceState) before the first request · token only in the POST body · no #t= → no request
 *      · storage never touched · token never in console · every error code → its message · no double submit
 *   C  recovery codes box: continue disabled before "saved" · after continue no code / secret / QR in the DOM ·
 *      TXT download = local Blob + revokeObjectURL + tawasolna-recovery-codes.txt (only on click)
 *   Q  QR only for otpauth://totp/ (anything else → no QR, no form)
 *   P  panel link only on the invite page (mfa reply with "panel" → ignored) · password reset → no start request
 *   F  admin forgot box: one POST <panel>/forgot (no auth) · same message for 200 / 429 / network
 * Run: node tests/test_staff_link_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const tick = async (n) => { for (let i = 0; i < (n || 6); i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const T = (k, v) => String(STRINGS[k] || k).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m));
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-xyzw';
const SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP';
const URI = 'otpauth://totp/Tawasolna:staff?secret=' + SECRET + '&issuer=Tawasolna';
const CODES = ['aaaa-1111', 'bbbb-2222', 'cccc-3333', 'dddd-4444', 'eeee-5555',
               'ffff-6666', 'gggg-7777', 'hhhh-8888', 'iiii-9999', 'jjjj-0000'];

// ── fake DOM ── (initial hidden = as in staff-link.html / admin.html)
const HIDDEN = new Set(['slRetry', 'slForm', 'slCodes', 'slDone', 'slPanel', 'loginWrap', 'codeForm', 'enrollForm', 'codesBox',
  'forgotForm', 'main-content']);
function makeDoc(ids) {
  const byId = {};
  function el(tag) {
    const ls = {}, attrs = {};
    const e = {
      tagName: String(tag).toUpperCase(), children: [], parent: null, hidden: false, disabled: false, checked: false,
      value: '', className: '', type: '', href: '', download: '', onclick: null, _text: '',
      get textContent() { return this._text + this.children.map(c => c.textContent).join(''); },
      set textContent(v) { this.children.forEach(c => { c.parent = null; }); this.children = []; this._text = String(v); },
      setAttribute(k, v) { attrs[k] = String(v); }, getAttribute(k) { return k in attrs ? attrs[k] : null; },
      removeAttribute(k) { delete attrs[k]; }, attrs,
      appendChild(c) { c.parent = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter(x => x !== c); c.parent = null; return c; },
      addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); },
      fire(t, ev) { (ls[t] || []).forEach(fn => fn(Object.assign({ preventDefault() {} }, ev || {}))); if (t === 'click' && this.onclick) this.onclick(); },
      click() { this.fire('click'); }, focus() {},
    };
    return e;
  }
  ids.forEach(id => { byId[id] = el(id.indexOf('Form') !== -1 ? 'form' : 'div'); byId[id].id = id; byId[id].hidden = HIDDEN.has(id); });
  const body = el('body');
  ids.forEach(id => body.appendChild(byId[id]));
  const doc = {
    readyState: 'complete', body, title: '',
    getElementById: id => byId[id] || null,
    createElement: tag => el(tag),
    querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {},
  };
  return { doc, byId };
}
// every text / attribute / value in the subtree (to look for secrets)
function dump(e) {
  if (!e) return '';
  return [e._text, e.value, e.href, JSON.stringify(e.attrs || {})].join('|') + e.children.map(dump).join('|');
}
function find(e, pred) {
  if (pred(e)) return e;
  for (const c of e.children) { const f = find(c, pred); if (f) return f; }
  return null;
}

const SL_IDS = ['slBox', 'slTitle', 'slHint', 'slMsg', 'slRetry', 'slBind', 'slForm', 'slPassRow', 'slPass', 'slPass2Row',
  'slPass2', 'slPassHint', 'slCodeRow', 'slCode', 'slSubmit', 'slErr', 'slCodes', 'slDone', 'slDoneTitle', 'slDoneText',
  'slPanel', 'slPanelUrl', 'slPanelCopy', 'slPanelGo'];

// replies: { 'start': [status, body] | 'network', 'complete': ... } — or a function(url, body) → [status, body]
function page(opts) {
  const { doc, byId } = makeDoc(opts.ids || SL_IDS);
  const rec = { requests: [], replaced: [], storage: [], logs: [], qr: [], blobs: [], revoked: [], clicks: [], order: [] };
  const storage = new Proxy({}, { get: (t, k) => { rec.storage.push(String(k)); return () => null; } });
  const loc = { pathname: opts.path, hash: opts.hash || '', search: '', origin: 'https://site.example', href: '' };
  const logc = {};
  ['log', 'warn', 'error', 'info', 'debug'].forEach(m => { logc[m] = (...a) => rec.logs.push(a.map(String).join(' ')); });
  const ctx = {
    console: logc, JSON, Promise, Object, Array, Number, String, Math, Date, RegExp, Error, URLSearchParams,
    setTimeout: (fn) => { fn(); return 0; }, clearTimeout() {},
    AbortController, Blob: function (parts, o) { rec.blobs.push({ text: parts.join(''), type: o && o.type }); },
    URL: { createObjectURL: () => { rec.order.push('create'); return 'blob:x1'; }, revokeObjectURL: u => { rec.order.push('revoke'); rec.revoked.push(u); } },
    navigator: { userAgent: 'node', clipboard: { writeText: t => { rec.clip = t; return Promise.resolve(); } } },
    document: doc, location: loc,
    history: { replaceState: (s, t, u) => { rec.replaced.push(u); rec.order.push('replace'); loc.hash = ''; } },
    addEventListener() {}, requestAnimationFrame() {},
    TW_STRINGS: { dict: STRINGS },
    TW_LIMITS: { limits: { staff_password_min: 12, password_max_bytes: 72 }, report_types: [] },
  };
  ctx.window = ctx;
  ctx.fetch = (url, init) => {
    const body = init && init.body ? JSON.parse(init.body) : null;
    rec.requests.push({ url, init, body });
    rec.order.push('fetch');
    const key = /\/start$/.test(url) ? 'start' : /\/complete$/.test(url) ? 'complete' : 'other';
    let r = typeof opts.reply === 'function' ? opts.reply(url, body, rec.requests.length) : (opts.reply || {})[key];
    if (r === 'network' || !r) return Promise.reject(new TypeError('net'));
    if (r === 'hold') return new Promise(() => {});
    const [status, b] = r;
    return Promise.resolve({ ok: status >= 200 && status < 300, status, text: () => Promise.resolve(JSON.stringify(b)) });
  };
  vm.createContext(ctx);
  vm.runInContext(read('tw_shared.js'), ctx, { filename: 'tw_shared.js' });
  ctx.showToast = (m, t) => { (rec.toasts = rec.toasts || []).push([m, t]); };
  ctx.QRCode = function (box, o) { rec.qr.push(o.text); box.appendChild(doc.createElement('canvas')); };
  ctx.QRCode.CorrectLevel = { M: 0 };
  ctx.localStorage = storage; ctx.sessionStorage = storage;   // from here on, any touch is recorded
  vm.runInContext(read('static/shared/admin-otp-ui.js'), ctx, { filename: 'admin-otp-ui.js' });
  if (opts.extra) opts.extra(ctx, rec, byId);
  vm.runInContext(read(opts.script || 'static/staff-link/staff-link.js'), ctx, { filename: 'page.js' });
  return { ctx, rec, byId, doc };
}
const ok = d => [200, { ok: true, data: d }];
const bad = (status, code) => [status, { ok: false, error: { code, message: 'server text' } }];
const START_OK = ok({ secret: SECRET, otpauth_uri: URI, name: 'سارة' });
function fill(byId, pass, pass2, code) {
  byId.slPass.value = pass; byId.slPass2.value = pass2 === undefined ? pass : pass2; byId.slCode.value = code || '';
}

(async function main() {
  console.log('\nS — the token');
  {
    const p = page({ path: '/staff/invite', hash: '', reply: { start: START_OK } });
    await tick();
    check('S1 no #t= → no request at all', p.rec.requests.length === 0);
    check('S2 no #t= → "invalid link" + ask the owner', p.byId.slMsg.textContent.indexOf(T('staff.link.err.invalid_link')) === 0
      && p.byId.slMsg.textContent.indexOf(T('staff.link.err.ask_owner')) !== -1 && p.byId.slForm.hidden === true);
  }
  {
    const p = page({ path: '/staff/password-reset', hash: '#x=1' });
    await tick();
    check('S3 other fragment → no request + fragment removed + ask "forgot"', p.rec.requests.length === 0
      && p.rec.replaced[0] === '/staff/password-reset' && p.byId.slMsg.textContent.indexOf(T('staff.link.err.ask_forgot')) !== -1);
  }
  {
    const p = page({ path: '/staff/invite', hash: '#t=' + TOKEN, reply: { start: START_OK, complete: ok({ recovery_codes: CODES, name: 'سارة', panel: '/secret-panel' }) } });
    await tick();
    check('S4 fragment removed before the first request', p.rec.order[0] === 'replace' && p.rec.order.indexOf('fetch') > 0
      && p.rec.replaced[0] === '/staff/invite' && p.ctx.location.hash === '');
    const r0 = p.rec.requests[0];
    check('S5 start: POST /staff/invite/start · token in the body only', r0 && r0.url === '/staff/invite/start'
      && r0.init.method === 'POST' && r0.body.token === TOKEN && r0.url.indexOf(TOKEN) === -1
      && JSON.stringify(r0.init.headers).indexOf(TOKEN) === -1);
    check('S6 no auth header (no user session on this page)', !('Authorization' in r0.init.headers));
    check('S7 form shown with password + confirm + code', p.byId.slForm.hidden === false && !p.byId.slPassRow.hidden
      && !p.byId.slPass2Row.hidden && !p.byId.slCodeRow.hidden);
    check('Q1 QR drawn from the otpauth uri (in the browser)', p.rec.qr.length === 1 && p.rec.qr[0] === URI);
    check('Q2 grouped key + open-in-app link shown', dump(p.byId.slBind).indexOf('JBSW Y3DP EHPK') !== -1
      && !!find(p.byId.slBind, e => e.attrs && e.attrs.href === URI));
    fill(p.byId, 'a long pass phrase', 'a long pass phrase', '123456');
    p.byId.slForm.fire('submit');
    p.byId.slForm.fire('submit');   // double click
    await tick();
    const completes = p.rec.requests.filter(r => /complete$/.test(r.url));
    check('S8 no double submit → one complete request', completes.length === 1);
    check('S9 complete body = {token, password, code}', completes[0].body.token === TOKEN
      && completes[0].body.password === 'a long pass phrase' && completes[0].body.code === '123456');
    check('S10 storage never touched', p.rec.storage.length === 0, p.rec.storage);
    check('S11 token never in console', p.rec.logs.every(l => l.indexOf(TOKEN) === -1));

    console.log('\nC — recovery codes box');
    const box = p.byId.slCodes;
    const done = find(box, e => e.tagName === 'BUTTON' && e._text === T('admin.login.codes_done'));
    const saved = find(box, e => e.type === 'checkbox');
    check('C1 the 10 codes shown once', box.hidden === false && CODES.every(c => dump(box).indexOf(c) !== -1)
      && p.byId.slBox.hidden === true);
    check('C2 secret + QR gone once the codes show', dump(p.byId.slBind).indexOf(SECRET.slice(0, 8)) === -1 && p.byId.slBind.children.length === 0);
    check('C3 continue disabled before "saved"', done && done.disabled === true);
    done.click();
    check('C4 continue before "saved" → nothing happens', p.byId.slDone.hidden === true && CODES.every(c => dump(box).indexOf(c) !== -1));
    check('C5 file warning shown', dump(box).indexOf(T('admin.login.codes_file_warn')) !== -1);
    check('C6 no download before a click', p.rec.blobs.length === 0);
    const dl = find(box, e => e.tagName === 'BUTTON' && e._text === T('admin.login.codes_download'));
    let anchor = null;
    const origCreate = p.doc.createElement;
    p.doc.createElement = t => { const e = origCreate(t); if (t === 'a') { anchor = e; e.click = () => p.rec.clicks.push(e.download); } return e; };
    dl.click();
    p.doc.createElement = origCreate;
    check('C7 TXT = local Blob with the codes · file name · revoked after the click',
      p.rec.blobs.length === 1 && CODES.every(c => p.rec.blobs[0].text.indexOf(c) !== -1) && /^text\/plain/.test(p.rec.blobs[0].type)
      && p.rec.clicks[0] === 'tawasolna-recovery-codes.txt' && p.rec.revoked[0] === 'blob:x1'
      && p.rec.order.lastIndexOf('revoke') > p.rec.order.lastIndexOf('create'));
    check('C8 the temporary link is removed', anchor && anchor.parent === null);
    saved.checked = true; saved.fire('change');
    check('C9 "saved" enables continue', done.disabled === false);
    done.click();
    check('C10 after continue: no code / secret / QR anywhere in the DOM', CODES.every(c => dump(p.doc.body).indexOf(c) === -1)
      && dump(p.doc.body).indexOf(SECRET.slice(0, 8)) === -1 && dump(p.doc.body).indexOf('canvas') === -1 && box.children.length === 0);

    console.log('\nP — panel link');
    check('P1 invite: panel link (origin + panel) + go button', p.byId.slDone.hidden === false && p.byId.slPanel.hidden === false
      && p.byId.slPanelUrl.textContent === 'https://site.example/secret-panel' && p.byId.slPanelGo.attrs.href === '/secret-panel');
    check('P2 token never in console (whole flow)', p.rec.logs.every(l => l.indexOf(TOKEN) === -1));
  }
  {
    const p = page({ path: '/staff/mfa-reset', hash: '#t=' + TOKEN, reply: { start: START_OK, complete: ok({ recovery_codes: CODES, name: 'x', panel: '/secret-panel' }) } });
    await tick();
    check('P3 mfa: start = /staff/mfa-reset/start · code only', p.rec.requests[0].url === '/staff/mfa-reset/start'
      && p.byId.slPassRow.hidden === true && p.byId.slCodeRow.hidden === false);
    p.byId.slCode.value = '654321';
    p.byId.slForm.fire('submit');
    await tick();
    const c = p.rec.requests[1];
    check('P4 mfa complete body = {token, code} (no password)', c.url === '/staff/mfa-reset/complete' && c.body.token === TOKEN
      && c.body.code === '654321' && !('password' in c.body));
    const box = p.byId.slCodes, saved = find(box, e => e.type === 'checkbox');
    const done = find(box, e => e.tagName === 'BUTTON' && e._text === T('admin.login.codes_done'));
    saved.checked = true; saved.fire('change'); done.click();
    check('P5 mfa: no panel link even if the reply had one · "sign in with your link" text', p.byId.slPanel.hidden === true
      && dump(p.doc.body).indexOf('secret-panel') === -1 && p.byId.slDoneText.textContent === T('staff.link.mfa.done_text'));
  }
  {
    const p = page({ path: '/staff/password-reset', hash: '#t=' + TOKEN, reply: { complete: ok({}) } });
    await tick();
    check('P6 password reset: no start request · password + confirm, no code', p.rec.requests.length === 0
      && p.byId.slForm.hidden === false && p.byId.slCodeRow.hidden === true && p.byId.slPassRow.hidden === false);
    fill(p.byId, 'pass phrase one', 'pass phrase two');
    p.byId.slForm.fire('submit');
    await tick();
    check('P7 mismatch → message, no request', p.rec.requests.length === 0 && p.byId.slErr.textContent === T('staff.link.err.mismatch'));
    fill(p.byId, 'pass phrase one');
    p.byId.slForm.fire('submit');
    await tick();
    const c = p.rec.requests[0];
    check('P8 complete = {token, password}', c.url === '/staff/password-reset/complete' && c.body.token === TOKEN
      && c.body.password === 'pass phrase one' && !('code' in c.body));
    check('P9 done: "password changed" · no panel link · no codes box', p.byId.slDone.hidden === false
      && p.byId.slDoneText.textContent === T('staff.link.password.done_text') && p.byId.slPanel.hidden === true && p.byId.slCodes.children.length === 0);
  }

  console.log('\nS — error messages');
  async function invErr(reply, path) {
    const p = page({ path: path || '/staff/invite', hash: '#t=' + TOKEN, reply: { start: START_OK, complete: reply } });
    await tick();
    fill(p.byId, 'a long pass phrase', undefined, '123456');
    p.byId.slForm.fire('submit');
    await tick();
    return p;
  }
  {
    let p = await invErr(bad(400, 'invalid_code'));
    check('S12 invalid_code → its message · form stays · code cleared · button back', p.byId.slErr.textContent === T('admin.staff.error.invalid_code')
      && p.byId.slForm.hidden === false && p.byId.slCode.value === '' && p.byId.slSubmit.disabled === false);
    p = await invErr(bad(422, 'invalid_code_format'));
    check('S13 invalid_code_format → its message', p.byId.slErr.textContent === T('admin.staff.error.invalid_code_format'));
    p = await invErr(bad(422, 'weak_password'));
    check('S14 weak_password → its message (min 12)', p.byId.slErr.textContent === T('admin.staff.error.weak_password', { min: '12' }));
    p = await invErr(bad(422, 'password_too_long'));
    check('S15 password_too_long → its message', p.byId.slErr.textContent === T('admin.staff.error.password_too_long', { max: '72' }));
    p = await invErr([429, { ok: false, error: { code: 'rate_limited', message: 'x' } }]);
    check('S16 429 → "too many attempts"', p.byId.slErr.textContent === T('staff.link.err.rate'));
    p = await invErr([500, { ok: false, error: { code: 'server_error', message: 'x' } }]);
    check('S17 500 → generic message', p.byId.slErr.textContent === T('staff.link.err.generic'));
    p = await invErr('network');
    check('S18 network → generic message', p.byId.slErr.textContent === T('staff.link.err.generic'));
    p = await invErr(bad(400, 'invalid_link'));
    check('S19 invalid_link on complete → "invalid" + ask the owner · form + secret gone', p.byId.slForm.hidden === true
      && p.byId.slMsg.textContent === T('staff.link.err.invalid_link') + ' ' + T('staff.link.err.ask_owner')
      && p.byId.slBind.children.length === 0);
    p = await invErr(bad(400, 'invalid_link'), '/staff/password-reset');
    check('S20 invalid_link on password reset → ask "forgot password"',
      p.byId.slMsg.textContent === T('staff.link.err.invalid_link') + ' ' + T('staff.link.err.ask_forgot'));
  }
  {
    const p = page({ path: '/staff/invite', hash: '#t=' + TOKEN, reply: { start: bad(400, 'invalid_link') } });
    await tick();
    check('S21 invalid_link on start → message, no form, no retry', p.byId.slForm.hidden === true && p.byId.slRetry.hidden === true
      && p.byId.slMsg.textContent.indexOf(T('staff.link.err.invalid_link')) === 0);
    const q = page({ path: '/staff/invite', hash: '#t=' + TOKEN, reply: (u, b, n) => (n === 1 ? [429, {}] : START_OK) });
    await tick();
    check('S22 429 on start → message + retry (token kept in memory)', q.byId.slMsg.textContent === T('staff.link.err.rate') && q.byId.slRetry.hidden === false);
    q.byId.slRetry.click();
    await tick();
    check('S23 retry → second start with the same token → form', q.rec.requests.length === 2 && q.rec.requests[1].body.token === TOKEN
      && q.byId.slForm.hidden === false);
  }
  {
    const p = page({ path: '/staff/invite', hash: '#t=' + TOKEN, reply: { start: START_OK, complete: 'hold' } });
    await tick();
    fill(p.byId, 'a long pass phrase', undefined, '123456');
    p.byId.slForm.fire('submit');
    await tick();
    check('S24 button disabled while the request runs', p.byId.slSubmit.disabled === true);
    p.byId.slForm.fire('submit');
    check('S25 second submit during the request → no request', p.rec.requests.filter(r => /complete$/.test(r.url)).length === 1);
  }

  console.log('\nQ — QR only for otpauth://totp/');
  for (const uri of ['otpauth://hotp/x?secret=' + SECRET, 'javascript:alert(1)', 'https://evil.example/qr']) {
    const p = page({ path: '/staff/invite', hash: '#t=' + TOKEN, reply: { start: ok({ secret: SECRET, otpauth_uri: uri, name: 'x' }) } });
    await tick();
    check('Q3 ' + uri.slice(0, 14) + ' → no QR · no link · no form', p.rec.qr.length === 0 && p.byId.slBind.children.length === 0
      && p.byId.slForm.hidden === true && dump(p.doc.body).indexOf(uri) === -1);
  }

  console.log('\nF — admin forgot box');
  const ADM_IDS = ['loginWrap', 'loginForm', 'codeForm', 'enrollForm', 'codesBox', 'forgotForm', 'main-content', 'admin-user',
    'admin-pass', 'loginBtn', 'loginErr', 'codeHint', 'admin-code', 'codeBtn', 'codeMode', 'codeErr', 'enrollBind', 'enroll-code',
    'enrollBtn', 'enrollErr', 'forgot-email', 'forgotBtn', 'forgotMsg', 'forgotOpen'];
  async function forgot(reply) {
    const p = page({ path: '/panel-x', ids: ADM_IDS, script: 'static/admin/admin.js', reply: () => reply,
      extra: (ctx) => {
        ctx.TwAdminJobs = { ACTIONS: {} };
        ctx.TwAdminShell = { base: () => '/panel-x', start: () => false, wasExpired: () => false, run() {}, mount() {} };
        ctx.TwAdminSession = { setToken() {} };
      } });
    p.byId.forgotOpen.click();
    check('F0 "forgot?" opens the forgot box only', p.byId.forgotForm.hidden === false && p.byId.loginForm.hidden === true);
    p.byId['forgot-email'].value = 'someone@example.com';
    p.byId.forgotForm.fire('submit');
    p.byId.forgotForm.fire('submit');
    await tick();
    return p;
  }
  const msgs = [];
  for (const r of [ok({ sent: true }), [429, {}], 'network', [500, {}]]) {
    const p = await forgot(r);
    const req = p.rec.requests;
    check('F1 one POST <panel>/forgot {email} without auth (' + (Array.isArray(r) ? r[0] : r) + ')', req.length === 1
      && req[0].url === '/panel-x/forgot' && req[0].init.method === 'POST' && req[0].body.email === 'someone@example.com'
      && !('Authorization' in req[0].init.headers));
    msgs.push(p.byId.forgotMsg.textContent);
  }
  check('F2 the same message for 200 / 429 / network / 500', msgs.every(m => m === T('admin.forgot.sent')), msgs);

  const noPanel = ['staff-link.html', 'static/staff-link/staff-link.js', 'static/shared/admin-otp-ui.js'].filter(f => read(f).indexOf('tw-ctrl') !== -1);
  check('F3 no panel path in the staff page / scripts', noPanel.length === 0, noPanel);

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}());
