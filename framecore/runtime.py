"""Readable startup diagnostics for both humans and agents."""
import importlib.util
import os
import shutil
from pathlib import Path

def diagnostics():
    browser = False
    if importlib.util.find_spec('playwright'):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw: browser = Path(pw.chromium.executable_path).exists()
        except Exception: pass
    # Playwright's executable_path points to full Chrome even when only-shell
    # was installed. Recognize the officially downloaded headless package too.
    browser_root = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if browser_root and browser_root != '0':
        base = Path(browser_root)
        browser = browser or any(path.is_file() for name in
            ('chrome-headless-shell', 'chrome-headless-shell.exe', 'headless_shell', 'headless_shell.exe')
            for path in base.glob('chromium_headless_shell-*/*/' + name))
    checks = [
        {'id':'ffmpeg','label':'Eksport obrazu i dźwięku','ok':bool(shutil.which('ffmpeg')),'fix':'Zainstaluj FFmpeg i dodaj go do PATH.'},
        {'id':'ffprobe','label':'Odczyt plików multimedialnych','ok':bool(shutil.which('ffprobe')),'fix':'Zainstaluj FFprobe razem z FFmpeg.'},
        {'id':'chromium','label':'Renderowanie animacji','ok':browser or bool(shutil.which('chromium')),'fix':'Uruchom: python -m playwright install chromium.'},
    ]
    return {'checks':checks,'ready':all(c['ok'] for c in checks),'editor_ready':True,
            'quickstart':['get_editing_guide','get_project','get_selection','list_assets','list_templates','list_motion','inspect_project'],
            'workflow':'Odczytaj projekt i katalogi; zaplanuj sceny; zastosuj zmiany z expected_revision; obejrzyj capture_frame; dopiero potem export i get_job.'}
