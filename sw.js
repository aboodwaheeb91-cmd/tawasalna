
// Fix [A-2]: Version includes build timestamp
// Update this BUILD_TIME on every deploy to bust old caches
const BUILD_TIME = '20260529_1341';
const CACHE_NAME = 'tawasolna-v4-' + BUILD_TIME; // bumped version to bust old cache

const STATIC_ASSETS = [
  '/landing.html',
  '/index.html',
  '/manifest.json'
];

// URLs that should NEVER be cached (always network)
const NO_CACHE = [
  // Fix [A-4]: JS files always from network — prevents stale code after deploy
  '.js',
  '/profile',
  '/auth/',
  '/experience',
  '/education',
  '/skills/',
  '/langs/',
  '/links/',
  '/course/',
  '/messages',
  '/notifications',
  '/kyc/',
  '/reports',
  '/admin',
  '/profile.html',
  '/home.html',
  '/settings.html',
  '/company.html',
  '/company-profile.html',
  '/edu.html',
  '/edu-profile.html',
  '/jobs.html',
  '/job-detail.html',
  '/sw.js',
  '/tw_shared.js',
];

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
  if(e.request.method !== 'GET') return;
  
  var url = e.request.url;
  
  // Never cache these URLs - always go to network
  if(NO_CACHE.some(function(path){ return url.includes(path); })){
    e.respondWith(fetch(e.request).catch(function(){ return new Response('', {status: 503}); }));
    return;
  }
  
  // For everything else: network first, cache as fallback
  e.respondWith(
    fetch(e.request).then(function(response){
      if(response && response.status === 200){
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function(cache){ cache.put(e.request, clone); });
      }
      return response;
    }).catch(function(){
      return caches.match(e.request);
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

self.addEventListener('notificationclick', function(e){
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url));
});
