"""Checks that need a live page: sound/cue events (window.EV) and reading-time of on-screen text (window.TEXTS).

Page contract shared with lemo-opuscar and scripts/html_to_video.py:
  window.seek(t) | window.render(t)   draw the frame at second t (deterministic)
  window.DURATION | window.DUR        film length in seconds
  window.READY | window.__ready       set/resolved once fonts and images are loaded
  window.EV = [{t, type, ...}]        sound and cue events (optional)
  window.TEXTS(t) = [{id, text, x0, y0, x1, y1}]   every on-screen text at t with its pixel box (optional)
"""
from __future__ import annotations

import contextlib
import json
import re
import sys
from pathlib import Path

from .common import SCRIPTS, die, log


def _h2v():
    sys.path.insert(0, str(SCRIPTS))
    import html_to_video  # type: ignore
    return html_to_video


@contextlib.contextmanager
def open_page(page_path: Path, size: tuple[int, int] = (1920, 1080), timeout: int = 60):
    from playwright.sync_api import sync_playwright

    h = _h2v()
    src = page_path.resolve()
    if not src.exists():
        die(f"not found: {src}")
    server, port = h.serve_directory(src.parent)
    try:
        with sync_playwright() as pw:
            browser = h.launch_browser(pw, None)
            ctx = browser.new_context(viewport={"width": size[0], "height": size[1]})
            page = ctx.new_page()
            page.set_default_timeout(timeout * 1000)
            page.on("pageerror", lambda e: log(f"[page error] {e}"))
            page.add_init_script("window.__CAPTURE__ = true;")
            page.goto(f"http://127.0.0.1:{port}/{src.name}?capture=1", wait_until="load")
            page.evaluate(h.READY_JS)
            if page.evaluate("'READY' in window && window.READY !== true"):
                page.wait_for_function("window.READY === true", polling=100, timeout=timeout * 1000)
            try:
                yield page
            finally:
                browser.close()
    finally:
        server.shutdown()


def events(page_path: Path, out: Path | None = None, size=(1920, 1080)) -> dict:
    with open_page(page_path, size) as page:
        data = page.evaluate("({dur: (typeof window.DURATION === 'number' ? window.DURATION : window.DUR) ?? null, "
                             "ev: window.EV ?? [], seek: ['seek','render','renderFrame','draw'].find(n => typeof window[n] === 'function') ?? null})")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def events_to_cues(ev: dict, sfx_map: dict | None = None, default_gain: float = -8.0) -> dict:
    """window.EV -> a cue sheet for audio.mix_cues. An event may carry its own `sfx` (name or file)."""
    sfx_map = {"click": "click", "tap": "click", "cut": "whoosh", "whoosh": "whoosh", "hit": "impact", "impact": "impact", "pop": "pop",
               "type": "typewriter", "tick": "tick", "chime": "chime", "reveal": "sparkle", **(sfx_map or {})}
    hits = []
    for e in ev.get("ev", []):
        name = e.get("sfx") or sfx_map.get(str(e.get("type", "")).lower())
        if not name:
            continue
        hit = {"t": float(e["t"]), "gain_db": float(e.get("gain_db", default_gain))}
        hit["file" if str(name).lower().endswith((".wav", ".mp3", ".m4a")) else "sfx"] = name
        hits.append(hit)
    return {"duration": float(ev.get("dur") or 0) or (max([h["t"] for h in hits], default=0) + 1.0), "hits": hits}


def readcheck(page_path: Path, step: float = 0.04, latin_cps: float = 15.0, cjk_cps: float = 4.5, pad: float = 1.5,
              min_seconds: float = 1.5, fps: float = 30.0, size=(1920, 1080)) -> dict:
    """Every on-screen text must stay unchanged for chars/cps + pad seconds, stay inside the frame, and hold still >= 8 frames before moving."""
    with open_page(page_path, size) as page:
        if not page.evaluate("typeof window.TEXTS === 'function'"):
            die("page has no window.TEXTS(t); add it to enable the reading-time check (see projects/video-studio/README.md)")
        dur = page.evaluate("(typeof window.DURATION === 'number' ? window.DURATION : window.DUR) ?? null")
        if not dur:
            die("page has no window.DURATION")
        seek = page.evaluate("['seek','render','renderFrame','draw'].find(n => typeof window[n] === 'function') ?? null")
        pieces: dict[str, dict] = {}
        done: list[dict] = []
        t = 0.0
        while t <= dur + 1e-9:
            if seek:
                page.evaluate(f"(t) => window.{seek}(t)", t)
            cur = {x["id"]: x for x in page.evaluate("(t) => window.TEXTS(t)", t)}
            for pid in list(pieces):
                if pid not in cur or cur[pid]["text"] != pieces[pid]["text"]:
                    done.append(pieces.pop(pid))
            for pid, x in cur.items():
                p = pieces.get(pid)
                box = (x["x0"], x["y0"], x["x1"], x["y1"])
                if not p:
                    pieces[pid] = {"id": pid, "text": x["text"], "t0": t, "t1": t, "boxes": [box]}
                else:
                    p["t1"] = t; p["boxes"].append(box)
            t += step
        done.extend(pieces.values())
    W, H = size
    failures, stats = [], []
    for p in done:
        text = p["text"]
        cjk = len(re.findall(r"[぀-ヿ㐀-鿿가-힯]", text))
        other = len(re.sub(r"\s", "", text)) - cjk
        need = max(cjk / cjk_cps + other / latin_cps + pad, min_seconds)
        shown = p["t1"] - p["t0"] + step
        row = {"id": p["id"], "text": text[:60], "from": round(p["t0"], 2), "shown_s": round(shown, 2), "needs_s": round(need, 2)}
        stats.append(row)
        if shown + 1e-6 < need:
            failures.append(f"'{text[:40]}' ({p['id']}) is on screen {shown:.2f}s from t={p['t0']:.2f}s; needs {need:.2f}s to be read")
        b = p["boxes"]
        if any(x0 < -1 or y0 < -1 or x1 > W + 1 or y1 > H + 1 for x0, y0, x1, y1 in b):
            failures.append(f"'{text[:40]}' ({p['id']}) leaves the frame (box outside {W}x{H})")
        # hold-still rule: after the text settles it must stay put >= 8 frames before it moves again
        cs = [((x0 + x1) / 2, (y0 + y1) / 2) for x0, y0, x1, y1 in b]
        settle = next((i for i in range(len(cs) - 2) if all(abs(cs[i + k + 1][0] - cs[i + k][0]) + abs(cs[i + k + 1][1] - cs[i + k][1]) < 0.6 for k in range(2))), None)
        if settle is not None:
            base = cs[settle]
            mv = next((i for i in range(settle, len(cs)) if abs(cs[i][0] - base[0]) + abs(cs[i][1] - base[1]) > 3.0), None)
            if mv is not None:
                hold_frames = (mv - settle) * step * fps
                if hold_frames < 8 and mv < len(cs) - 1:
                    failures.append(f"'{text[:40]}' ({p['id']}) moves again {hold_frames:.0f} frames after settling (needs at least 8) at t={p['t0'] + mv * step:.2f}s")
    return {"pieces": stats, "failures": failures, "ok": not failures}
