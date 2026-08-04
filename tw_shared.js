
// ══ Auth Headers Helper ══
function getAuthHeaders(json){
  var jwt = localStorage.getItem('tw_jwt')||'';
  var h = {'Authorization':'Bearer '+jwt};
  if(json) h['Content-Type']='application/json';
  return h;
}

// ══ tw_shared.js - Shared Utilities ══
// تواصلنا - Shared JavaScript Utilities

// DS-FEEDBACK V1 — F34 · docs/design-system/FEEDBACK-SYSTEM.md
var _twTimer   = null;
var _twSurface = null;
var FBK_DURATION = { success: 2800, info: 3200, warning: 4000, error: 4500 };

function showToast(msg, type, _legacyDur) {
  if (msg == null) return;
  if (type !== 'success' && type !== 'error' && type !== 'warning' && type !== 'info') type = 'success';
  var dur = FBK_DURATION[type];   // centralized duration — _legacyDur ignored (FBK-07)

  clearTimeout(_twTimer);         // Latest Replaces Current (FBK-06)
  if (_twSurface) { _twSurface.remove(); _twSurface = null; }

  // DOM construction — textContent only, never innerHTML (FBK-21 XSS P0 fix)
  var surface = document.createElement('div');
  surface.className = 'tw-snackbar ' + type;
  surface.setAttribute('role', 'status');
  surface.setAttribute('aria-live', 'polite');
  surface.setAttribute('aria-atomic', 'true');
  var msgSpan = document.createElement('span');
  surface.appendChild(msgSpan);
  document.body.appendChild(surface);  // live region must be in DOM before content (FBK-12)
  _twSurface = surface;
  msgSpan.textContent = msg;            // content set AFTER DOM insertion — triggers announcement

  // Lifecycle: hidden → entering → visible (FBK-08)
  requestAnimationFrame(function() {
    requestAnimationFrame(function() { surface.classList.add('show'); });
  });

  // Lifecycle: visible → exiting → hidden (FBK-08)
  _twTimer = setTimeout(function() {
    surface.classList.remove('show');
    setTimeout(function() {   // DOM cleanup after 300ms CSS transition
      if (surface.parentNode) { surface.remove(); if (_twSurface === surface) _twSurface = null; }
    }, 350);
    setTimeout(function() {   // Stuck State Guard (FBK-08): force hidden after 1000ms
      if (surface.parentNode) { surface.remove(); if (_twSurface === surface) _twSurface = null; }
    }, 1000);
  }, dur);
}
window.showToast = showToast;

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

// ══ API-MUT Error Normalizer (System Gap fill — API-MUT-11) ══
// Contract (permanent — PR #523):
//   Input:  raw JSON body from any profile API response (may be null/undefined)
//   Output: { fieldErrors: [{field, code, message}], generalError: {code, message} | null }
//   Rules:
//     1. body.errors[] (field-specific) is consumed first — each entry with .field → fieldErrors
//     2. body.error{} (general) is only consumed if fieldErrors.length === 0 AND no generalError yet
//        (Separation of shapes: field-specific shape NEVER coexists with body.error{})
//     3. body.detail → legacy FastAPI backward compat (only when both official shapes absent)
//     4. Unknown/null body → generalError.message = 'حدث خطأ، حاول مجدداً' (F9 — no silent failure)
//   Consumers: profile-v2.edit.js save handler → _routeFieldError() per fieldError
//   DO NOT call fetch('/profile') directly — use tw_shared.js exports only
function normalizeErrorResponse(body) {
  if (!body) return { fieldErrors: [], generalError: { code: 'unknown', message: 'حدث خطأ، حاول مجدداً' } };
  var fieldErrors = [];
  var generalError = null;
  // Official field-specific shape: body.errors[]
  if (Array.isArray(body.errors)) {
    for (var i = 0; i < body.errors.length; i++) {
      var e = body.errors[i];
      if (e && e.field) {
        fieldErrors.push({ field: e.field, code: e.code || '', message: e.message || '' });
      } else if (e && e.code && !generalError) {
        // entry in errors[] with no field → treat as general
        generalError = { code: e.code, message: e.message || '' };
      }
    }
  }
  // Official general shape: body.error{} — only when no field errors (separate shapes per API-MUT)
  if (!fieldErrors.length && !generalError && body.error && typeof body.error === 'object' && body.error.code) {
    generalError = { code: body.error.code, message: body.error.message || '' };
  }
  // Legacy FastAPI detail (backward compat — only when official shapes absent)
  if (!fieldErrors.length && !generalError) {
    var det = body.detail;
    if (det && typeof det === 'object') {
      if (det.field || det.code) {
        fieldErrors.push({ field: det.field || '', code: det.code || '', message: det.error || det.message || '' });
      } else if (typeof det === 'string') {
        generalError = { code: '', message: det };
      }
    } else if (typeof det === 'string') {
      generalError = { code: '', message: det };
    }
  }
  // Unknown shape fallback: caller always has something to display
  if (!fieldErrors.length && !generalError) {
    generalError = { code: 'unknown', message: 'حدث خطأ، حاول مجدداً' };
  }
  return { fieldErrors: fieldErrors, generalError: generalError };
}
window.normalizeErrorResponse = normalizeErrorResponse;

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
  try {
    Object.keys(localStorage)
      .filter(function(k){ return k.startsWith('tw_'); })
      .forEach(function(k){ localStorage.removeItem(k); });
  } catch(e){}
  window.location.href = '/login';
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
// Auth protocol: sends {"type":"auth","token":"..."} as the first message;
// only processes badge_update after server confirms with auth_ok.
(function() {
  var _gen = 0;      // increments on each _initBadgeWS call; stale loops self-cancel
  var _activeUid = 0;
  var _activeSocket = null;   // current active WS reference
  var _reconnectTimer = null; // active reconnect timer handle

  function _clearSocket() {
    _gen++;
    var sock = _activeSocket;
    _activeSocket = null;
    if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
    if (sock) { try { sock.close(); } catch(e) {} }
  }

  function _initBadgeWS() {
    var u = null;
    try { u = JSON.parse(localStorage.getItem('tw_user') || 'null'); } catch(e){}
    var jwt = localStorage.getItem('tw_jwt') || '';
    if (!u || !u.id || !jwt) return;

    _gen++;
    _activeUid = u.id;
    var capturedGen = _gen;
    var capturedUid = Number(u.id);

    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws;
    try { ws = new WebSocket(protocol + '//' + window.location.host + '/ws/' + u.id); } catch(e) { return; }
    _activeSocket = ws;
    var retries = 0;
    var wsReady = false;

    ws.onopen = function() {
      if (capturedGen !== _gen) { ws.close(); return; }
      wsReady = false;
      ws.send(JSON.stringify({type: 'auth', token: jwt}));
    };
    ws.onmessage = function(e) {
      // Stale-connection guard: superseded by newer login or _initBadgeWS call
      if (capturedGen !== _gen || capturedUid !== _activeUid) return;
      try {
        var data = JSON.parse(e.data);
        if (data.type === 'auth_ok') {
          // Validate server echoed the correct user_id
          if (Number(data.user_id) !== capturedUid) { ws.close(); return; }
          wsReady = true;
          return;
        }
        if (!wsReady) return;
        if (data.type === 'badge_update' && data.badge === 'messages') {
          var count = data.count || 0;
          document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
            el.textContent = count > 9 ? '9+' : String(count);
            el.style.display = count > 0 ? 'inline-block' : 'none';
          });
        }
      } catch(ex) {}
    };
    ws.onclose = function(event) {
      wsReady = false;
      if (ws === _activeSocket) _activeSocket = null;
      // Auth/Policy close codes (4001-4007) — do not reconnect
      if (event.code >= 4001 && event.code <= 4007) return;
      // Superseded by a newer session — do not reconnect
      if (capturedGen !== _gen) return;
      if (retries < 5) {
        retries++;
        var delay = Math.min(30000, Math.pow(2, retries) * 1000 + Math.floor(Math.random() * 1000));
        _reconnectTimer = setTimeout(_initBadgeWS, delay);
      }
    };
    ws.onerror = function() { ws.close(); };
  }

  // Run after load so localStorage is populated by page auth guards
  window.addEventListener('load', function() {
    setTimeout(_initBadgeWS, 200);
  });

  // TwAuthSync: close socket on logout or account-switch
  if (typeof TwAuthSync !== 'undefined' && TwAuthSync.onSessionChange) {
    TwAuthSync.onSessionChange(function(info) {
      _clearSocket();
      // Reinitialize only when a new JWT is present (account-switch); logout = stay disconnected
      if (info && info.jwt) {
        setTimeout(_initBadgeWS, 300);
      }
    });
  }
})();


