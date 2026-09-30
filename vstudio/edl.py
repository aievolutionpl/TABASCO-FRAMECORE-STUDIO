"""Edit-decision-list renderer: footage + images -> one finished MP4.

Production-correctness rules (from video-use, MIT, and our own tests):
  1. Each clip is normalised to its own segment (size, fps, pixel format, 48 kHz stereo) and segments are joined
     losslessly with the concat demuxer, so nothing is re-encoded twice when overlays are added.
  2. 30 ms audio fades at every segment boundary (no clicks at cuts).
  3. Overlays first, subtitles LAST in the video chain, otherwise an overlay can hide the captions.
  4. Loudness is mastered in two passes (measure, then linear gain), default -14 LUFS / -1.5 dBTP.
  5. Cuts never depend on an unverified guess: `silence-cut` snaps to measured silence, with padding.

EDL (JSON):
{
  "size": "1080x1920", "fps": 30, "loudness": -14,
  "clips": [{"src": "a.mp4", "in": 1.2, "out": 6.0, "speed": 1.0, "fit": "cover|contain", "focus_x": 0.5, "focus_y": 0.5,
             "mute": false, "fade_in": 0, "fade_out": 0, "duration": 3 (images), "transition": {"type": "fade", "duration": 0.4}}],
  "overlays": [{"type": "text", "text": "...", "start": 0.5, "end": 3, "position": "bottom|top|center|lower-third",
                "size": 64, "color": "white", "font": "bold|sans|serif|mono|impact|<path.ttf>", "box": true, "fade": 0.2},
               {"type": "image", "src": "logo.png", "start": 0, "end": 99, "x": "W-w-40", "y": "40", "width": 180}],
  "audio": [{"src": "music.mp3", "start": 0, "gain_db": -18, "loop": true, "duck": true, "fade_in": 0.5, "fade_out": 1.5}],
  "subtitles": {"file": "subs.srt", "style": "clean|bold|minimal"}
}
Paths are relative to the EDL file.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .common import die, ffprobe, log, need, run

IMG = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
XFADE = {"fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown", "circleopen",
         "circleclose", "dissolve", "fadeblack", "fadewhite", "radial", "smoothleft", "smoothright", "zoomin", "pixelize", "hlslice", "vuslice"}
FONTS = {"sans": "arial.ttf", "bold": "arialbd.ttf", "serif": "times.ttf", "mono": "consola.ttf", "impact": "impact.ttf",
         "segoe": "segoeui.ttf", "segoe-bold": "segoeuib.ttf"}
SUB_STYLES = {
    "clean": "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1.6,Shadow=0,MarginV=40,Alignment=2",
    "bold": "FontName=Arial,Bold=1,FontSize=20,PrimaryColour=&H0000E6FF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,MarginV=70,Alignment=2",
    "minimal": "FontName=Arial,FontSize=11,PrimaryColour=&H00F0F0F0,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=0,MarginV=30,Alignment=2",
}
POSITIONS = {"bottom": ("(w-text_w)/2", "h*0.80"), "top": ("(w-text_w)/2", "h*0.10"), "center": ("(w-text_w)/2", "(h-text_h)/2"),
             "lower-third": ("w*0.06", "h*0.74")}
X264 = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off"]


def _size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def _atempo(speed: float) -> str:
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


def _make_segment(i: int, c: dict, base: Path, W: int, H: int, fps: float, tmp: Path, preview: bool) -> tuple[Path, float]:
    src = Path(c["src"]); src = src if src.is_absolute() else base / src
    if not src.exists():
        die(f"clip {i}: source not found: {src}")
    is_img = src.suffix.lower() in IMG
    speed = float(c.get("speed", 1.0))
    ss = float(c.get("in", 0.0))
    if is_img:
        dur_src = float(c.get("duration", 3.0)); has_audio = False
    else:
        info = ffprobe(src)
        end = float(c["out"]) if c.get("out") is not None else info["duration"]
        dur_src = end - ss
        has_audio = info["has_audio"] and not c.get("mute", False)
        if dur_src <= 0:
            die(f"clip {i}: 'out' must be after 'in'")
    dur = dur_src / speed
    cmd: list = ["ffmpeg", "-y", "-loglevel", "error"]
    if is_img:
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.4f}", "-i", src]
    else:
        cmd += ["-ss", f"{ss:.4f}", "-t", f"{dur_src:.4f}", "-i", src]
    if not has_audio:
        cmd += ["-f", "lavfi", "-t", f"{dur:.4f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    fx, fy = float(c.get("focus_x", 0.5)), float(c.get("focus_y", 0.5))
    if c.get("fit", "cover") == "contain":
        v = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:5[bg];"
             f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    else:
        v = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}"
    v += f",setpts=(PTS-STARTPTS)/{speed},fps={fps},setsar=1"
    fi, fo = float(c.get("fade_in", 0)), float(c.get("fade_out", 0))
    if fi > 0:
        v += f",fade=t=in:st=0:d={fi}"
    if fo > 0:
        v += f",fade=t=out:st={max(dur - fo, 0):.4f}:d={fo}"
    v += ",format=yuv420p[v]"
    asrc = "[0:a]" if has_audio else "[1:a]"
    a = asrc + (_atempo(speed) + "," if has_audio and abs(speed - 1) > 1e-3 else "")
    a += f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.03,afade=t=out:st={max(dur - 0.03, 0):.4f}:d=0.03"
    if fi > 0:
        a += f",afade=t=in:st=0:d={fi}"
    if fo > 0:
        a += f",afade=t=out:st={max(dur - fo, 0):.4f}:d={fo}"
    a += "[a]"
    seg = tmp / f"seg_{i:03d}.mp4"
    crf, preset = ("26", "ultrafast") if preview else ("16", "fast")
    cmd += ["-filter_complex", f"{v};{a}", "-map", "[v]", "-map", "[a]", *X264, "-crf", crf, "-preset", preset, "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.4f}", seg]
    run(cmd)
    return seg, dur


def _join(segs: list[Path], durs: list[float], clips: list[dict], tmp: Path, fps: float, preview: bool) -> tuple[Path, float]:
    trans = [c.get("transition") for c in clips]
    out = tmp / "joined.mp4"
    if not any(trans[1:]):
        lst = tmp / "concat.txt"
        lst.write_text("".join(f"file '{s.name}'\n" for s in segs), encoding="utf-8")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", out.name], cwd=tmp)
        return out, sum(durs)
    cmd: list = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in segs:
        cmd += ["-i", s.name]
    parts, cv, ca, total = [], "[0:v]", "[0:a]", durs[0]
    for k in range(1, len(segs)):
        t = trans[k]
        nv, na = f"[v{k}]", f"[a{k}]"
        if t:
            typ = t.get("type", "fade"); d = float(t.get("duration", 0.4))
            if typ not in XFADE:
                die(f"unknown transition '{typ}'. Use one of: {', '.join(sorted(XFADE))}")
            d = min(d, durs[k] * 0.9, total * 0.9)
            parts.append(f"{cv}[{k}:v]xfade=transition={typ}:duration={d}:offset={total - d:.4f}{nv}")
            parts.append(f"{ca}[{k}:a]acrossfade=d={d}{na}")
            total += durs[k] - d
        else:
            parts.append(f"{cv}{ca}[{k}:v][{k}:a]concat=n=2:v=1:a=1{nv}{na}")
            total += durs[k]
        cv, ca = nv, na
    crf, preset = ("26", "ultrafast") if preview else ("16", "fast")
    run(cmd + ["-filter_complex", ";".join(parts), "-map", cv, "-map", ca, *X264, "-crf", crf, "-preset", preset, "-r", str(fps),
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out.name], cwd=tmp)
    return out, total


def _font_file(name: str | None, tmp: Path, base: Path, idx: int) -> str:
    name = name or "bold"
    cand = Path(name) if name.lower().endswith((".ttf", ".otf")) else Path(r"C:\Windows\Fonts") / FONTS.get(name, "arialbd.ttf")
    if not cand.is_absolute():
        cand = base / cand
    if not cand.exists():
        cand = Path(r"C:\Windows\Fonts\arial.ttf")
    if not cand.exists():
        die(f"font not found: {name}")
    dst = tmp / f"font{idx}{cand.suffix}"
    shutil.copy2(cand, dst)
    return dst.name


def _audio_graph(edl: dict, base: Path, tmp: Path, total: float, has_main_audio: bool, first_idx: int) -> tuple[list, str, str]:
    """Returns (extra input args, filtergraph, output label) for the audio chain of the final pass (input 0 = joined video)."""
    extra: list = []
    tracks = edl.get("audio", [])
    parts = []
    mix_in = ["[0:a]"] if has_main_audio else []
    need_sc = any(t.get("duck") for t in tracks) and has_main_audio
    if need_sc:
        parts.append("[0:a]asplit=2[mainA][scA]")
        mix_in = ["[mainA]"]
    k = 0
    for t in tracks:
        src = Path(t["src"]); src = src if src.is_absolute() else base / src
        if not src.exists():
            die(f"audio track not found: {src}")
        if t.get("loop", False):
            extra += ["-stream_loop", "-1"]
        extra += ["-i", src]
        lab = f"[{first_idx + sum(1 for x in extra if x == '-i') - 1}:a]"   # input index of this track in the final command
        start = float(t.get("start", 0)); gain = float(t.get("gain_db", -6))
        fi, fo = float(t.get("fade_in", 0.2)), float(t.get("fade_out", 0.6))
        chain = f"{lab}aresample=48000,aformat=channel_layouts=stereo,atrim=0:{max(total - start, 0.1):.3f},asetpts=PTS-STARTPTS,volume={gain}dB"
        if fi > 0:
            chain += f",afade=t=in:st=0:d={fi}"
        if fo > 0:
            chain += f",afade=t=out:st={max(total - start - fo, 0):.3f}:d={fo}"
        if start > 0:
            chain += f",adelay={int(start * 1000)}|{int(start * 1000)}"
        out_lab = f"[t{k}]"
        if t.get("duck") and need_sc:
            parts.append(chain + f"[raw{k}]")
            parts.append(f"[raw{k}][scA]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350:makeup=1{out_lab}")
        else:
            parts.append(chain + out_lab)
        mix_in.append(out_lab)
        k += 1
    if not mix_in:
        return extra, "", ""
    if len(mix_in) == 1:
        parts.append(f"{mix_in[0]}anull[amix]")
    else:
        parts.append("".join(mix_in) + f"amix=inputs={len(mix_in)}:normalize=0:duration=first:dropout_transition=0[amix]")
    return extra, ";".join(parts), "[amix]"


def _measure(cmd_in: list, graph: str, lab: str, lufs: float, tp: float, cwd: Path) -> str:
    g = graph + f";{lab}loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json[mo]"
    cp = subprocess.run(["ffmpeg", "-hide_banner", "-y", *[str(x) for x in cmd_in], "-filter_complex", g, "-map", "[mo]", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(cwd))
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", cp.stderr, re.S)
    if not m:
        log("WARNING: loudness measurement failed, audio is NOT normalised: " + cp.stderr[-400:].replace("\n", " "))
        return f"{lab}anull[aout]"
    if "-inf" in m.group(0):
        log("note: silent audio, skipping loudness normalisation")
        return f"{lab}anull[aout]"
    j = json.loads(m.group(0))
    return (f"{lab}loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
            f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000[aout]")


def build_edl(edl: dict, base: Path, out: Path, preview: bool = False, keep_tmp: bool = False) -> dict:
    need("ffmpeg")
    W, H = _size(edl.get("size", "1920x1080"))
    fps = float(edl.get("fps", 30))
    clips = edl["clips"]
    if not clips:
        die("EDL has no clips")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f".tmp_{out.stem}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    if preview:
        W, H = (W // 2 // 2 * 2, H // 2 // 2 * 2)
    segs, durs = [], []
    for i, c in enumerate(clips):
        s, d = _make_segment(i, c, base, W, H, fps, tmp, preview)
        segs.append(s); durs.append(d)
        log(f"  clip {i + 1}/{len(clips)}: {Path(c['src']).name} -> {d:.2f}s")
    joined, total = _join(segs, durs, clips, tmp, fps, preview)
    overlays, tracks, subs = edl.get("overlays", []), edl.get("audio", []), edl.get("subtitles")
    lufs = edl.get("loudness", -14)
    crf, preset = ("28", "ultrafast") if preview else ("17", "medium")
    if not (overlays or tracks or subs or lufs):
        shutil.copy2(joined, out)
    else:
        inputs: list = ["-i", joined.name]
        vparts, cur, n_img = [], "[0:v]", 0
        for k, o in enumerate(overlays):
            s, e = float(o.get("start", 0)), float(o.get("end", total))
            if o["type"] == "text":
                (tmp / f"ov{k}.txt").write_text(o["text"], encoding="utf-8")
                fontf = _font_file(o.get("font"), tmp, base, k)
                px, py = POSITIONS.get(o.get("position", "bottom"), POSITIONS["bottom"])
                size = int(o.get("size", max(H // 18, 24)))
                fade = float(o.get("fade", 0))
                alpha = "" if fade <= 0 else f":alpha='min(1,max(0,min((t-{s})/{fade},({e}-t)/{fade})))'"
                box = f":box=1:boxcolor={o.get('box_color', 'black@0.55')}:boxborderw={o.get('box_pad', 18)}" if o.get("box") else ""
                nxt = f"[o{k}]"
                vparts.append(f"{cur}drawtext=fontfile='{fontf}':textfile='ov{k}.txt':expansion=none:fontsize={size}:fontcolor={o.get('color', 'white')}:"
                              f"x={o.get('x', px)}:y={o.get('y', py)}{box}{alpha}:enable='between(t,{s},{e})'{nxt}")
                cur = nxt
            elif o["type"] == "image":
                src = Path(o["src"]); src = src if src.is_absolute() else base / src
                n_img += 1
                shutil.copy2(src, tmp / f"img{k}{src.suffix}")
                inputs += ["-i", f"img{k}{src.suffix}"]
                idx = sum(1 for x in inputs if x == "-i") - 1
                wd = int(o.get("width", 200))
                vparts.append(f"[{idx}:v]scale={wd}:-1,format=rgba[lg{k}]")
                nxt = f"[o{k}]"
                vparts.append(f"{cur}[lg{k}]overlay={o.get('x', 'W-w-40')}:{o.get('y', '40')}:enable='between(t,{s},{e})'{nxt}")
                cur = nxt
            else:
                die(f"unknown overlay type '{o['type']}'")
        if subs:  # subtitles LAST
            sf = Path(subs["file"]); sf = sf if sf.is_absolute() else base / sf
            shutil.copy2(sf, tmp / "subs.srt")
            style = SUB_STYLES.get(subs.get("style", "clean"), subs.get("style"))
            vparts.append(f"{cur}subtitles=filename=subs.srt:force_style='{style}'[vs]")
            cur = "[vs]"
        vparts.append(f"{cur}format=yuv420p[vout]")
        main_info = ffprobe(joined)
        extra, agraph, alab = _audio_graph(edl, base, tmp, total, main_info["has_audio"], sum(1 for x in inputs if x == "-i"))
        full_inputs = inputs + extra
        graph = ";".join(vparts)
        maps = ["-map", "[vout]"]
        if alab:
            if lufs:
                af = _measure(full_inputs, agraph, alab, float(lufs), -1.5, tmp)
            else:
                af = f"{alab}anull[aout]"
            graph += ";" + agraph + ";" + af
            maps += ["-map", "[aout]"]
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *full_inputs, "-filter_complex", graph, *maps, *X264, "-crf", crf, "-preset", preset,
               "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{total:.4f}", str(out.resolve())]
        run(cmd, cwd=tmp)
    info = ffprobe(out)
    if not keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    res = {"output": str(out), "expected_duration": round(total, 3), "actual_duration": round(info["duration"], 3),
           "size": f"{info['width']}x{info['height']}", "fps": round(info["fps"], 2), "has_audio": info["has_audio"], "clips": len(clips)}
    if info["has_audio"] and lufs:
        from .audio import measure_loudness
        ld = measure_loudness(out)
        res["loudness"] = ld
        if ld and abs(ld["integrated_lufs"] - float(lufs)) > 1.5:
            log(f"WARNING: loudness is {ld['integrated_lufs']} LUFS, target {lufs}. The mix is peak-limited (sparse loud transients); "
                f"compress or limit the loud sources, or raise the quiet ones.")
    log(f"edl: {res['actual_duration']}s (expected {res['expected_duration']}s) -> {out}")
    return res


# ------------------------------------------------------------------ helpers that generate EDLs

def detect_silence(src: Path, noise_db: float = -32.0, min_len: float = 0.45) -> list[tuple[float, float]]:
    cp = run(["ffmpeg", "-hide_banner", "-i", src, "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"], check=False)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", cp.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", cp.stderr)]
    dur = ffprobe(src)["duration"]
    out = []
    for i, s in enumerate(starts):
        out.append((max(s, 0.0), ends[i] if i < len(ends) else dur))
    return out


def silence_cut_edl(src: Path, size: str | None, fps: float | None, noise_db: float, min_len: float, pad: float) -> dict:
    info = ffprobe(src)
    sil = detect_silence(src, noise_db, min_len)
    keep, cur = [], 0.0
    for s, e in sil:
        if s - cur > 0.15:
            keep.append([max(cur - pad, 0.0), min(s + pad, info["duration"])])
        cur = e
    if info["duration"] - cur > 0.15:
        keep.append([max(cur - pad, 0.0), info["duration"]])
    merged: list[list[float]] = []
    for a, b in keep:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return {"size": size or f"{info['width']}x{info['height']}", "fps": fps or round(info["fps"]) or 30,
            "clips": [{"src": str(src), "in": round(a, 3), "out": round(b, 3), "fit": "cover"} for a, b in merged]}
