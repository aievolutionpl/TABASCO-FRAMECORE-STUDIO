"""Versioned JSON model. All callers validate before committing content."""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath

from . import motion

FORMATS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}
KINDS = {"video", "image", "audio", "text", "caption", "shape"}


class EditorError(ValueError):
    def __init__(self, message, code="invalid_command"):
        super().__init__(message)
        self.code = code


def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex[:12]


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise EditorError(f"{name} musi być liczbą skończoną")
    if low is not None and value < low or high is not None and value > high:
        raise EditorError(f"{name} poza obsługiwanym zakresem")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise EditorError("Nieprawidłowy identyfikator")
    return value


def project(name="Projekt bez nazwy", format="9:16", duration=15, brief="", workflow="Premiera produktu"):
    if format not in FORMATS:
        raise EditorError("Nieobsługiwany format")
    w, h = FORMATS[format]
    p = {"schemaVersion": 1, "id": uid("fc"), "revision": 0,
         "metadata": {"name": str(name)[:200], "brief": str(brief)[:10000], "workflow": str(workflow)[:200], "createdAt": now(), "updatedAt": now()},
         "canvas": {"width": w, "height": h, "fps": 30, "background": "#101415"},
         "duration": duration, "assets": [], "scenes": [], "elements": [],
         "tracks": [{"id": k, "name": n, "kind": k, "muted": False, "hidden": False, "locked": False}
                    for k, n in [("video", "Nagrania"), ("image", "Obrazy i logo"), ("shape", "Kształty"),
                                 ("text", "Teksty"), ("caption", "Napisy"), ("audio", "Dźwięk")]],
         "brand": {"name": "Studio", "colors": {"background": "#101415", "text": "#f5f3ec", "accent": "#c1df98"},
                   "font": "Arial", "logoAssetId": None, "captionStyle": "minimal", "motionStyle": "premium", "ctaStyle": "pill"},
         "exportProfiles": list(FORMATS)}
    validate(p)
    return p


def element(p, type="text", **values):
    w, h = p["canvas"]["width"], p["canvas"]["height"]
    e = {"id": uid("el"), "type": type, "trackId": type, "sceneId": None, "assetId": None,
         "text": "Twój nagłówek", "start": 0, "duration": min(3, p["duration"]), "sourceStart": 0,
         "x": w * .08, "y": h * .16, "width": w * .84, "height": h * .22,
         "scale": 1, "rotation": 0, "opacity": 1,
         "style": {"fontSize": max(24, w * .065), "fontFamily": p["brand"]["font"], "fontWeight": 700,
                   "color": p["brand"]["colors"]["text"], "align": "left", "background": "transparent", "radius": 0},
         "motion": {"id": "soft-fade", "duration": .6}, "effects": [], "keyframes": []}
    e.update(values)
    return e


def validate(p):
    if not isinstance(p, dict) or p.get("schemaVersion") != 1:
        raise EditorError("Nieobsługiwany schemat projektu")
    identifier(p["id"])
    number(p["duration"], "duration", .1, 600)
    for k in ("width", "height"):
        number(p["canvas"][k], k, 64, 4096)
        if not isinstance(p["canvas"][k], int) or p["canvas"][k] % 2:
            raise EditorError("Wymiary filmu muszą być parzystymi liczbami całkowitymi")
    number(p["canvas"]["fps"], "fps", 1, 60)
    if not isinstance(p["canvas"]["fps"], int):
        raise EditorError("FPS musi być liczbą całkowitą")
    if p["canvas"].get("backgroundPreset"):
        from .backgrounds import resolve
        resolve(p["canvas"]["backgroundPreset"])
    if "backgroundAnimated" in p["canvas"] and not isinstance(p["canvas"]["backgroundAnimated"], bool):
        raise EditorError("Nieprawidłowe ustawienie animacji tła")
    ids = []
    for group in ("elements", "tracks", "scenes", "assets"):
        if not isinstance(p[group], list) or len(p[group]) > 1000:
            raise EditorError(f"Nieprawidłowa kolekcja: {group}")
        for item in p[group]:
            ids.append(identifier(item["id"]))
    if len(ids) != len(set(ids)):
        raise EditorError("Powtórzone identyfikatory")
    tracks = {t["id"] for t in p["tracks"]}
    scenes = {s["id"] for s in p["scenes"]}
    assets = {a["id"]: a for a in p["assets"]}
    for t in p["tracks"]:
        if t["kind"] not in KINDS or any(not isinstance(t[k], bool) for k in ("muted", "hidden", "locked")):
            raise EditorError("Nieprawidłowa ścieżka")
    if not isinstance(p["brand"]["font"], str) or len(p["brand"]["font"]) > 200:
        raise EditorError("Nieprawidłowy font marki")
    for k in ("background", "text", "accent"):
        if not isinstance(p["brand"]["colors"].get(k), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", p["brand"]["colors"][k]):
            raise EditorError("Kolory marki wymagają sześciocyfrowych wartości hex")
    for a in p["assets"]:
        path = PurePosixPath(a["file"])
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 2 or path.parts[0] != "assets":
            raise EditorError("Materiał musi być lokalnym plikiem projektu")
        if a["kind"] not in {"video", "image", "audio", "font"}:
            raise EditorError("Nieobsługiwany typ materiału")
    for scene in p["scenes"]:
        number(scene["start"], "scene start", 0, p["duration"])
        number(scene["duration"], "scene duration", .01, p["duration"])
        if scene["start"] + scene["duration"] > p["duration"] + 1e-6:
            raise EditorError("Scena przekracza długość projektu")
    for e in p["elements"]:
        if e["type"] not in KINDS or e["trackId"] not in tracks:
            raise EditorError("Nieprawidłowy typ elementu lub ścieżka")
        if e.get("sceneId") and e["sceneId"] not in scenes:
            raise EditorError("Nieznana scena")
        if e.get("assetId") and e["assetId"] not in assets:
            raise EditorError("Nieznany materiał")
        if e["type"] in {"video", "image", "audio"}:
            asset = assets.get(e.get("assetId"))
            if not asset or asset["kind"] != e["type"] and not (e["type"] == "audio" and asset["kind"] == "video" and asset.get("hasAudio")):
                raise EditorError("Element wymaga materiału zgodnego z jego typem")
        for k in ("x", "y", "rotation"):
            number(e[k], k, -10000, 10000)
        for k in ("width", "height"):
            number(e[k], k, 1, 10000)
        number(e["scale"], "scale", .01, 20)
        number(e["opacity"], "opacity", 0, 1)
        number(e["start"], "start", 0, p["duration"])
        number(e["duration"], "clip duration", .01, p["duration"])
        number(e.get("sourceStart", 0), "sourceStart", 0, 36000)
        number(e.get("motionOffset", 0), "motionOffset", 0, 36000)
        if e["start"] + e["duration"] > p["duration"] + 1e-6:
            raise EditorError("Klip przekracza długość projektu")
        a = assets.get(e.get("assetId"))
        if a and a.get("duration") and e["sourceStart"] + e["duration"] > a["duration"] + .1:
            raise EditorError("Klip przekracza długość materiału źródłowego")
        m = e.get("motion")
        if m:
            if not motion.resolve(m["id"]):
                raise EditorError("Nieznana animacja")
            number(m["duration"], "motion duration", .1, 2)
        if e.get("effects"):
            raise EditorError("Użyj animacji z biblioteki; efekty własne nie są obsługiwane")
        if not isinstance(e.get("keyframes", []), list) or len(e.get("keyframes", [])) > 200:
            raise EditorError("Nieprawidłowa lista klatek kluczowych")
        seen = set()
        for kf in e.get("keyframes", []):
            if not isinstance(kf, dict) or set(kf) != {"property", "time", "value"}:
                raise EditorError("Klatka wymaga property, time i value")
            prop = kf["property"]
            bounds = {"x": (-10000,10000), "y": (-10000,10000), "rotation": (-10000,10000), "scale": (.01,20), "opacity": (0,1)}
            if prop not in bounds:
                raise EditorError("Nieobsługiwana właściwość klatki kluczowej")
            number(kf["time"], "keyframe time", 0, e["duration"])
            number(kf["value"], "keyframe value", *bounds[prop])
            key = (prop, kf["time"])
            if key in seen:
                raise EditorError("Powtórzona klatka kluczowa")
            seen.add(key)
        if e.get("audio"):
            if e["type"] != "audio" or set(e["audio"]) != {"gain", "fadeIn", "fadeOut"}:
                raise EditorError("Nieprawidłowe parametry audio")
            number(e["audio"]["gain"], "gain", 0, 1)
            for prop in ("fadeIn", "fadeOut"):
                number(e["audio"][prop], prop, 0, e["duration"])
        style = e["style"]
        if not isinstance(style["fontFamily"], str) or not style["fontFamily"].strip() or len(style["fontFamily"]) > 200 or any(ord(c) < 32 for c in style["fontFamily"]):
            raise EditorError("Nieprawidłowa nazwa fontu")
        number(style["fontWeight"], "fontWeight", 100, 1000)
        if not isinstance(style["fontWeight"], int):
            raise EditorError("Grubość fontu musi być liczbą całkowitą")
        number(style["fontSize"], "fontSize", 1, 600)
        number(style["radius"], "radius", 0, 1000)
        if style["align"] not in {"left", "center", "right"}:
            raise EditorError("Nieprawidłowe wyrównanie")
        if not isinstance(e["text"], str) or len(e["text"]) > 10000:
            raise EditorError("Tekst jest zbyt długi")
    logo = p["brand"].get("logoAssetId")
    if logo and (logo not in assets or assets[logo]["kind"] != "image"):
        raise EditorError("Logo marki musi być obrazem")
    return p
