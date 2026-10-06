"""Local FrameCore editor. Reuse vstudio HTTP boundaries and file serving."""
from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from http.server import ThreadingHTTPServer
from vstudio.dashboard.server import Handler as StudioHandler
from .api import API
from .composition import compile_project
from .model import EditorError
from .motion import registry
from .render import RenderJobs

STATIC = Path(__file__).parent / "static"
from .media_import import MEDIA_TYPES, import_asset


class Handler(StudioHandler):
    def _send(self, code, body, ctype, extra=None):
        # Rejected uploads can leave unread bytes. Never treat them as a second
        # HTTP request on a persistent POST connection.
        if self.command == "POST":
            self.close_connection = True
            extra = {**(extra or {}), "Connection": "close"}
        return super()._send(code, body, ctype, extra)

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
            if path == "/api/brands":
                from .brands import BrandLibrary
                return self._json(200, BrandLibrary(store).list())
            if path.startswith("/brand-assets/"):
                from .brands import BrandLibrary
                _, _, bid, aid = path.split("/")
                library = BrandLibrary(store)
                profile = library.get(bid)
                asset = next((a for a in profile["assets"] if a["id"] == aid), None)
                if not asset: return self._err(404, "Nie znaleziono materiału marki")
                return self._file(library.directory(bid) / asset["file"])
            if path == "/api/projects": return self._json(200, {"projects": store.list()})
            if path == "/api/assistant/status": return self._json(200, self.server.assistant.status())
            if path == "/api/runtime":
                from .runtime import diagnostics
                return self._json(200, diagnostics())
            if path == "/api/mcp-config":
                import sys
                root = Path(__file__).resolve().parents[1]
                return self._json(200, {"mcpServers":{"framecore":{"command":sys.executable,
                    "args":[str(root / 'framecore.py'), 'mcp', '--root', str(store.root.resolve())], 'cwd':str(root)}}})
            if path.startswith("/api/assistant/job/"): return self._json(200, self.server.assistant.get(path.split("/")[-1]))
            if path == "/api/motion":
                from .motion import exits
                from .production import EASINGS
                return self._json(200, {"components": registry(), "exits": exits(), "easings": sorted(EASINGS)})
            if path == "/api/tools": return self._json(200, {"tools": self.server.api.tools()})
            if path.startswith("/api/project/"): return self._json(200, store.read(path.split("/")[-1]))
            if path.startswith("/api/context/"): return self._json(200, store.context(path.split("/")[-1]))
            if path.startswith("/api/job/"): return self._json(200, self.server.jobs.get(path.split("/")[-1]))
            if path.startswith("/composition/"):
                pid = path.split("/")[-1]
                return self._send(200, compile_project(store.read(pid)["project"], f"/assets/{pid}/").encode(), "text/html; charset=utf-8")
            if path.startswith("/media/"):
                parts = path.strip('/').split('/')
                if len(parts) != 4:
                    return self._err(404, "Nie znaleziono pliku analizy")
                return self._file(self.server.api.media.artifact(parts[1], parts[2], parts[3]))
            if path.startswith("/assets/"):
                _, _, pid, name = path.split("/")
                p = store.read(pid)["project"]
                a = next((a for a in p["assets"] if Path(a["file"]).name == name), None)
                if not a: return self._err(404, "Nie znaleziono materiału")
                return self._file(store.directory(pid) / a["file"])
            if path.startswith("/exports/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4 or parts[-1] not in {"framecore.mp4", "delivery.zip", "quality-report.json"}: return self._err(404, "Nie znaleziono")
                from .model import identifier
                identifier(parts[2])
                file = store.directory(parts[1]) / "exports" / parts[2] / parts[-1]
                if not file.is_file(): return self._err(404, "Nie znaleziono")
                if parts[-1] == "quality-report.json":
                    from .quality import get_report
                    return self._json(200,get_report(store,self.server.jobs,parts[1],parts[2]))
                return self._file(file)
            if path.startswith("/reviews/"):
                parts = path.strip("/").split("/")
                import re
                from .model import identifier
                if len(parts) != 4 or not re.fullmatch(r"frame-\d{3}\.png|diff-\d{3}\.png|onion\.png|contact-sheet\.jpg|review\.json",parts[-1]):
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
            limit = 20_000_000 if path.startswith("/api/brand-upload/") else 100_000_000 if path.startswith("/api/upload/") else 4_000_000
            if length < 0 or length > limit: return self._err(413, "Żądanie jest zbyt duże")
            if path.startswith("/api/brand-upload/"):
                from urllib.parse import parse_qs
                from .brands import BrandLibrary
                qs = parse_qs(urlparse(self.path).query)
                result = BrandLibrary(self.server.store).upload(path.split("/")[-1], int(qs["version"][0]),
                    self.rfile.read(length), qs.get("name", ["upload"])[0], qs.get("role", ["reference"])[0])
            elif path.startswith("/api/upload/"):
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                result = import_asset(self.server.store, path.split("/")[-1], self.rfile.read(length),
                                      qs.get("name", ["upload"])[0], qs.get("role", ["media"])[0], int(qs["revision"][0]))
            else:
                if not self.headers.get("Content-Type", "").startswith("application/json"): return self._err(415, "Wymagana treść JSON")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict): raise EditorError("Treść żądania musi być obiektem")
                if path == "/api/agent/status": result=self.server.agent.status()
                elif path == "/api/agent/connect": result=self.server.agent.connect(body.get("provider"),body.get("model",""),body.get("api_key",""))
                elif path == "/api/agent/disconnect": result=self.server.agent.stop(disconnect=True)
                elif path == "/api/agent/stop": result=self.server.agent.stop()
                elif path == "/api/agent/brand-draft": result=self.server.agent.start_brand(body.get("profile"), body.get("notes"))
                elif path == "/api/agent/run": result=self.server.agent.start(body.get("project_id"),body.get("expected_revision"),body.get("prompt"),body.get("auto_apply",False))
                elif path == "/api/demo":
                    from .demo import create_demo
                    result = create_demo(self.server.store)
                elif path == "/api/create": result = self.server.api.call("create_project", body, "human")
                elif path == "/api/command": result = self.server.api.call(body["name"], body.get("args", {}), "human")
                elif path == "/api/export": result = self.server.api.call("export", body, "human")
                elif path == "/api/assistant/settings": result = self.server.assistant.save(body)
                elif path == "/api/assistant/test": result = self.server.assistant.test()
                elif path == "/api/assistant/models": result = self.server.assistant.models()
                elif path == "/api/assistant/run": result = self.server.assistant.start(body.get("project_id"), body.get("prompt"))
                elif path == "/api/assistant/cancel": result = self.server.assistant.cancel(body.get("job_id"))
                else: return self._err(404, "Nie znaleziono")
            self._json(200, result)
        except (EditorError, KeyError, ValueError, TypeError) as exc:
            self._json(409 if getattr(exc,"code",None)=="revision_conflict" else 400, {"error": str(exc), "code": getattr(exc,"code","invalid_request")})
        except Exception as exc:
            self._json(500, {"error": str(exc), "code": "internal_error"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128
    allow_reuse_address = True

    def __init__(self, store, port=8877):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(24)
        self.store = store
        self.jobs = RenderJobs(store)
        self.api = API(store, self.jobs)
        from .agent import AgentService
        self.assistant = AgentService(self.api)
        from .agent_control import AgentControl
        self.agent = AgentControl(store)


    def server_close(self):
        self.assistant.stop_all()
        self.agent.stop(disconnect=True)
        super().server_close()

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
