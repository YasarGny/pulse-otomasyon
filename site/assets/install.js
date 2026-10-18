/* Installation is optional. Browser eligibility, not a guessed device, opens the suggestion. */
(() => {
  if (
    window.PULSE_ARCHIVE ||
    !window.isSecureContext ||
    !/^https?:$/.test(location.protocol)
  )
    return;
  const base = new URL("../", document.currentScript.src);
  const $ = (selector) => document.querySelector(selector);
  const mode = matchMedia("(display-mode: standalone)");
  const standalone = () =>
    mode.matches ||
    matchMedia("(display-mode: fullscreen)").matches ||
    navigator.standalone === true;
  const read = (key) => {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  };
  const write = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch (_) {}
  };
  let installed = standalone() || read("pulse-app-installed") === "true";
  let dismissedUntil = Number(read("pulse-install-dismissed-until")) || 0;
  let deferred = null,
    relatedInstalled = false,
    prompting = false,
    banner = null,
    entry = null,
    dialog = null;
  const ua = navigator.userAgent;
  const safari =
    /Safari\//.test(ua) &&
    !/Chrome|Chromium|CriOS|Edg|FxiOS|OPiOS|Android/.test(ua);
  const appleMobile =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const manual =
    safari &&
    (appleMobile ||
      (/Macintosh/.test(ua) && Number(/Version\/(\d+)/.exec(ua)?.[1]) >= 17));
  const make = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };
  const eligible = () => !installed && !relatedInstalled && !standalone();
  function markInstalled() {
    installed = true;
    deferred = null;
    write("pulse-app-installed", "true");
    if (dialog?.open) dialog.close();
    render();
  }
  function dismiss() {
    dismissedUntil = Date.now() + 30 * 86400000;
    write("pulse-install-dismissed-until", String(dismissedUntil));
    render();
  }
  function help() {
    if (!dialog) {
      dialog = make("dialog", "install-help");
      dialog.setAttribute("aria-labelledby", "install-help-title");
      const heading = make("h2", "", "PULSE’u uygulama olarak ekle");
      heading.id = "install-help-title";
      const steps = make("ol");
      for (const step of appleMobile
        ? [
            "Safari’de Paylaş düğmesine dokun.",
            "Ana Ekrana Ekle’yi seç.",
            "Ekle’ye dokun.",
          ]
        : [
            "Safari’de Dosya menüsünü aç.",
            "Dock’a Ekle’yi seç.",
            "Ekle’ye bas.",
          ])
        steps.append(make("li", "", step));
      const close = make("button", "retry", "Tamam");
      close.type = "button";
      close.addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
          const r = dialog.getBoundingClientRect();
          if (
            event.clientX < r.left ||
            event.clientX > r.right ||
            event.clientY < r.top ||
            event.clientY > r.bottom
          )
            dialog.close();
        }
      });
      dialog.append(heading, steps, close);
      document.body.append(dialog);
    }
    dialog.showModal();
  }
  async function install() {
    if (!eligible() || prompting) return;
    if (!deferred) {
      if (manual) help();
      return;
    }
    const event = deferred;
    deferred = null;
    prompting = true;
    render();
    try {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice.outcome === "dismissed") dismiss();
      // Only appinstalled confirms completion; accepting the dialog alone does not.
    } catch (_) {
      /* The browser retains its own install menu if prompting fails. */
    } finally {
      prompting = false;
      render();
    }
  }
  function render() {
    const shell = $(".site-shell");
    if (!shell) return;
    if (!entry) {
      entry = make("button", "install-entry", "Uygulama olarak ekle");
      entry.type = "button";
      entry.hidden = true;
      entry.addEventListener("click", install);
      $(".foot")?.append(entry);
    }
    const locked =
      document.documentElement.classList.contains("pulse-locked") ||
      document.documentElement.classList.contains("pulse-loading");
    entry.hidden = !eligible() || (!deferred && !manual) || prompting || locked;
    const show =
      eligible() &&
      deferred &&
      !prompting &&
      dismissedUntil <= Date.now() &&
      !locked &&
      document.body.dataset.page === "home";
    if (!show) {
      if (banner) banner.hidden = true;
      return;
    }
    if (!banner) {
      banner = make("aside", "install-card");
      banner.setAttribute("aria-labelledby", "install-title");
      const icon = make("img", "install-icon");
      icon.src = new URL("assets/app-192.png?v=2", base).href;
      icon.alt = "";
      icon.width = icon.height = 44;
      const copy = make("div", "install-copy");
      const heading = make("h2", "", "PULSE elinin altında.");
      heading.id = "install-title";
      copy.append(
        heading,
        make(
          "p",
          "",
          "Haberler ve podcast’ler, ayrı bir uygulama penceresinde.",
        ),
      );
      const add = make("button", "retry install-add", "Uygulamayı ekle");
      add.type = "button";
      add.addEventListener("click", install);
      const close = make("button", "install-dismiss", "×");
      close.type = "button";
      close.setAttribute("aria-label", "Uygulama önerisini kapat");
      close.addEventListener("click", () => {
        $("#main").focus({ preventScroll: true });
        dismiss();
      });
      banner.append(icon, copy, add, close);
      $("#main").before(banner);
    }
    banner.hidden = false;
  }
  window.addEventListener("beforeinstallprompt", async (event) => {
    event.preventDefault();
    if (installed || standalone()) return;
    deferred = event;
    try {
      const apps = await navigator.getInstalledRelatedApps?.();
      relatedInstalled = !!apps?.some(
        (app) =>
          app.platform === "webapp" &&
          (app.id === base.href ||
            app.url === new URL("manifest.webmanifest", base).href),
      );
    } catch (_) {}
    render();
  });
  window.addEventListener("appinstalled", markInstalled);
  mode.addEventListener?.("change", () => {
    if (standalone()) markInstalled();
    else render();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === "pulse-app-installed" && event.newValue === "true")
      markInstalled();
    if (event.key === "pulse-install-dismissed-until") {
      dismissedUntil = Number(event.newValue) || 0;
      render();
    }
  });
  for (const event of ["pulse:navigate", "pulse:rendered", "pulse:locked"])
    window.addEventListener(event, render);
  if (standalone()) markInstalled();
  render();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register(new URL("sw.js", base), {
        scope: base.pathname,
        updateViaCache: "none",
      })
      .catch(() => {});
  }
})();
