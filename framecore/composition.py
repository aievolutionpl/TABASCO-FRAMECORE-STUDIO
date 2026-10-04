"""Compile validated data only; never execute agent-provided HTML/JS."""
import json
from pathlib import Path
from .model import validate

RUNTIME = Path(__file__).parent / "static" / "composition.js"


def compile_project(project, asset_prefix="assets/"):
    validate(project)
    data = json.dumps(project, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    prefix = json.dumps(asset_prefix).replace("<", "\\u003c")
    c = project["canvas"]
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Kompozycja FrameCore</title>'
            '<style>*{box-sizing:border-box}html,body{margin:0;overflow:hidden}body{background:#000}</style></head><body>'
            f'<main data-composition-id="framecore" data-width="{c["width"]}" data-height="{c["height"]}" data-duration="{project["duration"]}" style="position:relative;overflow:hidden"></main>'
            f'<script>window.FRAMECORE_PROJECT={data};window.FRAMECORE_ASSET_PREFIX={prefix};</script>'
            f'<script>{RUNTIME.read_text(encoding="utf-8")}</script></body></html>')
