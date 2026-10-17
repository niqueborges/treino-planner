const CACHE = 'treino-planner-v10';
const ASSETS = [
  '/',
  '/index.html',
  '/styles.css',
  '/library.css',
  '/workout.css',
  '/rest-timer.js',
  '/app.js',
  '/manifest.webmanifest',
  '/icon.svg'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== location.origin || url.pathname.startsWith('/api/')) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      // Revalidate the HTTP cache so deployed assets are not hidden by an older response.
      const response = await fetch(request, { cache: 'no-cache' });
      if (response.ok) await cache.put(request, response.clone());
      return response;
    } catch (_) {
      const cached = await cache.match(request);
      if (cached) return cached;
      if (request.mode === 'navigate') {
        const fallback = await cache.match('/index.html');
        if (fallback) return fallback;
      }
      return Response.error();
    }
  })());
});
