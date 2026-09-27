/* Story Scout Next v2 — offline service worker.
   Cache names are namespaced "ssn-v2-" so v2 never evicts or overwrites
   v1's cache (and cleanup below only ever deletes v2's own old caches). */
const PREFIX = "ssn-v2-";
const CACHE = PREFIX + "arcade-2";
const PRECACHE = [
  "./",
  "./index.html",
  "./css/style.css",
  "./css/scenes.css",
  "./js/app.js",
  "./js/search.js",
  "./js/storage.js",
  "./js/loadout.js",
  "./js/clips.js",
  "./js/arcade.js",
  "../data/stories.json",
  "./manifest.webmanifest",
  "./assets/daily-goods-logo.jpeg",
  "./assets/px/nico-hero.svg",
  "./assets/px/nico-mini.svg",
  "./assets/px/nico-badge.svg",
  "./assets/px/nico-sit.svg",
  "./assets/px/medallion.svg",
  "./assets/px/scene-city.svg",
  "./assets/px/scene-trail.svg",
  "./assets/px/scene-harbor.svg",
  "./assets/px/scene-alley.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith(PREFIX) && k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Network-first for story data so SYNC stays fresh when online
  if (url.pathname.endsWith("/data/stories.json") || url.pathname.endsWith("/data/twitter_stories.json")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req, { cacheName: CACHE }))
    );
    return;
  }

  // Network-first for HTML/CSS/JS/SVG so UI deploys aren't stuck behind SW cache
  const path = url.pathname;
  const isShell =
    path.endsWith("/") ||
    path.endsWith(".html") ||
    path.endsWith(".css") ||
    path.endsWith(".js") ||
    path.endsWith(".svg") ||
    path.endsWith(".webmanifest");

  if (url.origin === self.location.origin) {
    if (isShell) {
      event.respondWith(
        fetch(req)
          .then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return res;
          })
          .catch(() => caches.match(req, { cacheName: CACHE }))
      );
      return;
    }
    event.respondWith(
      caches.match(req, { cacheName: CACHE }).then((hit) => {
        if (hit) return hit;
        return fetch(req).then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        });
      })
    );
  }
});
