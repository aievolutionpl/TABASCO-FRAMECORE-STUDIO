"""Wiedza dla agenta: co musi spełniać scena, jak pisać deterministyczny GSAP, jak wygląda pętla pracy.

To są teksty operacyjne (po angielsku, bo czyta je model), serwowane przez `knowledge_get` i osadzane w skillu. Zasady GSAP
pochodzą z praktyki: każda z nich wyłapała prawdziwy błąd przy budowie szablonów (nadzorca zgłasza je kodami).
"""
from __future__ import annotations

from . import common
from .common import StudioError

CONTRACT = """\
# Page contract (html engine)

A film is one HTML page whose picture is a pure function of time. The renderer steps the page frame by frame and screenshots it.

Required on `window`:
- `DURATION` (number): film length in seconds.
- `seek(t)`: draw the frame for time `t` (seconds), deterministically. Must work for any t in [0, DURATION], in any order.
- `__ready` (Promise): resolves when fonts and images are ready (`document.fonts.ready.then(fit)` is enough).
- `__CAPTURE__` (boolean, set by the renderer BEFORE page scripts run): when true, do not start any autoplay loop; only `seek` moves the picture.

Strongly recommended:
- `EV = [{t, type}]` sound events (types: whoosh, hit/impact, pop, click, chime, tick, reveal, type). Sound is generated from these.
- `TEXTS(t) = [{id, text, x0, y0, x1, y1}]` every visible text with its pixel box at time t, so reading time, framing, contrast and
  safe zones can be checked. Read the same source as the drawing code; if you forget a text here the check will say OK for text that is not drawn.

Rules: no Math.random, no timers, no CSS transitions/animations, no state carried between frames. One continuous motion beats cuts.
Layout is relative to the viewport or a fixed stage scaled to fit, so one file exports to 16:9, 9:16 and 1:1.
"""

GSAP = """\
# Deterministic GSAP recipe

Load GSAP from https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js (call `vendor_add` with `gsap` once so preview,
checks and render also work offline). Skeleton:

```js
var DUR = 7, CAPTURE = !!window.__CAPTURE__;
gsap.config({ force3D: false });                       // 2D transforms: no compositor layer promotion, frames do not depend on history
var tl = gsap.timeline({ repeat: -1, paused: CAPTURE });
tl.set('#a', { opacity: 0, x: 0 }, 0);                 // EVERY start state set at time 0 of the timeline: loops reset cleanly
tl.to('#a', { opacity: 1, duration: 0.6 }, 0.5);
tl.set({}, {}, DUR);                                   // timeline lasts exactly DUR
if (CAPTURE) { tl.totalTime(DUR - 0.001, false); tl.totalTime(0, false); }   // warm-up: initialise every tween in order
window.DURATION = DUR;
window.seek = function (t) { tl.pause(); tl.totalTime(((t % DUR) + DUR) % DUR, false); };
```

Pitfalls (each one produces a finding):
1. Never let two tweens of the SAME property on the SAME element overlap in time. The earlier one keeps writing after the later one
   ends, so the final value depends on seek order (NONDETERMINISTIC). Use `tl.set` at a computed time instead.
2. No `yoyo`/`repeat` inside tweens, no `onUpdate`/`.call()` for state, no timers, no Math.random. Write a fixed sequence of explicit tweens.
3. `from()`/`fromTo()` render their start values immediately; build "hidden until later" states with `tl.set(..., 0)` then `.to()`.
4. Centre with flexbox or explicit left/top, never `transform: translate(-50%)` (GSAP owns transform). Animate size and border-radius in px, not %.
5. Toggle visibility with `autoAlpha` through `tl.set`; make TEXTS read the DOM (Range rect + opacity + visibility) so it never lies.
6. To sync one motion to another, pass a function as `ease` computed from the other motion's progress (see examples/motion-graphics/03).
7. Holds over 1 s need a slow push-in or drift (DEAD_TIME), and a looping film must end where it starts (NOT_LOOPING) unless a hard reset is intended.
8. 3D: put `perspective` on the PARENT, rotate a child with `rotationY`; fake thickness with a stack of planes at different translateZ.
"""

WORKFLOW = """\
# Work loop (follow it; the supervisor is your eyes)

1. `studio_status` first. If the studio is not onboarded, ask the user for brand, palette, font, tone and default format, then `profile_set`.
2. `task_next` returns what the user asked for in the dashboard. `task_update` -> in_progress.
3. Choose a start: `templates_list` then `project_create` (from a template, or blank). Read the brief; `knowledge_get topic=brand|motion|visual|gsap|contract`.
4. Edit the scene: `scene_read`, then `scene_write` / `scene_patch` with `check: "quick"`.
5. LOOK at the film: `frames_view` with times at the opening, the main beat, the fastest transition and the end. Judge hierarchy, spacing, cut-off text, stray shapes.
6. `check_run` (standard). Fix errors first, then warnings, then re-run; read `delta` to see what you resolved and what is new. Repeat until `verdict: pass`.
   If a warning is intentional (e.g. a prompt demands a static hold), say so in `task_update` notes and keep it.
7. `render_start` (draft) then `job_wait`; `gate_set` approve stills/brief/visual_rules when genuinely done; `render_start` final; `deliver_start`.
8. `task_update` -> done with a short note: what was made, which warnings remain and why.

Never report success without a `pass` verdict or an explicit note. After 6 rounds without progress, stop and ask the user. Never overwrite a scene without `scene_write` (it keeps history; `scene_restore` undoes).
"""


def findings_text() -> str:
    from .supervisor import REMEDIES

    rows = ["# Finding codes and how to fix them", ""]
    for code, (title, fix) in REMEDIES.items():
        rows.append(f"- **{code}** ({title}): {fix}")
    return "\n".join(rows) + "\n"


def _template(name: str) -> str:
    f = common.STUDIO / "templates" / name
    return f.read_text(encoding="utf-8") if f.exists() else ""


def brand_text() -> str:
    from . import workspace

    p = workspace.profile_get()
    if not p.get("onboarded"):
        return "# Brand profile\n\nNot set up yet. Ask the user (name, palette, font, tone, audience, default format) and call `profile_set`.\n"
    pal = p["palette"]
    return (f"# Brand profile: {p['name']}\n\n- Palette: background {pal['bg']}, ink {pal['ink']}, accent {pal['accent']}, accent 2 {pal['accent2']}\n"
            f"- Font: {p['font']}\n- Tone: {p['tone']}\n- Audience: {p['audience']}\n- Default format: {p['default_format']} at {p['fps']} fps\n\n"
            "Use these values; do not invent colours or fonts.\n")


TOPICS = {
    "contract": ("Page contract: hooks the scene must expose", lambda: CONTRACT),
    "gsap": ("Deterministic GSAP recipe and pitfalls", lambda: GSAP),
    "workflow": ("The work loop with the supervisor", lambda: WORKFLOW),
    "findings": ("Finding codes and fixes", findings_text),
    "motion": ("Motion rules (numeric)", lambda: _template("MOTION_RULES.md")),
    "visual": ("Visual rules (palette, type, composition)", lambda: _template("VISUAL_RULES.md")),
    "brand": ("The user's brand profile", brand_text),
}


def get(topic: str) -> dict:
    if topic not in TOPICS:
        raise StudioError(f"nieznany temat '{topic}'. Dostępne: {', '.join(TOPICS)}")
    text = TOPICS[topic][1]()
    return {"topic": topic, "title": TOPICS[topic][0], "text": text or "(pusto)"}
