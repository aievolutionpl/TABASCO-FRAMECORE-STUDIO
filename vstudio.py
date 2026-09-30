#!/usr/bin/env python3
"""vstudio CLI - analyze, build, edit, mix, critique, deliver.

    py -3 -I projects/video-studio/vstudio.py <komenda> [opcje]
    vstudio.cmd <komenda> [opcje]          (Windows, skrót)

`-I` (isolated) nie dodaje katalogu skryptu do sys.path, więc robimy to sami przed importem pakietu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # wymagane pod `py -3 -I`

for _stream in (sys.stdout, sys.stderr):  # konsola Windows to cp1252: polskie znaki wywalają --help i raporty
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # brak reconfigure (potok, stary Python) - nie blokujemy pracy
        pass

from vstudio import __version__  # noqa: E402
from vstudio import analyze as ana  # noqa: E402
from vstudio import audio as aud  # noqa: E402
from vstudio import compare as cmp  # noqa: E402
from vstudio import edl as edl_mod  # noqa: E402
from vstudio import pages  # noqa: E402
from vstudio import project as proj  # noqa: E402
from vstudio.common import ENGINES, GATES, OUTPUT, SCRIPTS, die, emit, load_project, run  # noqa: E402


# ------------------------------------------------------------------ helpers

def resolve_project(value: str | None) -> tuple[Path, dict]:
    """Ścieżka do projektu albo slug szukany w output/**; bez argumentu: jedyny projekt."""
    if value:
        p = Path(value)
        if (p / "project.json").exists():
            return load_project(p)
        hits = sorted(q.parent for q in OUTPUT.rglob("project.json") if value in str(q.parent))
        if len(hits) == 1:
            return load_project(hits[0])
        if not hits:
            die(f"brak projektu '{value}' w {OUTPUT}")
        die("niejednoznaczne '" + value + "': " + ", ".join(map(str, hits)))
    hits = sorted(q.parent for q in OUTPUT.rglob("project.json"))
    if len(hits) == 1:
        return load_project(hits[0])
    die("nie podano --project, a w output/ nie ma dokładnie jednego projektu")


def page_of(pdir: Path, pr: dict) -> Path:
    """Strona źródłowa dla komend opartych na kontrakcie strony (cues, readcheck, stills html)."""
    for rel in ("src/index.html", "src/src/index.html", "src/index.htm"):
        p = pdir / rel
        if p.exists():
            return p
    die(f"brak strony HTML w {pdir / 'src'} - komendy cues/readcheck wymagają kontraktu strony "
        f"(window.DURATION/seek/EV/TEXTS; patrz README projektu). Silnik '{pr.get('engine')}' go nie ma.")


def _times(s: str) -> list[float]:
    return [float(x) for x in s.replace(";", ",").split(",") if x.strip()]


def latest_render(pdir: Path, final: bool | None = None) -> Path:
    pat = "*_final_*.mp4" if final else "*_final_*.mp4" if final is None and list((pdir / "renders").glob("*_final_*.mp4")) else "*_draft_*.mp4"
    cands = sorted((pdir / "renders").glob(pat))
    if not cands and final is None:
        cands = sorted((pdir / "renders").glob("*.mp4"))
    if not cands:
        die(f"brak renderów w {pdir / 'renders'} (uruchom: vstudio render --draft)")
    return cands[-1]


# ------------------------------------------------------------------ cli

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vstudio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"vstudio {__version__}")
    ap.add_argument("--json", action="store_true", help="wyjście maszynowe (dla agentów)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="nowy projekt w output/<brand>/<slug>/")
    n.add_argument("slug")
    n.add_argument("--brand", required=True)
    n.add_argument("--engine", choices=ENGINES, default="html")
    n.add_argument("--size", default="1920x1080")
    n.add_argument("--fps", type=int, default=30)
    n.add_argument("--duration", type=float, default=15.0)
    n.add_argument("--kind", default="promo")
    n.add_argument("--ref", help="plik referencyjny do skopiowania do refs/")
    n.add_argument("--install", action="store_true", help="npm install (silnik remotion)")

    sub.add_parser("list", help="projekty w output/ i ich następny krok")
    sub.add_parser("doctor", help="sprawdzenie środowiska (uruchom to pierwsze)")

    for name in ("status", "still", "render", "gate", "cues", "sound", "readcheck", "deliver"):
        p = sub.add_parser(name)
        p.add_argument("--project", "-p", help="ścieżka lub slug (domyślnie: jedyny projekt w output/)")
        if name == "still":
            p.add_argument("--times", type=_times, default=[0.0, 1.5, 3.0, 5.0], help="np. 0,1.5,3,5")
        if name == "render":
            p.add_argument("--final", action="store_true")
            p.add_argument("--tag")
            p.add_argument("--subframes", type=int)
            p.add_argument("--audio")
            p.add_argument("--force", action="store_true")
        if name == "gate":
            p.add_argument("action", choices=["approve", "reset", "score"])
            p.add_argument("name", nargs="?", choices=GATES)
            p.add_argument("--score", type=float)
        if name == "cues":
            p.add_argument("--page")
            p.add_argument("--events", help="plik JSON z window.EV zamiast odczytu strony")
            p.add_argument("--out")
        if name == "sound":
            p.add_argument("--video", help="render do podłożenia dźwięku (domyślnie najnowszy)")
            p.add_argument("--out")
        if name == "readcheck":
            p.add_argument("--step", type=float, default=0.04)
        if name == "deliver":
            p.add_argument("--video")
            p.add_argument("--strict", action="store_true")
            p.add_argument("--poster-at", type=float, default=0.5)

    a_an = sub.add_parser("analyze", help="studium referencji -> SPEC.md + analysis.json + keyframes")
    a_an.add_argument("video")
    a_an.add_argument("--out")
    a_an.add_argument("--width", type=int, default=192)
    a_an.add_argument("--sensitivity", type=float, default=1.0)
    a_an.add_argument("--no-keyframes", action="store_true")

    a_c = sub.add_parser("compare", help="render vs referencja + CRITIC_BRIEF.md")
    a_c.add_argument("ref")
    a_c.add_argument("mine")
    a_c.add_argument("--out")
    a_c.add_argument("--project", "-p")
    a_c.add_argument("--no-reuse", action="store_true")

    a_e = sub.add_parser("edl", help="montaż z listy decyzji (EDL JSON)")
    e_sub = a_e.add_subparsers(dest="edl_cmd", required=True)
    eb = e_sub.add_parser("build")
    eb.add_argument("edl")
    eb.add_argument("-o", "--out", required=True)
    eb.add_argument("--preview", action="store_true")
    eb.add_argument("--keep-tmp", action="store_true")
    es = e_sub.add_parser("silence", help="wycinanie ciszy -> EDL")
    es.add_argument("src")
    es.add_argument("-o", "--out", required=True)
    es.add_argument("--noise-db", type=float, default=-32.0)
    es.add_argument("--min-len", type=float, default=0.45)
    es.add_argument("--pad", type=float, default=0.08)
    es.add_argument("--size")
    es.add_argument("--fps", type=float)

    a_s = sub.add_parser("sfx", help="proceduralne efekty (bez licencji)")
    a_s.add_argument("name", nargs="?", help="nazwa efektu; bez argumentu: lista")
    a_s.add_argument("-o", "--out")
    a_s.add_argument("--seed", type=int, default=1)

    a_m = sub.add_parser("mix", help="cue sheet JSON -> miks -14 LUFS")
    a_m.add_argument("cues")
    a_m.add_argument("-o", "--out", required=True)
    a_m.add_argument("--fps", type=float)

    a_x = sub.add_parser("mux", help="wideo + audio -> mp4")
    a_x.add_argument("video")
    a_x.add_argument("audio")
    a_x.add_argument("-o", "--out", required=True)

    a_q = sub.add_parser("qa", help="audyt pliku przez scripts/video_qa.py")
    a_q.add_argument("video")
    a_q.add_argument("--json")
    a_q.add_argument("--sheet")
    a_q.add_argument("--expect")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)

    # ---- komendy bez projektu
    if a.cmd == "new":
        print(proj.new_project(a))
        return 0
    if a.cmd == "list":
        rows = []
        for q in sorted(OUTPUT.rglob("project.json")):
            d, pr = load_project(q.parent)
            rows.append({"slug": pr["slug"], "brand": pr["brand"], "engine": pr["engine"], "dir": str(d), "next": proj.next_step(pr)})
        if a.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            print("\n".join(f"{r['slug']:<26} {r['brand']:<18} {r['engine']:<11} -> {r['next']}" for r in rows) or "(brak projektów)")
        return 0
    if a.cmd == "doctor":
        from vstudio.doctor import report
        return 0 if report(json_out=a.json) else 2
    if a.cmd == "analyze":
        video = Path(a.video)
        if not video.exists():
            die(f"nie ma pliku: {video}")
        out = Path(a.out) if a.out else video.parent / (video.stem + "_analysis")
        ana.analyze(video, out, width=a.width, sensitivity=a.sensitivity, keyframes=not a.no_keyframes)
        emit({"out": str(out)}, a.json, str(out))
        return 0
    if a.cmd == "edl":
        if a.edl_cmd == "build":
            src = Path(a.edl)
            if not src.exists():
                die(f"nie ma pliku EDL: {src}")
            data = json.loads(src.read_text(encoding="utf-8"))
            res = edl_mod.build_edl(data, src.parent, Path(a.out), preview=a.preview, keep_tmp=a.keep_tmp)
            emit(res, a.json, f"{res['output']}  {res['actual_duration']}s  {res['size']}")
            return 0
        d = edl_mod.silence_cut_edl(Path(a.src), a.size, a.fps, a.noise_db, a.min_len, a.pad)
        Path(a.out).write_text(json.dumps(d, indent=2), encoding="utf-8")
        emit(d, a.json, f"{len(d['clips'])} segmentów -> {a.out}")
        return 0
    if a.cmd == "sfx":
        if a.name is None:
            print("\n".join(aud.SFX))
            return 0
        out = Path(a.out) if a.out else Path.cwd() / f"{a.name}.wav"
        aud.write_wav(out, aud.synth(a.name, a.seed))
        print(out)
        return 0
    if a.cmd == "mix":
        cj = Path(a.cues)
        if not cj.exists():
            die(f"nie ma cue sheetu: {cj}")
        cues = json.loads(cj.read_text(encoding="utf-8"))
        res = aud.mix_cues(cues, cj.parent, Path(a.out), fps=a.fps)
        emit(res, a.json, f"{res['file']}  {res['loudness']}")
        return 0
    if a.cmd == "mux":
        print(aud.mux(Path(a.video), Path(a.audio), Path(a.out)))
        return 0
    if a.cmd == "qa":
        cmd = [sys.executable, str(SCRIPTS / "video_qa.py"), a.video]
        for flag, val in (("--json", a.json), ("--sheet", a.sheet), ("--expect", a.expect)):
            if val:
                cmd += [flag, val]
        cp = run(cmd, check=False)
        return cp.returncode

    # ---- komendy projektowe
    pdir, pr = resolve_project(getattr(a, "project", None))

    if a.cmd == "compare":
        out = Path(a.out) if a.out else pdir / "analysis" / "compare"
        cmp.compare(Path(a.ref), Path(a.mine), out, reuse=not a.no_reuse)
        emit({"out": str(out)}, a.json, str(out))
        return 0
    if a.cmd == "status":
        emit(pr, a.json, proj.cmd_status(pdir, pr))
        return 0
    if a.cmd == "gate":
        print(proj.cmd_gate(pdir, pr, a.action, a.name, getattr(a, "score", None)))
        return 0
    if a.cmd == "still":
        outs = proj.render_stills(pdir, pr, a.times)
        emit({"stills": [str(o) for o in outs]}, a.json, "\n".join(str(o) for o in outs))
        return 0
    if a.cmd == "render":
        out = proj.render(pdir, pr, final=a.final, tag=a.tag, subframes=a.subframes, audio=a.audio, force=a.force)
        emit({"render": str(out)}, a.json, str(out))
        return 0
    if a.cmd == "readcheck":
        page = page_of(pdir, pr)
        res = pages.readcheck(page, step=a.step, fps=pr["fps"], size=tuple(pr["size"]))
        emit(res, a.json, "OK: wszystkie teksty czytelne i w kadrze" if res["ok"]
             else "\n".join("! " + f for f in res["failures"]))
        return 0 if res["ok"] else 3
    if a.cmd == "cues":
        page = Path(a.page) if a.page else page_of(pdir, pr)
        ev = json.loads(Path(a.events).read_text(encoding="utf-8")) if a.events else pages.events(page, size=tuple(pr["size"]))
        cues = pages.events_to_cues(ev)
        out = Path(a.out) if a.out else pdir / "audio" / "cues.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cues, indent=2, ensure_ascii=False), encoding="utf-8")
        emit({"cues": str(out), "hits": len(cues["hits"]), "duration": cues["duration"]}, a.json,
             f"{len(cues['hits'])} cue -> {out}")
        return 0
    if a.cmd == "sound":
        page = page_of(pdir, pr)
        ev = pages.events(page, size=tuple(pr["size"]))
        cues = pages.events_to_cues(ev)
        adir = pdir / "audio"
        adir.mkdir(exist_ok=True)
        (adir / "cues.json").write_text(json.dumps(cues, indent=2, ensure_ascii=False), encoding="utf-8")
        mixf = adir / "mix.m4a"
        res = aud.mix_cues(cues, pdir, mixf, fps=pr["fps"])
        video = Path(a.video) if a.video else latest_render(pdir)
        out = Path(a.out) if a.out else (pdir / "renders" / (video.stem + "_sound.mp4"))
        aud.mux(video, mixf, out)
        emit({"mix": str(mixf), "video": str(out), "loudness": res["loudness"], "hits": len(cues["hits"])}, a.json,
             f"{out}\n  ({len(cues['hits'])} cue, {res['loudness']})")
        return 0
    if a.cmd == "deliver":
        res = proj.deliver(pdir, pr, Path(a.video) if a.video else None, a.strict, a.poster_at)
        emit(res, a.json, res["video"] + ("\n! " + "\n! ".join(res["warnings"]) if res["warnings"] else ""))
        return 0
    die(f"nieobsłużona komenda: {a.cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
