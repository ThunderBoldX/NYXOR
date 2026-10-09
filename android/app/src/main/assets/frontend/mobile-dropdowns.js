'use strict';
// Native selects retain their IDs and change events. The visible controls and
// portal menus share keyboard, focus and disabled-state behavior.
window.NyxorDropdowns=(()=>{
 let active=null,serial=0,typed='',typedAt=0;
 function close(restore=false){
  if(!active)return;const item=active;active=null;
  item.button.setAttribute('aria-expanded','false');item.button.removeAttribute('aria-activedescendant');
  item.menu.classList.remove('open');setTimeout(()=>item.menu.remove(),160);
  if(restore&&item.button.isConnected)item.button.focus();
 }
 function focus(index){
  if(!active)return;const options=active.options;if(!options.length)return;
  active.index=(index+options.length)%options.length;
  options.forEach((option,i)=>option.classList.toggle('focused',i===active.index));
  const option=options[active.index];active.button.setAttribute('aria-activedescendant',option.id);option.scrollIntoView({block:'nearest'});
 }
 function choose(index){
  const item=active,option=item?.options[index];if(!option)return;
  item.select.value=option.dataset.value;const selected=item.select.selectedOptions[0];item.label.textContent=selected?.textContent||'';
  close();item.select.dispatchEvent(new Event('change',{bubbles:true}));
  // A change may replace the whole page (language, account or reward filters).
  document.querySelector(`[data-dropdown-for="${CSS.escape(item.select.id)}"]`)?.focus();
 }
 function open(item){
  if(item.select.disabled)return;if(active?.button===item.button){close();return;}close();
  const menu=document.createElement('div');menu.className='dropdown-menu';menu.id='dropdown-menu-'+(++serial);menu.setAttribute('role','listbox');
  menu.setAttribute('aria-label',item.button.getAttribute('aria-label'));
  const options=[...item.select.options].filter(option=>!option.disabled).map(option=>{
   const row=document.createElement('div');row.className='dropdown-option';row.setAttribute('role','option');row.setAttribute('aria-selected',String(option.selected));row.dataset.value=option.value;row.id='dropdown-option-'+(++serial);
   const label=document.createElement('span');label.textContent=option.textContent;const tick=document.createElement('span');tick.className='dropdown-check';tick.textContent=option.selected?'✓':'';tick.setAttribute('aria-hidden','true');row.append(label,tick);menu.append(row);return row;
  });
  document.body.append(menu);
  const rect=item.button.getBoundingClientRect(),margin=12,below=innerHeight-rect.bottom-margin,above=rect.top-44;
  const up=below<Math.min(menu.scrollHeight,220)&&above>below;
  const width=Math.min(Math.max(rect.width,180),innerWidth-2*margin),maxHeight=Math.max(40,Math.min(320,up?above:below));
  menu.style.width=width+'px';menu.style.maxHeight=maxHeight+'px';menu.style.left=Math.max(margin,Math.min(rect.left,innerWidth-width-margin))+'px';
  if(up){menu.style.bottom=(innerHeight-rect.top+6)+'px';menu.style.transformOrigin='bottom center';}else menu.style.top=(rect.bottom+6)+'px';
  active={...item,menu,options,index:Math.max(0,options.findIndex(option=>option.dataset.value===item.select.value))};
  item.button.setAttribute('aria-expanded','true');item.button.setAttribute('aria-controls',menu.id);item.button.focus();
  menu.addEventListener('pointerdown',event=>event.preventDefault());
  menu.addEventListener('click',event=>{const row=event.target.closest('[role=option]');if(row&&active?.menu===menu)choose(options.indexOf(row));});
  requestAnimationFrame(()=>{if(active?.menu===menu){menu.classList.add('open');focus(active.index);}});
 }
 function enhance(){
  if(active&&!active.select.isConnected)close();
  document.querySelectorAll('#main select:not([data-enhanced])').forEach(select=>{
   select.dataset.enhanced='true';const wrapper=document.createElement('span');wrapper.className='dropdown '+select.className;
   select.before(wrapper);wrapper.append(select);select.classList.add('dropdown-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
   const button=document.createElement('button');button.type='button';button.className='dropdown-trigger';button.dataset.dropdownFor=select.id;
   const labelled=document.querySelector(`label[for="${CSS.escape(select.id)}"]`);
   button.setAttribute('role','combobox');button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');button.setAttribute('aria-label',select.getAttribute('aria-label')||labelled?.textContent||select.id);
   button.disabled=select.disabled;const label=document.createElement('span');label.className='dropdown-value';label.textContent=select.selectedOptions[0]?.textContent||'';
   const arrow=document.createElement('span');arrow.className='dropdown-arrow';arrow.setAttribute('aria-hidden','true');button.append(label,arrow);wrapper.append(button);
   const item={select,button,label};button.addEventListener('click',()=>open(item));
   if(labelled)labelled.addEventListener('click',event=>{event.preventDefault();button.focus();});
   select.addEventListener('change',()=>{label.textContent=select.selectedOptions[0]?.textContent||'';});
   button.addEventListener('keydown',event=>{
    if(select.disabled)return;
    if(['ArrowDown','ArrowUp','Home','End','Enter',' ','Escape','Tab'].includes(event.key)){
     if(event.key==='Tab'){close();return;}event.preventDefault();
     if(event.key==='Escape'){close(true);return;}
     if(!active||active.button!==button){open(item);return;}
     if(event.key==='Enter'||event.key===' ')choose(active.index);
     else focus(event.key==='Home'?0:event.key==='End'?active.options.length-1:active.index+(event.key==='ArrowUp'?-1:1));
    }else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey){
     event.preventDefault();if(!active||active.button!==button)open(item);if(!active)return;
     typed=Date.now()-typedAt>700?event.key:typed+event.key;typedAt=Date.now();
     const index=active.options.findIndex(option=>option.textContent.trim().toLocaleLowerCase().startsWith(typed.toLocaleLowerCase()));if(index>=0)focus(index);
    }
   });
  });
 }
 document.addEventListener('pointerdown',event=>{if(active&&!active.button.contains(event.target)&&!active.menu.contains(event.target))close();});
 document.addEventListener('focusin',event=>{if(active&&event.target!==active.button&&!active.menu.contains(event.target))close();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)close();});
 window.addEventListener('resize',()=>close());
 window.addEventListener('scroll',event=>{if(active&&!active.menu.contains(event.target))close();},true);
 return {enhance,close,isOpen:()=>Boolean(active)};
})();
