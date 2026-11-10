/* Service worker de la app del gemelo: permite instalarla como aplicación y guarda en caché
 * los archivos fijos (three.js, modelo 3D, estilos). Nunca guarda la API ni las páginas:
 * el estado del brazo siempre viene en vivo de la app. */
const CACHE = 'gemelo-v1';
const FIJOS = ['/lib/', '/modelo/', '/css/', '/js/', '/icono'];

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(k => Promise.all(k.filter(n => n !== CACHE).map(n => caches.delete(n)))).then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || !FIJOS.some(p => u.pathname.startsWith(p))) return;
  // primero la red (para recibir versiones nuevas); si no responde, la copia guardada
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then(k => k.put(e.request, c)); }
    return r;
  }).catch(() => caches.match(e.request)));
});
