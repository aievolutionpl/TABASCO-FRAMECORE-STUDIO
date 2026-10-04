/* Original FrameCore deterministic composition adapter, MIT. */
(() => {
  const p = window.FRAMECORE_PROJECT, tracks = new Map(p.tracks.map(t => [t.id, t]));
  const assets = new Map(p.assets.map(a => [a.id, a])), nodes = new Map();
  let time = 0, playing = false, rate = 1, last = 0, frame;
  const root = document.querySelector('[data-composition-id]');
  root.style.width = p.canvas.width + 'px'; root.style.height = p.canvas.height + 'px';
  root.style.background = p.canvas.background;
  for (const track of p.tracks) {
    for (const e of p.elements.filter(e => e.trackId === track.id)) {
      const n = document.createElement('div'); n.className = 'fc-element'; n.dataset.elementId = e.id;
      n.dataset.trackIndex = p.tracks.indexOf(track); n.dataset.start = e.start; n.dataset.duration = e.duration;
      Object.assign(n.style, {position:'absolute', left:e.x+'px', top:e.y+'px', width:e.width+'px', height:e.height+'px',
        color:e.style.color, fontSize:e.style.fontSize+'px', fontFamily:e.style.fontFamily, fontWeight:e.style.fontWeight,
        textAlign:e.style.align, background:e.style.background, borderRadius:e.style.radius+'px', whiteSpace:'pre-wrap',
        lineHeight:'1.08', display:'flex', alignItems:'center', justifyContent:e.style.align==='center'?'center':e.style.align==='right'?'flex-end':'flex-start'});
      let media;
      if (['image','video','audio'].includes(e.type)) {
        const a = assets.get(e.assetId); media = document.createElement(e.type==='image'?'img':e.type);
        media.src = window.FRAMECORE_ASSET_PREFIX + encodeURIComponent(a.file.split('/').pop());
        media.style.cssText='width:100%;height:100%;object-fit:contain;display:block';
        if(a.provenance?.source==='phosphor_builtin') {
          n.style.maskImage=`url("${media.src}")`;n.style.maskSize='contain';n.style.maskRepeat='no-repeat';n.style.maskPosition='center';
          n.style.background=e.style.color;media.style.opacity=0;
        }
        if (e.type==='video') { media.playsInline=true; media.preload='auto'; media.muted=true; }
        if (e.type==='audio') { media.preload='auto'; media.muted=!!track.muted || !!window.__CAPTURE__; }
        n.append(media);
      } else if (e.type !== 'shape') n.textContent = e.text;
      root.append(n); nodes.set(e.id, {node:n, media});
    }
  }
  const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
  const ease = u => 1-Math.pow(1-u,3);
  function keyed(e,prop,t) {
    const points=(e.keyframes||[]).filter(k=>k.property===prop).sort((a,b)=>a.time-b.time);
    if(!points.length)return e[prop];
    if(t<=points[0].time)return points[0].value;
    for(let i=1;i<points.length;i++)if(t<=points[i].time){const a=points[i-1],b=points[i];return a.value+(b.value-a.value)*(t-a.time)/(b.time-a.time);}
    return points.at(-1).value;
  }
  function paint(t) {
    const waits=[]; time=clamp(t,0,p.duration);
    for (const e of p.elements) {
      const {node:n,media} = nodes.get(e.id), track=tracks.get(e.trackId);
      const local=time-e.start, visible=!track.hidden && local>=0 && local<e.duration;
      n.style.visibility=visible?'visible':'hidden';
      let alpha=1, dx=0,dy=0,scale=1,blur=0;
      const m=e.motion, phase=local+(e.motionOffset||0), u=m?clamp(phase/m.duration):1, z=ease(u);
      if(m) switch(m.id) {
        case 'premium-blur-reveal': alpha=z;dy=(1-z)*28;blur=(1-z)*18;break;
        case 'impact-rise':alpha=z;dy=(1-z)*90;scale=.85+.15*z;break;
        case 'soft-fade':alpha=z;break;
        case 'slide-left':alpha=z;dx=(1-z)*60;break;
        case 'scale-in':alpha=z;scale=.9+.1*z;break;
        case 'word-pop':alpha=z;scale=.65+.35*z+.04*Math.sin(u*Math.PI);break;
        case 'logo-settle':alpha=z;dy=(1-z)*12;break;
        case 'cta-pulse':alpha=z;scale=1+.025*Math.sin(Math.max(0,phase-m.duration)*Math.PI*2);break;
        case 'slide-right':alpha=z;dx=-(1-z)*60;break;
        case 'drop-in':alpha=z;dy=-(1-z)*80;break;
        case 'zoom-out':alpha=z;scale=1.2-.2*z;break;
        case 'rotate-in':alpha=z;scale=.8+.2*z;break;
        case 'bounce-in':alpha=z;dy=-(1-z)*60*Math.cos(u*Math.PI*2);break;
        case 'float':alpha=z;dy=Math.sin(Math.max(0,phase-m.duration)*2)*10;break;
        case 'wipe-left':alpha=1;n.style.clipPath=`inset(0 ${(1-z)*100}% 0 0)`;break;
        case 'wipe-up':alpha=1;n.style.clipPath=`inset(${(1-z)*100}% 0 0 0)`;break;
        case 'focus-in':alpha=z;blur=(1-z)*30;scale=1.04-.04*z;break;
        case 'elastic-pop':alpha=z;scale=.5+.5*z+.1*Math.sin(u*Math.PI*3)*(1-u);break;
        case 'gentle-tilt':alpha=z;dx=(1-z)*20;break;
        case 'cinema-rise':alpha=z;dy=(1-z)*150;blur=(1-z)*4;break;
      }
      if(!['wipe-left','wipe-up'].includes(m?.id))n.style.clipPath='none';
      const tilt=m?.id==='rotate-in'?(1-z)*-18:m?.id==='gentle-tilt'?(1-z)*-8:0;
      n.style.left=keyed(e,'x',local)+'px';n.style.top=keyed(e,'y',local)+'px';
      n.style.opacity=keyed(e,'opacity',local)*alpha; n.style.filter=`blur(${blur}px)`;
      n.style.transform=`translate(${dx}px,${dy}px) rotate(${keyed(e,'rotation',local)+tilt}deg) scale(${keyed(e,'scale',local)*scale})`;
      if (media && ['video','audio'].includes(e.type)) {
        const sourceTime=Math.max(0,e.sourceStart+local);
        media.muted=e.type==='video'||track.muted||!!window.__CAPTURE__;
        if(e.type==='audio') {const a=e.audio||{gain:1,fadeIn:0,fadeOut:0};media.volume=clamp(a.gain*Math.min(1,a.fadeIn?Math.max(0,local)/a.fadeIn:1,a.fadeOut?Math.max(0,e.duration-local)/a.fadeOut:1));}
        if(!visible || !playing) media.pause();
        if(visible && media.readyState>=1 && Math.abs(media.currentTime-sourceTime)>.04) {
          if(window.__CAPTURE__) waits.push(new Promise(resolve=>{
            const done=()=>{media.removeEventListener('seeked',done);resolve();};
            media.addEventListener('seeked',done,{once:true}); media.currentTime=Math.min(sourceTime,Math.max(0,media.duration-.001));
            setTimeout(done,3000);
          }));
          else media.currentTime=Math.min(sourceTime,Math.max(0,media.duration-.001));
        }
        if(visible&&playing) media.play().catch(()=>{});
      }
    }
    return Promise.all(waits);
  }
  function tick(now) {
    if(!playing)return;
    paint(time+(now-last)/1000*rate); last=now;
    if(time>=p.duration){playing=false;return;}
    frame=requestAnimationFrame(tick);
  }
  const timeline={duration:()=>p.duration,time:()=>time,seek:t=>paint(t),
    play:()=>{if(time>=p.duration)paint(0);if(!playing){playing=true;last=performance.now();frame=requestAnimationFrame(tick);}},
    pause:()=>{playing=false;cancelAnimationFrame(frame);for(const {media} of nodes.values())if(media?.pause)media.pause();},
    timeScale:r=>{rate=r;}};
  window.__timelines={framecore:timeline}; window.seek=paint; window.DURATION=p.duration;
  window.TEXTS=t=>p.elements.filter(e=>['text','caption'].includes(e.type)&&e.start<=t&&t<e.start+e.duration).map(e=>({id:e.id,text:e.text,x0:e.x,y0:e.y,x1:e.x+e.width,y1:e.y+e.height,caption:e.type==='caption'}));
  window.__ready=Promise.all([...nodes.values()].map(({media})=>{
    if(!media)return Promise.resolve();
    if(media.tagName==='IMG')return media.decode();
    if(media.readyState>=2)return Promise.resolve();
    return new Promise((resolve,reject)=>{media.addEventListener('loadeddata',resolve,{once:true});media.addEventListener('error',()=>reject(new Error('Media load failed')),{once:true});});
  })).then(()=>paint(0)).then(()=>{window.READY=true;});
  paint(0);
})();
