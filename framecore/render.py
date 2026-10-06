"""Revision-frozen local export, reusing vstudio's deterministic renderer."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from copy import deepcopy
from pathlib import Path

from .persistence import atomic_write, file_lock

from .composition import compile_project
from .model import EditorError, uid


def probe(path):
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    if cp.returncode:
        raise EditorError("Nieobsługiwany lub uszkodzony plik multimedialny")
    return json.loads(cp.stdout)


class RenderJobs:
    def __init__(self, store):
        self.store = store
        self.directory = store.root / ".jobs"
        self.directory.mkdir(exist_ok=True)

    def _path(self, job_id):
        from .model import identifier
        identifier(job_id)
        return self.directory / (job_id + ".json")

    def get(self, job_id):
        path = self._path(job_id)
        if not path.is_file():
            raise EditorError("Nie znaleziono zadania renderowania", "not_found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _update(self, job_id, **values):
        with file_lock(self.directory / ".lock"):
            job = self.get(job_id)
            job.update(values)
            atomic_write(self._path(job_id), json.dumps(job))

    def start(self, pid, expected_revision, quality="final"):
        p = self.store.read(pid)["project"]
        if isinstance(expected_revision, bool) or not isinstance(expected_revision,int) or expected_revision != p["revision"]:
            raise EditorError("Konflikt rewizji przed eksportem", "revision_conflict")
        if quality not in {"final", "draft"}:
            raise EditorError("Nieobsługiwana jakość eksportu")
        from .production import require_export
        production_status = require_export(p, self.store.directory(pid), quality)
        job_id = uid("render")
        with file_lock(self.directory / ".lock"):
            for path in self.directory.glob("*.json"):
                j = json.loads(path.read_text(encoding="utf-8"))
                if j["status"] in {"queued", "rendering"}:
                    try:
                        os.kill(j["ownerPid"], 0)
                    except ProcessLookupError:
                        j.update(status="failed", error="Proces renderowania zakończył się przed ukończeniem")
                        atomic_write(path, json.dumps(j))
                    else:
                        raise EditorError("Trwa inny render; poczekaj przed kolejnym eksportem", "render_busy")
            job = {"id": job_id, "project_id": pid, "revision": p["revision"], "status": "queued", "progress": 0, "quality": quality, "ownerPid": os.getpid()}
            atomic_write(self._path(job_id), json.dumps(job))
        threading.Thread(target=self._run, args=(job_id, p, quality, production_status), daemon=True).start()
        return self.get(job_id)

    def _run(self, job_id, p, quality, production_status):
        try:
            self._update(job_id, status="rendering", progress=.05)
            root = self.store.directory(p["id"])
            directory = root / "exports" / job_id
            directory.mkdir(parents=True)
            (directory / "assets").mkdir()
            for a in p["assets"]:
                src = root / a["file"]
                target = directory / a["file"]
                shutil.copy2(src, target)
            (directory / "project.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
            from .production import asset_manifest
            frozen_assets = asset_manifest(p,directory)
            if {a["id"]:a["sha256"] for a in frozen_assets} != {a["id"]:a["sha256"] for a in production_status["assets"]}:
                raise EditorError("Materiały zmieniły się przed zamrożeniem eksportu", "revision_conflict")
            for filename, data in {"brief.json":p.get("production",{}), "assets-manifest.json":frozen_assets,
                                   "shot-list.json":p["scenes"], "motion-rules.json":{e["id"]:e.get("motion") for e in p["elements"]}}.items():
                (directory/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
            reviewed = production_status.get("review")
            if reviewed:
                shutil.copytree(root/"reviews"/reviewed["id"], directory/"review")
                (directory/"review"/"review.json").write_text(json.dumps(reviewed,ensure_ascii=False,indent=2),encoding="utf-8")
            from .delivery import freeze_notices
            freeze_notices(p,directory)
            html = directory / "index.html"
            html.write_text(compile_project(p), encoding="utf-8")
            renderer = Path(__file__).resolve().parents[1] / "vstudio/renderers/html_to_video.py"
            video = directory / "picture.mp4"
            # Capture at the project viewport; draft changes encoding quality only.
            cmd = [sys.executable, str(renderer), str(html), "-o", str(video), "--size", f'{p["canvas"]["width"]}x{p["canvas"]["height"]}',
                   "--fps", str(p["canvas"]["fps"]), "--duration", str(p["duration"]), "--crf", "18" if quality == "final" else "26",
                   "--preset", "veryfast"]
            subframes = 4 if quality == "final" and p["canvas"].get("fx", {}).get("motionBlur") else 1
            if subframes > 1:
                # Filmowe rozmycie ruchu: uśrednienie 4 podklatek w migawce 180°.
                cmd += ["--subframes", "4", "--shutter", "0.5"]
            with (directory / "render.log").open("w") as log:
                # Długie filmy i rozmycie ruchu (kilka zrzutów na klatkę) potrzebują więcej czasu.
                frames = p["duration"] * p["canvas"]["fps"] * subframes
                cp = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=max(1800, frames * 10))
            if cp.returncode:
                raise EditorError((directory / "render.log").read_text(encoding="utf-8")[-2000:], "render_failed")
            self._update(job_id, progress=.85)
            final = directory / "framecore.mp4"
            audio = [e for e in p["elements"] if e["type"] == "audio" and not next(t for t in p["tracks"] if t["id"] == e["trackId"])["muted"]]
            if audio:
                assets = {a["id"]: a for a in p["assets"]}
                args = ["ffmpeg", "-y", "-i", str(video)]
                filters = []
                for idx, e in enumerate(audio, 1):
                    args += ["-i", str(directory / assets[e["assetId"]]["file"])]
                    settings = e.get("audio", {"gain": 1, "fadeIn": 0, "fadeOut": 0})
                    chain = f'[{idx}:a]atrim=start={e["sourceStart"]}:duration={e["duration"]},asetpts=PTS-STARTPTS,volume={settings["gain"]}'
                    if settings["fadeIn"]: chain += f',afade=t=in:st=0:d={settings["fadeIn"]}'
                    if settings["fadeOut"]: chain += f',afade=t=out:st={e["duration"]-settings["fadeOut"]}:d={settings["fadeOut"]}'
                    filters.append(chain + f',adelay={round(e["start"]*1000)}:all=1[a{idx}]')
                filters.append("".join(f"[a{i}]" for i in range(1,len(audio)+1))+f'amix=inputs={len(audio)}:normalize=0,apad,atrim=duration={p["duration"]}[out]')
                args += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[out]", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", str(final)]
                cp = subprocess.run(args, capture_output=True, text=True, timeout=180)
                if cp.returncode:
                    raise EditorError(cp.stderr[-2000:], "audio_mix_failed")
            else:
                video.rename(final)
            info = probe(final)
            self._update(job_id, status="complete", progress=1, url=f'/exports/{p["id"]}/{job_id}/framecore.mp4',
                         duration=float(info["format"]["duration"]), width=p["canvas"]["width"], height=p["canvas"]["height"])
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))
