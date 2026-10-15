// test_session_change_stale_runtime.js — task 5.0b + 5.0d (real code in a vm, no browser)
//  A. profile-v2.render.js: a getProfile reply that lands after a session change is dropped
//     (initial load + auth-sync re-verify) — a stale viewer_type=owner never renders the owner UI.
//     5.0d: a late 401 of a previous session never calls invalidateSession (no logout of the new account).
//  B. static/job/job-detail.js: one TwAuthSync.onSessionChange subscription — identity change
//     (login / logout / another account) → location.reload(); same identity → nothing.
// Run: node tests/test_session_change_stale_runtime.js
'use strict';
const fs = require('fs');
const vm = require('vm');

let failed = 0;
function check(label, cond) {
  if (cond) console.log('  PASS', label);
  else { console.error('  FAIL', label); failed++; }
}
function section(src, key) {
  const b = '// @vm-extract-begin: ' + key, e = '// @vm-extract-end: ' + key;
  const i = src.indexOf(b), j = src.indexOf(e, i);
  if (i < 0 || j < 0) throw new Error('marker missing: ' + key);
  return src.slice(i, j + e.length);
}
function deferred() {
  let resolve, reject; const p = new Promise(function (r, j) { resolve = r; reject = j; });
  return { promise: p, resolve: resolve, reject: reject };
}
const tick = () => new Promise(r => setImmediate(r));

const renderSrc = fs.readFileSync('./profile-v2.render.js', 'utf8');
const initialLoad = section(renderSrc, 'p2-initial-load');
const authsync = section(renderSrc, 'p2-authsync');

function el() {
  return { style: {}, hidden: false, textContent: '',
           classList: { add() {}, remove() {}, contains() { return false; } } };
}
function profileCtx(snapshot) {
  const els = {}, pending = [], rendered = [], invalidated = [], bodyCls = new Set(['view-owner']);
  let cb = null;
  const ctx = vm.createContext({
    console,
    document: {
      body: { classList: { add: c => bodyCls.add(c), remove: (...c) => c.forEach(x => bodyCls.delete(x)),
                           contains: c => bodyCls.has(c) } },
      getElementById: id => (els[id] = els[id] || el()),
      querySelectorAll: () => []
    },
    TwAuthSync: {
      onSessionChange: f => { cb = f; },
      getSessionSnapshot: () => snapshot.current,
      invalidateSession: r => { invalidated.push(r); }
    },
    twT: k => k,
    _scProfileId: 42,
    _scViewerType: null,
    _scOwnerHydrationGeneration: 0,
    getProfile: () => { const d = deferred(); pending.push(d); return d.promise; },
    getOwnerProfile: () => new Promise(() => {}),
    _currentJwt: () => 'jwt'
  });
  ctx.window = ctx;
  ctx.renderProfile = function (res) {           // records what would be drawn
    rendered.push(res.viewer_type);
    ctx._scViewerType = res.viewer_type;
  };
  vm.runInContext(initialLoad + '\n' + authsync, ctx);
  return { ctx, pending, rendered, invalidated, fire: info => cb(info) };
}

(async function () {
  console.log('A. profile-v2 — stale getProfile reply after a session change');
  const OWNER = { state: 'authenticated', isAuthenticated: true, userId: 42, userType: 'emp' };
  const GUEST = { state: 'guest', isAuthenticated: false, userId: null };

  // A1 — initial load in flight → logout → owner reply arrives late
  {
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    check('initial load sent one request', t.pending.length === 1);
    snap.current = GUEST;
    t.fire({ reason: 'storage', snapshot: GUEST });        // logout in another tab
    check('logout re-fetches', t.pending.length === 2);
    t.pending[0].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    check('late owner reply of the initial load is dropped', t.rendered.indexOf('owner') === -1);
    check('page stays guest', t.ctx._scViewerType === 'guest');
    t.pending[1].resolve({ viewer_type: 'guest', profile: { id: 42 } });
    await tick();
    check('reply for the current session renders', t.rendered.join() === 'guest');
  }

  // A2 — owner background re-verify (focus) in flight → logout → owner reply arrives late
  {
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    t.pending[0].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    check('initial owner render', t.rendered.join() === 'owner');
    t.fire({ reason: 'focus', snapshot: OWNER });          // same owner → background re-verify
    check('re-verify sent', t.pending.length === 2);
    snap.current = GUEST;
    t.fire({ reason: 'storage', snapshot: GUEST });
    t.pending[1].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    check('late owner re-verify reply is dropped', t.rendered.join() === 'owner' && t.ctx._scViewerType === 'guest');
    t.pending[2].resolve({ viewer_type: 'guest', profile: { id: 42 } });
    await tick();
    check('guest reply renders', t.rendered.join() === 'owner,guest');
  }

  // A3 — no session change → the re-verify reply still renders (guard is not over-eager)
  {
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    t.pending[0].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    t.fire({ reason: 'pageshow', snapshot: OWNER });
    t.pending[1].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    check('same-session re-verify renders', t.rendered.join() === 'owner,owner');
  }

  // A4 (5.0d) — late 401 after an account switch must not log out the new account
  const ACC_B = { state: 'authenticated', isAuthenticated: true, userId: 99, userType: 'emp' };
  const ACC_C = { state: 'authenticated', isAuthenticated: true, userId: 77, userType: 'emp' };
  const E401 = () => new Error('HTTP 401');
  {
    // owner re-verify (focus) in flight → account B signs in → re-verify 401s late
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    t.pending[0].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    t.fire({ reason: 'focus', snapshot: OWNER });
    snap.current = ACC_B;
    t.fire({ reason: 'storage', snapshot: ACC_B });
    t.pending[1].reject(E401());
    await tick();
    check('late 401 of the owner re-verify → no invalidateSession', t.invalidated.length === 0);
    t.pending[2].reject(E401());
    await tick();
    check('401 of the current revocation re-verify → invalidateSession', t.invalidated.join() === 'api_401');
  }
  {
    // revocation re-verify in flight → another switch → first request 401s late
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    snap.current = ACC_B;
    t.fire({ reason: 'storage', snapshot: ACC_B });
    snap.current = ACC_C;
    t.fire({ reason: 'storage', snapshot: ACC_C });
    t.pending[1].reject(E401());
    await tick();
    check('late 401 of a previous revocation re-verify → no invalidateSession', t.invalidated.length === 0);
    t.pending[2].reject(E401());
    await tick();
    check('401 of the same generation → invalidateSession', t.invalidated.join() === 'api_401');
  }
  {
    // same-session owner re-verify 401 → still invalidates (guard not over-eager)
    const snap = { current: OWNER };
    const t = profileCtx(snap);
    t.pending[0].resolve({ viewer_type: 'owner', profile: { id: 42 } });
    await tick();
    t.fire({ reason: 'focus', snapshot: OWNER });
    t.pending[1].reject(E401());
    await tick();
    check('same-session re-verify 401 → invalidateSession', t.invalidated.join() === 'api_401');
  }

  console.log('B. job-detail — session change reloads, same identity does nothing');
  const jobSrc = fs.readFileSync('./static/job/job-detail.js', 'utf8');
  function jobCtx(start) {
    let cb = null, subs = 0, reloads = 0;
    const ctx = vm.createContext({
      console,
      TwAuthSync: { onSessionChange: f => { cb = f; subs++; }, getSessionSnapshot: () => start },
      getTwUser: () => ({}),
      location: { reload: () => { reloads++; }, pathname: '/job/J1', search: '' },
      document: { readyState: 'loading', addEventListener() {} }   // _init not run — session code only
    });
    ctx.window = ctx;
    vm.runInContext(jobSrc, ctx);
    return { subs: () => subs, reloads: () => reloads, fire: s => cb({ reason: 'x', snapshot: s }) };
  }
  const EMP = { state: 'authenticated', isAuthenticated: true, userId: 7, userType: 'emp' };
  const EMP2 = { state: 'authenticated', isAuthenticated: true, userId: 8, userType: 'emp' };
  const EXPIRED = { state: 'expired', isAuthenticated: false, userId: 7 };

  let j = jobCtx(EMP);
  check('one subscription', j.subs() === 1);
  j.fire(EMP);                       // focus / pageshow with the same account
  check('same identity → no reload', j.reloads() === 0);
  j.fire(EXPIRED);
  check('logout / expiry → reload', j.reloads() === 1);
  j = jobCtx(EMP); j.fire(EMP2);
  check('another account → reload', j.reloads() === 1);
  j = jobCtx(GUEST); j.fire(GUEST);
  check('guest stays guest → no reload', j.reloads() === 0);
  j.fire(EMP);
  check('guest logs in → reload', j.reloads() === 1);

  console.log(failed ? '\n' + failed + ' FAILED' : '\nALL PASSED');
  process.exit(failed ? 1 : 0);
})();
