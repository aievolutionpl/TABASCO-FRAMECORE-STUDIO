"""Derived media analysis. Originals and project revisions are never modified."""
from __future__ import annotations

import array
import hashlib
import json
import math
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

from .model import EditorError
from .persistence import atomic_write, file_lock

VERSION = 1
ARTIFACTS = {'thumbnail.jpg', 'contact-sheet.jpg', 'proxy.mp4', 'waveform.json'}
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='framecore-media')
_SLOTS = threading.BoundedSemaphore(16)


def _run(args, timeout=120):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EditorError('Analiza wymaga FFmpeg/FFprobe; sprawdź instalację lub limit czasu.', 'media_analysis_failed') from exc
    if result.returncode:
        raise EditorError(result.stderr.decode('utf-8', errors='replace')[-1200:], 'media_analysis_failed')
    return result.stdout


def _digest(path):
    stat = path.stat()
    return _cached_digest(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=256)
def _cached_digest(filename, size, mtime, ctime):
    with Path(filename).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def waveform(pcm, sample_rate=8000):
    samples = array.array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    step = max(1, math.ceil(len(samples) / 1200))
    peaks = [round(max(abs(v) for v in samples[i:i+step]) / 32768, 5) for i in range(0, len(samples), step)]
    silence, start = [], None
    window = max(1, sample_rate // 10)
    for i in range(0, len(samples), window):
        chunk = samples[i:i+window]
        rms = math.sqrt(sum(v*v for v in chunk) / len(chunk)) / 32768
        if rms < .01 and start is None:
            start = i / sample_rate
        elif rms >= .01 and start is not None:
            if i/sample_rate-start >= .3:
                silence.append({'start': start, 'end': i/sample_rate})
            start = None
    duration = len(samples)/sample_rate
    if start is not None and duration-start >= .3:
        silence.append({'start': start, 'end': duration})
    return {'sample_rate': sample_rate, 'duration': duration, 'seconds_per_bin': step/sample_rate,
            'peaks': peaks, 'silence': silence, 'silence_threshold_db': -40, 'minimum_silence': .3}


class MediaEngine:
    def __init__(self, store):
        self.store = store

    def _source(self, pid, aid):
        project = self.store.read(pid)['project']
        asset = next((a for a in project['assets'] if a['id'] == aid), None)
        if not asset or asset['kind'] not in {'image', 'audio', 'video'}:
            raise EditorError('Nie znaleziono materiału do analizy', 'not_found')
        root = self.store.directory(pid).resolve()
        source = (root / asset['file']).resolve()
        if not source.is_relative_to(root / 'assets') or not source.is_file():
            raise EditorError('Nieprawidłowe źródło materiału', 'not_found')
        return asset, source, root

    def _location(self, pid, aid):
        asset, source, root = self._source(pid, aid)
        digest = _digest(source)
        key = hashlib.sha256(f'{VERSION}:{asset["kind"]}:{digest}'.encode()).hexdigest()
        directory = (root / '.media-cache' / key).resolve()
        if not directory.is_relative_to(root):
            raise EditorError('Cache musi znajdować się w projekcie', 'not_found')
        return asset, source, directory, digest

    @staticmethod
    def _read(directory):
        try:
            report = json.loads((directory / 'analysis.json').read_text(encoding='utf-8'))
            if not isinstance(report, dict) or report.get('status') not in {'queued', 'running', 'ready', 'failed'}:
                raise ValueError('Invalid analysis manifest')
            return report
        except (OSError, ValueError):
            return {'status': 'not_started', 'artifacts': {}}

    @staticmethod
    def _save(directory, report):
        directory.mkdir(parents=True, exist_ok=True)
        report['updated_at'] = time.time()
        atomic_write(directory / 'analysis.json', json.dumps(report, ensure_ascii=False))

    def status(self, pid, aid):
        _, _, directory, digest = self._location(pid, aid)
        report = self._read(directory)
        if report['status'] in {'queued', 'running'} and time.time()-report.get('updated_at', 0) > 900:
            report = {**report, 'status': 'failed', 'error': 'Analiza przerwana. Uruchom ją ponownie.'}
        if report['status'] == 'ready' and any(name not in ARTIFACTS or not (directory/name).resolve().is_relative_to(directory) or not (directory/name).is_file() or _digest(directory/name) != record.get('sha256') for name, record in report.get('artifacts', {}).items()):
            report = {**report, 'status': 'failed', 'error': 'Cache niekompletny. Uruchom analizę ponownie.', 'artifacts': {}}
        return {**report, 'asset_id': aid, 'source_sha256': digest,
                'urls': {name: f'/media/{pid}/{aid}/{name}' for name in report.get('artifacts', {})}}

    def start(self, pid, aid):
        asset, source, directory, digest = self._location(pid, aid)
        with file_lock(directory / '.lock'):
            report = self.status(pid, aid)
            if report['status'] in {'ready', 'queued', 'running'}:
                return report
            if not _SLOTS.acquire(blocking=False):
                raise EditorError('Kolejka analiz pełna. Spróbuj ponownie później.', 'media_busy')
            report = {'status': 'queued', 'version': VERSION, 'source_sha256': digest, 'artifacts': {}}
            try:
                self._save(directory, report)
                _POOL.submit(self._analyze, asset, source, directory, report)
            except Exception:
                _SLOTS.release()
                raise
        return self.status(pid, aid)

    def artifact(self, pid, aid, name):
        if name not in ARTIFACTS:
            raise EditorError('Nieznany plik analizy', 'not_found')
        _, _, directory, _ = self._location(pid, aid)
        report = self._read(directory)
        path = (directory / name).resolve()
        if report['status'] != 'ready' or name not in report.get('artifacts', {}) or not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise EditorError('Analiza nie jest gotowa', 'not_found')
        return path

    def _analyze(self, asset, source, directory, report):
        try:
            report['status'] = 'running'
            self._save(directory, report)
            if asset['kind'] == 'image':
                with Image.open(source) as original:
                    picture = ImageOps.exif_transpose(original).convert('RGB')
                    report['metadata'] = {'kind': 'image', 'width': picture.width, 'height': picture.height,
                                          'format': original.format, 'bytes': source.stat().st_size}
                    picture.thumbnail((640, 640))
                    picture.save(directory / 'thumbnail.jpg', quality=85)
            else:
                info = json.loads(_run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(source)], 30))
                duration = float(info['format']['duration'])
                if not math.isfinite(duration) or not 0 < duration <= 3600:
                    raise EditorError('Analiza obsługuje materiały do 60 minut.', 'media_limit')
                streams = info.get('streams', [])
                report['metadata'] = {'kind': asset['kind'], 'duration': duration, 'bytes': source.stat().st_size,
                    'streams': [{k: s[k] for k in ('codec_type', 'codec_name', 'width', 'height', 'sample_rate', 'channels', 'avg_frame_rate') if k in s} for s in streams]}
                if asset['kind'] == 'video':
                    frames = []
                    for i in range(6):
                        raw = _run(['ffmpeg', '-v', 'error', '-threads', '1', '-ss', str(duration*i/6), '-i', str(source), '-frames:v', '1', '-vf', 'scale=320:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-threads', '1', '-'])
                        import io
                        with Image.open(io.BytesIO(raw)) as frame:
                            frames.append(ImageOps.pad(frame.convert('RGB'), (320, 180), color='#121416'))
                    frames[0].save(directory / 'thumbnail.jpg', quality=85)
                    sheet = Image.new('RGB', (960, 360), '#121416')
                    for i, frame in enumerate(frames):
                        sheet.paste(frame, ((i%3)*320, (i//3)*180))
                    sheet.save(directory / 'contact-sheet.jpg', quality=85)
                    report['contact_sheet_times'] = [duration*i/6 for i in range(6)]
                    _run(['ffmpeg', '-y', '-v', 'error', '-threads', '1', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-vf', 'scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2', '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(directory/'proxy.mp4')], 300)
                if any(s.get('codec_type') == 'audio' for s in streams):
                    pcm = _run(['ffmpeg', '-v', 'error', '-i', str(source), '-map', '0:a:0', '-t', str(duration), '-ac', '1', '-ar', '8000', '-f', 's16le', '-'], 120)
                    atomic_write(directory/'waveform.json', json.dumps(waveform(pcm)))
            if _digest(source) != report['source_sha256']:
                raise EditorError('Materiał zmienił się w trakcie analizy', 'media_changed')
            report['artifacts'] = {name: {'sha256': _digest(directory/name), 'bytes': (directory/name).stat().st_size}
                                   for name in sorted(ARTIFACTS) if (directory/name).is_file()}
            report['status'] = 'ready'
            self._save(directory, report)
        except Exception as exc:
            report.update(status='failed', error=str(exc)[:1500], artifacts={})
            self._save(directory, report)
        finally:
            _SLOTS.release()
