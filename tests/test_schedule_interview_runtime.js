/**
 * test_schedule_interview_runtime.js — PR 3.10 Schedule Interview System (frontend, focused).
 * Runs the REAL static/shared/tw-schedule.js in a Node vm context (stub DOM + TwAuthSync + twApi)
 * on top of the REAL Actions Registry block of tw_shared.js + window.TW_ACTIONS (tw_actions.py)
 * + the real strings (tw_strings.json) — PR 3.9b: tw-schedule.js has no inline visibility rule
 * any more, so without the registry there is no button (A0).
 *   A  twScheduleButton visibility — company viewer + emp other side only (not self / not co / guest)
 *   B  open appointment → «فتح الموعد» → room · draft keeps «تحديد موعد» · one batched request
 *   C  twScheduleMount replaces slots · old page-specific modal / application_id field are gone
 *
 * Run: node tests/test_schedule_interview_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');
const { execFileSync } = require('child_process');
const PY = (() => { for (const p of ['python3', 'python']) { try { execFileSync(p, ['-V']); return p; } catch (e) {} } })();
const ACTIONS_BLOCK = execFileSync(PY, ['-c', 'import tw_actions; print(tw_actions.page_block({}))'], { encoding: 'utf8' })
  .trim().replace(/^<script>|<\/script>$/g, '');
const SHARED = read('tw_shared.js');
const A_START = SHARED.indexOf('// ══ Actions Registry — twAction');
const REGISTRY = SHARED.slice(A_START, SHARED.indexOf('\n// ══', A_START + 10));
const STRINGS = JSON.parse(read('tw_strings.json')).ar;

// Minimal element stub — enough for tw-schedule.js button + mount paths
function makeEl(tag) {
  const attrs = {}, listeners = {};
  const el = {
    tagName: String(tag).toUpperCase(), className: '', children: [], parentNode: null,
    style: {},
    setAttribute: (k, v) => { attrs[k] = String(v); },
    getAttribute: k => (Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null),
    hasAttribute: k => Object.prototype.hasOwnProperty.call(attrs, k),
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
    appendChild: c => { c.parentNode = el; el.children.push(c); return c; },
    removeChild: c => { el.children.splice(el.children.indexOf(c), 1); c.parentNode = null; },
    replaceChild: (n, o) => { el.children[el.children.indexOf(o)] = n; n.parentNode = el; o.parentNode = null; },
    querySelectorAll: () => el.children.filter(c => c.hasAttribute && c.hasAttribute('data-tw-schedule-slot')),
    click: () => (listeners.click || []).forEach(fn => fn({ preventDefault() {}, stopPropagation() {} })),
  };
  // textContent like the DOM: own text once set, else the children's text (twAction → <span> label)
  let own = null;
  Object.defineProperty(el, 'textContent', {
    get: () => (own !== null ? own : el.children.map(c => c.textContent || '').join('')),
    set: v => { own = String(v); el.children.length = 0; },
  });
  return el;
}

function ctxFor(snapshot, openData, noRegistry) {
  const timers = [];
  const calls = [];
  const ctx = {
    console, Promise, encodeURIComponent, Object, Array, String, parseInt, isNaN, Intl, Date,
    setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
    TwAuthSync: { getSessionSnapshot: () => snapshot },
    twApi: url => { calls.push(url); return Promise.resolve({ ok: true, data: openData || {} }); },
    location: { href: '/u/U1' },
    document: {
      getElementById: () => null, createElement: makeEl,
      head: makeEl('head'), documentElement: makeEl('html'),
    },
    Number, JSON,
    twT: k => (Object.prototype.hasOwnProperty.call(STRINGS, k) ? STRINGS[k] : k),
    twLoginHref: next => '/login?next=' + encodeURIComponent(next),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  if (!noRegistry) {
    vm.runInContext(ACTIONS_BLOCK, ctx, { filename: 'TW_ACTIONS' });
    vm.runInContext(REGISTRY, ctx, { filename: 'tw_shared.js#actions' });
  }
  vm.runInContext(read('static/shared/tw-schedule.js'), ctx, { filename: 'tw-schedule.js' });
  const flush = async () => { while (timers.length) timers.shift()(); for (let i = 0; i < 5; i++) await null; };
  return { ctx, calls, flush };
}

const CO  = { isAuthenticated: true, userType: 'co',  userId: 8 };
const EMP = { isAuthenticated: true, userType: 'emp', userId: 7 };
const GUEST = { isAuthenticated: false, userType: null, userId: null };

(async function () {
  console.log('\nA — visibility');
  check('A0 no Actions Registry (tw_shared.js not loaded) → no button (fail-closed, no inline rule)',
    ctxFor(CO, null, true).ctx.twScheduleButton({ candidateId: 5 }) === null);
  check('A1 emp viewer → no button', ctxFor(EMP).ctx.twScheduleButton({ candidateId: 5 }) === null);
  check('A2 guest → no button', ctxFor(GUEST).ctx.twScheduleButton({ candidateId: 5 }) === null);
  check('A3 company on itself → no button', ctxFor(CO).ctx.twScheduleButton({ candidateId: 8 }) === null);
  check('A4 company on a co account → no button',
    ctxFor(CO).ctx.twScheduleButton({ candidateId: 5, candidateType: 'co' }) === null);
  const a5 = ctxFor(CO);
  const b5 = a5.ctx.twScheduleButton({ candidateId: 5, candidateType: 'emp', className: 'x-btn' });
  check('A5 company on emp → «تحديد موعد» button with the caller class',
    b5 && b5.textContent === 'تحديد موعد' && b5.className === 'x-btn');

  console.log('\nB — open appointment');
  const b = ctxFor(CO, { 5: { id: 9, status: 'pending_response', job_id: 3 }, 6: { id: 4, status: 'draft', job_id: 3 } });
  const open = b.ctx.twScheduleButton({ candidateId: 5, jobId: 3 });
  const draft = b.ctx.twScheduleButton({ candidateId: 6, jobId: 3 });
  await b.flush();
  check('B1 open appointment → «فتح الموعد»', open.textContent === 'فتح الموعد'
    && open.getAttribute('data-tw-schedule') === 'open');
  open.click();
  check('B2 click «فتح الموعد» → the appointment room', b.ctx.location.href === '/appointment-room?id=9',
    b.ctx.location.href);
  check('B3 draft keeps «تحديد موعد»', draft.textContent === 'تحديد موعد');
  check('B4 one batched request per job (ids + job_id)', b.calls.length === 1
    && /candidate_ids=5,6&job_id=3$/.test(b.calls[0]), JSON.stringify(b.calls));

  console.log('\nC — mount + old modal removed');
  const c = ctxFor(CO);
  const root = makeEl('div');
  const slot = makeEl('span');
  slot.setAttribute('data-tw-schedule-slot', '');
  slot.setAttribute('data-candidate-id', '5');
  slot.setAttribute('data-class', 'co-app-sched-btn co-app-act');
  root.appendChild(slot);
  c.ctx.twScheduleMount(root);
  check('C1 slot replaced by the shared button', root.children.length === 1
    && root.children[0].tagName === 'BUTTON' && root.children[0].className === 'co-app-sched-btn co-app-act');
  const cm = read('static/company/company.main.js');
  check('C2 company page: no page-specific appointment modal', !/_openApptModal|coApptModal|_submitApptForm/.test(cm)
    && !/coApptModal/.test(read('company-profile.html')));
  const ap = read('appointments.html');
  check('C3 appointments.html: no application_id field, + opens the shared dialog',
    !/fApplication|application_id/.test(ap) && /twScheduleInterview\(/.test(ap));
  check('C4 every placement loads tw-schedule.js after tw-overlay.js',
    ['appointments.html', 'company-profile.html', 'profile-showcase.html', 'messages.html'].every(f => {
      const s = read(f);
      const o = s.indexOf('tw-overlay.js'), t = s.indexOf('tw-schedule.js');
      return o > 0 && t > o;
    }));

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
