const {test}=require('node:test'),assert=require('node:assert/strict');
const {displayBounds,shouldStartFarming}=require('../window-options.cjs');
test('Window uses selected display, DPI and taskbar work area',()=>{
 for(const area of [{x:0,y:0,width:1920,height:1040},{x:0,y:0,width:1366,height:728},{x:0,y:0,width:1093,height:574},{x:-1280,y:40,width:1280,height:680},{x:0,y:0,width:800,height:560}]){
  const bounds=displayBounds(area);assert.equal(bounds.width,area.width);assert.equal(bounds.height,area.height);
  assert.equal(bounds.x,area.x);assert.equal(bounds.y,area.y);assert(bounds.minWidth<=area.width);assert(bounds.minHeight<=area.height);
 }
});
test('App-only startup never farms; farm mode requires startup, login and lists',()=>{
 const state={authenticated:true,settings:{launch_on_boot:true,startup_mode:'app'},queue:['World of Tanks'],streamers:[],points_games:[]};
 assert.equal(shouldStartFarming(['--autostart'],state),false);
 state.settings.startup_mode='farm';assert.equal(shouldStartFarming(['--autostart'],state),true);
 assert.equal(shouldStartFarming([],state),false);
 state.authenticated=false;assert.equal(shouldStartFarming(['--autostart'],state),false);
 state.authenticated=true;state.queue=[];assert.equal(shouldStartFarming(['--autostart'],state),false);
 state.points_games=['Rust'];assert.equal(shouldStartFarming(['--autostart'],state),true);
 state.settings.launch_on_boot=false;assert.equal(shouldStartFarming(['--autostart'],state),false);
 state.settings.launch_on_boot=true;delete state.settings.startup_mode;
 assert.equal(shouldStartFarming(['--autostart'],state),true,'Existing enabled startup preserves farm behavior');
});
