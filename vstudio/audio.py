"""Sound: procedural SFX, cue-sheet mixing with ducking, -14 LUFS mastering, muxing.

Everything is synthesised or decoded locally: no sample packs, no licences to track.
A cue sheet (JSON) is the contract between the picture and the mix: hit times come from the same
timeline that drives the animation, so sound lands on the frame it belongs to.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .common import die, ffprobe, log, need, run

SR = 48000
SFX = ["click", "tick", "pop", "whoosh", "swoosh_up", "swoosh_down", "impact", "thud", "riser", "chime", "sparkle",
       "typewriter", "shutter", "glitch"]


# ------------------------------------------------------------------ synthesis helpers

def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _decay(n: int, tau: float, attack: float = 0.0005) -> np.ndarray:
    t = _t(n)
    a = np.clip(t / max(attack, 1e-5), 0, 1)
    return a * np.exp(-t / tau)


def _fft_filter(x: np.ndarray, lo: float | None, hi: float | None) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        m *= 1 / (1 + (np.maximum(f, 1e-3) / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def _sweep_bandpass(x: np.ndarray, f_start: np.ndarray, width_oct: float = 1.2) -> np.ndarray:
    """Time-varying band-pass by overlap-added FFT frames; f_start has the centre frequency per sample."""
    n, frame, hop = len(x), 2048, 512
    win = np.hanning(frame)
    out = np.zeros(n + frame)
    norm = np.zeros(n + frame)
    freqs = np.fft.rfftfreq(frame, 1 / SR)
    lf = np.log2(np.maximum(freqs, 1.0))
    for s in range(0, n, hop):
        seg = np.zeros(frame)
        chunk = x[s:s + frame]
        seg[:len(chunk)] = chunk
        fc = f_start[min(s + frame // 2, n - 1)]
        mask = np.exp(-0.5 * ((lf - np.log2(fc)) / (width_oct / 2.355)) ** 2)
        y = np.fft.irfft(np.fft.rfft(seg * win) * mask, frame)
        out[s:s + frame] += y * win
        norm[s:s + frame] += win ** 2
    return (out / np.maximum(norm, 1e-6))[:n]


def synth(name: str, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if name == "click":
        n = int(SR * 0.05)
        x = _fft_filter(rng.standard_normal(n), 1800, 9000) * _decay(n, 0.004, 0.0002)
        x += 0.5 * np.sin(2 * np.pi * 1400 * _t(n)) * _decay(n, 0.006, 0.0002)
    elif name == "tick":
        n = int(SR * 0.04)
        x = np.sin(2 * np.pi * 3200 * _t(n)) * _decay(n, 0.004, 0.0002)
    elif name == "pop":
        n = int(SR * 0.16)
        t = _t(n)
        f = 180 + 520 * np.exp(-t / 0.018)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _decay(n, 0.03, 0.0008) + 0.05 * rng.standard_normal(n) * _decay(n, 0.01)
    elif name in ("whoosh", "swoosh_up", "swoosh_down"):
        dur = {"whoosh": 0.8, "swoosh_up": 0.5, "swoosh_down": 0.5}[name]
        n = int(SR * dur)
        u = np.linspace(0, 1, n)
        if name == "whoosh":
            fc = 350 * (2600 / 350) ** np.sin(np.pi * u * 0.85) ; env = np.sin(np.pi * u) ** 2
        elif name == "swoosh_up":
            fc = 500 * (7000 / 500) ** u; env = (u ** 1.5) * (1 - u) ** 0.4
        else:
            fc = 7000 * (500 / 7000) ** u; env = ((1 - u) ** 1.5) * u ** 0.4
        x = _sweep_bandpass(rng.standard_normal(n), fc, 1.6) * env
    elif name in ("impact", "thud"):
        long = name == "impact"
        n = int(SR * (1.4 if long else 0.45))
        t = _t(n)
        f = 42 + 60 * np.exp(-t / 0.06)
        sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * _decay(n, 0.35 if long else 0.1, 0.002)
        body = _fft_filter(rng.standard_normal(n), None, 900) * _decay(n, 0.12 if long else 0.05, 0.001)
        x = sub + 0.8 * body
        if long:
            x += 0.4 * _fft_filter(rng.standard_normal(n), 2000, None) * _decay(n, 0.02, 0.0005)
    elif name == "riser":
        n = int(SR * 2.0)
        u = np.linspace(0, 1, n)
        fc = 200 * (9000 / 200) ** u
        x = _sweep_bandpass(rng.standard_normal(n), fc, 2.0) * (u ** 2)
        x += 0.25 * np.sin(2 * np.pi * np.cumsum(200 * (8 ** u)) / SR) * (u ** 2)
    elif name == "chime":
        n = int(SR * 1.2)
        t = _t(n)
        x = sum(a * np.sin(2 * np.pi * f * t) * _decay(n, tau, 0.002) for f, a, tau in
                ((880, 1.0, 0.5), (1320, 0.5, 0.35), (1760, 0.35, 0.25), (2640, 0.15, 0.15)))
    elif name == "sparkle":
        n = int(SR * 0.6)
        x = np.zeros(n)
        for k in range(7):
            s = int(SR * (0.02 + 0.07 * k + 0.02 * rng.random()))
            m = int(SR * 0.08)
            f = rng.uniform(2400, 5600)
            x[s:s + m] += np.sin(2 * np.pi * f * _t(m)) * _decay(m, 0.02, 0.0005) * (0.9 ** k)
    elif name == "typewriter":
        n = int(SR * 0.06)
        x = _fft_filter(rng.standard_normal(n), 900, 6000) * _decay(n, 0.007, 0.0003) + 0.4 * np.sin(2 * np.pi * (700 + 200 * rng.random()) * _t(n)) * _decay(n, 0.01, 0.0003)
    elif name == "shutter":
        n = int(SR * 0.22)
        x = np.zeros(n)
        for s, g in ((0, 1.0), (int(SR * 0.07), 0.7)):
            m = int(SR * 0.05)
            x[s:s + m] += g * _fft_filter(rng.standard_normal(m), 1500, 8000) * _decay(m, 0.008, 0.0003)
    elif name == "glitch":
        n = int(SR * 0.35)
        x = np.zeros(n)
        for k in range(6):
            s = int(SR * 0.05 * k); m = int(SR * 0.03)
            chunk = np.sign(rng.standard_normal(m)) * (rng.random() > 0.3)
            x[s:s + m] += np.round(chunk * 4) / 4 * 0.8
        x = _fft_filter(x, 300, 9000)
    else:
        die(f"unknown sfx '{name}'. Available: {', '.join(SFX)}")
    x = x.astype(np.float32)
    peak = float(np.max(np.abs(x))) or 1.0
    return x * (0.7 / peak)


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = x if x.ndim == 2 else x[:, None]
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


# ------------------------------------------------------------------ decode / master / mux

def decode(path: Path, sr: int = SR) -> np.ndarray:
    """Any audio or video file -> float32 stereo (n, 2) at 48 kHz."""
    need("ffmpeg")
    cp = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                        capture_output=True)
    if cp.returncode != 0 or not cp.stdout:
        die(f"could not decode audio from {path}: {cp.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(cp.stdout, dtype=np.float32).reshape(-1, 2).copy()


def measure_loudness(path: Path) -> dict | None:
    cp = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", cp.stderr, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    return {"integrated_lufs": float(j["input_i"]), "true_peak_db": float(j["input_tp"]), "lra": float(j["input_lra"])}


def master(stereo: np.ndarray, out: Path, lufs: float = -14.0, tp: float = -1.5, lra: float = 11.0) -> dict:
    """Two-pass linear loudnorm of an in-memory mix to `lufs`; writes wav/m4a/mp3 by extension."""
    raw = np.clip(stereo, -1, 1).astype("<f4").tobytes()
    base = ["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-"]
    p1 = subprocess.run(base + ["-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
                        input=raw, capture_output=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr.decode(errors="replace"), re.S)
    out.parent.mkdir(parents=True, exist_ok=True)
    codec = {".wav": ["-c:a", "pcm_s16le"], ".m4a": ["-c:a", "aac", "-b:a", "192k"], ".mp3": ["-c:a", "libmp3lame", "-b:a", "192k"]}.get(out.suffix.lower(), [])
    if not m or "-inf" in m.group(0):
        log("master: silent mix, skipping loudness normalisation")
        af = []
    else:
        j = json.loads(m.group(0))
        af = ["-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                     f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"]
    p2 = subprocess.run(base + af + ["-ar", str(SR), *codec, "-y", str(out)], input=raw, capture_output=True)
    if p2.returncode != 0:
        die("master failed: " + p2.stderr.decode(errors="replace")[-400:])
    return {"file": str(out), "loudness": measure_loudness(out)}


def mux(video: Path, audio: Path, out: Path) -> Path:
    need("ffmpeg")
    dur = ffprobe(video)["duration"]
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out])
    return out


# ------------------------------------------------------------------ cue-sheet mix

def _db(x: float) -> float:
    return 10 ** (x / 20)


def _place(buf: np.ndarray, sig: np.ndarray, t: float) -> None:
    i = int(round(t * SR))
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    if i < 0:
        sig = sig[-i:]; i = 0; j = min(len(buf), len(sig))
    buf[i:j] += sig[:j - i]


def _duck_gain(ctrl: np.ndarray, n: int, depth_db: float, attack: float = 0.015, release: float = 0.30) -> np.ndarray:
    """Music gain (linear) that dips by depth_db while `ctrl` (mono abs signal) is active, smoothed attack/release."""
    block = SR // 100
    nb = -(-n // block)
    pad = np.zeros(nb * block)
    pad[:len(ctrl)] = np.abs(ctrl)[:nb * block]
    env = pad.reshape(nb, block).max(axis=1)
    target = (env > 0.02).astype(np.float64)
    g = np.zeros(nb)
    a, r = np.exp(-0.01 / attack), np.exp(-0.01 / release)
    cur = 0.0
    for i in range(nb):
        coef = a if target[i] > cur else r
        cur = coef * cur + (1 - coef) * target[i]
        g[i] = cur
    gain_db = depth_db * g
    xs = np.linspace(0, nb - 1, n)
    return 10 ** (np.interp(xs, np.arange(nb), gain_db) / 20)


def mix_cues(cues: dict, base_dir: Path, out: Path, fps: float | None = None) -> dict:
    duration = float(cues["duration"])
    fps = float(cues.get("fps") or fps or 30)
    n = int(duration * SR)
    sfx_bus = np.zeros((n, 2), dtype=np.float64)
    voice_bus = np.zeros((n, 2), dtype=np.float64)
    duck_src = np.zeros(n, dtype=np.float64)
    placed = []
    for h in cues.get("hits", []):
        t = float(h["t"]) if "t" in h else float(h["frame"]) / fps
        if "sfx" in h:
            sig = synth(h["sfx"], int(h.get("seed", 1)))[:, None].repeat(2, axis=1)
        else:
            f = Path(h["file"]); f = f if f.is_absolute() else base_dir / f
            sig = decode(f)
        pan = float(h.get("pan", 0.0))
        sig = sig * np.array([1 - max(pan, 0), 1 + min(pan, 0)]) * _db(float(h.get("gain_db", -6)))
        _place(sfx_bus, sig, t)
        if h.get("duck", False):
            _place(duck_src[:, None], np.abs(sig[:, :1]), t)
        placed.append({"t": round(t, 3), "what": h.get("sfx") or h.get("file"), "gain_db": h.get("gain_db", -6)})
    for v in cues.get("voice", []):
        f = Path(v["file"]); f = f if f.is_absolute() else base_dir / f
        sig = decode(f) * _db(float(v.get("gain_db", 0)))
        t = float(v.get("t", 0))
        _place(voice_bus, sig, t)
        _place(duck_src[:, None], np.abs(sig[:, :1]), t)
        placed.append({"t": t, "what": str(v["file"]), "gain_db": v.get("gain_db", 0)})
    music_bus = np.zeros((n, 2), dtype=np.float64)
    m = cues.get("music")
    if m:
        f = Path(m["file"]); f = f if f.is_absolute() else base_dir / f
        sig = decode(f)
        start = float(m.get("start", 0))
        need_len = n - int(start * SR)
        if m.get("loop", True) and len(sig) < need_len:
            sig = np.tile(sig, (-(-need_len // len(sig)), 1))
        sig = sig[:max(need_len, 0)] * _db(float(m.get("gain_db", -18)))
        fi, fo = float(m.get("fade_in", 0.3)), float(m.get("fade_out", 1.0))
        if fi > 0:
            k = min(int(fi * SR), len(sig)); sig[:k] *= np.linspace(0, 1, k)[:, None]
        if fo > 0:
            k = min(int(fo * SR), len(sig)); sig[-k:] *= np.linspace(1, 0, k)[:, None]
        _place(music_bus, sig, start)
        depth = float(m.get("duck_db", -9))
        if depth < 0 and duck_src.any():
            music_bus *= _duck_gain(duck_src, n, depth)[:, None]
    mixed = (music_bus + sfx_bus + voice_bus).astype(np.float32)
    peak = float(np.max(np.abs(mixed))) or 1.0
    if peak > 0.98:
        mixed *= 0.98 / peak
    res = master(mixed, out, float(cues.get("lufs", -14)))
    res["placed"] = placed
    res["duration"] = duration
    return res
