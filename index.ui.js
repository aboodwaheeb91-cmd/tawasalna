// index.ui.js — Auth Gateway: UI effects, form switching, role selector, utilities
// Responsibilities: selectType(), showRegister(), showLogin(), toast() (→ showToast wrapper),
//                   checkPassStrength(), ITQAN utilities, hash-based auto-route.
// Does NOT contain any auth logic — login/register/redirect live in index.auth.js.
// Version: auth-gw-v8

'use strict';

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
  var nameLabel = document.getElementById('nameLabel');
  var rName     = document.getElementById('rName');
  if(type === 'co'){
    if(nameLabel) nameLabel.textContent = 'اسم الشركة / الجهة';
    if(rName)     rName.placeholder = 'اسم شركتك أو مؤسستك...';
  } else if(type === 'edu'){
    if(nameLabel) nameLabel.textContent = 'اسم المؤسسة التعليمية';
    if(rName)     rName.placeholder = 'اسم الجامعة أو المركز...';
  } else {
    if(nameLabel) nameLabel.textContent = 'الاسم الكامل';
    if(rName)     rName.placeholder = 'اكتب اسمك...';
  }
}

// ── Form switching ────────────────────────────────────────────────────────────
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
}

function showLogin(){
  ++_panelGen; // cancel any in-flight accordion transition
  var lb = document.getElementById('loginBubble');
  var ls = document.getElementById('loginSection');
  var s1 = document.getElementById('registerStep1');
  var rp = document.getElementById('registerPanel');
  if(lb) lb.classList.remove('hidden');
  if(ls) ls.classList.remove('hidden');
  if(s1) s1.classList.add('hidden');
  if(rp) rp.classList.remove('open');
  _setBackLink(false); // reset for next register visit
  // reset card states for next visit to register
  ['empBtn','coBtn','eduBtn'].forEach(function(id){
    var b = document.getElementById(id);
    if(b) b.classList.remove('active','inst');
  });
  var typeRow = document.getElementById('typeRow');
  if(typeRow) typeRow.classList.remove('has-selection');
}

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
  if(!bar || !val){ if(bar) bar.style.display='none'; return; }
  bar.style.display='block'; label.style.display='block';
  var score = 0;
  if(val.length >= 8)  score++;
  if(val.length >= 12) score++;
  if(/[A-Z]/.test(val)) score++;
  if(/[0-9]/.test(val)) score++;
  if(/[^A-Za-z0-9]/.test(val)) score++;
  var levels = [
    {w:'20%',c:'#ef4444',t:'ضعيف جداً'},
    {w:'40%',c:'#f97316',t:'ضعيف'},
    {w:'60%',c:'#eab308',t:'متوسط'},
    {w:'80%',c:'#22c55e',t:'قوي'},
    {w:'100%',c:'#00c896',t:'قوي جداً'}
  ];
  var level = levels[Math.min(score, 4)];
  fill.style.width = level.w;
  fill.style.background = level.c;
  label.textContent = level.t;
  label.style.color = level.c;
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

// ── Hash-based auto-route ─────────────────────────────────────────────────────
// Supports: /login#register-emp  /login#register-co  /login#register-edu
// showRegister() opens step1 (cards), selectType() then opens the fields.
;(function(){
  var hash = window.location.hash;
  if(hash === '#register-emp')      { showRegister(); selectType('emp'); }
  else if(hash === '#register-co')  { showRegister(); selectType('co');  }
  else if(hash === '#register-edu') { showRegister(); selectType('edu'); }
}());
