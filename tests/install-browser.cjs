/* Browser-level PWA checks. Native install dialogs and OS media UI need a real device. */
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const AxeBuilder = require("@axe-core/playwright").default;
module.exports = async (browser, run, base) => {
  const photo = await fs.readFile("site/assets/covers/teknoloji-768.webp");
  const create = async (options = {}) => {
    const context = await browser.newContext({
      serviceWorkers: "block",
      viewport: { width: 1440, height: 1000 },
      reducedMotion: "reduce",
      ...options,
    });
    await context.route("https://images.example.test/**", (r) =>
      r.fulfill({ contentType: "image/webp", body: photo }),
    );
    const page = await context.newPage();
    page.on("pageerror", (e) => {
      throw e;
    });
    return { context, page };
  };
  const open = async (page) => {
    await page.goto(base + "/");
    await page.waitForFunction(
      () =>
        window.PULSE_RELEASE &&
        !document.documentElement.classList.contains("pulse-loading"),
    );
  };
  const offer = (page) =>
    page.evaluate(() => {
      const e = new Event("beforeinstallprompt", { cancelable: true });
      e.prompt = async () => {
        window.__prompts = (window.__prompts || 0) + 1;
      };
      e.userChoice = Promise.resolve({ outcome: "dismissed" });
      window.dispatchEvent(e);
      return e.defaultPrevented;
    });
  await run(
    "install suggestion is eligible-only, responsive, accessible and dismissible",
    async () => {
      const { context, page } = await create();
      await open(page);
      assert(await page.locator(".install-entry").isHidden());
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        assert(await offer(page));
        await page.locator(".install-card").waitFor({ state: "visible" });
        for (const theme of ["dark", "light"]) {
          await page.evaluate(
            (theme) => (document.documentElement.dataset.theme = theme),
            theme,
          );
          assert(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          );
          const report = await new AxeBuilder({ page })
            .include(".install-card")
            .analyze();
          assert.deepEqual(
            report.violations.map((v) => v.id),
            [],
          );
          await page.screenshot({
            path: `test-results/install-${width}-${theme}.png`,
          });
        }
      }
      await page.locator(".install-dismiss").click();
      assert(await page.locator(".install-card").isHidden());
      assert(await page.locator(".install-entry").isVisible());
      await open(page);
      await offer(page);
      assert(await page.locator(".install-card").isHidden());
      await page.locator(".install-entry").click();
      assert.equal(await page.evaluate(() => window.__prompts), 1);
      assert(await page.locator(".install-entry").isHidden());
      await context.close();
    },
  );
  await run(
    "installed event and standalone mode suppress installation on mobile and desktop",
    async () => {
      const { context, page } = await create();
      await open(page);
      await offer(page);
      await page.locator(".install-card").waitFor({ state: "visible" });
      await page.evaluate(() =>
        window.dispatchEvent(new Event("appinstalled")),
      );
      assert(await page.locator(".install-card").isHidden());
      assert(await page.locator(".install-entry").isHidden());
      await open(page);
      await offer(page);
      assert(await page.locator(".install-entry").isHidden());
      await context.close();
      for (const width of [1440, 390]) {
        const { context, page } = await create({
          viewport: { width, height: 900 },
        });
        await page.addInitScript(() => {
          const match = window.matchMedia.bind(window);
          window.matchMedia = (q) => {
            const result = match(q);
            if (q === "(display-mode: standalone)")
              Object.defineProperty(result, "matches", { value: true });
            return result;
          };
        });
        await open(page);
        await offer(page);
        assert(await page.locator(".install-entry").isHidden());
        assert.equal(await page.locator(".install-card:visible").count(), 0);
        await context.close();
      }
    },
  );
  await run(
    "a related installed app suppresses the suggestion and denied storage does not break it",
    async () => {
      let pair = await create();
      await pair.page.addInitScript(() =>
        Object.defineProperty(navigator, "getInstalledRelatedApps", {
          value: async () => [
            { platform: "webapp", id: location.origin + "/" },
          ],
        }),
      );
      await open(pair.page);
      await offer(pair.page);
      assert(await pair.page.locator(".install-entry").isHidden());
      await pair.context.close();
      pair = await create();
      await pair.page.addInitScript(() => {
        Storage.prototype.getItem = () => {
          throw Error("blocked");
        };
        Storage.prototype.setItem = () => {
          throw Error("blocked");
        };
      });
      await open(pair.page);
      await offer(pair.page);
      await pair.page.locator(".install-card").waitFor({ state: "visible" });
      await pair.page.locator(".install-dismiss").click();
      assert(await pair.page.locator(".install-card").isHidden());
      await pair.context.close();
    },
  );
  await run(
    "Safari installation guide is user-requested and does not interrupt audio",
    async () => {
      const { context, page } = await create({
        viewport: { width: 390, height: 844 },
        userAgent:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      });
      await open(page);
      assert.equal(await page.locator(".install-card").count(), 0);
      await page.locator(".podcast-box .audio-start").first().click();
      await page.waitForFunction(
        () => document.querySelector("audio").currentTime > 0.1,
      );
      await page.locator(".install-entry").click();
      assert(await page.locator(".install-help").isVisible());
      assert.match(
        await page.locator(".install-help").innerText(),
        /Ana Ekrana Ekle/,
      );
      const report = await new AxeBuilder({ page }).analyze();
      assert.deepEqual(
        report.violations.map((v) => v.id),
        [],
      );
      assert.equal(
        await page.locator("audio").evaluate((a) => a.paused),
        false,
      );
      await page.keyboard.press("Escape");
      assert(await page.locator(".install-help").isHidden());
      await context.close();
    },
  );
  await run(
    "desktop Media Session exposes episode art, position, speed and controls",
    async () => {
      const { context, page } = await create();
      await open(page);
      await page.evaluate(() => {
        window.__actions = {};
        const session = navigator.mediaSession;
        session.setActionHandler = (name, handler) =>
          (window.__actions[name] = handler);
        const position = session.setPositionState.bind(session);
        session.setPositionState = (state) => {
          window.__position = state;
          return position(state);
        };
      });
      await page.locator(".podcast-box .audio-start").first().click();
      await page.waitForFunction(
        () => document.querySelector("audio").currentTime > 0.1,
      );
      assert.equal(
        await page.evaluate(() => navigator.mediaSession.metadata.title),
        "Yeni Sekme",
      );
      assert.match(
        await page.evaluate(
          () => navigator.mediaSession.metadata.artwork[0].src,
        ),
        /yeni-sekme/,
      );
      assert.equal(
        await page.evaluate(() => navigator.mediaSession.playbackState),
        "playing",
      );
      await page.locator(".player-speed").click();
      await page.waitForFunction(() => window.__position?.playbackRate === 1.1);
      await page.evaluate(() => window.__actions.pause());
      assert.equal(
        await page.evaluate(() => navigator.mediaSession.playbackState),
        "paused",
      );
      await page.evaluate(() => window.__actions.seekto({ seekTime: 20 }));
      await page.waitForFunction(
        () => Math.abs(window.__position.position - 20) < 0.1,
      );
      await page.evaluate(() => window.__actions.seekbackward());
      assert.equal(
        await page.locator("audio").evaluate((a) => a.currentTime),
        10,
      );
      await page.evaluate(() => window.__actions.seekforward());
      assert.equal(
        await page.locator("audio").evaluate((a) => a.currentTime),
        20,
      );
      await page.evaluate(() => window.__actions.stop());
      assert.equal(
        await page.evaluate(() => navigator.mediaSession.metadata),
        null,
      );
      await context.close();
    },
  );
  await run(
    "real service worker keeps news network-only and offers a safe offline screen",
    async () => {
      // Installation is intentionally disabled in Playwright's incognito contexts.
      // A fresh normal profile verifies the real browser eligibility requirements.
      const profile = await fs.mkdtemp(
        require("node:path").join(
          require("node:os").tmpdir(),
          "pulse-install-",
        ),
      );
      const systemChromium = await fs.access("/usr/bin/chromium").then(
        () => "/usr/bin/chromium",
        () => undefined,
      );
      const context = await browser
        .browserType()
        .launchPersistentContext(profile, {
          headless: true,
          executablePath: process.env.PULSE_CHROMIUM || systemChromium,
          args: ["--no-sandbox"],
          serviceWorkers: "allow",
          viewport: { width: 390, height: 844 },
        });
      await context.route("https://images.example.test/**", (r) =>
        r.fulfill({ contentType: "image/webp", body: photo }),
      );
      const page = context.pages()[0];
      await open(page);
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.waitForFunction(() => navigator.serviceWorker.controller);
      const cdp = await context.newCDPSession(page);
      const manifest = await cdp.send("Page.getAppManifest");
      assert.equal(manifest.errors.length, 0);
      const parsed = JSON.parse(manifest.data);
      assert.equal(parsed.display, "standalone");
      assert.equal(parsed.icons.length, 2);
      const installability = await cdp.send("Page.getInstallabilityErrors");
      assert.deepEqual(installability.installabilityErrors, []);
      assert.deepEqual(await page.evaluate(() => caches.keys()), []);
      await context.setOffline(true);
      await page.reload();
      assert.equal(
        await page.locator("h1").innerText(),
        "Bağlantı kurulamadı.",
      );
      assert.equal(await page.locator(".story").count(), 0);
      await context.setOffline(false);
      await page.locator("a").click();
      await page.waitForFunction(() => window.PULSE_RELEASE);
      assert.equal(await page.locator(".selection-grid .story").count(), 3);
      assert.deepEqual(await page.evaluate(() => caches.keys()), []);
      await context.close();
      await fs.rm(profile, { recursive: true, force: true });
    },
  );
};
