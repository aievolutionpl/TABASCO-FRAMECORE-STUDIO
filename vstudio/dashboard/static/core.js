/* vstudio dashboard: rdzeń (API, routing, powłoka, pulse, pomocniki). Każdy napis z zewnątrz przechodzi przez esc(). */
'use strict';
const V = window.V = { S: { projects: [], status: null, profile: null, pulse: null, lastEvent: 0, caps: null }, views: {}, cleanup: null, listeners: {} };
const TOKEN = document.querySelector('meta[name=token]').content;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
V.esc = esc; V.$ = $; V.$$ = $$;

/* ---------- ikony ---------- */
const P = {
  home: 'M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z', grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z', folder: 'M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  bot: 'M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2zM8.5 14h.01M15.5 14h.01', map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14',
  play: 'M7 4.5v15l13-7.5z', pause: 'M7 4h4v16H7zM13 4h4v16h-4z', prev: 'M18 5v14L8 12zM6 5v14', next: 'M6 5v14l10-7zM18 5v14', stepb: 'M15 6l-6 6 6 6', stepf: 'M9 6l6 6-6 6',
  check: 'M4 12.5 9.5 18 20 6.5', x: 'M6 6l12 12M18 6 6 18', refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7', copy: 'M9 9h10v10H9zM5 15V5h10', spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  film: 'M4 4h16v16H4zM4 9h16M4 15h16M9 4v16M15 4v16', term: 'M4 5h16v14H4zM8 10l3 2-3 2M13 14h4', plus: 'M12 5v14M5 12h14', alert: 'M12 4 2.5 20h19zM12 10v4M12 17h.01',
  loop: 'M17 2l3 3-3 3M20 5H8a4 4 0 0 0-4 4v1M7 22l-3-3 3-3M4 19h12a4 4 0 0 0 4-4v-1', code: 'M8 7 3 12l5 5M16 7l5 5-5 5', eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  shield: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z', list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01', download: 'M12 4v11M7 11l5 5 5-5M5 20h14', send: 'M22 2 11 13M22 2l-7 20-4-9-9-4z',
};
V.icon = (n, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n] || ''}"/></svg>`;

/* ---------- API ---------- */
V.api = async (name, args = {}) => {
  const r = await fetch('/api/call/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': TOKEN }, body: JSON.stringify(args) });
  const j = await r.json().catch(() => ({ error: 'Nieczytelna odpowiedź serwera' }));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};
V.get = async path => { const r = await fetch(path); const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j; };
V.busy = async (btn, fn) => {
  if (btn) { btn.classList.add('busy'); btn.disabled = true; }
  try { return await fn(); } catch (e) { V.toast(e.message, 'err'); throw e; } finally { if (btn) { btn.classList.remove('busy'); btn.disabled = false; } }
};
V.on = (ev, fn) => { (V.listeners[ev] ||= new Set()).add(fn); return () => V.listeners[ev].delete(fn); };
V.emit = (ev, data) => (V.listeners[ev] || []).forEach(fn => { try { fn(data); } catch (e) { console.error(e); } });

/* ---------- UI: toasty, modale, formaty ---------- */
V.toast = (msg, kind = '', ms = 4200, onClick = null) => {
  const t = document.createElement('div'); t.className = 'toast ' + kind;
  t.innerHTML = `<span>${kind === 'err' ? V.icon('alert') : kind === 'ok' ? V.icon('check') : V.icon('spark')}</span><div>${esc(msg)}</div>`;
  if (onClick) { t.style.cursor = 'pointer'; t.onclick = () => { onClick(); t.remove(); }; }
  $('#toasts').appendChild(t); setTimeout(() => t.remove(), ms);
};
V.modal = (html, { wide = false, onClose } = {}) => {
  const bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">${html}</div>`;
  const close = () => { bg.remove(); document.removeEventListener('keydown', esc_); onClose && onClose(); };
  const esc_ = e => { if (e.key === 'Escape') close(); };
  bg.addEventListener('mousedown', e => { if (e.target === bg) close(); });
  document.addEventListener('keydown', esc_);
  $('#modals').appendChild(bg);
  return { el: bg.firstElementChild, close };
};
V.fmtTime = t => { t = Math.max(0, t || 0); const m = Math.floor(t / 60), s = t - m * 60; return String(m).padStart(2, '0') + ':' + s.toFixed(2).padStart(5, '0'); };
V.ago = ts => { const s = Math.max(0, Date.now() / 1000 - ts); return s < 5 ? 'teraz' : s < 60 ? Math.round(s) + ' s temu' : s < 3600 ? Math.round(s / 60) + ' min temu' : s < 86400 ? Math.round(s / 3600) + ' h temu' : Math.round(s / 86400) + ' d temu'; };
V.clock = ts => new Date(ts * 1000).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
V.verdict = v => ({ pass: ['ok', 'W porządku'], needs_fixes: ['warn', 'Wymaga poprawek'], blocked: ['err', 'Zablokowany'] }[v] || ['', 'Nie sprawdzony']);
V.copy = async (text, btn) => { try { await navigator.clipboard.writeText(text); V.toast('Skopiowano', 'ok', 1600); } catch { V.toast('Nie udało się skopiować', 'err'); } };
V.pid = p => p.id || (p.brand + '/' + p.slug);
V.project = id => V.S.projects.find(p => p.id === id);
V.srcOf = (id, qs = '') => `/preview/${id}/index.html${qs}`;
V.fileUrl = (id, rel) => `/files/${id}/${rel}`;

/* ---------- miniodtwarzacz sceny (do kart i podglądu): scena sterowana przez seek ---------- */
/* Scena działa w piaskownicy (CSP sandbox bez allow-same-origin): ma nieprzezroczysty origin, więc nie sięgnie do tokenu ani API dashboardu.
   Sterujemy nią przez postMessage: info (długość, czy ma seek) i seek(t). Serwer wstrzykuje po stronie sceny odpowiedni „most”. */
V.bridge = frame => {
  let id = 0; const pending = new Map(); const h = {};
  const onMsg = e => {
    const m = e.data; if (!m || m.vstudio !== 'res' || e.source !== frame.contentWindow) return;
    const p = pending.get(m.id); if (p) { pending.delete(m.id); p(m); } else if (m.ok === false && h.error) h.error(m.error);
  };
  window.addEventListener('message', onMsg);
  const send = (op, extra = {}, wait = false) => new Promise(res => {
    const my = ++id; if (wait) pending.set(my, res);
    try { frame.contentWindow.postMessage({ vstudio: 'req', id: my, op, ...extra }, '*'); } catch (e) { pending.delete(my); return res({ ok: false, error: String(e) }); }
    if (!wait) res();
  });
  return {
    info: () => Promise.race([send('info', {}, true), new Promise(r => setTimeout(() => r({ ok: false, error: 'timeout' }), 9000))]),
    seek: t => { send('seek', { t }); },
    onError: fn => { h.error = fn; },
    dispose: () => window.removeEventListener('message', onMsg),
  };
};
V.thumb = (host, url, w, h, posterT = 0) => {
  host.classList.add('thumb'); host.style.aspectRatio = `${w} / ${h}`;
  host.innerHTML = '<div class="ph">ładowanie podglądu…</div>';
  let frame = null, br = null, ready = false, raf = 0, dur = 0;
  const fit = () => { if (frame) frame.style.transform = `scale(${host.clientWidth / w})`; };
  const load = () => {
    frame = document.createElement('iframe'); frame.width = w; frame.height = h; frame.setAttribute('loading', 'lazy'); frame.setAttribute('tabindex', '-1'); frame.setAttribute('sandbox', 'allow-scripts');
    br = V.bridge(frame);
    frame.onload = async () => {
      const inf = await br.info();
      if (!inf.ok || !inf.hasSeek) { const ph = host.querySelector('.ph'); if (ph) ph.textContent = 'scena bez window.seek'; return; }
      dur = inf.dur || 1; ready = true; br.seek(posterT); host.querySelector('.ph')?.remove(); fit();
    };
    frame.src = url; host.appendChild(frame); fit();
  };
  const io = new IntersectionObserver(es => { if (es[0].isIntersecting && !frame) { load(); io.disconnect(); } }, { rootMargin: '120px' }); io.observe(host);
  new ResizeObserver(fit).observe(host);
  const play = () => { if (!ready) return; const t0 = performance.now(); cancelAnimationFrame(raf); const loop = now => { br.seek(((now - t0) / 1000) % dur); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); };
  const stop = () => { cancelAnimationFrame(raf); if (ready) br.seek(posterT); };
  host.addEventListener('mouseenter', play); host.addEventListener('mouseleave', stop);
  host._dispose = () => { cancelAnimationFrame(raf); io.disconnect(); if (br) br.dispose(); };
};

/* ---------- powłoka: nawigacja, okruszki, pulse ---------- */
V.renderNav = () => {
  const r = V.route_; const cur = r ? r.view : '';
  const item = (hash, icon, label, on, extra = '') => `<a href="${hash}" class="${on ? 'on' : ''}">${V.icon(icon)}<span class="pn">${label}</span>${extra}</a>`;
  const tasks = V.S.pulse ? V.S.pulse.open_tasks : 0;
  const dots = p => { const c = p.check; return `<span class="dot ${c ? (c.verdict === 'pass' ? 'ok' : c.verdict === 'blocked' ? 'err' : 'warn') : ''}" style="animation:none"></span>`; };
  $('#nav').innerHTML = `
    ${item('#/', 'home', 'Start', cur === 'home')}
    ${item('#/library', 'grid', 'Biblioteka szablonów', cur === 'library')}
    ${item('#/agent', 'bot', 'Agent', cur === 'agent', tasks ? `<span class="badge">${tasks}</span>` : '')}
    ${item('#/map', 'map', 'Mapa możliwości', cur === 'map')}
    <h6>Projekty</h6>
    ${V.S.projects.map(p => `<a href="#/p/${esc(p.id)}" class="${r && r.view === 'project' && r.params[0] === p.id ? 'on' : ''}">${dots(p)}<span class="pn">${esc(p.slug)}</span><span class="dim" style="font-size:11px">${p.check ? p.check.score : ''}</span></a>`).join('') || '<div class="dim" style="padding:6px 12px;font-size:13px">Jeszcze nic. Zacznij od szablonu.</div>'}
    <a href="#/library" style="margin-top:6px">${V.icon('plus')}<span class="pn">Nowy film</span></a>
    <h6>Start</h6>
    ${item('#/onboarding', 'spark', 'Onboarding', cur === 'onboarding')}`;
};
V.crumbs = parts => { $('#crumbs').innerHTML = parts.map((p, i) => i === parts.length - 1 ? `<b>${esc(p)}</b>` : `<span>${esc(p)}</span><span class="dim">/</span>`).join(''); };
V.setAgentPill = () => {
  const a = V.S.pulse && V.S.pulse.agent, pill = $('#agentPill'); if (!pill) return;
  const d = pill.querySelector('.dot'), t = pill.querySelector('span:last-child');
  if (a && a.connected) { d.className = 'dot ok'; t.textContent = `agent: ${a.last_call} · ${Math.round(a.seconds_ago)} s`; }
  else { d.className = 'dot'; t.textContent = a && a.last_seen ? `agent: bezczynny (${V.ago(a.last_seen)})` : 'agent: niepodłączony'; }
};
V.setJobPill = () => {
  const jobs = (V.S.pulse && V.S.pulse.jobs || []).filter(j => j.status === 'running'), pill = $('#jobPill');
  pill.hidden = !jobs.length; if (jobs.length) { const j = jobs[0]; pill.innerHTML = `<span class="dot warn"></span><span>${esc(j.kind)} ${Math.round(j.progress * 100)}%</span>`; pill.onclick = () => V.go(`#/p/${j.project}/render`); }
};
V.jobStates = {}; V.bootAt = Date.now() / 1000;
V.notifyJobs = jobs => {                      // powiadomienie o zmianie running -> koniec (także gdy job skończył się między dwoma odczytami)
  for (const j of jobs) {
    const was = V.jobStates[j.id]; V.jobStates[j.id] = j.status;
    if (j.status === 'running') continue;
    const fresh = was === 'running' || (was === undefined && j.finished && j.finished > V.bootAt);
    if (!fresh) continue;
    const names = { render: 'Render', sound: 'Dźwięk', deliver: 'Wydanie' }, nm = names[j.kind] || j.kind, slug = (j.project || '').split('/').pop();
    const ok = j.status === 'done';
    V.toast(`${nm} ${slug}: ${ok ? 'gotowe' : j.status === 'cancelled' ? 'anulowano' : 'nie udało się'}${ok ? ' (kliknij, żeby zobaczyć)' : ''}`, ok ? 'ok' : j.status === 'cancelled' ? '' : 'err', 7000, () => V.go(`#/p/${j.project}/render`));
    V.emit('job-finished', j);
  }
};
V.pulse = async () => {
  try {
    const p = await V.get('/api/pulse?since=' + V.S.lastEvent); const prev = V.S.pulse; V.S.pulse = p;
    if (p.events.length) V.S.lastEvent = p.events[p.events.length - 1].id;
    V.setAgentPill(); V.setJobPill(); V.notifyJobs(p.jobs);
    let changed = false;
    for (const [id, m] of Object.entries(p.projects)) { const o = prev && prev.projects[id]; if (!o || o.updated !== m.updated || o.round !== m.round || o.verdict !== m.verdict) changed = true; }
    if (prev && Object.keys(prev.projects).length !== Object.keys(p.projects).length) changed = true;
    if (changed) { await V.refreshProjects(); }
    V.emit('pulse', { p, prev });
  } catch (e) { /* serwer chwilowo niedostępny */ }
};
V.refreshProjects = async () => { try { V.S.projects = (await V.api('projects_list')).projects; V.renderNav(); V.emit('projects', V.S.projects); } catch (e) { /* ignoruj */ } };
V.refreshStatus = async () => { V.S.status = await V.api('studio_status'); return V.S.status; };

/* ---------- router ---------- */
V.go = hash => { if (location.hash === hash) V.route(); else location.hash = hash; };
V.route = async () => {
  const hash = location.hash.replace(/^#\/?/, ''); const parts = hash.split('/').filter(Boolean);
  let view = parts[0] || 'home', params = parts.slice(1);
  if (view === 'p') { view = 'project'; params = [parts[1] + '/' + parts[2], parts[3] || '']; }
  if (!V.views[view]) { view = 'home'; params = []; }
  if (V.cleanup) { try { V.cleanup(); } catch (e) { console.error(e); } V.cleanup = null; }
  const my = V.seq = (V.seq || 0) + 1;
  V.route_ = { view, params }; V.renderNav();
  // każda trasa dostaje własny kontener: spóźnione (async) zapisy starego widoku trafiają do odłączonego DOM i nic nie psują
  const outer = $('#view'); outer.className = 'view' + (view === 'project' ? ' flush' : ''); outer.scrollTop = 0;
  const host = document.createElement('div'); host.className = 'vbox'; outer.replaceChildren(host);
  let cleanup = null;
  try { cleanup = (await V.views[view](host, params)) || null; } catch (e) { console.error(e); V.toast('Widok nie zadziałał: ' + e.message, 'err', 7000); }
  if (V.seq !== my) { if (cleanup) try { cleanup(); } catch (e) { console.error(e); } return; }   // w trakcie ładowania przeszliśmy gdzie indziej
  V.cleanup = cleanup;
};
V.boot = async () => {
  window.addEventListener('hashchange', V.route);
  try { await Promise.all([V.refreshStatus(), V.refreshProjects(), V.api('profile_get').then(p => (V.S.profile = p))]); } catch (e) { V.toast('Nie udało się wczytać stanu: ' + e.message, 'err', 8000); }
  await V.pulse();
  if (V.S.status && !V.S.status.onboarded && !V.S.projects.length && !sessionStorage.getItem('onboardSkipped') && !location.hash) { sessionStorage.setItem('onboardSkipped', '1'); location.hash = '#/onboarding'; }
  else await V.route();
  setInterval(V.pulse, 1200);
};
