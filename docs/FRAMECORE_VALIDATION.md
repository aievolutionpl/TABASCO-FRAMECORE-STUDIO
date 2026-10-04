# Sprawdzenie FrameCore — 2026-10-04

Środowisko chmurowe: Python 3.12.14, Playwright 1.63.0, systemowy Chromium 151.0.7922.173 i dostępne FFmpeg/FFprobe. Nie skonfigurowano dostawcy generowania materiałów.

## Wyniki wykonanych testów

Nowy zestaw FrameCore: **22 testy przeszły, bez pominięć**. Polecenie:

```bash
python -m pytest tests/test_framecore.py tests/test_framecore_creator_pack.py tests/test_framecore_browser.py -o addopts='' -q
```

Sprawdzono wspólną edycję przez HTTP i osobny proces MCP, zaznaczenie, propozycje, cofanie, ponowną edycję człowieka, trwałość historii, konflikty rewizji i atomowość błędnych operacji. Import przez interfejs obejmował obraz produktu, logo oraz MP4 z dźwiękiem.

Test przeglądarkowy wyeksportował i pobrał film **15 s, 1080 × 1920, H.264 z audio**. FFprobe niezależnie sprawdził czas, rozdzielczość i kodeki. Oddzielnie wyrenderowano polski przykład współpracy **15 s, 1920 × 1080, H.264 + AAC**, dostępny w `assets/framecore-collaboration.mp4`. Klatki kontrolne obejrzano po renderze.

Dodatkowe sprawdzenia nowych funkcji:

- Ciągłość klatek kluczowych po podziale, skalowanie punktów przy zmianie formatu i odrzucanie błędnych wartości bez zmiany historii.
- Duplikowanie klipu oraz blokada zmiany na zablokowanej ścieżce.
- Ikony MIT jako materiały projektu, również dodawane przez propozycję z zachowaniem identyfikatorów.
- Dwanaście szablonów i 28 animacji. Każdą animację sprawdzono po przewinięciu w różnej kolejności; stan tego samego czasu był zgodny.
- Głośność, narastanie i wyciszenie, walidacja czasów oraz ich zachowanie po podziale audio.
- Polski interfejs, edycja klatek przez panel, kontrola struktury i rzeczywisty obraz klatki przekazywany agentowi. Bez błędów JavaScript w testowanych ścieżkach.
- Ochrona tokenem, odpowiedź HTTP 409, odrzucanie błędnych ścieżek/SVG oraz bezpieczne traktowanie tekstu zawierającego znaczniki skryptów.
- Stan eksportu dostępny z osobnego procesu; brak dostawcy nie tworzy fikcyjnych materiałów.

Ponownie uruchomiono serwer studia. Otwiera polski interfejs i lokalny Player osiąga gotowość. Układy 1512, 900 i 390 px sprawdzono pod kątem poziomego przepełnienia. Zrzut: `assets/framecore-editor.png`.

Skrypt `scripts/install-local.sh` wykonano w obecnym środowisku i potwierdzono sprawdzenie instalacji. Skrypt PowerShell przygotowano, ale nie uruchomiono na Windows. Brak narzędzia dostępu do systemu użytkownika oznacza, że nie wykonano instalacji na jego komputerze.

## Creator Pack — dodatkowa walidacja

- **60 ikon, 24 ilustracje 3D, 8 fontów, 24 tła i 12 szablonów**. Sumy SHA-256 i obecność oryginalnych licencji sprawdzono dla każdego pobranego pliku.
- Tablice znaków ośmiu fontów sprawdzono przez FontTools. Wszystkie zawierają `ĄąĆćĘęŁłŃńÓóŚśŹźŻż`. FontTools służył do audytu; aplikacja go nie wymaga.
- Test Chromium blokował wszystkie żądania poza własnym lokalnym serwerem. Biblioteka, wybór fontu, ilustracji i tła, propozycja nowego montażu i cofanie działały bez błędów JavaScript. Każdy z ośmiu fontów osiągnął stan załadowany w kompozycji przy zablokowanym internecie.
- Zrzuty animowanego tła w dwóch czasach były różne; powrót do tego samego czasu dał identyczny PNG.
- Przygotowano **48 rzeczywistych podglądów**: wszystkie 12 szablonów w formatach 16:9, 9:16, 1:1 i 4:5. Po poprawieniu wysokości etykiet i zawijania spacji sprawdzono 288 klatek tekstowych bez wykrytego przekroczenia pól. Nie jest to gwarancja dopasowania dowolnego tekstu użytkownika; po zmianach trzeba obejrzeć kadr.
- Wyrenderowano i obejrzano pokaz **12 s, 1920 × 1080, H.264 + AAC**. FFprobe potwierdził parametry; [film](../assets/framecore-creator-pack.mp4), [klatki](../assets/framecore-creator-pack-frames.jpg) i [przegląd szablonów](../assets/framecore-templates.jpg) są w repozytorium.
- `python framecore.py sample --creator-pack` tworzy niezależną kopię przykładu. Test potwierdza zachowanie wcześniejszej kopii i oryginalnego projektu.
- Ponownie sprawdzono żywy interfejs w szerokościach 1512, 900 i 390 px: brak poziomego przepełnienia dokumentu. Zrzut README pokazuje nową bibliotekę ilustracji.

Dysk `F:\CREATOR PACK` nie jest udostępniony w chmurze. Żaden materiał z tego folderu nie został przejrzany ani dodany. Zestaw 22 testów obejmuje 19 testów kontraktu/integracji i 3 testy przeglądarkowe; końcowy przebieg zakończył się w 128,90 s.

## Granice potwierdzenia

To działający etap rozbudowy, a nie wszystkie fazy z briefu. Test osobnego procesu MCP potwierdza protokół; nie oznacza skonfigurowania klienta Codex/Claude na komputerze użytkownika.

Dostawcy AI i automatyczna transkrypcja wymagają integracji. Plan scen jest szablonem lokalnym. Nie obsługujemy jeszcze dowolnego importu źródeł HyperFrames, marketplace, ripple/slip, krzywych animacji ani automatycznego dopasowania transkrypcji.

Kontrola struktury nie zastępuje oceny wizualnej i odsłuchu. Pełny historyczny zestaw repozytorium wykonano przed dołączeniem Creator Pack: **233 testy przeszły, 24 nie przeszły** (257 łącznie). Wszystkie 24 błędy dotyczą testów animacji otwierających `file://`, blokowanych przez politykę zarządzanego Chromium. Dwie nieaktualne asercje dokumentacji i nazwy profilu zostały poprawione. Wynik 22/22 dotyczy aktualnego zestawu FrameCore; cały historyczny zestaw pozostaje zablokowany w opisanej części.
