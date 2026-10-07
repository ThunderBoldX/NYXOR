'use strict';
function displayBounds(area){
 return {x:area.x,y:area.y,width:area.width,height:area.height,
         minWidth:Math.min(860,area.width),minHeight:Math.min(640,area.height)};
}
function shouldStartFarming(args,data){
 return args.includes('--autostart')&&data?.settings?.launch_on_boot===true&&data.settings.startup_mode!=='app'
  &&data.authenticated===true&&Boolean(data.queue?.length||data.streamers?.length||data.points_games?.length);
}
module.exports={displayBounds,shouldStartFarming};
