"""Log aktywności studia: kto (agent przez MCP, dashboard, CLI) wywołał jaką operację, ile trwała i czy się udała.

Plik JSONL w output/.studio/activity.jsonl. Dashboard pokazuje go na żywo (panel „Agent”), a status „agent połączony”
to po prostu: ostatnie wywołanie ze źródła `mcp` było niedawno.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import common

_LOCK = threading.Lock()
MAX_KEEP = 2000                 # przycinamy plik, żeby nie rósł bez końca


def _file() -> Path:
    return common.STATE_DIR / "activity.jsonl"


def record(source: str, kind: str, name: str, *, project: str | None = None, ok: bool = True, ms: int | None = None,
           summary: str = "", **extra) -> dict:
    """Dopisuje zdarzenie. `id` to czas w ns, więc rośnie monotonicznie i nadaje się do odpytywania `since`."""
    with _LOCK:
        ev = {"id": time.time_ns(), "ts": time.time(), "source": source, "kind": kind, "name": name, "project": project,
              "ok": bool(ok), "ms": ms, "summary": summary[:300], **extra}
        f = _file()
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        if f.stat().st_size > 4_000_000:
            lines = f.read_text(encoding="utf-8").splitlines()[-MAX_KEEP:]
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ev


def tail(limit: int = 50, since: int = 0, source: str | None = None) -> list[dict]:
    f = _file()
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines()[-MAX_KEEP:]:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev["id"] > since and (source is None or ev["source"] == source):
            out.append(ev)
    return out[-limit:]


def agent_status(window_s: float = 90.0) -> dict:
    """Czy agent (źródło `mcp`) jest podłączony: liczymy połączenie aktywnym, gdy jego ostatnie zdarzenie jest świeże."""
    last = tail(limit=1, source="mcp")
    if not last:
        return {"connected": False, "last_seen": None, "seconds_ago": None, "last_call": None}
    ev = last[-1]
    ago = max(0.0, time.time() - ev["ts"])
    return {"connected": ago <= window_s, "last_seen": ev["ts"], "seconds_ago": round(ago, 1), "last_call": ev["name"]}
