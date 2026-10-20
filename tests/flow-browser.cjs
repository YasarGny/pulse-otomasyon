const assert = require('node:assert/strict');
const AxeBuilder = require('@axe-core/playwright').default;
module.exports = async (browser, run, base) => {
  const context = await browser.newContext({viewport:{width:390,height:844},locale:'tr-TR',reducedMotion:'reduce',serviceWorkers:'block'});
  const page = await context.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await context.route('https://images.example.test/**', r => r.fulfill({path:'site/assets/covers/teknoloji-768.webp',contentType:'image/webp'}));
  let visit = 0;
  const open = async (route, {resume=false}={}) => {
    if (!resume) {
      await page.goto(base+'/gizlilik/');
      await page.evaluate(()=>{try{localStorage.removeItem('pulse-flow-progress-v1')}catch(_){}});
    }
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
      await page.locator('.flow-category').selectOption('teknoloji');
      assert.equal(await page.locator('.flow-count').innerText(), '1 / 3');
      await page.locator('.flow-story:visible .article-text').evaluate(el => {
        for(let i=0;i<18;i++){const p=document.createElement('p');p.textContent='Uzun haberin ayrıntıları okunmaya devam ediyor.';el.append(p);}
      });
      await page.locator('.flow-viewport').evaluate(el=>el.scrollTop=250);
      await page.locator('.flow-next').evaluate(n=>n.click());
      assert.equal(await page.locator('.flow-story:visible').getAttribute('data-section'), 'teknoloji');
      await page.locator('.flow-previous').evaluate(n=>n.click());
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
      assert.equal(await page.locator('.flow-category').inputValue(),'teknoloji');
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
        const move = new TouchEvent('touchmove',{touches:[touch(250)],cancelable:true});
        el.dispatchEvent(move);
        if (!move.defaultPrevented) throw Error('Boundary gesture must consume native momentum');
        el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[touch(250)]}));
      });
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 6');
    });
    await run('PageDown and PageUp work immediately without an extra focus step',async()=>{
      await open('/akis/');
      await page.locator('.flow-viewport').evaluate(el=>el.scrollTop=el.scrollHeight);
      await page.locator('#main').focus();
      await page.keyboard.press('PageDown');
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 6');
      await page.keyboard.press('PageUp');
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 6');
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
      assert.match(await page.locator('.mini-subtitle').innerText(), /Haber kesiti/);
      await page.locator('.clip-full-episode').click();
      await page.waitForFunction(()=>!document.querySelector('audio').paused && document.querySelector('audio').currentTime>=14);
      assert.match(await page.locator('audio').getAttribute('src'),/teknoloji\/podcast.mp3/);
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
    });
    await run('story navigation preserves clip playback, return finds its story and another clip replaces it',async()=>{
      await open('/akis/');
      await page.waitForSelector('.flow-story:visible .story-clip-play');
      await page.locator('.flow-story:visible .story-clip-play').click();
      await page.waitForFunction(()=>!document.querySelector('audio').paused);
      await page.locator('audio').evaluate(a=>a.playbackRate=.25);
      const source=await page.locator('audio').getAttribute('src');
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
      assert.equal(await page.locator('.flow-story:visible .story-clip').count(),0);
      await page.locator('.mini-more').click();
      await page.locator('.clip-return').click();
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 6');
      assert.equal(await page.locator('audio').getAttribute('src'),source);
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
      await page.locator('.flow-category').selectOption('oyun');
      await page.locator('.mini-more').click();
      await page.locator('.clip-return').click();
      assert.equal(await page.locator('.flow-category').inputValue(),'teknoloji');
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 3');
      await page.locator('.flow-next').click();
      await page.locator('.flow-previous').click();
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
      await page.locator('.flow-next').click();
      await page.locator('.flow-story:visible .story-clip-play').click();
      assert.notEqual(await page.locator('audio').getAttribute('src'),source);
      assert.equal(await page.locator('audio').count(),1);
    });
    await run('normal article pages expose the same verified story clip',async()=>{
      await open('/teknoloji/haber/teknoloji0/');
      await page.waitForSelector('.story-clip');
      assert.equal(await page.locator('.story-clip').count(),1);
      assert.match(await page.locator('.story-clip').innerText(),/Podcast’te bu konu/);
    });
    await run('one story card queues only its own cuts, stops at the last and can replay or select a cut',async()=>{
      await open('/teknoloji/haber/teknoloji1/');
      await page.waitForSelector('.story-clip');
      assert.equal(await page.locator('.story-clip').count(),1);
      assert.match(await page.locator('.story-clip').innerText(),/2 kesit/);
      await page.evaluate(()=>{window.clipActions={};navigator.mediaSession.setActionHandler=(name,fn)=>window.clipActions[name]=fn;});
      await page.locator('.story-clip-play').click();
      await page.waitForFunction(()=>document.querySelector('audio').readyState>=2);
      await page.evaluate(()=>window.clipActions.pause());
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
      await page.evaluate(()=>window.clipActions.play());
      await page.waitForFunction(()=>!document.querySelector('audio').paused);
      await page.locator('audio').evaluate(a=>a.currentTime=a.duration-.1);
      await page.waitForFunction(()=>document.querySelector('audio').src.includes('-30.000-32.000.mp3'));
      await page.waitForFunction(()=>document.querySelector('audio').ended);
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
      await page.locator('.mini-more').click();
      assert.equal(await page.locator('.clip-part-label').innerText(),'Kesit 2/2');
      await page.locator('.clip-part-previous').click();
      await page.waitForFunction(()=>document.querySelector('audio').src.includes('-20.000-22.000.mp3')&&!document.querySelector('audio').paused);
      await page.locator('.clip-part-next').click();
      await page.waitForFunction(()=>document.querySelector('audio').src.includes('-30.000-32.000.mp3'));
      await page.waitForFunction(()=>document.querySelector('audio').ended);
      await page.locator('.player-play').click();
      await page.waitForFunction(()=>document.querySelector('audio').src.includes('-20.000-22.000.mp3')&&!document.querySelector('audio').paused);
      assert.equal(await page.locator('audio').count(),1);
      const source=await page.locator('audio').getAttribute('src');
      await page.locator('.article-reader .back').click();
      await page.waitForSelector('#stories');
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
      await page.evaluate(()=>window.clipActions.pause());
      await page.locator('audio').evaluate(a=>a.dispatchEvent(new Event('ended')));
      assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
      assert.equal(await page.locator('audio').getAttribute('src'),source);
    });
    await run('immersive header is centered and mobile has a content preview instead of a fixed footer',async()=>{
      await page.setViewportSize({width:390,height:844});await open('/akis/');
      const layout=await page.evaluate(()=>{
        const title=document.querySelector('.flow-heading h1').getBoundingClientRect();
        const header=document.querySelector('.flow-header').getBoundingClientRect();
        const preview=document.querySelector('.flow-next');
        return {titleCenter:title.x+title.width/2,screen:innerWidth/2,headerHeight:header.height,
                previewPosition:getComputedStyle(preview).position,footer:!!document.querySelector('.flow-navigation')};
      });
      assert(Math.abs(layout.titleCenter-layout.screen)<1);assert(layout.headerHeight<=60);
      assert.equal(layout.footer,false);assert.notEqual(layout.previewPosition,'fixed');
      assert(await page.locator('.flow-next-title').innerText());
      await page.locator('.flow-next').click();
      assert.equal(await page.locator('.flow-count').innerText(),'2 / 6');
    });
    await run('same-day flow restores story category and reading position on reentry and a fresh tab',async()=>{
      await page.setViewportSize({width:390,height:500});await open('/akis/');
      await page.locator('.flow-category').selectOption('teknoloji');
      await page.locator('.flow-next').click();
      await page.locator('.flow-story:visible .story-image').evaluate(image=>image.decode());
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      await page.locator('.flow-viewport').evaluate(el=>{
        el.dispatchEvent(new WheelEvent('wheel',{deltaY:1,bubbles:true}));el.scrollTop=80;
      });
      const position=await page.locator('.flow-viewport').evaluate(el=>el.scrollTop);
      assert(position>0);
      const id=await page.locator('.flow-story:visible').getAttribute('data-story');
      await page.locator('.flow-close').click();
      await page.locator('.nav a[href*="akis/"]').click();
      assert.equal(await page.locator('.flow-story:visible').getAttribute('data-story'),id);
      assert.equal(await page.locator('.flow-category').inputValue(),'teknoloji');
      assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.scrollTop),position);
      const fresh=await context.newPage();await fresh.setViewportSize({width:390,height:500});
      await fresh.goto(base+'/akis/');await fresh.waitForSelector('.flow-story:visible');
      assert.equal(await fresh.locator('.flow-story:visible').getAttribute('data-story'),id);
      assert.equal(await fresh.locator('.flow-viewport').evaluate(el=>el.scrollTop),position);
      assert.equal(await fresh.locator('audio').evaluate(a=>a.paused),true);
      await fresh.close();
      await page.locator('.flow-reset').click();
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 3');
      assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.scrollTop),0);
    });
    await run('stale daily progress and removed story identities cannot open the wrong story',async()=>{
      await page.goto(base+'/gizlilik/');
      await page.evaluate(()=>localStorage.setItem('pulse-flow-progress-v1',JSON.stringify({date:'2000-01-01',section:'teknoloji',story:'teknoloji1',filter:'teknoloji',position:100})));
      await open('/akis/',{resume:true});
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 6');
      await page.goto(base+'/gizlilik/');
      await page.evaluate(()=>localStorage.setItem('pulse-flow-progress-v1',JSON.stringify({date:'2026-10-16',section:'teknoloji',story:'removed-id',filter:'teknoloji',position:100,complete:true})));
      await open('/akis/',{resume:true});
      assert.equal(await page.locator('.flow-count').innerText(),'1 / 3');
      assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.scrollTop),0);
    });
    await run('flow still opens and navigates when persistent storage is denied',async()=>{
      const denied=await browser.newContext({serviceWorkers:'block'});
      await denied.addInitScript(()=>{Storage.prototype.getItem=()=>{throw Error('denied')};Storage.prototype.setItem=()=>{throw Error('denied')};Storage.prototype.removeItem=()=>{throw Error('denied')}});
      const other=await denied.newPage();await other.goto(base+'/akis/');
      await other.waitForSelector('.flow-story:visible');
      assert.equal(await other.locator('.flow-count').innerText(),'1 / 6');
      await other.locator('.flow-next').click();
      assert.equal(await other.locator('.flow-count').innerText(),'2 / 6');
      await denied.close();
    });
    await run('flow fits mobile and desktop and exposes accessible controls',async()=>{
      for(const width of [320,390,768,1440]) {
        await page.setViewportSize({width,height:900});
        await open('/akis/');
        await page.waitForSelector('.flow-story:visible');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
        assert.equal(await page.locator('.flow-viewport').evaluate(el=>el.clientHeight>200),true);
        const alignment=await page.evaluate(()=>{
          const select=document.querySelector('.flow-category').getBoundingClientRect();
          const icon=document.querySelector('.flow-category-label > svg').getBoundingClientRect();
          const image=document.querySelector('.flow-next-image').getBoundingClientRect();
          const copy=document.querySelector('.flow-next-copy').getBoundingClientRect();
          return {chevronOffset:Math.abs(select.y+select.height/2-icon.y-icon.height/2),
            imageLeft:image.right<=copy.left,within:copy.right<=innerWidth};
        });
        assert(alignment.chevronOffset<1);assert(alignment.imageLeft);assert(alignment.within);
        await page.screenshot({path:`test-results/flow-${width}.png`});
      }
      const results=await new AxeBuilder({page}).analyze();
      assert.deepEqual(results.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
      assert.deepEqual(errors,[]);
    });
  } finally {await context.close();}
};
