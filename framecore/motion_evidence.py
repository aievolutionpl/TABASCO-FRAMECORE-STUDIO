"""Scene addresses, weighted onion frames and explicit visual comparisons.
Adapted from fframes time_spec/sheet/snapshot (MIT), see docs/FFRAMES.md.
"""
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from .persistence import atomic_write
from .model import EditorError, number
from .review import create_review, load_review


def resolve_time(p, spec):
    if isinstance(spec,(int,float)) and not isinstance(spec,bool):
        return number(spec,"time",0,max(0,p["duration"]-1/p["canvas"]["fps"]))
    if not isinstance(spec,str) or not 1 <= len(spec) <= 200: raise EditorError("Podaj czas lub scena@czas")
    start, duration = 0, p["duration"]
    offset = spec.strip()
    if "@" in offset:
        name, offset = offset.rsplit("@",1)
        scenes = [s for s in p["scenes"] if s["id"] == name or s["name"] == name]
        if len(scenes) != 1: raise EditorError("Wskaż jednoznaczną nazwę lub identyfikator sceny")
        start, duration = scenes[0]["start"], scenes[0]["duration"]
    fps = p["canvas"]["fps"]; last = max(0,duration-1/fps)
    try:
        if offset == "end": value = last
        elif offset.endswith("%"):
            ratio = number(float(offset[:-1]),"percent",0,100)/100
            value = min(last,math.floor(duration*fps*ratio)/fps)
        elif offset.endswith("ms"): value = float(offset[:-2])/1000
        elif offset.endswith("s"): value = float(offset[:-1])
        elif ":" in offset:
            parts = offset.split(":")
            if not 2 <= len(parts) <= 3: raise ValueError()
            numbers = [number(float(x),"clock",0,1e6) for x in parts]
            if any(v>=60 for v in numbers[1:]): raise ValueError()
            value = sum(v*60**i for i,v in enumerate(reversed(numbers)))
        else:
            frame = offset[:-1] if offset.endswith("f") else offset
            value = int(frame)/fps
    except (ValueError,OverflowError): raise EditorError("Nieprawidłowy adres klatki")
    number(value,"offset",0,last)
    return min(max(0,p["duration"]-1/fps),start+value)


def strip(store,pid,revision,start="0s",end="end",count=12):
    p=store.read(pid)["project"]
    if isinstance(count,bool) or not isinstance(count,int) or not 2<=count<=24: raise EditorError("Wybierz 2–24 klatki")
    a,b=resolve_time(p,start),resolve_time(p,end)
    if b<=a: raise EditorError("Koniec musi być późniejszy niż początek")
    r=create_review(store,pid,revision,[a+(b-a)*i/(count-1) for i in range(count)])
    out=store.directory(pid)/"reviews"/r["id"]
    total=sum(range(1,len(r["frames"])+1)); pixels=None
    for i,f in enumerate(r["frames"],1):
        image=np.asarray(Image.open(out/f["file"]).convert("RGB"),dtype=np.float32)
        if pixels is None: pixels=np.zeros_like(image)
        pixels+=image*(i/total)
    Image.fromarray(np.clip(np.rint(pixels),0,255).astype(np.uint8)).save(out/"onion.png")
    r.update(onionUrl=f"/reviews/{pid}/{r['id']}/onion.png",range={"start":a,"end":b,"count":len(r["frames"])})
    atomic_write(out/"review.json",json.dumps(r,ensure_ascii=False,indent=2))
    return r


def list_reviews(store,pid):
    result=[]
    for path in sorted((store.directory(pid)/"reviews").glob("*/review.json"),key=lambda f:f.stat().st_mtime_ns,reverse=True):
        r=json.loads(path.read_text(encoding="utf-8"))
        result.append({"id":r["id"],"revision":r["revision"],"createdAt":r["createdAt"],"verdict":r["verdict"],"times":[f["time"] for f in r["frames"]]})
    return {"reviews":result[:100]}


def compare(store,pid,baseline_id,review_id,threshold=16,max_ratio=.001):
    if isinstance(threshold,bool) or not isinstance(threshold,int) or not 0<=threshold<=255: raise EditorError("Próg kanału wymaga 0–255")
    max_ratio=number(max_ratio,"max_diff_ratio",0,1)
    if baseline_id == review_id: raise EditorError("Wybierz dwa różne przeglądy")
    root=store.directory(pid)/"reviews"
    old,new=load_review(store.directory(pid),baseline_id),load_review(store.directory(pid),review_id)
    # Compare only exactly matching schedules: a skipped frame must never look like a pass.
    if [f["time"] for f in old["frames"]] != [f["time"] for f in new["frames"]]:
        raise EditorError("Przeglądy wymagają tych samych czasów; wygeneruj nowy z times poprzedniego")
    frames=[]
    for i,(a,b) in enumerate(zip(old["frames"],new["frames"])):
        # Names are generated internally, never interpreted as arbitrary user paths.
        x=np.asarray(Image.open(root/baseline_id/f"frame-{i:03}.png").convert("RGB"),dtype=np.int16)
        y=np.asarray(Image.open(root/review_id/f"frame-{i:03}.png").convert("RGB"),dtype=np.int16)
        if x.shape != y.shape: raise EditorError("Nie można porównać różnych rozdzielczości")
        mask=np.any(np.abs(x-y)>threshold,axis=2);ratio=float(mask.mean())
        diff=y.astype(np.uint8);diff[mask]=[239,66,27]
        filename=f"diff-{i:03}.png";Image.fromarray(diff).save(root/review_id/filename)
        frames.append({"time":a["time"],"changedRatio":ratio,"matched":ratio<=max_ratio,
                       "diffUrl":f"/reviews/{pid}/{review_id}/{filename}"})
    report={"project_id":pid,"baseline_id":baseline_id,"review_id":review_id,"baselineRevision":old["revision"],"revision":new["revision"],
            "threshold":threshold,"maxDiffRatio":max_ratio,"frames":frames,"matched":all(f["matched"] for f in frames),
            "limitations":"Zmiana pikseli nie oznacza pogorszenia ani poprawy. Porównano tylko zapisane klatki. Baseline jest wskazanym przeglądem, nie automatyczną akceptacją jakości."}
    atomic_write(root/review_id/"comparison.json",json.dumps(report,ensure_ascii=False,indent=2))
    return report
