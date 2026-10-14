/**
 * test_schedule_interview_runtime.js — PR 3.10 Schedule Interview System (frontend, focused).
 * Runs the REAL static/shared/tw-schedule.js in a Node vm context (stub DOM + TwAuthSync + twApi)
 * on top of the REAL Actions Registry block of tw_shared.js + window.TW_ACTIONS (tw_actions.py)
 * + the real strings (tw_strings.json) — PR 3.9b: tw-schedule.js has no inline visibility rule
 * any more, so without the registry there is no button (A0).
 *   A  twScheduleButton visibility — company viewer + emp other side only (not self / not co / guest)
 *   B  open appointment → «فتح الموعد» → room · draft keeps «تحديد موعد» · one batched request
 *   C  twScheduleMount replaces slots · old page-specific modal / application_id field are gone
 *   D  draft dialog (PR 4.0): opens on the draft's mode + place · switching to أونلاين sends mode on /send
 *   E  reschedule mode (PR 4.12): appointment-room «اقتراح موعد جديد» = the same dialog → /reschedule
 *      with the picked LOCAL time as UTC ISO · type fixed · no create / send · past time refused
 *   F  PR 4.14 — no active job: «إرسال الدعوة» disabled + «انشر وظيفة» → twPostJobHref (real,
 *      tw_shared.js) · with jobs: enabled, no link · dialog text from twT (no fixed Arabic)
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
    style: {}, value: '', hidden: false,
    get options() { return el.children; },
    remove: i => { el.children.splice(i, 1); },
    setAttribute: (k, v) => { attrs[k] = String(v); },
    getAttribute: k => (Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null),
    hasAttribute: k => Object.prototype.hasOwnProperty.call(attrs, k),
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
    appendChild: c => { c.parentNode = el; el.children.push(c); return c; },
    removeChild: c => { el.children.splice(el.children.indexOf(c), 1); c.parentNode = null; },
    replaceChild: (n, o) => { el.children[el.children.indexOf(o)] = n; n.parentNode = el; o.parentNode = null; },
    querySelectorAll: () => el.children.filter(c => c.hasAttribute && c.hasAttribute('data-tw-schedule-slot')),
    click: () => (listeners.click || []).forEach(fn => fn({ preventDefault() {}, stopPropagation() {} })),
    find: pred => { if (pred(el)) return el; for (const c of el.children) { const f = c.find && c.find(pred); if (f) return f; } return null; },
  };
  // textContent like the DOM: own text once set, else the children's text (twAction → <span> label)
  let own = null;
  Object.defineProperty(el, 'textContent', {
    get: () => (own !== null ? own : el.children.map(c => c.textContent || '').join('')),
    set: v => { own = String(v); el.children.length = 0; },
  });
  return el;
}

function ctxFor(snapshot, openData, noRegistry, jobsData) {
  const timers = [];
  const calls = [], posts = [], modals = [];
  const ctx = {
    console, Promise, encodeURIComponent, Object, Array, String, parseInt, isNaN, Intl, Date,
    setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
    TwAuthSync: { getSessionSnapshot: () => snapshot },
    twApi: (url, opts) => {
      calls.push(url); posts.push({ url, body: opts && opts.body });
      if (/\/send$/.test(url)) return Promise.resolve({ ok: true, data: { id: 4 } });
      if (url === '/api/schedule/jobs') return Promise.resolve({ ok: true, data: jobsData || [] });
      return Promise.resolve({ ok: true, data: openData || {} });
    },
    twModal: cfg => {
      modals.push(cfg);
      cfg.disabledNow = cfg.actions.map(a => !!a.disabled);
      return { close() {}, setBusy() {}, setActionDisabled: (i, on) => { cfg.disabledNow[i] = !!on; } };
    },
    twApiMessage: (r, f) => f,
    twSafeLinkUrl: u => (/^https?:\/\/\S+$/.test(u) ? u : ''),
    location: { href: '/u/U1' },
    document: {
      getElementById: () => null, createElement: makeEl,
      head: makeEl('head'), documentElement: makeEl('html'),
    },
    Number, JSON,
    twT: k => (Object.prototype.hasOwnProperty.call(STRINGS, k) ? STRINGS[k] : k),
    twLoginHref: next => '/login?next=' + encodeURIComponent(next),
  };
  // the real «انشر وظيفة» href builder from tw_shared.js (company tw_id from the session cache)
  const ph = SHARED.slice(SHARED.indexOf('function twPostJobHref('), SHARED.indexOf('window.twPostJobHref'));
  ctx.getTwUser = () => ({ tw_id: 'C8', user_type: 'co' });
  vm.createContext(ctx);
  vm.runInContext(ph, ctx, { filename: 'tw_shared.js#twPostJobHref' });
  ctx.window = ctx;
  if (!noRegistry) {
    vm.runInContext(ACTIONS_BLOCK, ctx, { filename: 'TW_ACTIONS' });
    vm.runInContext(REGISTRY, ctx, { filename: 'tw_shared.js#actions' });
  }
  vm.runInContext(read('static/shared/tw-schedule.js'), ctx, { filename: 'tw-schedule.js' });
  const flush = async () => { while (timers.length) timers.shift()(); for (let i = 0; i < 5; i++) await null; };
  return { ctx, calls, posts, modals, flush };
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

  console.log('\nD — draft dialog keeps the draft mode (PR 4.0)');
  const d = ctxFor(CO, { 6: { id: 4, status: 'draft', job_id: 3, job_title: 'مطوّر',
    mode: 'onsite', online_url: null, location_text: 'مكتب عمّان' } });
  const dBtn = d.ctx.twScheduleButton({ candidateId: 6, candidateName: 'سارة', jobId: 3 });
  await d.flush();
  dBtn.click();
  const dlg = d.modals[0];
  check('D0 draft click opens the shared dialog', !!dlg && !!dlg.content);
  const form = dlg.content;
  const seg = form.find(n => n.className === 'tw-sch-seg');
  const [bOn, bOff] = seg.children;
  const urlIn = form.find(n => n.type === 'url');
  const locIn = form.find(n => n.tagName === 'INPUT' && n.maxLength === 500);
  check('D1 draft حضوري → dialog opens on حضوري (not the أونلاين default)',
    bOff.getAttribute('aria-pressed') === 'true' && bOn.getAttribute('aria-pressed') === 'false'
    && urlIn.parentNode.hidden === true && locIn.parentNode.hidden === false);
  check('D2 the draft place is loaded', locIn.value === 'مكتب عمّان', locIn.value);
  // pick a date ~6 months ahead + switch to أونلاين with a link, then send
  const pick = (cls, v) => { form.find(n => (n.className || '').indexOf(cls) !== -1).value = String(v); };
  pick('tw-sch-yr', new Date().getFullYear() + 1); pick('tw-sch-mon', 6); pick('tw-sch-day', 15);
  pick('tw-sch-hr', 10); pick('tw-sch-min', 0); pick('tw-sch-ap', 'am');
  bOn.click();
  urlIn.value = 'https://meet.example.com/abc';
  await dlg.actions[1].onClick();
  const send = d.posts.find(p => /\/api\/appointments\/4\/send$/.test(p.url));
  check('D3 no new appointment is created for a draft', !d.posts.some(p => p.url === '/api/appointments'));
  check('D4 /send carries the new mode + link (no place)', !!send && send.body.mode === 'online'
    && send.body.online_url === 'https://meet.example.com/abc' && send.body.location_text === null,
    JSON.stringify(send && send.body));

  console.log('\nE — reschedule mode (PR 4.12)');
  const e = ctxFor(CO);
  const RS = { id: 12, status: 'reschedule_requested', job_id: 3, job_title: 'مطوّر', mode: 'online',
    online_url: 'https://meet.example.com/old', location_text: null };
  e.ctx.twScheduleInterview({ candidateId: 6, candidateName: 'سارة', reschedule: RS });
  const eDlg = e.modals[0];
  check('E0 reschedule opens the shared dialog with its own title + submit text',
    !!eDlg && eDlg.title === STRINGS['appt.room.propose'] && eDlg.actions[1].text === STRINGS['appt.room.reschedule_submit']);
  const eForm = eDlg.content;
  const eSeg = eForm.find(n => n.className === 'tw-sch-seg');
  const eUrl = eForm.find(n => n.type === 'url');
  check('E1 type is fixed (no أونلاين / حضوري switch) and the current link is loaded',
    eSeg.parentNode.hidden === true && eUrl.value === 'https://meet.example.com/old');
  const ePick = (cls, v) => { eForm.find(n => (n.className || '').indexOf(cls) !== -1).value = String(v); };
  // a past local time is refused before any request
  ePick('tw-sch-yr', new Date().getFullYear()); ePick('tw-sch-mon', 1); ePick('tw-sch-day', 1);
  ePick('tw-sch-hr', 12); ePick('tw-sch-min', 0); ePick('tw-sch-ap', 'am');
  const past = new Date(new Date().getFullYear(), 0, 1, 0, 0, 0, 0);
  if (past.getTime() < Date.now()) {
    const r0 = await eDlg.actions[1].onClick();
    check('E2 a past time (local) is refused — no request', r0 === false && e.posts.length === 0);
  }
  ePick('tw-sch-yr', new Date().getFullYear() + 1); ePick('tw-sch-mon', 6); ePick('tw-sch-day', 15);
  ePick('tw-sch-hr', 3); ePick('tw-sch-min', 30); ePick('tw-sch-ap', 'pm');
  const r1 = await eDlg.actions[1].onClick();
  const rs = e.posts.find(p => p.url === '/api/appointments/12/reschedule');
  const want = new Date(new Date().getFullYear() + 1, 5, 15, 15, 30, 0, 0).toISOString();
  check('E3 submit → POST /reschedule with the picked local time as UTC ISO + deadline + link',
    r1 === true && !!rs && rs.body.new_scheduled_at === want && rs.body.deadline_hours === 48
    && rs.body.online_url === 'https://meet.example.com/old', JSON.stringify(rs && rs.body));
  check('E4 no create / send for a reschedule', !e.posts.some(p => p.url === '/api/appointments' || /\/send$/.test(p.url)));
  e.ctx.showToast = () => {};
  eDlg.onClose();
  check('E5 success → back to the room', e.ctx.location.href === '/appointment-room?id=12');

  console.log('\nF — no active job (PR 4.14)');
  const f = ctxFor(CO, null, false, []);
  f.ctx.twScheduleInterview({ candidateId: 6, candidateName: 'سارة' });
  await f.flush();
  const fDlg = f.modals[0];
  const post = fDlg.content.find(n => n.tagName === 'A');
  check('F1 no active job → «إرسال الدعوة» disabled', fDlg.disabledNow[1] === true && fDlg.disabledNow[0] === false,
    JSON.stringify(fDlg.disabledNow));
  check('F2 «انشر وظيفة» link → the company page on the post-job form',
    !!post && post.textContent === STRINGS['jobs.post'] && post.href === '/u/C8?post_job=1', post && post.href);
  const g = ctxFor(CO, null, false, [{ id: 3, title: 'مطوّر' }]);
  g.ctx.twScheduleInterview({ candidateId: 6, candidateName: 'سارة' });
  await g.flush();
  check('F3 active jobs → send enabled, no «انشر وظيفة» link',
    g.modals[0].disabledNow[1] === false && !g.modals[0].content.find(n => n.tagName === 'A'));
  const allText = [];
  (function walk(n) { if (n.textContent && !n.children.length) allText.push(n.textContent);
    if (n.placeholder) allText.push(n.placeholder); n.children.forEach(walk); })(g.modals[0].content);
  const vals = new Set(Object.values(STRINGS));
  const fixed = allText.filter(t => /[\u0600-\u06FF]/.test(t) && !vals.has(t) && t !== 'سارة' && t !== 'مطوّر');
  check('F4 every dialog text comes from tw_strings.json (twT)', allText.length > 20 && !fixed.length, fixed.join(' | '));
  check('F5 title + send text from twT', g.modals[0].title === STRINGS['appt.sch.title']
    && g.modals[0].actions[1].text === STRINGS['appt.sch.send']);

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
