"""Nadzorca jakości: po każdej zmianie sceny patrzy na film tak, jak zrobiłby to wymagający montażysta, i mówi agentowi, co poprawić.

Jedna runda (`check`) ładuje stronę w Chromium w rozmiarze projektu, próbkuje klatki i zwraca raport z kodami błędów,
czasem i miejscem w kadrze, wskazówką naprawy oraz różnicą względem poprzedniej rundy (co naprawiono, co nowe, co wciąż
wisi). Agent działa w pętli: edytuj scenę -> `check` -> popraw -> `check`, aż werdykt to `pass`.

Kontrole: błędy JS i sieci (w tym zablokowany CDN), kontrakt strony, puste klatki, martwy czas, twarde cięcia, domknięcie
pętli, determinizm (klatka nie zależy od kolejności seek), czas czytania tekstów, tekst poza kadrem, kontrast, rozmiar tekstu
i bezpieczne marginesy platform.
"""
from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import common, pages, vendor
from .common import StudioError

RASTER_ARGS = ["--disable-gpu-rasterization", "--disable-partial-raster"]   # bez tego Chromium daje szum rastra po skoku wstecz
BIG, BIG_FRACTION = 32, 2e-4            # klatki „takie same”: udział pikseli różniących się o > BIG (0-255) nie większy niż BIG_FRACTION
SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}
PENALTY = {"error": 30, "warn": 8, "info": 1}
DEPTH_STEP = {"quick": 0.25, "standard": 0.1, "deep": None}         # None = co klatkę projektu
MAX_SAMPLES = 240                      # ~25 s: głęboki nadzór ma mieścić się w limitach czasu klientów MCP

#: kod -> (tytuł dla człowieka, wskazówka naprawy dla agenta). Źródło dla raportów, skilla i docs/CAPABILITIES.md.
REMEDIES: dict[str, tuple[str, str]] = {
    "PAGE_ERROR": ("Błąd JavaScript na stronie",
                   "Read the error text, fix the script error in src/index.html (undefined variable, typo, missing library), then re-run check. Nothing else is trustworthy until the page loads clean."),
    "NET_FAILED": ("Nie załadował się zasób z sieci",
                   "An external resource (usually a CDN script such as GSAP) did not load. Call vendor_add for that URL (or pass a local file) so preview, checks and render work offline; the HTML itself stays unchanged."),
    "NET_HTTP": ("Zasób zwrócił błąd HTTP", "Fix the URL or vendor the resource with vendor_add."),
    "CONSOLE_WARN": ("Ostrzeżenie w konsoli strony", "Read the warning; in GSAP it often means an unsupported property or a missing plugin. Remove or replace it."),
    "NO_SEEK": ("Strona nie wystawia window.seek(t)", "Add window.seek = function (t) {...} that draws the frame for time t deterministically (for GSAP: tl.pause(); tl.totalTime(t % DUR)). See knowledge_get topic=contract."),
    "NO_DURATION": ("Brak window.DURATION", "Set window.DURATION to the film length in seconds."),
    "DURATION_MISMATCH": ("DURATION różni się od projektu", "Make window.DURATION equal to the project duration (or update the project) so the render is not cut or padded."),
    "NO_TEXTS": ("Brak window.TEXTS(t)", "Expose window.TEXTS(t) returning every visible text with its pixel box so readability can be checked (see knowledge_get topic=contract)."),
    "NO_EV": ("Brak window.EV", "Expose window.EV = [{t, type}] (whoosh, hit, pop, click, chime) so sound can be generated from the scene."),
    "BLANK_FRAMES": ("Puste klatki", "A stretch of the film shows a flat, empty frame. Start something moving earlier, or shorten the gap. Short gaps at the very start or end of a loop are fine."),
    "DEAD_TIME": ("Martwy czas: obraz stoi", "Nothing changes for too long. Add a slow push-in (about 0.25% per frame), a drift, or bring the next beat forward. Static holds over 1 s read as a frozen video."),
    "NOT_LOOPING": ("Pętla nie jest szczelna", "The last frame differs from the first, so a looping player will jump. Ease the end state back to the start state, or fade everything out at the end. Ignore if a hard reset is intended."),
    "NONDETERMINISTIC": ("Klatka zależy od historii", "The same time renders differently depending on what was drawn before. Remove Math.random, timers, CSS transitions, yoyo/repeat in tweens and overlapping tweens of one property; build state only from t."),
    "HARD_CUT": ("Twarde cięcie", "The picture changes abruptly between two samples. If this is meant to be a cut, fine; if the brief says one continuous motion, morph the object instead (size, radius, colour)."),
    "TEXT_READ": ("Tekst za krótko na ekranie", "Keep the text on screen at least characters/15 + 1.5 s, or shorten it. Do not animate text while it is being read."),
    "OFF_FRAME": ("Tekst wychodzi poza kadr", "Move or scale the element so its box stays inside the frame."),
    "TEXT_MOVES": ("Tekst rusza się zbyt szybko po wylądowaniu", "Let the text stand still for at least 8 frames after it lands before it moves again."),
    "LOW_CONTRAST": ("Niski kontrast tekstu", "Raise contrast to at least 3:1 for large text (4.5:1 for small): darken the background behind the text or change the text colour."),
    "TEXT_TINY": ("Tekst zbyt mały", "Increase the font size; on a phone, text under about 2.5% of the frame height is hard to read."),
    "SAFE_ZONE": ("Tekst w strefie interfejsu platformy", "Keep text out of the top 10% and bottom 20% of vertical video (Reels/Shorts/TikTok UI covers them) and 5% from the edges."),
    "TEXTS_FAILED": ("window.TEXTS rzuca wyjątek", "Fix the error thrown by window.TEXTS(t) (usually a selector that no longer exists or a read of an element before it is created). Reading time, framing and contrast cannot be checked until it works for every t."),
    "SEEK_FAILED": ("window.seek rzuca wyjątek", "Fix the error thrown by seek(t); the film cannot be sampled or rendered until it works for every t in [0, DURATION]."),
    "ENGINE_UNSUPPORTED": ("Silnik bez głębokich kontroli", "Deep checks need the html engine (window.seek contract). Use still/render for this engine."),
}


def _new_finding(code: str, severity: str, detail: str, *, t: float | None = None, box: list | None = None, ident: str = "", **extra) -> dict:
    title, fix = REMEDIES[code]
    return {"code": code, "severity": severity, "title": title, "detail": detail, "t": None if t is None else round(float(t), 2),
            "box": [round(v) for v in box] if box else None, "fix": fix, "id": ident, **extra}


# ------------------------------------------------------------------ przeglądarka

@contextmanager
def session(page_path: Path, size: tuple[int, int], timeout: int = 45):
    """Strona w Chromium z podsłuchem błędów: (page, events). events: errors, console, failed, http, hooks."""
    from playwright.sync_api import sync_playwright

    h = pages._h2v()
    src = page_path.resolve()
    if not src.exists():
        raise StudioError(f"brak strony: {src}")
    server, port = h.serve_directory(src.parent)
    ev: dict = {"errors": [], "console": [], "failed": [], "http": []}
    try:
        with sync_playwright() as pw:
            try:
                browser = h.launch_browser(pw, None, RASTER_ARGS)
            except SystemExit as exc:
                raise StudioError(f"nie znaleziono Chromium ({exc}). Uruchom: python -m playwright install chromium") from exc
            try:
                ctx = browser.new_context(viewport={"width": size[0], "height": size[1]})
                vendor.install_routes(ctx)
                page = ctx.new_page()
                page.set_default_timeout(timeout * 1000)
                page.on("pageerror", lambda e: ev["errors"].append(str(e)))
                page.on("console", lambda m: ev["console"].append((m.type, m.text)) if m.type in ("error", "warning") else None)
                page.on("requestfailed", lambda r: ev["failed"].append((r.url, str(r.failure or ""))))
                page.on("response", lambda r: ev["http"].append((r.url, r.status)) if r.status >= 400 else None)
                page.add_init_script("window.__CAPTURE__ = true;")
                page.goto(f"http://127.0.0.1:{port}/{src.name}?capture=1", wait_until="load")
                try:
                    page.evaluate(h.READY_JS)
                except Exception as exc:  # noqa: BLE001 - __ready odrzucone / biblioteka się nie załadowała
                    ev["errors"].append(f"__ready: {exc}")
                ev["hooks"] = page.evaluate("""() => ({
                    seek: ['seek','render','renderFrame','draw'].find(n => typeof window[n] === 'function') || null,
                    duration: typeof window.DURATION === 'number' ? window.DURATION : (typeof window.DUR === 'number' ? window.DUR : null),
                    texts: typeof window.TEXTS === 'function', ev: Array.isArray(window.EV) ? window.EV.length : null })""")
                yield page, ev
            finally:
                browser.close()
    finally:
        server.shutdown()


def _seek(page, name: str, t: float) -> None:
    page.evaluate(f"(t) => window.{name}(t)", t)


def _png(page) -> bytes:
    return page.screenshot(type="png")


def _jpg(page) -> bytes:
    return page.screenshot(type="jpeg", quality=88)


def _img(data: bytes):
    import io
    from PIL import Image

    return Image.open(io.BytesIO(data)).convert("RGB")


def _gray(im, width: int = 192):
    import numpy as np

    g = im.convert("L")
    return np.asarray(g.resize((width, max(1, round(width * im.height / im.width)))), dtype=np.float32)


def _same(a, b) -> bool:
    import numpy as np

    d = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    return float((d > BIG).mean()) <= BIG_FRACTION


def _lum(rgb):
    import numpy as np

    c = np.asarray(rgb, dtype=np.float32) / 255.0
    lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


# ------------------------------------------------------------------ raport

def _rounds_dir(pdir: Path) -> Path:
    return pdir / "supervisor"


def _next_round(pdir: Path) -> int:
    nums = [int(m.group(1)) for f in _rounds_dir(pdir).glob("round-*.json") if (m := re.match(r"round-(\d+)\.json", f.name))] if _rounds_dir(pdir).exists() else []
    return max(nums, default=0) + 1


def _key(f: dict) -> str:
    """Tożsamość znaleziska między rundami: dotyczące konkretnego tekstu po (kod, id), pozostałe po (kod, czas ~0.5 s)."""
    return f"{f['code']}|{f['id']}" if f["id"] else f"{f['code']}||{round((f['t'] or 0) * 2) / 2}"


def latest(pdir: Path) -> dict | None:
    f = _rounds_dir(pdir) / "latest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def history(pdir: Path) -> list[dict]:
    out = []
    for f in sorted(_rounds_dir(pdir).glob("round-*.json")) if _rounds_dir(pdir).exists() else []:
        r = json.loads(f.read_text(encoding="utf-8"))
        out.append({"round": r["round"], "at": r["at"], "score": r["score"], "verdict": r["verdict"], "counts": r["counts"], "depth": r["depth"]})
    return out


_RUNNING: set[str] = set()
_RLOCK = threading.Lock()


def is_running(pdir: Path) -> bool:
    """Czy dla projektu trwa właśnie runda nadzoru (automat w tle nie uruchamia drugiej)."""
    with _RLOCK:
        return str(pdir) in _RUNNING


def check(pdir: Path, pr: dict, depth: str = "standard", save: bool = True) -> dict:
    """Jedna runda nadzoru. Zwraca raport (też zapisany w supervisor/round-NNN.json)."""
    key = str(pdir)
    with _RLOCK:
        _RUNNING.add(key)
    try:
        return _check(pdir, pr, depth, save)
    finally:
        with _RLOCK:
            _RUNNING.discard(key)


def _check(pdir: Path, pr: dict, depth: str, save: bool) -> dict:
    if depth not in DEPTH_STEP:
        raise StudioError(f"depth musi być jednym z {list(DEPTH_STEP)}")
    t_start = time.time()
    fps, (w, h) = float(pr["fps"]), tuple(pr["size"])
    findings: list[dict] = []
    metrics: dict = {"depth": depth, "size": [w, h], "fps": fps}
    page_path = pdir / "src" / "index.html"
    rdir = _rounds_dir(pdir)
    n = _next_round(pdir) if save else 0
    round_assets = rdir / f"round-{n:03d}"

    if pr.get("engine") != "html" or not page_path.exists():
        findings.append(_new_finding("ENGINE_UNSUPPORTED", "info", f"silnik '{pr.get('engine')}' / brak src/index.html"))
        return _finish(pdir, pr, n, depth, findings, metrics, None, t_start, save)

    import numpy as np

    with session(page_path, (w, h)) as (page, ev):
        hooks = ev["hooks"]
        metrics["hooks"] = hooks
        # ---- błędy strony i sieci
        for e in ev["errors"]:
            findings.append(_new_finding("PAGE_ERROR", "error", e[:300]))
        for url, why in ev["failed"]:
            findings.append(_new_finding("NET_FAILED", "error", f"{url}  ({why})", ident=url[-40:]))
        for url, status in ev["http"]:
            findings.append(_new_finding("NET_HTTP", "warn", f"{url} -> HTTP {status}", ident=url[-40:]))
        for kind, text in ev["console"]:
            if kind == "warning" or "Failed to load resource" not in text:
                findings.append(_new_finding("CONSOLE_WARN", "warn" if kind == "warning" else "error", f"{kind}: {text[:240]}", ident=text[:30]))
        # ---- kontrakt
        seek = hooks["seek"]
        dur = hooks["duration"]
        if not seek:
            findings.append(_new_finding("NO_SEEK", "error", "brak seek/render/renderFrame/draw na window"))
        if dur is None:
            findings.append(_new_finding("NO_DURATION", "error", "window.DURATION nie jest liczbą"))
        elif abs(dur - float(pr["duration"])) > 0.05:
            findings.append(_new_finding("DURATION_MISMATCH", "warn", f"strona: {dur} s, projekt: {pr['duration']} s"))
        if not hooks["texts"]:
            findings.append(_new_finding("NO_TEXTS", "info", "czytelność tekstów nie jest sprawdzana"))
        if not hooks["ev"]:
            findings.append(_new_finding("NO_EV", "info", "brak zdarzeń dźwiękowych"))
        if not seek or dur is None:
            return _finish(pdir, pr, n, depth, findings, metrics, None, t_start, save, round_assets)

        # ---- próbkowanie klatek
        step = DEPTH_STEP[depth] or (1.0 / fps)
        times = [round(i * step, 4) for i in range(int(dur / step + 1e-9))]
        if len(times) > MAX_SAMPLES:
            times = [times[round(i * (len(times) - 1) / (MAX_SAMPLES - 1))] for i in range(MAX_SAMPLES)]
        last_t = round(dur - 1.0 / fps, 4)
        if last_t not in times:
            times.append(last_t)
        step = float(np.median(np.diff(times))) if len(times) > 1 else step     # faktyczny odstęp po ewentualnym przerzedzeniu próbek
        metrics.update(samples=len(times), step=round(step, 4), duration=dur, thinned=len(times) < int(dur / (DEPTH_STEP[depth] or 1.0 / fps)))
        frames_jpg: list[bytes] = []
        grays = []
        texts_at: list[list[dict]] = []
        texts_broken = False
        for t in times:
            try:
                _seek(page, seek, t)
                data = _jpg(page)
            except Exception as exc:  # noqa: BLE001
                findings.append(_new_finding("SEEK_FAILED", "error", f"t={t}: {str(exc)[:240]}", t=t))
                return _finish(pdir, pr, n, depth, findings, metrics, None, t_start, save, round_assets)
            frames_jpg.append(data)
            grays.append(_gray(_img(data)))
            try:
                texts_at.append(page.evaluate("(t) => (typeof window.TEXTS === 'function' ? window.TEXTS(t) : [])", t) or [])
            except Exception as exc:  # noqa: BLE001 - błąd w TEXTS to inna usterka niż w seek: osobny kod i osobna wskazówka
                texts_at.append([])
                if not texts_broken:
                    texts_broken = True
                    findings.append(_new_finding("TEXTS_FAILED", "error", f"t={t}: {str(exc)[:240]}", t=t))

        # ---- puste klatki i martwy czas
        stds = [float(g.std()) for g in grays]
        diffs = [float(np.abs(grays[i] - grays[i - 1]).mean()) for i in range(1, len(grays))]
        p99 = [float(np.percentile(np.abs(grays[i] - grays[i - 1]), 99)) for i in range(1, len(grays))]

        def runs(flags: list[bool], offset: int = 0) -> list[tuple[int, int]]:
            out, start = [], None
            for i, f in enumerate(flags + [False]):
                if f and start is None:
                    start = i
                if not f and start is not None:
                    out.append((start + offset, i - 1 + offset))
                    start = None
            return out

        for a, b in runs([s < 1.2 for s in stds]):
            t0, t1 = times[a], times[b] + step
            if t1 - t0 >= 0.5:
                edge = t0 <= 0.05 or t1 >= dur - 0.05
                findings.append(_new_finding("BLANK_FRAMES", "info" if edge and t1 - t0 <= 1.3 else "warn",
                                             f"płaski kadr {t0:.2f}-{t1:.2f} s ({t1 - t0:.1f} s)" + (" na brzegu pętli" if edge else ""), t=t0))
        max_freeze = 1.0
        for a, b in runs([d < 0.03 and q < 6 for d, q in zip(diffs, p99)], offset=1):
            t0, t1 = times[a - 1], times[b]
            if t1 - t0 >= max_freeze and not all(s < 1.2 for s in stds[a - 1:b + 1]):
                findings.append(_new_finding("DEAD_TIME", "warn", f"obraz stoi {t0:.2f}-{t1:.2f} s ({t1 - t0:.1f} s)", t=t0))
        cut_thr = 30.0 if step <= 1 / 15 else 55.0
        cuts = [times[i] for i, d in enumerate(diffs, start=1) if d > cut_thr]
        if cuts:
            findings.append(_new_finding("HARD_CUT", "info", f"gwałtowna zmiana obrazu przy t = {', '.join(f'{c:.2f}' for c in cuts[:6])} s", t=cuts[0]))
        loop_diff = float(np.abs(grays[0] - grays[-1]).mean())
        metrics["loop_diff"] = round(loop_diff, 2)
        if loop_diff > 2.0:
            findings.append(_new_finding("NOT_LOOPING", "info", f"pierwsza i ostatnia klatka różnią się o {loop_diff:.1f}/255", t=dur))

        # ---- determinizm: 6 klatek rosnąco vs malejąco, w PNG
        det_times = [round(dur * f, 3) for f in (0.13, 0.31, 0.47, 0.62, 0.79, 0.93)]
        ref = {}
        for t in det_times:
            _seek(page, seek, t)
            ref[t] = _img(_png(page))
        bad = []
        for t in reversed(det_times):
            _seek(page, seek, t)
            if not _same(_img(_png(page)), ref[t]):
                bad.append(t)
        if bad:
            findings.append(_new_finding("NONDETERMINISTIC", "error", f"klatka zależy od historii seek przy t = {', '.join(f'{b:.2f}' for b in sorted(bad))} s", t=min(bad)))
        metrics["deterministic"] = not bad

        # ---- teksty: kontrast, rozmiar, marginesy
        pieces: dict[tuple, dict] = {}
        for i, (t, items) in enumerate(zip(times, texts_at)):
            for it in items:
                k = (it["id"], it["text"])
                p = pieces.setdefault(k, {"id": it["id"], "text": it["text"], "idx": []})
                p["idx"].append((i, it))
        safe_bottom = 0.20 if h / w >= 1.6 else 0.04
        safe_top = 0.10 if h / w >= 1.6 else 0.04
        for p in pieces.values():
            mid_i, mid = p["idx"][len(p["idx"]) // 2]
            box = [mid["x0"], mid["y0"], mid["x1"], mid["y1"]]
            t_mid = times[mid_i]
            bh = box[3] - box[1]
            if bh < 0.025 * h:
                findings.append(_new_finding("TEXT_TINY", "warn", f"„{p['text'][:30]}” ma wysokość {bh:.0f}px = {bh / h:.1%} kadru", t=t_mid, box=box, ident=str(p["id"])))
            worst = None
            for _i, it in p["idx"]:
                x0, y0, x1, y1 = it["x0"], it["y0"], it["x1"], it["y1"]
                if x0 < 0.04 * w or x1 > 0.96 * w or y0 < safe_top * h or y1 > (1 - safe_bottom) * h:
                    worst = worst or (times[_i], [x0, y0, x1, y1])
            if worst:
                findings.append(_new_finding("SAFE_ZONE", "warn", f"„{p['text'][:30]}” wchodzi w strefę interfejsu/marginesu ({worst[0]:.2f} s)", t=worst[0], box=worst[1], ident=str(p["id"])))
            im = _img(frames_jpg[mid_i])
            x0, y0, x1, y1 = (max(0, int(box[0])), max(0, int(box[1])), min(w, int(box[2])), min(h, int(box[3])))
            if x1 - x0 >= 4 and y1 - y0 >= 4:
                lum = _lum(np.asarray(im.crop((x0, y0, x1, y1))))
                hi, lo = float(np.percentile(lum, 97)), float(np.percentile(lum, 3))
                ratio = (max(hi, lo) + 0.05) / (min(hi, lo) + 0.05)
                if ratio < 3.0:
                    findings.append(_new_finding("LOW_CONTRAST", "warn", f"„{p['text'][:30]}” ma kontrast {ratio:.1f}:1 (minimum 3:1)", t=t_mid, box=box, ident=str(p["id"]), ratio=round(ratio, 2)))
        metrics["texts"] = len(pieces)

    # ---- czas czytania (osobna sesja, krok 0.04 s: dokładniejszy niż nasze próbkowanie)
    if hooks["texts"] and not texts_broken:
        try:
            rc = pages.readcheck(page_path, fps=fps, size=(w, h))
        except Exception as exc:  # noqa: BLE001 - readcheck nie może przewrócić całej rundy
            findings.append(_new_finding("PAGE_ERROR", "warn", f"readcheck: {str(exc)[:200]}"))
            rc = {"failures": []}
        for f in rc["failures"]:
            m = re.search(r"\(([^)]+)\)", f)
            ident, tm = (m.group(1) if m else ""), re.search(r"t=([\d.]+)s", f)
            t = float(tm.group(1)) if tm else None
            code = "OFF_FRAME" if "leaves the frame" in f else "TEXT_MOVES" if "moves again" in f else "TEXT_READ"
            if code == "TEXT_READ" and t is not None and t >= dur - 0.05:
                continue            # próbka na granicy pętli (seek(DURATION) zawija do 0): to nie jest osobny napis
            findings.append(_new_finding(code, "error" if code == "OFF_FRAME" else "warn", f, t=t, ident=ident))
        metrics["readcheck_ok"] = rc.get("ok", None)

    # miniatury do raportu: filmstrip + dowody dla znalezisk
    film = _evidence(round_assets, times, frames_jpg, findings, dur) if save else None
    return _finish(pdir, pr, n, depth, findings, metrics, film, t_start, save, round_assets)


def _evidence(rdir: Path, times: list[float], frames: list[bytes], findings: list[dict], dur: float) -> dict:
    from PIL import ImageDraw

    rdir.mkdir(parents=True, exist_ok=True)
    count = min(12, len(times))
    idx = sorted({round(i * (len(times) - 1) / max(count - 1, 1)) for i in range(count)})
    paths, labels = [], []
    for i in idx:
        p = rdir / f"film_{i:04d}.jpg"
        im = _img(frames[i])
        im.thumbnail((360, 480))
        im.save(p, quality=82)
        paths.append(p)
        labels.append(f"{times[i]:.2f}s")
    sheet = common.image_sheet(paths, labels, rdir / "filmstrip.jpg", cols=min(6, len(paths)), tile_w=300)
    for p in paths:
        p.unlink(missing_ok=True)
    made = 0
    for f in findings:
        if f["t"] is None or made >= 8:
            continue
        i = min(range(len(times)), key=lambda k: abs(times[k] - f["t"]))
        im = _img(frames[i])
        if f["box"]:
            d = ImageDraw.Draw(im)
            x0, y0, x1, y1 = f["box"]
            d.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=(255, 64, 64), width=max(3, im.width // 360))
        im.thumbnail((720, 960))
        ev = rdir / f"ev_{made:02d}_{f['code']}.jpg"
        im.save(ev, quality=84)
        f["evidence"] = ev.name
        made += 1
    return {"filmstrip": sheet.name, "dir": rdir.name}


def _finish(pdir: Path, pr: dict, n: int, depth: str, findings: list[dict], metrics: dict, film: dict | None, t_start: float,
            save: bool, assets: Path | None = None) -> dict:
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["t"] if f["t"] is not None else -1))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    score = max(0, 100 - sum(PENALTY[f["severity"]] for f in findings))
    verdict = "blocked" if counts["error"] else "needs_fixes" if counts["warn"] else "pass"
    prev = latest(pdir)
    delta = None
    if prev:
        pk, ck = {_key(f): f for f in prev["findings"]}, {_key(f): f for f in findings}
        delta = {"resolved": [pk[k]["code"] + (f" ({pk[k]['t']}s)" if pk[k]["t"] is not None else "") for k in pk if k not in ck],
                 "new": [ck[k]["code"] + (f" ({ck[k]['t']}s)" if ck[k]["t"] is not None else "") for k in ck if k not in pk],
                 "persisting": sum(1 for k in ck if k in pk), "score_change": score - prev["score"], "since_round": prev["round"]}
    actions, seen = [], set()
    for f in findings:
        if f["severity"] != "info" and f["code"] not in seen:
            seen.add(f["code"])
            actions.append(f"[{f['code']}] {f['fix']}")
    report = {"project": f"{pr['brand']}/{pr['slug']}", "round": n, "depth": depth, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "verdict": verdict, "score": score, "counts": counts, "findings": findings, "delta": delta,
              "next_actions": actions[:4], "metrics": {**metrics, "elapsed_s": round(time.time() - t_start, 1)}, "assets": film}
    if save:
        rdir = _rounds_dir(pdir)
        rdir.mkdir(exist_ok=True)
        text = json.dumps(report, indent=2, ensure_ascii=False)
        (rdir / f"round-{n:03d}.json").write_text(text, encoding="utf-8")
        (rdir / "latest.json").write_text(text, encoding="utf-8")
        common.append_log(pdir, f"supervisor round {n} ({depth}): {verdict}, score {score}, {counts['error']} err / {counts['warn']} warn")
    return report


# ------------------------------------------------------------------ podgląd klatek dla agenta i UI

def capture_frames(pdir: Path, pr: dict, times: list[float], out_dir: Path, *, max_width: int = 720, label: bool = True) -> dict:
    """Klatki w zadanych chwilach (w jednej sesji: szybko) + arkusz kontaktowy z podpisami. Zwraca ścieżki."""
    if pr.get("engine") != "html":
        raise StudioError("podgląd klatek działa dla silnika html (inne silniki: vstudio still)")
    page_path = pdir / "src" / "index.html"
    if not page_path.exists():
        raise StudioError(f"brak {page_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    size = tuple(pr["size"])
    paths: list[Path] = []
    problems: list[str] = []
    with session(page_path, size) as (page, ev):
        seek = ev["hooks"]["seek"]
        if not seek:
            raise StudioError("strona nie wystawia window.seek(t): nie da się pobrać klatki (knowledge_get topic=contract)")
        problems = ev["errors"] + [f"{u} ({w})" for u, w in ev["failed"]]
        for t in times:
            _seek(page, seek, t)
            im = _img(_png(page))
            if im.width > max_width:
                im = im.resize((max_width, round(im.height * max_width / im.width)))
            p = out_dir / f"t_{t:07.3f}.jpg"
            im.save(p, quality=90)
            paths.append(p)
    sheet = None
    if len(paths) > 1:
        sheet = common.image_sheet(paths, [f"t={t:g}s" for t in times], out_dir / "sheet.jpg", cols=min(len(paths), 3), tile_w=max_width // 2 if len(paths) > 2 else max_width) if label else None
    return {"frames": [str(p) for p in paths], "sheet": str(sheet) if sheet else None, "page_problems": problems}


def timeline(pdir: Path, pr: dict, step: float = 0.1) -> dict:
    """Mapa czasu: zdarzenia dźwiękowe i kiedy jaki tekst jest widoczny (z boksem). Agent widzi, co gdzie się dzieje."""
    page_path = pdir / "src" / "index.html"
    if pr.get("engine") != "html" or not page_path.exists():
        raise StudioError("mapa czasu wymaga silnika html i src/index.html")
    with session(page_path, tuple(pr["size"])) as (page, ev):
        seek, dur = ev["hooks"]["seek"], ev["hooks"]["duration"]
        if not seek or dur is None:
            raise StudioError("strona nie spełnia kontraktu (window.seek + window.DURATION)")
        events = page.evaluate("() => (Array.isArray(window.EV) ? window.EV : [])")
        pieces: dict[tuple, dict] = {}
        t = 0.0
        while t <= dur + 1e-9:
            _seek(page, seek, min(t, dur - 1e-6))
            for it in (page.evaluate("(t) => (typeof window.TEXTS === 'function' ? window.TEXTS(t) : [])", t) or []):
                p = pieces.setdefault((it["id"], it["text"]), {"id": it["id"], "text": it["text"], "from": round(t, 2), "to": round(t, 2),
                                                                  "box": [round(it["x0"]), round(it["y0"]), round(it["x1"]), round(it["y1"])]})
                p["to"] = round(t, 2)
            t += step
    return {"duration": dur, "fps": pr["fps"], "size": pr["size"], "events": events, "texts": sorted(pieces.values(), key=lambda p: p["from"])}


def explain(code: str) -> dict:
    from . import director

    hit = director.explain(code)
    if hit:
        return hit
    if code not in REMEDIES:
        raise StudioError(f"nieznany kod '{code}'. Znane: {', '.join(sorted({*REMEDIES, *director.REMEDIES}))}")
    title, fix = REMEDIES[code]
    return {"code": code, "title": title, "fix": fix}

