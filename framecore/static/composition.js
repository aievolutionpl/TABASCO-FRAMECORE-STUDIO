/* Original FrameCore deterministic composition adapter, MIT.
   Motion 2.0: entrances, kinetic text, exits, element looks and film effects.
   Every visual is a pure function of film time, so preview and export match frame for frame. */
(() => {
  const p = window.FRAMECORE_PROJECT, tracks = new Map(p.tracks.map(t => [t.id, t]));
  const assets = new Map(p.assets.map(a => [a.id, a])), nodes = new Map();
  let time = 0, playing = false, rate = 1, last = 0, frame;
  const root = document.querySelector('[data-composition-id]');
  root.style.width = p.canvas.width + 'px'; root.style.height = p.canvas.height + 'px';
  root.style.background = p.canvas.background;
  const W = p.canvas.width, H = p.canvas.height, FPS = p.canvas.fps || 30;
  const fx = Object.assign({grade:'none', vignette:0, grain:0, letterbox:0, transition:'none', transitionDuration:.5}, p.canvas.fx || {});
  const accent = p.brand?.colors?.accent || '#f36b3f';
  // Stage holds background and clips so colour grade and scene transitions affect the picture, not overlays.
  const stage = document.createElement('div');
  stage.className = 'fc-stage'; stage.style.cssText = 'position:absolute;inset:0;overflow:hidden';
  root.append(stage);
  const bg=window.FRAMECORE_BACKGROUND, back=document.createElement('div');
  back.className='fc-background';back.style.cssText='position:absolute;inset:0;overflow:hidden;pointer-events:none';stage.append(back);
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
        orb.style.cssText=`position:absolute;width:${star?4+i%4:W*.75}px;height:${star?4+i%4:H*.75}px;border-radius:50%;background:${star?bg.colors[2]:`radial-gradient(ellipse,${bg.colors[1+i%2]}cc,transparent 70%)`};`;
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

  /* ---------- helpers ---------- */
  const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
  const EASE = {
    'linear': u=>u,
    'quad-out': u=>1-Math.pow(1-u,2),
    'cubic-out': u=>1-Math.pow(1-u,3),
    'quint-out': u=>1-Math.pow(1-u,5),
    'expo-out': u=>u>=1?1:1-Math.pow(2,-10*u),
    'back-out': u=>{const c=1.70158;return 1+(c+1)*Math.pow(u-1,3)+c*Math.pow(u-1,2);},
    'elastic-out': u=>u<=0?0:u>=1?1:Math.pow(2,-10*u)*Math.sin((u*10-.75)*(2*Math.PI)/3)+1,
    'cubic-in-out': u=>u<.5?4*u*u*u:1-Math.pow(-2*u+2,3)/2,
  };
  const ease = (u,curve='cubic-out') => (EASE[curve]||EASE['cubic-out'])(clamp(u));
  // Exits mirror the curve: an "out" curve becomes an accelerating departure.
  const easeExit = (u,curve='cubic-out') => 1-(EASE[curve]||EASE['cubic-out'])(clamp(1-u));
  const hash = (a,b=0) => { let h = Math.imul(a ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(b + 0x632be5ab, 0xc2b2ae35); h ^= h >>> 15; h = Math.imul(h, 0x27d4eb2f); return ((h ^ (h >>> 13)) >>> 0) / 4294967296; };
  const hexA = (hex,a) => { const n=parseInt(String(hex).slice(1),16); return Number.isFinite(n)&&String(hex).length===7?`rgba(${n>>16&255},${n>>8&255},${n&255},${a})`:`rgba(0,0,0,${a})`; };
  const KINETIC = {'type-on':'char','word-cascade':'word','char-rise':'char','word-blur':'word','char-wave':'char','scramble-in':'char','word-highlight':'word'};
  const SCRAMBLE = 'ABCDEFGHJKLMNOPRSTUWXYZ0123456789#%&*+=<>/';
  function shadowFilter(s){
    const c = s.shadowColor || s.color || '#000000';
    switch(s.shadow){
      case 'soft': return 'drop-shadow(0 8px 22px rgba(0,0,0,.45))';
      case 'lift': return 'drop-shadow(0 2px 1px rgba(0,0,0,.35)) drop-shadow(0 18px 28px rgba(0,0,0,.38))';
      case 'glow': return `drop-shadow(0 0 14px ${hexA(c,.75)}) drop-shadow(0 0 36px ${hexA(c,.45)})`;
      case 'neon': return `drop-shadow(0 0 2px #ffffff) drop-shadow(0 0 8px ${hexA(c,.95)}) drop-shadow(0 0 24px ${hexA(c,.8)}) drop-shadow(0 0 60px ${hexA(c,.55)})`;
      case 'long': return `drop-shadow(4px 4px 0 ${hexA(s.shadowColor||'#000000',.35)}) drop-shadow(8px 8px 0 ${hexA(s.shadowColor||'#000000',.22)}) drop-shadow(14px 14px 0 ${hexA(s.shadowColor||'#000000',.12)})`;
      default: return '';
    }
  }
  const gradientCss = g => `linear-gradient(${g.angle}deg, ${g.from}, ${g.to})`;
  function paintGradientText(el,g){
    el.style.backgroundImage=gradientCss(g);el.style.webkitBackgroundClip='text';el.style.backgroundClip='text';
    el.style.color='transparent';el.style.webkitTextFillColor='transparent';
  }

  /* ---------- build ---------- */
  for (const track of p.tracks) {
    for (const e of p.elements.filter(e => e.trackId === track.id)) {
      const s = e.style || {};
      const n = document.createElement('div'); n.className = 'fc-element'; n.dataset.elementId = e.id;
      n.dataset.trackIndex = p.tracks.indexOf(track); n.dataset.start = e.start; n.dataset.duration = e.duration;
      Object.assign(n.style, {position:'absolute', left:e.x+'px', top:e.y+'px', width:e.width+'px', height:e.height+'px',
        color:s.color, fontSize:s.fontSize+'px', fontFamily:s.fontFamily, fontWeight:s.fontWeight,
        textAlign:s.align, background:s.background, borderRadius:s.radius+'px', whiteSpace:'break-spaces',
        lineHeight:'1.08', padding:['text','caption'].includes(e.type)?'0 4px':'0', display:'flex', alignItems:'center', justifyContent:s.align==='center'?'center':s.align==='right'?'flex-end':'flex-start'});
      if(s.letterSpacing) n.style.letterSpacing = s.letterSpacing+'px';
      if(s.blend && s.blend!=='normal') n.style.mixBlendMode = s.blend;
      if(s.strokeWidth){ n.style.webkitTextStroke = `${s.strokeWidth}px ${s.strokeColor||'#000000'}`; n.style.paintOrder='stroke fill'; }
      let media, units=[], inner=null, caret=null;
      const motionId = e.motion?.id, unitKind = ['text','caption'].includes(e.type) ? KINETIC[motionId] : null;
      if (['image','video','audio'].includes(e.type)) {
        const a = assets.get(e.assetId); media = document.createElement(e.type==='image'?'img':e.type);
        media.src = window.FRAMECORE_ASSET_PREFIX + encodeURIComponent(a.file.split('/').pop());
        media.style.cssText=`width:100%;height:100%;object-fit:${s.fit==='cover'?'cover':'contain'};display:block`;
        if(a.provenance?.source==='phosphor_builtin'||(a.provenance?.source==='framecore_builtin'&&a.role==='icon')) {
          n.style.maskImage=`url("${media.src}")`;n.style.maskSize='contain';n.style.maskRepeat='no-repeat';n.style.maskPosition='center';
          n.style.background=s.gradient?gradientCss(s.gradient):s.color;media.style.opacity=0;
        }
        if (e.type==='video') { media.playsInline=true; media.preload='auto'; media.muted=true; }
        if (e.type==='audio') { media.preload='auto'; media.muted=!!track.muted || !!window.__CAPTURE__; }
        n.append(media);
      } else if (e.type === 'shape') {
        if(s.gradient) n.style.background = gradientCss(s.gradient);
      } else if (unitKind || s.gradient) {
        // Kinetic text: words keep line wrapping (nowrap inside a word, spaces between words).
        inner = document.createElement('span'); inner.className='fc-text';
        inner.style.cssText='display:block;width:100%;white-space:break-spaces';
        for (const token of e.text.split(/(\s+)/)) {
          if (!token) continue;
          if (/^\s+$/.test(token)) { inner.append(document.createTextNode(token)); continue; }
          const word = document.createElement('span'); word.className='fc-word';
          word.style.cssText='display:inline-block;white-space:nowrap';
          if (unitKind==='char') {
            for (const ch of Array.from(token)) {
              const c = document.createElement('span'); c.className='fc-char'; c.textContent=ch; c.dataset.char=ch;
              c.style.display='inline-block'; word.append(c); units.push(c);
            }
          } else { word.textContent = token; if(unitKind) units.push(word); }
          inner.append(word);
        }
        if (s.gradient) {
          if (units.length) units.forEach(u=>paintGradientText(u,s.gradient));
          else paintGradientText(inner,s.gradient);
        }
        if (motionId==='type-on') {
          caret=document.createElement('span');caret.className='fc-caret';
          caret.style.cssText=`display:inline-block;width:.08em;height:.9em;margin-left:.04em;vertical-align:-.08em;background:${s.gradient?s.gradient.to:s.color}`;
          inner.append(caret);
        }
        n.append(inner);
      } else n.textContent = e.text;
      stage.append(n); nodes.set(e.id, {node:n, media, units, caret, inner, shadow:shadowFilter(s)});
    }
  }

  /* ---------- film effects layer ---------- */
  const fxLayer = document.createElement('div');
  fxLayer.className='fc-fx'; fxLayer.style.cssText='position:absolute;inset:0;pointer-events:none;overflow:hidden';
  root.append(fxLayer);
  const GRADES = {none:'', cinematic:'contrast(1.08) saturate(.92) sepia(.12) hue-rotate(-6deg)', warm:'sepia(.22) saturate(1.15) hue-rotate(-8deg) brightness(1.03)',
    cool:'saturate(.95) hue-rotate(12deg) brightness(1.02) contrast(1.04)', mono:'grayscale(1) contrast(1.12)', vivid:'saturate(1.35) contrast(1.06)',
    faded:'contrast(.88) saturate(.8) brightness(1.06)', noir:'grayscale(1) contrast(1.45) brightness(.92)'};
  const gradeFilter = GRADES[fx.grade] || '';
  const transition = document.createElement('div');
  transition.style.cssText='position:absolute;inset:0;opacity:0';
  fxLayer.append(transition);
  let leak=null;
  if (fx.transition==='light-leak') {
    leak=document.createElement('div');
    leak.style.cssText=`position:absolute;width:${W*1.4}px;height:${H*1.4}px;border-radius:50%;mix-blend-mode:screen;opacity:0;`+
      `background:radial-gradient(ellipse at center, rgba(255,214,150,.95), rgba(255,120,70,.65) 35%, rgba(255,60,120,.25) 58%, transparent 72%)`;
    fxLayer.append(leak);
  }
  if (fx.vignette>0) {
    const v=document.createElement('div');
    v.style.cssText=`position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent ${Math.round(62-fx.vignette*22)}%, rgba(0,0,0,${(.35+fx.vignette*.55).toFixed(3)}) 100%)`;
    fxLayer.append(v);
  }
  let grain=null;
  if (fx.grain>0) {
    const size=160, c=document.createElement('canvas'); c.width=c.height=size;
    const ctx=c.getContext('2d'), img=ctx.createImageData(size,size);
    for(let i=0;i<size*size;i++){const v=Math.floor(hash(i,7)*255);img.data.set([v,v,v,255],i*4);}
    ctx.putImageData(img,0,0);
    grain=document.createElement('div');
    grain.style.cssText=`position:absolute;inset:-${size}px;background-image:url(${c.toDataURL()});background-size:${size}px ${size}px;mix-blend-mode:overlay;opacity:${(fx.grain*.55).toFixed(3)}`;
    fxLayer.append(grain);
  }
  if (fx.letterbox>0) for (const edge of ['top','bottom']) {
    const bar=document.createElement('div');
    bar.style.cssText=`position:absolute;left:0;right:0;${edge}:0;height:${(H*fx.letterbox/2).toFixed(1)}px;background:#000`;
    fxLayer.append(bar);
  }
  const boundaries = [...new Set(p.scenes.map(s=>s.start).filter(t=>t>.05&&t<p.duration-.05))].sort((a,b)=>a-b);
  function paintFx(t){
    let blur=0;
    // Peak of the scene transition sits exactly on the cut.
    const D=fx.transitionDuration, b=boundaries.find(b=>Math.abs(t-b)<D/2);
    const k = b===undefined ? -1 : (t-(b-D/2))/D, tri = k<0?0:1-Math.abs(2*k-1);
    transition.style.opacity=0; transition.style.transform='none';
    if(leak) leak.style.opacity=0;
    if(k>=0) switch(fx.transition){
      case 'dip': transition.style.background='#000'; transition.style.opacity=ease(tri,'cubic-in-out'); break;
      case 'flash': transition.style.background='#fff'; transition.style.opacity=Math.pow(tri,2.2)*.92; break;
      case 'wipe': {
        transition.style.background=accent; transition.style.opacity=1;
        transition.style.transform=`translateX(${(ease(k,'cubic-in-out')*2-1)*112}%) skewX(-12deg)`; break;
      }
      case 'light-leak':
        leak.style.opacity=ease(tri,'cubic-in-out')*.9;
        leak.style.left=(-W*.7+k*W*1.1)+'px'; leak.style.top=(-H*.5+Math.sin(k*Math.PI)*H*.15)+'px'; break;
      case 'blur': blur=tri*22; transition.style.background='#fff'; transition.style.opacity=tri*.18; break;
    }
    const filter=[gradeFilter, blur?`blur(${blur.toFixed(2)}px)`:''].filter(Boolean).join(' ');
    stage.style.filter=filter||'none';
    if(grain){const f=Math.floor(t*FPS);grain.style.transform=`translate(${Math.floor(hash(f,1)*160)-80}px,${Math.floor(hash(f,2)*160)-80}px)`;}
  }

  function keyed(e,prop,t) {
    const points=(e.keyframes||[]).filter(k=>k.property===prop).sort((a,b)=>a.time-b.time);
    if(!points.length)return e[prop];
    if(t<=points[0].time)return points[0].value;
    for(let i=1;i<points.length;i++)if(t<=points[i].time){const a=points[i-1],b=points[i];return a.value+(b.value-a.value)*(t-a.time)/(b.time-a.time);}
    return points.at(-1).value;
  }

  /* ---------- kinetic text ---------- */
  function paintUnits(e,info,phase){
    const m=e.motion, units=info.units, n=units.length; if(!n)return;
    const D=m.duration, unitDur=Math.min(.55,D*.6), stagger=n>1?(D-unitDur)/(n-1):0, fs=e.style.fontSize;
    if(m.id==='type-on'){
      const shown=Math.floor(clamp(phase/D)*n+1e-6);
      units.forEach((u,i)=>{u.style.opacity=i<shown?1:0;});
      if(info.caret){
        const idx=Math.min(shown,n-1);
        if(shown<n) units[idx].before(info.caret); else units[n-1].after(info.caret);
        const typing=phase<D, blinkOn=Math.floor(Math.max(0,phase-D)*2.2)%2===0;
        info.caret.style.opacity=(typing||(blinkOn&&phase<D+2.4))?1:0;
      }
      return;
    }
    if(m.id==='word-highlight'){
      const span=Math.max(D,e.duration-.3), step=span/n;
      units.forEach((u,i)=>{
        const a=clamp((phase-i*step)/Math.min(.18,step)), active=phase>=i*step&&phase<(i+1)*step;
        u.style.opacity=.32+.68*a;
        if(!e.style.gradient) u.style.color=active?accent:'inherit';
        u.style.transform=`translateY(${active?(-.06*e.style.fontSize*ease(clamp((phase-i*step)/.12),'back-out')).toFixed(2):0}px)`;
      });
      return;
    }
    units.forEach((u,i)=>{
      const local=(phase-i*stagger)/unitDur, z=ease(local,m.easing||'cubic-out'), a=clamp(local*1.6);
      let tf='', op=a, filter='';
      switch(m.id){
        case 'word-cascade': tf=`translateY(${((1-z)*fs*.55).toFixed(2)}px)`; break;
        case 'char-rise': tf=`translateY(${((1-z)*fs*.8).toFixed(2)}px) rotate(${((1-z)*8).toFixed(2)}deg)`; break;
        case 'word-blur': op=clamp(local); filter=`blur(${((1-ease(local,'quad-out'))*14).toFixed(2)}px)`; tf=`scale(${(1.12-.12*z).toFixed(4)})`; break;
        case 'char-wave': {
          const settle=Math.max(0,phase-D);
          tf=`translateY(${((1-z)*fs*.6+Math.sin(settle*4-i*.55)*fs*.07*Math.min(1,settle*2)).toFixed(2)}px)`; break;
        }
        case 'scramble-in': {
          const resolveAt=(i+1)*stagger+unitDur*.6;
          op=clamp(local*3);
          const ch=u.dataset.char;
          u.textContent = phase>=resolveAt||/\s/.test(ch) ? ch : SCRAMBLE[Math.floor(hash(i,Math.floor(phase*24))*SCRAMBLE.length)];
          if(e.style.gradient) u.style.webkitTextFillColor = phase<resolveAt ? accent : 'transparent';
          else u.style.color = phase<resolveAt ? accent : 'inherit';
          break;
        }
      }
      u.style.opacity=op.toFixed(4); u.style.transform=tf||'none'; u.style.filter=filter||'none';
    });
  }

  /* ---------- paint ---------- */
  function paint(t) {
    const waits=[]; time=clamp(t,0,p.duration);paintBackground(time);paintFx(time);
    for (const e of p.elements) {
      const info=nodes.get(e.id), {node:n,media} = info, track=tracks.get(e.trackId);
      const local=time-e.start, visible=!track.hidden && local>=0 && local<e.duration;
      n.style.visibility=visible?'visible':'hidden';
      let alpha=1, dx=0,dy=0,scale=1,sx=1,sy=1,skew=0,blur=0,extraRotate=0,flip=0,flipX=0,glow=0,clip='none',origin='50% 50%',split=0;
      const m=e.motion, phase=local+(e.motionOffset||0), u=m?clamp(phase/m.duration):1, z=ease(u,m?.easing);
      const kinetic = m && info.units.length;
      if(m && kinetic) { paintUnits(e,info,phase); }
      else if(m) switch(m.id) {
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
        case 'wipe-left':alpha=1;clip=`inset(0 ${(1-z)*100}% 0 0)`;break;
        case 'wipe-up':alpha=1;clip=`inset(${(1-z)*100}% 0 0 0)`;break;
        case 'focus-in':alpha=z;blur=(1-z)*30;scale=1.04-.04*z;break;
        case 'elastic-pop':alpha=z;scale=.5+.5*z+.1*Math.sin(u*Math.PI*3)*(1-u);break;
        case 'gentle-tilt':alpha=z;dx=(1-z)*20;break;
        case 'breathe':alpha=z;scale=1+.035*Math.sin(phase*2);break;
        case 'drift-diagonal':alpha=z;dx=Math.sin(phase*.7)*18;dy=Math.sin(phase*.7)*-12;break;
        case 'orbit-compact':alpha=z;dx=Math.cos(phase*1.3)*12;dy=Math.sin(phase*1.3)*12;break;
        case 'spin-soft':alpha=z;extraRotate=phase*12;break;
        case 'curtain-open':clip=`inset(0 ${(1-z)*50}% 0 ${(1-z)*50}%)`;break;
        case 'perspective-flip':alpha=z;flip=(1-z)*-75;break;
        case 'signal-glow':alpha=z;glow=5+5*(.5+.5*Math.sin(phase*2));break;
        case 'camera-push':alpha=z;scale=1+Math.min(phase,20)*.015;break;
        case 'cinema-rise':alpha=z;dy=(1-z)*150;blur=(1-z)*4;break;
        case 'ken-burns': {
          // Continuous over the whole clip: slow push with a gentle drift.
          const k=clamp(phase/Math.max(e.duration,.1)); alpha=z;
          scale=1.02+.12*ease(k,'quad-out'); dx=(k-.5)*-e.width*.035; dy=(k-.5)*-e.height*.02; break;
        }
        case 'iris-open': clip=`circle(${(z*75).toFixed(3)}% at 50% 50%)`; scale=1.06-.06*z; break;
        case 'zoom-blur-in': alpha=clamp(u*2.2); scale=1.45-.45*z; blur=(1-z)*26; break;
        case 'glitch-in': {
          const f=Math.floor(phase*FPS), j=(1-z);
          alpha=u<.55?(hash(f,3)>.35?1:.25):1; dx=(hash(f,4)-.5)*90*j; split=14*j;
          if(u<.6) clip=`inset(${Math.floor(hash(f,5)*40)}% 0 ${Math.floor(hash(f,6)*40)}% 0)`; break;
        }
        case 'swing-in': alpha=clamp(u*2); flipX=(1-z)*-95; origin='50% 0%'; break;
        case 'stretch-pop': alpha=clamp(u*3); sx=1+(1-z)*.55*Math.cos(u*Math.PI*1.5); sy=1/Math.max(.4,sx); scale=.6+.4*z; break;
        case 'skew-slide': alpha=z; dx=(1-z)*-140; skew=(1-z)*18; break;
      }
      // Exit runs in the final seconds of the clip and composes with any entrance.
      const x=e.exit;
      if(x){
        const xs=Math.max(0,e.duration-x.duration), v=local>xs?easeExit((local-xs)/x.duration,x.easing):0;
        if(v>0) switch(x.id){
          case 'fade-out': alpha*=1-v; break;
          case 'rise-out': alpha*=1-v; dy-=v*90; break;
          case 'drop-out': alpha*=1-v; dy+=v*120; break;
          case 'slide-out-left': alpha*=1-v; dx-=v*160; break;
          case 'slide-out-right': alpha*=1-v; dx+=v*160; break;
          case 'blur-out': alpha*=1-v; blur+=v*22; break;
          case 'scale-out': alpha*=1-v; scale*=1-.35*v; break;
          case 'zoom-through': alpha*=1-v; scale*=1+1.4*v; blur+=v*10; break;
          case 'wipe-out': clip=`inset(0 0 0 ${(v*100).toFixed(3)}%)`; break;
          case 'iris-close': clip=`circle(${((1-v)*75).toFixed(3)}% at 50% 50%)`; break;
        }
      }
      n.style.clipPath=clip; n.style.transformOrigin=origin;
      const tilt=m?.id==='rotate-in'?(1-z)*-18:m?.id==='gentle-tilt'?(1-z)*-8:0;
      n.style.left=keyed(e,'x',local)+'px';n.style.top=keyed(e,'y',local)+'px';
      n.style.opacity=keyed(e,'opacity',local)*alpha;
      const filters=[`blur(${blur}px)`];
      if(glow) filters.push(`drop-shadow(0 0 ${glow}px ${e.style.color})`);
      else filters.push('drop-shadow(0 0 0px transparent)');
      if(split) filters.push(`drop-shadow(${split.toFixed(2)}px 0 0 rgba(255,0,90,.8)) drop-shadow(${(-split).toFixed(2)}px 0 0 rgba(0,220,255,.8))`);
      if(info.shadow) filters.push(info.shadow);
      n.style.filter=filters.join(' ');
      n.style.transform=`perspective(1200px) rotateY(${flip}deg) rotateX(${flipX}deg) translate(${dx}px,${dy}px) rotate(${keyed(e,'rotation',local)+tilt+extraRotate}deg) skewX(${-skew}deg) scale(${keyed(e,'scale',local)*scale}) scale(${sx},${sy})`;
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
