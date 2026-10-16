// Render authored brand artwork to the PNG format understood by social crawlers.
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
(async () => {
  const system = await fs.access("/usr/bin/chromium").then(
    () => "/usr/bin/chromium",
    () => undefined,
  );
  const browser = await chromium.launch({
    executablePath: process.env.PULSE_CHROMIUM || system,
    args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 1,
    });
    const svg = await fs.readFile("site/assets/og.svg", "utf8");
    await page.setContent(
      "<!doctype html><html><head><style>html,body{margin:0;background:#090f1d}svg{display:block}</style></head><body>" +
        svg +
        "</body></html>",
    );
    await page.screenshot({ path: "site/assets/og.png" });
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
