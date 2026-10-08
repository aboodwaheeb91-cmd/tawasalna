// Service Worker — Cache Allowlist (security/sw-cache-allowlist)
//
// PRIVACY CONTRACT (permanent — see ARCHITECTURE.md → Service Worker Cache Allowlist):
//   - Only public static assets are cached: same-origin + GET + allowlisted
//     request.destination + allowlisted path. Everything else (API/JSON,
//     HTML navigations) goes to the network only — never cache.put.
//   - Any request carrying an Authorization header is never cached.
//   - New API endpoints need NO change here: the API is never cached by default.
//
// Bump BUILD_TIME whenever this file changes so `activate` deletes old caches.
const BUILD_TIME = '20261008_1200';
const CACHE_NAME = 'tawasolna-v6-' + BUILD_TIME;

// Precached public pages. OFFLINE_FALLBACK is the single offline response for
// navigations — never a private page from the cache.
// The fallback page is served through the Page Shell (F39), so the shell's shared
// CSS / JS (partials/shell-*.html), the page's own tw-icons.js + app-header.css (unified
// guest header — HEADER-NAV.md) and its logo
// (/static/33333.svg) are precached too — keep this list in sync with the partials
// and the page (test_landing_shell.py checks it).
// They are stored without ?v= and matched with ignoreSearch offline (see fetch).
const OFFLINE_FALLBACK = '/landing.html';
const STATIC_ASSETS = [
  OFFLINE_FALLBACK,
  '/manifest.json',
  '/static/tw_shared.css',
  '/static/tw_shared.js',
  '/static/shared/auth-sync.js',
  '/static/shared/tw-icons.js',
  '/static/app-header.css',
  '/static/33333.svg'
];

const CACHEABLE_DESTINATIONS = ['style', 'script', 'font', 'image', 'manifest'];

function _isCacheablePath(path) {
  return path.indexOf('/static/') === 0 ||
         path === '/manifest.json' ||
         /^\/icon-[A-Za-z0-9_-]+\.png$/.test(path);
}

// Single decision point: true only for public static assets.
function isCacheableRequest(request) {
  if (request.method !== 'GET') return false;
  if (request.headers && request.headers.has('Authorization')) return false;
  var url;
  try { url = new URL(request.url); } catch (e) { return false; }
  if (url.origin !== self.location.origin) return false;
  if (CACHEABLE_DESTINATIONS.indexOf(request.destination) === -1) return false;
  return _isCacheablePath(url.pathname);
}

self.addEventListener('install', function(e){
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(k){ return k !== CACHE_NAME; })
            .map(function(k){ return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(e){
  var request = e.request;
  if (request.method !== 'GET') return;

  // HTML navigations: network only; offline → one fixed public fallback.
  if (request.mode === 'navigate') {
    e.respondWith(
      fetch(request).catch(function(){
        return caches.match(OFFLINE_FALLBACK).then(function(r){
          return r || new Response('', { status: 503 });
        });
      })
    );
    return;
  }

  // Not allowlisted (API/JSON, Authorization, cross-origin, …):
  // no respondWith → browser default network fetch, nothing stored.
  if (!isCacheableRequest(request)) return;

  // Public static asset: network first, cache as offline fallback.
  e.respondWith(
    fetch(request).then(function(response){
      if (response && response.status === 200 && response.type === 'basic') {
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function(cache){ return cache.put(request, clone); })
          .catch(function(err){ console.warn('[sw] cache.put failed:', err); });
      }
      return response;
    }).catch(function(){
      // Offline: exact URL first; else the precached copy without ?v= (shell hash).
      return caches.match(request).then(function(r){
        return r || caches.match(request, { ignoreSearch: true });
      });
    })
  );
});

self.addEventListener('push', function(e){
  var data = e.data ? e.data.json() : {};
  e.waitUntil(
    self.registration.showNotification(data.title || 'تواصلنا', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      dir: 'rtl',
      lang: 'ar',
      data: { url: data.url || '/' }
    })
  );
});

// Only same-origin relative paths: must start with '/' and not '//' or '/\'.
function safeNotificationUrl(url) {
  if (typeof url !== 'string' || url.charAt(0) !== '/') return '/';
  var second = url.charAt(1);
  if (second === '/' || second === '\\') return '/';
  return url;
}

self.addEventListener('notificationclick', function(e){
  e.notification.close();
  var data = e.notification.data || {};
  e.waitUntil(clients.openWindow(safeNotificationUrl(data.url)));
});
