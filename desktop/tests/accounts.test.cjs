'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Accounts}=require('../accounts.cjs');
function fixture(){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'nyxor-accounts-')),made=[];
 const factory=folder=>{
  const state={settings:{language:'uk',launch_on_boot:false,startup_mode:'farm',energy_saver:false},account:'',account_user_id:'',authenticated:false,running:false,queue:[],streamers:[],points_games:[],state:{},auth:{status:'idle'}};
  const login={close:async()=>{login.closed=true;},ensure:async()=>{login.checked=true;},work:null};
  const engine={child:{pid:made.length+1},request:async p=>{if(p.action==='settings')Object.assign(state.settings,p.values);if(['queue','streamers','points_games'].includes(p.action))state[p.action]=p.items;if(p.action==='start')state.running=true;if(p.action==='stop')state.running=false;return {ok:true,data:structuredClone(state)};},stop:async()=>{engine.closed=true;}};
  made.push({folder,state,engine,login});return {engine,createLogin:()=>login};
 };
 const manager=new Accounts(root,factory);return {root,made,manager,cleanup:()=>fs.rmSync(root,{recursive:true,force:true})};
}
const execute=(slot,p)=>slot.engine.request(p);
test('Resource mode applies to every loaded account; an expired profile pauses without opening a browser',async()=>{
 const f=fixture();try{
  await f.manager.initialize();await f.manager.route({action:'account_add'},execute);
  await f.manager.route({action:'settings',values:{low_resource:true}},execute);
  assert(f.made.every(s=>s.state.settings.low_resource));
  f.made[0].state.running=true;f.made[0].state.auth_mode='browser';f.made[1].state.running=true;
  f.made[0].login.ensure=async()=>{throw new Error('expired');};let expired=false;
  f.made[0].login.status=async code=>{expired=code==='browser_expired';};
  await f.manager.snapshot();await f.manager.maintain();assert(expired);assert(!f.made[0].state.running);assert(f.made[1].state.running);
 }finally{f.cleanup();}
});
test('Legacy data stays in place; new accounts have independent engines, queues and Chrome roots',async()=>{
 const f=fixture();try{
  await f.manager.initialize();await f.manager.route({action:'queue',items:['Rust']},execute);
  const added=await f.manager.route({action:'account_add'},execute),id=added.data.active_account_id;
  assert.notEqual(id,'default');assert.equal(f.made[0].folder,f.root);assert.equal(f.made[1].folder,path.join(f.root,'accounts',id));
  await f.manager.route({action:'queue',items:['World of Tanks']},execute);
  assert.deepEqual(f.made[0].state.queue,['Rust']);assert.deepEqual(f.made[1].state.queue,['World of Tanks']);
  f.made[0].state.authenticated=true;f.made[0].state.account='one';f.made[0].state.account_user_id='1';
  f.made[1].state.authenticated=true;f.made[1].state.account='two';f.made[1].state.account_user_id='2';
  await f.manager.snapshot();await f.manager.route({action:'start',account_id:'default'},execute);await f.manager.route({action:'start',account_id:id},execute);
  assert.equal((await f.manager.snapshot()).accounts.filter(a=>a.running).length,2);
  await f.manager.route({action:'account_select',account_id:'default'},execute);assert(f.made[1].state.running);
  await f.manager.route({action:'stop',account_id:'default'},execute);assert(!f.made[0].state.running);assert(f.made[1].state.running);
  assert.equal((await f.manager.snapshot()).active_account_id,'default');
  await f.manager.stopAll();assert(f.made.every(s=>s.engine.closed&&s.login.closed));
 }finally{f.cleanup();}
});
test('App startup preferences are shared; only opted-in accounts start farming; duplicate Twitch identities are blocked',async()=>{
 const f=fixture();try{
  await f.manager.initialize();const id=(await f.manager.route({action:'account_add'},execute)).data.active_account_id;
  for(const [i,s] of f.made.entries())Object.assign(s.state,{authenticated:true,account_user_id:String(i+1),queue:['Rust']});
  await f.manager.route({action:'settings',values:{launch_on_boot:true,startup_mode:'farm'}},execute);
  await f.manager.autostart(['--autostart'],execute);assert(f.made[0].state.running);assert(!f.made[1].state.running);
  await f.manager.route({action:'account_autostart',account_id:id,enabled:true},execute);await f.manager.autostart(['--autostart'],execute);assert(f.made[1].state.running);
  await f.manager.route({action:'stop',account_id:id},execute);f.made[1].state.account_user_id='1';await f.manager.snapshot();
  await assert.rejects(f.manager.route({action:'start',account_id:id},execute),/уже доданий/);
  const saved=JSON.parse(fs.readFileSync(path.join(f.root,'accounts.json'),'utf8'));assert.equal(saved.active,id);assert(saved.preferences.launch_on_boot);assert(saved.profiles[1].auto_farm);
  assert(!JSON.stringify(saved).includes('authorization'));
  const restored=new Accounts(f.root,()=>{throw new Error('Not started');});assert.equal(restored.index.active,id);
  await assert.rejects(f.manager.route({action:'account_select',account_id:'../../outside'},execute),/Unknown/);
 }finally{f.cleanup();}
});
test('Index cannot select arbitrary paths and summaries exclude private backend fields',async()=>{
 const f=fixture();try{
  await f.manager.initialize();f.made[0].state.private_cookie='secret';f.made[0].state.auth.headers={authorization:'secret'};
  assert(!JSON.stringify((await f.manager.snapshot()).accounts).includes('secret'));
  fs.writeFileSync(path.join(f.root,'accounts.json'),JSON.stringify({version:1,active:'default',profiles:[{id:'default'},{id:'../elsewhere'}]}));assert.throws(()=>new Accounts(f.root,()=>{}),/Invalid/);
 }finally{f.cleanup();}
});
