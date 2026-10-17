/* Runs before first paint; publication access never depends on local storage. */
(() => {
  const root = document.documentElement;
  let selected = "dark";
  try {
    if (localStorage.getItem("pulse-theme") === "light") selected = "light";
  } catch (_) {}
  function apply(theme) {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#151618" : "#f6f5f1");
    for (const button of document.querySelectorAll(".theme-toggle")) {
      button.setAttribute(
        "aria-label",
        theme === "dark" ? "Açık temaya geç" : "Koyu temaya geç",
      );
      button.innerHTML =
        theme === "dark"
          ? '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg>'
          : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z"/></svg>';
    }
  }
  apply(selected);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".theme-toggle")) return;
    const theme = root.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("pulse-theme", theme);
    } catch (_) {}
    apply(theme);
  });
  document.addEventListener("DOMContentLoaded", () =>
    apply(root.dataset.theme),
  );
  window.addEventListener("pulse:navigate", () => apply(root.dataset.theme));
})();
