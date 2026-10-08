/*
 * Runtime test — per-job classification picker on the saved-candidate card (SYSTEMS_INDEX §20c)
 * + notifications badge cap (ARCHITECTURE §52 — twNotifBadgeLabel).
 *
 * Real code in Chromium (Playwright): tw_shared.js + company.api.js + company.main.js + company.css.
 * The API layer is stubbed (window.getSavedCandidates / updateCandidateJobStatus); any network
 * call to /jobs/applications (job_applications.status writer) fails the test.
 *
 * Run:   node tests/test_candidate_job_status_picker_runtime.js
 * Shots: SHOTS_DIR=<dir> SHOTS_TAG=before|after node tests/test_candidate_job_status_picker_runtime.js
 */
'use strict';
const fs   = require('fs');
const path = require('path');

function _requirePlaywright() {
  try { return require('playwright'); } catch (e) {}
  const root = require('child_process').execSync('npm root -g').toString().trim();
  return require(path.join(root, 'playwright'));
}
const { chromium } = _requirePlaywright();

const ROOT = require('path').join(__dirname, '..');
const MIME = { '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };

const ITEM = {
  candidate_id: 42, tw_id: 'U1234567', full_name: 'سارة أحمد', profession: 'مهندسة برمجيات',
  city: 'عمّان', country: 'الأردن', status: 'shortlisted', notes: '', created_at: '2026-09-01T10:00:00Z',
  save_source: 'applicant', tags: [],
  job_links: [
    { job_id: 7, title: 'مطوّر واجهات', application_id: 501, apply_date: '2026-09-02T10:00:00Z',
      application_status: 'interview', status: 'interview', candidate_status: 'interview' },
    { job_id: 9, title: '<img src=x onerror="window.__xss=1">محلل بيانات', application_id: null,
      apply_date: null, application_status: null, status: null, candidate_status: null }
  ]
};

// Screenshots use a readable title (the escaping case is covered by A5).
if (process.env.SHOTS_DIR) ITEM.job_links[1].title = 'محلل بيانات';

const HARNESS = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/app-header.css">
<link rel="stylesheet" href="/static/company/company.css">
<style>body{background:#0b0f1a;color:#fff;font-family:Cairo,system-ui,sans-serif;margin:0}</style>
</head><body>
<div class="co-fl-overlay" id="coCandidatesModal" style="display:none">
  <div class="co-fl-panel co-cand-panel">
    <div class="co-fl-head co-cand-head">
      <div class="co-cand-tabs" id="coCandTabs">
        <button class="co-cand-tab active" data-tab="saved">المحفوظون</button>
        <button class="co-cand-tab" data-tab="suggestions">اقتراحات مناسبة</button>
      </div>
      <button class="co-fl-close" id="coCandClose" aria-label="إغلاق">×</button>
    </div>
    <div class="co-cand-body" id="coCandBody"></div>
  </div>
</div>
<script>
  window._companyProfileIdFromRoute = 1;   // page bootstrap (loadData) stays on the page
  window.__calls = []; window.__netWrites = []; window.__toasts = []; window.__pending = null;
  var _realFetch = window.fetch;
  window.fetch = function (url, opts) {
    if (String(url).indexOf('/jobs/applications') !== -1) window.__netWrites.push(String(url));
    return Promise.resolve(new Response('{}', { status: 200 }));
  };
</script>
<script src="/tw_shared.js"></script>
<script src="/static/company/company.api.js"></script>
<script>
  window.companyState = { permissions: { can_edit: true }, jobs: [] };
  window._jwt = function () { return 'x'; };
  window.showToast = function (msg, type) { window.__toasts.push({ msg: msg, type: type || 'success' }); };
  var ITEM = ${JSON.stringify(ITEM)};
  window.getSavedCandidates = function () {
    return Promise.resolve({ ok: true, data: { items: [JSON.parse(JSON.stringify(ITEM))],
                                               pagination: { offset: 0, has_more: false } } });
  };
  window.getSavedCandidatesStats = function () { return Promise.resolve({ ok: true, data: { total: 1, by_status: {} } }); };
  window.updateCandidateJobStatus = function (cid, jid, cs) {
    window.__calls.push({ cid: cid, jid: jid, cs: cs });
    return new Promise(function (resolve) { window.__pending = resolve; });
  };
</script>
<script src="/static/company/company.main.js"></script>
</body></html>`;

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}

async function newPage(browser, viewport) {
  const ctx  = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname !== 'harness.local') return route.abort();
    if (u.pathname === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: HARNESS });
    const f = path.join(ROOT, u.pathname);
    if (!f.startsWith(ROOT) || !fs.existsSync(f)) return route.fulfill({ status: 404, body: '' });
    return route.fulfill({ status: 200, contentType: MIME[path.extname(f)] || 'text/plain', body: fs.readFileSync(f) });
  });
  await page.goto('http://harness.local/');
  if (!(await page.evaluate(() => typeof window._coCandOpen === 'function'))) {
    throw new Error('company.main.js did not boot: ' + JSON.stringify(errors) + ' @ ' + page.url());
  }
  await page.evaluate(() => window._coCandOpen());
  await page.waitForSelector('.co-cand-saved-card[data-cid="42"]');
  await page.click('.co-cand-saved-card[data-cid="42"] .co-csc-toggle');
  return { ctx, page, errors };
}

const picker = jid => `.co-cand-job-status-dp[data-jid="${jid}"]`;
async function pickerState(page, jid) {
  return page.evaluate(sel => {
    const w = document.querySelector(sel);
    if (!w) return null;
    const b = w.querySelector('.co-dp-btn');
    return { label: w.querySelector('.co-dp-val').textContent, selected: w.getAttribute('data-selected'),
             cls: w.className, disabled: b.disabled };
  }, picker(jid));
}
async function choose(page, jid, value) {
  await page.click(picker(jid) + ' .co-dp-btn');
  await page.click(picker(jid) + ` .co-dp-opt[data-value="${value}"]`);
}
const linksOf = page => page.evaluate(() =>
  JSON.parse(document.querySelector('.co-cand-saved-card[data-cid="42"]').getAttribute('data-job-links')));

(async () => {
  const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});

  // ── Screenshots mode ───────────────────────────────────────────
  if (process.env.SHOTS_DIR) {
    const tag = process.env.SHOTS_TAG || 'after';
    for (const [name, vp] of [['mobile', { width: 390, height: 844 }], ['desktop', { width: 1280, height: 900 }]]) {
      const { ctx, page } = await newPage(browser, vp);
      await page.locator('.co-cand-saved-card[data-cid="42"]').screenshot(
        { path: path.join(process.env.SHOTS_DIR, `card-${tag}-${name}.png`) });
      if (await page.$(picker(9))) {
        await page.click(picker(9) + ' .co-dp-btn');
        await page.locator('.co-cand-saved-card[data-cid="42"]').screenshot(
          { path: path.join(process.env.SHOTS_DIR, `card-${tag}-${name}-open.png`) });
      }
      await ctx.close();
    }
    await browser.close();
    console.log('screenshots → ' + process.env.SHOTS_DIR);
    return;
  }

  const { page, errors } = await newPage(browser, { width: 390, height: 844 });

  console.log('A. Render');
  const s7 = await pickerState(page, 7), s9 = await pickerState(page, 9);
  check('A1. one picker per job_links[] entry', (await page.$$('.co-cand-job-status-dp')).length === 2);
  check('A2. classified job shows its label + status palette class',
        s7 && s7.label === 'مقابلة' && s7.selected === 'interview' && /co-cand-status--interview/.test(s7.cls), s7);
  check('A3. null candidate_status shows «غير مصنّف» (neutral, no palette class)',
        s9 && s9.label === 'غير مصنّف' && s9.selected === '' && !/co-cand-status--/.test(s9.cls), s9);
  const opts = await page.$$eval(picker(9) + ' .co-dp-opt', os => os.map(o => o.getAttribute('data-value')));
  check('A4. 7 options: unset + the 6 VALID_CANDIDATE_STATUSES',
        JSON.stringify(opts) === JSON.stringify(['', 'saved', 'shortlisted', 'contacted', 'interview', 'hired', 'rejected']), opts);
  const titleTxt = await page.$eval(`.co-cand-job-status-dp[data-jid="9"]`, w => w.parentNode.querySelector('.co-cand-job-status-title').textContent);
  check('A5. job title escaped (twEscHtml) — rendered as text, no injected element',
        titleTxt.indexOf('<img') === 0 && !(await page.evaluate(() => window.__xss)));
  check('A6. section title «تصنيف المرشح لكل وظيفة»',
        (await page.textContent('.co-cand-job-status-section .co-cand-job-section-title')).indexOf('تصنيف المرشح لكل وظيفة') === 0);

  console.log('B. Change → PATCH (success)');
  await choose(page, 9, 'shortlisted');
  const c1 = await page.evaluate(() => window.__calls[0]);
  check('B1. PATCH via updateCandidateJobStatus(cid, jid, value)', c1 && c1.cid === 42 && c1.jid === 9 && c1.cs === 'shortlisted', c1);
  const busy = await pickerState(page, 9);
  check('B2. picker locked + old value kept while in flight (no optimistic UI)',
        busy.disabled === true && busy.label === 'غير مصنّف', busy);
  check('B3. other job picker of the same card locked too', (await pickerState(page, 7)).disabled === true);
  await page.evaluate(() => window.__pending({ ok: true, data: { candidate_status: 'shortlisted' } }));
  await page.waitForFunction(sel => !document.querySelector(sel + ' .co-dp-btn').disabled, picker(9));
  const ok = await pickerState(page, 9);
  check('B4. success → new label + palette class + unlocked',
        ok.label === 'مرشح قوي' && /co-cand-status--shortlisted/.test(ok.cls) && !ok.disabled, ok);
  check('B5. data-job-links updated locally (candidate_status only)',
        (await linksOf(page)).find(l => l.job_id === 9).candidate_status === 'shortlisted');
  check('B6. success toast', (await page.evaluate(() => window.__toasts.slice(-1)[0])).type === 'success');

  console.log('C. Change → failure → rollback');
  await choose(page, 9, 'rejected');
  await page.evaluate(() => window.__pending({ ok: false, data: { detail: 'خطأ' } }));
  await page.waitForFunction(sel => !document.querySelector(sel + ' .co-dp-btn').disabled, picker(9));
  const rb = await pickerState(page, 9);
  check('C1. failure → previous value restored', rb.label === 'مرشح قوي' && rb.selected === 'shortlisted', rb);
  check('C2. data-job-links unchanged', (await linksOf(page)).find(l => l.job_id === 9).candidate_status === 'shortlisted');
  check('C3. error toast', (await page.evaluate(() => window.__toasts.slice(-1)[0])).type === 'error');
  await choose(page, 9, 'hired');
  await page.evaluate(() => window.__pending(Promise.reject(new Error('net'))));
  await page.waitForFunction(sel => !document.querySelector(sel + ' .co-dp-btn').disabled, picker(9));
  check('C4. network error → rollback + error toast',
        (await pickerState(page, 9)).label === 'مرشح قوي'
        && (await page.evaluate(() => window.__toasts.slice(-1)[0])).type === 'error');

  console.log('D. «غير مصنّف» + no-op');
  await choose(page, 9, '');
  const c4 = await page.evaluate(() => window.__calls.slice(-1)[0]);
  check('D1. «غير مصنّف» sends candidate_status null', c4.cs === null, c4);
  await page.evaluate(() => window.__pending({ ok: true, data: {} }));
  await page.waitForFunction(sel => !document.querySelector(sel + ' .co-dp-btn').disabled, picker(9));
  const nCalls = await page.evaluate(() => window.__calls.length);
  await choose(page, 9, '');
  check('D2. same value → no PATCH', (await page.evaluate(() => window.__calls.length)) === nCalls);

  console.log('E. tw:candidate-job-classification-updated → picker');
  await page.evaluate(() => document.dispatchEvent(new CustomEvent('tw:candidate-job-classification-updated', {
    detail: { candidateId: 42, jobId: 7, applicationStatus: 'hired', candidateStatus: 'hired', generalStatus: null } })));
  const ev = await pickerState(page, 7);
  check('E1. event updates the picker (label + palette)', ev.label === 'تم التوظيف' && /co-cand-status--hired/.test(ev.cls), ev);
  check('E2. event triggers no PATCH', (await page.evaluate(() => window.__calls.length)) === nCalls);
  check('E3. chips sections not duplicated by re-render',
        (await page.$$('.co-cand-saved-card[data-cid="42"] .co-cand-job-chip')).length === 2
        && (await page.$$('.co-cand-saved-card[data-cid="42"] .co-cand-job-status-section')).length === 1);

  console.log('F. Reverse direction forbidden');
  check('F1. picker never calls /jobs/applications (job_applications.status)',
        (await page.evaluate(() => window.__netWrites.length)) === 0);
  check('F2. no page errors', errors.length === 0, errors);

  console.log('G. Notifications badge cap (twNotifBadgeLabel)');
  const lbl = await page.evaluate(() => [5, 99, 100, 0].map(n => window.twNotifBadgeLabel(n)));
  check('G1. 5 → "5"', lbl[0] === '5', lbl);
  check('G2. 99 → "99"', lbl[1] === '99', lbl);
  check('G3. 100 → "99+"', lbl[2] === '99+', lbl);
  check('G4. 0 → "0"', lbl[3] === '0', lbl);

  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
