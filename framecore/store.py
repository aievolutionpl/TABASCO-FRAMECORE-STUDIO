"""One atomic document transaction for project, history, session and proposals."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from vstudio.locking import atomic_write, file_lock
from .model import EditorError, identifier, now, project, uid, validate

ACTION_LABELS = {"add_library_asset":"Dodano materiał biblioteki", "set_background":"Zmieniono tło", "add_text":"Dodano tekst", "add_image":"Dodano obraz", "add_video":"Dodano wideo", "add_audio":"Dodano dźwięk", "add_caption":"Dodano napis", "add_shape":"Dodano kształt", "add_asset":"Dodano materiał", "add_icon":"Dodano ikonę", "move_element":"Przesunięto element", "resize_element":"Zmieniono rozmiar", "set_property":"Zmieniono właściwość", "move_clip":"Przesunięto klip", "trim_clip":"Przycięto klip", "split_clip":"Podzielono klip", "delete_clip":"Usunięto klip", "duplicate_clip":"Duplikowano klip", "apply_motion":"Zmieniono animację", "set_format":"Zmieniono format", "set_brand":"Zmieniono markę", "style_captions":"Zmieniono styl napisów", "set_track":"Zmieniono ścieżkę", "assemble_storyboard":"Zbudowano montaż", "rename_project":"Zmieniono nazwę projektu", "set_duration":"Zmieniono długość projektu", "set_keyframes":"Zmieniono klatki kluczowe", "set_audio":"Zmieniono dźwięk", "apply_template":"Zastosowano szablon", "add_scene":"Dodano scenę", "duplicate_scene":"Duplikowano scenę"}

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "output" / ".framecore"
ACTION_LABELS.update(replace_clip_asset="Podmieniono materiał klipu",add_track="Dodano ścieżkę",set_project_fps="Zmieniono FPS",assemble_visual_lesson="Zbudowano edytowalny plan lekcji",set_learning_brief="Zapisano cel lekcji",set_scene_learning="Opisano scenę lekcji",set_production_contract="Zapisano brief produkcyjny", set_scene_beat="Zmieniono beat sceny",
                     annotate_story_beats="Opisano stany i beaty", apply_motion_rules="Zastosowano reguły ruchu")


class Store:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, project_id):
        identifier(project_id)
        return self.root / project_id

    def _load(self, pid):
        path = self.directory(pid) / "state.json"
        if not path.is_file():
            raise EditorError("Nie znaleziono projektu", "not_found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, state):
        from .library import materialize
        materialize(state["project"], self.directory(state["project"]["id"]))
        path = self.directory(state["project"]["id"]) / "state.json"
        atomic_write(path, json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2))

    def create(self, name="Projekt bez nazwy", format="9:16", duration=15, brief="", workflow="Premiera produktu"):
        p = project(name, format, duration, brief, workflow)
        directory = self.directory(p["id"])
        directory.mkdir()
        (directory / "assets").mkdir()
        self._save({"project": p, "history": [], "cursor": 0, "session": {"selection": [], "playhead": 0}, "proposals": {}})
        return self.read(p["id"])

    def list(self):
        result = []
        for f in sorted(self.root.glob("*/state.json")):
            p = self.read(f.parent.name)["project"]
            result.append({"id": p["id"], "name": p["metadata"]["name"], "revision": p["revision"], "updatedAt": p["metadata"]["updatedAt"]})
        return sorted(result, key=lambda p: p["updatedAt"], reverse=True)

    def read(self, pid):
        with file_lock(self.directory(pid) / ".lock"):
            s = self._load(pid)
            p = deepcopy(s["project"])
            selected = [i for i in s["session"]["selection"] if any(e["id"] == i for e in p["elements"])]
            return {"project": p, "session": {**s["session"], "selection": selected},
                    "history": [{k: h[k] for k in ("id", "actor", "description", "at", "commands")} for h in s["history"]],
                    "cursor": s["cursor"], "canUndo": s["cursor"] > 0, "canRedo": s["cursor"] < len(s["history"]),
                    "proposals": list(s["proposals"].values())}

    def execute(self, pid, name, args=None, expected_revision=None, actor="human"):
        from .commands import mutate
        args = deepcopy(args or {})
        with file_lock(self.directory(pid) / ".lock"):
            s = self._load(pid)
            p = s["project"]
            if name in {"set_selection", "set_playhead"}:
                if name == "set_selection":
                    selected = args.get("element_ids", [])
                    if not isinstance(selected, list) or any(i not in {e["id"] for e in p["elements"]} for i in selected):
                        raise EditorError("Nieprawidłowe zaznaczenie")
                    s["session"]["selection"] = selected
                else:
                    from .model import number
                    s["session"]["playhead"] = number(args.get("time"), "playhead", 0, p["duration"])
                self._save(s)
            else:
                if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision != p["revision"]:
                    raise EditorError(f"Konflikt rewizji: oczekiwano {expected_revision}, aktualna {p['revision']}", "revision_conflict")
                if name in {"undo", "redo"}:
                    idx = s["cursor"] - 1 if name == "undo" else s["cursor"]
                    if idx < 0 or idx >= len(s["history"]):
                        raise EditorError(f"Brak operacji do wykonania: {name}")
                    restored = deepcopy(s["history"][idx]["before" if name == "undo" else "after"])
                    restored["revision"] = p["revision"] + 1
                    restored["metadata"]["updatedAt"] = now()
                    s["project"] = restored
                    s["cursor"] += -1 if name == "undo" else 1
                elif name == "cancel_proposal":
                    proposal = s["proposals"].get(args.get("proposal_id"))
                    if not proposal or proposal["status"] != "pending":
                        raise EditorError("Propozycja jest niedostępna")
                    proposal["status"] = "cancelled"
                elif name == "propose_changes":
                    working = deepcopy(p)
                    commands = args.get("commands", [])
                    if not isinstance(commands, list) or not 1 <= len(commands) <= 100:
                        raise EditorError("Propozycja musi zawierać 1–100 komend")
                    for c in commands:
                        mutate(working, c["name"], c.get("args", {}), s["session"])
                    validate(working)
                    proposal = {"id": uid("proposal"), "baseRevision": p["revision"], "description": str(args.get("description", "Proponowana zmiana"))[:500],
                                "commands": commands, "duration": working["duration"], "status": "pending", "projectAfter": working,
                                "changes": [{"id": e["id"], "before": next((b for b in p["elements"] if b["id"] == e["id"]), None), "after": e}
                                            for e in working["elements"] if e not in p["elements"]],
                                "removed": [e["id"] for e in p["elements"] if e["id"] not in {a["id"] for a in working["elements"]}]}
                    s["proposals"][proposal["id"]] = proposal
                else:
                    working = deepcopy(p)
                    if name == "apply_proposal":
                        proposal = s["proposals"].get(args.get("proposal_id"))
                        if not proposal or proposal["status"] != "pending":
                            raise EditorError("Propozycja jest niedostępna")
                        if proposal["baseRevision"] != p["revision"]:
                            raise EditorError("Propozycja jest nieaktualna; przygotuj nową", "revision_conflict")
                        commands = proposal["commands"]
                        description = proposal["description"]
                        proposal["status"] = "applied"
                    else:
                        commands = [{"name": name, "args": args}]
                        description = str(args.get("description", ACTION_LABELS.get(name, name)))[:500]
                    if name == "apply_proposal":
                        working = deepcopy(proposal["projectAfter"])
                    else:
                        for c in commands:
                            mutate(working, c["name"], c.get("args", {}), s["session"])
                    validate(working)
                    working["revision"] = p["revision"] + 1
                    working["metadata"]["updatedAt"] = now()
                    s["history"] = s["history"][:s["cursor"]]
                    s["history"].append({"id": uid("action"), "actor": actor, "description": description, "at": now(),
                                         "commands": commands, "before": p, "after": working})
                    s["cursor"] = len(s["history"])
                    s["project"] = working
                s["session"]["playhead"] = min(s["session"]["playhead"], s["project"]["duration"])
                self._save(s)
        return self.read(pid)

    def create_variant(self, pid, revision, format):
        import shutil
        from .production import annotate_beats, reflow
        source = self.read(pid)["project"]
        if isinstance(revision, bool) or not isinstance(revision,int) or revision != source["revision"]:
            raise EditorError("Konflikt rewizji przed utworzeniem wariantu", "revision_conflict")
        variant = reflow(deepcopy(source), format)
        variant["id"] = uid("fc"); variant["revision"] = 0
        variant["metadata"].update(name=source["metadata"]["name"] + " · " + format, createdAt=now(), updatedAt=now(),
                                  variantOf={"project_id":pid,"revision":revision,"layout":"story-reflow","format":format})
        variant.setdefault("production", {}).update(requireReview=True)
        variant["production"].setdefault("product", source["metadata"]["name"])
        variant["production"].setdefault("message", source["metadata"]["brief"][:2000] or source["metadata"]["name"])
        annotate_beats(variant); validate(variant)
        directory = self.directory(variant["id"]); (directory/"assets").mkdir(parents=True)
        try:
            for a in variant["assets"]: shutil.copy2(self.directory(pid)/a["file"], directory/a["file"])
            self._save({"project":variant,"history":[],"cursor":0,"session":{"selection":[],"playhead":0},"proposals":{}})
        except Exception:
            shutil.rmtree(directory)
            raise
        return self.read(variant["id"])

    def context(self, pid):
        s = self.read(pid)
        p, session = s["project"], s["session"]
        t = session["playhead"]
        hidden = {track["id"] for track in p["tracks"] if track["hidden"]}
        visible = [e for e in p["elements"] if e["type"] != "audio" and e["trackId"] not in hidden and e["opacity"] > 0 and e["start"] <= t < e["start"] + e["duration"]]
        return {"project_id": pid, "revision": p["revision"], "metadata": p["metadata"], "canvas": p["canvas"],
                "selection": session["selection"], "selected": [e for e in p["elements"] if e["id"] in session["selection"]],
                "playhead": t, "frame": round(t * p["canvas"]["fps"]), "visible": visible,
                "transcript": [{"text": e["text"], "start": e["start"], "duration": e["duration"]} for e in p["elements"] if e["type"] == "caption"],
                "lesson": p.get("lesson"), "assets": p["assets"], "brand": p["brand"], "companyBrain": p.get("brandProfile"), "scenes": p["scenes"], "tracks": p["tracks"],
                "recentActions": s["history"][max(0, s["cursor"] - 10):s["cursor"]]}
