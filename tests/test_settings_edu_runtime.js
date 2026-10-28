/**
 * test_settings_edu_runtime.js — PR 4.7: settings.html + edu-profile.html on the unified page checklist
 * Runs the REAL static/settings/settings.js and the REAL edu-profile.html page script in a Node vm with a
 * tiny fake DOM + recorded stubs for the shared helpers (twRequireAuth / twApi / twModal / twAction / twT …).
 *   A  settings guard — guest → no request at all
 *   B  account data from GET /profile/{uid}/full (never tw_user / tw_jwt) · type via account.type.*
 *   C  KYC row — reachable: twAction('verify_identity') opens the flow · state from GET /kyc/status
 *   D  KYC OTP — 503 otp_delivery_unavailable → «غير متاحة» text, no code field · success only on
 *      2xx + status "success" · 401 → no toast (guard redirects) · valid code → next step
 *   E  KYC docs — ID required · upload (private path) → POST /kyc/docs → review
 *   F  phone / password — twModal stays open on error · field errors · fresh token renewed
 *   G  edu — public load via twApi · owner → edit_profile · visitor → message · invalid website blocked
 *   H  strings — every twT key used exists in tw_strings.json (+ the verify_identity action)
 *   K  verify_identity off by default (until plan 5.1) → no KYC row, no /kyc request · admin
 *      override enabled:true → row back (action states from the REAL tw_actions.py merged registry)
 *   L  notification emails (5.1c) — one switch per type from GET /my/email-notifications · change →
 *      PUT {types:{key:bool}} · failure → switch rolled back + error toast · admin-off type disabled
 *
 * Run: node tests/test_settings_edu_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');
const { execFileSync } = require('child_process');
const PY = (() => { for (const p of ['python3', 'python']) { try { execFileSync(p, ['-V']); return p; } catch (e) {} } })();
// the registry exactly as pages receive it (tw_actions.merged — registry defaults + admin overrides)
const mergedActions = ov => JSON.parse(execFileSync(PY, ['-c',
  'import json, sys, tw_actions; print(json.dumps(tw_actions.merged(json.loads(sys.argv[1]))))', JSON.stringify(ov || {})],
  { encoding: 'utf8' }));
const KYC_ON = { verify_identity: { enabled: true } };   // admin turned it on (after plan 5.1)

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const flush = async () => { for (let i = 0; i < 10; i++) await new Promise(r => setImmediate(r)); };

const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const ACTIONS = JSON.parse(read('tw_actions.json')).actions;
const SETTINGS_JS = read('static/settings/settings.js');
const SETTINGS_HTML = read('settings.html');
const EDU_HTML = read('edu-profile.html');
const EDU_JS = (function () {
  const i = EDU_HTML.lastIndexOf('<script>');
  return EDU_HTML.slice(i + 8, EDU_HTML.indexOf('</script>', i));
})();

// ── tiny fake DOM ───────────────────────────────────────────────────────────
class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = []; this.parentNode = null; this.attrs = {}; this.style = {};
    this._text = ''; this.listeners = {}; this.value = ''; this.hidden = false;
    const self = this;
    this.classList = {
      add: (...c) => { const s = new Set(self._cls()); c.forEach(x => s.add(x)); self.className = [...s].join(' '); },
      remove: (...c) => { self.className = self._cls().filter(x => c.indexOf(x) < 0).join(' '); },
      contains: c => self._cls().indexOf(c) >= 0,
    };
  }
  _cls() { return (this.attrs['class'] || '').split(/\s+/).filter(Boolean); }
  get className() { return this.attrs['class'] || ''; }
  set className(v) { this.attrs['class'] = String(v); }
  get id() { return this.attrs.id || ''; }
  set id(v) { this.attrs.id = String(v); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; }
  replaceChildren(...c) { this.textContent = ''; c.forEach(x => this.appendChild(x)); }
  remove() { if (this.parentNode) { const p = this.parentNode; p.children = p.children.filter(x => x !== this); this.parentNode = null; } }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(v) { this.children.forEach(c => { c.parentNode = null; }); this.children = []; this._text = String(v); }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  fire(t, ev) { (this.listeners[t] || []).forEach(fn => fn(ev || { target: this, preventDefault() {} })); }
  click() { this.fire('click'); }
  _all() { const out = []; this.children.forEach(c => { out.push(c); out.push(...c._all()); }); return out; }
  find(fn) { return this._all().filter(fn); }
  querySelectorAll(sel) {
    const m = /^\[([\w-]+)\]$/.exec(sel);
    return m ? this._all().filter(e => e.hasAttribute(m[1])) : [];
  }
}
const byClass = (root, c) => root.find(e => e.classList.contains(c));
const visibleText = root => root.find(e => !e.hidden).map(e => e._text).join(' ');

function makeDocument(ids, extra) {
  const body = new El('body');
  ids.forEach(id => { const e = new El('div'); e.id = id; body.appendChild(e); });
  (extra || []).forEach(e => body.appendChild(e));
  return {
    body, title: '',
    getElementById: id => body._all().find(e => e.id === id) || null,
    querySelectorAll: s => body.querySelectorAll(s),
    createElement: t => new El(t),
  };
}

// recorded shared stubs — api: { 'METHOD path': response | fn(opts) → response }
function sharedStubs(rec, opts) {
  const api = opts.api || {};
  const merged = mergedActions(opts.overrides === undefined ? KYC_ON : opts.overrides);
  return {
    twT: (k, vars) => { if (!(k in STRINGS)) rec.missingKeys.add(k); return vars ? k + JSON.stringify(vars) : k; },
    twTApply() {}, twIcon: { hydrate() {} },
    twIconEl: name => { const e = new El('svg'); e.setAttribute('data-icon', name); return e; },
    twApi: (path, o) => {
      o = o || {};
      const key = (o.method || 'GET') + ' ' + path;
      rec.api.push({ key, body: o.body, auth: o.auth });
      let r = api[key];
      if (typeof r === 'function') r = r(o);
      return Promise.resolve(r || { ok: false, status: 500, data: null, error: { fieldErrors: [], generalError: { code: 'unknown', message: 'x' } } });
    },
    twApiMessage: (res, fb) => {
      const e = res && res.error; const f = e && e.fieldErrors && e.fieldErrors[0];
      return (f && f.message) || (e && e.generalError && e.generalError.code !== 'unknown' && e.generalError.message) || fb;
    },
    twModal: m => { const ctl = { close() { ctl.closed = true; }, m }; rec.modals.push(ctl); return ctl; },
    twActionState: id => {
      const d = merged[id];
      return d && !d.off && (d.visibleTo || []).indexOf(opts.userType || 'edu') >= 0 ? 'enabled' : 'hidden';
    },
    twAction: (id, ctx) => {
      rec.actions.push({ id, ctx });
      if (!(id in ACTIONS) || merged[id].off) return null;
      if (id === 'message' && opts.viewerIsOwnerOf) return null;
      const b = new El('button'); b.setAttribute('data-tw-action', id);
      b.addEventListener('click', () => ctx.onClick && ctx.onClick(ctx, b));
      return b;
    },
    twCanMessage: id => { rec.canMsg = (rec.canMsg || []).concat([id]);   // server rule (5.0g)
      return Promise.resolve({ can_message: opts.canMessage !== false, reason: null, ended: false, can_end: false }); },
    showToast: (msg, type) => rec.toasts.push({ msg, type }),
    setBtnLoad() {},
    twSafeLinkUrl: u => (/^https?:\/\/[^\s/]/.test(u) ? u : ''),
    twAvatarEl: () => new El('span'),
    twFormatDate: v => 'D(' + v + ')',
    TW: {
      uploadImage: o => { rec.uploads.push(o.kind); return Promise.resolve(opts.upload || { ok: true, status: 200, data: { path: 'kyc-docs/7_' + o.kind + '_abc.png' } }); },
      uploadError: (r, fb) => { const e = new Error('u'); e.userMsg = fb; return e; },
      uploadFailureMessage: (e, fb) => (e && e.userMsg) || fb,
    },
    FileReader: class { readAsDataURL(f) { this.onload({ target: { result: 'data:image/png;base64,AAAA' + f.name } }); } },
  };
}

function baseCtx(rec, opts, document) {
  const ctx = Object.assign({
    document, console: { log() {}, warn() {}, error() {} }, Promise, Object, JSON, String, Number, Array,
    encodeURIComponent, URLSearchParams, setTimeout: fn => rec.timers.push(fn),
    location: { href: '/x', pathname: '/x', search: opts.search || '' },
    // tw_user / tw_jwt are never read — any localStorage access fails the run
    get localStorage() { rec.lsTouched = true; throw new Error('localStorage read'); },
  }, sharedStubs(rec, opts));
  ctx.window = ctx;
  return ctx;
}
const newRec = () => ({ api: [], toasts: [], modals: [], actions: [], uploads: [], timers: [], missingKeys: new Set(), lsTouched: false });

const OK = data => ({ ok: true, status: 200, data, error: null });
const FAIL = (status, error) => ({ ok: false, status, data: null, error });
const PROFILE = OK({ profile: { user_type: 'edu', tw_id: 'T123', full_name: 'جامعة', email: 'a@b.co', phone: '+962790000000' } });

async function runSettings(opts) {
  opts = opts || {};
  // the notification switches (5.1c) load on every run — default: no types (sections A–K unaffected)
  opts.api = Object.assign({ 'GET /my/email-notifications': OK({ types: [] }),
                            'GET /blocks?offset=0': OK({ items: [], total: 0 }) }, opts.api || {});   // «المحظورون» (5.4)
  const rec = newRec();
  const rows = ['phone', 'password'].map(k => { const b = new El('button'); b.setAttribute('data-st-open', k); return b; });
  const kycRow = new El('div'); kycRow.id = 'kycRow'; kycRow.hidden = true;
  ['kycState', 'kycAction'].forEach(id => { const e = new El('span'); e.id = id; kycRow.appendChild(e); });
  const document = makeDocument(['dispName', 'dispEmail', 'dispPhone', 'dispType', 'dispID', 'notifyList', 'blockedList'], rows.concat([kycRow]));
  const ctx = baseCtx(rec, opts, document);
  ctx.twRequireAuth = () => (opts.guest ? null : { isAuthenticated: true, userId: 7, userType: 'edu' });
  ctx.TwAuthSync = { getToken: () => 'JWT', renewToken: t => { rec.renewed = t; return true; }, invalidateSession: r => { rec.invalidated = r; } };
  vm.runInNewContext(SETTINGS_JS, ctx, { filename: 'settings.js' });
  await flush();
  return { rec, ctx, document, rows, $: id => document.getElementById(id) };
}
const kycBtn = p => p.$('kycAction') && p.$('kycAction').find(e => e.getAttribute('data-tw-action') === 'verify_identity')[0];
const lastModal = p => p.rec.modals[p.rec.modals.length - 1];
const btnByKey = (root, key) => root.find(e => e.tagName === 'BUTTON' && e._text === key)[0];

(async function main() {
  // ── A — guard ──
  console.log('\nA — settings guard');
  {
    const p = await runSettings({ guest: true });
    check('A1 guest → no API request', p.rec.api.length === 0, p.rec.api);
    check('A2 guest → no KYC button', !kycBtn(p));
  }

  // ── B — account data ──
  console.log('\nB — account data (API truth)');
  {
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: null }) } });
    check('B1 GET /profile/7/full requested', p.rec.api.some(a => a.key === 'GET /profile/7/full'));
    check('B2 fields rendered from the API', p.$('dispName')._text === 'جامعة' && p.$('dispEmail')._text === 'a@b.co'
          && p.$('dispPhone')._text === '+962790000000' && p.$('dispID')._text === 'T123');
    check('B3 account type via account.type.edu', p.$('dispType')._text === 'account.type.edu');
    check('B4 localStorage never read', !p.rec.lsTouched);
    const q = await runSettings({ api: { 'GET /profile/7/full': FAIL(500, { fieldErrors: [], generalError: { code: '', message: 'خطأ' } }) } });
    check('B5 load error → error toast', q.rec.toasts.some(t => t.type === 'error'));
  }

  // ── C — KYC row ──
  console.log('\nC — KYC row is reachable');
  {
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'none', status: 'pending' } }) } });
    check('C1 «توثيق الهوية» button rendered by twAction(verify_identity)', !!kycBtn(p));
    check('C2 state text = not verified', p.$('kycState')._text === 'settings.kyc.state.none');
    kycBtn(p).click();
    await flush();
    const m = lastModal(p);
    check('C3 click → twModal opens the KYC flow', !!m && m.m.title === 'settings.kyc.title');
    const prog = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'phone', status: 'pending' } }) } });
    const acts = prog.rec.actions.filter(a => a.id === 'verify_identity');
    check('C4 in progress → «أكمل التوثيق» label', acts[acts.length - 1].ctx.labelKey === 'settings.kyc.continue');
    const rev = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'review', status: 'pending' } }) } });
    check('C5 review → state «قيد المراجعة»', rev.$('kycState')._text === 'settings.kyc.state.review');
    const ok = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'approved', status: 'approved' } }) } });
    check('C6 approved → no button, verified icon', !kycBtn(ok) && ok.$('kycAction').find(e => e.getAttribute('data-icon') === 'verified').length === 1);
  }

  // ── D — KYC OTP ──
  console.log('\nD — KYC OTP send / verify');
  async function openStep1(sendResp, verifyResp) {
    const p = await runSettings({ api: {
      'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'none' } }),
      'POST /kyc/email/send': sendResp, 'POST /kyc/email/verify': verifyResp } });
    kycBtn(p).click();
    await flush();
    const body = lastModal(p).m.content;
    return { p, body };
  }
  {
    const unavailable = FAIL(503, { fieldErrors: [{ field: '', code: 'otp_delivery_unavailable', message: 'x' }], generalError: null });
    const { p, body } = await openStep1(unavailable);
    const email = body.find(e => e.tagName === 'INPUT')[0];
    check('D1 email prefilled from the account', email.value === 'a@b.co');
    btnByKey(body, 'settings.kyc.send_code').click();
    await flush();
    check('D2 POST /kyc/email/send with the email', p.rec.api.some(a => a.key === 'POST /kyc/email/send' && a.body.email === 'a@b.co'));
    check('D3 503 → «غير متاحة» message', p.rec.toasts.some(t => t.type === 'error' && t.msg === 'settings.kyc.otp_unavailable'));
    check('D4 503 → code field stays hidden', byClass(body, 'st-code')[0].parentNode.hidden === true);
    check('D5 503 → no success toast', !p.rec.toasts.some(t => t.type === 'success'));
  }
  {
    const { p, body } = await openStep1(OK({ status: 'error' }));
    btnByKey(body, 'settings.kyc.send_code').click();
    await flush();
    check('D6 200 without status "success" → no success, error toast', !p.rec.toasts.some(t => t.type === 'success') && p.rec.toasts.some(t => t.type === 'error'));
  }
  {
    const { p, body } = await openStep1(FAIL(401, { fieldErrors: [], generalError: { code: '', message: 'x' } }));
    btnByKey(body, 'settings.kyc.send_code').click();
    await flush();
    check('D7 401 → no toast (twApi invalidates, the guard redirects)', p.rec.toasts.length === 0);
  }
  {
    const { p, body } = await openStep1(OK({ status: 'success' }), OK({ status: 'success' }));
    btnByKey(body, 'settings.kyc.send_code').click();
    await flush();
    check('D8 success → code field shown + success toast', byClass(body, 'st-code')[0].parentNode.hidden === false
          && p.rec.toasts.some(t => t.type === 'success' && t.msg === 'settings.kyc.code_sent'));
    const code = byClass(body, 'st-code')[0];
    code.value = '12';
    btnByKey(body, 'settings.kyc.verify_code').click();
    await flush();
    check('D9 short code → no request', !p.rec.api.some(a => a.key === 'POST /kyc/email/verify'));
    code.value = '123456';
    btnByKey(body, 'settings.kyc.verify_code').click();
    await flush();
    check('D10 valid code → POST /kyc/email/verify', p.rec.api.some(a => a.key === 'POST /kyc/email/verify' && a.body.code === '123456'));
    check('D11 verified → phone step shown', visibleText(body).indexOf('settings.kyc.phone.hint') >= 0);
    check('D12 row state → in progress', p.$('kycState')._text === 'settings.kyc.state.progress');
  }

  // ── E — KYC docs ──
  console.log('\nE — KYC documents');
  {
    const p = await runSettings({ api: {
      'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'id_upload' } }),
      'POST /kyc/docs': OK({ status: 'success' }) } });
    kycBtn(p).click();
    await flush();
    const body = lastModal(p).m.content;
    btnByKey(body, 'settings.kyc.docs.submit').click();
    await flush();
    check('E1 no ID → error, no upload', p.rec.uploads.length === 0 && p.rec.toasts.some(t => t.msg === 'settings.kyc.docs.id_required'));
    const file = body.find(e => e.tagName === 'INPUT' && e.type === 'file')[0];
    file.files = [{ name: 'id.png' }];
    file.fire('change');
    check('E2 picked file → name shown, no <img> preview', visibleText(body).indexOf('id.png') >= 0 && body.find(e => e.tagName === 'IMG').length === 0);
    btnByKey(body, 'settings.kyc.docs.submit').click();
    await flush();
    const docs = p.rec.api.find(a => a.key === 'POST /kyc/docs');
    check('E3 upload kyc-id-front → POST /kyc/docs with the private path', p.rec.uploads.join() === 'kyc-id-front'
          && docs && docs.body.id_front_url === 'kyc-docs/7_kyc-id-front_abc.png' && docs.body.selfie_url === null);
    check('E4 sent → review view + row state', visibleText(body).indexOf('settings.kyc.review.title') >= 0
          && p.$('kycState')._text === 'settings.kyc.state.review');
  }
  {
    const p = await runSettings({ upload: { ok: false, status: 502, data: {} }, api: {
      'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: { step: 'id_upload' } }) } });
    kycBtn(p).click();
    await flush();
    const body = lastModal(p).m.content;
    const file = body.find(e => e.tagName === 'INPUT' && e.type === 'file')[0];
    file.files = [{ name: 'id.png' }]; file.fire('change');
    btnByKey(body, 'settings.kyc.docs.submit').click();
    await flush();
    check('E5 failed upload → error, /kyc/docs never called', !p.rec.api.some(a => a.key === 'POST /kyc/docs')
          && p.rec.toasts.some(t => t.type === 'error'));
  }

  // ── F — phone / password ──
  console.log('\nF — phone / password dialogs');
  {
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE,
      'PUT /profile/7': FAIL(422, { fieldErrors: [{ field: 'phone', code: 'x', message: 'رقم غير صالح' }], generalError: null }) } });
    p.rows[0].click();
    const m = lastModal(p);
    const input = m.m.content.find(e => e.tagName === 'INPUT')[0];
    input.value = '';
    check('F1 empty phone → dialog stays open, no request', m.m.actions[1].onClick() === false && !p.rec.api.some(a => a.key === 'PUT /profile/7'));
    input.value = 'bad';
    const kept = await m.m.actions[1].onClick();
    check('F2 server error → stays open + field error', kept === false && byClass(m.m.content, 'st-err')[0]._text === 'رقم غير صالح');
    check('F3 no success toast on error', !p.rec.toasts.some(t => t.type === 'success'));
  }
  {
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE,
      'PUT /auth/password': o => (o.body.current_password === 'wrong'
        ? FAIL(422, { fieldErrors: [{ field: 'current_password', code: 'wrong_password', message: 'كلمة المرور الحالية غير صحيحة' }], generalError: null })
        : OK({ ok: true, token: 'NEW' })) } });
    p.rows[1].click();
    const m = lastModal(p);
    const [oldI, newI, confI] = m.m.content.find(e => e.tagName === 'INPUT');
    oldI.value = 'a'; newI.value = 'Secret123'; confI.value = 'other';
    check('F4 mismatch → stays open, no request', m.m.actions[1].onClick() === false && !p.rec.api.some(a => a.key === 'PUT /auth/password'));
    oldI.value = 'wrong'; confI.value = 'Secret123';
    const kept = await m.m.actions[1].onClick();
    check('F5 wrong current → error on the current-password field', kept === false && oldI._err._text === 'كلمة المرور الحالية غير صحيحة');
    oldI.value = 'right';
    const done = await m.m.actions[1].onClick();
    check('F6 success → fresh token renewed + success toast', done !== false && p.rec.renewed === 'NEW'
          && p.rec.toasts.some(t => t.type === 'success' && t.msg === 'settings.pw.changed'));
  }

  // ── G — edu ──
  console.log('\nG — edu-profile');
  async function runEdu(opts) {
    const rec = newRec();
    const document = makeDocument(['profileLogo', 'profileName', 'profileDesc', 'profileLoc', 'aboutWeb', 'ownerActions', 'visitorActions']);
    const ctx = baseCtx(rec, opts, document);
    ctx._eduProfileIdFromRoute = 7;
    const snap = opts.snap || { isAuthenticated: false, userId: null, userType: null };
    ctx.TwAuthSync = { getSessionSnapshot: () => snap, onSessionChange() {} };
    vm.runInNewContext(EDU_JS, ctx, { filename: 'edu-profile.html' });
    await flush();
    return { rec, ctx, $: id => document.getElementById(id) };
  }
  const EDU_PROFILE = OK({ profile: { full_name: 'جامعة', bio: 'b', location: 'عمان', website: 'https://u.edu', tw_id: 'T7' } });
  {
    const v = await runEdu({ api: { 'GET /profile/7': EDU_PROFILE } });
    const load = v.rec.api.find(a => a.key === 'GET /profile/7');
    check('G1 public profile via twApi (auth:false)', !!load && load.auth === false);
    check('G2 fields rendered', v.$('profileName')._text === 'جامعة' && v.$('aboutWeb').href === 'https://u.edu');
    check('G3 visitor → twAction(message) shown', v.$('visitorActions').find(e => e.getAttribute('data-tw-action') === 'message').length === 1);
    check('G4 visitor → no edit button', !v.rec.actions.some(a => a.id === 'edit_profile'));
    check('G5 localStorage never read', !v.rec.lsTouched);
    const m = v.rec.actions.find(a => a.id === 'message');
    check('G5b «مراسلة» asks the server rule (twCanMessage) and passes canMessage', (v.rec.canMsg || []).map(String).includes('7')
      && !!m && m.ctx.canMessage === true);
  }
  {
    const v = await runEdu({ canMessage: false, api: { 'GET /profile/7': EDU_PROFILE } });
    const m = v.rec.actions.find(a => a.id === 'message');
    check('G5c server says no → canMessage false reaches twAction', !!m && m.ctx.canMessage === false);
  }
  {
    const o = await runEdu({ snap: { isAuthenticated: true, userId: 7, userType: 'edu' }, viewerIsOwnerOf: true,
      api: { 'GET /profile/7': EDU_PROFILE, 'PUT /profile/7': OK({ ok: true }), 'PUT /auth/user/7/name': OK({ ok: true }) } });
    const edit = o.$('ownerActions').find(e => e.getAttribute('data-tw-action') === 'edit_profile')[0];
    check('G6 owner → twAction(edit_profile)', !!edit && o.rec.actions.some(a => a.id === 'edit_profile' && a.ctx.mode === 'owner'));
    edit.click();
    const m = o.rec.modals[0];
    check('G7 edit opens twModal', !!m && m.m.title === 'edu.edit.title');
    const inputs = m.m.content.find(e => e.tagName === 'INPUT' || e.tagName === 'TEXTAREA');
    inputs[3].value = 'javascript:alert(1)';
    check('G8 unsafe website → stays open, no request', m.m.actions[1].onClick() === false
          && !o.rec.api.some(a => a.key === 'PUT /profile/7'));
    inputs[3].value = 'https://new.edu'; inputs[0].value = 'جامعة جديدة';
    const r = await m.m.actions[1].onClick();
    check('G9 save → PUT /profile + PUT name, success', r !== false && o.rec.api.some(a => a.key === 'PUT /profile/7' && a.body.website === 'https://new.edu')
          && o.rec.api.some(a => a.key === 'PUT /auth/user/7/name') && o.rec.toasts.some(t => t.type === 'success'));
  }

  // ── K — verify_identity off by default ──
  console.log('\nK — verify_identity off by default (until plan 5.1)');
  {
    check('K1 registry default: verify_identity is off', mergedActions({}).verify_identity.off === true);
    const off = await runSettings({ overrides: {}, api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: null }) } });
    check('K2 action off → KYC row removed from the page', off.$('kycRow') === null);
    check('K3 action off → no button and no KYC text', !kycBtn(off) && off.$('kycState') === null
          && !off.rec.actions.some(a => a.id === 'verify_identity'));
    check('K4 action off → no /kyc request', !off.rec.api.some(a => a.key.indexOf('/kyc/') >= 0), off.rec.api.map(a => a.key));
    check('K5 rest of the page still works', off.$('dispName')._text === 'جامعة');
    const on = await runSettings({ overrides: KYC_ON, api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc: null }) } });
    check('K6 admin override enabled:true → row shown with the button', !!on.$('kycRow') && on.$('kycRow').hidden === false && !!kycBtn(on));
  }

  // ── N — rejected → the admin's reason above «إعادة المحاولة» (task 8.1) ──
  console.log('\nN — KYC rejection reason');
  async function openRejected(kyc) {
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /kyc/status/7': OK({ status: 'success', kyc }) } });
    kycBtn(p).click();
    await flush();
    return lastModal(p).m.content;
  }
  {
    const reason = '<img src=x onerror=alert(1)> الصورة غير واضحة';
    const body = await openRejected({ step: 'rejected', status: 'rejected', reject_reason: reason });
    const box = byClass(body, 'st-result')[0];
    const text = byClass(body, 'st-kyc-reason-text')[0];
    const retry = btnByKey(body, 'settings.kyc.retry');
    check('N1 reason shown as plain text (textContent, no element from it)', !!text && text._text === reason
          && body.find(e => e.tagName === 'IMG').length === 0);
    const order = box ? box.children : [];
    const iReason = order.indexOf(byClass(body, 'st-kyc-reason')[0]), iRetry = order.indexOf(retry);
    check('N2 reason block sits above the retry button', iReason >= 0 && iRetry > iReason, { iReason, iRetry });
    const none = await openRejected({ step: 'rejected', status: 'rejected' });
    check('N3 no reason → no reason block, retry still there', byClass(none, 'st-kyc-reason').length === 0
          && !!btnByKey(none, 'settings.kyc.retry'));
  }

  // ── H — strings ──
  console.log('\nH — strings');
  {
    const used = new Set();
    [SETTINGS_JS, EDU_JS].forEach(src => (src.match(/twT\('([\w.]+)'/g) || []).forEach(m => used.add(m.slice(5, -1))));
    [SETTINGS_HTML, EDU_HTML].forEach(src => (src.match(/data-tw-t="([\w.]+)"/g) || []).forEach(m => used.add(m.slice(11, -1))));
    (SETTINGS_JS.match(/'settings\.[\w.]+'/g) || []).forEach(m => { const k = m.slice(1, -1); if (!/\.$/.test(k)) used.add(k); });
    ['email', 'phone'].forEach(ch => ['hint', 'label', 'required', 'verified'].forEach(s => used.add('settings.kyc.' + ch + '.' + s)));
    ['none', 'progress', 'review', 'approved', 'rejected'].forEach(s => used.add('settings.kyc.state.' + s));
    ['review', 'approved', 'rejected'].forEach(v => { used.add('settings.kyc.' + v + '.title'); used.add('settings.kyc.' + v + '.hint'); });
    ['emp', 'co', 'edu'].forEach(t => used.add('account.type.' + t));
    const missing = [...used].filter(k => !/\.$/.test(k) && !(k in STRINGS));
    check('H1 every key used exists in tw_strings.json', missing.length === 0, missing);
    const a = ACTIONS.verify_identity;
    check('H2 verify_identity action: label key exists + shield-check icon', !!a && a.labelKey in STRINGS && a.icon === 'shield-check');
  }

  // ── L — notification email switches (5.1c) ──
  console.log('\nL — notification email switches');
  {
    const TYPES = OK({ types: [
      { key: 'notify_message', enabled: true, available: true },
      { key: 'notify_appointment_invited', enabled: false, available: true },
      { key: 'notify_appointment_cancelled', enabled: true, available: false },
    ] });
    let putOk = true;
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE, 'GET /my/email-notifications': TYPES,
      'PUT /my/email-notifications': () => (putOk ? TYPES : FAIL(500, { fieldErrors: [], generalError: { code: 'unknown', message: 'x' } })) } });
    const sw = p.$('notifyList').find(e => e.hasAttribute('data-notify-type'));
    const byKey = k => sw.find(e => e.getAttribute('data-notify-type') === k);
    check('L1 one switch per type, state from the API', sw.length === 3 && byKey('notify_message').checked === true
          && byKey('notify_appointment_invited').checked === false);
    check('L2 type switched off by the admin → disabled', byKey('notify_appointment_cancelled').disabled === true
          && byKey('notify_message').disabled === false);
    const m = byKey('notify_message');
    m.checked = false;
    p.$('notifyList').fire('change', { target: m });
    await flush();
    const put = p.rec.api.filter(a => a.key === 'PUT /my/email-notifications');
    check('L3 change → PUT {types:{notify_message:false}}', put.length === 1
          && JSON.stringify(put[0].body) === JSON.stringify({ types: { notify_message: false } }), put);
    check('L4 saved → success toast', p.rec.toasts.some(t => t.type === 'success' && t.msg === 'settings.notify.saved'));
    putOk = false;
    m.checked = true;
    p.$('notifyList').fire('change', { target: m });
    await flush();
    check('L5 save failed → switch rolled back + error toast', m.checked === false && p.rec.toasts.some(t => t.type === 'error'));
  }

  // ── M — «المحظورون» (task 5.4): own list from GET /blocks · «إلغاء الحظر» → DELETE /blocks/{id} ──
  console.log('\nM — blocked list');
  {
    let delOk = true;
    const p = await runSettings({ api: { 'GET /profile/7/full': PROFILE,
      'GET /blocks?offset=0': OK({ items: [{ id: 41, full_name: 'سامي', user_type: 'emp', blocked_at: '2026-10-20T10:00:00Z' },
                                           { id: 42, full_name: 'شركة', user_type: 'co', blocked_at: '2026-10-21T10:00:00Z' }], total: 2 }),
      'DELETE /blocks/41': () => (delOk ? OK({ blocked: false }) : FAIL(500, { fieldErrors: [], generalError: { code: 'unknown', message: 'x' } })) } });
    const un = () => p.$('blockedList').find(e => e.getAttribute('data-tw-action') === 'unblock');
    check('M1 one row + «إلغاء الحظر» (twAction unblock) per blocked account', un().length === 2
          && p.rec.api.some(a => a.key === 'GET /blocks?offset=0'));
    delOk = false;
    un()[0].click();
    await flush();
    check('M2 failed unblock → error toast, row stays', un().length === 2 && p.rec.toasts.some(t => t.type === 'error'));
    delOk = true;
    un()[0].click();
    await flush();
    check('M3 unblock → one DELETE /blocks/41, row removed, success toast',
          p.rec.api.filter(a => a.key === 'DELETE /blocks/41').length === 2 && un().length === 1
          && p.rec.toasts.some(t => t.type === 'success' && t.msg === 'settings.unblock.done'));
    const e = await runSettings({ api: { 'GET /profile/7/full': PROFILE } });
    check('M4 empty list → empty-state text', e.$('blockedList').find(x => x._text === 'settings.blocked.empty').length === 1);
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
