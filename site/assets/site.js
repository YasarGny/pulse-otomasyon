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
    headphones: '<path d="M4 14v-3a8 8 0 0 1 16 0v3M4 12H3v7h4v-7Zm16 0h1v7h-4v-7Z"/>',
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
    if (selectedClip || !selected || !hasStarted || !audio.readyState || failed || pendingPosition)
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
    icon(miniMore, document.body.dataset.page === "flow" ? "headphones" : "settings");
    for (const start of all('.story-clip-play')) {
      const active = selectedClip && selectedClip.key === start.dataset.clipKey && selectedClip.context === release;
      icon($('.clip-action-icon', start), active && playing ? 'pause' : 'play');
      $('.clip-action-label', start).textContent = active && playing ? 'Duraklat' : 'Dinle';
      start.setAttribute('aria-pressed', String(!!active && playing));
    }
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
      !context || window.PulseControls?.state.enabled === false ||
      (kind === "podcast" && window.PulseControls?.state.podcasts[section] === false) ||
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
      selectedClip = null; fullEpisode.hidden = clipNotice.hidden = clipTopic.hidden = clipParts.hidden = clipReturn.hidden = true;
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
    if (selectedClip) miniSubtitle.textContent = clipCaption(selectedClip);
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
      if (selectedClip) selectedClip.stopped = true;
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
    if (audio.ended && selectedClip?.entries.length > 1) {
      const clip = selectedClip;
      playStoryClip(clip.entries, 0, clip.section, clip.story, clip.context);
      return;
    }
    if (audio.ended) { pendingPosition = 0; audio.currentTime = 0; }
    if (selectedClip) selectedClip.stopped = false;
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
    selectedClip = null; fullEpisode.hidden = clipNotice.hidden = clipTopic.hidden = clipParts.hidden = clipReturn.hidden = true;
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
        play: () => {if (audio.paused || audio.ended || failed) toggle();},
        pause: () => {if (selectedClip) selectedClip.stopped = true; audio.pause();},
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
  // Story clips are actual short files. Native EOF also stops in background tabs.
  let selectedClip = null, clipIndexPromise = null;
  const fullEpisode = make('button', 'clip-full-episode', 'Tam bölümü dinle');
  fullEpisode.type = 'button'; fullEpisode.hidden = true; full.append(fullEpisode);
  const clipTopic = make('p', 'clip-topic'); clipTopic.hidden = true;
  full.insertBefore(clipTopic, controls);
  const clipReturn = make('button', 'clip-return', 'Dinlenen habere dön');
  clipReturn.type = 'button'; clipReturn.hidden = true; full.insertBefore(clipReturn, controls);
  clipReturn.onclick = () => {
    if (!selectedClip) return;
    const clip = selectedClip; collapsePanel(false);
    if (clip.context === release && revealFlowStory?.(clip.section, clip.story)) return;
    navigate(new URL(clip.section + '/haber/' + encodeURIComponent(clip.story) + '/', base));
  };
  const clipParts = make('div', 'clip-parts'); clipParts.hidden = true;
  const previousPart = make('button', 'clip-part-previous', '←');
  const nextPart = make('button', 'clip-part-next', '→');
  previousPart.type = nextPart.type = 'button';
  previousPart.setAttribute('aria-label', 'Önceki kesit'); nextPart.setAttribute('aria-label', 'Sonraki kesit');
  const partLabel = make('span', 'clip-part-label'); partLabel.setAttribute('role', 'status');
  clipParts.append(previousPart, partLabel, nextPart); full.insertBefore(clipParts, controls);
  const clipNotice = make('p', 'clip-notice'); clipNotice.hidden = true; full.append(clipNotice);
  const clipCaption = clip => 'Haber kesiti' + (clip.entries.length > 1 ? ' · ' + (clip.index + 1) + '/' + clip.entries.length : '') + ' · ' + format(clip.entry.duration);
  function playStoryClip(entries, index, section, story, context) {
    if (!entries[index]) return;
    const entry = entries[index], asset = context.editions[section].podcast;
    const rate = audio.playbackRate, expanded = !panel.hidden;
    const clipContext = {...context, url:base, editions:{...context.editions,
      [section]:{...context.editions[section], podcast:{...asset, ...entry}}}};
    configure(section, 'podcast', clipContext);
    selectedClip = {entries, index, entry, section, story, context, key:section + ':' + story};
    clipTopic.textContent = context.editions[section].stories.find(item => item.id === story)?.title || '';
    clipTopic.hidden = !clipTopic.textContent;
    clipReturn.hidden = false;
    pendingPosition = 0; if (audio.readyState) audio.currentTime = 0;
    audio.playbackRate = rate;
    playerSubtitle.textContent = miniSubtitle.textContent = clipCaption(selectedClip);
    fullEpisode.hidden = false; clipNotice.hidden = true;
    clipParts.hidden = entries.length < 2;
    previousPart.disabled = index === 0; nextPart.disabled = index === entries.length - 1;
    partLabel.textContent = 'Kesit ' + (index + 1) + '/' + entries.length;
    chapterAsset = null; tabs.hidden = true; chooseTab(false);
    if (expanded) {panel.hidden = miniDetails.hidden = false; miniMore.setAttribute('aria-expanded','true'); mount();}
    toggle();
  }
  previousPart.onclick = () => {
    if (!selectedClip) return;
    const clip = selectedClip; playStoryClip(clip.entries,clip.index - 1,clip.section,clip.story,clip.context);
  };
  nextPart.onclick = () => {
    if (!selectedClip) return;
    const clip = selectedClip; playStoryClip(clip.entries,clip.index + 1,clip.section,clip.story,clip.context);
  };
  fullEpisode.onclick = () => {
    if (!selectedClip) return;
    const clip = selectedClip, position = clip.entry.start + audio.currentTime;
    const rate = audio.playbackRate;
    configure(clip.section, 'podcast', clip.context);
    pendingPosition = position;
    if (audio.readyState) { audio.currentTime = position; pendingPosition = 0; }
    audio.playbackRate = rate;
    toggle();
  };
  audio.addEventListener('ended', () => {
    if (!selectedClip || selectedClip.stopped || failed) return;
    const clip = selectedClip;
    if (clip.index + 1 < clip.entries.length) {
      playStoryClip(clip.entries,clip.index + 1,clip.section,clip.story,clip.context);
    } else {
      clipNotice.textContent = clip.entries.length > 1 ? 'Kesitler tamamlandı. Tekrar dinlemek için oynat.' : 'Kesit tamamlandı. Tekrar dinlemek için oynat.';
      clipNotice.hidden = false;
    }
  });
  async function clipsForStories() {
    if (!clipIndexPromise) clipIndexPromise = (async () => {
      const embedded = window.PULSE_RELEASE?.clips;
      if (embedded) return embedded;
      const response = await fetch(new URL('assets/clips/index.json', base), {cache:'no-store', signal:AbortSignal.timeout(12000)});
      if (!response.ok) throw Error('Kesit bilgisi yüklenemedi');
      return response.json();
    })().catch(() => { clipIndexPromise = null; return null; });
    return clipIndexPromise;
  }
  async function hydrateStoryClips() {
    const slots = all('.story-clip-slot');
    if (!slots.length || !release) return;
    const context = release;
    if (!slots.some(slot => { const s = slot.dataset.section || document.body.dataset.section; return context.editions[s]?.podcast && window.PulseControls?.state.podcasts[s] !== false; })) return;
    const index = await clipsForStories();
    if (context !== release || index?.schema_version !== 1 || index.release_id !== context.manifest.release_id) return;
    for (const slot of slots) {
      if (!slot.isConnected || slot.childElementCount) continue;
      const section = slot.dataset.section || document.body.dataset.section;
      const story = slot.dataset.story || document.body.dataset.story;
      const asset = context.editions[section]?.podcast;
      if (!asset) continue;
      const entries = index.stories?.[section + ':' + story];
      if (!Array.isArray(entries)) continue;
      const valid = entries.slice(0, 80).filter(entry => entry && entry.audio_sha256 === asset.sha256 &&
        /^releases\/[A-Za-z0-9_-]+\/clips\/[a-f0-9]{64}-[0-9.]+-[0-9.]+\.mp3$/.test(entry.file) &&
        entry.file.startsWith('releases/' + context.manifest.release_id + '/clips/') &&
        /^[a-f0-9]{64}$/.test(entry.sha256) && Number.isFinite(entry.duration) && entry.duration >= 1 &&
        Number.isFinite(entry.start) && Number.isFinite(entry.end) && entry.start >= 0 && entry.end <= asset.duration &&
        entry.end > entry.start && Math.abs(entry.duration - (entry.end - entry.start)) <= .2)
        .sort((a,b) => a.start - b.start);
      // Deduplicate retries, reject overlaps, never turn another story into a queue entry.
      const seen = new Set();
      const queue = valid.filter(entry => {if (seen.has(entry.file)) return false; seen.add(entry.file); return true;});
      if (!queue.length || queue.some((entry,i) => i > 0 && entry.start < queue[i-1].end)) continue;
      const strip = make('div', 'story-clip');
      const cover = make('img'); cover.alt = ''; cover.width = cover.height = 48;
      cover.src = new URL('assets/covers/' + (section === 'teknoloji' ? 'yeni-sekme' : 'moradon-fm') + '-192.webp', base).href;
      const copy = make('div', 'story-clip-copy');
      const total = Math.round(queue.reduce((sum, entry) => sum + entry.duration, 0));
      const durationText = (total >= 60 ? Math.floor(total/60) + ' dk ' : '') + (total%60 ? total%60 + ' sn' : '');
      copy.append(make('strong', '', 'Podcast’te bu konu'), make('span', '', asset.title + ' · ' + (queue.length > 1 ? queue.length + ' kesit · ' : '') + durationText.trim()));
      const start = make('button', 'story-clip-play'); start.type = 'button';
      const actionIcon = make('span', 'clip-action-icon'); icon(actionIcon, 'play');
      start.append(actionIcon, make('span', 'clip-action-label', 'Dinle'));
      start.dataset.clipKey = section + ':' + story;
      start.setAttribute('aria-label', asset.title + ': Bu haberin ' + (queue.length > 1 ? queue.length + ' kesitini' : 'kesitini') + ' dinle');
      start.onclick = () => {
        if (release !== context) return;
        lastAudioTrigger = start;
        if (selectedClip?.key === start.dataset.clipKey && selectedClip.context === context) { toggle(); return; }
        playStoryClip(queue, 0, section, story, context);
      };
      strip.append(cover, copy, start); slot.append(strip);

    }
  }

  const chapterCache = new Map();
  let chapterRegistry = null;
  let chapterRegistryAt = 0, chapterRefreshRunning = false, chapterRefreshAgain = false;
  async function chaptersFor(asset) {
    if (!asset || !/^[a-f0-9]{64}$/.test(asset.sha256)) return null;
    if (!chapterCache.has(asset.sha256)) chapterCache.set(asset.sha256, (async () => {
      try {
        const embedded = window.PULSE_RELEASE?.chapters?.[asset.sha256];
        if (embedded) return PulseListening.validate(embedded, asset);
        if (window.PULSE_ARCHIVE) return null;
        if (!chapterRegistry || performance.now() - chapterRegistryAt >= 50000) {
          chapterRegistryAt = performance.now();
          chapterRegistry = fetch(new URL("assets/chapters/index.json", base),
          { cache: "no-cache", signal: AbortSignal.timeout(10000) }).then(async response => {
            if (!response.ok) return {};
            const text = await response.text();
            return text.length < 200000 ? JSON.parse(text) : {};
          }).catch(() => ({}));
        }
        const registry = await chapterRegistry;
        const indexed = PulseListening.validate(registry[asset.sha256], asset);
        if (indexed) return indexed;
        // A CDN can briefly retain yesterday's index; the SHA-addressed file
        // is independently validated and cannot be borrowed from other audio.
        const sidecar = await fetch(new URL('assets/chapters/' + asset.sha256 + '.json', base),
          {cache:'no-cache',signal:AbortSignal.timeout(10000)});
        if (!sidecar.ok) return null;
        const text = await sidecar.text();
        return text.length < 65536 ? PulseListening.validate(JSON.parse(text),asset) : null;
      } catch (_) { return null; }
    })());
    const pending = chapterCache.get(asset.sha256);
    const data = await pending;
    if (!data && chapterCache.get(asset.sha256) === pending) chapterCache.delete(asset.sha256);
    return data;
  }
  const tabs = make("div", "player-tabs");
  tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Oynatıcı görünümü");
  const transportTab = make("button", "", "Oynatıcı"), chapterTab = make("button", "", "Bu bölümde");
  const chapterPanel = make("div", "player-chapters");
  chapterPanel.hidden = tabs.hidden = true;
  const chapterList = make("ol", "chapter-list");
  chapterPanel.append(chapterList);
  let currentChapters = null, chapterAsset = null, chapterLoadEpoch = 0;
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
    const epoch = ++chapterLoadEpoch;
    chapterAsset = asset.sha256; currentChapters = null; tabs.hidden = true;
    chapterList.replaceChildren(); chooseTab(false); syncChapters();
    const data = selected.kind === "podcast" ? await chaptersFor(asset) : null;
    if (chapterAsset !== asset.sha256 || epoch !== chapterLoadEpoch) return;
    currentChapters = data; tabs.hidden = !data;
    if (data) chapterList.replaceChildren(...chapterRows(data,selected.section,selected.kind,selectedRelease));
    syncChapters();
  }
  async function hydrateChapters() {
    const listen = $(".listen-player");
    if (!listen || listen.closest(".episode")?.querySelector(".episode-chapters")) return;
    const section = listen.dataset.listenSection;
    const kind = new URLSearchParams(location.search).get("ses") === "ozet" ? "summary" : "podcast";
    if (kind !== "podcast") return;
    const asset = release.editions[section].podcast;
    if (!asset || window.PulseControls?.state.podcasts[section] === false) return;
    const data = await chaptersFor(asset);
    if (!data || !listen.isConnected || listen.closest(".episode")?.querySelector(".episode-chapters")) return;
    const container = make("section","episode-chapters");
    const heading = make("h2","","Bu bölümde"), list = make("ol","chapter-list");
    list.append(...chapterRows(data,section,kind)); container.append(heading,list);
    listen.closest(".episode").append(container); syncChapters();
  }
  async function refreshMissingChapters() {
    if (!release || window.PULSE_ARCHIVE || document.hidden) return;
    if (chapterRefreshRunning) { chapterRefreshAgain = true; return; }
    const missingPlayer = !selectedClip && selected?.kind === "podcast" && !currentChapters &&
      selectedRelease.manifest.release_id === release.manifest.release_id;
    const listenPage = $(".listen-player");
    const missingPage = listenPage && release.editions[listenPage.dataset.listenSection]?.podcast &&
      new URLSearchParams(location.search).get("ses") !== "ozet" && !$(".episode-chapters");
    const missingClips = all('.story-clip-slot').some(slot => { const s = slot.dataset.section || document.body.dataset.section; return !slot.childElementCount && release.editions[s]?.podcast && window.PulseControls?.state.podcasts[s] !== false; });
    if (!missingPlayer && !missingPage && !missingClips) return;
    chapterRefreshRunning = true;
    try {
      chapterRegistry = null;
      // Do not borrow an in-flight missing response from before this verified update.
      if (missingPlayer) chapterCache.delete(selectedRelease.editions[selected.section].podcast.sha256);
      if (missingPage) chapterCache.delete(release.editions[listenPage.dataset.listenSection].podcast.sha256);
      clipIndexPromise = null; hydrateStoryClips();
      if (missingPlayer) {
        chapterAsset = null;
        await loadSelectedChapters();
      }
      if (missingPage) await hydrateChapters();
    } finally {
      chapterRefreshRunning = false;
      if (chapterRefreshAgain) {
        chapterRefreshAgain = false;
        await refreshMissingChapters();
      }
    }
  }
  window.addEventListener("pulse:verified", event => {
    if (event.detail?.release_id === release?.manifest.release_id)
      refreshMissingChapters().catch(() => {});
  });
  let playbackChannel = null;
  try { playbackChannel = new BroadcastChannel("pulse-audio-session-v1");
    playbackChannel.onmessage = event => { if (event.data === "playing") { if (selectedClip) selectedClip.stopped = true; audio.pause(); playRequest++; } };
    audio.addEventListener("play",()=>playbackChannel.postMessage("playing"));
  } catch (_) {}
  function saveState() {
    if (
      release && !window.PULSE_ARCHIVE &&
      renderedURL.pathname === location.pathname &&
      renderedURL.search === location.search
    )
      try {
        saveFlowProgress?.();
        history.replaceState(
          {
            ...history.state,
            pulse: true,
            releaseId: release?.manifest.release_id,
            scroll: readingScroll(),
            list: listState,
            flow: flowSnapshot,
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
  const flowProgressKey = 'pulse-flow-progress-v1';
  let flowSnapshot = null, revealFlowStory = null, saveFlowProgress = null;
  function storedFlow(stories) {
    if (window.PULSE_ARCHIVE) return null;
    try {
      const item = JSON.parse(localStorage.getItem(flowProgressKey));
      if (!item || item.date !== release.manifest.publish_date) {
        localStorage.removeItem(flowProgressKey); return null;
      }
      if (!['', 'teknoloji', 'oyun'].includes(item.filter) ||
          !Number.isFinite(item.position) || item.position < 0 || item.position > 1e7) return null;
      const visible = stories.filter(story => !item.filter || story.dataset.section === item.filter);
      const index = visible.findIndex(story => story.dataset.section === item.section && story.dataset.story === item.story);
      return {filter:item.filter, index:index >= 0 && item.complete === true && item.releaseId === release.manifest.release_id ? visible.length : Math.max(0,index),
        positions:index < 0 ? {} : {[item.section + ':' + item.story]:item.position}};
    } catch (_) { return null; }
  }
  function setupFlow(state) {
    document.body.classList.toggle('in-news-flow', document.body.dataset.page === 'flow');
    revealFlowStory = saveFlowProgress = null;
    const root = $('.news-flow');
    if (!root) { flowSnapshot = null; return; }
    const viewport = $('.flow-viewport', root), stories = all('.flow-story', root);
    const next = $('.flow-next', root), previous = $('.flow-previous', root);
    const endPanel = $('.flow-end', root), announcement = $('.flow-announcement', root);
    const closeFlow = $('.flow-close', root), category = $('.flow-category', root);
    const stepNext = $('.flow-step-next', root), storyNavigation = $('.flow-story-navigation', root);
    const counter = $('.flow-count', root);
    const nextImage = $('.flow-next-image', root);
    nextImage.onerror = () => {nextImage.hidden = true; next.classList.remove('has-image');};
    nextImage.onload = () => {nextImage.hidden = false; next.classList.add('has-image');};
    if (history.state?.flowReturn) closeFlow.href = history.state.flowReturn;
    const initial = state?.flow || storedFlow(stories) || {filter:state?.flowInitialSection || '',index:0,positions:{}};
    let filter = initial?.filter || '', index = Number.isInteger(initial?.index) ? initial.index : 0;
    if (!['', 'teknoloji', 'oyun'].includes(filter)) filter = '';
    const positions = {...initial?.positions};
    let visible = [], active = null, wheelAt = -Infinity, gesture = null, lastWheel = -Infinity, restoreEpoch = 0;
    const save = () => {
      if (active) positions[active.dataset.section + ':' + active.dataset.story] = viewport.scrollTop;
      flowSnapshot = {filter, index, positions}; saveState();
    };
    const atTop = () => viewport.scrollTop <= 2;
    const atBottom = () => viewport.scrollTop + viewport.clientHeight >= viewport.scrollHeight - 3;
    function show(target, restore = true) {
      const epoch = ++restoreEpoch;
      if (active) positions[active.dataset.section + ':' + active.dataset.story] = viewport.scrollTop;
      const complete = target >= visible.length;
      index = Math.max(0, Math.min(visible.length, target));
      stories.forEach(story => story.hidden = true);
      active = complete ? null : visible[index];
      endPanel.hidden = !complete; viewport.hidden = complete;
      if (active) {
        active.hidden = false;
        const desired = restore ? positions[active.dataset.section + ':' + active.dataset.story] || 0 : 0;
        viewport.scrollTop = desired;
        const photo = active.querySelector('.story-image');
        Promise.all([photo?.decode().catch(()=>{}), document.fonts?.ready]).then(()=>{
          requestAnimationFrame(()=>{if(epoch===restoreEpoch) viewport.scrollTop=desired;});
        });
        const image = $('img', active); if (image) image.loading = 'eager';
        const upcoming = visible[index + 1]?.querySelector('img'); if (upcoming) upcoming.loading = 'eager';
        if (!matchMedia('(prefers-reduced-motion: reduce)').matches)
          active.animate([{opacity:.5, transform:'translateY(12px)'}, {opacity:1, transform:'translateY(0)'}], {duration:180, easing:'ease-out'});
      }
      counter.textContent = complete ? visible.length + ' / ' + visible.length : (index + 1) + ' / ' + visible.length;
      if (active) ($('.news-figure',active) || active).append(counter);
      previous.disabled = index === 0; next.disabled = stepNext.disabled = complete;
      storyNavigation.hidden = complete;
      const upcoming = visible[index + 1];
      $('.flow-next-label', root).textContent = upcoming ? 'Sıradaki haber' : 'Günün son haberi';
      $('.flow-next-title', root).textContent = upcoming ? $('h1',upcoming).textContent : 'Akışı tamamla';
      $('.flow-next-category', root).textContent = upcoming ? $('.eyebrow',upcoming).textContent : '';
      const preview = $('.flow-next-image',root), image = upcoming?.querySelector('.story-image');
      preview.hidden = !image; next.classList.toggle('has-image', !!image);
      if (image) preview.src = image.src; else preview.removeAttribute('src');
      next.setAttribute('aria-label', upcoming ? 'Sonraki haber: ' + $('h1',upcoming).textContent : 'Akışı tamamla');
      announcement.textContent = complete ? 'Günün akışını tamamladın' : counter.textContent + ' · ' + $('h1',active).textContent;

      save();
    }
    function filterStories() {
      visible = stories.filter(story => !filter || story.dataset.section === filter);
      category.value = filter;
      show(index);
    }
    function move(target) {
      // Persistent footer controls must not pull the new story down to their
      // focused position when its content changes (especially mobile browsers).
      viewport.focus({preventScroll:true});
      show(target);
      if (viewport.hidden) $('.flow-end-previous', root).focus({preventScroll:true});
      else viewport.focus({preventScroll:true});
    }
    next.onclick = () => move(index + 1);
    previous.onclick = () => move(index - 1);
    $('.flow-end-previous', root).onclick = () => move(Math.max(0, visible.length - 1));
    $('.flow-restart', root).onclick = $('.flow-reset', root).onclick = () => { index = 0; show(0, false); viewport.focus(); };
    stepNext.onclick = () => move(index + 1);
    category.onchange = () => {
      if (category.value === filter) return;
      filter = category.value; index = 0; filterStories();
    };
    let scrollSaveTimer = null, lastFlowWrite = 0;
    viewport.addEventListener('scroll', () => {
      if (active) positions[active.dataset.section + ':' + active.dataset.story] = viewport.scrollTop;
      flowSnapshot = {filter, index, positions};
      if (performance.now() - lastFlowWrite > 500) {saveState(); lastFlowWrite = performance.now();}
      clearTimeout(scrollSaveTimer);
      scrollSaveTimer = setTimeout(saveState, 220);
    }, {passive:true, signal:pageEvents.signal});
    pageEvents.signal.addEventListener('abort', () => clearTimeout(scrollSaveTimer), {once:true});
    for (const event of ['pointerdown','touchstart','wheel','keydown'])
      window.addEventListener(event,()=>restoreEpoch++,{capture:true,passive:true,signal:pageEvents.signal});
    viewport.addEventListener('touchstart', event => {
      const control = event.target.closest('button,a,input,select,textarea,[contenteditable]');
      if ((control && !control.matches('.flow-next,.flow-previous')) || event.touches.length !== 1) {gesture = null; return;}
      gesture = {x:event.touches[0].clientX, y:event.touches[0].clientY, top:atTop(), bottom:atBottom()};
    }, {passive:true, signal:pageEvents.signal});
    viewport.addEventListener('touchmove', event => {
      if (!gesture || event.touches.length !== 1) return;
      const dx = event.touches[0].clientX - gesture.x, dy = event.touches[0].clientY - gesture.y;
      // Consume only a new outward boundary gesture. Native momentum must not
      // scroll the next article immediately after the content swap.
      if (Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx) * 1.5 &&
          ((dy < 0 && gesture.bottom) || (dy > 0 && gesture.top && index > 0)))
        if (event.cancelable) event.preventDefault();
    }, {passive:false, signal:pageEvents.signal});
    viewport.addEventListener('touchend', event => {
      if (!gesture || !event.changedTouches.length) return;
      const dx = event.changedTouches[0].clientX - gesture.x, dy = event.changedTouches[0].clientY - gesture.y;
      if (Math.abs(dy) >= 70 && Math.abs(dy) > Math.abs(dx) * 1.5) {
        if (dy < 0 && gesture.bottom) show(index + 1);
        else if (dy > 0 && gesture.top && index > 0) show(index - 1);
      }
      gesture = null;
    }, {passive:true, signal:pageEvents.signal});
    viewport.addEventListener('touchcancel', () => gesture = null, {signal:pageEvents.signal});
    viewport.addEventListener('wheel', event => {
      const now = performance.now(), fresh = now - lastWheel > 260;
      lastWheel = now;
      // Require a new wheel gesture at the boundary, never the tail of inertia.
      if (!fresh || now - wheelAt < 700 || Math.abs(event.deltaY) < 12 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      if ((event.deltaY > 0 && atBottom()) || (event.deltaY < 0 && atTop() && index > 0)) {
        event.preventDefault(); wheelAt = now; show(index + (event.deltaY > 0 ? 1 : -1));
      }
    }, {passive:false, signal:pageEvents.signal});
    document.addEventListener('keydown', event => {
      if (event.defaultPrevented || event.target.closest('input,textarea,select,[contenteditable],.audio-session') || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'PageDown') {
        event.preventDefault();
        if (!viewport.hidden && atBottom()) move(index + 1);
        else viewport.scrollBy({top:viewport.clientHeight * .85, behavior:'instant'});
      } else if (event.key === 'PageUp') {
        event.preventDefault();
        if ((viewport.hidden || atTop()) && index > 0) move(index - 1);
        else viewport.scrollBy({top:-viewport.clientHeight * .85, behavior:'instant'});
      }
    }, {signal:pageEvents.signal});
    revealFlowStory = (section, storyId) => {
      const target = stories.find(item => item.dataset.section === section && item.dataset.story === storyId);
      if (!target) return false;
      if (filter && filter !== section) { filter = section; index = 0; filterStories(); }
      show(visible.indexOf(target), false); viewport.focus(); return true;
    };
    saveFlowProgress = () => {
      if (window.PULSE_ARCHIVE) return;
      const story = active || visible.at(-1);
      if (!story) return;
      try {
        localStorage.setItem(flowProgressKey, JSON.stringify({date:release.manifest.publish_date,releaseId:release.manifest.release_id,
          section:story.dataset.section, story:story.dataset.story, filter,
          position:active ? viewport.scrollTop : positions[story.dataset.section + ':' + story.dataset.story] || 0,
          complete:!active}));
      } catch (_) {}
    };
    filterStories();
  }

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
      const filtered = terms.length > 0 || categories.length > 0 || (!document.body.dataset.section && !!filter);
      const resultCount = $("#story-count");
      resultCount.hidden = !filtered;
      resultCount.textContent = filtered ? count + " haber bulundu" : "";
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
    const illustrateFallback = (fallback, section) => {
      if (!fallback || fallback.querySelector('.fallback-art')) return;
      const art = make('img', 'fallback-art'); art.alt = ''; art.setAttribute('aria-hidden','true');
      art.src = new URL('assets/covers/' + (section === 'oyun' ? 'oyun' : 'teknoloji') + '-768.webp', base).href;
      fallback.prepend(art);
      const credit = make('small', 'fallback-credit', 'PULSE · Temsili görsel'); fallback.append(credit);
    };
    for (const missing of all('.image-missing')) {
      illustrateFallback($('.image-fallback',missing), missing.closest('[data-section]')?.dataset.section);
    }
    for (const image of all(".story-image")) {
      const frame = image.closest(".image-frame");
      if (!frame) continue;
      const fallback = $(".image-fallback", frame);
      const show = () => {
        image.hidden = true;
        fallback.hidden = false;
        image.closest('.news-figure')?.classList.add('is-fallback');
        illustrateFallback(fallback, image.closest('[data-section]')?.dataset.section);
      };
      const hide = () => {
        image.hidden = false;
        fallback.hidden = true;
        image.closest('.news-figure')?.classList.remove('is-fallback');
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
    setupFlow(state);
    hydrateStoryClips();
    hydrateChapters();
    for (const start of all(".audio-start"))
      start.addEventListener(
        "click",
        () => {
          if (configure(start.dataset.section, start.dataset.kind)) toggle();
        },
        { signal: pageEvents.signal },
      );
    const listen = $(".listen-player");
    if (listen) {
      const section = listen.dataset.listenSection,
        kind =
          new URLSearchParams(location.search).get("ses") === "ozet" || !release.editions[section].podcast || window.PulseControls?.state.podcasts[section] === false
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
    window.PulseControls?.refreshView();
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
          flowReturn: doc.body.dataset.page === "flow" ? location.href : null,
          flow: null, flowInitialSection: doc.body.dataset.page === "flow" ? document.body.dataset.section || "" : "",
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
    if (a.matches(".flow-close") && history.state?.flowReturn) { saveState(); history.back(); return; }
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
    if (window.PulseControls?.state.enabled === false) return;
    if (release?.manifest.release_id === next.manifest.release_id) return;
    // A verified new issue must not replace the listener’s active immutable recording.
    release = next;
    if (selected) configure(selected.section, selected.kind, selectedRelease);
    chapterRegistry = null; chapterCache.clear(); clipIndexPromise = null;
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
  function receiveRelease(next) {
    ready(next).catch(() => window.dispatchEvent(new Event('pulse:render-error')));
  }
  window.addEventListener("pulse:ready", (event) => receiveRelease(event.detail));
  window.addEventListener("pulse:locked", () => {
    $(".topics-dialog")?.close();
    collapsePanel(false);
    miniLink.removeAttribute("href");
    release = null;
    pendingNav?.abort();
  });
  window.addEventListener("pulse:controls", () => {
    const controls = window.PulseControls?.state;
    if (controls && (!controls.enabled || (selected?.kind === 'podcast' && controls.podcasts[selected.section] === false))) close.click();
    window.PulseControls?.refreshView();
  });
  if (window.PULSE_RELEASE) receiveRelease(window.PULSE_RELEASE);
})();
