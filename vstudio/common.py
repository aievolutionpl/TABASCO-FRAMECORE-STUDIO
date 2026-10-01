"""Shared helpers: paths, subprocess, ffprobe, browser discovery, project state, contact sheets."""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(__file__).resolve().parent
STUDIO = PKG.parent                      # katalog projektu (repo albo projects/video-studio)
VENDOR = PKG / "renderers"               # renderery dołączone do pakietu (self-contained)
_ws = STUDIO.parent if STUDIO.parent.name == "projects" else None   # <workspace>/projects
SCRIPTS = VENDOR if (VENDOR / "html_to_video.py").exists() else (_ws.parent / "scripts" if _ws else STUDIO / "scripts")
ROOT = _ws.parent if _ws else STUDIO     # korzeń workspace albo korzeń repo
OUTPUT = ROOT / "output"
STATE_DIR = OUTPUT / ".studio"            # profil marki, aktywność agenta, joby, vendor (poza projektami; output/ jest w .gitignore)

GATES = ["brief", "reference_spec", "visual_rules", "stills", "draft", "sound", "critic", "final"]
ENGINES = ("html", "hyperframes", "remotion")


def log(msg: str = "") -> None:
    print(msg, file=sys.stderr, flush=True)


class StudioError(Exception):
    """Błąd operacji w trybie usługowym (MCP / dashboard): serwer nie może się zamknąć, więc die() rzuca wyjątek."""


#: ustawiane przez `vstudio mcp` i `vstudio dashboard`; w zwykłym CLI die() kończy proces jak dotąd
SERVICE_MODE = False


def die(msg: str, code: int = 1):
    if SERVICE_MODE:
        raise StudioError(msg)
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def today() -> str:
    return datetime.date.today().isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "untitled"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True,
        capture: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    cp = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=full_env, text=True,
                        encoding="utf-8", errors="replace", capture_output=capture, timeout=timeout)
    if check and cp.returncode != 0:
        tail = ((cp.stderr or "") + (cp.stdout or ""))[-1200:]
        die(f"command failed ({cp.returncode}): {' '.join(str(c) for c in cmd[:6])} ...\n{tail}")
    return cp


def need(tool: str) -> str:
    p = shutil.which(tool)
    if not p:
        die(f"{tool} not found on PATH")
    return p


def ffprobe(path: Path) -> dict:
    need("ffprobe")
    cp = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    d = json.loads(cp.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    fps = 0.0
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        n, dn = v["avg_frame_rate"].split("/")
        fps = int(n) / int(dn) if int(dn) else 0.0
    return {
        "duration": float(d["format"].get("duration", 0)),
        "width": v["width"] if v else None, "height": v["height"] if v else None, "fps": fps,
        "has_video": v is not None, "has_audio": a is not None,
        "frames": int(v["nb_frames"]) if v and str(v.get("nb_frames", "")).isdigit() else None,
        "size_mb": round(int(d["format"].get("size", 0)) / 1e6, 2),
    }


def find_chrome() -> str | None:
    """System Chrome / Edge path (used for Remotion's --browser-executable)."""
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(p):
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    pw = glob.glob(os.path.expanduser("~/AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe"))
    return sorted(pw)[-1] if pw else None


def npx(args: list[str], cwd: Path | None = None, env: dict | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    exe = "npx.cmd" if os.name == "nt" else "npx"
    e = {"HYPERFRAMES_SKIP_SKILLS": "1", "DO_NOT_TRACK": "1", **(env or {})}
    return run([exe, "--yes", *args], cwd=cwd, env=e, check=False, timeout=timeout)


# ---------- project state ----------

def project_file(pdir: Path) -> Path:
    return pdir / "project.json"


def load_project(pdir: str | Path) -> tuple[Path, dict]:
    p = Path(pdir)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    f = project_file(p)
    if not f.exists():
        die(f"not a vstudio project (no project.json): {p}")
    return p, json.loads(f.read_text(encoding="utf-8"))


def save_project(pdir: Path, data: dict) -> None:
    project_file(pdir).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_log(pdir: Path, line: str) -> None:
    with open(pdir / "LOG.md", "a", encoding="utf-8") as fh:
        fh.write(f"- {datetime.datetime.now():%Y-%m-%d %H:%M} {line}\n")


# ---------- images ----------

def image_sheet(paths: list[Path], labels: list[str], out: Path, cols: int = 4, tile_w: int = 480) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=max(tile_w // 24, 12))
    except TypeError:
        font = ImageFont.load_default()
    tiles = []
    for p, lab in zip(paths, labels):
        im = Image.open(p).convert("RGB")
        im = im.resize((tile_w, round(im.height * tile_w / im.width)))
        d = ImageDraw.Draw(im, "RGBA")
        tw = d.textlength(lab, font=font)
        fs = getattr(font, "size", 14)
        d.rectangle([4, im.height - fs - 12, tw + 14, im.height - 4], fill=(0, 0, 0, 170))
        d.text((9, im.height - fs - 9), lab, fill=(255, 255, 255, 255), font=font)
        tiles.append(im)
    if not tiles:
        die("no images for contact sheet")
    th, gap = tiles[0].height, 6
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * gap, rows * th + (rows + 1) * gap), (24, 24, 24))
    for i, im in enumerate(tiles):
        sheet.paste(im, (gap + (i % cols) * (tile_w + gap), gap + (i // cols) * (th + gap)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90) if out.suffix.lower() in (".jpg", ".jpeg") else sheet.save(out)
    return out


def grab_frame(video: Path, t: float, out: Path, width: int | None = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", video, "-frames:v", "1"]
    chain = [f"scale={width}:-2"] if width else []
    if out.suffix.lower() in (".jpg", ".jpeg"):
        chain.append("format=yuvj420p")  # MJPEG needs full-range input; this converts from limited-range video
    if chain:
        cmd += ["-vf", ",".join(chain)]
    run(cmd + [out])
    return out


def emit(obj, as_json: bool, text: str | None = None) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    elif text is not None:
        print(text)


class Timer:
    def __init__(self):
        self.t0 = time.time()

    def s(self) -> str:
        return f"{time.time() - self.t0:.1f}s"
