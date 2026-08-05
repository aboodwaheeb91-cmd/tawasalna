// index.ui.js — Auth Gateway: UI effects, form switching, role selector, utilities
// Responsibilities: selectType(), showRegister(), showLogin(), toast() (→ showToast wrapper),
//                   checkPassStrength(), ITQAN utilities, hash-based auto-route.
// Does NOT contain any auth logic — login/register/redirect live in index.auth.js.
// Version: auth-gw-v9

'use strict';

// ── DS-NAV: Auth Gateway history state (NAV-04 Auth Back pattern) ────────────
// Login is the "root" view; Register is pushed on top. Android/Browser Back
// navigates register → login without leaving /login. No beforeunload, no trapping.
// _authViewPushed tracks whether a pushState for register is on the history stack.
var _authViewPushed = false;

// ── Role selector (register-only, 3 explicit options) ────────────────────────
// First selection: slide #registerPanel open from top.
// Type switch: slide current panel closed, update labels, slide new one open.
// Cards stay visible throughout to allow switching.
var _panelGen = 0;

function selectType(type){
  // Immediate visual feedback on cards
  ['empBtn','coBtn','eduBtn'].forEach(function(id){
    var b = document.getElementById(id);
    if(b) b.classList.remove('active','inst');
  });
  var activeEl = document.getElementById(type + 'Btn');
  if(activeEl){
    activeEl.classList.add('active');
    if(type !== 'emp') activeEl.classList.add('inst');
  }
  var typeRow = document.getElementById('typeRow');
  if(typeRow) typeRow.classList.add('has-selection');

  var panel = document.getElementById('registerPanel');
  if(!panel) return;

  var isOpen = panel.classList.contains('open');

  if(!isOpen){
    // First open: update labels, slide down, move back link below the form
    curType = type;
    _applyRegLabels(type);
    panel.classList.add('open');
    _setBackLink(true);
  } else {
    // Close current → update labels → reopen for new type
    var gen = ++_panelGen;
    panel.classList.remove('open');
    function onClose(e){
      if(e.propertyName !== 'max-height') return;
      panel.removeEventListener('transitionend', onClose);
      if(_panelGen !== gen) return; // cancelled by showLogin or rapid switch
      curType = type;
      _applyRegLabels(type);
      panel.classList.add('open');
    }
    panel.addEventListener('transitionend', onClose);
  }
}

// _setBackLink(panelOpen) — toggles which "عندك حساب؟ دخول" copy is visible.
// true  → link lives below the register form (panel is open)
// false → link lives below the role cards (panel is closed)
function _setBackLink(panelOpen){
  var bl1 = document.getElementById('regBackStep1');
  var bl2 = document.getElementById('regBackPanel');
  if(bl1) bl1.classList.toggle('hidden', panelOpen);
  if(bl2) bl2.classList.toggle('hidden', !panelOpen);
}

function _applyRegLabels(type){
  // Clear all name-related validation errors on every type switch
  if(typeof _lClearFieldError === 'function'){
    _lClearFieldError('wrapper-rName', 'r-name-error');
    _lClearFieldError('wrapper-rFirstName', 'r-first-name-error');
    _lClearFieldError('wrapper-rLastName', 'r-last-name-error');
  }

  var empFields  = document.getElementById('empNameFields');
  var orgWrapper = document.getElementById('wrapper-rName');
  var nameLabel  = document.getElementById('nameLabel');
  var rName      = document.getElementById('rName');

  if(type === 'emp'){
    if(empFields)  empFields.removeAttribute('hidden');
    if(orgWrapper) orgWrapper.setAttribute('hidden', '');
    // Clear org name value when switching away from org type
    if(rName) rName.value = '';
  } else {
    if(empFields)  empFields.setAttribute('hidden', '');
    if(orgWrapper) orgWrapper.removeAttribute('hidden');
    // Clear emp name fields when switching away from emp type
    ['rFirstName','rMiddleName','rLastName'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.value = '';
    });
    if(type === 'co'){
      if(nameLabel) nameLabel.textContent = 'اسم الشركة / الجهة';
      if(rName){
        rName.placeholder = 'اسم شركتك أو مؤسستك...';
        rName.setAttribute('autocomplete', 'organization');
      }
    } else { // edu
      if(nameLabel) nameLabel.textContent = 'اسم المؤسسة التعليمية';
      if(rName){
        rName.placeholder = 'اسم الجامعة أو المركز...';
        rName.setAttribute('autocomplete', 'organization');
      }
    }
  }
}

// ── Form switching ────────────────────────────────────────────────────────────

// _applyLoginUI — pure render: shows login, hides register.
// Called from showLogin() and popstate handler.
// Also clears register transient state (errors, submit flag) per fix H.
function _applyLoginUI(){
  ++_panelGen;
  var lb = document.getElementById('loginBubble');
  var ls = document.getElementById('loginSection');
  var s1 = document.getElementById('registerStep1');
  var rp = document.getElementById('registerPanel');
  if(lb) lb.classList.remove('hidden');
  if(ls) ls.classList.remove('hidden');
  if(s1) s1.classList.add('hidden');
  if(rp) rp.classList.remove('open');
  _setBackLink(false);
  ['empBtn','coBtn','eduBtn'].forEach(function(id){
    var b = document.getElementById(id);
    if(b) b.classList.remove('active','inst');
  });
  var typeRow = document.getElementById('typeRow');
  if(typeRow) typeRow.classList.remove('has-selection');
  _authViewPushed = false;
  // C: clear stale field focus styles on return to login
  setTimeout(function(){
    if(document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  }, 0);
  // H: clear register transient state (errors, submit flag) — values are preserved
  if(typeof _resetRegisterTransientState === 'function') _resetRegisterTransientState();
}

function showRegister(){
  ++_panelGen; // cancel any in-flight accordion transition
  var lb = document.getElementById('loginBubble');
  var ls = document.getElementById('loginSection');
  var s1 = document.getElementById('registerStep1');
  var rp = document.getElementById('registerPanel');
  if(lb) lb.classList.add('hidden');
  if(ls) ls.classList.add('hidden'); // keeps index.auth.js Enter-key guard working
  if(s1) s1.classList.remove('hidden');
  if(rp) rp.classList.remove('open');
  _setBackLink(false); // back link below role cards
  // DS-NAV: push register state once so Android/Browser Back returns to login
  if(!_authViewPushed){
    var _ex = history.state || {};
    history.pushState(Object.assign({}, _ex, {nav: Object.assign({}, _ex.nav||{}, {entryType:'push', authView:'register'})}), '');
    _authViewPushed = true;
  }
}

function showLogin(){
  // DS-NAV: use history.back() only when BOTH the in-memory flag AND the canonical
  // history.state.nav confirm a register push is on the stack (NAV-13 back-trust check).
  var _nav = history.state && history.state.nav;
  if(_authViewPushed && _nav && _nav.entryType === 'push' && _nav.authView === 'register'){
    history.back(); // popstate will call _applyLoginUI
    return;
  }
  _applyLoginUI();
}

// DS-NAV: popstate listener — pure render only, no pushState/back() here.
// Fires on Android Back, Browser Back, and history.back() calls from showLogin().
window.addEventListener('popstate', function(e){
  var state = e.state;
  var _nav = state && state.nav;
  if(_nav && _nav.authView === 'register'){
    // Forward navigation to register (unusual but handle gracefully)
    if(!_authViewPushed){
      _authViewPushed = true;
      var s1 = document.getElementById('registerStep1');
      var ls = document.getElementById('loginSection');
      var lb = document.getElementById('loginBubble');
      if(lb) lb.classList.add('hidden');
      if(ls) ls.classList.add('hidden');
      if(s1) s1.classList.remove('hidden');
    }
  } else {
    // Back to login (entryType:'replace-init' state or browser-initial null state)
    _applyLoginUI();
  }
});

// ── Toast compatibility wrapper ───────────────────────────────────────────────
// Delegates to canonical DS-FEEDBACK runtime (tw_shared.js showToast). No local Surface.
function toast(msg, type){
  window.showToast(msg, type || 'success');
}

// ── Password strength bar ─────────────────────────────────────────────────────
function checkPassStrength(val){
  var bar   = document.getElementById('passStrengthBar');
  var fill  = document.getElementById('passStrengthFill');
  var label = document.getElementById('passStrengthLabel');
  if(!bar || !val){
    if(bar)   bar.style.display='none';
    if(label){ label.style.display='none'; label.textContent=''; }
    if(fill)  { fill.style.width='0'; fill.style.background=''; }
    return;
  }
  bar.style.display='block'; label.style.display='block';
  var score = 0;
  if(val.length >= 8)  score++;
  if(val.length >= 12) score++;
  if(/[A-Z]/.test(val)) score++;
  if(/[0-9]/.test(val)) score++;
  if(/[^A-Za-z0-9]/.test(val)) score++;
  var levels = [
    {w:'20%',tok:'--auth-strength-very-weak',t:'ضعيف جداً'},
    {w:'40%',tok:'--auth-strength-weak',t:'ضعيف'},
    {w:'60%',tok:'--auth-strength-medium',t:'متوسط'},
    {w:'80%',tok:'--auth-strength-strong',t:'قوي'},
    {w:'100%',tok:'--auth-strength-very-strong',t:'قوي جداً'}
  ];
  var level = levels[Math.min(score, 4)];
  fill.style.width = level.w;
  fill.style.background = 'var(' + level.tok + ')';
  label.textContent = level.t;
  label.style.color = 'var(' + level.tok + ')';
}

// showToast provided by tw_shared.js (loaded before this file)

function setBtnLoad(btn, loading){
  if(!btn) return;
  if(loading){
    btn.classList.add('tw-btn-loading');
    btn._orig = btn.textContent;
    btn.textContent = '';
    btn.disabled = true;
  } else {
    btn.classList.remove('tw-btn-loading');
    btn.textContent = btn._orig || 'حفظ';
    btn.disabled = false;
  }
}

function twNavigate(url){
  document.body.style.cssText = 'opacity:0;transform:translateY(-6px);transition:all .2s ease;';
  setTimeout(function(){ window.location.href = url; }, 180);
}

function initScrollProg(){
  var p = document.createElement('div');
  p.className = 'tw-scroll-prog';
  document.body.prepend(p);
  window.addEventListener('scroll', function(){
    var pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
    p.style.width = Math.min(pct, 100) + '%';
  });
}

// ── Login password show/hide toggle (DS-INP INP-11) ─────────────────────────
;(function(){
  var eyeBtn  = document.getElementById('lPassEye');
  var passEl  = document.getElementById('lPass');
  var eyeShow = document.getElementById('lEyeShow');
  var eyeHide = document.getElementById('lEyeHide');
  if(!eyeBtn || !passEl) return;
  eyeBtn.addEventListener('click', function(){
    var show = passEl.type === 'password';
    passEl.type = show ? 'text' : 'password';
    eyeBtn.setAttribute('aria-pressed', show ? 'true' : 'false');
    eyeBtn.setAttribute('aria-label', show ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
    // SVGElement does not reflect .hidden as a DOM attribute; use setAttribute/removeAttribute
    if(eyeShow){ if(show) eyeShow.setAttribute('hidden',''); else eyeShow.removeAttribute('hidden'); }
    if(eyeHide){ if(!show) eyeHide.setAttribute('hidden',''); else eyeHide.removeAttribute('hidden'); }
  });
}());

// ── Register password show/hide toggle (DS-INP INP-11) ───────────────────────
;(function(){
  var eyeBtn  = document.getElementById('rPassEye');
  var passEl  = document.getElementById('rPass');
  var eyeShow = document.getElementById('rEyeShow');
  var eyeHide = document.getElementById('rEyeHide');
  if(!eyeBtn || !passEl) return;
  eyeBtn.addEventListener('click', function(){
    var show = passEl.type === 'password';
    passEl.type = show ? 'text' : 'password';
    eyeBtn.setAttribute('aria-pressed', show ? 'true' : 'false');
    eyeBtn.setAttribute('aria-label', show ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
    if(eyeShow){ if(show) eyeShow.setAttribute('hidden',''); else eyeShow.removeAttribute('hidden'); }
    if(eyeHide){ if(!show) eyeHide.setAttribute('hidden',''); else eyeHide.removeAttribute('hidden'); }
  });
}());

// ── Register password strength listener (replaces oninput attr removed from HTML) ──
;(function(){
  var passEl = document.getElementById('rPass');
  if(passEl) passEl.addEventListener('input', function(){ checkPassStrength(passEl.value); });
}());

// ── Lucide icon init ──────────────────────────────────────────────────────────
if(window.lucide && lucide.createIcons) lucide.createIcons();

// ── DS-NAV: Replace initial history entry with login state ───────────────────
// Sets canonical nav.entryType='replace-init' + nav.authView='login' baseline.
// Merges with any existing state so no other system's state is overwritten.
// Done before hash routing so hash-triggered showRegister() pushes on top.
// Ref: DS-NAV NAV-13 Auth Gateway Back Pattern.
;(function(){
  var _ex = history.state || {};
  history.replaceState(Object.assign({}, _ex, {nav: Object.assign({}, _ex.nav||{}, {entryType:'replace-init', authView:'login'})}), '');
}());

// ── Hash-based auto-route ─────────────────────────────────────────────────────
// Supports: /login#register-emp  /login#register-co  /login#register-edu
// showRegister() opens step1 (cards), selectType() then opens the fields.
;(function(){
  var hash = window.location.hash;
  if(hash === '#register-emp')      { showRegister(); selectType('emp'); }
  else if(hash === '#register-co')  { showRegister(); selectType('co');  }
  else if(hash === '#register-edu') { showRegister(); selectType('edu'); }
  else if(hash === '#register')     { showRegister(); }
}());
