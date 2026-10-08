'use strict';
Object.assign(text.uk,{
 launchOnBoot:'Запускати разом із Windows',bootHint:'Після входу у Windows NYXOR запуститься у треї. Нижче обери, чи починати фарм автоматично. Для фарму потрібні підключений Twitch і збережені списки.',
 startupMode:'Дія після автозапуску',startupApp:'Лише запускати NYXOR',startupFarm:'Запускати NYXOR і фарм',
 background:'NYXOR працює у системному треї. Закриття вікна залишає фарм увімкненим. Щоб завершити програму, обери «Вийти з NYXOR» у треї.',
 backgroundHint:'Хрестик згортає NYXOR у трей поруч із годинником. Подвійне натискання на місяць відкриває вікно; праве — показує запуск, зупинку та вихід.',
 lockHint:'Статус гри й каналу доступний при наведенні на значок у треї. Фарм працює із заблокованим екраном, поки ПК увімкнений і підключений до інтернету.',
 forceStopHint:'Вимкнений або приспаний комп’ютер не фармить. Звичайний режим запобігає автоматичному сну під час фарму, але дозволяє вимкнення екрана.',
 energyHint:'Менше мережевих перевірок, оновлень екрана та анімацій. У цьому режимі Windows може приспати ПК, що призупинить фарм. Вимкни його для безперервної роботи.',
 batterySettings:'Налаштування живлення Windows',notificationSettings:'Сповіщення Windows',nativeOnlyText:'Цей інтерфейс підключається до ядра, вбудованого у Windows-застосунок.',about:'NYXOR 2.4.0 · Windows preview',
 net_offline:'Немає з’єднання. Перевір Wi-Fi або Ethernet.',net_dns:'Не вдалося знайти адресу Twitch. Перевір мережу, VPN та DNS.',net_tls:'Не вдалося перевірити з’єднання. Перевір час Windows та VPN.',net_connection:'Не вдалося підключитися до Twitch. Перевір мережу та доступ програми до інтернету.'
});
Object.assign(text.en,{
 launchOnBoot:'Start with Windows',bootHint:'After signing in to Windows, NYXOR starts in the tray. Choose below whether to farm automatically. Farming requires a connected Twitch account and saved lists.',
 startupMode:'After startup',startupApp:'Start NYXOR only',startupFarm:'Start NYXOR and farm',
 background:'NYXOR runs in the system tray. Closing the window keeps farming active. Choose “Quit NYXOR” in the tray to exit.',
 backgroundHint:'The close button hides NYXOR beside the clock. Double-click the moon to open it; right-click for start, stop and quit.',
 lockHint:'Hover over the tray icon for the current game and channel. Farming continues with a locked screen while your PC is awake and online.',
 forceStopHint:'Farming pauses when the PC sleeps or shuts down. Normal mode prevents automatic sleep while farming, while allowing the display to turn off.',
 energyHint:'Fewer network checks, screen updates and animations. Windows may put your PC to sleep in this mode, pausing farming. Turn it off for continuous operation.',
 batterySettings:'Windows power settings',notificationSettings:'Windows notifications',nativeOnlyText:'This interface connects to the engine built into the Windows app.',about:'NYXOR 2.4.0 · Windows preview',
 net_offline:'No connection. Check Wi-Fi or Ethernet.',net_dns:'Could not resolve Twitch’s address. Check your network, VPN and DNS.',net_tls:'Could not verify the connection. Check the Windows clock and VPN.',net_connection:'Could not connect to Twitch. Check your network and internet access for NYXOR.'
});
Object.assign(text.uk,{
 loginText:'Вхід відкриється на сайті Twitch в окремому вікні Chrome. Потрібен встановлений Google Chrome; твої звичайні вкладки залишаться окремо.',
 browserWaiting:'Увійди у Twitch у відкритому вікні. NYXOR перевірить акаунт і кампанії, а потім підключиться автоматично.',
 net_browser_missing:'Для входу потрібен Google Chrome. Встанови його й натисни «Підключити Twitch» знову.',
 net_browser_closed:'Вікно Twitch закрито. Натисни «Підключити Twitch», щоб продовжити.',
 net_browser_timeout:'Не вдалося завершити вхід вчасно. Перевір, чи підтверджено вхід на Twitch, та спробуй знову.',
 net_browser_invalid:'Не вдалося отримати підтверджений сеанс Twitch. Спробуй підключитися знову.',
 net_browser_rejected:'Twitch не підтвердив сеанс або доступ до кампаній. Підключи Twitch повторно.',
 net_browser_catalog:'Twitch не підтвердив доступ до Drops. Підключи Twitch повторно.',
 net_browser_expired:'Сеанс Twitch потребує оновлення. Підключи Twitch повторно.',
 net_browser_account_changed:'Акаунт у вікні Twitch змінився. Зупини фарм і підключи потрібний акаунт.'
});
Object.assign(text.en,{
 loginText:'Sign in on Twitch in a separate Chrome window. Google Chrome must be installed; your regular tabs stay separate.',
 browserWaiting:'Sign in to Twitch in the opened window. NYXOR checks your account and campaigns, then connects automatically.',
 net_browser_missing:'Google Chrome is required for login. Install it, then click “Connect Twitch” again.',
 net_browser_closed:'The Twitch window was closed. Click “Connect Twitch” to continue.',
 net_browser_timeout:'Login did not finish in time. Check that you approved the Twitch login, then retry.',
 net_browser_invalid:'Could not obtain a verified Twitch session. Try connecting again.',
 net_browser_rejected:'Twitch did not confirm the session or campaign access. Connect Twitch again.',
 net_browser_catalog:'Twitch did not confirm Drops access. Connect Twitch again.',
 net_browser_expired:'Your Twitch session needs refreshing. Connect Twitch again.',
 net_browser_account_changed:'The account in the Twitch window changed. Stop farming and connect the intended account.'
});
const deviceAuthContent=authContent;
authContent=function(auth){
 if(auth.status==='browser_renewing')return `<span class="loader"></span><p role="status">${t('renewing')}</p>`;
 if(auth.status==='browser_pending')return `<span class="loader"></span><p role="status">${t('browserWaiting')}</p><div class="browser-auth-actions"><button class="text-link" id="auth">${t('openTwitch')}</button><button class="text-link" id="cancel-auth">${t('cancel')}</button></div>`;
 return deviceAuthContent(auth);
};
document.addEventListener('click',async event=>{
 if(event.target.closest('#cancel-auth')){
  try{model=await call('cancel_auth');render();}catch(error){toast(error.message);}
 }
});
document.addEventListener('change',event=>{
 if(event.target.id==='startup-mode')update('settings',{values:{startup_mode:event.target.value}});
});
const desktopAccountButton=document.querySelector('#account-button');
const mobileRender=render;
render=function(animate=false){
 // Keep the actual button and its handler while #main is replaced on each render.
 document.querySelector('.topbar')?.append(desktopAccountButton);
 mobileRender(animate);
 const page=document.querySelector('#main>div');if(!page)return;
 const heading=page.querySelector('.page-head');
 if(heading){const actions=document.createElement('div');actions.className='page-actions';const status=heading.querySelector('.status');if(status)actions.append(status);actions.append(desktopAccountButton);heading.append(actions);}
 if(route==='home'){
  const metric=page.querySelector('.metric-grid'),hero=metric?.previousElementSibling;
  if(metric&&hero){const summary=document.createElement('div');summary.className='desktop-summary';hero.before(summary);summary.append(hero,metric);}
  const rewards=[...page.children].filter(element=>element.matches('.reward'));
  if(rewards.length){const grid=document.createElement('div');grid.className='reward-grid';rewards[0].before(grid);grid.append(...rewards);}
 }
 if(route==='settings'){
  const bootCard=page.querySelector('[data-setting="launch_on_boot"]')?.closest('.list-card');
  if(bootCard){const row=document.createElement('div');row.className='list-row';row.innerHTML=`<label class="settings-label" for="startup-mode">${t('startupMode')}</label><select class="language" id="startup-mode" ${model.settings.launch_on_boot?'':'disabled'}><option value="app" ${model.settings.startup_mode==='app'?'selected':''}>${t('startupApp')}</option><option value="farm" ${model.settings.startup_mode!=='app'?'selected':''}>${t('startupFarm')}</option></select>`;bootCard.append(row);}
  if(model.authenticated&&(model.auth?.error_code||model.auth?.status==='browser_pending')){
   const accountCard=page.querySelector('.list-card'),notice=document.createElement('div');
   notice.className='empty auth-card';notice.innerHTML=authContent(model.auth);accountCard?.after(notice);
  }
  const heads=[...page.children].filter(element=>element.matches('.section-head'));
  if(heads.length!==3)return;
  const children=[...page.children],account=children.slice(children.indexOf(heads[0]),children.indexOf(heads[1])),preferences=children.slice(children.indexOf(heads[1]),children.indexOf(heads[2])),background=children.slice(children.indexOf(heads[2]));
  const layout=document.createElement('div'),left=document.createElement('section'),right=document.createElement('section');layout.className='settings-layout';
  heads[0].before(layout);left.append(...preferences);right.append(...account,...background);layout.append(left,right);
 }
};
if(model)render();

Object.assign(text.uk,{accounts:'Акаунти',addAccount:'Додати акаунт',accountHint:'Окремі входи, списки, прогрес та історія. Перемикання не зупиняє фарм інших акаунтів.',mainAccount:'Основний акаунт',newAccount:'Новий акаунт',viewAccount:'Перегляд',selectedAccount:'Обраний',chooseAccount:'Вибрати',accountStartup:'Фарм при автозапуску',farmingAccounts:'Зараз фармлять',renewing:'Поновлюємо сеанс Twitch…',disconnectAccount:'Відключити акаунт',parallelHint:'Кожен активний акаунт використовує окремий процес і браузерний профіль. Більше акаунтів — більше пам’яті та мережевих запитів.'});
Object.assign(text.en,{accounts:'Accounts',addAccount:'Add account',accountHint:'Separate logins, lists, progress and history. Switching keeps other accounts farming.',mainAccount:'Main account',newAccount:'New account',viewAccount:'Viewing',selectedAccount:'Selected',chooseAccount:'Select',accountStartup:'Farm on Windows startup',farmingAccounts:'Farming now',renewing:'Renewing Twitch session…',disconnectAccount:'Disconnect account',parallelHint:'Each active account uses its own process and browser profile. More accounts use more memory and network requests.'});
paths.accounts=paths.account;
const desktopCall=call,desktopNavigate=navigate,accountsBaseRender=render,desktopRefresh=refresh;
let accountEpoch=0;
const demoProfiles=new Map(),demoActive={id:'default'};
if(demo)demoProfiles.set('default',structuredClone(demoState));
function demoAccountView(){
 const selected=demoProfiles.get(demoActive.id);Object.assign(demoState,structuredClone(selected));
 return {...structuredClone(selected),active_account_id:demoActive.id,accounts:[...demoProfiles].map(([id,s])=>({id,account:s.account,authenticated:s.authenticated,running:s.running,auto_farm:s.auto_farm!==false,game:s.state?.game,channel:s.state?.channel,points:s.state?.points,drops:s.state?.active_drops||[],auth_status:s.auth?.status}))};
}
call=async function(action,values={}){
 const epoch=accountEpoch,target=values.account_id||model?.active_account_id||'default';
 if(demo){
  if(action==='account_add'){const id='demo-'+(demoProfiles.size+1),s=structuredClone(demoProfiles.get('default'));Object.assign(s,{authenticated:false,account:'',running:false,queue:[],streamers:[],points_games:[],history:[],watched:[],events:[],state:{},stats:{},auth:{status:'idle'},auto_farm:false});demoProfiles.set(id,s);demoActive.id=id;return demoAccountView();}
  if(action==='account_select'){demoActive.id=target;return demoAccountView();}
  if(action==='account_autostart'){demoProfiles.get(target).auto_farm=values.enabled;return demoAccountView();}
  if(['start','restart','stop','auth','logout'].includes(action)&&target!==demoActive.id){const s=demoProfiles.get(target);if(action==='auth')throw new Error(t('demoLogin'));s.running=action==='start'||action==='restart';if(action==='logout'){s.authenticated=false;s.account='';}return demoAccountView();}
  const result=await desktopCall(action,values);
  if(result?.settings){const {accounts:unused,active_account_id:unusedId,...clean}=result;demoProfiles.set(demoActive.id,clean);return demoAccountView();}
  return result;
 }
 const result=await desktopCall(action,action==='snapshot'||action==='account_add'?values:{account_id:target,...values});
 if(epoch!==accountEpoch&&result?.settings&&!['account_select','account_add'].includes(action))return desktopCall('snapshot');
 return result;
};
navigate=function(r){if(r!=='accounts')return desktopNavigate(r);historySelection.clear();route=r;clearTimeout(searchTimer);searchSeq++;suggestions=[];render(true);window.scrollTo({top:0,behavior:'instant'});};
refresh=async function(force=false){const before=model;await desktopRefresh(force);if(route==='accounts'&&JSON.stringify(before?.accounts)!==JSON.stringify(model?.accounts))render();};
function accountName(row){return row.account?'@'+row.account:t(row.id==='default'?'mainAccount':'newAccount');}
function accountsPage(){
 return head('accounts')+`<p class="hint">${t('accountHint')}</p><button class="primary account-add" id="add-account" ${busy?'disabled':''}>${icon('plus')}${t('addAccount')}</button><div class="account-grid">${(model.accounts||[]).map(row=>{
  const selected=row.id===model.active_account_id,renewing=row.auth_status==='browser_renewing';
  return `<article class="account-card ${selected?'selected':''}"><div class="account-card-head"><div class="reward-icon">${icon('account')}</div><div class="row-main"><h2>${e(accountName(row))}</h2><p class="row-sub">${selected?t('selectedAccount'):t('chooseAccount')}</p></div><span class="status ${row.running?'running':'idle'}">${renewing?t('renewing'):t(row.running?'running':'stopped')}</span></div><p class="hint">${e([row.game,row.channel].filter(v=>v&&v!=='—').join(' · ')||t(row.authenticated?'ready':'notConnected'))}</p>${row.running?`<p class="positive">${t('points')}: ${e(row.points||'—')}</p>`:''}${(row.drops||[]).map(d=>`<p class="row-sub">${e(d.drop)} · ${e(d.current)} / ${e(d.required)} ${t('min')}</p>`).join('')}${row.auth_error?`<p class="error-banner">${e(t('net_'+row.auth_error))}</p>`:''}<div class="account-controls"><button class="secondary" data-account-select="${e(row.id)}" ${selected||busy?'disabled':''}>${t('chooseAccount')}</button><button class="primary" data-account-action="${row.running?'stop':row.authenticated?'start':'auth'}" data-account-id="${e(row.id)}" ${busy?'disabled':''}>${icon(row.running?'stop':row.authenticated?'play':'link')}${t(row.running?'stop':row.authenticated?'start':'connect')}</button>${row.authenticated?`<button class="text-link" data-account-action="logout" data-account-id="${e(row.id)}" ${busy?'disabled':''}>${t('disconnectAccount')}</button>`:''}</div><label class="account-startup"><input type="checkbox" data-account-startup="${e(row.id)}" ${row.auto_farm?'checked':''} ${busy?'disabled':''}>${t('accountStartup')}</label></article>`;
 }).join('')}</div><p class="hint">${t('parallelHint')}</p>`;
}
render=function(animate=false){
 accountsBaseRender(animate);if(!model)return;
 const nav=$('#nav');nav.insertAdjacentHTML('beforeend',`<button class="nav-item ${route==='accounts'?'active':''}" data-go="accounts" ${route==='accounts'?'aria-current="page"':''}>${icon('accounts')}<span>${t('accounts')}</span></button>`);
 const page=$('#main>div');if(!page)return;
 if(route==='accounts'){page.innerHTML=accountsPage();const actions=document.createElement('div');actions.className='page-actions';actions.append(desktopAccountButton);page.querySelector('.page-head').append(actions);}
 const heading=page.querySelector('.page-head>div');
 if(heading&&(model.accounts||[]).length){heading.insertAdjacentHTML('beforeend',`<label class="account-view">${t('viewAccount')}<select id="view-account" aria-label="${t('viewAccount')}" ${busy?'disabled':''}>${model.accounts.map(row=>`<option value="${e(row.id)}" ${row.id===model.active_account_id?'selected':''}>${e(accountName(row))}</option>`).join('')}</select></label>`);}
 if(route==='home'){
  const active=(model.accounts||[]).filter(row=>row.running);
  if(active.length){const strip=document.createElement('div');strip.className='farming-accounts';strip.innerHTML=`<span>${t('farmingAccounts')}</span>${active.map(row=>`<button class="pill" data-account-select="${e(row.id)}">${e(accountName(row))} · ${e(row.game&&row.game!=='—'?row.game:t('ready'))}</button>`).join('')}`;page.querySelector('.page-head').after(strip);}
 }
};
async function accountAction(action,values={}){
 if(busy)return;busy=true;if(['account_select','account_add'].includes(action)){accountEpoch++;oldProgress.clear();directory=null;directorySeq++;directoryBusy=false;historySelection.clear();rewardGame='';searchSeq++;suggestions=[];}
 render();try{model=await call(action,values);locale=model.settings?.language||locale;}catch(error){toast(error.message);}finally{busy=false;render();}
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
