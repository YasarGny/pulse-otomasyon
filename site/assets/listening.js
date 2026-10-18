/* Optional, audio-bound chapter data and measured, reversible title motion. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PulseListening = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  function validate(data, asset) {
    if (!data || data.schema_version !== 1 || data.reviewed !== true ||
        data.audio_sha256 !== asset.sha256 || !Number.isFinite(asset.duration) ||
        !Array.isArray(data.chapters) || !data.chapters.length || data.chapters.length > 40)
      return null;
    let previous = -10;
    for (const item of data.chapters) {
      if (!item || typeof item !== "object" || !Number.isFinite(item.start) || item.start < 0 || item.start >= asset.duration ||
          item.start - previous < 5 || typeof item.title !== "string" ||
          !item.title.trim() || item.title.length > 240 || /[\x00-\x1f]/.test(item.title))
        return null;
      previous = item.start;
    }
    return data;
  }
  function activeIndex(chapters, time) {
    let index = -1;
    chapters.forEach((chapter, i) => { if (time >= chapter.start) index = i; });
    return index;
  }
  function marquee(viewport, track, blocked) {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let animation = null;
    function refresh() {
      animation?.cancel();
      animation = null;
      viewport.classList.toggle("title-static", reduced.matches);
      const distance = Math.max(0, track.scrollWidth - viewport.clientWidth);
      if (reduced.matches || distance <= 1 || !viewport.getClientRects().length) return;
      const travel = distance / 24 * 1000;
      const total = 2500 + travel + 3000 + travel + 4000;
      const at = (ms) => ms / total;
      animation = track.animate([
        { transform: "translateX(0)", offset: 0 },
        { transform: "translateX(0)", offset: at(2500), easing: "ease-in-out" },
        { transform: `translateX(${-distance}px)`, offset: at(2500 + travel) },
        { transform: `translateX(${-distance}px)`, offset: at(5500 + travel), easing: "ease-in-out" },
        { transform: "translateX(0)", offset: at(5500 + travel * 2) },
        { transform: "translateX(0)", offset: 1 },
      ], { duration: total, iterations: Infinity });
      sync();
    }
    function sync() {
      if (!animation) return;
      if (document.hidden || blocked() || viewport.matches(":hover, :focus-within")) animation.pause();
      else animation.play();
    }
    for (const event of ["pointerenter", "pointerleave", "focusin", "focusout"])
      viewport.addEventListener(event, () => queueMicrotask(sync));
    document.addEventListener("visibilitychange", sync);
    reduced.addEventListener("change", refresh);
    new ResizeObserver(refresh).observe(viewport);
    return { refresh, sync };
  }
  return { validate, activeIndex, marquee };
});
