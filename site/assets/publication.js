/* Shared, testable publication rules. Time comes from the same-origin HTTP response. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PulsePublication = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const sections = ["teknoloji", "oyun"];
  function dateParts(at) {
    const p = Object.fromEntries(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: "Europe/Istanbul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      })
        .formatToParts(at)
        .filter((x) => x.type !== "literal")
        .map((x) => [x.type, x.value]),
    );
    return {
      date: `${p.year}-${p.month}-${p.day}`,
      hour: Number(p.hour),
      minute: Number(p.minute),
    };
  }
  function expectedDate(at) {
    const p = dateParts(at);
    if (p.hour >= 6) return p.date;
    return new Date(Date.parse(p.date + "T12:00:00Z") - 86400000)
      .toISOString()
      .slice(0, 10);
  }
  function httpTime(headers) {
    const raw = headers.get("date"),
      age = Number(headers.get("age") || 0);
    const epoch = Date.parse(raw);
    if (!raw || !Number.isFinite(epoch) || !Number.isFinite(age) || age < 0)
      throw Error("Sunucu zamanı doğrulanamadı");
    return new Date(epoch + age * 1000);
  }
  function isReady(m, at) {
    if (
      !m ||
      m.schema_version !== 1 ||
      m.status !== "ready" ||
      m.publish_date !== expectedDate(at) ||
      m.validation !== "full-mp3-decode+sha256+content-v1"
    )
      return false;
    if (
      !/^\d{4}-\d{2}-\d{2}-[a-f0-9]{16}$/.test(m.release_id) ||
      !m.release_id.startsWith(m.publish_date + "-")
    )
      return false;
    const earliest = m.publish_date + "T07:30:00+03:00";
    if (m.not_before !== earliest || at.getTime() < Date.parse(earliest))
      return false;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(m.game_start || "")) return false;
    return sections.every(
      (s) =>
        m.editions?.[s]?.file === s + ".json" &&
        /^[a-f0-9]{64}$/.test(m.editions[s].sha256) &&
        Number.isInteger(m.editions[s].issue) &&
        m.editions[s].issue > 0,
    );
  }
  function safeRelative(path) {
    return (
      typeof path === "string" &&
      /^[a-zA-Z0-9_./-]+$/.test(path) &&
      !path.startsWith("/") &&
      !path.split("/").some((p) => p === ".." || p === "." || !p)
    );
  }
  function issue(date, start) {
    return (
      Math.round(
        (Date.parse(date + "T00:00:00Z") - Date.parse(start + "T00:00:00Z")) /
          86400000,
      ) + 1
    );
  }
  function editionValid(d, section, m) {
    if (
      d?.section !== section ||
      d.publish_date !== m.publish_date ||
      d.ready !== true ||
      d.issue !== m.editions[section].issue ||
      d.issue !==
        issue(
          d.publish_date,
          section === "teknoloji" ? "2026-10-16" : m.game_start,
        )
    )
      return false;
    if (
      !Array.isArray(d.stories) ||
      d.stories.length < 3 ||
      d.stories.length > 12
    )
      return false;
    const ids = new Set(),
      sources = new Set();
    if (
      !d.stories.every((s) => {
        if (
          !["id", "title", "summary", "why", "category", "source_name"].every(
            (k) => typeof s[k] === "string" && s[k].trim(),
          ) ||
          !safeHttps(s.source_url) ||
          ids.has(s.id) ||
          sources.has(s.source_url)
        )
          return false;
        ids.add(s.id);
        sources.add(s.source_url);
        return true;
      })
    )
      return false;
    return ["summary", "podcast"].every((kind) => {
      const a = d[kind],
        min = kind === "summary" ? 20 : 40;
      return (
        a?.file === `${section}/${kind}.mp3` &&
        Number.isFinite(a.duration) &&
        a.duration >= min &&
        Number.isInteger(a.bytes) &&
        a.bytes >= 25000 &&
        /^[a-f0-9]{64}$/.test(a.sha256) &&
        a.episode === d.issue
      );
    });
  }
  function safeHttps(value) {
    try {
      const u = new URL(value);
      return (
        u.protocol === "https:" && !!u.hostname && !u.username && !u.password
      );
    } catch {
      return false;
    }
  }
  async function sha256(bytes) {
    return Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (x) => x.toString(16).padStart(2, "0"),
    ).join("");
  }
  return {
    sections,
    dateParts,
    expectedDate,
    httpTime,
    isReady,
    editionValid,
    safeRelative,
    safeHttps,
    sha256,
  };
});
