const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),source=path.resolve(root,'../android/app/src/main/assets/frontend'),target=path.join(root,'generated/ui');
fs.mkdirSync(target,{recursive:true});fs.cpSync(source,target,{recursive:true});
let html=fs.readFileSync(path.join(target,'index.html'),'utf8');
// Mobile addons have their own account bridge and navigation. Desktop keeps its native implementation.
html=html.replace('<link rel="stylesheet" href="mobile.css">','').replace('<script src="mobile-dropdowns.js"></script>','').replace('<script src="mobile-ui.js"></script>','');
html=html.replace('</head>','<link rel="stylesheet" href="desktop.css"></head>').replace('<body>','<body><div class="desktop-titlebar"><span>NYXOR</span></div>').replace('<script src="app.js"></script>','<script src="app.js"></script><script src="dropdowns.js"></script><script src="desktop-ui.js"></script>');
fs.writeFileSync(path.join(target,'index.html'),html);
for(const name of ['desktop.css','desktop-ui.js','dropdowns.js'])fs.copyFileSync(path.join(root,'ui',name),path.join(target,name));
