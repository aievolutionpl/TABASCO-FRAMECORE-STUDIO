"""Frame-locked comparison of a render against a reference, plus a brief for a fresh-context critic.

The session that built a video knows every compromise it made; a critic that did not build it does not.
`compare` produces the evidence (numbers + paired frames) and CRITIC_BRIEF.md to hand to the `video-critic`
subagent (or a new session) with the default verdict "reject".
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .analyze import analyze
from .common import ffprobe, grab_frame, log

CRITIC_PROMPT = """You're a harsh motion director and you didn't build this. Default: reject.
Put the reference and the render side by side, frame-locked, and compare them.
For every mismatch give: shot + frame number, what's wrong, why it looks worse, and the exact fix
("card lands 6 frames early, delay to frame 44").
Also measure frame-to-frame change and flag:
- any fast move followed by a dead stop (that's what "choppy" is)
- text moving before it's readable (text must stay still at least 8 frames before it moves)
- sound landing off its visual hit
Prioritize the 5 fixes that improve the video most. Score out of 10. Nothing ships below 8/10."""


def _load(video: Path, out: Path, reuse: bool) -> dict:
    f = out / "analysis.json"
    if reuse and f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("source") == str(video):
            return d
    return analyze(video, out)


def _color_dist(a: list[dict], b: list[dict]) -> float | None:
    def rgb(h):
        return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    if not a or not b:
        return None
    ds = [min(np.linalg.norm(rgb(x["hex"]) - rgb(y["hex"])) for y in b) for x in a[:3]]
    return round(float(np.mean(ds)), 1)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _align(ref: dict, mine: dict) -> list[tuple[int, int | None]]:
    rf, mf = ref["info"]["fps"], mine["info"]["fps"]
    out = []
    for i, s in enumerate(ref["shots"]):
        a0, a1 = s["start"] / rf, (s["end"] + 1) / rf
        best, bo = None, 0.0
        for j, t in enumerate(mine["shots"]):
            o = _overlap(a0, a1, t["start"] / mf, (t["end"] + 1) / mf)
            if o > bo:
                best, bo = j, o
        out.append((i, best if bo >= 0.3 * (a1 - a0) else None))
    return out


def _pair_image(ref_v: Path, my_v: Path, rs: dict, ms: dict, rf: float, mf: float, out: Path, label: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    fr = (0.02, 0.25, 0.5, 0.75, 0.98)
    tw = 380
    tiles = []
    for row, (v, s, f, tag) in enumerate(((ref_v, rs, rf, "REF"), (my_v, ms, mf, "MINE"))):
        for k, u in enumerate(fr):
            frame = int(s["start"] + u * (s["end"] - s["start"]))
            p = grab_frame(v, frame / f, out.parent / "_tmp" / f"{tag}_{k}.jpg", width=tw)
            tiles.append((row, k, Image.open(p).convert("RGB"), f"{tag} f{frame}"))
    th = tiles[0][2].height
    sheet = Image.new("RGB", (len(fr) * tw + (len(fr) + 1) * 6, 2 * th + 3 * 6 + 22), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=13)
    except TypeError:
        font = ImageFont.load_default()
    d.text((8, 4), label, fill=(230, 230, 230), font=font)
    for row, k, im, lab in tiles:
        x, y = 6 + k * (tw + 6), 22 + 6 + row * (th + 6)
        sheet.paste(im, (x, y))
        d.rectangle([x + 3, y + th - 20, x + 8 + d.textlength(lab, font=font), y + th - 3], fill=(0, 0, 0))
        d.text((x + 6, y + th - 19), lab, fill=(255, 255, 255), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)


def compare(ref: Path, mine: Path, out: Path, reuse: bool = True) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    A = _load(ref, out / "ref", reuse)
    B = _load(mine, out / "mine", reuse)
    rf, mf = A["info"]["fps"], B["info"]["fps"]
    issues: list[str] = []
    shots_out = []
    align = _align(A, B)
    if len(A["shots"]) != len(B["shots"]):
        issues.append(f"shot count differs: reference {len(A['shots'])}, render {len(B['shots'])}")
    for i, j in align:
        rs = A["shots"][i]
        if j is None:
            issues.append(f"shot {i + 1} (ref f{rs['start']}-{rs['end']}): no matching shot in the render (missing or merged)")
            continue
        ms = B["shots"][j]
        off = round((ms["start"] / mf - rs["start"] / rf) * rf)
        dlen = round(ms["seconds"] * rf - rs["seconds"] * rf)
        er = np.array(A["per_frame"]["energy"][rs["start"] + 1:rs["end"] + 1] or [0.0])
        em = np.array(B["per_frame"]["energy"][ms["start"] + 1:ms["end"] + 1] or [0.0])
        L = 120
        a = np.interp(np.linspace(0, 1, L), np.linspace(0, 1, len(er)), er)
        b = np.interp(np.linspace(0, 1, L), np.linspace(0, 1, len(em)), em)
        corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-6 and b.std() > 1e-6 else None
        pr = (int(np.argmax(er)) if len(er) else 0)
        pm = (int(np.argmax(em)) if len(em) else 0)
        row = {"ref_shot": i + 1, "render_shot": j + 1, "start_offset_frames": off, "length_delta_frames": dlen,
               "energy_correlation": None if corr is None else round(corr, 2),
               "peak_offset_frames": round((pm / mf - pr / rf) * rf), "palette_distance": _color_dist(rs["palette"], ms["palette"]), "moves": []}
        if abs(off) >= 2:
            issues.append(f"shot {i + 1} (ref f{rs['start']}): cut lands {abs(off)} frames {'late' if off > 0 else 'early'} in the render (render f{ms['start']}); "
                          f"{'advance' if off > 0 else 'delay'} it by {abs(off)}")
        if abs(dlen) >= 3:
            issues.append(f"shot {i + 1}: length differs by {dlen:+d} frames (ref {rs['frames']}, render {ms['frames']})")
        for k, (mr, mm) in enumerate(zip(rs["moves"], ms["moves"]), 1):
            ds = round((mm["start"] - ms["start"]) - (mr["start"] - rs["start"]))
            dd = mm["frames"] - mr["frames"]
            dk = None if mr["arrival_k"] is None or mm["arrival_k"] is None else round(mm["arrival_k"] - mr["arrival_k"], 3)
            row["moves"].append({"n": k, "start_delta_frames": ds, "duration_delta_frames": dd, "arrival_k_delta": dk})
            if abs(ds) >= 2:
                issues.append(f"shot {i + 1} move {k}: starts {abs(ds)} frames {'later' if ds > 0 else 'earlier'} than reference "
                              f"(ref f{mr['start']}, render f{mm['start']}); {'advance' if ds > 0 else 'delay'} by {abs(ds)}")
            if abs(dd) >= 3:
                issues.append(f"shot {i + 1} move {k}: lasts {dd:+d} frames vs reference ({mr['frames']} -> {mm['frames']})")
            if dk is not None and abs(dk) >= 0.06:
                issues.append(f"shot {i + 1} move {k}: settles {'more abruptly' if dk > 0 else 'more linearly'} than reference (arrival_k {mm['arrival_k']} vs {mr['arrival_k']})")
        if len(ms["dead_stops"]) > len(rs["dead_stops"]):
            issues.append(f"shot {i + 1}: render has dead stops at frames {ms['dead_stops']} that the reference does not (choppy)")
        if len(ms["frozen_runs"]) > len(rs["frozen_runs"]):
            fz = [(f['start'], f['frames']) for f in ms['frozen_runs']]
            issues.append(f"shot {i + 1}: render freezes (start frame, length) {fz}; reference keeps moving")
        shots_out.append(row)
        _pair_image(ref, mine, rs, ms, rf, mf, out / "pairs" / f"shot_{i + 1:02d}.jpg",
                    f"shot {i + 1}  REF f{rs['start']}-{rs['end']}  vs  MINE f{ms['start']}-{ms['end']}")
    audio = {}
    if A["audio"] and B["audio"]:
        rh = np.array([h["t"] for h in A["audio"]["hits"]]); mh = np.array([h["t"] for h in B["audio"]["hits"]])
        offs = []
        for t in rh:
            if len(mh):
                k = int(np.argmin(np.abs(mh - t)))
                offs.append(round((mh[k] - t) * 1000))
        bad = [o for o in offs if abs(o) > 60]
        audio = {"ref_hits": len(rh), "render_hits": len(mh), "offsets_ms": offs,
                 "loudness_ref": A["audio"]["loudness"], "loudness_render": B["audio"]["loudness"]}
        if len(rh) and len(mh) < 0.7 * len(rh):
            issues.append(f"sound: render has {len(mh)} hits, reference {len(rh)}; important actions have no sound")
        if bad:
            issues.append(f"sound: {len(bad)} of {len(offs)} hits are more than 60 ms off the reference (offsets ms: {offs})")
        lr, lm = A["audio"]["loudness"], B["audio"]["loudness"]
        if lr and lm and abs(lr["integrated_lufs"] - lm["integrated_lufs"]) > 2:
            issues.append(f"sound: loudness {lm['integrated_lufs']} LUFS vs reference {lr['integrated_lufs']} LUFS (target about -14)")
    elif A["audio"] and not B["audio"]:
        issues.append("sound: the render has no audio; the reference does")
    # motion flags that exist in the render regardless of the reference
    for f in B["flags"]:
        if "dead stop" in f or "nothing moves" in f:
            issues.append("render: " + f)
    result = {"reference": str(ref), "render": str(mine), "shots": shots_out, "audio": audio, "issues": sorted(set(issues), key=issues.index)}
    (out / "compare.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    L = [f"# COMPARE: {mine.name} vs reference {ref.name}", "",
         f"Reference: {A['info']['width']}x{A['info']['height']} @ {rf:.2f} fps, {len(A['shots'])} shots. Render: {B['info']['width']}x{B['info']['height']} @ {mf:.2f} fps, {len(B['shots'])} shots.", "",
         "## Mismatches (most specific first)", ""]
    L += [f"{n}. {t}" for n, t in enumerate(result["issues"], 1)] or ["None measured. Still look at the pair images: numbers do not catch a wrong layout."]
    L += ["", "## Per shot", "", "| ref shot | render shot | start offset (f) | length delta (f) | energy corr | peak offset (f) | palette dist |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['ref_shot']} | {r['render_shot']} | {r['start_offset_frames']} | {r['length_delta_frames']} | {r['energy_correlation']} | {r['peak_offset_frames']} | {r['palette_distance']} |" for r in shots_out]
    L += ["", "Pair images: `pairs/shot_XX.jpg` (top row reference, bottom row render, same relative positions in the shot).", ""]
    (out / "COMPARE.md").write_text("\n".join(L), encoding="utf-8")
    brief = [f"# Critic brief", "", "Run this in a **fresh context** (the `video-critic` subagent or a new session). You did not build this video; you have no attachment to it.", "",
             "## Inputs", "", f"- Reference: `{ref}`", f"- Render: `{mine}`", f"- Measured comparison: `{out / 'COMPARE.md'}` and `{out / 'compare.json'}`",
             f"- Paired frames (open every one): `{out / 'pairs'}`", f"- Reference study: `{out / 'ref' / 'SPEC.md'}`; render study: `{out / 'mine' / 'SPEC.md'}`", "",
             "## Your role", "", CRITIC_PROMPT, "", "## Output format", "",
             "```", "SCORE: x/10   (VERDICT: reject | ship)", "FIX 1: shot N, frame F: <what is wrong> / <why it looks worse> / <exact fix with frame numbers>", "... up to FIX 5", "```", "",
             "Ground every claim in a frame number or a measured value. \"The motion feels weird\" is not feedback. Do not edit the project; report only.", ""]
    (out / "CRITIC_BRIEF.md").write_text("\n".join(brief), encoding="utf-8")
    import shutil
    shutil.rmtree(out / "pairs" / "_tmp", ignore_errors=True)
    log(f"compare: {len(result['issues'])} mismatches -> {out}")
    return result
