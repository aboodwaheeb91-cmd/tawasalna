/**
 * test_withdraw_ui_82b_runtime.js — task 8.2b: withdraw / re-apply UI (backend = task 8.2a).
 * Real page code in Node vm contexts, fake DOM + twApi:
 *   A  static/job/job-detail.js — «سحب الطلب» only for in_review · withdraw → «إعادة التقديم» ·
 *      re-apply only for withdrawn + open job (same apply modal / POST) · 409 / 429 → server text
 *   B  profile-v2.apps.js («طلباتي») — withdraw slot only on in_review cards · withdraw → «منسحب» · 409 → server text
 *   C  company.main.js (@vm-extract co-applicants-render) — withdrawn not in the active list,
 *      collapsed «منسحبون» section, badge + profile link only (no classify / bank / notes / schedule)
 *   D  registry + strings — withdraw_application = emp only + danger twConfirm · every new key exists
 *
 * Run: node tests/test_withdraw_ui_82b_runtime.js
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
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };
const STRINGS = JSON.parse(read('tw_strings.json')).ar;
const twT = (k, v) => { const s = STRINGS[k]; if (typeof s !== 'string') return k;
  return v ? s.replace(/\{(\w+)\}/g, (m, n) => (n in v ? String(v[n]) : m)) : s; };
// twApiMessage stand-in: the server's {ok:false, error:{message}} text, else the fallback
const twApiMessage = (r, f) => (r && r.error && r.error.message) || f;
const err = (status, code, message) => ({ ok: false, status, error: { message }, data: { ok: false, error: { code, message } } });

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase(); this.children = []; this.attrs = {}; this.style = {
      setProperty: (k, v) => { this.style[k] = v; }, removeProperty: k => { delete this.style[k]; } };
    this._text = ''; this.listeners = {}; this.hidden = false; this.disabled = false; this._cls = new Set();
    const self = this;
    this.classList = { add: (...c) => c.forEach(x => self._cls.add(x)), remove: (...c) => c.forEach(x => self._cls.delete(x)),
                       contains: c => self._cls.has(c) };
  }
  set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get className() { return [...this._cls].join(' '); }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'href') this.href = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) { this.children.push(c); c.parentNode = this; return c; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  querySelector() { return null; }
  closest() { return this._row || null; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent || '').join(''); }
  set innerHTML(v) { this._html = v; }
}

// ── A: job-detail.js ────────────────────────────────────────────────────────
async function jobPage(opts) {
  const ids = {};
  const byId = id => (ids[id] = ids[id] || new El(id === 'jdCoName' || id === 'jdCoCardName' ? 'a' : 'div'));
  ['jdSiCo', 'jdSiLoc', 'jdSiType', 'jdSiMode', 'jdSiExp', 'jdSiSal', 'jdSiViews', 'jdSiDate'].forEach(id => {
    byId(id)._row = new El('div');
  });
  const slots = {};
  ['card', 'sticky'].forEach(k => { const s = new El('div'); s.attrs['data-jd-apply-slot'] = k; slots[k] = s; });
  const doc = {
    readyState: 'complete', body: new El('body'), title: '',
    getElementById: byId, createElement: t => new El(t), createTextNode: t => ({ textContent: String(t) }),
    querySelectorAll: sel => sel === '[data-jd-apply-slot]' ? [slots.card, slots.sticky] : [],
    addEventListener: noop,
  };
  const JOB = { id: 5, title: 'مطوّر', company_id: 77, company_tw_id: 'C962xyz', company_name: 'شركة',
                status: opts.jobStatus || 'active', created_at: '2026-10-08T09:00:00Z', skills: [], job_type: 'full_time' };
  const api = Object.assign({
    '/jobs/5': { ok: true, status: 200, data: { job: JOB } },
    '/my/applications': { ok: true, status: 200, data: { applications: opts.apps || [] } },
    '/jobs': { ok: true, status: 200, data: { jobs: [] } },
  }, opts.api || {});
  const calls = [], modals = [], toasts = [];
  const ctx = {
    document: doc, console: { log: noop, warn: noop, error: noop }, URLSearchParams, Set, Date, Math, JSON, Promise,
    location: { search: '?id=5', pathname: '/job-detail', href: '/job-detail?id=5' }, navigator: {},
    TwAuthSync: { getSessionSnapshot: () => ({ isAuthenticated: true, userType: 'emp', userId: 9 }) },
    getTwUser: () => ({ id: 9, tw_id: 'U1' }),
    twT, twApiMessage,
    twApi: (p, o) => { calls.push([p, o || {}]); return Promise.resolve(api[p] || { ok: false, status: 404 }); },
    // the registry decides visibility (D checks emp-only); here: one button per call, ctx kept
    twAction: (id, c) => { const b = new El('button'); b.actionId = id; b.ctx = c; b.disabled = !!c.disabled; return b; },
    twModal: o => { modals.push(o); return { close: noop }; },
    twReportDialog: noop, twIconEl: () => new El('svg'), twIcon: { hydrate: noop }, twAvatarHtml: () => '',
    twFormatDate: v => 'G:' + v, twLoginHref: p => '/login?next=' + p, twAccountHref: () => '/u/U1',
    twNavBack: noop, twHomeHref: () => '/home', showToast: (m, t) => toasts.push([m, t]),
    fetch: () => { throw new Error('raw fetch called'); },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(read('static/job/job-detail.js'), ctx, { filename: 'job-detail.js' });
  await flush();
  const ids2 = k => slots[k].children.map(b => b.actionId);
  const btn = (k, id) => slots[k].children.find(b => b.actionId === id);
  return { slots, ids: ids2, btn, calls, modals, toasts, api };
}

(async function main() {
  console.log('\nA — job-detail.js: withdraw / re-apply');
  {
    const p = await jobPage({ apps: [{ id: 31, job_id: 5, status: 'in_review' }],
      api: { '/jobs/applications/31/withdraw': { ok: true, status: 200, data: { ok: true, data: { status: 'withdrawn' } } } } });
    check('A1 in_review → «تم التقديم» disabled + «سحب الطلب» in the card slot only (not the sticky bar)',
      JSON.stringify(p.ids('card')) === '["apply_job","withdraw_application"]'
      && JSON.stringify(p.ids('sticky')) === '["apply_job"]'
      && p.btn('card', 'apply_job').disabled === true && p.btn('card', 'apply_job').ctx.labelKey === 'job.applied',
      { card: p.ids('card'), sticky: p.ids('sticky') });
    await p.btn('card', 'withdraw_application').ctx.onClick();
    const post = p.calls.find(c => c[0] === '/jobs/applications/31/withdraw');
    check('A2 withdraw → twApi POST /jobs/applications/31/withdraw', post && post[1].method === 'POST');
    check('A3 after withdrawing → «إعادة التقديم» enabled in both slots, no withdraw button',
      JSON.stringify(p.ids('card')) === '["reapply_job"]' && JSON.stringify(p.ids('sticky')) === '["reapply_job"]'
      && !p.btn('card', 'reapply_job').disabled, { card: p.ids('card') });
    check('A4 success toast = apps.withdraw.ok', p.toasts.some(t => t[0] === STRINGS['apps.withdraw.ok'] && t[1] === 'success'));
  }
  {
    const MSG = STRINGS['jobs.app_state.application_final'];
    const p = await jobPage({ apps: [{ id: 31, job_id: 5, status: 'in_review' }],
      api: { '/jobs/applications/31/withdraw': err(409, 'application_final', MSG) } });
    const ok = await p.btn('card', 'withdraw_application').ctx.onClick();
    check('A5 409 application_final → the server text in an error toast, state unchanged',
      ok === false && p.toasts.some(t => t[0] === MSG && t[1] === 'error')
      && JSON.stringify(p.ids('card')) === '["apply_job","withdraw_application"]', p.toasts);
  }
  {
    const p = await jobPage({ apps: [{ id: 31, job_id: 5, status: 'withdrawn' }],
      api: { '/jobs/5/apply': { ok: true, status: 200, data: { status: 'pending', id: 31, reapplied: true } } } });
    check('A6 withdrawn + open job → «إعادة التقديم» (enabled), no withdraw / no «تقديم الآن»',
      JSON.stringify(p.ids('card')) === '["reapply_job"]' && !p.btn('card', 'reapply_job').disabled, p.ids('card'));
    p.btn('card', 'reapply_job').ctx.onClick();
    check('A7 re-apply → the same apply modal (twModal)', p.modals.length === 1);
    const send = p.modals[0].actions.find(a => typeof a.onClick === 'function');
    const ok = await send.onClick();
    check('A8 re-apply → POST /jobs/5/apply (the current apply path)',
      ok === true && p.calls.some(c => c[0] === '/jobs/5/apply' && c[1].method === 'POST'));
    check('A9 back to «قيد المراجعة»: «تم التقديم» disabled + «سحب الطلب» again + toast job.reapply.ok',
      JSON.stringify(p.ids('card')) === '["apply_job","withdraw_application"]'
      && p.btn('card', 'apply_job').disabled === true
      && p.toasts.some(t => t[0] === STRINGS['job.reapply.ok']), { card: p.ids('card'), toasts: p.toasts });
  }
  {
    const MSG = 'وصلت للحد الأقصى لإعادة التقديم على هذه الوظيفة (3 مرات بالأسبوع)، حاول لاحقاً';
    const p = await jobPage({ apps: [{ id: 31, job_id: 5, status: 'withdrawn' }],
      api: { '/jobs/5/apply': err(429, 'reapply_limit', MSG) } });
    p.btn('card', 'reapply_job').ctx.onClick();
    const ok = await p.modals[0].actions.find(a => typeof a.onClick === 'function').onClick();
    check('A10 429 reapply_limit → server text, modal stays open, still «إعادة التقديم»',
      ok === false && p.toasts.some(t => t[0] === MSG && t[1] === 'error')
      && JSON.stringify(p.ids('card')) === '["reapply_job"]', p.toasts);
  }
  {
    const p = await jobPage({ jobStatus: 'paused', apps: [{ id: 31, job_id: 5, status: 'withdrawn' }] });
    check('A11 withdrawn + paused job → no re-apply (disabled «موقوفة»)',
      JSON.stringify(p.ids('card')) === '["apply_job"]' && p.btn('card', 'apply_job').disabled === true, p.ids('card'));
  }
  for (const st of ['hired', 'rejected']) {
    const p = await jobPage({ apps: [{ id: 31, job_id: 5, status: st }] });
    check('A12 ' + st + ' → no withdraw / no re-apply', JSON.stringify(p.ids('card')) === '["apply_job"]', p.ids('card'));
  }
  {
    const p = await jobPage({ apps: [] });
    check('A13 no application → «تقديم الآن» only', JSON.stringify(p.ids('card')) === '["apply_job"]'
      && p.btn('card', 'apply_job').ctx.labelKey === 'job.apply_now');
  }

  console.log('\nB — profile-v2.apps.js («طلباتي»)');
  {
    const APPS = [
      { id: 11, job_id: 1, status: 'in_review', title: 'أ' },
      { id: 12, job_id: 2, status: 'withdrawn', title: 'ب' },
      { id: 13, job_id: 3, status: 'hired', title: 'ج' },
    ];
    // fake pane: slots / cards parsed from the rendered HTML string
    const badges = {}, slots = [];
    const pane = {
      set innerHTML(v) {
        this._html = v; slots.length = 0;
        (v.match(/data-sc-withdraw-slot data-app-id="(\d+)"/g) || []).forEach(m => {
          const id = m.match(/(\d+)/)[1];
          const badge = badges[id] = { className: '', textContent: '' };
          const card = { querySelector: () => badge };
          const s = new El('span'); s.attrs['data-app-id'] = id; s.closest = () => card;
          s.removed = false; s.remove = function () { this.removed = true; };
          slots.push(s);
        });
      },
      get innerHTML() { return this._html; },
      querySelectorAll: sel => (sel === '[data-sc-withdraw-slot]' ? slots : []),
    };
    const MSG = STRINGS['jobs.app_state.job_not_active'];
    const api = {
      '/my/applications': { ok: true, status: 200, raw: { applications: APPS } },
      '/jobs/applications/11/withdraw': { ok: true, status: 200, data: { ok: true } },
    };
    const calls = [], toasts = [], actions = [];
    const ctx = {
      console, document: { getElementById: id => (id === 'scAppsPane' ? pane : null) },
      scTab: noop, _scViewerType: 'owner', twT, twApiMessage,
      twEscHtml: v => String(v == null ? '' : v), twFormatDate: v => String(v),
      twApi: (p, o) => { calls.push([p, o || {}]); return Promise.resolve(api[p] || { ok: false, status: 404 }); },
      twAction: (id, c) => { actions.push([id, c]); const b = new El('button'); b.ctx = c; return b; },
      showToast: (m, t) => toasts.push([m, t]),
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(read('profile-v2.apps.js'), ctx, { filename: 'profile-v2.apps.js' });
    ctx.scTab('apps');
    await flush();
    const html = pane.innerHTML || '';
    check('B1 withdraw slot only on the in_review card (11) — not withdrawn (12) / hired (13)',
      slots.length === 1 && slots[0].getAttribute('data-app-id') === '11', slots.map(s => s.attrs));
    check('B2 withdrawn card → «منسحب» badge (apps.status.withdrawn)',
      html.includes('sc-app-status--withdrawn') && html.includes(STRINGS['apps.status.withdrawn']));
    check('B3 the button = twAction(\'withdraw_application\') (registry twConfirm), mounted in the slot',
      actions.length === 1 && actions[0][0] === 'withdraw_application' && slots[0].children.length === 1);
    actions[0][1].onClick(actions[0][1], slots[0].children[0]);
    await flush();
    check('B4 confirmed → POST /jobs/applications/11/withdraw → badge «منسحب», button gone',
      calls.some(c => c[0] === '/jobs/applications/11/withdraw' && c[1].method === 'POST')
      && badges['11'].textContent === STRINGS['apps.status.withdrawn']
      && /sc-app-status--withdrawn/.test(badges['11'].className) && slots[0].removed === true, badges['11']);

    api['/jobs/applications/11/withdraw'] = err(409, 'job_not_active', MSG);
    ctx.scTab('apps');
    await flush();
    const b = slots[0].children[0];
    actions[actions.length - 1][1].onClick(null, b);
    await flush();
    check('B5 409 → the server text in an error toast, button enabled again',
      toasts.some(t => t[0] === MSG && t[1] === 'error') && b.disabled === false && slots[0].removed === false, toasts);
  }

  console.log('\nC — company applicants modal (company.main.js co-applicants-render)');
  {
    const MAIN = read('static/company/company.main.js');
    const b = '// @vm-extract-begin: co-applicants-render', e = '// @vm-extract-end: co-applicants-render';
    const code = MAIN.slice(MAIN.indexOf(b), MAIN.indexOf(e));
    const list = { innerHTML: '' };
    const ctx = {
      document: { getElementById: id => (id === 'coAppList' ? list : null) },
      twT, twEscHtml: v => String(v == null ? '' : v), twFormatDate: v => String(v || ''), twFormatNumber: n => String(n),
      twAvatarHtml: () => '<i class="av"></i>', _schedSlotHTML: () => '<span data-tw-schedule-slot></span>',
      _wireApplicantCards: noop, _APP_STATUS_LABEL: { withdrawn: STRINGS['company.stage.withdrawn'], pending: 'p', interview: 'i' },
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(code, ctx, { filename: 'co-applicants-render' });
    const A = (id, status) => ({ id, user_id: id + 100, status, full_name: 'N' + id, tw_id: 'U' + id, applied_at: '2026-10-01' });
    ctx._renderApplicants([A(1, 'pending'), A(2, 'withdrawn'), A(3, 'interview')]);
    const html = list.innerHTML;
    const at = html.indexOf('<details class="co-app-withdrawn"');
    const active = at === -1 ? html : html.slice(0, at), section = at === -1 ? '' : html.slice(at);
    check('C1 withdrawn not in the active list', active.includes('data-app-id="1"') && active.includes('data-app-id="3"')
      && !active.includes('data-app-id="2"'));
    check('C2 withdrawn in a collapsed «منسحبون (1)» section (<details> without open)',
      at !== -1 && !/<details[^>]*\bopen\b/.test(section) && section.includes('data-app-id="2"')
      && section.includes(twT('company.app.withdrawn_section', { count: '1' })));
    check('C3 withdrawn card: «منسحب» badge + profile link, no classify / bank / notes / schedule',
      section.includes('co-app-status--withdrawn') && section.includes(STRINGS['company.stage.withdrawn'])
      && section.includes('href="/u/U2"')
      && !/co-classify-btn|co-talentbank-btn|co-notes-btn|data-tw-schedule-slot/.test(section));
    ctx._renderApplicants([A(4, 'withdrawn')]);
    check('C4 only withdrawn → «لا يوجد متقدمون» + the section', list.innerHTML.includes(STRINGS['company.app.empty'])
      && list.innerHTML.includes('data-app-id="4"'));
    ctx._renderApplicants([A(5, 'pending')]);
    check('C5 no withdrawn → no section', !list.innerHTML.includes('co-app-withdrawn'));
    ctx._renderApplicants([Object.assign(A(6, 'pending'), { is_saved: true, other_job_titles: ['وظيفة أخرى'] })]);
    const h6 = list.innerHTML, sc = h6.indexOf('co-app-saved-ctx');
    check('C6 saved-elsewhere line rendered between card head and card foot (was 185-12 in test_post_comments.py)',
      sc > h6.indexOf('co-app-card-head') && sc < h6.indexOf('co-app-card-foot') && h6.includes('وظيفة أخرى'));
  }

  console.log('\nD — registry + strings');
  {
    const REG = JSON.parse(read('tw_actions.json')).actions;
    const w = REG.withdraw_application, r = REG.reapply_job;
    check('D1 withdraw_application: personal account only, twConfirm danger (title / message / confirm keys exist)',
      w && JSON.stringify(w.visibleTo) === '["emp"]' && w.auth === true && w.confirm && w.confirm.danger === true
      && ['titleKey', 'messageKey', 'confirmKey'].every(k => typeof STRINGS[w.confirm[k]] === 'string'));
    check('D2 reapply_job: personal account only', r && JSON.stringify(r.visibleTo) === '["emp"]' && r.auth === true);
    const keys = ['action.withdraw_application', 'action.reapply_job', 'apps.status.withdrawn', 'apps.withdraw.ok',
                  'apps.withdraw.err', 'job.reapply.ok', 'company.stage.withdrawn', 'company.app.withdrawn_section',
                  'appt.cause.applicant_withdrew'];
    const missing = keys.filter(k => typeof STRINGS[k] !== 'string');
    check('D3 every new twT key exists', !missing.length, missing);
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}()).catch(e => { console.error(e); process.exit(1); });
