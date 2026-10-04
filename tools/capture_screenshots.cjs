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
    return refresh(true);
   },language);
   await page.waitForFunction(()=>document.querySelector('.game-art img')?.naturalWidth>0);
   async function capture(name){
    await page.evaluate(()=>Promise.all(document.getAnimations().filter(a=>a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished)));
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
   await page.locator('#nav [data-go=pointsPage]').click();await page.locator('#points-order').selectOption('quiet');
   await page.locator('[data-directory=Rust]').click();await page.getByText('A quiet night',{exact:true}).waitFor();
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('points');
   await page.locator('[data-points-tab=history]').click();await page.locator('#select-history').click();
   await page.locator('[data-history-login=nightwatch]').click();
   assert.equal(await page.locator('.history-check:checked').count(),2);await capture('history');
   await page.locator('#nav [data-go=activity]').click();await page.locator('#reward-game').selectOption('Rust');
   assert.equal(await page.locator('.event').count(),2);await capture('activity');
   await page.locator('#nav [data-go=settings]').click();await page.locator('[data-setting=energy_saver]').click();
   await page.waitForFunction(()=>document.documentElement.classList.contains('energy-saver'));
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('settings');
  }
  assert.deepEqual(errors,[]);
  if(process.env.BANNER_PREVIEW){
   const banner=await browser.newPage({viewport:{width:1280,height:440},deviceScaleFactor:1});
   await banner.goto(url+'/nyxor-banner.svg');await banner.screenshot({path:process.env.BANNER_PREVIEW});
  }
  console.log('12 screenshots captured; centered moon at 320/390/768px, real game artwork, selection, filter and energy toggle checked.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
