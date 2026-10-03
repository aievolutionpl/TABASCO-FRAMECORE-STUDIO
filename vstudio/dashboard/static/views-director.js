/* Zakładka „Reżyser” w warsztacie projektu: plan stylu i bitów, przegląd (rytm, hak, tekst, ruch), zatwierdzenie i assety. */
'use strict';
(() => {
  const { esc, $, $$ } = V;
  const ROLE = { hook: 'Hak', problem: 'Problem', setup: 'Wstęp', reveal: 'Odsłonięcie', proof: 'Dowód', benefit: 'Korzyści', detail: 'Szczegół', demo: 'Demo', card: 'Karta', point: 'Punkt', item: 'Pozycja', cta: 'CTA' };
  const FORMATS = [['', 'dowolny (dobierz sam)'], ['tool-drop', 'Polecajka narzędzia'], ['talking-head', 'Mówiąca głowa z napisami'], ['listicle', 'Lista N rzeczy']];
  const CHECK = {
    hook: 'Pierwsza sekunda przyciąga uwagę (ruch, mocny napis albo obraz).',
    text: 'Każdy tekst jest w pełni widoczny, czytelny na telefonie i bez literówek (polskie znaki też).',
    rhythm: 'Co 2-3 s widać coś nowego, żaden bit nie jest nieruchomym slajdem.',
    style: 'Wygląd pasuje do marki i celu, a style są mieszane celowo.',
    motion: 'Ruch ma ciężar: wygładzone wejścia i zatrzymania, elementy wchodzą z opóźnieniem, nic nie jedzie jak robot.',
    assets: 'Ikony i obrazy są ostre, spójne z marką i pomagają przekazowi.',
  };
  const STATE = { none: ['', 'Brak przeglądu'], reviewed: ['warn', 'Przegląd bez zatwierdzenia'], approved: ['ok', 'Zatwierdzone'], rejected: ['err', 'Odrzucone'], stale: ['warn', 'Scena zmieniona po decyzji'] };
  const PLATFORMS = [['', 'dobierz do formatu'], ['reels', 'Reels'], ['tiktok', 'TikTok'], ['shorts', 'Shorts'], ['story', 'Story'], ['feed', 'Feed'], ['linkedin', 'LinkedIn'], ['web', 'Strona www'], ['presentation', 'Prezentacja']];
  const lookColor = i => `hsl(${(i * 67 + 210) % 360} 62% 56%)`;

  V.directorPanel = ctx => {
    const { pid, host, DUR, isActive, seek, askAgent } = ctx;
    const D = { latest: null, state: null, plan: null, history: [], assets: null, depth: 'standard', prefer: [], sel: null, results: null, form: null };

    /* ---------- wykres rytmu ---------- */
    const chart = () => {
      const rep = D.latest; if (!rep) return '';
      const m = rep.metrics, dur = m.duration || DUR, Wd = 600, Ht = 150, L = 8, R = 8, T = 16, B = 30, step = m.step || 0.1, ser = m.shift_series || [];
      const x = t => L + (Wd - L - R) * t / dur, top = Math.max(0.3, Math.max(0, ...ser) * 1.15), y = v => Ht - B - (Ht - B - T) * Math.min(v / top, 1);
      const pts = ser.map((v, i) => [x(i * step), y(v)]);
      const area = pts.length ? `M${x(0)},${Ht - B} ` + pts.map(p => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ') + ` L${pts[pts.length - 1][0].toFixed(1)},${Ht - B}Z` : '';
      const plan = D.plan && Math.abs(D.plan.duration - dur) <= 0.5 ? D.plan.beats : [];
      const labels = m.look_labels || [];
      return `<svg class="rchart" viewBox="0 0 ${Wd} ${Ht}" id="rchart" role="img" aria-label="Wykres rytmu filmu">
        ${(m.gaps || []).map(g => `<rect x="${x(g[0])}" y="${T}" width="${x(g[1]) - x(g[0])}" height="${Ht - B - T}" class="gap"><title>Luka ${g[0]}–${g[1]} s: nic nowego</title></rect>`).join('')}
        <line x1="${L}" x2="${Wd - R}" y1="${y(0.1)}" y2="${y(0.1)}" class="thr"/>
        <path d="${area}" class="area"/><polyline points="${pts.map(p => p.map(n => n.toFixed(1)).join(',')).join(' ')}" class="line"/>
        ${plan.map(b => `<g><line x1="${x(b.t0)}" x2="${x(b.t0)}" y1="${T}" y2="${Ht - B}" class="beat"/><text x="${x(b.t0) + 3}" y="${T - 4}" class="lbl">${esc(ROLE[b.role] || b.role)}</text></g>`).join('')}
        ${(m.events || []).map(e => `<line x1="${x(e)}" x2="${x(e)}" y1="${T}" y2="${Ht - B}" class="ev"><title>nowa sytuacja @ ${e.toFixed(2)} s</title></line>`).join('')}
        ${Array.from({ length: Math.ceil(dur) }, (_, s) => `<text x="${x(s) + 2}" y="${Ht - B + 11}" class="tick">${s}s</text>`).join('')}
        ${labels.map((lb, s) => `<rect x="${x(s)}" y="${Ht - 14}" width="${Math.max(2, x(Math.min(s + 1, dur)) - x(s) - 1)}" height="9" rx="2" fill="${lookColor(lb)}"><title>look ${lb + 1} @ ${s}–${s + 1} s</title></rect>`).join('')}
        <line id="rhead" x1="0" x2="0" y1="${T}" y2="${Ht - B}" class="head" visibility="hidden"/></svg>`;
    };

    const ring = (score, kind) => { const c = 2 * Math.PI * 34, col = { ok: 'var(--ok)', warn: 'var(--warn)', err: 'var(--err)', '': 'var(--dim)' }[kind]; return `<div class="ring"><svg width="84" height="84" viewBox="0 0 84 84"><circle cx="42" cy="42" r="34" fill="none" stroke="var(--panel-3)" stroke-width="8"/><circle cx="42" cy="42" r="34" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${c * (score || 0) / 100} ${c}"/></svg><b>${score ?? '–'}</b></div>`; };
    const metric = (label, val, cls = '') => `<span class="chip ${cls}" title="${esc(label)}">${esc(label)}: <b>${esc(val)}</b></span>`;
    const evUrl = (rep, name) => V.fileUrl(pid, `director/${rep.assets.dir}/${name}`);

    /* ---------- sekcje ---------- */
    const head = () => {
      const rep = D.latest, st = D.state, [sk, sl] = STATE[st.state] || ['', st.state], [vk, vl] = V.verdict(rep && rep.verdict), m = rep && rep.metrics;
      const so = st.signoff;
      return `<div class="row" style="gap:16px">${ring(rep ? rep.score : null, vk)}<div style="flex:1"><div class="row wrap" style="gap:6px;margin-bottom:6px"><span class="chip ${vk}">${esc(vl)}</span><span class="chip ${sk}" title="Finalny render i wydanie wymagają zatwierdzenia aktualnej wersji sceny">${esc(sl)}</span></div>
          <div class="muted" style="font-size:13px">${rep ? `${rep.counts.error} błędów · ${rep.counts.warn} ostrzeżeń · ${rep.counts.info} info<br>przegląd ${rep.round} · ${esc(rep.depth)} · ${rep.metrics.elapsed_s} s${so ? `<br>decyzja: ${esc(so.by)} · ${esc((so.at || '').replace('T', ' '))}` : ''}` : 'Reżyser sprawdza to, co widzi widz: rytm, hak, różnorodność, ruch, tekst i fonty, obrazy.'}</div></div></div>
        <div class="row" style="margin:14px 0 4px"><select id="dDepth" style="width:auto"><option value="quick">szybki</option><option value="standard">standardowy</option><option value="deep">dokładny</option></select><button class="btn primary" id="dRun" style="flex:1">${V.icon('eye')} Uruchom przegląd reżysera</button></div>
        ${m ? `<div class="row wrap" style="gap:6px;margin:10px 0 2px">${metric('tempo', `${m.platform}, zmiana co ≤ ${m.max_gap} s`)}${metric('haczyk', Math.round(m.hook * 100) + '%', m.hook < 0.08 ? 'warn' : 'ok')}${metric('looki', `${m.looks}/${m.looks_required}`, m.looks < m.looks_required ? 'warn' : 'ok')}${metric('nowe sytuacje', m.events.length)}${m.motion && m.motion.moves ? metric('ruch liniowy', Math.round(m.motion.share * 100) + '%', m.motion.share >= 0.5 ? 'warn' : 'ok') : ''}${metric('assety', m.assets_visible)}${m.plan_adherence != null ? metric('zgodność z planem', Math.round(m.plan_adherence * 100) + '%') : ''}${m.thinned ? metric('próbkowanie', 'rzadsze (ciężka scena)', 'warn') : ''}</div>` : ''}
        ${m && m.motion_skipped ? `<div class="dim" style="font-size:12px;margin-top:6px">Analiza ruchu pominięta: ${esc(m.motion_skipped)}</div>` : ''}`;
    };

    const rhythmCard = () => D.latest ? `<div class="card pad" style="margin:12px 0"><div class="row" style="margin-bottom:6px"><h3 style="flex:1">Rytm</h3><span class="dim" style="font-size:12px"><i class="lg ev"></i>nowa sytuacja <i class="lg gap"></i>luka <i class="lg beat"></i>bit z planu</span></div>${chart()}
        <div class="dim" style="font-size:12px;margin-top:4px">Niebieska krzywa to zmiana kadru względem 0,5 s wcześniej; kolorowy pasek to „looki” (podobny wygląd = ten sam kolor). Kliknij wykres, żeby przejść do tej chwili.</div>
        ${D.latest.assets ? `<img src="${evUrl(D.latest, D.latest.assets.filmstrip)}" alt="Taśma klatek" style="width:100%;border-radius:10px;border:1px solid var(--line);margin-top:10px;cursor:zoom-in" id="dStrip">` : ''}</div>` : '';

    const findingsCard = () => {
      const rep = D.latest; if (!rep) return '';
      return `<div class="col" id="dFindings">${rep.findings.length ? rep.findings.map((f, i) => `<div class="finding ${f.severity}" data-f="${i}"><div class="row"><span class="ttl" style="flex:1">${esc(f.title)}</span>${f.t != null ? `<span class="chip mono">${V.fmtTime(f.t)}</span>` : ''}<span class="chip">${esc(f.code)}</span></div><div class="det">${esc(f.detail)}</div>
          ${D.sel === i ? `<div class="fix"><b>Wskazówka dla agenta:</b> ${esc(f.fix)}</div>${f.evidence ? `<img src="${evUrl(rep, f.evidence)}" alt="Dowód" style="width:100%;margin-top:8px;border-radius:8px;border:1px solid var(--line)">` : ''}<div class="row" style="margin-top:8px"><button class="btn sm" data-ask="${i}">${V.icon('send')} Napraw z agentem</button></div>` : ''}</div>`).join('') : `<div class="card empty" style="padding:26px"><div class="glyph">🎬</div>Reżyser nie ma uwag. Obejrzyj klatki i zatwierdź.</div>`}</div>`;
    };

    const signCard = () => {
      const rep = D.latest, st = D.state; if (!rep) return '';
      const warns = [...new Map(rep.findings.filter(f => f.severity === 'warn').map(f => [f.code, f])).values()];
      if (st.state === 'approved') {
        const so = st.signoff, acc = so.accepted || {};
        return `<div class="card pad" style="margin:12px 0"><div class="row"><h3 style="flex:1">Zatwierdzone</h3><span class="chip ok">${esc(so.by)}</span></div><p class="muted" style="margin:8px 0;font-size:13.5px">${esc(so.notes)}</p>
          ${Object.keys(acc).length ? `<div class="dim" style="font-size:12.5px">Świadomie zaakceptowane: ${Object.entries(acc).map(([k, v]) => `<b>${esc(k)}</b> (${esc(v)})`).join(', ')}</div>` : ''}
          <div class="dim" style="font-size:12.5px;margin-top:8px">Każda zmiana sceny unieważni to zatwierdzenie.</div></div>`;
      }
      return `<div class="card pad" style="margin:12px 0"><h3 style="margin-bottom:6px">Zatwierdzenie przed wysyłką</h3>
        <div class="dim" style="font-size:12.5px;margin-bottom:10px">Finalny render i wydanie wystartują dopiero po zatwierdzeniu aktualnej wersji sceny. Obejrzyj taśmę klatek i wykres, potem potwierdź każdą pozycję.</div>
        <div class="col" style="gap:8px">${Object.entries(CHECK).map(([k, v]) => `<label class="map-row" style="align-items:flex-start"><input type="checkbox" data-chk="${k}" style="margin-top:3px"><span style="font-size:13.5px">${esc(v)}</span></label>`).join('')}</div>
        ${warns.length ? `<div style="margin-top:12px"><div class="dim" style="font-size:12.5px;margin-bottom:6px">Ostrzeżenia: napraw je albo zaakceptuj z powodem (np. celowa cisza w otwarciu).</div>${warns.map(f => `<div class="row" style="margin-bottom:6px"><span class="chip warn">${esc(f.code)}</span><input class="acc" data-acc="${esc(f.code)}" placeholder="powód akceptacji" style="flex:1"></div>`).join('')}</div>` : ''}
        ${rep.counts.error ? `<div class="chip err" style="margin-top:12px">Błędy blokują zatwierdzenie: popraw je i uruchom przegląd ponownie.</div>` : ''}
        <textarea id="dNotes" placeholder="Co zobaczyłeś na klatkach? (min. 12 znaków)" style="margin-top:12px"></textarea>
        <div class="row" style="margin-top:8px"><button class="btn primary" id="dApprove" style="flex:1" ${rep.counts.error ? 'disabled' : ''}>${V.icon('check')} Zatwierdź</button><button class="btn" id="dReject">Odrzuć</button></div></div>`;
    };

    const planCard = () => {
      const p = D.plan, f = D.form || {};
      const styleChip = (s, role) => `<span class="schip" title="${esc(s.tagline || '')}"><i style="background:${esc(s.palette.accent)}"></i><i style="background:${esc(s.palette.accent2)}"></i><i style="background:${esc(s.palette.bg)}"></i>${esc(s.name)}${role ? `<small>${role}</small>` : ''}</span>`;
      const beats = p ? p.beats.map(b => { const w = 100 * (b.t1 - b.t0) / p.duration; return `<div class="bt" style="flex:${w}" title="${esc(b.copy)}"><b>${esc(ROLE[b.role] || b.role)}</b><span>${b.t0}–${b.t1} s</span><em>${esc(b.style)}</em><small>${esc(b.layout)}${b.transition_in ? ' · ' + esc(b.transition_in) : ''}</small></div>`; }).join('') : '';
      return `<div class="card pad" style="margin:12px 0"><div class="row" style="margin-bottom:8px"><h3 style="flex:1">Plan reżyserski</h3>${p ? `<button class="btn sm" id="pSend">${V.icon('send')} Zbuduj z agentem</button>` : ''}</div>
        ${p ? `<div class="row wrap" style="gap:6px;margin-bottom:8px">${styleChip(p.styles.main, 'główny')}${p.styles.accents.map(a => styleChip(a, 'akcent')).join('')}<span class="chip">${esc(p.platform)} · tempo ${esc(p.pace)}</span>${p.format ? `<span class="chip ok">format: ${esc(p.format.name)}</span>` : ''}</div>
          ${(p.warnings || []).map(w => `<div class="chip warn" style="margin-bottom:6px;white-space:normal">${esc(w)}</div>`).join('')}
          <div class="beats">${beats}</div><div class="dim" style="font-size:12px;margin-top:6px">Stałe: kolory i font marki. Zmienne co bit: układ, tło, język ruchu, przejście. Kliknij bit, żeby zobaczyć regułę tekstu.</div>` : '<div class="dim" style="margin-bottom:8px">Zaplanuj film zanim go zbudujesz: dobiorę styl główny i dwa akcenty o różnych układach i ułożę bity co 2-3 s.</div>'}
        <details style="margin-top:10px" ${p ? '' : 'open'}><summary class="btn sm ghost" style="display:inline-flex">${p ? 'Zaplanuj od nowa' : 'Nowy plan'}</summary><div class="col" style="gap:8px;margin-top:10px">
          <textarea id="pGoal" placeholder="O czym jest film i do czego ma skłonić? np. „Premiera aplikacji do planowania treningów, zachęć do zapisu na listę”">${esc(f.goal || (p ? p.goal : ''))}</textarea>
          <div class="row"><input id="pTone" placeholder="ton (np. premium, zabawny)" value="${esc(f.tone || '')}" style="flex:1"><select id="pPlat" style="width:auto">${PLATFORMS.map(([k, l]) => `<option value="${k}" ${f.platform === k ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
          <div class="row" style="gap:8px">
            <div class="row" style="flex:1"><span class="dim" style="font-size:12.5px;min-width:50px">Profil:</span><select id="pProf" style="flex:1"><option value="premium_minimal" ${f.creative_profile === 'premium_minimal' ? 'selected' : ''}>Premium Minimal</option><option value="cinematic" ${f.creative_profile === 'cinematic' ? 'selected' : ''}>Cinematic</option><option value="social_fast" ${(!f.creative_profile || f.creative_profile === 'social_fast') ? 'selected' : ''}>Social Fast</option><option value="educational" ${f.creative_profile === 'educational' ? 'selected' : ''}>Educational</option></select></div>
            <div class="row" style="flex:1"><span class="dim" style="font-size:12.5px;min-width:50px">Tekst:</span><select id="pTextMode" style="flex:1"><option value="full" ${(!f.text_mode || f.text_mode === 'full') ? 'selected' : ''}>Pełny</option><option value="headline_only" ${f.text_mode === 'headline_only' ? 'selected' : ''}>Tylko nagłówki</option><option value="none" ${f.text_mode === 'none' ? 'selected' : ''}>Bez tekstu</option></select></div>
          </div>
          <div class="row"><span class="dim" style="font-size:12.5px">Format rolki:</span><select id="pFmt" style="flex:1">${FORMATS.map(([k, l]) => `<option value="${k}" ${f.format === k ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
          <div class="row wrap" style="gap:6px"><span class="dim" style="font-size:12.5px">Preferowane style:</span>${D.prefer.map(id => `<span class="chip ok" data-unpref="${esc(id)}" style="cursor:pointer">${esc(id)} ✕</span>`).join('') || '<span class="dim" style="font-size:12.5px">brak (dobiorę sam)</span>'}<button class="btn sm ghost" id="pStyles">Biblioteka stylów</button></div>
          <button class="btn primary" id="pGo">${V.icon('spark')} Zaplanuj</button></div></details></div>`;
    };

    const assetsCard = () => {
      const A = D.assets, res = D.results;
      return `<div class="card pad" style="margin:12px 0"><div class="row" style="margin-bottom:8px"><h3 style="flex:1">Assety</h3><span class="dim" style="font-size:12px">${A ? A.builtin_icons : 0} wbudowanych ikon</span></div>
        <div class="row"><input id="aQ" placeholder="szukaj: koszyk, rakieta, serce…" style="flex:1"><select id="aSrc" style="width:auto"><option value="builtin">wbudowane</option><option value="iconify">Iconify (sieć)</option><option value="openverse">Openverse (sieć)</option></select><button class="btn" id="aGo">Szukaj</button></div>
        ${res ? `<div class="agrid" style="margin-top:10px">${res.results.length ? res.results.map((r, i) => `<div class="aitem"><div class="aprev">${r.preview ? r.preview : `<span class="dim" style="font-size:11px">${esc(r.kind)}</span>`}</div><div class="aname" title="${esc(r.name)}">${esc(r.name)}</div><div class="dim" style="font-size:10.5px">${esc(r.license || '')}</div><button class="btn sm" data-add="${i}">Dodaj</button></div>`).join('') : '<div class="dim">Brak wyników.</div>'}</div>${res.note ? `<div class="dim" style="font-size:12px;margin-top:6px">${esc(res.note)}</div>` : ''}` : ''}
        <div class="row" style="margin-top:12px"><select id="gKind" style="width:auto">${(A ? A.generators : []).map(g => `<option value="${esc(g.kind)}" title="${esc(g.about)}">${esc(g.kind)}</option>`).join('')}</select><input id="gSeed" type="number" min="0" value="1" style="width:84px" title="ziarno: ten sam numer daje tę samą grafikę"><button class="btn" id="gGo">Wygeneruj w kolorach marki</button></div>
        <h3 style="margin:14px 0 8px;font-size:13.5px">W projekcie (${A ? A.assets.length : 0})</h3>
        <div class="agrid">${A && A.assets.length ? A.assets.map(a => `<div class="aitem"><div class="aprev"><img src="${V.fileUrl(pid, 'src/' + a.rel)}" alt="${esc(a.file)}" style="max-width:100%;max-height:100%"></div><div class="aname" title="${esc(a.file)}">${esc(a.file)}</div><div class="dim" style="font-size:10.5px" title="${esc(a.license || 'brak śladu licencji')}">${esc(a.origin)}${a.license ? ' · ' + esc(a.license) : ''}</div><div class="row" style="gap:4px"><button class="btn sm" data-code="${esc(a.file)}">Kod</button><button class="btn sm ghost" data-rm="${esc(a.file)}">✕</button></div></div>`).join('') : '<div class="dim">Brak assetów. Dodaj ikony i grafiki, żeby bity nie były samym tekstem.</div>'}</div></div>`;
    };

    /* ---------- render zakładki ---------- */
    const paint = () => {
      const body = $('#pbody', host); if (!isActive()) return;
      body.innerHTML = head() + rhythmCard() + signCard() + findingsCard() + planCard() + assetsCard();
      wire(body);
    };

    const load = async () => {
      const [lat, as] = await Promise.all([V.api('director_latest', { project: pid }), V.api('assets_list', { project: pid })]);
      Object.assign(D, { latest: lat.review, state: lat.state, plan: lat.plan, history: lat.history, assets: as });
    };

    const wire = body => {
      const sel = $('#dDepth', body); sel.value = D.depth; sel.onchange = () => { D.depth = sel.value; };
      $('#dRun', body).onclick = e => V.busy(e.currentTarget, async () => { const r = await V.api('director_review', { project: pid, depth: D.depth }); await load(); D.sel = null; paint(); V.refreshProjects();
        V.toast(`Reżyser: ${V.verdict(r.verdict)[1]} (wynik ${r.score})`, r.verdict === 'pass' ? 'ok' : ''); });
      const ch = $('#rchart', body);
      if (ch) { const head = $('#rhead', ch); ch.onclick = e => { const r = ch.getBoundingClientRect(), vx = (e.clientX - r.left) / r.width * 600, dur = D.latest.metrics.duration || DUR, t = Math.min(Math.max((vx - 8) / (600 - 16), 0), 1) * dur; seek(t); head.setAttribute('x1', vx); head.setAttribute('x2', vx); head.setAttribute('visibility', 'visible'); }; }
      const strip = $('#dStrip', body); if (strip) strip.onclick = () => V.modal(`<img src="${strip.src}" style="width:100%;border-radius:10px">`, { wide: true });
      $$('.finding', body).forEach(el => el.onclick = e => { if (e.target.closest('button')) return; const i = +el.dataset.f, f = D.latest.findings[i]; D.sel = D.sel === i ? null : i; paint(); if (f.t != null) seek(f.t, { keepBox: true }); });
      $$('[data-ask]', body).forEach(b => b.onclick = e => { e.stopPropagation(); const f = D.latest.findings[+b.dataset.ask]; askAgent(`Projekt ${pid}: napraw uwagę reżysera ${f.code}${f.t != null ? ` przy t=${f.t}s` : ''}. ${f.detail} Wskazówka: ${f.fix} Potem uruchom director_review.`, b); });
      // zatwierdzenie
      const sign = (btn, approve) => V.busy(btn, async () => {
        const checklist = {}; $$('[data-chk]', body).forEach(c => { checklist[c.dataset.chk] = c.checked; });
        const accept = {}; $$('[data-acc]', body).forEach(i => { if (i.value.trim()) accept[i.dataset.acc] = i.value.trim(); });
        const r = await V.api('director_signoff', { project: pid, approve, notes: $('#dNotes', body).value, checklist, accept });
        await load(); paint(); V.refreshProjects(); V.toast(approve ? 'Zatwierdzone: finalny render i wydanie odblokowane' : 'Odrzucone', approve ? 'ok' : '');
      });
      const ap = $('#dApprove', body); if (ap) ap.onclick = e => sign(e.currentTarget, true);
      const rj = $('#dReject', body); if (rj) rj.onclick = e => sign(e.currentTarget, false);
      // plan
      const ps = $('#pSend', body); if (ps) ps.onclick = e => askAgent(`Projekt ${pid}: zbuduj scenę według planu reżyserskiego (director_latest). Styl główny ${D.plan.styles.main.id}, akcenty ${D.plan.styles.accents.map(a => a.id).join(', ')}; ${D.plan.beats.length} bitów, nowa sytuacja wizualna co ${D.plan.contract.visible_change_every_s} s. Dodaj ikony i grafiki (assets_search, assets_add, assets_generate). Na końcu director_review i director_signoff.`, e.currentTarget);
      $$('[data-unpref]', body).forEach(c => c.onclick = () => { D.prefer = D.prefer.filter(x => x !== c.dataset.unpref); paint(); });
      const saveForm = () => { D.form = { goal: $('#pGoal', body).value, tone: $('#pTone', body).value, platform: $('#pPlat', body).value, format: $('#pFmt', body).value, creative_profile: $('#pProf', body).value, text_mode: $('#pTextMode', body).value }; };
      $('#pStyles', body).onclick = async () => { saveForm(); const r = await V.api('styles_list', {}); const m = V.modal(`<h3>Biblioteka stylów</h3><p class="muted" style="margin:4px 0 12px">Kliknij, żeby preferować styl w planie (maks. 2). Reszta zostanie dobrana pod cel i ton.</p><div class="sgrid">${r.styles.map(s => `<div class="scard ${D.prefer.includes(s.id) ? 'on' : ''}" data-s="${esc(s.id)}"><div class="row"><b style="flex:1">${esc(s.name)}</b><span class="dim mono" style="font-size:11px">energia ${s.energy}</span></div><div class="muted" style="font-size:12.5px;margin:4px 0 8px">${esc(s.tagline)}</div><div class="row" style="gap:4px;margin-bottom:6px">${Object.values(s.palette).map(c => `<i class="chipc" style="background:${esc(c)}"></i>`).join('')}</div><div class="dim" style="font-size:11.5px">${esc(s.tags.slice(0, 4).join(' · '))}</div></div>`).join('')}</div>`, { wide: true, onClose: paint });
        $$('.scard', m.el).forEach(c => c.onclick = () => { const id = c.dataset.s; if (D.prefer.includes(id)) D.prefer = D.prefer.filter(x => x !== id); else if (D.prefer.length < 2) D.prefer.push(id); else { V.toast('Maksymalnie 2 preferowane style', 'err'); return; } c.classList.toggle('on'); }); };
      $('#pGo', body).onclick = e => V.busy(e.currentTarget, async () => { saveForm(); const goal = D.form.goal.trim(); if (!goal) { V.toast('Opisz, o czym jest film', 'err'); return; }
        await V.api('director_plan', { project: pid, goal, tone: D.form.tone, ...(D.form.platform ? { platform: D.form.platform } : {}), ...(D.form.format ? { format: D.form.format } : {}), ...(D.form.creative_profile ? { creative_profile: D.form.creative_profile } : {}), ...(D.form.text_mode ? { text_mode: D.form.text_mode } : {}), ...(D.prefer.length ? { prefer: D.prefer } : {}) });
        await load(); paint(); V.toast('Plan gotowy', 'ok'); });
      // assety
      const q = $('#aQ', body);
      const search = () => V.busy($('#aGo', body), async () => { D.results = await V.api('assets_search', { query: q.value.trim(), source: $('#aSrc', body).value, limit: 18 }); paint(); });
      $('#aGo', body).onclick = search; q.onkeydown = e => { if (e.key === 'Enter') search(); };
      $$('[data-add]', body).forEach(b => b.onclick = () => V.busy(b, async () => { const r = D.results.results[+b.dataset.add]; const a = await V.api('assets_add', { project: pid, ref: r.id });
        await load(); paint(); V.toast(`Dodano ${a.file}`, 'ok'); showSnippet(a.file, a.snippet); }));
      $('#gGo', body).onclick = e => V.busy(e.currentTarget, async () => { const a = await V.api('assets_generate', { project: pid, kind: $('#gKind', body).value, seed: +$('#gSeed', body).value || 1 }); await load(); paint(); V.toast(`Wygenerowano ${a.file}`, 'ok'); });
      $$('[data-code]', body).forEach(b => b.onclick = () => V.busy(b, async () => { const s = await V.api('assets_snippet', { project: pid, file: b.dataset.code }); showSnippet(b.dataset.code, s); }));
      $$('[data-rm]', body).forEach(b => b.onclick = () => { if (!confirm(`Usunąć ${b.dataset.rm}?`)) return; V.busy(b, async () => { await V.api('assets_remove', { project: pid, file: b.dataset.rm }); await load(); paint(); }); });
    };
    const showSnippet = (file, s) => {
      const m = V.modal(`<h3>${esc(file)}</h3><p class="muted" style="margin:4px 0 10px;font-size:13px">${esc(s.note || '')}</p><div class="code" style="max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all">${esc(s.html)}</div>
        <div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn ghost" id="sAsk">Poproś agenta o wstawienie</button><button class="btn primary" id="sCopy">${V.icon('copy')} Kopiuj kod</button></div>`);
      $('#sCopy', m.el).onclick = () => V.copy(s.html);
      $('#sAsk', m.el).onclick = e => askAgent(`Projekt ${pid}: wstaw asset ${file} w odpowiednim bicie sceny (kod: assets_snippet). Dopasuj rozmiar (6-12% szerokości kadru), kolor przez CSS color i wejście z opóźnieniem.`, e.currentTarget).then(m.close);
    };

    return { render: async () => { const body = $('#pbody', host); if (!isActive()) return; if (!D.latest && !D.state) body.innerHTML = '<div class="skel" style="height:320px"></div>';
      try { await load(); } catch (e) { if (isActive()) body.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; } paint(); },
      refresh: async () => { if (!isActive()) return; try { await load(); paint(); } catch { /* następne odświeżenie */ } } };
  };
})();
