#!/usr/bin/env python3
"""Deterministic HTML -> MP4 recorder for code-animated pages (canvas, SVG, Three.js, GSAP, CSS).

Frame-exact capture: the page is stepped one frame at a time and screenshotted, so a slow
machine never drops frames. Two timing modes:

  seek   page exposes window.seek(t) (or draw/render/renderFrame); t is in seconds.
         Fully deterministic, preferred. See Skills/remotion-video-creator/references/.
  clock  any page that animates with requestAnimationFrame / setTimeout / Date.now /
         performance.now / GSAP. Playwright's fake clock is advanced frame by frame and
         CSS/WAAPI animations are seeked to the same time.

Usage:
  python scripts/html_to_video.py anim.html -o out.mp4 --size 1920x1080 --fps 60 --duration 15
  python scripts/html_to_video.py anim.html --still 3.5 -o frame.png      # one frame, fast
  python scripts/html_to_video.py anim.html -o out.mp4 --audio track.mp3
  python scripts/html_to_video.py anim.html -o out.mp4 --fps 60 --subframes 6      # motion blur (seek mode)
  python scripts/html_to_video.py anim.html -o out --sizes 1920x1080,1080x1920,1080x1080   # all aspects in parallel

Page conventions (all optional): window.DURATION or window.DUR (seconds), window.__ready (promise) or window.READY (bool),
window.__CAPTURE__ is set to true before page scripts run, so pages can skip autoplay.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SEEK_NAMES = ["seek", "renderFrame", "draw", "render"]

CHROMIUM_ARGS = [
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
    "--hide-scrollbars",
    "--force-color-profile=srgb",
    "--disable-lcd-text",
    "--font-render-hinting=none",
    "--autoplay-policy=no-user-gesture-required",
]

# Runs in the page after each clock step: seeks CSS animations / transitions / WAAPI to `elapsed` ms.
SEEK_ANIMATIONS_JS = """
(elapsed) => {
  const starts = (window.__animStarts = window.__animStarts || new WeakMap());
  for (const a of document.getAnimations()) {
    if (!starts.has(a)) starts.set(a, elapsed);  // first seen now: treat as just started
    a.pause();
    a.currentTime = elapsed - starts.get(a);
  }
}
"""

READY_JS = """
async () => {
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  if (window.__ready) await window.__ready;
}
"""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def parse_size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        return int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError("size must look like 1920x1080")


def launch_browser(pw, preferred: str | None, extra_args: list[str] | None = None):
    """Playwright's bundled headless shell is often missing; fall back to Chrome, Edge, any local Chromium."""
    chromium_args = CHROMIUM_ARGS + list(extra_args or [])
    attempts: list[dict] = []
    if preferred:
        attempts.append({"executable_path": preferred} if os.path.exists(preferred) else {"channel": preferred})
    attempts += [{}, {"channel": "chrome"}, {"channel": "msedge"}]
    root = os.path.expanduser("~/AppData/Local/ms-playwright")
    for pattern in ("chromium_headless_shell-*/*/headless_shell.exe", "chromium-*/chrome-win/chrome.exe"):
        for exe in sorted(glob.glob(os.path.join(root, pattern)), reverse=True):
            attempts.append({"executable_path": exe})
    last = None
    for kwargs in attempts:
        try:
            return pw.chromium.launch(args=chromium_args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - try the next candidate
            last = exc
    raise SystemExit(f"No usable Chromium found. Last error: {last}")


def install_vendor_routes(target) -> None:
    """VSTUDIO_VENDOR_INDEX (plik index.json z `vstudio vendor`): żądania do zewnętrznych URL-i z indeksu dostają lokalną kopię.

    Dzięki temu strona z GSAP z CDN renderuje się offline, a jej HTML zostaje bez zmian (u innych dalej ładuje z CDN).
    """
    import json
    import mimetypes
    import re

    index = os.environ.get("VSTUDIO_VENDOR_INDEX")
    if not index or not os.path.exists(index):
        return
    urls = json.loads(Path(index).read_text(encoding="utf-8"))
    base = Path(index).parent

    def handler(route):
        name = urls.get(route.request.url)
        f = base / name if name else None
        if f is not None and f.is_file():
            ctype = "application/javascript" if f.suffix in (".js", ".mjs") else (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            route.fulfill(body=f.read_bytes(), content_type=ctype, headers={"access-control-allow-origin": "*"})
        else:
            route.continue_()

    target.route(re.compile(r"^https?://(?!127\.0\.0\.1|localhost)"), handler)


def serve_directory(directory: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    """Local pages need http:// (not file://) so ES modules and importmaps work."""

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D102
            pass

        def do_GET(self):  # noqa: D102
            if self.path.startswith("/favicon.ico"):
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

    handler = functools.partial(Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def start_ffmpeg(args, width: int, height: int, duration: float, out: Path, logfile) -> subprocess.Popen:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH")
    src_w, src_h = round(width * args.scale), round(height * args.scale)  # screenshot size incl. device scale
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{src_w}x{src_h}", "-framerate", str(args.fps), "-i", "-",
    ]
    if args.audio:
        cmd += ["-i", args.audio]
    cmd += [
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-r", str(args.fps), "-movflags", "+faststart",
        # sRGB frames -> BT.709 limited-range yuv420p, tagged so players do not guess the matrix
        "-vf", f"scale={width}:{height}:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off",
    ]
    if args.audio:
        fade_start = max(duration - 0.4, 0)
        cmd += ["-c:a", "aac", "-b:a", "192k", "-af", f"afade=t=out:st={fade_start:.3f}:d=0.4", "-map", "0:v", "-map", "1:a"]
    cmd += ["-t", f"{duration:.3f}", str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logfile)


def export_many(args) -> int:
    """Render every size in --sizes as its own process, in parallel (each process owns one browser)."""
    sizes = [parse_size(x) for x in args.sizes.split(",")]
    skip_with_value = {"--sizes", "--size", "-o", "--out", "--jobs"}
    base, it = [], iter(sys.argv[1:])
    for tok in it:
        if tok in skip_with_value:
            next(it, None)
        elif not tok.startswith(tuple(f"{f}=" for f in skip_with_value if f.startswith("--"))):
            base.append(tok)
    ext = ".png" if args.still is not None else ".mp4"
    stem = Path(args.out) if args.out else Path(args.html).with_suffix("")
    stem = stem.with_suffix("") if stem.suffix in (".mp4", ".png") else stem
    procs, failed, pending = [], 0, list(sizes)
    while pending or procs:
        while pending and len(procs) < args.jobs:
            w, h = pending.pop(0)
            target = f"{stem}_{w}x{h}{ext}"
            cmd = [sys.executable, __file__] + base + ["--size", f"{w}x{h}", "-o", target]
            procs.append((target, subprocess.Popen(cmd)))
        for item in list(procs):
            code = item[1].poll()
            if code is not None:
                procs.remove(item)
                failed += code != 0
                log(f"{'done' if code == 0 else 'FAILED'}: {item[0]}")
        time.sleep(0.3)
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="path to a local HTML file, or an http(s) URL")
    ap.add_argument("-o", "--out", help="output .mp4 (or .png with --still); default: <html stem>.mp4 next to the page")
    ap.add_argument("--size", type=parse_size, default=(1920, 1080), help="viewport WxH (default 1920x1080)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, help="seconds; default window.DURATION from the page")
    ap.add_argument("--start", type=float, default=0.0, help="start time in seconds (seek mode)")
    ap.add_argument("--still", type=float, metavar="T", help="render only the frame at T seconds to a PNG")
    ap.add_argument("--mode", choices=["auto", "seek", "clock"], default="auto")
    ap.add_argument("--fn", help="seek function name (default: first of seek/renderFrame/draw/render)")
    ap.add_argument("--audio", help="audio file to mux in (fades out over the last 0.4 s)")
    ap.add_argument("--crf", type=int, default=16, help="x264 quality, lower is better (default 16)")
    ap.add_argument("--preset", default="medium", help="x264 preset (default medium)")
    ap.add_argument("--subframes", type=int, default=1, help="average N sub-frames per frame for motion blur (seek mode only; 6 is a good value)")
    ap.add_argument("--shutter", type=float, default=0.5, help="fraction of the frame interval the sub-frames span (0.5 = 180 degree shutter)")
    ap.add_argument("--sizes", help="comma separated WxH list; renders each in parallel to <out>_WxH.mp4 (page must be responsive)")
    ap.add_argument("--jobs", type=int, default=3, help="parallel renders for --sizes (default 3)")
    ap.add_argument("--png", action="store_true", help="lossless PNG frames instead of JPEG q95 (slower)")
    ap.add_argument("--scale", type=float, default=1.0, help="device scale factor, e.g. 2 for crisper text then downscaled")
    ap.add_argument("--root", help="directory to serve (default: folder of the HTML file)")
    ap.add_argument("--browser", help="Chromium executable path or channel name (chrome, msedge)")
    ap.add_argument("--timeout", type=int, default=60, help="page load / ready timeout in seconds")
    args = ap.parse_args()
    if args.sizes:
        return export_many(args)

    from playwright.sync_api import sync_playwright
    import numpy as np
    from PIL import Image

    width, height = args.size
    server = None
    if args.html.startswith(("http://", "https://")):
        url = args.html
    else:
        src = Path(args.html).resolve()
        if not src.exists():
            raise SystemExit(f"not found: {src}")
        root = Path(args.root).resolve() if args.root else src.parent
        server, port = serve_directory(root)
        url = f"http://127.0.0.1:{port}/{src.relative_to(root).as_posix()}"
    url += ("&" if "?" in url else "?") + "capture=1"

    if args.out:
        out = Path(args.out)
    elif args.still is not None:
        out = Path(args.html).with_suffix(".png")
    else:
        out = Path(args.html).with_suffix(".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = launch_browser(pw, args.browser)

        def open_page(use_clock: bool):
            ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=args.scale)
            pg = ctx.new_page()
            pg.set_default_timeout(args.timeout * 1000)
            pg.on("pageerror", lambda e: log(f"[page error] {e}"))
            pg.on("console", lambda m: log(f"[console.{m.type}] {m.text}") if m.type in ("error", "warning") else None)
            pg.add_init_script("window.__CAPTURE__ = true;")
            install_vendor_routes(ctx)
            if use_clock:
                pg.clock.install(time=0)
                pg.clock.pause_at(1)  # frozen before any page script runs; we advance it manually
            pg.goto(url, wait_until="load")
            return ctx, pg

        names = [args.fn] if args.fn else SEEK_NAMES
        find_seek = "(ns) => ns.find(n => typeof window[n] === 'function') || null"
        seek_fn = None
        if args.mode == "clock":
            ctx, page = open_page(True)
        else:
            ctx, page = open_page(False)
            seek_fn = page.evaluate(find_seek, names)
            if args.mode == "seek" and not seek_fn:
                raise SystemExit(f"--mode seek but no window function found among {names}")
            if not seek_fn:  # no seek function: reload under the fake clock
                ctx.close()
                ctx, page = open_page(True)
        mode = "seek" if seek_fn else "clock"

        page.evaluate(READY_JS)
        if mode == "seek" and page.evaluate("'READY' in window && window.READY !== true"):  # lemo-opuscar style pages
            page.wait_for_function("window.READY === true", polling=100, timeout=args.timeout * 1000)
        duration = args.duration or page.evaluate(
            "typeof window.DURATION === 'number' ? window.DURATION : (typeof window.DUR === 'number' ? window.DUR : null)")
        if args.still is None and not duration:
            raise SystemExit("unknown duration: pass --duration or define window.DURATION in the page")
        log(f"mode={mode}" + (f" fn={seek_fn}" if seek_fn else "") + f" size={width}x{height} fps={args.fps}"
            + (f" duration={duration}s" if duration else ""))

        WARMUP_MS = 17  # one rAF interval, so frame 0 is drawn after the page's first animation callback
        fake_ms = 0     # how far the page clock has been advanced (clock mode)
        cursor = 0      # last frame index simulated (clock mode)
        if mode == "clock":
            page.clock.run_for(WARMUP_MS)
            fake_ms = WARMUP_MS
            page.evaluate(SEEK_ANIMATIONS_JS, 0)  # register existing CSS animations at t=0

        def seek_at(t: float, n: int) -> None:
            page.evaluate(f"(a) => window.{seek_fn}(a[0], a[1])", [t, n])

        def goto_frame(n: int) -> None:
            """Put the page at frame n (time n/fps). Clock mode steps frame by frame so nothing is skipped."""
            nonlocal fake_ms, cursor
            if mode == "seek":
                seek_at(n / args.fps, n)
                return
            while cursor < n:
                cursor += 1
                elapsed = round(cursor * 1000 / args.fps)
                target = WARMUP_MS + elapsed
                page.clock.run_for(target - fake_ms)
                fake_ms = target
                page.evaluate(SEEK_ANIMATIONS_JS, elapsed)

        start_frame = round(args.start * args.fps)

        shot = {"type": "png"} if (args.png or args.still is not None) else {"type": "jpeg", "quality": 95}

        if args.still is not None:
            goto_frame(round(args.still * args.fps))
            page.screenshot(path=str(out), type="png")
            log(f"wrote {out}")
        else:
            total = round(duration * args.fps)
            logfile = tempfile.TemporaryFile()
            ff = start_ffmpeg(args, width, height, duration, out, logfile)
            began = time.time()
            try:
                def grab() -> "np.ndarray":
                    return np.asarray(Image.open(io.BytesIO(page.screenshot(**shot))).convert("RGB"))

                sub = args.subframes
                if sub > 1 and mode != "seek":
                    log("note: --subframes needs seek mode (clock mode updates the page once per ~16 ms); ignoring")
                    sub = 1
                for i in range(total):
                    f = start_frame + i
                    if sub == 1:
                        goto_frame(f)
                        frame = grab()
                    else:
                        acc = None
                        for k in range(sub):
                            seek_at((f + k / sub * args.shutter) / args.fps, f)
                            part = grab().astype(np.float32)
                            acc = part if acc is None else acc + part
                        frame = (acc / sub + 0.5).astype(np.uint8)
                    ff.stdin.write(frame.tobytes())
                    if i % max(total // 10, 1) == 0:
                        log(f"  frame {i}/{total} ({time.time() - began:.0f}s)")
                ff.stdin.close()
                code = ff.wait()
            except BrokenPipeError:
                code = ff.wait()
            finally:
                browser.close()
            if code != 0:
                logfile.seek(0)
                raise SystemExit(f"ffmpeg failed ({code}): {logfile.read().decode(errors='replace')[-800:]}")
            log(f"wrote {out} ({total} frames, {time.time() - began:.0f}s)")
            print(str(out))
            if server:
                server.shutdown()
            return 0

        browser.close()
    if server:
        server.shutdown()
    print(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
