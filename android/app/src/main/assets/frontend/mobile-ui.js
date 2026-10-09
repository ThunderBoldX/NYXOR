'use strict';
(()=>{
if(window.NyxorNative?.platform==='desktop')return;
document.documentElement.classList.add('mobile-upgrade');
Object.assign(text.uk,{accounts:'Акаунти',addAccount:'Додати акаунт',accountHint:'Окремі входи, списки, прогрес та історія. Перемикання не зупиняє фарм інших акаунтів.',mainAccount:'Основний акаунт',newAccount:'Новий акаунт',viewAccount:'Перегляд',selectedAccount:'Обраний',chooseAccount:'Вибрати',accountStartup:'Фарм після перезавантаження',farmingAccounts:'Зараз фармлять',renewing:'Поновлюємо сеанс Twitch…',disconnectAccount:'Відключити акаунт',parallelHint:'Кожен акаунт має окремий вхід і власний фарм. Більше активних акаунтів — більше пам’яті, мережевих запитів і витрат батареї.'});
Object.assign(text.en,{accounts:'Accounts',addAccount:'Add account',accountHint:'Separate logins, lists, progress and history. Switching keeps other accounts farming.',mainAccount:'Main account',newAccount:'New account',viewAccount:'Viewing',selectedAccount:'Selected',chooseAccount:'Select',accountStartup:'Farm after phone restart',farmingAccounts:'Farming now',renewing:'Renewing Twitch session…',disconnectAccount:'Disconnect account',parallelHint:'Each account has its own login and farming session. More active accounts use more memory, network traffic and battery.'});
paths.accounts=paths.account;
const desktopCall=call,desktopNavigate=navigate,accountsBaseRender=render,desktopRefresh=refresh;
let accountEpoch=0;
const accountSelection=new Set();
Object.assign(text.uk,{accountSelectHint:'Затисни картку акаунта, щоб вибрати кілька профілів.',selectAccounts:'Вибрати акаунти',deleteAccounts:'Видалити вибрані акаунти?',deleteAccountsHint:'Фарм вибраних акаунтів зупиниться. Їхні збережені входи, списки й історія будуть видалені. Інші акаунти продовжать працювати.',noAccounts:'Додай акаунт, щоб підключити Twitch і почати фарм.',claimed:'Отримано'});
Object.assign(text.en,{accountSelectHint:'Hold an account card to select several profiles.',selectAccounts:'Select accounts',deleteAccounts:'Delete selected accounts?',deleteAccountsHint:'Farming stops for the selected accounts. Their saved logins, lists and history will be deleted. Other accounts keep farming.',noAccounts:'Add an account to connect Twitch and start farming.',claimed:'Claimed'});
const demoProfiles=new Map(),demoActive={id:'default'},demoTemplate=structuredClone(demoState);
function emptyAccountState(){return {...structuredClone(demoTemplate),authenticated:false,account:'',running:false,queue:[],streamers:[],points_games:[],history:[],watched:[],events:[],state:{},stats:{},auth:{status:'idle'},auto_farm:false,settings:structuredClone(model?.settings||demoTemplate.settings)};}
if(demo)demoProfiles.set('default',structuredClone(demoState));
function demoAccountView(){
 const selected=demoProfiles.get(demoActive.id)||emptyAccountState();Object.assign(demoState,structuredClone(selected));
 return {...structuredClone(selected),active_account_id:demoActive.id,accounts:[...demoProfiles].map(([id,s])=>({id,account:s.account,authenticated:s.authenticated,running:s.running,auto_farm:s.auto_farm!==false,game:s.state?.game,channel:s.state?.channel,points:s.state?.points,drops:s.state?.active_drops||[],auth_status:s.auth?.status}))};
}
call=async function(action,values={}){
 const epoch=accountEpoch,target=values.account_id||model?.active_account_id||'default';
 if(demo){
  if(action==='account_add'){let n=demoProfiles.size+1;while(demoProfiles.has('demo-'+n))n++;const id='demo-'+n,s=emptyAccountState();demoProfiles.set(id,s);demoActive.id=id;return demoAccountView();}
  if(action==='account_delete'){for(const id of values.ids)demoProfiles.delete(id);if(!demoProfiles.has(demoActive.id))demoActive.id=demoProfiles.keys().next().value||null;return demoAccountView();}
  if(action==='account_select'){demoActive.id=target;return demoAccountView();}
  if(action==='account_autostart'){demoProfiles.get(target).auto_farm=values.enabled;return demoAccountView();}
  if(['start','restart','stop','auth','logout'].includes(action)&&target!==demoActive.id){const s=demoProfiles.get(target);if(action==='auth')throw new Error(t('demoLogin'));s.running=action==='start'||action==='restart';if(action==='logout'){s.authenticated=false;s.account='';}return demoAccountView();}
  if(action==='settings'&&'low_resource' in (values.values||{})){
   for(const s of demoProfiles.values())s.settings.low_resource=values.values.low_resource;
   demoState.settings.low_resource=values.values.low_resource;
   values={...values,values:Object.fromEntries(Object.entries(values.values).filter(([key])=>key!=='low_resource'))};
   if(!Object.keys(values.values).length)return demoAccountView();
  }
  if(action==='snapshot'&&!demoProfiles.size)return demoAccountView();
  const result=await desktopCall(action,values);
  if(result?.settings){const {accounts:unused,active_account_id:unusedId,...clean}=result;demoProfiles.set(demoActive.id,clean);return demoAccountView();}
  return result;
 }
 let result=await desktopCall(action,action==='snapshot'||action==='account_add'?values:{account_id:target,...values});if(result?.starting)result=await desktopCall('snapshot');
 if(epoch!==accountEpoch&&result?.settings&&!['account_select','account_add'].includes(action))return desktopCall('snapshot');
 return result;
};
navigate=function(r){accountSelection.clear();if(r!=='accounts')return desktopNavigate(r);historySelection.clear();route=r;clearTimeout(searchTimer);searchSeq++;suggestions=[];render(true);window.scrollTo({top:0,behavior:'instant'});};
refresh=async function(force=false){const before=model;await desktopRefresh(force);if(route==='accounts'&&JSON.stringify(before?.accounts)!==JSON.stringify(model?.accounts))render();};
function accountName(row){return row.account?'@'+row.account:t(row.id==='default'?'mainAccount':'newAccount');}
function accountsPage(){
 const selecting=accountSelection.size>0,disabled=busy||selecting?'disabled':'';
 return head('accounts')+`<p class="hint">${t('accountHint')}</p><button class="primary account-add" id="add-account" ${disabled}>${icon('plus')}${t('addAccount')}</button>${model.accounts?.length?`<p class="hint">${t('accountSelectHint')}</p><div class="history-toolbar">${selecting?`<span role="status">${t('selected')}: ${accountSelection.size}</span><button class="text-link" id="clear-account-selection" ${busy?'disabled':''}>${t('clearSelection')}</button><button class="secondary danger" id="delete-accounts" ${busy?'disabled':''}>${t('remove')}</button>`:`<button class="text-link" id="select-accounts">${t('selectAccounts')}</button>`}</div>`:`<p class="hint">${t('noAccounts')}</p>`}<div class="account-grid">${(model.accounts||[]).map(row=>{
  const selected=row.id===model.active_account_id,renewing=row.auth_status==='browser_renewing';
  return `<article class="account-card ${selected?'selected':''} ${accountSelection.has(row.id)?'marked':''}" data-account-row="${e(row.id)}" tabindex="0" aria-label="${e(accountName(row))}"><div class="account-card-head"><div class="reward-icon">${icon('account')}</div><div class="row-main"><h2>${e(accountName(row))}</h2><p class="row-sub">${selected?t('selectedAccount'):t('chooseAccount')}</p></div><span class="status ${row.running?'running':'idle'}">${renewing?t('renewing'):t(row.running?'running':'stopped')}</span>${selecting?`<input type="checkbox" class="account-check" aria-label="${e(accountName(row))}" ${accountSelection.has(row.id)?'checked':''} ${busy?'disabled':''}>`:''}</div><p class="hint">${e([row.game,row.channel].filter(v=>v&&v!=='—').join(' · ')||t(row.authenticated?'ready':'notConnected'))}</p>${row.running?`<p class="positive">${t('points')}: ${e(row.points||'—')}</p>`:''}${(row.drops||[]).map(d=>`<p class="row-sub">${e(d.drop)} · ${e(d.current)} / ${e(d.required)} ${t('min')}</p>`).join('')}${row.auth_error?`<p class="error-banner">${e(t('net_'+row.auth_error))}</p>`:''}<div class="account-controls"><button class="secondary" data-account-select="${e(row.id)}" ${selected||busy||selecting?'disabled':''}>${t('chooseAccount')}</button><button class="primary" data-account-action="${row.running?'stop':row.authenticated?'start':'auth'}" data-account-id="${e(row.id)}" ${disabled}>${icon(row.running?'stop':row.authenticated?'play':'link')}${t(row.running?'stop':row.authenticated?'start':'connect')}</button>${row.authenticated?`<button class="text-link" data-account-action="logout" data-account-id="${e(row.id)}" ${disabled}>${t('disconnectAccount')}</button>`:''}</div><label class="account-startup"><input type="checkbox" data-account-startup="${e(row.id)}" ${row.auto_farm?'checked':''} ${disabled}>${t('accountStartup')}</label></article>`;
 }).join('')}</div><p class="hint">${t('parallelHint')}</p>`;
}
render=function(animate=false){
 accountsBaseRender(animate);if(!model)return;
 const nav=$('#nav');nav.insertAdjacentHTML('beforeend',`<button class="nav-item ${route==='accounts'?'active':''}" data-go="accounts" ${route==='accounts'?'aria-current="page"':''}>${icon('accounts')}<span>${t('accounts')}</span></button>`);
 const page=$('#main>div');if(!page)return;
 if(route==='accounts')page.innerHTML=accountsPage();
 const heading=page.querySelector('.page-head>div');
 if(heading&&(model.accounts||[]).length){heading.insertAdjacentHTML('beforeend',`<label class="account-view">${t('viewAccount')}<select id="view-account" aria-label="${t('viewAccount')}" ${busy?'disabled':''}>${model.accounts.map(row=>`<option value="${e(row.id)}" ${row.id===model.active_account_id?'selected':''}>${e(accountName(row))}</option>`).join('')}</select></label>`);}
 if(route==='home'){
  const active=(model.accounts||[]).filter(row=>row.running);
  if(active.length){const strip=document.createElement('div');strip.className='farming-accounts';strip.innerHTML=`<span>${t('farmingAccounts')}</span>${active.map(row=>`<button class="pill" data-account-select="${e(row.id)}">${e(accountName(row))} · ${e(row.game&&row.game!=='—'?row.game:t('ready'))}</button>`).join('')}`;page.querySelector('.page-head').after(strip);}
 }
};
async function accountAction(action,values={}){
 if(busy)return;busy=true;if(['account_select','account_add','account_delete'].includes(action)){accountEpoch++;oldProgress.clear();directory=null;directorySeq++;directoryBusy=false;historySelection.clear();rewardGame='';searchSeq++;suggestions=[];}
 render();try{model=await call(action,values);locale=model.settings?.language||locale;if(action==='account_delete')accountSelection.clear();}catch(error){toast(error.message);}finally{busy=false;render();}
}
document.addEventListener('change',event=>{
 if(event.target.id==='view-account')accountAction('account_select',{account_id:event.target.value});
 if(event.target.dataset.accountStartup)accountAction('account_autostart',{account_id:event.target.dataset.accountStartup,enabled:event.target.checked});
});
document.addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button||button.disabled)return;
 if(button.id==='add-account')accountAction('account_add');
 if(button.dataset.accountSelect)accountAction('account_select',{account_id:button.dataset.accountSelect});
 if(button.dataset.accountAction){const action=button.dataset.accountAction,values={account_id:button.dataset.accountId};if(action==='logout')confirmAction(t('disconnectAccount'),t('logoutText'),()=>accountAction(action,values));else accountAction(action,values);}
});
if(model)render();

let accountPress=null,accountPressTimer,suppressAccountClick=0;
function cancelAccountPress(){clearTimeout(accountPressTimer);accountPress=null;}
function toggleAccount(id){accountSelection.has(id)?accountSelection.delete(id):accountSelection.add(id);render();}
document.addEventListener('pointerdown',event=>{
 const card=event.target.closest('[data-account-row]');
 if(!card||busy||event.button!==0||accountSelection.size||event.target.closest('button,input,label,a'))return;
 cancelAccountPress();accountPress={id:card.dataset.accountRow,x:event.clientX,y:event.clientY};
 accountPressTimer=setTimeout(()=>{if(!accountPress)return;const id=accountPress.id;cancelAccountPress();accountSelection.add(id);suppressAccountClick=Date.now()+900;render();},500);
});
document.addEventListener('pointermove',event=>{if(accountPress&&Math.hypot(event.clientX-accountPress.x,event.clientY-accountPress.y)>8)cancelAccountPress();});
for(const name of ['pointerup','pointercancel','scroll'])document.addEventListener(name,cancelAccountPress,{capture:true});
document.addEventListener('click',event=>{
 const card=event.target.closest('[data-account-row]');if(!card)return;
 if(Date.now()<suppressAccountClick||accountSelection.size){event.preventDefault();event.stopImmediatePropagation();if(!busy&&Date.now()>=suppressAccountClick)toggleAccount(card.dataset.accountRow);}
},true);
document.addEventListener('keydown',event=>{
 if($('#confirm').open||busy)return;
 if(event.key==='Escape'&&accountSelection.size){event.preventDefault();accountSelection.clear();render();}
 const card=event.target.closest('[data-account-row]');
 if(card&&event.target===card&&[' ','Enter'].includes(event.key)){event.preventDefault();toggleAccount(card.dataset.accountRow);}
});
document.addEventListener('click',event=>{
 const id=event.target.closest('button')?.id;if(busy)return;
 if(id==='select-accounts'&&model.accounts?.length){accountSelection.add(model.accounts[0].id);render();}
 if(id==='clear-account-selection'){accountSelection.clear();render();}
 if(id==='delete-accounts'&&accountSelection.size){
  const ids=[...accountSelection],names=model.accounts.filter(row=>accountSelection.has(row.id)).map(accountName).join(', ');
  confirmAction(t('deleteAccounts'),names+'\n\n'+t('deleteAccountsHint'),()=>accountAction('account_delete',{ids}));
  $('#accept-confirm').textContent=t('remove');
 }
});

function rewardArtURL(value){
 try{const u=new URL(value);return typeof value==='string'&&value.length<=2048&&u.protocol==='https:'&&['static-cdn.jtvnw.net','static.twitchcdn.net'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443')&&!u.hash?u.href:'';}catch{return '';}
}
function dropArt(benefit,name){const url=rewardArtURL(benefit?.image_url);return `<div class="drop-art">${icon('gift')}${url?`<img src="${e(url)}" alt="${e(benefit.name||name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`:''}</div>`;}
function dropGallery(row){const items=Array.isArray(row.benefits)&&row.benefits.length?row.benefits.slice(0,30):[{}];return `<div class="drop-gallery">${items.map(b=>`<figure>${dropArt(b,row.drop||row.claim)}${items.length>1?`<figcaption>${e(b.name||row.drop||row.claim)}</figcaption>`:''}</figure>`).join('')}</div>`;}
document.addEventListener('error',event=>{const img=event.target;if(img.matches?.('.drop-art img'))img.remove();},true);
const originalActivity=activity,originalSettings=settings;
settings=function(){return model.accounts?.length===0?head('settings')+`<div class="empty"><h2>${t('accounts')}</h2><p>${t('noAccounts')}</p><button class="primary" id="add-account">${icon('plus')}${t('addAccount')}</button></div>`:originalSettings();};
activity=function(){
 const original=originalActivity();if(activityTab!=='history')return original;
 const items=(model.history||[]).filter(row=>!rewardGame||row.game===rewardGame),start=original.indexOf('<div class="list-card">');
 if(!items.length||start<0)return original;
 return original.slice(0,start)+`<div class="claimed-grid">${items.map(row=>`<article class="claimed-card">${dropGallery(row)}<div class="claimed-details"><div class="timestamp">${e(new Date(row.timestamp).toLocaleString(locale==='uk'?'uk-UA':'en-GB',{day:'numeric',month:'short',year:'numeric'}))}</div><h2 class="event">${e(row.drop||row.claim||'Drop')}</h2><p class="row-sub">${e([row.game,row.channel].filter(Boolean).join(' · '))}</p><div class="claimed-status">${icon('check')}${t('claimed')}</div></div></article>`).join('')}</div>`;
};
const artworkRender=render;
render=function(animate=false){
 const ids=new Set((model?.accounts||[]).map(row=>row.id));for(const id of accountSelection)if(!ids.has(id))accountSelection.delete(id);
 artworkRender(animate);
 if(route==='home')document.querySelectorAll('#main .reward').forEach((card,i)=>{const row=model.state?.active_drops?.[i];if(row?.benefits?.length)card.insertAdjacentHTML('afterbegin',dropGallery(row));});
};
if(model)render();

const mobileFinalRender=render;
render=function(animate=false){window.NyxorDropdowns.close();mobileFinalRender(animate);window.NyxorDropdowns.enhance();};
const originalBack=window.nyxorBack;
window.nyxorBack=()=>{if($('#confirm').open)return originalBack();if(accountSelection.size){accountSelection.clear();render();return true;}if(window.NyxorDropdowns.isOpen()){window.NyxorDropdowns.close();return true;}return originalBack();};
const resourceRefresh=refresh;let lastMobileRefresh=0;
refresh=async function(force=false){if(!force&&(document.hidden||window.NyxorDropdowns.isOpen()||model?.settings?.energy_saver&&Date.now()-lastMobileRefresh<15000))return;lastMobileRefresh=Date.now();return resourceRefresh(force);};
if(demo)window.NyxorMobileDemo={profiles:demoProfiles,active:demoActive};
// Android device-code login belongs on the selected profile's Settings page.
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-account-action="auth"]');if(!button||button.disabled||busy)return;
 event.preventDefault();event.stopImmediatePropagation();
 const id=button.dataset.accountId;
 await accountAction('account_select',{account_id:id});navigate('settings');await accountAction('auth',{account_id:id});
},true);
if(model)render();
})();
