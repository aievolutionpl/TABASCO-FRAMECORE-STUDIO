"""`vstudio doctor`: sprawdzenie środowiska. Pierwsza komenda w nowej sesji.

Rozróżnia twarde braki (kod wyjścia 2, bez tego nic nie zadziała) od ostrzeżeń (działa, ale
jakaś ścieżka/silnik będzie niedostępny).
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .common import OUTPUT, ROOT, SCRIPTS, STUDIO, find_chrome, log

#: twarde zależności: bez nich pipeline nie ruszy
REQUIRED_MODULES = ("numpy", "PIL", "playwright")


def _which(name: str) -> str | None:
    return shutil.which(name) or shutil.which(name + ".cmd")


def _playwright_chromium() -> str | None:
    for pat in (os.path.expanduser("~/AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe"),
                os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
                os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def check() -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "", level: str = "fail") -> None:
        checks.append({"check": name, "ok": bool(ok), "level": level, "detail": detail})

    add("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
    for tool in ("ffmpeg", "ffprobe"):
        p = _which(tool)
        add(tool, bool(p), p or "brak na PATH")
    has_loudnorm = False
    if _which("ffmpeg"):
        cp = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
        has_loudnorm = "loudnorm" in (cp.stdout or "")
    add("ffmpeg loudnorm", has_loudnorm, "mastering dwuprzebiegowy -14 LUFS" if has_loudnorm else "brak filtra loudnorm")
    for mod in REQUIRED_MODULES:
        spec = importlib.util.find_spec(mod)
        ver = ""
        if spec:
            try:
                ver = str(getattr(__import__(mod), "__version__", "") or "")
            except Exception as exc:  # pragma: no cover - środowiskowe
                ver = f"błąd importu: {exc}"
        add(mod, bool(spec), ver)
    chrome = find_chrome()
    add("chromium (playwright/chrome)", bool(chrome), chrome or "uruchom: py -3 -m playwright install chromium")
    for f in ("html_to_video.py", "video_qa.py"):
        add(f"renderery/{f}", (SCRIPTS / f).exists(), str(SCRIPTS / f))
    add("starter html-video-starter.html", _starter().exists(), str(_starter()))
    for f in ("BRIEF.md", "VISUAL_RULES.md", "MOTION_RULES.md"):
        add(f"templates/{f}", (STUDIO / "templates" / f).exists())
    agents = ROOT / "Agents"
    n_brands = len(list(agents.glob("*/CONFIG.md"))) if agents.exists() else 0
    add("brand configs (Agents/*/CONFIG.md)", n_brands > 0, f"{n_brands} plików", "warn")
    add("npx (remotion / hyperframes)", bool(_which("npx")), _which("npx") or "brak - silnik html działa bez tego", "warn")
    add("output/", OUTPUT.exists(), str(OUTPUT), "warn")
    return checks


def _starter() -> Path:
    return ROOT / "Skills" / "remotion-video-creator" / "templates" / "html-video-starter.html"


def report(json_out: bool = False) -> bool:
    checks = check()
    ok = all(c["ok"] for c in checks if c["level"] == "fail")
    if json_out:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
        return ok
    print("vstudio doctor")
    for c in checks:
        mark = "OK  " if c["ok"] else ("BLAD" if c["level"] == "fail" else "WARN")
        print(f"  [{mark}] {c['check']:<36} {c['detail']}")
    bad = [c for c in checks if not c["ok"] and c["level"] == "fail"]
    warn = [c for c in checks if not c["ok"] and c["level"] == "warn"]
    print()
    print("środowisko gotowe" if ok else f"{len(bad)} twardych braków: " + ", ".join(c["check"] for c in bad))
    if warn:
        print(f"ostrzeżenia ({len(warn)}): " + ", ".join(c["check"] for c in warn))
    return ok
