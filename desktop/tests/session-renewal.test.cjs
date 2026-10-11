const {test}=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {createRenewal}=require('../session-renewal.cjs');
const {TwitchLogin}=require('../twitch-login.cjs');
const WEB='kimne78kx3ncx6brgo4mv6wki5h1ko';
const context=()=>({headers:{authorization:'OAuth fixturetoken','client-id':WEB,'client-integrity':'oldproof','x-device-id':'fixturedevice'},user_agent:'Fixture Chrome',expires_at:Date.now()/1000-5});
function fixture({complete=true,otherAccount=false,cookieFailure=false}={}){
 const partitions=[],windows=[],cookies=[];let cleared=0,caches=0;
 const owned={setUserAgent(){},cookies:{set:async row=>{cookies.push(row);if(cookieFailure)throw new Error('cookie fixture failure');}},clearStorageData:async()=>{cleared++;},clearCache:async()=>{caches++;}};
 class Window extends EventEmitter{
  constructor(options){super();this.options=options;this.destroyed=false;windows.push(this);const wc=this.webContents=new EventEmitter();
   wc.setAudioMuted=value=>this.muted=value;wc.setWindowOpenHandler=fn=>this.popup=fn;
   const debug=wc.debugger=new EventEmitter();debug.attach=()=>debug.attached=true;debug.detach=()=>debug.attached=false;debug.isAttached=()=>debug.attached;
   debug.sendCommand=async(method,p)=>method==='Network.getResponseBody'?{body:JSON.stringify(p.requestId==='proof'?{token:'newproof',expiration:Date.now()+3600000}:{data:{currentUser:{dropCampaigns:[]}}})}:{};
  }
  async loadURL(url){if(url==='about:blank'||!complete)return;queueMicrotask(()=>{
   const d=this.webContents.debugger,headers={...context().headers,'client-integrity':'newproof',...(otherAccount?{authorization:'OAuth other'}:{})};
   d.emit('message',{},'Network.requestWillBeSent',{requestId:'catalog',request:{url:'https://gql.twitch.tv/gql',headers}});
   for(const [id,url] of [['proof','https://gql.twitch.tv/integrity'],['catalog','https://gql.twitch.tv/gql']]){
    d.emit('message',{},'Network.responseReceived',{requestId:id,response:{url,status:200}});d.emit('message',{},'Network.loadingFinished',{requestId:id});
   }
  });}
  isDestroyed(){return this.destroyed;}
  destroy(){if(this.destroyed)return;this.destroyed=true;this.emit('closed');}
 }
 return {deps:{BrowserWindow:Window,session:{fromPartition:(name,options)=>{partitions.push({name,options});return owned;}}},partitions,windows,cookies,get cleared(){return cleared;},get caches(){return caches;}};
}
test('Proof renewal uses a hidden, muted memory session and destroys it after verified capture',async()=>{
 const f=fixture(),helper=createRenewal('C:/profiles/one',f.deps);const fresh=await helper.renew(context());
 assert.equal(fresh.headers.authorization,'OAuth fixturetoken');assert.equal(fresh.headers['client-integrity'],'newproof');
 assert(fresh.expires_at>Date.now()/1000+3500);assert.equal(f.windows.length,1);assert.equal(f.windows[0].options.show,false);
 assert.equal(f.windows[0].options.webPreferences.nodeIntegration,false);assert(f.windows[0].muted);assert(f.windows[0].destroyed);
 assert.equal(f.partitions[0].options.cache,false);assert(!f.partitions[0].name.startsWith('persist:'));assert.equal(f.cleared,1);assert.equal(f.caches,1);
 assert.deepEqual(f.windows[0].popup(),{action:'deny'});
});
test('Accounts have independent memory partitions and mismatched identity is rejected',async()=>{
 const a=fixture(),b=fixture({otherAccount:true});await createRenewal('C:/profiles/one',a.deps).renew(context());
 await assert.rejects(createRenewal('C:/profiles/two',b.deps).renew(context()),e=>e.code==='browser_account_changed');
 assert.notEqual(a.partitions[0].name,b.partitions[0].name);assert(b.windows[0].destroyed);assert.equal(b.cleared,1);
});
test('Timeout, cancellation and setup failure always release the hidden page and cookies',async()=>{
 const f=fixture({complete:false}),helper=createRenewal('C:/profiles/one',f.deps,20);
 await assert.rejects(helper.renew(context()),e=>e.code==='browser_timeout');assert(f.windows[0].destroyed);assert.equal(f.cleared,1);
 const pending=helper.renew(context());await new Promise(resolve=>setImmediate(resolve));helper.cancel();
 await assert.rejects(pending,e=>e.code==='browser_closed');assert.equal(f.cleared,2);
 const broken=fixture({cookieFailure:true});await assert.rejects(createRenewal('C:/profiles/broken',broken.deps).renew(context()));assert.equal(broken.cleared,1);
});
test('Proactive login renewal is deduplicated and imports only a freshly verified same-account context',async()=>{
 const messages=[],previous=context();previous.expires_at=Date.now()/1000+60;let release,calls=0;
 const renewal={renew:()=>{calls++;return new Promise(resolve=>release=resolve);},cancel(){},clear:async()=>{}};
 const login=new TwitchLogin('C:/fixture/proactive',{request:async row=>{messages.push(row);return {ok:true};}},renewal);login.accepted=previous;
 const first=login.ensure(),second=login.ensure();await new Promise(resolve=>setImmediate(resolve));assert.equal(calls,1);
 release({...previous,expires_at:Date.now()/1000+3600});await Promise.all([first,second]);await login.ensure();
 assert.equal(messages.filter(row=>row.action==='browser_import').length,1);assert(messages.find(row=>row.action==='browser_import').renewal);
 assert.equal(login.child,undefined);
});
test('Cancellation discards late proof; offline renewal retains the previous saved login',async()=>{
 let release;const messages=[],renewal={renew:()=>new Promise(resolve=>release=resolve),cancel(){},clear:async()=>{}};
 const login=new TwitchLogin('C:/fixture/cancel',{request:async row=>{messages.push(row);return {ok:true};}},renewal);const previous=login.accepted=context();
 const pending=login.ensure();await new Promise(resolve=>setImmediate(resolve));login.cancelRenewal();release({...previous,expires_at:Date.now()/1000+3600});await pending;
 assert.equal(messages.filter(row=>row.action==='browser_import').length,0);assert.equal(login.accepted,previous);
 renewal.renew=async()=>{throw Object.assign(new Error('offline'),{code:'connection'});};
 await assert.rejects(login.ensure(),e=>e.code==='connection');assert.equal(login.accepted,previous);
 assert(login.retryAt>Date.now());assert.equal(messages.at(-1).code,'connection');
});
test('Backend validation timeout keeps the old login and retry path',async()=>{
 const previous=context(),renewal={renew:async()=>({...previous,expires_at:Date.now()/1000+3600}),cancel(){},clear:async()=>{}};
 const login=new TwitchLogin('C:/fixture/slow-validation',{request:async row=>row.action==='browser_import'?{ok:false,error_code:'timeout'}:{ok:true}},renewal);
 login.accepted=previous;await assert.rejects(login.ensure(),e=>e.code==='connection');assert.equal(login.accepted,previous);assert(login.retryAt>Date.now());
});
