"""Editable 30-second launch film: six exact five-second scenes."""
from pathlib import Path
import io
import wave
import numpy as np
from .api import API
from .render import RenderJobs

SCENES = [
    ('Twój pomysł.\nWspólna rama.', 'FRAMECORE / STUDIO', 'shared-frame', 'premium-blur-reveal'),
    ('Nadaj historii\nrytm.', 'SCENY · MATERIAŁY · ANIMACJE', 'motion-cards', 'wipe-left'),
    ('Twój model.\nTwój agent.', 'OPENROUTER + OPENAI', 'open-frame', 'impact-rise'),
    ('Twórzcie\nna jednej osi.', 'WSPÓLNY PROJEKT. HISTORIA ZMIAN.', 'shared-frame', 'slide-right'),
    ('Pierwszy film?\nZacznij tutaj.', 'ONBOARDING · BIBLIOTEKA · SZABLONY', 'motion-cards', 'word-pop'),
    ('Z pomysłu\nw gotowy film.', 'URUCHOM FRAMECORE', 'open-frame', 'cinema-rise'),
]

def music(duration=30):
    sr=44100
    t=np.arange(sr*duration)/sr
    track=np.zeros_like(t)
    for i,chord in enumerate(((110,164.81,220),(130.81,196,261.63),(98,146.83,196),(123.47,185,246.94),(110,164.81,220),(130.81,196,261.63))):
        section=(t>=i*5)&(t<(i+1)*5); local=t[section]-i*5
        env=np.minimum(1,local/.3)*np.minimum(1,(5-local)/.4)
        track[section]+=env*sum(.025*np.sin(2*np.pi*f*local)+.01*np.sin(2*np.pi*f*2*local) for f in chord)
    beat=t%0.5
    track+=.12*np.exp(-beat*24)*np.sin(2*np.pi*(55*beat+2*(1-np.exp(-beat*35))))
    rng=np.random.default_rng(104)
    track+=rng.normal(0,.025,len(t))*np.exp(-((t+.25)%0.5)*95)
    for boundary in (5,10,15,20,25):
        d=t-boundary
        track+=np.where((d>=0)&(d<.7),.03*np.sin(2*np.pi*660*d)*np.exp(-np.maximum(0,d)*9),0)
    track*=np.minimum(1,t/.5)*np.minimum(1,(duration-t)/1.2)
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(sr)
        out.writeframes((np.clip(track,-.9,.9)*32767).astype('<i2').tobytes())
    return buffer.getvalue()

def create_campaign(store):
    api=API(store,RenderJobs(store))
    state=api.call('create_project',{'name':'FRAMECORE — Twój pomysł. Wspólna rama.','format':'16:9','duration':30,
                                  'brief':'Reklama narzędzia. Sześć scen po 5 sekund; lokalne materiały AI, zróżnicowany ruch i własna muzyka.'})
    pid=state['project']['id']
    def command(tool_name,**args):
        nonlocal state
        state=api.call(tool_name,{'project_id':pid,'expected_revision':state['project']['revision'],**args},actor='agent')
        return state['project']['elements'][-1] if state['project']['elements'] else None
    command('set_brand',brand={'name':'FRAMECORE','font':'Manrope','colors':{'background':'#080b0d','text':'#f6f1e8','accent':'#f36b3f'}})
    # All background layers are added before typography, preserving predictable stacking.
    for i,(_,_,asset,motion) in enumerate(SCENES):
        command('add_scene',name=f'{i+1:02d} / {SCENES[i][1]}',start=i*5,duration=5,message=SCENES[i][0])
        e=command('add_library_asset',asset_id='campaign-'+asset,start=i*5,duration=5,x=0,y=0,width=1920,height=1080)
        command('apply_motion',element_id=e['id'],motion_id=['soft-fade','zoom-out','focus-in','wipe-up','rotate-in','scale-in'][i],duration=.7)
        command('set_keyframes',element_id=e['id'],keyframes=[{'property':'scale','time':0,'value':1.0},{'property':'scale','time':5,'value':1.035}])
    for i,(title,label,asset,motion) in enumerate(SCENES):
        start=i*5
        command('add_text',text=label,start=start+.15,duration=4.85,x=120,y=285,width=820,height=65,
                style={'fontFamily':'Manrope','fontSize':28,'fontWeight':600,'color':'#f69b76'},motion={'id':'soft-fade','duration':.6})
        command('add_text',text=title,start=start+.25,duration=4.75,x=112,y=380,width=910,height=295,
                style={'fontFamily':'Manrope','fontSize':100,'fontWeight':800,'color':'#f6f1e8','align':'left'},motion={'id':motion,'duration':.8})
        if i==2:
            command('add_text',text='Podłącz klucz. Zleć montaż.',start=start+1,duration=4,x=120,y=715,width=850,height=70,
                    style={'fontFamily':'Manrope','fontSize':34,'fontWeight':500,'color':'#c6c6c0'},motion={'id':'slide-left','duration':.6})
        if i==5:
            command('add_text',text='github.com/aievolutionpl',start=start+1,duration=4,x=120,y=735,width=800,height=65,
                    style={'fontFamily':'Manrope','fontSize':31,'fontWeight':500,'color':'#f69b76'},motion={'id':'cta-pulse','duration':.8})
        command('add_text',text=f'{i+1:02d} / 06',start=start,duration=5,x=120,y=925,width=240,height=60,
                style={'fontFamily':'Manrope','fontSize':28,'fontWeight':500,'color':'#aaa9a5'},motion={'id':'soft-fade','duration':.2})
    command('add_text',text='FRAMECORE',start=0,duration=30,x=120,y=70,width=760,height=80,
            style={'fontFamily':'Manrope','fontSize':42,'fontWeight':800,'color':'#f6f1e8'},motion={'id':'logo-settle','duration':.8})
    command('add_text',text='TABASCO CREATIVES + FRAMECORE — STUDIO',start=0,duration=30,x=120,y=152,width=960,height=60,
            style={'fontFamily':'Manrope','fontSize':22,'fontWeight':500,'color':'#9c9c96'},motion={'id':'soft-fade','duration':.8})
    imports=store.root.parent/'imports';imports.mkdir(exist_ok=True,parents=True)
    audio=imports/'framecore-campaign-music.wav';audio.write_bytes(music())
    command('add_asset',source_file=str(audio.resolve()),role='audio')
    aid=state['project']['assets'][-1]['id']
    # Import already adds a clip; avoid doubling the soundtrack.
    audio_element=next((e for e in state['project']['elements'] if e['type']=='audio' and e.get('assetId')==aid),None)
    if audio_element is None: audio_element=command('add_audio',assetId=aid,start=0,duration=30)
    command('set_audio',element_id=audio_element['id'],audio={'gain':.85,'fadeIn':.5,'fadeOut':1.2})
    command('set_playhead',time=2)
    return state
