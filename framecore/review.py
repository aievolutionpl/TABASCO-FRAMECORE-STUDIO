"""Actual browser evidence; manual review is explicit and bound to frozen content."""
from copy import deepcopy
import io
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw
from .persistence import atomic_write, file_lock
from .model import EditorError, identifier, number, now, uid
from .production import CHECKLIST, asset_manifest, fingerprint, require_assets


def load_review(directory, review_id):
    identifier(review_id)
    path = Path(directory) / "reviews" / review_id / "review.json"
    if not path.is_file(): raise EditorError("Nie znaleziono przeglądu", "not_found")
    return json.loads(path.read_text(encoding="utf-8"))


def latest_review(p, directory):
    paths = sorted((Path(directory) / "reviews").glob("*/review.json"), key=lambda f: f.stat().st_mtime_ns, reverse=True)
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["fingerprint"] == fingerprint(p):
            hashes = {a["id"]: a["sha256"] for a in asset_manifest(p, directory)}
            if report["assetHashes"] == hashes: return report
    return None


def frame_times(p, times=None):
    frame = 1 / p["canvas"]["fps"]
    last = max(0, p["duration"]-frame)
    if times is not None:
        if not isinstance(times, list) or not 1 <= len(times) <= 64: raise EditorError("Wybierz 1–64 czasy klatek")
        return sorted(set(round(min(last, number(t, "time", 0, last+1e-6)), 6) for t in times))
    # Prioritise beat midpoints, then both sides of cuts and motion completion.
    core = {0, round(last, 6)}
    for s in p["scenes"]: core.add(round(min(last, s["start"]+s["duration"]/2), 6))
    if len(core) > 64: raise EditorError("Wybierz czasy przeglądu dla projektu z ponad 62 beatami")
    extra = set()
    boundaries = {e["start"] for e in p["elements"]} | {s["start"] for s in p["scenes"]}
    for t in boundaries:
        for offset in (-frame, frame): extra.add(round(min(last, max(0, t+offset)), 6))
    for e in p["elements"]:
        if e.get("motion"): extra.add(round(min(last, e["start"]+e["motion"]["duration"]), 6))
        if e.get("exit"): extra.add(round(min(last, max(0, e["start"]+e["duration"]-e["exit"]["duration"]/2)), 6))
    extra = sorted(extra-core)
    capacity = max(0, max(24, len(core))-len(core))
    if len(extra) > capacity:
        extra = [extra[round(i*(len(extra)-1)/max(1,capacity-1))] for i in range(capacity)]
    return sorted(core | set(extra))


AUDIT_JS = """t => {
 const p=window.FRAMECORE_PROJECT, errors=[];
 for(const e of p.elements){
   const n=document.querySelector(`[data-element-id="${e.id}"]`), s=getComputedStyle(n);
   if(e.type==='audio'||s.visibility==='hidden'||Number(s.opacity)<.05||t-e.start<(e.motion?.duration||0))continue;
   const r=n.getBoundingClientRect();
   if(r.left<-.5||r.top<-.5||r.right>p.canvas.width+.5||r.bottom>p.canvas.height+.5)
     errors.push({code:'outside_canvas',element_id:e.id,time:t,message:'Element wychodzi poza kadr'});
   if(['text','caption'].includes(e.type)&&e.text.trim()){
     const range=document.createRange();range.selectNodeContents(n);const text=range.getBoundingClientRect();
     if(text.left<r.left-1||text.right>r.right+1||text.top<r.top-1||text.bottom>r.bottom+1)
       errors.push({code:'text_overflow',element_id:e.id,time:t,message:'Tekst przekracza swoje pole'});
   }
 }
 return errors;
}"""


def create_review(store, pid, expected_revision, times=None):
    from playwright.sync_api import sync_playwright
    from .server import start_background
    from .composition import compile_project
    from .inspection import inspect
    p = store.read(pid)["project"]
    if isinstance(expected_revision, bool) or not isinstance(expected_revision,int) or expected_revision != p["revision"]:
        raise EditorError("Konflikt rewizji przed przeglądem", "revision_conflict")
    root = store.directory(pid)
    require_assets(p, root)
    initial_assets = asset_manifest(p, root)
    selected_times = frame_times(p, times)
    rid = uid("review"); out = root / "reviews" / rid; out.mkdir(parents=True)
    server, _ = start_background(store)
    frames, errors, thumbs = [], [], []
    pixel_hashes = {}; determinism = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**({"executable_path": shutil.which("chromium")} if shutil.which("chromium") else {}))
            try:
                page = browser.new_page(viewport={"width": p["canvas"]["width"], "height": p["canvas"]["height"]})
                from .portable_media import install_capture_routes
                install_capture_routes(page, p, root)
                base = f"http://127.0.0.1:{server.server_port}"
                page.goto(base + "/composition/" + pid)
                page.set_content(compile_project(p, f"{base}/assets/{pid}/"))
                page.evaluate("window.__CAPTURE__=true"); page.evaluate("window.__ready")
                for i, t in enumerate(selected_times):
                    page.evaluate("t=>window.seek(t)", t)
                    issues = page.evaluate(AUDIT_JS, t); errors.extend(issues)
                    filename = f"frame-{i:03}.png"
                    data = page.screenshot(path=str(out/filename))
                    frames.append({"time": t, "file": filename, "url": f"/reviews/{pid}/{rid}/{filename}", "issues": issues})
                    image = Image.open(io.BytesIO(data)).convert("RGB")
                    pixel_hashes[t] = hashlib.sha256(image.tobytes()).hexdigest()
                    image.thumbnail((300, 220))
                    thumbs.append(image)
                # Return from a different position and reverse seek order for 3 actual samples.
                for t in reversed(sorted({selected_times[0], selected_times[len(selected_times)//2], selected_times[-1]})):
                    page.evaluate("t=>window.seek(t)", selected_times[0] if t != selected_times[0] else selected_times[-1])
                    page.evaluate("t=>window.seek(t)", t)
                    pixels = Image.open(io.BytesIO(page.screenshot())).convert("RGB").tobytes()
                    same = hashlib.sha256(pixels).hexdigest() == pixel_hashes[t]
                    determinism.append({"time":t, "identicalPixels":same})
                    if not same: errors.append({"code":"seek_inconsistent", "element_id":None, "time":t, "message":"Powrót do tego samego czasu dał inne piksele"})
            finally: browser.close()
    except Exception:
        shutil.rmtree(out)
        raise
    finally: server.shutdown(); server.server_close()
    cols = min(4, len(frames)); cellw, cellh = 320, 252
    sheet = Image.new("RGB", (cols*cellw, ((len(frames)+cols-1)//cols)*cellh), "#151719")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(thumbs):
        x,y = (i%cols)*cellw,(i//cols)*cellh
        sheet.paste(image, (x+(cellw-image.width)//2,y+5))
        draw.text((x+10,y+230), f"{frames[i]['time']:.3f}s  |  {'CHECK' if frames[i]['issues'] else 'FRAME'}", fill="#f48d6e")
    sheet.save(out/"contact-sheet.jpg", quality=90)
    if {a["id"]:a["sha256"] for a in initial_assets} != {a["id"]:a["sha256"] for a in asset_manifest(p, root)}:
        shutil.rmtree(out)
        raise EditorError("Materiały zmieniły się podczas przeglądu", "revision_conflict")
    report = {"id": rid, "project_id": pid, "revision": p["revision"], "fingerprint": fingerprint(p),
              "createdAt": now(), "assetHashes": {a["id"]: a["sha256"] for a in initial_assets},
              "frames": frames, "determinism":determinism, "errors": errors, "warnings": inspect(p)["issues"], "verdict": "pending",
              "checklist": {}, "notes": "", "sheetUrl": f"/reviews/{pid}/{rid}/contact-sheet.jpg",
              "limitations": "Próbkowane klatki; kontrola pola tekstu, kadru i powrotu do maksymalnie 3 czasów. To nie jest wyczerpujący test determinizmu. Hierarchię, zgodność marki, ciągłość i dźwięk oceń samodzielnie."}
    atomic_write(out/"review.json", json.dumps(report, ensure_ascii=False, indent=2))
    artifacts = {"brief.json":p.get("production",{}), "assets-manifest.json":asset_manifest(p,root),
                 "shot-list.json":p["scenes"], "motion-rules.json":{e["id"]:e.get("motion") for e in p["elements"]},
                 "project.json":p}
    for name, data in artifacts.items(): atomic_write(out/name, json.dumps(data,ensure_ascii=False,indent=2))
    return report


def verdict(store, pid, revision, review_id, value, checks, notes, actor):
    root = store.directory(pid)
    with file_lock(root/".lock"):
        p = deepcopy(store._load(pid)["project"])
        report = load_review(root,review_id)
        if isinstance(revision,bool) or not isinstance(revision,int) or revision != p["revision"] or report["fingerprint"] != fingerprint(p):
            raise EditorError("Przegląd jest nieaktualny; wygeneruj klatki ponownie", "revision_conflict")
        if value not in {"approved", "rejected"}: raise EditorError("Wybierz approved lub rejected")
        if not isinstance(checks,dict) or set(checks) != set(CHECKLIST) or any(not isinstance(v,bool) for v in checks.values()):
            raise EditorError("Oceń wszystkie punkty checklisty")
        if not isinstance(notes,str) or len(notes)>10000: raise EditorError("Nieprawidłowe uwagi przeglądu")
        hashes = {a["id"]:a["sha256"] for a in asset_manifest(p,root)}
        if report["assetHashes"] != hashes: raise EditorError("Materiały zmieniły się po przeglądzie", "revision_conflict")
        if value == "approved" and (report["errors"] or not all(checks.values())):
            raise EditorError("Napraw błędy klatek i przejdź całą checklistę przed zatwierdzeniem", "review_failed")
        report.update(verdict=value,checklist=checks,notes=notes,reviewer=actor,reviewedAt=now())
        atomic_write(root/"reviews"/review_id/"review.json",json.dumps(report,ensure_ascii=False,indent=2))
        return report
