'use strict';
const fs=require('node:fs'),path=require('node:path'),{randomUUID}=require('node:crypto');
const {shouldStartFarming}=require('./window-options.cjs');
const ID=/^(?:default|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/;
const GLOBAL=new Set(['language','launch_on_boot','startup_mode','low_resource']);
class Accounts{
 constructor(root,factory){
  this.root=path.resolve(root);this.factory=factory;this.slots=new Map();this.file=path.join(this.root,'accounts.json');
  this.index=fs.existsSync(this.file)?JSON.parse(fs.readFileSync(this.file,'utf8')):{version:1,active:'default',preferences:null,profiles:[{id:'default',auto_farm:true}]};
  if(this.index.version!==1||!Array.isArray(this.index.profiles)||this.index.profiles.length>20
   ||this.index.profiles.some(p=>!ID.test(p.id))||new Set(this.index.profiles.map(p=>p.id)).size!==this.index.profiles.length
   ||(this.index.profiles.length?!this.index.profiles.some(p=>p.id===this.index.active):this.index.active!==null))throw new Error('Invalid NYXOR account index');
 }
 save(){fs.mkdirSync(this.root,{recursive:true});const temp=this.file+'.'+randomUUID()+'.tmp';try{fs.writeFileSync(temp,JSON.stringify(this.index));fs.renameSync(temp,this.file);}finally{if(fs.existsSync(temp))fs.unlinkSync(temp);}}
 profile(id){const profile=this.index.profiles.find(p=>p.id===id);if(!profile)throw new Error('Unknown NYXOR account');return profile;}
 get(id=this.index.active){
  const record=this.profile(id);
  if(!this.slots.has(id)){
   // Preserve the original engine and Chrome paths; new profiles never share them.
   const root=id==='default'?this.root:path.join(this.root,'accounts',id);
   const slot={id,record,root,data:null};
   const raw=this.factory(root);slot.raw=raw.engine;
   slot.engine={request:async payload=>{const result=await raw.engine.request(payload);if(result.ok&&result.data?.settings)this.observe(slot,result.data);return result;},stop:()=>raw.engine.stop(),get child(){return raw.engine.child;}};
   slot.login=raw.createLogin(slot.engine);this.slots.set(id,slot);
  }
  return this.slots.get(id);
 }
 observe(slot,data){
  slot.data=data;
  const publicIdentity={account:data.account||data.state?.account||slot.record.identity?.account||'',user_id:data.account_user_id||'',authenticated:data.authenticated===true};
  if(JSON.stringify(slot.record.identity)!==JSON.stringify(publicIdentity)){slot.record.identity=publicIdentity;this.save();}
 }
 async initialize(){
  if(!this.index.profiles.length){this.index.preferences||={language:'uk',launch_on_boot:false,startup_mode:'app',low_resource:false};return;}
  const legacy=this.get(this.index.profiles.some(p=>p.id==='default')?'default':this.index.active),result=await legacy.engine.request({action:'snapshot'});
  if(!result.ok)throw new Error(result.error);
  if(!this.index.preferences){const s=result.data.settings;this.index.preferences={language:s.language,launch_on_boot:s.launch_on_boot,startup_mode:s.startup_mode};this.save();}
  for(const slot of this.slots.values())await slot.engine.request({action:'settings',values:{low_resource:this.index.preferences.low_resource===true}});
  await this.get().engine.request({action:'snapshot'});
 }
 summaries(){return this.index.profiles.map(record=>{
  const data=this.slots.get(record.id)?.data,identity=data?.authenticated===false?{}:record.identity||{};
  return {id:record.id,account:data?.account||data?.state?.account||identity.account||'',authenticated:data?.authenticated??identity.authenticated??false,
   running:data?.running===true,auto_farm:record.auto_farm===true,auth_status:data?.auth?.status||'idle',auth_error:data?.auth?.error_code||'',
   game:data?.state?.game||'',channel:data?.state?.channel||'',mode:data?.state?.mode||'',points:data?.state?.points||'—',
   drops:(data?.state?.active_drops||[]).map(d=>({drop:d.drop,current:d.current,required:d.required})),error:data?.error||''};
 });}
 async snapshot(){
  if(this.deletion)await this.deletion.catch(()=>{});
  if(!this.index.profiles.length)return {platform:'desktop',network:'unknown',running:false,authenticated:false,account:'',account_user_id:'',auth:{status:'idle'},error:'',state:{},stats:{},queue:[],streamers:[],points_games:[],history:[],watched:[],events:[],settings:{language:'uk',auto_restart:true,energy_saver:false,channel_points:{},...this.index.preferences},active_account_id:null,accounts:[]};
  const selected=this.index.active;
  await Promise.all([...this.slots.values()].map(async slot=>{try{await slot.engine.request({action:'snapshot'});}catch{if(slot.data)slot.data={...slot.data,running:false,error:'Engine stopped. Reopen NYXOR.'};}}));
  if(selected!==this.index.active)return this.snapshot();
  const data=this.get(selected).data;if(!data)throw new Error('NYXOR account is starting');
  return {...data,settings:{...data.settings,...this.index.preferences},active_account_id:selected,accounts:this.summaries()};
 }
 async route(payload,execute){
  if(this.deletion)await this.deletion.catch(()=>{});
  const action=payload.action;
  if(action==='snapshot')return {ok:true,data:await this.snapshot()};
  if(action==='account_delete'){
   const ids=payload.ids;
   if(!Array.isArray(ids)||!ids.length||ids.length>20||new Set(ids).size!==ids.length)throw new Error('Invalid account selection');
   ids.forEach(id=>this.profile(id));
   this.deletion=this.remove(ids);
   try{await this.deletion;}finally{this.deletion=null;}
   if(this.index.active)await this.get().engine.request({action:'snapshot'});
   return {ok:true,data:await this.snapshot()};
  }
  if(action==='account_add'){
   if(this.index.profiles.length>=20)throw new Error('NYXOR supports up to 20 saved accounts');
   const record={id:randomUUID(),auto_farm:false};this.index.profiles.push(record);
   try{await this.get(record.id).engine.request({action:'settings',values:{language:this.index.preferences.language,low_resource:this.index.preferences.low_resource===true}});this.index.active=record.id;this.save();}
   catch(error){this.index.profiles=this.index.profiles.filter(p=>p!==record);throw error;}
   return {ok:true,data:await this.snapshot()};
  }
  const id=payload.account_id||this.index.active,slot=this.get(id);
  if(action==='account_select'){await slot.engine.request({action:'settings',values:{low_resource:this.index.preferences.low_resource===true}});this.index.active=id;this.save();return {ok:true,data:await this.snapshot()};}
  if(action==='account_autostart'){
   if(typeof payload.enabled!=='boolean')throw new Error('Invalid startup setting');
   slot.record.auto_farm=payload.enabled;this.save();return {ok:true,data:await this.snapshot()};
  }
  if(['start','restart'].includes(action)){
   await slot.engine.request({action:'snapshot'});
   const user=slot.data?.account_user_id;
   if(user&&this.index.profiles.some(p=>p.id!==id&&p.identity?.authenticated&&p.identity.user_id===user))throw new Error(this.index.preferences.language==='uk'?'Цей Twitch-акаунт уже доданий в іншому профілі. Відключи його повторний вхід.':'This Twitch account is already connected in another profile. Sign out of the duplicate.');
  }
  const result=await execute(slot,payload);
  if(!result.ok)return result;
  if(action==='settings'){
   const changed=Object.fromEntries(Object.entries(payload.values||{}).filter(([k])=>GLOBAL.has(k)));
   this.index.preferences={...this.index.preferences,...changed};this.save();
   if('low_resource' in changed)await Promise.all([...this.slots.values()].filter(s=>s!==slot).map(s=>s.engine.request({action:'settings',values:{low_resource:changed.low_resource}})));
  }
  // Search/directory/connection return their own shape; other operations return
  // the currently selected view, even when a background account was changed.
  if(['search','directory','check_connection','open','copy_code','background_settings','notification_settings'].includes(action))return result;
  return {ok:true,data:await this.snapshot()};
 }
 async remove(ids){
   for(const id of ids){
    const slot=this.get(id),target=id==='default'?path.join(this.root,'engine'):path.join(this.root,'accounts',id);
    const expected=id==='default'?this.root:path.join(this.root,'accounts');
    if(path.dirname(path.resolve(target))!==expected||path.basename(target)!==(id==='default'?'engine':id))throw new Error('Invalid account directory');
    // Stop only the selected profile before deleting its private data. Never
    // remove the legacy userData root: it also contains all other accounts.
    if(!slot.raw.dead&&!slot.raw.stopping)await slot.engine.request({action:'stop'});
    await slot.login.close();await slot.engine.stop();
    await slot.login.logout();
    await fs.promises.rm(target,{recursive:true,force:true,maxRetries:3,retryDelay:300});
    this.slots.delete(id);this.index.profiles=this.index.profiles.filter(p=>p.id!==id);
    if(this.index.active===id)this.index.active=this.index.profiles[0]?.id||null;
    this.save();
   }
 }
 async autostart(args,execute){
  const failures=[];
  for(const record of this.index.profiles){
   if(!record.auto_farm)continue;
   const slot=this.get(record.id);await slot.engine.request({action:'settings',values:{low_resource:this.index.preferences.low_resource===true}});await slot.engine.request({action:'snapshot'});
   if(shouldStartFarming(args,{...slot.data,settings:{...slot.data.settings,...this.index.preferences}})){
    try{const result=await this.route({action:'start',account_id:record.id},execute);if(!result.ok)throw new Error(result.error);}catch{failures.push(record.id);}
   }
  }
  return failures;
 }
 async maintain(){
  if(this.deletion)return;
  for(const slot of this.slots.values())if(slot.data?.running&&slot.data.auth_mode==='browser'){
   try{await slot.login.ensure();}catch{await slot.engine.request({action:'stop'});await slot.login.status('browser_expired');}
  }
 }
 async stopAll(){await Promise.all([...this.slots.values()].map(async slot=>{await slot.login.close();await slot.engine.stop();}));}
}
module.exports={Accounts};
