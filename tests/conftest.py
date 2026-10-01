"""Wspólne fixture'y: izolowane studio w katalogu tymczasowym, żeby testy nigdy nie dotykały prawdziwego output/ ani .mcp.json."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _playwright_browsers_dir() -> Path | None:
    """Gdzie Playwright trzyma przeglądarki w prawdziwym HOME (testy podmieniają HOME, więc bez tego nie znalazłby Chromium)."""
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return None
    home = Path.home()
    if os.name == "nt":
        return home / "AppData" / "Local" / "ms-playwright"
    if sys.platform == "darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """Puste studio: OUTPUT, STATE_DIR i ROOT wskazują na tmp_path; tryb usługowy włączony (błędy jako wyjątki)."""
    from vstudio import agentkit, common, doctor, project, workspace
    from vstudio.dashboard import server

    out = tmp_path / "output"
    out.mkdir()
    for mod in (common, project, workspace, doctor, server):
        monkeypatch.setattr(mod, "OUTPUT", out)
    monkeypatch.setattr(common, "STATE_DIR", out / ".studio")
    monkeypatch.setattr(common, "SERVICE_MODE", True)
    monkeypatch.setattr(project, "ROOT", tmp_path)
    monkeypatch.setattr(agentkit, "ROOT", tmp_path)
    browsers = _playwright_browsers_dir()
    if browsers is not None and browsers.is_dir():
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    return out


@pytest.fixture(scope="session")
def gsap_js() -> Path:
    """GSAP 3.12.5 do testów przeglądarkowych: z GSAP_JS (plik) albo pominięcie testu."""
    p = os.environ.get("GSAP_JS")
    if p and Path(p).is_file():
        return Path(p)
    pytest.skip("ustaw GSAP_JS=/ścieżka/gsap.min.js (GSAP 3.12.5), żeby uruchomić testy przeglądarkowe")


@pytest.fixture
def vendored_studio(studio, gsap_js):
    """Studio z lokalną kopią GSAP w vendorze: szablony działają offline."""
    from vstudio import vendor

    vendor.add("gsap", file=str(gsap_js))
    return studio
