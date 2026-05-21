// ══ tw_shared.js - Shared Utilities ══
// تواصلنا - Shared JavaScript Utilities

var _twToast = null;

function showToast(msg, type, dur) {
  type = type || 'success';
  dur  = dur  || 2800;
  if (_twToast) { _twToast.remove(); }
  var t = document.createElement('div');
  t.className = 'tw-toast ' + type;
  var ico = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  t.innerHTML = '<span>' + ico + '</span><span>' + msg + '</span>';
  document.body.appendChild(t);
  _twToast = t;
  requestAnimationFrame(function(){
    requestAnimationFrame(function(){ t.classList.add('show'); });
  });
  setTimeout(function(){
    t.classList.remove('show');
    setTimeout(function(){ if (t.parentNode) t.remove(); }, 350);
  }, dur);
}

function setBtnLoad(btn, loading) {
  if (!btn) return;
  if (loading) {
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

function twNavigate(url) {
  document.body.style.cssText = 'opacity:0;transform:translateY(-6px);transition:all .2s ease;';
  setTimeout(function(){ window.location.href = url; }, 180);
}

function initScrollProg() {
  var p = document.createElement('div');
  p.className = 'tw-scroll-prog';
  document.body.prepend(p);
  window.addEventListener('scroll', function(){
    var pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
    p.style.width = Math.min(pct, 100) + '%';
  });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e){
  if (e.key === 'Escape') {
    var fn = window.closeModal || window.closeEdit || window.closePostJob || window.closeKYC;
    if (typeof fn === 'function') fn();
  }
  if (e.key === '/' && !['INPUT','TEXTAREA'].includes(e.target.tagName)) {
    e.preventDefault();
    var s = document.getElementById('searchInput') ||
            document.getElementById('userSearch') ||
            document.getElementById('jobSearch');
    if (s) s.focus();
  }
});

// Page fade-in
document.documentElement.style.opacity = '0';
window.addEventListener('load', function(){
  document.documentElement.style.transition = 'opacity .25s ease';
  document.documentElement.style.opacity = '1';
});

// Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function(){
    navigator.serviceWorker.register('/sw.js').catch(function(){});
  });
}
// ══ Error Tracking ══
window.addEventListener('error', function(e){
  var err = {
    msg: e.message,
    file: e.filename,
    line: e.lineno,
    page: window.location.pathname,
    ua: navigator.userAgent.slice(0,100),
    ts: new Date().toISOString()
  };
  // Send to server silently
  fetch('/log/error', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(err)
  }).catch(function(){});
});

window.addEventListener('unhandledrejection', function(e){
  fetch('/log/error', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({msg: String(e.reason), page: window.location.pathname, type: 'promise', ts: new Date().toISOString()})
  }).catch(function(){});
});

// ── XSS Protection ──
function sanitize(str){
  if(!str) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#x27;')
    .replace(/\//g,'&#x2F;');
}

// Safe text setter
function safeText(el, text){
  if(!el) return;
  el.textContent = text || '';
}

// ══ Logo from Admin ══
var _twLogos = {logo1:'', logo2:'', sizes:{}, select:{}};

function applyLogosToPage(){
  var path = window.location.pathname;
  var pageKey = 'home';
  if(path.includes('profile')) pageKey='profile';
  else if(path.includes('landing')||path==='/'||path==='') pageKey='landing';
  else if(path.includes('jobs')) pageKey='jobs';
  else if(path.includes('settings')) pageKey='settings';
  else if(path.includes('message')) pageKey='messages';
  else if(path.includes('notif')) pageKey='notifications';
  else if(path.includes('admin')) pageKey='admin';

  var size = (_twLogos.sizes[pageKey]||44)+'px';
  var sel = _twLogos.select[pageKey]||'both';
  var l1 = sel==='logo2'?'':_twLogos.logo1;
  var l2 = sel==='logo1'?'':_twLogos.logo2;
  if(sel==='none') return; // no logo for this page

  var targets=document.querySelectorAll('.nav-logo,.login-logo,.tb-logo,.nav-brand');
  targets.forEach(function(el){
    var html='';
    if(l1) html+='<img src="'+l1+'" style="height:'+size+';max-height:'+size+';object-fit:contain;display:block">';
    if(l2) html+='<img src="'+l2+'" style="height:'+size+';max-height:'+size+';object-fit:contain;display:block;margin-right:4px">';
    if(html){
      el.innerHTML=html;
      el.style.cssText=(el.style.cssText||'')+';display:flex;align-items:center;gap:4px;height:100%;padding:3px 0';
    }
  });
}

function loadAndApplyLogos(){
  fetch('/admin/logo').then(function(r){return r.json();}).then(function(d){
    _twLogos.logo1=d.logo1||'';
    _twLogos.logo2=d.logo2||'';
    _twLogos.sizes=d.sizes||{};
    _twLogos.select=d.select||{};
    if(_twLogos.logo1||_twLogos.logo2){
      applyLogosToPage();
      setTimeout(applyLogosToPage,600);
    }
  }).catch(function(){});
}

// Load logos from server on page load
if(document.readyState==='complete'){
  loadAndApplyLogos();
} else {
  window.addEventListener('load',loadAndApplyLogos);
}


