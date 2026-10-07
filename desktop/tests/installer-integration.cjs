const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),app=path.join(root,'desktop/dist/win-unpacked/NYXOR.exe');
const {Engine}=require(path.join(root,'desktop/bridge.cjs'));
const ps='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe';
const base=process.env.NYXOR_DESKTOP_TEST_ROOT||path.join(root,'.local/installer-tests');fs.mkdirSync(base,{recursive:true});const testRoot=fs.mkdtempSync(path.join(base,'run-'));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const owned=new Set();
function launch(exe,args,env={}){const child=spawn(exe,args,{windowsHide:true,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});owned.add(child);child.once('close',()=>owned.delete(child));let output='';child.stdout.on('data',data=>output+=data);child.stderr.on('data',data=>output+=data);return {child,done:new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>resolve({code,output}));})};}
async function within(promise,ms){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Test timed out')),ms);})]);}finally{clearTimeout(timer);}}
function alive(pid){try{process.kill(pid,0);return true;}catch{return false;}}
(async()=>{
 const checks=[];
 const record=checks.push.bind(checks);checks.push=(...messages)=>{console.log(messages.join('\n'));return record(...messages);};
 const access=await within(launch(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'desktop/tests/installer-access.ps1'),'-TestRoot',path.join(testRoot,'access-fixtures')]).done,15000);
 assert.equal(access.code,0,access.output);checks.push('Writable/fresh/protected folder access and temporary probe cleanup');
 const data=path.join(testRoot,'update-ipc-test');fs.mkdirSync(data,{recursive:true});
 const first=launch(app,['--smoke-dir='+data,'--wait-for-update']);
 const deadline=Date.now()+20000;
 while(!fs.existsSync(path.join(data,'ready.json'))&&Date.now()<deadline)await delay(200);
 assert(fs.existsSync(path.join(data,'ready.json')),'Application did not become ready');
 const ready=JSON.parse(fs.readFileSync(path.join(data,'ready.json')));assert(alive(ready.engine));
 const quit=launch(app,['--smoke-dir='+data,'--quit-for-update']);
 assert.equal((await within(quit.done,15000)).code,0);assert.equal((await within(first.done,15000)).code,0);
 await delay(300);assert(!alive(ready.engine),'Graceful update left an orphan engine');checks.push('Update IPC exits the app and its backend');

 const fixture=path.join(testRoot,"install tests/NYXOR's app"),engineFolder=path.join(fixture,'resources/engine');
 fs.mkdirSync(fixture,{recursive:true});fs.cpSync(path.join(root,'desktop/engine/nyxor-engine'),engineFolder,{recursive:true});
 fs.copyFileSync(path.join(engineFolder,'nyxor-engine.exe'),path.join(engineFolder,'helper.exe'));
 fs.writeFileSync(path.join(fixture,'NYXOR.exe'),'');
 const helper=new Engine(path.join(engineFolder,'helper.exe'),[path.join(testRoot,'helper-data')]);
 const orphan=new Engine(path.join(engineFolder,'nyxor-engine.exe'),[path.join(testRoot,'orphan-data')]);
 try{
  assert((await helper.request({action:'snapshot'})).ok);assert((await orphan.request({action:'snapshot'})).ok);
  const env={NYXOR_INSTALL_TARGET:fixture};
  const checked=await within(launch(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'desktop/installer/processes.ps1'),'-Mode','Check'],env).done,15000);
  assert.equal(checked.code,0,checked.output);checks.push('A real orphan engine is detected');
  const compiler=process.env.NYXOR_NSIS_COMPILER;assert(compiler&&fs.existsSync(compiler),'Set NYXOR_NSIS_COMPILER to makensis.exe');
  const output=path.join(fixture,'NYXOR Setup Check.exe'),script=path.join(testRoot,'installer-check.nsi');
  fs.writeFileSync(script,`Unicode true\nName "NYXOR Installer Check"\nOutFile "${output}"\nRequestExecutionLevel user\nSilentInstall silent\n!include "LogicLib.nsh"\n!include "${path.join(root,'desktop/installer/custom.nsh')}"\nVar PowerShellPath\nSection\nReadEnvStr $INSTDIR "NYXOR_ACCESS_FIXTURE"\n\${If} $INSTDIR == ""\nStrCpy $INSTDIR "$EXEDIR"\n\${EndIf}\nStrCpy $PowerShellPath "$SYSDIR\\WindowsPowerShell\\v1.0\\powershell.exe"\n!insertmacro customCheckAppRunning\nSetErrorLevel 0\nSectionEnd\n`);
  const compiled=await within(launch(compiler,['/V2',script]).done,15000);assert.equal(compiled.code,0,compiled.output);
  const blocked=await within(launch(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'desktop/tests/installer-access.ps1'),'-TestRoot',path.join(testRoot,'native-access-fixtures'),'-NativeCheckExe',output]).done,120000);assert.equal(blocked.code,0,blocked.output);checks.push('Compiled NSIS stops on denied access before changing protected fixture');
  const checkMacro=await within(launch(output,[]).done,25000);assert.equal(checkMacro.code,0,checkMacro.output);
  await within(orphan.closed,10000);assert(alive(helper.child.pid),'Unrelated helper was stopped');
  checks.push('Compiled NSIS macro closes the real orphan and leaves unrelated processes alive');
  const noApp=await within(launch(output,[]).done,15000);assert.equal(noApp.code,0,noApp.output);
  assert((await helper.request({action:'snapshot'})).ok);checks.push('Setup itself and another process in its directory cause no false running-app warning');
  const missing=await within(launch(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'desktop/installer/processes.ps1'),'-Mode','Check'],{NYXOR_INSTALL_TARGET:path.join(testRoot,'not-installed-yet')}).done,15000);assert.equal(missing.code,1);checks.push('Fresh installation returns no running app');
 }finally{await helper.stop();await orphan.stop();}
 fs.writeFileSync(path.join(testRoot,'installer-test-result.json'),JSON.stringify({ok:true,checks},null,2));
 console.log(checks.join('\n'));
})().catch(error=>{for(const child of owned)child.kill();fs.writeFileSync(path.join(testRoot,'installer-test-result.json'),JSON.stringify({ok:false,error:error.stack},null,2));console.error(error);process.exitCode=1;});
