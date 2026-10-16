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
    const meta = el("div", "audio-meta");
    const minutes = Math.floor(asset.duration / 60),
      seconds = Math.floor(asset.duration % 60)
        .toString()
        .padStart(2, "0");
    meta.append(
      el("span", "", `Bölüm ${String(asset.episode).padStart(3, "0")}`),
      el("span", "", `${minutes}:${seconds}`),
    );
    const audio = el("audio");
    audio.controls = true;
    audio.preload = "none";
    audio.src = new URL(asset.file, release.url).href;
    audio.setAttribute("aria-label", label);
    audio.setAttribute("controlslist", "nodownload");
    const error = el(
      "p",
      "audio-error",
      "Ses yüklenemedi. Bağlantınızı kontrol edip yeniden deneyin.",
    );
    error.hidden = true;
    error.setAttribute("role", "status");
    const retry = el("button", "retry", "Sesi yeniden yükle");
    retry.type = "button";
    retry.hidden = true;
    audio.addEventListener("error", () => {
      error.hidden = false;
      retry.hidden = false;
    });
    retry.addEventListener("click", () => {
      error.hidden = true;
      retry.hidden = true;
      audio.load();
    });
    target.replaceChildren(meta, audio, error, retry);
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
    $("story-count").textContent =
      `${data.stories.length} haber · kaynaklarıyla`;
    $("stories").replaceChildren();
    data.stories.forEach((s, index) => {
      const article = el("article", "story");
      const category = el("div", "category");
      category.append(
        el("span", "story-index", String(index + 1).padStart(2, "0")),
        document.createTextNode(s.category),
      );
      article.append(category, el("h3", "", s.title));
      if (s.image_url && rules.safeHttps(s.image_url)) {
        const figure = el("figure"),
          image = el("img", "story-image");
        image.src = s.image_url;
        image.alt = s.title;
        image.loading = "lazy";
        image.decoding = "async";
        image.referrerPolicy = "no-referrer";
        image.width = 800;
        image.height = 450;
        image.addEventListener("error", () => figure.remove(), { once: true });
        figure.append(
          image,
          el("figcaption", "", `Görsel kaynağı: ${s.source_name}`),
        );
        article.append(figure);
      }
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
