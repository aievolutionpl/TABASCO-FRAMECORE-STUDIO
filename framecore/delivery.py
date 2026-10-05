"""Delivery package from a completed, frozen export; never from live project state."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from .model import EditorError


def freeze_notices(p, directory):
    """Preserve complete original notices for redistributed assets and embedded fonts."""
    import shutil
    from .library import manifest
    repo = Path(__file__).resolve().parents[1]
    catalogue = manifest()
    used_fonts = {e["style"]["fontFamily"] for e in p["elements"] if e["type"] in {"text","caption"}}
    fonts = [f for f in catalogue["fonts"] if f["family"] in used_fonts]
    paths = {f["licenseFile"] for f in fonts}
    entries = {a["id"]:a for a in catalogue["assets"]}
    for a in p["assets"]:
        provenance = a.get("provenance",{})
        if provenance.get("source") == "phosphor_builtin": paths.add("licenses/Phosphor-MIT.txt")
        entry = entries.get(provenance.get("library_id")) if provenance.get("source")=="framecore_builtin" else None
        if entry: paths.add(entry["licenseFile"])
    out = Path(directory)/"licenses"; out.mkdir(exist_ok=True)
    for path in paths: shutil.copy2(repo/path,out/Path(path).name)
    shutil.copy2(repo/"LICENSE",out/"FRAMECORE-MIT.txt")
    (Path(directory)/"font-manifest.json").write_text(json.dumps(fonts,ensure_ascii=False,indent=2),encoding="utf-8")


def package(store, jobs, pid, job_id):
    job = jobs.get(job_id)
    if job["project_id"] != pid or job["status"] != "complete":
        raise EditorError("Wybierz ukończony eksport tego projektu")
    directory = store.directory(pid)/"exports"/job_id
    p = json.loads((directory/"project.json").read_text(encoding="utf-8"))
    credits = ["# Materiały filmu", "", "Źródła i licencje według zamrożonego projektu. Materiały użytkownika wymagają jego praw do dystrybucji.", ""]
    for a in p["assets"]:
        credits.append(f"- {a['name']}: {a.get('license','nie podano')} — {json.dumps(a.get('provenance',{}),ensure_ascii=False)}")
    for f in json.loads((directory/"font-manifest.json").read_text(encoding="utf-8")):
        credits.append(f"- Font {f['family']}: {f['license']} — {f['source']}; pełny tekst w licenses/{Path(f['licenseFile']).name}")
    (directory/"CREDITS.md").write_text("\n".join(credits),encoding="utf-8")
    target = directory/"delivery.zip"
    temp = directory/"delivery.tmp"
    from vstudio.locking import file_lock
    with file_lock(directory/".delivery-lock"):
        with ZipFile(temp,"w",ZIP_DEFLATED) as archive:
            for file in sorted(directory.rglob("*")):
                if file.is_file() and (file.name in {"framecore.mp4","project.json","brief.json","assets-manifest.json","font-manifest.json","shot-list.json","motion-rules.json","CREDITS.md","index.html"}
                                       or file.is_relative_to(directory/"assets") or file.is_relative_to(directory/"review") or file.is_relative_to(directory/"licenses")):
                    archive.write(file,str(file.relative_to(directory)))
        temp.replace(target)
    return {"project_id":pid,"revision":p["revision"],"job_id":job_id,"url":f"/exports/{pid}/{job_id}/delivery.zip","bytes":target.stat().st_size}
