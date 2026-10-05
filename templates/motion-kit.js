/* vstudio motion kit: deterministyczne pomocniki ruchu i napisów.
 * Wszystko jest czystą funkcją czasu t (zero timerów, zero losowości), więc działa z window.seek(t) i renderuje się tak samo za każdym razem.
 *   VS.bezier(x1,y1,x2,y2)            krzywa cubic-bezier jako funkcja p -> y (ease dla GSAP albo do ręcznego liczenia)
 *   VS.ease.out / inOut / soft / snap gotowe, mocne krzywe (silne wyhamowanie na końcu: ruch „ma ciężar”)
 *   VS.spring(k, c, m)                sprężyna jako ease: gsap.to(el, { y: 0, duration: VS.springDuration(170, 16), ease: VS.spring(170, 16) })
 *   VS.count / VS.type / VS.blink     licznik, pisanie znak po znaku, miganie kursora: wprost z t
 *   VS.captions.mount / draw / texts  napisy słowo po słowie (single | pop | karaoke) z danych z captions_build
 */
(function (g) {
  'use strict';
  var VS = g.VS = g.VS || {};

  VS.clamp = function (x, a, b) { return x < a ? a : x > b ? b : x; };
  VS.lerp = function (a, b, p) { return a + (b - a) * p; };

  /* cubic-bezier(x1, y1, x2, y2) jako funkcja easingu (Newton + bisekcja) */
  VS.bezier = function (x1, y1, x2, y2) {
    var cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    var cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    var X = function (s) { return ((ax * s + bx) * s + cx) * s; };
    var Y = function (s) { return ((ay * s + by) * s + cy) * s; };
    var dX = function (s) { return (3 * ax * s + 2 * bx) * s + cx; };
    return function (p) {
      if (p <= 0) return 0;
      if (p >= 1) return 1;
      var s = p, i, e, d;
      for (i = 0; i < 8; i++) {
        e = X(s) - p;
        if (Math.abs(e) < 1e-6) return Y(s);
        d = dX(s);
        if (Math.abs(d) < 1e-6) break;
        s -= e / d;
      }
      var lo = 0, hi = 1;
      s = p;
      for (i = 0; i < 24; i++) {
        e = X(s);
        if (Math.abs(e - p) < 1e-6) break;
        if (e < p) lo = s; else hi = s;
        s = (lo + hi) / 2;
      }
      return Y(s);
    };
  };
  VS.ease = { out: VS.bezier(0.23, 1, 0.32, 1), inOut: VS.bezier(0.77, 0, 0.175, 1), soft: VS.bezier(0.25, 0.46, 0.45, 0.94), snap: VS.bezier(0.16, 1, 0.3, 1) };

  /* sprężyna (tłumiony oscylator): sztywność k, tłumienie c, masa m. Zwraca ease; czas ustalenia daje VS.springDuration */
  function spr(k, c, m) {
    var w0 = Math.sqrt(k / m), z = c / (2 * Math.sqrt(k * m));
    return { w0: w0, z: z, sigma: z < 1 ? z * w0 : w0 * (z - Math.sqrt(Math.max(z * z - 1, 0))) };
  }
  VS.springDuration = function (k, c, m) {
    var s = spr(k || 170, c == null ? 18 : c, m || 1);
    return Math.min(Math.log(1000) / Math.max(s.sigma, 0.2), 4);          // obwiednia spada poniżej 0.1%
  };
  VS.spring = function (k, c, m) {
    k = k || 170; c = c == null ? 18 : c; m = m || 1;
    var s = spr(k, c, m), T = VS.springDuration(k, c, m), w0 = s.w0, z = s.z;
    return function (p) {
      if (p <= 0) return 0;
      if (p >= 1) return 1;
      var t = p * T;
      if (z < 1) {
        var wd = w0 * Math.sqrt(1 - z * z);
        return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
      }
      if (z === 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
      var r = w0 * Math.sqrt(z * z - 1), a = -z * w0 + r, b = -z * w0 - r;
      return 1 - (b * Math.exp(a * t) - a * Math.exp(b * t)) / (b - a);
    };
  };

  VS.count = function (t, t0, t1, from, to, ease) {
    var p = VS.clamp((t - t0) / Math.max(t1 - t0, 1e-6), 0, 1);
    return from + (to - from) * (ease || VS.ease.out)(p);
  };
  VS.type = function (s, t, t0, cps) { return s.slice(0, Math.floor(VS.clamp((t - t0) * (cps || 24), 0, s.length))); };
  VS.blink = function (t, hz) { return Math.floor(t * (hz || 2)) % 2 === 0; };

  /* napisy słowo po słowie. Dane: { lines: [{ t0, t1, words: [{ t0, t1, w, hl }] }] } (captions_build) */
  VS.captions = (function () {
    var C = { el: null, data: null, opts: {}, line: -2, spans: [] };
    var CSS = '.vs-cap{position:absolute;left:0;right:0;display:flex;flex-wrap:wrap;justify-content:center;gap:0 .26em;pointer-events:none;text-align:center;' +
      'font-family:var(--cap-font,"Archivo Black","Inter","Helvetica Neue",Arial,sans-serif);font-weight:900;font-size:var(--cap-size,9vw);line-height:1.5;' +
      'color:var(--cap-color,#fff);text-transform:var(--cap-case,uppercase);letter-spacing:-.01em;text-shadow:0 .035em .3em rgba(0,0,0,.45);padding:0 6%;box-sizing:border-box}' +
      '.vs-w{display:inline-block;transform-origin:50% 72%;will-change:transform}.vs-w.hl{color:var(--cap-hl,#FFD60A)}';
    var pop = VS.spring(300, 21);

    function mount(el, data, opts) {
      if (!document.getElementById('vs-cap-css')) {
        var st = document.createElement('style');
        st.id = 'vs-cap-css';
        st.textContent = CSS;
        document.head.appendChild(st);
      }
      C.el = el; C.data = data; C.opts = opts || {}; C.line = -2; C.spans = [];
      if (el.className.indexOf('vs-cap') < 0) el.className += ' vs-cap';
      el.textContent = '';
    }
    function lineAt(t) {
      var L = C.data.lines, lo = -1, i;
      for (i = 0; i < L.length; i++) { if (t >= L[i].t0) lo = i; else break; }
      if (lo < 0) return -1;
      var end = L[lo].t1 + (C.opts.hold == null ? 0.18 : C.opts.hold);
      if (L[lo + 1]) end = Math.min(end, L[lo + 1].t0);
      return t < end ? lo : -1;
    }
    function build(i) {
      if (C.line === i) return;
      C.line = i; C.spans = []; C.el.textContent = '';
      if (i < 0) return;
      C.data.lines[i].words.forEach(function (w) {
        var s = document.createElement('span');
        s.className = 'vs-w' + (w.hl ? ' hl' : '');
        s.textContent = w.w;
        C.el.appendChild(s);
        C.spans.push(s);
      });
    }
    function draw(t) {
      var i = lineAt(t);
      build(i);
      if (i < 0) return;
      var ws = C.data.lines[i].words, style = C.opts.style || 'pop', pd = C.opts.pop || 0.2, j, w, s, p, k;
      for (j = 0; j < ws.length; j++) {
        w = ws[j]; s = C.spans[j];
        p = VS.clamp((t - w.t0) / pd, 0, 1);
        if (style === 'karaoke') {
          var active = t >= w.t0 && (j === ws.length - 1 || t < ws[j + 1].t0);
          s.style.opacity = t >= w.t0 ? '1' : '0.45';
          k = active ? 1 + 0.08 * pop(p) : 1;
        } else {
          s.style.opacity = t >= w.t0 ? '1' : '0';
          k = t >= w.t0 ? 0.8 + 0.2 * pop(p) : 0.8;
        }
        s.style.transform = 'scale(' + k.toFixed(4) + ')';
      }
    }
    function texts(t) {
      if (!C.el || C.line < 0) return [];
      var ws = C.data.lines[C.line].words, vis = [], x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, j, r;
      for (j = 0; j < ws.length; j++) {
        if (t >= ws[j].t0 || C.opts.style === 'karaoke') {
          r = C.spans[j].getBoundingClientRect();
          vis.push(ws[j].w); x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
        }
      }
      return vis.length ? [{ id: 'cap', text: vis.join(' '), x0: x0, y0: y0, x1: x1, y1: y1, caption: true }] : [];
    }
    return { mount: mount, draw: draw, texts: texts };
  })();
})(window);
