/* Motion 2.0 UI: animation browser, entrance/exit controls, element looks and film effects. MIT. */
export const EASING_LABELS=[['cubic-out','Płynna'],['quad-out','Lekka'],['quint-out','Ciężka / osiadanie'],['expo-out','Ekspresowa'],
 ['back-out','Z odbiciem'],['elastic-out','Elastyczna'],['cubic-in-out','Miękka S'],['linear','Liniowa']];
const SHADOWS=[['none','Bez cienia'],['soft','Miękki'],['lift','Uniesienie'],['glow','Poświata'],['neon','Neon'],['long','Długi cień']];
const BLENDS=[['normal','Normalny'],['screen','Rozjaśnienie'],['multiply','Mnożenie'],['overlay','Nakładka'],['soft-light','Miękkie światło'],['lighten','Jaśniejszy'],['difference','Różnica']];
const GRADES=[['none','Naturalny'],['cinematic','Kinowy'],['warm','Ciepły'],['cool','Chłodny'],['vivid','Żywy'],['faded','Wyblakły'],['mono','Czarno-biały'],['noir','Noir']];
const ENERGY={low:'SPOKOJNA',medium:'ŚREDNIA',high:'WYSOKA'};
export const FILM_PRESETS={
 clean:{name:'Czysty',fx:{grade:'none',vignette:0,grain:0,letterbox:0,transition:'none',transitionDuration:.5,motionBlur:false}},
 cinema:{name:'Kino',fx:{grade:'cinematic',vignette:.45,grain:.25,letterbox:.12,transition:'dip',transitionDuration:.6,motionBlur:true}},
 social:{name:'Rolka',fx:{grade:'vivid',vignette:.2,grain:0,letterbox:0,transition:'flash',transitionDuration:.35,motionBlur:false}},
 retro:{name:'Retro',fx:{grade:'faded',vignette:.55,grain:.6,letterbox:0,transition:'light-leak',transitionDuration:.9,motionBlur:false}},
 noir:{name:'Noir',fx:{grade:'noir',vignette:.7,grain:.45,letterbox:.1,transition:'dip',transitionDuration:.7,motionBlur:true}},
};

export function createMotionUI(ctx){
 const {getProject,selected,command,esc,toast,getMotions,getExits,getEditingPresets,rerenderLibrary,previewMotion,previewExit,previewTransition}=ctx;
 let transitionSceneId=null;
 let filter='all';
 const options=(list,value)=>list.map(([v,l])=>`<option value="${v}" ${value===v?'selected':''}>${l}</option>`).join('');
 const hex=(v,fallback)=>/^#[0-9a-fA-F]{6}$/.test(v||'')?v:fallback;
 function demoMarkup(m,i){
  if(m.kind==='kinetic'){
   const text=m.unit==='word'?['Ruch','słów']:[...'Litery'];
   return text.map((t,k)=>`<i style="--i:${k}">${esc(t)}</i>`).join(m.unit==='word'?' ':'');
  }
  return esc(['Aa →','FORMA','Cześć.'][i%3]);
 }
 function tile(m,i){
  const e=selected(),active=e?.motion?.id===m.id,blocked=e&&m.kind==='kinetic'&&!['text','caption'].includes(e.type);
  return `<button class="motion-tile ${active?'active':''}" data-motion="${m.id}" data-kind="${m.kind}" ${blocked?'aria-disabled="true" title="Tylko dla tekstu i napisów"':''}><div class="motion-art"><span class="motion-demo" data-demo="${m.id}">${demoMarkup(m,i)}</span><span class="motion-preview-label">▶ PODGLĄD</span></div><strong>${esc(m.name)}</strong><small>${esc(m.category)} · ${ENERGY[m.energy]||''}</small></button>`;
 }
 function exitTile(x){
  const active=selected()?.exit?.id===x.id;
  return `<button class="motion-tile exit-tile ${active?'active':''}" data-exit="${x.id}"><div class="motion-art"><span class="motion-demo" data-demo="${x.id}">Koniec.</span><span class="motion-preview-label">◀ WYJŚCIE</span></div><strong>${esc(x.name)}</strong><small>WYJŚCIE · ${ENERGY[x.energy]||''}</small></button>`;
 }
 function panel(){
  const motions=getMotions(),exits=getExits(),e=selected();
  const groups=[['all','Wszystkie',motions.length+exits.length],['entrance','Wejścia',motions.filter(m=>m.kind==='entrance').length],['kinetic','Tekst kinetyczny',motions.filter(m=>m.kind==='kinetic').length],['exit','Wyjścia',exits.length]];
  const list=filter==='exit'?[]:motions.filter(m=>filter==='all'||m.kind===filter),exitList=['all','exit'].includes(filter)?exits:[];
  const target=e?`<div class="motion-target">Zaznaczono: <strong>${esc(e.type==='text'||e.type==='caption'?e.text.slice(0,32):e.type)}</strong>${e.motion?` · wejście ${esc(motions.find(m=>m.id===e.motion.id)?.name||'')}`:''}${e.exit?` · wyjście ${esc(exits.find(x=>x.id===e.exit.id)?.name||'')}`:''}</div>`:'<div class="motion-target muted">Zaznacz klip na osi czasu, aby nadać mu ruch.</div>';
  return `<h2 class="panel-heading">Ruch z charakterem</h2><div class="panel-subtitle">Wejścia, tekst kinetyczny i wyjścia. Najedź, aby zobaczyć podgląd.</div>${target}<div class="motion-filters" role="group" aria-label="Rodzaj ruchu">${groups.map(([id,n,c])=>`<button data-motion-filter="${id}" class="${filter===id?'active':''}" aria-pressed="${filter===id}">${n}<span>${c}</span></button>`).join('')}</div>`+
   (list.length?`<div class="section-label">WEJŚCIA I AKCENTY <span>${list.length}</span></div><div class="motion-grid">${list.map(tile).join('')}</div>`:'')+
   (exitList.length?`<div class="section-label">WYJŚCIA <span>${exitList.length}</span></div><div class="motion-grid">${exitList.map(exitTile).join('')}</div>`:'')+
   `<div class="tip-card">Tekst kinetyczny animuje każde słowo lub literę. Wyjście działa w ostatnich sekundach klipu i łączy się z dowolnym wejściem.</div>`;
 }
 function animationSection(e){
  const motions=getMotions(),exits=getExits(),textual=['text','caption'].includes(e.type);
  const entries=motions.filter(m=>m.kind==='entrance'),kinetic=motions.filter(m=>m.kind==='kinetic');
  const current=motions.find(m=>m.id===e.motion?.id);
  return `<div class="inspector-section motion-section"><h3>Ruch <button class="quiet-button" data-motion-tab>Przeglądaj</button></h3>
   <div class="motion-pill"><span class="motion-pill-icon">✦</span><span>${esc(current?.name||'Bez animacji')}<small>${e.motion?.duration||0}s · ${current?{low:'spokojna',medium:'średnia',high:'wysoka'}[current.energy]+' energia':'bez ruchu'}${e.exit?` · wyjście ${e.exit.duration}s`:''}</small></span></div>
   <label class="field full">Wejście<select data-anim="motion-id"><option value="none">Bez animacji</option><optgroup label="Wejścia i akcenty">${entries.map(m=>`<option value="${m.id}" ${e.motion?.id===m.id?'selected':''}>${esc(m.name)}</option>`).join('')}</optgroup>${textual?`<optgroup label="Tekst kinetyczny">${kinetic.map(m=>`<option value="${m.id}" ${e.motion?.id===m.id?'selected':''}>${esc(m.name)}</option>`).join('')}</optgroup>`:''}</select></label>
   ${e.motion?`<div class="field-grid"><label class="field">Czas wejścia · s<input data-anim="motion-duration" type="number" min=".1" max="4" step=".1" value="${e.motion.duration}"></label><label class="field">Krzywa<select data-anim="motion-easing">${options(EASING_LABELS,e.motion.easing||'cubic-out')}</select></label></div>`:''}
   ${e.type!=='audio'?`<label class="field full">Wyjście<select data-anim="exit-id"><option value="none">Bez wyjścia</option>${exits.map(x=>`<option value="${x.id}" ${e.exit?.id===x.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>
   ${e.exit?`<div class="field-grid"><label class="field">Czas wyjścia · s<input data-anim="exit-duration" type="number" min=".1" max="2" step=".1" value="${e.exit.duration}"></label><label class="field">Krzywa<select data-anim="exit-easing">${options(EASING_LABELS,e.exit.easing||'cubic-out')}</select></label></div>`:''}`:''}
   <div class="motion-actions">${e.motion?'<button class="secondary-button" data-preview-motion>▶ Podgląd wejścia</button>':''}${e.exit?'<button class="secondary-button" data-preview-exit>◀ Podgląd wyjścia</button>':''}</div></div>`;
 }
 function lookSection(e){
  if(e.type==='audio')return '';
  const s=e.style,textual=['text','caption'].includes(e.type),g=s.gradient;
  const baseColor=hex(s.color,'#ffffff');
  return `<div class="inspector-section look-section"><h3>Wygląd i efekty</h3><div class="field-grid">
   <label class="field">Cień<select data-property="style.shadow">${options(SHADOWS,s.shadow||'none')}</select></label>
   ${['glow','neon','long'].includes(s.shadow)?`<label class="field">Kolor cienia<input type="color" data-property="style.shadowColor" value="${hex(s.shadowColor,s.shadow==='long'?'#000000':baseColor)}"></label>`:'<span></span>'}
   <label class="field">Mieszanie<select data-property="style.blend">${options(BLENDS,s.blend||'normal')}</select></label>
   ${['image','video'].includes(e.type)?`<label class="field">Dopasowanie<select data-property="style.fit">${options([['contain','Zmieść'],['cover','Wypełnij kadr']],s.fit||'contain')}</select></label>`:'<span></span>'}
   ${textual?`<label class="field">Odstęp liter · px<input data-property="style.letterSpacing" type="number" step="1" min="-50" max="200" value="${s.letterSpacing||0}"></label><label class="field">Obrys · px<input data-property="style.strokeWidth" type="number" step="1" min="0" max="40" value="${s.strokeWidth||0}"></label>${s.strokeWidth?`<label class="field full">Kolor obrysu<input type="color" data-property="style.strokeColor" value="${hex(s.strokeColor,'#000000')}"></label>`:''}`:''}
   </div>${['text','caption','shape'].includes(e.type)||e.assetId&&e.type==='image'?`<label class="production-toggle look-toggle"><input type="checkbox" data-look="gradient-on" ${g?'checked':''}> Wypełnienie gradientem</label>
   ${g?`<div class="gradient-row"><input type="color" data-look="gradient-from" value="${g.from}" aria-label="Kolor początkowy"><span class="gradient-preview" style="background:linear-gradient(${g.angle}deg,${g.from},${g.to})"></span><input type="color" data-look="gradient-to" value="${g.to}" aria-label="Kolor końcowy"><label class="field">Kąt<input data-look="gradient-angle" type="number" min="0" max="360" step="15" value="${g.angle}"></label></div>`:''}`:''}</div>`;
 }
 function clipFxSection(){
  const e=selected();
  if(!e||e.type==='audio')return '<div class="tip-card">Zaznacz klip obrazu, wideo, tekstu lub kształtu, aby nadać mu własny efekt.</div>';
  const fx=e.clipFx||{look:'none',strength:1};
  return `<div class="inspector-section"><h3>Efekt zaznaczonego klipu</h3><div class="clip-look-grid">${getEditingPresets().clipLooks.map(pr=>`<button data-clip-look="${pr.id}" aria-pressed="${fx.look===pr.id}" class="clip-look ${fx.look===pr.id?'active':''}"><span class="look-swatch look-${pr.id}"></span>${esc(pr.name)}</button>`).join('')}</div><label class="field full">Siła · ${Math.round(fx.strength*100)}%<input data-clip-strength type="range" min="0" max="1" step=".05" value="${fx.strength}"></label><p class="inspector-note">Efekt zmienia tylko ten klip. Naturalny usuwa korekcję koloru.</p></div>`;
 }
 function transitionSection(){
  const scenes=getProject().scenes.filter(s=>s.start>0).sort((a,b)=>a.start-b.start);
  const scene=scenes.find(s=>s.id===transitionSceneId)||scenes[0];
  if(!scene)return '<div class="tip-card">Dodaj plan z co najmniej dwiema scenami, aby używać przejść między scenami.</div>';
  transitionSceneId=scene.id;
  const fx=getProject().canvas.fx||{},value=scene.transition||{id:fx.transition||'none',duration:fx.transitionDuration||.5};
  return `<div class="inspector-section"><h3>Przejście do sceny</h3><label class="field full">Scena<select data-transition-scene>${scenes.map(s=>`<option value="${s.id}" ${s.id===scene.id?'selected':''}>${esc(s.name)} · ${s.start.toFixed(2)} s</option>`).join('')}</select></label><div class="transition-grid">${getEditingPresets().transitions.map(pr=>`<button data-scene-transition="${pr.id}" aria-pressed="${value.id===pr.id}" class="transition-choice ${value.id===pr.id?'active':''}"><span class="transition-demo transition-${pr.id}"><i></i></span>${esc(pr.name)}</button>`).join('')}</div><label class="field full">Czas przejścia · s<input data-scene-transition-duration type="number" min=".1" max="2" step=".1" value="${value.duration}"></label><div class="motion-actions"><button class="secondary-button" data-preview-transition>▶ Podgląd przejścia</button><button class="quiet-button" data-reset-transition>Użyj ustawień filmu</button></div><p class="inspector-note">${scene.transition?'Własne przejście tej sceny.':'Scena dziedziczy ustawienia całego filmu.'} Przejścia zasłaniają lub stylizują cięcie; nie wymagają nakładania nagrań.</p></div>`;
 }
 function effectsPanel(){return `<h2 class="panel-heading">Efekty i przejścia</h2><div class="panel-subtitle">Wbudowane, działają offline i trafiają do eksportu.</div>${clipFxSection()}${transitionSection()}${filmSection()}`;}
 function filmSection(){
  const p=getProject(),fx=Object.assign({grade:'none',vignette:0,grain:0,letterbox:0,transition:'none',transitionDuration:.5,motionBlur:false},p.canvas.fx||{});
  const range=(label,key,max,step)=>`<label class="field full range-field">${label}<span class="range-value">${Math.round(fx[key]/max*100)}%</span><input type="range" data-fx="${key}" min="0" max="${max}" step="${step}" value="${fx[key]}"></label>`;
  return `<div class="inspector-section film-section"><h3>Efekty filmowe</h3><div class="film-presets">${Object.entries(FILM_PRESETS).map(([id,pr])=>`<button class="film-preset" data-fx-preset="${id}"><span class="film-swatch ${id}"></span>${pr.name}</button>`).join('')}</div>
   <label class="field full">Kolor (look)<select data-fx="grade">${options(GRADES,fx.grade)}</select></label>
   ${range('Winieta','vignette',1,.05)}${range('Ziarno filmowe','grain',1,.05)}${range('Kaszeta kinowa','letterbox',.25,.01)}
   <div class="field-grid"><label class="field">Domyślne przejście<select data-fx="transition">${options(getEditingPresets().transitions.map(pr=>[pr.id,pr.name]),fx.transition)}</select></label><label class="field">Czas · s<input data-fx="transitionDuration" type="number" min=".1" max="2" step=".1" value="${fx.transitionDuration}"></label></div>
   <label class="production-toggle"><input type="checkbox" data-fx="motionBlur" ${fx.motionBlur?'checked':''}> Rozmycie ruchu w finalnym eksporcie</label>
   <p class="inspector-note">${p.scenes.length?`Przejścia działają na ${Math.max(0,p.scenes.length-1)} cięciach między scenami.`:'Przejścia pojawią się po dodaniu scen.'} Rozmycie ruchu wydłuża render około 4×.</p></div>`;
 }
 async function onChange(t){
  const e=selected();
  if(t.hasAttribute('data-transition-scene')){transitionSceneId=t.value;rerenderLibrary();return true;}
  if(t.hasAttribute('data-scene-transition-duration')){const s=getProject().scenes.find(s=>s.id===transitionSceneId),fx=getProject().canvas.fx||{};await command('set_scene_transition',{scene_id:s.id,transition:{id:s.transition?.id||fx.transition||'none',duration:Number(t.value)}});return true;}
  if(t.hasAttribute('data-clip-strength')&&e){await command('set_clip_fx',{fx:{look:e.clipFx?.look||'none',strength:Number(t.value)}});return true;}
  if(t.dataset.fx){
   const k=t.dataset.fx,v=t.type==='checkbox'?t.checked:['range','number'].includes(t.type)?Number(t.value):t.value;
   await command('set_canvas_fx',{fx:{[k]:v}});return true;
  }
  if(t.dataset.anim&&e){
   const k=t.dataset.anim;
   if(k==='motion-id'){const m=getMotions().find(m=>m.id===t.value);await command('apply_motion',m?{motion_id:m.id,duration:m.defaults.duration,easing:m.defaults.easing}:{motion_id:'none'});if(m)await previewMotion();}
   if(k==='motion-duration')await command('apply_motion',{motion_id:e.motion.id,duration:Number(t.value),easing:e.motion.easing||'cubic-out'});
   if(k==='motion-easing')await command('apply_motion',{motion_id:e.motion.id,duration:e.motion.duration,easing:t.value});
   if(k==='exit-id'){await command('apply_exit',t.value==='none'?{exit_id:'none'}:{exit_id:t.value,duration:e.exit?.duration||.6,easing:e.exit?.easing||'cubic-out'});if(t.value!=='none')await previewExit();}
   if(k==='exit-duration')await command('apply_exit',{exit_id:e.exit.id,duration:Number(t.value),easing:e.exit.easing||'cubic-out'});
   if(k==='exit-easing')await command('apply_exit',{exit_id:e.exit.id,duration:e.exit.duration,easing:t.value});
   return true;
  }
  if(t.dataset.look&&e){
   const accent=getProject().brand.colors.accent,g=e.style.gradient||{from:/^#[0-9a-fA-F]{6}$/.test(e.style.color)?e.style.color:'#ffffff',to:accent,angle:90};
   const k=t.dataset.look;let value;
   if(k==='gradient-on')value=t.checked?g:null;
   else value={...g,[k.slice(9)]:k==='gradient-angle'?Number(t.value):t.value};
   await command('set_property',{element_id:e.id,property:'style.gradient',value});return true;
  }
  return false;
 }
 async function onClick(b){
  if(b.dataset.clipLook){if(!selected()||selected().type==='audio')return true;await command('set_clip_fx',{fx:{look:b.dataset.clipLook,strength:selected().clipFx?.strength??1}});return true;}
  if(b.dataset.sceneTransition){const scene=getProject().scenes.find(s=>s.id===transitionSceneId);await command('set_scene_transition',{scene_id:scene.id,transition:{id:b.dataset.sceneTransition,duration:scene.transition?.duration||getProject().canvas.fx?.transitionDuration||.5}});return true;}
  if(b.hasAttribute('data-reset-transition')){await command('set_scene_transition',{scene_id:transitionSceneId,transition:null});return true;}
  if(b.hasAttribute('data-preview-transition')){const scene=getProject().scenes.find(s=>s.id===transitionSceneId);await previewTransition(scene);return true;}
  if(b.dataset.motionFilter){filter=b.dataset.motionFilter;rerenderLibrary();return true;}
  if(b.dataset.exit){
   const e=selected();if(!e)return toast('Zaznacz element, aby dodać wyjście.'),true;
   if(e.type==='audio')return toast('Dźwięk wycisza się w panelu Dźwięk.'),true;
   await command('apply_exit',{exit_id:b.dataset.exit,duration:Math.min(.6,e.duration),easing:'cubic-out'});await previewExit();toast('Wyjście zastosowane — podgląd końca klipu.');return true;
  }
  if(b.dataset.fxPreset){const pr=FILM_PRESETS[b.dataset.fxPreset];await command('set_canvas_fx',{fx:pr.fx});toast(`Look „${pr.name}” zastosowany do całego filmu.`);return true;}
  if(b.hasAttribute('data-preview-motion')){await previewMotion();return true;}
  if(b.hasAttribute('data-preview-exit')){await previewExit();return true;}
  return false;
 }
 return {panel,effectsPanel,clipFxSection,animationSection,lookSection,filmSection,onChange,onClick};
}
