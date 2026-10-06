"""Lossless originals plus codec-portable browser copies for the desktop renderer.

Playwright Chromium does not guarantee proprietary MP4/AAC codecs on every OS.
The installed app uses FFmpeg to create VP9/Opus or PCM copies only for capture.
Project files, original assets, revision fingerprints and final audio remain intact.
"""
from copy import deepcopy
import hashlib
import mimetypes
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlparse
from .model import EditorError


def prepare(project, root, destination):
    if os.environ.get('FRAMECORE_PORTABLE_MEDIA') != '1': return {}
    root = Path(root).resolve()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copies = {}
    used = {e.get('assetId') for e in project['elements'] if e['type'] in {'video', 'audio'}}
    for asset in project['assets']:
        if asset['id'] not in used or asset['kind'] not in {'video', 'audio'}: continue
        source = (root / asset['file']).resolve()
        if not source.is_relative_to(root / 'assets') or not source.is_file():
            raise EditorError('Nie znaleziono oryginalnego materiału do renderowania')
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
        suffix = '.webm' if asset['kind'] == 'video' else '.wav'
        target = destination / ('browser-' + digest.hexdigest() + suffix)
        if not target.exists():
            # Each concurrent process uses a distinct temporary output; rename is atomic.
            import uuid
            temporary = target.with_name(target.stem + '-' + uuid.uuid4().hex + suffix)
            cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(source)]
            if asset['kind'] == 'video':
                cmd += ['-map', '0:v:0', '-map', '0:a?', '-c:v', 'libvpx-vp9', '-crf', '15', '-b:v', '0',
                        '-deadline', 'good', '-cpu-used', '4', '-c:a', 'libopus']
            else:
                cmd += ['-vn', '-c:a', 'pcm_s16le']
            try:
                from .desktop_runtime import process_options
                result = subprocess.run([*cmd, str(temporary)], capture_output=True, text=True, timeout=1800, **process_options())
                if result.returncode: raise EditorError('Nie udało się przygotować materiału: ' + result.stderr[-1200:])
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        copies[Path(asset['file']).name] = target
    return copies


def for_export(project, root):
    copies = prepare(project, root, Path(root) / 'assets')
    result = deepcopy(project)
    for asset in result['assets']:
        target = copies.get(Path(asset['file']).name)
        if target: asset['file'] = 'assets/' + target.name
    return result


def install_capture_routes(page, project, root):
    copies = prepare(project, root, Path(root) / '.desktop-media')
    if not copies: return
    def serve(route):
        file = copies.get(Path(unquote(urlparse(route.request.url).path)).name)
        if not file: return route.continue_()
        size = file.stat().st_size
        content_type = mimetypes.guess_type(file)[0] or 'application/octet-stream'
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', route.request.headers.get('range', ''))
        if match and size:
            first, last = match.groups()
            start = int(first) if first else max(0, size - int(last or 0))
            end = min(int(last), size - 1) if first and last else size - 1
            if start > end: return route.fulfill(status=416, headers={'Content-Range': f'bytes */{size}'}, body='')
            with file.open('rb') as stream:
                stream.seek(start); data = stream.read(end - start + 1)
            return route.fulfill(status=206, content_type=content_type, body=data,
                headers={'Accept-Ranges': 'bytes', 'Content-Range': f'bytes {start}-{end}/{size}'})
        route.fulfill(path=str(file), content_type=content_type)
    page.route('**/assets/' + project['id'] + '/*', serve)
