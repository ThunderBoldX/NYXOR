'use strict';
// Native Chrome owns one NYXOR profile. Never attach to the user's browser.
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process');
const {EventEmitter}=require('node:events');
const WEB_CLIENT='kimne78kx3ncx6brgo4mv6wki5h1ko',GQL='https://gql.twitch.tv/gql',INTEGRITY='https://gql.twitch.tv/integrity';
const HEADERS=new Set(['authorization','client-id','client-integrity','client-version','client-session-id','x-device-id','device-id','accept-language']);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function failure(code){const error=new Error(code);error.code=code;return error;}
function chromePath(){
 for(const base of [process.env.PROGRAMFILES,process.env['PROGRAMFILES(X86)'],process.env.LOCALAPPDATA].filter(Boolean)){
  const candidate=path.join(base,'Google/Chrome/Application/chrome.exe');if(fs.existsSync(candidate))return candidate;
 }
 throw failure('browser_missing');
}
async function availablePort(){
 const server=net.createServer();await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 const port=server.address().port;await new Promise(resolve=>server.close(resolve));return port;
}
function localSocket(value,port){
 const url=new URL(value);
 if(url.protocol!=='ws:'||url.hostname!=='127.0.0.1'||url.port!==String(port)||url.username||url.password||url.search||url.hash||!url.pathname.startsWith('/devtools/browser/'))throw failure('browser_invalid');
 return url.href;
}
class Protocol extends EventEmitter{
 constructor(socket){
  super();this.socket=socket;this.pending=new Map();this.id=0;
  socket.addEventListener('message',event=>{
   try{const message=JSON.parse(event.data);if(message.id){const item=this.pending.get(message.id);if(item){clearTimeout(item.timer);this.pending.delete(message.id);message.error?item.reject(failure('browser_invalid')):item.resolve(message.result);}}
   else this.emit('event',message);}catch{}
  });
  socket.addEventListener('close',()=>{this.closed=true;for(const item of this.pending.values()){clearTimeout(item.timer);item.reject(failure('browser_closed'));}this.pending.clear();this.emit('closed');});
 }
 static async connect(url){
  const socket=new WebSocket(url);
  await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{socket.close();reject(failure('browser_timeout'));},5000);
   socket.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
   socket.addEventListener('error',()=>{clearTimeout(timer);reject(failure('browser_closed'));},{once:true});
  });
  return new Protocol(socket);
 }
 command(method,params={},sessionId){
  if(this.closed)return Promise.reject(failure('browser_closed'));
  return new Promise((resolve,reject)=>{const id=++this.id,timer=setTimeout(()=>{this.pending.delete(id);reject(failure('browser_timeout'));},8000);this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
 }
 close(){this.socket.close();}
}
class Observation{
 constructor(){this.requests=new Map();this.responses=new Map();this.issued=new Map();this.accepted=new Set();}
 request(id,url,raw){
  if(url!==GQL)return;
  const headers=Object.fromEntries(Object.entries(raw||{}).map(([k,v])=>[k.toLowerCase(),v]).filter(([k])=>HEADERS.has(k)));
  if(headers['client-id']!==WEB_CLIENT||!/^OAuth [A-Za-z0-9_-]{1,512}$/.test(headers.authorization||'')||!headers['client-integrity'])return;
  this.requests.set(id,headers);
  if(this.requests.size>128){const oldest=this.requests.keys().next().value;this.requests.delete(oldest);this.accepted.delete(oldest);}
 }
 body(id,url,data){
  if(url===INTEGRITY&&typeof data?.token==='string'&&Number.isFinite(data.expiration)){
   const expiry=data.expiration/1000;if(expiry>Date.now()/1000+30&&expiry<Date.now()/1000+86400)this.issued.set(data.token,expiry);
   if(this.issued.size>16)this.issued.delete(this.issued.keys().next().value);
  }
  if(url===GQL&&this.requests.has(id)){
   const rows=Array.isArray(data)?data:[data];
   if(rows.some(row=>row&&!row.errors&&Array.isArray(row.data?.currentUser?.dropCampaigns)))this.accepted.add(id);
  }
 }
 bundle(userAgent){
  for(const [id,headers] of [...this.requests].reverse()){
   const expiry=this.issued.get(headers['client-integrity']);
   if(this.accepted.has(id)&&expiry>Date.now()/1000+30&&(headers['x-device-id']||headers['device-id']))return {headers,user_agent:userAgent,expires_at:expiry};
  }
  return null;
 }
}
class TwitchLogin{
 constructor(root,engine){
  this.root=path.resolve(root);this.profile=path.join(this.root,'twitch-profile');this.engine=engine;
  this.generation=0;this.accepted=null;this.renewTimer=null;
 }
 async status(code){return this.engine.request({action:'browser_error',code}).catch(()=>{});}
 async start(interactive=true){
  if(this.work){if(interactive)await this.focus();return;}
  const generation=++this.generation;
  if(interactive){const result=await this.engine.request({action:'browser_begin'});if(!result.ok)throw new Error(result.error);}
  this.work=this.capture(interactive,generation).catch(async error=>{if(generation===this.generation){await this.status(error.code||'browser_invalid');await this.close();}}).finally(()=>{if(generation===this.generation)this.work=null;});
  // Login runs asynchronously; the renderer receives only its public status.
 }
 async launch(interactive){
  if(this.protocol&&!this.protocol.closed){if(interactive)await this.focus();return;}
  if(fs.existsSync(path.join(this.profile,'logout-required')))await this.clearProfile();
  const executable=chromePath();fs.mkdirSync(this.profile,{recursive:true});
  const temporary=path.join(this.profile,'tmp');fs.mkdirSync(temporary,{recursive:true});
  this.port=await availablePort();
  this.child=spawn(executable,[`--user-data-dir=${this.profile}`,'--remote-debugging-address=127.0.0.1',`--remote-debugging-port=${this.port}`,
   '--no-first-run','--no-default-browser-check','--disable-background-mode','--disable-sync',...(!interactive?['--start-minimized']:[]),'--app=https://www.twitch.tv/drops/campaigns'],
   {windowsHide:true,stdio:'ignore',env:{...process.env,TMP:temporary,TEMP:temporary,TMPDIR:temporary}});
  this.child.once('error',()=>{this.spawnFailed=true;});this.spawnFailed=false;
  const deadline=Date.now()+20000;
  while(Date.now()<deadline){
   if(this.spawnFailed||this.child.exitCode!==null)throw failure('browser_closed');
   try{
    const response=await fetch(`http://127.0.0.1:${this.port}/json/version`,{redirect:'error',signal:AbortSignal.timeout(1500)});
    const data=await response.json();this.protocol=await Protocol.connect(localSocket(data.webSocketDebuggerUrl,this.port));
    const processes=await this.protocol.command('SystemInfo.getProcessInfo');
    if(!processes.processInfo?.some(info=>info.type==='browser'&&info.id===this.child.pid)){this.protocol.close();this.protocol=null;throw failure('browser_invalid');}
    const version=await this.protocol.command('Browser.getVersion');this.userAgent=version.userAgent;
    const targets=await this.protocol.command('Target.getTargets');
    const target=targets.targetInfos?.find(info=>info.type==='page'&&info.url.startsWith('https://www.twitch.tv/'));
    if(!target)throw failure('browser_invalid');
    this.target=target.targetId;const attached=await this.protocol.command('Target.attachToTarget',{targetId:this.target,flatten:true});this.session=attached.sessionId;
    return;
   }catch(error){if(error.code==='browser_invalid')throw error;this.protocol?.close();this.protocol=null;await sleep(200);}
  }
  throw failure('browser_timeout');
 }
 async focus(){
  if(!this.protocol||this.protocol.closed)return;
  const info=await this.protocol.command('Browser.getWindowForTarget',{targetId:this.target});
  await this.protocol.command('Browser.setWindowBounds',{windowId:info.windowId,bounds:{windowState:'normal'}});
  await this.protocol.command('Page.bringToFront',{},this.session);
 }
 async capture(interactive,generation){
  clearTimeout(this.renewTimer);await this.launch(interactive);
  const observation=new Observation();let pageNavigated=false;
  const protocol=this.protocol,session=this.session;
  const onEvent=event=>{
   if(event.sessionId!==session)return;
   const p=event.params||{},id=p.requestId;
   if(event.method==='Network.requestWillBeSent')observation.request(id,p.request?.url,p.request?.headers);
   if(event.method==='Network.responseReceived'&&[GQL,INTEGRITY].includes(p.response?.url)){
    observation.responses.set(id,{url:p.response.url,status:p.response.status});
    if(observation.responses.size>128)observation.responses.delete(observation.responses.keys().next().value);
   }
   if(event.method==='Network.loadingFailed')observation.responses.delete(id);
   if(event.method==='Network.loadingFinished'){
    const response=observation.responses.get(id);observation.responses.delete(id);
    if(response?.status===200)protocol.command('Network.getResponseBody',{requestId:id},session).then(body=>{
     const raw=body.base64Encoded?Buffer.from(body.body,'base64').toString('utf8'):body.body;
     if(raw.length<=4*1024*1024)observation.body(id,response.url,JSON.parse(raw));
    }).catch(()=>{});
   }
  };
  protocol.on('event',onEvent);
  try{
   await protocol.command('Network.enable',{},session);
   await protocol.command('Page.enable',{},session);
   await protocol.command('Page.reload',{},session);
   const deadline=Date.now()+(interactive?600000:30000);
   while(generation===this.generation&&Date.now()<deadline){
    if(protocol.closed||this.child.exitCode!==null)throw failure('browser_closed');
    const cookies=await protocol.command('Network.getCookies',{urls:['https://www.twitch.tv/']},session);
    const signedIn=cookies.cookies?.some(cookie=>cookie.name==='auth-token'&&cookie.value&&['twitch.tv','.twitch.tv','www.twitch.tv'].includes(cookie.domain));
    if(signedIn&&!pageNavigated){pageNavigated=true;await protocol.command('Page.navigate',{url:'https://www.twitch.tv/drops/campaigns'},session);}
    const context=observation.bundle(this.userAgent);
    if(context&&generation===this.generation){
     const response=await this.engine.request({action:'browser_import',context,renewal:!interactive});
     if(!response.ok)throw failure('browser_rejected');
     this.accepted=context;
     // Keep the owned profile minimized while active: Twitch refreshes its own proof.
     const info=await protocol.command('Browser.getWindowForTarget',{targetId:this.target});
     await protocol.command('Browser.setWindowBounds',{windowId:info.windowId,bounds:{windowState:'minimized'}});
     const delay=Math.max(30000,(context.expires_at-Date.now()/1000-90)*1000);
     this.renewTimer=setTimeout(()=>this.start(false),delay);
     return;
    }
    await sleep(750);
   }
   if(generation===this.generation)throw failure('browser_timeout');
  }finally{protocol.off('event',onEvent);}
 }
 async ensure(){
  if(this.accepted&&this.accepted.expires_at>Date.now()/1000+60&&this.protocol&&!this.protocol.closed)return;
  await this.start(false);await this.work;
  if(!this.accepted||this.accepted.expires_at<=Date.now()/1000+30||!this.protocol||this.protocol.closed)throw failure('browser_expired');
 }
 async close(){
  ++this.generation;clearTimeout(this.renewTimer);this.accepted=null;
  const protocol=this.protocol,child=this.child;this.protocol=null;this.child=null;
  if(protocol&&!protocol.closed){await protocol.command('Browser.close').catch(()=>{});protocol.close();}
  if(child&&child.exitCode===null){
   await Promise.race([new Promise(resolve=>child.once('exit',resolve)),sleep(2500)]);
   if(child.exitCode===null)child.kill();
  }
  this.work=null;
 }
 async logout(){
  await this.close();
  if(fs.existsSync(this.profile))fs.writeFileSync(path.join(this.profile,'logout-required'),'1');
  await this.clearProfile();
 }
 async clearProfile(){
  const target=path.resolve(this.profile);
  if(path.dirname(target)!==this.root||path.basename(target)!=='twitch-profile')throw failure('browser_invalid');
  await fs.promises.rm(target,{recursive:true,force:true,maxRetries:3,retryDelay:300});
 }
}
module.exports={TwitchLogin,Observation,localSocket,chromePath};
