
// ══ Auth Headers Helper ══
function getAuthHeaders(json){
  var jwt = localStorage.getItem('tw_jwt')||'';
  var h = {'Authorization':'Bearer '+jwt};
  if(json) h['Content-Type']='application/json';
  return h;
}

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

// ══ Global Badge Loader ══
// Populates all elements with data-badge="msgs" and data-badge="notif".
// Call once after page init from any authenticated page.
function loadGlobalBadges() {
  try {
    var u   = JSON.parse(localStorage.getItem('tw_user') || 'null');
    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!u || !u.id || !jwt) return;

    fetch('/notifications/' + u.id)
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(d) {
        if (!d) return;
        var count = d.unread || 0;
        document.querySelectorAll('[data-badge="notif"]').forEach(function(el) {
          el.textContent = count > 9 ? '9+' : String(count);
          el.style.display = count > 0 ? 'inline-block' : 'none';
        });
      }).catch(function() {});

    fetch('/messages/unread/' + u.id, { headers: { 'Authorization': 'Bearer ' + jwt } })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(d) {
        if (!d) return;
        var count = d.count || 0;
        document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
          el.textContent = count > 9 ? '9+' : String(count);
          el.style.display = count > 0 ? 'inline-block' : 'none';
        });
      }).catch(function() {});
  } catch(e) {}
}

// ══ Logo from Admin ══
var _twLogoWide = 'https://wrxvmdmknhoufoeprpoc.supabase.co/storage/v1/object/public/site/Logo.svg';

function applyNavLogo(){
  if(!_twLogoWide) return;
  // Update existing img src if present
  document.querySelectorAll('.nav-logo img,.tb-logo img,.login-logo img,.nav-brand img').forEach(function(img){
    img.src = _twLogoWide;
  });
  // If no img found, inject it
  document.querySelectorAll('.nav-logo,.tb-logo,.login-logo,.nav-brand').forEach(function(el){
    if(!el.querySelector('img')){
      el.innerHTML = '<img src="'+_twLogoWide+'" style="height:36px;width:auto;object-fit:contain;display:block">';
    }
  });
}

function loadAndApplyLogos(){
  // Apply immediately
  applyNavLogo();
  // Retry after short delay (for dynamically rendered navbars)
  setTimeout(applyNavLogo, 200);
  setTimeout(applyNavLogo, 800);
  // Fetch from server for any updates
  fetch('/admin/logo').then(function(r){return r.json();}).then(function(d){
    if(d.logo_wide) _twLogoWide = d.logo_wide;
    applyNavLogo();
  }).catch(function(){});
}

// ══ Global Header Menu (.sc-header ☰ dropdown) ══════════════════════════
// Single source of truth for the unified mobile menu shared by every page
// built on the Profile V2 .sc-header contract (currently messages.html and
// profile-showcase.html — see ARCHITECTURE.md "Global Header Menu Contract").
// Design rule: header contains primary navigation; this menu contains
// secondary tools only. Never duplicate header nav items here.

function getTwUser() {
  try { return JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch(e) { return null; }
}

// Type-aware "home" destination — single source of truth (previously
// duplicated as goMessengerHome() in messages.render.js and hardcoded to
// '/home' for every account type in profile-v2.render.js).
function twHomeHref(u) {
  u = u || getTwUser();
  if (!u) return '/';
  return u.user_type === 'co' ? '/company' : u.user_type === 'edu' ? '/edu' : '/home';
}

function twLogout() {
  localStorage.removeItem('tw_user');
  localStorage.removeItem('tw_jwt');
  window.location.href = '/';
}

function twOwnProfileUrl() {
  var u = getTwUser();
  if (!u || !u.tw_id) return null;
  return window.location.origin + '/u/' + u.tw_id;
}

function twCopyProfileLink() {
  var url = twOwnProfileUrl();
  if (!url) { showToast('سجّل الدخول أولاً', 'error'); return; }
  navigator.clipboard.writeText(url)
    .then(function() { showToast('تم نسخ رابط الملف', 'success'); })
    .catch(function() { showToast('تعذّر نسخ الرابط', 'error'); });
}

function twShareProfile() {
  var url = twOwnProfileUrl();
  if (!url) { showToast('سجّل الدخول أولاً', 'error'); return; }
  var u = getTwUser();
  if (navigator.share) {
    navigator.share({
      title: (u && u.full_name ? u.full_name : 'بروفايل') + ' — تواصلنا',
      text:  'تعرّف على ملفي الشخصي على تواصلنا',
      url:   url
    }).catch(function() {});
  } else {
    twCopyProfileLink();
  }
}

// Secondary-tools menu items — NO navigation items (home/profile/messages/
// notifications are already in the header and must not be duplicated here).
// Items with `disabled:true` are shown greyed with a "قريباً" tag — they
// have no route yet and must NOT appear as functional links.
function _twHeaderMenuItems() {
  return [
    { key: 'settings', label: 'الإعدادات', href: '/settings',
      icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
    { key: 'contact', label: 'تواصل معنا', disabled: true,
      icon: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 12 19.79 19.79 0 0 1 1.06 3.31 2 2 0 0 1 3 1h2.09a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9a16 16 0 0 0 5.9 5.9l1.36-1.36a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 20 16z"/>' },
    { key: 'report', label: 'الإبلاغ عن مشكلة', disabled: true,
      icon: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>' },
    { key: 'suggest', label: 'اقترح ميزة', disabled: true,
      icon: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
    { key: 'logout', label: 'تسجيل الخروج', action: 'twLogout', danger: true,
      icon: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>' }
  ];
}

function _twHeaderMenuItemHtml(item) {
  var svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    + 'stroke-linecap="round" stroke-linejoin="round" class="sc-svg-icon-sm" aria-hidden="true">' + item.icon + '</svg>';
  if (item.disabled) {
    return '<div class="sc-menu-item disabled" title="قريباً">'
      + svg + sanitize(item.label)
      + '<span class="sc-menu-soon">قريباً</span></div>';
  }
  var cls = 'sc-menu-item' + (item.danger ? ' danger' : '');
  if (item.action) {
    return '<button type="button" class="' + cls + '" data-menu-action="' + item.action + '">' + svg + sanitize(item.label) + '</button>';
  }
  return '<a class="' + cls + '" href="' + item.href + '" data-key="' + item.key + '">' + svg + sanitize(item.label) + '</a>';
}

// Wires button#btnId (toggle) + #ddId (.sc-menu-dropdown, must already be
// inside a `.sc-menu-wrap` ancestor for outside-click + positioning to
// work) for one page.
// `dynId` (optional): id of the inner container to render dynamic items
// into. When omitted the items are rendered directly into #ddId. Use when
// the dropdown also contains a static section above the dynamic items —
// e.g. profile-showcase.html puts the eye-preview rows as a static first
// child of the dropdown so their directly-bound event listeners survive
// across re-renders; tw_shared.js only regenerates the sibling #scMenuDynamic
// container below them.
function initGlobalHeaderMenu(btnId, ddId, dynId) {
  var btn  = document.getElementById(btnId);
  var dd   = document.getElementById(ddId);
  var dyn  = dynId ? (document.getElementById(dynId) || dd) : dd;
  if (!btn || !dd) return;
  var wrap = dd.closest('.sc-menu-wrap') || dd.parentElement;

  function render() {
    dyn.innerHTML = _twHeaderMenuItems().map(_twHeaderMenuItemHtml).join('');
  }
  function close() {
    dd.classList.remove('open');
    // Also collapse the eye submenu (if any) so it always resets on next open
    var em = document.getElementById('scEyeMenu');
    if (em) em.classList.remove('open');
  }

  btn.addEventListener('click', function(e) {
    e.stopPropagation();
    if (!dd.classList.contains('open')) render();
    dd.classList.toggle('open');
  });
  document.addEventListener('click', function(e) {
    if (wrap && !wrap.contains(e.target)) close();
  });
  dd.addEventListener('click', function(e) {
    var actionEl = e.target.closest('[data-menu-action]');
    if (actionEl) {
      var fn = window[actionEl.getAttribute('data-menu-action')];
      if (typeof fn === 'function') fn();
    }
    // Let the host page run cleanup (e.g. messages.html marking the open
    // conversation inactive over the existing WS) before a menu link navigates away.
    var link = e.target.closest('a.sc-menu-item');
    if (link && typeof window.twBeforeHeaderNav === 'function') {
      window.twBeforeHeaderNav(link.getAttribute('data-key'));
    }
    if (e.target.closest('a.sc-menu-item, button.sc-menu-item')) close();
  });
}

// ══ Global Real-time Badge WebSocket ══
// Opens a WS on EVERY page using the authenticated viewer's ID (not profile owner).
// Handles badge_update events to update [data-badge="msgs"] in real time.
(function() {
  function _initBadgeWS() {
    var u = null;
    try { u = JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch(e){}
    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!u || !u.id || !jwt) return;

    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(protocol + '//' + window.location.host + '/ws/' + u.id);
    var retries = 0;

    ws.onmessage = function(e) {
      try {
        var data = JSON.parse(e.data);
        if (data.type === 'badge_update' && data.badge === 'messages') {
          var count = data.count || 0;
          document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
            el.textContent = count > 9 ? '9+' : String(count);
            el.style.display = count > 0 ? 'inline-block' : 'none';
          });
        }
      } catch(ex) {}
    };
    ws.onclose = function() {
      if (retries < 5) { retries++; setTimeout(_initBadgeWS, retries * 2000); }
    };
    ws.onerror = function() { ws.close(); };
  }

  // Run after load so localStorage is populated by page auth guards
  window.addEventListener('load', function() {
    setTimeout(_initBadgeWS, 200);
  });
})();


