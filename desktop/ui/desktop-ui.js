'use strict';
Object.assign(text.uk,{
 launchOnBoot:'Запускати разом із Windows',bootHint:'Після входу у Windows NYXOR запуститься у треї та відновить фарм. Потрібні підключений Twitch та збережені списки.',
 background:'NYXOR працює у системному треї. Закриття вікна залишає фарм увімкненим. Щоб завершити програму, обери «Вийти з NYXOR» у треї.',
 backgroundHint:'Хрестик згортає NYXOR у трей поруч із годинником. Подвійне натискання на місяць відкриває вікно; праве — показує запуск, зупинку та вихід.',
 lockHint:'Статус гри й каналу доступний при наведенні на значок у треї. Фарм працює із заблокованим екраном, поки ПК увімкнений і підключений до інтернету.',
 forceStopHint:'Вимкнений або приспаний комп’ютер не фармить. Звичайний режим запобігає автоматичному сну під час фарму, але дозволяє вимкнення екрана.',
 energyHint:'Менше мережевих перевірок, оновлень екрана та анімацій. У цьому режимі Windows може приспати ПК, що призупинить фарм. Вимкни його для безперервної роботи.',
 batterySettings:'Налаштування живлення Windows',notificationSettings:'Сповіщення Windows',nativeOnlyText:'Цей інтерфейс підключається до ядра, вбудованого у Windows-застосунок.',about:'NYXOR 2.3.3 · Windows preview',
 net_offline:'Немає з’єднання. Перевір Wi-Fi або Ethernet.',net_dns:'Не вдалося знайти адресу Twitch. Перевір мережу, VPN та DNS.',net_tls:'Не вдалося перевірити з’єднання. Перевір час Windows та VPN.',net_connection:'Не вдалося підключитися до Twitch. Перевір мережу та доступ програми до інтернету.'
});
Object.assign(text.en,{
 launchOnBoot:'Start with Windows',bootHint:'After signing in to Windows, NYXOR starts in the tray and resumes farming. Requires a connected Twitch account and saved lists.',
 background:'NYXOR runs in the system tray. Closing the window keeps farming active. Choose “Quit NYXOR” in the tray to exit.',
 backgroundHint:'The close button hides NYXOR beside the clock. Double-click the moon to open it; right-click for start, stop and quit.',
 lockHint:'Hover over the tray icon for the current game and channel. Farming continues with a locked screen while your PC is awake and online.',
 forceStopHint:'Farming pauses when the PC sleeps or shuts down. Normal mode prevents automatic sleep while farming, while allowing the display to turn off.',
 energyHint:'Fewer network checks, screen updates and animations. Windows may put your PC to sleep in this mode, pausing farming. Turn it off for continuous operation.',
 batterySettings:'Windows power settings',notificationSettings:'Windows notifications',nativeOnlyText:'This interface connects to the engine built into the Windows app.',about:'NYXOR 2.3.3 · Windows preview',
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
 if(auth.status==='browser_pending')return `<span class="loader"></span><p role="status">${t('browserWaiting')}</p><div class="browser-auth-actions"><button class="text-link" id="auth">${t('openTwitch')}</button><button class="text-link" id="cancel-auth">${t('cancel')}</button></div>`;
 return deviceAuthContent(auth);
};
document.addEventListener('click',async event=>{
 if(event.target.closest('#cancel-auth')){
  try{model=await call('cancel_auth');render();}catch(error){toast(error.message);}
 }
});
const mobileRender=render;
render=function(animate=false){
 mobileRender(animate);
 const page=document.querySelector('#main>div');if(!page)return;
 if(route==='home'){
  const metric=page.querySelector('.metric-grid'),hero=metric?.previousElementSibling;
  if(metric&&hero){const summary=document.createElement('div');summary.className='desktop-summary';hero.before(summary);summary.append(hero,metric);}
  const rewards=[...page.children].filter(element=>element.matches('.reward'));
  if(rewards.length){const grid=document.createElement('div');grid.className='reward-grid';rewards[0].before(grid);grid.append(...rewards);}
 }
 if(route==='settings'){
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
