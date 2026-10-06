"""Film pokazujący współpracę; edytowalny przykład z własną muzyką i ikonami MIT."""
import io
import math
import struct
import wave
from pathlib import Path
from .templates import template_scenes


def soundtrack(duration=15):
    data = io.BytesIO()
    with wave.open(data, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        samples = bytearray()
        for i in range(round(duration*22050)):
            t=i/22050
            bed=.035*(math.sin(2*math.pi*110*t)+.4*math.sin(2*math.pi*164.81*t)+.25*math.sin(2*math.pi*220*t))
            beat=(t%1)*8
            accent=.09*math.exp(-beat*5)*math.sin(2*math.pi*(65-20*min(1,beat))*t)
            value=(bed+accent)*min(1,t/.6,(duration-t)/1.5)
            samples.extend(struct.pack('<h',round(value*32767)))
        w.writeframes(samples)
    return data.getvalue()


def create_sample(store):
    from .server import import_asset
    s=store.create("MotionDuo Studio — wspólny film", "16:9", 15, "Film o współpracy człowieka z agentem.", "Współpraca z AI")
    pid=s["project"]["id"]
    def command(name,args):
        nonlocal s
        s=store.execute(pid,name,args,s["project"]["revision"],"system")
    s=import_asset(store,pid,soundtrack(),"Rytm współpracy · własny podkład.wav","audio",s["project"]["revision"],"system")
    command("set_brand",{"brand":{"name":"TABASCO CREATIVES + FRAMECORE", "colors":{"background":"#111315","text":"#f5f3ec","accent":"#ef421b"}}})
    scenes=template_scenes("collaboration",15,"MOTIONDUO\nSTUDIO")
    scenes[0]["message"]="Masz pomysł?"
    scenes[1]["message"]="Nadaj mu historię."
    scenes[3]["message"]="Ty wybierasz kierunek."
    scenes[4]["message"]="Agent pomaga w montażu."
    command("assemble_storyboard",{"scenes":scenes})
    for e in list(s["project"]["elements"]):
        if e["type"]=="text":
            command("resize_element",{"element_id":e["id"],"width":1680,"height":240})
            command("move_element",{"element_id":e["id"],"x":120,"y":180})
            command("set_property",{"element_id":e["id"],"property":"style.fontSize","value":92 if '\n' not in e["text"] else 104})
    for scene,key,motion in zip(scenes[:5],("lightning","film-strip","shapes","cursor","robot"),("elastic-pop","wipe-up","rotate-in","float","cinema-rise")):
        command("add_icon",{"icon_id":key if key!='cursor' else 'check',"start":scene["start"],"duration":scene["duration"],"x":120,"y":525,"width":225,"height":225})
        eid=s["project"]["elements"][-1]["id"]
        command("apply_motion",{"element_id":eid,"motion_id":motion,"duration":.8})
        command("set_property",{"element_id":eid,"property":"style.color","value":"#ef421b"})
        command("add_text",{"text":["IDEA","HISTORIA","NARZĘDZIA","CZŁOWIEK","AGENT AI"][scenes.index(scene)],"start":scene["start"],"duration":scene["duration"],"x":440,"y":570,"width":1150,"height":100,"style":{"fontSize":44,"color":"#b7b6b0","fontWeight":400},"motion":{"id":"slide-left","duration":.8}})
    image=Path(__file__).resolve().parents[1]/"assets/motionduo-banner.png"
    if image.is_file():
        s=import_asset(store,pid,image.read_bytes(),image.name,"brand",s["project"]["revision"],"system")
        command("add_image",{"assetId":s["project"]["assets"][-1]["id"],"start":13,"duration":2,"x":510,"y":440,"width":900,"height":506,"motion":{"id":"focus-in","duration":.5}})
    audio=next(e for e in s["project"]["elements"] if e["type"]=="audio")
    command("set_audio",{"element_id":audio["id"],"audio":{"gain":.8,"fadeIn":.3,"fadeOut":1}})
    command("add_text",{"text":"by TABASCO CREATIVES + FRAMECORE", "start":0,"duration":15,"x":120,"y":70,"width":1680,"height":50,"style":{"fontSize":24,"fontWeight":400,"color":"#b7b6b0"}})
    logo=Path(__file__).resolve().parents[1]/"assets/motionduo-mark.png"
    if logo.is_file():
        s=import_asset(store,pid,logo.read_bytes(),"MotionDuo — wspólny montaż.png","logo",s["project"]["revision"],"system")
        command("set_brand",{"brand":{"logoAssetId":s["project"]["assets"][-1]["id"]},"restyle":False})
        command("add_image",{"assetId":s["project"]["assets"][-1]["id"],"start":0,"duration":15,"x":1730,"y":45,"width":90,"height":90,"motion":{"id":"logo-settle","duration":.6}})
    first=next(e for e in s["project"]["elements"] if e["type"]=="text")
    store.execute(pid,"set_selection",{"element_ids":[first["id"]]})
    store.execute(pid,"set_playhead",{"time":1.1})
    return store.read(pid)


def create_creator_pack(store, sample_directory="creator-pack"):
    """Nowa kopia edytowalnego pokazu; istniejące projekty pozostają zachowane."""
    import json
    import shutil
    from copy import deepcopy
    from .model import validate
    source=Path(__file__).resolve().parents[1]/'examples'/sample_directory
    p=json.loads((source/'project.json').read_text(encoding='utf-8'))
    validate(p)
    state=store.create(p['metadata']['name'],'16:9',p['duration'])
    state=store._load(state['project']['id'])
    p=deepcopy(p);p['id']=state['project']['id'];p['revision']=0
    p['metadata']['createdAt']=state['project']['metadata']['createdAt']
    p['metadata']['updatedAt']=state['project']['metadata']['updatedAt']
    for a in p['assets']:
        asset=(source/a['file']).resolve()
        if not asset.is_relative_to(source.resolve()):raise ValueError('Nieprawidłowy przykład')
        shutil.copy2(asset,store.directory(p['id'])/a['file'])
    state['project']=p
    state['session'].update(selection=[next(e['id'] for e in p['elements'] if e['type']=='text')],playhead=1.2)
    store._save(state)
    return store.read(p['id'])
