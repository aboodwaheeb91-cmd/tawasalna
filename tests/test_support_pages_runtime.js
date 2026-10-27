/**
 * test_support_pages_runtime.js — support pages (task 7.2a واجهة · docs/rules/support.md → الواجهة)
 * Runs the REAL static/support/support-form.js + support.js / support-track.js in a Node vm with a fake DOM
 * and a stubbed twApi.
 *   A  /support FAQ: categories in the order of GET /support/meta · local search over question + answer ·
 *      no hit → the «no results» line
 *   B  account: «لم تُحلّ مشكلتي» fills the category + faq_id → POST /support/tickets carries both ·
 *      the optional fields of the category come from meta (list → <select>)
 *   C  guest: «لم تُحلّ» on «الدخول والحساب» only (other categories → login link) · no category list ·
 *      code first, then POST /support/guest/tickets (auth:false, faq_id, no category) · done = text + H number
 *   D  /support/track (7.4): the token from the hash → replaceState clears it → sessionStorage · the link alone →
 *      code screen (masked address, «أرسل الرمز» disabled until the reply + cooldown) → verify → {session} →
 *      the thread · reply / resolve carry {session} only · 401 → code screen · a reload keeps the session ·
 *      no link and no session → «افتح الرابط من الإيميل» · 404 → general text + «إعادة إرسال الرابط»
 *   E  no innerHTML anywhere on these pages
 *
 * Run: node tests/test_support_pages_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const FORM = fs.readFileSync('static/support/support-form.js', 'utf8');
const PAGE = fs.readFileSync('static/support/support.js', 'utf8');
const TRACK = fs.readFileSync('static/support/support-track.js', 'utf8');
const innerHtml = [];

function fakeEl(tag) {
  const ls = {};
  const e = {
    tagName: tag, className: '', hidden: false, children: [], attrs: {}, value: '', type: '', href: '',
    disabled: false, readOnly: false, _text: '',
    get textContent() { return this._text + this.children.map(c => c.textContent).join(''); },
    set textContent(v) { this._text = String(v); this.children = []; },
    set innerHTML(v) { innerHtml.push([tag, String(v)]); },
    get options() { return this.children.filter(c => c.tagName === 'option'); },
    classList: { toggle() {}, add() {}, remove() {} },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { if (c.parent) c.parent.children.splice(c.parent.children.indexOf(c), 1); c.parent = this; this.children.push(c); return c; },
    insertBefore(c, ref) { c.parent = this; this.children.splice(this.children.indexOf(ref), 0, c); return c; },
    addEventListener(t, fn) { (ls[t] = ls[t] || []).push(fn); }, fire(t, ev) { (ls[t] || []).forEach(fn => fn(ev || { key: '' })); },
    scrollIntoView() {}, focus() {},
  };
  return e;
}
const all = el => [el].concat((el.children || []).flatMap(all));
const visible = (el, root) => { for (let n = el; n && n !== root; n = n.parent) if (n.hidden) return false; return true; };
const settle = async () => { for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r)); };

const META = {
  categories: ['account', 'verification', 'jobs', 'general'], guest_category: 'account',
  fields: { account: [{ key: 'issue', type: 'enum', values: ['forgot_password', 'other'] }, { key: 'account_name', type: 'text', max: 100 }],
            verification: [{ key: 'submitted_date', type: 'date' }], jobs: [{ key: 'kind', type: 'enum', values: ['apply', 'post'] }],
            general: [] },
  faq: { account: ['forgot', 'no_code'], verification: ['how'], jobs: ['track', 'withdraw'], general: ['idea'] },
};

// opts: signedIn · hash · api(path, o) → twApi result · ids (page element ids)
function boot(src, opts) {
  const ids = {};
  (opts.ids || []).forEach(id => { ids[id] = fakeEl('div'); ids[id].id = id; });
  const rec = { calls: [], replaced: [], toasts: [], modals: [], timers: [] };
  const store = opts.store || {};
  const ctx = {
    sessionStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); },
                      removeItem: k => { delete store[k]; } },
    setTimeout: (fn, ms) => { rec.timers.push(fn); return rec.timers.length; },
    console, Promise, String, Object, Array, JSON,
    document: { createElement: fakeEl, createTextNode: t => { const n = fakeEl('#text'); n._text = String(t); return n; },
                getElementById: id => ids[id] || null, addEventListener() {}, body: fakeEl('body') },
    location: { hash: opts.hash || '', pathname: opts.path || '/support', search: '' },
    history: { replaceState: (s, t, u) => { rec.replaced.push(u); ctx.location.hash = ''; } },
    TwAuthSync: { getSessionSnapshot: () => ({ isAuthenticated: !!opts.signedIn }) },
    twT: (k, v) => k + (v && v.minutes ? ':' + v.minutes : '') + (v && v.seconds ? ':' + v.seconds : '')
                     + (v && v.email ? ':' + v.ticket + ':' + v.email : ''), twTApply() {},
    twLimit: n => ({ support_subject_max: 150, support_body_max: 4000 })[n],
    twFormatDateTime: v => String(v), twLoginHref: n => '/login?next=' + encodeURIComponent(n),
    twApiMessage: (res, fb) => (res && res.error && res.error.message) || fb,
    showToast: (m, t) => rec.toasts.push([m, t]),
    twConfirm: () => Promise.resolve(true),
    twModal: o => { rec.modals.push(o); return {}; },
    twApi: (path, o) => { rec.calls.push([path, o || {}]); return Promise.resolve(opts.api(path, o || {})); },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(FORM, ctx, { filename: 'support-form.js' });
  vm.runInContext(src, ctx, { filename: 'page.js' });
  return { ctx, ids, rec, store };
}

const PAGE_IDS = ['spFaq', 'spSearch', 'spNoHits', 'spFormSec', 'spNew', 'spResendSec', 'spResendBtn', 'spResend',
                  'spMineSec', 'spList', 'spHome', 'spThread'];
function api(extra) {
  return (path, o) => {
    if (path === '/support/meta') return { ok: true, status: 200, data: META };
    if (path === '/support/tickets' && !o.method) return { ok: true, status: 200, data: { items: [] } };
    return (extra && extra(path, o)) || { ok: true, status: 201, data: { public_id: 'HABCDEFGHIJ' } };
  };
}
// the input of the form field whose label text starts with key
function fieldInput(root, key) {
  const label = all(root).find(e => e.tagName === 'label' && e.children[0] && e.children[0]._text === key);
  return label && label.parent.children.find(c => ['input', 'textarea', 'select'].includes(c.tagName)
                                             || c.className === 'sp-date');
}
const button = (root, text) => all(root).find(e => e.tagName === 'button' && e._text === text && visible(e, root));

(async function main() {
  console.log('A — FAQ + local search');
  {
    const p = boot(PAGE, { signedIn: true, ids: PAGE_IDS, api: api() });
    await settle();
    const faq = p.ids.spFaq;
    const cats = faq.children.map(s => s.children[0]._text);
    check('A1 categories in meta order', JSON.stringify(cats) === JSON.stringify(META.categories.map(c => 'support.category.' + c)), cats);
    const rows = all(faq).filter(e => e.tagName === 'details');
    check('A2 one row per FAQ id, q / a from twT', rows.length === 6 && rows[0].children[0]._text === 'support.faq.account.forgot.q'
      && rows[0].children[1].children[0]._text === 'support.faq.account.forgot.a');
    p.ids.spSearch.value = 'JOBS.WITHDRAW.A';   // answer text, any case
    p.ids.spSearch.fire('input');
    const shown = rows.filter(r => visible(r, faq)).map(r => r.attrs['data-faq']);
    check('A3 search matches the answer too → one row, other categories hidden', JSON.stringify(shown) === '["jobs.withdraw"]', shown);
    check('A4 hit → «no results» hidden', p.ids.spNoHits.hidden === true);
    p.ids.spSearch.value = 'zzz';
    p.ids.spSearch.fire('input');
    check('A5 no hit → «no results» shown', p.ids.spNoHits.hidden === false && rows.every(r => !visible(r, faq)));
    p.ids.spSearch.value = '';
    p.ids.spSearch.fire('input');
    check('A6 empty search → every row back', rows.every(r => visible(r, faq)));
  }

  console.log('\nB — account: «لم تُحلّ» fills category + faq_id');
  {
    const p = boot(PAGE, { signedIn: true, ids: PAGE_IDS, api: api() });
    await settle();
    check('B0 my tickets shown, resend link hidden', p.ids.spMineSec.hidden === false && p.ids.spResendSec.hidden === true);
    all(p.ids.spFaq).find(e => e.attrs['data-faq-open'] === 'jobs.track').fire('click');
    const form = p.ids.spNew;
    const cat = fieldInput(form, 'support.form.category');
    check('B1 category filled', cat && cat.value === 'jobs', cat && cat.value);
    const kind = fieldInput(form, 'support.field.kind');
    check('B2 the category fields from meta (list → select with its values)', kind && kind.tagName === 'select'
      && kind.options.map(o => o.value).join() === ',apply,post');
    check('B3 the fixed «no password / code» line under the form', all(form).some(e => e._text === 'support.form.no_secrets'));
    fieldInput(form, 'support.form.subject').value = 'موضوع';
    fieldInput(form, 'support.form.body').value = 'رسالة';
    kind.value = 'apply';
    button(form, 'support.form.submit').fire('click');
    await settle();
    const post = p.rec.calls.find(c => c[0] === '/support/tickets' && c[1].method === 'POST');
    check('B4 POST /support/tickets carries category + faq_id + details', !!post && post[1].body.category === 'jobs'
      && post[1].body.faq_id === 'track' && post[1].body.details.kind === 'apply', post && JSON.stringify(post[1].body));
    // another category → the faq_id of jobs is dropped
    all(p.ids.spFaq).find(e => e.attrs['data-faq-open'] === 'jobs.track').fire('click');
    const c2 = fieldInput(p.ids.spNew, 'support.form.category');
    c2.value = 'general';
    c2.fire('change');
    fieldInput(p.ids.spNew, 'support.form.subject').value = 's';
    fieldInput(p.ids.spNew, 'support.form.body').value = 'b';
    p.rec.calls.length = 0;
    button(p.ids.spNew, 'support.form.submit').fire('click');
    await settle();
    const post2 = p.rec.calls.find(c => c[0] === '/support/tickets' && c[1].method === 'POST');
    check('B5 category changed → faq_id of the old category not sent', !!post2 && !('faq_id' in post2[1].body)
      && post2[1].body.category === 'general');
  }

  console.log('\nC — guest: «الدخول والحساب» only, OTP path');
  {
    const p = boot(PAGE, { signedIn: false, ids: PAGE_IDS, api: api() });
    await settle();
    const opens = all(p.ids.spFaq).filter(e => e.attrs['data-faq-open']).map(e => e.attrs['data-faq-open']);
    check('C1 «لم تُحلّ» on account FAQs only', JSON.stringify(opens) === '["account.forgot","account.no_code"]', opens);
    const links = all(p.ids.spFaq).filter(e => e.tagName === 'a');
    check('C2 other categories → login link back to /support', links.length === 4
      && links.every(a => a.href === '/login?next=%2Fsupport'));
    check('C3 my tickets hidden, «فقدت رابط المتابعة؟» shown', p.ids.spMineSec.hidden === true && p.ids.spResendSec.hidden === false);
    all(p.ids.spFaq).find(e => e.attrs['data-faq-open'] === 'account.no_code').fire('click');
    const form = p.ids.spNew;
    check('C4 no category list for the guest', !fieldInput(form, 'support.form.category'));
    const email = fieldInput(form, 'support.guest.email');
    check('C5 hint under the guest email', email && email.parent.children.some(c => c._text === 'support.guest.email_hint'));
    email.value = 'a@b.co';
    fieldInput(form, 'support.form.subject').value = 's';
    fieldInput(form, 'support.form.body').value = 'b';
    button(form, 'support.guest.send_code').fire('click');
    await settle();
    const code = p.rec.calls.find(c => c[0] === '/support/guest/code');
    check('C6 code first — POST /support/guest/code auth:false', !!code && code[1].auth === false && code[1].body.email === 'a@b.co');
    fieldInput(form, 'support.guest.code').value = '123456';
    button(form, 'support.guest.submit').fire('click');
    await settle();
    const t = p.rec.calls.find(c => c[0] === '/support/guest/tickets');
    check('C7 POST /support/guest/tickets: auth:false · code · faq_id · no category', !!t && t[1].auth === false
      && t[1].body.code === '123456' && t[1].body.faq_id === 'no_code' && !('category' in t[1].body), t && JSON.stringify(t[1].body));
    const text = form.textContent;
    check('C8 done: «أرسلنا رابط المتابعة» + the H number, no link shown', text.includes('support.guest.done')
      && text.includes('HABCDEFGHIJ') && !all(form).some(e => e.tagName === 'a'));
    p.ids.spResendBtn.fire('click');
    const rf = p.ids.spResend;
    fieldInput(rf, 'support.guest.email').value = 'x@y.co';
    button(rf, 'support.resend.submit').fire('click');
    await settle();
    const rs = p.rec.calls.find(c => c[0] === '/support/track/resend');
    check('C9 resend → POST /support/track/resend · one general text', !!rs && rs[1].auth === false
      && all(rf).some(e => e._text === 'support.resend.done'));
  }

  console.log('\nD — /support/track');
  {
    const thread = { public_id: 'HABCDEFGHIJ', category: 'account', status: 'awaiting_user', subject: 's', can_reopen: true,
                     messages: [{ author_type: 'admin', body: '<b>x</b>', created_at: 't' }] };
    let sessionOk = true, codeRes = null;
    const trackApi = (path, o) => {
      const b = o.body || {};
      if (path === '/support/track/view' && b.session) return sessionOk && b.session === 'sess_1'
        ? { ok: true, status: 200, data: thread } : { ok: false, status: 401, error: { message: 'support.error.track_session' } };
      if (path === '/support/track/view') return { ok: true, status: 200, data: { ticket: 'HABCDEFGHIJ', email: 'a***@gmail.com', verified: false } };
      if (path === '/support/track/code') return new Promise(r => { codeRes = r; });
      if (path === '/support/track/verify') return b.code === '123456' ? { ok: true, status: 200, data: { session: 'sess_1' } }
        : { ok: false, status: 422, error: { message: 'support.error.code_invalid', field: 'code' } };
      return { ok: true, status: 200, data: { status: 'resolved' } };
    };
    const p = boot(TRACK, { hash: '#t=tok_EN-123', path: '/support/track', ids: ['stRoot'], api: trackApi });
    check('D1 hash cleared at once (replaceState without the fragment) · link in sessionStorage',
      p.rec.replaced[0] === '/support/track' && p.ctx.location.hash === ''
      && JSON.parse(p.store.tw_support_track).t === 'tok_EN-123');
    await settle();
    const v = p.rec.calls[0];
    check('D2 POST /support/track/view {token} — token in the body only, no session yet', v[0] === '/support/track/view'
      && v[1].method === 'POST' && v[1].auth === false && v[1].body.token === 'tok_EN-123' && !('session' in v[1].body)
      && !v[0].includes('tok'));
    const R = p.ids.stRoot;
    check('D3 the link alone → code screen with the masked address, no thread',
      all(R).some(e => e._text === 'support.track.code_intro:HABCDEFGHIJ:a***@gmail.com')
      && !all(R).some(e => e._text === '<b>x</b>'));
    const send = button(R, 'support.track.send_code');
    send.fire('click');
    await settle();
    check('D4 «أرسل الرمز» → POST /support/track/code {token} · disabled until the reply',
      send.disabled === true && p.rec.calls.some(c => c[0] === '/support/track/code' && c[1].body.token === 'tok_EN-123'
        && !('email' in c[1].body)));
    codeRes({ ok: true, status: 200, data: { sent: true, cooldown_s: 2, minutes: 10 } });
    await settle();
    check('D5 cooldown counts down, then the button is back', send.disabled === true && send._text === 'support.track.code_wait:2'
      && (p.rec.timers.shift()(), send._text === 'support.track.code_wait:1')
      && (p.rec.timers.shift()(), send.disabled === false && send._text === 'support.track.send_code'));
    fieldInput(R, 'support.guest.code').value = '000000';
    button(R, 'support.track.verify').fire('click');
    await settle();
    check('D6 wrong code → error on the field, still the code screen', !!button(R, 'support.track.verify')
      && !p.store.tw_support_track.includes('sess_1'));
    fieldInput(R, 'support.guest.code').value = '123456';
    button(R, 'support.track.verify').fire('click');
    await settle();
    check('D7 right code → session in sessionStorage → the thread (message as text)',
      JSON.parse(p.store.tw_support_track).s === 'sess_1'
      && all(R).some(e => e._text === 'support.status_user.awaiting_user') && all(R).some(e => e._text === '<b>x</b>'));
    button(R, 'support.thread.resolve').fire('click');
    await settle();
    const rs = p.rec.calls.find(c => c[0] === '/support/track/resolve');
    check('D8 «تم الحل» → POST /support/track/resolve {session} only', !!rs && rs[1].body.session === 'sess_1' && !('token' in rs[1].body));

    // reload: the same tab (sessionStorage kept), no hash → straight to the thread
    const again = boot(TRACK, { hash: '', path: '/support/track', ids: ['stRoot'], api: trackApi, store: p.store });
    await settle();
    check('D9 reload keeps the session → view {session} → thread', again.rec.calls[0][1].body.session === 'sess_1'
      && all(again.ids.stRoot).some(e => e._text === '<b>x</b>'));
    // 401 (expired / revoked) → the session forgotten → code screen of the stored link
    sessionOk = false;
    const exp = boot(TRACK, { hash: '', path: '/support/track', ids: ['stRoot'], api: trackApi, store: p.store });
    await settle();
    check('D10 401 → code screen, session dropped', !!button(exp.ids.stRoot, 'support.track.send_code')
      && !('s' in JSON.parse(p.store.tw_support_track)));

    const n = boot(TRACK, { hash: '#t=bad', path: '/support/track', ids: ['stRoot'],
                            api: () => ({ ok: false, status: 404, error: { message: 'support.error.track_not_found' } }) });
    await settle();
    check('D11 404 → general text + «إعادة إرسال الرابط»', all(n.ids.stRoot).some(e => e._text === 'support.error.track_not_found')
      && !!all(n.ids.stRoot).find(e => e.tagName === 'button' && e._text === 'support.track.resend'));
    const none = boot(TRACK, { hash: '', path: '/support/track', ids: ['stRoot'], api: () => ({ ok: true, status: 200, data: {} }) });
    await settle();
    check('D12 no link and no session → no request, «افتح الرابط من الإيميل» (not «الرابط غير صالح»)',
      none.rec.calls.length === 0 && all(none.ids.stRoot).some(e => e._text === 'support.track.open_from_email')
      && !all(none.ids.stRoot).some(e => e._text === 'support.error.track_not_found'));
  }

  console.log('\nE — text only');
  check('E1 no innerHTML on the support pages', innerHtml.length === 0, JSON.stringify(innerHtml.slice(0, 3)));
  check('E2 support-track.js never touches innerHTML (any path, not only the ones run here)', !/innerHTML/.test(TRACK.replace(/\/\/[^\n]*/g, '')));

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
