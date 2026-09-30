/* Widok warsztatu projektu: podgląd sterowany seek, transport, oś czasu i panel (nadzór, źródło, render, potok, agent). */
'use strict';
(() => {
  const { esc, $, $$ } = V;
  const TABS = [['nadzor', 'Nadzór', 'shield'], ['zrodlo', 'Źródło', 'code'], ['render', 'Render', 'film'], ['potok', 'Potok', 'list'], ['agent', 'Agent', 'bot']];
  const GATES = [['brief', 'Brief'], ['reference_spec', 'Studium referencji'], ['visual_rules', 'Zasady wizualne'], ['stills', 'Klatki kontrolne'], ['draft', 'Render roboczy'], ['sound', 'Dźwięk'], ['critic', 'Krytyk (≥ 8/10)'], ['final', 'Render finalny']];
  const EVCOL = { whoosh: '#6cb6ff', hit: '#ff6b81', impact: '#ff6b81', pop: '#ffc857', click: '#ffc857', chime: '#3ddc97', tick: '#8c94a9', reveal: '#c77dff', type: '#5ee1ff' };

  V.views.project = async (host, [pid, tabArg]) => {
    if (!V.project(pid)) await V.refreshProjects();
    const proj = V.project(pid);
    if (!proj) { V.crumbs(['Projekty', pid]); host.innerHTML = `<div class="page"><div class="card empty"><div class="glyph">🔎</div>Nie ma projektu <b>${esc(pid)}</b>.<div style="margin-top:12px"><a class="btn" href="#/">Wróć do startu</a></div></div></div>`; return; }
    V.crumbs(['Projekty', proj.slug]);
    let alive = true, tab = TABS.some(t => t[0] === tabArg) ? tabArg : 'nadzor';
    const [W, H] = proj.size, DUR = proj.duration, FPS = proj.fps;
    const S = { report: null, history: [], detail: null, tl: null, scene: null, sceneDirty: false, jobs: [], selected: null, mtime: proj.updated };
    const Pl = { t: 0, playing: false, loop: true, rate: 1, api: null, raf: 0, last: 0 };

    host.innerHTML = `<div class="ws">
      <section class="stage-col">
        <div class="ws-head"><h2>${esc(proj.slug)}</h2><span class="chip" title="${esc(proj.brand)}">${W}×${H} · ${FPS} fps · ${DUR} s</span><div class="spacer"></div>
          <label class="pill" id="autoPill" title="Gdy scena zmieni się na dysku (agent, edytor), serwer sam robi szybki nadzór"><input type="checkbox" id="autoSup" style="accent-color:#7c8cff"> auto-nadzór</label>
          <button class="btn sm" id="bCheck">${V.icon('shield')} Sprawdź</button><button class="btn sm primary" id="bDraft" title="Render roboczy (połowa rozdzielczości)">${V.icon('film')} Render</button></div>
        <div class="stage-wrap" id="stageWrap"><div class="device" id="device"><iframe id="frame" title="Podgląd sceny"></iframe><div class="ovl" id="ovl"></div><div class="veil" id="veil">Ładowanie sceny…</div></div></div>
        <div class="transport">
          <button class="btn icon sm ghost" id="tStart" title="Początek (Home)">${V.icon('prev')}</button>
          <button class="btn icon sm ghost" id="tBack" title="Klatka wstecz (←)">${V.icon('stepb')}</button>
          <button class="btn icon" id="tPlay" title="Odtwarzaj / pauza (spacja)">${V.icon('play')}</button>
          <button class="btn icon sm ghost" id="tFwd" title="Klatka naprzód (→)">${V.icon('stepf')}</button>
          <button class="btn icon sm ghost" id="tLoop" title="Pętla (L)">${V.icon('loop')}</button>
          <div class="time" id="tTime">00:00.00</div><span class="dim mono" id="tFrame"></span>
          <div class="spacer"></div>
          <div class="seg" id="tRate"><button data-r=".25">¼×</button><button data-r=".5">½×</button><button data-r="1" class="on">1×</button></div>
        </div>
        <div class="tl" id="tl"></div>
      </section>
      <aside class="panel"><div class="tabs" id="tabs">${TABS.map(([k, l]) => `<button data-tab="${k}" class="${k === tab ? 'on' : ''}">${l}<span class="n" data-n="${k}" hidden></span></button>`).join('')}</div><div class="pbody" id="pbody"></div></aside>
    </div>`;

    /* ---------- dopasowanie urządzenia ---------- */
    const wrap = $('#stageWrap', host), dev = $('#device', host), frame = $('#frame', host), veil = $('#veil', host);
    const fit = () => { const aw = wrap.clientWidth - 40, ah = wrap.clientHeight - 14, k = Math.max(0.05, Math.min(aw / W, ah / H)); dev.style.width = Math.round(W * k) + 'px'; dev.style.height = Math.round(H * k) + 'px'; };
    const ro = new ResizeObserver(fit); ro.observe(wrap); fit();

    /* ---------- odtwarzacz ---------- */
    const dur = () => Pl.api && Pl.api.dur || DUR;
    const seek = (t, { keepBox = false } = {}) => {
      const d = dur(); t = Pl.loop || !Pl.playing ? ((t % d) + d) % d : Math.min(Math.max(t, 0), d); if (t > d - 1e-6 && !Pl.loop) t = d - 1e-3;
      Pl.t = t; if (Pl.api) { try { Pl.api.seek(t); } catch (e) { veilShow('Scena zgłosiła błąd w seek(): ' + e.message); } }
      $('#tTime', host).textContent = V.fmtTime(t) + ' / ' + V.fmtTime(d); $('#tFrame', host).textContent = 'kl. ' + Math.round(t * FPS);
      const hd = $('#tl .head', host); if (hd) hd.style.left = (100 * t / d) + '%';
      if (!keepBox) { $('#ovl', host).innerHTML = ''; }
    };
    const setPlay = on => {
      Pl.playing = on; $('#tPlay', host).innerHTML = V.icon(on ? 'pause' : 'play'); cancelAnimationFrame(Pl.raf);
      if (on) { Pl.last = performance.now(); const loop = now => { const dt = (now - Pl.last) / 1000; Pl.last = now; seek(Pl.t + dt * Pl.rate); Pl.raf = requestAnimationFrame(loop); }; Pl.raf = requestAnimationFrame(loop); }
    };
    const veilShow = msg => { veil.hidden = false; veil.innerHTML = esc(msg); };
    const loadFrame = () => {
      const keep = Pl.t; veil.hidden = false; veil.textContent = 'Ładowanie sceny…'; Pl.api = null;
      frame.onload = async () => {
        try { await Promise.race([frame.contentWindow.__ready, new Promise(r => setTimeout(r, 6000))]); } catch (e) { /* biblioteka z CDN mogła nie wstać */ }
        Pl.api = V.sceneApi(frame.contentWindow);
        if (!Pl.api) { veilShow('Scena nie wystawia window.seek(t) albo nie załadowała się (np. zablokowany CDN). Uruchom nadzór: pokaże przyczynę i poprawkę.'); return; }
        veil.hidden = true; seek(keep);
      };
      frame.src = V.srcOf(pid, '?r=' + Date.now());
    };
    loadFrame();

    $('#tPlay', host).onclick = () => setPlay(!Pl.playing);
    $('#tStart', host).onclick = () => { setPlay(false); seek(0); };
    $('#tBack', host).onclick = () => { setPlay(false); seek(Pl.t - 1 / FPS); };
    $('#tFwd', host).onclick = () => { setPlay(false); seek(Pl.t + 1 / FPS); };
    $('#tLoop', host).onclick = e => { Pl.loop = !Pl.loop; e.currentTarget.style.color = Pl.loop ? 'var(--a1)' : ''; };
    $('#tLoop', host).style.color = 'var(--a1)';
    $$('#tRate button', host).forEach(b => b.onclick = () => { Pl.rate = +b.dataset.r; $$('#tRate button', host).forEach(x => x.classList.toggle('on', x === b)); });
    const onKey = e => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || e.metaKey || e.ctrlKey) return;
      if (e.code === 'Space') { e.preventDefault(); setPlay(!Pl.playing); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); setPlay(false); seek(Pl.t - (e.shiftKey ? 1 : 1 / FPS)); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); setPlay(false); seek(Pl.t + (e.shiftKey ? 1 : 1 / FPS)); }
      else if (e.key === 'Home') seek(0); else if (e.key.toLowerCase() === 'l') $('#tLoop', host).click();
    };
    document.addEventListener('keydown', onKey);

    /* ---------- oś czasu ---------- */
    const renderTimeline = () => {
      const d = DUR, T = $('#tl', host), tl = S.tl, rep = S.report;
      const ticks = []; const step = d > 30 ? 5 : d > 12 ? 2 : 1; for (let s = 0; s <= d + 1e-6; s += step) ticks.push(s);
      let rows = []; const texts = tl ? tl.texts : [];
      texts.forEach(tx => { let r = rows.findIndex(end => end <= tx.from); if (r < 0) { r = rows.length; rows.push(0); } rows[r] = tx.to + 0.05; tx._r = r; });
      const nrows = Math.max(1, rows.length);
      const fnd = (rep ? rep.findings : []).filter(f => f.t != null && f.t <= d + 0.01);
      T.innerHTML = `<div class="tlin"><div class="ruler">${ticks.map(s => `<span style="left:${100 * s / d}%">${s}s</span>`).join('')}</div>
        <div class="lane"><label>dźwięk</label>${tl ? tl.events.map(e => `<i class="ev" style="left:${100 * e.t / d}%;background:${EVCOL[e.type] || '#ffc857'}" title="${esc(e.type)} @ ${e.t.toFixed(2)} s"></i>`).join('') : ''}</div>
        <div class="lane tall" style="height:${nrows * 22 + 2}px"><label>tekst</label>${tl ? texts.map(tx => `<div class="bar" style="left:${100 * tx.from / d}%;width:${Math.max(0.6, 100 * (tx.to - tx.from) / d)}%;top:${tx._r * 22 + 3}px" title="${esc(tx.text)} (${tx.from}–${tx.to} s)">${esc(tx.text)}</div>`).join('') : '<div class="skel" style="position:absolute;inset:3px 40px"></div>'}</div>
        <div class="lane"><label>nadzór</label>${fnd.map(f => `<i class="fd ${f.severity}" style="left:${100 * f.t / d}%" title="${esc(f.code)} @ ${f.t} s"></i>`).join('')}</div>
        <div class="head" style="left:${100 * Pl.t / d}%"></div></div>`;
      const at = ev => { const r = $('.tlin', T).getBoundingClientRect(); return Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1) * d; };
      let drag = false; T.onpointerdown = e => { drag = true; T.setPointerCapture(e.pointerId); setPlay(false); seek(at(e)); };
      T.onpointermove = e => { if (drag) seek(at(e)); }; T.onpointerup = () => { drag = false; };
    };
    renderTimeline();
    V.api('timeline_get', { project: pid }).then(r => { if (alive) { S.tl = r; renderTimeline(); } }).catch(() => { if (alive) { S.tl = { events: [], texts: [] }; renderTimeline(); } });

    /* ---------- nadzór ---------- */
    const ring = (score, kind) => { const c = 2 * Math.PI * 34, col = { ok: 'var(--ok)', warn: 'var(--warn)', err: 'var(--err)', '': 'var(--dim)' }[kind]; return `<div class="ring"><svg width="84" height="84" viewBox="0 0 84 84"><circle cx="42" cy="42" r="34" fill="none" stroke="var(--panel-3)" stroke-width="8"/><circle cx="42" cy="42" r="34" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${c * score / 100} ${c}"/></svg><b>${score ?? '–'}</b></div>`; };
    const assetUrl = (rep, name) => V.fileUrl(pid, `supervisor/${rep.assets.dir}/${name}`);
    const askAgent = async (prompt, btn) => V.busy(btn, async () => { const r = await V.api('task_create', { prompt, project: pid }); V.toast(`Zadanie ${r.task.id} dla agenta dodane`, 'ok'); V.refreshStatus(); });
    const findingPrompt = f => `Projekt ${pid}: napraw znalezisko ${f.code}${f.t != null ? ` przy t=${f.t}s` : ''}. ${f.detail} Wskazówka: ${f.fix}`;
    const renderCheck = () => {
      const rep = S.report, body = $('#pbody', host); if (tab !== 'nadzor') return;
      const [kind, label] = V.verdict(rep && rep.verdict);
      const hist = S.history.slice(-14);
      body.innerHTML = `<div class="row" style="gap:16px">${ring(rep ? rep.score : null, kind)}<div style="flex:1"><div class="chip ${kind}" style="margin-bottom:6px">${esc(label)}</div>
          <div class="muted" style="font-size:13px">${rep ? `${rep.counts.error} błędów · ${rep.counts.warn} ostrzeżeń · ${rep.counts.info} info<br>runda ${rep.round} · ${esc(rep.depth)} · ${rep.metrics.elapsed_s} s` : 'Film jeszcze nie był sprawdzany. Nadzorca obejrzy klatki, pętlę, determinizm i czytelność.'}</div></div></div>
        <div class="row" style="margin:14px 0 4px"><select id="depth" style="width:auto"><option value="quick">szybki (0,25 s)</option><option value="standard" selected>standardowy (0,1 s)</option><option value="deep">dokładny (co klatkę)</option></select><button class="btn primary" id="runCheck" style="flex:1">${V.icon('shield')} Uruchom nadzór</button></div>
        ${rep && rep.delta ? `<div class="row wrap" style="margin:10px 0"><span class="chip ok">naprawiono ${rep.delta.resolved.length}</span><span class="chip ${rep.delta.new.length ? 'warn' : ''}">nowe ${rep.delta.new.length}</span><span class="chip">wciąż ${rep.delta.persisting}</span><span class="chip ${rep.delta.score_change >= 0 ? 'ok' : 'err'}">${rep.delta.score_change >= 0 ? '+' : ''}${rep.delta.score_change} pkt</span><span class="dim" style="font-size:12px">vs runda ${rep.delta.since_round}</span></div>` : ''}
        ${hist.length > 1 ? `<div class="row" style="margin-top:8px"><div class="spark" title="Wynik w kolejnych rundach">${hist.map(h => `<i style="height:${Math.max(6, h.score) * 0.32}px" title="runda ${h.round}: ${h.score}"></i>`).join('')}</div><span class="dim" style="font-size:12px">wynik w ${hist.length} rundach</span></div>` : ''}
        ${rep && rep.assets ? `<div style="margin:12px 0"><img src="${assetUrl(rep, rep.assets.filmstrip)}" alt="Taśma filmowa" style="width:100%;border-radius:10px;border:1px solid var(--line);cursor:zoom-in" id="strip"></div>` : ''}
        ${rep && rep.next_actions.length ? `<div class="card pad" style="margin:10px 0"><h3 style="margin-bottom:8px">Co poprawić najpierw</h3>${rep.next_actions.map(a => `<div class="muted" style="font-size:13px;margin-bottom:6px">${esc(a)}</div>`).join('')}<button class="btn sm primary" id="askAll" style="margin-top:6px">${V.icon('send')} Wyślij do agenta</button></div>` : ''}
        <div class="col" id="findings">${rep ? (rep.findings.length ? rep.findings.map((f, i) => `<div class="finding ${f.severity}" data-f="${i}"><div class="row"><span class="ttl" style="flex:1">${esc(f.title)}</span>${f.t != null ? `<span class="chip mono">${V.fmtTime(f.t)}</span>` : ''}<span class="chip">${esc(f.code)}</span></div><div class="det">${esc(f.detail)}</div>
          ${S.selected === i ? `<div class="fix"><b>Wskazówka dla agenta:</b> ${esc(f.fix)}</div>${f.evidence ? `<img src="${assetUrl(rep, f.evidence)}" alt="Dowód" style="width:100%;margin-top:8px;border-radius:8px;border:1px solid var(--line)">` : ''}<div class="row" style="margin-top:8px"><button class="btn sm" data-ask="${i}">${V.icon('send')} Napraw z agentem</button></div>` : ''}</div>`).join('') : `<div class="card empty" style="padding:26px"><div class="glyph">✨</div>Brak znalezisk. Film spełnia wszystkie kontrole.</div>`) : ''}</div>`;
      const dsel = $('#depth', body); dsel.value = S.depth || 'standard'; dsel.onchange = () => { S.depth = dsel.value; };
      $('#runCheck', body).onclick = e => V.busy(e.currentTarget, async () => { const r = await V.api('check_run', { project: pid, depth: dsel.value }); S.report = r; S.selected = null; S.history = (await V.api('check_history', { project: pid })).rounds; renderCheck(); renderTimeline(); V.refreshProjects(); V.toast(`Nadzór: ${V.verdict(r.verdict)[1]} (wynik ${r.score})`, r.verdict === 'pass' ? 'ok' : ''); });
      const strip = $('#strip', body); if (strip) strip.onclick = () => V.modal(`<img src="${strip.src}" style="width:100%;border-radius:10px">`, { wide: true });
      const aa = $('#askAll', body); if (aa) aa.onclick = e => askAgent(`Projekt ${pid}: popraw film wg rundy ${rep.round} nadzoru.\n` + rep.next_actions.join('\n'), e.currentTarget);
      $$('.finding', body).forEach(el => el.onclick = e => { if (e.target.closest('button')) return; const i = +el.dataset.f, f = rep.findings[i]; S.selected = S.selected === i ? null : i; renderCheck();
        if (f.t != null) { setPlay(false); seek(f.t, { keepBox: true }); if (f.box) { $('#ovl', host).innerHTML = `<div class="box" style="left:${100 * f.box[0] / W}%;top:${100 * f.box[1] / H}%;width:${100 * (f.box[2] - f.box[0]) / W}%;height:${100 * (f.box[3] - f.box[1]) / H}%"></div>`; } } });
      $$('[data-ask]', body).forEach(b => b.onclick = e => { e.stopPropagation(); askAgent(findingPrompt(rep.findings[+b.dataset.ask]), b); });
    };

    /* ---------- źródło ---------- */
    const renderSource = async () => {
      const body = $('#pbody', host); if (tab !== 'zrodlo') return;
      body.innerHTML = '<div class="skel" style="height:320px"></div>';
      let sc, hist;
      try { [sc, hist] = await Promise.all([V.api('scene_read', { project: pid }), V.api('scene_history', { project: pid })]); } catch (e) { body.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; }
      if (!alive || tab !== 'zrodlo') return; S.scene = sc; S.mtime = V.project(pid)?.updated;
      const v = sc.vendor, offline = v.needs_network.length && !v.vendored.length;
      body.innerHTML = `${v.external.length ? `<div class="card pad" style="margin-bottom:12px"><div class="row"><h3 style="flex:1">Zasoby z sieci</h3><span class="chip ${v.needs_network.length ? 'warn' : 'ok'}">${v.needs_network.length ? 'wymagają sieci' : 'lokalne kopie'}</span></div>
          ${v.external.map(u => `<div class="row" style="margin-top:8px"><span class="mono muted" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(u)}">${esc(u)}</span>${v.vendored.includes(u) ? '<span class="chip ok">offline ✓</span>' : `<button class="btn sm" data-vend="${esc(u)}">${V.icon('download')} Kopia lokalna</button>`}</div>`).join('')}</div>` : ''}
        <div class="row" style="margin-bottom:8px"><span class="chip">${sc.lines} linii</span><span class="chip mono">${esc(sc.sha)}</span><div class="spacer"></div>
          <select id="hist" style="width:auto;max-width:170px"><option value="">Historia (${hist.versions.length})</option>${hist.versions.map(h => `<option value="${esc(h.version)}">${esc(h.version.replace('.html', ''))} ${esc(h.note)}</option>`).join('')}</select></div>
        ${sc.truncated ? `<div class="card pad muted">Plik jest większy niż 60 kB, więc dashboard go nie edytuje. Zmień go w edytorze kodu albo przez agenta.</div>` : `<textarea id="editor" class="editor" spellcheck="false">${esc(sc.content)}</textarea>
        <div class="row" style="margin-top:10px"><button class="btn" id="save">Zapisz</button><button class="btn primary" id="saveCheck" style="flex:1">${V.icon('shield')} Zapisz i sprawdź</button></div>
        <div class="dim" style="font-size:12px;margin-top:8px">Zapis tworzy kopię w historii (cofniesz go z listy). <kbd>Ctrl</kbd>+<kbd>S</kbd> zapisuje. Gdy agent zmieni plik, podgląd odświeży się sam.</div>`}`;
      const ed = $('#editor', body);
      if (ed) {
        ed.oninput = () => { S.sceneDirty = true; };
        ed.onkeydown = e => { if (e.key === 'Tab') { e.preventDefault(); const s = ed.selectionStart; ed.setRangeText('  ', s, ed.selectionEnd, 'end'); } if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); $('#save', body).click(); } };
        const doSave = (btn, check) => V.busy(btn, async () => { const r = await V.api('scene_write', { project: pid, content: ed.value, note: 'dashboard', check: check ? 'quick' : undefined }); S.sceneDirty = false; S.scene.sha = r.sha; loadFrame(); await V.refreshProjects();
          if (r.check) { S.report = (await V.api('check_latest', { project: pid })).report; S.history = (await V.api('check_history', { project: pid })).rounds; renderTimeline(); V.toast(`Zapisano. Nadzór: ${V.verdict(r.check.verdict)[1]} (${r.check.score})`, r.check.verdict === 'pass' ? 'ok' : ''); } else V.toast('Zapisano', 'ok'); });
        $('#save', body).onclick = e => doSave(e.currentTarget, false); $('#saveCheck', body).onclick = e => doSave(e.currentTarget, true);
      }
      $('#hist', body).onchange = async e => { const ver = e.target.value; if (!ver) return; if (S.sceneDirty && !confirm('Masz niezapisane zmiany. Przywrócić wersję i je utracić?')) { e.target.value = ''; return; }
        await V.busy(null, async () => { await V.api('scene_restore', { project: pid, version: ver }); S.sceneDirty = false; V.toast('Przywrócono wersję', 'ok'); loadFrame(); await V.refreshProjects(); renderSource(); }); };
      $$('[data-vend]', body).forEach(b => b.onclick = () => V.busy(b, async () => { try { await V.api('vendor_add', { url: b.dataset.vend }); V.toast('Zapisano lokalną kopię', 'ok'); loadFrame(); renderSource(); } catch (e) { V.modal(`<h3>Nie udało się pobrać</h3><p class="muted">${esc(e.message)}</p><p>Bez sieci skopiuj bibliotekę z dysku:</p><div class="code">python vstudio.py vendor add ${esc(b.dataset.vend)} --file /sciezka/do/pliku.js</div>`); } }));
    };

    /* ---------- render ---------- */
    const renderRender = async () => {
      const body = $('#pbody', host); if (tab !== 'render') return;
      const [jl, det] = await Promise.all([V.api('jobs_list', { project: pid }), V.api('project_get', { project: pid })]); if (!alive || tab !== 'render') return;
      S.jobs = jl.jobs; S.detail = det.project; const R = det.project.renders;
      const jobRow = j => `<div class="card pad" style="padding:12px 14px"><div class="row"><span class="dot ${j.status === 'running' ? 'warn' : j.status === 'done' ? 'ok' : 'err'}" style="animation:none"></span><b style="flex:1">${esc(j.kind)}</b><span class="chip ${j.status === 'done' ? 'ok' : j.status === 'running' ? 'warn' : 'err'}">${esc(j.status)}</span>${j.status === 'running' ? `<button class="btn sm ghost" data-cancel="${esc(j.id)}">Anuluj</button>` : ''}</div>
        ${j.status === 'running' ? `<div class="progress" style="margin:8px 0"><i style="width:${Math.round(j.progress * 100)}%"></i></div>` : ''}<div class="dim mono" style="font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(j.message)}</div></div>`;
      body.innerHTML = `<div class="grid c2" style="gap:10px"><button class="btn primary" id="rDraft">${V.icon('film')} Render roboczy</button><button class="btn" id="rFinal">Render finalny</button><button class="btn" id="rSound">Dźwięk (−14 LUFS)</button><button class="btn" id="rDeliver">Wydanie (QA + paczka)</button></div>
        <div class="dim" style="font-size:12.5px;margin:8px 0 14px">Render finalny wymaga zatwierdzonych bramek: brief, zasady wizualne, klatki (zakładka Potok). Wymaga FFmpeg.</div>
        <div class="col" id="jobs">${S.jobs.slice(0, 5).map(jobRow).join('')}</div>
        <h3 style="margin:18px 0 10px">Rendery (${R.length})</h3>
        ${R.length ? `<video controls preload="metadata" style="width:100%;border-radius:12px;background:#000;max-height:360px" src="${V.fileUrl(pid, R[0].file)}"></video>
          <div class="col" style="margin-top:10px">${R.map(r => `<a class="row muted" href="${V.fileUrl(pid, r.file)}" target="_blank" style="text-decoration:none"><span>${r.final ? '🎞' : '▫'}</span><span class="mono" style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(r.file.split('/').pop())}</span><span>${r.mb} MB</span></a>`).join('')}</div>` : '<div class="card empty" style="padding:24px">Jeszcze nie ma renderów.</div>'}`;
      const start = (id, name, args) => $(id, body).onclick = e => V.busy(e.currentTarget, async () => { const r = await V.api(name, { project: pid, ...args }); (r.warnings || []).forEach(w => V.toast(w, '', 6500)); V.toast('Job uruchomiony', 'ok'); renderRender(); });
      start('#rDraft', 'render_start', {}); start('#rFinal', 'render_start', { final: true }); start('#rSound', 'sound_start', {}); start('#rDeliver', 'deliver_start', {});
      $$('[data-cancel]', body).forEach(b => b.onclick = () => V.busy(b, async () => { await V.api('job_cancel', { job: b.dataset.cancel }); renderRender(); }));
    };
    const auto = $('#autoSup', host); auto.checked = !(V.S.profile && V.S.profile.auto_supervise === false);
    auto.onchange = () => V.api('profile_set', { auto_supervise: auto.checked }).then(p => { V.S.profile = p; V.toast(auto.checked ? 'Auto-nadzór włączony' : 'Auto-nadzór wyłączony', 'ok', 1800); }).catch(e => { V.toast(e.message, 'err'); auto.checked = !auto.checked; });
    $('#bCheck', host).onclick = () => { tab = 'nadzor'; setTab(); setTimeout(() => $('#runCheck', host) && $('#runCheck', host).click(), 50); };
    $('#bDraft', host).onclick = () => { tab = 'render'; setTab(); setTimeout(() => $('#rDraft', host) && $('#rDraft', host).click(), 350); };

    /* ---------- potok ---------- */
    const renderPipe = async () => {
      const body = $('#pbody', host); if (tab !== 'potok') return;
      const det = (await V.api('project_get', { project: pid })).project; if (!alive || tab !== 'potok') return; S.detail = det;
      const nextGate = det.next.split(':')[0];
      body.innerHTML = `<div class="card pad" style="margin-bottom:12px"><div class="dim" style="font-size:12px;margin-bottom:4px">NASTĘPNY KROK</div><div>${esc(det.next)}</div></div>
        <div class="col">${GATES.map(([k, l]) => { const v = det.gates[k], done = v !== null && v !== false && v !== 'n/a', na = v === 'n/a'; return `<div class="gate ${done ? 'done' : ''} ${k === nextGate ? 'next' : ''}"><span class="ck">${done ? '✓' : ''}</span><span style="flex:1">${l}${na ? ' <span class="dim">(nie dotyczy)</span>' : ''}${typeof v === 'string' && !na ? ` <span class="dim mono" style="font-size:12px">${esc(v)}</span>` : ''}</span>
          ${k === 'critic' ? `<input type="number" min="0" max="10" step=".5" id="score" value="${det.critic_score ?? ''}" placeholder="0-10" style="width:76px"><button class="btn sm" data-score>Zapisz</button>` : !na ? `<button class="btn sm ${done ? 'ghost' : ''}" data-gate="${k}" data-act="${done ? 'reset' : 'approve'}">${done ? 'Cofnij' : 'Zatwierdź'}</button>` : ''}</div>`; }).join('')}</div>
        <div class="dim" style="font-size:12.5px;margin-top:12px">Zatwierdzaj bramkę dopiero, gdy praca jest naprawdę skończona. Finalny render blokuje brak: brief, zasady wizualne, klatki.</div>`;
      $$('[data-gate]', body).forEach(b => b.onclick = () => V.busy(b, async () => { await V.api('gate_set', { project: pid, action: b.dataset.act, gate: b.dataset.gate }); await V.refreshProjects(); renderPipe(); }));
      const sb = $('[data-score]', body); if (sb) sb.onclick = () => V.busy(sb, async () => { const v = parseFloat($('#score', body).value); if (isNaN(v)) { V.toast('Podaj ocenę 0-10', 'err'); return; } await V.api('gate_set', { project: pid, action: 'score', score: v }); await V.refreshProjects(); renderPipe(); });
    };

    /* ---------- agent (per projekt) ---------- */
    const renderAgent = async () => {
      const body = $('#pbody', host); if (tab !== 'agent') return;
      const [tk, act] = await Promise.all([V.api('task_list', {}), V.api('activity_tail', { limit: 60 })]); if (!alive || tab !== 'agent') return;
      const mine = tk.tasks.filter(t => t.project === pid).reverse(), evs = act.events.filter(e => e.project === pid).reverse().slice(0, 14), a = act.agent;
      body.innerHTML = `<div class="row" style="margin-bottom:10px"><span class="dot ${a.connected ? 'ok' : ''}"></span><span class="muted">${a.connected ? `Agent połączony (${esc(a.last_call)})` : 'Agent niepodłączony'}</span><div class="spacer"></div><a class="btn sm" href="#/agent">Połącz</a></div>
        <textarea id="ask" placeholder="Poproś agenta o zmianę, np. „skróć do 5 s i zmień akcent na koral”"></textarea><button class="btn primary" id="askBtn" style="margin-top:8px;width:100%">${V.icon('send')} Wyślij do agenta</button>
        <h3 style="margin:18px 0 8px">Zadania (${mine.length})</h3><div class="col">${mine.map(t => `<div class="card pad" style="padding:12px 14px"><div class="row"><span class="mono dim">${esc(t.id)}</span><span class="chip ${t.status === 'done' ? 'ok' : t.status === 'in_progress' ? 'info' : t.status === 'blocked' ? 'err' : ''}">${esc(t.status)}</span></div><div style="margin:6px 0;font-size:13.5px">${esc(t.prompt)}</div>${t.notes.map(n => `<div class="muted" style="font-size:12.5px">↳ ${esc(n.text)}</div>`).join('')}</div>`).join('') || '<div class="dim">Brak zadań dla tego projektu.</div>'}</div>
        <h3 style="margin:18px 0 8px">Aktywność w projekcie</h3><div class="feed">${V.feedRows(evs) || '<div class="dim">Brak.</div>'}</div>`;
      $('#askBtn', body).onclick = e => V.busy(e.currentTarget, async () => { const prompt = $('#ask', body).value.trim(); if (!prompt) { V.toast('Napisz, o co prosisz', 'err'); return; } await V.api('task_create', { prompt, project: pid }); V.toast('Zadanie dodane', 'ok'); renderAgent(); V.refreshStatus(); });
    };

    const setTab = () => { $$('#tabs button', host).forEach(b => b.classList.toggle('on', b.dataset.tab === tab)); history.replaceState(null, '', `#/p/${pid}/${tab}`);
      ({ nadzor: renderCheck, zrodlo: renderSource, render: renderRender, potok: renderPipe, agent: renderAgent })[tab](); };
    $$('#tabs button', host).forEach(b => b.onclick = () => { tab = b.dataset.tab; setTab(); });

    // dane początkowe
    Promise.all([V.api('check_latest', { project: pid }), V.api('check_history', { project: pid })]).then(([l, h]) => { if (!alive) return; S.report = l.report; S.history = h.rounds; if (tab === 'nadzor') renderCheck(); renderTimeline(); });
    setTab();

    // pulse: odśwież podgląd, gdy scena zmieniła się na dysku (agent!), oraz postęp jobów
    const off = V.on('pulse', ({ p, prev }) => {
      const m = p.projects[pid]; if (!m) return;
      if (S.mtime && m.updated && m.updated !== S.mtime) {
        S.mtime = m.updated;
        if (!S.sceneDirty) { clearTimeout(S.rl); S.rl = setTimeout(() => { loadFrame(); V.toast('Scena zmieniła się na dysku: odświeżono podgląd', ''); if (tab === 'zrodlo') renderSource(); }, 350); }
        else V.toast('Plik zmienił się na dysku, a masz niezapisane zmiany w edytorze', 'err', 7000);
      }
      if (prev && prev.projects[pid] && m.round !== prev.projects[pid].round && tab === 'nadzor') V.api('check_latest', { project: pid }).then(l => { S.report = l.report; renderCheck(); renderTimeline(); });
      if (tab === 'render' && (p.jobs.length || (prev && prev.jobs.length))) renderRender();
      if (tab === 'agent' && p.events.length) renderAgent();
    });
    return () => { alive = false; off(); ro.disconnect(); cancelAnimationFrame(Pl.raf); document.removeEventListener('keydown', onKey); };
  };
})();
