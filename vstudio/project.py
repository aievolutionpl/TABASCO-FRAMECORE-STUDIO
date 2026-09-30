"""Project lifecycle: scaffold per engine, gates, stills, render, deliver.

A project lives in output/<brand>/<slug>/ and is engine-agnostic at the top level:

  project.json  BRIEF.md  VISUAL_RULES.md  MOTION_RULES.md  STORYBOARD.md  LOG.md
  src/          the engine project (html | hyperframes | remotion)
  refs/ analysis/ stills/ renders/ audio/ final/
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from .common import (ENGINES, GATES, OUTPUT, ROOT, SCRIPTS, STUDIO, append_log, die, ffprobe, find_chrome, grab_frame, image_sheet, load_project,
                     log, npx, run, save_project, sha256, slugify, today)

_STARTERS = (STUDIO / "templates" / "html-video-starter.html",          # dołączony do repo
             ROOT / "Skills" / "remotion-video-creator" / "templates" / "html-video-starter.html")
STARTER = next((p for p in _STARTERS if p.exists()), _STARTERS[0])
PRESETS = {(1920, 1080): "landscape", (1080, 1920): "portrait", (1080, 1080): "square", (3840, 2160): "landscape-4k",
           (2160, 3840): "portrait-4k", (2160, 2160): "square-4k"}

REMOTION_FILES = {
    "package.json": """{
  "name": "{{slug}}",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "remotion studio src/index.ts",
    "still": "remotion still src/index.ts Main out/still.png --frame=30",
    "render": "remotion render src/index.ts Main out/video.mp4"
  },
  "dependencies": {
    "@remotion/cli": "4.0.512",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "remotion": "4.0.512"
  },
  "devDependencies": {"@types/react": "19.2.7", "typescript": "5.9.3"}
}
""",
    "tsconfig.json": """{
  "compilerOptions": {"target": "ES2022", "module": "ESNext", "moduleResolution": "bundler", "jsx": "react-jsx", "strict": true, "skipLibCheck": true, "noEmit": true},
  "include": ["src"]
}
""",
    "remotion.config.ts": """import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
""",
    "src/index.ts": """import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
""",
    "src/Root.tsx": """import React from 'react';
import {Composition} from 'remotion';
import {Main} from './Main';

export const FPS = {{fps}};
export const RemotionRoot: React.FC = () => (
  <Composition id="Main" component={Main} durationInFrames={Math.round({{duration}} * FPS)} fps={FPS} width={{{width}}} height={{{height}}}
    defaultProps={{title: 'Title'}} />
);
""",
    "src/Main.tsx": """import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// Frames are a pure function of the frame number: no CSS animations, no timers, no Math.random().
// Motion rules: see ../MOTION_RULES.md (arrive fast and land soft, nothing freezes, stagger, hold text).
export const Main: React.FC<{title: string}> = ({title}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 20, stiffness: 200}});   // snappy, minimal bounce
  const push = interpolate(frame, [0, durationInFrames], [1, 1.0025 ** durationInFrames]);  // ~0.25% per frame: nothing freezes
  return (
    <AbsoluteFill style={{background: '#0b0d10', justifyContent: 'center', alignItems: 'center'}}>
      <div style={{transform: `scale(${push}) translateY(${(1 - enter) * 40}px)`, opacity: enter, color: '#f4f1ea',
        fontFamily: 'Inter, Segoe UI, sans-serif', fontWeight: 600, fontSize: 96}}>
        {title}
      </div>
    </AbsoluteFill>
  );
};
""",
}


def _fill(text: str, vals: dict) -> str:
    for k, v in vals.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def _find_brand_config(brand: str) -> str | None:
    key = re.sub(r"[^a-z0-9]", "", brand.lower())
    agents = ROOT / "Agents"
    if not agents.exists():
        return None
    for d in agents.iterdir():
        if d.is_dir() and re.sub(r"[^a-z0-9]", "", d.name.lower()) == key and (d / "CONFIG.md").exists():
            return str((d / "CONFIG.md").relative_to(ROOT)).replace("\\", "/")
    for d in agents.iterdir():
        if d.is_dir() and key and key in re.sub(r"[^a-z0-9]", "", d.name.lower()) and (d / "CONFIG.md").exists():
            return str((d / "CONFIG.md").relative_to(ROOT)).replace("\\", "/")
    return None


def new_project(a) -> Path:
    slug, brand = slugify(a.slug), slugify(a.brand)
    w, h = (int(x) for x in a.size.lower().split("x"))
    pdir = OUTPUT / brand / slug
    if pdir.exists():
        die(f"{pdir} already exists (vstudio never overwrites a project)")
    for d in ("src", "refs", "analysis", "stills", "renders", "audio", "final"):
        (pdir / d).mkdir(parents=True)
    cfg = _find_brand_config(a.brand)
    vals = {"slug": slug, "slug_path": pdir.relative_to(ROOT).as_posix(), "brand": brand, "engine": a.engine, "width": w, "height": h,
            "fps": a.fps, "duration": a.duration, "kind": a.kind, "brand_config": cfg or "Agents/<BRAND>/CONFIG.md",
            "brand_config_line": f"(config: `{cfg}`)" if cfg else "(no matching Agents/<BRAND>/CONFIG.md found: load the right one manually)"}
    for name in ("BRIEF.md", "VISUAL_RULES.md", "MOTION_RULES.md"):
        (pdir / name).write_text(_fill((STUDIO / "templates" / name).read_text(encoding="utf-8"), vals), encoding="utf-8")
    (pdir / "STORYBOARD.md").write_text(f"# Storyboard: {slug}\n\nOne row per shot: framing, duration, what moves, transition in, sound.\nRender key stills before anything else (`vstudio still`).\n", encoding="utf-8")
    proj = {"slug": slug, "brand": brand, "brand_config": cfg, "engine": a.engine, "kind": a.kind, "size": [w, h], "fps": a.fps, "duration": a.duration,
            "composition": "Main", "created": today(), "ref": a.ref, "gates": {g: None for g in GATES}, "critic_score": None, "renders": []}
    if a.ref:
        rp = Path(a.ref)
        if rp.exists():
            shutil.copy2(rp, pdir / "refs" / rp.name)
            proj["ref"] = f"refs/{rp.name}"
    else:
        proj["gates"]["reference_spec"] = "n/a"
    save_project(pdir, proj)
    append_log(pdir, f"created ({a.engine}, {w}x{h}@{a.fps}, {a.duration}s)")
    scaffold_engine(pdir, proj, vals, install=getattr(a, "install", False))
    (pdir / "README.md").write_text(
        f"# {slug}\n\nWork this project with `python projects/video-studio/vstudio.py` (see `Skills/video-studio/SKILL.md`).\n\n"
        f"    vstudio status {vals['slug_path']}\n\nFlow: brief -> (reference spec) -> visual rules -> stills -> draft -> sound -> critic -> final.\n", encoding="utf-8")
    return pdir


def scaffold_engine(pdir: Path, proj: dict, vals: dict, install: bool) -> None:
    src = pdir / "src"
    eng = proj["engine"]
    if eng == "html":
        if not STARTER.exists():
            die(f"starter template missing: {STARTER}")
        (src / "index.html").write_text(STARTER.read_text(encoding="utf-8").replace("<title>HTML video starter</title>", f"<title>{proj['slug']}</title>"), encoding="utf-8")
    elif eng == "remotion":
        for rel, body in REMOTION_FILES.items():
            f = src / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(_fill(body, vals), encoding="utf-8")
        if install:
            log("npm install (Remotion) ...")
            run(["npm.cmd" if sys.platform == "win32" else "npm", "install", "--no-audit", "--no-fund"], cwd=src, capture=False, timeout=1800)
        else:
            log("Remotion project written. Run `npm install` in src/ (or re-run with --install) before rendering.")
    elif eng == "hyperframes":
        w, h = proj["size"]
        preset = PRESETS.get((w, h), "landscape")
        shutil.rmtree(src, ignore_errors=True)
        cp = npx(["hyperframes", "init", "src", "--non-interactive", "--example", "blank", "--resolution", preset], cwd=pdir)
        if cp.returncode != 0 or not (src / "index.html").exists():
            die("hyperframes init failed:\n" + (cp.stderr or cp.stdout or "")[-600:])
        idx = src / "index.html"
        t = idx.read_text(encoding="utf-8")
        idx.write_text(re.sub(r'data-duration="10"', f'data-duration="{proj["duration"]}"', t), encoding="utf-8")
        if (w, h) not in PRESETS:
            log(f"note: {w}x{h} is not a HyperFrames preset; edit data-width/data-height in src/index.html")


# ------------------------------------------------------------------ status / gates

def next_step(proj: dict) -> str:
    g = proj["gates"]
    order = [("brief", "fill BRIEF.md, then: gate approve brief"),
             ("reference_spec", f"run `analyze {proj.get('ref')}` into analysis/, read SPEC.md, then: gate approve reference_spec"),
             ("visual_rules", "write VISUAL_RULES.md (fonts, palette, spacing, banned), then: gate approve visual_rules"),
             ("stills", "build the shots, render 5 stills (opening, main composition, product, fastest transition, end card), review zoomed, then: gate approve stills"),
             ("draft", "render --draft and run qa / readcheck"), ("sound", "build the cue sheet, mix, mux, then: gate approve sound"),
             ("critic", "compare + hand CRITIC_BRIEF.md to the video-critic subagent, fix, then: gate score <0-10>"), ("final", "render --final, then: deliver")]
    for name, msg in order:
        if g.get(name) in (None, False) and g.get(name) != "n/a":
            return f"{name}: {msg}"
    return "all gates passed: deliver"


def cmd_status(pdir: Path, proj: dict) -> str:
    rows = [f"{proj['slug']} ({proj['brand']}) | {proj['engine']} | {proj['size'][0]}x{proj['size'][1]}@{proj['fps']} | {proj['duration']}s",
            f"dir: {pdir}"]
    for g in GATES:
        v = proj["gates"].get(g)
        mark = "x" if v not in (None, False) else " "
        rows.append(f"  [{mark}] {g}" + (f"  ({v})" if isinstance(v, str) and v != "n/a" else "") + ("  (not needed)" if v == "n/a" else ""))
    if proj.get("critic_score") is not None:
        rows.append(f"  critic score: {proj['critic_score']}/10")
    rows.append(f"next -> {next_step(proj)}")
    return "\n".join(rows)


def cmd_gate(pdir: Path, proj: dict, action: str, name: str | None, score: float | None) -> str:
    if action == "score":
        if score is None:
            die("gate score needs a number")
        proj["critic_score"] = score
        proj["gates"]["critic"] = today() if score >= 8 else False
        msg = f"critic score {score}/10 -> {'passed' if score >= 8 else 'BELOW 8: fix and re-run the critic (nothing ships below 8/10)'}"
    else:
        if name not in GATES:
            die(f"unknown gate '{name}'. Gates: {', '.join(GATES)}")
        if action == "approve":
            proj["gates"][name] = today()
        elif action == "reset":
            proj["gates"][name] = None
        msg = f"{name}: {action}"
    save_project(pdir, proj)
    append_log(pdir, msg)
    return msg


# ------------------------------------------------------------------ stills

def render_stills(pdir: Path, proj: dict, times: list[float]) -> list[Path]:
    eng, (w, h), fps = proj["engine"], proj["size"], proj["fps"]
    sd = pdir / "stills"
    sd.mkdir(exist_ok=True)
    outs: list[Path] = []
    if eng == "html":
        for t in times:
            o = sd / f"t_{t:06.2f}.png"
            run([sys.executable, SCRIPTS / "html_to_video.py", pdir / "src" / "index.html", "--still", t, "--size", f"{w}x{h}", "--fps", fps, "-o", o])
            outs.append(o)
    elif eng == "hyperframes":
        raw = sd / "_raw"
        shutil.rmtree(raw, ignore_errors=True)
        cp = npx(["hyperframes", "snapshot", "src", "--at", ",".join(str(t) for t in times), "--no-end", "-o", str(raw.resolve())], cwd=pdir)
        files = sorted(raw.glob("*.png")) if raw.exists() else []
        if cp.returncode != 0 or not files:
            die("hyperframes snapshot failed:\n" + ((cp.stderr or "") + (cp.stdout or ""))[-600:])
        for t, f in zip(times, files):
            o = sd / f"t_{t:06.2f}.png"
            shutil.move(str(f), o)
            outs.append(o)
        shutil.rmtree(raw, ignore_errors=True)
    elif eng == "remotion":
        src = pdir / "src"
        if not (src / "node_modules").exists():
            die("run `npm install` in src/ first (or create the project with --install)")
        chrome = find_chrome()
        for t in times:
            o = sd / f"t_{t:06.2f}.png"
            cmd = ["remotion", "still", "src/index.ts", proj.get("composition", "Main"), str(o.resolve()), f"--frame={round(t * fps)}"]
            if chrome:
                cmd.append(f"--browser-executable={chrome}")
            cp = npx(cmd, cwd=src)
            if cp.returncode != 0 or not o.exists():
                die("remotion still failed:\n" + ((cp.stderr or "") + (cp.stdout or ""))[-600:])
            outs.append(o)
    sheet = image_sheet(outs, [f"t={t:g}s" for t in times], sd / "sheet.jpg", cols=min(len(outs), 3), tile_w=620)
    log(f"stills: {len(outs)} -> {sd} (sheet: {sheet.name}). Open every image and check hierarchy, spacing, type, colours, stray shapes, cut-off text.")
    append_log(pdir, f"stills at {times}")
    return outs


# ------------------------------------------------------------------ render

def render(pdir: Path, proj: dict, final: bool, tag: str | None, subframes: int | None, audio: str | None, force: bool) -> Path:
    eng, (w, h), fps = proj["engine"], proj["size"], proj["fps"]
    if final and not force:
        need = ["brief", "visual_rules", "stills"] + (["reference_spec"] if proj.get("ref") else [])
        missing = [g for g in need if proj["gates"].get(g) in (None, False)]
        if missing:
            die(f"final render blocked: gates not approved: {', '.join(missing)}. Approve them (`gate approve <name>`) once the work is actually done, or pass --force.")
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{proj['slug']}_{tag or ('final' if final else 'draft')}_{stamp}.mp4"
    out = pdir / "renders" / name
    if eng == "html":
        dw, dh = (w, h) if final else (w // 4 * 2, h // 4 * 2)
        dfps = fps if final else min(fps, 30)
        cmd = [sys.executable, SCRIPTS / "html_to_video.py", pdir / "src" / "index.html", "-o", out, "--size", f"{dw}x{dh}", "--fps", dfps]
        if final:
            cmd += ["--subframes", subframes if subframes is not None else 4, "--crf", 16, "--preset", "slow"]
        else:
            cmd += ["--crf", 24, "--preset", "veryfast"]
        if audio:
            cmd += ["--audio", audio]
        run(cmd, capture=False)
    elif eng == "hyperframes":
        cp = npx(["hyperframes", "render", "src", "-q", "delivery" if final else "draft", "-f", str(fps), "-o", str(out.resolve()), "--quiet"], cwd=pdir)
        if cp.returncode != 0 or not out.exists():
            die("hyperframes render failed:\n" + ((cp.stderr or "") + (cp.stdout or ""))[-800:])
        if audio:
            from .audio import mux
            silent = out.with_name(out.stem + "_silent.mp4")
            out.replace(silent)
            mux(silent, Path(audio), out)
            silent.unlink(missing_ok=True)
    elif eng == "remotion":
        src = pdir / "src"
        if not (src / "node_modules").exists():
            die("run `npm install` in src/ first")
        chrome = find_chrome()
        cmd = ["remotion", "render", "src/index.ts", proj.get("composition", "Main"), str(out.resolve()), "--crf", "17" if final else "28"]
        if not final:
            cmd += ["--scale", "0.5"]
        if chrome:
            cmd.append(f"--browser-executable={chrome}")
        cp = npx(cmd, cwd=src)
        if cp.returncode != 0 or not out.exists():
            die("remotion render failed:\n" + ((cp.stderr or "") + (cp.stdout or ""))[-800:])
        if audio:
            from .audio import mux
            silent = out.with_name(out.stem + "_silent.mp4")
            out.replace(silent)
            mux(silent, Path(audio), out)
            silent.unlink(missing_ok=True)
    if not out.exists():
        die(f"render produced no file: {out}")
    qa_json = out.with_suffix(".qa.json")
    qa_args = [sys.executable, SCRIPTS / "video_qa.py", out, "--json", qa_json]
    if final:
        qa_args += ["--expect", f"{w}x{h}@{fps}", "--duration", proj["duration"], "--tol", max(1.0, proj["duration"] * 0.1)]
    else:
        qa_args += ["--no-sheet"]
    run(qa_args, check=False)
    proj["renders"].append({"file": f"renders/{name}", "final": final, "at": __import__("datetime").datetime.now().isoformat(timespec="seconds")})
    if final:
        proj["gates"]["final"] = today()
    else:
        proj["gates"]["draft"] = today()
    save_project(pdir, proj)
    append_log(pdir, f"render {'final' if final else 'draft'}: renders/{name}")
    return out


# ------------------------------------------------------------------ deliver

def deliver(pdir: Path, proj: dict, video: Path | None, strict: bool, poster_at: float) -> dict:
    cands = sorted((pdir / "renders").glob("*_final_*.mp4"))
    src = video or (cands[-1] if cands else None)
    if not src or not src.exists():
        die("no final render to deliver (run render --final, or pass --video)")
    warnings = []
    if proj.get("critic_score") is None:
        warnings.append("critic has not scored this film (run compare and the video-critic subagent for anything that will be published)")
    elif proj["critic_score"] < 8:
        warnings.append(f"critic score {proj['critic_score']}/10 is below the 8/10 shipping bar")
    if strict and warnings:
        die("deliver blocked (--strict): " + "; ".join(warnings))
    fd = pdir / "final"
    fd.mkdir(exist_ok=True)
    out = fd / f"{proj['slug']}.mp4"
    shutil.copy2(src, out)
    poster = grab_frame(out, poster_at, fd / "poster.jpg", width=1280)
    qa = fd / "qa.json"
    run([sys.executable, SCRIPTS / "video_qa.py", out, "--json", qa, "--sheet", fd / "contact_sheet.png", "--frames", 12,
         "--expect", f"{proj['size'][0]}x{proj['size'][1]}@{proj['fps']}"], check=False)
    dash = []
    srcdir = pdir / "src"
    for f in list(srcdir.rglob("*.html")) + list(srcdir.rglob("*.tsx")) + list(srcdir.rglob("*.js")) + list(srcdir.rglob("*.json")):
        if "node_modules" in f.parts:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "—" in line:
                dash.append(f"{f.relative_to(pdir).as_posix()}:{i}")
    if dash:
        warnings.append(f"em dash (U+2014) found in {len(dash)} source line(s), e.g. {dash[:3]}: workspace rule is no em dashes in on-screen copy")
    info = ffprobe(out)
    man = [f"# Delivery: {proj['slug']}", "", f"- Brand: {proj['brand']}  | Engine: {proj['engine']}  | Delivered: {today()}",
           f"- File: `final/{out.name}` ({info['width']}x{info['height']} @ {info['fps']:.2f} fps, {info['duration']:.2f} s, {info['size_mb']} MB, audio: {'yes' if info['has_audio'] else 'no'})",
           f"- SHA-256: `{sha256(out)}`", f"- Poster: `final/{poster.name}`  | Contact sheet: `final/contact_sheet.png`  | QA: `final/qa.json`",
           f"- Critic score: {proj.get('critic_score', 'not scored')}", "", "## Gates", ""]
    man += [f"- {g}: {proj['gates'].get(g)}" for g in GATES]
    man += ["", "## Warnings", ""] + ([f"- {w}" for w in warnings] or ["- none"])
    man += ["", "## Credits (third-party assets in this film)", "", "- Sound: procedural (vstudio) unless listed here", "- Fonts: ", "- Music: ", "- Images / footage: ", "",
            "## Before publishing", "", "- Never publish without explicit user approval.",
            "- Home Fires Jersey: log to Notion (`Skills/hfj-notion-logger/SKILL.md`, database `3282c19fdc61800f80dbe10c1deefd46`)." if "home-fires" in proj["brand"] else "- Brand-specific logging, if any, per `Agents/<BRAND>/CONFIG.md`.",
            "- The user is responsible for the rights to any third-party material used.", ""]
    (fd / "DELIVERY.md").write_text("\n".join(man), encoding="utf-8")
    append_log(pdir, f"delivered final/{out.name}")
    return {"video": str(out), "poster": str(poster), "warnings": warnings, "manifest": str(fd / "DELIVERY.md")}
