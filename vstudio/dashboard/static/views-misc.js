/* Widoki: Mapa możliwości i Onboarding (środowisko, marka, agent, pierwszy film). */
'use strict';
(() => {
  const { esc, $, $$ } = V;

  /* ---------- Mapa możliwości ---------- */
  V.views.map = async host => {
    V.crumbs(['Mapa możliwości']);
    const data = await V.get('/api/capabilities'); const caps = data.capabilities;
    host.innerHTML = `<div class="page"><div class="page-head"><div style="flex:1"><h1>Mapa możliwości</h1><p>Wszystko, co studio potrafi: <b>${caps.length} operacji</b> w jednym rejestrze. Te same operacje ma agent (MCP), ten dashboard i CLI, więc nic się nie rozjeżdża. Dokumentacja i skill generują się stąd.</p></div><input type="text" id="q" placeholder="Szukaj operacji…" style="max-width:280px"></div><div id="caps"></div></div>`;
    const draw = q => {
      q = (q || '').toLowerCase();
      $('#caps', host).innerHTML = data.categories.map(c => {
        const list = caps.filter(x => x.category === c.id && (!q || (x.name + ' ' + x.title + ' ' + x.summary).toLowerCase().includes(q)));
        if (!list.length) return '';
        return `<h2 style="margin:22px 0 10px">${esc(c.title)} <span class="dim" style="font-size:13px;font-weight:500">${list.length}</span></h2><div class="col" style="gap:8px">${list.map(x => `<details class="card cap"><summary><span class="mono" style="color:var(--a1);min-width:150px">${esc(x.name)}</span><span style="flex:1">${esc(x.title)}</span>${x.mutates ? '<span class="chip warn">zmienia pliki</span>' : '<span class="chip">odczyt</span>'}${x.job ? '<span class="chip info">job</span>' : ''}${x.images ? '<span class="chip ok">obrazy</span>' : ''}</summary>
          <div style="margin-top:10px" class="col"><div class="muted">${esc(x.summary)}</div>${x.when ? `<div><span class="chip grad">kiedy</span> <span class="muted">${esc(x.when)}</span></div>` : ''}${x.returns ? `<div class="dim" style="font-size:13px">Zwraca: ${esc(x.returns)}</div>` : ''}
          ${Object.keys(x.params).length ? `<table class="t"><tr><th>Parametr</th><th>Typ</th><th>Opis</th></tr>${Object.entries(x.params).map(([k, s]) => `<tr><td class="mono">${esc(k)}${x.required.includes(k) ? ' <span class="chip err">wymagany</span>' : ''}</td><td class="mono dim">${esc(s.type || '')}${s.enum ? ' (' + esc(s.enum.join(' | ')) + ')' : ''}</td><td class="muted">${esc(s.description || '')}${'default' in s ? ` Domyślnie: <span class="mono">${esc(JSON.stringify(s.default))}</span>` : ''}</td></tr>`).join('')}</table>` : '<div class="dim">Bez parametrów.</div>'}
          ${!x.required.length && !x.mutates && !x.job ? `<div><button class="btn sm" data-try="${esc(x.name)}">Wypróbuj</button></div><div class="code" data-out="${esc(x.name)}" hidden></div>` : ''}</div></details>`).join('')}</div>`;
      }).join('') || '<div class="empty">Brak pasujących operacji.</div>';
      $$('[data-try]', host).forEach(b => b.onclick = () => V.busy(b, async () => { const r = await V.api(b.dataset.try, {}); const o = $(`[data-out="${b.dataset.try}"]`, host); o.hidden = false; o.textContent = JSON.stringify(r, null, 1).slice(0, 4000); }));
    };
    draw(''); $('#q', host).oninput = e => draw(e.target.value);
  };

  /* ---------- Onboarding ---------- */
  const FONTS = ['Inter', 'Manrope', 'Poppins', 'DM Sans', 'Playfair Display', 'system-ui'];
  V.views.onboarding = async host => {
    V.crumbs(['Onboarding']);
    let step = 0, prof = { ...(V.S.profile || {}) }, pal = { ...(prof.palette || { bg: '#0B0E24', ink: '#F4F6FF', accent: '#FF6B4A', accent2: '#4F8CFF' }) };
    const STEPS = ['Środowisko', 'Marka', 'Agent', 'Pierwszy film'];
    const shell = inner => `<div class="page" style="max-width:860px"><div class="stepper">${STEPS.map((_, i) => `<div class="s ${i <= step ? 'on' : ''}"></div>`).join('')}</div>
      <div class="dim" style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px">Krok ${step + 1} z ${STEPS.length}: ${STEPS[step]}</div>${inner}</div>`;
    const nav = (back, next, nextLabel = 'Dalej') => `<div class="row" style="justify-content:space-between;margin-top:22px">${back ? '<button class="btn ghost" id="obBack">← Wstecz</button>' : '<span></span>'}<div class="row"><button class="btn ghost" id="obSkip">Pomiń onboarding</button>${next ? `<button class="btn primary" id="obNext">${nextLabel}</button>` : ''}</div></div>`;
    const wire = onNext => { const b = $('#obBack', host); if (b) b.onclick = () => { step--; draw(); }; $('#obSkip', host).onclick = () => V.go('#/'); const n = $('#obNext', host); if (n) n.onclick = async e => { if (onNext) { try { await V.busy(e.currentTarget, onNext); } catch { return; } } step++; draw(); }; };

    const draw = async () => {
      if (step === 0) {
        host.innerHTML = shell('<h1>Sprawdzam środowisko</h1><p class="muted">Studio potrzebuje Pythona, Chromium (render klatek) i FFmpeg (wideo i dźwięk).</p><div class="checks" id="checks"><div class="skel" style="height:200px"></div></div>' + nav(false, true));
        wire(); const r = await V.api('doctor', {});
        $('#checks', host).innerHTML = r.checks.map(c => `<div class="c"><span class="dot ${c.ok ? 'ok' : c.level === 'warn' ? 'warn' : 'err'}" style="animation:none"></span><b style="min-width:210px">${esc(c.check)}</b><span class="muted mono" style="font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(c.detail)}">${esc(c.detail)}</span></div>`).join('') + (r.ok ? '<div class="chip ok" style="margin-top:10px;align-self:flex-start">Środowisko gotowe</div>' : '<div class="card pad" style="margin-top:10px;border-color:rgba(255,107,129,.4)">Brakuje wymaganych elementów (czerwone). Bez FFmpeg nadal możesz tworzyć i sprawdzać sceny; nie wyrenderujesz wideo.</div>');
      } else if (step === 1) {
        host.innerHTML = shell(`<h1>Twoja marka</h1><p class="muted">Agent użyje tych wartości zamiast wymyślać kolory i fonty.</p>
          <div class="grid c2" style="align-items:start"><div class="col">
            <label class="f">Nazwa marki<input type="text" id="pName" value="${esc(prof.name || '')}" placeholder="np. Kawiarnia Ziarno"></label>
            <div class="row wrap" style="gap:12px">${[['bg', 'Tło'], ['ink', 'Tekst'], ['accent', 'Akcent'], ['accent2', 'Akcent 2']].map(([k, l]) => `<label class="f" style="align-items:flex-start">${l}<input type="color" data-pal="${k}" value="${esc(pal[k])}"></label>`).join('')}</div>
            <label class="f">Font<select id="pFont">${FONTS.map(f => `<option ${f === (prof.font || 'Inter') ? 'selected' : ''}>${f}</option>`).join('')}</select></label>
            <label class="f">Ton komunikacji<input type="text" id="pTone" value="${esc(prof.tone || '')}"></label>
            <label class="f">Odbiorcy<input type="text" id="pAud" value="${esc(prof.audience || '')}" placeholder="np. kawosze 25-40, Instagram"></label>
            <label class="f">Domyślny format<div class="seg" id="pFmt">${['9:16', '4:5', '1:1', '16:9'].map(f => `<button data-f="${f}" class="${f === (prof.default_format || '4:5') ? 'on' : ''}">${f}</button>`).join('')}</div></label></div>
          <div><div class="swatch" id="sw"><div style="font-size:11px;letter-spacing:.1em;opacity:.7" id="swA">NOWOŚĆ</div><div style="font-size:26px;font-weight:800;line-height:1.1;margin-top:4px" id="swT">Twój film zaczyna się tutaj</div><div style="margin-top:10px;display:flex;gap:8px"><i id="swC1" style="width:46px;height:8px;border-radius:8px"></i><i id="swC2" style="width:26px;height:8px;border-radius:8px"></i></div></div><div class="dim" style="font-size:12.5px;margin-top:8px">Podgląd palety i fontu.</div></div></div>` + nav(true, true, 'Zapisz i dalej'));
        const paint = () => { const sw = $('#sw', host); sw.style.background = pal.bg; sw.style.color = pal.ink; sw.style.fontFamily = `"${$('#pFont', host).value}", system-ui, sans-serif`; $('#swC1', host).style.background = pal.accent; $('#swC2', host).style.background = pal.accent2; $('#swA', host).style.color = pal.accent; $('#swT', host).textContent = ($('#pName', host).value || 'Twój film') + ' zaczyna się tutaj'; };
        $$('[data-pal]', host).forEach(i => i.oninput = () => { pal[i.dataset.pal] = i.value; paint(); }); $('#pFont', host).onchange = paint; $('#pName', host).oninput = paint;
        $$('#pFmt button', host).forEach(b => b.onclick = () => { $$('#pFmt button', host).forEach(x => x.classList.toggle('on', x === b)); }); paint();
        wire(async () => { const name = $('#pName', host).value.trim(); if (!name) { V.toast('Podaj nazwę marki', 'err'); throw new Error('brak nazwy'); }
          prof = await V.api('profile_set', { name, palette: pal, font: $('#pFont', host).value, tone: $('#pTone', host).value || undefined, audience: $('#pAud', host).value || undefined, default_format: $('#pFmt .on', host).dataset.f }); V.S.profile = prof; await V.refreshStatus(); });
      } else if (step === 2) {
        host.innerHTML = shell('<h1>Połącz agenta</h1><p class="muted">Agent (np. Claude Code) dostanie narzędzia studia. Możesz to zrobić teraz albo później w zakładce Agent.</p><div id="connect"><div class="skel" style="height:280px"></div></div>' + nav(true, true));
        wire(); V.connectCard(await V.api('agent_connect_info', {}), $('#connect', host));
      } else {
        const { templates } = await V.api('templates_list'); const pick = templates.filter(t => ['hide-the-cut', 'one-hero-one-world', 'three-colours-only'].includes(t.id));
        host.innerHTML = shell(`<h1>Pierwszy film</h1><p class="muted">Wybierz szablon albo opisz film agentowi.</p><div class="grid c3">${pick.map(t => `<div class="card hover tcard"><div data-tt="${esc(t.id)}"></div><div class="body"><h3>${esc(t.title)}</h3><p>${esc(t.use_for)}</p><button class="btn primary" data-use="${esc(t.id)}">Użyj</button></div></div>`).join('')}</div>
          <div class="card pad" style="margin-top:16px"><h3 style="margin-bottom:8px">Albo opisz film agentowi</h3><textarea id="obAsk" placeholder="O czym ma być film i dla kogo?"></textarea><button class="btn" id="obSend" style="margin-top:8px">${V.icon('send')} Wyślij do agenta</button></div>` + nav(true, false));
        wire(); pick.forEach(t => V.thumb($(`[data-tt="${t.id}"]`, host), `/template/${t.id}/`, t.size[0], t.size[1], t.poster_t));
        $$('[data-use]', host).forEach(b => b.onclick = () => V.newProjectModal(templates.find(t => t.id === b.dataset.use)));
        $('#obSend', host).onclick = e => V.busy(e.currentTarget, async () => { const prompt = $('#obAsk', host).value.trim(); if (!prompt) { V.toast('Opisz film', 'err'); return; } await V.api('task_create', { prompt }); V.toast('Zadanie czeka na agenta', 'ok'); V.go('#/agent'); });
      }
    };
    draw(); return () => $$('.thumb', host).forEach(el => el._dispose && el._dispose());
  };
})();
