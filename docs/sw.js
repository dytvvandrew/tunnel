const CACHE = "tunnel-cockpit-v1";
const SHELL = ["./", "./index.html", "./cockpit.css", "./cockpit.js", "./manifest.webmanifest", "./assets/app-icon.svg", "./overview.html", "./assets/tunnel_excavation_hero.svg"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))), self.clients.claim()]));
});
self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).then(response => {const copy=response.clone();caches.open(CACHE).then(cache => cache.put(request,copy));return response;}).catch(() => caches.match(request).then(response => response || caches.match("./index.html"))));
  } else {
    event.respondWith(fetch(request).then(network => {if(network.ok){const copy=network.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));}return network;}).catch(() => caches.match(request)));
  }
});
