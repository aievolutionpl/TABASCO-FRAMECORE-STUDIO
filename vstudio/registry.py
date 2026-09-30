"""Rejestr możliwości studia: jedno źródło prawdy o tym, co studio potrafi.

Każda operacja (utwórz projekt, sprawdź klatki, wyrenderuj…) jest opisana RAZ: nazwa, kategoria, schemat parametrów,
opis „kiedy użyć”. Z tego opisu powstają wszystkie powierzchnie, więc nie mogą się rozjechać:

  - serwer MCP (`vstudio mcp`)        -> tools/list i tools/call dla podłączonego agenta,
  - API dashboardu (`/api/call/<n>`)   -> te same operacje z interfejsu,
  - docs/CAPABILITIES.md               -> mapa wszystkiego (generowana, test pilnuje aktualności),
  - skills/vstudio/SKILL.md            -> tabela narzędzi dla agenta (generowana).

Handler zwraca zwykły słownik JSON. Jeśli w wyniku jest klucz `images` (lista {path, label}), MCP odda je agentowi jako
obrazy, a dashboard pokaże jako miniatury.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from . import activity, common

CATEGORIES = [
    ("onboarding", "Start i połączenie agenta"),
    ("library", "Biblioteka szablonów"),
    ("projects", "Projekty i bramki jakości"),
    ("scene", "Scena (kod filmu)"),
    ("knowledge", "Wiedza dla agenta"),
    ("inspect", "Podgląd klatek i osi czasu"),
    ("supervise", "Nadzór jakości"),
    ("render", "Render, dźwięk, wydanie"),
    ("agent", "Zadania dla agenta"),
    ("system", "Środowisko i aktywność"),
]

_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


class CapabilityError(Exception):
    """Operacja się nie udała (zły argument, brak projektu, błąd silnika). Komunikat jest dla człowieka i agenta."""


@dataclass
class Capability:
    name: str
    title: str
    summary: str
    category: str
    handler: Callable[..., dict]
    params: dict = field(default_factory=dict)          # nazwa -> schemat JSON pojedynczego parametru
    required: tuple = ()
    returns: str = ""                                    # jednozdaniowy opis wyniku
    when: str = ""                                       # wskazówka dla agenta: kiedy po to sięgnąć
    mutates: bool = False                                # zmienia pliki / stan
    job: bool = False                                    # długa operacja: zwraca job (postęp przez job_get / job_wait)
    images: bool = False                                 # wynik może zawierać obrazy

    def input_schema(self) -> dict:
        return {"type": "object", "properties": self.params, "required": list(self.required), "additionalProperties": False}

    def describe(self) -> dict:
        return {"name": self.name, "title": self.title, "summary": self.summary, "category": self.category, "params": self.params,
                "required": list(self.required), "returns": self.returns, "when": self.when, "mutates": self.mutates,
                "job": self.job, "images": self.images}


REGISTRY: dict[str, Capability] = {}


def capability(name: str, title: str, summary: str, category: str, *, params: dict | None = None, required: tuple = (),
               returns: str = "", when: str = "", mutates: bool = False, job: bool = False, images: bool = False):
    """Dekorator rejestrujący operację. Kolejność rejestracji = kolejność w dokumentacji."""
    if category not in dict(CATEGORIES):
        raise ValueError(f"nieznana kategoria: {category}")

    def deco(fn: Callable[..., dict]):
        if name in REGISTRY:
            raise ValueError(f"operacja już zarejestrowana: {name}")
        REGISTRY[name] = Capability(name, title, summary, category, fn, params or {}, tuple(required), returns, when, mutates, job, images)
        return fn

    return deco


def describe() -> list[dict]:
    return [c.describe() for c in REGISTRY.values()]


def validate(cap: Capability, args: dict) -> dict:
    """Lekka walidacja względem schematu (typy, enum, zakresy, wymagane, nieznane klucze) + domyślne wartości."""
    if not isinstance(args, dict):
        raise CapabilityError("argumenty muszą być obiektem JSON")
    unknown = sorted(set(args) - set(cap.params))
    if unknown:
        raise CapabilityError(f"{cap.name}: nieznane parametry {unknown}; dozwolone: {sorted(cap.params)}")
    out = {}
    for k in cap.required:
        if k not in args or args[k] in (None, ""):
            raise CapabilityError(f"{cap.name}: brakuje wymaganego parametru '{k}'")
    for k, spec in cap.params.items():
        if k not in args or args[k] is None:
            if "default" in spec:
                out[k] = spec["default"]
            continue
        v = args[k]
        t = spec.get("type")
        if t:
            ok = isinstance(v, _TYPES[t]) and not (t in ("integer", "number") and isinstance(v, bool))
            if t == "integer" and isinstance(v, float) and v.is_integer():
                v, ok = int(v), True
            if not ok:
                raise CapabilityError(f"{cap.name}: parametr '{k}' ma być typu {t}, jest {type(v).__name__}")
        if "enum" in spec and v not in spec["enum"]:
            raise CapabilityError(f"{cap.name}: parametr '{k}' ma być jednym z {spec['enum']}")
        if t in ("integer", "number"):
            if "minimum" in spec and v < spec["minimum"]:
                raise CapabilityError(f"{cap.name}: '{k}' musi być >= {spec['minimum']}")
            if "maximum" in spec and v > spec["maximum"]:
                raise CapabilityError(f"{cap.name}: '{k}' musi być <= {spec['maximum']}")
        if t == "array" and "items" in spec and "type" in spec["items"]:
            it = spec["items"]["type"]
            if not all(isinstance(x, _TYPES[it]) and not isinstance(x, bool) for x in v):
                raise CapabilityError(f"{cap.name}: elementy '{k}' mają być typu {it}")
        out[k] = v
    return out


def _brief(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = v if isinstance(v, str) else repr(v)
        parts.append(f"{k}={s[:40]}")
    return ", ".join(parts)[:200]


def call(name: str, args: dict | None = None, *, source: str = "api") -> dict:
    """Wywołuje operację: walidacja, tryb usługowy (błędy jako wyjątki), log aktywności. Zwraca słownik wyniku."""
    cap = REGISTRY.get(name)
    if cap is None:
        raise CapabilityError(f"nieznana operacja '{name}'. Dostępne: {', '.join(sorted(REGISTRY))}")
    args = validate(cap, args or {})
    t0 = time.time()
    project = args.get("project") if isinstance(args.get("project"), str) else None
    try:
        res = cap.handler(**args)
    except CapabilityError as exc:
        activity.record(source, "call", name, project=project, ok=False, ms=int((time.time() - t0) * 1000), summary=f"{_brief(args)} -> {exc}")
        raise
    except common.StudioError as exc:
        activity.record(source, "call", name, project=project, ok=False, ms=int((time.time() - t0) * 1000), summary=f"{_brief(args)} -> {exc}")
        raise CapabilityError(str(exc)) from exc
    except SystemExit as exc:          # kod, który mimo trybu usługowego zawołał sys.exit
        msg = f"operacja zakończyła proces (kod {exc.code})"
        activity.record(source, "call", name, project=project, ok=False, ms=int((time.time() - t0) * 1000), summary=f"{_brief(args)} -> {msg}")
        raise CapabilityError(msg) from exc
    if not isinstance(res, dict):
        res = {"result": res}
    # operacje „tylko do odczytu” z dashboardu/pollingu nie zaśmiecają feedu; wszystko od agenta i każda zmiana jest logowana
    if source != "dashboard" or cap.mutates or cap.job:
        rp = res.get("project")                       # niektóre operacje zwracają cały obiekt projektu, log potrzebuje tylko id
        rp = rp.get("id") if isinstance(rp, dict) else rp
        activity.record(source, "call", name, project=rp if isinstance(rp, str) else project, ok=True,
                        ms=int((time.time() - t0) * 1000), summary=_brief(args))
    return res
