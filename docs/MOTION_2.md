# Ruch 2.0 — tekst kinetyczny, wyjścia i look filmowy

Ruch 2.0 rozbudowuje silnik kompozycji FrameCore. Każdy efekt jest czystą funkcją czasu filmu: ta sama klatka w podglądzie, w `capture_frame` i w eksporcie MP4 wygląda identycznie. Projekt nadal przechowuje wyłącznie zamknięte słowniki wartości, nigdy dowolny CSS ani HTML.

## Co nowego

| Obszar | Co dostajesz |
| --- | --- |
| **Tekst kinetyczny** | 7 animacji, które ruszają każdym słowem lub literą: maszyna do pisania z kursorem, kaskada słów, litery z dołu, słowa z mgły, fala liter, dekodowanie (scramble) i karaoke słów w kolorze akcentu marki. |
| **Nowe wejścia** | Ken Burns, otwarcie przesłony, wjazd z rozmyciem, cyfrowy glitch z rozszczepieniem RGB, wahadło 3D, sprężysty skok i ukośny wjazd. Łącznie **42 animacje wejścia** (było 28). |
| **Wyjścia** | 10 animacji końca klipu: wygaszenie, odlot w górę, spadek, zjazd w lewo i prawo, rozmycie, zmniejszenie, przelot przez kamerę, zasłonięcie, zamknięcie przesłony. Łączą się z dowolnym wejściem. |
| **Krzywe ruchu** | Do czterech dotychczasowych dochodzą: ekspresowa (`expo-out`), z odbiciem (`back-out`), elastyczna (`elastic-out`) i miękka S (`cubic-in-out`). |
| **Wygląd elementu** | Cienie (miękki, uniesienie, poświata, neon, długi cień), wypełnienie gradientem (tekst, kształty, ikony), odstęp liter, obrys tekstu, tryby mieszania i dopasowanie obrazu „wypełnij kadr”. |
| **Look filmu** | Korekcja koloru (kinowy, ciepły, chłodny, żywy, wyblakły, czarno-biały, noir), winieta, deterministyczne ziarno filmowe, kaszeta kinowa i przejścia na cięciach scen: przez czerń, błysk, kurtyna w kolorze marki, light leak i rozmycie. |
| **Rozmycie ruchu** | Opcja finalnego eksportu: 4 podklatki uśredniane w migawce 180°. Szybkie wejścia wyglądają jak z kamery, kosztem ok. 4× dłuższego renderu. |
| **Szablony** | Każdy z 12 szablonów ma teraz własny tekst kinetyczny sceny tytułowej, wyjście nagłówków i look filmu. |

## W edytorze

- **Animacje** — filtry *Wszystkie / Wejścia / Tekst kinetyczny / Wyjścia*, podgląd na żywo po najechaniu na kafelek, podświetlenie animacji zaznaczonego klipu. Kliknięcie kafelka nadaje ruch z dobranym czasem i krzywą, a potem odtwarza podgląd wejścia lub końca klipu.
- **Właściwości → Ruch** — wybór wejścia i wyjścia z listy, czas i krzywa dla każdego oraz przyciski *Podgląd wejścia* / *Podgląd wyjścia*.
- **Właściwości → Wygląd i efekty** — cień i jego kolor, mieszanie, dopasowanie obrazu, odstęp liter, obrys oraz gradient z podglądem.
- **Ustawienia projektu → Efekty filmowe** (nic nie zaznaczono) — pięć looków jednym kliknięciem (*Czysty, Kino, Rolka, Retro, Noir*) i ręczne suwaki: kolor, winieta, ziarno, kaszeta, przejścia scen, czas przejścia i rozmycie ruchu.

Wszystkie zmiany trafiają do wspólnej historii cofania i są widoczne dla agenta.

## Dla agentów (MCP i wbudowany agent)

```json
{"name": "apply_motion", "arguments": {"element_id": "el_…", "motion_id": "char-rise"}}
{"name": "apply_exit", "arguments": {"element_id": "el_…", "exit_id": "blur-out", "duration": 0.5}}
{"name": "set_property", "arguments": {"element_id": "el_…", "property": "style.gradient",
  "value": {"from": "#fff1dc", "to": "#ff7a45", "angle": 100}}}
{"name": "set_canvas_fx", "arguments": {"fx": {"grade": "cinematic", "vignette": 0.4, "grain": 0.2,
  "transition": "light-leak", "transitionDuration": 0.9, "motionBlur": true}}}
```

`list_motion` zwraca `components` (z `kind`: `entrance` lub `kinetic` i sugerowanymi `defaults`), `exits` oraz `easings`. Bez podanego czasu i krzywej `apply_motion` użyje wartości sugerowanych. Każde narzędzie wymaga `project_id` i `expected_revision`. `inspect_project` ostrzega dodatkowo, gdy wejście i wyjście nakładają się w zbyt krótkim klipie (`motion_overlap`).

## Filmy demo

Oba filmy powstały wyłącznie przez API FrameCore i są edytowalnymi projektami:

```bash
python framecore.py sample --showreel   # 16:9, 24 s, sześć scen po 4 s
python framecore.py sample --reel       # 9:16, 12 s, trzy sceny po 4 s
python scripts/render-showcase.py       # tworzy oba projekty, eksportuje MP4 i podglądy README
```

| Film | Co pokazuje |
| --- | --- |
| [Showreel Motion 2.0](../assets/framecore-motion2-showreel.mp4) | Kinetyczne nagłówki z gradientem, maszynę do pisania, karaoke, karty z przesłoną/sprężyną/ukośnym wjazdem i glitchem ilustracji, neonowe dekodowanie, look *Kino* z light leakami na cięciach i rozmyciem ruchu. |
| [Rolka 9:16](../assets/framecore-motion2-reel.mp4) | Pionowy format, karaoke dużych napisów, sprężyste emoji, look *Rolka* z błyskami na cięciach. |

Tła pochodzą z kolekcji FrameCore Cinema (materiały generowane AI, [pochodzenie](CAMPAIGN_ASSETS.md)); muzyka jest syntetyzowana proceduralnie w `framecore/showcase.py`; ilustracje to Microsoft Fluent Emoji (MIT).

## Ograniczenia

- Tekst kinetyczny dzieli tekst na słowa i litery w przeglądarce; bardzo długie akapity animowane literami mogą spowolnić podgląd.
- Gradient na tekście kinetycznym jest nakładany na każde słowo lub literę osobno.
- Rozmycie ruchu działa tylko w finalnym eksporcie, nie w szkicu ani w podglądzie.
- Przejścia scen działają na granicach scen z planu (`scenes`); projekt bez scen ma zwykłe cięcia.

Panel **Efekty** rozszerza ten system o przejścia dla poszczególnych scen, looki klipów z regulacją siły oraz narzędzia timeline. [Aktualna instrukcja i API](EDITING_EFFECTS.md).
