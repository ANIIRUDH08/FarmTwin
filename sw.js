// FarmTwin service worker: saves everything the app downloads so it opens offline.
// Bump CACHE_VERSION whenever you upload a new version of the site.
const CACHE_VERSION = "farmtwin-v1";

const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
  "./app.py", "./model.py", "./explain.py", "./season.py", "./recommend.py",
  "./data.json", "./api_key.py", "./crop_model.joblib", "./Crop_recommendation.csv"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => Promise.all(CORE.map((u) => cache.add(u).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                       // AI calls (POST) are never cached
  const url = new URL(req.url);
  if (url.hostname.endsWith("googleapis.com") && url.pathname.includes("/models/")) return;

  const sameOrigin = url.origin === self.location.origin;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_VERSION);
    const hit = await cache.match(req, { ignoreSearch: sameOrigin });

    const refresh = fetch(req).then((res) => {
      if (res && (res.status === 200 || res.type === "opaque")) cache.put(req, res.clone());
      return res;
    });

    if (hit) {
      if (sameOrigin) refresh.catch(() => {});             // site files: show saved copy, update quietly
      return hit;                                          // libraries (CDN): saved copy, never changes
    }
    try {
      return await refresh;
    } catch (e) {
      if (req.mode === "navigate") {
        const home = await cache.match("./index.html");
        if (home) return home;
      }
      return new Response("Offline and not saved yet.", { status: 503, statusText: "Offline" });
    }
  })());
});
