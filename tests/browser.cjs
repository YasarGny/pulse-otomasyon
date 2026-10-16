const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const { spawn } = require("node:child_process");
const fs = require("node:fs/promises");
const assert = require("node:assert/strict");
const path = require("node:path");
const base = "http://127.0.0.1:8765";
let passed = 0;
const server = spawn(
  process.env.PULSE_PYTHON || "python3",
  ["tests/serve_fixture.py"],
  {
    stdio: ["ignore", "pipe", "inherit"],
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  },
);
const ready = new Promise((resolve, reject) => {
  server.stdout.on("data", (d) => {
    if (d.toString().includes("Fixture server ready")) resolve();
  });
  server.on("exit", (c) => reject(Error("Fixture server exited " + c)));
  setTimeout(() => reject(Error("Fixture startup timeout")), 30000).unref();
});
async function run(name, fn) {
  await fn();
  passed++;
  console.log("PASS", name);
}
(async () => {
  await ready;
  const executablePath =
    process.env.PULSE_CHROMIUM ||
    ((await fs.access("/usr/bin/chromium").then(
      () => true,
      () => false,
    ))
      ? "/usr/bin/chromium"
      : undefined);
  const browser = await chromium.launch({
    headless: true,
    executablePath,
    args: ["--no-sandbox"],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      locale: "tr-TR",
      reducedMotion: "reduce",
    });
    const image = await fs.readFile("site/assets/covers/teknoloji.svg");
    await context.route("https://images.example.test/**", (route) =>
      route.fulfill({ status: 200, contentType: "image/svg+xml", body: image }),
    );
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const open = async (route) => {
      await page.goto(base + route);
      await page.waitForFunction(() => !!window.PULSE_RELEASE);
    };
    const noOverflow = async () =>
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        "Horizontal overflow",
      );
    await run("desktop home: two editions, no news or players", async () => {
      await open("/");
      assert.equal(await page.locator(".edition-card").count(), 2);
      assert.equal(await page.locator("audio,article.story").count(), 0);
      assert.match(await page.locator("h1").innerText(), /Günlük gündemimiz/);
      await noOverflow();
      await page.screenshot({
        path: "test-results/home-desktop.png",
        fullPage: true,
      });
      const results = await new AxeBuilder({ page }).analyze();
      assert.deepEqual(
        results.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
        [],
      );
    });
    await run("keyboard skip link reaches main content", async () => {
      await page.goto(base);
      await page.waitForFunction(() => window.PULSE_RELEASE);
      await page.keyboard.press("Tab");
      assert.equal(await page.locator(":focus").innerText(), "İçeriğe geç");
      await page.keyboard.press("Enter");
      assert.equal(new URL(page.url()).hash, "#main");
    });
    await run("mobile home layout", async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      await open("/");
      await noOverflow();
      await page.screenshot({
        path: "test-results/home-mobile.png",
        fullPage: true,
      });
    });
    for (const width of [1440, 820, 390, 320]) {
      await run(`technology layout at ${width}px`, async () => {
        await page.setViewportSize({ width, height: 900 });
        await open("/teknoloji/");
        await noOverflow();
        assert.equal(await page.locator(".story").count(), 3);
        assert.equal(await page.locator("audio").count(), 2);
        assert.match(
          await page.locator("#issue").innerText(),
          /16 Ekim 2026 · Sayı 001/,
        );
        assert.equal(
          await page.locator("#podcast-title").innerText(),
          "Yeni Sekme",
        );
        assert.equal(await page.locator(".story-image").count(), 1);
        await page.screenshot({
          path: `test-results/teknoloji-${width}.png`,
          fullPage: true,
        });
        const results = await new AxeBuilder({ page }).analyze();
        assert.deepEqual(
          results.violations.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => n.target),
          })),
          [],
        );
      });
    }
    await run("game edition and distinct podcast on mobile", async () => {
      await open("/oyun/");
      assert.equal(
        await page.locator("#podcast-title").innerText(),
        "Moradon FM",
      );
      assert.equal(await page.locator(".story").count(), 3);
      assert.match(
        await page.locator(".story").first().innerText(),
        /oynana|oynanış/,
      );
      await noOverflow();
      await page.screenshot({
        path: "test-results/oyun-mobile.png",
        fullPage: true,
      });
      const results = await new AxeBuilder({ page }).analyze();
      assert.deepEqual(
        results.violations.map((v) => v.id),
        [],
      );
    });
    await run("real MP3 playback and metadata", async () => {
      await page.locator("#summary audio").evaluate(async (a) => {
        await a.play();
      });
      await page.waitForFunction(
        () => document.querySelector("#summary audio").currentTime > 0.1,
      );
      assert(
        (await page.locator("#summary audio").evaluate((a) => a.duration)) >=
          40,
      );
      await page.locator("#summary audio").evaluate((a) => a.pause());
    });
    await run("audio error has a usable retry action", async () => {
      await page
        .locator("#summary audio")
        .evaluate((a) => a.dispatchEvent(new Event("error")));
      assert(await page.locator("#summary .audio-error").isVisible());
      await page.locator("#summary button").click();
      assert(await page.locator("#summary .audio-error").isHidden());
    });
    await run(
      "failed news image degrades to text without hiding the story",
      async () => {
        await page.route("https://images.example.test/**", (route) =>
          route.abort(),
        );
        await open("/teknoloji/");
        await page.waitForFunction(
          () => document.querySelectorAll(".story-image").length === 0,
        );
        assert.equal(await page.locator(".story").count(), 3);
        await page.unroute("https://images.example.test/**");
      },
    );
    await page.clock.install();
    let serverTime = "Fri, 16 Oct 2026 04:29:59 GMT";
    await page.route("**/data/publication.json*", async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        headers: {
          ...response.headers(),
          date: serverTime,
          "cache-control": "no-store",
        },
      });
    });
    await run(
      "07:29 remains in the print room even if the files are ready",
      async () => {
        await page.goto(base);
        await page.locator("#pulse-printing").waitFor();
        assert(await page.locator(".site-shell").isHidden());
        await page.screenshot({
          path: "test-results/printing-mobile.png",
          fullPage: true,
        });
        const results = await new AxeBuilder({ page }).analyze();
        assert.deepEqual(
          results.violations.map((v) => v.id),
          [],
        );
      },
    );
    await run(
      "07:30 opens verified publications automatically on polling",
      async () => {
        serverTime = "Fri, 16 Oct 2026 04:30:00 GMT";
        await page.clock.runFor(61000);
        await new Promise((r) => setTimeout(r, 100));
        await page.waitForFunction(() => window.PULSE_RELEASE);
        assert(await page.locator("#pulse-printing").isHidden());
      },
    );
    await run(
      "next morning 06:00 closes an already-open tab automatically",
      async () => {
        serverTime = "Sat, 17 Oct 2026 03:00:00 GMT";
        await page.clock.runFor(61000);
        await page.waitForFunction(() => !window.PULSE_RELEASE);
        assert(await page.locator("#pulse-printing").isVisible());
        assert(await page.locator(".site-shell").isHidden());
      },
    );
    await page.clock.resume();
    await page.unroute("**/data/publication.json*");
    await run(
      "client clock cannot open yesterday or bypass the server clock",
      async () => {
        await page.addInitScript(() => {
          Date.now = () => new Date("2099-01-01T12:00:00Z").getTime();
        });
        await open("/");
        assert(await page.locator(".site-shell").isVisible());
      },
    );
    await run(
      "missing audio prevents the entire publication from opening",
      async () => {
        await page.route("**/oyun/podcast.mp3", (route) =>
          route.fulfill({ status: 404, body: "missing" }),
        );
        await page.goto(base);
        await page
          .locator("#printing-status")
          .filter({ hasText: "doğrulanamadı" })
          .waitFor();
        assert(await page.locator(".site-shell").isHidden());
        await page.unroute("**/oyun/podcast.mp3");
      },
    );
    await run(
      "corrupt JSON fails hash verification and stays closed",
      async () => {
        await page.route("**/releases/*/oyun.json", (route) =>
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: "{bad json",
          }),
        );
        await page.goto(base + "/oyun/");
        await page
          .locator("#printing-status")
          .filter({ hasText: "doğrulanamadı" })
          .waitFor();
        assert(await page.locator(".site-shell").isHidden());
        await page.unroute("**/releases/*/oyun.json");
      },
    );
    await run("missing manifest stays closed", async () => {
      await page.route("**/data/publication.json*", (route) =>
        route.fulfill({ status: 404, body: "missing" }),
      );
      await page.goto(base);
      await page
        .locator("#printing-status")
        .filter({ hasText: "doğrulanamadı" })
        .waitFor();
      assert(await page.locator(".site-shell").isHidden());
      await page.unroute("**/data/publication.json*");
    });
    await run("no browser runtime errors", async () =>
      assert.deepEqual(errors, []),
    );
    await context.close();
    console.log(`${passed} browser checks passed`);
  } finally {
    await browser.close();
  }
})()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => server.kill());
