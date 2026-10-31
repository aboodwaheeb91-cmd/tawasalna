/**
 * test_certificates_87_runtime.js — task 8.7: certificate PDF UI on the profile page (docs/rules/certificates.md).
 * Real code in a Node vm context (tw_shared.js + profile-v2.certs.js + profile-v2.courses.js + profile-v2.edu.js),
 * fake DOM + twApi / twModal stubs:
 *   A  «عرض الشهادة» only when the server says can_view_certificate (courses + education cards)
 *   B  the viewer: GET /certificates/{kind}/{id}/view → twModal with a sandboxed iframe + «فتح بتبويب جديد»
 *      (target _blank · rel noopener noreferrer · URL through twSafeLinkUrl) · failed / unsafe URL → no modal
 *   C  the legacy certificate_url: owner only, with «استبدل بملف PDF» · javascript: → no href
 *   D  the save payload never carries certificate_url · every cert.* key exists in tw_strings.json
 *
 * Run: node tests/test_certificates_87_runtime.js
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
const noop = () => {};
const flush = async () => { for (let i = 0; i < 10; i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase(); this.children = []; this.attrs = {}; this.style = {};
    this._text = ''; this.listeners = {}; this.hidden = false; this.disabled = false; this.value = '';
    this.options = []; this._cls = new Set();
    const self = this;
    this.classList = { add: (...c) => c.forEach(x => self._cls.add(x)), remove: (...c) => c.forEach(x => self._cls.delete(x)),
                       contains: c => self._cls.has(c) };
  }
  set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get className() { return [...this._cls].join(' '); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  closest() { return null; }
  focus() {}
  click() {}
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent || '').join(''); }
  set innerHTML(v) { this._html = String(v); }
  get innerHTML() { return this._html || ''; }
}

function makeCtx() {
  const ids = {};
  const docListeners = {};
  const doc = {
    readyState: 'complete', body: new El('body'), documentElement: new El('html'),
    getElementById: id => (ids[id] = ids[id] || new El(id.endsWith('Overlay') ? 'div' : 'input')),
    createElement: t => new El(t), createTextNode: t => ({ textContent: String(t) }),
    querySelectorAll: () => [], querySelector: () => null,
    addEventListener: (t, f) => { (docListeners[t] = docListeners[t] || []).push(f); },
  };
  const ctx = {
    document: doc, console: { log: noop, warn: noop, error: noop }, navigator: {}, location: { pathname: '/u/U1', search: '', origin: 'https://t.example' },
    localStorage: { getItem: () => null, setItem: noop, removeItem: noop }, setTimeout: () => 0, clearTimeout: noop,
    requestAnimationFrame: () => 0, URLSearchParams, Promise, JSON, Math, Date, Object, Array, String, Number, RegExp,
    fetch: () => Promise.reject(new Error('fetch not allowed')), FileReader: function () {},
    addEventListener: noop, removeEventListener: noop, matchMedia: () => ({ matches: false, addEventListener: noop }),
  };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(read('tw_shared.js'), ctx, { filename: 'tw_shared.js' });
  // stubs over the shared runtime (recorded)
  ctx.STRINGS = STRINGS;
  vm.runInContext("window.TW_STRINGS = {dict: STRINGS}; window.TW_LIMITS = {limits:{cert_max_bytes:5242880}, report_types:[]};", ctx);
  ctx.calls = []; ctx.modals = []; ctx.toasts = []; ctx.apiReplies = {};
  ctx.twApi = (path, opts) => { ctx.calls.push({ path, opts: opts || {} });
    return Promise.resolve(ctx.apiReplies[path] || { ok: false, status: 404, error: { message: 'x' }, data: null }); };
  ctx.twModal = o => { ctx.modals.push(o); return { close: noop }; };
  ctx.twConfirm = () => Promise.resolve(true);
  ctx.showToast = (m, t) => ctx.toasts.push([m, t]);
  ctx.twIcon = name => '<svg data-i="' + name + '"></svg>';
  ctx.twIconEl = name => { const e = new El('svg'); e.attrs['data-i'] = name; return e; };
  ctx.scConfirm = noop;
  vm.runInContext(read('profile-v2.certs.js'), ctx, { filename: 'profile-v2.certs.js' });
  vm.runInContext(read('profile-v2.edu.js'), ctx, { filename: 'profile-v2.edu.js' });
  vm.runInContext(read('profile-v2.courses.js'), ctx, { filename: 'profile-v2.courses.js' });
  ctx._ids = ids; ctx._docListeners = docListeners;
  return ctx;
}

async function main() {
  // ── A: view button only when can_view_certificate ──
  {
    const c = makeCtx();
    const courses = [{ id: 11, title: 'C1', has_certificate: true, can_view_certificate: true },
                     { id: 12, title: 'C2', has_certificate: true, can_view_certificate: false },
                     { id: 13, title: 'C3', has_certificate: false, can_view_certificate: false }];
    const html = c._buildCoursesHTML(courses, false);
    check('A1 course with can_view → one view button (that row)',
      (html.match(/data-tw-cert-view="course"/g) || []).length === 1 && html.includes('data-id="11"'), html.length);
    check('A2 no button for has_certificate without can_view', !html.includes('data-id="12"') && !html.includes('data-id="13"'));
    check('A3 button label from twT', html.includes(STRINGS['cert.view']));
    const eh = c._buildEduHTML([{ id: 21, institution: 'I', has_certificate: true, can_view_certificate: true },
                                { id: 22, institution: 'I', has_certificate: true, can_view_certificate: false }], false);
    check('A4 education: button only on the row the server allows',
      eh.includes('data-tw-cert-view="education"') && eh.includes('data-id="21"') && !eh.includes('data-id="22"'));
    check('A5 no inline onclick on the certificate button', !/data-tw-cert-view[^>]*onclick/.test(html));
  }

  // ── B: viewer ──
  {
    const c = makeCtx();
    const URL = 'https://sb.supabase.co/storage/v1/object/sign/cert-docs/7_cert_aaaaaaaaaaaa.pdf?token=T';
    c.apiReplies['/certificates/course/11/view'] = { ok: true, status: 200, data: { url: URL, expires_in: 300 } };
    const ok = await c.TwProfileCert.openViewer('course', 11);
    check('B1 view asks the server (GET, the right path)', c.calls[0] && c.calls[0].path === '/certificates/course/11/view'
      && !c.calls[0].opts.method, c.calls);
    check('B2 twModal opened', ok === true && c.modals.length === 1);
    const box = c.modals[0] && c.modals[0].content;
    const frame = box && box.children.find(x => x.tagName === 'IFRAME');
    const link = box && box.children.find(x => x.tagName === 'A');
    check('B3 iframe preview: src = the signed URL + sandbox without top-navigation / popups / forms',
      frame && frame.src === URL && typeof frame.attrs.sandbox === 'string'
      && !/allow-top-navigation|allow-popups|allow-forms/.test(frame.attrs.sandbox)
      && frame.attrs.referrerpolicy === 'no-referrer', frame && frame.attrs);
    check('B4 «فتح بتبويب جديد»: _blank + noopener noreferrer + same URL',
      link && link.href === URL && link.target === '_blank' && link.rel === 'noopener noreferrer'
      && link.textContent.includes(STRINGS['cert.open_new_tab']));
    // failed view (404 — no access / no file) → toast, no modal
    const c2 = makeCtx();
    c2.apiReplies['/certificates/education/5/view'] = { ok: false, status: 404, error: { message: STRINGS['cert.err.not_found'] } };
    const r2 = await c2.TwProfileCert.openViewer('education', 5);
    check('B5 404 → no modal + error toast', r2 === false && c2.modals.length === 0 && c2.toasts.length === 1
      && c2.toasts[0][1] === 'error');
    // a non-https URL from the server is never framed
    const c3 = makeCtx();
    c3.apiReplies['/certificates/course/9/view'] = { ok: true, status: 200, data: { url: 'javascript:alert(1)' } };
    const r3 = await c3.TwProfileCert.openViewer('course', 9);
    check('B6 unsafe URL → no modal', r3 === false && c3.modals.length === 0);
    const r4 = await c3.TwProfileCert.openViewer('nope', 9);
    check('B7 unknown kind → no request', r4 === false && c3.calls.length === 1);
    // delegated click on the card button
    const c4 = makeCtx();
    c4.apiReplies['/certificates/course/11/view'] = { ok: true, status: 200, data: { url: URL } };
    const btn = new El('button'); btn.attrs['data-tw-cert-view'] = 'course'; btn.attrs['data-id'] = '11';
    btn.closest = sel => (sel === '[data-tw-cert-view]' ? btn : null);
    (c4._docListeners.click || []).forEach(f => f({ target: btn, preventDefault: noop }));
    await flush();
    check('B8 card button (event delegation) opens the viewer', c4.modals.length === 1);
  }

  // ── C: legacy link ──
  {
    const c = makeCtx();
    const legacy = { id: 31, title: 'L', certificate_url: 'https://old.example/c', has_certificate: false };
    const own = c._buildCoursesHTML([legacy], true);
    check('C1 owner sees the legacy link + «استبدل بملف PDF»',
      own.includes('href="https://old.example/c"') && own.includes('rel="noopener noreferrer"')
      && own.includes('data-tw-cert-replace="31"') && own.includes(STRINGS['cert.legacy.replace']));
    const other = c._buildCoursesHTML([legacy], false);
    check('C2 non-owner never sees it (even if a value slipped through)', !other.includes('old.example')
      && !other.includes('data-tw-cert-replace'));
    const bad = c._buildCoursesHTML([{ id: 32, title: 'B', certificate_url: 'javascript:alert(1)' }], true);
    check('C3 javascript: legacy value → text only, no href', !bad.includes('href="javascript') && !/href="[^"]*alert/.test(bad));
  }

  // ── D: payload + strings ──
  {
    const c = makeCtx();
    c._scProfile = { courses: [] };
    c._scUserId = 7;
    c._currentJwt = () => 'jwt';
    c._scViewerType = 'owner';
    let sent = null;
    c.addCourse = (uid, p) => { sent = p; return Promise.resolve({ ok: true, status: 200, data: { course: { id: 40, title: 'T' } } }); };
    c.document.getElementById('courseTitle').value = 'T';
    c.document.getElementById('courseSaveBtn').onclick();
    await flush();
    check('D1 save payload has no certificate_url', sent && !('certificate_url' in sent), sent);
    const src = read('profile-v2.certs.js');
    const keys = new Set((src.match(/twT\('([a-z0-9._]+)'/g) || []).map(s => s.slice(5, -1)));
    const missing = [...keys].filter(k => typeof STRINGS[k] !== 'string');
    check('D2 every twT key used by profile-v2.certs.js exists', keys.size > 10 && missing.length === 0, missing);
    const page = read('profile-showcase.html');
    const iCerts = page.indexOf('profile-v2.certs.js'), iCourses = page.indexOf('profile-v2.courses.js'),
          iEdu = page.indexOf('profile-v2.edu.js');
    check('D3 the page loads profile-v2.certs.js before the course / education modules',
      iCerts > 0 && iCerts < iCourses && iCerts < iEdu);
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}
main().catch(e => { console.error(e); process.exit(1); });
