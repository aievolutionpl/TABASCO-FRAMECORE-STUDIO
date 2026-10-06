"""Build the editable Motion 2.0 demos, export them and refresh README previews.

    python scripts/render-showcase.py              # showreel 16:9 + rolka 9:16
    python scripts/render-showcase.py showreel     # jeden film

Writes assets/<name>.mp4, an animated GIF preview, a poster and a frame sheet.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image

from framecore.showcase import SHOWCASES, export
from framecore.store import Store

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def previews(video, stem, vertical, sheet_times):
    gif = ASSETS / f"{stem}.gif"
    width = 300 if vertical else 640
    palette = f"fps=12,scale={width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-filter_complex", palette, "-loop", "0", str(gif)], check=True)
    poster = ASSETS / f"{stem}-poster.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(sheet_times[1]), "-i", str(video), "-frames:v", "1", "-q:v", "3", str(poster)], check=True)
    frames = []
    for i, t in enumerate(sheet_times):
        target = ASSETS / f".{stem}-{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-q:v", "3", str(target)], check=True)
        frames.append(Image.open(target).convert("RGB")); target.unlink()
    w = 270 if vertical else 480
    h = round(w * frames[0].height / frames[0].width)
    cols = len(frames) if vertical else 3
    sheet = Image.new("RGB", (w * cols, h * ((len(frames) + cols - 1) // cols)), "#07090b")
    for i, frame in enumerate(frames):
        sheet.paste(frame.resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
    sheet.save(ASSETS / f"{stem}-frames.jpg", quality=86)
    print(f"Saved {gif.name} ({gif.stat().st_size // 1024} KB), {poster.name}, {stem}-frames.jpg", flush=True)


SHEETS = {"showreel": [1.8, 3.2, 5.6, 7.4, 11.0, 14.2, 18.2, 21.6, 23.0], "reel": [1.0, 2.6, 5.2, 7.0, 10.0, 11.5]}

if __name__ == "__main__":
    names = sys.argv[1:] or list(SHOWCASES)
    store = Store()
    for name in names:
        create, stem = SHOWCASES[name]
        state = create(store)
        print(f"{name}: project {state['project']['id']} rev {state['project']['revision']}", flush=True)
        target = ASSETS / f"{stem}.mp4"
        job = export(store, state, target)
        print(f"Saved {target.relative_to(ROOT)} ({job['duration']:.1f} s)", flush=True)
        previews(target, stem, state["project"]["canvas"]["height"] > state["project"]["canvas"]["width"], SHEETS[name])
