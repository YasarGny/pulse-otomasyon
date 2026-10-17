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
  function lock(reason = "", mode = null) {
    if (!mode) {
      const at =
        serverEpoch === null
          ? null
          : new Date(serverEpoch + performance.now() - observed);
      mode =
        at && at >= new Date(rules.expectedDate(at) + "T07:30:00+03:00")
          ? "delayed"
          : "printing";
    }
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
      if (mode === "offline") {
        const image = make("img", "connection-illustration");
        image.src = new URL("assets/connection-paper.webp", base).href;
        image.alt = "";
        image.width = 768;
        image.height = 512;
        art.append(image);
      } else {
        art.innerHTML = `<svg class="press-illustration" viewBox="0 0 1280 1280" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs><linearGradient id="paper-shade" x2="0.2" y2="1"><stop stop-color="#f2eee6"/><stop offset="1" stop-color="#d8d3c9"/></linearGradient></defs>
          <image href="${new URL("assets/press-machine.webp", base).href}" width="1280" height="1280"/>
          <g transform="matrix(.76 -.25 .38 .54 390 610)">
            <g class="press-newspaper">
              <rect x="0" y="0" width="720" height="500" rx="5" fill="url(#paper-shade)" stroke="#c2bbb0" stroke-width="4"/>
              <text x="42" y="105" fill="#202125" font-size="82" font-family="Arial,sans-serif" font-weight="900" letter-spacing="-4">PULSE<tspan fill="#ed3477">.</tspan></text>
              <path d="M42 135h636" stroke="#7c7b78" stroke-width="4"/>
              <rect x="42" y="164" width="266" height="150" fill="#d783a9"/>
              <path d="M342 176h336m-336 28h336m-336 28h336m-336 28h336m-336 28h336M42 350h636m-636 28h636m-636 28h636m-636 28h480" stroke="#a9a69f" stroke-width="13"/>
            </g>
          </g>
        </svg>`;
      }
      const status = make("p", "pulse-print-small");
      status.id = "printing-status";
      status.setAttribute("role", "status");
      const retry = make("button", "retry", "Tekrar dene");
      retry.type = "button";
      retry.hidden = mode === "printing";
      retry.addEventListener("click", () => check());
      card.append(
        Object.assign(make("div", "pulse-print-brand"), {
          innerHTML: "PULSE<span>.</span>",
        }),
        art,
        make(
          "h1",
          "",
          mode === "offline"
            ? "Yayın durumu doğrulanamadı."
            : mode === "delayed"
              ? "Hazırlık devam ediyor."
              : "Haberler baskıya giriyor!",
        ),
        make(
          "p",
          "",
          mode === "offline"
            ? "Bağlantını kontrol edip yeniden deneyebilirsin."
            : mode === "delayed"
              ? "İki yayın tamamlandığında burada olacak."
              : "Teknoloji ve oyun gündemi hazırlanıyor.",
        ),
        make(
          "div",
          "pulse-print-clock",
          mode === "printing"
            ? "Yeni sayı hedefi 07:30."
            : mode === "delayed"
              ? "07:30 hedef saati aşıldı."
              : "",
        ),
        status,
        retry,
      );
      overlay.append(card);
      document.body.append(overlay);
      if (shell.contains(document.activeElement)) {
        const focusTarget = retry.hidden ? overlay.querySelector("h1") : retry;
        focusTarget.tabIndex = -1;
        focusTarget.focus();
      }
    }
    document.getElementById("printing-status").textContent = reason;
    window.dispatchEvent(new CustomEvent("pulse:locked"));
  }
  function reveal() {
    if (
      !window.PULSE_RELEASE ||
      document.getElementById("main")?.dataset.release !== active
    )
      return;
    if (
      serverEpoch !== null &&
      !rules.isReady(
        window.PULSE_RELEASE.manifest,
        new Date(serverEpoch + performance.now() - observed),
      )
    ) {
      lock();
      return;
    }
    const overlay = document.getElementById("pulse-printing");
    const hadFocus = overlay?.contains(document.activeElement);
    overlay?.remove();
    shell.inert = false;
    shell.removeAttribute("aria-hidden");
    document.documentElement.classList.remove("pulse-locked", "pulse-loading");
    document.getElementById("publication-loading")?.remove();
    if (hadFocus) document.getElementById("main").focus();
  }
  function unlock(manifest, editions, url) {
    const changed = active !== manifest.release_id;
    active = manifest.release_id;
    window.PULSE_RELEASE = { manifest, editions, url };
    // Verified JSON must not expose a cached HTML page from another release.
    if (changed)
      window.dispatchEvent(
        new CustomEvent("pulse:ready", { detail: window.PULSE_RELEASE }),
      );
  }
  window.addEventListener("pulse:rendered", (event) => {
    if (event.detail?.release_id === active) reveal();
  });
  window.addEventListener("pulse:render-error", () =>
    lock(
      "Sayfa güncel yayınla eşleşmedi. Yeniden kontrol edeceğiz.",
      "offline",
    ),
  );
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
      lock("", "offline");
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
    const loading = make("div", "publication-loading");
    loading.id = "publication-loading";
    const content = make("div", "loading-content");
    content.innerHTML =
      '<div class="loading-brand">PULSE<span>.</span></div><div class="loading-preview" aria-hidden="true"><div class="loading-picture"></div><div class="loading-lines"><i></i><i></i><i></i></div></div>';
    content.append(make("p", "loading-message", "Yayın kontrol ediliyor…"));
    loading.append(content);
    loading.setAttribute("role", "status");
    loading.setAttribute("aria-label", "Yayın kontrol ediliyor");
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
    document.documentElement.classList.toggle(
      "document-hidden",
      document.hidden,
    );
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
