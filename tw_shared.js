
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
//        — object with field/code → fieldErrors; object with message only → generalError (PR 1.6)
//     3b. body.error as a string (global handler shape) → generalError (PR 1.6)
//     3c. body.message (+ body.code) legacy shape → generalError; body.error{field} → fieldErrors (PR 3A)
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
    // API Contract (PR 3A): {ok:false, error:{code, message, field?}} — with field → fieldErrors
    if (body.error.field) fieldErrors.push({ field: body.error.field, code: body.error.code, message: body.error.message || '' });
    else generalError = { code: body.error.code, message: body.error.message || '' };
  }
  // Legacy FastAPI detail (backward compat — only when official shapes absent)
  if (!fieldErrors.length && !generalError) {
    var det = body.detail;
    if (det && typeof det === 'object') {
      if (det.field || det.code) {
        fieldErrors.push({ field: det.field || '', code: det.code || '', message: det.error || det.message || '' });
      } else if (typeof det.message === 'string' && det.message) {
        // dict detail without field (PR 1.6 handler: {error, detail:{status, message}})
        generalError = { code: '', message: det.message };
      }
    } else if (typeof det === 'string') {
      generalError = { code: '', message: det };
    }
  }
  // Global handler string shape {"error": "..."} (string HTTPException detail · 422 validation · 500 server error)
  if (!fieldErrors.length && !generalError && typeof body.error === 'string' && body.error) {
    generalError = { code: '', message: body.error };
  }
  // Legacy {ok:false, code, message} (API-MUT-11 {message} shape — e.g. 409 pipeline errors)
  if (!fieldErrors.length && !generalError && typeof body.message === 'string' && body.message) {
    generalError = { code: typeof body.code === 'string' ? body.code : '', message: body.message };
  }
  // Unknown shape fallback: caller always has something to display
  if (!fieldErrors.length && !generalError) {
    generalError = { code: 'unknown', message: 'حدث خطأ، حاول مجدداً' };
  }
  return { fieldErrors: fieldErrors, generalError: generalError };
}
window.normalizeErrorResponse = normalizeErrorResponse;

// ══ API Client — twApi (PR 3A · SYSTEMS_INDEX §45a · CLAUDE.md → API Client Rule) ══
// The ONE way a page calls the site API:  twApi(path, opts) → Promise<{ok, status, data, error, raw}>
//   opts: method ('GET') · body (object/array → JSON; string / FormData / Blob sent as is)
//         headers (merged last) · auth (default true → getAuthHeaders) · timeout (ms) · signal
//   ok     true only for HTTP 2xx and a body without ok:false / success:false
//   data   body.data when the body has it (API Contract {ok, data}), else the whole body (legacy shapes)
//   error  null on success, else normalizeErrorResponse(...) → {fieldErrors[], generalError}
//   raw    the parsed body as sent (extra fields: total / page / count …)
//   status HTTP status · 0 = no response (network / timeout / aborted)
// Never rejects: network failure / timeout → ok:false + Arabic generalError (code network / timeout).
// 401 on a request that carried the current user's JWT → TwAuthSync.invalidateSession('api_401')
// once (the JWT is cleared, so parallel 401s don't repeat it); twRequireAuth finishes the redirect.
var TW_API_TIMEOUT_MS = 20000;
var _twApi401Jwt = '';

function _twApiFail(status, code, message, raw) {
  return { ok: false, status: status, data: null, raw: raw === undefined ? null : raw,
           error: { fieldErrors: [], generalError: { code: code, message: message } } };
}

function _twApiJwt() {
  try { return localStorage.getItem('tw_jwt') || ''; } catch (e) { return ''; }
}

function twApi(path, opts) {
  opts = opts || {};
  return new Promise(function (resolve) {
    var useAuth = opts.auth !== false;
    var sentJwt = useAuth ? _twApiJwt() : '';
    var headers = useAuth ? getAuthHeaders(false) : {};
    var body = opts.body;
    if (body !== undefined && body !== null && typeof body === 'object'
        && !(typeof FormData !== 'undefined' && body instanceof FormData)
        && !(typeof Blob !== 'undefined' && body instanceof Blob)
        && !(typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams)) {
      try { body = JSON.stringify(body); }
      catch (e) { resolve(_twApiFail(0, 'client', 'حدث خطأ، حاول مجدداً')); return; }
      headers['Content-Type'] = 'application/json';
    } else if (typeof body === 'string') {
      headers['Content-Type'] = 'application/json';
    }
    if (opts.headers) for (var k in opts.headers) headers[k] = opts.headers[k];

    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timedOut = false;
    var ms = opts.timeout > 0 ? opts.timeout : TW_API_TIMEOUT_MS;
    var timer = ctrl ? setTimeout(function () { timedOut = true; ctrl.abort(); }, ms) : null;
    if (ctrl && opts.signal) {
      if (opts.signal.aborted) ctrl.abort();
      else opts.signal.addEventListener('abort', function () { ctrl.abort(); });
    }

    var init = { method: (opts.method || 'GET').toUpperCase(), headers: headers };
    if (body !== undefined && body !== null) init.body = body;
    if (ctrl) init.signal = ctrl.signal;

    fetch(path, init).then(function (r) {
      return r.text().then(function (txt) {
        clearTimeout(timer);
        var parsed = null;
        if (txt) { try { parsed = JSON.parse(txt); } catch (e) { parsed = null; } }
        if (r.status === 401 && sentJwt && sentJwt !== _twApi401Jwt && _twApiJwt() === sentJwt
            && window.TwAuthSync && typeof TwAuthSync.invalidateSession === 'function') {
          _twApi401Jwt = sentJwt;
          try { TwAuthSync.invalidateSession('api_401'); } catch (e) { console.warn('[twApi] invalidateSession failed:', e); }
        }
        var isObj = parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed);
        var ok = r.ok && !(isObj && (parsed.ok === false || parsed.success === false));
        if (ok) {
          resolve({ ok: true, status: r.status, raw: parsed,
                    data: (isObj && Object.prototype.hasOwnProperty.call(parsed, 'data')) ? parsed.data : parsed,
                    error: null });
        } else {
          resolve({ ok: false, status: r.status, data: null, raw: parsed,
                    error: normalizeErrorResponse(isObj ? parsed : null) });
        }
      });
    }).catch(function () {
      clearTimeout(timer);
      if (timedOut) resolve(_twApiFail(0, 'timeout', 'انتهت مهلة الاتصال بالخادم، حاول مرة أخرى'));
      else if (opts.signal && opts.signal.aborted) resolve(_twApiFail(0, 'aborted', 'تم إلغاء الطلب'));
      else resolve(_twApiFail(0, 'network', 'تعذّر الاتصال بالخادم، تحقق من اتصالك بالإنترنت وحاول مرة أخرى'));
    });
  });
}
window.twApi = twApi;

// twApiMessage(res, fallback) → the text to show for a failed twApi result: first field
// error, else the general error (not the generic 'unknown' one), else fallback.
function twApiMessage(res, fallback) {
  var err = res && res.error;
  if (err && err.fieldErrors && err.fieldErrors.length && err.fieldErrors[0].message) return err.fieldErrors[0].message;
  var g = err && err.generalError;
  return (g && g.code !== 'unknown' && g.message) || fallback || 'حدث خطأ، حاول مجدداً';
}
window.twApiMessage = twApiMessage;

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

// Page fade-in removed (PR 2C): <html> was hidden until window.load (all images /
// fonts / logo), and pages already painted by the Page Shell flashed out. Pages
// render as soon as they parse; skeletons cover the loading state.

// Service Worker — not on pages served with the admin Page Shell
// (<meta name="tw-sw" content="off"> — PAGE-SHELL.md SHELL-03).
if ('serviceWorker' in navigator && !document.querySelector('meta[name="tw-sw"][content="off"]')) {
  window.addEventListener('load', function(){
    navigator.serviceWorker.register('/sw.js').catch(function(){});
  });
}

// Clears every Cache Storage entry for this origin — the single cache-wipe
// helper on session end (called by TwAuthSync.invalidateSession() and the
// twLogout() fallback). Best-effort and fire-and-forget: never delays a redirect.
function twClearAppCaches() {
  try {
    if (typeof caches === 'undefined' || !caches || typeof caches.keys !== 'function') {
      return Promise.resolve();
    }
    return caches.keys().then(function(keys){
      return Promise.all(keys.map(function(k){ return caches.delete(k); }));
    }).catch(function(err){
      console.warn('[twClearAppCaches] cache clear failed:', err);
    });
  } catch (err) {
    console.warn('[twClearAppCaches] cache clear failed:', err);
    return Promise.resolve();
  }
}
window.twClearAppCaches = twClearAppCaches;
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

// ── Strings System (PR 3.6 · SYSTEMS_INDEX §59 · docs/GLOSSARY.md) ──
// twT(key, vars): the ONLY way UI text reaches the page. Dictionary = window.TW_STRINGS.dict,
// put inline at <!--tw:strings--> by read_html (tw_strings.json defaults + admin overrides from
// site_settings). {name} → vars.name (unknown {x} stays as is). Missing key → returns the key
// and warns once per key. Result is plain text — escape it like any other text (twEscHtml).
var _twTWarned = {};
function twT(key, vars) {
  var S = window.TW_STRINGS;
  var d = S && S.dict;
  var s = d && Object.prototype.hasOwnProperty.call(d, key) ? d[key] : null;
  if (typeof s !== 'string') {
    if (!_twTWarned[key]) { _twTWarned[key] = 1; console.warn('[twT] missing string key: ' + key); }
    return String(key);
  }
  if (!vars) return s;
  return s.replace(/\{([a-z0-9_]+)\}/g, function (m, n) {
    return Object.prototype.hasOwnProperty.call(vars, n) && vars[n] != null ? String(vars[n]) : m;
  });
}
window.twT = twT;

// Static HTML: <el data-tw-t="key"> → textContent · <el data-tw-t-label="key"> → aria-label + title.
// Runs once on DOMContentLoaded for the document; call again for markup added later.
function twTApply(root) {
  root = root || (typeof document !== 'undefined' ? document : null);
  if (!root || typeof root.querySelectorAll !== 'function') return;
  root.querySelectorAll('[data-tw-t]').forEach(function (el) { el.textContent = twT(el.getAttribute('data-tw-t')); });
  root.querySelectorAll('[data-tw-t-label]').forEach(function (el) {
    var t = twT(el.getAttribute('data-tw-t-label'));
    el.setAttribute('aria-label', t);
    el.setAttribute('title', t);
  });
}
window.twTApply = twTApply;

// ── XSS Protection (§54 Safe Rendering — single canonical implementation) ──
// twEscAttr: canonical escaping for attribute values and text content.
// Handles null/undefined → ''; handles numeric 0 → "0" (correct; old sanitize returned '').
function twEscAttr(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}
window.twEscAttr = twEscAttr;

// twEscHtml: alias — attr escaping is a safe superset of text-content escaping.
function twEscHtml(v) { return twEscAttr(v); }
window.twEscHtml = twEscHtml;

// twSafeImageUrl: the ONLY image-URL check (§54 rule 4 · DS-IMAGE IMG-08).
// Accepts https:// or a root-relative path ("/x" — not "//x" and not "/\x").
// Anything else (javascript:, data:, vbscript:, http:, blob:, leading space…) → ''.
function twSafeImageUrl(url) {
  if (typeof url !== 'string' || !url) return '';
  return /^(https:\/\/|\/(?![\/\\]))/i.test(url) ? url : '';
}
window.twSafeImageUrl = twSafeImageUrl;

// twSafeLinkUrl: the ONLY check for a user-entered external link shown in href (§54 rule 4b).
// Accepts http:// or https:// followed by a host char; no whitespace / control char anywhere.
// Anything else (javascript:, data:, vbscript:, //x, /path, leading space…) → '' →
// the caller renders the URL as plain text (no <a>). Backend twin: _validate_external_url.
function twSafeLinkUrl(url) {
  if (typeof url !== 'string' || !url || url.length > 2048) return '';
  if (/[\u0000-\u0020\u007f-\u009f\u2028\u2029]/.test(url)) return '';
  return /^https?:\/\/[^\/\\]/i.test(url) ? url : '';
}
window.twSafeLinkUrl = twSafeLinkUrl;

// twCssUrl: CSS url("…") for background-image — validated + CSS-string escaped.
// Invalid URL → '' (caller keeps its default background).
function twCssUrl(url) {
  var u = twSafeImageUrl(url);
  if (!u) return '';
  return 'url("' + u.replace(/[\\"\n\r\f]/g, function(c) {
    return '\\' + c.charCodeAt(0).toString(16) + ' ';
  }) + '")';
}
window.twCssUrl = twCssUrl;

// ══ DS-IMAGE — Avatar / Logo (F38 · docs/design-system/IMAGE-SYSTEM.md) ══
// twAvatarHtml(entity, size, opts) → string · twAvatarEl(entity, size, opts) → element.
// entity: { full_name, avatar_url, user_type } · size: md | lg | xl | 2xl · opts.eager (hero).
// Both build from _twAvatarSpec — one source for classes, URL check and fallback letter.
var _TW_AVA_PX = { md: 40, lg: 48, xl: 88, '2xl': 106 };

function _twAvatarSpec(entity, size, opts) {
  var e = entity || {};
  var t = (e.user_type === 'co' || e.user_type === 'edu') ? e.user_type : 'emp';
  var s = Object.prototype.hasOwnProperty.call(_TW_AVA_PX, size) ? size : 'md';
  var name = typeof e.full_name === 'string' ? e.full_name.trim() : '';
  return {
    type: t,
    size: s,
    px: _TW_AVA_PX[s],
    cls: 'tw-ava tw-ava--' + s + ' tw-ava--' + (t === 'emp' ? 'emp' : 'org'),
    src: twSafeImageUrl(e.avatar_url),
    letter: name ? Array.from(name)[0] : '؟',
    loading: (opts && opts.eager) ? 'eager' : 'lazy',
  };
}

function twAvatarHtml(entity, size, opts) {
  var p = _twAvatarSpec(entity, size, opts);
  var img = p.src
    ? '<img src="' + twEscAttr(p.src) + '" alt="" decoding="async" loading="' + p.loading
      + '" width="' + p.px + '" height="' + p.px + '">'
    : '';
  return '<span class="' + p.cls + '" data-tw-ava="' + p.type + '"' + (p.src ? '' : ' data-fb="1"') + '>'
    + img + '<span class="tw-ava__fb" aria-hidden="true">' + twEscHtml(p.letter) + '</span></span>';
}
window.twAvatarHtml = twAvatarHtml;

function twAvatarEl(entity, size, opts) {
  var p = _twAvatarSpec(entity, size, opts);
  var root = document.createElement('span');
  root.className = p.cls;
  root.setAttribute('data-tw-ava', p.type);
  if (p.src) {
    var img = document.createElement('img');
    img.setAttribute('alt', '');
    img.setAttribute('decoding', 'async');
    img.setAttribute('loading', p.loading);
    img.setAttribute('width', String(p.px));
    img.setAttribute('height', String(p.px));
    img.setAttribute('src', p.src);
    root.appendChild(img);
  } else {
    root.setAttribute('data-fb', '1');
  }
  var fb = document.createElement('span');
  fb.className = 'tw-ava__fb';
  fb.setAttribute('aria-hidden', 'true');
  fb.textContent = p.letter;
  root.appendChild(fb);
  return root;
}
window.twAvatarEl = twAvatarEl;

// One capture listener for every avatar: image error (does not bubble) → fallback letter.
// No inline onerror anywhere (IMG-07).
document.addEventListener('error', function(e) {
  var t = e.target;
  if (!t || t.tagName !== 'IMG' || !t.parentNode) return;
  var host = t.parentNode;
  if (host.hasAttribute && host.hasAttribute('data-tw-ava')) host.setAttribute('data-fb', '1');
}, true);

// Safe text setter
function safeText(el, text){
  if(!el) return;
  el.textContent = text || '';
}

// ══ Global Badge Loader ══
// Populates all elements with data-badge="msgs", data-badge="notif", data-ah-notif-badge.
// Call once after page init from any authenticated page.
// Requires TwAuthSync (VM-10A contract) — no raw localStorage fallback.
// 401 → session invalid (invalidateSession) + cancel sibling request.
// 403/5xx/network → preserve session.
// _badgeGeneration: prevents stale HTTP responses from a prior account overwriting
// the current account's badge counts after a cross-tab or within-tab account switch.
var _badgeGeneration = 0;

// twNotifBadgeLabel: the ONLY cap rule for BOTH header badges — notifications and messages
// (§52 · HEADER-NAV.md HNAV-05) — 1..99 → "N", > 99 → "99+".
function twNotifBadgeLabel(count) {
  var n = Number(count) || 0;
  return n > 99 ? '99+' : String(n);
}
window.twNotifBadgeLabel = twNotifBadgeLabel;

function loadGlobalBadges() {
  // TwAuthSync is mandatory — never fall back to raw localStorage
  if (!window.TwAuthSync) return;
  var snap = TwAuthSync.getSessionSnapshot();
  if (!snap.isAuthenticated) return;
  var userId = snap.userId;
  var jwt    = localStorage.getItem('tw_jwt') || '';
  if (!userId || !jwt) return;

  // Clear badges before fetching — prevents stale counts from previous account
  // Includes [data-ah-notif-badge] (legacy selector used by some pages)
  document.querySelectorAll('[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]').forEach(function(el) {
    el.textContent = '';
    el.style.display = 'none';
  });

  var gen            = ++_badgeGeneration;   // capture generation
  var capturedUserId = Number(userId);       // capture userId for account-switch guard

  // Triple guard: generation, userId, and still authenticated.
  // Generation alone can't detect an account switch that happened to reuse the same
  // _badgeGeneration slot (e.g. rapid logout+login).
  function _guardOk() {
    if (gen !== _badgeGeneration) return false;
    if (!window.TwAuthSync) return false;
    var s = TwAuthSync.getSessionSnapshot();
    return s.isAuthenticated && Number(s.userId) === capturedUserId;
  }

  // On 401: bump _badgeGeneration to cancel any other in-flight request from this batch,
  // then invalidate the session via TwAuthSync.
  function _on401() {
    _badgeGeneration++;   // makes _guardOk() false for the sibling fetch as well
    if (window.TwAuthSync && typeof TwAuthSync.invalidateSession === 'function') {
      TwAuthSync.invalidateSession('api_401');
    }
  }

  fetch('/notifications/' + userId, { headers: { 'Authorization': 'Bearer ' + jwt } })
    .then(function(r) {
      if (r.status === 401) { _on401(); return null; }
      // 403 = authenticated but not authorised — preserve session
      // 5xx / network error — preserve session (handled by .catch)
      return r.ok ? r.json() : null;
    })
    .then(function(d) {
      if (!d || !_guardOk()) return;
      var count = d.unread || 0;
      // Write to both selectors (data-badge="notif" and legacy data-ah-notif-badge)
      document.querySelectorAll('[data-badge="notif"],[data-ah-notif-badge]').forEach(function(el) {
        el.textContent = twNotifBadgeLabel(count);
        el.style.display = count > 0 ? 'inline-block' : 'none';
      });
    }).catch(function() {});

  fetch('/messages/unread/' + userId, { headers: { 'Authorization': 'Bearer ' + jwt } })
    .then(function(r) {
      if (r.status === 401) { _on401(); return null; }
      // 403 = authenticated but not authorised — preserve session
      return r.ok ? r.json() : null;
    })
    .then(function(d) {
      if (!d || !_guardOk()) return;
      var count = d.count || 0;
      document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
        el.textContent = twNotifBadgeLabel(count);
        el.style.display = count > 0 ? 'inline-block' : 'none';
      });
    }).catch(function() {});
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

// "Home" (feed/dashboard) destination — single source of truth for header
// home buttons. Home V2 (/home) renders a view per account type (emp/co/edu,
// static/home/home.nav.js), so every logged-in account goes to /home.
function twHomeHref(u) {
  u = u || getTwUser();
  if (!u) return '/';
  return '/home';
}

// "My account" destination — single source of truth for post-login /
// logged-in entry routing (redirect(u) in index.auth.js + landing.html).
// Distinct from twHomeHref() above, which is the type-aware feed/dashboard.
// Account with tw_id → /u/{tw_id} (Smart Router, all user types); else /login.
function twAccountHref(u) {
  return (u && u.tw_id) ? '/u/' + encodeURIComponent(u.tw_id) : '/login';
}

// Talent Bank (بنك المواهب) destination for a company account — the candidates
// modal inside its own company page, opened by the ?cand deep-link
// (company.main.js). Empty ?cand= opens the bank without a selected candidate.
// Company without tw_id → /company-profile (legacy redirect resolves it).
function twTalentBankHref(u) {
  u = u || getTwUser();
  return (u && u.tw_id) ? '/u/' + encodeURIComponent(u.tw_id) + '?cand=' : '/company-profile';
}

// Entry-page session gate (landing.html + Auth Gateway on-load/bfcache check).
// Decides from TwAuthSync.getSessionSnapshot() only — never from tw_user alone.
//   authenticated               → returns twAccountHref(tw_user) (caller redirects)
//   expired / stale / invalid   → TwAuthSync.invalidateSession('stale_entry'), no redirect → null
//   guest / no TwAuthSync       → null (fail-closed: no redirect)
// Never returns '/login' — an entry page must not redirect to the login page.
function twEntryDestination() {
  if (!window.TwAuthSync || typeof TwAuthSync.getSessionSnapshot !== 'function') return null;
  var snap = TwAuthSync.getSessionSnapshot();
  if (snap && snap.isAuthenticated) {
    var dest = twAccountHref(getTwUser());
    return dest === '/login' ? null : dest;
  }
  if (snap && snap.state !== 'guest' && typeof TwAuthSync.invalidateSession === 'function') {
    TwAuthSync.invalidateSession('stale_entry');
  }
  return null;
}

// ══ Auth Return Destination — ?next= (NAV-07 · Auth Gateway rule 13) ══
// twSafeNext(next) → next when it is an internal path, else '' (open-redirect guard).
// Internal = one leading "/" (not "//", not "/\"), no backslash / whitespace / control
// character anywhere (the URL parser drops tabs/newlines: "/\t/evil.com" → "//evil.com"),
// at most 512 chars, and not /login itself (no login loop). Scheme / host can't appear:
// "https://…", "javascript:…" and "//host" all fail the first rule.
var _TW_NEXT_MAX = 512;
function twSafeNext(next) {
  if (typeof next !== 'string' || !next || next.length > _TW_NEXT_MAX) return '';
  if (!/^\/(?![\/\\])/.test(next)) return '';
  if (/[\\\s\u0000-\u001f\u007f]/.test(next)) return '';
  if (/^\/login(?:[\/?#.]|$)/i.test(next)) return '';
  return next;
}
window.twSafeNext = twSafeNext;

// twLoginHref(next) → '/login?next=<encoded>' — the ONLY way a page sends a visitor to the
// login page with a way back. Unsafe / empty next → plain '/login'.
function twLoginHref(next) {
  var n = twSafeNext(next);
  return n ? '/login?next=' + encodeURIComponent(n) : '/login';
}
window.twLoginHref = twLoginHref;

// ══ Protected Page Guard — twRequireAuth (PAGE-SHELL.md SHELL-09 · Auth Gateway rule 14) ══
// The ONE guard for pages that need a session (<meta name="tw-page" content="auth">).
// Called once, first thing in the page script:  var snap = twRequireAuth(); if (!snap) return;
// Decides from TwAuthSync.getSessionSnapshot() only (never tw_user / tw_jwt directly):
//   guest / expired / stale / invalid / no TwAuthSync → location.replace(twLoginHref(path + query)) → null
//   opts.userTypes given and the account type is not in it → location.replace(twAccountHref(u)) → null
//   authenticated                                        → the snapshot
// Same decision again on every TwAuthSync.onSessionChange (logout / expiry in another tab,
// bfcache restore — VM-01: no own pageshow / storage listener). Another account signed in
// (userId changed) → reload so the page never shows account A's data to account B.
// One onSessionChange registration per page (a second call does not register again).
var _twGuardBound   = false;
var _twGuardLeaving = false;

function _twGuardDestination(snap, types) {
  if (!snap || !snap.isAuthenticated) return twLoginHref(location.pathname + location.search);
  if (types && types.indexOf(snap.userType) === -1) return twAccountHref(getTwUser());
  return null;
}

function _twGuardLeave(dest) {
  if (_twGuardLeaving) return;
  _twGuardLeaving = true;
  if (dest) location.replace(dest);
  else location.reload();
}

function twRequireAuth(opts) {
  var types = (opts && Array.isArray(opts.userTypes) && opts.userTypes.length) ? opts.userTypes.slice() : null;
  var sync  = (window.TwAuthSync && typeof TwAuthSync.getSessionSnapshot === 'function') ? TwAuthSync : null;
  var snap  = sync ? sync.getSessionSnapshot() : null;
  var dest  = _twGuardDestination(snap, types);
  if (dest) { _twGuardLeave(dest); return null; }
  if (!_twGuardBound && typeof sync.onSessionChange === 'function') {
    _twGuardBound = true;
    var boundUserId = Number(snap.userId);
    sync.onSessionChange(function (info) {
      var s = (info && info.snapshot) || sync.getSessionSnapshot();
      var d = _twGuardDestination(s, types);
      if (d) { _twGuardLeave(d); return; }
      if (Number(s.userId) !== boundUserId) _twGuardLeave(null);
    });
  }
  return snap;
}
window.twRequireAuth = twRequireAuth;

function twLogout() {
  if (window.TwAuthSync && typeof TwAuthSync.invalidateSession === 'function') {
    TwAuthSync.invalidateSession('logout', { redirect: '/login' });
  } else {
    // Allowlist only — never startsWith('tw_') which would delete user preferences
    var _LOGOUT_KEYS = ['tw_jwt', 'tw_user'];
    try {
      for (var _li = 0; _li < _LOGOUT_KEYS.length; _li++) {
        localStorage.removeItem(_LOGOUT_KEYS[_li]);
      }
    } catch(e){}
    twClearAppCaches();
    window.location.href = '/login';
  }
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

// ── Central Header Menu Policy Registry (VM-10B) ──────────────────
// Single source of truth for all header menu items.
// show: 'all' | 'auth' | 'guest'
// accountTypes: optional string[] — if set, item only shows for those user types.
// Items with show:'auth' appear only when session is authenticated.
// Items with show:'guest' appear only when session is guest/expired/invalid.
// Items with disabled:true are shown greyed with twT('common.soon') — no route yet.
// labelKey = Strings System key (twT) — no fixed text here.
var _TW_HEADER_MENU_POLICY = [
  { key: 'settings', labelKey: 'menu.settings', href: '/settings', show: 'auth',
    icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
  { key: 'candidates', labelKey: 'people.talent_bank', href: twTalentBankHref, show: 'auth',
    accountTypes: ['co'],
    icon: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>' },
  { key: 'contact', labelKey: 'menu.contact', disabled: true, show: 'all',
    icon: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 12 19.79 19.79 0 0 1 1.06 3.31 2 2 0 0 1 3 1h2.09a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9a16 16 0 0 0 5.9 5.9l1.36-1.36a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 20 16z"/>' },
  { key: 'report', labelKey: 'menu.report', disabled: true, show: 'all',
    icon: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>' },
  { key: 'suggest', labelKey: 'menu.suggest', disabled: true, show: 'all',
    icon: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
  { key: 'logout', labelKey: 'auth.logout', action: 'twLogout', danger: true, show: 'auth',
    icon: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>' },
  { key: 'login', labelKey: 'auth.login', href: '/login', show: 'guest',
    icon: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>' },
  { key: 'register', labelKey: 'auth.register', href: '/login#register', show: 'guest',
    icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>' },
];

// Filter policy items for a given session snapshot (VM-10B)
// Applies both show: and accountTypes: filters.
function _twMenuItemsForSnapshot(snapshot) {
  var auth  = snapshot && snapshot.isAuthenticated;
  var utype = snapshot && snapshot.userType;
  return _TW_HEADER_MENU_POLICY.filter(function (item) {
    if (item.show === 'all')   return true;
    if (item.show === 'auth') {
      if (!auth) return false;
      // accountTypes filter: if specified, only show for those user types
      if (item.accountTypes) {
        return item.accountTypes.indexOf(utype) !== -1;
      }
      return true;
    }
    if (item.show === 'guest') return !auth;
    return true;
  });
}

// Secondary-tools menu items — delegates to policy for current session state.
// Legacy callers that use _twHeaderMenuItems() still work.
function _twHeaderMenuItems() {
  var snapshot = window.TwAuthSync
    ? TwAuthSync.getSessionSnapshot()
    : { state: 'guest', isAuthenticated: false };
  return _twMenuItemsForSnapshot(snapshot);
}

function _twHeaderMenuItemHtml(item) {
  var svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    + 'stroke-linecap="round" stroke-linejoin="round" class="sc-svg-icon-sm" aria-hidden="true">' + item.icon + '</svg>';
  var label = twEscHtml(twT(item.labelKey));
  if (item.disabled) {
    var soon = twEscHtml(twT('common.soon'));
    return '<div class="sc-menu-item disabled" title="' + soon + '">'
      + svg + label
      + '<span class="sc-menu-soon">' + soon + '</span></div>';
  }
  var cls = 'sc-menu-item' + (item.danger ? ' danger' : '');
  if (item.action) {
    return '<button type="button" class="' + cls + '" data-menu-action="' + item.action + '">' + svg + label + '</button>';
  }
  var href = typeof item.href === 'function' ? item.href() : item.href;
  return '<a class="' + cls + '" href="' + twEscAttr(href) + '" data-key="' + item.key + '">' + svg + label + '</a>';
}

// ── Declarative Session Visibility (VM-10D) ──────────────────────
// Processes all elements with data-tw-session="authenticated|guest|all"
// and sets/clears the `hidden` attribute based on current session state.
// Called once on initGlobalHeaderMenu() and on every session change.
function _twApplyDeclarativeVisibility() {
  var snapshot = window.TwAuthSync
    ? TwAuthSync.getSessionSnapshot()
    : { state: 'guest', isAuthenticated: false, userType: null };
  var auth = snapshot.isAuthenticated;
  var utype = snapshot.userType;
  document.querySelectorAll('[data-tw-session]').forEach(function (el) {
    var req   = el.getAttribute('data-tw-session');
    var types = el.getAttribute('data-tw-account-types');
    var show  = false;
    if      (req === 'all')           show = true;
    else if (req === 'authenticated') {
      show = auth;
      if (show && types) {
        var arr = types.split(',').map(function (t) { return t.trim(); });
        show = arr.indexOf(utype) !== -1;
      }
    }
    else if (req === 'guest')         show = !auth;
    el.hidden = !show;
  });
}

// ── Idempotent Global Header Menu (VM-10C) ────────────────────────
// Wires button#btnId (toggle) + #ddId (.sc-menu-dropdown, must already be
// inside a `.sc-menu-wrap` ancestor for outside-click + positioning).
// Idempotent: a second call for the same btnId is silently ignored.
// `dynId` (optional): inner container for dynamic items — use when the
// dropdown has a static section above (e.g. the eye-preview block in
// profile-showcase.html); tw_shared.js only regenerates the sibling container.
// Auto-rerenders on session change via a single global TwAuthSync listener.
var _ghInstances = [];
var _ghListenerRegistered = false;

function initGlobalHeaderMenu(btnId, ddId, dynId) {
  // Idempotency guard — one wiring per button
  for (var i = 0; i < _ghInstances.length; i++) {
    if (_ghInstances[i].btnId === btnId) return;
  }

  var btn = document.getElementById(btnId);
  var dd  = document.getElementById(ddId);
  if (!btn || !dd) return;

  var instance = { btnId: btnId, ddId: ddId, dynId: dynId || null };
  _ghInstances.push(instance);

  var dyn  = dynId ? (document.getElementById(dynId) || dd) : dd;
  var wrap = dd.closest('.sc-menu-wrap') || dd.parentElement;

  function _renderInstance(inst) {
    var dynEl = inst.dynId
      ? (document.getElementById(inst.dynId) || document.getElementById(inst.ddId))
      : document.getElementById(inst.ddId);
    if (!dynEl) return;
    var snapshot = window.TwAuthSync
      ? TwAuthSync.getSessionSnapshot()
      : { state: 'guest', isAuthenticated: false };
    dynEl.innerHTML = _twMenuItemsForSnapshot(snapshot).map(_twHeaderMenuItemHtml).join('');
  }

  function render() { _renderInstance(instance); }

  function close() {
    dd.classList.remove('open');
    var em = document.getElementById('scEyeMenu');
    if (em) em.classList.remove('open');
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (!dd.classList.contains('open')) render();
    dd.classList.toggle('open');
  });
  document.addEventListener('click', function (e) {
    if (wrap && !wrap.contains(e.target)) close();
  });
  dd.addEventListener('click', function (e) {
    var actionEl = e.target.closest('[data-menu-action]');
    if (actionEl) {
      var fn = window[actionEl.getAttribute('data-menu-action')];
      if (typeof fn === 'function') fn();
    }
    // Allow host page to run cleanup before navigation (e.g. messages.html)
    var link = e.target.closest('a.sc-menu-item');
    if (link && typeof window.twBeforeHeaderNav === 'function') {
      window.twBeforeHeaderNav(link.getAttribute('data-key'));
    }
    if (e.target.closest('a.sc-menu-item, button.sc-menu-item')) close();
  });

  // Register one global TwAuthSync listener for ALL instances (once per page)
  if (!_ghListenerRegistered && window.TwAuthSync) {
    _ghListenerRegistered = true;
    TwAuthSync.onSessionChange(function () {
      for (var j = 0; j < _ghInstances.length; j++) {
        _renderInstance(_ghInstances[j]);
      }
      _twApplyDeclarativeVisibility();
    });
  }

  // Apply declarative visibility and pre-render on first call
  _twApplyDeclarativeVisibility();
}

// ══ App Header + Bottom Nav — ONE header for the whole site (docs/design-system/HEADER-NAV.md) ══
// A page declares placeholders; this file renders them once at DOMContentLoaded:
//   <header data-tw-header [data-back="home|account|/internal/path"]></header>   (first child of <body>)
//   <nav data-tw-bottom-nav [data-tw-current="home|appointments|messages|notifications|account"]></nav>
// Header order (HNAV-02): authenticated → [back?] home · logo · bell · messages · menu
//                         guest         → [back?] · logo · login · register
// Both groups are in the DOM; data-tw-session + _twApplyDeclarativeVisibility (VM-10) pick one.
// Icons: twIcon (DS-ICON registry — loaded by the page, never by this file). Logo: /static/33333.svg only (HNAV-04).
// Badges: [data-badge="notif"] / [data-badge="msgs"] filled by loadGlobalBadges + Badge WS,
// one cap rule twNotifBadgeLabel (99+) for both (HNAV-05). Menu: initGlobalHeaderMenu (VM-10).
var TW_LOGO_SRC = '/static/33333.svg';

// Bottom nav registry (HNAV-06) — the ONE definition per account type. Every item has a real
// href (never "#"). labelKey (twT) / icon may be a {emp, co, edu} map; types (optional) limits an item.
var _TW_BOTTOM_NAV = [
  { key: 'home',          labelKey: 'nav.home',          icon: 'home',          href: function (u) { return twHomeHref(u); } },
  { key: 'appointments',  labelKey: 'nav.appointments',  icon: 'calendar',      href: '/appointments' },
  { key: 'messages',      labelKey: 'nav.messages',      icon: 'messages',      href: '/messages' },
  { key: 'notifications', labelKey: 'nav.notifications', icon: 'notifications', href: '/notifications' },
  { key: 'account',
    labelKey: { emp: 'nav.account.emp', co: 'nav.account.co', edu: 'nav.account.edu' },
    icon:  { emp: 'user', co: 'briefcase', edu: 'graduation-cap' },
    href:  function (u) { return twAccountHref(u); } },
];

function _twPick(v, type) { return (v && typeof v === 'object') ? (v[type] || v.emp) : v; }

// Resolved items for one account type → [{key, label, icon, href}] (no "#", no empty href).
function twBottomNavItems(userType, u) {
  var type = (userType === 'co' || userType === 'edu') ? userType : 'emp';
  return _TW_BOTTOM_NAV.filter(function (it) {
    return !it.types || it.types.indexOf(type) !== -1;
  }).map(function (it) {
    var href = typeof it.href === 'function' ? it.href(u) : it.href;
    return { key: it.key, label: twT(_twPick(it.labelKey, type)), icon: _twPick(it.icon, type), href: href || '/' };
  });
}
window.twBottomNavItems = twBottomNavItems;

// Current tab: data-tw-current on the placeholder wins, else the path.
function _twNavCurrentKey(el, u) {
  var k = el && el.getAttribute('data-tw-current');
  if (k) return k;
  var p = location.pathname.replace(/\/+$/, '') || '/';
  if (p === '/home' || p === '/appointments' || p === '/messages' || p === '/notifications') return p.slice(1);
  if (u && u.tw_id && p === '/u/' + u.tw_id) return 'account';
  return '';
}

function _twIco(name, size) {
  return typeof window.twIcon === 'function' ? window.twIcon(name, { size: size }) : '';
}

// Back destination when there is no trusted in-site history (NAV-05 step 4/5 · NAV-06).
function _twBackFallback(v) {
  if (v === 'account') {
    var d = twAccountHref(getTwUser());
    return d === '/login' ? twHomeHref() : d;
  }
  var safe = v && v !== 'home' ? twSafeNext(v) : '';
  return safe || twHomeHref();
}

// Interceptable Back (NAV-05): pushed in-site entry → history.back(); trusted context.from →
// go there; otherwise the page fallback. Never a bare history.back() (deep link would leave the site).
function twNavBack(fallback) {
  var nav = (history.state && history.state.nav) || null;
  if (nav && nav.entryType === 'push') { history.back(); return; }
  var from = nav && nav.context && twSafeNext(nav.context.from);
  if (from && from.indexOf('/login') !== 0) { location.href = from; return; }
  location.href = fallback || twHomeHref();
}
window.twNavBack = twNavBack;

// aria-label + title from one twT key (icon-only buttons).
function _twLbl(key) {
  var t = twEscAttr(twT(key));
  return ' aria-label="' + t + '" title="' + t + '"';
}

function _twHeaderHtml(hdr, current) {
  var back = hdr.hasAttribute('data-back')
    ? '<button type="button" class="sc-hicon sc-hicon-bare tw-hdr-back" data-tw-hdr-back' + _twLbl('header.back') + '>'
      + _twIco('back', 'xl') + '</button>' : '';
  function cur(key) { return key === current ? ' is-current" aria-current="page' : ''; }
  var login = twLoginHref(location.pathname + location.search);
  return ''
    + '<div class="sc-head-right">' + back
    +   '<a class="sc-hicon sc-home-btn' + cur('home') + '" href="' + twEscAttr(twHomeHref()) + '" data-key="home"'
    +   _twLbl('header.home') + ' data-tw-session="authenticated" hidden>' + _twIco('home', 'xl') + '</a>'
    + '</div>'
    + '<span class="sc-logo"><img src="' + TW_LOGO_SRC + '" alt="' + twEscAttr(twT('brand.name')) + '" width="120" height="32"></span>'
    + '<div class="sc-head-icons">'
    +   '<a class="sc-hicon sc-hicon-bare tw-hdr-ico' + cur('notifications') + '" href="/notifications" data-key="notifications"'
    +   _twLbl('header.notifications') + ' data-tw-session="authenticated" hidden>' + _twIco('notifications', 'xl')
    +   '<span class="tw-hdr-badge" data-badge="notif"></span></a>'
    +   '<a class="sc-hicon sc-hicon-bare tw-hdr-ico' + cur('messages') + '" href="/messages" data-key="messages"'
    +   _twLbl('header.messages') + ' data-tw-session="authenticated" hidden>' + _twIco('messages', 'xl')
    +   '<span class="tw-hdr-badge" data-badge="msgs"></span></a>'
    +   '<div class="sc-menu-wrap" data-tw-session="authenticated" hidden>'
    +     '<button type="button" class="sc-hicon sc-hicon-bare" id="twHdrMenuBtn"' + _twLbl('header.menu') + '>'
    +     _twIco('menu', 'xl') + '</button>'
    +     '<div class="sc-menu-dropdown" id="twHdrMenuDd"></div>'
    +   '</div>'
    +   '<a class="tw-hdr-auth" href="' + twEscAttr(login) + '" data-tw-session="guest" hidden>' + twEscHtml(twT('auth.login')) + '</a>'
    +   '<a class="tw-hdr-auth tw-hdr-auth--primary" href="/login#register" data-tw-session="guest" hidden>' + twEscHtml(twT('auth.register')) + '</a>'
    + '</div>';
}

function _twRenderBottomNav(nav) {
  var snap = window.TwAuthSync ? TwAuthSync.getSessionSnapshot() : null;
  var u    = getTwUser();
  var auth = !!(snap && snap.isAuthenticated);
  var key  = auth ? snap.userType + '|' + snap.userId + '|' + ((u && u.tw_id) || '') : 'guest';
  if (nav._twKey === key) return;
  nav._twKey = key;
  nav.hidden = !auth;
  document.body.classList.toggle('tw-has-bnav', auth);
  if (!auth) { nav.innerHTML = ''; return; }
  var current = _twNavCurrentKey(nav, u);
  nav.innerHTML = twBottomNavItems(snap.userType, u).map(function (it) {
    var on = it.key === current;
    return '<a class="tw-bnav-item' + (on ? ' is-current" aria-current="page' : '') + '" href="'
      + twEscAttr(it.href) + '" data-key="' + it.key + '">' + _twIco(it.icon, '2xl')
      + '<span>' + twEscHtml(it.label) + '</span></a>';
  }).join('');
}

// Links in the header / bottom nav run the page cleanup hook first (messages.html —
// same hook initGlobalHeaderMenu runs for menu links).
function _twChromeNavClick(e) {
  var a = e.target.closest('a[data-key]');
  if (!a || a.closest('.sc-menu-dropdown')) return;
  if (typeof window.twBeforeHeaderNav === 'function') window.twBeforeHeaderNav(a.getAttribute('data-key'));
}

var _twChromeBound = false;
function twMountAppChrome() {
  var hdr = document.querySelector('[data-tw-header]');
  var nav = document.querySelector('[data-tw-bottom-nav]');
  if (hdr && !hdr.hasAttribute('data-tw-mounted')) {
    hdr.setAttribute('data-tw-mounted', '');
    hdr.classList.add('sc-header', 'tw-hdr');
    hdr.setAttribute('aria-label', twT('header.label'));
    hdr.innerHTML = _twHeaderHtml(hdr, _twNavCurrentKey(hdr, getTwUser()));
    var backBtn = hdr.querySelector('[data-tw-hdr-back]');
    if (backBtn) backBtn.addEventListener('click', function () {
      twNavBack(_twBackFallback(hdr.getAttribute('data-back')));
    });
    hdr.addEventListener('click', _twChromeNavClick);
    initGlobalHeaderMenu('twHdrMenuBtn', 'twHdrMenuDd');   // menu + data-tw-session visibility (VM-10)
    if (typeof loadGlobalBadges === 'function') loadGlobalBadges();
  }
  if (nav && !nav.hasAttribute('data-tw-mounted')) {
    nav.setAttribute('data-tw-mounted', '');
    nav.classList.add('tw-bnav');
    nav.setAttribute('aria-label', twT('nav.label'));
    nav.addEventListener('click', _twChromeNavClick);
    _twRenderBottomNav(nav);
  }
  if ((hdr || nav) && !_twChromeBound && window.TwAuthSync && typeof TwAuthSync.onSessionChange === 'function') {
    _twChromeBound = true;
    TwAuthSync.onSessionChange(function () {
      var n = document.querySelector('[data-tw-bottom-nav]');
      if (n) _twRenderBottomNav(n);
    });
  }
}
window.twMountAppChrome = twMountAppChrome;
if (typeof document !== 'undefined' && typeof document.querySelector === 'function') {
  if (document.readyState === 'loading' && typeof document.addEventListener === 'function') {
    document.addEventListener('DOMContentLoaded', function () { twTApply(document); twMountAppChrome(); });
  } else if (document.readyState === 'interactive' || document.readyState === 'complete') {
    twTApply(document);
    twMountAppChrome();
  }
}

// ══ Global Real-time Badge WebSocket ══
// Opens a WS on EVERY page using the authenticated viewer's ID (not profile owner).
// Handles badge_update events to update [data-badge="msgs"] in real time.
// Auth protocol: sends {"type":"auth","token":"..."} as the first message;
// only processes badge_update after server confirms with auth_ok.
// @vm-extract-begin: badge-ws
// Exposed: window._twBadgeWsStop(), window._twBadgeWsStart()
(function() {
  var _gen = 0;      // increments on each _initBadgeWS call; stale loops self-cancel
  var _activeUid = 0;
  var _activeJwt = '';         // JWT the current socket authenticated with (PR 2C same-session check)
  var _activeSocket = null;    // current active WS reference
  var _reconnectTimer = null;  // active reconnect timer handle
  var _retries = 0;            // IIFE-level: persists across _initBadgeWS() calls; reset on auth_ok or new session
  var _sessionReinitTimer = null; // cancellable handle for 300ms session-switch reinit

  function _clearSocket() {
    _gen++;
    var sock = _activeSocket;
    _activeSocket = null;
    if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
    if (_sessionReinitTimer) { clearTimeout(_sessionReinitTimer); _sessionReinitTimer = null; }
    if (sock) { try { sock.close(); } catch(e) {} }
  }

  // Clear all badge elements including data-ah-notif-badge (legacy selector)
  function _clearBadges() {
    document.querySelectorAll('[data-badge="msgs"],[data-badge="notif"],[data-ah-notif-badge]').forEach(function(el) {
      el.textContent = '';
      el.style.display = 'none';
    });
  }

  // pendingJwt: JWT captured synchronously from info.jwt before the async delay fires.
  // V2 contract: getSessionSnapshot() returns {state,isAuthenticated,userType,userId,reason}
  // — no jwt field. JWT always comes from pendingJwt or localStorage.
  function _initBadgeWS(pendingJwt) {
    var snapshot = (typeof TwAuthSync !== 'undefined' && typeof TwAuthSync.getSessionSnapshot === 'function')
        ? TwAuthSync.getSessionSnapshot() : null;
    var uid, jwt;
    if (snapshot) {
      if (!snapshot.isAuthenticated) return;
      uid = snapshot.userId;
      jwt = pendingJwt || (typeof localStorage !== 'undefined' && localStorage.getItem('tw_jwt')) || '';
    } else {
      var u = null;
      try { u = JSON.parse((typeof localStorage !== 'undefined' && localStorage.getItem('tw_user')) || 'null'); } catch(e){}
      jwt = pendingJwt || (typeof localStorage !== 'undefined' && localStorage.getItem('tw_jwt')) || '';
      if (!u || !u.id || !jwt) return;
      uid = u.id;
    }
    if (!uid || !jwt) return;

    _gen++;
    _activeUid = uid;
    _activeJwt = jwt;
    var capturedGen = _gen;
    var capturedUid = Number(uid);

    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws;
    try { ws = new WebSocket(protocol + '//' + window.location.host + '/ws/' + uid); } catch(e) { return; }
    _activeSocket = ws;
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
          if (Number(data.user_id) !== capturedUid) {
            // Mismatch: advance generation to cancel stale closures, close with Forbidden
            _gen++;
            ws.close(4003);
            return;
          }
          _retries = 0;  // reset retry counter on successful auth
          wsReady = true;
          return;
        }
        if (!wsReady) return;
        if (data.type === 'badge_update' && data.badge === 'messages') {
          var count = data.count || 0;
          document.querySelectorAll('[data-badge="msgs"]').forEach(function(el) {
            el.textContent = twNotifBadgeLabel(count);
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
      if (_retries < 5) {
        _retries++;
        var delay = Math.min(30000, Math.pow(2, _retries) * 1000 + Math.floor(Math.random() * 1000));
        _reconnectTimer = setTimeout(_initBadgeWS, delay);
      }
    };
    ws.onerror = function() { ws.close(); };
  }

  function _twBadgeWsStop() {
    _clearSocket();          // _gen++, cancel timers, close socket
    _badgeGeneration++;      // invalidates in-flight HTTP badge requests from prior account
    _retries = 0;
    _clearBadges();
  }

  function _twBadgeWsStart() {
    _retries = 0;
    _initBadgeWS();
  }

  // _bindBadgeAuthSync: idempotent registration of TwAuthSync.onSessionChange listener.
  // Called at IIFE run time AND again at window.load so it succeeds regardless of
  // whether auth-sync.js loads before or after tw_shared.js.
  var _badgeAuthSyncBound = false;
  function _bindBadgeAuthSync() {
    if (_badgeAuthSyncBound) return;
    if (typeof TwAuthSync === 'undefined' || typeof TwAuthSync.onSessionChange !== 'function') return;
    _badgeAuthSyncBound = true;
    TwAuthSync.onSessionChange(function(info) {
      // Same session, socket still alive (CONNECTING / OPEN) → keep it (PR 2C):
      // no close, no badge flash, no extra GETs. Reconnect only when the JWT or
      // the user changed, or the socket is really closed.
      var snap = info && info.snapshot;
      if (info && info.jwt && info.jwt === _activeJwt && snap && snap.isAuthenticated
          && Number(snap.userId) === Number(_activeUid)
          && _activeSocket && _activeSocket.readyState < 2) return;
      // Full unified stop path on every real session change:
      // close socket + cancel timers (_gen++) + cancel in-flight HTTP + clear DOM
      _twBadgeWsStop();
      // Only restart when a new JWT is present (authenticated account switch or token refresh).
      // guest / expired / invalid / stale → stay stopped, no new socket, no badge fetch.
      var capturedJwt = (info && info.jwt) ? info.jwt : null;
      if (!capturedJwt) return;
      _sessionReinitTimer = setTimeout(function() {
        _sessionReinitTimer = null;
        // loadGlobalBadges is defined at module scope (outside this IIFE)
        if (typeof loadGlobalBadges === 'function') loadGlobalBadges();
        _initBadgeWS(capturedJwt);
      }, 300);
    });
  }

  // Try to bind now (succeeds when tw_shared.js loads after auth-sync.js)
  _bindBadgeAuthSync();

  // Run after load so localStorage is populated by page auth guards.
  // Also retries _bindBadgeAuthSync in case auth-sync.js loaded after tw_shared.js.
  window.addEventListener('load', function() {
    _bindBadgeAuthSync();  // idempotent — no-op if already bound
    setTimeout(_initBadgeWS, 200);
  });

  window._twBadgeWsStop  = _twBadgeWsStop;
  window._twBadgeWsStart = _twBadgeWsStart;
})();
// @vm-extract-end: badge-ws


