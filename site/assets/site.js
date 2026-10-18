/* Static pages first; one persistent audio session and optional same-origin navigation. */
(() => {
  "use strict";
  const base = new URL("../", document.currentScript.src);
  // Header/footer and app identity survive main-content swaps. Freeze their
  // original targets before pushState changes the relative-URL base.
  if (!window.PULSE_ARCHIVE)
    for (const link of document.querySelectorAll(
      '.nav a[href], .foot a[href], link[rel="manifest"], link[rel="icon"], link[rel="apple-touch-icon"]',
    ))
      link.href = new URL(link.getAttribute("href"), location.href).href;
  const readingScroll = () => window.scrollY;
  const scrollReadingTo = (top) =>
    window.scrollTo({ top, behavior: "instant" });
  const $ = (s, root = document) => root.querySelector(s);
  const all = (s, root = document) => [...root.querySelectorAll(s)];
  const make = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const icons = {
    play: '<path d="m8 5 12 7-12 7Z" fill="currentColor" stroke="none"/>',
    pause: '<path d="M8 6v12M16 6v12" stroke-width="4"/>',
    back: '<path d="M5 9a8 8 0 1 1-1 8M5 3v6h6"/><text x="12" y="17" text-anchor="middle" fill="currentColor" stroke="none" font-size="8" font-family="Arial,sans-serif" font-weight="700">10</text>',
    forward:
      '<path d="M19 9a8 8 0 1 0 1 8M19 3v6h-6"/><text x="12" y="17" text-anchor="middle" fill="currentColor" stroke="none" font-size="8" font-family="Arial,sans-serif" font-weight="700">10</text>',
    volume:
      '<path d="m11 5-5 4H3v6h3l5 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    mute: '<path d="m11 5-5 4H3v6h3l5 4ZM16 9l6 6m0-6-6 6"/>',
    settings: '<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
  };
  const icon = (n, name) => {
    if (n.dataset.icon === name) return;
    n.dataset.icon = name;
    n.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true">' + icons[name] + "</svg>";
  };
  const button = (cls, name, label) => {
    const n = make("button", cls);
    n.type = "button";
    n.setAttribute("aria-label", label);
    icon(n, name);
    return n;
  };
  const format = (s) => {
    s = Math.max(0, Math.floor(Number.isFinite(s) ? s : 0));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  };
  let release = null,
    selected = null,
    pageEvents = null,
    pendingNav = null,
    listState = null;
  let selectedRelease = null, playRequest = 0;
  let bufferingTimer = null, showBuffering = false;
  let renderedURL = new URL(location.href);
  let selectedDuration = 0,
    loading = false,
    failed = false,
    hasStarted = false;
  const host = make("div", "audio-session");
  const audio = make("audio");
  audio.preload = "none";
  host.append(audio);
  document.body.append(host);
  const full = make("div", "player");
  full.hidden = true;
  full.setAttribute("role", "group");
  const label = make("div", "player-label");
  const playerHeading = make("div", "player-heading");
  const playerInfo = make("div", "player-info");
  const playerSubtitle = make("p", "player-subtitle");
  const playerDuration = make("p", "player-duration");
  playerInfo.append(label, playerSubtitle, playerDuration);
  const playerCover = make("img", "player-cover");
  playerCover.alt = "";
  playerCover.width = playerCover.height = 64;
  playerHeading.append(playerCover, playerInfo);
  const controls = make("div", "player-controls");
  const back = button("player-skip", "back", "10 saniye geri al");
  const play = button("player-play", "play", "Oynat");
  const forward = button("player-skip", "forward", "10 saniye ileri al");
  const speed = make("button", "player-speed", "1×");
  speed.type = "button";
  controls.append(back, play, forward);
  const seek = make("input", "player-seek");
  seek.type = "range";
  seek.min = "0";
  seek.max = "1";
  seek.step = ".1";
  seek.value = "0";
  seek.disabled = true;
  seek.setAttribute("aria-label", "Ses ilerlemesi");
  const times = make("div", "player-times");
  const current = make("span", "", "0:00"),
    end = make("span", "", "0:00");
  times.append(current, end);
  const bottom = make("div", "player-bottom");
  const episode = make("span", "player-date");
  episode.hidden = true;
  const mute = button("player-mute", "volume", "Sesi kapat");
  mute.setAttribute("aria-pressed", "false");
  const volume = make("input", "player-volume");
  volume.type = "range";
  volume.min = "0";
  volume.max = "1";
  volume.step = ".05";
  volume.value = "1";
  volume.setAttribute("aria-label", "Ses seviyesi");
  // iOS exposes device volume rather than a writable HTMLMediaElement volume.
  if (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  )
    volume.hidden = true;
  const deviceVolume = make("span", "device-volume", "Ses: cihaz tuşları");
  deviceVolume.hidden = !volume.hidden;
  const volumeControls = make("div", "player-volume-controls");
  volumeControls.append(mute, volume, deviceVolume);
  bottom.append(volumeControls, speed, episode);
  const status = make("p", "audio-status");
  status.setAttribute("role", "status");
  const retry = make("button", "retry", "Tekrar dene");
  retry.type = "button";
  retry.hidden = true;
  full.append(playerHeading, controls, seek, times, bottom, status, retry);
  host.append(full);
  const mini = make("div", "persistent-audio");
  mini.hidden = true;
  mini.setAttribute("role", "region");
  mini.setAttribute("aria-label", "Dinleme kontrolleri");
  const minibar = make("div", "mini-bar"),
    miniTitle = make("div", "mini-title"),
    miniLink = make("a"),
    miniTime = make("span", "mini-time"),
    miniStatus = make("span", "mini-status sr-only");
  miniStatus.setAttribute("role", "status");
  const miniSubtitle = make("span", "mini-subtitle");
  miniTitle.append(miniLink, miniSubtitle, miniTime, miniStatus);
  const close = button(
    "mini-close",
    "close",
    "Dinlemeyi durdur ve oynatıcıyı kapat",
  );
  const miniCover = make("img", "mini-cover");
  miniCover.alt = "";
  miniCover.width = miniCover.height = 44;
  const miniMore = button("mini-more", "settings", "Oynatıcı kontrollerini aç");
  const panel = make("div", "floating-panel");
  panel.hidden = true;
  panel.id = "floating-player-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Oynatıcı kontrolleri");
  const collapse = button("mini-collapse", "close", "Kontrolleri küçült");
  close.textContent = "Dinlemeyi bitir";
  close.setAttribute("aria-label", "Dinlemeyi bitir");
  let lastAudioTrigger = null;
  miniMore.setAttribute("aria-expanded", "false");
  miniMore.setAttribute("aria-controls", "floating-player-panel");
  const miniDetails = make("div", "mini-details");
  miniDetails.id = "mini-details";
  miniDetails.hidden = true;
  minibar.append(miniCover, miniTitle, collapse);
  panel.append(minibar, miniDetails, close);
  mini.append(panel, miniMore);
  host.append(mini);
  const rates = [0.75, 1, 1.1, 1.2, 1.25, 1.5, 2];
  const progressKey = "pulse-listening-v1";
  let savedListening = {}, pendingPosition = 0, lastProgressWrite = 0;
  try {
    const stored = JSON.parse(localStorage.getItem(progressKey));
    if (stored && typeof stored === "object" && !Array.isArray(stored))
      savedListening = stored;
  } catch (_) {}
  const assetKey = (section, kind, context = release) => {
    const asset = context?.editions[section]?.[kind];
    return asset ? context.manifest.publish_date + ":" + section + ":" + kind + ":" + asset.sha256 : "";
  };
  function remembered(section, kind, context = release) {
    const record = savedListening[assetKey(section, kind, context)];
    const duration = context?.editions[section]?.[kind]?.duration || 0;
    return record && Number.isFinite(record.position) && record.position >= 3 &&
      record.position < duration - 5 && rates.includes(record.rate)
      ? record : null;
  }
  function persistListening(force = false) {
    if (!selected || !hasStarted || !audio.readyState || failed || pendingPosition)
      return;
    if (!force && Date.now() - lastProgressWrite < 5000) return;
    lastProgressWrite = Date.now();
    const key = assetKey(selected.section, selected.kind, selectedRelease);
    if (audio.ended || audio.currentTime >= selectedDuration - 5 || audio.currentTime < 3)
      delete savedListening[key];
    else savedListening[key] = { position: audio.currentTime, rate: audio.playbackRate };
    try { localStorage.setItem(progressKey, JSON.stringify(savedListening)); } catch (_) {}
  }
  const restart = make("button", "player-restart", "Baştan dinle");
  restart.type = "button";
  full.append(restart);
  restart.onclick = () => {
    pendingPosition = 0;
    if (audio.readyState) audio.currentTime = 0;
    persistListening(true);
    progress();
  };
  audio.addEventListener("loadedmetadata", () => {
    if (pendingPosition && Number.isFinite(audio.duration)) {
      audio.currentTime = Math.min(pendingPosition, Math.max(0, audio.duration - 1));
      pendingPosition = 0;
      progress();
    }
  });
  audio.addEventListener("timeupdate", () => persistListening());
  for (const event of ["pause", "seeked", "ended", "ratechange"])
    audio.addEventListener(event, () => persistListening(true));
  window.addEventListener("pagehide", () => persistListening(true));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) persistListening(true);
  });
  function title() {
    return selected
      ? selected.kind === "summary"
        ? "Günün Özeti · " +
          (selected.section === "teknoloji" ? "Teknoloji" : "Oyun")
        : selectedRelease.editions[selected.section].podcast.title
      : "";
  }
  function update() {
    if (!loading || failed) {
      clearTimeout(bufferingTimer); bufferingTimer = null; showBuffering = false;
    } else if (!showBuffering && bufferingTimer === null) {
      bufferingTimer = setTimeout(() => {
        bufferingTimer = null;
        if (loading && !failed) { showBuffering = true; update(); }
      }, 350);
    }
    play.dataset.buffering = miniMore.dataset.buffering = String(showBuffering);
    const playing = !!selected && !audio.paused && !audio.ended && !failed;
    for (const n of [play]) {
      icon(n, playing ? "pause" : "play");
      n.setAttribute(
        "aria-label",
        title() + ": " + (playing ? "Duraklat" : "Oynat"),
      );
      n.setAttribute("aria-busy", String(loading));
    }
    all(".audio-start").forEach((n) => {
      const active =
        selected &&
        n.dataset.section === selected.section &&
        n.dataset.kind === selected.kind &&
        selectedRelease.manifest.publish_date === release?.manifest.publish_date &&
        selectedRelease.editions[selected.section][selected.kind].sha256 === release?.editions[selected.section]?.[selected.kind]?.sha256;
      icon(n, active && playing ? "pause" : "play");
      n.setAttribute("aria-pressed", String(!!active && playing));
      n.setAttribute("aria-busy", String(!!active && loading));
      const listenLabel = n.closest(".listen-player")?.querySelector("span");
      if (listenLabel)
        listenLabel.textContent =
          active && failed
            ? "Tekrar dene"
            : active && playing
              ? "Duraklat"
              : "Dinle";
      n.dataset.state = active
        ? failed
          ? "error"
          : showBuffering
            ? "loading"
            : playing
              ? "playing"
              : "paused"
        : "idle";
      n.setAttribute(
        "aria-label",
        (n.dataset.kind === "podcast"
          ? n.dataset.section === "teknoloji"
            ? "Yeni Sekme"
            : "Moradon FM"
          : "Günün Özeti · " +
            (n.dataset.section === "teknoloji" ? "Teknoloji" : "Oyun")) +
          ": " +
          (active && failed
            ? "Tekrar dene"
            : active && playing
              ? "Duraklat"
              : remembered(n.dataset.section, n.dataset.kind)
                ? "Kaldığın yerden dinle"
                : "Oynat"),
      );
    });
    const state = failed
      ? "Ses yüklenemedi."
      : loading
        ? "Ses yükleniyor…"
        : "";
    full.classList.toggle("is-loading", showBuffering && !failed);
    full.classList.toggle("is-error", failed);
    status.textContent = failed ? "Ses yüklenemedi." : "";
    miniStatus.textContent = showBuffering && !failed ? state : "";
    retry.hidden = !failed;
    mini.hidden =
      !selected ||
      !hasStarted;
    document.body.classList.toggle("has-mini", !mini.hidden);
    icon(miniMore, "settings");
    syncChapters();
    miniMore.setAttribute("aria-busy", String(loading));
    miniMore.dataset.state = failed
      ? "error"
      : showBuffering
        ? "loading"
        : playing
          ? "playing"
          : "paused";
    miniMore.setAttribute(
      "aria-label",
      (panel.hidden ? "Oynatıcı kontrollerini aç" : "Kontrolleri küçült") +
        ": " +
        title() +
        (failed ? ", ses yüklenemedi" : playing ? ", çalıyor" : ", duraklatıldı"),
    );
    miniMore.style.setProperty(
      "--progress",
      ((Number(seek.value) / Number(seek.max)) * 360 || 0) + "deg",
    );
    const rate = audio.playbackRate;
    speed.textContent = rate + "×";
    speed.setAttribute(
      "aria-label",
      "Hız " + rate + "×, değiştirmek için basın",
    );
  }
  function syncMediaSession() {
    if (!("mediaSession" in navigator)) return;
    try {
      navigator.mediaSession.playbackState =
        !selected || audio.ended ? "none" : audio.paused ? "paused" : "playing";
      if (!selected) {
        navigator.mediaSession.metadata = null;
        navigator.mediaSession.setPositionState?.();
      } else if (Number.isFinite(audio.duration) && audio.duration > 0) {
        navigator.mediaSession.setPositionState?.({
          duration: audio.duration,
          playbackRate: audio.playbackRate,
          position: Math.max(0, Math.min(audio.duration, audio.currentTime)),
        });
      }
    } catch (_) {}
  }
  for (const event of [
    "play",
    "pause",
    "ended",
    "ratechange",
    "loadedmetadata",
    "timeupdate",
    "seeked",
  ])
    audio.addEventListener(event, syncMediaSession);
  function progress() {
    const duration = Number.isFinite(audio.duration)
      ? audio.duration
      : selectedDuration;
    seek.max = String(duration || 1);
    seek.disabled = !audio.readyState || !Number.isFinite(audio.duration) || audio.duration <= 0;
    seek.value = String(audio.currentTime || 0);
    current.textContent = format(audio.currentTime);
    end.textContent = format(duration);
    playerDuration.textContent = format(duration);
    seek.style.setProperty(
      "--played",
      ((audio.currentTime || 0) / (duration || 1)) * 100 + "%",
    );
    miniMore.style.setProperty(
      "--progress",
      ((audio.currentTime || 0) / (duration || 1)) * 360 + "deg",
    );
    miniTime.textContent = format(audio.currentTime) + " / " + format(duration);
    seek.setAttribute(
      "aria-valuetext",
      current.textContent + " / " + end.textContent,
    );
    syncChapters();
  }
  function mount() {
    miniDetails.insertBefore(full, chapterPanel);
    full.hidden = false;
  }
  function configure(section, kind, context = release) {
    if (
      !context ||
      !context.editions[section]?.[kind] ||
      !["podcast", "summary"].includes(kind)
    )
      return false;
    const asset = context.editions[section][kind];
    const changed =
      !selected || selected.section !== section || selected.kind !== kind ||
      selectedRelease.editions[section][kind].sha256 !== asset.sha256 ||
      selectedRelease.manifest.publish_date !== context.manifest.publish_date;
    if (changed) {
      persistListening(true);
      collapsePanel(false);
      audio.pause();
      playRequest++;
      selected = { section, kind };
      selectedRelease = context;
      const previous = remembered(section, kind, context);
      pendingPosition = previous?.position || 0;
      selectedDuration = asset.duration;
      audio.src = new URL(asset.file, context.url).href;
      audio.load();
      audio.playbackRate = previous?.rate || 1;
      loading = false;
      failed = false;
      hasStarted = false;
    }
    const coverName = section === "teknoloji" ? "yeni-sekme" : "moradon-fm";
    const coverUrl = new URL("assets/covers/" + coverName + "-192.webp", base)
      .href;
    playerCover.hidden = miniCover.hidden = kind !== "podcast";
    if (kind === "podcast") playerCover.src = miniCover.src = coverUrl;
    label.textContent = title();
    playerSubtitle.textContent =
      kind === "podcast"
        ? (section === "teknoloji" ? "Teknoloji" : "Oyun") +
          " podcast’i · Yaşar ve Necdet"
        : (section === "teknoloji" ? "Teknoloji" : "Oyun") + " · Günün Özeti";
    playerSubtitle.hidden = miniSubtitle.hidden = kind !== "podcast";
    full.setAttribute("aria-label", title() + " oynatıcı");
    episode.textContent = context.manifest.publish_date
      .split("-")
      .reverse()
      .join(".");
    miniSubtitle.textContent = (section === "teknoloji" ? "Teknoloji" : "Oyun") +
      (kind === "podcast" ? " podcast’i · " : " · ") + episode.textContent;
    miniLink.textContent = title();
    miniLink.href = new URL(
      section + "/dinle/index.html" + (kind === "summary" ? "?ses=ozet" : ""),
      base,
    ).href;
    if (context.manifest.publish_date !== release?.manifest.publish_date) miniLink.removeAttribute("href");
    loadSelectedChapters();
    progress();
    update();
    return true;
  }
  async function toggle() {
    if (!selected) return;
    if (document.getElementById("main").contains(document.activeElement))
      lastAudioTrigger = document.activeElement;
    if (!audio.paused && !failed) {
      playRequest++;
      audio.pause();
      loading = false;
      update();
      return;
    }
    if (failed) {
      pendingPosition = audio.currentTime || pendingPosition;
      audio.load();
    }
    if (audio.ended) { pendingPosition = 0; audio.currentTime = 0; }
    hasStarted = true;
    loading = true;
    failed = false;
    update();
    const request = ++playRequest;
    try {
      await audio.play();
    } catch (error) {
      if (request === playRequest && error.name !== "AbortError") {
        failed = true;
        loading = false;
      }
    } finally {
      if (request === playRequest) update();
    }
  }
  for (const n of [play]) n.addEventListener("click", toggle);
  close.addEventListener("click", () => {
    persistListening(true);
    const restoreFocus = mini.contains(document.activeElement);
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    selected = null;
    selectedRelease = null;
    playRequest++;
    syncMediaSession();
    miniDetails.hidden = panel.hidden = true;
    miniMore.setAttribute("aria-expanded", "false");
    hasStarted = false;
    full.hidden = true;
    loading = failed = false;
    update();
    if (
      restoreFocus &&
      !document.documentElement.classList.contains("pulse-locked")
    )
      (lastAudioTrigger?.isConnected && lastAudioTrigger.getClientRects().length
        ? lastAudioTrigger
        : $("#main")
      ).focus({
        preventScroll: true,
      });
  });
  function collapsePanel(restoreFocus = false) {
    panel.hidden = miniDetails.hidden = true;
    miniMore.setAttribute("aria-expanded", "false");
    if (mini.contains(full)) {
      host.append(full);
      full.hidden = true;
    }
    update();
    titleMotion?.sync();
    if (restoreFocus && !mini.hidden) miniMore.focus({ preventScroll: true });
  }
  miniMore.onclick = () => {
    if (!panel.hidden) {
      collapsePanel(true);
      return;
    }
    panel.hidden = miniDetails.hidden = false;
    miniMore.setAttribute("aria-expanded", "true");
    mount();
    titleMotion.refresh();
    update();
    play.focus({ preventScroll: true });
  };
  collapse.onclick = () => collapsePanel(true);
  document.addEventListener("pointerdown", (event) => {
    if (!panel.hidden && !mini.contains(event.target)) collapsePanel(false);
  });
  document.addEventListener("focusin", (event) => {
    if (!panel.hidden && !mini.contains(event.target)) collapsePanel(false);
  });
  mini.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      event.preventDefault();
      collapsePanel(true);
    }
  });
  function jump(delta) {
    if (audio.readyState)
      audio.currentTime = Math.max(
        0,
        Math.min(
          Number.isFinite(audio.duration) ? audio.duration : selectedDuration,
          audio.currentTime + delta,
        ),
      );
    progress();
  }
  back.onclick = () => jump(-10);
  forward.onclick = () => jump(10);
  seek.oninput = () => {
    if (audio.readyState) audio.currentTime = Number(seek.value);
    progress();
  };
  speed.onclick = () => {
    audio.playbackRate =
      rates[(rates.indexOf(audio.playbackRate) + 1) % rates.length];
    update();
  };
  const updateVolume = () => {
    const silent = audio.muted || audio.volume === 0;
    volume.style.setProperty(
      "--level",
      (silent ? 0 : audio.volume * 100) + "%",
    );
    icon(mute, silent ? "mute" : "volume");
    mute.setAttribute("aria-label", silent ? "Sesi aç" : "Sesi kapat");
    mute.setAttribute("aria-pressed", String(silent));
  };
  mute.onclick = () => {
    audio.muted = !audio.muted;
    updateVolume();
  };
  volume.oninput = () => {
    audio.volume = Number(volume.value);
    audio.muted = audio.volume === 0;
    updateVolume();
  };
  audio.addEventListener("volumechange", updateVolume);
  retry.onclick = () => { toggle(); };
  for (const name of [
    "timeupdate",
    "loadedmetadata",
    "durationchange",
    "seeked",
  ])
    audio.addEventListener(name, progress);
  audio.addEventListener("waiting", () => {
    loading = true;
    update();
  });
  for (const name of ["playing", "canplay", "pause", "ended"])
    audio.addEventListener(name, () => {
      loading = false;
      update();
    });
  audio.addEventListener("error", () => {
    if (selected) {
      failed = true;
      loading = false;
      update();
    }
  });
  audio.addEventListener("play", () => {
    hasStarted = true;
    all("audio").forEach((other) => {
      if (other !== audio) other.pause();
    });
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: title(),
          artist: selected.kind === "podcast" ? "Yaşar ve Necdet" : "PULSE",
          album: "PULSE",
          artwork:
            selected.kind === "podcast"
              ? [{ src: playerCover.src, sizes: "192x192", type: "image/webp" }]
              : [],
        });
      } catch (_) {}
      for (const [action, handler] of Object.entries({
        play: () => audio.play().catch(() => {}),
        pause: () => audio.pause(),
        stop: () => close.click(),
        seekbackward: () => jump(-10),
        seekforward: () => jump(10),
        seekto: (details) => {
          if (
            Number.isFinite(details.seekTime) &&
            Number.isFinite(audio.duration)
          )
            audio.currentTime = Math.max(
              0,
              Math.min(audio.duration, details.seekTime),
            );
        },
      })) {
        try {
          navigator.mediaSession.setActionHandler(action, handler);
        } catch (_) {}
      }
    }
    update();
  });
  const chapterCache = new Map();
  let chapterRegistry = null;
  async function chaptersFor(asset) {
    if (!asset || !/^[a-f0-9]{64}$/.test(asset.sha256)) return null;
    if (!chapterCache.has(asset.sha256)) chapterCache.set(asset.sha256, (async () => {
      try {
        const embedded = window.PULSE_RELEASE?.chapters?.[asset.sha256];
        if (embedded) return PulseListening.validate(embedded, asset);
        if (window.PULSE_ARCHIVE) return null;
        if (!chapterRegistry) chapterRegistry = fetch(new URL("assets/chapters/index.json", base),
          { cache: "no-cache", signal: AbortSignal.timeout(10000) }).then(async response => {
            if (!response.ok) return {};
            const text = await response.text();
            return text.length < 200000 ? JSON.parse(text) : {};
          }).catch(() => ({}));
        const registry = await chapterRegistry;
        return PulseListening.validate(registry[asset.sha256], asset);
      } catch (_) { return null; }
    })());
    return chapterCache.get(asset.sha256);
  }
  const tabs = make("div", "player-tabs");
  tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Oynatıcı görünümü");
  const transportTab = make("button", "", "Oynatıcı"), chapterTab = make("button", "", "Bu bölümde");
  const chapterPanel = make("div", "player-chapters");
  chapterPanel.hidden = tabs.hidden = true;
  const chapterList = make("ol", "chapter-list");
  chapterPanel.append(chapterList);
  let currentChapters = null, chapterAsset = null;
  for (const [tab, id, controlled] of [[transportTab,"transport-tab","transport-pane"],[chapterTab,"chapters-tab","chapters-pane"]]) {
    tab.type = "button"; tab.id = id; tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", controlled);
  }
  const transportExtras = make("div", "transport-extras");
  transportExtras.id = "transport-pane"; chapterPanel.id = "chapters-pane";
  transportExtras.append(bottom, restart); full.append(transportExtras);
  for (const [pane, tab] of [[transportExtras,transportTab],[chapterPanel,chapterTab]]) {
    pane.setAttribute("role","tabpanel"); pane.setAttribute("aria-labelledby",tab.id);
  }
  tabs.append(transportTab, chapterTab);
  miniDetails.prepend(tabs); miniDetails.append(chapterPanel);
  // Keep the same transport available while browsing chapters, rather than another audio element.
  function chooseTab(chapters, scroll = true) {
    chapterPanel.hidden = !chapters;
    transportExtras.hidden = chapters;
    full.classList.toggle("chapter-mode", chapters);
    for (const [tab, active] of [[transportTab,!chapters],[chapterTab,chapters]]) {
      tab.setAttribute("aria-selected",String(active)); tab.tabIndex = active ? 0 : -1;
    }
    if (chapters && scroll) chapterList.querySelector('[aria-current="true"]')?.scrollIntoView({ block:"nearest" });
  }
  chooseTab(false);
  transportTab.onclick = () => chooseTab(false);
  chapterTab.onclick = () => chooseTab(true);
  tabs.onkeydown = e => {
    if (!["ArrowLeft","ArrowRight","Home","End"].includes(e.key)) return;
    e.preventDefault();
    const next = e.key === "Home" ? transportTab : e.key === "End" ? chapterTab : document.activeElement === transportTab ? chapterTab : transportTab;
    chooseTab(next === chapterTab); next.focus();
  };
  const scrollingTitle = make("button", "scrolling-title");
  scrollingTitle.type = "button"; scrollingTitle.setAttribute("aria-expanded","false");
  scrollingTitle.setAttribute("aria-controls","full-topic-title");
  const titleTrack = make("span", "title-track"); scrollingTitle.append(titleTrack);
  const fullTopicTitle = make("p", "full-topic-title"); fullTopicTitle.id = "full-topic-title"; fullTopicTitle.hidden = true;
  minibar.after(scrollingTitle, fullTopicTitle);
  scrollingTitle.hidden = true;
  const titleMotion = PulseListening.marquee(scrollingTitle,titleTrack,()=>panel.hidden || !fullTopicTitle.hidden);
  scrollingTitle.onclick = () => {
    fullTopicTitle.hidden = !fullTopicTitle.hidden;
    scrollingTitle.setAttribute("aria-expanded",String(!fullTopicTitle.hidden)); titleMotion.sync();
  };
  function chapterRows(data, section, kind, context = release) {
    const date = context.manifest.publish_date;
    return data.chapters.map(chapter => {
      const li = make("li"), button = make("button", "chapter-jump");
      button.type = "button"; button.dataset.section = section; button.dataset.kind = kind;
      button.dataset.start = chapter.start; button.dataset.sha = data.audio_sha256; button.dataset.date = date;
      button.append(make("span","chapter-time",format(chapter.start)), make("span","chapter-title",chapter.title), make("span","chapter-indicator"), make("span","sr-only",", buradan dinle"));
      $(".chapter-indicator",button).setAttribute("aria-hidden","true");
      icon($(".chapter-indicator",button), "play");

      button.onclick = () => seekChapter(section,kind,chapter.start,data.audio_sha256,date);
      li.append(button); return li;
    });
  }
  async function seekChapter(section,kind,time,sha,date) {
    const keepOpen = !panel.hidden;
    const asset = release?.editions[section]?.[kind];
    // The open player can still belong to yesterday's immutable release.
    const active = selected?.section === section && selected?.kind === kind &&
      selectedRelease?.editions[section]?.[kind]?.sha256 === sha && selectedRelease.manifest.publish_date === date;
    if (!active && (!asset || asset.sha256 !== sha || release.manifest.publish_date !== date || !configure(section,kind))) return;
    hasStarted = true;
    if (failed || audio.error) audio.load();
    failed = false;
    if (audio.readyState && Number.isFinite(audio.duration)) {
      pendingPosition = 0; audio.currentTime = Math.min(time, Math.max(0,audio.duration - .1));
    } else pendingPosition = time;
    if (keepOpen) { panel.hidden = miniDetails.hidden = false; miniMore.setAttribute("aria-expanded","true"); mount(); }
    if (audio.paused) await toggle();
    progress(); update();
  }
  function syncChapters() {
    const data = currentChapters;
    const index = data ? PulseListening.activeIndex(data.chapters, audio.currentTime) : -1;
    const asset = selected && selectedRelease.editions[selected.section][selected.kind];
    for (const item of all(".chapter-jump")) {
      const same = asset?.sha256 === item.dataset.sha && selectedRelease.manifest.publish_date === item.dataset.date;
      const isActive = same && data && data.chapters[index]?.start === Number(item.dataset.start);
      if (isActive) item.setAttribute("aria-current","true"); else item.removeAttribute("aria-current");
      item.classList.toggle("is-playing",!!isActive && !audio.paused && !audio.ended);
      icon($(".chapter-indicator",item), isActive && !audio.paused && !audio.ended ? "pause" : "play");
    }
    const text = index >= 0 ? data.chapters[index].title : "";
    if (titleTrack.textContent !== text) {
      titleTrack.textContent = fullTopicTitle.textContent = text;
      fullTopicTitle.hidden = true; scrollingTitle.setAttribute("aria-expanded","false");
      scrollingTitle.hidden = !text; titleMotion.refresh();
    }
  }
  async function loadSelectedChapters() {
    const asset = selectedRelease.editions[selected.section][selected.kind];
    if (chapterAsset === asset.sha256) return;
    chapterAsset = asset.sha256; currentChapters = null; tabs.hidden = true;
    chapterList.replaceChildren(); chooseTab(false); syncChapters();
    const data = selected.kind === "podcast" ? await chaptersFor(asset) : null;
    if (chapterAsset !== asset.sha256) return;
    currentChapters = data; tabs.hidden = !data;
    if (data) chapterList.replaceChildren(...chapterRows(data,selected.section,selected.kind,selectedRelease));
    syncChapters();
  }
  async function hydrateChapters() {
    const listen = $(".listen-player");
    if (!listen) return;
    const section = listen.dataset.listenSection;
    const kind = new URLSearchParams(location.search).get("ses") === "ozet" ? "summary" : "podcast";
    if (kind !== "podcast") return;
    const asset = release.editions[section].podcast;
    const data = await chaptersFor(asset);
    if (!data || !listen.isConnected) return;
    const container = make("section","episode-chapters");
    const heading = make("h2","","Bu bölümde"), list = make("ol","chapter-list");
    list.append(...chapterRows(data,section,kind)); container.append(heading,list);
    listen.closest(".episode").append(container); syncChapters();
  }
  let playbackChannel = null;
  try { playbackChannel = new BroadcastChannel("pulse-audio-session-v1");
    playbackChannel.onmessage = event => { if (event.data === "playing") { audio.pause(); playRequest++; } };
    audio.addEventListener("play",()=>playbackChannel.postMessage("playing"));
  } catch (_) {}
  function saveState() {
    if (
      release && !window.PULSE_ARCHIVE &&
      renderedURL.pathname === location.pathname &&
      renderedURL.search === location.search
    )
      try {
        history.replaceState(
          {
            ...history.state,
            pulse: true,
            releaseId: release?.manifest.release_id,
            scroll: readingScroll(),
            list: listState,
            focusStory:
              document.activeElement?.closest(".story")?.dataset.story || null,
          },
          "",
          location.href,
        );
      } catch (_) {}
  }
  window.addEventListener("pagehide", saveState);
  document.addEventListener("scrollend", () => {
    if (release) saveState();
  });
  function readerReturn(state = history.state, key = "readerReturn") {
    const origin = state?.[key];
    if (!origin || origin.state?.releaseId !== release?.manifest.release_id)
      return null;
    try {
      const url = new URL(origin.url);
      const routes = [
        "", "index.html", "haberler/", "haberler/index.html",
        "teknoloji/", "teknoloji/index.html", "oyun/", "oyun/index.html",
        "podcastler/", "podcastler/index.html",
        "teknoloji/dinle/", "teknoloji/dinle/index.html", "oyun/dinle/", "oyun/dinle/index.html",
      ];
      if (
        url.origin === base.origin &&
        (routes.some((route) => url.pathname === new URL(route, base).pathname) ||
          (url.pathname.startsWith(base.pathname) && /^(teknoloji|oyun)\/haber\/[A-Za-z0-9_-]{1,100}\/(index\.html)?$/.test(url.pathname.slice(base.pathname.length))))
      )
        return origin;
    } catch (_) {}
    return null;
  }
  const categoryStates = new Map();
  function setupList(state) {
    const stories = $("#stories");
    if (!stories) { listState = null; return; }
    const articles = all(".story", stories), search = $(".news-search"),
      buttons = all("[data-filter]"), dialog = $(".topics-dialog"),
      topicToggle = $(".topics-toggle"), options = $(".topic-options"),
      chips = $(".filter-chips"), searchToggle = $(".search-toggle"),
      searchLabel = $(".news-search-label"), clearSearch = $(".search-clear");
    const scope = document.body.dataset.section || "all";
    state = state || categoryStates.get(scope);
    let filter = document.body.dataset.section || state?.section || "",
      categories = Array.isArray(state?.categories) ? state.categories : state?.category ? [state.category] : [],
      limit = state?.limit || 8, query = state?.query || "";
    search.value = query;
    const normalize = (text) => text.toLocaleLowerCase("tr-TR").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i");
    const searchable = new Map(articles.map((article) => [article,
      normalize([$("h2,h3", article)?.textContent, $(".story-brief", article)?.textContent,
        article.dataset.category].join(" "))]));
    const available = () => [...new Set(articles.filter(a => !filter || a.dataset.section === filter)
      .map(a => a.dataset.category))];
    categories = categories.filter(c => available().includes(c));
    let timer;
    pageEvents.signal.addEventListener("abort", () => { clearTimeout(timer); dialog.close(); }, { once: true });
    function save() { refresh(); saveState(); }
    function refresh() {
      let count = 0;
      const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
      for (const article of articles) {
        const match = (!filter || article.dataset.section === filter) &&
          (!categories.length || categories.includes(article.dataset.category)) &&
          terms.every(term => searchable.get(article).includes(term));
        article.hidden = !match || count++ >= limit;
      }
      $(".news-more").hidden = count <= limit;
      $(".empty-filter").hidden = count !== 0;
      $("#story-count").textContent = count + " haber";
      buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.filter === filter)));
      topicToggle.hidden = available().length < 2;
      topicToggle.textContent = "Konular" + (categories.length ? " · " + categories.length : "");
      chips.replaceChildren(...categories.map(category => {
        const chip = make("button", "filter-chip", category + " ×");
        chip.type = "button";
        chip.setAttribute("aria-label", category + " filtresini kaldır");
        chip.onclick = () => { categories = categories.filter(c => c !== category); limit = 8; save(); topicToggle.focus(); };
        return chip;
      }));
      clearSearch.hidden = !query;
      searchLabel.classList.toggle("search-active", !!query || searchToggle.getAttribute("aria-expanded") === "true");
      listState = { section: filter, categories, limit, query };
      categoryStates.set(scope, listState);
    }
    searchToggle.onclick = () => {
      const expanded = searchToggle.getAttribute("aria-expanded") !== "true";
      searchToggle.setAttribute("aria-expanded", String(expanded));
      searchLabel.classList.toggle("search-active", expanded || !!query);
      if (expanded) search.focus();
    };
    search.addEventListener("input", () => {
      query = search.value.slice(0, 160); limit = 8; refresh();
      clearTimeout(timer); timer = setTimeout(saveState, 300);
    }, { signal: pageEvents.signal });
    clearSearch.onclick = () => {
      query = search.value = ""; limit = 8;
      searchToggle.setAttribute("aria-expanded","true"); save(); search.focus();
    };
    topicToggle.onclick = () => {
      options.replaceChildren(...available().map(category => {
        const label = make("label", "topic-option");
        const input = make("input"); input.type = "checkbox"; input.value = category;
        input.checked = categories.includes(category);
        label.append(input, document.createTextNode(category)); return label;
      }));
      dialog.showModal();
    };
    $(".topics-clear").onclick = () => all("input", options).forEach(i => i.checked = false);
    $("form", dialog).addEventListener("submit", event => {
      if (event.submitter?.value === "apply") {
        categories = all("input:checked", options).map(i => i.value); limit = 8; save();
      }
    }, { signal: pageEvents.signal });
    dialog.addEventListener("close", () => {
      if (!dialog.open && topicToggle.isConnected) topicToggle.focus({ preventScroll: true });
    }, { signal: pageEvents.signal });
    dialog.addEventListener("click", e => { if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    } }, { signal: pageEvents.signal });
    for (const b of buttons) b.onclick = () => { filter = b.dataset.filter; categories = []; limit = 8; save(); };
    $(".news-more").onclick = () => { limit += 8; save(); };
    $(".reset-filter").onclick = () => {
      filter = document.body.dataset.section || ""; categories = []; query = search.value = "";
      limit = 8; save();
      (topicToggle.hidden ? (search.getClientRects().length ? search : searchToggle) : topicToggle).focus();
    };
    refresh();
  }
  function backLabel(link, text) {
    const arrow = link.querySelector("svg");
    link.replaceChildren(...(arrow ? [arrow] : []), document.createTextNode(" " + text));
  }
  function returnLabel() {
    if (document.body.dataset.page === "listen") return "Bölüme dön";
    if (document.body.dataset.page === "article") return "Habere dön";
    if (document.body.dataset.page === "podcasts") return "Podcast’lere dön";
    if (document.body.dataset.page === "home") return "Seçkiye dön";
    return document.body.dataset.section === "teknoloji" ? "Teknoloji yayınına dön" : document.body.dataset.section === "oyun" ? "Oyun yayınına dön" : "Haberlere dön";
  }
  function hydrate(state) {
    pageEvents?.abort();
    pageEvents = new AbortController();
    const articleBack = $(".article-reader .back");
    const origin = readerReturn(state);
    if (articleBack && origin) {
      articleBack.href = origin.url;
      if (origin.label) backLabel(articleBack, origin.label);
    }
    const listenBack = $(".listen-back");
    if (listenBack) {
      const source = readerReturn(state, "listeningReturn");
      const routes = {secki: ["index.html", "Seçkiye dön"], podcastler: ["podcastler/index.html", "Podcast’lere dön"],
        teknoloji: ["teknoloji/index.html", "Teknoloji yayınına dön"], oyun: ["oyun/index.html", "Oyun yayınına dön"], haberler: ["haberler/index.html", "Haberlere dön"]};
      const from = new URLSearchParams(location.search).get("from");
      const fallback = Object.hasOwn(routes, from) ? routes[from] : routes.podcastler;
      listenBack.href = source?.url || new URL(fallback[0], base).href;
      backLabel(listenBack, source?.label || fallback[1]);
    }
    for (const image of all(".story-image")) {
      const frame = image.closest(".image-frame");
      if (!frame) continue;
      const fallback = $(".image-fallback", frame);
      const show = () => {
        image.hidden = true;
        fallback.hidden = false;
      };
      const hide = () => {
        image.hidden = false;
        fallback.hidden = true;
      };
      image.addEventListener("error", show, { signal: pageEvents.signal });
      image.addEventListener("load", hide, { signal: pageEvents.signal });
      $(".image-retry", frame)?.addEventListener(
        "click",
        () => {
          const src = image.src;
          image.removeAttribute("src");
          image.src = src;
        },
        { signal: pageEvents.signal },
      );
      if (image.complete && !image.naturalWidth) show();
    }
    setupList(state?.list);
    hydrateChapters();
    for (const start of all(".audio-start"))
      start.addEventListener(
        "click",
        () => {
          configure(start.dataset.section, start.dataset.kind);
          toggle();
        },
        { signal: pageEvents.signal },
      );
    const listen = $(".listen-player");
    if (listen) {
      const section = listen.dataset.listenSection,
        kind =
          new URLSearchParams(location.search).get("ses") === "ozet"
            ? "summary"
            : "podcast";
      const edition = release.editions[section];
      const heading = listen
        .closest(".episode")
        .querySelector(".episode-heading");
      const pageTitle =
        (kind === "summary"
          ? "Günün Özeti · " + (section === "teknoloji" ? "Teknoloji" : "Oyun")
          : edition.podcast.title) + " · PULSE";
      document.title = pageTitle;
      $('meta[property="og:title"]')?.setAttribute("content", pageTitle);
      if (kind === "summary") {
        const canonical = new URL(location.href);
        canonical.hash = "";
        canonical.searchParams.delete("from");
        $('link[rel="canonical"]')?.setAttribute("href", canonical.href);
        $('meta[property="og:url"]')?.setAttribute("content", canonical.href);
        const description =
          (section === "teknoloji" ? "Teknoloji" : "Oyun") +
          " haberleri: Günün Özeti · PULSE";
        for (const selector of [
          'meta[name="description"]',
          'meta[property="og:description"]',
        ])
          $(selector)?.setAttribute("content", description);
      }
      heading.querySelector("h1").textContent =
        kind === "summary" ? "Günün Özeti" : edition.podcast.title;
      heading.querySelector(".eyebrow").textContent =
        (section === "teknoloji" ? "Teknoloji" : "Oyun") +
        (kind === "podcast" ? " podcast’i" : "");
      heading.querySelector(".episode-hosts").hidden = kind !== "podcast";
      heading.querySelector(".program-art").hidden = kind !== "podcast";
      heading.querySelector(".detail-meta").textContent =
        release.manifest.publish_date.split("-").reverse().join(".") +
        " · " +
        format(edition[kind].duration);
      const start = listen.querySelector(".audio-start");
      start.dataset.kind = kind;
      start.setAttribute("aria-label", pageTitle + ": Oynat");
    }
    update();
    all(".resume-note").forEach((n) => n.remove());
    for (const start of all(".audio-start")) {
      const record = remembered(start.dataset.section, start.dataset.kind);
      if (!record) continue;
      const copy = start.closest(".audio-box")?.querySelector(".audio-copy") ||
        start.closest(".program-card")?.querySelector(".program-body") ||
        start.closest(".listen-player");
      if (copy) copy.append(make("p", "resume-note", "Kaldığın yer · " + format(record.position)));
    }
    window.dispatchEvent(new Event("pulse:navigate"));
  }
  async function documentAt(url, signal) {
    const response = await fetch(url, { cache: "no-store", signal });
    if (!response.ok) throw Error("Sayfa yüklenemedi");
    const doc = new DOMParser().parseFromString(
      await response.text(),
      "text/html",
    );
    const path = new URL(url, location.href).pathname;
    const legal =
      [
        "gizlilik/",
        "gizlilik/index.html",
        "kosullar/",
        "kosullar/index.html",
      ].some((route) => path === new URL(route, base).pathname) &&
      doc.body.dataset.page === "legal";
    if (
      doc.body.dataset.design !== "editor-desk-v1" ||
      !$("#main", doc) ||
      (!legal &&
        $("#main", doc).dataset.release !== release?.manifest.release_id)
    )
      throw Error("Sayfa güncel sayıyla eşleşmiyor");
    return doc;
  }
  function swap(doc, state) {
    renderedURL = new URL(location.href);
    const main = $("#main"),
      incoming = $("#main", doc);
    main.className = incoming.className;
    main.replaceChildren(...incoming.childNodes);
    main.dataset.release = incoming.dataset.release;
    for (const key of ["page", "section", "story"])
      document.body.dataset[key] = doc.body.dataset[key] || "";
    document.title = doc.title;
    $(".nav-issue").textContent = $(".nav-issue", doc)?.textContent || "";
    for (const selector of [
      'link[rel="canonical"]',
      'meta[name="description"]',
      'meta[property="og:type"]',
      'meta[property="og:title"]',
      'meta[property="og:description"]',
      'meta[property="og:url"]',
      'meta[property="og:image"]',
    ]) {
      const source = $(selector, doc),
        target = $(selector);
      if (source && target)
        for (const key of ["content", "href"])
          if (source.hasAttribute(key))
            target.setAttribute(key, source.getAttribute(key));
    }
    all('script[type="application/ld+json"]', document.head).forEach((n) =>
      n.remove(),
    );
    all('script[type="application/ld+json"]', doc.head).forEach((n) =>
      document.head.append(n.cloneNode(true)),
    );
    for (const property of ["og:image:width", "og:image:height"]) {
      const selector = 'meta[property="' + property + '"]';
      $(selector)?.remove();
      const incomingMeta = $(selector, doc);
      if (incomingMeta) document.head.append(incomingMeta.cloneNode(true));
    }
    all(".nav nav a").forEach((a) => {
      const incomingLink = all(".nav nav a", doc).find(
        (n) => n.textContent === a.textContent,
      );
      if (incomingLink?.hasAttribute("aria-current"))
        a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    hydrate(state);
  }
  async function navigate(url, { pop = false, state = null } = {}) {
    pendingNav?.abort();
    const controller = new AbortController();
    pendingNav = controller;
    $("#main").classList.add("content-transition");
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      if (!pop) saveState();
      const doc = await documentAt(url, controller.signal);
      if (controller !== pendingNav) return;
      if (pop && state?.releaseId !== release.manifest.release_id) state = null;
      if (!pop) {
        const origin =
          ["home", "news", "podcasts", "listen"].includes(document.body.dataset.page) &&
          doc.body.dataset.page === "article"
            ? { url: location.href, state: {releaseId: release.manifest.release_id}, label: returnLabel() }
            : null;
        const previousListening = readerReturn(history.state, "listeningReturn");
        const listeningOrigin = doc.body.dataset.page === "listen"
          ? (document.body.dataset.page === "listen" && previousListening
            ? {...previousListening, distance: (previousListening.distance || 1) + 1}
            : ["home", "news", "podcasts", "article"].includes(document.body.dataset.page)
              ? {url: location.href, state: {releaseId: release.manifest.release_id}, label: returnLabel(), distance: 1} : null)
          : null;
        state = {
          pulse: true, releaseId: release.manifest.release_id,
          scroll: 0, readerReturn: origin, listeningReturn: listeningOrigin,
        };
        history.pushState(state, "", url);
      }
      swap(doc, state);
      const anchor = url.hash
        ? document.getElementById(decodeURIComponent(url.hash.slice(1)))
        : null;
      $("#main").focus({ preventScroll: true });
      if (pop && state?.focusStory)
        all(".story")
          .find((story) => story.dataset.story === state.focusStory)
          ?.querySelector(".story-detail-link")
          ?.focus({ preventScroll: true });
      if (pop && state?.pulse) scrollReadingTo(state.scroll || 0);
      else if (anchor) anchor.scrollIntoView();
      else scrollReadingTo(state?.scroll || 0);
    } catch (error) {
      if (controller !== pendingNav) return;
      // A hard navigation rechecks the manifest rather than trusting a mismatched page.
      location.assign(url.href);
    } finally {
      clearTimeout(timeout);
      if (controller === pendingNav)
        $("#main").classList.remove("content-transition");
    }
  }
  document.addEventListener("click", (event) => {
    const a = event.target.closest("a[href]");
    if (
      !a ||
      !release ||
      window.PULSE_ARCHIVE ||
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      a.target ||
      a.hasAttribute("download")
    )
      return;
    const url = new URL(a.href);
    if (
      url.origin !== base.origin ||
      !url.pathname.startsWith(base.pathname) ||
      (!url.pathname.endsWith("/") && !url.pathname.endsWith(".html"))
    )
      return;
    if (
      url.pathname === location.pathname &&
      url.search === location.search &&
      url.hash
    )
      return;
    event.preventDefault();
    if (a.matches(".article-reader .back") && readerReturn()) {
      history.back();
      return;
    }
    if (a.matches(".listen-back") && readerReturn(history.state, "listeningReturn")) {
      const count = readerReturn(history.state, "listeningReturn").distance || 1;
      history.go(-Math.max(1, Math.min(100, Number.isInteger(count) ? count : 1)));
      return;
    }
    navigate(url);
  });
  window.addEventListener("popstate", (event) => {
    if (release && !window.PULSE_ARCHIVE)
      navigate(new URL(location.href), { pop: true, state: event.state });
  });
  async function ready(next) {
    if (release?.manifest.release_id === next.manifest.release_id) return;
    // A verified new issue must not replace the listener’s active immutable recording.
    release = next;
    if (selected) configure(selected.section, selected.kind, selectedRelease);
    chapterRegistry = null; chapterCache.clear();
    const allowed = new Set(Object.keys(next.editions).flatMap((section) =>
      ["podcast", "summary"].map((kind) => assetKey(section, kind))));
    if (selected) allowed.add(assetKey(selected.section, selected.kind, selectedRelease));
    savedListening = Object.fromEntries(Object.entries(savedListening)
      .filter(([key]) => allowed.has(key)));
    if ($("#main").dataset.release !== next.manifest.release_id) {
      try {
        const doc = await documentAt(location.href, AbortSignal.timeout(15000));
        swap(doc, null);
      } catch (_) {
        window.dispatchEvent(new Event("pulse:render-error"));
        return;
      }
    } else hydrate(
      history.state?.releaseId === next.manifest.release_id ? history.state : null,
    );
    window.dispatchEvent(
      new CustomEvent("pulse:rendered", {
        detail: { release_id: next.manifest.release_id },
      }),
    );
    if (!window.PULSE_ARCHIVE) {
      history.scrollRestoration = "manual";
      if (!history.state?.pulse)
        history.replaceState(
          { pulse: true, releaseId: next.manifest.release_id, scroll: 0 },
          "", location.href,
        );
      else if (history.state.releaseId === next.manifest.release_id)
        scrollReadingTo(history.state.scroll || 0);
    }
  }
  window.addEventListener("pulse:ready", (event) => ready(event.detail));
  window.addEventListener("pulse:locked", () => {
    $(".topics-dialog")?.close();
    collapsePanel(false);
    miniLink.removeAttribute("href");
    release = null;
    pendingNav?.abort();
  });
  if (window.PULSE_RELEASE) ready(window.PULSE_RELEASE);
})();
