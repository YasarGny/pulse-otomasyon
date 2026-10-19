const assert = require('node:assert/strict');
const AxeBuilder = require('@axe-core/playwright').default;
module.exports = async (browser, run, base) => {
  const context = await browser.newContext({viewport:{width:390,height:844},locale:'tr-TR',reducedMotion:'reduce',serviceWorkers:'block'});
  const page = await context.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await context.route('https://images.example.test/**', r => r.fulfill({path:'site/assets/covers/teknoloji-768.webp',contentType:'image/webp'}));
  let visit = 0;
  const open = async route => {
    const url = new URL(route, base); url.searchParams.set('flow_check', String(++visit));
    await page.goto(url.href);
    await page.waitForFunction(() => window.PULSE_RELEASE && !document.documentElement.classList.contains('pulse-loading') && !document.documentElement.classList.contains('pulse-locked'));
  };
  try {
    await run('flow opens as a separate surface and returns to the original scroll position', async () => {
      await open('/teknoloji/');
      await page.evaluate(() => scrollTo({top:300,behavior:'instant'}));
      const y = await page.evaluate(() => scrollY);
      // A normal link uses the shared same-origin navigation and preserves history.
      await page.evaluate(() => document.querySelector('.nav a[href*="akis"]').click());
      await page.waitForSelector('.news-flow');
      assert.equal(await page.locator('.flow-story:visible').count(), 1);
      assert.equal(await page.locator('.flow-count').innerText(), '1 / 3');
      await page.locator('.flow-close').click();
      await page.waitForSelector('.category-audio, #stories');
      await page.waitForFunction(y => Math.abs(scrollY-y)<3, y);
    });
    await run('flow category stays selected, full text scroll restores, and wheel inertia cannot flip articles', async () => {
      await open('/akis/');
      await page.locator('[data-flow-filter="teknoloji"]').click();
      assert.equal(await page.locator('.flow-count').innerText(), '1 / 3');
      await page.locator('.flow-story:visible .article-text').evaluate(el => {
        for(let i=0;i<18;i++){const p=document.createElement('p');p.textContent='Uzun haberin ayrıntıları okunmaya devam ediyor.';el.append(p);}
      });
      await page.locator('.flow-viewport').evaluate(el=>el.scrollTop=250);
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('.flow-story:visible').getAttribute('data-section'), 'teknoloji');
      await page.locator('.flow-previous').click();
      assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.scrollTop),250);
      await page.locator('.flow-viewport').evaluate(el=>{
        el.dispatchEvent(new WheelEvent('wheel',{deltaY:80,bubbles:true,cancelable:true}));
        el.scrollTop=el.scrollHeight;
        el.dispatchEvent(new WheelEvent('wheel',{deltaY:40,bubbles:true,cancelable:true}));
      });
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 3');
      await page.waitForTimeout(750);
      await page.locator('.flow-viewport').dispatchEvent('wheel',{deltaY:80,bubbles:true,cancelable:true});
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 3');
      await page.reload();
      await page.waitForFunction(()=>!document.documentElement.classList.contains('pulse-loading'));
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 3');
      assert.equal(await page.locator('[data-flow-filter="teknoloji"]').getAttribute('aria-pressed'),'true');
      await page.locator('.flow-next').click(); await page.locator('.flow-next').click();
      assert.equal(await page.locator('.flow-end').isVisible(),true);
      await page.locator('.flow-restart').click();
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 3');
    });
    await run('a fresh vertical touch is required after finishing a long article',async()=>{
      await open('/akis/');
      await page.locator('.flow-story:visible .article-text').evaluate(el=>{
        for(let i=0;i<20;i++){const p=document.createElement('p');p.textContent='Haberi okumaya devam ederken başka habere geçilmez.';el.append(p);}
      });
      await page.locator('.flow-viewport').evaluate(el=>{
        el.scrollTop=100;
        const touch=y=>new Touch({identifier:1,target:el,clientX:120,clientY:y});
        el.dispatchEvent(new TouchEvent('touchstart',{touches:[touch(450)]}));
        el.scrollTop=el.scrollHeight;
        el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[touch(250)]}));
      });
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 6');
      await page.locator('.flow-viewport').evaluate(el=>{
        const touch=y=>new Touch({identifier:2,target:el,clientX:120,clientY:y});
        el.dispatchEvent(new TouchEvent('touchstart',{touches:[touch(450)]}));
        el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[touch(250)]}));
      });
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 6');
    });
    await run('a real bounded clip uses the single audio session and stops at native EOF',async()=>{
      await open('/akis/');
      await page.waitForSelector('.flow-story:visible .story-clip-play');
      await page.locator('.flow-story:visible .story-clip-play').click();
      await page.waitForFunction(()=>!document.querySelector('audio').paused);
      assert.equal(await page.locator('audio').count(),1);
      assert.match(await page.locator('audio').getAttribute('src'),/releases\/[^/]+\/clips\//);
      await page.waitForFunction(()=>document.querySelector('audio').ended);
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
      assert.equal(await page.locator('audio').evaluate(a=>a.duration<2.2),true);
      await page.locator('.mini-more').click();
      assert.equal(await page.locator('.clip-notice').isVisible(),true);
      assert.equal(await page.locator('.clip-full-episode').isVisible(),true);
      await page.locator('.clip-full-episode').click();
      await page.waitForFunction(()=>!document.querySelector('audio').paused && document.querySelector('audio').currentTime>=14);
      assert.match(await page.locator('audio').getAttribute('src'),/teknoloji\/podcast.mp3/);
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
    });
    await run('switching stories stops only clip playback and unmapped news has no misleading audio strip',async()=>{
      await open('/akis/');
      await page.waitForSelector('.flow-story:visible .story-clip-play');
      await page.locator('.flow-story:visible .story-clip-play').click();
      await page.waitForFunction(()=>!document.querySelector('audio').paused);
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
      assert.equal(await page.locator('.flow-story:visible .story-clip').count(),0);
      await page.locator('.flow-previous').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
    });
    await run('normal article pages expose the same verified story clip',async()=>{
      await open('/teknoloji/haber/teknoloji0/');
      await page.waitForSelector('.story-clip');
      assert.equal(await page.locator('.story-clip').count(),1);
      assert.match(await page.locator('.story-clip').innerText(),/Podcast’te bu konu/);
    });
    await run('flow fits mobile and desktop and exposes accessible controls',async()=>{
      for(const width of [320,390,768,1440]) {
        await page.setViewportSize({width,height:900});
        await open('/akis/');
        await page.waitForSelector('.flow-story:visible');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
        assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.clientHeight>200),true);
        await page.screenshot({path:`test-results/flow-${width}.png`});
      }
      const results=await new AxeBuilder({page}).analyze();
      assert.deepEqual(results.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
      assert.deepEqual(errors,[]);
    });
  } finally {await context.close();}
};
