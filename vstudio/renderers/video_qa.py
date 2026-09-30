#!/usr/bin/env python3
"""Inspect a rendered video: spec check, dead time, black frames, loop closure, audio levels, contact sheet.

This is the "render, inspect, refine" step. Run it after every render; open the contact sheet
(PNG) and look at it before calling a video done.

Usage:
  python scripts/video_qa.py out.mp4
  python scripts/video_qa.py out.mp4 --expect 1920x1080@60 --duration 15 --audio yes --loop
  python scripts/video_qa.py out.mp4 --sheet sheet.png --frames 16 --safe-zone
  python scripts/video_qa.py out.mp4 --at 0,1.5,3,7.25 --json report.json
  python scripts/video_qa.py out.mp4 --bpm 120 --cols 7          # one frame per beat

Exit code 1 when a hard expectation fails (spec, duration, audio presence, --loop). Dead time,
black frames and audio levels are warnings.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(video: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)])
    if r.returncode:
        raise SystemExit(f"ffprobe failed: {r.stderr.strip()[:300]}")
    data = json.loads(r.stdout)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
    return {
        "width": v["width"], "height": v["height"], "fps": num / den if den else 0.0,
        "duration": float(data["format"]["duration"]), "codec": v["codec_name"], "pix_fmt": v.get("pix_fmt"),
        "frames": int(v["nb_frames"]) if v.get("nb_frames", "").isdigit() else None,
        "has_audio": a is not None, "audio_codec": a["codec_name"] if a else None,
        "size_mb": round(int(data["format"]["size"]) / 1e6, 2),
        "bitrate_kbps": round(int(data["format"].get("bit_rate", 0)) / 1000),
    }


def ffmpeg_stderr(video: Path, vf: str | None = None, af: str | None = None) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video)]
    if vf:
        cmd += ["-vf", vf, "-an"]
    if af:
        cmd += ["-af", af, "-vn"]
    return run(cmd + ["-f", "null", "-"]).stderr


def find_freezes(video: Path, duration: float) -> list[tuple[float, float]]:
    log = ffmpeg_stderr(video, vf="freezedetect=n=-60dB:d=0.5")
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    return [(s, ends[i] if i < len(ends) else duration) for i, s in enumerate(starts)]


def find_black(video: Path) -> list[tuple[float, float]]:
    log = ffmpeg_stderr(video, vf="blackdetect=d=0.2:pic_th=0.98")
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]


def audio_levels(video: Path) -> tuple[float | None, float | None]:
    log = ffmpeg_stderr(video, af="volumedetect")
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", log)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", log)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def grab_frame(video: Path, t: float, out: Path, width: int | None = None, last: bool = False) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    cmd += ["-sseof", "-0.5"] if last else ["-ss", f"{t:.3f}"]
    cmd += ["-i", str(video)]
    if width:
        cmd += ["-vf", f"scale={width}:-2"]
    cmd += ["-update", "1", "-frames:v", "1", str(out)] if last else ["-frames:v", "1", str(out)]
    run(cmd)


def loop_ssim(video: Path, tmp: Path) -> float | None:
    first, last = tmp / "first.png", tmp / "last.png"
    grab_frame(video, 0, first)
    grab_frame(video, 0, last, last=True)
    if not (first.exists() and last.exists()):
        return None
    log = run(["ffmpeg", "-hide_banner", "-i", str(first), "-i", str(last), "-lavfi", "ssim", "-f", "null", "-"]).stderr
    m = re.search(r"All:([\d.]+)", log)
    return float(m.group(1)) if m else None


def safe_zone_box(w: int, h: int) -> tuple[int, int, int, int]:
    """Approximate UI-safe rectangle. Portrait: conservative union of TikTok / Reels / Shorts overlays.
    Landscape: the central 9:16 column, for footage that will be re-cropped to vertical."""
    if h > w:
        return round(w * 0.06), round(h * 0.14), round(w * 0.88), round(h * 0.75)
    cw = round(h * 9 / 16)
    return (w - cw) // 2, 0, (w + cw) // 2, h


def contact_sheet(video: Path, times: list[float], out: Path, cols: int, tile_w: int, safe: bool, info: dict) -> None:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=max(tile_w // 22, 11))
    except TypeError:  # old Pillow
        font = ImageFont.load_default()
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            f = Path(td) / f"f{i}.png"
            grab_frame(video, t, f, width=tile_w)
            if not f.exists():
                continue
            im = Image.open(f).convert("RGB")
            d = ImageDraw.Draw(im, "RGBA")
            if safe:
                x0, y0, x1, y1 = safe_zone_box(info["width"], info["height"])
                k = im.width / info["width"]
                d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], outline=(255, 60, 60, 230), width=2)
            label = f"{t:.2f}s"
            fs = getattr(font, "size", 14)
            tw = d.textlength(label, font=font)
            y = im.height - fs - 12  # bottom-left so the label never covers title text
            d.rectangle([4, y, tw + 14, im.height - 4], fill=(0, 0, 0, 170))
            d.text((9, y + 3), label, fill=(255, 255, 255, 255), font=font)
            tiles.append(im)
    if not tiles:
        raise SystemExit("could not extract any frames")
    th = tiles[0].height
    rows = -(-len(tiles) // cols)
    gap = 6
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * gap, rows * th + (rows + 1) * gap), (24, 24, 24))
    for i, im in enumerate(tiles):
        sheet.paste(im, (gap + (i % cols) * (tile_w + gap), gap + (i // cols) * (th + gap)))
    sheet.save(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--expect", metavar="WxH[@FPS]", help="required resolution and optional fps, e.g. 1920x1080@60")
    ap.add_argument("--duration", type=float, help="required duration in seconds")
    ap.add_argument("--tol", type=float, default=0.15, help="duration tolerance in seconds (default 0.15)")
    ap.add_argument("--audio", choices=["yes", "no"], help="require / forbid an audio track")
    ap.add_argument("--loop", action="store_true", help="require last frame ~ first frame (seamless loop)")
    ap.add_argument("--max-freeze", type=float, default=1.0, help="warn on frozen spans longer than this (s)")
    ap.add_argument("--sheet", help="contact sheet PNG path (default: <video>_contact.png)")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--frames", type=int, default=12, help="frames in the contact sheet (default 12)")
    ap.add_argument("--at", help="comma separated timestamps (s) for the sheet instead of even spacing")
    ap.add_argument("--bpm", type=float, help="sample one frame on every beat at this tempo instead of even spacing")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--tile", type=int, default=480, help="tile width in px (default 480)")
    ap.add_argument("--safe-zone", action="store_true", help="draw the approximate platform-UI safe zone on tiles")
    ap.add_argument("--json", help="also write the report to this JSON file")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found on PATH")
    video = Path(args.video)
    if not video.exists():
        raise SystemExit(f"not found: {video}")

    info = probe(video)
    checks: list[tuple[str, str, str]] = []  # (status, name, detail)

    def add(ok: bool | None, name: str, detail: str, soft: bool = False) -> None:
        checks.append((PASS if ok else (WARN if soft else FAIL), name, detail))

    print(f"{video.name}: {info['width']}x{info['height']} @ {info['fps']:.2f} fps, {info['duration']:.2f}s, "
          f"{info['codec']}/{info['pix_fmt']}, {info['size_mb']} MB, {info['bitrate_kbps']} kbps, "
          f"audio={'yes (' + info['audio_codec'] + ')' if info['has_audio'] else 'no'}")

    if args.expect:
        m = re.fullmatch(r"(\d+)x(\d+)(?:@(\d+(?:\.\d+)?))?", args.expect)
        if not m:
            raise SystemExit("--expect must look like 1920x1080@60")
        ew, eh, efps = int(m.group(1)), int(m.group(2)), m.group(3)
        add((info["width"], info["height"]) == (ew, eh), "resolution", f"{info['width']}x{info['height']} (want {ew}x{eh})")
        if efps:
            add(abs(info["fps"] - float(efps)) < 0.05, "fps", f"{info['fps']:.2f} (want {efps})")
    if args.duration is not None:
        add(abs(info["duration"] - args.duration) <= args.tol, "duration", f"{info['duration']:.2f}s (want {args.duration}s +/- {args.tol})")
    if args.audio:
        add(info["has_audio"] == (args.audio == "yes"), "audio track", f"has_audio={info['has_audio']} (want {args.audio})")
    add(info["pix_fmt"] == "yuv420p", "pixel format", f"{info['pix_fmt']} (yuv420p plays everywhere)", soft=True)

    freezes = [(a, b) for a, b in find_freezes(video, info["duration"]) if b - a >= args.max_freeze]
    add(not freezes, "dead time", "none" if not freezes else ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in freezes)
        + f" frozen longer than {args.max_freeze}s (intentional hold? otherwise tighten)", soft=True)
    black = find_black(video)
    add(not black, "black frames", "none" if not black else ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in black), soft=True)

    with tempfile.TemporaryDirectory() as td:
        ssim = loop_ssim(video, Path(td))
    if ssim is not None:
        add(ssim >= 0.95 if args.loop else True, "loop closure", f"first vs last frame SSIM {ssim:.3f}"
            + (" (seamless)" if ssim >= 0.95 else " (not a seamless loop)"), soft=not args.loop)

    if info["has_audio"]:
        mean, peak = audio_levels(video)
        if mean is not None and peak is not None:
            add(peak < -0.1, "audio peak", f"{peak} dB" + (" (clipping risk, lower the gain)" if peak >= -0.1 else ""), soft=True)
            add(mean > -30, "audio level", f"mean {mean} dB" + (" (very quiet)" if mean <= -30 else ""), soft=True)

    sheet_path = None
    if not args.no_sheet:
        if args.at:
            times = [float(x) for x in args.at.split(",")]
        elif args.bpm:
            beats = int(info["duration"] * args.bpm / 60)
            times = [k * 60 / args.bpm for k in range(min(beats, 64))]
        else:
            times = [(i + 0.5) / args.frames * info["duration"] for i in range(args.frames)]
        sheet_path = Path(args.sheet) if args.sheet else video.with_name(video.stem + "_contact.png")
        contact_sheet(video, times, sheet_path, args.cols, args.tile, args.safe_zone, info)

    for status, name, detail in checks:
        print(f"  [{status}] {name}: {detail}")
    if sheet_path:
        print(f"contact sheet: {sheet_path}")
    if args.json:
        Path(args.json).write_text(json.dumps({"info": info, "checks": [
            {"status": s, "name": n, "detail": d} for s, n, d in checks], "sheet": str(sheet_path) if sheet_path else None},
            indent=2), encoding="utf-8")
    return 1 if any(s == FAIL for s, _, _ in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
