"""Joby: długie operacje (render, dźwięk, wydanie) uruchamiane jako osobny proces z postępem i logiem.

Serwer MCP i dashboard nie mogą blokować się na renderze, więc render to podproces `vstudio.py <komenda>`; wątek czyta jego
wyjście, wyciąga postęp z linii `frame i/N` i zapisuje stan w output/.studio/jobs/<id>.json. Ponieważ agent (proces MCP) i dashboard
to RÓŻNE procesy, stan joba jest czytelny i sterowalny z obu: liczy się plik stanu + PID, a nie tylko pamięć procesu, który job uruchomił.

Zasady:
  - w projekcie działa naraz jeden job (render, dźwięk i wydanie dotykają tych samych plików),
  - cancel zabija całe drzewo procesów (vstudio -> html_to_video -> ffmpeg) i usuwa urwane pliki (po migawce katalogu renders/ z chwili startu),
  - zamknięcie serwera przerywa jego joby (nie zostawiamy osieroconych renderów),
  - job, którego proces zniknął bez wyniku, dostaje trwały status `lost` (raz, nie przy każdym odczycie).
"""
from __future__ import annotations

import atexit
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import activity, common, vendor
from .common import STUDIO, StudioError
from .locking import atomic_write, file_lock

_PROCS: dict[str, subprocess.Popen] = {}
_LIVE: dict[str, dict] = {}            # działające joby TEGO procesu: jeden wspólny obiekt dla wątku czytającego wyjście i dla cancel()
_PROGRESS = re.compile(r"frame\s+(\d+)\s*/\s*(\d+)")


def _dir() -> Path:
    d = common.STATE_DIR / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(job_id: str) -> dict | None:
    f = _dir() / f"{job_id}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(job: dict) -> None:
    """Zapis stanu: pod blokadą, atomowo, i bez nadpisywania anulowania zapisanego przez inny proces (dashboard anuluje job agenta)."""
    with file_lock(_dir() / ".lock"):
        disk = _read(job["id"])
        if disk and disk.get("status") == "cancelled" and job["status"] == "running":
            job.update(status="cancelled", message=disk.get("message", "anulowano"), finished=disk.get("finished") or time.time())
        atomic_write(_dir() / f"{job['id']}.json", json.dumps(job, indent=2, ensure_ascii=False))


def _safe_save(job: dict) -> None:
    try:
        _save(job)
    except (OSError, TimeoutError):
        pass                                # błąd zapisu stanu nie może zatrzymać odczytu wyjścia (dziecko zablokowałoby się na pełnym pipe)


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                    # zombie (np. kontener bez reapera na PID 1) to już martwy proces
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def get(job_id: str) -> dict:
    if not re.fullmatch(r"J-[0-9a-f]{8}", job_id or ""):
        raise StudioError(f"niepoprawny identyfikator joba '{job_id}'")
    if job_id in _LIVE:
        return dict(_LIVE[job_id])
    job = _read(job_id)
    if job is None:
        raise StudioError(f"brak joba {job_id}")
    if job["status"] == "running" and not pid_alive(job.get("pid")):
        # proces zniknął bez zapisania wyniku: oznaczamy RAZ i trwale (inaczej `finished` odświeżałoby się przy każdym odczycie)
        job.update(status="lost", message="proces joba przestał istnieć (serwer zamknięty w trakcie?)", finished=time.time())
        _safe_save(job)
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
    busy = [j for j in listing(project_id) if j["status"] == "running"]
    if busy:
        raise StudioError(f"w projekcie {project_id} trwa już job: {busy[0]['kind']} ({busy[0]['id']}). Poczekaj na koniec albo go anuluj "
                          "(render, dźwięk i wydanie dotykają tych samych plików).")
    job_id = f"J-{os.urandom(4).hex()}"
    log_file = _dir() / f"{job_id}.log"
    cmd = [sys.executable, str(STUDIO / "vstudio.py"), *args]
    env = {**os.environ, **vendor.env(), "PYTHONUNBUFFERED": "1"}
    renders = pdir / "renders"
    job = {"id": job_id, "kind": kind, "project": project_id, "cmd": " ".join(args), "status": "running", "progress": 0.0,
           "message": "start", "started": time.time(), "finished": None, "result": None, "source": source, "pid": None,
           "before": sorted(f.name for f in renders.glob("*")) if renders.exists() else []}
    # osobna grupa procesów: render to drzewo (vstudio.py -> html_to_video.py -> ffmpeg), a cancel musi zabić całe
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(cmd, cwd=str(STUDIO), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1, **group)
    except OSError as exc:
        raise StudioError(f"nie udało się uruchomić joba: {exc}") from exc
    job["pid"] = proc.pid
    _PROCS[job_id] = proc
    _LIVE[job_id] = job
    _save(job)
    activity.record(source, "job", f"{kind} start", project=project_id, summary=job["cmd"])
    threading.Thread(target=_pump, args=(job, proc, log_file, pdir), daemon=True).start()
    return dict(job)


def _pump(job: dict, proc: subprocess.Popen, log_file: Path, pdir: Path) -> None:
    last = ""
    try:
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
                _safe_save(job)
        rc = proc.wait()
        job["finished"] = time.time()
        disk = _read(job["id"])
        if disk and disk.get("status") == "cancelled":                  # anulowane z innego procesu (np. dashboard anuluje job agenta)
            job.update(status="cancelled", message="anulowano")
        if job["status"] == "cancelled":
            pass
        elif rc == 0:
            job.update(status="done", progress=1.0, message="gotowe", result=_result(job, pdir, last))
        else:
            job.update(status="failed", message=(last or f"kod wyjścia {rc}")[:300])
        if job["status"] in ("cancelled", "failed"):
            job["removed"] = cleanup_partial(job, pdir)
    except Exception as exc:  # noqa: BLE001 - wątek nie może paść po cichu: job zostałby na zawsze „running”
        job.update(status="failed", finished=time.time(), message=f"błąd obsługi joba: {exc}"[:300])
    _safe_save(job)
    _PROCS.pop(job["id"], None)
    _LIVE.pop(job["id"], None)
    activity.record(job["source"], "job", f"{job['kind']} {job['status']}", project=job["project"], ok=job["status"] == "done", summary=job["message"])


def cleanup_partial(job: dict, pdir: Path) -> list[str]:
    """Anulowany albo nieudany render zostawia urwany plik wideo: usuwamy to, co POWSTAŁO od startu joba (migawka katalogu renders/).

    W projekcie działa naraz jeden job, więc nowe pliki są na pewno jego; wcześniejszych renderów nie ruszamy.
    """
    removed = []
    if job["kind"] in ("render", "sound"):
        before = set(job.get("before", []))
        for f in list((pdir / "renders").glob("*")):
            if f.is_file() and f.name not in before and f.suffix in (".mp4", ".mov", ".json"):
                f.unlink(missing_ok=True)
                removed.append(f.name)
    return removed


def _result(job: dict, pdir: Path, last_line: str) -> dict:
    res: dict = {"output": last_line}
    if job["kind"] in ("render", "sound"):
        before = set(job.get("before", []))
        fresh = [f for f in list((pdir / "renders").glob("*.mp4")) + list((pdir / "renders").glob("*.mov")) if f.name not in before]
        if fresh:
            newest = max(fresh, key=lambda f: f.stat().st_mtime)
            res["file"] = f"renders/{newest.name}"
            res["mb"] = round(newest.stat().st_size / 1e6, 2)
    elif job["kind"] == "deliver":
        d = pdir / "final"
        res["files"] = [f"final/{f.name}" for f in sorted(d.glob("*")) if f.is_file()] if d.exists() else []
    return res


def kill_pid(pid: int) -> None:
    """Zabija proces i wszystkie jego potomki (samo terminate() zostawiłoby ffmpeg dokańczający render w tle)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def kill_tree(proc: subprocess.Popen) -> None:
    kill_pid(proc.pid)


def cancel(job_id: str) -> dict:
    """Anuluje job: także taki, który uruchomił INNY proces (agent przez MCP), bo liczy się PID z pliku stanu."""
    job = get(job_id)
    if job["status"] != "running":
        return job
    live, proc = _LIVE.get(job_id), _PROCS.get(job_id)
    if live is not None and proc is not None:
        live.update(status="cancelled", message="anulowano", finished=time.time())
        _save(live)
        kill_tree(proc)
        return dict(live)
    job.update(status="cancelled", message="anulowano", finished=time.time())
    _save(job)
    kill_pid(job["pid"])
    return job


def shutdown() -> None:
    """Zamknięcie serwera przerywa jego joby: nie zostawiamy osieroconych renderów (chromium + ffmpeg) pracujących w tle."""
    for jid, proc in list(_PROCS.items()):
        live = _LIVE.get(jid)
        if live is not None:
            live.update(status="cancelled", message="serwer zakończył pracę", finished=time.time())
            _safe_save(live)
        kill_tree(proc)


atexit.register(shutdown)


def wait(job_id: str, timeout: float = 60.0) -> dict:
    """Czeka na zakończenie joba (maks. `timeout` s) i zwraca jego stan; agent woła to po render_start."""
    end = time.time() + timeout
    while True:
        job = get(job_id)
        if job["status"] != "running" or time.time() >= end:
            return job
        time.sleep(0.4)
