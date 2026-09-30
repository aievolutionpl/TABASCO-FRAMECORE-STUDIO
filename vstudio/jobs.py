"""Joby: długie operacje (render, dźwięk, wydanie) uruchamiane jako osobny proces z postępem i logiem.

Serwer MCP i dashboard nie mogą blokować się na renderze, więc render to podproces `vstudio.py <komenda>`; wątek czyta jego
wyjście, wyciąga postęp z linii `frame i/N` i zapisuje stan w output/.studio/jobs/<id>.json (dashboard odpytuje, agent woła
`job_wait`). Zadanie można anulować. Po restarcie serwera dawne joby zostają w historii jako zakończone lub „lost”.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import activity, common, vendor
from .common import STUDIO, StudioError

_LOCK = threading.Lock()
_PROCS: dict[str, subprocess.Popen] = {}
_LIVE: dict[str, dict] = {}            # działające joby: jeden wspólny obiekt dla wątku czytającego wyjście i dla cancel()
_PROGRESS = re.compile(r"frame\s+(\d+)\s*/\s*(\d+)")


def _dir() -> Path:
    d = common.STATE_DIR / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(job: dict) -> None:
    f = _dir() / f"{job['id']}.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def get(job_id: str) -> dict:
    if not re.fullmatch(r"J-[0-9a-f]{8}", job_id or ""):
        raise StudioError(f"niepoprawny identyfikator joba '{job_id}'")
    if job_id in _LIVE:
        return dict(_LIVE[job_id])
    f = _dir() / f"{job_id}.json"
    if not f.exists():
        raise StudioError(f"brak joba {job_id}")
    job = json.loads(f.read_text(encoding="utf-8"))
    if job["status"] == "running" and job_id not in _PROCS:
        job.update(status="lost", message="serwer został zrestartowany w trakcie joba", finished=job.get("finished") or time.time())
    return job


def listing(project: str | None = None, limit: int = 30) -> list[dict]:
    rows = []
    for f in sorted(_dir().glob("J-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit * 3]:
        try:
            j = get(f.stem)
        except (StudioError, ValueError):
            continue
        if project is None or j["project"] == project:
            rows.append(j)
    return rows[:limit]


def log_tail(job_id: str, lines: int = 40) -> str:
    f = _dir() / f"{job_id}.log"
    return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]) if f.exists() else ""


def start(kind: str, project_id: str, pdir: Path, args: list[str], source: str = "api") -> dict:
    """Uruchamia `vstudio.py <args>` jako job. `args` bez interpretera i bez ścieżki skryptu."""
    job_id = f"J-{os.urandom(4).hex()}"
    log_file = _dir() / f"{job_id}.log"
    cmd = [sys.executable, str(STUDIO / "vstudio.py"), *args]
    env = {**os.environ, **vendor.env(), "PYTHONUNBUFFERED": "1"}
    job = {"id": job_id, "kind": kind, "project": project_id, "cmd": " ".join(args), "status": "running", "progress": 0.0,
           "message": "start", "started": time.time(), "finished": None, "result": None, "source": source}
    with _LOCK:
        _save(job)
    try:
        proc = subprocess.Popen(cmd, cwd=str(STUDIO), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
    except OSError as exc:
        job.update(status="failed", message=str(exc), finished=time.time())
        _save(job)
        raise StudioError(f"nie udało się uruchomić joba: {exc}") from exc
    _PROCS[job_id] = proc
    _LIVE[job_id] = job
    activity.record(source, "job", f"{kind} start", project=project_id, summary=job["cmd"])
    threading.Thread(target=_pump, args=(job, proc, log_file, pdir), daemon=True).start()
    return job


def _pump(job: dict, proc: subprocess.Popen, log_file: Path, pdir: Path) -> None:
    last = ""
    with open(log_file, "w", encoding="utf-8") as lf:
        for line in proc.stdout:          # type: ignore[union-attr]
            lf.write(line)
            lf.flush()
            line = line.strip()
            if not line:
                continue
            last = line
            m = _PROGRESS.search(line)
            if m:
                job["progress"] = round(min(int(m.group(1)) / max(int(m.group(2)), 1), 0.99), 3)
            job["message"] = line[:200]
            _save(job)
    rc = proc.wait()
    job["finished"] = time.time()
    if job["status"] == "cancelled":
        pass
    elif rc == 0:
        job.update(status="done", progress=1.0, message="gotowe", result=_result(job, pdir, last))
    else:
        job.update(status="failed", message=(last or f"kod wyjścia {rc}")[:300])
    _save(job)
    _PROCS.pop(job["id"], None)
    _LIVE.pop(job["id"], None)
    activity.record(job["source"], "job", f"{job['kind']} {job['status']}", project=job["project"], ok=job["status"] == "done", summary=job["message"])


def _result(job: dict, pdir: Path, last_line: str) -> dict:
    res: dict = {"output": last_line}
    if job["kind"] in ("render", "sound"):
        fresh = [f for f in (pdir / "renders").glob("*.mp4") if f.stat().st_mtime >= job["started"] - 1]
        if fresh:
            newest = max(fresh, key=lambda f: f.stat().st_mtime)
            res["file"] = f"renders/{newest.name}"
            res["mb"] = round(newest.stat().st_size / 1e6, 2)
    elif job["kind"] == "deliver":
        d = pdir / "final"
        res["files"] = [f"final/{f.name}" for f in sorted(d.glob("*")) if f.is_file()] if d.exists() else []
    return res


def cancel(job_id: str) -> dict:
    job = get(job_id)
    proc, live = _PROCS.get(job_id), _LIVE.get(job_id)
    if job["status"] != "running" or proc is None or live is None:
        return job
    live.update(status="cancelled", message="anulowano", finished=time.time())
    _save(live)
    proc.terminate()
    return dict(live)


def wait(job_id: str, timeout: float = 60.0) -> dict:
    """Czeka na zakończenie joba (maks. `timeout` s) i zwraca jego stan; agent woła to po render_start."""
    end = time.time() + timeout
    while True:
        job = get(job_id)
        if job["status"] != "running" or time.time() >= end:
            return job
        time.sleep(0.4)
