// Social cover uses the preserved original art and the editor desk brand.
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.PULSE_CHROMIUM ||
      ((await fs.access("/usr/bin/chromium").then(
        () => true,
        () => false,
      ))
        ? "/usr/bin/chromium"
        : undefined),
    args: ["--no-sandbox"],
  });
  try {
    const covers = await Promise.all(
      ["teknoloji", "oyun"].map(
        async (s) =>
          "data:image/webp;base64," +
          (await fs.readFile("site/assets/covers/" + s + ".webp")).toString(
            "base64",
          ),
      ),
    );
    const page = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 1,
    });
    await page.setContent(
      `<!doctype html><html lang="tr"><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;padding:36px 48px;background:#151618;color:#f2f1ed;font-family:Arial,sans-serif}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #3c4046;padding-bottom:20px}b{font-size:36px;letter-spacing:-2px}b span{color:#f2a7cc}header p{font-size:16px;color:#babbc1}h1{font-size:42px;letter-spacing:-1.6px;margin:22px 0}main{display:flex;gap:24px}article{flex:1;min-width:0}img{display:block;width:100%;height:280px;object-fit:contain;background:#202225;border-radius:8px}h2{font-size:23px;margin:14px 0 6px}article p{margin:0;color:#babbc1;font-size:16px}</style><header><b>PULSE<span>.</span></b><p>Her sabah 07:30</p></header><h1>Teknoloji, oyun ve iyi muhabbet.</h1><main><article><img src="${covers[0]}" alt=""><h2>Teknoloji</h2><p>Yeni Sekme · Teknoloji podcast’i</p></article><article><img src="${covers[1]}" alt=""><h2>Oyun</h2><p>Moradon FM · Oyun podcast’i</p></article></main></html>`,
    );
    await page.evaluate(() =>
      Promise.all([...document.images].map((i) => i.decode())),
    );
    await page.screenshot({ path: "site/assets/og.png" });
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
