/* Editable story arc, voiceover script and semantic transition notes. */
export function createLessonUI(ctx){
 const {getProject,call,command,esc,openModal,closeModal,modalHeader,toast}=ctx;
 const $=s=>document.querySelector(s);
 let plan=null,planProject=null;
 const labels={topic:'Temat',audience:'Odbiorcy',coreIdea:'Główna myśl do zrozumienia',misconception:'Typowe błędne przekonanie',openingQuestion:'Pytanie otwierające'};
 function open(){const p=getProject(),b=p.lesson||{};plan=null;planProject=p.id;openModal(modalHeader('HISTORIA, KTÓRA WYJAŚNIA','Lekcja przez historię','Pytanie → przykład → problem → mechanizm → odkrycie → konsekwencja → odpowiedź.')+`<div class="modal-body">${Object.entries(labels).map(([k,n])=>`<label class="field">${n}<textarea data-lesson-brief="${k}" rows="2">${esc(b[k]||((k==='topic')?p.metadata.name:''))}</textarea></label>`).join('')}<label class="field">Długość · s<input id="lessonDuration" type="number" min="7" max="600" value="${p.lesson?p.duration:75}"></label><label class="production-toggle"><input id="lessonPaper" type="checkbox" ${p.brandProfile?'':'checked'}> Zastosuj papierowy kierunek zamiast obecnego wyglądu</label><p class="inspector-note">Opcjonalny kierunek: krem, węgiel i koral, font Manrope, 24 FPS. Plan jest punktem wyjścia — agent lub człowiek uzupełnia wyjaśnienie, obraz i narrację. Bramka przeglądu będzie włączona.</p><button class="primary-button" data-lesson="plan">Przygotuj edytowalny plan</button><div id="lessonPlan"></div></div>`);}
 async function prepare(){
  const brief=Object.fromEntries([...document.querySelectorAll('[data-lesson-brief]')].map(e=>[e.dataset.lessonBrief,e.value]));
  plan=await call('plan_visual_lesson',{brief,duration:Number($('#lessonDuration').value)});
  $('#lessonPlan').innerHTML=`<div class="lesson-plan">${plan.scenes.map((s,i)=>`<label class="field"><strong>${i+1}. ${esc(s.name)}</strong><textarea data-lesson-message="${i}">${esc(s.message)}</textarea></label>`).join('')}</div><label class="production-toggle"><input id="lessonReplace" type="checkbox"> Zastąp obecny montaż (można cofnąć)</label><p class="inspector-note">Powstaną zwykłe teksty, kształty i podpisy na timeline. ${esc(plan.note)} Obrazy, lektor i przejścia wymagają dalszej pracy.</p><button class="primary-button" data-lesson="assemble">Zbuduj plan na osi czasu</button>`;
 }
 function sceneModal(id){
  const scene=getProject().scenes.find(s=>s.id===id);if(!scene)return;
  const b=scene.lesson||{};
  openModal(modalHeader('JEDNA SCENA · JEDEN CEL',scene.name,'Tekst lektora, wizualna odpowiedź i przejście są oddzielne od nagłówka.')+`<div class="modal-body">${[['purpose','Cel nauki'],['narration','Tekst lektora'],['visual','Co pokazuje obraz'],['transition','Co przechodzi w następną scenę'],['audio','Muzyka, efekty i dźwięki potrzebne w scenie']].map(([k,n])=>`<label class="field">${n}<textarea data-lesson-scene-field="${k}" rows="3">${esc(b[k])}</textarea></label>`).join('')}<p class="inspector-note">Orientacyjny cel: 125–145 słów/min. Tekst nie tworzy audio. Po wgraniu lektora dopasuj klip i napisy na timeline.</p><button class="primary-button" data-lesson-save-scene="${id}">Zapisz opis sceny</button></div>`);
 }
 function start(){$('#modalContent').addEventListener('input',e=>{if(e.target.matches('[data-lesson-brief]')||e.target.id==='lessonDuration'){plan=null;$('#lessonPlan')?.replaceChildren();}});document.addEventListener('click',async e=>{const b=e.target.closest('[data-lesson],[data-lesson-scene],[data-lesson-save-scene]');if(!b)return;b.disabled=true;try{
  if(b.dataset.lesson==='open')open();
  if(b.dataset.lesson==='plan')await prepare();
  if(b.dataset.lesson==='assemble'){
   if(getProject().id!==planProject)throw Error('Projekt zmienił się; otwórz plan ponownie.');
   plan.scenes.forEach((s,i)=>{s.message=$(`[data-lesson-message="${i}"]`).value;s.lesson.purpose=s.message;});
   await command('assemble_visual_lesson',{brief:plan.brief,scenes:plan.scenes,duration:plan.duration,replace:$('#lessonReplace').checked,paper_style:$('#lessonPaper').checked});closeModal();toast('Plan na timeline. Uzupełnij sceny i wygeneruj przegląd.');
  }
  if(b.dataset.lessonScene)sceneModal(b.dataset.lessonScene);
  if(b.dataset.lessonSaveScene){const lesson=Object.fromEntries([...document.querySelectorAll('[data-lesson-scene-field]')].map(e=>[e.dataset.lessonSceneField,e.value]));await command('set_scene_learning',{scene_id:b.dataset.lessonSaveScene,lesson});closeModal();toast('Opis sceny zapisany dla człowieka i agenta.');}
  if(b.dataset.lesson==='check'){const s=await call('get_lesson_status');openModal(modalHeader('KONTROLA TREŚCI','Przejrzyj lekcję',s.note)+`<div class="modal-body">${s.issues.map(i=>`<p>${esc(i.message)}</p>`).join('')||'<p>Opisy są uzupełnione; sprawdź teraz rzeczywisty film.</p>'}<ul>${s.reviewChecklist.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`);}
 }catch(err){toast(err.message);}finally{b.disabled=false;}});}
 return {start};
}
