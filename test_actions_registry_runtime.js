/**
 * test_actions_registry_runtime.js — PR 3.7 Actions Registry (BUTTONS.md BTN-19 · SYSTEMS_INDEX §60).
 * Real code: the twAction block of tw_shared.js in a Node vm, fed by the REAL page block that
 * tw_actions.py builds (registry + admin overrides); override validation via tw_actions.py.
 *   A  visibility — an action never renders for a viewer outside visibleTo / targets
 *   B  guest + auth action → login with a way back (twLoginHref(path + query))
 *   C  admin override — enabled:false hides it · visibleTo replaced · unknown id / field refused
 *   D  danger action asks twConfirm first · verified condition → disabled
 *   E  reference consumers — appointments.html + tw-schedule.js go through the registry
 *
 * Run: node test_actions_registry_runtime.js
 */
'use strict';
const fs = require('fs');
const vm = require('vm');
const { execFileSync } = require('child_process');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');

const PY = (() => { for (const p of ['python3', 'python']) { try { execFileSync(p, ['-V']); return p; } catch (e) {} } })();
const py = code => JSON.parse(execFileSync(PY, ['-c', 'import json, tw_actions\n' + code], { encoding: 'utf8' }));
const pageBlock = ov => py('print(json.dumps(tw_actions.page_block(json.loads(' + JSON.stringify(JSON.stringify(ov)) + '))))');

// the Actions block of tw_shared.js only (between its banner and the next banner)
const SRC = read('tw_shared.js');
const START = SRC.indexOf('// ══ Actions Registry — twAction');
const BLOCK = SRC.slice(START, SRC.indexOf('\n// ══', START + 10));

function makeEl(tag) {
  const attrs = {}, listeners = {};
  const el = {
    tagName: String(tag).toUpperCase(), className: '', textContent: '', children: [], disabled: false,
    setAttribute: (k, v) => { attrs[k] = String(v); },
    getAttribute: k => (k in attrs ? attrs[k] : null),
    appendChild: c => { el.children.push(c); return c; },
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
    click: () => (listeners.click || []).forEach(fn => fn({ preventDefault() {} })),
  };
  return el;
}

function ctxFor(snapshot, overrides, extra) {
  const ctx = Object.assign({
    console, Object, Number, String, JSON,
    document: { createElement: makeEl },
    location: { pathname: '/u/C123', search: '?tab=jobs', href: '/u/C123?tab=jobs' },
    TwAuthSync: { getSessionSnapshot: () => snapshot },
    twT: k => 'T:' + k,
    twLoginHref: next => '/login?next=' + encodeURIComponent(next),
    twIconEl: n => Object.assign(makeEl('svg'), { icon: n }),
  }, extra || {});
  ctx.window = ctx;
  vm.createContext(ctx);
  const blk = pageBlock(overrides || {});
  vm.runInContext(blk.replace(/^<script>|<\/script>$/g, ''), ctx);
  vm.runInContext(BLOCK, ctx, { filename: 'tw_shared.js#actions' });
  return ctx;
}

const GUEST = { isAuthenticated: false };
const EMP = { isAuthenticated: true, userType: 'emp', userId: 7 };
const CO  = { isAuthenticated: true, userType: 'co',  userId: 8 };
const EDU = { isAuthenticated: true, userType: 'edu', userId: 9 };

console.log('\nA — visibility');
check('A1 schedule: company on an emp → button', !!ctxFor(CO).twAction('schedule', { ownerId: 5, targetType: 'emp' }));
check('A2 schedule: emp viewer → nothing', ctxFor(EMP).twAction('schedule', { ownerId: 5, targetType: 'emp' }) === null);
check('A3 schedule: guest → nothing (not in visibleTo)', ctxFor(GUEST).twAction('schedule', { ownerId: 5, targetType: 'emp' }) === null);
check('A4 schedule: company on itself (owner) → nothing', ctxFor(CO).twAction('schedule', { ownerId: 8, targetType: 'emp' }) === null);
check('A5 schedule: company on a company → nothing (targets)', ctxFor(CO).twAction('schedule', { ownerId: 5, targetType: 'co' }) === null);
check('A6 edit_profile: owner only', !!ctxFor(EMP).twAction('edit_profile', { ownerId: 7 })
  && ctxFor(EMP).twAction('edit_profile', { ownerId: 99 }) === null && ctxFor(GUEST).twAction('edit_profile', { ownerId: 7 }) === null);
check('A7 page VM signal: mode public-user → registered (no owner buttons)',
  ctxFor(EMP).twAction('edit_profile', { mode: 'public-user', ownerId: 7 }) === null);
const b = ctxFor(CO).twAction('schedule', { ownerId: 5, targetType: 'emp' });
check('A8 type → shared class · icon + label from the registry',
  b.className === 'tw-act tw-act-primary' && b.children[0].icon === 'calendar'
  && b.children[1].textContent === 'T:action.schedule' && b.getAttribute('data-tw-action') === 'schedule');
check('A9 unknown id → nothing', ctxFor(CO).twAction('nope', {}) === null);

console.log('\nB — guest → login');
const g = ctxFor(GUEST);
let ran = false;
const fb = g.twAction('follow', { ownerId: 3, targetType: 'co', onClick: () => { ran = true; } });
check('B1 guest sees «متابعة» (state login)', !!fb && g.twActionState('follow', { ownerId: 3, targetType: 'co' }) === 'login');
fb.click();
check('B2 click → twLoginHref(path + query), handler not run',
  g.location.href === '/login?next=' + encodeURIComponent('/u/C123?tab=jobs') && !ran, g.location.href);
const e = ctxFor(EMP); let ranE = false;
e.twAction('follow', { ownerId: 3, targetType: 'co', onClick: () => { ranE = true; } }).click();
check('B3 signed-in emp → handler runs', ranE);

console.log('\nC — admin override');
check('C1 enabled:false → hidden for everyone',
  ctxFor(CO, { schedule: { enabled: false } }).twAction('schedule', { ownerId: 5, targetType: 'emp' }) === null);
check('C2 visibleTo replaced → new audience sees it, old one does not',
  !!ctxFor(EDU, { message: { visibleTo: ['edu'] } }).twAction('message', {})
  && ctxFor(EMP, { message: { visibleTo: ['edu'] } }).twAction('message', {}) === null);
const err = code => py('try:\n  tw_actions.validate_overrides(' + code + ')\n  print(json.dumps("ok"))\n'
  + 'except tw_actions.ActionsError as e:\n  print(json.dumps(e.code))');
check('C3 unknown action id refused', err('{"hack": {"enabled": False}}') === 'unknown_action');
check('C4 unknown field refused', err('{"follow": {"labelKey": "x"}}') === 'unknown_field');
check('C5 unknown audience refused', err('{"follow": {"visibleTo": ["admin"]}}') === 'invalid_value');
check('C6 non-bool enabled refused', err('{"follow": {"enabled": "no"}}') === 'invalid_value');
check('C7 valid override accepted', err('{"follow": {"enabled": False, "visibleTo": ["emp"]}}') === 'ok');
check('C8 page block is script-safe', !/<\/script>.*<\/script>/.test(pageBlock({})) && pageBlock({}).startsWith('<script>window.TW_ACTIONS='));
const SRV = read('server.py');
const getA = SRV.split('@app.get("/admin/actions")')[1].split('\n@app.')[0];
const putA = SRV.split('@app.put("/admin/actions")')[1].split('\n@app.')[0];
check('C9 GET/PUT /admin/actions admin-only + validated + saved + live',
  /check_admin\(request\)/.test(getA) && /check_admin\(request\)/.test(putA)
  && /tw_actions\.validate_overrides\(/.test(putA) && /set_site_setting\(tw_actions\.SETTING_KEY/.test(putA)
  && /_actions_set_overrides\(clean\)/.test(putA));
check('C10 overrides loaded at startup', /await asyncio\.to_thread\(_actions_load_overrides\)/.test(SRV));

console.log('\nD — danger + conditions');
let asked = null, ranD = false;
const d = ctxFor(CO, {}, { twConfirm: o => { asked = o; return Promise.resolve(false); } });
d.twAction('close_room', { onClick: () => { ranD = true; } }).click();
(async () => {
  await null; await null;
  check('D1 danger action asks twConfirm (danger:true) first; «إلغاء» → not run',
    asked && asked.danger === true && asked.title === 'T:action.close_room_title' && !ranD);
  const n = ctxFor(CO); let ranN = false;
  n.twAction('close_room', { onClick: () => { ranN = true; } }).click();
  check('D2 no tw-overlay.js → fail closed (not run)', !ranN);
  const v = ctxFor(EMP);
  v.TW_ACTIONS.actions.apply_job.enabledWhen = ['verified'];
  check('D3 enabledWhen verified → disabled until ctx.verified',
    v.twActionState('apply_job', {}) === 'disabled' && v.twActionState('apply_job', { verified: true }) === 'enabled');

  console.log('\nE — reference consumers');
  const appt = read('appointments.html');
  check('E1 appointments.html: FAB + room link via twAction, no IS_CO gate / page FAB markup',
    /twAction\('schedule_new'/.test(appt) && /twAction\('open_room'/.test(appt)
    && !/id="fabNew"/.test(appt) && !/IS_CO\)\s*\{\s*fabNew/.test(appt));
  const sch = read('static/shared/tw-schedule.js');
  check('E2 tw-schedule.js: visibility + button from the registry (schedule)',
    /twActionState\('schedule'/.test(sch) && /twAction\('schedule'/.test(sch));

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
