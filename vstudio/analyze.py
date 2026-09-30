"""Reference frame study: cuts, shots, per-shot motion, palette, audio hits, tempo, loudness -> SPEC.md + analysis.json.

Numbers come from pixels (frames downscaled to ~192 px wide), never from eyeballing. Keyframes are written
at full resolution so an agent can look at them next to the numbers.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .common import ffprobe, grab_frame, image_sheet, log, need, run


# ------------------------------------------------------------------ video pass

def _stream_frames(video: Path, width: int):
    info = ffprobe(video)
    w = width - width % 2
    h = round(info["height"] * w / info["width"])
    h -= h % 2
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", f"scale={w}:{h}:flags=area",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
    p.wait()


def _phase_shift(a: np.ndarray, b: np.ndarray, win: np.ndarray) -> tuple[float, float]:
    """Global translation of b relative to a (pixels), by phase correlation."""
    fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    corr = np.fft.ifft2(r).real
    iy, ix = np.unravel_index(np.argmax(corr), corr.shape)
    h, w = corr.shape
    dy = iy - h if iy > h // 2 else iy
    dx = ix - w if ix > w // 2 else ix
    return float(dx), float(dy)


def video_pass(video: Path, width: int = 192, hist_stride: int = 3) -> dict:
    mad, hdist, luma, frac, cx, cy, dxs, dys = ([] for _ in range(8))
    color_hists: dict[int, np.ndarray] = {}
    prev = prev_hist = win = None
    n = 0
    for fr in _stream_frames(video, width):
        g = (0.299 * fr[..., 0] + 0.587 * fr[..., 1] + 0.114 * fr[..., 2]).astype(np.float32)
        if win is None:
            win = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1])).astype(np.float32)
        hist = np.histogram(g, bins=64, range=(0, 255))[0].astype(np.float32)
        hist /= hist.sum()
        luma.append(float(g.mean()))
        if prev is None:
            mad.append(0.0); hdist.append(0.0); frac.append(0.0); cx.append(None); cy.append(None); dxs.append(0.0); dys.append(0.0)
        else:
            diff = np.abs(g - prev)
            mad.append(float(diff.mean()))
            hdist.append(float(0.5 * np.abs(hist - prev_hist).sum()))
            mask = diff > 12
            f = float(mask.mean())
            frac.append(f)
            if f > 0.0005:
                ys, xs = np.nonzero(mask)
                cx.append(float(xs.mean() / g.shape[1])); cy.append(float(ys.mean() / g.shape[0]))
            else:
                cx.append(None); cy.append(None)
            dx, dy = _phase_shift(prev, g, win)
            dxs.append(dx); dys.append(dy)
        if n % hist_stride == 0:
            code = ((fr[..., 0] >> 4).astype(np.uint16) << 8) | ((fr[..., 1] >> 4).astype(np.uint16) << 4) | (fr[..., 2] >> 4)
            color_hists[n] = np.bincount(code.ravel(), minlength=4096).astype(np.uint32)
        prev, prev_hist = g, hist
        n += 1
    return {"n": n, "mad": mad, "hdist": hdist, "luma": luma, "frac": frac, "cx": cx, "cy": cy,
            "dx": dxs, "dy": dys, "width": win.shape[1] if win is not None else width, "color_hists": color_hists}


# ------------------------------------------------------------------ cuts & shots

def detect_cuts(mad: list[float], hdist: list[float], sensitivity: float = 1.0) -> list[dict]:
    d, h = np.array(mad), np.array(hdist)
    n = len(d)
    cand = []
    for i in range(1, n):
        lo, hi = max(1, i - 10), min(n, i + 11)
        neigh = np.concatenate([d[lo:i], d[i + 1:hi]])
        med = max(float(np.median(neigh)) if len(neigh) else 0.0, 1.0)
        strong = (h[i] >= 0.30 / sensitivity and d[i] >= 10 / sensitivity) or d[i] >= 35 / sensitivity
        if strong and d[i] >= 3 * med:
            cand.append((i, float(d[i]), float(h[i]), min(1.0, float(d[i]) / (6 * med))))
    cuts = []  # non-maximum suppression within 3 frames
    for c in sorted(cand, key=lambda x: -x[1]):
        if all(abs(c[0] - k["frame"]) > 3 for k in cuts):
            cuts.append({"frame": c[0], "mad": round(c[1], 2), "hist_change": round(c[2], 3), "confidence": round(c[3], 2)})
    return sorted(cuts, key=lambda k: k["frame"])


def _runs(mask: np.ndarray, min_len: int = 1, gap: int = 0) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append([start, i - 1]); start = None
    if start is not None:
        runs.append([start, len(mask) - 1])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(a, b) for a, b in merged if b - a + 1 >= min_len]


def _palette(hists: dict[int, np.ndarray], lo: int, hi: int, k: int = 5) -> list[dict]:
    tot = np.zeros(4096, dtype=np.float64)
    for f, hh in hists.items():
        if lo <= f < hi:
            tot += hh
    if tot.sum() == 0:
        return []
    order = np.argsort(-tot)
    out: list[dict] = []
    for b in order[:200]:
        if tot[b] == 0:
            break
        rgb = np.array([(b >> 8 & 15) * 16 + 8, (b >> 4 & 15) * 16 + 8, (b & 15) * 16 + 8], dtype=float)  # bin centres (+-8)
        for o in out:
            if np.linalg.norm(o["_rgb"] - rgb) < 48:
                o["_w"] += tot[b]
                break
        else:
            out.append({"_rgb": rgb, "_w": tot[b]})
        if len(out) >= k * 3:
            break
    out.sort(key=lambda o: -o["_w"])
    s = tot.sum()
    return [{"hex": "#%02x%02x%02x" % tuple(int(v) for v in o["_rgb"]), "pct": round(100 * o["_w"] / s, 1)} for o in out[:k]]


def noise_floor(mad: list[float], cuts: list[dict]) -> float:
    """Frame-difference level of 'nothing is moving' (codec noise), so thresholds scale with the video."""
    skip = {c['frame'] for c in cuts}
    vals = [v for i, v in enumerate(mad) if i > 0 and i not in skip]
    return max(0.03, 1.5 * float(np.percentile(vals, 10))) if vals else 0.03


def shot_stats(vp: dict, start: int, end: int, fps: float, floor: float) -> dict:
    mad = np.array(vp["mad"][start:end]); mad[0] = 0.0 if start > 0 else mad[0]
    e = mad.copy()
    peak = float(e.max()) if len(e) else 0.0
    thr = max(0.2 * peak, 3 * floor)
    moves = []
    for a, b in _runs(e > thr, min_len=2, gap=1):
        seg = e[a:b + 1]
        pk = int(a + np.argmax(seg)); pe = float(e[pk])
        tail = e[pk:b + 6] if pk + 1 < len(e) else e[pk:]
        ratios = [tail[i + 1] / tail[i] for i in range(len(tail) - 1) if tail[i] > 0.03 * pe and tail[i + 1] <= tail[i] * 1.05]
        k = round(1 - float(np.median(np.clip(ratios, 0.05, 1.2))), 3) if len(ratios) >= 3 else None
        cxs = [vp["cx"][start + i] for i in range(a, b + 1) if vp["cx"][start + i] is not None]
        cys = [vp["cy"][start + i] for i in range(a, b + 1) if vp["cy"][start + i] is not None]
        travel = None
        if len(cxs) >= 2:
            travel = round(100 * float(np.hypot(cxs[-1] - cxs[0], cys[-1] - cys[0])), 1)
        moves.append({"start": start + a, "end": start + b, "frames": b - a + 1, "peak_frame": start + pk,
                      "peak_energy": round(pe, 2), "arrival_k": k, "travel_pct": travel})
    dead = [start + i for i in range(len(e) - 1) if e[i] >= 0.3 * peak and peak > 6 * floor and e[i + 1] < max(0.05 * e[i], 1.5 * floor)]
    dx = np.array(vp["dx"][start:end]); dy = np.array(vp["dy"][start:end])
    still = (e < 1.5 * floor) & (np.abs(dx) < 0.2) & (np.abs(dy) < 0.2)
    need_frames = max(int(round(0.4 * fps)), 6)
    frozen = [{"start": start + a, "frames": b - a + 1} for a, b in _runs(still, min_len=need_frames)]
    return {
        "start": start, "end": end - 1, "frames": end - start, "seconds": round((end - start) / fps, 3),
        "avg_energy": round(float(e.mean()), 2) if len(e) else 0.0, "peak_energy": round(peak, 2),
        "moves": moves, "dead_stops": dead, "frozen_runs": frozen,
        "camera_shift_pct": [round(100 * float(dx.sum()) / vp["width"], 2), round(100 * float(dy.sum()) / vp["width"], 2)],
        "mean_luma": round(float(np.mean(vp["luma"][start:end])), 1),
        "palette": _palette(vp["color_hists"], start, end),
    }


# ------------------------------------------------------------------ audio pass

def audio_pass(video: Path, fps: float) -> dict | None:
    info = ffprobe(video)
    if not info["has_audio"]:
        return None
    sr = 16000
    cp = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                        capture_output=True)
    x = np.frombuffer(cp.stdout, dtype=np.float32)
    if len(x) < sr // 2:
        return None
    hop, win = sr // 100, sr // 50
    env = np.sqrt(np.convolve(x * x, np.ones(win) / win, mode="same"))[::hop]
    k = 3
    le = np.concatenate([np.full(k, -100.0), 20 * np.log10(env + 1e-5)])  # pad: an onset at t=0 still shows as a rise
    flux = np.zeros_like(le)
    flux[k:] = np.maximum(0, le[k:] - le[:-k])
    med = float(np.median(flux)); mad_ = float(np.median(np.abs(flux - med))) + 1e-6
    thr = max(6.0, med + 5 * mad_)
    hits, last = [], -99
    for i in range(1, len(flux) - 1):
        if flux[i] >= thr and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1] and i - last >= 8:
            t = (i - k) / 100.0
            hits.append({"t": round(t, 3), "frame": int(round(t * fps)), "level_db": round(float(le[i:i + 5].max()), 1),
                         "strength_db": round(float(flux[i]), 1)})
            last = i
    bpm, conf = None, None
    if len(hits) >= 6:
        f = flux - flux.mean()
        ac = np.correlate(f, f, mode="full")[len(f) - 1:]
        lo, hi = 30, 100  # 0.30 s .. 1.00 s
        lag = lo + int(np.argmax(ac[lo:hi]))
        bpm = round(60.0 / (lag / 100.0), 1)
        conf = round(float(ac[lag] / (ac[0] + 1e-9)), 2)
    cp2 = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", cp2.stderr, re.S)
    loud = None
    if m:
        j = json.loads(m.group(0))
        loud = {"integrated_lufs": float(j["input_i"]), "true_peak_db": float(j["input_tp"]), "lra": float(j["input_lra"])}
    return {"hits": hits, "bpm_guess": bpm, "bpm_confidence": conf, "loudness": loud,
            "rms_db": {"mean": round(float(le.mean()), 1), "max": round(float(le.max()), 1)}}


# ------------------------------------------------------------------ report

def motion_chart(vp: dict, cuts: list[dict], audio: dict | None, fps: float, out: Path) -> None:
    from PIL import Image, ImageDraw

    W, H, pad = 1600, 380, 40
    n = vp["n"]
    e = np.array(vp["mad"])
    top = max(float(e.max()), 1.0)
    im = Image.new("RGB", (W, H), (18, 18, 18))
    d = ImageDraw.Draw(im)
    x = lambda f: pad + (W - 2 * pad) * f / max(n - 1, 1)
    y = lambda v: H - pad - (H - 2 * pad - 20) * v / top
    for c in cuts:
        d.line([(x(c["frame"]), pad - 10), (x(c["frame"]), H - pad)], fill=(255, 70, 70), width=2)
    pts = [(x(i), y(min(v, top))) for i, v in enumerate(e)]
    if len(pts) > 1:
        d.line(pts, fill=(120, 200, 255), width=2)
    if audio:
        for h in audio["hits"]:
            d.line([(x(h["frame"]), H - pad), (x(h["frame"]), H - pad + 14)], fill=(255, 200, 60), width=2)
    sec = 0
    while sec * fps < n:
        d.text((x(sec * fps) - 6, H - pad + 18), f"{sec}s", fill=(150, 150, 150))
        sec += max(1, int(n / fps // 12) or 1)
    d.text((pad, 8), "frame-to-frame change (blue), cuts (red), sound hits (yellow)", fill=(200, 200, 200))
    im.save(out)


def build_spec(info: dict, video: Path, cuts, shots, audio, cut_hit, flags, rel_keyframes) -> str:
    L = [f"# SPEC: {video.name}", "",
         f"Source: `{video}` | {info['width']}x{info['height']} @ {info['fps']:.3f} fps | {info['frames_counted']} frames | {info['duration']:.2f} s",
         "", "Numbers below are measured from pixels (frames downscaled to ~192 px wide). **The frames are the truth: if a description disagrees with the frames, the frames win.** "
         "Open the keyframes and `motion.png` before building; confirm each cut visually.", "", "## Summary", ""]
    avg = np.mean([s["seconds"] for s in shots]) if shots else 0
    L += [f"- Shots: **{len(shots)}** (cuts: {len(cuts)}), average shot {avg:.2f} s",
          f"- Audio: " + (f"{len(audio['hits'])} hits, tempo guess {audio['bpm_guess']} BPM (confidence {audio['bpm_confidence']}), "
                          f"loudness {audio['loudness']['integrated_lufs'] if audio['loudness'] else 'n/a'} LUFS" if audio else "none"),
          f"- Cuts landing within 2 frames of a sound hit: **{cut_hit['on_hit']}/{len(cuts)}**" if audio and cuts else "- Cuts vs sound: n/a", ""]
    L += ["## Shot list", "", "| # | frames | time (s) | len (f) | avg energy | peak | moves | dead stops | frozen | camera shift % (x,y) | palette |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(shots, 1):
        pal = " ".join(f"{p['hex']}({p['pct']:.0f}%)" for p in s["palette"][:4])
        L.append(f"| {i} | {s['start']}-{s['end']} | {s['start'] / info['fps']:.2f}-{(s['end'] + 1) / info['fps']:.2f} | {s['frames']} | {s['avg_energy']} | {s['peak_energy']} | "
                 f"{len(s['moves'])} | {len(s['dead_stops'])} | {len(s['frozen_runs'])} | {s['camera_shift_pct'][0]},{s['camera_shift_pct'][1]} | {pal} |")
    L += ["", "## Big moves (per shot)", "",
          "`arrival_k` is the share of the remaining distance covered each frame while settling (good motion is roughly 0.12 to 0.19); `travel_pct` is centroid travel as % of frame.", "",
          "| shot | start-end (f) | len (f) | peak f | peak energy | arrival_k | travel % |", "|---|---|---|---|---|---|---|"]
    for i, s in enumerate(shots, 1):
        for m in s["moves"]:
            L.append(f"| {i} | {m['start']}-{m['end']} | {m['frames']} | {m['peak_frame']} | {m['peak_energy']} | {m['arrival_k']} | {m['travel_pct']} |")
    if audio:
        L += ["", "## Sound hits (first 80)", "", "| # | t (s) | frame | level dB | strength dB |", "|---|---|---|---|---|"]
        for i, h in enumerate(audio["hits"][:80], 1):
            L.append(f"| {i} | {h['t']} | {h['frame']} | {h['level_db']} | {h['strength_db']} |")
    L += ["", "## Flags against the motion rules", ""]
    L += [f"- {f}" for f in flags] or ["- none"]
    L += ["", "## Keyframes", ""] + [f"- {k}" for k in rel_keyframes]
    L += ["", "## Limits", "", "Cut detection finds hard cuts (frame-difference spikes). Soft dissolves and whip-pans can be missed or split; check `motion.png` and the keyframes. "
          "Element positions are the centroid of changed pixels, not tracked objects. Colours are quantised to 16 levels per channel. Text is not read (look at the keyframes).", ""]
    return "\n".join(L)


def analyze(video: Path, out: Path, width: int = 192, sensitivity: float = 1.0, keyframes: bool = True) -> dict:
    need("ffmpeg")
    info = ffprobe(video)
    if not info["has_video"]:
        raise SystemExit("no video stream")
    out.mkdir(parents=True, exist_ok=True)
    fps = info["fps"]
    log(f"analyze: {video.name} ({info['width']}x{info['height']} @ {fps:.2f} fps)")
    vp = video_pass(video, width)
    info["frames_counted"] = vp["n"]
    cuts = detect_cuts(vp["mad"], vp["hdist"], sensitivity)
    bounds = [0] + [c["frame"] for c in cuts] + [vp["n"]]
    floor = noise_floor(vp["mad"], cuts)
    shots = [shot_stats(vp, bounds[i], bounds[i + 1], fps, floor) for i in range(len(bounds) - 1)]
    audio = audio_pass(video, fps)
    on_hit = 0
    cut_hit = {"on_hit": 0, "offsets_frames": []}
    if audio and cuts:
        hf = np.array([h["frame"] for h in audio["hits"]]) if audio["hits"] else np.array([])
        for c in cuts:
            if len(hf):
                off = int(c["frame"] - hf[np.argmin(np.abs(hf - c["frame"]))])
                cut_hit["offsets_frames"].append(off)
                on_hit += abs(off) <= 2
        cut_hit["on_hit"] = int(on_hit)
    flags = []
    for i, s in enumerate(shots, 1):
        for f in s["dead_stops"]:
            flags.append(f"shot {i}: fast move then dead stop at frame {f} (what reads as choppy)")
        for fr in s["frozen_runs"]:
            flags.append(f"shot {i}: nothing moves for {fr['frames']} frames from frame {fr['start']} (nothing should ever freeze)")
        for m in s["moves"]:
            if m["arrival_k"] is not None and not 0.08 <= m["arrival_k"] <= 0.30:
                flags.append(f"shot {i}: move at frames {m['start']}-{m['end']} settles with k={m['arrival_k']} (outside 0.08-0.30: linear or abrupt)")
    kf_rel: list[str] = []
    if keyframes:
        kd = out / "keyframes"
        first_frames = []
        for i, s in enumerate(shots, 1):
            for tag, f in (("first", s["start"]), ("mid", (s["start"] + s["end"]) // 2), ("last", s["end"])):
                p = grab_frame(video, f / fps, kd / f"shot_{i:02d}_{tag}.jpg", width=640)
                kf_rel.append(f"keyframes/{p.name} (frame {f})")
                if tag == "first":
                    first_frames.append((p, f"shot {i} f{f}"))
        image_sheet([p for p, _ in first_frames], [l for _, l in first_frames], out / "shots_sheet.jpg", cols=4, tile_w=400)
    motion_chart(vp, cuts, audio, fps, out / "motion.png")
    info["noise_floor"] = round(floor, 3)
    data = {"source": str(video), "info": info, "cuts": cuts, "shots": shots, "audio": audio, "cut_vs_hits": cut_hit,
            "flags": flags, "per_frame": {"energy": [round(v, 3) for v in vp["mad"]], "luma": [round(v, 1) for v in vp["luma"]],
                                           "centroid_x": [None if v is None else round(v, 4) for v in vp["cx"]],
                                           "centroid_y": [None if v is None else round(v, 4) for v in vp["cy"]],
                                           "shift_x": [round(v, 2) for v in vp["dx"]], "shift_y": [round(v, 2) for v in vp["dy"]]}}
    (out / "analysis.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    (out / "SPEC.md").write_text(build_spec(info, video, cuts, shots, audio, cut_hit, flags, kf_rel), encoding="utf-8")
    log(f"analyze: {len(shots)} shots, {len(cuts)} cuts, {len(audio['hits']) if audio else 0} sound hits -> {out}")
    return data
