#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
python_bin="${FRAMECORE_PYTHON:-python3}"
"$python_bin" -c 'import sys; assert sys.version_info >= (3,11), "Wymagany Python 3.11+"'
for command in ffmpeg ffprobe; do
  if ! command -v "$command" >/dev/null; then
    echo "Brak $command. Zainstaluj FFmpeg: macOS — brew install ffmpeg; Ubuntu — sudo apt install ffmpeg."
    exit 1
  fi
done
if [ ! -x .venv/bin/python ]; then "$python_bin" -m venv .venv; fi
if ! .venv/bin/python -c 'import PIL, numpy, playwright, pytest' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt pytest
fi
if ! command -v chromium >/dev/null && ! .venv/bin/python -c 'from playwright.sync_api import sync_playwright; from pathlib import Path; p=sync_playwright().start(); assert Path(p.chromium.executable_path).is_file(); p.stop()' 2>/dev/null; then
  .venv/bin/python -m playwright install chromium
fi
.venv/bin/python -c 'from framecore.model import project; from framecore.composition import compile_project; assert "framecore" in compile_project(project())'
echo "Studio przygotowane. Uruchom: .venv/bin/python framecore.py editor"
