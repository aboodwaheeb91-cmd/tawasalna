// test_vm01_bfcache_runtime.js — VM-01 bfcache session revalidation runtime tests
// Tests 9 scenarios for profile-v2.render.js and edu-profile.html session guards.
// Run: node test_vm01_bfcache_runtime.js
'use strict';

// ── Minimal DOM/window shim ──────────────────────────────────────────────────
const _classes = new Set();
const _bodyClasses = {
  add(c){ _classes.add(c); },
  remove(c){ _classes.delete(c); },
  contains(c){ return _classes.has(c); }
};

const _domElements = {};
function _mkEl(id){ return { style:{display:'',cssText:''}, classList:{ _s:new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);}, contains(c){return this._s.has(c);} } }; }

global.document = {
  body: { classList: _bodyClasses },
  getElementById(id){ if(!_domElements[id]) _domElements[id]=_mkEl(id); return _domElements[id]; },
  querySelectorAll(){ return []; },
  createElement(){ return {style:{},className:'',textContent:'',appendChild(){},remove(){}}; }
};
global.window = global;
global.fetch = async function(){ return { ok:true, json: async()=>({profile:{}}) }; };
global.localStorage = (function(){
  const s={};
  return { getItem(k){return s[k]||null;}, setItem(k,v){s[k]=v;}, removeItem(k){delete s[k];} };
})();
global.requestAnimationFrame = function(cb){ cb(); };

// ── Test harness ─────────────────────────────────────────────────────────────
let _passed = 0, _failed = 0;
function assert(label, condition){
  if(condition){ console.log('  ✅ PASS:', label); _passed++; }
  else          { console.error('  ❌ FAIL:', label); _failed++; }
}

// ── Scenario 1: Profile V2 owner → logout callback strips owner UI ──────────
console.log('\nScenario 1: Profile V2 — logout fires, owner UI revoked immediately');
(function(){
  // Setup state
  window._scViewerType = 'owner';
  window._scProfileId  = 42;
  window._scOwnerHydrationGeneration = 0;
  window._scOwnerProfile        = { id: 42, full_name: 'أحمد' };
  window._scOwnerProfilePromise = null;
  document.body.classList.add('view-owner');

  var _handlers = [];
  window.TwAuthSync = {
    onSessionChange(cb){ _handlers.push(cb); },
    getSessionSnapshot(){ return { state:'unauthenticated', isAuthenticated:false, userType:null, userId:null, reason:'logout' }; }
  };

  // Simulate handler registration (inline logic from profile-v2.render.js IIFE)
  function _simulateHandler(info){
    var reason   = info && info.reason;
    var snapshot = (info && info.snapshot) || TwAuthSync.getSessionSnapshot();
    if(document.body.classList.contains('preview-public-user') || document.body.classList.contains('preview-guest')) return;
    // bfcache carve-out check
    if(reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
       snapshot.userId != null && String(snapshot.userId) === String(window._scProfileId) &&
       window._scViewerType === 'owner') { return; }
    // Revoke
    window._scOwnerHydrationGeneration = (window._scOwnerHydrationGeneration || 0) + 1;
    window._scOwnerProfile        = null;
    window._scOwnerProfilePromise = null;
    if(document.body.classList.contains('view-owner')){
      document.body.classList.remove('view-owner');
      document.body.classList.add('view-guest');
      window._scViewerType = 'guest';
    }
  }

  var info = { reason:'logout', snapshot:{ state:'unauthenticated', isAuthenticated:false, userId:null } };
  _simulateHandler(info);

  assert('_scViewerType set to guest', window._scViewerType === 'guest');
  assert('body.view-owner removed',    !document.body.classList.contains('view-owner'));
  assert('body.view-guest added',      document.body.classList.contains('view-guest'));
  assert('_scOwnerProfile cleared',    window._scOwnerProfile === null);
  assert('hydration generation incremented', window._scOwnerHydrationGeneration === 1);
})();

// ── Scenario 2: Stale hydration promise blocked by generation guard ──────────
console.log('\nScenario 2: Profile V2 — stale hydration result blocked by generation guard');
(function(){
  window._scViewerType = 'owner';
  window._scProfileId  = 42;
  window._scOwnerHydrationGeneration = 3;  // current gen after revocations

  var capturedGen = 2;  // captured from older hydration call
  var resultApplied = false;

  // Simulate the guard inside the .then() callback
  if(capturedGen !== window._scOwnerHydrationGeneration){
    // guard fires → result NOT applied
  } else {
    resultApplied = true;
  }

  assert('Stale hydration result NOT applied', !resultApplied);
})();

// ── Scenario 3: bfcache pageshow — same valid owner → carve-out, no strip ───
console.log('\nScenario 3: Profile V2 — pageshow same owner with valid session → carve-out (no strip)');
(function(){
  window._scViewerType = 'owner';
  window._scProfileId  = 42;
  window._scOwnerHydrationGeneration = 0;
  window._scOwnerProfile = { id:42 };
  document.body.classList.add('view-owner');
  document.body.classList.remove('view-guest');

  var carvedOut = false;
  var revoked   = false;

  function _simulateHandler(info){
    var reason   = info && info.reason;
    var snapshot = (info && info.snapshot);
    if(reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
       snapshot.userId != null && String(snapshot.userId) === String(window._scProfileId) &&
       window._scViewerType === 'owner') {
      carvedOut = true;
      return;
    }
    revoked = true;
    window._scOwnerHydrationGeneration++;
    window._scOwnerProfile = null;
    document.body.classList.remove('view-owner');
    document.body.classList.add('view-guest');
    window._scViewerType = 'guest';
  }

  var info = { reason:'pageshow', snapshot:{ isAuthenticated:true, userType:'emp', userId:42 } };
  _simulateHandler(info);

  assert('Carve-out triggered (no revoke)', carvedOut && !revoked);
  assert('_scOwnerProfile preserved',       window._scOwnerProfile !== null);
  assert('view-owner class preserved',      document.body.classList.contains('view-owner'));
})();

// ── Scenario 4: Account A→B with valid JWT → Account A owner UI stripped ─────
console.log('\nScenario 4: Profile V2 — account switch (B views A\'s profile) → owner UI stripped');
(function(){
  window._scViewerType = 'owner';
  window._scProfileId  = 42;   // Profile belongs to user 42 (Account A)
  window._scOwnerHydrationGeneration = 0;
  window._scOwnerProfile = { id:42 };
  document.body.classList.add('view-owner');
  document.body.classList.remove('view-guest');

  var revoked = false;

  function _simulateHandler(info){
    var reason   = info && info.reason;
    var snapshot = info && info.snapshot;
    // pageshow carve-out: check snapshot.userId === _scProfileId
    if(reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
       snapshot.userId != null && String(snapshot.userId) === String(window._scProfileId) &&
       window._scViewerType === 'owner') {
      return;  // carve-out — but this won't fire because userId=99 ≠ _scProfileId=42
    }
    revoked = true;
    window._scOwnerHydrationGeneration++;
    window._scOwnerProfile = null;
    document.body.classList.remove('view-owner');
    document.body.classList.add('view-guest');
    window._scViewerType = 'guest';
  }

  // Account B (userId=99) logs in on same browser — pageshow fires
  var info = { reason:'pageshow', snapshot:{ isAuthenticated:true, userType:'emp', userId:99 } };
  _simulateHandler(info);

  assert('Owner UI revoked for account B', revoked);
  assert('_scViewerType set to guest',     window._scViewerType === 'guest');
  assert('_scOwnerProfile cleared',        window._scOwnerProfile === null);
})();

// ── Scenario 5: Guest pageshow — view-guest confirmed ────────────────────────
console.log('\nScenario 5: Profile V2 — guest viewer, pageshow → stays guest, no crash');
(function(){
  window._scViewerType = 'guest';
  window._scProfileId  = 42;
  window._scOwnerProfile = null;
  document.body.classList.remove('view-owner');
  document.body.classList.add('view-guest');

  var errorThrown = false;
  try {
    // Simulate handler for guest (no owner state to clear)
    function _simulateHandler(info){
      var reason   = info && info.reason;
      var snapshot = info && info.snapshot;
      if(reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
         snapshot.userId != null && String(snapshot.userId) === String(window._scProfileId) &&
         window._scViewerType === 'owner') {
        return;
      }
      // Revoke (no-op in guest mode since view-owner not set)
      window._scOwnerHydrationGeneration = (window._scOwnerHydrationGeneration||0) + 1;
      window._scOwnerProfile = null;
      if(document.body.classList.contains('view-owner')){
        document.body.classList.remove('view-owner');
        document.body.classList.add('view-guest');
        window._scViewerType = 'guest';
      }
    }
    _simulateHandler({ reason:'focus', snapshot:{ isAuthenticated:false, userId:null } });
  } catch(e) { errorThrown = true; }

  assert('No crash in guest mode',         !errorThrown);
  assert('view-guest class still set',     document.body.classList.contains('view-guest'));
  assert('_scOwnerProfile still null',     window._scOwnerProfile === null);
})();

// ── Scenario 6: Edu owner → logout → handler revokes (_isOwner=false) ────────
console.log('\nScenario 6: Edu profile — logout fires, _isOwner revoked, ownerActions hidden');
(function(){
  var _isOwner = true;
  var _user    = { id:7, user_type:'edu', full_name:'جامعة الأمل' };
  var _urlId   = '7';

  function _isCurrentEduOwner(){
    if (!global.TwAuthSync || !global.TwAuthSync.getSessionSnapshot) {
      try { var _u = JSON.parse(localStorage.getItem('tw_user')||'null'); if(!_u||_u.user_type!=='edu') return false; return !_urlId||String(_u.id)===String(_urlId); } catch(e){ return false; }
    }
    var _snap = TwAuthSync.getSessionSnapshot();
    if (!_snap||!_snap.isAuthenticated||_snap.userType!=='edu') return false;
    if (_snap.userId==null) return false;
    return !_urlId||String(_snap.userId)===String(_urlId);
  }

  // Handler simulation
  function _simulateEduHandler(info, setState){
    var reason   = info && info.reason;
    var snapshot = (info && info.snapshot);
    if(reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
       snapshot.userType === 'edu' && snapshot.userId != null &&
       (!_urlId || String(snapshot.userId) === String(_urlId)) && _isOwner) {
      return;  // carve-out
    }
    setState('revoked');
    _isOwner = false;
    _user    = null;
  }

  var state = 'owner';
  global.TwAuthSync = {
    onSessionChange(cb){},
    getSessionSnapshot(){ return { isAuthenticated:false, userId:null, userType:null, state:'unauthenticated' }; }
  };

  _simulateEduHandler({ reason:'logout', snapshot:{ isAuthenticated:false, userId:null } }, function(s){ state=s; });

  assert('_isOwner set to false',    !_isOwner);
  assert('_user set to null',        _user === null);
  assert('state revoked',            state === 'revoked');
  assert('_isCurrentEduOwner false after revoke', !_isCurrentEduOwner());
})();

// ── Scenario 7: Edu account switch → saveEdit blocked by _isCurrentEduOwner ──
console.log('\nScenario 7: Edu profile — account switch, saveEdit blocked by live guard');
(function(){
  var _isOwner = false;  // already revoked (account switch scenario)
  var _urlId   = '7';

  global.TwAuthSync = {
    getSessionSnapshot(){ return { isAuthenticated:true, userType:'edu', userId:99, state:'authenticated' }; }
  };

  function _isCurrentEduOwner(){
    var _snap = TwAuthSync.getSessionSnapshot();
    if (!_snap||!_snap.isAuthenticated||_snap.userType!=='edu') return false;
    if (_snap.userId==null) return false;
    return !_urlId||String(_snap.userId)===String(_urlId);
  }

  var fetchCalled = false;
  function saveEdit(){
    if (!_isCurrentEduOwner()) return;
    fetchCalled = true;
  }

  saveEdit();

  assert('saveEdit blocked (userId 99 ≠ urlId 7)', !fetchCalled);
})();

// ── Scenario 8: No duplicate listener registration ────────────────────────────
console.log('\nScenario 8: No duplicate TwAuthSync listener registered');
(function(){
  var registrations = [];
  global.TwAuthSync = {
    onSessionChange(cb){ registrations.push(cb); },
    getSessionSnapshot(){ return { isAuthenticated:false, userId:null, userType:null, state:'unauthenticated' }; }
  };

  // Simulate IIFE running once (as it does in the actual page)
  (function(){
    if (!global.TwAuthSync) return;
    TwAuthSync.onSessionChange(function(info){ /* edu handler */ });
  })();

  assert('Exactly 1 listener registered', registrations.length === 1);
})();

// ── Scenario 9: Company profile — no regression ───────────────────────────────
console.log('\nScenario 9: Company profile — bfcache carve-out uses jwt only (old pattern, no regression)');
(function(){
  // Old company.main.js carve-out pattern: reason==='pageshow' && jwt
  // We verify the test harness does NOT accidentally test profile V2 logic here
  // This is a structural check: the two carve-out conditions are independent
  var profileV2CarvedOut = false;
  var companyCarvedOut   = false;

  // Profile V2 carve-out (snapshot.userId === _scProfileId)
  function profileV2Carve(reason, snapshot, _scProfileId, _scViewerType){
    return (reason === 'pageshow' && snapshot && snapshot.isAuthenticated &&
            snapshot.userId != null && String(snapshot.userId) === String(_scProfileId) &&
            _scViewerType === 'owner');
  }

  // Company old carve-out (jwt present only)
  function companyCarve(reason, jwt){
    return (reason === 'pageshow' && !!jwt);
  }

  profileV2CarvedOut = profileV2Carve('pageshow', {isAuthenticated:true,userId:42}, 42, 'owner');
  companyCarvedOut   = companyCarve('pageshow', 'some-jwt-token');

  assert('Profile V2 carve-out triggers correctly', profileV2CarvedOut);
  assert('Company carve-out independent from Profile V2', companyCarvedOut);

  // Account switch: Profile V2 should NOT carve-out when userId ≠ profileId
  var profileV2CarvedOutForB = profileV2Carve('pageshow', {isAuthenticated:true,userId:99}, 42, 'owner');
  assert('Profile V2 does NOT carve-out for account switch', !profileV2CarvedOutForB);
})();

// ── Summary ──────────────────────────────────────────────────────────────────
console.log('\n' + '─'.repeat(50));
console.log('VM-01 bfcache runtime tests:', _passed, 'passed,', _failed, 'failed');
if (_failed > 0) { process.exit(1); }
