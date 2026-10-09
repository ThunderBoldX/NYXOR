'use strict';
const {spawn}=require('node:child_process');
const readline=require('node:readline');
const ACTIONS=new Set(['snapshot','check_connection','start','stop','restart','auth','cancel_auth','logout','delete_history','queue','streamers','points_games','settings','directory','search','open','copy_code','background_settings','notification_settings','account_add','account_select','account_autostart','account_delete']);
function validate(payload){
 if(typeof payload!=='string'||Buffer.byteLength(payload)>60000)throw new Error('Invalid request');
 const data=JSON.parse(payload);
 if(!data||Array.isArray(data)||!ACTIONS.has(data.action))throw new Error('Unknown action');
 return data;
}
function twitchURL(value){
 const url=new URL(value);
 if(url.protocol!=='https:'||!['twitch.tv','www.twitch.tv','id.twitch.tv'].includes(url.hostname)||url.username||url.password||(url.port&&url.port!=='443'))throw new Error('Only secure Twitch links are allowed');
 return url.href;
}
class Engine {
 constructor(command,args,options={},timeout=40000){
  this.pending=new Map();this.counter=0;this.timeout=timeout;this.stopping=false;
  this.child=spawn(command,args,{...options,windowsHide:true,stdio:['pipe','pipe','pipe']});
  this.closed=new Promise(resolve=>this.child.once('close',resolve));
  const lines=readline.createInterface({input:this.child.stdout});
  lines.on('line',line=>{try{const result=JSON.parse(line),item=this.pending.get(result.id);if(item){clearTimeout(item.timer);this.pending.delete(result.id);item.resolve(result.response);}}catch{this.fail('The farming engine returned invalid data');}});
  // Drain private diagnostics without copying tokens or account data into log files.
  this.child.stderr.resume();
  this.child.on('error',()=>{this.dead=true;this.fail('Could not start the farming engine. Reinstall NYXOR.');});
  this.child.stdin.on('error',()=>this.fail('The farming engine is unavailable'));
  this.child.on('close',()=>{this.dead=true;this.fail('The farming engine stopped. Reopen NYXOR.');});
 }
 fail(message){for(const item of this.pending.values()){clearTimeout(item.timer);item.reject(new Error(message));}this.pending.clear();}
 request(payload){
  if(this.dead||this.stopping)return Promise.reject(new Error('The farming engine is unavailable'));
  return new Promise((resolve,reject)=>{
   const id=String(++this.counter),timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('The farming engine timed out. Please retry.'));},this.timeout);
   this.pending.set(id,{resolve,reject,timer});
   this.child.stdin.write(JSON.stringify({id,payload})+'\n',error=>{if(error){clearTimeout(timer);this.pending.delete(id);reject(new Error('The farming engine is unavailable'));}});
  });
 }
 async stop(){
  if(this.dead)return;
  this.stopping=true;
  this.child.stdin.end(JSON.stringify({id:'shutdown',payload:{action:'shutdown'}})+'\n');
  const timer=setTimeout(()=>this.child.kill(),10000);
  await this.closed;clearTimeout(timer);this.fail('NYXOR closed');
 }
}
module.exports={Engine,validate,twitchURL};
