"""Original MIT motion components: semantic metadata and validated parameters."""
from copy import deepcopy

_ITEMS = [
    ("premium-blur-reveal", "Wejście z rozmyciem", "TEKST", "title_reveal", "medium", ["premium", "minimal"]),
    ("impact-rise", "Mocne wejście", "OTWARCIE", "headline_impact", "high", ["bold", "social"]),
    ("soft-fade", "Delikatne pojawienie", "PRODUKT", "product_reveal", "low", ["premium", "minimal"]),
    ("slide-left", "Przesunięcie w lewo", "INTERFEJS", "supporting_reveal", "medium", ["editorial"]),
    ("scale-in", "Zbliżenie produktu", "PRODUKT", "product_focus", "medium", ["premium"]),
    ("word-pop", "Akcent napisu", "NAPISY", "caption_emphasis", "high", ["social"]),
    ("logo-settle", "Spokojne wejście logo", "LOGO", "brand_reveal", "low", ["premium"]),
    ("cta-pulse", "Puls wezwania", "DZIAŁANIE", "call_to_action", "medium", ["social", "minimal"]),
    ("slide-right", "Przesunięcie w prawo", "TEKST", "supporting_reveal", "medium", ["editorial"]),
    ("drop-in", "Wejście z góry", "TEKST", "title_reveal", "medium", ["social"]),
    ("zoom-out", "Oddalenie", "PRODUKT", "product_focus", "low", ["premium"]),
    ("rotate-in", "Obrót na wejściu", "LOGO", "brand_reveal", "medium", ["social"]),
    ("bounce-in", "Sprężyste wejście", "OTWARCIE", "headline_impact", "high", ["social"]),
    ("float", "Delikatne unoszenie", "PRODUKT", "product_focus", "low", ["premium"]),
    ("wipe-left", "Odsłonięcie poziome", "TEKST", "title_reveal", "medium", ["editorial"]),
    ("wipe-up", "Odsłonięcie pionowe", "TEKST", "title_reveal", "medium", ["editorial"]),
    ("focus-in", "Wyostrzenie", "PRODUKT", "product_reveal", "low", ["premium"]),
    ("elastic-pop", "Elastyczny akcent", "NAPISY", "caption_emphasis", "high", ["social"]),
    ("gentle-tilt", "Lekki przechył", "LOGO", "brand_reveal", "low", ["minimal"]),
    ("cinema-rise", "Filmowe wejście", "OTWARCIE", "headline_impact", "medium", ["premium"]),
]
COMPONENTS = [{"id": i, "name": name, "category": cat, "intent": intent,
               "supported_elements": ["text", "caption", "image", "shape", "video"],
               "duration_range": [0.1, 2.0], "energy": energy, "style": style,
               "parameters": {"duration": {"type": "number", "minimum": 0.1, "maximum": 2.0}},
               "preview": {"type": "live", "motion_id": i}, "license": "MIT"}
              for i, name, cat, intent, energy, style in _ITEMS]


def registry():
    return deepcopy(COMPONENTS)


def resolve(motion_id):
    return next((deepcopy(c) for c in COMPONENTS if c["id"] == motion_id), None)
