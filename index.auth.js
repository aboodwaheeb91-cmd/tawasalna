// index.auth.js — Auth Gateway: redirect logic, login, register
// Responsibilities: redirect(), doLogin(), doRegister(), on-load session check.
// Does NOT touch DOM appearance — UI effects live in index.ui.js.
// Version: auth-gw-v4

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
var _submitting = false;

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

  // Clear server error on fresh submit (DS-VAL VAL-12)
  _lClearFormError();

  // Client-side validation — collect all errors, show at once (DS-VAL VAL-08)
  var hasError = false;
  if(!email){
    _lShowFieldError('wrapper-lEmail', 'l-email-error', 'البريد الإلكتروني مطلوب');
    hasError = true;
  } else if(!_lIsValidEmail(email)){
    _lShowFieldError('wrapper-lEmail', 'l-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
    hasError = true;
  }
  if(!pass){
    _lShowFieldError('wrapper-lPass', 'l-pass-error', 'كلمة المرور مطلوبة');
    hasError = true;
  }
  if(hasError){
    var firstErr = document.querySelector('#loginSection .field.has-error input');
    if(firstErr) firstErr.focus();
    return;
  }

  // DS-BTN BTN-09: guard double-submit; button stays loading on success (user is leaving)
  _submitting = true;
  var btn = document.getElementById('loginBtn');
  setBtnLoad(btn, true);
  var _success = false;

  try {
    var res  = await fetch('/auth/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email, password:pass})
    });
    var data = await res.json();
    if(!res.ok){
      // DS-VAL VAL-09: auth failure → form-level banner, not DS-FEEDBACK toast (F34)
      _lShowFormError(data.detail || 'بيانات الدخول غير صحيحة');
      return;
    }
    _success = true;
    // Clear any stale tw_ keys before writing new session (prevents cross-account leaks)
    Object.keys(localStorage)
      .filter(function(k){ return k.startsWith('tw_'); })
      .forEach(function(k){ localStorage.removeItem(k); });
    localStorage.setItem('tw_user', JSON.stringify(data.user));
    if(data.token) localStorage.setItem('tw_jwt', data.token);
    // Success operational feedback via DS-FEEDBACK (F34 — success is not a form error)
    toast('مرحباً بك! 👋');
    setTimeout(function(){ redirect(data.user); }, 600);
  } catch(e){
    _lShowFormError('تعذّر الاتصال بالخادم، تحقق من اتصالك وحاول مرة أخرى');
  } finally {
    _submitting = false;
    if(!_success) setBtnLoad(btn, false);
  }
}

// ── Login field validation events (DS-VAL VAL-05, VAL-12) ────────────────────
;(function(){
  var emailEl = document.getElementById('lEmail');
  if(emailEl){
    // Blur: email format check on non-empty value (VAL-05 — no Required on blur)
    emailEl.addEventListener('blur', function(){
      var v = emailEl.value.trim();
      if(v && !_lIsValidEmail(v)){
        _lShowFieldError('wrapper-lEmail', 'l-email-error', 'صيغة البريد الإلكتروني غير صحيحة');
      }
    });
    // Input: clear server error; clear format error once valid (VAL-12)
    emailEl.addEventListener('input', function(){
      _lClearFormError();
      var v = emailEl.value.trim();
      if(!v || _lIsValidEmail(v)) _lClearFieldError('wrapper-lEmail', 'l-email-error');
    });
  }
  var passEl = document.getElementById('lPass');
  if(passEl){
    // Input: clear server error and Required error once non-empty (VAL-12)
    passEl.addEventListener('input', function(){
      _lClearFormError();
      if(passEl.value) _lClearFieldError('wrapper-lPass', 'l-pass-error');
    });
  }
}());

// ── Register ──────────────────────────────────────────────────────────────────
async function doRegister(){
  var full_name = document.getElementById('rName').value.trim();
  var email     = document.getElementById('rEmail').value.trim();
  var password  = document.getElementById('rPass').value;

  if(!full_name){ toast('أدخل الاسم', 'error'); return; }
  if(!email)    { toast('أدخل البريد الإلكتروني', 'error'); return; }
  if(password.length < 6){ toast('كلمة المرور قصيرة جداً', 'error'); return; }
  if(!['emp','co','edu'].includes(curType)){ toast('اختر نوع الحساب', 'error'); return; }

  var btn = document.getElementById('regBtn');
  btn._orig = 'إنشاء حساب';
  setBtnLoad(btn, true);
  try {
    var res  = await fetch('/auth/register', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({full_name, email, password, user_type: curType})
    });
    var data = await res.json();
    if(!res.ok){ toast(data.detail || 'خطأ في التسجيل', 'error'); return; }
    localStorage.setItem('tw_user', JSON.stringify(data.user));
    if(data.token) localStorage.setItem('tw_jwt', data.token);
    toast('تم إنشاء حسابك! 🎉');
    setTimeout(function(){ redirect(data.user); }, 700);
  } catch(e) {
    toast('تعذّر الاتصال بالخادم', 'error');
  } finally {
    setBtnLoad(btn, false);
  }
}

// ── Enter key shortcut ────────────────────────────────────────────────────────
// Guard: only fire when user is actively focused on an INPUT element.
// Prevents autofill from triggering doLogin() without explicit user action.
document.addEventListener('keydown', function(e){
  if(e.key !== 'Enter') return;
  if(!e.target || e.target.tagName !== 'INPUT') return;
  var login = document.getElementById('loginSection');
  if(login && !login.classList.contains('hidden')) doLogin();
  else doRegister();
});
