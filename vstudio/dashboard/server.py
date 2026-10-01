"""Serwer dashboardu: lokalny interfejs do generowania filmów z nadzorem jakości i podglądem pracy agenta.

Wszystko, co robi interfejs, przechodzi przez ten sam rejestr możliwości co agent (`POST /api/call/<operacja>`), więc widok i agent
nie mogą się rozjechać. Serwer słucha WYŁĄCZNIE na localhost, bo dashboard zmienia pliki projektów. Zabezpieczenia:
  - nagłówek Host musi wskazywać localhost/127.0.0.1 (obrona przed DNS rebinding),
  - POST wymaga Content-Type: application/json (blokuje „proste” żądania międzydomenowe), zgodnego Origin i tokenu sesji,
  - pliki projektów są serwowane tylko z katalogu projektu (bez ../), tylko znane typy,
  - podgląd scen wstrzykuje `window.__CAPTURE__ = true`, żeby strona czekała na `seek` (to, co widzisz, to to, co się wyrenderuje).
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__, activity, common, jobs, ops, registry, vendor, workspace  # noqa: F401  (ops wypełnia rejestr)
from ..common import OUTPUT, StudioError
from .watcher import Watcher

STATIC = Path(__file__).resolve().parent / "static"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".m4a", ".wav", ".json", ".md", ".txt", ".html", ".css", ".js", ".woff2"}
_HOST_OK = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
MAX_BODY = 4_000_000                        # scena do ~2 MB + narzut JSON


#: Scena (kod agenta/szablonu) jest NIEUFNA. Sandbox bez allow-same-origin daje jej nieprzezroczysty origin: skrypt sceny nie przeczyta
#: tokenu z dashboardu, nie wywoła jego API i nie sięgnie do okna rodzica. Sterowanie odbywa się przez postMessage (most poniżej).
PREVIEW_HEADERS = {"Content-Security-Policy": "sandbox allow-scripts"}

BRIDGE = """<script>(function () {
  var NAMES = ['seek', 'renderFrame', 'draw', 'render'];
  function api() { var n = NAMES.find(function (x) { return typeof window[x] === 'function'; }); return n ? window[n] : null; }
  addEventListener('message', function (e) {
    var m = e.data; if (!m || m.vstudio !== 'req' || e.source !== parent) return;
    var reply = function (o) { o.vstudio = 'res'; o.id = m.id; parent.postMessage(o, e.origin === 'null' ? '*' : e.origin); };
    if (m.op === 'info') {
      Promise.race([Promise.resolve(window.__ready), new Promise(function (r) { setTimeout(r, 6000); })]).catch(function () {}).then(function () {
        reply({ ok: true, hasSeek: !!api(), dur: typeof window.DURATION === 'number' ? window.DURATION : (typeof window.DUR === 'number' ? window.DUR : null) });
      });
    } else if (m.op === 'seek') {
      var f = api(); if (!f) return reply({ ok: false, error: 'brak window.seek' });
      try { f(m.t); if (m.ack) reply({ ok: true }); } catch (err) { reply({ ok: false, error: String(err && err.message || err) }); }
    }
  });
})();</script>"""


def _inject(html: str, capture: bool) -> str:
    """Do podglądu: lokalne kopie bibliotek z vendora i (opcjonalnie) tryb capture, żeby scenę sterował dashboard przez seek."""
    html, _ = vendor.rewrite_html(html)
    if capture:
        tag = "<script>window.__CAPTURE__ = true;</script>" + BRIDGE
        m = re.search(r"<head[^>]*>", html, flags=re.I)
        html = html[:m.end()] + tag + html[m.end():] if m else tag + html
    return html


class Handler(BaseHTTPRequestHandler):
    server_version = f"vstudio-dashboard/{__version__}"
    protocol_version = "HTTP/1.1"

    # ---- wspólne
    def log_message(self, fmt, *args):          # cisza: aktywność i tak trafia do activity.jsonl
        pass

    @property
    def token(self) -> str:
        return self.server.token                 # type: ignore[attr-defined]

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _err(self, code: int, msg: str) -> None:
        self._json(code, {"error": msg})

    def _host_ok(self) -> bool:
        return bool(_HOST_OK.match(self.headers.get("Host", "")))

    # ---- GET
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            return self._err(403, "niedozwolony nagłówek Host (dashboard działa tylko na localhost)")
        url = urlparse(self.path)
        path, qs = unquote(url.path), parse_qs(url.query)
        try:
            return self._route_get(path, qs)
        except StudioError as exc:
            return self._err(404, str(exc))
        except Exception as exc:  # noqa: BLE001 - serwer ma przeżyć błąd w pojedynczym żądaniu
            return self._err(500, f"błąd wewnętrzny: {exc}")

    def _route_get(self, path: str, qs: dict) -> None:
        if True:
            if path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", self.token).replace("__VERSION__", __version__)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/capabilities":
                return self._json(200, {"categories": [{"id": c, "title": t} for c, t in registry.CATEGORIES], "capabilities": registry.describe()})
            if path == "/api/pulse":
                return self._json(200, self._pulse(int(qs.get("since", ["0"])[0] or 0)))
            if path.startswith("/files/"):
                return self._project_file(path[len("/files/"):])
            if path.startswith("/preview/"):
                return self._preview(path[len("/preview/"):], live="live" in qs)
            if path.startswith("/template/"):
                return self._template(path[len("/template/"):], live="live" in qs)
            if path.startswith("/vendor/"):
                body = vendor.read_file(path[len("/vendor/"):])
                if body is None:
                    return self._err(404, "brak pliku vendor")
                return self._send(200, body, vendor.content_type(path))         # bez CORS: podgląd ładuje to jako zwykły skrypt
        self._err(404, "nie ma takiej ścieżki")

    def _static(self, rel: str) -> None:
        f = (STATIC / rel).resolve()
        if not f.is_file() or not f.is_relative_to(STATIC.resolve()):
            return self._err(404, "brak pliku")
        self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")

    def _pulse(self, since: int) -> dict:
        """Lekki puls dla odpytywania: nowe zdarzenia, stan agenta, działające joby i znaczniki zmian projektów (mtime sceny)."""
        running = [j for j in jobs.listing(limit=10) if j["status"] == "running" or (j["finished"] or 0) > time.time() - 120]
        marks = {p["id"]: {"updated": p["updated"], "verdict": (p["check"] or {}).get("verdict"), "round": (p["check"] or {}).get("round")}
                 for p in workspace.list_projects()}
        return {"now": time.time(), "events": activity.tail(40, since), "agent": activity.agent_status(), "jobs": running, "projects": marks,
                "open_tasks": len(workspace.tasks_list("open")) + len(workspace.tasks_list("in_progress"))}

    def _project_dir(self, pid: str) -> Path:
        pdir, _ = workspace.resolve(pid)
        return pdir

    def _split_pid(self, rest: str) -> tuple[str, str]:
        parts = rest.split("/", 2)
        if len(parts) < 2:
            raise StudioError("niepełna ścieżka")
        return f"{parts[0]}/{parts[1]}", parts[2] if len(parts) > 2 else ""

    def _project_file(self, rest: str) -> None:
        pid, rel = self._split_pid(rest)
        pdir = self._project_dir(pid)
        f = (pdir / rel).resolve()
        if not f.is_file() or not f.is_relative_to(pdir.resolve()) or f.suffix.lower() not in ALLOWED_EXT or any(part.startswith(".") for part in Path(rel).parts):
            return self._err(404, "brak pliku")
        self._file(f)

    def _file(self, f: Path) -> None:
        """Plik z obsługą Range (potrzebne do przewijania wideo w przeglądarce)."""
        size = f.stat().st_size
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng and (m := re.match(r"bytes=(\d*)-(\d*)$", rng.strip())):
            a, b = m.groups()
            if a == "" and b:
                start = max(size - int(b), 0)
            elif a:
                start = int(a)
                end = min(int(b), size - 1) if b else size - 1
            if start > end or start >= size:
                return self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(f, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(65536, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def _preview(self, rest: str, live: bool) -> None:
        """Scena projektu do iframe: /preview/<marka>/<slug>/ albo /preview/<marka>/<slug>/<plik z src/>."""
        pid, rel = self._split_pid(rest)
        pdir = self._project_dir(pid)
        src = (pdir / "src").resolve()
        f = (src / (rel or "index.html")).resolve()
        if not f.is_file() or not f.is_relative_to(src) or any(p.startswith(".") for p in Path(rel).parts):
            return self._err(404, "brak pliku sceny")
        if f.suffix.lower() in (".html", ".htm"):
            return self._send(200, _inject(f.read_text(encoding="utf-8"), capture=not live).encode("utf-8"), "text/html; charset=utf-8", PREVIEW_HEADERS)
        if f.suffix.lower() not in ALLOWED_EXT:
            return self._err(404, "niedozwolony typ pliku")
        self._file(f)

    def _template(self, rest: str, live: bool) -> None:
        tid = rest.strip("/").split("/")[0]
        if not re.fullmatch(r"[a-z0-9-]+", tid or ""):
            return self._err(404, "zły szablon")
        html = workspace.template_html(tid)
        self._send(200, _inject(html, capture=not live).encode("utf-8"), "text/html; charset=utf-8", PREVIEW_HEADERS)

    # ---- POST
    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            return self._err(403, "niedozwolony nagłówek Host")
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            return self._err(403, "niedozwolony Origin")
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            return self._err(415, "wymagany Content-Type: application/json")
        if not hmac.compare_digest(self.headers.get("X-Studio-Token", ""), self.token):
            return self._err(403, "brak albo zły token sesji (odśwież stronę)")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._err(413, "za duże żądanie")
        try:
            args = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._err(400, "niepoprawny JSON")
        path = unquote(urlparse(self.path).path)
        m = re.fullmatch(r"/api/call/([a-z_]+)", path)
        if not m:
            return self._err(404, "nie ma takiej ścieżki")
        try:
            res = registry.call(m.group(1), args, source="dashboard")
        except registry.CapabilityError as exc:
            return self._err(400, str(exc))
        except Exception as exc:  # noqa: BLE001 - serwer ma przeżyć błąd operacji
            return self._err(500, f"błąd wewnętrzny: {exc}")
        for im in res.get("images", []) or []:
            if im.get("project") and im.get("rel"):
                im["url"] = f"/files/{im['project']}/{im['rel']}?v={int(time.time())}"
        self._json(200, res)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        """Przeglądarka przerywa połączenia przy nawigacji (BrokenPipe, reset): to normalne, nie zaśmiecamy konsoli śladami."""
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)

    def __init__(self, host: str, port: int):
        super().__init__((host, port), Handler)
        self.token = secrets.token_urlsafe(18)


def start_background(port: int = 0, watch: bool = False) -> tuple[DashboardServer, threading.Thread]:
    """Do testów: serwer na wolnym porcie w wątku (watch=True uruchamia też automatyczny nadzór)."""
    common.SERVICE_MODE = True
    srv = DashboardServer("127.0.0.1", port)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    if watch:
        srv.watcher = Watcher(interval=0.5)             # type: ignore[attr-defined]
        srv.watcher.start()                              # type: ignore[attr-defined]
    return srv, th


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise StudioError("dashboard słucha tylko na localhost: zmienia pliki projektów, więc nie wystawiamy go do sieci")
    common.SERVICE_MODE = True
    OUTPUT.mkdir(exist_ok=True)
    srv = None
    for p in range(port, port + 20):
        try:
            srv = DashboardServer(host, p)
            break
        except OSError:
            continue
    if srv is None:
        raise StudioError(f"porty {port}-{port + 19} są zajęte")
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"vstudio dashboard: {url}   (Ctrl+C kończy)", flush=True)
    srv.watcher = Watcher()                              # type: ignore[attr-defined]
    srv.watcher.start()                                  # type: ignore[attr-defined]
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nkoniec.")
    finally:
        jobs.shutdown()                                   # nie zostawiamy osieroconych renderów po zamknięciu dashboardu
        srv.server_close()
    return 0
