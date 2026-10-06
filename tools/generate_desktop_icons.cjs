// Optional asset regeneration: npm install playwright, then BROWSER_EXECUTABLE=... node this file.
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const root=path.resolve(__dirname,'../desktop/assets');
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:256,height:256},deviceScaleFactor:1});
  await page.setContent('<style>body{margin:0;background:transparent}svg{display:block}</style>'+fs.readFileSync(path.join(root,'nyxor.svg'),'utf8'));
  await page.screenshot({path:path.join(root,'nyxor.png'),omitBackground:true});
 }finally{await browser.close();}
})();
