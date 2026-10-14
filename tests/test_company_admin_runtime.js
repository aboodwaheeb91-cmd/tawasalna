/*
 * Runtime test — company page owner dashboard + jobs (PR 4.3c).
 * Real code from company.main.js / company.jobs.js (vm, @vm-extract markers), stubbed DOM + twApi.
 *
 *   1. «تعديل الملف» save: 3 PUTs one after the other; success → closeEdit() + button reset;
 *      a failed PUT stops the chain, keeps the modal open, names the part, resets the button,
 *      and applies only the parts the server confirmed.
 *   2. _loadApplicants: a reply for job A that lands after the modal moved to job B is dropped.
 *   3. submitRating: one request on a double click; guest → login; result reported.
 *
 * Run: node tests/test_company_admin_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function assert(name, cond, extra) {
  if (cond) { passed++; console.log('  ✅ ' + name); }
  else { failed++; console.log('  ❌ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}
function extract(src, key) {
  const b = '// @vm-extract-begin: ' + key, e = '// @vm-extract-end: ' + key;
  const si = src.indexOf(b), ei = src.indexOf(e, si);
  if (si < 0 || ei < 0) throw new Error('marker not found: ' + key);
  return src.slice(si, ei + e.length);
}
const MAIN = fs.readFileSync('./static/company/company.main.js', 'utf8');
const JOBS = fs.readFileSync('./static/company/company.jobs.js', 'utf8');
const STR  = JSON.parse(fs.readFileSync('./tw_strings.json', 'utf8')).ar;
const twT  = (k, v) => String(STR[k] || k).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m));
const twApiMessage = (res, fb) => (res && res.error && res.error.generalError && res.error.generalError.message) || fb;
const tick = () => new Promise(r => setImmediate(r));
const fail = (status, message) => ({ ok: false, status, data: null, raw: null,
  error: { fieldErrors: [], generalError: { code: 'x', message } } });

// ── 1. saveEdit ─────────────────────────────────────────────────────────
function saveCtx(answers) {
  const els = {
    'e-name': { value: 'شركة جديدة' }, 'e-desc': { value: 'وصف' }, 'e-country': { value: 'الأردن' },
    'e-city-sel': { value: 'عمّان' }, 'e-district': { value: 'العبدلي' }, 'e-type': { value: 'تقنية' },
    'e-founded': { value: '2010' }, 'e-size': { value: '11-50' },
    editSaveBtn: { disabled: false, textContent: 'حفظ' },
  };
  const calls = [], toasts = [], seen = { closeEdit: 0, loadData: 0, renderProfile: 0, renderBranches: 0 };
  const ctx = {
    window: {}, twT, twApiMessage, String, parseInt, isNaN,
    companyState: { permissions: { can_edit: true }, profile: { id: 5, full_name: 'قديم', bio: 'قديم' },
                    company: { industry: 'قديم' }, branches: [{ country: 'قديم' }] },
    _branchesLoaded: true,
    document: { getElementById: id => els[id] || null, querySelectorAll: () => [] },
    showToast: (m, t) => toasts.push({ m, t: t || 'ok' }),
    closeEdit: () => { seen.closeEdit++; },
    loadData: () => { seen.loadData++; },
    renderProfile: () => { seen.renderProfile++; },
    renderBranches: () => { seen.renderBranches++; },
    twApi: (path, opts) => {
      calls.push({ path, method: opts.method, open: calls.length - done.length });
      const i = calls.length - 1;
      return new Promise(r => setImmediate(() => { done.push(i); r(answers[i] || { ok: true, status: 200, raw: {} }); }));
    },
  };
  const done = [];
  ctx.window = ctx;
  ctx.window.showToast = ctx.showToast; ctx.window.loadData = ctx.loadData;
  ctx.window.renderProfile = ctx.renderProfile; ctx.window.renderBranches = ctx.renderBranches;
  vm.createContext(ctx);
  vm.runInContext(extract(MAIN, 'co-save-edit'), ctx);
  return { ctx, els, calls, toasts, seen };
}

(async () => {
  console.log('1. «تعديل الملف» save');
  {
    const t = saveCtx([]);
    vm.runInContext('saveEdit()', t.ctx);
    assert('button disabled + «جاري الحفظ…» while saving', t.els.editSaveBtn.disabled === true);
    vm.runInContext('saveEdit()', t.ctx);   // double click
    for (let i = 0; i < 6; i++) await tick();
    assert('3 PUTs, one after the other (never two in flight)',
      t.calls.length === 3 && t.calls.every(c => c.method === 'PUT' && c.open === 0), t.calls);
    assert('order: company → profile → branches',
      /\/company\/profile\/5$/.test(t.calls[0].path) && /^\/profile\/5$/.test(t.calls[1].path)
      && /\/company\/branches\/5$/.test(t.calls[2].path), t.calls.map(c => c.path));
    assert('success → closeEdit() (overlay + history entry) + one success toast',
      t.seen.closeEdit === 1 && t.toasts.length === 1 && t.toasts[0].t === 'ok', t.toasts);
    assert('success → button back to «حفظ», enabled',
      t.els.editSaveBtn.disabled === false && t.els.editSaveBtn.textContent === 'حفظ', t.els.editSaveBtn);
    assert('success → page updated locally + silent sync',
      t.ctx.companyState.profile.full_name === 'شركة جديدة' && t.seen.loadData === 1);
  }
  {
    const t = saveCtx([{ ok: true, status: 200, raw: {} }, fail(400, 'الاسم غير صالح')]);
    vm.runInContext('saveEdit()', t.ctx);
    for (let i = 0; i < 6; i++) await tick();
    assert('failure on the 2nd PUT stops the chain (branches not sent)', t.calls.length === 2, t.calls.length);
    assert('failure → modal stays open (no closeEdit)', t.seen.closeEdit === 0);
    const msg = (t.toasts[0] || {}).m || '';
    assert('failure → one error toast naming the part + the server reason + retry hint',
      t.toasts.length === 1 && t.toasts[0].t === 'error'
      && msg.indexOf(twT('company.edit.part.profile')) !== -1 && msg.indexOf('الاسم غير صالح') !== -1
      && msg.indexOf(twT('company.edit.partial_retry')) !== -1, t.toasts);
    assert('failure → button reset (enabled, «حفظ»)',
      t.els.editSaveBtn.disabled === false && t.els.editSaveBtn.textContent === 'حفظ');
    assert('only the confirmed part is applied (company yes, profile + branches untouched)',
      t.ctx.companyState.company.industry === 'تقنية' && t.ctx.companyState.profile.full_name === 'قديم'
      && t.ctx.companyState.branches[0].country === 'قديم' && t.seen.renderBranches === 0);
  }

  // ── 2. stale applicants reply ─────────────────────────────────────────
  console.log('\n2. applicants: last job wins');
  {
    const pending = [], rendered = [];
    const list = { innerHTML: '' };
    const ctx = vm.createContext({
      String, parseInt, twEscHtml: s => String(s), twT,   // PR 4.14: the loader text is twT (tw_shared.js on the page)
      TwCompanyPage: { signedIn: () => true },
      document: { getElementById: () => list },
      twApi: path => new Promise(r => pending.push({ path, r })),
      _renderApplicants: apps => rendered.push(apps.map(a => a.id)),
    });
    vm.runInContext('var _appJobId = null, _appLoading = false;' + extract(MAIN, 'co-applicants-load'), ctx);
    vm.runInContext('_appJobId = 1; _loadApplicants(1); _appJobId = 2; _loadApplicants(2);', ctx);
    assert('switching job sends a new request (not dropped while the first is in flight)', pending.length === 2);
    pending[1].r({ ok: true, status: 200, raw: { applicants: [{ id: 'B' }] } });
    await tick();
    pending[0].r({ ok: true, status: 200, raw: { applicants: [{ id: 'A' }] } });
    await tick();
    assert('job A reply arriving late is ignored — job B list stays', JSON.stringify(rendered) === '[["B"]]', rendered);
  }

  // ── 3. rating submit ──────────────────────────────────────────────────
  console.log('\n3. rating: one submit');
  {
    const reqs = [], toasts = [];
    let toLogin = 0, signed = true;
    const ctx = vm.createContext({
      String, URLSearchParams, Promise, location: { search: '' },
      _signedIn: () => signed, _toLogin: () => { toLogin++; },
      twApiMessage,
      companyState: { profile: { id: 9 }, permissions: { can_rate: true, my_rating: null },
                      stats: { rating_avg: null, rating_count: 0 } },
      twApi: (path, opts) => { reqs.push({ path, opts }); return new Promise(r => setImmediate(() =>
        r({ ok: true, status: 200, raw: { status: 'success', rating_avg: 4, rating_count: 1, my_score: 4 } }))); },
      showToast: (m, t) => toasts.push({ m, t: t || 'ok' }),
    });
    ctx.window = ctx;
    vm.runInContext('var isRateLoading = false;' + extract(JOBS, 'co-rating-submit'), ctx);
    const p1 = vm.runInContext('submitRating(4)', ctx);
    const p2 = vm.runInContext('submitRating(4)', ctx);
    const [r1, r2] = await Promise.all([p1, p2]);
    assert('double click → one POST', reqs.length === 1 && reqs[0].opts.method === 'POST', reqs.length);
    assert('first resolves true, the guarded one false', r1 === true && r2 === false);
    assert('success toast + state from the server', toasts.length === 1 && toasts[0].t === 'ok'
      && ctx.companyState.stats.rating_count === 1 && ctx.companyState.permissions.my_rating === 4, toasts);
    signed = false;
    const r3 = await vm.runInContext('submitRating(3)', ctx);
    assert('guest → login (twLoginHref path), no request', r3 === false && toLogin === 1 && reqs.length === 1);
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
