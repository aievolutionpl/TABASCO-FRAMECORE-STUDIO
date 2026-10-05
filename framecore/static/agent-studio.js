/* Integrated agent, connection setup and a replayable first-run tour. */
(() => {
  const el = (s) => document.querySelector(s);
  let agentStatus, currentJob, polling, running = false;
  const html = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (path, body) => {
    const response = await fetch(path, {method:body === undefined ? 'GET':'POST', headers:{'Content-Type':'application/json','X-Studio-Token':window.STUDIO_TOKEN}, body:body === undefined ? undefined:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Nie udało się wykonać operacji.');
    return result;
  };
  document.head.insertAdjacentHTML('beforeend','<link rel="stylesheet" href="/static/agent-studio.css">');
  el('.top-actions').insertAdjacentHTML('afterbegin','<button id="studioTour" class="quiet-button" title="Samouczek">Jak zacząć</button><button id="studioConnect" class="quiet-button">Integracje</button><button id="studioAgent" class="agent-launch"><span class="agent-orb"></span> Twój agent</button>');
  document.body.insertAdjacentHTML('beforeend', `
    <aside id="agentDrawer" class="agent-drawer" hidden aria-label="Rozmowa z agentem">
      <header><div><span class="eyebrow">TWÓJ PARTNER W MONTAŻU</span><h2>Od pomysłu do filmu.</h2></div><button id="closeAgent" class="icon-button" aria-label="Zamknij agenta">×</button></header>
      <div class="agent-connection"><span id="agentConnection">Sprawdzam połączenie…</span><button id="agentSettings">Ustawienia</button></div>
      <div id="agentMessages" class="agent-messages" aria-live="polite"><article class="agent-message"><strong>Zróbmy coś dobrego.</strong><p>Opisz film lub zmianę. Widzę bieżący projekt, zaznaczenie i oś czasu. Moje zmiany możesz cofnąć.</p></article>
      <div class="agent-starters"><button data-prompt="Przeczytaj projekt i zaproponuj trzy konkretne ulepszenia montażu. Na razie nic nie zmieniaj.">Oceń mój montaż ↗</button><button data-prompt="Sprawdź zaznaczenie i dobierz czytelną animację wejścia. Zastosuj zmianę, zachowując czas klipu.">Ożyw zaznaczony klip ↗</button><button data-prompt="Sprawdź projekt: układ, długość scen i czytelność tekstów. Opisz znalezione problemy.">Sprawdź przed eksportem ↗</button></div></div>
      <form id="assistantForm"><label for="assistantPrompt">Co tworzymy?</label><textarea id="assistantPrompt" maxlength="12000" rows="3" placeholder="Np. skróć nagłówek, dodaj wejście i zostaw 5 sekund na każdą scenę…" required></textarea><div class="agent-compose-footer"><span>Zmiany trafiają do wspólnej historii.<br>Wywołania API mogą być płatne.</span><button type="button" id="cancelAgent" hidden>Zatrzymaj</button><button id="sendAgent" class="primary-button">Wyślij ↗</button></div></form>
    </aside>
    <dialog id="connectionDialog" class="studio-dialog"><form id="connectionForm"><header><div><span class="eyebrow">POŁĄCZ SWÓJ MODEL</span><h2>Agent, którego wybierasz.</h2></div><button type="button" data-close-dialog="connectionDialog" aria-label="Zamknij">×</button></header><p class="dialog-intro">Agent może układać sceny, edytować klipy i uruchamiać eksport. Pracuje na tym samym projekcie co Ty.</p>
      <div class="form-grid"><label>Dostawca<select id="assistantProvider"><option value="openrouter">OpenRouter</option><option value="openai">OpenAI</option></select></label><label>Model<input id="assistantModel" list="assistantModels" value="openai/gpt-4.1-mini" maxlength="160" required><datalist id="assistantModels"></datalist></label></div>
      <label>Klucz API<input id="assistantKey" type="password" autocomplete="off" placeholder="Wklej klucz tutaj — nigdy w rozmowie"></label><p class="field-note">Klucz jest przechowywany lokalnie na tym komputerze, poza projektem i repozytorium. Do dostawcy trafiają polecenia oraz dane montażu. Obsługujemy też zmienne OPENROUTER_API_KEY i OPENAI_API_KEY.</p>
      <div id="connectionFeedback" class="connection-feedback" role="status"></div><div class="dialog-buttons"><button type="button" id="forgetKey">Usuń zapisany klucz</button><button type="button" id="loadModels">Pobierz modele</button><button type="button" id="testAgent">Test połączenia</button><button class="primary-button">Zapisz</button></div><p class="field-note">Test wysyła krótkie zapytanie do modelu i może zużyć niewielką liczbę tokenów. Pobieranie katalogu modeli nie uruchamia montażu.</p>
    </form></dialog>
    <dialog id="tourDialog" class="studio-dialog tour-dialog"><header><span class="eyebrow">FRAMECORE / PIERWSZY FILM</span><button data-close-dialog="tourDialog" aria-label="Zamknij samouczek">×</button></header><div id="tourContent"></div><footer><span id="tourCount"></span><div><button id="tourBack">Wstecz</button><button id="tourNext" class="primary-button">Dalej →</button></div></footer></dialog>`);

  const message = (text, kind='agent') => {
    const node = document.createElement('article'); node.className = 'agent-message '+kind;
    node.textContent = text; el('#agentMessages').append(node); node.scrollIntoView({block:'nearest'}); return node;
  };
  async function refreshStatus() {
    try { agentStatus = await api('/api/assistant/status'); el('#agentConnection').textContent = agentStatus.configured ? agentStatus.model : 'Dodaj klucz, aby rozpocząć'; el('#studioAgent').classList.toggle('connected',agentStatus.configured); }
    catch { el('#agentConnection').textContent = 'Połączenie ze studiem niedostępne'; }
  }
  async function settings() {
    await refreshStatus();
    if (agentStatus) { el('#assistantProvider').value = agentStatus.provider; el('#assistantModel').value = agentStatus.model; }
    el('#assistantKey').value = ''; el('#connectionFeedback').textContent = agentStatus?.configured ? 'Klucz jest skonfigurowany. Puste pole zachowa dotychczasowy klucz.' : 'Wybierz dostawcę i dodaj klucz.';
    el('#connectionDialog').showModal();
    let health=el('#runtimeChecks');
    if(!health){health=document.createElement('div');health.id='runtimeChecks';health.className='runtime-checks';el('#connectionForm').append(health);}
    health.textContent='Sprawdzam narzędzia lokalne…';
    try{const data=await api('/api/runtime');health.innerHTML='<strong>Gotowość studia</strong>'+data.checks.map(c=>`<div>${c.ok?'✓':'!'} ${html(c.label)}${c.ok?'':` — ${html(c.fix)}`}</div>`).join('');}catch(error){health.textContent=error.message;}
  }
  async function saveSettings(extra={}) {
    const result = await api('/api/assistant/settings',{provider:el('#assistantProvider').value, model:el('#assistantModel').value.trim(), api_key:el('#assistantKey').value,...extra});
    el('#assistantKey').value = ''; await refreshStatus(); return result;
  }
  async function connectionAction(action) {
    const buttons = el('#connectionDialog').querySelectorAll('button'); buttons.forEach(b=>b.disabled=true);
    el('#connectionFeedback').textContent = 'Łączenie…';
    try {
      await saveSettings();
      if(action==='models') { const data=await api('/api/assistant/models',{}); el('#assistantModels').innerHTML=data.models.map(m=>`<option value="${html(m.id)}">${html(m.name)}</option>`).join(''); el('#connectionFeedback').textContent=`Dostępne modele: ${data.models.length}. Wybierz model z listy lub wpisz identyfikator.`; }
      else { const data=await api('/api/assistant/test',{}); el('#connectionFeedback').textContent=`Połączenie działa. Model: ${data.model}.`; }
    } catch(error) { el('#connectionFeedback').textContent=error.message; }
    finally { buttons.forEach(b=>b.disabled=false); }
  }
  el('#studioAgent').onclick = () => { el('#agentDrawer').hidden=!el('#agentDrawer').hidden; refreshStatus(); if(!el('#agentDrawer').hidden)el('#assistantPrompt').focus(); };
  el('#closeAgent').onclick = () => el('#agentDrawer').hidden=true;
  el('#studioConnect').onclick=el('#agentSettings').onclick=settings;
  el('#assistantProvider').onchange=()=>{el('#assistantModel').value=el('#assistantProvider').value==='openrouter'?'openai/gpt-4.1-mini':'gpt-4.1-mini';el('#assistantKey').value='';};
  document.querySelectorAll('[data-close-dialog]').forEach(b=>b.onclick=()=>el('#'+b.dataset.closeDialog).close());
  el('#connectionForm').onsubmit=async e=>{e.preventDefault();try{await saveSettings();el('#connectionFeedback').textContent='Ustawienia zapisane.';}catch(error){el('#connectionFeedback').textContent=error.message;}};
  el('#testAgent').onclick=()=>connectionAction('test'); el('#loadModels').onclick=()=>connectionAction('models');
  el('#forgetKey').onclick=async()=>{try{await saveSettings({clear_key:true});el('#connectionFeedback').textContent=agentStatus.configured?'Usunięto zapisany klucz. Nadal działa klucz ze zmiennej środowiskowej.':'Klucz usunięty.';}catch(error){el('#connectionFeedback').textContent=error.message;}};
  document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{el('#assistantPrompt').value=b.dataset.prompt;el('#assistantPrompt').focus();});
  function setRunning(value) { running=value;el('#sendAgent').disabled=value;el('#cancelAgent').hidden=!value;el('#assistantPrompt').disabled=value; }
  el('#assistantForm').onsubmit=async e=>{
    e.preventDefault(); if(running)return;
    const project = window.framecoreContext?.();
    if(!project){message('Najpierw otwórz projekt.');return;}
    const prompt=el('#assistantPrompt').value.trim(); if(!prompt)return;
    setRunning(true);message(prompt,'human');el('#assistantPrompt').value='';
    const progress=message('Agent czyta projekt…','progress'); let seen=0;
    try {
      const job=await api('/api/assistant/run',{project_id:project.id,prompt}); currentJob=job.id;
      const poll=async()=>{
        try {
          const next=await api('/api/assistant/job/'+currentJob);
          for(const event of next.events.slice(seen)){ const row=document.createElement('div');row.className='agent-event';row.textContent=(event.ok?'✓ ':'! ')+event.tool+(event.message?' — '+event.message:'');progress.append(row); }
          seen=next.events.length;
          if(next.status==='running'){polling=setTimeout(poll,900);return;}
          message(next.status==='cancelled'?'Zatrzymano. Wykonane zmiany możesz cofnąć.':next.reply);setRunning(false);currentJob=null;
        } catch(error){message(error.message);setRunning(false);}
      };poll();
    }catch(error){progress.textContent=error.message;setRunning(false);}
  };
  el('#cancelAgent').onclick=async()=>{if(currentJob){try{await api('/api/assistant/cancel',{job_id:currentJob});message('Zatrzymuję po bieżącym wywołaniu.');}catch(error){message(error.message);}}};

  const slides=[
    ['Twoja historia. Wspólna rama.','Od materiałów do gotowego filmu — razem z agentem lub samodzielnie. Wszystkie zmiany zapisują się lokalnie.','01 / STUDIO','Utwórz projekt, wybierz format 16:9, 9:16 albo kwadrat i określ długość filmu.'],
    ['Najpierw dobry materiał.','W panelu Materiały dodaj zdjęcia, nagrania i dźwięk. Biblioteka, Tła i Szablony dają Ci gotowy punkt startowy.','02 / MATERIAŁY','Przeciągnij plik do studia. Wybierz szablon i obejrzyj plan scen przed zbudowaniem montażu.'],
    ['Nadaj scenom rytm.','Zaznacz klip na osi czasu. Właściwości zmieniają tekst, położenie i długość. Animacje nadają mu wejście.','03 / MONTAŻ','Spacja odtwarza podgląd. Ctrl/Cmd + Z cofa zmianę. Klipy można przycinać, dzielić i przesuwać.'],
    ['Zaproś swojego agenta.','W Integracjach wybierz OpenRouter lub OpenAI, dodaj klucz i przetestuj model. Następnie otwórz Twój agent.','04 / WSPÓŁPRACA','Agent widzi projekt i zaznaczenie. Napisz: „Dodaj animację wejścia do zaznaczonego nagłówka”. Operacje zobaczysz w rozmowie i historii.'],
    ['Obejrzyj. Popraw. Wyeksportuj.','Sprawdź każdą scenę oraz dźwięk, a potem wybierz Eksport. Gotowy MP4 pozostaje na Twoim komputerze.','05 / GOTOWY FILM','Do eksportu potrzebne są FFmpeg i Chromium. Agent może sprawdzić strukturę, ale ostateczny wygląd oceniasz w podglądzie.']
  ];
  let slide=0;
  function paintTour(){const s=slides[slide];el('#tourContent').innerHTML=`<div class="tour-art"><span class="tour-frame"></span><span>${s[2]}</span></div><h1>${s[0]}</h1><p>${s[1]}</p><div class="tour-tip">${s[3]}</div>`;el('#tourCount').textContent=`${slide+1} / ${slides.length}`;el('#tourBack').disabled=slide===0;el('#tourNext').textContent=slide===slides.length-1?'Zaczynam tworzyć ↗':'Dalej →';}
  el('#studioTour').onclick=()=>{slide=0;paintTour();el('#tourDialog').showModal();};
  el('#tourBack').onclick=()=>{slide=Math.max(0,slide-1);paintTour();};
  el('#tourNext').onclick=()=>{if(slide===slides.length-1){localStorage.setItem('framecore-onboarding-v2','done');el('#tourDialog').close();}else{slide++;paintTour();}};
  el('#tourDialog').addEventListener('close',()=>localStorage.setItem('framecore-onboarding-v2','done'));
  if(!localStorage.getItem('framecore-onboarding-v2')){paintTour();el('#tourDialog').showModal();}
  // Keep the existing proposal/CLI dashboard available alongside tool-calling chat.
  const integrations=document.createElement('div');integrations.className='dialog-buttons';
  integrations.innerHTML='<button type="button" id="openCliAgents">Codex / Claude · zadania</button><button type="button" data-mcp-config>Konfiguracja MCP</button>';
  el('#connectionForm').append(integrations);
  el('#openCliAgents').onclick=()=>{el('#connectionDialog').close();el('#agentDrawer').hidden=true;window.framecoreAgentDashboard?.();};
  refreshStatus();
  document.addEventListener('click',async e=>{
    if(!e.target.closest('[data-mcp-config]'))return;
    e.preventDefault();e.stopImmediatePropagation();
    try{const config=await api('/api/mcp-config');el('#connectionDialog').close();const target=el('#modalContent');target.innerHTML='<div class="modal-header"><h2>Połącz agenta przez MCP</h2><button data-close>×</button></div><div class="modal-body"><p>Konfiguracja dla tego komputera i aktualnego katalogu projektów.</p><pre class="connect-code">'+html(JSON.stringify(config,null,2))+'</pre><p>Najpierw: get_editing_guide → get_project → get_selection. Pełna instrukcja: docs/AGENT_QUICKSTART.md.</p></div>';el('#modal').showModal();}catch(error){message(error.message);}
  },true);
})();
