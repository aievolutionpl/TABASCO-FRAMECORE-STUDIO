"""Reusable production contract, narrative beats and independent format layouts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .model import EditorError, FORMATS, identifier, number, uid

CHECKLIST = {
    "readability": "Teksty są czytelne i nie są ucięte",
    "hierarchy": "Każdy beat ma jeden główny punkt uwagi",
    "brand": "Materiały i branding odpowiadają briefowi",
    "continuity": "Wejścia, wyjścia i przejścia zachowują ciągłość",
    "audio": "Sprawdzono rytm i dźwięk albo świadomie wybrano ciszę",
}
EASINGS = {"linear", "quad-out", "cubic-out", "quint-out", "expo-out", "back-out", "elastic-out", "cubic-in-out"}
MOTION_RULES = {
    "text": {"duration": .65, "easing": "cubic-out"},
    "caption": {"duration": .35, "easing": "quad-out"},
    "image": {"duration": 1.0, "easing": "quint-out"},
    "video": {"duration": 1.1, "easing": "quint-out"},
    "shape": {"duration": .55, "easing": "cubic-out"},
}


def fingerprint(p):
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def text(value, limit=2000):
    if not isinstance(value, str) or len(value) > limit:
        raise EditorError("Nieprawidłowe pole kontraktu produkcyjnego")
    return value


def validate_contract(p):
    c = p.get("production", {})
    allowed = {"product", "message", "facts", "references", "rejectionCriteria", "requiredAssets", "requireReview"}
    if not isinstance(c, dict) or set(c) - allowed:
        raise EditorError("Nieznane pole kontraktu produkcyjnego")
    for key in ("product", "message"):
        if key in c: text(c[key])
    for key in ("facts", "references", "rejectionCriteria"):
        values = c.get(key, [])
        if not isinstance(values, list) or len(values) > 50: raise EditorError("Nieprawidłowa lista w briefie")
        for value in values: text(value)
    if not isinstance(c.get("requireReview", False), bool): raise EditorError("Bramka jakości wymaga wartości logicznej")
    required = c.get("requiredAssets", [])
    if not isinstance(required, list) or len(required) > 50: raise EditorError("Nieprawidłowe wymagane materiały")
    for a in required:
        if not isinstance(a, dict) or set(a) != {"label", "assetId"}: raise EditorError("Materiał wymaga label i assetId")
        if not text(a["label"], 200).strip(): raise EditorError("Podaj nazwę wymaganego materiału")
        if a["assetId"] is not None: identifier(a["assetId"])
    for scene in p["scenes"]:
        if "beat" not in scene: continue
        beat = scene["beat"]
        if not isinstance(beat, dict) or set(beat) != {"purpose", "entryState", "exitState", "focusElementId"}:
            raise EditorError("Beat wymaga purpose, entryState, exitState i focusElementId")
        for key in ("purpose", "entryState", "exitState"): text(beat[key])
        if beat["focusElementId"] is not None:
            focus = next((e for e in p["elements"] if e["id"] == beat["focusElementId"]), None)
            if not focus or focus["type"] == "audio" or focus["start"] >= scene["start"] + scene["duration"] or focus["start"] + focus["duration"] <= scene["start"]:
                raise EditorError("Główny element musi być widoczny w czasie beatu")


def annotate_beats(p):
    visual = [e for e in p["elements"] if e["type"] != "audio"]
    if not p["scenes"]:
        starts = sorted({0, *(e["start"] for e in visual)})
        if len(starts) > 50: raise EditorError("Zbyt wiele beatów; najpierw uporządkuj sceny")
        p["scenes"] = [{"id": uid("scene"), "name": f"BEAT {i+1:02}", "start": start,
                        "duration": (starts[i+1] if i+1 < len(starts) else p["duration"]) - start,
                        "message": "", "visualPurpose": "", "motionIntent": "", "audioIntent": ""}
                       for i, start in enumerate(starts) if start < p["duration"]]
    previous = "Widz poznaje początek historii"
    for scene in sorted(p["scenes"], key=lambda s: s["start"]):
        active = [e for e in visual if e["start"] < scene["start"] + scene["duration"] and e["start"] + e["duration"] > scene["start"]]
        focus = next((e for e in active if e["type"] == "text"), next(iter(active), None))
        message = scene.get("message") or (focus.get("text") if focus else "") or scene["name"]
        scene.setdefault("beat", {"purpose": message, "entryState": previous,
                                  "exitState": message, "focusElementId": focus["id"] if focus else None})
        previous = scene["beat"]["exitState"]


def asset_manifest(p, directory):
    result = []
    for a in p["assets"]:
        path = (Path(directory) / a["file"]).resolve()
        exists = path.is_relative_to(Path(directory).resolve()) and path.is_file()
        result.append({**deepcopy(a), "exists": exists, "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else None})
    return result


def status(p, directory):
    from .review import latest_review
    manifest = asset_manifest(p, directory)
    assets = {a["id"]: a for a in manifest}
    c = p.get("production", {})
    blockers = []
    for a in c.get("requiredAssets", []):
        if not assets.get(a["assetId"], {}).get("exists"):
            blockers.append({"code": "required_asset_missing", "message": f"Brak wymaganego materiału: {a['label']}"})
    used = {a["id"] for a in p["assets"]}
    for aid in used:
        if not assets.get(aid, {}).get("exists"):
            blockers.append({"code": "asset_file_missing", "message": f"Brak pliku materiału projektu: {aid}"})
    if c.get("requireReview"):
        for key in ("product", "message"):
            if not c.get(key, "").strip(): blockers.append({"code": "brief_incomplete", "message": "Uzupełnij produkt i główny komunikat"}); break
        if not p["scenes"] or any(not s.get("beat") or any(not s["beat"][k].strip() for k in ("purpose", "entryState", "exitState")) or not s["beat"]["focusElementId"] for s in p["scenes"]):
            blockers.append({"code": "beats_incomplete", "message": "Opisz stany, cel i główny element każdego beatu"})
    review = latest_review(p, directory)
    approved = bool(review and review.get("verdict") == "approved" and not review["errors"])
    return {"project_id": p["id"], "revision": p["revision"], "contract": c,
            "assets": manifest, "blockers": blockers, "review": review, "reviewApproved": approved,
            "finalReady": not blockers and (not c.get("requireReview") or approved),
            "checklist": CHECKLIST, "motionRules": MOTION_RULES,
            "nextAction": blockers[0]["message"] if blockers else "Eksportuj film" if approved else "Wygeneruj i obejrzyj planszę klatek"}


def require_assets(p, directory):
    blockers = [b for b in status(p, directory)["blockers"] if b["code"] in {"required_asset_missing", "asset_file_missing"}]
    if blockers: raise EditorError(blockers[0]["message"], "production_blocked")


def require_export(p, directory, quality):
    s = status(p, directory)
    require_assets(p, directory)
    if quality == "final" and p.get("production", {}).get("requireReview") and not s["finalReady"]:
        raise EditorError(s["blockers"][0]["message"] if s["blockers"] else "Najpierw zatwierdź przegląd aktualnej rewizji", "review_required")
    return s


def reflow(p, format):
    """Explicit layout pass: wide splits copy/visual; vertical stacks them. Review required."""
    from .commands import mutate
    if format not in FORMATS: raise EditorError("Nieobsługiwany format")
    mutate(p, "set_format", {"format": format}, {"selection": []})
    original_font_sizes = {e["id"]:e["style"]["fontSize"] for e in p["elements"]}
    w, h = FORMATS[format]; wide = w > h
    for e in p["elements"]:
        if e["type"] in {"audio", "shape", "video"}: continue
        if e["type"] == "text":
            x, y, ew, eh = (.07*w, .18*h, .52*w, .58*h) if wide else (.08*w, .12*h, .84*w, .28*h)
            size = min(w*.064, h*.10) if wide else w*.07
            peers = [t for t in p["elements"] if t["type"] == "text" and t["start"] < e["start"]+e["duration"] and t["start"]+t["duration"] > e["start"]]
            if original_font_sizes[e["id"]] < max(original_font_sizes[t["id"]] for t in peers)*.65:
                x, y, ew, eh, size = .08*w, (.74 if wide else .38)*h, (.5 if wide else .84)*w, .06*h, w*.03
        elif e["type"] == "caption":
            x, y, ew, eh, size = .08*w, .84*h, .84*w, .07*h, w*.028
        else:
            is_logo = e["assetId"] == p["brand"].get("logoAssetId")
            size = e["style"]["fontSize"]
            side = min(w,h)*.09 if is_logo else min(w,h)*.34 if wide else min(w*.58,h*.34)
            x, y, ew, eh = ((.86*w, .04*h, side, side) if is_logo else
                            (.62*w, (h-side)/2, side, side) if wide else ((w-side)/2, .44*h, side, side))
        for point in e.get("keyframes", []):
            if point["property"] == "x": point["value"] += x-e["x"]
            if point["property"] == "y": point["value"] += y-e["y"]
        e.update(x=x, y=y, width=ew, height=eh)
        e["style"]["fontSize"] = size
    return p
