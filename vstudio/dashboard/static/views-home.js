/* Widoki: Start (home) i Biblioteka szablonów + modal nowego projektu. */
'use strict';
(() => {
  const { esc, $, $$ } = V;

  const nextStep = s => {
    let m;
    if ((m = s.match(/^([a-z0-9._-]+\/[a-z0-9._-]+):/))) return { icon: 'shield', href: `#/p/${m[1]}`, label: 'Otwórz projekt', text: s };
    if (/środowisko/i.test(s)) return { icon: 'alert', href: '#/onboarding', label: 'Diagnostyka', text: s };
    if (/profil marki/i.test(s)) return { icon: 'spark', href: '#/onboarding', label: 'Uzupełnij', text: s };
    if (/zadań dla agenta/i.test(s)) return { icon: 'bot', href: '#/agent', label: 'Zobacz', text: s };
    if (/pierwszy film/i.test(s)) return { icon: 'film', href: '#/library', label: 'Szablony', text: s };
    return { icon: 'spark', href: '#/', label: '', text: s };
  };

  V.projectCard = p => {
    const c = p.check, [kind, label] = V.verdict(c && c.verdict), pct = p.gates_total ? Math.round(100 * p.gates_done / p.gates_total) : 0;
    return `<a class="card hover tcard" href="#/p/${esc(p.id)}" style="text-decoration:none;color:inherit">
      <div class="thumb" data-thumb="${esc(p.id)}"></div>
      <div class="body"><div class="row"><h3 style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.slug)}</h3><span class="chip ${kind}">${c ? esc(label) + ' · ' + c.score : esc(label)}</span></div>
      <div class="row wrap"><span class="chip">${p.size[0]}×${p.size[1]}</span><span class="chip">${p.duration} s</span><span class="chip">${esc(p.brand)}</span>${p.director && p.director.state === 'approved' ? '<span class="chip ok" title="Reżyser zatwierdził tę wersję">🎬 zatwierdzone</span>' : p.director && p.director.state === 'rejected' ? '<span class="chip err" title="Reżyser odrzucił tę wersję">🎬 odrzucone</span>' : ''}</div>
      <div class="pbar" title="Bramki jakości ${p.gates_done}/${p.gates_total}"><i style="width:${pct}%"></i></div></div></a>`;
  };
  V.mountThumbs = root => $$('[data-thumb]', root).forEach(el => { const p = V.project(el.dataset.thumb); if (p) V.thumb(el, V.srcOf(p.id), p.size[0], p.size[1], Math.min(p.duration * 0.45, p.duration - 0.1)); });

  V.views.home = async host => {
    const st = await V.refreshStatus(); await V.refreshProjects();
    const brand = st.brand ? `, ${esc(st.brand)}` : '';
    const steps = st.next.map(nextStep);
    const a = V.S.pulse && V.S.pulse.agent;
    V.crumbs(['Start']);
    host.innerHTML = `<div class="page">
      <section class="hero">
        <div class="chip grad" style="margin-bottom:10px">Studio filmowe z nadzorem jakości</div>
        <h1>Co dziś tworzymy${brand}?</h1>
        <p>Opisz film, a agent zbuduje scenę; nadzorca sprawdzi każdą klatkę. Albo zacznij od gotowego szablonu i popraw go sam.</p>
        <div class="row" style="align-items:stretch;gap:12px;flex-wrap:wrap">
          <textarea id="ask" placeholder="np. 7-sekundowa pętla dla sklepu z kawą: ziarno zamienia się w filiżankę, na końcu napis „Nowa paleniarnia”." style="flex:1;min-width:280px;min-height:92px"></textarea>
          <div class="col" style="width:210px">
            <select id="askProj"><option value="">Nowy projekt (agent wybierze)</option>${V.S.projects.map(p => `<option value="${esc(p.id)}">${esc(p.id)}</option>`).join('')}</select>
            <button class="btn primary" id="askBtn">${V.icon('send')} Poproś agenta</button>
            <a class="btn" href="#/library">${V.icon('grid')} Wybierz szablon</a>
          </div>
        </div>
        <div class="dim" style="margin-top:10px;font-size:12.5px" id="askHint">${a && a.connected ? 'Agent jest połączony i zobaczy zadanie od razu.' : 'Agent nie jest jeszcze połączony: zadanie poczeka w kolejce. <a href="#/agent">Podłącz agenta</a>.'}</div>
      </section>

      ${steps.length ? `<h2 style="margin:26px 0 12px">Co dalej</h2><div class="grid c2">${steps.map(s => `<div class="step"><div class="ico">${V.icon(s.icon)}</div><div style="flex:1">${esc(s.text)}</div>${s.label ? `<a class="btn sm" href="${esc(s.href)}">${esc(s.label)}</a>` : ''}</div>`).join('')}</div>` : ''}

      <div class="row" style="margin:28px 0 12px"><h2 style="flex:1">Projekty</h2><a class="btn sm" href="#/library">${V.icon('plus')} Nowy</a></div>
      ${V.S.projects.length ? `<div class="grid auto" id="pgrid">${V.S.projects.map(V.projectCard).join('')}</div>` : `<div class="card empty"><div class="glyph">🎬</div><div>Nie ma jeszcze żadnego filmu.</div><div style="margin-top:12px"><a class="btn primary" href="#/library">Zacznij od szablonu</a></div></div>`}

      <h2 style="margin:30px 0 12px">Aktywność</h2><div class="feed" id="homeFeed"></div>
    </div>`;
    V.mountThumbs(host);
    const feed = async () => { const r = await V.api('activity_tail', { limit: 8 }); $('#homeFeed', host).innerHTML = V.feedRows(r.events.slice().reverse()) || '<div class="dim">Brak aktywności. Gdy agent albo dashboard coś zrobi, zobaczysz to tutaj.</div>'; };
    feed().catch(() => {});
    const off = V.on('pulse', ({ p }) => { if (p.events.length) feed().catch(() => {}); });
    $('#askBtn', host).onclick = e => V.busy(e.currentTarget, async () => {
      const prompt = $('#ask', host).value.trim(); if (!prompt) { V.toast('Napisz, co ma powstać', 'err'); return; }
      const project = $('#askProj', host).value || undefined;
      const r = await V.api('task_create', { prompt, project }); $('#ask', host).value = '';
      V.toast(`Zadanie ${r.task.id} czeka na agenta`, 'ok'); V.refreshStatus();
    });
    return () => { off(); $$('[data-thumb]', host).forEach(el => el._dispose && el._dispose()); };
  };

  V.feedRows = evs => evs.map(e => `<div class="ev-row"><span class="dim mono">${V.clock(e.ts)}</span><span><span class="dot ${e.ok ? 'ok' : 'err'}" style="animation:none;display:inline-block;margin-right:8px"></span><span class="nm">${esc(e.name)}</span> <span class="chip" style="margin-left:6px">${esc(e.source)}</span>${typeof e.project === 'string' && e.project ? ` <span class="dim" style="font-size:12px">${esc(e.project.split('/').pop())}</span>` : ''}</span><span class="dim mono" style="font-size:12px">${e.ms != null ? e.ms + ' ms' : ''}</span>${e.summary ? `<span class="sm" title="${esc(e.summary)}">${esc(e.summary)}</span>` : ''}</div>`).join('');

  /* ---------- Biblioteka ---------- */
  V.views.library = async host => {
    V.crumbs(['Biblioteka szablonów']);
    host.innerHTML = `<div class="page"><div class="page-head"><div style="flex:1"><h1>Biblioteka szablonów</h1><p>Osiem gotowych scen. Najedź kursorem, żeby zobaczyć animację. Każdy szablon jest zwykłym plikiem HTML, który agent (albo Ty) może dowolnie zmienić.</p></div></div><div class="grid auto" id="tgrid">${'<div class="card skel" style="height:320px"></div>'.repeat(4)}</div></div>`;
    const { templates } = await V.api('templates_list');
    $('#tgrid', host).innerHTML = templates.map(t => `<div class="card hover tcard" data-t="${esc(t.id)}">
      <div data-tt="${esc(t.id)}"></div>
      <div class="body"><h3>${esc(t.title)}</h3><p>${esc(t.summary)}</p><div class="dim" style="font-size:12.5px">Do: ${esc(t.use_for)}</div>
      <div class="row wrap">${t.tags.map(g => `<span class="chip">${esc(g)}</span>`).join('')}<span class="chip">${t.size[0]}×${t.size[1]}</span><span class="chip">${t.duration} s</span>${t.loop ? '<span class="chip ok">pętla</span>' : ''}${t.needs_network ? '<span class="chip warn" title="Wymaga sieci (CDN) albo lokalnej kopii: vendor_add">CDN</span>' : ''}</div>
      <div style="flex:1"></div><button class="btn primary" data-use="${esc(t.id)}">${V.icon('plus')} Użyj szablonu</button></div></div>`).join('');
    templates.forEach(t => V.thumb($(`[data-tt="${t.id}"]`, host), `/template/${t.id}/`, t.size[0], t.size[1], t.poster_t));
    $$('[data-use]', host).forEach(b => b.onclick = () => V.newProjectModal(templates.find(t => t.id === b.dataset.use)));
    return () => $$('.thumb', host).forEach(el => el._dispose && el._dispose());
  };

  V.newProjectModal = (tpl, opts = {}) => {
    const prof = V.S.profile || {};
    const m = V.modal(`<h2>${tpl ? 'Nowy film z szablonu' : 'Nowy film'}</h2><p class="muted" style="margin:4px 0 16px">${tpl ? esc(tpl.title) + ': ' + esc(tpl.summary) : 'Pusty projekt ze startowym szablonem.'}</p>
      <div class="col">
        <label class="f">Nazwa projektu<input type="text" id="np_slug" placeholder="np. promocja-wiosna" value="${esc(opts.slug || (tpl ? tpl.id : ''))}"></label>
        <label class="f">Marka<input type="text" id="np_brand" value="${esc(opts.brand || prof.name || '')}" placeholder="np. Moja Marka"></label>
        <label class="f">Brief (po co ten film, dla kogo)<textarea id="np_brief" placeholder="Jednym zdaniem: cel i odbiorca."></textarea></label>
        <div class="row" style="justify-content:flex-end;margin-top:6px"><button class="btn ghost" id="np_cancel">Anuluj</button><button class="btn primary" id="np_ok">Utwórz projekt</button></div>
      </div>`);
    $('#np_cancel', m.el).onclick = m.close;
    $('#np_ok', m.el).onclick = e => V.busy(e.currentTarget, async () => {
      const slug = $('#np_slug', m.el).value.trim(), brand = $('#np_brand', m.el).value.trim(), brief = $('#np_brief', m.el).value.trim();
      if (!slug) { V.toast('Podaj nazwę projektu', 'err'); return; }
      const r = await V.api('project_create', { slug, brand: brand || undefined, template: tpl ? tpl.id : undefined, brief: brief || undefined });
      m.close(); await V.refreshProjects(); V.toast('Projekt utworzony', 'ok'); V.go(`#/p/${r.project.id}`);
    });
    setTimeout(() => $('#np_slug', m.el).focus(), 30);
  };
})();
