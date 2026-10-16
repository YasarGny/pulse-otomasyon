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
      play: '<path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
      pause: '<path d="M8 6v12M16 6v12" stroke-width="4"/>',
      back: '<path d="M5 9a8 8 0 1 1-1 8M5 3v6h6"/><text x="12" y="17" text-anchor="middle" fill="currentColor" stroke="none" font-size="8" font-family="Arial,sans-serif" font-weight="700">10</text>',
      forward:
        '<path d="M19 9a8 8 0 1 0 1 8M19 3v6h-6"/><text x="12" y="17" text-anchor="middle" fill="currentColor" stroke="none" font-size="8" font-family="Arial,sans-serif" font-weight="700">10</text>',
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
    const back = button("player-skip", "back", "10 saniye geri al");
    const forward = button("player-skip", "forward", "10 saniye ileri al");
    const rates = [1, 1.1, 1.2, 1.25, 1.5, 2];
    const speed = el("button", "player-speed", "1×");
    speed.type = "button";
    let rateIndex = 0;
    speed.setAttribute(
      "aria-label",
      label + ": hız 1×, değiştirmek için basın",
    );
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
    back.addEventListener("click", () => jump(-10));
    forward.addEventListener("click", () => jump(10));
    speed.addEventListener("click", () => {
      rateIndex = (rateIndex + 1) % rates.length;
      audio.playbackRate = rates[rateIndex];
      speed.textContent = rates[rateIndex] + "×";
      speed.setAttribute(
        "aria-label",
        label + ": hız " + rates[rateIndex] + "×, değiştirmek için basın",
      );
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
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(new Date(data.publish_date + "T12:00:00+03:00"));
    $("issue").textContent =
      `${formatted} · Sayı ${String(data.issue).padStart(3, "0")}`;
    $("story-count").textContent = `${data.stories.length} haber`;
    $("stories").replaceChildren();
    document.querySelector(".news-tools")?.remove();
    document.querySelector(".news-more")?.remove();
    const tools = el("div", "news-tools");
    const filter = el("select", "news-filter");
    filter.setAttribute("aria-label", "Haber kategorisi");
    const all = el("option", "", "Tüm kategoriler");
    all.value = "";
    filter.append(all);
    for (const category of [...new Set(data.stories.map((s) => s.category))]) {
      const option = el("option", "", category);
      option.value = category;
      filter.append(option);
    }
    const more = el("button", "news-more", "Daha fazla göster");
    more.type = "button";
    let visibleCount = 8;
    const updateNews = () => {
      let seen = 0;
      for (const article of $("stories").children) {
        const matches =
          !filter.value || article.dataset.category === filter.value;
        article.hidden = !matches || seen++ >= visibleCount;
      }
      more.hidden = seen <= visibleCount;
      const shown = Math.min(seen, visibleCount);
      $("story-count").textContent = `${shown} / ${seen} haber`;
    };
    filter.onchange = () => {
      visibleCount = 8;
      updateNews();
    };
    more.onclick = () => {
      visibleCount += 8;
      updateNews();
    };
    tools.append(filter);
    $("stories").before(tools);
    $("stories").after(more);
    data.stories.forEach((s, index) => {
      const article = el("article", "story");
      article.dataset.category = s.category;
      if (index >= 5) article.classList.add("story-compact");
      const category = el("div", "category");
      category.append(
        el("span", "story-index", String(index + 1).padStart(2, "0")),
        document.createTextNode(s.category),
      );
      if (s.image_url && rules.safeHttps(s.image_url)) {
        const figure = el("figure"),
          image = el("img", "story-image");
        image.src =
          window.PULSE_ARCHIVE &&
          /^\.\.\/\.\.\/media\/[a-f0-9]+\.(jpg|png|webp|gif|svg)$/.test(
            s.archive_image || "",
          )
            ? new URL(s.archive_image, release.url).href
            : s.image_url;
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
      const heading = el("h3");
      const detail = el("a", "story-detail-link", s.title);
      detail.href = "haber/" + encodeURIComponent(s.id) + "/index.html";
      heading.append(detail);
      article.append(category, heading);
      const link = el("a", "source-link", `${s.source_name} · Kaynağı oku →`);
      link.href = s.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      article.append(
        el("p", "", s.brief || s.summary.split(/(?<=[.!?])\s+/)[0]),
        link,
      );
      $("stories").append(article);
    });
    updateNews();
    $("stories").setAttribute("aria-busy", "false");
    $("notice").hidden = true;
    player($("summary"), data.summary, release, "Günün sesli özeti");
    player($("podcast"), data.podcast, release, data.podcast.title);
    setupListening();
    document.title = `PULSE ${section === "teknoloji" ? "Teknoloji" : "Oyun"} · Sayı ${String(data.issue).padStart(3, "0")} · ${formatted}`;
  }
  function setupListening() {
    const tabs = document.querySelectorAll(".listen-tab");
    const panels = document.querySelectorAll(".listening-cards > section");
    tabs.forEach((tab) => {
      const activate = () => {
        tabs.forEach((t) => {
          t.setAttribute("aria-selected", String(t === tab));
          t.tabIndex = t === tab ? 0 : -1;
        });
        panels.forEach((panel) => {
          panel.hidden = panel.id !== tab.getAttribute("aria-controls");
          if (panel.hidden) panel.querySelector("audio")?.pause();
        });
      };
      tab.onclick = activate;
      tab.onkeydown = (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
          return;
        event.preventDefault();
        const next =
          event.key === "Home"
            ? tabs[0]
            : event.key === "End"
              ? tabs[tabs.length - 1]
              : [...tabs].find((t) => t !== tab);
        next.click();
        next.focus();
      };
    });
    tabs[0]?.click();
  }
  window.addEventListener("pulse:ready", (event) => render(event.detail));
  if (window.PULSE_RELEASE) render(window.PULSE_RELEASE);
})();
