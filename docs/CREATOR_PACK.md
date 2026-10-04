# Wbudowany Creator Pack

Materiały są częścią TABASCO CREATIVES + FRAMECORE — STUDIO. Po instalacji możesz montować i eksportować film bez pobierania fontów, ikon czy ilustracji z internetu.

## Co możesz wybrać

| Zasób | Liczba | Zastosowanie |
| --- | ---: | --- |
| Ikony | 60 | Phosphor, Tabler i Lucide; edytowalny kolor |
| Ilustracje 3D | 24 | Microsoft Fluent Emoji, przezroczyste PNG |
| Rodziny fontów | 8 | Lokalne pliki TTF, wszystkie z polskimi znakami |
| Tła | 24 | 2 jednolite, 12 gradientów, 4 wzory, 6 animowanych |
| Szablony | 12 | Własna typografia, paleta, układ i sześć edytowalnych scen |
| Animacje elementów | 28 | Wejścia, odsłonięcia, unoszenie, orbita, poświata i zbliżenie |

Fonty: **Manrope, Space Grotesk, Playfair Display, Fraunces, Bebas Neue, DM Sans, DM Serif Display, JetBrains Mono**. Sprawdzono obecność `ĄąĆćĘęŁłŃńÓóŚśŹźŻż` w tablicach znaków każdego pliku. Bebas Neue i DM Serif Display zawierają jedną grubość 400; pozostałe pliki obsługują zakresy podane w katalogu.

Własne szablony obejmują premierę produktu, reklamę społecznościową, film wyjaśniający, współpracę z AI, zwiastun, magazyn, technologię, minimalny manifest, podcast, wydarzenie, lekcję i kreatywną premierę. Przy braku materiałów szablon dodaje ilustrację z biblioteki. Dodane wcześniej obrazy i nagrania mogą wejść do montażu. Przed zastąpieniem istniejącego montażu interfejs pokazuje propozycję zmian.

## W edytorze

1. **Biblioteka** — wyszukaj materiał po nazwie, temacie lub kolekcji. Filtry rozdzielają ikony i ilustracje 3D. Kliknięcie dodaje materiał na oś czasu.
2. **Tekst** — dodaj nagłówek i wybierz font. Karta fontu zmienia zaznaczony tekst; bez zaznaczenia ustawia krój dla nowych tekstów. Inspektor i panel **Marka** także zawierają fonty lokalne.
3. **Tła** — wybierz gradient, wzór lub animowane tło. Wyłącz ruch przełącznikiem, jeśli potrzebujesz statycznej kompozycji. W panelu **Marka** możesz ustawić własny jednolity kolor tła.
4. **Szablony** — wybierz wygląd, popraw sześć tekstów i zbuduj montaż. Własne fonty i ilustracje pozostają edytowalne.
5. **Animacje** — zaznacz element i wybierz ruch. Możesz też użyć klatek kluczowych w inspektorze.

Ruch tła i elementów jest liczony z czasu filmu, więc przewijanie i eksport odtwarzają tę samą kompozycję. Eksport osadza użyte fonty w HTML jako dane; nie korzysta z fontów systemowych dla rodzin lokalnych. Pliki ikon i ilustracji są kopiowane do projektu oraz zamrożonego eksportu.

## Przykład do dalszej edycji

```bash
python framecore.py sample --creator-pack
python framecore.py editor
```

W menu projektów wybierz **Creator Pack — wbudowane materiały**. Polecenie tworzy nową kopię i zachowuje istniejące projekty. [Film 12 sekund](../assets/framecore-creator-pack.mp4) · [Projekt JSON](../examples/creator-pack/project.json) · [Przegląd szablonów](../assets/framecore-templates.jpg).

## Dla agenta MCP

Najpierw odczytaj `list_library`, `list_fonts`, `list_backgrounds`, `list_templates` i `list_motion`. Używaj identyfikatorów otrzymanych z katalogów.

```json
{
  "name": "propose_changes",
  "arguments": {
    "project_id": "ID_PROJEKTU",
    "expected_revision": 0,
    "description": "Ilustracja, ikona i animowane tło",
    "commands": [
      {"name": "add_library_asset", "args": {"asset_id": "fluent-rocket", "start": 0, "duration": 3}},
      {"name": "add_icon", "args": {"icon_id": "lucide-leaf", "start": 0, "duration": 3}},
      {"name": "set_background", "args": {"background_id": "aurora-breath", "animated": true}}
    ]
  }
}
```

Podstaw rzeczywisty identyfikator i rewizję. Zastosowana propozycja ma jeden krok cofania. `set_property` z `property: "style.fontFamily"` zmienia font tekstu. `plan_storyboard` zwraca `template_id`; przekazuj go wraz z poprawionymi scenami do `assemble_storyboard`, aby zachować wygląd wybranego szablonu. Obejrzyj wynik przez `capture_frame`.

## Źródła i licencje

| Źródło | Zakres | Licencja |
| --- | --- | --- |
| [Phosphor](https://github.com/phosphor-icons/phosphor-core) | 12 ikon filmowych z istniejącej biblioteki | MIT |
| [Tabler Icons](https://github.com/tabler/tabler-icons) | 24 ikony outline | MIT |
| [Lucide](https://github.com/lucide-icons/lucide) | 24 ikony | ISC / MIT, zgodnie z plikiem projektu |
| [Microsoft Fluent Emoji](https://github.com/microsoft/fluentui-emoji) | 24 ilustracje 3D | MIT |
| [Google Fonts](https://github.com/google/fonts) | 8 rodzin fontów | SIL OFL 1.1, osobny plik każdej rodziny |

[Katalog plików](../framecore/static/library/catalog.json) zapisuje commit źródłowy, oryginalną ścieżkę, sumę SHA-256 i ścieżkę licencji. Pliki zewnętrzne pozostają niezmienione. SVG sprawdzono pod kątem skryptów i odwołań zewnętrznych; arbitralny import SVG nadal nie jest dozwolony. Tła, animacje i szablony są własnym kodem projektu MIT. [Pełne informacje prawne](../THIRD_PARTY_NOTICES.md).

`.gitattributes` zachowuje oryginalne bajty materiałów i licencji także przy automatycznej konwersji końców linii w Git na Windows. Dzięki temu sumy SHA-256 plików SVG zgadzają się po pobraniu repozytorium.

## Twoje materiały z dysku F:

Środowisko chmurowe nie ma dostępu do `F:\CREATOR PACK`. Nie dodano plików z tego folderu. Po udostępnieniu paczki można ocenić jakość, formaty, rozmiar i prawa do rozpowszechniania, a następnie dołączyć wybrane pliki do katalogu.
