'use strict';
const {app,BrowserWindow,ipcMain,protocol,net,Menu,Tray,nativeImage,shell,clipboard,powerSaveBlocker}=require('electron');
const path=require('node:path'),fs=require('node:fs'),{pathToFileURL}=require('node:url');
const {Engine,validate,twitchURL}=require('./bridge.cjs');
const smokeArg=process.argv.find(arg=>arg.startsWith('--smoke-dir='));
const smokeDir=smokeArg?path.resolve(smokeArg.slice('--smoke-dir='.length)):null;
if(smokeDir){fs.mkdirSync(smokeDir,{recursive:true});app.setPath('userData',path.join(smokeDir,'user-data'));}
protocol.registerSchemesAsPrivileged([{scheme:'nyxor',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
let window,tray,engine,quitting=false,powerId,refreshTimer,lastSnapshot;
const ui=path.join(__dirname,'generated/ui');
function show(){window.show();window.restore();window.focus();}
function syncStatus(data){
 if(!data?.settings)return;
 lastSnapshot=data;
 const prevent=data.running&&!data.settings.energy_saver;
 if(prevent&&powerId===undefined)powerId=powerSaveBlocker.start('prevent-app-suspension');
 if(!prevent&&powerId!==undefined){powerSaveBlocker.stop(powerId);powerId=undefined;}
 if(!tray)return;
 const uk=data.settings.language==='uk';
 const game=data.state?.game,channel=data.state?.channel;
 const detail=[game,channel].filter(value=>value&&value!=='—').join(' · ');
 tray.setToolTip(('NYXOR · '+(data.running?(uk?'Працює':'Running'):(uk?'На паузі':'Paused'))+(detail?'\n'+detail:'')).slice(0,127));
 tray.setContextMenu(Menu.buildFromTemplate([
  {label:uk?'Відкрити NYXOR':'Open NYXOR',click:show},
  {label:data.running?(uk?'Зупинити фарм':'Stop farming'):(uk?'Запустити фарм':'Start farming'),click:async()=>{
   const result=await engine.request({action:data.running?'stop':'start'}).catch(error=>({ok:false,error:error.message}));
   if(result.ok)syncStatus(result.data);else{show();await window.webContents.executeJavaScript(`toast(${JSON.stringify(result.error)})`).catch(()=>{});}
  }},
  {type:'separator'},
  {label:uk?'Вийти з NYXOR':'Quit NYXOR',click:()=>app.quit()}
 ]));
}
function startup(enabled){
 if(!app.isPackaged&&enabled)throw new Error('Autostart is available after installing NYXOR');
 if(app.isPackaged&&!smokeDir){
  app.setLoginItemSettings({openAtLogin:enabled,path:process.execPath,args:['--autostart']});
  if(app.getLoginItemSettings({path:process.execPath,args:['--autostart']}).openAtLogin!==enabled)throw new Error('Windows could not update autostart. Please retry.');
 }
}
async function request(data){
 if(data.action==='open'){await shell.openExternal(twitchURL(data.url));return {ok:true,data:{}};}
 if(data.action==='copy_code'){
  const status=await engine.request({action:'snapshot'}),auth=status.data?.auth;
  if(!status.ok||auth?.status!=='pending'||auth.expires_at*1000<=Date.now())throw new Error('Request a new Twitch code first');
  clipboard.writeText(String(auth.code));return {ok:true,data:{}};
 }
 if(data.action==='background_settings'||data.action==='notification_settings'){
  await shell.openExternal(data.action==='background_settings'?'ms-settings:powersleep':'ms-settings:notifications');return {ok:true,data:{}};
 }
 const prior=lastSnapshot?.settings?.launch_on_boot===true;
 const boot=data.action==='settings'&&typeof data.values?.launch_on_boot==='boolean';
 if(boot)startup(data.values.launch_on_boot);
 let result;
 try{
  if(data.action==='restart'){result=await engine.request({action:'stop'});if(result.ok)result=await engine.request({action:'start'});}
  else result=await engine.request(data);
 }catch(error){if(boot)startup(prior);throw error;}
 if(boot&&!result.ok)startup(prior);
 if(result.ok)syncStatus(result.data);
 return result;
}
async function smoke(){
 const errors=[];
 window.webContents.on('console-message',(_event,details)=>{if(details.level==='error')errors.push(details.message);});
 try{
  await window.webContents.executeJavaScript('refresh(true)');
  const deadline=Date.now()+30000;
  while(Date.now()<deadline&&!await window.webContents.executeJavaScript('Boolean(model)'))await new Promise(resolve=>setTimeout(resolve,200));
  if(!await window.webContents.executeJavaScript('Boolean(model)'))throw new Error('UI did not receive engine state');
  const status=await request({action:'snapshot'});
  if(!status.ok||status.data.platform!=='desktop'||status.data.authenticated)throw new Error('Unexpected first launch state');
  syncStatus({...status.data,running:true,settings:{...status.data.settings,energy_saver:false}});
  if(powerId===undefined||!powerSaveBlocker.isStarted(powerId))throw new Error('Normal mode did not prevent sleep');
  syncStatus({...status.data,running:true,settings:{...status.data.settings,energy_saver:true}});
  if(powerId!==undefined)throw new Error('Energy saver did not release the power blocker');
  syncStatus(status.data);
  if(tray.isDestroyed())throw new Error('Tray was not created');
  const queue=await request({action:'queue',items:['Rust']});if(!queue.ok||queue.data.queue[0]!=='Rust')throw new Error('Queue persistence failed');
  const power=await request({action:'settings',values:{energy_saver:true,language:'en'}});if(!power.ok||!power.data.settings.energy_saver)throw new Error('Settings failed');
  const start=await request({action:'start'});if(start.ok)throw new Error('Unauthenticated farming must be blocked');
  await request({action:'queue',items:[]});
  await window.webContents.executeJavaScript("refresh(true).then(()=>navigate('settings'))");
  await new Promise(resolve=>setTimeout(resolve,600));
  fs.writeFileSync(path.join(smokeDir,'first-launch.png'),(await window.webContents.capturePage()).toPNG());
  await window.loadURL('nyxor://app/index.html?demo=1');
  await window.webContents.executeJavaScript('refresh(true)');
  while(!await window.webContents.executeJavaScript('Boolean(model)'))await new Promise(resolve=>setTimeout(resolve,150));
  await window.webContents.executeJavaScript(`demoState.settings.language='en';demoState.state.game_art_url='https://static-cdn.jtvnw.net/ttv-boxart/263490-144x192.jpg';refresh(true);`);
  await new Promise(resolve=>setTimeout(resolve,2000));
  const layout=await window.webContents.executeJavaScript(`({overflow:document.documentElement.scrollWidth>innerWidth,desktop:document.documentElement.classList.contains('desktop-app'),sidebar:document.querySelector('#nav').getBoundingClientRect().width,moon:(()=>{const b=document.querySelector('#account-button').getBoundingClientRect(),i=document.querySelector('#account-button svg').getBoundingClientRect();return Math.abs(b.top+b.height/2-i.top-i.height/2)<1})()})`);
  if(layout.overflow||!layout.desktop||!layout.moon||layout.sidebar<200)throw new Error('Desktop layout check failed: '+JSON.stringify(layout));
  fs.writeFileSync(path.join(smokeDir,'overview.png'),(await window.webContents.capturePage()).toPNG());
  for(const section of ['games','streamers','pointsPage','activity','settings']){
   await window.webContents.executeJavaScript(`navigate(${JSON.stringify(section)})`);
   await new Promise(resolve=>setTimeout(resolve,400));
   if(await window.webContents.executeJavaScript('document.documentElement.scrollWidth>innerWidth'))throw new Error(section+' overflows');
  }
  window.close();
  if(window.isDestroyed())throw new Error('Closing the window destroyed the app');
  const afterClose=await request({action:'snapshot'});
  if(!afterClose.ok)throw new Error('Closing the window stopped the engine');
  if(errors.length)throw new Error('Renderer errors: '+errors.join('; '));
  fs.writeFileSync(path.join(smokeDir,'result.json'),JSON.stringify({ok:true,layout,errors,engine:status.data.platform,checks:['persistent queue','energy setting','unauthenticated start blocked','six sections','centered moon','no horizontal overflow','tray status','close to tray keeps engine alive','normal power blocker and eco release']},null,2));
 }catch(error){fs.writeFileSync(path.join(smokeDir,'result.json'),JSON.stringify({ok:false,error:error.stack,errors},null,2));process.exitCode=1;}
 finally{app.quit();}
}
if(!app.requestSingleInstanceLock())app.quit();
else{
 app.on('second-instance',()=>{if(window)show();});
 app.whenReady().then(async()=>{
  protocol.handle('nyxor',incoming=>{
   const url=new URL(incoming.url),name=decodeURIComponent(url.pathname).replace(/^\//,'');
   if(url.host!=='app'||!['index.html','style.css','app.js','desktop.css','desktop-ui.js'].includes(name))return new Response('',{status:404});
   return net.fetch(pathToFileURL(path.join(ui,name)).href);
  });
  const dataDirectory=path.join(app.getPath('userData'),'engine');
  if(app.isPackaged)engine=new Engine(path.join(process.resourcesPath,'engine/nyxor-engine.exe'),[dataDirectory],{env:{...process.env,PYTHONUTF8:'1'}});
  else engine=new Engine(process.env.NYXOR_PYTHON||'python',[path.join(__dirname,'backend.py'),dataDirectory],{env:{...process.env,PYTHONUTF8:'1'}});
  ipcMain.handle('nyxor:request',async(event,payload)=>{
   try{
    if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!event.senderFrame.url.startsWith('nyxor://app/index.html'))throw new Error('Untrusted request');
    return await request(validate(payload));
   }catch(error){return {ok:false,error:error.message};}
  });
  window=new BrowserWindow({width:1320,height:940,minWidth:860,minHeight:640,show:false,backgroundColor:'#0c0b10',title:'NYXOR',icon:path.join(__dirname,'assets/nyxor.ico'),titleBarStyle:'hidden',titleBarOverlay:{color:'#0c0b10',symbolColor:'#c3b4d6',height:36},webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  Menu.setApplicationMenu(null);
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith('nyxor://app/index.html'))event.preventDefault();});
  window.on('close',event=>{if(!quitting){event.preventDefault();window.hide();}});
  tray=new Tray(nativeImage.createFromPath(path.join(__dirname,'assets/tray.png')));tray.on('double-click',show);
  syncStatus({running:false,settings:{language:'uk'}});
  await window.loadURL('nyxor://app/index.html');
  const initial=await engine.request({action:'snapshot'}).catch(()=>null);
  if(initial?.ok){
   syncStatus(initial.data);
   // Reconcile persisted preference with the actual installed Windows application.
   try{startup(initial.data.settings.launch_on_boot===true);}catch{}
   if(process.argv.includes('--autostart')&&initial.data.settings.launch_on_boot&&initial.data.authenticated&&(initial.data.queue.length||initial.data.streamers.length||initial.data.points_games.length)){
    const result=await request({action:'start'});if(!result.ok)show();
   }
  }
  if(smokeDir)await smoke();
  else{
   if(!process.argv.includes('--autostart'))show();
   refreshTimer=setInterval(()=>engine.request({action:'snapshot'}).then(result=>{if(result.ok)syncStatus(result.data);}).catch(()=>{
    if(powerId!==undefined){powerSaveBlocker.stop(powerId);powerId=undefined;}
    tray?.setToolTip('NYXOR · Engine stopped — reopen the app');
   }),10000);
  }
 }).catch(error=>{if(smokeDir)fs.writeFileSync(path.join(smokeDir,'result.json'),JSON.stringify({ok:false,error:error.stack}));app.quit();});
 app.on('before-quit',event=>{
  if(quitting)return;
  event.preventDefault();quitting=true;clearInterval(refreshTimer);
  if(powerId!==undefined)powerSaveBlocker.stop(powerId);
  (engine?engine.stop():Promise.resolve()).finally(()=>{tray?.destroy();app.quit();});
 });
 app.on('window-all-closed',()=>{if(quitting)app.quit();});
 app.on('activate',()=>{if(window)show();});
}
