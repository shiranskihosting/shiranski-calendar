/* לוח הצפייה · service worker · אופליין */
const SHELL = 'vb-shell-v10';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-48.png','./icon-72.png','./icon-96.png','./icon-144.png','./icon-192.png','./icon-256.png','./icon-512.png','./icon-maskable-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== 'vb-data').map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;                       // fonts etc.: network
  if (url.pathname.endsWith('data.enc.json')) return;              // the page itself caches data in 'vb-data'
  e.respondWith(
    fetch(e.request, { cache: 'no-cache' }).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
  );
});
