/* Production workflow: real evidence and an explicit review, shared with MCP. */
export function createProductionUI(ctx){
 const {getProject,esc,icon,call,command,openModal,closeModal,modalHeader,toast}=ctx;
 let lastReview=null;
 const lines=value=>value.split('\n').map(s=>s.trim()).filter(Boolean);
 const field=(name,label,value)=>`<label class="field full">${label}<textarea data-production-field="${name}">${esc(value||'')}</textarea></label>`;
 function panel(p){
  const c=p.production||{};
  return `<h2 class="panel-heading">Produkcja</h2><p class="panel-subtitle">Brief → beaty → klatki → ocena → film.</p><button class="secondary-button" data-lesson="open">Lekcja przez historię · plan 7 scen</button>${p.lesson?`<button class="secondary-button" data-lesson="check">Sprawdź opisy i tempo narracji</button>`:''}<div id="productionStatus" class="production-status" role="status">Sprawdzanie projektu…</div>
   <details open class="production-section"><summary>1. Brief reżyserski</summary>
   ${field('product','Produkt / temat',c.product||p.metadata.name)}${field('message','Jeden główny komunikat',c.message||p.metadata.brief)}
   ${field('facts','Potwierdzone fakty · jeden na wiersz',(c.facts||[]).join('\n'))}
   ${field('references','Referencje · link lub opis na wiersz',(c.references||[]).join('\n'))}
   ${field('rejectionCriteria','Kryteria odrzucenia · jedno na wiersz',(c.rejectionCriteria||[]).join('\n'))}
   <label class="production-toggle"><input id="requireProductionReview" type="checkbox" ${c.requireReview?'checked':''}> Wymagaj oceny przed finalnym eksportem</label>
   <button class="primary-button" data-production-action="save">Zapisz brief</button></details>
   <details class="production-section"><summary>2. Obowiązkowe materiały</summary><div id="requiredAssets">${(c.requiredAssets||[]).map(a=>requiredRow(p,a)).join('')}</div><button class="secondary-button" data-production-action="add-required">+ Wymagany materiał</button><p class="inspector-note">Wskaż prawdziwy plik. Brak wymaganej pozycji zatrzyma przegląd i render. Zapisz listę przyciskiem Zapisz brief.</p></details>
   <details open class="production-section"><summary>3. Stany i beaty</summary><button class="secondary-button" data-production-action="beats">Uzupełnij beaty z montażu</button>${p.scenes.map(s=>`<button class="production-beat" data-production-scene="${s.id}"><strong>${esc(s.name)}</strong><small>${s.start.toFixed(2)}–${(s.start+s.duration).toFixed(2)} s</small><span>${esc(s.beat?.purpose||'Opisz cel i stany sceny')}</span></button>${s.lesson?`<button class="secondary-button" data-lesson-scene="${s.id}">Tekst lektora · ${esc(s.name)}</button>`:''}` ).join('')}<p class="inspector-note">Proponowany opis jest punktem wyjścia. Sprawdź cel i główny element każdej sceny.</p></details>
   <details class="production-section"><summary>4. Reguły ruchu</summary><p>Napisy wchodzą szybciej; obrazy i wideo osiadają wolniej. Animacja pozostaje deterministyczna.</p><ol><li>Jeden element prowadzi widza między scenami.</li><li>Ruch pokazuje przyczynę i skutek.</li><li>Jedno główne działanie; dodatki mają niższą rangę.</li><li>Czytelne osiadanie → szybkie wyjście → spokojne wejście.</li><li>Cięcie zachowuje kierunek lub wspólny obiekt.</li><li>Pierwsza klatka daje kontekst, ostatnia czytelny następny krok.</li></ol><button class="secondary-button" data-production-action="motion">Zastosuj reguły ruchu</button></details>
   <div class="production-section"><h3>5. Przegląd przed eksportem</h3><button class="primary-button" data-production-action="review">${icon('images')}Generuj planszę klatek</button><button class="secondary-button" data-production-action="latest">Otwórz aktualny przegląd</button><p class="inspector-note">Obejrzyj klatki i przejścia; dźwięk sprawdź w roboczym MP4. Ocena wymaga Twojej checklisty.</p></div>
   <details class="production-section"><summary>Laboratorium ruchu · fframes</summary><label class="field">Scena<select id="motionScene"><option value="">Cały film</option>${p.scenes.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label><label class="field">Liczba klatek<input id="motionCount" type="number" min="2" max="24" value="12"></label><button class="secondary-button" data-production-action="strip">Plansza i tor ruchu</button><p class="inspector-note">Nakładka klatek pokazuje tor i zmianę tempa. Agent może podać adres np. scena@50% lub scena@end.</p><label class="field">Przegląd przed zmianą<input id="baselineReview" placeholder="review_…"></label><label class="field">Przegląd po zmianie<input id="changedReview" placeholder="review_…"></label><button class="secondary-button" data-production-action="compare">Porównaj zapisane klatki</button><button class="secondary-button" data-production-action="review-list">Pokaż identyfikatory przeglądów</button><p class="inspector-note">Porównuj przeglądy z tymi samymi czasami. Zmiana pikseli nie jest oceną jakości.</p></details>
   <div class="production-section"><h3>6. Osobne układy</h3><div class="production-formats">${['16:9','9:16','4:5','1:1'].map(f=>`<button data-production-format="${f}">${f}</button>`).join('')}</div><p class="inspector-note">Powstanie osobny projekt z układem tekst + ilustracja, do dalszej edycji. Wideo i kształty zachowują skalowane pozycje. Każdy wariant wymaga własnej oceny.</p></div>`;
 }
 function requiredRow(p,a={label:'',assetId:null}){return `<div class="required-asset-row"><input data-required-label aria-label="Nazwa wymaganego materiału" placeholder="np. prawdziwe logo" value="${esc(a.label)}"><select data-required-id aria-label="Plik wymaganego materiału"><option value="">Brak pliku — do uzupełnienia</option>${p.assets.map(x=>`<option value="${x.id}" ${x.id===a.assetId?'selected':''}>${esc(x.name)}</option>`).join('')}</select><button data-production-action="remove-required" aria-label="Usuń wymaganie">×</button></div>`;}
 async function refreshStatus(){
  const pid=getProject().id;const s=await call('get_production_status');const box=document.querySelector('#productionStatus');
  if(!box||pid!==getProject().id||s.revision!==getProject().revision)return;
  box.innerHTML=`<strong>${s.finalReady?'Gotowe do eksportu':s.blockers.length?'Uzupełnij produkcję':'Potrzebna ocena klatek'}</strong>${s.blockers.map(b=>`<p>${esc(b.message)}</p>`).join('')}<small>Rewizja ${s.revision} · ${s.assets.length} materiałów${s.reviewApproved?' · przegląd zatwierdzony':s.review?' · przegląd czeka na ocenę':' · bez aktualnej oceny'}</small>`;
 }
 async function openReview(r){
  lastReview=r;const current=r.revision===getProject().revision;
  openModal(modalHeader('PRZEGLĄD NA DOWODACH',`Klatki · rewizja ${r.revision}`,r.limitations)+`<div class="modal-body review-body"><p>Identyfikator przeglądu: <code>${esc(r.id)}</code></p>${r.onionUrl?`<h3>Tor ruchu · nakładka klatek</h3><img class="review-sheet" src="${esc(r.onionUrl)}" alt="Tor ruchu z nałożonych klatek"><p class="inspector-note">Późniejsze klatki mają większą wagę. To wizualizacja próbek całego kadru.</p>`:''}<img class="review-sheet" src="${esc(r.sheetUrl)}" alt="Plansza rzeczywistych klatek filmu"><div class="review-frame-links">${r.frames.map(f=>`<a href="${esc(f.url)}" target="_blank" rel="noopener">${f.time.toFixed(3)} s</a>`).join('')}</div><p>${(r.determinism||[]).filter(x=>x.identicalPixels).length}/${(r.determinism||[]).length} badanych powrotów do czasu dało identyczne piksele.</p><p>${r.errors.length?`Błędy kadru lub tekstu: ${r.errors.length}`:'W badanych klatkach nie wykryto przekroczenia pola tekstu ani kadru.'}</p>${r.errors.map(e=>`<p class="review-error">${esc(e.message)} · ${e.time.toFixed(3)} s · ${esc(e.element_id)}</p>`).join('')}<p class="inspector-note">${r.warnings.length} uwag kontroli struktury. Próbowane klatki nie zastępują obejrzenia całego filmu. Kryteria briefu: ${esc((getProject().production?.rejectionCriteria||[]).join('; ')||'nie podano')}.</p>
   <div class="review-checklist">${Object.entries({'readability':'Teksty są czytelne i nie są ucięte','hierarchy':'Każdy beat ma główny punkt uwagi','brand':'Materiały i branding odpowiadają briefowi','continuity':'Przejścia i ruch zachowują ciągłość','audio':'Sprawdzono dźwięk albo świadomie wybrano ciszę'}).map(([id,label])=>`<label><input type="checkbox" data-review-check="${id}" ${r.checklist[id]?'checked':''}>${label}</label>`).join('')}</div><label class="field">Uwagi do poprawy<textarea id="reviewNotes">${esc(r.notes)}</textarea></label><div class="modal-actions"><button class="secondary-button" data-production-action="reject">Wymaga poprawek</button><button class="primary-button" data-production-action="approve" ${!current||r.errors.length?'disabled':''}>Zatwierdź przegląd</button></div>${!current?'<p>Przegląd jest nieaktualny. Wygeneruj nową planszę.</p>':''}</div>`);
 }
 function beatModal(id){
  const p=getProject(),s=p.scenes.find(s=>s.id===id);if(!s)return;
  const b=s.beat||{};
  openModal(modalHeader('STORYBOARD JAKO STANY',s.name,'Opisz, co widz ma zrozumieć, oraz wejście i wyjście sceny.')+`<div class="modal-body">${field('purpose','Cel beatu',b.purpose)}${field('entryState','Stan wejściowy',b.entryState)}${field('exitState','Stan wyjściowy',b.exitState)}<label class="field">Główny element<select id="beatFocus"><option value="">Wybierz element</option>${p.elements.filter(e=>e.type!=='audio'&&e.start<s.start+s.duration&&e.start+e.duration>s.start).map(e=>`<option value="${e.id}" ${b.focusElementId===e.id?'selected':''}>${esc(e.text||e.type)} · ${esc(e.id)}</option>`).join('')}</select></label><button class="primary-button" data-production-save-beat="${id}">Zapisz beat</button></div>`);
 }
 async function handleClick(event){
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.productionScene)return beatModal(button.dataset.productionScene);
  if(button.dataset.productionSaveBeat){const get=k=>document.querySelector(`[data-production-field="${k}"]`).value;await command('set_scene_beat',{scene_id:button.dataset.productionSaveBeat,beat:{purpose:get('purpose'),entryState:get('entryState'),exitState:get('exitState'),focusElementId:document.querySelector('#beatFocus').value||null}});closeModal();return;}
  if(button.dataset.productionFormat){
   button.disabled=true;try{const next=await call('create_format_variant',{format:button.dataset.productionFormat});ctx.selectProject(next);toast('Osobny wariant gotowy. Dopracuj układ i wykonaj jego przegląd.');}finally{button.disabled=false;}return;
  }
  const action=button.dataset.productionAction;if(!action)return;
  if(action==='add-required'){document.querySelector('#requiredAssets').insertAdjacentHTML('beforeend',requiredRow(getProject()));return;}
  if(action==='remove-required'){button.closest('.required-asset-row').remove();return;}
  button.disabled=true;
  try{
   if(action==='save'){
    const get=k=>document.querySelector(`[data-production-field="${k}"]`).value;
    await command('set_production_contract',{contract:{product:get('product'),message:get('message'),facts:lines(get('facts')),references:lines(get('references')),rejectionCriteria:lines(get('rejectionCriteria')),requireReview:document.querySelector('#requireProductionReview').checked,requiredAssets:[...document.querySelectorAll('.required-asset-row')].map(row=>({label:row.querySelector('[data-required-label]').value,assetId:row.querySelector('[data-required-id]').value||null}))}});
    toast('Brief zapisany we wspólnym projekcie.');
   }
   if(action==='strip'){
    const scene=document.querySelector('#motionScene').value,count=Number(document.querySelector('#motionCount').value);
    const args={count,start:scene?scene+'@0s':'0s',end:scene?scene+'@end':'end'};
    openModal(modalHeader('LABORATORIUM RUCHU','Przygotowuję klatki…','Próbki sceny i nakładka toru.')+'<div class="modal-body" role="status">Renderowanie…</div>');
    try{await openReview(await call('create_motion_strip',args));}catch(e){closeModal();throw e;}
   }
   if(action==='review-list'){
    const data=await call('list_reviews');openModal(modalHeader('ZAPISANE DOWODY','Przeglądy projektu','Identyfikatory do porównania przed / po.')+`<div class="modal-body">${data.reviews.map(r=>`<p><code>${esc(r.id)}</code> · rewizja ${r.revision} · ${r.times.length} klatek</p>`).join('')||'Brak przeglądów'}</div>`);
   }
   if(action==='compare'){
    const r=await call('compare_reviews',{baseline_id:document.querySelector('#baselineReview').value.trim(),review_id:document.querySelector('#changedReview').value.trim()});
    openModal(modalHeader('PORÓWNANIE PIKSELI',r.matched?'Klatki zgodne w tolerancji':'Wykryto różnice',r.limitations)+`<div class="modal-body">${r.frames.map(f=>`<p><a href="${esc(f.diffUrl)}" target="_blank" rel="noopener">${f.time.toFixed(3)} s · ${(f.changedRatio*100).toFixed(2)}% pikseli różni się</a></p>`).join('')}</div>`);
   }
   if(action==='beats')await command('annotate_story_beats');
   if(action==='motion')await command('apply_motion_rules');
   if(action==='review'){
    openModal(modalHeader('KLATKI PRZED EKSPORTEM','Przygotowuję planszę…','Renderer sprawdza sceny i przejścia.')+'<div class="modal-body"><p role="status">Trwa zapis rzeczywistych klatek filmu.</p></div>');
    try{await openReview(await call('create_review'));}catch(e){closeModal();throw e;}
   }
   if(action==='latest'){const s=await call('get_production_status');if(s.review)await openReview(s.review);else toast('Nie ma przeglądu aktualnej rewizji. Wygeneruj planszę.');}
   if(action==='approve'||action==='reject'){
    const checklist=Object.fromEntries([...document.querySelectorAll('[data-review-check]')].map(el=>[el.dataset.reviewCheck,el.checked]));
    await call('review_verdict',{review_id:lastReview.id,verdict:action==='approve'?'approved':'rejected',checklist,notes:document.querySelector('#reviewNotes').value});
    closeModal();await refreshStatus();toast(action==='approve'?'Przegląd aktualnej rewizji zatwierdzony.':'Uwagi zapisane. Popraw montaż i sprawdź nową planszę.');
   }
  }finally{button.disabled=false;}
 }
 return {panel,refreshStatus,handleClick};
}
