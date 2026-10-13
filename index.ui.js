// index.ui.js — Auth Gateway: UI effects, form switching, role selector
// Responsibilities: selectType(), showRegister(), showLogin(), checkPassStrength(),
//                   button / radio / eye wiring, hash-based auto-route.
// Shared (tw_shared.js): showToast (DS-FEEDBACK) · twT (Strings) · twIcon / twIconEl (DS-ICON).
// Does NOT contain any auth logic — login/register/redirect live in index.auth.js.
// Version: auth-gw-v10

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
    // Radio group state follows every path (click, keyboard arrows, #register-* hash route)
    var radio = activeEl.querySelector('input[type="radio"]');
    if(radio && !radio.checked) radio.checked = true;
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
    var isCo = type === 'co';   // else edu
    // Keys go on the data-tw-t* attributes too: a #register-co hash route runs before
    // twTApply (DOMContentLoaded), which would otherwise put the generic label back.
    var labelKey = isCo ? 'register.co_name' : 'register.edu_name';
    var phKey    = isCo ? 'register.co_placeholder' : 'register.edu_placeholder';
    if(nameLabel){ nameLabel.setAttribute('data-tw-t', labelKey); nameLabel.textContent = twT(labelKey); }
    if(rName){
      rName.setAttribute('data-tw-t-placeholder', phKey);
      rName.placeholder = twT(phKey);
      rName.setAttribute('autocomplete', 'organization');
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
    if(!b) return;
    b.classList.remove('active','inst');
    var radio = b.querySelector('input[type="radio"]');
    if(radio) radio.checked = false;
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
    {w:'20%',tok:'--auth-strength-very-weak'},
    {w:'40%',tok:'--auth-strength-weak'},
    {w:'60%',tok:'--auth-strength-medium'},
    {w:'80%',tok:'--auth-strength-strong'},
    {w:'100%',tok:'--auth-strength-very-strong'}
  ];
  var idx = Math.min(score, 4);
  var level = levels[idx];
  fill.style.width = level.w;
  fill.style.background = 'var(' + level.tok + ')';
  label.textContent = twT('register.strength.' + (idx + 1));
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
    btn.textContent = btn._orig || '';
    btn.disabled = false;
  }
}

// ── Password show/hide toggle (DS-INP INP-11) — <button data-pass-eye="<input id>"> ──
// Icon swap through DS-ICON (twIconEl eye / eye-off); label from the Strings System.
document.querySelectorAll('[data-pass-eye]').forEach(function(eyeBtn){
  var passEl = document.getElementById(eyeBtn.getAttribute('data-pass-eye'));
  if(!passEl) return;
  eyeBtn.addEventListener('click', function(){
    var show = passEl.type === 'password';
    passEl.type = show ? 'text' : 'password';
    eyeBtn.setAttribute('aria-pressed', show ? 'true' : 'false');
    var lbl = twT(show ? 'login.hide_password' : 'login.show_password');
    eyeBtn.setAttribute('aria-label', lbl);
    eyeBtn.setAttribute('title', lbl);
    eyeBtn.textContent = '';
    eyeBtn.appendChild(twIconEl(show ? 'eye-off' : 'eye', { size: 'md' }));
  });
});

// ── Register password strength listener (replaces oninput attr removed from HTML) ──
;(function(){
  var passEl = document.getElementById('rPass');
  if(passEl) passEl.addEventListener('input', function(){ checkPassStrength(passEl.value); });
}());

// ── Buttons + account type radios (no inline onclick in index.html) ─────────
;(function(){
  var loginBtn = document.getElementById('loginBtn');
  if(loginBtn) loginBtn.addEventListener('click', function(){ doLogin(); });
  var regBtn = document.getElementById('regBtn');
  if(regBtn) regBtn.addEventListener('click', function(){ doRegister(); });
  document.querySelectorAll('[data-auth-go]').forEach(function(b){
    b.addEventListener('click', function(){
      if(b.getAttribute('data-auth-go') === 'register') showRegister(); else showLogin();
    });
  });
  // No reset flow yet (FUTURE_ROADMAP — phase 5) → honest notice, not a dead link.
  var forgot = document.getElementById('forgotBtn');
  if(forgot) forgot.addEventListener('click', function(){ showToast(twT('login.forgot_soon'), 'info'); });
  var google = document.getElementById('googleBtn');
  if(google) google.addEventListener('click', function(){ showToast(twT('login.google_soon'), 'info'); });
  // Native radio group: click / Space / arrow keys all fire 'change' → selectType.
  document.querySelectorAll('#typeRow input[name="accountType"]').forEach(function(r){
    r.addEventListener('change', function(){ if(r.checked) selectType(r.value); });
  });
}());

// ── DS-ICON: static <i data-tw-icon> placeholders (once) ─────────────────────
if(window.twIcon && typeof twIcon.hydrate === 'function') twIcon.hydrate(document.body);

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
