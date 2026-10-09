// Uses the generated desktop UI. Run desktop/scripts/prepare-ui.cjs first.
const {chromium}=require('playwright'),http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),front=path.join(root,'desktop/generated/ui');
const server=http.createServer((request,response)=>{
 const name=path.basename(new URL(request.url,'http://localhost').pathname)||'index.html',file=path.join(front,name);
 if(!fs.existsSync(file)){response.writeHead(404).end();return;}
 response.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');response.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1060},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  // Fictional reward illustrations for demo screenshots; runtime uses Twitch's imageAssetURL.
  await page.route('https://static-cdn.jtvnw.net/nyxor-demo/*.png',async route=>{
   const hoodie=route.request().url().includes('hoodie');
   const body=`<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240"><defs><linearGradient id="a" x2="1" y2="1"><stop stop-color="#bca4ed"/><stop offset="1" stop-color="#524367"/></linearGradient><filter id="s"><feDropShadow dx="0" dy="12" stdDeviation="9" flood-opacity=".4"/></filter></defs><ellipse cx="160" cy="210" rx="98" ry="13" fill="#000" opacity=".3"/><g filter="url(#s)">${hoodie?'<path d="M120 52Q160 12 200 52L246 81 266 141 228 153 211 116 211 204 109 204 109 116 92 153 54 141 74 81Z" fill="url(#a)" stroke="#d6c6fa" stroke-width="3"/><path d="M123 51Q160 100 197 51" fill="#282032"/><path d="M138 138H183L195 177H125Z" fill="#33273f"/><path d="M158 85V117M166 85V117" stroke="#d9c7ff" stroke-width="3"/>':'<path d="M72 80 160 49 248 80V180L160 215 72 180Z" fill="url(#a)" stroke="#ccb8f2" stroke-width="3"/><path d="M72 80 160 114 248 80M160 114V215" fill="none" stroke="#dccdf5" stroke-width="3"/><path d="M92 71 178 105V198M137 57 223 91V189" fill="none" stroke="#9de3c8" stroke-width="9"/><path d="M113 137 144 149V173L113 162Z" fill="#251e2f"/>'}</g></svg>`;
   await route.fulfill({status:200,contentType:'image/svg+xml',body});
  });
  await page.addInitScript(()=>{window.NyxorNative={platform:'desktop',onReply(){}};});
  async function select(id,value){await page.locator(`[data-dropdown-for="${id}"]`).click();await page.locator(`.dropdown-menu.open [role=option][data-value="${value}"]`).click();}
  for(const language of ['en','uk']){
   const output=path.join(root,'docs/screenshots/windows',language);fs.mkdirSync(output,{recursive:true});
   await page.goto('http://127.0.0.1:'+server.address().port+'/?demo=1');await page.locator('.hero').waitFor();
   await page.evaluate(async language=>{
    demoState.settings.language=language;demoState.state.game_art_url='https://static-cdn.jtvnw.net/ttv-boxart/263490-144x192.jpg';
    demoState.watched.push({login:'nightwatch',display_name:'Nightwatch',game:'Warframe',earned:180,balance:4850,last_seen:new Date().toISOString()});
    demoState.history.push({timestamp:new Date().toISOString(),game:'Warframe',claim:'Tenno Supply Cache',channel:'Nightwatch'});
    const crate={id:'demo-crate',name:'Supply crate',image_url:'https://static-cdn.jtvnw.net/nyxor-demo/crate.png'};
    const hoodie={id:'demo-hoodie',name:'Nightfall hoodie',image_url:'https://static-cdn.jtvnw.net/nyxor-demo/hoodie.png'};
    demoState.state.active_drops[0].benefits=[crate];demoState.state.active_drops[1].benefits=[hoodie];
    demoState.history[0].benefits=[crate];demoState.history[1].benefits=[hoodie];
    await refresh(true);
   },language);
   await page.waitForFunction(()=>document.querySelector('.game-art img')?.naturalWidth>0);
   await page.waitForFunction(()=>[...document.querySelectorAll('.reward .drop-art img')].length===2&&[...document.querySelectorAll('.reward .drop-art img')].every(img=>img.naturalWidth>0));
   async function capture(name){
    await page.evaluate(()=>Promise.all(document.getAnimations().filter(animation=>animation.effect.getComputedTiming().iterations!==Infinity).map(animation=>animation.finished)));
    assert.equal(await page.locator('html').getAttribute('lang'),language);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,name+'.png'),fullPage:name==='settings'});
   }
   await capture('overview');
   await page.evaluate(async()=>{demoState.running=false;await refresh(true);});await capture('overview-paused');
   await page.evaluate(async()=>{demoState.running=true;await refresh(true);});
   await page.locator('[data-go=pointsPage]').click();await select('points-order','quiet');
   await page.locator('[data-directory=Rust]').click();await page.getByText('A quiet night',{exact:true}).waitFor();
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('points');
   await page.locator('[data-points-tab=history]').click();await page.locator('#select-history').click();
   await page.locator('[data-history-login=nightwatch]').click();assert.equal(await page.locator('.history-check:checked').count(),2);
   await capture('history');
   await page.locator('#delete-history').click();await page.locator('#accept-confirm').click();await page.waitForFunction(()=>model.watched.length===0);
   assert.equal(await page.evaluate(()=>model.streamers.length),2);
   await page.locator('[data-go=activity]').click();await select('reward-game','Rust');assert.equal(await page.locator('.event').count(),1);
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('activity');
   await page.locator('[data-go=settings]').click();await page.locator('[data-setting=energy_saver]').click();
   await page.waitForFunction(()=>document.documentElement.classList.contains('energy-saver'));
   assert(await page.locator('#startup-mode').isDisabled());
   await page.locator('[data-setting=launch_on_boot]').click();
   await page.waitForFunction(()=>!document.querySelector('#startup-mode').disabled);
   await select('startup-mode','app');await page.waitForFunction(()=>model.settings.startup_mode==='app');
   await page.locator('[data-low-resource]').click();await page.waitForFunction(()=>model.settings.low_resource===true);
   assert(await page.locator('html').evaluate(element=>element.classList.contains('low-resource')));
   await page.evaluate(async()=>{let calls=0;const original=call;call=async(...args)=>{calls++;return original(...args);};await refresh(true);const before=calls;await refresh();if(calls!==before)throw new Error('Resource mode did not throttle refresh');call=original;});
   await page.locator('#toast.visible').waitFor({state:'detached'});await capture('settings');
   await page.locator('[data-dropdown-for=language]').click();await page.locator('.dropdown-menu.open').waitFor();await capture('dropdown-language');
   await page.locator('[data-dropdown-for=language]').press('Escape');assert.equal(await page.locator('[data-dropdown-for=language]').getAttribute('aria-expanded'),'false');
   await page.locator('[data-dropdown-for=language]').press('ArrowDown');await page.locator('[data-dropdown-for=language]').press('Home');await page.locator('[data-dropdown-for=language]').press('Enter');await page.waitForFunction(()=>locale==='uk');
   if(language==='en'){await select('language','en');await page.waitForFunction(()=>locale==='en');}
   await page.evaluate(async()=>{const sample=structuredClone(demoProfiles.get('default'));sample.account='moonrunner';sample.queue=['World of Tanks'];sample.points_games=['World of Tanks'];sample.state.game='World of Tanks';sample.state.channel='TankStreamer';sample.state.points='8 100';sample.state.active_drops=[];sample.running=true;sample.auto_farm=false;demoProfiles.set('demo-2',sample);await refresh(true);});
   await page.locator('[data-go=accounts]').click();await capture('accounts');
   const firstCard=page.locator('[data-account-row=default]');
   await firstCard.locator('h2').hover();await page.mouse.down();await page.waitForTimeout(600);await page.mouse.up();
   await page.waitForFunction(()=>accountSelection.size===1);assert.equal(await page.locator('.account-check').count(),2);
   await page.waitForTimeout(950);await page.locator('[data-account-row="demo-2"] .account-check').click();assert.equal(await page.locator('.account-check:checked').count(),2);
   await capture('accounts-selection');
   await page.locator('#delete-accounts').click();await page.locator('#cancel-confirm').click();assert.equal(await page.locator('.account-card').count(),2);
   await page.locator('#clear-account-selection').click();assert.equal(await page.locator('.account-check').count(),0);
   await page.locator('#select-accounts').click();await page.locator('[data-account-row=default] .account-check').click();assert.equal(await page.locator('.account-check').count(),0);
   await page.locator('[data-dropdown-for=view-account]').click();await page.locator('.dropdown-menu.open').waitFor();await capture('dropdown-accounts');
   const popup=await page.locator('.dropdown-menu.open').boundingBox();assert(popup.x>=0&&popup.y>=36&&popup.x+popup.width<=1440&&popup.y+popup.height<=1060);
   await page.locator('[data-go=accounts]').click();assert.equal(await page.locator('[data-dropdown-for=view-account]').getAttribute('aria-expanded'),'false');
   await page.locator('[data-account-select="demo-2"]').click();await page.waitForFunction(()=>model.active_account_id==='demo-2');
   await page.locator('[data-go=games]').click();assert.deepEqual(await page.evaluate(()=>model.queue),['World of Tanks']);
   await page.locator('[data-go=accounts]').click();await page.locator('[data-account-id="demo-2"][data-account-action=stop]').click();
   await page.waitForFunction(()=>!model.accounts.find(row=>row.id==='demo-2').running);assert(await page.evaluate(()=>model.accounts.find(row=>row.id==='default').running));
   await page.locator('[data-account-id="demo-2"][data-account-action=start]').click();await page.waitForFunction(()=>model.accounts.filter(row=>row.running).length===2);
   await select('view-account','default');await page.waitForFunction(()=>model.active_account_id==='default');
   await page.locator('#add-account').click();await page.waitForFunction(()=>model.active_account_id==='demo-3');assert.deepEqual(await page.evaluate(()=>model.queue),[]);assert(!await page.evaluate(()=>model.authenticated));
   await select('view-account','default');await page.waitForFunction(()=>model.active_account_id==='default');
   for(const [width,height] of [[800,560],[860,640],[1093,574],[1366,728],[1440,900],[1920,1040]]){
    await page.setViewportSize({width,height});
    for(const route of ['home','games','streamers','pointsPage','activity','settings','accounts']){
     await page.evaluate(route=>navigate(route),route);
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overflow '+width+'/'+route);
     assert.equal(await page.locator('#account-button').count(),1);
    }
    for(const running of [true,false]){
     await page.evaluate(async running=>{demoState.running=running;await refresh(true);navigate('home');},running);
     const separate=await page.evaluate(()=>{const a=document.querySelector('#account-button').getBoundingClientRect(),s=document.querySelector('.page-head .status').getBoundingClientRect();return s.right+12<=a.left&&a.right<=innerWidth;});
     assert(separate,'Status/settings overlap at '+width+'px, running='+running);
    }
    await page.locator('#account-button').click();await page.locator('[data-dropdown-for=startup-mode]').waitFor();
    const centered=await page.locator('#account-button').evaluate(button=>{const b=button.getBoundingClientRect(),i=button.querySelector('svg').getBoundingClientRect();return Math.abs(b.top+b.height/2-i.top-i.height/2)<1&&Math.abs(b.left+b.width/2-i.left-i.width/2)<1;});assert(centered);
   }
   await page.setViewportSize({width:1440,height:1060});
   await page.evaluate(()=>navigate('accounts'));await page.locator('#select-accounts').click();
   await page.locator('[data-account-row="demo-3"] .account-check').click();
   await page.locator('#delete-accounts').click();await page.locator('#accept-confirm').click();await page.waitForFunction(()=>model.accounts.length===1);
   assert.equal(await page.evaluate(()=>model.active_account_id),'demo-2');assert.deepEqual(await page.evaluate(()=>model.queue),['World of Tanks']);
   await page.locator('#select-accounts').click();await page.locator('#delete-accounts').click();await page.locator('#accept-confirm').click();await page.waitForFunction(()=>model.accounts.length===0);
   assert.equal(await page.locator('.account-check').count(),0);
   await page.locator('[data-go=settings]').click();assert.equal(await page.locator('#auth').count(),0);await page.locator('#add-account').click();await page.waitForFunction(()=>model.accounts.length===1);assert.deepEqual(await page.evaluate(()=>model.queue),[]);
   await page.evaluate(()=>{demoState.history=[{timestamp:new Date().toISOString(),game:'Rust',claim:'No artwork yet',benefits:[{name:'Unknown',image_url:'https://evil.test/image.png'}]}];navigate('activity');return refresh(true);});
   assert.equal(await page.locator('.claimed-card .drop-art img').count(),0);assert.equal(await page.locator('.claimed-card').count(),1);
  }
  assert.deepEqual(errors,[]);console.log('20 desktop screenshots; 7 routes at 800/860/1093/1366/1440/1920px; custom dropdowns, resource mode, independent accounts, hold selection, cancel, bulk delete, last-account removal, add after empty, reward artwork and missing-image fallback checks passed.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
