/* Network-only: an installed window must never promote yesterday's cached issue. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("fetch", (event) => {
  if (
    event.request.mode !== "navigate" ||
    new URL(event.request.url).origin !== self.location.origin
  )
    return;
  event.respondWith(
    fetch(event.request, { cache: "no-store" }).catch(
      () =>
        new Response(
          `<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#151618"><title>Bağlantı kurulamadı · PULSE</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#151618;color:#f2f1ed}body{margin:0;min-height:100dvh;display:grid;place-items:center}main{padding:32px;max-width:400px}strong{font-size:36px;letter-spacing:-2px}span{color:#ff3d85}h1{font-size:28px;line-height:1.2;margin-top:48px}p{color:#babbc1;line-height:1.6}a{display:inline-block;padding:12px 20px;margin-top:16px;border-radius:8px;background:#ff3d85;color:#151618;font-weight:700;text-decoration:none}a:focus-visible{outline:3px solid white;outline-offset:4px}
</style></head><body><main><strong>PULSE<span>.</span></strong><h1>Bağlantı kurulamadı.</h1><p>İnternete bağlanıp yeniden deneyebilirsin.</p><a href="">Tekrar dene</a></main></body></html>`,
          {
            status: 503,
            headers: {
              "Content-Type": "text/html; charset=utf-8",
              "Cache-Control": "no-store",
              "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            },
          },
        ),
    ),
  );
});
