/* Real browser integration checks: public gate, static routes, one audio session, offline ZIP. */
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const { spawn } = require("node:child_process");
const fs = require("node:fs/promises"),
  path = require("node:path"),
  assert = require("node:assert/strict");
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
  server.on("exit", (c) => reject(Error("Fixture exited " + c)));
  setTimeout(() => reject(Error("Fixture timeout")), 120000).unref();
});
async function run(name, fn) {
  try {
    await fn();
  } catch (error) {
    const detail = `${name}: ${error.stack || error}`;
    await fs.mkdir("test-results", { recursive: true });
    await fs.writeFile("test-results/browser-failure.txt", detail);
    if (process.env.GITHUB_ACTIONS)
      console.error(
        "::error::" +
          detail
            .replace(/%/g, "%25")
            .replace(/\r/g, "%0D")
            .replace(/\n/g, "%0A"),
      );
    throw error;
  }
  passed++;
  console.log("PASS", name);
}
(async () => {
  await ready;
  const browser = await chromium.launch({
    headless: true,
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
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      locale: "tr-TR",
      reducedMotion: "reduce",
      serviceWorkers: "block", // Mocked gate responses; real worker is checked separately.
    });
    const tech = await fs.readFile("site/assets/covers/teknoloji-768.webp"),
      game = await fs.readFile("site/assets/covers/oyun-768.webp");
    await context.route("https://images.example.test/**", (r) =>
      r.fulfill({
        status: 200,
        contentType: "image/webp",
        body: r.request().url().includes("oyun") ? game : tech,
      }),
    );
    const page = await context.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const open = async (route) => {
      await page.goto(base + route);
      await page.waitForFunction(
        () =>
          window.PULSE_RELEASE &&
          document.querySelector("#main").dataset.release ===
            window.PULSE_RELEASE.manifest.release_id,
      );
    };
    const selectTopic = async (value) => {
      await page.locator('.topics-toggle').click();
      await page.locator('.topic-options input').evaluateAll((nodes,value) => {
        for(const node of nodes) node.checked = node.value === value;
      },value);
      await page.locator('.topics-apply').click();
      await page.waitForFunction(value=>[...document.querySelectorAll('.filter-chip')].some(n=>n.textContent===value+' ×'),value);
    };
    const searchFor = async (value) => {
      if(!await page.locator('.news-search').isVisible()) await page.locator('.search-toggle').click();
      await page.locator('.news-search').fill(value);
    };
    const noOverflow = async () => {
      const result = await page.evaluate(() => ({
        width: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        route: location.pathname,
        overflowing: [...document.querySelectorAll("body *")]
          .filter((node) => {
            const rect = node.getBoundingClientRect();
            return (
              rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1)
            );
          })
          .slice(0, 12)
          .map((node) => ({
            tag: node.tagName,
            class: node.className,
            text: node.textContent.slice(0, 80),
            width: node.getBoundingClientRect().width,
          })),
      }));
      assert(
        result.scrollWidth <= result.width,
        "Horizontal overflow: " + JSON.stringify(result),
      );
    };
    const axe = async () => {
      const r = await new AxeBuilder({ page }).analyze();
      assert.deepEqual(
        r.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
        [],
      );
    };
    await run(
      "editorial home: three illustrated stories and equal unplayed podcasts",
      async () => {
        await open("/");
        assert.equal(await page.locator(".selection-grid .story").count(), 3);
        assert.equal(
          await page.locator(".selection-grid .story-image").count(),
          3,
        );
        assert.equal(
          await page.locator(".podcast-cards .audio-box").count(),
          2,
        );
        assert.equal(
          await page.locator(".summary-cards .audio-box").count(),
          2,
        );
        assert.equal(
          await page.locator("html").getAttribute("data-theme"),
          "dark",
        );
        assert(await page.locator(".persistent-audio").isHidden());
        assert.equal(
          await page.locator("audio").evaluate((a) => a.getAttribute("src")),
          null,
        );
        assert.match(
          await page.locator(".nav-issue").innerText(),
          /^16\.10\.2026$/,
        );
        assert.deepEqual(
          await page
            .locator(".podcast-box .program-art")
            .evaluateAll((images) =>
              images.map((img) => ({
                loaded: img.complete && img.naturalWidth > 0,
                square: img.naturalWidth === img.naturalHeight,
              })),
            ),
          [
            { loaded: true, square: true },
            { loaded: true, square: true },
          ],
        );
        await noOverflow();
        await axe();
        await page.screenshot({
          path: "test-results/editor-home-dark-desktop.png",
          fullPage: true,
        });
      },
    );
    await run(
      "theme preference changes before reload and survives enhanced navigation",
      async () => {
        await page.locator(".theme-toggle").click();
        assert.equal(
          await page.locator("html").getAttribute("data-theme"),
          "light",
        );
        await page.locator('.nav nav a[href*="teknoloji"]').click();
        await page.waitForURL("**/teknoloji/index.html");
        assert.equal(
          await page.locator("html").getAttribute("data-theme"),
          "light",
        );
        await page.reload();
        await page.waitForFunction(() => window.PULSE_RELEASE);
        assert.equal(
          await page.locator("html").getAttribute("data-theme"),
          "light",
        );
        await axe();
        await open("/");
        await page.screenshot({
          path: "test-results/editor-home-light-desktop.png",
          fullPage: true,
        });
        await page.locator(".theme-toggle").click();
      },
    );
    await run(
      "storage denial still defaults to dark and permits changing theme",
      async () => {
        const c = await browser.newContext();
        await c.addInitScript(() => {
          Object.defineProperty(window, "localStorage", {
            get() {
              throw new DOMException("blocked", "SecurityError");
            },
          });
        });
        const p = await c.newPage();
        await p.goto(base);
        await p.waitForFunction(() => window.PULSE_RELEASE);
        assert.equal(
          await p.locator("html").getAttribute("data-theme"),
          "dark",
        );
        await p.locator(".theme-toggle").click();
        assert.equal(
          await p.locator("html").getAttribute("data-theme"),
          "light",
        );
        await p.locator(".podcast-box .audio-start").first().click();
        await p.waitForFunction(()=>document.querySelector("audio").currentTime>.1);
        await p.locator("audio").evaluate(a=>{a.currentTime=17;a.pause();});
        await p.locator(".mini-more").click();
        assert(await p.locator(".player-restart").isVisible());
        await c.close();
      },
    );
    await run(
      "static complete articles remain readable with JavaScript disabled",
      async () => {
        const c = await browser.newContext({ javaScriptEnabled: false });
        const p = await c.newPage();
        await p.goto(base + "/expanded/teknoloji/haber/teknoloji0/index.html");
        assert.equal(await p.locator(".article-text p").count(), 2);
        assert(await p.locator("h1").isVisible());
        assert.equal(await p.locator(".source-link").count(), 1);
        assert.equal(
          await p
            .locator(".article-text")
            .innerText()
            .then((t) => t.includes("İkinci paragraf")),
          true,
        );
        await c.close();
      },
    );
    for (const [width, height] of [
      [1440, 1000],
      [1024, 768],
      [768, 1024],
      [640, 900],
      [430, 932],
      [390, 844],
      [320, 780],
    ])
      await run(
        `responsive routes and focusable audio at ${width}px`,
        async () => {
          await page.setViewportSize({ width, height });
          for (const route of [
            "/",
            "/haberler/",
            "/teknoloji/",
            "/oyun/",
            "/podcastler/",
            "/teknoloji/dinle/",
            "/teknoloji/haber/teknoloji0/",
          ]) {
            await open(route);
            await noOverflow();
            assert.equal(await page.locator("h1").count(), 1);
            for (const b of await page.locator(".audio-start:visible").all()) {
              const box = await b.boundingBox();
              assert(box.width >= 44 && box.height >= 44, "audio touch target");
            }
            for (const img of await page.locator(".story-image").all())
              assert.equal(
                await img.evaluate((i) => getComputedStyle(i).objectFit),
                "contain",
              );
          }
          await open("/");
          await page.screenshot({
            path: `test-results/editor-home-${width}.png`,
            fullPage: true,
          });
          await axe();
        },
      );
    await run(
      "200% text enlargement keeps reading and controls within screen",
      async () => {
        for (const width of [390, 320]) {
          await page.setViewportSize({ width, height: 844 });
          for (const route of [
            "/",
            "/haberler/",
            "/teknoloji/dinle/",
            "/teknoloji/haber/teknoloji0/",
          ]) {
            await open(route);
            await page.evaluate(() => {
              const sizes = [...document.querySelectorAll("body, body *")]
                .filter((node) => node instanceof HTMLElement)
                .map((node) => [
                  node,
                  parseFloat(getComputedStyle(node).fontSize),
                ]);
              for (const [node, size] of sizes)
                node.style.fontSize = size * 2 + "px";
            });
            await noOverflow();
          }
        }
      },
    );
    await run("keyboard skip link reaches main", async () => {
      await open("/");
      await page.keyboard.press("Tab");
      assert.equal(await page.locator(":focus").innerText(), "İçeriğe geç");
      await page.keyboard.press("Enter");
      assert.equal(new URL(page.url()).hash, "#main");
    });
    await run(
      "large daily list filters and reveals without duplicating articles",
      async () => {
        await open("/expanded/haberler/");
        assert.equal(await page.locator("#stories .story").count(), 40);
        assert.equal(await page.locator("#stories .story:visible").count(), 8);
        await page.locator(".news-more").click();
        assert.equal(await page.locator("#stories .story:visible").count(), 16);
        await page.locator('[data-filter="oyun"]').click();
        assert.equal(await page.locator("#stories .story:visible").count(), 8);
        for (const a of await page.locator("#stories .story:visible").all())
          assert.equal(await a.getAttribute("data-section"), "oyun");
        await selectTopic("BİLİM");
        await page.locator(".news-more").click();
        assert.equal(await page.locator("#stories .story:visible").count(), 10);
        await noOverflow();
        await axe();
      },
    );
    await run(
      "image and story text open full article; source remains independent",
      async () => {
        for (const selector of [".story-image", ".story-detail-link"]) {
          await open("/expanded/teknoloji/");
          const source = page
            .locator("#stories .story:visible .source-link")
            .first();
          await source.evaluate((a) =>
            a.addEventListener("click", (e) => {
              e.preventDefault();
              window.__source = true;
            }),
          );
          await source.click();
          assert(await page.evaluate(() => window.__source));
          const target = page
            .locator("#stories .story:visible")
            .first()
            .locator(selector);
          await target.scrollIntoViewIfNeeded();
          const box = await target.boundingBox();
          await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForURL("**/haber/**");
          assert.equal(await page.locator(".article-text p").count(), 2);
          assert.equal(await page.locator(".source-link").count(), 1);
          assert.equal(
            await page
              .locator('meta[property="og:type"]')
              .getAttribute("content"),
            "article",
          );
          const schema = JSON.parse(
            await page
              .locator('script[type="application/ld+json"]')
              .textContent(),
          );
          assert.equal(schema.headline, await page.locator("h1").innerText());
        }
      },
    );
    await run(
      "back navigation restores list filter and revealed count",
      async () => {
        await open("/expanded/haberler/");
        await page.locator('[data-filter="oyun"]').click();
        await page.locator(".news-more").click();
        const link = page.locator("#stories .story:visible .story-detail-link").last();
        await link.scrollIntoViewIfNeeded();
        const position = await page.evaluate(() => scrollY);
        await link.click();
        await page.waitForURL("**/haber/**");
        await page.goBack();
        await page.waitForSelector("#stories");
        assert.equal(
          await page
            .locator('[data-filter="oyun"]')
            .getAttribute("aria-pressed"),
          "true",
        );
        assert.equal(await page.locator("#stories .story:visible").count(), 16);
        assert(Math.abs(await page.evaluate(() => scrollY) - position) <= 2);
      },
    );
    await run(
      "article return link restores its exact origin, filters, pagination and reading position",
      async () => {
        await page.setViewportSize({ width: 390, height: 844 });
        for (const route of ["/expanded/teknoloji/", "/expanded/oyun/", "/expanded/haberler/#main"]) {
          await open(route);
          if (route.includes("haberler"))
            await page.locator('[data-filter="oyun"]').click();
          await selectTopic("BİLİM");
          await page.locator(".news-more").click();
          const link = page.locator("#stories .story:visible .story-detail-link").last();
          await link.scrollIntoViewIfNeeded();
          const origin = page.url();
          const position = await page.evaluate(() => scrollY);
          const story = await link.innerText();
          await link.click();
          await page.waitForSelector(".article-reader");
          // Return context also survives reloading a shared article tab.
          await page.reload();
          await page.waitForFunction(() => !!window.PULSE_RELEASE);
          const historyLength = await page.evaluate(() => history.length);
          assert.equal(await page.locator(".article-reader .back").getAttribute("href"), origin);
          await page.locator(".article-reader .back").click();
          await page.waitForSelector("#stories");
          assert.equal(page.url(), origin);
          assert.equal(await page.locator(".filter-chip").innerText(), "BİLİM ×");
          assert.equal(await page.locator("#stories .story:visible").count(), 10);
          assert.equal(await page.locator(":focus").innerText(), story);
          assert(Math.abs(await page.evaluate(() => scrollY) - position) <= 2);
          assert.equal(await page.evaluate(() => history.length), historyLength);
          await page.goForward();
          await page.waitForSelector(".article-reader");
          assert.equal(await page.locator("h1").innerText(), story);
          await page.goBack();
          await page.waitForSelector("#stories");
        }
      },
    );
    await run(
      "selection return stays on selection and direct article links fall back to their category",
      async () => {
        await open("/expanded/");
        const link = page.locator(".home-news .story-detail-link").last();
        await link.scrollIntoViewIfNeeded();
        const position = await page.evaluate(() => scrollY);
        const direct = await link.getAttribute("href");
        await link.click();
        await page.waitForSelector(".article-reader");
        await page.locator(".back").click();
        await page.waitForSelector(".daily-selection");
        assert.equal(new URL(page.url()).pathname, "/expanded/");
        assert(Math.abs(await page.evaluate(() => scrollY) - position) <= 2);
        await open(new URL(direct, base + "/expanded/").pathname);
        await page.locator(".back").click();
        await page.waitForSelector("#stories");
        assert(["teknoloji", "oyun"].includes(await page.locator("body").getAttribute("data-section")));
      },
    );
    await run(
      "category lists have no misleading combined-list shortcut and reset keeps their section",
      async () => {
        for (const section of ["teknoloji", "oyun"]) {
          await open("/expanded/" + section + "/");
          assert.equal(await page.locator(".all-news-link").count(), 0);
          await searchFor("no-matching-story-xyz");
          await page.locator(".reset-filter").click();
          assert(await page.locator(".topics-toggle").evaluate((button) => button === document.activeElement));
          await page.locator(".news-more").click();
          for (const story of await page.locator("#stories .story:visible").all())
            assert.equal(await story.getAttribute("data-section"), section);
          await noOverflow();
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
      },
    );
    await run(
      "search is Turkish-aware, scoped, resettable and retained on article return",
      async () => {
        await open("/expanded/teknoloji/");
        await searchFor("yazilim");
        assert.equal(await page.locator("#stories .story:visible").count(), 8);
        await searchFor("YAZILIM");
        assert.equal(await page.locator("#stories .story:visible").count(), 8);
        await page.locator(".news-more").click();
        assert.equal(await page.locator("#stories .story:visible").count(), 10);
        const link = page.locator("#stories .story:visible .story-detail-link").last();
        await link.click();
        await page.waitForSelector(".article-reader");
        await page.locator(".back").click();
        await page.waitForSelector("#stories");
        assert.equal(await page.locator(".news-search").inputValue(), "YAZILIM");
        assert.equal(await page.locator("#stories .story:visible").count(), 10);
        await selectTopic("BİLİM");
        assert.equal(await page.locator("#stories .story:visible").count(), 0);
        await page.locator(".reset-filter").click();
        assert.equal(await page.locator(".news-search").inputValue(), "");
        await searchFor("bilim");
        assert.equal(await page.locator("#stories .story:visible").count(), 8);
        for (const story of await page.locator("#stories .story:visible").all())
          assert.equal(await story.getAttribute("data-section"), "teknoloji");
        await searchFor("<script>no-results</script>");
        assert(await page.locator(".empty-filter").isVisible());
        assert.equal(await page.locator("#stories .story:visible").count(), 0);
        await page.setViewportSize({width:320,height:740});
        await noOverflow();
        await axe();
        await page.setViewportSize({width:1440,height:1000});
      },
    );
    await run(
      "saved listening resumes only on explicit play, restores speed and supports restarting",
      async () => {
        await open("/");
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(() => document.querySelector("audio").currentTime > .1);
        await page.locator("audio").evaluate((a) => {a.pause();a.currentTime=17;a.playbackRate=1.25;});
        await page.waitForFunction(() => Object.values(JSON.parse(localStorage.getItem("pulse-listening-v1") || "{}")).some(r=>r.position>=17));
        await page.reload();
        await page.waitForSelector(".resume-note");
        assert(await page.locator(".resume-note").first().innerText().then(t=>t.includes("0:17")));
        assert.equal(await page.locator("audio").getAttribute("src"), null);
        assert(await page.locator("audio").evaluate(a=>a.paused));
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(() => document.querySelector("audio").currentTime>=17);
        assert.equal(await page.locator("audio").evaluate(a=>a.playbackRate),1.25);
        await page.locator(".mini-more").click();
        await page.locator(".player-restart").click();
        assert(await page.locator("audio").evaluate(a=>a.currentTime<2));
        await page.locator(".mini-close").click();
        await page.reload();
        await page.waitForFunction(()=>!!window.PULSE_RELEASE);
        assert.equal(await page.locator(".resume-note").count(),0);
        await page.evaluate(()=>localStorage.removeItem("pulse-listening-v1"));
      },
    );
    await run(
      "invalid or completed listening records never auto-select audio or leak to another edition",
      async () => {
        await open("/");
        await page.evaluate(()=>{
          const sha = window.PULSE_RELEASE.editions.teknoloji.podcast.sha256;
          localStorage.setItem("pulse-listening-v1",JSON.stringify({["2020-01-01:teknoloji:podcast:"+sha]:{position:17,rate:1}}));
        });
        await page.reload();
        await page.waitForFunction(()=>!!window.PULSE_RELEASE);
        assert.equal(await page.locator(".resume-note").count(),0);
        assert.equal(await page.locator("audio").getAttribute("src"),null);
        await page.evaluate(()=>localStorage.setItem("pulse-listening-v1","{broken"));
        await page.reload();
        await page.waitForFunction(()=>!!window.PULSE_RELEASE);
        assert.equal(await page.locator(".resume-note").count(),0);
        await page.evaluate(()=>{
          const r=window.PULSE_RELEASE,a=r.editions.teknoloji.podcast;
          const key=r.manifest.publish_date+":teknoloji:podcast:"+a.sha256;
          localStorage.setItem("pulse-listening-v1",JSON.stringify({[key]:{position:a.duration-1,rate:1}}));
        });
        await page.reload();
        await page.waitForFunction(()=>!!window.PULSE_RELEASE);
        assert.equal(await page.locator(".resume-note").count(),0);
        await page.evaluate(()=>localStorage.removeItem("pulse-listening-v1"));
      },
    );
    await run(
      "audio cards stay fixed, show a visible pause glyph and use only the floating transport",
      async () => {
        await page.setViewportSize({ width: 390, height: 844 });
        await open("/");
        for (const selector of [
          ".podcast-box .audio-start",
          ".summary-box .audio-start",
        ]) {
          const start = page.locator(selector).first();
          await start.scrollIntoViewIfNeeded();
          const geometry = () =>
            start.evaluate((n) => {
              const b = n.getBoundingClientRect();
              const c = n.closest(".audio-box").getBoundingClientRect();
              return {
                x: b.x + b.width / 2,
                y: b.y + scrollY + b.height / 2,
                height: c.height,
              };
            });
          const before = await geometry();
          await start.click();
          await page.waitForFunction(
            () => document.querySelector("audio").currentTime > 0.1,
          );
          assert.equal(
            await page.locator("#main .player, .inline-player").count(),
            0,
          );
          const after = await geometry();
          for (const key of ["x", "y", "height"])
            assert(Math.abs(before[key] - after[key]) < 0.6, key + " changed");
          const stroke = await start
            .locator("svg path")
            .evaluate((n) => getComputedStyle(n).stroke);
          assert.notEqual(stroke, "none");
          assert.equal(await start.getAttribute("aria-pressed"), "true");
          await start.click();
          assert(await page.locator("audio").evaluate((a) => a.paused));
          assert.equal(await start.getAttribute("aria-pressed"), "false");
          assert(await page.locator(".mini-more").isVisible());
        }
        for (const width of [320, 390, 768, 1440]) {
          await page.setViewportSize({ width, height: 900 });
          await page.locator(".mini-more").click();
          const centres = await page
            .locator(".player-controls")
            .evaluate((n) => {
              const c = n.getBoundingClientRect();
              const p = n.querySelector(".player-play").getBoundingClientRect();
              return { controls: c.x + c.width / 2, play: p.x + p.width / 2 };
            });
          assert(
            Math.abs(centres.controls - centres.play) < 1,
            "transport is not centred at " + width,
          );
          assert.equal(
            await page.locator(".floating-panel .player").count(),
            1,
          );
          await axe();
          await page.screenshot({
            path: "test-results/player-single-" + width + ".png",
          });
          await page.locator(".mini-collapse").click();
        }
      },
    );
    await run(
      "navigation and category soundtracks are explicit and podcast covers are substantial",
      async () => {
        for (const section of ["teknoloji", "oyun"]) {
          await open("/" + section + "/");
          assert.deepEqual(await page.locator(".nav nav a").allTextContents(), [
            "Günün seçkisi",
            "Teknoloji",
            "Oyun",
            "Podcast’ler",
            "Akış",
          ]);
          assert.equal(
            await page
              .locator('.nav nav a[aria-current="page"]')
              .getAttribute("href"),
            base + "/" + section + "/index.html",
          );
          assert.equal(
            await page
              .locator('[data-audio-section="' + section + '"]')
              .count(),
            2,
          );
          assert.equal(
            await page
              .locator(
                '[data-audio-section="' +
                  (section === "teknoloji" ? "oyun" : "teknoloji") +
                  '"]',
              )
              .count(),
            0,
          );
        }
        await open("/podcastler/");
        assert.equal(await page.locator(".program-card").count(), 2);
        for (const width of [390, 1440]) {
          await page.setViewportSize({ width, height: 1000 });
          for (const art of await page
            .locator(".program-card .program-art")
            .all()) {
            const box = await art.boundingBox();
            assert(box.width >= 270 && Math.abs(box.width - box.height) < 1);
          }
          await noOverflow();
          await axe();
          await page.screenshot({
            path: "test-results/podcast-library-" + width + ".png",
            fullPage: true,
          });
        }
      },
    );
    await run(
      "one actual MP3 plays and continues through article navigation",
      async () => {
        await open("/");
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        const before = await page.locator("audio").evaluate((a) => {
          a.dataset.identity = "persistent-proof";
          return a.currentTime;
        });
        await page
          .locator(".selection-grid .story-detail-link")
          .first()
          .click();
        await page.waitForURL("**/haber/**");
        assert.equal(
          await page.locator("audio").evaluate((a) => a.dataset.identity),
          "persistent-proof",
        );
        assert.equal(
          await page.locator("audio").evaluate((a) => a.paused),
          false,
        );
        assert(
          (await page.locator("audio").evaluate((a) => a.currentTime)) >=
            before,
        );
        await page.locator(".persistent-audio").waitFor({ state: "visible" });
        await page.waitForFunction(
          () =>
            document.querySelector(".mini-cover").complete &&
            document.querySelector(".mini-cover").naturalWidth > 0,
        );
        assert.match(
          await page.locator(".mini-cover").getAttribute("src"),
          /yeni-sekme-192.webp/,
        );
        await noOverflow();
        await axe();
        await page.screenshot({
          path: "test-results/editor-article-playing-mobile.png",
          fullPage: true,
        });
        await page.locator(".mini-more").click();
        await page.locator(".mini-details .player-play").click();
        await page.locator(".mini-collapse").click();
      },
    );
    await run(
      "mini-player exposes live seek, speed, volume and keyboard-safe full controls",
      async () => {
        const original = await page.locator("audio").evaluate((a) => {
          window.__dockAudio = a;
          return a.currentTime;
        });
        await page.locator(".mini-more").click();
        assert.equal(
          await page.locator(".mini-more").getAttribute("aria-expanded"),
          "true",
        );
        await page.locator(".mini-details .player-speed").click();
        assert.equal(
          await page.locator("audio").evaluate((a) => a.playbackRate),
          1.1,
        );
        await page.locator(".mini-details .player-volume").evaluate((i) => {
          i.value = "0.4";
          i.dispatchEvent(new Event("input"));
        });
        assert.equal(
          await page.locator("audio").evaluate((a) => a.volume),
          0.4,
        );
        await page.locator(".mini-details .player-seek").evaluate((i) => {
          i.value = "10";
          i.dispatchEvent(new Event("input"));
        });
        assert(
          Math.abs(
            (await page.locator("audio").evaluate((a) => a.currentTime)) - 10,
          ) < 1,
        );
        assert(
          await page.locator("audio").evaluate((a) => a === window.__dockAudio),
        );
        assert(await page.locator(".floating-panel").isVisible());
        await noOverflow();
        await axe();
        await page.screenshot({
          path: "test-results/editor-expanded-player-mobile.png",
          fullPage: true,
        });
        await page.locator(".mini-details .player-speed").press("Escape");
        assert(await page.locator(".mini-details").isHidden());
        assert(
          await page
            .locator(".mini-more")
            .evaluate((n) => n === document.activeElement),
        );
        await page.locator("audio").evaluate((a) => {
          a.playbackRate = 1;
          a.volume = 1;
        });
      },
    );
    await run(
      "floating launcher preserves page geometry, closes outside and restores focus without stopping audio",
      async () => {
        await page.locator("audio").evaluate((a) => a.play());
        for (const width of [320, 390, 768, 1440]) {
          await page.setViewportSize({ width, height: 568 });
          const shell = await page.locator(".site-shell").boundingBox();
          const orb = await page.locator(".mini-more").boundingBox();
          assert.equal(Math.round(orb.width), Math.round(orb.height));
          assert(orb.width >= 44 && orb.width <= 64);
          await page.locator(".mini-more").click();
          const after = await page.locator(".site-shell").boundingBox();
          assert.equal(after.width, shell.width);
          assert.equal(after.height, shell.height);
          assert.equal(
            await page
              .locator("body")
              .evaluate((n) => getComputedStyle(n).overflow),
            "visible",
          );
          const popup = await page.locator(".floating-panel").boundingBox();
          assert(
            popup.x >= 0 && popup.y >= 0 && popup.x + popup.width <= width,
          );
          await page.locator(".player-speed").click();
          assert(await page.locator(".floating-panel").isVisible());
          await page.mouse.click(2, 100);
          assert(await page.locator(".floating-panel").isHidden());
          assert(await page.locator("audio").evaluate((a) => !a.paused));
          assert(
            await page
              .locator("audio")
              .evaluate((a) => a === window.__dockAudio),
          );
          await page.locator(".mini-more").click();
          await page.locator(".mini-more").click();
          assert(await page.locator(".floating-panel").isHidden());
          await page.locator(".foot a").last().scrollIntoViewIfNeeded();
          const footer = await page.locator(".foot a").last().boundingBox();
          const circle = await page.locator(".mini-more").boundingBox();
          assert(
            footer.y + footer.height <= circle.y ||
              footer.x + footer.width <= circle.x,
            "Launcher blocks footer link",
          );
          await noOverflow();
        }
        await page.setViewportSize({ width: 390, height: 844 });
        await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
        await page.screenshot({
          path: "test-results/editor-floating-button-mobile.png",
        });
        await page.locator("audio").evaluate((a) => {
          a.playbackRate = 1;
          a.volume = 1;
        });
      },
    );
    await run(
      "new audio selection replaces the single session; no simultaneous playback",
      async () => {
        await open("/");
        await page.locator(".summary-box .audio-start").last().click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        assert.match(
          await page.locator("audio").getAttribute("src"),
          /oyun\/summary\.mp3/,
        );
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        assert.equal(await page.locator("audio").count(), 1);
        assert.match(
          await page.locator("audio").getAttribute("src"),
          /teknoloji\/podcast\.mp3/,
        );
        await page.locator("audio").evaluate((a) => a.pause());
      },
    );
    await run(
      "speed cycle, ten-second seeks, volume and mute control actual audio",
      async () => {
        const audio = page.locator("audio");
        await page.locator(".mini-more").click();
        for (const rate of [1.1, 1.2, 1.25, 1.5, 2, 0.75, 1]) {
          await page.locator(".player-speed").click();
          assert.equal(await audio.evaluate((a) => a.playbackRate), rate);
        }
        await page.locator(".player-seek").evaluate((i) => {
          i.value = "10";
          i.dispatchEvent(new Event("input"));
        });
        assert(
          Math.abs((await audio.evaluate((a) => a.currentTime)) - 10) < 0.5,
        );
        await page.locator(".player-skip").last().click();
        assert(
          Math.abs((await audio.evaluate((a) => a.currentTime)) - 20) < 0.5,
        );
        await page.locator(".player-skip").first().click();
        assert(
          Math.abs((await audio.evaluate((a) => a.currentTime)) - 10) < 0.5,
        );
        await page.locator(".player-volume").evaluate((i) => {
          i.value = ".3";
          i.dispatchEvent(new Event("input"));
        });
        assert.equal(await audio.evaluate((a) => a.volume), 0.3);
        await page.locator(".player-mute").click();
        assert(await audio.evaluate((a) => a.muted));
        await page.locator(".player-mute").click();
        assert.equal(await audio.evaluate((a) => a.muted), false);
      },
    );
    await run(
      "audio retry clears error; stopping mini-player releases session",
      async () => {
        await page
          .locator("audio")
          .evaluate((a) => a.dispatchEvent(new Event("error")));
        assert.match(
          await page.locator(".audio-status").innerText(),
          /yüklenemedi/,
        );
        await page.locator(".player .retry").click();
        assert.equal(await page.locator(".player .retry").isHidden(), true);
        await page.locator(".player-play").click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        await page
          .locator(".selection-grid .story-detail-link")
          .first()
          .click();
        await page.waitForURL("**/haber/**");
        await page.locator(".mini-more").click();
        await page.locator(".mini-close").click();
        assert(await page.locator(".persistent-audio").isHidden());
        assert.equal(await page.locator("audio").getAttribute("src"), null);
        assert(
          await page
            .locator("#main")
            .evaluate((n) => n === document.activeElement),
        );
      },
    );
    await run(
      "persistent shell links retain root targets across articles, legal pages and home",
      async () => {
        await open("/");
        const articleURL = await page
          .locator(".selection-grid .story-detail-link")
          .first()
          .getAttribute("href");
        const deepURL = new URL(articleURL, base + "/").pathname;
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        await page
          .locator("audio")
          .evaluate((a) => (a.dataset.continuity = "shell-links"));
        await page
          .locator(".selection-grid .story-detail-link")
          .first()
          .click();
        await page.waitForFunction(
          () => document.body.dataset.page === "article",
        );
        for (const [selector, route, identity] of [
          ['.foot a[href*="gizlilik"]', "/gizlilik/index.html", "legal"],
          ['.nav nav a[href*="teknoloji"]', "/teknoloji/index.html", "news"],
          [
            '.nav nav a[href*="podcastler"]',
            "/podcastler/index.html",
            "podcasts",
          ],
          [".nav .brand", "/index.html", "home"],
        ]) {
          await page.locator(selector).click();
          await page.waitForFunction(
            (identity) => document.body?.dataset.page === identity,
            identity,
          );
          assert.equal(new URL(page.url()).pathname, route);
          assert.equal(
            await page.locator("audio").evaluate((a) => a.dataset.continuity),
            "shell-links",
          );
          assert.equal(
            await page.locator("audio").evaluate((a) => a.paused),
            false,
          );
          assert.equal(
            await page.locator('link[rel="manifest"]').getAttribute("href"),
            base + "/manifest.webmanifest",
          );
        }
        await open(deepURL);
        assert.equal(
          await page.locator('.foot a[href*="gizlilik"]').getAttribute("href"),
          base + "/gizlilik/index.html",
        );
        await page.locator(".nav .brand").click();
        await page.waitForFunction(
          () => document.body?.dataset.page === "home",
        );
        assert.equal(new URL(page.url()).pathname, "/index.html");
      },
    );
    await run(
      "program visit never auto-plays or shows an unstarted mini-player",
      async () => {
        await open("/teknoloji/dinle/");
        assert(await page.locator("audio").evaluate((a) => a.paused));
        assert(await page.locator(".persistent-audio").isHidden());
        assert.equal(await page.locator(".player").isVisible(), false);
        assert.equal(await page.locator("audio").getAttribute("src"), null);
        assert.match(
          await page.locator(".episode .detail-meta").innerText(),
          /^16\.10\.2026/,
        );
        assert.equal(await page.locator(".episode .player").count(), 0);
        await page.locator(".listen-player .audio-start").click();
        await page.locator(".mini-more").click();
        assert(await page.locator(".floating-panel .player").isVisible());
        await page.screenshot({
          path: "test-results/editor-full-player-mobile.png",
          fullPage: true,
        });
        await axe();
        await page.locator(".theme-toggle").click();
        await axe();
        await page.locator(".theme-toggle").click();
      },
    );
    await run(
      "summary listening route shows summary identity and never pretends to be the podcast",
      async () => {
        await open("/teknoloji/dinle/?ses=ozet");
        assert.equal(
          await page.locator(".episode h1").innerText(),
          "Günün Özeti",
        );
        assert.equal(await page.title(), "Günün Özeti · Teknoloji · PULSE");
        assert.equal(
          await page
            .locator('meta[property="og:title"]')
            .getAttribute("content"),
          await page.title(),
        );
        assert.match(
          await page.locator('meta[property="og:url"]').getAttribute("content"),
          /ses=ozet/,
        );
        assert(await page.locator(".episode-hosts").isHidden());
        assert(await page.locator(".episode-heading .program-art").isHidden());
        assert.equal(await page.locator("audio").getAttribute("src"), null);
        assert.equal(
          await page
            .locator(".listen-player .audio-start")
            .getAttribute("data-kind"),
          "summary",
        );
        await page.locator(".listen-player .audio-start").click();
        assert.match(
          await page.locator("audio").getAttribute("src"),
          /summary.mp3/,
        );
        await page.locator("audio").evaluate((a) => a.pause());
        assert(await page.locator("audio").evaluate((a) => a.paused));
        await noOverflow();
      },
    );
    await run(
      "failed photographs retain story, source and a usable retry",
      async () => {
        await page.route("https://images.example.test/**", (r) => r.abort());
        await open("/");
        await page
          .locator(".image-fallback")
          .first()
          .waitFor({ state: "visible" });
        assert.equal(await page.locator(".selection-grid .story").count(), 3);
        assert.equal(
          await page.locator(".selection-grid .source-link").count(),
          3,
        );
        assert(
          await page
            .locator(".selection-grid .story-detail-link")
            .first()
            .isVisible(),
        );
        await page.unroute("https://images.example.test/**");
        await page.locator(".image-retry").first().click();
        await page.waitForFunction(
          () => document.querySelector(".story-image").naturalWidth > 0,
        );
      },
    );
    await run(
      "audio survives legal navigation and Media Session tracks the actual audio",
      async () => {
        await open("/");
        await page.evaluate(() => {
          window.__mediaHandlers = {};
          navigator.mediaSession.setActionHandler = (name, handler) =>
            (window.__mediaHandlers[name] = handler);
        });
        await page.locator(".podcast-box .audio-start").first().click();
        await page.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        await page.evaluate(
          () =>
            (document.querySelector("audio").dataset.continuity =
              "legal-proof"),
        );
        assert.equal(
          await page.evaluate(() => navigator.mediaSession.metadata.title),
          "Yeni Sekme",
        );
        await page.locator('.foot a[href*="gizlilik"]').click();
        await page.waitForURL("**/gizlilik/index.html");
        await page.waitForFunction(
          () => document.body.dataset.page === "legal",
        );
        assert(
          await page
            .locator("#main")
            .evaluate((n) => n.classList.contains("policy-page")),
        );
        assert.equal(
          await page.locator("audio").evaluate((a) => a.dataset.continuity),
          "legal-proof",
        );
        assert.equal(
          await page.locator("audio").evaluate((a) => a.paused),
          false,
        );
        await page.evaluate(() => window.__mediaHandlers.pause());
        assert.equal(
          await page.evaluate(() => navigator.mediaSession.playbackState),
          "paused",
        );
        await page.evaluate(() =>
          window.__mediaHandlers.seekto({ seekTime: 1 }),
        );
        assert.equal(
          await page.locator("audio").evaluate((a) => a.currentTime),
          1,
        );
        await page.goBack();
        await page.waitForFunction(() => document.body.dataset.page === "home");
        assert.equal(await page.locator("#main").getAttribute("class"), "");
        assert.equal(
          await page.locator("audio").evaluate((a) => a.dataset.continuity),
          "legal-proof",
        );
        await page.evaluate(() => window.__mediaHandlers.stop());
        assert.equal(
          await page.evaluate(() => navigator.mediaSession.metadata),
          null,
        );
        assert.equal(
          await page.evaluate(() => navigator.mediaSession.playbackState),
          "none",
        );
        await page.locator('.foot a[href*="gizlilik"]').click();
        await page.waitForFunction(
          () => document.body.dataset.page === "legal",
        );
        const verifiedRelease = await page.evaluate(()=>window.PULSE_RELEASE.manifest.release_id);
        await page.route("**/data/publication.json*", (r) => r.abort());
        const failedPoll = page.waitForEvent('requestfailed', request=>
          request.url().includes('/data/publication.json'));
        await page.evaluate(() =>
          document.dispatchEvent(new Event("visibilitychange")),
        );
        await failedPoll;
        // A single transient failure now retains the verified publication;
        // legal pages remain accessible throughout either state.
        assert.equal(await page.evaluate(()=>window.PULSE_RELEASE?.manifest.release_id),verifiedRelease);
        assert.equal(await page.locator("#pulse-printing").count(), 0);
        assert.equal(
          await page.locator(".site-shell").evaluate((n) => n.inert),
          false,
        );
        assert(await page.locator("#main h1").isVisible());
        await page.unroute("**/data/publication.json*");
      },
    );
    await run(
      "legal pages do not require publication access and support both themes",
      async () => {
        await page.route("**/data/publication.json*", (r) => r.abort());
        for (const slug of ["gizlilik", "kosullar"]) {
          await page.goto(base + "/" + slug + "/");
          assert.equal(await page.locator("h1").count(), 1);
          assert.equal(await page.locator("#pulse-printing").count(), 0);
          await axe();
          await page.locator(".theme-toggle").click();
          await axe();
          await noOverflow();
        }
        await page.unroute("**/data/publication.json*");
      },
    );
    await run(
      "ready pages do not briefly mount the printing screen",
      async () => {
        await page.addInitScript(() => {
          window.__printMounts = 0;
          new MutationObserver((rs) => {
            for (const r of rs)
              for (const n of r.addedNodes)
                if (
                  n.nodeType === 1 &&
                  (n.id === "pulse-printing" ||
                    n.querySelector?.("#pulse-printing"))
                )
                  window.__printMounts++;
          }).observe(document, { childList: true, subtree: true });
        });
        await page.route("**/data/publication.json*", async (r) => {
          await new Promise((ok) => setTimeout(ok, 350));
          await r.continue();
        });
        await open("/");
        assert.equal(await page.evaluate(() => window.__printMounts), 0);
        await page.unroute("**/data/publication.json*");
      },
    );
    await run(
      "stale HTML remains hidden until it matches the verified release",
      async () => {
        let requests = 0;
        await page.route(base + "/", async (route) => {
          const response = await route.fetch();
          let body = await response.text();
          requests++;
          if (requests === 1)
            body = body
              .replace(/data-release="[^"]+"/, 'data-release="stale-html"')
              .replace("Günün seçkisi", "ESKİ SAYFA");
          else await new Promise((resolve) => setTimeout(resolve, 600));
          await route.fulfill({ response, body });
        });
        await page.goto(base);
        await page.waitForFunction(() => window.PULSE_RELEASE);
        assert.equal(
          await page
            .locator(".site-shell")
            .evaluate((n) => getComputedStyle(n).visibility),
          "hidden",
        );
        await page.waitForFunction(
          () =>
            document.querySelector("#main").dataset.release ===
            window.PULSE_RELEASE?.manifest.release_id,
        );
        assert.match(await page.locator("h1").innerText(), /Günün seçkisi/);
        assert(await page.locator(".site-shell").isVisible());
        await page.unroute(base + "/");
      },
    );
    await run(
      "iOS exposes device-volume guidance rather than a nonfunctional software slider",
      async () => {
        const c = await browser.newContext({
          viewport: { width: 390, height: 844 },
          userAgent:
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
        });
        const p = await c.newPage();
        await p.goto(base + "/teknoloji/dinle/");
        await p.waitForFunction(
          () =>
            window.PULSE_RELEASE &&
            !document.querySelector(".site-shell").inert,
        );
        await p.locator(".listen-player .audio-start").click();
        await p.locator(".mini-more").click();
        assert(await p.locator(".player-volume").isHidden());
        assert(await p.locator(".device-volume").isVisible());
        await c.close();
      },
    );
    await run(
      "printing artwork animates paper, respects reduced motion and has a distinct offline illustration",
      async () => {
        const c = await browser.newContext({
          viewport: { width: 390, height: 844 },
          reducedMotion: "no-preference",
        });
        const p = await c.newPage();
        await p.route("**/data/publication.json*", async (r) => {
          const response = await r.fetch();
          await r.fulfill({
            response,
            headers: {
              ...response.headers(),
              date: "Fri, 16 Oct 2026 04:29:00 GMT",
              "cache-control": "no-store",
            },
          });
        });
        await p.goto(base);
        await p.locator('.pulse-printing[data-mode="printing"]').waitFor();
        await p.waitForFunction(
          () =>
            performance
              .getEntriesByType("resource")
              .filter((r) => /press-(model|mask)/.test(r.name)).length === 2,
        );
        const maskCheck = await p.evaluate(async () => {
          const shape = document.querySelector(".press-paper-path > g");
          const projection = shape.transform.baseVal.consolidate().matrix;
          const inverse = new DOMMatrix([
            projection.a,
            projection.b,
            projection.c,
            projection.d,
            projection.e,
            projection.f,
          ]).inverse();
          const image = new Image();
          image.src = document
            .querySelector(".press-occlusion-mask")
            .getAttribute("href");
          await image.decode();
          const canvas = document.createElement("canvas");
          canvas.width = canvas.height = 640;
          const context = canvas.getContext("2d");
          context.drawImage(image, 0, 0, 640, 640);
          const pixels = context.getImageData(0, 0, 640, 640).data;
          let visible = 0,
            outside = 0;
          for (let y = 0; y < 640; y++)
            for (let x = 0; x < 640; x++)
              if (pixels[(y * 640 + x) * 4] > 200) {
                visible++;
                const uv = new DOMPoint(x + 0.5, y + 0.5).matrixTransform(
                  inverse,
                );
                if (uv.x < -2 || uv.x > 242 || uv.y < -2 || uv.y > 322)
                  outside++;
              }
          return { visible, outside };
        });
        assert(maskCheck.visible > 10000, "Rendered paper mask missing");
        assert.equal(
          maskCheck.outside,
          0,
          "Printed surface does not match the rendered camera",
        );
        assert.equal(
          await p
            .locator(".press-newspaper")
            .evaluate((n) => getComputedStyle(n).animationName),
          "paper-feed",
        );
        await p.evaluate(
          () =>
            (window.__paper = getComputedStyle(
              document.querySelector(".press-newspaper"),
            ).transform),
        );
        await p.waitForFunction(
          () =>
            getComputedStyle(document.querySelector(".press-newspaper"))
              .transform !== window.__paper,
        );
        const animation = await p
          .locator(".press-newspaper")
          .evaluateHandle((n) => n.getAnimations()[0]);
        await animation.evaluate((a) => a.pause());
        const offsets = [];
        for (let frame = 0; frame < 14; frame++) {
          await animation.evaluate(
            (a, ms) => (a.currentTime = ms),
            frame * (12000 / 14),
          );
          offsets.push(
            await p
              .locator(".press-newspaper")
              .evaluate(
                (n) => new DOMMatrix(getComputedStyle(n).transform).m42,
              ),
          );
          await p.screenshot({
            path:
              "test-results/printing-frame-" +
              String(frame).padStart(2, "0") +
              ".png",
          });
        }
        assert(
          offsets.every((value, i) => i === 0 || value > offsets[i - 1]),
          "Paper must advance without reversing",
        );
        await animation.evaluate((a) => {
          a.currentTime = 0;
          a.play();
        });
        await p.screenshot({
          path: "test-results/editor-printing-animated-mobile.png",
          fullPage: true,
        });
        await p.emulateMedia({ reducedMotion: "reduce" });
        assert.equal(
          await p
            .locator(".press-newspaper")
            .evaluate((n) => getComputedStyle(n).animationName),
          "none",
        );
        await p.unroute("**/data/publication.json*");
        await p.route("**/data/publication.json*", async (r) => {
          const response = await r.fetch();
          const data = await response.json();
          data.status = "preparing";
          await r.fulfill({
            response,
            json: data,
            headers: {
              ...response.headers(),
              date: "Fri, 16 Oct 2026 05:00:00 GMT",
              "cache-control": "no-store",
            },
          });
        });
        await p.reload();
        await p.locator('.pulse-printing[data-mode="delayed"]').waitFor();
        assert.doesNotMatch(await p.locator('.pulse-print-card').innerText(), /hedef saati aşıldı/);
        assert.match(
          await p.locator(".pulse-print-card h1").innerText(),
          /devam ediyor/,
        );
        assert(await p.locator(".pulse-print-card .retry").isHidden());
        await p.screenshot({
          path: "test-results/editor-delayed-mobile.png",
          fullPage: true,
        });
        await p.unroute("**/data/publication.json*");
        await p.route("**/data/publication.json*", (r) =>
          r.fulfill({ status: 404, body: "missing" }),
        );
        await p.reload();
        await p.locator('.pulse-printing[data-mode="offline"]').waitFor();
        await p.waitForFunction(() => {
          const i = document.querySelector(".connection-illustration");
          return i?.complete && i.naturalWidth > 0;
        });
        assert.equal(await p.locator(".press-newspaper").count(), 0);
        await p.screenshot({
          path: "test-results/editor-connection-mobile.png",
          fullPage: true,
        });
        await c.close();
      },
    );
    await page.clock.install();
    let serverTime = "Fri, 16 Oct 2026 04:29:59 GMT";
    await page.route("**/data/publication.json*", async (r) => {
      const response = await r.fetch();
      await r.fulfill({
        response,
        headers: {
          ...response.headers(),
          date: serverTime,
          "cache-control": "no-store",
        },
      });
    });
    await run(
      "07:29 stays locked even when both files are complete",
      async () => {
        await page.goto(base);
        await page.locator("#pulse-printing").waitFor();
        assert(await page.locator(".site-shell").isHidden());
        await axe();
        await page.screenshot({
          path: "test-results/editor-printing-mobile.png",
          fullPage: true,
        });
      },
    );
    await run("07:30 opens only verified publications on polling", async () => {
      serverTime = "Fri, 16 Oct 2026 04:30:00 GMT";
      await page.clock.runFor(61000);
      await page.waitForFunction(() => window.PULSE_RELEASE);
      assert.equal(await page.locator("#pulse-printing").count(), 0);
    });
    await run(
      "next day 06:00 closes an open news page",
      async () => {
        serverTime = "Sat, 17 Oct 2026 03:00:00 GMT";
        await page.clock.runFor(61000);
        await page.waitForFunction(() => !window.PULSE_RELEASE);
        assert(await page.locator("#pulse-printing").isVisible());
        assert(await page.locator("audio").evaluate((a) => a.paused));
      },
    );
    await page.clock.resume();
    await page.unroute("**/data/publication.json*");
    await run(
      "client clock cannot bypass server publication rules",
      async () => {
        await page.addInitScript(() => {
          Date.now = () => new Date("2099-01-01T12:00:00Z").getTime();
        });
        await open("/");
        assert(await page.locator(".site-shell").isVisible());
      },
    );
    await run(
      "one missing MP3 prevents the entire daily release opening",
      async () => {
        await page.route("**/oyun/podcast.mp3", (r) =>
          r.fulfill({ status: 404, body: "missing" }),
        );
        await page.goto(base);
        await page.locator('#pulse-printing[data-mode="offline"]').waitFor();
        assert(await page.locator(".site-shell").isHidden());
        await page.unroute("**/oyun/podcast.mp3");
      },
    );
    await run("corrupt JSON remains closed", async () => {
      await page.route("**/releases/*/oyun.json", (r) =>
        r.fulfill({
          status: 200,
          contentType: "application/json",
          body: "{bad",
        }),
      );
      await page.goto(base + "/oyun/");
      await page.locator('#pulse-printing[data-mode="offline"]').waitFor();
      assert(await page.locator(".site-shell").isHidden());
      await page.unroute("**/releases/*/oyun.json");
    });
    await run(
      "missing manifest shows connection error rather than false preparation",
      async () => {
        await page.route("**/data/publication.json*", (r) =>
          r.fulfill({ status: 404, body: "missing" }),
        );
        await page.goto(base);
        await page.locator('#pulse-printing[data-mode="offline"]').waitFor();
        assert.match(
          await page.locator("#pulse-printing h1").innerText(),
          /doğrulanamadı/,
        );
        await page.unroute("**/data/publication.json*");
      },
    );
    await run(
      "offline ZIP opens local home, photos, full details and MP3 without external services",
      async () => {
        const c = await browser.newContext({
            offline: true,
            viewport: { width: 390, height: 844 },
          }),
          p = await c.newPage(),
          localErrors = [];
        p.on("pageerror", (e) => localErrors.push(e.message));
        const root = path.resolve("test-results/offline");
        try {
          await p.goto(
            require("node:url").pathToFileURL(path.join(root, "index.html"))
              .href,
          );
        } catch (error) {
          if (!error.message.includes("ERR_BLOCKED_BY_ADMINISTRATOR"))
            throw error;
          console.log(
            "NOTE managed Chromium blocks file URLs; testing extracted files with an in-memory origin while offline.",
          );
          await c.route("https://pulse-offline.test/**", async (r) => {
            let rel = decodeURIComponent(
              new URL(r.request().url()).pathname,
            ).replace(/^\//, "");
            if (rel.endsWith("/")) rel += "index.html";
            const file = path.resolve(root, rel);
            assert(file.startsWith(root + path.sep));
            const types = {
              ".html": "text/html",
              ".js": "application/javascript",
              ".css": "text/css",
              ".webp": "image/webp",
              ".svg": "image/svg+xml",
              ".mp3": "audio/mpeg",
            };
            await r.fulfill({
              status: 200,
              contentType:
                types[path.extname(file)] || "application/octet-stream",
              body: await fs.readFile(file),
            });
          });
          await p.goto("https://pulse-offline.test/index.html");
        }
        await p.waitForFunction(() => window.PULSE_ARCHIVE);
        assert.equal(await p.locator(".selection-grid .story").count(), 3);
        assert(
          await p
            .locator(".story-image")
            .first()
            .evaluate((i) => i.complete && i.naturalWidth > 0),
        );
        await p.locator(".podcast-box .audio-start").first().click();
        await p.waitForFunction(
          () => document.querySelector("audio").currentTime > 0.1,
        );
        await p.locator(".selection-grid .story-detail-link").first().click();
        await p.locator(".article-text p").first().waitFor({ state: "visible" });
        await p.waitForFunction(() => {
          const image = document.querySelector(".story-image");
          return image?.complete && image.naturalWidth > 0;
        });
        assert.equal(await p.locator(".article-text p").count(), 1);
        assert.equal(await p.locator(".source-link").count(), 1);
        assert.equal(await p.locator("#pulse-printing").count(), 0);
        assert(
          await p
            .locator(".story-image")
            .evaluate((i) => i.complete && i.naturalWidth > 0),
        );
        assert.deepEqual(localErrors, []);
        await p.screenshot({
          path: "test-results/editor-offline-detail.png",
          fullPage: true,
        });
        await c.close();
      },
    );
    await require("./publication-recovery-browser.cjs")(browser, run, base);
    await require("./chapters-browser.cjs")(browser, run, base);
    await require("./flow-browser.cjs")(browser, run, base);
    await require("./install-browser.cjs")(browser, run, base);
    await run("no browser runtime errors", async () =>
      assert.deepEqual(errors, []),
    );
    await context.close();
    console.log(`${passed} browser checks passed`);
  } finally {
    await browser.close();
  }
})()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(() => server.kill());
