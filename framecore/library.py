"""Audytowana biblioteka ikon Phosphor MIT; identyfikatory z zamkniętej listy."""
from pathlib import Path
from .model import EditorError, uid

ROOT = Path(__file__).parent / "static/icons"
ICONS = {"sparkle": "Iskra", "lightning": "Energia", "film-strip": "Film", "robot": "Agent AI",
         "music-notes": "Muzyka", "waveform": "Dźwięk", "palette": "Paleta", "shapes": "Kształty",
         "check": "Gotowe", "arrow-right": "Dalej", "images": "Obrazy", "scissors": "Montaż"}


def catalog():
    return [{"id": key, "name": value, "license": "MIT", "preview": f"/static/icons/{key}.svg"} for key, value in ICONS.items()]


def icon_asset(icon_id):
    if icon_id not in ICONS:
        raise EditorError("Nieznana ikona")
    aid = uid("asset")
    return {"id": aid, "name": ICONS[icon_id], "kind": "image", "file": f"assets/{aid}.svg", "mime": "image/svg+xml",
            "duration": None, "role": "icon", "license": "MIT",
            "provenance": {"source": "phosphor_builtin", "icon_id": icon_id, "version": "2.1.1"}}


def materialize(project, directory):
    for a in project["assets"]:
        if a.get("provenance", {}).get("source") == "phosphor_builtin":
            key = a["provenance"].get("icon_id")
            if key not in ICONS:
                raise EditorError("Nieznana ikona biblioteki")
            path = directory / a["file"]
            if not path.exists():
                # Only audited SVGs; uploaded SVG/code is never accepted.
                path.write_bytes((ROOT / (key + ".svg")).read_bytes())
