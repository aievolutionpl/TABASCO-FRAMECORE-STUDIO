"""Measurements of the decoded, frozen MP4; advice, never a creative verdict.
Adapted from echris6/motion-video-kit (MIT), see docs/MOTION_VIDEO_KIT.md.
"""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from vstudio.locking import atomic_write, file_lock
from .model import EditorError, now
from .render import probe

PROFILES = {
    "calm": {"label": "Spokojny", "targetLufs": -16, "minimumLra": 1.5},
    "punchy": {"label": "Dynamiczny", "targetLufs": -14, "minimumLra": 3},
    "mute": {"label": "Świadoma cisza", "targetLufs": None, "minimumLra": None},
}


def run(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EditorError("Nie udało się uruchomić pomiaru FFmpeg", "measurement_failed") from exc
    if result.returncode: raise EditorError("FFmpeg nie mógł zmierzyć tego filmu", "measurement_failed")
    return result


def frozen_intervals(metadata, duration, threshold=.35):
    """10 Hz luma differences in 8-bit units, including explicit timestamps."""
    pattern = r"pts_time:([\d.]+)\s+lavfi.signalstats.YAVG=([\d.]+)"
    intervals = []
    for match in re.finditer(pattern, metadata):
        t, difference = map(float, match.groups())
        if difference >= threshold: continue
        start, end = max(0, t-.1), min(duration, t)
        if end <= start: continue
        if intervals and start <= intervals[-1]["end"]+.011:
            intervals[-1]["end"] = round(end, 4)
        else: intervals.append({"start": round(start, 4), "end": round(end, 4)})
    for interval in intervals: interval["duration"] = round(interval["end"]-interval["start"],4)
    return intervals


def measure(path, profile="calm"):
    if not isinstance(profile,str) or profile not in PROFILES: raise EditorError("Wybierz profil calm, punchy lub mute")
    info = probe(path)
    duration = float(info["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0: raise EditorError("Film wymaga dodatniego czasu")
    result = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:v:0",
                  "-vf", "fps=10,scale=320:-2,format=gray,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                  "-an", "-f", "null", "-"])
    if not re.search(r"lavfi.signalstats.YAVG=", result.stdout):
        raise EditorError("Za krótki film do pomiaru różnic przy 10 klatkach/s", "measurement_failed")
    holds = frozen_intervals(result.stdout, duration)
    frozen = round(sum(h["duration"] for h in holds),4)
    warnings = []
    if frozen > duration/30: warnings.append({"code":"frozen_total", "message":"Dużo prawie nieruchomego obrazu; sprawdź rytm i cel pauz"})
    for h in holds:
        # The final 1.5 s may intentionally hold a CTA; retain every interval in evidence.
        before_cta = max(0, min(h["end"], duration-1.5)-h["start"])
        if before_cta > .6+.001:
            warnings.append({"code":"long_hold", "time":h["start"], "message":"Zastój dłuższy niż 0,6 s poza ostatnimi 1,5 s; sprawdź, czy jest zamierzony"})
    audio = {"present": any(s["codec_type"] == "audio" for s in info["streams"])}
    if audio["present"]:
        result = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
        summary = result.stderr.rsplit("Summary:",1)[-1]
        for label, key in (("I","integratedLufs"),("LRA","rangeLu"),("Peak","truePeakDbfs")):
            m = re.search(r"^\s*"+label+r":\s*([-+]?(?:\d+(?:\.\d*)?|inf))",summary,re.M)
            if not m: raise EditorError("Niepełny pomiar głośności FFmpeg", "measurement_failed")
            value = float(m.group(1)); audio[key] = value if math.isfinite(value) else None
        if audio["truePeakDbfs"] is not None and audio["truePeakDbfs"] > -1:
            warnings.append({"code":"true_peak", "message":"Szczyt rzeczywisty przekracza −1 dBFS; zmniejsz miks"})
        if profile == "mute":
            warnings.append({"code":"audio_present", "message":"Wybrano ciszę, ale MP4 zawiera ścieżkę audio"})
        else:
            target = PROFILES[profile]["targetLufs"]
            if audio["integratedLufs"] is None or abs(audio["integratedLufs"]-target)>2:
                warnings.append({"code":"loudness", "message":f"Głośność odbiega od orientacyjnego celu {target} LUFS; oceń miks odsłuchem"})
            if duration >= 10 and audio["rangeLu"] < PROFILES[profile]["minimumLra"]:
                warnings.append({"code":"dynamics", "message":"Mała zmienność głośności; sprawdź, czy muzyka wspiera dramaturgię"})
    elif profile != "mute":
        warnings.append({"code":"audio_missing", "message":"Film nie ma ścieżki audio. Wybierz świadomą ciszę albo dodaj dźwięk"})
    return {"profile":profile, "targets":{**PROFILES[profile], "truePeakDbfs":-1, "frozenSecondsPer30":1, "maximumHoldSeconds":.6},
            "duration":duration, "motion":{"sampleFps":10, "threshold":.35, "intervals":holds, "frozenSeconds":frozen,
            "longestHold":max((h["duration"] for h in holds),default=0)}, "audio":audio, "warnings":warnings,
            "limitations":"Pomiar różnic luminancji przy 10 FPS i szerokości 320 px może pominąć drobny ruch. Pauzy i końcowe CTA wymagają oceny człowieka. LUFS i szczyty nie zastępują odsłuchu; brak pomiaru kontrastu, koloru marki i relacji efektów do muzyki. Raport nie zatwierdza filmu."}


def export_directory(store, jobs, pid, job_id):
    job = jobs.get(job_id)
    if job["project_id"] != pid or job["status"] != "complete": raise EditorError("Wybierz ukończony eksport tego projektu")
    return job, store.directory(pid)/"exports"/job_id


def analyze(store, jobs, pid, job_id, profile="calm"):
    job, directory = export_directory(store,jobs,pid,job_id)
    with file_lock(directory/".quality-lock"):
        film = directory/"framecore.mp4"
        sha = hashlib.sha256(film.read_bytes()).hexdigest()
        report = measure(film,profile)
        if sha != hashlib.sha256(film.read_bytes()).hexdigest(): raise EditorError("Film zmienił się podczas pomiaru", "revision_conflict")
        report.update(project_id=pid,job_id=job_id,revision=job["revision"],sha256=sha,createdAt=now(),
                      url=f"/exports/{pid}/{job_id}/quality-report.json")
        atomic_write(directory/"quality-report.json",json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
        return report


def get_report(store,jobs,pid,job_id):
    _, directory = export_directory(store,jobs,pid,job_id)
    path = directory/"quality-report.json"
    if not path.is_file(): raise EditorError("Najpierw wykonaj pomiar eksportu", "not_found")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["sha256"] != hashlib.sha256((directory/"framecore.mp4").read_bytes()).hexdigest():
        raise EditorError("Film zmienił się po pomiarze", "revision_conflict")
    return report
