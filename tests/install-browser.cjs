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
    "footer installation is explicit, responsive and remains available after cancellation",
    async () => {
      const { context, page } = await create();
      await open(page);
      assert(await page.locator(".foot-actions .install-entry").isVisible());
      assert.equal(await page.locator(".install-card").count(), 0);
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.locator(".foot").scrollIntoViewIfNeeded();
        for (const theme of ["dark", "light"]) {
          await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          assert(await page.locator(".install-entry").evaluate(n => n.getBoundingClientRect().height >= 44));
          const baselines = await page.evaluate(() =>
            [".foot .brand", ".install-entry", ".foot-actions a"].map(selector => {
              const node = document.querySelector(selector), style = getComputedStyle(node);
              const range = document.createRange();
              range.selectNodeContents(node.firstChild);
              const canvas = document.createElement("canvas").getContext("2d");
              canvas.font = style.fontWeight + " " + style.fontSize + " " + style.fontFamily;
              return range.getBoundingClientRect().bottom -
                canvas.measureText(node.firstChild.textContent).fontBoundingBoxDescent;
            }),
          );
          assert(Math.max(...baselines) - Math.min(...baselines) < 1);
          const report = await new AxeBuilder({ page }).include(".foot").analyze();
          assert.deepEqual(report.violations.map(v => v.id), []);
          await page.screenshot({path: `test-results/install-footer-${width}-${theme}.png`});
        }
      }
      assert(await offer(page));
      assert.equal(await page.evaluate(() => window.__prompts || 0), 0);
      assert.equal(await page.locator(".install-card").count(), 0);
      await page.locator(".install-entry").click();
      assert.equal(await page.evaluate(() => window.__prompts), 1);
      assert(await page.locator(".install-entry").isVisible());
      await page.locator(".install-entry").click();
      assert(await page.locator(".install-help").isVisible());
      await page.keyboard.press("Escape");
      assert(await page.locator(".install-entry").evaluate(n => n === document.activeElement));
      await offer(page);
      await page.locator(".install-entry").click();
      assert.equal(await page.evaluate(() => window.__prompts), 2);
      await page.locator('.nav nav a[href*="teknoloji"]').click();
      await page.waitForSelector("#stories");
      assert.equal(await page.locator(".foot .install-entry").count(), 1);
      assert(await page.locator(".install-entry").isVisible());
      await context.close();
    },
  );
  await run(
    "legacy install records cannot block reinstall and new eligibility supersedes an install event",
    async () => {
      const { context, page } = await create();
      await page.addInitScript(() => {
        localStorage.setItem("pulse-app-installed", "true");
        localStorage.setItem("pulse-install-dismissed-until", String(Date.now()+30*86400000));
      });
      await open(page);
      assert(await page.locator(".install-entry").isVisible());
      assert.equal(await page.evaluate(() => localStorage.getItem("pulse-app-installed")), null);
      await page.evaluate(() => window.dispatchEvent(new Event("appinstalled")));
      assert(await page.locator(".install-entry").isHidden());
      await offer(page);
      assert(await page.locator(".install-entry").isVisible());
      await page.locator(".install-entry").click();
      assert.equal(await page.evaluate(() => window.__prompts), 1);
      await open(page);
      assert(await page.locator(".install-entry").isVisible());
      assert.equal(await page.locator(".install-card").count(), 0);
      await context.close();
    },
  );
  await run(
    "standalone and confirmed related installation suppress the footer action",
    async () => {
      for (const width of [1440,390]) {
        const { context, page } = await create({ viewport: {width,height:900} });
        await page.addInitScript(() => {
          const match=window.matchMedia.bind(window);
          window.matchMedia=q=>{
            const result=match(q);
            if(q==="(display-mode: standalone)") Object.defineProperty(result,"matches",{value:true});
            return result;
          };
        });
        await open(page);
        await offer(page);
        assert(await page.locator(".install-entry").isHidden());
        assert.equal(await page.locator(".install-card").count(), 0);
        await context.close();
      }
      const {context,page}=await create();
      await page.addInitScript(()=>{
        window.__relatedInstalled=true;
        Object.defineProperty(navigator,"getInstalledRelatedApps",{
          value:async()=>window.__relatedInstalled?[{platform:"webapp",id:location.origin+"/"}]:[],
        });
      });
      await open(page);
      await page.waitForFunction(()=>document.querySelector(".install-entry").hidden);
      await page.evaluate(()=>{
        window.__relatedInstalled=false;
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await page.waitForFunction(()=>!document.querySelector(".install-entry").hidden);
      await context.close();
    },
  );
  await run(
    "stale related-app checks cannot override fresh install eligibility",
    async () => {
      const {context,page}=await create();
      await page.addInitScript(()=>Object.defineProperty(navigator,"getInstalledRelatedApps",{
        value:()=>new Promise(resolve=>window.__resolveRelated=resolve),
      }));
      await open(page);
      await offer(page);
      await page.evaluate(()=>window.__resolveRelated([{platform:"webapp",id:location.origin+"/"}]));
      assert(await page.locator(".install-entry").isVisible());
      await page.locator(".install-entry").click();
      assert.equal(await page.evaluate(()=>window.__prompts),1);
      await context.close();
    },
  );
  await run(
    "prompt acceptance needs confirmation and native failure offers a manual guide",
    async () => {
      const {context,page}=await create();
      await open(page);
      await page.evaluate(()=>{
        const e=new Event("beforeinstallprompt",{cancelable:true});
        e.prompt=async()=>{};
        e.userChoice=Promise.resolve({outcome:"accepted"});
        window.dispatchEvent(e);
      });
      await page.locator(".install-entry").click();
      assert(await page.locator(".install-entry").isVisible());
      await page.evaluate(()=>window.dispatchEvent(new Event("appinstalled")));
      assert(await page.locator(".install-entry").isHidden());
      await page.evaluate(()=>{
        const e=new Event("beforeinstallprompt",{cancelable:true});
        e.prompt=async()=>{throw Error("expired prompt");};
        window.dispatchEvent(e);
      });
      await page.locator(".install-entry").click();
      assert(await page.locator(".install-help").isVisible());
      await page.keyboard.press("Escape");
      assert(await page.locator(".install-entry").isEnabled());
      await context.close();
    },
  );
  await run(
    "manual Android and desktop guides work without eligibility or storage access",
    async () => {
      for (const mobile of [true,false]) {
        const {context,page}=await create(mobile?{
          viewport:{width:390,height:844},
          userAgent:"Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0.0.0 Mobile Safari/537.36",
        }:{});
        await page.addInitScript(()=>{
          for(const key of ["getItem","setItem","removeItem"])
            Storage.prototype[key]=()=>{throw Error("blocked");};
          Object.defineProperty(navigator,"getInstalledRelatedApps",{value:async()=>{throw Error("unavailable");}});
        });
        await open(page);
        assert(await page.locator(".install-entry").isVisible());
        assert.equal(await page.locator("dialog[open]").count(),0);
        await page.locator(".install-entry").click();
        assert(await page.locator(".install-help").isVisible());
        assert.match(await page.locator(".install-help").innerText(),mobile?/Ana ekrana ekle/:/Adres çubuğundaki/);
        const report=await new AxeBuilder({page}).analyze();
        assert.deepEqual(report.violations.map(v=>v.id),[]);
        await page.keyboard.press("Escape");
        assert(await page.locator(".install-entry").evaluate(n=>n===document.activeElement));
        await context.close();
      }
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
      await page.locator(".install-entry").click();
      await page.evaluate(() => {
        document.documentElement.classList.add("pulse-locked");
        window.dispatchEvent(new Event("pulse:locked"));
      });
      assert(await page.locator(".install-help").isHidden());
      assert(await page.locator(".install-entry").isHidden());
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
      await page.locator(".mini-more").click();
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
