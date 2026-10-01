/* Widok Agent: połączenie (MCP + skill), prośby do agenta, tablica zadań i aktywność na żywo. */
'use strict';
(() => {
  const { esc, $, $$ } = V;

  V.connectCard = (info, host) => {
    const a = info.agent, cmd = info.claude_code, json = JSON.stringify(info.mcp_json, null, 2);
    host.innerHTML = `<div class="card pad">
      <div class="row" style="margin-bottom:12px"><span class="dot ${a.connected ? 'ok' : ''}"></span><h3 style="flex:1">${a.connected ? 'Agent jest połączony' : 'Agent niepodłączony'}</h3>${a.last_seen ? `<span class="dim">ostatnie wywołanie: <span class="mono">${esc(a.last_call)}</span>, ${V.ago(a.last_seen)}</span>` : ''}</div>
      <div class="col" style="gap:14px">
        <div><div class="row" style="margin-bottom:6px"><span class="chip grad">1</span><b>Zainstaluj skill i konfigurację MCP</b></div>
          <div class="muted" style="font-size:13px;margin-bottom:8px">Zapisuje <span class="mono">SKILL.md</span> (instrukcja pracy dla agenta) i wpis <span class="mono">vstudio</span> w <span class="mono">.mcp.json</span> tego repozytorium.</div>
          <div class="row"><button class="btn primary" id="cInstall">${V.icon('download')} Zainstaluj</button><span class="chip ${info.mcp_configured ? 'ok' : ''}">${info.mcp_configured ? '.mcp.json gotowy' : '.mcp.json brak wpisu'}</span><span class="chip ${info.skill.installed_project ? 'ok' : ''}">${info.skill.installed_project ? 'skill zainstalowany' : 'skill nie zainstalowany'}</span></div></div>
        <div><div class="row" style="margin-bottom:6px"><span class="chip grad">2</span><b>Albo dodaj serwer ręcznie (Claude Code)</b></div>
          <div class="copy"><div class="code" style="padding-right:84px">${esc(cmd)}</div><button class="btn sm" data-copy="cmd">${V.icon('copy')} Kopiuj</button></div></div>
        <div><div class="row" style="margin-bottom:6px"><span class="chip grad">3</span><b>Sprawdź, że serwer startuje</b></div>
          <div class="row"><button class="btn" id="cTest">${V.icon('bot')} Testuj połączenie</button><span id="cTestOut" class="muted"></span></div></div>
        <div class="dim" style="font-size:12.5px">Uruchom agenta w katalogu projektu. Pierwsze wywołanie narzędzia zapali zielony wskaźnik w nagłówku; od tej chwili widzisz tu każdy jego ruch.</div>
      </div></div>`;
    $('[data-copy=cmd]', host).onclick = () => V.copy(cmd);
    $('#cInstall', host).onclick = e => V.busy(e.currentTarget, async () => { const r = await V.api('agent_install', {}); V.toast('Zainstalowano: ' + Object.keys(r.installed).join(', '), 'ok'); V.modal(`<h3>Gotowe</h3><div class="col" style="margin:10px 0">${Object.entries(r.installed).map(([k, v]) => `<div><span class="chip">${esc(k)}</span> <span class="mono muted">${esc(v)}</span></div>`).join('')}</div><p class="muted">${esc(r.note)}</p><details><summary class="muted" style="cursor:pointer">Pokaż JSON konfiguracji</summary><div class="code" style="margin-top:8px">${esc(json)}</div></details>`); if (V.route_ && V.route_.view === 'agent') V.route(); });
    $('#cTest', host).onclick = e => V.busy(e.currentTarget, async () => { const r = await V.api('agent_selftest', {}); $('#cTestOut', host).innerHTML = r.ok ? `<span class="chip ok">działa</span> ${r.tools} narzędzi · protokół ${esc(r.protocol)} · ${r.ms} ms` : `<span class="chip err">błąd</span> ${esc(r.error)}`; });
  };

  V.views.agent = async host => {
    V.crumbs(['Agent']);
    host.innerHTML = `<div class="page"><div class="page-head"><div style="flex:1"><h1>Agent</h1><p>Podłącz agenta (np. Claude Code), a on dostanie narzędzia studia, wiedzę o zasadach i nadzorcę jakości. Ty zlecasz pracę i widzisz, co robi.</p></div></div>
      <div class="grid" style="grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);align-items:start" id="agrid">
        <div class="col" style="gap:16px"><div id="connect"><div class="skel" style="height:300px"></div></div>
          <div class="card pad"><h3 style="margin-bottom:10px">Poproś agenta</h3><textarea id="ask" placeholder="Opisz, co ma zrobić. Agent podejmie zadanie przez narzędzie task_next."></textarea>
            <div class="row" style="margin-top:8px"><select id="askProj" style="flex:1"><option value="">Bez projektu (nowy film)</option>${V.S.projects.map(p => `<option value="${esc(p.id)}">${esc(p.id)}</option>`).join('')}</select><button class="btn primary" id="askBtn">${V.icon('send')} Wyślij</button></div></div>
          <div id="board"></div></div>
        <div class="card pad"><div class="row" style="margin-bottom:10px"><h3 style="flex:1">Aktywność na żywo</h3><span class="chip info">MCP · dashboard · joby</span></div><div class="feed" id="feed"></div></div></div></div>`;
    const loadConnect = async () => V.connectCard(await V.api('agent_connect_info', {}), $('#connect', host));
    const loadBoard = async () => {
      const { tasks } = await V.api('task_list', {}); const col = (s, t) => tasks.filter(x => s.includes(x.status)).reverse();
      const card = t => `<div class="card pad" style="padding:11px 13px"><div class="row"><span class="mono dim">${esc(t.id)}</span>${t.project ? `<a class="chip" href="#/p/${esc(t.project)}">${esc(t.project)}</a>` : ''}<span class="spacer"></span><span class="dim" style="font-size:12px">${V.ago(t.updated)}</span></div><div style="margin-top:6px;font-size:13.5px">${esc(t.prompt)}</div>${t.notes.slice(-2).map(n => `<div class="muted" style="font-size:12.5px;margin-top:4px">↳ ${esc(n.text)}</div>`).join('')}</div>`;
      const colHtml = (title, list, kind) => `<div><div class="row" style="margin-bottom:8px"><b>${title}</b><span class="chip ${kind}">${list.length}</span></div><div class="col" style="gap:8px">${list.map(card).join('') || '<div class="dim" style="font-size:13px">—</div>'}</div></div>`;
      $('#board', host).innerHTML = `<div class="card pad"><h3 style="margin-bottom:12px">Zadania</h3><div class="grid c3" style="gap:12px">${colHtml('Otwarte', col(['open']), '')}${colHtml('W toku', col(['in_progress', 'blocked']), 'info')}${colHtml('Zrobione', col(['done']).slice(0, 5), 'ok')}</div></div>`;
    };
    const loadFeed = async () => { const r = await V.api('activity_tail', { limit: 40 }); $('#feed', host).innerHTML = V.feedRows(r.events.slice().reverse()) || '<div class="empty" style="padding:30px"><div class="glyph">📡</div>Cisza. Gdy agent wywoła pierwsze narzędzie, zobaczysz je tutaj.</div>'; };
    await Promise.all([loadConnect(), loadBoard(), loadFeed()]);
    $('#askBtn', host).onclick = e => V.busy(e.currentTarget, async () => { const prompt = $('#ask', host).value.trim(); if (!prompt) { V.toast('Napisz, co ma zrobić agent', 'err'); return; } const r = await V.api('task_create', { prompt, project: $('#askProj', host).value || undefined }); $('#ask', host).value = ''; V.toast(`Zadanie ${r.task.id} dodane`, 'ok'); loadBoard(); V.refreshStatus(); });
    const off = V.on('pulse', ({ p, prev }) => { if (p.events.length) { loadFeed(); loadBoard(); } if (prev && prev.agent.connected !== p.agent.connected) loadConnect(); });
    return off;
  };
})();
