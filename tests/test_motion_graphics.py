"""Testy sześciu pętli motion graphics z examples/motion-graphics (GSAP 3.12.5, 1080x1350, 7 s).

Część statyczna nie wymaga przeglądarki. Część `browser` ładuje strony w Chromium (Playwright); GSAP bierze z pliku
wskazanego w GSAP_JS albo z CDN (adres z promptów) - gdy żadne z tych nie działa, testy są pomijane.
"""
from __future__ import annotations

import io
import os
import random
import re
import urllib.request
from pathlib import Path

import pytest

DIR = Path(__file__).resolve().parents[1] / "examples" / "motion-graphics"
CDN = "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"
FILES = sorted(DIR.glob("0[1-6]-*.html"))
BIG = 32                     # różnica piksela (0-255), od której uznajemy, że to nie szum rastra
BIG_FRACTION = 2e-4          # dopuszczalny udział takich pikseli w kadrze
NO_LOOP = {"03-three-colours-only.html"}   # prompt: twardy reset do 9 kolorów o 7 s (przełącznik przed/po)
CHROMIUM_ARGS = ["--disable-gpu-rasterization", "--disable-partial-raster", "--hide-scrollbars",
                 "--force-color-profile=srgb", "--disable-lcd-text", "--font-render-hinting=none"]


def test_six_files_present():
    assert [f.name[:2] for f in FILES] == ["01", "02", "03", "04", "05", "06"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
class TestStatic:
    def test_single_file_with_only_the_gsap_cdn(self, path):
        html = path.read_text(encoding="utf-8")
        assert html.count(f'<script src="{CDN}"></script>') == 1
        external = re.findall(r'(?:src|href)\s*=\s*["\'](https?:[^"\']+)', html)
        assert external == [CDN]

    def test_canvas_timeline_and_loop(self, path):
        html = path.read_text(encoding="utf-8")
        assert "width: 1080px; height: 1350px" in html
        assert "var DUR = 7" in html
        assert "repeat: -1" in html
        assert "gsap.timeline(" in html and html.count("gsap.timeline(") == 1    # jedna oś czasu
        assert "tl.set({}, {}, DUR)" in html                                     # oś trwa dokładnie 7 s

    def test_vstudio_page_contract(self, path):
        html = path.read_text(encoding="utf-8")
        for hook in ("window.DURATION = DUR", "window.seek = ", "window.EV = ", "window.TEXTS = ", "window.__ready = ", "window.__CAPTURE__"):
            assert hook in html, hook

    def test_prompt_and_determinism_rules(self, path):
        html = path.read_text(encoding="utf-8")
        code = re.sub(r"<!--.*?-->|/\*.*?\*/", "", html, flags=re.S)             # komentarze mogą opisywać zakazy
        assert "translate(-50%" not in code        # prompt: GSAP animuje transform, wyśrodkowanie tylko flexboxem / left,top
        for banned in ("Math.random", "setTimeout", "setInterval", "yoyo", "requestAnimationFrame", "onUpdate", ".call("):
            assert banned not in code, banned
        assert "gsap.config({ force3D: false })" in code
        assert ".set(" in code                      # stany startowe w czasie 0 osi


def _gsap_source() -> bytes | None:
    local = os.environ.get("GSAP_JS")
    if local and Path(local).is_file():
        return Path(local).read_bytes()
    try:
        with urllib.request.urlopen(CDN, timeout=10) as r:
            return r.read()
    except Exception:  # noqa: BLE001 - brak sieci: pomijamy testy przeglądarkowe
        return None


@pytest.fixture(scope="module")
def browser_page():
    pytest.importorskip("playwright.sync_api")
    gsap_js = _gsap_source()
    if gsap_js is None:
        pytest.skip("brak GSAP 3.12.5 (ustaw GSAP_JS=/ścieżka/gsap.min.js albo zapewnij dostęp do cdnjs)")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            br = pw.chromium.launch(args=CHROMIUM_ARGS)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"brak Chromium: {exc}")

        def open_page(path: Path):
            ctx = br.new_context(viewport={"width": 540, "height": 675})         # połowa skali: szybciej, strona skaluje się sama
            page = ctx.new_page()
            problems: list[str] = []
            page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
            page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.route("**/gsap.min.js", lambda r: r.fulfill(body=gsap_js, content_type="application/javascript"))
            page.add_init_script("window.__CAPTURE__ = true;")
            page.goto(path.resolve().as_uri(), wait_until="load")
            page.evaluate("async () => { await window.__ready; }")
            return page, problems

        yield open_page
        br.close()


def _same(a, b) -> tuple[bool, str]:
    """Ta sama klatka z dokładnością do szumu rastra Chromium.

    Po skoku wstecz rasteryzator potrafi dać przy identycznym DOM różnice do ~16/255 na gradientach (świeży, sekwencyjny
    dojazd - tak renderuje html_to_video.py - jest bit w bit powtarzalny). Błąd logiki animacji (zły stan elementu)
    daje różnice rzędu 100-250/255 na tysiącach pikseli, więc liczymy udział pikseli różniących się o > BIG.
    """
    import numpy as np

    d = np.abs(a - b).max(axis=2)
    frac = float((d > BIG).mean())
    return frac <= BIG_FRACTION, f"{frac:.4%} pikseli różni się o > {BIG}/255 (max {int(d.max())})"


def _frame(page, t: float):
    import numpy as np
    from PIL import Image

    page.evaluate("(t) => window.seek(t)", t)
    return np.asarray(Image.open(io.BytesIO(page.screenshot())).convert("RGB"), dtype=np.int16)


@pytest.mark.browser
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
class TestInBrowser:
    def test_loads_clean_and_exposes_contract(self, browser_page, path):
        page, problems = browser_page(path)
        assert problems == []
        assert page.evaluate("window.DURATION") == 7
        assert isinstance(page.evaluate("window.EV"), list) and page.evaluate("window.EV")
        for t in (0.0, 1.0, 3.5, 6.9):
            page.evaluate("(t) => window.seek(t)", t)
            for box in page.evaluate("(t) => window.TEXTS(t)", t):
                assert {"id", "text", "x0", "y0", "x1", "y1"} <= set(box)
                assert box["x1"] > box["x0"] and box["y1"] > box["y0"]

    def test_frame_is_a_pure_function_of_time(self, browser_page, path):
        """Ten sam czas daje ten sam obraz niezależnie od kolejności seek (w tym skoki wstecz)."""
        page, _ = browser_page(path)
        times = [round(i * 0.35, 2) for i in range(20)]
        ref = {t: _frame(page, t) for t in times}
        order = times[:]
        random.Random(11).shuffle(order)
        for t in order:
            ok, info = _same(_frame(page, t), ref[t])
            assert ok, f"t={t}: obraz zależy od historii seek ({info})"

    def test_loop_closes(self, browser_page, path):
        """Ostatnia klatka ≈ pierwsza (pętla szczelna); plik 3 to przełącznik przed/po z twardym resetem."""
        import numpy as np

        page, _ = browser_page(path)
        first, last = _frame(page, 0.0), _frame(page, 7 - 1 / 30)
        mean = float(np.abs(first - last).mean())
        if path.name in NO_LOOP:
            assert mean > 10, "plik 3 ma resetować się twardo do 9 kolorów"
        else:
            assert mean < 1.0, f"pętla nieszczelna: średnia różnica {mean:.2f}"

    def test_seek_wraps_around_the_loop(self, browser_page, path):
        page, _ = browser_page(path)
        ok, info = _same(_frame(page, 2.4), _frame(page, 2.4 + 7))
        assert ok, info
