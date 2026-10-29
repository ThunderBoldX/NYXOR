'use strict';
Object.assign(text.uk,{
 about:'NYXOR 2.5.0 · iOS preview',nativeOnlyText:'Відкрий застосунок NYXOR для iPhone.',
 backgroundOptions:'Робота у фоні',bootHint:'iOS не підтримує автоматичний запуск фарму після перезавантаження.',
 backgroundHint:'Для фонового сеансу запусти фарм і вибери дроп на огляді. iOS показує системний прогрес і може перервати завдання.',
 lockHint:'Фоновий сеанс завершується після підтвердженого отримання вибраного дропу. Без нього фарм призупиняється при згортанні.',
 forceStopHint:'Якщо прибрати застосунок із перемикача програм, iOS припинить сеанс. Повернися у NYXOR, щоб почати новий.',
 energyHint:'Зменшує перевірки кампаній та оновлення екрана. Потрібні фрагменти перевіряються раз на 20 секунд. Дозвіл фонового виконання визначає iOS.',
 iosGoal:'Фармити до цього дропу у фоні',iosCancel:'Зупинити фоновий сеанс',iosActive:'Фоновий сеанс активний',
 iosFinished:'Вибраний дроп отримано. Сеанс завершено.',iosExpired:'iOS завершила фоновий сеанс. Прогрес збережений; можна почати новий.',
 iosForeground:'Зараз доступний фарм із відкритим застосунком.',iosSession:'Фоновий сеанс одного дропу',
 iosUnavailable:'Дроп більше не доступний у поточному перегляді. Сеанс зупинено.'
});
Object.assign(text.en,{
 about:'NYXOR 2.5.0 · iOS preview',nativeOnlyText:'Open the NYXOR iPhone app.',
 backgroundOptions:'Background sessions',bootHint:'iOS does not support starting farming after a reboot.',
 backgroundHint:'Start farming, then select a Drop on Overview for a background session. iOS shows system progress and may interrupt the task.',
 lockHint:'The session ends after the selected Drop is confirmed claimed. Without a session, farming pauses when the app backgrounds.',
 forceStopHint:'Removing NYXOR from the app switcher ends the session. Return to the app to start again.',
 energyHint:'Reduces campaign checks and screen updates. Required playback remains on a 20-second cadence. iOS decides whether background execution is allowed.',
 iosGoal:'Farm until this Drop in background',iosCancel:'Stop background session',iosActive:'Background session active',
 iosFinished:'Selected Drop claimed. Session completed.',iosExpired:'iOS ended the session. Progress is saved; you can start another.',
 iosForeground:'Foreground farming is available right now.',iosSession:'One-Drop background session',
 iosUnavailable:'This Drop is no longer available on the current stream. Session stopped.'
});
const iosRender=render;
render=function(animate=false){
 iosRender(animate);if(!model)return;
 const bg=model.ios_background||{};
 document.querySelectorAll('.account-startup').forEach(e=>e.remove());
 if(route==='settings'){
  for(const id of ['background-settings','notification-settings'])document.getElementById(id)?.remove();
  document.querySelector('[data-setting="launch_on_boot"]')?.closest('.list-card')?.remove();
 }
 if(route==='home'){
  const message=bg.active?'iosActive':bg.code==='completed'?'iosFinished':bg.code==='expired'?'iosExpired':bg.code==='unavailable'?'iosUnavailable':'iosForeground';
  document.querySelector('.hero')?.insertAdjacentHTML('afterend',`<section class="list-card ios-session" role="status"><strong>${t('iosSession')}</strong><p class="hint">${t(message)}</p>${bg.active&&bg.goal?`<p class="hint">${e([bg.goal.account,bg.goal.game,bg.goal.title].filter(Boolean).join(' · '))}</p>`:''}${bg.active?`<button class="secondary" id="ios-cancel">${t('iosCancel')}</button>`:''}</section>`);
  if(bg.available&&!bg.active&&model.running)document.querySelectorAll('#main .reward').forEach((card,index)=>{
   const row=model.state?.active_drops?.[index];
   if(row?.drop_id)card.insertAdjacentHTML('beforeend',`<button class="secondary ios-goal" data-ios-drop="${e(row.drop_id)}">${t('iosGoal')}</button>`);
  });
 }
};
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-ios-drop],#ios-cancel');if(!button||button.disabled)return;
 button.disabled=true;
 try{await call(button.id==='ios-cancel'?'ios_background_cancel':'ios_background_begin',button.dataset.iosDrop?{drop_id:button.dataset.iosDrop}:{});await refresh(true);}
 catch(error){toast(error.message);}finally{button.disabled=false;}
});
if(model)render();
