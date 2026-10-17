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
    const moveFocus =
      shell.contains(document.activeElement) ||
      !!document.activeElement.closest(".audio-session");
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
        art.innerHTML = `<svg class="press-illustration" style="stroke:none" viewBox="0 0 480 430" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <linearGradient id="press-ivory" x2="0" y2="1"><stop stop-color="#f6f1e7"/><stop offset=".5" stop-color="#d7d1c5"/><stop offset="1" stop-color="#aea89e"/></linearGradient>
            <linearGradient id="press-pink" x2="0" y2="1"><stop stop-color="#ffb6d2"/><stop offset=".22" stop-color="#fa4b8e"/><stop offset=".6" stop-color="#e82b73"/><stop offset="1" stop-color="#8c224a"/></linearGradient>
            <linearGradient id="press-steel" x2="0" y2="1"><stop stop-color="#9a9c9e"/><stop offset=".3" stop-color="#393b40"/><stop offset="1" stop-color="#17191d"/></linearGradient>
            <linearGradient id="paper-shade" x2="0" y2="1"><stop stop-color="#d5cec0"/><stop offset=".25" stop-color="#f4f0e7"/><stop offset="1" stop-color="#e7e0d4"/></linearGradient>
            <clipPath id="press-output"><rect x="18" y="92" width="224" height="208"/></clipPath>
            <g id="press-sheet"><rect x="18" y="92" width="224" height="360" fill="url(#paper-shade)"/><g transform="translate(0 24)"><text x="34" y="145" fill="#202125" font-size="34" font-family="Arial,sans-serif" font-weight="900" letter-spacing="-2">PULSE<tspan fill="#ed3477">.</tspan></text><path d="M34 156h190" stroke="#77736e"/><rect x="34" y="172" width="80" height="61" fill="#e880a5"/><path d="M126 178h98m-98 11h98m-98 11h98m-98 11h98m-98 11h98M34 252h190m-190 12h190m-190 12h190m-190 12h130" stroke="#aaa398" stroke-width="4"/></g></g>
          </defs>
          <g transform="matrix(1 -.22 .28 .86 63 106)">
            <ellipse cx="130" cy="250" rx="180" ry="14" fill="#000" opacity=".16"/>
            <path d="M-26 233h54v25h-54Zm260 0h54v25h-54Z" fill="#77736f"/>
            <path d="M-20 0l-10 7v244l10-7Zm300 0 10 7v244l-10-7Z" fill="#959086"/><path d="M-20 0h34v244h-34Zm266 0h34v244h-34Z" fill="url(#press-ivory)" stroke="#aaa397" stroke-width="2"/>
            <rect x="-20" y="0" width="300" height="24" rx="5" fill="url(#press-ivory)" stroke="#aaa397"/>
            <rect x="-6" y="35" width="272" height="62" rx="29" fill="url(#press-steel)"/>
            <rect class="press-back-roller" x="7" y="35" width="246" height="62" rx="29" fill="url(#press-pink)"/>
            <path d="M30 46h199" stroke="#ffc2da" stroke-width="2" opacity=".7"/>
            <rect x="-2" y="219" width="264" height="20" rx="3" fill="url(#press-steel)"/>
            <g class="press-paper-path" clip-path="url(#press-output)"><g class="press-newspaper"><use href="#press-sheet"/><use href="#press-sheet" y="-360"/></g></g>
            <g class="press-front-roller"><rect x="-7" y="87" width="274" height="41" rx="20" fill="url(#press-steel)"/><rect x="6" y="87" width="248" height="41" rx="20" fill="url(#press-ivory)"/><path d="M28 96h204" stroke="#fffaf1" stroke-width="2" opacity=".7"/></g>
            <path d="M-22 66q0-14 16-14h13v182h-29Zm268-14h13q18 0 18 14v168h-31Z" fill="url(#press-ivory)" stroke="#a49e92" stroke-width="2"/>
            <g fill="url(#press-steel)" stroke="#aaa"><circle cx="-8" cy="80" r="5"/><circle cx="-8" cy="214" r="5"/><circle cx="260" cy="80" r="5"/><circle cx="260" cy="214" r="5"/></g>
            <g transform="translate(-25 106)"><g class="press-gear" stroke="#b4b1ac" stroke-width="3" fill="none"><circle r="22" fill="#2b2d32"/><circle r="7"/><path d="M0-20v13m0 14v13M-20 0h13m14 0h13M-14-14l9 9m10 10 9 9m-28 0 9-9m10-10 9-9"/></g></g>
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
      if (moveFocus) {
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
