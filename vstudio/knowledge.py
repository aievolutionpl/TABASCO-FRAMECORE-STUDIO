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
  Word-by-word captions that follow a voice add `caption: true` to their entry (`VS.captions.texts(t)` does it): they are only checked for staying inside
  the frame, not for reading time or holding still, because the viewer hears them. Never mark ordinary text as a caption.
- `window.__ALPHA__` (boolean, set by the renderer in overlay mode, see `render_start overlay`): true when the film is rendered as a transparent layer to be placed over
  the user's own footage. Hide full-bleed backdrops and the footage placeholder when it is set (or mark them `data-alpha="hide"`); keep cards, captions and effects.

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
# Work loop (follow it; the supervisor and the director are your eyes)

1. `studio_status` first. If the studio is not onboarded, ask the user for brand, palette, font, tone and default format, then `profile_set`.
2. `task_next` returns what the user asked for in the dashboard. `task_update` -> in_progress.
3. DIRECT before you build: `project_create` (from the closest template or blank), then `director_plan` (goal, platform, tone). It picks a main style plus two
   accents with different layouts and returns a beat sheet with a visible change every 2-3 s. Read `knowledge_get topic=direction`, and `style_get` for each style used.
4. Build beat by beat: `scene_read`, then `scene_write` / `scene_patch` with `check: "quick"`. Fetch icons and stickers with `assets_search` / `assets_add` /
   `assets_generate` instead of leaving beats text-only.
5. LOOK at the film: `frames_view` at the opening, each beat, the fastest transition and the end. Judge hierarchy, spacing, cut-off text, stray shapes.
6. `check_run` (standard): technical correctness. Fix errors first, then warnings, then re-run; read `delta`. Repeat until `verdict: pass`.
   If a warning is intentional (e.g. a prompt demands a static hold), say so in `task_update` notes and keep it.
7. `director_review`: pacing, hook, variety, motion, text rendering. LOOK at the filmstrip and the rhythm chart it returns. Fix findings, re-run.
   Best: hand this step to the `vstudio-director` agent (fresh eyes, no edit tools). When the checklist honestly holds: `director_signoff` (approve true, notes of what you saw,
   accept: {CODE: reason} for warnings kept on purpose). Any later edit to the scene invalidates the sign-off.
8. Only now `render_start` (draft, then final once brief, visual_rules and stills are approved) and `deliver_start`: final render and delivery refuse to start without the
   director's sign-off for the current scene. Tell the user the film is ready only after that.
9. `task_update` -> done with a short note: what was made, which styles, which warnings remain and why.

Never report success without `pass` from the supervisor, an approved director sign-off and a note about warnings kept on purpose. After 6 rounds without progress, stop and
ask the user. Never overwrite a scene without `scene_write` (it keeps history; `scene_restore` undoes).
"""

DIRECTION = """\
# The director's craft (read before building; director_review measures it)

A film that is technically correct can still be boring. You are the director: decide what the viewer sees every 2-3 seconds,
respecting the project's creative profile (premium_minimal, cinematic, social_fast, educational) and text mode (none, headline_only, full).

1. Hook, 0-1.5 s. Frame 1 is the thumbnail. In social reels, something moves or a bold line is on screen by 1 s. In text_mode="none",
   a captivating visual hero or opening move replaces hook copy.
2. Rhythm. A visibly NEW situation every 2-3 s on reels/tiktok/shorts (3.5 s on feed/linkedin, up to 7 s in premium_minimal / cinematic
   for intentional calm holds). "New" means layout, background, subject or camera changes, not just a word swap. Let the CTA hold still
   for 1.5-2.5 s.
3. Variety inside a system. Constant: palette, font, tone, logo position.
   - In social_fast: vary layout and style accents across beats (at least 2 looks in 7 s, 3 from 12 s).
   - In premium_minimal: a single dominant look and coherent world are intentional; forced multi-style hopping is avoided.
4. Motion with weight. Ease everything: expo.out or power3.out for entrances, power2.inOut for moves, back.out(1.4) for pops.
   Constant speed only for long drifts (LINEAR_MOTION). In premium_minimal, motion is subtle and deliberate, without bouncy cartoon physics.
5. Text. Dependent on text_mode:
   - "none": no on-screen text required; purely visual film.
   - "headline_only": bold titles only; no micro-copy or cluttered paragraphs.
   - "full": at most 6 words per beat and 2 sizes; key word in accent colour.
   In all text modes with copy: text must be fully visible, never clipped (TEXT_CLIPPED), never overlapping (TEXT_OVERLAP).
   Polish letters must come from the chosen font (GLYPH_MISSING). Reading time must satisfy chars/15 + 1.5 s (educational requires generous reading time).
6. Assets.
   - In social_fast: pair text beats with an icon, sticker or generated graphic.
   - In premium_minimal: NEVER add automatic icons or clutter; leave generous whitespace around the single hero focus.
7. Sound. Every intentional transition has a cue in EV: hit for cuts, whoosh for moves, pop for stickers, chime for success.
   In premium_minimal, avoid aggressive sound effects on gentle ambient cuts.
8. Restraint. If a beat has two ideas, split it. If an element does not help the message, remove it.

Review ritual: `director_review`, then LOOK at the filmstrip and the rhythm chart. Check each checklist item honestly.
"""

FEEL = """\
# Physical motion: how movement gets weight

Cheap motion is linear, instant or floaty. Physical motion starts fast, lands softly and has a little life in it. These rules are what `director_review` can measure
(LINEAR_MOTION, NO_STAGGER) plus the habits that make a film feel built rather than assembled. The motion kit (`motion_kit_add`) provides the curves.

1. Entrances ease OUT: fast start, long soft landing (`VS.ease.out` = cubic-bezier(.23, 1, .32, 1), or GSAP expo.out / power3.out). Exits are shorter than entrances (60-70%) and
   leave quickly; a thing that arrives slowly and leaves slowly feels heavy for no reason. Linear is for loops, progress bars and long drifts only.
2. One spring per beat, on the hero element (a card dropping in, a badge). `ease: VS.spring(170, 16)` (stiffness, damping) overshoots 2-6% and settles; use
   `duration: VS.springDuration(170, 16)` so the tween lasts exactly as long as the spring needs. Stiffer and tighter (300, 21) for small pops; softer (120, 14) for big cards.
   Critical damping (damping = 2 * sqrt(stiffness)) never overshoots: use it for things that must not bounce (text blocks, a window sliding in).
3. Scale from .8-.95, never from 0, and fade in together (opacity 0 to 1 within the first third). Pops end at 1, not at 1.05 held.
4. Stagger groups by .04-.09 s in reading order; six items should finish entering within about .5 s. All at once is NO_STAGGER; slower than .12 s feels like a slideshow.
5. Duration by size: state change .15-.25 s, text and icons .35-.6 s, cards and windows .6-.9 s. Nothing over 1 s except camera moves and drifts.
6. Distance by importance: details travel 12-40 px, cards 80-200 px. Everything in a beat travels in the same direction family (up and in), with one counter-move for contrast.
7. Settle, then hold: an element stays still for at least 8 frames (about .27 s at 30 fps) after it lands before anything else moves it. The hold-still check enforces it.
8. Under any hold over 1 s put a slow push-in (3-6% scale across the beat) or drift, so the picture is never dead (DEAD_TIME).
9. Overlap: start the next move while the previous one is in its last 20%; a film where everything waits for the previous thing to finish feels sequential, not directed.
10. Everything from time: `VS.count`, `VS.type`, `VS.blink` compute numbers, typing and cursor blink directly from t. No timers, no randomness, so seek order never matters.
"""

ASSETS = """\
# Assets: icons, generated graphics and downloaded images

- Where: files live in `src/assets/` and the scene references them as `assets/<file>`. Preview, supervisor and render all serve `src/` as the root. `ASSETS.json` records source,
  licence, author and hash of every file; delivery turns it into credits.
- Order of preference: (1) built-in icons (`assets_search source=builtin`, 64 line icons, English and Polish keywords), (2) generated graphics (`assets_generate`: blob, mesh,
  dots, grid, rings, waves, rays, confetti, grain, starburst, squiggle, arrow; deterministic from a seed, in brand colours), (3) Iconify icons and Openverse photos
  (`assets_search source=iconify|openverse`, needs internet; only permissive licences are returned), (4) a plain https URL (licence unknown: tell the user to check the rights).
- Inline SVG (`assets_snippet mode=inline`) inherits CSS `color`, so one icon can follow the palette and animate like any element. Use `<img>` for photos.
- Images must be decoded before frame 0: `window.__ready = Promise.all([document.fonts.ready, ...[...document.images].map(i => i.decode())])`. A broken image is ASSET_BROKEN.
- Downloads are safe by construction: https only, public hosts only, size and time limits, content sniffing, SVG sanitised (no scripts, no external references), rasters re-encoded.
- Use icons at 6-12% of the frame width, in groups of 3-6 with a stagger; never decorate for its own sake.
"""


def findings_text() -> str:
    from .director import REMEDIES as DIRECTOR
    from .supervisor import REMEDIES

    rows = ["# Finding codes and how to fix them", "", "## Supervisor (technical correctness)", ""]
    for code, (title, fix) in REMEDIES.items():
        rows.append(f"- **{code}** ({title}): {fix}")
    rows += ["", "## Director (what the viewer sees)", ""]
    for code, (title, fix) in DIRECTOR.items():
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


def _styles_text() -> str:
    from . import styles

    return styles.library_text()


def _formats_text() -> str:
    from . import styles

    return styles.formats_text()


def _creative_profiles_text() -> str:
    from . import brands

    lines = ["# Creative profiles and text modes", "", "## Profiles", ""]
    for pid, p in brands.CREATIVE_PROFILES.items():
        lines.append(f"### {p['name']} (`{pid}`)")
        lines.append(f"- **Description:** {p['description']}")
        lines.append(f"- **Default pace:** {p['default_pace']} (max allowable pace gap: {p['max_pace_gap']}s)")
        lines.append(f"- **Calm holds allowed:** {p['allow_calm_holds']}")
        lines.append(f"- **Suppress auto icons:** {p['suppress_auto_icons']}")
        lines.append(f"- **Preferred styles:** {', '.join(p['preferred_styles']) or 'none'}")
        lines.append(f"- **Avoid styles:** {', '.join(p['avoid_styles']) or 'none'}")
        lines.append("")
    lines.append("## Text Modes")
    lines.append("- `none`: Purely visual film without on-screen copy. Hook text warning is suppressed.")
    lines.append("- `headline_only`: Strong, concise titles. Avoid clutter, micro-text, or multi-sentence paragraphs.")
    lines.append("- `full`: Standard storytelling copy with headlines and supporting lines.")
    return "\n".join(lines) + "\n"


TOPICS = {
    "contract": ("Page contract: hooks the scene must expose", lambda: CONTRACT),
    "direction": ("The director's craft: hook, rhythm, variety, motion, text, assets", lambda: DIRECTION),
    "creative_profiles": ("Creative profiles (premium_minimal, cinematic, social_fast, educational) and text modes", _creative_profiles_text),
    "styles": ("Style library, transitions and beat layouts", _styles_text),
    "formats": ("Reel formats with proven beat sheets (tool-drop, talking-head, listicle) and caption rules", _formats_text),
    "assets": ("Icons, generated graphics and downloaded images", lambda: ASSETS),
    "gsap": ("Deterministic GSAP recipe and pitfalls", lambda: GSAP),
    "workflow": ("The work loop with the supervisor", lambda: WORKFLOW),
    "findings": ("Finding codes and fixes", findings_text),
    "feel": ("Physical motion: ease-out, springs, scale, stagger, settle (with the motion kit)", lambda: FEEL),
    "motion": ("Motion rules (numeric)", lambda: _template("MOTION_RULES.md")),
    "visual": ("Visual rules (palette, type, composition)", lambda: _template("VISUAL_RULES.md")),
    "brand": ("The user's brand profile", brand_text),
}


def get(topic: str) -> dict:
    if topic not in TOPICS:
        raise StudioError(f"nieznany temat '{topic}'. Dostępne: {', '.join(TOPICS)}")
    text = TOPICS[topic][1]()
    return {"topic": topic, "title": TOPICS[topic][0], "text": text or "(pusto)"}
