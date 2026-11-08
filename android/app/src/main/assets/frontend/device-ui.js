'use strict';
(() => {
 const platform = window.NyxorNative?.platform || 'android';
 if (!window.NyxorNative || demo || !['desktop','android'].includes(platform)) return;
 const desktop = platform === 'desktop';
 const tr = (ua, en) => locale === 'uk' ? ua : en;
 let state = {}, busy = false, panel, fetched = false;
 function paint() {
  if (!panel?.isConnected) return;
  const status = (name, running) => {
   const color = running === null ? '#aaa' : running ? '#a9e8cb' : '#ff9fae';
   const value = running === null ? tr('Недоступний', 'Unavailable') :
    running ? tr('Фармить', 'Farming') : tr('На паузі', 'Paused');
   return `<div class="list-row"><span>${name}</span><span style="color:${color}">● ${value}</span></div>`;
  };
  const running = Boolean(model?.any_running || model?.running || model?.accounts?.some(account => account.running));
  panel.querySelector('[data-device-states]').innerHTML =
   status('Windows', desktop ? running : state.peer?.running ?? null) +
   status('Android', desktop ? state.peer?.running ?? null : running);
  const select = panel.querySelector('select');
  if (select && select.dataset.options !== JSON.stringify(state.addresses)) {
   select.replaceChildren(...(state.addresses || []).map(address => new Option(address,address)));
   select.dataset.options = JSON.stringify(state.addresses);
  }
  if (desktop) panel.querySelector('textarea').value = state.code || '';
  panel.querySelector('[data-device-import]').disabled = busy || !state.peer || !model?.active_account_id;
  panel.querySelector('[data-device-unlink]').disabled = busy || !state.linked;
  panel.querySelector('[data-device-pair]').disabled = busy || (desktop && !select?.value);
 }
 async function execute(action, values = {}) {
  if (busy) return;
  busy = true;
  paint();
  try {
   state = await call(action, values);
   fetched = true;
  } catch (error) { toast(error.message); }
  finally { busy = false; paint(); }
 }
 function createPanel() {
  const section = document.createElement('section');
  section.id = 'nyxor-devices';
  section.className = 'list-card';
  section.style.cssText = 'padding:16px;margin-top:16px';
  section.innerHTML = `<h2>${tr('Пристрої', 'Devices')}</h2>
   <p class="hint">${tr('Підключи ПК і телефон до однієї локальної мережі. Створи код на ПК та встав його на телефоні.', 'Connect your PC and phone to the same local network. Create a code on the PC and paste it on the phone.')}</p>
   <div data-device-states></div>
   ${desktop ? '<select class="language" aria-label="IP"></select>' : ''}
   <textarea rows="2" ${desktop ? 'readonly' : ''} autocomplete="off" spellcheck="false" aria-label="${tr('Код підключення', 'Pairing code')}" style="width:100%;margin:10px 0;padding:8px;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:10px;resize:vertical"></textarea>
   <button class="secondary" data-device-pair>${desktop ? tr('Створити код', 'Create code') : tr('Підключити ПК', 'Pair PC')}</button>
   <button class="secondary" data-device-import>${desktop ? tr('Взяти налаштування з телефона', 'Use phone settings') : tr('Взяти налаштування з ПК', 'Use PC settings')}</button>
   <button class="secondary" data-device-unlink>${tr('Роз’єднати', 'Unlink')}</button>`;
  section.querySelector('[data-device-pair]').onclick = () => desktop ?
   execute('device_offer', {address:section.querySelector('select').value}) :
   execute('device_pair', {code:section.querySelector('textarea').value.trim()});
  section.querySelector('[data-device-unlink]').onclick = () => execute('device_unlink');
  section.querySelector('[data-device-import]').onclick = () => {
   if (!state.peer || !model?.active_account_id || document.querySelector('#confirm').open) return;
   const profile = state.peer.profile;
   const account_id = model.active_account_id;
   confirmAction(tr('Перенести налаштування?', 'Copy settings?'),
    tr('Списки ігор і каналів та параметри фарму обраного профілю буде замінено. Вхід у Twitch збережеться.',
       'Game and channel lists and farming options for the selected profile will be replaced. Twitch login is kept.'),
    async () => {
     try {
      model = await call('profile_import', {profile, account_id});
      render();
      toast(tr('Налаштування перенесено', 'Settings copied'));
     } catch (error) { toast(error.message); }
    });
  };
  return section;
 }
 const previous = render;
 render = function(...args) {
  previous(...args);
  if (route !== 'settings') return;
  panel ||= createPanel();
  document.querySelector('#main').append(panel);
  paint();
  if (!fetched) void execute('device_status');
 };
 setInterval(() => {
  if (route === 'settings' && !document.hidden) void execute('device_status');
 }, 12000);
})();
