"""Local FrameCore editor. Reuse vstudio HTTP boundaries and file serving."""
from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image
from http.server import ThreadingHTTPServer
from vstudio.dashboard.server import Handler as StudioHandler
from .api import API
from .composition import compile_project
from .model import EditorError, uid
from .motion import registry
from .render import RenderJobs, probe

STATIC = Path(__file__).parent / "static"
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


def import_asset(store, pid, data, filename, role="media", expected_revision=None, actor="human"):
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_TYPES or not data or len(data) > 100_000_000:
        raise EditorError("Dodaj PNG/JPG/WebP, MP4/WebM/MOV lub WAV/MP3/M4A do 100 MB")
    pdir = store.directory(pid)
    # Confirm the project exists before writing a file.
    state = store.read(pid)
    aid = uid("asset")
    file = f"assets/{aid}{suffix}"
    path = pdir / file
    path.write_bytes(data)
    try:
        kind = MEDIA_TYPES[suffix].split("/")[0]
        duration = None
        has_audio = False
        if kind == "image":
            with Image.open(path) as image:
                image.verify()
        else:
            info = probe(path)
            streams = info["streams"]
            has_audio = any(s["codec_type"] == "audio" for s in streams)
            if kind == "video" and not any(s["codec_type"] == "video" for s in streams) or kind == "audio" and not any(s["codec_type"] == "audio" for s in streams):
                raise EditorError("Zawartość pliku nie odpowiada typowi materiału")
            duration = float(info["format"]["duration"])
        a = {"id": aid, "name": Path(filename).name[:200], "kind": kind, "file": file, "mime": MEDIA_TYPES[suffix],
             "duration": duration, "hasAudio": has_audio, "role": role, "provenance": {"source": "user_upload"}, "license": "user_provided"}
        return store.execute(pid, "add_asset", {"asset": a}, expected_revision if expected_revision is not None else state["project"]["revision"], actor)
    except Exception:
        path.unlink(missing_ok=True)
        raise


class Handler(StudioHandler):
    def _route_get(self, path, qs):
        store = self.server.store
        try:
            if path in {"/", "/index.html"}:
                html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", self.token)
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if path.startswith("/static/"):
                file = (STATIC / path.removeprefix("/static/")).resolve()
                if not file.is_relative_to(STATIC.resolve()) or not file.is_file() or file.suffix not in {".js", ".css", ".svg", ".ttf", ".png"}:
                    return self._err(404, "Nie znaleziono")
                return self._send(200, file.read_bytes(), mimetypes.guess_type(file)[0] or "application/octet-stream")
            if path == "/api/projects": return self._json(200, {"projects": store.list()})
            if path == "/api/motion": return self._json(200, {"components": registry()})
            if path == "/api/tools": return self._json(200, {"tools": self.server.api.tools()})
            if path.startswith("/api/project/"): return self._json(200, store.read(path.split("/")[-1]))
            if path.startswith("/api/context/"): return self._json(200, store.context(path.split("/")[-1]))
            if path.startswith("/api/job/"): return self._json(200, self.server.jobs.get(path.split("/")[-1]))
            if path.startswith("/composition/"):
                pid = path.split("/")[-1]
                return self._send(200, compile_project(store.read(pid)["project"], f"/assets/{pid}/").encode(), "text/html; charset=utf-8")
            if path.startswith("/assets/"):
                _, _, pid, name = path.split("/")
                p = store.read(pid)["project"]
                a = next((a for a in p["assets"] if Path(a["file"]).name == name), None)
                if not a: return self._err(404, "Nie znaleziono materiału")
                return self._file(store.directory(pid) / a["file"])
            if path.startswith("/exports/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4 or parts[-1] not in {"framecore.mp4", "delivery.zip"}: return self._err(404, "Nie znaleziono")
                from .model import identifier
                identifier(parts[2])
                file = store.directory(parts[1]) / "exports" / parts[2] / parts[-1]
                if not file.is_file(): return self._err(404, "Nie znaleziono")
                return self._file(file)
            if path.startswith("/reviews/"):
                parts = path.strip("/").split("/")
                import re
                from .model import identifier
                if len(parts) != 4 or not re.fullmatch(r"frame-\d{3}\.png|contact-sheet\.jpg|review\.json",parts[-1]):
                    return self._err(404,"Nie znaleziono klatki")
                identifier(parts[2])
                file = store.directory(parts[1])/"reviews"/parts[2]/parts[-1]
                if not file.is_file(): return self._err(404,"Nie znaleziono klatki")
                return self._file(file)
            return self._err(404, "Nie znaleziono")
        except (EditorError, ValueError) as exc:
            return self._json(404 if getattr(exc,"code",None)=="not_found" else 400, {"error": str(exc), "code": getattr(exc,"code","invalid_request")})

    def do_POST(self):
        if not self._host_ok(): return self._err(403, "Nieprawidłowy Host")
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""): return self._err(403, "Nieprawidłowy Origin")
        if not hmac.compare_digest(self.headers.get("X-Studio-Token", ""), self.token): return self._err(403, "Wymagany token sesji")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            path = unquote(urlparse(self.path).path)
            if length < 0 or length > (100_000_000 if path.startswith("/api/upload/") else 4_000_000): return self._err(413, "Żądanie jest zbyt duże")
            if path.startswith("/api/upload/"):
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                result = import_asset(self.server.store, path.split("/")[-1], self.rfile.read(length),
                                      qs.get("name", ["upload"])[0], qs.get("role", ["media"])[0], int(qs["revision"][0]))
            else:
                if not self.headers.get("Content-Type", "").startswith("application/json"): return self._err(415, "Wymagana treść JSON")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict): raise EditorError("Treść żądania musi być obiektem")
                if path == "/api/demo":
                    from .demo import create_demo
                    result = create_demo(self.server.store)
                elif path == "/api/create": result = self.server.api.call("create_project", body, "human")
                elif path == "/api/command": result = self.server.api.call(body["name"], body.get("args", {}), "human")
                elif path == "/api/export": result = self.server.api.call("export", body, "human")
                else: return self._err(404, "Nie znaleziono")
            self._json(200, result)
        except (EditorError, KeyError, ValueError, TypeError) as exc:
            self._json(409 if getattr(exc,"code",None)=="revision_conflict" else 400, {"error": str(exc), "code": getattr(exc,"code","invalid_request")})
        except Exception as exc:
            self._json(500, {"error": str(exc), "code": "internal_error"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, store, port=8877):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(24)
        self.store = store
        self.jobs = RenderJobs(store)
        self.api = API(store, self.jobs)


def start_background(store, port=0):
    server = Server(store, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def serve(host="127.0.0.1", port=8765, open_browser=False):
    from .store import Store
    if host not in {"127.0.0.1", "localhost"}:
        raise EditorError("FrameCore działa wyłącznie na localhost")
    server = Server(Store(), port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"TABASCO FRAMECORE STUDIO: {url}", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
