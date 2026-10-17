// Rasterize the preserved P. favicon; maskable icons keep all marks in the safe zone.
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PULSE_CHROMIUM || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  try {
    const svg = await fs.readFile("site/assets/favicon.svg", "utf8");
    for (const size of [180, 192, 512]) {
      const page = await browser.newPage({
        viewport: { width: size, height: size },
        deviceScaleFactor: 1,
      });
      await page.setContent(
        `<style>html,body{margin:0;width:100%;height:100%;background:#080e1a}svg{display:block;width:100%;height:100%}</style>${svg}`,
      );
      await page.screenshot({ path: `site/assets/app-${size}.png` });
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
