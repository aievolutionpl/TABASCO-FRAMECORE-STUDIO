"""Biblioteka marek i profile kreatywne studia filmowego.

Zapewnia:
  1. Wiele niezależnych marek (kolory, fonty, logo, reguły użycia, referencje, ograniczenia kreatywne).
  2. Wersjonowanie ustawień marek i trwałe powiązanie z projektami (zmiana aktywnej marki nie psuje starych projektów).
  3. Bezstratną migrację ze starego pojedynczego pliku profile.json.
  4. Profile kreatywne: premium_minimal, cinematic, social_fast, educational.
  5. Tryby tekstu: none, headline_only, full.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from . import common
from .common import StudioError
from .locking import atomic_write, file_lock

FORMATS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}

TEXT_MODES = ["none", "headline_only", "full"]

CREATIVE_PROFILES: dict[str, dict[str, Any]] = {
    "premium_minimal": {
        "id": "premium_minimal",
        "name": "Premium Minimal",
        "tagline": "Jeden główny motyw, dużo przestrzeni, powściągliwy ruch, bez dekoracji.",
        "description": "Zaprojektowany dla marek luksusowych, architektury, designu i produktów premium. Wyklucza automatyczne dodawanie naklejek i ikon, eliminuje wymuszone mieszanie stylów i agresywne cięcia.",
        "default_pace": "calm",
        "max_pace_gap": 7.5,
        "allow_calm_holds": True,
        "suppress_auto_icons": True,
        "allowed_no_visual_assets": True,
        "allowed_monotone": True,
        "allow_empty_text": True,
        "default_text_mode": "headline_only",
        "max_words_per_beat": 4,
        "preferred_styles": ["swiss-minimal", "dark-luxe", "gradient-mesh", "pastel-soft"],
        "avoid_styles": ["neo-brutal", "sticker-pop", "retro-synth"],
        "preferred_transitions": ["blur-dissolve", "wipe-slide", "morph"],
        "subtle_motion": True,
        "require_sfx_hits": False,
    },
    "cinematic": {
        "id": "cinematic",
        "name": "Kinowy (Cinematic)",
        "tagline": "Głębia, powolny najazd kamery, szlachetne światło i nastrojowy ton.",
        "description": "Dla opowieści wideo, zwiastunów, filmów wizerunkowych i materiałów dokumentalnych. Dłuższe ujęcia z płynnym ruchem kamery i wyciszonym tempem.",
        "default_pace": "calm",
        "max_pace_gap": 6.0,
        "allow_calm_holds": True,
        "suppress_auto_icons": False,
        "allowed_no_visual_assets": True,
        "allowed_monotone": False,
        "allow_empty_text": False,
        "default_text_mode": "headline_only",
        "max_words_per_beat": 6,
        "preferred_styles": ["cinematic-captions", "dark-luxe", "gradient-mesh"],
        "avoid_styles": ["sticker-pop", "neo-brutal"],
        "preferred_transitions": ["blur-dissolve", "mask-circle", "zoom-through"],
        "subtle_motion": True,
        "require_sfx_hits": False,
    },
    "social_fast": {
        "id": "social_fast",
        "name": "Social Fast (Rolki i Shorts)",
        "tagline": "Mocny hak, zmiana sytuacji co 2-3 s, wyrazista typografia i rytm.",
        "description": "Zoptymalizowany pod algorytmy feedu: natychmiastowe przyciągnięcie uwagi, wysoka energia, napisy słowo po słowie i dynamiczne przejścia z dźwiękiem.",
        "default_pace": "fast",
        "max_pace_gap": 2.5,
        "allow_calm_holds": False,
        "suppress_auto_icons": False,
        "allowed_no_visual_assets": False,
        "allowed_monotone": False,
        "allow_empty_text": False,
        "default_text_mode": "full",
        "max_words_per_beat": 6,
        "preferred_styles": ["kinetic-type", "creator-captions", "tool-showcase", "neo-brutal"],
        "avoid_styles": ["pastel-soft"],
        "preferred_transitions": ["punch-in", "flash-cut", "card-drop", "wipe-slide"],
        "subtle_motion": False,
        "require_sfx_hits": True,
    },
    "educational": {
        "id": "educational",
        "name": "Edukacyjny i Wyjaśniający",
        "tagline": "Maksymalna czytelność, czas na przyswojenie wiedzy, jasna hierarchia.",
        "description": "Dla tutoriali, prezentacji B2B, wyjaśnień procesów i danych. Priorytetem jest czytelność tekstu, bezpieczny kontrast i wystarczający czas na przeczytanie.",
        "default_pace": "standard",
        "max_pace_gap": 4.0,
        "allow_calm_holds": False,
        "suppress_auto_icons": False,
        "allowed_no_visual_assets": False,
        "allowed_monotone": False,
        "allow_empty_text": False,
        "default_text_mode": "full",
        "max_words_per_beat": 10,
        "preferred_styles": ["swiss-minimal", "data-story", "tool-showcase", "glass-ui"],
        "avoid_styles": ["retro-synth"],
        "preferred_transitions": ["push", "wipe-slide", "slide-stack"],
        "subtle_motion": False,
        "require_sfx_hits": False,
    },
}

DEFAULT_PALETTE = {
    "bg": "#0B0E24",
    "ink": "#F4F6FF",
    "accent": "#FF6B4A",
    "accent2": "#4F8CFF",
}

DEFAULT_BRAND_TEMPLATE: dict[str, Any] = {
    "id": "default",
    "name": "Domyślna Marka",
    "palette": DEFAULT_PALETTE.copy(),
    "font": "Inter",
    "font_heading": "",
    "tone": "konkretny, spokojny, bez przesady",
    "audience": "",
    "default_format": "4:5",
    "fps": 30,
    "creative_profile": "social_fast",
    "text_mode": "full",
    "logo": {
        "path": "",
        "position": "top-right",
        "rules": "Zachowaj bezpieczny margines min. 4% kadru; nie zniekształcaj proporcji.",
    },
    "references": [],
    "constraints": {
        "no_stickers": False,
        "no_neon": False,
        "max_words_per_beat": 6,
        "banned_colors": [],
        "banned_fonts": [],
    },
    "auto_supervise": True,
    "require_director": True,
    "version": 1,
    "onboarded": False,
    "created_at": None,
    "updated_at": None,
}


def _state_file(filename: str) -> Path:
    common.STATE_DIR.mkdir(parents=True, exist_ok=True)
    return common.STATE_DIR / filename


def _state_lock():
    return file_lock(common.STATE_DIR / ".lock")


def _read_json(filename: str, default: Any) -> Any:
    f = _state_file(filename)
    if not f.exists():
        return default
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return default


def _write_json(filename: str, data: Any) -> None:
    atomic_write(_state_file(filename), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def migrate_legacy_profile_if_needed() -> dict:
    """Bezstratna migracja istniejącego profile.json do struktury brands.json."""
    brands_file = _state_file("brands.json")
    if brands_file.exists():
        try:
            data = json.loads(brands_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "brands" in data and "active_brand_id" in data:
                return data
        except ValueError:
            pass

    # Próba odczytu ze starego profilu
    old_profile = _read_json("profile.json", None)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if old_profile and isinstance(old_profile, dict):
        brand_name = old_profile.get("name", "").strip()
        brand_id = common.slugify(brand_name) if brand_name else "default"
        if not brand_id:
            brand_id = "default"

        migrated_brand = {
            **DEFAULT_BRAND_TEMPLATE,
            "id": brand_id,
            "name": brand_name or "Domyślna Marka",
            "palette": {**DEFAULT_PALETTE, **old_profile.get("palette", {})},
            "font": old_profile.get("font", DEFAULT_BRAND_TEMPLATE["font"]),
            "tone": old_profile.get("tone", DEFAULT_BRAND_TEMPLATE["tone"]),
            "audience": old_profile.get("audience", ""),
            "default_format": old_profile.get("default_format", "4:5"),
            "fps": old_profile.get("fps", 30),
            "auto_supervise": old_profile.get("auto_supervise", True),
            "require_director": old_profile.get("require_director", True),
            "onboarded": bool(old_profile.get("onboarded", bool(brand_name))),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        store = {
            "active_brand_id": brand_id,
            "brands": {brand_id: migrated_brand},
        }
    else:
        init_brand = {
            **DEFAULT_BRAND_TEMPLATE,
            "created_at": now,
            "updated_at": now,
        }
        store = {
            "active_brand_id": "default",
            "brands": {"default": init_brand},
        }

    _write_json("brands.json", store)
    # Zapisz kompatybilny snapshot profile.json
    _sync_profile_compat(store["brands"][store["active_brand_id"]])
    return store


def _sync_profile_compat(active_brand: dict) -> None:
    """Zapisuje bieżącą markę jako profile.json dla kompatybilności wstecznej."""
    compat = {
        "onboarded": active_brand.get("onboarded", False),
        "name": active_brand.get("name", ""),
        "palette": active_brand.get("palette", DEFAULT_PALETTE),
        "font": active_brand.get("font", "Inter"),
        "tone": active_brand.get("tone", ""),
        "audience": active_brand.get("audience", ""),
        "default_format": active_brand.get("default_format", "4:5"),
        "fps": active_brand.get("fps", 30),
        "auto_supervise": active_brand.get("auto_supervise", True),
        "require_director": active_brand.get("require_director", True),
        "brand_id": active_brand.get("id", "default"),
        "version": active_brand.get("version", 1),
        "creative_profile": active_brand.get("creative_profile", "social_fast"),
        "text_mode": active_brand.get("text_mode", "full"),
    }
    _write_json("profile.json", compat)


def get_brands_store() -> dict:
    with _state_lock():
        return migrate_legacy_profile_if_needed()


def list_brands() -> dict:
    store = get_brands_store()
    active_id = store.get("active_brand_id", "default")
    res = []
    for bid, b in store.get("brands", {}).items():
        res.append({
            "id": bid,
            "name": b.get("name") or bid,
            "is_active": (bid == active_id),
            "creative_profile": b.get("creative_profile", "social_fast"),
            "text_mode": b.get("text_mode", "full"),
            "font": b.get("font", "Inter"),
            "palette": b.get("palette", DEFAULT_PALETTE),
            "tone": b.get("tone", ""),
            "audience": b.get("audience", ""),
            "creative_restrictions": b.get("creative_restrictions", []),
            "version": b.get("version", 1),
            "onboarded": b.get("onboarded", False),
            "updated_at": b.get("updated_at"),
        })
    res.sort(key=lambda x: (not x["is_active"], x["name"].lower()))
    return {"brands": res, "active_brand_id": active_id}


def get_brand(brand_id: str | None = None) -> dict:
    store = get_brands_store()
    bid = brand_id or store.get("active_brand_id", "default")
    brands = store.get("brands", {})
    if bid in brands:
        b = brands[bid]
        # scal z szablonem dla ewentualnych brakujących nowych pól
        merged = {**DEFAULT_BRAND_TEMPLATE, **b}
        merged["palette"] = {**DEFAULT_PALETTE, **b.get("palette", {})}
        merged["is_active"] = (bid == store.get("active_brand_id"))
        return merged
    # jeśli brak podanego id, fallback na aktywną lub domyślną
    active_id = store.get("active_brand_id", "default")
    if active_id in brands:
        b = brands[active_id]
        merged = {**DEFAULT_BRAND_TEMPLATE, **b}
        merged["palette"] = {**DEFAULT_PALETTE, **b.get("palette", {})}
        merged["is_active"] = True
        return merged
    return {**DEFAULT_BRAND_TEMPLATE, "is_active": True}


def set_brand(brand_id_or_patch: str | dict, patch: dict | None = None) -> dict:
    """Zapisuje lub aktualizuje markę i podbija numer wersji."""
    if isinstance(brand_id_or_patch, dict):
        if patch is None:
            patch = brand_id_or_patch
            brand_id = patch.get("id")
        else:
            brand_id = str(patch)
            patch = brand_id_or_patch
    else:
        brand_id = str(brand_id_or_patch)
        patch = patch or {}

    with _state_lock():
        store = migrate_legacy_profile_if_needed()
        brands = store.setdefault("brands", {})
        bid = brand_id or patch.get("id") or store.get("active_brand_id", "default")
        bid = common.slugify(str(bid))
        if not bid:
            raise StudioError("id marki nie może być puste")

        current = brands.get(bid, {**DEFAULT_BRAND_TEMPLATE, "id": bid, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        # walidacja i aplikowanie pól
        updated = dict(current)
        for k, v in patch.items():
            if k == "palette":
                if not isinstance(v, dict):
                    raise StudioError("palette musi być słownikiem kolorów")
                pal = dict(updated.get("palette", DEFAULT_PALETTE))
                for ck, cv in v.items():
                    s_cv = str(cv).strip()
                    if re.fullmatch(r"#[0-9a-fA-F]{3}", s_cv):
                        s_cv = "#" + "".join(c * 2 for c in s_cv[1:])
                    if not re.fullmatch(r"#[0-9a-fA-F]{6}", s_cv):
                        raise StudioError(f"palette.{ck}: kolor musi mieć postać #RRGGBB (np. #FF6B4A)")
                    pal[ck] = s_cv
                updated["palette"] = pal
            elif k == "creative_profile":
                if v not in CREATIVE_PROFILES:
                    raise StudioError(f"nieznany profil kreatywny '{v}'. Dozwolone: {list(CREATIVE_PROFILES)}")
                updated[k] = v
            elif k == "text_mode":
                if v not in TEXT_MODES:
                    raise StudioError(f"nieznany tryb tekstu '{v}'. Dozwolone: {TEXT_MODES}")
                updated[k] = v
            elif k == "default_format":
                if v not in FORMATS:
                    raise StudioError(f"default_format: jedno z {list(FORMATS)}")
                updated[k] = v
            elif k == "fps":
                if not isinstance(v, int) or not 12 <= v <= 120:
                    raise StudioError("fps: liczba całkowita 12-120")
                updated[k] = v
            elif k in ("auto_supervise", "require_director"):
                updated[k] = bool(v)
            elif k == "logo":
                if isinstance(v, dict):
                    updated["logo"] = {**updated.get("logo", {}), **v}
            elif k == "constraints":
                if isinstance(v, dict):
                    updated["constraints"] = {**updated.get("constraints", {}), **v}
            elif k == "references":
                if isinstance(v, list):
                    updated["references"] = v
            elif k in ("name", "font", "font_heading", "tone", "audience"):
                updated[k] = str(v)[:300]

        if "name" in updated:
            updated["onboarded"] = bool(str(updated["name"]).strip())

        # inkrementacja wersji przy zmianie istniejącej marki
        is_new = (bid not in brands)
        if is_new:
            updated["version"] = patch.get("version", 1)
        else:
            updated["version"] = current.get("version", 1) + 1
        updated["updated_at"] = now
        brands[bid] = updated

        if not store.get("active_brand_id") or store.get("active_brand_id") == bid:
            store["active_brand_id"] = bid
            _sync_profile_compat(updated)

        _write_json("brands.json", store)
        updated["is_active"] = (store.get("active_brand_id") == bid)
        return updated


def activate_brand(brand_id: str) -> dict:
    with _state_lock():
        store = migrate_legacy_profile_if_needed()
        brands = store.get("brands", {})
        bid = common.slugify(brand_id)
        if bid not in brands:
            raise StudioError(f"brak marki '{brand_id}'. Dostępne: {list(brands.keys())}")
        store["active_brand_id"] = bid
        _write_json("brands.json", store)
        active_brand = brands[bid]
        _sync_profile_compat(active_brand)
        res = dict(active_brand)
        res["is_active"] = True
        res["active_brand_id"] = bid
        return res


def delete_brand(brand_id: str) -> dict:
    with _state_lock():
        store = migrate_legacy_profile_if_needed()
        brands = store.get("brands", {})
        bid = common.slugify(brand_id)
        if bid not in brands:
            raise StudioError(f"brak marki '{brand_id}'")
        if len(brands) <= 1:
            raise StudioError("nie można usunąć jedynej marki w studio")
        del brands[bid]
        if store.get("active_brand_id") == bid:
            store["active_brand_id"] = next(iter(brands.keys()))
            _sync_profile_compat(brands[store["active_brand_id"]])
        _write_json("brands.json", store)
        return {"deleted": bid, "active_brand_id": store["active_brand_id"]}


def brand_snapshot_for_project(brand_id: str | None = None) -> dict:
    """Tworzy niezależną migawkę marki do trwałego zapisania w projekcie."""
    b = get_brand(brand_id)
    return {
        "brand_id": b["id"],
        "name": b["name"],
        "brand_name": b["name"],
        "version": b.get("version", 1),
        "palette": dict(b.get("palette", DEFAULT_PALETTE)),
        "font": b.get("font", "Inter"),
        "font_heading": b.get("font_heading", ""),
        "tone": b.get("tone", ""),
        "creative_profile": b.get("creative_profile", "social_fast"),
        "text_mode": b.get("text_mode", "full"),
        "logo": dict(b.get("logo", {})),
        "constraints": dict(b.get("constraints", {})),
        "snapshot_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
