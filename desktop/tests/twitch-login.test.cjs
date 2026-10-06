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
