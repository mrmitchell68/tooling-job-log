/* Tooling Job Log v2 service worker — offline app shell + CDN libraries. */
const VERSION = "tjl-v2.2.0";
const SHELL_CACHE = VERSION + "-shell";
const LIB_CACHE = "tjl-libs-v1";           // CDN libs are version-pinned, so this cache survives app updates
const SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-64.png"
];
// Small libs precached best-effort at install. The big OCR engine + English data
// (~7 MB) are cached at runtime the first time OCR runs or when the app warms them.
const LIBS = [
  "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js",
  "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/worker.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js",
  "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600;700&display=swap"
];
const CDN_HOSTS = ["cdn.jsdelivr.net", "cdnjs.cloudflare.com", "fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await shell.addAll(SHELL.map((u) => new Request(u, { cache: "reload" })));
    const libs = await caches.open(LIB_CACHE);
    await Promise.all(LIBS.map(async (u) => {
      try {
        if (await libs.match(u)) return;
        const res = await fetch(u, { mode: "cors" });
        if (res.ok) await libs.put(u, res);
      } catch (e) { /* offline during install: fine, cached later */ }
    }));
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith("tjl-v") && k !== SHELL_CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data === "skipWaiting") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // App navigation: serve cached shell instantly, refresh it in the background.
  if (req.mode === "navigate" && url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(SHELL_CACHE);
      const cached = await cache.match("./index.html") || await cache.match("./");
      const network = fetch(req).then((res) => {
        if (res.ok && (url.pathname.endsWith("/") || url.pathname.endsWith("/index.html"))) cache.put("./index.html", res.clone());
        return res;
      }).catch(() => null);
      if (cached) { event.waitUntil(network); return cached; }
      return (await network) || new Response("Offline and not cached yet.", { status: 503, headers: { "Content-Type": "text/plain" } });
    })());
    return;
  }

  // Same-origin static files: cache first, update in background.
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(SHELL_CACHE);
      const cached = await cache.match(req, { ignoreSearch: true });
      const network = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
      if (cached) { event.waitUntil(network); return cached; }
      return (await network) || new Response("", { status: 504 });
    })());
    return;
  }

  // Version-pinned CDN libraries, OCR engine/data and fonts: cache first.
  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith((async () => {
      const cache = await caches.open(LIB_CACHE);
      const cached = await cache.match(req, { ignoreVary: true }) || await cache.match(req.url, { ignoreVary: true });
      if (cached) return cached;
      try {
        const res = await fetch(req);
        if (res.ok || res.type === "opaque") cache.put(req.url, res.clone()).catch(() => {});
        return res;
      } catch (e) {
        return new Response("", { status: 504, statusText: "Offline" });
      }
    })());
  }
});
