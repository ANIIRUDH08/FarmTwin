// FarmTwin service worker: saves everything the app downloads so it opens offline.
// App files (your own .py/.html/.json) are fetched fresh whenever there is internet and the
// saved copy is used only when offline. Big libraries from CDNs are saved once and reused.
const APP_CACHE = "farmtwin-app-v3";     // bump when you upload a new version (optional now)
const LIBS_CACHE = "farmtwin-libs-v1";   // stlite / Pyodide / packages: kept between updates

const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
  "./app.py", "./model.py", "./explain.py", "./season.py", "./recommend.py",
  "./data.json", "./api_key.py", "./crop_model.joblib", "./Crop_recommendation.csv"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_CACHE)
      .then((cache) => Promise.all(CORE.map((u) =>
        fetch(u, { cache: "no-cache" }).then((r) => r.ok && cache.put(u, r)).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys
        .filter((k) => k !== APP_CACHE && k !== LIBS_CACHE)
        .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                        // AI calls (POST) are never cached
  const url = new URL(req.url);
  if (url.hostname.endsWith("googleapis.com") && url.pathname.includes("/models/")) return;
  event.respondWith(url.origin === self.location.origin ? networkFirst(req) : cacheFirst(req));
});

async function networkFirst(req) {
  const cache = await caches.open(APP_CACHE);
  try {
    const live = req.mode === "navigate" ? fetch(req) : fetch(req, { cache: "no-cache" });
    const res = await Promise.race([
      live,
      new Promise((_, reject) => setTimeout(() => reject(new Error("slow")), 5000)),
    ]);
    if (res && res.status === 200) cache.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    if (req.mode === "navigate") {
      const home = await cache.match("./index.html");
      if (home) return home;
    }
    return new Response("Offline and not saved yet.", { status: 503, statusText: "Offline" });
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(LIBS_CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res && (res.status === 200 || res.type === "opaque")) cache.put(req, res.clone());
    return res;
  } catch (e) {
    return new Response("Offline and not saved yet.", { status: 503, statusText: "Offline" });
  }
}
