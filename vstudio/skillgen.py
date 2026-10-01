"""Generator skilla dla agenta (skills/vstudio/SKILL.md) z rejestru możliwości.

Tabela narzędzi, kody znalezisk i pętla pracy pochodzą z kodu (rejestr, REMEDIES, knowledge), więc skill nie może się rozjechać
z tym, co serwer MCP faktycznie wystawia. Test porównuje plik w repo z wynikiem `render()`; odśwież: `vstudio skill --write`.
"""
from __future__ import annotations

from . import director, knowledge, registry
from .supervisor import REMEDIES


def _param_sig(cap) -> str:
    bits = []
    for k, spec in cap.params.items():
        bits.append(f"`{k}`" + ("" if k in cap.required else "?"))
    return ", ".join(bits) or "-"


def tools_table() -> str:
    rows = []
    for cat, label in registry.CATEGORIES:
        caps = [c for c in registry.REGISTRY.values() if c.category == cat]
        if not caps:
            continue
        rows.append(f"### {label}\n")
        rows.append("| Narzędzie | Parametry | Do czego |")
        rows.append("| --- | --- | --- |")
        for c in caps:
            flags = (" (zmienia pliki)" if c.mutates else "") + (" (job)" if c.job else "") + (" (obrazy)" if c.images else "")
            rows.append(f"| `{c.name}` | {_param_sig(c)} | {c.summary}{flags} |")
        rows.append("")
    return "\n".join(rows)


AGENT_TOOLS = ["Read", "mcp__vstudio__director_review", "mcp__vstudio__director_latest", "mcp__vstudio__director_signoff", "mcp__vstudio__frames_view",
               "mcp__vstudio__filmstrip", "mcp__vstudio__timeline_get", "mcp__vstudio__check_run", "mcp__vstudio__check_latest", "mcp__vstudio__project_get",
               "mcp__vstudio__knowledge_get", "mcp__vstudio__scene_read", "mcp__vstudio__style_get", "mcp__vstudio__check_explain"]


def render_agent() -> str:
    """Subagent Claude Code `vstudio-director`: surowy recenzent z własnym kontekstem i BEZ narzędzi do edycji sceny (niezależność oceny)."""
    items = "\n".join(f"   - `{k}`: {v}" for k, v in director.CHECKLIST.items())
    return f"""---
name: vstudio-director
description: Strict film director and QA reviewer for vstudio videos. Use proactively BEFORE telling the user a video is ready and before a final render or delivery. It reviews pacing, hook, variety, motion, text rendering and assets with the vstudio MCP tools, then signs the film off or sends it back with concrete fixes. It never edits the scene.
tools: {", ".join(AGENT_TOOLS)}
model: inherit
---

You are the director and the last line of defence between a film and the user. You review; you do not build. You have no tools to edit the scene on purpose:
your judgement must stay independent of the person who made the film.

## Procedure

1. `director_latest` for the project: read the plan (styles, beats, contract) and the sign-off state.
2. `check_run` (standard). If the supervisor verdict is `blocked`, stop: send the film back with the findings. Technical errors come before taste.
3. `director_review` (standard; `deep` for films up to 20 s). It returns a filmstrip and a rhythm chart (green lines: new situations, red areas: gaps).
4. LOOK. Study the images, then call `frames_view` at: 0.3 s and 0.9 s (the hook), the middle of every beat in the plan, the strongest transition, and the last second.
   Read every text on screen for spelling (Polish letters!), cut-off words and legibility at phone size. Judge hierarchy, spacing, colour, icon style and whether each beat
   shows something NEW.
5. Decide against the checklist, honestly:
{items}
6. Sign off with `director_signoff`:
   - all items hold and no errors: `approve: true`, `notes` naming what you saw with timestamps (at least two specifics), `checklist` all true,
     `accept: {{CODE: reason}}` only for warnings the brief justifies;
   - anything fails: `approve: false` and `notes` listing what to change, at which time, in priority order.
7. Reply to the caller with the decision first, then at most 6 bullets. Do not soften a rejection and do not fix the film yourself.

## Standards

- A finding of code ERROR can never be accepted. A warning is accepted only when the brief demands it (for example a deliberate quiet opening) and the reason says so.
- Never tick a checklist item you did not verify on frames. Never approve because the score is high: the score measures what is measurable, you judge the rest.
- Be specific: "3.2-6.0 s is one static layout; add a layout change at 4.5 s (device mock to icon grid)" beats "pacing could be better".
- Variety without chaos: brand colours, font and logo stay constant; layout, background, motion language and transition change between beats.
- A film you would scroll past on a phone is not approved.
"""


def render() -> str:
    codes = "\n".join(f"- `{code}`: {fix}" for code, (_title, fix) in REMEDIES.items())
    dcodes = "\n".join(f"- `{code}`: {fix}" for code, (_title, fix) in director.REMEDIES.items())
    return f"""---
name: vstudio
description: Generate, supervise and deliver code-rendered videos and motion graphics with the vstudio studio (deterministic HTML scenes rendered via Playwright/FFmpeg). Use when the user wants a video, animation, motion graphic, product demo or reel made, edited, checked or rendered, or when a vstudio MCP server is connected.
---

# vstudio: studio filmowe dla agenta

vstudio to deterministyczne studio: film to strona HTML, w której obraz jest czystą funkcją czasu. Ty piszesz scenę, a studio
**pilnuje jakości**: po każdej zmianie nadzorca (`check_run`) sprawdza błędy, klatki, pętlę, determinizm, czytelność i kontrast
i mówi, co poprawić. Użytkownik widzi to samo w dashboardzie (`python vstudio.py dashboard`).

## Połączenie

Serwer MCP: `python vstudio.py mcp` (stdio). Z poziomu dashboardu: Agent → Połącz. Albo: `claude mcp add vstudio -- python vstudio.py mcp`.
Zacznij od `studio_status`: mówi, czy środowisko działa, czy jest profil marki i co robić dalej.

## Pętla pracy

{knowledge.WORKFLOW}
## Zasady sceny

{knowledge.CONTRACT}
{knowledge.GSAP}
## Narzędzia

Każde narzędzie jest zarejestrowane w jednym miejscu (`vstudio/registry.py`); ta tabela jest generowana.

{tools_table()}
## Reżyser: film ma być ładny, dynamiczny i sprawdzony zanim trafi do użytkownika

Nadzorca (`check_run`) odpowiada za poprawność techniczną. **Reżyser** odpowiada za to, co widzi widz: plan stylu i storyboard
(`director_plan`), przegląd rytmu, haka, różnorodności, ruchu, widoczności tekstu i fontów (`director_review`) oraz zatwierdzenie
(`director_signoff`). Finalny render i wydanie **nie wystartują** bez zatwierdzenia aktualnej wersji sceny. Najlepiej oddaj przegląd
subagentowi `vstudio-director` (świeże oczy, bez narzędzi do edycji). Assety (ikony, grafiki, obrazy) bierz z `assets_search` / `assets_add` /
`assets_generate`. Zasady rzemiosła: `knowledge_get topic=direction`, style: `topic=styles`, assety: `topic=assets`.

{knowledge.DIRECTION}
## Kody znalezisk nadzorcy

{codes}

## Kody znalezisk reżysera

{dcodes}

## Zasady pracy

- Patrz na klatki (`frames_view`), nie zgaduj z kodu: początek, główny moment, najszybsze przejście, koniec.
- Nie twierdź, że film jest gotowy bez werdyktu `pass`, zatwierdzenia reżysera (`director_signoff`) i jawnej notatki o świadomie zostawionych ostrzeżeniach.
- Nie zostawiaj bitów samego tekstu: dodaj ikonę, naklejkę albo grafikę (`assets_search`, `assets_generate`). Zmieniaj wygląd co 2-3 s, marka zostaje stała.
- Nie wymyślaj kolorów ani fontów: bierz z `knowledge_get topic=brand`.
- Edytuj sceny przez `scene_write` / `scene_patch` (zachowują historię, `scene_restore` cofa). Nie nadpisuj `src/index.html` inaczej.
- Po 6 rundach bez postępu zatrzymaj się i zapytaj użytkownika. Nic nie publikuj bez jego wyraźnej zgody.
"""
