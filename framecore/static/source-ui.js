/* Source monitor: select a real media range, then commit one shared edit. */
export function createSourceUI({getProject,getState,command,choose,esc,openModal,closeModal,modalHeader,toast}){
 let source=null;
 const $=s=>document.querySelector(s);
 function open(aid){
  const p=getProject(),a=p.assets.find(a=>a.id===aid);if(!a)return;
  source={pid:p.id,revision:p.revision,asset:a};
  const url=`/assets/${p.id}/${encodeURIComponent(a.file.split('/').pop())}`;
  const end=Math.max(.01,Math.min(a.duration||3,p.duration-getState().session.playhead,3));
  openModal(modalHeader('MONITOR ŹRÓDŁA','Wybierz fragment',esc(a.name))+`<div class="modal-body source-monitor">${a.kind==='image'?`<img class="source-picture" src="${url}" alt="${esc(a.name)}">`:`<${a.kind} id="sourcePlayer" controls preload="metadata" src="${url}" class="source-picture"></${a.kind}>`}${a.duration?`<div class="field-grid"><label class="field">Wejście IN · s<input id="sourceIn" type="number" min="0" max="${a.duration}" step=".01" value="0"></label><label class="field">Wyjście OUT · s<input id="sourceOut" type="number" min="0" max="${a.duration}" step=".01" value="${end.toFixed(3)}"></label></div><div class="motion-actions"><button class="secondary-button" data-source-mark="in">Ustaw IN · I</button><button class="secondary-button" data-source-mark="out">Ustaw OUT · O</button><button class="secondary-button" data-source-play>▶ Odtwórz zakres</button></div>${a.kind==='video'&&a.hasAudio?'<label class="production-toggle"><input id="sourceIncludeAudio" type="checkbox" checked> Dodaj też dźwięk na osobnej ścieżce</label>':''}`:''}<p class="inspector-note">Wstawianie przy ${getState().session.playhead.toFixed(2)} s. Oryginał pozostaje bez zmian; montaż i dźwięk można edytować osobno.</p><button class="primary-button" data-source-insert>Wstaw wybrany fragment</button></div>`);
  const player=$('#sourcePlayer');
  if(player){player.addEventListener('timeupdate',()=>{if(player.dataset.rangePlayback&&player.currentTime>=Number($('#sourceOut').value)){player.pause();delete player.dataset.rangePlayback;}});$('#modal').addEventListener('close',()=>player.pause(),{once:true});}
 }
 async function handle(e){
  const b=e.target.closest('[data-source-asset],[data-source-mark],[data-source-insert],[data-source-play]');if(!b)return;
  if(b.dataset.sourceAsset)return open(b.dataset.sourceAsset);
  const player=$('#sourcePlayer');
  if(b.dataset.sourceMark){$('#source'+(b.dataset.sourceMark==='in'?'In':'Out')).value=(player?.currentTime||0).toFixed(3);return;}
  if(b.hasAttribute('data-source-play')){const start=Number($('#sourceIn').value),end=Number($('#sourceOut').value);if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>source.asset.duration)throw Error('Wybierz poprawny zakres IN–OUT.');player.currentTime=start;player.dataset.rangePlayback='true';await player.play();return;}
  if(b.hasAttribute('data-source-insert')){
   if(getProject().id!==source.pid||getProject().revision!==source.revision)throw Error('Projekt zmienił się; otwórz wybór zakresu ponownie.');
   const before=getProject().elements.length,a=source.asset;
   const result=await command(a.kind==='image'?'add_image':'insert_media_range',a.kind==='image'?{assetId:a.id,start:getState().session.playhead,duration:Math.min(3,getProject().duration-getState().session.playhead)}:{asset_id:a.id,source_start:Number($('#sourceIn').value),source_end:Number($('#sourceOut').value),start:getState().session.playhead,include_audio:$('#sourceIncludeAudio')?.checked||false});
   if(result){closeModal();await choose(result.project.elements.slice(before).map(e=>e.id));}
  }
 }
 document.addEventListener('click',e=>handle(e).catch(err=>toast(err.message)));
 document.addEventListener('keydown',e=>{if(!$('#modal').open||!$('#sourcePlayer')||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.ctrlKey||e.metaKey)return;const key=e.key.toLowerCase();if(['i','o'].includes(key)){e.preventDefault();$('#source'+(key==='i'?'In':'Out')).value=$('#sourcePlayer').currentTime.toFixed(3);}});
 return {open};
}
