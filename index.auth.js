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
  if(u.user_type === 'co')    { window.location.href = '/company-profile'; return; }
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

// ── Login ─────────────────────────────────────────────────────────────────────
async function doLogin(){
  var email = document.getElementById('lEmail').value.trim();
  var pass  = document.getElementById('lPass').value;
  if(!email || !pass){ toast('أدخل البريد وكلمة المرور', 'error'); return; }
  var btn = document.getElementById('loginBtn');
  setBtnLoad(btn, true);
  try {
    var res  = await fetch('/auth/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email, password:pass})
    });
    var data = await res.json();
    if(!res.ok){ toast(data.detail || 'بيانات الدخول غير صحيحة', 'error'); return; }
    // Clear any stale tw_ keys before writing new session (prevents cross-account leaks)
    Object.keys(localStorage)
      .filter(function(k){ return k.startsWith('tw_'); })
      .forEach(function(k){ localStorage.removeItem(k); });
    localStorage.setItem('tw_user', JSON.stringify(data.user));
    if(data.token) localStorage.setItem('tw_jwt', data.token);
    toast('مرحباً بك! 👋');
    setTimeout(function(){ redirect(data.user); }, 600);
  } catch(e) {
    toast('تعذّر الاتصال بالخادم', 'error');
  } finally {
    setBtnLoad(btn, false);
  }
}

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
