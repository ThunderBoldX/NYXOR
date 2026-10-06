const {test}=require('node:test'),assert=require('node:assert/strict');
const {Engine,validate,twitchURL}=require('../bridge.cjs');
test('Only explicit engine and shell actions are accepted',()=>{
 assert.equal(validate('{"action":"snapshot"}').action,'snapshot');
 for(const input of ['null','[]','{"action":"exec"}','{"action":"shutdown"}','{}','invalid'])assert.throws(()=>validate(input));
 assert.throws(()=>validate(' '.repeat(65537)));
});
test('Browser links must be HTTPS on Twitch, without credentials or alternative ports',()=>{
 assert.equal(twitchURL('https://www.twitch.tv/activate'),'https://www.twitch.tv/activate');
 for(const link of ['http://twitch.tv','https://twitch.tv.example.com','https://evil@twitch.tv','https://twitch.tv:8443','file:///C:/secret','javascript:alert(1)','https://example.com'])assert.throws(()=>twitchURL(link));
});
test('Requests are matched to their IDs, engine termination rejects pending requests',async()=>{
 const code=`const r=require('readline').createInterface({input:process.stdin});r.on('line',line=>{const m=JSON.parse(line);if(m.payload.action==='shutdown')process.exit(0);if(m.payload.action==='crash')process.exit(1);if(m.payload.action!=='wait')process.stdout.write(JSON.stringify({id:m.id,response:{ok:true,data:m.payload}})+'\\n');});`;
 const engine=new Engine(process.execPath,['-e',code],{},2000);
 const results=await Promise.all([engine.request({action:'snapshot'}),engine.request({action:'queue'})]);
 assert.equal(results[0].data.action,'snapshot');assert.equal(results[1].data.action,'queue');
 const waiting=assert.rejects(engine.request({action:'wait'}),/stopped/);
 await assert.rejects(engine.request({action:'crash'}),/stopped/);await waiting;await engine.stop();
});
test('Timeout removes requests and graceful shutdown exits the process',async()=>{
 const code=`require('readline').createInterface({input:process.stdin}).on('line',l=>{if(JSON.parse(l).payload.action==='shutdown')process.exit(0)});`;
 const engine=new Engine(process.execPath,['-e',code],{},150);
 await assert.rejects(engine.request({action:'snapshot'}),/timed out/);assert.equal(engine.pending.size,0);
 await engine.stop();assert.equal(engine.dead,true);
});
