'use strict';
const {contextBridge,ipcRenderer}=require('electron');
let reply;
contextBridge.exposeInMainWorld('NyxorNative',{
 platform:'desktop',
 onReply(callback){if(typeof callback==='function')reply=callback;},
 request(id,payload){
  if(typeof id!=='string'||typeof payload!=='string')return;
  ipcRenderer.invoke('nyxor:request',payload).then(result=>reply?.(id,result),()=>reply?.(id,{ok:false,error:'Could not communicate with NYXOR'}));
 }
});
