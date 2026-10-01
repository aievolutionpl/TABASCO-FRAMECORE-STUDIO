"""Stan warsztatu: profil marki, projekty, biblioteka szablonów, edycja sceny z historią, zadania dla agenta.

Wszystko, co należy do użytkownika (profil, zadania, joby, vendor), leży w output/.studio/ (poza repozytorium).
Funkcje rzucają StudioError z komunikatem zrozumiałym dla człowieka i agenta; rejestr możliwości zamienia to na błąd operacji.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from . import common, project as proj, vendor
from .locking import atomic_write, file_lock
from .common import GATES, OUTPUT, STUDIO, StudioError

FORMATS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}
DEFAULT_PROFILE = {
    "onboarded": False, "name": "", "palette": {"bg": "#0B0E24", "ink": "#F4F6FF", "accent": "#FF6B4A", "accent2": "#4F8CFF"},
    "font": "Inter", "tone": "konkretny, spokojny, bez przesady", "audience": "", "default_format": "4:5", "fps": 30,
    "auto_supervise": True,          # dashboard sprawdza scenę w tle, gdy zmieni się na dysku (agent, edytor)
    "require_director": True,         # finalny render i wydanie wymagają zatwierdzenia reżysera dla aktualnej wersji sceny
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)?$")


# ------------------------------------------------------------------ pliki stanu

def _state(name: str) -> Path:
    common.STATE_DIR.mkdir(parents=True, exist_ok=True)
    return common.STATE_DIR / name


def _read_json(name: str, default):
    f = _state(name)
    if not f.exists():
        return default
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return default


def _write_json(name: str, data) -> None:
    atomic_write(_state(name), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _state_lock():
    """Blokada między procesami (MCP + dashboard) dla odczytu-zmiany-zapisu plików stanu."""
    return file_lock(common.STATE_DIR / ".lock")


# ------------------------------------------------------------------ profil marki

def profile_get() -> dict:
    p = _read_json("profile.json", {})
    merged = {**DEFAULT_PROFILE, **p, "palette": {**DEFAULT_PROFILE["palette"], **p.get("palette", {})}}
    return merged


def profile_set(patch: dict) -> dict:
    allowed = set(DEFAULT_PROFILE) - {"onboarded"}
    unknown = sorted(set(patch) - allowed)
    if unknown:
        raise StudioError(f"nieznane pola profilu {unknown}; dozwolone: {sorted(allowed)}")
    with _state_lock():
        return _profile_set(patch)


def _profile_set(patch: dict) -> dict:
    p = profile_get()
    for k, v in patch.items():
        if k == "palette":
            if not isinstance(v, dict) or set(v) - set(DEFAULT_PROFILE["palette"]):
                raise StudioError(f"palette: klucze {sorted(DEFAULT_PROFILE['palette'])}")
            for ck, cv in v.items():
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(cv)):
                    raise StudioError(f"palette.{ck}: kolor musi mieć postać #RRGGBB")
            p["palette"] = {**p["palette"], **v}
        elif k == "default_format":
            if v not in FORMATS:
                raise StudioError(f"default_format: jedno z {list(FORMATS)}")
            p[k] = v
        elif k in ("auto_supervise", "require_director"):
            p[k] = bool(v)
        elif k == "fps":
            if not isinstance(v, int) or not 12 <= v <= 120:
                raise StudioError("fps: liczba całkowita 12-120")
            p[k] = v
        else:
            p[k] = str(v)[:200]
    p["onboarded"] = bool(p["name"].strip())
    _write_json("profile.json", p)
    return p


# ------------------------------------------------------------------ projekty

def project_id(pdir: Path) -> str:
    return pdir.relative_to(OUTPUT).as_posix()


def resolve(ref: str) -> tuple[Path, dict]:
    """„marka/slug” albo samo „slug” (gdy jednoznaczne). Tylko projekty w output/: żadnych ścieżek z zewnątrz."""
    ref = (ref or "").strip().strip("/")
    if not _ID_RE.match(ref):
        raise StudioError(f"niepoprawny identyfikator projektu '{ref}' (oczekuję 'marka/slug' albo 'slug')")
    if "/" in ref:
        pdir = OUTPUT / ref
        if not (pdir / "project.json").exists():
            raise StudioError(f"brak projektu '{ref}'. Dostępne: {', '.join(p['id'] for p in list_projects()) or '(brak)'}")
        return common.load_project(pdir)
    hits = [q.parent for q in OUTPUT.glob("*/*/project.json") if q.parent.name == ref and not q.parent.parent.name.startswith(".")]
    if not hits:
        raise StudioError(f"brak projektu '{ref}'. Dostępne: {', '.join(p['id'] for p in list_projects()) or '(brak)'}")
    if len(hits) > 1:
        raise StudioError(f"'{ref}' jest niejednoznaczne: {', '.join(project_id(h) for h in hits)}")
    return common.load_project(hits[0])


def _gates_done(pr: dict) -> tuple[int, int]:
    needed = [g for g in GATES if pr["gates"].get(g) != "n/a"]
    return sum(1 for g in needed if pr["gates"].get(g) not in (None, False)), len(needed)


def summarize(pdir: Path, pr: dict, detail: bool = False) -> dict:
    from . import director, supervisor

    done, total = _gates_done(pr)
    src = pdir / "src" / "index.html"
    rep = supervisor.latest(pdir)
    out = {"id": project_id(pdir), "slug": pr["slug"], "brand": pr["brand"], "engine": pr["engine"], "size": pr["size"], "fps": pr["fps"],
           "duration": pr["duration"], "gates_done": done, "gates_total": total, "next": proj.next_step(pr),
           "updated": src.stat().st_mtime if src.exists() else None,
           "check": {"verdict": rep["verdict"], "score": rep["score"], "round": rep["round"], "counts": rep["counts"]} if rep else None}
    ds = director.state(pdir)
    out["director"] = {"state": ds["state"], "verdict": ds["review"]["verdict"] if ds["review"] else None, "score": ds["review"]["score"] if ds["review"] else None}
    if detail:
        renders = []
        for f in sorted(list((pdir / "renders").glob("*.mp4")) + list((pdir / "renders").glob("*.mov")), key=lambda x: x.stat().st_mtime, reverse=True):
            renders.append({"file": f"renders/{f.name}", "mb": round(f.stat().st_size / 1e6, 2), "at": f.stat().st_mtime,
                            "final": "_final_" in f.name, "overlay": f.suffix == ".mov"})
        out.update(gates={g: pr["gates"].get(g) for g in GATES}, critic_score=pr.get("critic_score"), renders=renders,
                   has_source=src.exists(), status=proj.cmd_status(pdir, pr),
                   vendor=vendor.status_for_html(src.read_text(encoding="utf-8")) if src.exists() else None,
                   tasks=[t for t in tasks_list() if t["project"] == out["id"]],
                   finals=[f"final/{f.name}" for f in sorted((pdir / "final").glob("*")) if f.is_file()] if (pdir / "final").exists() else [])
    return out


def list_projects() -> list[dict]:
    rows = []
    for q in sorted(OUTPUT.glob("*/*/project.json")):
        if q.parent.parent.name.startswith("."):
            continue
        try:
            d, pr = common.load_project(q.parent)
            rows.append(summarize(d, pr))
        except (StudioError, KeyError, ValueError):
            continue
    rows.sort(key=lambda r: r["updated"] or 0, reverse=True)
    return rows


# ------------------------------------------------------------------ szablony

def templates() -> list[dict]:
    data = json.loads((STUDIO / "templates" / "catalog.json").read_text(encoding="utf-8"))
    out = []
    for t in data["templates"]:
        f = STUDIO / t["file"]
        html = expand_template(f.read_text(encoding="utf-8")) if f.exists() else ""
        st = vendor.status_for_html(html)
        out.append({**t, "available": f.exists(), "external": st["external"], "needs_network": bool(st["needs_network"])})
    return out


def get_template(tid: str) -> dict:
    for t in templates():
        if t["id"] == tid:
            if not t["available"]:
                raise StudioError(f"plik szablonu '{tid}' nie istnieje: {t['file']}")
            return t
    raise StudioError(f"nieznany szablon '{tid}'. Dostępne: {', '.join(t['id'] for t in templates())}")


KIT_MARK = "<!--@motion-kit-->"


def expand_template(html: str) -> str:
    """Szablon może zawierać znacznik `<!--@motion-kit-->`: w jego miejsce wchodzi templates/motion-kit.js (jedno źródło prawdy dla wszystkich szablonów)."""
    if KIT_MARK not in html:
        return html
    kit = (STUDIO / "templates" / "motion-kit.js").read_text(encoding="utf-8")
    return html.replace(KIT_MARK, "<script>\n" + kit + "\n</script>")


def template_html(tid: str) -> str:
    return expand_template((STUDIO / get_template(tid)["file"]).read_text(encoding="utf-8"))


def create_project(slug: str, brand: str | None = None, template: str | None = None, format: str | None = None,
                   size: str | None = None, fps: int | None = None, duration: float | None = None, brief: str | None = None,
                   kind: str = "promo") -> dict:
    prof = profile_get()
    brand = (brand or prof["name"] or "studio").strip()
    tpl = get_template(template) if template else None
    if size:
        if not re.fullmatch(r"\d{3,4}x\d{3,4}", size.lower()):
            raise StudioError("size: format WxH, np. 1080x1350")
        wh = size.lower()
    elif format:
        if format not in FORMATS:
            raise StudioError(f"format: jedno z {list(FORMATS)}")
        wh = "{}x{}".format(*FORMATS[format])
    elif tpl:
        wh = "{}x{}".format(*tpl["size"])
    else:
        wh = "{}x{}".format(*FORMATS[prof["default_format"]])
    ns = argparse.Namespace(slug=slug, brand=brand, engine="html", size=wh, fps=fps or (tpl["fps"] if tpl else prof["fps"]),
                            duration=float(duration or (tpl["duration"] if tpl else 10.0)), kind=kind, ref=None, install=False)
    pdir = proj.new_project(ns)
    src = pdir / "src" / "index.html"
    if tpl:
        html = template_html(tpl["id"])
        html = re.sub(r"<title>.*?</title>", f"<title>{common.slugify(slug)}</title>", html, count=1, flags=re.S)
        src.write_text(html, encoding="utf-8")
    if brief:
        with open(pdir / "BRIEF.md", "a", encoding="utf-8") as fh:
            fh.write(f"\n\n## Request\n\n{brief.strip()}\n")
    common.append_log(pdir, f"created from {'template ' + tpl['id'] if tpl else 'starter'}")
    _, pr = common.load_project(pdir)
    return summarize(pdir, pr, detail=True)


# ------------------------------------------------------------------ scena

def _scene_path(pdir: Path) -> Path:
    f = pdir / "src" / "index.html"
    if not f.exists():
        raise StudioError(f"brak {f.relative_to(pdir)} (silnik: pliki sceny inne niż html edytuj bezpośrednio)")
    return f


def scene_info(pdir: Path, pr: dict) -> dict:
    text = _scene_path(pdir).read_text(encoding="utf-8")
    return {"lines": text.count("\n") + 1, "bytes": len(text.encode()), "sha": hashlib.sha256(text.encode()).hexdigest()[:12],
            "hooks": {k: (k in text) for k in ("DURATION", "window.seek", "EV", "TEXTS", "__ready", "__CAPTURE__")},
            "vendor": vendor.status_for_html(text)}


def scene_read(pdir: Path, pr: dict, start_line: int | None = None, end_line: int | None = None, limit: int = 60000) -> dict:
    text = _scene_path(pdir).read_text(encoding="utf-8")
    lines = text.splitlines()
    if start_line or end_line:
        a, b = max((start_line or 1) - 1, 0), min(end_line or len(lines), len(lines))
        body, rng = "\n".join(lines[a:b]), [a + 1, b]
    else:
        body, rng = text, [1, len(lines)]
    trunc = len(body) > limit
    return {"project": project_id(pdir), "content": body[:limit], "range": rng, "truncated": trunc, **scene_info(pdir, pr)}


def _history_dir(pdir: Path) -> Path:
    return pdir / "src" / ".history"


def _backup(pdir: Path, note: str) -> str | None:
    src = _scene_path(pdir)
    hd = _history_dir(pdir)
    hd.mkdir(exist_ok=True)
    t = time.time()
    while True:                                               # dwa zapisy w tej samej milisekundzie nie mogą nadpisać jednej wersji
        name = f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(t))}-{int(t * 1000) % 1000:03d}.html"
        if not (hd / name).exists():
            break
        t += 0.001
    (hd / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (hd / (name + ".note")).write_text(note[:200], encoding="utf-8")
    olds = sorted(hd.glob("*.html"))[:-30]                    # trzymamy 30 ostatnich wersji
    for o in olds:
        o.unlink(missing_ok=True)
        (hd / (o.name + ".note")).unlink(missing_ok=True)
    return name


def _sane(content: str) -> None:
    if not content.strip():
        raise StudioError("pusta scena")
    if len(content.encode()) > 2_000_000:
        raise StudioError("scena większa niż 2 MB")
    if "<" not in content:
        raise StudioError("to nie wygląda na HTML (brak znaczników)")


def scene_write(pdir: Path, pr: dict, content: str, note: str = "") -> dict:
    _sane(content)
    src = pdir / "src" / "index.html"
    backup = _backup(pdir, note or "scene_write") if src.exists() else None
    src.parent.mkdir(exist_ok=True)
    src.write_text(content, encoding="utf-8")
    common.append_log(pdir, f"scene written ({len(content)} bytes){': ' + note if note else ''}")
    return {"project": project_id(pdir), "backup": backup, **scene_info(pdir, pr)}


def scene_patch(pdir: Path, pr: dict, edits: list[dict], note: str = "") -> dict:
    text = _scene_path(pdir).read_text(encoding="utf-8")
    applied = []
    for i, e in enumerate(edits, 1):
        if not isinstance(e, dict) or "find" not in e or "replace" not in e:
            raise StudioError(f"edit #{i}: potrzebne pola 'find' i 'replace'")
        find, repl, every = str(e["find"]), str(e["replace"]), bool(e.get("all"))
        n = text.count(find)
        if n == 0:
            raise StudioError(f"edit #{i}: nie znaleziono tekstu do zamiany: {find[:80]!r}. Przeczytaj scenę (scene_read) i skopiuj dokładny fragment.")
        if n > 1 and not every:
            raise StudioError(f"edit #{i}: tekst występuje {n} razy; rozszerz 'find' o kontekst albo ustaw all=true")
        text = text.replace(find, repl) if every else text.replace(find, repl, 1)
        applied.append({"edit": i, "replaced": n if every else 1})
    _sane(text)
    backup = _backup(pdir, note or "scene_patch")
    (pdir / "src" / "index.html").write_text(text, encoding="utf-8")
    common.append_log(pdir, f"scene patched ({len(edits)} edits){': ' + note if note else ''}")
    return {"project": project_id(pdir), "applied": applied, "backup": backup, **scene_info(pdir, pr)}


# ---- paleta: kolory #RRGGBB w scenie (formy 3-cyfrowe pomijamy: łatwo je pomylić z id/selektorami i encjami HTML)
_HEX6 = re.compile(r"(?<![&\w#])(?<!url\()(?<!href=\")(?<!href=')#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?(?![0-9a-zA-Z])")


def _hls(hexcol: str) -> tuple[float, float, float]:
    import colorsys

    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ll, ss


def _is_neutral(hexcol: str) -> bool:
    _, ll, ss = _hls(hexcol)
    return ss < 0.18 or ll < 0.22 or ll > 0.88          # prawie czarny/biały/szary i ciemny granat: tło lub tekst, nie akcent


def brand_suggestion(colors: list[dict], palette: dict) -> list[dict]:
    """Propozycja mapowania kolorów sceny na paletę marki (tło, tekst, akcent, akcent 2). To podpowiedź do zatwierdzenia, nie automat."""
    by_count = sorted(colors, key=lambda c: -c["count"])
    neutrals = [c for c in by_count if _is_neutral(c["hex"])]
    chromatic = [c for c in by_count if not _is_neutral(c["hex"])]
    out: list[dict] = []
    used: set[str] = set()

    def add(role: str, src: dict | None) -> None:
        if src and src["hex"] not in used and src["hex"].upper() != palette[role].upper():
            used.add(src["hex"])
            out.append({"role": role, "from": src["hex"], "to": palette[role].upper()})

    if neutrals:
        dark_theme = _hls(neutrals[0]["hex"])[1] < 0.5
        dark = [c for c in neutrals if _hls(c["hex"])[1] < 0.5]
        light = [c for c in neutrals if _hls(c["hex"])[1] >= 0.5]
        add("bg", (dark if dark_theme else light)[0] if (dark if dark_theme else light) else None)
        add("ink", (light if dark_theme else dark)[0] if (light if dark_theme else dark) else None)
    add("accent", chromatic[0] if chromatic else None)
    if len(chromatic) > 1:
        far = next((c for c in chromatic[1:] if abs(_hls(c["hex"])[0] - _hls(chromatic[0]["hex"])[0]) >= 40), chromatic[1])
        add("accent2", far)
    return out


def scene_palette(pdir: Path, pr: dict) -> dict:
    text = _scene_path(pdir).read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for m in _HEX6.finditer(text):
        k = "#" + m.group(1).upper()
        counts[k] = counts.get(k, 0) + 1
    colors = []
    for hx, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        hue, light, sat = _hls(hx)
        colors.append({"hex": hx, "count": n, "lightness": round(light, 2), "saturation": round(sat, 2), "neutral": _is_neutral(hx)})
    prof = profile_get()
    return {"project": project_id(pdir), "colors": colors, "brand": prof["palette"] if prof["onboarded"] else None,
            "suggestion": brand_suggestion(colors, prof["palette"]) if prof["onboarded"] and colors else []}


def scene_recolor(pdir: Path, pr: dict, mapping: dict, note: str = "") -> dict:
    """Podmienia kolory w scenie jednym przebiegiem (A->B nie łańcuchuje się z B->C), z kopią w historii."""
    if not isinstance(mapping, dict) or not mapping:
        raise StudioError("mapping: obiekt {\"#STARY\": \"#NOWY\"} z co najmniej jednym kolorem")
    norm: dict[str, str] = {}
    for old, new in mapping.items():
        for c in (old, new):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(c)):
                raise StudioError(f"kolor '{c}' musi mieć postać #RRGGBB")
        norm[str(old).upper()] = str(new).upper()
    text = _scene_path(pdir).read_text(encoding="utf-8")
    counts: dict[str, int] = {}

    def swap(m: re.Match) -> str:
        key = "#" + m.group(1).upper()
        if key in norm:
            counts[key] = counts.get(key, 0) + 1
            return norm[key] + (m.group(2) or "")            # przezroczystość (#RRGGBBAA) zostaje
        return m.group(0)

    out = _HEX6.sub(swap, text)
    missing = [k for k in norm if k not in counts]
    if not counts:
        raise StudioError(f"żaden z kolorów {sorted(norm)} nie występuje w scenie (scene_palette pokazuje, jakie są)")
    backup = _backup(pdir, note or "scene_recolor")
    (pdir / "src" / "index.html").write_text(out, encoding="utf-8")
    common.append_log(pdir, f"scene recolored ({sum(counts.values())} replacements)")
    return {"project": project_id(pdir), "replaced": counts, "not_found": missing, "backup": backup, **scene_info(pdir, pr)}


def scene_history(pdir: Path) -> list[dict]:
    hd = _history_dir(pdir)
    out = []
    for f in sorted(hd.glob("*.html"), reverse=True) if hd.exists() else []:
        n = hd / (f.name + ".note")
        out.append({"version": f.name, "bytes": f.stat().st_size, "note": n.read_text(encoding="utf-8") if n.exists() else ""})
    return out


def scene_restore(pdir: Path, pr: dict, version: str) -> dict:
    if "/" in version or "\\" in version or not version.endswith(".html"):
        raise StudioError("niepoprawna wersja")
    f = _history_dir(pdir) / version
    if not f.is_file():
        raise StudioError(f"brak wersji '{version}'. Zobacz scene_history.")
    content = f.read_text(encoding="utf-8")                  # najpierw odczyt: kopia poniżej przycina historię do 30 wersji
    backup = _backup(pdir, f"before restore of {version}")
    (pdir / "src" / "index.html").write_text(content, encoding="utf-8")
    common.append_log(pdir, f"scene restored from {version}")
    return {"project": project_id(pdir), "restored": version, "backup": backup, **scene_info(pdir, pr)}


# ------------------------------------------------------------------ zadania dla agenta

def tasks_list(status: str | None = None) -> list[dict]:
    rows = _read_json("tasks.json", [])
    return [t for t in rows if status is None or t["status"] == status]


def task_create(prompt: str, project: str | None = None, source: str = "dashboard") -> dict:
    if not prompt.strip():
        raise StudioError("pusty opis zadania")
    if project:
        project = project_id(resolve(project)[0])           # zapisujemy id kanoniczne: sam slug nie pasowałby do filtrów po id
    with _state_lock():
        rows = _read_json("tasks.json", [])
        tid = f"T-{len(rows) + 1:04d}"
        t = {"id": tid, "project": project, "prompt": prompt.strip()[:4000], "status": "open", "source": source,
             "created": time.time(), "updated": time.time(), "notes": []}
        rows.append(t)
        _write_json("tasks.json", rows)
    return t


def task_update(tid: str, status: str | None = None, note: str | None = None) -> dict:
    with _state_lock():
        rows = _read_json("tasks.json", [])
        t = next((r for r in rows if r["id"] == tid), None)
        if not t:
            raise StudioError(f"brak zadania {tid}")
        if status:
            t["status"] = status
        if note:
            t["notes"].append({"at": time.time(), "text": note[:1000]})
        t["updated"] = time.time()
        _write_json("tasks.json", rows)
    return t


def task_next() -> dict | None:
    """Najstarsze otwarte zadanie (albo to, które agent już zaczął), z kontekstem do działania."""
    rows = tasks_list()
    t = next((r for r in rows if r["status"] == "in_progress"), None) or next((r for r in rows if r["status"] == "open"), None)
    return t
