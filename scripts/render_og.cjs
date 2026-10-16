// Render the same optimized cover artwork and live typography for social previews.
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
    const covers = await Promise.all(
      ["teknoloji", "oyun"].map(
        async (section) =>
          "data:image/webp;base64," +
          (
            await fs.readFile("site/assets/covers/" + section + ".webp")
          ).toString("base64"),
      ),
    );
    const page = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 1,
    });
    await page.setContent(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
      *{box-sizing:border-box}body{margin:0;background:#080e1a;color:#f1f4fa;font-family:Arial,sans-serif;padding:45px 54px}header{display:flex;justify-content:space-between;align-items:center}b{font-size:26px;letter-spacing:-1px}header span{font-size:15px;color:#acb9cc}h1{font-size:55px;letter-spacing:-3px;margin:26px 0 30px;font-weight:600}h1 span{color:#f2a7cc}main{display:flex;gap:22px}article{flex:1;position:relative;border:1px solid #27354a;border-radius:20px;overflow:hidden;height:335px}img{width:100%;height:100%;object-fit:cover}article div{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:end;padding:25px;background:linear-gradient(transparent 30%,#080e1aee)}h2{font-size:28px;letter-spacing:-1px;margin:0 0 7px}p{font-size:14px;color:#d0daea;margin:0}
      </style></head><body><header><b>PULSE<span style="color:#f2a7cc">.</span></b><span>Her sabah 07.30</span></header><h1>Günlük <span>gündemimiz.</span></h1><main><article><img src="${covers[0]}" alt=""><div><h2>PULSE Teknoloji</h2><p>Yeni Sekme · Yaşar &amp; Necdet</p></div></article><article><img src="${covers[1]}" alt=""><div><h2>PULSE Oyun</h2><p>Moradon FM · Yaşar &amp; Necdet</p></div></article></main></body></html>`);
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
