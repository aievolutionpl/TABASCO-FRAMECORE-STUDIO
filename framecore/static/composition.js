/* Original FrameCore deterministic composition adapter, MIT. */
(() => {
  const p = window.FRAMECORE_PROJECT, tracks = new Map(p.tracks.map(t => [t.id, t]));
  const assets = new Map(p.assets.map(a => [a.id, a])), nodes = new Map();
  let time = 0, playing = false, rate = 1, last = 0, frame;
  const root = document.querySelector('[data-composition-id]');
  root.style.width = p.canvas.width + 'px'; root.style.height = p.canvas.height + 'px';
  root.style.background = p.canvas.background;
  const bg=window.FRAMECORE_BACKGROUND, back=document.createElement('div');
  back.className='fc-background';back.style.cssText='position:absolute;inset:0;overflow:hidden;pointer-events:none';root.append(back);
  const orbs=[];
  if(bg){
    back.style.background=bg.preview;
    if(bg.kind==='grid')back.style.background=`linear-gradient(${bg.colors[1]} 1px, transparent 1px),linear-gradient(90deg,${bg.colors[1]} 1px,transparent 1px),${bg.colors[0]}`;
    if(bg.kind==='dots')back.style.background=`radial-gradient(${bg.colors[1]} 1.5px,transparent 1.5px),${bg.colors[0]}`;
    if(bg.kind==='lines')back.style.background=`repeating-linear-gradient(135deg,${bg.colors[0]} 0px,${bg.colors[0]} 28px,${bg.colors[1]} 29px,${bg.colors[0]} 30px)`;
    if(bg.kind==='grain')back.style.background=`repeating-linear-gradient(15deg,${bg.colors[0]} 0px,${bg.colors[0]} 3px,${bg.colors[1]} 4px,${bg.colors[0]} 5px)`;
    if(['grid','dots'].includes(bg.kind))back.style.backgroundSize='48px 48px';
    if(bg.animated){
      for(let i=0;i<(bg.id==='starfield'?32:3);i++){
        const orb=document.createElement('div'),star=bg.id==='starfield';
        orb.style.cssText=`position:absolute;width:${star?4+i%4:p.canvas.width*.75}px;height:${star?4+i%4:p.canvas.height*.75}px;border-radius:50%;background:${star?bg.colors[2]:`radial-gradient(ellipse,${bg.colors[1+i%2]}cc,transparent 70%)`};`;
        back.append(orb);orbs.push(orb);
      }
    }
  }
  function paintBackground(t){
    if(!bg?.animated)return;
    const phase=p.canvas.backgroundAnimated===false?0:t;
    orbs.forEach((orb,i)=>{
      if(bg.id==='starfield'){
        orb.style.left=((i*137.508)%100)+'%';orb.style.top=((i*43.17+phase*(2+i%3))%110-5)+'%';
        orb.style.opacity=.25+.6*(.5+.5*Math.sin(phase*.8+i));
      }else{
        const speed=bg.id==='aurora-breath'?.35:bg.id==='prism'?.7:.5;
        const angle=phase*speed+i*2.094;
        orb.style.left=(15+28*Math.sin(angle))+'%';orb.style.top=(12+30*Math.cos(angle*.8))+'%';
        orb.style.transform=`rotate(${phase*7+i*60}deg) scale(${.9+.18*Math.sin(angle)})`;
      }
    });
  }
  for (const track of p.tracks) {
    for (const e of p.elements.filter(e => e.trackId === track.id)) {
      const n = document.createElement('div'); n.className = 'fc-element'; n.dataset.elementId = e.id;
      n.dataset.trackIndex = p.tracks.indexOf(track); n.dataset.start = e.start; n.dataset.duration = e.duration;
      Object.assign(n.style, {position:'absolute', left:e.x+'px', top:e.y+'px', width:e.width+'px', height:e.height+'px',
        color:e.style.color, fontSize:e.style.fontSize+'px', fontFamily:e.style.fontFamily, fontWeight:e.style.fontWeight,
        textAlign:e.style.align, background:e.style.background, borderRadius:e.style.radius+'px', whiteSpace:'break-spaces',
        lineHeight:'1.08', padding:['text','caption'].includes(e.type)?'0 4px':'0', display:'flex', alignItems:'center', justifyContent:e.style.align==='center'?'center':e.style.align==='right'?'flex-end':'flex-start'});
      let media;
      if (['image','video','audio'].includes(e.type)) {
        const a = assets.get(e.assetId); media = document.createElement(e.type==='image'?'img':e.type);
        media.src = window.FRAMECORE_ASSET_PREFIX + encodeURIComponent(a.file.split('/').pop());
        media.style.cssText='width:100%;height:100%;object-fit:contain;display:block';
        if(a.provenance?.source==='phosphor_builtin'||(a.provenance?.source==='framecore_builtin'&&a.role==='icon')) {
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
  const ease = (u,curve='cubic-out') => curve==='linear'?u:1-Math.pow(1-u,{'quad-out':2,'cubic-out':3,'quint-out':5}[curve]||3);
  function keyed(e,prop,t) {
    const points=(e.keyframes||[]).filter(k=>k.property===prop).sort((a,b)=>a.time-b.time);
    if(!points.length)return e[prop];
    if(t<=points[0].time)return points[0].value;
    for(let i=1;i<points.length;i++)if(t<=points[i].time){const a=points[i-1],b=points[i];return a.value+(b.value-a.value)*(t-a.time)/(b.time-a.time);}
    return points.at(-1).value;
  }
  function paint(t) {
    const waits=[]; time=clamp(t,0,p.duration);paintBackground(time);
    for (const e of p.elements) {
      const {node:n,media} = nodes.get(e.id), track=tracks.get(e.trackId);
      const local=time-e.start, visible=!track.hidden && local>=0 && local<e.duration;
      n.style.visibility=visible?'visible':'hidden';
      let alpha=1, dx=0,dy=0,scale=1,blur=0,extraRotate=0,flip=0,glow=0;
      const m=e.motion, phase=local+(e.motionOffset||0), u=m?clamp(phase/m.duration):1, z=ease(u,m?.easing);
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
        case 'breathe':alpha=z;scale=1+.035*Math.sin(phase*2);break;
        case 'drift-diagonal':alpha=z;dx=Math.sin(phase*.7)*18;dy=Math.sin(phase*.7)*-12;break;
        case 'orbit-compact':alpha=z;dx=Math.cos(phase*1.3)*12;dy=Math.sin(phase*1.3)*12;break;
        case 'spin-soft':alpha=z;extraRotate=phase*12;break;
        case 'curtain-open':n.style.clipPath=`inset(0 ${(1-z)*50}% 0 ${(1-z)*50}%)`;break;
        case 'perspective-flip':alpha=z;flip=(1-z)*-75;break;
        case 'signal-glow':alpha=z;glow=5+5*(.5+.5*Math.sin(phase*2));break;
        case 'camera-push':alpha=z;scale=1+Math.min(phase,20)*.015;break;
        case 'cinema-rise':alpha=z;dy=(1-z)*150;blur=(1-z)*4;break;
      }
      if(!['wipe-left','wipe-up','curtain-open'].includes(m?.id))n.style.clipPath='none';
      const tilt=m?.id==='rotate-in'?(1-z)*-18:m?.id==='gentle-tilt'?(1-z)*-8:0;
      n.style.left=keyed(e,'x',local)+'px';n.style.top=keyed(e,'y',local)+'px';
      n.style.opacity=keyed(e,'opacity',local)*alpha; n.style.filter=`blur(${blur}px) drop-shadow(0 0 ${glow}px ${glow?e.style.color:"transparent"})`;
      n.style.transform=`perspective(1200px) rotateY(${flip}deg) translate(${dx}px,${dy}px) rotate(${keyed(e,'rotation',local)+tilt+extraRotate}deg) scale(${keyed(e,'scale',local)*scale})`;
      if (media && ['video','audio'].includes(e.type)) {
        const sourceTime=Math.max(0,e.sourceStart+local);
        const targetTime=Math.min(sourceTime,Math.max(0,media.duration-.001));
        media.muted=e.type==='video'||track.muted||!!window.__CAPTURE__;
        if(e.type==='audio') {const a=e.audio||{gain:1,fadeIn:0,fadeOut:0};media.volume=clamp(a.gain*Math.min(1,a.fadeIn?Math.max(0,local)/a.fadeIn:1,a.fadeOut?Math.max(0,e.duration-local)/a.fadeOut:1));}
        if(!visible || !playing) media.pause();
        if(visible && media.readyState>=1 && Math.abs(media.currentTime-targetTime)>.04) {
          if(window.__CAPTURE__) waits.push(new Promise(resolve=>{
            const done=()=>{clearTimeout(timer);media.removeEventListener('seeked',done);resolve();};
            const timer=setTimeout(done,3000);
            media.addEventListener('seeked',done,{once:true}); media.currentTime=targetTime;
          }));
          else media.currentTime=targetTime;
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
  const fontLoads=[...new Set(p.elements.filter(e=>['text','caption'].includes(e.type)).map(e=>`${e.style.fontWeight} ${e.style.fontSize}px ${JSON.stringify(e.style.fontFamily)}`))].map(spec=>document.fonts.load(spec));
  window.__ready=Promise.all([Promise.all(fontLoads).then(()=>document.fonts.ready), ...nodes.values()].map(item=>{
    if(item instanceof Promise)return item;
    const {media}=item;
    if(!media)return Promise.resolve();
    if(media.tagName==='IMG')return media.decode();
    if(media.readyState>=2)return Promise.resolve();
    return new Promise((resolve,reject)=>{media.addEventListener('loadeddata',resolve,{once:true});media.addEventListener('error',()=>reject(new Error(`Media load failed (code ${media.error?.code}): ${media.currentSrc}`)),{once:true});});
  })).then(()=>paint(0)).then(()=>{window.READY=true;});
  paint(0);
})();
