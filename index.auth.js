// index.auth.js — Auth Gateway: redirect logic, login, register
// Responsibilities: redirect(), doLogin(), doRegister(), on-load session check.
// Does NOT touch DOM appearance — UI effects live in index.ui.js.
// Version: auth-gw-v5

'use strict';

// Shared state: current selected role (set by selectType() in index.ui.js)
var curType = 'emp';

// ── Post-login redirect ───────────────────────────────────────────────────────
// Single authority for where users land after login or register.
// Source of truth: user object from API response, NOT localStorage.
// P0 rules: no legacy ?id= URLs, no redirect to /messages or /notifications.
function redirect(u){
  if(!u) return;
  if(u.user_type === 'co')    { window.location.href = u.tw_id ? '/u/' + u.tw_id : '/company-profile'; return; }
  if(u.user_type === 'edu')   { window.location.href = '/edu-profile';     return; }
  // Defensive: admin normally uses a separate auth flow.
  if(u.user_type === 'admin') { window.location.href = '/admin';           return; }
  // Employee: canonical public profile. Fallback for legacy accounts missing tw_id.
  window.location.href = u.tw_id ? '/u/' + u.tw_id : '/profile-showcase';
}

// ── Single on-load session check ─────────────────────────────────────────────
// Exactly one check. If a valid cached session exists, redirect immediately.
// TODO (P1): call POST /auth/verify-token before trusting the cached session.
;(function(){
  try {
    var _cached = JSON.parse(localStorage.getItem('tw_user'));
    if(_cached && _cached.id) redirect(_cached);
  } catch(e){}
}());

// ── DS-VAL helpers (login form — not used outside login) ─────────────────────
var _submitting       = false;
var _lSubmitAttempted = false;  // arms Required re-show after first submit
var _lEmailErrorKind  = null;   // 'required' | 'format' | null — never compare message text

function _lShowFieldError(wrapperId, errorId, msg){
  var wrapper = document.getElementById(wrapperId);
  var errorEl = document.getElementById(errorId);
  if(wrapper) wrapper.classList.add('has-error');
  if(errorEl){ errorEl.textContent = msg; errorEl.removeAttribute('hidden'); }
  var input = wrapper ? wrapper.querySelector('input') : null;
  if(input) input.setAttribute('aria-invalid', 'true');
}

function _lClearFieldError(wrapperId, errorId){
  var wrapper = document.getElementById(wrapperId);
  var errorEl = document.getElementById(errorId);
  if(wrapper) wrapper.classList.remove('has-error');
  if(errorEl){ errorEl.textContent = ''; errorEl.setAttribute('hidden', ''); }
  var input = wrapper ? wrapper.querySelector('input') : null;
  if(input) input.setAttribute('aria-invalid', 'false');
}

function _lShowFormError(msg){
  var banner = document.getElementById('l-form-error');
  if(!banner) return;
  var textEl = banner.querySelector('.l-form-error-text');
  if(textEl) textEl.textContent = msg;
  banner.removeAttribute('hidden');
}

function _lClearFormError(){
  var banner = document.getElementById('l-form-error');
  if(banner) banner.setAttribute('hidden', '');
}

function _lIsValidEmail(v){
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

// ── Login ─────────────────────────────────────────────────────────────────────
async function doLogin(){
  if(_submitting) return;

  var emailEl = document.getElementById('lEmail');
  var passEl  = document.getElementById('lPass');
  var email   = emailEl ? emailEl.value.trim() : '';
  var pass    = passEl  ? passEl.value          : '';

  // Arm state machine so input handlers know a submit has been attempted
  _lSubmitAttempted = true;

  // Clear server error on fresh submit (DS-VAL VAL-12)
  _lClearFormError();

  // Client-side validation — collect all errors, show at once (DS-VAL VAL-08)
  // Also clears any stale errors for valid fields: autofill / password-manager may
  // populate fields without firing input events, so we cannot rely solely on those handlers.
  var hasError = false;
  if(!email){
    _lEmailErrorKind = 'required';
    _lShowFieldError('wrapper-lEmail', 'l-email-error', 'البريد الإلكتروني مطلوب');
    hasError = true;
  } else if(!_lIsValidEmail(email)){
    _lEmailErrorKind = 'format';
    _lShowFieldError('wrapper-lEmail', 'l-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
    hasError = true;
  } else {
    _lEmailErrorKind = null;
    _lClearFieldError('wrapper-lEmail', 'l-email-error');
  }
  if(!pass){
    _lShowFieldError('wrapper-lPass', 'l-pass-error', 'كلمة المرور مطلوبة');
    hasError = true;
  } else {
    _lClearFieldError('wrapper-lPass', 'l-pass-error');
  }
  if(hasError){
    var firstErr = document.querySelector('#loginSection .field.has-error input');
    if(firstErr){
      firstErr.focus();
      firstErr.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
    return;
  }

  // DS-BTN BTN-09: guard double-submit; button stays loading until redirect (user is leaving)
  _submitting = true;
  var btn = document.getElementById('loginBtn');
  setBtnLoad(btn, true);
  var _success = false;

  try {
    var res = await fetch('/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: email, password: pass})
    });

    // Safe JSON parse — non-JSON body (e.g. 502 HTML) must not throw to network handler
    var data;
    try { data = await res.json(); } catch(_e){ data = null; }

    if(!res.ok){
      // DS-VAL VAL-09: auth failure → form-level banner (not DS-FEEDBACK toast)
      // HTTP-status-based safe messages only — never expose raw data.detail (API-MUT-11)
      var safeMsg;
      if(res.status === 429){
        safeMsg = 'محاولات كثيرة جداً، حاول مرة أخرى لاحقاً';
      } else if(res.status >= 500){
        safeMsg = 'تعذّر تسجيل الدخول حالياً، حاول مرة أخرى لاحقاً';
      } else {
        safeMsg = 'بيانات الدخول غير صحيحة';
      }
      _lShowFormError(safeMsg);
      return;
    }

    // Validate 2xx structure before writing storage — malformed success must not redirect
    if(!data || !data.user || !data.user.id ||
       !data.token || typeof data.token !== 'string' || !data.token.trim()){
      _lShowFormError('تعذّر إكمال تسجيل الدخول، حاول مرة أخرى');
      return;
    }

    // Atomic session write — rollback both keys on any storage failure
    try {
      Object.keys(localStorage)
        .filter(function(k){ return k.startsWith('tw_'); })
        .forEach(function(k){ localStorage.removeItem(k); });
      localStorage.setItem('tw_user', JSON.stringify(data.user));
      localStorage.setItem('tw_jwt', data.token);
    } catch(storageErr){
      try { localStorage.removeItem('tw_user'); } catch(e){}
      try { localStorage.removeItem('tw_jwt');  } catch(e){}
      _lShowFormError('حدث خطأ أثناء تسجيل الدخول، حاول مرة أخرى');
      return;
    }

    // Only mark success AFTER all critical writes complete
    _success = true;
    // Success operational feedback via DS-FEEDBACK F34 (success is not a form error)
    toast('مرحباً بك', 'success');
    setTimeout(function(){ redirect(data.user); }, 600);
  } catch(e){
    _lShowFormError('تعذّر الاتصال بالخادم، تحقق من اتصالك وحاول مرة أخرى');
  } finally {
    // On failure only: restore button and unlock guard
    // On success: _submitting stays true, button stays loading until redirect
    if(!_success){
      _submitting = false;
      setBtnLoad(btn, false);
    }
  }
}

// ── Login field validation events (DS-VAL VAL-05, VAL-12) ────────────────────
// State machine — _lEmailErrorKind and _lSubmitAttempted are the source of truth.
// Never compare error message text to determine state.
;(function(){
  var emailEl = document.getElementById('lEmail');
  if(emailEl){
    // Blur: format error only on non-empty value (VAL-05 — no Required on blur)
    emailEl.addEventListener('blur', function(){
      var v = emailEl.value.trim();
      if(v && !_lIsValidEmail(v)){
        _lEmailErrorKind = 'format';
        _lShowFieldError('wrapper-lEmail', 'l-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
      }
    });
    // Input: state machine drives all transitions
    //   valid           → clear error
    //   empty + attempted  → Required (re-arm)
    //   empty + not attempted + was format → clear (no Required before first submit)
    //   non-empty invalid   → Format
    emailEl.addEventListener('input', function(){
      _lClearFormError();
      var v = emailEl.value.trim();
      if(_lIsValidEmail(v)){
        _lEmailErrorKind = null;
        _lClearFieldError('wrapper-lEmail', 'l-email-error');
      } else if(!v){
        if(_lSubmitAttempted){
          _lEmailErrorKind = 'required';
          _lShowFieldError('wrapper-lEmail', 'l-email-error', 'البريد الإلكتروني مطلوب');
        } else if(_lEmailErrorKind === 'format'){
          _lEmailErrorKind = null;
          _lClearFieldError('wrapper-lEmail', 'l-email-error');
        }
      } else {
        _lEmailErrorKind = 'format';
        _lShowFieldError('wrapper-lEmail', 'l-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
      }
    });
  }
  var passEl = document.getElementById('lPass');
  if(passEl){
    // Input: clear server error; Required re-arms when field goes empty after a submit attempt
    passEl.addEventListener('input', function(){
      _lClearFormError();
      if(passEl.value){
        _lClearFieldError('wrapper-lPass', 'l-pass-error');
      } else if(_lSubmitAttempted){
        _lShowFieldError('wrapper-lPass', 'l-pass-error', 'كلمة المرور مطلوبة');
      }
    });
  }
}());

// ── DS-VAL helpers (register form) ──────────────────────────────────────────
var _rSubmitAttempted = false;  // arms Required re-show after first submit
var _rEmailErrorKind  = null;   // 'required' | 'format' | null — never compare message text

// ── Register ──────────────────────────────────────────────────────────────────
async function doRegister(){
  var nameEl  = document.getElementById('rName');
  var emailEl = document.getElementById('rEmail');
  var passEl  = document.getElementById('rPass');
  var name    = nameEl  ? nameEl.value.trim()  : '';
  var email   = emailEl ? emailEl.value.trim() : '';
  var pass    = passEl  ? passEl.value         : '';

  _rSubmitAttempted = true;

  // Inline field validation — collect all errors, show at once (DS-VAL VAL-06)
  // Clears stale errors for valid fields (autofill / password-manager)
  var hasError = false;
  if(!name){
    _lShowFieldError('wrapper-rName', 'r-name-error', 'الاسم مطلوب');
    hasError = true;
  } else {
    _lClearFieldError('wrapper-rName', 'r-name-error');
  }
  if(!email){
    _rEmailErrorKind = 'required';
    _lShowFieldError('wrapper-rEmail', 'r-email-error', 'البريد الإلكتروني مطلوب');
    hasError = true;
  } else if(!_lIsValidEmail(email)){
    _rEmailErrorKind = 'format';
    _lShowFieldError('wrapper-rEmail', 'r-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
    hasError = true;
  } else {
    _rEmailErrorKind = null;
    _lClearFieldError('wrapper-rEmail', 'r-email-error');
  }
  if(!pass){
    _lShowFieldError('wrapper-rPass', 'r-pass-error', 'كلمة المرور مطلوبة');
    hasError = true;
  } else if(pass.length < 6){
    _lShowFieldError('wrapper-rPass', 'r-pass-error', 'كلمة المرور قصيرة جداً (6 أحرف على الأقل)');
    hasError = true;
  } else {
    _lClearFieldError('wrapper-rPass', 'r-pass-error');
  }
  if(!['emp','co','edu'].includes(curType)){
    toast('اختر نوع الحساب', 'error');
    hasError = true;
  }
  if(hasError){
    var firstErr = document.querySelector('#registerPanel .field.has-error input');
    if(firstErr){
      firstErr.focus();
      firstErr.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
    return;
  }

  var btn = document.getElementById('regBtn');
  btn._orig = 'إنشاء حساب';
  setBtnLoad(btn, true);
  try {
    var res  = await fetch('/auth/register', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({full_name:name, email:email, password:pass, user_type:curType})
    });
    var data = await res.json();
    if(!res.ok){ toast(data.detail || 'خطأ في التسجيل', 'error'); return; }
    localStorage.setItem('tw_user', JSON.stringify(data.user));
    if(data.token) localStorage.setItem('tw_jwt', data.token);
    toast('تم إنشاء حسابك! 🎉');
    setTimeout(function(){ redirect(data.user); }, 700);
  } catch(e){
    toast('تعذّر الاتصال بالخادم', 'error');
  } finally {
    setBtnLoad(btn, false);
  }
}

// ── Register field validation events (DS-VAL VAL-05, VAL-12) ─────────────────
// State machine — _rEmailErrorKind and _rSubmitAttempted are the source of truth.
;(function(){
  var rNameEl  = document.getElementById('rName');
  var rEmailEl = document.getElementById('rEmail');
  var rPassEl  = document.getElementById('rPass');

  if(rNameEl){
    rNameEl.addEventListener('input', function(){
      if(!_rSubmitAttempted) return;
      if(rNameEl.value.trim()){
        _lClearFieldError('wrapper-rName', 'r-name-error');
      } else {
        _lShowFieldError('wrapper-rName', 'r-name-error', 'الاسم مطلوب');
      }
    });
  }

  if(rEmailEl){
    // Blur: format error only on non-empty invalid value (VAL-05 — no Required on blur)
    rEmailEl.addEventListener('blur', function(){
      var v = rEmailEl.value.trim();
      if(v && !_lIsValidEmail(v)){
        _rEmailErrorKind = 'format';
        _lShowFieldError('wrapper-rEmail', 'r-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
      }
    });
    // Input: state machine drives all transitions
    rEmailEl.addEventListener('input', function(){
      var v = rEmailEl.value.trim();
      if(_lIsValidEmail(v)){
        _rEmailErrorKind = null;
        _lClearFieldError('wrapper-rEmail', 'r-email-error');
      } else if(!v){
        if(_rSubmitAttempted){
          _rEmailErrorKind = 'required';
          _lShowFieldError('wrapper-rEmail', 'r-email-error', 'البريد الإلكتروني مطلوب');
        } else if(_rEmailErrorKind === 'format'){
          _rEmailErrorKind = null;
          _lClearFieldError('wrapper-rEmail', 'r-email-error');
        }
      } else if(_rSubmitAttempted || _rEmailErrorKind === 'format'){
        _rEmailErrorKind = 'format';
        _lShowFieldError('wrapper-rEmail', 'r-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
      }
      // else: non-empty invalid before submit and before any blur Format — wait for blur
    });
  }

  if(rPassEl){
    // Input: Required / short error re-arms after first submit attempt
    rPassEl.addEventListener('input', function(){
      if(!_rSubmitAttempted) return;
      var v = rPassEl.value;
      if(!v){
        _lShowFieldError('wrapper-rPass', 'r-pass-error', 'كلمة المرور مطلوبة');
      } else if(v.length < 6){
        _lShowFieldError('wrapper-rPass', 'r-pass-error', 'كلمة المرور قصيرة جداً (6 أحرف على الأقل)');
      } else {
        _lClearFieldError('wrapper-rPass', 'r-pass-error');
      }
    });
  }
}());

// ── Enter key shortcut ────────────────────────────────────────────────────────
// Guard: only fire when user is actively focused on an INPUT element.
// Prevents autofill from triggering doLogin() without explicit user action.
// Login: Enter in email → focus password (DS-INP sequential nav); Enter in password → submit.
document.addEventListener('keydown', function(e){
  if(e.key !== 'Enter') return;
  if(!e.target || e.target.tagName !== 'INPUT') return;
  var login = document.getElementById('loginSection');
  if(login && !login.classList.contains('hidden')){
    e.preventDefault();
    if(e.target.id === 'lEmail'){
      var passEl = document.getElementById('lPass');
      if(passEl) passEl.focus();
    } else {
      doLogin();
    }
  } else {
    doRegister();
  }
});
