/* User-requested installation from the footer; never an automatic promotion. */
(() => {
  if (window.PULSE_ARCHIVE || !window.isSecureContext ||
      !/^https?:$/.test(location.protocol)) return;
  const base = new URL("../", document.currentScript.src);
  const $ = (selector) => document.querySelector(selector);
  const mode = matchMedia("(display-mode: standalone)");
  const fullMode = matchMedia("(display-mode: fullscreen)");
  const standalone = () => mode.matches || fullMode.matches || navigator.standalone === true;
  // Old install/dismissal history cannot establish whether the app is installed now.
  for (const key of ["pulse-app-installed", "pulse-install-dismissed-until"])
    try { localStorage.removeItem(key); } catch (_) {}
  let confirmedThisPage = false, relatedInstalled = false, deferred = null,
    prompting = false, dialog = null, checkVersion = 0;
  const entry = $(".foot .install-entry");
  if (!entry) return;
  const ua = navigator.userAgent;
  const appleMobile = /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const safari = /Safari\//.test(ua) && !/Chrome|Chromium|CriOS|Edg|FxiOS|OPiOS|Android/.test(ua);
  const eligible = () => !standalone() && !confirmedThisPage && !relatedInstalled;
  function render() {
    const locked = document.documentElement.classList.contains("pulse-locked") ||
      document.documentElement.classList.contains("pulse-loading");
    entry.hidden = !eligible() || locked;
    entry.disabled = prompting;
    if (entry.hidden && dialog?.open) dialog.close();
    if (entry.hidden && document.activeElement === entry)
      $(".foot .brand")?.focus({ preventScroll: true });
  }
  async function checkInstalled() {
    const version = ++checkVersion;
    if (typeof navigator.getInstalledRelatedApps !== "function") return;
    try {
      const apps = await navigator.getInstalledRelatedApps();
      if (version !== checkVersion) return;
      relatedInstalled = Array.isArray(apps) && apps.some((app) =>
        app.platform === "webapp" &&
        (app.id === base.href || app.url === new URL("manifest.webmanifest", base).href));
    } catch (_) {
      if (version !== checkVersion) return;
      relatedInstalled = false; // Unknown is not proof of installation.
    }
    render();
  }
  function help() {
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "install-help";
      dialog.setAttribute("aria-labelledby", "install-help-title");
      const heading = document.createElement("h2");
      heading.id = "install-help-title";
      heading.textContent = "PULSE’u uygulama olarak ekle";
      const steps = document.createElement("ol");
      const instructions = appleMobile ? [
        "Tarayıcının Paylaş menüsünü aç.",
        "Ana Ekrana Ekle’yi seç. Seçenek yoksa siteyi Safari’de aç.",
        "Ekle’ye dokun.",
      ] : safari && /Macintosh/.test(ua) ? [
        "Safari’de Dosya menüsünü aç.", "Dock’a Ekle’yi seç.", "Ekle’ye bas.",
      ] : /Android/.test(ua) ? [
        "Tarayıcının ⋮ menüsünü aç.",
        "Uygulamayı yükle veya Ana ekrana ekle’yi seç.",
        "Seçenek görünmüyorsa siteyi güncel Chrome veya Edge ile aç.",
      ] : [
        "Adres çubuğundaki yükleme simgesine veya tarayıcı menüsüne bak.",
        "Uygulamayı yükle veya Bu siteyi uygulama olarak yükle’yi seç.",
        "Seçenek görünmüyorsa siteyi güncel Chrome veya Edge ile aç.",
      ];
      for (const instruction of instructions) {
        const li = document.createElement("li");
        li.textContent = instruction;
        steps.append(li);
      }
      const close = document.createElement("button");
      close.className = "retry";
      close.type = "button";
      close.textContent = "Tamam";
      close.addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (event) => {
        if (event.target !== dialog) return;
        const r = dialog.getBoundingClientRect();
        if (event.clientX < r.left || event.clientX > r.right ||
            event.clientY < r.top || event.clientY > r.bottom) dialog.close();
      });
      dialog.addEventListener("close", () => {
        if ($(".site-shell")?.inert) return;
        (entry.hidden ? $(".foot .brand") : entry)?.focus({ preventScroll: true });
      });
      dialog.append(heading, steps, close);
      document.body.append(dialog);
    }
    if (!dialog.open) dialog.showModal();
  }
  async function install() {
    if (!eligible() || prompting) return;
    if (!deferred) { help(); return; }
    const event = deferred;
    deferred = null;
    prompting = true;
    render();
    try {
      await event.prompt();
      await event.userChoice;
      // Accepting a prompt alone is not confirmation; appinstalled confirms it.
    } catch (_) {
      if (eligible()) help();
    } finally {
      prompting = false;
      render();
    }
  }
  entry.addEventListener("click", install);
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    if (standalone()) return;
    // A fresh browser eligibility event supersedes a previous install signal.
    ++checkVersion;
    deferred = event;
    confirmedThisPage = relatedInstalled = false;
    if (dialog?.open) dialog.close();
    render();
  });
  window.addEventListener("appinstalled", () => {
    ++checkVersion;
    confirmedThisPage = true;
    deferred = null;
    render();
    if (dialog?.open) dialog.close();
  });
  for (const display of [mode, fullMode])
    display.addEventListener?.("change", () => { render(); checkInstalled(); });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) { render(); checkInstalled(); }
  });
  window.addEventListener("focus", checkInstalled);
  for (const event of ["pulse:navigate", "pulse:rendered", "pulse:locked"])
    window.addEventListener(event, render);
  render();
  checkInstalled();
  if ("serviceWorker" in navigator)
    navigator.serviceWorker.register(new URL("sw.js", base), {
      scope: base.pathname, updateViaCache: "none",
    }).catch(() => {});
})();
