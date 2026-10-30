const assert = require('node:assert/strict');
module.exports = async (browser, run, base) => {
  const opened = p => p.waitForFunction(() => window.PULSE_RELEASE &&
    !document.documentElement.classList.contains('pulse-loading') &&
    !document.documentElement.classList.contains('pulse-locked'));
  async function scenario(width, fn) {
    const c = await browser.newContext({viewport:{width,height:900},serviceWorkers:'block',reducedMotion:'reduce'});
    let controls = {schema_version:1,enabled:true,podcasts:{teknoloji:true,oyun:true}};
    await c.route('**/data/controls.json*', r => r.fulfill({contentType:'application/json',body:JSON.stringify(controls)}));
    await c.route('https://images.example.test/**', r => r.abort());
    const p = await c.newPage(), errors = [];
    p.on('pageerror', e => errors.push(e.message));
    try { await fn(p, next => {controls=next;}); assert.deepEqual(errors, []); }
    finally { await c.close(); }
  }
  for (const width of [390,1280]) {
    await run(`production pause keeps publication and playing audio across 06:00 at ${width}px`, () => scenario(width, async (p,set) => {
      await p.goto(base); await opened(p);
      const manifest=await p.evaluate(()=>window.PULSE_RELEASE.manifest);
      const identity=await p.evaluate(()=>window.PULSE_RELEASE.manifest.release_id);
      await p.evaluate(()=>{
        const news=document.createElement('h2');news.id='fixture-news-heading';
        news.textContent='Bugünün podcast teknolojisi haberi';document.querySelector('main').append(news);
      });
      await p.locator('.podcast-box .audio-start').first().click();
      await p.waitForFunction(() => !document.querySelector('audio').paused);
      set({schema_version:1,enabled:true,automation_enabled:false,retained_release_id:identity,podcasts:{teknoloji:true,oyun:true}});
      await p.evaluate(()=>dispatchEvent(new Event('online')));
      await p.waitForFunction(()=>window.PulseControls.state.automation_enabled===false);
      assert.equal(await p.locator('#fixture-news-heading').innerText(),'Bugünün podcast teknolojisi haberi');
      assert.equal(await p.locator('audio').evaluate(a=>a.paused),false);
      await p.route('**/data/publication.json*',async route=>{
        try {
          await route.fulfill({contentType:'application/json',body:JSON.stringify(manifest),
            headers:{date:'Sat, 17 Oct 2026 03:00:00 GMT',age:'0'}});
        } catch(error) {
          if (!/closed|disposed/i.test(error.message)) throw error;
        }
      });
      await p.evaluate(()=>new Promise(resolve=>{
        addEventListener('pulse:verified',resolve,{once:true});
        dispatchEvent(new Event('online'));
      }));
      await p.waitForTimeout(1200); // Include the independent 1-second freshness check.
      assert.equal(await p.locator('#pulse-printing').count(),0);
      assert.equal(await p.locator('.site-shell').isVisible(),true);
      assert.equal(await p.locator('audio').evaluate(a=>a.paused),false);
      assert.match(await p.locator('.nav-issue').innerText(),/Son yayın · 16\.10\.2026/);
      assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await p.locator('.selection-grid .story-detail-link').first().click();
      await p.locator('.article-reader').waitFor();
      assert.equal(await p.locator('#pulse-printing').count(),0);
      assert.equal(await p.locator('audio').evaluate(a=>a.paused),false);
      await p.screenshot({path:`test-results/production-pause-${width}.png`,fullPage:true});
      // Re-enabling restores normal freshness rules; it does not manufacture today's edition.
      set({schema_version:1,enabled:true,automation_enabled:true,podcasts:{teknoloji:true,oyun:true}});
      await p.evaluate(()=>dispatchEvent(new Event('online')));
      await p.waitForFunction(()=>!window.PULSE_RELEASE);
      await p.locator('#pulse-printing').waitFor();
    }));
  }
  for (const section of ['teknoloji','oyun']) {
    await run(`individual ${section} podcast pause preserves news, summaries and the partner`, () => scenario(390, async (p,set) => {
      await p.goto(base); await opened(p);
      await p.locator(`[data-audio-section="${section}"][data-audio-kind="podcast"] .audio-start`).click();
      await p.waitForFunction(() => !document.querySelector('audio').paused);
      set({schema_version:1,enabled:true,podcasts:{teknoloji:section!=='teknoloji',oyun:section!=='oyun'}});
      await p.evaluate(() => dispatchEvent(new Event('online')));
      await p.waitForFunction(s => window.PulseControls.state.podcasts[s]===false,section);
      assert.equal(await p.locator('audio').evaluate(a => a.paused),true);
      assert.equal(await p.locator('.summary-box:visible').count(),2);
      assert.equal(await p.locator('.podcast-box:visible').count(),1);
      const partner = section==='teknoloji'?'oyun':'teknoloji';
      await p.locator(`[data-audio-section="${partner}"][data-audio-kind="podcast"] .audio-start`).click();
      await p.waitForFunction(() => !document.querySelector('audio').paused);
      assert.equal(await p.locator('.selection-grid').isVisible(),true);
    }));
  }
  for (const route of ['without-podcasts','tech-podcast-paused','game-podcast-paused']) {
    await run(`${route} is a valid daily publication with working summary and article navigation`, () => scenario(390, async p => {
      await p.goto(base+'/'+route+'/'); await opened(p);
      assert.equal(await p.locator('.summary-box').count(),2);
      assert.equal(await p.locator('.podcast-box').count(),route==='without-podcasts'?0:1);
      const summary = p.locator('.summary-box .audio-copy a').first();
      await summary.click();
      await p.locator('.episode h1').waitFor();
      assert.equal(await p.locator('.episode h1').innerText(),'Günün Özeti');
      await p.locator('.listen-player .audio-start').click();
      await p.waitForFunction(() => !document.querySelector('audio').paused);
      assert.equal(await p.locator('#pulse-printing').count(),0);
    }));
  }
};
