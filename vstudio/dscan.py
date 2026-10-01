"""Analiza reżysera: czyste funkcje na danych z klatek i z DOM oraz skrypty wstrzykiwane do strony.

Nadzorca (`supervisor`) odpowiada na pytanie „czy film jest poprawny technicznie?”. Reżyser pyta o to, co widzi widz:
czy co kilka sekund dzieje się coś nowego, czy film nie wygląda tak samo od początku do końca, czy ruch ma przyspieszenia,
czy tekst NAPRAWDĘ jest widoczny i narysowany tym fontem, który wybrano.

Funkcje tu nie otwierają przeglądarki (przyjmują tablice), więc da się je testować syntetycznymi danymi.
"""
from __future__ import annotations

import math

# ------------------------------------------------------------------ miary na klatkach

THUMB_W = 64
CHG_THR = 28            # kanał RGB różniący się o więcej niż tyle (0-255) liczy się jako „piksel się zmienił”
GRID = 8                # kadr dzielimy na GRID x GRID bloków; blok „zmienił się”, gdy zmieniło się w nim >= BLOCK_MIN pikseli
BLOCK_MIN = 0.04
SHIFT_THR = 0.12        # tyle KADRU (w blokach) musi się wyraźnie zmienić względem chwili sprzed 0.5 s, żeby to była nowa sytuacja wizualna
HOOK_THR = 0.08         # tyle kadru musi się zmienić w pierwszych 1.5 s, żeby otwarcie miało hak
LOOK_TAU = 12.0         # odległość układu kolorów (0-100), od której dwa momenty uznajemy za dwa różne „looki” (kalibracja na 10 szablonach: jednolite filmy 1-2 looki, filmy ze zmianą tła i kart 3-4)


def thumb(im):
    """Miniatura RGB do porównań (PIL.Image -> ndarray uint8)."""
    import numpy as np
    from PIL import Image

    w = THUMB_W
    return np.asarray(im.convert("RGB").resize((w, max(8, round(w * im.height / im.width))), Image.BILINEAR), dtype=np.uint8)


def chg(a, b, thr: int = CHG_THR) -> float:
    """Ułamek kadru (0-1), który zmienił się wyraźnie między dwiema miniaturami."""
    import numpy as np

    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    return float((d > thr).mean())


def block_change(a, b, thr: int = CHG_THR) -> float:
    """Zasięg zmiany w kadrze (0-1): ułamek bloków siatki, w których zmieniło się wyraźnie >= BLOCK_MIN pikseli.

    Zmiana napisu zmienia tylko kreski liter (kilka % pikseli), ale zajmuje wiele bloków, więc liczy się jako zmiana „sytuacji”,
    a drobny licznik cyfr w jednym rogu nie.
    """
    import numpy as np

    d = (np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > thr)
    h, w = d.shape
    flags = [d[gy * h // GRID:(gy + 1) * h // GRID, gx * w // GRID:(gx + 1) * w // GRID].mean() >= BLOCK_MIN for gy in range(GRID) for gx in range(GRID)]
    return sum(flags) / len(flags)


def shift_series(thumbs: list, step: float, back: float = 0.5) -> list[float]:
    """D[i] = zasięg zmiany kadru względem klatki sprzed `back` s (dla początku: 0)."""
    k = max(1, round(back / step))
    return [block_change(thumbs[max(0, i - k)], thumbs[i]) if i else 0.0 for i in range(len(thumbs))]


def find_events(times: list[float], series: list[float], thr: float = SHIFT_THR, min_sep: float = 0.7, rise: float = 0.12, lookback_s: float = 0.4) -> list[float]:
    """Chwile nowych sytuacji wizualnych: narastające zbocze zmiany kadru powyżej progu `thr`.

    Zbocze to wzrost o >= `rise` względem najniższego poziomu z ostatnich `lookback_s` sekund. Dla twardego cięcia to chwila cięcia; wewnątrz ciągłej
    zmiany (np. przewijane okno) nowy bit z gwałtownym skokiem też jest zdarzeniem, a równy ruch nie rodzi go co próbkę. Okno jest w sekundach, nie
    w próbkach: przy rzadszym próbkowaniu (`quick`) trwały skok nie może wrócić jako drugie zdarzenie, zanim minie `min_sep`.
    t = 0 liczy się zawsze (pierwsza klatka jest „nowa” z definicji). Zdarzenia bliższe niż `min_sep` scalamy.
    """
    events = [0.0]
    for i in range(1, len(series)):
        if series[i] < thr:
            continue
        j = i
        while j > 0 and times[i] - times[j - 1] <= lookback_s + 1e-9:
            j -= 1
        base = min(series[j:i]) if j < i else series[i - 1]
        if series[i] - base >= rise and times[i] - events[-1] >= min_sep:
            events.append(round(times[i], 3))
    return events


def slow_gaps(events: list[float], dur: float, max_gap: float, tail_bonus: float = 1.0) -> list[tuple[float, float]]:
    """Przedziały bez nowej sytuacji dłuższe niż `max_gap` (końcowy może trwać o `tail_bonus` dłużej: to zwykle karta CTA)."""
    pts = sorted(set(events)) + [dur]
    out = []
    for a, b in zip(pts, pts[1:]):
        limit = max_gap + (tail_bonus if b >= dur - 1e-6 else 0.0)
        if b - a > limit + 1e-6:
            out.append((round(a, 2), round(b, 2)))
    return out


def hook_strength(thumbs: list, times: list[float], within: float = 1.5) -> float:
    """Największy zasięg zmiany kadru względem pierwszej klatki w pierwszych `within` s (0-1): czy otwarcie w ogóle coś robi."""
    best = 0.0
    for t, th in zip(times, thumbs):
        if t > within:
            break
        best = max(best, block_change(thumbs[0], th))
    return best


def color_layout(th) -> list[float]:
    """Układ kolorów 3x3 (27 liczb 0-100): gdzie jest jasno, ciemno i jakim kolorem. Opisuje „look” klatki."""
    import numpy as np

    h, w, _ = th.shape
    out = []
    for gy in range(3):
        for gx in range(3):
            cell = th[gy * h // 3:(gy + 1) * h // 3, gx * w // 3:(gx + 1) * w // 3].reshape(-1, 3).mean(axis=0)
            out.extend((cell / 255.0 * 100.0).tolist())
    return out


def look_distance(a: list[float], b: list[float]) -> float:
    """Różnica „looków”: pół średniej różnicy całego kadru, pół różnicy w najbardziej zmienionej komórce 3x3.

    Sama średnia nie widzi dużej karty na małym kawałku kadru (zmienia jedną komórkę z dziewięciu), a sama największa komórka rozbija
    jednolity film przy każdym przesunięciu elementu. Mieszanka łapie obie zmiany i jest odporna na drobny ruch.
    """
    n = len(a) // 3
    cells = [sum(abs(a[i * 3 + k] - b[i * 3 + k]) for k in range(3)) / 3 for i in range(n)]
    return 0.5 * (sum(cells) / n) + 0.5 * max(cells)


def look_clusters(thumbs: list, times: list[float], slice_s: float = 1.0, tau: float = LOOK_TAU) -> tuple[list[int], int, list[list[float]]]:
    """Dzieli film na plasterki po `slice_s` s i grupuje je w „looki” (wg układu kolorów). Zwraca etykiety plasterków, liczbę looków i ich centra."""
    import numpy as np

    if not thumbs:
        return [], 0, []
    dur = times[-1] + (times[1] - times[0] if len(times) > 1 else slice_s)
    n_slices = max(1, math.ceil(dur / slice_s - 1e-9))
    feats = []
    for s in range(n_slices):
        idx = [i for i, t in enumerate(times) if s * slice_s <= t < (s + 1) * slice_s] or [min(range(len(times)), key=lambda i: abs(times[i] - s * slice_s))]
        feats.append(np.mean([color_layout(thumbs[i]) for i in idx], axis=0).tolist())
    centers: list[list[float]] = []
    labels = []
    for f in feats:
        best = min(range(len(centers)), key=lambda c: look_distance(f, centers[c]), default=None)
        if best is not None and look_distance(f, centers[best]) <= tau:
            labels.append(best)
        else:
            centers.append(f)
            labels.append(len(centers) - 1)
    return labels, len(centers), centers


def required_looks(dur: float) -> int:
    """Ile różnych looków powinien mieć film: krótki 2, od 12 s 3, od 20 s 4."""
    return 1 if dur < 4.5 else 2 if dur < 12 else 3 if dur < 20 else 4


def flash_windows(lums: list[float], step: float, delta: float = 0.08, per_second: int = 6) -> list[tuple[float, float]]:
    """Okna 1 s, w których średnia jasność kadru skacze w górę i w dół >= `per_second` razy (3 błyski na sekundę to próg WCAG 2.3.1)."""
    signs = []
    for i in range(1, len(lums)):
        d = lums[i] - lums[i - 1]
        if abs(d) >= delta:
            signs.append((i, 1 if d > 0 else -1))
    flips = [(i, s) for k, (i, s) in enumerate(signs) if k == 0 or s != signs[k - 1][1]]
    out: list[tuple[float, float]] = []
    win = max(1, round(1.0 / step))
    for a in range(len(flips)):
        inside = [f for f in flips[a:] if f[0] - flips[a][0] <= win]
        if len(inside) >= per_second:
            t0, t1 = round(flips[a][0] * step, 2), round((inside[-1][0]) * step, 2)
            if not out or t0 > out[-1][1]:
                out.append((t0, t1))
    return out


# ------------------------------------------------------------------ ruch elementów (z DOM)

def _runs(flags: list[bool], gap: int = 1) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start = last = None
    for i, f in enumerate(flags):
        if f:
            if start is None:
                start = i
            last = i
        elif start is not None and i - last > gap:
            out.append((start, last))
            start = None
    if start is not None:
        out.append((start, last))
    return out


def motion_segments(rows_per_frame: list[list[list[float]]], fps: float, frame_diag: float, min_frames: int = 5) -> list[dict]:
    """Segmenty ruchu elementów. Wiersz: [idx, parent_idx, cx, cy, w, h, opacity]. Ruch dzieci liczony względem rodzica.

    Zwraca listę {el, kind: pos|size|alpha, f0, f1, t0, t1, amount, speeds, easing: linear|eased|None, enter}.
    """
    import numpy as np

    track: dict[int, dict] = {}
    for f, rows in enumerate(rows_per_frame):
        for idx, pidx, cx, cy, w, h, op in rows:
            tr = track.setdefault(int(idx), {"parent": int(pidx), "f": [], "c": [], "wh": [], "op": []})
            tr["f"].append(f)
            tr["c"].append((cx, cy))
            tr["wh"].append((w, h))
            tr["op"].append(op)
    out: list[dict] = []
    for idx, tr in track.items():
        if len(tr["f"]) < min_frames + 1:
            continue
        frames = np.array(tr["f"])
        c = np.array(tr["c"], dtype=float)
        wh = np.array(tr["wh"], dtype=float)
        op = np.array(tr["op"], dtype=float)
        par = track.get(tr["parent"])
        if par is not None:                             # ruch względem rodzica: dziecko w ruchomym kontenerze samo nie „rusza”
            pf = {f: k for k, f in enumerate(par["f"])}
            ref = np.array([par["c"][pf[f]] if f in pf else (0.0, 0.0) for f in frames], dtype=float)
            rel = c - ref
        else:
            rel = c
        speed_pos = np.r_[0.0, np.hypot(*np.diff(rel, axis=0).T)]
        speed_size = np.r_[0.0, np.abs(np.diff(wh[:, 0])) + np.abs(np.diff(wh[:, 1]))]
        speed_alpha = np.r_[0.0, np.abs(np.diff(op))]
        for kind, sp, thr in (("pos", speed_pos, 0.25), ("size", speed_size, 0.3), ("alpha", speed_alpha, 0.004)):
            for a, b in _runs((sp > thr).tolist()):
                if b - a + 1 < min_frames:
                    continue
                seg = sp[a:b + 1]
                if kind == "pos":
                    amount = float(seg.sum()) / frame_diag
                    if amount < 0.03:
                        continue
                elif kind == "size":
                    amount = float(abs(wh[b, 0] - wh[a, 0]) + abs(wh[b, 1] - wh[a, 1])) / max(float(wh[a, 0] + wh[a, 1]), 1.0)
                    if amount < 0.10:
                        continue
                else:
                    amount = float(abs(op[b] - op[a]))
                    if amount < 0.25:
                        continue
                core = seg[1:-1] if len(seg) > 4 else seg
                cv = float(core.std() / core.mean()) if core.mean() > 0 else 0.0
                easing = None
                if kind != "alpha":
                    easing = "linear" if (cv < 0.18 and len(seg) >= 8) else "eased"
                out.append({"el": idx, "parent": tr["parent"], "kind": kind, "f0": int(frames[a]), "f1": int(frames[b]), "t0": round(frames[a] / fps, 3),
                            "t1": round(frames[b] / fps, 3), "amount": round(amount, 3), "easing": easing,
                            "enter": kind == "alpha" and float(op[a]) < 0.2 and float(op[b]) > 0.6})
    return out


def easing_summary(segments: list[dict], max_len: float = 2.0) -> dict:
    """Ile ruchów ma przyspieszenia, a ile jest liniowych (tylko ruchy do `max_len` s: długi dryf liniowy jest normalny)."""
    cand = [s for s in segments if s["kind"] in ("pos", "size") and (s["t1"] - s["t0"]) <= max_len and s["easing"]]
    lin = [s for s in cand if s["easing"] == "linear"]
    return {"moves": len(cand), "linear": len(lin), "share": round(len(lin) / len(cand), 2) if cand else 0.0}


def stagger_groups(segments: list[dict], window_frames: int = 2, min_size: int = 6) -> list[dict]:
    """Grupy elementów, które pojawiają się w tej samej chwili bez opóźnienia (dziecko pojawiające się z rodzicem nie liczy się)."""
    ents = [s for s in segments if s["enter"]]
    ids = {s["el"] for s in ents}
    ents = [s for s in ents if s["parent"] not in ids]            # dziecko pojawia się razem z rodzicem: to jeden efekt
    groups = []
    used = set()
    for s in sorted(ents, key=lambda x: x["f0"]):
        if s["el"] in used:
            continue
        members = [m for m in ents if abs(m["f0"] - s["f0"]) <= window_frames and m["el"] not in used]
        if len(members) >= min_size:
            groups.append({"t": round(min(m["t0"] for m in members), 2), "count": len(members)})
            used.update(m["el"] for m in members)
    return groups


# ------------------------------------------------------------------ skrypty wstrzykiwane do strony

#: pozycje i krycie wszystkich widocznych elementów w bieżącej klatce: [idx, rodzic, cx, cy, w, h, krycie_efektywne]
MOTION_JS = """() => {
  const els = document.body.querySelectorAll('*'), idx = new Map(), eff = new Map(), out = [];
  const SKIP = new Set(['SCRIPT','STYLE','LINK','META','TITLE','NOSCRIPT','BR','DEFS','STOP','LINEARGRADIENT','RADIALGRADIENT','CLIPPATH','MASK','FILTER','SYMBOL','DESC','FETURBULENCE','FEGAUSSIANBLUR','FECOLORMATRIX']);
  for (let i = 0; i < els.length && i < 500; i++) {
    const el = els[i]; idx.set(el, i);
    if (SKIP.has(el.tagName.toUpperCase())) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none') continue;
    const own = cs.visibility === 'hidden' ? 0 : parseFloat(cs.opacity);
    const pe = el.parentElement, pop = pe && eff.has(pe) ? eff.get(pe) : 1;
    const op = (isNaN(own) ? 1 : own) * pop;
    eff.set(el, op);
    const r = el.getBoundingClientRect();
    if (r.width < 0.5 || r.height < 0.5) continue;
    let pi = -1;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) { if (idx.has(p)) { pi = idx.get(p); break; } }
    out.push([i, pi, +(r.left + r.width / 2).toFixed(2), +(r.top + r.height / 2).toFixed(2), +r.width.toFixed(2), +r.height.toFixed(2), +op.toFixed(3)]);
  }
  return out;
}"""

#: widoczne napisy w bieżącej klatce z geometrią, przycięciem przez overflow/kadr i fontem
TEXT_SCAN_JS = """() => {
  const W = innerWidth, H = innerHeight, out = [];
  const path = (el) => { const parts = []; for (let p = el, d = 0; p && p.nodeType === 1 && d < 7; p = p.parentElement, d++) {
      const sib = p.parentElement ? Array.prototype.indexOf.call(p.parentElement.children, p) : 0;
      parts.push(p.tagName.toLowerCase() + (p.id ? '#' + p.id : '') + ':' + sib); } return parts.reverse().join('>'); };
  const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
  const inter = (a, b) => ({ left: Math.max(a.left, b.left), top: Math.max(a.top, b.top), right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) });
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, txt = n.nodeValue.replace(/\\s+/g, ' ').trim();
    if (!txt) continue;
    const el = n.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'TITLE', 'NOSCRIPT'].includes(el.tagName.toUpperCase())) continue;
    let op = 1, hidden = false;
    for (let p = el; p && p.nodeType === 1; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.display === 'none' || cs.visibility === 'hidden') { hidden = true; break; }
      const o = parseFloat(cs.opacity); op *= isNaN(o) ? 1 : o;
    }
    if (hidden || op < 0.05) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    let vis = area(inter(r, { left: 0, top: 0, right: W, bottom: H })) / area(r);
    for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflow !== 'visible' || cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const pr = p.getBoundingClientRect();
        vis = Math.min(vis, area(inter(r, pr)) / area(r));
      }
    }
    const cs = getComputedStyle(el);
    out.push({ key: path(el) + '|' + txt.slice(0, 48), text: txt, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, op: op, vis: vis,
               family: cs.fontFamily, weight: cs.fontWeight, style: cs.fontStyle, size: parseFloat(cs.fontSize), transform: cs.textTransform,
               ellipsis: cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1 });
  }
  return out;
}"""

#: obrazy i grafiki widoczne w bieżącej klatce (do liczenia assetów i wykrywania niezaładowanych obrazów)
ASSET_SCAN_JS = """() => {
  const W = innerWidth, H = innerHeight, out = [];
  for (const el of document.body.querySelectorAll('img,svg,canvas,video,*')) {
    const tag = el.tagName.toLowerCase();
    const cs = getComputedStyle(el);
    const bg = cs.backgroundImage && cs.backgroundImage.includes('url(');
    if (!(tag === 'img' || tag === 'svg' || tag === 'canvas' || tag === 'video' || bg)) continue;
    if (tag === 'svg' && el.parentElement && el.parentElement.closest('svg')) continue;
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) continue;
    const src = tag === 'img' ? (el.currentSrc || el.src) : '';
    out.push({ tag: bg && !['img', 'svg', 'canvas', 'video'].includes(tag) ? 'bg' : tag, w: r.width, h: r.height,
               broken: tag === 'img' ? (el.complete && el.naturalWidth === 0) : false, src: src });
  }
  return out;
}"""

#: sprawdza, czy font z `family` faktycznie rysuje podane znaki (a nie zamiennik z listy lub z systemu). Metoda: wynik z fontem
#: pierwszym porównujemy z wynikiem z fontem nieistniejącym przy tych samych zapasowych; jeśli się nie różnią, pierwszy font nic nie wniósł.
GLYPH_JS = """async ({family, weight, style, chars}) => {
  const first = family.split(',')[0].trim();
  const bare = first.replace(/['"]/g, '');
  const generic = /^(serif|sans-serif|monospace|cursive|fantasy|system-ui|ui-[a-z-]+|-apple-system|emoji|math|fangsong|BlinkMacSystemFont)$/i.test(bare);
  const A = (tail) => `${style} ${weight} 48px ${first}, ${tail}`;
  const N = (tail) => `${style} ${weight} 48px "__vs_none__", ${tail}`;
  try { await Promise.all([document.fonts.load(`${style} ${weight} 48px ${first}`, chars)]); } catch (e) {}
  const c = document.createElement('canvas'); c.width = 96; c.height = 96;
  const g = c.getContext('2d', { willReadFrequently: true });
  const sig = (font, ch) => { g.clearRect(0, 0, 96, 96); g.font = font; g.textBaseline = 'alphabetic'; g.fillStyle = '#000'; g.fillText(ch, 10, 64);
    const d = g.getImageData(0, 0, 96, 96).data; let s = ''; for (let i = 3; i < d.length; i += 4) s += d[i] > 110 ? '1' : '0'; return s; };
  const contributes = (ch) => sig(A('serif'), ch) !== sig(N('serif'), ch) || sig(A('monospace'), ch) !== sig(N('monospace'), ch);
  const full = `${style} ${weight} 48px ${family}`;
  const nd = sig(full, '\\u{10FFFF}');
  const available = generic ? true : contributes('H');
  const missing = [], tofu = [];
  for (const ch of chars) {
    if (/\\s/.test(ch)) continue;
    if (sig(full, ch) === nd) { tofu.push(ch); continue; }
    if (!generic && available && !contributes(ch)) missing.push(ch);
  }
  return { first: bare, generic, available, missing, tofu };
}"""

#: zakłada na element atrybut, który robi jego tekst przezroczystym: różnica obrazu = realnie widoczny tusz
INK_STYLE_JS = """() => {
  if (document.getElementById('__vs_ink')) return;
  const s = document.createElement('style'); s.id = '__vs_ink';
  s.textContent = '[data-vs-hide], [data-vs-hide] * { color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important; -webkit-text-stroke-color: transparent !important; text-decoration-color: transparent !important; }';
  document.head.appendChild(s);
}"""

INK_HIDE_JS = """(key) => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const path = (el) => { const parts = []; for (let p = el, d = 0; p && p.nodeType === 1 && d < 7; p = p.parentElement, d++) {
      const sib = p.parentElement ? Array.prototype.indexOf.call(p.parentElement.children, p) : 0;
      parts.push(p.tagName.toLowerCase() + (p.id ? '#' + p.id : '') + ':' + sib); } return parts.reverse().join('>'); };
  while (walker.nextNode()) {
    const n = walker.currentNode, txt = n.nodeValue.replace(/\\s+/g, ' ').trim();
    if (txt && n.parentElement && (path(n.parentElement) + '|' + txt.slice(0, 48)) === key) { n.parentElement.setAttribute('data-vs-hide', '1'); return true; }
  }
  return false;
}"""

INK_SHOW_JS = """() => { document.querySelectorAll('[data-vs-hide]').forEach(e => e.removeAttribute('data-vs-hide')); }"""


# ------------------------------------------------------------------ geometria napisów

def norm_text(s: str) -> str:
    return "".join(s.lower().split())


def overlap_fraction(a: tuple, b: tuple) -> float:
    """Jaka część MNIEJSZEGO z dwóch prostokątów (x0, y0, x1, y1) jest przykryta przez drugi."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (ix * iy) / smaller if smaller > 0 else 0.0
