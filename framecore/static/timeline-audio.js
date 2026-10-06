/* Real media peaks, cropped in source time. Derived caches never change edits. */
export function createTimelineAudio({getProject,request}){
 const cache=new Map();
 function paint(){
  const p=getProject();if(!p)return;
  for(const canvas of document.querySelectorAll('[data-waveform]')){
   const e=p.elements.find(e=>e.id===canvas.dataset.waveform);if(!e)continue;
   const data=cache.get(p.id+':'+e.assetId);canvas.dataset.waveformState=data?.status||'loading';canvas.title=data?.wave?'Przebieg amplitudy źródła':data?.status==='unavailable'?'Analiza dźwięku niedostępna':'Analizowanie dźwięku…';
   if(data?.wave){
    const wave=data.wave, width=Math.max(1,Math.ceil(canvas.getBoundingClientRect().width)),height=30;
    canvas.width=Math.min(2048,width);canvas.height=height;
    const ctx=canvas.getContext('2d'),gain=e.audio?.gain??1;ctx.clearRect(0,0,canvas.width,height);ctx.fillStyle='#6ff0c4';
    for(let x=0;x<canvas.width;x++){
     const from=e.sourceStart+x/canvas.width*e.duration,to=e.sourceStart+(x+1)/canvas.width*e.duration;
     let peak=0;const lo=Math.floor(from/wave.seconds_per_bin),hi=Math.max(lo+1,Math.ceil(to/wave.seconds_per_bin));
     for(let i=Math.max(0,lo);i<Math.min(hi,wave.peaks.length);i++)peak=Math.max(peak,wave.peaks[i]);
     const local=(x+.5)/canvas.width*e.duration,a=e.audio||{};
     const fade=Math.min(1,a.fadeIn?local/a.fadeIn:1,a.fadeOut?(e.duration-local)/a.fadeOut:1);
     const h=Math.min(14,peak*gain*fade*14);ctx.fillRect(x,15-h,1,Math.max(1,2*h));
    }
   }
   if(!data||Date.now()-data.checked>30000)load(p.id,e.assetId);
  }
 }
 async function load(pid,aid){
  const key=pid+':'+aid;cache.set(key,{status:'loading',checked:Date.now()});
  try{
   let report=await request('/api/command',{name:'analyze_media',args:{project_id:pid,asset_id:aid}});
   for(let retry=0;['queued','running'].includes(report.status)&&retry<120;retry++){
    await new Promise(resolve=>setTimeout(resolve,500));
    if(getProject()?.id!==pid){cache.delete(key);return;}
    report=await request('/api/command',{name:'get_media_analysis',args:{project_id:pid,asset_id:aid}});
   }
   if(report.status!=='ready'||!report.urls?.['waveform.json'])throw Error('Waveform niedostępny');
   const wave=await request(report.urls['waveform.json']);cache.set(key,{status:'ready',wave,checked:Date.now()});
  }catch{cache.set(key,{status:'unavailable',checked:Date.now()});}
  if(getProject()?.id===pid)paint();
 }
 return {paint};
}
