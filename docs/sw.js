// Caché sencilla: la app funciona sin conexión mostrando el último informe descargado.
const CACHE = "oportunidades-v12";
const SHELL = ["./", "index.html", "styles.css", "app.js", "glossary.js", "simulador.js", "manifest.webmanifest", "icon-192.png"];
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.includes("/api/")) return;
  const key = url.origin + url.pathname; // ignora ?t=
  // "no-cache": siempre pregunta al servidor si hay versión nueva (ignora la caché de 10 min de GitHub)
  e.respondWith(fetch(e.request, { cache: "no-cache" }).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(key, copy)); }
    return res;
  }).catch(() => caches.match(key)));
});
