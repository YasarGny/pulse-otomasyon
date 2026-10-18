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
  controls.append(back, play, forward, speed);
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
  bottom.append(mute, volume, deviceVolume, episode);
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
    miniStatus = make("span", "mini-status");
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
  const assetKey = (section, kind) => {
    const asset = release?.editions[section]?.[kind];
    return asset ? release.manifest.publish_date + ":" + section + ":" + kind + ":" + asset.sha256 : "";
  };
  function remembered(section, kind) {
    const record = savedListening[assetKey(section, kind)];
    const duration = release?.editions[section]?.[kind]?.duration || 0;
    return record && Number.isFinite(record.position) && record.position >= 3 &&
      record.position < duration - 5 && rates.includes(record.rate)
      ? record : null;
  }
  function persistListening(force = false) {
    if (!selected || !hasStarted || !audio.readyState || failed || pendingPosition)
      return;
    if (!force && Date.now() - lastProgressWrite < 5000) return;
    lastProgressWrite = Date.now();
    const key = assetKey(selected.section, selected.kind);
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
        : release.editions[selected.section].podcast.title
      : "";
  }
  function update() {
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
        n.dataset.kind === selected.kind;
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
          : loading
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
    full.classList.toggle("is-loading", loading && !failed);
    full.classList.toggle("is-error", failed);
    status.textContent = state;
    miniStatus.textContent = state;
    retry.hidden = !failed;
    mini.hidden =
      !selected ||
      !hasStarted ||
      document.documentElement.classList.contains("pulse-locked");
    document.body.classList.toggle("has-mini", !mini.hidden);
    icon(miniMore, "settings");
    miniMore.setAttribute("aria-busy", String(loading));
    miniMore.dataset.state = failed
      ? "error"
      : loading
        ? "loading"
        : playing
          ? "playing"
          : "paused";
    miniMore.setAttribute(
      "aria-label",
      (panel.hidden ? "Oynatıcı kontrollerini aç" : "Kontrolleri küçült") +
        ": " +
        title() +
        (playing ? ", çalıyor" : ", duraklatıldı"),
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
    seek.disabled = !audio.readyState;
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
  }
  function mount() {
    miniDetails.append(full);
    full.hidden = false;
  }
  function configure(section, kind) {
    if (
      !release ||
      !release.editions[section] ||
      !["podcast", "summary"].includes(kind)
    )
      return false;
    const asset = release.editions[section][kind];
    const changed =
      !selected || selected.section !== section || selected.kind !== kind;
    if (changed) {
      persistListening(true);
      collapsePanel(false);
      audio.pause();
      selected = { section, kind };
      const previous = remembered(section, kind);
      pendingPosition = previous?.position || 0;
      selectedDuration = asset.duration;
      audio.src = new URL(asset.file, release.url).href;
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
    episode.textContent = release.manifest.publish_date
      .split("-")
      .reverse()
      .join(".");
    miniSubtitle.textContent = playerSubtitle.textContent;
    miniLink.textContent = title();
    miniLink.href = new URL(
      section + "/dinle/index.html" + (kind === "summary" ? "?ses=ozet" : ""),
      base,
    ).href;
    progress();
    update();
    return true;
  }
  async function toggle() {
    if (!selected) return;
    if (document.getElementById("main").contains(document.activeElement))
      lastAudioTrigger = document.activeElement;
    if (!audio.paused && !failed) {
      audio.pause();
      loading = false;
      update();
      return;
    }
    if (failed) audio.load();
    hasStarted = true;
    loading = true;
    failed = false;
    update();
    try {
      await audio.play();
    } catch (error) {
      if (error.name !== "AbortError") {
        failed = true;
        loading = false;
      }
    } finally {
      update();
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
  retry.onclick = () => {
    failed = false;
    loading = false;
    audio.load();
    update();
  };
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
  function readerReturn(state = history.state) {
    const origin = state?.readerReturn;
    if (!origin || origin.state?.releaseId !== release?.manifest.release_id)
      return null;
    try {
      const url = new URL(origin.url);
      const routes = [
        "", "index.html", "haberler/", "haberler/index.html",
        "teknoloji/", "teknoloji/index.html", "oyun/", "oyun/index.html",
      ];
      if (
        url.origin === base.origin &&
        routes.some((route) => url.pathname === new URL(route, base).pathname)
      )
        return origin;
    } catch (_) {}
    return null;
  }
  function setupList(state) {
    const stories = $("#stories");
    if (!stories) {
      listState = null;
      return;
    }
    const articles = all(".story", stories),
      select = $(".news-filter"),
      search = $(".news-search"),
      buttons = all("[data-filter]");
    let filter = state?.section || "",
      category = state?.category || "",
      limit = state?.limit || 8,
      query = state?.query || "";
    search.value = query;
    const normalize = (text) => text.toLocaleLowerCase("tr-TR")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i");
    const searchable = new Map(articles.map((a) => [a, normalize(a.textContent)]));
    let searchStateTimer;
    pageEvents.signal.addEventListener("abort", () => clearTimeout(searchStateTimer), { once: true });
    if (document.body.dataset.section) filter = document.body.dataset.section;
    function categories() {
      const values = [
        ...new Set(
          articles
            .filter((a) => !filter || a.dataset.section === filter)
            .map((a) => a.dataset.category),
        ),
      ];
      select.replaceChildren(
        new Option("Tüm konular", ""),
        ...values.map((v) => new Option(v, v)),
      );
      if (!values.includes(category)) category = "";
      select.value = category;
    }
    function refresh() {
      let count = 0;
      const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
      for (const a of articles) {
        const match =
          (!filter || a.dataset.section === filter) &&
          (!category || a.dataset.category === category) &&
          terms.every((term) => searchable.get(a).includes(term));
        a.hidden = !match || count++ >= limit;
      }
      $(".news-more").hidden = count <= limit;
      $(".empty-filter").hidden = count !== 0;
      $("#story-count").textContent =
        Math.min(count, limit) + " / " + count + " haber";
      buttons.forEach((b) =>
        b.setAttribute("aria-pressed", String(b.dataset.filter === filter)),
      );
      listState = { section: filter, category, limit, query };
    }
    search.addEventListener("input", () => {
      query = search.value.slice(0, 160);
      limit = 8;
      refresh();
      clearTimeout(searchStateTimer);
      searchStateTimer = setTimeout(saveState, 300);
    }, { signal: pageEvents.signal });
    for (const b of buttons)
      b.addEventListener(
        "click",
        () => {
          filter = b.dataset.filter;
          category = "";
          limit = 8;
          categories();
          refresh();
          saveState();
        },
        { signal: pageEvents.signal },
      );
    select.addEventListener(
      "change",
      () => {
        category = select.value;
        limit = 8;
        refresh();
        saveState();
      },
      { signal: pageEvents.signal },
    );
    $(".news-more").addEventListener(
      "click",
      () => {
        limit += 8;
        refresh();
        saveState();
      },
      { signal: pageEvents.signal },
    );
    $(".reset-filter").addEventListener(
      "click",
      () => {
        filter = document.body.dataset.section || "";
        category = "";
        query = search.value = "";
        limit = 8;
        categories();
        refresh();
        saveState();
        (buttons[0] || select).focus();
      },
      { signal: pageEvents.signal },
    );
    categories();
    refresh();
  }
  function hydrate(state) {
    pageEvents?.abort();
    pageEvents = new AbortController();
    const articleBack = $(".article-reader .back");
    const origin = readerReturn(state);
    if (articleBack && origin) articleBack.href = origin.url;
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
          ["home", "news"].includes(document.body.dataset.page) &&
          doc.body.dataset.page === "article"
            ? { url: location.href, state: history.state }
            : null;
        state = {
          pulse: true, releaseId: release.manifest.release_id,
          scroll: 0, readerReturn: origin,
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
    const a = event.target.closest("a");
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
    navigate(url);
  });
  window.addEventListener("popstate", (event) => {
    if (release && !window.PULSE_ARCHIVE)
      navigate(new URL(location.href), { pop: true, state: event.state });
  });
  async function ready(next) {
    if (release?.manifest.release_id === next.manifest.release_id) return;
    if (release) {
      close.click();
    }
    release = next;
    const allowed = new Set(Object.keys(next.editions).flatMap((section) =>
      ["podcast", "summary"].map((kind) => assetKey(section, kind))));
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
    close.click();
    release = null;
    pendingNav?.abort();
  });
  if (window.PULSE_RELEASE) ready(window.PULSE_RELEASE);
})();
