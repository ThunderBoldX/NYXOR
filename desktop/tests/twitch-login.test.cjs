const {test}=require('node:test'),assert=require('node:assert/strict');
const {Observation,localSocket,TwitchLogin}=require('../twitch-login.cjs');
const {validate}=require('../bridge.cjs');
const headers={'Authorization':'OAuth fixturetoken','Client-Id':'kimne78kx3ncx6brgo4mv6wki5h1ko','Client-Integrity':'fixtureproof','X-Device-Id':'fixturedevice','Cookie':'private-cookie','Unexpected':'ignore'};
test('Only issued proof plus a successful protected catalog produces a login context',()=>{
 const seen=new Observation();seen.request('1','https://gql.twitch.tv/gql',headers);
 assert.equal(seen.bundle('Chrome'),null);
 seen.body('proof','https://gql.twitch.tv/integrity',{token:'fixtureproof',expiration:Date.now()+3600000});
 seen.body('1','https://gql.twitch.tv/gql',{data:{currentUser:{dropCampaigns:null}}});
 assert.equal(seen.bundle('Chrome'),null);
 seen.body('1','https://gql.twitch.tv/gql',{errors:[{message:'failed'}],data:{currentUser:{dropCampaigns:[]}}});
 assert.equal(seen.bundle('Chrome'),null);
 seen.body('1','https://gql.twitch.tv/gql',[{data:{currentUser:{dropCampaigns:[]}}}]);
 const context=seen.bundle('Chrome');assert.equal(context.headers.authorization,'OAuth fixturetoken');
 assert.equal(context.headers.cookie,undefined);assert.equal(context.headers.unexpected,undefined);
 context.expires_at=0;seen.issued.set('fixtureproof',0);assert.equal(seen.bundle('Chrome'),null);
});
test('No capture from foreign URLs, client IDs or expired proof',()=>{
 const seen=new Observation();seen.request('1','https://example.com',headers);assert.equal(seen.requests.size,0);
 seen.request('2','https://gql.twitch.tv/gql',{...headers,'Client-Id':'other'});assert.equal(seen.requests.size,0);
 seen.body('proof','https://gql.twitch.tv/integrity',{token:'fixtureproof',expiration:Date.now()-1});assert.equal(seen.issued.size,0);
});
test('A cached previously issued proof still requires a fresh successful catalog response',()=>{
 const previous={headers:{'client-id':headers['Client-Id'],'client-integrity':'fixtureproof'},expires_at:Date.now()/1000+3600};
 const seen=new Observation(previous);assert.equal(seen.bundle('Chrome'),null);
 seen.request('fresh','https://gql.twitch.tv/gql',headers);assert.equal(seen.bundle('Chrome'),null);
 seen.body('fresh','https://gql.twitch.tv/gql',{data:{currentUser:{dropCampaigns:[]}}});assert.equal(seen.bundle('Chrome').expires_at,previous.expires_at);
 assert.equal(new Observation({...previous,expires_at:0}).issued.size,0);
});
test('Farming reuses a valid saved context without a browser; expiry never launches Chrome',async()=>{
 const messages=[],login=new TwitchLogin('C:/fixture/no-browser',{request:async p=>{messages.push(p);return {ok:true,data:{}};}});
 login.accepted={headers:{'client-id':headers['Client-Id']},expires_at:Date.now()/1000+3600};
 login.launch=async()=>{throw new Error('Unexpected browser launch');};
 await login.ensure();assert.equal(login.child,undefined);assert.equal(messages.length,0);
 login.accepted.expires_at=0;await assert.rejects(login.ensure(),error=>error.code==='browser_expired');
 assert.equal(messages[0].code,'browser_expired');await assert.rejects(login.start(false),error=>error.code==='browser_expired');
 assert.equal(login.renewTimer,null);assert.equal(login.child,undefined);
});
test('Successful verified login closes the owned Chrome and schedules no automatic reopen',async()=>{
 const {EventEmitter}=require('node:events');const messages=[];
 const login=new TwitchLogin('C:/fixture/login-only',{request:async p=>{messages.push(p);return {ok:true,data:{}};}});
 const protocol=new EventEmitter(),child={exitCode:null};login.child=child;login.protocol=protocol;login.session='test';login.userAgent='Chrome';login.launch=async()=>{};
 protocol.closed=false;protocol.close=()=>{protocol.closed=true;};
 const emit=(method,params)=>protocol.emit('event',{sessionId:'test',method,params});
 protocol.command=async(method,p)=>{
  if(method==='Page.reload'){
   emit('Network.requestWillBeSent',{requestId:'catalog',request:{url:'https://gql.twitch.tv/gql',headers}});
   for(const [id,url] of [['proof','https://gql.twitch.tv/integrity'],['catalog','https://gql.twitch.tv/gql']]){emit('Network.responseReceived',{requestId:id,response:{url,status:200}});emit('Network.loadingFinished',{requestId:id});}
  }
  if(method==='Network.getResponseBody')return {body:JSON.stringify(p.requestId==='proof'?{token:'fixtureproof',expiration:Date.now()+3600000}:{data:{currentUser:{dropCampaigns:[]}}})};
  if(method==='Network.getCookies')return {cookies:[]};
  if(method==='Browser.close')child.exitCode=0;
  return {};
 };
 await login.capture(true,login.generation);assert.equal(messages[0].action,'browser_import');
 assert(protocol.closed);assert.equal(login.child,null);assert.equal(login.protocol,null);assert(login.accepted.expires_at>Date.now()/1000);assert.equal(login.renewTimer,null);
 await login.ensure();assert.equal(messages.length,1);
});
test('DevTools can only connect to the launched local browser port',()=>{
 assert.equal(localSocket('ws://127.0.0.1:1234/devtools/browser/fixture',1234),'ws://127.0.0.1:1234/devtools/browser/fixture');
 for(const url of ['wss://127.0.0.1:1234/devtools/browser/x','ws://example.com:1234/devtools/browser/x','ws://127.0.0.1:1235/devtools/browser/x','ws://user@127.0.0.1:1234/devtools/browser/x','ws://127.0.0.1:1234/other'])assert.throws(()=>localSocket(url,1234));
 for(const action of ['browser_import','browser_begin','browser_error','browser_cancel'])assert.throws(()=>validate(JSON.stringify({action,context:{authorization:'secret'}})));
});
test('Repeated login focuses the existing flow; cancellation invalidates late capture',async()=>{
 const messages=[],engine={request:async payload=>{messages.push(payload);return {ok:true,data:{}};}};
 const login=new TwitchLogin('C:/fixture/nyxor',engine);let release,focused=0;
 login.capture=async()=>new Promise(resolve=>release=resolve);login.focus=async()=>{focused++;};
 await login.start(true);await login.start(true);assert.equal(messages.length,1);assert.equal(focused,1);
 const old=login.generation;await login.close();assert(login.generation>old);release();
 assert.equal(login.work,null);assert.equal(login.accepted,null);
});
