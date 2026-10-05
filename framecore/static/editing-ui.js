/* Shared editing commands: media swap, library-to-timeline drops and track tools. */
export function createEditingUI(ctx){
 const {getProject,getState,selected,request,command,choose,upload,esc,openModal,closeModal,modalHeader,toast}=ctx;
 const $=s=>document.querySelector(s);
 let target=null;
 const compatible=(track,kind)=>track===kind||['image','video'].includes(track)&&['image','video'].includes(kind);
 const kinds={image:'Obrazy',video:'Wideo i obrazy',audio:'Dźwięk',text:'Teksty',caption:'Napisy',shape:'Kształty'};
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
  if(b.dataset.edit==='replace')replaceModal();
  if(b.dataset.edit==='replace-file'){const clip=selected();if(!clip)return;target={project_id:getProject().id,id:clip.id};$('#replaceFile').accept=clip.type==='audio'?'audio/*,video/*':'image/png,image/jpeg,image/webp,video/*';$('#replaceFile').click();}
  if(b.dataset.edit==='apply-replace'){if(getProject().id!==target.project_id||getProject().revision!==target.revision)throw Error('Projekt zmienił się; otwórz podmianę ponownie.');await replace($('#replacementAsset').value,target.id,$('#replacementFit').checked);closeModal();}
  if(b.dataset.edit==='add-track')trackModal();
  if(b.dataset.edit==='create-track'){await command('add_track',{name:$('#newTrackName').value,kind:$('#newTrackKind').value});closeModal();}
  if(b.dataset.edit==='duplicate'){const e=selected();if(e)await command('duplicate_clip',{element_id:e.id,start:Math.min(getProject().duration-e.duration,e.start+e.duration)});}
 }
 function start(){
  document.addEventListener('click',e=>handle(e).catch(err=>toast(err.message)));
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
 return {controls,start,addAt};
}
