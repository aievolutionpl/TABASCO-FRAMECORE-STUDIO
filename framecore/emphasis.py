"""Emoji i podkreślenia tylko tam, gdzie wzmacniają treść.

Zasada: ikona lub emoji pojawia się, gdy podkreśla konkretne słowo albo wizualizuje
pojęcie z tekstu. Nie jest dekoracją sceny. Najwyżej jeden akcent na scenę.
"""
import re

# Rdzeń słowa (małe litery, bez polskich końcówek) → ilustracja Fluent Emoji z biblioteki.
KEYWORDS = [
    (("rakiet", "start", "premier", "launch", "wystartuj", "wzlot"), "fluent-rocket"),
    (("pomysł", "pomysl", "idea", "innowac", "odkryj", "zrozum", "wiedz"), "fluent-light-bulb"),
    (("agent", "robot", "ai", "sztuczn", "automat"), "fluent-robot"),
    (("film", "kino", "wideo", "scen", "montaż", "montaz", "zwiastun"), "fluent-clapper-board"),
    (("kamer", "nagran", "zdjęc", "zdjec", "foto", "aparat"), "fluent-movie-camera"),
    (("muzyk", "rytm", "dźwięk", "dzwiek", "melodi"), "fluent-musical-note"),
    (("podcast", "rozmow", "głos", "glos", "posłuchaj", "posluchaj", "mikrofon"), "fluent-microphone"),
    (("czas", "minut", "szybk", "teraz", "dziś", "dzis"), "fluent-hourglass-done"),
    (("cel", "skuteczn", "efekt", "precyz", "trafi"), "fluent-bullseye"),
    (("prezent", "oferta", "rabat", "gratis", "bonus"), "fluent-wrapped-gift"),
    (("ogień", "ogien", "gorąc", "gorac", "hit", "energi", "zatrzym"), "fluent-fire"),
    (("sukces", "świętuj", "swietuj", "wydarzen", "dołącz", "dolacz", "zaproszen", "impreza"), "fluent-party-popper"),
    (("lekcj", "nauk", "kurs", "krok"), "fluent-books"),
    (("świat", "swiat", "global", "międzynar", "miedzynar"), "fluent-globe-showing-europe-africa"),
    (("rozw", "wzrost", "natur", "eko", "rośn", "rosn"), "fluent-seedling"),
    (("kolor", "kreat", "design", "forma", "sztuk"), "fluent-artist-palette"),
    (("komputer", "aplikac", "narzędzi", "narzedzi", "technolog", "kod"), "fluent-laptop"),
    (("ogłosz", "oglosz", "uwag", "sprawdź", "sprawdz", "nowość", "nowosc"), "fluent-megaphone"),
    (("gwiazd", "najlepsz", "premium", "wyjątkow", "wyjatkow", "jakość", "jakosc"), "fluent-star"),
    (("magi", "nowa", "nowe", "nowy", "zmień", "zmien"), "fluent-sparkles"),
    (("gra", "zabaw", "gamin"), "fluent-video-game"),
]
STOP = {"i", "w", "z", "na", "do", "to", "się", "sie", "jest", "nie", "co", "jak", "od", "o", "a", "że", "ze", "po", "dla", "ten", "ta", "twój", "twoj", "twoja", "twoje"}
# Krótkie rdzenie dopasowujemy dokładnie, aby „grafika” nie stała się grą, a „celebryta” celem.
EXACT = {"ai", "gra", "hit", "cel", "kod", "eko"}
EMOJI_MOTIONS = ("emoji-pop", "emoji-bounce", "emoji-wiggle", "emoji-burst")


def is_emoji(asset):
    """Ikony i ilustracje Fluent Emoji; tła i sceny z biblioteki nie są akcentem."""
    if not asset or asset.get("kind") != "image":
        return False
    if asset.get("role") == "icon":
        return True
    from .library import manifest
    library_id = (asset.get("provenance") or {}).get("library_id")
    return any(a["id"] == library_id and a["kind"] == "illustration" for a in manifest()["assets"])


def words(text):
    return [w for w in re.split(r"\s+", text.strip()) if w]


def clean(word):
    return re.sub(r"[^\w]", "", word.lower())


def emoji_for(word):
    w = clean(word)
    if not w or w in STOP:
        return None
    for stems, emoji in KEYWORDS:
        if any(w == stem if stem in EXACT else w.startswith(stem) for stem in stems):
            return emoji
    return None


def suggest(text):
    """Najmocniejsze słowo z przypisanym emoji: (słowo, emoji) albo None, gdy nic nie warto podkreślać."""
    for word in words(text):
        emoji = emoji_for(word)
        if emoji:
            return re.sub(r"^[^\w]+|[^\w]+$", "", word), emoji
    return None


def word_index(text, word):
    target = clean(word)
    return next((i for i, w in enumerate(words(text)) if clean(w) == target), None)


def emphasis_time(e, word):
    """Lokalny czas, w którym słowo jest już widoczne — ta sama formuła co w composition.js."""
    from .motion import resolve
    m = e.get("motion")
    if not m:
        return .15
    component = resolve(m["id"]) or {}
    count = max(1, len(words(e["text"])))
    index = word_index(e["text"], word)
    if component.get("kind") == "kinetic" and index is not None:
        span = max(m["duration"], e["duration"] - .3) if m["id"] == "word-highlight" else m["duration"]
        return min(e["duration"] - .05, span * (index + 1) / count)
    return min(e["duration"] - .05, m["duration"])


def emphasize(p, e, word=None, emoji=True, emoji_id=None, motion_id="emoji-pop", color=None, marker=True):
    """Podkreśl słowo w tekście i opcjonalnie dodaj emoji, które wskakuje razem z nim. Zwraca element emoji albo None."""
    from .library import library_asset
    from .model import EditorError, element
    if e["type"] not in {"text", "caption"}:
        raise EditorError("Podkreślenie działa z tekstem i napisami")
    if not word:
        found = suggest(e["text"])
        if not found:
            raise EditorError("Nie widzę słowa, które warto podkreślić; wskaż je w polu word")
        word = found[0]
    if word_index(e["text"], word) is None:
        raise EditorError("Tego słowa nie ma w tekście")
    clear(p, e)
    e["style"]["emphasis"] = {"word": re.sub(r"^[^\w]+|[^\w]+$", "", word), "color": color or p["brand"]["colors"]["accent"], "marker": bool(marker)}
    if not emoji:
        return None
    asset = library_asset(emoji_id or emoji_for(word) or "fluent-sparkles")
    p["assets"].append(asset)
    w, h = p["canvas"]["width"], p["canvas"]["height"]
    st = e["style"]
    size = max(64, min(w * .2, st["fontSize"] * 1.25))
    lines = e["text"].split("\n")
    est = min(e["width"], max(len(line) for line in lines) * (st["fontSize"] * .52 + st.get("letterSpacing", 0)))
    x = {"left": e["x"] + est + size * .3, "center": e["x"] + e["width"] / 2 + est / 2 + size * .25,
         "right": e["x"] + e["width"] - est - size * 1.15}[st["align"]]
    block = min(e["height"], len(lines) * st["fontSize"] * 1.08)
    y = e["y"] + (e["height"] - block) / 2 - size * .45
    x, y = max(0, min(w - size, x)), max(0, min(h - size, y))
    at = emphasis_time(e, word)
    clip = element(p, "image", assetId=asset["id"], sceneId=e.get("sceneId"), start=round(e["start"] + max(0, at - .05), 3),
                   duration=round(e["duration"] - max(0, at - .05), 3), x=x, y=y, width=size, height=size,
                   motion={"id": motion_id, "duration": .8, "easing": "back-out"})
    if e.get("exit"):
        clip["exit"] = dict(e["exit"])
    p["elements"].append(clip)
    e["style"]["emphasis"]["emojiElementId"] = clip["id"]
    return clip


def clear(p, e):
    """Usuń podkreślenie i powiązane z nim emoji."""
    em = e["style"].pop("emphasis", None)
    if em and em.get("emojiElementId"):
        p["elements"] = [x for x in p["elements"] if x["id"] != em["emojiElementId"]]
