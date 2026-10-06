"""Edytowalne filmy demo Ruchu 2.0: showreel 16:9 i rolka 9:16.

Każdy element powstaje przez to samo API co w edytorze i MCP, więc po utworzeniu
projekt można dalej montować ręcznie albo z agentem.
"""
import io
import shutil
import wave
from pathlib import Path

import numpy as np

from .api import API
from .render import RenderJobs

ROOT = Path(__file__).resolve().parents[1]
INK, ACCENT, MINT = "#f6f1e8", "#ff7a45", "#9ff0c8"
WARM = {"from": "#fff1dc", "to": "#ff7a45", "angle": 100}


def music(duration, scene=4.0, bpm=120, seed=7):
    """Procedural score: pad chords per scene, kick on the beat, whoosh into every cut."""
    sr = 44100
    t = np.arange(int(sr * duration)) / sr
    track = np.zeros_like(t)
    chords = ((110, 164.81, 220, 277.18), (98, 146.83, 196, 246.94), (130.81, 196, 261.63, 329.63), (123.47, 185, 246.94, 311.13))
    for i in range(int(np.ceil(duration / scene))):
        section = (t >= i * scene) & (t < (i + 1) * scene)
        local = t[section] - i * scene
        env = np.minimum(1, local / .35) * np.minimum(1, (scene - local) / .5)
        chord = chords[i % len(chords)]
        track[section] += env * sum(.022 * np.sin(2 * np.pi * f * local) + .007 * np.sin(2 * np.pi * f * 2.01 * local) for f in chord)
    beat = 60 / bpm
    phase = t % beat
    track += .16 * np.exp(-phase * 22) * np.sin(2 * np.pi * (48 * phase + 3.2 * (1 - np.exp(-phase * 30))))
    hat = (t + beat / 2) % beat
    rng = np.random.default_rng(seed)
    track += rng.normal(0, .018, len(t)) * np.exp(-hat * 120)
    noise = rng.normal(0, 1, len(t))
    for cut in np.arange(scene, duration, scene):
        d = t - cut
        swell = np.where((d > -.6) & (d < .15), np.exp(-((d + .1) / .22) ** 2), 0)
        track += .06 * swell * noise
        track += np.where((d >= 0) & (d < .9), .09 * np.sin(2 * np.pi * 55 * d) * np.exp(-d * 6), 0)
    track *= np.minimum(1, t / .4) * np.minimum(1, (duration - t) / 1.2)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(sr)
        out.writeframes((np.clip(track, -.95, .95) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


class _Builder:
    def __init__(self, store, name, fmt, duration, brief):
        self.store, self.api = store, API(store, RenderJobs(store))
        self.state = self.api.call("create_project", {"name": name, "format": fmt, "duration": duration, "brief": brief})
        self.pid = self.state["project"]["id"]

    def __call__(self, tool, **args):
        self.state = self.api.call(tool, {"project_id": self.pid, "expected_revision": self.state["project"]["revision"], **args}, actor="agent")
        elements = self.state["project"]["elements"]
        return elements[-1]["id"] if elements else None

    def text(self, text, start, duration, x, y, w, h, motion, exit=None, **style):
        style.setdefault("fontFamily", "Manrope"); style.setdefault("fontWeight", 800); style.setdefault("color", INK)
        args = dict(text=text, start=start, duration=duration, x=x, y=y, width=w, height=h, style=style, motion=motion)
        if exit: args["exit"] = exit
        return self("add_text", **args)

    def image(self, asset_id, start, duration, x, y, w, h, motion, exit=None, opacity=1, **style):
        eid = self("add_library_asset", asset_id=asset_id, start=start, duration=duration, x=x, y=y, width=w, height=h)
        self("apply_motion", element_id=eid, motion_id=motion["id"], duration=motion["duration"], easing=motion.get("easing", "cubic-out"))
        if exit: self("apply_exit", element_id=eid, exit_id=exit["id"], duration=exit["duration"])
        if opacity != 1: self("set_property", element_id=eid, property="opacity", value=opacity)
        for key, value in style.items(): self("set_property", element_id=eid, property="style." + key, value=value)
        return eid

    def soundtrack(self, filename, duration, scene):
        imports = self.store.root.parent / "imports"; imports.mkdir(parents=True, exist_ok=True)
        audio = imports / filename; audio.write_bytes(music(duration, scene))
        self("add_asset", source_file=str(audio.resolve()), role="audio")
        aid = self.state["project"]["assets"][-1]["id"]
        clip = next((e for e in self.state["project"]["elements"] if e["type"] == "audio" and e.get("assetId") == aid), None)
        eid = clip["id"] if clip else self("add_audio", assetId=aid, start=0, duration=duration)
        self("set_audio", element_id=eid, audio={"gain": .9, "fadeIn": .3, "fadeOut": 1.0})


def create_showreel(store):
    """24 s, 16:9: sześć scen po 4 s pokazujących Ruch 2.0."""
    b = _Builder(store, "FRAMECORE — Motion 2.0 showreel", "16:9", 24,
                 "Showreel nowego silnika ruchu: tekst kinetyczny, wejścia i wyjścia, look filmowy. Sześć scen po 4 s.")
    b("set_brand", brand={"name": "FRAMECORE", "font": "Manrope", "colors": {"background": "#07090b", "text": INK, "accent": ACCENT}})
    b("set_background", background_id="graphite", animated=True)
    scenes = ["Otwarcie", "Tekst kinetyczny", "Wejścia i wyjścia", "Dekodowanie", "Look filmowy", "Zaproszenie"]
    for i, name in enumerate(scenes):
        b("add_scene", name=f"{i+1:02d} / {name}", start=i * 4, duration=4, message=name)
    # Backgrounds first so typography always sits above them.
    for start, asset, opacity in ((0, "shared-frame", .95), (4, "motion-cards", .55), (12, "open-frame", .7), (16, "shared-frame", .5), (20, "open-frame", .9)):
        b.image("campaign-" + asset, start, 4, 0, 0, 1920, 1080, {"id": "ken-burns", "duration": .7, "easing": "quad-out"}, opacity=opacity)
    # Scene 03 gets its own backdrop so every cut has clips on both sides.
    b("add_shape", start=8, duration=4, x=0, y=0, width=1920, height=1080, motion={"id": "soft-fade", "duration": .2},
      style={"gradient": {"from": "#0b0f14", "to": "#2a1a14", "angle": 160}, "radius": 0, "background": "#0b0f14"})
    kicker = dict(fontSize=36, fontWeight=700, color=ACCENT, letterSpacing=6)
    leave = {"id": "fade-out", "duration": .35}

    # 01 — opening
    b.text("FRAMECORE  ·  MOTION 2.0", .2, 3.8, 120, 300, 1100, 50, {"id": "word-cascade", "duration": .9}, leave, **kicker)
    b.text("Ruch, który\nopowiada.", .35, 3.65, 112, 370, 1150, 360, {"id": "char-rise", "duration": 1.4, "easing": "back-out"},
           {"id": "blur-out", "duration": .45}, fontSize=150, gradient=WARM, shadow="lift")
    b.text("Tekst kinetyczny · wejścia i wyjścia · look filmowy", 1.6, 2.4, 120, 760, 1300, 60, {"id": "word-blur", "duration": 1.0},
           leave, fontSize=38, fontWeight=500, color="#c9c4bb")

    # 02 — kinetic text
    b.text("01  /  TEKST KINETYCZNY", 4.15, 3.85, 120, 230, 1100, 50, {"id": "word-cascade", "duration": .7}, leave, **kicker)
    b.text("> litera po literze", 4.4, 3.6, 120, 320, 1300, 110, {"id": "type-on", "duration": 1.2, "easing": "linear"}, leave,
           fontFamily="JetBrains Mono", fontSize=78, fontWeight=500, color=MINT, shadow="glow", shadowColor="#2fd39a")
    b.text("Każde słowo trafia\nw rytm muzyki.", 5.3, 2.7, 116, 480, 1400, 260, {"id": "word-highlight", "duration": 2.2},
           {"id": "rise-out", "duration": .4}, fontSize=104, shadow="soft")
    b.text("char-rise · word-cascade · scramble · karaoke", 6.0, 2.0, 120, 820, 1300, 50, {"id": "word-blur", "duration": .8}, leave,
           fontFamily="JetBrains Mono", fontSize=36, fontWeight=500, color="#9a958d")

    # 03 — entrances and exits on cards
    b.text("02  /  WEJŚCIA I WYJŚCIA", 8.15, 3.85, 120, 120, 1100, 50, {"id": "word-cascade", "duration": .7}, leave, **kicker)
    cards = [("iris-open", "zoom-through", "fluent-rocket", "glitch-in", "#ff7a45", "#ffb36b", "IRIS + GLITCH"),
             ("stretch-pop", "drop-out", "fluent-sparkles", "swing-in", "#7a5cff", "#ff6ad5", "STRETCH + SWING"),
             ("skew-slide", "slide-out-right", "fluent-fire", "zoom-blur-in", "#18b7a0", "#9ff0c8", "SKEW + ZOOM")]
    b("add_track", kind="image", name="Ilustracje nad kartami")
    art_track = b.state["project"]["tracks"][-1]["id"]
    for i, (card_in, card_out, art, art_in, c1, c2, label) in enumerate(cards):
        x, start = 120 + i * 580, 8.35 + i * .3
        b("add_shape", start=start, duration=12 - start, x=x, y=230, width=520, height=640, motion={"id": card_in, "duration": .8, "easing": "back-out" if card_in == "stretch-pop" else "expo-out"},
          exit={"id": card_out, "duration": .45}, style={"gradient": {"from": c1, "to": c2, "angle": 150}, "radius": 44, "shadow": "lift", "background": c1})
        art_id = b.image(art, start + .35, 12 - start - .35, x + 110, 300, 300, 300, {"id": art_in, "duration": .7}, {"id": card_out, "duration": .45}, shadow="soft")
        b("move_clip", element_id=art_id, start=start + .35, track_id=art_track)
        b.text(label, start + .6, 12 - start - .6, x + 40, 700, 440, 60, {"id": "scramble-in", "duration": .8}, {"id": card_out, "duration": .45},
               fontFamily="JetBrains Mono", fontSize=36, fontWeight=700, color="#ffffff", align="center", letterSpacing=1)

    # 04 — decode
    b.text("03  /  DEKODOWANIE", 12.15, 3.85, 120, 260, 1100, 50, {"id": "word-cascade", "duration": .7}, leave, **kicker)
    b.text("TWÓJ POMYSŁ\nW KADRZE", 12.4, 3.6, 112, 340, 1100, 330, {"id": "scramble-in", "duration": 1.6},
           {"id": "zoom-through", "duration": .45}, fontFamily="Space Grotesk", fontSize=140, fontWeight=700, color="#fff4ea",
           shadow="neon", shadowColor=ACCENT)
    b.text("Deterministycznie: podgląd = eksport, klatka w klatkę.", 13.6, 2.4, 120, 720, 1200, 60, {"id": "word-blur", "duration": .9},
           leave, fontSize=38, fontWeight=500, color="#d4cdc2")

    # 05 — film look
    b.text("04  /  LOOK FILMOWY", 16.15, 3.85, 120, 220, 1100, 50, {"id": "word-cascade", "duration": .7}, leave, **kicker)
    for i, (word, color) in enumerate((("Kolor.", INK), ("Ziarno.", INK), ("Przejścia.", INK), ("Shadery.", ACCENT))):
        b.text(word, 16.4 + i * .35, 3.6 - i * .35, 112, 300 + i * 125, 1000, 125, {"id": "skew-slide", "duration": .6, "easing": "expo-out"},
               {"id": "slide-out-left", "duration": .35}, fontSize=104, color=color, shadow="soft")
    b.text("Rozpływ · wypalenie · panorama\nglitch · przesłona · kinowy zoom", 17.8, 2.2, 1000, 860, 800, 110, {"id": "word-blur", "duration": .8},
           leave, fontSize=36, fontWeight=500, color="#c9c4bb", align="right")

    # 06 — call to action
    b.text("Zbuduj film\nz agentem.", 20.3, 3.7, 112, 290, 1150, 330, {"id": "char-rise", "duration": 1.3, "easing": "back-out"}, None,
           fontSize=136, gradient=WARM, shadow="lift")
    b.text("$ python framecore.py editor", 21.4, 2.6, 120, 660, 1200, 80, {"id": "type-on", "duration": 1.2, "easing": "linear"}, None,
           fontFamily="JetBrains Mono", fontSize=44, fontWeight=500, color=MINT)
    b.text("TABASCO CREATIVES + FRAMECORE — STUDIO", 22.2, 1.8, 120, 790, 1200, 50, {"id": "word-cascade", "duration": .8}, None, **kicker)

    # Persistent chrome
    b.text("FRAMECORE", 0, 24, 120, 64, 600, 60, {"id": "logo-settle", "duration": .8}, None, fontSize=36, letterSpacing=4)
    for i in range(6):
        b.text(f"{i+1:02d} / 06", i * 4 + .1, 3.9, 1560, 64, 240, 60, {"id": "soft-fade", "duration": .3}, None,
               fontFamily="JetBrains Mono", fontSize=36, fontWeight=500, color="#9a958d", align="right")
    b("set_canvas_fx", fx={"grade": "cinematic", "vignette": .4, "grain": .18, "letterbox": 0, "transition": "light-leak",
                           "transitionDuration": .9, "motionBlur": True})
    # A different shader-style transition on every cut (inspired by HyperFrames shader transitions).
    scenes_by_start = {round(sc["start"], 3): sc["id"] for sc in b.state["project"]["scenes"]}
    for start, transition, duration in ((4, "domain-warp", .9), (8, "whip-pan", .6), (12, "glitch", .5), (16, "ridged-burn", .9), (20, "sdf-iris", .8)):
        b("set_scene_transition", scene_id=scenes_by_start[start], transition_id=transition, duration=duration)
    b.soundtrack("framecore-motion2-showreel.wav", 24, 4)
    b("set_playhead", time=1.6)
    return b.state


def create_reel(store):
    """12 s, 9:16: rolka społecznościowa z napisami karaoke i look „Rolka”."""
    b = _Builder(store, "FRAMECORE — rolka Motion 2.0", "9:16", 12,
                 "Pionowa rolka: kinetyczne napisy, karaoke i błyski na cięciach. Trzy sceny po 4 s.")
    b("set_brand", brand={"name": "FRAMECORE", "font": "Manrope", "colors": {"background": "#07090b", "text": INK, "accent": ACCENT}})
    b("set_background", background_id="ember", animated=True)
    for i, name in enumerate(("Hak", "Napisy", "Zaproszenie")):
        b("add_scene", name=f"{i+1:02d} / {name}", start=i * 4, duration=4, message=name)
    for start, asset, opacity in ((0, "motion-cards", .42), (4, "shared-frame", .45), (8, "open-frame", .8)):
        b.image("campaign-" + asset, start, 4, 0, 0, 1080, 1920, {"id": "ken-burns", "duration": .6}, opacity=opacity, fit="cover")
    leave = {"id": "fade-out", "duration": .3}
    kicker = dict(fontSize=34, fontWeight=700, color=ACCENT, letterSpacing=8, align="center")
    b.text("ROLKA  ·  9:16", .15, 3.85, 90, 330, 900, 60, {"id": "word-cascade", "duration": .7}, leave, **kicker)
    b.text("Napisy,\nktóre\nzatrzymują.", .3, 3.7, 70, 430, 940, 620, {"id": "char-rise", "duration": 1.4, "easing": "back-out"},
           {"id": "zoom-through", "duration": .4}, fontSize=124, align="center", gradient=WARM, shadow="lift")
    b.image("fluent-fire", 1.4, 2.6, 400, 1180, 280, 280, {"id": "stretch-pop", "duration": .7, "easing": "back-out"}, {"id": "scale-out", "duration": .3}, shadow="glow", shadowColor="#ff7a45")

    b.text("KARAOKE", 4.15, 3.85, 90, 380, 900, 60, {"id": "word-cascade", "duration": .6}, leave, **kicker)
    b.text("Każde słowo\nwchodzi\nw rytm.", 4.3, 3.7, 60, 480, 960, 560, {"id": "word-highlight", "duration": 2.4}, {"id": "rise-out", "duration": .35},
           fontSize=120, align="center", shadow="soft")
    b.text("+ GLITCH  + SCRAMBLE", 5.9, 2.1, 90, 1160, 900, 90, {"id": "scramble-in", "duration": 1.0}, leave,
           fontFamily="JetBrains Mono", fontSize=50, fontWeight=700, color=MINT, align="center", shadow="glow", shadowColor="#2fd39a")

    b.text("Zrób to\nw FrameCore.", 8.3, 3.7, 60, 520, 960, 420, {"id": "word-cascade", "duration": 1.1, "easing": "back-out"}, None,
           fontSize=116, align="center", gradient=WARM, shadow="lift")
    b.text("$ framecore.py editor", 9.4, 2.6, 90, 1010, 900, 80, {"id": "type-on", "duration": 1.0, "easing": "linear"}, None,
           fontFamily="JetBrains Mono", fontSize=48, fontWeight=500, color=MINT, align="center")
    b.text("FRAMECORE", 0, 12, 90, 150, 900, 70, {"id": "logo-settle", "duration": .8}, None, fontSize=40, letterSpacing=6, align="center")
    b("set_canvas_fx", fx={"grade": "vivid", "vignette": .3, "grain": .1, "letterbox": 0, "transition": "flash", "transitionDuration": .35,
                           "motionBlur": True})
    scenes_by_start = {round(sc["start"], 3): sc["id"] for sc in b.state["project"]["scenes"]}
    b("set_scene_transition", scene_id=scenes_by_start[4], transition_id="whip-pan", duration=.55)
    b("set_scene_transition", scene_id=scenes_by_start[8], transition_id="cinematic-zoom", duration=.7)
    b.soundtrack("framecore-motion2-reel.wav", 12, 4)
    b("set_playhead", time=1.8)
    return b.state


SHOWCASES = {"showreel": (create_showreel, "framecore-motion2-showreel"), "reel": (create_reel, "framecore-motion2-reel")}


def export(store, state, target, poll=2.0):
    """Export the current revision with the regular render job and copy the MP4 to target."""
    import time
    api = API(store, RenderJobs(store))
    p = state["project"]
    job = api.call("export", {"project_id": p["id"], "expected_revision": p["revision"]})
    while job["status"] not in {"failed", "complete"}:
        time.sleep(poll)
        job = api.call("get_job", {"job_id": job["id"]})
    if job["status"] != "complete":
        raise RuntimeError(job.get("error"))
    shutil.copy2(store.directory(p["id"]) / "exports" / job["id"] / "framecore.mp4", target)
    return job
