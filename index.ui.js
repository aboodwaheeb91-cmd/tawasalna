// index.ui.js — Auth Gateway: UI effects, form switching, role selector, utilities
// Responsibilities: selectType(), showRegister(), showLogin(), toast(),
//                   checkPassStrength(), ITQAN utilities, hash-based auto-route.
// Does NOT contain any auth logic — login/register/redirect live in index.auth.js.
// Version: auth-gw-v1

'use strict';

// ── Role selector (register-only, 3 explicit options) ────────────────────────
// Updates curType (declared in index.auth.js) and adjusts name field label.
function selectType(type){
  curType = type;
  var empBtn = document.getElementById('empBtn');
  var coBtn  = document.getElementById('coBtn');
  var eduBtn = document.getElementById('eduBtn');
  var nameLabel = document.getElementById('nameLabel');
  var rName     = document.getElementById('rName');

  [empBtn, coBtn, eduBtn].forEach(function(b){ if(b) b.classList.remove('active','inst'); });

  if(type === 'emp'){
    if(empBtn) empBtn.classList.add('active');
    if(nameLabel) nameLabel.textContent = 'الاسم الكامل';
    if(rName)     rName.placeholder = 'اكتب اسمك...';
  } else if(type === 'co'){
    if(coBtn) coBtn.classList.add('active','inst');
    if(nameLabel) nameLabel.textContent = 'اسم الشركة / الجهة';
    if(rName)     rName.placeholder = 'اسم شركتك أو مؤسستك...';
  } else if(type === 'edu'){
    if(eduBtn) eduBtn.classList.add('active','inst');
    if(nameLabel) nameLabel.textContent = 'اسم المؤسسة التعليمية';
    if(rName)     rName.placeholder = 'اسم الجامعة أو المركز...';
  }
}

// ── Form switching ────────────────────────────────────────────────────────────
function showRegister(){
  document.getElementById('loginSection').classList.add('hidden');
  document.getElementById('registerSection').classList.remove('hidden');
  var typeRow = document.getElementById('typeRow');
  if(typeRow) typeRow.classList.remove('hidden');
}

function showLogin(){
  document.getElementById('registerSection').classList.add('hidden');
  document.getElementById('loginSection').classList.remove('hidden');
  var typeRow = document.getElementById('typeRow');
  if(typeRow) typeRow.classList.add('hidden');
}

// ── Simple inline toast ───────────────────────────────────────────────────────
function toast(msg, type){
  type = type || 'success';
  var t = document.getElementById('toast');
  if(!t) return;
  t.textContent = msg;
  t.className = 'toast ' + type + ' show';
  setTimeout(function(){ t.classList.remove('show'); }, 3200);
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

// ── ITQAN shared utilities ────────────────────────────────────────────────────
var _twToast = null;
function showToast(msg, type, dur){
  type = type || 'success'; dur = dur || 2800;
  if(_twToast){ _twToast.remove(); }
  var t = document.createElement('div');
  t.className = 'tw-toast ' + type;
  t.setAttribute('aria-live', 'polite');
  var ico = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  t.innerHTML = '<span>' + ico + '</span><span>' + msg + '</span>';
  document.body.appendChild(t);
  _twToast = t;
  requestAnimationFrame(function(){
    requestAnimationFrame(function(){ t.classList.add('show'); });
  });
  setTimeout(function(){
    t.classList.remove('show');
    setTimeout(function(){ if(t.parentNode) t.remove(); }, 350);
  }, dur);
}

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

// ── Hash-based auto-route ─────────────────────────────────────────────────────
// Supports: /login#register-emp  /login#register-co  /login#register-edu
// Landing page can link here to pre-select a role and open the register form.
;(function(){
  var hash = window.location.hash;
  if(hash === '#register-emp')      { selectType('emp'); showRegister(); }
  else if(hash === '#register-co')  { selectType('co');  showRegister(); }
  else if(hash === '#register-edu') { selectType('edu'); showRegister(); }
}());
