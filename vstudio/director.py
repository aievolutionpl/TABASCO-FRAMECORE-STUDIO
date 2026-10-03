"""Reżyser: plan stylu i storyboardu, przegląd filmu oczami widza i bramka „zatwierdzone przed wysyłką do użytkownika”.

Trzy kroki pracy (agent i dashboard używają tych samych funkcji):

  1. `plan`     dobiera styl główny i dwa akcenty, układa bity co 2-3 s (hak, rozwinięcie, dowód, CTA), do każdego przypisuje
                styl, układ, przejście, dźwięk i hasła do assetów. Wynik: director/plan.json (+ opcjonalnie STORYBOARD.md).
  2. `review`   mierzy film: czy co kilka sekund jest nowa sytuacja wizualna, czy otwarcie ma hak, czy film nie wygląda tak samo
                od początku do końca, czy ruch ma przyspieszenia, czy każdy tekst NAPRAWDĘ jest widoczny i narysowany wybranym
                fontem (w tym polskie znaki), czy obrazy się załadowały i czy nie ma migotania. Zwraca werdykt, znaleziska i obrazy.
  3. `signoff`  świadome zatwierdzenie (albo odrzucenie) przez agenta-recenzenta lub człowieka po obejrzeniu klatek; powiązane
                z wersją sceny (hash), więc każda zmiana unieważnia zatwierdzenie. Finalny render i wydanie wymagają zatwierdzenia.

Przegląd mierzy to, co da się zmierzyć; oceny subiektywnej (czy jest PIĘKNIE) nie udaje: dlatego sign-off wymaga checklisty,
którą recenzent potwierdza po obejrzeniu taśmy klatek i wykresu rytmu.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from . import brands, common, dscan, pages, styles, supervisor
from .common import StudioError

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PENALTY = {"error": 30, "warn": 8, "info": 1}

PACE_GAP = {"fast": 2.5, "standard": 3.5, "calm": 5.0}               # maks. sekund bez nowej sytuacji wizualnej
PLATFORM_PACE = {"reels": "fast", "tiktok": "fast", "shorts": "fast", "story": "fast", "feed": "standard", "linkedin": "standard",
                 "web": "calm", "presentation": "calm"}
PLATFORMS = list(PLATFORM_PACE)
#: step: żądany odstęp próbek (s); budget*: ile sekund wolno poświęcić na daną fazę (ciężka strona dostaje rzadsze próbkowanie, nie timeout)
DEPTHS = {"quick": {"step": 0.2, "motion_fps": 15, "ink": 12, "budget": 15, "motion_budget": 8, "ink_budget": 6},
          "standard": {"step": 0.1, "motion_fps": 30, "ink": 40, "budget": 45, "motion_budget": 25, "ink_budget": 15},
          "deep": {"step": 0.05, "motion_fps": 60, "ink": 60, "budget": 120, "motion_budget": 60, "ink_budget": 30}}
MAX_SAMPLES = 220
MAX_MOTION_FRAMES = 640
MIN_MOTION_FPS = 12

#: kod -> (tytuł dla człowieka, wskazówka naprawy dla agenta)
REMEDIES: dict[str, tuple[str, str]] = {
    "SLOW_PACE": ("Za długo bez zmiany wizualnej",
                  "Nothing visibly new happens for too long. Add a beat inside the gap: swap the layout, change the background treatment, bring in a new element with a different transition (knowledge_get topic=styles lists them). Aim for a visible change every 2-3 s on social; a calm hold is fine only when the brief asks for it (then accept the warning with a reason)."),
    "MONOTONE_STYLE": ("Film wygląda tak samo od początku do końca",
                       "The whole film shares one look. Keep brand colours and font, but change the TREATMENT between beats: layout, background (dark / light / gradient), motion language, transition. Run director_plan to pick a main style plus two accents with different layouts."),
    "WEAK_HOOK": ("Słaby początek (hak)",
                  "Nothing grabs attention in the first 1.5 s. Open with motion or a bold line in frame 1, put the key promise on screen by 1 s, and save the logo or product reveal for the end."),
    "NO_HOOK_TEXT": ("Brak tekstu w pierwszej sekundzie",
                     "Most viewers watch muted: state the point in words (max 6) by 1 s, or open on a striking visual that carries it on its own."),
    "FLASH_RISK": ("Migotanie kadru",
                   "The frame flashes light and dark more than 3 times per second, which can harm photosensitive viewers and reads as a glitch. Reduce to at most 2 flashes per second and lower the contrast of each flash."),
    "LINEAR_MOTION": ("Ruch bez przyspieszeń",
                      "Most moves run at constant speed, which looks mechanical. Use eases: expo.out or power3.out for entrances, power2.inOut for moves, back.out(1.4) for pops. Keep ease none for long drifts only."),
    "NO_STAGGER": ("Elementy pojawiają się naraz",
                   "Several elements enter on the same frame. Offset them by 0.05-0.1 s (stagger) so the eye can follow the order."),
    "TEXT_CLIPPED": ("Tekst przycięty",
                     "The text is cut off by a container (overflow hidden) or by the frame. Enlarge the container, reduce the font size or shorten the copy. Check long Polish words."),
    "TEXT_TRUNCATED": ("Tekst skrócony wielokropkiem", "text-overflow: ellipsis is cutting the copy. Remove it, shorten the text or widen the box."),
    "TEXT_HIDDEN": ("Tekst nie jest widoczny na ekranie",
                    "The DOM says the text is shown, but the pixels do not change when it is hidden: it is covered by another element, has the same colour as its background, or is clipped away. Raise its z-index, change its colour or remove the cover."),
    "TEXT_OVERLAP": ("Teksty nakładają się",
                     "Two different texts overlap. Move them apart, stagger their timing so one leaves before the other lands, or reduce their size."),
    "TEXT_WALL": ("Za dużo tekstu naraz",
                  "More than about 28 words are on screen at once. Social video is read in under 2 s per beat: keep to 6 words per beat or split the beat in two."),
    "TEXTS_INCOMPLETE": ("TEXTS(t) pomija widoczne napisy",
                         "Some visible texts are not reported by window.TEXTS(t), so reading time, framing and contrast are not checked for them. Make TEXTS read the DOM (every visible text node with its Range rect and opacity)."),
    "GLYPH_MISSING": ("Brak glifów w foncie",
                      "Some characters are not drawn by the chosen font (they fall back to another font or show as boxes). For Polish load the font with the latin-ext subset or pick a font that covers ąćęłńóśźż, then run director_review again."),
    "FONT_FALLBACK": ("Font nie jest dostępny",
                      "The first font in the stack is not loaded, so the page falls back to another font and renders differently than designed (and differently on other machines). Bundle the font next to the scene with @font-face (src: url(assets/font.woff2)) or choose a system font stack."),
    "ASSET_BROKEN": ("Obraz się nie załadował",
                     "An <img> failed to load (wrong path, 404 or unsupported file). Add images with assets_add and use the returned snippet; files live in src/assets/ and are referenced as assets/<file>."),
    "NO_VISUAL_ASSETS": ("Brak ikon i obrazków",
                         "The film has no icons, illustrations or images. Add 3-6 icons or stickers where text carries the message (assets_search, then assets_add) to make beats more visual."),
    "BEAT_MISSING": ("Plan zakłada zmianę, której nie widać",
                     "The storyboard (director_plan) puts a new beat here, but nothing visibly changes in the film. Build the beat or update the plan."),
    "PLAN_STALE": ("Plan nie pasuje do filmu", "The saved plan has a different duration than the film. Run director_plan again."),
}

#: pozycje checklisty, które recenzent potwierdza w sign-off po obejrzeniu taśmy klatek
CHECKLIST: dict[str, str] = {
    "hook": "In the first second something grabs attention (motion, bold type or a striking image).",
    "text": "Every text is fully visible, readable at phone size and spelled correctly (Polish letters included).",
    "rhythm": "The picture visibly changes every 2-3 s; no beat feels like a still slide.",
    "style": "The look fits the brand and the goal, and styles are mixed on purpose, not by accident.",
    "motion": "Movement has weight: eased starts and stops, staggered entrances, nothing robotic.",
    "assets": "Icons and images (if any) are crisp, on-brand and help the message instead of decorating.",
}


def explain(code: str) -> dict | None:
    if code not in REMEDIES:
        return None
    title, fix = REMEDIES[code]
    return {"code": code, "title": title, "fix": fix}


def _finding(code: str, severity: str, detail: str, *, t: float | None = None, box: list | None = None, ident: str = "", **extra) -> dict:
    title, fix = REMEDIES[code]
    return {"code": code, "severity": severity, "title": title, "detail": detail, "t": None if t is None else round(float(t), 2),
            "box": [round(v) for v in box] if box else None, "fix": fix, "id": ident, **extra}


# ------------------------------------------------------------------ stan: pliki, hash sceny, sign-off

def _ddir(pdir: Path) -> Path:
    d = pdir / "director"
    d.mkdir(exist_ok=True)
    return d


def scene_hash(pdir: Path) -> str:
    """Odcisk całej sceny (src/ bez node_modules): zmiana czegokolwiek unieważnia przegląd i zatwierdzenie."""
    h = hashlib.sha256()
    src = pdir / "src"
    if not src.exists():
        return ""
    for f in sorted(p for p in src.rglob("*") if p.is_file() and "node_modules" not in p.parts):
        h.update(f.relative_to(src).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _read_json(f: Path):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except ValueError:
        return None


def latest(pdir: Path) -> dict | None:
    return _read_json(pdir / "director" / "latest.json")


def history(pdir: Path) -> list[dict]:
    out = []
    for f in sorted((pdir / "director").glob("review-*.json")) if (pdir / "director").exists() else []:
        r = _read_json(f)
        if r:
            out.append({"round": r["round"], "at": r["at"], "score": r["score"], "verdict": r["verdict"], "counts": r["counts"], "depth": r["depth"]})
    return out


def _next_round(pdir: Path) -> int:
    nums = [int(m.group(1)) for f in (pdir / "director").glob("review-*.json") if (m := re.match(r"review-(\d+)\.json", f.name))] if (pdir / "director").exists() else []
    return max(nums, default=0) + 1


def state(pdir: Path) -> dict:
    """Stan zatwierdzenia: none (brak przeglądu) | reviewed (przegląd bez zatwierdzenia) | approved | rejected | stale (scena zmieniona po decyzji)."""
    rev, so, cur = latest(pdir), _read_json(pdir / "director" / "signoff.json"), scene_hash(pdir)
    review_fresh = bool(rev and rev.get("scene_hash") == cur)
    if so and so.get("scene_hash") == cur:
        st = "approved" if so.get("approved") else "rejected"
    elif so:
        st = "stale"
    elif rev:
        st = "reviewed" if review_fresh else "stale"
    else:
        st = "none"
    return {"state": st, "review_fresh": review_fresh, "scene_hash": cur,
            "review": {k: rev[k] for k in ("round", "verdict", "score", "at", "counts")} if rev else None,
            "signoff": {k: so.get(k) for k in ("approved", "by", "at", "notes", "accepted")} if so else None}


def require(pdir: Path, action: str) -> None:
    """Bramka: akcja (finalny render, wydanie) wymaga zatwierdzenia aktualnej wersji sceny. Błąd mówi, co zrobić."""
    st = state(pdir)
    if st["state"] == "approved":
        return
    how = {"none": "Run director_review, look at the frames it returns, then director_signoff.",
           "reviewed": "The review is current: look at its frames and call director_signoff (approve: true) once the checklist holds.",
           "stale": "The scene changed after the last review/sign-off. Run director_review again, then director_signoff.",
           "rejected": "The last sign-off REJECTED this version. Fix what the notes say, run director_review, then director_signoff."}[st["state"]]
    raise StudioError(f"{action}: brak zatwierdzenia reżysera dla tej wersji sceny (stan: {st['state']}). {how} "
                      "(Pominięcie tylko na wyraźną prośbę użytkownika: skip_review.)")


def signoff(pdir: Path, approve: bool, notes: str, checklist: dict | None = None, accept: dict | None = None, by: str = "agent") -> dict:
    rev = latest(pdir)
    if not rev:
        raise StudioError("najpierw director_review: sign-off dotyczy konkretnego przeglądu")
    cur = scene_hash(pdir)
    if rev.get("scene_hash") != cur:
        raise StudioError("scena zmieniła się po ostatnim przeglądzie: uruchom director_review jeszcze raz")
    notes = (notes or "").strip()
    accept = {k: (v or "").strip() for k, v in (accept or {}).items()}
    checklist = {k: bool(v) for k, v in (checklist or {}).items()}
    if len(notes) < 12:
        raise StudioError("notes: opisz w 1-2 zdaniach, co zobaczyłeś na klatkach (min. 12 znaków)")
    if approve:
        errs = [f for f in rev["findings"] if f["severity"] == "error"]
        if errs:
            raise StudioError("nie można zatwierdzić z błędami: " + ", ".join(sorted({f["code"] for f in errs})) + ". Napraw i uruchom przegląd ponownie.")
        open_warns = sorted({f["code"] for f in rev["findings"] if f["severity"] == "warn" and f["code"] not in accept})
        if open_warns:
            raise StudioError("ostrzeżenia bez decyzji: " + ", ".join(open_warns) + ". Napraw je albo świadomie zaakceptuj z powodem (accept: {KOD: powód}).")
        bad = [c for c, why in accept.items() if len(why) < 6]
        if bad:
            raise StudioError("accept: podaj powód (min. 6 znaków) dla " + ", ".join(bad))
        missing = [k for k in CHECKLIST if not checklist.get(k)]
        if missing:
            raise StudioError("checklista musi być w całości potwierdzona; brakuje: " + ", ".join(missing) + ". Jeśli któraś pozycja nie jest spełniona, odrzuć wersję (approve: false).")
    rec = {"approved": bool(approve), "by": by, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "notes": notes, "checklist": checklist, "accepted": accept,
           "scene_hash": cur, "review_round": rev["round"], "verdict": rev["verdict"], "score": rev["score"]}
    from .locking import atomic_write

    atomic_write(_ddir(pdir) / "signoff.json", json.dumps(rec, indent=2, ensure_ascii=False))
    common.append_log(pdir, f"director sign-off: {'APPROVED' if approve else 'REJECTED'} by {by} (review round {rev['round']}, score {rev['score']})")
    return {**state(pdir), "record": rec}


# ------------------------------------------------------------------ plan

ROLE_LAYOUTS = {"hook": ["big-type", "number-counter", "product-hero", "full-bleed-caption"], "problem": ["big-type", "split-compare", "quote-card"],
                "setup": ["big-type", "full-bleed-caption", "icon-grid"], "reveal": ["product-hero", "device-mock", "big-type"],
                "proof": ["number-counter", "quote-card", "split-compare", "icon-grid"], "benefit": ["icon-grid", "list-reveal", "device-mock"],
                "detail": ["device-mock", "list-reveal", "icon-grid"], "cta": ["cta-card", "big-type"]}
ROLE_ICONS = {"demo": ["eye", "globe"], "card": ["star", "download"], "point": ["bulb", "check"], "item": ["target", "star"], "hook": ["bolt", "sparkle"], "problem": ["clock", "x"], "setup": ["user", "bulb"], "reveal": ["rocket", "sparkle"],
              "proof": ["star", "trend-up", "trophy"], "benefit": ["check", "heart", "shield"], "detail": ["sliders", "phone"], "cta": ["arrow-right", "link"]}
ROLE_COPY = {"hook": "Max 6 words: a promise, a question or a number. On screen by 1.0 s.",
             "problem": "One sentence naming the pain in the viewer's words.", "setup": "Set the scene in at most 8 words.",
             "reveal": "Name the product or idea. One line, plus the visual that shows it.", "proof": "One number, quote or before/after. No claims without a figure.",
             "benefit": "Up to 3 short lines (3 words each), one per icon.", "detail": "One feature in action; max 2 callouts.",
             "cta": "Brand + one action (max 5 words) + handle or URL. Holds still for at least 1.5 s."}
SEQUENCES = {1: ["reveal"], 2: ["setup", "reveal"], 3: ["setup", "reveal", "proof"], 4: ["setup", "reveal", "proof", "benefit"], 5: ["setup", "reveal", "proof", "benefit", "detail"]}


def platform_for(pr: dict) -> str:
    w, h = pr["size"]
    ratio = h / w
    return "reels" if ratio >= 1.6 else "feed" if ratio >= 0.9 else "web"


def plan_path(pdir: Path) -> Path:
    return pdir / "director" / "plan.json"


def load_plan(pdir: Path) -> dict | None:
    return _read_json(plan_path(pdir))


def _format_beats(fmt: dict, dur: float, items: int) -> list[dict]:
    """Bity formatu rolki z czasami: stałe (`fixed`) zachowują długość, reszta dzieli pozostały czas wg `share`; za krótki film skaluje stałe."""
    specs: list[dict] = []
    for b in fmt["beats"]:
        if b.get("repeat") == "items":
            for i in range(items):
                style, layout = b["cycle"][i % len(b["cycle"])]
                specs.append({**{k: v for k, v in b.items() if k not in ("cycle", "repeat")}, "style": style, "layout": layout,
                              "copy": b["copy"].replace("Item N", f"Item {i + 1}")})
        else:
            specs.append(dict(b))
    fixed = sum(b["fixed"] for b in specs if "fixed" in b)
    share_sum = sum(b["share"] for b in specs if "share" in b)
    n_flex = sum(1 for b in specs if "share" in b)
    scale = 1.0
    if dur - fixed < max(0.45 * dur, n_flex * 1.0):
        scale = min(1.0, dur * 0.55 / fixed)
    flex_total = dur - fixed * scale
    if flex_total < n_flex * 0.8:
        raise StudioError(f"ten format potrzebuje dłuższego filmu (jest {dur:g} s, minimum {max(1.8 * n_flex, 6):g} s): zwiększ duration albo zmniejsz items")
    t = 0.0
    for b in specs:
        length = b["fixed"] * scale if "fixed" in b else flex_total * b["share"] / share_sum
        b["t0"], b["t1"] = round(t, 2), round(t + length, 2)
        t += length
    specs[-1]["t1"] = round(dur, 2)
    return specs


def plan(pdir: Path, pr: dict, goal: str, tone: str = "", platform: str | None = None, pace: str | None = None, prefer: list[str] | None = None,
         avoid: list[str] | None = None, cta: str = "", loop: bool = False, write_storyboard: bool = False, format: str | None = None,  # noqa: A002
         items: int = 3, creative_profile: str | None = None, text_mode: str | None = None) -> dict:
    """Storyboard z bitami co 2-3 s: styl główny + dwa akcenty (różne układy), przejścia, dźwięk, hasła do assetów. Deterministycznie.

    Z `format` (tool-drop, talking-head, listicle) bity pochodzą ze sprawdzonego układu rolki zamiast z ogólnego szkieletu.
    Obsługuje profile kreatywne (premium_minimal, cinematic, social_fast, educational) oraz tryby tekstu (none, headline_only, full).
    """
    from . import workspace

    if not (goal or "").strip():
        raise StudioError("goal: opisz, o czym jest film i do czego ma służyć")
    if format is not None and format not in styles.FORMATS:
        raise StudioError(f"format: {', '.join(styles.FORMATS)}")
    if not 2 <= int(items) <= 7:
        raise StudioError("items: 2-7")

    c_profile = creative_profile or pr.get("creative_profile") or "social_fast"
    t_mode = text_mode or pr.get("text_mode") or "full"
    profile_cfg = brands.CREATIVE_PROFILES.get(c_profile, brands.CREATIVE_PROFILES["social_fast"])

    platform = platform or (styles.FORMATS[format]["platform"] if format else platform_for(pr))
    if platform not in PLATFORM_PACE:
        raise StudioError(f"platform: {', '.join(PLATFORMS)}")

    pace = pace or (profile_cfg["default_pace"] if c_profile in ("premium_minimal", "cinematic") else PLATFORM_PACE[platform])
    if pace not in PACE_GAP:
        raise StudioError(f"pace: {', '.join(PACE_GAP)}")

    prof = workspace.profile_get()
    tone_all = " ".join(x for x in (tone, prof.get("tone") if prof.get("onboarded") else "") if x)
    dur = float(pr["duration"])
    prof_brand = {"palette": prof["palette"], "font": prof["font"]} if prof.get("onboarded") else None
    kws = styles.tokens(goal)[:3]

    if c_profile == "premium_minimal":
        prefer = list(prefer or []) + [s for s in profile_cfg["preferred_styles"] if s not in (avoid or [])]
        avoid = list(avoid or []) + profile_cfg["avoid_styles"]

    if format:
        fmt = styles.FORMATS[format]
        specs = _format_beats(fmt, dur, int(items))
        order = [b["style"] for b in specs]
        main_id = max(dict.fromkeys(order), key=order.count)
        accent_ids = [i for i in dict.fromkeys(order) if i != main_id][:2]
        main, accents = styles.get(main_id), [styles.get(i) for i in accent_ids]
        rec = {"main": styles.summary(main), "main_why": [f"format {format}: {fmt['name']}"], "accents": [styles.summary(a) for a in accents],
               "accent_why": [f"{a['name']}: występuje w formacie {format}" for a in accents]}
        beats, used_tr = [], []
        for i, b in enumerate(specs):
            st = styles.get(b["style"])
            tr = None
            if i:
                tr = b.get("transition") or next((x for x in st["transitions"] if x not in used_tr[-2:]), st["transitions"][0])
                used_tr.append(tr)
            sound_fx = b.get("sound") or (styles.TRANSITIONS[tr]["sound"] if tr else "hit")
            if c_profile == "premium_minimal":
                sound_fx = "reveal" if sound_fx == "hit" else sound_fx
            icons_list = [] if c_profile == "premium_minimal" or profile_cfg.get("allowed_no_visual_assets") else b.get("icons", ROLE_ICONS.get(b["role"], []))
            copy_text = b["copy"]
            if t_mode == "none":
                copy_text = "Czysty kadr wizualny, brak napisów."
            elif t_mode == "headline_only":
                copy_text = "Zwięzły nagłówek (maks. 4 słowa), dużo światła."
            elif b["role"] == "cta" and cta:
                copy_text = f"{cta}. " + copy_text
            beats.append({"n": i + 1, "role": b["role"], "t0": b["t0"], "t1": b["t1"], "style": b["style"], "layout": b["layout"], "transition_in": tr,
                          "sound": sound_fx,
                          "motion": {"ease": st["motion"]["ease"], "duration": st["motion"]["duration"], "camera": st["motion"]["camera"]},
                          "copy": copy_text,
                          "icons": icons_list, "asset_queries": kws[:2] if (icons_list and b["role"] in ("hook", "demo", "card", "item")) else []})
        brand = prof_brand or {"palette": main["palette"], "font": main["type"]["stack"]}
    else:
        rec = styles.recommend(goal, tone_all, platform, pace, prefer, avoid)
        main, accents = styles.get(rec["main"]["id"]), [styles.get(a["id"]) for a in rec["accents"]]
        target = {"fast": 2.0, "standard": 2.8, "calm": 4.5}[pace]
        hook = min({"fast": 1.4, "standard": 1.8, "calm": 2.6}[pace], dur * 0.3)
        end = min({"fast": 2.2, "standard": 2.6, "calm": 3.4}[pace], dur * 0.3)
        mid_total = max(0.0, dur - hook - end)
        n_mid = max(0, round(mid_total / target)) if mid_total >= 0.8 * target else 0
        if mid_total > 0 and n_mid == 0:
            n_mid = 1
        roles = ["hook"] + (SEQUENCES.get(n_mid) or (SEQUENCES[5] + ["proof", "benefit", "detail"] * 4)[:n_mid]) + ["cta"]
        mid_len = mid_total / n_mid if n_mid else 0.0

        if c_profile == "premium_minimal":
            # W profilu premium_minimal jeden spójny styl dominuje w całym filmie, bez wymuszonego mieszania
            seq = [main] * len(roles)
        else:
            pool = [accents[0] if accents else main, accents[1] if len(accents) > 1 else main, main]
            seq = [main]
            for i in range(n_mid):
                pick = pool[i % len(pool)]
                if pick["id"] == seq[-1]["id"]:
                    pick = next((c for c in pool if c["id"] != seq[-1]["id"]), pick)
                seq.append(pick)
            last = main if seq[-1]["id"] != main["id"] else (accents[0] if accents else main)
            seq.append(last)

        brand = prof_brand or {"palette": main["palette"], "font": main["type"]["stack"]}
        beats, t, prev_layout, used_tr = [], 0.0, None, []
        for i, (role, st) in enumerate(zip(roles, seq)):
            length = hook if i == 0 else end if role == "cta" else mid_len
            layout = next((l for l in ROLE_LAYOUTS[role] if l in st["layouts"] and l != prev_layout), None) or next((l for l in st["layouts"] if l != prev_layout), st["layouts"][0])
            tr = None
            if i:
                tr = next((x for x in st["transitions"] if x not in used_tr[-2:]), st["transitions"][0])
                used_tr.append(tr)
            sound_fx = styles.TRANSITIONS[tr]["sound"] if tr else "hit"
            if c_profile == "premium_minimal":
                sound_fx = "reveal" if sound_fx == "hit" else sound_fx
            icons_list = [] if (c_profile == "premium_minimal" or profile_cfg.get("allowed_no_visual_assets")) else ROLE_ICONS.get(role, [])
            copy_text = ROLE_COPY[role]
            if t_mode == "none":
                copy_text = "Czysty kadr wizualny, brak napisów."
            elif t_mode == "headline_only":
                copy_text = "Krótki nagłówek (maks. 4 słowa), dużo przestrzeni i światła."
            elif role == "cta" and cta:
                copy_text = f"{cta} (max 5 words) + handle or URL. Holds still for at least 1.5 s."

            beats.append({"n": i + 1, "role": role, "t0": round(t, 2), "t1": round(t + length, 2), "style": st["id"], "layout": layout,
                          "transition_in": tr, "sound": sound_fx,
                          "motion": {"ease": st["motion"]["ease"], "duration": st["motion"]["duration"], "camera": st["motion"]["camera"]},
                          "copy": copy_text,
                          "icons": icons_list, "asset_queries": kws[:2] if (icons_list and role in ("hook", "reveal", "proof")) else []})
            prev_layout = layout
            t += length
        beats[-1]["t1"] = round(dur, 2)

    max_pace_gap = profile_cfg.get("max_pace_gap", PACE_GAP[pace])
    p = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "goal": goal.strip(), "tone": tone_all, "platform": platform, "pace": pace, "duration": dur, "loop": loop,
         "creative_profile": c_profile, "text_mode": t_mode,
         "creative_profile_rules": profile_cfg,
         "format": {"id": format, "name": styles.FORMATS[format]["name"]} if format else None,
         "warnings": [f"beat {b['n']} ({b['role']}) lasts {b['t1'] - b['t0']:.1f} s: add a visible change inside it (zoom, new card or layout)"
                      for b in beats if b["t1"] - b["t0"] > max_pace_gap + 1.0]
                     + [f"beat {b['n']} ({b['role']}) lasts only {b['t1'] - b['t0']:.1f} s: too short to read, lengthen the film or drop items"
                        for b in beats if b["t1"] - b["t0"] < 1.0],
         "styles": {"main": rec["main"], "main_why": rec["main_why"], "accents": rec["accents"], "accent_why": rec["accent_why"]},
         "brand": brand, "beats": beats,
         "contract": {"visible_change_every_s": max_pace_gap, "hook_by_s": 1.0, "max_words_per_beat": profile_cfg.get("max_words_per_beat", 6),
                      "styles_used": sorted({b["style"] for b in beats}),
                      "layouts_used": sorted({b["layout"] for b in beats}),
                      "rule": "Brand colours and font stay constant; layout, background treatment, motion language and transition change between beats."},
         "font_note": styles.font_note()}
    from .locking import atomic_write

    _ddir(pdir)
    atomic_write(plan_path(pdir), json.dumps(p, indent=2, ensure_ascii=False))
    if write_storyboard:
        p["storyboard_file"] = _write_storyboard(pdir, p)
    common.append_log(pdir, f"director plan: {rec['main']['id']} + {', '.join(a['id'] for a in rec['accents'])}, {len(beats)} beats")
    return p


def storyboard_md(p: dict) -> str:
    rows = [f"# Storyboard ({p['platform']}, {p['duration']:g} s, pace {p['pace']})", "", f"Goal: {p['goal']}", "",
            f"Main style: **{p['styles']['main']['name']}** ({p['styles']['main']['id']}). Accents: "
            + ", ".join(f"**{a['name']}** ({a['id']})" for a in p["styles"]["accents"]) + ".", "",
            f"Constant across beats: brand palette {', '.join(f'{k} {v}' for k, v in p['brand']['palette'].items())}; font {p['brand']['font']}.", "",
            "| # | Time | Role | Style | Layout | Transition in | Sound | Copy rule | Icons |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in p["beats"]:
        rows.append(f"| {b['n']} | {b['t0']:g}-{b['t1']:g} s | {b['role']} | {b['style']} | {b['layout']} | {b['transition_in'] or '-'} | {b['sound']} | {b['copy']} | {', '.join(b['icons'])} |")
    rows += ["", f"Rule: a visible change at least every {p['contract']['visible_change_every_s']} s; the key promise on screen by {p['contract']['hook_by_s']:g} s.", ""]
    return "\n".join(rows)


def _write_storyboard(pdir: Path, p: dict) -> str:
    f = pdir / "STORYBOARD.md"
    if f.exists() and f.read_text(encoding="utf-8").strip() and "<!-- director -->" not in f.read_text(encoding="utf-8"):
        (pdir / "STORYBOARD.previous.md").write_text(f.read_text(encoding="utf-8"), encoding="utf-8")     # nie gubimy cudzych notatek
    f.write_text("<!-- director -->\n" + storyboard_md(p), encoding="utf-8")
    return "STORYBOARD.md"


# ------------------------------------------------------------------ przegląd

def _same_text(api: str, dom: str) -> bool:
    """Czy napis zgłoszony w TEXTS(t) to ten sam co w DOM: krótkie (1 znak) tylko przez równość, dłuższe też przez zawieranie (częściowo wpisany tekst)."""
    if not api or not dom:
        return False
    return api == dom or (len(api) >= 2 and (api in dom or dom in api))


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def review(pdir: Path, pr: dict, platform: str | None = None, pace: str | None = None, depth: str = "standard", save: bool = True) -> dict:
    """Jedna runda przeglądu reżysera. Zwraca raport (zapisany w director/review-NNN.json)."""
    import numpy as np

    if depth not in DEPTHS:
        raise StudioError(f"depth: {', '.join(DEPTHS)}")
    if pr.get("engine") != "html":
        raise StudioError("reżyser działa dla silnika html (kontrakt strony window.seek)")
    page_path = pdir / "src" / "index.html"
    if not page_path.exists():
        raise StudioError(f"brak {page_path}")
    t_start = time.time()
    fps, (w, h) = float(pr["fps"]), tuple(pr["size"])
    platform = platform or platform_for(pr)
    if platform not in PLATFORM_PACE:
        raise StudioError(f"platform: {', '.join(PLATFORMS)}")
    pace = pace or PLATFORM_PACE[platform]
    if pace not in PACE_GAP:
        raise StudioError(f"pace: {', '.join(PACE_GAP)}")
    cfg = DEPTHS[depth]
    findings: list[dict] = []
    metrics: dict = {"depth": depth, "platform": platform, "pace": pace, "max_gap": PACE_GAP[pace], "size": [w, h], "fps": fps}
    rn = _next_round(pdir) if save else 0
    rdir = _ddir(pdir) / f"review-{rn:03d}" if save else None
    phase: dict[str, float] = {}
    clock = [time.time()]

    def lap(name: str) -> None:
        now = time.time()
        phase[name] = round(now - clock[0], 1)
        clock[0] = now

    with supervisor.session(page_path, (w, h)) as (page, ev):
        lap("load")
        hooks = ev["hooks"]
        seek, dur = hooks["seek"], hooks["duration"]
        if not seek or dur is None:
            raise StudioError("strona nie spełnia kontraktu (window.seek + window.DURATION): najpierw check_run i napraw znaleziska")
        if ev["errors"]:
            raise StudioError("strona zgłasza błędy JavaScript, więc przegląd nie ma sensu: " + ev["errors"][0][:200] + " (uruchom check_run)")
        # ---- 1. próbkowanie klatek i DOM (gęstość dobrana do kosztu klatki: ciężka strona dostaje rzadsze próbki, nie timeout)
        page.evaluate(dscan.INK_STYLE_JS)

        seek_ms: list[float] = []

        def grab(t: float) -> tuple:
            ts = time.time()
            supervisor._seek(page, seek, t)
            seek_ms.append(time.time() - ts)
            data = supervisor._jpg(page)
            th = dscan.thumb(supervisor._img(data))
            scan = page.evaluate(dscan.TEXT_SCAN_JS)
            try:
                api = page.evaluate("(t) => (typeof window.TEXTS === 'function' ? window.TEXTS(t) : null)", t)
            except Exception:  # noqa: BLE001 - błąd TEXTS zgłasza nadzorca (TEXTS_FAILED)
                api = None
            return data, th, scan, api

        t0 = time.time()
        grab(0.0)
        cost = max(time.time() - t0, 0.005)                      # pilot: pełny koszt jednej próbki
        want = int(dur / cfg["step"] + 1e-9)
        n = max(min(want, 12), min(want, int(cfg["budget"] / cost), MAX_SAMPLES))
        step = max(dur / n, cfg["step"] if n == want else 0.0)
        times = [round(i * step, 4) for i in range(int(dur / step + 1e-9))]
        last_t = round(dur - 1.0 / fps, 4)
        if last_t not in times:
            times.append(last_t)
        step = float(np.median(np.diff(times))) if len(times) > 1 else step
        metrics.update(samples=len(times), step=round(step, 3), duration=dur, thinned=n < want, sample_cost_ms=int(cost * 1000))
        frames, thumbs, lums, scans, texts_api, asset_scans = [], [], [], [], [], {}
        asset_every = max(1, len(times) // 8)
        for i, t in enumerate(times):
            data, th, scan, api = grab(t)
            frames.append(data)
            thumbs.append(th)
            lums.append(float(th.mean() / 255.0))
            scans.append(scan)
            texts_api.append(api)
            if i % asset_every == 0:
                asset_scans[t] = page.evaluate(dscan.ASSET_SCAN_JS)

        lap("sampling")
        # ---- 2. ruch elementów w pełnej liczbie klatek (bez zrzutów ekranu: sam DOM); pomijany, gdy strona jest za ciężka na gęste klatki
        rows_per_frame: list = []
        mstep = 1.0 / min(cfg["motion_fps"], fps)
        supervisor._seek(page, seek, round(dur * 0.5, 4))
        t0 = time.time()
        page.evaluate(dscan.MOTION_JS)
        mcost = sorted(seek_ms)[len(seek_ms) // 2] + (time.time() - t0)       # mediana koszt seek z próbkowania + koszt skryptu
        affordable = int(cfg["motion_budget"] / max(mcost, 0.002))
        if affordable >= dur * MIN_MOTION_FPS:
            mstep = max(mstep, dur / min(affordable, MAX_MOTION_FRAMES))
            mtimes = [i * mstep for i in range(int(dur / mstep + 1e-9))]
            m_start = time.time()
            for k, t in enumerate(mtimes):
                elapsed = time.time() - m_start
                if k >= 6 and elapsed / k * len(mtimes) > cfg["motion_budget"] * 1.3:    # prognoza przekracza budżet: przerywamy od razu
                    rows_per_frame = []
                    metrics["motion_skipped"] = f"strona jest za ciężka na gęste klatki ({int(elapsed / k * 1000)} ms/klatkę)"
                    break
                supervisor._seek(page, seek, round(t, 4))
                rows_per_frame.append(page.evaluate(dscan.MOTION_JS))
            if rows_per_frame:
                metrics["motion_fps"] = round(1.0 / mstep, 1)
        else:
            metrics["motion_skipped"] = f"strona jest za ciężka na gęste klatki ({int(mcost * 1000)} ms/klatkę)"
        lap("motion")
        # ---- 3. fonty: czy każdy znak jest rysowany wybranym fontem
        groups: dict[tuple, dict] = {}
        for sc in scans:
            for it in sc:
                if it["op"] < 0.3:
                    continue
                g = groups.setdefault((it["family"], it["weight"], it["style"], it["transform"]), {"chars": set(), "sample": it["text"]})
                txt = it["text"].upper() if it["transform"] == "uppercase" else it["text"].lower() if it["transform"] == "lowercase" else it["text"]
                g["chars"].update(c for c in txt if not c.isspace())
        glyph_results = []
        for (family, weight, style, transform), g in groups.items():
            chars = "".join(sorted(g["chars"]))[:240]
            try:
                r = page.evaluate(dscan.GLYPH_JS, {"family": family, "weight": weight, "style": style, "chars": chars})
            except Exception:  # noqa: BLE001 - brak canvasu itp.: pomijamy, to nie błąd filmu
                continue
            glyph_results.append({**r, "family": family, "sample": g["sample"]})

        lap("fonts")
        # ---- 4. pieces: agregacja napisów w czasie
        pieces: dict[str, dict] = {}
        for si, (t, sc) in enumerate(zip(times, scans)):
            for it in sc:
                p = pieces.setdefault(it["key"], {"key": it["key"], "text": it["text"], "samples": []})
                p["samples"].append((si, t, it))
        # ---- 5. weryfikacja „tuszu”: czy napis realnie zmienia piksele (nie jest zasłonięty ani w kolorze tła)
        ink: dict[str, float] = {}
        cands = sorted(pieces.values(), key=lambda p: -max((s[2]["x1"] - s[2]["x0"]) * (s[2]["y1"] - s[2]["y0"]) for s in p["samples"]))[:cfg["ink"]]
        ink_deadline = time.time() + cfg["ink_budget"]
        for p in cands:
            if time.time() > ink_deadline:
                metrics["ink_partial"] = True
                break
            good = [s for s in p["samples"] if s[2]["op"] >= 0.6 and s[2]["vis"] >= 0.6]
            if not good:
                continue
            si, t, it = max(good, key=lambda s: (s[2]["op"] * s[2]["vis"], -abs(s[1] - sum(x[1] for x in good) / len(good))))
            x0, y0 = max(0, int(it["x0"]) - 3), max(0, int(it["y0"]) - 3)
            x1, y1 = min(w, int(it["x1"]) + 3), min(h, int(it["y1"]) + 3)
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue
            supervisor._seek(page, seek, t)
            clip = {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
            a = supervisor._img(page.screenshot(type="png", clip=clip))
            if not page.evaluate(dscan.INK_HIDE_JS, p["key"]):
                continue
            b = supervisor._img(page.screenshot(type="png", clip=clip))
            page.evaluate(dscan.INK_SHOW_JS)
            ink[p["key"]] = dscan.chg(np.asarray(a), np.asarray(b), 24)
            p["ink_t"], p["ink_box"] = t, [it["x0"], it["y0"], it["x1"], it["y1"]]

        lap("ink")
    # ============================================================ analiza (bez przeglądarki)
    pl = load_plan(pdir)
    c_profile = pr.get("creative_profile") or (pl or {}).get("creative_profile") or "social_fast"
    t_mode = pr.get("text_mode") or (pl or {}).get("text_mode") or "full"
    profile_cfg = brands.CREATIVE_PROFILES.get(c_profile, brands.CREATIVE_PROFILES["social_fast"])

    # ---- rytm: nowe sytuacje wizualne i luki
    D = dscan.shift_series(thumbs, step)
    events = dscan.find_events(times, D)
    gap_limit = profile_cfg.get("max_pace_gap", PACE_GAP[pace])
    gaps = dscan.slow_gaps(events, dur, gap_limit)
    metrics.update(events=events, gaps=[list(g) for g in gaps], shift_series=[round(x, 3) for x in D], creative_profile=c_profile, text_mode=t_mode)
    for a, b in sorted(gaps, key=lambda g: g[0] - g[1])[:3]:
        findings.append(_finding("SLOW_PACE", "warn", f"od {a:.1f} do {b:.1f} s ({b - a:.1f} s) nic nowego nie dzieje się w kadrze (limit dla {c_profile}/{platform}: {gap_limit:g} s)", t=a))
    # ---- hak
    hook = dscan.hook_strength(thumbs, times)
    metrics["hook"] = round(hook, 3)
    if dur >= 3 and hook < dscan.HOOK_THR:
        if c_profile not in ("premium_minimal", "cinematic"):
            findings.append(_finding("WEAK_HOOK", "warn", f"w pierwszych 1,5 s zmienia się tylko {hook:.0%} kadru", t=0.0))
        else:
            metrics["subtle_hook_allowed"] = True
    early = [it for sc, t in zip(scans, times) if t <= 1.2 for it in sc if it["op"] >= 0.6]
    early_assets = any(a for t, a in asset_scans.items() if t <= 1.2)
    if dur >= 3 and not early and not early_assets:
        if t_mode != "none" and not profile_cfg.get("allow_empty_text"):
            findings.append(_finding("NO_HOOK_TEXT", "info", "do 1,2 s nie ma ani tekstu, ani obrazu", t=0.0))
    # ---- różnorodność looków
    labels, n_looks, _centers = dscan.look_clusters(thumbs, times)
    need = dscan.required_looks(dur)
    metrics.update(looks=n_looks, looks_required=need, look_labels=labels)
    if n_looks < need:
        if not profile_cfg.get("allowed_monotone"):
            findings.append(_finding("MONOTONE_STYLE", "warn", f"film ma {n_looks} look(i), a przy {dur:g} s powinien mieć co najmniej {need}: wygląda tak samo od początku do końca", t=0.0))
        else:
            metrics["monotone_style_justified"] = f"Profil {c_profile}: jednolity spójny motyw jest zamierzony."
    # ---- migotanie
    for a, b in dscan.flash_windows(lums, step)[:2]:
        findings.append(_finding("FLASH_RISK", "error", f"jasność kadru skacze w górę i w dół >= 6 razy w {a:.1f}-{b:.1f} s", t=a))
    # ---- ruch
    segs = dscan.motion_segments(rows_per_frame, 1.0 / mstep, (w * w + h * h) ** 0.5) if rows_per_frame else []
    eas = dscan.easing_summary(segs)
    staggers = dscan.stagger_groups(segs, window_frames=max(1, round(0.06 / mstep)))
    metrics["motion"] = {"segments": len(segs), **eas, "staggered_groups": len(staggers)}
    if eas["moves"] >= 4 and eas["share"] >= 0.5:
        findings.append(_finding("LINEAR_MOTION", "warn", f"{eas['linear']} z {eas['moves']} ruchów ma stałą prędkość (bez przyspieszeń)"))
    for g in staggers[:2]:
        findings.append(_finding("NO_STAGGER", "info", f"{g['count']} elementów pojawia się w tej samej chwili", t=g["t"]))
    # ---- teksty
    seen_texts = [(s[1], s[2]) for p in pieces.values() for s in p["samples"]]
    metrics["texts"] = len(pieces)
    for p in pieces.values():
        vis_s = [s for s in p["samples"] if s[2]["op"] >= 0.6]
        if not vis_s:
            continue
        best = max(vis_s, key=lambda s: s[2]["vis"])
        it = best[2]
        box = [it["x0"], it["y0"], it["x1"], it["y1"]]
        if it["vis"] < 0.92:
            findings.append(_finding("TEXT_CLIPPED", "error", f"„{p['text'][:36]}” jest przycięty: najlepiej widać {it['vis']:.0%}", t=best[1], box=box, ident=p["key"][-40:]))
        if any(s[2]["ellipsis"] for s in vis_s):
            findings.append(_finding("TEXT_TRUNCATED", "error", f"„{p['text'][:36]}” jest skrócony wielokropkiem", t=vis_s[0][1], box=box, ident=p["key"][-40:]))
        if p["key"] in ink and ink[p["key"]] < 0.01 and it["vis"] >= 0.6:
            findings.append(_finding("TEXT_HIDDEN", "error", f"„{p['text'][:36]}” jest „widoczny” w DOM, ale po jego ukryciu obraz się nie zmienia ({ink[p['key']]:.1%} pikseli)",
                                     t=p.get("ink_t", best[1]), box=p.get("ink_box", box), ident=p["key"][-40:]))
        # edukacyjny: kontrola czasu czytania
        if c_profile == "educational" and t_mode != "none":
            vis_dur = len(vis_s) * step
            min_read = len(p["text"].split()) * 0.35 + 1.2
            if vis_dur < min_read:
                findings.append(_finding("TEXT_CLIPPED", "warn", f"W trybie edukacyjnym tekst „{p['text'][:28]}” jest widoczny za krótko ({vis_dur:.1f} s, zalecane min. {min_read:.1f} s na przeczytanie)", t=best[1], box=box, ident=p["key"][-40:]))
    pair_hits: dict[tuple, list] = {}
    for si, (t, sc) in enumerate(zip(times, scans)):
        vis = [it for it in sc if it["op"] >= 0.6 and it["vis"] >= 0.6]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                if dscan.norm_text(a["text"]) == dscan.norm_text(b["text"]):
                    continue
                if dscan.overlap_fraction((a["x0"], a["y0"], a["x1"], a["y1"]), (b["x0"], b["y0"], b["x1"], b["y1"])) >= 0.25:
                    pair_hits.setdefault((a["key"], b["key"]), []).append((t, a, b))
    for (ka, kb), hits in list(pair_hits.items())[:40]:
        if len(hits) * step >= 0.3 and len([f for f in findings if f["code"] == "TEXT_OVERLAP"]) < 4:
            t, a, b = hits[0]
            findings.append(_finding("TEXT_OVERLAP", "warn", f"„{a['text'][:24]}” nakłada się na „{b['text'][:24]}” przez {len(hits) * step:.1f} s", t=t,
                                     box=[min(a["x0"], b["x0"]), min(a["y0"], b["y0"]), max(a["x1"], b["x1"]), max(a["y1"], b["y1"])], ident=(ka + kb)[-40:]))
    wall = max(((sum(_words(it["text"]) for it in sc if it["op"] >= 0.6 and it["vis"] >= 0.6), t) for sc, t in zip(scans, times)), default=(0, 0.0))
    metrics["max_words"] = wall[0]
    if wall[0] > (profile_cfg.get("max_words_per_beat", 6) * 4 if c_profile == "premium_minimal" else 28):
        findings.append(_finding("TEXT_WALL", "info", f"{wall[0]} słów naraz na ekranie (przy {wall[1]:.1f} s)", t=wall[1]))
    if hooks["texts"]:
        blind: list[str] = []
        for p in pieces.values():
            vs = [s for s in p["samples"] if s[2]["op"] >= 0.6 and s[2]["vis"] >= 0.6]
            if len(vs) * step < 0.4:
                continue
            nt = dscan.norm_text(p["text"])
            covered = 0
            for si, t, _it in vs:
                api = texts_api[si] or []
                if any(_same_text(dscan.norm_text(x.get("text", "")), nt) for x in api):
                    covered += 1
            if covered < len(vs) * 0.5:
                blind.append(p["text"][:24])
        if blind:
            findings.append(_finding("TEXTS_INCOMPLETE", "warn", f"TEXTS(t) nie zgłasza {len(blind)} widocznych napisów, np. „{blind[0]}”", ident=blind[0][:30]))
    # ---- fonty
    seen_fonts: set[str] = set()
    for r in glyph_results:
        if r["missing"]:
            ex = "".join(r["missing"][:8])
            findings.append(_finding("GLYPH_MISSING", "error", f"font „{r['first']}” nie ma znaków: {ex} (np. w „{r['sample'][:24]}”): są rysowane innym fontem", ident=r["first"][:30] + ex[:4]))
        if r["tofu"]:
            findings.append(_finding("GLYPH_MISSING", "error", f"znaki {''.join(r['tofu'][:8])} nie mają glifu w żadnym foncie (puste kwadraty)", ident="tofu" + "".join(r["tofu"][:4])))
        if not r["generic"] and not r["available"] and r["first"] not in seen_fonts:
            seen_fonts.add(r["first"])
            findings.append(_finding("FONT_FALLBACK", "info", f"font „{r['first']}” nie jest załadowany: strona używa zamiennika", ident=r["first"][:30]))
    # ---- assety
    all_assets = [a for lst in asset_scans.values() for a in lst]
    broken = sorted({a["src"] for a in all_assets if a["broken"]})
    for src in broken[:3]:
        findings.append(_finding("ASSET_BROKEN", "error", f"obraz się nie załadował: {src.rsplit('/', 1)[-1][:60]}", ident=src[-40:]))
    n_assets = len({(a["tag"], a["src"], round(a["w"]), round(a["h"])) for a in all_assets})
    metrics["assets_visible"] = n_assets
    if dur >= 5 and n_assets == 0:
        if not profile_cfg.get("allowed_no_visual_assets"):
            findings.append(_finding("NO_VISUAL_ASSETS", "info", "w całym filmie nie ma ikon, ilustracji ani obrazów"))
        else:
            metrics["no_assets_justification"] = f"Profil {c_profile}: brak ikon i ozdobników jest zamierzony."
    # ---- zgodność z planem
    if pl:
        if abs(float(pl["duration"]) - dur) > 0.5:
            findings.append(_finding("PLAN_STALE", "info", f"plan zakłada {pl['duration']:g} s, film trwa {dur:g} s"))
        else:
            hit = 0
            for b in pl["beats"][1:]:
                if any(abs(e - b["t0"]) <= 0.7 for e in events):
                    hit += 1
                else:
                    findings.append(_finding("BEAT_MISSING", "warn", f"bit {b['n']} ({b['role']}) ma zaczynać się przy {b['t0']:g} s, ale wtedy nic się wyraźnie nie zmienia", t=b["t0"]))
            metrics["plan_adherence"] = round(hit / max(1, len(pl["beats"]) - 1), 2)

    lap("analysis")
    metrics["phase_s"] = phase
    film = None
    if save:
        film = supervisor._evidence(rdir, times, frames, findings, dur)
        _chart(rdir / "rhythm.png", times, D, events, gaps, pl["beats"] if pl and abs(float(pl["duration"]) - dur) <= 0.5 else [], labels, thumbs, dur)
        film["rhythm"] = "rhythm.png"
    return _finish(pdir, pr, rn, depth, findings, metrics, film, t_start, save)


def _finish(pdir: Path, pr: dict, n: int, depth: str, findings: list[dict], metrics: dict, film: dict | None, t_start: float, save: bool) -> dict:
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["t"] if f["t"] is not None else -1))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    score = max(0, 100 - sum(PENALTY[f["severity"]] for f in findings))
    verdict = "blocked" if counts["error"] else "needs_fixes" if counts["warn"] else "pass"
    prev = latest(pdir)
    delta = None
    if prev:
        key = lambda f: f"{f['code']}|{f['id']}" if f["id"] else f"{f['code']}||{round((f['t'] or 0) * 2) / 2}"  # noqa: E731
        pk, ck = {key(f): f for f in prev["findings"]}, {key(f): f for f in findings}
        delta = {"resolved": [pk[k]["code"] for k in pk if k not in ck], "new": [ck[k]["code"] for k in ck if k not in pk],
                 "persisting": sum(1 for k in ck if k in pk), "score_change": score - prev["score"], "since_round": prev["round"]}
    actions, seen = [], set()
    for f in findings:
        if f["severity"] != "info" and f["code"] not in seen:
            seen.add(f["code"])
            actions.append(f"[{f['code']}] {f['fix']}")
    report = {"project": f"{pr['brand']}/{pr['slug']}", "round": n, "depth": depth, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "verdict": verdict, "score": score,
              "counts": counts, "findings": findings, "delta": delta, "next_actions": actions[:4], "scene_hash": scene_hash(pdir),
              "metrics": {**metrics, "elapsed_s": round(time.time() - t_start, 1)}, "assets": film, "checklist": CHECKLIST}
    if save:
        d = _ddir(pdir)
        text = json.dumps(report, indent=2, ensure_ascii=False)
        (d / f"review-{n:03d}.json").write_text(text, encoding="utf-8")
        (d / "latest.json").write_text(text, encoding="utf-8")
        common.append_log(pdir, f"director review {n} ({depth}): {verdict}, score {score}, {counts['error']} err / {counts['warn']} warn")
    return report


# ------------------------------------------------------------------ wykres rytmu

def _chart(path: Path, times: list[float], D: list[float], events: list[float], gaps: list, beats: list[dict], labels: list[int], thumbs: list, dur: float) -> None:
    """Wykres dla agenta i dla człowieka: jak bardzo zmienia się kadr (krzywa), nowe sytuacje (pionowe linie), luki (czerwone tło),
    bity z planu (przerywane) i pasek „looków” u dołu."""
    from PIL import Image, ImageDraw

    W, H, L, R, T, B = 1000, 300, 46, 16, 28, 56
    im = Image.new("RGB", (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    x = lambda t: L + (W - L - R) * (t / dur)  # noqa: E731
    top = max(0.3, max(D) * 1.15 if D else 0.3)
    y = lambda v: H - B - (H - B - T) * min(v / top, 1.0)  # noqa: E731
    for a, b in gaps:
        d.rectangle([x(a), T, x(b), H - B], fill=(253, 226, 226))
    thr_y = y(dscan.SHIFT_THR)
    d.line([L, thr_y, W - R, thr_y], fill=(190, 190, 200), width=1)
    d.text((6, thr_y - 6), "próg", fill=(130, 130, 140))
    for bt in beats:
        xx = x(bt["t0"])
        for yy in range(T, H - B, 8):
            d.line([xx, yy, xx, yy + 4], fill=(120, 120, 220), width=1)
    pts = [(x(t), y(v)) for t, v in zip(times, D)]
    if len(pts) > 1:
        d.polygon([(pts[0][0], H - B)] + pts + [(pts[-1][0], H - B)], fill=(214, 224, 255))
        d.line(pts, fill=(60, 90, 220), width=2)
    for e in events:
        d.line([x(e), T, x(e), H - B], fill=(20, 150, 90), width=2)
    d.line([L, H - B, W - R, H - B], fill=(120, 120, 130), width=1)
    for s in range(int(dur) + 1):
        d.line([x(s), H - B, x(s), H - B + 4], fill=(120, 120, 130))
        d.text((x(s) - 4, H - B + 6), str(s), fill=(90, 90, 100))
    # pasek looków: średni kolor plasterka 1 s
    n = max(1, int(dur + 0.999))
    for s in range(n):
        idx = [i for i, t in enumerate(times) if s <= t < s + 1] or [min(len(thumbs) - 1, s * len(thumbs) // n)]
        col = tuple(int(v) for v in thumbs[idx[0]].reshape(-1, 3).mean(axis=0))
        d.rectangle([x(s), H - 22, x(min(s + 1, dur)), H - 8], fill=col, outline=(200, 200, 205))
        if s < len(labels):
            d.text((x(s) + 3, H - 20), str(labels[s]), fill=(255, 255, 255) if sum(col) < 380 else (20, 20, 20))
    d.text((L, 6), f"Rytm: zmiana kadru (niebieska krzywa), nowe sytuacje (zielone), luki (czerwone), looki (pasek)", fill=(40, 40, 50))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
