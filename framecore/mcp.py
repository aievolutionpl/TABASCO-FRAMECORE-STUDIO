"""MCP stdio transport reuses the vstudio protocol loop and FrameCore API."""
from vstudio.mcp_server import McpServer, RpcError, SUPPORTED
from . import __version__
from .model import EditorError


class FrameCoreMCP(McpServer):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def _dispatch(self, method, params):
        if method == "initialize":
            self.initialized = True
            self.protocol = params.get("protocolVersion") if params.get("protocolVersion") in SUPPORTED else SUPPORTED[0]
            return {"protocolVersion": self.protocol, "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "tabasco-framecore", "version": __version__},
                    "instructions": "Przeczytaj get_editing_guide, get_selection i get_project. UI i MCP mają wspólną historię cofania. Używaj expected_revision. Duże zmiany przygotuj jako propozycję. Obejrzyj capture_frame i inspect_project. Dostawcy wymagają konfiguracji."}
        if method == "ping" or method.startswith("notifications/"): return {}
        if not self.initialized: raise RpcError(-32002, "Najpierw wywołaj initialize")
        if method == "tools/list": return {"tools": self.api.tools()}
        if method == "tools/call":
            import json
            try:
                result = self.api.call(params["name"], params.get("arguments", {}), actor="agent")
                if params["name"] == "capture_frame":
                    data = result.pop("data")
                    return {"content":[{"type":"text", "text":json.dumps(result,ensure_ascii=False)},
                                       {"type":"image", "mimeType":"image/png", "data":data}], "isError":False}
                if params["name"] in {"create_review", "get_review", "create_motion_strip"}:
                    import base64
                    sheet = self.api.store.directory(result["project_id"])/"reviews"/result["id"]/"contact-sheet.jpg"
                    content=[{"type":"text","text":json.dumps(result,ensure_ascii=False)},
                             {"type":"image","mimeType":"image/jpeg","data":base64.b64encode(sheet.read_bytes()).decode()}]
                    if result.get("onionUrl"):
                        onion=sheet.parent/"onion.png"
                        content.append({"type":"image","mimeType":"image/png","data":base64.b64encode(onion.read_bytes()).decode()})
                    return {"content":content,"isError":False}
                return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}
            except (EditorError, KeyError, TypeError) as exc:
                return {"content": [{"type": "text", "text": json.dumps({"error": str(exc), "code": getattr(exc, "code", "invalid_arguments")})}], "isError": True}
        raise RpcError(-32601, "Nieznana metoda")
