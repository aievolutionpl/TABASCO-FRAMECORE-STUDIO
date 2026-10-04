"""Własne, edytowalne szablony narracyjne, MIT."""
from .commands import storyboard
from .model import EditorError

TEMPLATES = {
    "product": ("Premiera produktu", ["Odkryj nową jakość.", "Codzienność zasługuje na więcej.", "{title}", "Zobacz detale.", "Poczuj różnicę.", "Poznaj produkt."]),
    "social": ("Reklama społecznościowa", ["Zatrzymaj się na chwilę.", "Znasz ten problem?", "{title}", "Tak to działa.", "Mniej wysiłku. Więcej efektu.", "Sprawdź teraz."]),
    "explainer": ("Film wyjaśniający", ["Jak to działa?", "Zacznijmy od pytania.", "{title}", "Krok pierwszy: przygotuj materiały.", "Krok drugi: nadaj im znaczenie.", "Spróbuj samodzielnie."]),
    "collaboration": ("Współpraca człowieka z AI", ["Pomysł zaczyna się od Ciebie.", "Materiały potrzebują historii.", "{title}", "Człowiek nadaje kierunek.", "Agent pomaga w montażu.", "Stwórzmy film razem."]),
}


def catalog():
    return [{"id": key, "name": value[0], "scenes": 6, "license": "MIT", "formats": ["9:16", "4:5", "1:1", "16:9"]} for key, value in TEMPLATES.items()]


def template_scenes(template_id, duration, title):
    if template_id not in TEMPLATES:
        raise EditorError("Nieznany szablon")
    name, messages = TEMPLATES[template_id]
    scenes = storyboard(duration, title, name)
    for scene, message in zip(scenes, messages):
        scene["message"] = message.replace("{title}", title)
    return scenes
