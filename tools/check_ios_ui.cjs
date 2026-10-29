const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),front=path.join(root,'ios/Resources/frontend');
const server=http.createServer((req,res)=>{const name=path.basename(new URL(req.url,'http://localhost').pathname)||'index.html',file=path.join(front,name);if(!fs.existsSync(file)){res.writeHead(404).end();return;}res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:402,height:800},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>window.NyxorNative={platform:'ios',onReply(){}});
  for(const language of ['uk','en']){
   await page.goto('http://127.0.0.1:'+server.address().port+'/?demo=1');await page.locator('.hero').waitFor();
   await page.evaluate(async language=>{demoState.settings.language=language;demoState.ios_background={available:true,active:false,code:'idle'};demoState.state.active_drops.forEach((d,i)=>{d.drop_id='drop-'+i;});await refresh(true);},language);
   assert.equal(await page.locator('[data-ios-drop]').count(),2);
   await page.evaluate(()=>{const original=call;call=async(action,values)=>{if(action==='ios_background_begin'){demoState.ios_background={available:true,active:true,code:'active',goal:{account:'SampleAccount',game:'Rust',title:'Reward'}};return {};}if(action==='ios_background_cancel'){demoState.ios_background.active=false;demoState.ios_background.code='cancelled';return {};}return original(action,values);};});
   await page.locator('[data-ios-drop]').first().click();await page.locator('#ios-cancel').waitFor();assert.equal(await page.locator('[data-ios-drop]').count(),0);
   assert((await page.locator('.ios-session').textContent()).includes('SampleAccount'));
   await page.locator('#ios-cancel').click();await page.locator('[data-ios-drop]').first().waitFor();
   const out=path.join(root,'.local/ios-ui',language);fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'overview.png'),fullPage:true});
   await page.evaluate(()=>navigate('settings'));assert.equal(await page.locator('[data-setting=launch_on_boot]').count(),0);assert.equal(await page.locator('#background-settings').count(),0);assert.equal(await page.locator('#notification-settings').count(),0);
   assert((await page.locator('.footer-note').textContent()).includes('iOS preview'));await page.screenshot({path:path.join(out,'settings.png'),fullPage:true});
   for(const [width,height] of [[320,700],[402,800],[874,402]]){await page.setViewportSize({width,height});for(const route of ['home','games','streamers','pointsPage','activity','settings','accounts']){await page.evaluate(route=>navigate(route),route);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),route+' overflow');assert.equal(await page.locator('.account-startup').count(),0);}}
   await page.setViewportSize({width:402,height:800});await page.evaluate(async()=>{demoState.ios_background={available:false,active:false,code:'foreground_only'};await refresh(true);navigate('home');});assert.equal(await page.locator('[data-ios-drop]').count(),0);
  }
  assert.deepEqual(errors,[]);console.log('iOS UI: two languages, 7 routes, 3 sizes, finite-goal controls, owner label, cancellation and unsupported-background fallback passed.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
