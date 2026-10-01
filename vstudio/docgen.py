"""Mapa możliwości studia (docs/CAPABILITIES.md) generowana z rejestru: dokumentacja nie może się rozjechać z kodem.

Test `tests/test_studio_agent.py` porównuje plik w repo z wynikiem `render()`. Odśwież: `python vstudio.py tools --write-docs`.
"""
from __future__ import annotations

from pathlib import Path

from . import common, ops, registry  # noqa: F401  (ops wypełnia rejestr)
from .director import REMEDIES as DIRECTOR_REMEDIES
from .supervisor import REMEDIES

DOC_PATH = common.STUDIO / "docs" / "CAPABILITIES.md"


def _params_table(cap) -> str:
    if not cap.params:
        return "_brak parametrów_\n"
    rows = ["| Parametr | Typ | Wymagany | Opis |", "| --- | --- | --- | --- |"]
    for k, spec in cap.params.items():
        typ = spec.get("type", "")
        if "enum" in spec:
            typ += " (" + " \\| ".join(map(str, spec["enum"])) + ")"
        desc = spec.get("description", "")
        if "default" in spec:
            desc = (desc + f" Domyślnie: `{spec['default']}`.").strip()
        rows.append(f"| `{k}` | {typ} | {'tak' if k in cap.required else 'nie'} | {desc} |")
    return "\n".join(rows) + "\n"


def render() -> str:
    caps = list(registry.REGISTRY.values())
    out = ["# Mapa możliwości vstudio", "",
           "> Plik generowany z rejestru możliwości (`vstudio/registry.py`, operacje w `vstudio/ops.py`). Nie edytuj ręcznie: "
           "`python vstudio.py tools --write-docs`.", "",
           f"Studio ma **{len(caps)} operacji** w {len({c.category for c in caps})} kategoriach. Każda z nich jest dostępna tą samą drogą "
           "z trzech powierzchni, bo wszystkie czytają jeden rejestr:", "",
           "| Powierzchnia | Jak | Dla kogo |", "| --- | --- | --- |",
           "| **Serwer MCP** | `python vstudio.py mcp` (stdio): narzędzia, zasoby, prompty | agent (Claude Code i inne klienty MCP) |",
           "| **Dashboard** | `python vstudio.py dashboard`: API `POST /api/call/<operacja>` | człowiek (interfejs w przeglądarce) |",
           "| **CLI** | `python vstudio.py check / tools / skill / vendor / onboard` (+ dotychczasowe komendy potoku) | skrypty, CI |", "",
           "```", "agent (MCP)  ─┐", "dashboard    ─┼─►  registry.call(operacja, args) ─► ops ─► workspace / supervisor / jobs / vendor ─► projekt na dysku",
           "CLI          ─┘            │", "                           └─► activity.jsonl  (feed „co robi agent” w dashboardzie)", "```", "",
           "Legenda: **zmienia pliki** = modyfikuje stan na dysku; **job** = długa operacja w tle (postęp przez `job_get`/`job_wait`); "
           "**obrazy** = wynik zawiera klatki, które MCP oddaje agentowi jako obrazy.", ""]
    for cat, label in registry.CATEGORIES:
        in_cat = [c for c in caps if c.category == cat]
        if not in_cat:
            continue
        out += [f"## {label}", ""]
        for c in in_cat:
            flags = [f for f, on in (("zmienia pliki", c.mutates), ("job", c.job), ("obrazy", c.images)) if on]
            out += [f"### `{c.name}`: {c.title}", "", c.summary, ""]
            if c.when:
                out += [f"**Kiedy:** {c.when}", ""]
            if c.returns:
                out += [f"**Zwraca:** {c.returns}", ""]
            if flags:
                out += ["**Cechy:** " + ", ".join(flags), ""]
            out += [_params_table(c)]
    out += ["## Kody znalezisk nadzorcy", "", "| Kod | Znaczenie | Jak naprawić (wskazówka dla agenta) |", "| --- | --- | --- |"]
    for code, (title, fix) in REMEDIES.items():
        out.append(f"| `{code}` | {title} | {fix} |")
    out += ["", "## Kody znalezisk reżysera", "", "| Kod | Znaczenie | Jak naprawić (wskazówka dla agenta) |", "| --- | --- | --- |"]
    for code, (title, fix) in DIRECTOR_REMEDIES.items():
        out.append(f"| `{code}` | {title} | {fix} |")
    out.append("")
    return "\n".join(out)


def table() -> str:
    rows = []
    for cat, label in registry.CATEGORIES:
        caps = [c for c in registry.REGISTRY.values() if c.category == cat]
        if caps:
            rows.append(f"\n{label}")
            for c in caps:
                flag = ("*" if c.mutates else " ") + ("J" if c.job else " ") + ("I" if c.images else " ")
                rows.append(f"  {c.name:<20}{flag}  {c.summary[:90]}")
    rows.append("\n* zmienia pliki   J job w tle   I zwraca obrazy")
    return "\n".join(rows).lstrip("\n")


def write() -> Path:
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render(), encoding="utf-8")
    return DOC_PATH
