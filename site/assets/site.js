(() => {
  "use strict";
  const section = document.body.dataset.page,
    $ = (id) => document.getElementById(id),
    rules = window.PulsePublication;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  function player(target, asset, release, label) {
    const audio = el("audio");
    audio.preload = "none";
    audio.src = new URL(asset.file, release.url).href;
    audio.setAttribute("aria-label", label);
    const box = target.closest(".audio-box");
    const ui = el("div", "player");
    ui.setAttribute("role", "group");
    ui.setAttribute("aria-label", label + " oynatıcı");
    const icons = {
      play: '<path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
      pause: '<path d="M8 6v12M16 6v12" stroke-width="4"/>',
      back: '<path d="M5 9a8 8 0 1 1-1 8M5 3v6h6"/><path d="M10 12v5m3-5h3v2h-3v3h3" stroke-width="1.1"/>',
      forward:
        '<path d="M19 9a8 8 0 1 0 1 8M19 3v6h-6"/><path d="M10 12v5m3-5h3v2h-3v3h3" stroke-width="1.1"/>',
      volume:
        '<path d="m11 5-5 4H3v6h3l5 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
      mute: '<path d="m11 5-5 4H3v6h3l5 4ZM16 9l6 6m0-6-6 6"/>',
    };
    const icon = (button, name) => {
      button.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true">' + icons[name] + "</svg>";
    };
    const button = (cls, name, text) => {
      const b = el("button", cls);
      b.type = "button";
      b.setAttribute("aria-label", label + ": " + text);
      icon(b, name);
      return b;
    };
    const play = button("player-play", "play", "Oynat");
    const back = button("player-skip", "back", "15 saniye geri al");
    const forward = button("player-skip", "forward", "15 saniye ileri al");
    const speed = el("select", "player-speed");
    speed.setAttribute("aria-label", label + ": oynatma hızı");
    for (const value of [0.75, 1, 1.25, 1.5, 1.75, 2]) {
      const option = el("option", "", value.toString().replace(".", ",") + "×");
      option.value = String(value);
      option.selected = value === 1;
      speed.append(option);
    }
    const controls = el("div", "player-controls");
    controls.append(play, back, forward, speed);
    const seek = el("input", "player-seek");
    seek.type = "range";
    seek.min = "0";
    seek.max = String(asset.duration);
    seek.step = ".1";
    seek.value = "0";
    seek.disabled = true;
    seek.setAttribute("aria-label", label + ": ilerleme");
    const times = el("div", "player-times");
    const current = el("span", "", "0:00");
    const end = el("span");
    times.append(current, end);
    const format = (seconds) => {
      seconds = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
      return (
        Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
      );
    };
    let duration = asset.duration;
    end.textContent = format(duration);
    const mute = button("player-mute", "volume", "Sesi kapat");
    mute.setAttribute("aria-pressed", "false");
    const volume = el("input", "player-volume");
    volume.type = "range";
    volume.min = "0";
    volume.max = "1";
    volume.step = ".05";
    volume.value = "1";
    volume.setAttribute("aria-label", label + ": ses seviyesi");
    const bottom = el("div", "player-bottom");
    const episode = el(
      "span",
      "player-episode",
      "Bölüm " + String(asset.episode).padStart(3, "0"),
    );
    bottom.append(episode, mute, volume);
    const error = el("p", "audio-error", "Ses yüklenemedi. Yeniden deneyin.");
    error.hidden = true;
    error.setAttribute("role", "status");
    const retry = el("button", "retry", "Yeniden dene");
    retry.type = "button";
    retry.hidden = true;
    const showError = () => {
      error.hidden = retry.hidden = false;
      play.removeAttribute("aria-busy");
    };
    const updatePlay = (playing) => {
      icon(play, playing ? "pause" : "play");
      play.setAttribute(
        "aria-label",
        label + ": " + (playing ? "Duraklat" : "Oynat"),
      );
      box?.classList.toggle("is-playing", playing);
    };
    play.addEventListener("click", async () => {
      if (!audio.paused) {
        audio.pause();
        return;
      }
      error.hidden = retry.hidden = true;
      play.setAttribute("aria-busy", "true");
      try {
        await audio.play();
      } catch (e) {
        if (e.name !== "AbortError") showError();
      } finally {
        play.removeAttribute("aria-busy");
      }
    });
    audio.addEventListener("play", () => {
      document.querySelectorAll("audio").forEach((other) => {
        if (other !== audio) other.pause();
      });
      updatePlay(true);
    });
    for (const event of ["pause", "ended", "error"])
      audio.addEventListener(event, () => updatePlay(false));
    audio.addEventListener("error", showError);
    audio.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0)
        duration = audio.duration;
      seek.max = String(duration);
      seek.disabled = false;
      end.textContent = format(duration);
    });
    audio.addEventListener("timeupdate", () => {
      current.textContent = format(audio.currentTime);
      seek.value = String(audio.currentTime);
      seek.style.setProperty(
        "--progress",
        Math.min(100, (audio.currentTime / duration) * 100) + "%",
      );
      seek.setAttribute(
        "aria-valuetext",
        format(audio.currentTime) + " / " + format(duration),
      );
    });
    seek.addEventListener("input", () => {
      if (audio.readyState >= 1) audio.currentTime = Number(seek.value);
    });
    const jump = (delta) => {
      if (audio.readyState >= 1)
        audio.currentTime = Math.max(
          0,
          Math.min(duration, audio.currentTime + delta),
        );
    };
    back.addEventListener("click", () => jump(-15));
    forward.addEventListener("click", () => jump(15));
    speed.addEventListener("change", () => {
      audio.playbackRate = Number(speed.value);
    });
    const updateVolume = () => {
      const silent = audio.muted || audio.volume === 0;
      volume.style.setProperty("--progress", audio.volume * 100 + "%");
      icon(mute, silent ? "mute" : "volume");
      mute.setAttribute("aria-pressed", String(silent));
      mute.setAttribute(
        "aria-label",
        label + ": " + (silent ? "Sesi aç" : "Sesi kapat"),
      );
    };
    mute.addEventListener("click", () => {
      audio.muted = !audio.muted;
      updateVolume();
    });
    volume.addEventListener("input", () => {
      audio.volume = Number(volume.value);
      audio.muted = Number(volume.value) === 0;
      updateVolume();
    });
    audio.addEventListener("volumechange", updateVolume);
    retry.addEventListener("click", () => {
      error.hidden = retry.hidden = true;
      audio.load();
    });
    ui.append(controls, seek, times, bottom);
    target.replaceChildren(audio, ui, error, retry);
  }
  function render(release) {
    const data = release.editions[section];
    if (!data) return;
    const formatted = new Intl.DateTimeFormat("tr-TR", {
      timeZone: "Europe/Istanbul",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date(data.publish_date + "T12:00:00+03:00"));
    $("issue").textContent =
      `${formatted} · Sayı ${String(data.issue).padStart(3, "0")}`;
    $("story-count").textContent = `${data.stories.length} haber`;
    $("stories").replaceChildren();
    data.stories.forEach((s, index) => {
      const article = el("article", "story");
      const category = el("div", "category");
      category.append(
        el("span", "story-index", String(index + 1).padStart(2, "0")),
        document.createTextNode(s.category),
      );
      if (s.image_url && rules.safeHttps(s.image_url)) {
        const figure = el("figure"),
          image = el("img", "story-image");
        image.src = s.image_url;
        image.alt = s.title;
        image.loading = "lazy";
        image.decoding = "async";
        image.referrerPolicy = "no-referrer";
        image.width = 800;
        image.addEventListener(
          "load",
          () => {
            image.width = image.naturalWidth;
            image.height = image.naturalHeight;
            image.style.maxWidth = image.naturalWidth + "px";
          },
          { once: true },
        );

        image.addEventListener("error", () => figure.remove(), { once: true });
        figure.append(
          image,
          el("figcaption", "", `Görsel kaynağı: ${s.source_name}`),
        );
        article.append(figure);
      }
      article.append(category, el("h3", "", s.title));
      const why = el("div", "why");
      why.append(el("strong", "", "NEDEN ÖNEMLİ?"), el("p", "", s.why));
      const link = el("a", "source-link", `${s.source_name} · Kaynağı oku →`);
      link.href = s.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      article.append(el("p", "", s.summary), why, link);
      $("stories").append(article);
    });
    $("stories").setAttribute("aria-busy", "false");
    $("notice").hidden = true;
    player($("summary"), data.summary, release, "Günün sesli özeti");
    player($("podcast"), data.podcast, release, data.podcast.title);
    document.title = `PULSE ${section === "teknoloji" ? "Teknoloji" : "Oyun"} · Sayı ${String(data.issue).padStart(3, "0")} · ${formatted}`;
  }
  window.addEventListener("pulse:ready", (event) => render(event.detail));
  if (window.PULSE_RELEASE) render(window.PULSE_RELEASE);
})();
