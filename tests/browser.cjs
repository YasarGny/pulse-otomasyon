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
    const image = await fs.readFile("site/assets/covers/teknoloji-768.webp");
    await context.route("https://images.example.test/**", (route) =>
      route.fulfill({ status: 200, contentType: "image/webp", body: image }),
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
    await run(
      "privacy and terms remain public without publication data",
      async () => {
        await page.route("**/data/publication.json*", (route) => route.abort());
        for (const slug of ["gizlilik", "kosullar"]) {
          await page.goto(base + "/" + slug + "/");
          assert.equal(await page.locator("h1").count(), 1);
          assert.equal(
            await page.locator("#pulse-printing, #publication-loading").count(),
            0,
          );
          await noOverflow();
          const results = await new AxeBuilder({ page }).analyze();
          assert.deepEqual(
            results.violations.map((v) => v.id),
            [],
          );
        }
        await page.unroute("**/data/publication.json*");
      },
    );
    await run("twenty news items stay compact, filter and reveal on mobile", async () => {
      await page.setViewportSize({width: 390, height: 844});
      await open("/expanded/teknoloji/");
      assert.equal(await page.locator(".story").count(), 20);
      assert.equal(await page.locator(".story:visible").count(), 8);
      await page.locator(".news-more").click();
      assert.equal(await page.locator(".story:visible").count(), 16);
      await page.locator(".news-more").click();
      assert.equal(await page.locator(".story:visible").count(), 20);
      assert(await page.locator(".news-more").isHidden());
      await page.locator(".news-filter").selectOption("BİLİM");
      assert.equal(await page.locator(".story:visible").count(), 8);
      await page.locator(".news-more").click();
      assert.equal(await page.locator(".story:visible").count(), 10);
      for (const story of await page.locator(".story:visible").all()) assert.equal(await story.getAttribute("data-category"), "BİLİM");
      await noOverflow();
      const results = await new AxeBuilder({page}).analyze();
      assert.deepEqual(results.violations.map(v => v.id), []);
      await page.screenshot({path: "test-results/expanded-news-mobile.png", fullPage: true});
      await page.setViewportSize({width:1440,height:1000});
    });
    await run("keyboard skip link reaches main content", async () => {
      await page.goto(base);
      await page.waitForFunction(() => window.PULSE_RELEASE);
      await page.keyboard.press("Tab");
      assert.equal(await page.locator(":focus").innerText(), "İçeriğe geç");
      await page.keyboard.press("Enter");
      await page.waitForURL("**/#main");
      assert.equal(new URL(page.url()).hash, "#main");
    });
    await run(
      "ready navigation never flashes the print room, even on a slow manifest",
      async () => {
        await page.addInitScript(() => {
          window.__printMounts = 0;
          new MutationObserver((records) => {
            for (const r of records)
              for (const n of r.addedNodes)
                if (
                  n.nodeType === 1 &&
                  (n.id === "pulse-printing" ||
                    n.querySelector?.("#pulse-printing"))
                )
                  window.__printMounts++;
          }).observe(document, { childList: true, subtree: true });
        });
        await page.route("**/data/publication.json*", async (route) => {
          await new Promise((resolve) => setTimeout(resolve, 400));
          await route.continue();
        });
        await open("/");
        assert.equal(await page.evaluate(() => window.__printMounts), 0);
        assert.equal(await page.locator("#publication-loading").count(), 0);
        await page.unroute("**/data/publication.json*");
      },
    );
    await run("mobile home layout", async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      await open("/");
      await noOverflow();
      for (const cover of await page.locator(".cover img").all()) {
        const box = await cover.boundingBox();
        assert(
          box.height < box.width,
          "Editorial covers must stay landscape on mobile",
        );
      }
      assert.equal(await page.locator('a[href*="github.com"]').count(), 0);
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
          /16\.10\.2026 · Sayı 001/,
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
    await run(
      "article details keep sources, full image and numeric date",
      async () => {
        await open("/teknoloji/");
        await page.locator(".story-detail-link").first().click();
        await page.waitForFunction(() => !!window.PULSE_RELEASE);
        assert.match(
          await page.locator(".detail-meta").innerText(),
          /16\.10\.2026/,
        );
        assert.equal(await page.locator(".source-link").count(), 1);
        assert.equal(await page.locator(".why").count(), 1);
        assert.equal(await page.locator("audio").count(), 0);
        assert.equal(await page.locator("h1").count(), 1);
        await noOverflow();
        const results = await new AxeBuilder({ page }).analyze();
        assert.deepEqual(
          results.violations.map((v) => v.id),
          [],
        );
        await page.screenshot({
          path: "test-results/detail-mobile.png",
          fullPage: true,
        });
      },
    );
    await run("compact listening tabs support keyboard switching", async () => {
      await open("/teknoloji/");
      assert(await page.locator("#summary-panel").isVisible());
      assert(await page.locator("#podcast-panel").isHidden());
      await page.locator("#summary-tab").focus();
      await page.keyboard.press("ArrowRight");
      assert(await page.locator("#podcast-panel").isVisible());
      assert(await page.locator("#summary-panel").isHidden());
      await page.keyboard.press("Home");
      assert(await page.locator("#summary-panel").isVisible());
      assert((await page.locator(".listening").boundingBox()).height < 310);
    });
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
      await page.locator("#summary .player-play").click();
      await page.waitForFunction(
        () => document.querySelector("#summary audio").currentTime > 0.1,
      );
      assert(
        (await page.locator("#summary audio").evaluate((a) => a.duration)) >=
          40,
      );
      await page.locator("#summary audio").evaluate((a) => a.pause());
    });
    await run(
      "custom controls change speed, seek, volume and mute",
      async () => {
        for (const value of [1.1, 1.2, 1.25, 1.5, 2, 1]) {
          await page.locator("#summary .player-speed").click();
          assert.equal(
            await page
              .locator("#summary audio")
              .evaluate((a) => a.playbackRate),
            value,
          );
        }
        for (let i = 0; i < 4; i++)
          await page.locator("#summary .player-speed").click();
        assert.equal(
          await page.locator("#summary audio").evaluate((a) => a.playbackRate),
          1.5,
        );
        await page.locator("#summary .player-seek").evaluate((input) => {
          input.value = "10";
          input.dispatchEvent(new Event("input"));
        });
        assert(
          Math.abs(
            (await page
              .locator("#summary audio")
              .evaluate((a) => a.currentTime)) - 10,
          ) < 1,
        );
        await page.locator("#summary .player-skip").last().click();
        assert(
          Math.abs(
            (await page
              .locator("#summary audio")
              .evaluate((a) => a.currentTime)) - 20,
          ) < 1,
        );
        await page.locator("#summary .player-volume").evaluate((input) => {
          input.value = ".3";
          input.dispatchEvent(new Event("input"));
        });
        assert.equal(
          await page.locator("#summary audio").evaluate((a) => a.volume),
          0.3,
        );
        await page.locator("#summary .player-mute").click();
        assert(await page.locator("#summary audio").evaluate((a) => a.muted));
        await page.locator("#summary .player-mute").click();
        assert.equal(
          await page.locator("#summary audio").evaluate((a) => a.muted),
          false,
        );
      },
    );
    await run("starting the podcast pauses the summary", async () => {
      await page.locator("#summary audio").evaluate((a) => a.play());
      await page.locator("#podcast-tab").click();
      await page.locator("#podcast audio").evaluate((a) => a.play());
      assert(await page.locator("#summary audio").evaluate((a) => a.paused));
      assert(
        await page
          .locator(".podcast-box")
          .evaluate((b) => b.classList.contains("is-playing")),
      );
      await page.locator("#podcast audio").evaluate((a) => a.pause());
    });
    await run(
      "mobile and landscape layouts preserve usable audio controls",
      async () => {
        for (const [width, height] of [
          [360, 800],
          [390, 844],
          [430, 932],
          [540, 720],
          [760, 540],
          [844, 390],
        ]) {
          await page.setViewportSize({ width, height });
          for (const route of ["/", "/teknoloji/", "/oyun/"]) {
            await open(route);
            await noOverflow();
            for (const audio of await page.locator(".player:visible").all()) {
              const box = await audio.boundingBox();
              assert(
                box.width >= 230 && box.height >= 44,
                `Audio controls too small at ${width}px`,
              );
            }
          }
        }
        await page.setViewportSize({ width: 390, height: 844 });
        await open("/oyun/");
      },
    );
    await run("audio error has a usable retry action", async () => {
      await page.locator("#summary-tab").click();
      await page
        .locator("#summary audio")
        .evaluate((a) => a.dispatchEvent(new Event("error")));
      assert(await page.locator("#summary .audio-error").isVisible());
      await page.locator("#summary .retry").click();
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
    await run(
      "extracted archive works with networking offline, including audio and details",
      async () => {
        const offline = await browser.newContext({
          offline: true,
          viewport: { width: 390, height: 844 },
          reducedMotion: "reduce",
        });
        const local = await offline.newPage();
        const localErrors = [];
        local.on("pageerror", (e) => localErrors.push(e.message));
        const { pathToFileURL } = require("node:url");
        try {
          await local.goto(
            pathToFileURL(path.resolve("test-results/offline/index.html")).href,
          );
        } catch (error) {
          if (!error.message.includes("ERR_BLOCKED_BY_ADMINISTRATOR"))
            throw error;
          console.log(
            "NOTE local Chromium policy blocks file URLs; checking extracted archive through an in-memory origin with networking offline.",
          );
          await offline.route(
            "https://pulse-offline.test/**",
            async (route) => {
              const relative = decodeURIComponent(
                new URL(route.request().url()).pathname,
              ).replace(/^\//, "");
              const file = path.resolve("test-results/offline", relative);
              assert(
                file.startsWith(
                  path.resolve("test-results/offline") + path.sep,
                ),
              );
              const types = {
                ".html": "text/html",
                ".js": "application/javascript",
                ".css": "text/css",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
                ".mp3": "audio/mpeg",
              };
              await route.fulfill({
                status: 200,
                contentType:
                  types[path.extname(file)] || "application/octet-stream",
                body: await fs.readFile(file),
              });
            },
          );
          await local.goto("https://pulse-offline.test/index.html");
        }
        assert.equal(await local.locator(".edition-card").count(), 2);
        await local.locator(".edition-card").first().click();
        await local.waitForSelector(".story-detail-link");
        assert.equal(await local.locator(".story").count(), 3);
        assert(
          await local
            .locator(".story-image")
            .first()
            .evaluate((i) => i.complete && i.naturalWidth > 0),
        );
        await local.locator("#summary .player-play").click();
        await local.waitForFunction(
          () => document.querySelector("#summary audio").currentTime > 0.1,
        );
        await local.locator(".story-detail-link").first().click();
        assert.equal(await local.locator("h1").count(), 1);
        assert(
          await local
            .locator(".story-image")
            .evaluate((i) => i.complete && i.naturalWidth > 0),
        );
        assert.equal(await local.locator(".source-link").count(), 1);
        assert.equal(await local.locator("#pulse-printing").count(), 0);
        assert.deepEqual(localErrors, []);
        await local.screenshot({
          path: "test-results/offline-detail-mobile.png",
          fullPage: true,
        });
        await offline.close();
      },
    );
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
