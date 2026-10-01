"""Operacje studia zarejestrowane w rejestrze możliwości. Kolejność = kolejność w dokumentacji i w skillu.

Import tego modułu wypełnia `registry.REGISTRY`. Handlery zwracają słowniki JSON; jeśli wynik ma klucz `images`
(lista {path, rel, label}), MCP odda je agentowi jako obrazy, a dashboard pokaże miniatury.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import activity, agentkit, doctor as doctor_mod, jobs, knowledge, supervisor, vendor, workspace
from .common import StudioError
from .registry import REGISTRY, capability, describe

PROJECT = {"type": "string", "description": "Project id 'brand/slug' (or a unique slug). Get ids from projects_list."}
_CHECK = {"type": "string", "enum": ["quick", "standard", "deep"], "description": "Run the supervisor after the change and attach its verdict."}


def _proj(ref: str):
    return workspace.resolve(ref)


def _img(pdir: Path, path: Path | str, label: str) -> dict:
    p = Path(path)
    return {"path": str(p), "rel": p.relative_to(pdir).as_posix(), "label": label, "project": workspace.project_id(pdir)}


def _brief_check(rep: dict, limit: int = 8) -> dict:
    return {"verdict": rep["verdict"], "score": rep["score"], "round": rep["round"], "counts": rep["counts"], "delta": rep["delta"],
            "findings": [{k: f[k] for k in ("code", "severity", "t", "detail", "fix")} for f in rep["findings"][:limit]],
            "next_actions": rep["next_actions"]}


# ============================================================ onboarding

@capability("studio_status", "Stan studia", "Jedno wywołanie: środowisko, profil marki, agent, projekty, zadania i co zrobić dalej.", "onboarding",
            returns="ready, onboarded, doctor, agent, projects, open_tasks, vendor, next[]",
            when="Call this FIRST in every session to learn what to do next.")
def studio_status() -> dict:
    checks = doctor_mod.check()
    failing = [c for c in checks if not c["ok"] and c["level"] == "fail"]
    prof = workspace.profile_get()
    projects = workspace.list_projects()
    tasks = workspace.tasks_list("open") + workspace.tasks_list("in_progress")
    agent = activity.agent_status()
    nxt = []
    if failing:
        nxt.append("Napraw środowisko: " + ", ".join(c["check"] for c in failing) + " (doctor)")
    if not prof["onboarded"]:
        nxt.append("Uzupełnij profil marki (profile_set): nazwa, paleta, font, ton, format")
    if tasks:
        nxt.append(f"Masz {len(tasks)} zadań dla agenta (task_next)")
    if not projects:
        nxt.append("Utwórz pierwszy film z szablonu (templates_list, project_create)")
    for p in projects[:5]:
        c = p["check"]
        if c and c["verdict"] != "pass":
            nxt.append(f"{p['id']}: nadzór {c['verdict']} (wynik {c['score']}); popraw i uruchom check_run")
        elif not c:
            nxt.append(f"{p['id']}: jeszcze nie sprawdzony (check_run)")
    return {"ready": not failing, "onboarded": prof["onboarded"], "brand": prof["name"] or None,
            "doctor": {"ok": not failing, "failing": [{"check": c["check"], "detail": c["detail"]} for c in failing]},
            "agent": agent, "projects": len(projects), "open_tasks": len(tasks), "vendor": len(vendor.listing()), "next": nxt}


@capability("profile_get", "Profil marki", "Nazwa, paleta, font, ton, odbiorcy i domyślny format użytkownika.", "onboarding",
            returns="profile", when="Before designing anything: use the brand values, do not invent colours or fonts.")
def profile_get() -> dict:
    return workspace.profile_get()


@capability("profile_set", "Zapisz profil marki", "Ustawia profil marki (częściowo). Uzupełnienie nazwy kończy onboarding.", "onboarding", mutates=True,
            params={"name": {"type": "string"}, "palette": {"type": "object", "description": "bg, ink, accent, accent2 as #RRGGBB"},
                    "font": {"type": "string"}, "tone": {"type": "string"}, "audience": {"type": "string"},
                    "default_format": {"type": "string", "enum": list(workspace.FORMATS)}, "fps": {"type": "integer", "minimum": 12, "maximum": 120},
                    "auto_supervise": {"type": "boolean", "description": "run a quick supervisor check in the background whenever a scene changes on disk (dashboard)"}},
            returns="profile", when="During onboarding, after asking the user for their brand.")
def profile_set(**patch) -> dict:
    return workspace.profile_set(patch)


@capability("agent_connect_info", "Jak podłączyć agenta", "Polecenie MCP, fragment .mcp.json, ścieżki skilla i stan połączenia agenta.", "onboarding",
            returns="command, claude_code, mcp_json, skill, agent")
def agent_connect_info() -> dict:
    return agentkit.connect_info()


@capability("agent_selftest", "Test połączenia agenta", "Uruchamia serwer MCP i robi handshake jak prawdziwy klient: dowód, że agent się połączy.", "onboarding",
            returns="ok, server, protocol, tools, ms")
def agent_selftest() -> dict:
    return agentkit.selftest()


@capability("agent_install", "Zainstaluj skill i konfigurację MCP", "Zapisuje skill (SKILL.md) i wpis vstudio w .mcp.json.", "onboarding", mutates=True,
            params={"skill": {"type": "boolean", "default": True}, "mcp_config": {"type": "boolean", "default": True},
                    "scope": {"type": "string", "enum": ["project", "user"], "default": "project"}},
            returns="installed{skill, mcp_config}")
def agent_install(skill: bool = True, mcp_config: bool = True, scope: str = "project") -> dict:
    return agentkit.install(skill, mcp_config, scope)


# ============================================================ library

@capability("templates_list", "Szablony", "Katalog szablonów: opis, technika, format, czas, tagi i czy wymagają sieci.", "library", returns="templates[]",
            when="When starting a new film: pick the closest template instead of writing from scratch.")
def templates_list() -> dict:
    return {"templates": workspace.templates()}


@capability("project_create", "Nowy projekt", "Tworzy projekt (opcjonalnie z szablonu) z briefem; format z szablonu lub profilu marki.", "library", mutates=True,
            params={"slug": {"type": "string", "description": "short-kebab-name"}, "brand": {"type": "string", "description": "defaults to the profile name"},
                    "template": {"type": "string", "description": "template id from templates_list"},
                    "format": {"type": "string", "enum": list(workspace.FORMATS)}, "size": {"type": "string", "description": "WxH, overrides format"},
                    "fps": {"type": "integer", "minimum": 12, "maximum": 120}, "duration": {"type": "number", "minimum": 1, "maximum": 600},
                    "brief": {"type": "string", "description": "what the film is for; written into BRIEF.md"}},
            required=("slug",), returns="project summary (id, size, gates, next)")
def project_create(**kw) -> dict:
    return {"project": workspace.create_project(**kw)}


# ============================================================ projects

@capability("projects_list", "Projekty", "Wszystkie projekty z postępem bramek, następnym krokiem i wynikiem ostatniego nadzoru.", "projects", returns="projects[]")
def projects_list() -> dict:
    return {"projects": workspace.list_projects()}


@capability("project_get", "Szczegóły projektu", "Bramki, rendery, zadania, pokrycie vendorem i podsumowanie nadzoru jednego projektu.", "projects",
            params={"project": PROJECT}, required=("project",), returns="project (status, gates, renders, vendor, tasks)")
def project_get(project: str) -> dict:
    pdir, pr = _proj(project)
    return {"project": workspace.summarize(pdir, pr, detail=True)}


@capability("gate_set", "Bramka jakości", "Zatwierdza/resetuje bramkę (brief, visual_rules, stills, draft, sound, critic, final) albo ustawia wynik krytyka.", "projects",
            mutates=True, params={"project": PROJECT, "action": {"type": "string", "enum": ["approve", "reset", "score"]},
                                   "gate": {"type": "string", "enum": ["brief", "reference_spec", "visual_rules", "stills", "draft", "sound", "critic", "final"]},
                                   "score": {"type": "number", "minimum": 0, "maximum": 10}},
            required=("project", "action"), returns="message, next",
            when="Approve a gate only when the work is genuinely done; final render is blocked until brief, visual_rules and stills are approved.")
def gate_set(project: str, action: str, gate: str | None = None, score: float | None = None) -> dict:
    from . import project as proj

    pdir, pr = _proj(project)
    msg = proj.cmd_gate(pdir, pr, action, gate, score)
    _, pr = _proj(project)
    return {"project": workspace.project_id(pdir), "message": msg, "next": proj.next_step(pr)}


# ============================================================ scene

@capability("scene_read", "Czytaj scenę", "Kod sceny (src/index.html) z informacją o haczykach kontraktu i zasobach z sieci.", "scene",
            params={"project": PROJECT, "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1}},
            required=("project",), returns="content, range, lines, hooks, vendor", when="Before editing: read the current scene.")
def scene_read(project: str, start_line: int | None = None, end_line: int | None = None) -> dict:
    pdir, pr = _proj(project)
    return workspace.scene_read(pdir, pr, start_line, end_line)


def _maybe_check(pdir: Path, pr: dict, check: str | None, res: dict) -> dict:
    if check:
        rep = supervisor.check(pdir, pr, depth=check)
        res["check"] = _brief_check(rep)
        imgs = []
        if rep.get("assets") and rep["assets"].get("filmstrip"):
            imgs.append(_img(pdir, pdir / "supervisor" / rep["assets"]["dir"] / rep["assets"]["filmstrip"], f"filmstrip, runda {rep['round']}"))
        res["images"] = imgs
    return res


@capability("scene_write", "Zapisz scenę", "Zapisuje całą scenę (z kopią w historii). Z `check` od razu uruchamia nadzorcę i zwraca werdykt.", "scene", mutates=True, images=True,
            params={"project": PROJECT, "content": {"type": "string", "description": "full HTML of the scene"}, "note": {"type": "string"}, "check": _CHECK},
            required=("project", "content"), returns="bytes, lines, backup, check?",
            when="Write the whole scene. For small changes prefer scene_patch.")
def scene_write(project: str, content: str, note: str = "", check: str | None = None) -> dict:
    pdir, pr = _proj(project)
    res = workspace.scene_write(pdir, pr, content, note)
    return _maybe_check(pdir, pr, check, res)


@capability("scene_patch", "Popraw fragment sceny", "Zamienia dokładne fragmenty tekstu (każdy musi wystąpić raz, chyba że all=true). Atomowo, z historią.", "scene",
            mutates=True, images=True,
            params={"project": PROJECT, "edits": {"type": "array", "items": {"type": "object"},
                                                    "description": "[{find, replace, all?}]; find must match exactly once"},
                    "note": {"type": "string"}, "check": _CHECK},
            required=("project", "edits"), returns="applied[], backup, check?", when="Small fixes after a finding: cheaper and safer than rewriting the scene.")
def scene_patch(project: str, edits: list, note: str = "", check: str | None = None) -> dict:
    pdir, pr = _proj(project)
    res = workspace.scene_patch(pdir, pr, edits, note)
    return _maybe_check(pdir, pr, check, res)


@capability("scene_palette", "Paleta sceny", "Kolory #RRGGBB użyte w scenie (liczność, jasność) i propozycja mapowania na kolory marki z profilu.", "scene",
            params={"project": PROJECT}, required=("project",), returns="colors[], brand, suggestion[]",
            when="Before restyling a template: see which colours it uses, then apply the brand with scene_recolor instead of editing hex values by hand.")
def scene_palette(project: str) -> dict:
    pdir, pr = _proj(project)
    return workspace.scene_palette(pdir, pr)


@capability("scene_recolor", "Zmień kolory sceny", "Podmienia kolory #RRGGBB w całej scenie jednym przebiegiem (z historią). Z `check` od razu uruchamia nadzorcę.", "scene",
            mutates=True, images=True,
            params={"project": PROJECT, "mapping": {"type": "object", "description": "{\"#OLD\": \"#NEW\", ...}, each #RRGGBB"}, "note": {"type": "string"}, "check": _CHECK},
            required=("project", "mapping"), returns="replaced{hex: n}, not_found[], check?",
            when="Apply the brand palette (see `suggestion` in scene_palette) or change one colour everywhere. Contrast is re-checked by the supervisor.")
def scene_recolor(project: str, mapping: dict, note: str = "", check: str | None = None) -> dict:
    pdir, pr = _proj(project)
    return _maybe_check(pdir, pr, check, workspace.scene_recolor(pdir, pr, mapping, note))


@capability("scene_history", "Historia sceny", "Ostatnie wersje sceny (do 30) z notatkami.", "scene", params={"project": PROJECT}, required=("project",), returns="versions[]")
def scene_history(project: str) -> dict:
    pdir, _ = _proj(project)
    return {"versions": workspace.scene_history(pdir)}


@capability("scene_restore", "Przywróć wersję sceny", "Cofa scenę do wersji z historii (obecna trafia do historii).", "scene", mutates=True,
            params={"project": PROJECT, "version": {"type": "string", "description": "file name from scene_history"}}, required=("project", "version"), returns="restored, backup")
def scene_restore(project: str, version: str) -> dict:
    pdir, pr = _proj(project)
    return workspace.scene_restore(pdir, pr, version)


# ============================================================ knowledge

@capability("knowledge_get", "Wiedza", "Zasady: kontrakt strony, deterministyczny GSAP, pętla pracy, kody znalezisk, ruch, wizualia, marka.", "knowledge",
            params={"topic": {"type": "string", "enum": list(knowledge.TOPICS)}}, required=("topic",), returns="text",
            when="Read `gsap` and `contract` before writing a scene, `brand` before choosing colours, `findings` when the supervisor reports a code.")
def knowledge_get(topic: str) -> dict:
    return knowledge.get(topic)


# ============================================================ inspect

@capability("frames_view", "Zobacz klatki", "Klatki filmu w podanych chwilach (obraz dla agenta i dashboardu): tak oceniasz kompozycję.", "inspect", images=True,
            params={"project": PROJECT, "times": {"type": "array", "items": {"type": "number"}, "description": "seconds, up to 12"},
                    "width": {"type": "integer", "minimum": 240, "maximum": 1440, "default": 720}},
            required=("project", "times"), returns="images (frames or a labelled sheet)",
            when="After every meaningful change: look at the opening, the main beat, the fastest transition and the end.")
def frames_view(project: str, times: list, width: int = 720) -> dict:
    pdir, pr = _proj(project)
    if not times or len(times) > 12:
        raise StudioError("times: od 1 do 12 chwil")
    out = pdir / "stills" / "agent"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    cap = supervisor.capture_frames(pdir, pr, [float(t) for t in times], out, max_width=width)
    imgs = ([_img(pdir, cap["sheet"], "arkusz klatek")] if cap["sheet"] and len(times) > 2 else
            [_img(pdir, f, f"t={t:g}s") for f, t in zip(cap["frames"], times)])
    return {"project": workspace.project_id(pdir), "times": times, "images": imgs, "page_problems": cap["page_problems"]}


@capability("filmstrip", "Taśma filmowa", "Równomierny przekrój całego filmu (do 12 klatek) jednym obrazem.", "inspect", images=True,
            params={"project": PROJECT, "count": {"type": "integer", "minimum": 3, "maximum": 12, "default": 8}}, required=("project",), returns="image")
def filmstrip(project: str, count: int = 8) -> dict:
    pdir, pr = _proj(project)
    dur = float(pr["duration"])
    times = [round(dur * i / count, 2) for i in range(count)]
    out = pdir / "stills" / "agent"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    cap = supervisor.capture_frames(pdir, pr, times, out, max_width=520)
    return {"project": workspace.project_id(pdir), "times": times, "images": [_img(pdir, cap["sheet"], f"taśma: {count} klatek")], "page_problems": cap["page_problems"]}


@capability("timeline_get", "Mapa czasu", "Zdarzenia dźwiękowe (EV) i przedziały, w których widać poszczególne teksty (z boksami).", "inspect",
            params={"project": PROJECT, "step": {"type": "number", "minimum": 0.02, "maximum": 1, "default": 0.1}}, required=("project",), returns="duration, events[], texts[]")
def timeline_get(project: str, step: float = 0.1) -> dict:
    pdir, pr = _proj(project)
    return {"project": workspace.project_id(pdir), **supervisor.timeline(pdir, pr, step)}


# ============================================================ supervise

@capability("check_run", "Sprawdź film (nadzór)", "Runda nadzoru: błędy, klatki, pętla, determinizm, czytelność, kontrast. Zwraca werdykt, znaleziska, delta i taśmę.", "supervise",
            images=True, mutates=True, params={"project": PROJECT, "depth": {"type": "string", "enum": ["quick", "standard", "deep"], "default": "standard"}},
            required=("project",), returns="verdict, score, findings[], delta, next_actions[], images",
            when="After every edit. Loop until verdict is `pass`; fix errors first, then warnings. Read `delta` to see progress.")
def check_run(project: str, depth: str = "standard") -> dict:
    pdir, pr = _proj(project)
    rep = supervisor.check(pdir, pr, depth=depth)
    imgs = []
    if rep.get("assets"):
        base = pdir / "supervisor" / rep["assets"]["dir"]
        imgs.append(_img(pdir, base / rep["assets"]["filmstrip"], f"taśma, runda {rep['round']}"))
        for f in rep["findings"]:
            if f.get("evidence") and f["severity"] != "info" and len(imgs) < 3:
                imgs.append(_img(pdir, base / f["evidence"], f"{f['code']} przy {f['t']}s"))
    return {**rep, "images": imgs}


@capability("check_latest", "Ostatni raport nadzoru", "Zwraca ostatni raport bez uruchamiania nowej rundy.", "supervise", params={"project": PROJECT}, required=("project",), returns="report or null")
def check_latest(project: str) -> dict:
    pdir, _ = _proj(project)
    return {"report": supervisor.latest(pdir)}


@capability("check_history", "Historia rund nadzoru", "Wynik i werdykt każdej rundy: widać, czy praca idzie do przodu.", "supervise", params={"project": PROJECT}, required=("project",), returns="rounds[]")
def check_history(project: str) -> dict:
    pdir, _ = _proj(project)
    return {"rounds": supervisor.history(pdir)}


@capability("check_explain", "Wyjaśnij kod znaleziska", "Co znaczy kod (np. NONDETERMINISTIC) i jak to naprawić.", "supervise",
            params={"code": {"type": "string"}}, required=("code",), returns="title, fix")
def check_explain(code: str) -> dict:
    return supervisor.explain(code)


# ============================================================ render

def _need(*tools: str) -> None:
    """Sprawdza narzędzia zewnętrzne PRZED startem joba: błąd od razu i po ludzku, a nie dopiero w logu procesu."""
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        raise StudioError(f"{', '.join(missing)} nie jest na PATH: ta operacja wymaga FFmpeg (zobacz doctor)")


@capability("render_start", "Render", "Uruchamia render jako job (draft w połowie rozdzielczości albo final). Zwraca job; postęp przez job_get/job_wait.", "render", job=True,
            params={"project": PROJECT, "final": {"type": "boolean", "default": False}, "audio": {"type": "string", "description": "path to a mixed audio file"},
                    "force": {"type": "boolean", "default": False, "description": "skip the gate check for a final render"}},
            required=("project",), returns="job, warnings[]",
            when="Render a draft after the supervisor says pass; final only after brief, visual_rules and stills are approved.")
def render_start(project: str, final: bool = False, audio: str | None = None, force: bool = False) -> dict:
    _need("ffmpeg")
    pdir, pr = _proj(project)
    warns = []
    rep = supervisor.latest(pdir)
    if rep is None:
        warns.append("Film nie był jeszcze sprawdzony nadzorcą (check_run).")
    elif rep["verdict"] != "pass":
        warns.append(f"Ostatni nadzór: {rep['verdict']} (wynik {rep['score']}, runda {rep['round']}).")
    args = ["render", "-p", str(pdir)] + (["--final"] if final else []) + (["--audio", audio] if audio else []) + (["--force"] if force else [])
    job = jobs.start("render", workspace.project_id(pdir), pdir, args, source="api")
    return {"job": job, "warnings": warns}


@capability("sound_start", "Dźwięk", "Buduje cue sheet z EV, miksuje do -14 LUFS i podkłada pod najnowszy render (job).", "render", job=True,
            params={"project": PROJECT}, required=("project",), returns="job")
def sound_start(project: str) -> dict:
    _need("ffmpeg", "ffprobe")
    pdir, _ = _proj(project)
    return {"job": jobs.start("sound", workspace.project_id(pdir), pdir, ["sound", "-p", str(pdir)])}


@capability("deliver_start", "Wydanie", "QA pliku, plakat, paczka wydania i DELIVERY.md (job).", "render", job=True,
            params={"project": PROJECT, "strict": {"type": "boolean", "default": False}}, required=("project",), returns="job")
def deliver_start(project: str, strict: bool = False) -> dict:
    _need("ffmpeg", "ffprobe")
    pdir, _ = _proj(project)
    return {"job": jobs.start("deliver", workspace.project_id(pdir), pdir, ["deliver", "-p", str(pdir)] + (["--strict"] if strict else []))}


@capability("jobs_list", "Joby", "Ostatnie joby (render, dźwięk, wydanie) z postępem.", "render", params={"project": PROJECT}, returns="jobs[]")
def jobs_list(project: str | None = None) -> dict:
    pid = workspace.project_id(_proj(project)[0]) if project else None
    return {"jobs": jobs.listing(pid)}


@capability("job_get", "Stan joba", "Status, postęp, wynik i ogon logu.", "render", params={"job": {"type": "string"}}, required=("job",), returns="job, log")
def job_get(job: str) -> dict:
    return {"job": jobs.get(job), "log": jobs.log_tail(job)}


@capability("job_wait", "Czekaj na job", "Blokuje do zakończenia joba albo do `timeout` s (maks. 600) i zwraca jego stan.", "render",
            params={"job": {"type": "string"}, "timeout": {"type": "number", "minimum": 1, "maximum": 600, "default": 60}}, required=("job",), returns="job, log",
            when="After render_start: call repeatedly until status is done/failed.")
def job_wait(job: str, timeout: float = 60.0) -> dict:
    j = jobs.wait(job, float(timeout))
    return {"job": j, "log": jobs.log_tail(job, 12)}


@capability("job_cancel", "Anuluj job", "Przerywa działający job.", "render", mutates=True, params={"job": {"type": "string"}}, required=("job",), returns="job")
def job_cancel(job: str) -> dict:
    return {"job": jobs.cancel(job)}


# ============================================================ agent tasks

@capability("task_create", "Zadanie dla agenta", "Zapisuje prośbę użytkownika dla agenta (dashboard: „poproś agenta”).", "agent", mutates=True,
            params={"prompt": {"type": "string"}, "project": PROJECT}, required=("prompt",), returns="task")
def task_create(prompt: str, project: str | None = None) -> dict:
    return {"task": workspace.task_create(prompt, project, source="api")}


@capability("task_list", "Lista zadań", "Zadania dla agenta (open, in_progress, done, blocked).", "agent",
            params={"status": {"type": "string", "enum": ["open", "in_progress", "done", "blocked"]}}, returns="tasks[]")
def task_list(status: str | None = None) -> dict:
    return {"tasks": workspace.tasks_list(status)}


@capability("task_next", "Następne zadanie", "Najstarsze otwarte zadanie użytkownika z kontekstem projektu i instrukcją, co dalej.", "agent", returns="task or null, guide",
            when="After studio_status: pick up what the user asked for in the dashboard.")
def task_next() -> dict:
    t = workspace.task_next()
    return {"task": t, "guide": "task_update -> in_progress, then follow knowledge_get topic=workflow." if t else "Brak otwartych zadań."}


@capability("task_update", "Aktualizuj zadanie", "Zmienia status (open, in_progress, done, blocked) i/lub dopisuje notatkę (np. świadomie zostawione ostrzeżenie).", "agent",
            mutates=True, params={"task": {"type": "string"}, "status": {"type": "string", "enum": ["open", "in_progress", "done", "blocked"]}, "note": {"type": "string"}},
            required=("task",), returns="task")
def task_update(task: str, status: str | None = None, note: str | None = None) -> dict:
    return {"task": workspace.task_update(task, status, note)}


# ============================================================ system

@capability("doctor", "Diagnostyka środowiska", "Python, FFmpeg, Playwright, Chromium, renderery, szablony: co działa, a czego brakuje.", "system", returns="ok, checks[]")
def doctor() -> dict:
    checks = doctor_mod.check()
    return {"ok": all(c["ok"] for c in checks if c["level"] == "fail"), "checks": checks}


@capability("activity_tail", "Aktywność", "Ostatnie wywołania operacji przez agenta, dashboard i joby.", "system",
            params={"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 40}, "since": {"type": "integer", "description": "event id, only newer"},
                    "source": {"type": "string", "enum": ["mcp", "dashboard", "api", "cli"]}}, returns="events[], agent")
def activity_tail(limit: int = 40, since: int = 0, source: str | None = None) -> dict:
    return {"events": activity.tail(limit, since, source), "agent": activity.agent_status()}


@capability("vendor_list", "Lokalne kopie bibliotek", "Które zewnętrzne zasoby (np. GSAP z CDN) mają lokalną kopię do pracy offline.", "system", returns="items[]")
def vendor_list() -> dict:
    return {"items": vendor.listing(), "aliases": vendor.ALIASES}


@capability("vendor_add", "Dodaj kopię biblioteki", "Zapisuje lokalną kopię URL-a (skrót: gsap); `file` = lokalny plik zamiast pobierania.", "system", mutates=True,
            params={"url": {"type": "string", "description": "https URL or alias (gsap)"}, "file": {"type": "string", "description": "local file to copy instead of downloading"}},
            required=("url",), returns="url, file, bytes", when="When a check reports NET_FAILED for a CDN script, or before working offline.")
def vendor_add(url: str, file: str | None = None) -> dict:
    return vendor.add(url, file)


@capability("vendor_remove", "Usuń kopię biblioteki", "Usuwa lokalną kopię.", "system", mutates=True, params={"url": {"type": "string"}}, required=("url",), returns="removed")
def vendor_remove(url: str) -> dict:
    return vendor.remove(url)


@capability("capabilities_list", "Mapa możliwości", "Pełna lista operacji studia: kategoria, parametry, czy zmienia pliki, czy to job.", "system", returns="categories[], capabilities[]")
def capabilities_list() -> dict:
    from .registry import CATEGORIES

    return {"categories": [{"id": c, "title": t} for c, t in CATEGORIES], "capabilities": describe()}


__all__ = ["REGISTRY"]
