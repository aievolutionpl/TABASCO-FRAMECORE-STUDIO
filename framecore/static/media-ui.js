/* Derived-media panel. Project mutations stay in the shared command API. */
export function createMediaUI({getProject, request, esc, openModal, modalHeader, toast}) {
  let generation=0, timer;
  const labels={not_started:'Nie analizowano',queued:'W kolejce',running:'Analizowanie…',ready:'Gotowe',failed:'Błąd analizy'};
  async function open() {
    const project=getProject(); if(!project)return;
    const pid=project.id, token=++generation;
    clearTimeout(timer);
    const assets=project.assets.filter(a=>['image','video','audio'].includes(a.kind));
    openModal(modalHeader('MEDIA ENGINE','Analiza materiałów','Miniatury, proxy i analiza dźwięku. Oryginały oraz historia projektu pozostają bez zmian.')+
      `<div class="modal-body"><label>Materiał<select id="mediaAnalysisAsset">${assets.map(a=>`<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select></label><button class="primary-button" id="startMediaAnalysis" ${assets.length?'':'disabled'}>Analizuj materiał</button><div id="mediaAnalysisResult" aria-live="polite"></div></div>`);
    const select=document.querySelector('#mediaAnalysisAsset'), result=document.querySelector('#mediaAnalysisResult');
    let selection=0;
    const active=()=>generation===token && result.isConnected && document.querySelector('#modal').open && getProject()?.id===pid;
    const call=(name,aid)=>request('/api/command',{name,args:{project_id:pid,asset_id:aid}});
    async function refresh() {
      clearTimeout(timer); const turn=++selection, aid=select.value;
      if(!aid){result.textContent='Dodaj najpierw materiał do projektu.';return;}
      try {
        const report=await call('get_media_analysis',aid);
        if(!active()||turn!==selection)return;
        const meta=report.metadata||{}, urls=report.urls||{};
        result.innerHTML=`<h3>${esc(labels[report.status]||report.status)}</h3>${report.error?`<p>${esc(report.error)}</p>`:''}
          <p>${esc(meta.kind||'')}${meta.width?` · ${meta.width} × ${meta.height}`:''}${meta.duration?` · ${meta.duration.toFixed(2)} s`:''}</p>
          ${urls['thumbnail.jpg']?`<img src="${esc(urls['thumbnail.jpg'])}" alt="Miniatura materiału" style="max-width:100%;max-height:200px">`:''}
          ${urls['contact-sheet.jpg']?`<img src="${esc(urls['contact-sheet.jpg'])}" alt="Sześć klatek materiału" style="width:100%">`:''}
          ${urls['proxy.mp4']?`<p><a href="${esc(urls['proxy.mp4'])}" target="_blank" rel="noopener">Otwórz proxy 640 px</a> · Eksport filmu nadal używa oryginału.</p>`:''}
          ${urls['waveform.json']?'<canvas id="mediaWaveform" width="640" height="100" aria-label="Przebieg amplitudy dźwięku" style="width:100%;background:#171b1c"></canvas><p id="mediaSilence"></p>':''}`;
        if(urls['waveform.json']) {
          const audio=await request(urls['waveform.json']);
          if(!active()||turn!==selection)return;
          const canvas=result.querySelector('canvas'),ctx=canvas.getContext('2d');ctx.strokeStyle='#f05b36';ctx.beginPath();
          audio.peaks.forEach((v,i)=>{const x=i/audio.peaks.length*640;ctx.moveTo(x,50-v*46);ctx.lineTo(x,50+v*46);});ctx.stroke();
          result.querySelector('#mediaSilence').textContent=`Odcinki ciszy: ${audio.silence.length} (próg −40 dB, minimum 0,3 s).`;
        }
        if(['queued','running'].includes(report.status)&&active())timer=setTimeout(refresh,1200);
      } catch(error){if(active())result.textContent=error.message;}
    }
    select.addEventListener('change',refresh);
    document.querySelector('#startMediaAnalysis').addEventListener('click',async()=>{
      const aid=select.value;try{await call('analyze_media',aid);if(active())await refresh();}catch(error){toast(error.message);}
    });
    await refresh();
  }
  document.addEventListener('click',event=>{if(event.target.closest('[data-media-analysis]'))open().catch(error=>toast(error.message));});
  return {open};
}
