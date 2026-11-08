'use strict';
(() => {
 if (!window.NyxorNative || demo) return;
 const platform = window.NyxorNative.platform || 'android';
 if (!TARGETS[platform]) return;
 const uk = () => locale === 'uk';
 const label = (ua, en) => uk() ? ua : en;
 let release, checking = false;
 async function check(showResult) {
  if (checking) return;
  checking = true;
  try {
   const result = await call('update_check');
   release = platform === 'desktop' ? result.update : selectUpdate(result.release, result.installed, platform);
   if (release) {
    if (document.querySelector('#confirm').open) return;
    const version = release.version;
    confirmAction(label('Нова версія NYXOR', 'NYXOR update available'),
     label(`Доступна версія ${release.version}. Продовжити до встановлення?`, `Version ${release.version} is available. Continue to installation?`),
     async () => {
      try {
       if (platform === 'desktop') toast(label('Завантажую оновлення…', 'Downloading update…'));
       await call('update_install', {version});
      } catch (error) { toast(error.message); }
     });
   } else if (showResult) toast(label('Нових оновлень немає', 'No updates available'));
  } catch {
   if (showResult) toast(label('Не вдалося перевірити оновлення', 'Could not check for updates'));
  } finally { checking = false; }
 }
 const previous = render;
 render = function(...args) {
  previous(...args);
  if (route === 'settings' && !document.querySelector('#nyxor-check-updates')) {
   const button = document.createElement('button');
   button.id = 'nyxor-check-updates';
   button.className = 'secondary';
   button.textContent = label('Перевірити оновлення', 'Check for updates');
   button.onclick = () => check(true);
   document.querySelector('#main').append(button);
  }
 };
 let startupChecked = false;
 function checkOnOpen() {
  if (document.hidden || startupChecked) return;
  startupChecked = true;
  void check(false);
 }
 document.addEventListener('visibilitychange', checkOnOpen);
 setTimeout(checkOnOpen, 4000);
})();
