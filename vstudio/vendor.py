"""Vendor: lokalne kopie bibliotek ładowanych z CDN (np. GSAP), żeby podgląd, nadzór i render działały offline.

Strona filmowa może mieć `<script src="https://cdnjs.cloudflare.com/.../gsap.min.js">`. Bez sieci (albo z zablokowanym CDN)
taka strona się nie uruchomi. `vstudio vendor add <url>` zapisuje kopię w output/.studio/vendor/, a wszystkie nasze ścieżki
przeglądarkowe podmieniają żądanie do tego URL-a na lokalny plik (HTML strony zostaje bez zmian, więc plik nadal działa
u każdego z CDN):

  - nadzorca i `frames_view` (Playwright)      -> route_handler()
  - render (`html_to_video.py`)                -> zmienna VSTUDIO_VENDOR_INDEX
  - podgląd w dashboardzie                     -> rewrite_html() podmienia adresy na /vendor/<plik>
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path

from . import common

#: skróty do popularnych bibliotek (wersje takie jak w przykładach repo)
ALIASES = {
    "gsap": "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js",
}
_MIME = {".js": "application/javascript", ".mjs": "application/javascript", ".css": "text/css", ".json": "application/json",
         ".woff2": "font/woff2", ".woff": "font/woff", ".svg": "image/svg+xml", ".png": "image/png"}
_URL_RE = re.compile(r"https?://[^\s\"'<>)]+")
#: typy zasobów, które w ogóle przechowujemy; rozszerzenie bierzemy z URL-a, a gdy go brak, z Content-Type odpowiedzi
_CT_EXT = {"text/css": ".css", "application/javascript": ".js", "text/javascript": ".js", "application/x-javascript": ".js",
           "font/woff2": ".woff2", "font/woff": ".woff", "application/font-woff2": ".woff2", "application/json": ".json",
           "image/svg+xml": ".svg", "image/png": ".png"}
_NET_EXT = {".js", ".mjs", ".css", ".json", ".woff2", ".woff", ".svg", ".png"}
#: z dysku kopiujemy TYLKO skrypty, style i fonty: `vendor_add` jest narzędziem agenta, więc nie może czytać dowolnych plików (klucze, dane)
_FILE_EXT = {".js", ".mjs", ".css", ".woff2", ".woff"}
MAX_BYTES = 20_000_000


def vendor_dir() -> Path:
    return common.STATE_DIR / "vendor"


def index_path() -> Path:
    return vendor_dir() / "index.json"


def load_index() -> dict[str, str]:
    f = index_path()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _save_index(idx: dict[str, str]) -> None:
    vendor_dir().mkdir(parents=True, exist_ok=True)
    index_path().write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")


def resolve_url(url_or_alias: str) -> str:
    return ALIASES.get(url_or_alias.lower(), url_or_alias)


def add(url_or_alias: str, file: str | None = None, timeout: int = 20) -> dict:
    """Zapisuje kopię zasobu. `file` to lokalny plik do skopiowania (praca bez sieci); inaczej pobieramy z URL-a.

    Zabezpieczenia (to narzędzie dostępne dla agenta): plik z dysku musi być skryptem/stylem/fontem o rozszerzeniu zgodnym z URL-em,
    rozmiar jest ograniczony, a typ pobranego zasobu wynika z odpowiedzi, nie tylko z końcówki adresu.
    """
    url = resolve_url(url_or_alias)
    if not re.match(r"^https?://", url):
        raise common.StudioError(f"'{url_or_alias}' nie jest adresem http(s) ani znanym skrótem ({', '.join(ALIASES)})")
    url_ext = Path(url.split("?")[0].split("#")[0]).suffix.lower()
    vendor_dir().mkdir(parents=True, exist_ok=True)
    if file:
        src = Path(file)
        ext = src.suffix.lower()
        if not src.is_file():
            raise common.StudioError(f"brak pliku: {src}")
        if ext not in _FILE_EXT:
            raise common.StudioError(f"z dysku kopiuję tylko skrypty, style i fonty ({', '.join(sorted(_FILE_EXT))}), a nie '{ext or 'plik bez rozszerzenia'}'")
        if url_ext in _FILE_EXT and url_ext != ext:
            raise common.StudioError(f"plik {ext} nie pasuje do adresu zakończonego {url_ext}")
        if src.stat().st_size > MAX_BYTES:
            raise common.StudioError(f"plik większy niż {MAX_BYTES // 1_000_000} MB")
        data = src.read_bytes()
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vstudio-vendor"})
            with urllib.request.urlopen(req, timeout=timeout) as r:                      # noqa: S310 - adres podaje użytkownik
                data = r.read(MAX_BYTES + 1)
                ctype = r.headers.get_content_type()
        except Exception as exc:  # noqa: BLE001
            raise common.StudioError(f"nie udało się pobrać {url}: {exc}. Bez sieci podaj lokalny plik (--file).") from exc
        if len(data) > MAX_BYTES:
            raise common.StudioError(f"zasób większy niż {MAX_BYTES // 1_000_000} MB")
        ext = url_ext if url_ext in _NET_EXT else _CT_EXT.get(ctype, "")
        if not ext:
            raise common.StudioError(f"nie rozpoznano typu zasobu (Content-Type: {ctype}); przechowuję skrypty, style, fonty i proste obrazy")
    name = hashlib.sha256(url.encode()).hexdigest()[:12] + ext
    dest = vendor_dir() / name
    dest.write_bytes(data)
    idx = load_index()
    idx[url] = name
    _save_index(idx)
    return {"url": url, "file": name, "bytes": dest.stat().st_size}


def remove(url_or_alias: str) -> dict:
    url = resolve_url(url_or_alias)
    idx = load_index()
    name = idx.pop(url, None)
    if name:
        (vendor_dir() / name).unlink(missing_ok=True)
        _save_index(idx)
    return {"removed": bool(name), "url": url}


def listing() -> list[dict]:
    idx = load_index()
    return [{"url": u, "file": n, "bytes": (vendor_dir() / n).stat().st_size if (vendor_dir() / n).exists() else 0} for u, n in sorted(idx.items())]


def content_type(name: str) -> str:
    return _MIME.get(Path(name).suffix.lower(), "application/octet-stream")


def read_file(name: str) -> bytes | None:
    """Plik z vendora po nazwie (z obroną przed ../)."""
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    f = vendor_dir() / name
    return f.read_bytes() if f.is_file() else None


def install_routes(target) -> bool:
    """Podpina podmianę żądań do zewnętrznych URL-i z vendora pod kontekst/stronę Playwrighta. Zwraca, czy jest co podmieniać."""
    idx = load_index()
    if not idx:
        return False

    def handler(route):
        name = idx.get(route.request.url)
        body = read_file(name) if name else None
        if body is None:
            route.continue_()
        else:
            route.fulfill(body=body, content_type=content_type(name), headers={"access-control-allow-origin": "*"})

    target.route(re.compile(r"^https?://(?!127\.0\.0\.1|localhost)"), handler)
    return True


def rewrite_html(html: str, prefix: str = "/vendor/") -> tuple[str, list[str]]:
    """Dla podglądu w przeglądarce: zamienia zvendorowane URL-e w HTML na lokalne. Zwraca (html, lista podmienionych URL-i)."""
    idx = load_index()
    swapped = []
    for url, name in idx.items():
        if url in html:
            html = html.replace(url, prefix + name)
            swapped.append(url)
    return html, swapped


def external_urls(html: str) -> list[str]:
    """Zewnętrzne zasoby, które strona ładuje z sieci (skrypty, style, fonty): kandydaci do vendora."""
    found = []
    for m in re.finditer(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def env() -> dict[str, str]:
    """Zmienne dla podprocesu renderera."""
    return {"VSTUDIO_VENDOR_INDEX": str(index_path())} if load_index() else {}


def status_for_html(html: str) -> dict:
    """Które zewnętrzne zasoby strony są pokryte vendorem, a które wymagają sieci."""
    idx = load_index()
    urls = external_urls(html)
    return {"external": urls, "vendored": [u for u in urls if u in idx], "needs_network": [u for u in urls if u not in idx]}
