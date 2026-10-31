// index.auth.js — Auth Gateway: redirect logic, login, register
// Responsibilities: redirect(), doLogin(), doRegister(), on-load session check.
// Does NOT touch DOM appearance — UI effects live in index.ui.js.
// Version: auth-gw-v16

'use strict';

// Shared state: current selected role (set by selectType() in index.ui.js)
var curType = 'emp';

// ── Post-login redirect ───────────────────────────────────────────────────────
// Single authority for where users land after login or register.
// Source of truth: user object from API response, NOT localStorage.
// Destination comes from twAccountHref() in tw_shared.js (shared with landing.html):
// account with tw_id → /u/{tw_id} (Smart Router), otherwise /login.
// P0 rules: no legacy ?id= URLs, no redirect to /messages or /notifications.
// Auth Return Destination (NAV-07): a safe ?next= (twSafeNext — internal path only)
// wins over the account destination; an unsafe one is ignored.
function _authNext(){
  try { return twSafeNext(new URLSearchParams(window.location.search).get('next') || ''); }
  catch(e){ return ''; }
}
function redirect(u){
  if(!u) return;
  window.location.href = _authNext() || twAccountHref(u);
}

// ── Single on-load session check ─────────────────────────────────────────────
// Exactly one check (Auth Gateway Rule 7). Decision comes from
// TwAuthSync.getSessionSnapshot() via twEntryDestination() — never tw_user alone.
// authenticated → redirect; expired/stale/invalid → invalidateSession('stale_entry')
// with no redirect (breaks the stale-session login ↔ profile loop).
// The same check is re-run on bfcache restore through TwAuthSync.onSessionChange
// (VM-01: no direct pageshow listener) — it is not a second on-load check.
;(function(){
  function _entryCheck(){
    var dest = twEntryDestination();
    if(dest) window.location.replace(_authNext() || dest);
  }
  _entryCheck();
  if(window.TwAuthSync && typeof TwAuthSync.onSessionChange === 'function'){
    TwAuthSync.onSessionChange(function(info){
      if(info && info.reason === 'pageshow') _entryCheck();
    });
  }
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

// Form-level banner (DS-VAL VAL-09): 'l-form-error' (login) · 'r-form-error' (register).
function _showFormBanner(id, msg){
  var banner = document.getElementById(id);
  if(!banner) return;
  var textEl = banner.querySelector('.l-form-error-text');
  if(textEl) textEl.textContent = msg;
  banner.removeAttribute('hidden');
}
function _clearFormBanner(id){
  var banner = document.getElementById(id);
  if(banner) banner.setAttribute('hidden', '');
}
function _lShowFormError(msg){ _showFormBanner('l-form-error', msg); }
function _lClearFormError(){
  _clearFormBanner('l-form-error');
  if(typeof _lShowRestore === 'function') _lShowRestore(false);   // the restore offer belongs to that error
}

// The new session goes through TwAuthSync only (auth-sync.js — the one session writer).
function _startSession(user, token){
  return !!(window.TwAuthSync && typeof TwAuthSync.startSession === 'function'
            && TwAuthSync.startSession(user, token));
}

// Login failure → fixed text by status / code (never the raw server text — API-MUT-11).
function _loginErrorText(res){
  var raw = res && res.raw;
  if(res.status === 429 && raw && raw.error && raw.error.code === 'login_locked'){
    return twT('login.err.locked');   // email / IP / IP + email lockout (PR 1.4 · 5.0h-2) — keyed on the code
  }
  if(res.status === 429) return twT('login.err.too_many');
  if(res.status === 0)   return twApiMessage(res, twT('login.err.network'));   // network / timeout
  if(res.status >= 500)  return twT('login.err.server');
  return twT('login.err.failed');   // every account failure (wrong password · unknown email · suspended · deleted) — one text, never the account state (5.4)
}

// Register failure → { field, text }. 4xx text = the server's own Arabic validation message
// (written in server.py — intentional, never str(e) — §54d); 409 = the email is taken → under
// the email field. 429 / 5xx / network → fixed text in the form banner.
function _registerError(res){
  var raw = res.raw;
  if(res.status === 422 && raw && raw.error && raw.error.code === 'terms_required'){
    return { field: 'terms', text: twT('register.err.terms_required') };   // task terms — keyed on the code
  }
  if(res.status === 409) return { field: 'email', text: twApiMessage(res, twT('register.err.failed')) };
  if(res.status === 429) return { field: null, text: twT('register.err.too_many') };
  if(res.status === 0)   return { field: null, text: twApiMessage(res, twT('login.err.network')) };
  if(res.status >= 500)  return { field: null, text: twT('register.err.server') };
  return { field: null, text: twApiMessage(res, twT('register.err.failed')) };
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
    _lShowFieldError('wrapper-lEmail', 'l-email-error', twT('login.err.email_required'));
    hasError = true;
  } else if(!_lIsValidEmail(email)){
    _lEmailErrorKind = 'format';
    _lShowFieldError('wrapper-lEmail', 'l-email-error', twT('login.err.email_format'));
    hasError = true;
  } else {
    _lEmailErrorKind = null;
    _lClearFieldError('wrapper-lEmail', 'l-email-error');
  }
  if(!pass){
    _lShowFieldError('wrapper-lPass', 'l-pass-error', twT('login.err.pass_required'));
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
    // twApi (API Client — PR 3A): never throws; network / timeout → ok:false, status 0.
    var res = await twApi('/auth/login', {method: 'POST', auth: false, body: {email: email, password: pass}});

    if(!res.ok){
      // task 8.5d — account_deleted only comes with the RIGHT password (a wrong one = the normal reply)
      if(_deletedReply(res)) return;
      // DS-VAL VAL-09: auth failure → form-level banner (not DS-FEEDBACK toast)
      // Status-based fixed messages only — never the raw server text (API-MUT-11)
      _lShowFormError(_loginErrorText(res));
      return;
    }
    if(_finishLogin(res.data, 'login.welcome')) _success = true;
  } catch(e){
    console.error('[login] unexpected error:', e);
    _lShowFormError(twT('login.err.network'));
  } finally {
    // On failure only: restore button and unlock guard
    // On success: _submitting stays true, button stays loading until redirect
    if(!_success){
      _submitting = false;
      setBtnLoad(btn, false);
    }
  }
}

// One session writer (TwAuthSync.startSession — validates the pair; malformed 2xx → false,
// nothing kept, no redirect). Shared by login + «استعادة حسابي» (same success path).
function _finishLogin(data, toastKey){
  if(!data || !data.user || !_startSession(data.user, data.token)){
    _lShowFormError(twT('login.err.incomplete'));
    return false;
  }
  // Success operational feedback via DS-FEEDBACK F34 (success is not a form error)
  showToast(twT(toastKey), 'success');
  setTimeout(function(){ redirect(data.user); }, 600);
  return true;
}

// ── Deleted account + «استعادة حسابي» (task 8.5d — docs/rules/account-deletion.md) ──
// 401 account_deleted (right password): restorable → the date + the restore button · else «الحساب غير متاح».
// The restore is its own request (POST /auth/restore with the email + password typed now) after twConfirm;
// success → the same path as a login. 403 admin_deleted → the support text. Never decided from tw_user.
function _deletedReply(res){
  var raw = res && res.raw;
  if(!(res.status === 401 && raw && raw.error && raw.error.code === 'account_deleted')) return false;
  if(raw.restorable === true){
    _lShowFormError(twT('login.deleted.restorable', { date: twFormatDate(raw.restore_until) }));
    if(typeof _lShowRestore === 'function') _lShowRestore(true);   // index.ui.js — appearance only
  } else {
    _lShowFormError(twT('login.deleted.unavailable'));
  }
  return true;
}

// Restore failure → each server code its own text (auth.restore.err.<code>); the login's fixed texts for
// 401 / 429 / network / 5xx; anything else → the generic login.restore.err.
var _RESTORE_ERR_CODES = ['not_deleted', 'expired', 'purging', 'already_purged', 'admin_deleted'];
function _restoreErrorText(res){
  var code = res.raw && res.raw.error && res.raw.error.code;
  if(code && _RESTORE_ERR_CODES.indexOf(code) >= 0) return twT('auth.restore.err.' + code);
  if(res.status === 401 || res.status === 429 || res.status === 0 || res.status >= 500) return _loginErrorText(res);
  return twT('login.restore.err');
}

async function doRestore(){
  if(_submitting) return;
  var emailEl = document.getElementById('lEmail');
  var passEl  = document.getElementById('lPass');
  var email   = emailEl ? emailEl.value.trim() : '';
  var pass    = passEl  ? passEl.value          : '';
  if(!email || !pass){ _lShowFormError(twT(email ? 'login.err.pass_required' : 'login.err.email_required')); return; }
  var ok = await twConfirm({ title: twT('login.restore.confirm_title'), message: twT('login.restore.confirm_msg'),
                             confirmText: twT('login.restore.btn') });
  if(!ok) return;
  _submitting = true;
  var btn = document.getElementById('lRestoreBtn');
  setBtnLoad(btn, true);
  var _success = false;
  try {
    var res = await twApi('/auth/restore', {method: 'POST', auth: false, body: {email: email, password: pass}});
    if(!res.ok){
      _lShowFormError(_restoreErrorText(res));
      return;
    }
    if(_finishLogin(res.data, 'login.restore.done')) _success = true;
  } catch(e){
    console.error('[restore] unexpected error:', e);
    _lShowFormError(twT('login.err.network'));
  } finally {
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
        _lShowFieldError('wrapper-lEmail', 'l-email-error', twT('login.err.email_format'));
      }
    });
    // Input: state machine drives all transitions
    //   valid                                        → clear error
    //   empty + attempted                            → Required (re-arm)
    //   empty + not attempted + was format           → clear (no Required before first submit)
    //   non-empty invalid + attempted or was format  → Format (live correction)
    //   non-empty invalid + not attempted + no prior → wait for blur (VAL-05)
    emailEl.addEventListener('input', function(){
      _lClearFormError();
      var v = emailEl.value.trim();
      if(_lIsValidEmail(v)){
        _lEmailErrorKind = null;
        _lClearFieldError('wrapper-lEmail', 'l-email-error');
      } else if(!v){
        if(_lSubmitAttempted){
          _lEmailErrorKind = 'required';
          _lShowFieldError('wrapper-lEmail', 'l-email-error', twT('login.err.email_required'));
        } else if(_lEmailErrorKind === 'format'){
          _lEmailErrorKind = null;
          _lClearFieldError('wrapper-lEmail', 'l-email-error');
        }
      } else if(_lSubmitAttempted || _lEmailErrorKind === 'format'){
        _lEmailErrorKind = 'format';
        _lShowFieldError('wrapper-lEmail', 'l-email-error', twT('login.err.email_format'));
      }
      // else: non-empty invalid, no submit attempted, no prior blur format — wait for blur
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
        _lShowFieldError('wrapper-lPass', 'l-pass-error', twT('login.err.pass_required'));
      }
    });
  }
}());

// ── DS-VAL helpers (register form) ──────────────────────────────────────────
var _rSubmitAttempted = false;  // arms Required re-show after first submit
var _rEmailErrorKind  = null;   // 'required' | 'format' | 'taken' (409) | null — never compare message text
var _rSubmitting      = false;  // BTN-09: duplicate-submit guard (register only)

// ── Register ──────────────────────────────────────────────────────────────────
async function doRegister(){
  if(_rSubmitting) return;  // BTN-09: block duplicate submit

  var emailEl = document.getElementById('rEmail');
  var passEl  = document.getElementById('rPass');
  var email   = emailEl ? emailEl.value.trim() : '';
  var pass    = passEl  ? passEl.value         : '';

  // Collect name based on account type
  var _regFirstName = '', _regMiddleName = '', _regLastName = '', _regOrgName = '';
  if(curType === 'emp'){
    var firstEl  = document.getElementById('rFirstName');
    var middleEl = document.getElementById('rMiddleName');
    var lastEl   = document.getElementById('rLastName');
    _regFirstName  = firstEl  ? firstEl.value.trim()  : '';
    _regMiddleName = middleEl ? middleEl.value.trim()  : '';
    _regLastName   = lastEl   ? lastEl.value.trim()   : '';
  } else {
    var nameEl = document.getElementById('rName');
    _regOrgName = nameEl ? nameEl.value.trim() : '';
  }

  _rSubmitAttempted = true;
  _clearFormBanner('r-form-error');   // fresh submit clears the last server error (VAL-12)

  // Inline field validation — collect all errors, show at once (DS-VAL VAL-06)
  // Clears stale errors for valid fields (autofill / password-manager)
  var hasError = false;
  if(curType === 'emp'){
    if(!_regFirstName){
      _lShowFieldError('wrapper-rFirstName', 'r-first-name-error', twT('register.err.first_required'));
      hasError = true;
    } else {
      _lClearFieldError('wrapper-rFirstName', 'r-first-name-error');
    }
    if(!_regLastName){
      _lShowFieldError('wrapper-rLastName', 'r-last-name-error', twT('register.err.last_required'));
      hasError = true;
    } else {
      _lClearFieldError('wrapper-rLastName', 'r-last-name-error');
    }
  } else {
    if(!_regOrgName){
      _lShowFieldError('wrapper-rName', 'r-name-error', twT('register.err.name_required'));
      hasError = true;
    } else {
      _lClearFieldError('wrapper-rName', 'r-name-error');
    }
  }
  if(!email){
    _rEmailErrorKind = 'required';
    _lShowFieldError('wrapper-rEmail', 'r-email-error', twT('login.err.email_required'));
    hasError = true;
  } else if(!_lIsValidEmail(email)){
    _rEmailErrorKind = 'format';
    _lShowFieldError('wrapper-rEmail', 'r-email-error', twT('login.err.email_format'));
    hasError = true;
  } else {
    _rEmailErrorKind = null;
    _lClearFieldError('wrapper-rEmail', 'r-email-error');
  }
  if(!pass){
    _lShowFieldError('wrapper-rPass', 'r-pass-error', twT('login.err.pass_required'));
    hasError = true;
  } else if(pass.length < 6){
    _lShowFieldError('wrapper-rPass', 'r-pass-error', twT('register.err.pass_short'));
    hasError = true;
  } else {
    _lClearFieldError('wrapper-rPass', 'r-pass-error');
  }
  // Terms + privacy consent (task terms) — the server rejects without it too (422 terms_required)
  var termsEl = document.getElementById('rTerms');
  var termsOk = !!(termsEl && termsEl.checked);
  if(!termsOk){
    _lShowFieldError('wrapper-rTerms', 'r-terms-error', twT('register.err.terms_required'));
    hasError = true;
  } else {
    _lClearFieldError('wrapper-rTerms', 'r-terms-error');
  }
  if(!['emp','co','edu'].includes(curType)){
    showToast(twT('register.err.type_required'), 'error');
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

  _rSubmitting = true;                       // BTN-09: lock before the request (synchronous)
  var btn = document.getElementById('regBtn');
  btn.setAttribute('aria-busy', 'true');     // BTN-07: loading state ARIA
  setBtnLoad(btn, true);
  var _success = false;
  try {
    // Build payload: structured name for emp, full_name for co/edu
    var payload = {email: email, password: pass, user_type: curType, terms_accepted: termsOk};
    if(curType === 'emp'){
      payload.first_name  = _regFirstName;
      if(_regMiddleName) payload.middle_name = _regMiddleName;
      payload.last_name   = _regLastName;
    } else {
      payload.full_name = _regOrgName;
    }
    // twApi (API Client — PR 3A): status checked before the body is used (was res.json() with no ok check).
    var res = await twApi('/auth/register', {method: 'POST', auth: false, body: payload});
    if(!res.ok){
      var err = _registerError(res);
      if(err.field === 'terms'){
        _lShowFieldError('wrapper-rTerms', 'r-terms-error', err.text);
      } else if(err.field === 'email'){
        _rEmailErrorKind = 'taken';
        _lShowFieldError('wrapper-rEmail', 'r-email-error', err.text);
        var emailInput = document.getElementById('rEmail');
        if(emailInput) emailInput.focus();
      } else {
        _showFormBanner('r-form-error', err.text);
      }
      return;
    }
    var data = res.data;
    if(!data || !data.user || !_startSession(data.user, data.token)){
      _showFormBanner('r-form-error', twT('register.err.failed'));
      return;
    }
    showToast(twT('register.success'), 'success');
    _success = true;                         // BTN-09: mark before redirect timer
    setTimeout(function(){ redirect(data.user); }, 700);
  } catch(e){
    console.error('[register] unexpected error:', e);
    _showFormBanner('r-form-error', twT('login.err.network'));
  } finally {
    // BTN-09: restore only on failure — stay locked on success until redirect
    if(!_success){
      _rSubmitting = false;
      btn.setAttribute('aria-busy', 'false');
      setBtnLoad(btn, false);
    }
  }
}

// ── Register field validation events (DS-VAL VAL-05, VAL-12) ─────────────────
// State machine — _rEmailErrorKind and _rSubmitAttempted are the source of truth.
;(function(){
  var rFirstEl = document.getElementById('rFirstName');
  var rLastEl  = document.getElementById('rLastName');
  var rNameEl  = document.getElementById('rName');
  var rEmailEl = document.getElementById('rEmail');
  var rPassEl  = document.getElementById('rPass');

  // Emp first name — live clear after submit attempt
  if(rFirstEl){
    rFirstEl.addEventListener('input', function(){
      if(!_rSubmitAttempted) return;
      if(rFirstEl.value.trim()){
        _lClearFieldError('wrapper-rFirstName', 'r-first-name-error');
      } else {
        _lShowFieldError('wrapper-rFirstName', 'r-first-name-error', twT('register.err.first_required'));
      }
    });
  }

  // Emp last name — live clear after submit attempt
  if(rLastEl){
    rLastEl.addEventListener('input', function(){
      if(!_rSubmitAttempted) return;
      if(rLastEl.value.trim()){
        _lClearFieldError('wrapper-rLastName', 'r-last-name-error');
      } else {
        _lShowFieldError('wrapper-rLastName', 'r-last-name-error', twT('register.err.last_required'));
      }
    });
  }

  // Org name (co/edu)
  if(rNameEl){
    rNameEl.addEventListener('input', function(){
      if(!_rSubmitAttempted) return;
      if(rNameEl.value.trim()){
        _lClearFieldError('wrapper-rName', 'r-name-error');
      } else {
        _lShowFieldError('wrapper-rName', 'r-name-error', twT('register.err.name_required'));
      }
    });
  }

  if(rEmailEl){
    // Blur: format error only on non-empty invalid value (VAL-05 — no Required on blur)
    rEmailEl.addEventListener('blur', function(){
      var v = rEmailEl.value.trim();
      if(v && !_lIsValidEmail(v)){
        _rEmailErrorKind = 'format';
        _lShowFieldError('wrapper-rEmail', 'r-email-error', twT('login.err.email_format'));
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
          _lShowFieldError('wrapper-rEmail', 'r-email-error', twT('login.err.email_required'));
        } else if(_rEmailErrorKind === 'format'){
          _rEmailErrorKind = null;
          _lClearFieldError('wrapper-rEmail', 'r-email-error');
        }
      } else if(_rSubmitAttempted || _rEmailErrorKind === 'format'){
        _rEmailErrorKind = 'format';
        _lShowFieldError('wrapper-rEmail', 'r-email-error', twT('login.err.email_format'));
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
        _lShowFieldError('wrapper-rPass', 'r-pass-error', twT('login.err.pass_required'));
      } else if(v.length < 6){
        _lShowFieldError('wrapper-rPass', 'r-pass-error', twT('register.err.pass_short'));
      } else {
        _lClearFieldError('wrapper-rPass', 'r-pass-error');
      }
    });
  }

  // Terms consent (task terms) — ticking the box clears its error; unticking after a submit re-shows it
  var rTermsEl = document.getElementById('rTerms');
  if(rTermsEl){
    rTermsEl.addEventListener('change', function(){
      if(rTermsEl.checked){
        _lClearFieldError('wrapper-rTerms', 'r-terms-error');
      } else if(_rSubmitAttempted){
        _lShowFieldError('wrapper-rTerms', 'r-terms-error', twT('register.err.terms_required'));
      }
    });
  }
}());

// ── Transient state reset helpers (called from index.ui.js on form switch) ───
// Clears errors and submit flags without touching field values (fix H).
function _resetRegisterTransientState(){
  _clearFormBanner('r-form-error');
  _rSubmitAttempted = false;
  _rEmailErrorKind  = null;
  _lClearFieldError('wrapper-rName',       'r-name-error');
  _lClearFieldError('wrapper-rFirstName',  'r-first-name-error');
  _lClearFieldError('wrapper-rLastName',   'r-last-name-error');
  _lClearFieldError('wrapper-rEmail',      'r-email-error');
  _lClearFieldError('wrapper-rPass',       'r-pass-error');
  _lClearFieldError('wrapper-rTerms',      'r-terms-error');
}

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
