/* Shared editing commands: media swap, library-to-timeline drops and track tools. */
export function createEditingUI(ctx){
 const {getProject,getState,selected,request,command,choose,upload,esc,openModal,closeModal,modalHeader,toast,getFonts,getEditingPresets}=ctx;
 const $=s=>document.querySelector(s);
 let target=null;
 const compatible=(track,kind)=>track===kind||['image','video'].includes(track)&&['image','video'].includes(kind);
 const kinds={image:'Obrazy',video:'Wideo i obrazy',audio:'Dźwięk',text:'Teksty',caption:'Napisy',shape:'Kształty'};
 function groupControls(){
  const ids=getState().session.selection,clips=getProject().elements.filter(e=>ids.includes(e.id)),textual=clips.every(e=>['text','caption'].includes(e.type));
  return `<div class="selected-heading">${clips.length} zaznaczone klipy</div><p class="inspector-note">Ctrl / ⌘ / Shift + klik dodaje klip. Przeciągnij zaznaczony klip, aby przesunąć całą grupę. Każda operacja to jeden krok cofania.</p><div class="inspector-section"><h3>Edycja grupy</h3><label class="field full">Przesunięcie · s<input id="groupDelta" type="number" step=".1" value="0"></label><div class="timeline-tool-grid"><button class="secondary-button" data-edit="move-group">Przesuń grupę</button><button class="secondary-button" data-edit="duplicate">Duplikuj grupę</button><button class="secondary-button" data-edit="split-group">Podziel przy wskaźniku</button><button class="secondary-button" data-edit="delete-group">Usuń grupę</button></div></div>${textual?`<div class="inspector-section"><h3>Wspólna typografia</h3><label class="field full">Font<select data-group-property="style.fontFamily">${[...getFonts().map(f=>f.family),'Arial','Georgia'].map(f=>`<option ${f===clips[0].style.fontFamily?'selected':''}>${esc(f)}</option>`).join('')}</select></label><label class="field full">Rozmiar<input type="number" min="1" data-group-property="style.fontSize" value="${clips[0].style.fontSize}"></label><label class="field full">Kolor<input type="color" data-group-property="style.color" value="${clips[0].style.color}"></label></div>`:''}${clips.every(e=>e.type!=='audio')?`<label class="field full">Look całej grupy<select data-group-look><option value="">Wybierz efekt…</option>${getEditingPresets().clipLooks.map(f=>`<option value="${f.id}">${esc(f.name)}</option>`).join('')}</select></label>`:''}`;
 }
 function timelineControls(e){return `<div class="inspector-section"><h3>Szybki montaż</h3><div class="timeline-tool-grid"><button class="secondary-button" data-edit="trim-left">Przytnij początek do wskaźnika</button><button class="secondary-button" data-edit="trim-right">Przytnij koniec do wskaźnika</button><button class="secondary-button" data-edit="close-gaps">Usuń luki na ścieżce</button><button class="secondary-button" data-edit="ripple-delete">Usuń i zsuń kolejne</button></div>${['video','audio'].includes(e.type)?`<label class="field full">Początek zakresu źródła · s<input data-slip-source type="number" min="0" step=".01" value="${e.sourceStart}"></label><button class="secondary-button" data-edit="slip">Zmień zakres źródła</button>`:''}<p class="inspector-note">Zsuwanie zmienia tylko tę ścieżkę. Pozostałe ścieżki, sceny i długość filmu pozostają na miejscu. Wszystkie zmiany można cofnąć.</p></div>`;}
 function timelineModal(){const e=selected();if(!e)return toast('Zaznacz klip na osi czasu, aby otworzyć narzędzia.');openModal(modalHeader('PRECYZYJNY MONTAŻ','Narzędzia timeline',`${e.start.toFixed(2)}–${(e.start+e.duration).toFixed(2)} s · wskaźnik ${getState().session.playhead.toFixed(2)} s`)+`<div class="modal-body">${timelineControls(e)}</div>`);}
 function controls(e){return ['image','video','audio'].includes(e.type)?`<div class="inspector-section"><h3>Źródło klipu</h3><p class="inspector-note">${esc(getProject().assets.find(a=>a.id===e.assetId)?.name||'Materiał')}</p><button class="secondary-button" data-edit="replace">Podmień materiał</button><button class="secondary-button" data-edit="replace-file">Wgraj plik i podmień</button><p class="inspector-note">Pozycja, czas, klatki kluczowe i animacja zostają. Możesz też upuścić materiał z biblioteki na klip.</p></div>`:'';}
 function replaceModal(){
  const e=selected();if(!e||!e.assetId)return toast('Zaznacz klip obrazu, wideo lub dźwięku.');
  target={project_id:getProject().id,revision:getProject().revision,id:e.id};
  const assets=getProject().assets.filter(a=>e.type==='audio'?a.kind==='audio'||a.kind==='video'&&a.hasAudio:['image','video'].includes(a.kind));
  openModal(modalHeader('EDYCJA BEZ UTRATY MONTAŻU','Podmień materiał','Geometria i animacja klipu pozostają edytowalne.')+`<div class="modal-body"><label class="field">Nowe źródło<select id="replacementAsset">${assets.map(a=>`<option value="${a.id}" ${a.id===e.assetId?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label><label class="production-toggle"><input id="replacementFit" type="checkbox"> Skróć klip, jeśli nowe nagranie jest krótsze</label><p class="inspector-note">Przy dopasowaniu skróci się też zakres klatek kluczowych. Nie wydłużamy krótkiego nagrania sztucznie.</p><button class="primary-button" data-edit="apply-replace">Podmień klip</button></div>`);
 }
 async function replace(aid,eid,fit=false){return command('replace_clip_asset',{element_id:eid,asset_id:aid,fit_source:fit});}
 async function addAt(aid,start,trackId){
   const p=getProject(),a=p.assets.find(a=>a.id===aid),track=p.tracks.find(t=>t.id===trackId);
   if(!a||!['image','video','audio'].includes(a.kind))throw Error('Nie można dodać tego materiału.');
   if(track&&(!compatible(track.kind,a.kind)||track.locked))throw Error('Upuść materiał na odblokowaną ścieżkę zgodnego rodzaju (obrazy i wideo można mieszać).');
   start=Math.max(0,Math.min(p.duration-.01,start));
   const result=await command('add_'+a.kind,{assetId:aid,start,duration:Math.min(a.duration||3,p.duration-start),
    ...(track?{trackId:track.id}:{}),...(a.kind==='video'?{x:0,y:0,width:p.canvas.width,height:p.canvas.height}:{})});
   if(result)await choose(result.project.elements.at(-1).id);
 }
 function trackModal(){openModal(modalHeader('WARSTWY MONTAŻU','Dodaj ścieżkę','Oddziel elementy na osi czasu, a potem przeciągaj klipy między ścieżkami zgodnego rodzaju (obrazy i wideo można mieszać).')+`<div class="modal-body"><label class="field">Nazwa<input id="newTrackName" value="Nowa ścieżka"></label><label class="field">Rodzaj<select id="newTrackKind">${Object.entries(kinds).map(([k,n])=>`<option value="${k}">${n}</option>`).join('')}</select></label><button class="primary-button" data-edit="create-track">Dodaj ścieżkę</button></div>`);}
 async function handle(e){
  const b=e.target.closest('[data-edit]');if(!b)return;
  if(b.dataset.edit==='move-group')await command('move_clips',{element_ids:[...getState().session.selection],delta:Number($('#groupDelta').value)});
  if(b.dataset.edit==='split-group')await command('split_clips',{element_ids:[...getState().session.selection],time:getState().session.playhead});
  if(b.dataset.edit==='delete-group')await command('delete_clips',{element_ids:[...getState().session.selection],ripple:$('#magnetic').checked});
  if(b.dataset.edit==='timeline-tools')timelineModal();
  if(['trim-left','trim-right','close-gaps','ripple-delete','slip'].includes(b.dataset.edit)){
   const clip=selected();if(!clip)return toast('Zaznacz jeden klip.');
   const op=b.dataset.edit,time=getState().session.playhead;
   if(op.startsWith('trim-')){
    if(time<=clip.start||time>=clip.start+clip.duration)throw Error('Ustaw wskaźnik wewnątrz klipu.');
    await command('trim_clip',{element_id:clip.id,start:op==='trim-left'?time:clip.start,duration:op==='trim-left'?clip.start+clip.duration-time:time-clip.start});
   }
   if(op==='close-gaps')await command('close_track_gaps',{track_id:clip.trackId});
   if(op==='ripple-delete')await command('ripple_delete',{element_id:clip.id});
   if(op==='slip')await command('slip_clip',{element_id:clip.id,source_start:Number(b.closest('.inspector-section').querySelector('[data-slip-source]').value)});
   if(document.querySelector('#modal').open)closeModal();
  }
  if(b.dataset.edit==='replace')replaceModal();
  if(b.dataset.edit==='replace-file'){const clip=selected();if(!clip)return;target={project_id:getProject().id,id:clip.id};$('#replaceFile').accept=clip.type==='audio'?'audio/*,video/*':'image/png,image/jpeg,image/webp,video/*';$('#replaceFile').click();}
  if(b.dataset.edit==='apply-replace'){if(getProject().id!==target.project_id||getProject().revision!==target.revision)throw Error('Projekt zmienił się; otwórz podmianę ponownie.');await replace($('#replacementAsset').value,target.id,$('#replacementFit').checked);closeModal();}
  if(b.dataset.edit==='add-track')trackModal();
  if(b.dataset.edit==='create-track'){await command('add_track',{name:$('#newTrackName').value,kind:$('#newTrackKind').value});closeModal();}
  if(b.dataset.edit==='duplicate'){const ids=[...getState().session.selection];if(!ids.length)return;const before=getProject().elements.length,result=await command('duplicate_clips',{element_ids:ids});if(result)await choose(result.project.elements.slice(before).map(e=>e.id));}
 }
 function start(){
  document.addEventListener('click',e=>handle(e).catch(err=>toast(err.message)));
  document.addEventListener('change',e=>{const t=e.target;if(!t.dataset.groupProperty&&!t.hasAttribute('data-group-look'))return;const properties=t.dataset.groupProperty?{[t.dataset.groupProperty]:t.type==='number'?Number(t.value):t.value}:{clipFx:{look:t.value,strength:1}};command('set_clip_properties',{element_ids:[...getState().session.selection],properties}).catch(err=>toast(err.message));});
  $('#replaceFile').addEventListener('change',async e=>{const frozen=target,file=e.target.files[0];if(!file)return;try{if(getProject().id!==frozen.project_id)throw Error('Wróć do projektu wybranego przy podmianie.');const assets=await upload([file]);if(getProject().id===frozen.project_id&&assets?.length)await replace(assets[0].id,frozen.id);}catch(err){toast(err.message);}finally{e.target.value='';}});
  $('#libraryContent').addEventListener('dragstart',e=>{const b=e.target.closest('[data-asset]');if(!b)return;e.dataTransfer.setData('application/x-framecore-asset',JSON.stringify({project_id:getProject().id,asset_id:b.dataset.asset}));e.dataTransfer.effectAllowed='copy';});
  const timeline=$('#timelineContent');
  timeline.addEventListener('dragover',e=>{e.preventDefault();timeline.classList.add('drop-active');});
  timeline.addEventListener('dragleave',e=>{if(!timeline.contains(e.relatedTarget))timeline.classList.remove('drop-active');});
  timeline.addEventListener('drop',async e=>{
   e.preventDefault();timeline.classList.remove('drop-active');const lane=e.target.closest('[data-lane]'),clip=e.target.closest('[data-clip]');if(!lane)return;
   const rect=lane.getBoundingClientRect(),time=(e.clientX-rect.left)/rect.width*getProject().duration;
   try{
    let ids=[];const value=e.dataTransfer.getData('application/x-framecore-asset');
    if(value){const item=JSON.parse(value);if(item.project_id!==getProject().id)throw Error('Materiał pochodzi z innego projektu.');ids=[item.asset_id];}
    else if(e.dataTransfer.files.length){if(clip&&e.dataTransfer.files.length!==1)throw Error('Na klip upuść jeden plik do podmiany.');const imported=await upload([...e.dataTransfer.files]);ids=(imported||[]).map(a=>a.id);}
    if(clip&&ids.length===1){await replace(ids[0],clip.dataset.clip);toast('Materiał podmieniony; montaż zachowany.');}
    else {let cursor=time;for(const id of ids){await addAt(id,cursor,lane.dataset.lane);cursor+=Math.min(getProject().assets.find(a=>a.id===id)?.duration||3,getProject().duration-cursor);}}
   }catch(err){toast(err.message);}
  });
  timeline.addEventListener('contextmenu',async e=>{const clip=e.target.closest('[data-clip]');if(!clip)return;e.preventDefault();await choose(clip.dataset.clip);if(selected()?.assetId)replaceModal();});
 }
 return {controls,timelineControls,groupControls,start,addAt};
}
