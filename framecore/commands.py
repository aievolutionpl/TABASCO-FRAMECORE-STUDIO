"""UI and MCP share this command vocabulary. No browser automation."""
from __future__ import annotations

from copy import deepcopy
from .model import EditorError, FORMATS, element, number, uid, track_accepts

STYLE_FIELDS = {"fontSize", "fontFamily", "fontWeight", "color", "align", "background", "radius"}
PROPERTIES = {"text", "x", "y", "width", "height", "rotation", "scale", "opacity", "start", "duration", "sourceStart"}


def target(p, args, session):
    eid = args.get("element_id")
    if not eid:
        if len(session["selection"]) != 1:
            raise EditorError("Zaznacz jeden element lub podaj element_id")
        eid = session["selection"][0]
    e = next((e for e in p["elements"] if e["id"] == eid), None)
    if not e:
        raise EditorError("Nie znaleziono elementu")
    track = next(t for t in p["tracks"] if t["id"] == e["trackId"])
    if track["locked"]:
        raise EditorError("Ścieżka jest zablokowana")
    return e


def slice_keyframes(keyframes, start, end):
    result = []
    for prop in sorted({k["property"] for k in keyframes}):
        points = sorted((k for k in keyframes if k["property"] == prop), key=lambda k: k["time"])
        def value(t):
            if t <= points[0]["time"]: return points[0]["value"]
            for a, b in zip(points, points[1:]):
                if t <= b["time"]:
                    u = (t-a["time"])/(b["time"]-a["time"])
                    return a["value"]+(b["value"]-a["value"])*u
            return points[-1]["value"]
        result.append({"property": prop, "time": 0, "value": value(start)})
        result.extend({**k, "time": k["time"]-start} for k in points if start < k["time"] < end)
        result.append({"property": prop, "time": end-start, "value": value(end)})
    return result


def storyboard(duration=15, title="Your product", workflow="Product launch"):
    number(duration, "duration", 3, 600)
    roles = ["OTWARCIE", "PROBLEM", "ODKRYCIE", "PRODUKT", "KORZYŚĆ", "DZIAŁANIE"]
    messages = ["Poznaj coś dla siebie.", "Mniej hałasu. Więcej sensu.", title, "Na każdy dzień.", "Mały detal. Duża różnica.", "Zacznij teraz."]
    weights = [2, 2, 3, 3, 3, 2]
    start = 0
    result = []
    for role, msg, weight in zip(roles, messages, weights):
        length = duration * weight / 15
        result.append({"id": uid("scene"), "name": role, "start": round(start, 6), "duration": round(length, 6),
                       "message": msg, "visualPurpose": f"{workflow}: {role.lower()}",
                       "motionIntent": "headline_impact" if role == "OTWARCIE" else "title_reveal", "audioIntent": "delikatny akcent"})
        start += length
    result[-1]["duration"] = duration - result[-1]["start"]
    return result


def mutate(p, name, args, session):
    if not isinstance(args, dict):
        raise EditorError("Argumenty komendy muszą być obiektem")
    if name == "assemble_visual_lesson":
        from .storytelling import assemble
        assemble(p,args,session)
    elif name == "set_learning_brief":
        from .storytelling import fields, BRIEF_FIELDS
        p["lesson"] = fields(args["brief"],BRIEF_FIELDS)
    elif name == "set_scene_learning":
        from .storytelling import fields, SCENE_FIELDS
        scene=next((s for s in p["scenes"] if s["id"]==args.get("scene_id")),None)
        if not scene:raise EditorError("Nie znaleziono sceny")
        scene["lesson"]={**scene.get("lesson",{}),**fields(args["lesson"],SCENE_FIELDS)}
    elif name == "set_project_fps":
        fps=number(args["fps"],"FPS",1,60)
        if not isinstance(fps,int):raise EditorError("FPS musi być liczbą całkowitą")
        p["canvas"]["fps"]=fps
    elif name == "add_track":
        from .model import KINDS
        kind=args.get("kind");label=args.get("name", "Nowa ścieżka")
        if kind not in KINDS or not isinstance(label,str) or not label.strip() or len(label)>100 or len(p["tracks"])>=24:
            raise EditorError("Podaj rodzaj i nazwę ścieżki; maksymalnie 24 ścieżki")
        p["tracks"].append({"id":uid("track"),"name":label,"kind":kind,"muted":False,"hidden":False,"locked":False})
    elif name == "replace_clip_asset":
        e=target(p,args,session)
        a=next((a for a in p["assets"] if a["id"]==args.get("asset_id")),None)
        if e["type"] not in {"image","video","audio"} or not a or a["kind"] not in {"image","video","audio"}:
            raise EditorError("Wybierz klip i poprawny materiał")
        new_kind='audio' if e['type']=='audio' and (a['kind']=='audio' or a['kind']=='video' and a.get('hasAudio')) else a['kind']
        if (e['type']=='audio') != (new_kind=='audio'):
            raise EditorError("Dźwięk można podmienić tylko dźwiękiem; obraz lub wideo materiałem wizualnym")
        fit=args.get('fit_source',False)
        if not isinstance(fit,bool):raise EditorError("fit_source musi być wartością logiczną")
        if a.get('duration') and a['duration']+.1<e['duration']:
            if not fit:raise EditorError("Źródło jest krótsze niż klip; zaznacz dopasowanie długości")
            e['duration']=a['duration'];e['keyframes']=slice_keyframes(e.get('keyframes',[]),0,e['duration'])
            for k in ('fadeIn','fadeOut'):
                if e.get('audio'):e['audio'][k]=min(e['audio'][k],e['duration'])
        current_track=next(t for t in p['tracks'] if t['id']==e['trackId'])
        if not track_accepts(current_track['kind'],new_kind):
            track=next((t for t in p['tracks'] if t['kind']==new_kind and not t['locked']),None)
            if not track:raise EditorError("Brak odblokowanej ścieżki dla tego materiału")
            e['trackId']=track['id']
        old=e['assetId'];e.update(assetId=a['id'],type=new_kind,sourceStart=0)
        if p['brand'].get('logoAssetId')==old:p['brand']['logoAssetId']=a['id'] if new_kind=='image' else None
    elif name == "set_production_contract":
        if not isinstance(args.get("contract"), dict): raise EditorError("Kontrakt musi być obiektem")
        p.setdefault("production", {}).update(deepcopy(args["contract"]))
    elif name == "set_scene_beat":
        scene = next((s for s in p["scenes"] if s["id"] == args.get("scene_id")), None)
        if not scene: raise EditorError("Nie znaleziono sceny")
        scene["beat"] = deepcopy(args["beat"])
    elif name == "annotate_story_beats":
        from .production import annotate_beats
        annotate_beats(p)
    elif name == "apply_motion_rules":
        from .production import MOTION_RULES
        for e in p["elements"]:
            if e["type"] in MOTION_RULES and e.get("motion"):
                target(p, {"element_id": e["id"]}, session)
                rule = MOTION_RULES[e["type"]]
                e["motion"].update(duration=max(.1, min(e["duration"], rule["duration"])), easing=rule["easing"])
    elif name.startswith("add_") and name[4:] in {"text", "video", "image", "audio", "caption", "shape"}:
        kind = name[4:]
        values = {k: deepcopy(v) for k, v in args.items() if k in PROPERTIES | {"id", "trackId", "assetId", "sceneId", "motion"}}
        e = element(p, kind, **values)
        if "style" in args:
            if set(args["style"]) - STYLE_FIELDS:
                raise EditorError("Nieznana właściwość stylu")
            e["style"].update(args["style"])
        p["elements"].append(e)
    elif name == "add_asset":
        a = deepcopy(args["asset"])
        p["assets"].append(a)
    elif name == "add_scene":
        p["scenes"].append({"id": uid("scene"), "name": str(args.get("name", "Scene"))[:200],
                             "start": args.get("start", 0), "duration": args.get("duration", 3),
                             "message": str(args.get("message", "")), "visualPurpose": "", "motionIntent": "title_reveal", "audioIntent": ""})
    elif name == "duplicate_scene":
        scene = next((s for s in p["scenes"] if s["id"] == args.get("scene_id")), None)
        if not scene:
            raise EditorError("Nie znaleziono sceny")
        copy = deepcopy(scene)
        copy["id"] = uid("scene")
        copy["start"] = args.get("start", scene["start"] + scene["duration"])
        delta = copy["start"] - scene["start"]
        copies = []
        for e in p["elements"]:
            if e.get("sceneId") == scene["id"]:
                e = deepcopy(e)
                e.update(id=uid("el"), sceneId=copy["id"], start=e["start"] + delta)
                copies.append(e)
        p["scenes"].append(copy)
        p["elements"].extend(copies)
    elif name in {"add_icon", "add_library_asset"}:
        from .library import icon_asset, library_asset
        a = icon_asset(args["icon_id"]) if name == "add_icon" else library_asset(args["asset_id"])
        p["assets"].append(a)
        p["elements"].append(element(p, "image", assetId=a["id"], start=args.get("start", session["playhead"]),
                                     duration=args.get("duration", min(3, p["duration"]-session["playhead"])),
                                     x=args.get("x", p["canvas"]["width"]*.1), y=args.get("y", p["canvas"]["height"]*.5),
                                     width=args.get("width", 160), height=args.get("height", 160)))
    elif name == "apply_template":
        from .templates import template_scenes
        scenes = template_scenes(args["template_id"], p["duration"], args.get("title", p["metadata"]["name"]))
        mutate(p, "assemble_storyboard", {"scenes": scenes, "replace": args.get("replace", False), "template_id": args["template_id"]}, session)
    elif name == "set_background":
        from .backgrounds import resolve
        bg = resolve(args["background_id"])
        animated = args.get("animated", True)
        if not isinstance(animated, bool): raise EditorError("Ruch tła wymaga wartości logicznej")
        p["canvas"].update(background=bg["colors"][0], backgroundPreset=bg["id"], backgroundAnimated=animated)
    elif name == "duplicate_clip":
        e = target(p, args, session)
        copy = deepcopy(e)
        copy.update(id=uid("el"), start=args.get("start", e["start"]+e["duration"]))
        p["elements"].append(copy)
    elif name == "set_audio":
        e = target(p, args, session)
        if e["type"] != "audio":
            raise EditorError("Wybierz klip dźwiękowy")
        if set(args.get("audio", {})) - {"gain", "fadeIn", "fadeOut"}:
            raise EditorError("Nieznane ustawienie dźwięku")
        e.setdefault("audio", {"gain": 1, "fadeIn": 0, "fadeOut": 0}).update(args.get("audio", {}))
    elif name == "set_keyframes":
        e = target(p, args, session)
        e["keyframes"] = deepcopy(args["keyframes"])
    elif name == "set_duration":
        p["duration"] = number(args["duration"], "duration", .1, 600)
    elif name == "move_element":
        e = target(p, args, session)
        for kf in e.get("keyframes", []):
            if kf["property"] in {"x", "y"}:
                kf["value"] += args[kf["property"]] - e[kf["property"]]
        e.update(x=args["x"], y=args["y"])
    elif name == "resize_element":
        e = target(p, args, session)
        e.update(width=args["width"], height=args["height"])
    elif name == "set_property":
        e = target(p, args, session)
        key = args["property"]
        if key in PROPERTIES:
            if key in {"x", "y", "rotation", "scale", "opacity"}:
                number(args["value"], key)
                for kf in e.get("keyframes", []):
                    if kf["property"] == key: kf["value"] += args["value"] - e[key]
            e[key] = args["value"]
        elif key.startswith("style.") and key[6:] in STYLE_FIELDS:
            e["style"][key[6:]] = args["value"]
            if key == "style.fontFamily":
                from .library import manifest
                face = next((f for f in manifest()["fonts"] if f["family"] == args["value"]), None)
                if face: e["style"]["fontWeight"] = max(face["weight"][0], min(e["style"]["fontWeight"], face["weight"][1]))
        else:
            raise EditorError("Właściwość nie jest edytowalna")
    elif name == "move_clip":
        e = target(p, args, session)
        e["start"] = args["start"]
        if "track_id" in args:
            track=next((t for t in p['tracks'] if t['id']==args['track_id']),None)
            if not track or not track_accepts(track['kind'],e['type']) or track['locked']:
                raise EditorError("Wybierz odblokowaną zgodną ścieżkę (obrazy i wideo można mieszać)")
            e["trackId"] = args["track_id"]
    elif name == "trim_clip":
        e = target(p, args, session)
        new_start = args.get("start", e["start"])
        delta = new_start - e["start"]
        e["keyframes"] = slice_keyframes(e.get("keyframes", []), delta, delta+args["duration"])
        if e["type"] in {"video", "audio"}:
            e["sourceStart"] += new_start - e["start"]
        e.update(start=new_start, duration=args["duration"])
        if e.get("audio"):
            for k in ("fadeIn", "fadeOut"): e["audio"][k] = min(e["audio"][k], e["duration"])
    elif name == "split_clip":
        e = target(p, args, session)
        at = number(args.get("time", session["playhead"]), "split time")
        offset = at - e["start"]
        if not .01 < offset < e["duration"] - .01:
            raise EditorError("Punkt podziału musi znajdować się wewnątrz klipu")
        second = deepcopy(e)
        second.update(id=uid("el"), start=at, duration=e["duration"] - offset,
                      sourceStart=e["sourceStart"] + offset, motionOffset=e.get("motionOffset", 0) + offset)
        second["keyframes"] = slice_keyframes(e.get("keyframes", []), offset, e["duration"])
        e["keyframes"] = slice_keyframes(e.get("keyframes", []), 0, offset)
        e["duration"] = offset
        if e.get("audio"):
            e["audio"]["fadeOut"] = 0
            second["audio"]["fadeIn"] = 0
            e["audio"]["fadeIn"] = min(e["audio"]["fadeIn"], offset)
            second["audio"]["fadeOut"] = min(second["audio"]["fadeOut"], second["duration"])
        p["elements"].append(second)
    elif name == "delete_clip":
        e = target(p, args, session)
        p["elements"].remove(e)
    elif name == "apply_motion":
        e = target(p, args, session)
        e["motion"] = {"id": args["motion_id"], "duration": args.get("duration", .8), "easing": args.get("easing", "cubic-out")}
        e.pop("motionOffset", None)
    elif name == "set_format":
        fmt = args["format"]
        if fmt not in FORMATS:
            raise EditorError("Nieobsługiwany format")
        ow, oh = p["canvas"]["width"], p["canvas"]["height"]
        w, h = FORMATS[fmt]
        for e in p["elements"]:
            for prop in ("x", "width"):
                e[prop] *= w / ow
            for prop in ("y", "height"):
                e[prop] *= h / oh
            e["style"]["fontSize"] *= w / ow
            for keyframe in e.get("keyframes", []):
                if keyframe["property"] == "x": keyframe["value"] *= w / ow
                if keyframe["property"] == "y": keyframe["value"] *= h / oh
        p["canvas"].update(width=w, height=h)
    elif name == "attach_brand_snapshot":
        p["assets"].extend(deepcopy(args["assets"]))
        p["brandProfile"] = deepcopy(args["snapshot"])
        mutate(p, "set_brand", {"brand": args["brand"], "restyle": args["restyle"]}, session)
    elif name == "set_brand":
        supplied = args.get("brand", {})
        allowed = {"name", "colors", "font", "logoAssetId", "captionStyle", "motionStyle", "ctaStyle"}
        if set(supplied) - allowed:
            raise EditorError("Nieznana właściwość marki")
        p["brand"].update(deepcopy(supplied))
        if args.get("restyle", True):
            p["canvas"]["background"] = p["brand"]["colors"]["background"]
            p["canvas"].pop("backgroundPreset", None)
            for e in p["elements"]:
                if e["type"] in {"text", "caption"}:
                    e["style"].update(color=p["brand"]["colors"]["text"], fontFamily=p["brand"]["font"])
    elif name == "style_captions":
        style = args["style"]
        if set(style) - STYLE_FIELDS:
            raise EditorError("Nieznany styl napisów")
        for e in p["elements"]:
            if e["type"] == "caption":
                e["style"].update(style)
    elif name == "set_track":
        track = next((t for t in p["tracks"] if t["id"] == args.get("track_id")), None)
        if not track or args.get("property") not in {"muted", "hidden", "locked"} or not isinstance(args.get("value"), bool):
            raise EditorError("Nieprawidłowa właściwość ścieżki")
        track[args["property"]] = args["value"]
    elif name == "assemble_storyboard":
        if p["elements"] and not args.get("replace", False):
            raise EditorError("Montaż zastąpi obecne zmiany; użyj sprawdzonej propozycji")
        scenes = deepcopy(args["scenes"])
        p["scenes"] = scenes
        p["elements"] = []
        w, h = p["canvas"]["width"], p["canvas"]["height"]
        images = [a for a in p["assets"] if a["kind"] == "image"]
        logo = next((a for a in images if a["id"] == p["brand"].get("logoAssetId")), None) or next((a for a in images if a.get("role") == "logo"), None)
        products = [a for a in images if not logo or a["id"] != logo["id"]]
        product = next((a for a in products if a.get("role") == "product"), products[0] if products else None)
        videos = [a for a in p["assets"] if a["kind"] == "video"]
        audios = [a for a in p["assets"] if a["kind"] == "audio"] or [a for a in videos if a.get("hasAudio")]
        for idx, scene in enumerate(scenes):
            start, length = scene["start"], scene["duration"]
            if videos and idx in {0, 3}:
                video = videos[0]
                vd = min(length, video.get("duration") or length)
                p["elements"].append(element(p, "video", assetId=video["id"], sceneId=scene["id"], start=start, duration=vd,
                                              x=0, y=0, width=w, height=h, opacity=.45))
            if product and idx in {1, 2, 4}:
                p["elements"].append(element(p, "image", assetId=product["id"], sceneId=scene["id"], start=start, duration=length,
                                              x=w*.12, y=h*.32, width=w*.76, height=h*.45, motion={"id": "scale-in", "duration": .8}))
            title = element(p, "text", text=scene["message"], sceneId=scene["id"], start=start, duration=length,
                            y=h*.17, height=h*.2, motion={"id": "impact-rise" if idx == 0 else "premium-blur-reveal", "duration": .8})
            p["elements"].append(title)
            label = element(p, "caption", text=scene["name"] + " / " + str(idx+1).zfill(2), sceneId=scene["id"], start=start, duration=length,
                            y=h*.86, height=h*.05, motion={"id": "soft-fade", "duration": .4})
            label["style"].update(fontSize=w*.024, fontWeight=400, color=p["brand"]["colors"]["accent"])
            p["elements"].append(label)
        if logo:
            p["brand"]["logoAssetId"] = logo["id"]
            p["elements"].append(element(p, "image", assetId=logo["id"], start=0, duration=p["duration"],
                                          x=w*.08, y=h*.06, width=w*.18, height=h*.06, motion={"id": "logo-settle", "duration": .6}))
        if audios:
            a = audios[0]
            p["elements"].append(element(p, "audio", assetId=a["id"], start=0, duration=min(p["duration"], a.get("duration") or p["duration"])))
        if args.get("template_id"):
            from .templates import apply_look
            apply_look(p, args["template_id"])
    elif name == "rename_project":
        p["metadata"]["name"] = str(args["name"])[:200]
    else:
        raise EditorError(f"Nieobsługiwana komenda: {name}")
    # Editing a focused clip may remove it or move it outside its beat. Keep the
    # narrative description and ask for a new focus rather than blocking editing.
    if name in {"delete_clip", "trim_clip", "move_clip", "split_clip", "duplicate_scene", "assemble_storyboard", "set_property", "replace_clip_asset"}:
        for scene in p["scenes"]:
            beat = scene.get("beat")
            if not beat or not beat.get("focusElementId"): continue
            focus = next((e for e in p["elements"] if e["id"] == beat["focusElementId"]), None)
            if not focus or focus["start"] >= scene["start"]+scene["duration"] or focus["start"]+focus["duration"] <= scene["start"]:
                beat["focusElementId"] = None
