'use strict';
// A short-lived, hidden, account-owned Twitch page refreshes the real web proof.
// No external browser is launched and no proof/challenge is fabricated.
const path=require('node:path');
const {createHash}=require('node:crypto');
const {Observation}=require('./twitch-login.cjs');
const GQL='https://gql.twitch.tv/gql',INTEGRITY='https://gql.twitch.tv/integrity';
function failure(code){return Object.assign(new Error(code),{code});}
function createRenewal(root,{BrowserWindow,session,trace=()=>{}},timeout=25000){
 let window=null,cancelled=false,active=false;
 const partition='nyxor-renew-'+createHash('sha256').update(path.resolve(root)).digest('hex');
 let owned=null;
 return {
  async renew(previous){
   if(active)throw failure('browser_invalid');
   active=true;
   try{return await this._renew(previous);}
   finally{this.cancel();await this.clear().catch(()=>{});active=false;}
  },
  async _renew(previous){
   if(window)throw failure('browser_invalid');
   cancelled=false;
   const deadline=Date.now()+timeout;
   const wait=async promise=>{let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(failure('browser_timeout')),Math.max(1,deadline-Date.now()));})]);}finally{clearTimeout(timer);}};
   trace('session');owned=session.fromPartition(partition,{cache:false});
   owned.setUserAgent(previous.user_agent);
   const token=previous.headers.authorization?.match(/^OAuth ([A-Za-z0-9_-]{1,512})$/)?.[1];
   const device=previous.headers['x-device-id']||previous.headers['device-id'];
   if(!token||!device)throw failure('browser_invalid');
   trace('cookie');await wait(owned.cookies.set({url:'https://www.twitch.tv',name:'auth-token',value:token,domain:'.twitch.tv',path:'/',secure:true,httpOnly:false}));
   await wait(owned.cookies.set({url:'https://www.twitch.tv',name:'unique_id',value:device,domain:'.twitch.tv',path:'/',secure:true}));
   if(cancelled)throw failure('browser_closed');
   trace('window');window=new BrowserWindow({show:false,width:1280,height:800,webPreferences:{session:owned,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});
   const current=window,contents=current.webContents,debuggerAPI=contents.debugger;
   contents.setAudioMuted(true);contents.setWindowOpenHandler(()=>({action:'deny'}));
   contents.on('will-navigate',(event,url)=>{try{if(!['www.twitch.tv','id.twitch.tv'].includes(new URL(url).hostname))event.preventDefault();}catch{event.preventDefault();}});
   const seen=new Observation(previous);
   let timer,onMessage,onDestroyed;
   try{
    await wait(current.loadURL('about:blank'));
    trace('debugger');debuggerAPI.attach('1.3');
    await wait(debuggerAPI.sendCommand('Network.enable'));
    trace('network');return await new Promise((resolve,reject)=>{
     let done=false;
     const finish=(error,value)=>{if(done)return;done=true;error?reject(error):resolve(value);};
     timer=setTimeout(()=>finish(failure('browser_timeout')),Math.max(1,deadline-Date.now()));
     onDestroyed=()=>finish(failure('browser_closed'));current.once('closed',onDestroyed);
     onMessage=(_event,method,p)=>{
      const id=p.requestId;
      if(method==='Network.requestWillBeSent')seen.request(id,p.request?.url,p.request?.headers);
      if(method==='Network.responseReceived'&&[GQL,INTEGRITY].includes(p.response?.url)){
       seen.responses.set(id,{url:p.response.url,status:p.response.status});
       if(seen.responses.size>128)seen.responses.delete(seen.responses.keys().next().value);
      }
      if(method==='Network.loadingFailed')seen.responses.delete(id);
      if(method==='Network.loadingFinished'){
       const response=seen.responses.get(id);seen.responses.delete(id);
       if(response?.status===200)debuggerAPI.sendCommand('Network.getResponseBody',{requestId:id}).then(body=>{
        if(done)return;
        const raw=body.base64Encoded?Buffer.from(body.body,'base64').toString('utf8'):body.body;
        if(raw.length>4*1024*1024)return;
        seen.body(id,response.url,JSON.parse(raw));
        const context=seen.bundle(previous.user_agent);
        if(context){
         if(context.headers.authorization!==previous.headers.authorization)finish(failure('browser_account_changed'));
         else finish(null,context);
        }
       }).catch(()=>{});
      }
     };
     debuggerAPI.on('message',onMessage);
     current.loadURL('https://www.twitch.tv/drops/campaigns').catch(()=>finish(failure('connection')));
    });
   }finally{
    clearTimeout(timer);if(onMessage)debuggerAPI.removeListener('message',onMessage);
    if(onDestroyed)current.removeListener('closed',onDestroyed);
    if(!current.isDestroyed()){if(debuggerAPI.isAttached())debuggerAPI.detach();current.destroy();}
    if(window===current)window=null;
   }
  },
  cancel(){cancelled=true;if(window&&!window.isDestroyed())window.destroy();window=null;},
  async clear(){this.cancel();if(owned){await owned.clearStorageData();await owned.clearCache();}}
 };
}
module.exports={createRenewal};
