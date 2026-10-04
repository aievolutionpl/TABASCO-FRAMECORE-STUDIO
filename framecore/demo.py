"""An original sample project; never presented as uploaded/generated AI media."""
import io
import math
import struct
import wave
from PIL import Image, ImageDraw, ImageFilter
from .commands import storyboard
from .model import uid


def create_demo(store):
    from .server import import_asset
    s = store.create("FORM — Lepsza codzienność", duration=15)
    pid = s["project"]["id"]
    image = Image.new("RGB", (900, 1100), "#101415")
    shadow = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((155, 890, 750, 980), fill=(0,0,0,190))
    image = Image.alpha_composite(image.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(28)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((270,220,630,935), radius=64, fill="#6a613e", outline="#a99b62", width=3)
    for x in range(281,621):
        t=(x-281)/340
        light=math.sin(t*math.pi)*.4+.6
        color=tuple(round(c*light) for c in (157,144,86))
        draw.line((x,277,x,883),fill=color,width=1)
    draw.rounded_rectangle((322,130,578,253), radius=17,fill="#232920",outline="#525b43",width=3)
    draw.rectangle((329,220,571,254), fill="#292f23")
    draw.rectangle((303,447,597,737),fill="#dddaca")
    draw.text((348,484),"F O R M",fill="#292e23",font_size=43)
    draw.line((342,562,558,562),fill="#9c9e86",width=1)
    draw.text((355,591),"CODZIENNY RYTUAl",fill="#4c5540",font_size=19)
    draw.text((371,647),"01 / NATURA",fill="#687155",font_size=14)
    draw.text((384,684),"250 ml",fill="#687155",font_size=17)
    data=io.BytesIO();image.save(data,format="PNG")
    s=import_asset(store,pid,data.getvalue(),"FORM produkt · przykład.png","product",s["project"]["revision"])
    # Original procedural ambient bed. Explicitly labelled, not AI-generated.
    data=io.BytesIO()
    with wave.open(data,"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050)
        samples=[]
        for i in range(15*22050):
            t=i/22050;fade=min(1,t/1.5,(15-t)/2)
            value=.045*fade*(math.sin(2*math.pi*110*t)+.45*math.sin(2*math.pi*164.81*t)+.25*math.sin(2*math.pi*220*t))
            samples.append(struct.pack('<h',round(value*32767)))
        wav.writeframes(b''.join(samples))
    s=import_asset(store,pid,data.getvalue(),"Spokojny podkład · własny przykład.wav","audio",s["project"]["revision"])
    scenes=storyboard(15,"FORM / A daily ritual.")
    scenes[0]["message"]="Codzienność\nz charakterem."
    scenes[1]["message"]="Mniej rzeczy.\nWięcej sensu."
    scenes[2]["message"]="Poznaj FORM."
    scenes[3]["message"]="Twój codzienny rytuał."
    scenes[4]["message"]="Z myślą\no Tobie."
    scenes[5]["message"]="Zrób miejsce\nna lepsze."
    s=store.execute(pid,"assemble_storyboard",{"scenes":scenes},s["project"]["revision"],"system")
    first=next(e for e in s["project"]["elements"] if e["type"]=="text")
    # Product remains visible in the opening scene in the sample only.
    aid=next(a["id"] for a in s["project"]["assets"] if a["kind"]=="image")
    s=store.execute(pid,"add_image",{"assetId":aid,"start":0,"duration":2,"x":130,"y":650,"width":820,"height":1000,"motion":{"id":"soft-fade","duration":.8}},s["project"]["revision"],"system")
    store.execute(pid,"set_selection",{"element_ids":[first["id"]]})
    store.execute(pid,"set_playhead",{"time":1.1})
    return store.read(pid)
