"""Assety dla filmów: ikony, grafiki generowane i obrazy z internetu, wszystkie lokalnie, z licencją i bez ryzyka.

Film jest lepszy, gdy obok tekstu ma ikony, naklejki i drobne obrazki. Skąd je brać:

  1. wbudowane ikony SVG (offline, własne): `builtin:<id>`,
  2. generatory (blob, mesh, wzory, konfetti, ...): deterministyczne z ziarna, w kolorach marki,
  3. internet: Iconify (ikony, licencja sprawdzana po stronie API) i Openverse (zdjęcia CC0/PDM/CC-BY),
     albo dowolny https URL.

Wszystko ląduje w `src/assets/` projektu (strona widzi to jako `assets/<plik>`), a ślad pochodzenia w `src/assets/ASSETS.json`
(źródło, licencja, autor, hash). `credits()` składa z tego sekcję „Credits” do DELIVERY.md.

Bezpieczeństwo pobierania (agent może dostać adres od kogoś, kto próbuje go namówić na zapytanie do sieci wewnętrznej):
tylko https na porcie 443, odrzucamy adresy nieglobalne (loopback, sieci prywatne, link-local, metadane chmury), każdy
przekierowanie jest sprawdzane od nowa, połączenie idzie na sprawdzony adres IP (bez proxy), limity rozmiaru i czasu,
typ pliku weryfikujemy po zawartości, SVG przechodzi przez czarną i białą listę (bez skryptów, bez zewnętrznych odwołań),
a obraz rastrowy jest ponownie kodowany (bez metadanych, zmniejszony).
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import StudioError

MAX_SVG = 300_000
MAX_RASTER = 6_000_000
MAX_PIXELS = 40_000_000
MAX_SIDE = 1600
TIMEOUT = 15
USER_AGENT = "vstudio-assets/1.0 (+local video studio)"
OK_LICENSES = {"MIT", "ISC", "Apache-2.0", "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "OFL-1.1", "Unlicense", "0BSD", "BSD-3-Clause", "BSD-2-Clause", "CC-PDM-1.0"}
ATTRIBUTION_LICENSES = {"CC-BY-4.0", "CC-BY-3.0", "by"}          # wymagają wskazania autora w creditsach
ICONIFY_PREFIXES = "lucide,tabler,ph,heroicons,mdi,fluent-emoji-flat,noto,twemoji"
OPENVERSE_LICENSES = "cc0,pdm,by"

# ------------------------------------------------------------------ ikony wbudowane (24x24, kreska currentColor)

ICONS: dict[str, tuple[str, str]] = {
    "check": ("ok tick done yes zrobione gotowe potwierdzenie", '<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    "x": ("close no cancel zamknij nie anuluj", '<path d="M6 6l12 12M18 6L6 18"/>'),
    "plus": ("add new more dodaj nowy", '<path d="M12 5v14M5 12h14"/>'),
    "arrow-right": ("next go dalej strzałka kierunek", '<path d="M5 12h14M13 6l6 6-6 6"/>'),
    "arrow-up-right": ("growth open external wzrost link", '<path d="M7 17L17 7M8 7h9v9"/>'),
    "play": ("video start odtwórz film", '<path d="M8 5.5v13l11-6.5z"/>'),
    "pause": ("stop pauza wstrzymaj", '<path d="M9 6v12M15 6v12"/>'),
    "heart": ("love like favorite serce lubię miłość ulubione", '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.4a4.3 4.3 0 0 1 7.5 2.4C19.5 15.4 12 20 12 20z"/>'),
    "star": ("rating review favorite gwiazdka ocena opinia", '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 17l-5.2 2.7 1-5.9-4.3-4.1 5.9-.8z"/>'),
    "bolt": ("fast energy power quick błyskawica szybko energia moc", '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/>'),
    "fire": ("hot trending popular ogień gorące popularne", '<path d="M12 3c1 3.5 5.5 5.5 5.5 11a5.5 5.5 0 0 1-11 0c0-2 1-3.5 2.2-4.7.6 1.2 1.4 1.7 2.1 2.2C11.5 10 12.5 7 12 3z"/>'),
    "gift": ("present bonus reward prezent upominek nagroda", '<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M3 9h18M12 9v11M12 9C10.5 5 6.5 5 6.5 7.5S10 9 12 9zm0 0c1.5-4 5.5-4 5.5-1.5S14 9 12 9z"/>'),
    "rocket": ("launch start startup speed premiera start szybki", '<path d="M12 3c3.5 2 5 5.5 5 9l-2.5 2.5h-5L7 12c0-3.5 1.5-7 5-9z"/><circle cx="12" cy="9.5" r="1.6"/><path d="M9.5 14.5L7 18l3-1M14.5 14.5L17 18l-3-1M12 17v4"/>'),
    "chat": ("message comment talk wiadomość komentarz rozmowa", '<path d="M5 5h14a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 16h-7l-4.5 3.5V16H5a1.5 1.5 0 0 1-1.5-1.5v-8A1.5 1.5 0 0 1 5 5z"/>'),
    "mail": ("email newsletter message poczta wiadomość", '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7.5l8 6 8-6"/>'),
    "phone": ("mobile app smartphone telefon aplikacja komórka", '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.5h2"/>'),
    "bell": ("notification alert reminder powiadomienie dzwonek przypomnienie", '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>'),
    "clock": ("time hour deadline czas godzina termin", '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/>'),
    "calendar": ("date event schedule data wydarzenie termin kalendarz", '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
    "pin": ("location map place address lokalizacja mapa miejsce adres", '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>'),
    "camera": ("photo picture zdjęcie aparat fotografia", '<path d="M4 8h3l1.5-2.5h7L17 8h3a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 20 19H4a1.5 1.5 0 0 1-1.5-1.5v-8A1.5 1.5 0 0 1 4 8z"/><circle cx="12" cy="13" r="3.5"/>'),
    "music": ("sound song audio muzyka dźwięk piosenka", '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>'),
    "mic": ("podcast voice record mikrofon głos nagranie", '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>'),
    "user": ("person profile account osoba profil konto klient", '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c.8-4 3.6-6 7.5-6s6.7 2 7.5 6"/>'),
    "users": ("team community people zespół społeczność ludzie", '<circle cx="9" cy="8.5" r="3.2"/><path d="M3 19.5c.6-3.4 3-5 6-5s5.4 1.6 6 5"/><circle cx="17" cy="9.5" r="2.6"/><path d="M16.5 14.8c2.6.1 4.3 1.5 4.8 4.2"/>'),
    "lock": ("secure private password zamek bezpieczeństwo prywatność hasło", '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>'),
    "shield": ("security protection trust gwarancja ochrona zaufanie bezpieczeństwo", '<path d="M12 3l7.5 3v5.5c0 4.5-3 8-7.5 9.5-4.5-1.5-7.5-5-7.5-9.5V6z"/><path d="M8.8 12l2.4 2.4L15.4 10"/>'),
    "sliders": ("settings options customize ustawienia opcje dopasuj", '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>'),
    "trend-up": ("growth chart increase sales wzrost wykres sprzedaż wyniki", '<path d="M4 20V4M4 20h16"/><path d="M8 15l3.5-4 3 2.5L20 7"/><path d="M16 7h4v4"/>'),
    "bars": ("stats analytics report statystyki analityka raport słupki", '<path d="M5 20V12M12 20V5M19 20V9"/>'),
    "dollar": ("money price cost pieniądze cena koszt płatność", '<circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2c-.5-1-1.5-1.5-2.8-1.5-1.6 0-2.8.8-2.8 2 0 1.3 1.2 1.7 2.8 2s2.8.7 2.8 2c0 1.2-1.2 2-2.8 2-1.3 0-2.4-.5-2.9-1.6M12 6v1.7M12 16.3V18"/>'),
    "tag": ("sale discount label price promocja rabat etykieta cena", '<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7a1 1 0 0 1 .7.3l8 8a1 1 0 0 1 0 1.4l-7.7 7.7a1 1 0 0 1-1.4 0l-8-8a1 1 0 0 1-.3-.7z"/><circle cx="8" cy="8" r="1.4"/>'),
    "percent": ("discount sale deal procent rabat okazja", '<path d="M18.5 5.5l-13 13"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>'),
    "trophy": ("win award best winner puchar nagroda zwycięzca najlepszy", '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4.5c0 3 1 4.5 3.5 5M16 6h3.5c0 3-1 4.5-3.5 5M12 13v4M8.5 20.5h7M10 17h4"/>'),
    "crown": ("premium vip king luksus korona", '<path d="M4 8l4.5 4L12 5.5 15.5 12 20 8l-1.5 10h-13z"/>'),
    "sparkle": ("magic ai new shine magia nowe blask", '<path d="M11 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z"/><path d="M19 15.5v4M17 17.5h4"/>'),
    "globe": ("world web internet international świat sieć międzynarodowy", '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.8 5.2 3.8 8.5s-1.2 6.1-3.8 8.5c-2.6-2.4-3.8-5.2-3.8-8.5S9.4 5.9 12 3.5z"/>'),
    "wifi": ("connection online network połączenie sieć", '<path d="M3.5 9.5a12 12 0 0 1 17 0M6.5 12.8a7.8 7.8 0 0 1 11 0M9.5 16a3.5 3.5 0 0 1 5 0"/><circle cx="12" cy="19" r=".8" fill="currentColor"/>'),
    "download": ("save get install pobierz zapisz", '<path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/>'),
    "upload": ("send share publish wyślij udostępnij", '<path d="M12 16V5M7 9.5l5-5 5 5M5 20h14"/>'),
    "search": ("find lookup magnifier szukaj lupa znajdź", '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20.5 20.5"/>'),
    "home": ("house start dom strona główna", '<path d="M4 11l8-7 8 7M6 9.5V20h12V9.5M10 20v-5.5h4V20"/>'),
    "bag": ("shopping store buy torba zakupy sklep kup", '<path d="M5.5 8h13l1 12.5h-15z"/><path d="M9 11V7.5a3 3 0 0 1 6 0V11"/>'),
    "cart": ("shopping checkout buy koszyk zakupy zamówienie", '<path d="M3 4h2.5l2 11h10.5l2-8H6.5"/><circle cx="9.5" cy="19.5" r="1.4"/><circle cx="17" cy="19.5" r="1.4"/>'),
    "truck": ("delivery shipping logistics dostawa wysyłka transport", '<path d="M3 6.5h11v10H3zM14 10h4l3 3.5v3H14"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>'),
    "leaf": ("eco nature green natural eko natura zielony roślina", '<path d="M5 19c0-8 4-14 14-14 0 10-6 14-14 14z"/><path d="M5 19c3-5 6-7.5 10-9.5"/>'),
    "sun": ("day light summer dzień światło lato słońce", '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>'),
    "moon": ("night dark sleep noc ciemny sen księżyc", '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>'),
    "cloud": ("storage weather sky chmura pogoda niebo", '<path d="M7 18.5a4 4 0 0 1-.6-8 5.5 5.5 0 0 1 10.7-1A4.7 4.7 0 0 1 17 18.5z"/>'),
    "thumbs-up": ("like approve good polecam lubię dobre", '<path d="M8 11v9H4.5v-9zM8 11l3.5-7c1.7 0 2.5 1.2 2.2 2.8L13 10h5.5a1.8 1.8 0 0 1 1.8 2.2l-1.4 6.2A2 2 0 0 1 17 20H8"/>'),
    "eye": ("view watch see oko oglądaj widok", '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>'),
    "bookmark": ("save later favorite zakładka zapisz ulubione", '<path d="M6.5 3.5h11v17L12 16.5l-5.5 4z"/>'),
    "share": ("send social network udostępnij sieć", '<circle cx="6" cy="12" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.2 10.9l7.6-3.8M8.2 13.1l7.6 3.8"/>'),
    "link": ("url connect chain adres połączenie", '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/>'),
    "code": ("developer program dev html kod programista", '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5M13.5 5.5l-3 13"/>'),
    "cpu": ("chip hardware processor ai procesor sprzęt układ", '<rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9.5 3v3.5M14.5 3v3.5M9.5 17.5V21M14.5 17.5V21M3 9.5h3.5M3 14.5h3.5M17.5 9.5H21M17.5 14.5H21"/>'),
    "bulb": ("idea tip insight pomysł wskazówka porada", '<path d="M9 17.5h6M10 20.5h4M12 3.5a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.4 1.1 2.2h5c0-.8.4-1.6 1.1-2.2A6 6 0 0 0 12 3.5z"/>'),
    "target": ("goal aim focus cel skupienie trafienie", '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8" fill="currentColor"/>'),
    "flag": ("milestone mark goal flaga cel etap", '<path d="M5.5 21V4M5.5 5h12l-2.5 4 2.5 4h-12"/>'),
    "coffee": ("cafe drink break kawa napój przerwa", '<path d="M5 8.5h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5v2M12 3.5v2"/>'),
    "smile": ("happy emoji face friendly uśmiech buzia szczęśliwy", '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 14c.8 1.6 2 2.4 3.5 2.4s2.7-.8 3.5-2.4M9 9.5v.5M15 9.5v.5"/>'),
    "megaphone": ("announce marketing news ogłoszenie reklama nowość", '<path d="M4 10v4h3l8 4.5v-13L7 10zM18.5 9.5a4 4 0 0 1 0 5"/>'),
    "video": ("film movie clip wideo nagranie klip", '<rect x="3" y="6.5" width="12.5" height="11" rx="2"/><path d="M15.5 11l5-3v8l-5-3"/>'),
    "image": ("photo gallery picture obraz galeria zdjęcie", '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 18l5-4.5 3.5 3L16 13l4 4"/>'),
}


def _icon_svg(icon_id: str, color: str = "currentColor", stroke: float = 2.0) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke:g}" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon_id][1]}</svg>')


_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")


def _norm(s: str) -> str:
    return s.lower().translate(_FOLD)


def search_builtin(query: str, limit: int = 12) -> list[dict]:
    words = [_norm(w) for w in re.findall(r"[\w-]+", query or "") if len(w) >= 2]
    scored = []
    for iid, (kw, _) in ICONS.items():
        hay = _norm(f"{iid} {kw}").split()
        score = sum(3 if w == iid else 2 if w in hay else 1 if any(h.startswith(w) or w.startswith(h) for h in hay if len(h) >= 4 and len(w) >= 3) else 0 for w in words)
        if score or not words:
            scored.append((-score, iid))
    scored.sort()
    return [{"source": "builtin", "id": f"builtin:{iid}", "name": iid, "kind": "icon", "license": "original (vstudio)", "attribution": None,
             "preview": _icon_svg(iid)} for _, iid in scored[:limit]]


# ------------------------------------------------------------------ generatory (deterministyczne z ziarna)

_DEFAULT_COLORS = ["#7C5CFF", "#2DE2E6", "#FF5C8A", "#FFD93D", "#0F1226"]


class _Rng:
    """Mały generator liczb (mulberry32): ten sam wynik na każdej wersji Pythona i systemie."""

    def __init__(self, seed: int) -> None:
        self.s = seed & 0xFFFFFFFF

    def random(self) -> float:
        self.s = (self.s + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.s
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.random()

    def pick(self, items: list):
        return items[min(int(self.random() * len(items)), len(items) - 1)]


def _hexes(colors: list[str] | None) -> list[str]:
    out = [c for c in (colors or []) if re.fullmatch(r"#[0-9a-fA-F]{6}", c or "")]
    return out or list(_DEFAULT_COLORS)


def _svg(w: int, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            + (f"<defs>{defs}</defs>" if defs else "") + body + "</svg>")


def _smooth_closed(points: list[tuple[float, float]]) -> str:
    """Zamknięta gładka krzywa przez punkty (Catmull-Rom -> Bezier)."""
    n = len(points)
    d = f"M{points[0][0]:.1f} {points[0][1]:.1f}"
    for i in range(n):
        p0, p1, p2, p3 = points[(i - 1) % n], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d + "z"


def gen_blob(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    r = _Rng(seed)
    cx, cy, rad = w / 2, h / 2, min(w, h) * 0.42
    n = 8
    pts = [(cx + math.cos(2 * math.pi * i / n) * rad * r.uniform(0.7, 1.0), cy + math.sin(2 * math.pi * i / n) * rad * r.uniform(0.7, 1.0)) for i in range(n)]
    c1, c2 = colors[0], colors[1 % len(colors)]
    defs = f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>'
    return _svg(w, h, f'<path d="{_smooth_closed(pts)}" fill="url(#g)"/>', defs)


def gen_mesh(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    r = _Rng(seed)
    bg = colors[-1]
    blobs, defs = "", f'<filter id="b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{int(min(w, h) * 0.12)}"/></filter>'
    for i in range(4):
        c = colors[i % max(len(colors) - 1, 1)]
        blobs += f'<circle cx="{r.uniform(0.1, 0.9) * w:.0f}" cy="{r.uniform(0.1, 0.9) * h:.0f}" r="{r.uniform(0.22, 0.4) * min(w, h):.0f}" fill="{c}" opacity="{r.uniform(0.65, 0.95):.2f}"/>'
    return _svg(w, h, f'<rect width="{w}" height="{h}" fill="{bg}"/><g filter="url(#b)">{blobs}</g>', defs)


def gen_dots(seed: int, colors: list[str], w: int, h: int, gap: int = 54, **_) -> str:
    r = _Rng(seed)
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="{gap * (0.1 + 0.12 * r.random()):.1f}"/>' for y in range(gap // 2, h, gap) for x in range(gap // 2, w, gap))
    return _svg(w, h, f'<g fill="{colors[0]}" opacity=".5">{dots}</g>')


def gen_grid(seed: int, colors: list[str], w: int, h: int, gap: int = 90, **_) -> str:
    lines = "".join(f'<path d="M{x} 0V{h}"/>' for x in range(0, w + 1, gap)) + "".join(f'<path d="M0 {y}H{w}"/>' for y in range(0, h + 1, gap))
    return _svg(w, h, f'<g stroke="{colors[0]}" stroke-width="2" opacity=".35">{lines}</g>')


def gen_rings(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    r = _Rng(seed)
    cx, cy = w * r.uniform(0.35, 0.65), h * r.uniform(0.35, 0.65)
    rings = "".join(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{(i + 1) * min(w, h) * 0.09:.0f}" opacity="{max(0.08, 0.6 - i * 0.07):.2f}"/>' for i in range(9))
    return _svg(w, h, f'<g fill="none" stroke="{colors[0]}" stroke-width="3">{rings}</g>')


def gen_waves(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    r = _Rng(seed)
    layers = ""
    for i in range(4):
        base = h * (0.5 + i * 0.12)
        amp, ph, freq = h * r.uniform(0.03, 0.06), r.uniform(0, 6.28), r.uniform(1.2, 2.4)
        pts = [(x, base + math.sin(x / w * freq * 2 * math.pi + ph) * amp) for x in range(0, w + 40, 40)]
        d = "M0 %d " % h + "L" + " L".join(f"{x:.0f} {y:.0f}" for x, y in pts) + f" L{w} {h}z"
        layers += f'<path d="{d}" fill="{colors[i % len(colors)]}" opacity="{0.35 + 0.15 * i:.2f}"/>'
    return _svg(w, h, layers)


def gen_rays(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    cx, cy, big, n = w / 2, h / 2, math.hypot(w, h), 18
    wedges = ""
    for i in range(0, n, 2):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        wedges += f'<path d="M{cx:.0f} {cy:.0f} L{cx + math.cos(a0) * big:.0f} {cy + math.sin(a0) * big:.0f} L{cx + math.cos(a1) * big:.0f} {cy + math.sin(a1) * big:.0f}z"/>'
    return _svg(w, h, f'<g fill="{colors[0]}" opacity=".28">{wedges}</g>')


def gen_confetti(seed: int, colors: list[str], w: int, h: int, count: int = 48, **_) -> str:
    r = _Rng(seed)
    bits = ""
    for _i in range(count):
        x, y, s, rot, c = r.uniform(0, w), r.uniform(0, h), r.uniform(0.012, 0.03) * min(w, h), r.uniform(0, 360), r.pick(colors)
        kind = r.random()
        if kind < 0.4:
            bits += f'<rect x="{-s:.1f}" y="{-s / 2:.1f}" width="{2 * s:.1f}" height="{s:.1f}" rx="2" fill="{c}" transform="translate({x:.0f} {y:.0f}) rotate({rot:.0f})"/>'
        elif kind < 0.7:
            bits += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{s * 0.7:.1f}" fill="{c}"/>'
        else:
            bits += f'<path d="M0 {-s:.1f} L{s:.1f} {s:.1f} L{-s:.1f} {s:.1f}z" fill="{c}" transform="translate({x:.0f} {y:.0f}) rotate({rot:.0f})"/>'
    return _svg(w, h, bits)


def gen_grain(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    defs = f'<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="{seed % 1000}"/><feColorMatrix type="saturate" values="0"/></filter>'
    return _svg(w, h, f'<rect width="{w}" height="{h}" filter="url(#n)" opacity=".09"/>', defs)


def gen_starburst(seed: int, colors: list[str], w: int, h: int, points: int = 14, **_) -> str:
    r = _Rng(seed)
    cx, cy, ro = w / 2, h / 2, min(w, h) * 0.46
    pts = []
    for i in range(points * 2):
        rad = ro if i % 2 == 0 else ro * r.uniform(0.74, 0.82)
        a = math.pi * i / points - math.pi / 2
        pts.append(f"{cx + math.cos(a) * rad:.1f},{cy + math.sin(a) * rad:.1f}")
    return _svg(w, h, f'<polygon points="{" ".join(pts)}" fill="{colors[0]}" stroke="{colors[-1]}" stroke-width="{max(4, min(w, h) // 60)}" stroke-linejoin="round"/>')


def gen_squiggle(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    n, amp = 7, h * 0.28
    pts = [(w * 0.04 + (w * 0.92) * i / (n * 2), h / 2 + (amp if i % 2 else -amp)) for i in range(n * 2 + 1)]
    d = f"M{pts[0][0]:.0f} {h / 2:.0f}" + "".join(f" Q{pts[i][0]:.0f} {pts[i][1]:.0f} {pts[i + 1][0]:.0f} {h / 2:.0f}" for i in range(1, len(pts) - 1, 2))
    return _svg(w, h, f'<path d="{d}" fill="none" stroke="{colors[0]}" stroke-width="{max(6, h // 8)}" stroke-linecap="round"/>')


def gen_arrow(seed: int, colors: list[str], w: int, h: int, **_) -> str:
    r = _Rng(seed)
    bend = h * r.uniform(0.2, 0.45)
    x0, y0, x1, y1 = w * 0.1, h * 0.75, w * 0.88, h * 0.25
    d = f"M{x0:.0f} {y0:.0f} C{w * 0.3:.0f} {y0 + bend:.0f} {w * 0.6:.0f} {y1 - bend:.0f} {x1:.0f} {y1:.0f}"
    head = f"M{x1 - w * 0.08:.0f} {y1 - h * 0.02:.0f} L{x1:.0f} {y1:.0f} L{x1 - w * 0.03:.0f} {y1 + h * 0.15:.0f}"
    return _svg(w, h, f'<g fill="none" stroke="{colors[0]}" stroke-width="{max(6, h // 14)}" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/><path d="{head}"/></g>')


GENERATORS: dict[str, tuple] = {
    "blob": (gen_blob, "organiczna plama z gradientem (tło kart, naklejki)", (800, 800)),
    "mesh": (gen_mesh, "tło z rozmytych plam, zorza (ostatni kolor to tło)", (1080, 1350)),
    "dots": (gen_dots, "siatka kropek o różnej wielkości (faktura)", (1080, 1350)),
    "grid": (gen_grid, "cienka siatka (tło techniczne)", (1080, 1350)),
    "rings": (gen_rings, "koncentryczne okręgi (radar, fala uderzeniowa)", (1080, 1350)),
    "waves": (gen_waves, "warstwy fal (dół kadru)", (1080, 1350)),
    "rays": (gen_rays, "promienie z centrum (sunburst)", (1080, 1350)),
    "confetti": (gen_confetti, "konfetti z kształtów w kolorach marki", (1080, 1350)),
    "grain": (gen_grain, "ziarno filmu jako nakładka (3-9% krycia)", (1080, 1350)),
    "starburst": (gen_starburst, "plakietka-gwiazda pod cenę lub „NEW” (tekst dodaj w HTML)", (600, 600)),
    "squiggle": (gen_squiggle, "falista kreska do podkreśleń", (700, 120)),
    "arrow": (gen_arrow, "odręczna strzałka", (600, 360)),
}

# ------------------------------------------------------------------ bezpieczne pobieranie

class FetchError(StudioError):
    """Pobranie odrzucone: adres, rozmiar, typ albo zawartość nie spełnia zasad."""


def _check_ip(ip_text: str) -> None:
    ip = ipaddress.ip_address(ip_text.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast:
        raise FetchError(f"adres {ip} nie jest publiczny: odrzucam (ochrona przed zapytaniami do sieci wewnętrznej)")


def check_url(url: str) -> list[str]:
    """Waliduje adres i zwraca sprawdzone IP serwera. https, port 443, bez danych logowania, tylko adresy publiczne."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise FetchError(f"niepoprawny adres: {exc}") from exc
    if u.scheme != "https":
        raise FetchError("dozwolony jest tylko https")
    if u.username or u.password:
        raise FetchError("adres z danymi logowania jest niedozwolony")
    host = (u.hostname or "").lower()
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost", ".lan")):
        raise FetchError("adres lokalny jest niedozwolony")
    if (u.port or 443) != 443:
        raise FetchError("dozwolony jest tylko port 443")
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError(f"nie udało się znaleźć serwera {host}: {exc}") from exc
    ips = sorted({i[4][0] for i in infos})
    if not ips:
        raise FetchError(f"serwer {host} nie ma adresu")
    for ip in ips:
        _check_ip(ip)
    return ips


class _PinnedHTTPS(http.client.HTTPSConnection):
    """Łączy się z ZWERYFIKOWANYM adresem IP (nie rozwiązuje nazwy drugi raz), a TLS sprawdza względem nazwy hosta."""

    def __init__(self, host: str, ip: str, **kw) -> None:
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _SafeHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        ips = check_url(req.full_url)
        ctx = ssl.create_default_context()
        return self.do_open(lambda host, **kw: _PinnedHTTPS(host, ips[0], context=ctx, **{k: v for k, v in kw.items() if k != "context"}), req)


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(urllib.parse.urljoin(req.full_url, newurl))        # każdy skok sprawdzamy od nowa
        return super().redirect_request(req, fp, code, msg, headers, urllib.parse.urljoin(req.full_url, newurl))


def _opener() -> urllib.request.OpenerDirector:
    proxied = any(os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"))
    if proxied:             # za proxy łączy się ono, nie my: sprawdzamy adres przed wysłaniem, ale nie możemy przypiąć IP
        return urllib.request.build_opener(_Redirects())
    return urllib.request.build_opener(_SafeHandler(), _Redirects())


def http_get(url: str, *, max_bytes: int, accept: str = "*/*", timeout: float = TIMEOUT) -> tuple[bytes, str, str]:
    """GET z limitem rozmiaru i czasu. Zwraca (treść, content-type, adres końcowy)."""
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    deadline = time.time() + timeout
    try:
        with _opener().open(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            length = resp.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise FetchError(f"plik ma {int(length) // 1000} kB: limit to {max_bytes // 1000} kB")
            chunks, total = [], 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FetchError(f"plik przekracza limit {max_bytes // 1000} kB")
                if time.time() > deadline:
                    raise FetchError("pobieranie trwa za długo")
                chunks.append(chunk)
            return b"".join(chunks), ctype, resp.geturl()
    except FetchError:
        raise
    except urllib.error.HTTPError as exc:
        raise FetchError(f"serwer odpowiedział HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        raise FetchError(f"nie udało się pobrać: {getattr(exc, 'reason', exc)}") from exc


def get_json(url: str) -> dict:
    data, _ctype, _final = http_get(url, max_bytes=2_000_000, accept="application/json")
    try:
        return json.loads(data.decode("utf-8"))
    except ValueError as exc:
        raise FetchError("odpowiedź API nie jest poprawnym JSON-em") from exc


# ------------------------------------------------------------------ sanityzacja

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK = "http://www.w3.org/1999/xlink"
_ALLOWED_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient", "radialgradient", "stop",
                 "clippath", "mask", "title", "desc", "symbol", "use", "pattern", "filter", "fegaussianblur", "feturbulence", "fecolormatrix",
                 "feoffset", "feblend", "feflood", "fecomposite", "femerge", "femergenode", "fedropshadow", "text", "tspan"}
_URL_ATTR = re.compile(r"url\(\s*(['\"]?)\s*([^)'\"]*)\1\s*\)", re.I)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _clean_attr_value(val: str) -> bool:
    """False, jeśli wartość odwołuje się poza dokument (url() na zewnątrz) albo wygląda na kod."""
    low = val.lower()
    if "javascript:" in low or "expression(" in low or "@import" in low or "data:text/html" in low:
        return False
    return all(m.group(2).startswith("#") for m in _URL_ATTR.finditer(val))


def sanitize_svg(text: str) -> str:
    """Czarna i biała lista: bez skryptów, stylów, foreignObject, obrazów i odwołań na zewnątrz. Zwraca czysty SVG."""
    if len(text.encode("utf-8")) > MAX_SVG:
        raise FetchError(f"SVG większy niż {MAX_SVG // 1000} kB")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise FetchError("SVG z DOCTYPE/ENTITY jest niedozwolony")
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", _XLINK)
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError as exc:
        raise FetchError(f"to nie jest poprawny SVG: {exc}") from exc
    if _local(root.tag) != "svg":
        raise FetchError("korzeń dokumentu nie jest elementem svg")

    def walk(el: ET.Element) -> None:
        for child in list(el):
            tag = _local(child.tag)
            if tag not in _ALLOWED_TAGS:
                el.remove(child)
                continue
            walk(child)
        for k in list(el.attrib):
            name = _local(k)
            val = el.attrib[k]
            if name.startswith("on") or name in ("style",) and not _clean_attr_value(val):
                del el.attrib[k]
            elif name == "href":
                if not val.startswith("#"):
                    del el.attrib[k]
            elif not _clean_attr_value(val):
                del el.attrib[k]

    walk(root)
    if "viewBox" not in root.attrib:
        def num(v: str | None) -> float | None:
            m = re.match(r"\s*([\d.]+)", v or "")
            return float(m.group(1)) if m else None

        w, h = num(root.get("width")), num(root.get("height"))
        if not (w and h):
            raise FetchError("SVG bez viewBox i bez width/height")
        root.set("viewBox", f"0 0 {w:g} {h:g}")
    out = ET.tostring(root, encoding="unicode")
    if not out.lstrip().startswith("<svg"):
        raise FetchError("nie udało się zserializować SVG")
    return out


def process_raster(data: bytes) -> tuple[bytes, str, tuple[int, int]]:
    """Obraz rastrowy: weryfikacja, limit pikseli, zmniejszenie, ponowne kodowanie bez metadanych."""
    import io

    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        im = Image.open(io.BytesIO(data))
        if im.format not in ("PNG", "JPEG", "WEBP"):
            raise FetchError(f"format {im.format} nie jest obsługiwany (PNG, JPEG, WebP, SVG)")
        if im.width * im.height > MAX_PIXELS:
            raise FetchError("obraz ma za dużo pikseli")
        im.load()
    except FetchError:
        raise
    except Exception as exc:  # noqa: BLE001 - PIL rzuca różne wyjątki dla uszkodzonych plików
        raise FetchError(f"nie udało się odczytać obrazu: {exc}") from exc
    if max(im.size) > MAX_SIDE:
        scale = MAX_SIDE / max(im.size)
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    buf = io.BytesIO()
    if alpha:
        im.convert("RGBA").save(buf, "PNG", optimize=True)
        ext = "png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
        ext = "jpg"
    return buf.getvalue(), ext, im.size


def sniff(data: bytes) -> str:
    head = data[:16]
    if head.startswith(b"\x89PNG"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if re.match(rb"\s*(<\?xml|<svg|<!--)", data[:200]):
        return "svg"
    raise FetchError("plik nie jest obrazem PNG, JPEG, WebP ani SVG")


# ------------------------------------------------------------------ projekt: katalog assetów i ślad pochodzenia

def _dir(pdir: Path) -> Path:
    d = pdir / "src" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(pdir: Path) -> Path:
    return _dir(pdir) / "ASSETS.json"


def _read_manifest(pdir: Path) -> list[dict]:
    f = _manifest_path(pdir)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except ValueError:
        return []


def _write_manifest(pdir: Path, rows: list[dict]) -> None:
    from .locking import atomic_write

    atomic_write(_manifest_path(pdir), json.dumps(rows, indent=2, ensure_ascii=False))


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _norm(name)).strip("-")
    return s[:48] or "asset"


def _unique(pdir: Path, base: str, ext: str) -> str:
    d = _dir(pdir)
    name, n = f"{base}.{ext}", 2
    while (d / name).exists():
        name = f"{base}-{n}.{ext}"
        n += 1
    return name


def _record(pdir: Path, file: str, data: bytes, **meta) -> dict:
    row = {"file": file, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "added": time.strftime("%Y-%m-%dT%H:%M:%S"), **meta}
    rows = [r for r in _read_manifest(pdir) if r["file"] != file] + [row]
    _write_manifest(pdir, rows)
    return row


def snippet(pdir: Path, file: str, mode: str = "auto") -> dict:
    """Kod do wklejenia w scenę. SVG inline (da się go przemalować przez CSS `color`), obraz rastrowy jako <img> ze ścieżką względną."""
    f = _dir(pdir) / file
    if not f.is_file():
        raise StudioError(f"brak assetu '{file}' (assets_list)")
    ext = f.suffix.lower().lstrip(".")
    if ext == "svg" and mode in ("auto", "inline"):
        svg = f.read_text(encoding="utf-8")
        return {"mode": "inline", "html": svg.replace("<svg ", '<svg class="asset" ', 1),
                "note": "Inline SVG inherits `color` (stroke/fill currentColor). Position it with CSS and animate it like any element."}
    if ext in ("svg", "png", "jpg", "webp"):
        size = None
        if ext != "svg":
            from PIL import Image

            with Image.open(f) as im:
                size = list(im.size)
        return {"mode": "img", "html": f'<img class="asset" src="assets/{file}" alt="" decoding="sync">', "size": size,
                "note": "Relative path: preview, supervisor and render all serve src/ as the root. Await decoding in __ready: "
                        "`window.__ready = Promise.all([document.fonts.ready, ...[...document.images].map(i => i.decode())])`."}
    raise StudioError(f"nieobsługiwany typ pliku: {ext}")


def listing(pdir: Path) -> list[dict]:
    d = _dir(pdir)
    meta = {r["file"]: r for r in _read_manifest(pdir)}
    rows = []
    for f in sorted(d.iterdir()):
        if f.name.startswith(".") or f.name == "ASSETS.json" or not f.is_file():
            continue
        m = meta.get(f.name, {})
        rows.append({"file": f.name, "rel": f"assets/{f.name}", "bytes": f.stat().st_size, "origin": m.get("origin", "unknown"),
                     "license": m.get("license"), "attribution": m.get("attribution"), "source": m.get("source"), "tracked": f.name in meta})
    return rows


def remove(pdir: Path, file: str) -> dict:
    d = _dir(pdir).resolve()
    f = (d / file).resolve()
    if f.parent != d or not f.is_file() or file == "ASSETS.json":
        raise StudioError(f"brak assetu '{file}'")
    f.unlink()
    _write_manifest(pdir, [r for r in _read_manifest(pdir) if r["file"] != file])
    return {"removed": file}


def credits(pdir: Path) -> list[str]:
    """Linie do sekcji Credits w DELIVERY.md: tylko zasoby spoza vstudio, z licencją i autorem."""
    out = []
    for r in _read_manifest(pdir):
        if r.get("origin") in ("fetched", "iconify", "openverse", "url"):
            who = f" by {r['author']}" if r.get("author") else ""
            lic = f" ({r['license']})" if r.get("license") else ""
            out.append(f"- `assets/{r['file']}`{who}{lic}: {r.get('source') or ''}".rstrip(": "))
    return out


# ------------------------------------------------------------------ operacje: szukaj, dodaj, generuj

def search(query: str, source: str = "builtin", limit: int = 12) -> dict:
    limit = max(1, min(int(limit), 30))
    if source == "builtin":
        return {"source": source, "query": query, "results": search_builtin(query, limit)}
    if source == "iconify":
        q = urllib.parse.urlencode({"query": query, "limit": limit, "prefixes": ICONIFY_PREFIXES})
        data = get_json(f"https://api.iconify.design/search?{q}")
        cols = data.get("collections", {})
        res = []
        for ident in data.get("icons", []):
            prefix, _, name = ident.partition(":")
            info = cols.get(prefix, {})
            spdx = (info.get("license") or {}).get("spdx") or (info.get("license") or {}).get("title")
            if spdx not in OK_LICENSES:
                continue
            res.append({"source": "iconify", "id": f"iconify:{prefix}:{name}", "name": name, "kind": "icon", "license": spdx,
                        "attribution": (info.get("author") or {}).get("name") if spdx in ATTRIBUTION_LICENSES else None,
                        "preview_url": f"https://api.iconify.design/{prefix}/{name}.svg", "set": info.get("name", prefix)})
        return {"source": source, "query": query, "results": res[:limit], "note": "licencje zweryfikowane w API Iconify; CC-BY wymaga wskazania autora (zapisywane w creditsach)"}
    if source == "openverse":
        q = urllib.parse.urlencode({"q": query, "page_size": limit, "license": OPENVERSE_LICENSES, "mature": "false", "extension": "jpg,png"})
        data = get_json(f"https://api.openverse.org/v1/images/?{q}")
        res = []
        for it in data.get("results", []):
            lic = (it.get("license") or "").lower()
            if lic not in OPENVERSE_LICENSES.split(","):
                continue
            res.append({"source": "openverse", "id": f"openverse:{it['id']}", "name": it.get("title") or it["id"], "kind": "photo",
                        "license": f"{lic.upper()} {it.get('license_version') or ''}".strip(), "author": it.get("creator"),
                        "attribution": it.get("attribution") if lic == "by" else None, "url": it.get("url"), "thumbnail": it.get("thumbnail"),
                        "landing": it.get("foreign_landing_url"), "license_url": it.get("license_url")})
        return {"source": source, "query": query, "results": res[:limit], "note": "tylko CC0, domena publiczna i CC-BY (bez NC/ND/SA); CC-BY wymaga wskazania autora"}
    raise StudioError("source: builtin, iconify albo openverse")


def _save_svg(pdir: Path, base: str, svg: str, **meta) -> dict:
    clean = sanitize_svg(svg)
    name = _unique(pdir, base, "svg")
    (_dir(pdir) / name).write_text(clean, encoding="utf-8")
    row = _record(pdir, name, clean.encode("utf-8"), kind="icon" if meta.get("origin") != "generated" else "graphic", **meta)
    return {"file": name, "rel": f"assets/{name}", "kind": row["kind"], "license": meta.get("license"), "snippet": snippet(pdir, name)}


def add(pdir: Path, ref: str, name: str | None = None, color: str | None = None) -> dict:
    """Dodaje asset do projektu. ref: `builtin:<id>`, `iconify:<prefix>:<name>`, `openverse:<id>` (z wyniku search) albo https URL."""
    if color and not re.fullmatch(r"#[0-9a-fA-F]{6}|currentColor", color):
        raise StudioError("color: #RRGGBB albo currentColor")
    if ref.startswith("builtin:"):
        iid = ref.split(":", 1)[1]
        if iid not in ICONS:
            raise StudioError(f"nie ma wbudowanej ikony '{iid}'. Użyj assets_search.")
        return _save_svg(pdir, _slug(name or iid), _icon_svg(iid, color or "currentColor"), origin="builtin", source=ref, license="original (vstudio)")
    if ref.startswith("iconify:"):
        parts = ref.split(":")
        if len(parts) != 3 or not all(re.fullmatch(r"[a-z0-9-]+", p) for p in parts[1:]):
            raise StudioError("iconify:<zestaw>:<nazwa>, np. iconify:lucide:heart")
        prefix, icon = parts[1], parts[2]
        info = (get_json(f"https://api.iconify.design/collection?prefix={prefix}&info=true").get("info") or {})
        lic = info.get("license") or {}
        spdx = lic.get("spdx") or lic.get("title")
        if spdx not in OK_LICENSES:
            raise FetchError(f"licencja zestawu {prefix} ({spdx or 'nieznana'}) nie jest na liście dozwolonych")
        q = f"?color={urllib.parse.quote(color)}" if color and color != "currentColor" else ""
        data, ctype, _ = http_get(f"https://api.iconify.design/{prefix}/{icon}.svg{q}", max_bytes=MAX_SVG, accept="image/svg+xml")
        return _save_svg(pdir, _slug(name or icon), data.decode("utf-8", "replace"), origin="iconify", source=f"https://icon-sets.iconify.design/{prefix}/{icon}/",
                         license=spdx, author=(info.get("author") or {}).get("name"), license_url=lic.get("url"))
    if ref.startswith("openverse:"):
        oid = ref.split(":", 1)[1]
        if not re.fullmatch(r"[0-9a-f-]{8,40}", oid):
            raise StudioError("niepoprawny identyfikator Openverse")
        meta = get_json(f"https://api.openverse.org/v1/images/{oid}/")
        lic = (meta.get("license") or "").lower()
        if lic not in OPENVERSE_LICENSES.split(","):
            raise FetchError(f"licencja '{lic}' nie jest dozwolona (CC0, domena publiczna, CC-BY)")
        return _add_url(pdir, meta["url"], name or meta.get("title") or oid, origin="openverse", source=meta.get("foreign_landing_url") or meta["url"],
                        license=f"{lic.upper()} {meta.get('license_version') or ''}".strip(), author=meta.get("creator"), license_url=meta.get("license_url"))
    if ref.startswith("https://"):
        return _add_url(pdir, ref, name or Path(urllib.parse.urlsplit(ref).path).stem, origin="url", source=ref, license="unknown: sprawdź prawa", author=None)
    raise StudioError("ref: builtin:<id>, iconify:<zestaw>:<nazwa>, openverse:<id> albo adres https")


def _add_url(pdir: Path, url: str, name: str, **meta) -> dict:
    data, _ctype, final = http_get(url, max_bytes=MAX_RASTER, accept="image/svg+xml,image/png,image/jpeg,image/webp")
    kind = sniff(data)
    if kind == "svg":
        return _save_svg(pdir, _slug(name), data.decode("utf-8", "replace"), **meta)
    clean, ext, size = process_raster(data)
    fname = _unique(pdir, _slug(name), ext)
    (_dir(pdir) / fname).write_bytes(clean)
    row = _record(pdir, fname, clean, kind="photo", width=size[0], height=size[1], **meta)
    return {"file": fname, "rel": f"assets/{fname}", "kind": "photo", "license": meta.get("license"), "size": list(size), "snippet": snippet(pdir, fname),
            "note": "Obraz zmniejszony do maks. 1600 px i zakodowany ponownie (bez metadanych)." if max(size) == MAX_SIDE else None}


def generate(pdir: Path, kind: str, seed: int = 1, colors: list[str] | None = None, name: str | None = None, width: int | None = None,
             height: int | None = None) -> dict:
    if kind not in GENERATORS:
        raise StudioError(f"nieznany generator '{kind}'. Dostępne: {', '.join(GENERATORS)}")
    fn, _desc, (dw, dh) = GENERATORS[kind]
    w, h = int(width or dw), int(height or dh)
    if not (64 <= w <= 4096 and 32 <= h <= 4096):
        raise StudioError("width/height: 64-4096 px")
    svg = fn(int(seed), _hexes(colors), w, h)
    return _save_svg(pdir, _slug(name or f"{kind}-{seed}"), svg, origin="generated", source=f"generator:{kind} seed={seed}", license="original (vstudio)")


def generator_list() -> list[dict]:
    return [{"kind": k, "about": d, "default_size": list(s)} for k, (_f, d, s) in GENERATORS.items()]
