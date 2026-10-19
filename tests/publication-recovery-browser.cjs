const assert = require('node:assert/strict');
module.exports = async function(browser, run, base) {
  async function scenario(test) {
    const context = await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block',reducedMotion:'reduce'});
    await context.route('https://images.example.test/**',route=>route.abort());
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.clock.install();
    let outage = false, status = 0, requests = 0, dateOffset = 0, headerSkew = 0;
    await page.route('**/data/publication.json*', async route => {
      requests++;
      if (outage) return status ? route.fulfill({status,body:'unavailable'}) : route.abort();
      const response = await route.fetch();
      const elapsed = await page.evaluate(()=>performance.now());
      return route.fulfill({response,headers:{...response.headers(),
        date:new Date(Date.UTC(2026,9,16,8)+dateOffset+elapsed+headerSkew).toUTCString(),age:'0'}});
    });
    try {
      await test({page, setOutage(value, code=0){outage=value;status=code;},
        get requests(){return requests;}, setDateOffset(value){dateOffset=value;}, setHeaderSkew(value){headerSkew=value;}});
      assert.deepEqual(errors, []);
    } finally {
      await page.unrouteAll({behavior:'wait'});
      await context.close();
    }
  }
  const opened = page => page.waitForFunction(()=>window.PULSE_RELEASE &&
    !document.documentElement.classList.contains('pulse-locked') &&
    !document.documentElement.classList.contains('pulse-loading'));
  await run('initial connection failure recovers automatically without reload',()=>scenario(async s=>{
    s.setOutage(true);
    await s.page.goto(base);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    s.setOutage(false);
    await s.page.clock.runFor(5100);
    await opened(s.page);
    assert.equal(await s.page.locator('#pulse-printing').count(),0);
  }));
  await run('transient background failure preserves reading and playing audio',()=>scenario(async s=>{
    await s.page.goto(base);
    await opened(s.page);
    await s.page.locator('.audio-start').first().click();
    await s.page.waitForFunction(()=>!document.querySelector('audio').paused);
    const before = await s.page.evaluate(()=>{scrollTo({top:300,behavior:"instant"});return {audio:document.querySelector('audio').src,scroll:scrollY};});
    s.setOutage(true,503);
    await s.page.clock.runFor(61000);
    assert.equal(await s.page.locator('#pulse-printing').count(),0);
    assert.equal(await s.page.locator('audio').evaluate(a=>a.paused),false);
    s.setOutage(false);
    await s.page.clock.runFor(11000);
    await opened(s.page);
    const after=await s.page.evaluate(()=>({audio:document.querySelector('audio').src,scroll:scrollY}));
    assert.deepEqual(after,before);
  }));
  await run('prolonged outage closes safely and recovers when connectivity returns',()=>scenario(async s=>{
    await s.page.goto(base); await opened(s.page);
    s.setOutage(true);
    await s.page.clock.runFor(123000);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    s.setOutage(false);
    await s.page.clock.runFor(31000);
    await opened(s.page);
  }));
  await run('retry button and online event recover without a navigation',()=>scenario(async s=>{
    s.setOutage(true); await s.page.goto(base);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    const before=s.requests;
    s.setOutage(false);
    await s.page.getByRole('button',{name:'Tekrar dene'}).click();
    await opened(s.page);
    assert.ok(s.requests>before);
    s.setOutage(true); await s.page.clock.runFor(123000);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    s.setOutage(false);
    await s.page.evaluate(()=>dispatchEvent(new Event('online')));
    await opened(s.page);
  }));
  await run('corruption during recheck closes immediately rather than using the grace window',()=>scenario(async s=>{
    await s.page.goto(base); await opened(s.page);
    await s.page.route('**/releases/*/oyun.json',r=>r.fulfill({status:200,contentType:'application/json',body:'{bad'}));
    await s.page.clock.runFor(61000);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    await s.page.unroute('**/releases/*/oyun.json');
    await s.page.clock.runFor(5100); await opened(s.page);
  }));
  await run('an older CDN Date header cannot trap an already verified tab',()=>scenario(async s=>{
    await s.page.goto(base); await opened(s.page);
    s.setHeaderSkew(-180000);
    await s.page.evaluate(()=>{window.verifiedPolls=0;addEventListener('pulse:verified',()=>window.verifiedPolls++);});
    for (let i=0;i<3;i++) {
      await s.page.clock.runFor(61000);
      await s.page.waitForFunction(n=>window.verifiedPolls>n,i);
    }
    assert.equal(await s.page.locator('#pulse-printing').count(),0);
    await opened(s.page);
    s.setHeaderSkew(0);
    const count=await s.page.evaluate(()=>window.verifiedPolls);
    await s.page.evaluate(()=>dispatchEvent(new Event('online')));
    await s.page.waitForFunction(n=>window.verifiedPolls>n,count);
    await opened(s.page);
  }));
  await run('temporary failure to replace stale HTML recovers without refreshing',()=>scenario(async s=>{
    let first = true, available = false;
    await s.page.route(base+'/', async route=>{
      if (!first && !available) return route.fulfill({status:503,body:'temporary'});
      const response = await route.fetch();
      if (!first) return route.fulfill({response});
      first = false;
      return route.fulfill({response,body:(await response.text()).replace(/data-release="[^"]+"/,'data-release="old"')});
    });
    await s.page.goto(base);
    await s.page.locator('#pulse-printing[data-mode="offline"]').waitFor();
    available = true;
    await s.page.clock.runFor(5100);
    await opened(s.page);
    assert.equal(await s.page.locator('#pulse-printing').count(),0);
  }));
  await run('connection grace never keeps yesterday open past 06:00',()=>scenario(async s=>{
    await s.page.goto(base); await opened(s.page);
    // Move trusted server time to 05:59:59 next morning before losing network.
    s.setDateOffset(Date.UTC(2026,9,17,2,59,50)-Date.UTC(2026,9,16,8)-await s.page.evaluate(()=>performance.now()));
    await s.page.evaluate(()=>{
      window.nearClosingVerified=false;
      addEventListener('pulse:verified',()=>window.nearClosingVerified=true,{once:true});
      dispatchEvent(new Event('online'));
    });
    await s.page.waitForFunction(()=>window.nearClosingVerified);
    assert.ok(await s.page.locator('.site-shell').isVisible());
    s.setOutage(true);
    await s.page.clock.runFor(11000);
    await s.page.waitForFunction(()=>!window.PULSE_RELEASE);
    assert.ok(await s.page.locator('#pulse-printing').isVisible());
  }));
};
