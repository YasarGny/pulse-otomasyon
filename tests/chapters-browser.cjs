const assert = require('node:assert/strict');
module.exports = async function(browser, run, base) {
  const context = await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce',serviceWorkers:'block'});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror',e=>errors.push(e.message));
  const open = async path => {
    await page.goto(base+path);
    await page.waitForFunction(()=>!!window.PULSE_RELEASE && !document.documentElement.classList.contains('pulse-locked'));
  };
  await run('chapter clicks seek the same audio without moving the article or reading position',async()=>{
    await open('/teknoloji/dinle/');
    await page.waitForSelector('.episode-chapters');
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>document.querySelector('audio').currentTime>=12 && !document.querySelector('audio').paused);
    const src = await page.locator('audio').getAttribute('src');
    await page.locator('.nav nav a[href*="oyun/index"]').click();
    await page.waitForSelector('body[data-section="oyun"] #stories');
    await page.locator('#stories .story-detail-link').first().click();
    await page.waitForSelector('.article-reader');
    const url = page.url(), scroll = await page.evaluate(()=>scrollY);
    await page.locator('.mini-more').click();
    await page.locator('#chapters-tab').click();
    await page.locator('.player-chapters [data-start="28"]').click();
    await page.waitForFunction(()=>document.querySelector('audio').currentTime>=28);
    assert.equal(page.url(),url);
    assert(Math.abs(await page.evaluate(()=>scrollY)-scroll)<=2);
    assert.equal(await page.locator('audio').getAttribute('src'),src);
    assert.equal(await page.locator('audio').count(),1);
    assert.equal(await page.locator('.player-chapters [data-start="28"]').getAttribute('aria-current'),'true');
    assert(await page.locator('.player-play').isVisible());
    const failedMedia = '**/releases/*/teknoloji/podcast.mp3';
    await context.route(failedMedia,route=>route.abort('failed'));
    await page.locator('audio').evaluate(a=>a.load());
    await page.waitForFunction(()=>!!document.querySelector('audio').error);
    await context.unroute(failedMedia);
    await page.locator('.player-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>document.querySelector('audio').currentTime>=12 && !document.querySelector('audio').paused);
    assert(await page.locator('.player .retry').isHidden());
    await page.keyboard.press('Escape');
    assert(await page.locator('.floating-panel').isHidden());
    assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
  });
  await run('long player topic moves in both directions and reduced motion stays readable',async()=>{
    await open('/teknoloji/dinle/');
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>document.querySelector('audio').currentTime>=12);
    await page.locator('audio').evaluate(a=>a.pause());
    await page.locator('.mini-more').click();
    await page.emulateMedia({reducedMotion:'no-preference'});
    await page.mouse.move(0,0);
    await page.waitForFunction(()=>document.querySelector('.title-track').getAnimations().length>0);
    const result = await page.locator('.title-track').evaluate(track=>{
      const animation=track.getAnimations()[0], duration=animation.effect.getTiming().duration;
      const sample=ms=>{animation.currentTime=ms;return new DOMMatrix(getComputedStyle(track).transform).m41};
      animation.pause();
      return {start:sample(1000),middle:sample(duration/2),end:sample(duration-1000)};
    });
    assert(Math.abs(result.start)<1 && result.middle < -20 && Math.abs(result.end)<1);
    await page.locator('.scrolling-title').click();
    assert(await page.locator('.full-topic-title').isVisible());
    assert((await page.locator('.full-topic-title').innerText()).includes('bugünün gelişmeleri'));
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.waitForFunction(()=>document.querySelector('.title-track').getAnimations().length===0);
    assert(await page.locator('.scrolling-title').evaluate(e=>e.classList.contains('title-static')));
  });
  await run('mobile topic selection supports cancel, multiple topics, removable chips and scoped search',async()=>{
    await open('/expanded/teknoloji/');
    assert(await page.locator('.news-search').isHidden());
    await page.locator('.topics-toggle').click();
    await page.locator('.topic-options input').first().check();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.filter-chip').count(),0);
    await page.locator('.topics-toggle').click();
    for(const item of await page.locator('.topic-options input').all()) await item.check();
    await page.locator('.topics-apply').click();
    assert.equal(await page.locator('.filter-chip').count(),2);
    await page.locator('.filter-chip').first().click();
    assert.equal(await page.locator('.filter-chip').count(),1);
    await page.locator('.search-toggle').click();
    await page.locator('.news-search').fill('no-match');
    assert(await page.locator('.empty-filter').isVisible());
    await page.locator('.search-toggle').click();
    await page.locator('.search-clear').click();
    assert(await page.locator('.news-search').isVisible());
    assert(await page.locator('.news-search').evaluate(input=>input===document.activeElement));
    assert.equal(await page.locator('.filter-chip').count(),1);
    for(const story of await page.locator('#stories .story:visible').all())
      assert.equal(await story.getAttribute('data-section'),'teknoloji');
  });
  await run('menu indicator equals its text width at desktop and mobile sizes',async()=>{
    for(const width of [320,390,768,1440]) {
      await page.setViewportSize({width,height:900});
      const widths=await page.locator('.nav nav a').evaluateAll(nodes=>nodes.map(a=>{
        const span=a.querySelector('span'), r=span.getBoundingClientRect();
        const marker=getComputedStyle(span,'::after');
        return {text:r.width,line:parseFloat(marker.width),height:a.getBoundingClientRect().height};
      }));
      for(const w of widths) { assert(Math.abs(w.text-w.line)<1); assert(w.height>=44); }
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
  });
  await run('daily-only listening has no archive catalog and uses neutral player selection',async()=>{
    let catalogRequests = 0;
    const track = request => { if(request.url().includes('/assets/episodes/')) catalogRequests++; };
    page.on('request',track);
    await open('/teknoloji/dinle/');
    await page.waitForSelector('.episode-chapters');
    assert.equal(await page.locator('.episode-history,.history-start').count(),0);
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.locator('audio').evaluate(a=>a.pause());
    await page.locator('.mini-more').click();
    await page.locator('#chapters-tab').click();
    for(const width of [390,1440]) {
      await page.setViewportSize({width,height:900});
      const styles = await page.evaluate(()=>{
        const tab=getComputedStyle(document.querySelector('.player-tabs [aria-selected="true"]'));
        const active=getComputedStyle(document.querySelector('.player-chapters [aria-current="true"]'));
        return {tabBorder:tab.borderBottomColor,shadow:active.boxShadow,accent:getComputedStyle(document.querySelector('.player-play')).backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert(!styles.shadow.includes('3px 0px'));
      assert.notEqual(styles.tabBorder,styles.accent);
      assert(!styles.shadow.includes(styles.accent));
      assert.equal(styles.overflow,false);
      await page.screenshot({path:`test-results/neutral-player-${width}.png`});
    }
    assert.equal(catalogRequests,0);
    page.off('request',track);
    await page.setViewportSize({width:390,height:844});
    await page.keyboard.press('Escape');
  });
  await run('daily gate closes topic selection without stranding an already playing recording',async()=>{
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>!document.querySelector('audio').paused);
    await page.locator('.nav nav a[href*="teknoloji/index"]').click();
    await page.waitForSelector('#stories');
    await page.locator('.topics-dialog').evaluate(dialog=>dialog.showModal());
    await page.evaluate(()=>{
      document.documentElement.classList.add('pulse-locked');
      const overlay=document.createElement('div');overlay.className='pulse-printing';overlay.textContent='Haberler baskıya giriyor!';document.body.append(overlay);
      window.dispatchEvent(new Event('pulse:locked'));
    });
    assert.equal(await page.locator('audio').evaluate(a=>a.paused),false);
    assert(await page.locator('.topics-dialog').isHidden());
    await page.locator('.mini-more').click();
    assert(await page.locator('.player-play').isVisible());
    await page.locator('.player-play').click();
    assert.equal(await page.locator('audio').evaluate(a=>a.paused),true);
    await page.locator('.mini-close').click();
    assert(await page.locator('.persistent-audio').isHidden());
  });
  await run('a second tab takes over playback instead of playing two recordings',async()=>{
    await open('/teknoloji/dinle/');
    await page.locator('.listen-player .audio-start').click();
    await page.waitForFunction(()=>!document.querySelector('audio').paused);
    const other = await context.newPage();
    try {
      await other.goto(base+'/oyun/dinle/');
      await other.waitForFunction(()=>!!window.PULSE_RELEASE);
      await other.locator('.listen-player .audio-start').click();
      await other.waitForFunction(()=>!document.querySelector('audio').paused);
      await page.waitForFunction(()=>document.querySelector('audio').paused);
      assert.equal(await page.locator('audio').count(),1);
      assert.equal(await other.locator('audio').count(),1);
    } finally { await other.close(); }
  });
  await run('navigation never creates a scroll container, including enlarged mobile text',async()=>{
    await open('/');
    for(const width of [320,390,640,768,1440]) {
      await page.setViewportSize({width,height:900});
      const result=await page.locator('.nav nav').evaluate(nav=>{
        const style=getComputedStyle(nav),rect=nav.getBoundingClientRect();
        return {x:style.overflowX,y:style.overflowY,inside:[...nav.querySelectorAll('a')].every(a=>{const r=a.getBoundingClientRect();return r.left>=rect.left-1&&r.right<=rect.right+1}),pageOverflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert.equal(result.x,'visible'); assert.equal(result.y,'visible');
      assert(result.inside); assert(!result.pageOverflow);
    }
    await page.setViewportSize({width:320,height:844});
    await page.locator('.nav nav a').evaluateAll(links=>links.forEach(a=>a.style.fontSize='26px'));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(await page.locator('.nav nav a').count(),4);
  });
  await run('brief and sustained buffering never move player controls or resize the panel',async()=>{
    await page.setViewportSize({width:390,height:844});
    await open('/teknoloji/dinle/');
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>!document.querySelector('audio').paused);
    await page.locator('audio').evaluate(a=>a.pause());
    await page.locator('.mini-more').click();
    const rects=()=>page.evaluate(()=>['.floating-panel','.player-play','.player-seek','.player-tabs'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return {s,x:r.x,y:r.y,w:r.width,h:r.height}}));
    for(const width of [390,1440]) {
      await page.setViewportSize({width,height:900});
      const before=await rects();
      await page.locator('audio').evaluate(a=>a.dispatchEvent(new Event('waiting')));
      assert.equal(await page.locator('.player-play').getAttribute('data-buffering'),'false');
      await page.locator('audio').evaluate(a=>a.dispatchEvent(new Event('canplay')));
      assert.deepEqual(await rects(),before);
      await page.locator('audio').evaluate(a=>a.dispatchEvent(new Event('waiting')));
      await page.waitForFunction(()=>document.querySelector('.player-play').dataset.buffering==='true');
      assert.deepEqual(await rects(),before);
      assert.equal(await page.locator('.audio-status').innerText(),'');
      assert(await page.locator('.mini-status').evaluate(n=>n.classList.contains('sr-only')&&n.textContent.includes('yükleniyor')));
      await page.screenshot({path:`test-results/stable-buffering-${width}.png`});
      await page.locator('audio').evaluate(a=>a.dispatchEvent(new Event('canplay')));
      assert.deepEqual(await rects(),before);
      assert.equal(await page.locator('.player-play').getAttribute('data-buffering'),'false');
    }
  });
  await run('episode back links preserve the entry menu, scroll and related-program context',async()=>{
    await page.setViewportSize({width:390,height:844});
    await open('/podcastler/');
    const card=page.locator('.program-detail').nth(1);
    await card.scrollIntoViewIfNeeded();
    const originalURL=page.url(), originalScroll=await page.evaluate(()=>scrollY);
    await card.click();
    await page.waitForSelector('.listen-back');
    assert((await page.locator('.listen-back').innerText()).includes('Podcast’lere dön'));
    assert.equal(await page.locator('.listen-back').getAttribute('href'),originalURL);
    await page.locator('.episode-secondary > a').click();
    await page.waitForSelector('body[data-section="teknoloji"] .listen-back');
    await page.locator('.episode-stories .story-detail-link').first().click();
    await page.waitForSelector('.article-reader');
    assert((await page.locator('.article-reader .back').innerText()).includes('Bölüme dön'));
    await page.locator('.article-reader .back').click();
    await page.waitForSelector('.listen-back');
    await page.locator('.listen-back').click();
    await page.waitForURL(originalURL);
    await page.waitForFunction(y=>Math.abs(scrollY-y)<3,originalScroll);
    await open('/teknoloji/');
    await page.locator('.podcast-box .audio-copy a').click();
    await page.waitForSelector('.listen-back');
    assert((await page.locator('.listen-back').innerText()).includes('Teknoloji yayınına dön'));
    await page.locator('.listen-back').click();
    await page.waitForSelector('body[data-page="news"][data-section="teknoloji"] #stories');
    for(const query of ['?from=podcastler','?from=https://outside.example/','?from=constructor','']) {
      await open('/oyun/dinle/'+query);
      assert((await page.locator('.listen-back').innerText()).includes('Podcast’lere dön'));
      assert((await page.locator('.listen-back').getAttribute('href')).startsWith(base+'/podcastler/'));
    }
  });
  await run('article details have one publisher source and aligned readable metadata in both themes',async()=>{
    await open('/expanded/teknoloji/');
    await page.locator('#stories .story-detail-link').first().click();
    await page.waitForSelector('.article-reader');
    for(const theme of ['dark','light']) {
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      for(const width of [320,390,768,1440]) {
        await page.setViewportSize({width,height:900});
        assert.equal(await page.locator('.article-reader .source-link').count(),1);
        assert.equal(await page.locator('.article-source').count(),0);
        assert.equal(await page.locator('.article-meta time').getAttribute('datetime'),'2026-10-16');
        const geometry=await page.evaluate(()=>{
          const meta=document.querySelector('.article-meta'),source=meta.querySelector('.source-link');
          const text=document.querySelector('.article-text'),r=text.getBoundingClientRect();
          return {sourceHeight:source.getBoundingClientRect().height,column:r.width,overflow:document.documentElement.scrollWidth>innerWidth,line:parseFloat(getComputedStyle(text).lineHeight)/parseFloat(getComputedStyle(text).fontSize)};
        });
        assert(geometry.sourceHeight>=44);assert(geometry.column<=720);assert(geometry.line>=1.6);assert(!geometry.overflow);
        if(width===390||width===1440) {
          await page.evaluate(()=>scrollTo(0,0));
          await page.screenshot({path:`test-results/article-refined-${theme}-${width}.png`,fullPage:true});
        }
      }
    }
  });
  await run('transport stays precisely centered in both tabs and secondary controls share one row',async()=>{
    await open('/teknoloji/dinle/');
    await page.locator('.episode-chapters [data-start="12"]').click();
    await page.waitForFunction(()=>!document.querySelector('audio').paused);
    await page.locator('audio').evaluate(a=>a.pause());
    await page.locator('.mini-more').click();
    for(const theme of ['dark','light']) {
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      for(const [width,height] of [[320,568],[360,740],[390,844],[412,915],[768,600],[1440,900],[844,390]]) {
        await page.setViewportSize({width,height});
        for(const tab of ['#transport-tab','#chapters-tab']) {
          await page.locator(tab).click();
          const g=await page.evaluate(()=>{
            const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}};
            return {panel:box('.floating-panel'),back:box('.player-skip:first-child'),play:box('.player-play'),forward:box('.player-skip:nth-child(3)'),seek:box('.player-seek'),mute:box('.player-mute'),volume:box('.player-volume'),speed:box('.player-speed'),overflow:document.documentElement.scrollWidth>innerWidth};
          });
          assert(Math.abs(g.play.cx-g.panel.cx)<1,JSON.stringify({width,height,tab,g}));
          assert(Math.abs(g.play.cx-g.seek.cx)<1);
          assert(Math.abs(g.play.cy-g.back.cy)<1&&Math.abs(g.play.cy-g.forward.cy)<1);
          assert(Math.abs((g.play.cx-g.back.cx)-(g.forward.cx-g.play.cx))<1);
          assert.equal(g.play.w,64);assert.equal(g.play.h,64);assert(!g.overflow);
          if(tab==='#transport-tab') {
            assert(Math.abs(g.mute.cy-g.volume.cy)<1&&Math.abs(g.volume.cy-g.speed.cy)<1);
            assert(g.volume.x+g.volume.w<=g.speed.x-8);
            assert(g.speed.h>=44&&g.mute.h>=44);
            assert(await page.locator('.player-date').isHidden());
          } else {
            assert(await page.locator('.player-speed').isHidden());
          }
          if([390,1440].includes(width))await page.screenshot({path:`test-results/player-aligned-${theme}-${width}-${tab.slice(1)}.png`});
        }
      }
    }
  });
  await run('chapter UI has no runtime errors',async()=>assert.deepEqual(errors,[]));
  await context.close();
};
