/* Mkulima Sokoni — root service worker (full-site PWA).
 *
 * Strategy:
 *  - HTML navigations: network-first, cache fallback, then offline page.
 *  - Static (assets, css, js, images, fonts): stale-while-revalidate.
 *  - API (/api/*): network-only (do not cache user data).
 *  - All other GET: cache fallback when offline.
 */
const CACHE_VERSION = 'mk-v3';
const APP_SHELL_CACHE = `${CACHE_VERSION}-shell`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const STATIC_CACHE = `${CACHE_VERSION}-static`;

const APP_SHELL = [
  '/',
  '/market',
  '/install',
  '/offline.html',
  '/manifest.webmanifest',
  '/assets/img/logo.jpeg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) =>
      // best-effort prefetch (do not fail install on individual misses)
      Promise.allSettled(APP_SHELL.map((url) => cache.add(url)))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => !k.startsWith(CACHE_VERSION))
          .map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

const isStaticAsset = (url) =>
  /\.(?:css|js|mjs|png|jpg|jpeg|webp|svg|gif|ico|woff2?|ttf|eot|mp3|mp4)$/i.test(
    url.pathname
  ) || url.pathname.startsWith('/assets/');

const isHtmlRequest = (request) =>
  request.mode === 'navigate' ||
  (request.method === 'GET' &&
    (request.headers.get('accept') || '').includes('text/html'));

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache APIs or auth-sensitive endpoints.
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/_vercel/')
  ) {
    return;
  }

  if (isHtmlRequest(request)) {
    event.respondWith(
      (async () => {
        try {
          const network = await fetch(request);
          const cache = await caches.open(RUNTIME_CACHE);
          cache.put(request, network.clone());
          return network;
        } catch {
          const cached = await caches.match(request);
          if (cached) return cached;
          const offline = await caches.match('/offline.html');
          return (
            offline ||
            new Response('You are offline.', {
              status: 503,
              headers: { 'Content-Type': 'text/plain; charset=utf-8' },
            })
          );
        }
      })()
    );
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(STATIC_CACHE);
        const cached = await cache.match(request);
        const network = fetch(request)
          .then((res) => {
            if (res && res.status === 200) cache.put(request, res.clone());
            return res;
          })
          .catch(() => null);
        return cached || (await network) || new Response('', { status: 504 });
      })()
    );
    return;
  }

  event.respondWith(
    (async () => {
      try {
        return await fetch(request);
      } catch {
        const cached = await caches.match(request);
        return cached || new Response('', { status: 504 });
      }
    })()
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
