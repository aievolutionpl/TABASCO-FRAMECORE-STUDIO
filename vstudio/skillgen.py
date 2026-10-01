"""Generator skilla dla agenta (skills/vstudio/SKILL.md) z rejestru możliwości.

Tabela narzędzi, kody znalezisk i pętla pracy pochodzą z kodu (rejestr, REMEDIES, knowledge), więc skill nie może się rozjechać
z tym, co serwer MCP faktycznie wystawia. Test porównuje plik w repo z wynikiem `render()`; odśwież: `vstudio skill --write`.
"""
from __future__ import annotations

from . import knowledge, registry
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


def render() -> str:
    codes = "\n".join(f"- `{code}`: {fix}" for code, (_title, fix) in REMEDIES.items())
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
## Kody znalezisk nadzorcy

{codes}

## Zasady pracy

- Patrz na klatki (`frames_view`), nie zgaduj z kodu: początek, główny moment, najszybsze przejście, koniec.
- Nie twierdź, że film jest gotowy bez werdyktu `pass` albo jawnej notatki o świadomie zostawionym ostrzeżeniu.
- Nie wymyślaj kolorów ani fontów: bierz z `knowledge_get topic=brand`.
- Edytuj sceny przez `scene_write` / `scene_patch` (zachowują historię, `scene_restore` cofa). Nie nadpisuj `src/index.html` inaczej.
- Po 6 rundach bez postępu zatrzymaj się i zapytaj użytkownika. Nic nie publikuj bez jego wyraźnej zgody.
"""
