"""Połączenie agenta ze studiem: konfiguracja MCP, test połączenia, instalacja skilla.

Agent (np. Claude Code) podłącza się przez serwer MCP `vstudio mcp` (stdio). Ten moduł mówi, jak to zrobić, sprawdza czy serwer
w ogóle startuje w tym środowisku (handshake JSON-RPC jak prawdziwy klient) i instaluje skill z instrukcją pracy.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from . import activity
from .common import ROOT, STUDIO, StudioError

SKILL_REL = Path("skills") / "vstudio" / "SKILL.md"


def mcp_command() -> list[str]:
    return [sys.executable, str(STUDIO / "vstudio.py"), "mcp"]


def connect_info() -> dict:
    cmd = mcp_command()
    quoted = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    mcp_json = {"mcpServers": {"vstudio": {"command": cmd[0], "args": cmd[1:]}}}
    skill_project = ROOT / ".claude" / "skills" / "vstudio" / "SKILL.md"
    skill_user = Path.home() / ".claude" / "skills" / "vstudio" / "SKILL.md"
    mcp_file = ROOT / ".mcp.json"
    configured = False
    if mcp_file.exists():
        try:
            configured = "vstudio" in json.loads(mcp_file.read_text(encoding="utf-8")).get("mcpServers", {})
        except ValueError:
            configured = False
    return {"command": cmd, "claude_code": f"claude mcp add vstudio -- {quoted}", "mcp_json": mcp_json,
            "mcp_json_path": str(mcp_file), "mcp_configured": configured,
            "skill": {"project_path": str(skill_project), "user_path": str(skill_user),
                      "installed_project": skill_project.exists(), "installed_user": skill_user.exists()},
            "agent": activity.agent_status()}


def selftest(timeout: float = 25.0) -> dict:
    """Uruchamia `vstudio mcp` i robi handshake (initialize, tools/list, ping). Dowodzi, że agent będzie mógł się połączyć."""
    t0 = time.time()
    proc = subprocess.Popen(mcp_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    try:
        def rpc(i: int, method: str, params: dict | None = None) -> dict:
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                raise StudioError("serwer MCP zamknął połączenie: " + (proc.stderr.read() or "")[-300:])
            return json.loads(line)

        init = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "vstudio-selftest", "version": "1"}})
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        tools = rpc(2, "tools/list")["result"]["tools"]
        rpc(3, "ping")
        return {"ok": True, "server": init["result"]["serverInfo"], "protocol": init["result"]["protocolVersion"], "tools": len(tools),
                "ms": int((time.time() - t0) * 1000)}
    except (StudioError, KeyError, ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)[:400], "ms": int((time.time() - t0) * 1000)}
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def skill_text() -> str:
    from . import skillgen

    return skillgen.render()


def install(skill: bool = True, mcp_config: bool = True, scope: str = "project") -> dict:
    if scope not in ("project", "user"):
        raise StudioError("scope: project albo user")
    done: dict = {}
    if skill:
        dest = (ROOT if scope == "project" else Path.home()) / ".claude" / "skills" / "vstudio" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(skill_text(), encoding="utf-8")
        done["skill"] = str(dest)
    if mcp_config:
        f = ROOT / ".mcp.json"
        data = {}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise StudioError(f"{f} nie jest poprawnym JSON-em: {exc}") from exc
        data.setdefault("mcpServers", {})["vstudio"] = connect_info()["mcp_json"]["mcpServers"]["vstudio"]
        f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        done["mcp_config"] = str(f)
    if not done:
        raise StudioError("nic do zainstalowania: włącz skill i/lub mcp_config")
    return {"installed": done, "note": "Uruchom ponownie agenta (albo zatwierdź serwer vstudio w jego ustawieniach MCP), żeby połączenie zadziałało."}
