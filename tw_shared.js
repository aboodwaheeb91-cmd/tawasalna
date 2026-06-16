
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
// Each host page only needs a `.sc-menu-wrap > button#<btnId> + .sc-menu-dropdown#<ddId>`
// shell already in its HTML/CSS; this file owns the item list, icons, the
// current-page/disabled rule, and the open/close wiring.

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
    .catch(function() { showToast('تعذر نسخ الرابط', 'error'); });
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

// `currentPage`: 'messages' | 'profile' — marks the matching nav item as
// the current page (shown, but not a clickable link to itself).
function _twHeaderMenuItems(currentPage) {
  var u = getTwUser();
  return [
    { key: 'home', label: 'الرئيسية', href: twHomeHref(u),
      icon: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1V10"/>' },
    { key: 'profile', label: 'الملف الشخصي', href: u && u.tw_id ? '/u/' + u.tw_id : '/profile',
      current: currentPage === 'profile',
      icon: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>' },
    { key: 'messages', label: 'الرسائل', href: '/messages',
      current: currentPage === 'messages',
      icon: '<path d="M4 4h16v12H8l-4 4V4z"/>' },
    { key: 'notifications', label: 'الإشعارات', href: '/notifications',
      icon: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>' },
    { key: 'settings', label: 'الإعدادات', href: '/settings',
      icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
    { key: 'share', label: 'مشاركة الملف الشخصي', action: 'twShareProfile',
      icon: '<path d="M12 3v12"/><path d="M7 8l5-5 5 5"/><path d="M5 21h14"/>' },
    { key: 'copy-link', label: 'نسخ رابط الملف', action: 'twCopyProfileLink',
      icon: '<rect x="7" y="7" width="11" height="11" rx="2"/><path d="M4 14V5a2 2 0 0 1 2-2h9"/>' },
    { key: 'logout', label: 'تسجيل الخروج', action: 'twLogout', danger: true,
      icon: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>' }
  ];
}

function _twHeaderMenuItemHtml(item) {
  var svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    + 'stroke-linecap="round" stroke-linejoin="round" class="sc-svg-icon-sm" aria-hidden="true">' + item.icon + '</svg>';
  if (item.current) {
    return '<div class="sc-menu-item current" aria-current="page">' + svg + sanitize(item.label) + '</div>';
  }
  var cls = 'sc-menu-item' + (item.danger ? ' danger' : '');
  if (item.action) {
    return '<button type="button" class="' + cls + '" data-menu-action="' + item.action + '">' + svg + sanitize(item.label) + '</button>';
  }
  return '<a class="' + cls + '" href="' + item.href + '" data-key="' + item.key + '">' + svg + sanitize(item.label) + '</a>';
}

// Wires button#btnId (toggle) + #ddId (.sc-menu-dropdown, must already be
// inside a `.sc-menu-wrap` ancestor for outside-click + positioning to
// work) for one page. Renders the item list fresh on every open so the
// current-page user / route are always up to date.
// `currentPage` may be a plain string ('messages' | 'profile') or a
// function returning one — profile-showcase.html needs a function since it
// renders both the OWNER's own profile and other people's profiles, and
// only the former should disable the "الملف الشخصي" item; ownership
// (window._scViewerType) isn't known yet when the page wires its header,
// only later once profile data has loaded — so it must be read lazily,
// each time the menu is opened, not once at init time.
function initGlobalHeaderMenu(btnId, ddId, currentPage) {
  var btn = document.getElementById(btnId);
  var dd  = document.getElementById(ddId);
  if (!btn || !dd) return;
  var wrap = dd.closest('.sc-menu-wrap') || dd.parentElement;

  function render() {
    var cp = typeof currentPage === 'function' ? currentPage() : currentPage;
    dd.innerHTML = _twHeaderMenuItems(cp).map(_twHeaderMenuItemHtml).join('');
  }
  function close() { dd.classList.remove('open'); }

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
    // conversation inactive over the existing WS) before a menu link
    // navigates away — same hook every link goes through, so behavior is
    // consistent regardless of which item was clicked.
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


