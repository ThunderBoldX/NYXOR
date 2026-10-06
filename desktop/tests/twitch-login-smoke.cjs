// No credentials or real user profile: launch, verify ownership, cancel and clean up.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {TwitchLogin}=require('../twitch-login.cjs');
(async()=>{
 const root=path.resolve(__dirname,'../../.local/browser-tests',`run-${Date.now()}`);fs.mkdirSync(root,{recursive:true});
 const login=new TwitchLogin(root,{request:async()=>({ok:true,data:{}})});
 try{
  await login.launch(false);
  assert(login.child.pid>0);assert(login.protocol&&!login.protocol.closed);
  const cookies=await login.protocol.command('Network.getCookies',{urls:['https://www.twitch.tv/']},login.session);
  assert(!cookies.cookies.some(cookie=>cookie.name==='auth-token'));
  const version=await login.protocol.command('Browser.getVersion');assert(version.userAgent.includes('Chrome/'));
  const child=login.child;
  await login.close();assert(child.exitCode!==null,'Owned Chrome did not exit');
  await login.logout();assert(!fs.existsSync(login.profile));
  fs.writeFileSync(path.join(root,'result.json'),JSON.stringify({ok:true,checks:['native Chrome startup','launched process ownership','separate empty profile','private local DevTools','owned browser closes','profile cleanup']},null,2));
  console.log(JSON.stringify({ok:true,result:path.join(root,'result.json')}));
 }catch(error){fs.writeFileSync(path.join(root,'result.json'),JSON.stringify({ok:false,error:error.code||error.message}));throw error;}
 finally{await login.close();}
})().catch(error=>{console.error(error.code||error.message);process.exitCode=1;});
