"""Validated media ingestion independent of HTTP and MCP transports."""
from pathlib import Path
from PIL import Image
from .model import EditorError, uid
from .render import probe

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


def import_asset(store, pid, data, filename, role="media", expected_revision=None, actor="human"):
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_TYPES or not data or len(data) > 100_000_000:
        raise EditorError("Dodaj PNG/JPG/WebP, MP4/WebM/MOV lub WAV/MP3/M4A do 100 MB")
    pdir = store.directory(pid)
    # Confirm the project exists before writing a file.
    state = store.read(pid)
    aid = uid("asset")
    file = f"assets/{aid}{suffix}"
    path = pdir / file
    path.write_bytes(data)
    try:
        kind = MEDIA_TYPES[suffix].split("/")[0]
        duration = None
        has_audio = False
        if kind == "image":
            with Image.open(path) as image:
                image.verify()
        else:
            info = probe(path)
            streams = info["streams"]
            has_audio = any(s["codec_type"] == "audio" for s in streams)
            if kind == "video" and not any(s["codec_type"] == "video" for s in streams) or kind == "audio" and not any(s["codec_type"] == "audio" for s in streams):
                raise EditorError("Zawartość pliku nie odpowiada typowi materiału")
            duration = float(info["format"]["duration"])
        a = {"id": aid, "name": Path(filename).name[:200], "kind": kind, "file": file, "mime": MEDIA_TYPES[suffix],
             "duration": duration, "hasAudio": has_audio, "role": role, "provenance": {"source": "user_upload"}, "license": "user_provided"}
        return store.execute(pid, "add_asset", {"asset": a}, expected_revision if expected_revision is not None else state["project"]["revision"], actor)
    except Exception:
        path.unlink(missing_ok=True)
        raise

