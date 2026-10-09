// Run with Playwright installed; BROWSER_EXECUTABLE optionally selects Chromium.
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const repo=path.resolve(__dirname,'..'),front=path.join(repo,'android/app/src/main/assets/frontend');
const server=http.createServer((req,res)=>{
 const name=path.basename(new URL(req.url,'http://localhost').pathname)||'index.html';
 const file=name==='nyxor-banner.svg'?path.join(repo,'docs/assets',name):path.join(front,name);
 if(!fs.existsSync(file)){res.writeHead(404).end();return;}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':'text/html');
 res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const url='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:390,height:1040},deviceScaleFactor:2,isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('https://static-cdn.jtvnw.net/nyxor-demo/*.png',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="180"><defs><linearGradient id="a"><stop stop-color="#cbb6f2"/><stop offset="1" stop-color="#625077"/></linearGradient></defs><ellipse cx="110" cy="150" rx="65" ry="10" fill="#000" opacity=".3"/><path d="M48 51 110 30 173 51V131L110 157 48 131Z" fill="url(#a)" stroke="#dac8f9" stroke-width="2"/><path d="M48 51 110 75 173 51M110 75V157" fill="none" stroke="#e3d7fc" stroke-width="2"/><path d="M75 43 138 66V144" fill="none" stroke="#a5e8c8" stroke-width="7"/></svg>'}));
  async function select(id,value){await page.locator(`[data-dropdown-for="${id}"]`).click();await page.locator(`.dropdown-menu.open [role=option][data-value="${value}"]`).click();}
  for(const language of ['uk','en']){
   const output=path.join(repo,'docs/screenshots',language==='en'?'en':'');fs.mkdirSync(output,{recursive:true});
   await page.goto(url+'/?demo=1');await page.locator('.hero').waitFor();
   await page.evaluate(language=>{
    demoState.settings.language=language;
    demoState.state.game_art_url='https://static-cdn.jtvnw.net/ttv-boxart/263490-144x192.jpg';
    demoState.watched.push({login:'nightwatch',display_name:'Nightwatch',game:'Warframe',earned:180,balance:4850,last_seen:new Date().toISOString()},
      {login:'duskplays',display_name:'DuskPlays',game:'Rust',earned:90,balance:1290,last_seen:new Date().toISOString()});
    demoState.history.push({timestamp:new Date().toISOString(),game:'Rust',claim:'Nightfall Hoodie',channel:'SharedStreamer'},
      {timestamp:new Date().toISOString(),game:'Warframe',claim:'Tenno Supply Cache',channel:'Nightwatch'});
    const benefit={id:'demo',name:'Sample reward',image_url:'https://static-cdn.jtvnw.net/nyxor-demo/crate.png'};
    for(const drop of demoState.state.active_drops)drop.benefits=[benefit];
    for(const drop of demoState.history)drop.benefits=[benefit];
    return refresh(true);
   },language);
   await page.waitForFunction(()=>document.querySelector('.game-art img')?.naturalWidth>0);
   await page.waitForFunction(()=>[...document.querySelectorAll('.reward .drop-art img')].length===2&&[...document.querySelectorAll('.reward .drop-art img')].every(img=>img.naturalWidth>0));
   async function capture(name){
    await page.evaluate(()=>Promise.allSettled(document.getAnimations().filter(a=>a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished)));
    assert.equal(await page.locator('html').getAttribute('lang'),language);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,name+'.png')});
   }
   for(const width of [320,390,768]){
    await page.setViewportSize({width,height:1040});
    const centered=await page.locator('#account-button').evaluate(button=>{
     const b=button.getBoundingClientRect(),i=button.querySelector('svg').getBoundingClientRect();
     return Math.abs((b.left+b.width/2)-(i.left+i.width/2))<.6 && Math.abs((b.top+b.height/2)-(i.top+i.height/2))<.6;
    });assert(centered,'Moon must be centered in its settings button');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   await page.setViewportSize({width:390,height:1040});await capture('overview');
   await page.locator('.shop-grid').evaluate(el=>window.scrollTo(0,el.previousElementSibling.previousElementSibling.getBoundingClientRect().top+scrollY-24));
   await capture('rewards');
   await page.locator('#nav [data-go=pointsPage]').click();await select('points-order','quiet');
   await page.locator('[data-directory=Rust]').click();await page.getByText('A quiet night',{exact:true}).waitFor();
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('points');
   await page.locator('[data-points-tab=history]').click();await page.locator('#select-history').click();
   await page.locator('[data-history-login=nightwatch]').click();
   assert.equal(await page.locator('.history-check:checked').count(),2);await capture('history');
   await page.locator('#nav [data-go=activity]').click();await select('reward-game','Rust');
   assert.equal(await page.locator('.event').count(),2);await capture('activity');
   await page.locator('#nav [data-go=settings]').click();await page.locator('[data-setting=energy_saver]').click();
   await page.waitForFunction(()=>document.documentElement.classList.contains('energy-saver'));
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('settings');
   await page.evaluate(async()=>{const sample=structuredClone(demoState);sample.account='moonrunner';sample.queue=['World of Tanks'];sample.state.game='World of Tanks';sample.state.channel='TankStreamer';sample.state.active_drops=[];sample.auto_farm=false;window.NyxorMobileDemo.profiles.set('demo-2',sample);await refresh(true);});
   await page.locator('[data-go=accounts]').click();await capture('accounts');
   await page.locator('[data-account-row=default] h2').click({delay:600});assert.equal(await page.locator('.account-check:checked').count(),1);
   await page.waitForTimeout(950);await page.locator('[data-account-row="demo-2"] .account-check').click();assert.equal(await page.locator('.account-check:checked').count(),2);await capture('accounts-selection');
   await page.locator('#delete-accounts').click();await page.locator('#cancel-confirm').click();assert.equal(await page.locator('.account-card').count(),2);
   await page.locator('#clear-account-selection').click();assert.equal(await page.locator('.account-check').count(),0);
   await page.locator('#select-accounts').click();await page.locator('[data-account-row=default] .account-check').click();assert.equal(await page.locator('.account-check').count(),0);
   await select('view-account','demo-2');await page.waitForFunction(()=>model.active_account_id==='demo-2');assert.deepEqual(await page.evaluate(()=>model.queue),['World of Tanks']);assert(await page.evaluate(()=>model.accounts.find(p=>p.id==='default').running));
   for(const [width,height] of [[320,568],[360,640],[390,844],[412,915],[768,1024]]){
    await page.setViewportSize({width,height});for(const route of ['home','games','streamers','pointsPage','activity','settings','accounts']){await page.evaluate(route=>navigate(route),route);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overflow at '+width+'/'+route);assert.equal(await page.locator('#nav .nav-item').count(),7);}
   }
   await page.setViewportSize({width:390,height:1040});await page.evaluate(()=>navigate('accounts'));await page.locator('#select-accounts').click();await page.locator('#delete-accounts').click();await page.locator('#accept-confirm').click();await page.waitForFunction(()=>model.accounts.length===1);assert(await page.evaluate(()=>model.running));
   await page.locator('#select-accounts').click();await page.locator('#delete-accounts').click();await page.locator('#accept-confirm').click();await page.waitForFunction(()=>model.accounts.length===0);
   await page.locator('[data-go=settings]').click();assert.equal(await page.locator('#auth').count(),0);await page.locator('#add-account').click();await page.waitForFunction(()=>model.accounts.length===1);assert.deepEqual(await page.evaluate(()=>model.queue),[]);
   await page.evaluate(()=>navigate('accounts'));await page.locator('[data-account-action=auth]').click();await page.waitForFunction(()=>route==='settings');assert.equal(await page.locator('#auth').count(),1);
  }
  assert.deepEqual(errors,[]);
  if(process.env.BANNER_PREVIEW){
   const banner=await browser.newPage({viewport:{width:1280,height:440},deviceScaleFactor:1});
   await banner.goto(url+'/nyxor-banner.svg');await banner.screenshot({path:process.env.BANNER_PREVIEW});
  }
  console.log('16 Android screenshots; 7 routes at 320/360/390/412/768px; hold selection, cancel, uncheck-last, bulk deletion, empty-profile recovery, independent account lists, reward artwork, game filter, dropdowns and energy mode checks passed.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
