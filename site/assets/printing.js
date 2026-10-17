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
      art.innerHTML = `<svg class="press-illustration" viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <ellipse cx="200" cy="277" rx="123" ry="8" fill="#000" opacity=".15" stroke="none"/>
        <path d="m91 49 14-8h202l-14 8Z" fill="#f0ece4" stroke="#a8a59f"/>
        <path d="m293 49 14-8v203l-14 9Z" fill="#b8b5b0" stroke="#918f8c"/>
        <rect x="91" y="49" width="202" height="17" rx="4" fill="#ece7df" stroke="#a8a59f"/>
        <rect x="91" y="59" width="17" height="194" rx="5" fill="#e4dfd7" stroke="#aaa69f"/>
        <rect x="276" y="59" width="17" height="194" rx="5" fill="#e4dfd7" stroke="#aaa69f"/>
        <rect x="108" y="84" width="168" height="27" rx="13" fill="#d783a9" stroke="#9b5f7a"/>
        <path d="M120 90h140" stroke="#efb9d1" stroke-width="3"/>
        <rect x="108" y="127" width="168" height="22" rx="11" fill="#6d7176" stroke="#292c30"/>
        <path d="M120 132h140" stroke="#999da2" stroke-width="2"/>
        <rect x="92" y="238" width="201" height="15" rx="3" fill="#c9c4bc" stroke="#a8a59f"/>
        <g class="press-newspaper" stroke="none"><rect x="131" y="144" width="122" height="121" rx="2" fill="#f0ece5"/>
        <text x="142" y="193" fill="#202125" font-size="23" font-family="Arial,sans-serif" font-weight="800" letter-spacing="-1">PULSE<tspan fill="#ad366c">.</tspan></text>
        <path d="M142 202h100" stroke="#4f5155"/>
        <rect x="142" y="212" width="43" height="26" fill="#d387a7" rx="1"/>
        <path d="M194 214h48m-48 7h48m-48 7h48m-100 18h100m-100 7h80" stroke="#acaaa7" stroke-width="3"/>
        </g>
        <rect x="108" y="146" width="168" height="23" rx="11" fill="#b5b7b9" stroke="#6c6f73"/>
        <path d="M120 151h140" stroke="#d9d9d9" stroke-width="2"/>
        <circle cx="99" cy="181" r="4" fill="#d783a9" stroke="#98607a"/>
        <path d="M85 254h29m156 0h29" stroke="#8e8c89" stroke-width="5"/>
      </svg>`;
      if (mode === "offline") art.hidden = true;
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
