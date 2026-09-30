"""Automatyczny nadzór w tle: gdy scena projektu zmieni się na dysku, serwer sam robi szybką kontrolę i zapisuje raport.

Dzięki temu „pilnowanie generacji” nie zależy od tego, czy agent pamięta o `check_run`: każda zmiana (agent, edytor, Ty) dostaje
werdykt, który widać w dashboardzie i który agent dostaje przez `check_latest` / zasób raportu. Nie dubluje pracy: pomija zmiany,
dla których raport jest już świeższy, i projekty, w których kontrola właśnie trwa. Włącza się profilem (`auto_supervise`).
"""
from __future__ import annotations

import threading

from .. import activity, supervisor, workspace
from ..common import StudioError


class Watcher(threading.Thread):
    def __init__(self, interval: float = 2.0):
        super().__init__(daemon=True, name="vstudio-watcher")
        self.interval = interval
        self.stop_event = threading.Event()
        self.seen: dict[str, float | None] = {}
        self.primed = False

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - watcher nie może paść
                activity.record("system", "supervisor", "watcher error", ok=False, summary=str(exc)[:200])
            self.primed = True
            self.stop_event.wait(self.interval)

    def tick(self) -> list[str]:
        """Jeden przebieg: zwraca id projektów, dla których uruchomiono kontrolę (ułatwia testy)."""
        ran: list[str] = []
        enabled = workspace.profile_get()["auto_supervise"]
        for p in workspace.list_projects():
            pid, mtime = p["id"], p["updated"]
            old = self.seen.get(pid, "new")
            self.seen[pid] = mtime
            if not self.primed or old == "new" or mtime is None or mtime == old or not enabled:
                continue
            try:
                pdir, pr = workspace.resolve(pid)
            except StudioError:
                continue
            if pr.get("engine") != "html" or supervisor.is_running(pdir):
                continue
            latest = pdir / "supervisor" / "latest.json"
            if latest.exists() and latest.stat().st_mtime >= mtime:
                continue                                  # raport jest już świeższy niż zmiana (np. scene_write z check)
            activity.record("system", "supervisor", "auto-nadzór", project=pid, summary="scena zmieniona na dysku: szybka kontrola")
            try:
                rep = supervisor.check(pdir, pr, depth="quick")
            except StudioError as exc:
                activity.record("system", "supervisor", "auto-nadzór", project=pid, ok=False, summary=str(exc)[:200])
                continue
            c = rep["counts"]
            activity.record("system", "supervisor", f"auto-nadzór: {rep['verdict']}", project=pid, ok=rep["verdict"] != "blocked",
                            summary=f"wynik {rep['score']}, {c['error']} błędów, {c['warn']} ostrzeżeń (runda {rep['round']})")
            ran.append(pid)
        return ran
