/* Amina service worker.
 *
 * Two jobs:
 *  1. Make the app installable (an installable app needs a service worker).
 *  2. Keep the shell working offline.
 *
 * It never caches /api/* . AI answers must be live or honestly degraded; a
 * cached answer presented as fresh would be the exact lying this project is
 * removing. Cross-origin requests (fonts) are left to the browser.
 */

const VERSION = 'amina-v2';
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;

// Resolve paths against the service worker's own scope so the app works on a
// root domain or a subpath host. scoped('/') -> '/', scoped('/amina') -> '/amina/'.
const scoped = (p) => new URL(p, self.registration.scope).pathname;
const INDEX = scoped('index.html');
const ROOT = scoped('.');
const CORE = [ROOT, INDEX, scoped('manifest.webmanifest'), scoped('icon.svg')];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Only GET. Never touch the API: live data or nothing.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/api/')) return;

  // Navigations: network first, fall back to the cached shell offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          // Only cache a good response for the app shell itself, never an error page or another path.
          if (res.ok && (url.pathname === ROOT || url.pathname === INDEX)) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(INDEX, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(INDEX).then((r) => r || caches.match(ROOT)))
    );
    return;
  }

  // Hashed build assets: cache first, they never change under one name.
  const isHashedAsset = /\/assets\/[^/]+-[A-Za-z0-9_-]{8,}\.[a-z0-9]+$/.test(url.pathname);
  if (isHashedAsset) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(ASSETS).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      }))
    );
    return;
  }

  // Everything else: try network, fall back to cache.
  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(SHELL).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(request))
  );
});
