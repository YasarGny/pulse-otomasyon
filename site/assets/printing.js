/* No local-clock fallback: unavailable, incomplete or stale publication stays in the print room. */
(() => {
  "use strict";
  const rules = window.PulsePublication,
    base = new URL("../", document.currentScript.src);
  let serverEpoch = null,
    observed = 0,
    lastSuccess = 0,
    active = null,
    busy = false;
  const shell = document.querySelector(".site-shell");
  const make = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };
  function lock(reason = "", mode = "printing") {
    active = null;
    window.PULSE_RELEASE = null;
    shell.inert = true;
    shell.setAttribute("aria-hidden", "true");
    shell.querySelectorAll("audio").forEach((a) => a.pause());
    document.documentElement.classList.add("pulse-locked");
    document.documentElement.classList.remove("pulse-loading");
    document.getElementById("publication-loading")?.remove();
    let overlay = document.getElementById("pulse-printing");
    if (overlay && overlay.dataset.mode !== mode) {
      overlay.remove();
      overlay = null;
    }
    if (!overlay) {
      overlay = make("main", "pulse-printing");
      overlay.id = "pulse-printing";
      overlay.dataset.mode = mode;
      const card = make("div", "pulse-print-card");
      const art = make("div", "press-scene");
      art.setAttribute("aria-hidden", "true");
      art.innerHTML = `<svg class="press-illustration" viewBox="0 0 400 290" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs><linearGradient id="press-metal" x2="0" y2="1"><stop stop-color="#344356"/><stop offset="1" stop-color="#172234"/></linearGradient><linearGradient id="press-light"><stop stop-color="#f2a7cc" stop-opacity="0"/><stop offset=".5" stop-color="#f2a7cc"/><stop offset="1" stop-color="#f2a7cc" stop-opacity="0"/></linearGradient></defs>
        <ellipse cx="200" cy="264" rx="148" ry="12" fill="#000" opacity=".25"/>
        <rect x="67" y="64" width="266" height="130" rx="20" fill="url(#press-metal)" stroke="#526178"/>
        <rect x="88" y="84" width="224" height="15" rx="7" fill="#0b111c"/>
        <circle cx="300" cy="119" r="4" fill="#f2a7cc" class="press-led"/>
        <path d="M92 147H308" stroke="#080e1a" stroke-width="13" stroke-linecap="round"/>
        <g class="press-newspaper"><rect x="112" y="133" width="176" height="116" rx="3" fill="#eeeae5"/>
        <text x="126" y="161" fill="#192232" font-size="22" font-family="Arial,sans-serif" font-weight="900" letter-spacing="-1">PULSE<tspan fill="#a34872">.</tspan></text>
        <path d="M126 170H274" stroke="#192232"/>
        <rect x="126" y="180" width="66" height="39" rx="2" fill="#658b94"/>
        <path d="m128 213 19-22 14 13 10-8 19 18" stroke="#b6d3d4" stroke-width="2"/>
        <path d="M204 182H273M204 190H273M204 198H273M204 206H255M126 230H274M126 237H252" stroke="#9a9ba0" stroke-width="3"/>
        </g>
        <path d="M92 147H308" stroke="url(#press-light)" stroke-width="2"/>
        <path d="M79 183v11a12 12 0 0 0 12 12h12m218-23v11a12 12 0 0 1-12 12h-12" stroke="#526178" stroke-width="2"/>
      </svg>`;
      if (mode === "offline") art.hidden = true;
      const status = make("p", "pulse-print-small");
      status.id = "printing-status";
      status.setAttribute("role", "status");
      const retry = make("button", "retry", "Yayın durumunu kontrol et");
      retry.type = "button";
      retry.addEventListener("click", () => check());
      card.append(
        make("div", "pulse-print-brand", "PULSE"),
        art,
        make(
          "h1",
          "",
          mode === "printing"
            ? "Haberler baskıya giriyor!"
            : "Yayına ulaşamadık.",
        ),
        make(
          "p",
          "",
          mode === "printing"
            ? "Gündemi toparlıyor, mikrofonları hazırlıyoruz."
            : "Bağlantıyı kontrol edip yeniden deneyebilirsiniz.",
        ),
        make(
          "div",
          "pulse-print-clock",
          mode === "printing"
            ? "Yeni sayı 07:30’da, her şey hazır olduğunda."
            : "",
        ),
        status,
        retry,
      );
      overlay.append(card);
      document.body.append(overlay);
      if (shell.contains(document.activeElement)) retry.focus();
    }
    document.getElementById("printing-status").textContent = reason;
    window.dispatchEvent(new CustomEvent("pulse:locked"));
  }
  function unlock(manifest, editions, url) {
    const changed = active !== manifest.release_id;
    active = manifest.release_id;
    window.PULSE_RELEASE = { manifest, editions, url };
    const overlay = document.getElementById("pulse-printing");
    const hadFocus = overlay?.contains(document.activeElement);
    overlay?.remove();
    shell.inert = false;
    shell.removeAttribute("aria-hidden");
    document.documentElement.classList.remove("pulse-locked", "pulse-loading");
    document.getElementById("publication-loading")?.remove();
    if (hadFocus) {
      const main = document.getElementById("main");
      main.tabIndex = -1;
      main.focus();
    }
    if (changed)
      window.dispatchEvent(
        new CustomEvent("pulse:ready", { detail: window.PULSE_RELEASE }),
      );
  }
  async function get(url) {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw Error("Yayın dosyaları henüz ulaşmadı");
    return response;
  }
  async function check() {
    if (busy) return;
    busy = true;
    try {
      const response = await get(
        new URL("data/publication.json?check=" + performance.now(), base),
      );
      const at = rules.httpTime(response.headers);
      // A cache returning an older clock cannot postpone tomorrow's closing indefinitely.
      if (
        serverEpoch !== null &&
        at.getTime() < serverEpoch + (performance.now() - observed) - 120000
      )
        throw Error("Yayın durumu güncelleniyor");
      serverEpoch = at.getTime();
      observed = performance.now();
      const manifest = await response.json();
      if (!rules.isReady(manifest, at)) {
        lock();
        return;
      }
      const url = new URL("releases/" + manifest.release_id + "/", base);
      const editions = Object.fromEntries(
        await Promise.all(
          rules.sections.map(async (section) => {
            const response = await get(
              new URL(manifest.editions[section].file, url),
            );
            const raw = await response.arrayBuffer();
            if ((await rules.sha256(raw)) !== manifest.editions[section].sha256)
              throw Error("Haber dosyası doğrulanamadı");
            const data = JSON.parse(new TextDecoder().decode(raw));
            if (!rules.editionValid(data, section, manifest))
              throw Error("Yayın henüz tamamlanmadı");
            await Promise.all(
              ["summary", "podcast"].map(async (kind) => {
                const a = data[kind];
                const r = await fetch(new URL(a.file, url), {
                  method: "HEAD",
                  cache: "no-store",
                  signal: AbortSignal.timeout(15000),
                });
                if (
                  !r.ok ||
                  Number(r.headers.get("content-length")) !== a.bytes ||
                  !(r.headers.get("content-type") || "").startsWith("audio/")
                )
                  throw Error("Ses dosyaları hazırlanıyor");
              }),
            );
            return [section, data];
          }),
        ),
      );
      // Network requests may straddle 06:00. Recheck against elapsed server time.
      const current = new Date(serverEpoch + performance.now() - observed);
      if (!rules.isReady(manifest, current)) {
        lock();
        return;
      }
      lastSuccess = performance.now();
      unlock(manifest, editions, url);
    } catch (error) {
      lock(
        "Yayın durumu doğrulanamadı. Birazdan yeniden kontrol edeceğiz.",
        "offline",
      );
    } finally {
      busy = false;
    }
  }
  // A ready page must never flash the print room while its manifest is fetched.
  // Keep a neutral loading surface until server-verified preparation is known.
  shell.inert = true;
  shell.setAttribute("aria-hidden", "true");
  setTimeout(() => {
    if (!document.documentElement.classList.contains("pulse-loading")) return;
    const loading = make("div", "publication-loading", "PULSE");
    loading.id = "publication-loading";
    loading.append(make("span", "", "."));
    loading.setAttribute("role", "status");
    loading.setAttribute("aria-label", "Yayın yükleniyor");
    document.body.append(loading);
  }, 180);
  check();
  setInterval(check, 60000);
  setInterval(() => {
    if (!active) return;
    const at = new Date(serverEpoch + performance.now() - observed);
    if (
      !rules.isReady(window.PULSE_RELEASE.manifest, at) ||
      performance.now() - lastSuccess > 120000
    )
      lock();
  }, 1000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      if (
        active &&
        serverEpoch !== null &&
        !rules.isReady(
          window.PULSE_RELEASE.manifest,
          new Date(serverEpoch + performance.now() - observed),
        )
      )
        lock();
      check();
    }
  });
})();
