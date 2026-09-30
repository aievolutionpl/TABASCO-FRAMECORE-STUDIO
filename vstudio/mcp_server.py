"""Serwer MCP (stdio) dla agenta: wystawia rejestr możliwości studia jako narzędzia, wiedzę i raporty jako zasoby, a pętle pracy jako prompty.

Protokół: JSON-RPC 2.0, jedna wiadomość JSON na linię (transport stdio z specyfikacji MCP). Zaimplementowany ręcznie na bibliotece
standardowej, więc nie dokłada zależności. stdout jest zarezerwowany dla protokołu: na czas obsługi żądań wszystko, co operacje
wypiszą przez print, trafia na stderr.

Uruchomienie: `python vstudio.py mcp`. Każde wywołanie narzędzia trafia do logu aktywności (źródło `mcp`), więc dashboard pokazuje
na żywo, co robi agent.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from . import __version__, common, knowledge, ops, registry, skillgen, supervisor, workspace  # noqa: F401  (ops wypełnia rejestr)
from .common import StudioError

SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_TEXT = 60_000
MAX_IMAGE_BYTES = 4_000_000
INSTRUCTIONS = ("vstudio: deterministic code-rendered video studio with a quality supervisor. Start with `studio_status`. "
                "Work loop: task_next -> project_create/scene_patch (with check) -> frames_view (LOOK at the film) -> check_run until verdict `pass` -> "
                "render_start + job_wait -> deliver_start. Read resource vstudio://skill or call knowledge_get for the rules.")

PROMPTS = {
    "make-video": {
        "description": "Zrób film od pomysłu do renderu: szablon, scena, nadzór, render.",
        "arguments": [{"name": "idea", "description": "O czym ma być film i dla kogo", "required": True},
                      {"name": "template", "description": "Opcjonalnie id szablonu z templates_list", "required": False}],
        "text": lambda a: ("Zrób film w vstudio.\n\nPomysł: {idea}\nSzablon (opcjonalnie): {template}\n\nPostępuj według pętli pracy: studio_status, knowledge_get "
                           "(brand, gsap, contract), project_create, edycja sceny z check, frames_view, check_run aż do werdyktu pass, render_start, job_wait. "
                           "Na końcu podsumuj, co powstało i które ostrzeżenia zostawiłeś świadomie.").format(idea=a.get("idea", ""), template=a.get("template") or "dobierz najbliższy"),
    },
    "fix-findings": {
        "description": "Napraw znaleziska ostatniej rundy nadzoru projektu.",
        "arguments": [{"name": "project", "description": "Id projektu (marka/slug)", "required": True}],
        "text": lambda a: (f"Projekt {a.get('project', '')}: uruchom check_latest, popraw błędy potem ostrzeżenia (scene_patch z check), patrz na klatki "
                           "(frames_view) i powtarzaj check_run, aż werdykt to pass albo zostaną tylko świadome ostrzeżenia (opisz je w task_update)."),
    },
    "onboard": {
        "description": "Przeprowadź onboarding: środowisko, marka, połączenie, pierwszy film.",
        "arguments": [],
        "text": lambda a: ("Przeprowadź onboarding vstudio: studio_status, popraw środowisko (doctor), zapytaj użytkownika o markę, paletę, font, ton, odbiorców i format, "
                           "zapisz profile_set, pokaż templates_list i zaproponuj pierwszy film."),
    },
}


def _tool_def(cap) -> dict:
    desc = cap.summary + (f" Use when: {cap.when}" if cap.when else "") + (f" Returns: {cap.returns}." if cap.returns else "")
    return {"name": cap.name, "title": cap.title, "description": desc, "inputSchema": cap.input_schema(),
            "annotations": {"title": cap.title, "readOnlyHint": not (cap.mutates or cap.job), "destructiveHint": False,
                            "idempotentHint": not (cap.mutates or cap.job), "openWorldHint": cap.name == "vendor_add"}}


def _image_blocks(res: dict) -> list[dict]:
    blocks = []
    for im in res.get("images", []) or []:
        p = Path(im["path"])
        if not p.is_file() or p.stat().st_size > MAX_IMAGE_BYTES:
            continue
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        blocks.append({"type": "text", "text": f"[{im.get('label', p.name)}]"})
        blocks.append({"type": "image", "data": base64.b64encode(p.read_bytes()).decode("ascii"), "mimeType": mime})
    return blocks


class McpServer:
    def __init__(self) -> None:
        self.initialized = False
        self.protocol = SUPPORTED[0]

    # ---- pojedyncze żądanie -> odpowiedź (None dla powiadomień)
    def handle(self, msg: dict) -> dict | None:
        if "method" not in msg:                      # odpowiedź klienta na nasze żądanie: nic nie wysyłamy
            return None
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        is_request = "id" in msg
        try:
            result = self._dispatch(method, params)
        except RpcError as exc:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": exc.code, "message": exc.message}} if is_request else None
        except Exception as exc:  # noqa: BLE001 - serwer nie może paść od błędu w narzędziu
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"internal error: {exc}"}} if is_request else None
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _dispatch(self, method: str | None, params: dict):
        if method == "initialize":
            want = params.get("protocolVersion")
            self.protocol = want if want in SUPPORTED else SUPPORTED[0]
            self.initialized = True
            return {"protocolVersion": self.protocol, "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False, "subscribe": False},
                                                                    "prompts": {"listChanged": False}},
                    "serverInfo": {"name": "vstudio", "title": "vstudio: studio filmowe", "version": __version__}, "instructions": INSTRUCTIONS}
        if method in ("notifications/initialized", "notifications/cancelled", "notifications/roots/list_changed"):
            return None
        if method == "ping":
            return {}
        if method == "logging/setLevel":
            return {}
        if method == "tools/list":
            return {"tools": [_tool_def(c) for c in registry.REGISTRY.values()]}
        if method == "tools/call":
            return self._call_tool(params.get("name"), params.get("arguments") or {})
        if method == "resources/list":
            return {"resources": self._resources()}
        if method == "resources/templates/list":
            return {"resourceTemplates": []}
        if method == "resources/read":
            return self._read_resource(params.get("uri", ""))
        if method == "prompts/list":
            return {"prompts": [{"name": n, "description": p["description"], "arguments": p["arguments"]} for n, p in PROMPTS.items()]}
        if method == "prompts/get":
            p = PROMPTS.get(params.get("name"))
            if not p:
                raise RpcError(-32602, f"nieznany prompt '{params.get('name')}'")
            return {"description": p["description"], "messages": [{"role": "user", "content": {"type": "text", "text": p["text"](params.get("arguments") or {})}}]}
        raise RpcError(-32601, f"method not found: {method}")

    def _call_tool(self, name: str | None, args: dict) -> dict:
        if name not in registry.REGISTRY:
            raise RpcError(-32602, f"unknown tool: {name}")
        try:
            res = registry.call(name, args, source="mcp")
        except registry.CapabilityError as exc:
            return {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}
        text = json.dumps({k: v for k, v in res.items() if k != "images"} | ({"images": [i.get("label") for i in res["images"]]} if res.get("images") else {}),
                          ensure_ascii=False, indent=1, default=str)
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT] + "\n... (obcięto; użyj węższego zapytania)"
        return {"content": [{"type": "text", "text": text}, *_image_blocks(res)], "structuredContent": {k: v for k, v in res.items() if k != "images"}, "isError": False}

    # ---- zasoby
    def _resources(self) -> list[dict]:
        out = [{"uri": "vstudio://skill", "name": "skill", "title": "Skill: instrukcja pracy ze studiem", "mimeType": "text/markdown"}]
        for t, (title, _) in knowledge.TOPICS.items():
            out.append({"uri": f"vstudio://knowledge/{t}", "name": f"knowledge-{t}", "title": title, "mimeType": "text/markdown"})
        for p in workspace.list_projects():
            out.append({"uri": f"vstudio://project/{p['id']}/brief", "name": f"brief-{p['slug']}", "title": f"Brief: {p['id']}", "mimeType": "text/markdown"})
            if p["check"]:
                out.append({"uri": f"vstudio://project/{p['id']}/report", "name": f"report-{p['slug']}", "title": f"Ostatni nadzór: {p['id']}", "mimeType": "application/json"})
        return out

    def _read_resource(self, uri: str) -> dict:
        try:
            if uri == "vstudio://skill":
                return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": skillgen.render()}]}
            if uri.startswith("vstudio://knowledge/"):
                k = knowledge.get(uri.rsplit("/", 1)[1])
                return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": k["text"]}]}
            if uri.startswith("vstudio://project/"):
                rest = uri[len("vstudio://project/"):]
                pid, kind = rest.rsplit("/", 1)
                pdir, _ = workspace.resolve(pid)
                if kind == "brief":
                    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": (pdir / "BRIEF.md").read_text(encoding="utf-8")}]}
                if kind == "report":
                    rep = supervisor.latest(pdir)
                    return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(rep, indent=1, ensure_ascii=False)}]}
        except (StudioError, OSError) as exc:
            raise RpcError(-32002, str(exc)) from exc
        raise RpcError(-32002, f"nieznany zasób: {uri}")

    # ---- pętla stdio
    def serve(self, stdin=None, stdout=None) -> None:
        stdin, out = stdin or sys.stdin, stdout or sys.stdout
        saved = sys.stdout
        sys.stdout = sys.stderr                     # print z operacji nie może zepsuć protokołu
        try:
            for line in stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    out.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
                    out.flush()
                    continue
                reply = [r for r in (self.handle(m) for m in msg) if r] if isinstance(msg, list) else self.handle(msg)
                if reply:
                    out.write(json.dumps(reply, ensure_ascii=False) + "\n")
                    out.flush()
        finally:
            sys.stdout = saved


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def main() -> int:
    common.SERVICE_MODE = True
    McpServer().serve()
    return 0
