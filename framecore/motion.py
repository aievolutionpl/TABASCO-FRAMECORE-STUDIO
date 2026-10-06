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
    ("breathe","Spokojny oddech","PRODUKT","product_focus","low",["premium"]),
    ("drift-diagonal","Dryf po przekątnej","PRODUKT","product_focus","low",["editorial"]),
    ("orbit-compact","Mała orbita","LOGO","brand_reveal","medium",["social"]),
    ("spin-soft","Powolny obrót","KSZTAŁTY","supporting_reveal","low",["minimal"]),
    ("curtain-open","Kurtyna","TEKST","title_reveal","medium",["editorial"]),
    ("perspective-flip","Obrót w przestrzeni","OTWARCIE","headline_impact","high",["social"]),
    ("signal-glow","Pulsująca poświata","TEKST","caption_emphasis","medium",["social"]),
    ("camera-push","Powolne zbliżenie","PRODUKT","product_focus","low",["premium"]),
    # Motion 2.0: kinowe wejścia dla każdego typu elementu.
    ("ken-burns","Ken Burns","PRODUKT","product_focus","low",["premium","editorial"]),
    ("iris-open","Otwarcie przesłony","OTWARCIE","title_reveal","medium",["premium"]),
    ("zoom-blur-in","Wjazd z rozmyciem","OTWARCIE","headline_impact","high",["social","bold"]),
    ("glitch-in","Cyfrowy glitch","OTWARCIE","headline_impact","high",["social","bold"]),
    ("swing-in","Wahadło","TEKST","supporting_reveal","medium",["editorial"]),
    ("stretch-pop","Sprężysty skok","NAPISY","caption_emphasis","high",["social"]),
    ("skew-slide","Ukośny wjazd","TEKST","supporting_reveal","medium",["bold","editorial"]),
]
# Tekst kinetyczny: animacja każdego słowa lub litery osobno (tylko tekst i napisy).
_KINETIC = [
    ("type-on","Maszyna do pisania","TEKST KINETYCZNY","title_reveal","medium",["editorial","minimal"],"char"),
    ("word-cascade","Kaskada słów","TEKST KINETYCZNY","title_reveal","medium",["premium","editorial"],"word"),
    ("char-rise","Litery z dołu","TEKST KINETYCZNY","headline_impact","high",["bold","social"],"char"),
    ("word-blur","Słowa z mgły","TEKST KINETYCZNY","title_reveal","low",["premium"],"word"),
    ("char-wave","Fala liter","TEKST KINETYCZNY","caption_emphasis","high",["social"],"char"),
    ("scramble-in","Dekodowanie","TEKST KINETYCZNY","headline_impact","high",["bold","social"],"char"),
    ("word-highlight","Karaoke słów","TEKST KINETYCZNY","caption_emphasis","medium",["social"],"word"),
]
# Akcenty emoji: krótki, wyrazisty ruch, który podkreśla słowo; po nim tylko delikatne osiadanie.
_ACCENTS = [
    ("emoji-pop","Pop emoji","AKCENT EMOJI","emphasis","high",["social"]),
    ("emoji-bounce","Odbicie emoji","AKCENT EMOJI","emphasis","high",["social"]),
    ("emoji-wiggle","Potrząśnięcie","AKCENT EMOJI","emphasis","medium",["social","editorial"]),
    ("emoji-burst","Wybuch z poświatą","AKCENT EMOJI","emphasis","high",["bold","social"]),
]
# Wyjścia działają w ostatnich sekundach klipu i łączą się z dowolnym wejściem.
_EXITS = [
    ("fade-out","Wygaszenie","low"),("rise-out","Odlot w górę","medium"),("drop-out","Spadek","medium"),
    ("slide-out-left","Zjazd w lewo","medium"),("slide-out-right","Zjazd w prawo","medium"),
    ("blur-out","Rozmycie","low"),("scale-out","Zmniejszenie","medium"),("zoom-through","Przelot przez kamerę","high"),
    ("wipe-out","Zasłonięcie","medium"),("iris-close","Zamknięcie przesłony","medium"),
]
MAX_DURATION = 4.0
COMPONENTS = [{"id": i, "name": name, "category": cat, "intent": intent, "kind": "entrance",
               "supported_elements": ["text", "caption", "image", "shape", "video"],
               "duration_range": [0.1, MAX_DURATION], "energy": energy, "style": style,
               "parameters": {"duration": {"type": "number", "minimum": 0.1, "maximum": MAX_DURATION}},
               "preview": {"type": "live", "motion_id": i}, "license": "MIT"}
              for i, name, cat, intent, energy, style in _ITEMS]
COMPONENTS += [{"id": i, "name": name, "category": cat, "intent": intent, "kind": "kinetic", "unit": unit,
                "supported_elements": ["text", "caption"],
                "duration_range": [0.1, MAX_DURATION], "energy": energy, "style": style,
                "parameters": {"duration": {"type": "number", "minimum": 0.1, "maximum": MAX_DURATION}},
                "preview": {"type": "live", "motion_id": i}, "license": "MIT"}
               for i, name, cat, intent, energy, style, unit in _KINETIC]
# Sugerowane parametry, gdy człowiek lub agent nie poda własnych.
_DEFAULTS = {"type-on": (1.6, "linear"), "word-cascade": (1.2, "cubic-out"), "char-rise": (1.3, "back-out"),
             "word-blur": (1.4, "quad-out"), "char-wave": (1.2, "back-out"), "scramble-in": (1.4, "cubic-out"),
             "word-highlight": (1.5, "linear"), "ken-burns": (.8, "quad-out"), "iris-open": (.9, "cubic-in-out"),
             "zoom-blur-in": (.7, "expo-out"), "glitch-in": (.7, "cubic-out"), "swing-in": (.9, "back-out"),
             "stretch-pop": (.7, "back-out"), "skew-slide": (.7, "expo-out")}
for component in COMPONENTS:
    duration, easing = _DEFAULTS.get(component["id"], (.8, "cubic-out"))
    component["defaults"] = {"duration": duration, "easing": easing}
COMPONENTS += [{"id": i, "name": name, "category": cat, "intent": intent, "kind": "accent",
                "supported_elements": ["image", "text", "caption", "shape"],
                "duration_range": [0.1, MAX_DURATION], "energy": energy, "style": style,
                "parameters": {"duration": {"type": "number", "minimum": 0.1, "maximum": MAX_DURATION}},
                "defaults": {"duration": .8, "easing": "back-out"},
                "preview": {"type": "live", "motion_id": i}, "license": "MIT"}
               for i, name, cat, intent, energy, style in _ACCENTS]
EXITS = [{"id": i, "name": name, "category": "WYJŚCIE", "kind": "exit", "energy": energy,
          "supported_elements": ["text", "caption", "image", "shape", "video"],
          "duration_range": [0.1, 2.0], "defaults": {"duration": .6, "easing": "cubic-out"}, "license": "MIT"}
         for i, name, energy in _EXITS]


def registry():
    return deepcopy(COMPONENTS)


def exits():
    return deepcopy(EXITS)


def resolve(motion_id):
    return next((deepcopy(c) for c in COMPONENTS if c["id"] == motion_id), None)


def resolve_exit(exit_id):
    return next((deepcopy(c) for c in EXITS if c["id"] == exit_id), None)
