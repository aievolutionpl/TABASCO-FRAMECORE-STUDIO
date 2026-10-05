/* Dashboard agent connections; keys never enter browser storage. */
export function createAgentUI(ctx){
 const {request,getProject,getDraft,esc,openModal,closeModal,modalHeader,toast,refreshProject}=ctx;
 let current=null,lastTask='';
 const api=(action,body={})=>request('/api/agent/'+action,body);
 function controls(draft={auto:false}){return `<div class="agent-connection"><p id="agentConnectionStatus" role="status">${current?.connected?esc(current.provider)+' · '+esc(current.model||'model domyślny'):'Połącz OpenAI / Claude / OpenRouter'}</p><label class="production-toggle"><input id="agentAutoApply" type="checkbox" ${draft.auto?'checked':''}> Agent stosuje zmiany samodzielnie</label><button class="primary-button" data-agent-action="run">Zleć agentowi</button><button class="secondary-button" data-agent-action="stop">Zatrzymaj</button><div id="agentTaskStatus" aria-live="polite"></div><p class="inspector-note">Domyślnie otrzymasz propozycję do przejrzenia. Samodzielne sterowanie zapisuje jeden krok cofania dla zadania. Zmiany człowieka mają ochronę rewizji.</p></div>`;}
 async function connectModal(){
  current=await api('status');
  openModal(modalHeader('AGENT PRZEJMUJE MONTAŻ','Połącz agenta','Subskrypcja przez lokalne CLI albo własny klucz OpenRouter.')+`<div class="modal-body"><label class="field">Połączenie<select id="agentProvider"><option value="openrouter">OpenRouter · API</option><option value="codex">OpenAI · Codex CLI</option><option value="claude">Claude · Claude Code CLI</option></select></label><label class="field">Model<input id="agentModel" placeholder="np. openai/gpt-4.1"></label><label class="field" id="agentKeyField">Klucz OpenRouter<input id="agentApiKey" type="password" autocomplete="off" spellcheck="false" placeholder="Klucz pozostaje wyłącznie w pamięci serwera"></label><p id="agentProviderHint" class="inspector-note"></p><p class="inspector-note">Przy zleceniu polecenie, opisy projektu i katalog zasobów trafią do wybranego dostawcy. Pliki obrazów i filmów pozostają lokalne. API jest rozliczane osobno od subskrypcji. CLI korzysta z Twojego wcześniejszego logowania.</p><div class="modal-actions"><button class="primary-button" data-agent-action="connect">Połącz</button><button class="secondary-button" data-agent-action="disconnect">Rozłącz i usuń klucz z pamięci</button></div><details class="production-section"><summary>Logowanie subskrypcją na komputerze</summary><p>Zainstaluj Codex CLI lub Claude Code oficjalną metodą, a potem zaloguj się w terminalu:</p><pre class="connect-code">codex login\nclaude auth login</pre><p>Uruchom studio na tym samym komputerze i koncie systemowym. Dostęp przez subskrypcję zależy od planu, limitów i zasad dostawcy; studio nie zamienia abonamentu na klucz API.</p></details><details class="production-section"><summary>Zewnętrzny agent przez MCP</summary><p>Możesz także podłączyć pełnego klienta MCP z pomocą <a href="https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/blob/main/MCP_SPEC.md" target="_blank" rel="noopener">instrukcji projektu</a>.</p></details></div>`);
  const select=document.querySelector('#agentProvider');if(current.connected)select.value=current.provider;
  document.querySelector('#agentModel').value=current.model||'';
  const hint=()=>{
   const mode=select.value;document.querySelector('#agentKeyField').hidden=mode!=='openrouter';document.querySelector('#agentApiKey').value='';
   document.querySelector('#agentProviderHint').textContent=mode==='openrouter'?'Wpisz klucz i identyfikator modelu dostępnego w OpenRouter.':current.available[mode]?'CLI jest zainstalowane. Pierwsze zadanie sprawdzi dostęp do zalogowanego konta.':'CLI nie znaleziono na komputerze uruchamiającym studio. Zainstaluj je i zaloguj się w terminalu.';
  };select.addEventListener('change',hint);hint();
 }
 async function refresh(){
  if(!document.querySelector('#agentConnectionStatus')&&!current?.task)return;
  const s=await api('status');current=s;
  const box=document.querySelector('#agentConnectionStatus');if(box)box.textContent=s.connected?s.provider+' · '+(s.model||'model domyślny'):'Agent nie jest połączony';
  const t=s.task,taskBox=document.querySelector('#agentTaskStatus');
  if(taskBox)taskBox.textContent=t?({queued:'W kolejce',running:'Agent pracuje',proposed:'Propozycja gotowa',applied:'Zmiany zastosowane',complete:'Gotowe',draft:'Szkic profilu gotowy',failed:'Błąd',cancelled:'Zatrzymano'}[t.status]||t.status)+' · '+t.message:'';
  if(t?.project_id&&!['queued','running'].includes(t.status)&&lastTask!==t.id+':'+t.status){lastTask=t.id+':'+t.status;await refreshProject(t.project_id);}
 }
 async function handle(event){
  const b=event.target.closest('[data-agent-action]');if(!b)return;
  b.disabled=true;
  try{
   const action=b.dataset.agentAction;
   if(action==='connect'){
    const provider=document.querySelector('#agentProvider').value,model=document.querySelector('#agentModel').value.trim(),key=document.querySelector('#agentApiKey').value;
    document.querySelector('#agentApiKey').value='';current=await api('connect',{provider,model,api_key:provider==='openrouter'?key:''});closeModal();toast('Połączenie przygotowane. Zleć zadanie, aby sprawdzić konto i model.');await refresh();
   }
   if(action==='disconnect'){current=await api('disconnect');closeModal();await refresh();toast('Rozłączono agenta. Klucz usunięty z pamięci.');}
   if(action==='stop'){current=await api('stop');await refresh();}
   if(action==='run'){
    const p=getProject(),draft=getDraft(),prompt=draft.prompt,auto_apply=draft.auto;current=await api('status');
    if(!current.connected){await connectModal();return;}
    const task=await api('run',{project_id:p.id,expected_revision:p.revision,prompt,auto_apply});current.task=task;await refresh();
   }
  }catch(e){toast(e.message);}finally{b.disabled=false;}
 }
 function start(){document.addEventListener('click',handle);setInterval(()=>refresh().catch(()=>{}),1000);}
 return {controls,connectModal,start};
}
