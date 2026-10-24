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
    await run(`owner global pause closes the whole site at ${width}px`, () => scenario(width, async (p,set) => {
      set({schema_version:1,enabled:false,podcasts:{teknoloji:true,oyun:true}});
      await p.goto(base);
      await p.getByRole('heading',{name:'Yayınlara kısa bir ara verdik.'}).waitFor();
      assert.equal(await p.locator('.site-shell').count(),0);
      assert.equal(await p.locator('#pulse-printing').count(),0);
      assert.equal(await p.evaluate(() => document.querySelector('audio')?.paused !== false),true);
      assert.equal(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
      await p.screenshot({path:`test-results/owner-pause-${width}.png`,fullPage:true});
    }));
  }
  await run('owner global pause stops an already playing audio session', () => scenario(390, async (p,set) => {
    await p.goto(base); await opened(p);
    await p.locator('.podcast-box .audio-start').first().click();
    await p.waitForFunction(() => !document.querySelector('audio').paused);
    set({schema_version:1,enabled:false,podcasts:{teknoloji:true,oyun:true}});
    await p.evaluate(() => dispatchEvent(new Event('online')));
    await p.getByRole('heading',{name:'Yayınlara kısa bir ara verdik.'}).waitFor();
    assert.equal(await p.evaluate(() => document.querySelector('audio')?.paused !== false),true);
  }));
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
