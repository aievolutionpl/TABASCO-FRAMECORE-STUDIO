"""Napisy słowo po słowie: z tekstu lektora, SRT, VTT albo znaczników słów (np. z transkrypcji) do danych dla silnika `VS.captions`.

Formaty rolek (mówiąca głowa, polecajka narzędzia) stoją na napisach, które pojawiają się razem z głosem: jedno słowo albo trzy, wielkie,
z podświetlonym słowem kluczowym. Tu powstają dane (linie i czasy słów), a rysuje je `templates/motion-kit.js`, więc wynik jest czystą
funkcją czasu i renderuje się deterministycznie.

Czasy słów: gdy nie ma znaczników, rozkładamy je proporcjonalnie do długości słowa i przerw na interpunkcji (przecinek, kropka). To
przybliżenie. Dokładne napisy daje transkrypcja ze znacznikami słów (`words`) albo SRT/VTT z narzędzia, którego używasz do montażu.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from . import assets
from .common import STUDIO, StudioError

STYLES = ("single", "pop", "karaoke")
MIN_WORD = 0.2                                      # w stylu `single` krótsze słowa łączymy z następnym (inaczej migają)
_PAUSE = {",": 2.5, ";": 2.5, ":": 2.5, "—": 2.5, "-": 0.0, ".": 5.0, "?": 5.0, "!": 5.0, "…": 5.0}
_SENTENCE_END = (".", "?", "!", "…")
_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _clean(word: str) -> str:
    return re.sub(r"[^\w]", "", _fold(word))


def _seconds(m: re.Match) -> float:
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_cues(text: str) -> list[tuple[float, float, str]]:
    """Wskazówki czasowe z SRT albo VTT: [(początek, koniec, tekst)]."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        for i, ln in enumerate(lines):
            if "-->" in ln:
                a, b = (x.strip().split(" ")[0] for x in ln.split("-->", 1))
                ma, mb = _TIME.fullmatch(a), _TIME.fullmatch(b)
                if not (ma and mb):
                    raise StudioError(f"nie rozumiem czasu w linii '{ln.strip()[:60]}' (oczekuję 00:00:01,000 --> 00:00:03,500)")
                body = re.sub(r"<[^>]+>", "", " ".join(lines[i + 1:])).strip()
                if body:
                    cues.append((_seconds(ma), _seconds(mb), body))
                break
    if not cues:
        raise StudioError("brak napisów w SRT/VTT (oczekuję bloków z linią 'początek --> koniec')")
    return cues


def _weight(word: str) -> float:
    letters = len(re.sub(r"[^\w]", "", word))
    return max(letters, 1) + 1.0 + _PAUSE.get(word[-1:], 0.0)


def spread(words: list[str], t0: float, t1: float) -> list[dict]:
    """Rozkłada słowa na odcinku [t0, t1] proporcjonalnie do długości i przerw na interpunkcji."""
    if t1 <= t0:
        raise StudioError("koniec napisów musi być po początku")
    total = sum(_weight(w) for w in words)
    out, t = [], t0
    for w in words:
        d = (t1 - t0) * _weight(w) / total
        out.append({"t0": round(t, 3), "t1": round(t + d, 3), "w": w})
        t += d
    return out


def words_from_text(text: str, start: float, end: float | None, wpm: float) -> list[dict]:
    words = text.split()
    if not words:
        raise StudioError("pusty tekst napisów")
    if end is None:
        end = start + len(words) * 60.0 / wpm
    return spread(words, start, end)


def words_from_cues(cues: list[tuple[float, float, str]]) -> list[dict]:
    out: list[dict] = []
    for a, b, body in cues:
        out += spread(body.split(), a, b)
    return out


def _normalise_words(raw: list) -> list[dict]:
    out = []
    for i, w in enumerate(raw):
        if not isinstance(w, dict):
            raise StudioError(f"words[{i}] ma być obiektem {{t0, t1, w}}")
        text = str(w.get("w", w.get("text", w.get("word", "")))).strip()
        t0, t1 = w.get("t0", w.get("start")), w.get("t1", w.get("end"))
        if not text or not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)) or t1 < t0:
            raise StudioError(f"words[{i}]: potrzebne t0 <= t1 (liczby) i niepusty tekst")
        out.append({"t0": round(float(t0), 3), "t1": round(float(t1), 3), "w": text})
    if not out:
        raise StudioError("pusta lista words")
    return sorted(out, key=lambda x: x["t0"])


def group(words: list[dict], max_words: int, style: str) -> list[dict]:
    """Linie napisów: do `max_words` słów, a po końcu zdania zawsze nowa linia.

    W stylu `single` słowo krótsze niż MIN_WORD (np. „w”, „a”) łączymy z następnym w parę, bo inaczej mignęłoby na ułamek sekundy.
    """
    cap = max(max_words, 2) if style == "single" else max_words
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        dur = (words[i + 1]["t0"] if i + 1 < len(words) else w["t1"]) - cur[0]["t0"]
        enough = len(cur) >= max_words and (style != "single" or dur >= MIN_WORD)
        if w["w"].endswith(_SENTENCE_END) or len(cur) >= cap or enough:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return [{"t0": ln[0]["t0"], "t1": ln[-1]["t1"], "words": ln} for ln in lines]


def build(*, text: str | None = None, srt: str | None = None, words: list | None = None, start: float = 0.0, end: float | None = None,
          wpm: float = 150.0, max_words: int | None = None, style: str = "single", highlight: list[str] | None = None, numbers: bool = True) -> dict:
    """Dane napisów z jednego źródła: `text` (czasy szacowane), `srt` (SRT lub VTT) albo `words` (znaczniki słów)."""
    if style not in STYLES:
        raise StudioError(f"style: {', '.join(STYLES)}")
    given = [x for x in (text, srt, words) if x]
    if len(given) != 1:
        raise StudioError("podaj dokładnie jedno źródło napisów: text, srt albo words")
    if not 40 <= wpm <= 400:
        raise StudioError("wpm: 40-400 słów na minutę")
    if text:
        ws = words_from_text(text, float(start), None if end is None else float(end), float(wpm))
    elif srt:
        ws = words_from_cues(parse_cues(srt))
        ws = [{**w, "t0": round(w["t0"] + float(start), 3), "t1": round(w["t1"] + float(start), 3)} for w in ws]
    else:
        ws = _normalise_words(words)
    n = max_words or (1 if style == "single" else 3)
    if not 1 <= n <= 6:
        raise StudioError("max_words: 1-6")
    hl = {_clean(h) for h in (highlight or []) if _clean(h)}
    for w in ws:
        w["hl"] = bool(_clean(w["w"]) in hl or (numbers and re.search(r"\d", w["w"])))
    lines = group(ws, n, style)
    return {"style": style, "start": lines[0]["t0"], "end": lines[-1]["t1"], "words": len(ws), "max_words": n, "lines": lines}


def _kit() -> str:
    f = STUDIO / "templates" / "motion-kit.js"
    return f.read_text(encoding="utf-8")


def install_kit(pdir: Path) -> dict:
    """Zapisuje templates/motion-kit.js jako src/assets/motion-kit.js (z wpisem w śladzie assetów)."""
    d = assets._dir(pdir)
    text = _kit()
    (d / "motion-kit.js").write_text(text, encoding="utf-8")
    assets._record(pdir, "motion-kit.js", text.encode("utf-8"), origin="generated", kind="script", source="templates/motion-kit.js", license="original (vstudio)")
    return {"file": "motion-kit.js", "rel": "assets/motion-kit.js"}


KIT_USAGE = """\
Include once, before your scene script:  <script src="assets/motion-kit.js"></script>
Springs for GSAP:   gsap.to(el, { y: 0, duration: VS.springDuration(170, 16), ease: VS.spring(170, 16) })      // k, damping, mass
Strong curves:      ease: VS.ease.out | VS.ease.inOut | VS.ease.soft | VS.ease.snap   (or VS.bezier(x1, y1, x2, y2))
From t directly:    VS.count(t, t0, t1, from, to)   VS.type(text, t, t0, cps)   VS.blink(t, hz)   (no timers, no randomness)
Physical feel: ease-out on entrances (fast start, soft landing), a spring only on one hero element per beat, start scale at .8-.95 never 0,
stagger 0.04-0.09 s, exits shorter than entrances."""


def snippet(selector: str = "#cap", style: str = "single") -> str:
    return (f'<div id="cap" style="top:46%"></div>   <!-- position: the seam between footage and cards (safe zone: 10%-80% of the height) -->\n'
            '<script src="assets/motion-kit.js"></script>\n<script src="assets/captions.js"></script>\n<script>\n'
            f"  VS.captions.mount(document.querySelector('{selector}'), window.CAPTIONS, {{ style: '{style}' }});\n"
            "  // inside window.seek(t):   VS.captions.draw(t);\n"
            "  // inside window.TEXTS(t):  append VS.captions.texts(t) to the array you return\n"
            "  // look: CSS variables --cap-font, --cap-size (9vw), --cap-color, --cap-hl (highlight), --cap-case (uppercase | none)\n</script>")


def write(pdir: Path, data: dict) -> dict:
    """Zapisuje dane napisów i silnik w src/assets/ i zwraca kod do wklejenia w scenę."""
    d = assets._dir(pdir)
    body = ("/* vstudio captions: wygenerowane przez captions_build. Popraw tekst i czasy tutaj albo uruchom narzędzie jeszcze raz. */\n"
            f"window.CAPTIONS = {json.dumps(data, ensure_ascii=False)};\n")
    (d / "captions.js").write_text(body, encoding="utf-8")
    assets._record(pdir, "captions.js", body.encode("utf-8"), origin="generated", kind="script", source=f"captions style={data['style']}", license="original (vstudio)")
    install_kit(pdir)
    return {"file": "captions.js", "rel": "assets/captions.js", "kit": "assets/motion-kit.js", "snippet": snippet(style=data["style"])}
